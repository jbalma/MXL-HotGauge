#!/usr/bin/env python
"""Post-mortem inspector for leakage-feedback iteration directories.

Walks a stage2/ directory produced by the smoke test (iter_000, iter_001, ...) and, from the
files already on disk, reconstructs what the loop did at every iteration:

  * total power fed to 3D-ICE (parsed from each iter's filled IC.flp), and
  * each block's solved temperature (from die_elements.temps),

then prints the per-iteration summary plus temperature trajectories for the blocks that ended
hottest / grew the most. Use it to distinguish a GRADUAL RATCHET (block temp climbing a few K
per iteration -> genuine local electro-thermal runaway at these leakage settings) from a
SOLVER SPIKE (temp jumping orders of magnitude in one iteration -> numerical/co-simulation
instability, e.g. the heatsink FMU).

Usage:
    python examples/inspect_feedback_iters.py leakage_feedback_smoketest/skylake_HS483/stage2
    python examples/inspect_feedback_iters.py <stage2_dir> --top 8
"""
import os
import re
import sys
import glob
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), 'HotGauge'))

from HotGauge.thermal.ICE import load_3DICE_block_file
from HotGauge.thermal.utils import K_to_C

_POWER_RGX = re.compile(r'^\s*power\s+values\s+(.*?)\s*;\s*$')


def total_power_from_flp(flp_file):
    """Sum the per-slot power over all blocks in a filled IC.flp; return the per-slot totals."""
    totals = None
    with open(flp_file) as f:
        for line in f:
            m = _POWER_RGX.match(line)
            if not m:
                continue
            vals = np.array([float(v) for v in m.group(1).split(',')], dtype=float)
            totals = vals if totals is None else totals + vals
    return totals


def iter_dirs(stage_dir):
    dirs = glob.glob(os.path.join(stage_dir, 'iter_[0-9]*'))
    def idx(d):
        m = re.search(r'iter_(\d+)$', d)
        return int(m.group(1)) if m else -1
    return sorted(dirs, key=idx)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stage_dir', help='e.g. leakage_feedback_smoketest/skylake_HS483/stage2')
    ap.add_argument('--top', type=int, default=6, help='trajectories for the top-N blocks')
    ap.add_argument('--t-floor-K', type=float, default=200.0,
                    help='ignore blocks below this temp (0 K = outside die layer)')
    args = ap.parse_args()

    dirs = iter_dirs(args.stage_dir)
    if not dirs:
        print('No iter_* directories under {}'.format(args.stage_dir))
        return 1

    per_iter = []   # (idx, total_W_mean, temps_dict {block: max_T_K over slots})
    for d in dirs:
        idx = int(re.search(r'iter_(\d+)$', d).group(1))
        tfile = os.path.join(d, 'die_elements.temps')
        ffile = os.path.join(d, 'IC.flp')
        temps = None
        if os.path.isfile(tfile) and os.path.getsize(tfile) > 0:
            try:
                raw = load_3DICE_block_file(tfile, convert_K_to_C=False)
                temps = {b: float(np.max(v)) for b, v in raw.items()
                         if np.size(v) and float(np.max(v)) >= args.t_floor_K}
            except Exception as e:
                print('  ! could not parse {}: {}'.format(tfile, e))
        ptot = total_power_from_flp(ffile) if os.path.isfile(ffile) else None
        per_iter.append((idx, ptot, temps))

    print('Per-iteration summary  ({} dirs under {})'.format(len(per_iter), args.stage_dir))
    print('  iter | power in: mean/max slot [W] | hottest block (max T)')
    for idx, ptot, temps in per_iter:
        p_str = '{:10.2f} / {:10.2f}'.format(np.mean(ptot), np.max(ptot)) \
                if ptot is not None else '        (no IC.flp)  '
        if temps:
            hot = max(temps, key=temps.get)
            t_str = '{:<16s} {:9.1f} K ({:8.1f} C)'.format(hot, temps[hot], K_to_C(temps[hot]))
        else:
            t_str = '(no die_elements.temps -- solve failed or not run)'
        print('  {:>4d} | {} | {}'.format(idx, p_str, t_str))

    # Trajectories: union of blocks that ended hottest and that grew the most.
    seq = [(idx, temps) for idx, _, temps in per_iter if temps]
    if len(seq) < 2:
        print('\nFewer than 2 parseable iterations -- no trajectories to show.')
        return 0
    first, last = seq[0][1], seq[-1][1]
    blocks = set(sorted(last, key=last.get, reverse=True)[:args.top])
    growth = {b: last[b] - first.get(b, last[b]) for b in last}
    blocks |= set(sorted(growth, key=growth.get, reverse=True)[:args.top])

    print('\nTemperature trajectories [C] (top blocks by final temp and by growth):')
    hdr = '  {:<20s}'.format('block') + ''.join('{:>9d}'.format(i) for i, _ in seq)
    print(hdr)
    for b in sorted(blocks, key=lambda b: -last.get(b, -np.inf)):
        row = '  {:<20s}'.format(b[:20])
        for _, temps in seq:
            row += '{:>9.1f}'.format(K_to_C(temps[b])) if b in temps else '{:>9s}'.format('-')
        print(row)

    # Simple verdict heuristic: largest single-iteration jump of the hottest block.
    hot_final = max(last, key=last.get)
    traj = [temps.get(hot_final) for _, temps in seq if temps.get(hot_final) is not None]
    if len(traj) >= 2:
        jumps = np.diff(traj)
        print('\nHottest block {}: start {:.1f} C, end {:.1f} C, largest single-iter jump '
              '{:+.1f} K'.format(hot_final, K_to_C(traj[0]), K_to_C(traj[-1]), np.max(jumps)))
        if np.max(jumps) > 200:
            print('  -> looks like a SOLVER SPIKE (order-of-magnitude jump in one iteration)')
        elif traj[-1] > traj[0] + 5:
            print('  -> looks like a GRADUAL RATCHET (leakage/temperature gain > 1 at this '
                  'block under the current leakage settings)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
