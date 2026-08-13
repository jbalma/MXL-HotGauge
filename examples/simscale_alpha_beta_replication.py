#!/usr/bin/env python
"""Reproduce the SimScale alpha/beta experiment in 3D-ICE, as a cross-check of our thermal path.

What this tests
---------------
The SimScale CFD study fits peak chip temperature bi-linearly in two power channels::

    T_max = T_0 + alpha(v_air) * P_core + beta(v_air) * P_FU

and finds ``beta / alpha`` rising from 2.4 to 5.5 as airflow increases -- a watt injected at a
200 um functional unit costs several times what a watt spread over the die costs. That ratio is
the entire quantitative case for photonic microrefrigeration, and so far we have taken it on
faith from an external model.

This script runs *their experiment* in *our* model. Two steady solves at a fixed sink:

* **uniform**  -- ``P_uni`` distributed over the die in proportion to block area, so the power
  density is flat. Gives ``alpha = (T_max - T_amb) / P_uni``.
* **hotspot**  -- the same ``P_uni`` plus ``P_hs`` concentrated in one small block per core.
  Gives ``beta = (T_max_hs - T_max_uni) / P_hs``.

Then compares ``beta/alpha`` against SimScale's. Agreement is real validation of our thermal
path; disagreement localises where the two models diverge.

What is deliberately NOT matched
--------------------------------
SimScale's die is a 400 mm^2 square with 2x2 mm cores and a 200x200 um hotspot each. Our
floorplan is a real 14 nm Skylake-derived layout: 174 mm^2 for 14 cores, aspect 1.56, median
block 0.028 mm^2. The *functional-unit granularity* matches well (0.028 vs their 0.04 mm^2) but
the die area and aspect do not.

That is on purpose. ``alpha`` is dominated by the sink and by die-wide spreading, so it scales
with die area and is not expected to match. ``beta`` is dominated by *local* spreading
resistance in ~0.5 mm of silicon, which saturates within a few mm of the source and should
therefore transfer between geometries. So ``beta/alpha`` is the transferable quantity, and the
absolute values are not -- read the ratio, not the coefficients.

Leakage is also off here: the SimScale fit is linear in power because its CFD had no
temperature-dependent leakage. Matching that is what makes the comparison clean. Turning
leakage back on is the *next* experiment, and it should push our temperatures above theirs.

Usage
-----
    python examples/simscale_alpha_beta_replication.py --cores 14
    python examples/simscale_alpha_beta_replication.py --cores 14 --p-uni 227 --p-hs 37.73
"""
import os
import sys
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))
sys.path.insert(0, _HERE)

from HotGauge.thermal import get_stack_template, ICEThermalSolver
from HotGauge.thermal.sink_models import (ConstantHTCSink, render_stack_with_sink,
                                          chip_area_m2_from_floorplan, simscale_alpha,
                                          simscale_beta)
from HotGauge.power import BasicPowerTrace
from HotGauge.configuration import mcpat_to_flp_name

# SimScale's design point, from Results_3.nb: uniform power and the hotspot increment whose
# ratio produced the published alpha/beta. P_hs is 16 hotspots at 2.36 W, not the 70 W of the
# write-up's headline figure -- use the numbers the coefficients were actually fitted at.
DEFAULT_P_UNI_W = 226.56
DEFAULT_P_HS_W = 37.73

#: Reference points from the notebooks (CFM -> (alpha, beta)) for the comparison table.
SIMSCALE_REF = {87: (0.2799, 1.3049), 200: (0.2361, 1.2607)}


def flp_block_areas(flp_path):
    """Map floorplan block name -> area in m^2, parsed from the 3D-ICE .flp."""
    import re
    text = open(flp_path).read()
    rgx = re.compile(r'(\S+)\s*:\s*position\s+[\d.eE+-]+,\s*[\d.eE+-]+\s*;\s*'
                     r'dimension\s+([\d.eE+-]+),\s*([\d.eE+-]+)\s*;')
    return {m.group(1): float(m.group(2)) * float(m.group(3)) * 1e-12
            for m in rgx.finditer(text)}


#: SimScale's hotspot footprint: 200 x 200 um.
SIMSCALE_HOTSPOT_M2 = (200e-6) ** 2


def pick_hotspot_blocks(areas, num_cores, target_m2=SIMSCALE_HOTSPOT_M2):
    """One hotspot block per core: the block whose area is closest to ``target_m2``.

    Matching *area* is what makes beta comparable. An earlier version took the smallest block
    per core, which picked 37 um slivers and concentrated the hotspot power at 1906 W/mm^2
    against SimScale's 62.5 -- a 30x mismatch that would have made beta meaningless. Spreading
    resistance is set by the source footprint, so the footprint is the thing to match.
    """
    per_core = {}
    for name, area in areas.items():
        if '_' not in name:
            continue
        idx = name.rsplit('_', 1)[-1]
        if not idx.isdigit():
            continue
        idx = int(idx)
        if idx >= num_cores:
            continue
        err = abs(area - target_m2)
        if idx not in per_core or err < per_core[idx][2]:
            per_core[idx] = (name, area, err)
    return {v[0]: v[1] for v in per_core.values()}


def build_trace(areas, hotspots, p_uni_W, p_hs_W, flp_template, tech_node, num_cores):
    """Uniform-by-area power plus an optional equal share of ``p_hs_W`` in each hotspot block.

    Keys are floorplan block names. ``ICEThermalSolver`` maps McPAT names through
    ``mcpat_to_flp_name``; names that are already floorplan names pass through unchanged, which
    is what lets a synthetic map be injected without inventing a fake McPAT hierarchy.
    """
    total_area = sum(areas.values())
    powers = {}
    for name, area in areas.items():
        powers[name] = p_uni_W * area / total_area
    if p_hs_W and hotspots:
        share = p_hs_W / len(hotspots)
        for name in hotspots:
            powers[name] += share
    return BasicPowerTrace({u: np.full(1, p) for u, p in powers.items()}, 1.0)


class FloorplanNamedSolver(ICEThermalSolver):
    """``ICEThermalSolver`` for traces already keyed by floorplan block name.

    The stock solver runs every trace through ``prepare_dice_trace``, which renames McPAT units,
    splits ``Processor/Total L3s`` across cores and appends the modelled IMC/IO/SoC units. A
    synthetic power map is already in floorplan-name form and has no McPAT hierarchy to split,
    so that pass is skipped rather than fed fake aggregate keys.
    """

    def __call__(self, power_trace):
        run_dir = os.path.join(self.run_base_dir, 'iter_{:03d}'.format(self._iter))
        self._iter += 1
        if self.mode == 'steady':
            return self._run_steady_and_read_temps(power_trace, run_dir, len(power_trace))
        return self._run_and_read_temps(power_trace, run_dir)


def solve_peak_K(trace, stack, flp_template, tech_node, out_dir, tag, ambient_K, num_cores):
    solver = FloorplanNamedSolver(stack, flp_template, tech_node,
                              run_base_dir=os.path.join(out_dir, tag),
                              initial_temp=ambient_K, num_cores=num_cores,
                              single_thread=True, mode='steady')
    temps = solver(trace)
    vals = [np.asarray(v, float).ravel()[-1] for v in temps.values()]
    return float(np.max(vals)), float(np.mean(vals))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cores', type=int, default=14)
    ap.add_argument('--tech-node', default='14')
    ap.add_argument('--p-uni', type=float, default=DEFAULT_P_UNI_W)
    ap.add_argument('--p-hs', type=float, default=DEFAULT_P_HS_W)
    ap.add_argument('--cfm', type=float, nargs='+', default=[87.0, 200.0],
                    help='airflow points; the sink HTC is set from SimScale alpha at each')
    ap.add_argument('--ambient-C', type=float, default=19.85,
                    help="SimScale's T_0")
    ap.add_argument('--flp-template', default=None)
    ap.add_argument('--stack', default='skylake')
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()

    args.flp_template = args.flp_template or os.path.join(
        _HERE, 'floorplans', 'outputs',
        'skylake{}nm_{}core_3_3D-ICE_template.flp'.format(args.tech_node, args.cores))
    args.out_dir = args.out_dir or os.path.join(os.getcwd(), 'simscale_replication')
    os.makedirs(args.out_dir, exist_ok=True)

    ambient_K = args.ambient_C + 273.15
    flp_solid = args.flp_template.replace('_template', '')
    areas = flp_block_areas(flp_solid)
    hotspots = pick_hotspot_blocks(areas, args.cores)
    area_m2 = chip_area_m2_from_floorplan(args.flp_template)
    base_stack = get_stack_template(args.stack)

    hs_area = sum(areas[n] for n in hotspots)
    print('SimScale alpha/beta replication in 3D-ICE')
    print('  floorplan  : {}'.format(os.path.basename(flp_solid)))
    print('  die        : {:.1f} mm^2, {} blocks, {} cores'.format(
        area_m2 * 1e6, len(areas), args.cores))
    print('  hotspots   : {} blocks, {:.4f} mm^2 total ({:.4f} mm^2 each)'.format(
        len(hotspots), hs_area * 1e6, hs_area * 1e6 / max(len(hotspots), 1)))
    print('  power      : P_uni {:.2f} W, P_hs {:.2f} W'.format(args.p_uni, args.p_hs))
    print('  hotspot flux: {:.1f} W/mm^2   (SimScale 62.5 W/mm^2 base)'.format(
        args.p_hs / (hs_area * 1e6) if hs_area else float('nan')))
    print('  leakage    : OFF (SimScale CFD had none -- matched deliberately)')
    print()

    rows = []
    for cfm in args.cfm:
        # Set the sink so a uniform load reproduces SimScale's alpha over OUR die area.
        #
        # Referencing it to their 400 mm^2 instead (the obvious first move) is wrong and quietly
        # destroys the experiment: our die is 174 mm^2, so the same coefficient is a 2.3x larger
        # R_sink. Since alpha ~ R_sink while beta ~ R_sink + R_local_spread, inflating R_sink
        # compresses beta/alpha toward 1 -- it measured 2.07 against their 4.66 purely from that.
        # Holding alpha fixed is the control that makes beta comparable.
        h_si = 1.0 / (simscale_alpha(cfm) * area_m2)
        sink = ConstantHTCSink(h_si, ambient_K=ambient_K,
                               label='SimScale-equiv @{:.0f} CFM'.format(cfm))
        stack = render_stack_with_sink(
            base_stack, sink, os.path.join(args.out_dir, 'stack_{:.0f}.stk'.format(cfm)))

        t_uni = build_trace(areas, {}, args.p_uni, 0.0,
                            args.flp_template, args.tech_node, args.cores)
        peak_uni, mean_uni = solve_peak_K(t_uni, stack, args.flp_template, args.tech_node,
                                          args.out_dir, 'uni_{:.0f}'.format(cfm),
                                          ambient_K, args.cores)

        t_hs = build_trace(areas, hotspots, args.p_uni, args.p_hs,
                           args.flp_template, args.tech_node, args.cores)
        peak_hs, mean_hs = solve_peak_K(t_hs, stack, args.flp_template, args.tech_node,
                                        args.out_dir, 'hs_{:.0f}'.format(cfm),
                                        ambient_K, args.cores)

        alpha = (peak_uni - ambient_K) / args.p_uni
        beta = (peak_hs - peak_uni) / args.p_hs
        rows.append(dict(cfm=cfm, h_si=h_si, peak_uni_C=peak_uni - 273.15,
                         peak_hs_C=peak_hs - 273.15, mean_uni_C=mean_uni - 273.15,
                         alpha=alpha, beta=beta, ratio=beta / alpha if alpha else float('nan')))

    print('{:>6} {:>10} {:>10} {:>9} {:>9} {:>8} | {:>9} {:>9} {:>8}'.format(
        'CFM', 'T_uni[C]', 'T_hs[C]', 'alpha', 'beta', 'b/a', 'a_simsc', 'b_simsc', 'b/a_ss'))
    for r in rows:
        ref = SIMSCALE_REF.get(int(r['cfm']))
        if ref:
            ra, rb = ref
            print('{:>6.0f} {:>10.2f} {:>10.2f} {:>9.4f} {:>9.4f} {:>8.2f} | '
                  '{:>9.4f} {:>9.4f} {:>8.2f}'.format(
                      r['cfm'], r['peak_uni_C'], r['peak_hs_C'], r['alpha'], r['beta'],
                      r['ratio'], ra, rb, rb / ra))
        else:
            print('{:>6.0f} {:>10.2f} {:>10.2f} {:>9.4f} {:>9.4f} {:>8.2f} | {:>29}'.format(
                r['cfm'], r['peak_uni_C'], r['peak_hs_C'], r['alpha'], r['beta'],
                r['ratio'], '(no reference point)'))

    out = os.path.join(args.out_dir, 'alpha_beta.json')
    with open(out, 'w') as f:
        json.dump(dict(cores=args.cores, tech_node=args.tech_node, p_uni_W=args.p_uni,
                       p_hs_W=args.p_hs, die_mm2=area_m2 * 1e6,
                       n_hotspots=len(hotspots), hotspot_mm2=hs_area * 1e6,
                       rows=rows, simscale_ref=SIMSCALE_REF), f, indent=2)
    print('\nwrote {}'.format(out))


if __name__ == '__main__':
    main()
