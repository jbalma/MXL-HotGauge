#!/usr/bin/env python
"""Compare the four catalogue re-run arms, one flag at a time (§P0.16).

    python examples/catalogue_arm_compare.py

The arms form a CHAIN, each differing from the previous by exactly one flag, so every difference
has a single cause:

    A  pipeline  + stock     + stock                   <- same-code control
    B  simulated + stock     + stock                   <- A->B = the leakage curve
    C  simulated + amortized + stock                   <- B->C = the RBB policy
    D  simulated + amortized + hierarchy-consistent    <- C->D = the core_other accounting

`[!]` **Arm A is the control, NOT the recorded catalogue.** §P0.15 established that the recorded
rows predate the RBB work, the residual/backtracking convergence fix and `verify=True`, so
"treating it as a reproduction target would have read a real improvement as a regression". A vs the
recorded tree is reported separately and labelled as *code drift*, never as a defect.

`[!]` **An `unconverged` row is neither holding nor failing** and is counted as neither, the same
rule the density ladder uses. A flip is only counted between two decided verdicts.

`[!]` **Do not read a partial campaign.** The driver reports each arm's completeness and refuses to
summarise a pair unless both arms have the point.
"""
import os
import re
import sys
import json
import glob
import argparse
import collections

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')

ARMS = ('A', 'B', 'C', 'D')
ARM_FLAGS = {
    'A': ('pipeline', 'stock', 'stock'),
    'B': ('simulated', 'stock', 'stock'),
    'C': ('simulated', 'amortized', 'stock'),
    'D': ('simulated', 'amortized', 'hierarchy-consistent'),
}
#: what each adjacent pair isolates
STEPS = (('A', 'B', 'the leakage curve'),
         ('B', 'C', 'the RBB policy'),
         ('C', 'D', 'the core_other accounting'))


def arm_root(arm):
    return os.path.join(_REPO, 'results', 'rerun_arm_%s' % arm)


def verdict(row):
    """'unconverged' | 'diverged' | 'holds' -- unconverged is neither of the other two."""
    if row.get('unconverged'):
        return 'unconverged'
    return 'diverged' if row.get('diverged') else 'holds'


#: Drivers that cannot complete on this toolchain at all (§P0.16): `stacked_memory_study.py` fails
#: with `ICESteadySim failed` after ~75 min per point. It accepts none of the re-run flags, so its
#: points are identical in every arm and inform no comparison. This is a property of the DRIVER,
#: so it is the one exclusion that can be stated without looking at a log.
BROKEN_DRIVERS = ('stacked_memory_study.py',)

_RAISED = re.compile(r'^\[sweep\] point (\d+) raised', re.M)


def raised_out_dirs(arm):
    """Out-dirs the sweep runner ATTEMPTED and that raised, for one arm, read from its own logs.

    `[!]` This replaces a fixed `--mr-target-C <= 45` rule, which was **wrong**. That rule came
    from bracketing the `__agg__L3` planner bug with two real points -- `A_ceiling_T50` completing
    and `A_ceiling_T40` raising -- in **arm D**. The same point 16 (`A_ceiling_T50`) then **raised
    in arm B**. The bug fires when the synthetic `__agg__L3` key's TEMPERATURE exceeds the target,
    and that temperature depends on the leakage curve and the core_other policy. So the trigger is
    physics-dependent and arm-dependent, and no fixed target threshold can express it.

    What a completeness guard actually needs is not the cause but the state: a point is *done*,
    *attempted and failed*, or *not yet run*. Only the last means the arm is unfinished. That
    distinction is read straight off `[sweep] point N raised` lines, needs no threshold, and cannot
    drift.
    """
    out = set()
    root = arm_root(arm)
    for lg in glob.glob(os.path.join(root, 'logs', '*.log')):
        stream = os.path.join(root, os.path.basename(lg)[:-4] + '.json')
        if not os.path.exists(stream):
            continue
        try:
            pts = json.load(open(stream))
            txt = open(lg, errors='replace').read()
        except Exception:
            continue
        for m in _RAISED.finditer(txt):
            i = int(m.group(1))
            if 0 <= i < len(pts):
                a = pts[i]
                if '--out-dir' in a:
                    out.add(a[a.index('--out-dir') + 1])
    return out


def is_broken_driver(point):
    """True for a point whose DRIVER cannot complete at all (arm-independent)."""
    return any(d in point.get('driver', '') for d in BROKEN_DRIVERS)


def arm_completeness(arm):
    """``(n_with_output, n_planned, [missing out-dirs])`` for one arm, FROM ITS PLAN.

    `[!]` Counting ``*.json`` under the arm root is not a completeness check and reads high: the
    tree also holds one ``sf<NN>_<driver>.json`` argv file per stream plus the plan itself. Counting
    ``mr_comparison.json`` reads low, because several catalogue drivers are not
    ``mr_comparison``. The plan's own ``--out-dir`` list is the only authoritative denominator --
    it is what the run was asked to produce.

    `[!]` A stream's ``.done`` marker is also not sufficient: one arm-D stream completed all 33 of
    its points and left no marker, so marker-counting understates completeness while json-counting
    overstates it. Ask the plan.
    """
    plan = os.path.join(arm_root(arm), 'plan.json')
    if not os.path.exists(plan):
        return 0, 0, []
    want, broken = [], set()
    for pt in json.load(open(plan))['points']:
        a = pt['argv']
        if '--out-dir' not in a:
            continue
        d = a[a.index('--out-dir') + 1]
        want.append(d)
        if is_broken_driver(pt):
            broken.add(d)
    failed = raised_out_dirs(arm)
    excluded = broken | failed
    missing = [w for w in want if not glob.glob(os.path.join(w, '*.json'))]
    reachable = [w for w in want if w not in excluded]
    pending = [w for w in missing if w not in excluded]
    return (len(reachable) - len(pending), len(reachable), pending, len(excluded))


def load_arm(arm):
    """``{relpath: {armname: row}}`` for every mr_comparison point in one arm tree."""
    root = arm_root(arm)
    out = {}
    for fp in glob.glob(os.path.join(root, '**', 'mr_comparison.json'), recursive=True):
        rel = os.path.relpath(os.path.dirname(fp), root)
        try:
            doc = json.load(open(fp))
        except Exception:
            continue
        rows = {r['arm']: r for r in doc.get('rows', []) if 'arm' in r}
        if rows:
            out[rel] = rows
    return out


def compare(lo, hi, data, mr_arm='control'):
    """Verdict flips and temperature moves for one adjacent pair, on one MR arm."""
    a, b = data.get(lo, {}), data.get(hi, {})
    common = sorted(set(a) & set(b))
    flips, peaks, undecided = collections.Counter(), [], 0
    for k in common:
        ra, rb = a[k].get(mr_arm), b[k].get(mr_arm)
        if not ra or not rb:
            continue
        va, vb = verdict(ra), verdict(rb)
        if 'unconverged' in (va, vb):
            undecided += 1
            continue
        flips[(va, vb)] += 1
        if va == vb == 'holds' and ra.get('peak_C') is not None and rb.get('peak_C') is not None:
            peaks.append(rb['peak_C'] - ra['peak_C'])
    # JSON keys must be strings: the flip counter is keyed by a (from, to) verdict pair.
    return {'n_common': len(common),
            'flips': {'%s->%s' % k: v for k, v in flips.items()},
            'n_undecided': undecided,
            'n_peak_pairs': len(peaks),
            'mean_dpeak_K': (sum(peaks) / len(peaks)) if peaks else None,
            'max_dpeak_K': (max(peaks, key=abs) if peaks else None)}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mr-arm', default='control',
                    choices=['control', 'array_idle', 'array_on'],
                    help='which MR arm to compare (default control -- the arm whose divergence '
                         'the rescue claim and the density ceiling both rest on)')
    ap.add_argument('--json-out', default=os.path.join(_EV, 'catalogue_arm_compare.json'))
    args = ap.parse_args()

    data = {a: load_arm(a) for a in ARMS}
    comp = {a: arm_completeness(a) for a in ARMS}
    print('%-5s %-11s %-11s %-22s %16s %s'
          % ('arm', 'curve', 'rbb', 'core_other', 'reachable done', 'excluded'))
    for a in ARMS:
        done, want, _, unreach = comp[a]
        print('%-5s %-11s %-11s %-22s %10d/%-5d %d' % ((a,) + ARM_FLAGS[a] + (done, want, unreach)))
    print('  ("excluded" = a broken driver (stacked_memory_study) plus every point this arm '
          'ATTEMPTED\n   and that raised -- read from its own [sweep] logs, not from a target '
          'threshold. The\n   __agg__L3 bug is arm-dependent: point 16 raised in B and completed '
          'in D.)')
    incomplete = [a for a in ARMS if comp[a][1] == 0 or comp[a][0] < comp[a][1]]
    if incomplete:
        print('\n`[!]` ARMS NOT COMPLETE: %s. Pairs below cover only their shared points, and '
              'NOTHING here should be quoted until every arm reads N/N.'
              % ', '.join('%s (%d/%d)' % (a, comp[a][0], comp[a][1]) for a in incomplete))
    else:
        print('\n`[+]` All arms complete on every reachable point.')

    print('\n=== one flag at a time, on the %s arm ===' % args.mr_arm)
    steps = {}
    for lo, hi, what in STEPS:
        c = compare(lo, hi, data, args.mr_arm)
        steps['%s->%s' % (lo, hi)] = dict(c, isolates=what)
        changed = {k: v for k, v in c['flips'].items()
                   if k.split('->')[0] != k.split('->')[1]}
        print('\n%s -> %s  (%s):  %d shared points, %d undecided'
              % (lo, hi, what, c['n_common'], c['n_undecided']))
        if not c['n_common']:
            print('   (no shared points yet)')
            continue
        same = sum(v for k, v in c['flips'].items()
                   if k.split('->')[0] == k.split('->')[1])
        print('   verdict unchanged: %d' % same)
        for lbl, k in sorted(changed.items(), key=lambda x: -x[1]):
            print('   **%s: %d points**' % (lbl.replace('->', ' -> '), k))
        if c['mean_dpeak_K'] is not None:
            print('   peak temperature on points holding in BOTH: mean %+.2f K, largest %+.2f K '
                  '(%d pairs)' % (c['mean_dpeak_K'], c['max_dpeak_K'], c['n_peak_pairs']))

    doc = {'note': __doc__, 'arm_flags': {a: ARM_FLAGS[a] for a in ARMS},
           'mr_arm': args.mr_arm,
           'completeness': {a: {'done': comp[a][0], 'reachable': comp[a][1],
                                'missing': comp[a][2][:20],
                                'known_unreachable': comp[a][3]} for a in ARMS},
           'complete': not incomplete,
           'steps': steps}
    with open(args.json_out, 'w') as f:
        json.dump(doc, f, indent=1)
    print('\nwritten: %s' % args.json_out)


if __name__ == '__main__':
    main()
