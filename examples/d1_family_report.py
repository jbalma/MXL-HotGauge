#!/usr/bin/env python
"""D1 (§P0.22.3): the dense-execution-cluster family against the reference die at MATCHED WATTS.

    python examples/d1_family_report.py

Reads the members' control ladders (``results/d1_family/exec<f>/control/W*/probe.json``) and
array rungs (``results/d1_family_arr/exec<f>/array/W*/mr_comparison.json``, falling back to
``results/d1_family/...``), places each beside the reference rows at the same die watts
(``results/uniform_density_armD/shaped`` and ``results/array_coverage_armD/c1.00``), scores
§P0.22.3's P1-P4, and writes ``docs/evidence/d1_exec_density_family_result.json``. Rungs still
running are listed as open; a cliff is only called between ADJACENT rungs.
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


def watts_of(path):
    m = re.search(r'W([0-9.]+)', os.path.basename(path))
    return float(m.group(1)) if m else None


def reference():
    ctrl = []
    for f in sorted(glob.glob(os.path.join(_REPO, 'results', 'uniform_density_armD', 'shaped',
                                           'd*', 'probe.json'))):
        for r in json.load(open(f))['rows']:
            ctrl.append({'W': r['density'] * REF_MM2, 'density': r['density'],
                         'diverged': r['diverged'], 'peak_C': r['peak_C'],
                         'hottest_block': r.get('hottest_block')})
    arr = {}
    for f in sorted(glob.glob(os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00',
                                           'd*', 'mr_comparison.json'))):
        j = json.load(open(f))
        arr[round(j['density'] * REF_MM2, 1)] = {r['arm']: r for r in j['rows']}
    return ctrl, arr


def member_rows(factor):
    ctrl = []
    for f in sorted(glob.glob(os.path.join(_REPO, 'results', 'd1_family',
                                           'exec{:g}'.format(factor), 'control', 'W*',
                                           'probe.json'))):
        for r in json.load(open(f))['rows']:
            ctrl.append({'W': watts_of(os.path.dirname(f)), 'density': r['density'],
                         'diverged': r['diverged'], 'peak_C': r['peak_C'],
                         'hottest_block': r.get('hottest_block'),
                         'unconverged': r.get('unconverged')})
    arr = {}
    for base in ('d1_family_arr', 'd1_family'):
        for f in sorted(glob.glob(os.path.join(_REPO, 'results', base, 'exec{:g}'.format(factor),
                                               'array', 'W*', 'mr_comparison.json'))):
            W = round(watts_of(os.path.dirname(f)), 1)
            if W not in arr:
                arr[W] = {r['arm']: r for r in json.load(open(f))['rows']}
                arr[W]['_source'] = os.path.relpath(f, _REPO)
    return ctrl, arr


def cliff_W(rows):
    # An UNCONVERGED row is neither a hold nor a failure (register §4); it is listed, not counted.
    held = sorted(r['W'] for r in rows if not r['diverged'] and not r.get('unconverged'))
    failed = sorted(r['W'] for r in rows if r['diverged'] and not r.get('unconverged'))
    unconv = sorted(r['W'] for r in rows if r.get('unconverged'))
    ok = bool(held and failed and held[-1] < failed[0] and failed[0] - held[-1] <= 5.2)
    one = bool(held and failed and held[-1] < failed[0] and failed[0] - held[-1] <= 10.3
               and any(held[-1] < u < failed[0] for u in unconv))
    return {'highest_holding_W': held[-1] if held else None,
            'lowest_failing_W': failed[0] if failed else None, 'bracketed': ok,
            'bracketed_to_one_unconverged_rung': one, 'unconverged_W': unconv}


def normalised_Q(row):
    """Minimum-plan cost normalised to the 92 C target at the package resistance (register §4)."""
    if not row or row.get('diverged') or row.get('heat_removed_W') is None:
        return None
    return row['heat_removed_W'] + (row['peak_C'] - 92.0) / DT_DQ


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--factors', type=float, nargs='+', default=[0.5, 0.25])
    ap.add_argument('--json-out', default=os.path.join(_EV, 'd1_exec_density_family_result.json'))
    args = ap.parse_args()
    fam = json.load(open(os.path.join(_EV, 'd1_exec_density_family.json')))
    mm2 = {m['factor']: m['die_mm2'] for m in fam['members']}

    ref_ctrl, ref_arr = reference()
    ref_cliff = cliff_W(ref_ctrl)
    out = {'note': __doc__.strip(), 'reference': {'control_cliff_W': ref_cliff,
                                                  'die_mm2': REF_MM2}, 'members': {}}
    print('reference shaped control: holds %.1f W, fails %.1f W' % (
        ref_cliff['highest_holding_W'] or float('nan'), ref_cliff['lowest_failing_W'] or float('nan')))
    sc = {}
    for F in args.factors:
        ctrl, arr = member_rows(F)
        c = cliff_W(ctrl)
        print('\nmember x%g  (%.2f mm^2)' % (F, mm2[F]))
        print('  control (shaped):')
        for r in sorted(ctrl, key=lambda r: r['W']):
            print('    %6.1f W  %.3f W/mm^2  %s  %s' % (r['W'], r['density'],
                                                        'DIV' if r['diverged'] else '%.1f C' % r['peak_C'],
                                                        r['hottest_block'] or ''))
        print('    cliff: holds %s, fails %s%s' % (c['highest_holding_W'], c['lowest_failing_W'],
                                                     '' if c['bracketed'] else '  [not bracketed]'))
        print('  array rungs (matched watts against the reference c1.00 ladder):')
        rungs = []
        for W in sorted(arr):
            on, idle = arr[W].get('array_on'), arr[W].get('array_idle')
            ref = ref_arr.get(W, {}).get('array_on')
            q, qr = normalised_Q(on), normalised_Q(ref)
            # A rung is HELD only if the reported field is a steady state AT the target: the
            # planner can return a stable hot-branch or conservation-capped field far above 92 C
            # (the x0.5 member at 242.6 W: 114 C on 192.7 W delivered), which is not a rescue.
            holds = bool(on and not on.get('diverged') and on.get('mr_plan_holds_target'))
            rung = {'W': W, 'diverged': bool(on and on.get('diverged')), 'holds_target': holds,
                    'peak_C': on.get('peak_C') if on else None,
                    'Q_W': on.get('heat_removed_W') if on else None, 'Q_norm_W': q,
                    'ref_Q_W': ref.get('heat_removed_W') if ref else None, 'ref_Q_norm_W': qr,
                    'Q_ratio_vs_ref': (q / qr) if (q and qr) else None,
                    'peak_block': on.get('peak_block') if on else None,
                    'tiles_capped': (on.get('extractor') or {}).get('n_tiles_capped') if on else None,
                    'idle_diverged': bool(idle and idle.get('diverged')),
                    'reason': (on.get('mr_reason') or '')[:70] if on else None,
                    'unconverged': on.get('unconverged') if on else None}
            rungs.append(rung)
            print('    %6.1f W  %s  Q %s (ref %s)  norm ratio %s  block %s  capped %s  idle %s%s' % (
                W, 'DIV' if rung['diverged'] else ('%.1f C' % (rung['peak_C'] or 0)
                                                   + ('' if holds else ' NOT HELD')),
                '--' if rung['Q_W'] is None else '%.1f' % rung['Q_W'],
                '--' if rung['ref_Q_W'] is None else '%.1f' % rung['ref_Q_W'],
                '--' if rung['Q_ratio_vs_ref'] is None else '%.2f' % rung['Q_ratio_vs_ref'],
                rung['peak_block'], rung['tiles_capped'], 'DIV' if rung['idle_diverged'] else 'holds',
                '' if holds else '  [%s]' % (rung['reason'] or '')[:60]))
        out['members'][F] = {'die_mm2': mm2[F], 'control': sorted(ctrl, key=lambda r: r['W']),
                             'control_cliff_W': c, 'array': rungs}
        # score
        s = {}
        if (c['bracketed'] or c['bracketed_to_one_unconverged_rung']) and ref_cliff['bracketed']:
            note = ('' if c['bracketed'] else
                    '; the %.1f W rung is UNCONVERGED (neither a hold nor a failure)' % c['unconverged_W'][0])
            s['P1_control_watts_fall'] = {
                'predicted': 'holds <= 55 W (reference 60.7 W)',
                'measured': c,
                'verdict': (('confirmed: verified hold %.1f W, fails %.1f W, against the reference\'s 60.7 W hold'
                             % (c['highest_holding_W'], c['lowest_failing_W'])) + note
                            if c['lowest_failing_W'] <= ref_cliff['highest_holding_W'] + 1e-6
                            else 'FALSIFIED: fails above the reference\'s hold')}
        else:
            s['P1_control_watts_fall'] = {'verdict': 'open', 'measured': c}
        held = [r for r in rungs if r['holds_target'] and r['Q_ratio_vs_ref']]
        lost = [r for r in rungs if not r['holds_target'] and r['W'] <= 162.0]
        if rungs:
            worst = max((abs(r['Q_ratio_vs_ref'] - 1.0) for r in held), default=None)
            s['P2_array_holds_at_matched_watts'] = {
                'predicted': 'every reference rung holds, 0 tiles capped, plan within +-20 %',
                'measured': {'rungs_held': [r['W'] for r in held],
                             'rungs_lost': [r['W'] for r in rungs if not r['holds_target']],
                             'plan_ratios': {r['W']: r['Q_ratio_vs_ref'] for r in held},
                             'worst_plan_ratio': worst,
                             'max_tiles_capped': max((r['tiles_capped'] or 0) for r in rungs)},
                'verdict': ('FALSIFIED: a rung <= 162 W lost' if lost else
                            ('confirmed' if worst is not None and worst <= 0.20 and
                             max((r['tiles_capped'] or 0) for r in rungs) == 0 else
                             ('plan outside +-20 %%: worst ratio %.2f' % (1 + worst) if worst is not None
                              and worst > 0.20 else 'open')))}
            blocks = {r['peak_block'].rsplit('_', 1)[0] for r in rungs if r['peak_block']}
            blocks |= {r['hottest_block'].rsplit('_', 1)[0] for r in ctrl if r['hottest_block']}
            s['P3_peak_block_is_cALU'] = {'measured': sorted(blocks),
                                          'verdict': 'confirmed' if blocks and blocks <= {'cALU'} else
                                          ('NOT as predicted: %s' % sorted(blocks) if blocks else 'open')}
            s['P4_next_is_conservation'] = {
                'measured': {'max_tiles_capped': max((r['tiles_capped'] or 0) for r in rungs),
                             'reasons': [r['reason'] for r in rungs if r['W'] >= 240]},
                'verdict': 'open until the 243 W rung lands' if not any(r['W'] >= 240 for r in rungs)
                else ('confirmed' if max((r['tiles_capped'] or 0) for r in rungs) == 0 else 'NOT as predicted')}
        sc['x%g' % F] = s
    print('\nscorecard:')
    for m, s in sc.items():
        for k, v in s.items():
            print('  %-6s %-34s %s' % (m, k, v['verdict']))
    out['scorecard'] = sc
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s' % os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
