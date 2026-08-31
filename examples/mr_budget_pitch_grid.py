#!/usr/bin/env python
"""Test 6g: does the budget cliff move with tile pitch?

    scripts/mr_budget_pitch_sweep.sh <jobid>
    python examples/mr_budget_pitch_grid.py

Test 6e found efficacy flat to the target block's own power and then a cliff, caused by the aimed
block ceasing to be the die peak. The obvious hypothesis was that a COARSE tile, which spans the
target and its neighbours, cools the runner-up as well and so delays or removes the migration --
making fine and coarse pitch a genuine trade rather than better and worse, with a crossing point
that would be a design number.

**Half right, and the half that fails is the half that mattered.** Coarse pitch DOES delay the
cliff, monotonically -- 50 and 200 um migrate after 16 W, 500 um after 24 W, and 2000 um has not
migrated at all by 45 W, the top of the ladder. So the collateral-cooling mechanism is real, large,
and exactly as hypothesised. But the delay is bought with plateau height and it never pays for
itself: fine pitch wins at EVERY budget measured, including the ones where it has cliffed and the
coarse pitch has not (1.030 against 0.899 K/W at 45 W). The best coarse pitch only draws level
once fine has already cliffed (1.396 against 1.395 K/W at 32 W), and by then both are bulk cooling
rather than aiming.

So there is no crossing point and no trade to design around. What the grid does establish is that
the two variables are close to separable:

  * pitch is a hardware choice and it sets the HEIGHT of the efficacy plateau;
  * pitch ALSO moves where that plateau ends, substantially -- but in the opposite direction, and
    the height term dominates at every budget measured.

An array vendor therefore cannot buy their way past a bad power map with tile geometry in either
direction -- finer or coarser.
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

TARGET_BLOCK_W = 16.0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--results', default=os.path.join(_REPO, 'results', 'mr_budget'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'mr_budget_pitch_grid.json'))
    args = ap.parse_args()

    grid = {}
    for p in sorted(glob.glob(os.path.join(args.results, 'p*', 'w*', 'tile_pitch.json'))):
        pitch = float(re.search(r'[/\\]p(\d+)[/\\]', p).group(1))
        d = json.load(open(p))
        r = d['rows'][0]
        grid.setdefault(pitch, []).append({
            'budget_W': d['mr_W'], 'peak_C': r['peak_C'], 'peak_drop_K': r['peak_drop_K'],
            'K_per_W_lifted': r['K_per_W'], 'target_C': r['target_C'],
            'base_peak_C': d['base_peak_C'],
            'collateral_area_ratio': r['collateral_area_ratio'],
            'target_is_peak': abs(r['target_C'] - r['peak_C']) < 0.01,
            'budget_over_block_power': d['mr_W'] / TARGET_BLOCK_W})
    if not grid:
        raise SystemExit('no solves under {} -- run scripts/mr_budget_pitch_sweep.sh'
                         .format(args.results))
    for v in grid.values():
        v.sort(key=lambda r: r['budget_W'])

    pitches = sorted(grid)
    budgets = sorted({r['budget_W'] for v in grid.values() for r in v})
    print('K per watt lifted.  * = the aimed block is no longer the die peak\n')
    print('%-9s' % 'budget W' + ''.join('%12s' % ('%.0f um' % p) for p in pitches))
    for W in budgets:
        line = '%-9.0f' % W
        for p in pitches:
            m = [r for r in grid[p] if r['budget_W'] == W]
            line += '%12s' % ('%.3f%s' % (m[0]['K_per_W_lifted'],
                                          '' if m[0]['target_is_peak'] else '*') if m else '--')
        print(line)

    print('\n%-10s %12s %12s %20s %14s'
          % ('pitch um', 'plateau K/W', 'collateral', 'migrates after', 'K/W past cliff'))
    summary = []
    for p in pitches:
        v = grid[p]
        plateau = v[0]['K_per_W_lifted']
        still = [r['budget_W'] for r in v if r['target_is_peak']]
        lo = max(still) if still else None
        past = [r['K_per_W_lifted'] for r in v if not r['target_is_peak']]
        summary.append({'pitch_um': p, 'plateau_K_per_W': plateau,
                        'collateral_area_ratio': v[0]['collateral_area_ratio'],
                        'migrates_after_W': lo,
                        'migrates_after_x_block': lo / TARGET_BLOCK_W if lo else None,
                        'K_per_W_past_cliff': min(past) if past else None,
                        'n_budgets': len(v)})
        print('%-10.0f %12.3f %11.2fx %20s %14s'
              % (p, plateau, v[0]['collateral_area_ratio'],
                 ('%.0f W (%.2fx block)' % (lo, lo / TARGET_BLOCK_W)) if lo else 'never',
                 ('%.3f' % min(past)) if past else 'pending'))

    fine = min(pitches)
    coarse = max(pitches)
    ratio = grid[fine][0]['K_per_W_lifted'] / grid[coarse][0]['K_per_W_lifted']
    out = {
        'note': __doc__.strip(),
        'driver': 'scripts/mr_budget_pitch_sweep.sh + examples/tile_pitch_sweep.py',
        'fixed': {'floorplan': 'skylake10nm_7core_0_3D-ICE_template.flp', 'target': 'L3_4',
                  'concentrate': 4.0, 'die_W': 100.0, 'target_block_W': TARGET_BLOCK_W,
                  'burial_um': 200.0, 'cell_um': 50.0},
        'grid': {str(p): grid[p] for p in pitches},
        'per_pitch': summary,
        'THE_DELAY_IS_REAL_AND_NOT_WORTH_BUYING': (
            'Coarse tiles cool the runner-up as well as the target, and they do delay the '
            'migration that causes the cliff -- monotonically, and by a lot: 50 and 200 um '
            'migrate after 16 W, 500 um after 24 W, and 2000 um has not migrated at all by 45 W, '
            'the top of the ladder. The hypothesised mechanism is real and large. But the delay '
            'is bought with plateau height and it never pays for itself. Fine pitch wins at EVERY '
            'budget measured -- including 45 W, where fine has already cliffed to 1.030 K/W and '
            'coarse, still aiming, manages only 0.899. The coarsest pitch starts {:.2f}x lower '
            '({:.3f} against {:.3f} K/W), and the best coarse pitch draws level only once fine '
            'has cliffed (1.396 against 1.395 K/W at 32 W), by which point both are bulk cooling '
            'rather than aiming. There is no crossing point worth designing around.'
            .format(ratio, grid[fine][0]['K_per_W_lifted'], grid[coarse][0]['K_per_W_lifted'])),
        'PITCH_AND_PLAN_SIZE_ARE_NEARLY_SEPARABLE': (
            'Pitch sets the HEIGHT of the efficacy plateau and it also moves WHERE that plateau '
            'ends -- but the two move in opposite directions and the height term dominates '
            'everywhere measured. That is the useful form of the result: the cliff is not a hard '
            'floorplan property that hardware cannot touch, but no tile geometry buys past a bad '
            'power map, because every rung of delay costs more plateau than it returns. Choose '
            'pitch for efficacy, size the plan from the runner-up gap, and re-aim rather than '
            'over-drive.'),
        'WHAT_THIS_DOES_NOT_SHOW': (
            'One shape (--concentrate 4.0 on L3_4) and one burial depth, single-target plans, '
            'linear solves without leakage feedback. The uniform-workload case is known to order '
            'pitches the OTHER way (tile_pitch_uniform.json), so this grid describes the '
            'concentrated regime only.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\n' + out['PITCH_AND_PLAN_SIZE_ARE_NEARLY_SEPARABLE'])
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
