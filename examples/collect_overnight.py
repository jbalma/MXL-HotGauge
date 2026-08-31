#!/usr/bin/env python
"""Collect the overnight campaign into evidence, one row per solved arm.

    python examples/collect_overnight.py

Most of the campaign runs ``mr_comparison.py``, which writes a uniform ``mr_comparison.json`` per
point, so one collector covers the density ladder, the airflow sweep, the resistance ladder, the
core-count scaling and every sensitivity family. The tile-pitch and clipping families write
different schemas and are collected separately where they appear.

The column that matters most is ``diverged``. A control arm that runs away while the array arm
holds target is not a missing data point -- it IS the result, and it is the only form of evidence
that supports "enables a chip that could not otherwise run". The collector therefore keeps
diverged rows rather than dropping them, and reports rescue as its own count.
"""
import os
import re
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')

KEEP = ('arm', 'cores', 'peak_C', 'peak_block', 'p_chip_W', 'heat_removed_W', 'p_mr_net_W',
        'p_cool_W', 'p_total_W', 'f_GHz', 'throttling', 'gflops', 'gflops_per_total_W',
        'diverged', 'die_span_K', 'peak_to_runner_up_gap_K', 'n_targets', 'net_generating',
        'mr_plan_holds_target', 'mr_plan_is_minimum', 'area_mm2', 'fan_W')
TOP = ('density', 'cfm', 'r_th', 'pitch_um', 'burial_um', 'spreading', 'mr_material')


def collect(root):
    rows = []
    for f in sorted(glob.glob(os.path.join(root, '*', '*', 'mr_comparison.json'))):
        try:
            j = json.load(open(f))
        except Exception:
            continue
        fam = os.path.basename(os.path.dirname(os.path.dirname(f)))
        pt = os.path.basename(os.path.dirname(f))
        head = {k: j.get(k) for k in TOP}
        for r in j.get('rows', []):
            row = {'family': fam, 'point': pt}
            row.update(head)
            row.update({k: r.get(k) for k in KEEP})
            row['W_per_mm2'] = ((r.get('p_chip_W') or 0.0) / r['area_mm2']
                                if r.get('area_mm2') else None)
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--roots', nargs='+',
                    default=[os.path.join(_REPO, 'results', 'overnight_forward'),
                             os.path.join(_REPO, 'results', 'overnight_wave2')])
    ap.add_argument('--json-out', default=os.path.join(_EV, 'overnight_campaign.json'))
    args = ap.parse_args()

    rows = []
    for r in args.roots:
        rows.extend(collect(r))
    if not rows:
        raise SystemExit('no mr_comparison.json found yet under {}'.format(args.roots))

    # --- rescue: control diverges, array_on holds -------------------------------------------
    by_pt = {}
    for r in rows:
        by_pt.setdefault((r['family'], r['point']), {})[r['arm']] = r
    rescues, held, lost = [], 0, 0
    for (fam, pt), arms in sorted(by_pt.items()):
        c, a = arms.get('control'), arms.get('array_on')
        if not c or not a:
            continue
        if c.get('diverged') and not a.get('diverged'):
            rescues.append({'family': fam, 'point': pt, 'density': a.get('density'),
                            'cfm': a.get('cfm'), 'cores': a.get('cores'),
                            'array_peak_C': a.get('peak_C'),
                            'heat_removed_W': a.get('heat_removed_W'),
                            'p_mr_net_W': a.get('p_mr_net_W'),
                            'gflops': a.get('gflops')})
        if a.get('diverged'):
            lost += 1
        else:
            held += 1

    fams = sorted({r['family'] for r in rows})
    print('collected %d arm-rows across %d points, families: %s'
          % (len(rows), len(by_pt), ', '.join(fams)))
    print('\narray_on held: %d points; array_on also diverged: %d' % (held, lost))
    print('RESCUES (control runs away, array holds): %d\n' % len(rescues))
    if rescues:
        print('%-12s %-10s %8s %7s %9s %10s %10s'
              % ('family', 'point', 'density', 'cores', 'peak_C', 'Q_rem_W', 'GFLOP/s'))
        for r in rescues[:20]:
            print('%-12s %-10s %8s %7s %9.2f %10.3f %10.1f'
                  % (r['family'], r['point'], r['density'], r['cores'],
                     r['array_peak_C'] or float('nan'), r['heat_removed_W'] or 0.0,
                     r['gflops'] or float('nan')))

    out = {'note': __doc__.strip(), 'n_rows': len(rows), 'n_points': len(by_pt),
           'families': fams, 'rows': rows, 'rescues': rescues,
           'n_rescues': len(rescues), 'n_array_held': held, 'n_array_diverged': lost,
           'A_DIVERGED_CONTROL_IS_THE_RESULT': (
               'Rows where the control arm has no steady state are kept, not dropped. A control '
               'that runs away while the array arm holds target is the only form of evidence that '
               'supports "enables a chip that could not otherwise run" -- treating it as missing '
               'data would discard exactly the finding the campaign was run to produce.')}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
