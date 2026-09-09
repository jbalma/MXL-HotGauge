#!/usr/bin/env python
"""The MR catalogue on the measured leakage curves -- rescue survival, array cost, loop gain.

    python examples/mr_curve_compare.py

§P0.15 gave ``mr_comparison.py`` and ``mr_clipping_study.py`` a ``--leakage-curve`` flag but never
ran them on anything but ``pipeline``, so the 22 rescues, the clipping study, the granularity
result and the budget cliff all still rested on CACTI's eleven hard-coded numbers (§P0.12). This
reads the pipeline tree and the two simulated trees and answers the one question the rescue claim
turns on.

**A rescue is a DIFFERENCE, so both arms are required.** The recorded headline is *"control has no
steady state, array holds target"*. Re-running only the array arm cannot tell you whether a rescue
survived -- if a gentler curve lets the CONTROL hold, the rescue is gone while every MR number in
it is unchanged. This compares ``control``, ``array_idle`` and ``array_on`` at every point.

`[+]` **The loop gain is recoverable from the recorded logs, with no re-solve.** When the solver
calls a genuine runaway it prints the residual on either side of one step at a known damping, and
``anchor_residual`` is re-anchored every iteration in that branch
(``power/leakage.py``), so the printed pair is **one iteration apart**. The damped
fixed-point map ``T <- (1-r)T + r f(T)`` has residual multiplier ``(1-r) + rG``, hence

    G = 1 + (residual_2 / residual_1 - 1) / r

That is the quantity §P0.16 predicted with, and measuring it on both curves is what shows why the
prediction failed: see ``report()``.
"""
import os
import re
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

#: where each curve's airflow ladder lives. `pipeline` is the RECORDED tree and is never rewritten.
TREES = {
    'pipeline': os.path.join(_REPO, 'results', 'overnight_forward', 'B_cfm'),
    'simulated': os.path.join(_REPO, 'results', 'mr_curve_compare', 'B_cfm_simulated'),
    'simulated-gidl-off': os.path.join(_REPO, 'results', 'mr_curve_compare', 'B_cfm_gidl_off'),
}
CFMS = ('120', '88', '60', '45', '30', '20')

#: the clipping study (`mr_clipping_study.py`) -- the OTHER side of the 345 K crossover. Its
#: baseline sits at ~344.9 K (on the crossover) and its MR arm at ~326.1 K, where the simulated
#: curve carries ~5x the `dP_leak/dT` of the pipeline one. The airflow ladder's arms sit at 367 K
#: and above, where it carries less. Two MR families, opposite sides, same flag.
CLIP_TREES = {
    'pipeline': os.path.join(_REPO, 'results', 'overnight_forward', 'E_leak'),
    'simulated': os.path.join(_REPO, 'results', 'mr_curve_compare', 'E_leak_simulated'),
    'simulated-gidl-off': os.path.join(_REPO, 'results', 'mr_curve_compare', 'E_leak_gidl_off'),
}
BUDGETS = ('0.5', '1', '2', '3', '5', '8', '12')

#: the COUPLED granularity ladder. `[!]` The recorded granularity result (2.77x on a hotspot) comes
#: from `tile_pitch_sweep.py`, which does LINEAR solves and holds no leakage model at all -- so
#: `--leakage-curve` cannot be tested there and re-running it would be a byte-identical no-op. This
#: asks the same question through `mr_comparison.py`, which solves the coupled problem.
PITCH_TREES = {
    'pipeline': os.path.join(_REPO, 'results', 'mr_curve_compare', 'C_pitch_pipeline'),
    'simulated': os.path.join(_REPO, 'results', 'mr_curve_compare', 'C_pitch_simulated'),
    'simulated-gidl-off': os.path.join(_REPO, 'results', 'mr_curve_compare', 'C_pitch_gidl_off'),
}
PITCHES = ('50', '100', '200', '500', '1000', '2000')

_RUNAWAY = re.compile(r'residual still growing \(([\d.]+) -> ([\d.]+) K\) '
                      r'at the minimum damping ([\d.]+)')


def loop_gain(log_path):
    """``G`` at the first genuine-runaway call in ``log_path``, or ``None``.

    The first such line in an ``mr_comparison`` log is the **control** arm, which is the arm the
    rescue claim depends on (arms are emitted control, array_idle, array_on in order).
    """
    if not os.path.exists(log_path):
        return None
    for line in open(log_path, errors='replace'):
        m = _RUNAWAY.search(line)
        if m:
            r1, r2, r = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if r1 > 0 and r > 0:
                return {'residual_from_K': r1, 'residual_to_K': r2, 'min_relax': r,
                        'loop_gain_G': 1.0 + ((r2 / r1) - 1.0) / r}
    return None


def read_point(tree, cfm):
    p = os.path.join(tree, 'cfm%s' % cfm, 'mr_comparison.json')
    if not os.path.exists(p):
        return None
    doc = json.load(open(p))
    arms = {r['arm']: r for r in doc['rows']}
    out = {'cfm': float(cfm)}
    for a in ('control', 'array_idle', 'array_on'):
        r = arms.get(a, {})
        out[a] = {'diverged': r.get('diverged'), 'unconverged': r.get('unconverged'),
                  'peak_C': r.get('peak_C'), 'p_chip_W': r.get('p_chip_W'),
                  'p_mr_net_W': r.get('p_mr_net_W'),
                  'heat_removed_W': r.get('heat_removed_W'),
                  'holds_target': r.get('mr_plan_holds_target'),
                  'plan_is_minimum': r.get('mr_plan_is_minimum')}
    out['control_loop_gain'] = loop_gain(os.path.join(tree, 'cfm%s' % cfm, 'log.txt'))
    return out


def is_rescue(pt):
    """The recorded definition: control has NO steady state and the array holds.

    `[!]` An ``unconverged`` arm is neither holding nor failing and must never become a rescue or
    a ceiling -- the same rule the density ladder uses.
    """
    c, a = pt['control'], pt['array_on']
    if c.get('unconverged') or a.get('unconverged'):
        return None
    return bool(c.get('diverged')) and not a.get('diverged')


def read_clip(tree, w):
    p = os.path.join(tree, 'w%s' % w, 'mr_study.json')
    if not os.path.exists(p):
        return None
    doc = json.load(open(p))
    r = doc['rows'][0]
    base, mr, acc = r.get('baseline') or {}, r.get('mr') or {}, r.get('mr_accounting') or {}
    return {
        'budget_W': float(w),
        'baseline_T_hot_C': base.get('T_hot_C'), 'mr_T_hot_C': mr.get('T_hot_C'),
        'dT_K': (base.get('T_hot_C') - mr.get('T_hot_C'))
                if base.get('T_hot_C') is not None and mr.get('T_hot_C') is not None else None,
        'heat_removed_W': acc.get('heat_removed_W'),
        'baseline_perf_per_W': base.get('perf_per_W'), 'mr_perf_per_W': mr.get('perf_per_W'),
        'mr_wins_on_perf_per_W': (mr.get('perf_per_W') > base.get('perf_per_W'))
                if base.get('perf_per_W') is not None and mr.get('perf_per_W') is not None else None,
        'mr_converged': r.get('mr_converged'), 'baseline_diverged': r.get('baseline_diverged'),
        'electrical_power_W': acc.get('electrical_power_W'),
        'net_generating': acc.get('net_generating'),
    }


def clipping_report():
    """The budget ladder on all three curves. `[!]` The MR arm here sits at ~326 K -- the COLD side
    of the 345 K crossover -- so this family is expected to move where the airflow ladder did not."""
    data = {k: {w: read_clip(t, w) for w in BUDGETS} for k, t in CLIP_TREES.items()}
    data = {k: {w: v for w, v in d.items() if v} for k, d in data.items()}
    if not any(data.values()):
        print('\n(no clipping results yet)')
        return {}

    print('\n=== clipping study: budget ladder, dT bought and where the arms sit ===')
    print('%-20s %-7s %10s %10s %8s %10s %9s'
          % ('curve', 'budget', 'base T C', 'mr T C', 'dT K', 'removed W', 'MR wins'))
    for k, d in data.items():
        for w in BUDGETS:
            if w not in d:
                continue
            r = d[w]
            print('%-20s %-7s %10s %10s %8s %10s %9s' % (
                k, w,
                '%.2f' % r['baseline_T_hot_C'] if r['baseline_T_hot_C'] is not None else '--',
                '%.2f' % r['mr_T_hot_C'] if r['mr_T_hot_C'] is not None else '--',
                '%.2f' % r['dT_K'] if r['dT_K'] is not None else '--',
                '%.3f' % r['heat_removed_W'] if r['heat_removed_W'] is not None else '--',
                r['mr_wins_on_perf_per_W']))

    print('\n=== K per watt removed -- the quantity that is comparable across curves ===')
    print('%-20s %s' % ('curve', '  '.join('%7s' % w for w in BUDGETS)))
    for k, d in data.items():
        print('%-20s %s' % (k, '  '.join(
            '%7.3f' % (d[w]['dT_K'] / d[w]['heat_removed_W'])
            if w in d and d[w].get('heat_removed_W') else '   -   ' for w in BUDGETS)))
    return data


def read_pitch(tree, pitch):
    p = os.path.join(tree, 'p%s' % pitch, 'mr_comparison.json')
    if not os.path.exists(p):
        return None
    doc = json.load(open(p))
    arms = {r['arm']: r for r in doc['rows']}
    a, c = arms.get('array_on', {}), arms.get('control', {})
    return {'pitch_um': float(pitch), 'n_tiles': a.get('n_tiles'),
            'control_diverged': c.get('diverged'),
            'peak_C': a.get('peak_C'), 'p_mr_net_W': a.get('p_mr_net_W'),
            'heat_removed_W': a.get('heat_removed_W'), 'p_chip_W': a.get('p_chip_W')}


def pitch_report():
    """Granularity, coupled. The cost of a COARSE array at a fixed target is the granularity
    result; a coarse tile cools collateral silicon and bills the laser for it."""
    data = {k: {p: read_pitch(t, p) for p in PITCHES} for k, t in PITCH_TREES.items()}
    data = {k: {p: v for p, v in d.items() if v} for k, d in data.items()}
    if not any(data.values()):
        print('\n(no pitch results yet)')
        return {}
    print('\n=== granularity, COUPLED: array cost vs tile pitch at a fixed 92 C target ===')
    print('%-20s %-7s %9s %9s %10s %9s' % ('curve', 'pitch', 'n_tiles', 'peak C', 'removed W',
                                           'ctrl div'))
    for k, d in data.items():
        for p in PITCHES:
            if p not in d:
                continue
            r = d[p]
            print('%-20s %-7s %9s %9s %10s %9s' % (
                k, p, r['n_tiles'],
                '%.2f' % r['peak_C'] if r['peak_C'] is not None else '--',
                '%.3f' % r['heat_removed_W'] if r['heat_removed_W'] is not None else '--',
                r['control_diverged']))
    print('\n=== coarse-vs-fine penalty (removed W at 2000 um / at 200 um) ===')
    for k, d in data.items():
        if '2000' in d and '200' in d and d['200']['heat_removed_W']:
            print('  %-20s %.3f W -> %.3f W   = %.2fx'
                  % (k, d['200']['heat_removed_W'], d['2000']['heat_removed_W'],
                     d['2000']['heat_removed_W'] / d['200']['heat_removed_W']))
    # `[!]` The raw ratio above is CONFOUNDED by where each minimum-plan descent stopped: on the
    # simulated curve the 2000 um point lands 3.3 K below the 200 um point, and buying those
    # kelvin is most of its extra cost. Normalise every point to a common peak at the package's
    # own measured resistance (0.3247 K/W at 88 CFM, spreading_boundary_by_die.json) -- the same
    # correction that reproduced the airflow ladder's array-cost delta to 0.06 %.
    R_TH = 0.3247
    ref = 93.5
    print('\n=== the same penalty, NORMALISED to a common %.1f C peak at %.4f K/W ==='
          % (ref, R_TH))
    for k, d in data.items():
        if not ('2000' in d and '200' in d):
            continue
        adj = {p: d[p]['heat_removed_W'] - (ref - d[p]['peak_C']) / R_TH for p in ('200', '2000')}
        print('  %-20s %.3f W -> %.3f W   = %.2fx   (raw %.2fx)'
              % (k, adj['200'], adj['2000'], adj['2000'] / adj['200'],
                 d['2000']['heat_removed_W'] / d['200']['heat_removed_W']))
    print('`[!]` The correction REVERSES the ordering, so the raw ratio must not be quoted: the '
          'granularity penalty does not clearly move with the curve.')
    return data


def report():
    data = {k: {c: read_point(t, c) for c in CFMS} for k, t in TREES.items()}
    data = {k: {c: v for c, v in d.items() if v} for k, d in data.items()}

    print('=== rescue survival (control diverges AND array holds) ===')
    print('%-20s %s' % ('curve', '  '.join('%5s' % c for c in CFMS)))
    survival = {}
    for k, d in data.items():
        cells, n = [], 0
        for c in CFMS:
            if c not in d:
                cells.append('  -  '); continue
            r = is_rescue(d[c])
            cells.append(' YES ' if r else (' no  ' if r is False else ' ??? '))
            n += 1 if r else 0
        survival[k] = n
        print('%-20s %s   -> %d/%d' % (k, '  '.join(cells), n, len(d)))

    print('\n=== control-arm loop gain G at the runaway call (no re-solve) ===')
    print('%-20s %s' % ('curve', '  '.join('%5s' % c for c in CFMS)))
    for k, d in data.items():
        print('%-20s %s' % (k, '  '.join(
            '%5.2f' % d[c]['control_loop_gain']['loop_gain_G']
            if c in d and d[c]['control_loop_gain'] else '  -  ' for c in CFMS)))
    print('%-20s %s' % ('residual at call K', '  '.join(
        '%5.0f' % data['pipeline'][c]['control_loop_gain']['residual_from_K']
        if c in data.get('pipeline', {}) and data['pipeline'][c]['control_loop_gain'] else '  -  '
        for c in CFMS)))
    print('%-20s %s' % ('  (simulated)', '  '.join(
        '%5.0f' % data['simulated'][c]['control_loop_gain']['residual_from_K']
        if c in data.get('simulated', {}) and data['simulated'][c]['control_loop_gain'] else '  -  '
        for c in CFMS)))

    print('\n=== array_on: what the rescue COSTS, and where it lands ===')
    print('%-20s %-6s %8s %9s %9s %9s' % ('curve', 'cfm', 'peak C', 'net W', 'chip W', 'removed W'))
    for k, d in data.items():
        for c in CFMS:
            if c not in d:
                continue
            a = d[c]['array_on']
            print('%-20s %-6s %8s %9s %9s %9s' % (
                k, c,
                '%.2f' % a['peak_C'] if a['peak_C'] is not None else '--',
                '%.3f' % a['p_mr_net_W'] if a['p_mr_net_W'] is not None else '--',
                '%.2f' % a['p_chip_W'] if a['p_chip_W'] is not None else '--',
                '%.3f' % a['heat_removed_W'] if a['heat_removed_W'] is not None else '--'))

    clip = clipping_report()
    pitch = pitch_report()

    doc = {'note': __doc__, 'trees': TREES, 'points': data,
           'clipping_trees': CLIP_TREES, 'clipping': clip,
           'pitch_trees': PITCH_TREES, 'pitch': pitch,
           'rescues_surviving': survival,
           'rescue_definition': 'control diverged AND array_on converged; unconverged counts as '
                                'neither (same rule as the density ladder)'}
    out = os.path.join(_EV, 'mr_catalogue_curve_compare.json')
    with open(out, 'w') as f:
        json.dump(doc, f, indent=1)
    print('\nwritten: %s' % out)
    return doc


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    report()
