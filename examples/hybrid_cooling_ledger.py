#!/usr/bin/env python
"""Test 6b: every conventional cooler, alone vs. that same cooler PLUS laser cooling.

    python examples/hybrid_cooling_ledger.py

Supersedes the sweep in ``examples/liquid_vs_photonic.py``, which asked the right question of
only one baseline. That script's photonic arm was already a hybrid -- the package kept removing
the heat the array did not, at its own pumping cost -- but the sweep loop ran a single entry,
``cold_plate_liquid``, and reported every row against the liquid number. Air and microchannel
were tabulated as baselines and never paired with a laser. This runs all of them, and scores
each hybrid against ITS OWN baseline:

    fan alone          vs   fan + laser
    cold plate alone   vs   cold plate + laser
    microchannel alone vs   microchannel + laser

That matters because the baseline is not a neutral reference -- it sets BOTH terms of the
photonic ledger at once, in the same direction:

  * it sets ``T_h``, and therefore ``phi``, and therefore how much of the lifted heat is
    recoverable as work (eq. 1.13). A worse cooler runs the die hotter and makes recovery
    worth more.
  * it sets the pumping power the laser is displacing. A worse cooler costs more to run, so
    each watt the laser takes over saves more.

Air is worse than liquid on both, so it is the most favourable hybrid partner, and it is the one
the earlier sweep never ran.

The fraction-removed result
---------------------------
With a linear pumping model the sign of the answer does not depend on how much heat the array
takes over. Writing ``f`` for the fraction removed:

    delta = (P_in - P_rec) - f * P_cool = f * [ P_die * c_laser - P_cool ]

where ``c_laser`` is the laser loop's net wall-plug cost per watt removed. Both terms are linear
in ``f``, so ``f`` scales the margin but cannot flip it. The decision therefore reduces to a
single comparison of per-watt costs, which is what this script reports:

    the hybrid wins iff   c_laser (W in per W removed)  <  the baseline's own W per W removed.

`[!]` What this is not
-----------------------
``T_h`` is held at the value the baseline cooler alone implies. A real hybrid removing 25 % of
the heat would run the die COLDER than that, or hold temperature and pass more power -- so the
laser gets no credit here for the thermal headroom it buys, which is the term the catalogue
already measures separately. This ledger is therefore conservative for the laser on temperature
and optimistic on recovery (the LPC ceiling is an upper bound). Neither is a solve.

The air baseline's pumping fraction is the measured 35 W fan against a ~60 W die, held constant
as a FRACTION out to a 250 W die. That is a stated extrapolation, not a measurement, and it is
the single input the air result is most sensitive to -- so it is swept.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal import exergy as EX

#: Measured reference resistances already in this repository [K/W], die-level.
R_TH = {'air_88cfm': 0.325, 'cold_plate_liquid': 0.05, 'microchannel_direct_die': 0.0153}

#: Moving power for each, as a fraction of die power. Stated inputs, not derived.
P_COOL_FRACTION = {'air_88cfm': 0.58, 'cold_plate_liquid': 0.05, 'microchannel_direct_die': 0.12}

ETA_L = 0.85
ETA_C = 0.92


def photonic_ledger(Q_c_W, T_h_K, eta_AS, eta_P_int, T_0_K, eta_L=ETA_L, eta_c=ETA_C):
    """Wall-plug in, electrical out, for removing ``Q_c_W`` at ``T_h_K``. All from Chapter 1."""
    P_L = Q_c_W / (eta_AS * eta_c)                 # (1.1) rearranged
    P_in = P_L / eta_L
    P_f = eta_c * P_L * (1.0 + eta_AS)             # (1.2)
    eta_P = eta_P_int * EX.lpc_ceiling(eta_AS, T_h_K, T_0_K)   # (1.13)-(1.14)
    P_rec = eta_P * P_f                            # (1.6)
    return {'P_L_W': P_L, 'P_in_W': P_in, 'P_f_W': P_f, 'eta_P': eta_P,
            'P_rec_W': P_rec, 'P_net_W': P_in - P_rec,
            'cost_per_W_removed': (P_in - P_rec) / Q_c_W if Q_c_W else float('nan'),
            'loop_gain': EX.loop_gain(eta_L, eta_c, eta_AS, T_h_K, T_0_K),
            'self_powering': EX.loop_gain(eta_L, eta_c, eta_AS, T_h_K, T_0_K) >= 1.0}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--die-W', type=float, default=250.0)
    ap.add_argument('--T0-K', type=float, default=EX.BOOK_T0_K)
    ap.add_argument('--ambient-K', type=float, default=300.0)
    ap.add_argument('--eta-AS', type=float, nargs='+', default=[0.02, 0.20, 0.50, 1.00])
    ap.add_argument('--eta-P-int', type=float, nargs='+', default=[0.3, 0.6])
    ap.add_argument('--fraction-removed', type=float, nargs='+', default=[0.10, 0.25, 0.50],
                    help='share of die power the array takes over; swept to show the sign of the '
                         'answer does not depend on it')
    ap.add_argument('--air-pumping-fraction', type=float, nargs='+', default=[0.29, 0.58],
                    help='the 250 W extrapolation of the measured 35 W / 60 W fan, and half it')
    ap.add_argument('--json-out', default=os.path.join(_REPO, 'docs', 'evidence',
                                                       'hybrid_cooling_ledger.json'))
    args = ap.parse_args()

    P = args.die_W
    baselines = {}
    print('die {:.0f} W, T0 {:.0f} K, ambient {:.0f} K\n'.format(P, args.T0_K, args.ambient_K))
    print('%-26s %8s %8s %10s %12s %10s'
          % ('cooler alone', 'T_h', 'phi', 'P_cool', 'net system W', 'W per W'))
    for k, r in sorted(R_TH.items(), key=lambda kv: -kv[1]):
        T_h = args.ambient_K + r * P
        pc = P_COOL_FRACTION[k] * P
        baselines[k] = {'R_th_K_per_W': r, 'T_h_K': T_h, 'P_cool_W': pc,
                        'P_net_system_W': P + pc,
                        'W_per_W_removed': P_COOL_FRACTION[k],
                        'phi_at_T_h': EX.carnot_factor(T_h, args.T0_K)}
        print('%-26s %6.1f K %8.4f %8.1f W %11.1f W %9.3f'
              % (k, T_h, EX.carnot_factor(T_h, args.T0_K), pc, P + pc, P_COOL_FRACTION[k]))

    # ---- every cooler, alone vs. that cooler + laser, scored against ITSELF -----------------
    rows = []
    for k in sorted(R_TH, key=lambda x: -R_TH[x]):
        b = baselines[k]
        print('\n=== %s  ALONE (%.1f W)  vs  %s + LASER ==='
              % (k, b['P_net_system_W'], k))
        print('%-8s %-10s %-6s %9s %11s %12s %11s %9s'
              % ('eta_AS', 'eta_P_int', 'f', 'P_in', 'P_recovered', 'net system W',
                 'vs alone', 'W per W'))
        for eas in args.eta_AS:
            for epi in args.eta_P_int:
                for f in args.fraction_removed:
                    led = photonic_ledger(f * P, b['T_h_K'], eas, epi, args.T0_K)
                    pkg = b['P_cool_W'] * (1.0 - f)
                    net = P + pkg + led['P_net_W']
                    d = net - b['P_net_system_W']
                    rows.append({'baseline': k, 'eta_AS': eas, 'eta_P_int': epi,
                                 'fraction_removed': f, 'T_h_K': b['T_h_K'],
                                 'P_in_W': led['P_in_W'], 'P_rec_W': led['P_rec_W'],
                                 'net_system_W': net, 'vs_own_baseline_W': d,
                                 'laser_W_per_W_removed': led['cost_per_W_removed'],
                                 'baseline_W_per_W_removed': b['W_per_W_removed'],
                                 'beats_own_baseline': d < 0.0,
                                 'loop_gain': led['loop_gain'],
                                 'self_powering': led['self_powering']})
                    print('%-8.2f %-10.2f %-6.2f %8.1f W %10.1f W %11.1f W %+10.1f W %8.3f%s%s'
                          % (eas, epi, f, led['P_in_W'], led['P_rec_W'], net, d,
                             led['cost_per_W_removed'],
                             '  BEATS' if d < 0 else '',
                             '  SELF-POW' if led['self_powering'] else ''))

    # ---- the f-independent decision number --------------------------------------------------
    print('\n\n=== BREAKEVEN: laser net cost per watt removed, vs what the baseline itself '
          'pays ===')
    print('(the hybrid wins iff the laser column is BELOW the baseline column; f cancels)\n')
    print('%-26s %10s %12s %12s %10s'
          % ('baseline', 'T_h', 'baseline W/W', 'laser W/W', 'verdict'))
    breakeven = []
    eas, epi = max(args.eta_AS), max(args.eta_P_int)
    for k in sorted(R_TH, key=lambda x: -R_TH[x]):
        b = baselines[k]
        led = photonic_ledger(1.0, b['T_h_K'], eas, epi, args.T0_K)
        c = led['cost_per_W_removed']
        wins = c < b['W_per_W_removed']
        breakeven.append({'baseline': k, 'T_h_K': b['T_h_K'],
                          'baseline_W_per_W': b['W_per_W_removed'], 'laser_W_per_W': c,
                          'ratio_laser_over_baseline': c / b['W_per_W_removed'],
                          'hybrid_beats_baseline': wins})
        print('%-26s %8.1f K %12.3f %12.3f %10s'
              % (k, b['T_h_K'], b['W_per_W_removed'], c, 'HYBRID WINS' if wins else 'loses'))

    # ---- sensitivity of the air result to the one input it turns on -------------------------
    print('\n=== air baseline: sensitivity to the fan-power extrapolation ===')
    air_sens = []
    b = baselines['air_88cfm']
    led = photonic_ledger(1.0, b['T_h_K'], eas, epi, args.T0_K)
    c = led['cost_per_W_removed']
    for frac in args.air_pumping_fraction:
        wins = c < frac
        air_sens.append({'air_pumping_fraction': frac, 'laser_W_per_W': c,
                         'hybrid_beats_air': wins})
        print('  fan at %.2f W/W  vs laser %.3f W/W  ->  %s'
              % (frac, c, 'HYBRID WINS' if wins else 'loses'))

    air_wins = [r for r in rows if r['baseline'] == 'air_88cfm' and r['beats_own_baseline']]
    liq_wins = [r for r in rows if r['baseline'] == 'cold_plate_liquid'
                and r['beats_own_baseline']]
    out = {
        'note': __doc__.strip(),
        'supersedes': 'docs/evidence/liquid_vs_photonic.json (single baseline: cold plate only)',
        'die_W': P, 'T0_K': args.T0_K, 'ambient_K': args.ambient_K,
        'eta_L': ETA_L, 'eta_c': ETA_C,
        'baselines_alone': baselines,
        'hybrid_rows': rows,
        'breakeven_per_watt': breakeven,
        'air_pumping_sensitivity': air_sens,
        'eta_used_for_breakeven': {'eta_AS': eas, 'eta_P_int': epi},
        'n_air_hybrid_wins': len(air_wins), 'n_liquid_hybrid_wins': len(liq_wins),
        'THE_BASELINE_SETS_BOTH_TERMS': (
            'The conventional cooler is not a neutral reference. It sets T_h -- and therefore '
            'phi, and therefore what fraction of the lifted heat is recoverable -- AND it sets '
            'the pumping power the laser displaces. Both move the same way, so the comparison is '
            'far more sensitive to which baseline you pick than to the photonic efficiencies. '
            'Air runs the die at {:.0f} K (phi {:.4f}) against the cold plate\'s {:.0f} K (phi '
            '{:.4f}) -- {:.2f}x the recoverable fraction -- while costing {:.1f} W to run against '
            '{:.1f} W, so each watt the array takes over displaces {:.1f}x more pumping.'
            .format(baselines['air_88cfm']['T_h_K'], baselines['air_88cfm']['phi_at_T_h'],
                    baselines['cold_plate_liquid']['T_h_K'],
                    baselines['cold_plate_liquid']['phi_at_T_h'],
                    baselines['air_88cfm']['phi_at_T_h']
                    / baselines['cold_plate_liquid']['phi_at_T_h'],
                    baselines['air_88cfm']['P_cool_W'],
                    baselines['cold_plate_liquid']['P_cool_W'],
                    baselines['air_88cfm']['P_cool_W']
                    / baselines['cold_plate_liquid']['P_cool_W'])),
        'FRACTION_REMOVED_CANNOT_FLIP_THE_SIGN': (
            'With a linear pumping model both the laser cost and the displaced pumping scale '
            'with the fraction removed, so f scales the margin and cannot change who wins. The '
            'decision is entirely a comparison of per-watt costs, which is why it is reported '
            'that way. This is a property of the model, not a measurement -- a real pump or fan '
            'curve is not linear, and at small f a fan may not step down at all.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
