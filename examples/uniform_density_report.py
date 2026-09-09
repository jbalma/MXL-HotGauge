#!/usr/bin/env python
"""Merge the concentration-ladder points and write docs/evidence/uniform_density_probe.json.

    python examples/uniform_density_report.py

The ladder runs one point per slurm worker (``scripts/uniform_density_ladder.sh``), so each
point writes its own ``probe.json``. This collects them, finds each arm's cliff, and states the
verdict the experiment was built to produce -- see ``examples/uniform_density_probe.py`` for what
the two arms are and why the comparison is clean.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')


def cliff(rows, arm):
    held = sorted(r['density'] for r in rows if r['arm'] == arm and not r['diverged'])
    failed = sorted(r['density'] for r in rows if r['arm'] == arm and r['diverged'])
    return {'highest_holding': held[-1] if held else None,
            'lowest_failing': failed[0] if failed else None,
            'n_held': len(held), 'n_failed': len(failed)}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'uniform_density'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'uniform_density_probe.json'))
    args = ap.parse_args()

    rows, meta = [], {}
    for f in sorted(glob.glob(os.path.join(args.base, '*', 'd*', 'probe.json'))):
        j = json.load(open(f))
        rows.extend(j['rows'])
        # 'leakage_curve' matters as much as 'rbb_policy' does: a simulated-curve ladder and a
        # pipeline-curve ladder produce structurally identical output, so without this stamp the
        # two reports are indistinguishable and can be mistaken for each other. Absent in files
        # written before P0.13, which is itself the right signal -- those are pipeline runs.
        meta = meta or {k: j[k] for k in ('floorplan', 'die_mm2', 'n_blocks', 'cores', 'cooling',
                                          'spreading', 'leak_fraction', 'leakage_model',
                                          'leakage_curve', 'leakage_T_ref_K',
                                          'rbb_policy', 'real_map_concentration')
                        if k in j}
    if not rows:
        print('no points under {}'.format(args.base))
        return 1
    rows.sort(key=lambda r: (r['arm'], r['density']))

    c = {a: cliff(rows, a) for a in ('shaped', 'uniform')}
    sh, un = c['shaped'], c['uniform']

    # The verdict, stated from the numbers rather than asserted.
    if sh['lowest_failing'] is None or un['lowest_failing'] is None:
        verdict = ('INCONCLUSIVE -- one arm never failed inside the ladder. Extend the range '
                   'before reading anything into it.')
    elif abs(sh['lowest_failing'] - un['lowest_failing']) < 1e-9:
        verdict = (
            'THE CEILING IS NOT CONCENTRATION. Both arms lose their steady state at the same '
            'density ({:.2f} W/mm^2) even though one has Gini 0 and peak == mean and the other '
            'has a peak {:.0f}x its mean. A flat die fails where a shaped die fails, so the gate '
            'is the package and the leakage model -- physics, not an accounting artefact. That '
            'closes a question asked five times and confounded five ways, and it means the '
            'density ceiling can be quoted.'
            .format(sh['lowest_failing'],
                    (meta.get('real_map_concentration') or {}).get('peak_over_mean', float('nan'))))
    elif un['lowest_failing'] > sh['lowest_failing']:
        verdict = (
            'THE CEILING HAS TWO TERMS, AND CONCENTRATION IS ONE OF THEM. On the same watts, the '
            'same die and the same package, the flat map holds to {} W/mm^2 and first fails at '
            '{:.2f}, while the real map first fails at {:.2f} -- a factor of {:.2f} between them. '
            '`[!]` But the flat die has a finite ceiling too, and that is the other half of the '
            'answer: with Gini 0 and peak == mean there is no hot block to blame, so the flat '
            'arm\'s own cliff is the DIE-AVERAGE limit of this package and this leakage model. '
            'Read it as: physics sets a floor near {:.2f} W/mm^2, and the floorplan\'s '
            'concentration costs the difference down to {:.2f}. Neither term is an accounting '
            'artefact, which is what five eliminated hypotheses have been pointing at.'
            .format('%.2f' % un['highest_holding'] if un['highest_holding'] else 'nothing tested',
                    un['lowest_failing'], sh['lowest_failing'],
                    un['lowest_failing'] / sh['lowest_failing'],
                    un['lowest_failing'], sh['lowest_failing']))
    else:
        verdict = (
            '`[!]` THE FLAT DIE IS WORSE, which no hypothesis predicted: uniform fails at {:.2f} '
            'W/mm^2 where the shaped map holds to {:.2f}. Spreading a fixed total power OUT '
            'raised the temperature, so the die is not limited by its hottest block but by bulk '
            'heat removal, and concentration was helping -- the hot block sits next to cold '
            'silicon that sinks it. Worth confirming before it is quoted.'
            .format(un['lowest_failing'], sh['highest_holding']))

    out = dict(meta)
    out.update({
        'note': __doc__.strip(),
        'command': 'scripts/uniform_density_ladder.sh | scripts/campaign_inner.sh',
        'n_points': len(rows), 'cliff_by_arm': c, 'rows': rows, 'VERDICT': verdict,
        'THE_CONTROL': (
            'Both arms carry the SAME total power on the SAME die with the SAME package and the '
            'same leakage rule; only the spatial distribution differs, and the uniform arm is '
            'asserted at run time to have Gini 0 and peak == mean. Any difference in where the '
            'steady state is lost is concentration and nothing else.'),
        'WHY_THIS_AND_NOT_A_THIRD_BLOCK': (
            'core_other and RBB have each been removed once, and the ceiling did not move either '
            'time -- remove one and the other runs away. A ceiling that survives the removal of '
            'whichever block is hottest is not a property of that block, so the next test had to '
            'be about the map rather than about a block.'),
    })
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)

    print('%-9s %8s %9s %8s %9s  %s' % ('arm', 'density', 'verdict', 'peak_C', 'pk/mean',
                                        'hottest block'))
    print('-' * 66)
    for r in rows:
        print('%-9s %8.2f %9s %8s %9.2f  %s' % (
            r['arm'], r['density'], 'DIVERGED' if r['diverged'] else 'holds',
            '--' if r['peak_C'] is None else '%.2f' % r['peak_C'],
            r['peak_over_mean'], r['hottest_block'] or '-'))
    print('\ncliffs: %s' % json.dumps(c))
    print('\n%s\n' % verdict)
    print('written: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
