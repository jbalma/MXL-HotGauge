#!/usr/bin/env python
"""Colour a die by recoverable exergy instead of temperature.

    python examples/exergy_map.py --out docs/figures/exergy_map.png

Every thermal figure in this project colours a die by temperature, which answers "where is the
problem". The power-recovery framing of ``docs/Photonic_Cooling_Devices___v9.pdf`` Chapter 1 asks a
different question -- "where is the *opportunity*" -- and it has a different answer, because the
recoverable work from a block is ``phi(T) * P``, which weights hot **and** dissipative together.
A hot block with no power is worthless; a warm block carrying watts is not.

No new solves: this reads the per-block temperature fields the tier screens already wrote
(``results/isa_fields/*/tiers.json``, 1126 blocks each) and the block powers from the floorplan.

`[!]` What this figure may NOT be used to claim
------------------------------------------------
``phi`` here is computed on **junction** temperatures, because those are what the fields contain.
The Carnot factor is properly set by the extractor's temperature, which is lower by the conduction
drop up through the die -- so every ``phi`` on this map is an **overstatement**, and by a margin
that grows with power density. ``examples/thermal_zone_probe.py --mode extractor`` measures the
drop; until it is folded in, this is a map of *where* the exergy is, not *how much* there is.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib import cm, colors

from HotGauge.thermal import exergy as EX
from HotGauge.utils import Floorplan


def load_field(tiers_json):
    with open(tiers_json) as f:
        d = json.load(f)
    temps = {r['block']: float(r['T_C']) + 273.15 for r in d['ranked']}
    return temps, d['floorplan'], d


def block_powers(flp_path, die_W):
    """Uniform density, matching how the tier screens were driven."""
    fp = Floorplan.from_file(flp_path, frmt='3D-ICE')
    geo = {e.name: (e.minx / 1000., e.miny / 1000., e.width / 1000., e.height / 1000.)
           for e in fp.elements}
    area = {n: g[2] * g[3] for n, g in geo.items()}
    tot = sum(area.values())
    return geo, {n: die_W * area[n] / tot for n in area}, tot


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fields', default=os.path.join(_REPO, 'results', 'isa_fields'))
    ap.add_argument('--variants', nargs='+', default=['x86_skylake', 'arm_v1'])
    ap.add_argument('--T0-K', type=float, default=EX.BOOK_T0_K)
    ap.add_argument('--out', default=os.path.join(_REPO, 'docs', 'figures', 'exergy_map.png'))
    ap.add_argument('--json-out', default=os.path.join(_REPO, 'docs', 'evidence',
                                                       'exergy_map.json'))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    panels, report = [], {}
    for v in args.variants:
        tj = os.path.join(args.fields, v, 'tiers.json')
        if not os.path.isfile(tj):
            print('skip {}: no field'.format(v))
            continue
        temps, flp, meta = load_field(tj)
        if not os.path.isfile(flp):
            print('skip {}: floorplan {} missing'.format(v, flp))
            continue
        geo, powers, area = block_powers(flp, meta.get('actual_power_W', meta['power_W']))
        m = EX.exergy_map(temps, powers, args.T0_K, temperature_is='junction')
        tw = EX.power_weighted_temperature(temps, powers)
        m['power_weighted_T_K'] = tw
        m['phi_at_power_weighted_T'] = EX.carnot_factor(tw, args.T0_K)
        m['collapse_error'] = m['phi_at_power_weighted_T'] / m['die_mean_phi'] - 1.0 \
            if m['die_mean_phi'] else None
        m['die_area_mm2'] = area
        report[v] = {k: m[k] for k in ('die_power_W', 'die_exergy_W', 'die_mean_phi', 'T_0_K',
                                       'power_weighted_T_K', 'phi_at_power_weighted_T',
                                       'collapse_error', 'die_area_mm2', 'temperature_is', 'note')}
        panels.append((v, geo, m))
        print('{:<16s} {:6.1f} W over {:5.1f} mm2 -> recoverable exergy {:6.2f} W '
              '(mean phi {:.4f}); one-temperature treatment would say {:.4f} ({:+.1%})'
              .format(v, m['die_power_W'], area, m['die_exergy_W'], m['die_mean_phi'],
                      m['phi_at_power_weighted_T'], m['collapse_error']))

    if not panels:
        print('no fields found'); return 1

    fig, axes = plt.subplots(1, len(panels), figsize=(6.2 * len(panels), 4.6), squeeze=False)
    vmax = max(max((d['exergy_W'] / max(1e-12, geo[b][2] * geo[b][3]))
                   for b, d in m['per_block'].items()) for _, geo, m in panels)
    norm = colors.Normalize(0.0, vmax)
    cmap = matplotlib.colormaps['inferno']
    for ax, (v, geo, m) in zip(axes[0], panels):
        for b, d in m['per_block'].items():
            x, y, w, h = geo[b]
            dens = d['exergy_W'] / max(1e-12, w * h)
            ax.add_patch(Rectangle((x, y), w, h, facecolor=cmap(norm(dens)), linewidth=0))
        W = max(g[0] + g[2] for g in geo.values()); H = max(g[1] + g[3] for g in geo.values())
        ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect('equal')
        ax.set_title('{}\n{:.1f} W dissipated, {:.2f} W recoverable  (mean $\\phi$ {:.3f})'
                     .format(v, m['die_power_W'], m['die_exergy_W'], m['die_mean_phi']),
                     fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), ax=axes[0].tolist(),
                 fraction=0.03, pad=0.02, label='recoverable exergy density  [W/mm$^2$]')
    fig.suptitle('Where the recoverable work is, not where the heat is.  '
                 '$\\phi = 1 - T_0/T_h$ at $T_0$ = {:.0f} K, weighted by local dissipation.\n'
                 'Computed on JUNCTION temperatures, so every value is an overstatement -- the '
                 'extractor the heat is lifted from runs cooler.'.format(args.T0_K),
                 fontsize=9, y=1.04)
    fig.savefig(args.out, dpi=170, bbox_inches='tight')
    print('\nwrote {}'.format(args.out))
    with open(args.json_out, 'w') as f:
        json.dump({'note': __doc__.strip(), 'variants': report}, f, indent=1)
    print('wrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
