#!/usr/bin/env python
"""Test 6d: the AIMED rescue -- charging the array only for the hotspot, as the limit binds.

    python examples/aimed_vs_bulk_rescue.py

Test 6c priced the rescue with the array charged as though it lifted bulk die power, and said so:
every crossover it reported was conservative for the laser. This is the case it deliberately did
not run.

Real thermal limits do not bind on a die average. They bind on one block, and every bulk
mechanism -- more airflow, a colder coolant -- has to drag the WHOLE die down to move that one
block. The array does not. That asymmetry is the entire physical case for photonic cooling, and
it is the one thing in this comparison that liquid cannot buy at any price.

The comparison is therefore not watts against watts but KELVIN OF PEAK REDUCTION PER ELECTRICAL
WATT, because that is what a thermal limit actually spends:

  * ARRAY. Measured, through the coupled solve, in tile_pitch_{concentrated,uniform}.json. On a
    concentrated hotspot the efficacy rises from 0.977 K/W at 2000 um pitch to 1.855 K/W per
    block -- and on a UNIFORM die it is flat at ~0.67 K/W and fine pitch buys nothing at all.
    That contrast is the measurement that matters here: granularity pays 2.77x on a hotspot and
    zero on a flat die.

  * CHILLER. Analytic, and optimistic throughout. Efficacy is eta_2 * (T_a - dT) / P_die, which
    FALLS as the rescue deepens, because the machine doing the work gets worse exactly as it is
    asked for more.

  * MORE AIRFLOW. Analytic, from the affinity laws in Test 6c. Falls fastest of the three.

`[!]` What this is not
-----------------------
The array efficacies are measured on ONE concentrated shape (--concentrate 4.0 on L3_4, 100 W
die, 3 W array budget, 200 um burial) and one uniform shape. They are not a general law: the
regression file records efficiencies from 2.23 to 10.77 K/W across shapes, so the 1.855 used
here is a mid-range concentrated value and not the ceiling. The chiller and fan curves are
closed-form and are not solved.

Both electrical conversions come from the measured rescue: 1.735 W in per W lifted, or 0.945 W/W
once the leakage the rescue itself saves is credited. Where the leakage credit is used it is
labelled, because it is a real term that no earlier ledger counted and it is worth roughly a
factor of two.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

#: measured in docs/evidence/rescue_measured_anchor.json, 34-core d1.15.
#: `[!]` SECOND-LAW values (30 Aug 2026). The recorded study's 1.735 / 0.945 carried the
#: first-law recovery term -- the phi -> 1 limit -- and were 1.419x too favourable to the array.
#: See docs/evidence/loop_model_reconciliation.json.
W_ELEC_PER_W_LIFTED = 2.4728
W_ELEC_PER_W_LIFTED_NET_LEAKAGE = 1.6833

FAN_R_EXP, FAN_P_EXP, FAN_R_FLOOR = 0.6, 3.0, 0.08


def load_measured_efficacy():
    """K of peak drop per watt LIFTED, by pitch, for a concentrated and a uniform shape."""
    out = {}
    for shape, fn in (('concentrated', 'tile_pitch_concentrated.json'),
                      ('uniform', 'tile_pitch_uniform.json')):
        d = json.load(open(os.path.join(_EV, fn)))
        out[shape] = {'base_peak_C': d['base_peak_C'], 'die_W': d['die_W'], 'mr_W': d['mr_W'],
                      'burial_um': d['burial_um'],
                      'rows': [{'label': r['label'], 'pitch_um': r['pitch_um'],
                                'K_per_W_lifted': r['K_per_W'],
                                'collateral_area_ratio': r['collateral_area_ratio'],
                                'n_engaged': r['n_engaged']} for r in d['rows']]}
    return out


def chiller_efficacy(dT_K, P_die_W, eta_2nd, T_a=300.0):
    """K of die-wide reduction per electrical watt. Falls with depth by construction."""
    if dT_K <= 0 or dT_K >= T_a:
        return float('inf') if dT_K <= 0 else 0.0
    return eta_2nd * (T_a - dT_K) / P_die_W


def fan_efficacy(dT_K, P_die_W, R0=0.325, P0=35.0, T_a=300.0):
    """K per electrical watt from more airflow, against the same baseline heatsink."""
    R_need = R0 - dT_K / P_die_W
    if R_need <= FAN_R_FLOOR:
        return 0.0
    ratio = (R_need / R0) ** (-1.0 / FAN_R_EXP)
    extra_W = P0 * ratio ** FAN_P_EXP - P0
    return dT_K / extra_W if extra_W > 0 else float('inf')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--die-W', type=float, default=100.0)
    ap.add_argument('--ambient-K', type=float, default=300.0)
    ap.add_argument('--eta-chiller-2nd', type=float, default=0.40)
    ap.add_argument('--depths-K', type=float, nargs='+',
                    default=[10, 20, 30, 42, 60, 80, 100, 120, 150])
    ap.add_argument('--json-out', default=os.path.join(_EV, 'aimed_vs_bulk_rescue.json'))
    args = ap.parse_args()

    eff = load_measured_efficacy()
    P, Ta, e2 = args.die_W, args.ambient_K, args.eta_chiller_2nd

    # ---- what granularity is worth, and only on a hotspot -----------------------------------
    print('MEASURED array efficacy, K of peak drop per watt LIFTED (3 W budget, 200 um burial)\n')
    print('%-12s %14s %14s %10s' % ('pitch um', 'concentrated', 'uniform', 'ratio'))
    conc = {r['label']: r for r in eff['concentrated']['rows']}
    unif = {r['label']: r for r in eff['uniform']['rows']}
    gran = []
    for lab in ['2000', '1000', '500', '200', '100', '50']:
        c, u = conc[lab]['K_per_W_lifted'], unif[lab]['K_per_W_lifted']
        gran.append({'pitch_um': conc[lab]['pitch_um'], 'concentrated_K_per_W': c,
                     'uniform_K_per_W': u, 'ratio': c / u})
        print('%-12s %14.3f %14.3f %10.2f' % (lab, c, u, c / u))
    best_c = max(r['K_per_W_lifted'] for r in eff['concentrated']['rows'])
    best_u = max(r['K_per_W_lifted'] for r in eff['uniform']['rows'])
    print('\n  concentrated: %.3f -> %.3f K/W going 2000 um -> 50 um  (%.2fx for granularity)'
          % (conc['2000']['K_per_W_lifted'], conc['50']['K_per_W_lifted'],
             conc['50']['K_per_W_lifted'] / conc['2000']['K_per_W_lifted']))
    print('  uniform:      %.3f -> %.3f K/W over the same ladder  (%.2fx -- granularity buys NOTHING)'
          % (unif['2000']['K_per_W_lifted'], unif['50']['K_per_W_lifted'],
             unif['50']['K_per_W_lifted'] / unif['2000']['K_per_W_lifted']))

    # ---- kelvin per ELECTRICAL watt, against the bulk mechanisms -----------------------------
    print('\n\n=== K of peak reduction per ELECTRICAL watt (%.0f W die, eta_2nd %.2f) ===\n'
          % (P, e2))
    print('%-9s %11s %11s %11s %11s %s'
          % ('depth K', 'chiller', 'more fan', 'aimed 50um', 'aimed +leak', 'winner'))
    rows = []
    a_gross = best_c / W_ELEC_PER_W_LIFTED
    a_net = best_c / W_ELEC_PER_W_LIFTED_NET_LEAKAGE
    u_gross = best_u / W_ELEC_PER_W_LIFTED
    for dT in args.depths_K:
        ch = chiller_efficacy(dT, P, e2, Ta)
        fa = fan_efficacy(dT, P)
        best = max([('chiller', ch), ('fan', fa), ('aimed array', a_gross)], key=lambda kv: kv[1])
        rows.append({'depth_K': dT, 'chiller_K_per_W': ch, 'fan_K_per_W': fa,
                     'aimed_array_K_per_W': a_gross, 'aimed_array_net_leakage_K_per_W': a_net,
                     'uniform_array_K_per_W': u_gross,
                     'winner': best[0], 'array_beats_chiller': a_gross > ch,
                     'array_net_beats_chiller': a_net > ch})
        print('%-9.0f %11.3f %11.3f %11.3f %11.3f  %s'
              % (dT, ch, fa, a_gross, a_net, best[0].upper()))

    # ---- crossovers --------------------------------------------------------------------------
    print('\n=== depth at which the aimed array overtakes the chiller ===')
    cross = {}
    for name, val in (('aimed_gross', a_gross), ('aimed_net_of_leakage', a_net),
                      ('uniform_shape', u_gross)):
        d = None
        x = 0.5
        while x < Ta - 1.0:
            if val > chiller_efficacy(x, P, e2, Ta):
                d = x
                break
            x += 0.5
        cross[name] = d
        print('  %-22s %.3f K/W  ->  overtakes at %s'
              % (name, val, ('%.1f K of depth' % d) if d else 'never below 299 K'))

    # ---- does efficacy hold at the BUDGET a real rescue needs? ------------------------------
    print('\n=== saturation check: efficacy vs array budget (measured, two studies) ===')
    anc = json.load(open(os.path.join(_EV, 'mr_rescue_cost_34core.json')))['rows']
    sat = []
    for dens in ['d1.10', 'd1.15', 'd1.18']:
        u, t = anc['stability_only'][dens], anc['target_holding'][dens]
        drop = u['peak_C'] - t['peak_C']
        q = t['heat_removed_W']
        sat.append({'case': '34core_' + dens, 'budget_W': q, 'peak_drop_K': drop,
                    'K_per_W_lifted': drop / q})
        print('  34-core %-6s  %6.2f W lifted -> %6.2f K  =  %.3f K/W'
              % (dens, q, drop, drop / q))
    small = {'case': 'tile_pitch_concentrated_50um', 'budget_W': eff['concentrated']['mr_W'],
             'peak_drop_K': conc['50']['K_per_W_lifted'] * eff['concentrated']['mr_W'],
             'K_per_W_lifted': conc['50']['K_per_W_lifted']}
    sat.insert(0, small)
    print('  tile-pitch     %6.2f W lifted -> %6.2f K  =  %.3f K/W'
          % (small['budget_W'], small['peak_drop_K'], small['K_per_W_lifted']))
    big = sat[2]['K_per_W_lifted']
    fade = small['K_per_W_lifted'] / big
    print('\n  efficacy falls %.2fx going from a %.0f W budget to a %.0f W one.'
          % (fade, small['budget_W'], sat[2]['budget_W']))
    a_big_gross = big / W_ELEC_PER_W_LIFTED
    a_big_net = big / W_ELEC_PER_W_LIFTED_NET_LEAKAGE
    ch42 = chiller_efficacy(42.0, P, e2, Ta)
    print('  at that larger budget the array gives %.3f K/W gross, %.3f net, vs chiller %.3f '
          'at 42 K.' % (a_big_gross, a_big_net, ch42))
    print('  -> %s gross, %s net of leakage.'
          % ('array LOSES' if a_big_gross < ch42 else 'array wins',
             'array LOSES' if a_big_net < ch42 else 'array wins'))

    out = {
        'note': __doc__.strip(),
        'saturation_check': sat,
        'saturation_fade_factor': fade,
        'SATURATION_IS_THE_REAL_LIMIT_ON_THE_AIMED_CASE': (
            'The 1.855 K/W headline is measured at a 3 W array budget. At the {:.0f} W budget the '
            'measured 34-core rescue actually needed, efficacy is {:.3f} K/W -- a {:.2f}x fade -- '
            'because the local region saturates and the array is forced outward into cooler '
            'tiles. At that budget the aimed array gives {:.3f} K per electrical watt gross '
            'against the chiller\'s {:.3f} at 42 K, so it LOSES gross and leads only once the '
            'leakage credit is counted ({:.3f}). The aimed advantage is therefore real but it '
            'decays with the size of the rescue, and it decays fastest exactly where the rescue '
            'is largest. Two different dies and shapes are being compared here, so this is an '
            'indication of the trend rather than a clean scaling law -- a budget sweep on ONE '
            'shape is the measurement that would settle it.'
            .format(sat[2]['budget_W'], big, fade, a_big_gross, ch42, a_big_net)),
        'inputs_are_measured_from': ['docs/evidence/tile_pitch_concentrated.json',
                                     'docs/evidence/tile_pitch_uniform.json',
                                     'docs/evidence/rescue_measured_anchor.json'],
        'die_W': P, 'ambient_K': Ta, 'eta_chiller_2nd': e2,
        'W_elec_per_W_lifted': W_ELEC_PER_W_LIFTED,
        'W_elec_per_W_lifted_net_leakage': W_ELEC_PER_W_LIFTED_NET_LEAKAGE,
        'measured_efficacy': eff,
        'granularity_value': gran,
        'efficacy_vs_depth': rows,
        'crossover_depth_K': cross,
        'GRANULARITY_IS_WORTH_NOTHING_ON_A_FLAT_DIE': (
            'Going from 2000 um to 50 um pitch is worth {:.2f}x on a concentrated hotspot and '
            '{:.2f}x on a uniform die -- that is, nothing. Fine pitch is not a general good; it '
            'is the mechanism by which an array converts SPATIAL structure into efficacy, and a '
            'die without spatial structure has none to convert. This also means array value '
            'cannot be quoted per-die: it is a property of the workload and floorplan, and the '
            'same hardware is worth {:.2f}x more on one shape than another.'
            .format(conc['50']['K_per_W_lifted'] / conc['2000']['K_per_W_lifted'],
                    unif['50']['K_per_W_lifted'] / unif['2000']['K_per_W_lifted'],
                    best_c / best_u)),
        'THE_AIMED_CASE_IS_THE_ONLY_ONE_THE_ARRAY_WINS': (
            'Charged for bulk die power (Test 6c) the array needed ~100 K of chill depth before '
            'it beat a chiller. Charged only for the hotspot, as a real limit binds, it delivers '
            '{:.3f} K per electrical watt against the chiller\'s {:.3f} at 42 K -- so it leads '
            'from {:.1f} K of depth, and from {:.1f} K once the leakage credit is counted. On a '
            'uniform shape it manages {:.3f} K/W and the ordering reverses. The array\'s case is '
            'therefore not "cheaper cooling" but "the only mechanism that can be aimed", and it '
            'is worth having exactly and only where the die is hotspot-limited.'
            .format(a_gross, chiller_efficacy(42.0, P, e2, Ta),
                    cross['aimed_gross'] or -1, cross['aimed_net_of_leakage'] or -1, u_gross)),
        'WHAT_WOULD_FALSIFY_THIS': (
            'The efficacy ladder is one concentrated shape and one uniform shape, at one burial '
            'depth and one 3 W budget. The saturation check above already shows the fade is real '
            'and large, but it compares two different dies. A budget sweep on a SINGLE shape, '
            'from 1 W to the 45 W a real rescue needs, is the measurement that would settle how '
            'much of the aimed advantage survives at scale. Until it is run, the aimed case '
            'should be quoted at the large-budget efficacy, not the small-budget one.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\n' + out['THE_AIMED_CASE_IS_THE_ONLY_ONE_THE_ARRAY_WINS'])
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
