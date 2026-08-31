#!/usr/bin/env python
"""Draw the Golden Cove / Redwood Cove core template from the pack's published numbers.

    python examples/plot_core_template.py --out docs/figures/core_template.png

Two cores on a common millimetre scale, every block at its published area, laid out in the
arrangement read off the annotated plate. Block labels carry the published mm^2 so the figure is
checkable against ``block_areas.csv`` by eye.

**This draws from the pack's NUMBERS, not its images.** 104 of the pack's plates are
SemiAnalysis paid-subscriber content and much of the rest is third-party work that is explicitly
not redistributable, so the plates are internal reference only and must not be embedded in
anything published. The published areas are facts about the parts and each cites its source, so
a figure our own code draws from them is a durable asset in a way the plates are not -- which is
the pack README's own argument.
"""
import os
import sys
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from HotGauge.thermal import core_templates as CT

#: One colour per functional class, so the two cores can be compared block by block.
CLASS_COLOUR = {
    'frontend': '#5B8FF9', 'ooo': '#5AD8A6', 'regfile': '#9270CA',
    'fpu': '#F6BD16', 'fma': '#E8684A', 'int': '#6DC8EC',
    'lsu': '#FF9D4D', 'l2_ctrl': '#B4B4B4', 'l2_array': '#D3D3D3',
    'uncore': '#6E6E6E',
}


#: Short labels, because the published block names do not fit inside the blocks they name.
SHORT = {
    'frontend_branch_decode_l1i_op': 'frontend\n(BP, decode,\nuop$, L1I)',
    'ooo_sched_and_retire': 'OoO sched\n+ retire',
    'load_store_with_l1d': 'load/store\n+ L1D',
    'fpu_excl_fma': 'FPU\n(less FMA)',
    'fpu_incl_fma_eus': 'FPU\n+ FMA EUs',
    'fma_eus_port_0_1': 'FMA EUs\nport 0 & 1',
    'integer_execution': 'int\nexec',
    'l2_control': 'L2 control\n+ tags',
    'l2_cache': 'L2',
    'fpu_register_file': 'FP RF',
    'int_register_file': 'INT RF',
    'uncore': 'uncore',
}


def draw(ax, template, title):
    g = template.geometry()
    cls = template.classes()
    w, h = template.outline_mm()
    for name, (x, y, bw, bh) in sorted(g.items(), key=lambda kv: -kv[1][2] * kv[1][3]):
        c = CLASS_COLOUR.get(cls[name], '#CCCCCC')
        ax.add_patch(Rectangle((x, y), bw, bh, facecolor=c, edgecolor='white', linewidth=0.8))
        area = template.blocks[name]
        # Label only what a reader can actually read; the rest is in the colour key.
        if bw * bh > 0.055 * template.total_mm2:
            ax.text(x + bw / 2, y + bh / 2, '{}\n{:.3f} mm$^2$'.format(SHORT.get(name, name),
                                                                       area),
                    ha='center', va='center', fontsize=6.5, color='black')
    ax.set_xlim(-0.05, w + 0.05)
    ax.set_ylim(-0.05, h + 0.05)
    ax.set_aspect('equal')
    ax.set_title('{}\n{} {:.3f} mm$^2$ published, {:.2f} x {:.2f} mm'
                 .format(title, template.node, template.total_mm2, w, h), fontsize=9)
    ax.set_xlabel('mm', fontsize=8)
    ax.tick_params(labelsize=7)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(_REPO, 'docs', 'figures',
                                                  'core_template.png'))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    gc, rw = CT.golden_cove(), CT.redwood_cove()
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
    draw(axes[0], gc, 'Intel Golden Cove P-core')
    draw(axes[1], rw, 'Intel Redwood Cove P-core')

    handles = [Rectangle((0, 0), 1, 1, facecolor=c, edgecolor='white')
               for c in CLASS_COLOUR.values()]
    fig.legend(handles, list(CLASS_COLOUR), loc='lower center', ncol=len(CLASS_COLOUR),
               fontsize=7, frameon=False, bbox_to_anchor=(0.5, -0.06))

    cons = CT.arrangement_consistency()
    resc = CT.rescale_error_vs_published()
    fig.suptitle('Published block areas, arrangement read off the annotated plate. '
                 'Areas exact; dimensions are an output.\n'
                 'Closure to the published core total: '
                 '$-$1.35% and $-$0.04%.   '
                 'Arrangement vs the plate\'s own pixels: worst block {:.0%}.   '
                 'Uniform rescale Golden$\\rightarrow$Redwood: {:.0%} worst block, {:.0%} mean.'
                 .format(cons['worst_abs_error'], resc['max_abs_error'], resc['mean_abs_error']),
                 fontsize=8.5, y=1.06)
    fig.tight_layout()
    fig.savefig(args.out, dpi=170, bbox_inches='tight')
    print('wrote {}'.format(args.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
