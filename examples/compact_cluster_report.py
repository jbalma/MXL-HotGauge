#!/usr/bin/env python
"""§P0.36: the COMPACT execution cluster beside its sliver twin at the same geometry.

    python examples/compact_cluster_report.py      # -> docs/evidence/compact_cluster.json

Reads ``results/compact_cluster/x<factor>/b<burial>/p<pitch>/W*`` and the twins: the 8x / 16x sliver
members of §P0.32 (``results/cluster_transport/``) and the x0.5 / x0.25 per-block D1 rows of §P0.34
(``results/d1_family_power/``). Same areas, powers, names, die area, planner shape and grid; only the
cluster's SHAPE differs. A row with s > 1 is envelope-only and never a hold.
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
from cluster_coldend_report import verdict              # noqa: E402


def twin_dir(F, B, P, wname):
    if F in (0.5, 0.25):
        return os.path.join(_REPO, 'results', 'd1_family_power', 'exec%g' % F, 'array', wname)
    return os.path.join(_REPO, 'results', 'cluster_transport', 'x%g' % F, 'b%d' % B, 'p%d' % P, wname)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'compact_cluster'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'compact_cluster.json'))
    args = ap.parse_args()
    fam = json.load(open(os.path.join(_EV, 'd1_exec_density_family_compact.json')))
    shapes = {m['factor']: {'die_mm2': m['die_mm2'], 'unit_shapes_um': m.get('unit_shapes_um_core16')} for m in fam['members']}
    rows, complete = [], True
    print('%-7s %4s %4s %6s | compact: %-5s %6s %5s %6s %7s %7s | sliver: %-5s %6s %5s %6s %7s %7s | plan ratio' % (
        'member', 'b', 'p', 'W', 'hold', 'plan', 's', 'capped', 'minTile', 'maxFlux', 'hold', 'plan', 's', 'capped', 'minTile', 'maxFlux'))
    for d in sorted(glob.glob(os.path.join(args.base, 'x*', 'b*', 'p*', 'W*')), key=lambda p: (p.split('/x')[-1].split('/')[0], p.split('/b')[-1].split('/')[0], p.split('/p')[-1].split('/')[0], float(os.path.basename(p)[1:]))):
        F = float(d.split('/x')[-1].split('/')[0]); B = int(d.split('/b')[-1].split('/')[0]); P = int(d.split('/p')[-1].split('/')[0])
        v = read_point(d)
        if v is None:
            complete = False
            continue
        complete = complete and v['done']
        t = read_point(twin_dir(F, B, P, os.path.basename(d)))
        v['factor'] = F
        v['sliver_twin'] = {k: t.get(k) for k in ('holds', 'envelope_only', 'diverged', 'Q_W', 'Q_norm_W', 's', 'tiles_capped', 'min_tile_K', 'max_tile_flux', 'peak_C', 'peak_block')} if t else None
        v['plan_ratio_compact_over_sliver'] = (v['Q_norm_W'] / t['Q_norm_W']) if (t and v.get('holds') and t.get('holds') and t.get('Q_norm_W')) else None
        rows.append(v)

        def f(x, k, fmt):
            return '--' if (not x or x.get(k) is None) else fmt % x[k]
        print('x%-6g %4d %4d %6.1f | %-14s %6s %5s %6s %7s %7s | %-13s %6s %5s %6s %7s %7s | %s' % (
            F, B, P, v['W'], verdict(v), f(v, 'Q_W', '%.1f'), f(v, 's', '%.2f'), v.get('tiles_capped'), f(v, 'min_tile_K', '%.0f'), f(v, 'max_tile_flux', '%.0f'),
            verdict(t), f(t, 'Q_W', '%.1f'), f(t, 's', '%.2f'), (t or {}).get('tiles_capped'), f(t, 'min_tile_K', '%.0f'), f(t, 'max_tile_flux', '%.0f'),
            '--' if v['plan_ratio_compact_over_sliver'] is None else '%.2f' % v['plan_ratio_compact_over_sliver']))

    def pt(F, B, P, W):
        return next((r for r in rows if r['factor'] == F and r['burial_um'] == B and r['pitch_um'] == P and abs(r['W'] - W) < 0.2), None)
    sc = {}
    ref = json.load(open(os.path.join(_EV, 'd1_exec_density_family_x8x16.json')))
    ref_mm2 = {m['factor']: m['die_mm2'] for m in ref['members']}
    s16 = (shapes.get(0.0625) or {}).get('unit_shapes_um') or {}
    if s16:
        c = s16.get('cALU', [0, 0])
        sc['P1_geometry'] = {'measured': {'cALU_16x_um': c, 'die_mm2': {k: v['die_mm2'] for k, v in shapes.items()}, 'sliver_die_mm2': ref_mm2},
                             'verdict': 'confirmed' if (30 <= c[0] <= 40 and 25 <= c[1] <= 40 and all(abs(shapes[k]['die_mm2'] / ref_mm2[k] - 1) < 1e-3 for k in ref_mm2 if k in shapes)) else 'NOT as predicted'}
    need = [pt(0.125, 20, 100, 161.8), pt(0.125, 20, 100, 202.2), pt(0.0625, 20, 100, 161.8), pt(0.0625, 20, 100, 202.2)]
    if all(need) and all(r['done'] for r in need):
        ratios = {('x%g/W%.0f' % (r['factor'], r['W'])): r['plan_ratio_compact_over_sliver'] for r in need}
        r16 = need[3]
        held = [v for v in ratios.values() if v is not None]
        fals = (need[1]['plan_ratio_compact_over_sliver'] is not None and need[1]['plan_ratio_compact_over_sliver'] < 1.0) or (held and all(abs(v - 1) <= 0.05 for v in held) and r16.get('holds'))
        ok = (not r16.get('holds')) and held and all(1.10 <= v <= 1.30 for v in held)
        sc['P2_compact_dearer_16x_loses_202'] = {'measured': {'plan_ratio': ratios, '16x_202W': verdict(r16)}, 'verdict': 'FALSIFIED' if fals else ('confirmed' if ok else 'NOT as predicted')}
    a, b = pt(0.0625, 20, 200, 161.8), pt(0.125, 20, 200, 202.2)
    if a and b and a['done'] and b['done']:
        sc['P3_coarse_pitch'] = {'measured': {'16x_162W_p200': (verdict(a), a.get('Q_W'), a['plan_ratio_compact_over_sliver']), '8x_202W_p200': (verdict(b), b.get('s'))},
                                 'verdict': 'FALSIFIED' if not a.get('holds') else ('confirmed' if (a['plan_ratio_compact_over_sliver'] or 9) <= 1.30 and ((not b.get('holds')) or (b.get('s') or 0) >= 0.95) else 'NOT as predicted')}
    p100 = [r for r in rows if r['pitch_um'] == 100 and abs(r['W'] - 202.2) < 0.2 and r['burial_um'] == 20 and r['factor'] in (0.125, 0.0625)]
    if p100 and all(r['done'] for r in p100):
        m = {('x%g' % r['factor']): {'capped': r.get('tiles_capped'), 'max_flux': r.get('max_tile_flux'), 'min_tile_K': r.get('min_tile_K'), 'sliver_max_flux': (r['sliver_twin'] or {}).get('max_tile_flux')} for r in p100}
        anycap = any((r.get('tiles_capped') or 0) >= 1 for r in p100)
        sc['P4_film_binds_sooner'] = {'measured': m, 'verdict': 'FALSIFIED' if not anycap else ('confirmed' if all(250 <= (r.get('max_tile_flux') or 0) <= 400 for r in p100) else 'NOT as predicted')}
    d1 = [r for r in rows if r['factor'] in (0.5, 0.25) and r['plan_ratio_compact_over_sliver'] is not None]
    if d1:
        m = {('x%g/W%.0f' % (r['factor'], r['W'])): r['plan_ratio_compact_over_sliver'] for r in d1}
        sc['P5_shape_invisible_at_D1_geometry'] = {'measured': m, 'verdict': 'FALSIFIED' if any(abs(v - 1) > 0.10 for v in m.values()) else ('confirmed' if all(abs(v - 1) <= 0.05 for v in m.values()) else 'NOT as predicted')}
    print('\nscorecard (§P0.36):')
    for k, v in sc.items():
        print('  %-36s %s   %s' % (k, v['verdict'], json.dumps(v['measured'])[:260]))
    out = {'note': __doc__.strip(), 'shapes': {str(k): v for k, v in shapes.items()}, 'rows': rows, 'scorecard': sc, 'complete': complete}
    with open(args.json_out, 'w') as fh:
        json.dump(out, fh, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if complete else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
