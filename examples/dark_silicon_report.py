#!/usr/bin/env python
"""F2 (§P0.23.2): dark-silicon recovery -- the active-core fraction each arm can light at a
given per-core power, and what the laser costs to light all of it.

    python examples/dark_silicon_report.py

Reads ``results/dark_silicon/d<density>/f<fraction>/mr_comparison.json``; per per-core power:
the highest lit fraction per arm (a fraction counts as lit only if the arm holds, converged,
with the plan holding the 92 C target), the laser cost at 100 %, and the comparison of that
cost with the uniform-activity ladder at the same die average (``results/array_coverage_armD/
c1.00``). Scores §P0.23.2 P1-P4 and writes ``docs/evidence/dark_silicon.json``. Rungs still
running are listed as open.
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
BACKGROUND = 0.25
DT_DQ = 0.3247


def load(overrides=()):
    """Recorded points, then each override base in order: a point found under an override REPLACES
    the recorded one arm by arm and records where it came from (§P0.29: the per-block envelope
    shape and the 12-iteration budget supersede the seed-shape rows)."""
    pts = {}
    bases = [os.path.join(_REPO, 'results', 'dark_silicon')] + [os.path.join(_REPO, b) if not os.path.isabs(b) else b for b in overrides]
    files = []
    for b in bases:
        files += sorted(glob.glob(os.path.join(b, 'd*', 'f*', 'mr_comparison.json')))
    for f in files:
        d = float(re.search(r'/d([0-9.]+)/', f).group(1)); fr = float(re.search(r'/f([0-9.]+)/', f).group(1))
        j = json.load(open(f)); rows = {r['arm']: r for r in j['rows']}
        rec = {'density': d, 'fraction': fr, 'die_avg': d * (fr + BACKGROUND * (1 - fr)),
               'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE'))}
        for arm, r in rows.items():
            lit = (not r.get('diverged')) and not r.get('unconverged') and (r.get('mr_plan_holds_target', True) is not False)
            rec[arm] = {'lit': lit, 'diverged': r.get('diverged'), 'unconverged': r.get('unconverged'),
                        'reason': (r.get('mr_reason') or '')[:90], 'unfinished': (r.get('mr_reason') or '').startswith('max_iter'),
                        'peak_C': r.get('peak_C'), 'p_chip_W': r.get('p_chip_W'),
                        'Q_W': r.get('heat_removed_W'), 'p_mr_net_W': r.get('p_mr_net_W'),
                        'peak_block': r.get('peak_block'), 'tiles_capped': (r.get('extractor') or {}).get('n_tiles_capped'),
                        'source': os.path.relpath(os.path.dirname(f), _REPO), 'envelope_shape': j.get('mr_envelope_shape') or 'seed'}
        if (d, fr) in pts:
            # override: keep the recorded record, replace the arms this base carries
            for arm in rows:
                pts[(d, fr)][arm] = rec[arm]
            pts[(d, fr)]['done'] = pts[(d, fr)]['done'] and rec['done']
        else:
            pts[(d, fr)] = rec
    return pts


def uniform_Q(density):
    f = os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00', 'd%.2f' % density, 'mr_comparison.json')
    if not os.path.isfile(f):
        return None
    r = {x['arm']: x for x in json.load(open(f))['rows']}.get('array_on')
    if not r or r.get('diverged'):
        return None
    return r['heat_removed_W'] + (r['peak_C'] - 92.0) / DT_DQ


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--override', nargs='*', default=[],
                    help='result bases whose points SUPERSEDE results/dark_silicon (e.g. results/dark_silicon_v2/power)')
    ap.add_argument('--json-out', default=os.path.join(_EV, 'dark_silicon.json'))
    args = ap.parse_args()
    pts = load(args.override)
    dens = sorted({d for d, _ in pts}); fracs = sorted({f for _, f in pts})
    out = {'note': __doc__.strip(), 'background': BACKGROUND, 'per_density': {}, 'points': [pts[k] for k in sorted(pts)]}
    print('%6s %6s %8s | %-9s %-9s %-9s | %8s %8s' % ('d', 'f', 'die avg', 'control', 'idle', 'laser', 'Q_W', 'net_W'))
    for d in dens:
        for fr in fracs:
            p = pts.get((d, fr))
            if not p:
                continue
            def st(arm):
                a = p.get(arm)
                if not a:
                    return '--'
                return ('lit %.0fC' % a['peak_C']) if a['lit'] else ('unconv' if a.get('unconverged') else ('DIV' if a.get('diverged') else 'hot %.0fC' % (a['peak_C'] or 0)))
            on = p.get('array_on', {})
            print('%6.2f %6.2f %8.3f | %-9s %-9s %-9s | %8s %8s%s' % (
                d, fr, p['die_avg'], st('control'), st('array_idle'), st('array_on'),
                '--' if on.get('Q_W') is None else '%.1f' % on['Q_W'], '--' if on.get('p_mr_net_W') is None else '%.1f' % on['p_mr_net_W'],
                '' if p['done'] else '  [running]'))
        summ = {}
        for arm in ('control', 'array_idle', 'array_on'):
            lit = [fr for fr in fracs if pts.get((d, fr), {}).get(arm, {}).get('lit')]
            unlit = [fr for fr in fracs if (d, fr) in pts and arm in pts[(d, fr)] and not pts[(d, fr)][arm]['lit']]
            summ[arm] = {'highest_lit_fraction': max(lit) if lit else 0.0, 'lowest_unlit_fraction': min(unlit) if unlit else None,
                         'complete': all(pts.get((d, fr), {}).get('done') for fr in fracs)}
        full = pts.get((d, 1.0), {}).get('array_on', {})
        summ['laser_cost_at_100pct_W'] = full.get('Q_W'); summ['laser_net_at_100pct_W'] = full.get('p_mr_net_W')
        uq = uniform_Q(d)
        if uq and full.get('Q_W') is not None and full.get('lit'):
            summ['plan_vs_uniform_ladder'] = (full['Q_W'] + (full['peak_C'] - 92.0) / DT_DQ) / uq if uq > 0.5 else None
        out['per_density'][str(d)] = summ
        print('   -> lit up to: control %.2f, idle %.2f, laser %.2f; laser cost at 100 %%: %s W' % (
            summ['control']['highest_lit_fraction'], summ['array_idle']['highest_lit_fraction'], summ['array_on']['highest_lit_fraction'],
            '--' if summ['laser_cost_at_100pct_W'] is None else '%.1f' % summ['laser_cost_at_100pct_W']))
    # scorecard
    sc = {}
    g = lambda d, arm: out['per_density'].get(str(d), {}).get(arm, {})
    if g(1.0, 'control').get('complete'):
        sc['P1_control_cannot_light_the_die'] = {'predicted': 'control lights 50 % at 0.78, 25-50 % at 1.00, <= 25 % at 1.20/1.50',
                                                 'measured': {str(d): g(d, 'control').get('highest_lit_fraction') for d in dens},
                                                 'verdict': 'FALSIFIED: the control holds 100 % at 1.00' if g(1.0, 'control').get('highest_lit_fraction') == 1.0 else
                                                 ('confirmed' if g(0.78, 'control').get('highest_lit_fraction', 1) <= 0.5 else 'NOT as predicted')}
    if g(0.78, 'array_idle').get('complete'):
        sc['P2_passive_layer_lights_the_native_die'] = {'predicted': 'idle lights 100 % at 0.78 and 1.00',
                                                        'measured': {str(d): g(d, 'array_idle').get('highest_lit_fraction') for d in dens},
                                                        'verdict': 'confirmed' if g(0.78, 'array_idle').get('highest_lit_fraction') == 1.0 else 'FALSIFIED'}
    if all(g(d, 'array_on').get('complete') for d in dens):
        costs = {str(d): out['per_density'][str(d)].get('laser_cost_at_100pct_W') for d in dens}
        lit_all = all(g(d, 'array_on').get('highest_lit_fraction') == 1.0 for d in dens)
        sc['P3_laser_lights_100pct_everywhere'] = {'predicted': '100 % at every per-core power; <=5 W at 0.78/1.00, 15-35 W at 1.20, 50-80 W at 1.50',
                                                   'measured': costs, 'verdict': ('confirmed' if lit_all and all((costs.get(k) or 0) <= 100 for k in costs) else 'NOT as predicted')}
        ratios = {str(d): out['per_density'][str(d)].get('plan_vs_uniform_ladder') for d in dens}
        if any(v for v in ratios.values()):
            worst = max(abs(v - 1) for v in ratios.values() if v)
            sc['P4_array_resolves_the_cluster'] = {'predicted': 'plan at 100 % within +-25 % of the uniform ladder at the same die average',
                                                   'measured': ratios, 'verdict': 'confirmed' if worst <= 0.25 else ('FALSIFIED' if worst > 0.5 else 'outside +-25 %')}
    out['scorecard'] = sc
    if sc:
        print('\nscorecard:')
        for k, v in sc.items():
            print('  %-42s %s' % (k, v['verdict']))
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s' % os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
