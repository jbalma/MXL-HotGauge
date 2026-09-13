#!/usr/bin/env python
"""§P0.29 part 3: the rescue ladder under the per-block (``power``) envelope shape beside the
recorded seed-shape ladder -- cost, share s, peak, tile flux per rung, and the top rung each
shape reaches. Writes docs/evidence/rescue_ladder_power.json.

    python examples/rescue_ladder_shape_report.py
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')


def rows(base):
    out = {}
    for f in sorted(glob.glob(os.path.join(base, 'd*', 'mr_comparison.json'))):
        j = json.load(open(f))
        r = [x for x in j['rows'] if x['arm'] == 'array_on']
        if not r:
            continue
        r = r[0]
        d = float(j['density'])
        held = bool(not r.get('diverged') and not r.get('unconverged') and r.get('mr_plan_holds_target'))
        out[d] = {'density': d, 'held': held, 'diverged': bool(r.get('diverged')), 'unconverged': bool(r.get('unconverged')),
                  'plan_W': r.get('heat_removed_W'), 'p_chip_W': r.get('p_chip_W'), 'p_injected_W': r.get('p_injected_W'),
                  's': (r['heat_removed_W'] / r['p_chip_W']) if r.get('heat_removed_W') and r.get('p_chip_W') else None,
                  'net_W': r.get('p_mr_net_W'), 'peak_C': r.get('peak_C'), 'peak_block': r.get('peak_block'),
                  'tiles_capped': (r.get('extractor') or {}).get('n_tiles_capped'),
                  'max_tile_flux_W_per_mm2': (r.get('tile_flux') or {}).get('max_flux_W_per_mm2'),
                  'reason': (r.get('mr_reason') or '')[:90], 'envelope_shape': j.get('mr_envelope_shape') or 'seed',
                  'source': os.path.relpath(os.path.dirname(f), _REPO)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'rescue_ladder_power.json'))
    args = ap.parse_args()
    seed = rows(os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00'))
    power = rows(os.path.join(_REPO, 'results', 'array_coverage_armD_power'))
    print('%5s | %-30s | %-30s | %s' % ('rung', 'seed shape', 'per-block shape', 'change'))
    comp = []
    for d in sorted(set(seed) | set(power)):
        a, b = seed.get(d), power.get(d)
        f = lambda r: '--' if not r else ('no steady state' if r['diverged'] else '%.1f W, s=%.2f, %.1f C%s' % (r['plan_W'] or 0, r['s'] or 0, r['peak_C'] or 0, '' if r['held'] else ' NOT HELD'))
        ch = ('%+.0f %%' % (100 * (b['plan_W'] / a['plan_W'] - 1))) if (a and b and a.get('plan_W') and b.get('plan_W') and a['held'] and b['held']) else ''
        print('%5.2f | %-30s | %-30s | %s' % (d, f(a), f(b), ch))
        comp.append({'density': d, 'seed': a, 'power': b, 'plan_change': (b['plan_W'] / a['plan_W'] - 1) if (a and b and a.get('plan_W') and b.get('plan_W')) else None})
    top = lambda R: max([d for d, r in R.items() if r['held']] or [0])
    out = {'note': __doc__.strip(), 'rungs': comp, 'top_rung_seed': top(seed), 'top_rung_power': top(power),
           'lowest_failing_seed': min([d for d, r in seed.items() if r['diverged']] or [None]) if any(r['diverged'] for r in seed.values()) else None,
           'lowest_failing_power': min([d for d, r in power.items() if r['diverged'] or not r['held']] or [None]) if any((r['diverged'] or not r['held']) for r in power.values()) else None,
           'complete': True}
    print('top rung held: seed %.2f, per-block %.2f; lowest failing per-block: %s' % (out['top_rung_seed'], out['top_rung_power'], out['lowest_failing_power']))
    json.dump(out, open(args.json_out, 'w'), indent=1)
    print('written:', os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
