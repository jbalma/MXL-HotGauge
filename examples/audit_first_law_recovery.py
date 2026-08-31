#!/usr/bin/env python
"""Audit: which recorded results actually carry the first-law recovery term, and how badly.

    python examples/audit_first_law_recovery.py

The 30 August loop-model reconciliation found that ``MRParams.breakeven_ratio`` omits the Carnot
factor on the anti-Stokes term, making it the ``phi -> 1`` limit. Every ``mr_accounting`` figure
recorded before that date carries it. This file sizes the exposure rather than assuming it: a
first pass flagged files by the mere PRESENCE of the ``p_mr_net_W`` key, which overstated the
problem -- two of the flagged files record it as identically zero, meaning the MR arm was inactive
and nothing needs re-running there.

The signature that matters is a NEGATIVE ``p_mr_net_W``. That is the ledger reporting the loop as
net-generating -- recovering more electrical power than it draws -- which the second law forbids at
any finite chip temperature for the shipped efficiencies. A positive value is merely optimistic;
a negative one is the bug in its pure form.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')


def _walk(obj, hits):
    if isinstance(obj, dict):
        v = obj.get('p_mr_net_W')
        if isinstance(v, (int, float)) and abs(v) > 1e-9:
            hits.append(float(v))
        for x in obj.values():
            _walk(x, hits)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, hits)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--evidence', default=_EV)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'first_law_recovery_audit.json'))
    args = ap.parse_args()

    rows = []
    for f in sorted(glob.glob(os.path.join(args.evidence, '*.json'))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if 'p_mr_net_W' not in json.dumps(d):
            continue
        hits = []
        _walk(d, hits)
        neg = [h for h in hits if h < 0]
        rows.append({'file': os.path.basename(f), 'n_nonzero': len(hits),
                     'n_negative': len(neg),
                     'min': min(hits) if hits else None, 'max': max(hits) if hits else None,
                     'affected': bool(hits),
                     'reports_net_generation': bool(neg)})

    print('%-42s %9s %9s %s' % ('evidence file', 'nonzero', 'negative', 'range'))
    for r in rows:
        print('%-42s %9d %9d %s'
              % (r['file'], r['n_nonzero'], r['n_negative'],
                 ('%.3f .. %.3f' % (r['min'], r['max'])) if r['affected']
                 else 'all zero -- NOT affected'))

    affected = [r for r in rows if r['affected']]
    generating = [r for r in rows if r['reports_net_generation']]
    clean = [r for r in rows if not r['affected']]
    print('\n%d files mention the key; %d actually carry a recovery term; %d report NET GENERATION.'
          % (len(rows), len(affected), len(generating)))

    out = {
        'note': __doc__.strip(),
        'rows': rows,
        'n_files_mentioning_key': len(rows),
        'n_files_affected': len(affected),
        'n_files_reporting_net_generation': len(generating),
        'files_not_affected': [r['file'] for r in clean],
        'files_reporting_net_generation': [r['file'] for r in generating],
        'PRESENCE_OF_THE_KEY_IS_NOT_EXPOSURE': (
            'A first pass flagged files by the presence of p_mr_net_W and reported a larger '
            'exposure than exists. {} of the {} files that mention the key record it as '
            'identically zero -- the MR arm was inactive, so there is no recovery term to correct '
            'and nothing to re-run. Sizing the exposure needs the values, not the schema.'
            .format(len(clean), len(rows))),
        'NEGATIVE_IS_THE_BUG_IN_PURE_FORM': (
            'A negative p_mr_net_W is the ledger reporting the loop as net-generating: recovering '
            'more electrical power than it draws. The second law forbids that at any finite chip '
            'temperature for the shipped efficiencies (loop gain 0.821 at 350 K, 0.958 at 1000 K). '
            'Files with negative entries should be re-run first; files with positive entries are '
            'optimistic but not self-contradictory.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
