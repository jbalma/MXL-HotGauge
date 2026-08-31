"""Spend the cooling budget where it buys the most leakage, not where the die is hottest.

Why this exists
---------------
``microrefrigeration.clipping_plan`` allocates removal by **temperature excess**: every block above
the target gets exactly enough cooling to bring it to the target, subject to device caps. That is
the right policy when the objective is *hold a thermal limit* -- which is what every catalogue
result so far has measured.

The photonic-cooling architecture argument (``docs/Photonic_Cooling_Devices___v9.pdf`` Sections
1.14 and 10.8) changes the objective. Cooling is no longer only about holding a limit; it is about
suppressing the static-power term, which carries ``exp(-Vth/(n kB Tj/q))``. Under that objective
the question for each block is not *how far above the target are you* but **how many watts of
leakage does the next watt of cooling remove**.

Those two policies rank blocks differently, and the gap is large. Measured on this project's own
calibrated curve, the same L2 block's marginal leakage response varies **25x with its own
temperature**:

    315 K   0.135 mW/K      local doubling 274 K   -- essentially flat, cooling buys nothing
    350 K   3.382 mW/K      local doubling  10.9 K
    390 K   4.380 mW/K      local doubling   8.5 K

Temperature excess cannot see that. A block 5 K above target at 315 K and one 5 K above target at
350 K look identical to ``clipping_plan`` and differ by 25x in what cooling them is worth.

The figure of merit
-------------------
Cooling block *b* by ``dT`` costs ``dT / s_b`` watts of removal, where ``s_b`` is the measured
K/W sensitivity. It saves ``(dP_leak/dT)_b * dT`` watts of leakage. So the benefit per watt spent is

    B_b  =  s_b * (dP_leak/dT)_b                                        [W saved / W removed]

which combines *how cheap this block is to cool* with *how much cooling it is worth*. Both factors
are measured -- ``s_b`` by the planner's own probe, ``dP_leak/dT`` from ``leakage_calibration/``.

**B > 1 would mean the removal pays for itself in leakage alone.** Measured on this project's
own die and curve, it does not come close: B peaks at **~0.015 W/W around 360 K**, so a watt of
extraction returns about 1.5% of itself in leakage. That is the honest size of the lever, and it
has a direct consequence -- **leakage payback alone never justifies the cooling.** The
justification stays on the performance side (holding the clock, avoiding throttle), which is what
``clipping_plan`` already optimises. This policy is therefore a **tie-breaker on top of the
thermal-limit objective, not a replacement for it**; the settled allocation decision needs a
secondary term, not an inversion.

What this module does NOT change
--------------------------------
Only the **allocation** half of the settled extraction policy. The **projection** half --
a block's removal lands on the tiles physically above it, in proportion to overlap area
(``mr_array.project_plan_to_tiles``) -- is geometry, not policy, and is untouched;
``test_mr_array.py::TestExtractionTracksPowerDensity`` still guards it. The settled decision in
``docs/PHASE0_CHECKLIST.md`` conflates the two, and only its second half is in question here.

The honest limit
----------------
McPAT rejects temperatures outside 300-400 K, so the calibrated curve stops at 310 K and clamps
below it. ``MIN_TRUSTWORTHY_T_K`` is that floor: this module refuses to allocate cooling that would
take a block below it, because the model cannot say what such cooling buys. That is also, on the
measured curve, roughly where the benefit vanishes anyway -- so the refusal costs little and stops
the planner chasing a clamp.
"""
import logging

LOGGER = logging.getLogger(__name__)

#: Below this the calibrated leakage curve clamps, so its marginal response is an artefact of the
#: clamp rather than physics. Allocation stops here. Matches
#: ``thermal_zones.CALIBRATION_FLOOR_K``; kept separate so the two can diverge if the calibration
#: is ever extended (PTM SPICE cards would do it).
MIN_TRUSTWORTHY_T_K = 310.0

#: Benefit-per-watt below which a block is not worth cooling for leakage.
#:
#: **This default was 0.01 and that was wrong** -- it sat above almost the entire measured range
#: and silently caused the policy to allocate nothing, which looked like the policy failing rather
#: than the threshold suppressing it. Measured on the project's own curve, the largest-leakage
#: block on the 34-core die returns:
#:
#:     320 K  0.0008 W/W      360 K  0.0145 W/W   (peak)
#:     340 K  0.0054 W/W      400 K  0.0123 W/W
#:
#: So spot cooling returns **at most ~1.5% of the removed heat** as leakage saving, peaking near
#: 360 K. The threshold is now set well below that so the smallness is *reported* rather than
#: hidden behind a cutoff -- which is the number a reader actually needs.
MIN_BENEFIT_W_PER_W = 1e-4


def marginal_leakage_W_per_K(T_K, leakage_W, model, h_K=1.0):
    """``dP_leak/dT`` for a block at ``T_K`` currently leaking ``leakage_W`` [W/K].

    Central difference on the calibrated curve, scaled by the block's own leakage. Positive means
    cooling reduces leakage.
    """
    T = float(T_K)
    ref = model.scale(T)
    if ref <= 0:
        return 0.0
    return float(leakage_W) * (model.scale(T + h_K) - model.scale(T - h_K)) / (2.0 * h_K * ref)


def benefit_per_watt(T_K, leakage_W, sensitivity_K_per_W, model, h_K=1.0):
    """Watts of leakage removed per watt of heat extracted, for one block at one temperature.

    Above 1.0 the extraction pays for itself in leakage before any performance benefit is counted.
    """
    s = float(sensitivity_K_per_W)
    if s <= 0:
        return 0.0
    return s * marginal_leakage_W_per_K(T_K, leakage_W, model, h_K)


def leakage_benefit_plan(block_temps_K, block_geom, params, sensitivity_K_per_W,
                         block_leakage_W, model, budget_W, n_steps=400,
                         min_T_K=MIN_TRUSTWORTHY_T_K, min_benefit=MIN_BENEFIT_W_PER_W):
    """Allocate ``budget_W`` of removal by marginal leakage benefit. Returns ``(plan, detail)``.

    Greedy and incremental rather than analytic, because the benefit *falls as a block cools* --
    the calibrated curve flattens -- so the ranking changes during allocation and a one-shot
    water-fill would over-allocate to whichever block started hottest.

    Device caps are the same ones ``clipping_plan`` applies, so the two policies are compared on
    equal terms: ``h_max * area`` and ``dt_max / s`` per block. The differences are what is being
    maximised, and that this policy takes a **budget** while ``clipping_plan`` derives its size
    from a target -- which is the policy inversion stated plainly.
    """
    budget_W = float(budget_W)
    if budget_W <= 0:
        return {}, {'reason': 'no budget'}

    state, skipped = {}, {}
    for blk, T0 in block_temps_K.items():
        geom = block_geom.get(blk)
        s = float(sensitivity_K_per_W.get(blk, 0.0))
        lk = float(block_leakage_W.get(blk, 0.0))
        if geom is None or s <= 0 or lk <= 0:
            skipped[blk] = ('no_geometry' if geom is None else
                            ('no_sensitivity' if s <= 0 else 'no_leakage'))
            continue
        T0 = float(T0)
        cap = min(params.h_max * geom['area_mm2'], params.dt_max_K / s)
        if T0 <= min_T_K or cap <= 0:
            skipped[blk] = 'already_below_trustworthy_floor' if T0 <= min_T_K else 'zero_cap'
            continue
        state[blk] = {'T': T0, 'T0': T0, 'q': 0.0, 's': s, 'leak0': lk, 'cap': cap,
                      'area_mm2': geom['area_mm2']}
    if not state:
        return {}, {'reason': 'no eligible blocks', 'skipped': skipped}

    step = budget_W / float(n_steps)
    spent = 0.0
    for _ in range(n_steps):
        best, best_b = None, 0.0
        for blk, st in state.items():
            if st['q'] >= st['cap'] - 1e-12 or st['T'] <= min_T_K:
                continue
            lk_now = st['leak0'] * model.scale(st['T']) / model.scale(st['T0'])
            b = benefit_per_watt(st['T'], lk_now, st['s'], model)
            if b > best_b:
                best, best_b = blk, b
        if best is None or best_b < min_benefit:
            break
        st = state[best]
        take = min(step, st['cap'] - st['q'], max(0.0, (st['T'] - min_T_K) / st['s']))
        if take <= 0:
            st['q'] = st['cap']
            continue
        st['q'] += take
        st['T'] -= take * st['s']
        spent += take

    plan = {b: st['q'] for b, st in state.items() if st['q'] > 0}
    detail = {
        'policy': 'leakage_benefit',
        'budget_W': budget_W, 'spent_W': spent,
        'unspent_W': budget_W - spent,
        'n_blocks_cooled': len(plan),
        'skipped': skipped,
        'per_block': {b: {'q_W': st['q'], 'T_from_K': st['T0'], 'T_to_K': st['T'],
                          'benefit_start': benefit_per_watt(st['T0'], st['leak0'], st['s'], model),
                          'capped': st['q'] >= st['cap'] - 1e-12}
                      for b, st in state.items() if st['q'] > 0},
        'leakage_saved_W': sum(
            st['leak0'] * (1.0 - model.scale(st['T']) / model.scale(st['T0']))
            for st in state.values() if st['q'] > 0),
        'note': ('unspent budget means every remaining block fell below min_benefit or hit a cap; '
                 'that is a result, not a failure -- it says the die has no more leakage worth '
                 'buying at this budget'),
    }
    return plan, detail


def leakage_saved_by_plan(plan, block_temps_K, sensitivity_K_per_W, block_leakage_W, model):
    """Leakage a given plan removes [W]. Used to score ANY plan, including ``clipping_plan``'s.

    This is what makes the two policies comparable: the clipping plan was never built to maximise
    this, so scoring it here is the fair way to ask how much it leaves on the table.
    """
    total = 0.0
    for blk, q in plan.items():
        s = float(sensitivity_K_per_W.get(blk, 0.0))
        lk = float(block_leakage_W.get(blk, 0.0))
        T0 = block_temps_K.get(blk)
        if s <= 0 or lk <= 0 or T0 is None:
            continue
        T1 = max(float(T0) - float(q) * s, MIN_TRUSTWORTHY_T_K)
        r0 = model.scale(float(T0))
        if r0 <= 0:
            continue
        total += lk * (1.0 - model.scale(T1) / r0)
    return total
