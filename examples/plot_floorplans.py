#!/usr/bin/env python
"""Render the generated N-core floorplans, and the power density landing on them.

Two panels per floorplan:

* **Block map** -- every floorplan element drawn to scale, coloured by unit type. Shows the
  tiling and how much of the die each functional unit actually occupies.
* **Power density** -- the same blocks shaded by W/mm^2 once a trace has been scaled onto them.
  This is the panel that matters for microrefrigeration: it shows *where* the heat is, and the
  answer is a small number of very hot functional units, not a warm die.

The density scale is deliberately logarithmic. On a linear scale the hotspots saturate and
everything else reads as zero, which is exactly the coarse-graining mistake the SimScale
comparison is about -- die-average, core-average and hotspot densities differ by two orders of
magnitude on the same chip.

Usage
-----
    python examples/plot_floorplans.py --cores 34 70 128 --power 200 --out-dir plots
"""
import os
import sys
import json
import argparse

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.colors import LogNorm, Normalize

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power import BasicPowerTrace
from HotGauge.configuration import load_block_powers
from HotGauge.thermal.ICE import Floorplan
from HotGauge.thermal.leakage_feedback import (scale_trace_to_die_power, replicate_trace_cores,
                                               prepare_dice_trace)

#: Unit-type groupings, so a 128-core map reads as structure rather than confetti.
_GROUPS = (
    ('Execution', ('iALU', 'cALU', 'FPUs', 'AVXs', 'AVX_FPU')),
    ('Scheduling', ('IW', 'fpIWin', 'ROB', 'RAT', 'RNU', 'BPT', 'BTB')),
    ('Register files', ('iRF', 'fpRF')),
    ('Load/store', ('LdStQ', 'StQ', 'LdQ', 'DTLB', 'ITLB', 'MMU')),
    ('Caches', ('L1', 'L2', 'L3', 'dcache', 'icache')),
    ('Uncore', ('IMC', 'SoC', 'IO', 'NUCA', 'BUSES')),
)
_GROUP_COLORS = ('#B05924', '#2C4A6E', '#4E7C6B', '#7A5B8E', '#3D6E8F', '#8A8F98')


def _group_of(name):
    base = name.rsplit('_', 1)[0]
    for i, (label, prefixes) in enumerate(_GROUPS):
        for p in prefixes:
            if base == p or base.startswith(p):
                return i, label
    return len(_GROUPS), 'Other'


def _extent(flp):
    xs = [e.minx for e in flp.elements] + [e.maxx for e in flp.elements]
    ys = [e.miny for e in flp.elements] + [e.maxy for e in flp.elements]
    return min(xs), max(xs), min(ys), max(ys)


def plot_block_map(flp, ax, title):
    """Every element to scale, coloured by unit-type group."""
    seen = {}
    for e in flp.elements:
        gi, label = _group_of(e.name)
        color = (_GROUP_COLORS + ('#B8BCC4',))[min(gi, len(_GROUP_COLORS))]
        seen.setdefault(label, color)
        ax.add_patch(Rectangle((e.minx / 1000.0, e.miny / 1000.0),
                               e.width / 1000.0, e.height / 1000.0,
                               facecolor=color, edgecolor='white', linewidth=0.12))
    x0, x1, y0, y1 = _extent(flp)
    ax.set_xlim(x0 / 1000.0, x1 / 1000.0)
    ax.set_ylim(y0 / 1000.0, y1 / 1000.0)
    ax.set_aspect('equal')
    ax.set_xlabel('mm')
    ax.set_ylabel('mm')
    ax.set_title(title, fontsize=11, loc='left')
    handles = [Rectangle((0, 0), 1, 1, facecolor=c) for c in seen.values()]
    ax.legend(handles, list(seen.keys()), fontsize=7, loc='upper left',
              bbox_to_anchor=(1.01, 1.0), frameon=False)
    return ax


def plot_power_density(flp, powers, ax, title, vmin=None, vmax=None):
    """Blocks shaded by W/mm^2 on a log scale, with the hottest block annotated."""
    dens = {}
    for e in flp.elements:
        p = powers.get(e.name)
        if p is None:
            continue
        area_mm2 = (e.width * e.height) / 1.0e6
        if area_mm2 > 0:
            dens[e.name] = float(np.ravel(p).sum()) / area_mm2
    if not dens:
        raise ValueError('no trace power landed on {}'.format(title))

    vals = np.array(list(dens.values()))
    pos = vals[vals > 0]
    vmin = vmin or max(pos.min(), pos.max() / 1e3)
    vmax = vmax or pos.max()
    norm = LogNorm(vmin=vmin, vmax=vmax)
    cmap = plt.get_cmap('inferno')

    hottest, hot_d = None, -1.0
    for e in flp.elements:
        d = dens.get(e.name, 0.0)
        color = cmap(norm(d)) if d > vmin else cmap(0.0)
        ax.add_patch(Rectangle((e.minx / 1000.0, e.miny / 1000.0),
                               e.width / 1000.0, e.height / 1000.0,
                               facecolor=color, edgecolor='none'))
        if d > hot_d:
            hottest, hot_d = e, d

    x0, x1, y0, y1 = _extent(flp)
    ax.set_xlim(x0 / 1000.0, x1 / 1000.0)
    ax.set_ylim(y0 / 1000.0, y1 / 1000.0)
    ax.set_aspect('equal')
    ax.set_xlabel('mm')
    ax.set_title(title, fontsize=11, loc='left')
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = ax.figure.colorbar(sm, ax=ax, fraction=0.045, pad=0.02)
    cb.set_label('W/mm$^2$', fontsize=8)
    cb.ax.tick_params(labelsize=7)
    if hottest is not None:
        ax.plot(hottest.minx / 1000.0 + hottest.width / 2000.0,
                hottest.miny / 1000.0 + hottest.height / 2000.0,
                marker='o', ms=5, mfc='none', mec='#5BE8FF', mew=1.2)
    return dens, hottest, hot_d


def density_stats(flp, dens, total_W):
    """Die-average, core-average and peak density -- the coarse-graining ladder."""
    die_mm2 = sum((e.width * e.height) / 1.0e6 for e in flp.elements)
    hot = max(dens.values()) if dens else float('nan')
    ranked = sorted(dens.values(), reverse=True)
    top1pct = ranked[:max(1, len(ranked) // 100)]
    return {'die_mm2': die_mm2, 'die_avg': total_W / die_mm2,
            'peak': hot, 'top1pct_avg': float(np.mean(top1pct)),
            'ratio': hot / (total_W / die_mm2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, nargs='+', default=[8, 34, 70, 128])
    ap.add_argument('--flp-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--node', default='7nm')
    ap.add_argument('--trace-dir', default=os.path.join(_REPO, 'mcpat_runs', '7nm',
                                                        'linpack_3.8GHz'))
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--power', type=float, default=200.0)
    ap.add_argument('--trace-cores', type=int, default=8)
    ap.add_argument('--out-dir', default=os.path.join(os.getcwd(), 'plots'))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    files = load_block_powers(args.trace_dir)
    with open(files[0]) as f:
        first = {u: float(np.ravel(v)[0]) for u, v in json.load(f).items()}
    base0 = BasicPowerTrace({u: np.array([p]) for u, p in first.items()}, 1.0)

    rows = []
    for n in args.cores:
        stem = 'skylake{}_{}core_{}_3D-ICE_template.flp'.format(
            args.node, n, 0 if n == 7 else 3)
        path = os.path.join(args.flp_dir, stem)
        if not os.path.isfile(path):
            alt = os.path.join(args.flp_dir, stem.replace('_3_', '_0_'))
            path = alt if os.path.isfile(alt) else path
        if not os.path.isfile(path):
            print('  skip {}-core: no floorplan at {}'.format(n, path))
            continue

        flp = Floorplan.from_file(path)
        base = replicate_trace_cores(base0, n, n_src=args.trace_cores) \
            if n > args.trace_cores else base0
        trace, _, _ = scale_trace_to_die_power(base, path, args.tech_node, args.power,
                                               num_cores=n)
        dice = prepare_dice_trace(trace, path, args.tech_node, num_cores=n)
        powers = dice.powers if hasattr(dice, 'powers') else dice

        fig, axes = plt.subplots(1, 2, figsize=(14, 6.2))
        plot_block_map(flp, axes[0], '{}-core block map'.format(n))
        dens, hottest, hot_d = plot_power_density(
            flp, powers, axes[1],
            '{}-core power density at {:.0f} W'.format(n, args.power))
        st = density_stats(flp, dens, args.power)
        fig.suptitle('{}  --  {} blocks, {:.1f} mm$^2$'.format(
            os.path.basename(path), len(flp.elements), st['die_mm2']),
            fontsize=10, x=0.02, ha='left')
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        out = os.path.join(args.out_dir, 'floorplan_{}core.png'.format(n))
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)

        st.update({'cores': n, 'blocks': len(flp.elements),
                   'hottest': hottest.name if hottest else None, 'png': out})
        rows.append(st)
        print('  wrote {}'.format(out))

    print()
    hdr = '{:>6s} {:>8s} {:>10s} {:>11s} {:>11s} {:>10s} {:>8s}  {}'.format(
        'cores', 'blocks', 'area mm^2', 'die W/mm^2', 'top1% W/mm^2', 'peak', 'peak/avg',
        'hottest block')
    print(hdr)
    print('-' * len(hdr))
    for r in rows:
        print('{:>6d} {:>8d} {:>10.2f} {:>11.3f} {:>11.2f} {:>10.2f} {:>8.0f}x  {}'.format(
            r['cores'], r['blocks'], r['die_mm2'], r['die_avg'], r['top1pct_avg'],
            r['peak'], r['ratio'], r['hottest']))

    with open(os.path.join(args.out_dir, 'density_summary.json'), 'w') as f:
        json.dump(rows, f, indent=2)


if __name__ == '__main__':
    main()
