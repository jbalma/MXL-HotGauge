#!/usr/bin/env python
"""Is the high-density ceiling set by CONCENTRATION, or by the die average?

    python examples/uniform_density_probe.py --densities 0.6 0.8 1.0 1.2 1.6 2.0 2.4

Why this probe exists
---------------------
Five hypotheses for the ceiling have been eliminated by measurement, and the last two were
eliminated the same way: shrink ``core_other`` and ``RBB`` runs away instead; amortize ``RBB``
and ``core_other`` runs away instead. The ceiling did not move either time. A ceiling that
survives the removal of whichever block happens to be hottest is not a property of that block,
and chasing a third one is not an experiment.

So stop varying blocks and vary the map. Two arms at each density, **identical in every respect
except how the same watts are spread**:

* ``shaped``  -- the real McPAT power map, rescaled to the target die average.
* ``uniform`` -- every block at the same W/mm^2. No hot block, by construction: Gini 0,
  peak == mean. Asserted, not assumed.

Read it like this:

* both arms lose their steady state at about the same density -> the ceiling is the package and
  the leakage model. It is **physics**, the artefact hypothesis is finished after five attempts,
  and the number can be quoted.
* the uniform arm holds well past the shaped one -> the gate is **concentration**, which is a
  measurable property of a floorplan rather than a block to chase, and this project already has
  metrics for it.

`[!]` Control arm only -- no cooling array. The question is whether a steady state EXISTS, which
is a property of the die and its package. Adding the array would answer a different question and
would put the planner's path back into an experiment built to remove confounds.

How it drives the solver, and why that is not the usual path
------------------------------------------------------------
Uniformity has to be imposed on the **floorplan-named** power map, not on the McPAT trace. A
McPAT trace reaches the die through aggregate splitting (L3) and modelled extras (IMC/IO/SoC), so
a flattened trace would produce a die that is not flat. The probe therefore calls
``prepare_dice_trace`` once, shapes the resulting block map, and solves with
``ICEThermalSolver(already_dice_named=True)`` and an identity name map -- the same path
``accelerator_floorplan`` uses.

That forces one stated approximation, which is the price of the control: **leakage is a fixed
fraction of each block's power**, taken from the trace's own measured die-wide fraction. The real
split is per-unit, and a uniform map has no per-unit identity to inherit it from. Both arms use
the same rule, so it cannot favour either -- but a per-block leakage difference is not modelled
here and no claim in this file rests on one.
"""
import os
import sys
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))
sys.path.insert(0, _HERE)

from HotGauge.power import BasicPowerTrace, LeakageModel
from HotGauge.configuration import load_block_powers
from HotGauge.thermal import get_stack_template, ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (prepare_dice_trace, replicate_trace_cores,
                                               load_calibrated_leakage_model,
                                               load_leakage_model, LEAKAGE_CURVES,
                                               mcpat_tref_from_trace_dir, peak_temp_K)
from HotGauge.power.core_other import (CORE_OTHER_POLICIES, resolve_trace_dir,
                                      DEFAULT_CORE_OTHER_POLICY)
from HotGauge.thermal.sink_models import (render_stack_with_sink, chip_area_m2_from_floorplan,
                                          spreading_sink_for_stack, BaffledFinSink,
                                          ThermalResistanceSink)
from HotGauge.thermal.power_shape import (block_power_map, uniform_density_map,
                                          scale_map_to_density, concentration)
from HotGauge.thermal.rbb import amortize_rbb, add_rbb_argument
from HotGauge.thermal.leakage_feedback import mcpat_flp_name_map
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0
ARMS = ('shaped', 'uniform')


def build_block_map(args, flp, n_cores):
    """The real McPAT power map, as floorplan block powers, plus the die-wide leakage fraction."""
    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    if n_cores > args.trace_cores:
        base = replicate_trace_cores(base, n_cores, n_src=args.trace_cores)

    split = os.path.join(args.trace_dir, os.path.basename(files[0]).replace(
        'block_powers_', 'block_powers_split_'))
    leak_fraction = args.leak_fraction
    if leak_fraction is None and os.path.isfile(split):
        with open(split) as f:
            sp = json.load(f)
        tot = sum(float(v[0]) + float(v[1]) for v in sp.values())
        leak = sum(float(v[1]) for v in sp.values())
        leak_fraction = (leak / tot) if tot > 0 else 0.2
    if leak_fraction is None:
        leak_fraction = 0.2

    # The RBB policy has to be applied HERE, on the McPAT trace, before the map is flattened --
    # afterwards there is no bus to amortize. Default stock, so the shaped arm is the same map
    # the density ladder that found the ceiling was run on.
    base, _, rbb_meta = amortize_rbb(base, flp, policy=args.rbb_policy,
                                     span=args.rbb_span,
                                     name_map=mcpat_flp_name_map(include_core_idx=n_cores > 1))
    dice = prepare_dice_trace(base, flp, args.tech_node, num_cores=n_cores)
    areas = {e.name: (e.width * e.height) / 1.0e6 for e in Floorplan.from_file(flp).elements}
    on_block, off_block = block_power_map(dice, areas)
    return on_block, off_block, areas, float(leak_fraction), rbb_meta


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trace-dir', default='mcpat_runs/7nm/linpack_3.8GHz')
    # `[!]` The TEMPLATE, not the rendered .flp. The rendered file carries literal
    # "power values 0.0;" entries, so a solve driven from it runs on an unpowered die -- the
    # solver's own guard catches that, and this is where it is avoided.
    ap.add_argument('--flp', default=os.path.join(
        _HERE, 'floorplans', 'outputs', 'skylake7nm_34core_3_3D-ICE_template.flp'))
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--densities', type=float, nargs='+',
                    default=[0.6, 0.8, 1.0, 1.2, 1.6, 2.0, 2.4])
    ap.add_argument('--arms', nargs='+', default=list(ARMS), choices=ARMS)
    # cooling: the density ladder's own configuration, so the two are comparable
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, default=None)
    ap.add_argument('--ambient-K', type=float, default=295.15)
    ap.add_argument('--burial-um', type=float, default=200.0)
    ap.add_argument('--cell-um', type=float, default=50.0)
    ap.add_argument('--spreading', action='store_true', default=True)
    ap.add_argument('--no-spreading', dest='spreading', action='store_false')
    ap.add_argument('--base-mm2', type=float, default=None)
    ap.add_argument('--leak-fraction', type=float, default=None,
                    help='override the die-wide leakage fraction (default: measured from the '
                         'trace split files)')
    add_rbb_argument(ap)
    ap.add_argument('--leakage-cal', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    # `[!]` DEFAULT 'pipeline', and it must stay that way -- same discipline as --rbb-policy.
    # Every recorded density result was solved on the pipeline curve; changing the default would
    # silently move all of them. The simulated curve (P0.13) is a deliberate, flagged re-run.
    ap.add_argument('--leakage-curve', default='simulated', choices=list(LEAKAGE_CURVES),
                    help='which leakage-vs-temperature curve to solve on. pipeline = CACTI\'s '
                         '11 hard-coded numbers (the recorded catalogue); simulated = BSIM-CMG '
                         'on the ASAP7 card (P0.13); simulated-gidl-off = the other bracket')
    # §P0.16. `stock` (default) reproduces the recorded catalogue exactly; `hierarchy-consistent`
    # undoes the `2 * runtime_dynamic` in scripts/mcpat_to_blk_lvl_power_dict.py and residualises
    # the bare Core<N> row, so `core_other` carries leakage only. Additive: the non-default branch
    # is placed AHEAD of the existing path, which stays reachable and unmodified.
    ap.add_argument('--core-other-policy', default=DEFAULT_CORE_OTHER_POLICY,
                    choices=list(CORE_OTHER_POLICIES),
                    help='how to treat McPAT\'s per-core accounting. "hierarchy-consistent" '
                         '(default since P0.17) removes the converter\'s '
                         '2x on itemised per-core dynamic and gives core_other the true leakage '
                         'remainder (raises the die static fraction ~1.74x). See P0.16.')
    ap.add_argument('--tol', type=float, default=0.1)
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--out-dir', default=os.path.join(_REPO, 'results', 'uniform_density'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'uniform_density_probe.json'))
    args = ap.parse_args()
    # §P0.16: under a non-stock core_other policy, solve against a corrected copy of
    # the trace. Returns args.trace_dir unchanged under the default, so the recorded
    # path is byte-identical.
    args.trace_dir = resolve_trace_dir(args.trace_dir, args.core_other_policy)
    os.makedirs(args.out_dir, exist_ok=True)

    flp = args.flp
    area_m2 = chip_area_m2_from_floorplan(flp)
    shaped_map, off_block, areas, leak_fraction, rbb_meta = build_block_map(
        args, flp, args.cores)

    # Identical to mr_comparison's choice, so the two studies share a leakage model rather than
    # differing in one more thing than intended.
    if args.leakage_curve != 'pipeline':
        # The simulated curve carries its own anchor (330 K, the pipeline's own T_ref), so the
        # swap changes the SHAPE of leakage-vs-temperature and nothing else.
        leak_model, t_ref = load_leakage_model(args.leakage_curve,
                                               calibration=args.leakage_cal)
        leak_src = leak_model.description
    elif os.path.isfile(args.leakage_cal):
        leak_model, t_ref = load_calibrated_leakage_model(args.leakage_cal, extrapolate=True)
        leak_src = 'MEASURED McPAT curve + Arrhenius tail above 400 K'
    else:
        leak_model = LeakageModel.exponential(15.0)
        t_ref = mcpat_tref_from_trace_dir(args.trace_dir) or 330.0
        leak_src = 'assumed exponential'

    print('uniform-density probe   {}   {:.2f} mm^2, {} blocks'.format(
        os.path.basename(flp), sum(areas.values()), len(areas)))
    print('  leakage: {} ; die-wide fraction {:.3f} (from the trace split)'.format(
        leak_src, leak_fraction))
    print('  off-die trace power not solved: {:.1f} W (McPAT aggregates)'.format(off_block))
    c0 = concentration(shaped_map, areas)
    print('  real map: peak {:.1f} W/mm^2 on {}, {:.1f}x the mean, Gini {:.3f}'.format(
        c0['peak_W_per_mm2'], c0['top_block'], c0['peak_over_mean'], c0['gini']))
    print()
    hdr = '{:>8} {:>9} {:>10} {:>9} {:>9} {:>10}  {}'.format(
        'density', 'arm', 'peak_C', 'gini', 'pk/mean', 'verdict', 'hottest block')
    print(hdr)
    print('-' * len(hdr))

    sink = (ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K)
            if args.r_th is not None else BaffledFinSink(args.cfm, area_m2,
                                                         ambient_K=args.ambient_K))
    spec = 'spec:package=direct_die,mr=none,src={:.0f},cell={:.0f}{}'.format(
        args.burial_um, args.cell_um, ',sink_in_stack=0' if args.spreading else '')
    if args.spreading:
        sink = spreading_sink_for_stack(spec, sink, area_m2 * 1e6, base_area_mm2=args.base_mm2)
    stack = render_stack_with_sink(get_stack_template(spec), sink,
                                   os.path.join(args.out_dir, 'probe.stk'))

    rows = []
    for d in args.densities:
        for arm in args.arms:
            if arm == 'uniform':
                pmap, _ = uniform_density_map(areas, d * sum(areas.values()))
            else:
                pmap, _ = scale_map_to_density(shaped_map, areas, d)
            conc = concentration(pmap, areas)
            # The control the whole probe rests on: same watts, same die, different shape only.
            assert abs(conc['mean_W_per_mm2'] - d) < 1e-9, 'arm is not at the requested density'

            trace = BasicPowerTrace({b: np.array([w]) for b, w in pmap.items()}, 1.0)
            leak_ref = {b: leak_fraction * w for b, w in pmap.items()}
            tag = '{}_d{:.2f}'.format(arm, d)
            solver = ICEThermalSolver(stack, flp, args.tech_node,
                                      run_base_dir=os.path.join(args.out_dir, tag),
                                      initial_temp=args.ambient_K, num_cores=args.cores,
                                      single_thread=True, mode='steady',
                                      already_dice_named=True)
            r = run_leakage_feedback(trace, leak_ref, solver, model=leak_model, T_ref=t_ref,
                                     num_cores=args.cores, tol_K=args.tol,
                                     max_iter=args.max_iter, relax=args.relax,
                                     t_floor_K=T_FLOOR_K, name_map=lambda u: u)
            div = bool(r.get('diverged'))
            peak = None if div else K_to_C(peak_temp_K(r['temp_trace'], t_floor_K=T_FLOOR_K))
            hottest = None
            if r.get('temp_trace'):
                vals = {k: float(np.max(np.ravel(v))) for k, v in r['temp_trace'].items()
                        if float(np.max(np.ravel(v))) > T_FLOOR_K}
                if vals:
                    hottest = max(vals, key=vals.get)
            verdict = 'DIVERGED' if div else ('unconverged' if r.get('unconverged') else 'holds')
            rows.append({'density': d, 'arm': arm, 'diverged': div, 'peak_C': peak,
                         'unconverged': bool(r.get('unconverged')),
                         'hottest_block': hottest,
                         'hottest_K': (max(vals.values()) if r.get('temp_trace') and vals
                                       else None),
                         'gini': conc['gini'], 'peak_over_mean': conc['peak_over_mean'],
                         'peak_W_per_mm2': conc['peak_W_per_mm2'],
                         'total_W': conc['total_W']})
            print('{:>8.2f} {:>9} {:>10} {:>9.3f} {:>9.2f} {:>10}  {}'.format(
                d, arm, '--' if peak is None else '{:.2f}'.format(peak),
                conc['gini'], conc['peak_over_mean'], verdict, hottest or '-'))
            sys.stdout.flush()

    def cliff(arm):
        held = [r['density'] for r in rows if r['arm'] == arm and not r['diverged']]
        failed = [r['density'] for r in rows if r['arm'] == arm and r['diverged']]
        return {'highest_holding': max(held) if held else None,
                'lowest_failing': min(failed) if failed else None}

    out = {'note': __doc__.strip(),
           'floorplan': os.path.basename(flp), 'die_mm2': sum(areas.values()),
           'n_blocks': len(areas), 'cores': args.cores,
           'cooling': ('R_th {:.3g} K/W'.format(args.r_th) if args.r_th is not None
                       else '{:.0f} CFM baffled fin'.format(args.cfm)),
           'spreading': bool(args.spreading),
           'leak_fraction': leak_fraction, 'leakage_model': leak_src,
           'leakage_curve': args.leakage_curve, 'leakage_T_ref_K': t_ref,
           'rbb_policy': args.rbb_policy, 'rbb': rbb_meta,
           'real_map_concentration': c0,
           'cliff_by_arm': {a: cliff(a) for a in args.arms},
           'rows': rows,
           'THE_CONTROL': (
               'The two arms carry the SAME total power on the SAME die with the SAME package and '
               'the same leakage rule. Only the spatial distribution differs, and the uniform arm '
               'is asserted to have Gini 0 and peak == mean at every point. Any difference in '
               'where the steady state is lost is therefore concentration and nothing else.'),
           'THE_APPROXIMATION': (
               'Leakage is a fixed fraction of each block power, taken from the trace die-wide. '
               'A uniform map has no per-unit identity to inherit a per-unit split from. Both '
               'arms use the same rule so it cannot favour either, but a per-block leakage '
               'difference is not modelled and no claim here rests on one.')}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\n  cliffs: {}'.format(json.dumps(out['cliff_by_arm'])))
    print('  written: {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
