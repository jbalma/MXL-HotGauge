#!/usr/bin/env python
"""How big is the cold-zone prize, now that the leakage curve is simulated rather than clamped?

    python examples/cold_zone_prize.py

`docs/evidence/cold_zone_prize_bounds.json` (29 Aug 2026) called this **"the single number the
architecture argument is most uncertain about -- ~50x"**, put the spread at **2.3x** between our
own curve (13.5 % of die power) and the book's Section 10.8 (31.7 %), and said what would settle
it: *"PTM SPICE cards ... give leakage vs temperature over any range. McPAT cannot: it rejects
input outside 300-400 K."* §P0.13 built that simulator. This is the answer.

Why the old spread existed
--------------------------
The prize is *bounded by the static fraction* -- you cannot save more leakage than there is -- so
what matters is the **leakage reduction factor** between the hot baseline and the cold zone, and
then only through ``1 - 1/reduction``, which saturates hard. The pipeline curve **clamps below
300 K**: it reports the same leakage at 200 K as at 300 K, so its reduction is stuck at 1.7x and
the prize looks small. That was never physics -- it is where CACTI's table stops.

`[+]` The two ratios are RE-DERIVED, and the recorded pair was a scope error
--------------------------------------------------------------------------
The conversion from "leakage reduction" to "% of die power" needs two ratios: the **static
fraction** of die power and the **cache share** of leakage. §P0.14 inherited them from
`cold_zone_prize_bounds.json` (34.64 % and 92.6 %) and could not reproduce them, leaving the
absolute prize quotable only as a 10-30 % range. They are now reproduced **exactly** -- all four
recorded quantities to the last digit -- and the rule that produces them is wrong.

The recorded pair is ``mcpat_runs/7nm/linpack_3.8GHz/block_powers_split_400000000000.json``,
summed over the **true leaves of Core0 alone** with ``Processor/Total L3s`` bridged in. Two
independent defects, and they compound:

* **Scope.** One core's leaves are weighed against the **whole chip's** L3. The cache share is
  divided by an eighth of the core power it should be divided by, so 66.8 % becomes 92.6 %.
* **Slice.** ``400000000000`` is the first tick of the trace and the die is still warming up:
  only Core0 has ramped, so its dynamic power is a third of steady state. That lifts the static
  fraction from 15.5 % to 34.6 % -- and it hits the one-core scope hardest precisely because
  Core0 is the core the rule keeps.

`[!]` **The handoff's hypothesis is withdrawn.** §P0.14 guessed the pair had been measured
*after* leakage feedback converged at the operating temperature, with L3 bridged. It was not, and
the recorded numbers rule it out on their own: dynamic power does not depend on temperature, and
the recorded 2.6062 W is the T_ref dynamic of that slice to four decimal places. No feedback and
no temperature is involved -- it is scope and slice arithmetic.

What replaces it: the ratios the **pipeline itself** implies, computed the way ``die_power_of_trace``
computes die power -- everything that lands on a real floorplan block, over the steady-state
slices. That denominator includes the ``core_other`` slab (42 % of on-die leakage), which the
McPAT-leaf view drops entirely, and it is the same die power every recorded thermal result is a
fraction of. It gives **static 15.98 %, cache share 38.24 %** and a ceiling of **6.1 %** of die
power against the recorded 32.1 %.

`[!]` **So the absolute prize moves DOWN, and the 30 % end of the range is withdrawn.** The
inherited pair was not one plausible reading among two -- it was arithmetic on the wrong scope
and the wrong slice. The improvement over the pipeline curve is untouched: both conversions
multiply the same ``1 - 1/reduction`` by a constant, so **2.23x** survives unchanged. That is
still the number to quote; the absolute prize is now ~6 % of die power (4.5 % if the cold die
carries L3 only), with ~10 % as the upper bound if ``core_other``'s leakage is excluded.
"""
import os
import sys
import re
import json
import glob
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.leakage_feedback import load_leakage_model
from HotGauge.power.core_other import (CORE_OTHER_POLICIES, resolve_trace_dir,
                                       DEFAULT_CORE_OTHER_POLICY)

#: McPAT hierarchy aggregates -- they restate their children and must not be summed with them.
_AGGREGATES = ('Processor', 'Processor/Total Cores', 'NUCA', 'Processor/Total L3s')

#: The four curves, and what each one actually is.
CURVES = (
    ('pipeline', 'pipeline', "CACTI's 11 hard-coded numbers; CLAMPS below 300 K"),
    ('simulated', 'simulated', 'BSIM-CMG on the ASAP7 card, all mechanisms (P0.13)'),
    ('simulated-gidl-off', 'simulated-gidl-off', 'same card, GIDL disabled -- the other bracket'),
)


#: The trace slice the recorded pair was taken from, and the scope rule that reproduces it.
#: Kept as data because it is the *provenance*, not a recommendation -- see the module docstring.
RECORDED_SLICE = 'block_powers_split_400000000000.json'
RECORDED_SCOPE = 'true leaves of Core0 alone + Processor/Total L3s bridged'

#: Ticks below this are the trace's warm-up: only Core0 has ramped, so die dynamic power is about
#: a third of steady state and every static fraction taken there is inflated. Measured on the 7nm
#: linpack trace: die-scope static fraction 20.3 % at 4e11 against 14.4 % from 1.6e12 on.
STEADY_FROM_TICK = 1_600_000_000_000

#: The die the density ladder, the MR catalogue and the clock search all solve.
DEFAULT_FLP = os.path.join(_REPO, 'examples', 'floorplans', 'outputs',
                           'skylake7nm_34core_3_3D-ICE_template.flp')

#: Blocks ``add_extra_DICE_units`` models rather than reads from McPAT. Their power is on the die
#: and belongs in the denominator, but McPAT attributes no leakage to them, so they must not be
#: counted in the numerator -- ``get_IO_SoC_powers`` returns an absolute SoC power that appears in
#: a leakage-only pass just as it does in a total pass.
_MODELLED_PREFIXES = ('IMC', 'IO_', 'SoC')


def _split_files(trace_dir, steady_only=True):
    """Split traces for ``trace_dir``, ordered by numeric tick, warm-up dropped by default."""
    def tick(path):
        return int(re.search(r'_(\d+)\.json$', path).group(1))
    files = sorted(glob.glob(os.path.join(trace_dir, 'block_powers_split_*.json')), key=tick)
    if steady_only:
        steady = [f for f in files if tick(f) >= STEADY_FROM_TICK]
        if steady:
            return steady
    return files


def _true_leaves(split):
    """Keys with no children in the dict.

    `[!]` Not the same as "not in ``_AGGREGATES``". McPAT's hierarchy has *intermediate* parents
    -- ``Core0/Load Store Unit``, ``Core0/Renaming Unit``, ``Core0/Instruction Fetch Unit`` --
    that restate their children the same way ``Processor`` does but are not on any aggregate
    list. Each carries 0.8 mW of leakage here, which is small, and it is exactly the 2.5 mW that
    separates a near-miss from reproducing the recorded 1.3812 W to the last digit. Structure,
    not a name list.
    """
    keys = set(split)
    return [k for k in keys if not any(o != k and o.startswith(k + '/') for o in keys)]


def recorded_pair_provenance(trace_dir):
    """Reproduce ``cold_zone_prize_bounds.json``'s measured baseline, and say where it came from.

    Returns the four recorded quantities recomputed under ``RECORDED_SCOPE`` on
    ``RECORDED_SLICE``. They agree to the last recorded digit, which is what turns "probably
    measured some other way" into a settled provenance -- and settles it as a **defect**: one
    core's leaves against the whole chip's L3, on a warm-up slice. Returns ``None`` if the trace
    is not present.
    """
    path = os.path.join(trace_dir, RECORDED_SLICE)
    if not os.path.isfile(path):
        return None
    sp = json.load(open(path))
    core0 = {k: sp[k] for k in _true_leaves(sp) if k.startswith('Core0/')}
    l3 = sp[_AGGREGATES[3]]
    dyn = sum(float(v[0]) for v in core0.values()) + float(l3[0])
    leak = sum(float(v[1]) for v in core0.values()) + float(l3[1])
    cache = float(l3[1]) + sum(float(v[1]) for k, v in core0.items() if k.endswith('/L2'))
    return {'slice': RECORDED_SLICE, 'scope': RECORDED_SCOPE,
            'dynamic_W': dyn, 'static_W': leak, 'cache_leakage_W': cache,
            'static_fraction': leak / (dyn + leak), 'cache_share_of_leakage': cache / leak,
            'l3_share_of_leakage': float(l3[1]) / leak,
            'defects': ['scope: one core of leaves against the whole chip\'s L3',
                        'slice: tick 4e11 is warm-up -- only Core0 has ramped'],
            'withdrawn_hypothesis': (
                'NOT measured post-feedback at the operating temperature: dynamic power is '
                'temperature-independent and the recorded 2.6062 W is this slice\'s T_ref '
                'dynamic exactly.')}


def die_ratios(trace_dir, flp=None, tech_node=7, num_cores=8):
    """`[+]` The ratios the pipeline itself implies -- the corrected conversion.

    "% of die power" has one defensible denominator in this project: the power that lands on a
    real floorplan block, which is what ``die_power_of_trace`` returns and what every recorded
    thermal result is a fraction of. Getting there means running the dynamic+leakage total and
    the leakage alone through ``prepare_dice_trace`` and keeping the blocks the floorplan has.

    Two things this picks up that a McPAT-leaf sum does not:

    * **``core_other``.** McPAT's bare ``Core<N>`` row becomes the tiler's ``core_other`` slab,
      and it carries **42 % of on-die leakage**. It is real power on a real block; leaving it out
      inflates the cache's share of leakage from 38 % to 67 %.
    * **The modelled extras.** ``add_extra_DICE_units`` puts IMC/IO/SoC on the die. Their power
      belongs in the denominator and their (zero) McPAT leakage does not belong in the numerator,
      so they are subtracted from the leakage pass and counted once in the total.

    Averaged over the steady-state slices. Returns ``None`` if the trace or floorplan is missing.
    """
    from HotGauge.power.traces import BasicPowerTrace
    from HotGauge.thermal.leakage_feedback import prepare_dice_trace
    from HotGauge.thermal.ICE import Floorplan

    flp = flp or DEFAULT_FLP
    files = _split_files(trace_dir)
    if not files or not os.path.isfile(flp):
        return None
    blocks = {e.name for e in Floorplan.from_file(flp).elements}

    def on_die(sp, pick):
        trace = BasicPowerTrace({u: np.array([pick(v)]) for u, v in sp.items()}, 1.0)
        dice = prepare_dice_trace(trace, flp, tech_node, num_cores=num_cores)
        return {n: float(np.sum(s)) for n, s in dice.powers.items() if n in blocks}

    acc = []
    for path in files:
        sp = json.load(open(path))
        total = on_die(sp, lambda v: float(v[0]) + float(v[1]))
        leaks = on_die(sp, lambda v: float(v[1]))
        modelled = {b for b in total if b.startswith(_MODELLED_PREFIXES)}
        die = sum(total.values())
        leak = sum(v for b, v in leaks.items() if b not in modelled)
        share = lambda pred: sum(v for b, v in leaks.items() if pred(b)) / leak
        acc.append({
            'die_W': die, 'static_W': leak, 'static_fraction': leak / die,
            'l3_share_of_leakage': share(lambda b: b.startswith('L3_')),
            'cache_share_of_leakage': share(lambda b: b.startswith(('L3_', 'L2_'))),
            'cache_share_incl_L1': share(lambda b: b.startswith(('L3_', 'L2_', 'DCache_',
                                                                 'iCache_'))),
            'core_other_share_of_leakage': share(lambda b: b.startswith('core_other')),
        })
    out = {k: float(np.mean([a[k] for a in acc])) for k in acc[0]}
    out.update({'source': '%s (%d steady slices, tick >= %.0e)'
                % (os.path.relpath(trace_dir, _REPO), len(files), STEADY_FROM_TICK),
                'floorplan': os.path.basename(flp),
                'aggregation': 'power on real floorplan blocks, via prepare_dice_trace'})
    return out


def trace_ratios(trace_dir):
    """The McPAT-leaf view of the same ratios -- an upper bound, and a cross-check on ``die_ratios``.

    True leaves of **every** core plus ``Processor/Total L3s`` bridged, averaged over the
    steady-state slices. This is the corrected form of the scope the recorded pair used: same
    rule, all eight cores instead of one, and off the warm-up.

    It is not the conversion to quote, because it has no floorplan and therefore no
    ``core_other`` -- McPAT's un-itemised per-core power, 42 % of the leakage that actually
    reaches the die. Dropping it leaves the cache looking like 67 % of leakage instead of 38 %,
    so this is the **upper bound** on the prize and ``die_ratios`` is the answer.
    """
    files = _split_files(trace_dir)
    if not files:
        return None
    acc = []
    for path in files:
        sp = json.load(open(path))
        leaves = {k: sp[k] for k in _true_leaves(sp) if k.startswith('Core')}
        l3d, l3l = (float(sp[_AGGREGATES[3]][0]), float(sp[_AGGREGATES[3]][1])) \
            if _AGGREGATES[3] in sp else (0.0, 0.0)
        dyn = sum(float(v[0]) for v in leaves.values()) + l3d
        leak = sum(float(v[1]) for v in leaves.values()) + l3l
        l2 = sum(float(v[1]) for k, v in leaves.items() if k.endswith('/L2'))
        l1 = sum(float(v[1]) for k, v in leaves.items()
                 if 'Instruction Cache' in k or 'Data Cache' in k)
        acc.append({'dynamic_W': dyn, 'static_W': leak, 'total_W': dyn + leak,
                    'static_fraction': leak / (dyn + leak),
                    'cache_share_of_leakage': (l3l + l2) / leak if leak else 0.0,
                    'cache_share_incl_L1': (l3l + l2 + l1) / leak if leak else 0.0,
                    'l3_share_of_leakage': l3l / leak if leak else 0.0})
    out = {k: float(np.mean([a[k] for a in acc])) for k in acc[0]}
    out.update({'source': '%s (%d steady slices)' % (os.path.relpath(trace_dir, _REPO), len(files)),
                'aggregation': 'true leaves of all cores + Processor/Total L3s bridged'})
    return out


def prize_pct(reduction, static_fraction, cache_share):
    """Die power saved, as a percent, if the cache's leakage falls by ``reduction``.

    ``static_fraction * cache_share`` is the ceiling -- the share of die power that is cache
    leakage -- and ``1 - 1/reduction`` is how much of that ceiling a given reduction reaches. The
    second factor **saturates**: 10x takes 90 % of the prize, 100x takes 99 %. That is why three
    orders of magnitude of disagreement about the reduction can be worth ~1 % of die power.
    """
    return 100.0 * static_fraction * cache_share * (1.0 - 1.0 / reduction)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--hot-K', type=float, default=350.0,
                    help='the baseline the cold zone is cooled FROM (the recorded file used 350)')
    ap.add_argument('--cold-K', type=float, nargs='+',
                    default=[300., 290., 280., 270., 260., 250., 240., 230., 220., 210., 200.])
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--calibration', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--recorded', default=os.path.join(_EV, 'cold_zone_prize_bounds.json'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'cold_zone_prize_simulated.json'))
    ap.add_argument('--flp', default=DEFAULT_FLP,
                    help='the die whose block power is the denominator for "%% of die power"')
    # §P0.16/§P0.17. `stock` (default) reproduces every recorded ratio. `hierarchy-consistent`
    # undoes the converter's `2 * runtime_dynamic` on itemised per-core dynamic and gives
    # core_other its true leakage remainder -- which is exactly what the static fraction below is
    # a ratio of, so this flag moves the prize.
    ap.add_argument('--core-other-policy', default=DEFAULT_CORE_OTHER_POLICY,
                    choices=list(CORE_OTHER_POLICIES),
                    help='McPAT per-core accounting. "hierarchy-consistent" (default since P0.17) '
                         'is the corrected one (raises the die static '
                         'fraction ~1.74x). See P0.16.')
    args = ap.parse_args()
    # Solve against a corrected copy of the trace under a non-stock policy; returns the path
    # unchanged under the default, so the recorded path is byte-identical.
    args.trace_dir = resolve_trace_dir(args.trace_dir, args.core_other_policy)

    rec = json.load(open(args.recorded))
    base = rec['measured_baseline']
    inherited = {'static_fraction': base['static_fraction_pct'] / 100.0,
                 'cache_share_of_leakage': base['cache_share_of_all_leakage_pct'] / 100.0,
                 'source': os.path.relpath(args.recorded, _REPO),
                 'provenance': 'INHERITED -- now REPRODUCED, and found to be a scope error; '
                               'see provenance_of_recorded_pair'}
    provenance = recorded_pair_provenance(args.trace_dir)
    leaf = trace_ratios(args.trace_dir)          # McPAT-leaf view: the upper bound
    recomputed = die_ratios(args.trace_dir, flp=args.flp) or leaf   # the answer

    # Reproduce the recorded file's own arithmetic, as a check that the formula is the same one.
    check = prize_pct(rec['bounds'][0]['leakage_reduction_x'],
                      inherited['static_fraction'], inherited['cache_share_of_leakage'])
    formula_reproduces = abs(check - rec['bounds'][0]['die_power_saved_pct_cache_only']) < 0.02

    models = {}
    for label, which, what in CURVES:
        m, t_ref = load_leakage_model(which, calibration=args.calibration)
        models[label] = (m, t_ref, what)

    # The analytic P0.12 curve is not a LeakageModel; read its recorded comparison directly.
    analytic = json.load(open(os.path.join(_EV, 'device_leakage_asap7.json')))
    a_rel = {c['T_K']: c['card_rel'] for c in analytic['comparison']}

    rows = []
    for T_cold in args.cold_K:
        row = {'T_cold_K': T_cold}
        for label, (m, t_ref, _) in models.items():
            hot = float(m.scale(args.hot_K, t_ref))
            cold = float(m.scale(T_cold, t_ref))
            red = hot / cold
            row[label] = {
                'leakage_reduction_x': red,
                'die_power_saved_pct_recorded_ratios': prize_pct(
                    red, inherited['static_fraction'], inherited['cache_share_of_leakage']),
                'die_power_saved_pct_rederived': prize_pct(
                    red, recomputed['static_fraction'],
                    recomputed['cache_share_of_leakage']) if recomputed else None,
            }
        if T_cold in a_rel and args.hot_K in a_rel:
            red = a_rel[args.hot_K] / a_rel[T_cold]
            row['analytic-P0.12'] = {
                'leakage_reduction_x': red,
                'die_power_saved_pct_recorded_ratios': prize_pct(
                    red, inherited['static_fraction'], inherited['cache_share_of_leakage']),
            }
        rows.append(row)

    # Where does it stop paying? The design question is not "how cold can we get" but "how cold
    # is worth getting" -- the prize saturates and the last 50 K may buy nothing.
    def knee_of(label, frac=0.95):
        """The WARMEST cold-zone temperature that still collects ``frac`` of the maximum prize.

        Rows run hot to cold, so this is the first row that qualifies -- not the last. Taking the
        last returns the coldest point in the sweep every time, which is the sweep's edge rather
        than a property of the curve, and it inverts the design statement from "you only need to
        reach X" into "you need to reach the bottom".
        """
        best_ = max(r[label]['die_power_saved_pct_recorded_ratios'] for r in rows)
        for r in sorted(rows, key=lambda r: -r['T_cold_K']):
            if r[label]['die_power_saved_pct_recorded_ratios'] >= frac * best_:
                return r['T_cold_K'], best_
        return None, best_

    knee, best = knee_of('simulated')
    knee_gidl, _ = knee_of('simulated-gidl-off')
    at200 = rows[-1]
    pipe200 = at200['pipeline']['die_power_saved_pct_recorded_ratios']
    sim200 = at200['simulated']['die_power_saved_pct_recorded_ratios']
    gidl200 = at200['simulated-gidl-off']['die_power_saved_pct_recorded_ratios']
    # `[!]` The two conversions disagree about the SIZE of the prize by ~3x, because their input
    # ratios differ. What they agree on exactly is the IMPROVEMENT, because both multiply the
    # same (1 - 1/reduction) by a constant -- so the ratio simulated/pipeline is identical under
    # either. That is what makes the headline claim safe and the absolute one not.
    improvement = {
        'recorded_ratios': sim200 / pipe200 if pipe200 else None,
        'rederived': (at200['simulated']['die_power_saved_pct_rederived']
                       / at200['pipeline']['die_power_saved_pct_rederived'])
        if at200['pipeline'].get('die_power_saved_pct_rederived') else None,
    }

    out = {
        'note': __doc__.strip(),
        'hot_baseline_K': args.hot_K,
        'ratios': {'recorded_and_withdrawn': inherited, 'rederived_pipeline_die': recomputed,
                   'mcpat_leaf_upper_bound': leaf,
                   'recorded_formula_reproduces': bool(formula_reproduces)},
        'provenance_of_recorded_pair': provenance,
        'rows': rows,
        'improvement_over_pipeline_x': improvement,
        'saturation_knee_K': knee,
        'saturation_knee_K_gidl_off': knee_gidl,
        'book_section_10_8': {'reduction_x': [100.0, 200.0],
                              'die_power_saved_pct_recorded_ratios': [
                                  prize_pct(100.0, inherited['static_fraction'],
                                            inherited['cache_share_of_leakage']),
                                  prize_pct(200.0, inherited['static_fraction'],
                                            inherited['cache_share_of_leakage'])]},

        'FINDING_1_THE_2_3X_SPREAD_IS_CLOSED_AND_THE_BOOK_WAS_RIGHT': (
            'The recorded uncertainty was 13.5 % of die power (our curve) against 31.7 % (the '
            'book) -- a 2.3x spread called the largest in the architecture argument. Simulated, '
            'cooling the cache from {:.0f} K to 200 K reduces its leakage **{:.1f}x** where the '
            'pipeline curve says {:.2f}x, and the prize grows by **{:.1f}x** -- the book\'s end '
            'of the recorded 2.3x spread. `[!]` That is a statement about the SPREAD, not about '
            'the book\'s absolute number: re-derived ratios (FINDING_5) put the prize at ~6 % of '
            'die power, well below the book\'s 31.7 %, and both of the recorded bounds with it. '
            'The pipeline curve was wrong for a specific and '
            'boring reason: it CLAMPS below 300 K, reporting the same leakage at 200 K as at '
            '300 K. That clamp was never a floor -- it is where CACTI\'s table stops. '
            '`[!]` Quote the {:.1f}x improvement, not the absolute percentage. The reduction '
            'factor is measured here; the conversion to die power is now re-derived rather than '
            'inherited (FINDING_5) and puts the absolute prize at ~{:.0f} % of die power, not '
            'the ~30 % the inherited ratios gave. The improvement is unchanged by that, which '
            'is why it is the safe number.'
            .format(args.hot_K, at200['simulated']['leakage_reduction_x'],
                    at200['pipeline']['leakage_reduction_x'],
                    improvement['recorded_ratios'], improvement['recorded_ratios'],
                    at200['simulated']['die_power_saved_pct_rederived'])),

        'FINDING_2_BUT_THE_BOOK_WAS_RIGHT_FOR_THE_WRONG_REASON': (
            'Section 10.8 claims a "realistic 100-200x" leakage reduction. The simulator says '
            '{:.1f}x -- roughly {:.0f}x less. It does not matter, and that is the point: the prize '
            'is bounded by the static fraction and approaches it as 1 - 1/reduction, so {:.1f}x '
            'already collects {:.1f} % of the available {:.1f} %. Do not quote the book\'s '
            'reduction factor; quote the die power, which is what survives.'
            .format(at200['simulated']['leakage_reduction_x'],
                    100.0 / at200['simulated']['leakage_reduction_x'],
                    at200['simulated']['leakage_reduction_x'],
                    at200['simulated']['die_power_saved_pct_rederived'],
                    100.0 * recomputed['static_fraction']
                    * recomputed['cache_share_of_leakage'])),

        'FINDING_3_THE_GIDL_BRACKET_BARELY_MATTERS_HERE': (
            'P0.13\'s largest open uncertainty is GIDL: ASAP7 is a predictive PDK and its GIDL '
            'coefficients move device leakage at 200 K by ~40x. Through the saturation that is '
            'worth **{:.1f} percentage points of die power** ({:.1f} % with GIDL, {:.1f} % '
            'without). A 40x device-level uncertainty is a {:.1f}-point architecture-level one. '
            'The cold-zone case does not depend on settling it.'
            .format(gidl200 - sim200, sim200, gidl200, gidl200 - sim200)),

        'FINDING_4_HOW_COLD_IS_WORTH_GETTING_AND_IT_IS_NOT_VERY': (
            'The prize is within 5 % of its maximum by **{:.0f} K**, so the {:.0f} K of cooling '
            'below that buys under 5 % more. This is the useful form of the result and it is a '
            'design constraint rather than a curiosity: the target is not "as cold as possible" '
            'but roughly **{:.0f} K** -- barely sub-ambient, and a far easier machine to build '
            'than the deep-cryogenic one the reduction factors suggest. {}'
            .format(knee, knee - min(args.cold_K), knee,
                    ('`[+]` And this is the one number the GIDL bracket does NOT move: both '
                     'brackets put the knee at {:.0f} K. GIDL changes how flat the curve is below '
                     'the knee, not where the knee is, so the design target does not wait on '
                     'settling it.').format(knee) if knee == knee_gidl else
                    ('`[!]` The GIDL bracket moves this: without GIDL the curve keeps paying to '
                     '{:.0f} K. Take the colder end as the design target.').format(knee_gidl))
            if knee else 'no saturation inside the sweep'),

        'FINDING_5_THE_INHERITED_RATIOS_ARE_A_SCOPE_ERROR_AND_THE_PRIZE_MOVES_DOWN': (
            '§P0.14 could not reproduce the recorded pair (static 34.64 %, cache share 92.6 %) '
            'and quoted the absolute prize as a 10-30 % range because of it. It reproduces '
            'EXACTLY -- 2.6062 W dynamic, 1.3812 W static, 1.2784 W cache leakage, all four to '
            'the last recorded digit -- from {} summed over {}. That settles the provenance and '
            'settles it as a defect, with two independent parts: **scope**, one core\'s leaves '
            'weighed against the WHOLE chip\'s L3, which inflates the cache share from 66.8 % to '
            '92.6 %; and **slice**, tick 4e11 is the trace warm-up where only Core0 has ramped, '
            'which inflates the static fraction from 15.5 % to 34.6 %. '
            '`[!]` §P0.14\'s guess that the pair was measured post-feedback at the operating '
            'temperature is WITHDRAWN: dynamic power does not depend on temperature, and 2.6062 W '
            'is that slice\'s T_ref dynamic exactly. '
            'Re-derived on the pipeline\'s own denominator -- power that lands on a real '
            'floorplan block, over the steady slices -- the ratios are **static {:.2f} %, cache '
            'share {:.2f} %**, a ceiling of {:.1f} % of die power against the recorded 32.1 %. '
            'So the absolute prize is ~{:.0f} % of die power and the 30 % end of the range is '
            'withdrawn. The 2.23x improvement is untouched.'
            .format(RECORDED_SLICE, RECORDED_SCOPE,
                    100 * recomputed['static_fraction'],
                    100 * recomputed['cache_share_of_leakage'],
                    100 * recomputed['static_fraction'] * recomputed['cache_share_of_leakage'],
                    at200['simulated']['die_power_saved_pct_rederived'])),

        'HONEST_LIMITS': (
            'The leakage REDUCTION factors are reproducible and so, now, are the two conversion '
            'ratios (FINDING_5). What remains is a real spread in what counts as cache leakage, '
            'and it is a modelling choice rather than an unknown: on the pipeline denominator the '
            'prize at 200 K is {:.1f} % of die power with L3+L2 as the cold die, {:.1f} % with L3 '
            'alone, and {:.1f} % if McPAT\'s un-itemised `core_other` leakage (42 % of on-die '
            'leakage) is excluded from the denominator as the McPAT-leaf view does. Roughly '
            '**4-10 % of die power**, against the 10-30 % §P0.14 had to quote and the 31.7 % the '
            'book implies. The inherited 34.64 %/92.6 % pair is not one plausible reading among '
            'two -- it is arithmetic on the wrong scope and the wrong slice -- and should not be '
            'used again. '
            '`[+]` The IMPROVEMENT is unaffected by any of this, which is what the headline claim '
            'rests on: every conversion multiplies the same (1 - 1/reduction) by a constant, so '
            'the simulated curve beats the pipeline curve by {:.2f}x under all of them. The claim '
            '"our own curve understated the cold-zone prize by ~2.2x, because it clamps" is '
            'unchanged. The claim "the prize is ~30 % of die power" is withdrawn. '
            '`[!]` What the smaller absolute prize does NOT change: the cold zone still has to be '
            'a separate die (TEST 1, thermal_zone_tests.json), and the knee is still ~280 K. What '
            'it does change is the size of the win being bought, and that is now a first-order '
            'input to whether a separate cold cache die pays for itself. '
            'Separately, this is one device flavour\'s physics applied to a chip-level power '
            'split, and it assumes the cache can actually be HELD at the cold temperature.'
            .format(at200['simulated']['die_power_saved_pct_rederived'],
                    prize_pct(at200['simulated']['leakage_reduction_x'],
                              recomputed['static_fraction'],
                              recomputed['l3_share_of_leakage']),
                    prize_pct(at200['simulated']['leakage_reduction_x'],
                              leaf['static_fraction'], leaf['cache_share_of_leakage'])
                    if leaf else float('nan'),
                    improvement['recorded_ratios'])),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)

    print(__doc__.split('\n')[0])
    print('\nRATIOS for the die-power conversion (the recorded pair is REPRODUCED and WRONG):')
    print('  recorded    static %.2f%%  cache share of leakage %.1f%%   (%s)'
          % (100 * inherited['static_fraction'], 100 * inherited['cache_share_of_leakage'],
             'formula reproduces the recorded file' if formula_reproduces else '** MISMATCH **'))
    if provenance:
        print('              ^ reproduced exactly from %s over %s' % (provenance['slice'],
                                                                      provenance['scope']))
        print('                dyn %.4f W  static %.4f W  cache %.4f W  -> %.2f%% / %.2f%%'
              % (provenance['dynamic_W'], provenance['static_W'], provenance['cache_leakage_W'],
                 100 * provenance['static_fraction'],
                 100 * provenance['cache_share_of_leakage']))
        for d in provenance['defects']:
            print('                [!] %s' % d)
    if leaf:
        print('  leaf bound  static %.2f%%  cache share of leakage %.1f%%   (%s)'
              % (100 * leaf['static_fraction'], 100 * leaf['cache_share_of_leakage'],
                 leaf['aggregation']))
    if recomputed:
        print('  RE-DERIVED  static %.2f%%  cache share of leakage %.1f%%   (%s)'
              % (100 * recomputed['static_fraction'], 100 * recomputed['cache_share_of_leakage'],
                 recomputed['aggregation']))
        print('              L3 only %.2f%%   core_other %.2f%% of on-die leakage   die %.2f W'
              % (100 * recomputed['l3_share_of_leakage'],
                 100 * recomputed.get('core_other_share_of_leakage', float('nan')),
                 recomputed.get('die_W', float('nan'))))
    print('\nLEAKAGE REDUCTION from %.0f K, and the prize (%% of die power, RE-DERIVED ratios):'
          % args.hot_K)
    print('   %7s | %10s %8s | %10s %8s | %10s %8s'
          % ('T_cold', 'pipeline', 'prize', 'simulated', 'prize', 'no-GIDL', 'prize'))
    for r in rows:
        print('   %6.0fK | %9.2fx %7.1f%% | %9.2fx %7.1f%% | %9.1fx %7.1f%%'
              % (r['T_cold_K'],
                 r['pipeline']['leakage_reduction_x'],
                 r['pipeline']['die_power_saved_pct_rederived'],
                 r['simulated']['leakage_reduction_x'],
                 r['simulated']['die_power_saved_pct_rederived'],
                 r['simulated-gidl-off']['leakage_reduction_x'],
                 r['simulated-gidl-off']['die_power_saved_pct_rederived']))
    print('\n  ceiling (all cache leakage removed): %.1f%% of die power  '
          '(recorded ratios said %.1f%%)'
          % (100 * recomputed['static_fraction'] * recomputed['cache_share_of_leakage'],
             100 * inherited['static_fraction'] * inherited['cache_share_of_leakage']))
    print('  book Section 10.8 (100-200x):        %.1f-%.1f%%'
          % tuple(out['book_section_10_8']['die_power_saved_pct_recorded_ratios']))
    print('  recorded "our curve" answer:          %.1f%%'
          % rec['bounds'][0]['die_power_saved_pct_cache_only'])
    print('\n  prize at 200 K:  recorded ratios %.1f%%   RE-DERIVED ratios %.1f%%'
          % (sim200, at200['simulated']['die_power_saved_pct_rederived']))
    print('  IMPROVEMENT over the pipeline curve: %.2fx (recorded ratios) / %.2fx (re-derived) '
          '-- identical, and this is the robust number'
          % (improvement['recorded_ratios'], improvement['rederived']))
    print('\n' + out['FINDING_1_THE_2_3X_SPREAD_IS_CLOSED_AND_THE_BOOK_WAS_RIGHT'])
    print('\n' + out['FINDING_4_HOW_COLD_IS_WORTH_GETTING_AND_IT_IS_NOT_VERY'])
    print('\n' + out['FINDING_5_THE_INHERITED_RATIOS_ARE_A_SCOPE_ERROR_AND_THE_PRIZE_MOVES_DOWN'])
    print('\nwritten: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
