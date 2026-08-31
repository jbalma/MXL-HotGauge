#!/usr/bin/env python
"""Test 9: how much electricity comes back, on a die designed to run hot.

    python examples/recovery_at_temperature.py

Earlier recovery work asked whether the loop pays for itself on dies running at 310-370 K, and
answered no. That was the right answer to the wrong question. At those temperatures the Carnot
factor is 0.05-0.20, so the chip's heat carries almost no exergy and the loop is mostly recycling
its own pump light. The interesting regime is the one the architecture proposes and the toolchain
could not previously reach: logic held deliberately hot.

This reports, for a die of given power held at ``T_h``, the electrical power the loop exports --
or costs -- as a fraction of the die's own dissipation. Three things move it, and only one of
them is the extractor:

  * ``phi = 1 - T_0/T_h`` -- what fraction of the lifted heat is convertible at all;
  * ``eta_ASF`` -- how much heat is lifted per watt of pump light;
  * ``eta_P``, the laser wall-plug -- which enters as ``1/eta_P`` and is therefore the steepest
    term of the three near unity.

`[!]` What this is not
-----------------------
A second-law ledger on stated efficiencies, not a device simulation. The LPC is held at its
exergy ceiling times a stated internal factor, so the export figures are the best a perfect
converter could do at that temperature -- an upper bound by construction, and it should be quoted
as one. Nothing here models the extractor material's quenching behaviour at the temperature it is
being asked to work at, which is the assumption most likely to bite: the zone-matched extractor
families of v91 s8.4 exist precisely because no single material spans this range.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal import exergy as EX
from HotGauge.thermal.microrefrigeration import MRParams

PRESETS = (
    ('legacy   eta_ASF 0.20', {'eta_asf': 0.20, 'laser_wallplug': 0.70, 'lpc_efficiency': 0.90}),
    ('shipped  eta_ASF 0.32', {}),
    ('v91 tgt  eta_ASF 0.40', {'eta_asf': 0.40}),
    ('v91 tgt  + laser 0.90', {'eta_asf': 0.40, 'laser_wallplug': 0.90}),
)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--die-W', type=float, default=250.0)
    ap.add_argument('--fraction-lifted', type=float, default=0.30,
                    help='share of die power the array lifts; the rest leaves through the package')
    ap.add_argument('--T0-K', type=float, default=295.0)
    ap.add_argument('--temps-K', type=float, nargs='+',
                    default=[350, 400, 450, 500, 550, 600, 700, 800])
    ap.add_argument('--json-out', default=os.path.join(_EV, 'recovery_at_temperature.json'))
    args = ap.parse_args()

    P, T0, f = args.die_W, args.T0_K, args.fraction_lifted
    Q = f * P
    print('die %.0f W, array lifts %.0f%% of it (%.1f W), T_0 %.0f K' % (P, 100 * f, Q, T0))
    print('positive = net electrical COST; negative = net electrical EXPORT\n')
    print('%-24s' % 'preset' + ''.join('%9s' % ('%dK' % t) for t in args.temps_K))

    table, cross = [], []
    for label, kw in PRESETS:
        p = MRParams(313.15, **kw)
        row, line = [], '%-24s' % label
        for T in args.temps_K:
            cost_per_W = (1.0 - p.breakeven_ratio_at(T, T0)) / p.cop
            net_W = cost_per_W * Q
            row.append({'T_h_K': T, 'phi': EX.carnot_factor(T, T0),
                        'cost_per_W': cost_per_W, 'net_W': net_W,
                        'net_frac_of_die': net_W / P, 'exporting': net_W < 0})
            line += '%9s' % ('%+.1f' % net_W)
        print(line)
        T_sp = EX.self_powering_T_h(p.eta_asf, p.laser_wallplug, p.collection_efficiency, T0)
        table.append({'preset': label.strip(), 'eta_ASF': p.eta_asf,
                      'eta_P': p.laser_wallplug, 'eta_LPC': p.lpc_efficiency,
                      'rows': row, 'self_powering_T_h_K': T_sp})
        cross.append((label.strip(), T_sp))

    print('\n=== temperature at which each preset stops costing and starts exporting ===')
    for label, T in cross:
        print('   %-24s %s' % (label, ('%.0f K  (%.0f C)' % (T, T - 273.15)) if T else 'never'))

    best = table[-1]
    hot = [r for r in best['rows'] if r['exporting']]
    out = {
        'note': __doc__.strip(),
        'die_W': P, 'fraction_lifted': f, 'Q_lifted_W': Q, 'T0_K': T0,
        'presets': table,
        'self_powering_temperatures': {l: T for l, T in cross},
        'THE_REGIME_WAS_THE_PROBLEM': (
            'At 350 K the Carnot factor is {:.3f} and every preset costs power -- which is the '
            'result this project recorded and generalised too far. At 600 K phi is {:.3f}, and '
            'the v91 target preset with a 90 % laser has fallen to {:+.1f} W on a {:.0f} W lift. '
            'The loop was never going to look good on a die held near ambient; the question is '
            'what it does on a die designed to run hot.'
            .format(EX.carnot_factor(350.0, T0), EX.carnot_factor(600.0, T0),
                    [r for r in best['rows'] if r['T_h_K'] == 600][0]['net_W'], Q)),
        'WHAT_IT_TAKES_TO_EXPORT': (
            'The crossing is at {} for the v91 target preset with a 90 % laser. Above it the loop '
            'exports electricity while cooling: the chip becomes the hot reservoir of a heat '
            'engine that happens to also be its cooler. eta_P is the steep term -- it enters as '
            '1/eta_P -- so the laser and the optical path decide where this line sits, not the '
            'extractor.'
            .format(('%.0f K' % best['self_powering_T_h_K'])
                    if best['self_powering_T_h_K'] else 'no finite temperature')),
        'UPPER_BOUND_BY_CONSTRUCTION': (
            'The LPC is held at its exergy ceiling (v91 eq. 1.14) times a stated internal factor, '
            'so these are the best a perfect converter could do at each temperature. Quote them '
            'as bounds. The unmodelled assumption most likely to bite is extractor quenching at '
            'the working temperature -- which is exactly why v91 s8.4 specifies a different '
            'material family per thermal zone rather than one extractor across the die.'),
    }
    with open(args.json_out, 'w') as f_:
        json.dump(out, f_, indent=1)
    print('\n' + out['THE_REGIME_WAS_THE_PROBLEM'])
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
