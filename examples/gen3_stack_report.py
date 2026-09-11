#!/usr/bin/env python
"""X4 (§P0.27.4): the gen-3 two-die stack -- read ``results/gen3_stack/`` and score P14-P18.

    python examples/gen3_stack_report.py

Rows: bond conductivity x objective (dye curve-only / Cr:LiSAF dual at 280 K; the hot-spot
regression at 2.00) x density. Per row: the storage zone's landing, the plan and its share of
the converged die power, the cache leakage, the compute die's peak, tiles capped, whether the
stack held. P17 compares the 2.00 hot-spot row with the 100 um reference at 202 W
(``results/x3_u70/ref/array/W202.194``). An UNCONVERGED row is neither a hold nor a failure.
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
    for f in sorted(glob.glob(os.path.join(base, 'bondk*', '*', 'd*', 'mr_comparison.json'))):
        j = json.load(open(f))
        m = re.search(r'bondk([0-9.]+)/([^/]+)/d([0-9.]+)/', f)
        r = {x['arm']: x for x in j['rows']}
        on, idle = r.get('array_on') or {}, r.get('array_idle') or {}
        zone = on.get('zone_report') or {}
        out.append({'bond_k': float(m.group(1)), 'objective': m.group(2), 'density': float(m.group(3)),
                    'source': os.path.relpath(f, _REPO), 'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE')),
                    'idle_diverged': bool(idle.get('diverged')), 'idle_peak_C': idle.get('peak_C'),
                    'idle_cache_mean_C': idle.get('cache_zone_mean_C'), 'idle_cache_leak_W': idle.get('cache_leakage_W'),
                    'on_diverged': bool(on.get('diverged')), 'on_unconverged': bool(on.get('unconverged')),
                    'holds': bool(on.get('mr_plan_holds_target')), 'reason': (on.get('mr_reason') or '')[:90],
                    'plan_W': on.get('heat_removed_W'), 'p_chip_W': on.get('p_chip_W'), 'p_injected_W': on.get('p_injected_W'),
                    'share': (on['heat_removed_W'] / on['p_chip_W']) if on.get('heat_removed_W') and on.get('p_chip_W') else None,
                    'net_W': on.get('p_mr_net_W'), 'peak_C': on.get('peak_C'), 'peak_block': on.get('peak_block'),
                    'cache_mean_C': on.get('cache_zone_mean_C'), 'cache_max_C': on.get('cache_zone_max_C'),
                    'cache_leak_W': on.get('cache_leakage_W'), 'die_leak_W': on.get('die_leakage_W'),
                    'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped'),
                    'shortfall_W': (on.get('extractor') or {}).get('shortfall_W'),
                    'stack_spec': on.get('stack_spec')})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'gen3_stack'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'gen3_stack.json'))
    args = ap.parse_args()
    R = rows_of(args.base)
    queued = sorted(glob.glob(os.path.join(args.base, 'bondk*', '*', 'd*')))
    print('%6s %-9s %5s | %-22s | %-30s %6s %5s %-13s %7s %6s %6s' % (
        'bond k', 'objective', 'd', 'idle: peak / cache mean', 'laser: peak / cache mean/max', 'plan', 'share', 'cache leak', 'capped', 'holds', 'net'))
    for r in sorted(R, key=lambda r: (-r['bond_k'], r['objective'], -r['density'])):
        idle = 'DIVERGED' if r['idle_diverged'] else ('%.1f C / %s' % (r['idle_peak_C'] or 0, '%.0f K' % (r['idle_cache_mean_C'] + 273.15) if r['idle_cache_mean_C'] is not None else '--'))
        if r['on_diverged']:
            on = 'DIVERGED (no steady state)'
        else:
            on = '%.1f C / %s / %s' % (r['peak_C'] or 0, '%.0f K' % (r['cache_mean_C'] + 273.15) if r['cache_mean_C'] is not None else '--',
                                       '%.0f K' % (r['cache_max_C'] + 273.15) if r['cache_max_C'] is not None else '--')
        print('%6g %-9s %5.2f | %-22s | %-30s %6s %5s %-13s %7s %6s %6s%s' % (
            r['bond_k'], r['objective'], r['density'], idle, on,
            '--' if r['plan_W'] is None else '%.1f' % r['plan_W'], '--' if r['share'] is None else '%.2f' % r['share'],
            '--' if r['cache_leak_W'] is None else '%.2f W (idle %s)' % (r['cache_leak_W'], '%.2f' % r['idle_cache_leak_W'] if r['idle_cache_leak_W'] is not None else '--'),
            r['tiles_capped'], 'yes' if r['holds'] else ('UNCONV' if r['on_unconverged'] else 'no'),
            '--' if r['net_W'] is None else '%.0f' % r['net_W'], '' if r['done'] else '  [running]'))
    done = [d for d in queued if os.path.isfile(os.path.join(d, 'DONE'))]
    print('\n%d of %d points done' % (len(done), len(queued)))

    def pick(k, obj, d):
        for r in R:
            if abs(r['bond_k'] - k) < 1e-9 and r['objective'] == obj and abs(r['density'] - d) < 1e-9:
                return r
        return None
    sc = {}
    # P14: storage zone at its knee for 5-15 W of Cr:LiSAF at the default bond
    r = pick(50, 'dual_T280', 1.00)
    if r and r['done']:
        ok = (not r['on_diverged']) and r['cache_mean_C'] is not None and r['cache_mean_C'] + 273.15 <= 290 and r['plan_W'] is not None and r['plan_W'] <= 15
        sc['P14_storage_knee_cheaply'] = {'measured': {k: r[k] for k in ('cache_mean_C', 'cache_max_C', 'plan_W', 'holds', 'on_diverged', 'tiles_capped', 'shortfall_W')},
                                          'verdict': 'confirmed' if ok else ('FALSIFIED: > 40 W or zone above 300 K' if (r['plan_W'] or 0) > 40 or (r['cache_mean_C'] or 999) + 273.15 > 300 else 'NOT as predicted')}
    # P15: the bond decides -- cost ratio hybrid / microbump, and the zone landing
    a, b = pick(120, 'dye_T280', 1.00), pick(50, 'dye_T280', 1.00)
    if a and b and a['done'] and b['done'] and a['plan_W'] and b['plan_W']:
        ratio = a['plan_W'] / b['plan_W']
        sc['P15_bond_decides'] = {'plan_hybrid_W': a['plan_W'], 'plan_microbump_W': b['plan_W'], 'ratio': ratio,
                                  'zone_hybrid_K': (a['cache_mean_C'] or 0) + 273.15, 'zone_microbump_K': (b['cache_mean_C'] or 0) + 273.15,
                                  'verdict': 'confirmed' if ratio >= 3 else ('FALSIFIED: cost moves < 1.5x' if ratio < 1.5 else 'NOT as predicted')}
    # P16: the prize collected at a cost below it
    r = pick(50, 'dye_T280', 1.00)
    if r and r['done'] and r['cache_leak_W'] and r['idle_cache_leak_W']:
        red = r['idle_cache_leak_W'] / r['cache_leak_W']
        saved = r['idle_cache_leak_W'] - r['cache_leak_W']
        sc['P16_prize_collected'] = {'cache_leak_reduction_x': red, 'leakage_saved_W': saved, 'laser_net_W': r['net_W'],
                                     'verdict': ('confirmed' if 2.7 <= red <= 3.6 and r['net_W'] is not None and r['net_W'] < saved
                                                 else ('FALSIFIED: the laser draws more than it saves' if r['net_W'] is not None and r['net_W'] >= saved else 'NOT as predicted'))}
    # P17: the compute die unchanged at 2.00 (vs the 100 um reference at 202 W)
    r = pick(50, 'peak', 2.00)
    ref_f = os.path.join(_REPO, 'results', 'x3_u70', 'ref', 'array', 'W202.194', 'mr_comparison.json')
    if r and r['done'] and os.path.isfile(ref_f):
        ref = [x for x in json.load(open(ref_f))['rows'] if x['arm'] == 'array_on'][0]
        dq = (r['plan_W'] / ref['heat_removed_W'] - 1.0) if r['plan_W'] and ref.get('heat_removed_W') else None
        sc['P17_compute_die_unchanged'] = {'stack_plan_W': r['plan_W'], 'ref_100um_plan_W': ref.get('heat_removed_W'), 'plan_delta': dq,
                                           'stack_peak_C': r['peak_C'], 'ref_peak_C': ref.get('peak_C'), 'stack_holds': r['holds'],
                                           'verdict': ('open' if dq is None else ('confirmed' if abs(dq) <= 0.05 and r['holds'] else 'NOT as predicted'))}
    # P18: isolation vs the compute die's sink
    iso = {}
    for k in (120, 50, 5, 0.5):
        r = pick(k, 'dye_T280', 1.00)
        if r and r['done']:
            iso[k] = {'compute_diverged': r['on_diverged'] and r['idle_diverged'], 'idle_diverged': r['idle_diverged'], 'on_diverged': r['on_diverged'],
                      'zone_mean_K': None if r['cache_mean_C'] is None else r['cache_mean_C'] + 273.15, 'peak_C': r['peak_C'], 'plan_W': r['plan_W'], 'p_chip_W': r['p_chip_W'], 'holds': r['holds']}
    if iso:
        falsify = [k for k, v in iso.items() if v['zone_mean_K'] is not None and v['zone_mean_K'] <= 290 and v['holds'] and v['plan_W'] is not None and v['p_chip_W'] and v['plan_W'] < v['p_chip_W']]
        sc['P18_single_array_cannot_isolate'] = {'by_bond_k': iso, 'verdict': ('FALSIFIED: %s' % falsify if falsify else ('confirmed' if len(iso) == 4 else 'open'))}
    print('\nscorecard:')
    for k, v in sc.items():
        print('  %-34s %s' % (k, v['verdict']))
    out = {'note': __doc__.strip(), 'grid_um': 100, 'rows': R, 'scorecard': sc, 'complete': len(done) == len(queued) and bool(queued)}
    json.dump(out, open(args.json_out, 'w'), indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
