"""Acceptance test for the heatsink FMU.

  1. constant power must APPROACH AN ASYMPTOTE (a linear ramp means no heat is leaving)
  2. raising fan speed must LOWER the steady temperature
"""
import os, sys, json
import numpy as np
REPO = '/mnt/nfs01/scratch/jbalma/MXL-HotGauge'
sys.path.insert(0, os.path.join(REPO, 'HotGauge'))
from HotGauge.power import BasicPowerTrace
from HotGauge.configuration import load_block_powers
from HotGauge.thermal import get_stack_template, ICEThermalSolver
from HotGauge.thermal.utils import K_to_C

TOTAL_W, SLOT_S, N_SLOTS, SPS, T_FLOOR = 35.0, 1.0, 20, 100, 200.0
flp = os.path.join(REPO, 'examples/floorplans/outputs/skylake7nm_7core_3_3D-ICE_template.flp')
files = load_block_powers(os.path.join(REPO, 'mcpat_runs/7nm/linpack_3.8GHz'))
first = {u: float(np.ravel(v)[0]) for u, v in json.load(open(files[0])).items()}
scale = TOTAL_W / sum(max(p, 0.0) for p in first.values())

def run(rpm, tag):
    powers = {u: np.full(N_SLOTS, p * scale) for u, p in first.items()}
    tr = BasicPowerTrace(powers, SLOT_S)
    s = ICEThermalSolver(get_stack_template('skylake_HS483'), flp, 7,
                         run_base_dir='/mnt/nfs01/scratch/jbalma/mxl-nodelibs/accept_' + tag,
                         initial_temp=303.15, plugin_args=str(int(rpm)), num_cores=8,
                         single_thread=True, steps_per_slot=SPS, mode='transient')
    temps = s(tr)
    series = [np.asarray(v, float).ravel() for v in temps.values()
              if np.asarray(v, float).ravel().max() > T_FLOOR]
    traj = np.vstack(series).mean(axis=0)
    d = np.diff(traj)
    ratio = float(d[-1] / d[0]) if d.size > 1 and d[0] != 0 else float('nan')
    return traj, ratio

print('sim: {} slots x {} s = {} s at {} W\n'.format(N_SLOTS, SLOT_S, N_SLOTS*SLOT_S, TOTAL_W))
res = {}
for rpm in (0, 6000):
    traj, ratio = run(rpm, str(rpm))
    res[rpm] = (traj, ratio)
    print('fan {:4d} RPM: final {:7.2f} C | increment ratio last/first = {:.4f}  {}'.format(
        rpm, K_to_C(traj[-1]), ratio,
        'LINEAR RAMP - no heat leaving' if (np.isfinite(ratio) and ratio > 0.98) else 'decaying -> asymptote'))
    print('   trajectory [C]: ' + ' '.join('{:.1f}'.format(K_to_C(t)) for t in traj[::3]))

print('\n--- ACCEPTANCE ---')
t1, r1 = res[0]; t2, r2 = res[6000]
a = np.isfinite(r1) and r1 < 0.98 and np.isfinite(r2) and r2 < 0.98
b = t2[-1] < t1[-1]
print('  1. constant power asymptotes      : {}'.format('PASS' if a else 'FAIL'))
print('  2. more fan -> cooler             : {}  ({:.2f} C at 6000 vs {:.2f} C at 0, delta {:+.2f} K)'.format(
    'PASS' if b else 'FAIL', K_to_C(t2[-1]), K_to_C(t1[-1]), K_to_C(t2[-1]) - K_to_C(t1[-1])))
print('\n  => FMU {}'.format('WORKS' if (a and b) else 'STILL BROKEN'))
