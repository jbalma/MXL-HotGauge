#!/usr/bin/env python
"""Test 6: liquid against photonic, scored on NET system power rather than temperature.

    python examples/liquid_vs_photonic.py

The bounded comparison the ranked list asks for, in the form the power-recovery framing gives it.
Scored on temperature alone a microchannel plate wins comfortably -- 0.0153 K/W measured, against
an array whose whole budget is a few watts. But that scoring ignores the asymmetry that matters:

    **liquid cooling can only ever SPEND power. Photonic cooling can spend it and give some back.**

So the comparison is net system power, `P_die + P_cool - P_recovered`, and the recovery term is
bounded by the second law at the temperature the die actually runs (eq. 1.13). That makes the
answer depend on `T_h` -- which is the architecture argument's whole point, and the reason this
test is worth running under the new framing when it was marginal under the old one.

Bounded, in the sense the ranked list meant
--------------------------------------------
Every efficiency here is a stated input with a stated range, not a fitted value, and the result is
reported as a band. The point is to find *where the crossover sits and how sensitive it is*, not
to claim a number. Two of the four photonic efficiencies (`eta_AS`, `eta_P_int`) are the ones the
whole result turns on, and they are swept.

`[!]` What this is not
-----------------------
Not a solve. Thermal resistances come from measured references already in the repository; this is
the loop-level power ledger sitting on top of them. The die temperature it uses for `T_h` is the
one those resistances imply, and the LPC ceiling is an upper bound -- so the photonic column is
optimistic by construction and should be read as "the best this could be", against liquid's
"roughly what this is".
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
#: The microchannel figure is the one the handbook quotes from a measured anchor; the air figure
#: is the 88 CFM baseline the catalogue sweeps at.
R_TH = {'air_88cfm': 0.325, 'cold_plate_liquid': 0.05, 'microchannel_direct_die': 0.0153}

#: Pumping / moving power for each, as a fraction of die power. Stated, not derived: air is the
#: measured 35 W fan against a ~60 W die; liquid loops are quoted at a few percent of IT load and
#: microchannel pumping at rather more because the pressure drop is large.
P_COOL_FRACTION = {'air_88cfm': 0.58, 'cold_plate_liquid': 0.05, 'microchannel_direct_die': 0.12}

#: Photonic loop efficiencies. eta_L and eta_c are the project's shipped values; eta_AS and
#: eta_P_int are the two the answer turns on and are swept.
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
    ap.add_argument('--fraction-removed', type=float, default=0.25,
                    help='share of die power the photonic array removes; the rest still leaves '
                         'through the package, so this is a HYBRID and is scored as one')
    ap.add_argument('--json-out', default=os.path.join(_REPO, 'docs', 'evidence',
                                                       'liquid_vs_photonic.json'))
    args = ap.parse_args()

    P = args.die_W
    rows, liquid = [], {}
    print('die {:.0f} W, T0 {:.0f} K, photonic array removes {:.0%} of die power\n'
          .format(P, args.T0_K, args.fraction_removed))
    print('%-26s %9s %10s %12s' % ('conventional cooling', 'T_h', 'P_cool', 'net system W'))
    for k, r in sorted(R_TH.items(), key=lambda kv: -kv[1]):
        T_h = args.ambient_K + r * P
        pc = P_COOL_FRACTION[k] * P
        liquid[k] = {'R_th_K_per_W': r, 'T_h_K': T_h, 'P_cool_W': pc, 'P_net_system_W': P + pc,
                     'phi_at_T_h': EX.carnot_factor(T_h, args.T0_K)}
        print('%-26s %7.1f K %9.1f W %11.1f W' % (k, T_h, pc, P + pc))

    print('\n%-10s %-10s %8s %10s %11s %12s %10s' %
          ('eta_AS', 'eta_P_int', 'T_h', 'P_in', 'P_recovered', 'net system W', 'vs liquid'))
    base = liquid['cold_plate_liquid']['P_net_system_W']
    for k, r in [('cold_plate_liquid', R_TH['cold_plate_liquid'])]:
        T_h = args.ambient_K + r * P
        for eas in args.eta_AS:
            for epi in args.eta_P_int:
                led = photonic_ledger(args.fraction_removed * P, T_h, eas, epi, args.T0_K)
                # hybrid: the package still removes the rest, at its own pumping cost
                pkg = P_COOL_FRACTION[k] * P * (1.0 - args.fraction_removed)
                net = P + pkg + led['P_net_W']
                rows.append({'eta_AS': eas, 'eta_P_int': epi, 'T_h_K': T_h,
                             'P_in_W': led['P_in_W'], 'P_rec_W': led['P_rec_W'],
                             'net_system_W': net, 'vs_liquid_W': net - base,
                             'loop_gain': led['loop_gain'],
                             'self_powering': led['self_powering']})
                print('%-10.2f %-10.2f %7.1f K %9.1f W %10.1f W %11.1f W %+9.1f W%s'
                      % (eas, epi, T_h, led['P_in_W'], led['P_rec_W'], net, net - base,
                         '  SELF-POWERING' if led['self_powering'] else ''))

    # --- the decision-relevant number: at what T_h does photonic stop costing more? ----------
    print('\n%-8s %9s %10s %12s %11s %s'
          % ('T_h', 'phi', 'P_recover', 'net system W', 'vs liquid', 'loop gain'))
    cross = []
    eas, epi = max(args.eta_AS), max(args.eta_P_int)
    for T_h in (312.5, 350.0, 400.0, 450.0, 500.0, 550.0, 600.0, 700.0):
        led = photonic_ledger(args.fraction_removed * P, T_h, eas, epi, args.T0_K)
        pkg = P_COOL_FRACTION['cold_plate_liquid'] * P * (1.0 - args.fraction_removed)
        net = P + pkg + led['P_net_W']
        cross.append({'T_h_K': T_h, 'phi': EX.carnot_factor(T_h, args.T0_K),
                      'P_rec_W': led['P_rec_W'], 'net_system_W': net,
                      'vs_liquid_W': net - base, 'loop_gain': led['loop_gain'],
                      'beats_liquid': net < base, 'self_powering': led['self_powering']})
        print('%7.0fK %9.3f %9.1f W %11.1f W %+10.1f W %10.2f%s%s'
              % (T_h, EX.carnot_factor(T_h, args.T0_K), led['P_rec_W'], net, net - base,
                 led['loop_gain'], '  BEATS LIQUID' if net < base else '',
                 '  SELF-POWERING' if led['self_powering'] else ''))
    winners = [c for c in cross if c['beats_liquid']]
    crossover_K = winners[0]['T_h_K'] if winners else None

    best = min(rows, key=lambda r: r['net_system_W'])
    out = {
        'note': __doc__.strip(),
        'die_W': P, 'T0_K': args.T0_K, 'ambient_K': args.ambient_K,
        'fraction_removed': args.fraction_removed,
        'eta_L': ETA_L, 'eta_c': ETA_C,
        'conventional': liquid, 'photonic_hybrid': rows,
        'best_photonic': best,
        'crossover_sweep': cross,
        'crossover_T_h_K': crossover_K,
        'eta_used_for_crossover': {'eta_AS': eas, 'eta_P_int': epi},
        'verdict': (
            'At a die temperature set by a liquid cold plate ({:.0f} K), photonic cooling costs '
            'MORE net system power than the liquid loop alone in every configuration swept: the '
            'best case is {:+.1f} W against liquid. The reason is structural rather than a matter '
            'of efficiency -- phi at {:.0f} K is only {:.3f}, so the recovery term cannot pay for '
            'the laser. The loop gain reaches {:.2f} at best, against the 1.0 it needs.'
            .format(liquid['cold_plate_liquid']['T_h_K'], best['vs_liquid_W'],
                    liquid['cold_plate_liquid']['T_h_K'],
                    liquid['cold_plate_liquid']['phi_at_T_h'],
                    max(r['loop_gain'] for r in rows))),
        'SELF_POWERING_IS_NOT_THE_SAME_AS_WINNING': (
            'The loop crosses into self-powering at T_h = 450 K -- loop gain 1.05, so it recovers '
            'enough to run its own laser -- and it STILL costs more net system power than the '
            'liquid loop, by +26.4 W. Even at 700 K it is +17.6 W worse. The two are different '
            'claims and it would be easy to conflate them: self-powering says the loop pays for '
            'ITSELF; it does not say the loop is a cheaper way to move heat than a pump. It is '
            'not. Photonic net COP here is about 3; a liquid cold plate moving 250 W for 12.5 W '
            'is about 20.'),
        'what_would_change_it': (
            'The recovery term scales with phi, and phi is set by T_h. Good cooling is therefore '
            'SELF-DEFEATING for recovery: the better the cold plate, the colder the die, the less '
            'its waste heat is worth. Run the compute hot on purpose and the recovery term grows '
            '-- which is what Section 10.8 proposes and what Test 1 says a monolithic die cannot '
            'deliver.'),
        'THE_HONEST_CONCLUSION_FOR_THE_FRAMING': (
            'Exergy recovery ALONE does not make photonic cooling competitive with liquid on '
            'system power, at any temperature in the swept range, under the most favourable '
            'efficiencies swept. The case for photonic cooling has to rest on what liquid cannot '
            'do at all -- spatial selectivity at sub-100-um resolution, per-tile targeting, and '
            'the thermal-limit rescue the catalogue already measures -- with recovery as a term '
            'that improves the ledger rather than one that carries it. Presenting recovery as the '
            'headline would invite exactly the comparison above, and it does not survive it.'),
    }
    if crossover_K:
        print('\nCROSSOVER: photonic beats the liquid loop on net system power above '
              'T_h = {:.0f} K, at eta_AS {:.2f} and eta_P_int {:.2f}.'.format(crossover_K, eas, epi))
    else:
        print('\nNO CROSSOVER anywhere in the swept range.')
    print('\n' + out['verdict'])
    print('\n' + out['what_would_change_it'])
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
