#!/usr/bin/env python
"""F3 (§P0.24): the GA100 on the direct-die microchannel plate, with the array -- collect
``results/accel_f3/<tag>_<arm>/accelerator_study.json``, score the predictions, write
``docs/evidence/accel_f3.json``.

    python examples/accel_f3_report.py
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
ARMS = ('control', 'array_idle', 'array_on')


def load(base):
    pts = {}
    for d in sorted(glob.glob(os.path.join(base, '*_*'))):
        m = re.match(r'(.+)_(control|array_idle|array_on)$', os.path.basename(d))
        if not m:
            continue
        tag, arm = m.group(1), m.group(2)
        f = os.path.join(d, 'accelerator_study.json')
        rec = {'done': os.path.isfile(os.path.join(d, 'DONE')), 'present': os.path.isfile(f)}
        if rec['present']:
            j = json.load(open(f)); t = j.get('tiers') or {}; mr = j.get('mr') or {}
            held = (not j.get('diverged')) and not j.get('unconverged') and (mr.get('holds_target', True) is not False)
            rec.update({'die_W': j['die_power_W'], 'realised_W': j.get('realised_W'), 'density': j.get('density_W_per_mm2'),
                        'kernel': j.get('kernel'), 'diverged': j.get('diverged'), 'unconverged': j.get('unconverged'),
                        'holds': held, 'peak_C': t.get('peak_C'), 'peak_block': t.get('peak_block'), 'peak_class': t.get('peak_class'),
                        'plateau': t.get('plateau_within_dt_max'), 'Q_W': mr.get('heat_removed_W'), 'net_W': mr.get('electrical_W'),
                        'holds_target': mr.get('holds_target'), 'reason': mr.get('reason'),
                        'tiles_capped': (mr.get('extractor') or {}).get('n_tiles_capped'),
                        'max_tile_flux': ((mr.get('tile_flux') or {}).get('max_W_per_mm2') if isinstance(mr.get('tile_flux'), dict) else None),
                        'converged_die_W': mr.get('converged_die_W'),
                        's': ((mr.get('heat_removed_W') or 0.0) / mr['converged_die_W']) if mr.get('converged_die_W') else None,
                        'cooling': (j.get('cooling') or {}).get('r_th_K_per_W')})
        pts.setdefault(tag, {})[arm] = rec
    return pts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'accel_f3'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'accel_f3.json'))
    args = ap.parse_args()
    pts = load(args.base)
    def key(t):
        m = re.match(r'(uniform|occ\d+)_(\d+)W', t); return (m.group(1) != 'uniform', m.group(1), int(m.group(2)))
    print('%-16s %-10s %6s %8s %8s %8s %6s %7s %s' % ('point', 'arm', 'holds', 'peak_C', 'Q_W', 'net_W', 's', 'capped', 'block / reason'))
    for tag in sorted(pts, key=key):
        for arm in ARMS:
            r = pts[tag].get(arm)
            if not r or not r['present']:
                print('%-16s %-10s %s' % (tag, arm, '[running]' if r else '[missing]')); continue
            print('%-16s %-10s %6s %8s %8s %8s %6s %7s %s%s' % (
                tag, arm, 'yes' if r['holds'] else ('unconv' if r.get('unconverged') else 'NO'),
                '--' if r['peak_C'] is None else '%.1f' % r['peak_C'],
                '--' if r['Q_W'] is None else '%.1f' % r['Q_W'], '--' if r['net_W'] is None else '%.1f' % r['net_W'],
                '--' if r['s'] is None else '%.2f' % r['s'], '--' if r['tiles_capped'] is None else r['tiles_capped'],
                r['peak_block'] or '', ('  ' + (r['reason'] or '')[:60]) if arm == 'array_on' else ''))
    # ladders (uniform)
    uni = {int(re.match(r'uniform_(\d+)W', t).group(1)): pts[t] for t in pts if t.startswith('uniform')}
    lad = {}
    for arm in ARMS:
        held = sorted(W for W, p in uni.items() if p.get(arm, {}).get('holds'))
        failed = sorted(W for W, p in uni.items() if p.get(arm, {}).get('present') and not p[arm]['holds'] and not p[arm].get('unconverged'))
        lad[arm] = {'holds_to_W': held[-1] if held else None, 'fails_at_W': failed[0] if failed else None,
                    'complete': all(p.get(arm, {}).get('done') for p in uni.values())}
    print('\nuniform ladder:', json.dumps(lad))
    sc = {}
    c, i, o = lad['control'], lad['array_idle'], lad['array_on']
    if c['complete'] and c['holds_to_W'] is not None:
        sc['P1_control_runs_away_1000_2000'] = {'measured': c, 'verdict': ('FALSIFIED: holds 2000 W' if (c['holds_to_W'] or 0) >= 2000 else
                                                                            ('confirmed' if c['holds_to_W'] >= 1000 and (c['fails_at_W'] or 9e9) <= 2000 else 'NOT as predicted'))}
    if c['complete'] and i['complete'] and c['holds_to_W'] and i['holds_to_W']:
        sc['P2_idle_buys_a_rung'] = {'measured': (c['holds_to_W'], i['holds_to_W']), 'verdict': 'confirmed' if i['holds_to_W'] > c['holds_to_W'] else 'NOT as predicted'}
    if o['complete'] and o['holds_to_W'] is not None and c.get('holds_to_W'):
        p2000 = uni.get(2000, {}).get('array_on', {})
        mult = o['holds_to_W'] / c['holds_to_W']
        sc['P3_laser_holds_2000_plus'] = {'measured': {'holds_to_W': o['holds_to_W'], 's_at_2000': p2000.get('s'), 'multiplier_vs_control': mult},
                                          'verdict': ('FALSIFIED: fails at <= 2000 W' if o['holds_to_W'] < 2000 else
                                                      ('confirmed' if (p2000.get('s') or 0) <= 0.6 else 'holds, but s >= 0.6 at 2000'))}
        sc['P6_multiplier_smaller_than_CPU'] = {'measured': mult, 'verdict': 'confirmed' if 1.3 <= mult < 2.4 else ('FALSIFIED: >= 2.4x' if mult >= 2.4 else 'below 1.3x')}
    flux = [r['max_tile_flux'] for t in pts for r in pts[t].values() if r.get('max_tile_flux') is not None]
    capped = [r['tiles_capped'] or 0 for t in pts for r in pts[t].values() if r.get('tiles_capped') is not None]
    if flux and all(p.get('array_on', {}).get('done') for p in pts.values()):
        sc['P4_tile_demand'] = {'measured': {'max_tile_flux_W_per_mm2': max(flux), 'max_tiles_capped': max(capped) if capped else None},
                                'verdict': ('FALSIFIED: < 50 W/mm^2 everywhere' if max(flux) < 50 else ('confirmed' if max(capped or [0]) == 0 else 'tiles capped: the device binds'))}
    occ = {t: pts[t] for t in pts if t.startswith('occ8')}
    if occ and all(p.get('array_on', {}).get('done') for p in occ.values()):
        r14 = occ.get('occ8_1400W', {}).get('array_on', {})
        sc['P5_concentrated_kernel'] = {'measured': {t: {a: (occ[t][a].get('holds'), occ[t][a].get('Q_W'), occ[t][a].get('peak_block')) for a in ARMS if a in occ[t]} for t in occ},
                                        'verdict': ('confirmed' if r14.get('holds') and (r14.get('Q_W') or 9e9) <= 120 else ('FALSIFIED: laser cannot hold occ8 at 1400 W' if not r14.get('holds') else 'holds, cost > 120 W'))}
    if sc:
        print('\nscorecard:')
        for k, v in sc.items():
            print('  %-34s %s' % (k, v['verdict']))
    out = {'note': __doc__.strip(), 'points': pts, 'uniform_ladder_W': lad, 'scorecard': sc,
           'complete': all(r.get('done') for p in pts.values() for r in p.values()) and len(pts) >= 9}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
