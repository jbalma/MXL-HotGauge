#!/usr/bin/env python
"""Does the flat-die ceiling move when the leakage curve is replaced by a simulated one?

    python examples/density_ceiling_curve_compare.py

**It does -- and it moves the wrong way.** §P0.12 predicted the opposite: the pipeline's Arrhenius
tail is ~6x too steep at 450 K, a gentler tail runs away later, therefore §P0.11's flat-die
ceiling of 1.0-1.2 W/mm^2 must be *conservative*. §P0.13 then measured the tail and made the gap
bigger -- 47x at 500 K -- which made the prediction look safe.

Measured, the uniform arm's ceiling moves **down** a rung. That claim is withdrawn.

Why -- and this is the useful part
----------------------------------
Thermal runaway is a **local instability**. Whether a steady state exists is decided by the
feedback gain ``d(ln P_leak)/dT`` *at the temperature the die is actually sitting at*, not by the
leakage at 500 K. By the time a block reaches 500 K it has already run away under either curve;
the 47x disagreement lives entirely in a region the answer does not depend on.

In the band the surviving points occupy -- roughly **317-347 K** -- the ordering is *reversed*:

* the pipeline curve is nearly **flat** there (slope 0.0013/K at 310 K, 0.0091/K at 330 K),
  because that is where CACTI's table is clamped or barely moving;
* the simulated curve has a real, roughly constant slope (~0.036/K, a 19 K doubling) throughout.

The two curves cross in gain at about **345 K**: below it the simulated curve carries more gain
(9.2x at 320 K, 4.1x at 330 K, and 28x at 310 K just outside the band), above it less. More gain
runs away earlier, and the surviving points sit below the crossover -- which is why the ceiling
moves down rather than up.

`[!]` What this relocates
--------------------------
The pipeline curve's most consequential error for the ceiling is **not** its hot tail. It is that
the curve is nearly flat at 310-330 K, understating feedback gain by roughly an order of magnitude
exactly where dies operate -- which makes every recorded ceiling **optimistic**. The same flatness
is what made the cold-zone prize look small in §P0.14. One clamp, two wrong answers, in opposite
directions.
"""
import os
import sys
import glob
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

import logging
logging.disable(logging.WARNING)   # the extrapolation warnings are expected and are not the point

from HotGauge.thermal.leakage_feedback import load_leakage_model, LEAKAGE_CURVES


def load_ladder(base, *extra):
    """``{(arm, density): row}`` from one or more campaign directories of ``probe.json`` files.

    `[!]` Extra directories are for **refining** a ladder, not for pooling different experiments.
    §P0.15 runs 0.05 W/mm^2 points around each curve's cliff into a separate `*_fine` tree so the
    coarse campaign stays exactly as it was recorded; merging them here is what lets the fine
    points participate in the cliff without rewriting the coarse results. A directory whose points
    were solved on a *different curve* must never be merged in -- that would silently pool two
    experiments into one ladder, and nothing downstream would notice.
    """
    rows = []
    for b in (base,) + tuple(extra):
        if not b:
            continue
        for f in sorted(glob.glob(os.path.join(b, '*', 'd*', 'probe.json'))):
            rows.extend(json.load(open(f))['rows'])
    return {(r['arm'], r['density']): r for r in rows}


def cliff(ladder, arm):
    """``(highest holding, lowest failing, [unconverged densities])`` for one arm.

    `[!]` **An ``unconverged`` row is neither.** ``run_leakage_feedback(verify=True)`` re-solves at
    half the damping and flags the row when the two disagree: the answer then depends on the
    damping, which is a property of the solver rather than of the die, and CLAUDE.md's rule is
    that such a row must not be quoted. ``uniform_density_report.cliff`` counts any non-diverged
    row as holding -- correct for the recorded P0.11 ladder, where nothing was flagged, but it
    would silently promote a damping artefact into a ceiling here. This one does not, and reports
    the flagged rungs separately so they are visible rather than dropped.
    """
    def rows(pred):
        return sorted(d for (a, d), r in ladder.items() if a == arm and pred(r))
    unconv = rows(lambda r: r.get('unconverged'))
    held = rows(lambda r: not r['diverged'] and not r.get('unconverged'))
    failed = rows(lambda r: r['diverged'] and not r.get('unconverged'))
    return (held[-1] if held else None), (failed[0] if failed else None), unconv


def log_slope(model, T, T_ref, h=1.0):
    """``d(ln scale)/dT`` -- the feedback gain, which is what decides stability."""
    return float((np.log(float(model.scale(T + h, T_ref)))
                  - np.log(float(model.scale(T - h, T_ref)))) / (2 * h))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pipeline-base', default=os.path.join(_REPO, 'results', 'uniform_density'))
    ap.add_argument('--simulated-base', default=os.path.join(_REPO, 'results',
                                                             'uniform_density_simulated'))
    ap.add_argument('--calibration', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'uniform_density_curve_compare.json'))
    # `[!]` WHICH curve the second ladder was solved on. It is not cosmetic: it selects the model
    # the gain table below is computed from, and it names the second ladder in the evidence file.
    # §P0.14 ran only `simulated`; §P0.15 runs `simulated-gidl-off`, and the two ladders must not
    # end up under the same key in two evidence files that then get compared to each other.
    # Default 'simulated' so the recorded evidence file's keys and contents are unchanged.
    ap.add_argument('--curve', default='simulated', choices=[c for c in LEAKAGE_CURVES
                                                             if c != 'pipeline'],
                    help='the curve --simulated-base was solved on; names it in the output')
    # Refinement runs live in their own tree so the recorded coarse campaign is never rewritten.
    # `[!]` Only ever pass a directory solved on the SAME curve as the base it extends.
    ap.add_argument('--pipeline-extra', nargs='*', default=[], metavar='DIR',
                    help='extra pipeline-curve ladders to merge in (e.g. the *_fine refinement)')
    ap.add_argument('--simulated-extra', nargs='*', default=[], metavar='DIR',
                    help='extra ladders on --curve to merge in (e.g. the *_fine refinement)')
    args = ap.parse_args()
    CURVE = args.curve

    pipe_l = load_ladder(args.pipeline_base, *args.pipeline_extra)
    sim_l = load_ladder(args.simulated_base, *args.simulated_extra)
    if not sim_l:
        raise SystemExit('no {} ladder under {} -- run the matching '
                         'scripts/uniform_density_ladder_*.sh first'
                         .format(CURVE, args.simulated_base))

    arms = ('shaped', 'uniform')
    cliffs = {a: {'pipeline': cliff(pipe_l, a), CURVE: cliff(sim_l, a)} for a in arms}
    # Two different claims, and conflating them overstates the result. The FAILING rung moving is
    # "the ceiling moved". The highest HOLDING rung moving can also mean a point merely stopped
    # being a demonstrable hold (flagged unconverged), which is weaker and must be said as such.
    fail_moved = {a: cliffs[a]['pipeline'][1] != cliffs[a][CURVE][1] for a in arms}
    hold_moved = {a: cliffs[a]['pipeline'][0] != cliffs[a][CURVE][0] for a in arms}
    moved = {a: fail_moved[a] or hold_moved[a] for a in arms}

    # Point-by-point, only where both ladders have a point -- an unmatched rung proves nothing.
    common = sorted(set(pipe_l) & set(sim_l))
    comparison, verdict_flips, peak_deltas = [], 0, []
    for k in common:
        p, s = pipe_l[k], sim_l[k]
        row = {'arm': k[0], 'density_W_per_mm2': k[1],
               'pipeline_diverged': bool(p['diverged']),
               CURVE + '_diverged': bool(s['diverged']),
               'pipeline_unconverged': bool(p.get('unconverged')),
               CURVE + '_unconverged': bool(s.get('unconverged')),
               'pipeline_peak_C': p['peak_C'], CURVE + '_peak_C': s['peak_C'],
               'verdict_agrees': bool(p['diverged'] == s['diverged']
                                      and bool(p.get('unconverged')) == bool(s.get('unconverged')))}
        if not row['verdict_agrees']:
            verdict_flips += 1
        if (p['peak_C'] is not None and s['peak_C'] is not None
                and not p.get('unconverged') and not s.get('unconverged')):
            row['delta_peak_K'] = s['peak_C'] - p['peak_C']
            peak_deltas.append(row['delta_peak_K'])
        comparison.append(row)

    # The mechanism: where does each curve actually have its feedback gain?
    pm, t_p = load_leakage_model('pipeline', calibration=args.calibration)
    sm, t_s = load_leakage_model(CURVE)
    gain = []
    for T in (310., 320., 330., 340., 350., 360., 380., 400., 450., 500.):
        gp, gs = log_slope(pm, T, t_p), log_slope(sm, T, t_s)
        gain.append({'T_K': T,
                     'pipeline_rel': float(pm.scale(T, t_p)),
                     CURVE + '_rel': float(sm.scale(T, t_s)),
                     CURVE + '_over_pipeline':
                         float(sm.scale(T, t_s)) / float(pm.scale(T, t_p)),
                     'pipeline_dln_dT': gp, CURVE + '_dln_dT': gs,
                     'gain_ratio_sim_over_pipe': gs / gp if gp else None})

    holding = [r for r in comparison if r['pipeline_peak_C'] is not None
               and not r[CURVE + '_diverged'] and not r[CURVE + '_unconverged']
               and r[CURVE + '_peak_C'] is not None]
    band = (min(r[CURVE + '_peak_C'] for r in holding) + 273.15,
            max(r['pipeline_peak_C'] for r in holding) + 273.15) if holding else (None, None)
    in_band = [g for g in gain if band[0] and band[0] <= g['T_K'] <= band[1] + 15]
    max_gain_ratio = max((g['gain_ratio_sim_over_pipe'] for g in in_band
                          if g['gain_ratio_sim_over_pipe']), default=None)

    out = {
        'note': __doc__.strip(),
        # `[!]` The docstring above is written about the `simulated` curve, which is what the
        # default run compares. Name the curve this file actually holds so the two cannot be
        # confused by a reader who trusts the prose over the keys.
        'curve': CURVE,
        'ladders': {'pipeline': os.path.relpath(args.pipeline_base, _REPO),
                    CURVE: os.path.relpath(args.simulated_base, _REPO)},
        'cliffs': {a: {'pipeline': {'highest_holding': cliffs[a]['pipeline'][0],
                                    'lowest_failing': cliffs[a]['pipeline'][1],
                                    'unconverged_densities': cliffs[a]['pipeline'][2]},
                       CURVE: {'highest_holding': cliffs[a][CURVE][0],
                               'lowest_failing': cliffs[a][CURVE][1],
                               'unconverged_densities': cliffs[a][CURVE][2]},
                       'first_failing_moved': bool(fail_moved[a]),
                       'highest_holding_moved': bool(hold_moved[a]),
                       'ceiling_moved': bool(moved[a])} for a in arms},
        'n_common_points': len(common),
        'n_verdict_flips': verdict_flips,
        'max_abs_peak_delta_K': float(np.max(np.abs(peak_deltas))) if peak_deltas else None,
        'comparison': comparison,
        'operating_band_K': list(band),
        'feedback_gain': gain,

        'FINDING_1_THE_CEILING_MOVES_AND_IT_MOVES_DOWN': (
            'Both arms degrade, in two different ways. ' +
            ' '.join(
                '{}: first-failing {} -> {} ({}); highest demonstrated hold {} -> {}{}.'.format(
                    a, cliffs[a]['pipeline'][1], cliffs[a][CURVE][1],
                    'MOVED DOWN' if fail_moved[a] else 'unchanged',
                    cliffs[a]['pipeline'][0], cliffs[a][CURVE][0],
                    ' (the previously-holding rung{} {} now flagged unconverged, so {} not a '
                    'demonstrated hold)'.format(
                        '' if len(cliffs[a][CURVE][2]) == 1 else 's',
                        ', '.join(str(d) for d in cliffs[a][CURVE][2]),
                        'it is' if len(cliffs[a][CURVE][2]) == 1 else 'they are')
                    if cliffs[a][CURVE][2] else '')
                for a in arms) +
            ' {} of {} common points flip verdict. Peaks of the points that survive on both curves '
            'move by up to {:.1f} K{}.'
            .format(verdict_flips, len(common),
                    float(np.max(np.abs(peak_deltas))) if peak_deltas else float('nan'),
                    (', and the sign is NOT constant -- cooler points get cooler and hotter '
                     'points get hotter, which is the signature of a curve that is steeper '
                     'through the operating band rather than uniformly higher or lower'
                     if peak_deltas and min(peak_deltas) < 0 < max(peak_deltas) else
                     ', all in the same direction ({})'.format(
                         'cooler' if peak_deltas and max(peak_deltas) < 0 else 'hotter')
                     if peak_deltas else ''))),

        'FINDING_2_THE_PREDICTED_DIRECTION_WAS_WRONG': (
            'P0.12 predicted the ceiling would move UP. Its argument: the pipeline tail is ~6x too '
            'steep at 450 K, a gentler tail runs away later, so P0.11\'s 1.0-1.2 W/mm^2 flat-die '
            'ceiling is CONSERVATIVE. P0.13 then measured a 47x gap at 500 K, which made the '
            'prediction look safe. **It is wrong, and the ceiling moves the other way.** '
            '`[!]` The claim "P0.11\'s ceiling is conservative" is WITHDRAWN.'),

        'FINDING_3_WHY_RUNAWAY_IS_DECIDED_WHERE_THE_DIE_SITS_NOT_AT_500K': (
            'Thermal runaway is a LOCAL instability: what matters is d(ln P_leak)/dT at the '
            'temperature the die is actually at, not leakage at 500 K -- by 500 K it has already '
            'run away under either curve, so the 47x disagreement lives where the answer does not '
            'live. The surviving points occupy roughly {:.0f}-{:.0f} K, and in that band the '
            'ordering REVERSES: the pipeline curve is nearly flat there (0.0013/K at 310 K, '
            '0.0091/K at 330 K, because that is where CACTI\'s table is clamped or barely moving) '
            'while the simulated curve has a real ~0.036/K slope throughout. The simulated curve '
            'therefore carries up to {:.1f}x MORE feedback gain inside the band where stability '
            'is decided, and the two cross over at about 345 K. More gain runs away EARLIER, '
            'which is what the ladder shows.'
            .format(band[0] or float('nan'), band[1] or float('nan'),
                    max_gain_ratio or float('nan'))),

        'FINDING_4_THE_ERROR_THAT_MATTERS_IS_THE_COLD_END_NOT_THE_TAIL': (
            'This relocates the defect worth caring about. The pipeline curve\'s most consequential '
            'error for the density ceiling is NOT its 47x-too-steep hot tail -- that region is '
            'never reached by a surviving die. It is that the curve is nearly FLAT at 310-330 K, '
            'understating the feedback gain by up to {:.0f}x exactly where dies operate, which '
            'makes every recorded ceiling optimistic. The same flatness is what made the cold-zone '
            'prize look small (P0.14): one clamp, two wrong answers, in opposite directions.'
            .format(max_gain_ratio or float('nan'))),

        'HONEST_LIMITS': (
            'The ladder is 0.20-0.40 W/mm^2 coarse near the cliff, so a move is resolved only to '
            'the nearest rung; the sub-rung evidence is the peak temperatures, and '
            'scripts/uniform_density_ladder_fine.sh refines it to 0.05 W/mm^2. '
            + ('`[!]` This file is the {} bracket. The GIDL bracket question it was run to answer '
               'is CLOSED and the answer is negative: the uniform arm has the SAME highest holding '
               'and lowest failing rung under both brackets. The reason the earlier note below was '
               'wrong is that it compared leakage LEVELS between brackets, where runaway is set by '
               'the SLOPE -- across 316-328 K the brackets differ 1.16-1.27x in gain against the '
               '6-14x the pipeline->simulated swap carries. '.format(CURVE)
               if CURVE != 'simulated' else
               'Only the full-GIDL simulated bracket was run here: GIDL is a cold-end mechanism '
               'and the two brackets differ 14-15 % at 450-500 K, well inside a rung. `[+]` The '
               'GIDL-off ladder has SINCE been run (P0.15, uniform_density_curve_compare_gidl_off'
               '.json) and the bracket does not move the uniform arm at all -- the worry recorded '
               'here that it "differs much more at 310 K, so the bracket is a real open question" '
               'was about the leakage LEVEL, and runaway is set by the SLOPE, which differs only '
               '1.16-1.27x across the band that decides it. The question is closed, negatively. ')
            + '`[!]` The peak deltas above EXCLUDE the rows flagged `unconverged`, which is correct '
            '(such a peak must not be quoted) but hides the largest movement in the campaign: '
            'shaped 0.60 sits at 85.54 C on the simulated curve against 73.48 C on the pipeline '
            'one, +12.1 K at the same density, and its peak is stable to 0.01 K across all three '
            'damping levels even though the residual never meets tolerance. Directional evidence, '
            'not a citable number -- and it is why the surviving deltas being NEGATIVE is not a '
            'contradiction: the simulated curve sits below the pipeline curve at 317-329 K and '
            'above it by ~346 K, so cool points cool and hot points heat. '
            'Rows flagged `unconverged` are counted as NEITHER holding nor failing here (the stock '
            'uniform_density_report counts any non-diverged row as holding, which was right for '
            'the recorded ladder where nothing was flagged). Everything else is identical between '
            'the two campaigns -- same die, package, RBB policy, arms, convergence settings, '
            'verified field by field -- and the pipeline ladder is the recorded P0.11 one rather '
            'than a re-run, so the two were produced by the same code at different times.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)

    print(__doc__.split('\n')[0])
    print('\nCLIFFS (highest holding -> lowest failing):')
    for a in arms:
        c = cliffs[a]
        print('  %-8s pipeline %s -> %s   %s %s -> %s   %s%s'
              % (a, c['pipeline'][0], c['pipeline'][1], CURVE, c[CURVE][0], c[CURVE][1],
                 '** MOVED **' if moved[a] else 'unchanged',
                 '   [unconverged: %s]' % c[CURVE][2] if c[CURVE][2] else ''))
    print('\nPOINT BY POINT (%d common):' % len(common))
    print('   %-8s %6s | %-11s %-11s | %s' % ('arm', 'dens', 'pipeline', CURVE, 'dPeak'))
    for r in comparison:
        def v(pre):
            if r[pre + '_unconverged']:
                return 'UNCONVERGED'
            return 'DIVERGED' if r[pre + '_diverged'] else 'holds'
        print('   %-8s %6.2f | %-11s %-11s | %s'
              % (r['arm'], r['density_W_per_mm2'], v('pipeline'), v(CURVE),
                 ('%+.2f K' % r['delta_peak_K']) if 'delta_peak_K' in r else '--'))
    print('\n  verdict flips: %d / %d' % (verdict_flips, len(common)))
    print('\nFEEDBACK GAIN d(ln leak)/dT -- what actually decides stability:')
    print('   %6s %10s %10s | %11s %11s %8s'
          % ('T_K', 'pipeline', CURVE, 'gain pipe', 'gain sim', 'sim/pipe'))
    for g in gain:
        print('   %6.0f %10.4g %10.4g | %11.4f %11.4f %8s'
              % (g['T_K'], g['pipeline_rel'], g[CURVE + '_rel'],
                 g['pipeline_dln_dT'], g[CURVE + '_dln_dT'],
                 '%.2f' % g['gain_ratio_sim_over_pipe']
                 if g['gain_ratio_sim_over_pipe'] else '--'))
    if band[0] is not None:
        print('\n  holding points occupy %.0f-%.0f K' % band)
    else:
        print('\n  `[!]` NO point holds on both ladders -- the operating band is undefined, and '
              'the gain table below cannot be narrowed to it.')
    print('\n' + out['FINDING_1_THE_CEILING_MOVES_AND_IT_MOVES_DOWN'])
    print('\n' + out['FINDING_3_WHY_RUNAWAY_IS_DECIDED_WHERE_THE_DIE_SITS_NOT_AT_500K'])
    print('\nwritten: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
