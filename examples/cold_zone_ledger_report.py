#!/usr/bin/env python
"""§P0.45: WHERE a cold memory zone pays -- read ``results/cold_zone_ledger[_power]/`` and score P1-P5.

    python examples/cold_zone_ledger_report.py

Rows: trace (hp = the recorded HP-cache trace; hpx4nolc = HP cells, longer-channel devices off, 4x L3)
x isolation k x objective (cache = caches at 280 K on the storage array; peak = the hot-spot objective
alone, the ALTERNATIVE) x density (hpx4nolc at MATCHED ACTIVITY: 1.268 / 2.536). The ledger per
(trace, k, density): saved = cache_leakage_W(peak) - cache_leakage_W(cache), cost = p_mr_net_W(cache)
- p_mr_net_W(peak); pays iff saved > cost. Two envelope shapes, seed and per-block (`_power`); P1-P3
are scored on the per-block rows, P4 on the seed rows against §P0.37's.
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
    for f in sorted(glob.glob(os.path.join(base, '*', '*', 'd*', 'mr_comparison.json'))):
        m = re.search(r'/(hp|hpx4nolc)_isok([0-9.]+)/(cache|peak)/d([0-9.]+)/', f)
        if not m:
            continue
        j = json.load(open(f))
        r = {x['arm']: x for x in j['rows']}
        on, idle = r.get('array_on') or {}, r.get('array_idle') or {}
        q, p = on.get('heat_removed_W'), on.get('p_chip_W')
        out.append({'trace': m.group(1), 'iso_k': float(m.group(2)), 'objective': m.group(3), 'density': float(m.group(4)),
                    'source': os.path.relpath(f, _REPO), 'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE')),
                    'shape': on.get('mr_envelope_shape'),
                    'idle_diverged': bool(idle.get('diverged')), 'idle_reason': (idle.get('diverged_reason') or '')[:60],
                    'idle_peak_C': idle.get('peak_C'), 'idle_cache_mean_C': idle.get('cache_zone_mean_C'), 'idle_cache_leak_W': idle.get('cache_leakage_W'),
                    'on_diverged': bool(on.get('diverged')), 'on_unconverged': bool(on.get('unconverged')),
                    'reason': (on.get('mr_reason') or on.get('diverged_reason') or '')[:80],
                    'holds': bool(on.get('mr_plan_holds_target')), 'loop_converged': bool(on.get('mr_loop_converged')),
                    'zone_worst_excess_K': max([z.get('worst_excess_K') for z in (on.get('mr_zones') or {}).values() if z.get('worst_excess_K') is not None] or [None], key=lambda v: -1e9 if v is None else v),
                    'plan_W': q, 'storage_array_plan_W': on.get('storage_array_plan_W'), 'p_chip_W': p, 'share': (q / p) if q and p else None,
                    'net_W': on.get('p_mr_net_W'), 'peak_C': on.get('peak_C'),
                    'cache_mean_C': on.get('cache_zone_mean_C'), 'cache_max_C': on.get('cache_zone_max_C'),
                    'cache_leak_W': on.get('cache_leakage_W'), 'die_leak_W': on.get('die_leakage_W'),
                    'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped')})
    return out


def held(r):
    if r is None or r.get('on_diverged') or r.get('on_unconverged') or (r.get('share') or 0) > 1.0:
        return False
    if (r.get('plan_W') or 0.0) == 0.0 and 'nothing above target' in (r.get('reason') or ''):
        return True                      # the unaided die already holds: the alternative EXISTS at 0 W
    ex = r.get('zone_worst_excess_K')
    return bool(r.get('holds') or (r.get('loop_converged') and ex is not None and ex <= 2.0))


def _f(v, fmt='%.1f'):
    return '--' if v is None else fmt % v


def ledger(R):
    """Per (trace, k, density): the cache row against the peak row."""
    out = {}
    for r in R:
        key = (r['trace'], r['iso_k'], r['density'])
        out.setdefault(key, {})[r['objective']] = r
    L = []
    for key, d in sorted(out.items()):
        c, pk = d.get('cache'), d.get('peak')
        e = {'trace': key[0], 'iso_k': key[1], 'density': key[2], 'cache': c, 'peak': pk,
             'cache_held': held(c), 'peak_held': held(pk)}
        if c and pk and held(c) and held(pk) and c['cache_leak_W'] is not None and pk['cache_leak_W'] is not None:
            e['saved_W'] = pk['cache_leak_W'] - c['cache_leak_W']
            e['cost_W'] = (c['net_W'] or 0.0) - (pk['net_W'] or 0.0)
            e['pays_by_W'] = e['saved_W'] - e['cost_W']
        elif c and held(c) and pk and not held(pk):
            e['note'] = 'the alternative (peak objective) has no hold: the cold zone is what makes the die viable'
            e['saved_W'] = None
            e['cost_W'] = (c['net_W'] or 0.0)
        L.append(e)
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'cold_zone_ledger.json'))
    args = ap.parse_args()
    bases = {'seed': os.path.join(_REPO, 'results', 'cold_zone_ledger'), 'power': os.path.join(_REPO, 'results', 'cold_zone_ledger_power')}
    allrows, ledgers = {}, {}
    for shape, base in bases.items():
        R = rows_of(base)
        allrows[shape] = R
        queued = sorted(glob.glob(os.path.join(base, '*', '*', 'd*')))
        done = [d for d in queued if os.path.isfile(os.path.join(d, 'DONE'))]
        print('\n== %s shape  (%d of %d points done) ==' % (shape, len(done), len(queued)))
        print('%-9s %6s %-6s %6s | %-24s | %-30s %7s %7s %5s %-20s %6s %5s' % ('trace', 'iso k', 'obj', 'd', 'idle: peak / cache', 'laser: peak / cache mean/max', 'plan', 'storage', 's', 'cache leak (idle)', 'net', 'holds'))
        for r in sorted(R, key=lambda r: (r['trace'], r['iso_k'], r['density'], r['objective'])):
            idle = 'DIVERGED %s' % r['idle_reason'][:14] if r['idle_diverged'] else '%s C / %s C' % (_f(r['idle_peak_C']), _f(r['idle_cache_mean_C']))
            on = 'DIVERGED' if r['on_diverged'] else '%s C / %s / %s C' % (_f(r['peak_C']), _f(r['cache_mean_C']), _f(r['cache_max_C']))
            print('%-9s %6g %-6s %6.3f | %-24s | %-30s %7s %7s %5s %-20s %6s %5s%s' % (
                r['trace'], r['iso_k'], r['objective'], r['density'], idle[:24], on[:30], _f(r['plan_W']), _f(r['storage_array_plan_W']), _f(r['share'], '%.2f'),
                '%s W (%s)' % (_f(r['cache_leak_W'], '%.2f'), _f(r['idle_cache_leak_W'], '%.2f')), _f(r['net_W']),
                'yes' if held(r) else ('UNCONV' if r['on_unconverged'] else 'no'), '' if r['done'] else '  [running]'))
        L = ledger(R)
        ledgers[shape] = L
        print('  ledger (cache row against the peak-objective alternative):')
        for e in L:
            if 'pays_by_W' in e:
                print('    %-9s k %-6g d %-6.3f saved %6.2f W  cost %6.2f W  -> %s by %.1f W' % (e['trace'], e['iso_k'], e['density'], e['saved_W'], e['cost_W'], 'PAYS' if e['pays_by_W'] > 0 else 'red', abs(e['pays_by_W'])))
            else:
                print('    %-9s k %-6g d %-6.3f cache %s, peak %s%s' % (e['trace'], e['iso_k'], e['density'], 'held' if e['cache_held'] else 'NOT held', 'held' if e['peak_held'] else 'NOT held', ('  -- ' + e['note']) if e.get('note') else ''))
    # scorecard (P1-P3 on the per-block rows; P4 on seed)
    sc = {}
    Lp = {(e['trace'], e['iso_k'], e['density']): e for e in ledgers.get('power', [])}
    Ls = {(e['trace'], e['iso_k'], e['density']): e for e in ledgers.get('seed', [])}

    def v(ok, fals):
        return 'confirmed' if ok else ('FALSIFIED' if fals else 'NOT as predicted')
    a, b = Lp.get(('hp', 0.025, 2.0)), Lp.get(('hp', 0.1, 2.0))
    if a and b and 'pays_by_W' in a and 'pays_by_W' in b:
        ok = (-6 <= a['pays_by_W'] <= -1 or -3 <= a['pays_by_W'] <= 0) and (-6 <= b['pays_by_W'] <= -1) and a['cache_held'] and (a['cache']['share'] or 9) < 1
        fals = a['pays_by_W'] > 0 or not a['cache_held']
        sc['P1_hp_at_2.00_closer_still_red'] = {'k0.025': {k: a[k] for k in ('saved_W', 'cost_W', 'pays_by_W')}, 'k0.1': {k: b[k] for k in ('saved_W', 'cost_W', 'pays_by_W')}, 'verdict': v(ok, fals)}
    elif a or b:
        sc['P1_hp_at_2.00_closer_still_red'] = {'k0.025': a and {k: a.get(k) for k in ('cache_held', 'peak_held', 'note')}, 'k0.1': b and {k: b.get(k) for k in ('cache_held', 'peak_held', 'note')}, 'verdict': 'NOT as predicted (a row not held)'}
    d1 = [x for x in Lp if x[0] == 'hpx4nolc' and x[2] < 2.0]
    if d1:
        e = Lp[min(d1, key=lambda x: x[1])]           # k 0.025
        c = e.get('cache') or {}
        ok = e['cache_held'] and (not e['peak_held']) and 10 <= (c.get('cache_leak_W') or 0) <= 17 and 20 <= (c.get('plan_W') or 0) <= 30 and bool((e.get('cache') or {}).get('idle_diverged'))
        fals = (e['peak_held'] and (e['peak']['plan_W'] or 0) < 10) or (e['cache_held'] and e.get('pays_by_W') is not None and e['pays_by_W'] < 0)
        sc['P2_hot_end_at_1.00_equiv_viable_only_cold'] = {'k0.025': {'cache_held': e['cache_held'], 'peak_held': e['peak_held'], 'cache_leak_W': c.get('cache_leak_W'), 'plan_W': c.get('plan_W'), 'net_W': c.get('net_W'), 'idle_diverged': c.get('idle_diverged'), 'peak_reason': (e.get('peak') or {}).get('reason')}, 'verdict': v(ok, fals)}
    d2 = [x for x in Lp if x[0] == 'hpx4nolc' and x[2] > 2.0]
    if d2:
        e = Lp[min(d2, key=lambda x: x[1])]
        c = e.get('cache') or {}
        ok = e['cache_held'] and 25 <= (c.get('storage_array_plan_W') or 0) <= 40
        sc['P3_hot_end_at_2.00_equiv'] = {'k0.025': {'cache_held': e['cache_held'], 'storage_array_plan_W': c.get('storage_array_plan_W'), 'plan_W': c.get('plan_W'), 'net_W': c.get('net_W'), 'reason': c.get('reason'), 'share': c.get('share')}, 'verdict': ('confirmed' if ok else ('planner-limited' if (c.get('share') or 0) >= 1 or not e['cache_held'] else 'NOT as predicted'))}
    s1 = [r for r in allrows.get('seed', []) if r['trace'] == 'hp' and r['objective'] == 'cache' and abs(r['density'] - 1.0) < 1e-9]
    if s1:
        ref = {0.025: 10.9, 0.1: 13.7}
        dev = {('%g' % r['iso_k']): (None if r['plan_W'] is None else 100 * (r['plan_W'] / ref[r['iso_k']] - 1)) for r in s1 if r['iso_k'] in ref}
        ok = all(v_ is not None and abs(v_) <= 15 for v_ in dev.values())
        sc['P4_scalar_vs_curve_only_at_1.00'] = {'deviation_pct_vs_P037': dev, 'verdict': 'confirmed' if ok else 'NOT as predicted'}
    sc['P5_matched_activity_densities'] = {'d1': 1.268, 'd2': 2.536, 'verdict': 'NOT as predicted (1.268 under the 1.3-1.6 band; 2.536 in band)'}
    print('\nscorecard:')
    for k, val in sc.items():
        print('  %-45s %s' % (k, val['verdict']))
    out = {'note': __doc__.strip(), 'rows': allrows, 'ledger': ledgers, 'scorecard': sc, 'dram_note': 'cache die, not DRAM: the §P0.37 stack'}
    json.dump(out, open(args.json_out, 'w'), indent=1, default=str)
    print('\nwritten:', os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
