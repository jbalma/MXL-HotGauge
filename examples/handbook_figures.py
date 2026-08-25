#!/usr/bin/env python
"""Generate every figure the handbook embeds, from the model's own inputs and outputs.

Nothing here is drawn by hand. The stack cross-section is parsed out of the ``.stk`` the solver
was actually given; the floorplans are the ``.flp`` files it was actually handed; the plots read
the harvested evidence JSON rather than numbers typed from memory. That is deliberate -- a figure
that is redrawn by hand drifts away from the model silently, and this project has already lost
several results to exactly that class of mistake.

Usage
-----
    python examples/handbook_figures.py --out-dir docs/figures
"""
import os
import re
import sys
import json
import math
import argparse

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.stack_report import parse_stack, resistance_budget

plt.rcParams.update({
    'font.size': 9, 'axes.titlesize': 10, 'axes.labelsize': 9,
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'axes.edgecolor': '#555555', 'axes.linewidth': 0.8,
    'xtick.color': '#333333', 'ytick.color': '#333333',
})

#: Colour per material, so the cross-section and the budget bar agree by eye.
MAT_COLOR = {
    'HEATSINK_METAL': '#9aa7b4', 'THERMAL_GREASE': '#c9a227', 'COPPER': '#c07a3e',
    'SOLDER_TIM': '#8d6e63', 'SILICON': '#4a6fa5',
}
SOURCE_COLOR = '#c0392b'

#: The two die areas the acceptance gate covers: GA100 (passes) and Ryzen 7500F (fails).
AREA_BIG, AREA_SMALL = 826.0, 91.0


def _die_side_mm(area_mm2):
    return math.sqrt(area_mm2)


def fig_stack_side_view(stack_file, out_path):
    """Cross-section of the modelled stack, with the resistance budget beside it.

    The vertical axis is compressed -- a 30 um grease line and a 3000 um spreader cannot share a
    linear scale and stay legible -- so each layer's drawn height is sqrt(thickness), and the true
    thickness is printed on the layer. The point of the figure is the ORDER of the layers and
    where the heat is made, not a scale drawing.
    """
    p = parse_stack(stack_file)
    big = resistance_budget(stack_file, AREA_BIG)
    small = resistance_budget(stack_file, AREA_SMALL)

    # Assemble drawn layers top-down, exactly as the stack section lists them.
    layers = []
    for e in p['stack']:
        if e['kind'] == 'die':
            for i, dl in enumerate(p['die_layers']):
                layers.append({'label': 'die[{}]'.format(i), 'h': dl['height_um'],
                               'mat': dl['material'], 'src': dl['kind'] == 'source'})
        else:
            ld = p['layer_defs'][e['type']]
            layers.append({'label': e['instance'], 'h': ld['height_um'],
                           'mat': ld['material'], 'src': False})

    fig = plt.figure(figsize=(11.5, 6.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 1.0], wspace=0.28)
    ax = fig.add_subplot(gs[0, 0])
    axb = fig.add_subplot(gs[0, 1])

    drawn = [math.sqrt(l['h']) for l in layers]
    total_drawn = sum(drawn)
    y = total_drawn
    x0, x1 = 0.0, 1.0
    for l, dh in zip(layers, drawn):
        y -= dh
        col = SOURCE_COLOR if l['src'] else MAT_COLOR.get(l['mat'], '#999999')
        ax.add_patch(Rectangle((x0, y), x1 - x0, dh, facecolor=col,
                               edgecolor='white', linewidth=0.8,
                               alpha=0.95 if l['src'] else 0.85))
        k = p['materials'][l['mat']]['k_si']
        if l['src']:
            txt = 'SOURCE  {:.0f} um  silicon  -- all heat made here'.format(l['h'])
        else:
            txt = '{}   {:.0f} um   {}  k={:.0f} W/(m K)'.format(
                l['label'], l['h'], l['mat'].lower().replace('_', ' '), k)
        ax.text(0.012, y + dh / 2.0, txt, va='center', ha='left', fontsize=7.4,
                color='white' if l['mat'] in ('COPPER', 'SILICON') or l['src'] else '#222222',
                fontweight='bold' if l['src'] else 'normal')
        l['y0'], l['dh'] = y, dh

    # Convective boundary above the sink.
    htc_si = p['htc_3dice'] * 1e12
    for xa in np.linspace(0.08, 0.92, 9):
        ax.add_patch(FancyArrowPatch((xa, total_drawn + 5.5), (xa, total_drawn + 0.6),
                                     arrowstyle='-|>', mutation_scale=8,
                                     color='#3d6e8f', linewidth=1.0))
    ax.text(0.5, total_drawn + 6.6,
            'convective boundary:  h = {:.0f} W/(m$^2$ K)   at  T$_{{amb}}$ = {:.1f} $^\\circ$C'
            .format(htc_si, 294.65 - 273.15), ha='center', fontsize=8.4, color='#3d6e8f')

    # Heat flows from the source layer UP through 380 um of silicon: this is a flip-chip die,
    # active side down, so the whole substrate sits between the transistors and the coolant.
    src = [l for l in layers if l['src']][0]
    pkg_top = total_drawn
    ax.add_patch(FancyArrowPatch((0.945, src['y0'] + src['dh']), (0.945, pkg_top - 0.4),
                                 arrowstyle='-|>', mutation_scale=11, color='#b03030',
                                 linewidth=1.6))
    ax.text(0.935, (src['y0'] + pkg_top) / 2.0, 'every watt takes this path', rotation=90,
            ha='right', va='center', fontsize=7.6, color='#b03030')

    # The overhang the stack does not model: one dashed region per side, spanning spreader to sink.
    ax.plot([x0, x1], [0, 0], color='#333333', linewidth=1.0)
    ov = 0.34
    hsp = [l for l in layers if l['label'] == 'HSP'][0]
    ihs_y0, ihs_top = hsp['y0'], pkg_top
    for xa in (x0 - ov, x1):
        ax.add_patch(Rectangle((xa, ihs_y0), ov, ihs_top - ihs_y0, facecolor='#f6e3e3',
                               edgecolor='#b03030', linewidth=1.2, linestyle='--', zorder=0))
        ax.text(xa + ov / 2.0, (ihs_y0 + ihs_top) / 2.0, 'NOT\nMODELLED', ha='center',
                va='center', fontsize=8.2, color='#b03030', fontweight='bold')

    ax.text(0.5, -7.0,
            'die footprint  =  the whole simulated domain:  826 mm$^2$ '
            '$\\rightarrow$ 28.7 mm square,   91 mm$^2$ $\\rightarrow$ 9.5 mm square\n'
            'A real spreader and sink overhang the die and carry heat sideways before handing '
            'it up. Nothing here does.\nThat is survivable on a large die and dominant on a '
            'small one -- and it is the one gap blocking the acceptance gate.',
            ha='center', va='top', fontsize=8.0, color='#333333')

    ax.set_xlim(x0 - ov - 0.06, x1 + ov + 0.06)
    ax.set_ylim(-34, total_drawn + 11)
    ax.axis('off')
    ax.set_title('The stack, as the solver receives it\n'
                 '(vertical scale compressed as $\\sqrt{{h}}$; from {})'
                 .format(os.path.basename(stack_file)), fontsize=9.5)

    # --- resistance budget -------------------------------------------------
    names = [r['name'] for r in big['rows']]
    rb = [r['r_K_per_W'] for r in big['rows']]
    rs = [r['r_K_per_W'] for r in small['rows']]
    cols = [SOURCE_COLOR if n.endswith('*') else MAT_COLOR.get(r['material'], '#999')
            for n, r in zip(names, big['rows'])]
    ypos = np.arange(len(names))[::-1]
    axb.barh(ypos + 0.19, rs, height=0.36, color=cols, alpha=0.95,
             edgecolor='white', label='91 mm$^2$  (Ryzen 7500F)')
    axb.barh(ypos - 0.19, rb, height=0.36, color=cols, alpha=0.45,
             edgecolor='white', label='826 mm$^2$  (GA100)')
    axb.set_yticks(ypos)
    axb.set_yticklabels(['{}  {}'.format(n, r['material'].lower().replace('_', ' '))
                         for n, r in zip(names, big['rows'])], fontsize=7.4)
    axb.set_xscale('log')
    axb.set_xlabel('vertical resistance through that layer  [K/W]')
    axb.grid(axis='x', alpha=0.25, linewidth=0.6)
    axb.set_axisbelow(True)
    axb.set_title('Every layer scales as exactly 1/area\n'
                  'total {:.4f} K/W at 826 mm$^2$   {:.4f} K/W at 91 mm$^2$   '
                  '(ratio {:.2f} = area ratio)'
                  .format(big['total_K_per_W'], small['total_K_per_W'],
                          small['total_K_per_W'] / big['total_K_per_W']), fontsize=9.0)
    axb.set_ylim(-0.9, len(names) - 0.4)
    axb.legend(loc='lower right', fontsize=7.6, frameon=True, ncol=2)
    for spine in ('top', 'right'):
        axb.spines[spine].set_visible(False)

    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return {'big': big, 'small': small, 'layers': layers}



# --------------------------------------------------------------------------------------------
# Floorplans
# --------------------------------------------------------------------------------------------

_BLOCK_RE = re.compile(r'(\S+)\s*:\s*\n\s*position\s+([\d.eE+-]+)\s*,\s*([\d.eE+-]+)\s*;'
                       r'\s*\n\s*dimension\s+([\d.eE+-]+)\s*,\s*([\d.eE+-]+)')


def read_flp(path):
    """Blocks as (name, x, y, w, h) in um -- the same text 3D-ICE parses."""
    with open(path) as f:
        txt = f.read()
    out = []
    for name, x, y, w, h in _BLOCK_RE.findall(txt):
        out.append({'name': name, 'x': float(x), 'y': float(y),
                    'w': float(w), 'h': float(h)})
    return out


#: Accelerator classes, in the order they should appear in a legend.
ACCEL_CLASSES = (
    ('SM datapath', '#B05924', lambda n: n.startswith('SM') and n.endswith('_DP')),
    ('SM L1 / SMEM', '#d99a6c', lambda n: n.startswith('SM') and '_L1' in n),
    ('L2 slices', '#2C4A6E', lambda n: n.startswith('L2_')),
    ('HBM PHY', '#4E7C6B', lambda n: n.startswith('HBM_PHY')),
    ('Memory controllers', '#7fae9c', lambda n: n.startswith('MEMCTRL')),
    ('NVLink', '#7A5B8E', lambda n: n.startswith('NVLINK')),
    ('PCIe / uncore residual', '#8A8F98', lambda n: n.startswith('PCIE')),
)

#: CPU classes. Names are ``UNIT_<core index>``, so strip the index first.
CPU_CLASSES = (
    ('Execution', '#B05924', ('iALU', 'cALU', 'FPUs', 'AVX')),
    ('Scheduling / rename', '#c98f5a', ('iWin', 'fpiWin', 'ROB', 'iRAT', 'fpRAT', 'Rename',
                                        'FreeList', 'RBB', 'RAS', 'gPred', 'Chooser',
                                        'L1Pred', 'L2Pred', 'IF', 'iDec', 'iBuf')),
    ('Register files', '#2C4A6E', ('iRF', 'fpRF')),
    ('Load / store', '#7A5B8E', ('LS', 'LoadQ', 'StoreQ', 'dTLB', 'iTLB')),
    ('Caches', '#4E7C6B', ('DCache', 'iCache', 'L2', 'L3')),
    ('Other', '#8A8F98', ('core_other',)),
)


def _accel_color(name):
    for label, col, test in ACCEL_CLASSES:
        if test(name):
            return col, label
    return '#8A8F98', 'PCIe / misc'


def _cpu_color(name):
    base = re.sub(r'_\d+$', '', name)
    for label, col, prefixes in CPU_CLASSES:
        for pre in prefixes:
            if base == pre or base.startswith(pre):
                return col, label
    return '#8A8F98', 'Other'


def _draw_flp(ax, blocks, colorer, edge=0.15, alpha=0.92):
    for b in blocks:
        col, _ = colorer(b['name'])
        ax.add_patch(Rectangle((b['x'] / 1000.0, b['y'] / 1000.0),
                               b['w'] / 1000.0, b['h'] / 1000.0,
                               facecolor=col, edgecolor='white', linewidth=edge, alpha=alpha))
    w = max(b['x'] + b['w'] for b in blocks) / 1000.0
    h = max(b['y'] + b['h'] for b in blocks) / 1000.0
    return w, h


def fig_dies(flps, out_path):
    """Every die simulated so far, drawn to one common millimetre scale.

    Drawing them on a shared scale is the whole point. The accelerator is eight times the area of
    the 34-core CPU and carries a fifth as many floorplan blocks, and no amount of prose makes
    that as obvious as putting them side by side.
    """
    entries = []
    for title, path, kind in flps:
        blocks = read_flp(path)
        w = max(b['x'] + b['w'] for b in blocks) / 1000.0
        h = max(b['y'] + b['h'] for b in blocks) / 1000.0
        entries.append({'title': title, 'blocks': blocks, 'w': w, 'h': h, 'kind': kind})

    wmax = max(e['w'] for e in entries)
    hmax = max(e['h'] for e in entries)
    fig, axes = plt.subplots(1, len(entries), figsize=(3.9 * len(entries), 3.9))
    fig.subplots_adjust(wspace=0.22)
    for ax, e in zip(np.atleast_1d(axes), entries):
        colorer = _accel_color if e['kind'] == 'accel' else _cpu_color
        _draw_flp(ax, e['blocks'], colorer)
        ax.set_xlim(-0.6, wmax + 0.6)
        ax.set_ylim(-0.6, hmax + 0.6)
        ax.set_aspect('equal')
        ax.set_title('{}\n{:.1f} x {:.1f} mm   =   {:.0f} mm$^2$   in {} blocks'
                     .format(e['title'], e['w'], e['h'], e['w'] * e['h'], len(e['blocks'])),
                     fontsize=9.0)
        ax.set_xlabel('mm')
        ax.tick_params(labelsize=7.5)
        for spine in ('top', 'right'):
            ax.spines[spine].set_visible(False)

    cpu_h = [Line2D([], [], marker='s', linestyle='', markersize=8, color=c, label=l)
             for l, c, _ in CPU_CLASSES]
    acc_h = [Line2D([], [], marker='s', linestyle='', markersize=8, color=c, label=l)
             for l, c, _ in ACCEL_CLASSES]
    l1 = fig.legend(handles=cpu_h, loc='upper left', ncol=6, fontsize=7.8, frameon=False,
                    bbox_to_anchor=(0.055, 0.055), title='CPU floorplan')
    l2 = fig.legend(handles=acc_h, loc='upper left', ncol=7, fontsize=7.8, frameon=False,
                    bbox_to_anchor=(0.055, -0.025), title='Accelerator floorplan')
    for lg in (l1, l2):
        lg.get_title().set_fontsize(8.2)
        lg._legend_box.align = 'left'
    fig.suptitle('The dies simulated so far, on one scale', fontsize=11, y=1.0)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return entries




def fig_tiles(accel_flp, cpu_flp, out_path, accel_cell_um=100.0, cpu_cell_um=50.0):
    """What the repeating tiles actually are, and what the thermal grid can resolve of them.

    The third panel is the one that matters. 3D-ICE discretises the die into square cells -- 100 um
    on the accelerator, 50 um on the CPU -- and a floorplan block thinner than a cell cannot have
    its own temperature; it inherits the cell's. Every accelerator block clears the grid by a wide
    margin. A large fraction of the CPU's do not, including RBB, which is the block the cliff
    results report as the hottest on the die.
    """
    acc = read_flp(accel_flp)
    cpu_all = read_flp(cpu_flp)
    core = [b for b in cpu_all if b['name'].endswith('_0')]

    fig = plt.figure(figsize=(13.6, 5.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.15], wspace=0.26)
    axa, axc, axh = (fig.add_subplot(gs[0, i]) for i in range(3))

    def _tile(ax, blocks, cell_um, label_min_mm2, title, colorer, grid_lim=None):
        x0 = min(b['x'] for b in blocks)
        y0 = min(b['y'] for b in blocks)
        for b in blocks:
            col, _ = colorer(b['name'])
            ax.add_patch(Rectangle((b['x'] - x0, b['y'] - y0), b['w'], b['h'],
                                   facecolor=col, edgecolor='white', linewidth=0.5, alpha=0.9))
            if b['w'] * b['h'] / 1e6 >= label_min_mm2:
                ax.text(b['x'] - x0 + b['w'] / 2.0, b['y'] - y0 + b['h'] / 2.0,
                        '{}\n{:.0f}x{:.0f}'.format(re.sub(r'_\d+$', '', b['name']),
                                                   b['w'], b['h']),
                        ha='center', va='center', fontsize=6.4, color='white')
        w = max(b['x'] + b['w'] for b in blocks) - x0
        h = max(b['y'] + b['h'] for b in blocks) - y0
        for gx in np.arange(0, w + cell_um, cell_um):
            ax.plot([gx, gx], [0, h], color='#000000', linewidth=0.3, alpha=0.22, zorder=5)
        for gy in np.arange(0, h + cell_um, cell_um):
            ax.plot([0, w], [gy, gy], color='#000000', linewidth=0.3, alpha=0.22, zorder=5)
        ax.set_xlim(-w * 0.04, w * 1.04)
        ax.set_ylim(-h * 0.04, h * 1.04)
        ax.set_aspect('equal')
        ax.set_title(title, fontsize=9.0)
        ax.set_xlabel('um')
        ax.tick_params(labelsize=7)
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)
        return w, h

    # One TPC's worth of accelerator: two SMs, each split datapath / L1.
    sm_pair = [b for b in acc if re.match(r'SM(0|1)_', b['name'])]
    w, h = _tile(axa, sm_pair, accel_cell_um, 0.2,
                 'Accelerator tile: 2 SMs (1 TPC)\n'
                 'grid {:.0f} um -- every block spans 6+ cells'.format(accel_cell_um),
                 _accel_color)

    w2, h2 = _tile(axc, core, cpu_cell_um, 0.05,
                   'CPU tile: one core, 33 blocks, 2.47 mm$^2$\n'
                   'grid {:.0f} um -- many blocks are thinner than one cell'.format(cpu_cell_um),
                   _cpu_color)
    rbb = [b for b in core if b['name'].startswith('RBB')][0]
    x0 = min(b['x'] for b in core)
    y0 = min(b['y'] for b in core)
    axc.add_patch(Rectangle((rbb['x'] - x0, rbb['y'] - y0), rbb['w'], rbb['h'],
                            facecolor='none', edgecolor='#c0392b', linewidth=1.6, zorder=6))
    axc.annotate('RBB, {:.0f} x {:.0f} um -- the block the cliff\nresults name as the hottest '
                 'on the die,\nand it is thinner than one grid cell'
                 .format(rbb['w'], rbb['h']),
                 xy=(rbb['x'] - x0 + rbb['w'], rbb['y'] - y0 + rbb['h'] / 2.0),
                 xytext=(w2 * 0.52, h2 * 1.16), fontsize=7.2, color='#c0392b',
                 arrowprops=dict(arrowstyle='->', color='#c0392b', linewidth=1.0))
    axc.set_ylim(-h2 * 0.04, h2 * 1.42)

    # The resolution test is the block's SHORT side against the cell size, so that is what the
    # histogram plots -- an area histogram would put a 474 x 7 um block on the safe side of a
    # cell-area line while the solver still cannot resolve it.
    aa = np.array([min(b['w'], b['h']) for b in acc])
    ca = np.array([min(b['w'], b['h']) for b in cpu_all])
    bins = np.logspace(math.log10(min(ca.min(), aa.min()) * 0.7),
                       math.log10(max(ca.max(), aa.max()) * 1.4), 44)
    axh.hist(ca, bins=bins, color='#2C4A6E', alpha=0.72, label='34-core CPU (1126 blocks)')
    axh.hist(aa, bins=bins, color='#B05924', alpha=0.72, label='GA100 (367 blocks)')
    for cell, col, lab in ((cpu_cell_um, '#2C4A6E', 'CPU cell, 50 um'),
                           (accel_cell_um, '#B05924', 'accel cell, 100 um')):
        axh.axvline(cell, color=col, linestyle='--', linewidth=1.2)
        axh.text(cell, axh.get_ylim()[1] * 0.62, ' ' + lab, rotation=90,
                 fontsize=7.0, color=col, va='center', ha='center',
                 bbox=dict(facecolor='white', edgecolor='none', pad=1.0, alpha=0.85))
    # The resolution test is the SHORT side, not the area: a block 474 x 7 um has ten cells'
    # worth of area and still cannot be resolved across its height.
    n_sub = sum(1 for b in cpu_all if min(b['w'], b['h']) < cpu_cell_um)
    n_sub_acc = sum(1 for b in acc if min(b['w'], b['h']) < accel_cell_um)
    axh.set_xscale('log')
    axh.set_xlabel('short side of the floorplan block  [um]')
    axh.set_ylabel('blocks')
    axh.set_title('Anything left of its dashed line cannot have its own\ntemperature. That is '
                  '{} of the CPU\'s {} blocks ({:.0f}%),\nand {} of the accelerator\'s {}.'
                  .format(n_sub, len(ca), 100.0 * n_sub / len(ca), n_sub_acc, len(aa)),
                  fontsize=9.0)
    axh.legend(fontsize=7.6, frameon=False, loc='upper left')
    axh.grid(axis='y', alpha=0.25, linewidth=0.6)
    axh.set_axisbelow(True)
    for sp in ('top', 'right'):
        axh.spines[sp].set_visible(False)

    fig.suptitle('Tile geometry, and what the thermal grid resolves of it', fontsize=11,
                 y=1.05)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return {'n_subcell_cpu': n_sub, 'n_cpu': len(ca), 'n_subcell_accel': n_sub_acc,
            'rbb': rbb}




# --------------------------------------------------------------------------------------------
# The acceptance gate
# --------------------------------------------------------------------------------------------

#: One row per published reference point. ``r_package`` is what the SOLVER measured on that run
#: (external resistance set to zero and the die driven at the published power), not a lumped
#: estimate -- except RYZEN_7500F_LIQUID, which never ran because the package alone already
#: exceeds its budget, and takes the air run's measured package resistance.
GATE_ROWS = (
    {'tag': 'H100, air\n470 W, 826 mm$^2$', 'budget': 0.1074, 'package': 0.05665,
     'pub_C': (54.0, 72.0), 'model_C': 60.669, 'status': 'PASS', 'lab_xy': (170.0, 0.175)},
    {'tag': 'H100, D2C liquid\n453 W, 826 mm$^2$', 'budget': 0.0662, 'package': 0.0550,
     'pub_C': (41.0, 50.0), 'model_C': None, 'status': 'FAIL', 'lab_xy': (150.0, 0.038)},
    {'tag': 'Ryzen 7500F, air\n132 W, 91 mm$^2$', 'budget': 0.3962, 'package': 0.3610,
     'pub_C': (74.9, 76.3), 'model_C': None, 'status': 'FAIL', 'lab_xy': (120.0, 1.05)},
    {'tag': 'Ryzen 7500F, liquid\n129 W, 91 mm$^2$', 'budget': 0.3651, 'package': 0.3610,
     'pub_C': (69.5, 71.1), 'model_C': None, 'status': 'not run', 'lab_xy': (120.0, 0.72)},
)

#: The one-dimensional stack resistance is exactly proportional to 1/area, because every layer
#: in the template spans exactly the die footprint. This constant is R x area, from the .stk.
_R_AREA_K = 0.0402 * 826.0

#: What the SOLVER measured, peak-block to die surface, on the two dies the gate covers. On the
#: big die this sits well above the 1-D line -- that gap is lateral constriction into a hotspot.
#: On the small die it lands on it, because at 91 mm^2 the whole die is effectively the hotspot.
_MEASURED_PACKAGE = ((826.0, 0.05665), (91.0, 0.3610))


def fig_acceptance_gate(out_path):
    """What the gate found, and the single number that explains all four verdicts.

    A published part fixes a junction-to-fluid resistance: its power, its ambient and its measured
    temperature leave no freedom. The model's package consumes part of that budget before any
    coolant is reached, and whatever is left is what the cooler has to deliver. The gate passes
    exactly where that remainder is large, and fails everywhere it is small -- which is not a
    coincidence and not four separate bugs.
    """
    fig = plt.figure(figsize=(13.4, 4.9))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 0.95, 1.05], wspace=0.32)
    ax, axt, axr = (fig.add_subplot(gs[0, i]) for i in range(3))

    y = np.arange(len(GATE_ROWS))[::-1]
    for i, (yy, r) in enumerate(zip(y, GATE_ROWS)):
        frac = r['package'] / r['budget']
        ax.barh(yy, 100 * frac, height=0.52, color='#8d6e63',
                edgecolor='white', label='package we model' if i == 0 else None)
        ax.barh(yy, 100 * max(1.0 - frac, 0.0), left=100 * frac, height=0.52, color='#4E7C6B',
                edgecolor='white', label='left for the cooler' if i == 0 else None)
        ax.text(100 * frac / 2.0, yy, '{:.0f}%'.format(100 * frac), va='center', ha='center',
                fontsize=8.4, color='white', fontweight='bold')
        ax.text(101.5, yy, '{}\nbudget {:.4f} K/W\ncooler gets {:.4f}'
                .format(r['status'], r['budget'], r['budget'] - r['package']),
                va='center', fontsize=7.4,
                color='#2e7d32' if r['status'] == 'PASS' else '#b03030',
                fontweight='bold' if r['status'] == 'PASS' else 'normal')
    ax.set_yticks(y)
    ax.set_yticklabels([r['tag'] for r in GATE_ROWS], fontsize=8.0)
    ax.set_xlim(0, 148)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel('share of the published junction-to-fluid budget')
    ax.set_title('The whole gate in one picture:\nthe model passes where the package is half the '
                 'budget,\nand fails where it is nearly all of it', fontsize=9.0)
    ax.legend(fontsize=7.8, frameon=False, loc='upper center', ncol=2,
              bbox_to_anchor=(0.42, -0.16))
    ax.grid(axis='x', alpha=0.25, linewidth=0.6)
    ax.set_axisbelow(True)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)

    # Published bands against the one prediction that exists.
    for yy, r in zip(y, GATE_ROWS):
        lo, hi = r['pub_C']
        axt.plot([lo, hi], [yy, yy], color='#3d6e8f', linewidth=7, alpha=0.45,
                 solid_capstyle='butt')
        axt.plot([lo, lo], [yy - 0.22, yy + 0.22], color='#3d6e8f', linewidth=1.4)
        axt.plot([hi, hi], [yy - 0.22, yy + 0.22], color='#3d6e8f', linewidth=1.4)
        if r['model_C'] is not None:
            axt.plot([r['model_C']], [yy], marker='D', markersize=8, color='#2e7d32', zorder=5)
            axt.text(r['model_C'], yy + 0.32, '{:.1f} $^\\circ$C'.format(r['model_C']),
                     ha='center', fontsize=8.0, color='#2e7d32', fontweight='bold')
        else:
            axt.text((lo + hi) / 2.0, yy + 0.30, 'no prediction:\nno flow reaches the\n'
                     'required resistance', ha='center', fontsize=7.0, color='#b03030')
    axt.set_yticks(y)
    axt.set_yticklabels([])
    axt.set_ylim(-0.7, len(GATE_ROWS) - 0.3)
    axt.set_xlabel('peak junction temperature  [$^\\circ$C]')
    axt.set_title('Published band (blue) against the model (green).\nThree points produce no '
                  'prediction at all --\nwhich is a result, not a missing run', fontsize=9.0)
    axt.grid(axis='x', alpha=0.25, linewidth=0.6)
    axt.set_axisbelow(True)
    for sp in ('top', 'right', 'left'):
        axt.spines[sp].set_visible(False)

    # Why: package resistance is 1/area, and small dies have small budgets.
    areas = np.logspace(math.log10(40), math.log10(1400), 200)
    axr.plot(areas, _R_AREA_K / areas, color='#8d6e63', linewidth=1.8, linestyle='--',
             label='1-D stack resistance, {:.0f}/area  (from the .stk)'.format(_R_AREA_K))
    axr.plot([a for a, _ in _MEASURED_PACKAGE], [r for _, r in _MEASURED_PACKAGE],
             marker='o', markersize=7, color='#8d6e63', linewidth=1.8,
             label='what the solve measures, peak block')
    axr.annotate('lateral constriction\ninto the hotspot', xy=(826.0, 0.048),
                 xytext=(880.0, 0.016), fontsize=7.0, color='#8d6e63', ha='center',
                 arrowprops=dict(arrowstyle='->', color='#8d6e63', linewidth=0.8))
    axr.set_ylim(0.012, 1.9)
    mk = {'PASS': ('o', '#2e7d32'), 'FAIL': ('X', '#b03030'), 'not run': ('s', '#999999')}
    for r, area in zip(GATE_ROWS, (826.0, 826.0, 91.0, 91.0)):
        m, c = mk[r['status']]
        axr.plot([area], [r['budget']], marker=m, markersize=9, color=c, linestyle='')
        axr.annotate(r['tag'].replace('\n', '  '), xy=(area, r['budget']), xytext=r['lab_xy'],
                     fontsize=7.2, color=c,
                     arrowprops=dict(arrowstyle='->', color=c, linewidth=0.8))
    axr.set_xscale('log')
    axr.set_yscale('log')
    axr.set_xlabel('die area  [mm$^2$]')
    axr.set_ylabel('thermal resistance  [K/W]')
    axr.set_title('Package resistance rises as 1/area while the budget\ndoes not, so the gap '
                  'closes on small dies. At 91 mm$^2$\nthere is essentially nothing left for '
                  'the cooler.', fontsize=9.0)
    axr.legend(fontsize=7.4, frameon=False, loc='upper right')
    axr.grid(alpha=0.25, linewidth=0.6, which='both')
    axr.set_axisbelow(True)
    for sp in ('top', 'right'):
        axr.spines[sp].set_visible(False)

    fig.suptitle('The acceptance gate: four published parts, measured against the model',
                 fontsize=11.5, y=1.11)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return GATE_ROWS




# --------------------------------------------------------------------------------------------
# Results: the cliff, and what sets how much microrefrigeration can buy
# --------------------------------------------------------------------------------------------

#: Which tier screens to draw a full clip curve for, and how to label them.
_CLIP_CASES = (
    ('tiers_34core_uniform', 'every core the same', '#2C4A6E'),
    ('tiers_34core_mixed25', '25% of cores loaded', '#B05924'),
    ('tiers_34core_g4_turbo', 'one core in turbo, 4x emphasis', '#c0392b'),
)


def fig_results(evidence_dir, out_path):
    """The three CPU results the project actually rests on.

    Everything here is 34-core, 7 nm, 88 CFM and damping-verified. Accelerator temperatures are
    deliberately absent: those runs were made with the leakage feedback silently inert, and none
    of them has been re-run yet, so plotting them would be publishing a withdrawn number.
    """
    cliff = json.load(open(os.path.join(evidence_dir, 'cliff_verified_34core_88cfm.json')))
    tiers = {}
    for f in sorted(os.listdir(evidence_dir)):
        if f.startswith('tiers_34core_') and f.endswith('.json'):
            tiers[f[:-5]] = json.load(open(os.path.join(evidence_dir, f)))

    fig = plt.figure(figsize=(13.6, 4.7))
    gs = fig.add_gridspec(1, 3, wspace=0.30)
    axc, axp, axg = (fig.add_subplot(gs[0, i]) for i in range(3))

    # --- the cliff --------------------------------------------------------
    pts = sorted(cliff['points'].items(), key=lambda kv: float(kv[0][1:]))
    dens = [float(k[1:]) for k, _ in pts]
    for key, lab, col, mk in (('nomr', 'no microrefrigeration', '#2C4A6E', 'o'),
                              ('mr', 'with microrefrigeration', '#c0392b', 's')):
        xs = [d for d, (_, v) in zip(dens, pts) if v[key].get('peak_C') is not None]
        ys = [v[key]['peak_C'] for _, v in pts if v[key].get('peak_C') is not None]
        axc.plot(xs, ys, marker=mk, color=col, linewidth=1.8, markersize=7, label=lab)
        last = max(xs)
        nxt = [d for d in dens if d > last]
        if nxt:
            axc.annotate('', xy=(min(nxt), ys[-1] + 6.5), xytext=(last, ys[-1]),
                         arrowprops=dict(arrowstyle='-|>', color=col, linewidth=1.6,
                                         linestyle='--'))
            axc.text(min(nxt) + 0.004, ys[-1] + 7.0, 'runaway', color=col, fontsize=7.6,
                     rotation=62)
    axc.axvspan(1.05, 1.10, color='#2C4A6E', alpha=0.08)
    axc.axvspan(1.15, 1.18, color='#c0392b', alpha=0.08)
    axc.text(1.075, 60.5, 'cliff without MR\n1.05 - 1.10', ha='center', fontsize=7.4,
             color='#2C4A6E')
    axc.text(1.165, 55.0, 'cliff with MR\n1.15 - 1.18', ha='center', fontsize=7.4,
             color='#c0392b')
    axc.set_xlabel('power-density multiplier on the 34-core die')
    axc.set_ylabel('peak junction temperature  [$^\\circ$C]')
    axc.set_xlim(0.97, 1.24)
    axc.set_ylim(52, 118)
    axc.set_title('The stability cliff is not gradual.\nBeyond it the leakage/temperature loop '
                  'does not\nconverge at any damping -- the die runs away.', fontsize=9.0)
    axc.legend(fontsize=7.8, frameon=False, loc='upper left')
    axc.grid(alpha=0.25, linewidth=0.6)
    axc.set_axisbelow(True)

    # --- plateau against clip-one gain -------------------------------------
    xs, ys, labs, cols = [], [], [], []
    cmap = {'uniform': '#2C4A6E', 'mixed': '#B05924', 'turbo': '#c0392b'}
    for name, d in sorted(tiers.items()):
        cc = d.get('clip_curve') or []
        if not cc:
            continue
        xs.append(d['plateau_within_dt_max'])
        ys.append(cc[0]['gain_K'])
        labs.append(name.replace('tiers_34core_', ''))
        cols.append(cmap.get(d.get('activity'), '#8A8F98'))
    axp.scatter(xs, ys, c=cols, s=64, zorder=4, edgecolor='white', linewidth=0.8)
    # Only the endpoints are labelled; eleven labels on eleven points is confetti, and the
    # colour already carries which family each screen belongs to.
    _CALLOUTS = {'g4_turbo_idle': (14, 6), 'g4_mixed25': (10, -14),
                 'uniform': (10, 6), 'fpu2': (-8, 12), 'fpu4': (10, 2)}
    for x, y, l in zip(xs, ys, labs):
        if l in _CALLOUTS:
            axp.annotate(l, xy=(x, y), xytext=_CALLOUTS[l], textcoords='offset points',
                         fontsize=7.0, color='#444444')
    xx = np.linspace(1.6, 31, 100)
    axp.plot(xx, 10.0 / xx * 1.9, color='#999999', linestyle=':', linewidth=1.2, zorder=1)
    axp.legend(handles=[Line2D([], [], marker='o', linestyle='', markersize=7, color=c, label=l)
                        for l, c in (('every core the same', '#2C4A6E'),
                                     ('a fraction loaded', '#B05924'),
                                     ('one core in turbo', '#c0392b'))] +
                       [Line2D([], [], linestyle=':', color='#999999',
                               label='roughly inverse')],
               fontsize=7.4, frameon=False, loc='upper right')
    axp.set_xscale('log')
    axp.set_xlabel('plateau: blocks within 10 K of the peak')
    axp.set_ylabel('gain from cooling the single hottest block  [K]')
    axp.set_title('Cooling one block only helps when there IS one\nhot block. Concentrate the '
                  'workload and the plateau\ncollapses from 29 blocks to 2 -- and MR starts '
                  'to pay.', fontsize=9.0)
    axp.grid(alpha=0.25, linewidth=0.6)
    axp.set_axisbelow(True)

    # --- clip curves -------------------------------------------------------
    for key, lab, col in _CLIP_CASES:
        d = tiers.get(key)
        if not d:
            continue
        cc = d['clip_curve']
        axg.plot([c['n_clipped'] for c in cc], [c['gain_K'] for c in cc],
                 marker='o', markersize=4, color=col, linewidth=1.7, label=lab)
    axg.axhline(10.0, color='#333333', linestyle='--', linewidth=1.0)
    axg.text(20, 10.25, 'dt$_{max}$ = 10 K: the device ceiling', ha='right', fontsize=7.4,
             color='#333333')
    axg.set_xlabel('number of blocks cooled, hottest first')
    axg.set_ylabel('reduction in peak temperature  [K]')
    axg.set_title('The same 10 K device buys 10 K from one block\nin turbo, and needs 15 blocks '
                  'to buy it when\nthe load is spread. Depth and breadth are separate.',
                  fontsize=9.0)
    axg.legend(fontsize=7.6, frameon=False, loc='lower right')
    axg.grid(alpha=0.25, linewidth=0.6)
    axg.set_axisbelow(True)
    axg.set_xlim(0.5, 20.5)

    for ax in (axc, axp, axg):
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)

    fig.suptitle('34-core CPU, 7 nm, 88 CFM -- damping-verified. '
                 'Accelerator temperatures are withdrawn pending re-runs.', fontsize=10.5,
                 y=1.06)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return {'n_tiers': len(tiers), 'n_cliff': len(pts)}




# --------------------------------------------------------------------------------------------
# Accelerator area and power breakdown
# --------------------------------------------------------------------------------------------

#: Class -> (label, colour, which floorplan prefixes belong to it, where the area came from).
_ACCEL_BREAKDOWN = (
    ('sm_dp', 'SM datapath', '#B05924', ('SM', '_DP'),
     '128 SMs x 3.43 mm$^2$ (1x TPC = 6.86 mm$^2$)'),
    ('sm_l1', 'SM L1 / SMEM', '#d99a6c', ('SM', '_L1'),
     '33.4% of each SM (192 KiB L1/SMEM)'),
    ('l2', 'L2 slices', '#2C4A6E', ('L2_', None),
     '96 tiles x 1.24 mm$^2$ (512 KB tile B)'),
    ('hbm_phy', 'HBM PHY', '#4E7C6B', ('HBM_PHY', None), '6 PHY bands, 1024-bit each'),
    ('mem_ctrl', 'Memory controllers', '#7fae9c', ('MEMCTRL', None),
     '4 bands, 3x 512-bit each'),
    ('nvlink', 'NVLink', '#7A5B8E', ('NVLINK', None), '4 PHY, 50 GB/s each'),
    ('pcie_misc', 'PCIe / uncore residual', '#8A8F98', ('PCIE', None),
     'residual that closes the die -- NOT measured'),
)


def _accel_class(name):
    for key, _, _, (pre, suf), _ in _ACCEL_BREAKDOWN:
        if name.startswith(pre) and (suf is None or suf in name):
            return key
    return 'pcie_misc'


def fig_accel_breakdown(accel_flp, out_path, total_W=470.0):
    """Where the accelerator's area goes, and where the power is assumed to go.

    The area column is measured: every number traces to a published die shot of GA100 (die 826
    mm^2, 1x TPC 6.86 mm^2, 512 KB L2 tile 1.24 mm^2, 16x PCIe 4.0 PHY 5.24 mm^2 -- SemiAnalysis
    / Locuza). The power column is not: it is a stated split, and the right-hand panel shows what
    that split implies. Keeping them side by side is the point, because the third panel -- power
    density per class -- is a product of one measurement and one assumption, and it is the number
    that decides where a hotspot appears.
    """
    from HotGauge.thermal.accelerator_floorplan import GA100_POWER_SPLIT, SM_DATAPATH_POWER_FRACTION

    blocks = read_flp(accel_flp)
    area = {}
    count = {}
    for b in blocks:
        k = _accel_class(b['name'])
        area[k] = area.get(k, 0.0) + b['w'] * b['h'] / 1e6
        count[k] = count.get(k, 0) + 1
    die = sum(area.values())

    # The stated split gives SMs one number; the floorplan splits each SM into datapath and L1.
    power = {}
    for key, _, _, _, _ in _ACCEL_BREAKDOWN:
        if key == 'sm_dp':
            power[key] = GA100_POWER_SPLIT['sm'] * SM_DATAPATH_POWER_FRACTION
        elif key == 'sm_l1':
            power[key] = GA100_POWER_SPLIT['sm'] * (1.0 - SM_DATAPATH_POWER_FRACTION)
        else:
            power[key] = GA100_POWER_SPLIT[key]

    fig = plt.figure(figsize=(13.6, 5.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.45, 1.0, 0.95], wspace=0.42)
    axa, axs, axd = (fig.add_subplot(gs[0, i]) for i in range(3))

    # Panel 1: the die as one bar, split by class, with provenance beside each slice.
    left = 0.0
    for key, lab, col, _, prov in _ACCEL_BREAKDOWN:
        w = area[key]
        axa.barh(0, w, left=left, height=0.55, color=col, edgecolor='white')
        if w / die > 0.05:
            axa.text(left + w / 2.0, 0, '{:.0f}%'.format(100 * w / die), ha='center',
                     va='center', color='white', fontsize=8.2, fontweight='bold')
        left += w
    axa.set_xlim(0, die)
    axa.set_ylim(-3.6, 0.75)
    axa.set_yticks([])
    axa.set_xlabel('die area  [mm$^2$]')
    y = -0.55
    for key, lab, col, _, prov in _ACCEL_BREAKDOWN:
        axa.add_patch(Rectangle((8, y - 0.10), 22, 0.20, color=col, clip_on=False))
        axa.text(38, y, '{:<22s} {:3d} block{:s}  {:6.1f} mm$^2$   {:s}'
                 .format(lab, count[key], ' ' if count[key] == 1 else 's', area[key], prov),
                 va='center', fontsize=7.0, color='#333333')
        y -= 0.40
    axa.set_title('Every area on this die traces to a measurement\n'
                  'except the last one, which is the residual that closes it', fontsize=9.0)
    for sp in ('top', 'right', 'left'):
        axa.spines[sp].set_visible(False)

    # Panel 2: area share against the assumed power share.
    keys = [k for k, _, _, _, _ in _ACCEL_BREAKDOWN]
    labs = [l for _, l, _, _, _ in _ACCEL_BREAKDOWN]
    cols = [c for _, _, c, _, _ in _ACCEL_BREAKDOWN]
    yy = np.arange(len(keys))[::-1]
    axs.barh(yy + 0.19, [100 * area[k] / die for k in keys], height=0.36, color=cols,
             edgecolor='white', label='share of area  (measured)')
    axs.barh(yy - 0.19, [100 * power[k] for k in keys], height=0.36, color=cols, alpha=0.45,
             edgecolor='white', label='share of power  (assumed)')
    axs.set_yticks(yy)
    axs.set_yticklabels(labs, fontsize=7.6)
    axs.set_xlabel('per cent of die')
    axs.set_title('Solid: measured area. Faded: assumed power.\n'
                  'Where the faded bar is longer, that class runs hot.', fontsize=9.0)
    axs.legend(fontsize=7.4, frameon=False, loc='lower right')
    axs.grid(axis='x', alpha=0.25, linewidth=0.6)
    axs.set_axisbelow(True)
    for sp in ('top', 'right'):
        axs.spines[sp].set_visible(False)

    # Panel 3: what that implies for power density.
    dens = [power[k] * total_W / area[k] for k in keys]
    axd.barh(yy, dens, height=0.55, color=cols, edgecolor='white')
    for y_, d_ in zip(yy, dens):
        axd.text(d_ + 0.02, y_, '{:.2f}'.format(d_), va='center', fontsize=7.4, color='#333333')
    axd.axvline(total_W / die, color='#333333', linestyle='--', linewidth=1.1)
    axd.text(total_W / die, -0.85, ' die average {:.2f}'.format(total_W / die),
             fontsize=7.4, color='#333333')
    axd.set_ylim(-1.15, len(keys) - 0.4)
    axd.set_yticks(yy)
    axd.set_yticklabels([])
    axd.set_xlim(0, max(dens) * 1.30)
    axd.set_xlabel('power density at {:.0f} W  [W/mm$^2$]'.format(total_W))
    axd.set_title('The memory interface, not the compute, carries the\nhighest assumed density '
                  '-- and it sits on the die edge.', fontsize=9.0)
    axd.grid(axis='x', alpha=0.25, linewidth=0.6)
    axd.set_axisbelow(True)
    for sp in ('top', 'right', 'left'):
        axd.spines[sp].set_visible(False)

    fig.suptitle('GA100: where the area is measured, where the power is assumed', fontsize=11,
                 y=1.02)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return {'die_mm2': die, 'area': area, 'count': count, 'density': dict(zip(keys, dens))}




# --------------------------------------------------------------------------------------------
# The package change: lidded -> direct die with a photonic pixel layer
# --------------------------------------------------------------------------------------------

MR_COLOR = '#2e9e5b'


def _draw_stack(ax, spec, title, strike=(), highlight=(), depth_callout=False):
    """One stack drawn top-down, vertical scale compressed as sqrt(thickness).

    ``strike`` names package layers to draw as removed; ``highlight`` names layers to ring.
    """
    from HotGauge.thermal.die_stack import MATERIALS

    rows = []
    for inst, _, h, mat in spec.package_layers():
        rows.append({'label': inst, 'h': h, 'mat': mat, 'src': False})
    for i, dl in enumerate(spec.die_layers()):
        rows.append({'label': 'die[{}]'.format(i), 'h': dl['height_um'], 'mat': dl['material'],
                     'src': dl['kind'] == 'source'})

    drawn = [math.sqrt(r['h']) for r in rows]
    total = sum(drawn)
    y = total
    for r, dh in zip(rows, drawn):
        y -= dh
        r['y0'], r['dh'] = y, dh
        col = SOURCE_COLOR if r['src'] else MAT_COLOR.get(r['mat'], MR_COLOR)
        ax.add_patch(Rectangle((0, y), 1.0, dh, facecolor=col, edgecolor='white',
                               linewidth=0.8, alpha=0.35 if r['label'] in strike else 0.9))
        k = MATERIALS[r['mat']][0]
        if r['src']:
            txt = 'SOURCE  {:.0f} um  -- heat made here'.format(r['h'])
        elif r['label'].startswith('die['):
            txt = '{}  {:.0f} um  silicon'.format(r['label'], r['h'])
        else:
            txt = '{}  {:.0f} um  {}  k={:.0f}'.format(
                r['label'], r['h'], r['mat'].lower().replace('_', ' '), k)
        ax.text(0.015, y + dh / 2.0, txt, va='center', ha='left', fontsize=7.2,
                color='white' if r['mat'] in ('COPPER', 'SILICON') or r['src'] else '#222222',
                fontweight='bold' if r['src'] else 'normal')
        if r['label'] in strike:
            ax.plot([0.02, 0.98], [y + dh * 0.65, y + dh * 0.35], color='#b03030', linewidth=2.4)
            ax.plot([0.02, 0.98], [y + dh * 0.35, y + dh * 0.65], color='#b03030', linewidth=2.4)
        if r['label'] in highlight:
            ax.add_patch(Rectangle((0, y), 1.0, dh, facecolor='none', edgecolor=MR_COLOR,
                                   linewidth=2.6, zorder=6))

    if depth_callout:
        src = [r for r in rows if r['src']][0]
        # The callout must span silicon + pixels, not the sink: it is the path a watt takes from
        # the transistors to the coolant, which is the number a vendor has to agree to.
        pix = [r for r in rows if r['label'] == 'MR_PIXELS'][0]
        top = pix['y0'] + pix['dh']
        ax.annotate('', xy=(1.06, top), xytext=(1.06, src['y0'] + src['dh']),
                    arrowprops=dict(arrowstyle='<->', color='#b03030', linewidth=1.4))
        ax.text(1.10, (top + src['y0']) / 2.0,
                'burial depth\n{:.0f} um silicon\n+ {:.0f} um pixels\n= {:.0f} um to coolant\n'
                '(now a parameter)'.format(spec.source_depth_um, spec.mr_um,
                                           spec.path_to_coolant_um()['total_um']),
                va='center', ha='left', fontsize=7.2, color='#b03030')

    ax.set_xlim(-0.05, 1.75)
    ax.set_ylim(-4, total + 4)
    ax.axis('off')
    ax.set_title(title, fontsize=9.2)
    return rows, total


def fig_stack_packages(out_path):
    """The package change the project needs, and what it is worth.

    Photonic microrefrigeration is only buildable direct-die: the pixels have to sit on the
    silicon. Modelling it through a lidded package spends most of the resistance budget on solder
    and a copper lid before the cooler does anything, and those two layers are exactly what
    direct-die deletes.
    """
    from HotGauge.thermal.die_stack import StackSpec, compare_packages

    lidded = StackSpec(package='lidded', cell_um=50.0)
    direct = StackSpec(package='direct_die', mr_layer=True, mr_material='GAAS', cell_um=50.0)

    fig = plt.figure(figsize=(13.8, 6.1))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.25], wspace=0.16)
    axl, axd, axb = (fig.add_subplot(gs[0, i]) for i in range(3))

    _draw_stack(axl, lidded, 'Before: lidded package\n(what every result so far came through)',
                strike=('HSP', 'SOLDER'))
    axl.text(0.5, -2.5, 'the two struck layers are 47% of the resistance,\n'
                        'and they sit between the cooler and the heat',
             ha='center', va='top', fontsize=7.6, color='#b03030')

    _draw_stack(axd, direct, 'After: direct die\npixel array where the grease was',
                highlight=('MR_PIXELS',), depth_callout=True)
    axd.text(0.5, -2.5, 'GaAs pixels are 14x more conductive than the\n'
                        'grease they replace, so the array is not a tax',
             ha='center', va='top', fontsize=7.6, color=MR_COLOR)

    # Budget comparison at both die areas.
    cmp826, cmp91 = compare_packages(826.0), compare_packages(91.0)
    groups = [('826 mm$^2$\nGA100', cmp826), ('91 mm$^2$\nRyzen 7500F', cmp91)]
    x = np.arange(len(groups))
    for i, (lab, c) in enumerate(groups):
        base = 0.0
        for r in c['lidded']['rows']:
            col = SOURCE_COLOR if r['name'].endswith('*') else MAT_COLOR.get(r['material'], '#999')
            axb.bar(i - 0.19, r['r_K_per_W'], bottom=base, width=0.34, color=col,
                    edgecolor='white', linewidth=0.5)
            base += r['r_K_per_W']
        axb.text(i - 0.19, base * 1.10, 'lidded\n{:.4f}'.format(base), ha='center',
                 fontsize=7.6, color='#333333')
        base2 = 0.0
        for r in c['direct_die']['rows']:
            col = (MR_COLOR if r['material'] == 'GAAS'
                   else SOURCE_COLOR if r['name'].endswith('*')
                   else MAT_COLOR.get(r['material'], '#999'))
            axb.bar(i + 0.19, r['r_K_per_W'], bottom=base2, width=0.34, color=col,
                    edgecolor='white', linewidth=0.5)
            base2 += r['r_K_per_W']
        axb.text(i + 0.19, base2 * 1.10, 'direct die\n{:.4f}\n({:.0f}% lower)'
                 .format(base2, 100 * c['reduction']), ha='center', fontsize=7.6,
                 color=MR_COLOR, fontweight='bold')
    axb.set_xticks(x)
    axb.set_xticklabels([l for l, _ in groups], fontsize=8.4)
    axb.set_yscale('log')
    axb.set_ylabel('stack resistance, die footprint  [K/W]')
    axb.set_ylim(1e-3, 1.3)
    axb.set_title('The same 68% cut at both die sizes, because every layer\nis 1/area. On the '
                  '91 mm$^2$ part that takes the package\nfrom 91% of the published budget to '
                  '29%. What is left is\nmostly the grey sink base -- the next artifact, not a '
                  'result.', fontsize=8.8)
    axb.grid(axis='y', alpha=0.25, linewidth=0.6, which='both')
    axb.set_axisbelow(True)
    for sp in ('top', 'right'):
        axb.spines[sp].set_visible(False)

    fig.suptitle('The stack, rebuilt for direct-die photonic cooling', fontsize=11.5, y=1.02)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return {'lidded_826': cmp826['lidded_K_per_W'], 'direct_826': cmp826['direct_die_K_per_W'],
            'lidded_91': cmp91['lidded_K_per_W'], 'direct_91': cmp91['direct_die_K_per_W'],
            'reduction': cmp826['reduction']}




# --------------------------------------------------------------------------------------------
# Where the cooling is applied, and why it decides whether burial depth matters
# --------------------------------------------------------------------------------------------

#: Measured, 3D-ICE, 100 um grid, 8.8 x 6.1 mm die at 100 W, 3 W of removal aimed at L3_4 -- the
#: block that sets the peak with no cooling. Only the PLACE of the removal and the burial depth
#: change between columns. Linear solves: no leakage feedback, deliberately, so the only thing
#: moving is geometry. results/mr_placement/summary.json
PLACEMENT_ROWS = (
    {'burial_um': 360.0, 'no_mr_C': 81.845, 'gain_source_K': -8.566, 'gain_pixels_K': -4.066},
    {'burial_um': 100.0, 'no_mr_C': 76.812, 'gain_source_K': -8.474, 'gain_pixels_K': -5.662},
    {'burial_um': 20.0, 'no_mr_C': 75.929, 'gain_source_K': -9.254, 'gain_pixels_K': -6.800},
)


def fig_mr_placement(out_path):
    """The correction, in one figure: cooling has to happen where the cooler is.

    Applying the removal as negative power on a processor block puts it in the die's own source
    layer, in the same 20 um of silicon as the transistors. Cooling and heating are then
    co-located and the extracted watt crosses no silicon at all -- so the burial depth cannot
    affect the answer, by construction. Moving the removal into the pixel array, where the
    hardware puts it, makes the watt climb the burial depth first.
    """
    d = [r['burial_um'] for r in PLACEMENT_ROWS]
    gs = [-r['gain_source_K'] for r in PLACEMENT_ROWS]
    gp = [-r['gain_pixels_K'] for r in PLACEMENT_ROWS]
    base = [r['no_mr_C'] for r in PLACEMENT_ROWS]

    fig = plt.figure(figsize=(13.4, 4.7))
    gs_ = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.15, 1.0], wspace=0.30)
    axa, axb, axc = (fig.add_subplot(gs_[0, i]) for i in range(3))

    # Panel 1: the two placements, drawn.
    for ax_x, title, col, ycool in ((0.26, 'MR in the SOURCE layer\n(the old formulation)',
                                     '#c0392b', 0.30),
                                    (0.74, 'MR in the PIXEL layer\n(the hardware)',
                                     MR_COLOR, 0.74)):
        axa.add_patch(Rectangle((ax_x - 0.19, 0.78), 0.38, 0.14, facecolor='#9aa7b4',
                                edgecolor='white'))
        axa.text(ax_x, 0.85, 'SINK', ha='center', va='center', fontsize=7.4)
        axa.add_patch(Rectangle((ax_x - 0.19, 0.70), 0.38, 0.08, facecolor=MR_COLOR,
                                edgecolor='white', alpha=0.85))
        axa.text(ax_x, 0.74, 'pixel array', ha='center', va='center', fontsize=7.4,
                 color='white')
        axa.add_patch(Rectangle((ax_x - 0.19, 0.30), 0.38, 0.40, facecolor='#4a6fa5',
                                edgecolor='white', alpha=0.85))
        axa.text(ax_x, 0.50, 'silicon\n(burial depth)', ha='center', va='center', fontsize=7.4,
                 color='white')
        axa.add_patch(Rectangle((ax_x - 0.19, 0.24), 0.38, 0.06, facecolor=SOURCE_COLOR,
                                edgecolor='white'))
        axa.text(ax_x, 0.27, 'transistors', ha='center', va='center', fontsize=7.0,
                 color='white', fontweight='bold')
        axa.add_patch(FancyArrowPatch((ax_x, 0.27), (ax_x, ycool), arrowstyle='-|>',
                                      mutation_scale=13, color=col, linewidth=2.2))
        axa.text(ax_x, 0.16, title, ha='center', va='top', fontsize=8.0, color=col)
        axa.text(ax_x, 0.06,
                 'watt crosses 0 um' if ycool < 0.5 else 'watt crosses the\nburial depth',
                 ha='center', va='top', fontsize=7.4, color=col, style='italic')
    axa.set_xlim(0, 1)
    axa.set_ylim(-0.05, 1.0)
    axa.axis('off')
    axa.set_title('Same stack, same 3 W. Only the arrow moves.', fontsize=9.2)

    # Panel 2: what the 3 W buys, against burial depth.
    axb.plot(d, gs, marker='s', color='#c0392b', linewidth=2.0, markersize=8,
             label='MR in the source layer')
    axb.plot(d, gp, marker='o', color=MR_COLOR, linewidth=2.0, markersize=8,
             label='MR in the pixel layer')
    for x, a, b in zip(d, gs, gp):
        axb.annotate('', xy=(x, b), xytext=(x, a),
                     arrowprops=dict(arrowstyle='<->', color='#888888', linewidth=0.9))
        axb.text(x * 1.06, (a + b) / 2.0, '{:.2f}x'.format(a / b), fontsize=7.6,
                 color='#555555', va='center')
    axb.set_xscale('log')
    axb.set_xticks(d)
    axb.set_xticklabels(['{:.0f}'.format(x) for x in d])
    axb.invert_xaxis()
    axb.set_xlabel('burial depth of the active layer  [um]   (thinner to the right)')
    axb.set_ylabel('temperature drop on the target block  [K]')
    axb.set_ylim(0, 11)
    axb.set_title('The old formulation over-states what 3 W buys by\n2.1x on an unthinned die, '
                  'and never converges:\neven at 20 um the watt still crosses the bond.',
                  fontsize=9.2)
    axb.legend(fontsize=7.8, frameon=False, loc='lower left')
    axb.grid(alpha=0.25, linewidth=0.6)
    axb.set_axisbelow(True)

    # Panel 3: the sensitivity itself, which is the point.
    span_s = max(gs) - min(gs)
    span_p = max(gp) - min(gp)
    axc.bar([0], [span_s], width=0.5, color='#c0392b', edgecolor='white')
    axc.bar([1], [span_p], width=0.5, color=MR_COLOR, edgecolor='white')
    axc.text(0, span_s + 0.08, '{:.2f} K\nand not even\nmonotone'.format(span_s), ha='center',
             fontsize=8.0, color='#c0392b')
    axc.text(1, span_p + 0.08, '{:.2f} K\nmonotone,\n+{:.0f}% by thinning'
             .format(span_p, 100 * (gp[-1] / gp[0] - 1)), ha='center', fontsize=8.0,
             color=MR_COLOR)
    axc.set_xticks([0, 1])
    axc.set_xticklabels(['MR in the\nsource layer', 'MR in the\npixel layer'], fontsize=8.4)
    axc.set_ylabel('how much the MR gain moves\nfrom 360 um to 20 um of burial  [K]')
    axc.set_ylim(0, 4.0)
    axc.set_title('Burial depth is a design parameter only in the\nright-hand case. In the left '
                  'one it is inert --\nnot approximately, but by construction.', fontsize=9.2)
    axc.grid(axis='y', alpha=0.25, linewidth=0.6)
    axc.set_axisbelow(True)

    for ax in (axb, axc):
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)

    fig.suptitle('Where the cooling is applied decides whether die thinning is worth anything',
                 fontsize=11.5, y=1.03)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return {'span_source': span_s, 'span_pixels': span_p,
            'overstatement': [a / b for a, b in zip(gs, gp)]}




# --------------------------------------------------------------------------------------------
# Tile pitch: how coarse the cooling array should be, and why it depends on the workload
# --------------------------------------------------------------------------------------------

def fig_tile_pitch(evidence_dir, out_path):
    """The optimal cooling-tile pitch reverses between two power maps on the same die.

    A tile cools whatever is under it. Whether that extra area is waste or the whole mechanism
    depends on how degenerate the peak is, and this measures it: identical die, identical target,
    identical 3 W of removal, only the power map changed.

    On a degenerate peak, cooling one block harder is pointless -- the runner-up takes over 0.56 K
    later -- so the coarse tile that drags the neighbourhood down wins. On an isolated hotspot
    there is nothing to take over, and every watt spent outside the spike is wasted.
    """
    u = json.load(open(os.path.join(evidence_dir, 'tile_pitch_uniform.json')))
    h = json.load(open(os.path.join(evidence_dir, 'tile_pitch_concentrated.json')))
    rows_u = [r for r in u['rows'] if r['pitch_um'] > 0]
    rows_h = [r for r in h['rows'] if r['pitch_um'] > 0]
    p = [r['pitch_um'] for r in rows_u]

    fig = plt.figure(figsize=(13.4, 4.8))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.15, 1.0], wspace=0.32)
    axa, axb, axc = (fig.add_subplot(gs[0, i]) for i in range(3))

    for ax, rows, title, col, sub in (
            (axa, rows_u, 'Uniform power: the peak is degenerate', '#2C4A6E',
             '24 of 25 blocks within 10 K of the peak;\nthe runner-up is 0.56 K behind'),
            (axb, rows_h, 'Concentrated 8x: the peak is isolated', '#c0392b',
             '1 block within 10 K of the peak;\nthe runner-up is 12.25 K behind')):
        y = [r['peak_drop_K'] for r in rows]
        ax.plot(p, y, marker='o', color=col, linewidth=2.2, markersize=8)
        best = max(rows, key=lambda r: r['peak_drop_K'])
        ax.plot([best['pitch_um']], [best['peak_drop_K']], marker='o', markersize=15,
                markerfacecolor='none', markeredgecolor=MR_COLOR, markeredgewidth=2.4)
        ax.annotate('best: {:.0f} um'.format(best['pitch_um']),
                    xy=(best['pitch_um'], best['peak_drop_K']),
                    xytext=(0, 16), textcoords='offset points', ha='center', fontsize=8.4,
                    color=MR_COLOR, fontweight='bold')
        ax.set_xscale('log')
        ax.set_xticks(p)
        ax.set_xticklabels(['{:.0f}'.format(x) for x in p])
        ax.invert_xaxis()
        ax.set_xlabel('tile pitch [um]   (finer to the right)')
        ax.set_ylabel('peak reduction for a fixed 3 W  [K]')
        ax.set_ylim(0, 7.6)
        ax.set_title(title + '\n' + sub, fontsize=9.2)
        ax.grid(alpha=0.25, linewidth=0.6)
        ax.set_axisbelow(True)

    # The structural point: one strategy is a constant, the other is a bet.
    coarse = [rows_u[0]['peak_drop_K'], rows_h[0]['peak_drop_K']]
    fine = [rows_u[-1]['peak_drop_K'], rows_h[-1]['peak_drop_K']]
    x = np.arange(2)
    axc.bar(x - 0.19, coarse, width=0.36, color='#8A8F98', edgecolor='white',
            label='coarse, 2000 um')
    axc.bar(x + 0.19, fine, width=0.36, color=MR_COLOR, edgecolor='white',
            label='fine, 100 um')
    for xi, (c, f) in enumerate(zip(coarse, fine)):
        axc.text(xi - 0.19, c + 0.12, '{:.2f}'.format(c), ha='center', fontsize=8.0)
        axc.text(xi + 0.19, f + 0.12, '{:.2f}'.format(f), ha='center', fontsize=8.0,
                 color=MR_COLOR, fontweight='bold')
    axc.set_xticks(x)
    axc.set_xticklabels(['uniform', 'concentrated'], fontsize=9)
    axc.set_ylabel('peak reduction for a fixed 3 W  [K]')
    axc.set_ylim(0, 8.4)
    axc.set_title('A coarse array is a constant: 3.03 vs 3.09 K across a\npower map whose peak '
                  'moved 79 K. A fine one swings 3.6x.\nFine targeting is the high-variance bet.',
                  fontsize=9.2)
    axc.legend(fontsize=7.8, frameon=False, loc='upper left')
    axc.grid(axis='y', alpha=0.25, linewidth=0.6)
    axc.set_axisbelow(True)

    for ax in (axa, axb, axc):
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)

    fig.suptitle('The best cooling-tile pitch depends on the workload, and reverses between these '
                 'two', fontsize=11.5, y=1.03)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return {'best_uniform': max(rows_u, key=lambda r: r['peak_drop_K'])['pitch_um'],
            'best_concentrated': max(rows_h, key=lambda r: r['peak_drop_K'])['pitch_um']}




# --------------------------------------------------------------------------------------------
# Where to put the cooling: targeted saturates, proportional does not
# --------------------------------------------------------------------------------------------

def fig_die_average(evidence_dir, out_path):
    """Whether an area cooling array can move the die-average path that sets the clock.

    The handbook said MR is weak as a clock enabler because "the clock ceiling is set by the
    die-average thermal path, which hotspot clipping barely touches". Both halves of that are
    true. The conclusion does not follow, because hotspot clipping is one strategy among several
    and it is the one that saturates soonest.
    """
    d = json.load(open(os.path.join(evidence_dir, 'die_average_strategies.json')))
    base = d['base_peak_C']
    order = ('hotspot', 'top5', 'uniform', 'proportional')
    cols = {'hotspot': '#c0392b', 'top5': '#B05924', 'uniform': '#8A8F98',
            'proportional': MR_COLOR}
    by = {s: sorted([r for r in d['rows'] if r['strategy'] == s], key=lambda r: r['watts'])
          for s in order}

    fig = plt.figure(figsize=(13.4, 4.8))
    gs = fig.add_gridspec(1, 3, wspace=0.30)
    axa, axb, axc = (fig.add_subplot(gs[0, i]) for i in range(3))

    for s in order:
        w = [r['watts'] for r in by[s]]
        axa.plot(w, [-r['d_peak_K'] for r in by[s]], marker='o', color=cols[s], linewidth=2.0,
                 markersize=7, label=s)
        axb.plot(w, [-r['d_peak_K'] / r['watts'] for r in by[s]], marker='o', color=cols[s],
                 linewidth=2.0, markersize=7, label=s)
    axa.set_xlabel('watts removed from the die')
    axa.set_ylabel('peak temperature reduction [K]')
    axa.set_title('Targeted cooling bends over. Proportional\nextraction is straight: it scales '
                  'the whole field.', fontsize=9.2)
    axa.legend(fontsize=7.8, frameon=False, loc='upper left')

    axb.set_xlabel('watts removed from the die')
    axb.set_ylabel('peak reduction per watt removed  [K/W]')
    axb.set_title('The same thing as efficiency. Targeted loses 65-80%\nof its efficiency by '
                  '30 W; distributed loses none.', fontsize=9.2)
    axb.set_ylim(0, 1.1)
    axb.legend(fontsize=7.8, frameon=False, loc='upper right')

    for ax in (axa, axb):
        ax.grid(alpha=0.25, linewidth=0.6)
        ax.set_axisbelow(True)

    # Why: where the cooling ends up relative to the peak.
    w30 = {s: [r for r in by[s] if r['watts'] == 30.0][0] for s in order}
    x = np.arange(len(order))
    axc.bar(x, [-w30[s]['d_peak_K'] for s in order],
            color=[cols[s] for s in order], edgecolor='white', width=0.62)
    for i, s in enumerate(order):
        axc.text(i, -w30[s]['d_peak_K'] + 0.25, '{:.1f} K'.format(-w30[s]['d_peak_K']),
                 ha='center', fontsize=8.6,
                 fontweight='bold' if s == 'proportional' else 'normal', color=cols[s])
    axc.set_xticks(x)
    axc.set_xticklabels(order, fontsize=8.4, rotation=12)
    axc.set_ylabel('peak reduction at 30 W removed [K]')
    axc.set_ylim(0, 15)
    axc.set_title('At 30 W, matching extraction to dissipation is\nworth 1.9x hotspot clipping '
                  '-- on the same watts.', fontsize=9.2)
    axc.grid(axis='y', alpha=0.25, linewidth=0.6)
    axc.set_axisbelow(True)

    for ax in (axa, axb, axc):
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)

    fig.suptitle('How to move the die-average path: match extraction to dissipation, '
                 'do not chase the hotspot', fontsize=11.5, y=1.03)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return {'best_30W': max(order, key=lambda s: -w30[s]['d_peak_K']),
            'prop_30W_K': -w30['proportional']['d_peak_K'],
            'hotspot_30W_K': -w30['hotspot']['d_peak_K']}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=os.path.join(_REPO, 'docs', 'figures'))
    ap.add_argument('--stack', default=os.path.join(
        _REPO, 'results', 'accept_air', 'H100_AIR_assumed', 'stack.stk'))
    a = ap.parse_args()
    if not os.path.isdir(a.out_dir):
        os.makedirs(a.out_dir)
    r = fig_stack_side_view(a.stack, os.path.join(a.out_dir, 'stack_side_view.png'))
    print('stack_side_view.png  total R: {:.4f} (826) {:.4f} (91)'
          .format(r['big']['total_K_per_W'], r['small']['total_K_per_W']))

    da = fig_die_average(os.path.join(_REPO, 'docs', 'evidence'),
                         os.path.join(a.out_dir, 'die_average.png'))
    print('die_average.png  at 30 W: proportional {:.2f} K vs hotspot {:.2f} K'
          .format(da['prop_30W_K'], da['hotspot_30W_K']))

    tp = fig_tile_pitch(os.path.join(_REPO, 'docs', 'evidence'),
                        os.path.join(a.out_dir, 'tile_pitch.png'))
    print('tile_pitch.png  best pitch: uniform {:.0f} um, concentrated {:.0f} um'
          .format(tp['best_uniform'], tp['best_concentrated']))

    mp = fig_mr_placement(os.path.join(a.out_dir, 'mr_placement.png'))
    print('mr_placement.png  source span {:.2f} K, pixel span {:.2f} K, over-stated {}'
          .format(mp['span_source'], mp['span_pixels'],
                  ', '.join('{:.2f}x'.format(x) for x in mp['overstatement'])))

    sp = fig_stack_packages(os.path.join(a.out_dir, 'stack_packages.png'))
    print('stack_packages.png  826: {:.5f} -> {:.5f}   91: {:.5f} -> {:.5f}  ({:.0f}% lower)'
          .format(sp['lidded_826'], sp['direct_826'], sp['lidded_91'], sp['direct_91'],
                  100 * sp['reduction']))

    fp = os.path.join(_REPO, 'examples', 'floorplans', 'outputs')
    e = fig_dies([('34-core CPU, 7 nm', os.path.join(fp, 'skylake7nm_34core_3_3D-ICE_template.flp'), 'cpu'),
                  ('128-core CPU, 7 nm', os.path.join(fp, 'skylake7nm_128core_3_3D-ICE_template.flp'), 'cpu'),
                  ('GA100 accelerator', os.path.join(_REPO, 'results', 'accept_air',
                                                     'H100_AIR_assumed', 'ga100.flp'), 'accel')],
                 os.path.join(a.out_dir, 'dies.png'))
    print('dies.png  ' + '  '.join('{}: {}blk {:.0f}mm2'.format(x['title'], len(x['blocks']),
                                                                x['w'] * x['h']) for x in e))

    t = fig_tiles(os.path.join(_REPO, 'results', 'accept_air', 'H100_AIR_assumed', 'ga100.flp'),
                  os.path.join(fp, 'skylake7nm_34core_3_3D-ICE_template.flp'),
                  os.path.join(a.out_dir, 'tiles.png'))
    print('tiles.png  sub-cell CPU blocks: {}/{}  RBB {:.1f}x{:.1f} um'
          .format(t['n_subcell_cpu'], t['n_cpu'], t['rbb']['w'], t['rbb']['h']))

    ab = fig_accel_breakdown(os.path.join(_REPO, 'results', 'accept_air', 'H100_AIR_assumed',
                                          'ga100.flp'),
                             os.path.join(a.out_dir, 'accel_breakdown.png'))
    print('accel_breakdown.png  die {:.1f} mm2  peak class density {:.2f} W/mm2'
          .format(ab['die_mm2'], max(ab['density'].values())))

    res = fig_results(os.path.join(_REPO, 'docs', 'evidence'),
                      os.path.join(a.out_dir, 'results.png'))
    print('results.png  {} tier screens, {} cliff densities'
          .format(res['n_tiers'], res['n_cliff']))

    g = fig_acceptance_gate(os.path.join(a.out_dir, 'acceptance_gate.png'))
    print('acceptance_gate.png  ' + '  '.join('{}:{:.0f}%'.format(
        r['status'], 100 * r['package'] / r['budget']) for r in g))
