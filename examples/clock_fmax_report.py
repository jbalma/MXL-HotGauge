#!/usr/bin/env python
"""§P0.31 part 2: the clock search on the generalized f_max model -- every arm's sustainable
clock, the limiter it names, the period's composition at the ceiling, and what 10 GHz would need.

    python examples/clock_fmax_report.py           # -> docs/evidence/clock_fmax.json

Reads ``results/clock_fmax/<run>/clock_headroom.json`` (``scripts/clock_fmax.sh``), restates each
row with IPC(f) (``docs/evidence/comet_ipc_vs_f.json``, FFT) beside the FLOP/s proxy, compares
the laser arm with the recorded F1c row at the same operating point (gate-only model), and
scores §P0.31 P4-P7. Every clock is UNCALIBRATED as F1c's were (the 3.8 GHz anchor).
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
ARMS = ('control', 'array_idle', 'array_on')
F1C = {'0.78': 'spice_d0.78', '1.00': 'spice_d1.00', '1.20': 'spice_d1.20'}


def f1c_rows(density):
    p = os.path.join(_REPO, 'results', 'clock_f1c_density', F1C.get('%.2f' % density, ''), 'clock_headroom.json')
    if not os.path.isfile(p):
        return {}
    return {r['arm']: r for r in json.load(open(p))['rows']}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'clock_fmax'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'clock_fmax.json'))
    ap.add_argument('--ipc-source', default=os.path.join(_EV, 'comet_ipc_vs_f.json'))
    ap.add_argument('--ipc-benchmark', default='fft_1to20')
    args = ap.parse_args()
    ipc = None
    if os.path.isfile(args.ipc_source):
        from comet_ipc_reader import load_ipc, ipc_at
        ipc = load_ipc(args.ipc_source, args.ipc_benchmark)
    runs = {}
    for f in sorted(glob.glob(os.path.join(args.base, '*', 'clock_headroom.json'))):
        tag = os.path.basename(os.path.dirname(f))
        j = json.load(open(f))
        d = j.get('density_at_trace_clock')
        old = f1c_rows(d) if d else {}
        rows = {}
        for r in j['rows']:
            fm = r.get('fmax') or {}
            fg = r.get('f_sustainable_GHz')
            cores = j.get('cores', 34)
            p_pkg = (r.get('p_chip_W') or 0) + (r.get('p_cool_W') or 0)
            ipc_f = ipc_at(ipc, fg) if (ipc and fg) else None
            o = old.get(r['arm'], {})
            rows[r['arm']] = {
                'f_GHz': fg, 'limited_by': r.get('limited_by'), 'bracket_GHz': r.get('bracket_GHz'),
                'peak_C': r.get('peak_C'), 'peak_block': r.get('peak_block'), 'p_chip_W': r.get('p_chip_W'),
                'p_pkg_W': p_pkg, 'heat_removed_W': r.get('heat_removed_W'), 'p_mr_net_W': r.get('p_mr_net_W'),
                'V_V': fm.get('V_used_V'), 'v_max_reliability_V': fm.get('v_max_reliability_V'),
                'reliability_binding': fm.get('reliability_binding'), 'T_eval_K': fm.get('T_eval_K'),
                'dT_core_K': fm.get('dT_eval_K'), 'period_terms': fm.get('period_terms'),
                'period_dominated_by': fm.get('period_dominated_by'),
                'ceiling_at_context': fm.get('ceiling_at_context'),
                'logic_depth_for_10GHz': fm.get('logic_depth_for_report_GHz'),
                'n_passes': fm.get('n_passes'), 'n_evaluations': len(r.get('evaluations') or []),
                'IPC_f': ipc_f, 'GIPS': (fg * ipc_f * cores) if ipc_f else None,
                'GIPS_per_package_W': (fg * ipc_f * cores / p_pkg) if (ipc_f and p_pkg) else None,
                'f1c_gate_only_GHz': o.get('f_sustainable_GHz'), 'f1c_limited_by': o.get('limited_by'),
                'evaluations': r.get('fmax_evaluations')}
        c = rows.get('control', {})
        for a, rr in rows.items():
            if c.get('f_GHz') and rr.get('f_GHz'):
                rr['clock_gain_vs_control'] = rr['f_GHz'] / c['f_GHz'] - 1.0
                if rr.get('GIPS') and c.get('GIPS'):
                    rr['throughput_gain_vs_control'] = rr['GIPS'] / c['GIPS'] - 1.0
        runs[tag] = {'density': d, 'vf_source': j.get('vf_source'), 'mr_target_C': j.get('mr_target_C'),
                     'mr_envelope_shape': j.get('mr_envelope_shape'), 'mr_extractor': j.get('mr_extractor'),
                     'model': (j.get('fmax_model') or {}).get('source_tag'),
                     'model_params': (j.get('fmax_model') or {}).get('params'),
                     'rows': rows, 'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE'))}
    for tag, R in runs.items():
        print('\n%s  (%.2f W/mm^2 at the trace clock, %s, target %.0f C, shape %s)%s' % (
            tag, R['density'] or 0, R['model'], R['mr_target_C'] or 0, R['mr_envelope_shape'], '' if R['done'] else '  [running]'))
        print('  %-10s %6s %-20s %6s %6s %-8s %6s %6s %6s %6s %6s %6s %6s %5s %6s %7s' % (
            'arm', 'f_GHz', 'limited by', 'V', 'Vmax', 'binding', 'peak', 'dTcore', 'Q_W', 'P_die', 'gate', 'wire', 'N@10G', 'pass', 'GIPS', 'F1c'))
        for a in ARMS:
            r = R['rows'].get(a)
            if not r:
                continue
            pt = r.get('period_terms') or {}
            print('  %-10s %6s %-20s %6s %6s %-8s %6s %6s %6s %6s %6s %6s %6s %5s %6s %7s' % (
                a, '--' if r['f_GHz'] is None else '%.3f' % r['f_GHz'], r['limited_by'],
                '--' if r['V_V'] is None else '%.3f' % r['V_V'], '--' if r['v_max_reliability_V'] is None else '%.3f' % r['v_max_reliability_V'],
                r['reliability_binding'] or '--', '--' if r['peak_C'] is None else '%.1f' % r['peak_C'],
                '--' if r['dT_core_K'] is None else '%.1f' % r['dT_core_K'], '--' if r['heat_removed_W'] is None else '%.1f' % r['heat_removed_W'],
                '--' if r['p_chip_W'] is None else '%.1f' % r['p_chip_W'],
                '--' if not pt else '%.2f' % pt.get('gate_frac', 0), '--' if not pt else '%.2f' % pt.get('wire_frac', 0),
                '--' if r['logic_depth_for_10GHz'] is None else '%.1f' % r['logic_depth_for_10GHz'], r['n_passes'] or '--',
                '--' if r['GIPS'] is None else '%.0f' % r['GIPS'], '--' if r['f1c_gate_only_GHz'] is None else '%.3f' % r['f1c_gate_only_GHz']))
    # ---- scoring §P0.31 P4-P7 ----
    def arm(run, a):
        return runs.get(run, {}).get('rows', {}).get(a, {})
    sc = {}
    c1, i1, o1 = arm('qual_d1.00', 'control'), arm('qual_d1.00', 'array_idle'), arm('qual_d1.00', 'array_on')
    if c1.get('f_GHz') and o1.get('f_GHz') and runs['qual_d1.00']['done']:
        thermal_c = str(c1['limited_by']).startswith(('over_thermal', 'thermal'))
        ok = (3.55 <= c1['f_GHz'] <= 3.70 and thermal_c and 4.20 <= o1['f_GHz'] <= 4.35 and str(o1['limited_by']) == 'reliability:tddb')
        fals = (str(o1['limited_by']).startswith(('over_thermal', 'thermal')) or o1['f_GHz'] > 4.5)
        sc['P4_1.00_three_arms'] = {'measured': {a: (arm('qual_d1.00', a).get('f_GHz'), arm('qual_d1.00', a).get('limited_by')) for a in ARMS},
                                    'plus_1.20': {a: (arm('qual_d1.20', a).get('f_GHz'), arm('qual_d1.20', a).get('limited_by')) for a in ARMS},
                                    'plus_0.78': {a: (arm('qual_d0.78', a).get('f_GHz'), arm('qual_d0.78', a).get('limited_by')) for a in ARMS},
                                    'verdict': 'FALSIFIED' if fals else ('confirmed' if ok else 'NOT as predicted')}
    t75, t60 = arm('qual_d1.00_T75', 'array_on'), arm('qual_d1.00_T60', 'array_on')
    if t75.get('f_GHz') and t60.get('f_GHz'):
        ok = (4.40 <= t75['f_GHz'] <= 4.60 and 4.55 <= t60['f_GHz'] <= 4.80 and all(str(x['limited_by']) == 'reliability:tddb' for x in (t75, t60)))
        fals = t60['f_GHz'] < 4.4 or str(t60['limited_by']) == 'device'
        sc['P5_target_knob'] = {'measured': {'75C': (t75['f_GHz'], t75['limited_by'], t75['heat_removed_W']), '60C': (t60['f_GHz'], t60['limited_by'], t60['heat_removed_W']),
                                             '92C': (o1.get('f_GHz'), o1.get('limited_by'), o1.get('heat_removed_W')),
                                             '1.20': {'75C': (arm('qual_d1.20_T75', 'array_on').get('f_GHz'), arm('qual_d1.20_T75', 'array_on').get('heat_removed_W')),
                                                      '60C': (arm('qual_d1.20_T60', 'array_on').get('f_GHz'), arm('qual_d1.20_T60', 'array_on').get('heat_removed_W'))}},
                                'verdict': 'FALSIFIED' if fals else ('confirmed' if ok else 'NOT as predicted')}
    n10c, n10o = arm('qual_d1.00_N10', 'control'), arm('qual_d1.00_N10', 'array_on')
    depths = [r.get('logic_depth_for_10GHz') for R in runs.values() for r in R['rows'].values() if r.get('logic_depth_for_10GHz')]
    if n10o.get('f_GHz') and depths:
        ok = (all(5.0 <= n <= 8.0 for n in depths) and 6.2 <= n10o['f_GHz'] <= 6.8 and str(n10o['limited_by']) == 'reliability:tddb'
              and 3.9 <= (n10c.get('f_GHz') or 0) <= 4.3)
        fals = n10o['f_GHz'] < 5.5 or n10o['f_GHz'] > 7.5
        sc['P6_10GHz_needs_the_pipeline'] = {'measured': {'logic_depth_for_10GHz_range': (min(depths), max(depths)),
                                                          'N10_control': (n10c.get('f_GHz'), n10c.get('limited_by')),
                                                          'N10_array_on': (n10o['f_GHz'], n10o['limited_by'], n10o['heat_removed_W'])},
                                             'verdict': 'FALSIFIED' if fals else ('confirmed' if ok else 'NOT as predicted')}
    nat = arm('native_d1.00', 'array_on')
    if nat.get('f_GHz'):
        sc['P7_native_budget'] = {'measured': (nat['f_GHz'], nat['limited_by'], nat['V_V'], nat['v_max_reliability_V'], nat['reliability_binding']),
                                  'verdict': 'FALSIFIED' if nat['f_GHz'] >= 3.8 else ('confirmed' if 3.3 <= nat['f_GHz'] <= 3.6 else 'NOT as predicted')}
    print('\nscorecard (§P0.31 part 2):')
    for k, v in sc.items():
        print('  %-30s %s   %s' % (k, v['verdict'], json.dumps(v['measured'])[:230]))
    out = {'note': __doc__.strip(), 'runs': runs, 'scorecard': sc, 'ipc_benchmark': args.ipc_benchmark if ipc else None,
           'complete': bool(runs) and all(R['done'] for R in runs.values())}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
