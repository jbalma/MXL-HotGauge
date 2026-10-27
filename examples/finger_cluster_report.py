#!/usr/bin/env python
"""§P0.38: the DESIGNED finger cluster beside the strip and compact members at the same geometry.

    python examples/finger_cluster_report.py      # -> docs/evidence/finger_cluster.json

Reads ``results/finger_cluster/{finger,strip,compact}_x<factor>/b<burial>/p<pitch>/W*`` and, for the
16x strip / compact members, the recorded rows of §P0.32 (``results/cluster_transport/``) and §P0.36
(``results/compact_cluster/``); ``results/finger_cluster/bounds/`` holds the compact 16x's
transport-wall bounds (no scalar lift). Same areas, powers, names, die area, planner shape and grid
in every shape of one factor; only the arrangement differs. A row with s > 1 is envelope-only and
never a hold; an unconverged row is neither. Quote every row with its unit SHAPE.
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

RUNGS = (111.207, 121.316, 161.755, 202.194, 242.633)
KEEP = ('W', 'density', 'burial_um', 'pitch_um', 'done', 'holds', 'envelope_only', 'diverged', 'unconverged',
        'peak_C', 'peak_block', 'Q_W', 'Q_norm_W', 'p_chip_W', 's', 'tiles_capped', 'min_tile_K',
        'max_tile_flux', 'n_tiles', 'reason')


def member_dir(base, shape, F, B, P, W):
    wname = 'W%.3f' % W
    if F == 0.0625 and shape == 'strip':
        return os.path.join(_REPO, 'results', 'cluster_transport', 'x%g' % F, 'b%d' % B, 'p%d' % P, wname)
    if F == 0.0625 and shape == 'compact':
        return os.path.join(_REPO, 'results', 'compact_cluster', 'x%g' % F, 'b%d' % B, 'p%d' % P, wname)
    return os.path.join(base, '%s_x%g' % (shape, F), 'b%d' % B, 'p%d' % P, wname)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'finger_cluster'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'finger_cluster.json'))
    args = ap.parse_args()
    geom = {}
    for f, key in (('d1_exec_density_family_finger.json', 'finger'), ('d1_exec_density_family_x32.json', 'strip'),
                   ('d1_exec_density_family_compact_x32.json', 'compact'), ('d1_exec_density_family_x8x16.json', 'strip'),
                   ('d1_exec_density_family_compact.json', 'compact')):
        p = os.path.join(_EV, f)
        if os.path.isfile(p):
            for m in json.load(open(p))['members']:
                if m['factor'] in (0.0625, 0.03125):
                    geom['%s_x%g' % (key, m['factor'])] = {'die_mm2': m['die_mm2'], 'unit_shapes_um_core16': m.get('unit_shapes_um_core16'),
                                                           'unit_centres_um_core16': m.get('unit_centres_um_core16'), 'blocks': m['blocks']}
    rows, complete = [], True
    for F in (0.0625, 0.03125):
        for P in (100, 200):
            print('\n%gx cluster, 20 um burial, %d um pitch  (verdict plan[W] s capped peak-block)' % (1 / F, P))
            print('%8s | %-40s | %-40s | %-40s' % ('W', 'strip', 'DESIGNED finger', 'compact'))
            for W in RUNGS:
                cells = []
                for shape in ('strip', 'finger', 'compact'):
                    v = read_point(member_dir(args.base, shape, F, 20, P, W))
                    if v is None:
                        complete = False
                        cells.append('--')
                        continue
                    complete = complete and bool(v.get('done'))
                    r = {k: v.get(k) for k in KEEP}
                    r.update({'shape': shape, 'factor': F, 'verdict': verdict(v)})
                    rows.append(r)
                    cells.append('%-13s %6s %5s %3s %s' % (verdict(v), '--' if v.get('Q_W') is None else '%.1f' % v['Q_W'],
                                                           '--' if v.get('s') is None else '%.2f' % v['s'], v.get('tiles_capped'), v.get('peak_block') or ''))
                print('%8.1f | %-40s | %-40s | %-40s' % (W, cells[0], cells[1], cells[2]))
    bounds = []
    for d in sorted(glob.glob(os.path.join(args.base, 'bounds', '*', 'b*', 'p*', 'W*'))):
        v = read_point(d)
        if v is None:
            complete = False
            continue
        complete = complete and bool(v.get('done'))
        r = {k: v.get(k) for k in KEEP}
        r.update({'case': d.split('/bounds/')[1].split('/')[0], 'shape': 'compact', 'factor': 0.0625, 'verdict': verdict(v), 'scalar_lift': None})
        bounds.append(r)
    if bounds:
        print('\nbounds on the compact 16x wall (no scalar lift):')
        for r in bounds:
            print('  %-28s b%-3d p%-4d W%6.1f  %-13s plan %s  s %s  capped %s  min tile %s K' % (
                r['case'], r['burial_um'], r['pitch_um'], r['W'], r['verdict'], '--' if r['Q_W'] is None else '%.1f' % r['Q_W'],
                '--' if r['s'] is None else '%.2f' % r['s'], r['tiles_capped'], '--' if r['min_tile_K'] is None else '%.0f' % r['min_tile_K']))

    def pt(shape, F, P, W):
        return next((r for r in rows if r['shape'] == shape and r['factor'] == F and r['pitch_um'] == P and abs(r['W'] - W) < 0.2), None)

    def held(r):
        return bool(r and r.get('holds') and not r.get('envelope_only'))
    sc = {}
    f162, f202, f243 = (pt('finger', 0.0625, 100, W) for W in RUNGS[2:])
    s162, s202 = pt('strip', 0.0625, 100, RUNGS[2]), pt('strip', 0.0625, 100, RUNGS[3])
    if all((f162, f202, f243, s162, s202)) and all(r['done'] for r in (f162, f202, f243)):
        ratios = {W: (f['Q_norm_W'] / s['Q_norm_W']) if (held(f) and held(s) and s.get('Q_norm_W')) else None
                  for W, f, s in ((162, f162, s162), (202, f202, s202))}
        ok = held(f162) and held(f202) and not held(f243) and all(v is not None and 0.85 <= v <= 1.15 for v in ratios.values())
        fals = (not held(f202)) or any(v is not None and abs(v - 1) > 0.25 for v in ratios.values())
        sc['P1_designed_finger_16x_keeps_the_rungs'] = {'measured': {'verdicts': {162: f162['verdict'], 202: f202['verdict'], 243: f243['verdict']}, 'plan_ratio_finger_over_strip': ratios},
                                                        'verdict': 'confirmed' if ok else ('FALSIFIED' if fals else 'NOT as predicted')}
        top = next((r for r in (f243, f202, f162) if held(r)), None)
        if top:
            pb = (top.get('peak_block') or '')
            sc['P2_limiter_moves_to_the_vector_unit'] = {'measured': {'top_held_W': top['W'], 'peak_block': pb},
                                                         'verdict': 'confirmed' if pb.startswith(('AVXs', 'FPUs')) else ('FALSIFIED' if pb.startswith(('cALU', 'iALU')) else 'NOT as predicted')}
    a, b, sa = pt('finger', 0.0625, 200, RUNGS[2]), pt('finger', 0.0625, 200, RUNGS[3]), pt('strip', 0.0625, 200, RUNGS[2])
    if a and b and a['done'] and b['done']:
        ratio = (a['Q_norm_W'] / sa['Q_norm_W']) if (held(a) and held(sa) and sa.get('Q_norm_W')) else None
        ok = held(a) and ratio is not None and abs(ratio - 1) <= 0.20 and ((not held(b)) or (b.get('s') or 0) >= 0.95)
        sc['P3_coarse_pitch'] = {'measured': {'162W': a['verdict'], 'plan_ratio_finger_over_strip': ratio, '202W': b['verdict'], 's_202W': b.get('s')},
                                 'verdict': 'confirmed' if ok else 'NOT as predicted'}
    x32 = {sh: {W: pt(sh, 0.03125, 100, W) for W in RUNGS} for sh in ('strip', 'finger', 'compact')}
    if all(r is not None and r['done'] for sh in x32.values() for r in sh.values()):
        top = {sh: max([W for W, r in x32[sh].items() if held(r)] or [0]) for sh in x32}
        ok = all(abs(top[sh] - RUNGS[2]) < 0.2 for sh in ('strip', 'finger')) and top['compact'] <= RUNGS[1] + 0.2
        fals = top['compact'] >= RUNGS[2] - 0.2 or any(held(x32[sh][RUNGS[3]]) and (x32[sh][RUNGS[3]].get('s') or 9) < 0.95 for sh in ('strip', 'finger'))
        sc['P4_32x_costs_a_rung_order_survives'] = {'measured': {'top_held_W_by_shape': top}, 'verdict': 'confirmed' if ok else ('FALSIFIED' if fals else 'NOT as predicted')}
    if bounds and all(r['done'] for r in bounds):
        def bp(case, B, P, W):
            return next((r for r in bounds if r['case'] == case and r['burial_um'] == B and r['pitch_um'] == P and abs(r['W'] - W) < 0.2), None)
        a5, a50 = bp('compact_x0.0625_gaasr', 5, 100, RUNGS[2]), bp('compact_x0.0625_gaasr', 20, 50, RUNGS[2])
        if a5 and a50:
            sc['P5_bounds_on_the_compact_16x_wall'] = {'measured': {'5um_gaasr_162W': a5['verdict'], '50um_pitch_gaasr_162W': a50['verdict'],
                                                                    'all': {('%s/b%d/p%d/W%.0f' % (r['case'], r['burial_um'], r['pitch_um'], r['W'])): r['verdict'] for r in bounds}},
                                                       'verdict': 'confirmed' if (held(a5) and held(a50)) else ('FALSIFIED: the wall is below the grid' if not (held(a5) or held(a50)) else 'NOT as predicted'),
                                                       'not_built': 'the cropped die on a 25 um grid'}
    print('\nscorecard (§P0.38):')
    for k, v in sc.items():
        print('  %-42s %s   %s' % (k, v['verdict'], json.dumps(v['measured'])[:300]))
    out = {'note': __doc__.strip(), 'geometry': geom, 'rows': rows, 'bounds': bounds, 'scorecard': sc, 'complete': complete}
    with open(args.json_out, 'w') as fh:
        json.dump(out, fh, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if complete else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
