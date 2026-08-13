#!/usr/bin/env python
"""Report power density at the scale that actually limits performance: the functional unit.

Why this exists
---------------
"Chip power density" is ambiguous by orders of magnitude, and quoting the wrong coarse-graining
leads to badly wrong conclusions about what cooling is needed. The spatial ladder
(Maxwell Labs; see docs/Microrefrigeration_v1.pdf) spans five orders of magnitude::

    rack 0.01  ->  server 0.1  ->  processor 1.0  ->  core 10  ->  hot spot 100   [W/mm^2]

Literature and datasheets overwhelmingly quote the *die-average* value (a 300-800 mm^2 part at
300-700 W reads as ~1 W/mm^2), which makes a chip look benign while the local flux that sets
the thermal limit is one to two orders of magnitude higher. HotGauge's own case study makes
the point concretely: functional units surpass 120 C while units 200 um away stay 30 K cooler.

This script computes, for a given floorplan + power trace, the power density of every
functional unit -- P_block / block_area -- and reports the distribution, the die average, and
where the hottest units sit relative to that ladder and to the microrefrigeration operating
envelope (cooling density H ~1-10 W/mm^2, dT_total <~ 10 K, spatial targeting <~100 um).

The gap between the die-average column and the p99/peak column is the whole argument for
spatially targeted cooling.

Example
-------
    python examples/power_density_profile.py --trace-dir mcpat_runs/7nm/linpack_3.8GHz \\
        --total-power 150
"""
import os
import sys
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.configuration import load_block_powers
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import mcpat_flp_name_map

# Maxwell Labs spatial ladder [W/mm^2]
LADDER = [('rack', 0.01), ('server', 0.1), ('processor', 1.0), ('core', 10.0),
          ('hot spot', 100.0)]
#: Microrefrigeration cooling-density envelope (docs/Microrefrigeration_v1.pdf)
MR_H_MIN, MR_H_MAX = 1.0, 10.0
MR_SPATIAL_UM = 100.0


def ladder_bucket(q):
    """Nearest ladder rung (log distance) for a power density in W/mm^2."""
    if q <= 0:
        return 'n/a'
    return min(LADDER, key=lambda kv: abs(np.log10(q) - np.log10(kv[1])))[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trace-dir', default=None)
    ap.add_argument('--flp-template', default=None)
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--num-cores', type=int, default=8)
    ap.add_argument('--total-power', type=float, default=None,
                    help='scale the trace to this total die power [W] (default: use as-is)')
    ap.add_argument('--top', type=int, default=15, help='how many hottest units to list')
    ap.add_argument('--out-json', default=None)
    args = ap.parse_args()

    args.flp_template = args.flp_template or os.path.join(
        _HERE, 'floorplans', 'outputs',
        'skylake{}nm_7core_3_3D-ICE_template.flp'.format(args.tech_node))
    args.trace_dir = args.trace_dir or os.path.join(
        _HERE, 'ICE_simulation_from_MCPAT', 'traces', 'example_workload',
        '{}nm'.format(args.tech_node))

    flp = Floorplan.from_file(args.flp_template)
    # areas in mm^2, and the smallest lateral dimension (the scale MR must target)
    geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                     'min_dim_um': float(min(e.width, e.height))} for e in flp.elements}
    die_area_mm2 = (flp.width * flp.height) / 1.0e6

    files = load_block_powers(args.trace_dir)
    if not files:
        raise SystemExit('No block_powers_*.json in {}'.format(args.trace_dir))
    with open(files[0]) as f:
        mcpat_powers = {u: float(np.asarray(v, dtype=float).ravel()[0])
                        for u, v in json.load(f).items()}

    raw_total = sum(max(p, 0.0) for p in mcpat_powers.values())
    scale = (args.total_power / raw_total) if args.total_power else 1.0
    total_W = raw_total * scale

    # Bridge McPAT unit names onto floorplan blocks (aggregates map to None and are skipped).
    name_map = mcpat_flp_name_map(include_core_idx=(args.num_cores > 1))
    per_block = {}
    for unit, p in mcpat_powers.items():
        blk = name_map(unit)
        if blk is None or blk not in geom:
            continue
        per_block[blk] = per_block.get(blk, 0.0) + max(p, 0.0) * scale

    rows = []
    for blk, p in per_block.items():
        g = geom[blk]
        rows.append({'block': blk, 'power_W': p, 'area_mm2': g['area_mm2'],
                     'min_dim_um': g['min_dim_um'],
                     'q_W_per_mm2': p / g['area_mm2'] if g['area_mm2'] > 0 else 0.0})
    if not rows:
        raise SystemExit('Name bridge resolved no blocks -- check --num-cores/--flp-template')
    rows.sort(key=lambda r: -r['q_W_per_mm2'])
    q = np.array([r['q_W_per_mm2'] for r in rows])
    mapped_W = sum(r['power_W'] for r in rows)

    print('functional-unit power density profile')
    print('  floorplan   : {}'.format(os.path.basename(args.flp_template)))
    print('  trace       : {}'.format(args.trace_dir))
    print('  die area    : {:.2f} mm^2   blocks resolved: {}'.format(die_area_mm2, len(rows)))
    print('  total power : {:.2f} W (scale x{:.4f}); {:.2f} W lands on mapped blocks'.format(
        total_W, scale, mapped_W))

    print('\n  --- the coarse-graining that matters ---')
    die_avg = total_W / die_area_mm2
    print('  die-average          : {:8.3f} W/mm^2   <- what datasheets/papers usually quote'
          .format(die_avg))
    print('  block median         : {:8.3f} W/mm^2'.format(float(np.median(q))))
    print('  block p90 / p99      : {:8.3f} / {:.3f} W/mm^2'.format(
        float(np.percentile(q, 90)), float(np.percentile(q, 99))))
    print('  block PEAK           : {:8.3f} W/mm^2   <- what sets the thermal limit'.format(
        float(q.max())))
    print('  peak / die-average   : {:8.1f}x'.format(float(q.max()) / die_avg if die_avg else 0))
    print('  ladder rung (peak)   : {}'.format(ladder_bucket(float(q.max()))))

    print('\n  --- top {} units by power density ---'.format(args.top))
    print('  {:<24s} {:>9s} {:>10s} {:>11s} {:>10s} {:>9s}'.format(
        'block', 'P[W]', 'area[mm^2]', 'min_dim[um]', 'q[W/mm^2]', 'MR?'))
    for r in rows[:args.top]:
        # Can microrefrigeration actually service this unit? It must be within the cooling
        # density envelope AND large enough to target at ~100 um spatial resolution.
        within_H = r['q_W_per_mm2'] <= MR_H_MAX
        targetable = r['min_dim_um'] >= MR_SPATIAL_UM
        mr = 'yes' if (within_H and targetable) else ('q>H' if not within_H else '<100um')
        print('  {:<24s} {:>9.4f} {:>10.5f} {:>11.1f} {:>10.3f} {:>9s}'.format(
            r['block'][:24], r['power_W'], r['area_mm2'], r['min_dim_um'],
            r['q_W_per_mm2'], mr))

    print('\n  --- microrefrigeration reach (H {:.0f}-{:.0f} W/mm^2, spatial <~{:.0f} um) ---'
          .format(MR_H_MIN, MR_H_MAX, MR_SPATIAL_UM))
    over_H = [r for r in rows if r['q_W_per_mm2'] > MR_H_MAX]
    small = [r for r in rows if r['min_dim_um'] < MR_SPATIAL_UM]
    print('  units above the MR cooling-density ceiling : {} of {}'.format(len(over_H), len(rows)))
    print('  units narrower than the MR spatial limit   : {} of {} (min dim < {:.0f} um)'.format(
        len(small), len(rows), MR_SPATIAL_UM))
    print('  NOTE: MR clips the temperature EXCESS, not the whole heat load, so "q > H" does'
          '\n  not mean MR is useless there -- it means MR cannot absorb that unit\'s full flux'
          '\n  and must be sized against the excess above the thermal target.')

    if args.out_json:
        with open(args.out_json, 'w') as f:
            json.dump({'die_area_mm2': die_area_mm2, 'total_W': total_W,
                       'die_avg_W_per_mm2': die_avg, 'blocks': rows}, f, indent=2)
        print('\n  written: {}'.format(args.out_json))
    return 0


if __name__ == '__main__':
    sys.exit(main())
