#!/usr/bin/env python
"""MR vs no-MR on each generated floorplan, at matched power density.

Why matched density rather than matched power
---------------------------------------------
Die-average power density is the quantity that determines whether a die is thermally
comfortable; total watts is not. Running 34-, 70- and 128-core dies all at 200 W would compare
2.0 W/mm^2 against 0.58 W/mm^2 and tell us mostly about die area. Holding density fixed asks
the question that matters: **does photonic MR help more or less as you scale core count at
constant density?**

What MR can actually reach
--------------------------
Set by ``--spot-min-um`` (default 10 um) and ``--spot-policy``. The realistic pixel pitch for a
cooling tile array is 1-10 um, not the 100 um this study originally assumed: at 100 um only 20 of
57 above-target blocks on the 34-core die are addressable, at 10 um it is 44, and at 1 um all of
them. Spot size is therefore *not* the binding constraint -- the block selection policy is, since
blocks above a 92 C target carry only ~10% of die power while 65% sits 10-20 K below it.

``--spot-policy`` decides what happens to a block narrower than the pitch: ``dilute`` (default)
illuminates the whole pixel and bills the laser for it, ``exclude`` refuses it, ``ideal`` cools it
free. Everything before this option existed behaved as ``ideal``, so older results are an upper
bound on MR.

Reported per floorplan
----------------------
Peak temperature, converged die power, clock, throughput, and the cooling power each option
costs. ``dT`` and ``d perf`` are the MR deltas, which is the number the whole exercise is for.

Usage
-----
    python examples/mr_comparison.py --cores 34 70 128 --density 0.575 --cfm 88
"""
import os
import sys
import math
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace, LeakageModel
from HotGauge.configuration import load_block_powers
from HotGauge.thermal import get_stack_template, ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.rbb import amortize_rbb, add_rbb_argument
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, die_power_of_trace,
                                               mcpat_flp_name_map, replicate_trace_cores,
                                               load_calibrated_leakage_model,
                                               load_leakage_model, LEAKAGE_CURVES,
                                               rebalance_trace_by_block_area,
                                               mcpat_tref_from_trace_dir)
from HotGauge.power.core_other import (CORE_OTHER_POLICIES, resolve_trace_dir,
                                      DEFAULT_CORE_OTHER_POLICY)
from HotGauge.thermal.die_stack import DEFAULT_DIRECT_SOURCE_DEPTH_UM
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink, spreading_sink_for_stack,
                                          chip_area_m2_from_floorplan, simscale_fan_power,
                                          SIMSCALE_T0_K)
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, mr_accounting,
                                                 zone_report,
                                                 DEFAULT_SPOT_MIN_UM,
                                                 DEFAULT_SPOT_POLICY,
                                                 DEFAULT_H_MAX_W_PER_MM2, DEFAULT_DT_MAX_K, DEFAULT_ETA_ASF, DEFAULT_LASER_WALLPLUG, DEFAULT_LPC_EFFICIENCY)
from HotGauge.thermal.ice_server import ICESessionCache
from HotGauge.thermal.leakage_ledger import leakage_ledger
from HotGauge.thermal.leakage_feedback import aggregate_aware_name_map
from HotGauge.thermal.mr_array import (ArrayWiring, wiring_for_stack, DEFAULT_PITCH_UM,
                                       device_pitch_range_um, DEFAULT_COVERAGE)
from HotGauge.thermal.extractor import (make_extractor, EXTRACTORS, DualZoneExtractor, ZONE_MODES,
                                        DEFAULT_ZONE_MODE, DEFAULT_COLD_ZONE_PATTERN,
                                        DEFAULT_COLD_EXTRACTOR)
from HotGauge.power.clock_search import (scale_cores, single_core_turbo,
                                         mixed_utilisation, emphasise_units)
from HotGauge.thermal.floorplan_metrics import relative_plateau, peak_to_runner_up_gap
from HotGauge.power.process_nodes import NODES, describe_assumptions, TRACE_REFERENCE_GHZ
from HotGauge.power.performance_model import FMaxModel, performance_summary
from HotGauge.thermal.utils import K_to_C
from HotGauge.thermal.arm_consistency import check_arm_consistency

T_FLOOR_K = 200.0
DEFAULT_FLOPS_PER_CYCLE = 32.0


def floorplan_path(flp_dir, node, n):
    stem = 'skylake{}_{}core_3_3D-ICE_template.flp'.format(node, n)
    p = os.path.join(flp_dir, stem)
    if os.path.isfile(p):
        return p
    return os.path.join(flp_dir, stem.replace('_3_', '_0_'))


def make_sink(args, area_m2):
    """The cooling solution for this point.

    Two ways to specify it, and they answer different questions:

    * ``--cfm`` -> ``BaffledFinSink``: the SimScale server air stack, whose resistance and fan
      power are both measured/fitted. Use it to ask "does this part work on air".
    * ``--r-th`` -> ``ThermalResistanceSink``: a bare thermal resistance in K/W, which is how
      cold plates and liquid loops are specified on datasheets. Use it to ask "how good does
      the cooling have to BE", which is the question once air has been shown to fail. Its
      parasitic power is not modelled (pump/chiller power is not in this model), so perf/W
      from an ``--r-th`` run counts compute + MR power only and is an upper bound.
    """
    if args.r_th is not None:
        return ThermalResistanceSink(args.r_th, area_m2, ambient_K=args.ambient_K,
                                     label='R_th {:.3g} K/W'.format(args.r_th))
    return BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K)


#: The three arms. See docs/EXECUTION_PLAN.md 6a for why two is not enough once the array is a
#: real die layer: comparing against a grease stack credits the laser with the GaAs-versus-grease
#: conductivity gain, and comparing against the unpowered array discards it. Three separates them.
ARMS = ('control', 'array_idle', 'array_on')


def arm_stack_spec(args, arm):
    """Stack spec string for one arm. ``control`` keeps the 30 um grease; the array arms
    replace exactly that layer and change nothing else."""
    if args.stack != 'auto':
        return args.stack
    # Under --no-array every arm gets the control stack: the legacy placement subtracts the plan
    # from the processor trace, so there IS no array die, and rendering one nothing fills would
    # fail in ICESteadySim rather than here.
    mr = 'none' if (arm == 'control' or args.no_array) else args.mr_material
    # Under --spreading the cold-plate slab comes OUT of the stack; SpreadingSink puts it back
    # in the boundary with its real overhang. Both arms lose it, so the arms still differ by
    # exactly the 30 um layer.
    sink_term = ',sink_in_stack=0' if args.spreading else ''
    # X4 (§P0.27.4): the gen-3 storage die above the processor die, in EVERY arm -- the stack is
    # the design, the arms differ by the 30 um layer above it exactly as before.
    gen3 = (',storage={:g},bond={:g},bondk={:g}'.format(args.storage_um, args.bond_um, args.bond_k)
            if getattr(args, 'gen3_split', None) else '')
    return 'spec:package=direct_die,mr={},src={:.0f},cell={:.0f}{}{}'.format(
        mr, args.burial_um, args.cell_um, sink_term, gen3)


def evaluate(args, flp, trace, leak_ref, geom, name_map, leak_model, t_ref, fmax,
             area_m2, n_cores, arm, tag, target_C=None):
    """One (floorplan, arm) point.

    ``target_C`` overrides ``args.mr_target_C`` for this point only. It is how
    ``--mr-target-offset-K`` works: the target is derived from the CONTROL arm's own measured
    peak rather than stated as an absolute temperature. See the flag's help for why that
    matters.
    """
    if target_C is None:
        target_C = args.mr_target_C
    use_mr = (arm == 'array_on')
    stack_spec = arm_stack_spec(args, arm)
    sink = make_sink(args, area_m2)
    if args.spreading:
        # Identical in every arm: the base is above the 30 um layer, so it cannot be part of
        # what separates them.
        sink = spreading_sink_for_stack(stack_spec, sink, area_m2 * 1e6,
                                        base_area_mm2=args.base_mm2)
    stack = render_stack_with_sink(get_stack_template(stack_spec), sink,
                                   os.path.join(args.out_dir, 'stacks', tag + '.stk'))
    counter = {'n': 0}

    # The cooling array, when this arm has one. ArrayWiring owns the tile grid, the tile
    # floorplan on disk, and the plan that moves between solves -- see its docstring for the two
    # bugs that motivated factoring it out rather than repeating it per driver.
    #
    # Via wiring_for_stack, not ArrayWiring directly: the placement has to be derived from the
    # STACK, because the two can disagree and both directions are silent. With --stack skylake
    # (or any single-die template) a bare ArrayWiring would compute a plan, project it onto tiles
    # the stack has no die for, and land nothing -- which reads as an expensive cooler that does
    # not work. That is now an error naming the fix.
    wiring = None
    if arm != 'control' and not args.no_array:
        wiring = wiring_for_stack(stack, flp, os.path.join(args.out_dir, tag),
                                  want_array=True,
                                  pitch_um=args.pitch_um, cell_um=args.cell_um,
                                  coverage=args.array_coverage)

    # X4: with --gen3-split the SOLVER sees the compute-die template (caches dark) plus the
    # storage-die template (caches only); the accounting, the name map and the tile wiring keep
    # the reference floorplan, whose blocks are the union of the two.
    gen3_kw = {}
    solver_flp = flp
    if getattr(args, 'gen3_split', None):
        solver_flp = os.path.join(args.gen3_split, 'compute_template.flp')
        gen3_kw['storage_flp_template'] = os.path.join(args.gen3_split, 'storage_template.flp')

    def solver_factory(sub):
        return ICEThermalSolver(stack, solver_flp, args.tech_node,
                                run_base_dir=os.path.join(args.out_dir, tag, sub),
                                initial_temp=args.ambient_K, num_cores=n_cores,
                                single_thread=True, mode='steady',
                                session_cache=args.session_cache, **gen3_kw,
                                # §P0.19: the extractor cap needs the array die's own temperatures
                                mr_temps=bool(wiring is not None and args.mr_extractor != 'none'),
                                # re-read every time: the planner revises between solves
                                **(wiring.solver_kwargs() if wiring else {}))

    # The MR clipping loop calls this several times, so verification has to be accumulated over
    # ALL of them. Reporting only the last solve's agreement is actively misleading: a point can
    # fail verification on an intermediate MR iteration and still finish with a reassuring
    # 0.01 K spread, which invites someone to wave the flag away.
    ver = {'n_solves': 0, 'n_unconverged': 0, 'worst_spread_K': None}
    solve_history = []

    def solve_with_leakage(tr):
        counter['n'] += 1
        solver = solver_factory('it{:02d}'.format(counter['n']))
        r = run_leakage_feedback(tr, leak_ref, solver,
                                 model=leak_model, T_ref=t_ref, num_cores=n_cores,
                                 tol_K=args.tol, max_iter=args.max_iter, relax=args.relax,
                                 t_floor_K=T_FLOOR_K, bridge_aggregates=True,
                                 verify=not args.no_verify, verify_tol_K=args.verify_tol)
        solve_with_leakage.last = r
        # the array die's tile temperatures from the solve that produced this field (§P0.19)
        solve_with_leakage.last_mr_temps = getattr(solver, 'last_mr_temps', None)
        # Every solve, so the row can be built from the solve that produced the REPORTED
        # field rather than the last one executed -- the planner's bisections deliberately
        # end on a failing probe, and a row built from that probe reports a runaway's power
        # under a holding plan's peak (found in P0.19: p_chip 1527 W on a 263 W die at 91 C).
        solve_history.append(r)
        ver['n_solves'] += 1
        spread = r.get('peak_spread_K')
        if spread is not None:
            ver['worst_spread_K'] = max(ver['worst_spread_K'] or 0.0, float(spread))
        # An unverified solve is not a result. Record it so the row is flagged rather than
        # quoted: every large error in this project so far has been a damping artefact that
        # looked exactly like a converged number.
        if r.get('unconverged'):
            ver['n_unconverged'] += 1
        return r['temp_trace']

    # §P0.19: with an extractor model the lift is derived from the extractor's own cooling curve
    # at the tile's temperature; the scalar dt_max is dropped unless given explicitly.
    extractor = None if args.mr_extractor == 'none' else make_extractor(args.mr_extractor)
    cold_tiles = set()
    if extractor is not None and args.mr_zone_mode == 'dual' and wiring is not None:
        # §P0.21: the flagged dual-material arrangement -- cold-zone tiles (majority under the
        # blocks matching --mr-cold-zone-pattern) get the storage-zone material's curve.
        from HotGauge.thermal.mr_array import tiles_over_blocks
        cold_tiles = tiles_over_blocks(wiring.tiles, wiring.blocks, args.mr_cold_zone_pattern)
        extractor = DualZoneExtractor(make_extractor(args.mr_cold_extractor), extractor, cold_tiles)
    dt_max = (args.mr_dt_max if args.mr_dt_max is not None
              else (None if extractor is not None else DEFAULT_DT_MAX_K))
    # §P0.22 (D3): the cache-leakage objective plans the cache-zone blocks (the same pattern the
    # dual-material arrangement uses) against --mr-cold-target-K and everything else against
    # the hot-spot target. Default 'peak' passes no zones, so the recorded rows are untouched.
    zone_targets = ([(args.mr_cold_zone_pattern, args.mr_cold_target_K)]
                    if args.mr_objective == 'cache-leakage' else None)
    mr = MRParams(target_K=target_C + 273.15, h_max=args.mr_h_max,
                  dt_max_K=dt_max, eta_asf=args.eta_asf,
                  laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                  spot_min_um=args.spot_min_um, spot_policy=args.spot_policy,
                  extractor=extractor, zone_targets=zone_targets, objective=args.mr_objective,
                  envelope_shape=args.mr_envelope_shape)

    def last_status():
        # Lets run_mr_clipping tell a converged baseline from a divergent one, which is what
        # decides whether the plan can be sized from the baseline at all.
        r = getattr(solve_with_leakage, 'last', None) or {}
        return {'diverged': bool(r.get('diverged')), 'unconverged': bool(r.get('unconverged'))}

    def last_tile_temps():
        return getattr(solve_with_leakage, 'last_mr_temps', None)

    def converged_die_power():
        # The die power the cooling actually produced, for the energy cap (P0.18.2's over-pull).
        r = getattr(solve_with_leakage, 'last', None) or {}
        if r.get('diverged') or not r.get('power_trace'):
            return None
        return die_power_of_trace(r['power_trace'], flp, args.tech_node, num_cores=n_cores)

    res = None
    flux = None
    if use_mr:
        # The die power the plan must conserve against -- the one PHYSICAL cap alongside the
        # three device caps (h_max, dt_max, need). See clipping_plan for why it exists.
        p_die_W = die_power_of_trace(trace, flp, args.tech_node, num_cores=n_cores)
        res = run_mr_clipping(trace, solve_with_leakage, geom, mr, name_map,
                              max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                              status_fn=last_status, plan_mode=args.mr_plan_mode,
                              die_power_W=p_die_W,
                              recovery_at_junction=args.recovery_at_junction,
                              T_0_K=args.T0_K,
                              tile_temps_fn=(last_tile_temps if extractor is not None else None),
                              die_power_fn=(converged_die_power
                                            if args.mr_energy_cap == 'converged' else None),
                              # No wiring under --no-array: omitting all three of tiles /
                              # tile_blocks / set_mr_powers is what selects the legacy
                              # in-source-layer placement. A HALF-specified array is refused by
                              # CoolingApplication rather than half-applied.
                              **(wiring.planner_kwargs() if wiring else {}))
        temps, acc = res['temp_trace'], res['accounting']
        # Per-TILE flux of the plan the reported field was solved on, against h_max. The
        # planner caps per block; the device emits per tile, and coverage shrinks the tile.
        flux = wiring.flux_report(args.mr_h_max) if wiring else None
    else:
        temps = solve_with_leakage(trace)
        acc = mr_accounting({}, mr)

    last = getattr(solve_with_leakage, 'last', None)
    if use_mr and res is not None and res.get('temp_trace') is not None:
        # The solve whose field the planner REPORTED, found by identity of its temperature
        # trace; falls back to the last executed solve only if none matches.
        for _r in reversed(solve_history):
            if _r.get('temp_trace') is res['temp_trace']:
                last = _r
                break
    # For an MR point the verdict belongs to the MR loop, not to the last leakage solve: the
    # envelope-anchored descent deliberately probes past the stability boundary and then reports
    # the last plan that held, so its final solve can be a diverged probe while the RESULT is a
    # perfectly good solution.
    if use_mr and 'temp_trace_diverged' in (res or {}):
        mr_field_diverged = bool(res.get('temp_trace_diverged'))
    else:
        mr_field_diverged = bool((last or {}).get('diverged'))

    # Verification applies to the solve that produced the REPORTED field, not to every solve the
    # search made. The envelope descent and both bisections deliberately visit unstable states to
    # bracket an answer, and those probes are the ones that fail verification -- flagging the
    # whole point for that conflates "we tested a state that turned out unstable" with "the
    # answer is unverified". It hid roughly fifteen good measurements, including every
    # pixel-pitch point. The reported-field check itself is unchanged and just as strict.
    if use_mr and res is not None and 'result_unconverged' in res:
        unconverged = bool(res['result_unconverged'])
    else:
        unconverged = bool(ver['n_unconverged'])
    row = {'tag': tag, 'cores': n_cores, 'arm': arm, 'mr': use_mr,
           # The target this point was actually planned against, and where it came from. An
           # absolute target that nothing reaches produces a row that looks like a converged
           # result and contains no MR at all -- which is what happened to the entire margin
           # family when --spreading moved the die 12-26 K below targets written for the old
           # boundary. Stamping both makes that visible in the harvest instead of silent.
           # Only the planning arm has a target; stamping one on control/array_idle would read
           # as though they had been held to it.
           'mr_target_C': (target_C if use_mr else None),
           'mr_target_source': (None if not use_mr else
                                ('offset_from_control_peak'
                                 if (args.mr_target_offset_K is not None
                                     and target_C != args.mr_target_C)
                                 else 'absolute')),
           'mr_target_offset_K': (args.mr_target_offset_K if use_mr else None),
           # Which generation of results this is. 'mr: true/false' no longer identifies a row
           # now that the array can be a real die layer or a subtraction from the trace.
           'placement': (res or {}).get('placement', 'none' if arm == 'control' else 'array_above'),
           'n_tiles': len(wiring.tiles) if wiring else 0,
           'pitch_um': args.pitch_um if wiring else None,
           # The array charged its own footprint (P0.18): requested and ACHIEVED coverage,
           # extractor and reserved mm^2, and the worst tile flux against h_max.
           **(wiring.area_fields() if wiring else {}),
           'tile_flux': flux,
           'mr_extractor': args.mr_extractor if use_mr else None,
           'mr_zone_mode': args.mr_zone_mode if use_mr else None,
           'n_cold_zone_tiles': (len(cold_tiles) if use_mr else None),
           'mr_energy_cap': args.mr_energy_cap if use_mr else None,
           # §P0.22 (D3): the objective the plan was built against and where each zone landed.
           'mr_objective': args.mr_objective if use_mr else None,
           'mr_envelope_shape': args.mr_envelope_shape if use_mr else None,
           'mr_cold_target_K': (args.mr_cold_target_K if (use_mr and mr.has_zones) else None),
           'mr_zones': (res or {}).get('zones') if use_mr else None,
           'extractor': (res or {}).get('extractor') if use_mr else None,
           'mr_dt_max_K': (None if mr.dt_max_K == float('inf') else mr.dt_max_K) if use_mr else None,
           'stack_spec': arm_stack_spec(args, arm),
           'fan_W': sink.parasitic_power_W(),
           # probe failures are diagnostics, kept so a suspicious point can still be audited
           'n_probe_solves_unconverged': ver['n_unconverged'],
           'mr_reason': (res or {}).get('reason') if use_mr else None,
           'mr_loop_converged': bool((res or {}).get('converged')) if use_mr else None,
           # Whether the reported plan is the MINIMUM MR that keeps a steady state, or merely
           # an upper bound the descent stopped at. Only the former is a rescue-cost claim.
           'mr_plan_is_minimum': (res or {}).get('plan_is_minimum') if use_mr else None,
           # The one that decides whether a row is a RESCUE or merely a stable-but-hot die:
           # the minimum plan for a steady state to exist can leave the peak at 133 C.
           'mr_plan_holds_target': (res or {}).get('plan_holds_target') if use_mr else None,
           'mr_minimum_plan_W': (res or {}).get('minimum_plan_W') if use_mr else None,
           'mr_largest_failing_plan_W': (res or {}).get('largest_failing_plan_W') if use_mr
                                        else None,
           'unconverged': unconverged,
           'n_solves': ver['n_solves'], 'n_unconverged_solves': ver['n_unconverged'],
           # worst_ is the one that decides whether this row is quotable; peak_spread_K is the
           # final solve's, kept because it is what the reported temperatures came from.
           'worst_peak_spread_K': ver['worst_spread_K'],
           'peak_spread_K': (last or {}).get('peak_spread_K'),
           'relax_final': (last or {}).get('relax_final')}
    if last is None or mr_field_diverged:
        row['diverged'] = True
        return row

    finals = {k: float(np.ravel(v)[-1]) for k, v in temps.items()}
    # §P0.22 (D3): the leakage ledger. Every arm's reported field is priced on the SAME leakage
    # reference and curve the feedback loop solved with, so "cooling the caches saved X W of
    # leakage" is a difference of two rows built by one rule. The cache zone is the same pattern
    # the objective and the dual-material arrangement use; its temperatures are summarised for
    # every arm too, so the idle row says where the caches sit before anything is asked of them.
    _nm = aggregate_aware_name_map(include_core_idx=(n_cores > 1), num_cores=n_cores)
    _led = leakage_ledger(temps, leak_ref, leak_model, t_ref, _nm,
                          zones={'cache': args.mr_cold_zone_pattern}, t_floor_K=T_FLOOR_K)
    _zr = zone_report(temps, MRParams(target_K=args.mr_target_C + 273.15,
                                      zone_targets=[(args.mr_cold_zone_pattern,
                                                     args.mr_cold_target_K)]), T_FLOOR_K)
    _cz = _zr.get(args.mr_cold_zone_pattern) or {}
    row.update({'die_leakage_W': _led['die_leakage_W'],
                'cache_leakage_W': _led['zones']['cache'],
                'reference_leakage_W': _led['reference_leakage_W'],
                'n_leakage_units': _led['n_units'],
                'n_leakage_units_at_floor': _led['n_units_at_floor'],
                'n_leakage_units_off_die': _led['n_units_off_die'],
                'off_die_reference_leakage_W': _led['off_die_reference_W'],
                'cache_zone_pattern': args.mr_cold_zone_pattern,
                'n_cache_blocks': _cz.get('n_blocks'),
                'cache_zone_max_C': (K_to_C(_cz['max_K']) if _cz.get('max_K') is not None else None),
                'cache_zone_mean_C': (K_to_C(_cz['mean_K']) if _cz.get('mean_K') is not None
                                      else None)})
    hot_name, hot_K = None, -np.inf
    for k, v in finals.items():
        if v > T_FLOOR_K and v > hot_K:
            hot_name, hot_K = k, v
    p_chip = die_power_of_trace(last['power_trace'], flp, args.tech_node, num_cores=n_cores)
    # Static-power accounting. The injected trace carries leakage extracted at T_ref; the
    # converged trace carries it rescaled to the solved temperatures. The difference is the
    # leakage the die gained (or, under MR, gave back) purely from its temperature, which is
    # what makes MR partly self-funding: cooling the hotspot lowers leakage everywhere hot.
    p_inj = die_power_of_trace(trace, flp, args.tech_node, num_cores=n_cores)
    p_leak_growth = p_chip - p_inj
    p_mr_net = acc['electrical_power_W']
    p_cool = sink.parasitic_power_W() + p_mr_net
    perf = performance_summary(list(finals.values()), fmax, f_nominal_GHz=args.f_nominal,
                               compute_power_W=p_chip, cooling_power_W=p_cool,
                               throttle_K=args.throttle_C + 273.15, t_floor_K=T_FLOOR_K)
    g = perf['f_effective_GHz'] * args.flops_per_cycle * n_cores
    # The floorplan METRICS, stamped on the same row as the MR benefit. LADDER_GEN0 section 3
    # asks for a regression of measured benefit against these; computing them here is what makes
    # the two joinable at all, and it costs nothing -- the temperature field is already in hand.
    # They are properties of the DESIGN AND WORKLOAD, so the meaningful ones are those from the
    # unpowered arms; they are stamped on every arm so a reader can see the cooling move them.
    finals_C = {b: K_to_C(v) for b, v in finals.items() if v > T_FLOOR_K}
    metrics = {}
    if len(finals_C) >= 2:
        rp = relative_plateau(finals_C, 0.25)
        metrics = {'relative_plateau_25pct': rp['n_blocks'],
                   'relative_plateau_share': rp['share'],
                   'die_span_K': rp['span_K'],
                   'peak_to_runner_up_gap_K': peak_to_runner_up_gap(finals_C)}
    row.update(metrics)
    row.update({'diverged': False, 'peak_C': K_to_C(hot_K), 'peak_block': hot_name,
                'p_chip_W': p_chip, 'heat_removed_W': acc['heat_removed_W'],
                'p_mr_net_W': p_mr_net, 'p_cool_W': p_cool, 'p_total_W': p_chip + p_cool,
                'f_GHz': perf['f_effective_GHz'], 'throttling': perf['throttling'],
                'gflops': g, 'gflops_per_total_W': g / (p_chip + p_cool),
                # Thermal-only vs IPC-scaled kept SEPARATE on purpose: the first is simulated,
                # the second multiplies it by an architectural ratio nothing here can verify.
                'ipc_rel': (args.node_obj.ipc_rel if args.node_obj else 1.0),
                'gflops_with_ipc': g * (args.node_obj.ipc_rel if args.node_obj else 1.0),
                'p_injected_W': p_inj, 'p_leak_growth_W': p_leak_growth,
                'n_targets': acc.get('n_blocks_cooled', 0),
                'effective_cop': acc.get('effective_cop'),
                'net_generating': acc.get('net_generating')})
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, nargs='+', default=[34, 70, 128])
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--tech-node', type=int, default=7)
    add_rbb_argument(ap)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--stack', default='auto',
                    help="'auto' builds a direct-die stack per arm -- 30 um grease for the "
                         "control, 30 um pixel array for the others, nothing else different. "
                         "Give a template name or a spec: string to override, in which case "
                         "every arm shares it.")
    ap.add_argument('--gen3-split', default=None,
                    help='X4: directory holding compute_template.flp / storage_template.flp '
                         '(examples/split_storage_die.py); puts the storage die above the '
                         'processor die in every arm')
    ap.add_argument('--storage-um', type=float, default=50.0, help='X4: storage die thickness')
    ap.add_argument('--bond-um', type=float, default=5.0, help='X4: die-to-die bond thickness')
    ap.add_argument('--bond-k', type=float, default=50.0,
                    help='X4: bond conductivity W/(m K) -- hybrid ~120, microbump ~50, underfill ~5')
    ap.add_argument('--arms', nargs='+', default=list(ARMS), choices=list(ARMS),
                    help='control = grease, no cooling; array_idle = pixels at 0 W (the passive '
                         'term); array_on = pixels under the planner (the laser term, measured '
                         'against array_idle)')
    ap.add_argument('--pitch-um', type=float, default=DEFAULT_PITCH_UM,
                    help='cooling tile pitch. Granularity is a SWEPT variable -- the ladder is '
                         '50/100/200/500/1000/2000 um and the ordering of coarse against fine '
                         'reverses with the workload -- so a single value here is for holding it '
                         'fixed while sweeping something else. The device is a tile COUNT (4-16 '
                         'on ~200 mm^2), which is an annotation per die, not a pitch: see '
                         'mr_array.device_pitch_range_um')
    ap.add_argument('--array-coverage', type=float, default=DEFAULT_COVERAGE,
                    help='fraction of the pixel layer\'s footprint that is emitting extractor '
                         '(AREAL). The device\'s couplers, waveguides, fibre access and '
                         'monolithic-backside LPC share that footprint with the tiles (v91 '
                         'Figs. 9.1/9.8/9.12), so < 1 charges the array its own area; the '
                         'uncovered silicon is cooled only by what spreads sideways through '
                         'the burial depth. 1.0 is every recorded result. Cannot move a '
                         'control-arm ceiling: the control has no array. See P0.18.')
    ap.add_argument('--burial-um', type=float, default=DEFAULT_DIRECT_SOURCE_DEPTH_UM,
                    help='active-layer depth below the cooled surface; identical in every arm')
    ap.add_argument('--no-array', action='store_true',
                    help='legacy placement: subtract the plan from the processor trace instead '
                         'of putting it on the array. An UPPER BOUND, not the device -- the '
                         'extracted watt crosses no silicon, so burial depth is inert by '
                         'construction. Every arm then runs on the control stack and '
                         'array_idle is dropped, because with no array die it would be the '
                         'control under a second name. Retained so results predating the array '
                         'reproduce; pair it with --stack skylake to reproduce one exactly.')
    ap.add_argument('--spreading', action='store_true',
                    help='take the cold-plate slab OUT of the stack and fold it into the boundary '
                         'as a real overhanging base (P0.4). 3D-ICE gives every layer exactly the '
                         'die footprint, so a slab in the stack is a column of metal the width of '
                         'the die and the package budget comes out proportional to 1/area -- '
                         '15.5x across the die sizes here, against 2.6x with the overhang. '
                         'STRONGLY preferred for anything quotable; off by default only so that '
                         'results predating it reproduce.')
    ap.add_argument('--base-mm2', type=float, default=None,
                    help='cold-plate footprint [mm^2] for --spreading. Default: the socket '
                         'footprint (a fixed AREA, not a ratio of the die -- a ratio puts 1/area '
                         'straight back in)')
    ap.add_argument('--mr-material', default='GAAS')
    ap.add_argument('--cell-um', type=float, default=50.0,
                    help='3D-ICE grid cell; the tile grid snaps to it')
    ap.add_argument('--density', type=float, default=0.575,
                    help='die-average power density [W/mm^2] held fixed across floorplans')
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, default=None,
                    help='use a bare thermal resistance [K/W] instead of the airflow model -- '
                         'the way cold plates and liquid loops are specified (0.02-0.05 K/W is '
                         'liquid class). Overrides --cfm; pump power is NOT modelled.')
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    ap.add_argument('--leakage-cal', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    # `[!]` DEFAULT 'pipeline', and it must stay that way -- same discipline as --rbb-policy.
    # Every recorded result in this driver's catalogue was solved on the pipeline curve; changing
    # the default would silently move all of them. A non-default curve is a deliberate, flagged
    # re-run. See §P0.13/§P0.14 and thermal.leakage_feedback.load_leakage_model.
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
    # --- workload shape, mirroring examples/thermal_tiers.py so the two are joinable ---
    ap.add_argument('--power-follows-area', default=None, metavar='FLP_DIR',
                    help='hold every block\'s power DENSITY at its value on the reference '
                         'floorplan directory given, instead of holding its power. REQUIRED for '
                         'floorplans whose block areas did not come from McPAT (the pack-rebuilt '
                         'ISA variants): the trace and the areas are otherwise two inconsistent '
                         'models, and the core_other slab alone reaches 28 W/mm^2. Omit for '
                         'McPAT-derived floorplans, where the trace already matches the areas.')
    ap.add_argument('--activity', default='uniform', choices=('uniform', 'turbo', 'mixed'),
                    help='per-core activity: uniform (every core saturated -- the most hostile '
                         'assumption for MR), turbo (one core saturated), mixed')
    ap.add_argument('--hot-core', type=int, default=0)
    ap.add_argument('--background', type=float, default=0.25,
                    help='activity of the non-saturated cores')
    ap.add_argument('--active-fraction', type=float, default=0.5, help='for --activity mixed')
    ap.add_argument('--emphasise', default=None,
                    help="McPAT unit substring to concentrate a core's power into, e.g. "
                         "'Floating Point Units' (accelerator-style core)")
    ap.add_argument('--emphasis-factor', type=float, default=3.0)
    ap.add_argument('--activity-scope', default='iso-per-core',
                    choices=('iso-per-core', 'iso-density'))
    ap.add_argument('--mr-target-C', type=float, default=92.0)
    ap.add_argument('--mr-target-offset-K', type=float, default=None,
                    help='derive the MR target from THIS POINT\'s measured unaided peak: '
                         'target = array_idle peak - OFFSET [K] (array_idle is the unaided '
                         'state of the arm being planned -- same stack, laser off; the control '
                         'is a DIFFERENT stack and is cooler by the passive term, so offsetting '
                         'from it re-creates the same defect), instead of the absolute '
                         '--mr-target-C. Use this for margin and rescue-cost sweeps. An absolute '
                         'target silently produces a study that measures nothing when the '
                         'boundary moves: --spreading dropped the 34-core die to 77.5-81.1 C '
                         'while the margin sweep still asked for 93-99 C, so 68 of 85 catalogue '
                         'points returned "nothing above target", removed zero watts and engaged '
                         'zero blocks -- see docs/evidence/catalogue_naming_and_margin_defects.json. '
                         'A derived target cannot slide out from under its own study. If the '
                         'control arm diverges there is no measured peak to offset from, and the '
                         'point falls back to --mr-target-C with mr_target_source stamped '
                         'accordingly.')
    ap.add_argument('--eta-asf', type=float, default=DEFAULT_ETA_ASF)
    ap.add_argument('--eta-laser', type=float, default=DEFAULT_LASER_WALLPLUG)
    ap.add_argument('--eta-lpc', type=float, default=DEFAULT_LPC_EFFICIENCY)
    ap.add_argument('--mr-h-max', type=float, default=DEFAULT_H_MAX_W_PER_MM2)
    ap.add_argument('--mr-dt-max', type=float, default=None,
                    help='scalar lift cap [K]; default {} K, or NONE (no scalar cap) when '
                         '--mr-extractor is set, because the extractor curve then bounds the '
                         'lift'.format(DEFAULT_DT_MAX_K))
    ap.add_argument('--mr-extractor', default='none', choices=['none'] + sorted(EXTRACTORS),
                    help='P0.19: bound each tile by the extractor\'s own cooling flux at the '
                         'tile\'s solved temperature (thermal.extractor) instead of the scalar '
                         'dt_max. dye = R101/R640-SMILES at v91 §8.3; gaas = Table 9.2 benchmark '
                         'with a fixed 890 nm pump; gaas-retuned = pump follows the gap. Default '
                         'none reproduces every recorded result.')
    ap.add_argument('--mr-zone-mode', default=DEFAULT_ZONE_MODE, choices=ZONE_MODES,
                    help='P0.21: single = one extractor material over the whole array (the '
                         'DEFAULT, architecture-agnostic); dual = the flagged cold-zone / '
                         'hot-zone arrangement, laid out against this floorplan: tiles mostly '
                         'under --mr-cold-zone-pattern blocks get --mr-cold-extractor, the rest '
                         '--mr-extractor. A per-architecture product; measure it, do not ship it.')
    ap.add_argument('--mr-cold-zone-pattern', default=DEFAULT_COLD_ZONE_PATTERN,
                    help='regex on floorplan block names that defines the cold (storage) zone')
    ap.add_argument('--mr-cold-extractor', default=DEFAULT_COLD_EXTRACTOR,
                    choices=sorted(EXTRACTORS),
                    help='the storage-zone material in dual mode (decided 8 Sep: Cr:LiSAF)')
    ap.add_argument('--mr-objective', default='peak', choices=('peak', 'cache-leakage'),
                    help='§P0.22 (D3). "peak" (default, every recorded row): hold every block at '
                         'or below --mr-target-C. "cache-leakage": hold the cache-zone blocks '
                         '(--mr-cold-zone-pattern) at --mr-cold-target-K and everything else at '
                         '--mr-target-C, at minimum cooling watts -- the objective under which a '
                         'storage-zone material has a job. Rows carry die_leakage_W and '
                         'cache_leakage_W under either objective.')
    ap.add_argument('--mr-cold-target-K', type=float, default=280.0,
                    help='cache-zone temperature the cache-leakage objective holds [K]. 280 K is '
                         'the measured knee of the cold-zone prize (RESULTS_REGISTER §1.2); it is '
                         'BELOW the 295 K ambient, which is the point (§P0.22.2 P2).')
    ap.add_argument('--mr-envelope-shape', default='seed', choices=('seed', 'power'),
                    help='§P0.24. Shape of the rescue path\'s first (full-capability) plan: "seed" '
                         '(every recorded row) is dt_max / 1.0 K/W per block, uniform, scaled by '
                         'conservation; "power" caps each block at its own dissipation, so full '
                         'capability means removing every block\'s own heat.')
    ap.add_argument('--mr-energy-cap', default='injected', choices=('injected', 'converged'),
                    help='which die power the conservation cap uses: the injected trace (recorded '
                         'behaviour) or the CONVERGED die power after each solve, which stops the '
                         'array removing more than the cooled die dissipates (P0.18.2\'s 12 W '
                         'over-pull at 2.60 W/mm^2)')
    ap.add_argument('--mr-iter', type=int, default=6)
    # 'auto' sizes the plan from the uncooled baseline when that baseline exists, and from the
    # device envelope (descending toward the target) when it does not. The latter is required in
    # the rescue regime: there the baseline diverges, and planning from a point on a divergent
    # trajectory made the rescue depend on where the iteration stopped. See
    # HotGauge/thermal/microrefrigeration.py.
    ap.add_argument('--mr-plan-mode', default='auto', choices=('auto', 'baseline', 'envelope'),
                    help='how the MR plan is sized (default auto)')
    ap.add_argument('--spot-min-um', type=float, default=DEFAULT_SPOT_MIN_UM)
    ap.add_argument('--spot-policy', default=DEFAULT_SPOT_POLICY,
                    choices=('dilute', 'exclude', 'ideal'),
                    help='what to do with a block narrower than the pitch')
    ap.add_argument('--f-nominal', type=float, default=4.0)
    # Generational comparison. --node-model looks up that node's nominal clock and IPC, sets
    # f_nominal from it, and (unless --density is given explicitly) scales the operating density
    # by the dynamic-power cost of running at that clock instead of the trace's 3.8 GHz.
    #
    # That last part is the physically interesting coupling: a 7nm part rated at 5.0 GHz costs
    # 2.96x the dynamic power of the trace, so its "native" operating point is 0.660 * 2.96 =
    # 1.95 W/mm^2 -- deep into the regime where cooling decides whether the clock is reachable
    # at all. Ignoring it would compare nodes at a power budget none of them actually run at.
    #
    # IPC is applied ONLY to reported throughput (gflops_with_ipc), never to power or
    # temperature, because nothing in this pipeline can simulate it -- every trace is the same
    # microarchitecture. See HotGauge/power/process_nodes.py.
    ap.add_argument('--node-model', default=None, choices=sorted(NODES),
                    help='apply this node\'s nominal clock and IPC (generational study)')
    ap.add_argument('--native-density', action='store_true',
                    help='with --node-model, derive density from the node\'s own measured '
                         'power scaled to its nominal clock, instead of --density')
    ap.add_argument('--derate-per-K', type=float, default=0.001)
    ap.add_argument('--throttle-C', type=float, default=100.0)
    ap.add_argument('--flops-per-cycle', type=float, default=DEFAULT_FLOPS_PER_CYCLE)
    ap.add_argument('--tol', type=float, default=0.5)
    # Convergence verification is ON by default. Every solve is repeated at half the damping
    # and the peaks must agree; a point that fails is reported UNCONVERGED rather than as a
    # number. This exists because the damping the leakage fixed point needs cannot be
    # predicted, and getting it wrong is silent -- see docs/GAMEPLAN.md P0.1.
    ap.add_argument('--no-verify', action='store_true',
                    help='skip the second (half-damping) solve; faster, unsafe to quote')
    ap.add_argument('--verify-tol', type=float, default=1.0,
                    help='peak-temperature agreement [K] required between damping levels')
    # 60, not 30 or 12. Convergent cases still settle in 2-3 iterations, but two things need
    # headroom now: convergence is tested on the fixed-point RESIDUAL (a stricter measure than
    # the old change-between-solves, by roughly 1/relax), and declaring a genuine runaway means
    # the adaptive scheme has to walk the damping down to its floor first -- measured at ~48
    # solves. Iterations are ~0.6 s with a persistent session, so headroom is cheap.
    ap.add_argument('--max-iter', type=int, default=60)
    # 0.5 is now a STARTING point, not a fixed choice. The loop backtracks: any step that
    # increases the residual is rejected and retaken with half the damping, so the damping is
    # discovered per point instead of guessed. MEASURED on a lumped model driven by the real
    # 7nm leakage curve: the apparent runaway cliff moved 23% (11.21 -> 13.79 in theta) across
    # fixed relax values 1.0 -> 0.0125, and the peak that went with it moved 17 K; with
    # backtracking the same cliff lands at 11.227-11.229 from starting relax 1.0, 0.5 or 0.1 --
    # a 0.01% spread. That is the whole point: the answer no longer depends on the knob.
    ap.add_argument('--no-leakage-extrapolation', action='store_true',
                    help='clamp the calibrated leakage curve at its top measured temperature '
                         '(400 K) instead of extrapolating an Arrhenius tail above it. The tail '
                         'is uncertain by ~2.5x there and can blow a large block up in a single '
                         'iteration; clamping is the conservative comparison')
    ap.add_argument('--relax', type=float, default=0.5,
                    help='STARTING under-relaxation; the loop tightens it automatically')
    ap.add_argument('--no-server', action='store_true',
                    help='use the one-shot Emulator instead of a persistent '
                         '3D-ICE session (~150x slower; for cross-checking)')
    ap.add_argument('--recovery-at-junction', action='store_true',
                    help='bound the LPC recovery by the Carnot factor of the junction the heat is '
                         'lifted from (v91 eq. 1.14-1.16). Without it the ledger uses the '
                         'phi -> 1 limit and can report a net-generating loop')
    ap.add_argument('--T0-K', type=float, default=295.0,
                    help='sink temperature for the Carnot factor, with --recovery-at-junction')
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    # §P0.16: under a non-stock core_other policy, solve against a corrected copy of
    # the trace. Returns args.trace_dir unchanged under the default, so the recorded
    # path is byte-identical.
    args.trace_dir = resolve_trace_dir(args.trace_dir, args.core_other_policy)
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'mr_compare'))
    os.makedirs(args.out_dir, exist_ok=True)

    # With no array die there is no material substitution to separate, so array_idle would be
    # the control under a second name -- and reporting it as a third arm would invent a passive
    # term that does not exist on the legacy path. Dropped rather than silently duplicated.
    if args.no_array and 'array_idle' in args.arms:
        args.arms = [a for a in args.arms if a != 'array_idle']
        print('  --no-array: dropping the array_idle arm (nothing to be idle)')

    # One persistent 3D-ICE session, shared across every point in the sweep. It factorises the
    # system matrix once (~88 s on the 34-core die) and each later solve costs ~0.6 s instead
    # of ~88 s. Safe to share: the cache hashes everything the matrix is built from and rebuilds
    # automatically when the sink or floorplan changes, and a session refuses to solve against a
    # stack it did not factorise.
    args.session_cache = None if args.no_server else ICESessionCache()

    # --- generational node model -------------------------------------------------------
    args.node_obj = NODES[args.node_model] if args.node_model else None
    if args.node_obj is not None:
        args.f_nominal = args.node_obj.f_nominal_GHz
        args.tech_node = args.node_obj.tech_node
        args.node = '{}nm'.format(args.node_obj.tech_node)
        print(describe_assumptions())
        print()
        print('  node     : {} ({}), f_nominal {:.2f} GHz, IPC {:.2f}x'.format(
            args.node_obj.name, args.node_obj.era, args.node_obj.f_nominal_GHz,
            args.node_obj.ipc_rel))
        print('  clock    : dynamic power x{:.3f} vs the {:.1f} GHz trace'.format(
            args.node_obj.dynamic_power_factor(), TRACE_REFERENCE_GHZ))

    if args.leakage_curve != 'pipeline':
        # A flagged re-run on a non-pipeline curve. --no-leakage-extrapolation is a property of
        # the pipeline curve's Arrhenius tail and has no meaning here, so it is ignored rather
        # than silently half-applied.
        leak_model, t_ref = load_leakage_model(args.leakage_curve,
                                               calibration=args.leakage_cal, extrapolate=True)
        leak_src = 'leakage curve {!r} (P0.13/P0.14)'.format(args.leakage_curve)
    elif os.path.isfile(args.leakage_cal):
        # `[!]` Above the measured range (top 400 K) the Arrhenius tail can hand a large block a
        # very large leakage in ONE step, before any relaxation damps it. On the 34-core die that
        # shows up as the un-itemised `core_other` slab -- 15.85 mm^2, 15.7 % of the die -- hitting
        # thousands of kelvin on iteration 1 at high density, which is a numerical blow-up rather
        # than a physical runaway. --no-leakage-extrapolation clamps at the top measured point
        # instead, so the two can be compared and the artefact separated from the physics.
        leak_model, t_ref = load_calibrated_leakage_model(
            args.leakage_cal, extrapolate=not args.no_leakage_extrapolation)
        leak_src = ('MEASURED McPAT curve, CLAMPED above 400 K'
                    if args.no_leakage_extrapolation
                    else 'MEASURED McPAT curve + Arrhenius tail above 400 K')
    else:
        leak_model = LeakageModel.exponential(15.0)
        t_ref = mcpat_tref_from_trace_dir(args.trace_dir) or 330.0
        leak_src = 'assumed exponential'
    fmax = FMaxModel.linear_derate(args.derate_per_K)

    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    split = os.path.join(args.trace_dir,
                         os.path.basename(files[0]).replace('block_powers_',
                                                            'block_powers_split_'))

    print('MR vs no-MR at matched density')
    print('  density  : {:.3f} W/mm^2 held fixed'.format(args.density))
    if args.r_th is not None:
        print('  cooling  : R_th {:.4g} K/W (bare resistance; pump power NOT modelled)'
              .format(args.r_th))
    else:
        print('  airflow  : {:.0f} CFM  (fan {:.1f} W)'.format(args.cfm,
                                                               simscale_fan_power(args.cfm)))
    print('  leakage  : {}'.format(leak_src))
    print('  MR       : eta_asf {:.2f}, laser {:.2f}, LPC {:.2f}, spot >= {:.0f} um'.format(
        args.eta_asf, args.eta_laser, args.eta_lpc, args.spot_min_um))
    print('  spot     : {:.0f} um pitch, policy={}'.format(
        args.spot_min_um, args.spot_policy))
    print()
    hdr = ('{:>6s} {:>8s} {:>7s} {:>4s} {:>8s} {:>8s} {:>8s} {:>8s} {:>7s} {:>10s} {:>9s}'
           .format('cores', 'area', 'P_die', 'MR', 'peak C', 'Q_rem', 'dP_leak', 'P_cool',
                   'f GHz', 'GFLOP/s', 'per totW'))
    print(hdr)
    print('-' * len(hdr))

    rows = []
    rbb_meta = None   # set per core count below; None only if --cores is empty
    for n in args.cores:
        flp = floorplan_path(args.flp_dir, args.node, n)
        if args.node_obj is not None and args.native_density:
            # Measure this node's own power for the workload, then scale it to the node's rated
            # clock. That is the density the part actually runs at -- not an arbitrary sweep
            # value -- and it is where the generational comparison becomes meaningful.
            _base = replicate_trace_cores(base0, n, n_src=args.trace_cores) \
                if n > args.trace_cores else base0
            _p_native = die_power_of_trace(_base, flp, args.tech_node, num_cores=n)
            _area = chip_area_m2_from_floorplan(flp) * 1e6
            args.density = (_p_native / _area) * args.node_obj.dynamic_power_factor()
            print('  native   : {:.2f} W at 3.8 GHz -> {:.2f} W at {:.2f} GHz over {:.1f} mm^2'
                  ' = {:.3f} W/mm^2'.format(
                      _p_native, _p_native * args.node_obj.dynamic_power_factor(),
                      args.node_obj.f_nominal_GHz, _area, args.density))
        if not os.path.isfile(flp):
            print('  skip {}-core: no floorplan'.format(n))
            continue
        area_m2 = chip_area_m2_from_floorplan(flp)
        power_W = args.density * area_m2 * 1e6

        base = replicate_trace_cores(base0, n, n_src=args.trace_cores) \
            if n > args.trace_cores else base0

        # POWER ON A FLOORPLAN WHOSE AREAS DID NOT COME FROM McPAT.
        #
        # A McPAT trace and a McPAT floorplan agree by construction -- the area a unit gets and
        # the power it dissipates are outputs of the same model. The floorplan-pack rebuild
        # replaces the AREAS with published ones and the pack publishes no per-block power for
        # any part, so that agreement has to be restored by an explicit rule rather than assumed.
        #
        # Without one the failure is not subtle: McPAT's un-itemised core area and its
        # un-itemised core power both land on the `core_other` slab -- 15.85 mm^2 at 1.4 W/mm^2
        # on the baseline -- and a floorplan that shrinks the slab to the published 1.35% while
        # the trace still hands it 38% of die power puts 28 W/mm^2 on it. Six of seven rebuilt
        # floorplans had no steady state at a 0.60 W/mm^2 die average because of that one block.
        #
        # --power-follows-area holds each block's power DENSITY at its value on the reference
        # floorplan, so only the ARRANGEMENT changes. See
        # leakage_feedback.rebalance_trace_by_block_area for why that is the honest rule and what
        # it costs: these floorplans then compare geometry at constant activity density, not
        # activity.
        rebalance_meta = None
        if args.power_follows_area:
            ref_flp = floorplan_path(args.power_follows_area, args.node, n)
            if not os.path.isfile(ref_flp):
                raise SystemExit('--power-follows-area: no {}-core floorplan under {}'
                                 .format(n, args.power_follows_area))
            base, rebalance_meta = rebalance_trace_by_block_area(base, flp, ref_flp)
            print('  power    : each block holds its W/mm^2 from {} '
                  '({} blocks rescaled, x{:.3f} to x{:.3f})'.format(
                      os.path.relpath(ref_flp, _REPO), rebalance_meta['n_blocks_rescaled'],
                      rebalance_meta['min_factor'], rebalance_meta['max_factor']))

        # WORKLOAD SHAPE. Identical construction to examples/thermal_tiers.py -- deliberately, so
        # a shape screened there and a shape measured here are the same input. That equality is
        # the whole point: the tier screens produce the floorplan METRICS and this driver produces
        # the MR BENEFIT, and LADDER_GEN0 section 3 asks for a regression of one against the other.
        # Until 27 Aug 2026 those two datasets could not be joined, because the 11 shapes existed
        # only in the control-arm screens and every one of the 35 catalogue points with a measured
        # MR benefit ran at uniform activity on the same die.
        #
        # Emphasis is applied to the per-core mix BEFORE any activity map or normalisation, so it
        # composes with them and does not change core power on its own.
        if args.emphasise:
            base = emphasise_units(base, args.emphasise, args.emphasis_factor)
        activity_map = None
        if args.activity == 'turbo':
            activity_map = single_core_turbo(n, args.hot_core, args.background)
        elif args.activity == 'mixed':
            activity_map = mixed_utilisation(n, args.active_fraction, args.background)

        if activity_map is not None and args.activity_scope == 'iso-density':
            base = scale_cores(base, activity_map)
            trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                                       num_cores=n)
        else:
            # iso-per-core: normalise the SATURATED die to --density first, then quiet the cores,
            # so an idle core dissipates less and die power lands below the target. That is what a
            # real part does, and it is the right comparison for an activity study.
            trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                                       num_cores=n)
            if activity_map is not None:
                trace = scale_cores(trace, activity_map)
        leak_ref = {}
        if os.path.isfile(split):
            with open(split) as f:
                leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}
            if rebalance_meta is not None:
                # The leakage reference is a per-unit power and has to move with the trace it
                # references. Leaving it un-rebalanced would drive the feedback loop from one
                # floorplan's areas and the temperatures from another's, which is silent.
                f_by_unit = rebalance_meta['factors_by_unit']
                leak_ref = {u: v * f_by_unit.get(u, 1.0) for u, v in leak_ref.items()}

        # `[!]` RBB policy: applied ONCE here, on the baseline trace, after every other trace
        # transform and before the feedback loop, the planner and the accounting -- so all three
        # see one power map. Trace and leakage reference move together; rescale_trace rebuilds
        # power as `series - leak + leak*scale(T)`, so a zeroed series with a live leakage entry
        # would re-inject the bus with a negative power below T_ref. See HotGauge.thermal.rbb.
        trace, leak_ref, rbb_meta = amortize_rbb(
            trace, flp, policy=args.rbb_policy, leakage_ref=leak_ref or None,
            span=args.rbb_span, name_map=mcpat_flp_name_map(include_core_idx=(n > 1)))
        leak_ref = leak_ref or {}

        fp = Floorplan.from_file(flp)
        geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                         'min_dim_um': float(min(e.width, e.height))} for e in fp.elements}
        name_map = mcpat_flp_name_map(include_core_idx=(n > 1))

        pair = {}
        # Derived targets need the control arm's peak, so control must be solved first. ARMS is
        # already ordered that way; this asserts it rather than trusting it, because a reordered
        # --arms would otherwise silently fall back to the absolute target.
        # The target is offset from the UNAIDED PEAK OF THE ARM BEING PLANNED, which is
        # array_idle -- the same stack, same array, laser off -- and NOT the control.
        #
        # Deriving from the control looks right and is not: the array arm is already cooler than
        # the control by the passive term (7.4 K at d=0.80), so any offset smaller than that
        # passive term lands ABOVE the array's own peak and the planner correctly does nothing.
        # That would reproduce the exact defect this flag exists to remove, one layer down.
        # Measured while smoke-testing this flag: control 84.9 C, array_idle 77.5 C, so a 3 K
        # offset from the control gives a target of 81.9 C and engages zero blocks.
        point_target_C = None
        if args.mr_target_offset_K is not None:
            ref = 'array_idle' if 'array_idle' in args.arms else 'control'
            if ref not in args.arms:
                raise SystemExit('--mr-target-offset-K needs array_idle (preferred) or control '
                                 'in --arms to measure from; got --arms {}'
                                 .format(' '.join(args.arms)))
            if 'array_on' in args.arms and args.arms.index(ref) > args.arms.index('array_on'):
                raise SystemExit('--mr-target-offset-K needs {} solved BEFORE array_on; '
                                 'got --arms {}'.format(ref, ' '.join(args.arms)))
        for arm in args.arms:
            tag = '{}c_{}'.format(n, arm)
            r = evaluate(args, flp, trace, leak_ref, geom, name_map, leak_model, t_ref, fmax,
                         area_m2, n, arm, tag, target_C=point_target_C)
            r.update({'area_mm2': area_m2 * 1e6, 'power_W': power_W,
                      # Stamped per row: results from the two RBB policies are not comparable
                      # and a row that does not say which one it came from is unusable.
                      'rbb_policy': args.rbb_policy})
            rows.append(r)
            pair[arm] = r
            # Back-compatible aliases so the summarisers and collect_findings keep working while
            # both generations of results are on disk.
            if arm == 'control':
                pair.setdefault('nomr', r)
            if args.mr_target_offset_K is not None and arm == ref:
                if r.get('diverged') or r.get('peak_C') is None:
                    print('       -> {} has no steady state, so there is no measured peak to '
                          'offset from; falling back to --mr-target-C {:.1f} C'
                          .format(ref, args.mr_target_C))
                else:
                    point_target_C = r['peak_C'] - args.mr_target_offset_K
                    print('       -> target derived from the {} peak (the unaided state of the '
                          'arm being planned): {:.2f} C - {:.1f} K = {:.2f} C'.format(
                              ref, r['peak_C'], args.mr_target_offset_K, point_target_C))
            elif arm == 'array_on':
                pair['mr'] = r
            if r['diverged']:
                print('{:>6d} {:>8.1f} {:>7.1f} {:>11s} {:>8s} {:>8s} {:>8s} {:>7s} {:>10s} '
                      '{:>9s}  RUNAWAY'.format(n, area_m2 * 1e6, power_W, arm,
                                               '--', '--', '--', '--', '--', '--'))
            else:
                flags = '  THROTTLED' if r['throttling'] else ''
                if r.get('unconverged'):
                    flags += ('  ** UNCONVERGED: {}/{} solves failed verification, worst peak '
                              'spread {:.1f} K **').format(
                        r.get('n_unconverged_solves', '?'), r.get('n_solves', '?'),
                        r.get('worst_peak_spread_K') or float('nan'))
                print('{:>6d} {:>8.1f} {:>7.1f} {:>11s} {:>8.1f} {:>8.3f} {:>8.2f} {:>8.2f} '
                      '{:>7.3f} {:>10.1f} {:>9.3f}{}'.format(
                          n, area_m2 * 1e6, power_W, arm,
                          r['peak_C'], r['heat_removed_W'], r['p_leak_growth_W'],
                          r['p_cool_W'], r['f_GHz'], r['gflops'], r['gflops_per_total_W'],
                          flags))
        # Report the two terms SEPARATELY. Collapsing them back into one number is the exact
        # confound the three arms exist to remove: the passive term is what replacing grease
        # with GaAs is worth before any light, and the laser term is what the planner buys on
        # top of it. A single "MR delta" credits the laser with both.
        ctrl, idle, on = pair.get('control'), pair.get('array_idle'), pair.get('array_on')
        # Does the powered arm's TEMPERATURE agree with the cooling it says it applied? A stale
        # plan left on the array is invisible in every recorded field and shows up only here.
        # See HotGauge/thermal/arm_consistency.py.
        if idle and on and not idle.get('diverged') and not on.get('diverged'):
            check_arm_consistency(idle.get('peak_C'), on.get('peak_C'),
                                  on.get('heat_removed_W', 0.0),
                                  label='mr_comparison {}'.format(on.get('tag', '')))
        live = [x for x in (ctrl, idle, on) if x]
        if any(x.get('unconverged') for x in live):
            print('       -> deltas NOT REPORTED: at least one arm failed convergence '
                  'verification, so the difference would be a difference of artefacts.')
        elif ctrl and ctrl['diverged'] and on and not on['diverged']:
            # WHICH arm did the rescuing is the whole point. Attributing a runaway rescue to the
            # laser when the unpowered array already arrested it would credit the light with what
            # the material substitution achieved -- and that is the headline claim, so it has to
            # be right.
            if idle and not idle['diverged']:
                print('       -> the UNPOWERED array already rescues a die with no steady '
                      'state: {:.1f} C at 0 W of light. The grease stack has no steady state; '
                      'swapping 30 um of it for GaAs is sufficient on its own.'
                      .format(idle['peak_C']))
                print('       -> laser  (array idle -> array on): {:+.1f} K, {:+.1f}% '
                      'throughput, {:.3f} W removed for {:+.2f} W'.format(
                          on['peak_C'] - idle['peak_C'],
                          100.0 * (on['gflops'] / idle['gflops'] - 1.0),
                          on['heat_removed_W'], on['p_cool_W'] - idle['p_cool_W']))
            else:
                print('       -> the LASER rescues a die with no steady state (the unpowered '
                      'array does not): {:.1f} C, {:.1f} GFLOP/s, {:.3f} W removed'
                      .format(on['peak_C'], on['gflops'], on['heat_removed_W']))
        else:
            if ctrl and idle and not ctrl['diverged'] and not idle['diverged']:
                print('       -> passive (grease -> GaAs, no light): {:+.1f} K, {:+.1f}% '
                      'throughput'.format(idle['peak_C'] - ctrl['peak_C'],
                                          100.0 * (idle['gflops'] / ctrl['gflops'] - 1.0)))
            if idle and on and not idle['diverged'] and not on['diverged']:
                print('       -> laser  (array idle -> array on): {:+.1f} K, {:+.1f}% '
                      'throughput, {:+.2f} W cooling, {:.3f} W removed{}'.format(
                          on['peak_C'] - idle['peak_C'],
                          100.0 * (on['gflops'] / idle['gflops'] - 1.0),
                          on['p_cool_W'] - idle['p_cool_W'], on['heat_removed_W'],
                          '  (idle: nothing above target)' if on['heat_removed_W'] == 0 else ''))
            if ctrl and on and not ctrl['diverged'] and not on['diverged']:
                print('       -> TOTAL  (grease -> array on): {:+.1f} K, {:+.1f}% throughput, '
                      'peak block {} -> {}'.format(
                          on['peak_C'] - ctrl['peak_C'],
                          100.0 * (on['gflops'] / ctrl['gflops'] - 1.0),
                          ctrl['peak_block'], on['peak_block']))
        print()

    with open(os.path.join(args.out_dir, 'mr_comparison.json'), 'w') as f:
        json.dump({'density': args.density, 'cfm': args.cfm, 'r_th': args.r_th,
                   'rbb_policy': args.rbb_policy, 'rbb': rbb_meta,
                   'f_nominal_GHz': args.f_nominal, 'node': args.node,
                   # The array configuration at the top level as well as per row. The rows are
                   # authoritative, but a summariser deciding whether two result files are
                   # comparable should not have to open the rows to find out -- and a batch
                   # script deciding whether an old result can be reused cannot.
                   'arms': list(args.arms), 'stack': args.stack,
                   'spreading': bool(args.spreading), 'base_mm2': args.base_mm2,
                   'mr_extractor': args.mr_extractor, 'mr_energy_cap': args.mr_energy_cap,
                   'mr_objective': args.mr_objective, 'mr_cold_target_K': args.mr_cold_target_K,
                   'mr_cold_zone_pattern': args.mr_cold_zone_pattern,
                   'pitch_um': args.pitch_um, 'burial_um': args.burial_um,
                   'mr_material': args.mr_material, 'cell_um': args.cell_um,
                   'gen3_split': args.gen3_split, 'storage_um': args.storage_um if args.gen3_split else None,
                   'bond_um': args.bond_um if args.gen3_split else None, 'bond_k_W_per_mK': args.bond_k if args.gen3_split else None,
                   'stack_specs': {a: arm_stack_spec(args, a) for a in args.arms},
                   'rows': rows}, f, indent=2)
    print('  written: {}'.format(os.path.join(args.out_dir, 'mr_comparison.json')))


if __name__ == '__main__':
    main()
