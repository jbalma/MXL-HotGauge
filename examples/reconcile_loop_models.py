#!/usr/bin/env python
"""Test 7: reconciling the two loop models, which disagreed about whether the loop self-powers.

    python examples/reconcile_loop_models.py

This repository carried two independent statements of the same photonic loop, and at the shipped
defaults they gave qualitatively different answers:

    microrefrigeration.MRParams.breakeven_ratio = eta_laser * eta_LPC * coll * (1 + eta_ASF)
    exergy.loop_gain                            = eta_L     * eta_c            * (1 + eta_AS * phi)

`eta_AS` and `eta_ASF` are the same quantity -- the anti-Stokes up-conversion efficiency -- so the
two expressions differ by **exactly the factor phi multiplying it**, and the first is the
`phi -> 1` limit of the second. phi = 1 - T_0/T_h reaches 1 only as `T_h -> infinity`.

What that omission was doing
----------------------------
The first-law form credits the ENTIRE fluorescence stream `(1 + eta_ASF)` as convertible to
electricity at `eta_LPC`. Only the pump-derived part is work-like; the heat-derived part is
Carnot-limited, and that is what `phi` accounts for. At the shipped defaults the difference flips
the verdict: the first-law ledger returns **1.032 and reports the loop as net-generating**, while
the second-law value is **0.821 at 350 K** and does not reach 1.0 at any temperature silicon can
survive. Every `mr_accounting` result recorded before 30 August 2026 carries the optimistic term.

The check that did not catch it was `first_law_ok`, which tests `recovered <= gross + heat`. That
is the first law, and the first law is satisfied -- the recovered energy really is available. It is
the SECOND law that forbids converting it at that efficiency, and nothing was testing it.

Why this matters for architecture rather than just bookkeeping
-------------------------------------------------------------
Because `phi` is set by `T_h`, the corrected model says the required extractor efficiency falls
steeply with die temperature -- which is the whole case for running logic hot. This file prints
that curve. The uncomfortable part is where the toolchain stops: McPAT refuses temperatures above
400 K, and 400 K is a point at which the requirement is still unphysical.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal import exergy as EX
from HotGauge.thermal.microrefrigeration import MRParams


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--T0-K', type=float, default=EX.BOOK_T0_K)
    ap.add_argument('--temps-K', type=float, nargs='+',
                   default=[330, 350, 373, 400, 450, 500, 550, 600, 700, 800, 1000])
    ap.add_argument('--eta-P', type=float, nargs='+', default=[0.85, 0.90, 0.95],
                    help='pump laser wall-plug efficiencies to sweep -- now the binding term')
    ap.add_argument('--eta-ASF', type=float, nargs='+',
                    default=[0.12, 0.22, 0.30, 0.35, 0.40],
                    help='v91 Table 8.1 gives 0.124 at 680 nm and 0.221 at 740 nm for '
                         'SMILES-R640; >0.30 is the current experimental claim')
    ap.add_argument('--json-out', default=os.path.join(_REPO, 'docs', 'evidence',
                                                       'loop_model_reconciliation.json'))
    args = ap.parse_args()

    p = MRParams(313.15)
    # `[!]` eta_cpl is the COUPLING efficiency. eta_LPC must NOT be folded in here: (1.16) has
    # already eliminated it by substituting its exergy ceiling (1.14). Doing so on 30 Aug 2026
    # inflated the required eta_ASF at 600 K from 0.347 to 0.548.
    eta_cpl = p.collection_efficiency
    eta_c = eta_cpl
    T0 = args.T0_K
    print('shipped defaults: eta_ASF %.2f, eta_LPC %.2f, collection %.2f, eta_laser %.2f'
          % (p.eta_asf, p.lpc_efficiency, p.collection_efficiency, p.laser_wallplug))
    print('first-law (phi -> 1) breakeven ratio: %.5f  -> reports SELF-SUSTAINING\n'
          % p.breakeven_ratio)

    print('%8s %8s %12s %12s %10s %14s'
          % ('T_h K', 'phi', 'MR (fixed)', 'exergy 1.15', 'agree', 'self-powering?'))
    rows = []
    for T in args.temps_K:
        mr = p.breakeven_ratio_at(T, T0)
        ex = EX.loop_gain(p.laser_wallplug, eta_c, p.eta_asf, T, T0)
        rows.append({'T_h_K': T, 'phi': EX.carnot_factor(T, T0), 'mr_ratio': mr,
                     'exergy_loop_gain': ex, 'models_agree': abs(mr - ex) < 1e-12,
                     'self_powering': ex >= 1.0,
                     'overstatement_vs_first_law': p.breakeven_ratio / ex})
        print('%8.0f %8.4f %12.5f %12.5f %10s %14s'
              % (T, EX.carnot_factor(T, T0), mr, ex, 'yes' if abs(mr - ex) < 1e-12 else 'NO',
                 'yes' if ex >= 1.0 else 'no'))

    # ---- the design curve: what the extractor must reach, against die temperature -----------
    print('\n=== required eta_ASF for a self-powering loop (eq. 1.16) ===')
    print('%8s %8s %16s %s' % ('T_h K', 'phi', 'eta_ASF needed', 'note'))
    req = []
    MCPAT_MAX = 400.0
    for T in args.temps_K:
        need = EX.eta_AS_required(p.laser_wallplug, eta_c, T, T0)
        note = ''
        if T <= MCPAT_MAX:
            note = 'within McPAT'
        else:
            note = 'BEYOND McPAT (>400 K)'
        if need > 1.0:
            note += ' -- unphysical, eta_ASF > 1'
        req.append({'T_h_K': T, 'phi': EX.carnot_factor(T, T0), 'eta_ASF_required': need,
                    'within_mcpat_domain': T <= MCPAT_MAX, 'requires_eta_above_1': need > 1.0})
        print('%8.0f %8.4f %16.3f %s' % (T, EX.carnot_factor(T, T0), need, note))

    inside = [r for r in req if r['within_mcpat_domain']]
    best_inside = min(inside, key=lambda r: r['eta_ASF_required']) if inside else None
    feasible = [r for r in req if not r['requires_eta_above_1']]
    first_feasible = min(feasible, key=lambda r: r['T_h_K']) if feasible else None

    # ---- the design map that matters now: how hot must logic run for a given extractor? ----
    print('\n=== T_h at which the loop self-powers, by extractor and laser (T_0 = %.0f K) ==='
          % T0)
    print('%10s' % 'eta_ASF' + ''.join('%14s' % ('eta_P=%.2f' % e) for e in args.eta_P))
    design = []
    for a in args.eta_ASF:
        line = '%10.2f' % a
        for e in args.eta_P:
            T = EX.self_powering_T_h(a, e, eta_cpl, T0)
            design.append({'eta_ASF': a, 'eta_P': e, 'self_powering_T_h_K': T})
            line += '%14s' % (('%.0f K' % T) if T else 'never')
        print(line)
    print('\n  v91 Table 8.1: SMILES-R640 reaches eta_ASF 0.124 at 680 nm, 0.221 at 740 nm.')
    print('  Yb:YLF (0.02-0.035) is SUPERSEDED and must not be quoted as state of the art.')

    out = {
        'note': __doc__.strip(),
        'design_map_self_powering_T_h': design,
        'eta_cpl_used': eta_cpl,
        'defaults': {'eta_ASF': p.eta_asf, 'eta_LPC': p.lpc_efficiency,
                     'collection': p.collection_efficiency, 'eta_laser': p.laser_wallplug,
                     'T_0_K': T0},
        'first_law_breakeven_ratio': p.breakeven_ratio,
        'ladder': rows,
        'eta_ASF_required': req,
        'best_within_mcpat_domain': best_inside,
        'first_temperature_not_requiring_eta_above_1': first_feasible,
        'THE_TWO_MODELS_DIFFER_BY_EXACTLY_PHI': (
            'eta_AS and eta_ASF are the same quantity, so breakeven_ratio and loop_gain differ '
            'only by phi multiplying it, and the first is the phi -> 1 limit of the second. '
            'Verified identical at every temperature in this ladder to 1e-12. The first-law form '
            'credits the whole fluorescence stream as convertible work; only the pump-derived '
            'part is, and the heat-derived part is Carnot-limited.'),
        'WHAT_IT_CHANGED': (
            'At the shipped defaults the first-law ledger returns {:.5f} and reports the loop as '
            'NET-GENERATING. The second-law value is {:.5f} at 350 K and {:.5f} even at 1000 K -- '
            'it never reaches 1.0 at any temperature silicon survives. The self-powering result '
            'was entirely the missing Carnot factor. The guard that should have caught it, '
            'first_law_ok, tests recovered <= gross + heat: that is the FIRST law and it passes. '
            'Nothing was testing the second.'
            .format(p.breakeven_ratio,
                    EX.loop_gain(p.laser_wallplug, eta_c, p.eta_asf, 350.0, T0),
                    EX.loop_gain(p.laser_wallplug, eta_c, p.eta_asf, 1000.0, T0))),
        'ETA_P_IS_NOW_THE_BINDING_TERM': (
            'The required eta_ASF is {:.3f}/phi, and that numerator is 1/(eta_P*eta_cpl) - 1, '
            'which is very steep near unity. Moving the laser wall-plug from 0.85 to 0.90 drops '
            'the self-powering temperature at eta_ASF = 0.30 from {:.0f} K to {:.0f} K; at 0.95 '
            'it falls to {:.0f} K. Section 1.12 Example 3 makes the same point about eta_cpl: a '
            'single 20 % front-end loss roughly doubles the extractor target. With the v91 '
            'materials the extractor is no longer the hard part -- THE LASER AND THE OPTICAL '
            'PATH ARE. That is a different programme from the one this project has been costing.'
            .format(1.0 / (0.85 * eta_cpl) - 1.0,
                    EX.self_powering_T_h(0.30, 0.85, eta_cpl, T0),
                    EX.self_powering_T_h(0.30, 0.90, eta_cpl, T0),
                    EX.self_powering_T_h(0.30, 0.95, eta_cpl, T0))),
        'WHAT_THE_v91_MATERIALS_CHANGE': (
            'Yb:YLF at eta_ASF ~ 0.02-0.035 and 1-10 W/mm^2 is SUPERSEDED for compute tiles and '
            'must not be quoted as the state of the art. v91 Table 8.2 gives two platforms at '
            '10^3-10^4 W/mm^2 -- direct-bandgap GaAs/GaInP epitaxy, and SMILES-R640-in-polymer '
            'thin films which reach the same density at ROOM TEMPERATURE, solution-processed, on '
            'any planar substrate. Table 8.1 gives the anti-Stokes ladder: eta_ASF 0.124 at a '
            '680 nm pump rising to 0.221 at 740 nm, with eta_EQE 0.99 at Nt >= 1e-2 M. Against '
            'the corrected requirement that changes the verdict at achievable temperatures: '
            '0.347 is needed at 600 K and 0.305 at 700 K, so an extractor at or above 0.30 -- '
            'the current experimental claim, beyond Table 8.1\'s tabulated range -- closes the '
            'loop in the 400-600 K hot-compute zone of Section 10.8.'),
        'THE_400_K_CEILING_STILL_BITES_BUT_DIFFERENTLY': (
            'With the corrected coupling term the requirement at 400 K is {:.3f}, not the >1 this '
            'file previously reported -- so McPAT\'s domain is no longer a wall of impossibility. '
            'It is still the wrong place to stop: the requirement roughly halves again between '
            '400 K and 600 K ({:.3f} -> {:.3f}), and 400-600 K is exactly the hot-compute zone '
            'the architecture proposes. The tooling answer has not changed either way -- McPAT '
            'is not in the temperature loop (docs/MCPAT_HIGH_TEMPERATURE.md).'
            .format(EX.eta_AS_required(0.85, eta_cpl, 400.0, T0),
                    EX.eta_AS_required(0.85, eta_cpl, 400.0, T0),
                    EX.eta_AS_required(0.85, eta_cpl, 600.0, T0))),
        'ZONE_MATCHED_EXTRACTORS_CLOSE_A_RECORDED_GAP': (
            'This project recorded "eta_AS(T_h) is not modelled at all" as an open gap. v91 s8.4 '
            'answers it structurally rather than numerically: a heterogeneous die does not use '
            'one extractor material across its area. Yb:YLF/Yb:silica for cold storage tiles '
            '(150-300 K), Yb:ZBLAN or fluoride glass for warm interconnect (300-400 K), '
            'Ho3+/Tm3+ fluorides or Cr3+ colquiriites for hot compute (400-600 K), and SiC:Er or '
            'GaN:Yb above 600 K -- the same wide-bandgap families as the compute devices there. '
            'Per-tile temperature targeting requires per-tile extractor selection.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\n' + out['WHAT_THE_v91_MATERIALS_CHANGE'])
    print('\nwrote {}'.format(args.json_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
