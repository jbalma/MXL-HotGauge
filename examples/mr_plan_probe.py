#!/usr/bin/env python
"""What is the MR plan actually sized from when the bare die has no steady state?

The suspicion
-------------
``run_mr_clipping`` sizes its whole plan from an UNCOOLED baseline solve::

    base_temps = thermal_solve_fn(trace)
    base_hot   = {blocks above target in base_temps}

That is sound when the baseline has a steady state. In the rescue regime it does not: the
baseline diverges, so ``base_temps`` is whichever field the iteration happened to be passing
through when a runaway guard fired. The plan -- and therefore whether MR "rescues" the die --
would then depend on where a divergent sequence was stopped, which is the same class of error
as the convergence bug in docs/CONVERGENCE.md, one level up.

The observation that motivates it: at a fixed 92 C target the rescue is NOT monotone in
density. 1.10 rescues, 1.12 does not, 1.15 rescues, 1.16 does not. Physics does not usually do
that; path-dependence does.

What this prints, per density
-----------------------------
* the peak of the baseline field the plan was sized from, and whether that baseline converged
* how many blocks were above target in it, and the total heat the plan asked for
* whether the cooled system then converged

If the baseline peak (and hence the plan size) jumps around between neighbouring densities,
the mechanism is confirmed and MR rescue results are not trustworthy until the plan is sized
from something that exists.
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
                                               load_calibrated_leakage_model,
                                               mcpat_flp_name_map, mcpat_tref_from_trace_dir,
                                               peak_temp_K)
from HotGauge.thermal.sink_models import (BaffledFinSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan, SIMSCALE_T0_K)
from HotGauge.thermal.sink_models import spreading_sink_for_stack
from HotGauge.thermal.die_stack import stack_for_spreading
from HotGauge.thermal.mr_array import wiring_for_stack, DEFAULT_PITCH_UM
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping,
                                                 DEFAULT_H_MAX_W_PER_MM2, DEFAULT_DT_MAX_K)
from HotGauge.thermal.ice_server import ICESessionCache
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--recovery-at-junction', action='store_true',
                    help='bound the LPC recovery by the Carnot factor of the junction the heat is '
                         'lifted from (v91 eq. 1.14-1.16). Without it the ledger uses the '
                         'phi -> 1 limit, which overstates recovery at every finite temperature')
    ap.add_argument('--T0-K', type=float, default=295.0,
                    help='sink temperature for the Carnot factor, with --recovery-at-junction')
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
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
    ap.add_argument('--pitch-um', type=float, default=DEFAULT_PITCH_UM,
                    help='cooling tile pitch; the array is a second powered die above the silicon')
    ap.add_argument('--no-array', action='store_true',
                    help='legacy placement: subtract the plan from the processor trace instead of putting it on the array. An upper bound, not the device -- see CoolingApplication')
    ap.add_argument('--cell-um', type=float, default=50.0,
                    help='3D-ICE grid cell; the tile grid SNAPS to it. Must match the cell= in '
                         'the stack spec: tiles snapped to a finer grid than the solver uses '
                         'come back overlapping after 3D-ICE quantises them, and the failure is '
                         'a wrong floorplan rather than an error')
    ap.add_argument('--densities', type=float, nargs='+',
                    default=[1.10, 1.12, 1.15, 1.16])
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    ap.add_argument('--mr-target-C', type=float, default=92.0)
    ap.add_argument('--mr-h-max', type=float, default=DEFAULT_H_MAX_W_PER_MM2)
    ap.add_argument('--mr-dt-max', type=float, default=DEFAULT_DT_MAX_K)
    ap.add_argument('--mr-iter', type=int, default=6)
    ap.add_argument('--spot-min-um', type=float, default=10.0)
    ap.add_argument('--spot-policy', default='dilute')
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--leakage-cal', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'mr_plan_probe'))
    os.makedirs(args.out_dir, exist_ok=True)

    stem = 'skylake{}_{}core_3_3D-ICE_template.flp'.format(args.node, args.cores)
    flp = os.path.join(args.flp_dir, stem)
    if not os.path.isfile(flp):
        flp = os.path.join(args.flp_dir, stem.replace('_3_', '_0_'))
    area_m2 = chip_area_m2_from_floorplan(flp)
    fp = Floorplan.from_file(flp)
    geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                     'min_dim_um': float(min(e.width, e.height))} for e in fp.elements}
    name_map = mcpat_flp_name_map(include_core_idx=(args.cores > 1))

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

    sink = BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K)
    stack_name = args.stack
    if args.spreading:
        stack_name = stack_for_spreading(stack_name)
        sink = spreading_sink_for_stack(stack_name, sink, area_m2 * 1e6,
                                        base_area_mm2=args.base_mm2)
    stack = render_stack_with_sink(get_stack_template(stack_name), sink,
                                   os.path.join(args.out_dir, 'probe.stk'))
    cache = ICESessionCache()
    mr = MRParams(target_K=args.mr_target_C + 273.15, h_max=args.mr_h_max,
                  dt_max_K=args.mr_dt_max, spot_min_um=args.spot_min_um,
                  spot_policy=args.spot_policy)

    print('MR plan provenance probe: {}-core {}, {:.0f} CFM, target {:.0f} C\n'.format(
        args.cores, args.node, args.cfm, args.mr_target_C))
    print('{:>8s} {:>10s} {:>12s} {:>9s} {:>10s} {:>12s} {:>10s}'.format(
        'density', 'baseline', 'base peak C', 'above tgt', 'plan W', 'MR result', 'MR peak C'))

    out = []
    for d in args.densities:
        power_W = d * area_m2 * 1e6
        trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                                   num_cores=args.cores)
        split = os.path.join(args.trace_dir, os.path.basename(files[0]).replace(
            'block_powers_', 'block_powers_split_'))
        leak_ref = {}
        if os.path.isfile(split):
            with open(split) as f:
                leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}

        counter = {'n': 0}
        seen = {'first': None}
        # The array as a second powered die; --no-array keeps the legacy in-source-layer bound.
        wiring = wiring_for_stack(stack, flp, os.path.join(args.out_dir, 'd{:g}'.format(d)),
                                  want_array=not args.no_array, pitch_um=args.pitch_um,
                                  cell_um=args.cell_um)

        def solver_factory(sub):
            return ICEThermalSolver(stack, flp, args.tech_node,
                                    run_base_dir=os.path.join(args.out_dir,
                                                              'd{:g}'.format(d), sub),
                                    initial_temp=args.ambient_K, num_cores=args.cores,
                                    single_thread=True, mode='steady', session_cache=cache,
                                    **(wiring.solver_kwargs() if wiring else {}))

        def solve(tr, _lr=leak_ref):
            counter['n'] += 1
            r = run_leakage_feedback(tr, _lr, solver_factory('it{:02d}'.format(counter['n'])),
                                     model=leak_model, T_ref=t_ref, num_cores=args.cores,
                                     tol_K=args.tol, max_iter=args.max_iter, relax=args.relax,
                                     t_floor_K=T_FLOOR_K, bridge_aggregates=True)
            solve.last = r
            # The FIRST call is the uncooled baseline the whole plan is sized from.
            if seen['first'] is None:
                seen['first'] = {'diverged': bool(r.get('diverged')),
                                 'unconverged': bool(r.get('unconverged')),
                                 'peak_K': peak_temp_K(r.get('temp_trace') or {}, T_FLOOR_K),
                                 'iterations': r.get('iterations')}
            return r['temp_trace']

        res = run_mr_clipping(trace, solve, geom, mr, name_map,
                              max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                              **(wiring.planner_kwargs() if wiring else {}),

            # `[!]` Carnot-bound the LPC recovery at the junction the

            # heat is lifted from (v91 eq. 1.14-1.16). Without it the

            # ledger uses the phi -> 1 limit and can report a loop that

            # generates net power, which the second law forbids.

            recovery_at_junction=args.recovery_at_junction,

            T_0_K=args.T0_K)
        first = seen['first'] or {}
        base_peak = first.get('peak_K')
        # How many blocks the plan was sized against, and how big it came out.
        above = sum(1 for t in (res.get('temp_trace') or {}).values()
                    if float(np.ravel(t)[-1]) > mr.target_K)
        plan_W = float(sum((res.get('plan') or {}).values()))
        last = getattr(solve, 'last', {}) or {}
        mr_div = bool(last.get('diverged'))
        mr_peak = peak_temp_K(last.get('temp_trace') or {}, T_FLOOR_K)
        row = {'density': d, 'baseline_diverged': first.get('diverged'),
               'baseline_peak_C': K_to_C(base_peak) if base_peak else None,
               'baseline_iterations': first.get('iterations'),
               'n_above_target_after': above, 'plan_W': plan_W,
               'mr_diverged': mr_div, 'mr_peak_C': K_to_C(mr_peak) if mr_peak else None,
               'mr_converged_flag': res.get('converged'), 'mr_reason': res.get('reason')}
        out.append(row)
        print('{:>8.3f} {:>10s} {:>12s} {:>9d} {:>10.3f} {:>12s} {:>10s}'.format(
            d, 'RUNAWAY' if first.get('diverged') else 'converged',
            '{:.1f}'.format(row['baseline_peak_C']) if row['baseline_peak_C'] else '--',
            above, plan_W, 'RUNAWAY' if mr_div else 'converged',
            '{:.1f}'.format(row['mr_peak_C']) if row['mr_peak_C'] else '--'))

    path = os.path.join(args.out_dir, 'mr_plan_probe.json')
    with open(path, 'w') as f:
        json.dump({'cores': args.cores, 'cfm': args.cfm, 'target_C': args.mr_target_C,
                   'rows': out}, f, indent=2)
    print('\n  written: {}'.format(path))
    print('  READ: if baseline peak (and plan W) jump between neighbouring densities, the plan '
          'is\n  being sized from an arbitrary point on a divergent trajectory.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
