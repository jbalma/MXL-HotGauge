#!/usr/bin/env python
"""The extractor's cooling flux versus its own temperature, per platform, on v98's volumetric route
-- where ``dt_max`` comes from (§P0.19, rebuilt on v98 in §P0.20).

    python examples/extractor_curves.py       # pure arithmetic; no solver, runs anywhere

Writes ``docs/evidence/extractor_cooling_curves.json``: ``h(T)`` for the dye and the GaAs
extractors at v91's design points, the temperature at which each stops cooling, the anchors the
model is checked against (Table 8.1, eq. 8.4, Table 9.2 / eqs. 9.5-9.7, the A_0 breakeven, the
Fig. 9.9 map structure), and the bracket the device team has to close (the dye tail's thermal
fraction, the host background absorption, fixed versus retuned pump for GaAs).
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

from HotGauge.thermal.extractor import (DyeExtractor, SemiconductorExtractor, DYE_LADDER,
                                        DYE_SIGMA_BOOK, DYE_SIGMA_DISORDER, DYE_BACKGROUND_CM,
                                        make_extractor)


def curve(x, T):
    return [{'T_K': float(t), 'h_W_per_mm2': float(x.cooling_density_W_per_mm2(t)),
             'eta_asf': float(x.eta_asf(t)), 'eta_c': float(x.eta_c(t) if hasattr(x, 'eta_c') else x.eta_cool(t))}
            for t in T]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'extractor_cooling_curves.json'))
    ap.add_argument('--die-demand', default=os.path.join(_EV, 'array_coverage_armD.json'),
                    help='the coverage ladder, for the per-tile flux the die actually asks for')
    args = ap.parse_args()
    T = np.arange(120.0, 620.0 + 1e-9, 10.0)

    # --- the dye on v98's route: every rung, and the target device with its sigma bracket ------
    ladder = {}
    for r in sorted(DYE_LADDER):
        d = DyeExtractor.from_rung(r)
        ladder[str(r)] = {'inputs': d.describe(), 'curve': curve(d, T)}
    target = {}
    for name, kw in (('book_sigma1_kedenburg', {}),
                     ('disorder_sigma0.26', {'sigma': DYE_SIGMA_DISORDER}),
                     ('book_sigma1_original_host', {'background': 'original'})):
        d = DyeExtractor.from_rung(6, **kw)
        target[name] = {'inputs': d.describe(), 'curve': curve(d, T), 'T_min_K': d.t_min_K(),
                        'h_at': {str(t): d.cooling_density_W_per_mm2(t) for t in (200.0, 230.0, 263.0, 300.0, 330.0, 365.0, 400.0)}}

    # --- the die's demand: the largest per-tile flux the coverage ladder ever asked for ---------
    demand = None
    if os.path.isfile(args.die_demand):
        j = json.load(open(args.die_demand))
        rows = [r for r in j.get('rows', []) if r.get('max_tile_flux_W_per_mm2')]
        by_cov = {}
        for r in rows:
            by_cov.setdefault(r['coverage'], []).append(r)
        demand = {str(c): {'max_tile_flux_W_per_mm2_over_ladder': max(x['max_tile_flux_W_per_mm2'] for x in rs),
                           'at_2.00': next((x['max_tile_flux_W_per_mm2'] for x in rs if abs(x['density'] - 2.0) < 1e-9), None)}
                  for c, rs in by_cov.items()}
    # which rung covers the demand at the tile temperatures this die runs its array at
    rung_needed = {}
    for T_tile in (263.0, 300.0, 330.0):
        need = demand['1.0']['max_tile_flux_W_per_mm2_over_ladder'] if demand else 8.0
        ok = [r for r in sorted(DYE_LADDER) if DyeExtractor.from_rung(r).cooling_density_W_per_mm2(T_tile) >= need]
        rung_needed[str(T_tile)] = {'demand_W_per_mm2': need, 'lowest_rung_that_covers': (ok[0] if ok else None),
                                    'h_by_rung': {str(r): DyeExtractor.from_rung(r).cooling_density_W_per_mm2(T_tile) for r in sorted(DYE_LADDER)}}

    # --- GaAs ------------------------------------------------------------------------------------
    gaas = {}
    for name, kw in (('table_9_2_fixed_890nm', {}), ('table_9_2_retuned', {'retune_pump': True}),
                     ('table_1_1_enhanced_fixed', {'eta_e': 0.9, 'purcell': 10.0, 'film_um': 2.0}),
                     ('table_1_1_enhanced_retuned', {'eta_e': 0.9, 'purcell': 10.0, 'film_um': 2.0, 'retune_pump': True})):
        g = SemiconductorExtractor(**kw)
        gaas[name] = {'inputs': g.describe(), 'curve': curve(g, T), 'T_min_K': g.t_min_K(),
                      'N_opt_300K_cm3': g.optimum(300.0)[0], 'p_opt_300K_W_per_mm3': g.optimum(300.0)[1]}
    g0 = SemiconductorExtractor()
    book = g0.book_closed_form(300.0)
    d6 = DyeExtractor.from_rung(6)

    out = {
        'note': __doc__.strip(),
        'source': 'docs/Photonic_Cooling_Devices___v98.pdf (8 Sep 2026): eqs. 5.7, 8.4-8.9, 9.5-9.7; Tables 1.1, 8.1, 8.2, 8.3, 9.2',
        'model': ('p_max = n_t x_max(T) (F_P/tau) hbar w_p eta_cool(T), x_max = [1 + exp((E_00 - E_p)/kT)]^-1 '
                  '(the transparency cap, thermal by construction), eta_cool = eta_abs eta_EQE lambda_p/lambda_f - 1, '
                  'eps(E,T) = 4290 exp[sigma (E - E_600)/kT]; Pcool/A = p_max d. GaAs: A,B,C balance with photon '
                  'recycling, Urbach tail, Varshni gap, v98 (9.6)-(9.7).'),
        'dye_ladder_table_8_2': ladder,
        'target_device_table_1_1_rung_6': target,
        'die_demand_from_coverage_ladder': demand,
        'rung_needed_for_this_die': rung_needed,
        'gaas': gaas,
        'anchors': {'gaas_table_9_2': {'N_opt_cm3': 5.7e17, 'p_opt_W_per_mm3': 80.0,
                                       'model': {'N_opt_cm3': g0.optimum(300.0)[0], 'p_opt_W_per_mm3': g0.optimum(300.0)[1]},
                                       'v98_eq_9_6_closed_form': book['p_opt_W_per_mm3'], 'A0_per_s': book['A0_per_s']},
                    'dye_tables_8_1_8_2': 'reproduced to the printed digit -- tests in thermal/test_extractor.py',
                    'sigma_bracket': {'book': DYE_SIGMA_BOOK, 'disorder': DYE_SIGMA_DISORDER},
                    'alpha_b_cm': DYE_BACKGROUND_CM},
        'FINDING_1_THE_CAP_IS_THERMAL_BY_CONSTRUCTION': (
            'The transparency cap x_max is a Boltzmann population ratio between the absorption and emission '
            'cross-sections at the pump (McCumber), so the capability collapse on cooling does not depend on how '
            'the absorption tail is broadened: the target device (rung 6) gives {:.0f} W/mm^2 at 400 K, {:.0f} at '
            '300 K, {:.0f} at 263 K and {:.0f} at 200 K for sigma = 1 and 0.26 alike. T_min (where net cooling '
            'vanishes) is {} K at sigma = 1 and {} at sigma = 0.26 -- and the capability is below 0.2 % of design '
            'at either, so the bracket the device team was asked to close no longer decides anything the die '
            'can see.'.format(d6.cooling_density_W_per_mm2(400.0), d6.cooling_density_W_per_mm2(300.0),
                              d6.cooling_density_W_per_mm2(263.0), d6.cooling_density_W_per_mm2(200.0),
                              '{:.0f}'.format(d6.t_min_K()) if d6.t_min_K() else 'none',
                              '{:.0f}'.format(target['disorder_sigma0.26']['T_min_K']) if target['disorder_sigma0.26']['T_min_K'] else 'none above 80')),
        'FINDING_2_WHICH_RUNG_THIS_DIE_NEEDS': rung_needed,
        'FINDING_3_V91_FIGURE_WITHDRAWN': (
            'v91 eq. 8.4 (10^3-10^4 W/mm^2 for a bulk 10^-2 M x 5 um film) is withdrawn by v98 itself: stimulated '
            'emission at the pump caps the excited fraction at x_max ~ 10^-3-10^-4, and the bulk film tops out at '
            '0.03-0.09 W/mm^2 at 300 K (Table 8.1). The 10^3 figure is the Tier-I design point after the photonic '
            'ladder (Table 8.2), not a bulk property. The 819 W/mm^2 / 207 K row of the 5 Sep evidence rested on '
            'the withdrawn figure and is superseded here.'),
        'HONEST_LIMITS': (
            'Steady state at the transparency ceiling (pump >> I_sat); the tail beyond 620 nm is the anchored '
            'exponential of v98 eq. 9.5, which the book itself names as the priority measurement; eta_EQE = 1 '
            'everywhere (every areal figure scales with the realised eta_cool, positive only for eta_EQE >= '
            '0.92-0.95); the design point needs a pump flux of order 1 MW/cm^2 and is a pulsed, targeted tile.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print(__doc__.split('\n')[0])
    print('\nTARGET DEVICE (v98 Table 1.1 / rung 6): h(T) W/mm^2:')
    for name, v in target.items():
        print('   %-28s %s  T_min %s' % (name, ' '.join('%s:%.0f' % (k, x) for k, x in v['h_at'].items()),
                                         'none' if v['T_min_K'] is None else '%.0f K' % v['T_min_K']))
    print('\nrung needed for this die (max tile flux %.1f W/mm^2 at full coverage):' % (rung_needed['300.0']['demand_W_per_mm2']))
    for Tt, v in rung_needed.items():
        print('   tiles at %s K: lowest rung that covers = %s   (h by rung: %s)' % (
            Tt, v['lowest_rung_that_covers'], ' '.join('%s:%.2g' % (r, h) for r, h in v['h_by_rung'].items())))
    print('\nGaAs Table 9.2: numeric %.1f W/mm^3, v98 (9.6) %.1f, N_opt %.2g; Table 1.1 enhanced: %.2g W/mm^3, N_opt %.2g'
          % (g0.optimum(300.0)[1], book['p_opt_W_per_mm3'], g0.optimum(300.0)[0],
             gaas['table_1_1_enhanced_fixed']['p_opt_300K_W_per_mm3'], gaas['table_1_1_enhanced_fixed']['N_opt_300K_cm3']))
    print('\nwritten: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
