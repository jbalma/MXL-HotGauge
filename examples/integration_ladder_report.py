#!/usr/bin/env python
"""§P0.28: the integration ladder -- burial depth x tile pitch on the reference die (100 um grid).

    python examples/integration_ladder_report.py

Reads results/integration/b<burial>/p<pitch>/d<density>/mr_comparison.json plus the 100 um
reference rows (results/x3_u70/ref/array/W*, burial 200 / pitch 500), scores P1-P5 and writes
docs/evidence/integration_ladder.json and a figure for the MXL-006 memo.
"""
import os
import re
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
REF_MM2 = 101.09708


def row_of(f, arm):
    j = json.load(open(f))
    r = [x for x in j['rows'] if x['arm'] == arm]
    return r[0] if r else None


def holds(r):
    return bool(r and not r.get('diverged') and not r.get('unconverged') and
                (r.get('mr_plan_holds_target') or ((r.get('heat_removed_W') or 0) <= 1e-6 and (r.get('peak_C') or 999) <= 92.0)
                 or (r.get('mr_reason') or '').startswith('descent converged on the target; this plan holds')))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'integration_ladder.json'))
    ap.add_argument('--fig-out', default=os.path.join(_REPO, 'docs', 'photonic_cooling', 'MXL-006-PRO', 'Update', 'figures', 'fig_integration_ladder.png'))
    args = ap.parse_args()
    pts = {}
    for f in sorted(glob.glob(os.path.join(_REPO, "results", "integration", "b*", "p*", "d*", "mr_comparison.json"))):
        m = re.search(r'b([0-9]+)/p([0-9]+)/d([0-9.]+)(?:_idle)?/', f)
        b, p, d = int(m.group(1)), int(m.group(2)), float(m.group(3))
        for arm in ('array_on', 'array_idle'):
            r = row_of(f, arm)
            if r:
                pts[(b, p, d, arm)] = r
    # reference rows at burial 200 / pitch 500 on the 100 um grid (x3_u70/ref)
    for f in sorted(glob.glob(os.path.join(_REPO, 'results', 'x3_u70', 'ref', 'array', 'W*', 'mr_comparison.json'))):
        W = float(re.search(r'W([0-9.]+)', f).group(1)); d = round(W / REF_MM2, 2)
        for arm in ('array_on', 'array_idle'):
            r = row_of(f, arm)
            if r and (200, 500, d, arm) not in pts:
                pts[(200, 500, d, arm)] = r
    queued = sorted(set((int(re.search(r'b([0-9]+)', d).group(1)), int(re.search(r'p([0-9]+)', d).group(1)), float(re.search(r'd([0-9.]+)', os.path.basename(d)).group(1)), os.path.basename(d).endswith('_idle'))
                        for d in glob.glob(os.path.join(_REPO, 'results', 'integration', 'b*', 'p*', 'd*'))))
    done = [q for q in queued if os.path.isfile(os.path.join(_REPO, 'results', 'integration', 'b%d' % q[0], 'p%d' % q[1], 'd%.2f%s' % (q[2], '_idle' if q[3] else ''), 'DONE'))]

    def cell(b, p, d):
        r = pts.get((b, p, d, 'array_on'))
        if not r:
            return '--'
        if r.get('diverged'):
            return 'DIV'
        s = '%.1f W' % r['heat_removed_W'] if r.get('heat_removed_W') is not None else '--'
        if not holds(r):
            s += ' (not held, %.0f C)' % (r.get('peak_C') or 0)
        tf = (r.get('tile_flux') or {}).get('max_flux_W_per_mm2')
        if tf:
            s += ' [%.1f W/mm2]' % tf
        return s
    print('%-8s %-6s | ' % ('burial', 'pitch') + ' | '.join('%-30s' % ('%.2f' % d) for d in (1.20, 2.00, 2.40, 2.60, 3.00)))
    for b in (200, 100, 50, 20):
        for p in (500, 200):
            print('%-8d %-6d | ' % (b, p) + ' | '.join('%-30s' % cell(b, p, d) for d in (1.20, 2.00, 2.40, 2.60, 3.00)))
    print('idle at 1.20 by burial:', {b: ('DIV' if (pts.get((b, 500, 1.20, 'array_idle')) or {}).get('diverged') else ('%.1f C' % pts[(b, 500, 1.20, 'array_idle')]['peak_C'] if (b, 500, 1.20, 'array_idle') in pts else '--')) for b in (200, 100, 50, 20)})
    print('%d of %d points done' % (len(done), len(queued)))

    def Q(b, p, d):
        r = pts.get((b, p, d, 'array_on'))
        return r['heat_removed_W'] if r and holds(r) and r.get('heat_removed_W') else None
    sc = {}
    q200, q20 = Q(200, 500, 2.00), Q(20, 500, 2.00)
    if q200 and q20:
        drop = 1 - q20 / q200
        sc['P1_plan_falls_with_burial'] = {'plan_200um_W': q200, 'plan_20um_W': q20, 'drop': drop,
                                          'verdict': 'confirmed' if 0.10 <= drop <= 0.25 else ('FALSIFIED: < 5 %' if drop < 0.05 else 'NOT as predicted')}
    h260 = {b: holds(pts.get((b, 500, 2.60, 'array_on'))) for b in (200, 100, 50, 20) if (b, 500, 2.60, 'array_on') in pts}
    h300 = {b: holds(pts.get((b, 500, 3.00, 'array_on'))) for b in (200, 100, 50, 20) if (b, 500, 3.00, 'array_on') in pts}
    if h260 and h300:
        sc['P2_top_rung'] = {'holds_2.60': h260, 'holds_3.00': h300,
                             'verdict': ('FALSIFIED: 3.00 held' if any(h300.values()) else ('FALSIFIED: 2.60 lost at 20 um' if 20 in h260 and not h260[20] else
                                         ('confirmed' if all(h260.get(b, False) for b in (50, 20) if b in h260) else 'NOT as predicted')))}
    a, b_ = Q(200, 200, 2.00), Q(200, 500, 2.00)
    c, d_ = Q(20, 200, 2.00), Q(20, 500, 2.00)
    if a and b_ and c and d_:
        inert = abs(a / b_ - 1); gain = 1 - c / d_
        sc['P3_pitch'] = {'pitch_ratio_at_200um_burial': a / b_, 'pitch_gain_at_20um_burial': gain,
                          'verdict': ('confirmed' if inert <= 0.02 and 0.10 <= gain <= 0.20 else ('FALSIFIED: < 3 % at 20 um' if gain < 0.03 else 'NOT as predicted'))}
    idle = {b: (pts.get((b, 500, 1.20, 'array_idle')) or {}).get('diverged') for b in (200, 100, 50, 20) if (b, 500, 1.20, 'array_idle') in pts}
    if idle:
        sc['P4_passive_cliff'] = {'idle_diverged_at_1.20': idle, 'verdict': 'confirmed' if all(idle.values()) else 'FALSIFIED: idle holds 1.20 at %s' % [b for b, v in idle.items() if not v]}
    tf = {b: ((pts.get((b, 200, 2.00, 'array_on')) or {}).get('tile_flux') or {}).get('max_flux_W_per_mm2') for b in (200, 100, 50, 20)}
    if tf.get(20):
        sc['P5_tile_flux'] = {'max_tile_flux_at_2.00_pitch200': tf, 'verdict': 'confirmed' if 5 <= tf[20] <= 10 else ('FALSIFIED: > 20' if tf[20] > 20 else 'NOT as predicted')}
    print('\nscorecard:')
    for k, v in sc.items():
        print('  %-28s %s' % (k, v['verdict']))
    out = {'note': __doc__.strip(), 'grid_um': 100, 'points': {'%d/%d/%.2f/%s' % k: {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict)) or kk == 'tile_flux'} for k, v in pts.items()},
           'scorecard': sc, 'complete': len(done) == len(queued) and bool(queued)}
    json.dump(out, open(args.json_out, 'w'), indent=1)
    # figure
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.4))
        cols = {200: '#8a8985', 100: '#2a78d6', 50: '#1baf7a', 20: '#eb6834'}
        for p, ls in ((500, '-'), (200, '--')):
            for b in (200, 100, 50, 20):
                xs, ys = [], []
                for d in (1.20, 2.00, 2.40, 2.60, 3.00):
                    q = Q(b, p, d)
                    if q is not None:
                        xs.append(d); ys.append(q)
                if xs:
                    a1.plot(xs, ys, ls=ls, marker='o', color=cols[b], label='%d µm burial, %d µm pitch' % (b, p))
        a1.set_xlabel('die power density, W/mm²'); a1.set_ylabel('minimum plan that holds 92 °C, W'); a1.set_title('The rescue cost by degree of integration (100 µm grid)'); a1.legend(fontsize=7)
        for p, ls in ((500, '-'), (200, '--')):
            xs, ys = [], []
            for b in (200, 100, 50, 20):
                top = max([d for d in (1.20, 2.00, 2.40, 2.60, 3.00) if holds(pts.get((b, p, d, 'array_on')))] or [0])
                xs.append(b); ys.append(top)
            a2.plot(xs, ys, ls=ls, marker='s', label='%d µm pitch' % p)
        a2.invert_xaxis(); a2.set_xlabel('burial depth, µm (array plane above the transistors)'); a2.set_ylabel('highest rung held, W/mm²'); a2.set_title('The top rung vs integration'); a2.legend(fontsize=8)
        os.makedirs(os.path.dirname(args.fig_out), exist_ok=True)
        fig.savefig(args.fig_out, dpi=160, bbox_inches='tight'); plt.close(fig)
        print('figure:', os.path.relpath(args.fig_out, _REPO))
    except Exception as ex:      # noqa: BLE001
        print('figure skipped:', ex)
    print('written: %s%s' % (os.path.relpath(args.json_out, _REPO), '' if out['complete'] else '   [INCOMPLETE]'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
