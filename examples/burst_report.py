#!/usr/bin/env python
"""F4 (§P0.25): burst absorption -- collect ``results/burst/d*/k*/burst_absorption.json``, score
the predictions, write ``docs/evidence/burst_absorption.json``.

    python examples/burst_report.py
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
ARMS = ('control', 'array_static', 'array_modulated')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'burst'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'burst_absorption.json'))
    args = ap.parse_args()
    pts = {}
    for f in glob.glob(os.path.join(args.base, 'd*', 'k*', 'burst_absorption.json')):
        j = json.load(open(f)); d, k = float(j['density']), float(j['burst_factor'])
        pts[(d, k)] = {'density': d, 'k': k, 'die_W': j['die_W'], 'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE')),
                       'rows': {r['arm']: r for r in j['rows']}}
    print('%5s %4s | %-32s %-32s %-32s' % ('d0', 'k', 'control', 'array_static', 'array_modulated'))
    for key in sorted(pts):
        p = pts[key]; cells = []
        for arm in ARMS:
            r = p['rows'].get(arm)
            if not r:
                cells.append('--'); continue
            if r.get('steady_diverged'):
                cells.append('no steady state'); continue
            cells.append('%.1f->%.1f C (+%.1f K) >spec %.0f ms%s' % (r['steady_peak_C'], r['peak_C'] or 0, r['overshoot_K'] or 0, r['ms_above_spec'],
                                                                    ' UNCONV' if r.get('unconverged') else (' RUNAWAY' if r.get('diverged') else '')))
        print('%5.2f %4.1f | %-32s %-32s %-32s%s' % (key[0], key[1], cells[0], cells[1], cells[2], '' if p['done'] else '  [running]'))
    sc = {}
    def g(d, k, arm):
        return (pts.get((d, k), {}).get('rows') or {}).get(arm) or {}
    ok = lambda r: r and not r.get('steady_diverged') and not r.get('diverged') and not r.get('unconverged') and r.get('overshoot_K') is not None
    c2, c3 = g(0.8, 2.0, 'control'), g(0.8, 3.0, 'control')
    if ok(c2) and ok(c3):
        sc['P1_control_overshoots'] = {'measured': {'k2': c2['overshoot_K'], 'k3': c3['overshoot_K'], 'ms_above_spec_k3': c3['ms_above_spec']},
                                       'verdict': ('FALSIFIED: < 5 K at k=3' if c3['overshoot_K'] < 5 else
                                                   ('confirmed' if 8 <= c2['overshoot_K'] <= 20 and 15 <= c3['overshoot_K'] <= 40 and c3['ms_above_spec'] >= 5 else 'NOT as predicted'))}
    s2, m2, m3 = g(0.8, 2.0, 'array_static'), g(0.8, 2.0, 'array_modulated'), g(0.8, 3.0, 'array_modulated')
    if ok(c2) and ok(s2):
        sc['P2_static_array_no_help'] = {'measured': {'control': c2['overshoot_K'], 'static': s2['overshoot_K']},
                                         'verdict': ('FALSIFIED: static < half the control' if s2['overshoot_K'] < 0.5 * c2['overshoot_K'] else
                                                     ('confirmed' if abs(s2['overshoot_K'] - c2['overshoot_K']) <= 3 else 'NOT as predicted'))}
    if ok(c2) and ok(m2):
        allm = [g(0.8, k, 'array_modulated') for k in (1.5, 2.0, 3.0)]
        worst = max((r['overshoot_K'] for r in allm if ok(r)), default=None)
        sc['P3_modulated_absorbs'] = {'measured': {'worst_overshoot_K': worst, 'ms_above_spec_k3': m3.get('ms_above_spec'), 'laser_J_k2': m2.get('laser_energy_J')},
                                      'verdict': ('FALSIFIED: >= half the control' if m2['overshoot_K'] >= 0.5 * c2['overshoot_K'] else
                                                  ('confirmed' if worst is not None and worst <= 3 and (m3.get('ms_above_spec') or 0) == 0 else 'absorbs, outside the 3 K band'))}
    s12, m12 = g(1.0, 2.0, 'array_static'), g(1.0, 2.0, 'array_modulated')
    if ok(s12) and ok(m12):
        sc['P4_at_1.00'] = {'measured': {'static_ms_above_spec': s12['ms_above_spec'], 'modulated_overshoot_K': m12['overshoot_K']},
                            'verdict': 'confirmed' if s12['ms_above_spec'] > 0 and m12['overshoot_K'] <= 3 else 'NOT as predicted'}
    div = [(k, arm) for k, p in pts.items() for arm, r in p['rows'].items() if r.get('diverged')]
    if pts and all(p['done'] for p in pts.values()):
        sc['P5_no_transient_runaway'] = {'measured': div, 'verdict': 'confirmed' if not div else 'FALSIFIED: %s' % div}
    if sc:
        print('\nscorecard:')
        for k, v in sc.items():
            print('  %-28s %s' % (k, v['verdict']))
    out = {'note': __doc__.strip(), 'points': [pts[k] for k in sorted(pts)], 'scorecard': sc,
           'complete': bool(pts) and all(p['done'] for p in pts.values())}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
