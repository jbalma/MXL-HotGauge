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
from HotGauge.thermal.ice_server import ICESessionCache, shared_cache
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink)
from HotGauge.thermal.sink_models import spreading_sink_for_stack, MicrochannelSink
from HotGauge.thermal.die_stack import stack_for_spreading
from HotGauge.thermal.stack_models import coarsen_stack_grid
from HotGauge.thermal.cooling_spec import (CoolingSpec, CoolingSpecSink, air_spec,
                                           solve_flow_for_peak, velocity_is_plausible)
from HotGauge.thermal.mr_array import (wiring_for_stack, stack_carries_an_array,
                                       DEFAULT_PITCH_UM, device_pitch_range_um)
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, mr_accounting,
                                                 DEFAULT_H_MAX_W_PER_MM2, DEFAULT_DT_MAX_K, DEFAULT_ETA_ASF, DEFAULT_LASER_WALLPLUG, DEFAULT_LPC_EFFICIENCY)
from HotGauge.thermal.accelerator_floorplan import (
    GA100_AREAS, GA100_POWER_SPLIT, DEFAULT_BOOST_POWER_RATIO, ga100_geometry,
    ga100_consistency, ga100_floorplan, ga100_block_powers, block_areas_mm2,
    power_density_by_class, power_split_sensitivity, tier_analysis_by_class,
    kernel_activity, KERNELS)

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGGER = logging.getLogger('accelerator_study')
T_FLOOR_K = 273.15

def _session(no_server):
    """The process-wide session cache, or None when running without the server.

    Deliberately NOT a module-level global here: ``runpy.run_path`` re-executes this file for each
    point of a sweep and would reset it, so a three-point sweep still factorised three times. The
    singleton lives in ``ice_server``, which is imported normally and therefore survives.
    """
    return None if no_server else shared_cache()

_MIN_DIM_CACHE = {}


def _min_dim_um(flp_path, name):
    """Narrowest side of a block [um] -- the MR spot policy needs it to know whether the pixel
    can be focused onto the block or has to be billed pixel-wide."""
    if flp_path not in _MIN_DIM_CACHE:
        d, cur = {}, None
        with open(flp_path) as f:
            for line in f:
                t = line.strip()
                if t.endswith(':'):
                    cur = t[:-1].strip()
                elif t.startswith('dimension') and cur:
                    w, h = [float(v) for v in t[len('dimension'):].strip(' ;').split(',')]
                    d[cur] = min(w, h)
        _MIN_DIM_CACHE[flp_path] = d
    return _MIN_DIM_CACHE[flp_path].get(name, 1e9)


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
    # --- kernel shape: the one input that could still produce a real hotspot ---
    ap.add_argument('--kernel', default='uniform', choices=list(KERNELS),
                    help="activity shape. 'uniform' (default) is the CONTROL -- every block in a "
                         "class equal, so any hotspot comes from geometry rather than from an "
                         "imbalance assumed into the input. The others are real GPU behaviour: "
                         "'occupancy' runs --n-active SMs boosted and idles the rest, "
                         "'memory_bound' stalls the SMs and runs the interface flat out, "
                         "'tensor' moves power from each L1 array into its own datapath")
    ap.add_argument('--n-active', type=int, default=None,
                    help='SMs running, for --kernel occupancy (1..128)')
    ap.add_argument('--placement', default='contiguous',
                    choices=('contiguous', 'scattered', 'cluster'),
                    help='where the active SMs sit. This is most of the answer, not a detail: '
                         'contiguous piles their heat together (worst for the die, best for MR), '
                         'scattered surrounds each with idle silicon, cluster fills whole '
                         '32-SM groups as a GPC-aligned or MIG partition would')
    ap.add_argument('--idle-fraction', type=float, default=None,
                    help='power an idle SM still draws, as a fraction of an active one (ASSUMED; '
                         'default 0.10). Setting it to 0 would make any partial-occupancy die look '
                         'far more concentrated than a real part')
    ap.add_argument('--boost-power-ratio', type=float, default=None,
                    help='power multiplier for a boosted SM (ASSUMED; default %.2f). Load-bearing '
                         'for the occupancy result -- sweep it' % DEFAULT_BOOST_POWER_RATIO)
    ap.add_argument('--dt-max-K', type=float, default=DEFAULT_DT_MAX_K,
                    help='MR device capability, for the plateau and clip-one figures')
    # --- MR: what a rescue actually costs on this die ---
    ap.add_argument('--mr', action='store_true',
                    help='also run the microrefrigeration clipping loop and price it. Only worth '
                         'doing where the die is actually over its limit -- a plateau that is '
                         'cheap to clip on a 78 C die is a solution to no problem')
    ap.add_argument('--mr-target-C', type=float, default=98.0)
    ap.add_argument('--mr-iter', type=int, default=25)
    ap.add_argument('--mr-h-max', type=float, default=DEFAULT_H_MAX_W_PER_MM2)
    ap.add_argument('--eta-asf', type=float, default=DEFAULT_ETA_ASF)
    ap.add_argument('--eta-laser', type=float, default=DEFAULT_LASER_WALLPLUG)
    ap.add_argument('--eta-lpc', type=float, default=DEFAULT_LPC_EFFICIENCY)
    ap.add_argument('--spot-min-um', type=float, default=10.0)
    ap.add_argument('--spot-policy', default='dilute')
    ap.add_argument('--split-sensitivity', default=None,
                    help='also report density accounting with this class share scaled 0.5-1.5x, '
                         'e.g. hbm_phy')
    # thermal
    # --- cooling ---
    # The legacy sinks return the SAME thermal resistance whatever the die is, which is what
    # invalidated every accelerator temperature this study produced. --cooling-fluid switches to
    # a sink whose geometry is built for the die and whose parasitic power includes the chiller.
    ap.add_argument('--cooling-fluid', default=None, choices=('air', 'water'),
                    help='use a geometry-derived CoolingSpec sink sized for this die, instead of '
                         'the legacy fixed-resistance sink. STRONGLY preferred for the '
                         'accelerator: the legacy sink gives an 826 mm^2 die the same 0.0764 K/W '
                         'as a 101 mm^2 one')
    ap.add_argument('--cooling-flow-m3s', type=float, default=None,
                    help='flow rate for --cooling-fluid; omit to solve it from --cooling-target-C')
    ap.add_argument('--cooling-target-C', type=float, default=90.0,
                    help='lumped peak the flow is solved to hold, when no flow is given. The real '
                         'peak comes from the coupled solve; this only CHOOSES the operating point')
    ap.add_argument('--microchannel', action='store_true',
                    help='direct-die MICROCHANNEL cold plate instead of a finned water block or '
                         'an air sink. Anchored on a measured reference (1020 W/cm^2 at <69 C '
                         'and <120 kPa; see sink_models.MICROCHANNEL_REF). This is what a '
                         'direct-die accelerator is really cooled by -- CoolingSpec\'s water '
                         'path is a finned base sized for the die and comes out ~3.6x worse')
    ap.add_argument('--dt-fluid-K', type=float, default=10.0,
                    help='coolant temperature rise across the die for --microchannel; sets the '
                         'flow, and therefore the pump power. The reference rig runs ~2 K, which '
                         'is far more flow than a practical loop')
    ap.add_argument('--inlet-C', type=float, default=35.0)
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, default=None,
                    help='use a fixed thermal resistance [K/W] instead of an air sink')
    ap.add_argument('--ambient-K', type=float, default=308.15)
    ap.add_argument('--spreading', action='store_true',
                    help='take the cold-plate slab OUT of the stack and fold it into the boundary '
                         'as a real overhanging base (P0.4). A slab in the stack is a column of '
                         'metal the width of the die, so the package budget comes out as 1/area '
                         '-- 15.5x across the die sizes here, against 2.6x with the overhang. '
                         'Amends the --stack spec with sink_in_stack=0. STRONGLY preferred for '
                         'anything quotable; off by default so results predating it reproduce.')
    ap.add_argument('--base-mm2', type=float, default=None,
                    help='cold-plate footprint [mm^2] for --spreading. Default: the socket '
                         'footprint (a fixed AREA, not a ratio of the die)')
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--pitch-um', type=float, default=DEFAULT_PITCH_UM,
                    help='cooling tile pitch; the array is a second powered die')
    ap.add_argument('--no-array', action='store_true',
                    help='legacy in-source-layer placement -- an upper bound, not the device')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--leakage-cal',
                    # The measured McPAT curve lives HERE. I first defaulted this to
                    # docs/evidence/, which does not exist, so every accelerator run
                    # silently fell back to an assumed exponential while the CPU runs
                    # used the measured one -- breaking the iso-node comparison the
                    # whole study rests on. The fallback is legitimate; defaulting to
                    # it by typo is not.
                    default=os.path.join(_REPO, 'leakage_calibration',
                                         'leakage_calibration.json'))
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
    kw = {}
    if args.idle_fraction is not None:
        kw['idle_fraction'] = args.idle_fraction
    if args.boost_power_ratio is not None:
        kw['boost_ratio'] = args.boost_power_ratio
    activity, kmeta = kernel_activity(classes, kernel=args.kernel, n_active=args.n_active,
                                      placement=args.placement, **kw)
    powers, pmeta = ga100_block_powers(power_W, classes, activity=activity)
    realised_W = pmeta['realised_W']
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
    print('  power    : {:.1f} W nominal -> {:.1f} W realised = {:.3f} W/mm^2 die average   '
          '[class split ASSUMED]'.format(power_W, realised_W, realised_W / area_mm2))
    if args.kernel == 'uniform':
        print('  kernel   : uniform (CONTROL -- any hotspot is geometric, not assumed in)')
    else:
        print('  kernel   : {}{}'.format(
            args.kernel,
            '  {} of {} SMs active, {} placement, boost x{:.2f}, idle {:.0%}'.format(
                kmeta.get('n_active'), kmeta.get('n_sm'), kmeta.get('placement'),
                kmeta.get('boost_ratio', 1.0), kmeta.get('idle_fraction', 0.0))
            if args.kernel == 'occupancy' else ''))
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
    cooling_note = None
    if args.cooling_fluid:
        if args.cooling_flow_m3s is not None:
            spec = (air_spec(area_mm2, args.cooling_flow_m3s, args.inlet_C,
                             ambient_C=args.ambient_K - 273.15)
                    if args.cooling_fluid == 'air' else
                    CoolingSpec('water', area_mm2, args.cooling_flow_m3s, args.inlet_C,
                                ambient_C=args.ambient_K - 273.15))
        else:
            spec = solve_flow_for_peak(args.cooling_fluid, area_mm2, realised_W,
                                       args.cooling_target_C, inlet_C=args.inlet_C,
                                       ambient_C=args.ambient_K - 273.15)
            if spec is None:
                raise SystemExit(
                    'no flow rate holds {:.0f} C at {:.0f} W on a {:.0f} mm^2 die with {} -- '
                    'that is a real answer, not an error: this cooling class cannot do it.'
                    .format(args.cooling_target_C, realised_W, area_mm2, args.cooling_fluid))
            if args.cooling_fluid == 'air':
                spec = air_spec(area_mm2, spec.flow_m3s, args.inlet_C,
                                ambient_C=args.ambient_K - 273.15)
        ok, vmsg = velocity_is_plausible(spec)
        cooling_note = spec.report(realised_W)
        cooling_note['velocity_plausible'] = ok
        cooling_note['velocity_note'] = vmsg
        sink = CoolingSpecSink(spec, realised_W)
    elif args.microchannel:
        # Direct-die microchannel cold plate, anchored on a measured reference point. This is
        # what a direct-die accelerator is actually cooled by; CoolingSpec's water path models a
        # finned base sized for the die, which is a water block and ~3.6x worse.
        sink = MicrochannelSink(area_mm2, realised_W, dT_fluid_K=args.dt_fluid_K,
                                inlet_C=args.inlet_C, ambient_K=args.ambient_K)
        cooling_note = {'kind': 'microchannel', 'r_th_K_per_W': sink.r_th_K_per_W,
                        'r_conv_K_per_W': sink.r_conv_K_per_W,
                        'r_caloric_K_per_W': sink.r_caloric_K_per_W,
                        'flow_m3s': sink.flow_m3s, 'dp_Pa': sink.pressure_drop_Pa,
                        'pump_W': sink.parasitic_power_W(),
                        'flux_ratio_vs_reference': sink.flux_ratio,
                        'inlet_C': args.inlet_C, 'dT_fluid_K': args.dt_fluid_K}
        print('  cooling  : {}'.format(sink.describe()))
        print('             pump power is CHANNELS ONLY -- a floor. The manifold, plenum and '
              'facility loop are not modelled;\n             the LCEstimator CDU figure is '
              '~7 W/device for the whole loop.')
    else:
        sink = (ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K)
                if args.r_th is not None
                else BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K))
    stack_name = args.stack
    if args.spreading:
        stack_name = stack_for_spreading(stack_name)
        sink = spreading_sink_for_stack(stack_name, sink, area_mm2,
                                        base_area_mm2=args.base_mm2)
    stack = render_stack_with_sink(get_stack_template(stack_name), sink,
                                  os.path.join(args.out_dir, 'ga100.stk'))
    coarsen_stack_grid(stack, args.cell_um)
    # ONE cache for the whole run. This must be created outside every loop: the cache is what
    # makes the factorisation a one-time cost, and the MR loop calls the solver 15-25 times with
    # an identical system matrix. Constructing a cache per call -- which this file did briefly --
    # starts a fresh server and refactorises each time, multiplying walltime by the solve count.
    # On the GA100 die that is 288 s per iteration instead of 288 s once.
    session = _session(args.no_server)

    # The cooling array, if this stack carries one. Built HERE rather than inside `if args.mr`,
    # because a stack that declares an array die needs its tile floorplan for EVERY solve, not
    # only the ones with a laser plan. Without that:
    #
    #   * the baseline solve below cannot render the stack at all -- {mr_flp_file} is unfilled --
    #     so the array arms would only be reachable with --mr; and
    #   * the `array_idle` arm would be unreachable, which is the one that separates the GaAs
    #     substitution from the laser. On the first three-arm runs the unpowered array alone
    #     rescued a die that had no steady state under grease, so an on/off comparison books
    #     that packaging gain as a photonics result.
    #
    # Zero-power tiles at construction; the planner replaces them if --mr runs.
    #
    # `want_array` is `--mr or the stack has one`, which keeps BOTH silent failures loud without
    # breaking a plain baseline run:
    #   * --mr on a stack with no array die is refused, naming the fix -- a plan computed and
    #     projected onto tiles that do not exist lands nowhere and reads as a cooler that does
    #     not work;
    #   * a stack that DOES declare an array gets wired whether or not a laser plan is asked
    #     for, which is what makes the unpowered arm reachable;
    #   * a baseline run on a single-die stack is untouched, exactly as before.
    wiring = None if args.no_array else wiring_for_stack(
        stack, flp_path, os.path.join(args.out_dir, 'mr_array'),
        want_array=bool(args.mr) or stack_carries_an_array(stack),
        pitch_um=args.pitch_um, cell_um=args.cell_um)

    solver = ICEThermalSolver(stack, flp_path, args.tech_node,
                              run_base_dir=os.path.join(args.out_dir, 'solve'),
                              initial_temp=args.ambient_K, num_cores=1,
                              single_thread=True, mode='steady',
                              session_cache=session,
                              # The trace's keys ARE this floorplan's element names, so the
                              # McPAT rename/L3-split/IMC path must be skipped -- there are no
                              # cores here to split an L3 across.
                              already_dice_named=True,
                              **(wiring.solver_kwargs() if wiring else {}))

    if cooling_note and cooling_note.get('kind') == 'microchannel':
        # Already reported at construction; the fin-stack fields below do not exist for it.
        pass
    elif cooling_note:
        print('  cooling  : {} sized for this die -- base {:.0f} mm, {} fins, {:.4g} m^3/s'.format(
            args.cooling_fluid, cooling_note['base_side_mm'], cooling_note['n_fins'],
            cooling_note['flow_m3s']))
        print('             R_th {:.4f} K/W (conv {:.4f} + caloric {:.4f}), inlet {:.1f} C'.format(
            cooling_note['r_conv_K_per_W'] + cooling_note['r_caloric_K_per_W'],
            cooling_note['r_conv_K_per_W'], cooling_note['r_caloric_K_per_W'],
            cooling_note['inlet_C']))
        print('             wall plug {:.1f} W = {:.1f} mover + {:.1f} chiller   [{}]'.format(
            cooling_note['wall_plug_W'], cooling_note['mover_power_W'],
            cooling_note['chiller_power_W'], cooling_note['velocity_note']))
        if not cooling_note['velocity_plausible']:
            print('             WARNING: not a buildable configuration')
    else:
        print('  cooling  : {}  [LEGACY sink -- resistance does NOT scale with die area]'.format(
            'R_th {:g} K/W'.format(args.r_th) if args.r_th is not None
            else '{:g} CFM baffled fin'.format(args.cfm)))
    print('\n  solving the leakage fixed point over {} blocks ...'.format(len(classes)))

    if args.mr:
        # Same scaffolding mr_comparison.py uses: the MR loop drives the coupled solve, and the
        # verification verdict belongs to the solve that produced the REPORTED field rather than
        # to every probe the descent made.
        geom = {}
        for name, a_mm2 in areas.items():
            geom[name] = {'area_mm2': a_mm2, 'min_dim_um': _min_dim_um(flp_path, name)}
        counter = {'n': 0}
        holder = {}

        def solve_fn(tr):
            counter['n'] += 1
            r = run_leakage_feedback(tr, leak_ref, ICEThermalSolver(
                stack, flp_path, args.tech_node,
                run_base_dir=os.path.join(args.out_dir, 'solve',
                                          'mr{:02d}'.format(counter['n'])),
                initial_temp=args.ambient_K, num_cores=1, single_thread=True, mode='steady',
                session_cache=session,
                already_dice_named=True,
                **(wiring.solver_kwargs() if wiring else {})),
                model=leak_model, T_ref=t_ref, num_cores=1, tol_K=args.tol,
                max_iter=args.max_iter, relax=args.relax, t_floor_K=T_FLOOR_K,
                bridge_aggregates=False,
                               name_map=(lambda u: u), verify=True)
            holder['last'] = r
            return r['temp_trace']

        mrp = MRParams(target_K=args.mr_target_C + 273.15, h_max=args.mr_h_max,
                       dt_max_K=args.dt_max_K, eta_asf=args.eta_asf,
                       laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                       spot_min_um=args.spot_min_um, spot_policy=args.spot_policy)
        mres = run_mr_clipping(trace, solve_fn, geom, mrp, name_map=lambda u: u,
                               max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                               **(wiring.planner_kwargs() if wiring else {}),
                               status_fn=lambda: {
                                   'diverged': bool((holder.get('last') or {}).get('diverged')),
                                   'unconverged': bool(
                                       (holder.get('last') or {}).get('unconverged'))},
                               plan_mode='auto')
        acc = mres['accounting']
        res = dict(holder.get('last') or {})
        res['temp_trace'] = mres['temp_trace']
        res['diverged'] = bool(mres.get('temp_trace_diverged'))
        res['unconverged'] = bool(mres.get('result_unconverged'))
        out_mr = {'target_C': args.mr_target_C, 'n_targets': len(mres.get('plan') or {}),
                  'heat_removed_W': acc.get('heat_removed_W'),
                  'heat_billed_W': acc.get('heat_billed_W'),
                  'electrical_W': acc.get('electrical_power_W'),
                  'effective_cop': acc.get('effective_cop'),
                  'net_generating': acc.get('net_generating'),
                  'holds_target': mres.get('plan_holds_target'),
                  'plan_is_minimum': mres.get('plan_is_minimum'),
                  # Depth versus breadth versus cost: three different verdicts, and on this die
                  # they do not point at the same fix.
                  'dt_max_bound': mres.get('dt_max_bound'),
                  'lift_achieved_K': mres.get('lift_achieved_K'),
                  'lift_needed_K': mres.get('lift_needed_K'),
                  'reason': mres.get('reason')}
        print('  [MR] target {:.0f} C -> {} blocks, {:.4f} W removed, {:.3f} W net electrical'
              '  (holds={}, minimal={})'.format(
                  args.mr_target_C, out_mr['n_targets'], out_mr['heat_removed_W'] or 0.0,
                  out_mr['electrical_W'] or 0.0, out_mr['holds_target'],
                  out_mr['plan_is_minimum']))
        print('       reason: {}'.format(out_mr['reason']))
    else:
        out_mr = None
        res = run_leakage_feedback(trace, leak_ref, solver, model=leak_model, T_ref=t_ref,
                                   num_cores=1, tol_K=args.tol, max_iter=args.max_iter,
                                   relax=args.relax, t_floor_K=T_FLOOR_K,
                                   bridge_aggregates=False,
                               name_map=(lambda u: u), verify=True)

    if res.get('diverged'):
        print('\n  NO STEADY STATE: thermal runaway at {:.3f} W/mm^2. That is a result, not a '
              'failure -- report it as one.'.format(power_W / area_mm2))
    if res.get('unconverged'):
        print('\n  WARNING: failed damping verification (worst spread {} K). Not quotable.'
              .format(res.get('verify_spread_K')))

    out = {'floorplan': 'GA100 (measured die shots)', 'calibrated': False,
           'die_mm2': area_mm2, 'n_blocks': len(classes),
           'die_power_W': power_W, 'realised_W': realised_W,
           'density_W_per_mm2': realised_W / area_mm2,
           'nominal_density_W_per_mm2': power_W / area_mm2,
           'kernel': args.kernel, 'kernel_meta': kmeta, 'mr': out_mr,
           'cell_um': args.cell_um, 'split_sm': not args.no_split_sm,
           'leak_fraction': args.leak_fraction, 'leak_basis': leak_basis,
           'cfm': args.cfm, 'r_th': args.r_th, 'dt_max_K': args.dt_max_K,
           'cooling_fluid': args.cooling_fluid, 'cooling': cooling_note,
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
    else:
        temps_C = {}

    if not temps_C:
        # A point can fail damping verification and come back with a field that is entirely at
        # the floor. That is an UNQUOTABLE RESULT, not a crash: tier_analysis_by_class raises
        # 'no blocks to rank' on an empty field, and letting that propagate killed the point and
        # everything the caller wanted to write about it. Report it and move on -- the run
        # already carries `unconverged` and `verify_spread_K` saying why.
        out['tiers'] = None
        out['clip_curve'] = None
        out['no_field'] = True
        print('\n  NO USABLE FIELD: every block sat at the solver floor, so there is nothing to '
              'rank.\n  This point is unconverged ({}), not a crash -- recorded as unquotable.'
              .format('diverged' if res.get('diverged') else 'failed damping verification'))
    else:
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
