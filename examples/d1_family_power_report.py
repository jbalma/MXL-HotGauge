#!/usr/bin/env python
"""§P0.34: the D1 dense-cluster family under the PER-BLOCK envelope shape, beside its seed-shape
record and the per-block reference ladder, at matched die watts.

    python examples/d1_family_power_report.py      # -> docs/evidence/d1_exec_density_family_power.json

Reads ``results/d1_family_power/exec<f>/array/W*/mr_comparison.json`` (power shape), the recorded
``results/d1_family_arr/`` (seed shape, §P0.22.3) and both reference ladders
(``results/array_coverage_armD/c1.00/d*`` seed, ``results/array_coverage_armD_power/d*`` power).
The premium (member plan / reference plan) is quoted WITHIN a shape only; both are printed.
Scores §P0.34 P1-P3. A rung is held only if the reported field is a steady state at the target.
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
from d1_family_report import REF_MM2, watts_of, normalised_Q     # noqa: E402


def ladder(pattern):
    out = {}
    for f in sorted(glob.glob(pattern)):
        j = json.load(open(f))
        W = round(float(j['density']) * REF_MM2, 1) if 'W' not in os.path.basename(os.path.dirname(f)) \
            else round(watts_of(os.path.dirname(f)), 1)
        out[W] = {r['arm']: r for r in j['rows']}
        out[W]['_done'] = os.path.isfile(os.path.join(os.path.dirname(f), 'DONE'))
    return out


def rung_view(on, ref_on):
    if not on:
        return None
    holds = bool(not on.get('diverged') and on.get('mr_plan_holds_target') and not on.get('unconverged'))
    q, qr = normalised_Q(on), normalised_Q(ref_on)
    return {'holds': holds, 'diverged': bool(on.get('diverged')), 'unconverged': bool(on.get('unconverged')),
            'peak_C': on.get('peak_C'), 'Q_W': on.get('heat_removed_W'), 'Q_norm_W': q,
            'p_chip_W': on.get('p_chip_W'),
            's': (on['heat_removed_W'] / on['p_chip_W']) if (on.get('heat_removed_W') and on.get('p_chip_W')) else None,
            'ref_Q_W': ref_on.get('heat_removed_W') if ref_on else None,
            'ref_holds': bool(ref_on and not ref_on.get('diverged') and ref_on.get('mr_plan_holds_target')) if ref_on else None,
            'premium': (q / qr) if (q and qr and holds) else None,
            'peak_block': on.get('peak_block'), 'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped'),
            'max_tile_flux': (on.get('tile_flux') or {}).get('max_flux_W_per_mm2'),
            'reason': (on.get('mr_reason') or '')[:80], 'shape': on.get('mr_envelope_shape')}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--factors', type=float, nargs='+', default=[0.5, 0.25])
    ap.add_argument('--json-out', default=os.path.join(_EV, 'd1_exec_density_family_power.json'))
    args = ap.parse_args()
    ref = {'seed': ladder(os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00', 'd*', 'mr_comparison.json')),
           'power': ladder(os.path.join(_REPO, 'results', 'array_coverage_armD_power', 'd*', 'mr_comparison.json'))}
    out = {'note': __doc__.strip(), 'members': {}, 'reference': {}}
    for shape in ('seed', 'power'):
        out['reference'][shape] = {W: rung_view(v.get('array_on'), None) for W, v in ref[shape].items()}
    sc = {}
    complete = True
    for F in args.factors:
        mem = {'seed': ladder(os.path.join(_REPO, 'results', 'd1_family_arr', 'exec{:g}'.format(F), 'array', 'W*', 'mr_comparison.json')),
               'power': ladder(os.path.join(_REPO, 'results', 'd1_family_power', 'exec{:g}'.format(F), 'array', 'W*', 'mr_comparison.json'))}
        rows = {}
        Ws = sorted(set(mem['seed']) | set(mem['power']))
        print('\nmember x%g' % F)
        print('  %7s | %-38s | %-38s | %s' % ('W', 'seed: hold  plan  (ref)  premium', 'power: hold  plan  (ref)  premium  s', 'change'))
        for W in Ws:
            v = {}
            for shape in ('seed', 'power'):
                on = mem[shape].get(W, {}).get('array_on')
                ron = ref[shape].get(W, {}).get('array_on')
                v[shape] = rung_view(on, ron)
                if shape == 'power' and W in mem['power'] and not mem['power'][W]['_done']:
                    complete = False
            rows[W] = v

            def fmt(r):
                if not r:
                    return '%-38s' % 'pending'
                return '%-38s' % ('%s %6s (%6s) %s %s' % (
                    'HELD' if r['holds'] else ('DIV ' if r['diverged'] else ('UNC ' if r['unconverged'] else 'lost')),
                    '--' if r['Q_W'] is None else '%.1f' % r['Q_W'], '--' if r['ref_Q_W'] is None else '%.1f' % r['ref_Q_W'],
                    '--' if r['premium'] is None else '%.2fx' % r['premium'], '' if r['s'] is None else 's %.2f' % r['s']))
            ch = ''
            if v['seed'] and v['power'] and v['seed']['Q_W'] and v['power']['Q_W'] and v['seed']['holds'] and v['power']['holds']:
                ch = '%+.0f %%' % (100 * (v['power']['Q_W'] / v['seed']['Q_W'] - 1))
            elif v['seed'] and v['power'] and not v['seed']['holds'] and v['power']['holds']:
                ch = 'GAINED'
            print('  %7.1f | %s | %s | %s' % (W, fmt(v['seed']), fmt(v['power']), ch))
        out['members'][F] = rows
        # ---- scoring ----
        s = {}
        P = {W: v['power'] for W, v in rows.items() if v.get('power')}
        if F == 0.5:
            f243 = P.get(242.6)
            moves = {W: (rows[W]['power']['Q_W'] / rows[W]['seed']['Q_W'] - 1) for W in (121.3, 161.8, 202.2)
                     if rows.get(W, {}).get('seed') and rows[W].get('power') and rows[W]['seed']['Q_W'] and rows[W]['power']['Q_W']
                     and rows[W]['seed']['holds'] and rows[W]['power']['holds']}
            if f243 and len(moves) == 3:
                ok_fall = (-0.35 <= moves[121.3] <= -0.20 and -0.35 <= moves[161.8] <= -0.20 and -0.25 <= moves[202.2] <= -0.15)
                s['P1_x0.5_plans_fall_and_243W_held'] = {
                    'measured': {'plan_change': moves, '243W': {k: f243[k] for k in ('holds', 's', 'Q_W', 'peak_C')}},
                    'verdict': ('FALSIFIED' if (not f243['holds'] or abs(moves[202.2]) < 0.10) else
                                ('confirmed' if ok_fall and f243['holds'] and 0.80 <= (f243['s'] or 0) <= 0.90 else 'NOT as predicted'))}
            else:
                s['P1_x0.5_plans_fall_and_243W_held'] = {'verdict': 'open'}
        if F == 0.25:
            f202, f243 = P.get(202.2), P.get(242.6)
            if f202 and f243:
                s['P2_x0.25_holds_202_loses_243'] = {
                    'measured': {'202W': {k: f202[k] for k in ('holds', 's', 'Q_W', 'peak_C', 'reason')},
                                 '243W': {k: f243[k] for k in ('holds', 's', 'Q_W', 'peak_C', 'reason')}},
                    'verdict': ('FALSIFIED' if (not f202['holds'] or f243['holds']) else
                                ('confirmed' if 0.70 <= (f202['s'] or 0) <= 0.85 else 'NOT as predicted'))}
            else:
                s['P2_x0.25_holds_202_loses_243'] = {'verdict': 'open'}
        prem = {W: v['power']['premium'] for W, v in rows.items() if v.get('power') and v['power'].get('premium')}
        prem_seed = {W: v['seed']['premium'] for W, v in rows.items() if v.get('seed') and v['seed'].get('premium')}
        if prem:
            die_wide = [p for W, p in prem.items() if W >= 160]
            low = prem.get(111.2)
            s['P3_premium_like_for_like'] = {
                'measured': {'power_shape': prem, 'seed_shape': prem_seed},
                'verdict': ('FALSIFIED: premium > 1.6x at 202 W' if prem.get(202.2, 0) > 1.6 else
                            ('confirmed' if die_wide and all(1.1 <= p <= 1.4 for p in die_wide) and (low is None or 1.5 <= low <= 3.0)
                             else 'NOT as predicted'))}
        sc['x%g' % F] = s
    print('\nscorecard (§P0.34):')
    for m, s in sc.items():
        for k, v in s.items():
            print('  %-6s %-36s %s   %s' % (m, k, v['verdict'], json.dumps(v.get('measured', ''))[:200]))
    out['scorecard'] = sc
    out['complete'] = complete
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if complete else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
