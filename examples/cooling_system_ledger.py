#!/usr/bin/env python
"""§P0.30: the cooling-SYSTEM ledger -- what it costs, in electrical watts, to make an inoperable
die operable by each route, on the coupled solve.

    python examples/cooling_system_ledger.py

Inputs
------
* ``results/cop_ambient/air/d<rung>/T<ambient>``   the conventional air package (88 CFM, 35 W fan)
  with the ambient swept: the highest ambient at which the control arm HOLDS is "the ambient the
  package needs" at that rung.
* ``results/cop_ambient/liquid/d<rung>/C<inlet>``  the direct-die microchannel plate with the inlet
  swept: the highest inlet at which the control holds.
* the recorded rescue ladder (``results/array_coverage_armD/c1.00``): the laser's net electrical
  draw at the same rung, at 293 K ambient with the same 35 W fan.

Pricing (ported from mxl_LCEstimator_v8/thermal_model_unified.py and STATED, not fitted)
---------------------------------------------------------------------------------------
* chiller COP(T_in) = gamma * T_in / (T_amb - T_in), gamma = 0.4, clipped to [0.5, 6.0]
  (LCEstimator's calculate_chiller_cop_thermodynamic), with its sub-zero penalties: 3 % of COP per
  degree below 0 C down to -20 C, then exp((T_in + 20) / 15) below that (calculate_subzero_cop);
* refrigerated air: supply 5 K below the required ambient; the fan stays at 88 CFM (35 W); the
  refrigeration load is the die + fan heat (LCEstimator charges 1.5x the chip for air mass -- we
  charge the heat actually rejected into the air stream, and say so);
* liquid: chiller at the required inlet; pump at LCEstimator's single-pump 6.85 W scaled as
  flow^3 with flow held at the plate's design point (a flow sweep is a separate axis);
* photonic: the recorded p_mr_net_W (laser electrical minus LPC recovery, register §1.3) plus
  the 35 W fan; the die's own leakage saving is already inside the converged die power.

System COP = converged die power / (fan + pump + chiller + laser net). Every number is ARGUED on
the stated pricing; the temperatures the package needs are MEASURED on the coupled solve.
"""
import os
import re
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
T_AMB_K = 295.0
FAN_W = 34.984
PUMP_W = 6.85
GAMMA = 0.4
REF_MM2 = 101.09708


def chiller_cop(T_in_K, T_amb_K=T_AMB_K, gamma=GAMMA, lo=0.5, hi=6.0):
    """LCEstimator's thermodynamic chiller COP with its sub-zero penalties (stated in the docstring)."""
    T_in_C = T_in_K - 273.15
    if T_in_C >= 0:
        cop = gamma * T_in_K / max(T_amb_K - T_in_K, 1e-6)
        return float(min(max(cop, lo), hi))
    cop0 = min(max(gamma * 273.15 / (T_amb_K - 273.15), lo), hi)
    if T_in_C >= -20:
        cop = cop0 * (1.0 - 0.03 * abs(T_in_C))
    else:
        cop = cop0 * 0.4 * __import__('math').exp((T_in_C + 20.0) / 15.0)
    return float(min(max(cop, lo), hi))


def control_row(f):
    j = json.load(open(f))
    r = [x for x in j['rows'] if x['arm'] == 'control']
    return r[0] if r else None


def holds(r):
    return bool(r and not r.get('diverged') and not r.get('unconverged') and r.get('peak_C') is not None and r['peak_C'] <= 100.0)


def required_T(base, rung, kind):
    """Highest ambient (air) or inlet (liquid) at which the control holds, and the row."""
    out = []
    for d in sorted(glob.glob(os.path.join(base, kind, 'd%.2f' % rung, '*'))):
        m = re.search(r'/(T|C)(-?[0-9.]+)$', d)
        if not m or not os.path.isfile(os.path.join(d, 'mr_comparison.json')):
            continue
        T = float(m.group(2)) + (273.15 if m.group(1) == 'C' else 0.0)
        r = control_row(os.path.join(d, 'mr_comparison.json'))
        out.append((T, holds(r), r))
    out.sort(key=lambda x: -x[0])
    held = [x for x in out if x[1]]
    return (held[0] if held else None), out


def laser_row(rung):
    f = os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00', 'd%.2f' % rung, 'mr_comparison.json')
    if not os.path.isfile(f):
        return None
    j = json.load(open(f))
    r = [x for x in j['rows'] if x['arm'] == 'array_on']
    return r[0] if r else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'cop_ambient'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'cooling_system_ledger.json'))
    args = ap.parse_args()
    rows = []
    print('%5s | %-34s | %-34s | %-30s | %s' % ('rung', 'refrigerated air (88 CFM)', 'chilled liquid plate', 'photonic (recorded)', 'system COP air / liquid / photonic'))
    for rung in (1.20, 1.60, 2.00, 2.40):
        die_W = rung * REF_MM2
        air, air_all = required_T(args.base, rung, 'air')
        liq, liq_all = required_T(args.base, rung, 'liquid')
        las = laser_row(rung)
        rec = {'rung': rung, 'die_W_injected': die_W,
               'air': None, 'liquid': None, 'photonic': None,
               'air_sweep': [(T, h) for T, h, _ in air_all], 'liquid_sweep': [(T, h) for T, h, _ in liq_all]}
        if air:
            T, _, r = air
            T_supply = T - 5.0
            P_die = r['p_chip_W']
            cop = chiller_cop(T_supply)
            P_ref = (P_die + FAN_W) / cop if T < 293.0 else 0.0
            rec['air'] = {'required_ambient_K': T, 'supply_K': T_supply, 'p_chip_W': P_die, 'peak_C': r['peak_C'], 'fan_W': FAN_W,
                          'chiller_cop': cop if T < 293.0 else None, 'refrigeration_W': P_ref, 'total_W': FAN_W + P_ref,
                          'system_cop': P_die / (FAN_W + P_ref)}
        if liq:
            T, _, r = liq
            P_die = r['p_chip_W']
            cop = chiller_cop(T)
            P_ch = (P_die + PUMP_W) / cop if T < 293.0 else 0.0
            rec['liquid'] = {'required_inlet_K': T, 'p_chip_W': P_die, 'peak_C': r['peak_C'], 'pump_W': PUMP_W,
                             'chiller_cop': cop if T < 293.0 else None, 'chiller_W': P_ch, 'total_W': PUMP_W + P_ch,
                             'system_cop': P_die / (PUMP_W + P_ch)}
        if las and not las.get('diverged') and las.get('mr_plan_holds_target'):
            P_die = las['p_chip_W']
            rec['photonic'] = {'p_chip_W': P_die, 'peak_C': las['peak_C'], 'heat_removed_W': las['heat_removed_W'],
                               'laser_net_W': las['p_mr_net_W'], 'fan_W': FAN_W, 'total_W': FAN_W + las['p_mr_net_W'],
                               'system_cop': P_die / (FAN_W + las['p_mr_net_W'])}
        rows.append(rec)

        def fmt(x, kind):
            if not x:
                return 'no solution in range' if (air_all if kind == 'air' else liq_all) else '--'
            if kind == 'air':
                return 'ambient %.0f K, chiller %.0f W (COP %s), total %.0f W' % (x['required_ambient_K'], x['refrigeration_W'], '--' if x['chiller_cop'] is None else '%.2f' % x['chiller_cop'], x['total_W'])
            if kind == 'liquid':
                return 'inlet %.0f K, chiller %.0f W (COP %s), total %.0f W' % (x['required_inlet_K'], x['chiller_W'], '--' if x['chiller_cop'] is None else '%.2f' % x['chiller_cop'], x['total_W'])
            return '%.1f W net + fan = %.0f W' % (x['laser_net_W'], x['total_W'])
        cops = ' / '.join('%.2f' % rec[k]['system_cop'] if rec[k] else '--' for k in ('air', 'liquid', 'photonic'))
        print('%5.2f | %-34s | %-34s | %-30s | %s' % (rung, fmt(rec['air'], 'air'), fmt(rec['liquid'], 'liquid'), fmt(rec['photonic'], 'p'), cops))
    out = {'note': __doc__.strip(), 'pricing': {'T_amb_K': T_AMB_K, 'fan_W': FAN_W, 'pump_W': PUMP_W, 'gamma': GAMMA, 'cop_bounds': [0.5, 6.0]}, 'rows': rows,
           'complete': all(r['air_sweep'] and r['liquid_sweep'] for r in rows)}
    json.dump(out, open(args.json_out, 'w'), indent=1)
    print('written: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
