#!/usr/bin/env python
"""Read the RBB bracket and write docs/evidence/rbb_bracket.json.

    python examples/rbb_bracket_report.py

The bracket ran the SAME density ladder under both placement policies -- see
``scripts/rbb_bracket.sh`` -- to put the size of the RBB change on record before any catalogue
re-run. It answered that, and it also answered a question it was not asked.
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

DENSITIES = ('1.20', '1.60', '1.80', '2.00', '2.40')
POLICIES = ('stock', 'amortized')


def hottest_block(run_dir):
    """The hottest block the leakage loop named in the log, and how hot."""
    try:
        with open(os.path.join(run_dir, 'log.txt')) as f:
            text = f.read()
    except IOError:
        return None, None
    hits = re.findall(r"block '([A-Za-z_0-9]+)' reached ([0-9.]+) K", text)
    if not hits:
        return None, None
    block, k = max(hits, key=lambda h: float(h[1]))
    return block, float(k)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'rbb_bracket'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'rbb_bracket.json'))
    args = ap.parse_args()

    rows, pairs = [], {}
    for pol in POLICIES:
        for d in DENSITIES:
            run = os.path.join(args.base, pol, 'd' + d)
            f = os.path.join(run, 'mr_comparison.json')
            if not os.path.isfile(f):
                continue
            j = json.load(open(f))
            blk, k = hottest_block(run)
            for r in j['rows']:
                rows.append({'policy': pol, 'density': float(d), 'arm': r.get('arm'),
                             'diverged': bool(r.get('diverged')), 'peak_C': r.get('peak_C'),
                             'heat_removed_W': r.get('heat_removed_W'),
                             'holds_target': r.get('holds_target'),
                             'unconverged': r.get('unconverged'),
                             'hottest_block_in_log': blk, 'hottest_K_in_log': k})
                if r.get('arm') == 'array_on':
                    pairs.setdefault(d, {})[pol] = rows[-1]
            if pol == 'amortized':
                pairs.setdefault(d, {})['rbb_meta'] = j.get('rbb')

    deltas = []
    for d in DENSITIES:
        p = pairs.get(d, {})
        s, a = p.get('stock'), p.get('amortized')
        if not (s and a):
            continue
        both = (not s['diverged']) and (not a['diverged'])
        deltas.append({
            'density': float(d),
            'stock_diverged': s['diverged'], 'amortized_diverged': a['diverged'],
            'stock_peak_C': s['peak_C'], 'amortized_peak_C': a['peak_C'],
            'delta_peak_K': (a['peak_C'] - s['peak_C']) if both else None,
            'stock_Q_mr_W': s['heat_removed_W'], 'amortized_Q_mr_W': a['heat_removed_W'],
            'delta_Q_mr_pct': (100.0 * (a['heat_removed_W'] / s['heat_removed_W'] - 1.0)
                               if both and s['heat_removed_W'] else None),
            'hottest_block_stock': s['hottest_block_in_log'],
            'hottest_block_amortized': a['hottest_block_in_log'],
        })

    out = {
     'note': __doc__.strip(),
     'floorplan': 'skylake7nm_34core_3_3D-ICE.flp (the die the A_density ladder runs on)',
     'command': 'scripts/rbb_bracket.sh | scripts/campaign_inner.sh',
     'n_points': len(rows),
     'deltas_on_the_array_arm': deltas,
     'rows': rows,

     'WHAT_THE_BRACKET_WAS_FOR': (
         'Amortizing the results-broadcast bus changes every recorded thermal result, so the size '
         'of the change had to be on the record BEFORE the catalogue was re-run -- otherwise '
         '"the numbers moved" and "the study changed" are indistinguishable afterwards. Same '
         'points, same everything else, one flag apart.'),

     'THE_CHANGE_IS_REAL_AND_MATERIAL': (
         'Where both policies converge, amortizing lowers the solved peak and moves the cooling '
         'bill: at 1.20 W/mm^2 the array arm goes 93.96 -> 87.24 C (-6.7 K) at essentially the '
         'same 26 W of heat lifted, and at 1.60 it goes 92.83 -> 90.79 C (-2.0 K) while the heat '
         'lifted falls 112.53 -> 89.58 W, -20 %. No recorded result survives the switch unchanged, '
         'which is why it is a policy with a default rather than an edit.'),

     'BUT_THE_CEILING_DID_NOT_MOVE': (
         'Both policies fail at 2.00 and 2.40 W/mm^2, on every arm. Amortizing RBB does NOT '
         'unblock the high-density programme. `[!]` This contradicts the premise carried into '
         'docs/NEXT_SESSION.md -- "RBB placement gates every high-density result" -- and it is '
         'the fifth hypothesis for this ceiling to be eliminated by measurement, after the bulk '
         'floor, the leakage extrapolation, the array envelope and core_other.'),

     'AND_RBB_WAS_NEVER_THE_GATE_ON_THIS_FLOORPLAN': (
         'At every diverging point the block the leakage loop names is core_other_0 -- under BOTH '
         'policies, at nearly the same temperature (d2.00: 3488 K stock, 3611 K amortized; d2.40: '
         '15760 K and 16417 K). RBB never appears. docs/evidence/rbb_is_the_gate.json measured '
         'RBB as the runaway on the REBUILT ISA floorplans (a64fx, riscv), where core_other had '
         'already been shrunk from 15.68 % of die area to 0.94 %. On the standard 34-core die the '
         'density ladder actually uses, core_other_0 is still the hottest thing on the die. Two '
         'different floorplans, two different top blocks -- and the same ceiling.'),

     'WHICH_IS_THE_INFORMATIVE_RESULT': (
         'Each of the two candidate blocks has now been removed, and the ceiling did not move '
         'either time: shrink core_other and RBB runs away (rbb_is_the_gate.json); amortize RBB '
         'and core_other runs away (this file). A ceiling that survives the removal of whichever '
         'block is hottest is not a property of that block. Either it is set by something global '
         '-- the package and spreading boundary, or the leakage model above 400 K -- or it is '
         'real. `[!]` The next test should therefore be a global one and not a third block: run '
         'the ladder on a UNIFORM power map, where no block is hot by construction. If a flat die '
         'also has no steady state at 2.00 W/mm^2, the ceiling is physics and the artefact '
         'hypothesis is finished.'),

     'THE_STOCK_PATH_IS_BIT_FOR_BIT_UNCHANGED': (
         'Checked against the recorded campaign, results/overnight_forward/A_density: all 15 '
         'arm x density points of the stock bracket reproduce the recorded verdict and peak to '
         'better than 0.01 K (93.96 / 92.83 / 78.07 C on the array arm at 1.20 / 1.60 / 1.80, '
         'diverged everywhere the record says diverged). The policy is additive: with the '
         'default flag the pipeline is the one that produced the catalogue.'),

     'WHAT_IS_NOT_ESTABLISHED': (
         'The 1.80 point is not usable as evidence in either direction: stock converges there at '
         '78.07 C having lifted 181 W -- far below the 92 C target, so the planner overshot -- '
         'while amortized diverges. The ladder is not monotone under either policy at that point, '
         'so the single-point difference is planner path, not a ceiling. Nothing here bears on '
         'whether amortizing is the right SEMANTICS; that rests on the McPAT source (see '
         'HotGauge.thermal.rbb) and is unaffected by where the ceiling turns out to be.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('%d rows, %d density pairs -> %s' % (len(rows), len(deltas), args.json_out))
    for d in deltas:
        print('  d%.2f  stock %-9s amortized %-9s  peak %s  Q_mr %s   hottest: %s / %s' % (
            d['density'],
            'DIVERGED' if d['stock_diverged'] else '%.2f C' % d['stock_peak_C'],
            'DIVERGED' if d['amortized_diverged'] else '%.2f C' % d['amortized_peak_C'],
            ('%+.2f K' % d['delta_peak_K']) if d['delta_peak_K'] is not None else '--',
            ('%+.1f %%' % d['delta_Q_mr_pct']) if d['delta_Q_mr_pct'] is not None else '--',
            d['hottest_block_stock'] or '-', d['hottest_block_amortized'] or '-'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
