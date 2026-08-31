#!/usr/bin/env python
"""P0.2 acceptance: does the burial depth stop being inert once the PLANNER puts the cooling
where the hardware puts it?

What this is for
----------------
``examples/mr_placement_probe.py`` settled the physics by driving 3D-ICE directly: with the
removal in the die's own source layer the burial depth is inert *by construction*, and with it in
the tiles above the silicon, thinning 360 -> 20 um improves what a fixed 3 W buys by **67 %**
(``docs/evidence/mr_placement_burial_depth.json``).

That probe writes its own ``.stk``, its own floorplans and shells out to the Emulator. None of the
production path is exercised. This driver asks the same question through
:func:`~HotGauge.thermal.microrefrigeration.run_mr_clipping` --
:class:`~HotGauge.thermal.microrefrigeration.CoolingApplication`,
:class:`~HotGauge.thermal.mr_array.ArrayWiring`, ``ICEThermalSolver``, the session cache -- because
that is the path every study result now comes through, and a planner that computes a beautiful
plan and lands it in the wrong layer produces plausible temperatures rather than an error.

It is the acceptance check in ``docs/EXECUTION_PLAN.md`` P0.2, and it is deliberately the harder
one: the watts-conserved assertion can pass on a plan that never reaches the silicon.

Method, and why it is shaped like this
--------------------------------------
Three arms at each burial depth, all on the **same stack** -- the array die is present and its
tiles exist in every arm, so the only thing that moves is *where the 3 W goes*:

  none     tiles at 0 W, no plan. The baseline the other two are measured against.
  source   the plan applied through ``CoolingApplication(tiles=None)`` -- subtracted from the
           processor trace, i.e. the legacy in-source-layer placement, with the (inert) array
           still bonded above so the stack resistance is identical.
  pixels   the same plan projected onto the tiles -- the device.

The plan is sized by ``run_mr_clipping`` in both cooled arms, with ``max_total_W`` binding, so the
comparison is genuinely "what a FIXED 3 W buys". The target is set per depth at
``(no-MR peak - --target-margin-K)`` rather than at an absolute temperature: a thinner die is a
cooler die, so a fixed target would ask a different question at each depth and the budget would
stop binding at the thin end. The script prints the watts each plan actually spent and refuses to
report a swing if they disagree -- an unequal budget is a confound, not a result.

Solves are **linear, no leakage feedback**, exactly as in ``mr_placement_probe``: the point is to
let geometry be the only thing moving.

Usage
-----
    python examples/burial_depth_planner_probe.py --out-dir results/burial_planner
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
from HotGauge.thermal.mr_array import (ArrayWiring, blocks_from_floorplan, coverage_report,
                                       DEFAULT_PITCH_UM)
from HotGauge.thermal.microrefrigeration import MRParams, run_mr_clipping
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0

#: Silicon left BELOW the active layer, held constant so the sweep isolates the path up. Same
#: value as mr_placement_probe.BELOW_UM -- this probe has to be the same experiment.
BELOW_UM = 20.0

#: The measured result this reproduces. mr_placement_probe, 360 -> 20 um, 3 W on the hottest
#: block: |gain| goes 4.066 K -> 6.800 K in the pixels, and 8.566 -> 9.254 K in the source layer.
REFERENCE = {'evidence': 'docs/evidence/mr_placement_burial_depth.json',
             'target': 'L3_4', 'reduction': 'block maximum',
             'pixels_ratio': 6.800 / 4.066, 'source_ratio': 9.254 / 8.566}

#: Why the PERCENTAGE here will not equal the reference percentage, and why that is not a
#: failure. Both are real measurements of different quantities, and the difference is worth
#: knowing about because the 67 % is quoted as a design constant in CODESIGN_PLAN.md s1.
#:
#: 1. **Block maximum against block average.** mr_placement_probe writes its own .stk with
#:    ``Tflp (PROCESSOR_DIE, ..., maximum, final)``. The production path is
#:    ``ICE.DIE_TFLP_OUTPUT``, which is ``average`` -- so every catalogue result, and every
#:    number this driver prints, is a block MEAN. On the same block at the same burial depth the
#:    two differ by ~2.6 K (81.24 C maximum against 78.62 C average), and they respond to
#:    thinning differently: a block's hottest cell is set largely by its own local flux, while
#:    its mean responds to the whole block's path to the coolant.
#: 2. **A different block.** run_mr_clipping ranks by the temperature the production path
#:    reports, and on that reduction the hottest block is L2_4, not L3_4. Running the direct
#:    probe on L2_4 with maxima gives +11.0 %, against +67.2 % on L3_4 -- so block choice alone
#:    moves the headline by 6x.
#:
#: The claim that survives all three measurements is the one the acceptance check is for: with
#: the array above the silicon the burial depth is a strong lever, and with the cooling in the
#: source layer it is not. The MAGNITUDE is a property of the block and the reduction, and
#: should be quoted with both stated.
COMPARABILITY = (
    'the reference is a block MAXIMUM on L3_4; the production path reports block AVERAGES and '
    'ranks L2_4 hottest. Both differences move the magnitude several-fold, so the percentages '
    'are not expected to match -- the separation between the two placements is what is being '
    'tested.')


def die_peak_block(temps):
    """``(name, K)`` of the hottest real element. Layers below T_FLOOR_K are unsolved padding."""
    best, best_T = None, -np.inf
    for k, v in temps.items():
        t = float(np.ravel(v)[-1])
        if t > T_FLOOR_K and t > best_T:
            best, best_T = k, t
    return best, best_T


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--recovery-at-junction', action='store_true',
                    help='bound the LPC recovery by the Carnot factor of the junction the heat is '
                         'lifted from (v91 eq. 1.14-1.16). Without it the ledger uses the '
                         'phi -> 1 limit, which overstates recovery at every finite temperature')
    ap.add_argument('--T0-K', type=float, default=295.0,
                    help='sink temperature for the Carnot factor, with --recovery-at-junction')
    ap.add_argument('--out-dir', default=os.path.join(_REPO, 'results', 'burial_planner'))
    ap.add_argument('--flp', default=os.path.join(_HERE, 'floorplans', 'outputs',
                                                  'skylake10nm_7core_0_3D-ICE_template.flp'),
                    help='same floorplan as mr_placement_probe -- this must be the same '
                         'experiment or it reproduces nothing')
    ap.add_argument('--depths', type=float, nargs='+', default=[360.0, 100.0, 20.0])
    ap.add_argument('--die-W', type=float, default=100.0,
                    help='spread uniformly over every block, so any hotspot is geometry')
    ap.add_argument('--mr-W', type=float, default=3.0, help='the fixed budget the plan may spend')
    ap.add_argument('--pitch-um', type=float, default=DEFAULT_PITCH_UM)
    ap.add_argument('--cell-um', type=float, default=100.0)
    ap.add_argument('--mr-material', default='GAAS')
    ap.add_argument('--mr-um', type=float, default=30.0)
    ap.add_argument('--tech-node', type=int, default=10)
    ap.add_argument('--ambient-K', type=float, default=300.0)
    ap.add_argument('--target-margin-K', type=float, default=20.0,
                    help='MR target is set this far BELOW each depth\'s own uncooled peak, so '
                         'the budget binds identically at every depth')
    ap.add_argument('--mr-iter', type=int, default=8)
    ap.add_argument('--budget-tol-W', type=float, default=1e-3,
                    help='how closely the arms must agree on watts spent before a swing is '
                         'reported at all')
    args = ap.parse_args()

    # Absolute: 3D-ICE runs inside a multiprocessing worker with a different cwd.
    args.out_dir = os.path.abspath(args.out_dir)
    args.flp = os.path.abspath(args.flp)
    os.makedirs(args.out_dir, exist_ok=True)
    flp_obj = Floorplan.from_file(args.flp, frmt='3D-ICE')
    blocks = blocks_from_floorplan(flp_obj)
    geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                     'min_dim_um': float(min(e.width, e.height))} for e in flp_obj.elements}
    die_powers = {n: args.die_W / len(blocks) for n in blocks}
    trace = BasicPowerTrace({n: np.array([p]) for n, p in die_powers.items()}, 1.0)
    # The floorplan's own element names -- no McPAT rename in this experiment.
    name_map = (lambda u: u)

    print('burial depth THROUGH THE PLANNER  ({} blocks, {:.0f} W uniform)'
          .format(len(blocks), args.die_W))
    print('  reproducing {}'.format(REFERENCE['evidence']))
    print('  budget {:.3f} W, target = uncooled peak - {:.0f} K, pitch {:.0f} um, cell {:.0f} um'
          .format(args.mr_W, args.target_margin_K, args.pitch_um, args.cell_um))
    print()

    rows = []
    for depth in args.depths:
        tag = 'd{:.0f}'.format(depth)
        spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                         die_um=depth + 20.0 + BELOW_UM, source_depth_um=depth, source_um=20.0,
                         mr_material=args.mr_material, mr_um=args.mr_um, cell_um=args.cell_um)
        stack = write_stack(spec, os.path.join(args.out_dir, tag + '.stk'))
        # One wiring per depth. The tile GRID does not depend on the depth -- it is the same
        # die footprint -- but the PLAN does, and the wiring is what carries it between solves,
        # so a fresh one per depth keeps the depths from leaking into each other.
        #
        # ArrayWiring directly rather than wiring_for_stack: the stack is built two lines above
        # by this script and is known to carry the array, so there is nothing to derive.
        wiring = ArrayWiring(args.flp, os.path.join(args.out_dir, tag),
                             pitch_um=args.pitch_um, cell_um=args.cell_um)

        counter = {'n': 0}

        def make_solve_fn(sub, w):
            """A callable that builds a FRESH solver on every call.

            This is the one thing ArrayWiring's docstring insists on and it is worth restating
            where it bites: ``solver_kwargs()`` snapshots the CURRENT tile powers, and the solver
            renders them into the array's floorplan at construction. Build the solver once and
            hand it to run_mr_clipping and every iteration re-solves the plan the wiring held
            *before the planner ever ran* -- all zeros. The run then completes, conserves its
            watts, reports 3.000 W removed, and the die does not move by a millikelvin. No error,
            no warning; just a cooler that appears to do nothing. That is what this probe caught
            on its first pass, and it is the exact failure the array placement exists to make
            visible, so it is documented rather than quietly fixed.

            Passed in EVERY arm, including 'source': the array die is bonded above the silicon
            whether or not it is doing anything, and leaving it out of the legacy arm would
            compare two different stacks and call the difference a placement effect.
            """
            def solve(tr):
                counter['n'] += 1
                solver = ICEThermalSolver(
                    stack, args.flp, args.tech_node,
                    run_base_dir=os.path.join(args.out_dir, tag, sub,
                                              'it{:03d}'.format(counter['n'])),
                    initial_temp=args.ambient_K, num_cores=1,
                    single_thread=True, mode='steady',
                    already_dice_named=True,
                    **w.solver_kwargs())
                return solver(tr)
            return solve

        # --- arm 'none': the array present, at 0 W. --------------------------------------
        wiring.set_mr_powers({t['name']: 0.0 for t in wiring.tiles})
        t0 = time.time()
        base_temps = make_solve_fn('none', wiring)(trace)
        peak_block, peak_K = die_peak_block(base_temps)
        target_K = peak_K - args.target_margin_K
        print('  {:>4.0f} um: uncooled peak {:.3f} C at {} ({:.1f} s) -> MR target {:.3f} C'
              .format(depth, K_to_C(peak_K), peak_block, time.time() - t0, K_to_C(target_K)))

        mr = MRParams(target_K=target_K, max_total_W=args.mr_W,
                      # Generous, so the BUDGET is what binds and not a per-block cap -- the
                      # measurement is "what a fixed 3 W buys", and a dt_max or h_max clamp
                      # would make it "what the device can lift", which is a different question.
                      h_max=1.0e6, dt_max_K=1.0e6, spot_policy='ideal', spot_min_um=0.0)

        arms = {}
        for where in ('source', 'pixels'):
            # The array stays in the stack for both. Only the PLANNER's placement changes.
            wiring.set_mr_powers({t['name']: 0.0 for t in wiring.tiles})
            planner_kw = wiring.planner_kwargs() if where == 'pixels' else {}
            t0 = time.time()
            res = run_mr_clipping(trace, make_solve_fn(where, wiring), geom, mr, name_map,
                                  max_iter=args.mr_iter, tol_K=0.5, relax=0.7, **planner_kw,
                # `[!]` Carnot-bound the LPC recovery at the junction the
                # heat is lifted from (v91 eq. 1.14-1.16). Without it the
                # ledger uses the phi -> 1 limit and can report a loop that
                # generates net power, which the second law forbids.
                recovery_at_junction=args.recovery_at_junction,
                T_0_K=args.T0_K)
            t_block = float(np.ravel(res['temp_trace'][peak_block])[-1])
            spent = sum(v for v in res['plan'].values() if v and v > 0)
            arms[where] = {'peak_block_C': K_to_C(t_block),
                           'gain_K': K_to_C(t_block) - K_to_C(peak_K),
                           'W_spent': spent, 'placement': res['placement'],
                           'converged': bool(res['converged']),
                           'n_blocks': len([v for v in res['plan'].values() if v and v > 0]),
                           'seconds': time.time() - t0}
            a = arms[where]
            print('          {:<7s} placement={:<15s} {:.4f} W over {} block(s) '
                  '-> {} {:+.4f} K   ({:.1f} s)'
                  .format(where, a['placement'], a['W_spent'], a['n_blocks'], peak_block,
                          a['gain_K'], a['seconds']))

        row = {'burial_um': depth, 'peak_block': peak_block, 'no_mr_C': K_to_C(peak_K),
               'target_C': K_to_C(target_K),
               'source_C': arms['source']['peak_block_C'],
               'pixels_C': arms['pixels']['peak_block_C'],
               'gain_source_K': arms['source']['gain_K'],
               'gain_pixels_K': arms['pixels']['gain_K'],
               'W_source': arms['source']['W_spent'], 'W_pixels': arms['pixels']['W_spent'],
               'placement_source': arms['source']['placement'],
               'placement_pixels': arms['pixels']['placement'],
               'n_tiles': len(wiring.tiles)}
        rows.append(row)

    # --- the verdict ------------------------------------------------------------------
    print()
    deep, thin = rows[0], rows[-1]
    budgets = [r[k] for r in rows for k in ('W_source', 'W_pixels')]
    equal_budget = (max(budgets) - min(budgets)) <= args.budget_tol_W
    out = {'note': 'P0.2 acceptance: the burial depth measured THROUGH run_mr_clipping, so the '
                   'production path (CoolingApplication, ArrayWiring, ICEThermalSolver) is what '
                   'is being tested rather than a hand-built .stk.',
           'driver': 'examples/burial_depth_planner_probe.py',
           'reference': REFERENCE, 'comparability': COMPARABILITY,
           'rows': rows, 'equal_budget': equal_budget,
           'budget_spread_W': max(budgets) - min(budgets),
           'die_W': args.die_W, 'mr_W': args.mr_W, 'pitch_um': args.pitch_um,
           'cell_um': args.cell_um, 'target_margin_K': args.target_margin_K}

    if not equal_budget:
        print('  NOT REPORTING A SWING: the arms spent different budgets ({:.4g} W apart, '
              'tolerance {:.4g}). An unequal budget is a confound -- lower --target-margin-K '
              'until the cap binds everywhere.'.format(out['budget_spread_W'], args.budget_tol_W))
        out['verdict'] = 'inconclusive: unequal budgets'
    else:
        for where in ('source', 'pixels'):
            g_deep = abs(deep['gain_{}_K'.format(where)])
            g_thin = abs(thin['gain_{}_K'.format(where)])
            ratio = (g_thin / g_deep) if g_deep else float('nan')
            out['{}_ratio'.format(where)] = ratio
            out['{}_swing_pct'.format(where)] = 100.0 * (ratio - 1.0)
            print('  {:<7s}: {:.0f} -> {:.0f} um moves what {:.3g} W buys from {:.4f} K to '
                  '{:.4f} K  ({:+.1f}%)'
                  .format(where, deep['burial_um'], thin['burial_um'], args.mr_W,
                          g_deep, g_thin, 100.0 * (ratio - 1.0)))
        print()
        print('  reference (mr_placement_probe, direct 3D-ICE, {} on {}): pixels {:+.1f}%, '
              'source {:+.1f}%'
              .format(REFERENCE['reduction'], REFERENCE['target'],
                      100.0 * (REFERENCE['pixels_ratio'] - 1.0),
                      100.0 * (REFERENCE['source_ratio'] - 1.0)))
        print('  NOT directly comparable, and deliberately reported anyway: {}'
              .format(COMPARABILITY))
        # The claim is qualitative and it is the one that matters: through the planner, the
        # ARRAY placement is strongly burial-sensitive and the source placement is not. The
        # absolute percentages need not match the direct probe -- run_mr_clipping ranks and
        # spreads the budget itself rather than forcing all 3 W onto one block -- but the
        # SEPARATION must survive, because that separation is the whole design argument.
        # The test is the SEPARATION, not the magnitude -- see COMPARABILITY. The source arm
        # may come out slightly negative (a thinner die is a cooler die, so the same 3 W is a
        # smaller fraction of a smaller excess), which is still "inert" for this purpose; what
        # must not happen is the two placements responding alike.
        out['verdict'] = ('burial depth is live through the planner'
                          if out['pixels_swing_pct'] > 3.0 * abs(out['source_swing_pct'])
                          else 'FAILED: the planner has not made burial depth live')
        print('  verdict: {}'.format(out['verdict']))

    path = os.path.join(args.out_dir, 'summary.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print('\n  written: {}'.format(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
