#!/usr/bin/env python
"""Why RBB gates the high-density programme, and what fixing it is worth.

    python examples/rbb_amortization_test.py

`[!]` CORRECTED 31 Aug 2026. The first version of this file argued that RBB's placed density
must be unphysical because real blocks sit at 1-3 W/mm^2. **That premise is false and is
withdrawn.** The HotGauge paper (SII-A) reports >8 W/mm^2 within a core, literature hotspot
definitions are 6.8-10, and this project's own measured distribution on these dies has block
p90 = 13.2 and p99 = 64.4 W/mm^2, with iBuf at 141 and cALU at 65. RBB sits *inside* that
distribution. The case below rests on the area semantics instead, which is where it always
belonged -- and which the McPAT source settles outright.

The problem in one sentence
---------------------------
McPAT publishes the results-broadcast bus as an **Area Overhead**, not an Area -- the project's own
``isa_floorplans._root_area`` exists because of that spelling. Two lines of McPAT say what the
spelling means:

* ``EXECU::EXECU`` (``McPAT/core.cc`` ~1150-1259) builds the bus out of ``interconnect`` objects
  whose *length* argument is ``rfu->int_regfile_height + exeu->FU_height + lsq_height``, plus
  ``scheu->Iw_height`` for the tag bus. ``RegFU``'s own comment (~core.cc:989) says it plainly:
  *"the bypass buses need to travel across all the register files."* The area is real silicon --
  wire tracks -- distributed across the execution cluster by construction.
* ``core.cc:1265`` folds that area into the Execution Unit's own: ``area.set_area(area.get_area()
  + bypass.area.get_area())``. "Area Overhead" means *itemised, and already inside the parent*.

The tiler nonetheless renders it as a discrete 142 x 13 um rectangle and hands it the bus's full
power. That is a real power number on a fictitious footprint, and it is the hottest block on every
die this project has simulated.

`[!]` And the tiler is not wrong by accident. ``examples/floorplans.py``'s
``# Make RBB Area instead of Area Overhead`` is **stock** HotGauge, present in the initial commit,
and Fig. 5 of the paper shows RBB as a block. Changing it is a deliberate divergence from
upstream, not a bug fix, which is why it ships as an opt-in policy rather than a new default.

What that does at density
-------------------------
Leakage feedback is exponential in temperature, so the hottest block sets whether the solve
converges. Once RBB crosses the top of the calibrated leakage table (400 K) the Arrhenius tail
multiplies its leakage by hundreds, which heats it further -- it reaches thousands of kelvin on
ITERATION ONE. The die then has no steady state, so every question asked at that density returns
"diverged" regardless of what else was varied. That is why sweeping dt_max over 6.7x and h_max over
120x changed nothing: the outcome was decided before either mattered.

The fix
-------
Amortize the bus into the units it spans, which is what "Area Overhead" already means. Three ways
were costed, in descending order of principle:

 1. **Redistribute its power** across the execution-unit blocks in proportion to their area, and
    stop giving RBB power. Matches the published semantics exactly; needs no new assumption.
 2. **Give it a real footprint** -- the span of the units it serves. Arithmetically close to (1),
    but the tiler places disjoint rectangles and this bus overlaps its siblings by construction,
    so it cannot be expressed. **Not implementable here.**
 3. **Cap block power density.** A guard, not a fix: it stops the runaway without making the
    number right, and would silently alter every existing result.

**(1) has now landed** as ``HotGauge.thermal.rbb`` -- ``--rbb-policy {stock,amortized}``,
defaulting to ``stock`` so an un-flagged re-run reproduces the recorded catalogue. The RBB
rectangle stays in the floorplan at zero power: it stands for wire tracks that are real silicon
but physically elsewhere, so deleting it would shrink the die while re-tiling to grow its
neighbours would move every block and make the two policies incomparable. Power moves; geometry
does not.

What this file still does
-------------------------
Sizes the change on the shipped floorplan, so the decision rests on a number. The recipient set
comes from ``rbb.rbb_recipients`` rather than a local list -- `[!]` the original list here named
``regs`` and ``iSched``, which this floorplan *subdivides*, so it silently excluded the scheduler
blocks the tag bus explicitly spans and counted 204 recipients where the floorplan has 272.
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
from HotGauge.thermal.rbb import rbb_recipients


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
    eu = {b: a for blocks in rbb_recipients(area).values() for b, a in blocks.items()}

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
    print('  `[!]` The ratio is the size of the change, NOT an argument that the placed value')
    print('  is unphysical: block p90 on this die is 13.2 W/mm^2 and p99 is 64.4, so %.0f'
          % q_now)
    print('  sits inside the measured distribution. The case rests on the area semantics.')

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
           'THE_MISMATCH': (
               'The bus carries {:.2f} W on {:.4f} mm^2 because McPAT published an AREA OVERHEAD '
               'and the tiler treated it as a footprint. That is {:.0f} W/mm^2; amortized over '
               'the {:.2f} mm^2 of execution units the bus spans it is {:.3f} W/mm^2, a factor '
               'of {:.0f} lower. `[!]` That ratio is the SIZE of the change and nothing more. It '
               'is NOT evidence the placed value is unphysical -- block p90 on this die is 13.2 '
               'W/mm^2 and p99 is 64.4, so the placed value sits inside the measured '
               'distribution. The earlier "real blocks are 1-3 W/mm^2" claim is WITHDRAWN.'
               .format(rbb_W, rbb_area, q_now, eu_area, q_amortized, q_now / q_amortized)),
           'WHY_THE_FOOTPRINT_IS_FICTITIOUS': (
               'Not density -- geometry. McPAT builds the bus from interconnect wires whose '
               'length spans the register file, the functional units and the LSQ (core.cc '
               '~1150-1259; RegFU comment at ~989: "the bypass buses need to travel across all '
               'the register files"), and folds their area into the Execution Unit at '
               'core.cc:1265. An Area Overhead is itemised and already inside its parent. The '
               'compact rectangle the tiler gives it is not where that copper is.'),
           'WHY_IT_GATES': (
               'Leakage feedback is exponential in temperature, so the hottest block decides '
               'whether the solve converges. RBB is the hottest block on every die here. Past '
               '400 K -- the top of the calibrated leakage table -- the Arrhenius tail multiplies '
               'its leakage by hundreds and it reaches thousands of kelvin on iteration one. Every '
               'question asked at that density then returns "diverged" whatever else was varied, '
               'which is why dt_max over 6.7x and h_max over 120x had no effect.'),
           'THE_FIX': (
               'Redistribute the bus power across the execution-unit blocks in proportion to '
               'area, and stop giving RBB power. That is what "Area Overhead" already means and '
               'it needs no new assumption. Giving it the real span instead is arithmetically '
               'close but not implementable -- the tiler places disjoint rectangles and this bus '
               'overlaps its siblings by construction. Capping block power density is a guard, '
               'not a fix.'),
           'STATUS': (
               'LANDED 31 Aug 2026 as HotGauge.thermal.rbb: --rbb-policy {stock,amortized}, '
               'default stock so an un-flagged re-run reproduces the recorded catalogue. The RBB '
               'rectangle stays in the floorplan at zero power. Bracketed against stock on the '
               'same density ladder before any catalogue re-run: results/rbb_bracket.'),
           'RECIPIENT_SET_CORRECTED': (
               'This file previously named regs and iSched as recipients. The shipped tiler '
               'SUBDIVIDES both, so neither is ever placed -- the set silently excluded iWin, '
               'fpiWin and ROB, the scheduler blocks the tag bus explicitly spans, and counted '
               '204 recipient blocks where the floorplan has 272. It now takes the set from '
               'rbb.rbb_recipients, which also drops AVXs: this pipeline forces AVXs to zero '
               'power, so anything routed there would be destroyed downstream.'),
           'WHY_IT_IS_A_POLICY_AND_NOT_A_DEFAULT': (
               'examples/floorplans.py\'s "Make RBB Area instead of Area Overhead" is STOCK '
               'HotGauge, present in the initial commit, and Fig. 5 of the paper shows RBB as a '
               'block. Amortizing is a deliberate divergence from upstream, not a bug fix, so '
               'stock stays the default and the alternative is opt-in and stamped on every row.'),
           }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
