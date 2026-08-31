#!/usr/bin/env python
"""Did the surviving floorplan metric transfer to the pack-rebuilt floorplans? Write the evidence.

    python examples/isa_metric_transfer_report.py --out docs/evidence/isa_metric_transfer_pack.json

What this asks
--------------
One metric survived phase 1: **plateau width as a fraction of the die's own temperature span,
against the watts it costs to hold a demanded margin.** rho +0.84 over eleven workloads on one
floorplan, +1.00 over four floorplans, +1.00 over six -- three datasets, two kinds of variation.

Every floorplan in those six was a **uniform rescale** of one McPAT unit mix. So plateau width and
die size were not independent: the only thing that varied was compaction, and both quantities are
monotone in it. The pack rebuild breaks that -- the block mix, the block sizes and the vector
width all move independently of the die area -- which makes it the first real test of whether the
metric measures *shape* or was reading *scale* through a proxy.

How this avoids fishing
-----------------------
``relative_plateau_25pct`` is the **pre-registered** metric and it is reported first, on its own.
The other six quantities are reported as a panel *because a negative result on the registered
metric demands knowing what does predict* -- not as candidates that have passed anything. Any of
them that looks strong here is a hypothesis to register and test on new data, and the report says
so in its own output. n = 6 floorplans; nothing here is a p-value to lean on.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))
sys.path.insert(0, _HERE)

from isa_metric_regression import collect, spearman

#: The registered metric first, then the panel. Order matters: it is the order the report prints.
REGISTERED = ('relative_plateau_25pct', 'relative_plateau_25pct')
PANEL = [('relative_plateau_share', 'relative_plateau_share'),
         ('peak_to_runner_up_gap_K', 'peak_to_runner_up_gap_K'),
         ('die_span_K', 'die_span_K'),
         ('unaided_peak_C', 'unaided_peak_C'),
         ('die_area_mm2', 'area_mm2'),
         ('die_power_W', 'power_W')]


def analyse(root, arm):
    pts = collect(root, arm)
    out = {'root': root, 'arm': arm, 'n_points': len(pts), 'rows': [],
           'no_steady_state': [], 'rho_vs_cost': {}}
    for (a, v, off) in sorted(pts, key=lambda k: (k[1], k[2])):
        r = pts[(a, v, off)]
        if r['diverged']:
            out['no_steady_state'].append('{} @ {} K'.format(v, off))
            continue
        out['rows'].append({'floorplan': v, 'margin_K': off,
                            'density_W_per_mm2': r['density'],
                            'area_mm2': round(r['area_mm2'], 2),
                            'power_W': round(r['power_W'], 2),
                            'unaided_peak_C': round(r['unaided_peak_C'], 2),
                            'relative_plateau_25pct': r['relative_plateau_25pct'],
                            'die_span_K': round(r['die_span_K'], 2),
                            'peak_to_runner_up_gap_K': round(r['peak_to_runner_up_gap_K'], 3),
                            'cost_W': round(r['cost_W'], 4),
                            'unconverged': r['unconverged']})
    for off in sorted({k[2] for k in pts}):
        rows = [v for k, v in pts.items() if k[2] == off and not v['diverged']]
        if len(rows) < 3:
            out['rho_vs_cost'][str(off)] = {'n': len(rows),
                                            'why': 'fewer than 3 convergent floorplans'}
            continue
        cost = [v['cost_W'] for v in rows]
        d = {'n': len(rows), 'floorplans': sorted({k[1] for k in pts if k[2] == off})}
        for name, key in [REGISTERED] + PANEL:
            rho, p = spearman([v[key] for v in rows], cost)
            d[name] = {'rho': round(rho, 3), 'p': round(p, 4) if p is not None else None}
        out['rho_vs_cost'][str(off)] = d
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--old', default=os.path.join(_REPO, 'results', 'isa_benefit'))
    ap.add_argument('--new', default=os.path.join(_REPO, 'results', 'isa_benefit_pack'))
    ap.add_argument('--out', default=os.path.join(_REPO, 'docs', 'evidence',
                                                  'isa_metric_transfer_pack.json'))
    args = ap.parse_args()

    datasets = {
        'old_press_ratio_floorplans_iso_density': analyse(args.old, 'iso'),
        'pack_rebuilt_iso_density': analyse(args.new, 'iso'),
        'pack_rebuilt_published_density': analyse(args.new, 'published'),
    }
    for name, d in datasets.items():
        print('\n=== {}  ({} points, {} with no steady state) ==='.format(
            name, d['n_points'], len(d['no_steady_state'])))
        for off, r in sorted(d['rho_vs_cost'].items(), key=lambda kv: int(kv[0])):
            if 'why' in r:
                print('  {:>2s} K : n={} -- {}'.format(off, r['n'], r['why']))
                continue
            print('  {:>2s} K : n={}   REGISTERED relative_plateau_25pct rho = {:+.3f}'.format(
                off, r['n'], r['relative_plateau_25pct']['rho']))
            print('           panel: ' + '  '.join(
                '{} {:+.2f}'.format(k, r[k]['rho']) for k, _ in PANEL))
        if d['no_steady_state']:
            print('  no steady state: {}'.format(', '.join(sorted(set(d['no_steady_state'])))))

    with open(args.out, 'w') as f:
        json.dump({'note': __doc__.strip(), 'datasets': datasets}, f, indent=1)
    print('\nwrote {}'.format(args.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
