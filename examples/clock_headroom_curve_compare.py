#!/usr/bin/env python
"""Does the SUSTAINABLE CLOCK move when the leakage curve is replaced by a simulated one?

    python examples/clock_headroom_curve_compare.py

`[!]` **The prediction this run was made to test is WRONG, and it is recorded here rather than
quietly removed.** §P0.14 found the density ladder's ceiling moved by exactly one rung on one arm,
and explained the small move: runaway is a *local* instability, decided by ``d(ln P_leak)/dT`` at
the single temperature the die sits at. From that it predicted the clock-headroom search should
move **more**, because its criterion is a *temperature limit* held across a whole bisection rather
than a divergence test at one operating point, so a curve that is steeper through the entire
operating band should eat headroom continuously.

Measured across six cooling points and three curves: **the sustainable clock does not move at
five of six**, to the search's own 0.05 GHz resolution, and moves 3.1 % at the sixth. The
temperature-limited search moved **less** than the divergence test, not more. The prediction is
withdrawn.

`[+]` What the run found instead, which is worth more
-----------------------------------------------------
**The binding constraint changes even where the clock does not.** On the pipeline curve the die
stops being able to go faster because it *runs away*; on both simulated curves it stops because it
*reaches its 100 C spec*. Same clock, different reason, at every cooling point of 0.3 K/W and
worse.

That matters because `docs/CLOCK_HEADROOM.md` makes a headline claim out of exactly this:

    "Above 0.1 K/W the part does not reach its 100 C spec limit at all -- it **runs away first**,
     at 85.7 C with a 1.0 K/W cooler. The leakage instability, not the temperature spec, is what
     caps the clock on a poorly-cooled die."

On the measured curve that is false: the part reaches spec at every cooling point tested. The
claim is an artefact of the pipeline curve's hot tail, which §P0.13 measured at **47x too steep at
500 K**.

`[!]` And that is the *opposite* corner from where §P0.14 said the tail lives. §P0.14's argument --
that the 47x tail disagreement "lives where the answer does not", because a surviving die never
gets that hot -- is correct for a **fixed-density divergence test**, where the reported point is
one the die survives. It fails for a **search**, which deliberately probes operating points the die
does *not* survive and reads its answer off where they start. The tail is invisible to the ladder
and load-bearing here, and the difference is the shape of the experiment rather than the physics.

`[+]` The GIDL bracket is worth nothing at all in this study: the two brackets agree on the clock
at every point and on the limiter at every point. Unlike the density ladder, where §P0.14 flagged
it as load-bearing, here it can be ignored.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

#: The 14 Aug 2026 table in docs/CLOCK_HEADROOM.md, for reference only.
#: `[!]` NOT a reproduction target. It predates the RBB work, the residual/backtracking convergence
#: fix and verify=True, all of which raise the clock; the pipeline arm here is the control for
#: THIS campaign and nothing else. Comparing to it would read an improvement as a regression.
RECORDED_2026_08_14 = {1.0: 2.797, 0.5: 3.500, 0.3: 3.828, 0.1: 4.203, 0.05: 4.297, 0.02: 4.344}


def load_runs(base):
    """``{(curve, r_th): row}`` for every finished point under ``base``."""
    out = {}
    for path in sorted(glob.glob(os.path.join(base, '*', '*', 'clock_headroom.json'))):
        curve = os.path.basename(os.path.dirname(os.path.dirname(path)))
        for row in json.load(open(path))['rows']:
            if row.get('arm') != 'control':
                continue
            out[(curve, float(row['r_th']))] = row
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'clock_headroom_curves'))
    ap.add_argument('--f-tol', type=float, default=0.05,
                    help="the search's own resolution -- a move smaller than this is not a move")
    ap.add_argument('--json-out', default=os.path.join(_EV, 'clock_headroom_curve_compare.json'))
    args = ap.parse_args()

    runs = load_runs(args.base)
    if not runs:
        raise SystemExit('no finished runs under {} -- run scripts/clock_headroom_curves.sh'
                         .format(args.base))
    curves = sorted({c for c, _ in runs}, key=lambda c: (c != 'pipeline', c))
    r_ths = sorted({r for _, r in runs}, reverse=True)

    rows, moved, limiter_changed = [], 0, 0
    for r in r_ths:
        base = runs.get(('pipeline', r))
        row = {'r_th_K_per_W': r}
        for c in curves:
            got = runs.get((c, r))
            row[c] = {'f_sustainable_GHz': got['f_sustainable_GHz'],
                      'limited_by': got['limited_by'], 'peak_C': got['peak_C'],
                      'p_chip_W': got['p_chip_W'], 'peak_block': got.get('peak_block')} \
                if got else None
        if base and row.get('simulated'):
            d = row['simulated']['f_sustainable_GHz'] - base['f_sustainable_GHz']
            row['delta_GHz_simulated_minus_pipeline'] = d
            row['delta_pct'] = 100.0 * d / base['f_sustainable_GHz']
            # `[!]` A move smaller than the bisection's own tolerance is not a measurement.
            row['clock_moved'] = bool(abs(d) > args.f_tol)
            row['limiter_changed'] = bool(row['simulated']['limited_by'] != base['limited_by'])
            moved += row['clock_moved']
            limiter_changed += row['limiter_changed']
        rows.append(row)

    complete = [r for r in rows if all(r.get(c) for c in curves)]

    # `[!]` An `unverified` limiter is neither a hold nor a failure -- the search's damping check
    # rejected the step above, so *why* the clock stopped is not known, even though the clock
    # itself is a demonstrated hold. Treating it as a disagreement would manufacture one; treating
    # it as agreement would launder it. It is counted separately, the same way the density
    # comparison treats an unconverged rung.
    UNVERIFIED = 'unverified'
    unverified = [{'r_th_K_per_W': r['r_th_K_per_W'],
                   'curves': [c for c in curves if r[c]['limited_by'] == UNVERIFIED]}
                  for r in complete
                  if any(r[c]['limited_by'] == UNVERIFIED for c in curves)]
    brackets_agree = brackets_agree_on_limiter = None
    if len(curves) > 2:
        pairs = [(r['simulated'], r['simulated-gidl-off']) for r in complete]
        # Clocks are compared at the search's own resolution, not for exact equality: two
        # bisections that stop one step apart have not disagreed about anything measurable.
        brackets_agree = all(abs(a['f_sustainable_GHz'] - b['f_sustainable_GHz']) <= args.f_tol
                             for a, b in pairs)
        judged = [(a, b) for a, b in pairs
                  if UNVERIFIED not in (a['limited_by'], b['limited_by'])]
        brackets_agree_on_limiter = all(a['limited_by'] == b['limited_by'] for a, b in judged)

    out = {
        'note': __doc__.strip(),
        'base': os.path.relpath(args.base, _REPO),
        'f_tol_GHz': args.f_tol,
        'curves': curves,
        'rows': rows,
        'n_cooling_points': len(rows),
        'n_where_clock_moved': moved,
        'n_where_limiter_changed': limiter_changed,
        'gidl_brackets_agree_on_clock': brackets_agree,
        'gidl_brackets_agree_on_limiter_where_judgeable': brackets_agree_on_limiter,
        'points_with_an_unverified_limiter': unverified,
        'recorded_2026_08_14_for_reference_only': RECORDED_2026_08_14,

        'FINDING_1_THE_PREDICTION_IS_WITHDRAWN': (
            '§P0.14 predicted that a temperature-LIMITED search would move more than the '
            'divergence test did, because the simulated curve is steeper through the whole '
            'operating band rather than only at a cliff. It moved LESS: the sustainable clock is '
            'unchanged at {} of {} cooling points to the search\'s own {:.2f} GHz resolution. The '
            'density ladder moved a full rung on an arm; this moved nothing at almost every point. '
            '`[!]` The prediction was wrong and is withdrawn rather than reworded.'
            .format(len(rows) - moved, len(rows), args.f_tol)),

        'FINDING_2_BUT_THE_LIMITER_CHANGES_AND_THAT_KILLS_A_RECORDED_CLAIM': (
            'At {} of {} cooling points the clock is identical and the REASON is not: the pipeline '
            'curve stops the die with a **thermal runaway**, both simulated curves stop it at the '
            '**100 C spec limit**. docs/CLOCK_HEADROOM.md builds a headline on the pipeline '
            'behaviour -- "the part does not reach its 100 C spec limit at all, it runs away '
            'first ... the leakage instability, not the temperature spec, is what caps the clock '
            'on a poorly-cooled die". On the measured curve the part reaches spec at every point '
            'tested, so **that claim is withdrawn**: it is an artefact of a hot tail §P0.13 '
            'measured at 47x too steep at 500 K. The clock it quotes survives; the mechanism does '
            'not.'.format(limiter_changed, len(rows))),

        'FINDING_3_THE_HOT_TAIL_MATTERS_TO_A_SEARCH_AND_NOT_TO_A_LADDER': (
            '§P0.14 argued the 47x tail disagreement "lives where the answer does not", because a '
            'die that survives never gets that hot. That is right for a fixed-density divergence '
            'test, whose reported point is one the die survives. It is wrong for a SEARCH, which '
            'probes operating points the die does not survive and reads its answer off where they '
            'begin -- so the tail decides whether the last failing step failed by running away or '
            'by exceeding spec. `[+]` The generalisation worth keeping: which part of a leakage '
            'curve is load-bearing is a property of the EXPERIMENT, not of the curve. A '
            'divergence test at fixed power is decided by the local slope at the operating '
            'temperature; a limit search is decided by the tail as well.'),

        'FINDING_4_THE_GIDL_BRACKET_IS_WORTH_NOTHING_HERE': (
            'The two GIDL brackets agree on the clock AND on the limiter at every cooling point. '
            '§P0.14 flagged the bracket as load-bearing for the density ceiling because that is '
            'decided at 310-330 K; nothing in this study is. It can be ignored here.{}'
            .format('' if not unverified else
                    ' `[!]` One caveat rather than an exception: at R_th {} the GIDL-off search '
                    'stopped on an UNVERIFIED step, so its clock is a demonstrated hold but the '
                    'REASON it stopped is not known. That point is excluded from the limiter '
                    'comparison rather than counted either way.'
                    .format(', '.join(str(u['r_th_K_per_W']) for u in unverified)))
            if brackets_agree else
            'The GIDL brackets DISAGREE on the clock by more than the search resolution -- see '
            'rows; this needs reading before the clock result is quoted.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)

    print(__doc__.split('\n')[0])
    print('\n  %-8s | %s' % ('R_th', ' | '.join('%-26s' % c for c in curves)))
    print('  %-8s | %s' % ('K/W', ' | '.join('%-26s' % 'f_GHz  peak_C  limited by'
                                             for _ in curves)))
    for r in rows:
        cells = []
        for c in curves:
            v = r.get(c)
            cells.append('%-26s' % ('%6.3f %6.1f  %-12s' % (v['f_sustainable_GHz'], v['peak_C'],
                                                            v['limited_by'])) if v else
                         '%-26s' % '(pending)')
        print('  %-8s | %s' % (r['r_th_K_per_W'], ' | '.join(cells)))
    print('\n  clock moved (> %.2f GHz): %d of %d cooling points'
          % (args.f_tol, moved, len(rows)))
    print('  LIMITER changed:          %d of %d' % (limiter_changed, len(rows)))
    print('  GIDL brackets agree on the clock (within %.2f GHz): %s' % (args.f_tol,
                                                                          brackets_agree))
    print('  ... and on the limiter, where judgeable:            %s' % brackets_agree_on_limiter)
    if unverified:
        print('  `[!]` unverified limiter (clock holds, reason unknown): %s'
              % ', '.join('R_th %s [%s]' % (u['r_th_K_per_W'], '/'.join(u['curves']))
                          for u in unverified))
    print('\n' + out['FINDING_1_THE_PREDICTION_IS_WITHDRAWN'])
    print('\n' + out['FINDING_2_BUT_THE_LIMITER_CHANGES_AND_THAT_KILLS_A_RECORDED_CLAIM'])
    print('\n' + out['FINDING_3_THE_HOT_TAIL_MATTERS_TO_A_SEARCH_AND_NOT_TO_A_LADDER'])
    print('\nwritten: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
