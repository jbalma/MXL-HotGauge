#!/usr/bin/env python
"""§P0.39: the RAIL model (V_eff = V_dd - IR) in the generalized clock search.

    python examples/clock_rail_report.py           # -> docs/evidence/clock_rail.json

Reads ``results/clock_rail/<member>/resize<k>/clock_headroom.json`` (``scripts/clock_rail.sh``): the
laser arm's sustainable clock, the limiter it names, the worst execution block's current density
against the native die's, the IR drop and the effective supply, and what ideal rails would have
given on the same solve. ``resizeoff`` is the rail-less twin. The reference die's rail-less twin is
§P0.31's (``results/clock_fmax/qual_d1.00``). Every clock is UNCALIBRATED (the 3.8 GHz anchor) and
carries its V/F source and limiter; IPC(f) from ``docs/evidence/comet_ipc_vs_f.json`` (FFT).
Static IR only: no L di/dt, no decap; rails sized for the native die to a 5 % budget (STATED).
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


def laser_row(path):
    if not os.path.isfile(path):
        return None, None
    j = json.load(open(path))
    r = next((x for x in j['rows'] if x['arm'] == 'array_on'), None)
    return j, r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'clock_rail'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'clock_rail.json'))
    ap.add_argument('--ipc-source', default=os.path.join(_EV, 'comet_ipc_vs_f.json'))
    ap.add_argument('--ipc-benchmark', default='fft_1to20')
    args = ap.parse_args()
    ipc = None
    if os.path.isfile(args.ipc_source):
        from comet_ipc_reader import load_ipc, ipc_at
        ipc = load_ipc(args.ipc_source, args.ipc_benchmark)
    rows, complete = [], True
    todo = sorted(glob.glob(os.path.join(args.base, '*', 'resize*')))
    sources = [(os.path.basename(os.path.dirname(d)), os.path.basename(d)[len('resize'):], os.path.join(d, 'clock_headroom.json'), d) for d in todo]
    sources.append(('ref_d1.00', 'off', os.path.join(_REPO, 'results', 'clock_fmax', 'qual_d1.00', 'clock_headroom.json'), None))
    for member, k, path, d in sources:
        j, r = laser_row(path)
        if d is not None:
            complete = complete and os.path.isfile(os.path.join(d, 'DONE'))
        if r is None:
            continue
        fm = r.get('fmax') or {}
        rail = fm.get('rail') or {}
        fg = r.get('f_sustainable_GHz')
        ipc_f = ipc_at(ipc, fg) if (ipc and fg) else None
        rows.append({'member': member, 'resize': k, 'source': os.path.relpath(path, _REPO), 'vf_source': j.get('vf_source'),
                     'f_GHz': fg, 'limited_by': r.get('limited_by'), 'bracket_GHz': r.get('bracket_GHz'),
                     'V_V': fm.get('V_used_V'), 'V_eff_V': rail.get('V_eff_V'), 'ir_drop_V': rail.get('ir_drop_V'),
                     'J_exec_max_A_per_mm2': rail.get('J_exec_max_A_per_mm2'), 'J_over_native': rail.get('J_over_native'),
                     'ideal_rails': rail.get('ideal_rails'), 'v_max_reliability_V': fm.get('v_max_reliability_V'),
                     'T_eval_K': fm.get('T_eval_K'), 'peak_C': r.get('peak_C'), 'peak_block': r.get('peak_block'),
                     'p_chip_W': r.get('p_chip_W'), 'heat_removed_W': r.get('heat_removed_W'),
                     'IPC_f': ipc_f, 'f_x_IPC': (fg * ipc_f) if ipc_f else None,
                     'mr_envelope_shape': j.get('mr_envelope_shape'),
                     'failed_candidates': [{'f_GHz': e.get('f_GHz'), 'reason': e.get('unsustainable_reason'),
                                            'J_over_native': ((e.get('rail') or {}).get('J_over_native')),
                                            'ir_drop_V': ((e.get('rail') or {}).get('ir_drop_V'))}
                                           for e in (r.get('fmax_evaluations') or []) if e.get('unsustainable_reason')][:6]})
    order = {'off': -1}
    rows.sort(key=lambda x: (x['member'], order.get(x['resize'], float(x['resize']) if x['resize'] != 'off' else -1)))
    print('%-10s %6s | %7s %-28s %6s %7s %7s %8s | %s' % ('member', 'resize', 'f GHz', 'limited by', 'V', 'IR mV', 'V_eff', 'J/J_nat', 'ideal-rail f_max at the same solve'))
    for x in rows:
        f = lambda v, fmt: '--' if v is None else fmt % v
        print('%-10s %6s | %7s %-28s %6s %7s %7s %8s | %s' % (
            x['member'], x['resize'], f(x['f_GHz'], '%.3f'), (x['limited_by'] or '')[:28], f(x['V_V'], '%.3f'),
            f(None if x['ir_drop_V'] is None else 1e3 * x['ir_drop_V'], '%.0f'), f(x['V_eff_V'], '%.3f'), f(x['J_over_native'], '%.1f'),
            f((x['ideal_rails'] or {}).get('f_max_GHz'), '%.3f')))
        for e in x['failed_candidates'][:2]:
            print('%19s failed %.3f GHz: %s (J/J_nat %s, IR %s mV)' % ('', e['f_GHz'], e['reason'], f(e['J_over_native'], '%.1f'),
                                                                        f(None if e['ir_drop_V'] is None else 1e3 * e['ir_drop_V'], '%.0f')))

    def pick(member, k):
        return next((x for x in rows if x['member'] == member and x['resize'] == k), None)
    sc = {}
    off, r1, r2 = pick('ref_d1.00', 'off'), pick('ref_d1.00', '1'), pick('ref_d1.00', '2')
    if off and r1 and r2 and off['f_GHz'] and r1['f_GHz']:
        loss = 1.0 - r1['f_GHz'] / off['f_GHz']
        ok = 0.01 <= loss <= 0.03 and (r2['f_GHz'] or 0) >= 0.997 * off['f_GHz'] and 1.3 <= (r1['J_over_native'] or 0) <= 1.6
        sc['P1_reference_barely_notices'] = {'measured': {'f_off': off['f_GHz'], 'f_resize1': r1['f_GHz'], 'f_resize2': r2['f_GHz'], 'loss': loss,
                                                          'J_over_native': r1['J_over_native'], 'ir_drop_V': r1['ir_drop_V'], 'limited_by': r1['limited_by']},
                                             'verdict': 'confirmed' if ok else ('FALSIFIED' if loss > 0.05 else 'NOT as predicted')}
    p2, p3, p4 = {}, {}, {}
    for member, kJ, khalf in (('x0.125', '8', '4'), ('x0.0625', '16', '8')):
        o, n1, nJ, nh = pick(member, 'off'), pick(member, '1'), pick(member, kJ), pick(member, khalf)
        if n1:
            p2[member] = {'f_GHz': n1['f_GHz'], 'limited_by': n1['limited_by'], 'J_over_native': n1['J_over_native'], 'ir_drop_V': n1['ir_drop_V'],
                          'first_failure': (n1['failed_candidates'] or [None])[0]}
        if o and nJ and o['f_GHz'] and nJ['f_GHz']:
            p3[member] = {'f_off': o['f_GHz'], 'f_at_Jx': nJ['f_GHz'], 'loss_at_Jx': 1 - nJ['f_GHz'] / o['f_GHz'],
                          'loss_at_half': (1 - nh['f_GHz'] / o['f_GHz']) if (nh and nh['f_GHz']) else None, 'J_over_native_at_Jx': nJ['J_over_native']}
        if o:
            p4[member] = {'f_off': o['f_GHz'], 'limited_by': o['limited_by'], 'peak_C': o['peak_C']}
    if len(p2) == 2:
        fals = any((v['f_GHz'] or 0) >= 3.0 for v in p2.values())
        ok = all((v['f_GHz'] or 0) <= 2.05 for v in p2.values())
        sc['P2_dense_cluster_on_native_rails_has_no_clock'] = {'measured': p2, 'verdict': 'FALSIFIED' if fals else ('confirmed' if ok else 'NOT as predicted')}
    if len(p3) == 2:
        ok = all(v['loss_at_Jx'] <= 0.03 for v in p3.values())
        sc['P3_resizing_by_J_restores_it'] = {'measured': p3, 'verdict': 'confirmed' if ok else ('FALSIFIED' if any(v['loss_at_Jx'] > 0.05 for v in p3.values()) else 'NOT as predicted')}
    if len(p4) == 2:
        ok = all(3.70 <= (v['f_off'] or 0) <= 3.83 for v in p4.values())
        sc['P4_rail_off_cluster_clock_is_the_references'] = {'measured': p4, 'verdict': 'confirmed' if ok else ('FALSIFIED' if any((v['f_off'] or 0) < 3.6 for v in p4.values()) else 'NOT as predicted')}
    print('\nscorecard (§P0.39):')
    for k, v in sc.items():
        print('  %-48s %s   %s' % (k, v['verdict'], json.dumps(v['measured'])[:320]))
    out = {'note': __doc__.strip(), 'rail': {'droop_native': 0.05, 'J_native_A_per_mm2': 44.45, 'sized_for': 'native_d0.78_control worst execution block'},
           'ipc_benchmark': args.ipc_benchmark if ipc else None, 'rows': rows, 'scorecard': sc, 'complete': complete and bool(todo)}
    with open(args.json_out, 'w') as fh:
        json.dump(out, fh, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
