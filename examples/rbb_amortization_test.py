#!/usr/bin/env python
"""Why RBB gates the high-density programme, and what fixing it would mean.

    python examples/rbb_amortization_test.py

The problem in one sentence
---------------------------
McPAT publishes the results-broadcast bus as an **Area Overhead**, not an Area -- the project's own
``isa_floorplans._root_area`` exists because of that spelling. An overhead is not a footprint: a
results-broadcast bus is wiring distributed across the execution units, and it has no compact place
to sit. The tiler nonetheless renders it as a discrete rectangle and hands it the bus's full power.

The result is a real power number on a fictitious footprint, and it is the hottest block on every
die this project has simulated.

What that does at density
-------------------------
Leakage feedback is exponential in temperature, so the hottest block sets whether the solve
converges. Once RBB crosses the top of the calibrated leakage table (400 K) the Arrhenius tail
multiplies its leakage by hundreds, which heats it further -- it reaches thousands of kelvin on
ITERATION ONE. The die then has no steady state, so every question asked at that density returns
"diverged" regardless of what else was varied. That is why sweeping dt_max over 6.7x and h_max over
120x changed nothing: the outcome was decided before either mattered.

The fix, and why it is the honest one
-------------------------------------
Amortize the bus into the units it actually spans, which is what "Area Overhead" already means.
Three ways to do it, in descending order of principle:

 1. **Redistribute its power** across the execution-unit blocks in proportion to their area, and
    stop placing RBB as a block. This matches the published semantics exactly and needs no new
    assumption.
 2. **Give it a real footprint** -- the span of the execution units it serves -- and keep its
    power. Arithmetically close to (1); differs only in whether the bus appears as a named block.
 3. **Cap block power density** at a physical ceiling. A guard, not a fix: it stops the runaway
    without making the number right, and would silently alter every existing result.

This file quantifies (1) against the current placement so the size of the change is on record
before anyone edits the tiler.

`[!]` What this is not
-----------------------
Not the fix itself. Changing how RBB is placed alters every recorded thermal result in the
project, so it needs to land as a deliberate, tested change with the catalogue re-run behind it --
not as a side effect of an overnight investigation. This measures what that change is worth.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.utils.floorplan import Floorplan
from HotGauge.thermal.mr_array import blocks_from_floorplan

#: the execution-unit blocks a results-broadcast bus physically spans
EU_BLOCKS = ('cALU', 'iALU', 'FPUs', 'AVXs', 'regs', 'iRF', 'fpRF', 'iSched')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--flp', default=os.path.join(
        _HERE, 'floorplans', 'outputs', 'skylake7nm_34core_3_3D-ICE.flp'))
    ap.add_argument('--die-W', type=float, default=210.7,
                    help='die power at the operating point of interest (default: the sustainable '
                         'clock found by the dt_max sweep, where the array holds 92 C)')
    ap.add_argument('--rbb-power-share', type=float, default=0.0164,
                    help='share of die power on the bus. Default from the measured profile: '
                         'RBB_0 at 0.759 W of a 46.03 W mapped total')
    ap.add_argument('--json-out', default=os.path.join(_EV, 'rbb_amortization.json'))
    args = ap.parse_args()

    b = blocks_from_floorplan(Floorplan.from_file(args.flp, frmt='3D-ICE'))
    area = {n: v[2] * v[3] / 1e6 for n, v in b.items()}          # mm^2
    die_mm2 = sum(area.values())
    rbb = {n: a for n, a in area.items() if n.startswith('RBB')}
    eu = {n: a for n, a in area.items() if n.split('_')[0] in EU_BLOCKS}

    rbb_area = sum(rbb.values())
    eu_area = sum(eu.values())
    rbb_W = args.rbb_power_share * args.die_W
    q_now = rbb_W / rbb_area
    q_amortized = rbb_W / eu_area
    # what the EU blocks already carry, so the added density can be put in proportion
    print('floorplan: %s' % os.path.basename(args.flp))
    print('  die %.2f mm^2, %d blocks\n' % (die_mm2, len(b)))
    print('  RBB as placed        %d blocks, %.4f mm^2 total (%.3f%% of die)'
          % (len(rbb), rbb_area, 100 * rbb_area / die_mm2))
    print('  execution units      %d blocks, %.3f mm^2 total (%.2f%% of die)'
          % (len(eu), eu_area, 100 * eu_area / die_mm2))
    print()
    print('  bus power at this operating point   %.2f W' % rbb_W)
    print('  density as placed                   %.1f W/mm^2' % q_now)
    print('  density if amortized over the EUs   %.3f W/mm^2' % q_amortized)
    print('  ratio                               %.0fx' % (q_now / q_amortized))
    print()
    print('  real silicon blocks on this die sit at 1-3 W/mm^2, so the placed value is')
    print('  %.0f-%.0fx physical and the amortized value is inside the normal range.'
          % (q_now / 3.0, q_now / 1.0))

    out = {'note': __doc__.strip(),
           'floorplan': os.path.basename(args.flp), 'die_mm2': die_mm2,
           'die_W_at_operating_point': args.die_W,
           'rbb': {'n_blocks': len(rbb), 'area_mm2': rbb_area,
                   'share_of_die': rbb_area / die_mm2,
                   'power_W': rbb_W, 'density_W_per_mm2': q_now},
           'execution_units': {'n_blocks': len(eu), 'area_mm2': eu_area,
                               'share_of_die': eu_area / die_mm2},
           'amortized_density_W_per_mm2': q_amortized,
           'density_ratio': q_now / q_amortized,
           'THE_MISMATCH_IS_THE_WHOLE_PROBLEM': (
               'The bus carries {:.2f} W on {:.4f} mm^2 because McPAT published an AREA OVERHEAD '
               'and the tiler treated it as a footprint. That is {:.0f} W/mm^2, against 1-3 for '
               'real blocks on the same die. Amortized over the {:.2f} mm^2 of execution units the '
               'bus actually spans, the same power is {:.3f} W/mm^2 -- inside the normal range, and '
               'a factor of {:.0f} lower.'
               .format(rbb_W, rbb_area, q_now, eu_area, q_amortized, q_now / q_amortized)),
           'WHY_IT_GATES': (
               'Leakage feedback is exponential in temperature, so the hottest block decides '
               'whether the solve converges. RBB is the hottest block on every die here. Past '
               '400 K -- the top of the calibrated leakage table -- the Arrhenius tail multiplies '
               'its leakage by hundreds and it reaches thousands of kelvin on iteration one. Every '
               'question asked at that density then returns "diverged" whatever else was varied, '
               'which is why dt_max over 6.7x and h_max over 120x had no effect.'),
           'THE_FIX': (
               'Redistribute the bus power across the execution-unit blocks in proportion to '
               'area, and stop placing RBB as a block. That is what "Area Overhead" already means '
               'and it needs no new assumption. Alternatives: give it the real span of the units '
               'it serves (arithmetically close), or cap block power density (a guard, not a fix, '
               'and it would silently alter every existing result).'),
           'WHY_THIS_FILE_DOES_NOT_DO_IT': (
               'Changing RBB placement alters every recorded thermal result in the project. It '
               'should land as a deliberate, tested change with the catalogue re-run behind it, '
               'not as a side effect of an overnight investigation. This measures what the change '
               'is worth so the decision can be made on a number.'),
           }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
