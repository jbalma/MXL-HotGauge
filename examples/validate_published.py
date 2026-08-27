#!/usr/bin/env python
"""Does the model reproduce a part that demonstrably works?

    python examples/validate_published.py --point H100_AIR

Everything in this project is calibrated piecewise and none of it had been checked end to end.
The result was a model predicting thermal runaway for a 400 W accelerator at 0.48 W/mm^2 -- a
configuration that ships in volume and does not run away. A model that contradicts a part you can
buy is falsified, whatever its components say.

This runs the published operating point through the same coupled solve every study uses, and says
plainly whether it lands. When it does not, ``--bisect`` walks the three candidate causes in the
order they are cheapest to rule out:

    split     the assumed per-class power split, which puts 1.47 W/mm^2 on an 8 mm^2 memory
              controller -- flatten it toward uniform and see whether the hotspot survives
    leak      leakage fraction applied uniformly to every class including HBM PHY and NVLINK,
              which are largely dynamic and should not leak like logic
    cooling   the sink, which CoolingSpec already reproduces to within a few percent of the
              published resistance -- so this one is expected to be exonerated

The stack template WAS the fourth candidate and the one this script could not vary. It can now:
``--stack`` takes a generated spec, and ``--spreading`` moves the package's spreading layers out
of the stack and into the boundary, where they get their real overhang instead of being a column
of metal the width of the die.

That fourth candidate turned out to be the largest one. As a stack layer the base tracks 1/area
exactly -- 15.5x across the die sizes this project models -- which is why the gate reproduced an
826 mm^2 accelerator and failed a 91 mm^2 CPU. See ``docs/evidence/direct_die_overhang.json``.

**Read the result honestly.** Four package inputs behind this gate are still unvalidated: the
die-attach solder thickness and conductivity, and the cold plate's thickness and conductivity
(``docs/PHASE0_CHECKLIST.md``, P0.4). Adjusting them until the gate passes is tuning against the
acceptance test, which is the exact failure the gate exists to prevent. Run it at the values the
model already holds; if it fails, that is a result and the four inputs are where to look, with
their OWN references.
"""
import os
import sys
import json
import argparse
import logging

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace, LeakageModel
from HotGauge.thermal import get_stack_template, ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.ice_server import shared_cache
from HotGauge.thermal.leakage_feedback import load_calibrated_leakage_model
from HotGauge.thermal.sink_models import (render_stack_with_sink, chip_area_m2_from_floorplan,
                                          SpreadingSink, external_r_for_spreading_total)
from HotGauge.thermal.die_stack import parse_spec_string, is_spec_string
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.stack_models import coarsen_stack_grid
from HotGauge.thermal.cooling_spec import (CoolingSpec, CoolingSpecSink, air_spec,
                                           solve_flow_for_peak, solve_flow_for_r_th,
                                           velocity_is_plausible, measure_package_resistance,
                                           external_r_for_total, base_area_from_footprint,
                                           COOLER_CLASSES)
from HotGauge.thermal.accelerator_floorplan import (ga100_geometry, ga100_floorplan,
                                                    ga100_block_powers, block_areas_mm2,
                                                    GA100_POWER_SPLIT, SM_SRAM_FRACTION,
                                                    tier_analysis_by_class)
from HotGauge.thermal.published_reference import (PUBLISHED_POINTS, all_thermal_points,
                                                  check_peak)

T_FLOOR_K = 273.15

#: Power splits to try when bisecting. 'measured' is the study's assumption; 'flat' spreads power
#: by AREA so every class has the same density, which removes the hotspot by construction and so
#: tells you how much of the peak the split is responsible for.
SPLIT_VARIANTS = ('assumed', 'flat')


def flat_split_by_area(classes, areas):
    """A split giving every block the same power density -- the null hypothesis for the hotspot.

    Returned in the key space ``ga100_block_powers`` expects: the two SM sub-blocks fold back into
    a single ``sm`` share, because that function re-splits them itself via ``datapath_fraction``.
    Pass ``datapath_fraction`` = the datapath's AREA fraction alongside this, or the tile
    concentration comes straight back in.
    """
    tot = sum(areas.get(b, 0.0) for b in classes)
    per_class = {}
    for b, c in classes.items():
        key = 'sm' if c in ('sm_dp', 'sm_l1') else c
        per_class[key] = per_class.get(key, 0.0) + areas.get(b, 0.0) / tot
    return per_class


def run_point(args, key, split_mode='assumed', leak_fraction=None, leak_by_class=False):
    """One coupled solve at a published operating point."""
    p = all_thermal_points()[key]
    leak_fraction = p and (leak_fraction if leak_fraction is not None else args.leak_fraction)

    out_dir = os.path.join(args.out_dir, '{}_{}'.format(key, split_mode))
    os.makedirs(out_dir, exist_ok=True)

    if p.get('floorplan', 'ga100') == 'ga100':
        g = ga100_geometry()
        flp, classes = ga100_floorplan(os.path.join(out_dir, 'ga100.flp'), split_sm=True, geom=g,
                                       cell_um=args.cell_um)
        areas = block_areas_mm2(flp)
        area_mm2 = g['w_die'] * g['h_die']
        is_cpu = False
    else:
        # A CPU point: use a shipped McPAT-derived floorplan and spread the published package
        # power over it by AREA. That is deliberately crude -- a real per-block map would come
        # from Sniper -- but this test is about whether a die of roughly this size at this power
        # under this cooler lands near the published temperature, not about the power map.
        flp = os.path.join(_REPO, 'examples', 'floorplans', 'outputs',
                           '{}_3D-ICE_template.flp'.format(p['floorplan']))
        if not os.path.isfile(flp):
            raise SystemExit('no floorplan at {}'.format(flp))
        fp = Floorplan.from_file(flp)
        areas = {e.name: (e.width * e.height) / 1.0e6 for e in fp.elements}
        area_mm2 = chip_area_m2_from_floorplan(flp) * 1e6
        classes = {n: 'cpu' for n in areas}
        is_cpu = True

    if is_cpu:
        tot = sum(areas.values())
        powers = {n: p['power_W'] * a / tot for n, a in areas.items()}
    else:
        split = dict(GA100_POWER_SPLIT)
        dp_frac = None
        if split_mode == 'flat':
            split = flat_split_by_area(classes, areas)
            # Power follows area inside the tile too, or the datapath concentration survives a
            # 'flat' split and the test does not test what it claims to.
            dp_frac = 1.0 - SM_SRAM_FRACTION
        kw_bp = {} if dp_frac is None else {'datapath_fraction': dp_frac}
        powers, pmeta = ga100_block_powers(p['power_W'], classes, split=split, **kw_bp)

    # Leakage reference. By class it tracks what actually leaks: logic does, I/O PHYs mostly
    # do not, and SRAM sits between. Uniform is the study's original assumption.
    LEAK_BY_CLASS = {'sm_dp': 1.0, 'sm_l1': 0.7, 'l2': 0.7, 'mem_ctrl': 0.5,
                     'hbm_phy': 0.15, 'nvlink': 0.15, 'pcie_misc': 0.5, 'sm': 1.0}
    if leak_by_class:
        leak_ref = {b: powers[b] * leak_fraction * LEAK_BY_CLASS.get(classes[b], 1.0)
                    for b in powers}
    else:
        leak_ref = {b: powers[b] * leak_fraction for b in powers}

    trace = BasicPowerTrace({u: np.array([v]) for u, v in powers.items()}, 1.0)

    spread = COOLER_CLASSES[p.get('cooler_class', 'cfd_reference')]

    # Two corrections the first attempt lacked, and together they are the whole difference.
    # 1. The published resistance is junction-to-ambient and ALREADY CONTAINS the package. 3D-ICE
    #    adds the package itself, so external cooling supplies only the remainder -- and on this
    #    die the package is more than half the budget.
    # 2. The sink is sized by COOLER CLASS. base_spread 1.85 is the CFD study's own small sink;
    #    using it everywhere demanded face velocities nobody builds.
    # Base geometry first: the probe below needs the same boundary the real solve will get, or
    # the resistance it subtracts is not the one 3D-ICE saw.
    base_mm2 = base_t_mm = base_k = series = None
    if args.spreading:
        if not is_spec_string(args.stack):
            raise SystemExit(
                '--spreading needs a generated stack so its base geometry is known, not the '
                'template {!r}. For a lidded reference part: --stack '
                'spec:package=lidded,sink_in_stack=0,package_in_boundary=1'.format(args.stack))
        spec_obj = parse_spec_string(args.stack)
        if spec_obj.boundary_base() is None:
            raise SystemExit(
                '--stack {!r} declares no boundary base to spread into. Add sink_in_stack=0, '
                'and package_in_boundary=1 on a lidded part.'.format(args.stack))
        base_mm2 = args.base_mm2 or base_area_from_footprint(area_mm2)
        base_t_mm, base_k = spec_obj.boundary_base()
        series = spec_obj.boundary_series_layers()

    def _wrap(sk):
        if not args.spreading:
            return sk
        return SpreadingSink(sk, area_mm2, base_area_mm2=base_mm2,
                             base_thickness_mm=base_t_mm, base_k_W_mK=base_k,
                             series_above_base=series, ambient_K=p['ambient_C'] + 273.15)

    r_pkg = args.package_r
    if r_pkg is None:
        probe = solve_flow_for_peak(p['fluid'], area_mm2, p['power_W'], p['temp_C'][1],
                                    inlet_C=p['ambient_C'], ambient_C=p['ambient_C'],
                                    base_spread=spread)
        probe_sink = _wrap(CoolingSpecSink(probe, p['power_W']))
        probe_stack = render_stack_with_sink(get_stack_template(args.stack), probe_sink,
                                             os.path.join(out_dir, 'probe.stk'))
        coarsen_stack_grid(probe_stack, args.cell_um)
        # The resistance measure_package_resistance subtracts must be the one the stack was
        # RENDERED with, or the remainder is not the package.
        probe_r = (probe_sink.total_resistance_K_per_W() if args.spreading
                   else probe_sink.r_th_K_per_W)
        _, r_pkg, _ = measure_package_resistance(
            probe_stack, flp, args.tech_node, area_mm2, probe_r,
            p['power_W'], p['ambient_C'] + 273.15, powers,
            session_cache=shared_cache(), run_dir=os.path.join(out_dir, 'pkg'))

    # What the boundary as a whole must deliver, once the stack has taken its share.
    r_boundary = external_r_for_total(p['implied_r_th_peak'], r_pkg)

    if args.spreading:
        # With the base in the boundary, the remainder is NOT the convective term alone: it also
        # contains the spreading into the base and whatever sits above it. Solving the cooler
        # directly against r_boundary would demand a cooler better than the target by exactly the
        # spreading resistance -- which is how you end up asking for a 0.0028 K/W cooler, a thing
        # that does not exist. Invert the boundary instead.
        r_ext = external_r_for_spreading_total(
            r_boundary, area_mm2, base_mm2, base_thickness_mm=base_t_mm,
            base_k_W_mK=base_k, series_above_base=series)
        if r_ext is None:
            raise SystemExit(
                'the spreading into a {:.0f} mm^2 base alone exceeds the {:.4f} K/W left after '
                'the stack on a {:.0f} mm^2 die -- no cooler reaches this point through this '
                'package. That is a real answer, not a tuning failure.'
                .format(base_mm2, r_boundary, area_mm2))
        # The cooler is sized over the BASE it is bolted to, not over the die.
        cooler_area_mm2 = base_mm2
    else:
        r_ext = r_boundary
        cooler_area_mm2 = area_mm2

    spec = solve_flow_for_r_th(p['fluid'], cooler_area_mm2, r_ext, inlet_C=p['ambient_C'],
                               ambient_C=p['ambient_C'], base_spread=spread)
    if spec is None:
        raise SystemExit(
            'no flow reaches {:.4f} K/W of EXTERNAL resistance on a {:.0f} mm^2 die with {} and a '
            '{} sink -- a real answer: this cooling class cannot hold the published temperature '
            'through this package.'.format(r_ext, area_mm2, p['fluid'], p.get('cooler_class')))
    if p['fluid'] == 'air':
        spec = air_spec(cooler_area_mm2, spec.flow_m3s, p['ambient_C'], ambient_C=p['ambient_C'],
                        base_spread=spread)
    sink = _wrap(CoolingSpecSink(spec, p['power_W'], r_package_K_per_W=r_pkg))

    stack = render_stack_with_sink(get_stack_template(args.stack),
                                   sink, os.path.join(out_dir, 'stack.stk'))
    coarsen_stack_grid(stack, args.cell_um)

    cal = os.path.join(_REPO, 'leakage_calibration', 'leakage_calibration.json')
    leak_model, t_ref = (load_calibrated_leakage_model(cal, extrapolate=True)
                         if os.path.isfile(cal) else (LeakageModel.exponential(15.0), 330.0))

    res = run_leakage_feedback(
        trace, leak_ref,
        ICEThermalSolver(stack, flp, args.tech_node, run_base_dir=os.path.join(out_dir, 'solve'),
                         initial_temp=p['ambient_C'] + 273.15, num_cores=1, single_thread=True,
                         mode='steady', session_cache=shared_cache(), already_dice_named=True),
        model=leak_model, T_ref=t_ref, num_cores=1, tol_K=args.tol, max_iter=args.max_iter,
        relax=args.relax, t_floor_K=T_FLOOR_K, bridge_aggregates=False,
        name_map=(lambda u: u), verify=True)

    diverged = bool(res.get('diverged'))
    peak_C = None
    tiers = None
    if not diverged and res.get('temp_trace'):
        temps = {b: float(np.ravel(v)[-1]) - 273.15 for b, v in res['temp_trace'].items()
                 if float(np.ravel(v)[-1]) > T_FLOOR_K and not b.startswith('__')}
        if temps:
            tiers = tier_analysis_by_class(temps, classes, 10.0)
            peak_C = tiers['peak_C']

    ok, verdict = check_peak(key, peak_C, diverged=diverged)
    return {'point': key, 'split_mode': split_mode, 'leak_fraction': leak_fraction,
            'stack': args.stack, 'spreading': bool(args.spreading),
            'base_mm2': (base_mm2 if args.spreading else None),
            'r_boundary_K_per_W': r_boundary,
            'r_package_K_per_W': r_pkg, 'r_external_K_per_W': r_ext,
            'cooler_class': p.get('cooler_class'),
            'leak_by_class': leak_by_class,
            # A SpreadingSink has no r_th_K_per_W on purpose -- exposing one would make it look
            # like a whole-cooler resistance to SpreadingSink's own duck-typed check, and a
            # wrapped wrapper would then skip its spreading term silently.
            'r_th_K_per_W': (sink.total_resistance_K_per_W() if args.spreading
                             else sink.r_th_K_per_W),
            'flow_m3s': spec.flow_m3s, 'wall_plug_W': spec.wall_plug_W(p['power_W']),
            'peak_C': peak_C, 'peak_class': (tiers or {}).get('peak_class'),
            'diverged': diverged, 'unconverged': bool(res.get('unconverged')),
            'ok': ok, 'verdict': verdict,
            'by_class': (tiers or {}).get('by_class')}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--point', default='H100_AIR', choices=sorted(all_thermal_points()))
    ap.add_argument('--package-r', type=float, default=None,
                    help='skip the calibration solve and use this package resistance [K/W]')
    ap.add_argument('--bisect', action='store_true',
                    help='on failure, walk the candidate causes')
    ap.add_argument('--leak-fraction', type=float, default=0.25)
    ap.add_argument('--cell-um', type=float, default=100.0)
    ap.add_argument('--stack', default='skylake',
                    help="stack template or spec: string. The gate's reference parts are LIDDED, "
                         "so the spreading form is "
                         "spec:package=lidded,sink_in_stack=0,package_in_boundary=1 -- see "
                         "--spreading. 'skylake' is the historical template every earlier gate "
                         "run used and is kept as the default so those reproduce.")
    ap.add_argument('--spreading', action='store_true',
                    help='fold the package spreading layers into the boundary with their real '
                         'overhang, instead of leaving them in the stack as columns the width of '
                         'the die. Requires a --stack spec with sink_in_stack=0 (and '
                         'package_in_boundary=1 on a lidded part).')
    ap.add_argument('--base-mm2', type=float, default=None,
                    help='spreading base footprint [mm^2]; default is the socket footprint')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--tol', type=float, default=0.05)
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--out-dir', default=os.path.join(os.getcwd(), 'validate_published'))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    # Absolute: the floorplan path is baked into the stack and re-resolved inside the solver,
    # which runs from a different working directory.
    args.out_dir = os.path.abspath(args.out_dir)
    os.makedirs(args.out_dir, exist_ok=True)

    p = all_thermal_points()[args.point]
    print('ACCEPTANCE TEST: {}'.format(p['label']))
    print('  source   : {}'.format(p['source']))
    print('  published: {:.0f} W, ambient {:.1f} C, observed {:.0f}-{:.0f} C under load'.format(
        p['power_W'], p['ambient_C'], p['temp_C'][0], p['temp_C'][1]))
    print('  implied junction-to-{} R_th at the top of the range: {:.4f} K/W'.format(
        'air' if p['fluid'] == 'air' else 'coolant', p['implied_r_th_peak']))
    print()

    runs = [run_point(args, args.point)]
    print('  baseline (study assumptions):')
    print('    R_th {:.4f} K/W, flow {:.4g} m^3/s, {:.1f} W at the wall'.format(
        runs[0]['r_th_K_per_W'], runs[0]['flow_m3s'], runs[0]['wall_plug_W']))
    print('    {}'.format(runs[0]['verdict']))

    if not runs[0]['ok'] and args.bisect:
        print('\n  bisecting the candidates:')
        for label, kw in (('flat power split (removes the hotspot by construction)',
                           dict(split_mode='flat')),
                          ('leakage weighted by class (I/O does not leak like logic)',
                           dict(leak_by_class=True)),
                          ('leakage fraction 0.10 instead of 0.25', dict(leak_fraction=0.10)),
                          ('flat split AND class-weighted leakage',
                           dict(split_mode='flat', leak_by_class=True))):
            r = run_point(args, args.point, **kw)
            runs.append(dict(r, label=label))
            print('    {:<58s} {}'.format(label[:58],
                                          'RUNAWAY' if r['diverged'] else
                                          '{:.1f} C  {}'.format(r['peak_C'],
                                                                'PASS' if r['ok'] else 'fail')))

    path = os.path.join(args.out_dir, 'validate_{}.json'.format(args.point))
    with open(path, 'w') as f:
        json.dump({'point': p, 'runs': runs}, f, indent=2, default=str)
    print('\n  wrote {}'.format(path))
    return 0 if runs[0]['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
