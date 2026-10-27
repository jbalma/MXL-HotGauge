#!/usr/bin/env python
"""§P0.32: the 8x / 16x execution-cluster ladder at 20 um and 5 um burial -- where heat TRANSPORT
binds a >100 W/mm^2 functional unit.

    python examples/cluster_transport_report.py     # -> docs/evidence/cluster_transport.json

Reads ``results/cluster_transport/x<factor>/b<burial>/p<pitch>/W<watts>/mr_comparison.json`` (the
members, per-block shape, 50 um cells) and ``results/cluster_transport/ref/...`` (the reference
die at the same burial / pitch / shape), places every rung beside the reference's 200 um-burial
per-block ladder (``results/array_coverage_armD_power/``), and scores §P0.32 P1-P6. The grid
caveat is computed, not asserted: the cluster block's area against the 50 um cell.
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
sys.path.insert(0, _HERE)
from d1_family_report import REF_MM2, watts_of, normalised_Q     # noqa: E402

K_SI = 130.0       # W/mK, for the 1-D estimate q d / k
REF_CALU_UM = (142.0, 115.0)


def read_point(d):
    f = os.path.join(d, 'mr_comparison.json')
    if not os.path.isfile(f):
        return None
    j = json.load(open(f))
    rows = {r['arm']: r for r in j['rows']}
    on, idle = rows.get('array_on'), rows.get('array_idle')
    v = {'W': round(watts_of(d), 1), 'density': j['density'], 'burial_um': j['burial_um'], 'pitch_um': j['pitch_um'],
         'done': os.path.isfile(os.path.join(d, 'DONE')),
         'idle_diverged': bool(idle and idle.get('diverged')) if idle else None,
         'idle_peak_C': idle.get('peak_C') if idle else None}
    if on:
        s_val = (on['heat_removed_W'] / on['p_chip_W']) if (on.get('heat_removed_W') and on.get('p_chip_W')) else None
        # A plan that lifts more than the die makes (s > 1) is under the injected-energy cap:
        # envelope-only, not a rescue (register §1.3 / §P0.18.2). It is reported, never counted.
        envelope_only = bool(s_val is not None and s_val > 1.0)
        v.update({'holds': bool(not on.get('diverged') and on.get('mr_plan_holds_target') and not on.get('unconverged') and not envelope_only),
                  'envelope_only': envelope_only,
                  'diverged': bool(on.get('diverged')), 'unconverged': bool(on.get('unconverged')),
                  'peak_C': on.get('peak_C'), 'peak_block': on.get('peak_block'), 'Q_W': on.get('heat_removed_W'),
                  'Q_norm_W': normalised_Q(on), 'p_chip_W': on.get('p_chip_W'),
                  's': (on['heat_removed_W'] / on['p_chip_W']) if (on.get('heat_removed_W') and on.get('p_chip_W')) else None,
                  'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped'),
                  'min_tile_K': (on.get('extractor') or {}).get('min_engaged_tile_K'),
                  'max_tile_flux': (on.get('tile_flux') or {}).get('max_flux_W_per_mm2'),
                  'n_tiles': on.get('n_tiles'), 'reason': (on.get('mr_reason') or '')[:90],
                  'shape': on.get('mr_envelope_shape')})
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'cluster_transport'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'cluster_transport.json'))
    ap.add_argument('--cell-um', type=float, default=50.0)
    args = ap.parse_args()
    fam = json.load(open(os.path.join(_EV, 'd1_exec_density_family_x8x16.json')))
    mm2 = {m['factor']: m['die_mm2'] for m in fam['members']}
    ref200 = {}
    for f in glob.glob(os.path.join(_REPO, 'results', 'array_coverage_armD_power', 'd*', 'mr_comparison.json')):
        j = json.load(open(f))
        r = [x for x in j['rows'] if x['arm'] == 'array_on']
        if r:
            ref200[round(j['density'] * REF_MM2, 1)] = {'Q_W': r[0].get('heat_removed_W'), 'holds': bool(not r[0].get('diverged') and r[0].get('mr_plan_holds_target')),
                                                       'peak_C': r[0].get('peak_C'), 'max_tile_flux': (r[0].get('tile_flux') or {}).get('max_flux_W_per_mm2')}
    out = {'note': __doc__.strip(), 'members': {}, 'reference_same_geometry': {}, 'reference_200um_power_shape': ref200,
           'grid_caveat': {}, 'one_d_estimate_K': {}}
    # the grid caveat and the 1-D estimate, computed
    for F in (0.125, 0.0625):
        # the tiler keeps the column width and shrinks the height: the dense cALU is a sliver
        m = re.search(r'^cALU_16 :\s*\n\s*position\s+[\d.]+\s*,\s*[\d.]+\s*;\s*\n\s*dimension\s+([\d.]+)\s*,\s*([\d.]+)',
                      open(os.path.join(_REPO, 'examples', 'floorplans', 'outputs', 'd1_exec%g' % F, 'skylake7nm_34core_3_3D-ICE_template.flp')).read(), re.M)
        w, h = (float(m.group(1)), float(m.group(2))) if m else (REF_CALU_UM[0] * F ** 0.5, REF_CALU_UM[1] * F ** 0.5)
        out['grid_caveat'][F] = {'cALU_um': [w, h], 'cALU_mm2': w * h * 1e-6, 'cell_mm2': args.cell_um ** 2 * 1e-6,
                                 'cells_per_block': w * h / args.cell_um ** 2,
                                 'smearing_factor_upper_bound': max(1.0, args.cell_um ** 2 / (w * h))}
    for q in (230.0, 460.0):
        out['one_d_estimate_K']['%.0f_W_per_mm2' % q] = {'%d_um' % d: q * 1e6 * d * 1e-6 / K_SI for d in (5, 20, 200)}
    complete = True
    print('member  burial pitch |   W   hold   peak    plan   (ref same geom / ref 200um)  s    capped  minTile  maxFlux  block')
    for F in (0.125, 0.0625):
        out['members'][F] = {'die_mm2': mm2[F], 'points': []}
        for B in (20, 5):
            for P in (200, 100):
                for d in sorted(glob.glob(os.path.join(args.base, 'x%g' % F, 'b%d' % B, 'p%d' % P, 'W*')), key=watts_of):
                    v = read_point(d)
                    if v is None:
                        complete = False
                        continue
                    complete = complete and v['done']
                    rd = os.path.join(args.base, 'ref', 'b%d' % B, 'p%d' % P, os.path.basename(d))
                    rv = read_point(rd)
                    v['ref_same_geometry'] = {k: rv.get(k) for k in ('holds', 'Q_W', 'Q_norm_W', 'peak_C', 'max_tile_flux', 'tiles_capped')} if rv else None
                    v['ref_200um'] = ref200.get(v['W'])
                    v['premium_same_geometry'] = (v['Q_norm_W'] / rv['Q_norm_W']) if (rv and v.get('holds') and rv.get('holds') and v.get('Q_norm_W') and rv.get('Q_norm_W')) else None
                    v['premium_vs_200um'] = (v['Q_W'] / ref200[v['W']]['Q_W']) if (v.get('holds') and v['W'] in ref200 and ref200[v['W']]['Q_W']) else None
                    out['members'][F]['points'].append(v)
                    print('x%-6g %4d  %4d  | %6.1f %-5s %6s %7s  (%7s / %7s)  %5s  %5s  %6s  %6s  %s' % (
                        F, B, P, v['W'], ('HELD' if v.get('holds') else ('ENV' if v.get('envelope_only') else ('DIV' if v.get('diverged') else ('UNC' if v.get('unconverged') else 'lost')))),
                        '--' if v.get('peak_C') is None else '%.1f' % v['peak_C'], '--' if v.get('Q_W') is None else '%.1f' % v['Q_W'],
                        '--' if not rv or rv.get('Q_W') is None else '%.1f' % rv['Q_W'], '--' if v['W'] not in ref200 else '%.1f' % (ref200[v['W']]['Q_W'] or 0),
                        '--' if v.get('s') is None else '%.2f' % v['s'], v.get('tiles_capped'), '--' if v.get('min_tile_K') is None else '%.0f' % v['min_tile_K'],
                        '--' if v.get('max_tile_flux') is None else '%.1f' % v['max_tile_flux'], v.get('peak_block')))
    for B in (20, 5):
        for P in (200, 100):
            for d in sorted(glob.glob(os.path.join(args.base, 'ref', 'b%d' % B, 'p%d' % P, 'W*')), key=watts_of):
                v = read_point(d)
                if v:
                    v['ref_200um'] = ref200.get(v['W'])
                    v['move_vs_200um'] = (v['Q_W'] / ref200[v['W']]['Q_W'] - 1) if (v.get('holds') and v['W'] in ref200 and ref200[v['W']]['Q_W']) else None
                    out['reference_same_geometry'].setdefault('b%d/p%d' % (B, P), []).append(v)
                    complete = complete and v['done']

    # ---- scoring ----
    def pt(F, B, P, W):
        for v in out['members'].get(F, {}).get('points', []):
            if v['burial_um'] == B and v['pitch_um'] == P and abs(v['W'] - W) < 0.2:
                return v
        return None
    sc = {}
    sc['P1_family'] = {'measured': {'die_mm2': mm2}, 'verdict': 'confirmed' if 83.5 <= mm2[0.125] <= 84.5 and 82.5 <= mm2[0.0625] <= 83.5 else 'NOT as predicted'}
    a, b, c, d = pt(0.125, 5, 100, 242.6), pt(0.0625, 5, 100, 202.2), pt(0.0625, 5, 100, 242.6), pt(0.0625, 20, 200, 202.2)
    e = pt(0.125, 20, 200, 202.2)
    f8_243_20 = pt(0.125, 20, 200, 242.6)
    if all(x and x['done'] for x in (a, b, c, d, e, f8_243_20)):
        falsified = (pt(0.125, 5, 100, 202.2) and not pt(0.125, 5, 100, 202.2)['holds']) or (pt(0.0625, 20, 200, 242.6) and pt(0.0625, 20, 200, 242.6)['holds'])
        confirmed = a['holds'] and b['holds'] and not c['holds'] and not d['holds'] and e['holds'] and not f8_243_20['holds']
        sc['P2_transport_binds'] = {'measured': {'8x@5um/100: 243W': a['holds'], '16x@5um/100: 202W': b['holds'], '16x@5um/100: 243W': c['holds'],
                                                 '16x@20um/200: 202W': d['holds'], '8x@20um/200: 202W': e['holds'], '8x@20um/200: 243W': f8_243_20['holds']},
                                    'verdict': 'FALSIFIED' if falsified else ('confirmed' if confirmed else 'NOT as predicted')}
    else:
        sc['P2_transport_binds'] = {'verdict': 'open'}
    pts = [v for F in out['members'] for v in out['members'][F]['points'] if v.get('holds')]
    if pts:
        fl = max((v['max_tile_flux'] or 0) for v in pts)
        cap5 = max((v['tiles_capped'] or 0) for v in pts if v['burial_um'] == 5)
        cap20 = [v['tiles_capped'] or 0 for v in pts if v['burial_um'] == 20 and abs(v['W'] - 202.2) < 0.2 and v in out['members'][0.0625]['points']]
        sc['P3_tile_demand'] = {'measured': {'max_tile_flux_W_per_mm2': fl, 'max_capped_at_5um': cap5, 'capped_16x_20um_202W': cap20,
                                             'min_tile_K': min((v['min_tile_K'] or 999) for v in pts)},
                                'verdict': ('FALSIFIED' if (fl > 813 or max([cap5] + cap20) > 20) else
                                            ('confirmed' if fl > 50 and cap5 == 0 and cap20 and 1 <= max(cap20) <= 10 else 'NOT as predicted'))}
    refs = [v for k, vs in out['reference_same_geometry'].items() for v in vs if v.get('move_vs_200um') is not None]
    if refs:
        mv = {('b%d/p%d/W%.1f' % (v['burial_um'], v['pitch_um'], v['W'])): v['move_vs_200um'] for v in refs}
        sc['P5_reference_thinning_inert'] = {'measured': mv, 'verdict': ('FALSIFIED' if any(abs(x) > 0.15 for x in mv.values()) else
                                                                         ('confirmed' if all(abs(x) <= 0.10 for x in mv.values()) else 'NOT as predicted'))}
    prem = {('x%g/W%.1f' % (F, v['W'])): v['premium_same_geometry'] for F in out['members'] for v in out['members'][F]['points']
            if v['burial_um'] == 5 and v['pitch_um'] == 100 and v.get('premium_same_geometry')}
    if prem:
        mid = [p for k, p in prem.items() if k.endswith('W161.8') or k.endswith('W202.2')]
        sc['P6_premium_at_5um'] = {'measured': prem, 'verdict': ('FALSIFIED' if any(p > 3.0 for k, p in prem.items() if k.endswith('W202.2')) else
                                                                 ('confirmed' if mid and all(1.3 <= p <= 2.0 for p in mid) else 'NOT as predicted'))}
    out['scorecard'] = sc
    out['complete'] = complete
    print('\nscorecard (§P0.32):')
    for k, v in sc.items():
        print('  %-28s %s   %s' % (k, v['verdict'], json.dumps(v.get('measured', ''))[:220]))
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if complete else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
