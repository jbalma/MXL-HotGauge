#!/usr/bin/env python
"""§P0.37: the TWO-SINK gen-3 stack -- read ``results/two_sink/`` and score P1-P6.

    python examples/two_sink_report.py

Rows: isolation conductivity (100 um layer) [x far-face sink] x storage-array material
(Cr:LiSAF = ``crlisaf_T280`` / dye = ``dye_T280``; ``peak`` = the compute-die regression) x
density. Per row: where the cache zone landed, the plan and how much of it the STORAGE die's
own array carries, its share of the converged die power, cache leakage against the idle arm,
tiles capped, whether it held. An UNCONVERGED row is neither a hold nor a failure; a row with
s > 1 is envelope-only. X4's twin rows (``docs/evidence/gen3_stack.json``) are the comparison.
Every Cr:LiSAF figure is a ceiling at eta_EQE = 1; the isolation carries no via copper.
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


def rows_of(base):
    out = []
    for f in sorted(glob.glob(os.path.join(base, 'isok*', '*', 'd*', 'mr_comparison.json'))):
        j = json.load(open(f))
        m = re.search(r'isok([0-9.]+)(?:_bsink([0-9.]+))?/([^/]+)/d([0-9.]+)/', f)
        r = {x['arm']: x for x in j['rows']}
        on, idle = r.get('array_on') or {}, r.get('array_idle') or {}
        q, p = on.get('heat_removed_W'), on.get('p_chip_W')
        out.append({'iso_k': float(m.group(1)), 'bottom_sink_r_th': float(m.group(2)) if m.group(2) else None,
                    'objective': m.group(3), 'density': float(m.group(4)),
                    'source': os.path.relpath(f, _REPO),
                    'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE')),
                    'idle_diverged': bool(idle.get('diverged')), 'idle_peak_C': idle.get('peak_C'),
                    'idle_cache_mean_C': idle.get('cache_zone_mean_C'), 'idle_cache_leak_W': idle.get('cache_leakage_W'),
                    'on_diverged': bool(on.get('diverged')), 'on_unconverged': bool(on.get('unconverged')),
                    'holds': bool(on.get('mr_plan_holds_target')), 'reason': (on.get('mr_reason') or '')[:90],
                    # the planner's own tolerance is 2 K: a converged descent whose worst zone block
                    # is within it IS the hold (mr_plan_holds_target asks for <= target exactly)
                    'loop_converged': bool(on.get('mr_loop_converged')),
                    'zone_worst_excess_K': max([z.get('worst_excess_K') for z in (on.get('mr_zones') or {}).values()
                                                if z.get('worst_excess_K') is not None] or [None], key=lambda v: -1e9 if v is None else v),
                    'plan_W': q, 'storage_array_plan_W': on.get('storage_array_plan_W'),
                    'p_chip_W': p, 'p_injected_W': on.get('p_injected_W'),
                    'share': (q / p) if q and p else None,
                    'net_W': on.get('p_mr_net_W'), 'peak_C': on.get('peak_C'), 'peak_block': on.get('peak_block'),
                    'cache_mean_C': on.get('cache_zone_mean_C'), 'cache_max_C': on.get('cache_zone_max_C'),
                    'cache_leak_W': on.get('cache_leakage_W'), 'die_leak_W': on.get('die_leakage_W'),
                    'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped'),
                    'shortfall_W': (on.get('extractor') or {}).get('shortfall_W'),
                    'envelope_shape': on.get('mr_envelope_shape'), 'stack_spec': on.get('stack_spec')})
    return out


def held(r):
    """Held: not diverged / unconverged, s <= 1, and either the planner's flag or a converged
    descent whose worst block is inside the planner's 2 K tolerance."""
    if r is None or r.get('on_diverged') or r.get('on_unconverged') or (r.get('share') or 0) > 1.0:
        return False
    ex = r.get('zone_worst_excess_K')
    return bool(r.get('holds') or (r.get('loop_converged') and ex is not None and ex <= 2.0))


def _K(c):
    return None if c is None else c + 273.15


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'two_sink_v3'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'two_sink.json'))
    args = ap.parse_args()
    R = rows_of(args.base)
    queued = sorted(glob.glob(os.path.join(args.base, 'isok*', '*', 'd*')))
    print('%6s %5s %-13s %5s | %-16s | %-26s %7s %7s %5s %-18s %6s %6s' % (
        'iso k', 'bsink', 'objective', 'd', 'idle peak/cache', 'laser: peak/cache mean/max', 'plan', 'storage', 's', 'cache leak', 'capped', 'holds'))
    for r in sorted(R, key=lambda r: (r['density'], r['objective'], r['iso_k'], r['bottom_sink_r_th'] or 0)):
        idle = 'DIVERGED' if r['idle_diverged'] else '%.1f C / %s' % (r['idle_peak_C'] or 0, '--' if r['idle_cache_mean_C'] is None else '%.0f K' % _K(r['idle_cache_mean_C']))
        on = 'DIVERGED' if r['on_diverged'] else '%.1f C / %s / %s' % (
            r['peak_C'] or 0, '--' if r['cache_mean_C'] is None else '%.0f K' % _K(r['cache_mean_C']),
            '--' if r['cache_max_C'] is None else '%.0f K' % _K(r['cache_max_C']))
        f1 = lambda v, fmt='%.1f': '--' if v is None else fmt % v
        print('%6g %5s %-13s %5.2f | %-16s | %-26s %7s %7s %5s %-18s %6s %6s%s' % (
            r['iso_k'], f1(r['bottom_sink_r_th'], '%g'), r['objective'], r['density'], idle, on,
            f1(r['plan_W']), f1(r['storage_array_plan_W']), f1(r['share'], '%.2f'),
            '--' if r['cache_leak_W'] is None else '%.2f W (idle %s)' % (r['cache_leak_W'], f1(r['idle_cache_leak_W'], '%.2f')),
            r['tiles_capped'], 'yes' if held(r) else ('UNCONV' if r['on_unconverged'] else 'no'),
            '' if r['done'] else '  [running]'))
    # the recorded twins re-run with the cache-only zone pattern (D3 monolithic, X4 sink-side stack)
    twins = []
    for f in sorted(glob.glob(os.path.join(args.base, 'twin_*', '*', 'd*', 'mr_comparison.json'))):
        m = re.search(r'twin_([^/]+)/([^/]+)/d([0-9.]+)/', f)
        r = {x['arm']: x for x in json.load(open(f))['rows']}
        on, idle = r.get('array_on') or {}, r.get('array_idle') or {}
        q, p = on.get('heat_removed_W'), on.get('p_chip_W')
        twins.append({'twin': m.group(1), 'objective': m.group(2), 'density': float(m.group(3)),
                      'source': os.path.relpath(f, _REPO), 'plan_W': q, 'share': (q / p) if q and p else None,
                      'cache_mean_K': _K(on.get('cache_zone_mean_C')), 'cache_max_K': _K(on.get('cache_zone_max_C')),
                      'cache_leak_W': on.get('cache_leakage_W'), 'idle_cache_leak_W': idle.get('cache_leakage_W'),
                      'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped'),
                      'holds': bool(on.get('mr_plan_holds_target')), 'unconverged': bool(on.get('unconverged')),
                      'diverged': bool(on.get('diverged')), 'reason': (on.get('mr_reason') or '')[:90]})
    if twins:
        print('\nrecorded twins, cache-only zone pattern (recorded with L2Pred in the zone: monolithic 99.4 W, X4 99.3 W, s = 1.08):')
        for t in twins:
            print('  %-14s %-13s plan %s  s %s  zone %s / %s K  capped %s  holds %s' % (
                t['twin'], t['objective'], '--' if t['plan_W'] is None else '%.1f W' % t['plan_W'],
                '--' if t['share'] is None else '%.2f' % t['share'],
                '--' if t['cache_mean_K'] is None else '%.0f' % t['cache_mean_K'],
                '--' if t['cache_max_K'] is None else '%.0f' % t['cache_max_K'], t['tiles_capped'],
                'yes' if t['holds'] else ('UNCONV' if t['unconverged'] else 'no')))
    done = [d for d in queued if os.path.isfile(os.path.join(d, 'DONE'))]
    print('\n%d of %d points done' % (len(done), len(queued)))

    BS = 3.0            # the ladder's default far-face sink [K/W]; None = the adiabatic smoke row

    def pick(k, obj, d, bs=BS):
        for r in R:
            if (abs(r['iso_k'] - k) < 1e-9 and r['objective'] == obj and abs(r['density'] - d) < 1e-9
                    and r['bottom_sink_r_th'] == bs and r['done']):
                return r
        return None

    def brief(r):
        return None if r is None else {k: r[k] for k in ('plan_W', 'storage_array_plan_W', 'share', 'cache_mean_C', 'cache_max_C',
                                                           'cache_leak_W', 'idle_cache_leak_W', 'net_W', 'tiles_capped', 'shortfall_W',
                                                           'holds', 'loop_converged', 'zone_worst_excess_K', 'on_diverged', 'on_unconverged', 'peak_C', 'reason')}
    zoneK = lambda r: None if (r is None or r['cache_mean_C'] is None) else _K(r['cache_mean_C'])
    sc = {}
    # P1 (as amended): off the heat path the prize is cheap (dye storage array, k <= 0.1, 3 K/W far-face sink)
    rs = [pick(k, 'dye_T280', 1.00) for k in (0.025, 0.1)]
    if all(rs):
        ok = all((not r['on_diverged']) and zoneK(r) is not None and zoneK(r) <= 283 and r['plan_W'] is not None
                 and 7 <= r['plan_W'] <= 17 and (r['share'] or 9) <= 0.15 for r in rs)
        fals = (rs[0]['plan_W'] or 0) > 25 or any((zoneK(r) or 999) > 285 for r in rs)
        sc['P1_prize_is_cheap_off_the_heat_path'] = {'k0.025': brief(rs[0]), 'k0.1': brief(rs[1]), 'x4_plan_W': 99.3,
                                                     'verdict': 'confirmed' if ok else ('FALSIFIED' if fals else 'NOT as predicted')}
    # P2: Cr:LiSAF's isolation window
    a, b, c = (pick(k, 'crlisaf_T280', 1.00) for k in (0.025, 0.1, 0.5))
    if a and b and c:
        ok = ((a['tiles_capped'] or 0) == 0 and zoneK(a) <= 283 and (b['tiles_capped'] or 0) <= 10 and zoneK(b) <= 285
              and (c['tiles_capped'] or 0) >= 20 and zoneK(c) >= 290)
        fals = ((c['tiles_capped'] or 0) == 0 and zoneK(c) <= 283) or (a['tiles_capped'] or 0) > 0
        sc['P2_crlisaf_window'] = {'k0.025': brief(a), 'k0.1': brief(b), 'k0.5': brief(c),
                                   'verdict': 'confirmed' if ok else ('FALSIFIED' if fals else 'NOT as predicted')}
    # P3: the cost follows k/t
    lo, mid, hi = pick(0.025, 'dye_T280', 1.00), pick(0.5, 'dye_T280', 1.00), pick(5, 'dye_T280', 1.00)
    if lo and mid and hi and lo['plan_W'] and mid['plan_W']:
        ok = 24 <= mid['plan_W'] <= 40 and ((hi['plan_W'] or 0) >= 70 or (hi['share'] or 0) >= 1.0)
        fals = abs(mid['plan_W'] / lo['plan_W'] - 1.0) <= 0.20
        sc['P3_cost_follows_isolation'] = {'plan_by_k_W': {k: (pick(k, 'dye_T280', 1.00) or {}).get('plan_W') for k in (0.025, 0.1, 0.5, 5)},
                                           'share_k5': hi['share'],
                                           'verdict': 'confirmed' if ok else ('FALSIFIED' if fals else 'NOT as predicted')}
    # P4: the far-face sink is a liability at a sub-ambient target
    ad, sk, skc = pick(0.1, 'dye_T280', 1.00), pick(0.1, 'dye_T280', 1.00, 0.3), pick(0.1, 'crlisaf_T280', 1.00, 0.3)
    adia = pick(0.1, 'dye_T280', 1.00, None)
    if adia:
        sc['P0_adiabatic_far_face'] = {'idle_diverged': adia['idle_diverged'], 'on_diverged': adia['on_diverged'], 'reason': adia['reason'],
                                       'verdict': 'no idle steady state: the isolated storage die needs a heat path of its own'
                                       if adia['idle_diverged'] else 'idle holds'}
    if ad and sk and skc and ad['plan_W'] and sk['plan_W']:
        extra = sk['plan_W'] - ad['plan_W']
        ok = 30 <= extra <= 50 and (skc['tiles_capped'] or 0) >= 40
        sc['P4_own_sink_is_a_liability'] = {'adiabatic': brief(ad), 'sink_dye': brief(sk), 'sink_crlisaf': brief(skc), 'extra_W': extra, 'plan_bsink1_W': (pick(0.1, 'dye_T280', 1.00, 1.0) or {}).get('plan_W'),
                                            'verdict': 'confirmed' if ok else ('FALSIFIED' if abs(extra) <= 10 else 'NOT as predicted')}
    # P5: the compute die does not notice (X4's compute-die row: 121.8 W)
    r = pick(0.1, 'peak', 2.00)
    if r and r['plan_W']:
        dq = r['plan_W'] / 121.8 - 1.0
        sc['P5_compute_die_unchanged'] = {'plan_W': r['plan_W'], 'x4_plan_W': 121.8, 'ref_100um_W': 126.1, 'delta': dq, 'peak_C': r['peak_C'],
                                          'tiles_capped': r['tiles_capped'], 'holds': r['holds'],
                                          'verdict': 'confirmed' if abs(dq) <= 0.05 and r['holds'] else ('FALSIFIED' if abs(dq) > 0.10 else 'NOT as predicted')}
    # P6: the combined design point at 2.00
    comb = {('%s_k%g' % (m, k)): brief(pick(k, m + '_T280', 2.00)) for m in ('dye', 'crlisaf') for k in (0.025, 0.1, 0.5)}
    if all(v is not None for v in comb.values()):
        base = (sc.get('P5_compute_die_unchanged') or {}).get('plan_W')
        d1, d2 = comb['dye_k0.025'], comb['dye_k0.1']
        ok = all(held(d) and (d['share'] or 9) < 1 and _K(d['cache_mean_C']) <= 283 for d in (d1, d2))
        if ok and base:
            ok = all(9 <= d['plan_W'] - base <= 24 for d in (d1, d2))
        fals = d1['on_diverged'] or (d1['share'] or 0) >= 1
        sc['P6_combined_design_point'] = {'rows': comb, 'compute_only_plan_W': base,
                                          'verdict': 'confirmed' if ok else ('FALSIFIED' if fals else 'NOT as predicted')}
    print('\nscorecard:')
    for k, v in sc.items():
        print('  %-40s %s' % (k, v['verdict']))
    out = {'note': __doc__.strip(), 'grid_um': 100, 'iso_um': 100, 'rows': R, 'twins_cache_only_pattern': twins, 'scorecard': sc,
           'complete': len(done) == len(queued) and bool(queued)}
    json.dump(out, open(args.json_out, 'w'), indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
