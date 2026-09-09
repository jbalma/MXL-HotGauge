#!/usr/bin/env python
"""§P0.21 -- the single-material default against the flagged dual-zone arrangement, one point.

    python examples/zone_mode_report.py --json-out docs/evidence/zone_mode_smoke.json

Reads results/zone_mode_smoke/{single,dual}_d2.00 and the P0.20 reference
(results/extractor_v98/dye_dt45/d2.00) and writes the comparison the checklist quotes.
"""
import argparse
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POINTS = {'reference_P0.20': 'results/extractor_v98/dye_dt45/d2.00',
          'single': 'results/zone_mode_smoke/single_d2.00',
          'dual': 'results/zone_mode_smoke/dual_d2.00'}
FIELDS = ('mr_zone_mode', 'n_cold_zone_tiles', 'n_tiles', 'mr_minimum_plan_W',
          'mr_largest_failing_plan_W', 'peak_C', 'peak_block', 'p_chip_W', 'p_mr_net_W',
          'mr_plan_holds_target', 'mr_plan_is_minimum', 'mr_reason')


def rows(x, out):
    if isinstance(x, dict):
        if 'arm' in x and 'peak_C' in x:
            out.append(x)
        else:
            for v in x.values():
                rows(v, out)
    elif isinstance(x, list):
        for v in x:
            rows(v, out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json-out', default=None)
    args = ap.parse_args()
    out = {'point': 'arm D, 34 cores, 88 CFM, target 92 C, 2.00 W/mm^2, coverage 1.00, '
                    'target device (rung 6), scalar 45 K kept', 'rows': {}}
    for k, d in POINTS.items():
        f = os.path.join(REPO, d, 'mr_comparison.json')
        if not os.path.exists(f):
            out['rows'][k] = None
            continue
        r = rows(json.load(open(f)), [])[0]
        row = {c: r.get(c) for c in FIELDS}
        row['extractor'] = r.get('extractor')
        row['tile_flux'] = r.get('tile_flux')
        out['rows'][k] = row
    s, d, ref = out['rows'].get('single'), out['rows'].get('dual'), out['rows'].get('reference_P0.20')
    if s and ref:
        out['default_regression'] = {
            'plan_W_single_minus_reference': s['mr_minimum_plan_W'] - ref['mr_minimum_plan_W'],
            'peak_C_single_minus_reference': s['peak_C'] - ref['peak_C']}
    if s and d:
        out['dual_vs_single'] = {
            'plan_W_dual_minus_single': d['mr_minimum_plan_W'] - s['mr_minimum_plan_W'],
            'peak_C_dual_minus_single': d['peak_C'] - s['peak_C'],
            'n_cold_zone_tiles': d['n_cold_zone_tiles'],
            'n_tiles_capped': (d['extractor'] or {}).get('n_tiles_capped'),
            'shortfall_W': (d['extractor'] or {}).get('shortfall_W')}
    out['reading'] = ('The dual arrangement is a floorplan statement: the numbers above hold for '
                      'this die and this cold-zone pattern only. The default is single.')
    txt = json.dumps(out, indent=1)
    print(txt)
    if args.json_out:
        with open(os.path.join(REPO, args.json_out), 'w') as fh:
            fh.write(txt + '\n')


if __name__ == '__main__':
    main()
