#!/usr/bin/env python
"""Correct every recovery-affected row in ``FINDINGS.json`` by algebra -- no re-solves.

    python examples/findings_recovery_correction.py

Why no re-solve is needed
-------------------------
``recovery_at_junction`` is **pure post-hoc accounting**: ``microrefrigeration.py`` re-runs
``mr_accounting`` on the finished plan and touches neither the solve nor the plan. And the ledger
is ``net = gross * (1 - ratio)`` with ``ratio`` a function of the MR params and ``T_h`` alone, so a
recorded row can be corrected from its own numbers:

    net_new = net_old * (1 - ratio_new) / (1 - ratio_old)

with ``ratio_new = params.breakeven_ratio_at(peak_C + 273.15)`` -- the second-law form, in which
the anti-Stokes term is weighted by the Carnot factor ``phi = 1 - T0/T_h`` of the heat actually
being lifted. ``ratio_old`` is the first-law ``MRParams.breakeven_ratio``, the ``phi -> 1`` limit.

`[+]` **``gross`` cancels, and so does spot dilution.** That is what makes this exact rather than
approximate. ``gross = heat_billed / cop`` and ``heat_billed = heat_removed * dilution``, and none
of ``gross``, ``cop`` or ``dilution`` appears in the ratio above. It matters in practice: row
``overnight3[26]`` (``p4_spot_s100_dilute``) has ``net/q = -0.6210`` against ``-0.1185`` for every
other row, which looks like a different efficiency preset and is really a **5.24x spot-dilution
overhead** -- 100 um spots on the ``dilute`` policy, billing the laser for the whole pixel. Trying
to identify a preset from ``net/q`` would have mis-assigned that row; the ratio form never asks.

What it corrects
----------------
``FINDINGS.json`` carries **36 negative ``p_mr_net_W`` entries** -- a net-generating cooler, the
first-law bug in pure form (a loop that returns more power than it draws). See
``docs/evidence/first_law_recovery_audit.json`` for the sized exposure.

Verified against ``overnight3[11]``: the implied ``ratio_old`` recovers ``MRParams.breakeven_ratio``
to four significant figures, and the row's **-0.596 W becomes +3.35 W** -- the sign flip the audit
predicted.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.microrefrigeration import MRParams


def negative_net_rows(obj, path=''):
    """Every ``mr_accounting``-shaped dict under ``obj`` with a negative ``p_mr_net_W``."""
    if isinstance(obj, dict):
        v = obj.get('p_mr_net_W')
        if isinstance(v, (int, float)) and v < 0:
            return [(path, obj)]
        out = []
        for k, sub in obj.items():
            out += negative_net_rows(sub, '{}/{}'.format(path, k))
        return out
    if isinstance(obj, list):
        out = []
        for i, sub in enumerate(obj):
            out += negative_net_rows(sub, '{}[{}]'.format(path, i))
        return out
    return []


def correct_row(row, params, T0_K=295.0):
    """``net_new`` for one recorded row, plus the terms it was derived from.

    Returns ``None`` when the row carries no ``peak_C``: without the junction temperature there
    is no ``T_h`` and therefore no second-law ratio. An uncorrectable row is reported as such,
    never guessed.
    """
    peak_C = row.get('peak_C')
    if peak_C is None:
        return None
    T_h = float(peak_C) + 273.15
    ratio_old = params.breakeven_ratio
    ratio_new = params.breakeven_ratio_at(T_h, T0_K)
    net_old = float(row['p_mr_net_W'])
    net_new = net_old * (1.0 - ratio_new) / (1.0 - ratio_old)
    return {
        'peak_C': float(peak_C), 'T_h_K': T_h, 'phi': 1.0 - T0_K / T_h,
        'heat_removed_W': row.get('heat_removed_W'),
        'ratio_first_law': ratio_old, 'ratio_second_law': ratio_new,
        'p_mr_net_W_recorded': net_old, 'p_mr_net_W_corrected': net_new,
        'sign_flipped': net_new > 0,
        'correction_factor': (1.0 - ratio_new) / (1.0 - ratio_old),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--findings', default=os.path.join(_EV, 'FINDINGS.json'))
    ap.add_argument('--T0-K', type=float, default=295.0)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'findings_recovery_correction.json'))
    args = ap.parse_args()

    findings = json.load(open(args.findings))
    rows = negative_net_rows(findings)
    # The recorded rows were computed at the shipped default preset, eta_asf = 0.32, which is
    # still the default -- so an un-flagged MRParams re-prices them correctly. `[!]` If that
    # default ever moves, pin it here explicitly: the correction re-prices a RECORDED row and must
    # use the preset that row was priced with, not whatever the default happens to be.
    params = MRParams(313.15)

    print('MRParams default: cop %.4f, first-law breakeven ratio %.5f'
          % (params.cop, params.breakeven_ratio))
    print('%d negative p_mr_net_W entries in %s\n' % (len(rows), os.path.basename(args.findings)))

    out, uncorrectable = [], []
    print('%-34s %8s %8s %9s %10s %10s' % ('row', 'peak C', 'phi', 'ratio_2nd', 'net old W', 'net new W'))
    for path, row in rows:
        c = correct_row(row, params, args.T0_K)
        if c is None:
            uncorrectable.append(path)
            continue
        c['path'] = path
        out.append(c)
        print('%-34s %8.2f %8.4f %9.4f %10.4f %10.4f'
              % (path[:34], c['peak_C'], c['phi'], c['ratio_second_law'],
                 c['p_mr_net_W_recorded'], c['p_mr_net_W_corrected']))

    flipped = [c for c in out if c['sign_flipped']]
    print('\n%d of %d rows corrected; %d flip sign (net-generating -> net-consuming)'
          % (len(out), len(rows), len(flipped)))
    if uncorrectable:
        print('%d rows carry no peak_C and are NOT corrected: %s'
              % (len(uncorrectable), ', '.join(uncorrectable)))
    print('recorded total %.3f W -> corrected total %.3f W'
          % (sum(c['p_mr_net_W_recorded'] for c in out),
             sum(c['p_mr_net_W_corrected'] for c in out)))

    doc = {
        'note': __doc__,
        'T0_K': args.T0_K,
        'params_note': 'shipped default preset, eta_asf 0.32 -- what the recorded rows were priced with',
        'params': {'cop': params.cop, 'breakeven_ratio_first_law': params.breakeven_ratio,
                   'eta_asf': params.eta_asf, 'laser_wallplug': params.laser_wallplug,
                   'lpc_efficiency': params.lpc_efficiency,
                   'collection_efficiency': params.collection_efficiency},
        'n_negative_rows': len(rows),
        'n_corrected': len(out),
        'n_sign_flipped': len(flipped),
        'uncorrectable_paths': uncorrectable,
        'total_recorded_W': sum(c['p_mr_net_W_recorded'] for c in out),
        'total_corrected_W': sum(c['p_mr_net_W_corrected'] for c in out),
        'rows': out,
    }
    with open(args.json_out, 'w') as f:
        json.dump(doc, f, indent=1)
    print('\nwritten: %s' % args.json_out)


if __name__ == '__main__':
    main()
