#!/usr/bin/env python
"""Test 6c: pricing the RESCUE of a die that its cooler cannot otherwise run.

    python examples/thermal_limit_rescue.py

Tests 6 and 6b both scored cooling at a fixed 250 W die, and neither enforced a junction limit.
That put them in the wrong regime twice over. Every option looked interchangeable because none
of them was actually constrained -- and the air baseline they compared against was already
ILLEGAL: 0.325 K/W on a 250 W die sits at 381.2 K, which is 108 C, past a 100 C limit and well
past 85 C. The finding that "fan + laser beats fan alone" was measured on a chip the fan cannot
run at all.

The regime that matters is the one where the chip is otherwise INOPERABLE. Below the limit,
cooling is a question of efficiency and the cheapest pump wins by definition. Above it, cooling
is a question of feasibility, and the comparison is between mechanisms that buy back headroom at
very different -- and very steeply rising -- prices.

The three rescue mechanisms, and why they diverge
--------------------------------------------------
Each buys the same thing (junction temperature) by a different route, and the routes have
different exponents:

  1. MORE AIRFLOW. Heatsink resistance falls sublinearly with flow while fan power rises with
     its cube. With R ~ CFM^-0.6 and P ~ CFM^3, fan power goes as R^-5. Rescue by fan is the
     steepest curve here and it saturates against the heatsink's conduction floor.

  2. SUB-AMBIENT CHILLER. Drop the coolant inlet below ambient and the die runs cooler at the
     same resistance. But the chiller must then lift the ENTIRE die power from T_in up to
     ambient, and its Carnot COP is T_in / (T_a - T_in), which collapses as T_in falls. This is
     the mechanism that makes unrunnable chips runnable under pure liquid today, and it is
     exactly the "collapsing COP" case: the colder you must go, the worse the machine that
     takes you there.

  3. LASER AT THE JUNCTION. The array removes heat at T_j itself. Its cost per watt is roughly
     flat in temperature, and the recovery term works in its FAVOUR as the die gets hotter,
     because phi = 1 - T_0/T_h grows (eq. 1.13).

The thermodynamic contrast is the whole point, and it is a contrast in WHERE each machine
operates. The chiller is forced to work at the coldest point in the system, sub-ambient, where
its COP is worst and still falling. The laser works at the hottest point in the system, the
junction at its limit, where its recovery is best and still rising. They move in opposite
directions against the same variable.

`[!]` What this is not
-----------------------
A single-resistance lumped model, not a solve. `T_j` here is a die-average against a die-level
R_th; a real rescue binds on a hotspot, which is the case that most favours the laser because it
is the only mechanism that can be aimed. That advantage is NOT counted here -- the laser is
charged as if it removed bulk die power -- so the crossovers below are conservative for it.

The chiller is given the optimistic reading throughout: cold side taken at the inlet temperature
(the warmest defensible choice, so the best COP), reject at ambient, and no condensation
penalty. Sub-ambient hardware in air is not usually buildable at all without sealing against
dew, and that constraint is noted but not priced.

Anti-Stokes efficiency is swept and is the input the answer turns on. eta_AS = 0.02 is near what
has been demonstrated; eta_AS = 1.0 is roughly 50x beyond it and is included as a ceiling, not a
forecast.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal import exergy as EX

R_TH = {'air_88cfm': 0.325, 'cold_plate_liquid': 0.05, 'microchannel_direct_die': 0.0153}
P_COOL_FRACTION = {'air_88cfm': 0.58, 'cold_plate_liquid': 0.05, 'microchannel_direct_die': 0.12}

#: fan affinity: resistance falls as CFM^-FAN_R_EXP, power rises as CFM^FAN_P_EXP.
FAN_R_EXP, FAN_P_EXP = 0.6, 3.0
#: heatsink conduction floor -- more air cannot beat the spreading resistance of the base.
FAN_R_FLOOR = 0.08

ETA_L = 0.85
ETA_C = 0.92


def laser_cost_per_W(T_h_K, eta_AS, eta_P_int, T_0_K, eta_L=ETA_L, eta_c=ETA_C):
    """Net wall-plug watts per watt lifted at ``T_h_K``, after recovery. Chapter 1."""
    P_L = 1.0 / (eta_AS * eta_c)
    P_in = P_L / eta_L
    P_f = eta_c * P_L * (1.0 + eta_AS)
    eta_P = eta_P_int * EX.lpc_ceiling(eta_AS, T_h_K, T_0_K)
    return P_in - eta_P * P_f


def chiller(T_in_K, T_reject_K, Q_W, eta_2nd):
    """Vapour-compression lift from ``T_in_K`` to ``T_reject_K``. Carnot times a stated fraction."""
    if T_in_K <= 1.0 or T_in_K >= T_reject_K:
        return {'needed': False, 'COP': float('inf'), 'P_W': 0.0, 'T_in_K': T_in_K}
    cop = eta_2nd * T_in_K / (T_reject_K - T_in_K)
    return {'needed': True, 'COP': cop, 'P_W': Q_W / cop, 'T_in_K': T_in_K}


def fan_rescue(R_req, R0, P0):
    """Fan power to reach ``R_req``. Returns None past the heatsink's conduction floor."""
    if R_req >= R0:
        return {'feasible': True, 'P_W': P0, 'R_th': R0, 'flow_ratio': 1.0}
    if R_req < FAN_R_FLOOR:
        return {'feasible': False, 'P_W': float('inf'), 'R_th': R_req, 'flow_ratio': float('inf')}
    ratio = (R_req / R0) ** (-1.0 / FAN_R_EXP)
    return {'feasible': True, 'P_W': P0 * ratio ** FAN_P_EXP, 'R_th': R_req, 'flow_ratio': ratio}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--Tj-max-K', type=float, default=373.15, help='junction limit (default 100 C)')
    ap.add_argument('--T0-K', type=float, default=EX.BOOK_T0_K)
    ap.add_argument('--ambient-K', type=float, default=300.0)
    ap.add_argument('--eta-AS', type=float, nargs='+', default=[0.02, 0.20, 1.00])
    ap.add_argument('--eta-P-int', type=float, default=0.6)
    ap.add_argument('--eta-chiller-2nd', type=float, nargs='+', default=[0.25, 0.40, 0.55],
                    help='chiller second-law efficiency; 0.4 is a good real vapour-compression unit')
    ap.add_argument('--overload', type=float, nargs='+',
                    default=[1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0],
                    help='die power as a multiple of what the cooler can run unaided')
    ap.add_argument('--json-out', default=os.path.join(_REPO, 'docs', 'evidence',
                                                       'thermal_limit_rescue.json'))
    args = ap.parse_args()

    Tmax, Ta, T0 = args.Tj_max_K, args.ambient_K, args.T0_K
    eta2_mid = args.eta_chiller_2nd[len(args.eta_chiller_2nd) // 2]

    # ---- what each cooler can run unaided ---------------------------------------------------
    print('junction limit %.1f K (%.1f C), ambient %.1f K, T0 %.1f K\n'
          % (Tmax, Tmax - 273.15, Ta, T0))
    print('%-26s %10s %12s %14s' % ('cooler', 'R_th K/W', 'P_max W', 'at 250 W'))
    limits = {}
    for k, r in sorted(R_TH.items(), key=lambda kv: -kv[1]):
        pmax = (Tmax - Ta) / r
        Tj250 = Ta + r * 250.0
        limits[k] = {'R_th_K_per_W': r, 'P_max_unaided_W': pmax, 'T_j_at_250W_K': Tj250,
                     'operable_at_250W': Tj250 <= Tmax}
        print('%-26s %10.4f %12.1f %10.1f K %s'
              % (k, r, pmax, Tj250, '' if Tj250 <= Tmax else 'INOPERABLE'))

    # ---- laser cost per watt at the junction limit ------------------------------------------
    print('\nlaser net cost per watt lifted, operating at T_j = %.1f K (phi %.4f):'
          % (Tmax, EX.carnot_factor(Tmax, T0)))
    laser_cpw = {}
    for eas in args.eta_AS:
        c = laser_cost_per_W(Tmax, eas, args.eta_P_int, T0)
        laser_cpw[eas] = c
        print('   eta_AS %-5.2f -> %9.3f W/W   (COP %6.3f)' % (eas, c, 1.0 / c if c > 0 else float('inf')))

    # ---- the rescue sweep -------------------------------------------------------------------
    rows = []
    for k in sorted(R_TH, key=lambda x: -R_TH[x]):
        L = limits[k]
        r, pmax = L['R_th_K_per_W'], L['P_max_unaided_W']
        pump0 = P_COOL_FRACTION[k] * 250.0
        print('\n\n=== %s : rescuing a die past its %.0f W unaided limit ==='
              % (k, pmax))
        print('%8s %8s %10s %10s %9s %s'
              % ('die W', 'T_in req', 'chiller W', 'COP_ch', 'sysCOP', '| laser hybrid, W and sysCOP by eta_AS'))
        for ov in args.overload:
            P = pmax * ov
            T_in_req = Tmax - r * P                      # coolant inlet the package would need
            ch = chiller(T_in_req, Ta, P, eta2_mid)
            pump = pump0 * (P / 250.0)                   # pumping scales with heat moved
            p_chill_total = pump + ch['P_W']
            row = {'baseline': k, 'overload': ov, 'die_W': P, 'T_in_required_K': T_in_req,
                   'chiller_needed': ch['needed'], 'chiller_COP': ch['COP'],
                   'chiller_W': ch['P_W'], 'pump_W': pump,
                   'chiller_route_cool_W': p_chill_total,
                   'chiller_route_sysCOP': P / p_chill_total if p_chill_total > 0 else float('inf'),
                   'laser_route': {}}
            # laser route: package runs unaided at its limit, array lifts the excess
            Q_L = max(0.0, P - pmax)
            for eas in args.eta_AS:
                cost = laser_cpw[eas] * Q_L
                tot = pump0 * (pmax / 250.0) + cost
                row['laser_route'][str(eas)] = {
                    'Q_laser_W': Q_L, 'laser_net_W': cost, 'cool_W': tot,
                    'sysCOP': P / tot if tot > 0 else float('inf'),
                    'beats_chiller': tot < p_chill_total}
            # fan-only rescue, where it applies
            if k == 'air_88cfm':
                fr = fan_rescue((Tmax - Ta) / P, r, 35.0)
                row['fan_route'] = {'feasible': fr['feasible'], 'P_W': fr['P_W'],
                                    'flow_ratio': fr['flow_ratio'],
                                    'sysCOP': P / fr['P_W'] if fr['feasible'] and fr['P_W'] > 0
                                    else 0.0}
            rows.append(row)
            tail = '  |'
            for eas in args.eta_AS:
                lr = row['laser_route'][str(eas)]
                tail += ' %8.1fW/%5.2f%s' % (lr['cool_W'], lr['sysCOP'],
                                             '*' if lr['beats_chiller'] else ' ')
            print('%8.0f %7.1fK %9.1f %10.3f %9.2f%s'
                  % (P, T_in_req, ch['P_W'], ch['COP'], row['chiller_route_sysCOP'], tail))
        if k == 'air_88cfm':
            print('  fan-only rescue (more airflow):')
            for rr in [x for x in rows if x['baseline'] == k]:
                f = rr['fan_route']
                print('     %8.0f W -> %s' % (rr['die_W'],
                      ('%.0f W fan, %.1fx flow, sysCOP %.2f' % (f['P_W'], f['flow_ratio'], f['sysCOP']))
                      if f['feasible'] else 'IMPOSSIBLE (past heatsink conduction floor)'))

    # ---- where the laser overtakes the chiller ----------------------------------------------
    print('\n\n=== CROSSOVER: die power above which the laser hybrid beats the chiller ===')
    print('%-26s %-9s %14s %14s %12s'
          % ('baseline', 'eta_AS', 'crossover W', 'x unaided', 'T_in there'))
    cross = []
    for k in sorted(R_TH, key=lambda x: -R_TH[x]):
        r, pmax = R_TH[k], limits[k]['P_max_unaided_W']
        pump0 = P_COOL_FRACTION[k] * 250.0
        for eas in args.eta_AS:
            found = None
            P = pmax
            while P < pmax * 20.0:
                P *= 1.005
                T_in = Tmax - r * P
                ch = chiller(T_in, Ta, P, eta2_mid)
                tot_ch = pump0 * (P / 250.0) + ch['P_W']
                tot_las = pump0 * (pmax / 250.0) + laser_cpw[eas] * (P - pmax)
                if tot_las < tot_ch:
                    found = (P, T_in)
                    break
            cross.append({'baseline': k, 'eta_AS': eas,
                          'crossover_die_W': found[0] if found else None,
                          'crossover_x_unaided': found[0] / pmax if found else None,
                          'T_in_at_crossover_K': found[1] if found else None})
            print('%-26s %-9.2f %14s %14s %12s'
                  % (k, eas,
                     '%.0f' % found[0] if found else 'none < 20x',
                     '%.2f' % (found[0] / pmax) if found else '-',
                     '%.1f K' % found[1] if found else '-'))

    # ---- chiller second-law sensitivity ------------------------------------------------------
    print('\n=== chiller efficiency sensitivity (cold plate at 2x its unaided limit) ===')
    sens = []
    r, pmax = R_TH['cold_plate_liquid'], limits['cold_plate_liquid']['P_max_unaided_W']
    P = 2.0 * pmax
    T_in = Tmax - r * P
    for e2 in args.eta_chiller_2nd:
        ch = chiller(T_in, Ta, P, e2)
        sens.append({'eta_2nd': e2, 'die_W': P, 'T_in_K': T_in, 'COP': ch['COP'],
                     'chiller_W': ch['P_W']})
        print('   eta_2nd %.2f -> COP %.3f, chiller %.0f W to run a %.0f W die at T_in %.1f K'
              % (e2, ch['COP'], ch['P_W'], P, T_in))

    out = {
        'note': __doc__.strip(),
        'supersedes': ('docs/evidence/hybrid_cooling_ledger.json and liquid_vs_photonic.json, '
                       'both of which scored a fixed 250 W die and enforced no junction limit'),
        'Tj_max_K': Tmax, 'ambient_K': Ta, 'T0_K': T0,
        'eta_L': ETA_L, 'eta_c': ETA_C, 'eta_P_int': args.eta_P_int,
        'eta_chiller_2nd_used': eta2_mid,
        'fan_model': {'R_exp': FAN_R_EXP, 'P_exp': FAN_P_EXP, 'R_floor_K_per_W': FAN_R_FLOOR},
        'unaided_limits': limits,
        'laser_cost_per_W_at_Tj_max': {str(k): v for k, v in laser_cpw.items()},
        'rescue_sweep': rows,
        'crossovers': cross,
        'chiller_sensitivity': sens,
        'THE_EARLIER_TESTS_WERE_IN_THE_WRONG_REGIME': (
            'Tests 6 and 6b fixed the die at 250 W and never checked T_j. At 0.325 K/W that is '
            '381.2 K = 108 C, past a 100 C limit and past 85 C -- so the air baseline they '
            'compared against could not run the chip at all, and the "fan + laser beats fan" '
            'result was scored on an illegal operating point. Below the thermal limit the '
            'cheapest pump wins by construction and the comparison is close to meaningless; the '
            'question only becomes interesting above it.'),
        'THE_CONTRAST_IS_WHERE_EACH_MACHINE_WORKS': (
            'The chiller is forced to operate at the coldest point in the system and its COP '
            'falls as T_in falls, so the deeper the rescue the worse the machine performing it. '
            'The laser operates at the hottest point -- the junction at its limit -- where phi is '
            'largest and its recovery term is best. The two mechanisms move in OPPOSITE '
            'directions against the same variable, which is why a crossover exists at all and '
            'why it is not sensitive to modest changes in either efficiency.'),
        'SPATIAL_SELECTIVITY_IS_NOT_COUNTED': (
            'The laser is charged here as though it lifted bulk die power. Real thermal limits '
            'bind on a hotspot, and the array is the only mechanism in this comparison that can '
            'be aimed at one -- so every crossover reported is conservative for the laser, '
            'probably substantially. Pricing the aimed case needs the per-tile map from Test 3 '
            'rather than this lumped model.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
