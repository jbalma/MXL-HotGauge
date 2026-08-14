"""Tests for the sustainable-clock search (HotGauge.power.clock_search).

Pure Python: the coupled solve is replaced by a monotone stand-in, so these pin the SEARCH
logic and the power scaling, not the thermal model.
"""
import numpy as np
import pytest

from HotGauge.power.traces import BasicPowerTrace
from HotGauge.power.clock_search import (clock_power_factors, scale_trace_for_clock,
                                         is_sustainable, reason_unsustainable,
                                         find_max_sustainable_clock, VF_TABLE_MAX_GHZ)


# ---------------------------------------------------------------------------
# Power scaling with clock
# ---------------------------------------------------------------------------
def test_factors_are_unity_at_the_reference_clock():
    dyn, leak, info = clock_power_factors(3.8, 3.8)
    assert dyn == pytest.approx(1.0)
    assert leak == pytest.approx(1.0)
    assert not info['vf_clamped']


def test_dynamic_grows_faster_than_leakage_with_clock():
    dyn, leak, _ = clock_power_factors(5.0, 3.8)
    assert dyn > 1.0 and leak > 1.0
    # V^2*f against V^1 -- the whole reason a higher clock is not free.
    assert dyn > leak


def test_above_the_vf_table_the_voltage_clamps_and_says_so():
    _, _, info = clock_power_factors(6.5, 3.8)
    assert info['vf_clamped']
    assert info['V'] == pytest.approx(1.4)          # top of VF_PAIRS


def test_scale_trace_splits_dynamic_from_leakage():
    trace = BasicPowerTrace({'a': np.array([2.0]), 'b': np.array([1.0])}, 1.0)
    leak = {'a': np.array([0.5])}                    # 'b' is purely dynamic
    dyn_s, leak_s, _ = clock_power_factors(4.6, 3.8)
    scaled, new_leak, info = scale_trace_for_clock(trace, leak, 4.6, 3.8)
    assert scaled['a'][0] == pytest.approx(1.5 * dyn_s + 0.5 * leak_s)
    assert scaled['b'][0] == pytest.approx(1.0 * dyn_s)
    assert new_leak['a'][0] == pytest.approx(0.5 * leak_s)
    assert info['dyn_scale'] == pytest.approx(dyn_s)


def test_leakage_exponent_zero_reproduces_ignoring_voltage():
    trace = BasicPowerTrace({'a': np.array([2.0])}, 1.0)
    leak = {'a': np.array([0.5])}
    _, new_leak, _ = scale_trace_for_clock(trace, leak, 5.0, 3.8,
                                           leakage_voltage_exponent=0.0)
    assert new_leak['a'][0] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# The sustainability predicate
# ---------------------------------------------------------------------------
def test_unverified_points_are_not_sustainable():
    """An answer that still moves with the damping is not evidence of anything."""
    assert not is_sustainable({'peak_K': 350.0, 'unconverged': True}, thermal_limit_K=373.15)
    assert reason_unsustainable({'peak_K': 350.0, 'unconverged': True}) == 'unverified'


def test_runaway_and_over_limit_are_distinguished():
    assert reason_unsustainable({'diverged': True}) == 'thermal_runaway'
    assert reason_unsustainable({'peak_K': 400.0}, 373.15) == 'over_thermal_limit'
    assert reason_unsustainable({'peak_K': 350.0}, 373.15) is None


# ---------------------------------------------------------------------------
# The search
# ---------------------------------------------------------------------------
def _thermal_stand_in(f_limit, runaway_above=None):
    """Peak temperature rising with clock, crossing the 373.15 K limit at ``f_limit``."""
    def evaluate(f):
        if runaway_above is not None and f > runaway_above:
            return {'diverged': True}
        return {'peak_K': 373.15 + 40.0 * (f - f_limit), 'converged': True}
    return evaluate


def test_finds_the_clock_where_the_limit_bites():
    res = find_max_sustainable_clock(_thermal_stand_in(4.37), 3.5, 5.0, tol_GHz=0.02)
    assert res['f_sustainable_GHz'] == pytest.approx(4.37, abs=0.02)
    assert res['limited_by'] == 'over_thermal_limit'
    assert not res['at_ceiling']
    lo, hi = res['bracket_GHz']
    assert lo <= 4.37 <= hi


def test_reports_the_search_ceiling_rather_than_inventing_a_limit():
    """If the part never hits a limit in range, the number is OUR bound, not the silicon's."""
    res = find_max_sustainable_clock(_thermal_stand_in(9.0), 3.5, 5.0, tol_GHz=0.02)
    assert res['at_ceiling'] and res['limited_by'] == 'search_ceiling'
    assert res['f_sustainable_GHz'] == pytest.approx(5.0)


def test_no_sustainable_clock_returns_none_not_the_floor():
    res = find_max_sustainable_clock(_thermal_stand_in(2.0), 3.5, 5.0)
    assert res['f_sustainable_GHz'] is None
    assert res['limited_by'] == 'over_thermal_limit'


def test_runaway_is_reported_as_such_not_as_a_temperature_limit():
    res = find_max_sustainable_clock(_thermal_stand_in(9.0, runaway_above=4.2), 3.5, 5.0,
                                     tol_GHz=0.02)
    assert res['limited_by'] == 'thermal_runaway'
    assert res['f_sustainable_GHz'] == pytest.approx(4.2, abs=0.02)


def test_search_is_capped_at_the_vf_table_by_default():
    res = find_max_sustainable_clock(_thermal_stand_in(9.0), 3.5, 6.5, tol_GHz=0.05)
    assert res['search_capped_at_vf_table']
    assert res['f_sustainable_GHz'] == pytest.approx(VF_TABLE_MAX_GHZ)


def test_bisection_stays_within_its_evaluation_budget():
    res = find_max_sustainable_clock(_thermal_stand_in(4.37), 3.5, 5.0, tol_GHz=1e-6,
                                     max_evals=8)
    assert len(res['evaluations']) <= 8
