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
Set by ``--spot-min-um`` (default 10 um) and ``--spot-policy``. The realistic pixel pitch for a
cooling tile array is 1-10 um, not the 100 um this study originally assumed: at 100 um only 20 of
57 above-target blocks on the 34-core die are addressable, at 10 um it is 44, and at 1 um all of
them. Spot size is therefore *not* the binding constraint -- the block selection policy is, since
blocks above a 92 C target carry only ~10% of die power while 65% sits 10-20 K below it.

``--spot-policy`` decides what happens to a block narrower than the pitch: ``dilute`` (default)
illuminates the whole pixel and bills the laser for it, ``exclude`` refuses it, ``ideal`` cools it
free. Everything before this option existed behaved as ``ideal``, so older results are an upper
bound on MR.

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
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink,
                                          chip_area_m2_from_floorplan, simscale_fan_power,
                                          SIMSCALE_T0_K)
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, mr_accounting,
                                                 DEFAULT_SPOT_MIN_UM,
                                                 DEFAULT_SPOT_POLICY)
from HotGauge.thermal.ice_server import ICESessionCache
from HotGauge.power.process_nodes import NODES, describe_assumptions, TRACE_REFERENCE_GHZ
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


def make_sink(args, area_m2):
    """The cooling solution for this point.

    Two ways to specify it, and they answer different questions:

    * ``--cfm`` -> ``BaffledFinSink``: the SimScale server air stack, whose resistance and fan
      power are both measured/fitted. Use it to ask "does this part work on air".
    * ``--r-th`` -> ``ThermalResistanceSink``: a bare thermal resistance in K/W, which is how
      cold plates and liquid loops are specified on datasheets. Use it to ask "how good does
      the cooling have to BE", which is the question once air has been shown to fail. Its
      parasitic power is not modelled (pump/chiller power is not in this model), so perf/W
      from an ``--r-th`` run counts compute + MR power only and is an upper bound.
    """
    if args.r_th is not None:
        return ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K,
                                     label='R_th {:.3g} K/W'.format(args.r_th))
    return BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K)


def evaluate(args, flp, trace, leak_ref, geom, name_map, leak_model, t_ref, fmax,
             area_m2, n_cores, use_mr, tag):
    """One (floorplan, MR on/off) point."""
    sink = make_sink(args, area_m2)
    stack = render_stack_with_sink(get_stack_template(args.stack), sink,
                                   os.path.join(args.out_dir, 'stacks', tag + '.stk'))
    counter = {'n': 0}

    def solver_factory(sub):
        return ICEThermalSolver(stack, flp, args.tech_node,
                                run_base_dir=os.path.join(args.out_dir, tag, sub),
                                initial_temp=args.ambient_K, num_cores=n_cores,
                                single_thread=True, mode='steady',
                                session_cache=args.session_cache)

    # The MR clipping loop calls this several times, so verification has to be accumulated over
    # ALL of them. Reporting only the last solve's agreement is actively misleading: a point can
    # fail verification on an intermediate MR iteration and still finish with a reassuring
    # 0.01 K spread, which invites someone to wave the flag away.
    ver = {'n_solves': 0, 'n_unconverged': 0, 'worst_spread_K': None}

    def solve_with_leakage(tr):
        counter['n'] += 1
        r = run_leakage_feedback(tr, leak_ref, solver_factory('it{:02d}'.format(counter['n'])),
                                 model=leak_model, T_ref=t_ref, num_cores=n_cores,
                                 tol_K=args.tol, max_iter=args.max_iter, relax=args.relax,
                                 t_floor_K=T_FLOOR_K, bridge_aggregates=True,
                                 verify=not args.no_verify, verify_tol_K=args.verify_tol)
        solve_with_leakage.last = r
        ver['n_solves'] += 1
        spread = r.get('peak_spread_K')
        if spread is not None:
            ver['worst_spread_K'] = max(ver['worst_spread_K'] or 0.0, float(spread))
        # An unverified solve is not a result. Record it so the row is flagged rather than
        # quoted: every large error in this project so far has been a damping artefact that
        # looked exactly like a converged number.
        if r.get('unconverged'):
            ver['n_unconverged'] += 1
        return r['temp_trace']

    mr = MRParams(target_K=args.mr_target_C + 273.15, h_max=args.mr_h_max,
                  dt_max_K=args.mr_dt_max, eta_asf=args.eta_asf,
                  laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                  spot_min_um=args.spot_min_um, spot_policy=args.spot_policy)

    def last_status():
        # Lets run_mr_clipping tell a converged baseline from a divergent one, which is what
        # decides whether the plan can be sized from the baseline at all.
        r = getattr(solve_with_leakage, 'last', None) or {}
        return {'diverged': bool(r.get('diverged')), 'unconverged': bool(r.get('unconverged'))}

    res = None
    if use_mr:
        res = run_mr_clipping(trace, solve_with_leakage, geom, mr, name_map,
                              max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                              status_fn=last_status, plan_mode=args.mr_plan_mode)
        temps, acc = res['temp_trace'], res['accounting']
    else:
        temps = solve_with_leakage(trace)
        acc = mr_accounting({}, mr)

    last = getattr(solve_with_leakage, 'last', None)
    # For an MR point the verdict belongs to the MR loop, not to the last leakage solve: the
    # envelope-anchored descent deliberately probes past the stability boundary and then reports
    # the last plan that held, so its final solve can be a diverged probe while the RESULT is a
    # perfectly good solution.
    if use_mr and 'temp_trace_diverged' in (res or {}):
        mr_field_diverged = bool(res.get('temp_trace_diverged'))
    else:
        mr_field_diverged = bool((last or {}).get('diverged'))
    row = {'tag': tag, 'cores': n_cores, 'mr': use_mr, 'fan_W': sink.parasitic_power_W(),
           'mr_reason': (res or {}).get('reason') if use_mr else None,
           'mr_loop_converged': bool((res or {}).get('converged')) if use_mr else None,
           # Whether the reported plan is the MINIMUM MR that keeps a steady state, or merely
           # an upper bound the descent stopped at. Only the former is a rescue-cost claim.
           'mr_plan_is_minimum': (res or {}).get('plan_is_minimum') if use_mr else None,
           # The one that decides whether a row is a RESCUE or merely a stable-but-hot die:
           # the minimum plan for a steady state to exist can leave the peak at 133 C.
           'mr_plan_holds_target': (res or {}).get('plan_holds_target') if use_mr else None,
           'mr_minimum_plan_W': (res or {}).get('minimum_plan_W') if use_mr else None,
           'mr_largest_failing_plan_W': (res or {}).get('largest_failing_plan_W') if use_mr
                                        else None,
           'unconverged': bool(ver['n_unconverged']),
           'n_solves': ver['n_solves'], 'n_unconverged_solves': ver['n_unconverged'],
           # worst_ is the one that decides whether this row is quotable; peak_spread_K is the
           # final solve's, kept because it is what the reported temperatures came from.
           'worst_peak_spread_K': ver['worst_spread_K'],
           'peak_spread_K': (last or {}).get('peak_spread_K'),
           'relax_final': (last or {}).get('relax_final')}
    if last is None or mr_field_diverged:
        row['diverged'] = True
        return row

    finals = {k: float(np.ravel(v)[-1]) for k, v in temps.items()}
    hot_name, hot_K = None, -np.inf
    for k, v in finals.items():
        if v > T_FLOOR_K and v > hot_K:
            hot_name, hot_K = k, v
    p_chip = die_power_of_trace(last['power_trace'], flp, args.tech_node, num_cores=n_cores)
    # Static-power accounting. The injected trace carries leakage extracted at T_ref; the
    # converged trace carries it rescaled to the solved temperatures. The difference is the
    # leakage the die gained (or, under MR, gave back) purely from its temperature, which is
    # what makes MR partly self-funding: cooling the hotspot lowers leakage everywhere hot.
    p_inj = die_power_of_trace(trace, flp, args.tech_node, num_cores=n_cores)
    p_leak_growth = p_chip - p_inj
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
                # Thermal-only vs IPC-scaled kept SEPARATE on purpose: the first is simulated,
                # the second multiplies it by an architectural ratio nothing here can verify.
                'ipc_rel': (args.node_obj.ipc_rel if args.node_obj else 1.0),
                'gflops_with_ipc': g * (args.node_obj.ipc_rel if args.node_obj else 1.0),
                'p_injected_W': p_inj, 'p_leak_growth_W': p_leak_growth,
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
    ap.add_argument('--r-th', type=float, default=None,
                    help='use a bare thermal resistance [K/W] instead of the airflow model -- '
                         'the way cold plates and liquid loops are specified (0.02-0.05 K/W is '
                         'liquid class). Overrides --cfm; pump power is NOT modelled.')
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
    # 'auto' sizes the plan from the uncooled baseline when that baseline exists, and from the
    # device envelope (descending toward the target) when it does not. The latter is required in
    # the rescue regime: there the baseline diverges, and planning from a point on a divergent
    # trajectory made the rescue depend on where the iteration stopped. See
    # HotGauge/thermal/microrefrigeration.py.
    ap.add_argument('--mr-plan-mode', default='auto', choices=('auto', 'baseline', 'envelope'),
                    help='how the MR plan is sized (default auto)')
    ap.add_argument('--spot-min-um', type=float, default=DEFAULT_SPOT_MIN_UM)
    ap.add_argument('--spot-policy', default=DEFAULT_SPOT_POLICY,
                    choices=('dilute', 'exclude', 'ideal'),
                    help='what to do with a block narrower than the pitch')
    ap.add_argument('--f-nominal', type=float, default=4.0)
    # Generational comparison. --node-model looks up that node's nominal clock and IPC, sets
    # f_nominal from it, and (unless --density is given explicitly) scales the operating density
    # by the dynamic-power cost of running at that clock instead of the trace's 3.8 GHz.
    #
    # That last part is the physically interesting coupling: a 7nm part rated at 5.0 GHz costs
    # 2.96x the dynamic power of the trace, so its "native" operating point is 0.660 * 2.96 =
    # 1.95 W/mm^2 -- deep into the regime where cooling decides whether the clock is reachable
    # at all. Ignoring it would compare nodes at a power budget none of them actually run at.
    #
    # IPC is applied ONLY to reported throughput (gflops_with_ipc), never to power or
    # temperature, because nothing in this pipeline can simulate it -- every trace is the same
    # microarchitecture. See HotGauge/power/process_nodes.py.
    ap.add_argument('--node-model', default=None, choices=sorted(NODES),
                    help='apply this node\'s nominal clock and IPC (generational study)')
    ap.add_argument('--native-density', action='store_true',
                    help='with --node-model, derive density from the node\'s own measured '
                         'power scaled to its nominal clock, instead of --density')
    ap.add_argument('--derate-per-K', type=float, default=0.001)
    ap.add_argument('--throttle-C', type=float, default=100.0)
    ap.add_argument('--flops-per-cycle', type=float, default=DEFAULT_FLOPS_PER_CYCLE)
    ap.add_argument('--tol', type=float, default=0.5)
    # Convergence verification is ON by default. Every solve is repeated at half the damping
    # and the peaks must agree; a point that fails is reported UNCONVERGED rather than as a
    # number. This exists because the damping the leakage fixed point needs cannot be
    # predicted, and getting it wrong is silent -- see docs/GAMEPLAN.md P0.1.
    ap.add_argument('--no-verify', action='store_true',
                    help='skip the second (half-damping) solve; faster, unsafe to quote')
    ap.add_argument('--verify-tol', type=float, default=1.0,
                    help='peak-temperature agreement [K] required between damping levels')
    # 60, not 30 or 12. Convergent cases still settle in 2-3 iterations, but two things need
    # headroom now: convergence is tested on the fixed-point RESIDUAL (a stricter measure than
    # the old change-between-solves, by roughly 1/relax), and declaring a genuine runaway means
    # the adaptive scheme has to walk the damping down to its floor first -- measured at ~48
    # solves. Iterations are ~0.6 s with a persistent session, so headroom is cheap.
    ap.add_argument('--max-iter', type=int, default=60)
    # 0.5 is now a STARTING point, not a fixed choice. The loop backtracks: any step that
    # increases the residual is rejected and retaken with half the damping, so the damping is
    # discovered per point instead of guessed. MEASURED on a lumped model driven by the real
    # 7nm leakage curve: the apparent runaway cliff moved 23% (11.21 -> 13.79 in theta) across
    # fixed relax values 1.0 -> 0.0125, and the peak that went with it moved 17 K; with
    # backtracking the same cliff lands at 11.227-11.229 from starting relax 1.0, 0.5 or 0.1 --
    # a 0.01% spread. That is the whole point: the answer no longer depends on the knob.
    ap.add_argument('--relax', type=float, default=0.5,
                    help='STARTING under-relaxation; the loop tightens it automatically')
    ap.add_argument('--no-server', action='store_true',
                    help='use the one-shot Emulator instead of a persistent '
                         '3D-ICE session (~150x slower; for cross-checking)')
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'mr_compare'))
    os.makedirs(args.out_dir, exist_ok=True)

    # One persistent 3D-ICE session, shared across every point in the sweep. It factorises the
    # system matrix once (~88 s on the 34-core die) and each later solve costs ~0.6 s instead
    # of ~88 s. Safe to share: the cache hashes everything the matrix is built from and rebuilds
    # automatically when the sink or floorplan changes, and a session refuses to solve against a
    # stack it did not factorise.
    args.session_cache = None if args.no_server else ICESessionCache()

    # --- generational node model -------------------------------------------------------
    args.node_obj = NODES[args.node_model] if args.node_model else None
    if args.node_obj is not None:
        args.f_nominal = args.node_obj.f_nominal_GHz
        args.tech_node = args.node_obj.tech_node
        args.node = '{}nm'.format(args.node_obj.tech_node)
        print(describe_assumptions())
        print()
        print('  node     : {} ({}), f_nominal {:.2f} GHz, IPC {:.2f}x'.format(
            args.node_obj.name, args.node_obj.era, args.node_obj.f_nominal_GHz,
            args.node_obj.ipc_rel))
        print('  clock    : dynamic power x{:.3f} vs the {:.1f} GHz trace'.format(
            args.node_obj.dynamic_power_factor(), TRACE_REFERENCE_GHZ))

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
    if args.r_th is not None:
        print('  cooling  : R_th {:.4g} K/W (bare resistance; pump power NOT modelled)'
              .format(args.r_th))
    else:
        print('  airflow  : {:.0f} CFM  (fan {:.1f} W)'.format(args.cfm,
                                                               simscale_fan_power(args.cfm)))
    print('  leakage  : {}'.format(leak_src))
    print('  MR       : eta_asf {:.2f}, laser {:.2f}, LPC {:.2f}, spot >= {:.0f} um'.format(
        args.eta_asf, args.eta_laser, args.eta_lpc, args.spot_min_um))
    print('  spot     : {:.0f} um pitch, policy={}'.format(
        args.spot_min_um, args.spot_policy))
    print()
    hdr = ('{:>6s} {:>8s} {:>7s} {:>4s} {:>8s} {:>8s} {:>8s} {:>8s} {:>7s} {:>10s} {:>9s}'
           .format('cores', 'area', 'P_die', 'MR', 'peak C', 'Q_rem', 'dP_leak', 'P_cool',
                   'f GHz', 'GFLOP/s', 'per totW'))
    print(hdr)
    print('-' * len(hdr))

    rows = []
    for n in args.cores:
        flp = floorplan_path(args.flp_dir, args.node, n)
        if args.node_obj is not None and args.native_density:
            # Measure this node's own power for the workload, then scale it to the node's rated
            # clock. That is the density the part actually runs at -- not an arbitrary sweep
            # value -- and it is where the generational comparison becomes meaningful.
            _base = replicate_trace_cores(base0, n, n_src=args.trace_cores) \
                if n > args.trace_cores else base0
            _p_native = die_power_of_trace(_base, flp, args.tech_node, num_cores=n)
            _area = chip_area_m2_from_floorplan(flp) * 1e6
            args.density = (_p_native / _area) * args.node_obj.dynamic_power_factor()
            print('  native   : {:.2f} W at 3.8 GHz -> {:.2f} W at {:.2f} GHz over {:.1f} mm^2'
                  ' = {:.3f} W/mm^2'.format(
                      _p_native, _p_native * args.node_obj.dynamic_power_factor(),
                      args.node_obj.f_nominal_GHz, _area, args.density))
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
                flags = '  THROTTLED' if r['throttling'] else ''
                if r.get('unconverged'):
                    flags += ('  ** UNCONVERGED: {}/{} solves failed verification, worst peak '
                              'spread {:.1f} K **').format(
                        r.get('n_unconverged_solves', '?'), r.get('n_solves', '?'),
                        r.get('worst_peak_spread_K') or float('nan'))
                print('{:>6d} {:>8.1f} {:>7.1f} {:>4s} {:>8.1f} {:>8.3f} {:>8.2f} {:>8.2f} '
                      '{:>7.3f} {:>10.1f} {:>9.3f}{}'.format(
                          n, area_m2 * 1e6, power_W, 'yes' if use_mr else 'no',
                          r['peak_C'], r['heat_removed_W'], r['p_leak_growth_W'],
                          r['p_cool_W'], r['f_GHz'], r['gflops'], r['gflops_per_total_W'],
                          flags))
        a, b = pair.get('nomr'), pair.get('mr')
        if a and b and (a.get('unconverged') or b.get('unconverged')):
            print('       -> MR delta NOT REPORTED: at least one side failed convergence '
                  'verification, so the difference would be a difference of artefacts.')
        elif a and b and not a['diverged'] and not b['diverged']:
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
        json.dump({'density': args.density, 'cfm': args.cfm, 'r_th': args.r_th,
                   'f_nominal_GHz': args.f_nominal, 'node': args.node,
                   'rows': rows}, f, indent=2)
    print('  written: {}'.format(os.path.join(args.out_dir, 'mr_comparison.json')))


if __name__ == '__main__':
    main()
