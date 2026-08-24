#!/usr/bin/env python
"""How hot the die runs as a function of how deep the transistors are buried.

Why this study exists
---------------------
Under direct-die cooling there is no lid and no die attach, so the only thing between the
transistors and the coolant is the silicon above them and the cooling tiles themselves. **How much
silicon that is becomes a design parameter**, and not one we control: it is set by how thin the
vendor is willing to grind the wafer, which is a manufacturing, warranty and reliability question
before it is a thermal one. This sweep produces the curve that conversation needs -- peak junction
temperature against burial depth, everything else held fixed.

It is also the curve that bounds the IP position. If the benefit is flat from 400 um down to
50 um, the scheme does not depend on aggressive thinning and can be claimed broadly. If it is
steep, the claim is tied to a thinning process, and that is a different negotiation.

What is swept and what is not
-----------------------------
Only the die geometry moves: ``source_depth_um``, and the die thickness with it so the silicon
below the active layer stays constant. The floorplan, the power, the leakage model, the cooling
and the grid are identical across points, so any difference in the answer is the burial depth.

Every point is a **new system matrix** -- the layer structure changes -- so none of them share a
factorisation. Budget roughly one factorisation per point; the session cache cannot help here and
does not pretend to.

Usage
-----
    python examples/burial_depth_sweep.py --out-dir results/burial \\
        --depths 360 240 120 60 20 --cores 34 --density 1.00
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

from HotGauge.configuration import load_block_powers
from HotGauge.thermal import ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.ICE import Floorplan, get_stack_template
from HotGauge.thermal.die_stack import StackSpec, write_stack, MR_PIXEL_MATERIALS
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, replicate_trace_cores,
                                               load_calibrated_leakage_model, die_power_of_trace,
                                               mcpat_tref_from_trace_dir)
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink,
                                          chip_area_m2_from_floorplan, SIMSCALE_T0_K)
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0

#: Depths worth asking about, coarse to aggressive. 360 um is the historical stack, which is
#: also roughly an unthinned die; 20 um is about as thin as anyone claims to grind.
DEFAULT_DEPTHS = (360.0, 240.0, 160.0, 100.0, 60.0, 30.0)

#: Silicon left below the active layer. Held constant so the sweep isolates the path UP to the
#: coolant rather than confounding it with how much bulk sits underneath.
BELOW_UM = 20.0


def build_stack(depth_um, args, out_dir):
    """One stack per burial depth, written where the run can be inspected afterwards."""
    spec = StackSpec(package=args.package,
                     die_um=depth_um + args.active_um + BELOW_UM,
                     source_depth_um=depth_um,
                     source_um=args.active_um,
                     mr_layer=(args.mr_material is not None and args.package == 'direct_die'),
                     mr_material=args.mr_material or 'GAAS',
                     mr_um=args.mr_um,
                     cell_um=args.cell_um)
    path = write_stack(spec, os.path.join(out_dir, 'stack_d{:.0f}.stk'.format(depth_um)))
    return spec, path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out-dir', default=os.path.join(_REPO, 'results', 'burial'))
    ap.add_argument('--depths', type=float, nargs='+', default=list(DEFAULT_DEPTHS),
                    help='burial depths to sweep [um], measured from the exposed die surface '
                         'down to the top of the active layer')
    ap.add_argument('--package', default='direct_die', choices=('direct_die', 'lidded'),
                    help='lidded is available as a control: burial depth should matter far less '
                         'when 3.2 mm of package sits above the silicon anyway')
    ap.add_argument('--mr-material', default='GAAS',
                    choices=list(MR_PIXEL_MATERIALS) + [None],
                    help='bulk material of the photonic pixel layer; omit for a bare TIM')
    ap.add_argument('--no-mr-layer', dest='mr_material', action='store_const', const=None)
    ap.add_argument('--mr-um', type=float, default=30.0)
    ap.add_argument('--active-um', type=float, default=20.0,
                    help='thickness of the active layer itself')
    ap.add_argument('--cell-um', type=float, default=50.0)
    # Everything below is the operating point, held fixed across the sweep.
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--flp', default=None)
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--density', type=float, default=1.00)
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, default=None)
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    ap.add_argument('--tol', type=float, default=0.05)
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.25)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    flp_path = args.flp or os.path.join(
        args.flp_dir, 'skylake{}_{}core_3_3D-ICE_template.flp'.format(args.node, args.cores))
    flp = Floorplan.from_file(flp_path)
    area_m2 = chip_area_m2_from_floorplan(flp)
    power_W = args.density * area_m2 * 1e6

    files = sorted(f for f in os.listdir(args.trace_dir) if f.startswith('block_powers_'))
    if not files:
        raise SystemExit('no block_powers_* in {}'.format(args.trace_dir))
    base = load_block_powers(os.path.join(args.trace_dir, files[0]))
    base = replicate_trace_cores(base, args.trace_cores, args.cores)
    trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                               num_cores=args.cores)
    actual_W = die_power_of_trace(trace, flp, args.tech_node, num_cores=args.cores)

    split = os.path.join(args.trace_dir,
                         os.path.basename(files[0]).replace('block_powers_',
                                                            'block_powers_split_'))
    leak_ref = {}
    if os.path.isfile(split):
        with open(split) as f:
            leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}
    if not leak_ref:
        # The leakage feedback is what makes this a coupled problem rather than a linear solve,
        # and a silently inert feedback has already cost this project 43 studies.
        raise SystemExit('no leakage split alongside {} -- refusing to run with the feedback '
                         'inert'.format(files[0]))
    leak_model = load_calibrated_leakage_model(args.node)
    t_ref = mcpat_tref_from_trace_dir(args.trace_dir)

    sink = (ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K)
            if args.r_th is not None
            else BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K))

    print('burial-depth sweep: {}-core {} at {:.3f} W/mm^2 ({:.1f} W), {} package, {}'
          .format(args.cores, args.node, actual_W / (area_m2 * 1e6), actual_W, args.package,
                  'R_th {:.3g} K/W'.format(args.r_th) if args.r_th is not None
                  else '{:.0f} CFM'.format(args.cfm)))
    print('  pixel layer: {}'.format(
        '{} um of {}'.format(args.mr_um, args.mr_material) if args.mr_material else 'none (TIM)'))
    print('  each depth is a NEW system matrix, so none of them share a factorisation\n')
    print('  {:>7s} {:>9s} {:>10s} {:>9s} {:>10s} {:>8s}'
          .format('depth', 'path um', 'lumped R', 'peak C', 'vs 360um', 'status'))

    rows, ref_peak = [], None
    for depth in args.depths:
        t0 = time.time()
        spec, base_stack = build_stack(depth, args, args.out_dir)
        stack = render_stack_with_sink(base_stack, sink,
                                       os.path.join(args.out_dir,
                                                    'solve_d{:.0f}.stk'.format(depth)))
        solver = ICEThermalSolver(stack, flp_path, args.tech_node,
                                  run_base_dir=os.path.join(args.out_dir,
                                                            'solve_d{:.0f}'.format(depth)),
                                  initial_temp=args.ambient_K, num_cores=args.cores,
                                  single_thread=True, mode='steady')
        res = run_leakage_feedback(trace, leak_ref, solver, model=leak_model, T_ref=t_ref,
                                   num_cores=args.cores, tol_K=args.tol, max_iter=args.max_iter,
                                   relax=args.relax, t_floor_K=T_FLOOR_K, bridge_aggregates=True)
        lumped = spec.resistance_budget(area_m2 * 1e6)['total_K_per_W']
        path_um = spec.path_to_coolant_um()['total_um']
        status = ('RUNAWAY' if res.get('diverged') else
                  'UNCONVERGED' if res.get('unconverged') else 'ok')
        peak = res.get('peak_C')
        if status == 'ok' and ref_peak is None:
            ref_peak = peak
        rows.append({'depth_um': depth, 'path_to_coolant_um': path_um,
                     'lumped_R_K_per_W': lumped, 'peak_C': peak, 'status': status,
                     'diverged': bool(res.get('diverged')),
                     'unconverged': bool(res.get('unconverged')),
                     'peak_block': res.get('peak_block'),
                     'peak_spread_K': res.get('peak_spread_K'),
                     'relax_final': res.get('relax_final'),
                     'p_chip_W': res.get('p_chip_W'), 'seconds': time.time() - t0})
        print('  {:>7.0f} {:>9.0f} {:>10.5f} {:>9s} {:>10s} {:>8s}'
              .format(depth, path_um, lumped,
                      '{:.2f}'.format(peak) if peak is not None else '--',
                      '{:+.2f} K'.format(peak - ref_peak)
                      if (peak is not None and ref_peak is not None) else '--',
                      status))

    out = {'note': 'peak junction temperature against how deep the active layer is buried, '
                   'under direct-die cooling. Only the die geometry changes between points.',
           'driver': 'examples/burial_depth_sweep.py',
           'package': args.package, 'mr_material': args.mr_material, 'mr_um': args.mr_um,
           'cores': args.cores, 'node': args.node, 'density': args.density,
           'die_power_W': actual_W, 'die_area_mm2': area_m2 * 1e6,
           'cfm': args.cfm, 'r_th': args.r_th, 'cell_um': args.cell_um,
           'below_um': BELOW_UM, 'active_um': args.active_um, 'rows': rows}
    path = os.path.join(args.out_dir, 'burial_depth.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(path))

    ok = [r for r in rows if r['status'] == 'ok']
    if len(ok) >= 2:
        span = max(r['peak_C'] for r in ok) - min(r['peak_C'] for r in ok)
        deep, thin = max(ok, key=lambda r: r['depth_um']), min(ok, key=lambda r: r['depth_um'])
        print('  {:.0f} um -> {:.0f} um of burial is worth {:.2f} K of peak temperature'
              .format(deep['depth_um'], thin['depth_um'], deep['peak_C'] - thin['peak_C']))
        print('  full span across the swept depths: {:.2f} K'.format(span))
    return 0


if __name__ == '__main__':
    sys.exit(main())
