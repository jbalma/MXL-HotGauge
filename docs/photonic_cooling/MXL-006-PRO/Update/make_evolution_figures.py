#!/usr/bin/env python
"""MXL-006 update memo: schematic figures of how core designs evolve under targeted laser cooling,
by scale and degree of integration. Pure matplotlib; every panel cites the HotGauge measurement or
argument it rests on. Run on the allocation (campaign server).

    python docs/photonic_cooling/MXL-006-PRO/Update/make_evolution_figures.py
"""
import os
import textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'figures')
os.makedirs(OUT, exist_ok=True)
C = {'si': '#c9d6e3', 'src': '#f2b6a0', 'hot': '#e0533a', 'tile': '#2a78d6', 'tile_off': '#b8cdea',
     'sink': '#8a8985', 'grease': '#d9c98f', 'bond': '#e8d5a3', 'cache': '#9fd3b6', 'cold': '#5bb7e0',
     'text': '#0b0b0b', 'text2': '#52514e', 'grid': '#e9e8e4', 'surface': '#fcfcfb', 'rail': '#c8a951',
     'dark': '#ebebe8'}
plt.rcParams.update({'figure.facecolor': C['surface'], 'axes.facecolor': C['surface'], 'font.size': 9,
                     'axes.titlesize': 10, 'axes.titleweight': 'bold', 'text.color': C['text'],
                     'savefig.dpi': 170, 'savefig.facecolor': C['surface'], 'savefig.bbox': 'tight'})


def _ax_clean(ax):
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def stack_panel(ax, title, layers, tiles=None, hot=None, note='', tag='', src_label='active layer', width=10.0):
    """Cross-section: ``layers`` bottom-up as (name, thickness_units, colour, label)."""
    _ax_clean(ax)
    y = 0.0
    tops = {}
    for name, h, col, lab in layers:
        ax.add_patch(Rectangle((0, y), width, h, facecolor=col, edgecolor='#666', lw=0.6))
        if lab:
            ax.text(width + 0.25, y + h / 2, lab, va='center', fontsize=7.5, color=C['text2'])
        tops[name] = (y, y + h)
        y += h
    if hot:
        y0, y1 = tops['src']
        for x, w in hot:
            ax.add_patch(Rectangle((x, y0), w, y1 - y0, facecolor=C['hot'], edgecolor='none'))
    if tiles:
        y0, y1 = tops['tiles']
        pitch, on = tiles
        n = int(width / pitch)
        for i in range(n):
            ax.add_patch(Rectangle((i * pitch + 0.03, y0), pitch - 0.06, y1 - y0,
                                   facecolor=C['tile'] if (on is None or i in on) else C['tile_off'], edgecolor='#335', lw=0.5))
    ax.set_xlim(-0.2, width + 6.0); ax.set_ylim(-2.6, y + 1.3)
    ax.set_title(textwrap.fill(title, 70), loc='left')
    if tag:
        ax.text(0, y + 0.2, textwrap.fill(tag, 92), fontsize=7.8, va='bottom', color='#1b5e20' if tag.startswith('MEASURED') else '#7a4b00', fontweight='bold')
    if note:
        ax.text(0, -0.35, textwrap.fill(note, 100), fontsize=7.4, color=C['text2'], va='top')


def figure_integration_levels():
    fig, axes = plt.subplots(2, 2, figsize=(15, 11.5))
    fig.subplots_adjust(hspace=0.35, wspace=0.12)
    hot = [(1.4, 0.5), (4.2, 0.5), (7.6, 0.5)]
    # Level 0: conventional
    stack_panel(axes[0, 0], 'Level 0 — conventional direct-die package (gen 0)',
                [('sub', 0.5, C['dark'], 'substrate'), ('si_low', 0.4, C['si'], ''), ('src', 0.3, C['src'], 'active layer: cALU / FPU / AVX hot spots'),
                 ('si', 2.0, C['si'], '200 µm silicon above the transistors'), ('grease', 0.3, C['grease'], '30 µm thermal grease'),
                 ('sink', 1.2, C['sink'], 'cold plate + 88 CFM fin stack')],
                hot=hot, tag='MEASURED: holds 0.60 W/mm² (real map) and 0.85 (flat); the die as traced (0.78) has no steady state',
                note='Binding constraint: leakage runaway through the hottest cALU. Concentrating power costs 1.4× of ceiling. (§P0.17, register §1.3)')
    # Level 1: decoupled cold plate
    stack_panel(axes[0, 1], 'Level 1 — decoupled photonic cold plate on the direct-die part',
                [('sub', 0.5, C['dark'], 'substrate'), ('si_low', 0.4, C['si'], ''), ('src', 0.3, C['src'], 'active layer'),
                 ('si', 2.0, C['si'], '200 µm silicon (the burial depth)'), ('tiles', 0.3, C['tile'], '30 µm GaAs / dye tiles, 500 µm pitch (26 % coverage suffices)'),
                 ('sink', 1.2, C['sink'], 'the SAME cold plate and fan')],
                tiles=(1.0, [1, 4, 7]), hot=hot,
                tag='MEASURED: laser holds 1.20 → 3.50 W/mm² with the per-block planner (2.40 under the seed shape); 0 tiles capped; 200 µm pitch plateau',
                note='What changes in the die: nothing yet. What the laser buys: the runaway (not the spec wall); clock to the device V/F ceiling (+14–34 %); 100 % active cores at 1.2 W/mm²; a 2× burst held under target. Cost: 12 → 114 W removed (per-block planner). (register §1.3)')
    # Level 2: package-integrated, thinned die, dense cluster, re-sized rails
    stack_panel(axes[1, 0], 'Level 2 — package-integrated array on a thinned die; the die redesigned around it',
                [('sub', 0.5, C['dark'], 'substrate; PDN stripes re-sized ~2.5×'), ('si_low', 0.4, C['si'], ''),
                 ('src', 0.3, C['src'], 'active layer: DENSER execution cluster (D1)'), ('si', 0.7, C['si'], '50–100 µm burial (§P0.28: cost within 10 % of the decoupled plate)'),
                 ('tiles', 0.3, C['tile'], '200 µm-pitch tiles, bonded at packaging'), ('sink', 1.2, C['sink'], 'cold plate + fan')],
                tiles=(0.5, [2, 3, 8, 9, 14, 15]), hot=[(1.3, 0.35), (1.75, 0.35), (4.3, 0.35), (4.75, 0.35), (7.5, 0.35), (7.95, 0.35)],
                tag='MEASURED (D1, X1, X3): 2× denser cluster held to 202 W; rails carry 2× the current; at 70 % utilisation 1.22× denser, every rung held',
                note='Binding constraint moves off temperature: the PDN (die current 1.5–3× native along the ladder) and thermal clock skew (3 → 8 % of the period). Design response: re-size rails, per-core clock domains, EM-budgeted target. (§P0.27)')
    # Level 3: stacked — storage die OFF the heat path
    ax = axes[1, 1]
    stack_panel(ax, 'Level 3 — stacked: the storage die OFF the compute die\'s heat path (surviving gen-3 form)',
                [('sink2', 0.9, C['sink'], 'second sink (storage side)'), ('tiles2', 0.3, C['cold'], 'Cr:LiSAF tiles, storage zone at ~280 K'),
                 ('stor', 0.6, C['cache'], '50 µm storage die: L2/L3 (30 % of the die, 54 % of leakage)'), ('bond', 0.2, C['bond'], 'bond / isolating interface'),
                 ('src', 0.3, C['src'], 'compute die active layer'), ('si', 0.7, C['si'], 'thinned compute die'),
                 ('tiles', 0.3, C['tile'], 'dye tile array (compute zone, hot side)'), ('sink', 1.0, C['sink'], 'compute-side cold plate')],
                tiles=(0.5, None), hot=[(1.4, 0.5), (4.2, 0.5), (7.6, 0.5)],
                tag='ARGUED (X4 falsified the sink-side form): storage die must not carry the compute die\'s heat',
                note='Measured 11 Sep: with the storage die BETWEEN compute die and sink, 280 K costs the whole die (99.3 W) at every bond; an isolating bond removes the compute die\'s sink. The cache prize (3.6× leakage, 280 K knee) stands; the geometry is two-sided. (§P0.27.4)')
    fig.suptitle('How the die evolves with the degree of integration of targeted laser cooling — HotGauge, 34-core 7 nm reference die', fontsize=11, fontweight='bold')
    fig.savefig(os.path.join(OUT, 'fig_integration_levels.png')); plt.close(fig)


def floorplan_cartoon(ax, title, cells, tag, note):
    """A one-core floorplan cartoon: cells = list of (x, y, w, h, colour, label, alpha)."""
    _ax_clean(ax)
    for x, y, w, h, col, lab, a in cells:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.01,rounding_size=0.05', facecolor=col, edgecolor='#555', lw=0.6, alpha=a))
        if lab:
            ax.text(x + w / 2, y + h / 2, lab, ha='center', va='center', fontsize=7)
    ax.set_xlim(-0.1, 6.4); ax.set_ylim(-2.3, 5.2)
    ax.set_title(textwrap.fill(title, 44), loc='left')
    ax.text(0, 4.25, textwrap.fill(tag, 58), fontsize=7.3, va='bottom', color='#1b5e20' if tag.startswith('MEASURED') else '#7a4b00', fontweight='bold')
    ax.text(0, -0.2, textwrap.fill(note, 62), fontsize=7.2, color=C['text2'], va='top')


def figure_core_evolution():
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.subplots_adjust(hspace=0.3, wspace=0.15)
    axes = axes.ravel()
    # gen 0: conventional core: exec spread out, caches
    g0 = [(0, 0, 2.2, 2.0, C['cache'], 'L2 / L3\n(cold, leaky)', 1), (2.4, 0, 1.6, 2.0, C['si'], 'front end', 1),
          (4.2, 0, 1.8, 2.0, C['si'], 'load/store\nDCache', 1),
          (0, 2.2, 1.4, 1.8, C['src'], 'cALU', 1), (1.6, 2.2, 1.4, 1.8, C['src'], 'iALU', 1), (3.2, 2.2, 1.4, 1.8, C['src'], 'FPU', 1), (4.8, 2.2, 1.2, 1.8, C['src'], 'AVX', 1)]
    floorplan_cartoon(axes[0], 'Gen 0 — as traced (the die a package can hold)', g0,
                      'MEASURED: hot block cALU at 29 W/mm²; caches 80–98 % static',
                      'Execution units spread to keep the concentration penalty (1.4×) and the runaway at bay. Static power 32 % of the die, 54 % of it in L2/L3.')
    # gen 1: dense cluster under tiles, rails re-sized
    g1 = [(0, 0, 2.2, 2.0, C['cache'], 'L2 / L3', 1), (2.4, 0, 1.6, 2.0, C['si'], 'front end', 1), (4.2, 0, 1.8, 2.0, C['si'], 'load/store\nDCache', 1),
          (0.3, 2.3, 0.9, 1.5, C['hot'], 'cALU', 1), (1.3, 2.3, 0.9, 1.5, C['hot'], 'iALU', 1), (2.3, 2.3, 0.9, 1.5, C['hot'], 'FPU', 1), (3.3, 2.3, 0.9, 1.5, C['hot'], 'AVX', 1),
          (0.1, 2.15, 4.3, 1.85, C['tile'], '', 0.18), (4.6, 2.2, 1.4, 1.8, C['rail'], 'PDN stripes\n× 2', 1)]
    floorplan_cartoon(axes[1], 'Gen 1 — dense execution cluster under the tiles', g1,
                      'MEASURED (D1, X1, X3): 2× / 4× denser held; rails 2× / 4×; 1.22× at 70 % utilisation',
                      'The cluster shrinks under the array (blue), the caches stay put. Cost is paid in light (1.2–1.4× the plan) and in rail metal (2×). Not: a monolithic hot/cold zoned die (1.24 K per 40 W).')
    # gen 2: low-Vt cells on the cooled cluster (argued)
    g2 = list(g1[:3]) + [(0.3, 2.3, 0.9, 1.5, '#b03020', 'cALU\nlow-Vt', 1), (1.3, 2.3, 0.9, 1.5, '#b03020', 'iALU\nlow-Vt', 1), (2.3, 2.3, 0.9, 1.5, '#b03020', 'FPU\nlow-Vt', 1),
                         (3.3, 2.3, 0.9, 1.5, '#b03020', 'AVX\nlow-Vt', 1), (0.1, 2.15, 4.3, 1.85, C['tile'], '', 0.18), (4.6, 2.2, 1.4, 1.8, C['rail'], 'PDN ×2\nper-core\nclock domain', 1)]
    floorplan_cartoon(axes[2], 'Gen 2 — device headroom: low-V_t cells only where cooled', g2,
                      'ARGUED on measured SPICE inputs: +7.6 % clock per 25 mV for 22–30 K of lift',
                      'The V_t lever re-priced on the ASAP7 card (61 mV/dec): 25 mV is inside the demonstrated lift, 50 mV is not. The MR electrical budget binds before the lift. Skew grows with the rung: per-core clock domains.')
    # gen 3: storage die off the heat path
    g3 = [(0, 0, 6.0, 1.3, C['cache'], 'STORAGE DIE: L2 / L3 at ~280 K on Cr:LiSAF\n(off the compute die\'s heat path)', 1),
          (0, 1.35, 6.0, 0.25, C['bond'], 'isolating interface (lateral conduction only)', 1),
          (2.4, 1.8, 1.6, 2.0, C['si'], 'front end', 1), (4.2, 1.8, 1.8, 2.0, C['si'], 'load/store', 1),
          (0.3, 2.1, 0.9, 1.5, C['hot'], 'cALU', 1), (1.3, 2.1, 0.9, 1.5, C['hot'], 'iALU', 1),
          (0.1, 1.9, 2.2, 1.9, C['tile'], '', 0.18)]
    floorplan_cartoon(axes[3], 'Gen 3 — the cache on its own die, off the heat path', g3,
                      'ARGUED; the sink-side form MEASURED and falsified (X4)',
                      'Cooling the cache is worth 2.23× more than first thought and saturates by 280 K; on the compute die, or on a die in its heat path, it costs the whole die. The storage die needs its own sink side.')
    fig.suptitle('The evolution ladder: one architectural change per measured constraint (MEASURED in green, ARGUED in brown)', fontsize=11, fontweight='bold')
    fig.savefig(os.path.join(OUT, 'fig_core_evolution.png')); plt.close(fig)


def figure_scales():
    """Scale ladder: what the array resolves at each pitch / burial, with the measured plateau."""
    fig, ax = plt.subplots(figsize=(12, 4.6))
    _ax_clean(ax)
    rows = [('Rack / board', '10 cm', 'fan, cold plate, 88 CFM', 'the package: 0.325 K/W to this die', C['sink']),
            ('Decoupled cold plate', '500 µm tiles, 200 µm burial', 'GaAs / dye tiles above the silicon', 'MEASURED: 200 µm-pitch plateau; 26 % coverage holds the same ceiling', C['tile']),
            ('Package-integrated', '100–200 µm tiles, 50–100 µm burial', 'array bonded at packaging, thinned die', 'MEASURED (§P0.28): thinning changes the cost < 10 %; 3.00 W/mm² holds only at intermediate burial', C['tile']),
            ('Die-integrated', '≤ 100 µm tiles, ≤ 20 µm burial', 'tiles in the BEOL / backside', 'ARGUED: resolves the 142 × 115 µm cALU; the extractor is 100× under-used on every die', C['tile']),
            ('Stacked / 2.5D', 'two sinks, two arrays', 'storage die on Cr:LiSAF off the heat path', 'ARGUED; sink-side form falsified (X4)', C['cold'])]
    for i, (name, geom, what, evid, col) in enumerate(rows):
        y = 4 - i
        ax.add_patch(Rectangle((0, y - 0.4), 2.6, 0.8, facecolor=col, alpha=0.35, edgecolor='#555', lw=0.5))
        ax.text(0.1, y, name, va='center', fontsize=9, fontweight='bold')
        ax.text(2.8, y + 0.15, geom, va='center', fontsize=8)
        ax.text(2.8, y - 0.2, what, va='center', fontsize=7.5, color=C['text2'])
        ax.text(7.0, y, evid, va='center', fontsize=8, color='#1b5e20' if evid.startswith('MEASURED') else ('#7a4b00' if evid.startswith('ARGUED') else C['text2']))
    ax.set_xlim(-0.1, 14); ax.set_ylim(-0.7, 4.7)
    ax.set_title('Degrees of integration, from the decoupled cold plate to the stack — and what is measured at each', loc='left')
    fig.savefig(os.path.join(OUT, 'fig_scales.png')); plt.close(fig)


if __name__ == '__main__':
    figure_integration_levels()
    figure_core_evolution()
    figure_scales()
    print('written:', sorted(os.listdir(OUT)))
