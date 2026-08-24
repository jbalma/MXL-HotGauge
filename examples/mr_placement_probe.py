#!/usr/bin/env python
"""Does the burial depth of the active layer matter? Only if the cooling happens above it.

The question this settles
-------------------------
Microrefrigeration used to be applied as *negative power on processor floorplan blocks*. Those
powers land in the die's own ``source`` layer -- the same 20 um of silicon the transistors are in.
Cooling and heating were therefore co-located, and **the extracted watt crossed no silicon at
all**. Under that arrangement, sweeping how deep the transistors are buried moves material that no
heat flows through on its way to the cooler, so the burial depth cannot change the answer. Not
approximately: by construction.

The hardware puts the cooling in a tile array bonded to the exposed silicon, above the die. A watt
made in the transistors has to climb the burial depth and cross the bond before anything removes
it. This probe runs both arrangements on the same stack, same power, same tiles, same watts of
removal, at several burial depths, and reports what changes.

Method
------
Three columns at each depth:

  none      no cooling at all -- the baseline the other two are measured against
  source    the removal subtracted from the target block's own power (the old formulation)
  pixels    the removal applied to the tiles above it, as its own 3D-ICE die element

The observable is the **target block's** temperature, not the die peak. Once a few watts come out
of the hottest block the peak moves elsewhere and stops responding, which hides the effect being
measured. (An earlier version of this probe aimed the cooling at the block with the highest power
*density*, which under uniform power is simply the smallest block -- it ranked 22nd by
temperature, and both arrangements duly gave the same answer. Aim at the block the no-MR solve
says is hottest.)

These are linear solves with no leakage feedback, deliberately: the only thing moving between
columns is geometry.

Usage
-----
    python examples/mr_placement_probe.py --out-dir results/mr_placement \\
        --depths 360 100 20 --mr-W 3.0
"""
import os
import re
import sys
import json
import time
import argparse
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.die_stack import StackSpec, render_stack_text
from HotGauge.thermal.ICE import ICE_DIR
from HotGauge.thermal.mr_array import (tile_grid, write_mr_floorplan, project_plan_to_tiles,
                                       tile_powers_for_stack, blocks_from_floorplan,
                                       coverage_report, DEFAULT_PITCH_UM)
from HotGauge.utils.floorplan import Floorplan

EMULATOR = os.path.join(ICE_DIR, 'bin', '3D-ICE-Emulator')

#: Silicon left below the active layer, held constant so the sweep isolates the path UP.
BELOW_UM = 20.0


def _powers_in(text):
    return sum(float(x) for x in re.findall(r'power values ([-0-9.eE+]+)\s*;', text))


def _write_case(d, spec, die_powers, tile_powers, flp_template, chip_w, chip_h):
    """Write one case, refusing to proceed if the powers did not actually land.

    A floorplan with literal numbers -- one taken from a previous run directory rather than the
    template -- passes through ``str.format`` untouched, and the case silently runs with someone
    else's powers. That has bitten this project before and it bit this probe during development.
    """
    os.makedirs(d, exist_ok=True)
    die_txt = flp_template.format(powers={k: '{:.6f}'.format(v) for k, v in die_powers.items()})
    if abs(_powers_in(die_txt) - sum(die_powers.values())) > 1e-3:
        raise ValueError('die powers did not land in {}: wrote {:.4f} W, meant {:.4f} W'
                         .format(d, _powers_in(die_txt), sum(die_powers.values())))
    with open(os.path.join(d, 'IC.flp'), 'w') as f:
        f.write(die_txt)

    write_mr_floorplan(os.path.join(d, 'MR.flp'), TILES)
    with open(os.path.join(d, 'MR.flp')) as f:
        mr_tmpl = f.read()               # read BEFORE opening for write; 'w' truncates first
    mr_txt = mr_tmpl.format(powers={k: '{:.6f}'.format(v) for k, v in tile_powers.items()})
    if abs(_powers_in(mr_txt) - sum(tile_powers.values())) > 1e-3:
        raise ValueError('MR powers did not land in {}'.format(d))
    with open(os.path.join(d, 'MR.flp'), 'w') as f:
        f.write(mr_txt)

    stk = render_stack_text(spec).format(
        flp_width='{:.0f}'.format(chip_w), flp_height='{:.0f}'.format(chip_h),
        flp_file='IC.flp', mr_flp_file='MR.flp',
        solver_config='   steady ;\n   initial temperature 300.0 ;',
        output_list='   Tflp (PROCESSOR_DIE, "die.temps", maximum, final ) ;\n'
                    '   Tflp (MR_ARRAY, "mr.temps", average, final ) ;')
    with open(os.path.join(d, 'IC.stk'), 'w') as f:
        f.write(stk)
    return _powers_in(die_txt), _powers_in(mr_txt)


def _read_temps(path):
    """``{element: K}`` from a 3D-ICE Tflp output, by column name."""
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        lines = f.read().split('\n')
    if len(lines) < 3:
        return None
    names = [x.strip()[:-3] for x in lines[1].split('\t')[1:] if x.strip()]
    vals = [float(x) for x in lines[2].split('\t')[1:] if x.strip()]
    return dict(zip(names, vals))


TILES = None


def main():
    global TILES
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out-dir', default=os.path.join(_REPO, 'results', 'mr_placement'))
    ap.add_argument('--flp', default=os.path.join(_HERE, 'floorplans', 'outputs',
                                                  'skylake10nm_7core_0_3D-ICE_template.flp'))
    ap.add_argument('--depths', type=float, nargs='+', default=[360.0, 100.0, 20.0])
    ap.add_argument('--die-W', type=float, default=100.0)
    ap.add_argument('--mr-W', type=float, default=3.0,
                    help='watts removed. Keep it well under the target block\'s own power, or '
                         'the block stops setting the peak and the measurement saturates')
    ap.add_argument('--pitch-um', type=float, default=DEFAULT_PITCH_UM)
    ap.add_argument('--cell-um', type=float, default=100.0)
    ap.add_argument('--mr-material', default='GAAS')
    ap.add_argument('--mr-um', type=float, default=30.0)
    ap.add_argument('--target', default=None,
                    help='block to cool; default is whichever the no-MR solve reports hottest')
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    with open(args.flp) as f:
        flp_template = f.read()
    if '{powers[' not in flp_template:
        raise SystemExit('{} has no power placeholders -- it is a filled floorplan from a run '
                         'directory, not a template'.format(args.flp))
    flp = Floorplan.from_file(args.flp, frmt='3D-ICE')
    blocks = blocks_from_floorplan(flp)
    chip_w = max(b[0] + b[2] for b in blocks.values())
    chip_h = max(b[1] + b[3] for b in blocks.values())
    chip_w, chip_h = math_ceil(chip_w, args.cell_um), math_ceil(chip_h, args.cell_um)
    die_powers = {n: args.die_W / len(blocks) for n in blocks}
    TILES = tile_grid(chip_w, chip_h, pitch_um=args.pitch_um, cell_um=args.cell_um)

    def run(d):
        t0 = time.time()
        r = subprocess.run([EMULATOR, 'IC.stk'], cwd=d, capture_output=True, text=True)
        if r.returncode != 0 or 'error' in (r.stdout + r.stderr).lower():
            raise SystemExit('3D-ICE failed in {}:\n{}\n{}'.format(d, r.stdout[-800:],
                                                                   r.stderr[-800:]))
        return time.time() - t0

    # Pass 1: the baseline at the deepest burial, to find the block that actually sets the peak.
    deepest = max(args.depths)
    spec0 = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                      die_um=deepest + 20.0 + BELOW_UM, source_depth_um=deepest,
                      source_um=20.0, mr_material=args.mr_material, mr_um=args.mr_um,
                      cell_um=args.cell_um)
    d0 = os.path.join(args.out_dir, 'd{:.0f}_none'.format(deepest))
    _write_case(d0, spec0, die_powers, tile_powers_for_stack({}, TILES), flp_template,
                chip_w, chip_h)
    print('baseline solve to pick the target block ...', flush=True)
    run(d0)
    base = _read_temps(os.path.join(d0, 'die.temps'))
    target = args.target or max(base, key=base.get)
    bx, by, bw, bh = blocks[target]
    print('target: {} ({:.0f} x {:.0f} um), hottest at {:.2f} C with no cooling'
          .format(target, bw, bh, base[target] - 273.15))

    tile_plan = project_plan_to_tiles({target: args.mr_W}, blocks, TILES)
    cov = coverage_report({target: args.mr_W}, tile_plan, blocks, TILES)
    print('tiles: {} at {:.0f} um pitch, {} engaged, {:.1f}x the requested die area'
          .format(cov['n_tiles'], args.pitch_um, cov['n_engaged'],
                  cov['collateral_area_ratio']))

    rows = []
    for depth in args.depths:
        spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                         die_um=depth + 20.0 + BELOW_UM, source_depth_um=depth, source_um=20.0,
                         mr_material=args.mr_material, mr_um=args.mr_um, cell_um=args.cell_um)
        temps = {}
        for where in ('none', 'source', 'pixels'):
            d = os.path.join(args.out_dir, 'd{:.0f}_{}'.format(depth, where))
            dp = dict(die_powers)
            if where == 'source':
                dp[target] -= args.mr_W
            tp = tile_powers_for_stack(tile_plan if where == 'pixels' else {}, TILES)
            _write_case(d, spec, dp, tp, flp_template, chip_w, chip_h)
            if not os.path.isfile(os.path.join(d, 'die.temps')):
                run(d)
            temps[where] = _read_temps(os.path.join(d, 'die.temps'))[target] - 273.15
        rows.append({'burial_um': depth, 'no_mr_C': temps['none'],
                     'source_C': temps['source'], 'pixels_C': temps['pixels'],
                     'gain_source_K': temps['source'] - temps['none'],
                     'gain_pixels_K': temps['pixels'] - temps['none']})
        r = rows[-1]
        print('  burial {:>4.0f} um:  no MR {:7.3f} C   MR@source {:+.3f} K   MR@pixels {:+.3f} K'
              '   over-stated {:.2f}x'
              .format(depth, r['no_mr_C'], r['gain_source_K'], r['gain_pixels_K'],
                      r['gain_source_K'] / r['gain_pixels_K']), flush=True)

    gs = [abs(r['gain_source_K']) for r in rows]
    gp = [abs(r['gain_pixels_K']) for r in rows]
    out = {'note': 'what the burial depth is worth, as a function of WHERE the cooling is '
                   'applied. Linear solves, no leakage feedback: only geometry moves.',
           'driver': 'examples/mr_placement_probe.py', 'target': target,
           'target_um': [bw, bh], 'die_W': args.die_W, 'mr_W': args.mr_W,
           'pitch_um': args.pitch_um, 'cell_um': args.cell_um, 'coverage': cov, 'rows': rows,
           'span_source_K': max(gs) - min(gs), 'span_pixels_K': max(gp) - min(gp)}
    path = os.path.join(args.out_dir, 'summary.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nacross {:.0f} -> {:.0f} um of burial, the MR gain moves {:.2f} K when the removal is '
          'in the\nsource layer and {:.2f} K when it is in the pixels. The first is the '
          'measurement noise\nfloor of a changing baseline; the second is the design parameter.'
          .format(max(args.depths), min(args.depths), out['span_source_K'],
                  out['span_pixels_K']))
    print('wrote {}'.format(path))
    return 0


def math_ceil(v, step):
    import math
    return math.ceil(v / step) * step


if __name__ == '__main__':
    sys.exit(main())
