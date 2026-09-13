#!/usr/bin/env python
"""Build a self-contained HTML package of the QUOTABLE results, for a proposal.

    python scripts/build_proposal_pack.py            # -> proposal_pack_<date>/ and .zip
    python scripts/build_proposal_pack.py --out DIR

Everything in it is register §1 (docs/RESULTS_REGISTER.md) with its caveat, plus the argued
evolution ladder (docs/designs/EVOLUTION_LADDER.md) tagged MEASURED / ARGUED. Nothing from
register §2 is presented as a result; the withdrawn list is included as a guard page so the
proposal writer never re-imports one. Plots are rendered from the evidence JSONs in
docs/evidence/ (copied into the pack under evidence/), floorplan figures from
docs/designs/figures/ (our own renderings of our own floorplans -- the floorplan-pack plates
are third-party content and are NOT included). No external resources: the pack works offline
and survives scp/zip.
"""
import os
import re
import io
import sys
import json
import glob
import shutil
import argparse
import datetime
import subprocess
import html as _html

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')

# The reference data-viz palette (dataviz skill, references/palette.md): categorical slots in
# fixed order, text tokens, surface, hairline grid. Series colour never carries text.
C = {'s1': '#2a78d6', 's2': '#eb6834', 's3': '#1baf7a', 's4': '#eda100',
     'text': '#0b0b0b', 'text2': '#52514e', 'muted': '#8a8985', 'surface': '#fcfcfb',
     'grid': '#e9e8e4', 'band': '#f0efec'}
REF_MM2 = 101.09708
DT_DQ = 0.3247

plt.rcParams.update({
    'figure.facecolor': C['surface'], 'axes.facecolor': C['surface'],
    'axes.edgecolor': C['grid'], 'axes.linewidth': 0.8, 'axes.grid': True,
    'grid.color': C['grid'], 'grid.linewidth': 0.6, 'grid.linestyle': '-',
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.axisbelow': True,
    'xtick.color': C['text2'], 'ytick.color': C['text2'], 'axes.labelcolor': C['text2'],
    'text.color': C['text'], 'font.size': 10, 'axes.titlesize': 11, 'axes.titleweight': 'bold',
    'legend.frameon': False, 'lines.linewidth': 2.0, 'lines.markersize': 6,
    'savefig.dpi': 160, 'savefig.facecolor': C['surface'], 'savefig.bbox': 'tight'})


def J(name):
    p = name if os.path.isabs(name) else os.path.join(_EV, name)
    return json.load(open(p)) if os.path.isfile(p) else None


def esc(x):
    return _html.escape(str(x))


# ----------------------------------------------------------------------------------------------
# plots -- each returns (filename, caption) or None when its evidence is missing
# ----------------------------------------------------------------------------------------------
def plot_rescue_ladder(out):
    rows = []
    for f in sorted(glob.glob(os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00', 'd*',
                                           'mr_comparison.json'))):
        j = json.load(open(f))
        r = {x['arm']: x for x in j['rows']}
        on = r.get('array_on', {})
        rows.append({'d': j['density'], 'ctrl': not r.get('control', {}).get('diverged', True),
                     'idle': not r.get('array_idle', {}).get('diverged', True),
                     'on': (not on.get('diverged', True)) and bool(on.get('mr_plan_holds_target', True)),
                     'Q': on.get('heat_removed_W'), 'net': on.get('p_mr_net_W'),
                     'P': on.get('p_chip_W')})
    rows = [r for r in rows if r['d'] <= 2.6]
    if not rows:
        return None
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2))
    d = [r['d'] for r in rows if r['on'] and r['Q'] is not None]
    a.plot(d, [r['Q'] for r in rows if r['on'] and r['Q'] is not None], color=C['s1'], marker='o', label='heat removed by the array')
    a.plot(d, [r['net'] for r in rows if r['on'] and r['Q'] is not None], color=C['s2'], marker='o', label='net electrical cost (with recovery)')
    a.axvline(1.0, color=C['muted'], lw=1); a.axvline(1.2, color=C['muted'], lw=1)
    a.text(0.03, 0.62, 'control fails at 1.00\nunpowered array fails at 1.20', transform=a.transAxes, fontsize=8, color=C['text2'], va='top')
    a.axvspan(2.4, 2.6, color=C['band'])
    a.text(0.97, 0.05, 'conservation: 2.40 holds,\n2.60 is envelope only', transform=a.transAxes, ha='right', fontsize=8, color=C['text2'])
    a.set_xlabel('die power density, W/mm²'); a.set_ylabel('W'); a.set_title('The rescue ladder — 34-core die, arm D, 88 CFM')
    a.legend(loc='upper left', fontsize=8)
    s = [r['Q'] / r['P'] for r in rows if r['on'] and r['Q'] and r['P']]
    b.plot(d, s, color=C['s1'], marker='o')
    b.axhline(1.0, color=C['muted'], lw=1); b.text(0.03, 0.93, 's = 1: the array lifts all of the die\'s heat', transform=b.transAxes, fontsize=8, color=C['text2'])
    b.axhline(0.5, color=C['grid'], lw=1); b.text(0.55, 0.42, 's = 0.5: where v100 eq. (1.33)\ndoubles the hybrid cap', transform=b.transAxes, fontsize=8, color=C['text2'])
    b.set_xlabel('die power density, W/mm²'); b.set_ylabel('s = heat lifted / converged die power'); b.set_title("The array's share of the heat, s")
    fn = 'rescue_ladder.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3. Minimum plan that holds 92 °C at each rung; the control has no steady '
                'state above 1.00 and the unpowered array above 1.10. Quote the range and the cost '
                'ladder, never the top rung. Source: results/array_coverage_armD/c1.00 (arm D).')


def _ladder_rows(base):
    rows = []
    for f in sorted(glob.glob(os.path.join(base, '*', 'd*', 'probe.json'))):
        rows += json.load(open(f))['rows']
    return rows


def plot_density_ceilings(out):
    L = {'34-core, 50 µm': _ladder_rows(os.path.join(_REPO, 'results', 'uniform_density_armD')),
         '70-core, 100 µm': _ladder_rows(os.path.join(_REPO, 'results', 'uniform_density_70core_armD'))}
    if not L['34-core, 50 µm']:
        return None
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    col = {('34-core, 50 µm', 'uniform'): C['s1'], ('34-core, 50 µm', 'shaped'): C['s3'],
           ('70-core, 100 µm', 'uniform'): C['s2'], ('70-core, 100 µm', 'shaped'): C['s4']}
    for die, rows in L.items():
        for arm in ('uniform', 'shaped'):
            rr = sorted([r for r in rows if r['arm'] == arm], key=lambda r: r['density'])
            if not rr:
                continue
            held = [r for r in rr if not r['diverged']]
            fail = [r for r in rr if r['diverged']]
            c = col[(die, arm)]
            lab = '%s, %s map' % (die, 'flat (Gini 0)' if arm == 'uniform' else 'real (shaped)')
            ax.plot([r['density'] for r in held], [r['peak_C'] for r in held], color=c, marker='o', label=lab)
            if fail:
                ax.scatter([r['density'] for r in fail], [112] * len(fail), marker='x', color=c, s=40)
    ax.axhline(110, color=C['grid']); ax.text(0.02, 0.985, '× = no steady state (leakage runaway) at that rung', transform=ax.transAxes, va='top', fontsize=8, color=C['text2'])
    ax.set_xlabel('die power density, W/mm²'); ax.set_ylabel('peak temperature, °C (holding rungs)')
    ax.set_title('Where the uncooled die loses its steady state — two dies, two power maps')
    ax.legend(fontsize=8, loc='lower right'); ax.set_ylim(35, 118)
    fn = 'density_ceilings.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3 and §P0.22.1. Control arm, no array, arm D. The 34-core die holds 0.85 flat '
                '/ 0.60 shaped (1.4×); the 70-core die (196 mm², same base) holds 0.65 flat — the '
                'absolute ceiling moves with the package, the ratio and the cALU hot spot travel. '
                '70-core rows are at 100 µm cells beside a matched-grid 34-core control that moved '
                'neither cliff. Source: results/uniform_density_armD, results/uniform_density_70core_armD.')


def plot_cold_zone(out):
    c = J('cold_zone_prize_simulated.json')
    if not c:
        return None
    rows = sorted(c['rows'], key=lambda r: -r['T_cold_K'])
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for key, lab, col in (('simulated', 'simulated (BSIM-CMG, ASAP7)', C['s1']),
                          ('simulated-gidl-off', 'simulated, GIDL off (the other bracket)', C['s3']),
                          ('pipeline', 'the pipeline curve (CACTI; clamps below 300 K)', C['s2'])):
        ax.plot([r['T_cold_K'] for r in rows], [r[key]['leakage_reduction_x'] for r in rows], color=col, marker='o', label=lab)
    knee = c.get('saturation_knee_K')
    if knee:
        ax.axvline(knee, color=C['muted'], lw=1); ax.text(knee + 1, ax.get_ylim()[1] * 0.9, 'knee %d K: within 5 %% of the maximum prize' % knee, fontsize=8, color=C['text2'])
    ax.set_yscale('log'); ax.invert_xaxis()
    ax.set_xlabel('cache temperature, K (cooled from %d K)' % c['hot_baseline_K']); ax.set_ylabel('leakage reduction, × (log)')
    ax.set_title('Cooling the cache: leakage reduction vs. temperature'); ax.legend(fontsize=8)
    fn = 'cold_zone_prize.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.2. Quote the 2.23× improvement over the original curve and the 280 K knee, '
                'not a percentage of die power (accounting-dependent, ~14 % corrected). Sub-ambient '
                'values are a bracket (both GIDL settings). Source: docs/evidence/cold_zone_prize_simulated.json.')


def plot_cache_objective(out):
    d = J('d3_cache_objective.json')
    if not d or not d.get('points'):
        return None
    pts = {(p['variant'], p['density']): p for p in d['points']}
    order = [('peak', 'hot-spot objective\n(reference)'), ('dtnone_T300', 'caches at 300 K'),
             ('dtnone_T280', 'caches at 280 K'), ('dual_T280', 'caches at 280 K,\nCr:LiSAF on cache tiles')]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, dens in ((a, 1.0), (b, 0.6)):
        labs, share, leak = [], [], []
        for v, lab in order:
            p = pts.get((v, dens))
            if not p:
                continue
            labs.append(lab); share.append(100 * (p['plan_share_of_die'] or 0)); leak.append(p['cache_leakage_W'] or 0)
        x = np.arange(len(labs))
        ax.bar(x, share, width=0.55, color=C['s1'])
        for i, (s_, l_) in enumerate(zip(share, leak)):
            ax.text(i, s_ + 2, '%.0f %%\ncache leakage %.2f W' % (s_, l_), ha='center', fontsize=8, color=C['text2'])
        ax.set_xticks(x); ax.set_xticklabels(labs, fontsize=8)
        ax.set_ylabel('cooling plan, % of the die\'s own power'); ax.set_ylim(0, 130)
        ax.axhline(100, color=C['muted'], lw=1); ax.text(-0.4, 102, 'conservation: the whole die\'s heat', fontsize=8, color=C['text2'])
        ax.set_title('%.2f W/mm² (die %s W)' % (dens, '99' if dens == 1.0 else '60'))
    fig.suptitle('Holding the caches cold on the MONOLITHIC die: what the planner has to remove', fontweight='bold', y=1.02)
    fn = 'cache_objective.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.2, §P0.22.2. The cache-leakage planner objective on the 34-core die (arm D, '
                'target device): reaching the 280 K knee is conservation-bound; 300 K costs ≥ 77 % of die '
                'power (lower bound). The measured leg of the separate-die argument. Source: '
                'docs/evidence/d3_cache_objective.json.')


def plot_dense_cluster(out):
    d = J('d1_exec_density_family_result.json')
    if not d or not d.get('members'):
        return None
    fig, ax = plt.subplots(figsize=(8, 4.4))
    cols = {'0.5': C['s1'], '0.25': C['s2']}
    for F, m in sorted(d['members'].items(), key=lambda kv: -float(kv[0])):
        rungs = m['array']
        held = [r for r in rungs if r.get('holds_target') and r.get('Q_ratio_vs_ref')]
        lost = [r for r in rungs if not r.get('holds_target')]
        c = cols.get(str(float(F)) if str(F) not in cols else str(F), C['s3'])
        lab = 'execution cluster ×%s area (%g× denser)' % (F, 1 / float(F))
        ax.plot([r['W'] for r in held], [r['Q_ratio_vs_ref'] for r in held], color=c, marker='o', label=lab)
        if lost:
            ax.scatter([r['W'] for r in lost], [1.0] * len(lost), marker='x', color=c, s=60)
            ax.annotate('×%s: rung lost' % F, (lost[0]['W'], 1.0), xytext=(0, 10 if float(F) == 0.5 else 24),
                        textcoords='offset points', ha='center', fontsize=8, color=C['text2'])
    ax.axhline(1.0, color=C['muted'], lw=1); ax.text(112, 1.03, 'reference die (34-core) = 1', fontsize=8, color=C['text2'])
    ax.set_yscale('log'); ax.set_xlabel('die power, W (matched to the reference rungs)')
    from matplotlib.ticker import FixedLocator, FixedFormatter
    ax.yaxis.set_major_locator(FixedLocator([1, 1.5, 2, 3, 5, 7])); ax.yaxis.set_major_formatter(FixedFormatter(['1×', '1.5×', '2×', '3×', '5×', '7×']))
    ax.yaxis.set_minor_locator(FixedLocator([])); ax.set_ylim(0.85, 8)
    ax.set_ylabel('cooling plan ÷ reference plan at the same watts (log)')
    ax.set_title('A denser execution cluster: the rescue travels, density is paid for in cooling watts')
    ax.legend(fontsize=8)
    fn = 'dense_cluster.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3, §P0.22.3 — the first re-measured design change. The array holds the 2× '
                'denser cluster to the 2.00-equivalent rung and the 4× to 1.60, 0 tiles capped; the premium '
                'is large where the reference needs no light and converges to ~1.2×. Plans normalised to '
                'a 92 °C landing at 0.3247 K/W. Source: docs/evidence/d1_exec_density_family_result.json.')


def plot_extractor(out):
    e = J('extractor_cooling_curves.json')
    if not e:
        return None
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    r6 = e['target_device_table_1_1_rung_6']['book_sigma1_kedenburg']['curve']
    ax.plot([p['T_K'] for p in r6 if p['h_W_per_mm2'] > 0], [p['h_W_per_mm2'] for p in r6 if p['h_W_per_mm2'] > 0],
            color=C['s1'], label='target device: R640-SMILES, v100 Table 1.1 (rung 6)')
    try:
        g = e['gaas']['table_1_1_enhanced_retuned']['curve']
        ax.plot([p['T_K'] for p in g if p['h_W_per_mm2'] > 0], [p['h_W_per_mm2'] for p in g if p['h_W_per_mm2'] > 0],
                color=C['s2'], label='GaAs, Table 1.1, pump retuned to the gap')
    except Exception:
        pass
    ax.axvspan(263, 330, color=C['band']); ax.text(266, 3e4, 'tiles on this die\nrun 263–330 K', fontsize=8, color=C['text2'])
    dem = e.get('die_demand_from_coverage_ladder', {}).get('1.0', {}).get('max_tile_flux_W_per_mm2_over_ladder')
    if dem:
        ax.axhline(dem, color=C['muted'], lw=1); ax.text(180, dem * 1.3, 'most any tile is asked for on this die: %.0f W/mm²' % dem, fontsize=8, color=C['text2'])
    ax.set_yscale('log'); ax.set_xlabel('extractor temperature, K'); ax.set_ylabel('cooling flux, W/mm² (log)')
    ax.set_title("The extractor's lift never binds on this die"); ax.legend(fontsize=8, loc='lower right', bbox_to_anchor=(1.0, 0.12))
    fn = 'extractor_curves.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.5. The lift is a curve fixed by v100\'s constitutive model (the transparency '
                'cap, eq. 5.7); 0 tiles capped at every rescue rung; the dye is a hot-die platform (design '
                'point at 400 K). Source: docs/evidence/extractor_cooling_curves.json.')


def plot_leakage_curves(out):
    d = J('device_leakage_spice_asap7.json')
    if not d:
        return None
    cmp_ = sorted(d['comparison'], key=lambda r: r['T_K'])
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.plot([r['T_K'] for r in cmp_], [r['simulated_rel'] for r in cmp_], color=C['s1'], marker='o', label='simulated (BSIM-CMG on the ASAP7 card)')
    ax.plot([r['T_K'] for r in cmp_], [r['pipeline_rel'] for r in cmp_], color=C['s2'], marker='o', label="the pipeline curve (CACTI's 11 numbers)")
    ax.set_yscale('log'); ax.set_xlabel('junction temperature, K'); ax.set_ylabel('leakage relative to 330 K (log)')
    ax.axvline(345, color=C['muted'], lw=1)
    ax.text(0.98, 0.08, 'the curves cross near 345 K: below it the simulated curve\ncarries more feedback gain, above it less',
            transform=ax.transAxes, ha='right', va='bottom', fontsize=8, color=C['text2'])
    ax.set_title('The leakage curve every thermal result rests on'); ax.legend(fontsize=8, loc='upper left')
    fn = 'leakage_curves.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.4, §1.6. The recorded catalogue rested on CACTI\'s table (not a device); every '
                'quotable number now rests on the simulated curve, fitted to nothing. Source: '
                'docs/evidence/device_leakage_spice_asap7.json.')


def plot_dark_silicon(out):
    d = J('dark_silicon.json')
    if not d or not d.get('points'):
        return None
    dens = sorted({p['density'] for p in d['points']}); fracs = sorted({p['fraction'] for p in d['points']})
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.9), sharey=True)
    arms = (('control', 'conventional package (grease)'), ('array_idle', 'GaAs array in place, no light'), ('array_on', 'laser on'))
    for ax, (arm, title) in zip(axes, arms):
        for i, dn in enumerate(dens):
            for j, fr in enumerate(fracs):
                p = next((x for x in d['points'] if x['density'] == dn and x['fraction'] == fr), None)
                a = (p or {}).get(arm)
                if not a:
                    continue
                if a['lit']:
                    col, txt = C['s1'], ('%.0f°C' % a['peak_C'])
                    if arm == 'array_on' and (a.get('Q_W') or 0) > 0.05:
                        txt += '\n%.0f W' % a['Q_W']
                elif a.get('unconverged'):
                    col, txt = C['band'], 'undecided'
                elif a.get('diverged'):
                    col, txt = '#f3d9d0', 'runaway'
                else:
                    # §P0.29: a stable field the planner had not finished descending to target
                    # (a LOWER-BOUND plan) is neither lit nor a runaway; it was drawn as one.
                    col, txt = '#f5efd6', 'unfinished\n%.0f°C' % (a.get('peak_C') or 0)
                ax.add_patch(plt.Rectangle((j, i), 0.94, 0.94, color=col))
                ax.text(j + 0.47, i + 0.47, txt, ha='center', va='center', fontsize=7.5, color=C['text'] if a['lit'] else C['text2'])
        ax.set_xlim(0, len(fracs)); ax.set_ylim(0, len(dens)); ax.grid(False)
        ax.set_xticks([j + 0.47 for j in range(len(fracs))]); ax.set_xticklabels(['%.0f %%' % (100 * f) for f in fracs])
        ax.set_yticks([i + 0.47 for i in range(len(dens))]); ax.set_yticklabels(['%.2f' % dn for dn in dens])
        ax.set_title(title, fontsize=10); ax.set_xlabel('cores active (contiguous block)')
    axes[0].set_ylabel('per-core power density, W/mm²')
    fig.suptitle('Dark-silicon recovery on the 34-core die: which fraction of the cores can be lit', fontweight='bold', y=1.03)
    fn = 'dark_silicon.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3, §P0.23.2. Blue = holds the 92 °C target (laser cost shown where light is needed); '
                'pink = leakage runaway; grey = undecided by the verifier; cream = the planner had not finished its descent (a lower-bound plan, §P0.29). Hot cores are a contiguous block, the worst '
                'case. Source: docs/evidence/dark_silicon.json.')


def plot_two_dies(out):
    t = J('iso_package_throughput.json')
    if not t or '70core' not in t.get('dies', {}):
        return None
    # `[!]` The right-hand panel used to plot the pipeline's thermal-only GFLOP/s proxy against
    # package power. It is flat by construction (the density ladders inject watts at a FIXED
    # clock) and was misread as "compute does not scale"; removed 10 Sep on the user's review.
    # Throughput with the clock as the free variable is §P0.26 (F1c) and gets its own figure.
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2))
    for die, col, lab in (('34core', C['s1'], '34-core, 101 mm²'), ('70core', C['s2'], '70-core, 196 mm²')):
        rows = [r for r in t['dies'][die]['rows'] if r.get('array_on', {}).get('holds') and r['array_on'].get('s') is not None]
        a.plot([r['density'] for r in rows], [r['array_on']['s'] for r in rows], color=col, marker='o', label=lab)
        b.plot([r['density'] for r in rows], [r['array_on']['p_chip_W'] for r in rows], color=col, marker='o', label=lab)
    a.axhline(1.0, color=C['muted'], lw=1); a.text(0.03, 0.93, 's = 1: the array lifts everything', transform=a.transAxes, fontsize=8, color=C['text2'])
    a.set_xlabel('die power density, W/mm²'); a.set_ylabel("the array's share of the heat, s"); a.set_title('The bigger die needs the array sooner'); a.legend(fontsize=8, loc='lower right')
    b.set_xlabel('die power density, W/mm²'); b.set_ylabel('sustainable die power, W (laser on)'); b.set_title('Watts the same 88 CFM package holds, laser on'); b.legend(fontsize=8, loc='upper left')
    b.text(0.97, 0.05, 'watts, not compute: the clock-search figure\n(F1c) carries the throughput', transform=b.transAxes, ha='right', fontsize=8, color=C['text2'])
    fn = 'two_dies.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3, §P0.23.1. The laser\'s multiplier travels (2.2× vs 2.4× the driver\'s control) and the watts do not '
                '(301 W vs 221 W at the top rung). These are WATTS at a fixed clock; throughput against cooling is the '
                'clock-search result (§P0.26). Source: docs/evidence/iso_package_throughput.json.')


def plot_clock(out):
    t = J('clock_f1c_density.json')
    if not t or not t.get('runs'):
        return None
    runs = t['runs']
    order = [('spice_d0.78', '0.78 W/mm²\n(SPICE V/F)'), ('spice_d1.00', '1.00 W/mm²\n(SPICE V/F)'),
             ('spice_d1.20', '1.20 W/mm²\n(SPICE V/F)'), ('table_d1.00', '1.00 W/mm²\n(shipped table)')]
    order = [(k, l) for k, l in order if k in runs]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4))
    arms = (('control', 'conventional package', C['s2']), ('array_idle', 'GaAs array, no light', C['s3']), ('array_on', 'laser on', C['s1']))
    w = 0.26
    for j, (arm, lab, col) in enumerate(arms):
        xs = [i + (j - 1) * (w + 0.02) for i in range(len(order))]
        f = [runs[k]['rows'].get(arm, {}).get('f_GHz') or 0 for k, _ in order]
        e = [runs[k]['rows'].get(arm, {}).get('GFLOPs_per_package_W') or 0 for k, _ in order]
        a.bar(xs, f, width=w, color=col, label=lab)
        b.bar(xs, e, width=w, color=col, label=lab)
        for x, v, (k, _) in zip(xs, f, order):
            r = runs[k]['rows'].get(arm, {})
            tag = 'ceiling' if r.get('limited_by') == 'vf_envelope' else ('%.0f °C' % r['peak_C'] if r.get('peak_C') else '')
            a.text(x, v + 0.05, '%.2f\n%s' % (v, tag), ha='center', fontsize=7, color=C['text2'])
    for ax in (a, b):
        ax.set_xticks(range(len(order))); ax.set_xticklabels([l for _, l in order], fontsize=8)
    a.set_ylim(2.5, 5.3); a.set_ylabel('sustainable clock, GHz'); a.set_title('The clock as the free variable: three cooling arms')
    a.axhline(4.173, color=C['muted'], lw=1); a.text(0.01, 0.955, 'SPICE device ceiling 4.17 GHz (10 % overdrive)', transform=a.transAxes, fontsize=8, color=C['text2'])
    a.legend(fontsize=8, loc='upper left', bbox_to_anchor=(0.0, 0.93))
    b.set_ylabel('GFLOP/s per package watt (die + fan + net laser)'); b.set_title('Efficiency falls as the clock rises, on every arm'); b.legend(fontsize=8, loc='upper right')
    fn = 'clock_vs_cooling.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3, §P0.26. 34-core die, arm D, 88 CFM; the operating point is the die\'s power density at the '
                'trace clock; dynamic ∝ V²f on the device V/F, leakage ∝ V (assumed). The laser runs the die at the '
                'device\'s own ceiling where the conventional package must clock down (+14 % at 1.00 W/mm², +26 % at 1.20; '
                '+34 % on the shipped 5 GHz table, thermal-limited at 2.28 W/mm²). Throughput is f × 32 FLOP/cycle × 34 cores. '
                'Source: docs/evidence/clock_f1c_density.json.')


def plot_accelerator(out):
    d = J('accel_f3_power_tol1.json')
    if not d or not d.get('points'):
        return None
    pts = d['points']
    uni = sorted((int(re.match(r'uniform_(\d+)W', t).group(1)), p) for t, p in pts.items() if t.startswith('uniform'))
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4))
    W = [w for w, _ in uni]; Q = [(p.get('array_on') or {}).get('Q_W') or 0 for _, p in uni]
    net = [(p.get('array_on') or {}).get('net_W') or 0 for _, p in uni]
    a.plot(W, Q, color=C['s1'], marker='o', label='heat removed by the array')
    a.plot(W, net, color=C['s2'], marker='o', label='net electrical cost (with recovery)')
    a.plot(W, W, color=C['grid'], lw=1); a.text(0.97, 0.05, 'grey line: heat removed = die power\n(conservation; reached at 2600 W, s = 0.98)', transform=a.transAxes, ha='right', fontsize=8, color=C['text2'])
    a.text(0.03, 0.93, 'conventional stack: no steady state at any of these powers\nGaAs layer alone: holds 700 W', transform=a.transAxes, fontsize=8, color=C['text2'], va='top')
    a.set_xlabel('accelerator die power, W (uniform kernel)'); a.set_ylabel('W'); a.set_title('GA100 on a direct-die microchannel plate, laser on'); a.legend(fontsize=8, loc='center left', bbox_to_anchor=(0.0, 0.62))
    occ = [(t, p) for t, p in pts.items() if t.startswith('occ')]
    occ.sort(key=lambda tp: (int(re.search(r'_(\d+)W', tp[0]).group(1)), int(re.match(r'occ(\d+)', tp[0]).group(1))))
    labs = [t.replace('_', '\n') for t, _ in occ]; q = [(p.get('array_on') or {}).get('Q_W') or 0 for _, p in occ]
    pk = [(p.get('array_on') or {}).get('peak_C') for _, p in occ]
    b.bar(range(len(occ)), q, width=0.55, color=C['s1'])
    for i, (v, t) in enumerate(zip(q, pk)):
        b.text(i, v + 8, '%.0f W\n%.0f °C' % (v, t or 0), ha='center', fontsize=8, color=C['text2'])
    b.set_xticks(range(len(occ))); b.set_xticklabels(labs, fontsize=8); b.set_ylabel('heat removed to hold 92 °C, W'); b.set_ylim(0, max(q) * 1.3)
    b.set_title('Concentrated kernels: 8 or 32 of 128 SMs active')
    fn = 'accelerator.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3, §P0.24. The array holds the GA100 (826 mm², areas measured, power split ASSUMED) from '
                '700 W to 2600 W where the conventional stack has no steady state on the simulated leakage curve; the top '
                'rung ends on conservation (s = 0.98). 100 µm cells; the power-shaped envelope and the loop\'s own '
                'tolerance. Max tile flux 5.3 W/mm² — the extractor is 150× under-used. Source: docs/evidence/accel_f3_power_tol1.json.')


def plot_burst(out):
    d = J('burst_absorption.json')
    if not d or not d.get('points'):
        return None
    pts = {(p['density'], p['k']): p for p in d['points']}
    ref = pts.get((0.8, 2.0)) or sorted(pts.values(), key=lambda p: (p['density'], p['k']))[0]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4))
    arms = (('control', 'conventional package', C['s2']), ('array_static', 'GaAs array, plan held', C['s3']), ('array_modulated', 'array modulated (feed-forward)', C['s1']))
    slot = d['points'][0].get('slot_ms') if 'slot_ms' in d['points'][0] else 1.0
    for arm, lab, col in arms:
        r = ref['rows'].get(arm)
        if not r or r.get('steady_diverged') or not r.get('per_slot_peak_C'):
            continue
        y = r['per_slot_peak_C']; x = [i * 1.0 for i in range(len(y))]
        a.plot(x, y, color=col, marker='o', markersize=3, label=lab)
    a.axvspan(5, 15, color=C['band']); a.text(5.2, a.get_ylim()[1] * 0.995, 'burst: dynamic power ×%.1f' % ref['k'], fontsize=8, color=C['text2'], va='top')
    a.axhline(100, color=C['muted'], lw=1); a.text(0.98, 0.02, '100 °C spec', transform=a.transAxes, ha='right', fontsize=8, color=C['text2'])
    a.axhline(92, color=C['grid'], lw=1)
    a.set_xlabel('time, ms'); a.set_ylabel('peak block temperature, °C'); a.set_title('A 10 ms burst at %.2f W/mm² (die %.0f W)' % (ref['density'], ref['die_W'])); a.legend(fontsize=8, loc='upper left', bbox_to_anchor=(0.0, 0.9))
    keys = sorted(pts); labs = ['%.2f W/mm²\n×%.1f' % k for k in keys]; w = 0.26
    for j, (arm, lab, col) in enumerate(arms):
        v = [(pts[k]['rows'].get(arm) or {}).get('overshoot_K') for k in keys]
        xs = [i + (j - 1) * (w + 0.02) for i in range(len(keys))]
        b.bar(xs, [x or 0 for x in v], width=w, color=col, label=lab)
        for x, val, k in zip(xs, v, keys):
            r = pts[k]['rows'].get(arm) or {}
            if val is None:
                b.text(x, 1, 'no steady\nstate', ha='center', fontsize=7, color=C['text2'])
            elif r.get('ms_above_spec'):
                b.text(x, val + 0.5, '%.0f ms\n>spec' % r['ms_above_spec'], ha='center', fontsize=7, color=C['text2'])
    b.set_xticks(range(len(keys))); b.set_xticklabels(labs, fontsize=8); b.set_ylabel('overshoot of the peak block, K'); b.set_title('Overshoot per arm across the ladder'); b.legend(fontsize=8, loc='upper left')
    fn = 'burst_absorption.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3, §P0.25. 34-core die, arm D, 88 CFM; every block\'s dynamic power × k for 10 ms, warm-started from the '
                'steady state; the modulated array removes the burst\'s own added watts at their source during the burst. The '
                'conventional package and the unpowered array ride the burst on thermal mass; the modulated array keeps the die '
                'under its target. Source: docs/evidence/burst_absorption.json.')


# ----------------------------------------------------------------------------------------------
# markdown tables -> HTML (the register's own tables, verbatim)
# ----------------------------------------------------------------------------------------------
def md_inline(t):
    t = esc(t)
    t = re.sub(r'`([^`]*)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'~~(.+?)~~', r'<s>\1</s>', t)
    t = t.replace('\\|', '|')
    return t


def md_table(lines):
    rows = [l for l in lines if l.strip().startswith('|')]
    if len(rows) < 2:
        return ''
    def cells(l):
        return [c.strip() for c in re.split(r'(?<!\\)\|', l.strip().strip('|'))]
    hdr = cells(rows[0]); body = [cells(r) for r in rows[2:]]
    h = ['<table><thead><tr>' + ''.join('<th>%s</th>' % md_inline(c) for c in hdr) + '</tr></thead><tbody>']
    for r in body:
        h.append('<tr>' + ''.join('<td>%s</td>' % md_inline(c) for c in r) + '</tr>')
    h.append('</tbody></table>')
    return '\n'.join(h)


def register_sections():
    """{'0': html, '1.1': html, ...} -- every table of RESULTS_REGISTER.md §0 and §1, plus the §2 table."""
    txt = open(os.path.join(_REPO, 'docs', 'RESULTS_REGISTER.md')).read().split('\n')
    out, cur, buf, title = {}, None, [], {}
    for l in txt + ['## end']:
        m = re.match(r'^(##+)\s+(.*)', l)
        if m:
            if cur is not None:
                out[cur] = md_table(buf)
            cur = m.group(2); buf = []; title[cur] = m.group(2)
        else:
            buf.append(l)
    return out


def md_to_html(path):
    """A small, honest markdown renderer for the ladder and the design records: headings, tables,
    lists, paragraphs, code spans, bold. Enough to read; the .md is shipped beside it."""
    lines = open(path).read().split('\n')
    h, i, para = [], 0, []
    def flush():
        if para:
            h.append('<p>%s</p>' % md_inline(' '.join(para))); para.clear()
    while i < len(lines):
        l = lines[i]
        if l.startswith('|'):
            flush(); j = i
            while j < len(lines) and lines[j].startswith('|'):
                j += 1
            h.append(md_table(lines[i:j])); i = j; continue
        if l.startswith('    ') and not para:
            flush(); j = i; code = []
            while j < len(lines) and (lines[j].startswith('    ') or lines[j].strip() == ''):
                code.append(lines[j][4:]); j += 1
            h.append('<pre>%s</pre>' % esc('\n'.join(code).strip('\n'))); i = j; continue
        m = re.match(r'^(#+)\s+(.*)', l)
        if m:
            flush(); h.append('<h%d>%s</h%d>' % (min(len(m.group(1)) + 1, 5), md_inline(m.group(2)), min(len(m.group(1)) + 1, 5))); i += 1; continue
        if re.match(r'^\s*[-*]\s+', l) or re.match(r'^\s*\d+\.\s+', l):
            flush(); j = i; items = []
            while j < len(lines) and (re.match(r'^\s*[-*]\s+', lines[j]) or re.match(r'^\s*\d+\.\s+', lines[j]) or (lines[j].startswith('  ') and lines[j].strip())):
                if re.match(r'^\s*[-*]\s+', lines[j]) or re.match(r'^\s*\d+\.\s+', lines[j]):
                    items.append(re.sub(r'^\s*([-*]|\d+\.)\s+', '', lines[j]))
                else:
                    items[-1] += ' ' + lines[j].strip()
                j += 1
            h.append('<ul>' + ''.join('<li>%s</li>' % md_inline(x) for x in items) + '</ul>'); i = j; continue
        if l.strip() == '---':
            flush(); h.append('<hr>'); i += 1; continue
        if l.strip() == '':
            flush(); i += 1; continue
        para.append(l.strip()); i += 1
    flush()
    return '\n'.join(h)


# ----------------------------------------------------------------------------------------------
CSS = """
:root{--ink:#0b0b0b;--ink2:#52514e;--mute:#8a8985;--surf:#fcfcfb;--line:#e9e8e4;--band:#f0efec;--acc:#2a78d6;--warn:#eb6834}
*{box-sizing:border-box}body{margin:0;background:var(--surf);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif}
main{max-width:1080px;margin:0 auto;padding:28px 36px 80px}h1{font-size:26px;margin:0 0 4px}h2{font-size:20px;margin:40px 0 8px;padding-top:12px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:22px 0 6px}h4{font-size:14px;margin:16px 0 4px}p{margin:8px 0}.sub{color:var(--ink2)}
table{border-collapse:collapse;width:100%;margin:10px 0 16px;font-size:13.5px}th,td{text-align:left;vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--line)}th{color:var(--ink2);font-weight:600;background:var(--band)}
code{font:12.5px/1.4 ui-monospace,Menlo,Consolas,monospace;background:var(--band);padding:1px 4px;border-radius:3px}pre{background:var(--band);padding:10px 12px;border-radius:4px;overflow-x:auto;font-size:12.5px}
figure{margin:14px 0 22px}figure img{max-width:100%;border:1px solid var(--line);border-radius:4px}figcaption{color:var(--ink2);font-size:13px;margin-top:6px}
.tile{display:inline-block;min-width:200px;margin:6px 10px 6px 0;padding:12px 16px;border:1px solid var(--line);border-radius:6px;background:#fff}.tile b{display:block;font-size:24px}.tile span{color:var(--ink2);font-size:13px}
.warn{border-left:4px solid var(--warn);padding:8px 12px;background:var(--band);margin:12px 0}.tag{font-size:11px;font-weight:700;letter-spacing:.04em;padding:1px 6px;border-radius:3px;background:var(--band);color:var(--ink2)}
.tag.m{background:#e3efdc;color:#1f5a12}.tag.a{background:#fbe8de;color:#8a3a12}nav a{margin-right:14px}a{color:var(--acc)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:800px){.grid{grid-template-columns:1fr}}@media print{main{max-width:none;padding:0}h2{break-before:page}}
"""


def plot_pdn(out):
    d = J('pdn_em_skew.json')
    if not d or not d.get('fields'):
        return None
    F = d['fields']
    rungs = [('1.00', 'rescue_d1.00_array_idle'), ('1.10', 'rescue_d1.10_array_on'), ('1.20', 'rescue_d1.20_array_on'),
             ('1.30', 'rescue_d1.30_array_on'), ('1.40', 'rescue_d1.40_array_on'), ('1.50', 'rescue_d1.50_array_on'),
             ('1.60', 'rescue_d1.60_array_on'), ('1.70', 'rescue_d1.70_array_on'), ('1.80', 'rescue_d1.80_array_on'),
             ('2.00', 'rescue_d2.00_array_on'), ('2.20', 'rescue_d2.20_array_on'), ('2.40', 'rescue_d2.40_array_on')]
    rungs = [(float(x), F[l]) for x, l in rungs if l in F]
    if not rungs:
        return None
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 4.2))
    x = [r[0] for r in rungs]
    a.plot(x, [r[1]['I_ratio'] for r in rungs], color=C['s1'], marker='o', label='die current / native (every rail)')
    a.plot(x, [r[1]['J_ratio_at_peak_block'] for r in rungs], color=C['s2'], marker='o', label='peak block J / native')
    for mem, col, lab in (('exec0.5', C['s3'], '×0.5 cluster: cALU J / native'), ('exec0.25', C['s4'], '×0.25 cluster')):
        pts = [(W / REF_MM2, F[l]['J_ratio_exec_max']) for W, l in ((121.316, 'd1_%s_W121.316_array_on' % mem), (161.755, 'd1_%s_W161.755_array_on' % mem), (202.194, 'd1_%s_W202.194_array_on' % mem)) if l in F]
        if pts:
            a.plot([p[0] for p in pts], [p[1] for p in pts], color=col, marker='s', ls='--', label=lab)
    a.axhline(1.0, color=C['muted'], lw=1); a.set_xlabel('die power density, W/mm² (0.70 V, 3.8 GHz)'); a.set_ylabel('× the native die (0.78 W/mm²)')
    a.set_title('The rescue ladder is a current ladder'); a.legend(fontsize=7, loc='upper left')
    b.semilogy(x, [r[1]['EM_AF_max'] for r in rungs], color=C['s2'], marker='o', label="worst block, Black's law (n = 2, 0.9 eV)")
    b.semilogy(x, [r[1]['J_ratio_at_peak_block'] ** 2 for r in rungs], color=C['s1'], marker='o', ls='--', label='J² alone at the peak block')
    b.axhline(1.0, color=C['muted'], lw=1); b.set_xlabel('die power density, W/mm²'); b.set_ylabel('EM acceleration vs the native die')
    b.set_title('The non-thermal end: EM acceleration'); b.legend(fontsize=7, loc='upper left')
    b.text(0.97, 0.05, 'ARGUED: n, E_a stated;\nno rail model', transform=b.transAxes, ha='right', fontsize=8, color=C['text2'])
    c.plot(x, [r[1]['dT_core_max_K'] for r in rungs], color=C['s1'], marker='o', label='laser field, worst core')
    nat = F.get('native_d0.78_control')
    if nat:
        c.axhline(nat['dT_core_max_K'], color=C['muted'], lw=1)
        c.text(0.03, 0.05, 'native die: %.0f K (%.1f %% of the period at 150 ps)' % (nat['dT_core_max_K'], nat['skew_cost_core_pct']), transform=c.transAxes, fontsize=8, color=C['text2'])
    ymax = max(r[1]['dT_core_max_K'] for r in rungs) * 1.1
    c.set_ylim(0, ymax)
    c2 = c.twinx(); c2.set_ylim(0, 100.0 * ymax * 150.0 * (0.5 * 0.004 + 0.5 * 0.00062) / (1000.0 / 3.8)); c2.set_ylabel('skew cost, % of the 3.8 GHz period (D_ins 150 ps)'); c2.grid(False)
    c.set_xlabel('die power density, W/mm²'); c.set_ylabel('core-domain gradient, K (L3 excluded)'); c.set_title('Thermal skew grows with the rung'); c.legend(fontsize=7, loc='upper left')
    fn = 'pdn_em_skew.png'; fig.savefig(os.path.join(out, fn)); plt.close(fig)
    return fn, ('Register §1.3, §P0.27 (X1/X2). The recorded final power maps of the rescue ladder and the D1 family, re-solved once and read '
                'as current densities at 0.70 V against the native die: every rung above ~1.3 W/mm² runs the rails at 1.5–3× the '
                'native current, the dense cluster\'s cALU at 2× / 4× that. EM acceleration and the skew percentage are ARGUED on stated '
                'constants (Black n = 2, E_a = 0.9 eV; insertion delay 150 ps); the gradients are measured. Source: docs/evidence/pdn_em_skew.json.')


def build(out):
    if os.path.isdir(out):
        shutil.rmtree(out)
    for sub in ('figures', 'evidence', 'docs'):
        os.makedirs(os.path.join(out, sub))
    fig_dir = os.path.join(out, 'figures')
    try:
        commit = subprocess.check_output(['git', '-C', _REPO, 'rev-parse', '--short', 'HEAD']).decode().strip()
    except Exception:
        commit = 'unknown'
    date = datetime.date.today().isoformat()

    figs = {}
    for name, fn in (('rescue', plot_rescue_ladder), ('ceilings', plot_density_ceilings),
                     ('cold', plot_cold_zone), ('cache', plot_cache_objective), ('dense', plot_dense_cluster),
                     ('extractor', plot_extractor), ('leak', plot_leakage_curves),
                     ('dark', plot_dark_silicon), ('twodies', plot_two_dies), ('clock', plot_clock),
                     ('accel', plot_accelerator), ('burst', plot_burst), ('pdn', plot_pdn)):
        try:
            figs[name] = fn(fig_dir)
        except Exception as ex:      # a missing evidence file must not sink the pack
            print('  [skip] %s: %s' % (name, ex)); figs[name] = None
    for m in ('ref', 'd1_exec0.5', 'd1_exec0.25'):
        src = os.path.join(_REPO, 'docs', 'designs', 'figures', m, 'floorplan_34core.png')
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(fig_dir, 'floorplan_%s.png' % m))

    # evidence: the curated quotable set
    ev_files = []
    for d in sorted(glob.glob(os.path.join(_REPO, 'results-quotable', '*'))):
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, '*.json')) + glob.glob(os.path.join(d, 'SOURCE.md')):
            dst = os.path.join(out, 'evidence', os.path.basename(d) + '__' + os.path.basename(f))
            shutil.copy(f, dst); ev_files.append(os.path.relpath(dst, out))
    for f in ('RESULTS_REGISTER.md', 'REFERENCES.md', 'METHODS.md', 'ARCHITECTURE_EVOLUTION.md',
              'designs/EVOLUTION_LADDER.md', 'designs/gen1_dense_cluster.md', 'designs/gen3_cache_objective.md'):
        src = os.path.join(_REPO, 'docs', f)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(out, 'docs', os.path.basename(f)))

    R = register_sections()
    d3 = J('d3_cache_objective.json') or {}
    d4 = J('d4_falsification_70core.json') or {}
    d1 = J('d1_exec_density_family_result.json') or {}

    def fig_html(key):
        f = figs.get(key)
        if not f:
            return ''
        return '<figure><img src="figures/%s" alt="%s"><figcaption>%s</figcaption></figure>' % (f[0], esc(f[0]), esc(f[1]))

    def sc_table(sc):
        if not sc:
            return '<p class="sub">not yet scored</p>'
        h = ['<table><thead><tr><th>prediction</th><th>verdict</th></tr></thead><tbody>']
        for k, v in sc.items():
            if isinstance(v, dict) and 'verdict' in v:
                h.append('<tr><td><code>%s</code></td><td>%s</td></tr>' % (esc(k), esc(v['verdict'])))
            elif isinstance(v, dict):
                for k2, v2 in v.items():
                    h.append('<tr><td><code>%s / %s</code></td><td>%s</td></tr>' % (esc(k), esc(k2), esc(v2.get('verdict'))))
        h.append('</tbody></table>')
        return '\n'.join(h)

    H = io.StringIO()
    w = H.write
    w('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    w('<title>MXL-HotGauge — quotable results, %s</title><style>%s</style></head><body><main>' % (date, CSS))
    w('<h1>MXL-HotGauge — quotable results for the proposal</h1>')
    w('<p class="sub">Photonic microrefrigeration of a 34-core 7 nm die: what has been measured, what is argued, and what must not be said. '
      'Generated %s from repository commit <code>%s</code> by <code>scripts/build_proposal_pack.py</code>. '
      'Every number is register §1 (<a href="docs/RESULTS_REGISTER.md">docs/RESULTS_REGISTER.md</a>) with its caveat; evidence files are under <code>evidence/</code>.</p>' % (date, commit))
    w('<nav><a href="#read">How to read</a><a href="#headline">Headline</a><a href="#ladder">The evolution ladder</a><a href="#cold">Cold caches</a>'
      '<a href="#density">Density &amp; floorplans</a><a href="#device">Device platform</a><a href="#transistor">Transistor</a>'
      '<a href="#corrections">Corrections</a><a href="#config">Configuration</a><a href="#never">Never say</a><a href="#files">Files</a></nav>')

    w('<h2 id="read">How to read this pack</h2>')
    w('<p>Three kinds of statement appear, and the tag matters more than the number: <span class="tag m">MEASURED</span> a solved result with a JSON behind it; '
      '<span class="tag a">ARGUED</span> reasoning from measured things (the ladder\'s design moves); anything else is <em>open</em> and is not in this pack. '
      'Every quotable claim carries a caveat column — it is part of the claim. Ratios travel across dies; absolute ceilings do not; MR costs are only comparable at a common landing peak (0.3247 K/W).</p>')
    w('<div class="warn"><strong>The die and the configuration.</strong> 34-core 7 nm skylake (101.1 mm², 1126 blocks), single-threaded LINPACK replicated; 88 CFM baffled fin on a fixed 1825 mm² base (0.325 K/W); '
      'arm D throughout (simulated leakage curve, amortized bus, hierarchy-consistent core accounting — the shipped default since 9 Sep 2026). '
      'Target extractor: v100 Table 1.1\'s R640-SMILES row; storage-zone material Cr:LiSAF (ceilings at η<sub>EQE</sub> = 1); Yb:YLF is not a zone material.</div>')

    w('<h2 id="headline">Headline — the laser rescues a die that has no steady state</h2>')
    w('<h3>Throughput: the clock as the free variable <span class="tag m">MEASURED</span></h3>')
    w(fig_html('clock'))
    w('<div><div class="tile"><b>35 / 35</b><span>rescue points, three leakage curves</span></div><div class="tile"><b>1.20 → 2.40 W/mm²</b><span>rescue range (unpowered array fails 1.20; laser holds to 2.40 under conservation)</span></div>'
      '<div class="tile"><b>17 → 139 W</b><span>heat removed at 1.20 → 2.00 (11 → 84 W net)</span></div><div class="tile"><b>0 tiles capped</b><span>by the target device at every rung</span></div></div>')
    w(fig_html('rescue'))
    w(R.get('1.1 The core result — microrefrigeration rescues a die that has no steady state', ''))

    w('<h2 id="ladder">The evolution ladder — bottleneck → laser cooling removes it → the architecture changes → the next bottleneck</h2>')
    w('<p>The argued account, in the frame of v100 §1.18 (the architectural budget inequality 1.32 and the hybrid cap 1.33) and §10.9 (thermal heterogeneity, three walls). '
      'The full document is <a href="docs/EVOLUTION_LADDER.md">docs/EVOLUTION_LADDER.md</a> (rendered below the scorecard); the design records are <a href="docs/gen1_dense_cluster.md">gen 1</a> and <a href="docs/gen3_cache_objective.md">gen 3</a>.</p>')
    lad = open(os.path.join(_REPO, 'docs', 'designs', 'EVOLUTION_LADDER.md')).read().split('\n')
    i7 = next((i for i, l in enumerate(lad) if l.startswith('## 7.')), None)
    if i7 is not None:
        j = i7 + 1
        while j < len(lad) and not lad[j].startswith('## '):
            j += 1
        w(md_table(lad[i7:j]))
    w('<h3>Gen 1, measured: the dense execution cluster <span class="tag m">MEASURED</span></h3>')
    w(fig_html('dense'))
    w('<div class="grid"><figure><img src="figures/floorplan_ref.png" alt="reference floorplan"><figcaption>The reference 34-core die (our rendering of our floorplan; 101.1 mm²).</figcaption></figure>'
      '<figure><img src="figures/floorplan_d1_exec0.5.png" alt="dense cluster floorplan"><figcaption>The ×0.5 member: execution units (cALU, iALU, FPU, AVX) at half area, caches and the leftover slab unchanged; 91.3 mm², cluster 2× denser at the same power.</figcaption></figure></div>')
    w(sc_table((d1.get('scorecard') or {})))
    w('<h3>Gen 3, the constraint measured: the cache-leakage objective on the monolithic die <span class="tag m">MEASURED</span> — the two-die design <span class="tag a">ARGUED</span></h3>')
    w(fig_html('cache'))
    w(sc_table(d3.get('scorecard')))
    w('<h3>The full ladder</h3><details><summary>Expand docs/EVOLUTION_LADDER.md</summary>%s</details>' % md_to_html(os.path.join(_REPO, 'docs', 'designs', 'EVOLUTION_LADDER.md')))

    w('<h2 id="cold">Cooling the cache — the prize is leakage, not heat</h2>')
    w(fig_html('cold'))
    w(R.get('1.2 Cooling the cache', ''))

    w('<h2 id="density">Density, concentration and the floorplan — and does it travel?</h2>')
    w(fig_html('ceilings'))
    w('<h3>Dark-silicon recovery and the second die <span class="tag m">MEASURED</span></h3>')
    w(fig_html('dark')); w(fig_html('twodies'))
    w('<h3>The accelerator on a microchannel plate <span class="tag m">MEASURED</span></h3>')
    w(fig_html('accel'))
    w('<h3>Burst absorption: the array\'s speed <span class="tag m">MEASURED</span></h3>')
    w(fig_html('burst'))
    w('<h3>The ladder\'s non-thermal end: rails and clock skew on the recorded fields <span class="tag m">MEASURED</span> as current density, <span class="tag a">ARGUED</span> as a limit</h3>')
    w(fig_html('pdn'))
    w(R.get('1.3 Density, concentration and the floorplan', ''))
    w('<h3>The 70-core falsification test (D4)</h3>')
    w(sc_table(d4.get('scorecard')))
    if not d4.get('complete', False):
        w('<p class="sub">The 70-core shaped 0.45 rung may still have been running when this pack was built; check <code>evidence/12-falsification-70core__d4_falsification_70core.json</code> → <code>complete</code>.</p>')

    w('<h2 id="device">The device platform</h2>')
    w(fig_html('extractor'))
    w(R.get('1.5 The device platform', ''))

    w('<h2 id="transistor">The transistor — ASAP7, simulated</h2>')
    w(fig_html('leak'))
    w(R.get('1.6 The transistor — ASAP7, simulated (§P0.13, §P0.18.3)', ''))
    w('<h3>The threshold lever, re-priced on the device <span class="tag a">ARGUED on measured inputs</span></h3>')
    w('<table><thead><tr><th>ΔV<sub>th</sub></th><th>clock</th><th>leakage on the low-V<sub>th</sub> blocks</th><th>cooling that pays for it</th><th>inside the demonstrated 45 K?</th></tr></thead><tbody>'
      '<tr><td>25 mV</td><td>+7.6 %</td><td>2.57× (300 K) … 2.03× (400 K)</td><td>22–30 K</td><td>yes</td></tr>'
      '<tr><td>50 mV</td><td>+15 %</td><td>6.6× … 4.1×</td><td>45–60 K</td><td>at its edge</td></tr>'
      '<tr><td>75 mV</td><td>+22 %</td><td>8.4× (400 K)</td><td>67–90 K</td><td>no</td></tr></tbody></table>'
      '<p class="sub">§P0.18.3. A re-derivation on the simulated card (swing 61 mV/dec at 300 K, +0.20 mV/dec per K), not a thermal measurement; the lever has not been run end to end.</p>')

    w('<h2 id="corrections">What the corrections revealed</h2>')
    w(R.get('1.4 What the corrections revealed', ''))

    w('<h2 id="config">The configuration every number is computed under</h2>')
    w(R.get('0. The configuration every current number is computed under', ''))

    w('<h2 id="never">Withdrawn — never say these</h2><p>Register §2. Kept here so a withdrawn number is recognised when it resurfaces in an older draft.</p>')
    w(R.get('2. Withdrawn — do not use', ''))

    w('<h2 id="files">Files in this pack</h2><ul>')
    for f in sorted(os.listdir(fig_dir)):
        w('<li><a href="figures/%s">figures/%s</a></li>' % (f, f))
    for f in sorted(os.listdir(os.path.join(out, 'docs'))):
        w('<li><a href="docs/%s">docs/%s</a></li>' % (f, f))
    for f in ev_files:
        w('<li><a href="%s">%s</a></li>' % (f, f))
    w('</ul><p class="sub">Solve trees (gigabytes) are not included; each SOURCE.md names the reproduce command and the raw tree in the repository.</p>')
    w('</main></body></html>')
    with open(os.path.join(out, 'index.html'), 'w') as f:
        f.write(H.getvalue())
    with open(os.path.join(out, 'README.md'), 'w') as f:
        f.write('# MXL-HotGauge quotable results pack (%s, commit %s)\n\nOpen `index.html`. Everything is register §1 with its caveat; '
                '`docs/` holds the register, the evolution ladder and the design records; `evidence/` the JSON behind each claim; '
                '`figures/` the plots. Regenerate with `python scripts/build_proposal_pack.py`.\n' % (date, commit))
    return figs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(_REPO, 'proposal_pack_%s' % datetime.date.today().isoformat()))
    ap.add_argument('--no-zip', action='store_true')
    args = ap.parse_args()
    figs = build(args.out)
    print('figures:', ', '.join(k for k, v in figs.items() if v))
    if not args.no_zip:
        z = shutil.make_archive(args.out, 'zip', os.path.dirname(args.out), os.path.basename(args.out))
        print('zip:', z, '%.1f MB' % (os.path.getsize(z) / 1e6))
    print('pack:', args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
