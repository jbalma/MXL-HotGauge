#!/usr/bin/env python
"""Sweep cooling class x power regime with steady solves + leakage feedback.

This is the tool the architecture / power-regime studies actually run on. For each
(cooling solution, die power) pair it runs the full power<->temperature<->leakage fixed point
to a steady-state 3D-ICE solution and reports the converged temperatures and power.

Why it does not use the heatsink FMU
------------------------------------
The detailed FMU heatsinks cannot be steady-solved by 3D-ICE at all (``emulate_steady``
returns an error for pluggable sinks and the emulator then silently writes the *initial*
temperature -- see ``assert_steady_supported``), and the HS483 FMU additionally fails to
reject heat in this build (``examples/calibrate_sink_surrogate.py`` detects the straight-line
temperature ramp that proves it). So cooling here is expressed as a thermal resistance --
which is how coolers are specified on datasheets anyway -- via
``HotGauge.thermal.sink_models.ThermalResistanceSink``.

The R_th values are *modeling assumptions*, not measurements: every sink reports
``UNCALIBRATED`` until anchored to a validated reference. Treat the sweep as "how does this
architecture respond across cooling classes", not as a prediction for a specific product.

Example
-------
    python examples/steady_sink_sweep.py --powers 35 100 250 --r-th 1.0 0.3 0.05
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
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power,
                                               die_power_of_trace,
                                               load_calibrated_leakage_model,
                                               mcpat_tref_from_trace_dir)
from HotGauge.power.performance_model import FMaxModel, performance_summary
from HotGauge.thermal.sink_models import (ThermalResistanceSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan)
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0

#: Rough guide only -- orders of magnitude, not product specs.
COOLING_CLASSES = [
    (1.0,  'desktop air (modest)'),
    (0.3,  'high-end air / AIO'),
    (0.05, 'server liquid loop'),
]


def die_stats(temps):
    vals = []
    for series in temps.values():
        arr = np.asarray(series, dtype=float).ravel()
        arr = arr[arr > T_FLOOR_K]
        if arr.size:
            vals.append(arr[-1])
    vals = np.asarray(vals, dtype=float)
    if vals.size == 0:
        raise RuntimeError('No die blocks above {} K'.format(T_FLOOR_K))
    return {'mean': float(vals.mean()), 'peak': float(vals.max()), 'std': float(vals.std())}


def scaled_trace(trace_dir, total_power_W, flp_template, tech_node, num_cores=8,
                 n_steps=1, slot_s=1.0):
    """Scale so the DIE dissipates total_power_W.

    Normalising by the raw sum of McPAT entries would be wrong: that sum includes hierarchy
    aggregates which restate their children, and excludes the IMC/IO/SoC units HotGauge adds.
    scale_trace_to_die_power() measures what actually reaches 3D-ICE (+5.2 % vs the raw sum on
    this trace) so a run labelled "50 W" really is 50 W on the die.
    """
    files = load_block_powers(trace_dir)
    if not files:
        raise RuntimeError('No block_powers_*.json in {}'.format(trace_dir))
    with open(files[0]) as f:
        first = {u: float(np.asarray(v, dtype=float).ravel()[0]) for u, v in json.load(f).items()}
    base = BasicPowerTrace({u: np.full(n_steps, p) for u, p in first.items()}, slot_s)
    scaled, scale, die_W = scale_trace_to_die_power(base, flp_template, tech_node,
                                                    total_power_W, num_cores=num_cores)
    leak_frac = {}
    split = os.path.join(trace_dir, os.path.basename(files[0]).replace('block_powers_',
                                                                       'block_powers_split_'))
    if os.path.isfile(split):
        with open(split) as f:
            sp = json.load(f)
        leak_frac = {u: float(v[1]) * scale for u, v in sp.items()}
    return scaled, leak_frac, die_W


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trace-dir', default=None)
    ap.add_argument('--flp-template', default=None)
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--num-cores', type=int, default=8)
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--powers', type=float, nargs='+', default=[35.0, 100.0, 250.0],
                    help='total die power levels [W]')
    ap.add_argument('--r-th', type=float, nargs='+', default=None,
                    help='cooling thermal resistances [K/W]; default = the built-in classes')
    ap.add_argument('--ambient-K', type=float, default=303.15)
    ap.add_argument('--t-ref', type=float, default=360.0)
    ap.add_argument('--doubling', type=float, default=15.0)
    ap.add_argument('--tol', type=float, default=0.5)
    # See docs/GAMEPLAN.md P0.1: relax is a STARTING point (the loop backtracks and tightens
    # it per point), convergence is tested on the fixed-point residual, and every solve is
    # repeated at half the damping to prove the answer does not depend on the knob.
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--no-verify', action='store_true',
                    help='skip the half-damping verification solve; faster, unsafe to quote')
    ap.add_argument('--verify-tol', type=float, default=1.0,
                    help='peak-temperature agreement [K] required between damping levels')
    ap.add_argument('--leak-fraction', type=float, default=0.2,
                    help='fallback leakage fraction if no split files are present')
    ap.add_argument('--leakage-cal', default=None,
                    help='leakage_calibration.json from examples/calibrate_leakage_model.py. '
                         'Uses the MEASURED McPAT leakage curve (from_table) and its true '
                         'T_ref instead of the assumed exponential/T_ref.')
    ap.add_argument('--f-nominal', type=float, default=4.0, help='nominal core clock [GHz]')
    ap.add_argument('--derate-per-K', type=float, default=0.001,
                    help='fractional f_max loss per K (UNCALIBRATED assumption)')
    ap.add_argument('--throttle-C', type=float, default=100.0, help='throttle trip point [C]')
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()

    args.flp_template = args.flp_template or os.path.join(
        _HERE, 'floorplans', 'outputs',
        'skylake{}nm_7core_3_3D-ICE_template.flp'.format(args.tech_node))
    args.trace_dir = args.trace_dir or os.path.join(
        _HERE, 'ICE_simulation_from_MCPAT', 'traces', 'example_workload',
        '{}nm'.format(args.tech_node))
    args.out_dir = args.out_dir or os.path.join(os.getcwd(), 'steady_sink_sweep')
    os.makedirs(args.out_dir, exist_ok=True)

    if args.r_th:
        classes = [(r, 'R_th={:.3g} K/W'.format(r)) for r in args.r_th]
    else:
        classes = COOLING_CLASSES

    area_m2 = chip_area_m2_from_floorplan(args.flp_template)
    base_stack = get_stack_template(args.stack)

    # Leakage model: measured curve if we have one, otherwise the assumed exponential.
    # T_ref is read from the trace's own McPAT XML whenever possible -- it must never be
    # guessed (a 30 K anchor error is ~4x in leakage, biased optimistic).
    if args.leakage_cal:
        model, t_ref = load_calibrated_leakage_model(args.leakage_cal)
        leak_src = 'MEASURED McPAT curve ({})'.format(os.path.basename(args.leakage_cal))
    else:
        model = LeakageModel.exponential(args.doubling)
        detected = mcpat_tref_from_trace_dir(args.trace_dir)
        t_ref = detected if detected is not None else args.t_ref
        leak_src = 'assumed exponential (doubling {:.1f} K)'.format(args.doubling)
    detected = mcpat_tref_from_trace_dir(args.trace_dir)
    t_ref_note = ('from trace XML' if detected is not None
                  else 'NO XML in trace dir -- using --t-ref, verify it')

    fmax_model = FMaxModel.linear_derate(args.derate_per_K)
    throttle_K = args.throttle_C + 273.15

    print('steady sink sweep')
    print('  floorplan : {}  ({:.4g} mm^2)'.format(os.path.basename(args.flp_template),
                                                   area_m2 * 1e6))
    print('  stack     : {} (conventional sink -- steady-solvable)'.format(
        os.path.basename(base_stack)))
    print('  ambient   : {:.2f} K'.format(args.ambient_K))
    print('  leakage   : {}'.format(leak_src))
    print('  T_ref     : {:.1f} K ({:.1f} C)  [{}]'.format(t_ref, t_ref - 273.15, t_ref_note))
    print('  perf      : f_nom {:.2f} GHz, derate {:.4g}/K, throttle at {:.0f} C  '
          '[{}]'.format(args.f_nominal, args.derate_per_K, args.throttle_C,
                        'calibrated' if fmax_model.calibrated else 'UNCALIBRATED'))
    print('\n  NOTE: R_th values are modeling assumptions, cooling parasitic power is NOT '
          'modelled\n  (so perf/W counts compute power only), and the f_max derating is an '
          'assumed slope.\n')

    header = ('{:<22s} {:>7s} {:>8s} {:>9s} {:>9s} {:>8s} {:>8s} {:>7s} {:>5s}'
              .format('cooling', 'P_in[W]', 'W/mm^2', 'peak[C]', 'P_out[W]', 'f[GHz]',
                      'rel_perf', 'GHz/W', 'iters'))
    print(header)
    print('-' * len(header))

    rows = []
    for r_th, label in classes:
        for p_w in args.powers:
            trace, leak_ref, raw = scaled_trace(args.trace_dir, p_w,
                                               args.flp_template, args.tech_node,
                                               num_cores=args.num_cores)
            if not leak_ref:
                leak_ref = {u: args.leak_fraction * max(float(s[0]), 0.0)
                            for u, s in trace.powers.items()}
            sink = ThermalResistanceSink(r_th, area_m2, ambient_K=args.ambient_K, label=label)
            tag = 'rth{:g}_P{:g}'.format(r_th, p_w)
            stack = render_stack_with_sink(base_stack, sink,
                                           os.path.join(args.out_dir, 'stacks', tag + '.stk'))
            solver = ICEThermalSolver(stack, args.flp_template, args.tech_node,
                                      run_base_dir=os.path.join(args.out_dir, tag),
                                      initial_temp=args.ambient_K, num_cores=args.num_cores,
                                      single_thread=True, mode='steady')
            res = run_leakage_feedback(trace, leak_ref, solver, model=model, T_ref=t_ref,
                                       num_cores=args.num_cores, tol_K=args.tol,
                                       max_iter=args.max_iter, relax=args.relax,
                                       t_floor_K=T_FLOOR_K,
                                       bridge_aggregates=True,
                                       verify=not args.no_verify,
                                       verify_tol_K=args.verify_tol)
            stats = die_stats(res['temp_trace'])
            # die_power_of_trace, not a raw sum -- the aggregates double-count (~2.36x).
            p_out = die_power_of_trace(res['power_trace'], args.flp_template, args.tech_node,
                                       num_cores=args.num_cores)
            diverged = bool(res.get('diverged'))
            unconverged = bool(res.get('unconverged'))
            status = ('DIVERGED' if diverged else
                      'UNVERIFIED' if unconverged else
                      'conv' if res['converged'] else 'maxit')
            density = p_w / (area_m2 * 1e6)
            if diverged:
                # The last state before a runaway guard fires is mid-divergence: its
                # temperatures and powers are not a solution and must not be tabulated as one.
                print('{:<22s} {:>7.1f} {:>8.2f} {:>9s} {:>9s} {:>8s} {:>8s} {:>7s} {:>4d} {}'
                      .format(label[:22], p_w, density, '--', '--', '--', '--', '--',
                              res['iterations'], status))
                perf = None
            else:
                perf = performance_summary(
                    [np.asarray(v, float).ravel()[-1] for v in res['temp_trace'].values()],
                    fmax_model, f_nominal_GHz=args.f_nominal, compute_power_W=p_out,
                    throttle_K=throttle_K, t_floor_K=T_FLOOR_K)
                print('{:<22s} {:>7.1f} {:>8.2f} {:>9.2f} {:>9.2f} {:>8.3f} {:>8.3f} {:>7.4f} '
                      '{:>4d} {}{}'.format(
                          label[:22], p_w, density, K_to_C(stats['peak']), p_out,
                          perf['f_effective_GHz'], perf['rel_perf'], perf['perf_per_W'],
                          res['iterations'], status,
                          ' THROTTLED' if perf['throttling'] else ''))
            rows.append({'r_th': r_th, 'label': label, 'power_in_W': p_w,
                         'power_density_W_per_mm2': density,
                         'peak_C': None if diverged else K_to_C(stats['peak']),
                         'mean_C': None if diverged else K_to_C(stats['mean']),
                         'power_out_W': None if diverged else p_out,
                         'performance': perf,
                         'iterations': res['iterations'],
                         'converged': bool(res['converged']), 'diverged': diverged,
                         'unconverged': unconverged,
                         'peak_spread_K': res.get('peak_spread_K'),
                         'relax_final': res.get('relax_final')})

    out = os.path.join(args.out_dir, 'sweep.json')
    with open(out, 'w') as f:
        json.dump({'area_m2': area_m2, 'ambient_K': args.ambient_K, 'rows': rows}, f, indent=2)
    print('\n  written: {}'.format(out))
    print('  dP[%] > 0 means blocks ran ABOVE T_ref so leakage grew; < 0 means cooling '
          'clawed static power back.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
