#!/usr/bin/env python
"""§P0.31 part 1: the generalized f_max model's own arithmetic, before any coupled solve.

    python examples/fmax_model_report.py          # -> docs/evidence/fmax_model.json

Nothing here is a thermal measurement. It tabulates what ``HotGauge.power.fmax_model`` says at a
GIVEN worst-block temperature and core gradient -- the reliability-budgeted V_max per mechanism,
the device's peak-clock supply, the ceiling and what sets it, the period's composition, the
logic depth 10 GHz would need -- under the stated constants and their sweeps, and scores the
model-arithmetic predictions P1-P3 of §P0.31. The coupled clock search (``scripts/clock_fmax.sh``)
is what turns these into operating points.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))
_EV = os.path.join(_REPO, 'docs', 'evidence')

from HotGauge.power.fmax_model import load_fmax_model, DEFAULTS      # noqa: E402
from HotGauge.power.device_vf import load_device_vf                  # noqa: E402

T_TABLE_C = [27.0, 40.0, 50.0, 60.0, 70.0, 78.6, 85.0, 92.0, 100.0]


def ceiling_row(m, T_K, dT_K):
    c = m.f_max_at(T_K, dT_K)
    rel = m.v_max_reliability(T_K, dT_K)
    per = c['period']
    return {'T_C': T_K - 273.15, 'dT_K': dT_K, 'f_max_GHz': c['f_max_GHz'], 'v_ceiling_V': c['v_max_V'],
            'limiter': c['limiter'], 'v_max_reliability_V': rel['v_max_V'],
            'v_max_over_vdd': rel['v_max_over_vdd'], 'reliability_binding': rel['binding'],
            'v_max_per_mechanism_V': {k: v['v_max_V'] for k, v in rel['per_mechanism'].items()},
            'sweep_limited': {k: v['sweep_limited'] for k, v in rel['per_mechanism'].items()},
            'v_device_peak_V': c['v_device_peak_V'], 'f_device_peak_GHz': c['f_device_peak_GHz'],
            'period_ps': per['period_ps'],
            'fractions': {k: per[k + '_frac'] for k in ('gate', 'wire', 'skew', 'overhead')},
            'dominant_term': c['dominant_term'],
            'f_at_vdd_GHz': m.frequency(m.vdd, T_K, dT_K),
            'f_at_0.77V_GHz': m.frequency(0.77, T_K, dT_K),
            'logic_depth_for_10GHz': m.logic_depth_for(10.0, c['v_max_V'], T_K, dT_K),
            'logic_depth_for_10GHz_at_vdd': m.logic_depth_for(10.0, m.vdd, T_K, dT_K)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'fmax_model.json'))
    ap.add_argument('--dT-K', type=float, default=DEFAULTS['dT_anchor_K'],
                    help='core-domain gradient assumed for the tables (X2: 24 K native, 32-60 K on the ladder)')
    args = ap.parse_args()
    m = load_fmax_model()
    out = {'note': __doc__.strip(), 'model': m.describe(), 'source': m.source_meta, 'tables': {}}
    print(m)
    print('anchor: FO4_ref %.2f ps, wire/stage %.2f ps, skew %.1f ps, overhead %.1f ps at %.2f GHz'
          % (m.FO4_ref_ps, m.wire_ref_ps, m.T_skew0_ps, m.T_ovh_ps, m.f_anchor))

    # -- the ceiling versus the worst block's temperature, both budget references ------------
    for ref in ('qual', 'native'):
        mm = load_fmax_model(budget_ref=ref)
        rows = [ceiling_row(mm, T + 273.15, args.dT_K) for T in T_TABLE_C]
        out['tables']['ceiling_vs_T_' + ref] = rows
        print('\nbudget reference %r (V_q %.3f V, T_q %.1f C, f_q %.3f GHz), dT %.0f K'
              % (ref, mm._budget['V_q_V'], mm._budget['T_q_K'] - 273.15, mm._budget['f_q_GHz'], args.dT_K))
        print('  %6s %8s %8s %8s %8s %-18s %7s %6s %6s %6s %6s %6s' % (
            'T_C', 'Vmax_rel', 'Vmax_em', 'Vmax_tddb', 'V_pk', 'limiter', 'f_max', 'gate', 'wire', 'skew', 'ovh', 'N@10G'))
        for r in rows:
            print('  %6.1f %8.3f %8.3f %8.3f %8.3f %-18s %7.3f %6.2f %6.2f %6.2f %6.2f %6s' % (
                r['T_C'], r['v_max_reliability_V'], r['v_max_per_mechanism_V'].get('em', 0),
                r['v_max_per_mechanism_V'].get('tddb', 0), r['v_device_peak_V'], r['limiter'],
                r['f_max_GHz'], r['fractions']['gate'], r['fractions']['wire'], r['fractions']['skew'],
                r['fractions']['overhead'], '--' if r['logic_depth_for_10GHz'] is None else '%.1f' % r['logic_depth_for_10GHz']))

    # -- the device's f(V) at a few temperatures: where it peaks --------------------------------
    fv = {}
    for T in (300.0, 330.0, 365.0, 373.15):
        grid = [round(v, 3) for v in m.V]
        fv['%.0fK' % T] = {'V': grid, 'f_GHz': [m.frequency(v, T, args.dT_K) for v in grid],
                           'peak': dict(zip(('V_V', 'f_GHz', 'at_sweep_end'), m.device_peak(T, args.dT_K)))}
    out['tables']['f_of_V'] = fv
    print('\ndevice peak clock (dT %.0f K): ' % args.dT_K + ', '.join(
        '%s: %.3f GHz at %.3f V%s' % (k, v['peak']['f_GHz'], v['peak']['V_V'], ' (sweep end)' if v['peak']['at_sweep_end'] else '')
        for k, v in fv.items()))

    # -- the old model, for the record ---------------------------------------------------------
    old = load_device_vf(T_K=300.0)
    out['device_vf_model'] = {'repr': repr(old), 'f_max_GHz': old.f_max, 'v_max_V': old.v_max}
    print('\nDeviceVFModel (the recorded F1c source): ceiling %.3f GHz at %.3f V, re-anchored per T' % (old.f_max, old.v_max))

    # -- sensitivities at the array's 92 C target and at 60 C ---------------------------------
    sens = {}
    base_92 = ceiling_row(m, 365.15, args.dT_K)
    for name, kw in (('tddb_n_30', {'tddb_n': 30.0}), ('tddb_n_50', {'tddb_n': 50.0}),
                     ('tddb_Ea_0.4', {'tddb_Ea_eV': 0.4}), ('tddb_Ea_0.8', {'tddb_Ea_eV': 0.8}),
                     ('em_only', {'mechanisms': ('em',)}), ('tddb_only', {'mechanisms': ('tddb',)}),
                     ('wire_0.15', {'wire_fraction': 0.15}), ('wire_0.45', {'wire_fraction': 0.45}),
                     ('overhead_0.04', {'overhead_fraction': 0.04}), ('overhead_0.12', {'overhead_fraction': 0.12}),
                     ('logic_depth_10', {'logic_depth': 10.0}), ('logic_depth_8', {'logic_depth': 8.0}),
                     ('D_ins_300', {'D_ins_ps': 300.0})):
        mm = load_fmax_model(**kw)
        sens[name] = {'params': {k: (list(v) if isinstance(v, tuple) else v) for k, v in kw.items()},
                      'at_92C': ceiling_row(mm, 365.15, args.dT_K), 'at_60C': ceiling_row(mm, 333.15, args.dT_K),
                      'at_100C': ceiling_row(mm, 373.15, args.dT_K)}
    out['tables']['sensitivity'] = sens
    print('\nsensitivity (f_max GHz / V_ceiling / limiter) at 100 C | 92 C | 60 C:')
    print('  %-16s %s' % ('default', ' | '.join('%.3f / %.3f / %s' % (r['f_max_GHz'], r['v_ceiling_V'], r['limiter'])
                                                for r in (ceiling_row(m, 373.15, args.dT_K), base_92, ceiling_row(m, 333.15, args.dT_K)))))
    for k, v in sens.items():
        print('  %-16s %s' % (k, ' | '.join('%.3f / %.3f / %s' % (r['f_max_GHz'], r['v_ceiling_V'], r['limiter'])
                                            for r in (v['at_100C'], v['at_92C'], v['at_60C']))))

    # -- what a die held at T buys over the 100 C qualification corner, same pipeline ----------
    q = ceiling_row(m, 373.15, args.dT_K)
    gains = {}
    for T in (92.0, 78.6, 60.0, 27.0):
        r = ceiling_row(m, T + 273.15, args.dT_K)
        # decompose: supply (V_max) vs temperature (I_on, wire, skew) at fixed supply
        f_vT = m.frequency(r['v_ceiling_V'], T + 273.15, args.dT_K)
        f_vTq = m.frequency(r['v_ceiling_V'], 373.15, args.dT_K)      # same supply, hot die
        f_vqT = m.frequency(q['v_ceiling_V'], T + 273.15, args.dT_K)  # hot corner's supply, cool die
        gains['%.1fC' % T] = {'f_max_GHz': r['f_max_GHz'], 'gain_vs_100C': r['f_max_GHz'] / q['f_max_GHz'] - 1.0,
                              'v_ceiling_V': r['v_ceiling_V'], 'v_gain': r['v_ceiling_V'] / q['v_ceiling_V'] - 1.0,
                              'gain_from_supply_at_T': f_vT / f_vqT - 1.0,
                              'gain_from_temperature_at_hot_supply': f_vqT / q['f_max_GHz'] - 1.0,
                              'limiter': r['limiter']}
    out['tables']['gain_vs_qualification_corner'] = gains
    print('\ngain over the 100 C corner (%.3f GHz at %.3f V), same 20-FO4 pipeline:' % (q['f_max_GHz'], q['v_ceiling_V']))
    for k, g in gains.items():
        print('  %-7s f_max %.3f GHz (%+.1f %%)  V %.3f (%+.1f %%)  supply term %+.1f %%  temperature term %+.1f %%  [%s]' % (
            k, g['f_max_GHz'], 100 * g['gain_vs_100C'], g['v_ceiling_V'], 100 * g['v_gain'],
            100 * g['gain_from_supply_at_T'], 100 * g['gain_from_temperature_at_hot_supply'], g['limiter']))

    # -- scorecard for §P0.31 P1-P3 (model arithmetic) -----------------------------------------
    tq = out['tables']['ceiling_vs_T_qual']
    by_T = {round(r['T_C'], 1): r for r in tq}
    v92, v60, v27 = (by_T[t]['v_max_reliability_V'] for t in (92.0, 60.0, 27.0))
    em_binds = [r['T_C'] for r in tq if r['reliability_binding'] == 'em']
    sc = {
        'P1_vmax_ladder': {'measured': {'92C': v92 / 0.77 - 1, '60C': v60 / 0.77 - 1, '27C': v27 / 0.77 - 1,
                                        'em_binds_at_C': em_binds},
                           'verdict': ('confirmed' if (0.005 <= v92 / 0.77 - 1 <= 0.02 and 0.03 <= v60 / 0.77 - 1 <= 0.06
                                                       and 0.10 <= v27 / 0.77 - 1 <= 0.16 and not em_binds)
                                       else 'NOT as predicted')},
        'P3_device_peak_inside_sweep': {'measured': {k: v['peak'] for k, v in fv.items()},
                                        'crossover_reliability_vs_device_C': [r['T_C'] for r in tq if r['limiter'] == 'device'],
                                        'verdict': ('confirmed' if (not fv['330K']['peak']['at_sweep_end'] and 0.85 <= fv['330K']['peak']['V_V'] <= 0.95)
                                                    else 'NOT as predicted')},
    }
    g60 = gains['60.0C']
    sc['P2_60C_vs_92C_same_pipeline'] = {'measured': (by_T[60.0]['f_max_GHz'] / by_T[92.0]['f_max_GHz'] - 1.0),
                                         'verdict': ('confirmed' if 0.08 <= by_T[60.0]['f_max_GHz'] / by_T[92.0]['f_max_GHz'] - 1.0 <= 0.12
                                                     else ('FALSIFIED' if not (0.05 <= by_T[60.0]['f_max_GHz'] / by_T[92.0]['f_max_GHz'] - 1.0 <= 0.15) else 'NOT as predicted'))}
    out['scorecard_model_arithmetic'] = sc
    print('\nscorecard (§P0.31 P1-P3, model arithmetic):')
    for k, v in sc.items():
        print('  %-32s %s   %s' % (k, v['verdict'], json.dumps(v['measured'])[:160]))
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('\nwritten: %s' % os.path.relpath(args.json_out, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
