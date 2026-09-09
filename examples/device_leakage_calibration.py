#!/usr/bin/env python
"""Where the leakage-vs-temperature curve comes from, and what a device card says instead.

    python examples/device_leakage_calibration.py

Two halves, and the first one changes how to read the second.

**1. The curve the whole project runs on is eleven hard-coded numbers.**
``leakage_calibration.json`` was built by running McPAT eleven times, changing nothing but the
temperature (verified: the 310 K and 400 K XML differ in exactly one line). The resulting chip
subthreshold power, normalised, is **bit-for-bit the CACTI array** ``I_off_n[0][*]`` for
"16nm DG HP" -- ratio 1.000 at all ten points. There is no device mix, no aggregation, no
structure-dependent behaviour: it is a pass-through of one table.

That table is written in ``McPAT/cacti/technology.cc`` as ``1.52e-7/1.5*1.2*1.07`` and friends --
32 nm-era numbers with three multiplicative fudges, reused unchanged for 32, 22 and 16 nm.

**2. And its shape is not a device.** Back out the local activation energy,
``Ea = -k d(ln I)/d(1/T)``. A single barrier gives one Ea, drifting smoothly by tens of percent.
This table gives **0.016 eV to 1.081 eV, a 69x spread, and not monotone**: 0.016 eV is below kT
itself, and 1.081 eV is nearly the full silicon bandgap. Those are different mechanisms, so the
table is an eyeballed interpolation rather than a characterisation.

**3. What a real card says.** ASAP7's BSIM-CMG 7 nm FinFET card (BSD-3, vendored under
``spice_leakage/``) supplies the temperature physics; :mod:`HotGauge.power.device_leakage` puts it
in the off-state limit. Two barrier forms are fitted -- one whose temperature *shape* is the
card's own bandgap, one with a free slope -- and they agree with each other to a few percent
everywhere, so the answer does not depend on that choice.

`[!]` What this is not: a SPICE run. No simulator here can evaluate BSIM-CMG (conda-forge
ngspice-41 is built without it and without OSDI; there is no Xyce package; OpenVAF ships no
binary). This is the card's parameters in the analytic off-state limit, and it is reported as
that. Settling it properly still wants a simulator.
"""
import os
import re
import sys
import json
import argparse

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.power.spice_cards import parse_card, card_path
from HotGauge.power.device_leakage import (barriers_from_card, fit_barrier, extrapolation_test,
                                           DeviceLeakageCurve, varshni_eg)

K_EV = 8.617333262e-5
#: The CACTI block the 7 nm runs resolve to -- "16nm DG HP", itself 32 nm numbers times fudges.
CACTI_FILE = os.path.join('McPAT', 'cacti', 'technology.cc')
CACTI_MARKER = 'for 16nm DG HP'


def cacti_ioff_table(repo=_REPO):
    """The ``I_off_n[0][0..100]`` block immediately preceding the 16nm DG HP marker."""
    path = os.path.join(repo, CACTI_FILE)
    lines = open(path).read().splitlines()
    end = next(i for i, l in enumerate(lines) if CACTI_MARKER in l)
    vals, exprs = {}, {}
    for l in lines[max(0, end - 12):end]:
        m = re.match(r'\s*I_off_n\[0\]\[(\d+)\]\s*=\s*([\d.eE+-]+)(?P<rest>[^;]*);', l)
        if m:
            idx = int(m.group(1))
            expr = m.group(2) + m.group('rest')
            vals[idx] = eval(expr, {'__builtins__': {}}, {})   # literal arithmetic only
            exprs[idx] = expr.strip()
    if len(vals) != 11:
        raise RuntimeError('expected 11 I_off entries before {!r}, found {}'
                           .format(CACTI_MARKER, len(vals)))
    T = np.array(sorted(vals), dtype=float) + 300.0
    I = np.array([vals[k] for k in sorted(vals)], dtype=float)
    return T, I, [exprs[k] for k in sorted(exprs)], path, end + 1


def local_activation_eV(T, I):
    return -np.diff(np.log(I)) / np.diff(1.0 / T) * K_EV


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--calibration', default=os.path.join(
        _REPO, 'leakage_calibration', 'leakage_calibration.json'))
    ap.add_argument('--device', default='nmos_rvt',
                    help='which flavour of the card to use (default nmos_rvt)')
    ap.add_argument('--anchor-K', type=float, default=330.0)
    ap.add_argument('--json-out', default=os.path.join(_EV, 'device_leakage_asap7.json'))
    args = ap.parse_args()

    cal = json.load(open(args.calibration))
    rows = cal['rows']
    T = np.array([r['T_K'] for r in rows], dtype=float)
    I_sub = np.array([r['subthreshold_W'] for r in rows], dtype=float)
    gate_W = float(rows[0]['gate_W'])
    Tr = args.anchor_K
    sub_ref = float(I_sub[T == Tr][0])
    I_rel = I_sub / sub_ref
    gate_fraction = gate_W / (gate_W + sub_ref)

    # --- 1. the pass-through ------------------------------------------------------------------
    Tc, Ic, exprs, cacti_path, cacti_line = cacti_ioff_table()
    c_ref = float(Ic[Tc == Tr][0])
    c_rel = Ic / c_ref
    common = [t for t in T if t in set(Tc)]
    ratios = [float((I_rel[T == t][0]) / (c_rel[Tc == t][0])) for t in common]
    passthrough = {
        'cacti_source': '{}:{}'.format(CACTI_FILE, cacti_line),
        'cacti_expressions': exprs,
        'n_common_points': len(common),
        'mcpat_over_cacti_ratio': ratios,
        'max_abs_deviation_from_1': float(np.max(np.abs(np.array(ratios) - 1.0))),
        'IS_A_PASSTHROUGH': bool(np.max(np.abs(np.array(ratios) - 1.0)) < 1e-4),
    }

    # --- 2. is that table a device? ------------------------------------------------------------
    Ea = local_activation_eV(Tc, Ic)
    physicality = {
        'local_activation_eV': [float(e) for e in Ea],
        'between_K': ['{:.0f}-{:.0f}'.format(Tc[i], Tc[i + 1]) for i in range(len(Ea))],
        'min_eV': float(Ea.min()), 'max_eV': float(Ea.max()),
        'spread': float(Ea.max() / Ea.min()),
        'monotone': bool(np.all(np.diff(Ea) >= 0) or np.all(np.diff(Ea) <= 0)),
        'kT_at_300K_eV': K_EV * 300.0,
        'silicon_bandgap_eV': float(varshni_eg(300.0, 1.17, 4.73e-4, 636.0)),
    }

    # --- 3. the card ---------------------------------------------------------------------------
    devices = parse_card()
    dev = devices[args.device]
    models = barriers_from_card(dev, Tr)
    fits, curves = {}, {}
    for name, m in models.items():
        p, rms = fit_barrier(m, T, I_rel)
        curves[name] = DeviceLeakageCurve(m, p, gate_fraction)
        fits[name] = {'params': dict(zip(m.labels, [float(v) for v in p])),
                      'rms_log10': rms, 'typical_factor_error': float(10 ** rms),
                      'extrapolation_test': extrapolation_test(m, T, I_rel, n_fit=7)}
    if 'n' in fits['varshni']['params']:
        fits['varshni']['n_hit_physical_floor'] = bool(
            abs(fits['varshni']['params']['n'] - 1.0) < 1e-6)

    # --- 4. what the two disagree about --------------------------------------------------------
    from HotGauge.thermal.leakage_feedback import load_calibrated_leakage_model
    lm, _ = load_calibrated_leakage_model(args.calibration, extrapolate=True)
    ref_scale = lm.scale(Tr)
    probe_T = [200., 220., 250., 280., 300., 310., 350., 400., 450., 500.]
    compare = []
    for t in probe_T:
        pipe = float(lm.scale(t) / ref_scale)
        card = float(curves['varshni'].total_rel(t))
        alt = float(curves['linear'].total_rel(t))
        compare.append({'T_K': t, 'pipeline_rel': pipe, 'card_rel': card,
                        'card_alt_form_rel': alt,
                        'model_spread_pct': 100.0 * abs(card - alt) / max(card, 1e-30),
                        'pipeline_over_card': pipe / card if card > 0 else None})
    knee = curves['varshni'].floor_temperature_K()

    out = {
        'note': __doc__.strip(),
        'card': {'path': os.path.relpath(card_path(), _REPO), 'device': args.device,
                 'devices_in_card': sorted(devices),
                 'bsim_cmg_version': dev.get('version'),
                 'source': 'ASAP7 PDK r1p7, The-OpenROAD-Project/asap7_pdk_r1p7, BSD-3-Clause',
                 'Eg_300K_eV': float(varshni_eg(300.0, dev['bg0sub'], dev['tbgasub'],
                                                dev['tbgbsub'])),
                 'ute': dev.get('ute'), 'kt1': dev.get('kt1')},
        'anchor_K': Tr, 'gate_fraction_at_anchor': gate_fraction,
        'passthrough': passthrough, 'table_physicality': physicality,
        'fits': fits, 'comparison': compare, 'gate_floor_knee_K': knee,

        'FINDING_1_THE_CURVE_IS_A_PASSTHROUGH': (
            'The project\'s leakage-vs-temperature curve is not a chip-level result. Normalised, '
            'it equals CACTI\'s hard-coded I_off_n[0][*] array for "16nm DG HP" to within {:.1e} '
            'at all {} points -- the eleven McPAT runs differ in one XML line and reproduce the '
            'table exactly. That table is written as 32 nm numbers times three fudge factors '
            '(1.52e-7/1.5*1.2*1.07 and so on) and is reused unchanged for 32, 22 and 16 nm.'
            .format(passthrough['max_abs_deviation_from_1'], passthrough['n_common_points'])),

        'FINDING_2_AND_IT_IS_NOT_A_DEVICE': (
            'Its implied local activation energy runs {:.3f} to {:.3f} eV -- a {:.0f}x spread, and '
            'not monotone. {:.3f} eV is below kT at room temperature ({:.3f} eV) and {:.3f} eV is '
            'nearly the silicon bandgap ({:.3f} eV): those are different mechanisms, so no single '
            'device produces this curve. It is an interpolation, and the project has been treating '
            'it as a measurement.'
            .format(physicality['min_eV'], physicality['max_eV'], physicality['spread'],
                    physicality['min_eV'], physicality['kT_at_300K_eV'],
                    physicality['max_eV'], physicality['silicon_bandgap_eV'])),

        'FINDING_3_THE_TWO_ENDS_MOVE_A_LOT': (
            'Against the card-parameterised off-state model: below the table the pipeline CLAMPS '
            '(leakage never falls), while the physics keeps falling to a gate-leakage floor at '
            'about {:.0f} K -- at 250 K the pipeline says {:.3f} and the card says {:.4f}, a '
            'factor of {:.0f}. Above the table the pipeline\'s Arrhenius tail is STEEPER than the '
            'physics: {:.0f}x vs {:.0f}x at 450 K and {:.0f}x vs {:.0f}x at 500 K. The two barrier '
            'forms agree with each other within a few percent throughout, so this is not an '
            'artefact of which one was chosen.'
            .format(knee or float('nan'),
                    [c for c in compare if c['T_K'] == 250][0]['pipeline_rel'],
                    [c for c in compare if c['T_K'] == 250][0]['card_rel'],
                    [c for c in compare if c['T_K'] == 250][0]['pipeline_over_card'],
                    [c for c in compare if c['T_K'] == 450][0]['pipeline_rel'],
                    [c for c in compare if c['T_K'] == 450][0]['card_rel'],
                    [c for c in compare if c['T_K'] == 500][0]['pipeline_rel'],
                    [c for c in compare if c['T_K'] == 500][0]['card_rel'])),

        'WHAT_IT_MEANS_FOR_P0_11': (
            'The flat-die ceiling of 1.0-1.2 W/mm^2 was solved with the pipeline curve, whose tail '
            'is ~6x steeper at 450 K than the card-based physics. A gentler tail runs away later, '
            'so that ceiling is CONSERVATIVE -- the direction matters and it should be requoted '
            'with an explicit "on the current leakage curve" qualifier until this is settled.'),

        'HONEST_LIMITS': (
            'This is not a SPICE simulation: no simulator available here evaluates BSIM-CMG '
            '(conda-forge ngspice-41 is built without it and without OSDI, there is no Xyce '
            'package, OpenVAF ships no binary). It is the card\'s own temperature parameters in '
            'the analytic off-state limit, with two free parameters fitted to the very table it '
            'is criticising -- so it inherits that table\'s level, and only its SHAPE is '
            'independent. It also omits GIDL, which the card enables and which would raise '
            'leakage at both ends. The two fitted parameters are also DEGENERATE over a 90 K '
            'window -- the curve is identifiable, the barrier height and its slope are not, so '
            'neither may be quoted as a device property. Neither curve is a measurement of a '
            'real 7 nm part.'),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)

    print(__doc__.split('\n')[0])
    print('\n1. PASS-THROUGH: mcpat/cacti ratio max deviation from 1 = %.2e over %d points -> %s'
          % (passthrough['max_abs_deviation_from_1'], passthrough['n_common_points'],
             'IS a pass-through' if passthrough['IS_A_PASSTHROUGH'] else 'is NOT'))
    print('   source: %s' % passthrough['cacti_source'])
    print('\n2. TABLE PHYSICALITY: Ea %.3f - %.3f eV (%.0fx spread), monotone=%s'
          % (physicality['min_eV'], physicality['max_eV'], physicality['spread'],
             physicality['monotone']))
    print('   kT(300K) = %.3f eV, Si bandgap = %.3f eV' % (physicality['kT_at_300K_eV'],
                                                           physicality['silicon_bandgap_eV']))
    print('\n3. CARD FITS (%s, BSIM-CMG %s):' % (args.device, dev.get('version')))
    for name, f_ in fits.items():
        print('   %-8s %-46s rms %.3f (%.2fx typical)'
              % (name, f_['params'], f_['rms_log10'], f_['typical_factor_error']))
    print('\n4. PIPELINE vs CARD (relative to %.0f K):' % Tr)
    print('   %6s %14s %14s %12s %10s' % ('T_K', 'pipeline', 'card', 'pipe/card', 'form spread'))
    for c in compare:
        print('   %6.0f %14.5g %14.5g %12s %9.1f%%'
              % (c['T_K'], c['pipeline_rel'], c['card_rel'],
                 '%.1fx' % c['pipeline_over_card'] if c['pipeline_over_card'] else '--',
                 c['model_spread_pct']))
    print('\n   gate-leakage floor knee: %.0f K -- below this, cooling buys almost nothing' % knee)
    print('\nwritten: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
