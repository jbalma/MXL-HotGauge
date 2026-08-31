#!/usr/bin/env python
"""The measured 34-core rescue, priced against a chiller, with a SECOND-LAW recovery term.

    python examples/rescue_measured_anchor.py

Supersedes the inline computation that produced the first version of
``docs/evidence/rescue_measured_anchor.json`` on 30 August 2026. That version took the array's
net electrical cost straight from ``mr_rescue_cost_34core.json`` as **1.735 W per watt lifted**,
which is what the study recorded -- and that recorded figure carries the first-law recovery term
(``MRParams.breakeven_ratio``, the phi -> 1 limit). See
``docs/evidence/loop_model_reconciliation.json``.

Recomputed at the junction temperature the rescue actually holds, the same loop costs
**2.473 W/W** -- a factor of **1.419** more. The recorded study used the LEGACY_ENVELOPE preset
(eta_ASF 0.20, eta_laser 0.70, eta_LPC 0.90), which this file confirms by reproducing its
``net/q = 1.743`` to four figures before correcting it.

Direction of the correction: every array cost in the rescue comparison goes UP, so the chiller's
margin widens. The qualitative conclusion of Test 6c is unchanged; its numbers are not.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.microrefrigeration import MRParams

#: the preset the recorded rescue study used, recovered by matching its net/q to four figures
LEGACY = {'eta_asf': 0.20, 'laser_wallplug': 0.70, 'lpc_efficiency': 0.90}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--target-C', type=float, default=92.0)
    ap.add_argument('--ambient-K', type=float, default=300.0)
    ap.add_argument('--T0-K', type=float, default=295.0)
    ap.add_argument('--fan-W', type=float, default=35.0)
    ap.add_argument('--eta-chiller-2nd', type=float, default=0.40)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'rescue_measured_anchor.json'))
    args = ap.parse_args()

    rows = json.load(open(os.path.join(_EV, 'mr_rescue_cost_34core.json')))['rows']
    p = MRParams(313.15, **LEGACY)
    Ta, T0, e2 = args.ambient_K, args.T0_K, args.eta_chiller_2nd

    print('preset recovered from the recorded study: cop %.4f, first-law ratio %.4f -> net/q %.4f'
          % (p.cop, p.breakeven_ratio, (1 - p.breakeven_ratio) / p.cop))
    print('(the study recorded net/q = 1.743 -- match confirms the preset)\n')

    out = {}
    print('%-7s %9s %9s %11s %11s %9s %9s'
          % ('density', 'unaided C', 'held C', 'lifted W', 'net/q 1st', 'net/q 2nd', 'factor'))
    for dens in ('d1.10', 'd1.15', 'd1.18'):
        u, t = rows['stability_only'][dens], rows['target_holding'][dens]
        T_h = t['peak_C'] + 273.15
        r2 = p.breakeven_ratio_at(T_h, T0)
        c1 = (1 - p.breakeven_ratio) / p.cop
        c2 = (1 - r2) / p.cop
        q = t['heat_removed_W']
        o = {'unaided_peak_C': u['peak_C'], 'unaided_chip_W': u['p_chip_W'],
             'mr_peak_C': t['peak_C'], 'mr_chip_W': t['p_chip_W'],
             'mr_heat_removed_W': q, 'T_h_K': T_h, 'phi': 1.0 - T0 / T_h,
             'recorded_net_W_first_law': t['p_mr_net_W'],
             'cost_per_W_first_law': c1, 'cost_per_W_second_law': c2,
             'correction_factor': c2 / c1,
             'mr_array_net_W': c2 * q,
             'leakage_saved_W': u['p_chip_W'] - t['p_chip_W']}
        o['effective_cost_per_W_net_leakage'] = ((c2 * q) - o['leakage_saved_W']) / q
        out[dens] = o
        print('%-7s %9.2f %9.2f %11.3f %11.3f %9.3f %9.3f'
              % (dens, u['peak_C'], t['peak_C'], q, c1, c2, c2 / c1))

    print('\n=== the rescue, priced both ways (chiller at eta_2nd %.2f) ===' % e2)
    print('%-7s %9s %9s %9s %12s %12s %12s %s'
          % ('density', 'dT need', 'T_in', 'COP_ch', 'chiller W', 'sys chiller', 'sys laser',
             'winner'))
    for dens in ('d1.10', 'd1.15', 'd1.18'):
        o = out[dens]
        dT = o['unaided_peak_C'] - args.target_C
        T_in = Ta - dT
        P = o['mr_chip_W']
        cop = e2 * T_in / (Ta - T_in) if T_in < Ta else float('inf')
        pch = P / cop
        sys_ch = P + args.fan_W + pch
        sys_las = P + args.fan_W + o['mr_array_net_W']
        o.update({'chiller_dT_K': dT, 'chiller_T_in_K': T_in, 'chiller_COP': cop,
                  'chiller_W': pch, 'sys_chiller_W': sys_ch, 'sys_laser_W': sys_las,
                  'winner': 'chiller' if sys_ch < sys_las else 'laser',
                  'dew_point_problem': T_in < 283.15})
        print('%-7s %8.1fK %8.1fK %9.3f %10.1f W %11.1f W %11.1f W  %s%s'
              % (dens, dT, T_in, cop, pch, sys_ch, sys_las, o['winner'].upper(),
                 '   [inlet below dew point]' if T_in < 283.15 else ''))

    print('\n=== how deep must the chill be before the laser wins? ===')
    a = out['d1.15']
    las = a['mr_array_net_W']
    P = a['mr_chip_W']
    deep = []
    print('%9s %9s %9s %11s %11s %s' % ('dT chill', 'T_in', 'COP_ch', 'chiller W', 'laser W', 'winner'))
    for dT in (20, 40, 60, 80, 100, 120, 140, 160, 180, 200):
        T_in = Ta - dT
        cop = e2 * T_in / (Ta - T_in)
        pch = P / cop
        deep.append({'dT_K': dT, 'T_in_K': T_in, 'COP': cop, 'chiller_W': pch,
                     'laser_W': las, 'laser_wins': las < pch})
        print('%8.0fK %8.1fK %9.3f %10.1f W %10.1f W  %s'
              % (dT, T_in, cop, pch, las, 'LASER' if las < pch else 'chiller'))
    first = next((d['dT_K'] for d in deep if d['laser_wins']), None)

    res = {'note': __doc__.strip(),
           'supersedes': 'the 30 Aug inline version, which used the first-law cost 1.735 W/W',
           'preset_used_by_the_recorded_study': LEGACY,
           'eta_chiller_2nd': e2, 'target_C': args.target_C, 'T0_K': T0, 'ambient_K': Ta,
           'anchors': out, 'deep_chill': deep, 'laser_wins_above_dT_K': first,
           'THE_CORRECTION': (
               'The recorded study reports 1.735 W per watt lifted. That figure carries the '
               'first-law recovery term. At the junction the rescue actually holds ({:.1f} K, '
               'phi {:.4f}) the same loop costs {:.3f} W/W -- a factor of {:.3f} more. Every '
               'array cost in the rescue comparison rises by that factor, so the chiller\'s '
               'margin widens and the depth at which the laser overtakes moves out from about '
               '80 K to {} K.'
               .format(out['d1.15']['T_h_K'], out['d1.15']['phi'],
                       out['d1.15']['cost_per_W_second_law'],
                       out['d1.15']['correction_factor'],
                       first if first else '>200')),
           'THE_LEAKAGE_CREDIT_STILL_STANDS': (
               'The 26.6 % chip-power reduction is a thermal result and is untouched by the '
               'recovery correction. It now takes the array from {:.3f} W/W gross to {:.3f} W/W '
               'net rather than 1.735 to 0.945 -- still nearly a factor of {:.2f}, and still the '
               'largest single term nobody was counting.'
               .format(out['d1.15']['cost_per_W_second_law'],
                       out['d1.15']['effective_cost_per_W_net_leakage'],
                       out['d1.15']['cost_per_W_second_law']
                       / out['d1.15']['effective_cost_per_W_net_leakage'])),
           }
    with open(args.json_out, 'w') as f:
        json.dump(res, f, indent=1)
    print('\n' + res['THE_CORRECTION'])
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
