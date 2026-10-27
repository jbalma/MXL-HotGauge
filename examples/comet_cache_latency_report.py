#!/usr/bin/env python
"""§P0.45: the CoMeT CACHE-LATENCY sweep -- what a faster L2 / L3 is worth against the DRAM floor.

    python examples/comet_cache_latency_report.py     # -> docs/evidence/comet_cache_latency.json

Reads ``CoMeT/test/mem_arrangement_sweep/cachelat/<bench>/cl<pct>/run_<f>/sim.out`` (L2 + L3 data and
tag access times at <pct> % of the recorded) beside the §P0.43 2.5D rows at 100 % (same binary, same
cores, same 2.5D memory, 4 and 16 GHz). Per (bench, f): instructions per second against the 100 %
row; per bench: the two-parameter fit t = a / f + b at each scaling, so the clock term `a` (where
the cache cycles live) and the DRAM floor `b` are read separately. The V_t pricing (P7) is an
interpolation on these rows, stated as such.
"""
import os
import sys
import json
import glob

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
from comet_mem_arrangement_report import row_of, BASE          # noqa: E402

CL = os.path.join(BASE, 'cachelat')
SCALES = (50, 75, 100, 150)


def main():
    out = {}
    for bench in ('splash2-fft-small-4', 'splash2-lu.cont-small-4'):
        out[bench] = {}
        for s in SCALES:
            runs = {}
            pat = (os.path.join(BASE, bench, 'gainestown_2_5D', 'run_*') if s == 100
                   else os.path.join(CL, bench, 'cl%d' % s, 'run_*'))
            for d in glob.glob(pat):
                f = float(d.rsplit('_', 1)[1])
                if f not in (4.0, 16.0):
                    continue
                r = row_of(d)
                if r:
                    runs[f] = r
            fit = None
            if len(runs) >= 2:
                fs = np.array(sorted(runs)); t = np.array([1.0 / runs[x]['GIPS'] for x in fs])
                A = np.vstack([1.0 / fs, np.ones_like(fs)]).T
                a, b = np.linalg.lstsq(A, t, rcond=None)[0]
                fit = {'a_ns_GHz': float(a), 'b_ns': float(b),
                       'elasticity': {('%g' % x): float((a / x) / (a / x + b)) for x in fs}}
            out[bench]['%d' % s] = {'runs': {('%g' % k): v for k, v in sorted(runs.items())}, 'fit': fit}
    sc = {}
    for bench, by in out.items():
        print('\n%s   (G instr/s, all cores; vs the recorded 100 %% cache latency at the same clock)' % bench)
        print('%-8s %18s %18s   | a [ns GHz]   b [ps]   elasticity @4 / @16' % ('L2/L3 %', '4 GHz', '16 GHz'))
        ref = by.get('100', {}).get('runs', {})
        for s in SCALES:
            a = by.get('%d' % s)
            if not a or not a['runs']:
                print('%-8d %18s %18s' % (s, '--', '--'))
                continue
            cells = []
            for f in (4.0, 16.0):
                r = a['runs'].get('%g' % f); rr = ref.get('%g' % f)
                cells.append('%18s' % ('--' if not r else ('%.3f (%+.1f%%)' % (r['GIPS'], 100 * (r['GIPS'] / rr['GIPS'] - 1)) if rr else '%.3f' % r['GIPS'])))
            fit = a['fit'] or {}; e = fit.get('elasticity') or {}
            print('%-8d %s %s   | %10s %8s   %s / %s' % (
                s, cells[0], cells[1], '--' if not fit else '%.3f' % fit['a_ns_GHz'], '--' if not fit else '%.1f' % (1e3 * fit['b_ns']),
                '--' if '4' not in e else '%.2f' % e['4'], '--' if '16' not in e else '%.2f' % e['16']))
        # P6 scoring on this bench
        def gain(s, f):
            r = by.get('%d' % s, {}).get('runs', {}).get('%g' % f); rr = ref.get('%g' % f)
            return None if not (r and rr) else 100 * (r['GIPS'] / rr['GIPS'] - 1)
        g = {('%d_%g' % (s, f)): gain(s, f) for s in (50, 75, 150) for f in (4.0, 16.0)}
        b100 = (by.get('100', {}).get('fit') or {}).get('b_ns')
        bmove = {('%d' % s): (None if not (b100 and (by.get('%d' % s, {}).get('fit') or {}).get('b_ns')) else 100 * (by['%d' % s]['fit']['b_ns'] / b100 - 1)) for s in (50, 75, 150)}
        sc[bench] = {'gain_pct': g, 'b_move_pct': bmove}
        if all(v is not None for v in g.values()):
            b50, b75, b150 = ((4, 9), (2, 5), (-10, -5)) if 'fft' in bench else ((3, 7), (1, 4), (-8, -3))
            ok4 = (b50[0] <= g['50_4'] <= b50[1]) and (b75[0] <= g['75_4'] <= b75[1]) and (b150[0] <= g['150_4'] <= b150[1])
            ok16 = all(abs(g['%d_16' % s]) <= 0.7 * abs(g['%d_4' % s]) + 1.0 for s in (50, 75, 150))
            okb = all(v is not None and abs(v) < 10 for v in bmove.values())
            fals = g['50_4'] > 15 or any(v is not None and abs(v) > 25 for v in bmove.values())
            sc[bench]['verdict'] = 'confirmed' if (ok4 and ok16 and okb) else ('FALSIFIED' if fals else 'NOT as predicted')
    # P7: a 0.8-0.9x latency SRAM by linear interpolation between the 75 % and 100 % rows at 4 GHz
    for bench in sc:
        g75 = sc[bench]['gain_pct'].get('75_4')
        sc[bench]['vt_lever_pct_at_4GHz'] = None if g75 is None else {'x0.9': g75 * (10.0 / 25.0), 'x0.8': g75 * (20.0 / 25.0), 'basis': 'linear in latency between the 75 % and 100 % rows'}
    print('\nscorecard (P6):', {b: v.get('verdict', '(incomplete)') for b, v in sc.items()})
    print('P7 (V_t lever, interpolated):', {b: v.get('vt_lever_pct_at_4GHz') for b, v in sc.items()})
    p = os.path.join(_REPO, 'docs', 'evidence', 'comet_cache_latency.json')
    json.dump({'note': __doc__.strip(), 'base': CL, 'benchmarks': out, 'scorecard': sc}, open(p, 'w'), indent=1)
    print('\nwritten:', os.path.relpath(p, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
