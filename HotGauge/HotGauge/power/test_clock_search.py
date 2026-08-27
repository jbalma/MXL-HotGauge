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


def test_stopping_at_the_vf_table_top_is_a_device_limit_not_a_search_limit():
    """Two different reasons to stop short, and only one of them is a measurement.

    At the V/F table top the part is VOLTAGE-limited: the next clock step needs a voltage the
    device cannot take (5.5 GHz -> 1.82 V against a 1.4 V maximum), so no amount of cooling
    buys more clock. A caller-chosen range running out is our bound, not the silicon's.
    """
    res = find_max_sustainable_clock(_thermal_stand_in(9.0), 3.5, 5.0, tol_GHz=0.02)
    assert res['at_ceiling'] and res['limited_by'] == 'vf_envelope'
    assert res['voltage_limited'] is True
    assert res['f_sustainable_GHz'] == pytest.approx(5.0)

    # A range the caller picked below the envelope is a search ceiling, and must say so.
    res = find_max_sustainable_clock(_thermal_stand_in(9.0), 3.0, 4.5, tol_GHz=0.02)
    assert res['limited_by'] == 'search_ceiling' and res['voltage_limited'] is False


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


# ---------------------------------------------------------------------------
# Per-core activity -- the degeneracy axis (see docs/DESIGN_STUDY_PLAN.md)
# ---------------------------------------------------------------------------
def _core_trace():
    return BasicPowerTrace({'Core0/Execution Unit/Integer ALUs': np.array([2.0]),
                            'Core1/Execution Unit/Integer ALUs': np.array([2.0]),
                            'Core2/Execution Unit/Integer ALUs': np.array([2.0]),
                            'BUSES': np.array([1.0]),
                            'Processor/Total L3s': np.array([3.0])}, 1.0)


def test_scale_cores_touches_only_per_core_entries():
    from HotGauge.power.clock_search import scale_cores
    out = scale_cores(_core_trace(), {0: 1.0, 1: 0.25, 2: 0.0})
    assert out['Core0/Execution Unit/Integer ALUs'][0] == pytest.approx(2.0)
    assert out['Core1/Execution Unit/Integer ALUs'][0] == pytest.approx(0.5)
    assert out['Core2/Execution Unit/Integer ALUs'][0] == pytest.approx(0.0)
    # Uncore is not per-core and must be left alone.
    assert out['BUSES'][0] == pytest.approx(1.0)
    assert out['Processor/Total L3s'][0] == pytest.approx(3.0)


def test_single_core_turbo_leaves_one_core_saturated():
    from HotGauge.power.clock_search import single_core_turbo, scale_cores
    m = single_core_turbo(3, hot_core=1, background=0.2)
    assert m == {0: 0.2, 1: 1.0, 2: 0.2}
    out = scale_cores(_core_trace(), m)
    assert out['Core1/Execution Unit/Integer ALUs'][0] == pytest.approx(2.0)
    assert out['Core0/Execution Unit/Integer ALUs'][0] == pytest.approx(0.4)


def test_mixed_utilisation_activates_the_requested_fraction():
    from HotGauge.power.clock_search import mixed_utilisation
    m = mixed_utilisation(8, active_fraction=0.5, background=0.1)
    assert sum(1 for v in m.values() if v == 1.0) == 4
    assert sum(1 for v in m.values() if v == 0.1) == 4


def test_activity_maps_reject_out_of_range_fractions():
    from HotGauge.power.clock_search import single_core_turbo, mixed_utilisation
    with pytest.raises(ValueError):
        single_core_turbo(4, background=1.5)
    with pytest.raises(ValueError):
        mixed_utilisation(4, active_fraction=-0.1)


# ---------------------------------------------------------------------------
# Unit emphasis -- the intra-core degeneracy axis (design G)
# ---------------------------------------------------------------------------
def _balanced_core():
    """A core whose power is spread over many similar units -- i.e. a thermal plateau."""
    p = {'Core0/Execution Unit/Floating Point Units': np.array([0.55]),
         'Core0/Execution Unit/Complex ALUs': np.array([0.36]),
         'Core0/Execution Unit/Integer ALUs': np.array([0.31]),
         'Core0/Execution Unit/Results Broadcast Bus': np.array([0.26]),
         'Core0/Load Store Unit/Data Cache': np.array([0.23]),
         'Core0/L2': np.array([0.07]),
         'Core1/Execution Unit/Floating Point Units': np.array([0.55]),
         'Core1/L2': np.array([0.07]),
         'BUSES': np.array([1.0])}
    return BasicPowerTrace(p, 1.0)


def _core_total(trace, idx):
    return sum(float(np.sum(v)) for k, v in trace.powers.items()
               if k.startswith('Core{}/'.format(idx)))


def test_emphasis_concentrates_power_without_changing_core_power():
    from HotGauge.power.clock_search import emphasise_units
    t = _balanced_core()
    before = _core_total(t, 0)
    out = emphasise_units(t, 'Floating Point Units', 2.0)
    assert _core_total(out, 0) == pytest.approx(before, rel=1e-9)
    # The emphasised unit doubled; the rest of the same core gave it back.
    assert out['Core0/Execution Unit/Floating Point Units'][0] == pytest.approx(1.10)
    assert out['Core0/Execution Unit/Complex ALUs'][0] < 0.36


def test_emphasis_is_per_core_and_leaves_the_uncore_alone():
    from HotGauge.power.clock_search import emphasise_units
    out = emphasise_units(_balanced_core(), 'Floating Point Units', 2.0)
    assert out['BUSES'][0] == pytest.approx(1.0)
    # Core1 has a different mix, so it gets its own scaling, not Core0's.
    assert out['Core1/Execution Unit/Floating Point Units'][0] == pytest.approx(1.10)
    assert out['Core1/L2'][0] < 0.07


def test_emphasis_raises_the_share_of_the_targeted_unit():
    from HotGauge.power.clock_search import emphasise_units
    t = _balanced_core()
    share = lambda tr: (float(tr['Core0/Execution Unit/Floating Point Units'][0])
                        / _core_total(tr, 0))
    assert share(emphasise_units(t, 'Floating Point Units', 1.5)) > share(t)


def test_emphasis_rejects_a_non_positive_factor():
    from HotGauge.power.clock_search import emphasise_units
    with pytest.raises(ValueError):
        emphasise_units(_balanced_core(), 'Floating Point Units', 0.0)


def test_per_core_clock_scales_only_the_boosted_core():
    from HotGauge.power.clock_search import (scale_trace_for_clock_per_core,
                                             clock_power_factors)
    trace = BasicPowerTrace({'Core0/Execution Unit/Integer ALUs': np.array([2.0]),
                             'Core1/Execution Unit/Integer ALUs': np.array([2.0]),
                             'BUSES': np.array([1.0])}, 1.0)
    leak = {'Core0/Execution Unit/Integer ALUs': np.array([0.5]),
            'Core1/Execution Unit/Integer ALUs': np.array([0.5])}
    out, new_leak, info = scale_trace_for_clock_per_core(trace, leak, {0: 4.6}, 3.8)
    dyn, lk, _ = clock_power_factors(4.6, 3.8)
    assert out['Core0/Execution Unit/Integer ALUs'][0] == pytest.approx(1.5 * dyn + 0.5 * lk)
    assert out['Core1/Execution Unit/Integer ALUs'][0] == pytest.approx(2.0)  # untouched
    assert out['BUSES'][0] == pytest.approx(1.0)                              # uncore untouched
    assert info['per_core'] == {0: 4.6}


def test_per_core_clock_matches_the_global_one_when_every_core_is_boosted():
    from HotGauge.power.clock_search import (scale_trace_for_clock,
                                             scale_trace_for_clock_per_core)
    trace = BasicPowerTrace({'Core0/a': np.array([2.0]), 'Core1/a': np.array([2.0])}, 1.0)
    leak = {'Core0/a': np.array([0.5]), 'Core1/a': np.array([0.5])}
    g, _, _ = scale_trace_for_clock(trace, leak, 4.6, 3.8)
    p, _, _ = scale_trace_for_clock_per_core(trace, leak, {0: 4.6, 1: 4.6}, 3.8)
    for k in ('Core0/a', 'Core1/a'):
        assert p[k][0] == pytest.approx(g[k][0])


# ---------------------------------------------------------------------------
# Selectable V/F source (IRDS 2024) -- the shipped table is wrong in absolute terms
# ---------------------------------------------------------------------------
def test_irds_and_shipped_curves_agree_on_the_COST_of_clock():
    """The surprise, and the reason the V/F error did less damage than it looked like it would.

    The pipeline never uses an absolute voltage -- it scales a McPAT trace by the RATIO
    ``(V/V_ref)^2 (f/f_ref)`` against the trace's own clock -- so the shipped table's ~2x supply
    voltage error CANCELS. Inside the 2024 node's valid range the two curves give dynamic
    multipliers within 6% of each other, and IRDS is the slightly more expensive of the two.
    So the power numbers in this study do not move; only the ceiling does.
    """
    from HotGauge.power.clock_search import clock_power_factors
    from HotGauge.power.irds_vf import IRDSVFModel
    m = IRDSVFModel(2024)
    for f in (3.0, 3.4, 4.0, 4.1):
        dyn_old, _, info_old = clock_power_factors(f, 3.8)
        dyn_new, _, info_new = clock_power_factors(f, 3.8, vf_model=m)
        assert not info_new['vf_clamped'], f
        assert dyn_new == pytest.approx(dyn_old, rel=0.15), f
    assert info_old['vf_source'] == 'VF_PAIRS'
    assert info_new['vf_source'] == 'irds:2024:wireloaded'


def test_above_the_node_ceiling_the_irds_multiplier_is_clamped_and_flagged():
    """Past f_max the voltage cannot rise, so the multiplier stops growing and is NOT a cost --
    it is a part that does not run. The flag is the only thing that makes it readable."""
    from HotGauge.power.clock_search import clock_power_factors
    from HotGauge.power.irds_vf import IRDSVFModel
    m = IRDSVFModel(2024)
    dyn_old, _, _ = clock_power_factors(5.0, 3.8)
    dyn_new, _, info = clock_power_factors(5.0, 3.8, vf_model=m)
    assert info['vf_clamped'] is True
    assert dyn_new < dyn_old          # clamped, hence understating -- which is why it is flagged


def test_vf_model_replaces_the_search_ceiling_too():
    """A 'voltage-limited' verdict is only meaningful against the right ceiling. The 2024 node
    tops out near 4.15 GHz, not the shipped table's 5.0 -- this is where the table error bit."""
    from HotGauge.power.clock_search import find_max_sustainable_clock, VF_TABLE_MAX_GHZ
    from HotGauge.power.irds_vf import IRDSVFModel
    m = IRDSVFModel(2024)
    assert m.f_max < VF_TABLE_MAX_GHZ
    res = find_max_sustainable_clock(lambda f: {'peak_K': 300.0}, 3.0, 6.0, vf_model=m)
    assert res['limited_by'] == 'vf_envelope'
    assert res['voltage_limited'] is True
    assert res['f_sustainable_GHz'] == pytest.approx(m.f_max)
    assert res['vf_ceiling_GHz'] == pytest.approx(m.f_max)
    assert 'IRDSVFModel' in res['vf_source']


def test_default_vf_source_is_unchanged():
    """Every existing result was measured through VF_PAIRS. The new option must not move them."""
    from HotGauge.power.clock_search import find_max_sustainable_clock
    res = find_max_sustainable_clock(lambda f: {'peak_K': 300.0}, 3.0, 6.0)
    assert res['f_sustainable_GHz'] == pytest.approx(VF_TABLE_MAX_GHZ)
    assert res['vf_source'] == 'VF_PAIRS'


def test_per_core_scaler_honours_the_vf_model():
    from HotGauge.power.clock_search import (scale_trace_for_clock_per_core,
                                             scale_trace_for_clock)
    from HotGauge.power.irds_vf import IRDSVFModel
    m = IRDSVFModel(2024)
    trace = BasicPowerTrace({'Core0/a': np.array([2.0]), 'Core1/a': np.array([2.0])}, 1.0)
    leak = {'Core0/a': np.array([0.5]), 'Core1/a': np.array([0.5])}
    p, _, _ = scale_trace_for_clock_per_core(trace, leak, {0: 3.2, 1: 3.2}, 3.8, vf_model=m)
    g, _, _ = scale_trace_for_clock(trace, leak, 3.2, 3.8, vf_model=m)
    plain, _, _ = scale_trace_for_clock(trace, leak, 3.2, 3.8)
    for k in ('Core0/a', 'Core1/a'):
        assert p[k][0] == pytest.approx(g[k][0])
        assert g[k][0] != pytest.approx(plain[k][0])   # the model was used, not silently dropped


class TestProbeFailuresMustNotSinkTheAnswer:
    """The MR planner probes past the stability boundary on purpose. Counting those probes as
    evidence about the ANSWER is how the MR arm of every clock study came to report its floor.

    Measured across the catalogue before the fix (27 Aug 2026): 9 of 10 ``array_on`` rows
    returned exactly 2.0000 GHz -- the value of ``--f-lo`` -- with ``limited_by='unverified'``.
    ``mr_comparison.py`` had already been fixed for the identical defect; ``clock_headroom.py``
    had taken only the ``diverged`` half of that fix and not the ``unconverged`` half.

    These tests pin the SEMANTICS the drivers depend on, so the asymmetry cannot come back.
    """

    def test_unverified_is_not_sustainable(self):
        """The conservative half, and it must stay: 'we could not tell' is not 'yes'."""
        from HotGauge.power.clock_search import is_sustainable, reason_unsustainable
        r = {'peak_K': 300.0, 'unconverged': True}
        assert is_sustainable(r, thermal_limit_K=400.0) is False
        assert reason_unsustainable(r, thermal_limit_K=400.0) == 'unverified'

    def test_a_converged_result_is_sustainable_regardless_of_how_many_probes_failed(self):
        """The other half. A result carrying no unconverged flag is an answer, even though the
        search that produced it visited unstable states to get there -- which is what the
        envelope descent is FOR."""
        from HotGauge.power.clock_search import is_sustainable
        r = {'peak_K': 350.0, 'unconverged': False, 'diverged': False}
        assert is_sustainable(r, thermal_limit_K=400.0) is True

    def test_the_driver_contract_result_unconverged_exists_on_mr_results(self):
        """clock_headroom and mr_comparison both key off this field. If run_mr_clipping stopped
        emitting it, both would silently fall back to counting probes again."""
        import inspect
        from HotGauge.thermal import microrefrigeration
        src = inspect.getsource(microrefrigeration)
        assert "'result_unconverged'" in src, (
            'run_mr_clipping must publish result_unconverged: it is the verdict on the RESULT '
            'rather than on the probes, and two drivers depend on it')

    def test_both_drivers_use_the_result_verdict_not_the_probe_counter(self):
        """The asymmetry that caused this bug was between two files, so the test spans both."""
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        ex = os.path.join(here, '..', '..', '..', 'examples')
        if not os.path.isdir(ex):
            pytest.skip('examples/ not present')
        for fname in ('clock_headroom.py', 'mr_comparison.py'):
            src = open(os.path.join(ex, fname)).read()
            assert "'result_unconverged' in res" in src, (
                '{} must take its unconverged verdict from the MR result, not from the '
                'accumulated probe counter'.format(fname))
