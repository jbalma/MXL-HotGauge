#!/usr/bin/env python
"""Where does temperature-dependent leakage break the SimScale CFD's linear model?

The question
------------
The SimScale study (docs/SimScale/Write_up/) fits peak chip temperature *linearly* in power:

    T_max = T_0 + alpha(v_air) * P_core + beta(v_air) * P_FU

That fit has no leakage feedback -- the CFD injected a fixed wattage. But leakage grows with
temperature, so the real die injects more power as it heats, which heats it further. At desktop
power the correction is modest. At the HPC power this study targets (290 W core + 70 W
functional unit) it need not be, and the linear model cannot see a thermal runaway at all.

This sweep runs the *same* baffled-fin sink through HotGauge's power<->temperature fixed point
and reports the gap. Neither model answers this alone: SimScale has the server geometry and the
fan curve but no leakage; HotGauge has the leakage loop but, before now, only a desktop tower.

Reading the output
------------------
``T_lin`` is what the CFD fit predicts for the SimScale die. ``T_fb`` is what the coupled solve
gives for *ours*. ``gap`` is the difference, and it has **two** causes that must not be
conflated:

* **die geometry** -- our floorplan is not SimScale's, so its on-die spreading differs. Compare
  ``R_die`` (our on-die resistance) against ``a-Rc`` (SimScale's, i.e. ``alpha`` minus the
  convective term). This term is present even with leakage frozen.
* **leakage feedback** -- shown separately as ``dP_leak``, the watts the die gained by heating.
  Only this part is something the CFD structurally cannot predict.

At 100 W on the 34-core die the gap is +40 K while ``dP_leak`` is 0.3 W: essentially all
geometry, no leakage. Reading that gap as a leakage effect would be wrong. Leakage only takes
over near the cliff, where it runs away outright.

``RUNAWAY`` means the fixed point diverged: no steady state exists at that (power, airflow)
pair, which the linear model reports as a merely-hot but finite temperature.

Caveats
-------
* alpha/beta are digitised from the write-up's figures -- ``docs/SimScale/Scripts`` and
  ``data`` copied over empty. See docs/SIMSCALE_INTEGRATION.md.
* alpha is a die-referenced R_th [K/W]; converting it to an HTC needs an area, and we use *our*
  floorplan's area, not the SimScale die's (unknown). The comparison is therefore like-for-like
  in R_th but assumes the two dies are of comparable size.
* Above 400 K the leakage curve is an Arrhenius extrapolation, so treat divergence as
  "no steady state here" rather than as a precise temperature.

Usage
-----
    python examples/simscale_hpc_study.py --powers 50,100,200,290 --cfms 30,50,88,133,200
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
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, die_power_of_trace,
                                               load_calibrated_leakage_model,
                                               mcpat_tref_from_trace_dir,
                                               replicate_trace_cores)
from HotGauge.thermal.sink_models import (BaffledFinSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan, simscale_alpha,
                                          simscale_beta, simscale_fan_power, SIMSCALE_T0_K,
                                          SIMSCALE_ALPHA_FIT)
from HotGauge.power.performance_model import FMaxModel, performance_summary
from HotGauge.thermal.utils import K_to_C

T_FLOOR_K = 200.0
DEFAULT_FLOPS_PER_CYCLE = 32.0


def evaluate(args, base, flp_area, leak_model, t_ref, fmax, power_W, cfm, tag):
    """One (die power, airflow) point through the coupled solve."""
    sink = BaffledFinSink(cfm, flp_area, ambient_K=args.ambient_K)
    stack = render_stack_with_sink(get_stack_template(args.stack), sink,
                                   os.path.join(args.out_dir, 'stacks', tag + '.stk'))

    trace, scale, _ = scale_trace_to_die_power(base, args.flp_template, args.tech_node,
                                               power_W, num_cores=args.num_cores)
    split = args.split_file
    leak_ref = {}
    if split and os.path.isfile(split):
        with open(split) as f:
            leak_ref = {u: float(v[1]) * scale for u, v in json.load(f).items()}

    def solver_factory(sub):
        return ICEThermalSolver(stack, args.flp_template, args.tech_node,
                                run_base_dir=os.path.join(args.out_dir, tag, sub),
                                initial_temp=args.ambient_K, num_cores=args.num_cores,
                                single_thread=True, mode='steady')

    res = run_leakage_feedback(trace, leak_ref, solver_factory('it'), model=leak_model,
                               T_ref=t_ref, num_cores=args.num_cores, tol_K=args.tol,
                               max_iter=args.max_iter, relax=0.5, t_floor_K=T_FLOOR_K,
                               bridge_aggregates=True)

    # The CFD's own prediction for the same injected power, with no leakage feedback.
    t_lin_C = K_to_C(SIMSCALE_T0_K + simscale_alpha(cfm) * power_W)
    row = {'tag': tag, 'power_W': power_W, 'cfm': cfm, 'alpha': simscale_alpha(cfm),
           'beta': simscale_beta(cfm), 'fan_W': sink.parasitic_power_W(),
           'r_th': sink.r_th_K_per_W, 't_lin_C': t_lin_C}

    if res.get('diverged'):
        row['diverged'] = True
        return row

    temps = res['temp_trace']
    finals = [float(np.ravel(v)[-1]) for v in temps.values()]
    peak_K = max(t for t in finals if t > T_FLOOR_K)
    p_chip = die_power_of_trace(res['power_trace'], args.flp_template, args.tech_node,
                                num_cores=args.num_cores)
    p_cool = sink.parasitic_power_W()
    perf = performance_summary(finals, fmax, f_nominal_GHz=args.f_nominal,
                               compute_power_W=p_chip, cooling_power_W=p_cool,
                               throttle_K=args.throttle_C + 273.15, t_floor_K=T_FLOOR_K)
    g = perf['f_effective_GHz'] * args.flops_per_cycle * args.num_cores
    # End-to-end resistance our model produces, and the on-die part of it. The on-die part
    # should be independent of airflow -- if it is not, the convective/conduction split is wrong.
    rise_K = peak_K - args.ambient_K
    r_end_to_end = rise_K / p_chip if p_chip > 0 else float('nan')
    row.update({'diverged': False, 't_fb_C': K_to_C(peak_K),
                'gap_K': K_to_C(peak_K) - t_lin_C,
                'r_end_to_end_K_per_W': r_end_to_end,
                'r_die_K_per_W': r_end_to_end - sink.r_th_K_per_W,
                'p_chip_W': p_chip, 'leakage_growth_W': p_chip - power_W,
                'p_cool_W': p_cool, 'p_total_W': p_chip + p_cool,
                'cop': (p_chip + p_cool) / p_cool if p_cool > 0 else float('inf'),
                'f_GHz': perf['f_effective_GHz'], 'throttling': perf['throttling'],
                'gflops': g, 'gflops_per_total_W': g / (p_chip + p_cool)})
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trace-dir', default='mcpat_runs/7nm/linpack_3.8GHz')
    ap.add_argument('--flp-template', default=os.path.join(
        _HERE, 'floorplans', 'outputs', 'skylake7nm_8core_3_3D-ICE_template.flp'))
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--num-cores', type=int, default=8,
                    help='cores in the floorplan being solved')
    ap.add_argument('--trace-cores', type=int, default=8,
                    help='cores present in the McPAT trace; tiled up to --num-cores')
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--powers', default='50,100,200,290',
                    help='comma-separated die powers [W]')
    ap.add_argument('--cfms', default='30,50,88,133,200',
                    help='comma-separated airflows [CFM]')
    ap.add_argument('--ambient-K', type=float, default=SIMSCALE_T0_K)
    ap.add_argument('--leakage-cal', default='leakage_calibration/leakage_calibration.json')
    ap.add_argument('--f-nominal', type=float, default=4.0)
    ap.add_argument('--derate-per-K', type=float, default=0.001)
    ap.add_argument('--throttle-C', type=float, default=100.0)
    ap.add_argument('--flops-per-cycle', type=float, default=DEFAULT_FLOPS_PER_CYCLE)
    ap.add_argument('--tol', type=float, default=0.5)
    ap.add_argument('--max-iter', type=int, default=12)
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()

    # 3D-ICE runs from its own working directory, so every path handed to it must be absolute.
    args.flp_template = os.path.abspath(args.flp_template)
    args.trace_dir = os.path.abspath(args.trace_dir)
    args.leakage_cal = os.path.abspath(args.leakage_cal)
    args.out_dir = os.path.abspath(args.out_dir or os.path.join(os.getcwd(), 'simscale_hpc'))
    os.makedirs(args.out_dir, exist_ok=True)
    powers = [float(x) for x in args.powers.split(',') if x.strip()]
    cfms = [float(x) for x in args.cfms.split(',') if x.strip()]

    flp_area = chip_area_m2_from_floorplan(args.flp_template)
    if os.path.isfile(args.leakage_cal):
        leak_model, t_ref = load_calibrated_leakage_model(args.leakage_cal, extrapolate=True)
        leak_src = 'MEASURED McPAT curve + Arrhenius tail above 400 K'
    else:
        leak_model = LeakageModel.exponential(15.0)
        t_ref = mcpat_tref_from_trace_dir(args.trace_dir) or 330.0
        leak_src = 'assumed exponential'
    fmax = FMaxModel.linear_derate(args.derate_per_K)

    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)
    args.split_file = os.path.join(
        args.trace_dir,
        os.path.basename(files[0]).replace('block_powers_', 'block_powers_split_'))

    # The McPAT trace is 8-core; an HPC die needs far more cores for hundreds of watts to be a
    # sane die-average density. Tile the same workload onto every core.
    trace_cores = args.trace_cores
    if args.num_cores > trace_cores:
        base = replicate_trace_cores(base, args.num_cores, n_src=trace_cores)

    print('SimScale baffled-fin sink under HotGauge leakage feedback')
    print('  floorplan : {} ({:.2f} mm^2, {} cores)'.format(
        os.path.basename(args.flp_template), flp_area * 1e6, args.num_cores))
    if args.num_cores > trace_cores:
        print('  trace     : {}-core McPAT trace tiled onto {} cores (homogeneous workload)'
              .format(trace_cores, args.num_cores))
    print('  leakage   : {}'.format(leak_src))
    print('  ambient   : {:.2f} K (SimScale T_0)'.format(args.ambient_K))
    print('  alpha/beta: DIGITISED from the write-up figures -- see '
          'docs/SIMSCALE_INTEGRATION.md')
    print()

    hdr = ('{:>7s} {:>6s} {:>7s} {:>7s} {:>8s} {:>8s} {:>6s} {:>7s} {:>6s} {:>8s} {:>7s} '
           '{:>9s}'.format(
               'P_die', 'CFM', 'R_conv', 'P_fan', 'T_lin C', 'T_fb C', 'gap K', 'R_die',
               'a-Rc', 'dP_leak', 'f GHz', 'GFLOP/s'))
    print(hdr)
    print('-' * len(hdr))

    rows = []
    for p in powers:
        for c in cfms:
            tag = 'P{:g}_C{:g}'.format(p, c)
            r = evaluate(args, base, flp_area, leak_model, t_ref, fmax, p, c, tag)
            rows.append(r)
            if r['diverged']:
                print('{:>7.0f} {:>6.0f} {:>7.4f} {:>7.1f} {:>8.1f} {:>8s} {:>6s} {:>7s} '
                      '{:>6.3f} {:>8s} {:>7s} {:>9s}  RUNAWAY'.format(
                          r['power_W'], r['cfm'], r['r_th'], r['fan_W'], r['t_lin_C'],
                          '--', '--', '--', r['alpha'] - r['r_th'], '--', '--', '--'))
            else:
                print('{:>7.0f} {:>6.0f} {:>7.4f} {:>7.1f} {:>8.1f} {:>8.1f} {:>6.1f} '
                      '{:>7.3f} {:>6.3f} {:>8.2f} {:>7.3f} {:>9.1f}{}'.format(
                          r['power_W'], r['cfm'], r['r_th'], r['fan_W'], r['t_lin_C'],
                          r['t_fb_C'], r['gap_K'], r['r_die_K_per_W'],
                          r['alpha'] - r['r_th'], r['leakage_growth_W'], r['f_GHz'],
                          r['gflops'], '  THROTTLED' if r['throttling'] else ''))
        print()

    ok = [r for r in rows if not r['diverged']]
    runaway = [r for r in rows if r['diverged']]
    print('summary')
    if ok:
        worst = max(ok, key=lambda r: r['gap_K'])
        print('  largest gap vs the CFD fit: {:+.1f} K at {:.0f} W / {:.0f} CFM -- of which '
              '{:.2f} W of extra leakage'.format(
                  worst['gap_K'], worst['power_W'], worst['cfm'],
                  worst['leakage_growth_W']))
        r_die = [r['r_die_K_per_W'] for r in ok]
        print('  our on-die resistance: {:.3f}-{:.3f} K/W (airflow-independent, as it should '
              'be) vs SimScale {:.3f} K/W'.format(
                  min(r_die), max(r_die),
                  SIMSCALE_ALPHA_FIT['r_cond']))
        if max(r_die) > 1.5 * SIMSCALE_ALPHA_FIT['r_cond']:
            print('  -> the gap above is mostly DIE GEOMETRY, not leakage: our floorplan '
                  'spreads heat {:.1f}x worse than the SimScale die.'.format(
                      max(r_die) / SIMSCALE_ALPHA_FIT['r_cond']))
        be = max(ok, key=lambda r: r['gflops_per_total_W'])
        print('  best efficiency: {:.0f} W / {:.0f} CFM -> {:.4f} GFLOP/s/W total '
              '(P_fan {:.1f} W, COP {:.2f})'.format(
                  be['power_W'], be['cfm'], be['gflops_per_total_W'], be['fan_W'], be['cop']))
    if runaway:
        print('  {} of {} points have NO steady state -- the linear CFD fit predicts a finite '
              'temperature for every one of them:'.format(len(runaway), len(rows)))
        for r in runaway:
            print('    {:.0f} W at {:.0f} CFM: CFD says {:.1f} C, coupled solve runs away'
                  .format(r['power_W'], r['cfm'], r['t_lin_C']))

    out = os.path.join(args.out_dir, 'sweep.json')
    with open(out, 'w') as f:
        json.dump({'rows': rows}, f, indent=2)
    print('\n  written: {}'.format(out))


if __name__ == '__main__':
    main()
