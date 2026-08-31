#!/usr/bin/env python
"""Can the die hold two temperatures at once, and how hot is the extractor really?

    python examples/thermal_zone_probe.py --mode extractor
    python examples/thermal_zone_probe.py --mode zones

Two experiments that Chapter 10.8 of ``docs/Photonic_Cooling_Devices___v9.pdf`` makes load-bearing
and that nothing in this repository had measured.

``--mode extractor``  (the prerequisite)
    Every exergy number in the power-recovery framing uses a Carnot factor ``phi = 1 - T_0/T_h``,
    and ``T_h`` is the temperature of the reservoir the heat is lifted **from** -- the anti-Stokes
    extractor in the cold plate, not the silicon junction. Those differ by the conduction drop up
    through the die, which grows with burial depth and power density. Using the junction
    temperature overstates recoverable work. This measures the drop, sweeping burial and pitch,
    with the array present and drawing **zero** power so the only thing being measured is the
    passive path.

``--mode zones``  (the blocking test)
    Section 10.8 proposes hot dynamic-dominated compute beside cold static-dominated SRAM. Whether
    a die can *hold* such a gradient is a question about lateral conduction, and the honest answer
    may be no. Rather than demand a gradient and report whether it was met, this drives an
    escalating removal budget over the cold zone only and records the **achieved** gradient at
    each step -- which gives the whole saturation curve rather than one pass/fail point, and shows
    directly where the gradient stops responding to more cooling.

    Cold zone is L2 and L3 (measured at 80.3% and 97.7% static on the project trace); everything
    else is the hot zone and receives **no cooling at all**, which is the policy inversion 10.8
    asks for.

An analytic prediction exists to check this against
----------------------------------------------------
``HotGauge/thermal/thermal_zones.py`` says a monolithic die needs 3000-6300x less boundary
conductance than silicon provides, so the gradient should saturate early and hard. That was a
closed-form argument; this is a 3D-ICE solve of the same question by a different route. Agreement
would be worth more than either alone; disagreement would mean one of them is wrong and is worth
finding out before anything is pitched on it.
"""
import os
import sys
import json
import time
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace
from HotGauge.thermal import ICEThermalSolver
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.die_stack import StackSpec, write_stack
from HotGauge.thermal.mr_array import (ArrayWiring, blocks_from_floorplan,
                                       project_plan_to_tiles, tile_powers_for_stack)
from HotGauge.thermal.utils import K_to_C
from HotGauge.thermal import exergy as EX

#: Below this a reported temperature is unsolved stack padding, not a die element.
T_FLOOR_K = 200.0

#: The array die reports no temperatures by default -- ``ICESteadySim.DIE_TFLP_OUTPUT`` names
#: ``PROCESSOR_DIE`` only, so a solve returns the silicon and nothing else. Measuring the
#: extractor's temperature requires asking for it explicitly, and without this line the whole
#: point of ``--mode extractor`` silently returns nothing. ``MR_ARRAY`` is the stack element
#: ``die_stack.write_stack`` emits for the cooling array.
MR_TFLP_OUTPUT = 'Tflp (MR_ARRAY, "mr_elements.temps", average, final ) ;'

#: Blocks whose power is static-dominated on the project trace, so they are the cold-zone
#: candidates. Measured, not assumed: L2 is 80.3% static and L3 97.7%, against 0.3% for the FPU.
COLD_PREFIXES = ('L2', 'L3')


def _is_cold(name):
    return any(name.startswith(p) for p in COLD_PREFIXES)


def _die_blocks(temps):
    """Solved die elements only, dropping stack padding and the array's own tiles."""
    return {k: float(np.ravel(v)[-1]) for k, v in temps.items()
            if float(np.ravel(v)[-1]) > T_FLOOR_K and not k.startswith('mr_')}


def _tile_temps(temps, tiles):
    names = {t['name'] for t in tiles}
    return {k: float(np.ravel(v)[-1]) for k, v in temps.items()
            if k in names and float(np.ravel(v)[-1]) > T_FLOOR_K}


def _mean(d):
    return (sum(d.values()) / len(d)) if d else float('nan')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mode', choices=('extractor', 'zones'), required=True)
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--flp', default=os.path.join(_HERE, 'floorplans', 'outputs',
                                                  'skylake7nm_34core_3_3D-ICE_template.flp'))
    ap.add_argument('--die-W', type=float, default=60.7,
                    help='die power; the 34-core baseline at 0.60 W/mm^2 by default')
    ap.add_argument('--densities', type=float, nargs='+', default=None,
                    help='extractor mode: sweep W/mm^2 instead of using --die-W. The drop from '
                         'junction to extractor scales with power density, and it is the density '
                         'that decides whether phi may be read off the junction at all.')
    ap.add_argument('--depths', type=float, nargs='+', default=[50.0, 200.0])
    ap.add_argument('--pitches', type=float, nargs='+', default=[100.0, 500.0, 2000.0])
    ap.add_argument('--budgets-W', type=float, nargs='+',
                    default=[0.0, 2.0, 5.0, 10.0, 20.0, 40.0],
                    help='zones mode: removal applied over the COLD zone only')
    ap.add_argument('--cell-um', type=float, default=50.0)
    ap.add_argument('--mr-material', default='GAAS')
    ap.add_argument('--mr-um', type=float, default=30.0)
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--ambient-K', type=float, default=300.0)
    ap.add_argument('--T0-K', type=float, default=EX.BOOK_T0_K)
    ap.add_argument('--below-um', type=float, default=20.0)
    args = ap.parse_args()

    args.out_dir = os.path.abspath(args.out_dir or
                                   os.path.join(_REPO, 'results', 'zone_' + args.mode))
    args.flp = os.path.abspath(args.flp)
    os.makedirs(args.out_dir, exist_ok=True)

    flp_obj = Floorplan.from_file(args.flp, frmt='3D-ICE')
    blocks = blocks_from_floorplan(flp_obj)
    area = {n: (b[2] * b[3]) / 1.0e6 for n, b in blocks.items()}
    total_area = sum(area.values())
    # Uniform density, so any gradient that appears is geometry and cooling rather than an
    # activity pattern assumed into the input.
    die_powers = {n: args.die_W * area[n] / total_area for n in blocks}
    trace = BasicPowerTrace({n: np.array([p]) for n, p in die_powers.items()}, 1.0)

    cold = sorted(n for n in blocks if _is_cold(n))
    hot = sorted(n for n in blocks if not _is_cold(n))
    print('{} mode: {} blocks, {:.1f} mm^2, {:.1f} W uniform'
          .format(args.mode, len(blocks), total_area, args.die_W))
    print('  cold zone (L2/L3): {} blocks, {:.1f} mm^2 = {:.1f}% of die'
          .format(len(cold), sum(area[n] for n in cold),
                  100 * sum(area[n] for n in cold) / total_area))
    print()

    rows = []
    for depth in args.depths:
        for pitch in args.pitches:
            tag = 'd{:.0f}_p{:.0f}'.format(depth, pitch)
            spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                             die_um=depth + 20.0 + args.below_um, source_depth_um=depth,
                             source_um=20.0, mr_material=args.mr_material, mr_um=args.mr_um,
                             cell_um=args.cell_um)
            stack = write_stack(spec, os.path.join(args.out_dir, tag + '.stk'))
            wiring = ArrayWiring(args.flp, os.path.join(args.out_dir, tag),
                                 pitch_um=pitch, cell_um=args.cell_um)

            if args.mode == 'extractor':
                dens_list = args.densities or [args.die_W / total_area]
                ladder = [('d', d) for d in dens_list]
            else:
                ladder = [('b', b) for b in args.budgets_W]
            for bi, (kind, val) in enumerate(ladder):
                if kind == 'd':
                    die_W = val * total_area
                    trace = BasicPowerTrace(
                        {n: np.array([die_W * area[n] / total_area]) for n in blocks}, 1.0)
                    budget = 0.0
                else:
                    die_W, budget = args.die_W, val
                # Cold-zone-only plan, split across cold blocks by area so the removal density is
                # uniform over the zone rather than concentrated on whichever block is largest.
                cold_area = sum(area[n] for n in cold) or 1.0
                plan = {n: budget * area[n] / cold_area for n in cold} if budget > 0 else {}
                tile_plan = project_plan_to_tiles(plan, wiring.blocks, wiring.tiles,
                                                  strict=False) if plan else {}
                wiring.set_mr_powers(tile_powers_for_stack(tile_plan, wiring.tiles))

                t0 = time.time()
                solver = ICEThermalSolver(
                    stack, args.flp, args.tech_node,
                    run_base_dir=os.path.join(args.out_dir, tag, 'b{:02d}'.format(bi)),
                    initial_temp=args.ambient_K, num_cores=1, single_thread=True,
                    mode='steady', already_dice_named=True,
                    extra_die_outputs=[MR_TFLP_OUTPUT], **wiring.solver_kwargs())
                temps = solver(trace)
                dt = time.time() - t0

                die = _die_blocks(temps)
                tt = _tile_temps(temps, wiring.tiles)
                cold_T = {n: die[n] for n in cold if n in die}
                hot_T = {n: die[n] for n in hot if n in die}
                j_mean, x_mean = _mean(die), _mean(tt)
                row = {
                    'depth_um': depth, 'pitch_um': pitch, 'budget_W': budget,
                    'die_W': die_W, 'density_W_mm2': die_W / total_area,
                    'n_tiles': len(wiring.tiles),
                    'junction_mean_K': j_mean, 'junction_peak_K': max(die.values()),
                    'extractor_mean_K': x_mean,
                    'extractor_peak_K': max(tt.values()) if tt else float('nan'),
                    'junction_minus_extractor_K': j_mean - x_mean,
                    'cold_mean_K': _mean(cold_T), 'hot_mean_K': _mean(hot_T),
                    'achieved_gradient_K': _mean(hot_T) - _mean(cold_T),
                    'phi_at_junction': EX.carnot_factor(j_mean, args.T0_K),
                    'phi_at_extractor': EX.carnot_factor(x_mean, args.T0_K) if tt else None,
                    'solve_s': dt,
                }
                if row['phi_at_extractor'] is not None and row['phi_at_junction'] > 0:
                    row['phi_overstatement'] = (row['phi_at_junction'] /
                                                row['phi_at_extractor']) \
                        if row['phi_at_extractor'] > 0 else float('inf')
                rows.append(row)
                if args.mode == 'extractor' and not tt:
                    raise SystemExit(
                        'the array die returned no temperatures, so the extractor drop cannot be '
                        'measured. The stack must carry an output line for MR_ARRAY -- see '
                        'MR_TFLP_OUTPUT. Reporting a junction-only result here would silently '
                        'answer a different question.')
                if args.mode == 'extractor':
                    print('  d={:>4.0f} p={:>5.0f}  {:5.2f} W/mm2  junction {:7.2f} C  '
                          'extractor {:7.2f} C  drop {:7.2f} K  phi {:.4f} -> {:.4f}  ({:.0f}s)'
                          .format(depth, pitch, row['density_W_mm2'], K_to_C(j_mean),
                                  K_to_C(x_mean), j_mean - x_mean, row['phi_at_junction'],
                                  row['phi_at_extractor'], dt))
                else:
                    print('  d={:>4.0f} p={:>5.0f} budget {:>5.1f} W  cold {:6.2f} C  hot {:6.2f} C'
                          '  gradient {:6.2f} K  ({:.0f}s)'
                          .format(depth, pitch, budget, K_to_C(_mean(cold_T)),
                                  K_to_C(_mean(hot_T)), row['achieved_gradient_K'], dt))

    out = os.path.join(args.out_dir, 'results.json')
    with open(out, 'w') as f:
        json.dump({'mode': args.mode, 'flp': args.flp, 'die_W': args.die_W,
                   'T0_K': args.T0_K, 'cold_blocks': len(cold), 'hot_blocks': len(hot),
                   'cold_area_mm2': sum(area[n] for n in cold), 'die_area_mm2': total_area,
                   'rows': rows}, f, indent=1)
    print('\nwrote {}'.format(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
