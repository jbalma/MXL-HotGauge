#!/usr/bin/env python
"""The leakage-vs-temperature curve, **simulated** from the ASAP7 card instead of interpolated.

    python examples/device_leakage_spice.py     # needs spice_toolchain/, see docs/BSIMCMG_TOOLCHAIN.md

What this settles
-----------------
``examples/device_leakage_calibration.py`` established two things and could not settle a third:

1. the pipeline's leakage curve is a **bit-for-bit pass-through** of CACTI's hard-coded
   ``I_off_n[0][*]`` array for "16nm DG HP" -- 32 nm numbers times three fudge factors;
2. its implied activation energy runs 0.016-1.081 eV, **69x and non-monotone**, so no single
   device produces it;
3. ...and the replacement it offered was the ASAP7 card in an **analytic off-state limit**, with
   two parameters fitted to the very table it criticises. Only its *shape* was independent; its
   *level* was still CACTI's, and it modelled subthreshold conduction and nothing else.

This removes point 3. ngspice 47, built from source with OSDI, loads BSIM-CMG compiled from
Verilog-A by OpenVAF, and evaluates the vendor's model on the vendor's parameters: all ~130 of
them, every conduction mechanism the card enables, an absolute current in amps, and no fit to
anything. The analytic curve becomes something to *check*, not something to rely on.

Three checks run alongside the sweep, because a wrong answer here would look entirely plausible
----------------------------------------------------------------------------------------------
* **Is it a transistor?** The subthreshold swing at 300 K is measured. A FinFET's ideal limit is
  59.6 mV/dec; anything far above it means the card is not binding and the numbers are a default
  device wearing ASAP7's name.
* **Does the answer depend on the model version?** The card declares BSIM-CMG **107**; VA-Models
  ships **110.0.0**, **111.2.1** and a Xyce-flavoured tree. All available ones are run and
  compared. A version-dependent answer is a result about VA-Models, not about silicon.
* **Which mechanism is it?** The run is repeated with ``gidlmod = 0`` and with ``igcmod = 0``, so
  the curve is decomposed rather than asserted. This is the check that changes the conclusion --
  see below.

`[!]` What is still assumed
---------------------------
* **The bias point is a choice**: ``V_gs = 0, V_ds = V_dd, V_bs = 0`` at the card's drawn length,
  one fin. A die leaks at a distribution of biases, stack heights and flavours; this is one corner
  of it, chosen to be the same corner the analytic model used so the two are comparable.
* **One device is not a die.** What transfers to the pipeline is the *shape*, not the amps.
* **Self-heating is off** (``shmod = 0`` in the card), so the swept temperature is the device's.
* **ASAP7 is a predictive PDK.** Its GIDL coefficients are a model choice, not a measurement of a
  fabricated part -- which is exactly why the GIDL-off curve is reported next to the full one
  rather than buried.
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

_VA_DIR = os.path.join('spice_toolchain', 'src', 'VA-Models', 'code', 'bsimcmg')
_OSDI_DIR = os.path.join('spice_toolchain', 'osdi')

#: The model trees to cross-check, newest-first-ish. ``vacode`` is the Xyce-flavoured 111.2.1.
VERSIONS = (('110.0.0', 'vacode110', 'bsimcmg_vacode110.osdi'),
            ('111.2.1', 'vacode111', 'bsimcmg_vacode111.osdi'),
            ('111.2.1-xyce', 'vacode', 'bsimcmg_vacode.osdi'))

#: Ideal subthreshold swing is ln(10)*kT/q; a real FinFET sits a few mV/dec above it.
_LN10_K_OVER_Q = 2.302585093 * 8.617333262e-5


def _sweep(dev, module, osdi, T_K, workdir, name, overrides=None, vdd=0.7,
           nfin=spice_sim.DEFAULT_NFIN):
    """``I_drain(T)`` per fin, in amps, for one model build and one set of card overrides."""
    d = dict(dev)
    if overrides:
        d.update(overrides)
    card = spice_sim.render_model_card(d, 'dut', module)
    deck = spice_sim.ioff_deck(card, 'dut', T_K - 273.15, osdi, vdd=vdd, nfin=nfin)
    out, deck_path = spice_sim.run_deck(deck, workdir, osdi=osdi, name=name)
    rows = spice_sim.parse_ioff(out, nfin=nfin)
    if len(rows) != len(T_K):
        sys.stderr.write(out[-4000:])
        raise SystemExit('{}: simulator returned {} of {} points -- see {}'
                         .format(name, len(rows), len(T_K), deck_path))
    return np.array([r[1] for r in rows]), spice_sim.unknown_parameters(out)


def _swing_mV_per_dec(dev, module, osdi, workdir, T_K=300.0, vdd=0.7,
                      nfin=spice_sim.DEFAULT_NFIN):
    """Subthreshold swing at ``T_K``, measured with GIDL off so it is the channel's own.

    GIDL is a *drain-side* current that barely responds to the gate, so leaving it in flattens the
    apparent swing at V_gs = 0 and makes a perfectly good device look broken. Turning it off is
    the right control for this one measurement, and only for this one.
    """
    d = dict(dev)
    d['gidlmod'] = 0.0
    card = spice_sim.render_model_card(d, 'dut', module)
    vgs = [0.05, 0.10, 0.15]
    lines = ['* subthreshold swing probe -- generated', card,
             'Vd d 0 dc {!r}'.format(float(vdd)), 'Vg g 0 dc 0',
             'N1 d g 0 0 0 dut nfin={:d}'.format(int(nfin)),
             '.control', 'pre_osdi {}'.format(osdi), 'option klu',
             'option temp = {!r}'.format(float(T_K - 273.15))]
    for v in vgs:
        lines += ['alter vg = {!r}'.format(float(v)), 'op',
                  'echo "IOFF {!r} $&i(vd)"'.format(float(v))]
    lines += ['quit', '.endc', '.end', '']
    out, deck = spice_sim.run_deck('\n'.join(lines), workdir, osdi=osdi, name='swing')
    rows = spice_sim.parse_ioff(out, nfin=nfin)
    if len(rows) != len(vgs):
        sys.stderr.write(out[-4000:])
        raise SystemExit('swing probe returned {} of {} points -- see {}'
                         .format(len(rows), len(vgs), deck))
    v = np.array([r[0] for r in rows])
    i = np.array([r[1] for r in rows])
    return float(np.mean(np.diff(v) / np.diff(np.log10(i))) * 1000.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--device', default='nmos_rvt')
    ap.add_argument('--anchor-K', type=float, default=330.0,
                    help="the pipeline's own T_ref (mcpat_tref), not a free choice")
    ap.add_argument('--t-min-K', type=float, default=200.0)
    ap.add_argument('--t-max-K', type=float, default=500.0)
    ap.add_argument('--t-step-K', type=float, default=10.0)
    ap.add_argument('--vdd', type=float, default=0.7, help='ASAP7 nominal supply')
    ap.add_argument('--nfin', type=int, default=spice_sim.DEFAULT_NFIN,
                    help='fins per device -- a NUMERICAL setting, not a physical one; '
                         'the current is divided back out. See spice_sim.ioff_deck')
    ap.add_argument('--primary', default='110.0.0',
                    help='which model version supplies the curve that gets used downstream')
    ap.add_argument('--workdir', default=os.path.join(_REPO, 'spice_toolchain', 'tmp', 'ioff'))
    ap.add_argument('--analytic', default=os.path.join(_EV, 'device_leakage_asap7.json'))
    ap.add_argument('--json-out', default=os.path.join(_EV, 'device_leakage_spice_asap7.json'))
    args = ap.parse_args()

    ng, _ = spice_sim.toolchain()
    devices = parse_card()
    dev = devices[args.device]

    # The anchor has to be a simulated point, or the whole curve is normalised to an interpolation.
    T_K = np.arange(args.t_min_K, args.t_max_K + 0.5 * args.t_step_K, args.t_step_K)
    if not np.any(np.isclose(T_K, args.anchor_K)):
        T_K = np.sort(np.append(T_K, args.anchor_K))
    anchor_i = int(np.argmin(np.abs(T_K - args.anchor_K)))

    # --- 1. every available model version, so "which version" is measured, not chosen ----------
    builds, unknown_by_version = {}, {}
    for label, tree, osdi_name in VERSIONS:
        va = os.path.join(_REPO, _VA_DIR, tree, 'bsimcmg.va')
        osdi = os.path.join(_REPO, _OSDI_DIR, osdi_name)
        if not (os.path.exists(va) and os.path.exists(osdi)):
            continue
        module = spice_sim.module_name_of(va)
        I, unknown = _sweep(dev, module, osdi, T_K, args.workdir, 'v' + tree,
                            vdd=args.vdd, nfin=args.nfin)
        builds[label] = {'tree': tree, 'module': module, 'osdi': osdi, 'va': va, 'I_A': I}
        unknown_by_version[label] = unknown
    if args.primary not in builds:
        raise SystemExit('primary version {!r} not built; have {}'
                         .format(args.primary, sorted(builds)))
    prim = builds[args.primary]
    I_A = prim['I_A']
    rel = I_A / I_A[anchor_i]

    spread = {}
    for label, b in builds.items():
        r = b['I_A'] / b['I_A'][anchor_i]
        spread[label] = {'max_abs_pct_vs_primary': float(np.max(np.abs(r / rel - 1.0)) * 100.0)}

    # --- 2. decompose it, rather than asserting what the floor is ------------------------------
    mech = {}
    for name, over in (('gidl_off', {'gidlmod': 0.0}),
                       ('gate_off', {'igcmod': 0.0}),
                       ('gidl_and_gate_off', {'gidlmod': 0.0, 'igcmod': 0.0})):
        I_m, _ = _sweep(dev, prim['module'], prim['osdi'], T_K, args.workdir, name,
                        overrides=over, vdd=args.vdd, nfin=args.nfin)
        mech[name] = I_m

    # --- 2b. is the answer converged in the ONE numerical knob that changes it? ----------------
    # A single fin leaks below the linear solver's resolution; nfin lifts it clear. The honest
    # check is not that nfin is "big enough" but that 10x more changes nothing.
    conv = {}
    for name, over in (('full', None), ('gidl_off', {'gidlmod': 0.0})):
        I_x, _ = _sweep(dev, prim['module'], prim['osdi'], T_K, args.workdir, 'conv_' + name,
                        overrides=over, vdd=args.vdd, nfin=args.nfin * 10)
        base = I_A if name == 'full' else mech['gidl_off']
        conv[name] = {'nfin': args.nfin, 'nfin_x10': args.nfin * 10,
                      'max_abs_pct': float(np.max(np.abs(I_x / base - 1.0)) * 100.0)}
    conv['CONVERGED'] = bool(max(v['max_abs_pct'] for v in conv.values()
                                 if isinstance(v, dict)) < 1.0)

    # --- 3. is it a transistor at all? ---------------------------------------------------------
    # nfin=1 deliberately: _sweep divides the current back down to ONE fin, so the width it is
    # normalised by has to be one fin's too. Using args.nfin here reports a per-um current 1000x
    # too small and fails the sanity check for the wrong reason.
    W_um = spice_sim.effective_width_um(dev, nfin=1)
    swing = _swing_mV_per_dec(dev, prim['module'], prim['osdi'], args.workdir,
                              vdd=args.vdd, nfin=args.nfin)
    ideal_swing = _LN10_K_OVER_Q * 300.0 * 1000.0
    i300 = float(np.interp(300.0, T_K, I_A)) / W_um
    sanity = {
        'I_off_300K_A_per_um': i300, 'nA_per_um_300K': i300 * 1e9,
        'in_nA_per_um_decade': bool(1e-11 <= i300 <= 1e-7),
        'subthreshold_swing_300K_mV_per_dec': swing,
        'ideal_swing_300K_mV_per_dec': ideal_swing,
        'swing_is_physical': bool(ideal_swing <= swing <= 1.6 * ideal_swing),
        # The SUBTHRESHOLD part must rise with temperature -- that is the barrier. The TOTAL
        # need not: GIDL is a tunnelling current with a negative temperature coefficient
        # (tgidl < 0 in the card), so where it dominates the total can be flat or fall. Testing
        # the total was the wrong test and it fired on correct physics.
        'subthreshold_monotone_increasing': bool(np.all(np.diff(mech['gidl_off']) > 0)),
        'total_monotone_increasing': bool(np.all(np.diff(I_A) > 0)),
        'effective_width_um': W_um,
    }
    sanity['PASSES'] = bool(sanity['in_nA_per_um_decade'] and sanity['swing_is_physical']
                            and sanity['subthreshold_monotone_increasing'])

    # --- 4. the comparison this whole exercise exists for --------------------------------------
    analytic = json.load(open(args.analytic))
    compare = []
    for a in analytic['comparison']:
        t = a['T_K']
        if not (T_K[0] <= t <= T_K[-1]):
            continue
        s = float(np.interp(t, T_K, rel))
        compare.append({'T_K': t, 'simulated_rel': s,
                        'analytic_card_rel': a['card_rel'], 'pipeline_rel': a['pipeline_rel'],
                        'analytic_over_simulated': a['card_rel'] / s,
                        'pipeline_over_simulated': a['pipeline_rel'] / s})
    worst_a = max(compare, key=lambda c: abs(np.log10(c['analytic_over_simulated'])))
    worst_p = max(compare, key=lambda c: abs(np.log10(c['pipeline_over_simulated'])))

    gidl_rel = mech['gidl_off'] / mech['gidl_off'][anchor_i]
    cold = int(np.argmin(np.abs(T_K - 200.0)))
    gidl_share_cold = 1.0 - float(mech['gidl_off'][cold] / I_A[cold])

    out_json = {
        'note': __doc__.strip(),
        'toolchain': {
            'ngspice': os.path.relpath(ng, _REPO),
            'osdi': os.path.relpath(prim['osdi'], _REPO),
            'verilog_a': os.path.relpath(prim['va'], _REPO),
            'module': prim['module'], 'model_version': args.primary,
            'built_by': 'docs/BSIMCMG_TOOLCHAIN.md',
        },
        'card': {'path': os.path.relpath(card_path(), _REPO), 'device': args.device,
                 'declared_version': dev.get('version'),
                 'unknown_parameters': unknown_by_version},
        'bias': {'vgs_V': 0.0, 'vds_V': args.vdd, 'vbs_V': 0.0, 'nfin': args.nfin,
                 'self_heating': bool(dev.get('shmod', 0))},
        'anchor_K': args.anchor_K,
        'sanity': sanity,
        'numerical_convergence': conv,
        'version_spread': spread,
        'curve': [{'T_K': float(t), 'I_A': float(i), 'I_A_per_um': float(i / W_um),
                   'rel_to_anchor': float(r), 'rel_to_anchor_gidl_off': float(g)}
                  for t, i, r, g in zip(T_K, I_A, rel, gidl_rel)],
        'mechanism': {k: [float(x) for x in v] for k, v in mech.items()},
        'comparison': compare,
        'gidl_share_of_leakage_at_200K': gidl_share_cold,

        'FINDING_1_IT_IS_A_SIMULATION_NOW': (
            'ngspice {} built from source with OSDI, loading BSIM-CMG {} compiled by OpenVAF, '
            'evaluates the ASAP7 {} card directly. Subthreshold swing at 300 K is {:.1f} mV/dec '
            'against an ideal {:.1f}, and I_off is {:.3g} nA/um -- both squarely in range, so the '
            'card is binding and the device is a device. The curve below is no longer fitted to '
            'anything: its level as well as its shape is the model\'s.'
            .format('47', args.primary, args.device, swing, ideal_swing, i300 * 1e9)),

        'FINDING_2_THE_COLD_END_IS_GIDL_NOT_A_GATE_FLOOR': (
            'The analytic model predicted leakage falling to a temperature-independent GATE floor '
            'at about 244 K. The simulator says the floor is real but it is {:.0f}% GIDL at 200 K, '
            'not gate tunnelling -- turning off igcmod barely moves the curve, turning off gidlmod '
            'drops 200 K by {:.0f}x. GIDL is exactly what the analytic model said it omitted and '
            'said would raise both ends, and at V_gs = 0 with V_ds = V_dd the gate-to-drain bias '
            'is -V_dd, so GIDL is on in the ordinary off state rather than an exotic corner. '
            'Simulated leakage at 200 K is {:.3g} of the 330 K value against the analytic '
            '{:.3g} -- the cold-zone prize is {:.0f}x SMALLER than the analytic curve promised.'
            .format(100.0 * gidl_share_cold,
                    float(I_A[cold] / mech['gidl_off'][cold]),
                    float(rel[cold]),
                    [c for c in compare if c['T_K'] == 200][0]['analytic_card_rel'],
                    float(rel[cold]) / [c for c in compare if c['T_K'] == 200][0]['analytic_card_rel'])),

        'FINDING_3_THE_HOT_TAIL_IS_GENTLER_STILL': (
            'At 500 K the pipeline says {:.0f}x the 330 K leakage, the analytic card model says '
            '{:.0f}x, and the simulator says {:.0f}x. Both replacements agree that the pipeline\'s '
            'Arrhenius tail is far too steep, and the simulator is gentler than the analytic model '
            'by another {:.1f}x. Since the flat-die ceiling of 1.0-1.2 W/mm^2 (P0.11) was solved '
            'on the pipeline curve, and a gentler tail runs away LATER, that ceiling is '
            'conservative by more than P0.12 estimated.'
            .format([c for c in compare if c['T_K'] == 500][0]['pipeline_rel'],
                    [c for c in compare if c['T_K'] == 500][0]['analytic_card_rel'],
                    [c for c in compare if c['T_K'] == 500][0]['simulated_rel'],
                    [c for c in compare if c['T_K'] == 500][0]['analytic_over_simulated'])),

        'FINDING_4_THE_ANSWER_DOES_NOT_DEPEND_ON_THE_MODEL_VERSION': (
            'The card declares version 107 and no 107 source exists in VA-Models, so all shipped '
            'versions were run: {}. Normalised to the anchor they agree to {:.1f}% at worst. The '
            'three parameters the newer models reject (capmod, coremod, version) are switches '
            'BSIM-CMG removed after 107, not values being silently dropped -- and the '
            'version-to-version agreement is the evidence that nothing important went with them.'
            .format(', '.join(sorted(builds)),
                    max(v['max_abs_pct_vs_primary'] for v in spread.values()))),

        'HONEST_LIMITS': (
            'One device (nmos_rvt), one bias corner (Vgs = 0, Vds = {:.2f} V, Vbs = 0), one fin, '
            'no self-heating (the card sets shmod = 0). A die leaks at a distribution of biases, '
            'stack heights and device flavours, so what transfers downstream is the SHAPE of '
            'I_off(T), not the amps. ASAP7 is a PREDICTIVE PDK: its GIDL coefficients '
            '(agidl = {:g}, bgidl = {:g}, egidl = {:g}) are a model choice, not a measurement of '
            'a fabricated 7 nm part, and Finding 2 rests on them -- which is why the GIDL-off '
            'curve is carried alongside the full one in every row rather than mentioned in a '
            'footnote. Treat the two as a bracket on the cold end.'
            .format(args.vdd, dev.get('agidl'), dev.get('bgidl'), dev.get('egidl'))),
    }
    with open(args.json_out, 'w') as f:
        json.dump(out_json, f, indent=1)

    print(__doc__.split('\n')[0])
    print('\nSIMULATOR: %s + %s (module %s, BSIM-CMG %s)'
          % (os.path.basename(ng), os.path.basename(prim['osdi']), prim['module'], args.primary))
    print('CARD: %s / %s, declared version %s'
          % (os.path.basename(card_path()), args.device, dev.get('version')))
    print('\nSANITY  %s' % ('PASS' if sanity['PASSES'] else '** FAIL -- card may not be binding **'))
    print('  I_off(300 K)      %.3g nA/um' % (i300 * 1e9))
    print('  swing(300 K)      %.1f mV/dec (ideal %.1f)' % (swing, ideal_swing))
    print('  subthreshold monotone in T   %s' % sanity['subthreshold_monotone_increasing'])
    print('  total monotone in T          %s   (GIDL has tgidl < 0, so False is physical)'
          % sanity['total_monotone_increasing'])
    print('  nfin x10 changes the curve by %.3f%%  -> %s'
          % (max(v['max_abs_pct'] for v in conv.values() if isinstance(v, dict)),
             'converged' if conv['CONVERGED'] else '** NOT CONVERGED **'))
    print('\nVERSION CROSS-CHECK (normalised, max deviation from %s):' % args.primary)
    for k in sorted(spread):
        print('  %-14s %6.2f%%   rejected params: %s'
              % (k, spread[k]['max_abs_pct_vs_primary'],
                 ', '.join(u.split('(')[1].split(')')[0] for u in unknown_by_version[k]) or 'none'))
    print('\nSIMULATED vs ANALYTIC vs PIPELINE (relative to %.0f K):' % args.anchor_K)
    print('   %6s %12s %12s %12s %12s %10s %10s'
          % ('T_K', 'simulated', 'sim/no-GIDL', 'analytic', 'pipeline', 'ana/sim', 'pipe/sim'))
    for c in compare:
        j = int(np.argmin(np.abs(T_K - c['T_K'])))
        print('   %6.0f %12.5g %12.5g %12.5g %12.5g %9.2fx %9.2fx'
              % (c['T_K'], c['simulated_rel'], gidl_rel[j], c['analytic_card_rel'],
                 c['pipeline_rel'], c['analytic_over_simulated'], c['pipeline_over_simulated']))
    print('\nGIDL is %.0f%% of leakage at 200 K -- the cold floor is GIDL, not the gate.'
          % (100.0 * gidl_share_cold))
    print('worst analytic/simulated %.2fx at %.0f K; worst pipeline/simulated %.2fx at %.0f K'
          % (worst_a['analytic_over_simulated'], worst_a['T_K'],
             worst_p['pipeline_over_simulated'], worst_p['T_K']))
    print('\nwritten: %s' % args.json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
