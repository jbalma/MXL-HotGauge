#!/usr/bin/env python
"""MR vs no-MR on each generated floorplan, at matched power density.

Why matched density rather than matched power
---------------------------------------------
Die-average power density is the quantity that determines whether a die is thermally
comfortable; total watts is not. Running 34-, 70- and 128-core dies all at 200 W would compare
2.0 W/mm^2 against 0.58 W/mm^2 and tell us mostly about die area. Holding density fixed asks
the question that matters: **does photonic MR help more or less as you scale core count at
constant density?**

What MR can actually reach
--------------------------
The two hottest units on these floorplans are not targetable: ``RBB`` is 142 x 13.4 um and
``iBuf`` 1.3 um across, both far below the 100 um minimum spot. The hottest reachable unit is
``cALU`` at ~15.6 W/mm^2. That is a real constraint, not a modelling convenience -- an optical
spot cannot be focused onto a 13 um sliver -- and it is why the comparison reports both the peak
block and whether MR was allowed to touch it.

Reported per floorplan
----------------------
Peak temperature, converged die power, clock, throughput, and the cooling power each option
costs. ``dT`` and ``d perf`` are the MR deltas, which is the number the whole exercise is for.

Usage
-----
    python examples/mr_comparison.py --cores 34 70 128 --density 0.575 --cfm 88
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
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, die_power_of_trace,
                                               mcpat_flp_name_map, replicate_trace_cores,
                                               load_calibrated_leakage_model,
                                               mcpat_tref_from_trace_dir)
from HotGauge.thermal.sink_models import (BaffledFinSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan, simscale_fan_power,
                                          SIMSCALE_T0_K)
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, mr_accounting,
                                                 DEFAULT_SPOT_MIN_UM)
from HotGauge.power.performance_model import FMaxModel, performance_summary
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0
DEFAULT_FLOPS_PER_CYCLE = 32.0


def floorplan_path(flp_dir, node, n):
    stem = 'skylake{}_{}core_3_3D-ICE_template.flp'.format(node, n)
    p = os.path.join(flp_dir, stem)
    if os.path.isfile(p):
        return p
    return os.path.join(flp_dir, stem.replace('_3_', '_0_'))


def evaluate(args, flp, trace, leak_ref, geom, name_map, leak_model, t_ref, fmax,
             area_m2, n_cores, use_mr, tag):
    """One (floorplan, MR on/off) point."""
    sink = BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K)
    stack = render_stack_with_sink(get_stack_template(args.stack), sink,
                                   os.path.join(args.out_dir, 'stacks', tag + '.stk'))
    counter = {'n': 0}

    def solver_factory(sub):
        return ICEThermalSolver(stack, flp, args.tech_node,
                                run_base_dir=os.path.join(args.out_dir, tag, sub),
                                initial_temp=args.ambient_K, num_cores=n_cores,
                                single_thread=True, mode='steady')

    def solve_with_leakage(tr):
        counter['n'] += 1
        r = run_leakage_feedback(tr, leak_ref, solver_factory('it{:02d}'.format(counter['n'])),
                                 model=leak_model, T_ref=t_ref, num_cores=n_cores,
                                 tol_K=args.tol, max_iter=args.max_iter, relax=0.5,
                                 t_floor_K=T_FLOOR_K, bridge_aggregates=True)
        solve_with_leakage.last = r
        return r['temp_trace']

    mr = MRParams(target_K=args.mr_target_C + 273.15, h_max=args.mr_h_max,
                  dt_max_K=args.mr_dt_max, eta_asf=args.eta_asf,
                  laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                  spot_min_um=args.spot_min_um)

    if use_mr:
        res = run_mr_clipping(trace, solve_with_leakage, geom, mr, name_map,
                              max_iter=args.mr_iter, tol_K=2.0, relax=0.7)
        temps, acc = res['temp_trace'], res['accounting']
    else:
        temps = solve_with_leakage(trace)
        acc = mr_accounting({}, mr)

    last = getattr(solve_with_leakage, 'last', None)
    row = {'tag': tag, 'cores': n_cores, 'mr': use_mr, 'fan_W': sink.parasitic_power_W()}
    if last is None or last.get('diverged'):
        row['diverged'] = True
        return row

    finals = {k: float(np.ravel(v)[-1]) for k, v in temps.items()}
    hot_name, hot_K = None, -np.inf
    for k, v in finals.items():
        if v > T_FLOOR_K and v > hot_K:
            hot_name, hot_K = k, v
    p_chip = die_power_of_trace(last['power_trace'], flp, args.tech_node, num_cores=n_cores)
    p_mr_net = acc['electrical_power_W']
    p_cool = sink.parasitic_power_W() + p_mr_net
    perf = performance_summary(list(finals.values()), fmax, f_nominal_GHz=args.f_nominal,
                               compute_power_W=p_chip, cooling_power_W=p_cool,
                               throttle_K=args.throttle_C + 273.15, t_floor_K=T_FLOOR_K)
    g = perf['f_effective_GHz'] * args.flops_per_cycle * n_cores
    row.update({'diverged': False, 'peak_C': K_to_C(hot_K), 'peak_block': hot_name,
                'p_chip_W': p_chip, 'heat_removed_W': acc['heat_removed_W'],
                'p_mr_net_W': p_mr_net, 'p_cool_W': p_cool, 'p_total_W': p_chip + p_cool,
                'f_GHz': perf['f_effective_GHz'], 'throttling': perf['throttling'],
                'gflops': g, 'gflops_per_total_W': g / (p_chip + p_cool),
                'n_targets': acc.get('n_blocks_cooled', 0),
                'effective_cop': acc.get('effective_cop'),
                'net_generating': acc.get('net_generating')})
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, nargs='+', default=[34, 70, 128])
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--density', type=float, default=0.575,
                    help='die-average power density [W/mm^2] held fixed across floorplans')
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    ap.add_argument('--leakage-cal', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--mr-target-C', type=float, default=92.0)
    ap.add_argument('--eta-asf', type=float, default=0.20)
    ap.add_argument('--eta-laser', type=float, default=0.70)
    ap.add_argument('--eta-lpc', type=float, default=0.90)
    ap.add_argument('--mr-h-max', type=float, default=10.0)
    ap.add_argument('--mr-dt-max', type=float, default=10.0)
    ap.add_argument('--mr-iter', type=int, default=6)
    ap.add_argument('--spot-min-um', type=float, default=DEFAULT_SPOT_MIN_UM)
    ap.add_argument('--f-nominal', type=float, default=4.0)
    ap.add_argument('--derate-per-K', type=float, default=0.001)
    ap.add_argument('--throttle-C', type=float, default=100.0)
    ap.add_argument('--flops-per-cycle', type=float, default=DEFAULT_FLOPS_PER_CYCLE)
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=12)
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'mr_compare'))
    os.makedirs(args.out_dir, exist_ok=True)

    if os.path.isfile(args.leakage_cal):
        leak_model, t_ref = load_calibrated_leakage_model(args.leakage_cal, extrapolate=True)
        leak_src = 'MEASURED McPAT curve + Arrhenius tail above 400 K'
    else:
        leak_model = LeakageModel.exponential(15.0)
        t_ref = mcpat_tref_from_trace_dir(args.trace_dir) or 330.0
        leak_src = 'assumed exponential'
    fmax = FMaxModel.linear_derate(args.derate_per_K)

    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    split = os.path.join(args.trace_dir,
                         os.path.basename(files[0]).replace('block_powers_',
                                                            'block_powers_split_'))

    print('MR vs no-MR at matched density')
    print('  density  : {:.3f} W/mm^2 held fixed'.format(args.density))
    print('  airflow  : {:.0f} CFM  (fan {:.1f} W)'.format(args.cfm, simscale_fan_power(args.cfm)))
    print('  leakage  : {}'.format(leak_src))
    print('  MR       : eta_asf {:.2f}, laser {:.2f}, LPC {:.2f}, spot >= {:.0f} um'.format(
        args.eta_asf, args.eta_laser, args.eta_lpc, args.spot_min_um))
    print()
    hdr = ('{:>6s} {:>8s} {:>7s} {:>4s} {:>8s} {:>8s} {:>8s} {:>7s} {:>10s} {:>9s}'.format(
        'cores', 'area', 'P_die', 'MR', 'peak C', 'Q_rem', 'P_cool', 'f GHz', 'GFLOP/s',
        'per totW'))
    print(hdr)
    print('-' * len(hdr))

    rows = []
    for n in args.cores:
        flp = floorplan_path(args.flp_dir, args.node, n)
        if not os.path.isfile(flp):
            print('  skip {}-core: no floorplan'.format(n))
            continue
        area_m2 = chip_area_m2_from_floorplan(flp)
        power_W = args.density * area_m2 * 1e6

        base = replicate_trace_cores(base0, n, n_src=args.trace_cores) \
            if n > args.trace_cores else base0
        trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                                   num_cores=n)
        leak_ref = {}
        if os.path.isfile(split):
            with open(split) as f:
                leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}

        fp = Floorplan.from_file(flp)
        geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                         'min_dim_um': float(min(e.width, e.height))} for e in fp.elements}
        name_map = mcpat_flp_name_map(include_core_idx=(n > 1))

        pair = {}
        for use_mr in (False, True):
            tag = '{}c_{}'.format(n, 'mr' if use_mr else 'nomr')
            r = evaluate(args, flp, trace, leak_ref, geom, name_map, leak_model, t_ref, fmax,
                         area_m2, n, use_mr, tag)
            r.update({'area_mm2': area_m2 * 1e6, 'power_W': power_W})
            rows.append(r)
            pair['mr' if use_mr else 'nomr'] = r
            if r['diverged']:
                print('{:>6d} {:>8.1f} {:>7.1f} {:>4s} {:>8s} {:>8s} {:>8s} {:>7s} {:>10s} '
                      '{:>9s}  RUNAWAY'.format(n, area_m2 * 1e6, power_W,
                                               'yes' if use_mr else 'no',
                                               '--', '--', '--', '--', '--', '--'))
            else:
                print('{:>6d} {:>8.1f} {:>7.1f} {:>4s} {:>8.1f} {:>8.3f} {:>8.2f} {:>7.3f} '
                      '{:>10.1f} {:>9.3f}{}'.format(
                          n, area_m2 * 1e6, power_W, 'yes' if use_mr else 'no',
                          r['peak_C'], r['heat_removed_W'], r['p_cool_W'], r['f_GHz'],
                          r['gflops'], r['gflops_per_total_W'],
                          '  THROTTLED' if r['throttling'] else ''))
        a, b = pair.get('nomr'), pair.get('mr')
        if a and b and not a['diverged'] and not b['diverged']:
            print('       -> MR delta: {:+.1f} K, {:+.1f}% throughput, {:+.2f} W cooling, '
                  'peak block {} -> {}'.format(
                      b['peak_C'] - a['peak_C'],
                      100.0 * (b['gflops'] / a['gflops'] - 1.0),
                      b['p_cool_W'] - a['p_cool_W'], a['peak_block'], b['peak_block']))
        elif a and b and a['diverged'] and not b['diverged']:
            print('       -> MR RESCUES a die with no steady state: {:.1f} C, {:.1f} GFLOP/s'
                  .format(b['peak_C'], b['gflops']))
        print()

    with open(os.path.join(args.out_dir, 'mr_comparison.json'), 'w') as f:
        json.dump({'density': args.density, 'cfm': args.cfm, 'rows': rows}, f, indent=2)
    print('  written: {}'.format(os.path.join(args.out_dir, 'mr_comparison.json')))


if __name__ == '__main__':
    main()
