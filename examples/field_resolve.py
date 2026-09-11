#!/usr/bin/env python
"""X1/X2 (§P0.27): re-solve a RECORDED final power map once, linearly, through the persistent
3D-ICE session, and write the per-block temperature field the leakage loop converged on but never
saved. The session path renders ``IC.stk`` / ``IC.flp`` / ``MR.flp`` and spawns no emulator, so a
solve tree holds every iteration's POWERS and no TEMPERATURES -- this puts the field beside them.

    python examples/field_resolve.py --run results/array_coverage_armD/c1.00/d2.00/34c_array_on \\
        --expect-removed-W 138.7288 --expect-peak-C 93.875 \\
        --out results/fields/rescue_d2.00_array_on/field.json

Which iteration is re-solved
----------------------------
An ``array_on`` tree has one ``itNN`` per planner pass, and the LAST one is the bisection's largest
FAILING plan, not the minimum (checked on d2.00 before this was written: it10's ``MR.flp`` sums to
-137.91 W against the recorded 138.73 W minimum). So the pass is selected by ``--expect-removed-W``
-- the row's own ``heat_removed_W`` -- and within it the last ``iter_NNN`` (the last solve the loop
made; the verification re-solve at half damping, within the loop's 1 K of the reported field).
Control and idle trees have one pass. ``--expect-peak-C`` is recorded beside the re-solved peak so
the report can score prediction P0 (agreement within 1 K); it does not gate the write.

`[!]` Needs the node: one session start is one factorisation (~90 s and several GB at 691k
unknowns). ``--dry-run`` does the selection and parsing only and is safe on the head node.
"""
import os
import re
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

_BLOCK = re.compile(r'^(\S+)\s*:\s*\n\s*position\s+([\d.eE+-]+)\s*,\s*([\d.eE+-]+)\s*;\s*\n'
                    r'\s*dimension\s+([\d.eE+-]+)\s*,\s*([\d.eE+-]+)\s*;\s*\n'
                    r'\s*power values\s+([^;]*);', re.M)


def parse_flp(path):
    """``{name: (x_um, y_um, w_um, h_um, P_W)}`` from a rendered .flp (first slot if a series)."""
    out = {}
    with open(path) as f:
        s = f.read()
    for m in _BLOCK.finditer(s):
        vals = [float(v) for v in m.group(6).replace('\n', ' ').split(',') if v.strip()]
        out[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)),
                           float(m.group(5)), vals[-1])
    if not out:
        raise ValueError('no blocks parsed from {}'.format(path))
    return out


def _last_iter(pass_dir):
    its = sorted(glob.glob(os.path.join(pass_dir, 'iter_*')))
    its = [d for d in its if os.path.isfile(os.path.join(d, 'IC.stk'))]
    if not its:
        raise RuntimeError('no iter_*/IC.stk under {}'.format(pass_dir))
    return its[-1]


def select_iteration(run, expect_removed_W=None, tol_W=0.05):
    """The ``itNN/iter_NNN`` whose MR plan matches the recorded removal (or the only pass)."""
    passes = sorted(glob.glob(os.path.join(run, 'it[0-9]*')))
    if not passes:
        raise RuntimeError('no itNN passes under {}'.format(run))
    if expect_removed_W is None or len(passes) == 1:
        return _last_iter(passes[-1]), None
    best = None
    for p in passes:
        it = _last_iter(p)
        mr = os.path.join(it, 'MR.flp')
        if not os.path.isfile(mr):
            continue
        q = -sum(v[4] for v in parse_flp(mr).values())
        d = abs(q - expect_removed_W)
        if best is None or d < best[0]:
            best = (d, it, q)
    if best is None:
        raise RuntimeError('no pass under {} carries an MR.flp'.format(run))
    if best[0] > tol_W:
        raise RuntimeError('no pass under {} matches the recorded removal {:.3f} W (closest {:.3f} W '
                           'in {}); refusing to re-solve a plan the row does not report'
                           .format(run, expect_removed_W, best[2], best[1]))
    return best[1], best[2]


def resolve(iter_dir, dry_run=False):
    stk = os.path.join(iter_dir, 'IC.stk')
    ic = parse_flp(os.path.join(iter_dir, 'IC.flp'))
    mr_path = os.path.join(iter_dir, 'MR.flp')
    mr = parse_flp(mr_path) if os.path.isfile(mr_path) else {}
    powers = {n: v[4] for n, v in ic.items()}
    powers.update({n: v[4] for n, v in mr.items()})
    res = {'iter_dir': iter_dir, 'stack': stk, 'n_blocks': len(ic), 'n_tiles': len(mr),
           'sum_P_W': sum(v[4] for v in ic.values()), 'sum_MR_W': sum(v[4] for v in mr.values())}
    if dry_run:
        return res, ic, mr, None
    from HotGauge.thermal.ice_server import ICEServerSession
    with ICEServerSession(stk, n_elements=len(ic) + len(mr)) as sess:
        temps = sess.solve_named(powers, strict=True)
    missing = [n for n in ic if n not in temps]
    if missing:
        raise RuntimeError('{} processor blocks have no temperature in the reply, e.g. {}'
                           .format(len(missing), missing[:5]))
    return res, ic, mr, temps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', required=True, help='an arm directory holding itNN/iter_NNN/IC.stk')
    ap.add_argument('--expect-removed-W', type=float, default=None,
                    help="the row's heat_removed_W; selects the planner pass to re-solve")
    ap.add_argument('--expect-peak-C', type=float, default=None, help="the row's peak_C (recorded, not enforced)")
    ap.add_argument('--label', default=None)
    ap.add_argument('--out', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    iter_dir, q = select_iteration(args.run, args.expect_removed_W)
    res, ic, mr, temps = resolve(iter_dir, dry_run=args.dry_run)
    res.update({'run': args.run, 'label': args.label, 'expect_removed_W': args.expect_removed_W,
                'expect_peak_C': args.expect_peak_C, 'selected_plan_W': q, 'dry_run': bool(args.dry_run)})
    blocks = {}
    for n, (x, y, w, h, p) in ic.items():
        blocks[n] = {'x_um': x, 'y_um': y, 'w_um': w, 'h_um': h, 'P_W': p,
                     'T_K': (None if temps is None else float(temps[n]))}
    res['blocks'] = blocks
    res['tiles'] = {n: {'x_um': x, 'y_um': y, 'w_um': w, 'h_um': h, 'P_W': p} for n, (x, y, w, h, p) in mr.items()}
    if temps is not None:
        pk = max(blocks, key=lambda n: blocks[n]['T_K'])
        res.update({'peak_K': blocks[pk]['T_K'], 'peak_C': blocks[pk]['T_K'] - 273.15, 'peak_block': pk,
                    'min_K': min(b['T_K'] for b in blocks.values())})
        if args.expect_peak_C is not None:
            res['peak_error_K'] = res['peak_C'] - args.expect_peak_C
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(res, f, indent=1)
    print('{}: {} blocks, {} tiles, P {:.2f} W, MR {:.2f} W{}'.format(
        args.label or args.run, len(ic), len(mr), res['sum_P_W'], res['sum_MR_W'],
        '' if temps is None else ', peak {:.2f} C at {} (recorded {}{})'.format(
            res['peak_C'], res['peak_block'], args.expect_peak_C,
            '' if args.expect_peak_C is None else ', err {:+.2f} K'.format(res['peak_error_K']))))
    print('written:', args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
