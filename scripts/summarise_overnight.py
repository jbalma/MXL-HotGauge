#!/usr/bin/env python
"""Roll the overnight2 study up into one table per phase.

**These results are VOID at and above ~1.05 W/mm^2.** The convergence test they passed measured
the change between successive solves, which scales with the damping, so points near the leakage
instability are truncations of diverging trajectories rather than solutions. Superseded by
``scripts/summarise_overnight3.py`` on ``results/overnight3``. This script is kept to read the
historical run and prints the warning on every invocation, so a stale table cannot be mistaken
for a current one. Full account: docs/CONVERGENCE.md.

Reads every ``results/overnight2/*/mr_comparison.json`` and pairs the MR-off and MR-on rows for
each point. Points that produced no JSON are listed as incomplete rather than skipped silently,
so a partial night is visible as a partial night.
"""
import os
import re
import glob
import json

OUT = '/mnt/nfs01/scratch/jbalma/MXL-HotGauge/results/overnight2'

#: Below this the trajectory really does flatten and these numbers stand (cross-checked at
#: 1.00 W/mm^2: 89.165 C here against 89.186 C from the verified path). At and above it they
#: do not.
VOID_ABOVE_W_PER_MM2 = 1.05

print('*' * 100)
print('WARNING: this study is VOID at and above ~{:.2f} W/mm^2.'.format(VOID_ABOVE_W_PER_MM2))
print('Its convergence test measured the change between successive solves, which scales with')
print('relax -- so tightening the damping made the tolerance weaker. At 1.15 W/mm^2 it stopped')
print('on iteration 2 reporting 101.09 C; that trajectory reaches 1092 C by iteration 52.')
print('Superseded by results/overnight3 (scripts/summarise_overnight3.py). docs/CONVERGENCE.md.')
print('*' * 100)
print()


def load(tag_dir):
    path = os.path.join(tag_dir, 'mr_comparison.json')
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except ValueError:
        return None
    pair = {}
    for r in data.get('rows', []):
        pair['mr' if r.get('mr') else 'nomr'] = r
    if 'nomr' not in pair or 'mr' not in pair:
        return None
    pair['_meta'] = data
    return pair


def fmt(pair):
    a, b = pair['nomr'], pair['mr']
    if a.get('diverged') and b.get('diverged'):
        return 'RUNAWAY both', ''
    if a.get('diverged'):
        return ('RUNAWAY -> {:.1f} C'.format(b['peak_C']),
                'MR RESCUE: {:.3f} GHz, {:.0f} GFLOP/s'.format(b['f_GHz'], b['gflops']))
    if b.get('diverged'):
        return '{:.1f} C -> RUNAWAY'.format(a['peak_C']), 'MR MADE IT WORSE'
    dT = b['peak_C'] - a['peak_C']
    dP = 100.0 * (b['gflops'] / a['gflops'] - 1.0) if a['gflops'] else float('nan')
    note = ''
    if abs(dT) < 0.05:
        note = 'MR idle (nothing above target)'
    # Static-power saving: dynamic power is identical between the two runs, so any difference
    # in converged die power is leakage the cooling bought back.
    dstat = a.get('p_chip_W', float('nan')) - b.get('p_chip_W', float('nan'))
    return ('{:6.1f} -> {:6.1f} C  ({:+6.1f} K)'.format(a['peak_C'], b['peak_C'], dT),
            '{:+6.1f}% perf, Q={:.3f} W, dP_static={:+.2f} W, P_cool {:.2f}->{:.2f} W {}'.format(
                dP, b['heat_removed_W'], dstat, a['p_cool_W'], b['p_cool_W'], note))


PHASES = [
    ('p1_dens', 'Phase 1 -- density sweep through the CONVERGENT regime (34-core, 88 CFM, '
                'target 92 C, 10 um, relax 0.1)'),
    ('p2_cliff', 'Phase 2 -- the true cliff, and relax-independence (a genuine runaway '
                 'diverges at every damping)'),
    ('p3_target', 'Phase 3 -- MR target sweep: does wider coverage buy anything?'),
    ('p4_spot', 'Phase 4 -- pixel pitch and policy at target 78 C (fabrication question)'),
    ('p5_', 'Phase 5 -- core count and airflow'),
]

dirs = sorted(d for d in glob.glob(os.path.join(OUT, '*')) if os.path.isdir(d))
seen, incomplete = set(), []

for prefix, title in PHASES:
    print('=' * 100)
    print(title)
    print('=' * 100)
    rows = [d for d in dirs if os.path.basename(d).startswith(prefix)]
    if not rows:
        print('  (no points)')
        print()
        continue
    for d in rows:
        seen.add(d)
        tag = os.path.basename(d)
        pair = load(d)
        if pair is None:
            incomplete.append(tag)
            print('  {:<28s} INCOMPLETE'.format(tag))
            continue
        main, note = fmt(pair)
        print('  {:<28s} {:<34s} {}'.format(tag, main, note))
    print()

leftover = [d for d in dirs if d not in seen]
if leftover:
    print('other points:')
    for d in leftover:
        pair = load(d)
        tag = os.path.basename(d)
        if pair is None:
            incomplete.append(tag)
            print('  {:<28s} INCOMPLETE'.format(tag))
        else:
            main, note = fmt(pair)
            print('  {:<28s} {:<34s} {}'.format(tag, main, note))
    print()

print('-' * 100)
print('{} points complete, {} incomplete'.format(len(seen) - len(incomplete), len(incomplete)))
if incomplete:
    print('incomplete: {}'.format(', '.join(sorted(incomplete))))
    print('re-run scripts/overnight_study.sh <jobid> -- completed points are skipped.')
