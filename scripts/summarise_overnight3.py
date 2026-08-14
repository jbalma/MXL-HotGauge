#!/usr/bin/env python
"""Roll a verified MR study up into one table per phase.

    python scripts/summarise_overnight3.py [results_dir]

Differs from ``summarise_overnight.py`` in one way that matters: it reports the **verification
status** of every point. A point whose peak still moves with the damping is not a result, so it
is printed as UNCONVERGED and counted separately rather than tabulated next to real numbers --
which is exactly the distinction the first two attempts could not make. See docs/CONVERGENCE.md.
"""
import os
import sys
import glob
import json

DEFAULT_OUT = '/mnt/nfs01/scratch/jbalma/MXL-HotGauge/results/overnight3'


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

    # Unverified first: its peak depends on the damping, so nothing downstream of it means
    # anything. Reporting it alongside converged points is how the earlier errors spread.
    bad = [n for n, r in (('no-MR', a), ('MR', b)) if r.get('unconverged')]
    if bad:
        spread = max((r.get('peak_spread_K') or 0.0) for r in (a, b))
        return ('** UNCONVERGED ({}) **'.format(', '.join(bad)),
                'peak moves {:.1f} K between damping levels -- not a result'.format(spread))

    if a.get('diverged') and b.get('diverged'):
        return 'RUNAWAY both', 'no steady state with or without MR, at every damping tried'
    if a.get('diverged'):
        return ('RUNAWAY -> {:.1f} C'.format(b['peak_C']),
                'MR RESCUE: {:.3f} GHz, {:.0f} GFLOP/s, Q={:.3f} W over {} blocks, '
                'P_MR={:.2f} W{}'.format(
                    b['f_GHz'], b['gflops'], b['heat_removed_W'], b.get('n_targets', 0),
                    b.get('p_mr_net_W', 0.0),
                    '' if b.get('throttling') else ', not throttling'))
    if b.get('diverged'):
        return '{:.1f} C -> RUNAWAY'.format(a['peak_C']), 'MR MADE IT WORSE'
    dT = b['peak_C'] - a['peak_C']
    dP = 100.0 * (b['gflops'] / a['gflops'] - 1.0) if a.get('gflops') else float('nan')
    note = 'MR idle (nothing above target)' if abs(dT) < 0.05 else ''
    # Dynamic power is identical between the two runs, so any difference in converged die power
    # is leakage the cooling bought back.
    dstat = a.get('p_chip_W', float('nan')) - b.get('p_chip_W', float('nan'))
    return ('{:6.1f} -> {:6.1f} C  ({:+6.1f} K)'.format(a['peak_C'], b['peak_C'], dT),
            '{:+6.1f}% perf, Q={:.3f} W, dP_static={:+.2f} W, P_cool {:.2f}->{:.2f} W {}'.format(
                dP, b['heat_removed_W'], dstat, a['p_cool_W'], b['p_cool_W'], note))


PHASES = [
    ('p1_dens', 'Phase 1 -- convergent regime and the exact cliff (34-core, 88 CFM, target 92 C, '
                '10 um dilute)'),
    ('p2_ceiling', 'Phase 2 -- where MR stops rescuing (1.15 rescues, 1.18 does not)'),
    ('p3_target', 'Phase 3 -- does a LOWER MR target push the rescue ceiling out? (coverage vs '
                  'heat budget)'),
    ('p4_spot', 'Phase 4 -- pixel pitch and policy at target 78 C (the fabrication question)'),
    ('p5_', 'Phase 5 -- core count and airflow'),
]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    dirs = sorted(d for d in glob.glob(os.path.join(out, '*')) if os.path.isdir(d))
    seen, incomplete, unverified = set(), [], []

    print('MR study, convergence-verified   ({})'.format(out))
    print('every point solved at two damping levels; peaks must agree within 1 K\n')

    def emit(d):
        tag = os.path.basename(d)
        pair = load(d)
        if pair is None:
            incomplete.append(tag)
            print('  {:<28s} INCOMPLETE'.format(tag))
            return
        if any(r.get('unconverged') for r in (pair['nomr'], pair['mr'])):
            unverified.append(tag)
        main_s, note = fmt(pair)
        print('  {:<28s} {:<36s} {}'.format(tag, main_s, note))

    for prefix, title in PHASES:
        print('=' * 110)
        print(title)
        print('=' * 110)
        rows = [d for d in dirs if os.path.basename(d).startswith(prefix)]
        if not rows:
            print('  (no points)')
            print()
            continue
        for d in rows:
            seen.add(d)
            emit(d)
        print()

    leftover = [d for d in dirs if d not in seen]
    if leftover:
        print('other points:')
        for d in leftover:
            seen.add(d)
            emit(d)
        print()

    print('-' * 110)
    print('{} points complete, {} incomplete, {} FAILED VERIFICATION'.format(
        len(seen) - len(incomplete), len(incomplete), len(unverified)))
    if incomplete:
        print('incomplete: {}'.format(', '.join(sorted(incomplete))))
        print('re-run scripts/overnight3_study.sh <jobid> -- completed points are skipped.')
    if unverified:
        print('unverified (DO NOT QUOTE): {}'.format(', '.join(sorted(unverified))))


if __name__ == '__main__':
    main()
