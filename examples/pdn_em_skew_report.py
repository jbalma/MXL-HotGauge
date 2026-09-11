#!/usr/bin/env python
"""X1/X2 (§P0.27): PDN headroom, EM acceleration and thermal clock skew from the RECORDED fields.

    python examples/pdn_em_skew_report.py            # reads results/fields/*/field.json

Nothing here is a thermal measurement of a new configuration. The fields are the recorded solve
trees' final power maps re-solved once through the session (``examples/field_resolve.py``); the
current density is arithmetic on them; every acceleration, lifetime and skew figure is ARGUED on
the constants below, which are stated once and written into the evidence file.

X1 -- the PDN-headroom metric: per block ``J = P / (V_dd A)`` [A/mm^2] against the NATIVE die
(the driver's control at 0.78 W/mm^2, 3.8 GHz, 0.70 V -- the rails a conventional floorplan of
this die is sized for). Black's law ``MTTF ~ J^-n exp(E_a / kT)``: the EM acceleration of a design
against the reference at the same block, and the lifetime ratio between two fields at one block.

X2 -- the thermal-skew metric: one H-tree per domain (core = the 32 blocks sharing a core index,
L3 excluded; die = every block), ``T_skew = D_ins * dT_domain * (w_wire a_R + w_cell a_cell)``,
converted to a frequency cost ``T_skew / T_period`` at the row's clock (SoC Physical Design,
pp. 55-56: the skew term of ``f_max = 1 / (T_comb + T_setup + T_skew + T_jitter)``).
"""
import os
import re
import sys
import json
import glob
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))
_EV = os.path.join(_REPO, 'docs', 'evidence')

#: The assumptions, stated once. Every number they touch is ARGUED.
ASSUMPTIONS = {
    'V_dd_V': 0.70,                    # the trace's supply on every injected-power rung
    'black_n': 2.0,                    # Black's law current exponent (Cu, textbook)
    'black_Ea_eV': 0.9,                # Cu electromigration activation energy (textbook)
    'k_eV_per_K': 8.617333e-5,
    'alpha_R_per_K': 0.0040,           # Cu resistivity, 0.40 %/K
    'alpha_cell_per_K': (1.0 / 0.942 - 1.0) / 100.0,   # delay ~ V/I_on; I_on(400K)/I_on(300K) = 0.942 (SPICE, §P0.18.3)
    'w_wire': 0.5, 'w_cell': 0.5,      # insertion delay split, stated
    'D_ins_core_ps': 150.0,            # H-tree insertion delay, one core (stated)
    'D_ins_die_ps': 500.0,             # one die-level tree (stated; a die this size uses per-core domains)
    'trace_clock_GHz': 3.8,            # the clock the injected-power rungs run at
    'reference_field': 'native_d0.78_control',
    'core_domain_excludes': ['L3'],
    'exec_cluster': ['cALU', 'iALU', 'FPUs', 'AVXs'],
}
_CORE = re.compile(r'^(.*)_(\d+)$')


def fam(name):
    m = _CORE.match(name)
    return m.group(1) if m else name


def core_of(name):
    m = _CORE.match(name)
    return int(m.group(2)) if m and m.group(1) not in ('IO', ) else None


def load_fields(base):
    out = {}
    for f in sorted(glob.glob(os.path.join(base, '*', 'field.json'))):
        j = json.load(open(f))
        if j.get('dry_run') or not j.get('blocks') or j.get('peak_K') is None:
            continue
        out[j['label']] = j
    return out


def f1c_voltage(label):
    """The F1c row's clock and supply from its own V/F source; None for injected-power rungs."""
    m = re.match(r'f1c_(spice|table)_d([0-9.]+)_(control|array_idle|array_on)$', label)
    if not m:
        return None, None
    run = '{}_d{}'.format(m.group(1), m.group(2))
    j = json.load(open(os.path.join(_REPO, 'results', 'clock_f1c_density', run, 'clock_headroom.json')))
    row = [r for r in j['rows'] if r['arm'] == m.group(3)][0]
    f = row['f_sustainable_GHz']
    if m.group(1) == 'table':
        from HotGauge.power.performance_model import voltage_for_frequency
        v, _ = voltage_for_frequency(f)
    else:
        from HotGauge.power.device_vf import load_device_vf
        v, _ = load_device_vf(T_K=300.0).voltage(f)
    return f, float(v)


def field_metrics(fld, ref, A):
    """Per-field X1/X2 numbers against the reference field ``ref`` (same block names)."""
    V = fld['V_V']
    Vr = ref['V_V']
    blocks = fld['blocks']
    rb = ref['blocks']
    area = {n: b['w_um'] * b['h_um'] * 1e-6 for n, b in blocks.items()}
    J = {n: b['P_W'] / (V * area[n]) for n, b in blocks.items()}
    Jr = {n: rb[n]['P_W'] / (Vr * (rb[n]['w_um'] * rb[n]['h_um'] * 1e-6)) for n in rb}
    T = {n: b['T_K'] for n, b in blocks.items()}
    Tr = {n: rb[n]['T_K'] for n in rb}
    A_die = sum(area.values())
    A_ref = sum(rb[n]['w_um'] * rb[n]['h_um'] * 1e-6 for n in rb)
    I = sum(b['P_W'] for b in blocks.values()) / V
    Ir = sum(b['P_W'] for b in rb.values()) / Vr
    common = [n for n in blocks if n in rb and Jr[n] > 0]
    ratio = {n: J[n] / Jr[n] for n in common}
    peak = fld['peak_block']
    ex = [n for n in common if fam(n) in A['exec_cluster']]
    kT = A['k_eV_per_K']
    Ea, n_ = A['black_Ea_eV'], A['black_n']

    def af(nm):     # EM acceleration of this field against the reference at the same block
        return (ratio[nm] ** n_) * np.exp(Ea / kT * (1.0 / Tr[nm] - 1.0 / T[nm]))

    def af_T(nm):   # the temperature term alone
        return float(np.exp(Ea / kT * (1.0 / Tr[nm] - 1.0 / T[nm])))
    af_all = {nm: float(af(nm)) for nm in common}
    worst = max(af_all, key=af_all.get)
    # X2: gradients per domain
    cores = {}
    for nm, t in T.items():
        c = core_of(nm)
        if c is None or fam(nm) in A['core_domain_excludes']:
            continue
        cores.setdefault(c, []).append(t)
    dT_core = {c: max(v) - min(v) for c, v in cores.items()}
    worst_core = max(dT_core, key=dT_core.get)
    dT_die = max(T.values()) - min(T.values())
    coef = A['w_wire'] * A['alpha_R_per_K'] + A['w_cell'] * A['alpha_cell_per_K']
    f = fld['clock_GHz']
    period_ps = 1000.0 / f
    skew_core_ps = A['D_ins_core_ps'] * dT_core[worst_core] * coef
    skew_core_mean_ps = A['D_ins_core_ps'] * float(np.mean(list(dT_core.values()))) * coef
    skew_die_ps = A['D_ins_die_ps'] * dT_die * coef
    return {
        'label': fld['label'], 'V_V': V, 'clock_GHz': f, 'P_W': fld['sum_P_W'], 'Q_W': -fld['sum_MR_W'],
        'A_die_mm2': A_die, 'peak_C': fld['peak_C'], 'peak_block': peak,
        'peak_error_K': fld.get('peak_error_K'), 'expect_peak_C': fld.get('expect_peak_C'),
        # X1
        'I_total_A': I, 'I_ratio': I / Ir, 'J_die_avg_A_per_mm2': I / A_die,
        'J_die_avg_ratio': (I / A_die) / (Ir / A_ref),
        'J_ratio_median': float(np.median(list(ratio.values()))),
        'J_ratio_max': max(ratio.values()), 'J_ratio_max_block': max(ratio, key=ratio.get),
        'J_ratio_at_peak_block': ratio.get(peak), 'J_at_peak_block_A_per_mm2': J[peak],
        'J_ratio_exec_max': max(ratio[n] for n in ex), 'J_ratio_exec_max_block': max(ex, key=lambda n: ratio[n]),
        'J_exec_max_A_per_mm2': max(J[n] for n in ex),
        'EM_AF_at_peak_block': af_all.get(peak), 'EM_AF_T_term_at_peak_block': af_T(peak),
        'EM_AF_max': af_all[worst], 'EM_AF_max_block': worst,
        'T_peak_block_K': T[peak], 'T_ref_at_peak_block_K': Tr.get(peak),
        # X2
        'dT_core_max_K': dT_core[worst_core], 'dT_core_max_core': worst_core,
        'dT_core_mean_K': float(np.mean(list(dT_core.values()))), 'dT_die_K': dT_die,
        'skew_core_ps': skew_core_ps, 'skew_core_mean_ps': skew_core_mean_ps, 'skew_die_ps': skew_die_ps,
        'period_ps': period_ps,
        'skew_cost_core_pct': 100.0 * skew_core_ps / period_ps,
        'skew_cost_core_mean_pct': 100.0 * skew_core_mean_ps / period_ps,
        'skew_cost_die_pct': 100.0 * skew_die_ps / period_ps,
        '_J': J, '_T': T,
    }


def lifetime_ratio(a, b, block, A):
    """MTTF(a) / MTTF(b) at one block: (J_b/J_a)^n exp(Ea/k (1/T_a - 1/T_b))."""
    Ja, Jb = a['_J'][block], b['_J'][block]
    Ta, Tb = a['_T'][block], b['_T'][block]
    if Ja <= 0 or Jb <= 0:
        return None
    return float((Jb / Ja) ** A['black_n'] * np.exp(A['black_Ea_eV'] / A['k_eV_per_K'] * (1.0 / Ta - 1.0 / Tb)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=os.path.join(_REPO, 'results', 'fields'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'pdn_em_skew.json'))
    args = ap.parse_args()
    A = dict(ASSUMPTIONS)
    fields = load_fields(args.base)
    if A['reference_field'] not in fields:
        raise SystemExit('reference field {} not solved yet'.format(A['reference_field']))
    for lab, fld in fields.items():
        f, v = f1c_voltage(lab)
        fld['clock_GHz'] = f or A['trace_clock_GHz']
        fld['V_V'] = v or A['V_dd_V']
    ref = fields[A['reference_field']]
    M = {lab: field_metrics(fld, ref, A) for lab, fld in fields.items()}

    print('%-34s %5s %5s %6s %6s | %6s %6s %6s %-9s %6s %6s | %6s %6s %6s %6s %6s' % (
        'field', 'V', 'GHz', 'P_W', 'Q_W', 'I/Iref', 'Jav/r', 'Jpk/r', 'peak', 'AF_pk', 'AFmax', 'dTcore', 'dTdie', 'sk%c', 'sk%d', 'errK'))
    for lab in sorted(M, key=lambda l: (l.split('_')[0], l)):
        m = M[lab]
        print('%-34s %5.2f %5.2f %6.1f %6.1f | %6.2f %6.2f %6.2f %-9s %6.2f %6.2f | %6.1f %6.1f %6.2f %6.1f %6s' % (
            lab, m['V_V'], m['clock_GHz'], m['P_W'], m['Q_W'], m['I_ratio'], m['J_die_avg_ratio'], m['J_ratio_at_peak_block'] or 0,
            m['peak_block'], m['EM_AF_at_peak_block'] or 0, m['EM_AF_max'], m['dT_core_max_K'], m['dT_die_K'],
            m['skew_cost_core_pct'], m['skew_cost_die_pct'], '' if m['peak_error_K'] is None else '%+.2f' % m['peak_error_K']))

    # pairwise lifetime ratios at matched operating points (the reliability dividend)
    pairs = [('rescue_d1.10_array_on', 'rescue_d1.10_array_idle', 'same injected power, 1.10 W/mm^2'),
             ('native_d0.78_array_idle', 'native_d0.78_control', 'the GaAs layer alone at native power'),
             ('f1c_spice_d1.00_array_on', 'f1c_spice_d1.00_control', 'F1c 1.00: laser at its clock vs control at its clock'),
             ('f1c_spice_d1.20_array_on', 'f1c_spice_d1.20_control', 'F1c 1.20: same'),
             ('f1c_table_d1.00_array_on', 'f1c_table_d1.00_control', 'F1c table: same'),
             ('f1c_spice_d1.00_array_on', 'f1c_spice_d1.00_array_idle', 'F1c 1.00: laser vs unpowered array')]
    pairwise = []
    for a, b, why in pairs:
        if a in M and b in M:
            blk = M[b]['peak_block']
            r = lifetime_ratio(M[a], M[b], blk, A)
            rT = float(np.exp(A['black_Ea_eV'] / A['k_eV_per_K'] * (1.0 / M[a]['_T'][blk] - 1.0 / M[b]['_T'][blk])))
            pairwise.append({'a': a, 'b': b, 'why': why, 'block': blk, 'MTTF_a_over_b': r, 'T_term': rT,
                             'J_term': (r / rT) if (r and rT) else None,
                             'T_a_C': M[a]['_T'][blk] - 273.15, 'T_b_C': M[b]['_T'][blk] - 273.15,
                             'J_a': M[a]['_J'][blk], 'J_b': M[b]['_J'][blk]})
    print('\nlifetime ratios at the comparator\'s peak block (MTTF a / MTTF b; T term alone in brackets):')
    for p in pairwise:
        print('  %-28s / %-28s %-7s %6.2fx (%5.2fx)  %s' % (p['a'], p['b'], p['block'], p['MTTF_a_over_b'] or 0, p['T_term'], p['why']))
    # the design-level statement: each field's OWN worst EM block against the reference, and a/b
    print('\nEM acceleration vs the native die at each field\'s own worst block (AF_max; a/b = the b design\'s worst block ages AF_b/AF_a slower):')
    for p in pairwise:
        a, b = M[p['a']], M[p['b']]
        p['AF_max_a'], p['AF_max_a_block'] = a['EM_AF_max'], a['EM_AF_max_block']
        p['AF_max_b'], p['AF_max_b_block'] = b['EM_AF_max'], b['EM_AF_max_block']
        p['worst_block_lifetime_a_over_b'] = b['EM_AF_max'] / a['EM_AF_max']
        print('  %-28s %6.1fx at %-9s / %-28s %6.1fx at %-9s -> %5.2fx' % (
            p['a'], a['EM_AF_max'], a['EM_AF_max_block'], p['b'], b['EM_AF_max'], b['EM_AF_max_block'], p['worst_block_lifetime_a_over_b']))
    print('\nworst EM block per field (AF_max block, its J ratio and temperature):')
    for lab in sorted(M):
        m = M[lab]; blk = m['EM_AF_max_block']
        print('  %-34s %-10s AF %7.1f  J/Jref %5.2f  T %6.1f C  (peak-T block %s at %.1f C, AF %.1f)' % (
            lab, blk, m['EM_AF_max'], m['_J'][blk] / (ref['blocks'][blk]['P_W'] / (ref['V_V'] * ref['blocks'][blk]['w_um'] * ref['blocks'][blk]['h_um'] * 1e-6)),
            m['_T'][blk] - 273.15, m['peak_block'], m['peak_C'], m['EM_AF_at_peak_block'] or 0))

    # skew comparisons for P6 / P7 / P8
    def dcost(a, b):
        return (M[a]['skew_cost_core_pct'] - M[b]['skew_cost_core_pct']) if (a in M and b in M) else None
    skew_pairs = {
        'P6_f1c_spice_d1.00_control_minus_laser_pct': dcost('f1c_spice_d1.00_control', 'f1c_spice_d1.00_array_on'),
        'P6_f1c_spice_d1.20_control_minus_laser_pct': dcost('f1c_spice_d1.20_control', 'f1c_spice_d1.20_array_on'),
        'P6_f1c_table_d1.00_control_minus_laser_pct': dcost('f1c_table_d1.00_control', 'f1c_table_d1.00_array_on'),
        'P6_rescue_d1.10_idle_minus_on_pct': dcost('rescue_d1.10_array_idle', 'rescue_d1.10_array_on'),
    }

    def dtc(l):
        return M[l]['dT_core_max_K'] if l in M else None
    d1 = {}
    for W, ref_lab in (('W121.316', 'rescue_d1.20_array_on'), ('W161.755', 'rescue_d1.60_array_on'), ('W202.194', 'rescue_d2.00_array_on')):
        for mem in ('exec0.5', 'exec0.25'):
            lab = 'd1_%s_%s_array_on' % (mem, W)
            if lab in M and ref_lab in M:
                d1['%s_%s_dTcore_ratio' % (mem, W)] = M[lab]['dT_core_max_K'] / M[ref_lab]['dT_core_max_K']
    p8 = (M['rescue_d2.00_array_on']['dT_core_max_K'] / M['rescue_d1.20_array_on']['dT_core_max_K']
          if 'rescue_d2.00_array_on' in M and 'rescue_d1.20_array_on' in M else None)

    # scorecard
    sc = {}
    errs = {l: m['peak_error_K'] for l, m in M.items() if m['peak_error_K'] is not None}
    worst_err = max(errs, key=lambda l: abs(errs[l])) if errs else None
    sc['P0_resolve_reproduces'] = {'worst_label': worst_err, 'worst_error_K': errs.get(worst_err), 'n': len(errs),
                                   'verdict': 'confirmed' if errs and max(abs(v) for v in errs.values()) <= 1.0 else 'FALSIFIED'}
    rungs = {d: M.get('rescue_d%s_array_on' % d) for d in ('1.20', '1.60', '2.00', '2.40')}
    rungs['1.00'] = M.get('rescue_d1.00_array_idle')
    p1 = {d: (m['I_ratio'], m['J_ratio_at_peak_block'] / m['J_die_avg_ratio']) for d, m in rungs.items() if m}
    sc['P1_current_ladder'] = {'I_ratio_by_rung': {d: v[0] for d, v in p1.items()}, 'peak_over_avg_by_rung': {d: v[1] for d, v in p1.items()},
                               'verdict': 'confirmed' if p1 and all(v[1] <= 1.3 for v in p1.values()) else ('FALSIFIED: peak-block ratio > 1.3x die-average' if p1 else 'open')}
    p2 = {}
    for mem, lo, hi in (('exec0.5', 1.8, 2.6), ('exec0.25', 3.6, 5.2)):
        vals = {W: M['d1_%s_%s_array_on' % (mem, W)]['J_ratio_exec_max'] / M[r]['J_ratio_exec_max']
                for W, r in (('W121.316', 'rescue_d1.20_array_on'), ('W161.755', 'rescue_d1.60_array_on'), ('W202.194', 'rescue_d2.00_array_on'))
                if 'd1_%s_%s_array_on' % (mem, W) in M and r in M}
        p2[mem] = {'cluster_J_ratio_vs_reference_at_matched_watts': vals,
                   'I_ratio_vs_reference': {W: M['d1_%s_%s_array_on' % (mem, W)]['I_ratio'] / M[r]['I_ratio']
                                            for W, r in (('W121.316', 'rescue_d1.20_array_on'), ('W161.755', 'rescue_d1.60_array_on'), ('W202.194', 'rescue_d2.00_array_on'))
                                            if 'd1_%s_%s_array_on' % (mem, W) in M and r in M}}
    v05 = list(p2.get('exec0.5', {}).get('cluster_J_ratio_vs_reference_at_matched_watts', {}).values())
    sc['P2_dense_cluster_rails'] = dict(p2, verdict=('confirmed' if v05 and all(1.8 <= v <= 2.6 for v in v05) else ('FALSIFIED' if v05 else 'open')))
    p3 = {l: M[l]['I_ratio'] for l in ('f1c_spice_d1.00_array_on', 'f1c_spice_d1.20_array_on', 'f1c_table_d1.00_array_on') if l in M}
    sc['P3_clock_rungs_current'] = {'I_ratio_vs_native': p3,
                                    'verdict': ('confirmed' if p3 and p3.get('f1c_table_d1.00_array_on', 9) <= 2.0 and p3.get('f1c_spice_d1.20_array_on', 0) >= 1.5 else ('FALSIFIED' if p3 else 'open'))}
    sc['P4_reliability_dividend'] = {'pairs': pairwise,
                                     'verdict': ('confirmed' if any(p['MTTF_a_over_b'] and 1.5 <= p['MTTF_a_over_b'] <= 2.6 for p in pairwise[:2]) else 'NOT as predicted')}
    p5 = {l: (M[l]['dT_core_max_K'], M[l]['skew_cost_core_pct'], M[l]['skew_cost_die_pct']) for l in ('rescue_d1.20_array_on', 'rescue_d1.60_array_on', 'rescue_d2.00_array_on') if l in M}
    sc['P5_skew_magnitude'] = {'dTcore_costcore_costdie': p5,
                               'verdict': ('confirmed' if p5 and all(2.5 <= v[1] <= 5.0 for v in p5.values()) else ('NOT as predicted' if p5 else 'open'))}
    vals6 = [v for v in skew_pairs.values() if v is not None and 'f1c' in [k for k, vv in skew_pairs.items() if vv == v][0]]
    sc['P6_uniformity_lever'] = {'core_skew_cost_control_minus_laser_pct': skew_pairs,
                                 'verdict': ('confirmed' if vals6 and all(1.0 <= v <= 3.0 for v in vals6) else
                                             ('FALSIFIED: < 0.5 % or the laser field less uniform' if vals6 and any(v < 0.5 for v in vals6) else ('NOT as predicted' if vals6 else 'open')))}
    v7 = [v for k, v in d1.items() if k.startswith('exec0.5')]
    sc['P7_density_costs_skew'] = {'dTcore_member_over_reference': d1,
                                   'verdict': ('confirmed' if v7 and all(1.2 <= v <= 1.5 for v in v7) else ('FALSIFIED: <= 1.1x' if v7 and any(v <= 1.1 for v in v7) else ('NOT as predicted' if v7 else 'open')))}
    sc['P8_gradient_grows'] = {'dTcore_2.00_over_1.20': p8, 'verdict': ('confirmed' if p8 and p8 >= 1.5 else ('FALSIFIED: flat within 20 %' if p8 and p8 < 1.2 else ('NOT as predicted' if p8 else 'open')))}
    print('\nscorecard:')
    for k, v in sc.items():
        print('  %-28s %s' % (k, v['verdict']))

    out = {'note': __doc__.strip(), 'assumptions': A, 'n_fields': len(M),
           'fields': {l: {k: v for k, v in m.items() if not k.startswith('_')} for l, m in M.items()},
           'lifetime_pairs': pairwise, 'skew_pairs': skew_pairs, 'd1_dTcore_ratios': d1, 'scorecard': sc}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten:', os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
