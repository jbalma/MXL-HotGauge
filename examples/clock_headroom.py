#!/usr/bin/env python
"""How much clock does a cooling solution buy? (clock as a free variable)

The question this answers
-------------------------
Every earlier study fixed ``f_nominal`` and let the model derate downward, so the best score any
cooling technology could achieve was "stops the throttling" -- a ceiling set by the input, not by
physics. Here the clock is the *output*: for each cooling solution the search raises the clock
until the die can no longer hold its thermal limit, and reports the highest clock it can hold.

That is the number a customer buys, it is directly comparable across cooling classes and across
process nodes, and -- because the criterion is a temperature limit rather than a frequency
derating -- it does **not** inherit the uncalibrated ``derate_per_K`` slope that the GFLOP/s
figures elsewhere rest on.

Three studies fall out of the same sweep
----------------------------------------
1. **What cooling does a 7nm part at its rated clock actually need?** Sweep ``--r-th`` down to
   liquid-class resistances and read off where the sustainable clock reaches the rated one.
2. **Iso-cooling generational comparison.** Same ``--r-th``, different ``--node-model``: the
   sustainable clock per node at identical cooling.
3. **What does MR add on top?** ``--mr`` runs each point in **three arms** -- ``control``
   (30 um of thermal grease, no cooling), ``array_idle`` (the GaAs pixel array in the grease's
   place, drawing no light) and ``array_on`` (the same array under the planner) -- and reports
   the **passive** and the **laser** term separately.

   Two arms are not enough here, and this driver is where it matters most. The array die is
   30 um of GaAs replacing 30 um of thermal grease, which is roughly 14x the conductivity, and
   the first three-arm runs showed the unpowered array alone rescuing a die that had no steady
   state under grease. Reported as one number, the headline becomes "photonic cooling buys
   +x GHz" when much of x is a packaging change with no laser in it. ``--no-array`` selects the
   legacy in-source-layer placement instead: cooling co-located with the transistors, burial
   depth inert by construction, an upper bound rather than the device. Kept only so results
   predating the array reproduce.

Examples
--------
    # what cooling does the 7nm part need to hold its rated 5.0 GHz?
    python examples/clock_headroom.py --cores 34 --node-model 7nm \\
        --r-th 1.0 0.5 0.3 0.1 0.05 0.02 --mr --pitch-um 5000

    # reproduce a pre-array result: legacy placement on the historical lidded stack
    python examples/clock_headroom.py --cores 34 --stack skylake --no-array --mr

    # sustainable clock on server air, per node, at matched cooling
    python examples/clock_headroom.py --cores 34 --cfm 88 --node-model 14nm
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
from HotGauge.thermal.rbb import amortize_rbb, add_rbb_argument
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (die_power_of_trace, mcpat_flp_name_map,
                                               replicate_trace_cores, peak_temp_K,
                                               scale_trace_to_die_power,
                                               load_calibrated_leakage_model,
                                               load_leakage_model, LEAKAGE_CURVES,
                                               mcpat_tref_from_trace_dir)
from HotGauge.power.core_other import (CORE_OTHER_POLICIES, resolve_trace_dir,
                                      DEFAULT_CORE_OTHER_POLICY)
from HotGauge.thermal.sink_models import (BaffledFinSink, ThermalResistanceSink,
                                          render_stack_with_sink, spreading_sink_for_stack,
                                          chip_area_m2_from_floorplan, simscale_fan_power,
                                          SIMSCALE_T0_K)
from HotGauge.thermal.microrefrigeration import (MRParams, run_mr_clipping, mr_accounting,
                                                 distributed_plan, CoolingApplication,
                                                 DEFAULT_SPOT_MIN_UM, DEFAULT_SPOT_POLICY,
                                                 DEFAULT_H_MAX_W_PER_MM2, DEFAULT_DT_MAX_K, DEFAULT_ETA_ASF, DEFAULT_LASER_WALLPLUG, DEFAULT_LPC_EFFICIENCY)
from HotGauge.thermal.mr_array import (wiring_for_stack, DEFAULT_PITCH_UM,
                                       device_pitch_range_um, DEFAULT_COVERAGE)
from HotGauge.thermal.die_stack import DEFAULT_DIRECT_SOURCE_DEPTH_UM
from HotGauge.thermal.ice_server import ICESessionCache
from HotGauge.power.process_nodes import NODES, describe_assumptions, TRACE_REFERENCE_GHZ
from HotGauge.power.clock_search import (scale_trace_for_clock, find_max_sustainable_clock,
                                         scale_trace_for_clock_per_core, scale_cores,
                                         single_core_turbo, emphasise_units, VF_TABLE_MAX_GHZ)
from HotGauge.power.performance_model import FMaxModel, performance_summary
# §P0.31: the generalized f_max(V, T | logic depth, wire, skew) with a reliability-budgeted V_max
from HotGauge.power.fmax_model import (GeneralizedFmaxModel, load_fmax_model, parse_fmax_spec,
                                       core_gradient_K)
from HotGauge.thermal.extractor import make_extractor, EXTRACTORS
from HotGauge.thermal.utils import K_to_C
from HotGauge.thermal.arm_consistency import check_arm_consistency

T_FLOOR_K = 200.0
DEFAULT_FLOPS_PER_CYCLE = 32.0


#: The three arms, identically to ``examples/mr_comparison.py``. Two is not enough once the
#: array is a real die layer: the GaAs pixel slab conducts ~14x better than the 30 um of thermal
#: grease it replaces, so a bare on/off comparison books that material substitution as a laser
#: result. Here that confound is worse than in mr_comparison, because the reported quantity is a
#: SUSTAINABLE CLOCK -- "MR buys +0.4 GHz" reads as a photonics claim and would be mostly
#: packaging. See docs/EXECUTION_PLAN.md 6a.
ARMS = ('control', 'array_idle', 'array_on')


def arm_stack_spec(args, arm):
    """Stack spec string for one arm. ``control`` keeps the 30 um grease; the array arms replace
    exactly that layer and change nothing else.

    Under ``--no-array`` every arm gets the control stack: the legacy placement subtracts the
    plan from the processor trace, so there IS no array die, and rendering one that nothing
    fills would fail in ICESteadySim rather than here.
    """
    if args.stack != 'auto':
        return args.stack
    mr = 'none' if (arm == 'control' or args.no_array) else args.mr_material
    # Under --spreading the cold-plate slab comes OUT of the stack; SpreadingSink puts it back
    # in the boundary with its real overhang. Every arm loses it, so the arms still differ by
    # exactly the 30 um layer.
    sink_term = ',sink_in_stack=0' if args.spreading else ''
    return 'spec:package=direct_die,mr={},src={:.0f},cell={:.0f}{}'.format(
        mr, args.burial_um, args.cell_um, sink_term)


def arms_for(args):
    """Which arms this invocation runs.

    Without ``--mr`` there is only the control. With ``--no-array`` there is no material
    substitution to separate, so ``array_idle`` would be the control under a second name and
    reporting it would invent a passive term that does not exist on that path.
    """
    if not args.mr:
        return ('control',)
    arms = tuple(a for a in ARMS if a in args.arms)
    if args.no_array:
        arms = tuple(a for a in arms if a != 'array_idle')
    return arms


def floorplan_path(flp_dir, node, n):
    stem = 'skylake{}_{}core_3_3D-ICE_template.flp'.format(node, n)
    p = os.path.join(flp_dir, stem)
    return p if os.path.isfile(p) else os.path.join(flp_dir, stem.replace('_3_', '_0_'))


def make_sink(args, area_m2, r_th):
    """Cooling as a bare resistance (``--r-th``) or as the measured air stack (``--cfm``).

    A resistance is how cold plates and liquid loops are specified, and it is the right axis
    once the question is "how good does the cooling have to BE". Its pump/chiller power is not
    modelled, so cooling power for those points counts MR only and is an underestimate.
    """
    if r_th is not None:
        return ThermalResistanceSink(r_th, area_m2, ambient_K=args.ambient_K,
                                     label='R_th {:.3g} K/W'.format(r_th))
    return BaffledFinSink(args.cfm, area_m2, ambient_K=args.ambient_K)


def _evaluate_clock_once(args, flp, base_trace, leak_ref_base, geom, name_map, leak_model, t_ref,
                         n_cores, sink, stack, use_mr, f_GHz, tag, wiring=None, run_tag=None):
    """One coupled solve at clock ``f_GHz``: rescale the trace, run the leakage fixed point
    (with damping verification), optionally clip hotspots with MR, return the peak.

    ``wiring`` is the :class:`~HotGauge.thermal.mr_array.ArrayWiring` for this arm, or ``None``
    for the control and for the legacy placement. It has to reach BOTH the solver (so the array
    die is rendered and carries the current tile powers) and the planner (so the plan is
    projected onto tiles instead of subtracted from the processor trace). Giving it to only one
    of the two is silent in both directions -- see ArrayWiring's docstring."""
    if args.turbo_core is not None:
        # Single-thread turbo: only the boosted core's clock is searched; the rest stay at the
        # trace's own clock. This is the geometry the tier screen says MR should suit best --
        # one hot structure with cool silicon around it -- and it cannot be expressed by a
        # global clock.
        trace, leak_ref, scale_info = scale_trace_for_clock_per_core(
            base_trace, leak_ref_base, {args.turbo_core: f_GHz}, TRACE_REFERENCE_GHZ,
            leakage_voltage_exponent=args.leak_v_exponent, vf_model=args._vf_model)
    else:
        trace, leak_ref, scale_info = scale_trace_for_clock(
            base_trace, leak_ref_base, f_GHz, TRACE_REFERENCE_GHZ,
            leakage_voltage_exponent=args.leak_v_exponent, vf_model=args._vf_model)

    counter = {'n': 0}
    # Accumulated over every solve the MR loop makes, not just the last one -- see the same
    # note in examples/mr_comparison.py. A point can fail on an intermediate MR iteration and
    # still finish with a reassuring final spread.
    state = {'unconverged': 0, 'last': None, 'n_solves': 0, 'worst_spread_K': None}

    def solver_factory(sub):
        # solver_kwargs() is re-read on every construction on purpose: the planner revises the
        # plan between solves and the solver renders whatever is current when it is built.
        return ICEThermalSolver(stack, flp, args.tech_node,
                                run_base_dir=os.path.join(args.out_dir, tag,
                                                          run_tag or 'f{:.3f}'.format(f_GHz), sub),
                                initial_temp=args.ambient_K, num_cores=n_cores,
                                single_thread=True, mode='steady',
                                session_cache=args.session_cache,
                                # §P0.19: the extractor cap needs the array die's own temperatures
                                mr_temps=bool(wiring is not None and args.mr_extractor != 'none'),
                                **(wiring.solver_kwargs() if wiring else {}))

    def solve_with_leakage(tr):
        counter['n'] += 1
        solver = solver_factory('it{:02d}'.format(counter['n']))
        r = run_leakage_feedback(tr, leak_ref, solver,
                                 model=leak_model, T_ref=t_ref, num_cores=n_cores,
                                 tol_K=args.tol, max_iter=args.max_iter, relax=args.relax,
                                 t_floor_K=T_FLOOR_K, bridge_aggregates=True,
                                 verify=not args.no_verify, verify_tol_K=args.verify_tol)
        state['last'] = r
        state['last_mr_temps'] = getattr(solver, 'last_mr_temps', None)
        state['n_solves'] += 1
        spread = r.get('peak_spread_K')
        if spread is not None:
            state['worst_spread_K'] = max(state['worst_spread_K'] or 0.0, float(spread))
        if r.get('unconverged'):
            state['unconverged'] += 1
        return r['temp_trace']

    # §P0.19 / §P0.29: the target device's cooling curve as the per-tile cap, and the planner's
    # envelope shape. Both default to the recorded configuration (no extractor, seed shape).
    extractor = None if args.mr_extractor == 'none' else make_extractor(args.mr_extractor)
    mr = MRParams(target_K=args.mr_target_K, h_max=args.mr_h_max,
                  dt_max_K=args.mr_dt_max, eta_asf=args.eta_asf,
                  laser_wallplug=args.eta_laser, lpc_efficiency=args.eta_lpc,
                  spot_min_um=args.spot_min_um, spot_policy=args.spot_policy,
                  extractor=extractor, envelope_shape=args.mr_envelope_shape)

    def last_tile_temps():
        return state.get('last_mr_temps')

    def last_status():
        r = state.get('last') or {}
        return {'diverged': bool(r.get('diverged')), 'unconverged': bool(r.get('unconverged'))}

    res = None
    if use_mr and args.mr_mode == 'distributed':
        # Design E, the control arm: spend the SAME budget spread over the die instead of
        # clipping hotspots. If this buys the same clock, the hotspot framing is wrong and the
        # comparison should be against a better sink rather than against nothing.
        #
        # This branch bypasses run_mr_clipping, so it has to place the cooling itself. Calling
        # apply_cooling_to_trace directly -- which is what it used to do -- would subtract the
        # watts from the processor trace while an inert array sat above, i.e. legacy placement
        # reported under an array stack. CoolingApplication is the same object run_mr_clipping
        # uses, so the two modes cannot drift apart.
        plan, plan_detail = distributed_plan(geom, mr, args.mr_budget_W, weight=args.mr_weight)
        apply_plan = CoolingApplication(
            trace, name_map,
            tiles=(wiring.tiles if wiring else None),
            blocks=(wiring.blocks if wiring else None),
            set_mr_powers=(wiring.set_mr_powers if wiring else None))
        temps = solve_with_leakage(apply_plan(plan))
        # `[!]` Recovery is Carnot-limited by the junction the heat is lifted FROM, and that is a
        # result of the solve rather than an input to the planner -- so it is read back here.
        _Th = _peak_K_for_accounting(temps)
        acc = mr_accounting(plan, mr, detail=plan_detail,
                            T_h_K=(_Th if ARGS.recovery_at_junction else None),
                            T_0_K=ARGS.T0_K)
        res = {'plan': plan, 'converged': True, 'temp_trace': temps,
               'temp_trace_diverged': bool((state['last'] or {}).get('diverged')),
               'placement': apply_plan.placement, 'tile_plan': apply_plan.last_tile_plan,
               'reason': 'distributed plan at a fixed budget (control arm)'}
    elif use_mr:
        # The die power the plan must conserve against. Three DEVICE caps already bound the
        # plan (h_max, dt_max, need); this is the one PHYSICAL cap -- the array cannot remove
        # more heat than the die makes without driving it below the coolant. It is what stops a
        # first-iteration plan sized from an assumed sensitivity running to kilowatts. See
        # clipping_plan and docs/evidence/clock_search_mr_arm_defect.json.
        p_die_W = die_power_of_trace(trace, flp, args.tech_node, num_cores=n_cores)
        res = run_mr_clipping(trace, solve_with_leakage, geom, mr, name_map,
                              max_iter=args.mr_iter, tol_K=2.0, relax=0.7,
                              status_fn=last_status, plan_mode=args.mr_plan_mode,
                              die_power_W=p_die_W,
                              # `[!]` Without this the MR arm's accounting falls back to the
                              # first-law ledger even when --recovery-at-junction is set: the
                              # direct mr_accounting call above is only the control arm's. Missing
                              # it reported a net-GENERATING loop (-23 W) at 373 K, where the
                              # second-law value is +120 W.
                              recovery_at_junction=args.recovery_at_junction,
                              T_0_K=args.T0_K,
                              tile_temps_fn=(last_tile_temps if extractor is not None else None),
                              **(wiring.planner_kwargs() if wiring else {}))
        temps, acc = res['temp_trace'], res['accounting']
    else:
        # The idle array still has to be solved WITH its tiles present at 0 W -- that is the
        # whole passive term. wiring already holds a zeroed plan, so nothing more is needed
        # here; the solver_kwargs above carry it.
        temps = solve_with_leakage(trace)
        acc = mr_accounting({}, mr)   # empty plan: nothing lifted, so no recovery term

    last = state['last'] or {}
    # See the note in examples/mr_comparison.py: for an MR point the MR loop's own verdict is
    # authoritative, because the envelope descent probes past the boundary on purpose.
    if use_mr and 'temp_trace_diverged' in (res or {}):
        field_diverged = bool(res.get('temp_trace_diverged'))
    else:
        field_diverged = bool(last.get('diverged'))

    # ...and the SAME correction for `unconverged`, which was missing until 27 Aug 2026 while the
    # `diverged` half above was already here. That asymmetry silently zeroed the MR arm of every
    # clock study in the project.
    #
    # `state['unconverged']` counts EVERY solve the MR loop makes, and the envelope descent
    # deliberately probes past the stability boundary to bracket its answer -- so for an MR point
    # that counter is essentially always non-zero. is_sustainable() treats unconverged as NOT
    # sustainable (correctly: "we could not tell" must not become "yes"), so every candidate clock
    # was rejected as 'unverified' and the bisection collapsed to --f-lo. Measured across the
    # catalogue before the fix: 9 of 10 array_on rows reported exactly 2.0000 GHz, the search
    # floor, with limited_by='unverified'.
    #
    # run_mr_clipping already publishes `result_unconverged` -- the verdict on the RESULT rather
    # than on the probes -- which is what mr_comparison.py has used since the same bug was found
    # there ("it hid roughly fifteen good measurements, including every pixel-pitch point").
    if use_mr and res is not None and 'result_unconverged' in res:
        field_unconverged = bool(res['result_unconverged'])
    else:
        field_unconverged = bool(state['unconverged'])
    out = {'f_GHz': f_GHz, 'diverged': field_diverged or temps is None,
           'unconverged': field_unconverged,
           'n_unconverged_solves': state['unconverged'], 'n_solves': state['n_solves'],
           'worst_peak_spread_K': state['worst_spread_K'],
           'vf_clamped': scale_info['vf_clamped'],
           'peak_spread_K': last.get('peak_spread_K'),
           'p_mr_net_W': acc['electrical_power_W'],
           'heat_removed_W': acc['heat_removed_W'],
           'n_targets': acc.get('n_blocks_cooled', 0),
           # Two generations of results exist and mr:true/false no longer tells them apart.
           'placement': ((res or {}).get('placement')
                         or ('array_above' if wiring else 'none' if not use_mr
                             else 'in_source_layer')),
           'n_tiles': len(wiring.tiles) if wiring else 0}
    if out['diverged'] or temps is None:
        out['peak_K'] = None
        return out
    out['peak_K'] = peak_temp_K(temps, T_FLOOR_K)
    out['peak_block'] = max(((k, float(np.ravel(v)[-1])) for k, v in temps.items()),
                            key=lambda kv: kv[1] if kv[1] > T_FLOOR_K else -np.inf)[0]
    out['p_chip_W'] = die_power_of_trace(last['power_trace'], flp, args.tech_node,
                                         num_cores=n_cores)
    out['p_injected_W'] = die_power_of_trace(trace, flp, args.tech_node, num_cores=n_cores)
    out['temps'] = {k: float(np.ravel(v)[-1]) for k, v in temps.items()}
    return out


def evaluate_clock(args, flp, base_trace, leak_ref_base, geom, name_map, leak_model, t_ref,
                   n_cores, sink, stack, use_mr, f_GHz, tag, wiring=None):
    """One candidate clock, self-consistent with the die it produces (§P0.31).

    With a plain V/F curve this is one coupled solve. With the generalized f_max model the
    supply a clock needs depends on the worst block's temperature and the core-domain gradient
    OF THAT SOLVE, so the candidate is solved in the context the previous candidate left, the
    context is re-read from the field, and the solve is repeated while the implied supply moves
    by more than ``--fmax-v-tol``. The verdict then carries the non-thermal limits by name: the
    clock needed a supply above the reliability-budgeted ``V_max`` at the solved temperature
    (``reliability:<mechanism>``), above the device's peak-clock supply (``device``), or above
    the simulated sweep (``sweep_end``).
    """
    model = args._vf_model
    if not isinstance(model, GeneralizedFmaxModel):
        return _evaluate_clock_once(args, flp, base_trace, leak_ref_base, geom, name_map,
                                    leak_model, t_ref, n_cores, sink, stack, use_mr, f_GHz, tag,
                                    wiring=wiring)
    ctx = args._fmax_ctx.setdefault(tag, {'T_K': model.T_anchor, 'dT_K': model.p['dT_anchor_K']})
    # The first pass is only as good as its starting context. The bisection's candidates are
    # far apart early on, so inherit the LAST solve's (T, dT) only as a fallback and prefer a
    # linear estimate from the two converged evaluations nearest in clock -- measured on the
    # smoke run, the inherited context cost two re-solves per candidate on the control arm.
    hist = args._fmax_hist.setdefault(tag, [])
    done = sorted(hist, key=lambda h: abs(h['f'] - f_GHz))[:2]
    if len(done) == 2 and abs(done[0]['f'] - done[1]['f']) > 1e-6:
        (f0, T0, d0), (f1, T1, d1) = ((h['f'], h['T_K'], h['dT_K']) for h in done)
        w = (f_GHz - f0) / (f1 - f0)
        w = max(-1.0, min(2.0, w))                   # a bounded extrapolation
        ctx.update({'T_K': T0 + w * (T1 - T0), 'dT_K': max(0.0, d0 + w * (d1 - d0))})
    elif len(done) == 1:
        ctx.update({'T_K': done[0]['T_K'], 'dT_K': done[0]['dT_K']})
    passes = []
    out = None
    for i in range(max(1, int(args.fmax_max_passes))):
        model.set_context(ctx['T_K'], ctx['dT_K'])
        v_used, v_clamped = model.voltage(f_GHz)
        v_pk, f_pk, at_end = model.device_peak()
        out = _evaluate_clock_once(args, flp, base_trace, leak_ref_base, geom, name_map,
                                   leak_model, t_ref, n_cores, sink, stack, use_mr, f_GHz, tag,
                                   wiring=wiring,
                                   run_tag='f{:.3f}'.format(f_GHz) + ('' if i == 0 else '_p%d' % i))
        rec = {'pass': i, 'T_context_K': ctx['T_K'], 'dT_context_K': ctx['dT_K'],
               'V_used_V': v_used, 'v_clamped': v_clamped, 'peak_K': out.get('peak_K')}
        if out.get('peak_K') is None:
            # a diverged solve leaves no field to re-read; keep the context
            passes.append(rec)
            break
        dT, dT_mean, core = core_gradient_K(out['temps'])
        ctx.update({'T_K': float(out['peak_K']), 'dT_K': dT})
        model.set_context(ctx['T_K'], ctx['dT_K'])
        if not out.get('diverged') and not out.get('unconverged'):
            hist.append({'f': float(f_GHz), 'T_K': ctx['T_K'], 'dT_K': dT})
        v_new, _ = model.voltage(f_GHz)
        rec.update({'dT_K': dT, 'dT_mean_K': dT_mean, 'dT_core': core, 'V_implied_V': v_new,
                    'dV_V': v_new - v_used})
        passes.append(rec)
        if abs(v_new - v_used) <= args.fmax_v_tol:
            break
    last = passes[-1]
    v_used = last['V_used_V']
    T_eval = ctx['T_K']
    dT_eval = ctx['dT_K']
    rel = model.v_max_reliability(T_eval, dT_eval)
    ceiling = model.f_max_at(T_eval, dT_eval)
    reason = None
    if last['v_clamped']:
        reason = 'sweep_end' if ceiling['limiter'] == 'sweep_end' else 'device'
    elif v_used > rel['v_max_V'] + 1e-6:
        reason = 'reliability:' + rel['binding']
    if reason is not None:
        out['unsustainable_reason'] = reason
    terms = model.period_terms(v_used, T_eval, dT_eval)
    out['fmax'] = {
        'V_used_V': v_used, 'v_clamped': last['v_clamped'], 'T_eval_K': T_eval, 'dT_eval_K': dT_eval,
        'v_max_reliability_V': rel['v_max_V'], 'reliability_binding': rel['binding'],
        'v_max_per_mechanism': {k: v['v_max_V'] for k, v in rel['per_mechanism'].items()},
        'acceleration_at_V_used': model.acceleration(v_used, T_eval, dT_eval),
        'ceiling_at_context': {k: ceiling[k] for k in ('f_max_GHz', 'v_max_V', 'limiter',
                                                        'v_device_peak_V', 'f_device_peak_GHz',
                                                        'dominant_term')},
        'period_terms': terms, 'period_dominated_by': terms['dominant'],
        'logic_depth_for_report_GHz': model.logic_depth_for(args.fmax_report_GHz, v_used, T_eval, dT_eval),
        'report_GHz': args.fmax_report_GHz,
        'n_passes': len(passes), 'passes': passes, 'unsustainable_reason': reason}
    return out


def report_arm_deltas(rows, args):
    """Print the passive and the laser term SEPARATELY, for one cooler.

    Collapsing them into a single "MR buys +x GHz" is the confound the three arms exist to
    remove. Swapping 30 um of thermal grease for 30 um of GaAs is a packaging change with no
    laser in it, and on the first three-arm runs it was the LARGER of the two terms at low
    density and the whole of the runaway rescue at high density. A licensee reading
    "photonic cooling buys 0.4 GHz" when 0.3 of it is the pixel slab's conductivity has been
    misled, whether or not anyone intended it.
    """
    by_arm = {r['arm']: r for r in rows}
    def f(arm):
        r = by_arm.get(arm)
        return r.get('f_sustainable_GHz') if r else None

    ctl, idle, on = f('control'), f('array_idle'), f('array_on')
    pad = ' ' * 14

    if args.no_array:
        # Two arms only, and the delta is not decomposable: on this path the array does not
        # exist, so there is no passive term to separate out. Say so rather than printing a
        # zero, which would read as "the material substitution is worth nothing".
        if ctl and on:
            print('{}      -> LEGACY placement, not the device: {:+.3f} GHz ({:+.1f}%) for '
                  '{:.2f} W net, cooling co-located with the transistors'
                  .format(pad, on - ctl, 100.0 * (on - ctl) / ctl,
                          by_arm['array_on'].get('p_mr_net_W', 0.0)))
        return

    if idle is not None and ctl:
        print('{}      -> PASSIVE (grease -> GaAs, 0 W of light): {:+.3f} GHz ({:+.1f}%)'
              .format(pad, idle - ctl, 100.0 * (idle - ctl) / ctl))
    elif idle is not None and ctl is None:
        print('{}      -> PASSIVE: the grease control has NO sustainable clock; the unpowered '
              'array alone reaches {:.3f} GHz'.format(pad, idle))

    # Before any laser term is printed: does the powered arm's TEMPERATURE agree with the
    # cooling it says it applied? A stale plan left on the array by a previous evaluation is
    # invisible in every recorded field and shows up only as this arithmetic. See
    # HotGauge/thermal/arm_consistency.py for the case that motivated it.
    if idle is not None and on is not None:
        check_arm_consistency(by_arm.get('array_idle', {}).get('peak_C'),
                              by_arm.get('array_on', {}).get('peak_C'),
                              by_arm['array_on'].get('heat_removed_W', 0.0),
                              label='clock_headroom {}'.format(
                                  by_arm['array_on'].get('cooling', '')))

    base = idle if idle is not None else ctl
    if on is not None and base:
        removed = by_arm['array_on'].get('heat_removed_W', 0.0) or 0.0
        if removed <= 0:
            print('{}      -> LASER: 0 W removed -- nothing was above target, so the laser term '
                  'is not applicable here rather than zero-valued'.format(pad))
        else:
            print('{}      -> LASER (idle -> on, {:.3f} W removed): {:+.3f} GHz ({:+.1f}%) for '
                  '{:.2f} W net'.format(pad, removed, on - base, 100.0 * (on - base) / base,
                                        by_arm['array_on'].get('p_mr_net_W', 0.0)))
    elif on is not None and base is None:
        print('{}      -> LASER: no arm below it has a sustainable clock, so the {:.3f} GHz is '
              'a rescue -- attribute it to whichever arm first achieved one'.format(pad, on))

    if ctl and on:
        print('{}      -> TOTAL (control -> array_on): {:+.3f} GHz ({:+.1f}%)'
              .format(pad, on - ctl, 100.0 * (on - ctl) / ctl))


def _parse_vf_source(spec):
    """``'table'`` -> None (shipped VF_PAIRS); ``'irds:<year>[:<anchor>]'`` -> an IRDSVFModel.

    Returning None for the default keeps the shipped curve as the literal default rather than a
    re-implementation of it, so existing results stay bit-identical.
    """
    spec = (spec or 'table').strip()
    if spec == 'table':
        return None
    if spec.startswith('fmax'):
        # §P0.31: the generalized f_max(V, T | logic depth, wire, skew) with V_max from an
        # Arrhenius reliability budget at the cooled temperature; anchored ONCE at the trace's
        # 3.8 GHz / 0.70 V / 330 K. 'fmax:N=10,w=0.3,ref=native,tddb_n=40,...' sets parameters.
        try:
            return load_fmax_model(**parse_fmax_spec(spec))
        except (OSError, ValueError, KeyError) as e:
            raise SystemExit('--vf-source {}: {}'.format(spec, e))
    if spec.startswith('spice'):
        # P0.18: the V/F SHAPE simulated from the ASAP7 card (I_on(V)/V on the diagonal), at the
        # tabulated temperature nearest the one asked for; anchored on the trace's clock at the
        # card's nominal supply. See HotGauge.power.device_vf.
        from HotGauge.power.device_vf import load_device_vf
        parts = spec.split(':')
        T_K = float(parts[1]) if len(parts) > 1 and parts[1] else 300.0
        try:
            return load_device_vf(T_K=T_K)
        except (OSError, ValueError, KeyError) as e:
            raise SystemExit('--vf-source {}: {} (run examples/device_vt_vf_spice.py first)'
                             .format(spec, e))
    if not spec.startswith('irds'):
        raise SystemExit("--vf-source must be 'table', 'irds:<year>[:<anchor>]', "
                         "'spice[:<T_K>]' or 'fmax[:k=v,...]', got %r" % spec)
    from HotGauge.power.irds_vf import IRDSVFModel
    parts = spec.split(':')
    year = int(parts[1]) if len(parts) > 1 and parts[1] else 2024
    anchor = parts[2] if len(parts) > 2 and parts[2] else 'wireloaded'
    try:
        return IRDSVFModel(year, anchor=anchor)
    except ValueError as e:
        raise SystemExit('--vf-source: {}'.format(e))



#: Set in main() so the nested solve callbacks can see the CLI without threading it through every
#: signature. Read-only by convention.
ARGS = None


def _peak_K_for_accounting(temps, t_floor_K=200.0):
    """Peak die temperature [K] from a temp trace, for the Carnot factor of the recovery term."""
    import numpy as _np
    vals = []
    for v in (temps.values() if hasattr(temps, 'values') else temps):
        a = _np.ravel(v)
        if a.size:
            vals.append(float(_np.max(a)))
    vals = [v for v in vals if v > t_floor_K]
    return max(vals) if vals else float('nan')

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, default=34)
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
                         "every arm shares it (and the array arms then need that stack to "
                         "carry a cooling die, or --no-array).")
    ap.add_argument('--pitch-um', type=float, default=DEFAULT_PITCH_UM,
                    help='cooling tile pitch; the array is a second powered die above the '
                         'silicon. Granularity is a SWEPT variable (ladder '
                         '50/100/200/500/1000/2000 um); a single value here holds it fixed while '
                         'the clock search sweeps. The device is a tile COUNT, annotated per die '
                         'by mr_array.device_pitch_range_um')
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
    ap.add_argument('--spreading', action='store_true',
                    help='take the cold-plate slab OUT of the stack and fold it into the boundary '
                         'as a real overhanging base (P0.4). A slab in the stack is a column of '
                         'metal the width of the die, so the package budget comes out '
                         'proportional to 1/area -- 15.5x across the die sizes here, against '
                         '2.6x with the overhang. STRONGLY preferred for anything quotable; off '
                         'by default only so results predating it reproduce.')
    ap.add_argument('--base-mm2', type=float, default=None,
                    help='cold-plate footprint [mm^2] for --spreading. Default: the socket '
                         'footprint (a fixed AREA, not a ratio of the die)')
    ap.add_argument('--mr-material', default='GAAS')
    ap.add_argument('--cell-um', type=float, default=50.0,
                    help='3D-ICE grid cell; the tile grid snaps to it')
    ap.add_argument('--no-array', action='store_true',
                    help='legacy placement: subtract the plan from the processor trace instead '
                         'of putting it on the array. An UPPER BOUND, not the device -- the '
                         'extracted watt crosses no silicon, so burial depth is inert by '
                         'construction. Retained so results predating the array reproduce.')
    ap.add_argument('--arms', nargs='+', default=list(ARMS), choices=list(ARMS),
                    help='control = grease, no cooling; array_idle = pixels at 0 W (the passive '
                         'term); array_on = pixels under the planner (the laser term, measured '
                         'against array_idle). Only meaningful with --mr.')
    ap.add_argument('--node-model', default=None, choices=sorted(NODES),
                    help='report this node\'s rated clock alongside the sustainable one')
    # --- cooling axis ---
    ap.add_argument('--cfm', type=float, default=88.0)
    ap.add_argument('--r-th', type=float, nargs='+', default=None,
                    help='sweep these sink resistances [K/W] instead of --cfm '
                         '(0.02-0.05 is liquid class)')
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    # --- clock search ---
    ap.add_argument('--f-lo', type=float, default=2.0)
    ap.add_argument('--f-hi', type=float, default=VF_TABLE_MAX_GHZ)
    ap.add_argument('--f-tol', type=float, default=0.05)
    ap.add_argument('--thermal-limit-C', type=float, default=100.0,
                    help='peak-block temperature the part must hold [C]')
    ap.add_argument('--leak-v-exponent', type=float, default=1.0,
                    help='leakage scales as V**this with clock/voltage (ASSUMPTION; 0 ignores '
                         'the voltage dependence entirely)')
    # Design A/G axes: which core is boosted, how quiet the others are, and whether a core's
    # power is concentrated into one structure. See docs/DESIGN_STUDY_PLAN.md.
    ap.add_argument('--turbo-core', type=int, default=None,
                    help='search the clock of THIS core only; the others stay at the trace '
                         'clock and are quieted by --turbo-background')
    ap.add_argument('--turbo-background', type=float, default=0.25,
                    help='activity of the non-boosted cores (with --turbo-core)')
    ap.add_argument('--density', type=float, default=None,
                    help='§P0.26: scale the trace so the die dissipates this W/mm^2 AT THE '
                         'TRACE CLOCK (3.8 GHz), exactly as the density ladders do, before the '
                         'clock search rescales from there. Without it the search starts from '
                         'the trace\'s own power (31 W on the 34-core die -- 0.31 W/mm^2 -- '
                         'where no arm ever meets a thermal limit).')
    ap.add_argument('--emphasise', default=None,
                    help="concentrate each core's power into units matching this substring, "
                         "e.g. 'Floating Point Units' (accelerator-style core)")
    ap.add_argument('--emphasis-factor', type=float, default=4.0)
    # The shipped table is not a curve for a modern node. Its error does NOT reach the power
    # numbers -- only voltage ratios are used and a common factor cancels -- but its 5.0 GHz top
    # is not a device limit, so a 'voltage-limited' verdict against it is ~20% too generous.
    # Selecting a roadmap node replaces both the curve and the ceiling. Off by default: two
    # curves inside one series is worse than either one alone.
    ap.add_argument('--vf-source', default='table',
                    help="V/F curve: 'table' (shipped VF_PAIRS, the default and what every "
                         "existing result used) or 'irds:<year>[:<anchor>]', e.g. irds:2024 or "
                         "irds:2031:cpu. The IRDS curve also caps the search at that node's "
                         "overdrive limit (~4.15 GHz for 2024) instead of 5.0 GHz. "
                         "'spice[:<T_K>]' (P0.18) takes the SHAPE from the ASAP7 card's "
                         "simulated I_on(V)/V at that temperature, anchored on the trace's "
                         "3.8 GHz at 0.70 V; needs docs/evidence/device_vt_vf_asap7.json")
    ap.add_argument('--above-vf-table', action='store_true',
                    help='allow searching past %.1f GHz, where the V/F table clamps the voltage '
                         'and the power cost of the clock is UNDERSTATED' % VF_TABLE_MAX_GHZ)
    # --- MR ---
    ap.add_argument('--mr', action='store_true', help='also search with hotspot clipping on')
    ap.add_argument('--mr-target-C', type=float, default=92.0,
                    help='absolute MR clip target [C]. NOTE this is usually the wrong policy '
                         'here -- see --mr-target-margin-K')
    # Convenience: express the target relative to the thermal limit rather than absolutely, so
    # a study that changes --thermal-limit-C does not silently change the MR coverage too.
    #
    # It does NOT fix the policy problem this sweep uncovered, and it is worth being precise
    # about why. With the clock free, MR clipped nothing exactly where cooling was worst:
    # at R_th 1.0 K/W the part settles at 2.797 GHz with a peak of 85.7 C and MR buys 0.000 GHz.
    # The tempting reading is "the 92 C target is too high, tie it to the 100 C limit" -- but
    # that point is not limited by the 100 C limit at all, it is limited by RUNAWAY at 85.7 C.
    # The leakage instability bites 14 K below the spec limit, so no target anchored to the limit
    # will ever engage there.
    #
    # A target that works at every cooling class has to be anchored to the operating point (peak
    # minus a margin) or to leakage contribution rather than temperature -- which is the
    # leakage-ranked policy in docs/GAMEPLAN.md, and needs its own study rather than a flag.
    ap.add_argument('--mr-target-margin-K', type=float, default=None,
                    help='set the MR target this many K below the THERMAL LIMIT instead of at a '
                         'fixed temperature (8 -> 92 C when the limit is 100 C). Note this does '
                         'not help where the binding constraint is runaway below the limit. '
                         'Overrides --mr-target-C.')
    ap.add_argument('--eta-asf', type=float, default=DEFAULT_ETA_ASF)
    ap.add_argument('--eta-laser', type=float, default=DEFAULT_LASER_WALLPLUG)
    ap.add_argument('--eta-lpc', type=float, default=DEFAULT_LPC_EFFICIENCY)
    ap.add_argument('--mr-h-max', type=float, default=DEFAULT_H_MAX_W_PER_MM2)
    ap.add_argument('--mr-dt-max', type=float, default=DEFAULT_DT_MAX_K)
    ap.add_argument('--mr-iter', type=int, default=6)
    ap.add_argument('--mr-extractor', default='none', choices=['none'] + sorted(EXTRACTORS),
                    help='§P0.19: the extractor platform whose cooling curve caps each tile at '
                         'delivery (dye = the v98/v100 target device). none = the recorded rows.')
    ap.add_argument('--mr-envelope-shape', default='seed', choices=('seed', 'power'),
                    help="§P0.29: the planner's envelope shape. seed = every recorded clock row "
                         "(a uniform per-block allotment, an upper bound); power = each block "
                         "capped at its own dissipation (18-33 %% cheaper on the rescue ladder). "
                         "Quote every plan with its shape.")
    # §P0.31: the generalized f_max model's self-consistency loop and its 'what would 10 GHz need'
    ap.add_argument('--fmax-v-tol', type=float, default=0.005,
                    help='re-solve a candidate clock while the supply implied by the solved '
                         'temperature/gradient moves by more than this [V] (fmax source only). '
                         '5 mV is ~0.03 GHz on the card, under the 0.05 GHz bisection tolerance')
    ap.add_argument('--fmax-max-passes', type=int, default=3)
    ap.add_argument('--fmax-report-GHz', type=float, default=10.0,
                    help='report the logic depth at which the solved operating point would '
                         'clock this [GHz] (fmax source only)')
    # Design E: 'clip' targets hot blocks (the assumption behind every MR result here);
    # 'distributed' spreads a fixed budget over the die, which is the control that tests it.
    ap.add_argument('--mr-mode', default='clip', choices=('clip', 'distributed'))
    ap.add_argument('--mr-budget-W', type=float, default=1.0,
                    help='heat to remove [W] in distributed mode; set it to the clipping run\'s '
                         'Q so the two are compared at equal cooling')
    ap.add_argument('--mr-weight', default='area', choices=('area', 'uniform'))
    ap.add_argument('--mr-plan-mode', default='auto', choices=('auto', 'baseline', 'envelope'),
                    help='how the MR plan is sized; auto switches to the envelope-anchored '
                         'descent when the uncooled die has no steady state')
    ap.add_argument('--spot-min-um', type=float, default=DEFAULT_SPOT_MIN_UM)
    ap.add_argument('--spot-policy', default=DEFAULT_SPOT_POLICY,
                    choices=('dilute', 'exclude', 'ideal'))
    # --- solver ---
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
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=60)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--no-verify', action='store_true')
    ap.add_argument('--verify-tol', type=float, default=1.0)
    ap.add_argument('--flops-per-cycle', type=float, default=DEFAULT_FLOPS_PER_CYCLE)
    ap.add_argument('--derate-per-K', type=float, default=0.001)
    ap.add_argument('--no-server', action='store_true')
    ap.add_argument('--recovery-at-junction', action='store_true',
                    help='bound the LPC recovery by the Carnot factor of the junction the heat is '
                         'lifted from (v91 eq. 1.14-1.16). Without it the ledger uses the phi -> 1 '
                         'limit, which overstates recovery at every finite temperature')
    ap.add_argument('--T0-K', type=float, default=295.0,
                    help='sink temperature for the Carnot factor, with --recovery-at-junction')
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()
    # §P0.16: under a non-stock core_other policy, solve against a corrected copy of
    # the trace. Returns args.trace_dir unchanged under the default, so the recorded
    # path is byte-identical.
    args.trace_dir = resolve_trace_dir(args.trace_dir, args.core_other_policy)
    global ARGS
    ARGS = args
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'clock_headroom'))
    os.makedirs(args.out_dir, exist_ok=True)
    args.session_cache = None if args.no_server else ICESessionCache()
    args._vf_model = _parse_vf_source(args.vf_source)
    # An explicit --f-hi is the caller's; the DEFAULT is the shipped table's top and would be a
    # silent 5.0 GHz ceiling on a node whose real ceiling is lower. Let the model set it.
    args._fmax_ctx = {}
    args._fmax_hist = {}
    if isinstance(args._vf_model, GeneralizedFmaxModel):
        # The ceiling is now a property of the SOLVED temperature, so the search is not capped
        # in advance: its top is the most optimistic clock the card admits (the device's peak
        # clock in the anchor context) and every candidate carries its own limit by name.
        if args.f_hi == VF_TABLE_MAX_GHZ:
            args.f_hi = args._vf_model.device_peak(args._vf_model.T_anchor,
                                                   args._vf_model.p['dT_anchor_K'])[1]
    elif args._vf_model is not None and args.f_hi == VF_TABLE_MAX_GHZ:
        args.f_hi = args._vf_model.f_max

    node_obj = NODES[args.node_model] if args.node_model else None
    if node_obj is not None:
        args.tech_node = node_obj.tech_node
        args.node = '{}nm'.format(node_obj.tech_node)

    if args.leakage_curve != 'pipeline':
        # `[!]` §P0.14 predicts this study should move MORE than the density ladder did. The
        # ladder is a divergence test, decided by d(ln P_leak)/dT at the temperature the die
        # reaches; this search is temperature-LIMITED -- it asks for the highest clock that holds
        # a limit -- so a curve that is steeper through the whole operating band (the simulated
        # one carries ~9x more feedback gain at 320 K) eats headroom continuously rather than only
        # at the cliff. A prediction worth recording before the run, and worth withdrawing in the
        # docs if it comes out otherwise.
        leak_model, t_ref = load_leakage_model(args.leakage_curve,
                                               calibration=args.leakage_cal, extrapolate=True)
        leak_src = 'leakage curve {!r} (P0.13/P0.14)'.format(args.leakage_curve)
    elif os.path.isfile(args.leakage_cal):
        leak_model, t_ref = load_calibrated_leakage_model(args.leakage_cal, extrapolate=True)
        leak_src = 'MEASURED McPAT curve + Arrhenius tail above 400 K'
    else:
        leak_model = LeakageModel.exponential(15.0)
        t_ref = mcpat_tref_from_trace_dir(args.trace_dir) or 330.0
        leak_src = 'assumed exponential'
    fmax = FMaxModel.linear_derate(args.derate_per_K)
    thermal_limit_K = args.thermal_limit_C + 273.15
    if args.mr_target_margin_K is not None:
        args.mr_target_K = thermal_limit_K - args.mr_target_margin_K
        mr_target_note = '{:.1f} C  (thermal limit - {:.1f} K)'.format(
            args.mr_target_K - 273.15, args.mr_target_margin_K)
    else:
        args.mr_target_K = args.mr_target_C + 273.15
        mr_target_note = '{:.1f} C  (absolute)'.format(args.mr_target_C)

    # Baseline trace at the trace's own clock; the search rescales it per candidate clock.
    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    split = os.path.join(args.trace_dir, os.path.basename(files[0]).replace(
        'block_powers_', 'block_powers_split_'))
    leak_ref_base = {}
    if os.path.isfile(split):
        with open(split) as f:
            leak_ref_base = {u: np.array([float(v[1])]) for u, v in json.load(f).items()}

    flp = floorplan_path(args.flp_dir, args.node, args.cores)
    if not os.path.isfile(flp):
        print('no floorplan for {} {}-core: {}'.format(args.node, args.cores, flp))
        return 1
    area_m2 = chip_area_m2_from_floorplan(flp)
    base = (replicate_trace_cores(base0, args.cores, n_src=args.trace_cores)
            if args.cores > args.trace_cores else base0)
    # Design shape first (constant core power), then activity. Both are properties of the part
    # and the workload, not of the clock, so they are applied before the clock search begins.
    if args.emphasise:
        base = emphasise_units(base, args.emphasise, args.emphasis_factor)
    if args.turbo_core is not None:
        base = scale_cores(base, single_core_turbo(args.cores, args.turbo_core,
                                                   args.turbo_background))
    if args.density is not None:
        # §P0.26: the operating point in W/mm^2 at the trace clock; the leakage reference is a
        # per-unit power and scales with the trace it references.
        base, _dscale, _ = scale_trace_to_die_power(base, flp, args.tech_node,
                                                    args.density * area_m2 * 1e6,
                                                    num_cores=args.cores)
        if leak_ref_base:
            leak_ref_base = {u: v * _dscale for u, v in leak_ref_base.items()}
    # `[!]` RBB policy: applied ONCE here, after every other trace transform (replication,
    # emphasis, turbo) and before the clock search rescales anything -- so p_ref, every candidate
    # clock and the accounting all see one power map. The leakage reference moves with it;
    # rescale_trace rebuilds power as `series - leak + leak*scale(T)`, so a zeroed series with a
    # live leakage entry would re-inject the bus. See HotGauge.thermal.rbb.
    base, leak_ref_base, rbb_meta = amortize_rbb(
        base, flp, policy=args.rbb_policy, leakage_ref=leak_ref_base or None,
        span=args.rbb_span, name_map=mcpat_flp_name_map(include_core_idx=(args.cores > 1)))
    leak_ref_base = leak_ref_base or {}

    p_ref = die_power_of_trace(base, flp, args.tech_node, num_cores=args.cores)
    fp = Floorplan.from_file(flp)
    geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                     'min_dim_um': float(min(e.width, e.height))} for e in fp.elements}
    name_map = mcpat_flp_name_map(include_core_idx=(args.cores > 1))

    print('sustainable-clock search  ({} , {}-core, {:.1f} mm^2)'.format(
        args.node, args.cores, area_m2 * 1e6))
    print('  trace    : {:.1f} W on the die at {:.1f} GHz ({:.3f} W/mm^2)'.format(
        p_ref, TRACE_REFERENCE_GHZ, p_ref / (area_m2 * 1e6)))
    print('  limit    : peak block <= {:.0f} C, damping-verified solves only'.format(
        args.thermal_limit_C))
    if args._vf_model is None:
        print('  V/F      : shipped VF_PAIRS, ceiling {:.2f} GHz  (NOT a modern-node curve: it '
              'asks ~2x the IRDS 2024 Vdd, so this ceiling is ~20% too generous)'
              .format(VF_TABLE_MAX_GHZ))
    else:
        print('  V/F      : {}'.format(args._vf_model))
        print('             ceiling {:.3f} GHz at {:.3f} V; power multipliers agree with the '
              'shipped table to ~6% (only ratios are used, so the level cancels)'
              .format(args._vf_model.f_max, args._vf_model.v_max))
    if args.emphasise:
        print('  design   : {!r} x{:.2f} at constant core power'.format(
            args.emphasise, args.emphasis_factor))
    if args.turbo_core is not None:
        print('  turbo    : core {} clocked alone, others at {:.2f} activity'.format(
            args.turbo_core, args.turbo_background))
    print('  leakage  : {}, +V^{:.2g} with clock (assumption)'.format(
        leak_src, args.leak_v_exponent))
    if args.mr:
        print('  MR target: {}'.format(mr_target_note))
    if node_obj is not None:
        print(describe_assumptions())
        print('  rated    : {} = {:.2f} GHz'.format(node_obj.name, node_obj.f_nominal_GHz))
    print()

    coolers = [(r, None) for r in (args.r_th or [])] or [(None, args.cfm)]
    arms = arms_for(args)
    if args.mr:
        print('  arms     : {}   ({})'.format(
            ' -> '.join(arms),
            'legacy in-source-layer placement, no array die' if args.no_array
            else 'grease -> GaAs at 0 W -> GaAs under the planner, at {:.0f} um pitch'
                 .format(args.pitch_um)))
    hdr = ('{:>14s} {:>10s} {:>9s} {:>8s} {:>8s} {:>8s} {:>9s} {:>10s}  {}'.format(
        'cooling', 'arm', 'f_sust', 'peak C', 'P_die W', 'W/mm^2', 'P_cool W', 'GFLOP/s',
        'limited by'))
    print(hdr)
    print('-' * len(hdr))

    rows = []
    for r_th, cfm in coolers:
        sink = make_sink(args, area_m2, r_th)
        label = ('R_th {:.3g}'.format(r_th) if r_th is not None
                 else '{:.0f} CFM'.format(cfm))
        tag = ('rth{:g}'.format(r_th) if r_th is not None else 'cfm{:g}'.format(cfm))
        for arm in arms:
            use_mr = (arm == 'array_on')
            sub = '{}_{}'.format(tag, arm)
            # The stack is per ARM, not per cooler: the arms differ by exactly the 30 um layer
            # and share everything else, including the sink.
            stack_spec = arm_stack_spec(args, arm)
            arm_sink = sink
            if args.spreading:
                arm_sink = spreading_sink_for_stack(stack_spec, sink, area_m2 * 1e6,
                                                    base_area_mm2=args.base_mm2)
            stack = render_stack_with_sink(get_stack_template(stack_spec), arm_sink,
                                           os.path.join(args.out_dir, 'stacks', sub + '.stk'))
            # Placement is derived from the STACK rather than from --mr, because the two can
            # disagree silently in both directions: tiles wired against a single-die stack
            # compute a plan that lands nowhere, and an array stack left unwired carries an
            # inert slab that only adds resistance.
            wiring = (None if (arm == 'control' or args.no_array)
                      else wiring_for_stack(stack, flp,
                                            os.path.join(args.out_dir, 'array', sub),
                                            want_array=True, pitch_um=args.pitch_um,
                                            cell_um=args.cell_um,
                                            coverage=args.array_coverage))
            seen = {}

            def evaluate(f, _sub=sub, _mr=use_mr, _sink=arm_sink, _stack=stack, _w=wiring):
                r = evaluate_clock(args, flp, base, leak_ref_base, geom, name_map, leak_model,
                                   t_ref, args.cores, _sink, _stack, _mr, f, _sub, wiring=_w)
                seen[round(f, 6)] = r
                return r

            _gen = isinstance(args._vf_model, GeneralizedFmaxModel)
            if _gen:
                # each arm starts its context afresh at the anchor; the candidates then inherit
                args._fmax_ctx.pop(sub, None)
                args._fmax_hist.pop(sub, None)
            search = find_max_sustainable_clock(
                evaluate, args.f_lo, args.f_hi, tol_GHz=args.f_tol,
                thermal_limit_K=thermal_limit_K, vf_model=args._vf_model,
                cap_at_vf_table=(not args.above_vf_table) and not _gen)

            f_s = search['f_sustainable_GHz']
            best = seen.get(round(f_s, 6)) if f_s is not None else None
            row = {'cooling': label, 'r_th': r_th, 'cfm': cfm, 'mr': use_mr,
                   # 'mr' is kept for the summarisers that already read it, but 'arm' is what
                   # identifies the point: mr:false is now either the grease control or the
                   # unpowered array, and those are different physics.
                   'arm': arm, 'stack_spec': arm_stack_spec(args, arm),
                   'placement': ('array_above' if wiring
                                 else 'in_source_layer' if use_mr else 'none'),
                   'n_tiles': len(wiring.tiles) if wiring else 0,
                   'pitch_um': args.pitch_um if wiring else None,
                   **(wiring.area_fields() if wiring else {}),
                   'burial_um': args.burial_um,
                   'f_sustainable_GHz': f_s, 'limited_by': search['limited_by'],
                   'at_ceiling': search['at_ceiling'],
                   'vf_clamped': search['vf_clamped'],
                   'bracket_GHz': search['bracket_GHz'],
                   'evaluations': [{k: v for k, v in e.items()} for e in search['evaluations']],
                   'fan_W': sink.parasitic_power_W(),
                   'rated_GHz': node_obj.f_nominal_GHz if node_obj else None}
            if isinstance(args._vf_model, GeneralizedFmaxModel):
                # §P0.31: the generalized model's diagnostics at the sustainable clock and at
                # every candidate, so the row names its limiter and its period's composition.
                row['fmax'] = (best or {}).get('fmax')
                row['fmax_evaluations'] = [
                    {'f_GHz': e['f_GHz'], 'sustainable': e['sustainable'], 'reason': e['reason'],
                     **{k: v for k, v in ((seen.get(round(e['f_GHz'], 6)) or {}).get('fmax') or {}).items()
                        if k in ('V_used_V', 'T_eval_K', 'dT_eval_K', 'v_max_reliability_V',
                                 'reliability_binding', 'period_dominated_by', 'n_passes',
                                 'unsustainable_reason')}}
                    for e in search['evaluations']]
                row['mr_envelope_shape'] = args.mr_envelope_shape if use_mr else None
                row['mr_extractor'] = args.mr_extractor if use_mr else None
            if best is not None and best.get('peak_K'):
                p_cool = sink.parasitic_power_W() + best['p_mr_net_W']
                g = f_s * args.flops_per_cycle * args.cores
                row.update({'peak_C': K_to_C(best['peak_K']),
                            'peak_block': best.get('peak_block'),
                            'p_chip_W': best['p_chip_W'],
                            'density_W_per_mm2': best['p_chip_W'] / (area_m2 * 1e6),
                            'p_mr_net_W': best['p_mr_net_W'],
                            'heat_removed_W': best['heat_removed_W'],
                            'p_cool_W': p_cool, 'gflops': g,
                            'gflops_per_total_W': g / (best['p_chip_W'] + p_cool)})
                print('{:>14s} {:>10s} {:>9.3f} {:>8.1f} {:>8.1f} {:>8.3f} {:>9.2f} {:>10.1f}  {}'
                      .format(label, arm, f_s, row['peak_C'],
                              row['p_chip_W'], row['density_W_per_mm2'], p_cool, g,
                              row['limited_by']
                              + (' (SEARCH CEILING, not the part)' if search['at_ceiling']
                                 else '')
                              + (' [V/F CLAMPED]' if search['vf_clamped'] else '')))
            else:
                print('{:>14s} {:>10s} {:>9s} {:>8s} {:>8s} {:>8s} {:>9s} {:>10s}  {}'.format(
                    label, arm, 'none', '--', '--', '--', '--', '--',
                    'no sustainable clock >= {:.2f} GHz ({})'.format(
                        args.f_lo, row['limited_by'])))
            # Stamped per row: the two RBB policies are not comparable and a row that
            # does not say which one produced it is unusable.
            row['rbb_policy'] = args.rbb_policy
            rows.append(row)

        if args.mr:
            report_arm_deltas(rows[-len(arms):], args)

    out = os.path.join(args.out_dir, 'clock_headroom.json')
    with open(out, 'w') as f:
        json.dump({'node': args.node, 'cores': args.cores, 'area_mm2': area_m2 * 1e6,
                   'rbb_policy': args.rbb_policy, 'rbb': rbb_meta,
                   'p_ref_W': p_ref, 'trace_GHz': TRACE_REFERENCE_GHZ,
                   'density_at_trace_clock': args.density,
                   'thermal_limit_C': args.thermal_limit_C,
                   'leak_v_exponent': args.leak_v_exponent,
                   'vf_source': args.vf_source,
                   'vf_model': None if args._vf_model is None else repr(args._vf_model),
                   'vf_ceiling_GHz': (VF_TABLE_MAX_GHZ if args._vf_model is None
                                      else args._vf_model.f_max),
                   'turbo_core': args.turbo_core, 'turbo_background': args.turbo_background,
                   'emphasise': args.emphasise, 'emphasis_factor': args.emphasis_factor,
                   'mr_mode': args.mr_mode, 'mr_budget_W': args.mr_budget_W,
                   'mr_target_C': args.mr_target_K - 273.15,
                   'mr_target_margin_K': args.mr_target_margin_K,
                   # The array configuration, so a row can be identified without the log. A
                   # result whose placement is unknown cannot be compared with anything.
                   'arms': list(arms), 'stack': args.stack, 'no_array': bool(args.no_array),
                   'spreading': bool(args.spreading), 'base_mm2': args.base_mm2,
                   'pitch_um': args.pitch_um, 'burial_um': args.burial_um,
                   'array_coverage': args.array_coverage,
                   'mr_material': args.mr_material, 'cell_um': args.cell_um,
                   'mr_extractor': args.mr_extractor, 'mr_envelope_shape': args.mr_envelope_shape,
                   'fmax_model': (args._vf_model.describe()
                                  if isinstance(args._vf_model, GeneralizedFmaxModel) else None),
                   'rated_GHz': node_obj.f_nominal_GHz if node_obj else None,
                   'rows': rows}, f, indent=2)
    print('\n  written: {}'.format(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
