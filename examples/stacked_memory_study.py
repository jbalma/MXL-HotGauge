#!/usr/bin/env python
"""Design D: does stacking memory over logic move the binding constraint to where MR can act?

The question
------------
On a single logic die MR is a weak clock lever, and the reason is structural: the thermal peak
is a 15-block plateau of replicated units, so clipping it is bulk cooling in disguise
(``docs/CLOCK_HEADROOM.md``, ``docs/DESIGN_STUDY_PLAN.md``). Stacked memory changes the problem
rather than the amount:

* the memory's limit is **lower** than the logic's -- JEDEC's 85 C refresh breakpoint against a
  100 C spec point -- so the *system* may become memory-limited;
* the memory has its **own positive feedback** (hotter -> shorter retention -> more refresh ->
  hotter), independent of leakage and on a different structure;
* the memory hot zone is set by the logic underneath it, so there is no reason for it to be a
  degenerate plateau.

Two coupled fixed points
------------------------
The logic's leakage loop and the memory's refresh loop are coupled only through the shared
thermal solution, so this iterates them together: solve, rescale logic leakage AND memory
refresh power, re-solve. Both are damping-verified via ``run_leakage_feedback``; the memory side
is a straight outer iteration on top.

What it reports
---------------
Per layer: peak, which limit binds, and -- for the memory -- how many banks are past the refresh
breakpoint (expensive) versus past the hard limit (out of spec). Plus the tier structure of the
memory layer, which is the screening question: if the memory hot zone is a spike rather than a
plateau, MR has something to bite on that the logic die never offered.

**Nothing here is calibrated.** The DRAM parameters are JEDEC conventions, not datasheet
extractions (see ``HotGauge.power.dram``), so this answers "does the constraint move and is the
hot zone concentrated", not "how much memory power".

Usage
-----
    python examples/stacked_memory_study.py --cores 34 --density 1.00 --cfm 88
"""
import os
import sys
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace, LeakageModel
from HotGauge.configuration import load_block_powers
from HotGauge.thermal import get_stack_template, ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, replicate_trace_cores,
                                               load_calibrated_leakage_model,
                                               mcpat_tref_from_trace_dir, peak_temp_K)
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink,
                                          chip_area_m2_from_floorplan, SIMSCALE_T0_K)
from HotGauge.thermal.stack_models import (memory_stack_floorplans, memory_output_instructions,
                                           render_stacked_memory_template, split_layer_temps)
from HotGauge.power.dram import (stacked_dram_model, dram_block_powers, dram_limit_report,
                                 DEFAULT_REFRESH_BREAK_K, DEFAULT_DRAM_LIMIT_K)
from HotGauge.power.clock_search import emphasise_units
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0

# Output instructions come from stack_models.memory_output_instructions(): 3D-ICE reports
# nothing for a die without one, and a memory layer that is never read cannot be shown to be
# the binding constraint.


def tier_structure(temps_C, dt_max_K):
    """Plateau width and clip-one gain -- the MR-leverage screen, applied to one layer."""
    ranked = sorted(temps_C.items(), key=lambda kv: -kv[1])
    if not ranked:
        return None
    peak = ranked[0][1]
    floor = peak - dt_max_K
    nxt = ranked[1][1] if len(ranked) > 1 else floor
    return {'peak_C': peak, 'peak_block': ranked[0][0],
            'plateau_within_dt_max': sum(1 for _, t in ranked if t > floor),
            'clip_one_gain_K': peak - max(floor, nxt),
            'top': [{'block': b, 'T_C': t} for b, t in ranked[:8]]}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--density', type=float, default=1.00,
                    help='LOGIC die average power density [W/mm^2]')
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, default=None)
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    # --- memory ---
    # A single thin bonded die is the most FAVOURABLE memory geometry there is, and the first
    # run showed why that matters: the memory came out 28 K cooler than the logic and the logic
    # stayed the binding constraint. HIR 2023 ch.20 s.2.10 says the real difficulty is "large
    # stack thermal resistance" -- an 8-high stack, where seven more dies and seven more bond
    # layers sit between the hot die and the sink.
    ap.add_argument('--mem-dies', type=int, default=1,
                    help='memory dies in the stack (HBM is 2- to 8-high)')
    ap.add_argument('--mem-banks-x', type=int, default=4)
    ap.add_argument('--mem-banks-y', type=int, default=4)
    ap.add_argument('--mem-density', type=float, default=0.15,
                    help='memory-die power density at the refresh breakpoint [W/mm^2] '
                         '(ASSUMPTION -- see HotGauge.power.dram)')
    ap.add_argument('--mem-die-um', type=float, default=50.0)
    ap.add_argument('--bond-um', type=float, default=5.0)
    ap.add_argument('--dram-break-C', type=float, default=DEFAULT_REFRESH_BREAK_K - 273.15)
    ap.add_argument('--dram-limit-C', type=float, default=DEFAULT_DRAM_LIMIT_K - 273.15)
    ap.add_argument('--logic-limit-C', type=float, default=100.0)
    ap.add_argument('--mem-iter', type=int, default=8,
                    help='outer iterations coupling refresh power to temperature')
    ap.add_argument('--mem-tol-K', type=float, default=0.5)
    # --- design shape (composes with design G) ---
    ap.add_argument('--emphasise', default=None)
    ap.add_argument('--emphasis-factor', type=float, default=4.0)
    ap.add_argument('--dt-max', type=float, default=10.0)
    # --- solver ---
    ap.add_argument('--leakage-cal', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--no-verify', action='store_true')
    ap.add_argument('--verify-tol', type=float, default=1.0)
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'stacked_memory'))
    os.makedirs(args.out_dir, exist_ok=True)

    stem = 'skylake{}_{}core_3_3D-ICE_template.flp'.format(args.node, args.cores)
    flp = os.path.join(args.flp_dir, stem)
    if not os.path.isfile(flp):
        flp = os.path.join(args.flp_dir, stem.replace('_3_', '_0_'))
    area_m2 = chip_area_m2_from_floorplan(flp)
    area_mm2 = area_m2 * 1e6
    power_W = args.density * area_mm2

    # --- the stack: memory die above the logic die -------------------------------------
    mem_flps, mem_by_die, mem_blocks = memory_stack_floorplans(
        flp, args.out_dir, n_dies=args.mem_dies,
        n_x=args.mem_banks_x, n_y=args.mem_banks_y)
    mem_outputs = memory_output_instructions(args.mem_dies)
    stacked_template = render_stacked_memory_template(
        get_stack_template(args.stack), os.path.join(args.out_dir, 'stacked_template.stk'),
        mem_flps, mem_die_um=args.mem_die_um, bond_um=args.bond_um, n_dies=args.mem_dies)
    sink = (ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K)
            if args.r_th is not None
            else BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K))
    stack = render_stack_with_sink(stacked_template, sink,
                                   os.path.join(args.out_dir, 'stacked.stk'))

    # --- logic power -------------------------------------------------------------------
    leak_model, t_ref = (load_calibrated_leakage_model(args.leakage_cal, extrapolate=True)
                         if os.path.isfile(args.leakage_cal)
                         else (LeakageModel.exponential(15.0),
                               mcpat_tref_from_trace_dir(args.trace_dir) or 330.0))
    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    base = (replicate_trace_cores(base0, args.cores, n_src=args.trace_cores)
            if args.cores > args.trace_cores else base0)
    if args.emphasise:
        base = emphasise_units(base, args.emphasise, args.emphasis_factor)
    trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                               num_cores=args.cores)
    split = os.path.join(args.trace_dir, os.path.basename(files[0]).replace(
        'block_powers_', 'block_powers_split_'))
    leak_ref = {}
    if os.path.isfile(split):
        with open(split) as f:
            leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}

    dram = stacked_dram_model(area_mm2, density_W_per_mm2=args.mem_density)
    dram_break_K = args.dram_break_C + 273.15
    dram_limit_K = args.dram_limit_C + 273.15

    print('stacked memory over logic: {}-core {}, {:.1f} mm^2'.format(
        args.cores, args.node, area_mm2))
    print('  logic    : {:.3f} W/mm^2 ({:.1f} W), limit {:.0f} C'.format(
        args.density, power_W, args.logic_limit_C))
    print('  memory   : {} die(s) x {}x{} banks, {:.3g} W/mm^2 at the breakpoint, {:.0f} um '
          'die on {:.0f} um bond'.format(args.mem_dies, args.mem_banks_x, args.mem_banks_y,
                                         args.mem_density, args.mem_die_um, args.bond_um))
    print('  memory   : refresh breakpoint {:.0f} C, hard limit {:.0f} C  [{}]'.format(
        args.dram_break_C, args.dram_limit_C, 'UNCALIBRATED -- JEDEC conventions'))
    print('  cooling  : {}'.format('R_th {:.3g} K/W'.format(args.r_th) if args.r_th is not None
                                   else '{:.0f} CFM'.format(args.cfm)))
    if args.emphasise:
        print('  design   : {!r} x{:.2f} at constant core power'.format(
            args.emphasise, args.emphasis_factor))
    print()

    counter = {'n': 0}

    def solve_stacked(mem_powers):
        """One damping-verified logic solve with the memory power held at ``mem_powers``."""
        counter['n'] += 1
        # The persistent-session path cannot serve a two-die stack yet: it identifies blocks
        # positionally from ONE floorplan, and its own guard says so rather than mislabelling
        # them ("floorplan has 16 named elements but the server reports 1142"). The emulator
        # path reads names from each Tflp file, so nothing has to assume an ordering across
        # dies. It costs ~85 s a solve instead of ~0.6 s, which is affordable for a screen and
        # is the right trade against silently attributing memory power to logic blocks.
        solver = ICEThermalSolver(
            stack, flp, args.tech_node,
            run_base_dir=os.path.join(args.out_dir, 'it{:02d}'.format(counter['n'])),
            initial_temp=args.ambient_K, num_cores=args.cores, single_thread=True,
            mode='steady', session_cache=None,
            extra_die_outputs=mem_outputs)

        # The memory banks are extra blocks on the same solve. They carry their own power and
        # are not in the McPAT trace, so they are injected here rather than through the trace.
        def solve_with_memory(tr):
            merged = dict(tr.powers)
            for blk, p in mem_powers.items():
                merged[blk] = np.array([float(p)])
            return solver(BasicPowerTrace(merged, tr.time_step))

        return run_leakage_feedback(trace, leak_ref, solve_with_memory, model=leak_model,
                                    T_ref=t_ref, num_cores=args.cores, tol_K=args.tol,
                                    max_iter=args.max_iter, relax=args.relax,
                                    t_floor_K=T_FLOOR_K, bridge_aggregates=True,
                                    verify=not args.no_verify, verify_tol_K=args.verify_tol)

    # --- couple the two feedbacks ------------------------------------------------------
    mem_powers = dram_block_powers(mem_blocks, dram, None, default_T_K=dram_break_K)
    history, res = [], None
    for it in range(args.mem_iter):
        res = solve_stacked(mem_powers)
        if res.get('diverged'):
            print('  iteration {}: LOGIC RUNAWAY -- no steady state'.format(it))
            break
        temps = res['temp_trace']
        logic_t, mem_t = split_layer_temps(temps)
        mem_peak = peak_temp_K(mem_t, T_FLOOR_K)
        new_powers = dram_block_powers(mem_blocks, dram, mem_t, default_T_K=dram_break_K)
        delta = max(abs(new_powers[b] - mem_powers[b]) for b in mem_blocks)
        total = sum(new_powers.values())
        history.append({'iter': it, 'mem_peak_C': K_to_C(mem_peak) if mem_peak else None,
                        'mem_power_W': total, 'max_bank_delta_W': delta,
                        'logic_peak_C': K_to_C(peak_temp_K(logic_t, T_FLOOR_K))})
        print('  it{:>2d}: logic {:6.2f} C   memory {:6.2f} C   refresh power {:6.3f} W  '
              '(dP {:.4f})'.format(it, history[-1]['logic_peak_C'],
                                   history[-1]['mem_peak_C'], total, delta))
        mem_powers = new_powers
        if delta <= args.mem_tol_K * 0.01 * max(total, 1e-9) or delta < 1e-4:
            break

    out = {'cores': args.cores, 'node': args.node, 'area_mm2': area_mm2,
           'logic_density': args.density, 'logic_power_W': power_W,
           'mem_density': args.mem_density, 'mem_banks': len(mem_blocks),
           'mem_dies': args.mem_dies,
           'dram_break_C': args.dram_break_C, 'dram_limit_C': args.dram_limit_C,
           'logic_limit_C': args.logic_limit_C, 'calibrated': False,
           'emphasise': args.emphasise, 'history': history}

    if res is None or res.get('diverged'):
        out['diverged'] = True
        print('\n  no steady state for the stack at this operating point')
    elif res.get('unconverged'):
        out['unconverged'] = True
        print('\n  ** UNCONVERGED (peak spread {:.2f} K) -- not a result **'.format(
            res.get('peak_spread_K') or float('nan')))
    else:
        logic_t, mem_t = split_layer_temps(res['temp_trace'])
        logic_C = {k: K_to_C(float(np.ravel(v)[-1])) for k, v in logic_t.items()
                   if float(np.ravel(v)[-1]) > T_FLOOR_K}
        mem_C = {k: K_to_C(float(np.ravel(v)[-1])) for k, v in mem_t.items()
                 if float(np.ravel(v)[-1]) > T_FLOOR_K}
        rep = dram_limit_report(mem_t, limit_K=dram_limit_K, break_K=dram_break_K)
        logic_tiers, mem_tiers = tier_structure(logic_C, args.dt_max), tier_structure(mem_C,
                                                                                      args.dt_max)
        logic_peak, mem_peak = logic_tiers['peak_C'], mem_tiers['peak_C']
        # Which limit binds -- expressed as headroom, so the comparison is like-for-like.
        logic_margin = args.logic_limit_C - logic_peak
        mem_margin = args.dram_limit_C - mem_peak
        binds = 'MEMORY' if mem_margin < logic_margin else 'LOGIC'

        print('\n  layer     peak C    limit C   margin K   plateau   clip-one K   peak block')
        print('  logic    {:7.2f}   {:7.1f}   {:8.2f}   {:7d}   {:10.2f}   {}'.format(
            logic_peak, args.logic_limit_C, logic_margin,
            logic_tiers['plateau_within_dt_max'], logic_tiers['clip_one_gain_K'],
            logic_tiers['peak_block']))
        print('  memory   {:7.2f}   {:7.1f}   {:8.2f}   {:7d}   {:10.2f}   {}'.format(
            mem_peak, args.dram_limit_C, mem_margin,
            mem_tiers['plateau_within_dt_max'], mem_tiers['clip_one_gain_K'],
            mem_tiers['peak_block']))
        print('\n  BINDING CONSTRAINT: {}'.format(binds))
        print('  memory banks past the refresh breakpoint: {} of {}  (past the hard limit: {})'
              .format(rep['n_over_break'], len(mem_blocks), rep['n_over_limit']))
        print('\n  READ: the memory plateau is the screening number. A spike there means MR has '
              'something\n  to bite on that the logic die never offered; a plateau means the '
              'same problem moved up a layer.')
        out.update({'diverged': False, 'binding': binds,
                    'logic': logic_tiers, 'memory': mem_tiers, 'dram_report': rep,
                    'logic_margin_K': logic_margin, 'mem_margin_K': mem_margin})

    path = os.path.join(args.out_dir, 'stacked_memory.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)
    print('\n  written: {}'.format(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
