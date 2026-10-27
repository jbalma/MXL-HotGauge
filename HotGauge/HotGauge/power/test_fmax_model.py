"""Tests for the generalized f_max model (§P0.31).

Pure tests build a synthetic alpha-power card so they run without the SPICE evidence; the
evidence tests read the recorded sweep. Each pure test encodes a way the answer could be
plausibly wrong: an anchor that re-fits itself at every temperature (the defect this model
replaces), a reference voltage read in the wrong context, a budget that hands back something
other than the 10 % overdrive at the qualification point, a colder die that buys nothing, a
mechanism that binds when its constants say it should not, a pipeline that does not shorten
the period.
"""
import os
import math

import numpy as np
import pytest

from HotGauge.power.fmax_model import (GeneralizedFmaxModel, load_fmax_model, parse_fmax_spec,
                                       core_gradient_K, evidence_path, DEFAULTS, K_EV_PER_K)
from HotGauge.power.clock_search import (is_sustainable, reason_unsustainable,
                                         clock_power_factors)

_needs_evidence = pytest.mark.skipif(not os.path.exists(evidence_path(False)),
                                     reason='device V_t / V/F evidence not generated')


def _synthetic(alpha=1.45, vt=0.28, k300=1.0e-3, dI_dT=-6.0e-4, v_end=1.0):
    """An alpha-power ``I_on(V, T)`` with a mild negative temperature coefficient."""
    V = np.round(np.arange(0.30, v_end + 1e-9, 0.025), 4)
    by_T = {}
    for T in (200.0, 250.0, 300.0, 330.0, 350.0, 400.0, 450.0, 500.0):
        vt_T = vt - 0.00046 * (T - 300.0)
        I = k300 * np.clip(V - vt_T, 1e-3, None) ** alpha * (1.0 + dI_dT * (T - 300.0))
        by_T[T] = I
    return V, by_T


def _model(**kw):
    V, by_T = _synthetic()
    return GeneralizedFmaxModel(V, by_T, vdd=0.70, vt_by_T={300.0: 0.28, 400.0: 0.234}, **kw)


# ---------------------------------------------------------------------------
# the anchor and the period
# ---------------------------------------------------------------------------
def test_anchor_reproduces_the_trace_clock_once_and_only_in_the_anchor_context():
    m = _model()
    assert m.frequency(0.70, T=330.0, dT=24.0) == pytest.approx(3.8, rel=1e-9)
    # NOT re-anchored: a hotter die at the same supply is slower, a colder one faster
    assert m.frequency(0.70, T=400.0, dT=24.0) < 3.8 < m.frequency(0.70, T=300.0, dT=24.0)


def test_period_terms_sum_and_the_reference_fo4_is_where_the_node_sits():
    m = _model()
    t = m.period_terms(0.70, 330.0, 24.0)
    assert t['period_ps'] == pytest.approx(t['gate_ps'] + t['wire_ps'] + t['skew_ps'] + t['overhead_ps'])
    assert t['period_ps'] == pytest.approx(1000.0 / 3.8)
    assert 6.0 < m.FO4_ref_ps < 11.0          # a 7 nm FO4, from a 20-deep 3.8 GHz pipeline
    assert t['dominant'] == 'gate'


def test_shorter_pipeline_raises_the_clock_but_fixed_terms_do_not_shrink():
    ref = _model()
    short = _model(logic_depth=10.0)
    assert short.FO4_ref_ps == pytest.approx(ref.FO4_ref_ps)   # the device did not change
    f_ref, f_short = ref.frequency(0.70, 330.0, 24.0), short.frequency(0.70, 330.0, 24.0)
    assert f_short > f_ref
    assert f_short < 2.0 * f_ref              # overhead + skew are fixed picoseconds
    n = ref.logic_depth_for(10.0, 0.70, 330.0, 24.0)
    assert n is not None and n < 10.0


def test_wire_term_moves_with_temperature_and_skew_with_the_gradient():
    m = _model()
    assert m.wire_ps(430.0) > m.wire_ps(330.0)
    assert m.skew_ps(60.0, 330.0) > m.skew_ps(24.0, 330.0)
    assert m.period_terms(0.70, 330.0, 60.0)['f_GHz'] < 3.8


def test_voltage_inverts_frequency_and_clamps_at_the_device_peak():
    m = _model()
    m.set_context(365.0, 40.0)
    f = 4.2
    v, clamped = m.voltage(f)
    assert not clamped
    assert m.frequency(v) == pytest.approx(f, rel=1e-6)
    v_pk, f_pk, at_end = m.device_peak()
    v_hi, clamped = m.voltage(100.0)
    assert clamped and v_hi == pytest.approx(v_pk)
    # the synthetic alpha-power card never saturates, so its peak is the sweep end
    assert at_end and v_pk == pytest.approx(m.v_sweep_end)


def test_a_saturating_card_names_the_device_as_the_limiter():
    V, by_T = _synthetic(alpha=1.0)
    # bend I_on over above 0.8 V so I_on/V falls: a velocity-saturated device
    for T in by_T:
        I = by_T[T].copy()
        I[V > 0.8] = I[V > 0.8][0] * (1.0 + 0.2 * (V[V > 0.8] - 0.8))
        by_T[T] = I
    m = GeneralizedFmaxModel(V, by_T, vdd=0.70, mechanisms=('em',))
    v_pk, f_pk, at_end = m.device_peak(300.0, 24.0)
    assert not at_end and 0.75 < v_pk < 0.9
    c = m.f_max_at(300.0, 24.0)
    assert c['limiter'] == 'device' and c['v_max_V'] == pytest.approx(v_pk)


def test_reference_voltage_is_the_anchor_supply_whatever_the_context():
    m = _model()
    m.set_context(400.0, 50.0)
    assert m.voltage(3.8)[0] > 0.70                    # the hot die needs more supply for 3.8 GHz
    assert m.reference_voltage(3.8)[0] == pytest.approx(0.70, abs=1e-6)
    dyn, leak, info = clock_power_factors(3.8, 3.8, vf_model=m)
    assert dyn > 1.0 and info['V_ref'] == pytest.approx(0.70, abs=1e-6)
    assert info['vf_source'].startswith('fmax:')


# ---------------------------------------------------------------------------
# the reliability budget
# ---------------------------------------------------------------------------
def test_budget_gives_back_the_ten_percent_overdrive_at_the_qualification_point():
    m = _model()
    rel = m.v_max_reliability(T=373.15, dT=24.0)
    assert rel['v_max_V'] == pytest.approx(0.77, abs=2e-3)
    assert not rel['sweep_limited']


def test_a_cooler_worst_block_buys_supply_and_the_ceiling_names_its_limiter():
    m = _model()
    v_hot = m.v_max_reliability(373.15)['v_max_V']
    v_92 = m.v_max_reliability(365.15)['v_max_V']
    v_27 = m.v_max_reliability(300.15)['v_max_V']
    assert v_hot < v_92 < v_27
    c = m.f_max_at(365.15, 32.0)
    assert c['limiter'].startswith('reliability:')
    assert c['f_max_GHz'] == pytest.approx(m.frequency(c['v_max_V'], 365.15, 32.0))


def test_tddb_binds_before_electromigration_with_the_stated_constants():
    m = _model()
    for T in (373.15, 350.0, 320.0):
        rel = m.v_max_reliability(T)
        # at the corner both mechanisms give back V_q: a tie, reported as one
        assert rel['binding'] == ('em+tddb' if T == 373.15 else 'tddb')
        # (at the corner the two bisections agree to ~1e-16 V; a tie, not an ordering)
        assert rel['per_mechanism']['em']['v_max_V'] >= rel['per_mechanism']['tddb']['v_max_V'] - 1e-6
        cf = rel['per_mechanism']['tddb'].get('closed_form_V')
        if cf is not None:
            assert cf == pytest.approx(rel['per_mechanism']['tddb']['v_max_V'], rel=1e-4)


def test_tddb_closed_form_matches_the_arrhenius_budget():
    m = _model(tddb_n=40.0, tddb_Ea_eV=0.6)
    T = 340.0
    rel = m.v_max_reliability(T)
    expect = 0.77 * math.exp(-(0.6 / K_EV_PER_K) * (1.0 / 373.15 - 1.0 / T) / 40.0)
    assert rel['per_mechanism']['tddb']['v_max_V'] == pytest.approx(expect, rel=1e-4)


def test_em_alone_is_sweep_limited_on_a_cool_die():
    m = _model(mechanisms=('em',))
    rel = m.v_max_reliability(310.0)
    assert rel['binding'] == 'em'
    assert rel['sweep_limited'] and rel['v_max_V'] == pytest.approx(m.v_sweep_end)
    assert m.f_max_at(310.0)['limiter'] == 'sweep_end'


def test_native_budget_reference_puts_a_92C_target_over_budget():
    m = _model(budget_ref='native', T_native_K=351.73)
    rel = m.v_max_reliability(365.15)
    assert rel['v_max_V'] < 0.70                       # hotter than the native die's worst block
    assert m.v_max_reliability(340.0)['v_max_V'] > 0.70


def test_bad_parameters_are_refused():
    with pytest.raises(ValueError):
        _model(nonsense=1.0)
    with pytest.raises(ValueError):
        _model(wire_fraction=1.0)
    with pytest.raises(ValueError):
        _model(budget_ref='guess')
    with pytest.raises(ValueError):
        _model(overhead_fraction=0.99)


# ---------------------------------------------------------------------------
# the search predicates and helpers
# ---------------------------------------------------------------------------
def test_search_predicates_honour_a_non_thermal_reason_but_thermal_first():
    ok = {'peak_K': 360.0, 'diverged': False, 'unconverged': False}
    assert is_sustainable(ok, 373.15)
    bad = dict(ok, unsustainable_reason='reliability:tddb')
    assert not is_sustainable(bad, 373.15)
    assert reason_unsustainable(bad, 373.15) == 'reliability:tddb'
    hot = dict(bad, peak_K=380.0)
    assert reason_unsustainable(hot, 373.15) == 'over_thermal_limit'


def test_core_gradient_reads_domains_and_excludes_l3():
    temps = {'cALU_0': 370.0, 'iALU_0': 350.0, 'L3_0': 300.0, 'cALU_1': 360.0, 'iALU_1': 355.0,
             'IO_3': 310.0}
    worst, mean, core = core_gradient_K(temps)
    assert worst == pytest.approx(20.0) and core == 0
    assert mean == pytest.approx(12.5)


def test_parse_fmax_spec():
    assert parse_fmax_spec('fmax') == {}
    p = parse_fmax_spec('fmax:N=10,w=0.4,ref=native,tddb_n=48,mechanisms=em+tddb')
    assert p == {'logic_depth': 10.0, 'wire_fraction': 0.4, 'budget_ref': 'native',
                 'tddb_n': 48.0, 'mechanisms': ('em', 'tddb')}
    with pytest.raises(ValueError):
        parse_fmax_spec('fmax:bogus=1')


@_needs_evidence
def test_recorded_card_anchors_and_the_hot_corner_is_the_overdrive():
    m = load_fmax_model()
    assert m.frequency(0.70, 330.0, DEFAULTS['dT_anchor_K']) == pytest.approx(3.8, rel=1e-9)
    assert m.v_max_reliability(373.15)['v_max_V'] == pytest.approx(0.77, abs=2e-3)
    assert 6.0 < m.FO4_ref_ps < 11.0
    assert 0.0 < m.alpha_cell(330.0) < 2e-3
    d = m.describe()
    assert d['budget_reference']['ref'] == 'qual' and 'params' in d


# ---------------------------------------------------------------------------
# §P0.39: the rail model, V_eff = V - IR
# ---------------------------------------------------------------------------
def test_rail_is_off_by_default_and_the_anchor_survives_turning_it_on():
    m0, m = _model(), _model(rail_droop_native=0.05)
    assert not m0.has_rail and m.has_rail
    assert m0.period_terms(0.70, 330.0, 24.0)['ir_drop_V'] == 0.0
    # on its native rails at its native current density the native die is still the trace
    assert m.ir_drop_V() == pytest.approx(0.035)
    assert m.frequency(0.70, T=330.0, dT=24.0) == pytest.approx(3.8, rel=1e-9)


def test_more_current_on_the_same_rails_costs_clock_and_needs_more_supply():
    m = _model(rail_droop_native=0.05)
    f1 = m.frequency(0.70, T=330.0, dT=24.0)
    v1, _ = m.voltage(3.8, T=330.0, dT=24.0)
    m.set_context(330.0, 24.0, J_A_per_mm2=4 * DEFAULTS['J_native_A_per_mm2'])
    assert m.ir_drop_V() == pytest.approx(0.14)
    assert m.frequency(0.70) < f1
    v4, _ = m.voltage(3.8)
    assert v4 == pytest.approx(v1 + 0.14 - 0.035, abs=2e-3)      # the supply makes the droop up
    assert m.period_terms(v4)['V_eff_V'] == pytest.approx(0.70 - 0.035, abs=2e-3)


def test_resized_rails_give_the_droop_back_in_proportion():
    J = 8 * DEFAULTS['J_native_A_per_mm2']
    a, b = _model(rail_droop_native=0.05), _model(rail_droop_native=0.05, rail_resize=8.0)
    assert b.ir_drop_V(J) == pytest.approx(a.ir_drop_V(J) / 8.0)
    assert b.ir_drop_V(J) == pytest.approx(0.035)               # J x re-sizing: the memo's claim


def test_rails_that_eat_the_supply_give_no_clock_rather_than_an_error():
    m = _model(rail_droop_native=0.05)
    m.set_context(330.0, 24.0, J_A_per_mm2=16 * DEFAULTS['J_native_A_per_mm2'])   # 0.56 V of drop
    assert m.frequency(0.70) == 0.0
    assert m.frequency(1.00) > 0.0
    t = m.period_terms(0.70)                      # the driver calls this directly on the row it reports
    assert t['f_GHz'] == 0.0 and t['dominant'] == 'rail' and t['period_ps'] is None
    assert m.logic_depth_for(10.0, 0.70) == 0.0 or m.logic_depth_for(10.0, 0.70) is None


def test_worst_current_density_reads_execution_blocks_only():
    from HotGauge.power.fmax_model import worst_current_density
    P = {'cALU_3': 0.7, 'L2_3': 50.0, 'FPUs_1': 1.4, 'IO': 9.0}
    A = {'cALU_3': 0.01, 'L2_3': 0.5, 'FPUs_1': 0.1, 'IO': 1.0}
    J, who = worst_current_density(P, A, 0.70)
    assert who == 'cALU_3' and J == pytest.approx(100.0)
    J_all, who_all = worst_current_density(P, A, 0.70, families=None)
    assert who_all == 'L2_3'


def test_rail_spec_keys_and_source_tag():
    p = parse_fmax_spec('fmax:rail=0.05,resize=4')
    assert p == {'rail_droop_native': 0.05, 'rail_resize': 4.0}
    assert _model(**p).source_tag.endswith(':rail0.05x4')
    assert 'rail' not in _model().source_tag
