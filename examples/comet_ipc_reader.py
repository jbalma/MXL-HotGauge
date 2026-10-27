#!/usr/bin/env python
"""§P0.33: IPC(f) per benchmark from CoMeT's frequency sweeps, so the memory wall can enter the
throughput claims.

    python examples/comet_ipc_reader.py            # -> docs/evidence/comet_ipc_vs_f.json

What it reads
-------------
CoMeT (Sniper + HotSpot) was run at 1-20 GHz with ONLY the core frequency changed between
configs (``gen_configs_core.sh``: ``sed 's/frequency =.*/frequency = N/'``), so the memory
system's latency stays fixed in nanoseconds and IPC falls with f. Per run directory:

* ``sim.out``       -- Instructions / Cycles / IPC / Time (ns) / Idle time per core;
* ``sim.cfg``       -- the frequency the run was configured at (``[perf_model/core] frequency``);
* ``PeriodicVdd.log`` / ``PeriodicFrequency.log`` -- the DVFS voltage and clock CoMeT assigned
  per core over the run (a two-level table, not a device curve -- see §P0.33 P4).

Two sweeps: ``thermal_example_test_1to20ghz/run_<f>`` (the FFT-style ``test`` kernel, one active
core of four, the densest sweep: 1-20 GHz in 2 GHz steps) and ``benchmarks_sweep/<bench>/run_<f>``
(SPLASH-2 / PARSEC on 4-16 cores, mostly 8 and 16 GHz, a few at 1-20).

What it writes
--------------
Per benchmark: the rows (f, per-core IPC, aggregate IPC over the ACTIVE cores, instructions,
cycles, wall time, Vdd), the speed-up against the lowest frequency, the elasticity
``d ln(throughput) / d ln f`` between adjacent points, and an ``IPC0 / (1 + f / f_k)`` fit where
three or more points exist. ``ipc_at(f)`` interpolates log-linearly between measured points --
the reports use it at the clock-search clocks (3.3-4.9 GHz), which FFT brackets with its 2, 4
and 6 GHz points.

`[!]` Only the frequency setting differs between CoMeT's configs. Nothing here says whether the
device can switch at 20 GHz; §P0.31's f_max model does.
"""
import os
import re
import sys
import json
import glob
import math
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
COMET_TEST = '/mnt/nfs01/scratch/jbalma/CoMeT/test'
EVIDENCE = os.path.join(_EV, 'comet_ipc_vs_f.json')

_ROW = re.compile(r'^\s*(Instructions|Cycles|IPC|Time \(ns\)|Idle time \(ns\))\s*\|(.*)$')


def parse_sim_out(path):
    rows = {}
    with open(path) as f:
        for line in f:
            m = _ROW.match(line)
            if m:
                vals = [v.strip() for v in m.group(2).split('|')]
                rows[m.group(1)] = [float(v) if v not in ('', '-') else float('nan') for v in vals]
            if rows and line.startswith('Branch predictor'):
                break
    if 'Instructions' not in rows or 'Cycles' not in rows:
        return None
    return rows


def cfg_frequency(rundir):
    p = os.path.join(rundir, 'sim.cfg')
    if not os.path.isfile(p):
        return None
    sect = None
    with open(p) as f:
        for line in f:
            s = line.strip()
            if s.startswith('['):
                sect = s
            elif sect == '[perf_model/core]' and s.startswith('frequency ='):
                return float(s.split('=')[1].strip().split()[0])
    return None


def last_log_row(path):
    """Last data row of a tab-separated per-core log (header 'Core0 Core1 ...'); None if absent."""
    if not os.path.isfile(path):
        return None
    last = None
    with open(path) as f:
        for line in f:
            if line.startswith('Core') or not line.strip():
                continue
            last = line
    if last is None:
        return None
    return [float(x) for x in last.split()]


def read_run(rundir):
    so = os.path.join(rundir, 'sim.out')
    if not os.path.isfile(so):
        return None
    rows = parse_sim_out(so)
    if rows is None:
        return None
    m = re.search(r'run_(\d+)$', rundir)
    f_dir = float(m.group(1)) if m else None
    f_cfg = cfg_frequency(rundir)
    f = f_cfg if f_cfg is not None else f_dir
    instr = np.array(rows['Instructions'])
    cyc = np.array(rows['Cycles'])
    active = instr > 0
    time_ns = rows.get('Time (ns)', [float('nan')])[0]
    ipc_core = [(i / c if c > 0 else 0.0) for i, c in zip(instr, cyc)]
    vdd = last_log_row(os.path.join(rundir, 'PeriodicVdd.log'))
    vdd_i = last_log_row(os.path.join(rundir, 'InstantVdd.log'))
    fper = last_log_row(os.path.join(rundir, 'PeriodicFrequency.log'))
    return {'run': os.path.relpath(rundir, COMET_TEST), 'f_GHz': f, 'f_dir_GHz': f_dir, 'f_cfg_GHz': f_cfg,
            'n_cores': int(len(instr)), 'n_active_cores': int(active.sum()),
            'instructions': [int(x) for x in instr], 'cycles': [int(x) for x in cyc],
            'ipc_per_core': ipc_core,
            'ipc_active_mean': float(np.mean([ipc_core[i] for i in range(len(instr)) if active[i]])) if active.any() else 0.0,
            'ipc_sum': float(sum(ipc_core)),
            'instructions_total': int(instr.sum()), 'time_ns': time_ns,
            'idle_ns': rows.get('Idle time (ns)'),
            'GIPS': (instr.sum() / time_ns) if time_ns and time_ns > 0 else None,   # instructions per ns = 1e9/s
            'vdd_V': vdd, 'vdd_instant_V': vdd_i, 'dvfs_f_GHz': fper}


def fit_knee(fs, ipcs):
    """``IPC(f) = IPC0 / (1 + f / f_k)`` by least squares on 1/IPC = (1/IPC0)(1 + f/f_k)."""
    fs, ipcs = np.asarray(fs, float), np.asarray(ipcs, float)
    ok = ipcs > 0
    if ok.sum() < 3:
        return None
    a, b = np.polyfit(fs[ok], 1.0 / ipcs[ok], 1)       # 1/IPC = b + a f
    if b <= 0 or a <= 0:
        return None
    ipc0, fk = 1.0 / b, b / a
    pred = ipc0 / (1.0 + fs[ok] / fk)
    res = np.abs(pred / ipcs[ok] - 1.0)
    return {'IPC0': float(ipc0), 'f_k_GHz': float(fk), 'max_abs_rel_residual': float(res.max()),
            'rms_rel_residual': float(np.sqrt(np.mean(res ** 2))), 'n_points': int(ok.sum())}


def benchmark_summary(name, runs):
    runs = sorted((r for r in runs if r and r['f_GHz']), key=lambda r: r['f_GHz'])
    if not runs:
        return None
    fs = [r['f_GHz'] for r in runs]
    ipc = [r['ipc_active_mean'] for r in runs]
    gips = [r['GIPS'] for r in runs]
    base = runs[0]
    speedup = [(base['time_ns'] / r['time_ns']) if (r['time_ns'] and base['time_ns']) else None for r in runs]
    elastic = []
    for a, b in zip(runs, runs[1:]):
        if a['GIPS'] and b['GIPS'] and a['f_GHz'] != b['f_GHz']:
            elastic.append({'from_GHz': a['f_GHz'], 'to_GHz': b['f_GHz'],
                            'elasticity': math.log(b['GIPS'] / a['GIPS']) / math.log(b['f_GHz'] / a['f_GHz']),
                            'ipc_ratio': (b['ipc_active_mean'] / a['ipc_active_mean']) if a['ipc_active_mean'] else None})
    return {'benchmark': name, 'n_runs': len(runs), 'f_GHz': fs, 'ipc_active_mean': ipc, 'GIPS': gips,
            'speedup_vs_lowest_f': speedup, 'n_active_cores': [r['n_active_cores'] for r in runs],
            'elasticity_adjacent': elastic, 'knee_fit': fit_knee(fs, ipc),
            'vdd_V_by_f': {'%g' % r['f_GHz']: r['vdd_V'] for r in runs},
            'runs': runs}


def ipc_at(summary, f_GHz):
    """IPC at ``f_GHz`` by log-linear interpolation between measured points (clamped at the ends)."""
    fs = np.asarray(summary['f_GHz'], float)
    ipc = np.asarray(summary['ipc_active_mean'], float)
    ok = ipc > 0
    fs, ipc = fs[ok], ipc[ok]
    if len(fs) == 0:
        return None
    if len(fs) == 1:
        return float(ipc[0])
    f = min(max(float(f_GHz), fs[0]), fs[-1])
    return float(math.exp(np.interp(math.log(f), np.log(fs), np.log(ipc))))


def load_ipc(path=EVIDENCE, benchmark='fft_1to20'):
    """The recorded evidence's summary for ``benchmark`` (for the reports)."""
    with open(path) as f:
        ev = json.load(f)
    return ev['benchmarks'][benchmark]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--comet-test', default=COMET_TEST)
    ap.add_argument('--json-out', default=EVIDENCE)
    args = ap.parse_args()
    benches = {}
    fft = [read_run(d) for d in glob.glob(os.path.join(args.comet_test, 'thermal_example_test_1to20ghz', 'run_*'))]
    benches['fft_1to20'] = benchmark_summary('fft_1to20', fft)
    sweep = os.path.join(args.comet_test, 'benchmarks_sweep')
    for bdir in sorted(glob.glob(os.path.join(sweep, '*'))):
        if not os.path.isdir(bdir) or not glob.glob(os.path.join(bdir, 'run_*')):
            continue
        name = os.path.basename(bdir)
        s = benchmark_summary(name, [read_run(d) for d in glob.glob(os.path.join(bdir, 'run_*'))])
        if s:
            benches[name] = s
    top = [read_run(d) for d in glob.glob(os.path.join(sweep, 'run_*'))]
    if any(top):
        benches['benchmarks_sweep_toplevel(lu.cont)'] = benchmark_summary('benchmarks_sweep_toplevel(lu.cont)', top)
    benches = {k: v for k, v in benches.items() if v}

    print('%-40s %5s  %s' % ('benchmark', 'runs', 'f GHz -> IPC(active mean) [GIPS]'))
    for name, s in benches.items():
        print('%-40s %5d  %s' % (name, s['n_runs'], '  '.join('%g->%.2f [%s]' % (f, i, '--' if g is None else '%.1f' % g)
                                                            for f, i, g in zip(s['f_GHz'], s['ipc_active_mean'], s['GIPS']))))
        if s['knee_fit']:
            print('%-40s        knee fit IPC0 %.2f, f_k %.1f GHz, max residual %.1f %%' % (
                '', s['knee_fit']['IPC0'], s['knee_fit']['f_k_GHz'], 100 * s['knee_fit']['max_abs_rel_residual']))
        for e in s['elasticity_adjacent']:
            print('%-40s        %g -> %g GHz: elasticity %.2f' % ('', e['from_GHz'], e['to_GHz'], e['elasticity']))

    # -- scorecard for §P0.33 --------------------------------------------------------------
    sc = {}
    f = benches.get('fft_1to20')
    if f and f['knee_fit']:
        k = f['knee_fit']
        sc['P1_fft_knee_fit'] = {'measured': k, 'verdict': ('confirmed' if 18 <= k['f_k_GHz'] <= 22 and k['max_abs_rel_residual'] <= 0.05
                                                            else ('FALSIFIED' if k['max_abs_rel_residual'] > 0.10 else 'NOT as predicted'))}
    if f:
        def elast(f0, f1):
            i0, i1 = ipc_at(f, f0), ipc_at(f, f1)
            return math.log((f1 * i1) / (f0 * i0)) / math.log(f1 / f0)
        e14, e26 = elast(3.664, 4.173), elast(3.324, 4.173)
        sc['P2_f1c_elasticity'] = {'measured': {'3.66->4.17': e14, '3.32->4.17': e26,
                                                'ipc_at_3.66': ipc_at(f, 3.664), 'ipc_at_4.17': ipc_at(f, 4.173)},
                                   'verdict': ('confirmed' if all(0.80 <= e <= 0.85 for e in (e14, e26))
                                               else ('FALSIFIED' if any(e < 0.70 or e > 0.95 for e in (e14, e26)) else 'NOT as predicted'))}

    def e8_16(name):
        # elasticity of instructions per second between 8 and 16 GHz on the interpolated IPC(f)
        s = benches.get(name)
        if not s or len(s['f_GHz']) < 2 or s['f_GHz'][0] > 8 or s['f_GHz'][-1] < 16:
            return None
        i8, i16 = ipc_at(s, 8.0), ipc_at(s, 16.0)
        return math.log((16.0 * i16) / (8.0 * i8)) / math.log(2.0) if i8 and i16 else None
    lu, sw, fft16 = e8_16('splash2_lu.cont-large-4'), e8_16('parsec_swaptions-small-4'), e8_16('fft_1to20')
    if lu is not None and sw is not None:
        sc['P3_multicore_elasticity_8_to_16'] = {'measured': {'lu.cont-large-4': lu, 'swaptions-small-4': sw, 'fft_1to20': fft16},
                                                 'verdict': ('confirmed' if 0.5 <= lu <= 0.7 and 0.85 <= sw <= 0.95
                                                             else ('FALSIFIED' if sw < lu else 'NOT as predicted'))}
    if f:
        vdd = {k: v for k, v in f['vdd_V_by_f'].items() if v}
        hi = [max(v) for k, v in vdd.items() if float(k) >= 4]
        sc['P4_comet_vdd_is_a_table'] = {'measured': vdd, 'verdict': ('confirmed' if hi and max(hi) - min(hi) < 1e-6 else 'NOT as predicted')}
    print('\nscorecard (§P0.33):')
    for k, v in sc.items():
        print('  %-34s %s   %s' % (k, v['verdict'], json.dumps(v['measured'])[:150]))
    out = {'note': __doc__.strip(), 'comet_test': args.comet_test, 'benchmarks': benches, 'scorecard': sc,
           'default_benchmark_for_reports': 'fft_1to20'}
    with open(args.json_out, 'w') as fh:
        json.dump(out, fh, indent=1)
    print('\nwritten: %s' % os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
