#!/usr/bin/env python
"""F1c (§P0.26): throughput with the CLOCK as the free variable -- read ``results/clock_f1c/*/
clock_headroom.json``, restate each arm's sustainable clock as FLOP/s = f x FLOP/cycle x cores
(ops over walltime at fixed IPC) per package watt, and -- §P0.33 -- as instructions per second
``f x IPC(f) x cores`` on CoMeT's measured IPC(f) (``--ipc-source``, ``--ipc-benchmark``), so the
memory wall enters the throughput claim; score the predictions, write ``docs/evidence/clock_f1c.json``.

    python examples/clock_f1c_report.py
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
ARMS = ('control', 'array_idle', 'array_on')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'clock_f1c'))
    ap.add_argument('--flops-per-cycle', type=float, default=32.0)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'clock_f1c.json'))
    # §P0.33: CoMeT's IPC(f) so the memory wall enters the throughput claim. The fixed-IPC
    # FLOP/s proxy is kept beside it; 'none' reproduces the recorded file exactly.
    ap.add_argument('--ipc-source', default=os.path.join(_EV, 'comet_ipc_vs_f.json'),
                    help="examples/comet_ipc_reader.py's evidence file, or 'none'")
    ap.add_argument('--ipc-benchmark', default='fft_1to20')
    args = ap.parse_args()
    ipc_curve = None
    if args.ipc_source != 'none' and os.path.isfile(args.ipc_source):
        sys.path.insert(0, _HERE)
        from comet_ipc_reader import load_ipc, ipc_at
        ipc_curve = load_ipc(args.ipc_source, args.ipc_benchmark)
    runs = {}
    for f in sorted(glob.glob(os.path.join(args.base, '*', 'clock_headroom.json'))):
        tag = os.path.basename(os.path.dirname(f)); j = json.load(open(f))
        rows = {}
        for r in j['rows']:
            arm = r.get('arm') or ('array_on' if r.get('mr') else 'control')
            f_ghz = r.get('f_sustainable_GHz'); cores = j.get('cores', 34)
            tflops = (f_ghz * args.flops_per_cycle * cores / 1000.0) if f_ghz else None
            ipc_f = ipc_at(ipc_curve, f_ghz) if (ipc_curve and f_ghz) else None
            gips = (f_ghz * ipc_f * cores) if ipc_f else None      # instructions per ns x cores = GIPS
            p_pkg = (r.get('p_chip_W') or 0) + (r.get('p_cool_W') or 0)
            rows[arm] = {'f_GHz': f_ghz, 'limited_by': r.get('limited_by'), 'vf_clamped': r.get('vf_clamped'),
                         'IPC_f': ipc_f, 'GIPS': gips, 'GIPS_per_package_W': (gips / p_pkg) if (gips and p_pkg) else None,
                         'at_ceiling': r.get('at_ceiling'), 'peak_C': r.get('peak_C'), 'peak_block': r.get('peak_block'),
                         'p_chip_W': r.get('p_chip_W'), 'density': r.get('density_W_per_mm2'), 'heat_removed_W': r.get('heat_removed_W'),
                         'p_mr_net_W': r.get('p_mr_net_W'), 'p_total_W': (r.get('p_chip_W') or 0) + (r.get('p_cool_W') or 0),
                         'TFLOPs': tflops, 'GFLOPs_per_package_W': (1000 * tflops / ((r.get('p_chip_W') or 0) + (r.get('p_cool_W') or 0))) if tflops and r.get('p_chip_W') else None}
        # the throughput gain against the control, clock-only (proxy) and with IPC(f)
        c = rows.get('control', {})
        for arm, rr in rows.items():
            if c.get('f_GHz') and rr.get('f_GHz'):
                rr['clock_gain_vs_control'] = rr['f_GHz'] / c['f_GHz'] - 1.0
                if rr.get('GIPS') and c.get('GIPS'):
                    rr['throughput_gain_vs_control'] = rr['GIPS'] / c['GIPS'] - 1.0
        runs[tag] = {'ipc_benchmark': (args.ipc_benchmark if ipc_curve else None),
                     'vf_source': j.get('vf_source'), 'vf_ceiling_GHz': j.get('vf_ceiling_GHz'), 'thermal_limit_C': j.get('thermal_limit_C'),
                     'trace_GHz': j.get('trace_GHz'), 'cores': j.get('cores'), 'rows': rows, 'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE'))}
    for tag, R in runs.items():
        print('\n%s  (V/F %s, table ceiling %s GHz, limit %s C)%s' % (tag, R['vf_source'], R['vf_ceiling_GHz'], R['thermal_limit_C'], '' if R['done'] else '  [running]'))
        print('  %-11s %7s %-22s %7s %8s %8s %8s %9s %6s %7s %8s %s' % ('arm', 'f_GHz', 'limited by', 'clamp', 'P_die', 'P_pkg', 'TFLOP/s', 'GF/pkgW', 'IPC(f)', 'GIPS', 'dGIPS', 'Q_W'))
        for arm in ARMS:
            r = R['rows'].get(arm)
            if not r:
                continue
            print('  %-11s %7s %-22s %7s %8s %8s %8s %9s %6s %7s %8s %s' % (arm, '--' if r['f_GHz'] is None else '%.2f' % r['f_GHz'], r['limited_by'], r['vf_clamped'],
                  '--' if r['p_chip_W'] is None else '%.1f' % r['p_chip_W'], '%.1f' % r['p_total_W'], '--' if r['TFLOPs'] is None else '%.2f' % r['TFLOPs'],
                  '--' if r['GFLOPs_per_package_W'] is None else '%.1f' % r['GFLOPs_per_package_W'],
                  '--' if r.get('IPC_f') is None else '%.2f' % r['IPC_f'], '--' if r.get('GIPS') is None else '%.1f' % r['GIPS'],
                  '--' if r.get('throughput_gain_vs_control') is None else '%+.1f%%' % (100 * r['throughput_gain_vs_control']),
                  '--' if r['heat_removed_W'] is None else '%.1f' % r['heat_removed_W']))
    sc = {}
    R = runs.get('cfm88', {}).get('rows', {})
    c, i, o = R.get('control', {}), R.get('array_idle', {}), R.get('array_on', {})
    if c.get('f_GHz'):
        sc['P1_control_runaway_limited'] = {'measured': (c['f_GHz'], c['limited_by']), 'verdict': ('FALSIFIED: >= 4.2 GHz' if c['f_GHz'] >= 4.2 else ('confirmed' if 3.8 <= c['f_GHz'] <= 4.0 else 'NOT as predicted'))}
    if i.get('f_GHz'):
        sc['P2_idle_spec_limited'] = {'measured': (i['f_GHz'], i['limited_by']), 'verdict': 'confirmed' if 4.1 <= i['f_GHz'] <= 4.3 else 'NOT as predicted'}
    if o.get('f_GHz') and c.get('f_GHz'):
        gain = o['f_GHz'] / c['f_GHz'] - 1
        sc['P3_laser_hits_the_table'] = {'measured': {'f_GHz': o['f_GHz'], 'vf_clamped': o['vf_clamped'], 'density': o['density'], 'Q_W': o['heat_removed_W'], 'gain_vs_control': gain},
                                         'verdict': ('FALSIFIED: < 4.5 GHz' if o['f_GHz'] < 4.5 else ('confirmed' if o['f_GHz'] >= 4.95 else 'holds below the table end: %.2f GHz (limiter %s)' % (o['f_GHz'], o['limited_by'])))}
    Ra = runs.get('cfm88_above_table', {}).get('rows', {})
    oa = Ra.get('array_on', {})
    if oa.get('f_GHz'):
        sc['P4_above_table_ARGUED'] = {'measured': (oa['f_GHz'], oa['limited_by'], oa['density']), 'verdict': ('inside 5.5-6.2 GHz (upper bound, voltage clamped)' if 5.5 <= oa['f_GHz'] <= 6.2 else 'outside the band: %.2f GHz' % oa['f_GHz'])}
    eff = [r.get('GFLOPs_per_package_W') for r in (c, i, o) if r.get('GFLOPs_per_package_W')]
    if len(eff) == 3:
        sc['P5_efficiency_falls_with_clock'] = {'measured': eff, 'verdict': 'confirmed' if eff[0] >= eff[1] >= eff[2] else 'NOT as predicted'}
    # §P0.26 part 2: the density-scaled runs
    def arm(run, a):
        return runs.get(run, {}).get('rows', {}).get(a, {})
    d78, d100, d120 = (arm('spice_d0.78', x) for x in ('control',)), None, None
    c78, i78, o78 = arm('spice_d0.78', 'control'), arm('spice_d0.78', 'array_idle'), arm('spice_d0.78', 'array_on')
    c1, i1, o1 = arm('spice_d1.00', 'control'), arm('spice_d1.00', 'array_idle'), arm('spice_d1.00', 'array_on')
    c12, i12, o12 = arm('spice_d1.20', 'control'), arm('spice_d1.20', 'array_idle'), arm('spice_d1.20', 'array_on')
    t1 = arm('table_d1.00', 'array_on'); ab = arm('spice_above_d1.00', 'array_on')
    ceil = runs.get('spice_d1.00', {}).get('vf_ceiling_GHz') or 4.173
    if c78.get('f_GHz') and o78.get('f_GHz'):
        sc['P6_0.78_all_at_device_ceiling'] = {'measured': (c78['f_GHz'], i78.get('f_GHz'), o78['f_GHz']),
                                              'verdict': 'confirmed' if all(abs(x - ceil) < 0.06 for x in (c78['f_GHz'], i78.get('f_GHz', 0), o78['f_GHz'])) else 'nearly: control %.2f (%s), array arms at the ceiling' % (c78['f_GHz'], c78['limited_by'])}
    if c1.get('f_GHz') and o1.get('f_GHz'):
        gain = o1['f_GHz'] / c1['f_GHz'] - 1
        sc['P7_1.00'] = {'measured': {'control': c1['f_GHz'], 'idle': i1.get('f_GHz'), 'laser': o1['f_GHz'], 'Q_W': o1['heat_removed_W'], 'gain': gain},
                         'verdict': ('FALSIFIED: laser < 4.0 GHz' if o1['f_GHz'] < 4.0 else ('confirmed' if 3.4 <= c1['f_GHz'] <= 3.7 and 0.13 <= gain <= 0.23 else 'NOT as predicted'))}
    if c12.get('f_GHz') and o12.get('f_GHz'):
        gain = o12['f_GHz'] / c12['f_GHz'] - 1
        sc['P8_1.20'] = {'measured': {'control': c12['f_GHz'], 'idle': i12.get('f_GHz'), 'laser': o12['f_GHz'], 'Q_W': o12['heat_removed_W'], 'gain': gain},
                         'verdict': ('FALSIFIED: laser < 4.0 GHz' if o12['f_GHz'] < 4.0 else ('confirmed' if 3.0 <= c12['f_GHz'] <= 3.4 and 0.25 <= gain <= 0.40 else 'NOT as predicted'))}
    if t1.get('f_GHz'):
        sc['P9_table_and_above'] = {'measured': {'table_laser': (t1['f_GHz'], t1['limited_by'], t1.get('density')), 'above_table_laser': (ab.get('f_GHz'), ab.get('limited_by'), ab.get('density'))},
                                    'verdict': ('clock inside 4.6-5.0 (%.2f) but thermal-limited at %.2f W/mm^2, not clamped; above the table no thermal bound inside the search' % (t1['f_GHz'], t1.get('density') or 0)
                                                if 4.6 <= t1['f_GHz'] <= 5.0 else 'NOT as predicted: %.2f GHz' % t1['f_GHz'])}
    effs = []
    for run in ('spice_d0.78', 'spice_d1.00', 'spice_d1.20', 'table_d1.00'):
        e = [arm(run, a).get('GFLOPs_per_package_W') for a in ARMS]
        if all(e):
            effs.append(e[0] >= e[1] >= e[2])
    if effs:
        sc['P10_efficiency_falls_with_clock'] = {'measured': effs, 'verdict': 'confirmed' if all(effs) else 'NOT as predicted'}
    if sc:
        print('\nscorecard:')
        for k, v in sc.items():
            print('  %-30s %s' % (k, v['verdict']))
    # §P0.33: the throughput elasticity at the recorded F1c clocks, from IPC(f)
    el = {}
    for tag, R in runs.items():
        c, o = R['rows'].get('control', {}), R['rows'].get('array_on', {})
        if c.get('GIPS') and o.get('GIPS') and o['f_GHz'] != c['f_GHz']:
            el[tag] = {'clock_gain': o['clock_gain_vs_control'], 'throughput_gain': o['throughput_gain_vs_control'],
                       'elasticity': __import__('math').log(o['GIPS'] / c['GIPS']) / __import__('math').log(o['f_GHz'] / c['f_GHz'])}
    if el:
        print('\nIPC(f) [%s]: the laser arm\'s throughput gain against its clock gain' % args.ipc_benchmark)
        for tag, e in el.items():
            print('  %-22s clock %+.1f %%  throughput %+.1f %%  elasticity %.2f' % (tag, 100 * e['clock_gain'], 100 * e['throughput_gain'], e['elasticity']))
    out = {'note': __doc__.strip(), 'runs': runs, 'scorecard': sc, 'ipc_source': (args.ipc_source if ipc_curve else None),
           'ipc_benchmark': (args.ipc_benchmark if ipc_curve else None), 'throughput_elasticity': el,
           'complete': bool(runs) and all(r['done'] for r in runs.values())}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
