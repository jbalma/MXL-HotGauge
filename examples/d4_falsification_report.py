#!/usr/bin/env python
"""D4 (§P0.22.1): the 70-core die as a falsification test -- do the ratios travel, and do the
absolute ceilings move the way the package says?

    python examples/d4_falsification_report.py

Reads the three ladders (34-core at 50 um recorded, 34-core at 100 um grid control, 70-core at
100 um), finds each arm's cliff, scores §P0.22.1's P1-P6, and writes
``docs/evidence/d4_falsification_70core.json``. Refuses to call a cliff on an arm that has not
failed inside its ladder (reports it as open).
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')

DIE_MM2 = {'34core': 101.097, '70core': 196.0}


def ladder(base):
    rows = []
    for f in sorted(glob.glob(os.path.join(base, '*', 'd*', 'probe.json'))):
        rows.extend(json.load(open(f))['rows'])
    rows.sort(key=lambda r: (r['arm'], r['density']))
    return rows


def cliff(rows, arm):
    held = sorted(r['density'] for r in rows if r['arm'] == arm and not r['diverged']
                  and not r.get('unconverged'))
    # `[!]` An UNCONVERGED row is neither a hold nor a failure (register §4): verification failed
    # across damping levels, which is what happens on the rung adjacent to a cliff. It is listed,
    # never counted on either side.
    failed = sorted(r['density'] for r in rows if r['arm'] == arm and r['diverged']
                    and not r.get('unconverged'))
    unconv = sorted(r['density'] for r in rows if r['arm'] == arm and r.get('unconverged'))
    hot = {}
    for r in rows:
        if r['arm'] == arm and r['diverged'] and r.get('hottest_block'):
            hot[r['hottest_block'].rsplit('_', 1)[0]] = hot.get(r['hottest_block'].rsplit('_', 1)[0], 0) + 1
    return {'highest_holding': held[-1] if held else None,
            'lowest_failing': failed[0] if failed else None,
            'n_held': len(held), 'n_failed': len(failed), 'unconverged': unconv,
            'runaway_blocks': hot,
            # A cliff is CALLED only when the highest hold and the lowest failure are ADJACENT
            # rungs (0.05 apart): with points still running in between, "holds 0.65, fails 0.95"
            # is not a ceiling and must not be scored as one.
            'bracketed': bool(held and failed and held[-1] < failed[0]
                              and failed[0] - held[-1] <= 0.05 + 1e-9),
            # One undecidable rung between the last hold and the first failure: the cliff is
            # known to within that rung and is scored under BOTH resolutions.
            'bracketed_to_one_unconverged_rung': bool(
                held and failed and held[-1] < failed[0] and failed[0] - held[-1] <= 0.10 + 1e-9
                and any(held[-1] < u < failed[0] for u in unconv)),
            'rows': [{'density': r['density'], 'peak_C': r['peak_C'], 'diverged': r['diverged'],
                      'hottest_block': r.get('hottest_block')}
                     for r in rows if r['arm'] == arm]}


def mid(c):
    if c['highest_holding'] is None or c['lowest_failing'] is None:
        return None
    return 0.5 * (c['highest_holding'] + c['lowest_failing'])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ref50', default=os.path.join(_REPO, 'results', 'uniform_density_armD'))
    ap.add_argument('--ref100', default=os.path.join(_REPO, 'results',
                                                     'uniform_density_34core_c100_armD'))
    ap.add_argument('--die70', default=os.path.join(_REPO, 'results', 'uniform_density_70core_armD'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'd4_falsification_70core.json'))
    args = ap.parse_args()

    L = {'34core_50um': ladder(args.ref50), '34core_100um': ladder(args.ref100),
         '70core_100um': ladder(args.die70)}
    C = {k: {a: cliff(v, a) for a in ('uniform', 'shaped')} for k, v in L.items()}
    for k in C:
        print(k)
        for a in ('uniform', 'shaped'):
            c = C[k][a]
            print('  %-8s holds %s  fails %s  (%d held, %d failed%s)  runaway %s' % (
                a, c['highest_holding'], c['lowest_failing'], c['n_held'], c['n_failed'],
                '' if not c['unconverged'] else ', unconverged at %s' % c['unconverged'],
                c['runaway_blocks']))
            for r in c['rows']:
                print('      %.2f  %s  %s' % (r['density'], 'DIV' if r['diverged'] else
                                              '%.1f C' % r['peak_C'], r['hottest_block'] or ''))

    sc = {}
    r50, r100, d70 = C['34core_50um'], C['34core_100um'], C['70core_100um']
    # P1 -- the grid control
    def rungs_moved(a, b):
        ma, mb = mid(a), mid(b)
        return None if (ma is None or mb is None) else round((mb - ma) / 0.05, 1)
    if r100['uniform']['bracketed'] and r100['shaped']['bracketed']:
        du, ds = rungs_moved(r50['uniform'], r100['uniform']), rungs_moved(r50['shaped'], r100['shaped'])
        sc['P1_grid_control'] = {
            'predicted': 'uniform unchanged; shaped up by 0-1 rung; falsifier: either >= 2 rungs',
            'measured': {'uniform_rungs_moved': du, 'shaped_rungs_moved': ds},
            'verdict': ('confirmed' if abs(du) < 1.5 and -0.5 <= ds < 1.5 else
                        'FALSIFIED: the 100 um ladders cannot be read against the 50 um ones')}
    else:
        sc['P1_grid_control'] = {'verdict': 'open: the 100 um 34-core ladder is not bracketed yet'}
    # P2/P3 -- the 70-core ceilings
    for arm, key, lo, hi, failby in (('uniform', 'P2_flat_ceiling', 0.65, 0.75, 0.80),
                                     ('shaped', 'P3_shaped_ceiling', 0.45, 0.55, 0.60)):
        c = d70[arm]
        if not c['bracketed'] and c['bracketed_to_one_unconverged_rung']:
            u = c['unconverged'][0]
            sc[key] = {'predicted': 'holds %.2f-%.2f, fails by %.2f' % (lo, hi, failby),
                       'measured': {'highest_holding': c['highest_holding'], 'lowest_failing': c['lowest_failing'],
                                    'undecidable_rung': u},
                       'verdict': ('holds %.2f, fails %.2f; the %.2f rung is UNCONVERGED (verification fails '
                                   'across damping levels next to the cliff) -- %s' % (
                                       c['highest_holding'], c['lowest_failing'], u,
                                       'inside the band if it holds, one rung below it if it fails; not falsified'
                                       if lo - 1e-9 <= u <= hi + 1e-9 else 'outside the band either way'))}
            continue
        if c['bracketed']:
            h = c['highest_holding']
            sc[key] = {'predicted': 'holds %.2f-%.2f, fails by %.2f' % (lo, hi, failby),
                       'measured': {'highest_holding': h, 'lowest_failing': c['lowest_failing']},
                       'verdict': ('confirmed' if lo - 1e-9 <= h <= hi + 1e-9 and
                                   c['lowest_failing'] <= failby + 1e-9 else
                                   ('NOT as predicted: %s' % ('above the band' if h > hi else 'below the band')))}
        else:
            sc[key] = {'verdict': 'open: not bracketed yet',
                       'measured': {'highest_holding': c['highest_holding'],
                                    'lowest_failing': c['lowest_failing']}}
    # P4 -- the ratio travels
    if d70['uniform']['bracketed'] and d70['shaped']['bracketed_to_one_unconverged_rung'] \
            and not d70['shaped']['bracketed']:
        c = d70['shaped']; u = c['unconverged'][0]
        r_lo = mid(d70['uniform']) / (0.5 * (c['highest_holding'] + u))     # 0.45 fails
        r_hi = mid(d70['uniform']) / (0.5 * (u + c['lowest_failing']))      # 0.45 holds
        ok = all(1.2 <= r <= 1.7 for r in (r_lo, r_hi))
        sc['P4_ratio_travels'] = {'predicted': '1.2-1.7',
                                  'measured': {'ratio_if_undecidable_rung_fails': r_lo,
                                               'ratio_if_undecidable_rung_holds': r_hi},
                                  'verdict': ('confirmed under either resolution of the unconverged rung'
                                              if ok else 'depends on the unconverged rung')}
    elif d70['uniform']['bracketed'] and d70['shaped']['bracketed']:
        ratio = mid(d70['uniform']) / mid(d70['shaped'])
        ref_ratio = (mid(r100['uniform']) / mid(r100['shaped'])
                     if r100['uniform']['bracketed'] and r100['shaped']['bracketed'] else
                     mid(r50['uniform']) / mid(r50['shaped']))
        sc['P4_ratio_travels'] = {'predicted': '1.2-1.7', 'measured': {'ratio_70core': ratio,
                                                                       'ratio_34core': ref_ratio},
                                  'verdict': 'confirmed' if 1.2 <= ratio <= 1.7 else 'FALSIFIED'}
    else:
        sc['P4_ratio_travels'] = {'verdict': 'open'}
    # P5 -- the hot block
    blocks = d70['shaped']['runaway_blocks']
    if blocks:
        top = max(blocks, key=blocks.get)
        sc['P5_hot_block'] = {'predicted': 'cALU', 'measured': blocks,
                              'verdict': 'confirmed' if top == 'cALU' else 'NOT as predicted: %s' % top}
    # P6 -- the absolute watts rise
    if d70['uniform']['bracketed']:
        w70 = d70['uniform']['highest_holding'] * DIE_MM2['70core']
        w34 = (r100['uniform']['highest_holding'] if r100['uniform']['highest_holding'] else 0.85) * DIE_MM2['34core']
        sc['P6_absolute_watts_rise'] = {'predicted': '130-150 W on the 70-core against 86 W',
                                        'measured': {'W_70core': w70, 'W_34core': w34},
                                        'verdict': ('confirmed' if 130 <= w70 <= 150 and w70 > w34 else
                                                    ('rises, outside the band' if w70 > w34 else 'FALSIFIED'))}
    print('\nscorecard:')
    for k, v in sc.items():
        print('  %-26s %s' % (k, v['verdict']))
    out = {'note': __doc__.strip(), 'cliffs': C, 'scorecard': sc, 'die_mm2': DIE_MM2,
           'boundary_K_per_W': {'34core': 0.3247, '70core': 0.2343},
           'complete': all(C['70core_100um'][a]['bracketed'] or C['70core_100um'][a]['bracketed_to_one_unconverged_rung']
                           for a in ('uniform', 'shaped'))
           and all(C['34core_100um'][a]['bracketed'] for a in ('uniform', 'shaped'))}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s%s' % (os.path.relpath(args.json_out, _REPO),
                               '' if out['complete'] else '   [INCOMPLETE -- ladders still running]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
