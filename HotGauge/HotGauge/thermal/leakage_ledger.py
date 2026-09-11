"""Leakage at the SOLVED temperatures, per unit and per zone (§P0.22, D3).

The cache-leakage objective (``MRParams(zone_targets=...)``) asks the planner to hold the caches
at a temperature chosen for leakage rather than for the hot spot. Whether that bought anything is
a question the temperature field alone cannot answer -- it needs the leakage each unit dissipates
AT the solved temperature, priced with the same reference and the same curve the feedback loop
used. That is what this module does, and it deliberately reuses the loop's own arithmetic
(``LeakageModel.scale`` on ``leakage_ref``) so the ledger and the solve cannot disagree.

Which units count -- the pipeline's own rule, not a name list
-------------------------------------------------------------
A unit counts ONCE if, and only if, its temperature key -- ``name_map(unit)``: a floorplan block,
or the synthetic ``__agg__L3`` for the bridged L3 aggregate -- is in the solved field. That is
exactly "power that lands on a real floorplan block", the denominator every recorded thermal
result is a fraction of (``examples/cold_zone_prize.die_ratios``), and it reproduces that
function's static power and cache share to four figures on the 34-core die. McPAT's restating
rows (``Processor``, ``Processor/Total Cores``, ``NUCA``, the intermediate parents) map to no
block and drop out by construction; the bare ``Core<N>`` row maps to ``core_other_N`` and counts,
which is the leakage the McPAT-leaf view loses (RESULTS_REGISTER §1.2's "upper bound").

`[!]` Two wrong rules preceded this one, both on the first D3 rows (9 Sep): summing every key in
the reference tripled the die total (45.7 W on a 99 W die), and a true-leaf rule dropped the
``core_other`` slab (a 3.25x swing on the same field). The cache figure was never affected --
L2 leaves plus the L3 aggregate -- the die total was, twice. Hence the test that pins this rule to
``die_ratios``.

Conventions, both the loop's: the LAST sample of a temperature series; a temperature at or below
``t_floor_K`` is a block outside the die layer (3D-ICE emits 0 K there) and scales as ``T_ref``
(factor 1.0), exactly as ``rescale_trace`` treats it. Zone membership is decided on the
temperature KEY with the ``__agg__`` prefix stripped, so ``^(L2|L3)`` catches ``L2_7``, ``L3_12``
and the bridged ``L3`` aggregate alike.
"""
import re

import numpy as np

SYNTHETIC_PREFIX = '__agg__'


def _last(x):
    a = np.ravel(np.asarray(x, dtype=float))
    return float(a[-1]) if a.size else float('nan')


def unit_leakage_W(temps, leakage_ref, model, T_ref, name_map, t_floor_K=200.0):
    """``{unit: (leakage_W_at_T, temp_key, T_K)}`` for every unit that lands on the solved die.

    A unit whose temperature key is not in ``temps`` is NOT on the die (a McPAT restatement, a
    bus, an unmapped name) and is omitted; :func:`leakage_ledger` reports what was omitted. A
    unit whose block is at or below the floor is priced at ``T_ref`` and flagged ``T_K = None``.
    """
    out = {}
    temps = temps or {}
    for unit, leak in (leakage_ref or {}).items():
        q0 = _last(leak)
        if not np.isfinite(q0):
            continue
        key = name_map(unit) if name_map is not None else unit
        if key is None or key not in temps:
            continue
        T = _last(temps[key])
        if not np.isfinite(T) or T <= t_floor_K:
            out[unit] = (q0, key, None)
            continue
        out[unit] = (q0 * float(model.scale(T, T_ref=T_ref, temp_units='K')), key, T)
    return out


def zone_leakage_W(temps, leakage_ref, model, T_ref, name_map, pattern=None, t_floor_K=200.0):
    """Leakage [W] at the solved temperatures summed over on-die units whose temperature key
    matches ``pattern`` (regex search on the key with ``__agg__`` stripped); all of them when
    ``None``."""
    rx = re.compile(pattern) if pattern else None
    tot = 0.0
    for _unit, (q, key, _T) in unit_leakage_W(temps, leakage_ref, model, T_ref, name_map,
                                             t_floor_K).items():
        if rx is not None:
            k = str(key)
            if k.startswith(SYNTHETIC_PREFIX):
                k = k[len(SYNTHETIC_PREFIX):]
            if not rx.search(k):
                continue
        tot += q
    return float(tot)


def leakage_ledger(temps, leakage_ref, model, T_ref, name_map, zones=None, t_floor_K=200.0):
    """The ledger a row carries.

    Returns ``{'die_leakage_W'`` (at the solved field), ``'reference_leakage_W'`` (the same units
    at ``T_ref``), ``'zones': {label: W}``, ``'n_units'`` (counted), ``'n_units_at_floor'``
    (counted at ``T_ref`` because their block is outside the die layer), ``'n_units_off_die'``
    and ``'off_die_reference_W'`` (omitted: no block behind them)``}``. ``zones`` is
    ``{label: pattern}``.
    """
    per = unit_leakage_W(temps, leakage_ref, model, T_ref, name_map, t_floor_K)
    die = float(sum(q for q, _k, _T in per.values()))
    ref = float(sum(_last(leakage_ref[u]) for u in per))
    off = [u for u in (leakage_ref or {}) if u not in per and np.isfinite(_last(leakage_ref[u]))]
    out = {'die_leakage_W': die, 'reference_leakage_W': ref,
           'n_units': len(per),
           'n_units_at_floor': int(sum(1 for _q, _k, T in per.values() if T is None)),
           'n_units_off_die': len(off),
           'off_die_reference_W': float(sum(_last(leakage_ref[u]) for u in off)),
           'zones': {}}
    for label, pat in (zones or {}).items():
        out['zones'][label] = zone_leakage_W(temps, leakage_ref, model, T_ref, name_map,
                                             pattern=pat, t_floor_K=t_floor_K)
    return out
