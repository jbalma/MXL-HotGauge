#!/usr/bin/env python
"""Read the extractor campaign (§P0.19) and score its predictions.

    python examples/extractor_report.py [--base results/extractor_armD]

Joins each array_on row to the full-coverage §P0.18.2 reference at the same density
(``results/array_coverage_armD/c1.00``), reports the coldest engaged tile, the extractor's flux
there, how many blocks the curve bound, and the plan cost against the reference at a common
landing peak (dt45 variant only -- the dtnone variant has a different plan shape and is not
comparable). Refuses to write the evidence file while the campaign is incomplete.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')


def _verdict(r):
    if r is None:
        return 'missing'
    if r.get('diverged'):
        return 'DIVERGED'
    if r.get('unconverged'):
        return 'unconverged'
    if r.get('mr') and not r.get('mr_plan_holds_target'):
        return 'holds-but-not-target'
    return 'holds'


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'extractor_armD'))
    ap.add_argument('--ref', default=os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'extractor_armD.json'))
    ap.add_argument('--dT-dQ', type=float, default=0.3247)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    joblist = os.path.join(args.base, 'joblist.tsv')
    planned = [l.split('\t')[0] for l in open(joblist).read().splitlines() if l.strip()] \
        if os.path.isfile(joblist) else []
    done = [p for p in planned if os.path.isfile(os.path.join(p, 'mr_comparison.json'))]
    complete = bool(planned) and len(done) == len(planned)
    print('extractor campaign: {}/{} points on disk{}'.format(
        len(done), len(planned), '' if complete else '  ** INCOMPLETE **'))

    ref = {}
    for f in glob.glob(os.path.join(args.ref, 'd*', 'mr_comparison.json')):
        d = float(os.path.basename(os.path.dirname(f))[1:])
        j = json.load(open(f))
        ref[d] = {r['arm']: r for r in j['rows']}

    rows = []
    for f in sorted(glob.glob(os.path.join(args.base, '*', 'd*', 'mr_comparison.json'))):
        variant = os.path.basename(os.path.dirname(os.path.dirname(f)))
        d = float(os.path.basename(os.path.dirname(f))[1:])
        j = json.load(open(f))
        on = [r for r in j['rows'] if r['arm'] == 'array_on'][0]
        ex = on.get('extractor') or {}
        r_on = (ref.get(d) or {}).get('array_on')
        tgt = float(on.get('mr_target_C') or 92.0)
        dq = None
        if (r_on and _verdict(on) == 'holds' and _verdict(r_on) == 'holds'
                and on.get('heat_removed_W') and r_on.get('heat_removed_W')):
            qn = on['heat_removed_W'] - (tgt - on['peak_C']) / args.dT_dQ
            qr = r_on['heat_removed_W'] - (tgt - r_on['peak_C']) / args.dT_dQ
            dq = 100.0 * (qn / qr - 1.0) if qr > 0 else None
        rows.append({'variant': variant, 'extractor': on.get('mr_extractor'),
                     'dt_max_K': on.get('mr_dt_max_K'), 'energy_cap': on.get('mr_energy_cap'),
                     'density': d, 'verdict': _verdict(on), 'peak_C': on.get('peak_C'),
                     'heat_removed_W': on.get('heat_removed_W'), 'p_chip_W': on.get('p_chip_W'),
                     'p_mr_net_W': on.get('p_mr_net_W'),
                     'min_engaged_tile_K': ex.get('min_engaged_tile_K'),
                     'h_at_min_tile': ex.get('h_at_min_tile_W_per_mm2'),
                     'T_min_K': ex.get('T_min_K'),
                     'n_bound': ex.get('n_tiles_capped'), 'shortfall_W': ex.get('shortfall_W'),
                     'reason': (on.get('mr_reason') or '')[:90],
                     'ref_verdict': _verdict(r_on), 'ref_Q_W': (r_on or {}).get('heat_removed_W'),
                     'dQ_vs_ref_pct_common_peak': dq})
    rows.sort(key=lambda r: (r['variant'], r['density']))

    def sel(variant_prefix, dens=None):
        return [r for r in rows if r['variant'].startswith(variant_prefix)
                and (dens is None or abs(r['density'] - dens) < 1e-9)]

    checks = {}
    dye45 = [r for r in sel('dye_dt45') if 'converged' not in r['variant']]
    checks['P1_dye_never_binds'] = {
        'measured': [{'density': r['density'], 'n_bound': r['n_bound'], 'verdict': r['verdict'],
                      'ref_verdict': r['ref_verdict'], 'dQ_pct': r['dQ_vs_ref_pct_common_peak'],
                      'min_tile_K': r['min_engaged_tile_K']} for r in dye45],
        'verdict': (None if not dye45 else
                    ('FALSIFIED' if any((r['n_bound'] or 0) > 0 and r['density'] <= 2.0 for r in dye45)
                     else 'CONFIRMED' if all((r['n_bound'] or 0) == 0
                                              and (r['ref_verdict'] == 'missing' or r['verdict'] == r['ref_verdict'])
                                              and (r['dQ_vs_ref_pct_common_peak'] is None
                                                   or abs(r['dQ_vs_ref_pct_common_peak']) <= 1.0)
                                              for r in dye45)
                     else 'NOT AS PREDICTED'))}
    g45 = sel('gaas-enhanced_dt45')
    gr45 = sel('gaas-retuned-enhanced_dt45')
    checks['P2_fixed_pump_gaas_binds_only_at_the_overpull'] = {
        'measured': [{'density': r['density'], 'n_bound': r['n_bound'], 'min_tile_K': r['min_engaged_tile_K'],
                      'verdict': r['verdict']} for r in g45],
        'retuned': [{'density': r['density'], 'n_bound': r['n_bound']} for r in gr45],
        'verdict': (None if not g45 else
                    ('FALSIFIED' if any((r['n_bound'] or 0) > 0 and abs(r['density'] - 2.0) < 1e-9 for r in g45)
                     else 'CONFIRMED' if (any((r['n_bound'] or 0) > 0 and r['density'] >= 2.6 for r in g45)
                                          and all((r['n_bound'] or 0) == 0 for r in gr45))
                     else 'NOT AS PREDICTED'))}
    conv = sel('dye_dt45_converged')
    v = {r['density']: r for r in conv}
    checks['P3_converged_cap_takes_a_rung'] = {
        'measured': [{'density': r['density'], 'verdict': r['verdict'], 'Q': r['heat_removed_W'],
                      'p_chip': r['p_chip_W']} for r in conv],
        'verdict': (None if not conv else
                    ('FALSIFIED' if v.get(2.6, {}).get('verdict') == 'holds'
                     else 'CONFIRMED' if (v.get(2.4, {}).get('verdict') == 'holds'
                                          and v.get(2.6, {}).get('verdict') != 'holds')
                     else 'NOT AS PREDICTED'))}
    anchor = [r for r in rows if abs(r['density'] - 1.15) < 1e-9 and r['variant'].endswith('dt45')]
    checks['P4_lift_at_the_airflow_anchor'] = {
        'measured': [{'variant': r['variant'], 'min_tile_K': r['min_engaged_tile_K'],
                      'h_at_min_tile': r['h_at_min_tile']} for r in anchor],
        'verdict': (None if not anchor else
                    ('CONFIRMED' if all((r['min_engaged_tile_K'] or 0) >= 300.0 for r in anchor)
                     else 'NOT AS PREDICTED'))}
    pen = []
    for r in rows:
        if r['variant'].endswith('_dtnone') and r['verdict'] == 'holds':
            twin = [x for x in rows if x['variant'] == r['variant'].replace('_dtnone', '_dt45')
                    and abs(x['density'] - r['density']) < 1e-9 and x['verdict'] == 'holds']
            if twin and twin[0]['heat_removed_W'] and r['heat_removed_W']:
                pen.append({'variant': r['variant'], 'density': r['density'],
                            'penalty_pct': 100.0 * (r['heat_removed_W'] / twin[0]['heat_removed_W'] - 1.0)})
    checks['P5_shape_penalty'] = {
        'measured': pen,
        'verdict': (None if not pen else
                    ('FALSIFIED' if any(x['penalty_pct'] < 0 for x in pen)
                     else 'CONFIRMED' if all(15.0 <= x['penalty_pct'] <= 45.0 for x in pen)
                     else 'NOT AS PREDICTED'))}

    out = {'note': __doc__.strip(), 'complete': complete, 'n_done': len(done), 'n_planned': len(planned),
           'rows': rows, 'predictions': checks,
           'READING': ('dt45 keeps the recorded sensitivity-weighted envelope shape and adds the '
                       'extractor curve as a further cap: comparable with P0.18.2. dtnone lets the '
                       'curve alone bound the envelope: an area-weighted shape, dearer, not comparable.')}
    print('\n{:>30} {:>5} | {:>10} {:>7} {:>7} {:>7} | {:>8} {:>8} {:>6} | {:>10} {:>8}'.format(
        'variant', 'dens', 'verdict', 'peak_C', 'Q_W', 'p_chip', 'minTile', 'h@tile', 'ncap', 'ref', 'dQ%'))
    for r in rows:
        print('{:>30} {:>5.2f} | {:>10} {:>7} {:>7} {:>7} | {:>8} {:>8} {:>6} | {:>10} {:>8}'.format(
            r['variant'], r['density'], r['verdict'],
            '--' if r['peak_C'] is None else '{:.1f}'.format(r['peak_C']),
            '--' if r['heat_removed_W'] is None else '{:.1f}'.format(r['heat_removed_W']),
            '--' if r['p_chip_W'] is None else '{:.0f}'.format(r['p_chip_W']),
            '--' if r['min_engaged_tile_K'] is None else '{:.1f}'.format(r['min_engaged_tile_K']),
            '--' if r['h_at_min_tile'] is None else '{:.0f}'.format(r['h_at_min_tile']),
            '--' if r['n_bound'] is None else str(r['n_bound']),
            r['ref_verdict'],
            '--' if r['dQ_vs_ref_pct_common_peak'] is None else '{:+.1f}'.format(r['dQ_vs_ref_pct_common_peak'])))
    print('\npredictions:')
    for k, val in checks.items():
        print('   {}: {}'.format(k, val.get('verdict')))
    if complete or args.force:
        with open(args.json_out, 'w') as f:
            json.dump(out, f, indent=1)
        print('\nwritten: {}'.format(args.json_out))
        return 0
    print('\nNOT written: campaign incomplete.')
    return 2


if __name__ == '__main__':
    sys.exit(main())
