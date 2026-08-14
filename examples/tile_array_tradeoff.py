#!/usr/bin/env python
"""What pixel pitch should a photonic cooling tile array be built at?

The question
------------
A cooling array is a grid of addressable pixels at some pitch P. Pitch is the dominant
fabrication cost driver -- it sets pixel count, optical routing, and the number of independent
control channels -- so the design question is how little pitch you can get away with.

Three effects trade off against each other as P shrinks:

1. **Addressability.** A block narrower than P cannot be selectively targeted. Coarse pitch
   silently excludes exactly the small, high-power-density units that most need cooling.
2. **Dilution.** Targeting a block smaller than a pixel spreads the cooling over the whole
   pixel. The block gets ``area_block / area_pixel`` of the delivered cooling and the rest
   lands on neighbours -- so the laser cost per watt removed *from the block that matters*
   rises by the reciprocal of that fraction.
3. **Pixel count.** Halving the pitch quadruples the pixels. This is the fabrication cost.

Effects 1 and 2 push toward fine pitch, effect 3 pushes coarse. This script quantifies all
three against a real floorplan and a real solved temperature field, so the crossover is a
measured number rather than an argument.

What it does NOT model
----------------------
Pixel *fill factor* (dead space between pixels), the optical power budget per channel, and
control-plane wiring. Those all worsen with fine pitch and would move the answer toward
coarser arrays. Treat the pixel counts here as a lower bound on fabrication difficulty.

Usage
-----
    python examples/tile_array_tradeoff.py --cores 34 --power 116.4 --pitches 100 10 1
"""
import os
import sys
import glob
import json
import math
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace
from HotGauge.configuration import load_block_powers
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (die_block_temps, scale_trace_to_die_power,
                                               replicate_trace_cores, prepare_dice_trace)


def pixels_to_cover(w_um, h_um, pitch_um):
    """Pixels needed to cover one block. A block always costs at least one pixel."""
    return max(1, math.ceil(w_um / pitch_um)) * max(1, math.ceil(h_um / pitch_um))


def analyse(flp_path, temps, powers, pitch_um, target_C):
    flp = Floorplan.from_file(flp_path)
    pixel_area = pitch_um * pitch_um

    tot_p = 0.0
    hot = []       # blocks above target
    addressable = []
    px_hot = 0
    dilution_weighted = []

    for e in flp.elements:
        p = float(np.ravel(powers.get(e.name, [0.0])).sum())
        tot_p += p
        t = temps.get(e.name)
        if t is None:
            continue
        t_c = float(np.ravel(t)[-1]) - 273.15
        if float(np.ravel(t)[-1]) < 200 or t_c <= target_C:
            continue
        area = e.width * e.height
        blk = {'name': e.name, 'p': p, 'area': area,
               'min_dim': min(e.width, e.height), 't_c': t_c}
        hot.append(blk)
        # Addressable if the block is at least one pixel across in its narrow dimension.
        if blk['min_dim'] >= pitch_um:
            addressable.append(blk)
        # Dilution: cooling delivered to a pixel is shared over the pixel's area. A block
        # smaller than a pixel receives only its area fraction of it.
        eff = min(1.0, area / pixel_area)
        dilution_weighted.append((p, eff))
        px_hot += pixels_to_cover(e.width, e.height, pitch_um)

    die_area = sum(e.width * e.height for e in flp.elements)
    px_die = pixels_to_cover(
        max(e.maxx for e in flp.elements) - min(e.minx for e in flp.elements),
        max(e.maxy for e in flp.elements) - min(e.miny for e in flp.elements), pitch_um)

    p_hot = sum(b['p'] for b in hot)
    p_addr = sum(b['p'] for b in addressable)
    # Power-weighted mean delivery efficiency across the hot set.
    wsum = sum(p for p, _ in dilution_weighted)
    eff_mean = (sum(p * e for p, e in dilution_weighted) / wsum) if wsum > 0 else float('nan')

    return {'pitch_um': pitch_um, 'die_mm2': die_area / 1e6,
            'n_hot': len(hot), 'n_addressable': len(addressable),
            'p_hot_W': p_hot, 'p_addressable_W': p_addr,
            'frac_hot_addressable': (len(addressable) / len(hot)) if hot else float('nan'),
            'frac_power_addressable': (p_addr / p_hot) if p_hot > 0 else float('nan'),
            'pixels_hot_only': px_hot, 'pixels_full_die': px_die,
            'delivery_efficiency': eff_mean,
            'laser_overhead': (1.0 / eff_mean) if eff_mean > 0 else float('inf')}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--power', type=float, default=116.4)
    ap.add_argument('--target-C', type=float, default=92.0)
    ap.add_argument('--pitches', type=float, nargs='+', default=[100.0, 10.0, 1.0])
    ap.add_argument('--temps-dir', default=None,
                    help='directory of a solved run; defaults to the 34-core uncooled case')
    args = ap.parse_args()

    flp = os.path.join(args.flp_dir, 'skylake{}_{}core_3_3D-ICE_template.flp'.format(
        args.node, args.cores))
    if not os.path.isfile(flp):
        raise SystemExit('no floorplan at {}'.format(flp))

    td = args.temps_dir or os.path.join(_REPO, 'results', 'mr_compare', '34c_nomr', 'it01')
    cand = sorted(glob.glob(os.path.join(td, 'iter_*')))
    if not cand:
        raise SystemExit('no solved iterations under {} -- pass --temps-dir'.format(td))
    temps = die_block_temps(os.path.join(cand[-1], 'die_elements.temps'))

    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    if args.cores > args.trace_cores:
        base = replicate_trace_cores(base, args.cores, n_src=args.trace_cores)
    tr, _, _ = scale_trace_to_die_power(base, flp, args.tech_node, args.power,
                                        num_cores=args.cores)
    powers = prepare_dice_trace(tr, flp, args.tech_node, num_cores=args.cores).powers

    rows = [analyse(flp, temps, powers, p, args.target_C) for p in args.pitches]

    print('Photonic cooling tile array: pixel pitch tradeoff')
    print('  floorplan : {}-core, {:.1f} mm^2 at {:.1f} W'.format(
        args.cores, rows[0]['die_mm2'], args.power))
    print('  hot set   : {} blocks above {:.0f} C, {:.2f} W'.format(
        rows[0]['n_hot'], args.target_C, rows[0]['p_hot_W']))
    print()
    hdr = ('{:>8s} {:>12s} {:>12s} {:>10s} {:>13s} {:>13s} {:>10s}'.format(
        'pitch', 'hot blocks', 'hot power', 'delivery', 'pixels (hot)', 'pixels (die)',
        'laser x'))
    print(hdr)
    print('-' * len(hdr))
    for r in rows:
        print('{:>6.0f}um {:>7d}/{:<4d} {:>11.1f}% {:>9.1f}% {:>13,d} {:>13,d} {:>9.2f}x'
              .format(r['pitch_um'], r['n_addressable'], r['n_hot'],
                      100 * r['frac_power_addressable'], 100 * r['delivery_efficiency'],
                      r['pixels_hot_only'], r['pixels_full_die'], r['laser_overhead']))
    print()
    print('  hot blocks   addressable / total above target')
    print('  hot power    fraction of above-target power in addressable blocks')
    print('  delivery     power-weighted fraction of pixel cooling that lands on the target')
    print('  pixels(hot)  pixels to tile only the above-target blocks')
    print('  pixels(die)  pixels to tile the whole die')
    print('  laser x      laser overhead from dilution, = 1 / delivery')

    out = os.path.join(os.getcwd(), 'tile_array_tradeoff.json')
    with open(out, 'w') as f:
        json.dump({'cores': args.cores, 'power_W': args.power, 'target_C': args.target_C,
                   'rows': rows}, f, indent=2)
    print('\n  written: {}'.format(out))


if __name__ == '__main__':
    main()
