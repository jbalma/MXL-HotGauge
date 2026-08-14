"""Clock as a free variable: how fast can this part run before thermal limits bite?

Why this module exists
----------------------
Everywhere else in the pipeline ``f_nominal`` is an **input** and the model only ever derates
*downward* from it. That makes one question askable -- "how much of its rated clock does this
part keep?" -- and makes the more interesting one unaskable: "how much clock does better
cooling *buy*?". With a hard cap at ``f_nominal`` the best any cooling technology can score is
"no throttling", so a study of microrefrigeration on a part that was not throttling in the
first place necessarily returns ~0, and one on a part that was throttling returns at most the
throttled fraction. A "+3.5% ceiling" measured that way is an artefact of the cap, not physics.

Here the clock is searched instead: raise it until the die can no longer hold the thermal
limit, and report the highest clock it *can* hold. That converts a cooling improvement into
the unit the customer buys -- sustained frequency -- and it is the same measurement for every
node, so it also gives the iso-cooling generational comparison.

What sets the answer
--------------------
A candidate clock ``f`` is **sustainable** when the coupled solve at ``f``

1. converges (and passes damping verification -- an unverified point is not an answer), and
2. lands with its peak block at or below ``thermal_limit_K``.

Raising ``f`` raises dynamic power as ``(V(f)/V(f_ref))^2 * (f/f_ref)`` through the shipped V/F
table, which heats the die, which raises leakage, which heats it further -- so the search runs
the full leakage fixed point at every candidate. Peak temperature is monotone in ``f``, so
bisection is exact and costs ~log2(range/tol) solves.

**The reported clock does not inherit the uncalibrated f_max derate slope.** The criterion is a
temperature limit, not a frequency derating, so unlike the GFLOP/s numbers elsewhere it does not
rest on ``derate_per_K``. What it does rest on is the thermal limit itself (a spec choice) and
the V/F table.

Honest limits
-------------
* The shipped V/F table stops at **5.0 GHz / 1.4 V**. Above that ``voltage_for_frequency``
  clamps, so dynamic power stops rising with voltage and the model *understates* the cost of
  the clock. Searches are capped at the table's top by default; going past it sets
  ``vf_clamped`` and the result must be read as an upper bound.
* Leakage grows with voltage as well as temperature. That dependence is not in McPAT's output
  here, so it is applied as an explicit power law (``leakage_voltage_exponent``, default 1.0)
  rather than ignored -- ignoring it would flatter every high-clock result.
"""

import numpy as np

from HotGauge.power.performance_model import (voltage_for_frequency, dynamic_power_scale,
                                              DEFAULT_THROTTLE_K)

#: Top of the shipped V/F table (``configuration.performance.VF_PAIRS``). Above this the
#: voltage -- and therefore the dynamic-power cost of the clock -- is clamped.
VF_TABLE_MAX_GHZ = 5.0


def clock_power_factors(f_GHz, f_ref_GHz, leakage_voltage_exponent=1.0):
    """Multipliers ``(dynamic, leakage)`` for running at ``f_GHz`` instead of ``f_ref_GHz``.

    Dynamic follows ``P ~ C V^2 f`` exactly as ``dynamic_power_scale`` defines it. Leakage is
    scaled by ``(V/V_ref) ** leakage_voltage_exponent``: subthreshold leakage rises with supply
    voltage through DIBL, and gate leakage rises faster still, but our McPAT extraction is at a
    single voltage so the exponent is an assumption, stated here rather than buried. 1.0 is a
    deliberately mild choice; 0.0 reproduces the older behaviour of ignoring it entirely.

    Returns ``(dyn_scale, leak_scale, info)`` where ``info['vf_clamped']`` is True if either
    frequency fell outside the V/F table.
    """
    v, clamp_a = voltage_for_frequency(f_GHz)
    v_ref, clamp_b = voltage_for_frequency(f_ref_GHz)
    dyn = dynamic_power_scale(f_GHz, f_ref_GHz)
    leak = (v / v_ref) ** float(leakage_voltage_exponent) if v_ref > 0 else 1.0
    return dyn, leak, {'V': v, 'V_ref': v_ref, 'vf_clamped': bool(clamp_a or clamp_b)}


def scale_trace_for_clock(trace, leakage_ref, f_GHz, f_ref_GHz,
                          leakage_voltage_exponent=1.0):
    """Rescale a power trace and its leakage split from ``f_ref_GHz`` to ``f_GHz``.

    The two components move differently -- dynamic with ``V^2 f``, leakage with ``V^n`` -- so
    they must be scaled separately and recombined, which is why this takes the split rather
    than the total. Units absent from ``leakage_ref`` are treated as purely dynamic.

    Returns ``(scaled_trace, scaled_leakage_ref, info)``.
    """
    from HotGauge.power.traces import BasicPowerTrace

    dyn_scale, leak_scale, info = clock_power_factors(
        f_GHz, f_ref_GHz, leakage_voltage_exponent=leakage_voltage_exponent)

    powers, new_leak = {}, {}
    for unit, series in trace.powers.items():
        total = np.asarray(series, dtype=float)
        leak = leakage_ref.get(unit) if leakage_ref else None
        if leak is None:
            powers[unit] = total * dyn_scale
            continue
        leak = np.asarray(leak, dtype=float)
        if leak.shape != total.shape:
            leak = np.full(total.shape, float(np.ravel(leak)[0]))
        dynamic = total - leak
        powers[unit] = dynamic * dyn_scale + leak * leak_scale
        new_leak[unit] = leak * leak_scale
    info.update({'dyn_scale': dyn_scale, 'leak_scale': leak_scale,
                 'f_GHz': float(f_GHz), 'f_ref_GHz': float(f_ref_GHz)})
    return BasicPowerTrace(powers, trace.time_step), new_leak, info


def is_sustainable(result, thermal_limit_K=DEFAULT_THROTTLE_K):
    """Did this coupled solve hold the thermal limit?

    ``result`` is a dict with 'peak_K' plus the flags ``run_leakage_feedback`` returns. An
    unverified point counts as NOT sustainable: its peak still depends on the damping, so it is
    not evidence either way, and treating "we could not tell" as "yes" is how an unconverged
    number becomes a claim.
    """
    if result.get('diverged') or result.get('unconverged'):
        return False
    peak = result.get('peak_K')
    return peak is not None and float(peak) <= float(thermal_limit_K)


def reason_unsustainable(result, thermal_limit_K=DEFAULT_THROTTLE_K):
    """Short label for *why* a clock is not sustainable -- runaway and throttle are different
    engineering problems, and the fix for one does not help the other."""
    if result.get('diverged'):
        return 'thermal_runaway'
    if result.get('unconverged'):
        return 'unverified'
    peak = result.get('peak_K')
    if peak is None:
        return 'no_solution'
    if float(peak) > float(thermal_limit_K):
        return 'over_thermal_limit'
    return None


def find_max_sustainable_clock(evaluate, f_lo, f_hi, tol_GHz=0.05, max_evals=14,
                               thermal_limit_K=DEFAULT_THROTTLE_K,
                               cap_at_vf_table=True):
    """Largest clock the part can hold, by bisection on ``evaluate``.

    evaluate : callable(f_GHz) -> dict with 'peak_K' and the run_leakage_feedback flags. It is
               responsible for rescaling the trace (``scale_trace_for_clock``) and running the
               coupled solve.
    f_lo     : a clock believed sustainable. It IS tested -- if the part cannot hold even this,
               the answer is "no sustainable clock in range", not a number.
    f_hi     : upper end of the search. Capped at the V/F table's top unless
               ``cap_at_vf_table=False``, because past it the voltage clamps and the model
               understates the power cost of the clock.
    tol_GHz  : bracket width to stop at.

    Peak temperature is monotone in clock (more dynamic power, more leakage, hotter), so the
    sustainable set is an interval and bisection is exact rather than a heuristic.

    Returns a dict:
        'f_sustainable_GHz' : the answer, or None if even ``f_lo`` fails
        'bracket_GHz'       : (highest sustainable, lowest unsustainable) -- the residual
                              uncertainty, so it can be quoted honestly
        'limited_by'        : why the next step up failed ('thermal_runaway',
                              'over_thermal_limit', 'unverified'), or 'search_ceiling' if the
                              range ran out before the part did
        'at_ceiling'        : True when the part never hit a limit inside the range
        'vf_clamped'        : True if any evaluated clock left the V/F table
        'evaluations'       : every (f, sustainable, peak_K, reason) tried, in order
    """
    f_lo, f_hi = float(f_lo), float(f_hi)
    if f_hi <= f_lo:
        raise ValueError('f_hi ({}) must exceed f_lo ({})'.format(f_hi, f_lo))
    capped = False
    if cap_at_vf_table and f_hi > VF_TABLE_MAX_GHZ:
        f_hi, capped = VF_TABLE_MAX_GHZ, True
        if f_hi <= f_lo:
            raise ValueError('f_lo ({}) is already above the V/F table top ({} GHz); pass '
                             'cap_at_vf_table=False and treat the result as an upper bound'
                             .format(f_lo, VF_TABLE_MAX_GHZ))

    evals, vf_clamped = [], False

    def _try(f):
        nonlocal vf_clamped
        res = evaluate(f) or {}
        ok = is_sustainable(res, thermal_limit_K)
        vf_clamped = vf_clamped or bool(res.get('vf_clamped'))
        evals.append({'f_GHz': float(f), 'sustainable': ok,
                      'peak_K': res.get('peak_K'),
                      'reason': None if ok else reason_unsustainable(res, thermal_limit_K)})
        return ok, res

    out = {'evaluations': evals, 'vf_clamped': False, 'at_ceiling': False,
           'search_capped_at_vf_table': capped, 'thermal_limit_K': float(thermal_limit_K)}

    ok_lo, _ = _try(f_lo)
    if not ok_lo:
        out.update({'f_sustainable_GHz': None, 'bracket_GHz': (None, f_lo),
                    'limited_by': evals[-1]['reason'], 'vf_clamped': vf_clamped})
        return out

    ok_hi, _ = _try(f_hi)
    if ok_hi:
        # The part never hit a limit inside the range: the number is bounded by the SEARCH,
        # not by the silicon. Saying so matters -- quoting f_hi as "the maximum" would be
        # reporting our own upper bound back as a measurement.
        out.update({'f_sustainable_GHz': f_hi, 'bracket_GHz': (f_hi, None),
                    'limited_by': 'search_ceiling', 'at_ceiling': True,
                    'vf_clamped': vf_clamped})
        return out

    lo, hi, limit_reason = f_lo, f_hi, evals[-1]['reason']
    while hi - lo > tol_GHz and len(evals) < max_evals:
        mid = 0.5 * (lo + hi)
        ok, _ = _try(mid)
        if ok:
            lo = mid
        else:
            hi, limit_reason = mid, evals[-1]['reason']

    out.update({'f_sustainable_GHz': lo, 'bracket_GHz': (lo, hi),
                'limited_by': limit_reason, 'vf_clamped': vf_clamped})
    return out


# ---------------------------------------------------------------------------
# Per-core activity: the degeneracy axis
# ---------------------------------------------------------------------------
def scale_cores(trace, core_scale, default=1.0):
    """Scale each core's power independently: ``{core_index: factor}``.

    Why this exists
    ---------------
    ``replicate_trace_cores`` copies one core's power onto every core, which models a
    homogeneous many-core running the same kernel everywhere. That is the worst case for peak
    temperature -- and, it turns out, the worst possible case for microrefrigeration.
    ``examples/thermal_tiers.py`` measured 15 blocks within ``dt_max`` of the peak on the
    34-core die, and they are the *same functional units repeated across cores*: `RBB_16`,
    `RBB_0`, `cALU_16`, `cALU_0`, ... The thermal peak is N-fold degenerate, so clipping the
    hottest block buys only the 1.25 K gap to its twin, and MR has to pay for every copy to
    move the peak at all.

    Every MR result to date is therefore measured against the most hostile workload the model
    can express, and nothing else has ever been tried. This makes the alternatives expressible:

    * **single-core turbo** -- one core at full activity, the rest low, which is the
      non-degenerate case MR should be best at;
    * **mixed utilisation** -- a realistic server workload where cores are not all saturated.

    Non-core keys (``BUSES``, ``Processor``, hierarchy aggregates) are left untouched: they are
    not per-core, and ``die_power_of_trace`` already discards the ones that are not real blocks.
    Scaling is applied to the whole per-core entry -- dynamic and leakage alike -- which
    corresponds to duty-cycling the core rather than changing its microarchitecture.
    """
    import re as _re
    from HotGauge.power.traces import BasicPowerTrace
    rgx = _re.compile(r'^Core(\d+)(/.*)?$')
    powers = {}
    for key, val in trace.powers.items():
        m = rgx.match(key)
        f = float(core_scale.get(int(m.group(1)), default)) if m else 1.0
        powers[key] = np.asarray(val, dtype=float) * f
    return BasicPowerTrace(powers, trace.time_step)


def single_core_turbo(n_cores, hot_core=0, background=0.25):
    """Activity map for one saturated core against a quiet background.

    ``background`` is the fraction of full activity the other cores run at; 0.0 is the fully
    idle limit, which is optimistic about how cold the neighbours get. This is the geometry MR
    should like most: one hot core surrounded by silicon acting as a heat sink, with the
    intervention sitting upstream of the constriction resistance that dominates that path.
    """
    if not 0.0 <= background <= 1.0:
        raise ValueError('background must be in [0, 1], got {!r}'.format(background))
    return {i: (1.0 if i == hot_core else float(background)) for i in range(int(n_cores))}


def mixed_utilisation(n_cores, active_fraction=0.5, background=0.25, seed_order=None):
    """Activity map with a fraction of cores saturated and the rest at ``background``.

    ``seed_order`` optionally gives the core order to activate (default: lowest index first),
    so the placement of the hot cores is explicit rather than incidental -- adjacency matters
    thermally, and a study that changes it by accident is not comparing what it thinks.
    """
    if not 0.0 <= active_fraction <= 1.0:
        raise ValueError('active_fraction must be in [0, 1], got {!r}'.format(active_fraction))
    n = int(n_cores)
    order = list(seed_order) if seed_order is not None else list(range(n))
    n_active = int(round(active_fraction * n))
    active = set(order[:n_active])
    return {i: (1.0 if i in active else float(background)) for i in range(n)}
