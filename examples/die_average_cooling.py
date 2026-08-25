#!/usr/bin/env python
"""Can a cooling array move the die-average thermal path, or only shave hotspots?

The claim under test
--------------------
The handbook says, and the runs supported:

    "MR is weak as a clock enabler. The clock ceiling is set by the die-average thermal path,
     which hotspot clipping barely touches."

That was measured with the cooling applied as negative power on individual floorplan blocks --
a *point* device. The photonic array is not a point device: it is an area device covering the
whole die, and the tile-pitch sweep showed that a coarse tile beats a fine one by 59% on a
degenerate peak precisely because it cools broadly rather than sharply. So "hotspot clipping
barely moves the die average" may be a true statement about the wrong instrument.

This compares spatial *strategies* at equal total removal, which is the comparison the old
formulation could not express because it had only one strategy.

    hotspot        every watt on the tiles over the hottest block
    top5           spread over the tiles above the five hottest blocks
    uniform        spread evenly over every tile on the die -- the die-average attack
    proportional   distributed in proportion to the local power map

``proportional`` is the interesting one physically: it matches extraction to dissipation cell by
cell, which is the arrangement the MR write-up's volumetric argument points at, and the limit in
which the thermal resistance between source and sink stops mattering because nothing has to
travel.

What is measured
----------------
Peak and mean junction temperature against total watts removed, for each strategy. The peak sets
the thermal limit and therefore the clock; the mean is the die-average path the claim is about.
A strategy that moves the mean as well as the peak is a clock enabler; one that moves only the
peak is a hotspot tool.

Linear solves, no leakage feedback: the point is to isolate where the cooling goes. Leakage
would amplify whatever this finds, since it is a positive feedback on temperature.

Usage
-----
    scripts/on_node.sh <jobid> python examples/die_average_cooling.py \\
        --out-dir results/die_average --watts 0 3 10 30 --pitch-um 500
"""
import os
import re
import sys
import json
import time
import argparse
import subprocess

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.die_stack import StackSpec, render_stack_text
from HotGauge.thermal.ICE import ICE_DIR
from HotGauge.thermal.mr_array import (tile_grid, write_mr_floorplan, project_plan_to_tiles,
                                       tile_powers_for_stack, blocks_from_floorplan)
from HotGauge.utils.floorplan import Floorplan

EMULATOR = os.path.join(ICE_DIR, 'bin', '3D-ICE-Emulator')
BELOW_UM = 20.0
STRATEGIES = ('hotspot', 'top5', 'uniform', 'proportional')


def _powers_in(text):
    return sum(float(x) for x in re.findall(r'power values ([-0-9.eE+]+)\s*;', text))


def _read_temps(path):
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        lines = f.read().split('\n')
    if len(lines) < 3:
        return None
    names = [x.strip()[:-3] for x in lines[1].split('\t')[1:] if x.strip()]
    vals = [float(x) for x in lines[2].split('\t')[1:] if x.strip()]
    return {n: v for n, v in zip(names, vals) if v > 200.0}


def build_plan(strategy, watts, blocks, tiles, ranked, die_powers):
    """Tile powers [W, positive = removed] for one strategy at one budget.

    Every strategy removes exactly ``watts``; only the distribution differs. That is the whole
    experiment, so it is asserted by the caller rather than trusted.
    """
    if watts <= 0:
        return {t['name']: 0.0 for t in tiles}
    if strategy == 'hotspot':
        return project_plan_to_tiles({ranked[0]: watts}, blocks, tiles)
    if strategy == 'top5':
        share = watts / 5.0
        return project_plan_to_tiles({b: share for b in ranked[:5]}, blocks, tiles)
    if strategy == 'uniform':
        # Per unit AREA, not per tile: the edge tiles are stretched to the die boundary, so
        # per-tile would quietly over-cool the edges.
        total_area = sum(t['w'] * t['h'] for t in tiles)
        return {t['name']: watts * t['w'] * t['h'] / total_area for t in tiles}
    if strategy == 'proportional':
        # Match extraction to dissipation: each block's share of the removal equals its share of
        # the die power, then projected onto whatever tiles sit above it.
        total_W = sum(die_powers.values())
        return project_plan_to_tiles({b: watts * p / total_W for b, p in die_powers.items()},
                                     blocks, tiles)
    raise ValueError('unknown strategy {!r}'.format(strategy))


def run_case(d, spec, die_powers, tiles, tile_plan, flp_template, chip_w, chip_h):
    os.makedirs(d, exist_ok=True)
    die_txt = flp_template.format(powers={k: '{:.6f}'.format(v) for k, v in die_powers.items()})
    if abs(_powers_in(die_txt) - sum(die_powers.values())) > 1e-3:
        raise ValueError('die powers did not land in {}'.format(d))
    with open(os.path.join(d, 'IC.flp'), 'w') as f:
        f.write(die_txt)

    tp = tile_powers_for_stack(tile_plan, tiles)
    write_mr_floorplan(os.path.join(d, 'MR.flp'), tiles)
    with open(os.path.join(d, 'MR.flp')) as f:
        mr_tmpl = f.read()
    mr_txt = mr_tmpl.format(powers={k: '{:.6f}'.format(v) for k, v in tp.items()})
    if abs(_powers_in(mr_txt) - sum(tp.values())) > 1e-3:
        raise ValueError('tile powers did not land in {}'.format(d))
    with open(os.path.join(d, 'MR.flp'), 'w') as f:
        f.write(mr_txt)

    with open(os.path.join(d, 'IC.stk'), 'w') as f:
        f.write(render_stack_text(spec).format(
            flp_width='{:.0f}'.format(chip_w), flp_height='{:.0f}'.format(chip_h),
            flp_file='IC.flp', mr_flp_file='MR.flp',
            solver_config='   steady ;\n   initial temperature 300.0 ;',
            output_list='   Tflp (PROCESSOR_DIE, "die.temps", maximum, final ) ;\n'
                        '   Tflp (PROCESSOR_DIE, "die_avg.temps", average, final ) ;'))
    if not os.path.isfile(os.path.join(d, 'die.temps')):
        r = subprocess.run([EMULATOR, 'IC.stk'], cwd=d, capture_output=True, text=True)
        if r.returncode != 0 or 'error' in (r.stdout + r.stderr).lower():
            raise SystemExit('3D-ICE failed in {}:\n{}'.format(d, (r.stdout + r.stderr)[-700:]))
    mx = _read_temps(os.path.join(d, 'die.temps'))
    av = _read_temps(os.path.join(d, 'die_avg.temps'))
    return (max(mx.values()) - 273.15, sum(av.values()) / len(av) - 273.15)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out-dir', default=os.path.join(_REPO, 'results', 'die_average'))
    ap.add_argument('--flp', default=os.path.join(_HERE, 'floorplans', 'outputs',
                                                  'skylake10nm_7core_0_3D-ICE_template.flp'))
    ap.add_argument('--watts', type=float, nargs='+', default=[3.0, 10.0, 30.0])
    ap.add_argument('--strategies', nargs='+', default=list(STRATEGIES))
    ap.add_argument('--die-W', type=float, default=100.0)
    ap.add_argument('--pitch-um', type=float, default=500.0)
    ap.add_argument('--cell-um', type=float, default=50.0)
    ap.add_argument('--burial-um', type=float, default=100.0)
    ap.add_argument('--mr-material', default='GAAS')
    ap.add_argument('--mr-um', type=float, default=30.0)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    with open(args.flp) as f:
        flp_template = f.read()
    if '{powers[' not in flp_template:
        raise SystemExit('{} is a filled floorplan, not a template'.format(args.flp))
    blocks = blocks_from_floorplan(Floorplan.from_file(args.flp, frmt='3D-ICE'))
    chip_w = int(np.ceil(max(b[0] + b[2] for b in blocks.values()) / args.cell_um) * args.cell_um)
    chip_h = int(np.ceil(max(b[1] + b[3] for b in blocks.values()) / args.cell_um) * args.cell_um)
    die_powers = {n: args.die_W / len(blocks) for n in blocks}
    tiles = tile_grid(chip_w, chip_h, pitch_um=args.pitch_um, cell_um=args.cell_um)

    spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                     die_um=args.burial_um + 20.0 + BELOW_UM, source_depth_um=args.burial_um,
                     source_um=20.0, mr_material=args.mr_material, mr_um=args.mr_um,
                     cell_um=args.cell_um)

    print('baseline ...', flush=True)
    base_peak, base_mean = run_case(os.path.join(args.out_dir, 'base'), spec, die_powers, tiles,
                                    {}, flp_template, chip_w, chip_h)
    ranked_temps = _read_temps(os.path.join(args.out_dir, 'base', 'die.temps'))
    ranked = sorted(ranked_temps, key=ranked_temps.get, reverse=True)
    print('{} blocks, {:.0f} W, {} tiles at {:.0f} um pitch, burial {:.0f} um'
          .format(len(blocks), args.die_W, len(tiles), args.pitch_um, args.burial_um))
    print('baseline: peak {:.3f} C, die mean {:.3f} C, spread {:.3f} K\n'
          .format(base_peak, base_mean, base_peak - base_mean))
    print('{:>14} {:>7} {:>9} {:>9} {:>10} {:>10}'
          .format('strategy', 'W', 'peak C', 'mean C', 'd peak', 'd mean'))

    rows = []
    for strategy in args.strategies:
        for watts in args.watts:
            plan = build_plan(strategy, watts, blocks, tiles, ranked, die_powers)
            got = sum(plan.values())
            if abs(got - watts) > 1e-3:
                raise SystemExit('{} at {:.1f} W distributed {:.4f} W -- strategies must remove '
                                 'the SAME total or the comparison is meaningless'
                                 .format(strategy, watts, got))
            d = os.path.join(args.out_dir, '{}_{:.0f}W'.format(strategy, watts))
            peak, mean = run_case(d, spec, die_powers, tiles, plan, flp_template, chip_w, chip_h)
            rows.append({'strategy': strategy, 'watts': watts, 'peak_C': peak, 'mean_C': mean,
                         'd_peak_K': peak - base_peak, 'd_mean_K': mean - base_mean,
                         'peak_K_per_W': (base_peak - peak) / watts if watts else None,
                         'mean_K_per_W': (base_mean - mean) / watts if watts else None})
            print('{:>14} {:>7.1f} {:>9.3f} {:>9.3f} {:>9.3f}K {:>9.3f}K'
                  .format(strategy, watts, peak, mean, peak - base_peak, mean - base_mean),
                  flush=True)
        print()

    out = {'note': 'peak and die-mean temperature against total watts removed, for four spatial '
                   'strategies at equal budget. Tests whether an area cooling array can move the '
                   'die-average path that sets the clock ceiling, or only shaves hotspots. '
                   'Linear solves, no leakage feedback.',
           'driver': 'examples/die_average_cooling.py',
           'floorplan': os.path.basename(args.flp), 'die_W': args.die_W,
           'pitch_um': args.pitch_um, 'burial_um': args.burial_um, 'cell_um': args.cell_um,
           'n_tiles': len(tiles), 'base_peak_C': base_peak, 'base_mean_C': base_mean,
           'rows': rows}
    path = os.path.join(args.out_dir, 'die_average.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)

    top = max(args.watts)
    at_top = {r['strategy']: r for r in rows if r['watts'] == top}
    if len(at_top) > 1:
        print('at {:.0f} W removed:'.format(top))
        for s, r in sorted(at_top.items(), key=lambda kv: kv[1]['d_mean_K']):
            print('  {:<14} peak {:+7.3f} K   die mean {:+7.3f} K   mean/peak {:5.2f}'
                  .format(s, r['d_peak_K'], r['d_mean_K'],
                          r['d_mean_K'] / r['d_peak_K'] if r['d_peak_K'] else float('nan')))
        print('\nA strategy whose mean/peak ratio approaches 1 is moving the whole die, not just')
        print('its hottest corner -- that is what a clock enabler has to do.')
    print('wrote {}'.format(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
