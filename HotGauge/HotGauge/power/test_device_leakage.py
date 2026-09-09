"""Tests for the card reader and the off-state leakage model.

The synthetic tests check the arithmetic; the ones marked against the shipped card check that the
vendored ASAP7 file still says what the model assumes it says. That second kind matters more than
it looks: the whole point of reading a vendor card is that the numbers are not ours, so a silent
change to the file must fail a test rather than quietly change a published curve.
"""
import os

import numpy as np
import pytest

from HotGauge.power.spice_cards import parse_card, card_path, require
from HotGauge.power.device_leakage import (varshni_eg, VarshniBarrier, LinearBarrier,
                                           barriers_from_card, fit_barrier, extrapolation_test,
                                           DeviceLeakageCurve, K_OVER_Q)

_CARD = card_path()
_needs_card = pytest.mark.skipif(not os.path.exists(_CARD), reason='vendored card not present')


# ---------------------------------------------------------------------------
# Card parsing
# ---------------------------------------------------------------------------
def test_parse_synthetic_card(tmp_path):
    p = tmp_path / 'toy.pm'
    p.write_text('* a comment\n'
                 '.model nfet nmos level = 17\n'
                 '+version = 107   tnom = 25\n'
                 '**** banner ****\n'
                 '+ute     = -0.7           bg0sub  = 1.17\n'
                 '.model pfet pmos level = 17\n'
                 '+ute = -0.5\n')
    d = parse_card(str(p))
    assert set(d) == {'nfet', 'pfet'}
    assert d['nfet']['__type__'] == 'nmos' and d['nfet']['__level__'] == 17
    assert d['nfet']['ute'] == pytest.approx(-0.7)
    assert d['nfet']['bg0sub'] == pytest.approx(1.17)
    assert d['pfet']['__type__'] == 'pmos'
    assert 'level' not in d['nfet'], 'level is stored as __level__, not as a parameter'


def test_empty_card_is_an_error(tmp_path):
    p = tmp_path / 'empty.pm'
    p.write_text('* nothing here\n')
    with pytest.raises(ValueError):
        parse_card(str(p))


def test_require_names_the_missing_parameter():
    with pytest.raises(KeyError, match='nosuchparam'):
        require({'ute': -0.7}, 'nosuchparam')


@_needs_card
def test_shipped_card_has_the_eight_asap7_devices():
    d = parse_card()
    assert set(d) == {'nmos_lvt', 'nmos_rvt', 'nmos_slvt', 'nmos_sram',
                      'pmos_lvt', 'pmos_rvt', 'pmos_slvt', 'pmos_sram'}
    assert all(v['__level__'] == 17 for v in d.values()), 'converted to the ngspice level number'
    assert all(v['version'] == 107 for v in d.values()), 'BSIM-CMG 107'


@_needs_card
def test_shipped_card_bandgap_is_silicon():
    """`[!]` The load-bearing check: if this drifts, every extrapolated curve moves."""
    n = parse_card()['nmos_rvt']
    eg300 = varshni_eg(300.0, n['bg0sub'], n['tbgasub'], n['tbgbsub'])
    assert eg300 == pytest.approx(1.1245, abs=2e-3), 'silicon is 1.12 eV at room temperature'
    assert varshni_eg(500.0, n['bg0sub'], n['tbgasub'], n['tbgbsub']) < eg300, 'gap narrows with T'


# ---------------------------------------------------------------------------
# Varshni
# ---------------------------------------------------------------------------
def test_varshni_is_monotonically_decreasing():
    T = np.linspace(200, 600, 50)
    eg = varshni_eg(T, 1.17, 4.73e-4, 636.0)
    assert np.all(np.diff(eg) < 0)


def test_varshni_at_zero_kelvin_is_eg0():
    assert varshni_eg(0.0, 1.17, 4.73e-4, 636.0) == pytest.approx(1.17)


# ---------------------------------------------------------------------------
# The barrier models
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('model', [
    VarshniBarrier(330.0, -0.7, 1.17, 4.73e-4, 636.0),
    LinearBarrier(330.0, -0.7),
])
def test_ratio_is_one_at_the_reference(model):
    p = model.initial_guess()
    assert model.ratio(330.0, p) == pytest.approx(1.0)


@pytest.mark.parametrize('model', [
    VarshniBarrier(330.0, -0.7, 1.17, 4.73e-4, 636.0),
    LinearBarrier(330.0, -0.7),
])
def test_leakage_rises_with_temperature(model):
    T = np.linspace(250, 500, 30)
    r = model.ratio(T, model.initial_guess())
    assert np.all(np.diff(r) > 0), 'off-state leakage must increase with temperature'


def test_linear_barrier_matches_hand_computed_ratio():
    """Pin the exponent convention so a sign slip cannot pass."""
    m = LinearBarrier(300.0, 0.0)          # ute=0 removes the mobility term
    a, b = 0.30, 0.0                       # flat barrier: only the vt**2 and exp(1/T) terms move
    T = 400.0
    expect = (T / 300.0) ** 2 * np.exp((a / 300.0 - a / T) / K_OVER_Q)
    assert m.ratio(T, (a, b)) == pytest.approx(expect, rel=1e-12)


def test_fit_recovers_the_synthetic_CURVE():
    """The curve is identifiable to machine precision, which is what gets used."""
    m = LinearBarrier(330.0, -0.7)
    truth = (0.32, -4.0e-4)
    T = np.arange(310.0, 401.0, 10.0)
    I = m.ratio(T, truth)
    p, rms = fit_barrier(m, T, I)
    assert rms < 1e-6
    assert m.ratio(T, p) == pytest.approx(I, rel=1e-5)


def test_the_two_parameters_are_DEGENERATE_over_the_fit_window():
    """`[!]` A property of the model that must not be discovered later by surprise.

    Over a 90 K window the barrier height and its slope trade off almost exactly: the recovered
    parameters differ from the truth by ~1 % while the curve is reproduced to 1e-5. So the fitted
    ``phi0``/``b`` are NOT measurements of a barrier height or of dV_th/dT and must never be
    quoted as such -- only the curve they generate means anything. That the two independent
    barrier forms nevertheless agree out to 500 K (see the evidence file) is a separate and
    stronger check than parameter recovery would have been.
    """
    m = LinearBarrier(330.0, -0.7)
    truth = (0.32, -4.0e-4)
    T = np.arange(310.0, 401.0, 10.0)
    p, _ = fit_barrier(m, T, m.ratio(T, truth))
    assert abs(p[0] - truth[0]) > 1e-4, 'parameters are not pinned down'
    assert m.ratio(T, p) == pytest.approx(m.ratio(T, truth), rel=1e-5), 'yet the curve is'


def test_extrapolation_survives_the_degeneracy():
    """Degenerate in-window parameters could still diverge outside it. Check they do not."""
    m = LinearBarrier(330.0, -0.7)
    truth = (0.32, -4.0e-4)
    T = np.arange(310.0, 401.0, 10.0)
    p, _ = fit_barrier(m, T, m.ratio(T, truth))
    T_out = np.array([200.0, 250.0, 450.0, 500.0])
    assert m.ratio(T_out, p) == pytest.approx(m.ratio(T_out, truth), rel=0.05)


def test_extrapolation_test_is_exact_on_synthetic_data():
    m = LinearBarrier(330.0, -0.7)
    T = np.arange(310.0, 401.0, 10.0)
    I = m.ratio(T, (0.32, -4.0e-4))
    r = extrapolation_test(m, T, I, n_fit=7)
    assert r['n_held_out'] == 3
    assert r['held_out_T_K'] == [380.0, 390.0, 400.0]
    assert r['worst_factor'] == pytest.approx(1.0, abs=1e-3)


def test_extrapolation_test_needs_a_held_out_point():
    m = LinearBarrier(330.0, -0.7)
    T = np.arange(310.0, 401.0, 10.0)
    I = m.ratio(T, (0.32, -4.0e-4))
    with pytest.raises(ValueError):
        extrapolation_test(m, T, I, n_fit=len(T))


# ---------------------------------------------------------------------------
# The gate floor -- the part the cold-zone claim rests on
# ---------------------------------------------------------------------------
def test_gate_floor_stops_total_leakage_falling_to_zero():
    m = LinearBarrier(330.0, -0.7)
    c = DeviceLeakageCurve(m, (0.32, -4.0e-4), gate_fraction_at_ref=0.006)
    assert c.subthreshold_rel(150.0) < 1e-6, 'subthreshold collapses when cold'
    assert c.total_rel(150.0) == pytest.approx(0.006, rel=1e-3), 'but the gate floor remains'


def test_no_gate_term_means_no_knee():
    m = LinearBarrier(330.0, -0.7)
    assert DeviceLeakageCurve(m, (0.32, -4.0e-4), 0.0).floor_temperature_K() is None


def test_knee_is_inside_the_bracket_and_cold():
    m = LinearBarrier(330.0, -0.7)
    knee = DeviceLeakageCurve(m, (0.32, -4.0e-4), 0.006).floor_temperature_K()
    assert 150.0 < knee < 320.0


@_needs_card
def test_barriers_from_card_uses_the_cards_own_numbers():
    dev = parse_card()['nmos_rvt']
    mods = barriers_from_card(dev, 330.0)
    assert mods['varshni'].eg0 == dev['bg0sub']
    assert mods['varshni'].alpha == dev['tbgasub']
    assert mods['varshni'].beta == dev['tbgbsub']
    assert mods['linear'].ute == dev['ute'] == mods['varshni'].ute
