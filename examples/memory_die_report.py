#!/usr/bin/env python
"""§P0.44: the memory die -- read ``results/memory_die/`` and score P1-P9.

    python examples/memory_die_report.py

Rows: placement (beside_gap<um> / sinkside_bondk<k> / farface_<iso>_bsink<R>) x n<dies>_w<W per
die> x density. Per row: the idle arm's verdict (a REFRESH runaway is the memory's own
divergence), the laser arm's plan split into the compute array's and the storage array's, where
the banks landed against 80 / 85 / 95 C, the refresh multiplier on the reported field, tiles
capped, whether it held. An UNCONVERGED row is neither a hold nor a failure; s > 1 is
envelope-only. Every DRAM number carries power/dram.py's UNCALIBRATED flag.
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
_ROW = re.compile(r'/(beside_gap(?P<gap>[0-9]+)|sinkside_bondk(?P<kb>[0-9.]+)|farface_(?P<iso>[^_/]+)_bsink(?P<bs>[0-9.]+)|reference_100um)'
                  r'/(?:n(?P<n>[0-9]+)_w(?P<w>[0-9.]+)|peak)/d(?P<d>[0-9.]+)/')


def rows_of(base):
    out = []
    for f in sorted(glob.glob(os.path.join(base, '*', '*', 'd*', 'mr_comparison.json'))):
        m = _ROW.search(f)
        if not m:
            continue
        j = json.load(open(f))
        r = {x['arm']: x for x in j['rows']}
        on, idle = r.get('array_on') or {}, r.get('array_idle') or {}
        q, p = on.get('heat_removed_W'), on.get('p_chip_W')
        g = m.groupdict()
        placement = ('beside' if g['gap'] else 'sink-side' if g['kb'] else 'far-face' if g['iso'] else 'reference')
        out.append({
            'placement': placement, 'gap_um': float(g['gap']) if g['gap'] else None,
            'bond_k': float(g['kb']) if g['kb'] else None, 'iso': g['iso'],
            'bottom_sink_r_th': float(g['bs']) if g['bs'] else None,
            'n_dies': int(g['n']) if g['n'] else 0, 'w_per_die': float(g['w']) if g['w'] else 0.0,
            'density': float(g['d']), 'source': os.path.relpath(f, _REPO),
            'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE')),
            'iso_k_effective': on.get('iso_k_effective_W_per_mK') or idle.get('iso_k_effective_W_per_mK'),
            'storage_k': on.get('storage_k_W_per_mK') or idle.get('storage_k_W_per_mK'),
            'mem_floor_W': on.get('mem_floor_W') or idle.get('mem_floor_W'),
            # idle arm
            'idle_diverged': bool(idle.get('diverged')), 'idle_reason': (idle.get('diverged_reason') or '')[:100],
            'idle_mem_diverged': bool(idle.get('mem_diverged')),
            'idle_peak_C': idle.get('peak_C'), 'idle_mem_max_C': idle.get('mem_zone_max_C'),
            'idle_mem_mean_C': idle.get('mem_zone_mean_C'), 'idle_mem_mult': idle.get('mem_refresh_mult_max'),
            'idle_mem_power_W': idle.get('mem_power_W'),
            # laser arm
            'on_diverged': bool(on.get('diverged')), 'on_unconverged': bool(on.get('unconverged')),
            'on_reason': (on.get('mr_reason') or on.get('diverged_reason') or '')[:100],
            'holds': bool(on.get('mr_plan_holds_target')), 'loop_converged': bool(on.get('mr_loop_converged')),
            'zone_worst_excess_K': max([z.get('worst_excess_K') for z in (on.get('mr_zones') or {}).values()
                                        if z.get('worst_excess_K') is not None] or [None],
                                       key=lambda v: -1e9 if v is None else v),
            'mem_zone': ((on.get('mr_zones') or {}).get('^MEM_')),
            'plan_W': q, 'storage_array_plan_W': on.get('storage_array_plan_W'),
            'compute_array_plan_W': ((q - on['storage_array_plan_W']) if (q is not None and on.get('storage_array_plan_W') is not None) else q),
            'p_chip_W': p, 'p_injected_W': on.get('p_injected_W'), 'share': (q / p) if q and p else None,
            'net_W': on.get('p_mr_net_W'), 'peak_C': on.get('peak_C'), 'peak_block': on.get('peak_block'),
            'mem_max_C': on.get('mem_zone_max_C'), 'mem_mean_C': on.get('mem_zone_mean_C'),
            'mem_peak_bank': on.get('mem_peak_bank'), 'mem_mult': on.get('mem_refresh_mult_max'),
            'mem_power_W': on.get('mem_power_W'), 'mem_over_break': on.get('mem_n_over_break'),
            'mem_over_limit': on.get('mem_n_over_limit'), 'mem_iterations': on.get('mem_iterations'),
            'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped'),
            'shortfall_W': (on.get('extractor') or {}).get('shortfall_W'),
            'envelope_shape': on.get('mr_envelope_shape'), 'stack_spec': on.get('stack_spec')})
    return out


def held(r):
    """Held: not diverged / unconverged, s <= 1, and the planner's flag or a converged descent
    with the worst block inside the planner's 2 K tolerance (two_sink_report's rule)."""
    if r is None or r.get('on_diverged') or r.get('on_unconverged') or (r.get('share') or 0) > 1.0:
        return False
    ex = r.get('zone_worst_excess_K')
    return bool(r.get('holds') or (r.get('loop_converged') and ex is not None and ex <= 2.0))


def _f(v, fmt='%.1f'):
    return '--' if v is None else fmt % v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'memory_die'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'memory_die.json'))
    args = ap.parse_args()
    R = rows_of(args.base)
    queued = sorted(glob.glob(os.path.join(args.base, '*', '*', 'd*')))
    print('%-10s %-9s %5s %2s %3s %5s | %-30s | %-34s %7s %7s %7s %5s %4s %6s %5s' % (
        'placement', 'variant', 'bsink', 'n', 'W', 'd', 'idle: peak / mem max (mult)',
        'laser: peak / mem mean / max (mult)', 'plan', 'compute', 'storage', 's', '>85C', 'capped', 'holds'))
    key = lambda r: ({'reference': 0, 'beside': 1, 'sink-side': 2, 'far-face': 3}[r['placement']],
                     r['density'], r['gap_um'] or 0, r['bond_k'] or 0, r['iso'] or '', r['bottom_sink_r_th'] or 0,
                     r['n_dies'], r['w_per_die'])
    for r in sorted(R, key=key):
        var = ('gap %g' % r['gap_um'] if r['gap_um'] else 'bond %g' % r['bond_k'] if r['bond_k'] else (r['iso'] or '--'))
        idle = ('DIVERGED%s' % (' (refresh)' if r['idle_mem_diverged'] else '') if r['idle_diverged']
                else '%s C / %s C (%s)' % (_f(r['idle_peak_C']), _f(r['idle_mem_max_C']), _f(r['idle_mem_mult'], '%.2f')))
        on = ('DIVERGED' if r['on_diverged'] else '%s C / %s / %s C (%s)' % (
            _f(r['peak_C']), _f(r['mem_mean_C']), _f(r['mem_max_C']), _f(r['mem_mult'], '%.2f')))
        print('%-10s %-9s %5s %2d %3g %5.2f | %-30s | %-34s %7s %7s %7s %5s %4s %6s %5s%s' % (
            r['placement'], var, _f(r['bottom_sink_r_th'], '%g'), r['n_dies'], r['w_per_die'], r['density'], idle, on,
            _f(r['plan_W']), _f(r['compute_array_plan_W']), _f(r['storage_array_plan_W']), _f(r['share'], '%.2f'),
            _f(r['mem_over_break'], '%d'), _f(r['tiles_capped'], '%d'),
            'yes' if held(r) else ('UNCONV' if r['on_unconverged'] else 'no'), '' if r['done'] else '  [running]'))
    done = [d for d in queued if os.path.isfile(os.path.join(d, 'DONE'))]
    print('\n%d of %d points done' % (len(done), len(queued)))

    def pick(placement, d=2.00, n=8, w=3.0, gap=None, kb=None, iso=None, bs=None):
        for r in R:
            if (r['placement'] == placement and abs(r['density'] - d) < 1e-9 and r['n_dies'] == n
                    and abs(r['w_per_die'] - w) < 1e-9 and (gap is None or r['gap_um'] == gap)
                    and (kb is None or r['bond_k'] == kb) and (iso is None or r['iso'] == iso)
                    and (bs is None or r['bottom_sink_r_th'] == bs) and r['done']):
                return r
        return None

    def brief(r):
        return None if r is None else {k: r[k] for k in (
            'plan_W', 'compute_array_plan_W', 'storage_array_plan_W', 'share', 'net_W', 'peak_C', 'mem_mean_C', 'mem_max_C',
            'mem_mult', 'mem_over_break', 'mem_over_limit', 'tiles_capped', 'holds', 'loop_converged', 'zone_worst_excess_K',
            'on_diverged', 'on_unconverged', 'on_reason', 'idle_diverged', 'idle_mem_diverged', 'idle_mem_max_C', 'idle_reason')}

    def verdict(ok, fals):
        return 'confirmed' if ok else ('FALSIFIED' if fals else 'NOT as predicted')
    sc = {}
    ref = pick('reference', n=0, w=0.0)
    ref_plan = ref['plan_W'] if ref else None
    # P1: the idle memory die's steady state is set by its heat path; refresh runaway is its own divergence
    p1 = {bs: pick('far-face', iso='vias', bs=bs) for bs in (1, 3, 10)}
    p1w = pick('far-face', iso='vias', bs=3, w=1.0)
    if all(p1.values()):
        ok = ((not p1[1]['idle_diverged']) and p1[3]['idle_diverged'] and p1[3]['idle_mem_diverged']
              and p1[10]['idle_diverged'] and p1[10]['idle_mem_diverged'])
        fals = (not p1[3]['idle_diverged']) or p1[1]['idle_diverged']
        if p1w:
            ok = ok and not p1w['idle_diverged']
        sc['P1_idle_state_set_by_heat_path'] = {'R1': brief(p1[1]), 'R3': brief(p1[3]), 'R10': brief(p1[10]),
                                               'R3_1W': brief(p1w), 'verdict': verdict(ok, fals)}
    # P2: what the storage array pays at the far face
    v3, v1, v10 = pick('far-face', iso='vias', bs=3), pick('far-face', iso='vias', bs=1), pick('far-face', iso='vias', bs=10)
    k5_3, k01_3 = pick('far-face', iso='k5', bs=3), pick('far-face', iso='k0.1', bs=3)
    if v3 and v1 and v10 and k5_3:
        s = lambda r: (r['storage_array_plan_W'] or 0.0)
        ok = (held(v3) and 3 <= s(v3) <= 8 and held(v1) and s(v1) <= 1.0 and held(v10) and 16 <= s(v10) <= 24
              and 25 <= s(k5_3) <= 45)
        fals = s(v3) > 12 or (k5_3['done'] and s(k5_3) < 15 and not k5_3['on_diverged'])
        sc['P2_far_face_storage_array_cost'] = {'vias_R1': brief(v1), 'vias_R3': brief(v3), 'vias_R10': brief(v10),
                                                'k5_R3': brief(k5_3), 'k0.1_R3': brief(k01_3), 'verdict': verdict(ok, fals)}
    # P3: the far face as a second heat path for the compute die
    k5_1 = pick('far-face', iso='k5', bs=1)
    if ref_plan and k5_1 and v1 and v3 and v10:
        c = lambda r: r['compute_array_plan_W']
        ok = (c(k5_1) is not None and 20 <= ref_plan - c(k5_1) <= 40
              and all(abs(c(r) - ref_plan) <= 5 for r in (v1, v3, v10) if c(r) is not None))
        fals = (c(k5_1) is not None and c(k5_1) > ref_plan) or any(abs(c(r) - ref_plan) > 10 for r in (v1, v3, v10) if c(r) is not None)
        sc['P3_far_face_is_a_second_heat_path'] = {'reference_plan_W': ref_plan, 'k5_R1': brief(k5_1),
                                                   'compute_plan_by_R_vias': {R: c(r) for R, r in ((1, v1), (3, v3), (10, v10))},
                                                   'verdict': verdict(ok, fals)}
    # P4: sink-side -- cheap for one die, dear for a stack
    ss = {(n, kb): pick('sink-side', n=n, kb=kb) for n in (1, 8) for kb in (5, 50)}
    if all(ss.values()):
        a, b, c8, d8 = ss[(1, 50)], ss[(1, 5)], ss[(8, 50)], ss[(8, 5)]
        ok = (held(a) and 135 <= (a['plan_W'] or 0) <= 165 and (a['mem_max_C'] or 99) <= 82
              and held(b) and 0 <= (b['plan_W'] or 0) - (a['plan_W'] or 0) <= 15
              and ((held(c8) and 175 <= (c8['plan_W'] or 0) <= 220) or not held(c8))
              and ((not held(d8)) or (d8['plan_W'] or 0) >= 220))
        fals = (held(d8) and (d8['plan_W'] or 0) < 180) or (held(a) and (a['plan_W'] or 0) > 170)
        sc['P4_sink_side_cheap_for_one_die_dear_for_a_stack'] = {'n1_k50': brief(a), 'n1_k5': brief(b), 'n8_k50': brief(c8), 'n8_k5': brief(d8),
                                                                 'x4_compute_row_W': 121.8, 'verdict': verdict(ok, fals)}
    # P5: beside costs nothing and the gap does not matter
    bs_ = {g: pick('beside', gap=g) for g in (500, 1000, 2000)}
    if all(bs_.values()) and ref_plan:
        mx = [r['mem_max_C'] for r in bs_.values() if r['mem_max_C'] is not None]
        st = [r['storage_array_plan_W'] or 0.0 for r in bs_.values()]
        ok = (all(held(r) for r in bs_.values()) and all(60 <= v <= 78 for v in mx) and max(st) <= 0.5
              and all(abs((r['plan_W'] or 0) / ref_plan - 1) <= 0.10 for r in bs_.values()) and (max(mx) - min(mx)) < 3)
        fals = any(v > 85 for v in mx) or (max(mx) - min(mx)) > 6
        sc['P5_beside_costs_nothing'] = {('gap_%d' % g): brief(r) for g, r in bs_.items()}
        sc['P5_beside_costs_nothing'].update({'reference_plan_W': ref_plan, 'mem_max_spread_K': (max(mx) - min(mx)) if mx else None,
                                              'verdict': verdict(ok, fals)})
    # P6: the multiplier is 1.0 in every held row
    hr = [r for r in R if r['done'] and held(r) and r['placement'] != 'reference']
    if hr:
        bad = [r['source'] for r in hr if (r['mem_mult'] or 1.0) > 1.0 + 1e-6]
        sc['P6_multiplier_is_one_when_held'] = {'n_held': len(hr), 'held_rows_with_m_gt_1': bad,
                                                'verdict': 'confirmed' if not bad else 'FALSIFIED'}
    # P7: 1 W per die moves the far-face verdicts, not the sink-side ones
    w1f, w1s, w3s = pick('far-face', iso='vias', bs=3, w=1.0), pick('sink-side', kb=5, w=1.0), pick('sink-side', kb=5)
    if w1f and w1s and w3s:
        ok = ((w1f['storage_array_plan_W'] or 0) <= 2 and not w1f['idle_diverged']
              and (w1s['plan_W'] is not None and w3s['plan_W'] is not None and abs(w1s['plan_W'] - w3s['plan_W']) <= 5))
        fals = (w1s['plan_W'] is not None and w3s['plan_W'] is not None and abs(w1s['plan_W'] - w3s['plan_W']) > 15)
        sc['P7_one_watt_per_die'] = {'far_face_vias_R3_1W': brief(w1f), 'sink_side_k5_1W': brief(w1s), 'sink_side_k5_3W': brief(w3s),
                                     'verdict': verdict(ok, fals)}
    # P8: at 1.00 W/mm^2
    s1, f1, b1 = pick('sink-side', d=1.00, kb=5), pick('far-face', d=1.00, iso='vias', bs=3), pick('beside', d=1.00, gap=1000)
    if s1 and f1 and b1:
        ok = ((s1['plan_W'] or 0) <= 1.0 and (s1['mem_max_C'] or 99) <= 65 and 3 <= (f1['storage_array_plan_W'] or 0) <= 8 and (b1['plan_W'] or 0) <= 1.0)
        fals = (s1['plan_W'] or 0) > 10 or (b1['plan_W'] or 0) > 10
        sc['P8_at_1.00'] = {'sink_side': brief(s1), 'far_face': brief(f1), 'beside': brief(b1), 'verdict': verdict(ok, fals)}
    # P9: the proximity trade priced
    if ref_plan and v3 and bs_.get(1000) and ss.get((1, 50)) and ss.get((8, 5)):
        sc['P9_proximity_trade_priced_W'] = {
            'beside_extra_over_reference': (bs_[1000]['plan_W'] or 0) - ref_plan if bs_[1000]['plan_W'] else None,
            'far_face_vias_R3_storage_array': v3['storage_array_plan_W'], 'far_face_vias_R3_net_laser': v3['net_W'],
            'sink_side_n1_k50_extra': (ss[(1, 50)]['plan_W'] or 0) - ref_plan if ss[(1, 50)]['plan_W'] else None,
            'sink_side_n8_k5_extra_or_verdict': ((ss[(8, 5)]['plan_W'] or 0) - ref_plan) if held(ss[(8, 5)]) else ss[(8, 5)]['on_reason'],
            'comet_3d_over_2p5d_pct': '+1 to +6 (§P0.43)'}
    print('\nscorecard:')
    for k, v in sc.items():
        print('  %-50s %s' % (k, v.get('verdict', '(priced)')))
    out = {'note': __doc__.strip(), 'grid_um': 100, 'rows': R, 'scorecard': sc,
           'complete': len(done) == len(queued) and bool(queued), 'dram_calibrated': False}
    json.dump(out, open(args.json_out, 'w'), indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
