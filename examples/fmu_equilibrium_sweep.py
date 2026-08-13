"""Drive the (now working) HS483 FMU to thermal equilibrium at several fan speeds.

Purpose
-------
1. Confirm the repaired FMU actually settles rather than merely decaying slowly.
2. Extract R_th(fan speed) = (T_die - T_air) / Q, which is exactly the calibration
   PumpedSink needs and which the broken FMU could never provide.

Cost: the co-simulation is only stable at dt <= 0.01 s (see PROJECT_STATUS), so this is
~0.24 s wall per step. One fan speed at 150 s simulated is ~15000 steps ~ 1 hour. Fan speeds
are therefore run as separate processes in parallel -- each 3D-ICE is single threaded.

Usage:  python examples/fmu_equilibrium_sweep.py --fan-rpm 6000 --sim-s 150
"""
import os, sys, json, argparse, time
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace
from HotGauge.configuration import load_block_powers
from HotGauge.thermal import get_stack_template, ICEThermalSolver
from HotGauge.thermal.leakage_feedback import die_block_temps
from HotGauge.thermal.utils import K_to_C

T_FLOOR = 200.0

ap = argparse.ArgumentParser()
ap.add_argument('--fan-rpm', type=float, required=True)
ap.add_argument('--total-power', type=float, default=35.0, help='<=40 W: FMU validity limit')
ap.add_argument('--sim-s', type=float, default=150.0)
ap.add_argument('--dt', type=float, default=0.01, help='must be <= 0.01 for stability')
ap.add_argument('--slot-s', type=float, default=1.0)
ap.add_argument('--air-K', type=float, default=303.15)
ap.add_argument('--out-dir', default=None)
args = ap.parse_args()

sps = int(round(args.slot_s / args.dt))
n_slots = int(round(args.sim_s / args.slot_s))
flp = os.path.join(_HERE, 'floorplans', 'outputs', 'skylake7nm_7core_3_3D-ICE_template.flp')
files = load_block_powers(os.path.join(_REPO, 'mcpat_runs/7nm/linpack_3.8GHz'))
first = {u: float(np.ravel(v)[0]) for u, v in json.load(open(files[0])).items()}
scale = args.total_power / sum(max(p, 0.0) for p in first.values())
out_dir = args.out_dir or os.path.join(os.getcwd(), 'fmu_equilibrium',
                                       'rpm{:.0f}'.format(args.fan_rpm))

print('FMU equilibrium: fan {:.0f} RPM, {:.1f} W, {:.0f} s at dt={:g} s ({} steps)'.format(
    args.fan_rpm, args.total_power, args.sim_s, args.dt, n_slots * sps), flush=True)

trace = BasicPowerTrace({u: np.full(n_slots, p * scale) for u, p in first.items()}, args.slot_s)
t0 = time.time()
temps = ICEThermalSolver(get_stack_template('skylake_HS483'), flp, 7, run_base_dir=out_dir,
                         initial_temp=args.air_K, plugin_args=str(int(args.fan_rpm)),
                         num_cores=8, single_thread=True, steps_per_slot=sps,
                         mode='transient')(trace)
wall = time.time() - t0

# die_block_temps drops the Tflp 'Time' column -- for runs longer than 200 s the clock
# otherwise reads as the hottest block on the die (a 400 s run reported a 400 K peak).
temps = die_block_temps(temps)
series = [np.asarray(v, float).ravel() for v in temps.values()
          if np.asarray(v, float).ravel().max() > T_FLOOR]
mean_traj = np.vstack(series).mean(axis=0)
peak_traj = np.vstack(series).max(axis=0)
d = np.diff(mean_traj)
# Settled if the last slot moves <1% as much as the first -- i.e. the exponential is spent.
ratio = float(d[-1] / d[0]) if d.size > 1 and d[0] != 0 else float('nan')
last_delta = float(abs(d[-1])) if d.size else float('nan')
r_th = (mean_traj[-1] - args.air_K) / args.total_power
r_th_peak = (peak_traj[-1] - args.air_K) / args.total_power

print('  wall {:.1f} min'.format(wall / 60.0), flush=True)
print('  final mean {:.3f} C   peak {:.3f} C'.format(K_to_C(mean_traj[-1]), K_to_C(peak_traj[-1])))
print('  last-slot movement {:.5f} K   increment ratio {:.5f}'.format(last_delta, ratio))
print('  SETTLED: {}'.format('yes' if last_delta < 0.01 else 'NO - run longer'))
print('  R_th(mean) {:.4f} K/W   R_th(peak) {:.4f} K/W  [vs air at {:.2f} K]'.format(
    r_th, r_th_peak, args.air_K))
print('  trajectory [C]: ' + ' '.join('{:.2f}'.format(K_to_C(t))
                                      for t in mean_traj[::max(1, len(mean_traj)//15)]))
with open(os.path.join(out_dir, 'equilibrium.json'), 'w') as f:
    json.dump({'fan_rpm': args.fan_rpm, 'total_power_W': args.total_power,
               'air_K': args.air_K, 'dt_s': args.dt, 'sim_s': args.sim_s,
               'final_mean_K': float(mean_traj[-1]), 'final_peak_K': float(peak_traj[-1]),
               'last_delta_K': last_delta, 'increment_ratio': ratio,
               'settled': bool(last_delta < 0.01),
               'r_th_mean_K_per_W': float(r_th), 'r_th_peak_K_per_W': float(r_th_peak),
               'mean_trajectory_K': [float(x) for x in mean_traj],
               'wall_s': wall}, f, indent=2)
print('  written: {}/equilibrium.json'.format(out_dir))
