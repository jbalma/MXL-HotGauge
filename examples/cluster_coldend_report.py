#!/usr/bin/env python
"""§P0.35: the dense cluster's cold-end wall -- is the lost top rung the film's, or one material's?

    python examples/cluster_coldend_report.py      # -> docs/evidence/cluster_coldend.json

Reads ``results/cluster_coldend/<variant>/x<factor>/b<burial>/p<pitch>/W*/mr_comparison.json`` and
places each row beside its §P0.32 dye twin (``results/cluster_transport/``, 100 um pitch). Variants:
``gaas_re`` (retuned, enhanced GaAs over the whole array), ``dual`` (dye + that GaAs over the
execution column), ``gaas_plain`` (v100 Table 9.2 GaAs, the failing control), ``dye_p50`` (the dye at
50 um pitch). A row with s > 1 is envelope-only and never a hold.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, _HERE)
from cluster_transport_report import read_point        # noqa: E402
from d1_family_report import watts_of                   # noqa: E402

VARIANTS = ('gaas_re', 'dual', 'gaas_plain', 'dye_p50')


def verdict(v):
    if v is None:
        return 'pending'
    return 'HELD' if v.get('holds') else ('ENV' if v.get('envelope_only') else ('DIV' if v.get('diverged') else ('UNC' if v.get('unconverged') else 'lost')))


def extras(d):
    j = json.load(open(os.path.join(d, 'mr_comparison.json')))
    on = [r for r in j['rows'] if r['arm'] == 'array_on'][0]
    ex = on.get('extractor') or {}
    return {'eta_asf_at_min_tile': ex.get('eta_asf_at_min_tile'), 'h_at_min_tile_W_per_mm2': ex.get('h_at_min_tile_W_per_mm2'),
            'extractor_label': ex.get('label'), 'n_cold_zone_tiles': on.get('n_cold_zone_tiles'), 'zone_mode': on.get('mr_zone_mode'),
            'p_mr_net_W': on.get('p_mr_net_W'), 'n_tiles': on.get('n_tiles')}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'cluster_coldend'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'cluster_coldend.json'))
    args = ap.parse_args()
    rows, complete = [], True
    print('%-10s %-7s %3s %4s %6s | %-5s %6s %5s %6s %7s %7s %6s | dye twin (p100): %-5s %6s %5s %6s' % (
        'variant', 'member', 'b', 'p', 'W', 'hold', 'plan', 's', 'capped', 'minTile', 'maxFlux', 'eta', 'hold', 'plan', 's', 'capped'))
    for var in VARIANTS:
        for d in sorted(glob.glob(os.path.join(args.base, var, 'x*', 'b*', 'p*', 'W*'))):
            F = float(d.split('/x')[-1].split('/')[0]); B = int(d.split('/b')[-1].split('/')[0]); P = int(d.split('/p')[-1].split('/')[0])
            v = read_point(d)
            if v is None:
                complete = False
                continue
            complete = complete and v['done']
            v.update(extras(d)); v.update({'variant': var, 'factor': F})
            twin = read_point(os.path.join(_REPO, 'results', 'cluster_transport', 'x%g' % F, 'b%d' % B, 'p100', os.path.basename(d)))
            v['dye_twin_p100'] = {k: twin.get(k) for k in ('holds', 'envelope_only', 'diverged', 'Q_W', 's', 'tiles_capped', 'min_tile_K', 'max_tile_flux')} if twin else None
            v['plan_vs_dye_twin'] = (v['Q_W'] / twin['Q_W'] - 1) if (twin and v.get('holds') and twin.get('holds') and twin.get('Q_W')) else None
            rows.append(v)
            print('%-10s x%-6g %3d %4d %6.1f | %-5s %6s %5s %6s %7s %7s %6s | %-22s %-5s %6s %5s %6s' % (
                var, F, B, P, v['W'], verdict(v), '--' if v.get('Q_W') is None else '%.1f' % v['Q_W'], '--' if v.get('s') is None else '%.2f' % v['s'],
                v.get('tiles_capped'), '--' if v.get('min_tile_K') is None else '%.0f' % v['min_tile_K'], '--' if v.get('max_tile_flux') is None else '%.0f' % v['max_tile_flux'],
                '--' if v.get('eta_asf_at_min_tile') is None else '%.3f' % v['eta_asf_at_min_tile'], '', verdict(twin),
                '--' if not twin or twin.get('Q_W') is None else '%.1f' % twin['Q_W'], '--' if not twin or twin.get('s') is None else '%.2f' % twin['s'],
                twin.get('tiles_capped') if twin else '--'))
    sc = {}
    g = [r for r in rows if r['variant'] == 'gaas_re']
    if g and all(r['done'] for r in g):
        top = [r for r in g if abs(r['W'] - 242.6) < 0.2]; mid = [r for r in g if abs(r['W'] - 202.2) < 0.2]
        held_top = [r for r in top if r.get('holds') and (r.get('s') or 1) < 0.98]
        caps = max((r.get('tiles_capped') or 0) for r in g)
        moves = [r['plan_vs_dye_twin'] for r in mid if r.get('plan_vs_dye_twin') is not None]
        sc['P1_cap_removed_243_still_lost'] = {'measured': {'243W': {('x%g/b%d' % (r['factor'], r['burial_um'])): (verdict(r), r.get('s'), r.get('Q_W')) for r in top},
                                                            'max_capped': caps, '202W_plan_vs_dye': moves},
                                               'verdict': 'FALSIFIED' if held_top else ('confirmed' if caps == 0 and all(abs(m) <= 0.05 for m in moves) else 'NOT as predicted')}
    du = [r for r in rows if r['variant'] == 'dual']
    if du and g and all(r['done'] for r in du):
        cmpd = {}
        for r in du:
            a = next((x for x in g if x['factor'] == r['factor'] and x['burial_um'] == r['burial_um'] and abs(x['W'] - r['W']) < 0.2), None)
            if a:
                cmpd['x%g/W%.0f' % (r['factor'], r['W'])] = {'dual': (verdict(r), r.get('Q_W'), r.get('n_cold_zone_tiles')), 'whole_array': (verdict(a), a.get('Q_W')),
                                                           'plan_diff': (r['Q_W'] / a['Q_W'] - 1) if (r.get('Q_W') and a.get('Q_W') and r.get('holds') and a.get('holds')) else None}
        same = all(v['dual'][0] == v['whole_array'][0] for v in cmpd.values())
        sc['P2_dual_equals_whole_array'] = {'measured': cmpd, 'verdict': 'FALSIFIED' if not same else ('confirmed' if all(v['plan_diff'] is None or abs(v['plan_diff']) <= 0.03 for v in cmpd.values()) else 'NOT as predicted')}
    pl = [r for r in rows if r['variant'] == 'gaas_plain']
    if pl and pl[0]['done']:
        sc['P3_plain_gaas_fails'] = {'measured': (verdict(pl[0]), pl[0].get('tiles_capped'), pl[0].get('Q_W')),
                                     'verdict': 'FALSIFIED' if pl[0].get('holds') else ('confirmed' if (pl[0].get('tiles_capped') or 0) > 100 else 'NOT as predicted')}
    p50 = [r for r in rows if r['variant'] == 'dye_p50']
    if p50 and all(r['done'] for r in p50):
        m = {('x%g/W%.0f' % (r['factor'], r['W'])): (verdict(r), r.get('tiles_capped'), r.get('max_tile_flux'), r.get('min_tile_K'), r.get('Q_W')) for r in p50}
        r16 = next((r for r in p50 if r['factor'] == 0.0625 and abs(r['W'] - 202.2) < 0.2), None)
        fals = bool(r16 and r16.get('holds') and (r16.get('tiles_capped') or 0) == 0)
        r8 = next((r for r in p50 if r['factor'] == 0.125 and abs(r['W'] - 202.2) < 0.2), None)
        ok = bool(r16 and not r16.get('holds') and r8 and r8.get('holds') and all(not r.get('holds') for r in p50 if abs(r['W'] - 242.6) < 0.2))
        sc['P4_finer_pitch_worse_for_dye'] = {'measured': m, 'verdict': 'FALSIFIED' if fals else ('confirmed' if ok else 'NOT as predicted')}
    if g:
        etas = [r.get('eta_asf_at_min_tile') for r in g if r.get('eta_asf_at_min_tile') is not None]
        if etas:
            sc['P5_price_is_pump_power'] = {'measured': {'eta_asf_at_coldest_tile': (min(etas), max(etas))}, 'verdict': 'confirmed' if 0.005 <= min(etas) and max(etas) <= 0.03 else 'NOT as predicted'}
    print('\nscorecard (§P0.35):')
    for k, v in sc.items():
        print('  %-34s %s   %s' % (k, v['verdict'], json.dumps(v['measured'])[:260]))
    out = {'note': __doc__.strip(), 'rows': rows, 'scorecard': sc, 'complete': complete}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if complete else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
