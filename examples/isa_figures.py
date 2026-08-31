#!/usr/bin/env python
"""Figures for the ISA floorplans: the geometry, and the thermal field it produces.

    python examples/isa_figures.py

Two panels per variant, deliberately side by side. The left is the FLOORPLAN -- what was designed
-- and the right is the SOLVED FIELD on the same footprint and the same scale. Putting them
adjacent is the point: the whole argument of the ISA work is that geometry sets the thermal
answer, so the reader should be able to see a block in one panel and find its temperature in the
other without re-orienting.

All four dies are drawn to a COMMON millimetre scale, so the compaction that the variants are
about is visible as size rather than having to be read off an axis. Temperatures share one colour
scale for the same reason.
"""
import os
import re
import sys
import json
import base64
import argparse

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))
sys.path.insert(0, _HERE)

from handbook_figures import read_flp, _cpu_color, CPU_CLASSES     # reuse the shipped conventions

plt.rcParams.update({
    'font.size': 9, 'axes.titlesize': 10, 'axes.labelsize': 9,
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'axes.edgecolor': '#555555', 'axes.linewidth': 0.8,
    'xtick.color': '#333333', 'ytick.color': '#333333',
})

# Ordered so the two built from PUBLISHED MICROARCHITECTURE sit next to the baseline, and the
# three built from press area ratios follow. The provenance differs and the figure should not
# flatten that.
VARIANTS = [
    ('x86_skylake',     'x86 Skylake-class\n(baseline)',       'outputs'),
    ('arm_a64fx',       'ARM A64FX-class\n(HPC, 512b SVE)',    'isa_outputs/arm_a64fx'),
    ('riscv_xiangshan', 'RISC-V XiangShan\n(server OoO)',      'isa_outputs/riscv_xiangshan'),
    ('arm_v1',          'ARM Neoverse V1-class',                'isa_outputs/arm_v1'),
    ('arm_n2',          'ARM Neoverse N2-class',                'isa_outputs/arm_n2'),
    ('riscv_p670',      'RISC-V P670-class',                    'isa_outputs/riscv_p670'),
]
STEM = 'skylake7nm_34core_3_3D-ICE.flp'


def _flp_path(sub):
    return os.path.join(_HERE, 'floorplans', sub, STEM)


def _field(variant):
    """Per-block temperatures [C] from the tier solve, or None if it has not landed."""
    p = os.path.join(_REPO, 'results', 'isa_fields', variant, 'tiers.json')
    if not os.path.isfile(p):
        return None
    d = json.load(open(p))
    return {b['block']: b['T_C'] for b in d.get('ranked', [])}


def fig_isa_floorplans(out_path):
    """Floorplan and solved field, side by side, four variants, common scale."""
    entries = []
    for key, label, sub in VARIANTS:
        path = _flp_path(sub)
        if not os.path.isfile(path):
            print('  missing floorplan: {}'.format(path))
            continue
        entries.append((key, label, read_flp(path), _field(key)))
    if not entries:
        raise SystemExit('no floorplans found')

    # One millimetre scale for every die, so compaction reads as size.
    span = max(max(b['x'] + b['w'] for b in blocks) for _, _, blocks, _ in entries) / 1000.0
    spanY = max(max(b['y'] + b['h'] for b in blocks) for _, _, blocks, _ in entries) / 1000.0

    have_fields = [f for _, _, _, f in entries if f]
    if have_fields:
        allT = [t for f in have_fields for t in f.values()]
        norm = Normalize(vmin=min(allT), vmax=max(allT))
    else:
        norm = None
    cmap = plt.get_cmap('inferno')

    n = len(entries)
    # Height follows the die aspect so the two rows sit close together; a fixed height leaves a
    # band of whitespace between them, because every panel is aspect-equal inside a common box.
    panel_w = 2.9
    panel_h = panel_w * spanY / span
    fig = plt.figure(figsize=(panel_w * n, 2 * panel_h + 2.1))
    # An explicit colourbar ROW, rather than stealing space from the panels: attaching it to the
    # axes list makes it float over the bottom row once bbox_inches='tight' re-crops.
    gs = fig.add_gridspec(3, n, height_ratios=[1, 1, 0.075], hspace=0.30, wspace=0.06,
                          top=0.88, bottom=0.10)
    axes = np.empty((2, n), dtype=object)
    for r in range(2):
        for c in range(n):
            axes[r, c] = fig.add_subplot(gs[r, c])
    cax = fig.add_subplot(gs[2, :])
    if n == 1:
        axes = axes.reshape(2, 1)

    for i, (key, label, blocks, field) in enumerate(entries):
        die_mm2 = sum(b['w'] * b['h'] for b in blocks) / 1e6

        ax = axes[0, i]
        for b in blocks:
            col, _ = _cpu_color(b['name'])
            ax.add_patch(Rectangle((b['x'] / 1000.0, b['y'] / 1000.0),
                                   b['w'] / 1000.0, b['h'] / 1000.0,
                                   facecolor=col, edgecolor='white', linewidth=0.12))
        ax.set_title('{}\n{:.0f} mm$^2$'.format(label, die_mm2), fontsize=9.5)
        ax.set_xlim(0, span); ax.set_ylim(0, spanY); ax.set_aspect('equal')
        ax.set_xticks([]); ax.set_yticks([])
        if i == 0:
            ax.set_ylabel('floorplan', fontsize=9.5)

        ax = axes[1, i]
        if field and norm is not None:
            for b in blocks:
                t = field.get(b['name'])
                col = cmap(norm(t)) if t is not None else '#DDDDDD'
                ax.add_patch(Rectangle((b['x'] / 1000.0, b['y'] / 1000.0),
                                       b['w'] / 1000.0, b['h'] / 1000.0,
                                       facecolor=col, edgecolor='none'))
            ts = [t for t in (field.get(b['name']) for b in blocks) if t is not None]
            ax.set_title('peak {:.1f} $\\degree$C    span {:.1f} K'.format(
                max(ts), max(ts) - min(ts)), fontsize=9)
        else:
            ax.text(0.5, 0.5, 'field not solved yet', transform=ax.transAxes,
                    ha='center', va='center', color='#888888', fontsize=9)
        ax.set_xlim(0, span); ax.set_ylim(0, spanY); ax.set_aspect('equal')
        ax.set_xticks([]); ax.set_yticks([])
        if i == 0:
            ax.set_ylabel('solved field\n(control arm, uniform activity)', fontsize=9)

    handles = [Rectangle((0, 0), 1, 1, facecolor=c) for _, c, _ in CPU_CLASSES]
    fig.legend(handles, [l for l, _, _ in CPU_CLASSES], loc='upper center',
               ncol=len(CPU_CLASSES), frameon=False, fontsize=8.2,
               bbox_to_anchor=(0.5, 1.005))
    if norm is not None:
        cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax,
                          orientation='horizontal')
        cb.set_label('block temperature [$\\degree$C], one scale across every die', fontsize=8.5)
    else:
        cax.axis('off')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('wrote {}'.format(out_path))
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(_REPO, 'docs', 'figures', 'isa_floorplans.png'))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig_isa_floorplans(args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
