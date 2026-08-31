#!/usr/bin/env python
"""Test 6f: the budget cliff, re-measured with leakage feedback in the loop.

    scripts/mr_budget_leakage_sweep.sh <jobid>
    python examples/mr_budget_leakage_saturation.py

Test 6e found efficacy flat to the target block's own power and then a cliff, on LINEAR solves
with no leakage feedback. Feedback should move that, and the two effects it introduces run
opposite:

  * Cooling cuts leakage, so a watt removed takes MORE than a watt out of the die. That raises
    efficacy and should push the cliff later.
  * But leakage is steepest at the hottest block, so the aimed target sheds power faster than its
    neighbours as it cools -- closing the gap to the runner-up from BOTH ends and bringing the
    migration on SOONER.

Which wins is not decidable from the linear result, and it decides whether the sizing rule from
6e (spend up to the runner-up gap, then re-aim) is conservative or optimistic in practice.

`[!]` What this is not
-----------------------
A different configuration from 6e, not a re-run of it: a real McPAT trace on the 8-core 7 nm
stack rather than a synthetic uniform map on the 7-core template, because the feedback loop needs
a per-block power model and the tile-pitch driver has none. So the ABSOLUTE efficacies are not
comparable between the two tests -- only the SHAPE of the curve and where it bends are.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--results', default=os.path.join(_REPO, 'results', 'mr_budget_leak'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'mr_budget_leakage.json'))
    args = ap.parse_args()

    rows = []
    for p in sorted(glob.glob(os.path.join(args.results, 'w*', 'mr_study.json'))):
        d = json.load(open(p))
        for r in d['rows']:
            if r.get('mr') is None or r.get('baseline') is None:
                continue
            acc = r['mr_accounting']
            q = float(acc['heat_removed_W'])
            base_C, mr_C = r['baseline']['T_hot_C'], r['mr']['T_hot_C']
            drop = base_C - mr_C
            rows.append({
                'budget_cap_W': float(os.path.basename(os.path.dirname(p))[1:]),
                'heat_removed_W': q, 'base_peak_C': base_C, 'mr_peak_C': mr_C,
                'peak_drop_K': drop, 'K_per_W_lifted': drop / q if q > 0 else float('nan'),
                'electrical_W': float(acc['electrical_power_W']),
                'recovered_W': float(acc.get('recovered_W', 0.0)),
                'n_blocks_cooled': acc.get('n_blocks_cooled'),
                'base_compute_W': r['baseline'].get('compute_power_W'),
                'mr_compute_W': r['mr'].get('compute_power_W'),
                'converged': r['mr_converged'],
                'power_W': r['power_W']})
    rows.sort(key=lambda r: r['heat_removed_W'])
    if not rows:
        raise SystemExit('no solves under {} -- run scripts/mr_budget_leakage_sweep.sh first'
                         .format(args.results))

    print('leakage feedback ON, coupled solves. Budget binds; target deliberately unreachable.\n')
    print('%8s %10s %10s %10s %11s %11s %11s %6s'
          % ('cap W', 'lifted W', 'peak C', 'drop K', 'K/W lifted', 'compute W', 'leak saved',
             'conv'))
    for r in rows:
        leak = ((r['base_compute_W'] - r['mr_compute_W'])
                if r['base_compute_W'] and r['mr_compute_W'] else float('nan'))
        r['leakage_saved_W'] = leak
        r['effective_W_out_per_W_lifted'] = ((r['heat_removed_W'] + leak) / r['heat_removed_W']
                                             if r['heat_removed_W'] > 0 else float('nan'))
        print('%8.1f %10.3f %10.3f %11.3f %11.3f %11.2f %11.2f %6s'
              % (r['budget_cap_W'], r['heat_removed_W'], r['mr_peak_C'], r['peak_drop_K'],
                 r['K_per_W_lifted'], r['mr_compute_W'] or float('nan'), leak,
                 'y' if r['converged'] else 'n'))

    print('\n%10s %14s %16s' % ('lifted W', 'marginal K/W', 'vs first rung'))
    ref = rows[0]['K_per_W_lifted']
    for i, r in enumerate(rows):
        if i == 0:
            r['marginal_K_per_W'] = r['peak_drop_K'] / r['heat_removed_W']
        else:
            dq = r['heat_removed_W'] - rows[i - 1]['heat_removed_W']
            r['marginal_K_per_W'] = ((r['peak_drop_K'] - rows[i - 1]['peak_drop_K']) / dq
                                     if dq > 1e-9 else float('nan'))
        r['fade_vs_first'] = ref / r['K_per_W_lifted'] if r['K_per_W_lifted'] > 0 else None
        print('%10.3f %14.3f %15.2fx' % (r['heat_removed_W'], r['marginal_K_per_W'],
                                         r['fade_vs_first'] or float('nan')))

    half = 0.5 * ref
    knee = next((r['heat_removed_W'] for r in rows[1:] if r['marginal_K_per_W'] < half), None)
    print('\nknee (marginal below half the first rung): %s'
          % ('%.2f W lifted' % knee if knee else 'not reached in the swept range'))

    out = {'note': __doc__.strip(),
           'compare_with': 'docs/evidence/mr_budget_saturation.json (linear, no feedback)',
           'driver': 'scripts/mr_budget_leakage_sweep.sh + examples/mr_clipping_study.py',
           'rows': rows, 'knee_heat_removed_W': knee,
           'first_rung_K_per_W': ref}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
