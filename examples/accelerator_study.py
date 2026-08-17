#!/usr/bin/env python
"""Thermal degeneracy on a REAL accelerator floorplan (Nvidia GA100, measured from die shots).

    python examples/accelerator_study.py --die-power-W 400 --cfm 88

What this answers that nothing before it could
----------------------------------------------
Every accelerator result so far came from a proxy: the McPAT CPU floorplan with each core's power
pushed into its FP units (``--emphasise``). That varies the *power map* and cannot vary the
*geometry*, and the degeneracy findings turned out to be about geometry. A 34-core CPU die has 15
blocks within 10 K of its peak. GA100 has 128 nearly identical compute tiles, and the question is
whether that is a wider plateau of the same kind or a different thermal regime.

The floorplan comes from ``HotGauge.thermal.accelerator_floorplan`` -- 826 mm^2, 367 blocks, areas
measured from the SemiAnalysis/Locuza annotated shots in ``docs/chip_design_lit/die_images``. Same
7 nm node class as the CPU die, so the comparison is iso-node.

The prediction being tested, stated before the run
--------------------------------------------------
With 128 identical tiles the die should be close to *maximally* degenerate: the plateau within
``dt_max`` should hold most of the SMs and clipping one should buy essentially nothing. If that
holds, hotspot MR is structurally wrong for accelerators and only a distributed/die-average policy
has any hope. If it does not -- if the L2 spines and perimeter PHY break the symmetry into a real
hotspot -- then accelerators are a *better* MR target than CPUs, which would be the more
interesting outcome.

There is already a hint of the second: at 400 W the assumed power split makes the memory
controllers and HBM PHY denser than the SM datapath (0.84 and 0.74 against 0.70 W/mm^2). Those sit
on the die perimeter, where the package spreads heat best, so which one wins is genuinely a solve
and not an argument.

What is measured and what is assumed
------------------------------------
Measured: all areas, block counts, arrangement, the 33.4% SRAM fraction inside a tile.
Assumed: the per-class power split (``GA100_POWER_SPLIT``) and the leakage fraction
(``--leak-fraction``). Neither is derivable from a die shot. ``--split-sensitivity`` re-runs the
density accounting across a range of the least certain share, and every JSON this writes carries
``calibrated: false``.

Grid: the die is 8x the CPU footprint, which at the stack template's 50 um cells is ~330k cells
per layer -- near where SuperLU 4.3 gave up on the deep stacks. ``--cell-um`` defaults to 100 for
that reason, and a coarsened peak is not comparable with a 50 um peak.
"""
import os
import sys
import json
import argparse
import logging

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'HotGauge'))

from HotGauge.power import BasicPowerTrace, LeakageModel
from HotGauge.thermal.leakage_feedback import load_calibrated_leakage_model
from HotGauge.thermal import get_stack_template, ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.ice_server import ICESessionCache
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink)
from HotGauge.thermal.stack_models import coarsen_stack_grid
from HotGauge.thermal.accelerator_floorplan import (
    GA100_AREAS, GA100_POWER_SPLIT, ga100_geometry, ga100_consistency, ga100_floorplan,
    ga100_block_powers, block_areas_mm2, power_density_by_class, power_split_sensitivity,
    tier_analysis_by_class)

LOGGER = logging.getLogger('accelerator_study')
T_FLOOR_K = 273.15


def build_trace(powers, leak_fraction):
    """A single-step trace over the floorplan's own block names, plus its leakage split.

    Block names ARE floorplan element names here, so no McPAT name mapping is involved -- which is
    the reason this study can use a floorplan McPAT knows nothing about.

    ``leak_fraction`` is applied uniformly. That is an assumption and a mild one for this purpose:
    what the leakage feedback needs is a reference leakage at ``T_ref`` to scale, and making it
    proportional to block power says "hotter blocks leak more", which is the right first order.
    Making it proportional to *area* instead would be defensible too and would move leakage from
    the datapath toward the SRAM; ``--leak-by-area`` does that, and the two bracket the truth.
    """
    trace = BasicPowerTrace({u: np.array([p]) for u, p in powers.items()}, 1.0)
    leak_ref = {u: p * leak_fraction for u, p in powers.items()}
    return trace, leak_ref


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--die-power-W', type=float, default=400.0,
                    help='total die power [W]; 400 is A100 SXM class')
    ap.add_argument('--density', type=float, default=None,
                    help='set die power from W/mm^2 instead (overrides --die-power-W); use this '
                         'to compare against the CPU density sweep at matched density')
    ap.add_argument('--cell-um', type=float, default=100.0,
                    help='thermal grid cell [um]. 100 by default because the die is 826 mm^2; a '
                         'coarsened peak is NOT comparable with a 50 um peak')
    ap.add_argument('--no-split-sm', action='store_true',
                    help='model each SM as one uniform block instead of datapath + L1 array. '
                         'Hides intra-tile concentration by construction')
    ap.add_argument('--leak-fraction', type=float, default=0.25,
                    help='fraction of each block power that is leakage at T_ref (ASSUMED)')
    ap.add_argument('--leak-by-area', action='store_true',
                    help='distribute reference leakage by AREA rather than by power -- the other '
                         'end of the bracket; leakage then favours the SRAM over the datapath')
    ap.add_argument('--dt-max-K', type=float, default=10.0,
                    help='MR device capability, for the plateau and clip-one figures')
    ap.add_argument('--split-sensitivity', default=None,
                    help='also report density accounting with this class share scaled 0.5-1.5x, '
                         'e.g. hbm_phy')
    # thermal
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, default=None,
                    help='use a fixed thermal resistance [K/W] instead of an air sink')
    ap.add_argument('--ambient-K', type=float, default=308.15)
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--leakage-cal', default='docs/evidence/leakage_calibration.json')
    ap.add_argument('--tol', type=float, default=0.05)
    ap.add_argument('--max-iter', type=int, default=120)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--no-server', action='store_true')
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'accelerator_study'))
    os.makedirs(args.out_dir, exist_ok=True)

    # --- floorplan ------------------------------------------------------------------
    g = ga100_geometry()
    cons = ga100_consistency(g)
    flp_path = os.path.join(args.out_dir, 'ga100.flp')
    # The grid must be passed to the FLOORPLAN as well as the stack: 3D-ICE quantises block edges
    # to it, and unsnapped-but-adjacent blocks come back overlapping and abort the solve.
    flp_path, classes = ga100_floorplan(flp_path, split_sm=not args.no_split_sm, geom=g,
                                        cell_um=args.cell_um)
    areas = block_areas_mm2(flp_path)
    area_mm2 = g['w_die'] * g['h_die']
    area_m2 = area_mm2 / 1e6

    power_W = args.density * area_mm2 if args.density is not None else args.die_power_W
    powers, pmeta = ga100_block_powers(power_W, classes)
    dens = power_density_by_class(classes, powers, areas)

    print('GA100 accelerator floorplan  (measured from die shots -- see '
          'HotGauge.thermal.accelerator_floorplan)')
    print('  die      : {:.2f} x {:.2f} mm = {:.1f} mm^2  (measured {:.0f} mm^2)'.format(
        g['w_die'], g['h_die'], area_mm2, GA100_AREAS['die_mm2']))
    print('  blocks   : {}  ({} SM tiles{}, {} L2, {} HBM PHY, {} MC, {} NVLINK, 1 PCIe/uncore)'
          .format(len(classes), 128, '' if args.no_split_sm else ' split into datapath + L1',
                  96, 6, 4, 4))
    print('  accounts : {:.0%} SM, {:.0%} L2, {:.0%} lumped (PHY, MC, routing, control)'.format(
        cons['sm_frac'], cons['l2_frac'], cons['lumped_frac']))
    print('  power    : {:.1f} W = {:.3f} W/mm^2 die average   [class split ASSUMED]'.format(
        power_W, power_W / area_mm2))
    print('  grid     : {:g} um cells'.format(args.cell_um))
    print()
    print('  {:<10s} {:>4s} {:>8s} {:>8s} {:>9s} {:>9s}'.format(
        'class', 'n', 'W', 'mm^2', 'W/block', 'W/mm^2'))
    for cls, v in sorted(dens.items(), key=lambda kv: -kv[1]['W_per_mm2']):
        print('  {:<10s} {:>4d} {:>8.1f} {:>8.1f} {:>9.3f} {:>9.3f}'.format(
            cls, v['n'], v['W'], v['mm2'], v['W'] / v['n'], v['W_per_mm2']))
    print()

    # --- leakage reference ----------------------------------------------------------
    if args.leak_by_area:
        total_a = sum(areas.get(n, 0.0) for n in powers)
        leak_total = args.leak_fraction * power_W
        leak_ref = {n: leak_total * areas.get(n, 0.0) / total_a for n in powers}
        trace = BasicPowerTrace({u: np.array([p]) for u, p in powers.items()}, 1.0)
        leak_basis = 'by area'
    else:
        trace, leak_ref = build_trace(powers, args.leak_fraction)
        leak_basis = 'by power'

    cal = args.leakage_cal
    if not os.path.isabs(cal):
        cal = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', cal)
    if os.path.isfile(cal):
        leak_model, t_ref = load_calibrated_leakage_model(cal, extrapolate=True)
        leak_src = 'MEASURED McPAT curve + Arrhenius tail'
    else:
        leak_model, t_ref = LeakageModel.exponential(15.0), 330.0
        leak_src = 'assumed exponential'
    print('  leakage  : {:.0%} of block power at T_ref = {:.1f} K, distributed {} [{}]'.format(
        args.leak_fraction, t_ref, leak_basis, leak_src))

    # --- solve ----------------------------------------------------------------------
    sink = (ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K)
            if args.r_th is not None
            else BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K))
    stack = render_stack_with_sink(get_stack_template(args.stack), sink,
                                  os.path.join(args.out_dir, 'ga100.stk'))
    coarsen_stack_grid(stack, args.cell_um)
    solver = ICEThermalSolver(stack, flp_path, args.tech_node,
                              run_base_dir=os.path.join(args.out_dir, 'solve'),
                              initial_temp=args.ambient_K, num_cores=1,
                              single_thread=True, mode='steady',
                              session_cache=None if args.no_server else ICESessionCache(),
                              # The trace's keys ARE this floorplan's element names, so the
                              # McPAT rename/L3-split/IMC path must be skipped -- there are no
                              # cores here to split an L3 across.
                              already_dice_named=True)

    print('  cooling  : {}'.format('R_th {:g} K/W'.format(args.r_th) if args.r_th is not None
                                   else '{:g} CFM baffled fin'.format(args.cfm)))
    print('\n  solving the leakage fixed point over {} blocks ...'.format(len(classes)))
    res = run_leakage_feedback(trace, leak_ref, solver, model=leak_model, T_ref=t_ref,
                               num_cores=1, tol_K=args.tol, max_iter=args.max_iter,
                               relax=args.relax, t_floor_K=T_FLOOR_K, bridge_aggregates=True,
                               verify=True)

    if res.get('diverged'):
        print('\n  NO STEADY STATE: thermal runaway at {:.3f} W/mm^2. That is a result, not a '
              'failure -- report it as one.'.format(power_W / area_mm2))
    if res.get('unconverged'):
        print('\n  WARNING: failed damping verification (worst spread {} K). Not quotable.'
              .format(res.get('verify_spread_K')))

    out = {'floorplan': 'GA100 (measured die shots)', 'calibrated': False,
           'die_mm2': area_mm2, 'n_blocks': len(classes),
           'die_power_W': power_W, 'density_W_per_mm2': power_W / area_mm2,
           'cell_um': args.cell_um, 'split_sm': not args.no_split_sm,
           'leak_fraction': args.leak_fraction, 'leak_basis': leak_basis,
           'cfm': args.cfm, 'r_th': args.r_th, 'dt_max_K': args.dt_max_K,
           'power_split': GA100_POWER_SPLIT, 'power_split_is_assumed': True,
           'geometry': g, 'consistency': cons,
           'density_by_class': dens,
           'diverged': bool(res.get('diverged')),
           'unconverged': bool(res.get('unconverged')),
           'verify_spread_K': res.get('verify_spread_K'),
           'iterations': res.get('iterations')}

    temps = res.get('temp_trace')
    if temps and not res.get('diverged'):
        # Same filter thermal_tiers.py uses: take the LAST iterate, drop blocks the solver never
        # populated (they sit at the floor) and the '__' bookkeeping keys.
        temps_C = {b: float(np.ravel(v)[-1]) - 273.15 for b, v in temps.items()
                   if float(np.ravel(v)[-1]) > T_FLOOR_K and not b.startswith('__')}
        t = tier_analysis_by_class(temps_C, classes, args.dt_max_K)
        out['tiers'] = {k: v for k, v in t.items() if k != 'rows'}
        out['clip_curve'] = t['rows']

        print('\n  peak {:.2f} C on {} ({})'.format(t['peak_C'], t['peak_block'],
                                                    t['peak_class']))
        print('\n  {:<10s} {:>4s} {:>9s} {:>9s} {:>9s} {:>10s}'.format(
            'class', 'n', 'max C', 'min C', 'spread K', 'in plateau'))
        for cls, v in sorted(t['by_class'].items(), key=lambda kv: -kv[1]['max_C']):
            print('  {:<10s} {:>4d} {:>9.2f} {:>9.2f} {:>9.2f} {:>10d}'.format(
                cls, v['n'], v['max_C'], v['min_C'], v['spread_K'], v['n_in_plateau']))

        print('\n  blocks within {:.0f} K of the peak      : {}'.format(
            args.dt_max_K, t['plateau_within_dt_max']))
        print('  blocks to clip for the full {:.0f} K    : {}'.format(
            args.dt_max_K, t['n_needed_for_full_dt_max']))
        print('  clipping ONE block gains            : {:.3f} K  ({:.1f}% of the device '
              'capability)'.format(t['clip_one_gain_K'],
                                   100.0 * t['clip_one_gain_K'] / args.dt_max_K))
        print('\n  READ: a wide plateau and a near-zero clip-one gain means hotspot MR cannot '
              'move this die\n        and only a distributed policy could. A narrow plateau '
              'would mean the opposite.')

    if args.split_sensitivity:
        s = power_split_sensitivity(power_W, classes, areas, vary=args.split_sensitivity)
        out['split_sensitivity'] = {'vary': args.split_sensitivity,
                                    'factors': {str(k): v for k, v in s.items()}}
        print('\n  sensitivity to the assumed {!r} share (W/mm^2 by class):'.format(
            args.split_sensitivity))
        cls_list = sorted(dens, key=lambda c: -dens[c]['W_per_mm2'])
        print('    {:<8s} '.format('factor') + ' '.join('{:>10s}'.format(c) for c in cls_list))
        for fac in sorted(s):
            print('    {:<8.2f} '.format(fac)
                  + ' '.join('{:>10.3f}'.format(s[fac][c]['W_per_mm2']) for c in cls_list))

    path = os.path.join(args.out_dir, 'accelerator_study.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print('\n  wrote {}'.format(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
