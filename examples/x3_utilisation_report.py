#!/usr/bin/env python
"""X3 (§P0.27.3): the dense cluster at the book's utilisation and halos, at MATCHED DIE WATTS.

    python examples/x3_utilisation_report.py

Reads ``results/x3_u70/<member>/control/W*/probe.json`` (shaped control) and
``results/x3_u70/<member>/array/W*/mr_comparison.json`` for the three members on ONE grid
(100 um): ``ref`` (the recorded reference re-run at 100 um), ``d1_exec1_u70`` (utilisation alone),
``d1_exec0.5_u70`` (utilisation + the x0.5 cluster). Scores P9-P13 and writes
``docs/evidence/x3_utilisation.json``. Rungs still running are listed as open; an UNCONVERGED row
is neither a hold nor a failure.
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
REF_MM2 = 101.09708
DT_DQ = 0.3247          # K/W, the package at 88 CFM on the 34-core die (register §4)
MEMBERS = ('ref', 'd1_exec1_u70', 'd1_exec0.5_u70')


def watts_of(path):
    m = re.search(r'W([0-9.]+)', os.path.basename(path))
    return float(m.group(1)) if m else None


def member_rows(member):
    base = os.path.join(_REPO, 'results', 'x3_u70', member)
    ctrl = []
    for f in sorted(glob.glob(os.path.join(base, 'control', 'W*', 'probe.json'))):
        for r in json.load(open(f))['rows']:
            ctrl.append({'W': watts_of(os.path.dirname(f)), 'density': r['density'], 'diverged': r['diverged'],
                         'peak_C': r['peak_C'], 'hottest_block': r.get('hottest_block'), 'unconverged': r.get('unconverged')})
    arr = {}
    for f in sorted(glob.glob(os.path.join(base, 'array', 'W*', 'mr_comparison.json'))):
        arr[round(watts_of(os.path.dirname(f)), 1)] = {r['arm']: r for r in json.load(open(f))['rows']}
    queued = sorted({round(watts_of(d), 1) for d in glob.glob(os.path.join(base, 'array', 'W*')) if os.path.isdir(d)})
    return ctrl, arr, queued


def cliff_W(rows):
    held = sorted(r['W'] for r in rows if not r['diverged'] and not r.get('unconverged'))
    failed = sorted(r['W'] for r in rows if r['diverged'] and not r.get('unconverged'))
    unconv = sorted(r['W'] for r in rows if r.get('unconverged'))
    adjacent = bool(held and failed and held[-1] < failed[0] and failed[0] - held[-1] <= 10.3)
    return {'highest_holding_W': held[-1] if held else None, 'lowest_failing_W': failed[0] if failed else None,
            'bracketed': adjacent, 'unconverged_W': unconv}


def normalised_Q(row):
    if not row or row.get('diverged') or row.get('heat_removed_W') is None:
        return None
    return row['heat_removed_W'] + (row['peak_C'] - 92.0) / DT_DQ


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'x3_utilisation.json'))
    args = ap.parse_args()
    fam = json.load(open(os.path.join(_EV, 'd1_exec_density_family_u70.json')))
    mm2 = {'ref': REF_MM2}
    for m in fam['members']:
        mm2['d1_exec{:g}_u70'.format(m['factor'])] = m['die_mm2']
    data = {}
    for M in MEMBERS:
        ctrl, arr, queued = member_rows(M)
        c = cliff_W(ctrl)
        rungs = []
        for W in sorted(arr):
            on, idle = arr[W].get('array_on'), arr[W].get('array_idle')
            # A rung the UNPOWERED array already holds under the target (plan 0 W, peak <= 92 C) is
            # held trivially -- the planner reports no plan rather than a holding one.
            holds = bool(on and not on.get('diverged') and not on.get('unconverged') and
                         (on.get('mr_plan_holds_target') or
                          (on.get('mr_reason') or '').startswith('descent converged on the target; this plan holds') or
                          ((on.get('heat_removed_W') or 0.0) <= 1e-6 and (on.get('peak_C') or 999) <= 92.0)))
            rungs.append({'W': W, 'holds_target': holds, 'diverged': bool(on and on.get('diverged')),
                          'unconverged': bool(on and on.get('unconverged')), 'peak_C': on.get('peak_C') if on else None,
                          'Q_W': on.get('heat_removed_W') if on else None, 'Q_norm_W': normalised_Q(on),
                          'peak_block': on.get('peak_block') if on else None,
                          'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped') if on else None,
                          'idle_diverged': bool(idle and idle.get('diverged')), 'idle_peak_C': idle.get('peak_C') if idle else None,
                          'reason': (on.get('mr_reason') or '')[:80] if on else None})
        data[M] = {'die_mm2': mm2.get(M), 'control': sorted(ctrl, key=lambda r: r['W']), 'control_cliff_W': c,
                   'array': rungs, 'array_open_W': [w for w in queued if w not in arr]}
        print('\n%s  (%.2f mm^2, %.3fx)' % (M, mm2.get(M, 0), mm2.get(M, 0) / REF_MM2))
        print('  control (shaped, 100 um): ' + ', '.join('%.1f W %s' % (r['W'], 'DIV' if r['diverged'] else ('UNCONV' if r.get('unconverged') else '%.1f C' % r['peak_C'])) for r in sorted(ctrl, key=lambda r: r['W'])))
        print('    cliff: holds %s, fails %s' % (c['highest_holding_W'], c['lowest_failing_W']))
        for r in rungs:
            print('  array %6.1f W: %s  Q %s  norm %s  %s  capped %s  idle %s' % (
                r['W'], 'DIV' if r['diverged'] else ('%.1f C%s' % (r['peak_C'] or 0, '' if r['holds_target'] else ' NOT HELD')),
                '--' if r['Q_W'] is None else '%.1f' % r['Q_W'], '--' if r['Q_norm_W'] is None else '%.1f' % r['Q_norm_W'],
                r['peak_block'], r['tiles_capped'], 'DIV' if r['idle_diverged'] else ('%.1f C' % r['idle_peak_C'] if r['idle_peak_C'] else '--')))
        if data[M]['array_open_W']:
            print('  open: %s' % data[M]['array_open_W'])

    # ratios at matched watts
    def qn(M, W):
        for r in data[M]['array']:
            if abs(r['W'] - W) < 0.2 and r['holds_target'] and r['Q_norm_W']:
                return r['Q_norm_W']
        return None
    Ws = (111.2, 121.3, 161.8, 202.2, 242.6)
    ratios = {'u70x0.5_over_ref': {}, 'u70x0.5_over_u70x1': {}, 'u70x1_over_ref': {}}
    for W in Ws:
        a, b, c = qn('d1_exec0.5_u70', W), qn('ref', W), qn('d1_exec1_u70', W)
        if a and b:
            ratios['u70x0.5_over_ref'][W] = a / b
        if a and c:
            ratios['u70x0.5_over_u70x1'][W] = a / c
        if c and b:
            ratios['u70x1_over_ref'][W] = c / b
    print('\nnormalised plan ratios at matched watts:', json.dumps(ratios))

    sc = {}
    areas = {M: data[M]['die_mm2'] / REF_MM2 for M in ('d1_exec1_u70', 'd1_exec0.5_u70') if data[M]['die_mm2']}
    sc['P9_die_grows'] = {'area_ratios': areas, 'cluster_density_vs_reference': 1.0 / (0.5 * 1.15 / 0.70),
                          'verdict': ('confirmed' if all(1.3 <= v <= 1.65 for v in areas.values()) else 'NOT as predicted: %s' % areas)}
    r05 = data['d1_exec0.5_u70']['array']
    held = [r['W'] for r in r05 if r['holds_target']]
    lost = [r['W'] for r in r05 if not r['holds_target'] and not r['unconverged']]
    unc = [r['W'] for r in r05 if r['unconverged']]
    capped = max((r['tiles_capped'] or 0) for r in r05) if r05 else None
    sc['P10_rescue_survives'] = {'held': held, 'lost': lost, 'unconverged': unc, 'open': data['d1_exec0.5_u70']['array_open_W'], 'max_tiles_capped': capped,
                                 'verdict': ('open' if data['d1_exec0.5_u70']['array_open_W'] else ('FALSIFIED: rung lost %s' % lost if lost else ('confirmed' if held and max(held) >= 242 and not capped else 'NOT as predicted')))}
    a, b = ratios['u70x0.5_over_ref'], ratios['u70x0.5_over_u70x1']
    hi = {W: v for W, v in a.items() if W >= 161}
    hi2 = {W: v for W, v in b.items() if W >= 161}
    sc['P11_premium_vs_control'] = {'vs_reference': a, 'vs_u70_control': b,
                                    'verdict': ('open' if not hi or not hi2 else
                                                ('FALSIFIED: > 1.0x vs the reference at >= 162 W' if any(v > 1.0 for v in hi.values()) else
                                                 ('FALSIFIED: > 1.5x vs the u70 control at >= 162 W' if any(v > 1.5 for v in hi2.values()) else
                                                  ('confirmed' if all(0.5 <= v <= 0.9 for v in hi.values()) and all(1.1 <= v <= 1.3 for v in hi2.values()) else 'NOT as predicted'))))}
    c1, c05 = data['d1_exec1_u70']['control_cliff_W'], data['d1_exec0.5_u70']['control_cliff_W']
    sc['P12_passive_ceiling_rises'] = {'u70x1': c1, 'u70x0.5': c05,
                                       'verdict': ('open' if c1['highest_holding_W'] is None or c05['highest_holding_W'] is None else
                                                   ('FALSIFIED: below the reference\'s 60.7 W rung' if min(c1['highest_holding_W'], c05['highest_holding_W']) < 60.0 else
                                                    ('confirmed' if 85 <= c1['highest_holding_W'] <= 100 and 75 <= c05['highest_holding_W'] <= 90 else 'NOT as predicted')))}
    blocks = set()
    for M in MEMBERS:
        blocks |= {r['peak_block'].rsplit('_', 1)[0] for r in data[M]['array'] if r.get('peak_block')}
        blocks |= {r['hottest_block'].rsplit('_', 1)[0] for r in data[M]['control'] if r.get('hottest_block')}
    sc['P13_peak_is_cALU'] = {'blocks': sorted(blocks), 'verdict': 'confirmed' if blocks and blocks <= {'cALU'} else ('open' if not blocks else 'NOT as predicted: %s' % sorted(blocks))}
    print('\nscorecard:')
    for k, v in sc.items():
        print('  %-26s %s' % (k, v['verdict']))
    complete = not any(data[M]['array_open_W'] for M in MEMBERS)
    out = {'note': __doc__.strip(), 'grid_um': 100, 'members': data, 'plan_ratios': ratios, 'scorecard': sc, 'complete': complete}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if complete else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
