#!/usr/bin/env python
"""Optimise the split of a cooling power budget between the fan and photonic MR.

The two questions
-----------------
**A. Maximum achievable performance** at a fixed cooling budget: given
``P_cool = P_fan + P_MR_net``, how should it be divided to maximise throughput? Spending on
the fan lowers the *whole die*; spending on MR lowers the *hottest block*, which is what
actually sets the clock. Neither is right on its own.

**B. Maximum compute efficiency** at a fixed performance target: what is the cheapest
``P_cool`` that still hits the target, and what split achieves it? Reported as
``GFLOP/s / (P_chip + P_cool)``, with the sub-metrics ``GFLOP/s / P_chip`` and
``GFLOP/s / P_cool`` broken out separately.

Why an interior optimum exists
------------------------------
Measured against the repaired HS483 FMU, the fan's marginal value collapses ~90x across its
range (-1.43 K/W for the first 1500 RPM, -0.016 K/W for the last). MR's cost is roughly linear
in the heat it removes. Diminishing returns on one lever and linear cost on the other is
exactly the shape that produces an interior optimum rather than a corner solution.

What is real and what is assumed
--------------------------------
* Fan R_th(u) and its power: **measured** (``HS483_FIT``, residuals <= 0.003 K/W).
* MR cost including LPC recovery: matches the Maxwell Labs power-analysis spreadsheet exactly.
* Leakage vs temperature: **measured** from McPAT, extrapolated above 400 K (uncertain there;
  used to decide *whether* a point diverges, not by how much).
* f_max(T) derating slope: **an assumption**. Performance numbers inherit that uncertainty --
  the *split* is far more robust than the absolute GFLOP/s.

Cost
----
Each evaluation is a steady 3D-ICE solve plus leakage feedback plus an MR clipping loop. Budget
minutes per point; the sweep is the expensive part, so start coarse.

Usage
-----
    python examples/hybrid_cooling_optimizer.py --power 26 --budget 2.0 --splits 5
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
                                               mcpat_flp_name_map, load_calibrated_leakage_model,
                                               mcpat_tref_from_trace_dir)
from HotGauge.thermal.sink_models import (PumpedSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan, HS483_FIT)
from HotGauge.thermal.sink_models import spreading_sink_for_stack
from HotGauge.thermal.die_stack import stack_for_spreading
from HotGauge.thermal.mr_array import wiring_for_stack, DEFAULT_PITCH_UM
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, mr_accounting,
                                                 DEFAULT_H_MAX_W_PER_MM2, DEFAULT_DT_MAX_K, DEFAULT_ETA_ASF, DEFAULT_LASER_WALLPLUG, DEFAULT_LPC_EFFICIENCY)
from HotGauge.power.performance_model import FMaxModel, performance_summary
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0
DEFAULT_FLOPS_PER_CYCLE = 32.0


def fan_setting_for_power(budget_W, area_m2, u_max=6.0, steps=2000):
    """Largest fan setting u whose electrical draw fits ``budget_W`` (0 if none does)."""
    if budget_W <= 0:
        return 0.0
    best = 0.0
    for i in range(1, steps + 1):
        u = u_max * i / steps
        s = PumpedSink(u, area_m2, R0=HS483_FIT['R0'], R_inf=HS483_FIT['R_inf'],
                       m=HS483_FIT['m'])
        if s.parasitic_power_W() <= budget_W:
            best = u
        else:
            break
    return best


def mr_heat_budget_for_power(net_budget_W, params):
    """Heat [W] MR can remove for ``net_budget_W`` of NET electrical draw.

    Inverts the accounting: net = (1 - breakeven_ratio) * Q / COP_elec. Above breakeven the
    loop is net-generating and any heat removal is affordable, so the budget stops binding.
    """
    if net_budget_W <= 0:
        return 0.0
    factor = (1.0 - params.breakeven_ratio) / params.cop
    if factor <= 0:
        return float('inf')      # self-sustaining or better: budget is not the constraint
    return net_budget_W / factor


def evaluate(args, trace, leak_ref, geom, name_map, leak_model, t_ref, fmax, area_m2,
             fan_W, mr_W, tag):
    """One (P_fan, P_MR) point: build the sink, solve, clip, and score it."""
    u = fan_setting_for_power(fan_W, area_m2)
    sink = PumpedSink(u, area_m2, R0=HS483_FIT['R0'], R_inf=HS483_FIT['R_inf'],
                      m=HS483_FIT['m'], ambient_K=args.ambient_K, calibrated=True)
    actual_fan_W = sink.parasitic_power_W()
    stack_name = args.stack
    if args.spreading:
        stack_name = stack_for_spreading(stack_name)
        sink = spreading_sink_for_stack(stack_name, sink, area_m2 * 1e6,
                                        base_area_mm2=args.base_mm2)
    stack = render_stack_with_sink(get_stack_template(stack_name), sink,
                                   os.path.join(args.out_dir, 'stacks', tag + '.stk'))

    # The array as a second powered die; --no-array keeps the legacy in-source-layer upper bound.
    wiring = wiring_for_stack(stack, args.flp_template, os.path.join(args.out_dir, tag),
                              want_array=not args.no_array, pitch_um=args.pitch_um,
                              cell_um=args.cell_um)

    def solver_factory(sub):
        return ICEThermalSolver(stack, args.flp_template, args.tech_node,
                                run_base_dir=os.path.join(args.out_dir, tag, sub),
                                initial_temp=args.ambient_K, num_cores=args.num_cores,
                                single_thread=True, mode='steady',
                                **(wiring.solver_kwargs() if wiring else {}))

    counter = {'n': 0}

    def solve_with_leakage(tr):
        counter['n'] += 1
        r = run_leakage_feedback(tr, leak_ref, solver_factory('it{:02d}'.format(counter['n'])),
                                 model=leak_model, T_ref=t_ref, num_cores=args.num_cores,
                                 tol_K=args.tol, max_iter=args.max_iter, relax=0.5,
                                 t_floor_K=T_FLOOR_K, bridge_aggregates=True)
        solve_with_leakage.last = r
        return r['temp_trace']

    mr = MRParams(target_K=args.mr_target_C + 273.15, h_max=args.mr_h_max,
                  dt_max_K=args.mr_dt_max, eta_asf=args.eta_asf,
                  laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                  max_total_W=(mr_W if np.isfinite(mr_W) and mr_W > 0 else None))

    if mr_W > 0:
        res = run_mr_clipping(trace, solve_with_leakage, geom, mr, name_map,
                              max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                              **(wiring.planner_kwargs() if wiring else {}),
            # `[!]` Carnot-bound the LPC recovery at the junction the
            # heat is lifted from (v91 eq. 1.14-1.16). Without it the
            # ledger uses the phi -> 1 limit and can report a loop that
            # generates net power, which the second law forbids.
            recovery_at_junction=args.recovery_at_junction,
            T_0_K=args.T0_K)
        temps, acc = res['temp_trace'], res['accounting']
    else:
        temps = solve_with_leakage(trace)
        acc = mr_accounting({}, mr)

    last = getattr(solve_with_leakage, 'last', None)
    diverged = bool(last.get('diverged')) if last else True
    if diverged:
        return {'tag': tag, 'fan_W': actual_fan_W, 'u': u, 'mr_budget_W': mr_W,
                'diverged': True, 'r_th': sink.thermal_resistance()}

    p_chip = die_power_of_trace(last['power_trace'], args.flp_template, args.tech_node,
                                num_cores=args.num_cores)
    p_mr_net = acc['electrical_power_W']
    p_cool = actual_fan_W + p_mr_net
    perf = performance_summary([np.ravel(v)[-1] for v in temps.values()], fmax,
                               f_nominal_GHz=args.f_nominal, compute_power_W=p_chip,
                               cooling_power_W=p_cool,
                               throttle_K=args.throttle_C + 273.15, t_floor_K=T_FLOOR_K)
    g = perf['f_effective_GHz'] * args.flops_per_cycle * args.num_cores
    return {'tag': tag, 'u': u, 'fan_W': actual_fan_W, 'mr_budget_W': mr_W,
            'r_th': sink.thermal_resistance(), 'heat_removed_W': acc['heat_removed_W'],
            'p_mr_net_W': p_mr_net, 'p_cool_W': p_cool, 'p_chip_W': p_chip,
            'p_total_W': p_chip + p_cool, 'peak_C': K_to_C(max(
                float(np.ravel(v)[-1]) for v in temps.values()
                if float(np.ravel(v)[-1]) > T_FLOOR_K)),
            'f_GHz': perf['f_effective_GHz'], 'throttling': perf['throttling'],
            'gflops': g, 'gflops_per_total_W': g / (p_chip + p_cool),
            'gflops_per_chip_W': g / p_chip,
            'gflops_per_cool_W': (g / p_cool) if p_cool > 0 else float('inf'),
            'diverged': False}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--recovery-at-junction', action='store_true',
                    help='bound the LPC recovery by the Carnot factor of the junction the heat is '
                         'lifted from (v91 eq. 1.14-1.16). Without it the ledger uses the '
                         'phi -> 1 limit, which overstates recovery at every finite temperature')
    ap.add_argument('--T0-K', type=float, default=295.0,
                    help='sink temperature for the Carnot factor, with --recovery-at-junction')
    ap.add_argument('--trace-dir', default='mcpat_runs/7nm/linpack_3.8GHz')
    ap.add_argument('--flp-template', default=os.path.join(
        _HERE, 'floorplans', 'outputs', 'skylake7nm_8core_3_3D-ICE_template.flp'))
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--num-cores', type=int, default=8)
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
    ap.add_argument('--power', type=float, default=26.0, help='die power [W]')
    ap.add_argument('--budget', type=float, default=2.0, help='total cooling budget [W]')
    ap.add_argument('--splits', type=int, default=5, help='split points across the budget')
    ap.add_argument('--ambient-K', type=float, default=303.15)
    ap.add_argument('--leakage-cal', default='leakage_calibration/leakage_calibration.json')
    ap.add_argument('--mr-target-C', type=float, default=92.0)
    ap.add_argument('--eta-asf', type=float, default=DEFAULT_ETA_ASF)
    ap.add_argument('--eta-laser', type=float, default=DEFAULT_LASER_WALLPLUG)
    ap.add_argument('--eta-lpc', type=float, default=DEFAULT_LPC_EFFICIENCY)
    ap.add_argument('--mr-h-max', type=float, default=DEFAULT_H_MAX_W_PER_MM2)
    ap.add_argument('--mr-dt-max', type=float, default=DEFAULT_DT_MAX_K)
    ap.add_argument('--mr-iter', type=int, default=6)
    ap.add_argument('--f-nominal', type=float, default=4.0)
    ap.add_argument('--derate-per-K', type=float, default=0.001)
    ap.add_argument('--throttle-C', type=float, default=100.0)
    ap.add_argument('--flops-per-cycle', type=float, default=DEFAULT_FLOPS_PER_CYCLE)
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=12)
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()

    args.out_dir = args.out_dir or os.path.join(
        os.getcwd(), 'hybrid_opt', 'P{:g}_B{:g}'.format(args.power, args.budget))
    os.makedirs(args.out_dir, exist_ok=True)

    area_m2 = chip_area_m2_from_floorplan(args.flp_template)
    flp = Floorplan.from_file(args.flp_template)
    geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                     'min_dim_um': float(min(e.width, e.height))} for e in flp.elements}
    name_map = mcpat_flp_name_map(include_core_idx=(args.num_cores > 1))

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
    base = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    trace, scale, _ = scale_trace_to_die_power(base, args.flp_template, args.tech_node,
                                               args.power, num_cores=args.num_cores)
    split = os.path.join(args.trace_dir,
                         os.path.basename(files[0]).replace('block_powers_',
                                                            'block_powers_split_'))
    leak_ref = {}
    if os.path.isfile(split):
        with open(split) as f:
            leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}

    probe = MRParams(target_K=args.mr_target_C + 273.15, eta_asf=args.eta_asf,
                     laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc)
    print('hybrid cooling optimiser')
    print('  die {:.1f} W on {}  ({:.2f} mm^2, {} cores)'.format(
        args.power, os.path.basename(args.flp_template), area_m2 * 1e6, args.num_cores))
    print('  cooling budget {:.2f} W split {} ways'.format(args.budget, args.splits))
    print('  leakage : {}'.format(leak_src))
    print('  fan     : CALIBRATED HS483 fit (R0={R0}, R_inf={R_inf}, m={m:.4f})'.format(**HS483_FIT))
    print('  MR      : COP_elec {:.3f}, breakeven ratio {:.3f}'.format(
        probe.cop, probe.breakeven_ratio))
    print('  perf    : f_max derate {:.4g}/K  [UNCALIBRATED -- absolute GFLOP/s inherit this]'
          .format(args.derate_per_K))
    print()
    print('  *** The fan THERMAL model R_ext(u) is calibrated against the FMU, but the fan')
    print('  *** POWER model (p_static/p_scale/n/r) is still PLACEHOLDER. The optimal split')
    print('  *** depends directly on what a watt of fan buys, so the SPLIT below is')
    print('  *** provisional until real fan curves (W vs RPM/CFM) replace those constants.')
    print('  *** The qualitative shape -- diminishing fan returns vs linear MR cost -- holds')
    print('  *** regardless; the exact crossover does not.\n')

    hdr = ('{:>7s} {:>7s} {:>8s} {:>8s} {:>8s} {:>8s} {:>7s} {:>9s} {:>10s} {:>10s}'.format(
        'P_fan', 'P_MR', 'R_th', 'Q_rem', 'peak C', 'P_tot', 'f GHz', 'GFLOP/s',
        'per totW', 'per coolW'))
    print(hdr); print('-' * len(hdr))

    rows = []
    for i in range(args.splits + 1):
        frac = i / float(args.splits)
        fan_W = args.budget * (1.0 - frac)
        mr_net_W = args.budget * frac
        mr_W = mr_heat_budget_for_power(mr_net_W, probe)
        r = evaluate(args, trace, leak_ref, geom, name_map, leak_model, t_ref, fmax, area_m2,
                     fan_W, mr_W, 'f{:02d}'.format(i))
        rows.append(r)
        if r['diverged']:
            print('{:>7.2f} {:>7.2f} {:>8.4f} {:>8s} {:>8s} {:>8s} {:>7s} {:>9s} {:>10s} {:>10s}'
                  .format(r['fan_W'], mr_net_W, r['r_th'], '--', '--', '--', '--', '--',
                          '--', '--') + '  DIVERGED')
        else:
            print('{:>7.2f} {:>7.2f} {:>8.4f} {:>8.3f} {:>8.2f} {:>8.2f} {:>7.3f} {:>9.1f} '
                  '{:>10.4f} {:>10.2f}{}'.format(
                      r['fan_W'], r['p_mr_net_W'], r['r_th'], r['heat_removed_W'],
                      r['peak_C'], r['p_total_W'], r['f_GHz'], r['gflops'],
                      r['gflops_per_total_W'], r['gflops_per_cool_W'],
                      '  THROTTLED' if r['throttling'] else ''))

    ok = [r for r in rows if not r['diverged']]
    print()
    if ok:
        bp = max(ok, key=lambda r: r['gflops'])
        be = max(ok, key=lambda r: r['gflops_per_total_W'])
        print('  A. MAX PERFORMANCE   : P_fan {:.2f} W : P_MR {:.2f} W  -> {:.1f} GFLOP/s '
              '({:.3f} GHz, peak {:.1f} C)'.format(bp['fan_W'], bp['p_mr_net_W'],
                                                   bp['gflops'], bp['f_GHz'], bp['peak_C']))
        print('  B. MAX EFFICIENCY    : P_fan {:.2f} W : P_MR {:.2f} W  -> {:.4f} GFLOP/s/W '
              'total  ({:.4f} per chip W, {:.2f} per cool W)'.format(
                  be['fan_W'], be['p_mr_net_W'], be['gflops_per_total_W'],
                  be['gflops_per_chip_W'], be['gflops_per_cool_W']))
        if bp['tag'] != be['tag']:
            print('  -> the two objectives choose DIFFERENT splits: maximum throughput is not '
                  'the most efficient point.')
        else:
            print('  -> both objectives choose the same split at this budget.')
    else:
        print('  every split diverged at {:.1f} W -- the budget cannot hold this die.'.format(
            args.power))

    out = os.path.join(args.out_dir, 'sweep.json')
    with open(out, 'w') as f:
        json.dump({'power_W': args.power, 'budget_W': args.budget, 'rows': rows}, f, indent=2)
    print('\n  written: {}'.format(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
