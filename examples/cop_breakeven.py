#!/usr/bin/env python
"""At what COP does microrefrigeration beat simply buying more cooling?

    python examples/cop_breakeven.py --cores 34 --density 1.10 --cfm 88 --target-C 98

Why this framing
----------------
Every result so far asks "is MR worth it at COP 0.14?" and the answer keeps coming back "only in
a narrow band". That is a verdict, and a verdict is not actionable. Inverting it gives a **target**
instead: hold the engineering fixed, and ask what COP the device would have to reach for MR to be
the cheaper way to hold a given temperature. A device team can aim at a number.

The comparison, in one currency
-------------------------------
Both arms are priced in **watts of system power**, which is the only currency this model can
honestly compute (dollars, volume and reliability are not modelled and are not guessed at):

    air arm : spin the fan faster until the die holds the target
              cost = P_die(faster air) + P_fan(faster air)
    MR arm  : keep the fan where it is and clip the hot blocks
              cost = P_die(with MR)    + P_fan(baseline) + P_MR(net electrical)

Both arms get the leakage credit they earn -- a cooler die leaks less -- because each is a full
coupled solve rather than an arithmetic adjustment.

Setting the two equal and solving for the efficiency gives the break-even:

    COP_breakeven = Q_billed * (1 - recovery_ratio) / budget
    budget        = [P_die(air) + P_fan(air)] - [P_die(MR) + P_fan(base)]

``budget`` is what the air arm spends that the MR arm does not. ``Q_billed`` is heat removed,
billed at the pixel rather than the block where the spot is wider than the target (the dilution
the spot-policy work fixed). ``recovery_ratio`` is the LPC's return, so this is a break-even on
the *net* cost, consistent with ``mr_accounting``.

The three answers, and only one of them is a number
---------------------------------------------------
1. **Air cannot reach the target at any airflow.** Then there is no budget to compare against and
   MR wins at *any* positive COP -- the alternative does not exist. Expect this above the
   constriction floor: beta saturates near 1.27 K/W above ~250 CFM, so past that point more air
   does essentially nothing for a hotspot however much fan power it burns.
2. **Air reaches it more cheaply than MR ever could** (``budget`` small or negative). MR loses at
   every COP, and no device improvement rescues it.
3. **A finite break-even COP.** Compare it against the modelled 0.14, and against the device-side
   break-even already in ``mr_accounting`` -- eta_ASF >= 0.587 makes MR net-free at the shipped
   laser and LPC efficiencies, which is a different and independent question.

What this does NOT cost
-----------------------
Fan power is modelled (``simscale_fan_power``); **pump and chiller power for a liquid loop are
not**, so ``--r-th`` points cannot be used as the air arm here and the script refuses them. Nor
does it price hardware, integration, or the laser's own capital cost. This is an operating-power
break-even and nothing more, which makes it a *lower bound* on the COP MR really needs.
"""
import os
import sys
import json
import argparse
import logging

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_HERE, '..', 'HotGauge'))

from HotGauge.power import BasicPowerTrace, LeakageModel
from HotGauge.configuration import load_block_powers
from HotGauge.thermal import get_stack_template, ICEThermalSolver, run_leakage_feedback
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, replicate_trace_cores,
                                               load_calibrated_leakage_model, die_power_of_trace,
                                               mcpat_tref_from_trace_dir, mcpat_flp_name_map)
from HotGauge.thermal.sink_models import (BaffledFinSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan, simscale_fan_power,
                                          simscale_beta, simscale_alpha)
from HotGauge.thermal.ice_server import ICESessionCache, shared_cache
from HotGauge.thermal.microrefrigeration import MRParams, run_mr_clipping, mr_accounting
from HotGauge.thermal.stack_models import coarsen_stack_grid
from HotGauge.thermal.accelerator_floorplan import (ga100_geometry, ga100_floorplan,
                                                    ga100_block_powers, block_areas_mm2,
                                                    kernel_activity, KERNELS)

LOGGER = logging.getLogger('cop_breakeven')
T_FLOOR_K = 273.15


def floorplan_path(flp_dir, node, n):
    return os.path.join(flp_dir, 'skylake{}_{}core_3_3D-ICE_template.flp'.format(node, n))


class Point(object):
    """One coupled solve at a given airflow, with or without MR."""

    def __init__(self, args, flp, trace, leak_ref, geom, name_map, leak_model, t_ref,
                 area_m2, n_cores, already_dice_named=False, cell_um=None):
        self.__dict__.update(locals())
        del self.self

    def run(self, cfm, use_mr, tag):
        a = self.args
        sink = BaffledFinSink(cfm, self.area_m2, ambient_K=a.ambient_K)
        stack = render_stack_with_sink(get_stack_template(a.stack), sink,
                                       os.path.join(a.out_dir, 'stacks', tag + '.stk'))
        if self.cell_um:
            coarsen_stack_grid(stack, self.cell_um)
        counter = {'n': 0}
        ver = {'n_solves': 0, 'n_unconverged': 0}

        def solve(tr):
            counter['n'] += 1
            r = run_leakage_feedback(
                tr, self.leak_ref,
                ICEThermalSolver(stack, self.flp, a.tech_node,
                                 run_base_dir=os.path.join(a.out_dir, tag,
                                                           'it{:02d}'.format(counter['n'])),
                                 initial_temp=a.ambient_K, num_cores=self.n_cores,
                                 single_thread=True, mode='steady',
                                 session_cache=a.session_cache,
                                 already_dice_named=self.already_dice_named),
                model=self.leak_model, T_ref=self.t_ref, num_cores=self.n_cores,
                tol_K=a.tol, max_iter=a.max_iter, relax=a.relax, t_floor_K=T_FLOOR_K,
                # The accelerator trace is keyed by floorplan block name, so it needs the
                # identity map; the CPU trace is McPAT-named and needs the McPAT bridge. Getting
                # this wrong does not raise -- it silently disables the leakage feedback.
                bridge_aggregates=not self.already_dice_named,
                name_map=((lambda u: u) if self.already_dice_named else None),
                verify=True)
            solve.last = r
            ver['n_solves'] += 1
            if r.get('unconverged'):
                ver['n_unconverged'] += 1
            return r['temp_trace']

        mr = MRParams(target_K=a.target_C + 273.15, h_max=a.mr_h_max, dt_max_K=a.mr_dt_max,
                      eta_asf=a.eta_asf, laser_wallplug=a.eta_laser, lpc_efficiency=a.eta_lpc,
                      spot_min_um=a.spot_min_um, spot_policy=a.spot_policy)

        def status():
            r = getattr(solve, 'last', None) or {}
            return {'diverged': bool(r.get('diverged')), 'unconverged': bool(r.get('unconverged'))}

        res = None
        if use_mr:
            res = run_mr_clipping(self.trace, solve, self.geom, mr, self.name_map,
                                  max_iter=a.mr_iter, tol_K=2.0, relax=0.7,
                                  status_fn=status, plan_mode='auto')
            temps, acc = res['temp_trace'], res['accounting']
            unconv = bool(res.get('result_unconverged'))
            diverged = bool(res.get('temp_trace_diverged'))
            holds = res.get('plan_holds_target')
            minimal = res.get('plan_is_minimum')
            mr_reason = res.get('reason')
            dt_bound = res.get('dt_max_bound')
        else:
            temps = solve(self.trace)
            acc = mr_accounting({}, mr)
            last = getattr(solve, 'last', None) or {}
            unconv, diverged = bool(last.get('unconverged')), bool(last.get('diverged'))
            holds = minimal = mr_reason = dt_bound = None

        peak_K = None
        if temps and not diverged:
            vals = [float(np.ravel(v)[-1]) for v in temps.values()]
            vals = [v for v in vals if v > T_FLOOR_K]
            peak_K = max(vals) if vals else None

        last = getattr(solve, 'last', None) or {}
        p_die = None
        if last.get('power_trace') is not None and not diverged:
            # already_dice_named has to travel here too: this is a SECOND route into
            # prepare_dice_trace, and it crashed on 'Processor/Total L3s' long after the solve
            # itself had succeeded -- a die with no cores has no L3 to split across them.
            p_die = die_power_of_trace(last['power_trace'], self.flp, a.tech_node,
                                       num_cores=self.n_cores,
                                       already_dice_named=self.already_dice_named)

        return {'cfm': float(cfm), 'mr': bool(use_mr),
                'peak_C': None if peak_K is None else peak_K - 273.15,
                'p_die_W': p_die, 'p_fan_W': float(simscale_fan_power(cfm)),
                'q_removed_W': float(acc.get('heat_removed_W', 0.0)),
                'q_billed_W': float(acc.get('heat_billed_W', acc.get('heat_removed_W', 0.0))),
                'p_mr_net_W': float(acc.get('electrical_power_W', 0.0)),
                'p_mr_gross_W': float(acc.get('electrical_gross_W', 0.0)),
                'recovery_ratio': float(acc.get('breakeven_ratio', 0.0)),
                # mr_accounting already computes this; recomputing it here would be a second
                # definition of the same quantity, which is how two numbers come to disagree.
                'effective_cop': acc.get('effective_cop'),
                'net_generating': bool(acc.get('net_generating', False)),
                'n_targets': len(res['plan']) if res and res.get('plan') else 0,
                'diverged': diverged, 'unconverged': unconv, 'holds_target': holds,
                # Direction of error matters and it is NOT the same on both paths. A truncated
                # BASELINE descent is still building the plan, so it understates cost. A truncated
                # ENVELOPE descent starts at full device capability and relaxes down, so it
                # OVERSTATES it -- which is how a target-98 rescue that the margin curve prices at
                # 0.29 W over 4 blocks came back at 131 W over 1126.
                'plan_is_minimum': minimal, 'mr_reason': mr_reason, 'dt_max_bound': dt_bound,
                'n_solves': ver['n_solves'], 'n_unconverged_solves': ver['n_unconverged']}



def _setup_ga100(args, leak_model, t_ref):
    """Build the accelerator die as a Point, in the same shape the CPU path produces.

    The GA100 floorplan has no cores, no McPAT names and no L3, so the trace is keyed by floorplan
    element name directly and the solver is told ``already_dice_named``. Everything downstream --
    the airflow bisection, the MR arm, the accounting -- is identical, which is the point: the two
    dies must be priced by the same procedure or the comparison means nothing.
    """
    g = ga100_geometry()
    flp = os.path.join(args.out_dir, 'ga100.flp')
    flp, classes = ga100_floorplan(flp, split_sm=True, geom=g, cell_um=args.cell_um)
    areas = block_areas_mm2(flp)
    area_mm2 = g['w_die'] * g['h_die']
    power_W = (args.density * area_mm2) if args.density is not None else args.die_power_W

    activity, kmeta = kernel_activity(classes, kernel=args.kernel, n_active=args.n_active,
                                      placement=args.placement)
    powers, pmeta = ga100_block_powers(power_W, classes, activity=activity)
    realised = pmeta['realised_W']
    trace = BasicPowerTrace({u: np.array([p]) for u, p in powers.items()}, 1.0)
    leak_ref = {u: p * 0.25 for u, p in powers.items()}

    mins = {}
    cur = None
    with open(flp) as f:
        for line in f:
            t = line.strip()
            if t.endswith(':'):
                cur = t[:-1].strip()
            elif t.startswith('dimension') and cur:
                w, h = [float(v) for v in t[len('dimension'):].strip(' ;').split(',')]
                mins[cur] = min(w, h)
    geom = {n: {'area_mm2': a_mm2, 'min_dim_um': mins.get(n, 1e9)} for n, a_mm2 in areas.items()}

    P = Point(args, flp, trace, leak_ref, geom, (lambda u: u), leak_model, t_ref,
              area_mm2 / 1e6, 1, already_dice_named=True, cell_um=args.cell_um)
    extra = {'kernel': kmeta, 'n_blocks': len(classes), 'nominal_W': power_W,
             'realised_W': realised, 'grid_um': args.cell_um}
    return P, area_mm2 / 1e6, realised, extra


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--die', default='cpu', choices=('cpu', 'ga100'),
                    help="which die. 'cpu' is the 34-core Skylake-derived floorplan; 'ga100' is "
                         "the die-shot-derived accelerator (826 mm^2, 367 blocks). The COP "
                         "break-even is the first MATRIX-DIVERSE study in this project -- each "
                         "airflow trial is a new system matrix -- so on ga100 it is also the "
                         "workload that decides whether the GPU solver port pays "
                         "(docs/SOLVER_ROADMAP.md)")
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--density', type=float, default=None,
                    help='W/mm^2. Defaults to 1.10 for --die cpu; for --die ga100 leave unset and '
                         'use --die-power-W instead, since an accelerator is TDP-limited rather '
                         'than density-limited')
    ap.add_argument('--cfm', type=float, default=88.0, help='baseline airflow')
    ap.add_argument('--cfm-max', type=float, default=600.0,
                    help='most airflow the air arm may buy. Beta saturates near 250 CFM, so '
                         'past that the fan burns power for almost no hotspot benefit')
    ap.add_argument('--target-C', type=float, default=98.0,
                    help='peak temperature BOTH arms must hold')
    ap.add_argument('--cfm-tol', type=float, default=4.0)
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--leakage-cal-default-note', default=None, help=argparse.SUPPRESS)
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--ambient-K', type=float, default=308.15)
    ap.add_argument('--leakage-cal',
                    # See the note in accelerator_study.py: the measured curve is in
                    # leakage_calibration/, not docs/evidence/.
                    default=os.path.join(_REPO, 'leakage_calibration',
                                         'leakage_calibration.json'))
    ap.add_argument('--tol', type=float, default=0.05)
    ap.add_argument('--max-iter', type=int, default=120)
    ap.add_argument('--relax', type=float, default=0.5)
    ap.add_argument('--mr-iter', type=int, default=25)
    ap.add_argument('--mr-h-max', type=float, default=10.0)
    ap.add_argument('--mr-dt-max', type=float, default=10.0)
    ap.add_argument('--eta-asf', type=float, default=0.20)
    ap.add_argument('--eta-laser', type=float, default=0.70)
    ap.add_argument('--eta-lpc', type=float, default=0.90)
    ap.add_argument('--spot-min-um', type=float, default=10.0)
    ap.add_argument('--spot-policy', default='dilute')
    # --- ga100 only ---
    ap.add_argument('--die-power-W', type=float, default=700.0,
                    help='accelerator die power [W] (--die ga100). 700 is H100 class, and is '
                         'where the accelerator actually needs cooling')
    ap.add_argument('--cell-um', type=float, default=100.0,
                    help='thermal grid for --die ga100; 100 is validated against 50 to 0.01 K')
    ap.add_argument('--kernel', default='uniform', choices=list(KERNELS))
    ap.add_argument('--n-active', type=int, default=None)
    ap.add_argument('--placement', default='contiguous',
                    choices=('contiguous', 'scattered', 'cluster'))
    ap.add_argument('--dt-max-K', type=float, default=10.0,
                    help='MR temperature lift. On the accelerator at 700 W this BINDS -- the die '
                         'needs 12.6-30 K -- so a break-even priced at 10 K is a break-even on a '
                         'target MR cannot reach. See docs/ACCELERATOR.md')
    ap.add_argument('--no-server', action='store_true')
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'cop_breakeven'))
    os.makedirs(args.out_dir, exist_ok=True)
    args.session_cache = None if args.no_server else shared_cache()
    if args.density is None and args.die == 'cpu':
        args.density = 1.10

    leak_model, t_ref = (load_calibrated_leakage_model(args.leakage_cal, extrapolate=True)
                         if os.path.isfile(args.leakage_cal)
                         else (LeakageModel.exponential(15.0),
                               mcpat_tref_from_trace_dir(args.trace_dir) or 330.0))

    extra = None
    if args.die == 'ga100':
        P, area_m2, power_W, extra = _setup_ga100(args, leak_model, t_ref)
        args.mr_dt_max = args.dt_max_K          # the accelerator's binding parameter
        flp = P.flp
    else:

        flp = floorplan_path(args.flp_dir, args.node, args.cores)
        if not os.path.isfile(flp):
            raise SystemExit('no floorplan at {}'.format(flp))
        area_m2 = chip_area_m2_from_floorplan(flp)
        power_W = args.density * area_m2 * 1e6

        files = load_block_powers(args.trace_dir)
        with open(files[0]) as f:
            first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
        base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
        base = (replicate_trace_cores(base0, args.cores, n_src=args.trace_cores)
                if args.cores > args.trace_cores else base0)
        trace, scale, _ = scale_trace_to_die_power(base, flp, args.tech_node, power_W,
                                                   num_cores=args.cores)
        split = os.path.join(args.trace_dir,
                             os.path.basename(files[0]).replace('block_powers_',
                                                                'block_powers_split_'))
        leak_ref = {}
        if os.path.isfile(split):
            with open(split) as f:
                leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}
        fp = Floorplan.from_file(flp)
        geom = {e.name: {'area_mm2': (e.width * e.height) / 1.0e6,
                         'min_dim_um': float(min(e.width, e.height))} for e in fp.elements}
        name_map = mcpat_flp_name_map(include_core_idx=(args.cores > 1))
        P = Point(args, flp, trace, leak_ref, geom, name_map, leak_model, t_ref, area_m2, args.cores)

    print('COP break-even: microrefrigeration against more airflow')
    if args.die == 'ga100':
        print('  die      : GA100 accelerator, {:.0f} mm^2, {} blocks, {:g} um grid'.format(
            area_m2 * 1e6, extra['n_blocks'], extra['grid_um']))
        print('  workload : kernel {!r}{}, {:.0f} W nominal -> {:.0f} W realised '
              '({:.3f} W/mm^2)'.format(
                  args.kernel,
                  '' if args.kernel != 'occupancy' else
                  ' ({} of {} SMs, {})'.format(extra['kernel'].get('n_active'),
                                               extra['kernel'].get('n_sm'), args.placement),
                  extra['nominal_W'], power_W, power_W / (area_m2 * 1e6)))
        print('  MR lift  : dt_max {:.0f} K  -- on this die at 700 W the lift BINDS, so a '
              'break-even\n             priced here may be for a target MR cannot reach'
              .format(args.mr_dt_max))
    else:
        print('  die      : {}-core {}, {:.1f} mm^2, {:.1f} W ({:.3f} W/mm^2)'.format(
            args.cores, args.node, area_m2 * 1e6, power_W, args.density))
    print('  target   : both arms must hold a peak of {:.1f} C'.format(args.target_C))
    print('  baseline : {:g} CFM, fan {:.1f} W'.format(args.cfm, simscale_fan_power(args.cfm)))
    print('  air arm  : may buy up to {:g} CFM ({:.1f} W of fan). beta {:.3f} -> {:.3f} K/W '
          'over that range -- the hotspot term barely moves'.format(
              args.cfm_max, simscale_fan_power(args.cfm_max),
              simscale_beta(args.cfm), simscale_beta(args.cfm_max)))
    print()

    rows = []

    # --- air arm: least airflow that holds the target -----------------------------------
    print('  [air] bisecting airflow for the target ...')
    hi = P.run(args.cfm_max, False, 'air_max')
    rows.append(hi)
    air_ok = (hi['peak_C'] is not None and not hi['diverged']
              and hi['peak_C'] <= args.target_C)
    print('       {:g} CFM -> {}'.format(
        args.cfm_max, 'RUNAWAY' if hi['diverged'] else '{:.2f} C'.format(hi['peak_C'])))

    air = None
    if air_ok:
        lo_cfm, hi_cfm = args.cfm, args.cfm_max
        air = hi
        while hi_cfm - lo_cfm > args.cfm_tol:
            mid = 0.5 * (lo_cfm + hi_cfm)
            r = P.run(mid, False, 'air_{:.0f}'.format(mid))
            rows.append(r)
            ok = (r['peak_C'] is not None and not r['diverged'] and r['peak_C'] <= args.target_C)
            print('       {:6.1f} CFM -> {:>9s}  fan {:6.1f} W'.format(
                mid, 'RUNAWAY' if r['diverged'] else '{:.2f} C'.format(r['peak_C']),
                r['p_fan_W']))
            if ok:
                hi_cfm, air = mid, r
            else:
                lo_cfm = mid

    # --- MR arm: clip at the baseline airflow -------------------------------------------
    print('\n  [MR] clipping at the baseline {:g} CFM ...'.format(args.cfm))
    mr = P.run(args.cfm, True, 'mr_base')
    rows.append(mr)
    print('       peak {:>9s}, {:.4f} W removed from {} blocks, {:.3f} W net electrical'.format(
        'RUNAWAY' if mr['diverged'] else '{:.2f} C'.format(mr['peak_C'] or float('nan')),
        mr['q_removed_W'], mr['n_targets'], mr['p_mr_net_W']))

    mr_ok = (mr['peak_C'] is not None and not mr['diverged']
             and mr['peak_C'] <= args.target_C + 1.0)
    if mr_ok and mr.get('plan_is_minimum') is False:
        print('       NOTE: the plan is not known to be minimal ({}), so this cost is an UPPER '
              'bound\n             and the break-even COP derived from it is correspondingly '
              'generous to MR.'.format(mr.get('mr_reason') or 'descent did not bracket the '
                                       'stability boundary'))

    # --- the comparison ------------------------------------------------------------------
    out = {'die': args.die, 'cores': args.cores, 'density': args.density,
           'ga100': extra, 'target_C': args.target_C,
           'cfm_base': args.cfm, 'cfm_max': args.cfm_max, 'area_mm2': area_m2 * 1e6,
           'nominal_die_W': power_W, 'rows': rows, 'calibrated': False,
           'air_feasible': bool(air_ok), 'mr_feasible': bool(mr_ok),
           'costs_modelled': 'die power + fan power + MR net electrical',
           'costs_NOT_modelled': 'pump/chiller power, hardware cost, integration, reliability'}

    print('\n  ' + '-' * 74)
    if not mr_ok:
        out['verdict'] = 'mr_cannot_hold_target'
        print('  MR cannot hold the target here, so there is nothing to price. That is the'
              '\n  result: the device envelope is the binding constraint, not its efficiency.')
    elif not air_ok:
        out['verdict'] = 'air_infeasible'
        out['breakeven_cop'] = None
        print('  AIR CANNOT REACH THE TARGET AT ANY AIRFLOW UP TO {:g} CFM.'.format(args.cfm_max))
        print('  There is no alternative to price MR against, so MR wins at ANY positive COP.')
        print('  This is the constriction floor doing what it does: beta saturates near')
        print('  {:.3f} K/W, so the hotspot term stops responding to airflow while the fan'
              .format(simscale_beta(args.cfm_max)))
        print('  keeps drawing more power. The question stops being efficiency and becomes')
        print('  whether the DEVICE can remove the heat at all.')
    else:
        air_total = (air['p_die_W'] or 0.0) + air['p_fan_W']
        mr_total_die = (mr['p_die_W'] or 0.0) + mr['p_fan_W']
        budget = air_total - mr_total_die
        q_billed = mr['q_billed_W']
        gross_factor = 1.0 - mr['recovery_ratio']
        print('  air arm : {:6.1f} CFM   die {:6.1f} W + fan {:6.1f} W = {:6.1f} W'.format(
            air['cfm'], air['p_die_W'] or float('nan'), air['p_fan_W'], air_total))
        print('  MR arm  : {:6.1f} CFM   die {:6.1f} W + fan {:6.1f} W = {:6.1f} W  + MR'.format(
            mr['cfm'], mr['p_die_W'] or float('nan'), mr['p_fan_W'], mr_total_die))
        print('  budget the air arm spends that MR does not : {:.2f} W'.format(budget))
        out.update({'air_total_W': air_total, 'mr_die_plus_fan_W': mr_total_die,
                    'budget_W': budget, 'q_billed_W': q_billed})
        if budget <= 0:
            out['verdict'] = 'air_cheaper_at_any_cop'
            out['breakeven_cop'] = None
            print('\n  More airflow is CHEAPER than the MR arm even before the laser is paid for.')
            print('  No COP rescues this operating point.')
        else:
            cop_be = q_billed * gross_factor / budget
            out['verdict'] = 'finite_breakeven'
            out['breakeven_cop'] = cop_be
            out['modelled_cop'] = mr.get('effective_cop')
            print('\n  BREAK-EVEN COP = {:.4f}'.format(cop_be))
            print('  (removing {:.4f} W of heat, net of {:.0%} LPC recovery, for a {:.2f} W '
                  'budget)'.format(q_billed, mr['recovery_ratio'], budget))
            eff_cop = mr.get('effective_cop')
            eff_cop = float('inf') if (eff_cop is None or mr['net_generating']) else float(eff_cop)
            out['effective_cop'] = None if eff_cop == float('inf') else eff_cop
            if mr['net_generating']:
                print('  the MR loop is NET-GENERATING at these efficiencies (the LPC returns '
                      'more\n  than the laser draws), so it wins at any budget.')
            else:
                print('  modelled effective COP at the shipped efficiencies: {:.4f}'.format(
                    eff_cop))
            if eff_cop >= cop_be:
                print('  -> MR ALREADY WINS at this operating point, by {:.1f}x'.format(
                    eff_cop / cop_be))
            else:
                print('  -> MR loses; it needs {:.1f}x better efficiency to break even'.format(
                    cop_be / eff_cop))

    path = os.path.join(args.out_dir, 'cop_breakeven.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print('\n  wrote {}'.format(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
