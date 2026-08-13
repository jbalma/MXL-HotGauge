#!/usr/bin/env python
"""Calibrate and validate the lumped sink surrogate against the real HS483 heatsink FMU.

The question this answers
-------------------------
3D-ICE can run the detailed fan/heatsink FMU, but only in *transient* mode, and reaching
thermal equilibrium takes minutes of simulated time per evaluation -- far too slow for the
architecture / power-regime sweeps we actually want. The cheap alternative is a conventional
``top heat sink`` (one heat transfer coefficient), which IS steady-solvable, but which
collapses spreader + sink + fan into a single number at the die's top face.

So: **how much accuracy does that collapse cost?**

Procedure
---------
1. Run the FMU stack (``skylake_HS483``) as a long constant-power transient until the die
   temperature stops moving. That equilibrium is the reference.
2. Bisect the conventional stack's heat transfer coefficient until its *steady* solve
   reproduces the reference mean die temperature. The resulting ``h*`` absorbs both the sink
   and the structural difference between the stacks (the FMU stack carries a 30 mm copper
   spreader that the conventional stack has no way to represent).
3. Report the residual on metrics that were NOT calibrated on -- peak block temperature and
   the per-block spread. That residual is the honest cost of the lumped approximation, and it
   is the number to quote before trusting the surrogate for a new power map.

Calibrating on the mean and scoring on the peak is deliberate: a surrogate tuned to match
every metric it is judged by proves nothing.

Power level
-----------
The HS483 Modelica model documents itself as valid only below **40 W** (above that the air
film approaches the fin half-spacing and it leaves its fitted regime). Default target power
is therefore 35 W, inside that envelope, so the *reference* is trustworthy. Our real 7nm
linpack trace is ~49 W and server parts are 300-700 W -- which is exactly why the
parameterized ``ThermalResistanceSink`` exists rather than an FMU per cooling class.

Example
-------
    python examples/calibrate_sink_surrogate.py --fan-rpm 6000 --total-power 35
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
from HotGauge.thermal import get_stack_template, ICEThermalSolver
from HotGauge.thermal.sink_models import (ConstantHTCSink, HS483AirSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan, fit_area_ratio,
                                          htc_3dice_to_si)
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0      # 3D-ICE reports 0 K for floorplan elements outside the die layer


def _hr(title):
    print('\n' + '=' * 72 + '\n{}\n'.format(title) + '=' * 72)


def die_stats(temps):
    """Mean / peak / spread over real die blocks (ignoring the 0 K out-of-die entries)."""
    vals = []
    for series in temps.values():
        arr = np.asarray(series, dtype=float).ravel()
        arr = arr[arr > T_FLOOR_K]
        if arr.size:
            vals.append(arr[-1])          # last timestep = closest to equilibrium
    vals = np.asarray(vals, dtype=float)
    if vals.size == 0:
        raise RuntimeError('No die blocks above the {} K floor -- solve produced nothing '
                           'usable.'.format(T_FLOOR_K))
    return {'mean': float(vals.mean()), 'peak': float(vals.max()),
            'min': float(vals.min()), 'std': float(vals.std()), 'n_blocks': int(vals.size)}


def build_constant_trace(trace_dir, total_power_W, n_slots, slot_s):
    """A constant-in-time McPAT-named trace whose per-step total is ``total_power_W``.

    Uses the first timestep's spatial power distribution (so the hotspot pattern is realistic)
    scaled to the requested total, then held constant for ``n_slots`` slots.
    """
    # load_block_powers returns the ordered list of block_powers_<tick>.json paths.
    files = load_block_powers(trace_dir)
    if not files:
        raise RuntimeError('No block_powers_*.json in {}'.format(trace_dir))
    with open(files[0]) as f:
        first = {u: float(np.asarray(v, dtype=float).ravel()[0]) for u, v in json.load(f).items()}
    raw_total = sum(max(p, 0.0) for p in first.values())
    if raw_total <= 0:
        raise RuntimeError('Trace {} has non-positive total power'.format(trace_dir))
    scale = float(total_power_W) / raw_total
    powers = {u: np.full(n_slots, p * scale) for u, p in first.items()}
    return BasicPowerTrace(powers, slot_s), raw_total, scale


def equilibrium_report(temps, n_tail=5):
    """How much the die is still moving over the last few slots -- did we actually settle?"""
    series = []
    for v in temps.values():
        arr = np.asarray(v, dtype=float).ravel()
        if arr.size and arr.max() > T_FLOOR_K:
            series.append(arr)
    if not series:
        return None
    stacked = np.vstack(series)              # blocks x timesteps
    per_step_mean = stacked.mean(axis=0)
    if per_step_mean.size < 2:
        return None
    tail = per_step_mean[-min(n_tail, per_step_mean.size):]
    # A working sink makes temperature approach an asymptote, so successive increments
    # SHRINK. If they stay equal, the assembly is just absorbing energy into its heat
    # capacity and (near-)nothing is reaching the air -- a broken/adiabatic sink, not a
    # slow one. Distinguishing those two is the difference between "run longer" and
    # "the heatsink model is wrong".
    incr = np.diff(per_step_mean)
    incr_ratio = float(incr[-1] / incr[0]) if incr.size > 1 and incr[0] != 0 else float('nan')
    return {'drift_K_over_tail': float(abs(tail[-1] - tail[0])),
            'last_step_delta_K': float(abs(per_step_mean[-1] - per_step_mean[-2])),
            'increment_ratio': incr_ratio,
            'linear_ramp': bool(np.isfinite(incr_ratio) and incr_ratio > 0.98),
            'trajectory_C': [float(K_to_C(t)) for t in per_step_mean[::max(1, len(per_step_mean)//8)]]}


def run_fmu_reference(args, trace, flp):
    _hr('STEP 1 - FMU reference: long constant-power transient to equilibrium')
    stack = get_stack_template(args.fmu_stack)
    print('  stack      : {}'.format(os.path.basename(stack)))
    print('  fan        : {:.0f} RPM'.format(args.fan_rpm))
    print('  power      : {:.2f} W  (HS483 validated below {:.0f} W: {})'.format(
        args.total_power, HS483AirSink.MAX_VALIDATED_POWER_W,
        'OK' if args.total_power <= HS483AirSink.MAX_VALIDATED_POWER_W else 'OUTSIDE ENVELOPE'))
    print('  sim time   : {} slots x {} s = {} s (step {} s)'.format(
        args.n_slots, args.slot_s, args.n_slots * args.slot_s,
        args.slot_s / args.steps_per_slot))

    solver = ICEThermalSolver(stack, flp, args.tech_node,
                              run_base_dir=os.path.join(args.out_dir, 'fmu_reference'),
                              initial_temp=args.ambient_K, plugin_args=str(int(args.fan_rpm)),
                              num_cores=args.num_cores, single_thread=True,
                              steps_per_slot=args.steps_per_slot, mode='transient')
    temps = solver(trace)
    stats = die_stats(temps)
    eq = equilibrium_report(temps)
    print('  reference die temps: mean {:.2f} C | peak {:.2f} C | spread(std) {:.2f} K '
          '| {} blocks'.format(K_to_C(stats['mean']), K_to_C(stats['peak']), stats['std'],
                               stats['n_blocks']))
    if eq:
        print('  equilibrium check  : drift over last slots {:.4f} K, last step {:.4f} K'.format(
            eq['drift_K_over_tail'], eq['last_step_delta_K']))
        print('  trajectory [C]     : {}'.format(
            ', '.join('{:.2f}'.format(t) for t in eq['trajectory_C'])))
        if eq['linear_ramp']:
            print('  *** SINK IS REJECTING NO HEAT: successive temperature increments are '
                  'constant (ratio {:.4f} ~ 1.0), i.e. a straight-line ramp. At constant '
                  'power a working heatsink must approach an asymptote. Running longer will '
                  'NOT help -- the FMU co-simulation is not removing heat. Verify the FMU '
                  'build before trusting any number from it. ***'.format(eq['increment_ratio']))
        elif eq['drift_K_over_tail'] > args.equilibrium_tol_K:
            print('  *** NOT AT EQUILIBRIUM: drift {:.3f} K > tol {:.3f} K. Increase --n-slots '
                  'or --slot-s; the calibration below is against a still-warming '
                  'reference. ***'.format(eq['drift_K_over_tail'], args.equilibrium_tol_K))
    return stats, eq


def steady_mean_for_htc(h_si, args, trace, flp, tag):
    """One steady solve of the conventional stack at heat transfer coefficient ``h_si``."""
    sink = ConstantHTCSink(h_si, ambient_K=args.ambient_K, label='probe')
    rendered = render_stack_with_sink(
        get_stack_template(args.conv_stack), sink,
        os.path.join(args.out_dir, 'rendered', 'stack_{}.stk'.format(tag)))
    solver = ICEThermalSolver(rendered, flp, args.tech_node,
                              run_base_dir=os.path.join(args.out_dir, 'steady', tag),
                              initial_temp=args.ambient_K, plugin_args=None,
                              num_cores=args.num_cores, single_thread=True, mode='steady')
    return die_stats(solver(trace))


def calibrate(args, trace, flp, target_mean_K):
    """Bisect the conventional stack's HTC until its steady mean die temp matches the FMU."""
    _hr('STEP 2 - calibrate conventional-stack HTC against the FMU reference')
    lo, hi = args.htc_lo, args.htc_hi

    # Higher h => better cooling => lower temperature, so the bracket is monotone decreasing.
    stats_lo = steady_mean_for_htc(lo, args, trace, flp, 'lo')
    stats_hi = steady_mean_for_htc(hi, args, trace, flp, 'hi')
    print('  bracket: h={:.4g} -> mean {:.2f} C | h={:.4g} -> mean {:.2f} C | target {:.2f} C'
          .format(lo, K_to_C(stats_lo['mean']), hi, K_to_C(stats_hi['mean']),
                  K_to_C(target_mean_K)))
    if not (stats_hi['mean'] <= target_mean_K <= stats_lo['mean']):
        print('  *** Target mean temperature is OUTSIDE the bracket -- no HTC in '
              '[{:.4g}, {:.4g}] W/(m^2 K) reproduces the FMU. Widen --htc-lo/--htc-hi. '
              'This is a real result, not just a search failure: it would mean the '
              'conventional stack cannot represent this sink at all. ***'.format(lo, hi))
        return None, [stats_lo, stats_hi]

    history = []
    for i in range(args.max_bisect):
        mid = np.sqrt(lo * hi)          # geometric: h spans orders of magnitude
        stats = steady_mean_for_htc(mid, args, trace, flp, 'bisect{:02d}'.format(i))
        err = K_to_C(stats['mean']) - K_to_C(target_mean_K)
        history.append({'h_si': float(mid), 'mean_C': K_to_C(stats['mean']),
                        'peak_C': K_to_C(stats['peak']), 'err_K': float(err)})
        print('    iter {:2d}: h={:.5g} W/(m^2 K) -> mean {:.3f} C (err {:+.3f} K)'.format(
            i, mid, K_to_C(stats['mean']), err))
        if abs(err) <= args.calib_tol_K:
            return {'h_si': float(mid), 'stats': stats, 'iters': i + 1}, history
        if stats['mean'] > target_mean_K:
            lo = mid                     # too hot -> need more cooling -> larger h
        else:
            hi = mid
    print('  *** did not converge within {} iterations ***'.format(args.max_bisect))
    return None, history


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trace-dir', default=None, help='defaults to shipped example_workload/7nm')
    ap.add_argument('--flp-template', default=None)
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--num-cores', type=int, default=8)
    ap.add_argument('--fmu-stack', default='skylake_HS483')
    ap.add_argument('--conv-stack', default='skylake')
    ap.add_argument('--fan-rpm', type=float, default=6000.0)
    ap.add_argument('--total-power', type=float, default=35.0,
                    help='total die power [W]; default 35 keeps the FMU inside its <40 W '
                         'validated envelope')
    ap.add_argument('--ambient-K', type=float, default=303.15)
    ap.add_argument('--slot-s', type=float, default=5.0, help='transient slot length [s]')
    ap.add_argument('--n-slots', type=int, default=100, help='number of slots (total sim time)')
    ap.add_argument('--steps-per-slot', type=int, default=10)
    ap.add_argument('--equilibrium-tol-K', type=float, default=0.05)
    ap.add_argument('--calib-tol-K', type=float, default=0.05)
    ap.add_argument('--max-bisect', type=int, default=14)
    ap.add_argument('--htc-lo', type=float, default=1.0e3, help='HTC bracket low [W/(m^2 K)]')
    ap.add_argument('--htc-hi', type=float, default=1.0e7, help='HTC bracket high [W/(m^2 K)]')
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--skip-fmu', type=float, default=None,
                    help='skip step 1 and calibrate against this reference mean die temp [C] '
                         '(for re-running the cheap half without redoing the long FMU run)')
    args = ap.parse_args()

    args.flp_template = args.flp_template or os.path.join(
        _HERE, 'floorplans', 'outputs',
        'skylake{}nm_7core_3_3D-ICE_template.flp'.format(args.tech_node))
    args.trace_dir = args.trace_dir or os.path.join(
        _HERE, 'ICE_simulation_from_MCPAT', 'traces', 'example_workload',
        '{}nm'.format(args.tech_node))
    args.out_dir = args.out_dir or os.path.join(os.getcwd(), 'sink_calibration',
                                                'rpm{:.0f}_P{:.0f}'.format(args.fan_rpm,
                                                                           args.total_power))
    os.makedirs(args.out_dir, exist_ok=True)

    area_m2 = chip_area_m2_from_floorplan(args.flp_template)
    print('sink surrogate calibration')
    print('  floorplan  : {}'.format(os.path.basename(args.flp_template)))
    print('  chip area  : {:.4g} mm^2  (the area the HTC is referenced to)'.format(area_m2 * 1e6))
    print('  outputs    : {}'.format(args.out_dir))

    trace, raw_total, scale = build_constant_trace(args.trace_dir, args.total_power,
                                                   args.n_slots, args.slot_s)
    print('  trace      : {} units, scaled x{:.4f} from {:.2f} W to {:.2f} W/step'.format(
        len(trace.powers), scale, raw_total, args.total_power))

    if args.skip_fmu is not None:
        from HotGauge.thermal.utils import C_to_K
        ref = {'mean': C_to_K(args.skip_fmu), 'peak': float('nan'), 'std': float('nan')}
        eq = None
        print('\n  (skipping FMU run; using supplied reference mean {:.2f} C)'.format(
            args.skip_fmu))
    else:
        ref, eq = run_fmu_reference(args, trace, args.flp_template)

    result, history = calibrate(args, trace, args.flp_template, ref['mean'])

    _hr('STEP 3 - result and the cost of the lumped approximation')
    summary = {'fan_rpm': args.fan_rpm, 'total_power_W': args.total_power,
               'chip_area_m2': area_m2, 'ambient_K': args.ambient_K,
               'reference': {k: (None if isinstance(v, float) and np.isnan(v) else v)
                             for k, v in ref.items()},
               'equilibrium': eq, 'history': history}
    if result is None:
        print('  CALIBRATION FAILED - see messages above. No surrogate coefficient produced.')
        summary['calibrated'] = False
    else:
        h = result['h_si']
        r_th = 1.0 / (h * area_m2)
        ratio = fit_area_ratio(h, args.fan_rpm, strict=False)
        print('  calibrated h   : {:.5g} W/(m^2 K)   ({:.5g} W/(um^2 K) for the .stk)'.format(
            h, h / 1.0e12))
        print('  implied R_th   : {:.4g} K/W over {:.4g} mm^2'.format(r_th, area_m2 * 1e6))
        print('  HS483AirSink   : area_ratio = {:.5g} at {:.0f} RPM'.format(ratio, args.fan_rpm))
        print('  converged in   : {} bisection steps'.format(result['iters']))
        if not np.isnan(ref['peak']):
            peak_err = K_to_C(result['stats']['peak']) - K_to_C(ref['peak'])
            print('\n  --- fidelity on metrics NOT calibrated against ---')
            print('  peak block temp: surrogate {:.2f} C vs FMU {:.2f} C  -> error {:+.2f} K'
                  .format(K_to_C(result['stats']['peak']), K_to_C(ref['peak']), peak_err))
            print('  block spread   : surrogate std {:.2f} K vs FMU std {:.2f} K'.format(
                result['stats']['std'], ref['std']))
            print('\n  Interpretation: the surrogate is tuned to the MEAN, so the peak error is'
                  '\n  the price of collapsing the spreader into one coefficient. Quote it as'
                  '\n  the surrogate uncertainty; re-calibrate if the power map changes shape.')
            summary['peak_error_K'] = float(peak_err)
        summary['calibrated'] = True
        summary['h_si'] = h
        summary['r_th_K_per_W'] = r_th
        summary['area_ratio'] = ratio

    out_json = os.path.join(args.out_dir, 'calibration.json')
    with open(out_json, 'w') as f:
        json.dump(summary, f, indent=2)
    print('\n  written: {}'.format(out_json))
    return 0 if summary.get('calibrated') else 1


if __name__ == '__main__':
    sys.exit(main())
