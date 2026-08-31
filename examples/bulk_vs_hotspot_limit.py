#!/usr/bin/env python
"""Which limit is binding: the package moving bulk heat, or the array clipping the peak?

    python examples/bulk_vs_hotspot_limit.py

The density ladder produces two very different kinds of failure and they look identical in the
output -- both report "no steady state". Separating them decides whether a result is evidence
about the ARRAY or evidence about the PACKAGE, and the distinction is not subtle once stated:

    the array clips the peak; it does not move bulk heat off the die.

Every watt the array lifts still has to leave through the package, plus the array's own optical
load. So there is a density above which the die exceeds its junction limit on the DIE AVERAGE
alone, before any hotspot is considered. Above that line no array of any capability helps, and a
diverged run there says nothing about the array at all -- it says the package is wrong for that
density.

Below the line the die is hotspot-limited, and a diverged run IS about the array: its intensity
ceiling, its temperature lift, or its spatial reach.

Why this matters for reading the campaign
-----------------------------------------
On 88 CFM of air the bulk line sits at 2.22 W/mm^2 for the 34-core die. The campaign's diverged
points at 2.40 and above are therefore **package** results and must not be quoted as array
limits. The point at 2.00 is below the line -- bulk-only would sit at 92.7 C -- so its failure is
a genuine array-envelope result, and it is the one the dt_max and h_max sweeps were run to
explain.

The architecture conclusion follows directly, and it is stronger than the one it replaces: at
high density the answer is neither cooler alone. The package must take the bulk -- which liquid
does to 14 W/mm^2 and air does not past 2.2 -- and the array must take the peak, which no bulk
cooler can reach. That is a division of labour, not a competition.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')

COOLERS = (('air_88cfm', 0.325), ('cold_plate_liquid', 0.05), ('microchannel_direct_die', 0.0153))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--area-mm2', type=float, default=101.19)
    ap.add_argument('--ambient-K', type=float, default=300.0)
    ap.add_argument('--Tj-max-K', type=float, default=373.15)
    ap.add_argument('--densities', type=float, nargs='+',
                    default=[1.15, 1.60, 2.00, 2.40, 2.80, 3.20, 4.00, 6.00])
    ap.add_argument('--json-out', default=os.path.join(_EV, 'bulk_vs_hotspot_limit.json'))
    args = ap.parse_args()

    A, Ta, Tlim = args.area_mm2, args.ambient_K, args.Tj_max_K
    print('die %.2f mm^2, ambient %.0f K, junction limit %.2f K (%.0f C)\n'
          % (A, Ta, Tlim, Tlim - 273.15))
    print('%9s %9s' % ('density', 'P_die W')
          + ''.join('%14s' % n.split('_')[0] for n, _ in COOLERS))
    rows = []
    for D in args.densities:
        P = D * A
        line = '%9.2f %9.1f' % (D, P)
        rec = {'density_W_per_mm2': D, 'P_die_W': P, 'coolers': {}}
        for name, r in COOLERS:
            Tj = Ta + r * P
            over = Tj > Tlim
            rec['coolers'][name] = {'R_th': r, 'T_bulk_K': Tj, 'bulk_limited': bool(over)}
            line += '%12.1fK%s' % (Tj, '!' if over else ' ')
        rows.append(rec)
        print(line)

    print('\n! = over the junction limit on BULK ALONE. No array helps above this line.\n')
    limits = {}
    for name, r in COOLERS:
        d_lim = (Tlim - Ta) / r / A
        limits[name] = d_lim
        print('  %-26s bulk-limited above %.2f W/mm^2' % (name, d_lim))

    out = {
        'note': __doc__.strip(),
        'area_mm2': A, 'ambient_K': Ta, 'Tj_max_K': Tlim,
        'rows': rows, 'bulk_limit_density_W_per_mm2': limits,
        'HOW_TO_READ_A_DIVERGED_RUN': (
            'Above the bulk line a diverged array arm is a PACKAGE result and says nothing about '
            'the array. Below it, a diverged array arm is an ARRAY result -- intensity ceiling, '
            'temperature lift, or spatial reach. The campaign\'s 2.40+ points on air are above the '
            'line (2.22 W/mm^2) and must not be quoted as array limits; the 2.00 point is below '
            'it, bulk-only 92.7 C, and is a genuine envelope result.'),
        'THE_DIVISION_OF_LABOUR': (
            'At high density neither cooler suffices alone, and that is the architecture claim. '
            'The package must move the bulk -- a cold plate stays under the limit to '
            '{:.1f} W/mm^2 and direct-die microchannel to {:.1f}, where 88 CFM of air gives out '
            'at {:.2f}. The array must take the peak, which no bulk cooler can reach at all '
            'because its resistance is set by the whole die rather than by the hot block. Pairing '
            'them is not a compromise between two options; it is the only combination that '
            'addresses both terms.'
            .format(limits['cold_plate_liquid'], limits['microchannel_direct_die'],
                    limits['air_88cfm'])),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\n' + out['THE_DIVISION_OF_LABOUR'])
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
