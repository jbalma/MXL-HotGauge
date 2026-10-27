#!/usr/bin/env python
"""§P0.42(b): where could a cold memory zone pay? -- the McPAT-only first sweep.

    bash spice_toolchain/tmp/mcpat_cache_surface.sh      # on the node
    python examples/mcpat_cache_surface_report.py        # -> docs/evidence/mcpat_cache_surface.json

One steady slice (8 cores, McPAT scope). Variants: the cell class per LEVEL ({L2, L3} x {HP, LSTP}),
the L3's capacity (1 / 2 / 4 / 8 x) in both classes, ``longer_channel_device`` off, McPAT's temperature
at 330 / 360 / 380 K. Per variant: L3 and L2 leakage [W], area [mm^2], LEAKAGE DENSITY [W/mm^2] -- the
quantity the two-sink ledger (§P0.37) needs: a cold zone pays when the leakage it sheds per mm^2
exceeds the laser's net draw per mm^2 of zone. This maps ONE die's inputs; it does not say what any
other architecture would find (user, 20 Sep: do not claim "no benefit" -- find where there is one).
"""
import os
import sys
import json
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
from mcpat_cache_device_report import parse          # noqa: E402

BASE = os.path.join(_REPO, 'results', 'mcpat_cache_surface')
N_L2 = 8
#: §P0.37, k = 0.025 W/mK, 3 K/W far-face sink, 1.00 W/mm^2: the laser's net draw to hold the
#: 30.1 mm^2 cache zone at 280 K, and the fraction of the zone's leakage that cooling sheds.
LASER_NET_W, ZONE_MM2, SHED = 7.0, 30.1, 1.0 - 1.0 / 3.5


def main():
    leak = lambda d: d.get('Subthreshold Leakage', 0.0) + d.get('Gate Leakage', 0.0)
    rows = {}
    for f in sorted(glob.glob(os.path.join(BASE, '*.txt'))):
        name = os.path.basename(f)[:-4]
        r = parse(f)
        if 'Total L3s' not in r or 'L2' not in r:
            rows[name] = {'failed': True}
            continue
        l3, l2, pr = r['Total L3s'], r['L2'], r['Processor']
        a3, a2 = l3.get('Area') or 0.0, l2.get('Area') or 0.0
        cache = leak(l3) + N_L2 * leak(l2)
        rows[name] = {'L3_leak_W': leak(l3), 'L3_area_mm2': a3, 'L3_leak_W_per_mm2': leak(l3) / a3 if a3 else None,
                      'L2_leak_W_each': leak(l2), 'L2_area_mm2_each': a2, 'L2_leak_W_per_mm2': leak(l2) / a2 if a2 else None,
                      'cache_leak_W': cache, 'processor_leak_W': leak(pr), 'cache_share': cache / leak(pr),
                      'L3_share_of_cache_leak': leak(l3) / cache if cache else None,
                      'L3_dynamic_W': l3.get('Runtime Dynamic')}
    print('%-22s %10s %9s %12s | %10s %9s %12s | %8s' % ('variant', 'L3 leak W', 'L3 mm2', 'L3 W/mm2', 'L2 leak W', 'L2 mm2', 'L2 W/mm2', 'share'))
    for n, v in rows.items():
        if v.get('failed'):
            print('%-22s FAILED' % n)
            continue
        print('%-22s %10.4f %9.3f %12.5f | %10.5f %9.3f %12.6f | %7.1f%%' % (
            n, v['L3_leak_W'], v['L3_area_mm2'], v['L3_leak_W_per_mm2'] or 0, v['L2_leak_W_each'], v['L2_area_mm2_each'],
            v['L2_leak_W_per_mm2'] or 0, 100 * v['cache_share']))
    be = LASER_NET_W / ZONE_MM2 / SHED
    print('\nbreak-even on the §P0.37 two-sink stack at its best isolation: the zone must carry >= %.3f W/mm^2 of leakage '
          '(floorplan scale) for cooling to 280 K to shed more than the laser draws' % be)
    sc = {}
    g = lambda n: rows.get(n) or {}
    base = g('class_L2dt0_L3dt0')
    caps = {cx: g('cap%dx_dt0' % cx) for cx in (2, 4, 8)}
    if base and all(v and not v.get('failed') for v in caps.values()):
        lin = {cx: caps[cx]['L3_leak_W'] / (cx * base['L3_leak_W']) for cx in caps}
        dens = {cx: caps[cx]['L3_leak_W_per_mm2'] / base['L3_leak_W_per_mm2'] for cx in caps}
        sc['P6_leakage_linear_in_capacity'] = {'measured': {'leak_over_linear': lin, 'density_vs_1x': dens},
                                               'verdict': 'confirmed' if all(abs(v - 1) <= 0.15 for v in lin.values()) else 'NOT as predicted'}
    t = {tk: g('T%d_dt0' % tk) for tk in (360, 380)}
    if base and t[380] and not t[380].get('failed'):
        ratio = {tk: t[tk]['cache_leak_W'] / base['cache_leak_W'] for tk in t if t[tk] and not t[tk].get('failed')}
        sc['P7_mcpat_temperature'] = {'measured': ratio, 'verdict': 'confirmed' if 2.5 <= ratio.get(380, 0) <= 4.0 else 'NOT as predicted'}
    if base:
        sc['P8_L3_is_most_of_the_prize'] = {'measured': {'L3_share_of_cache_leak': base['L3_share_of_cache_leak']},
                                            'verdict': 'confirmed' if 0.65 <= base['L3_share_of_cache_leak'] <= 0.85 else 'NOT as predicted'}
    print('\nscorecard (§P0.42 b):')
    for k, v in sc.items():
        print('  %-36s %s  %s' % (k, v['verdict'], json.dumps(v['measured'])[:200]))
    out = {'note': __doc__.strip(), 'break_even_leak_W_per_mm2_floorplan_scale': be,
           'break_even_inputs': {'laser_net_W': LASER_NET_W, 'zone_mm2': ZONE_MM2, 'shed_fraction': SHED, 'source': '§P0.37, k = 0.025, 3 K/W'},
           'rows': rows, 'scorecard': sc}
    p = os.path.join(_REPO, 'docs', 'evidence', 'mcpat_cache_surface.json')
    json.dump(out, open(p, 'w'), indent=1)
    print('written:', os.path.relpath(p, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
