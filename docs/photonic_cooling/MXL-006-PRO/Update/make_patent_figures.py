#!/usr/bin/env python
"""MXL-006 update memo: PATENT-STYLE drawings of how the core evolves in response to localized,
high-power-density photonic cooling. Monochrome line art with reference numerals, one sheet per
figure, drawn from the REAL floorplans (``examples/floorplans/outputs/…``), the recorded fields and
the evidence JSONs where a number appears. Run on the allocation (campaign server).

    python docs/photonic_cooling/MXL-006-PRO/Update/make_patent_figures.py

Writes ``figures/pat_fig1.png`` … ``pat_fig8.png`` and ``figures/patent_figure_legend.md`` (the
reference numerals). Every caption in the memo carries MEASURED / ARGUED per the register.
"""
import os
import re
import json
import textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, FancyArrowPatch, Circle, Ellipse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
OUT = os.path.join(HERE, 'figures')
EV = os.path.join(REPO, 'docs', 'evidence')
FLP = os.path.join(REPO, 'examples', 'floorplans', 'outputs')
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({'figure.facecolor': 'white', 'axes.facecolor': 'white', 'font.size': 8.5,
                     'font.family': 'DejaVu Sans', 'text.color': 'black', 'savefig.dpi': 200,
                     'savefig.facecolor': 'white', 'savefig.bbox': 'tight', 'hatch.linewidth': 0.5})
LW = 0.9
CLUSTER = ('cALU', 'iALU', 'FPUs', 'AVXs', 'RBB')
CACHES = ('L2', 'L3', 'DCache', 'iCache')
HATCH = {'cluster': 'xxxx', 'cache': '////', 'slab': '', 'front': '....', 'tile': '\\\\\\\\', 'sink': '||||', 'si': '', 'src': '', 'cold': '++++'}
LEGEND = {}     # figure -> [(numeral, meaning)]


def J(name):
    p = os.path.join(EV, name)
    return json.load(open(p)) if os.path.isfile(p) else None


def blocks(path):
    txt = open(path).read()
    out = {}
    for m in re.finditer(r'^(\S+) :\s*\n\s*position\s+([\d.]+)\s*,\s*([\d.]+)\s*;\s*\n\s*dimension\s+([\d.]+)\s*,\s*([\d.]+)', txt, re.M):
        out[m.group(1)] = dict(x=float(m.group(2)), y=float(m.group(3)), w=float(m.group(4)), h=float(m.group(5)))
    return out


def core_blocks(member, core=16):
    p = os.path.join(FLP, member, 'skylake7nm_34core_3_3D-ICE_template.flp') if member != 'ref' else os.path.join(FLP, 'skylake7nm_34core_3_3D-ICE_template.flp')
    b = blocks(p)
    return {k[:-len('_%d' % core)]: v for k, v in b.items() if k.endswith('_%d' % core)}


def fam_class(name):
    if name in CLUSTER:
        return 'cluster'
    if name in CACHES:
        return 'cache'
    if name == 'core_other':
        return 'slab'
    return 'front'


def clean(ax):
    ax.set_xticks([]); ax.set_yticks([])
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.set_aspect('equal')


def figlabel(fig, n, extra=''):
    fig.text(0.5, 0.012, 'FIG. %d%s' % (n, extra), ha='center', va='bottom', fontsize=12, fontweight='bold')


def numeral(ax, num, xy, xytext, ha='left', fs=8):
    ax.annotate(str(num), xy=xy, xytext=xytext, ha=ha, va='center', fontsize=fs,
                arrowprops=dict(arrowstyle='-', lw=0.6, color='black', shrinkA=0, shrinkB=1))


def draw_core(ax, cb, origin=None, scale=1.0, hatch_cluster=True, label_blocks=True, lw=LW):
    """One core's real floorplan, translated to ``origin`` (µm). Returns the bbox (x0, y0, w, h)."""
    x0 = min(v['x'] for v in cb.values()); y0 = min(v['y'] for v in cb.values())
    ox, oy = origin if origin else (0.0, 0.0)
    for name, v in cb.items():
        cls = fam_class(name)
        X, Y = (v['x'] - x0) * scale + ox, (v['y'] - y0) * scale + oy
        W, H = v['w'] * scale, v['h'] * scale
        ax.add_patch(Rectangle((X, Y), W, H, facecolor='white', edgecolor='black', lw=lw if cls != 'front' else 0.4,
                               hatch=(HATCH[cls] if (cls != 'cluster' or hatch_cluster) else '')))
        if label_blocks and W * H > 80000 * scale * scale and cls in ('cache', 'slab', 'cluster'):
            lab = {'core_other': 'control /\nun-itemised', 'DCache': 'D$', 'iCache': 'I$', 'FPUs': 'FPU', 'AVXs': 'AVX'}.get(name, name)
            ax.text(X + W / 2, Y + H / 2, lab, ha='center', va='center', fontsize=6.5,
                    bbox=dict(boxstyle='square,pad=0.1', facecolor='white', edgecolor='none'))
    xs = [(v['x'] - x0) * scale + ox for v in cb.values()]; ys = [(v['y'] - y0) * scale + oy for v in cb.values()]
    return (min(xs), min(ys), max((v['x'] - x0 + v['w']) * scale for v in cb.values()), max((v['y'] - y0 + v['h']) * scale for v in cb.values()))


def block_rect(cb, name, origin=(0, 0), scale=1.0):
    x0 = min(v['x'] for v in cb.values()); y0 = min(v['y'] for v in cb.values())
    v = cb[name]
    return ((v['x'] - x0) * scale + origin[0], (v['y'] - y0) * scale + origin[1], v['w'] * scale, v['h'] * scale)


def stack(ax, x, y, w, layers, lw=LW):
    """Cross-section layers bottom-up: (name, thickness, hatch, label). Returns {name: (y0, y1)}."""
    tops = {}
    for name, h, hatch, lab in layers:
        ax.add_patch(Rectangle((x, y), w, h, facecolor='white', edgecolor='black', lw=lw, hatch=hatch))
        tops[name] = (y, y + h)
        if lab:
            ax.text(x + w + 0.15, y + h / 2, lab, va='center', fontsize=7.5)
        y += h
    return tops


# ---------------------------------------------------------------------------------------------
def fig1_conventional_core():
    """FIG. 1: the conventional core (gen 0) as traced, and the conventional package in section."""
    cb = core_blocks('ref')
    fld = json.load(open(os.path.join(REPO, 'results', 'fields', 'native_d0.78_control', 'field.json')))
    T = {k[:-3]: v['T_K'] - 273.15 for k, v in fld['blocks'].items() if k.endswith('_16')}
    fig = plt.figure(figsize=(11, 6.4))
    ax = fig.add_axes([0.04, 0.36, 0.6, 0.6]); clean(ax)
    bx = draw_core(ax, cb, origin=(0, 0))
    ax.set_xlim(-250, bx[2] + 900); ax.set_ylim(-300, bx[3] + 250)
    ax.text(bx[2] / 2, bx[3] + 120, '100', ha='center', fontsize=9)
    ax.add_patch(Rectangle((0, 0), bx[2], bx[3], facecolor='none', edgecolor='black', lw=1.4))
    Xc, Yc, Wc, Hc = block_rect(cb, 'cALU'); Xf, Yf, Wf, Hf = block_rect(cb, 'FPUs'); Xa, Ya, Wa, Ha = block_rect(cb, 'AVXs')
    ax.add_patch(Rectangle((min(Xc, Xf) - 15, min(Yc, Yf) - 15), max(Xc + Wc, Xf + Wf) - min(Xc, Xf) + 30, max(Yc + Hc, Ya + Ha, Yf + Hf) - min(Yc, Yf) + 30, facecolor='none', edgecolor='black', lw=1.5))
    numeral(ax, 110, (max(Xc + Wc, Xf + Wf) + 15, max(Yc + Hc, Ya + Ha) - 30), (bx[2] + 480, max(Yc + Hc, Ya + Ha) + 40))
    for name, num in (('cALU', 112), ('iALU', 114), ('FPUs', 116), ('AVXs', 118)):
        X, Y, W, H = block_rect(cb, name)
        numeral(ax, num, (X + W, Y + H / 2), (bx[2] + 120, Y + H / 2))
    for name, num, pos in (('L2', 120, (-230, 500)), ('L3', 122, (-230, bx[3] - 90)), ('DCache', 124, (-230, 800)), ('iCache', 126, (-230, 250)), ('core_other', 140, (bx[2] + 120, 250))):
        X, Y, W, H = block_rect(cb, name)
        numeral(ax, num, (X + (0 if pos[0] < 0 else W), Y + H / 2), pos, ha='right' if pos[0] < 0 else 'left')
    X, Y, W, H = block_rect(cb, 'iWin'); numeral(ax, 130, (X + W / 2, Y + H), (X + W / 2 - 300, bx[3] + 120), ha='center')
    ax.text(0, -120, 'worst block 112 (cALU): 29 W/mm², %.0f °C at the native operating point (MEASURED)' % T.get('cALU', 78.6), fontsize=7, va='top')
    # section A-A'
    ax2 = fig.add_axes([0.66, 0.36, 0.32, 0.6]); clean(ax2)
    tops = stack(ax2, 0, 0, 6, [('sub', 0.6, HATCH['slab'], '200  substrate / bumps'), ('si_lo', 0.35, '', ''), ('src', 0.25, HATCH['cluster'], '202  active layer'),
                                ('si', 2.0, '', '204  silicon, 200 µm'), ('tim', 0.3, '....', '206  thermal interface'), ('plate', 0.9, HATCH['sink'], '208  cold plate'), ('sink', 1.3, '||||', '210  fin stack + fan')])
    for hx in (1.2, 3.1, 4.8):
        ax2.add_patch(Rectangle((hx, tops['src'][0]), 0.35, 0.25, facecolor='black'))
        for k in range(1, 4):
            ax2.add_patch(Ellipse((hx + 0.175, tops['src'][1] + 0.45 * k), 0.9 * k, 0.55 * k, facecolor='none', edgecolor='black', lw=0.5, ls=(0, (2, 2))))
    ax2.set_xlim(-0.3, 9.5); ax2.set_ylim(-0.6, 6.3)
    ax2.text(3.0, 6.0, 'section A–A′ (not to scale)', ha='center', fontsize=8)
    ax2.text(0, -0.45, 'heat from 112 spreads through 204 into 208: the die\'s ceiling is a leakage runaway\nthrough the hottest block; concentrating power costs 1.4× of ceiling (MEASURED, §P0.17)', fontsize=7, va='top')
    fig.text(0.04, 0.27, textwrap.fill('FIG. 1 — The conventional core 100 as traced (one core of the 34-core 7 nm reference die, drawn from its floorplan): execution cluster 110 '
                                       '(complex ALU 112, integer ALU 114, floating-point units 116, vector units 118) spread among the caches 120–126, the front end 130 and the '
                                       'un-itemised control slab 140. Hatching: cross = execution units, diagonal = caches, dots = front end. Section A–A′: the conventional '
                                       'direct-die package 200–210.', 150), fontsize=8, va='top')
    figlabel(fig, 1)
    fig.savefig(os.path.join(OUT, 'pat_fig1.png')); plt.close(fig)
    LEGEND[1] = [(100, 'core as traced (gen 0)'), (110, 'execution cluster'), (112, 'complex ALU (the worst block)'), (114, 'integer ALU'), (116, 'floating-point units'), (118, 'vector (AVX) units'),
                 (120, 'L2 cache'), (122, 'L3 slice'), (124, 'data cache'), (126, 'instruction cache'), (130, 'front end / scheduler'), (140, 'control slab'),
                 (200, 'substrate and bumps'), (202, 'active layer'), (204, 'silicon above the transistors (burial depth)'), (206, 'thermal interface material'), (208, 'cold plate'), (210, 'fin stack and fan')]


def fig2_apparatus():
    """FIG. 2: the driven, planner-commanded tile array as an apparatus, and its control loop."""
    fig = plt.figure(figsize=(11.5, 7.2))
    ax = fig.add_axes([0.03, 0.30, 0.55, 0.66]); clean(ax)
    tops = stack(ax, 0, 0, 7, [('sub', 0.6, '', '200'), ('si_lo', 0.35, '', ''), ('src', 0.25, HATCH['cluster'], '202  active layer'),
                               ('si', 1.6, '', '204  burial depth d (200 µm decoupled … 5 µm integrated)'), ('tiles', 0.45, '', ''), ('plate', 0.9, HATCH['sink'], '208  the SAME cold plate'), ('sink', 1.0, '||||', '210')])
    y0, y1 = tops['tiles']
    pitch = 1.0
    for i in range(7):
        on = i in (1, 3, 5)
        ax.add_patch(Rectangle((i * pitch + 0.04, y0), pitch - 0.08, y1 - y0, facecolor='white', edgecolor='black', lw=LW, hatch=HATCH['tile'] if on else ''))
        if on:
            for k in range(3):
                ax.add_patch(FancyArrowPatch((i * pitch + 0.25 + 0.25 * k, y0 - 0.05), (i * pitch + 0.25 + 0.25 * k, y0 - 0.55), arrowstyle='<-', mutation_scale=7, lw=0.6))
    ax.annotate('300 / 302  tile array (30 µm GaAs or dye film, pitch p)', xy=(6.96, (y0 + y1) / 2), xytext=(7.4, y1 + 0.95), fontsize=7.5, va='center', arrowprops=dict(arrowstyle='-', lw=0.6))
    for hx in (1.2, 3.2, 5.2):
        ax.add_patch(Rectangle((hx, tops['src'][0]), 0.5, 0.25, facecolor='black'))
    ax.add_patch(Rectangle((0, y1 + 0.02), 7, 0.14, facecolor='white', edgecolor='black', lw=0.6, hatch='....'))
    ax.annotate('304  pump waveguides / couplers', xy=(7.0, y1 + 0.09), xytext=(7.4, y1 - 0.12), fontsize=7.5, va='center', arrowprops=dict(arrowstyle='-', lw=0.6))
    ax.add_patch(Rectangle((-0.75, y0 - 0.1), 0.55, 0.7, facecolor='white', edgecolor='black', lw=0.8, hatch='---'))
    ax.annotate('306  luminescence collector', xy=(-0.5, y0 - 0.1), xytext=(-0.3, y0 - 0.9), fontsize=7.5, arrowprops=dict(arrowstyle='-', lw=0.6))
    ax.text(0, -0.7, 'heat lifted from the blocks under the driven tiles crosses 204 and leaves as anti-Stokes fluorescence,\nnot as conduction into 208', fontsize=7, va='top')
    ax.set_xlim(-1.0, 13.5); ax.set_ylim(-1.5, 5.9)
    # control loop
    ax2 = fig.add_axes([0.6, 0.30, 0.39, 0.66]); clean(ax2)
    boxes = [('312', 'SENSE\nper-block / per-tile temperature\n(fluorescence thermometry)', 0.5, 4.2, 1.2), ('314', 'PLAN\nsensitivities → per-block removal\n→ projected onto tiles → bisect to\nthe minimum plan on the cool branch\nunder the conservation cap', 0.5, 2.2, 1.7),
             ('316', 'DRIVE\nper-tile pump power', 0.5, 0.6, 1.2)]
    for num, txt, x, y, h in boxes:
        ax2.add_patch(Rectangle((x, y), 4.2, h, facecolor='white', edgecolor='black', lw=1.0))
        ax2.text(x + 0.15, y + h / 2, txt, va='center', fontsize=7)
        ax2.text(x + 4.35, y + h / 2, num, va='center', fontsize=9)
    ax2.add_patch(Rectangle((0.5, 5.9), 4.2, 0.7, facecolor='white', edgecolor='black', lw=1.2, hatch='xxxx'))
    ax2.text(2.6, 6.25, 'the die 100 under the array 300', ha='center', va='center', fontsize=7.5, bbox=dict(facecolor='white', edgecolor='none', pad=1))
    for (ya, yb) in ((5.9, 5.45), (4.2, 3.95), (2.2, 1.85)):
        ax2.add_patch(FancyArrowPatch((2.6, ya), (2.6, yb), arrowstyle='->', mutation_scale=10, lw=0.8))
    ax2.add_patch(FancyArrowPatch((4.7, 1.2), (5.6, 1.2), arrowstyle='-', lw=0.8))
    ax2.add_patch(FancyArrowPatch((5.6, 1.2), (5.6, 6.25), arrowstyle='-', lw=0.8))
    ax2.add_patch(FancyArrowPatch((5.6, 6.25), (4.75, 6.25), arrowstyle='->', mutation_scale=10, lw=0.8))
    ax2.text(5.7, 3.4, '310', fontsize=9)
    ax2.set_xlim(0, 6.6); ax2.set_ylim(0, 6.9)
    fig.text(0.03, 0.22, textwrap.fill('FIG. 2 — The apparatus: a photonic cooling layer 300 of anti-Stokes tiles 302 above the back surface of the die, pumped through waveguides 304 '
                                       'with the fluorescence collected by 306, under a controller 310 that senses (312), plans (314) and drives (316). MEASURED: the driven array '
                                       'holds the reference die from 1.20 to 3.50 W/mm² (per-block planner; the undriven layer of the same film fails at 1.20), for 12 → 114 W removed '
                                       'at 1.20 → 2.00 W/mm²; 0 tiles capped by the target device on the reference die.', 150), fontsize=8, va='top')
    figlabel(fig, 2)
    fig.savefig(os.path.join(OUT, 'pat_fig2.png')); plt.close(fig)
    LEGEND[2] = [(300, 'photonic cooling layer (tile array)'), (302, 'anti-Stokes tile (GaAs or SiN-encapsulated dye, 30 µm)'), (304, 'pump waveguides and couplers'), (306, 'luminescence collector'),
                 (310, 'controller'), (312, 'sensing: per-tile temperature'), (314, 'planner: minimum plan on the cool branch under the conservation cap'), (316, 'per-tile pump drive')]


def _compact_notes():
    """Top held rung per compact member, read from the evidence file (§P0.36); {} if absent."""
    d = J('compact_cluster.json')
    if not d:
        return {}
    out = {}
    for r in d.get('rows', []):
        key = (r['factor'], r['pitch_um'], r['burial_um'])
        if r.get('holds'):
            out[key] = max(out.get(key, 0), r['W'])
    return out


def fig3_densified_cluster(compact=False, finger=False):
    """FIG. 3 / 3B: gen 1 — the same core with its execution cluster at 1×–16× density and the tile pitch that resolves it;
    3B draws the COMPACT members (the four units in one near-square block) beside nothing else changed."""
    if not compact:
        members = [('ref', '1× (as traced)', 500, 'holds to 3.50 W/mm²'), ('d1_exec0.5', '2× denser', 500, 'holds every rung to 243 W'), ('d1_exec0.25', '4× denser', 500, 'holds to 202 W'),
                   ('d1_exec0.125', '8× denser', 200, 'holds to 202 W at 20–5 µm burial'), ('d1_exec0.0625', '16× denser', 100, 'holds 202 W only at 100 µm pitch')]
    elif finger:
        members = [('ref', '1× (as traced)', 500, 'holds to 3.50 W/mm²'),
                   ('d1_exec0.0625', '16×, the tiler\'s strips', 100, 'holds to 202 W (s 0.88); 243 W: no steady state'),
                   ('d1_exec0.0625_finger', '16×, DESIGNED fingers 906', 100, 'holds EVERY rung to 243 W (s 0.76) for 0.74–0.79× the strips\' plan'),
                   ('d1_exec0.03125', '32×, the tiler\'s strips', 100, 'holds to 162 W; 202 W: no steady state'),
                   ('d1_exec0.03125_finger', '32×, DESIGNED fingers 906', 100, 'holds EVERY rung to 243 W (s 0.85)')]
    else:
        n = _compact_notes()

        def note(F, P, B):
            w = n.get((F, P, B))
            return ('holds to %.0f W (compact, %d µm burial)' % (w, B)) if w else 'see §P0.36'
        members = [('ref', '1× (as traced)', 500, 'holds to 3.50 W/mm²'), ('d1_exec0.5_compact', '2× denser, compact', 500, note(0.5, 500, 200)),
                   ('d1_exec0.25_compact', '4× denser, compact', 500, note(0.25, 500, 200)), ('d1_exec0.125_compact', '8× denser, compact', 200, note(0.125, 200, 20)),
                   ('d1_exec0.0625_compact', '16× denser, compact', 100, note(0.0625, 100, 20))]
    fig, axes = plt.subplots(2, 5, figsize=(16, 9.5), gridspec_kw={'height_ratios': [1, 1.7]})
    fig.subplots_adjust(wspace=0.05, hspace=0.02, bottom=0.2, top=0.95)
    for col, (m, lab, pitch, note) in enumerate(members):
        ax, axz = axes[0, col], axes[1, col]
        clean(ax); clean(axz)
        cb = core_blocks(m)
        bx = draw_core(ax, cb, label_blocks=False, lw=0.6)
        X, Y, W, H = block_rect(cb, 'cALU'); Xf, Yf, Wf, Hf = block_rect(cb, 'FPUs'); Xa, Ya, Wa, Ha = block_rect(cb, 'AVXs')
        cx0, cy0 = min(X, Xf, Xa) - 40, min(Y, Yf, Ya) - 40
        cx1, cy1 = max(X + W, Xf + Wf, Xa + Wa) + 40, max(Y + H, Yf + Hf, Ya + Ha) + 40
        ax.add_patch(Rectangle((cx0, cy0), cx1 - cx0, cy1 - cy0, facecolor='none', edgecolor='black', lw=1.5))
        ax.set_xlim(bx[0] - 120, bx[2] + 120); ax.set_ylim(bx[1] - 80, bx[3] + 80)
        ax.set_title(lab, fontsize=9.5, fontweight='bold')
        ax.text(bx[0], bx[3] + 40, "110" + "′" * col, fontsize=9)
        # zoom: the cluster with the tile grid that resolves it, aligned on the die grid
        draw_core(axz, cb, label_blocks=False, lw=0.6)
        zx0, zy0, zx1, zy1 = cx0 - 0.6 * pitch, cy0 - 0.6 * pitch, cx1 + 0.6 * pitch, cy1 + 0.6 * pitch
        gx = int(zx0 // pitch) * pitch
        while gx < zx1:
            gy = int(zy0 // pitch) * pitch
            while gy < zy1:
                axz.add_patch(Rectangle((gx, gy), pitch, pitch, facecolor='none', edgecolor='black', lw=1.0, ls=(0, (3, 2))))
                gy += pitch
            gx += pitch
        axz.add_patch(Rectangle((cx0, cy0), cx1 - cx0, cy1 - cy0, facecolor='none', edgecolor='black', lw=1.5))
        for nm, num in (('cALU', 112), ('iALU', 114), ('FPUs', 116), ('AVXs', 118)):
            bx_, by_, bw_, bh_ = block_rect(cb, nm)
            axz.text(bx_ + bw_ + 0.05 * pitch, by_ + bh_ / 2, str(num), fontsize=6.5, va='center', bbox=dict(facecolor='white', edgecolor='none', pad=0.5))
        side = max(zx1 - zx0, zy1 - zy0)
        cxm, cym = (zx0 + zx1) / 2, (zy0 + zy1) / 2
        axz.set_xlim(cxm - side / 2, cxm + side / 2); axz.set_ylim(cym - side / 2 - 0.35 * side, cym + side / 2)
        axz.add_patch(Rectangle((cxm - side / 2, cym - side / 2 - 0.36 * side), side, 0.345 * side, facecolor='white', edgecolor='none', zorder=5))
        axz.text(cxm - side / 2, cym - side / 2 - 0.05 * side, textwrap.fill('detail: tiles 302 at %d µm pitch (dashed) over 110%s; %s' % (pitch, "′" * col, note), 36), fontsize=7, va='top', zorder=6)
    if finger:
        fig.text(0.05, 0.12, textwrap.fill('FIG. 3C — Gen 1 with DESIGNED fingers 906 (19 Sep, §P0.38): ONE execution column in which every execution unit (112–118) is a full-width strip with '
                                           'cooler logic on both sides — FP register file · vector unit 118 · FP window · FPU 116 · reorder buffer · complex ALU 112 · integer window · integer '
                                           'ALU 114 · integer register file · bus — so the hot strips sit 140–270 µm apart, each under its own 100 µm tile 302. Same areas, powers, block names '
                                           'and die area as the tiler\'s strip members beside them, where the two ALUs are adjacent and the vector / FP pair is a 17–34 µm-wide column of its own. '
                                           'MEASURED at matched die watts (per-block planner, 20 µm burial, 50 µm cells, 0 tiles capped): the designed fingers hold every rung to 243 W at 16× '
                                           'AND at 32× (a ~920 W/mm² complex ALU) where the strips lose 243 W and 202 W, for a quarter to a half less plan. A strip is one cell tall in both '
                                           'layouts, so this comparison is like for like.', 175), fontsize=8, va='top')
        figlabel(fig, 3, 'C')
        fig.savefig(os.path.join(OUT, 'pat_fig3c.png')); plt.close(fig)
        LEGEND['3C'] = [(906, 'execution units as DESIGNED fingers: each a full-width strip interdigitated with scheduler / register-file logic at the tile pitch')]
        return
    if compact:
        fig.text(0.05, 0.12, textwrap.fill('FIG. 3B — Gen 1 with a COMPACT cluster: the same five cores, the four execution units (112–118) grouped into one near-square block at the end of the '
                                           'execution column (vector unit across it; FPU beside a stacked integer-ALU / complex-ALU pair) instead of strips of two full-height columns. Same '
                                           'areas, powers, block names and die area as FIG. 3; only the SHAPE changes (16× complex ALU: 117 × 9 µm → 36 × 28 µm; cluster block 152 × 214 µm). '
                                           'Drawn from the compact floorplans; the notes under each detail are read from docs/evidence/compact_cluster.json (§P0.36, MEASURED, per-block planner, '
                                           '50 µm cells — the 16× unit is still sub-cell, so its holds are lower bounds).', 175), fontsize=8, va='top')
        figlabel(fig, 3, 'B')
        fig.savefig(os.path.join(OUT, 'pat_fig3b.png')); plt.close(fig)
        LEGEND['3B'] = []
        return
    fig.text(0.05, 0.12, textwrap.fill('FIG. 3 — Gen 1: the execution cluster 110 densified under the tiles — the SAME core drawn from the five floorplans (units 112–118 at 1×, 1/2, 1/4, 1/8, 1/16 '
                                       'of their area at unchanged power; caches 120–126, front end 130 and slab 140 unchanged; the die shrinks 0.90 → 0.82×). The dashed squares are the tile '
                                       'pitch 302 that resolves the cluster. MEASURED at matched die watts, per-block planner: the 2× cluster holds every reference rung to 243 W and the 4× to '
                                       '202 W (§P0.34); the 8× (230 W/mm² cALU) holds to 202 W at every burial and pitch tried and the 16× (460 W/mm²) only at 100 µm pitch (§P0.32). '
                                       'The dense units are slivers of the original column width (cALU 142 × 115 µm → 117 × 9 µm at 16×), so the tile must be matched to the unit.', 175),
             fontsize=8, va='top')
    figlabel(fig, 3)
    fig.savefig(os.path.join(OUT, 'pat_fig3.png')); plt.close(fig)
    LEGEND[3] = [("110′ … 110″″", 'the execution cluster at 2×, 4×, 8×, 16× density'), (302, 'tile pitch matched to the cluster (500 / 200 / 100 µm)')]


def fig4_rails_and_budget():
    """FIG. 4: gen 1 in section — rails re-sized over the cluster; the target chosen on a lifetime budget; what the clock is made of."""
    m = J('fmax_model.json'); c = J('clock_fmax.json')
    fig = plt.figure(figsize=(13, 7.6))
    ax = fig.add_axes([0.03, 0.34, 0.5, 0.62]); clean(ax)
    tops = stack(ax, 0, 0, 8, [('sub', 0.5, '', '200'), ('src', 0.3, '', '202'), ('beol', 0.7, '', ''), ('si', 1.2, '', '204  burial d'), ('tiles', 0.45, '', ''), ('plate', 0.8, HATCH['sink'], '208')])
    # dense cluster in the active layer
    ax.add_patch(Rectangle((2.6, tops['src'][0]), 1.6, 0.3, facecolor='white', edgecolor='black', hatch='xxxx', lw=LW)); ax.text(3.4, tops['src'][0] - 0.25, '110′', ha='center', fontsize=8)
    # rails in the BEOL: thin outside, wide over the cluster
    yb0, yb1 = tops['beol']
    for x, w in ((0.3, 0.12), (1.0, 0.12), (1.7, 0.12), (5.0, 0.12), (5.7, 0.12), (6.4, 0.12), (7.1, 0.12)):
        ax.add_patch(Rectangle((x, yb0 + 0.1), w, yb1 - yb0 - 0.2, facecolor='black'))
    for x, w in ((2.7, 0.32), (3.25, 0.32), (3.8, 0.32)):
        ax.add_patch(Rectangle((x, yb0 + 0.1), w, yb1 - yb0 - 0.2, facecolor='black'))
    ax.text(8.15, (yb0 + yb1) / 2, '400  power-distribution stripes\n402  widened ~J× over 110′ — MEASURED (§P0.39, static IR):\n        on native rails the 8× / 16× cluster clocks −19 / −31 %\n        with the array idle; widened 8× / 16×: +1.3 / +0.2 %', va='center', fontsize=7.2)
    ax.annotate('402', xy=(4.12, (yb0 + yb1) / 2), xytext=(4.7, -0.35), fontsize=8.5, arrowprops=dict(arrowstyle='-', lw=0.6))
    y0, y1 = tops['tiles']
    for i in range(8):
        on = i in (3, 4)
        ax.add_patch(Rectangle((i + 0.04, y0), 0.92, y1 - y0, facecolor='white', edgecolor='black', lw=LW, hatch=HATCH['tile'] if on else ''))
    ax.text(8.15, (y0 + y1) / 2, '302  tiles, driven where 110′ sits', va='center', fontsize=7.5)
    ax.add_patch(Rectangle((0.2, y1 + 1.25), 3.0, 0.7, facecolor='white', edgecolor='black', lw=1.0))
    ax.text(1.7, y1 + 1.6, '410  target T* chosen on the\nlifetime budget, not the spec', ha='center', va='center', fontsize=7)
    ax.add_patch(FancyArrowPatch((2.6, y1 + 1.25), (3.3, y1 + 0.05), arrowstyle='->', mutation_scale=9, lw=0.7))
    ax.set_xlim(-0.2, 14.5); ax.set_ylim(-0.8, 6.3)
    # inset: the V_max ladder
    ax2 = fig.add_axes([0.58, 0.62, 0.4, 0.32])
    rows = m['tables']['ceiling_vs_T_qual'] if m else []
    if rows:
        T = [r['T_C'] for r in rows]
        ax2.plot(T, [r['v_max_reliability_V'] for r in rows], color='black', lw=1.2, marker='o', ms=3)
        ax2.axhline(0.77, color='black', lw=0.6, ls='--')
        ax2.text(28, 0.773, '0.77 V = the fixed 10 % overdrive at 100 °C', fontsize=7)
        for tc, txt, dx, dy in ((92, '92 °C: +1 %', -24, 0.009), (60, '60 °C: +6 %', 4, 0.012), (27, '27 °C: +12 %', 6, -0.006)):
            r = min(rows, key=lambda r: abs(r['T_C'] - tc))
            ax2.annotate(txt, xy=(r['T_C'], r['v_max_reliability_V']), xytext=(r['T_C'] + dx, r['v_max_reliability_V'] + dy), fontsize=7, arrowprops=dict(arrowstyle='-', lw=0.5))
    ax2.set_xlabel('worst-block temperature T*, °C', fontsize=7.5); ax2.set_ylabel('V_max on the lifetime budget, V', fontsize=7.5); ax2.tick_params(labelsize=7)
    ax2.set_title('410: the budget (EM + TDDB, Arrhenius) buys supply as the array holds T* down', fontsize=8, pad=10)
    # inset: the period composition
    ax3 = fig.add_axes([0.58, 0.29, 0.4, 0.19])
    per = {'gate': 0.58, 'wire': 0.31, 'skew': 0.03, 'overhead': 0.08}
    if m:
        p0 = m['model']['anchor']; tot = p0['period_ps']
        per = {'gate': p0['gate_ps'] / tot, 'wire': p0['wire_ps'] / tot, 'skew': p0['skew_ps'] / tot, 'overhead': p0['overhead_ps'] / tot}
    left = 0
    for k, hatch in (('gate', 'xxxx'), ('wire', '////'), ('skew', '....'), ('overhead', '')):
        ax3.barh([1], [per[k]], left=left, color='white', edgecolor='black', hatch=hatch, height=0.5)
        if per[k] > 0.12:
            ax3.text(left + per[k] / 2, 1, '%s %.0f %%' % (k, 100 * per[k]), ha='center', va='center', fontsize=6.5, bbox=dict(facecolor='white', edgecolor='none', pad=0.5))
        else:
            ax3.annotate('%s %.0f %%' % (k, 100 * per[k]), xy=(left + per[k] / 2, 1.25), xytext=(left + per[k] / 2 - (0.06 if k == 'skew' else -0.02), 1.62), fontsize=6.5, ha='center', arrowprops=dict(arrowstyle='-', lw=0.5))
        left += per[k]
    gw = per['gate'] * 0.5 + per['wire'] * 0.5; fx = per['skew'] + per['overhead']
    ax3.barh([0], [gw], color='white', edgecolor='black', hatch='xxxx', height=0.5)
    ax3.barh([0], [fx], left=gw, color='white', edgecolor='black', hatch='....', height=0.5)
    ax3.text(gw / 2, 0, 'gate + wire halve', ha='center', va='center', fontsize=6.5, bbox=dict(facecolor='white', edgecolor='none', pad=0.5))
    ax3.annotate('skew + overhead: fixed ps', xy=(gw + fx / 2, 0.25), xytext=(gw + fx / 2 + 0.12, 0.55), fontsize=6.5, arrowprops=dict(arrowstyle='-', lw=0.5))
    ax3.set_xlim(0, 1); ax3.set_ylim(-0.4, 1.9); ax3.set_yticks([0, 1]); ax3.set_yticklabels(['re-pipelined\n(10 FO4)', 'as traced\n(20 FO4)'], fontsize=7); ax3.set_xticks([]); ax3.set_title('the clock period at the anchor: a third does not scale with supply', fontsize=8)
    for s_ in ax3.spines.values():
        s_.set_visible(False)
    laser = (c or {}).get('runs', {}).get('qual_d1.00', {}).get('rows', {}).get('array_on', {}).get('f_GHz')
    t60 = (c or {}).get('runs', {}).get('qual_d1.00_T60', {}).get('rows', {}).get('array_on', {}).get('f_GHz')
    n10 = (c or {}).get('runs', {}).get('qual_d1.00_N10', {}).get('rows', {}).get('array_on', {}).get('f_GHz')
    fig.text(0.03, 0.2, textwrap.fill('FIG. 4 — Gen 1 in section: the densified cluster 110′ under driven tiles 302, its power-distribution stripes 400 widened (402) in proportion to the '
                                       'cluster\'s current-density ratio, and the array\'s target temperature 410 chosen on an electromigration / dielectric-breakdown lifetime budget rather than '
                                       'the thermal specification. Upper inset: the budget buys supply as an Arrhenius ladder (MEASURED on the ASAP7 card; constants stated). Lower inset: the '
                                       'clock period decomposed — with wire, skew and setup/jitter in it, the cooled die\'s ceiling on the as-traced pipeline is %s GHz at the 92 °C target and %s GHz '
                                       'at a 60 °C target; a 10-FO4 pipeline reaches %s GHz, where the cooler binds again (coupled search, §P0.31). 10 GHz needs a 6–7 FO4 pipeline: the cooler '
                                       'and the pipeline are separate levers.' % ('%.2f' % laser if laser else '3.76', '%.2f' % t60 if t60 else '4.08', '%.2f' % n10 if n10 else '5.75'), 175), fontsize=8, va='top')
    figlabel(fig, 4)
    fig.savefig(os.path.join(OUT, 'pat_fig4.png')); plt.close(fig)
    LEGEND[4] = [(400, 'power-distribution stripes (top metal)'), (402, 'stripes widened ~J× over the dense cluster'), (410, 'target temperature chosen on the lifetime budget')]


def fig5_pitch_and_film():
    """FIG. 5: the tile pitch against the unit, and the film's cold end — the co-design rule."""
    fig, axes = plt.subplots(1, 4, figsize=(15, 5.6))
    fig.subplots_adjust(wspace=0.08, bottom=0.34, top=0.9)
    titles = ['(a) coarse tile: light spent on cool silicon', '(b) tile matched to the unit: held', '(c) matched tile at the top rung: the film\'s cold end', '(d) the responses']
    for ax, t in zip(axes, titles):
        clean(ax); ax.set_title(textwrap.fill(t, 34), fontsize=8.5, fontweight='bold')
        ax.set_xlim(-0.3, 6.3); ax.set_ylim(-1.6, 7.0)
    for ax, mode in zip(axes[:3], ('coarse', 'matched', 'cold')):
        tops = stack(ax, 0, 0, 6, [('sub', 0.4, '', ''), ('src', 0.3, '', ''), ('si', 1.0, '', ''), ('tiles', 0.5, '', ''), ('plate', 0.7, HATCH['sink'], '')], lw=0.8)
        ax.add_patch(Rectangle((2.7, tops['src'][0]), 0.6, 0.3, facecolor='black')); ax.text(3.0, tops['src'][0] - 0.3, '110″ (460 W/mm²)', ha='center', fontsize=7)
        y0, y1 = tops['tiles']
        if mode == 'coarse':
            ax.add_patch(Rectangle((1.0, y0), 4.0, y1 - y0, facecolor='white', edgecolor='black', lw=LW, hatch=HATCH['tile'])); ax.text(3.0, y1 + 0.15, '302 (200 µm)', ha='center', fontsize=7.5)
            for k in range(1, 4):
                ax.add_patch(Ellipse((3.0, tops['src'][1] + 0.35 * k), 1.4 * k, 0.5 * k, facecolor='none', edgecolor='black', lw=0.5, ls=(0, (2, 2))))
            ax.text(0, -0.5, 'the tile spans 4× the unit\'s footprint; the plan\nreaches the conservation cap (s = 1.00) and the\n16× cluster has no steady state at 202 W (MEASURED)', fontsize=7, va='top')
        elif mode == 'matched':
            ax.add_patch(Rectangle((2.5, y0), 1.0, y1 - y0, facecolor='white', edgecolor='black', lw=LW, hatch=HATCH['tile'])); ax.text(3.0, y1 + 0.15, '302 (100 µm)', ha='center', fontsize=7.5)
            for x in (1.4, 4.6):
                ax.add_patch(Rectangle((x - 0.5, y0), 1.0, y1 - y0, facecolor='white', edgecolor='black', lw=LW))
            ax.text(0, -0.5, 'the tile matches the unit: 164 W holds the 16×\ncluster at 202 W at either burial; demand\n160–170 W/mm² on the tile (MEASURED)', fontsize=7, va='top')
        else:
            ax.add_patch(Rectangle((2.5, y0), 1.0, y1 - y0, facecolor='white', edgecolor='black', lw=LW, hatch='xxxx')); ax.text(3.0, y1 + 0.15, '302 at 253 K', ha='center', fontsize=7.5)
            ax.text(0, -0.5, 'at 243 W the tile is driven to 253–254 K where the\ndye\'s transparency cap has collapsed; asked for\n170–200 W/mm², it is capped: no steady state (MEASURED)', fontsize=7, va='top')
    # (c) inset: the film's capability vs its temperature (register numbers, schematic curve)
    ax = axes[2]
    axi = ax.inset_axes([0.3, 0.7, 0.66, 0.25])
    Tk = [176, 200, 230, 263, 300, 350, 400]; h = [0.01, 11, 60, 263, 813, 2400, 5900]
    axi.semilogy(Tk, h, color='black', lw=1.0); axi.plot([253], [190], 'ko', ms=4); axi.text(256, 120, 'demand at 253 K', fontsize=6)
    axi.set_xlabel('tile T, K', fontsize=6); axi.set_ylabel('W/mm²', fontsize=6); axi.tick_params(labelsize=6); axi.set_title('target device (v100 Table 1.1)', fontsize=6.5)
    # (d) responses
    ax = axes[3]
    resp = [('502', 'tile pitch matched to the unit: ~100 µm. MEASURED: 200 µm cannot resolve a 16× unit; 50 µm loses every dye row (59–87 tiles capped)'),
            ('504', 'hot-zone material whose capability RISES on cooling (retuned, enhanced GaAs). MEASURED: the 8× cluster holds 243 W, s 0.88–0.91, tile at 235 K, 0 capped'),
            ('506', 'dual-material layout: that material over the execution column only, dye elsewhere. MEASURED: identical to 504 on the 8× cluster'),
            ('508', 'the price: η_ASF 0.010–0.016 at the coldest tile against the dye\'s ~0.10 — 6–10× the pump power per watt lifted there')]
    for i, (num, txt) in enumerate(resp):
        y = 5.2 - i * 1.55
        ax.add_patch(Rectangle((-0.2, y - 0.68), 6.0, 1.36, facecolor='white', edgecolor='black', lw=0.9))
        ax.text(-0.08, y, textwrap.fill(txt.replace('\n', ' '), 40), va='center', fontsize=6.2); ax.text(5.95, y, num, va='center', ha='left', fontsize=8.5)
    fig.text(0.04, 0.2, textwrap.fill('FIG. 5 — The tile against a dense functional unit, and the film\'s own limit. (a) A tile coarser than the unit spends its light on the silicon around it and '
                                      'the plan hits energy conservation before the unit is held. (b) A tile matched to the unit holds it. (c) At the top rung the matched tile is driven '
                                      'to 253 K, below the point where the dye\'s transparency cap has collapsed (inset: the target device\'s capability against its own temperature, from '
                                      'the register), and the planner\'s request exceeds what the tile can deliver — the first case on any die here where the film binds. (d) The design '
                                      'responses, MEASURED 19 Sep (§P0.35): pitch matched to the unit (502); a hot-zone material whose capability rises on cooling (504), which returns the 8× '
                                      'cluster\'s 243 W rung; the same material over the execution column only (506); and its price in pump power (508). That material is v100 Table 1.1\'s ceiling '
                                      'design point: an upper bound, not a device. §P0.32 / §P0.35, 50 µm cells (the 16× unit is sub-cell: its holds are lower bounds).', 185), fontsize=8, va='top')
    figlabel(fig, 5)
    fig.savefig(os.path.join(OUT, 'pat_fig5.png')); plt.close(fig)
    LEGEND[5] = [('110″', 'the 16× (460 W/mm²) execution unit'), (502, 'tile pitch matched to the unit'), (504, 'hot-zone tile material whose capability rises on cooling'), (506, 'dual-material tile layout: 504 over the execution column, dye elsewhere'), (508, 'the pump-power price of 504')]


def fig6_storage_die():
    """FIG. 6: gen 3 — the storage die off the compute die's heat path (and the falsified form)."""
    # 27 Oct: viewed at last (the 19 Sep sheet was regenerated unseen) -- (a)'s title ran into
    # (b)'s and (b)'s layer labels and note were clipped at the panel edge. Titles wrap, (b)
    # gets the width its labels need, the note is wrapped to the panel.
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.2), gridspec_kw={'width_ratios': [1.0, 1.35, 1.0]})
    fig.subplots_adjust(wspace=0.12, bottom=0.34, top=0.88, left=0.03, right=0.99)
    for ax, xmax in zip(axes, (10.5, 14.5, 10.5)):
        clean(ax); ax.set_xlim(-0.3, xmax); ax.set_ylim(-1.6, 7.4)
    ax = axes[0]; ax.set_title('(a) storage die on the sink side —\nMEASURED, FALSIFIED (X4)', fontsize=8.5, fontweight='bold')
    stack(ax, 0, 0, 6, [('sub', 0.5, '', '200'), ('src', 0.3, 'xxxx', '202  compute die'), ('si', 0.9, '', ''), ('bond', 0.25, '....', '620  bond (120 → 0.5 W/mK swept)'),
                        ('stor', 0.8, '////', '610  storage die (L2 / L3)'), ('tiles', 0.45, HATCH['tile'], '302'), ('plate', 0.8, HATCH['sink'], '208')])
    ax.add_patch(FancyArrowPatch((5, 0.9), (5, 4.0), arrowstyle='->', mutation_scale=14, lw=2.0))
    ax.text(0.2, 4.35, 'ALL of the compute die\'s heat crosses 610 (arrow)', fontsize=7.5)
    ax.text(0, -0.4, 'holding 610 at 280 K costs the whole die (99.3 W at every bond);\nan isolating bond takes the compute die\'s sink away', fontsize=7.2, va='top')
    ax = axes[1]; ax.set_title('(b) two-sided stack —\nMEASURED on its thermal side (§P0.37)', fontsize=8.5, fontweight='bold')
    stack(ax, 0, 0, 6, [('sink2', 0.7, '||||', '614  second sink, deliberately poor (~3 K/W)'), ('tiles2', 0.4, '++++', '612  storage array, 280 K'), ('stor', 0.7, '////', '610  storage die'), ('iso', 0.3, '', '620  isolating interface, ≤ 0.1 W/mK × 100 µm'),
                        ('src', 0.3, 'xxxx', '202  compute die, 110′ under 302'), ('si', 0.9, '', '204'), ('tiles', 0.4, HATCH['tile'], '302  dye tiles'), ('plate', 0.8, HATCH['sink'], '208')])
    ax.add_patch(FancyArrowPatch((5, 2.3), (5, 4.6), arrowstyle='->', mutation_scale=12, lw=1.6)); ax.add_patch(FancyArrowPatch((2, 1.7), (2, 0.2), arrowstyle='->', mutation_scale=10, lw=1.0))
    ax.text(0, -0.4, textwrap.fill('610 held at 280 K (282 K max) by 612 alone for 10.9–13.7 W (s 0.11–0.14; (a): 99.4 W), 302 at 0 W; '
                                   'leakage 3.5× down. Without 614 the unpowered 610 has NO steady state; a better 614 costs more '
                                   '(3 / 1 / 0.3 K/W: 13.7 / 20.1 / 39.8 W). Cr:LiSAF on 612: 1.7 W short.', 92), fontsize=7.0, va='top')
    ax = axes[2]; ax.set_title('(c) 2.5D placement — ARGUED', fontsize=8.5, fontweight='bold')
    stack(ax, 0, 0, 10, [('int', 0.6, '', '630  interposer')])
    stack(ax, 0.3, 0.6, 5.2, [('src', 0.35, 'xxxx', ''), ('si', 0.9, '', ''), ('tiles', 0.4, HATCH['tile'], ''), ('plate', 0.8, HATCH['sink'], '')])
    stack(ax, 6.3, 0.6, 3.4, [('stor', 0.9, '////', ''), ('tiles2', 0.4, '++++', ''), ('plate2', 0.8, HATCH['sink'], '')])
    ax.add_patch(Rectangle((5.5, 0.6), 0.8, 2.0, facecolor='white', edgecolor='black', lw=0.8, ls=(0, (3, 2))))
    ax.text(2.9, 3.4, 'compute die 100 + tiles 302 + plate 208', ha='center', fontsize=7.5); ax.text(8.0, 3.2, 'storage die 610\n+ tiles 612 + sink 614', ha='center', fontsize=7.5); ax.text(5.9, 3.9, '632\nisolating\nchannel', ha='center', fontsize=6.8)
    fig.text(0.04, 0.2, textwrap.fill('FIG. 6 — Gen 3: collecting the cache prize (leakage 2.7× / 3.6× down at 300 / 280 K; the knee at 280 K, barely sub-ambient — MEASURED). (a) With the storage '
                                      'die 610 between the compute die and the sink, all of the compute die\'s heat crosses it and holding it cold costs the whole die at every bond conductivity: '
                                      'MEASURED and falsified. (b) The surviving form: the storage die on the compute die\'s far face behind an interface 620 that conducts only laterally, its '
                                      'own array 612 and a deliberately poor sink 614; the compute face keeps the dye array 302 and cold plate 208. MEASURED 19 Sep (§P0.37, 100 µm cells): behind '
                                      '100 µm of 0.025–0.1 W/mK the storage die is held at the 280 K knee by its own dye array for 10.9–13.7 W with the compute array at 0 W — a ninth of (a) — and the '
                                      'cost rises linearly with the interface\'s conductance (26 W at 0.5, 75 W at 5 W/mK) and with the far-face sink\'s; without that sink the unpowered storage die '
                                      'runs away. Cr:LiSAF tiles (ceiling, η_EQE = 1) fall 1.7 W short and land the zone at 290 K (2.9× of the 3.5× leakage prize); the laser still draws 2.5× the '
                                      'leakage it saves — and that leakage DEPENDS ON THE MEMORY\'S CELL CLASS: these are HP-class bitcells; with low-standby-power cells it is 306× smaller (§P0.40). Where a cold '
                                      'memory zone pays (cell class, capacity, neighbour temperature, DRAM) is being mapped (§P0.42); proximity to the cores is a second motive. The interface itself (vias through an isolating gap) is ARGUED. (c) The same principle as a 2.5D placement on an interposer 630 with an '
                                      'isolating channel 632 — ARGUED.', 185), fontsize=8, va='top')
    figlabel(fig, 6)
    fig.savefig(os.path.join(OUT, 'pat_fig6.png')); plt.close(fig)
    LEGEND[6] = [(610, 'storage die (L2 / L3 caches)'), (612, 'storage-side array (dye: MEASURED to hold 280 K; Cr:LiSAF: ceiling, 1.7 W short)'), (614, 'second sink, storage side, deliberately poor (~3 K/W)'), (620, 'bond / isolating interface'), (630, 'interposer'), (632, 'isolating channel')]


def fig7_composite():
    """FIG. 7: the evolved core composed — plan view (real geometry) and section."""
    cb = core_blocks('d1_exec0.125_compact' if os.path.isdir(os.path.join(FLP, 'd1_exec0.125_compact')) else 'd1_exec0.125')
    fig = plt.figure(figsize=(13, 8.2))
    ax = fig.add_axes([0.03, 0.36, 0.46, 0.6]); clean(ax)
    bx = draw_core(ax, cb, label_blocks=True, lw=0.7)
    X, Y, W, H = block_rect(cb, 'cALU'); Xf, Yf, Wf, Hf = block_rect(cb, 'FPUs'); Xa, Ya, Wa, Ha = block_rect(cb, 'AVXs')
    cx0, cy0 = min(X, Xf, Xa) - 40, min(Y, Yf, Ya) - 40; cx1, cy1 = max(X + W, Xf + Wf, Xa + Wa) + 40, max(Y + H, Yf + Hf, Ya + Ha) + 40
    gx0 = int(cx0 // 200) * 200; gy0 = int(cy0 // 200) * 200
    gx = gx0
    while gx < cx1:
        gy = gy0
        while gy < cy1:
            x_a, y_a = max(gx, 0), max(gy, 0); x_b, y_b = min(gx + 200, bx[2]), min(gy + 200, bx[3])
            if x_b > x_a and y_b > y_a:
                ax.add_patch(Rectangle((x_a, y_a), x_b - x_a, y_b - y_a, facecolor='none', edgecolor='black', lw=1.0, ls=(0, (3, 2))))
            gy += 200
        gx += 200
    ax.add_patch(Rectangle((cx0, cy0), cx1 - cx0, cy1 - cy0, facecolor='none', edgecolor='black', lw=1.4))
    # caches marked as moved to the storage die: overlay hatch box
    for nm in ('L2', 'L3'):
        x, y, w, h = block_rect(cb, nm)
        ax.add_patch(Rectangle((x, y), w, h, facecolor='none', edgecolor='black', lw=1.2, ls=(0, (1, 1))))
    ax.set_xlim(bx[0] - 150, bx[2] + 150); ax.set_ylim(bx[1] - 100, bx[3] + 150)
    numeral(ax, "110′", ((cx0 + cx1) / 2, cy1), ((cx0 + cx1) / 2, bx[3] + 90), ha='center')
    numeral(ax, '302', (gx0 + 100, cy0), (gx0 - 250, bx[1] - 40), ha='center')
    x, y, w, h = block_rect(cb, 'L2'); numeral(ax, '610 (moved)', (x + w / 2, y + h / 2), (x + w / 2, bx[1] - 40), ha='center')
    ax.text(bx[0], bx[3] + 110, '100′ — the evolved core in plan (8× COMPACT cluster shown; drawn from its floorplan)', fontsize=8)
    ax2 = fig.add_axes([0.52, 0.36, 0.47, 0.6]); clean(ax2)
    tops = stack(ax2, 0, 0, 7, [('sink2', 0.6, '||||', '614'), ('tiles2', 0.35, '++++', '612  storage array, 280 K'), ('stor', 0.6, '////', '610  storage die: L2 / L3'), ('iso', 0.25, '', '620  isolating interface'),
                                ('src', 0.3, '', '202  compute die'), ('beol', 0.5, '', '400 / 402  rails, widened over 110′'), ('si', 0.9, '', '204  d ≈ 5–20 µm'), ('tiles', 0.4, '', '302  tiles at pitch p matched to 110′'), ('plate', 0.8, HATCH['sink'], '208 + 210')])
    ax2.add_patch(Rectangle((2.8, tops['src'][0]), 1.4, 0.3, facecolor='white', edgecolor='black', hatch='xxxx'))
    ax2.annotate('110′  (low-V_t cells 700: ARGUED)', xy=(4.2, tops['src'][0] + 0.15), xytext=(4.6, -1.0), fontsize=7, arrowprops=dict(arrowstyle='-', lw=0.6))
    yb0, yb1 = tops['beol']
    for x_, w_ in ((0.4, 0.1), (1.2, 0.1), (2.0, 0.1), (5.2, 0.1), (6.0, 0.1)):
        ax2.add_patch(Rectangle((x_, yb0 + 0.08), w_, yb1 - yb0 - 0.16, facecolor='black'))
    for x_ in (2.9, 3.4, 3.9):
        ax2.add_patch(Rectangle((x_, yb0 + 0.08), 0.28, yb1 - yb0 - 0.16, facecolor='black'))
    y0, y1 = tops['tiles']
    for i in range(7):
        on = i in (3, 4)
        ax2.add_patch(Rectangle((i + 0.04, y0), 0.92, y1 - y0, facecolor='white', edgecolor='black', lw=LW, hatch=HATCH['tile'] if on else ''))
    ax2.add_patch(Rectangle((0.0, -1.75), 4.3, 1.15, facecolor='white', edgecolor='black', lw=1.0))
    ax2.text(2.15, -1.17, '310  controller\n312 sense → 314 plan → 316 drive\n410: T* on the lifetime budget', ha='center', va='center', fontsize=6.8)
    ax2.add_patch(FancyArrowPatch((0.0, -1.2), (-0.45, -1.2), arrowstyle='-', lw=0.7)); ax2.add_patch(FancyArrowPatch((-0.45, -1.2), (-0.45, y0 + 0.2), arrowstyle='-', lw=0.7)); ax2.add_patch(FancyArrowPatch((-0.45, y0 + 0.2), (0.04, y0 + 0.2), arrowstyle='->', mutation_scale=9, lw=0.7))
    ax2.set_xlim(-0.8, 12.5); ax2.set_ylim(-1.9, 5.5)
    ax2.text(3.5, 5.2, 'section B–B′ (not to scale)', ha='center', fontsize=8)
    fig.text(0.03, 0.28, textwrap.fill('FIG. 7 — The core evolved in response to localized, high-power-density cooling — all measured and argued changes composed. Plan: the execution cluster 110′ '
                                       'densified 2–16× at unchanged power under tiles 302 at a pitch matched to it; the caches 120 / 122 relocated to a storage die 610 (dotted). Section B–B′: '
                                       'the compute die with rails 402 widened over the cluster, the tile array 302 within microns of the transistors (204), the controller 310 holding the '
                                       'target 410 on the lifetime budget, low-V_t cells 700 only where cooled (ARGUED), and the storage die 610 on the far face behind an isolating interface '
                                       '620 with its own array 612 and a deliberately poor sink 614 (MEASURED on the thermal side, §P0.37: 280 K for 10.9–13.7 W with the compute array untouched; the '
                                       'interface\'s construction ARGUED; the sink-side form measured and falsified). MEASURED elements: 110′ to 16× (§P0.32, '
                                       '§P0.34), 302 and 310 (the rescue ladder), 402 as a current density (X1), 410 (§P0.31), the cache knee at 280 K (D3).', 185), fontsize=8, va='top')
    figlabel(fig, 7)
    fig.savefig(os.path.join(OUT, 'pat_fig7.png')); plt.close(fig)
    LEGEND[7] = [("100′", 'the evolved core'), (700, 'low-threshold cells restricted to the cooled cluster (ARGUED)')]


def fig9_shape_rule():
    """FIG. 9: compact to ~8x, perimeter beyond it -- three details drawn from the real floorplans."""
    fig, axes = plt.subplots(1, 4, figsize=(19, 7.4))
    fig.subplots_adjust(wspace=0.08, bottom=0.27, top=0.92)
    panels = [('d1_exec0.125_compact', '(a) 8× cluster, COMPACT block 902', 'MEASURED: 0.94 / 0.85 of the strip layout\'s plan at 162 / 202 W;\ngains the 243 W rung at 200 µm pitch (s 0.98)'),
              ('d1_exec0.0625_compact', '(b) 16× cluster, COMPACT block 902′', 'MEASURED: no steady state at 162 and 202 W — 0 tiles capped,\nunchanged without the 45 K lift and under either material: TRANSPORT'),
              ('d1_exec0.0625', '(c) 16× cluster, the tiler\'s STRIPS 904', 'MEASURED: held to 202 W (s 0.88) at 100 µm pitch; 243 W lost.\nThe two ALUs are adjacent; the peak block is the bus strip beside them'),
              ('d1_exec0.03125_finger', '(d) 32× cluster as DESIGNED FINGERS 906', 'MEASURED: every rung held to 243 W at 32× (s 0.85) and at 16× (s 0.76),\n0 tiles capped, 0.74–0.79× the strips\' plan; the 32× strips lose 202 W')]
    pitch = 100.0
    for ax, (m, title, note) in zip(axes, panels):
        clean(ax)
        cb = core_blocks(m)
        draw_core(ax, cb, label_blocks=False, lw=0.7)
        rects = [block_rect(cb, n) for n in ('cALU', 'iALU', 'FPUs', 'AVXs')]
        cx0 = min(r[0] for r in rects) - 30; cy0 = min(r[1] for r in rects) - 30
        cx1 = max(r[0] + r[2] for r in rects) + 30; cy1 = max(r[1] + r[3] for r in rects) + 30
        side = max(cx1 - cx0, cy1 - cy0) + 2.2 * pitch
        cxm, cym = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        gx = int((cxm - side / 2) // pitch) * pitch
        while gx < cxm + side / 2:
            gy = int((cym - side / 2) // pitch) * pitch
            while gy < cym + side / 2:
                ax.add_patch(Rectangle((gx, gy), pitch, pitch, facecolor='none', edgecolor='black', lw=0.8, ls=(0, (3, 2))))
                gy += pitch
            gx += pitch
        ax.add_patch(Rectangle((cx0, cy0), cx1 - cx0, cy1 - cy0, facecolor='none', edgecolor='black', lw=1.6))
        for nm, num in (('cALU', 112), ('iALU', 114), ('FPUs', 116), ('AVXs', 118)):
            bx_, by_, bw_, bh_ = block_rect(cb, nm)
            ax.annotate(str(num), xy=(bx_ + bw_ / 2, by_ + bh_ / 2), xytext=(cxm + side / 2 - 0.1 * side, by_ + bh_ / 2), fontsize=7.5, va='center',
                        arrowprops=dict(arrowstyle='-', lw=0.5), bbox=dict(facecolor='white', edgecolor='none', pad=0.6))
        ax.set_xlim(cxm - side / 2, cxm + side / 2); ax.set_ylim(cym - side / 2, cym + side / 2)
        ax.set_title(title, fontsize=9.5, fontweight='bold')
        ax.text(0.0, -0.04, note, transform=ax.transAxes, fontsize=7.6, va='top')
    fig.text(0.04, 0.14, textwrap.fill('FIG. 9 — The shape of a densified execution cluster is a design variable (tiles 302 at 100 µm pitch dashed; all drawn from the floorplans; same unit areas, '
                                       'powers and die area within each density). (a) To about 8× (a ~230 W/mm² complex ALU) the units are best grouped into one compact block 902 under a few tiles: '
                                       'cheaper than strips and one rung higher. (b) At 16× (460 W/mm²) the compact block 902′ has no steady state above 121 W of die power with no tile capped — the '
                                       'wall does not move at 5 µm burial and moves one rung (162 W) with a 50 µm tile of a cold-tolerant film (§P0.38): transport and tile resolution. (c) The same 16× units as the slicing tiler '
                                       'leaves them — high-aspect strips 904, the two ALUs adjacent — are held to 202 W. (d) The DESIGNED form 906: one execution column, every execution unit a '
                                       'full-width strip with scheduler / register-file logic on both sides, hot strips 140–270 µm apart under their own tiles: every rung to 243 W at 16× and at 32×. '
                                       'Past ~8× the units want cool neighbours at the tile pitch, not compaction. MEASURED, §P0.36 / §P0.38 (per-block planner, 20 µm burial, 50 µm cells; strips are '
                                       'one cell tall in (c) and (d) alike, so (c)-vs-(d) is like for like; the compact unit is 0.4 of a cell — its losses are firm, its holds lower bounds).', 225), fontsize=8, va='top')
    figlabel(fig, 9)
    fig.savefig(os.path.join(OUT, 'pat_fig9.png')); plt.close(fig)
    LEGEND[9] = [(902, 'compact execution cluster (the four units in one near-square block)'), (904, 'execution units as the slicing tiler\'s high-aspect strips'), (906, 'execution units as DESIGNED fingers, interdigitated with scheduler / register-file logic at the tile pitch')]


def fig8_ladder():
    """FIG. 8: the argument — one architectural change per measured constraint."""
    fig, ax = plt.subplots(figsize=(15, 7.6)); clean(ax)
    cols = ['generation', 'binding constraint (from the solve)', 'what the cooler removes', 'architectural response', 'what binds next']
    rows = [('gen 0\nconventional', 'leakage runaway through the hottest\ncALU; 0.60–0.65 W/mm² shaped,\n0.85–0.90 flat; the traced die has\nno steady state on its package', '—', 'spread the execution units out\n(concentration costs 1.4× of ceiling)', 'the runaway', 'M'),
            ('gen 1\ndriven array', 'the stability boundary', 'the runaway first, then rungs\nto 3.50 W/mm² (conservation);\n12 → 114 W at 1.20 → 2.00', 'densify the execution cluster\n2× / 4× under the tiles (D1):\nheld to 243 / 202 W', 'the rails: 1.5–3× the native\ncurrent; cALU 2× / 4× that (X1)', 'M'),
            ('gen 1′\n8× / 16×', 'a 230–460 W/mm² unit: the tile\nmust resolve it, and the dye\'s\ncold end caps the top rung', 'with a cold-tolerant hot-zone\nmaterial the 8× holds 243 W\n(s 0.88); dual layout suffices', 'COMPACT cluster to ~8× (cheaper,\n+1 rung); FINGERS beyond it;\npitch ~100 µm; rails ~J×; T* budget', 'transport: a compact 460 W/mm²\ncluster has no steady state\nabove 121 W (nothing capped)', 'M'),
            ('gen 2\ndevice headroom', 'the clock: with wire, skew and\noverhead the 92 °C ceiling is\n3.76 GHz, TDDB-limited', 'each 30 K of target buys\n~6 % of supply (4.08 GHz at\n60 °C for 104 W)', 'low-V_t cells only where cooled\n(+7.6 % per 25 mV); re-pipeline\nfor clock (10 GHz needs 6–7 FO4)', 'the laser budget; with a short\npipeline the cooler binds again\n(5.75 GHz at 283 W)', 'A'),
            ('gen 3\nstorage die', 'cache leakage: the prize saturates\nby 280 K (2.23×); on the compute\ndie or in its heat path it costs\nthe whole die', 'the storage die\'s own 1.35 W\n(Cr:LiSAF tiles)', 'the storage die OFF the heat\npath: two-sided stack or 2.5D', 'interface isolation, two-sided\npackaging — not thermal', 'A')]
    x0 = [0.0, 1.7, 5.2, 8.6, 12.0]; wcol = [1.6, 3.4, 3.3, 3.3, 3.3]
    for j, c in enumerate(cols):
        ax.text(x0[j] + wcol[j] / 2, 6.55, c, ha='center', va='center', fontsize=8.5, fontweight='bold')
    for i, row in enumerate(rows):
        y = 5.6 - i * 1.3
        tag = row[-1]
        for j, txt in enumerate(row[:-1]):
            ax.add_patch(Rectangle((x0[j], y - 0.58), wcol[j], 1.16, facecolor='white', edgecolor='black', lw=1.1 if tag == 'M' else 0.8, ls='-' if tag == 'M' else (0, (4, 2))))
            ax.text(x0[j] + 0.08, y, txt, va='center', fontsize=6.6 if j else 7.5, fontweight='bold' if j == 0 else 'normal')
        if i < len(rows) - 1:
            ax.add_patch(FancyArrowPatch((x0[4] + wcol[4] / 2, y - 0.58), (x0[0] + wcol[0] / 2, y - 0.72), arrowstyle='->', mutation_scale=10, lw=0.8, connectionstyle='arc3,rad=0.0', alpha=0.0))
            ax.add_patch(FancyArrowPatch((x0[0] + wcol[0] / 2, y - 0.58), (x0[0] + wcol[0] / 2, y - 0.72), arrowstyle='->', mutation_scale=12, lw=1.0))
    ax.text(0, -1.05, 'solid border: MEASURED (a solved result with a JSON behind it); dashed: ARGUED on measured inputs. The ladder ends where its constraint stops being thermal.', fontsize=7.5)
    ax.set_xlim(-0.2, 15.5); ax.set_ylim(-1.3, 7.0)
    figlabel(fig, 8)
    fig.savefig(os.path.join(OUT, 'pat_fig8.png')); plt.close(fig)
    LEGEND[8] = []


def fig10_memory_die():
    """FIG. 10: the DRAM / HBM die beside, under and on top of the compute die -- MEASURED (§P0.44)."""
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.4), gridspec_kw={'width_ratios': [1.15, 1.0, 1.0]})
    fig.subplots_adjust(wspace=0.12, bottom=0.36, top=0.88, left=0.03, right=0.99)
    for ax, xmax in zip(axes, (12.5, 11.5, 11.5)):
        clean(ax); ax.set_xlim(-0.3, xmax); ax.set_ylim(-1.8, 7.6)
    # (a) beside -- 2.5D
    ax = axes[0]; ax.set_title('(a) memory die 710 BESIDE the compute die (2.5D) —\nMEASURED: thermally free', fontsize=8.5, fontweight='bold')
    stack(ax, 0, 0, 10.6, [('int', 0.6, '', '630  interposer')])
    stack(ax, 0.3, 0.6, 5.0, [('src', 0.35, 'xxxx', ''), ('si', 0.9, '', ''), ('tiles', 0.4, HATCH['tile'], ''), ('plate', 0.8, HATCH['sink'], '')])
    stack(ax, 6.0, 0.6, 4.6, [('mem', 0.9, '\\\\', ''), ('tiles2', 0.4, HATCH['tile'], ''), ('plate2', 0.8, HATCH['sink'], '')])
    ax.add_patch(Rectangle((5.3, 0.6), 0.7, 0.9, facecolor='white', edgecolor='black', lw=0.8, ls=(0, (3, 2))))
    ax.text(2.8, 3.3, 'compute die 100 + tiles 302 + plate 208', ha='center', fontsize=7.5); ax.text(8.3, 3.3, 'memory die 710 (DRAM / HBM)\n+ tiles 712 + plate 208', ha='center', fontsize=7.5); ax.text(5.65, 1.9, 'gap\n720', ha='center', fontsize=6.8)
    ax.text(0, -0.4, textwrap.fill('plan 123 W against the 126 W reference (−2.5 %), 0 W on the memory\'s tiles; banks 27–30 °C at every gap from 0.5 to 2 mm (2.6 K apart). One silicon slab in the model (lateral coupling an upper bound); the shared base\'s warming by the memory\'s 24 W (~1.8 K) is not in it.', 100), fontsize=7.0, va='top')
    # (b) far face
    ax = axes[1]; ax.set_title('(b) memory die 710 on the compute die\'s FAR FACE —\nMEASURED: −6 to +16 W by its own heat path', fontsize=8.5, fontweight='bold')
    stack(ax, 0, 0, 6, [('sink2', 0.7, '||||', '714  far-face path, 1 / 3 / 10 K/W'), ('tiles2', 0.4, '++++', '712  memory-side array (never needed)'), ('mem', 0.8, '\\\\', '710  memory die, 8 × 3 W, 27–70 °C'), ('iso', 0.3, '', '722  via-field interface, k_eff ≈ 0.85 W/mK'),
                        ('src', 0.3, 'xxxx', '202  compute die, 92 °C'), ('si', 0.9, '', '204'), ('tiles', 0.4, HATCH['tile'], '302  dye tiles'), ('plate', 0.8, HATCH['sink'], '208')])
    ax.add_patch(FancyArrowPatch((5, 2.3), (5, 4.6), arrowstyle='->', mutation_scale=12, lw=1.6)); ax.add_patch(FancyArrowPatch((2, 2.0), (2, 0.2), arrowstyle='->', mutation_scale=10, lw=1.0)); ax.add_patch(FancyArrowPatch((3.5, 1.6), (3.5, 2.4), arrowstyle='<->', mutation_scale=9, lw=0.9))
    ax.text(0, -0.4, textwrap.fill('Plan 120.0 / 132.4 / 141.6 W with the far-face path at 1 / 3 / 10 K/W (−6 / +6 / +16 W): at 1 K/W the far-face path takes compute heat too; at 3–10 K/W the memory\'s heat enters the compute die through 722 and leaves through 302. Banks 47 / 59 / 67 °C. Behind an aerogel-class 722 (0.1 W/mK) with a 10 K/W path: NO steady state (refresh runaway). The DRAM die wants the via field\'s conductance that the cache die of FIG. 6b did not.', 92), fontsize=7.0, va='top')
    # (c) sink-side (memory on logic)
    ax = axes[2]; ax.set_title('(c) memory die 710 ON TOP of the compute die (memory-on-logic) —\nMEASURED: 0 W for one die, +40 W or no hold for 8-high', fontsize=8.5, fontweight='bold')
    stack(ax, 0, 0, 6, [('sub', 0.5, '', '200'), ('src', 0.3, 'xxxx', '202  compute die'), ('si', 0.9, '', ''), ('bond', 0.25, '....', '620  bond, 50 or 5 W/mK'),
                        ('mem', 1.2, '\\\\', '710  memory die / 8-high stack, 40–50 °C'), ('tiles', 0.45, HATCH['tile'], '302'), ('plate', 0.8, HATCH['sink'], '208')])
    ax.add_patch(FancyArrowPatch((5, 0.9), (5, 4.4), arrowstyle='->', mutation_scale=14, lw=2.0))
    ax.text(0.2, 4.75, 'ALL of the compute die\'s heat crosses 710 (arrow)', fontsize=7.5)
    ax.text(0, -0.4, textwrap.fill('One 50 µm die: 126.1 W on a 50 W/mK bond (+0.0), 133.6 W on 5 W/mK (+7.5); an 8-high stack (435 µm lumped, series-equivalent 108 / 42 W/mK): 166.5 W on hybrid bonds (+40), NO steady state on microbumps — and 35 W at 1.00 W/mm² where the reference needs none. The stack\'s series resistance in the compute die\'s only heat path is the cost; the banks sit 45 K under the hot spot.', 92), fontsize=7.0, va='top')
    fig.text(0.04, 0.2, textwrap.fill('FIG. 10 — The memory die as a DRAM / HBM die, three placements, MEASURED 27 Oct (§P0.44; 100 µm cells, dye tiles, 8 dies × 3 W lumped, refresh feedback in the loop, planned at 80 °C under the 85 °C breakpoint, '
                                      'reference plan 126.1 W at 2.00 W/mm²). In every stacked placement the banks sit at the die\'s AREA-AVERAGE temperature, 25–45 K below the compute die\'s hot spot, and the 85 °C line never binds: '
                                      'the memory\'s own temperature is not the design variable — its HEAT PATH is. (a) Beside the compute die the memory is thermally free and the gap does not matter. (b) On the far face the cost is set by the memory\'s own exit: '
                                      'a good far-face path (1 K/W) pays the compute array back, a poor one (10 K/W) sends the memory\'s heat through the compute die; the via-field interface 722 is what the memory die WANTS (the cache die of FIG. 6b wanted an isolating one). '
                                      '(c) On top of the compute die the cost is the stack\'s series resistance in the compute die\'s only path to its cooler: nothing for one thin hybrid-bonded die, a third of the plan for an eight-high stack on hybrid bonds, no steady state on microbumps. '
                                      'Read with §P0.43 (memory under the cores is worth +1–6 % over 2.5D): the far-face form is the only 3D placement whose cooling cost is of the order of its throughput gain. The DRAM power model is a JEDEC convention (UNCALIBRATED): quote placements and heat paths, not memory watts. '
                                      'ARGUED: the far-face path\'s construction, the via field\'s electrical function, the interposer (one slab here), an eight-high stack die by die.', 185), fontsize=8, va='top')
    figlabel(fig, 10)
    fig.savefig(os.path.join(OUT, 'pat_fig10.png')); plt.close(fig)
    LEGEND[10] = [(710, 'memory die (DRAM / HBM; 8 dies lumped)'), (712, 'memory-side array (never engaged in a held row)'), (714, 'far-face heat path of stated K/W'), (720, 'gap on the interposer'), (722, 'via-field interface, k_eff stated'), (630, 'interposer'), (620, 'bond')]


def write_legend():
    lines = ['# Reference numerals in the patent-style figures (FIG. 1–9, 3B, 3C)', '',
             '| numeral | element | first figure |', '|---|---|---|']
    seen = set()
    for f in sorted(LEGEND, key=lambda k: (int(str(k).rstrip('BC')), str(k))):
        for num, meaning in LEGEND[f]:
            if num in seen:
                continue
            seen.add(num)
            lines.append('| %s | %s | FIG. %s |' % (num, meaning, f))
    with open(os.path.join(OUT, 'patent_figure_legend.md'), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    fig1_conventional_core(); fig2_apparatus(); fig3_densified_cluster(); fig3_densified_cluster(compact=True); fig3_densified_cluster(finger=True); fig4_rails_and_budget()
    fig5_pitch_and_film(); fig6_storage_die(); fig7_composite(); fig8_ladder(); fig9_shape_rule(); fig10_memory_die(); write_legend()
    print('written:', sorted(f for f in os.listdir(OUT) if f.startswith('pat_')))
