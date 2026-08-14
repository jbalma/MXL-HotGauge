#!/usr/bin/env python
"""How much clock does a cooling solution buy? (clock as a free variable)

The question this answers
-------------------------
Every earlier study fixed ``f_nominal`` and let the model derate downward, so the best score any
cooling technology could achieve was "stops the throttling" -- a ceiling set by the input, not by
physics. Here the clock is the *output*: for each cooling solution the search raises the clock
until the die can no longer hold its thermal limit, and reports the highest clock it can hold.

That is the number a customer buys, it is directly comparable across cooling classes and across
process nodes, and -- because the criterion is a temperature limit rather than a frequency
derating -- it does **not** inherit the uncalibrated ``derate_per_K`` slope that the GFLOP/s
figures elsewhere rest on.

Three studies fall out of the same sweep
----------------------------------------
1. **What cooling does a 7nm part at its rated clock actually need?** Sweep ``--r-th`` down to
   liquid-class resistances and read off where the sustainable clock reaches the rated one.
2. **Iso-cooling generational comparison.** Same ``--r-th``, different ``--node-model``: the
   sustainable clock per node at identical cooling.
3. **What does MR add on top?** ``--mr`` runs each point twice, with and without hotspot
   clipping, and reports the clock difference.

Examples
--------
    # what cooling does the 7nm part need to hold its rated 5.0 GHz?
    python examples/clock_headroom.py --cores 34 --node-model 7nm \\
        --r-th 1.0 0.5 0.3 0.1 0.05 0.02 --mr

    # sustainable clock on server air, per node, at matched cooling
    python examples/clock_headroom.py --cores 34 --cfm 88 --node-model 14nm
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
from HotGauge.thermal.leakage_feedback import (die_power_of_trace, mcpat_flp_name_map,
                                               replicate_trace_cores, peak_temp_K,
                                               load_calibrated_leakage_model,
                                               mcpat_tref_from_trace_dir)
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink,
                                          chip_area_m2_from_floorplan, simscale_fan_power,
                                          SIMSCALE_T0_K)
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, mr_accounting,
                                                 distributed_plan, apply_cooling_to_trace,
                                                 DEFAULT_SPOT_MIN_UM, DEFAULT_SPOT_POLICY)
from HotGauge.thermal.ice_server import ICESessionCache
from HotGauge.power.process_nodes import NODES, describe_assumptions, TRACE_REFERENCE_GHZ
from HotGauge.power.clock_search import (scale_trace_for_clock, find_max_sustainable_clock,
                                         scale_trace_for_clock_per_core, scale_cores,
                                         single_core_turbo, emphasise_units, VF_TABLE_MAX_GHZ)
from HotGauge.power.performance_model import FMaxModel, performance_summary
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0
DEFAULT_FLOPS_PER_CYCLE = 32.0


def floorplan_path(flp_dir, node, n):
    stem = 'skylake{}_{}core_3_3D-ICE_template.flp'.format(node, n)
    p = os.path.join(flp_dir, stem)
    return p if os.path.isfile(p) else os.path.join(flp_dir, stem.replace('_3_', '_0_'))


def make_sink(args, area_m2, r_th):
    """Cooling as a bare resistance (``--r-th``) or as the measured air stack (``--cfm``).

    A resistance is how cold plates and liquid loops are specified, and it is the right axis
    once the question is "how good does the cooling have to BE". Its pump/chiller power is not
    modelled, so cooling power for those points counts MR only and is an underestimate.
    """
    if r_th is not None:
        return ThermalResistanceSink(r_th, area_m2, ambient_K=args.ambient_K,
                                     label='R_th {:.3g} K/W'.format(r_th))
    return BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K)


def evaluate_clock(args, flp, base_trace, leak_ref_base, geom, name_map, leak_model, t_ref,
                   n_cores, sink, stack, use_mr, f_GHz, tag):
    """One coupled solve at clock ``f_GHz``: rescale the trace, run the leakage fixed point
    (with damping verification), optionally clip hotspots with MR, return the peak."""
    if args.turbo_core is not None:
        # Single-thread turbo: only the boosted core's clock is searched; the rest stay at the
        # trace's own clock. This is the geometry the tier screen says MR should suit best --
        # one hot structure with cool silicon around it -- and it cannot be expressed by a
        # global clock.
        trace, leak_ref, scale_info = scale_trace_for_clock_per_core(
            base_trace, leak_ref_base, {args.turbo_core: f_GHz}, TRACE_REFERENCE_GHZ,
            leakage_voltage_exponent=args.leak_v_exponent)
    else:
        trace, leak_ref, scale_info = scale_trace_for_clock(
            base_trace, leak_ref_base, f_GHz, TRACE_REFERENCE_GHZ,
            leakage_voltage_exponent=args.leak_v_exponent)

    counter = {'n': 0}
    # Accumulated over every solve the MR loop makes, not just the last one -- see the same
    # note in examples/mr_comparison.py. A point can fail on an intermediate MR iteration and
    # still finish with a reassuring final spread.
    state = {'unconverged': 0, 'last': None, 'n_solves': 0, 'worst_spread_K': None}

    def solver_factory(sub):
        return ICEThermalSolver(stack, flp, args.tech_node,
                                run_base_dir=os.path.join(args.out_dir, tag,
                                                          'f{:.3f}'.format(f_GHz), sub),
                                initial_temp=args.ambient_K, num_cores=n_cores,
                                single_thread=True, mode='steady',
                                session_cache=args.session_cache)

    def solve_with_leakage(tr):
        counter['n'] += 1
        r = run_leakage_feedback(tr, leak_ref, solver_factory('it{:02d}'.format(counter['n'])),
                                 model=leak_model, T_ref=t_ref, num_cores=n_cores,
                                 tol_K=args.tol, max_iter=args.max_iter, relax=args.relax,
                                 t_floor_K=T_FLOOR_K, bridge_aggregates=True,
                                 verify=not args.no_verify, verify_tol_K=args.verify_tol)
        state['last'] = r
        state['n_solves'] += 1
        spread = r.get('peak_spread_K')
        if spread is not None:
            state['worst_spread_K'] = max(state['worst_spread_K'] or 0.0, float(spread))
        if r.get('unconverged'):
            state['unconverged'] += 1
        return r['temp_trace']

    mr = MRParams(target_K=args.mr_target_K, h_max=args.mr_h_max,
                  dt_max_K=args.mr_dt_max, eta_asf=args.eta_asf,
                  laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                  spot_min_um=args.spot_min_um, spot_policy=args.spot_policy)

    def last_status():
        r = state.get('last') or {}
        return {'diverged': bool(r.get('diverged')), 'unconverged': bool(r.get('unconverged'))}

    res = None
    if use_mr and args.mr_mode == 'distributed':
        # Design E, the control arm: spend the SAME budget spread over the die instead of
        # clipping hotspots. If this buys the same clock, the hotspot framing is wrong and the
        # comparison should be against a better sink rather than against nothing.
        plan, plan_detail = distributed_plan(geom, mr, args.mr_budget_W, weight=args.mr_weight)
        temps = solve_with_leakage(apply_cooling_to_trace(trace, plan, name_map))
        acc = mr_accounting(plan, mr, detail=plan_detail)
        res = {'plan': plan, 'converged': True, 'temp_trace': temps,
               'temp_trace_diverged': bool((state['last'] or {}).get('diverged')),
               'reason': 'distributed plan at a fixed budget (control arm)'}
    elif use_mr:
        res = run_mr_clipping(trace, solve_with_leakage, geom, mr, name_map,
                              max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                              status_fn=last_status, plan_mode=args.mr_plan_mode)
        temps, acc = res['temp_trace'], res['accounting']
    else:
        temps = solve_with_leakage(trace)
        acc = mr_accounting({}, mr)

    last = state['last'] or {}
    # See the note in examples/mr_comparison.py: for an MR point the MR loop's own verdict is
    # authoritative, because the envelope descent probes past the boundary on purpose.
    if use_mr and 'temp_trace_diverged' in (res or {}):
        field_diverged = bool(res.get('temp_trace_diverged'))
    else:
        field_diverged = bool(last.get('diverged'))
    out = {'f_GHz': f_GHz, 'diverged': field_diverged or temps is None,
           'unconverged': bool(state['unconverged']),
           'n_unconverged_solves': state['unconverged'], 'n_solves': state['n_solves'],
           'worst_peak_spread_K': state['worst_spread_K'],
           'vf_clamped': scale_info['vf_clamped'],
           'peak_spread_K': last.get('peak_spread_K'),
           'p_mr_net_W': acc['electrical_power_W'],
           'heat_removed_W': acc['heat_removed_W'],
           'n_targets': acc.get('n_blocks_cooled', 0)}
    if out['diverged'] or temps is None:
        out['peak_K'] = None
        return out
    out['peak_K'] = peak_temp_K(temps, T_FLOOR_K)
    out['peak_block'] = max(((k, float(np.ravel(v)[-1])) for k, v in temps.items()),
                            key=lambda kv: kv[1] if kv[1] > T_FLOOR_K else -np.inf)[0]
    out['p_chip_W'] = die_power_of_trace(last['power_trace'], flp, args.tech_node,
                                         num_cores=n_cores)
    out['p_injected_W'] = die_power_of_trace(trace, flp, args.tech_node, num_cores=n_cores)
    out['temps'] = {k: float(np.ravel(v)[-1]) for k, v in temps.items()}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--node-model', default=None, choices=sorted(NODES),
                    help='report this node\'s rated clock alongside the sustainable one')
    # --- cooling axis ---
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, nargs='+', default=None,
                    help='sweep these sink resistances [K/W] instead of --cfm '
                         '(0.02-0.05 is liquid class)')
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    # --- clock search ---
    ap.add_argument('--f-lo', type=float, default=2.0)
    ap.add_argument('--f-hi', type=float, default=VF_TABLE_MAX_GHZ)
    ap.add_argument('--f-tol', type=float, default=0.05)
    ap.add_argument('--thermal-limit-C', type=float, default=100.0,
                    help='peak-block temperature the part must hold [C]')
    ap.add_argument('--leak-v-exponent', type=float, default=1.0,
                    help='leakage scales as V**this with clock/voltage (ASSUMPTION; 0 ignores '
                         'the voltage dependence entirely)')
    # Design A/G axes: which core is boosted, how quiet the others are, and whether a core's
    # power is concentrated into one structure. See docs/DESIGN_STUDY_PLAN.md.
    ap.add_argument('--turbo-core', type=int, default=None,
                    help='search the clock of THIS core only; the others stay at the trace '
                         'clock and are quieted by --turbo-background')
    ap.add_argument('--turbo-background', type=float, default=0.25,
                    help='activity of the non-boosted cores (with --turbo-core)')
    ap.add_argument('--emphasise', default=None,
                    help="concentrate each core's power into units matching this substring, "
                         "e.g. 'Floating Point Units' (accelerator-style core)")
    ap.add_argument('--emphasis-factor', type=float, default=4.0)
    ap.add_argument('--above-vf-table', action='store_true',
                    help='allow searching past %.1f GHz, where the V/F table clamps the voltage '
                         'and the power cost of the clock is UNDERSTATED' % VF_TABLE_MAX_GHZ)
    # --- MR ---
    ap.add_argument('--mr', action='store_true', help='also search with hotspot clipping on')
    ap.add_argument('--mr-target-C', type=float, default=92.0,
                    help='absolute MR clip target [C]. NOTE this is usually the wrong policy '
                         'here -- see --mr-target-margin-K')
    # Convenience: express the target relative to the thermal limit rather than absolutely, so
    # a study that changes --thermal-limit-C does not silently change the MR coverage too.
    #
    # It does NOT fix the policy problem this sweep uncovered, and it is worth being precise
    # about why. With the clock free, MR clipped nothing exactly where cooling was worst:
    # at R_th 1.0 K/W the part settles at 2.797 GHz with a peak of 85.7 C and MR buys 0.000 GHz.
    # The tempting reading is "the 92 C target is too high, tie it to the 100 C limit" -- but
    # that point is not limited by the 100 C limit at all, it is limited by RUNAWAY at 85.7 C.
    # The leakage instability bites 14 K below the spec limit, so no target anchored to the limit
    # will ever engage there.
    #
    # A target that works at every cooling class has to be anchored to the operating point (peak
    # minus a margin) or to leakage contribution rather than temperature -- which is the
    # leakage-ranked policy in docs/GAMEPLAN.md, and needs its own study rather than a flag.
    ap.add_argument('--mr-target-margin-K', type=float, default=None,
                    help='set the MR target this many K below the THERMAL LIMIT instead of at a '
                         'fixed temperature (8 -> 92 C when the limit is 100 C). Note this does '
                         'not help where the binding constraint is runaway below the limit. '
                         'Overrides --mr-target-C.')
    ap.add_argument('--eta-asf', type=float, default=0.20)
    ap.add_argument('--eta-laser', type=float, default=0.70)
    ap.add_argument('--eta-lpc', type=float, default=0.90)
    ap.add_argument('--mr-h-max', type=float, default=10.0)
    ap.add_argument('--mr-dt-max', type=float, default=10.0)
    ap.add_argument('--mr-iter', type=int, default=6)
    # Design E: 'clip' targets hot blocks (the assumption behind every MR result here);
    # 'distributed' spreads a fixed budget over the die, which is the control that tests it.
    ap.add_argument('--mr-mode', default='clip', choices=('clip', 'distributed'))
    ap.add_argument('--mr-budget-W', type=float, default=1.0,
                    help='heat to remove [W] in distributed mode; set it to the clipping run\'s '
                         'Q so the two are compared at equal cooling')
    ap.add_argument('--mr-weight', default='area', choices=('area', 'uniform'))
    ap.add_argument('--mr-plan-mode', default='auto', choices=('auto', 'baseline', 'envelope'),
                    help='how the MR plan is sized; auto switches to the envelope-anchored '
                         'descent when the uncooled die has no steady state')
    ap.add_argument('--spot-min-um', type=float, default=DEFAULT_SPOT_MIN_UM)
    ap.add_argument('--spot-policy', default=DEFAULT_SPOT_POLICY,
                    choices=('dilute', 'exclude', 'ideal'))
    # --- solver ---
    ap.add_argument('--leakage-cal', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--no-verify', action='store_true')
    ap.add_argument('--verify-tol', type=float, default=1.0)
    ap.add_argument('--flops-per-cycle', type=float, default=DEFAULT_FLOPS_PER_CYCLE)
    ap.add_argument('--derate-per-K', type=float, default=0.001)
    ap.add_argument('--no-server', action='store_true')
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'clock_headroom'))
    os.makedirs(args.out_dir, exist_ok=True)
    args.session_cache = None if args.no_server else ICESessionCache()

    node_obj = NODES[args.node_model] if args.node_model else None
    if node_obj is not None:
        args.tech_node = node_obj.tech_node
        args.node = '{}nm'.format(node_obj.tech_node)

    if os.path.isfile(args.leakage_cal):
        leak_model, t_ref = load_calibrated_leakage_model(args.leakage_cal, extrapolate=True)
        leak_src = 'MEASURED McPAT curve + Arrhenius tail above 400 K'
    else:
        leak_model = LeakageModel.exponential(15.0)
        t_ref = mcpat_tref_from_trace_dir(args.trace_dir) or 330.0
        leak_src = 'assumed exponential'
    fmax = FMaxModel.linear_derate(args.derate_per_K)
    thermal_limit_K = args.thermal_limit_C + 273.15
    if args.mr_target_margin_K is not None:
        args.mr_target_K = thermal_limit_K - args.mr_target_margin_K
        mr_target_note = '{:.1f} C  (thermal limit - {:.1f} K)'.format(
            args.mr_target_K - 273.15, args.mr_target_margin_K)
    else:
        args.mr_target_K = args.mr_target_C + 273.15
        mr_target_note = '{:.1f} C  (absolute)'.format(args.mr_target_C)

    # Baseline trace at the trace's own clock; the search rescales it per candidate clock.
    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    split = os.path.join(args.trace_dir, os.path.basename(files[0]).replace(
        'block_powers_', 'block_powers_split_'))
    leak_ref_base = {}
    if os.path.isfile(split):
        with open(split) as f:
            leak_ref_base = {u: np.array([float(v[1])]) for u, v in json.load(f).items()}

    flp = floorplan_path(args.flp_dir, args.node, args.cores)
    if not os.path.isfile(flp):
        print('no floorplan for {} {}-core: {}'.format(args.node, args.cores, flp))
        return 1
    area_m2 = chip_area_m2_from_floorplan(flp)
    base = (replicate_trace_cores(base0, args.cores, n_src=args.trace_cores)
            if args.cores > args.trace_cores else base0)
    # Design shape first (constant core power), then activity. Both are properties of the part
    # and the workload, not of the clock, so they are applied before the clock search begins.
    if args.emphasise:
        base = emphasise_units(base, args.emphasise, args.emphasis_factor)
    if args.turbo_core is not None:
        base = scale_cores(base, single_core_turbo(args.cores, args.turbo_core,
                                                   args.turbo_background))
    p_ref = die_power_of_trace(base, flp, args.tech_node, num_cores=args.cores)
    fp = Floorplan.from_file(flp)
    geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                     'min_dim_um': float(min(e.width, e.height))} for e in fp.elements}
    name_map = mcpat_flp_name_map(include_core_idx=(args.cores > 1))

    print('sustainable-clock search  ({} , {}-core, {:.1f} mm^2)'.format(
        args.node, args.cores, area_m2 * 1e6))
    print('  trace    : {:.1f} W on the die at {:.1f} GHz ({:.3f} W/mm^2)'.format(
        p_ref, TRACE_REFERENCE_GHZ, p_ref / (area_m2 * 1e6)))
    print('  limit    : peak block <= {:.0f} C, damping-verified solves only'.format(
        args.thermal_limit_C))
    if args.emphasise:
        print('  design   : {!r} x{:.2f} at constant core power'.format(
            args.emphasise, args.emphasis_factor))
    if args.turbo_core is not None:
        print('  turbo    : core {} clocked alone, others at {:.2f} activity'.format(
            args.turbo_core, args.turbo_background))
    print('  leakage  : {}, +V^{:.2g} with clock (assumption)'.format(
        leak_src, args.leak_v_exponent))
    if args.mr:
        print('  MR target: {}'.format(mr_target_note))
    if node_obj is not None:
        print(describe_assumptions())
        print('  rated    : {} = {:.2f} GHz'.format(node_obj.name, node_obj.f_nominal_GHz))
    print()

    coolers = [(r, None) for r in (args.r_th or [])] or [(None, args.cfm)]
    hdr = ('{:>14s} {:>4s} {:>9s} {:>8s} {:>8s} {:>8s} {:>9s} {:>10s}  {}'.format(
        'cooling', 'MR', 'f_sust', 'peak C', 'P_die W', 'W/mm^2', 'P_cool W', 'GFLOP/s',
        'limited by'))
    print(hdr)
    print('-' * len(hdr))

    rows = []
    for r_th, cfm in coolers:
        sink = make_sink(args, area_m2, r_th)
        label = ('R_th {:.3g}'.format(r_th) if r_th is not None
                 else '{:.0f} CFM'.format(cfm))
        tag = ('rth{:g}'.format(r_th) if r_th is not None else 'cfm{:g}'.format(cfm))
        stack = render_stack_with_sink(get_stack_template(args.stack), sink,
                                       os.path.join(args.out_dir, 'stacks', tag + '.stk'))
        for use_mr in ((False, True) if args.mr else (False,)):
            sub = '{}_{}'.format(tag, 'mr' if use_mr else 'nomr')
            seen = {}

            def evaluate(f, _sub=sub, _mr=use_mr, _sink=sink, _stack=stack):
                r = evaluate_clock(args, flp, base, leak_ref_base, geom, name_map, leak_model,
                                   t_ref, args.cores, _sink, _stack, _mr, f, _sub)
                seen[round(f, 6)] = r
                return r

            search = find_max_sustainable_clock(
                evaluate, args.f_lo, args.f_hi, tol_GHz=args.f_tol,
                thermal_limit_K=thermal_limit_K,
                cap_at_vf_table=not args.above_vf_table)

            f_s = search['f_sustainable_GHz']
            best = seen.get(round(f_s, 6)) if f_s is not None else None
            row = {'cooling': label, 'r_th': r_th, 'cfm': cfm, 'mr': use_mr,
                   'f_sustainable_GHz': f_s, 'limited_by': search['limited_by'],
                   'at_ceiling': search['at_ceiling'],
                   'vf_clamped': search['vf_clamped'],
                   'bracket_GHz': search['bracket_GHz'],
                   'evaluations': [{k: v for k, v in e.items()} for e in search['evaluations']],
                   'fan_W': sink.parasitic_power_W(),
                   'rated_GHz': node_obj.f_nominal_GHz if node_obj else None}
            if best is not None and best.get('peak_K'):
                p_cool = sink.parasitic_power_W() + best['p_mr_net_W']
                g = f_s * args.flops_per_cycle * args.cores
                row.update({'peak_C': K_to_C(best['peak_K']),
                            'peak_block': best.get('peak_block'),
                            'p_chip_W': best['p_chip_W'],
                            'density_W_per_mm2': best['p_chip_W'] / (area_m2 * 1e6),
                            'p_mr_net_W': best['p_mr_net_W'],
                            'heat_removed_W': best['heat_removed_W'],
                            'p_cool_W': p_cool, 'gflops': g,
                            'gflops_per_total_W': g / (best['p_chip_W'] + p_cool)})
                print('{:>14s} {:>4s} {:>9.3f} {:>8.1f} {:>8.1f} {:>8.3f} {:>9.2f} {:>10.1f}  {}'
                      .format(label, 'yes' if use_mr else 'no', f_s, row['peak_C'],
                              row['p_chip_W'], row['density_W_per_mm2'], p_cool, g,
                              row['limited_by']
                              + (' (SEARCH CEILING, not the part)' if search['at_ceiling']
                                 else '')
                              + (' [V/F CLAMPED]' if search['vf_clamped'] else '')))
            else:
                print('{:>14s} {:>4s} {:>9s} {:>8s} {:>8s} {:>8s} {:>9s} {:>10s}  {}'.format(
                    label, 'yes' if use_mr else 'no', 'none', '--', '--', '--', '--', '--',
                    'no sustainable clock >= {:.2f} GHz ({})'.format(
                        args.f_lo, row['limited_by'])))
            rows.append(row)

        if args.mr and len(rows) >= 2 and rows[-1]['f_sustainable_GHz'] and \
                rows[-2]['f_sustainable_GHz']:
            d = rows[-1]['f_sustainable_GHz'] - rows[-2]['f_sustainable_GHz']
            print('{:>14s}      -> MR buys {:+.3f} GHz ({:+.1f}%) for {:.2f} W net'.format(
                '', d, 100.0 * d / rows[-2]['f_sustainable_GHz'],
                rows[-1].get('p_mr_net_W', 0.0)))

    out = os.path.join(args.out_dir, 'clock_headroom.json')
    with open(out, 'w') as f:
        json.dump({'node': args.node, 'cores': args.cores, 'area_mm2': area_m2 * 1e6,
                   'p_ref_W': p_ref, 'trace_GHz': TRACE_REFERENCE_GHZ,
                   'thermal_limit_C': args.thermal_limit_C,
                   'leak_v_exponent': args.leak_v_exponent,
                   'turbo_core': args.turbo_core, 'turbo_background': args.turbo_background,
                   'emphasise': args.emphasise, 'emphasis_factor': args.emphasis_factor,
                   'mr_mode': args.mr_mode, 'mr_budget_W': args.mr_budget_W,
                   'mr_target_C': args.mr_target_K - 273.15,
                   'mr_target_margin_K': args.mr_target_margin_K,
                   'rated_GHz': node_obj.f_nominal_GHz if node_obj else None,
                   'rows': rows}, f, indent=2)
    print('\n  written: {}'.format(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
