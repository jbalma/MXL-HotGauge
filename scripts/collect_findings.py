#!/usr/bin/env python
"""Harvest every result directory into one machine-readable findings file.

    python scripts/collect_findings.py [--out docs/evidence/FINDINGS.json]

Why this exists: by the end of a long study the numbers live in a dozen result directories in
three output formats, and a summary written from memory is exactly how a retracted figure gets
quoted a second time. This reads the JSON that the runs actually produced, records the
verification status alongside every value, and refuses to report a number whose point failed
damping verification without saying so.

It is deliberately dumb about interpretation -- it collects and labels, and the reading is in
docs/. What it does enforce is that every entry carries: where it came from, whether it
converged, whether it was damping-verified, and whether the plan (if any) held its target.
"""
import os
import sys
import json
import glob
import argparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO, 'results')


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (IOError, ValueError):
        return None


def collect_mr_comparison(pattern, label):
    """mr_comparison.py output: MR on/off pairs at a density."""
    out = []
    for path in sorted(glob.glob(pattern)):
        d = _load(path)
        if not d:
            continue
        rows = {r['mr']: r for r in d.get('rows', [])}
        a, b = rows.get(False), rows.get(True)
        if a is None or b is None:
            continue
        tag = os.path.basename(os.path.dirname(path))
        entry = {'source': os.path.relpath(path, REPO), 'tag': tag, 'family': label,
                 'density': d.get('density'), 'cfm': d.get('cfm'), 'r_th': d.get('r_th'),
                 'no_mr': {'diverged': a.get('diverged'), 'unconverged': a.get('unconverged'),
                           'peak_C': a.get('peak_C')},
                 'mr': {'diverged': b.get('diverged'), 'unconverged': b.get('unconverged'),
                        'peak_C': b.get('peak_C'), 'heat_removed_W': b.get('heat_removed_W'),
                        'p_mr_net_W': b.get('p_mr_net_W'), 'n_targets': b.get('n_targets'),
                        'holds_target': b.get('mr_plan_holds_target'),
                        'plan_is_minimum': b.get('mr_plan_is_minimum'),
                        'reason': b.get('mr_reason')}}
        # Verification applies to the solve that produced the reported field. Older runs only
        # recorded "some solve failed", so fall back to that for them and say so in the entry --
        # a legacy flag must not be silently upgraded to a clean bill of health.
        legacy = ('n_probe_solves_unconverged' not in b)
        entry['verification_scope'] = 'any-solve (legacy)' if legacy else 'reported-field'
        entry['n_probe_solves_unconverged'] = b.get('n_probe_solves_unconverged')
        entry['quotable'] = bool(not a.get('unconverged') and not b.get('unconverged'))
        out.append(entry)
    return out


def collect_tiers(pattern, label):
    out = []
    for path in sorted(glob.glob(pattern)):
        d = _load(path)
        if not d:
            continue
        out.append({'source': os.path.relpath(path, REPO),
                    'tag': os.path.basename(os.path.dirname(path)), 'family': label,
                    'density': d.get('density'),
                    'actual_density': d.get('actual_density_W_per_mm2'),
                    'activity': d.get('activity'), 'emphasise': d.get('emphasise'),
                    'emphasis_factor': d.get('emphasis_factor'),
                    'dt_max_K': d.get('dt_max_K'), 'peak_C': d.get('peak_C'),
                    'peak_block': d.get('peak_block'),
                    'plateau': d.get('plateau_within_dt_max'),
                    'clip_one_gain_K': (d.get('clip_curve') or [{}])[0].get('gain_K'),
                    'n_needed_for_full_dt_max': d.get('n_needed_for_full_dt_max'),
                    'quotable': True})
    return out


def collect_clock(pattern, label):
    out = []
    for path in sorted(glob.glob(pattern)):
        d = _load(path)
        if not d:
            continue
        for r in d.get('rows', []):
            out.append({'source': os.path.relpath(path, REPO),
                        'tag': os.path.basename(os.path.dirname(path)), 'family': label,
                        'mr': r.get('mr'), 'mr_mode': d.get('mr_mode'),
                        'mr_target_C': d.get('mr_target_C'),
                        'emphasise': d.get('emphasise'), 'turbo_core': d.get('turbo_core'),
                        'r_th': r.get('r_th'), 'cfm': r.get('cfm'),
                        'f_sustainable_GHz': r.get('f_sustainable_GHz'),
                        'limited_by': r.get('limited_by'),
                        'voltage_limited': r.get('voltage_limited'),
                        'peak_C': r.get('peak_C'), 'p_chip_W': r.get('p_chip_W'),
                        'p_mr_net_W': r.get('p_mr_net_W'),
                        'heat_removed_W': r.get('heat_removed_W'),
                        'unconverged': r.get('unconverged'),
                        # The V/F caveat travels with every clock number, because it is the one
                        # place an absolute figure here is known to be wrong.
                        'vf_caveat': 'table needs ~2x the IRDS 2024 Vdd for the same clock; '
                                     'absolute power and any clock CEILING are overstated',
                        'quotable': bool(not r.get('unconverged'))})
    return out


def collect_stacked(pattern, label):
    out = []
    for path in sorted(glob.glob(pattern)):
        d = _load(path)
        if not d:
            continue
        entry = {'source': os.path.relpath(path, REPO),
                 'tag': os.path.basename(os.path.dirname(path)), 'family': label,
                 'mem_dies': d.get('mem_dies'), 'mem_density': d.get('mem_density'),
                 'emphasise': d.get('emphasise'), 'binding': d.get('binding'),
                 'diverged': d.get('diverged'), 'unconverged': d.get('unconverged'),
                 'calibrated': d.get('calibrated', False)}
        for layer in ('logic', 'memory'):
            if d.get(layer):
                entry[layer] = {'peak_C': d[layer].get('peak_C'),
                                'plateau': d[layer].get('plateau_within_dt_max'),
                                'clip_one_gain_K': d[layer].get('clip_one_gain_K'),
                                'peak_block': d[layer].get('peak_block')}
        entry['logic_margin_K'] = d.get('logic_margin_K')
        entry['mem_margin_K'] = d.get('mem_margin_K')
        entry['dram_report'] = d.get('dram_report')
        entry['quotable'] = bool(not d.get('unconverged') and not d.get('diverged'))
        out.append(entry)
    return out


def collect_accelerator(pattern, label):
    """accelerator_study.py output: the GA100 die-shot floorplan.

    Kept separate from the CPU families because its power split is an ASSUMPTION rather than a
    McPAT extraction, and mixing it into a table of measured points is exactly how that
    distinction gets lost.
    """
    out = []
    for path in sorted(glob.glob(pattern)):
        d = _load(path)
        if not d:
            continue
        t = d.get('tiers') or {}
        entry = {'source': os.path.relpath(path, REPO),
                 'tag': os.path.basename(os.path.dirname(path)), 'family': label,
                 'die_mm2': d.get('die_mm2'), 'n_blocks': d.get('n_blocks'),
                 'die_power_W': d.get('die_power_W'),
                 'density_W_per_mm2': d.get('density_W_per_mm2'),
                 'cell_um': d.get('cell_um'), 'split_sm': d.get('split_sm'),
                 'leak_fraction': d.get('leak_fraction'), 'leak_basis': d.get('leak_basis'),
                 'cfm': d.get('cfm'), 'r_th': d.get('r_th'),
                 'peak_C': t.get('peak_C'), 'peak_block': t.get('peak_block'),
                 'peak_class': t.get('peak_class'),
                 'plateau_within_dt_max': t.get('plateau_within_dt_max'),
                 'clip_one_gain_K': t.get('clip_one_gain_K'),
                 'n_needed_for_full_dt_max': t.get('n_needed_for_full_dt_max'),
                 'diverged': d.get('diverged'), 'unconverged': d.get('unconverged'),
                 # Loud, because this is the one family where it is true of the INPUT.
                 'calibrated': False,
                 'power_split_is_assumed': True,
                 'caveat': 'areas measured from die shots; the per-class POWER split is assumed '
                           '(GA100_POWER_SPLIT). The plateau result does not depend on it -- the '
                           'tiles are uniform under any split -- but WHICH block is the peak does'}
        entry['quotable'] = bool(not d.get('unconverged') and not d.get('diverged'))
        out.append(entry)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'evidence', 'FINDINGS.json'))
    args = ap.parse_args()

    R = lambda *p: os.path.join(RESULTS, *p)
    findings = {
        'note': 'Harvested from the JSON the runs produced, not written from memory. Every '
                'entry carries its convergence and verification status; "quotable" false means '
                'the point failed damping verification and must not be reported as a result.',
        'cliff': collect_mr_comparison(R('cliff_verified', '*', 'mr_comparison.json'),
                                       'cliff (34-core, 88 CFM, target 92 C)'),
        'overnight3': collect_mr_comparison(R('overnight3', '*', 'mr_comparison.json'),
                                            'overnight3 study'),
        'rescue_target98': collect_mr_comparison(R('design_batch', 'rescue_*',
                                                   'mr_comparison.json'),
                                                 'rescue at target 98 C'),
        # The nextsteps re-runs supersede the gapfill copies of the same points: those were
        # decided by the any-solve rule, which condemned them for probe failures rather than for
        # the field they reported. Both are collected -- the tag says which -- so a reader can see
        # that the re-measurement agreed rather than taking it on trust.
        'margin_curve': (collect_mr_comparison(R('gapfill', 'margin_*', 'mr_comparison.json'),
                                               'rescue cost vs margin demanded (legacy rule)')
                         + collect_mr_comparison(R('nextsteps', 'margin_*',
                                                   'mr_comparison.json'),
                                                 'margin curve 1, 1.10 W/mm^2 air')
                         + collect_mr_comparison(R('nextsteps', 'margin2_*',
                                                   'mr_comparison.json'),
                                                 'margin curve 2, 1.15 W/mm^2 air')
                         + collect_mr_comparison(R('nextsteps', 'margin3_*',
                                                   'mr_comparison.json'),
                                                 'margin curve 3, 1.10 W/mm^2 liquid')),
        'pitch': (collect_mr_comparison(R('gapfill', 'spot_*', 'mr_comparison.json'),
                                        'pixel pitch and policy (legacy rule)')
                  + collect_mr_comparison(R('nextsteps', 'pitch_*', 'mr_comparison.json'),
                                          'pixel pitch and policy, re-verified')),
        'core_scaling': (collect_mr_comparison(R('gapfill', 'cores128_*',
                                                 'mr_comparison.json'), '128-core scaling')
                         + collect_mr_comparison(R('nextsteps', 'cores128_*',
                                                   'mr_comparison.json'),
                                                 '128-core scaling, re-verified')),
        'ceiling': collect_mr_comparison(R('nextsteps', 'ceiling_*', 'mr_comparison.json'),
                                         'above the cliff'),
        'tiers': (collect_tiers(R('tiers_*', 'tiers.json'), 'tier screens')
                  + collect_tiers(R('design_batch', 'F_*', 'tiers.json'), 'dt_max roadmap')),
        'clock': (collect_clock(R('cooling_for_clock', '*', 'clock_headroom.json'),
                                'cooling sweep')
                  + collect_clock(R('turbo_*', 'clock_headroom.json'), 'turbo / design A')
                  + collect_clock(R('clock_target_*', 'clock_headroom.json'), 'MR target sweep')
                  + collect_clock(R('leakv_*', 'clock_headroom.json'), 'leakage-V sensitivity')
                  + collect_clock(R('design_batch', 'E_*', 'clock_headroom.json'),
                                  'distributed MR control arm')),
        'stacked': (collect_stacked(R('d_smoke', 'stacked_memory.json'), 'stacked memory')
                    + collect_stacked(R('design_batch', 'D_*', 'stacked_memory.json'),
                                      'stacked memory')
                    + collect_stacked(R('gapfill', 'D_*', 'stacked_memory.json'),
                                      'stacked memory, deep')
                    + collect_stacked(R('nextsteps', 'D_*', 'stacked_memory.json'),
                                      'stacked memory, deep (coarse grid)')),
        'accelerator': collect_accelerator(R('accel*', '*', 'accelerator_study.json'),
                                           'GA100 floorplan')
                       + collect_accelerator(R('accel_smoke', 'accelerator_study.json'),
                                             'GA100 floorplan'),
    }

    counts, unquotable = {}, []
    for k, v in findings.items():
        if isinstance(v, list):
            counts[k] = len(v)
            # Qualified by source, not by tag: re-runs deliberately reuse a tag so the old and new
            # measurements of a point can be compared, so a bare tag no longer identifies a run
            # and "margin_T95_d1.10 failed" would not say WHICH one.
            unquotable += ['{} [{}]'.format(e.get('tag'), e.get('source'))
                           for e in v if e.get('quotable') is False]
    findings['summary'] = {'counts': counts, 'n_failed_verification': len(unquotable),
                           'failed_verification': sorted(set(unquotable))}

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(findings, f, indent=2)

    print('collected into {}'.format(os.path.relpath(args.out, REPO)))
    for k, n in sorted(counts.items()):
        print('  {:<18s} {:>3d} entries'.format(k, n))
    print('  {} entries failed verification and are flagged unquotable'.format(len(unquotable)))
    if unquotable:
        print('    ' + ', '.join(sorted(set(unquotable))[:10]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
