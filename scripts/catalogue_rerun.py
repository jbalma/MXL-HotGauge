#!/usr/bin/env python
"""Plan the P0.5 catalogue re-run: enumerate the points, partition them by system matrix, and
emit one ``sweep_runner.py`` stream per partition.

    python scripts/catalogue_rerun.py --out results/rerun_plan          # plan only
    python scripts/catalogue_rerun.py --out results/rerun_plan --launch # ...and write the launcher

Why the plan is generated rather than written
---------------------------------------------
The catalogue is 80,330 solves (``docs/EXECUTION_PLAN.md`` s2), every one of them computed with
the cooling in the die's own source layer instead of in the array above it. Re-running it cold is
63.5 days; warm -- reusing each factorisation across every point that shares its system matrix --
is about 9 hours. That 169x is the entire reason P0.1 came first, and it is only collected if the
points are actually **grouped by matrix**, which the batch scripts do not do: they run one process
per point, and a process cannot share a factorisation with another one.

So this script does not define the catalogue. **The batch scripts in this directory define it**,
and this reads them -- by running each with a printing stand-in for ``srun`` -- so there is no
second copy to drift. A point added to a batch script is in the re-run automatically; a point
this script invents is a point nobody reviewed.

What the matrix key is, and why getting it wrong is only slow
-------------------------------------------------------------
``ice_server.matrix_fingerprint`` hashes the rendered ``.stk`` and every powered die's floorplan
GEOMETRY. In driver arguments that is: the floorplan (core count, node, accelerator grid), the
sink (``--cfm`` / ``--r-th`` / ambient), the stack (``--stack``, and under ``auto`` the burial
depth, pixel material and cell), and the tile grid (``--pitch-um``, ``--cell-um``). It is NOT the
die power, the density, the MR target, the spot policy, dt_max, the COP, the kernel shape or the
clock -- those are the right-hand side.

The key below is computed from arguments, so it is **conservative**: two points with the same key
certainly share a matrix; two points with different keys might also share one and simply will not
be pooled. That asymmetry is deliberate and it is what makes this safe -- ``ICESessionCache``
re-checks the real fingerprint on every solve and rebuilds when it differs, so a wrong key costs
factorisations and can never produce a wrong temperature.

Three arms, and what they do to the arithmetic
----------------------------------------------
Every mr_comparison / clock_headroom point now emits three arms, and the control arm's stack
(30 um of grease) is a DIFFERENT matrix from the array arms' (30 um of GaAs pixels). So a point
that used to need one factorisation needs two, and runs three arms' worth of solves. The plan
reports both counts; do not read the old 9 hours as still current.
"""
import os
import re
import sys
import math
import json
import stat
import shlex
import shutil
import argparse
import tempfile
import subprocess
import collections

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

#: Batch scripts that contribute points. Ordered as the catalogue families are in
#: docs/EXECUTION_PLAN.md s1, biggest first, because that is the order to start them in.
BATCH_SCRIPTS = ('cooling_for_rated_clock.sh', 'overnight3_study.sh', 'nextsteps_batch.sh',
                 'gapfill_batch.sh', 'cliff_reverify.sh', 'overnight_study.sh',
                 'followon_study.sh', 'design_study_batch.sh', 'accel_mr_batch.sh',
                 'dtmax_batch.sh', 'accel_batch.sh', 'kernel_batch.sh')

#: Arguments that are part of the SYSTEM MATRIX. Everything else is the right-hand side.
#: Grouped so the reason each one is here is inspectable rather than remembered.
MATRIX_ARGS = (
    # floorplan geometry
    '--cores', '--node', '--tech-node', '--flp', '--flp-template', '--flp-dir',
    '--no-split-sm', '--cell-um', '--mem-dies', '--mem-die-um', '--bond-um',
    '--mem-banks-x', '--mem-banks-y',
    # the boundary: render_stack_with_sink writes the heat transfer coefficient into the .stk
    '--cfm', '--r-th', '--ambient-K', '--cooling-fluid', '--cooling-flow-m3s',
    '--cooling-target-C', '--inlet-C',
    # the stack itself. --spreading belongs here because it takes the cold-plate slab OUT of
    # the stack (stack_for_spreading amends the spec at runtime, so the argument list is the only
    # place a planner can see it) and replaces the boundary condition.
    '--stack', '--burial-um', '--mr-material', '--no-array', '--spreading', '--base-mm2',
    # the tile grid -- a second powered die's floorplan is as much of the matrix as the first's
    '--pitch-um',
)

#: Measured, docs/evidence/session_memory.json. (peak GB, factorise s, solve s per session)
SESSION_COST = {34: {'peak_GB': 2.829, 'factorise_s': 67.78, 'solve_s': 0.385},
                128: {'peak_GB': 14.42, 'factorise_s': 722.61, 'solve_s': 1.916}}

#: Solves one ARM costs, counted rather than guessed: 80,330 solves over 144 distinct run
#: directories at two arms each (docs/EXECUTION_PLAN.md s1, from the ``iter_*`` directories, not
#: an estimate). It is large because every point is a leakage fixed point inside an MR descent,
#: and the clock family bisects on top of that.
#:
#: It is an AVERAGE over very unequal families -- clock is 24,591 solves over 28 rows and
#: stacked is 195 over 9 -- so a per-stream estimate carries that error. It is used for
#: BALANCING, where being wrong costs some idle cores, and for a headline figure that is
#: labelled as an estimate. It is not used for anything that has to be right.
SOLVES_PER_ARM = 80330.0 / (144 * 2)


def session_cost(cores):
    """Peak GB / factorise s / solve s for a session on an ``cores``-core die.

    Interpolated between the two measured points on unknowns, which go roughly as the core
    count. Outside them it clamps rather than extrapolating -- a made-up number for a die nobody
    has measured would be used to size concurrency, and over-subscribing the node is how a
    nine-hour run becomes a swap storm.
    """
    lo, hi = 34, 128
    if cores <= lo:
        return dict(SESSION_COST[lo])
    if cores >= hi:
        return dict(SESSION_COST[hi])
    f = (cores - lo) / float(hi - lo)
    return {k: SESSION_COST[lo][k] + f * (SESSION_COST[hi][k] - SESSION_COST[lo][k])
            for k in SESSION_COST[lo]}


def enumerate_points(repo, scripts, out_root):
    """Every driver invocation the batch scripts would issue, without issuing any of them.

    The scripts are copied to a scratch tree with ``REPO`` repointed at it, so their
    already-complete checks find nothing and every point is enumerated -- including the ones that
    would be skipped in the real results tree. ``srun`` is shadowed by a shim that prints the
    payload of ``bash -lc "..."`` instead of running it.

    **Every enumerated ``--out-dir`` is re-rooted under ``out_root``**, and that is not cosmetic.
    The batch scripts build their out-dirs from ``$REPO``, which the copy repointed at the scratch
    tree -- so the enumerated commands say ``--out-dir /tmp/catalogue_rerun_XXXX/results/...``.
    That path is deleted when enumeration finishes, and ``sweep_runner`` only supplies an
    ``--out-dir`` for points that do not already carry one, so the whole re-run would faithfully
    recreate the deleted scratch tree on the COMPUTE NODE's local disk and write every result
    into it. Nothing errors; the run just produces nothing anybody can find, and node-local /tmp
    is not on NFS so it does not survive the allocation either. Caught after 108 MB of a live run
    had gone there.

    The re-rooting keeps the batch structure -- ``<out_root>/<batch>/<tag>`` -- so the tags stay
    meaningful instead of collapsing to point_00, point_01, ...
    """
    tmp = tempfile.mkdtemp(prefix='catalogue_rerun_')
    os.makedirs(os.path.join(tmp, 'scripts'), exist_ok=True)
    os.makedirs(os.path.join(tmp, 'bin'), exist_ok=True)
    for f in os.listdir(os.path.join(repo, 'scripts')):
        if f.endswith('.sh'):
            src = open(os.path.join(repo, 'scripts', f)).read()
            src = src.replace('REPO={}'.format(repo), 'REPO={}'.format(tmp))
            open(os.path.join(tmp, 'scripts', f), 'w').write(src)
    # Three shims, and all three are load-bearing:
    #   srun    prints the payload of `bash -lc "..."` instead of running it.
    #   sleep   a no-op. Every batch script throttles with `while jobs -rp >= MAX_CONC; sleep 10`,
    #           and although the shimmed srun exits immediately, bash can still report the job as
    #           running for an instant -- so the enumeration pays 10 s per point and a 40-point
    #           script takes minutes to enumerate nothing.
    #   pgrep   always false. followon_study.sh blocks on `while pgrep -f overnight_study.sh` by
    #           design, which is right when running and a deadlock when enumerating.
    shims = {
        'srun': ('#!/usr/bin/env bash\nargs=("$@")\n'
                 'for ((i=0;i<${#args[@]};i++)); do\n'
                 '  case "${args[$i]}" in -c|-lc) printf "%s\\n" "${args[$((i+1))]}"; exit 0;; esac\n'
                 'done\nprintf "CMD: %s\\n" "$*"\n'),
        'sleep': '#!/usr/bin/env bash\nexit 0\n',
        'pgrep': '#!/usr/bin/env bash\nexit 1\n',
    }
    for name, body in shims.items():
        path = os.path.join(tmp, 'bin', name)
        open(path, 'w').write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    env = dict(os.environ)
    env['PATH'] = os.path.join(tmp, 'bin') + os.pathsep + env['PATH']
    points, failed = [], []
    for name in scripts:
        path = os.path.join(tmp, 'scripts', name)
        if not os.path.isfile(path):
            failed.append((name, 'not found')); continue
        try:
            r = subprocess.run(['bash', path, '9999'], capture_output=True, text=True,
                               cwd=tmp, env=env, timeout=180)
            stdout = r.stdout
        except subprocess.TimeoutExpired as e:
            # Keep whatever it managed to print, and SAY it was cut short -- a silently
            # truncated enumeration is a silently truncated re-run.
            stdout = (e.stdout or b'').decode('utf-8', 'replace') if isinstance(e.stdout, bytes) \
                else (e.stdout or '')
            failed.append((name, 'TIMED OUT after 180 s -- points may be missing'))
        found = 0
        for line in stdout.split('\n'):
            m = re.search(r'python (?:-u )?(examples/[a-z_]+\.py) (.*)$', line)
            if not m:
                continue
            argv = shlex.split(re.sub(r'\s*>\s*\S+\.log.*$', '', m.group(2)))
            argv = _reroot_paths(argv, tmp, out_root, repo)
            points.append({'script': name, 'driver': m.group(1), 'argv': argv})
            found += 1
        if not found:
            failed.append((name, 'enumerated no points'))
    shutil.rmtree(tmp, ignore_errors=True)
    return points, failed


def _reroot_paths(argv, tmp, out_root, repo):
    """Repoint every scratch-tree path at something real.

    The batch scripts build paths from ``$REPO``, and the enumeration copy repoints ``$REPO`` at
    a temporary tree -- so EVERY such path comes out under ``/tmp/catalogue_rerun_XXXX``, not
    just ``--out-dir``. There are two kinds and they go to different places:

    * **outputs** (``--out-dir``, always under ``$REPO/results/``) are re-rooted at ``out_root``,
      keeping the ``<batch>/<tag>`` structure so the tags stay meaningful.
    * **inputs** (``--trace-dir``, ``--flp-template``, ``--leakage-cal``, ...) are re-rooted at
      the REAL repo, because that is where the data actually is. The scratch tree only ever
      contained copies of the shell scripts.

    Fixing only ``--out-dir`` was the first version of this, and it left
    ``--trace-dir /tmp/catalogue_rerun_XXXX/mcpat_runs/10nm/linpack_3.8GHz`` intact -- which
    killed the whole generational family of ``followon_study.sh`` mid-run with a bare
    FileNotFoundError, five points after the stream had been running happily.
    """
    out = list(argv)
    for i, tok in enumerate(out):
        if i + 1 >= len(out):
            continue
        val = out[i + 1]
        if not isinstance(val, str) or not val.startswith(tmp):
            continue
        rel = os.path.relpath(val, tmp)
        parts = rel.split(os.sep)
        if tok == '--out-dir':
            if parts and parts[0] == 'results':
                parts = parts[1:]
            out[i + 1] = os.path.join(out_root, *parts) if parts else out_root
        else:
            out[i + 1] = os.path.join(repo, rel)
    return out


def matrix_key(point):
    """A conservative, order-independent key for the system matrix a point needs.

    **Last occurrence wins, because that is what argparse does.** A flag can legitimately appear
    twice: the shared argument groups in ``scripts/array_config.sh`` supply a default
    ``--pitch-um 500`` and a pitch-ladder point then appends its own rung, so the argv really
    does read ``--pitch-um 500 ... --pitch-um 2000``. The run is correct -- argparse keeps 2000 --
    and taking both would key a 500 um point that overrode itself to 500 differently from a plain
    500 um point, splitting one matrix into two groups and paying its factorisation twice.
    """
    argv, seen = point['argv'], collections.OrderedDict()
    for i, tok in enumerate(argv):
        if tok not in MATRIX_ARGS:
            continue
        vals = []
        j = i + 1
        while j < len(argv) and not argv[j].startswith('--'):
            vals.append(argv[j]); j += 1
        seen[tok] = ','.join(vals)          # later assignment replaces the earlier one
    parts = ['{}={}'.format(k, v) for k, v in seen.items()]
    return '{}|{}'.format(point['driver'], ' '.join(sorted(parts)))


def cores_of(point):
    argv = point['argv']
    if '--cores' in argv:
        try:
            return int(float(argv[argv.index('--cores') + 1]))
        except (ValueError, IndexError):
            pass
    if point['driver'].endswith('accelerator_study.py'):
        return 128        # GA100 class: use the large-die session cost, not the CPU default
    return 34


def n_arms(point):
    """Arms this invocation runs, which is also roughly its solve multiplier."""
    argv = point['argv']
    if point['driver'].endswith(('mr_comparison.py', 'clock_headroom.py')):
        if '--no-array' in argv:
            return 2
        if point['driver'].endswith('clock_headroom.py') and '--mr' not in argv:
            return 1
        return 3
    return 1


def n_matrices(point):
    """Distinct matrices ONE invocation needs. Three arms means two stacks, not one."""
    return 2 if n_arms(point) >= 2 and '--no-array' not in point['argv'] else 1


def group_cost(pts, solves_per_arm):
    c = max(cores_of(p) for p in pts)
    cost = session_cost(c)
    nm = n_matrices(pts[0])
    factor_s = nm * cost['factorise_s']
    solve_s = sum(n_arms(p) for p in pts) * cost['solve_s'] * solves_per_arm
    return {'cores': c, 'factor_s': factor_s, 'solve_s': solve_s,
            'seconds': factor_s + solve_s, 'peak_GB': cost['peak_GB'] * nm}


def build_groups(points, solves_per_arm, max_streams, split_ratio):
    """Matrix groups, with the CRITICAL-PATH group split only as far as it needs to be.

    Points sharing a matrix key must share a session or the factorisation is paid twice -- that
    is the whole 169x, and it is the default. But one group here holds over a hundred
    mr_comparison points on a single matrix, and left whole it is ten hours of solving while the
    rest of the node idles. Splitting a group in two costs one extra factorisation and halves its
    solve time, which is worth it exactly while that group is the thing everyone else is waiting
    for.

    So the rule is not "split big groups" -- that is how the first version of this ended up
    splitting almost everything down to single points, which is the COLD re-run wearing a
    different hat. It is:

      split the longest group, and only it, while
        * it is longer than an even share of the total work (it IS the critical path), and
        * its solve time is worth at least ``split_ratio`` factorisations (the extra
          factorisation buys more than it costs), and
        * it still has more than one point to give.

    Everything else stays whole.
    """
    keyed = collections.OrderedDict()
    for p in points:
        keyed.setdefault(matrix_key(p), []).append(p)
    groups = [dict(group_cost(pts, solves_per_arm), key=key, points=pts, of=1)
              for key, pts in keyed.items()]

    n_split = 0
    while True:
        total = sum(g['seconds'] for g in groups)
        even_share = total / float(max(max_streams, 1))
        g = max(groups, key=lambda g: g['seconds'])
        if g['seconds'] <= even_share:
            break                      # nothing dominates the critical path any more
        if len(g['points']) < 2:
            break                      # indivisible
        if g['solve_s'] <= split_ratio * g['factor_s']:
            break                      # another factorisation would cost more than it saves
        half = len(g['points']) // 2
        groups.remove(g)
        for chunk in (g['points'][:half], g['points'][half:]):
            groups.append(dict(group_cost(chunk, solves_per_arm), key=g['key'],
                               points=chunk, of=g['of'] + 1))
        n_split += 1
    for g in groups:
        g['was_split'] = g['of'] > 1
    return groups, n_split


def partition(groups, max_streams):
    """Pack groups into streams, longest first onto the shortest stream that can take it.

    **A stream is single-driver**, and that constraint is not cosmetic. ``sweep_runner.py`` runs
    ONE script over one points file, so a mixed stream has to be split into several processes at
    launch time -- and then the stream count the memory budget was computed against is no longer
    the number of things actually running. An earlier version of this did exactly that: it
    planned 11 streams and generated a launcher that wanted to run 30 processes. Keeping a stream
    equal to a process means the plan's arithmetic is the launcher's arithmetic.
    """
    groups = sorted(groups, key=lambda g: -g['seconds'])
    streams = [{'groups': [], 'seconds': 0.0, 'peak_GB': 0.0, 'driver': None}
               for _ in range(min(max_streams, len(groups)) or 1)]
    for g in groups:
        drv = g['key'].split('|')[0]
        ok = [s for s in streams if s['driver'] in (None, drv)]
        if not ok:
            # Every stream already belongs to another driver. Take the shortest one anyway and
            # let it grow a second driver -- reported, not hidden, because it is the one case
            # where a stream becomes two processes.
            ok = streams
        st = min(ok, key=lambda s: s['seconds'])
        st['groups'].append(g)
        st['seconds'] += g['seconds']
        st['peak_GB'] = max(st['peak_GB'], g['peak_GB'])
        st['driver'] = drv if st['driver'] in (None, drv) else 'MIXED'
    return [s for s in streams if s['groups']]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(_REPO, 'results', 'rerun_plan'))
    ap.add_argument('--scripts', nargs='+', default=list(BATCH_SCRIPTS))
    ap.add_argument('--max-streams', type=int, default=None,
                    help='concurrent sweep_runner processes. Default: as many as --mem-GB '
                         'allows. node-06 is 96 CPU / 243 GB and a solve is single-threaded, so '
                         'the cap is MEMORY, not cores -- one factorised two-die accelerator '
                         'session is ~14 GB and a three-arm point holds two of them')
    ap.add_argument('--mem-GB', type=float, default=200.0,
                    help='memory budget. Peak RSS is ~1.3x steady RSS; size on PEAK or the node '
                         'over-subscribes during the factorisation transient')
    ap.add_argument('--launch', action='store_true', help='also write run_rerun.sh')
    ap.add_argument('--solves-per-arm', type=float, default=SOLVES_PER_ARM,
                    help='average solves one arm costs (default %(default).0f, counted from the '
                         'old catalogue). Used for BALANCING and for a labelled estimate, '
                         'nothing that has to be right')
    ap.add_argument('--split-ratio', type=float, default=4.0,
                    help='how many factorisations of solve time one chunk may hold before a '
                         'matrix group is split across streams. Lower = more parallelism, more '
                         'repeated factorisations')
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    points, failed = enumerate_points(_REPO, args.scripts, os.path.abspath(args.out))
    for name, why in failed:
        print('  WARNING: {} {}'.format(name, why))
    if not points:
        raise SystemExit('no points enumerated -- did the batch scripts change shape?')

    # Refuse to emit a plan whose results would land anywhere but the output tree. This guards a
    # specific failure that already happened: the enumerated --out-dir is built from the scratch
    # tree's $REPO, and if it is not re-rooted the whole run recreates the deleted enumeration
    # directory on the COMPUTE NODE's local disk and writes every result into it -- silently, and
    # off NFS, so it does not survive the allocation either.
    stray, leaked = [], []
    for pt in points:
        a = pt['argv']
        v = a[a.index('--out-dir') + 1] if '--out-dir' in a else None
        if v is None or not os.path.abspath(v).startswith(os.path.abspath(args.out) + os.sep):
            stray.append((pt['script'], v))
        # ANY surviving scratch path, not just the out-dir -- --trace-dir got through once.
        for tok in a:
            if isinstance(tok, str) and 'catalogue_rerun_' in tok:
                leaked.append((pt['script'], tok))
    if stray:
        raise SystemExit(
            '{} point(s) would write outside {} -- e.g. {!r} from {}. The enumerated --out-dir '
            'was not re-rooted, so the run would write into a deleted scratch tree. See '
            '_reroot_paths.'.format(len(stray), args.out, stray[0][1], stray[0][0]))
    if leaked:
        raise SystemExit(
            '{} argument(s) still point into the enumeration scratch tree -- e.g. {!r} from {}. '
            'Every $REPO-derived path must be re-rooted, not only --out-dir. See _reroot_paths.'
            .format(len(leaked), leaked[0][1], leaked[0][0]))

    # How many streams the memory allows, before anything is split: the widest group sets it,
    # because any stream might end up holding it.
    probe, _ = build_groups(points, args.solves_per_arm, 1, args.split_ratio)
    worst_GB = max(g['peak_GB'] for g in probe)
    allowed = max(1, int(args.mem_GB // worst_GB))
    max_streams = args.max_streams or allowed
    if max_streams > allowed:
        print('  --max-streams {} exceeds what {:.0f} GB allows ({}); using {}'
              .format(max_streams, args.mem_GB, allowed, allowed))
        max_streams = allowed

    groups, n_splits = build_groups(points, args.solves_per_arm, max_streams, args.split_ratio)
    streams = partition(groups, max_streams)

    n_groups = sum(len(s['groups']) for s in streams)
    n_arm_total = sum(n_arms(p) for p in points)
    n_matrix_total = sum(n_matrices(g['points'][0]) for s in streams for g in s['groups'])

    print('catalogue re-run plan')
    print('  points          : {} invocations from {} batch scripts'.format(
        len(points), len(set(p['script'] for p in points))))
    print('  arms            : {} (three per planner point -- control, array_idle, array_on)'
          .format(n_arm_total))
    print('  distinct matrices: {} in {} groups'.format(n_matrix_total, n_groups))
    n_mixed = sum(1 for s in streams if s['driver'] == 'MIXED')
    print('  streams         : {} concurrent, peak {:.1f} GB of a {:.0f} GB budget ({:.1f} GB '
          'is the widest\n                    single session -- that is what caps concurrency, '
          'not the 96 cores)'
          .format(len(streams), sum(s['peak_GB'] for s in streams), args.mem_GB, worst_GB))
    longest = max(s['seconds'] for s in streams)
    total = sum(s['seconds'] for s in streams)
    n_split = sum(1 for s in streams for g in s['groups'] if g['was_split'])
    factor_h = sum(g['factor_s'] for s in streams for g in s['groups']) / 3600.0
    solve_h = sum(g['solve_s'] for s in streams for g in s['groups']) / 3600.0
    print('  solves          : ~{:,.0f} at {:.0f} per arm (COUNTED from the old catalogue, but '
          'an average over\n                    very unequal families -- treat the hours as an '
          'estimate)'.format(n_arm_total * args.solves_per_arm, args.solves_per_arm))
    print('  estimated       : {:.1f} h total = {:.1f} h factorising + {:.1f} h solving'
          .format(total / 3600.0, factor_h, solve_h))
    print('                    {:.1f} h wall on the longest stream'.format(longest / 3600.0))
    if n_split:
        print('  {} split(s) applied to the critical-path matrix, giving {} chunks that run '
              'concurrently.\n  Each chunk re-pays its factorisation and the estimate above '
              'includes that.'.format(n_splits, n_split))
    print()
    print('  {:>7s} {:>8s} {:>9s} {:>8s}  {}'.format('stream', 'groups', 'points', 'est h',
                                                     'biggest group'))
    manifest = []
    for i, s in enumerate(streams):
        pts = [p for g in s['groups'] for p in g['points']]
        path = os.path.join(args.out, 'stream_{:02d}.json'.format(i))
        with open(path, 'w') as f:
            json.dump([p['argv'] for p in pts], f, indent=1)
        big = max(s['groups'], key=lambda g: len(g['points']))
        manifest.append({'stream': i, 'points_file': path, 'n_groups': len(s['groups']),
                         'n_points': len(pts), 'est_seconds': s['seconds'],
                         'peak_GB': s['peak_GB'],
                         'drivers': sorted(set(p['driver'] for p in pts))})
        print('  {:>7d} {:>8d} {:>9d} {:>8.2f}  {} x{}'.format(
            i, len(s['groups']), len(pts), s['seconds'] / 3600.0,
            big['key'].split('|')[0].replace('examples/', ''), len(big['points'])))

    mixed = [m for m in manifest if len(m['drivers']) > 1]
    if mixed:
        print('\n  NOTE: {} stream(s) hold more than one driver and become that many processes '
              'at launch,\n  so concurrency may briefly exceed {}. Raise --mem-GB or lower '
              '--max-streams if the node is shared.'.format(len(mixed), len(streams)))

    plan = {'note': 'P0.5 catalogue re-run, partitioned by system matrix. Points are enumerated '
                    'from the batch scripts, not restated here.',
            'n_points': len(points), 'n_arms': n_arm_total, 'n_matrices': n_matrix_total,
            'solves_per_arm': args.solves_per_arm,
            'est_solves': n_arm_total * args.solves_per_arm,
            'est_total_h': total / 3600.0, 'est_wall_h': longest / 3600.0,
            'est_factorise_h': factor_h, 'est_solve_h': solve_h,
            'n_groups_split': n_split,
            'streams': manifest,
            'points': [{'script': p['script'], 'driver': p['driver'], 'argv': p['argv'],
                        'matrix_key': matrix_key(p), 'arms': n_arms(p)} for p in points]}
    with open(os.path.join(args.out, 'plan.json'), 'w') as f:
        json.dump(plan, f, indent=1)
    print('\n  written: {}'.format(os.path.join(args.out, 'plan.json')))

    if args.launch:
        write_launcher(args.out, plan, points, args.mem_GB)
    return 0


def write_launcher(out, plan, points, mem_GB):
    """One sweep_runner process per (stream, driver). Restartable, throttled, logs per stream.

    The split by driver is forced -- ``sweep_runner.py`` runs ONE script over one points file --
    and it breaks the plan's memory arithmetic, because a stream that was costed as one process
    becomes up to three. So the launcher does not inherit the stream count as its concurrency; it
    recomputes one from the largest per-process peak and the memory budget, and throttles.
    Firing all of them at once is how a three-hour run becomes a swap storm.
    """
    idx = {tuple(p['argv']): p for p in points}
    by = collections.OrderedDict()
    for m in plan['streams']:
        for a in json.load(open(m['points_file'])):
            by.setdefault((m['stream'], idx[tuple(a)]['driver']), []).append(a)

    procs = []
    for (stream, driver), argvs in by.items():
        pts = [idx[tuple(a)] for a in argvs]
        c = group_cost(pts, plan['solves_per_arm'])
        procs.append({'stream': stream, 'driver': driver, 'argvs': argvs,
                      'peak_GB': c['peak_GB'], 'seconds': c['seconds']})
    # Longest first: the critical path must not queue behind a one-point stream.
    procs.sort(key=lambda p: -p['seconds'])
    worst_GB = max(p['peak_GB'] for p in procs)
    max_conc = max(1, int(mem_GB // worst_GB))

    L = []
    A = L.append
    A('#!/usr/bin/env bash')
    A('#')
    A('# Generated by scripts/catalogue_rerun.py -- do not edit; regenerate.')
    A('#')
    A('#   scripts/run_rerun.sh <slurm_jobid>')
    A('#   MAX_CONC=6 scripts/run_rerun.sh <slurm_jobid>     # share the node')
    A('#')
    A('# One sweep_runner process per (stream, driver). Every point inside one shares a system')
    A('# matrix with its neighbours, so the factorisation is paid once per group rather than')
    A('# once per point -- that is the 169x the whole ordering of Phase 0 was chosen for.')
    A('#')
    A('# Concurrency is bounded by MEMORY, not by cores. A solve is single-threaded and node-06')
    A('# has 96 of them, but one factorised two-die session is %.1f GB on the largest die here,'
      % worst_GB)
    A('# so %d processes fill a %.0f GB budget. Sized on PEAK RSS, which runs ~1.3x steady'
      % (max_conc, mem_GB))
    A('# (docs/evidence/session_memory.json) -- sizing on steady oversubscribes the node during')
    A('# exactly the factorisation transient that makes it peak.')
    A('#')
    A('# Restartable: a finished stream leaves a .done marker and is skipped on the next run.')
    A('set -uo pipefail')
    A('JOBID="${1:?usage: run_rerun.sh <slurm_jobid>}"')
    A('REPO=%s' % _REPO)
    A('OUT=%s' % out)
    A('MAX_CONC="${MAX_CONC:-%d}"' % max_conc)
    A('mkdir -p "$OUT/logs"')
    A('log() { printf "[%s] %s\\n" "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }')
    A('throttle() { while [ "$(jobs -rp | wc -l)" -ge "$MAX_CONC" ]; do sleep 20; done; }')
    A('')
    A('log "=== catalogue re-run: %d streams, max concurrency $MAX_CONC ==="' % len(procs))
    A('log "    estimated %.1f h of solver work, %.1f h wall"'
      % (plan['est_total_h'], plan['est_wall_h']))

    for pr in procs:
        tag = 'sf{:02d}_{}'.format(pr['stream'], os.path.basename(pr['driver'])[:-3])
        pf = os.path.join(out, tag + '.json')
        with open(pf, 'w') as f:
            json.dump(pr['argvs'], f, indent=1)
        A('')
        A('# %d point(s), ~%.2f h, %.1f GB peak'
          % (len(pr['argvs']), pr['seconds'] / 3600.0, pr['peak_GB']))
        A('if [ -f "$OUT/logs/%s.done" ]; then log "SKIP %s"; else' % (tag, tag))
        A('  throttle')
        A('  log "START %s (%d points)"' % (tag, len(pr['argvs'])))
        A('  srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none bash -lc \\')
        A('    ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && '
          'OMP_NUM_THREADS=1 python -u scripts/sweep_runner.py %s %s --keep-going '
          '--out-root $OUT/%s > $OUT/logs/%s.log 2>&1 && touch $OUT/logs/%s.done" &'
          % (pr['driver'], pf, tag, tag, tag))
        A('fi')

    A('')
    A('log "all streams queued; waiting"')
    A('wait')
    A('log "=== catalogue re-run COMPLETE ==="')
    A('')
    A('# P0.5 acceptance: every row must carry a placement stamp, so this generation of results')
    A('# is distinguishable from the last one by inspection rather than by date.')
    A('srun --jobid="$JOBID" --overlap bash -lc \\')
    A('  ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && '
      'python scripts/collect_findings.py > $OUT/FINDINGS.txt 2>&1" || true')
    A('log "findings at $OUT/FINDINGS.txt"')

    path = os.path.join(_HERE, 'run_rerun.sh')
    open(path, 'w').write('\n'.join(L) + '\n')
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print('  written: {}'.format(path))
    print('  {} processes, max concurrency {} (largest session {:.1f} GB of a {:.0f} GB budget)'
          .format(len(procs), max_conc, worst_GB, mem_GB))


if __name__ == '__main__':
    sys.exit(main())
