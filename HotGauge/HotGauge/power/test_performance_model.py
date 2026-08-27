"""Tests for the temperature -> performance model (Goal 1b). Pure Python, no 3D-ICE."""
import numpy as np
import pytest

from HotGauge.power.performance_model import (FMaxModel, core_fmax, throttled_fmax,
                                              voltage_for_frequency, dynamic_power_scale,
                                              performance_summary, DEFAULT_TREF_PERF_K)


# ---------------------------------------------------------------------------
# f_max(T)
# ---------------------------------------------------------------------------
def test_fmax_is_unity_at_reference():
    m = FMaxModel.linear_derate(0.001, T_ref_K=DEFAULT_TREF_PERF_K)
    assert m.relative_fmax(DEFAULT_TREF_PERF_K) == pytest.approx(1.0)


def test_fmax_falls_with_temperature_and_rises_below_reference():
    m = FMaxModel.linear_derate(0.001, T_ref_K=373.15)
    assert m.relative_fmax(393.15) == pytest.approx(1.0 - 0.001 * 20)
    # 20 K cooler than reference => faster, which is the whole point of cooling
    assert m.relative_fmax(353.15) == pytest.approx(1.0 + 0.001 * 20)


def test_fmax_is_floored_so_extreme_temps_cannot_go_negative():
    m = FMaxModel.linear_derate(0.01, T_ref_K=373.15, floor=0.1)
    assert m.relative_fmax(1000.0) == pytest.approx(0.1)


def test_negative_derate_rejected():
    with pytest.raises(ValueError):
        FMaxModel.linear_derate(-0.001)


def test_from_table_interpolates_and_clamps():
    m = FMaxModel.from_table([300.0, 400.0], [1.2, 0.8])
    assert m.relative_fmax(350.0) == pytest.approx(1.0)
    assert m.relative_fmax(250.0) == pytest.approx(1.2)   # clamped low
    assert m.relative_fmax(500.0) == pytest.approx(0.8)   # clamped high


def test_calibration_flag_is_explicit():
    assert FMaxModel.linear_derate().calibrated is False
    assert FMaxModel.from_table([300.0, 400.0], [1.0, 0.9]).calibrated is True
    assert 'UNCALIBRATED' in repr(FMaxModel.linear_derate())


# ---------------------------------------------------------------------------
# The hottest block governs the core
# ---------------------------------------------------------------------------
def test_core_fmax_uses_hottest_block_not_average():
    m = FMaxModel.linear_derate(0.001, T_ref_K=373.15)
    cool_with_one_hotspot = [330.0, 330.0, 330.0, 423.15]
    f, t_hot = core_fmax(cool_with_one_hotspot, m, f_nominal_GHz=4.0)
    assert t_hot == pytest.approx(423.15)
    assert f == pytest.approx(4.0 * (1.0 - 0.001 * 50))
    # Averaging would have given a much rosier answer -- guard against a regression to mean.
    mean_based = 4.0 * m.relative_fmax(np.mean(cool_with_one_hotspot))
    assert f < mean_based


def test_core_fmax_ignores_out_of_die_zero_kelvin_entries():
    """3D-ICE emits 0 K outside the die layer; those must not become a fast, cold core."""
    m = FMaxModel.linear_derate(0.001)
    f, t_hot = core_fmax([0.0, 0.0, 380.0], m, f_nominal_GHz=4.0)
    assert t_hot == pytest.approx(380.0)


def test_core_fmax_errors_when_nothing_is_above_the_floor():
    m = FMaxModel.linear_derate(0.001)
    with pytest.raises(ValueError):
        core_fmax([0.0, 0.0], m)


# ---------------------------------------------------------------------------
# Throttling cliff
# ---------------------------------------------------------------------------
def test_no_throttle_below_trip_point():
    m = FMaxModel.linear_derate(0.001, T_ref_K=373.15)
    f, active = throttled_fmax(360.0, m, 4.0, throttle_K=373.15)
    assert active is False
    assert f == pytest.approx(4.0 * m.relative_fmax(360.0))


def test_throttle_is_much_steeper_than_guardband():
    m = FMaxModel.linear_derate(0.001, T_ref_K=373.15)
    below, _ = throttled_fmax(373.15, m, 4.0, throttle_K=373.15)
    above, active = throttled_fmax(383.15, m, 4.0, throttle_K=373.15,
                                   throttle_slope_per_K=0.02)
    assert active is True
    # 10 K past the trip point costs ~20% throttle, vs ~1% from the guardband alone.
    assert above == pytest.approx(below * m.relative_fmax(383.15)
                                  / m.relative_fmax(373.15) * 0.8, rel=1e-6)
    assert above < below * 0.85


def test_throttle_has_a_floor():
    m = FMaxModel.linear_derate(0.0)
    f, _ = throttled_fmax(1000.0, m, 4.0, throttle_K=373.15, floor_frac=0.3)
    assert f == pytest.approx(4.0 * 0.3)


# ---------------------------------------------------------------------------
# V/F coupling -- recovered frequency is not free
# ---------------------------------------------------------------------------
def test_voltage_increases_with_frequency():
    v_lo, _ = voltage_for_frequency(2.0)
    v_hi, _ = voltage_for_frequency(4.8)
    assert v_hi > v_lo


def test_voltage_clamps_outside_table_instead_of_raising():
    v, clamped = voltage_for_frequency(0.1)
    assert clamped is True and v == pytest.approx(0.6)
    v, clamped = voltage_for_frequency(99.0)
    assert clamped is True and v == pytest.approx(1.4)


def test_dynamic_power_scale_is_unity_at_reference():
    assert dynamic_power_scale(4.1, 4.1) == pytest.approx(1.0)


def test_dynamic_power_grows_superlinearly_with_frequency():
    """V^2*f means a 10% clock bump costs more than 10% dynamic power."""
    scale = dynamic_power_scale(4.51, 4.1)
    assert scale > 1.1


def test_dynamic_power_scale_rejects_bad_reference():
    with pytest.raises(ValueError):
        dynamic_power_scale(4.0, 0.0)


# ---------------------------------------------------------------------------
# Summary bundle
# ---------------------------------------------------------------------------
def test_summary_reports_perf_per_watt_including_cooling_cost():
    m = FMaxModel.linear_derate(0.001, T_ref_K=373.15)
    hot = performance_summary([360.0], m, f_nominal_GHz=4.0, compute_power_W=100.0,
                              cooling_power_W=25.0)
    assert hot['total_power_W'] == pytest.approx(125.0)
    assert hot['perf_per_W'] == pytest.approx(hot['f_effective_GHz'] / 125.0)


def test_summary_cooler_is_faster():
    m = FMaxModel.linear_derate(0.001, T_ref_K=373.15)
    warm = performance_summary([390.0], m, f_nominal_GHz=4.0)
    cool = performance_summary([350.0], m, f_nominal_GHz=4.0)
    assert cool['f_effective_GHz'] > warm['f_effective_GHz']
    assert cool['rel_perf'] > warm['rel_perf']


def test_summary_propagates_calibration_flag():
    assert performance_summary([350.0], FMaxModel.linear_derate())['calibrated'] is False
    assert performance_summary([350.0],
                               FMaxModel.from_table([300., 400.], [1., .9]))['calibrated'] is True


def test_cooling_that_clears_the_trip_point_beats_the_guardband_gain():
    """The clipping argument: crossing back under the trip point is worth far more than
    the same number of Kelvin spent purely on guardband."""
    m = FMaxModel.linear_derate(0.001, T_ref_K=373.15)
    throttled = performance_summary([383.15], m, f_nominal_GHz=4.0, throttle_K=373.15)
    just_under = performance_summary([373.15], m, f_nominal_GHz=4.0, throttle_K=373.15)
    assert throttled['throttling'] is True and just_under['throttling'] is False
    gain_crossing = just_under['f_effective_GHz'] - throttled['f_effective_GHz']
    # The same 10 K spent entirely below the trip point buys only the guardband slope.
    a = performance_summary([363.15], m, f_nominal_GHz=4.0, throttle_K=373.15)
    gain_below = a['f_effective_GHz'] - just_under['f_effective_GHz']
    assert gain_crossing > 5 * gain_below


# ---------------------------------------------------------------------------
# The alpha-power V/F fit, and why alpha is constrained
# ---------------------------------------------------------------------------
class TestVFAlphaPowerFit:
    """alpha < 1 is outside the model's own physical range, and it showed.

    Gonzalez, Gordon & Horowitz (JSSC 32(8), 1997) bound alpha between 1 (complete velocity
    saturation) and 2 (none). The shipped fit had alpha = 0.949, and the visible consequence was
    a curve that TURNS OVER: f(V) = k(V-Vth)^alpha / V has an interior maximum at Vth/(1-alpha)
    only when alpha < 1, which is where the reported "6.43 GHz ceiling at 9.40 V" came from.
    """

    def test_alpha_is_inside_the_physical_range(self):
        from HotGauge.power.performance_model import VF_ALPHA_POWER_FIT
        assert 1.0 <= VF_ALPHA_POWER_FIT['alpha'] <= 2.0

    def test_the_corrected_curve_does_not_turn_over(self):
        """Monotonic in V over any range anyone could apply to a part, and well past it."""
        from HotGauge.power.performance_model import frequency_for_voltage, VF_ALPHA_POWER_FIT
        vs = np.linspace(VF_ALPHA_POWER_FIT['Vth'] + 0.01, 12.0, 4000)
        f = np.array([frequency_for_voltage(v) for v in vs])
        assert np.all(np.diff(f) > 0), 'corrected V/F fit is not monotonic'

    def test_the_superseded_fit_is_kept_and_still_reproduces_its_artefact(self):
        """Provenance, not nostalgia: the withdrawn number must be reproducible on demand."""
        from HotGauge.power.performance_model import (VF_ALPHA_POWER_FIT_UNCONSTRAINED as U,
                                                      frequency_for_voltage,
                                                      voltage_for_frequency_extrapolated)
        assert U['alpha'] < 1.0 and U['alpha_constrained'] is False
        v_star = U['Vth'] / (1.0 - U['alpha'])
        assert v_star == pytest.approx(9.40, abs=0.02)
        assert frequency_for_voltage(v_star, U) == pytest.approx(6.43, abs=0.02)
        # and the documented supply demands
        assert voltage_for_frequency_extrapolated(5.5, U) == pytest.approx(1.82, abs=0.01)
        assert voltage_for_frequency_extrapolated(6.0, U) == pytest.approx(2.74, abs=0.01)

    def test_6_5_GHz_was_unreachable_only_because_of_the_turnover(self):
        """The old fit called 6.5 GHz impossible at ANY voltage. That was the artefact talking.

        The corrected curve reaches it -- at 3.34 V, which is oxide breakdown. Same verdict,
        stated in units that mean something instead of as a property of the exponent.
        """
        from HotGauge.power.performance_model import (VF_ALPHA_POWER_FIT_UNCONSTRAINED as U,
                                                      voltage_for_frequency_extrapolated)
        with pytest.raises(ValueError):
            voltage_for_frequency_extrapolated(6.5, U)
        assert voltage_for_frequency_extrapolated(6.5) == pytest.approx(3.34, abs=0.02)

    def test_the_table_still_ends_at_a_device_limit_not_a_data_limit(self):
        """The correction must NOT be read as 'the 5 GHz ceiling was wrong'. It was right.

        5.0 GHz needs ~1.38 V, the top of the table; 5.5 needs 1.71 and 6.0 needs 2.26. A
        vf_clamped verdict stays a RESULT -- voltage-limited, not thermally limited.
        """
        from HotGauge.power.performance_model import (voltage_for_frequency_extrapolated,
                                                      VF_MAX_VOLTAGE)
        assert voltage_for_frequency_extrapolated(5.0) <= VF_MAX_VOLTAGE
        assert voltage_for_frequency_extrapolated(5.5) > VF_MAX_VOLTAGE
        assert voltage_for_frequency_extrapolated(6.0) > 2.0

    def test_the_fit_is_worse_than_the_free_one_and_that_is_the_finding(self):
        """The constraint BINDS: alpha lands exactly on 1.0, and the fit degrades to match.

        If the table were a device delay curve, the physical range would contain it. It does not
        -- which is the evidence that VF_PAIRS is a product BIN table (reliability-limited
        guardbanding at the top of the range), not a transistor's V/F curve.
        """
        from HotGauge.power.performance_model import (VF_ALPHA_POWER_FIT as F,
                                                      VF_ALPHA_POWER_FIT_UNCONSTRAINED as U)
        assert F['alpha'] == pytest.approx(1.0), 'the alpha >= 1 bound should be active'
        assert F['alpha_bound_binds'] is True
        assert F['rms_error_frac'] > U['rms_error_frac']
        assert F['rms_error_frac'] < 0.01, 'still a good fit -- under 1% RMS'
