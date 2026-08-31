#!/usr/bin/env python
"""Regress the surviving floorplan metric against the cost of holding a margin, across floorplans.

    python examples/isa_metric_regression.py results/isa_benefit_pack --arm iso

Why this exists
---------------
Of five candidate phase-1 floorplan metrics, exactly one predicts across both kinds of variation:
**plateau width as a fraction of the die's own temperature span, against the watts it costs to
hold a demanded margin** -- rho +0.84 over eleven workloads on one floorplan, +1.00 over four
floorplans, +1.00 over six. ``hot_region_depth`` was built and dropped within a day because its
sign reverses across floorplans, and both outcomes are in ``docs/evidence/``.

This is the arithmetic that produced those rho values, lifted out of the shell so the re-run on
the pack-rebuilt floorplans uses the same code rather than the same intention.

Where the numbers come from, and it is not arbitrary
-----------------------------------------------------
* The **metric** is read from the ``array_idle`` arm -- the unaided state of the arm being
  planned, same stack and same array with the laser off. Reading it from the ``control`` arm
  would fold the 14 K passive grease-to-GaAs step into the shape being measured, and reading it
  from ``array_on`` would measure a die the plan has already flattened.
* The **cost** is ``array_on.heat_removed_W``: the watts of heat the planner had to move to hold
  the demanded margin. Lower is a better MR target.
* A point with no steady state contributes NOTHING and is reported. A runaway is not a large
  cost, it is an absent one, and averaging it in as a big number would invert the ranking.
"""
import os
import re
import sys
import json
import argparse

try:
    from scipy.stats import spearmanr
except ImportError:                                   # pragma: no cover
    spearmanr = None


def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    """Spearman rho, with a local fallback so the analysis does not need scipy to run."""
    if len(xs) < 3:
        return None, None
    if spearmanr is not None:
        rho, p = spearmanr(xs, ys)
        return float(rho), float(p)
    rx, ry = _rank(xs), _rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return (num / den if den else None), None


def read_point(path):
    """One sweep point -> the metric, the cost, and whether it converged at all."""
    with open(path) as f:
        d = json.load(f)
    by_arm = {r['arm']: r for r in d['rows']}
    idle = by_arm.get('array_idle')
    on = by_arm.get('array_on')
    if idle is None or on is None:
        return None
    out = {'density': d.get('density'), 'diverged': bool(idle.get('diverged'))}
    if idle.get('diverged') or on.get('diverged'):
        out['diverged'] = True
        return out
    out.update({
        'relative_plateau_25pct': idle.get('relative_plateau_25pct'),
        'relative_plateau_share': idle.get('relative_plateau_share'),
        'die_span_K': idle.get('die_span_K'),
        'peak_to_runner_up_gap_K': idle.get('peak_to_runner_up_gap_K'),
        'unaided_peak_C': idle.get('peak_C'),
        'peak_block': idle.get('peak_block'),
        'area_mm2': idle.get('area_mm2'),
        'power_W': idle.get('power_W'),
        'cost_W': on.get('heat_removed_W'),
        'unconverged': bool(idle.get('unconverged') or on.get('unconverged')),
    })
    return out


def collect(root, arm=None):
    """Every point under ``root``, keyed by (arm, variant, offset)."""
    pat = re.compile(r'^(?:(iso|published)_)?(.+)_off(\d+)$')
    pts = {}
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name, 'mr_comparison.json')
        if not os.path.isfile(p):
            continue
        m = pat.match(name)
        if not m:
            continue
        a, variant, off = m.group(1) or 'iso', m.group(2), int(m.group(3))
        if arm and a != arm:
            continue
        r = read_point(p)
        if r is not None:
            pts[(a, variant, off)] = r
    return pts


def regress(points, metric='relative_plateau_25pct', against='cost_W'):
    """rho(metric, cost) at each margin separately, then pooled.

    Per-margin is the honest unit: the cost of 3 K and the cost of 8 K are different quantities
    and pooling them mixes a within-floorplan trend into a between-floorplan one.
    """
    out = {'per_margin': {}, 'excluded': []}
    offs = sorted({k[2] for k in points})
    for off in offs:
        rows = [(k[1], v) for k, v in points.items() if k[2] == off]
        good = [(n, v) for n, v in rows if not v['diverged'] and v.get(against) is not None]
        bad = [n for n, v in rows if v['diverged']]
        if bad:
            out['excluded'] += ['{} @ {}K (no steady state)'.format(n, off) for n in sorted(bad)]
        if len(good) < 3:
            out['per_margin'][off] = {'n': len(good), 'rho': None,
                                      'why': 'fewer than 3 convergent floorplans'}
            continue
        xs = [v[metric] for _, v in good]
        ys = [v[against] for _, v in good]
        rho, p = spearman(xs, ys)
        out['per_margin'][off] = {
            'n': len(good), 'rho': rho, 'p': p,
            'floorplans': [n for n, _ in good],
            'metric': [round(x, 4) if isinstance(x, float) else x for x in xs],
            'cost_W': [round(y, 4) for y in ys]}
    rhos = [d['rho'] for d in out['per_margin'].values() if d.get('rho') is not None]
    out['rho_mean'] = sum(rhos) / len(rhos) if rhos else None
    out['n_margins_with_a_rho'] = len(rhos)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root', nargs='+', help='sweep result directories')
    ap.add_argument('--arm', default=None, choices=('iso', 'published'))
    ap.add_argument('--metric', default='relative_plateau_25pct')
    ap.add_argument('--json-out', default=None)
    args = ap.parse_args()

    report = {}
    for root in args.root:
        pts = collect(root, args.arm)
        if not pts:
            print('{}: no points'.format(root))
            continue
        arms = sorted({k[0] for k in pts})
        for a in arms:
            sub = {k: v for k, v in pts.items() if k[0] == a}
            print('\n=== {}  [{}]  {} points ==='.format(root, a, len(sub)))
            hdr = '{:<18s} {:>4s} {:>8s} {:>7s} {:>8s} {:>7s} {:>8s} {:>8s}'.format(
                'floorplan', 'offK', 'area', 'P_die', 'peak C', 'plateau', 'span K', 'cost W')
            print(hdr)
            print('-' * len(hdr))
            for (_, v, off) in sorted(sub, key=lambda k: (k[1], k[2])):
                r = sub[(a, v, off)]
                if r['diverged']:
                    print('{:<18s} {:>4d} {:>8s} {:>7s} {:>8s} {:>7s} {:>8s} {:>8s}'.format(
                        v, off, '--', '--', 'RUNAWAY', '--', '--', '--'))
                    continue
                print('{:<18s} {:>4d} {:>8.1f} {:>7.1f} {:>8.2f} {:>7d} {:>8.2f} {:>8.4f}{}'
                      .format(v, off, r['area_mm2'], r['power_W'], r['unaided_peak_C'],
                              r['relative_plateau_25pct'], r['die_span_K'], r['cost_W'],
                              '  ** UNCONVERGED **' if r['unconverged'] else ''))
            res = regress(sub, metric=args.metric)
            print('\nrho({} , cost) per margin:'.format(args.metric))
            for off, d in sorted(res['per_margin'].items()):
                if d.get('rho') is None:
                    print('  {:>2d} K : n={}  -- {}'.format(off, d['n'], d['why']))
                else:
                    print('  {:>2d} K : n={}  rho = {:+.3f}  (p={:.3g})'.format(
                        off, d['n'], d['rho'], d['p'] if d['p'] is not None else float('nan')))
            if res['excluded']:
                print('  excluded, no steady state: {}'.format(', '.join(res['excluded'])))
            report['{}|{}'.format(os.path.basename(root.rstrip('/')), a)] = {
                'points': {'{}|{}'.format(k[1], k[2]): v for k, v in sub.items()},
                'regression': res}

    if args.json_out:
        with open(args.json_out, 'w') as f:
            json.dump(report, f, indent=1)
        print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
