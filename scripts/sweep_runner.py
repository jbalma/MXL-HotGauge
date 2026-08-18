#!/usr/bin/env python
"""Run many study points in ONE process, so they share a factorisation.

    python scripts/sweep_runner.py examples/accelerator_study.py points.json
    python scripts/sweep_runner.py examples/accelerator_study.py -  <<< '[["--die-power-W","400"]]'

Why this exists
---------------
``ICESessionCache`` reuses a 3D-ICE factorisation while the system matrix is unchanged, and the
matrix depends on the stack and the floorplan **geometry** -- not on power values. So sweeping die
power, the kernel, the MR target or ``dt_max`` costs one factorisation for the whole sweep, while
sweeping airflow, the grid or the die costs one each.

The cache cannot cross a process boundary, and our batch scripts run one process per point. An
audit of the accelerator study found **42 runs sharing 4 distinct matrices** -- 38 redundant
factorisations, 4.6 hours at the GA100 die's 431 s, paid for nothing. This runs the points in a
single process instead, so the cache does its job.

What it does NOT do is parallelise. A batch that runs 4 points at once on 4 cores finishes a
matrix-DIVERSE sweep sooner than this does; the win here is for matrix-IDENTICAL sweeps, where
those 4 processes were each paying full price for the same factorisation. Pick per sweep: group
points by matrix, run each group in one process, run the groups in parallel.

Points file: a JSON list, each entry a list of command-line arguments for the target script.
``--out-dir`` is appended automatically from the entry's index unless the entry sets one.
"""
import os
import sys
import json
import time
import runpy
import argparse
import traceback


def load_points(path):
    text = sys.stdin.read() if path == '-' else open(path).read()
    pts = json.loads(text)
    if not isinstance(pts, list) or not all(isinstance(p, list) for p in pts):
        raise SystemExit('points file must be a JSON list of argv lists')
    return [[str(a) for a in p] for p in pts]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('script', help='study script to run, e.g. examples/accelerator_study.py')
    ap.add_argument('points', help='JSON file of argv lists, or - for stdin')
    ap.add_argument('--out-root', default=None,
                    help='parent directory for per-point --out-dir when a point does not set one')
    ap.add_argument('--keep-going', action='store_true',
                    help='continue after a point raises, instead of stopping the sweep')
    args = ap.parse_args()

    points = load_points(args.points)
    script = os.path.abspath(args.script)
    if not os.path.isfile(script):
        raise SystemExit('no such script: {}'.format(script))

    results, t_sweep = [], time.time()
    for i, argv in enumerate(points):
        if '--out-dir' not in argv:
            root = args.out_root or os.path.join(os.getcwd(), 'sweep')
            argv = argv + ['--out-dir', os.path.join(root, 'point_{:02d}'.format(i))]
        print('\n' + '=' * 78)
        print('[sweep] point {}/{}: {}'.format(i + 1, len(points), ' '.join(argv)))
        print('=' * 78, flush=True)
        t0 = time.time()
        old_argv = sys.argv
        sys.argv = [script] + argv
        status = 'ok'
        try:
            # run_path re-executes the module each time. That is deliberate: only the study's
            # module-level session cache is meant to persist, and it does, because runpy caches
            # nothing while the cache lives in the module object the study itself imports.
            runpy.run_path(script, run_name='__main__')
        except SystemExit as e:
            if e.code not in (0, None):
                status = 'exit {}'.format(e.code)
        except Exception:
            status = 'raised'
            traceback.print_exc()
            if not args.keep_going:
                sys.argv = old_argv
                raise
        finally:
            sys.argv = old_argv
        dt = time.time() - t0
        results.append({'point': i, 'argv': argv, 'status': status, 'seconds': dt})
        print('[sweep] point {} {} in {:.1f} s'.format(i, status, dt), flush=True)

    total = time.time() - t_sweep
    print('\n[sweep] {} points in {:.1f} s ({:.1f} min)'.format(len(points), total, total / 60))
    for r in results:
        print('   point {:<3d} {:<10s} {:8.1f} s'.format(r['point'], r['status'], r['seconds']))
    n_bad = sum(1 for r in results if r['status'] != 'ok')
    return 1 if n_bad else 0


if __name__ == '__main__':
    sys.exit(main())
