#!/usr/bin/env python
"""Threshold voltage, subthreshold swing and drive current vs temperature and supply, SIMULATED
from the ASAP7 card -- the two things §P0.13's toolchain did not yet give the project.

    python examples/device_vt_vf_spice.py     # needs spice_toolchain/, see docs/BSIMCMG_TOOLCHAIN.md

What this settles
-----------------
Until now the toolchain produced ONE curve, off-state leakage vs temperature, and the rest of the
device layer came from elsewhere: ``V_t`` was an analytic parameter and the V/F curve was the
IRDS 2024 roadmap table with a textbook ``alpha = 1.4`` (``docs/METHODS.md`` §3). This runs two
more decks on the same card in the same simulator:

* ``spice_sim.vt_deck`` -- the gate sweep at a linear and at a saturated drain bias, at every
  temperature. From it: ``V_t,lin(T)``, ``V_t,sat(T)`` by the constant-current criterion, the
  subthreshold swing ``SS(T)`` fitted inside a current window, DIBL, and ``I_off(T)`` at
  ``V_gs = 0`` -- which must reproduce the leakage evidence file's own curve (it is the same
  device in a different deck, so agreement is a check on both).
* ``spice_sim.idsat_deck`` -- the diagonal ``V_gs = V_ds = V`` at every temperature. From it:
  ``I_on(V, T)``, the alpha-power exponent as a FIT rather than an assumption, and the V/F shape
  ``f(V) ~ I_on(V) / V`` that ``power/device_vf.DeviceVFModel`` reads.

And the threshold-voltage lever of ``docs/LADDER_GEN0.md`` §2 is re-derived on the device: clock
gained per mV of ``V_t`` from the simulated curve, leakage cost from the simulated swing at the
operating temperature (not the roadmap's one room-temperature figure), and the kelvin of cooling
that pays for it from the simulated leakage curve's local slope.

`[!]` What is still assumed
---------------------------
* **The threshold criterion is a convention** -- 100 nA x W_eff / L_drawn per fin -- and a
  threshold is only comparable to another extracted the same way. IRDS quotes ``V_t,sat`` on its
  own definition; the comparison below is of *temperature coefficients and shape*, not levels.
* **One device, one length, no self-heating, no p-side, no wire load.** What transfers is the
  shape of ``I_on(V)/V`` and the temperature coefficients, not the amps.
* **The V/F anchor is the trace's own clock**: 3.8 GHz at the card's 0.70 V. ``clock_search``
  uses only ratios and is insensitive to it; ``f_max`` inherits it and says so.
* **ASAP7 is a predictive PDK.** The GIDL bracket is irrelevant here (the criterion currents are
  orders above GIDL), but the absolute threshold is a model choice, not a fabricated part's.
"""
import os
import sys
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power.spice_cards import parse_card, card_path
from HotGauge.power import spice_sim
from HotGauge.power.device_vf import DeviceVFModel, DEFAULT_F_ANCHOR_GHZ
from HotGauge.power.irds_vf import IRDSVFModel, IRDS_NODES, DEFAULT_ALPHA
from HotGauge.power.device_leakage import load_simulated_curve

_VA = os.path.join('spice_toolchain', 'src', 'VA-Models', 'code', 'bsimcmg', 'vacode110',
                   'bsimcmg.va')
_OSDI = os.path.join('spice_toolchain', 'osdi', 'bsimcmg_vacode110.osdi')


def _run(deck, workdir, name, osdi, tag, nfin, expect):
    out, path = spice_sim.run_deck(deck, workdir, osdi=osdi, name=name)
    rows = spice_sim.parse_iv(out, nfin=nfin, tag=tag)
    if len(rows) != expect:
        sys.stderr.write(out[-4000:])
        raise SystemExit('{}: simulator returned {} of {} points -- see {}'
                         .format(name, len(rows), expect, path))
    return rows, spice_sim.unknown_parameters(out)


def _lin_fit(x, y):
    a, b = np.polyfit(np.asarray(x, float), np.asarray(y, float), 1)
    return float(a), float(b)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--device', default='nmos_rvt')
    ap.add_argument('--vdd', type=float, default=0.7, help='ASAP7 nominal supply')
    ap.add_argument('--t-min-K', type=float, default=200.0)
    ap.add_argument('--t-max-K', type=float, default=500.0)
    ap.add_argument('--t-step-K', type=float, default=25.0)
    ap.add_argument('--vgs-step', type=float, default=0.025)
    ap.add_argument('--v-on-min', type=float, default=0.30)
    ap.add_argument('--v-on-max', type=float, default=0.85,
                    help='must reach vdd*(1+overdrive) + the largest Vt shift the lever asks for')
    ap.add_argument('--v-on-step', type=float, default=0.025)
    ap.add_argument('--nfin', type=int, default=spice_sim.DEFAULT_NFIN)
    ap.add_argument('--f-anchor-GHz', type=float, default=DEFAULT_F_ANCHOR_GHZ)
    ap.add_argument('--irds-year', type=int, default=2024)
    ap.add_argument('--workdir', default=os.path.join(_REPO, 'spice_toolchain', 'tmp', 'vtvf'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'device_vt_vf_asap7.json'))
    args = ap.parse_args()

    ng, _ = spice_sim.toolchain()
    dev = parse_card()[args.device]
    va, osdi = os.path.join(_REPO, _VA), os.path.join(_REPO, _OSDI)
    module = spice_sim.module_name_of(va)
    card = spice_sim.render_model_card(dev, 'dut', module)

    T_K = np.arange(args.t_min_K, args.t_max_K + 0.5 * args.t_step_K, args.t_step_K)
    for must in (300.0, 330.0, 400.0):
        if not np.any(np.isclose(T_K, must)):
            T_K = np.sort(np.append(T_K, must))
    T_C = T_K - 273.15
    n_vgs = int(round(args.vdd / args.vgs_step)) + 1
    V_on = np.arange(args.v_on_min, args.v_on_max + 0.5 * args.v_on_step, args.v_on_step)

    # --- 1. the gate sweep ----------------------------------------------------------------
    deck = spice_sim.vt_deck(card, 'dut', T_C, osdi, vdd=args.vdd, vgs_step=args.vgs_step,
                             nfin=args.nfin)
    vt_rows, unknown = _run(deck, args.workdir, 'vt', osdi, 'VT', args.nfin,
                            len(T_K) * 2 * n_vgs)
    i_th = spice_sim.threshold_current_A(dev, nfin=1)
    vds_lin = spice_sim.DEFAULT_VDS_LIN
    vt = []
    for t_c, t_k in zip(T_C, T_K):
        def sweep(vds):
            pts = sorted((r[2], r[3]) for r in vt_rows
                         if abs(r[0] - t_c) < 1e-6 and abs(r[1] - vds) < 1e-9)
            return np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
        v_l, i_l = sweep(vds_lin)
        v_s, i_s = sweep(args.vdd)
        vt.append({'T_K': float(t_k),
                   'vt_lin_V': spice_sim.constant_current_vt(v_l, i_l, i_th),
                   'vt_sat_V': spice_sim.constant_current_vt(v_s, i_s, i_th),
                   # two decades below the criterion: clear of GIDL at the bottom, clear of the
                   # threshold at the top, and sampled >= 4 times by a 25 mV step at 60 mV/dec
                   'ss_lin_mV_dec': spice_sim.subthreshold_swing_mV_per_dec(
                       v_l, i_l, i_th / 1000.0, i_th / 10.0),
                   'ss_sat_mV_dec': spice_sim.subthreshold_swing_mV_per_dec(
                       v_s, i_s, i_th / 1000.0, i_th / 10.0),
                   'i_off_A_per_fin': float(i_s[0]),
                   'i_lin_at_vdd_A_per_fin': float(i_l[-1])})
        vt[-1]['dibl_mV_per_V'] = spice_sim.dibl_mV_per_V(vt[-1]['vt_lin_V'], vt[-1]['vt_sat_V'],
                                                         vds_lin, args.vdd)
    anchor_i = int(np.argmin(np.abs(T_K - 330.0)))
    i_off_anchor = vt[anchor_i]['i_off_A_per_fin']
    for r in vt:
        r['i_off_rel_to_330K'] = r['i_off_A_per_fin'] / i_off_anchor

    # fits over the window McPAT itself can see plus the cold zone's near end
    fit_lo, fit_hi = 250.0, 400.0
    win = [r for r in vt if fit_lo <= r['T_K'] <= fit_hi and r['vt_lin_V'] is not None
           and r['vt_sat_V'] is not None]
    d_lin, _ = _lin_fit([r['T_K'] for r in win], [r['vt_lin_V'] for r in win])
    d_sat, _ = _lin_fit([r['T_K'] for r in win], [r['vt_sat_V'] for r in win])
    ss_win = [r for r in win if r['ss_lin_mV_dec'] is not None]
    d_ss, _ = _lin_fit([r['T_K'] for r in ss_win], [r['ss_lin_mV_dec'] for r in ss_win])
    fits = {'fit_range_K': [fit_lo, fit_hi],
            'dvt_dT_mV_per_K_lin': d_lin * 1000.0, 'dvt_dT_mV_per_K_sat': d_sat * 1000.0,
            'ss_dT_mV_per_dec_per_K': d_ss,
            # SS ~ n kT/q ln10: the ideality factor, temperature by temperature
            'ideality_n_by_T': {str(r['T_K']): r['ss_lin_mV_dec'] /
                                (2.302585093 * 8.617333262e-5 * r['T_K'] * 1000.0)
                                for r in ss_win}}

    # --- 2. the same device in the OTHER evidence file -----------------------------------
    leak = load_simulated_curve()
    cmp_rows = []
    for r in vt:
        if leak.T_K[0] <= r['T_K'] <= leak.T_K[-1]:
            ref = float(leak.total_rel(r['T_K']))
            cmp_rows.append({'T_K': r['T_K'], 'gate_sweep_rel': r['i_off_rel_to_330K'],
                             'leakage_evidence_rel': ref,
                             'pct': 100.0 * (r['i_off_rel_to_330K'] / ref - 1.0)})
    consistency = {'max_abs_pct': max(abs(c['pct']) for c in cmp_rows), 'rows': cmp_rows,
                   'note': ('I_off at V_gs = 0, V_ds = vdd from the gate sweep, relative to '
                            '330 K, against docs/evidence/device_leakage_spice_asap7.json. '
                            'Same card, same model, different deck and session.')}

    # --- 3. the diagonal ------------------------------------------------------------------
    deck = spice_sim.idsat_deck(card, 'dut', T_C, osdi, v_V=V_on, vdd=args.vdd, nfin=args.nfin)
    ion_rows, unknown2 = _run(deck, args.workdir, 'idsat', osdi, 'ION', args.nfin,
                              len(T_K) * len(V_on))
    W_um = spice_sim.effective_width_um(dev, nfin=1)
    by_T = []
    for t_c, t_k, r_vt in zip(T_C, T_K, vt):
        pts = sorted((r[2], r[3]) for r in ion_rows if abs(r[0] - t_c) < 1e-6)
        I = np.array([p[1] for p in pts])
        vt_sat = r_vt['vt_sat_V'] if r_vt['vt_sat_V'] is not None else 0.0
        alpha, k, rms = spice_sim.fit_alpha_power(V_on[V_on >= 0.45], I[V_on >= 0.45], vt_sat)
        i_vdd = float(np.interp(args.vdd, V_on, I))
        by_T.append({'T_K': float(t_k), 'I_on_A_per_fin': [float(x) for x in I],
                     'alpha_fit': alpha, 'alpha_fit_k': k, 'alpha_fit_rms_ln': rms,
                     'I_on_vdd_A_per_fin': i_vdd, 'I_on_vdd_uA_per_um': i_vdd * 1e6 / W_um})
    i300 = by_T[int(np.argmin(np.abs(T_K - 300.0)))]['I_on_vdd_A_per_fin']
    for r in by_T:
        r['I_on_vdd_rel_to_300K'] = r['I_on_vdd_A_per_fin'] / i300

    # --- 4. the V/F shape, against the roadmap's assumed one ------------------------------
    i300_idx = int(np.argmin(np.abs(T_K - 300.0)))
    r300 = by_T[i300_idx]
    vt300 = vt[i300_idx]
    dev_vf = DeviceVFModel(V_on, r300['I_on_A_per_fin'], vdd=args.vdd,
                           f_anchor_GHz=args.f_anchor_GHz, vt=vt300['vt_sat_V'],
                           ss_mV_dec=vt300['ss_lin_mV_dec'], T_K=300.0,
                           label='ASAP7 {}'.format(args.device))
    irds = IRDSVFModel(args.irds_year)
    V_cmp = [v for v in V_on if 0.45 <= v <= dev_vf.v_max + 1e-9]
    vf_shape = {'V': V_cmp,
                'device_f_rel_to_vdd': [dev_vf.frequency(v) / dev_vf.frequency(args.vdd)
                                        for v in V_cmp],
                'irds_f_rel_to_vdd': [irds.frequency(v) / irds.frequency(irds.vdd)
                                      for v in V_cmp],
                'note': ('both normalised to their own f(vdd); IRDS {} and ASAP7 share vdd = '
                         '0.70 V so the abscissa is common. IRDS shape is the alpha-power law '
                         'with alpha = {}; the device shape is I_on(V)/V simulated.'
                         .format(args.irds_year, DEFAULT_ALPHA))}
    max_shape_pct = max(abs(d / i - 1.0) * 100.0 for d, i in
                        zip(vf_shape['device_f_rel_to_vdd'], vf_shape['irds_f_rel_to_vdd']))

    # --- 5. the V_t lever, re-derived on the device ---------------------------------------
    lever = []
    for t_k in (300.0, 350.0, 400.0):
        j = int(np.argmin(np.abs(T_K - t_k)))
        # local doubling temperature of the SIMULATED leakage curve at this T
        dT = 1.0
        slope = (np.log(float(leak.total_rel(t_k + dT))) -
                 np.log(float(leak.total_rel(t_k - dT)))) / (2 * dT)
        doubling_K = float(np.log(2.0) / slope) if slope > 0 else float('inf')
        for shift in (25.0, 50.0, 75.0):
            m = DeviceVFModel(V_on, by_T[j]['I_on_A_per_fin'], vdd=args.vdd,
                              f_anchor_GHz=args.f_anchor_GHz, vt=vt[j]['vt_sat_V'],
                              ss_mV_dec=vt[j]['ss_lin_mV_dec'], T_K=float(T_K[j]),
                              vt_shift_mV=shift, label='ASAP7 {}'.format(args.device))
            irds_m = IRDSVFModel(args.irds_year, vt_shift_mV=shift)
            lever.append({'T_K': float(T_K[j]), 'dvt_mV': shift,
                          'clock_gain_pct_device': 100.0 * m.clock_gain(),
                          'clock_gain_pct_irds': 100.0 * irds_m.clock_gain(),
                          'leakage_mult_device_ss': m.leakage_multiplier,
                          'leakage_mult_irds_ss': irds_m.leakage_multiplier,
                          'ss_device_mV_dec': m.ss_mV_dec, 'ss_irds_mV_dec': irds_m.ss_mV_dec,
                          'local_doubling_K': doubling_K,
                          'cooling_K_to_offset_device': m.cooling_K_to_offset(doubling_K),
                          'cooling_K_to_offset_irds': irds_m.cooling_K_to_offset(doubling_K)})

    out = {
        'note': __doc__.strip(),
        'toolchain': {'ngspice': os.path.relpath(ng, _REPO), 'osdi': _OSDI, 'verilog_a': _VA,
                      'module': module, 'model_version': '110.0.0'},
        'card': {'path': os.path.relpath(card_path(), _REPO), 'device': args.device,
                 'unknown_parameters': sorted(set(unknown) | set(unknown2))},
        'criteria': {'vdd_V': args.vdd, 'vds_lin_V': vds_lin, 'nfin_numerical': args.nfin,
                     'i_ref_A_per_square': spice_sim.DEFAULT_I_REF_A_PER_SQUARE,
                     'i_th_A_per_fin': i_th, 'W_eff_um': W_um, 'L_drawn_um': dev['l'] * 1e6,
                     'ss_window_A_per_fin': [i_th / 1000.0, i_th / 10.0],
                     'alpha_fit_from_V': 0.45, 'vt_fit_range_K': [fit_lo, fit_hi]},
        'vt': vt, 'fits': fits,
        'consistency_with_leakage_evidence': consistency,
        'idsat': {'V': [float(v) for v in V_on], 'by_T': by_T},
        'vf_300K': vf_shape,
        'vs_irds': {'year': args.irds_year, 'irds': IRDS_NODES[args.irds_year],
                    'device_vt_sat_300K_V': vt300['vt_sat_V'],
                    'device_ss_300K_mV_dec': vt300['ss_lin_mV_dec'],
                    'device_alpha_fit_300K': r300['alpha_fit'], 'irds_alpha_assumed': DEFAULT_ALPHA,
                    'vf_shape_max_abs_pct': max_shape_pct,
                    'device_f_max_GHz': dev_vf.f_max, 'device_v_max_V': dev_vf.v_max,
                    'f_anchor_GHz': args.f_anchor_GHz},
        'vt_lever': lever,
        'FINDING_1_VT_AND_SS_ARE_SIMULATED_NOW': (
            'The gate sweep on the ASAP7 {} card gives V_t,lin = {:.3f} V and V_t,sat = {:.3f} V at '
            '300 K (constant-current, 100 nA x W/L), DIBL {:.0f} mV/V, subthreshold swing '
            '{:.1f} mV/dec. Between {:.0f} and {:.0f} K the threshold falls at {:.2f} mV/K (lin) / '
            '{:.2f} mV/K (sat) and the swing rises at {:.3f} mV/dec per K. None of these was '
            'available before: V_t was an analytic parameter and SS a single roadmap number.'
            .format(args.device, vt300['vt_lin_V'], vt300['vt_sat_V'], vt300['dibl_mV_per_V'],
                    vt300['ss_lin_mV_dec'], fit_lo, fit_hi, fits['dvt_dT_mV_per_K_lin'],
                    fits['dvt_dT_mV_per_K_sat'], fits['ss_dT_mV_per_dec_per_K'])),
        'FINDING_2_THE_TWO_EVIDENCE_FILES_AGREE': (
            'I_off(T) read off the gate sweep at V_gs = 0 reproduces the leakage evidence '
            'file\'s relative curve to {:.2f} % at worst across {}-{} K. Two decks, two sessions, '
            'one device.'.format(consistency['max_abs_pct'], cmp_rows[0]['T_K'],
                                 cmp_rows[-1]['T_K'])),
        'FINDING_3_THE_VF_SHAPE_IS_SIMULATED_AND_ALPHA_IS_MEASURED': (
            'On the diagonal V_gs = V_ds the alpha-power exponent fitted above threshold is '
            '{:.2f} at 300 K (rms {:.3f} in ln I) against the textbook 1.4 the IRDS model '
            'assumes; I_on falls to {:.3f} of its 300 K value at 400 K. Normalised to f(vdd), the '
            'simulated I_on(V)/V shape and the IRDS alpha-power shape differ by at most '
            '{:.1f} % over 0.45-{:.2f} V. With the trace\'s 3.8 GHz at 0.70 V as the anchor, '
            'the device curve puts the 10 % overdrive ceiling at {:.2f} GHz.'
            .format(r300['alpha_fit'], r300['alpha_fit_rms_ln'],
                    by_T[int(np.argmin(np.abs(T_K - 400.0)))]['I_on_vdd_rel_to_300K'],
                    max_shape_pct, dev_vf.v_max, dev_vf.f_max)),
        'FINDING_4_THE_VT_LEVER_ON_THE_DEVICE': (
            'A 50 mV V_t reduction at 300 K buys {:.1f} % clock on the simulated curve '
            '({:.1f} % on IRDS) and costs {:.2f}x leakage at the simulated {:.1f} mV/dec '
            '({:.2f}x at the roadmap\'s {:.0f}); at 400 K the same 50 mV costs {:.2f}x because '
            'the swing has risen to {:.1f} mV/dec, and the simulated leakage curve\'s local '
            'doubling temperature there is {:.1f} K, so {:.1f} K of cooling pays for it.'
            .format(*[x for r in lever if r['T_K'] == 300.0 and r['dvt_mV'] == 50.0
                      for x in (r['clock_gain_pct_device'], r['clock_gain_pct_irds'],
                                r['leakage_mult_device_ss'], r['ss_device_mV_dec'],
                                r['leakage_mult_irds_ss'], r['ss_irds_mV_dec'])],
                    *[x for r in lever if r['T_K'] == 400.0 and r['dvt_mV'] == 50.0
                      for x in (r['leakage_mult_device_ss'], r['ss_device_mV_dec'],
                                r['local_doubling_K'], r['cooling_K_to_offset_device'])])),
        'HONEST_LIMITS': (
            'One device ({}), one drawn length, no self-heating, no p-FET, no wire load, and a '
            'threshold CRITERION (100 nA x W/L) that is a convention -- compare temperature '
            'coefficients and shapes across sources, never levels. The absolute V/F anchor is '
            'the trace\'s clock at the card\'s nominal supply and is a statement about where the '
            'trace sits on the curve, not a measured ASAP7 clock.'.format(args.device)),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)

    print(__doc__.split('\n')[0])
    print('\nV_t / SS / DIBL / I_off by temperature (constant-current %.3g A per fin):' % i_th)
    print('   %6s %9s %9s %9s %9s %9s %11s' % ('T_K', 'Vt_lin', 'Vt_sat', 'SS_lin', 'SS_sat',
                                               'DIBL', 'Ioff_rel330'))
    for r in vt:
        print('   %6.0f %9.4f %9.4f %9.2f %9.2f %9.1f %11.4g' % (
            r['T_K'], r['vt_lin_V'] or float('nan'), r['vt_sat_V'] or float('nan'),
            r['ss_lin_mV_dec'] or float('nan'), r['ss_sat_mV_dec'] or float('nan'),
            r['dibl_mV_per_V'] or float('nan'), r['i_off_rel_to_330K']))
    print('\nfits %s' % json.dumps({k: v for k, v in fits.items() if k != 'ideality_n_by_T'}))
    print('I_off consistency with the leakage evidence: %.2f %% max' % consistency['max_abs_pct'])
    print('\nI_on(vdd) and alpha by temperature:')
    for r in by_T:
        print('   %6.0f  I_on %.4g A/fin (%.0f uA/um, %.3f of 300 K)  alpha %.3f (rms %.3f)' % (
            r['T_K'], r['I_on_vdd_A_per_fin'], r['I_on_vdd_uA_per_um'], r['I_on_vdd_rel_to_300K'],
            r['alpha_fit'], r['alpha_fit_rms_ln']))
    print('\n%s' % dev_vf)
    print('V/F shape vs IRDS alpha-power: max %.1f %% over 0.45-%.2f V' % (max_shape_pct,
                                                                           dev_vf.v_max))
    print('\nThe V_t lever on the device:')
    for r in lever:
        print('   %4.0f K  dVt %2.0f mV  clock +%.1f%% (irds +%.1f%%)  leak x%.2f @ %.1f mV/dec '
              '(irds x%.2f @ %.0f)  doubling %.1f K -> %.1f K of cooling' % (
                  r['T_K'], r['dvt_mV'], r['clock_gain_pct_device'], r['clock_gain_pct_irds'],
                  r['leakage_mult_device_ss'], r['ss_device_mV_dec'], r['leakage_mult_irds_ss'],
                  r['ss_irds_mV_dec'], r['local_doubling_K'], r['cooling_K_to_offset_device']))
    print('\nwritten: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
