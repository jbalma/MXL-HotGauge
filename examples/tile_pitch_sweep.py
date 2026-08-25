#!/usr/bin/env python
"""How much does finer cooling-tile targeting buy, and does it buy efficiency or effectiveness?

The question
------------
A cooling tile cools whatever sits beneath it, so a coarse array spends watts on silicon that was
not hot. Whether that is waste depends entirely on the die, and the two effects run opposite:

* **On a degenerate peak, collateral cooling is the mechanism.** The CPU results are dominated by
  the plateau -- clipping the single hottest block buys 1.25 K because the second hottest becomes
  the peak immediately. A tile spanning several plateau members clips them together, which
  per-block cooling cannot do at any price. And an over-cooled neighbour is not wasted: it becomes
  a lateral sink, and the heat flowing into it scales with the temperature difference the cooling
  just created.
* **On an isolated hotspot, collateral is waste.** Watts spent on already-cool silicon buy no peak
  reduction, so kelvin-per-watt -- and therefore the COP the whole business case rests on -- gets
  worse.

So this sweep reports **both**: peak reduction (effectiveness) and kelvin per watt removed
(efficiency), at a fixed removal budget, against tile pitch.

Why the pitch range stops where it does
---------------------------------------
3D-ICE must mesh at least as finely as the tiles, and the factorisation scales as N^1.67 from a
measured 90 s at 445k unknowns. On an 8.8 x 6.1 mm die with nine layers:

    pitch      tiles        unknowns     factorisation
    500 um       204         193,248     22 s
    100 um     5,368         193,248     22 s      (mesh already finer than the tiles)
     50 um    21,472         193,248     22 s
     10 um   536,800       4,831,200     1.3 h     (one-off solves; no feedback loop)
      1 um  53,680,000    483,120,000     122 days  (and terabytes of LU factors)

1 um is therefore not reachable, and it is also finer than the 50 um mesh every existing result
was computed on. The sweep runs the pitches that are, down to pitch = cell size.

A block finer than a tile is not a problem and never was: the array is a regular grid and a plan
**engages whichever tiles overlap the target region**, however many that is. RBB_16 on the
34-core die is 142 x 13 um -- thinner than one thermal cell -- and it engages 2 tiles at a
1000 um pitch and 3 at 50 um, with the watts conserved either way. What changes with pitch is not
whether the block can be reached but how much *other* silicon comes along: collateral on that
block runs 1137x at 1000 um, 10.5x at 100 um, 3.9x at 50 um.

``ideal_targeting_tiles`` (one tile per block) is offered as an optional upper bound on what
targeting could ever buy. It is a hypothetical, not a device, and it is only constructible where
blocks are coarser than the mesh -- on the 34-core floorplan 441 block pairs collide once snapped
to a 50 um grid. The sweep skips it and carries on when that happens.

Usage
-----
    python examples/tile_pitch_sweep.py --out-dir results/tile_pitch \\
        --pitches 2000 1000 500 200 100 --mr-W 3.0
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
from HotGauge.thermal.mr_array import (tile_grid, ideal_targeting_tiles, write_mr_floorplan,
                                       project_plan_to_tiles, tile_powers_for_stack,
                                       blocks_from_floorplan, coverage_report)
from HotGauge.utils.floorplan import Floorplan

EMULATOR = os.path.join(ICE_DIR, 'bin', '3D-ICE-Emulator')
BELOW_UM = 20.0


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
    return dict(zip(names, vals))


def _write_and_run(d, spec, die_powers, tiles, tile_powers, flp_template, chip_w, chip_h,
                   run=True):
    os.makedirs(d, exist_ok=True)
    die_txt = flp_template.format(powers={k: '{:.6f}'.format(v) for k, v in die_powers.items()})
    if abs(_powers_in(die_txt) - sum(die_powers.values())) > 1e-3:
        raise ValueError('die powers did not land in {}'.format(d))
    with open(os.path.join(d, 'IC.flp'), 'w') as f:
        f.write(die_txt)

    write_mr_floorplan(os.path.join(d, 'MR.flp'), tiles)
    with open(os.path.join(d, 'MR.flp')) as f:
        mr_tmpl = f.read()               # read BEFORE opening for write; 'w' truncates first
    mr_txt = mr_tmpl.format(powers={k: '{:.6f}'.format(v) for k, v in tile_powers.items()})
    if abs(_powers_in(mr_txt) - sum(tile_powers.values())) > 1e-3:
        raise ValueError('tile powers did not land in {}'.format(d))
    with open(os.path.join(d, 'MR.flp'), 'w') as f:
        f.write(mr_txt)

    with open(os.path.join(d, 'IC.stk'), 'w') as f:
        f.write(render_stack_text(spec).format(
            flp_width='{:.0f}'.format(chip_w), flp_height='{:.0f}'.format(chip_h),
            flp_file='IC.flp', mr_flp_file='MR.flp',
            solver_config='   steady ;\n   initial temperature 300.0 ;',
            output_list='   Tflp (PROCESSOR_DIE, "die.temps", maximum, final ) ;\n'
                        '   Tflp (MR_ARRAY, "mr.temps", average, final ) ;'))
    if run and not os.path.isfile(os.path.join(d, 'die.temps')):
        t0 = time.time()
        r = subprocess.run([EMULATOR, 'IC.stk'], cwd=d, capture_output=True, text=True)
        if r.returncode != 0 or 'error' in (r.stdout + r.stderr).lower():
            raise SystemExit('3D-ICE failed in {}:\n{}\n{}'.format(d, r.stdout[-600:],
                                                                   r.stderr[-600:]))
        return time.time() - t0
    return 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out-dir', default=os.path.join(_REPO, 'results', 'tile_pitch'))
    ap.add_argument('--flp', default=os.path.join(_HERE, 'floorplans', 'outputs',
                                                  'skylake10nm_7core_0_3D-ICE_template.flp'))
    ap.add_argument('--pitches', type=float, nargs='+',
                    default=[2000.0, 1000.0, 500.0, 200.0, 100.0])
    ap.add_argument('--no-ideal', action='store_true',
                    help='skip the optional per-block upper bound (a hypothetical, not a device)')
    ap.add_argument('--die-W', type=float, default=100.0)
    ap.add_argument('--mr-W', type=float, default=3.0,
                    help='total watts removed, held FIXED across pitches -- the sweep is about '
                         'where those watts go, not how many there are')
    ap.add_argument('--cell-um', type=float, default=50.0)
    ap.add_argument('--burial-um', type=float, default=100.0)
    ap.add_argument('--mr-material', default='GAAS')
    ap.add_argument('--mr-um', type=float, default=30.0)
    ap.add_argument('--target', default=None)
    ap.add_argument('--concentrate', type=float, default=1.0,
                    help='multiply the target block\'s power density by this and renormalise the '
                         'rest, holding total die power fixed. 1.0 is the uniform map, which is '
                         'maximally degenerate and where collateral cooling helps most. Raise it '
                         'to build an ISOLATED hotspot -- the case where collateral should turn '
                         'back into waste. This is the falsification test, not a variation.')
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
    if args.concentrate != 1.0:
        if args.target is None:
            raise SystemExit('--concentrate needs an explicit --target: the block to make hot '
                             'must be chosen before the baseline, not after it')
        die_powers[args.target] *= args.concentrate
        # Renormalise everything else so total die power is unchanged; otherwise the sweep would
        # confound "concentrated" with "hotter overall".
        others = args.die_W - die_powers[args.target]
        if others <= 0:
            raise SystemExit('--concentrate {} leaves no power for the other {} blocks'
                             .format(args.concentrate, len(blocks) - 1))
        scale = others / (args.die_W * (len(blocks) - 1) / len(blocks))
        for n in die_powers:
            if n != args.target:
                die_powers[n] *= scale

    spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                     die_um=args.burial_um + 20.0 + BELOW_UM, source_depth_um=args.burial_um,
                     source_um=20.0, mr_material=args.mr_material, mr_um=args.mr_um,
                     cell_um=args.cell_um)

    # Baseline: the array present but inert, so the stack is identical and only the powers move.
    base_tiles = tile_grid(chip_w, chip_h, pitch_um=max(args.pitches), cell_um=args.cell_um)
    d0 = os.path.join(args.out_dir, 'none')
    print('baseline solve ...', flush=True)
    _write_and_run(d0, spec, die_powers, base_tiles, tile_powers_for_stack({}, base_tiles),
                   flp_template, chip_w, chip_h)
    base = _read_temps(os.path.join(d0, 'die.temps'))
    target = args.target or max(base, key=base.get)
    base_peak = max(base.values()) - 273.15
    bw, bh = blocks[target][2], blocks[target][3]
    print('die {:.1f} x {:.1f} mm, {} blocks, {:.0f} W. Peak {:.3f} C at {} ({:.0f} x {:.0f} um)'
          .format(chip_w / 1000, chip_h / 1000, len(blocks), args.die_W, base_peak, target,
                  bw, bh))
    print('removing a fixed {:.1f} W aimed at it, at each pitch. '
          'concentration {:.1f}x, die power {:.1f} W\n'
          .format(args.mr_W, args.concentrate, sum(die_powers.values())))
    print('{:>10} {:>8} {:>9} {:>8} {:>10} {:>11} {:>9}'
          .format('pitch', 'tiles', 'engaged', 'collat', 'peak C', 'peak drop', 'K per W'))

    rows = []
    plans = [('{:.0f}'.format(p), p, tile_grid(chip_w, chip_h, pitch_um=p, cell_um=args.cell_um))
             for p in sorted(args.pitches, reverse=True)]
    if not args.no_ideal:
        try:
            plans.append(('per-block', 0.0, ideal_targeting_tiles(blocks, cell_um=args.cell_um)))
        except ValueError as e:
            print('  (pitch -> 0 endpoint unavailable: {})\n'.format(str(e).split('.')[0]))

    for label, pitch, tiles in plans:
        plan = project_plan_to_tiles({target: args.mr_W}, blocks, tiles)
        cov = coverage_report({target: args.mr_W}, plan, blocks, tiles)
        d = os.path.join(args.out_dir, 'p{}'.format(label.replace('-', '')))
        _write_and_run(d, spec, die_powers, tiles, tile_powers_for_stack(plan, tiles),
                       flp_template, chip_w, chip_h)
        temps = _read_temps(os.path.join(d, 'die.temps'))
        peak = max(temps.values()) - 273.15
        drop = base_peak - peak
        rows.append({'label': label, 'pitch_um': pitch, 'n_tiles': cov['n_tiles'],
                     'n_engaged': cov['n_engaged'],
                     'collateral_area_ratio': cov['collateral_area_ratio'],
                     'peak_C': peak, 'peak_drop_K': drop,
                     'K_per_W': drop / args.mr_W,
                     'target_C': temps[target] - 273.15})
        print('{:>10} {:>8} {:>9} {:>7.1f}x {:>10.3f} {:>10.3f}K {:>9.3f}'
              .format(label, cov['n_tiles'], cov['n_engaged'], cov['collateral_area_ratio'],
                      peak, drop, drop / args.mr_W), flush=True)

    out = {'note': 'peak reduction and kelvin-per-watt against cooling-tile pitch, at a FIXED '
                   'removal budget. Collateral cooling helps a degenerate peak and wastes watts '
                   'on an isolated one; this measures which. Linear solves, no leakage feedback.',
           'driver': 'examples/tile_pitch_sweep.py', 'floorplan': os.path.basename(args.flp),
           'target': target, 'target_um': [bw, bh], 'die_W': args.die_W, 'mr_W': args.mr_W,
           'burial_um': args.burial_um, 'cell_um': args.cell_um,
           'base_peak_C': base_peak, 'rows': rows}
    path = os.path.join(args.out_dir, 'tile_pitch.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)

    ok = [r for r in rows if r['peak_drop_K'] is not None]
    if len(ok) >= 2:
        best = max(ok, key=lambda r: r['peak_drop_K'])
        worst = min(ok, key=lambda r: r['peak_drop_K'])
        print('\nbest peak reduction: {} ({:.3f} K); worst: {} ({:.3f} K). Spread {:.3f} K on the '
              'same {:.1f} W.'.format(best['label'], best['peak_drop_K'], worst['label'],
                                      worst['peak_drop_K'],
                                      best['peak_drop_K'] - worst['peak_drop_K'], args.mr_W))
        coarse = [r for r in ok if r['pitch_um'] > 0]
        ideal = [r for r in ok if r['pitch_um'] == 0]
        if coarse and ideal:
            b = max(coarse, key=lambda r: r['peak_drop_K'])
            print('finest buildable pitch here ({} um) reaches {:.0f}% of what per-block '
                  'targeting achieves.'.format(
                      int(min(r['pitch_um'] for r in coarse)),
                      100.0 * b['peak_drop_K'] / ideal[0]['peak_drop_K']))
    print('wrote {}'.format(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
