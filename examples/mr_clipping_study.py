#!/usr/bin/env python
"""Does photonic microrefrigeration pay for itself? Baseline vs MR-clipped, same workload.

The question
------------
Bulk cooling is a weak lever on this die: going from 1.0 to 0.05 K/W (20x better) moved the
thermal-viability cliff only from ~40 W to ~55 W, because die-average thermal resistance barely
touches the local spreading resistance that sets hotspot temperature (peak local flux is
512 W/mm^2 at ``RBB_0``, 97x the die average). MR attacks that directly.

This script runs the same workload twice through the same steady 3D-ICE + leakage-feedback
pipeline -- once untouched, once with MR clipping hot blocks to a target -- and reports the
full chain: temperature, power, frequency, throughput, and MR's own electrical cost.

Reading the result honestly
---------------------------
MR is charged its real cost: ``P_electrical = Q_removed / COP``. At the working assumption of
20 % efficiency (COP 0.2) that is 5 W electrical per watt of heat removed -- so MR has to buy
a real frequency step to be worth anything. The comparison that matters is therefore
**performance per total watt**, with
MR's draw included -- not peak temperature, and not compute power alone. A row where MR lowers
temperature but loses on GFLOPs/W is MR failing at that operating point, and it is reported
as such.

FLOPs are ``f_GHz * flops_per_cycle_per_core * n_cores`` -- an architectural peak, not a
measured achieved rate. It scales linearly with frequency, so it tracks the clock; it is a
throughput proxy, not a benchmark result.

Example
-------
    python examples/mr_clipping_study.py --powers 50 65 --r-th 0.3 --mr-target-C 85
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
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power,
                                               die_power_of_trace,
                                               mcpat_flp_name_map, load_calibrated_leakage_model,
                                               load_leakage_model, LEAKAGE_CURVES,
                                               mcpat_tref_from_trace_dir)
from HotGauge.power.core_other import (CORE_OTHER_POLICIES, resolve_trace_dir,
                                      DEFAULT_CORE_OTHER_POLICY)
from HotGauge.thermal.rbb import amortize_rbb, add_rbb_argument
from HotGauge.thermal.sink_models import (ThermalResistanceSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan)
from HotGauge.thermal.sink_models import spreading_sink_for_stack
from HotGauge.thermal.die_stack import stack_for_spreading
from HotGauge.thermal.mr_array import wiring_for_stack, DEFAULT_PITCH_UM, DEFAULT_COVERAGE
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, mr_accounting,
                                                 DEFAULT_H_MAX_W_PER_MM2, DEFAULT_DT_MAX_K, DEFAULT_ETA_ASF, DEFAULT_LASER_WALLPLUG, DEFAULT_LPC_EFFICIENCY)
from HotGauge.power.performance_model import FMaxModel, performance_summary
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0
#: AVX-512: 2 FMA units x 8 doubles x 2 flops. Architectural peak, not achieved throughput.
DEFAULT_FLOPS_PER_CYCLE = 32.0


def die_peak(temps):
    vals = [float(np.ravel(v)[-1]) for v in temps.values()
            if float(np.ravel(v)[-1]) > T_FLOOR_K]
    return max(vals) if vals else float('nan')


def scaled_trace(trace_dir, total_power_W, flp_template, tech_node, num_cores=8):
    """Scale so the DIE dissipates total_power_W (not the raw McPAT sum -- see
    scale_trace_to_die_power: aggregates double-count, IMC/IO/SoC are missing)."""
    files = load_block_powers(trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.asarray(v, dtype=float).ravel()[0]) for u, v in json.load(f).items()}
    base = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    scaled, scale, die_W = scale_trace_to_die_power(base, flp_template, tech_node,
                                                    total_power_W, num_cores=num_cores)
    split = os.path.join(trace_dir,
                         os.path.basename(files[0]).replace('block_powers_', 'block_powers_split_'))
    leak = {}
    if os.path.isfile(split):
        with open(split) as f:
            leak = {u: float(v[1]) * scale for u, v in json.load(f).items()}
    return scaled, leak


def gflops(f_GHz, flops_per_cycle, n_cores):
    return float(f_GHz) * float(flops_per_cycle) * float(n_cores)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trace-dir', default='mcpat_runs/7nm/linpack_3.8GHz')
    ap.add_argument('--flp-template', default=None)
    ap.add_argument('--tech-node', type=int, default=7)
    add_rbb_argument(ap)
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
    ap.add_argument('--array-coverage', type=float, default=DEFAULT_COVERAGE,
                    help='fraction of the pixel layer\'s footprint that is emitting extractor '
                         '(AREAL). The device\'s couplers, waveguides, fibre access and '
                         'monolithic-backside LPC share that footprint with the tiles (v91 '
                         'Figs. 9.1/9.8/9.12), so < 1 charges the array its own area; the '
                         'uncovered silicon is cooled only by what spreads sideways through '
                         'the burial depth. 1.0 is every recorded result. Cannot move a '
                         'control-arm ceiling: the control has no array. See P0.18.')
    ap.add_argument('--no-array', action='store_true',
                    help='legacy placement: subtract the plan from the processor trace instead of putting it on the array. An upper bound, not the device -- see CoolingApplication')
    ap.add_argument('--cell-um', type=float, default=50.0,
                    help='3D-ICE grid cell; the tile grid SNAPS to it. Must match the cell= in '
                         'the stack spec: tiles snapped to a finer grid than the solver uses '
                         'come back overlapping after 3D-ICE quantises them, and the failure is '
                         'a wrong floorplan rather than an error')
    ap.add_argument('--powers', type=float, nargs='+', default=[50.0, 65.0])
    ap.add_argument('--r-th', type=float, default=0.3, help='bulk cooler [K/W]')
    ap.add_argument('--ambient-K', type=float, default=303.15)
    ap.add_argument('--leakage-cal', default='leakage_calibration/leakage_calibration.json')
    # `[!]` DEFAULT 'pipeline', and it must stay that way -- same discipline as --rbb-policy.
    # Every recorded result in this driver's catalogue was solved on the pipeline curve; changing
    # the default would silently move all of them. A non-default curve is a deliberate, flagged
    # re-run. See §P0.13/§P0.14 and thermal.leakage_feedback.load_leakage_model.
    ap.add_argument('--leakage-curve', default='pipeline', choices=list(LEAKAGE_CURVES),
                    help='which leakage-vs-temperature curve to solve on. pipeline = CACTI\'s '
                         '11 hard-coded numbers (the recorded catalogue); simulated = BSIM-CMG '
                         'on the ASAP7 card (P0.13); simulated-gidl-off = the other bracket')
    # §P0.16. `stock` (default) reproduces the recorded catalogue exactly; `hierarchy-consistent`
    # undoes the `2 * runtime_dynamic` in scripts/mcpat_to_blk_lvl_power_dict.py and residualises
    # the bare Core<N> row, so `core_other` carries leakage only. Additive: the non-default branch
    # is placed AHEAD of the existing path, which stays reachable and unmodified.
    ap.add_argument('--core-other-policy', default=DEFAULT_CORE_OTHER_POLICY,
                    choices=list(CORE_OTHER_POLICIES),
                    help='how to treat McPAT\'s per-core accounting. "hierarchy-consistent" '
                         '(default since P0.17) removes the converter\'s '
                         '2x on itemised per-core dynamic and gives core_other the true leakage '
                         'remainder (raises the die static fraction ~1.74x). See P0.16.')
    ap.add_argument('--doubling', type=float, default=15.0)
    ap.add_argument('--mr-target-C', type=float, default=85.0,
                    help='temperature MR clips hot blocks down to')
    ap.add_argument('--eta-asf', type=float, default=DEFAULT_ETA_ASF,
                    help='anti-Stokes/extractor efficiency (OPTICAL: heat removed per watt of '
                         'pump light). Electrical COP = eta_asf * eta_laser.')
    ap.add_argument('--eta-laser', type=float, default=DEFAULT_LASER_WALLPLUG, help='laser wall-plug efficiency')
    ap.add_argument('--eta-lpc', type=float, default=DEFAULT_LPC_EFFICIENCY, help='LPC cell efficiency')
    ap.add_argument('--recovery-at-junction', action='store_true',
                    help='bound the LPC recovery by the Carnot factor of the junction the heat is '
                         'actually lifted from (eq. 1.15). Without it the ledger uses the '
                         'phi -> 1 limit, which overstates recovery at every finite temperature '
                         'and at the shipped defaults reports a net-generating loop')
    ap.add_argument('--T0-K', type=float, default=295.0,
                    help='sink temperature for the Carnot factor, with --recovery-at-junction')
    ap.add_argument('--no-recovery', action='store_true',
                    help='disable LPC recovery (for before/after comparison)')
    ap.add_argument('--mr-h-max', type=float, default=DEFAULT_H_MAX_W_PER_MM2, help='W/mm^2 cooling density cap')
    ap.add_argument('--mr-dt-max', type=float, default=DEFAULT_DT_MAX_K)
    ap.add_argument('--mr-budget-W', type=float, default=None, help='cap on heat removed [W]')
    ap.add_argument('--mr-iter', type=int, default=6)
    ap.add_argument('--f-nominal', type=float, default=4.0)
    ap.add_argument('--derate-per-K', type=float, default=0.001)
    ap.add_argument('--throttle-C', type=float, default=100.0)
    ap.add_argument('--flops-per-cycle', type=float, default=DEFAULT_FLOPS_PER_CYCLE)
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=15)
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    # §P0.16: under a non-stock core_other policy, solve against a corrected copy of
    # the trace. Returns args.trace_dir unchanged under the default, so the recorded
    # path is byte-identical.
    args.trace_dir = resolve_trace_dir(args.trace_dir, args.core_other_policy)

    args.flp_template = args.flp_template or os.path.join(
        _HERE, 'floorplans', 'outputs',
        'skylake{}nm_7core_3_3D-ICE_template.flp'.format(args.tech_node))
    args.out_dir = args.out_dir or os.path.join(os.getcwd(), 'mr_clipping_study')
    os.makedirs(args.out_dir, exist_ok=True)

    area_m2 = chip_area_m2_from_floorplan(args.flp_template)
    flp = Floorplan.from_file(args.flp_template)
    geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                     'min_dim_um': float(min(e.width, e.height))} for e in flp.elements}
    name_map = mcpat_flp_name_map(include_core_idx=(args.num_cores > 1))

    if args.leakage_curve != 'pipeline':
        leak_model, t_ref = load_leakage_model(args.leakage_curve,
                                               calibration=args.leakage_cal)
        leak_src = 'leakage curve {!r} (P0.13/P0.14)'.format(args.leakage_curve)
    elif os.path.isfile(args.leakage_cal):
        leak_model, t_ref = load_calibrated_leakage_model(args.leakage_cal)
        leak_src = 'MEASURED McPAT curve'
    else:
        leak_model = LeakageModel.exponential(args.doubling)
        t_ref = mcpat_tref_from_trace_dir(args.trace_dir) or 330.0
        leak_src = 'assumed exponential ({:.0f} K)'.format(args.doubling)

    fmax = FMaxModel.linear_derate(args.derate_per_K)
    throttle_K = args.throttle_C + 273.15
    mr = MRParams(target_K=args.mr_target_C + 273.15, h_max=args.mr_h_max,
                  dt_max_K=args.mr_dt_max, eta_asf=args.eta_asf,
                  laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                  recover=not args.no_recovery, max_total_W=args.mr_budget_W)

    sink = ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K)
    stack_name = args.stack
    if args.spreading:
        stack_name = stack_for_spreading(stack_name)
        sink = spreading_sink_for_stack(stack_name, sink, area_m2 * 1e6,
                                        base_area_mm2=args.base_mm2)
    stack = render_stack_with_sink(get_stack_template(stack_name), sink,
                                   os.path.join(args.out_dir, 'stack.stk'))

    print('MR clipping study')
    print('  bulk cooler : R_th {:.3g} K/W over {:.4g} mm^2'.format(args.r_th, area_m2 * 1e6))
    print('  leakage     : {}, T_ref {:.1f} K'.format(leak_src, t_ref))
    print('  MR          : {}'.format(mr))
    print('  perf        : f_nom {:.2f} GHz, {:.0f} FLOP/cycle/core x {} cores'.format(
        args.f_nominal, args.flops_per_cycle, args.num_cores))
    print('\n  MR: COP_elec {:.3f} (= eta_ASF x eta_laser); breakeven ratio {:.3f} '
          '(self-sustaining at 1.0).\n  Cost quoted NET of LPC recovery. Judge on GFLOPs per '
          'TOTAL watt.\n'.format(mr.cop, mr.breakeven_ratio))

    hdr = ('{:<7s} {:<8s} {:>8s} {:>8s} {:>8s} {:>7s} {:>8s} {:>8s} {:>9s}'.format(
        'P_in[W]', 'case', 'peak[C]', 'P_cmp[W]', 'P_tot[W]', 'f[GHz]', 'GFLOP/s',
        'GFLOP/s/W', 'status'))
    print(hdr)
    print('-' * len(hdr))

    # The cooling array as a second powered die. --no-array keeps the legacy in-source-layer
    # placement, which is an upper bound rather than the device: the extracted watt crosses no
    # silicon, so burial depth is inert by construction.
    wiring = wiring_for_stack(stack, args.flp_template, args.out_dir,
                              want_array=not args.no_array, pitch_um=args.pitch_um,
                              cell_um=args.cell_um, coverage=args.array_coverage)

    rows = []
    for p_w in args.powers:
        trace, leak_ref = scaled_trace(args.trace_dir, p_w, args.flp_template,
                                       args.tech_node, num_cores=args.num_cores)
        # `[!]` Applied here, ONCE, on the baseline trace -- before the feedback loop, the
        # planner and the accounting, so all three see the same power map. Both the trace and
        # the leakage reference have to move together: rescale_trace rebuilds power as
        # `series - leak + leak*scale(T)`, so a zeroed series with a live leakage entry would
        # re-inject the bus with a negative power below T_ref.
        trace, leak_ref, rbb_meta = amortize_rbb(trace, args.flp_template,
                                                 policy=args.rbb_policy,
                                                 leakage_ref=leak_ref or None,
                                                 span=args.rbb_span,
                                                 name_map=mcpat_flp_name_map(
                                                     include_core_idx=args.num_cores > 1))
        leak_ref = leak_ref or {}
        if not leak_ref:
            leak_ref = {u: 0.2 * max(float(s[0]), 0.0) for u, s in trace.powers.items()}

        def make_solver(tag):
            return ICEThermalSolver(stack, args.flp_template, args.tech_node,
                                    run_base_dir=os.path.join(args.out_dir,
                                                              'P{:g}_{}'.format(p_w, tag)),
                                    initial_temp=args.ambient_K, num_cores=args.num_cores,
                                    single_thread=True, mode='steady',
                                    **(wiring.solver_kwargs() if wiring else {}))

        # --- baseline: leakage feedback only -------------------------------------------
        base = run_leakage_feedback(trace, leak_ref, make_solver('base'), model=leak_model,
                                    T_ref=t_ref, num_cores=args.num_cores, tol_K=args.tol,
                                    max_iter=args.max_iter, relax=0.5, t_floor_K=T_FLOOR_K,
                                       bridge_aggregates=True)
        b_div = bool(base.get('diverged'))
        b_peak = die_peak(base['temp_trace'])
        # Must use die_power_of_trace, NOT a raw sum: the McPAT trace carries hierarchy
        # aggregates that restate their children, so summing everything double-counts by
        # ~2.36x and silently deflates every perf-per-watt figure.
        b_pow = die_power_of_trace(base['power_trace'], args.flp_template, args.tech_node,
                                   num_cores=args.num_cores)
        if b_div:
            print('{:<7.0f} {:<8s} {:>8s} {:>8s} {:>8s} {:>7s} {:>8s} {:>8s} {:>9s}'.format(
                p_w, 'base', '--', '--', '--', '--', '--', '--', 'DIVERGED'))
            b_perf = None
        else:
            b_perf = performance_summary(
                [np.ravel(v)[-1] for v in base['temp_trace'].values()], fmax,
                f_nominal_GHz=args.f_nominal, compute_power_W=b_pow, throttle_K=throttle_K,
                t_floor_K=T_FLOOR_K)
            g = gflops(b_perf['f_effective_GHz'], args.flops_per_cycle, args.num_cores)
            print('{:<7.0f} {:<8s} {:>8.1f} {:>8.1f} {:>8.1f} {:>7.3f} {:>8.1f} {:>8.3f} {:>9s}'
                  .format(p_w, 'base', K_to_C(b_peak), b_pow, b_pow,
                          b_perf['f_effective_GHz'], g, g / b_pow,
                          'THROTTLE' if b_perf['throttling'] else 'ok'))

        # --- with MR clipping ----------------------------------------------------------
        # The MR loop needs a solver that includes leakage feedback, otherwise the cooling is
        # sized against a temperature field that ignores the leakage it will itself reduce.
        def solve_with_leakage(tr, _tag=['mr0']):
            tag = _tag[0]
            _tag[0] = 'mr{}'.format(int(tag[2:]) + 1)
            r = run_leakage_feedback(tr, leak_ref, make_solver(tag), model=leak_model,
                                     T_ref=t_ref, num_cores=args.num_cores, tol_K=args.tol,
                                     max_iter=args.max_iter, relax=0.5, t_floor_K=T_FLOOR_K,
                                       bridge_aggregates=True)
            solve_with_leakage.last = r
            return r['temp_trace']

        res = run_mr_clipping(trace, solve_with_leakage, geom, mr, name_map,
                              max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                              **(wiring.planner_kwargs() if wiring else {}))
        acc = res['accounting']
        last = getattr(solve_with_leakage, 'last', None)
        m_div = bool(last.get('diverged')) if last else True
        m_peak = die_peak(res['temp_trace'])
        if args.recovery_at_junction and not m_div and np.isfinite(m_peak):
            # `[!]` The recovery term is Carnot-limited by the temperature the heat is lifted
            # FROM, and that temperature is a result of the solve rather than an input to the
            # planner -- so the accounting is recomputed here rather than threaded through it.
            # Without this the ledger uses MRParams.breakeven_ratio, which is the phi -> 1
            # (infinite-T_h) limit and can report a net-generating loop the second law forbids.
            # See docs/evidence/loop_model_reconciliation.json.
            acc = mr_accounting(res['plan'], mr, detail=res.get('detail'),
                                T_h_K=float(m_peak), T_0_K=args.T0_K)
        m_cmp = (die_power_of_trace(last['power_trace'], args.flp_template, args.tech_node,
                                    num_cores=args.num_cores)
                 if last and not m_div else float('nan'))
        if m_div or not np.isfinite(m_cmp):
            print('{:<7.0f} {:<8s} {:>8s} {:>8s} {:>8s} {:>7s} {:>8s} {:>8s} {:>9s}'.format(
                p_w, 'MR', '--', '--', '--', '--', '--', '--', 'DIVERGED'))
            m_perf = None
        else:
            m_tot = m_cmp + acc['electrical_power_W']
            m_perf = performance_summary(
                [np.ravel(v)[-1] for v in res['temp_trace'].values()], fmax,
                f_nominal_GHz=args.f_nominal, compute_power_W=m_cmp,
                cooling_power_W=acc['electrical_power_W'], throttle_K=throttle_K,
                t_floor_K=T_FLOOR_K)
            g = gflops(m_perf['f_effective_GHz'], args.flops_per_cycle, args.num_cores)
            print('{:<7.0f} {:<8s} {:>8.1f} {:>8.1f} {:>8.1f} {:>7.3f} {:>8.1f} {:>8.3f} {:>9s}'
                  .format(p_w, 'MR', K_to_C(m_peak), m_cmp, m_tot,
                          m_perf['f_effective_GHz'], g, g / m_tot,
                          ('THROTTLE' if m_perf['throttling'] else 'ok')
                          + ('' if res['converged'] else '*')))
            print('         MR: removed {:.3f} W from {} block(s) -> {:.1f} W electrical '
                  '(net of {:.1f} W recovered){}'.format(acc['heat_removed_W'], acc['n_blocks_cooled'],
                                          acc['electrical_power_W'], acc['recovered_W'],
                                          '' if res['converged']
                                          else '  [* did not reach target: {}]'.format(
                                              res.get('reason', 'see detail'))))
            if b_perf is not None:
                dg = (g / m_tot) - (gflops(b_perf['f_effective_GHz'], args.flops_per_cycle,
                                           args.num_cores) / b_pow)
                # A zero delta means MR found nothing above target and did nothing -- that
                # is "not applicable here", not a loss.
                if acc['heat_removed_W'] <= 0:
                    verdict = 'MR INACTIVE (nothing above target)'
                else:
                    verdict = 'MR WINS' if dg > 0 else 'MR LOSES'
                print('         verdict: {} on GFLOP/s/W ({:+.4f})'.format(verdict, dg))
            elif b_div:
                print('         verdict: MR made a NON-VIABLE configuration viable')

        rows.append({'power_W': p_w, 'baseline': None if b_div else b_perf,
                     'mr': None if m_perf is None else m_perf, 'mr_accounting': acc,
                     'mr_converged': bool(res['converged']),
                     'baseline_diverged': b_div,
                     # Stamped per row for the same reason `placement` is: two generations of
                     # results now exist and the verdict alone does not tell them apart.
                     'rbb_policy': args.rbb_policy})

    out = os.path.join(args.out_dir, 'mr_study.json')
    with open(out, 'w') as f:
        json.dump({'r_th': args.r_th, 'mr': repr(mr), 'rbb': rbb_meta,
                   # The array charged its own footprint (P0.18); one wiring per run here.
                   'array_coverage': args.array_coverage,
                   'array': (wiring.area_fields() if wiring else None),
                   'rows': rows},
                  f, indent=2, default=str)
    print('\n  written: {}'.format(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
