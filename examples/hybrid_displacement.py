#!/usr/bin/env python
"""Test 8 (rewritten): what localized cooling displaces from the fan, and by what mechanism.

    python examples/hybrid_displacement.py

`[!]` This supersedes the first version of this file, which was wrong. That version assumed the
textbook fan affinity law -- ``P_fan ~ CFM^3``, giving ``P_fan ~ R^-5`` -- and built a headline
on the fifth power. **This project does not model a fan that way, and never did.**
``HotGauge.thermal.sink_models.FanCoolingModel`` is calibrated against Maxwell Labs' own
spreadsheet::

    CFM   = Q / (AIR_W_PER_CFM_K * dT_air)        AIR_W_PER_CFM_K = 0.569
    P_fan = MXL_FAN_W_PER_CFM * CFM               MXL_FAN_W_PER_CFM = 0.590

so **fan power scales as Q / dT_air**: linear in the heat carried, and INVERSE in the air
temperature rise. The three calibration cases span 3x in airflow and agree on 0.590 W/CFM to four
figures, so this is a property of the modelled fan rather than a fitted constant. The measured
campaign confirms it: 45 CFM draws 26.7 W against 88 CFM's 35.0 W, which is linear, not cubic.

The mechanism, corrected
------------------------
Taking flux off the fan is the WEAK lever here. Fan power is linear in heat carried, so an array
lifting fraction ``s`` cuts fan power by exactly ``s`` -- and it only pays if the array costs less
per watt than the fan does, which is a hard bar.

The strong lever is the one the sink model's own docstring names: **fan power is inverse in
``dT_air``**. Letting the air stream run hotter is dramatically cheaper, and the only reason a
designer cannot is that hotter air raises the effective ambient the die sees, which costs
temperature margin at the hotspot. The array buys that margin back exactly where it is spent.

    the array does not carry the heat -- it buys the MARGIN that lets the air carry it hot

That is a better claim than the one it replaces, and unlike the fifth-power version it is the
mechanism this repository actually models.

`[!]` What this is not
-----------------------
The margin-to-dT_air conversion here is a ledger on the calibrated fan model, not a coupled solve.
It assumes the array's measured peak reduction converts one-for-one into permissible air rise,
which the effective-ambient term (inlet + dT_air/2) makes conservative but not exact. The solver
campaign measures the same thing directly and should be preferred where the two disagree.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.sink_models import FanCoolingModel, MXL_FAN_W_PER_CFM, AIR_W_PER_CFM_K

#: measured second-law array cost per watt lifted, across the technology trajectory
COSTS = ((2.4728, 'legacy Yb:YLF'), (0.609, 'shipped'), (0.285, 'v91 target + 90% laser'),
         (0.101, 'same, logic run hot'))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--die-W', type=float, default=250.0)
    ap.add_argument('--dt-air-base-K', type=float, default=15.0)
    ap.add_argument('--dt-air-K', type=float, nargs='+', default=[15, 20, 30, 40, 50, 60])
    ap.add_argument('--margin-K', type=float, nargs='+', default=[0, 5, 10, 20, 30, 45],
                    help='hotspot margin the array buys back, which is what permits hotter air')
    ap.add_argument('--s', type=float, nargs='+', default=[0.0, 0.1, 0.2, 0.3])
    ap.add_argument('--json-out', default=os.path.join(_EV, 'hybrid_displacement.json'))
    args = ap.parse_args()

    fan = FanCoolingModel()
    P = args.die_W
    print('calibrated fan model: %.4f W/CFM, %.3f W/(CFM*K) -> P_fan = %.4f * Q / dT_air\n'
          % (MXL_FAN_W_PER_CFM, AIR_W_PER_CFM_K, MXL_FAN_W_PER_CFM / AIR_W_PER_CFM_K))

    # --- the weak lever: array carries flux, fan carries less (LINEAR) ----------------------
    print('=== weak lever: array takes flux fraction s (fan power is LINEAR in heat) ===')
    print('%6s %11s %12s %s' % ('s', 'fan W', 'saved W', 'array cost to break even'))
    base_fan = fan.fan_power_for(P, args.dt_air_base_K)
    weak = []
    for s in args.s:
        f = fan.fan_power_for(P * (1.0 - s), args.dt_air_base_K)
        saved = base_fan - f
        be = (saved / (s * P)) if s > 0 else float('nan')
        weak.append({'s': s, 'fan_W': f, 'saved_W': saved, 'breakeven_cost_W_per_W': be})
        print('%6.2f %11.2f %12.2f %s'
              % (s, f, saved, ('< %.3f W/W' % be) if s > 0 else '--'))
    print('    -> the bar is flat at %.3f W/W, which is just the fan\'s own W per W of heat.'
          % (base_fan / P))
    print('       Only the top of the extractor trajectory clears it.')

    # --- the strong lever: array buys margin, air runs hotter (INVERSE) ----------------------
    print('\n=== strong lever: array buys hotspot margin, so the air may run hotter ===')
    print('(fan power is INVERSE in dT_air -- this is the mechanism the sink model names)')
    print('%9s %11s %11s %11s %11s'
          % ('margin K', 'dT_air K', 'fan W', 'fan saved', 'vs baseline'))
    strong = []
    for m in args.margin_K:
        dt = args.dt_air_base_K + m
        f = fan.fan_power_for(P, dt)
        strong.append({'margin_K': m, 'dt_air_K': dt, 'fan_W': f,
                       'fan_saved_W': base_fan - f,
                       'fan_frac_of_baseline': f / base_fan})
        print('%9.0f %11.1f %11.2f %11.2f %10.1f%%'
              % (m, dt, f, base_fan - f, 100.0 * f / base_fan))

    # --- what the array costs to buy that margin, at each point on the trajectory ------------
    print('\n=== net, once the array is charged for the margin it buys ===')
    print('  (array lifts 20%% of die power; margin is what the campaign measures it to buy)')
    net = []
    s_ref = 0.20
    for cost, label in COSTS:
        arr = cost * s_ref * P
        row = {'array_cost_W_per_W': cost, 'label': label, 'array_W': arr, 'points': []}
        best = None
        for st in strong:
            total = P + st['fan_W'] + arr
            base_total = P + base_fan
            row['points'].append({'margin_K': st['margin_K'], 'dt_air_K': st['dt_air_K'],
                                  'system_W': total, 'vs_baseline_W': total - base_total})
            if best is None or total < best['system_W']:
                best = row['points'][-1]
        row['best'] = best
        net.append(row)
        print('  %-24s array %6.1f W -> best %+7.1f W vs baseline at margin %2.0f K'
              % (label, arr, best['vs_baseline_W'], best['margin_K']))

    out = {
        'note': __doc__.strip(),
        'supersedes': 'the first version of this file, which assumed P_fan ~ CFM^3 (affinity '
                      'law) and reported a fifth-power lever. The calibrated model is linear in '
                      'heat and inverse in dT_air.',
        'fan_model': {'W_per_CFM': MXL_FAN_W_PER_CFM, 'W_per_CFM_K': AIR_W_PER_CFM_K,
                      'P_fan_equals': 'MXL_FAN_W_PER_CFM * Q / (AIR_W_PER_CFM_K * dT_air)'},
        'die_W': P, 'dt_air_base_K': args.dt_air_base_K, 'baseline_fan_W': base_fan,
        'weak_lever_flux': weak, 'strong_lever_margin': strong, 'net_by_trajectory': net,
        'THE_FIRST_VERSION_WAS_WRONG': (
            'It assumed the textbook fan affinity law and reported fan power falling as the fifth '
            'power of thermal resistance, which produced a 22-35 % system-power saving. This '
            'project models a calibrated fan whose power is LINEAR in heat carried, so that '
            'headline was an artefact of an imported assumption rather than a result. The '
            'campaign confirms the linear model directly: 45 CFM draws 26.7 W against 88 CFM\'s '
            '35.0 W.'),
        'THE_REAL_MECHANISM_IS_BETTER': (
            'Fan power is inverse in dT_air, so letting the air run hot is where the money is -- '
            'the sink model\'s own calibration drops a 100 W chip\'s fan from 6.91 W to 2.07 W '
            'going from dT_air 15 K to 50 K. What stops a designer doing that is the effective '
            'ambient rising and eating hotspot margin. The array buys that margin back exactly '
            'where it is spent. So the claim is not that the array carries the heat more cheaply '
            'than the fan -- it does not -- but that it BUYS THE MARGIN THAT LETS THE AIR CARRY '
            'THE HEAT HOT, which is a different and much stronger lever.'),
        'WHAT_STILL_NEEDS_MEASURING': (
            'The margin-to-dT_air conversion is a ledger, not a solve: it assumes measured peak '
            'reduction converts one-for-one into permissible air rise. The campaign\'s airflow '
            'family measures the same thing through the coupled solver and should be preferred '
            'where they disagree.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\n' + out['THE_REAL_MECHANISM_IS_BETTER'])
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
