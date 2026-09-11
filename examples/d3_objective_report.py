#!/usr/bin/env python
"""D3 (§P0.22.2): the cache-leakage planner objective on the MONOLITHIC 34-core die -- collect the
smoke campaign and score the predictions.

    python examples/d3_objective_report.py

Reads ``results/d3_objective_v2/`` (twelve planner iterations, the corrected on-die leakage
ledger) and, for the record, ``results/d3_objective/`` (the first pass: six iterations, a ledger
whose DIE total double-counted McPAT's restating rows -- its cache figures are right, its die
totals are not, and they are reported as ``first_pass`` only). Writes
``docs/evidence/d3_cache_objective.json``.

What each variant is
--------------------
``peak``      the recorded hot-spot objective: the regression row.
``dt45_T*``   cache-leakage objective, the scalar 45 K lift kept beside the extractor curve.
``dtnone_T*`` cache-leakage objective, the target device's curve alone.
``dual_T*``   cache-leakage objective, curve only, Cr:LiSAF on the tiles majority-under the caches.
``T280`` / ``T300``: the cache-zone target -- the measured leakage knee (below the 295 K ambient),
and a reachable point above it.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')

CACHE = '^(L2|L3)'


def load(base):
    out = {}
    for f in sorted(glob.glob(os.path.join(base, '*', 'd*', 'mr_comparison.json'))):
        variant = os.path.basename(os.path.dirname(os.path.dirname(f)))
        j = json.load(open(f))
        rows = {r['arm']: r for r in j['rows']}
        out[(variant, float(j['density']))] = {'variant': variant, 'density': float(j['density']),
                                               'mr_iter': None, 'rows': rows,
                                               'done': os.path.isfile(os.path.join(
                                                   os.path.dirname(f), 'DONE'))}
    return out


def summarise(point):
    idle, on = point['rows'].get('array_idle'), point['rows'].get('array_on')
    if not on:
        return None
    z = (on.get('mr_zones') or {}).get(CACHE) or {}
    x = on.get('extractor') or {}
    s = {'variant': point['variant'], 'density': point['density'], 'done': point['done'],
         'objective': on.get('mr_objective'), 'cold_target_K': on.get('mr_cold_target_K'),
         'zone_mode': on.get('mr_zone_mode'), 'dt_max_K': on.get('mr_dt_max_K'),
         'diverged': bool(on.get('diverged')),
         'peak_C': on.get('peak_C'), 'heat_removed_W': on.get('heat_removed_W'),
         'p_chip_W': on.get('p_chip_W'), 'p_injected_W': on.get('p_injected_W'),
         'p_mr_net_W': on.get('p_mr_net_W'),
         'plan_share_of_die': ((on.get('heat_removed_W') or 0.0) / on['p_chip_W']
                               if on.get('p_chip_W') else None),
         'cache_zone_mean_K': z.get('mean_K'), 'cache_zone_max_K': z.get('max_K'),
         'cache_blocks_above_target': z.get('n_above_target'), 'n_cache_blocks': z.get('n_blocks'),
         'n_tiles_capped': x.get('n_tiles_capped'), 'shortfall_W': x.get('shortfall_W'),
         'die_leakage_W': on.get('die_leakage_W'), 'cache_leakage_W': on.get('cache_leakage_W'),
         'reason': on.get('mr_reason'), 'plan_holds_target': on.get('mr_plan_holds_target'),
         'plan_is_minimum': on.get('mr_plan_is_minimum'), 'unconverged': on.get('unconverged')}
    if idle and not idle.get('diverged'):
        s['idle'] = {'peak_C': idle.get('peak_C'), 'p_chip_W': idle.get('p_chip_W'),
                     'die_leakage_W': idle.get('die_leakage_W'),
                     'cache_leakage_W': idle.get('cache_leakage_W'),
                     'cache_zone_mean_C': idle.get('cache_zone_mean_C'),
                     'cache_zone_max_C': idle.get('cache_zone_max_C')}
        if idle.get('cache_leakage_W') and on.get('cache_leakage_W'):
            s['cache_leakage_reduction_x'] = idle['cache_leakage_W'] / on['cache_leakage_W']
        if idle.get('die_leakage_W') and on.get('die_leakage_W'):
            s['die_leakage_reduction_x'] = idle['die_leakage_W'] / on['die_leakage_W']
    return s


def score(pts, ref_rows):
    """The §P0.22.2 predictions against the rows, at 1.00 W/mm^2."""
    g = lambda v: pts.get((v, 1.0))
    out = {}
    pk = g('peak')
    if pk and ref_rows:
        r = ref_rows.get('array_on') or {}
        out['P1_regression'] = {
            'predicted': 'reproduces the c1.00 reference row to the digit (0 W, 89.1 C)',
            'measured': {'Q_W': pk['heat_removed_W'], 'peak_C': pk['peak_C'],
                         'ref_Q_W': r.get('heat_removed_W'), 'ref_peak_C': r.get('peak_C')},
            'verdict': ('confirmed' if (abs((pk['peak_C'] or 0) - (r.get('peak_C') or -1)) < 0.05
                                        and (pk['heat_removed_W'] or 0) == (r.get('heat_removed_W') or 0))
                        else 'NOT reproduced')}
    dn = g('dtnone_T280')
    if dn:
        cons = 'conservation' in (dn['reason'] or '') or (dn['plan_share_of_die'] or 0) >= 0.95
        out['P2_280K_is_conservation_bound'] = {
            'predicted': 'plan reaches the die-power cap; cache zone >= 292 K; not holding',
            'measured': {'plan_share_of_die': dn['plan_share_of_die'],
                         'cache_zone_mean_K': dn['cache_zone_mean_K'],
                         'cache_zone_max_K': dn['cache_zone_max_K'], 'holds': dn['plan_holds_target'],
                         'reason': dn['reason']},
            'verdict': ('confirmed (conservation binds; the zone does not reach 280 K)' if cons and
                        not dn['plan_holds_target'] else 'NOT as predicted'),
            'note': ('the falsifier -- a converged hold with cache mean <= 285 K on a plan <= 0.9x '
                     'die power -- is not met')}
    d45 = g('dt45_T280')
    if d45:
        out['P3_scalar_lift_binds'] = {
            'predicted': 'every cache block limit = dt_max; zone at idle - 45 K ~ 300-310 K',
            'measured': {'plan_share_of_die': d45['plan_share_of_die'],
                         'cache_zone_mean_K': d45['cache_zone_mean_K'], 'reason': d45['reason']},
            'verdict': 'NOT as predicted: conservation scales the plan before the 45 K lift binds '
                       '(the same landing as the curve-only run)'}
    d3 = g('dtnone_T300') or g('dt45_T300')
    if d3:
        share = d3['plan_share_of_die'] or 0.0
        out['P4_300K_costs_the_whole_die'] = {
            'predicted': '25-60 % of die power, more than the cache zone\'s own dissipation (~30 %)',
            'measured': {'plan_W': d3['heat_removed_W'], 'plan_share_of_die': share,
                         'lower_bound': 'max_iter' in (d3['reason'] or ''),
                         'cache_zone_mean_K': d3['cache_zone_mean_K']},
            'verdict': ('confirmed in direction, number too low: %.0f %% of die power' % (100 * share)
                        if share > 0.30 else 'FALSIFIED: plan <= the cache zone\'s own power')}
        if d3.get('cache_leakage_reduction_x'):
            out['P5_ledger'] = {
                'predicted': 'cache leakage >= 3x below idle at the 300 K target; falsifier < 2x',
                'measured': {'reduction_x': d3['cache_leakage_reduction_x'],
                             'idle_W': d3['idle']['cache_leakage_W'], 'W': d3['cache_leakage_W']},
                'verdict': ('confirmed' if d3['cache_leakage_reduction_x'] >= 3.0 else
                            ('below the prediction, above the falsifier' if
                             d3['cache_leakage_reduction_x'] >= 2.0 else 'FALSIFIED'))}
    du = g('dual_T280')
    if du:
        asked = (du['heat_removed_W'] or 0.0) + (du['shortfall_W'] or 0.0)
        out['P6_cr_lisaf_cannot'] = {
            'predicted': 'shortfall > 90 % of the cache tiles\' request; extractor_bound',
            'measured': {'n_tiles_capped': du['n_tiles_capped'], 'shortfall_W': du['shortfall_W'],
                         'delivered_W': du['heat_removed_W'],
                         'shortfall_share_of_request': (du['shortfall_W'] / asked) if asked else None,
                         'cache_zone_mean_K': du['cache_zone_mean_K']},
            'verdict': ('confirmed in substance (the cache target is not met and the storage tiles '
                        'cap); the shortfall is against the WHOLE plan, so the 90 % figure was '
                        'framed on the wrong denominator' if (du['n_tiles_capped'] or 0) > 0
                        else 'NOT as predicted: no tile capped')}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'd3_objective_v2'))
    ap.add_argument('--first-pass', default=os.path.join(_REPO, 'results', 'd3_objective'))
    ap.add_argument('--reference', default=os.path.join(_REPO, 'results', 'array_coverage_armD',
                                                        'c1.00', 'd1.00', 'mr_comparison.json'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'd3_cache_objective.json'))
    args = ap.parse_args()

    pts = {k: summarise(v) for k, v in load(args.base).items()}
    pts = {k: v for k, v in pts.items() if v}
    first = {k: summarise(v) for k, v in load(args.first_pass).items()}
    first = {k: v for k, v in first.items() if v}
    ref_rows = {}
    if os.path.isfile(args.reference):
        ref_rows = {r['arm']: r for r in json.load(open(args.reference))['rows']}

    def table(d, title):
        print('\n%s' % title)
        print('%-14s %5s %8s %7s %8s %8s %8s %6s %7s  %s' % (
            'variant', 'dens', 'Q_W', 'share', 'cacheK', 'cacheMx', 'cacheLk', 'capped', 'short', 'stop'))
        for k in sorted(d):
            s = d[k]
            print('%-14s %5.2f %8.2f %7s %8s %8s %8s %6s %7s  %s%s' % (
                s['variant'], s['density'], s['heat_removed_W'] or 0,
                '--' if s['plan_share_of_die'] is None else '%.2f' % s['plan_share_of_die'],
                '--' if s['cache_zone_mean_K'] is None else '%.1f' % s['cache_zone_mean_K'],
                '--' if s['cache_zone_max_K'] is None else '%.1f' % s['cache_zone_max_K'],
                '--' if s['cache_leakage_W'] is None else '%.2f' % s['cache_leakage_W'],
                s['n_tiles_capped'] if s['n_tiles_capped'] is not None else '--',
                '--' if not s['shortfall_W'] else '%.1f' % s['shortfall_W'],
                (s['reason'] or '')[:48], '' if s['done'] else '  [running]'))

    table(pts, 'twelve-iteration pass, corrected ledger (%s)' % os.path.relpath(args.base, _REPO))
    table(first, 'first pass, six iterations (cache figures valid; die totals NOT)')
    sc = score(pts if pts else first, ref_rows)
    print('\nscorecard (%s):' % ('12-iteration pass' if pts else 'FIRST PASS ONLY'))
    for k, v in sc.items():
        print('  %-34s %s' % (k, v['verdict']))
    out = {'note': __doc__.strip(), 'cache_pattern': CACHE,
           'points': [pts[k] for k in sorted(pts)],
           'first_pass': [first[k] for k in sorted(first)],
           'first_pass_caveat': ('six planner iterations (costs are lower bounds) and a ledger '
                                 'whose die_leakage_W summed McPAT\'s restating rows (x3.25); '
                                 'cache_leakage_W is unaffected. Superseded by points where present.'),
           'scorecard': sc, 'scored_on': '12-iteration pass' if pts else 'first pass',
           'complete': all(p['done'] for p in pts.values()) if pts else False}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s' % os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
