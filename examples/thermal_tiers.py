#!/usr/bin/env python
"""Why does clipping the hotspot buy so little clock? Look at the top of the distribution.

The screening question
----------------------
MR lowers a block by at most ``dt_max`` (the DEMONSTRATED device capability, 45 K -- see
``microrefrigeration.DEMONSTRATED``; this file used to say "10 K on the current device roadmap",
which was the unsourced legacy envelope) and only touches
blocks above its target. The clock is set by the *peak* block. So cooling the peak does not buy
``dt_max`` of headroom -- it buys only as much as the gap to whatever block becomes the peak
next:

    achievable peak reduction (cooling the top N) = T[0] - max(T[0] - dt_max, T[N])

If the die's hottest block stands well clear of the rest, N=1 buys the full ``dt_max`` and MR is
a powerful clock enabler. If the top of the distribution is a dense plateau -- many blocks
within a few K -- then MR has to cool all of them, which is bulk cooling with a laser, and the
economics collapse. **That shape, not the peak temperature, decides whether MR can enable
clock**, and it is a property of the floorplan and workload rather than of the cooling.

This is the cheap screening tool for candidate core designs: one converged solve per design
instead of a full clock search, and it predicts the clock leverage before any sweep is run.

Reported per design
-------------------
* the top of the temperature distribution, block by block
* ``N_needed``: how many blocks must be clipped to realise the full ``dt_max`` of headroom
* the laser heat that costs, and the resulting peak-reduction-per-watt
* a plateau width: how many blocks sit within ``dt_max`` of the peak

Usage
-----
    python examples/thermal_tiers.py --cores 34 --density 1.07 --r-th 0.1
"""
import os
import sys
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace, LeakageModel
from HotGauge.configuration import load_block_powers
from HotGauge.thermal import get_stack_template, ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, replicate_trace_cores,
                                               load_calibrated_leakage_model, die_power_of_trace,
                                               mcpat_tref_from_trace_dir, peak_temp_K)
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink,
                                          chip_area_m2_from_floorplan, SIMSCALE_T0_K)
from HotGauge.thermal.sink_models import spreading_sink_for_stack
from HotGauge.thermal.die_stack import stack_for_spreading
from HotGauge.thermal.ice_server import ICESessionCache
from HotGauge.power.clock_search import (scale_cores, single_core_turbo,
                                         mixed_utilisation, emphasise_units)
from HotGauge.thermal.utils import K_to_C
from HotGauge.thermal.microrefrigeration import DEFAULT_DT_MAX_K
from HotGauge.thermal.floorplan_metrics import relative_plateau, peak_to_runner_up_gap

T_FLOOR_K = 200.0


def tier_analysis(temps_C, dt_max_K, top=25):
    """Rank blocks by temperature and work out what clipping the top N actually buys."""
    ranked = sorted(temps_C.items(), key=lambda kv: -kv[1])
    peak = ranked[0][1]
    floor_after_full_clip = peak - dt_max_K

    # How many blocks must be clipped before the (N+1)-th no longer sets the peak?
    n_needed = 1
    for i, (_, t) in enumerate(ranked):
        if t <= floor_after_full_clip:
            n_needed = i
            break
    else:
        n_needed = len(ranked)

    rows = []
    for n in range(1, min(top, len(ranked)) + 1):
        # Clip the top n blocks as far as the device allows; the new peak is whichever is hotter:
        # a clipped block at its floor, or the first un-clipped block.
        new_peak = max(floor_after_full_clip,
                       ranked[n][1] if n < len(ranked) else -np.inf)
        rows.append({'n_clipped': n, 'new_peak_C': new_peak, 'gain_K': peak - new_peak})
    return {'ranked': ranked, 'peak_C': peak, 'n_needed_for_full_dt_max': n_needed,
            'plateau_within_dt_max': sum(1 for _, t in ranked if t > floor_after_full_clip),
            'rows': rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--flp', default=None, help='explicit floorplan path (for design variants)')
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--spreading', action='store_true',
                    help='take the cold-plate slab OUT of the stack and fold it into the boundary '
                         'as a real overhanging base (P0.4). A slab in the stack is a column of '
                         'metal the width of the die, so the package budget comes out as 1/area '
                         '-- 15.5x across the die sizes here, against 2.6x with the overhang. '
                         'Amends the --stack spec with sink_in_stack=0. STRONGLY preferred for '
                         'anything quotable; off by default so results predating it reproduce.')
    ap.add_argument('--base-mm2', type=float, default=None,
                    help='cold-plate footprint [mm^2] for --spreading. Default: the socket '
                         'footprint (a fixed AREA, not a ratio of the die)')
    ap.add_argument('--stack', default='skylake')
    # 0.60 W/mm^2 is the tier-screen working point on the CORRECTED --spreading boundary
    # (scripts/array_config.sh, DENSITY_STACKED, which is the authority). Was a hardcoded 1.07,
    # chosen for the pre-correction boundary where the cliff sat at 1.05-1.15; on the current
    # boundary the cliff is 0.80-0.85 under grease, so 1.07 is past it and returns RUNAWAY.
    ap.add_argument('--density', type=float, default=0.60)
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, default=None)
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    ap.add_argument('--dt-max', type=float, default=DEFAULT_DT_MAX_K,
                    help='the most MR can pull a single block down [K] -- the device roadmap '
                         'parameter this whole analysis turns on. Defaults to the DEMONSTRATED '
                         'capability (microrefrigeration.DEFAULT_DT_MAX_K); it defaulted to a '
                         'hardcoded 10.0 until 27 Aug 2026, which was the unsourced legacy '
                         'envelope and a hidden ceiling on every plateau width this driver '
                         'reports. Plateau widths are NOT comparable across dt_max, so sweep it '
                         'rather than assuming it.')
    ap.add_argument('--top', type=int, default=25)
    # The degeneracy axis. Homogeneous activity is what makes the peak N-fold degenerate and
    # therefore what makes MR look weak; these let a design be screened against workloads that
    # break that symmetry. See docs/DESIGN_STUDY_PLAN.md.
    ap.add_argument('--activity', default='uniform',
                    choices=('uniform', 'turbo', 'mixed'),
                    help='per-core activity: uniform (every core saturated -- the current and '
                         'most hostile assumption), turbo (one core saturated), mixed')
    ap.add_argument('--hot-core', type=int, default=0)
    ap.add_argument('--background', type=float, default=0.25,
                    help='activity of the non-saturated cores')
    ap.add_argument('--active-fraction', type=float, default=0.5,
                    help='for --activity mixed')
    # How a non-uniform activity map is normalised, and it changes the question being asked:
    #
    #   iso-per-core (default) -- each core keeps the absolute power it had when saturated, so
    #     quiet cores simply dissipate less and TOTAL die power falls. This is what a real part
    #     does when it boosts one core and idles the rest, and it is the right comparison for
    #     an activity study.
    #   iso-density -- renormalise so die-average density is held at --density. Right for
    #     comparing FLOORPLANS at a fixed power budget, wrong for activity: concentrating the
    #     same total power into one core of 34 puts ~3.7x the average density on it and the die
    #     runs away, which says nothing about turbo and everything about the normalisation.
    # Design G: concentrate a core's power into one structure, at constant core power, to test
    # whether INTRA-core dominance breaks the plateau that activity maps cannot touch.
    ap.add_argument('--emphasise', default=None,
                    help="McPAT unit substring to concentrate a core's power into, e.g. "
                         "'Floating Point Units' (accelerator-style core)")
    ap.add_argument('--emphasis-factor', type=float, default=3.0,
                    help='multiplier on the emphasised units; the rest of the same core is '
                         'scaled down so core power is unchanged')
    ap.add_argument('--activity-scope', default='iso-per-core',
                    choices=('iso-per-core', 'iso-density'),
                    help='whether a quiet die keeps its per-core power (default) or is '
                         'renormalised back up to --density')
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--leakage-cal', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'thermal_tiers'))
    os.makedirs(args.out_dir, exist_ok=True)

    flp = args.flp
    if flp is None:
        stem = 'skylake{}_{}core_3_3D-ICE_template.flp'.format(args.node, args.cores)
        flp = os.path.join(args.flp_dir, stem)
        if not os.path.isfile(flp):
            flp = os.path.join(args.flp_dir, stem.replace('_3_', '_0_'))
    area_m2 = chip_area_m2_from_floorplan(flp)
    power_W = args.density * area_m2 * 1e6

    leak_model, t_ref = (load_calibrated_leakage_model(args.leakage_cal, extrapolate=True)
                         if os.path.isfile(args.leakage_cal)
                         else (LeakageModel.exponential(15.0),
                               mcpat_tref_from_trace_dir(args.trace_dir) or 330.0))

    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    base = (replicate_trace_cores(base0, args.cores, n_src=args.trace_cores)
            if args.cores > args.trace_cores else base0)
    # Emphasis is applied to the per-core mix BEFORE any activity map or normalisation, so it
    # composes with them and does not change core power on its own.
    if args.emphasise:
        base = emphasise_units(base, args.emphasise, args.emphasis_factor)

    activity_map = None
    if args.activity == 'turbo':
        activity_map = single_core_turbo(args.cores, args.hot_core, args.background)
    elif args.activity == 'mixed':
        activity_map = mixed_utilisation(args.cores, args.active_fraction, args.background)

    if activity_map is not None and args.activity_scope == 'iso-density':
        base = scale_cores(base, activity_map)
        trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                                   num_cores=args.cores)
    else:
        # iso-per-core: normalise the SATURATED die to --density first, then quiet the cores.
        # Die power ends up below the target, which is the point -- an idle core dissipates less.
        trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                                   num_cores=args.cores)
        if activity_map is not None:
            trace = scale_cores(trace, activity_map)
    actual_W = die_power_of_trace(trace, flp, args.tech_node, num_cores=args.cores)
    split = os.path.join(args.trace_dir, os.path.basename(files[0]).replace(
        'block_powers_', 'block_powers_split_'))
    leak_ref = {}
    if os.path.isfile(split):
        with open(split) as f:
            leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}

    sink = (ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K)
            if args.r_th is not None
            else BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K))
    stack_name = args.stack
    if args.spreading:
        stack_name = stack_for_spreading(stack_name)
        sink = spreading_sink_for_stack(stack_name, sink, area_m2 * 1e6,
                                        base_area_mm2=args.base_mm2)
    stack = render_stack_with_sink(get_stack_template(stack_name), sink,
                                   os.path.join(args.out_dir, 'tiers.stk'))
    solver = ICEThermalSolver(stack, flp, args.tech_node,
                              run_base_dir=os.path.join(args.out_dir, 'solve'),
                              initial_temp=args.ambient_K, num_cores=args.cores,
                              single_thread=True, mode='steady',
                              session_cache=ICESessionCache())

    res = run_leakage_feedback(trace, leak_ref, solver, model=leak_model, T_ref=t_ref,
                               num_cores=args.cores, tol_K=args.tol, max_iter=args.max_iter,
                               relax=args.relax, t_floor_K=T_FLOOR_K, bridge_aggregates=True)

    act = ('uniform (every core saturated)' if args.activity == 'uniform' else
           'turbo: core {} at 1.0, others {:.2f}'.format(args.hot_core, args.background)
           if args.activity == 'turbo' else
           'mixed: {:.0%} of cores at 1.0, others {:.2f}'.format(args.active_fraction,
                                                                 args.background))
    print('thermal tier structure: {}-core {}, {:.3f} W/mm^2 ({:.1f} W), {}'.format(
        args.cores, args.node, args.density, power_W,
        'R_th {:.3g} K/W'.format(args.r_th) if args.r_th is not None
        else '{:.0f} CFM'.format(args.cfm)))
    print('  activity : {}  [{}]'.format(act, args.activity_scope))
    if args.emphasise:
        print('  emphasis : {!r} x{:.2f} at constant core power'.format(
            args.emphasise, args.emphasis_factor))
    print('  actual   : {:.1f} W on the die ({:.3f} W/mm^2)'.format(
        actual_W, actual_W / (area_m2 * 1e6)))
    if res.get('diverged'):
        print('  NO STEADY STATE at this operating point -- pick a lower density')
        return 1
    if res.get('unconverged'):
        print('  ** UNCONVERGED (peak spread {:.2f} K) -- not a result **'.format(
            res.get('peak_spread_K') or float('nan')))
        return 1

    temps = {k: K_to_C(float(np.ravel(v)[-1])) for k, v in res['temp_trace'].items()
             if float(np.ravel(v)[-1]) > T_FLOOR_K and not k.startswith('__')}
    t = tier_analysis(temps, args.dt_max, top=args.top)

    print('  peak {:.2f} C on {}, dt_max {:.1f} K -> best possible peak {:.2f} C\n'.format(
        t['peak_C'], t['ranked'][0][0], args.dt_max, t['peak_C'] - args.dt_max))
    print('  {:>4s} {:<18s} {:>9s}   {:>10s} {:>9s}'.format(
        'rank', 'block', 'T [C]', 'if clipped', 'gain K'))
    for i, (name, temp) in enumerate(t['ranked'][:args.top]):
        row = t['rows'][i]
        print('  {:>4d} {:<18s} {:>9.2f}   {:>10.2f} {:>9.2f}'.format(
            i + 1, name, temp, row['new_peak_C'], row['gain_K']))

    print('\n  blocks within dt_max of the peak : {}'.format(t['plateau_within_dt_max']))
    print('  blocks that must be clipped to realise the full {:.0f} K : {}'.format(
        args.dt_max, t['n_needed_for_full_dt_max']))
    frac = t['rows'][0]['gain_K'] / args.dt_max if args.dt_max else 0.0
    print('  clipping ONE block realises {:.0f}% of the device capability ({:.2f} K of {:.1f})'
          .format(100.0 * frac, t['rows'][0]['gain_K'], args.dt_max))
    print('\n  READ: a small plateau means MR can enable clock; a wide one means MR would have '
          'to\n  act as a bulk cooler to move the peak, which the laser COP cannot pay for.')

    out = os.path.join(args.out_dir, 'tiers.json')
    with open(out, 'w') as f:
        json.dump({'cores': args.cores, 'node': args.node, 'density': args.density,
                   'power_W': power_W, 'r_th': args.r_th, 'cfm': args.cfm,
                   'activity': args.activity, 'activity_scope': args.activity_scope,
                   'emphasise': args.emphasise, 'emphasis_factor': args.emphasis_factor,
                   'actual_power_W': actual_W,
                   'actual_density_W_per_mm2': actual_W / (area_m2 * 1e6),
                   'hot_core': args.hot_core,
                   'background': args.background, 'active_fraction': args.active_fraction,
                   'dt_max_K': args.dt_max, 'floorplan': flp,
                   # Device-INDEPENDENT phase-1 metrics, emitted alongside the dt_max-based ones.
                   # 'plateau_within_dt_max' below saturates to the whole die once dt_max reaches
                   # the die's own temperature span -- which the DEMONSTRATED 45 K does -- so it
                   # carries no information at the real envelope. These two do not depend on any
                   # device parameter and cannot go stale under one.
                   # See HotGauge/thermal/floorplan_metrics.py and
                   # docs/evidence/tier_screens_dt_ladder.json.
                   'relative_plateau_25pct': relative_plateau(temps, 0.25),
                   'peak_to_runner_up_gap_K': peak_to_runner_up_gap(temps),
                   'peak_C': t['peak_C'], 'peak_block': t['ranked'][0][0],
                   'plateau_within_dt_max': t['plateau_within_dt_max'],
                   'n_needed_for_full_dt_max': t['n_needed_for_full_dt_max'],
                   'ranked': [{'block': n, 'T_C': v} for n, v in t['ranked']],
                   'clip_curve': t['rows']}, f, indent=2)
    print('\n  written: {}'.format(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
