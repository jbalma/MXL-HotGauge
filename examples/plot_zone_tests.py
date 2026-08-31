#!/usr/bin/env python
"""The two zone-test results, drawn: what a demanded gradient actually comes back as.

    python examples/plot_zone_tests.py

Left: Test 1. Heat removed over the cold zone against the gradient it actually buys, one line per
tile pitch, with the 150 K Section 10.8 asks for marked. The point of the panel is that the marker
is off the top of the chart by two orders of magnitude, and that the coarsest pitch is flat on the
floor -- two independent ways for the template to fail.

Right: Test 2. The junction-to-extractor drop against power density, and the error that reading
the Carnot factor off the junction introduces. The counter-intuitive part is that they do not
track: the drop grows without limit while the phi error PEAKS at 8.2% near 2 W/mm^2 and falls
away either side -- phi saturates at the top, and at the bottom phi is small enough that even a
1 K drop is a few percent of it.
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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(_REPO, 'docs', 'figures', 'zone_tests.png'))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    z, x = [], []
    for f in sorted(glob.glob(os.path.join(_REPO, 'results', 'zone_zones', '*', 'results.json'))):
        z += json.load(open(f))['rows']
    for f in sorted(glob.glob(os.path.join(_REPO, 'results', 'zone_extractor', '*',
                                           'results.json'))):
        x += json.load(open(f))['rows']
    if not z or not x:
        print('missing results'); return 1

    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.8))

    # --- Test 1 -----------------------------------------------------------------------------
    depth_style = {50.0: '-', 200.0: '--'}
    pitch_col = {100.0: '#1F6F43', 500.0: '#0F5C6E', 2000.0: '#8C2F52'}
    for depth in sorted({r['depth_um'] for r in z}):
        for pitch in sorted({r['pitch_um'] for r in z}):
            pts = sorted(((r['budget_W'], r['achieved_gradient_K']) for r in z
                          if r['depth_um'] == depth and r['pitch_um'] == pitch))
            if not pts:
                continue
            a.plot([p[0] for p in pts], [p[1] for p in pts],
                   depth_style.get(depth, ':'), color=pitch_col.get(pitch, '#666'),
                   marker='o', ms=3.5, lw=1.6,
                   label='{:.0f} um pitch, {:.0f} um die'.format(pitch, depth))
    a.axhline(150, color='#B03030', lw=1.4, ls=':')
    a.text(1.0, 150 * 1.25, 'what Section 10.8 asks for: 150 K', color='#B03030', fontsize=8.5)
    a.set_yscale('log')
    a.set_ylim(1e-3, 600)
    a.set_xlabel('heat removed over the cold zone  [W]   (die dissipates 60.7 W)')
    a.set_ylabel('achieved hot$-$cold gradient  [K]')
    a.set_title('Test 1: a monolithic die cannot hold the gradient\n'
                '40 W removed — two thirds of the die — buys 1.24 K', fontsize=9.5)
    a.legend(fontsize=6.5, loc='upper left', frameon=False, ncol=2)
    a.grid(alpha=0.25, which='both')

    # --- Test 2 -----------------------------------------------------------------------------
    sel = [r for r in x if r['depth_um'] == 200.0 and r['pitch_um'] == 2000.0]
    sel.sort(key=lambda r: r['density_W_mm2'])
    d = [r['density_W_mm2'] for r in sel]
    drop = [r['junction_minus_extractor_K'] for r in sel]
    over = [100 * (r['phi_at_junction'] / r['phi_at_extractor'] - 1.0) for r in sel]
    b.plot(d, drop, '-o', color='#0F5C6E', ms=4, lw=1.7, label='junction $-$ extractor  [K]')
    b.set_xscale('log'); b.set_yscale('log')
    b.set_xlabel('power density  [W/mm$^2$]')
    b.set_ylabel('temperature drop  [K]', color='#0F5C6E')
    b.tick_params(axis='y', labelcolor='#0F5C6E')
    b2 = b.twinx()
    b2.plot(d, over, '-s', color='#8A5A00', ms=4, lw=1.7,
            label='error in $\\phi$ from using the junction  [%]')
    b2.set_ylabel('$\\phi$ overstated by  [%]', color='#8A5A00')
    b2.tick_params(axis='y', labelcolor='#8A5A00')
    b2.set_ylim(0, 10)
    b.set_title('Test 2: the drop grows without limit, the $\\phi$ error peaks at 8.2%\n'
                '200 um burial, 2000 um pitch — the worst case in the sweep', fontsize=9.5)
    h1, l1 = b.get_legend_handles_labels(); h2, l2 = b2.get_legend_handles_labels()
    b.legend(h1 + h2, l1 + l2, fontsize=7.5, loc='upper left', frameon=False)
    b.grid(alpha=0.25, which='both')

    fig.suptitle('Two measurements the power-recovery framing needed, and neither went the '
                 'expected way.', fontsize=10, y=1.02)
    fig.tight_layout()
    fig.savefig(args.out, dpi=170, bbox_inches='tight')
    print('wrote {}'.format(args.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
