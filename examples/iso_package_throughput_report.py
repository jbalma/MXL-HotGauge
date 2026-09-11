#!/usr/bin/env python
"""F1 (§P0.23.1): iso-package compute scaling in THROUGHPUT terms -- the same air-cooled package,
how much compute, at what cost -- from the arm-D rescue ladder rows, and (when it lands) the
70-core die with the array.

    python examples/iso_package_throughput_report.py

Reads ``results/array_coverage_armD/c1.00/d*/mr_comparison.json`` (34-core) and
``results/iso_package_70core/d*/mr_comparison.json`` (70-core, 100 um cells). Per rung and arm:
converged die watts, GFLOP/s (thermal-only: the hottest block's clock derate, no IPC scaling),
GFLOP/s per PACKAGE watt (die + fan + net MR electrical), s = heat lifted / die power. Reports
the sustainable-watts multiplier per die and scores §P0.23.1. Writes
``docs/evidence/iso_package_throughput.json``.

`[!]` "Throughput" here is the pipeline's thermal-only GFLOP/s at 32 FLOP/cycle/core -- a
proxy that moves only with the sustainable clock and the core count, never with IPC. Quote the
WATTS multiplier and the per-package-watt SHAPE, not the absolute GFLOP/s.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
CTRL_CEIL = {'34core': (0.60, 0.65), '70core': (0.40, 0.50)}     # shaped control, register §1.3 / §P0.22.1
MM2 = {'34core': 101.097, '70core': 196.0}


def ladder(base):
    out = []
    for f in sorted(glob.glob(os.path.join(base, 'd*', 'mr_comparison.json')),
                    key=lambda p: float(os.path.basename(os.path.dirname(p))[1:])):
        j = json.load(open(f)); rows = {r['arm']: r for r in j['rows']}
        rec = {'density': float(j['density']), 'done': os.path.isfile(os.path.join(os.path.dirname(f), 'DONE'))}
        for arm, r in rows.items():
            held = (not r.get('diverged')) and (r.get('mr_plan_holds_target', True) is not False)
            rec[arm] = {'holds': held, 'peak_C': r.get('peak_C'), 'p_chip_W': r.get('p_chip_W'),
                        'p_total_W': r.get('p_total_W'), 'gflops': r.get('gflops'),
                        'gflops_per_total_W': r.get('gflops_per_total_W'),
                        'heat_removed_W': r.get('heat_removed_W'), 'p_mr_net_W': r.get('p_mr_net_W'),
                        'f_GHz': r.get('f_GHz'), 'peak_block': r.get('peak_block'),
                        'tiles_capped': (r.get('extractor') or {}).get('n_tiles_capped'),
                        's': ((r.get('heat_removed_W') or 0.0) / r['p_chip_W']) if r.get('p_chip_W') else None,
                        'unconverged': r.get('unconverged')}
        out.append(rec)
    return out


def summarise(rows, die):
    res = {'rows': rows}
    for arm in ('control', 'array_idle', 'array_on'):
        held = [r for r in rows if r.get(arm, {}).get('holds') and not r[arm].get('unconverged')]
        failed = [r for r in rows if arm in r and not r[arm]['holds']]
        res[arm + '_holds_to'] = max((r['density'] for r in held), default=None)
        res[arm + '_fails_at'] = min((r['density'] for r in failed), default=None)
    top = res['array_on_holds_to']
    if top:
        row = next(r for r in rows if r['density'] == top)
        res['sustainable_die_W_with_laser'] = row['array_on']['p_chip_W']
        lo, hi = CTRL_CEIL[die]
        res['watts_multiplier_vs_shaped_control'] = (top / hi, top / lo)
        res['top_rung_s'] = row['array_on']['s']
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'iso_package_throughput.json'))
    args = ap.parse_args()
    dies = {'34core': ladder(os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00')),
            '70core': ladder(os.path.join(_REPO, 'results', 'iso_package_70core'))}
    out = {'note': __doc__.strip(), 'dies': {}}
    for die, rows in dies.items():
        if not rows:
            continue
        S = summarise(rows, die); out['dies'][die] = S
        print('\n%s (%.0f mm^2)' % (die, MM2[die]))
        print('  %5s %-10s %6s %8s %8s %8s %9s %6s %6s' % ('dens', 'arm', 'holds', 'P_die', 'P_pkg', 'GFLOP/s', 'GF/pkgW', 's', 'f_GHz'))
        for r in rows:
            for arm in ('control', 'array_idle', 'array_on'):
                a = r.get(arm)
                if not a:
                    continue
                print('  %5.2f %-10s %6s %8s %8s %8s %9s %6s %6s%s' % (
                    r['density'], arm, 'yes' if a['holds'] else 'NO',
                    '--' if a['p_chip_W'] is None else '%.1f' % a['p_chip_W'],
                    '--' if a['p_total_W'] is None else '%.1f' % a['p_total_W'],
                    '--' if a['gflops'] is None else '%.0f' % a['gflops'],
                    '--' if a['gflops_per_total_W'] is None else '%.2f' % a['gflops_per_total_W'],
                    '--' if a['s'] is None else '%.2f' % a['s'],
                    '--' if a['f_GHz'] is None else '%.2f' % a['f_GHz'],
                    '' if r['done'] else '  [running]'))
        if S.get('sustainable_die_W_with_laser'):
            print('  laser holds to %.2f W/mm^2 = %.0f W on this package; %.1f-%.1fx the shaped control; s at the top %.2f' % (
                S['array_on_holds_to'], S['sustainable_die_W_with_laser'],
                S['watts_multiplier_vs_shaped_control'][0], S['watts_multiplier_vs_shaped_control'][1], S['top_rung_s'] or 0))
    # scorecard for the 70-core (§P0.23.1)
    sc = {}
    S = out['dies'].get('70core')
    if S:
        idle = S.get('array_idle_holds_to'); idle_f = S.get('array_idle_fails_at')
        if idle is not None and idle_f is not None:
            sc['P1_idle_cliff_scales'] = {'predicted': 'holds 0.70-0.80, fails by 0.90', 'measured': (idle, idle_f),
                                         'verdict': 'confirmed' if 0.70 <= idle <= 0.80 and idle_f <= 0.90 else 'NOT as predicted'}
        top = S.get('array_on_holds_to'); topf = S.get('array_on_fails_at')
        if top is not None and (topf is not None or top >= 2.4):
            W = S['sustainable_die_W_with_laser']
            sc['P2_laser_holds_390_470W'] = {'predicted': '2.0-2.4 W/mm^2, 390-470 W, 0 capped', 'measured': (top, W),
                                             'verdict': 'confirmed' if top >= 2.0 and 390 <= W <= 480 else ('FALSIFIED' if top <= 1.6 else 'NOT as predicted')}
        r2 = next((r for r in S['rows'] if r['density'] == 2.0), None)
        r2_34 = next((r for r in out['dies']['34core']['rows'] if r['density'] == 2.0), None)
        if r2 and r2_34 and r2.get('array_on', {}).get('s') is not None:
            s70, s34 = r2['array_on']['s'], r2_34['array_on']['s']
            sc['P3_cost_scales_with_watts'] = {'predicted': 's(2.00) within +-0.10 of 0.74', 'measured': {'s_70core': s70, 's_34core': s34},
                                              'verdict': 'confirmed' if abs(s70 - s34) <= 0.10 else 'NOT as predicted'}
        blocks = {r['array_on']['peak_block'].rsplit('_', 1)[0] for r in S['rows'] if r.get('array_on', {}).get('holds') and r['array_on'].get('peak_block')}
        if blocks:
            sc['P4_peak_block_cALU'] = {'measured': sorted(blocks), 'verdict': 'confirmed' if blocks <= {'cALU'} else 'NOT as predicted: %s' % sorted(blocks)}
    out['scorecard_70core'] = sc
    if sc:
        print('\nscorecard (70-core):')
        for k, v in sc.items():
            print('  %-28s %s' % (k, v['verdict']))
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s' % os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
