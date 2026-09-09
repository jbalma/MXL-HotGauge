"""Tests for the V_t(T) / I_dsat(V, T) decks, their extractors, and the device-derived V/F curve.

Same split as ``test_spice_sim.py``: the deck and extraction tests are pure and always run; the
evidence tests need the recorded sweep; the simulator test needs ``spice_toolchain/``.

Each pure test encodes a way the answer could be plausibly wrong: a threshold read off the
wrong drain bias, a swing fitted across a window that walked out of subthreshold, an exponent
fitted without the threshold subtracted, a curve anchored on the shifted device so the lever
buys nothing, a shifted curve read past the end of the sweep.
"""
import os
import math

import numpy as np
import pytest

from HotGauge.power import spice_sim
from HotGauge.power.spice_cards import parse_card, card_path
from HotGauge.power.device_vf import DeviceVFModel, load_device_vf, DEVICE_VF_EVIDENCE, repo_root

_needs_card = pytest.mark.skipif(not os.path.exists(card_path()), reason='vendored card absent')
_needs_toolchain = pytest.mark.skipif(not spice_sim.have_toolchain(),
                                      reason='spice_toolchain/ not built')
_EV = os.path.join(repo_root(), DEVICE_VF_EVIDENCE)
_needs_evidence = pytest.mark.skipif(not os.path.exists(_EV),
                                     reason='device V_t / V/F evidence not generated')


# ---------------------------------------------------------------------------
# decks
# ---------------------------------------------------------------------------
def test_vt_deck_sweeps_the_gate_at_two_drain_biases():
    deck = spice_sim.vt_deck('.model dut bsimcmg', 'dut', [26.85, 126.85], '/tmp/x.osdi',
                             vdd=0.7, vgs_step=0.1)
    # 8 gate points x 2 drain biases x 2 temperatures
    assert deck.count('\nop\n') == 8 * 2 * 2
    assert deck.count('alter vd = 0.05') == 2 and deck.count('alter vd = 0.7') == 2
    lines = [l.strip() for l in deck.splitlines()]
    assert lines[lines.index('.control') + 1].startswith('pre_osdi ')
    assert 'echo "VT ' in deck


def test_idsat_deck_walks_the_diagonal():
    deck = spice_sim.idsat_deck('.model dut bsimcmg', 'dut', [26.85], '/tmp/x.osdi',
                                v_V=[0.5, 0.6, 0.7])
    assert deck.count('\nop\n') == 3
    for v in ('0.5', '0.6', '0.7'):
        assert 'alter vd = {}'.format(v) in deck and 'alter vg = {}'.format(v) in deck
    assert 'echo "ION ' in deck


def test_decks_never_write_numpy_repr():
    deck = spice_sim.idsat_deck('.model dut bsimcmg', 'dut', np.array([26.85]), '/tmp/x.osdi',
                                v_V=np.array([0.5, 0.7]))
    assert 'np.float64' not in deck


def test_parse_iv_reads_its_tag_only_and_divides_by_nfin():
    out = ('VT 26.85 0.05 0.1 -2.2237E-07\nION 26.85 0.7 0.7 -3.5E-02\nVT 26.85 0.05 0.2 -9.7E-06\n')
    vt = spice_sim.parse_iv(out, nfin=1000, tag='VT')
    assert vt == [(26.85, 0.05, 0.1, pytest.approx(2.2237e-10)),
                  (26.85, 0.05, 0.2, pytest.approx(9.7e-9))]
    ion = spice_sim.parse_iv(out, nfin=1000, tag='ION')
    assert len(ion) == 1 and ion[0][3] == pytest.approx(3.5e-5)


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------
def test_threshold_current_is_i_ref_times_w_over_l():
    dev = {'hfin': 32e-9, 'tfin': 6.5e-9, 'l': 21e-9}
    # W_eff = 70.5 nm, L = 21 nm -> 3.357 squares x 100 nA
    assert spice_sim.threshold_current_A(dev) == pytest.approx(100e-9 * 70.5 / 21.0)
    assert spice_sim.threshold_current_A(dev, nfin=10) == pytest.approx(10 * 100e-9 * 70.5 / 21.0)


def _exp_sweep(vt=0.3, ss_V=0.060, i_at_vt=1e-7, n=29, vmax=0.7):
    v = np.linspace(0.0, vmax, n)
    i = i_at_vt * 10.0 ** ((v - vt) / ss_V)
    return v, i


def test_constant_current_vt_recovers_a_synthetic_threshold():
    v, i = _exp_sweep(vt=0.3)
    assert spice_sim.constant_current_vt(v, i, 1e-7) == pytest.approx(0.3, abs=1e-9)
    # a criterion the sweep never reaches, or already exceeds, is None rather than a number
    assert spice_sim.constant_current_vt(v, i, 1e3) is None
    assert spice_sim.constant_current_vt(v, i, 1e-20) is None


def test_subthreshold_swing_is_fitted_inside_a_current_window():
    v, i = _exp_sweep(vt=0.3, ss_V=0.0617)
    ss = spice_sim.subthreshold_swing_mV_per_dec(v, i, 1e-9, 1e-8)
    assert ss == pytest.approx(61.7, rel=1e-6)
    assert spice_sim.subthreshold_swing_mV_per_dec(v, i, 1e2, 1e3) is None


def test_dibl_sign_and_units():
    assert spice_sim.dibl_mV_per_V(0.300, 0.280, 0.05, 0.70) == pytest.approx(20.0 / 0.65)
    assert spice_sim.dibl_mV_per_V(None, 0.28, 0.05, 0.7) is None


def test_fit_alpha_power_recovers_the_exponent_only_with_the_threshold_subtracted():
    v = np.linspace(0.35, 0.85, 21)
    vt = 0.28
    i = 2e-4 * (v - vt) ** 1.25
    alpha, k, rms = spice_sim.fit_alpha_power(v, i, vt)
    assert alpha == pytest.approx(1.25, abs=1e-6) and k == pytest.approx(2e-4, rel=1e-6)
    assert rms < 1e-9
    # fitting against V instead of (V - Vt) is the classic way to get a wrong exponent
    wrong, _, _ = spice_sim.fit_alpha_power(v, i, 0.0)
    assert wrong > 1.25
    with pytest.raises(ValueError):
        spice_sim.fit_alpha_power(v[:2], i[:2], vt)


# ---------------------------------------------------------------------------
# the device-derived V/F curve
# ---------------------------------------------------------------------------
def _synthetic_model(**kw):
    V = np.linspace(0.30, 0.90, 25)
    vt = 0.28
    I = 2e-4 * np.clip(V - vt, 1e-6, None) ** 1.2
    args = dict(V=V, I_on=I, vdd=0.7, f_anchor_GHz=3.8, vt=vt, ss_mV_dec=62.0, T_K=300.0)
    args.update(kw)
    return DeviceVFModel(**args)


def test_curve_passes_through_the_anchor_and_inverts():
    m = _synthetic_model()
    assert m.frequency(0.7) == pytest.approx(3.8, rel=1e-9)
    for f in (2.5, 3.0, 3.8):
        v, clamped = m.voltage(f)
        assert not clamped
        assert m.frequency(v) == pytest.approx(f, rel=1e-6)
    assert m.dynamic_power_scale(3.8, 3.8) == pytest.approx(1.0)
    assert m.dynamic_power_scale(4.0, 3.8) > 4.0 / 3.8, 'V^2 f must cost more than f alone'


def test_ceiling_is_overdrive_limited_and_reported_as_a_clamp():
    m = _synthetic_model(overdrive=0.10)
    assert m.v_max == pytest.approx(0.77)
    v, clamped = m.voltage(m.f_max * 1.5)
    assert clamped and v == pytest.approx(m.v_max)


def test_alpha_is_reported_from_the_data_not_assumed():
    m = _synthetic_model()
    assert m.alpha_fit == pytest.approx(1.2, abs=1e-3)
    assert not m.calibrated


def test_the_vt_lever_buys_clock_at_fixed_supply_and_costs_leakage():
    base = _synthetic_model()
    low = _synthetic_model(vt_shift_mV=50.0)
    assert low.vt == pytest.approx(base.vt - 0.05)
    assert low.clock_gain() > 0.0
    assert low.frequency(0.7) > base.frequency(0.7)
    # k is held at the nominal device: the shifted curve must NOT be re-anchored to 3.8 GHz
    assert low.frequency(0.7) != pytest.approx(3.8, rel=1e-3)
    assert low.leakage_multiplier == pytest.approx(10 ** (50.0 / 62.0))
    assert base.leakage_multiplier == pytest.approx(1.0)
    assert low.cooling_K_to_offset(10.0) == pytest.approx(math.log2(10 ** (50.0 / 62.0)) * 10.0)


def test_a_shifted_curve_may_not_read_past_the_sweep():
    """0.77 V + 75 mV of shift needs I_on at 0.845 V; a sweep that stops at 0.80 must refuse."""
    V = np.linspace(0.30, 0.80, 21)
    I = 2e-4 * np.clip(V - 0.28, 1e-6, None) ** 1.2
    with pytest.raises(ValueError, match='extend the sweep'):
        DeviceVFModel(V, I, vdd=0.7, f_anchor_GHz=3.8, vt=0.28, ss_mV_dec=62.0,
                      vt_shift_mV=75.0)


def test_source_tag_names_the_card_and_temperature():
    m = _synthetic_model(label='ASAP7 nmos_rvt', T_K=350.0)
    assert m.source_tag == 'spice:asap7:350K'


# ---------------------------------------------------------------------------
# the recorded evidence
# ---------------------------------------------------------------------------
@_needs_evidence
def test_loaded_curve_is_a_device_at_room_temperature():
    m = load_device_vf(T_K=300.0)
    assert m.source_meta['T_K_used'] == pytest.approx(300.0)
    assert 0.15 < m.vt < 0.45, 'V_t,sat {:.3f} V is not a 7 nm HP FinFET'.format(m.vt)
    assert 55.0 < m.ss_mV_dec < 80.0
    assert m.alpha_fit is not None and 0.8 < m.alpha_fit < 2.0
    assert m.frequency(m.vdd) == pytest.approx(3.8, rel=1e-9)
    assert m.f_max > 3.8


@_needs_evidence
def test_threshold_falls_with_temperature_at_a_physical_rate():
    import json
    ev = json.load(open(_EV))
    slope = ev['fits']['dvt_dT_mV_per_K_lin']
    assert -1.5 < slope < -0.2, 'dVt/dT {:.2f} mV/K is outside the FinFET range'.format(slope)
    ss = {r['T_K']: r['ss_lin_mV_dec'] for r in ev['vt']}
    assert ss[400.0] > ss[300.0] > ss[250.0], 'subthreshold swing must rise with temperature'


@_needs_evidence
def test_the_two_spice_evidence_files_agree_on_i_off():
    """Two decks, two sessions, one device: I_off(T) at V_gs = 0 from the gate sweep must
    reproduce the leakage curve's own relative shape. If it does not, one of them is not the
    ASAP7 card."""
    import json
    ev = json.load(open(_EV))
    assert ev['consistency_with_leakage_evidence']['max_abs_pct'] < 5.0


@_needs_toolchain
@_needs_card
def test_the_simulator_gives_a_threshold_and_a_swing():
    import tempfile
    ng, osdi = spice_sim.toolchain()
    va = os.path.join(repo_root(), 'spice_toolchain', 'src', 'VA-Models', 'code', 'bsimcmg',
                      'vacode110', 'bsimcmg.va')
    if not os.path.exists(va):
        pytest.skip('VA-Models source not present')
    dev = parse_card()['nmos_rvt']
    card = spice_sim.render_model_card(dev, 'dut', spice_sim.module_name_of(va))
    deck = spice_sim.vt_deck(card, 'dut', [26.85], osdi, vgs_step=0.025)
    out, _ = spice_sim.run_deck(deck, tempfile.mkdtemp(prefix='vt_test_'), name='t')
    rows = spice_sim.parse_iv(out, nfin=spice_sim.DEFAULT_NFIN, tag='VT')
    assert len(rows) == 29 * 2, out[-2000:]
    lin = [(r[2], r[3]) for r in rows if r[1] == pytest.approx(0.05)]
    v = [x[0] for x in lin]
    i = [x[1] for x in lin]
    i_th = spice_sim.threshold_current_A(dev, nfin=1)
    vt = spice_sim.constant_current_vt(v, i, i_th)
    assert vt is not None and 0.1 < vt < 0.5
    ss = spice_sim.subthreshold_swing_mV_per_dec(v, i, i_th / 1000.0, i_th / 10.0)
    assert ss is not None and 50.0 < ss < 90.0
