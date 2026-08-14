#!/usr/bin/env python
"""Roll the overnight study up into one table per phase.

Reads every ``results/followon/*/mr_comparison.json`` and pairs the MR-off and MR-on rows for
each point. Points that produced no JSON are listed as incomplete rather than skipped silently,
so a partial night is visible as a partial night.
"""
import os
import re
import glob
import json

OUT = '/mnt/nfs01/scratch/jbalma/MXL-HotGauge/results/followon'


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
    ('A_ceiling', 'Study A1 -- performance ceiling: drive the MR target down until it saturates'),
    ('A_dtmax', 'Study A2 -- what a larger dt_max would buy (device roadmap)'),
    ('A_hmax', 'Study A3 -- what a larger h_max would buy (device roadmap)'),
    ('B_14nm', 'Study B -- 14nm, 16-core (native 0.249 W/mm^2)'),
    ('B_10nm', 'Study B -- 10nm, 16-core (native 0.404 W/mm^2)'),
    ('B_7nm', 'Study B -- 7nm,  16-core (native 0.660 W/mm^2)'),
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
