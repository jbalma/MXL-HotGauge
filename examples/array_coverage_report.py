#!/usr/bin/env python
"""The array charged its own footprint: read the coverage ladder and state what moved (§P0.18).

    python examples/array_coverage_report.py [--base results/array_coverage_armD]

Reads every ``c<coverage>/d<density>/mr_comparison.json`` the ladder wrote
(``scripts/array_coverage_ladder_armD.sh``), joins the shared control / array_idle rows from the
full-coverage run onto every other coverage, finds each coverage's array-assisted ceiling, and
compares the minimum-plan cost at matched density. Then it checks the three predictions written
in ``docs/PHASE0_CHECKLIST.md`` §P0.18.2 against the numbers, in the numbers' own words.

`[!]` Refuses to write the evidence file while the ladder is incomplete. A partial ladder's
shared points are non-random (whichever finished first), and a file marked ``complete: false``
is still a file someone will lift numbers out of.

`[!]` An ``unconverged`` row is neither a hold nor a failure. Same rule as the density ladder.
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')


def _verdict(r):
    if r is None:
        return 'missing'
    if r.get('diverged'):
        return 'DIVERGED'
    if r.get('unconverged'):
        return 'unconverged'
    if r.get('mr') and not r.get('mr_plan_holds_target'):
        # "nothing above target" is a hold with nothing to do, not a failed plan: the array's
        # passive term alone kept the die under target and the planner removed 0 W.
        tgt = r.get('mr_target_C')
        if (r.get('heat_removed_W') == 0 and tgt is not None and r.get('peak_C') is not None
                and r['peak_C'] <= tgt + 2.0):
            return 'holds'
        return 'holds-but-not-target'
    return 'holds'


def load(base):
    pts = {}
    for f in sorted(glob.glob(os.path.join(base, 'c*', 'd*', 'mr_comparison.json'))):
        c = float(os.path.basename(os.path.dirname(os.path.dirname(f)))[1:])
        d = float(os.path.basename(os.path.dirname(f))[1:])
        j = json.load(open(f))
        pts[(c, d)] = {r['arm']: r for r in j['rows']}
    return pts


def ceiling(rows_by_density):
    """(highest holding, lowest failing) over array_on rows; unconverged counts as neither."""
    held = [d for d, r in rows_by_density.items() if _verdict(r) == 'holds']
    failed = [d for d, r in rows_by_density.items() if _verdict(r) == 'DIVERGED']
    return {'highest_holding': max(held) if held else None,
            'lowest_failing': min(failed) if failed else None,
            'n_held': len(held), 'n_failed': len(failed),
            'n_unconverged': sum(1 for r in rows_by_density.values()
                                 if _verdict(r) == 'unconverged')}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'array_coverage_armD'))
    ap.add_argument('--joblist', default=None,
                    help='the ladder joblist, to measure completeness against (default: '
                         '<base>/joblist.tsv)')
    ap.add_argument('--json-out', default=os.path.join(_EV, 'array_coverage_armD.json'))
    ap.add_argument('--h-max', type=float, default=1000.0)
    ap.add_argument('--dT-dQ', type=float, default=0.3247,
                    help='package K/W at 88 CFM on the 34-core die, for normalising Q to a '
                         'common landing peak (METHODS section 4.3). The descent stops wherever '
                         'it first holds target, so raw Q differs by the peak it landed at.')
    ap.add_argument('--force', action='store_true', help='write the file even if incomplete')
    args = ap.parse_args()

    joblist = args.joblist or os.path.join(args.base, 'joblist.tsv')
    planned = [l.split('\t')[0] for l in open(joblist).read().splitlines() if l.strip()] \
        if os.path.isfile(joblist) else []
    pts = load(args.base)
    done = [p for p in planned if os.path.isfile(os.path.join(p, 'mr_comparison.json'))]
    complete = bool(planned) and len(done) == len(planned)
    print('coverage ladder: {}/{} points on disk{}'.format(
        len(done), len(planned), '' if complete else '  ** INCOMPLETE **'))

    coverages = sorted({c for c, _ in pts})
    densities = sorted({d for _, d in pts})
    full = 1.0
    shared = {d: pts.get((full, d), {}) for d in densities}

    table = []
    for c in coverages:
        for d in densities:
            arms = pts.get((c, d))
            if not arms:
                continue
            on = arms.get('array_on')
            ctrl = shared[d].get('control')
            idle = shared[d].get('array_idle')
            flux = (on or {}).get('tile_flux') or {}
            table.append({
                'coverage': c, 'density': d,
                'coverage_achieved': (on or {}).get('array_coverage_achieved'),
                'reserved_mm2': (on or {}).get('array_reserved_mm2'),
                'n_tiles': (on or {}).get('n_tiles'),
                'n_gap_blocks': (on or {}).get('array_n_gap_blocks'),
                'control': _verdict(ctrl), 'control_peak_C': (ctrl or {}).get('peak_C'),
                'array_idle': _verdict(idle), 'idle_peak_C': (idle or {}).get('peak_C'),
                'array_on': _verdict(on), 'on_peak_C': (on or {}).get('peak_C'),
                'heat_removed_W': (on or {}).get('heat_removed_W'),
                'p_mr_net_W': (on or {}).get('p_mr_net_W'),
                'plan_is_minimum': (on or {}).get('mr_plan_is_minimum'),
                'plan_holds_target': (on or {}).get('mr_plan_holds_target'),
                'n_targets': (on or {}).get('n_targets'),
                'max_tile_flux_W_per_mm2': flux.get('max_flux_W_per_mm2'),
                'tiles_over_h_max': flux.get('n_tiles_over_h_max'),
                'unconverged': bool((on or {}).get('unconverged')),
            })

    ceilings = {}
    for c in coverages:
        ceilings[c] = ceiling({d: pts[(c, d)].get('array_on') for d in densities
                               if (c, d) in pts})
    ctrl_ceiling = ceiling({d: shared[d].get('control') for d in densities if shared[d]})
    idle_ceiling = ceiling({d: shared[d].get('array_idle') for d in densities if shared[d]})

    # Q at matched density against full coverage, only where both hold with a minimum plan.
    dq = []
    ref = {r['density']: r for r in table if r['coverage'] == full}
    for r in table:
        if r['coverage'] == full:
            continue
        b = ref.get(r['density'])
        if (b and r['array_on'] == 'holds' and b['array_on'] == 'holds'
                and r['heat_removed_W'] and b['heat_removed_W']):
            # Normalise both plans to the same landing peak: a plan that landed 1.9 K below
            # target removed 1.9 / (dT/dQ) W more than it needed to. Compared raw, that reads
            # as a coverage effect; it is the descent's stopping point.
            tgt = float((pts[(r['coverage'], r['density'])]['array_on'].get('mr_target_C')
                         or 92.0))
            qn_full = b['heat_removed_W'] - (tgt - b['on_peak_C']) / args.dT_dQ
            qn = r['heat_removed_W'] - (tgt - r['on_peak_C']) / args.dT_dQ
            dq.append({'coverage': r['coverage'], 'density': r['density'],
                       'Q_full_W': b['heat_removed_W'], 'Q_W': r['heat_removed_W'],
                       'dQ_pct': 100.0 * (r['heat_removed_W'] / b['heat_removed_W'] - 1.0),
                       'Q_full_at_target_W': qn_full, 'Q_at_target_W': qn,
                       'dQ_norm_pct': 100.0 * (qn / qn_full - 1.0) if qn_full > 0 else None,
                       'peak_full_C': b['on_peak_C'], 'peak_C': r['on_peak_C']})

    max_flux = max((r['max_tile_flux_W_per_mm2'] or 0.0) for r in table) if table else 0.0

    # --- the predictions, checked from the numbers -----------------------------------------
    checks = {}
    c1 = ceilings.get(full, {})
    hh, lf = c1.get('highest_holding'), c1.get('lowest_failing')
    checks['P1_full_coverage_ceiling'] = {
        'predicted': 'highest holding rung 1.50-1.70, lowest failing <= 2.00',
        'falsifier': 'highest holding <= 1.40',
        'measured': {'highest_holding': hh, 'lowest_failing': lf},
        'verdict': (None if hh is None else
                    'FALSIFIED -- recorded 1.60-1.80 array ceiling withdrawn' if hh <= 1.40 else
                    'CONFIRMED' if 1.50 <= hh <= 1.70 and (lf is None or lf <= 2.00) else
                    'OUTSIDE THE PREDICTED BAND (higher)' if hh > 1.70 else
                    'BAND MISSED (lower, above the falsifier)')}
    for c, band, note in ((0.75, 5.0, 'indistinguishable from 1.00'),
                          (0.50, 20.0, 'sign not predicted'),
                          (0.25, None, 'Q up >= 10 %, may lose one rung')):
        rows = [x for x in dq if x['coverage'] == c]
        worst = max((abs(x['dQ_norm_pct']) for x in rows if x['dQ_norm_pct'] is not None),
                    default=None)
        same_rung = (ceilings.get(c, {}).get('highest_holding') == hh) if c in ceilings else None
        lost = (None if (same_rung is None or hh is None or
                         ceilings[c].get('highest_holding') is None)
                else round(hh - ceilings[c]['highest_holding'], 3))
        checks['P2_coverage_{:.2f}'.format(c)] = {
            'predicted': ('|dQ| < {} %, same rung'.format(band) if band else note),
            'measured': {'max_abs_dQ_norm_pct': worst,
                         'max_abs_dQ_raw_pct': max((abs(x['dQ_pct']) for x in rows), default=None),
                         'rungs_lost': lost,
                         'ceiling': ceilings.get(c)},
            'verdict': (None if worst is None or lost is None else
                        ('CONFIRMED' if (band is not None and worst < band and lost == 0) or
                         (band is None and lost >= 0 and
                          any((x['dQ_norm_pct'] or 0.0) >= 10.0 for x in rows))
                         else 'NOT AS PREDICTED'))}
    c05 = checks['P2_coverage_0.50']['measured']['rungs_lost']
    checks['P2_named_falsifier'] = {
        'statement': 'coverage 0.50 loses a rung against 1.00 -> the burial-depth smearing '
                     'argument is wrong and the area is a first-order thermal term',
        'measured_rungs_lost_at_0.50': c05,
        'verdict': None if c05 is None else ('FALSIFIED' if c05 > 0 else 'survives')}
    checks['P3_tile_flux'] = {
        'predicted': 'max tile flux < 100 W/mm^2 everywhere; falsifier: any tile > 250',
        'measured_max_W_per_mm2': max_flux,
        'verdict': ('CONFIRMED' if max_flux < 100.0 else
                    'FALSIFIED -- demonstrated envelope would bind' if max_flux > 250.0
                    else 'between 100 and 250: above prediction, below the falsifier')}

    out = {'note': __doc__.strip(), 'base': os.path.relpath(args.base, _REPO),
           'complete': complete, 'n_done': len(done), 'n_planned': len(planned),
           'configuration': ('arm D: --leakage-curve simulated --rbb-policy amortized '
                             '--core-other-policy hierarchy-consistent; 34-core, 88 CFM, target '
                             '92 C, 500 um pitch, 200 um burial, --spreading, h_max {:.0f}'
                             .format(args.h_max)),
           'coverages': coverages, 'densities': densities,
           'ceilings_array_on_by_coverage': {str(c): v for c, v in ceilings.items()},
           'ceiling_control': ctrl_ceiling, 'ceiling_array_idle': idle_ceiling,
           'dQ_vs_full_coverage': dq, 'max_tile_flux_W_per_mm2': max_flux,
           'predictions': checks, 'rows': table,
           'WHAT_COVERAGE_CANNOT_MOVE': (
               'The control arm has no array, so the control ceiling above is the same at every '
               'coverage by construction and the flat-die / shaped ceilings in RESULTS_REGISTER '
               'section 1.3 are untouched. Coverage bounds the ARRAY-assisted density and cost.'),
           'READING_Q': ('All rows share one curve, one policy and one target, so the cross-curve '
                         'normalisation trap does not apply; but the minimum-plan descent stops '
                         'wherever it first holds target, so peaks land at 90-94 C rather than '
                         '92.0. dQ is quoted at matched density with both landing peaks beside it.')}

    print('\n{:>5} {:>6} {:>6} {:>7} {:>5} | {:>10} {:>10} | {:>10} {:>8} {:>8} {:>7} {:>9} {:>8}'.format(
        'cov', 'ach', 'dens', 'resmm2', 'gaps', 'control', 'idle', 'array_on', 'peak_C', 'Q_W', 'net_W',
        'maxflux', 'targets'))
    for r in table:
        print('{:>5.2f} {:>6} {:>6.2f} {:>7} {:>5} | {:>10} {:>10} | {:>10} {:>8} {:>8} {:>7} {:>9} {:>8}'
              .format(r['coverage'],
                      '--' if r['coverage_achieved'] is None else '{:.2f}'.format(r['coverage_achieved']),
                      r['density'],
                      '--' if r['reserved_mm2'] is None else '{:.1f}'.format(r['reserved_mm2']),
                      '--' if r['n_gap_blocks'] is None else str(r['n_gap_blocks']),
                      r['control'], r['array_idle'], r['array_on'],
                      '--' if r['on_peak_C'] is None else '{:.1f}'.format(r['on_peak_C']),
                      '--' if r['heat_removed_W'] is None else '{:.1f}'.format(r['heat_removed_W']),
                      '--' if r['p_mr_net_W'] is None else '{:.1f}'.format(r['p_mr_net_W']),
                      '--' if r['max_tile_flux_W_per_mm2'] is None
                      else '{:.1f}'.format(r['max_tile_flux_W_per_mm2']),
                      '--' if r['n_targets'] is None else str(r['n_targets'])))
    print('\nceilings (array_on): ' + json.dumps({str(c): v for c, v in ceilings.items()}))
    print('control: {}   array_idle: {}'.format(json.dumps(ctrl_ceiling), json.dumps(idle_ceiling)))
    print('\ndQ vs full coverage at matched density:')
    for x in dq:
        print('   c{:.2f} d{:.2f}: {:.2f} -> {:.2f} W ({:+.1f} % raw, {:+.1f} % at a common peak), '
              'peaks {:.1f} / {:.1f} C'.format(
            x['coverage'], x['density'], x['Q_full_W'], x['Q_W'], x['dQ_pct'],
            x['dQ_norm_pct'] if x['dQ_norm_pct'] is not None else float('nan'),
            x['peak_full_C'], x['peak_C']))
    print('\npredictions:')
    for k, v in checks.items():
        print('   {}: {}'.format(k, v.get('verdict')))
    if complete or args.force:
        with open(args.json_out, 'w') as f:
            json.dump(out, f, indent=1)
        print('\nwritten: {}'.format(args.json_out))
    else:
        print('\nNOT written: ladder incomplete ({}/{}). Re-run when it finishes, or --force.'
              .format(len(done), len(planned)))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
