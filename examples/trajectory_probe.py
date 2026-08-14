#!/usr/bin/env python
"""Is this operating point converging, or just being truncated? Print the trajectory.

The two look identical from the outside. A leakage fixed point that is slowly ratcheting
upward produces small differences between successive solves -- exactly what the old
convergence test measured -- and the test passes while the answer is still climbing. The
distinction only shows up in the *shape* of the iteration, which is what this prints:

* residual (|T_solved - T_driving|): the true distance from the fixed point. Falls
  geometrically for a convergent point; grows for a runaway.
* peak block temperature per iteration: flattens for a convergent point; climbs for a runaway.

Run with a fixed, undamped-adaptive setup so the trajectory is the raw iteration, not the
backtracking search:

    python examples/trajectory_probe.py --cores 34 --density 1.15 --cfm 88 --max-iter 200
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
from HotGauge.thermal import get_stack_template, ICEThermalSolver
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, replicate_trace_cores,
                                               load_calibrated_leakage_model,
                                               mcpat_tref_from_trace_dir,
                                               aggregate_aware_name_map,
                                               augment_temps_with_aggregates)
from HotGauge.power.leakage import converge_power_temperature
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink,
                                          chip_area_m2_from_floorplan, SIMSCALE_T0_K)
from HotGauge.thermal.ice_server import ICESessionCache

T_FLOOR_K = 200.0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--density', type=float, default=1.15)
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, default=None)
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    ap.add_argument('--relax', type=float, nargs='+', default=[0.1],
                    help='one trajectory per damping value')
    ap.add_argument('--max-iter', type=int, default=200)
    ap.add_argument('--tol', type=float, default=0.05)
    ap.add_argument('--adaptive', action='store_true',
                    help='allow the backtracking scheme (default: raw fixed-damping iteration)')
    ap.add_argument('--leakage-cal', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'trajectory'))
    os.makedirs(args.out_dir, exist_ok=True)

    stem = 'skylake{}_{}core_3_3D-ICE_template.flp'.format(args.node, args.cores)
    flp = os.path.join(args.flp_dir, stem)
    if not os.path.isfile(flp):
        flp = os.path.join(args.flp_dir, stem.replace('_3_', '_0_'))
    area_m2 = chip_area_m2_from_floorplan(flp)
    power_W = args.density * area_m2 * 1e6

    leak_model, t_ref = load_calibrated_leakage_model(args.leakage_cal, extrapolate=True) \
        if os.path.isfile(args.leakage_cal) else (LeakageModel.exponential(15.0),
                                                  mcpat_tref_from_trace_dir(args.trace_dir) or 330.0)

    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    base = (replicate_trace_cores(base0, args.cores, n_src=args.trace_cores)
            if args.cores > args.trace_cores else base0)
    trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                               num_cores=args.cores)
    split = os.path.join(args.trace_dir, os.path.basename(files[0]).replace(
        'block_powers_', 'block_powers_split_'))
    leak_ref = {}
    if os.path.isfile(split):
        with open(split) as f:
            leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}

    sink = (ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K)
            if args.r_th is not None
            else BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K))
    stack = render_stack_with_sink(get_stack_template(args.stack), sink,
                                   os.path.join(args.out_dir, 'probe.stk'))
    cache = ICESessionCache()
    name_map = aggregate_aware_name_map(include_core_idx=(args.cores > 1),
                                        num_cores=args.cores)

    print('trajectory probe: {}-core {} at {:.3f} W/mm^2 ({:.1f} W), {}'.format(
        args.cores, args.node, args.density, power_W,
        'R_th {:.3g} K/W'.format(args.r_th) if args.r_th is not None
        else '{:.0f} CFM'.format(args.cfm)))
    print('  {} iteration, tol {:.3g} K on the fixed-point residual\n'.format(
        'ADAPTIVE (backtracking)' if args.adaptive else 'raw fixed-damping', args.tol))

    out = {}
    for relax in args.relax:
        solver = ICEThermalSolver(stack, flp, args.tech_node,
                                  run_base_dir=os.path.join(args.out_dir,
                                                            'r{:g}'.format(relax)),
                                  initial_temp=args.ambient_K, num_cores=args.cores,
                                  single_thread=True, mode='steady', session_cache=cache)

        def solve(tr, _s=solver):
            return augment_temps_with_aggregates(_s(tr), num_cores=args.cores)

        res = converge_power_temperature(trace, leak_ref, solve, leak_model, T_ref=t_ref,
                                         name_map=name_map, tol_K=args.tol,
                                         max_iter=args.max_iter, relax=relax,
                                         adaptive_relax=args.adaptive, t_floor_K=T_FLOOR_K,
                                         max_temp_K=1000.0, max_power_growth=10.0)
        print('relax = {:g}: {} after {} iterations{}'.format(
            relax,
            'CONVERGED' if res['converged'] else
            ('DIVERGED ({})'.format(res['diverged_reason']) if res['diverged']
             else 'hit max_iter'),
            res['iterations'],
            '' if res['relax_final'] == relax else
            ' (damping tightened to {:g})'.format(res['relax_final'])))
        print('  {:>5s} {:>10s} {:>12s} {:>12s} {:>10s}'.format(
            'iter', 'peak C', 'residual K', 'delta K', 'P_die W'))
        hist = res['history']
        show = hist if len(hist) <= 40 else (hist[:12] + [None] + hist[-12:])
        for h in show:
            if h is None:
                print('  {:>5s} {:>10s} {:>12s} {:>12s} {:>10s}'.format(
                    '...', '...', '...', '...', '...'))
                continue
            print('  {:>5d} {:>10.2f} {:>12.4f} {:>12.4f} {:>10.2f}'.format(
                h['iter'], h['max_T_K'] - 273.15, h['residual_K'], h['max_delta_K'],
                h['total_W']))
        # The tell: is the peak still climbing when the OLD test would have stopped?
        peaks = [h['max_T_K'] - 273.15 for h in hist]
        deltas = [h['max_delta_K'] for h in hist]
        old_stop = next((i for i, d in enumerate(deltas) if i > 0 and d <= 0.5), None)
        if old_stop is not None:
            print('  the old criterion (successive dT <= 0.5 K) would have stopped at '
                  'iteration {} and reported {:.2f} C'.format(old_stop, peaks[old_stop]))
            print('  the trajectory continued to {:.2f} C by iteration {}'.format(
                peaks[-1], hist[-1]['iter']))
        out['relax_{:g}'.format(relax)] = {
            'converged': res['converged'], 'diverged': res['diverged'],
            'diverged_reason': res['diverged_reason'], 'iterations': res['iterations'],
            'peaks_C': peaks, 'residual_K': [h['residual_K'] for h in hist],
            'delta_K': deltas, 'total_W': [h['total_W'] for h in hist],
            'old_criterion_stop_iter': old_stop,
            'old_criterion_peak_C': peaks[old_stop] if old_stop is not None else None}
        print()

    path = os.path.join(args.out_dir, 'trajectory.json')
    with open(path, 'w') as f:
        json.dump({'density': args.density, 'cores': args.cores, 'power_W': power_W,
                   'cfm': args.cfm, 'r_th': args.r_th, 'runs': out}, f, indent=2)
    print('  written: {}'.format(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
