#!/usr/bin/env python
"""§P0.43: the MATCHED CoMeT memory-arrangement sweep -- what near memory buys, measured.

    python examples/comet_mem_arrangement_report.py     # -> docs/evidence/comet_mem_arrangement.json

Reads ``CoMeT/test/mem_arrangement_sweep/<bench>/<arrangement>/run_<f>/sim.out``: same binary, same
cores, same clocks; the arrangement (DDR 45 ns / 1 controller, 3Dmem 29 ns / 4, 2.5D 20 ns / 4, 3D
15 ns / 4) the only variable. Throughput is total instructions / wall time of the region; per
arrangement a two-parameter fit  t_per_instruction = a / f + b  (b = the memory floor the clock does
not touch) and the elasticity of throughput to clock, (a/f) / (a/f + b). Memory-bank temperatures
are CoMeT's own thermal model's (final sample). One workload class (SPLASH-2 small inputs, 4 cores).
"""
import os
import re
import sys
import json
import glob

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = '/mnt/nfs01/scratch/jbalma/CoMeT/test/mem_arrangement_sweep'
ORDER = ('gainestown_DDR', 'gainestown_3Dmem', 'gainestown_2_5D', 'gainestown_3D')


def row_of(d):
    so = os.path.join(d, 'sim.out')
    if not os.path.isfile(so):
        return None
    o = open(so).read()
    if 'Instructions' not in o:
        return None                      # an empty sim.out: the run died (reported as missing)
    nums = lambda rx: [float(x) for x in re.search(rx, o, re.M).group(1).split('|') if x.strip() not in ('', 'inf', 'nan')]
    ins = sum(nums(r'^\s*Instructions\s*\|(.*)$'))
    t_ns = max(nums(r'^\s*Time \(ns\)\s*\|(.*)$'))
    lat = nums(r'average dram access latency \(ns\)\s*\|(.*)$')
    q = nums(r'average dram queueing delay\s*\|(.*)$')
    acc = nums(r'num dram accesses\s*\|(.*)$')
    miss = re.search(r'Cache L2.*?num cache misses\s*\|(.*?)$', o, re.S | re.M)
    l2m = sum(float(x) for x in miss.group(1).split('|') if x.strip()) if miss else None
    r = {'instructions': ins, 'time_ns': t_ns, 'GIPS': ins / t_ns, 'dram_latency_ns': float(np.mean(lat)) if lat else None,
         'dram_queue_ns': float(np.mean(q)) if q else None, 'dram_accesses': sum(acc) if acc else None, 'L2_misses': l2m}
    tt = os.path.join(d, 'combined_temperature.trace')
    if not os.path.isfile(tt):
        tt = os.path.join(d, 'full_temperature_mem.trace')
    if os.path.isfile(tt):
        L = open(tt).read().strip().split('\n')
        if len(L) > 1:
            hdr = L[0].split('\t')
            last = [float(x) for x in L[-1].split('\t') if x != '']
            n = min(len(hdr), len(last))
            mem = [last[i] for i in range(n) if hdr[i].startswith('B_')]
            core = [last[i] for i in range(n) if hdr[i].startswith('C_')]
            r.update({'mem_max_C': max(mem) if mem else None, 'core_max_C': max(core) if core else None})
    return r


def main():
    out = {}
    for bd in sorted(glob.glob(os.path.join(BASE, '*-*'))):
        if not os.path.isdir(bd):
            continue
        bench = os.path.basename(bd)
        out[bench] = {}
        for arr in ORDER:
            runs = {}
            for d in glob.glob(os.path.join(bd, arr, 'run_*')):
                r = row_of(d)
                if r:
                    runs[float(d.rsplit('_', 1)[1])] = r
            if len(runs) >= 2:
                f = np.array(sorted(runs)); t = np.array([1.0 / runs[x]['GIPS'] for x in f])      # ns per instruction (all cores)
                A = np.vstack([1.0 / f, np.ones_like(f)]).T
                (a, b), res = np.linalg.lstsq(A, t, rcond=None)[:2]
                fit = {'a_ns_GHz': float(a), 'b_ns': float(b), 'max_rel_err': float(np.max(np.abs(A @ [a, b] - t) / t)),
                       'elasticity': {('%g' % x): float((a / x) / (a / x + b)) for x in f}}
            else:
                fit = None
            out[bench][arr] = {'runs': {('%g' % k): v for k, v in sorted(runs.items())}, 'fit': fit}
    for bench, arrs in out.items():
        print('\n%s   (G instr/s, all cores; vs 2.5D at the same clock)' % bench)
        fs = sorted({float(k) for a in arrs.values() for k in a['runs']})
        print('%-18s' % 'arrangement' + ''.join('%16s' % ('%g GHz' % f) for f in fs) + '   | floor b [ps]  elasticity @4 / @16   DRAM ns (+queue)   mem max C')
        ref = arrs.get('gainestown_2_5D', {}).get('runs', {})
        for arr in ORDER:
            a = arrs.get(arr)
            if not a or not a['runs']:
                continue
            cells = []
            for f in fs:
                r = a['runs'].get('%g' % f)
                rr = ref.get('%g' % f)
                cells.append('%16s' % ('--' if not r else ('%.3f (%+.0f%%)' % (r['GIPS'], 100 * (r['GIPS'] / rr['GIPS'] - 1)) if rr else '%.3f' % r['GIPS'])))
            fit = a['fit'] or {}
            e = fit.get('elasticity') or {}
            any_r = list(a['runs'].values())[-1]
            # the fastest runs can end before CoMeT's thermal sampling interval: take the hottest bank any run recorded
            mems = [r.get('mem_max_C') for r in a['runs'].values() if r.get('mem_max_C') is not None]
            any_r = dict(any_r, mem_max_C=(max(mems) if mems else None))
            print('%-18s' % arr.replace('gainestown_', '') + ''.join(cells) + '   | %10s  %9s / %-9s  %6s (+%s)   %s' % (
                '--' if not fit else '%.1f' % (1e3 * fit['b_ns']), '--' if '4' not in e else '%.2f' % e['4'], '--' if '16' not in e else '%.2f' % e['16'],
                '--' if any_r['dram_latency_ns'] is None else '%.1f' % any_r['dram_latency_ns'], '--' if any_r['dram_queue_ns'] is None else '%.1f' % any_r['dram_queue_ns'],
                '--' if any_r.get('mem_max_C') is None else '%.1f' % any_r['mem_max_C']))
    p = os.path.join(_REPO, 'docs', 'evidence', 'comet_mem_arrangement.json')
    json.dump({'note': __doc__.strip(), 'base': BASE, 'benchmarks': out}, open(p, 'w'), indent=1)
    print('\nwritten:', os.path.relpath(p, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
