#!/usr/bin/env python
"""F4 (§P0.25): burst absorption -- can a MODULATED photonic array hold a power burst that the
package's thermal mass cannot? Transient solve, warm-started from the steady state.

    python examples/burst_absorption_study.py --density 0.80 --burst-factor 2.0 \\
        --arms control array_static array_modulated --out-dir results/burst/d0.80/k2.0

The experiment
--------------
The die runs at ``--density`` (the steady operating point). For ``--burst-ms`` the DYNAMIC power
of every block is multiplied by ``--burst-factor`` (an activity burst at fixed voltage; the
leakage reference is untouched and the leakage feedback follows the temperature). Three arms:

* ``control``          the conventional package (grease), no array;
* ``array_static``     the GaAs array in place with the steady baseline plan held fixed through
                       the burst (at a density the unpowered array holds, that plan is zero);
* ``array_modulated``  the same array with a per-slot tile schedule: the baseline plan outside
                       the burst and a burst plan during it. ``--modulation feedforward``
                       (default) removes the burst's own added watts at their source -- what a
                       controller with a power monitor would do, and physically the array's
                       microsecond response is what makes that possible; ``--modulation
                       planner`` uses the steady planner's minimum plan at the burst power.

Each arm is warm-started from its own converged steady state (`final.tstack` of the last
leakage-feedback iteration), so the transient covers only ``--pre-ms`` + ``--burst-ms`` +
``--post-ms``. The leakage loop runs in transient mode with damping verification, as everywhere.

Reported per arm: peak temperature per slot, the overshoot above the pre-burst peak, the time
above the 92 C target and the 100 C spec, and the laser energy the modulated arm spent. The
"burst factor" a die can absorb is read across a ladder of ``--burst-factor`` values.

`[!]` Honest limits. Whole-die burst (every block's dynamic power scaled alike); the extractor's
per-tile cap is steady-only, so the modulated arm is not capped by the film -- read the tile
flux it asks for against the device (the register's 813 W/mm^2 at 300 K); 3D-ICE transient with
``--steps-per-slot`` sub-steps per slot; no clock or voltage model in the burst (it is watts).
"""
import os
import sys
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace
from HotGauge.configuration import load_block_powers
from HotGauge.thermal import get_stack_template, ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.rbb import amortize_rbb, add_rbb_argument
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, die_power_of_trace,
                                               mcpat_flp_name_map, replicate_trace_cores,
                                               load_leakage_model, LEAKAGE_CURVES, peak_temp_K,
                                               prepare_dice_trace)
from HotGauge.power.core_other import (CORE_OTHER_POLICIES, resolve_trace_dir,
                                      DEFAULT_CORE_OTHER_POLICY)
from HotGauge.thermal.die_stack import DEFAULT_DIRECT_SOURCE_DEPTH_UM
from HotGauge.thermal.sink_models import (BaffledFinSink, render_stack_with_sink,
                                          spreading_sink_for_stack, chip_area_m2_from_floorplan,
                                          SIMSCALE_T0_K)
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, DEFAULT_H_MAX_W_PER_MM2, DEFAULT_DT_MAX_K,
                                                 DEFAULT_ETA_ASF, DEFAULT_LASER_WALLPLUG,
                                                 DEFAULT_LPC_EFFICIENCY, DEFAULT_SPOT_MIN_UM,
                                                 DEFAULT_SPOT_POLICY)
from HotGauge.thermal.ice_server import ICESessionCache
from HotGauge.thermal.mr_array import (wiring_for_stack, DEFAULT_PITCH_UM, DEFAULT_COVERAGE,
                                       tile_power_schedule, tile_powers_for_stack)
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0
ARMS = ('control', 'array_static', 'array_modulated')


def floorplan_path(flp_dir, node, n):
    p = os.path.join(flp_dir, 'skylake{}_{}core_3_3D-ICE_template.flp'.format(node, n))
    return p


def stack_spec(args, arm):
    mr = 'none' if arm == 'control' else args.mr_material
    return 'spec:package=direct_die,mr={},src={:.0f},cell={:.0f}{}'.format(
        mr, args.burial_um, args.cell_um, ',sink_in_stack=0' if args.spreading else '')


def burst_trace(base, leak_ref, k, n_pre, n_burst, n_post):
    """The N-slot trace: baseline outside the burst, dynamic x k inside it; the leakage
    reference as a matching per-slot series (constant -- an activity burst at fixed V)."""
    n = n_pre + n_burst + n_post
    mask = np.zeros(n); mask[n_pre:n_pre + n_burst] = 1.0
    powers, leaks = {}, {}
    for u, v in base.powers.items():
        p = float(np.ravel(v)[0]); l = float(np.ravel(leak_ref.get(u, 0.0))[0]) if u in leak_ref else 0.0
        dyn = max(p - l, 0.0)
        powers[u] = l + dyn * (1.0 + (k - 1.0) * mask)
        if u in leak_ref:
            leaks[u] = np.full(n, l)
    return BasicPowerTrace(powers, base.time_step), leaks, mask


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--node', default='7nm'); ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm', 'linpack_3.8GHz'))
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--density', type=float, default=0.80, help='steady operating point, W/mm^2')
    ap.add_argument('--burst-factor', type=float, default=2.0, help='dynamic power multiplier during the burst')
    ap.add_argument('--pre-ms', type=float, default=5.0); ap.add_argument('--burst-ms', type=float, default=10.0)
    ap.add_argument('--post-ms', type=float, default=10.0); ap.add_argument('--slot-ms', type=float, default=1.0)
    ap.add_argument('--steps-per-slot', type=int, default=10)
    ap.add_argument('--arms', nargs='+', default=list(ARMS), choices=list(ARMS))
    ap.add_argument('--modulation', default='feedforward', choices=('feedforward', 'planner'))
    ap.add_argument('--cfm', type=float, default=88.0); ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    ap.add_argument('--spreading', action='store_true'); ap.add_argument('--base-mm2', type=float, default=None)
    ap.add_argument('--mr-material', default='GAAS'); ap.add_argument('--pitch-um', type=float, default=DEFAULT_PITCH_UM)
    ap.add_argument('--burial-um', type=float, default=DEFAULT_DIRECT_SOURCE_DEPTH_UM)
    ap.add_argument('--cell-um', type=float, default=50.0); ap.add_argument('--array-coverage', type=float, default=DEFAULT_COVERAGE)
    ap.add_argument('--mr-target-C', type=float, default=92.0); ap.add_argument('--spec-C', type=float, default=100.0)
    ap.add_argument('--mr-h-max', type=float, default=DEFAULT_H_MAX_W_PER_MM2)
    ap.add_argument('--mr-dt-max', type=float, default=None, help='scalar lift cap [K]; default microrefrigeration.DEFAULT_DT_MAX_K')
    ap.add_argument('--eta-asf', type=float, default=DEFAULT_ETA_ASF); ap.add_argument('--eta-laser', type=float, default=DEFAULT_LASER_WALLPLUG)
    ap.add_argument('--eta-lpc', type=float, default=DEFAULT_LPC_EFFICIENCY)
    ap.add_argument('--leakage-curve', default='simulated', choices=list(LEAKAGE_CURVES))
    ap.add_argument('--leakage-cal', default=os.path.join(_REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--core-other-policy', default=DEFAULT_CORE_OTHER_POLICY, choices=list(CORE_OTHER_POLICIES))
    add_rbb_argument(ap)
    ap.add_argument('--tol', type=float, default=0.5); ap.add_argument('--max-iter', type=int, default=40)
    ap.add_argument('--relax', type=float, default=0.5); ap.add_argument('--mr-iter', type=int, default=8)
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    args.trace_dir = resolve_trace_dir(args.trace_dir, args.core_other_policy)
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'burst'))
    os.makedirs(args.out_dir, exist_ok=True)

    n = args.cores
    flp = floorplan_path(args.flp_dir, args.node, n)
    area_m2 = chip_area_m2_from_floorplan(flp); area_mm2 = area_m2 * 1e6
    leak_model, t_ref = load_leakage_model(args.leakage_curve, calibration=args.leakage_cal, extrapolate=True)

    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    base = replicate_trace_cores(base0, n, n_src=args.trace_cores) if n > args.trace_cores else base0
    trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, args.density * area_mm2, num_cores=n)
    split = os.path.join(args.trace_dir, os.path.basename(files[0]).replace('block_powers_', 'block_powers_split_'))
    with open(split) as f:
        leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}
    trace, leak_ref, rbb_meta = amortize_rbb(trace, flp, policy=args.rbb_policy, leakage_ref=leak_ref,
                                             span=args.rbb_span, name_map=mcpat_flp_name_map(include_core_idx=(n > 1)))
    p_die = die_power_of_trace(trace, flp, args.tech_node, num_cores=n)
    fp = Floorplan.from_file(flp)
    geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6, 'min_dim_um': float(min(e.width, e.height))} for e in fp.elements}
    name_map = mcpat_flp_name_map(include_core_idx=(n > 1))

    n_pre, n_burst, n_post = (int(round(x / args.slot_ms)) for x in (args.pre_ms, args.burst_ms, args.post_ms))
    slot_s = args.slot_ms * 1e-3
    burst, leaks_t, mask = burst_trace(trace, leak_ref, args.burst_factor, n_pre, n_burst, n_post)
    burst = BasicPowerTrace(burst.powers, slot_s)
    print('burst absorption: {} cores, {:.2f} W/mm^2 = {:.1f} W steady; x{:.2f} dynamic for {:.0f} ms '
          '({} + {} + {} slots of {:.1f} ms)'.format(n, args.density, p_die, args.burst_factor, args.burst_ms,
                                                    n_pre, n_burst, n_post, args.slot_ms))

    rows = []
    for arm in args.arms:
        tag = '{}c_{}'.format(n, arm)
        spec = stack_spec(args, arm)
        sink = BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K)
        if args.spreading:
            sink = spreading_sink_for_stack(spec, sink, area_mm2, base_area_mm2=args.base_mm2)
        stack = render_stack_with_sink(get_stack_template(spec), sink, os.path.join(args.out_dir, 'stacks', tag + '.stk'))
        wiring = None
        if arm != 'control':
            wiring = wiring_for_stack(stack, flp, os.path.join(args.out_dir, tag), want_array=True,
                                      pitch_um=args.pitch_um, cell_um=args.cell_um, coverage=args.array_coverage)
        mr = MRParams(target_K=args.mr_target_C + 273.15, h_max=args.mr_h_max,
                      dt_max_K=(args.mr_dt_max if args.mr_dt_max is not None else DEFAULT_DT_MAX_K),
                      eta_asf=args.eta_asf, laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                      spot_min_um=DEFAULT_SPOT_MIN_UM, spot_policy=DEFAULT_SPOT_POLICY)

        # ---- steady baseline (and, for the array arms, the steady plans) -------------------
        cache = ICESessionCache()
        cnt = {'n': 0}; last = {}

        def steady_solve(tr, sub='steady'):
            cnt['n'] += 1
            solver = ICEThermalSolver(stack, flp, args.tech_node, run_base_dir=os.path.join(args.out_dir, tag, sub, 'it{:02d}'.format(cnt['n'])),
                                      initial_temp=args.ambient_K, num_cores=n, single_thread=True, mode='steady',
                                      session_cache=cache, **(wiring.solver_kwargs() if wiring else {}))
            r = run_leakage_feedback(tr, leak_ref, solver, model=leak_model, T_ref=t_ref, num_cores=n, tol_K=args.tol,
                                     max_iter=args.max_iter, relax=args.relax, t_floor_K=T_FLOOR_K, bridge_aggregates=True, verify=True)
            last['r'] = r
            return r['temp_trace']

        base_plan = {}
        if wiring is not None:
            # the steady baseline plan: whatever the planner needs to hold the target at the operating point
            res = run_mr_clipping(trace, steady_solve, geom, mr, name_map, max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                                  status_fn=lambda: {'diverged': bool(last.get('r', {}).get('diverged')),
                                                     'unconverged': bool(last.get('r', {}).get('unconverged'))},
                                  plan_mode='auto', die_power_W=p_die, **wiring.planner_kwargs())
            base_plan = dict(res.get('plan') or {})
            base_temps = res['temp_trace']; base_diverged = bool(res.get('temp_trace_diverged'))
        else:
            base_temps = steady_solve(trace); base_diverged = bool(last['r'].get('diverged'))
        if base_diverged:
            rows.append({'arm': arm, 'steady_diverged': True}); print('  {}: no steady state at the operating point'.format(arm)); continue
        base_peak = K_to_C(peak_temp_K(base_temps, t_floor_K=T_FLOOR_K))

        burst_plan = {}
        if arm == 'array_modulated':
            if args.modulation == 'feedforward':
                # remove the burst's own added dynamic watts at their source, block by block
                for u, v in trace.powers.items():
                    b = name_map(u)
                    if b is None or b not in geom:
                        continue
                    p = float(np.ravel(v)[0]); l = float(leak_ref.get(u, 0.0)) if u in leak_ref else 0.0
                    burst_plan[b] = burst_plan.get(b, 0.0) + (args.burst_factor - 1.0) * max(p - l, 0.0)
            else:
                hot = BasicPowerTrace({u: np.array([float(leak_ref.get(u, 0.0)) + args.burst_factor * max(float(np.ravel(v)[0]) - float(leak_ref.get(u, 0.0)), 0.0)]) for u, v in trace.powers.items()}, 1.0)
                res_b = run_mr_clipping(hot, lambda tr: steady_solve(tr, 'plan_burst'), geom, mr, name_map, max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                                        status_fn=lambda: {'diverged': bool(last.get('r', {}).get('diverged')), 'unconverged': bool(last.get('r', {}).get('unconverged'))},
                                        plan_mode='auto', die_power_W=die_power_of_trace(hot, flp, args.tech_node, num_cores=n), **wiring.planner_kwargs())
                burst_plan = dict(res_b.get('plan') or {})
        # ---- warm start: a one-shot steady sim with the baseline plan writes final.tstack -------
        if wiring is not None:
            wiring.set_mr_powers(tile_powers_for_stack(__import__('HotGauge.thermal.mr_array', fromlist=['project_plan_to_tiles']).project_plan_to_tiles(base_plan, wiring.blocks, wiring.tiles) if base_plan else {}, wiring.tiles))
        warm = ICEThermalSolver(stack, flp, args.tech_node, run_base_dir=os.path.join(args.out_dir, tag, 'warm'),
                                initial_temp=args.ambient_K, num_cores=n, single_thread=True, mode='steady',
                                **(wiring.solver_kwargs() if wiring else {}))
        r_warm = run_leakage_feedback(trace, leak_ref, warm, model=leak_model, T_ref=t_ref, num_cores=n, tol_K=args.tol,
                                      max_iter=args.max_iter, relax=args.relax, t_floor_K=T_FLOOR_K, bridge_aggregates=True, verify=False)
        tstack = os.path.join(args.out_dir, tag, 'warm', 'iter_{:03d}'.format(warm._iter - 1), 'final.tstack')
        if not os.path.isfile(tstack):
            raise SystemExit('warm-up wrote no final.tstack at {}'.format(tstack))
        warm_peak = K_to_C(peak_temp_K(r_warm['temp_trace'], t_floor_K=T_FLOOR_K))

        # ---- the transient ------------------------------------------------------------------
        n_slots = n_pre + n_burst + n_post
        mr_kw = {}
        if wiring is not None:
            plans = [dict(base_plan)] * n_pre + [dict(base_plan) if arm == 'array_static' else {**base_plan, **{b: base_plan.get(b, 0.0) + q for b, q in burst_plan.items()}}] * n_burst + [dict(base_plan)] * n_post
            sched = tile_power_schedule(plans, wiring.tiles, wiring.blocks)
            mr_kw = {'mr_flp_template': wiring.mr_flp_template, 'mr_powers': sched}
        tcnt = {'n': 0}

        def transient_solve(tr):
            tcnt['n'] += 1
            solver = ICEThermalSolver(stack, flp, args.tech_node, run_base_dir=os.path.join(args.out_dir, tag, 'transient', 'it{:02d}'.format(tcnt['n'])),
                                      initial_temp=(tstack, float(args.ambient_K)), num_cores=n, single_thread=True,
                                      mode='transient', steps_per_slot=args.steps_per_slot, **mr_kw)
            r = run_leakage_feedback(tr, leaks_t, solver, model=leak_model, T_ref=t_ref, num_cores=n, tol_K=args.tol,
                                     max_iter=args.max_iter, relax=args.relax, t_floor_K=T_FLOOR_K, bridge_aggregates=True, verify=True)
            last['t'] = r
            return r['temp_trace']

        temps = transient_solve(burst)
        rt = last['t']
        per_slot = []
        for i in range(n_slots):
            vals = [float(np.ravel(v)[i]) for v in temps.values() if np.size(v) > i and float(np.ravel(v)[i]) > T_FLOOR_K]
            per_slot.append(K_to_C(max(vals)) if vals else None)
        pk = [p for p in per_slot if p is not None]
        q_burst = float(sum(burst_plan.values())) if arm == 'array_modulated' else 0.0
        row = {'arm': arm, 'steady_diverged': False, 'steady_peak_C': base_peak, 'warm_peak_C': warm_peak,
               'base_plan_W': float(sum(base_plan.values())), 'burst_plan_W': q_burst,
               'burst_added_W': float(sum((args.burst_factor - 1.0) * max(float(np.ravel(v)[0]) - float(leak_ref.get(u, 0.0)), 0.0) for u, v in trace.powers.items() if name_map(u) in geom)),
               'laser_energy_J': q_burst / mr.cop * args.burst_ms * 1e-3 if q_burst else 0.0,
               'per_slot_peak_C': per_slot, 'peak_C': max(pk) if pk else None,
               'overshoot_K': (max(pk) - per_slot[0]) if pk and per_slot[0] is not None else None,
               'ms_above_target': args.slot_ms * sum(1 for p in pk if p > args.mr_target_C),
               'ms_above_spec': args.slot_ms * sum(1 for p in pk if p > args.spec_C),
               'diverged': bool(rt.get('diverged')), 'unconverged': bool(rt.get('unconverged')),
               'peak_spread_K': rt.get('peak_spread_K'), 'n_feedback_iter': rt.get('iterations')}
        rows.append(row)
        print('  {:<16s} steady {:.1f} C  peak {} C  overshoot {} K  >{:.0f}C {:.0f} ms  >{:.0f}C {:.0f} ms  burst plan {:.1f} W{}'.format(
            arm, base_peak, '--' if row['peak_C'] is None else '%.1f' % row['peak_C'],
            '--' if row['overshoot_K'] is None else '%.1f' % row['overshoot_K'], args.mr_target_C, row['ms_above_target'],
            args.spec_C, row['ms_above_spec'], q_burst, '  ** UNCONVERGED **' if row['unconverged'] else (' RUNAWAY' if row['diverged'] else '')))
    out = {'density': args.density, 'burst_factor': args.burst_factor, 'pre_ms': args.pre_ms, 'burst_ms': args.burst_ms, 'post_ms': args.post_ms,
           'slot_ms': args.slot_ms, 'steps_per_slot': args.steps_per_slot, 'modulation': args.modulation, 'cores': n, 'die_W': p_die,
           'target_C': args.mr_target_C, 'spec_C': args.spec_C, 'leakage_curve': args.leakage_curve, 'rbb_policy': args.rbb_policy, 'rows': rows}
    with open(os.path.join(args.out_dir, 'burst_absorption.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print('  written: {}'.format(os.path.join(args.out_dir, 'burst_absorption.json')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
