#!/usr/bin/env python
"""§P0.27 step 0: the campaign_inner.sh job list that re-solves the recorded fields X1/X2 read.

    python scripts/x1_fields_queue.py > results/campaign_queue/x1_fields.par4.tsv

One line per field: the rescue ladder (array_on 1.00-2.40, array_idle 1.00-1.10), the native
0.78 control and idle (dark-silicon f1.00), the D1 family's holding array rungs, the twelve F1c
rows. Each job is one `examples/field_resolve.py` call with the row's own heat_removed_W and
peak_C, writing results/fields/<label>/field.json.
"""
import os
import sys
import json
import glob

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(_REPO, 'results', 'fields')


def job(label, run, q, peak):
    d = os.path.join(OUT, label)
    cmd = ('python examples/field_resolve.py --run {run} --label {label} --out {d}/field.json'
           .format(run=run, label=label, d=d))
    if q is not None:
        cmd += ' --expect-removed-W {:.6f}'.format(q)
    if peak is not None:
        cmd += ' --expect-peak-C {:.6f}'.format(peak)
    return '{}\t{}'.format(d, cmd)


def mr_rows(point_dir):
    j = json.load(open(os.path.join(point_dir, 'mr_comparison.json')))
    return {r['arm']: r for r in j['rows']}


def ok(r):
    return r and not r.get('diverged') and not r.get('unconverged') and r.get('peak_C') is not None


def main():
    lines = []
    # the rescue ladder, full coverage
    base = os.path.join(_REPO, 'results', 'array_coverage_armD', 'c1.00')
    for d in ('1.00', '1.10', '1.20', '1.30', '1.40', '1.50', '1.60', '1.70', '1.80', '2.00', '2.20', '2.40'):
        rows = mr_rows(os.path.join(base, 'd' + d))
        for arm in ('array_on', 'array_idle', 'control'):
            r = rows.get(arm)
            if ok(r) and (arm != 'array_on' or r.get('mr_plan_holds_target')):
                lines.append(job('rescue_d%s_%s' % (d, arm), os.path.join(base, 'd' + d, '34c_' + arm),
                                 r.get('heat_removed_W') if arm == 'array_on' else None, r['peak_C']))
    # the native die: dark-silicon 0.78, every core lit
    nat = os.path.join(_REPO, 'results', 'dark_silicon', 'd0.78', 'f1.00')
    rows = mr_rows(nat)
    for arm in ('control', 'array_idle'):
        if ok(rows.get(arm)):
            lines.append(job('native_d0.78_%s' % arm, os.path.join(nat, '34c_' + arm), None, rows[arm]['peak_C']))
    # D1: the dense-cluster family's array rungs
    for member in ('exec0.5', 'exec0.25'):
        for pd in sorted(glob.glob(os.path.join(_REPO, 'results', 'd1_family_arr', member, 'array', 'W*'))):
            rows = mr_rows(pd)
            r = rows.get('array_on')
            if ok(r) and r.get('mr_plan_holds_target'):
                lines.append(job('d1_%s_%s_array_on' % (member, os.path.basename(pd)),
                                 os.path.join(pd, '34c_array_on'), r['heat_removed_W'], r['peak_C']))
    # F1c: the sustainable-clock evaluation of every arm
    for run in ('spice_d0.78', 'spice_d1.00', 'spice_d1.20', 'table_d1.00'):
        rd = os.path.join(_REPO, 'results', 'clock_f1c_density', run)
        j = json.load(open(os.path.join(rd, 'clock_headroom.json')))
        for r in j['rows']:
            arm = r['arm']
            fdirs = glob.glob(os.path.join(rd, 'cfm88_' + arm, 'f*'))
            if not fdirs:
                continue
            f = r['f_sustainable_GHz']
            fd = min(fdirs, key=lambda p: abs(float(os.path.basename(p)[1:]) - f))
            if abs(float(os.path.basename(fd)[1:]) - f) > 0.002:
                sys.stderr.write('skip {} {}: no f dir at {:.3f}\n'.format(run, arm, f))
                continue
            lines.append(job('f1c_%s_%s' % (run, arm), fd, r.get('heat_removed_W') if arm == 'array_on' else None,
                             r['peak_C']))
    sys.stdout.write('\n'.join(lines) + '\n')
    sys.stderr.write('{} fields\n'.format(len(lines)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
