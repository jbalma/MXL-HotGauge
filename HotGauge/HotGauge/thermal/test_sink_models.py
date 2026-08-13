"""Tests for the parameterized sink models (HotGauge.thermal.sink_models).

Pure Python -- no 3D-ICE binary needed. The physics checks are anchored on values that can be
verified by hand from the 3D-ICE source (HTC units) and the HS483 Modelica model (the
convection correlation), so a regression here means a real change in meaning, not just a
changed number.
"""
import os

import pytest

from HotGauge.thermal.sink_models import (UM2_PER_M2, htc_si_to_3dice, htc_3dice_to_si,
                                          thermal_resistance_to_htc_si, ConstantHTCSink,
                                          ThermalResistanceSink, HS483AirSink,
                                          render_stack_with_sink, fit_area_ratio)


# ---------------------------------------------------------------------------
# Unit conversions -- the trap that makes an HTC look absurd
# ---------------------------------------------------------------------------
def test_htc_unit_roundtrip():
    assert htc_3dice_to_si(1.0e-7) == pytest.approx(1.0e5)
    assert htc_si_to_3dice(1.0e5) == pytest.approx(1.0e-7)
    assert htc_si_to_3dice(htc_3dice_to_si(3.7e-8)) == pytest.approx(3.7e-8)


def test_stock_skylake_htc_is_about_1_K_per_W_over_a_10mm2_die():
    """1e-7 W/(um^2 K) looks huge until you reference it to the die area."""
    area_m2 = 10.0e-6          # 10 mm^2
    h_si = htc_3dice_to_si(1.0e-7)
    r_th = 1.0 / (h_si * area_m2)
    assert r_th == pytest.approx(1.0, rel=1e-9)


def test_thermal_resistance_conversion_is_inverse_of_r_th():
    area_m2 = 20.0e-6
    h = thermal_resistance_to_htc_si(0.25, area_m2)
    assert 1.0 / (h * area_m2) == pytest.approx(0.25)


@pytest.mark.parametrize('bad_r,bad_a', [(0.0, 1e-5), (-1.0, 1e-5), (0.3, 0.0), (0.3, -1e-5)])
def test_thermal_resistance_rejects_nonpositive(bad_r, bad_a):
    with pytest.raises(ValueError):
        thermal_resistance_to_htc_si(bad_r, bad_a)


# ---------------------------------------------------------------------------
# ThermalResistanceSink -- the power-regime workhorse
# ---------------------------------------------------------------------------
def test_thermal_resistance_sink_reports_requested_r_th():
    area_m2 = 15.0e-6
    sink = ThermalResistanceSink(0.05, area_m2)
    assert sink.thermal_resistance(area_m2) == pytest.approx(0.05)
    assert sink.htc_3dice() == pytest.approx(htc_si_to_3dice(sink.htc_si()))


def test_better_cooler_means_higher_htc():
    area_m2 = 15.0e-6
    server_liquid = ThermalResistanceSink(0.03, area_m2)
    desktop_air = ThermalResistanceSink(0.8, area_m2)
    assert server_liquid.htc_si() > desktop_air.htc_si()


def test_parasitic_power_distinguishes_zero_from_unmodelled():
    unknown = ThermalResistanceSink(0.1, 1e-5)
    known = ThermalResistanceSink(0.1, 1e-5, parasitic_power=12.0)
    assert unknown.parasitic_power_W() == 0.0 and unknown.parasitic_known is False
    assert known.parasitic_power_W() == 12.0 and known.parasitic_known is True
    # An efficiency study must be able to see the difference in the human-readable form.
    assert 'parasitic power unmodelled' in unknown.describe()
    assert 'parasitic power unmodelled' not in known.describe()


def test_describe_flags_uncalibrated():
    assert 'UNCALIBRATED' in ConstantHTCSink(1e5).describe()
    assert 'UNCALIBRATED' not in ConstantHTCSink(1e5, calibrated=True).describe()


# ---------------------------------------------------------------------------
# HS483 -- correlation taken verbatim from the Modelica model
# ---------------------------------------------------------------------------
def test_fin_htc_matches_modelica_correlation_by_hand():
    # htc = 0.8793 * (11.8 + 9.33*v - 1.09*v^2); at v = 1.0 m/s
    expected = 0.8793 * (11.8 + 9.33 * 1.0 - 1.09 * 1.0)
    assert HS483AirSink.fin_htc_si(1.0) == pytest.approx(expected)


def test_natural_convection_is_the_datasheet_constant():
    assert HS483AirSink.fin_htc_si(0.0) == pytest.approx(2.8)
    assert HS483AirSink.rpm_to_velocity(0.0) == 0.0


def test_fin_htc_increases_with_fan_speed_across_the_valid_range():
    htcs = [HS483AirSink.fin_htc_si(HS483AirSink.rpm_to_velocity(r))
            for r in (1500, 3000, 4500, 6000)]
    assert htcs == sorted(htcs)


def test_rpm_endpoints_map_to_documented_velocities():
    assert HS483AirSink.rpm_to_velocity(1500) == pytest.approx(1.0)
    assert HS483AirSink.rpm_to_velocity(6000) == pytest.approx(4.1)


def test_rpm_outside_validated_range_is_rejected_unless_forced():
    with pytest.raises(ValueError):
        HS483AirSink(900)
    # Explicit opt-in still works, for sensitivity studies that know they are extrapolating.
    assert HS483AirSink(900, strict=False).velocity_m_s < 1.0


def test_power_validity_envelope_flags_real_workloads():
    sink = HS483AirSink(6000)
    assert sink.power_within_validity(35.0) is True
    # Our 7nm linpack trace (~49 W) is already outside what the FMU was validated for.
    assert sink.power_within_validity(49.0) is False


def test_area_ratio_scales_the_die_referenced_htc():
    base = HS483AirSink(6000, area_ratio=1.0)
    scaled = HS483AirSink(6000, area_ratio=250.0)
    assert scaled.htc_si() == pytest.approx(base.htc_si() * 250.0)


def test_fit_area_ratio_inverts_the_surrogate():
    """Calibrating on a measured HTC must reproduce that HTC exactly."""
    measured = 4.2e4
    ratio = fit_area_ratio(measured, 6000)
    assert HS483AirSink(6000, area_ratio=ratio).htc_si() == pytest.approx(measured)


# ---------------------------------------------------------------------------
# Stack rendering
# ---------------------------------------------------------------------------
_CONV_STACK = ('top heat sink :\n'
               '   heat transfer coefficient 1.0e-7 ; // TODO: tune\n'
               '   temperature 303.15 ; // ambient\n'
               'dimensions :\n   chip length 100, width 100 ;\n')


# ---------------------------------------------------------------------------
# PumpedSink -- the fan side of the hybrid split
# ---------------------------------------------------------------------------
def test_fan_off_is_natural_convection_and_costs_nothing():
    from HotGauge.thermal.sink_models import PumpedSink
    s = PumpedSink(0.0, 28.39e-6, R0=60.0, R_inf=15.0)
    assert s.r_area() == pytest.approx(60.0)      # R0 at u=0
    assert s.parasitic_power_W() == 0.0


def test_more_fan_lowers_resistance_toward_the_asymptote_and_costs_more():
    from HotGauge.thermal.sink_models import PumpedSink
    area = 28.39e-6
    lo, hi = PumpedSink(0.5, area), PumpedSink(4.0, area)
    assert hi.r_area() < lo.r_area()
    assert hi.r_area() > hi.R_inf                 # never better than the asymptote
    assert hi.parasitic_power_W() > lo.parasitic_power_W()


def test_fan_returns_diminish_while_cost_accelerates():
    """The reason a hybrid split exists: fan watts get worse, MR watts do not."""
    from HotGauge.thermal.sink_models import PumpedSink
    area = 28.39e-6
    us = [1.0, 2.0, 4.0]
    r = [PumpedSink(u, area).r_area() for u in us]
    p = [PumpedSink(u, area).parasitic_power_W() for u in us]
    gain1, gain2 = r[0] - r[1], r[1] - r[2]
    cost1, cost2 = p[1] - p[0], p[2] - p[1]
    assert gain2 < gain1        # diminishing thermal returns
    assert cost2 > cost1        # accelerating power cost


def test_pumped_sink_reports_its_own_power_unlike_a_bare_r_th():
    from HotGauge.thermal.sink_models import PumpedSink
    assert PumpedSink(2.0, 28.39e-6).parasitic_known is True
    assert ThermalResistanceSink(0.3, 28.39e-6).parasitic_known is False


def test_for_power_budget_picks_the_strongest_affordable_setting():
    from HotGauge.thermal.sink_models import PumpedSink
    area = 28.39e-6
    s = PumpedSink.for_power_budget(5.0, area)
    assert s is not None
    assert s.parasitic_power_W() <= 5.0
    bigger = PumpedSink(s.u * 1.5 + 0.1, area)
    assert bigger.parasitic_power_W() > 5.0


def test_for_power_budget_rejects_negative():
    from HotGauge.thermal.sink_models import PumpedSink
    with pytest.raises(ValueError):
        PumpedSink.for_power_budget(-1.0, 28.39e-6)


def test_pumped_sink_rejects_bad_resistance_ordering():
    from HotGauge.thermal.sink_models import PumpedSink
    with pytest.raises(ValueError):
        PumpedSink(1.0, 28.39e-6, R0=10.0, R_inf=20.0)


# ---------------------------------------------------------------------------
# FanCoolingModel -- calibrated against docs/MXL-Photonic-Cooling-Power-Analysis.xlsx
# ---------------------------------------------------------------------------
def test_reproduces_the_mxl_fan_table():
    from HotGauge.thermal.sink_models import FanCoolingModel
    f = FanCoolingModel()
    # dT=50 K row: 3.51 CFM and 2.07 W for a 100 W chip
    assert f.cfm_for(100.0, 50.0) == pytest.approx(3.51, rel=2e-3)
    assert f.fan_power_for(100.0, 50.0) == pytest.approx(2.07, rel=5e-3)
    # the "dT=10K" row is really ~15 K of air rise (11.71 CFM, 6.91 W)
    assert f.cfm_for(100.0, 15.0) == pytest.approx(11.71, rel=2e-3)
    assert f.fan_power_for(100.0, 15.0) == pytest.approx(6.91, rel=5e-3)


def test_fan_power_is_linear_in_heat_and_inverse_in_dt():
    from HotGauge.thermal.sink_models import FanCoolingModel
    f = FanCoolingModel()
    assert f.fan_power_for(1000.0, 15.0) == pytest.approx(10 * f.fan_power_for(100.0, 15.0))
    # Halving the allowed air rise doubles the fan power -- the lever in the hybrid trade.
    assert f.fan_power_for(100.0, 25.0) == pytest.approx(2 * f.fan_power_for(100.0, 50.0))


def test_budget_inverse_roundtrips():
    from HotGauge.thermal.sink_models import FanCoolingModel
    f = FanCoolingModel()
    dt = f.dt_air_for_budget(100.0, 6.91)
    assert dt == pytest.approx(15.0, rel=5e-3)
    assert f.fan_power_for(100.0, dt) == pytest.approx(6.91, rel=5e-3)


def test_zero_fan_budget_means_no_forced_airflow():
    from HotGauge.thermal.sink_models import FanCoolingModel
    assert FanCoolingModel().dt_air_for_budget(100.0, 0.0) == float('inf')


def test_hotter_air_raises_the_effective_ambient():
    """Cheap fan power is paid for in temperature margin -- that is the whole trade."""
    from HotGauge.thermal.sink_models import FanCoolingModel
    f = FanCoolingModel(inlet_K=303.15)
    assert f.effective_ambient_K(50.0) > f.effective_ambient_K(15.0)
    assert f.effective_ambient_K(0.0) == pytest.approx(303.15)


def test_fan_model_rejects_nonsense():
    from HotGauge.thermal.sink_models import FanCoolingModel
    f = FanCoolingModel()
    with pytest.raises(ValueError):
        f.cfm_for(100.0, 0.0)
    with pytest.raises(ValueError):
        f.cfm_for(-1.0, 10.0)


def test_render_ignores_commented_out_variants(tmp_path):
    """skylake.stk ships commented mobile variants right below the active lines."""
    base = tmp_path / 'commented.stk'
    base.write_text('top heat sink :\n'
                    '   heat transfer coefficient 1.0e-7 ; // desktop\n'
                    '   // heat transfer coefficient 2.0e-7 ; // mobile\n'
                    '   temperature 303.15 ; // desktop\n'
                    '   // temperature 314.15 ; // mobile\n')
    out = render_stack_with_sink(str(base), ConstantHTCSink(5.0e4, ambient_K=298.15),
                                 str(tmp_path / 'o.stk'))
    text = open(out).read()
    # The commented variants must be left exactly as they were.
    assert '// heat transfer coefficient 2.0e-7 ;' in text
    assert '// temperature 314.15 ;' in text
    assert '5.000000e-08' in text and '298.150000' in text


def test_render_substitutes_htc_and_ambient(tmp_path):
    base = tmp_path / 'base.stk'
    base.write_text(_CONV_STACK)
    sink = ConstantHTCSink(5.0e4, ambient_K=298.15)
    out = render_stack_with_sink(str(base), sink, str(tmp_path / 'out.stk'))
    text = open(out).read()
    assert '5.000000e-08' in text          # 5e4 W/(m^2 K) -> 5e-8 W/(um^2 K)
    assert '298.150000' in text
    assert '1.0e-7' not in text
    # Everything else must survive untouched.
    assert 'chip length 100, width 100' in text


def test_render_rejects_pluggable_stack(tmp_path):
    """A pluggable stack has no HTC line -- catch it here, not after a wasted solve."""
    base = tmp_path / 'plug.stk'
    base.write_text('top pluggable heat sink :\n   spreader length 30000 ;\n'
                    '   plugin "x.so", "y" ;\ntemperature 303.15 ;\n')
    with pytest.raises(ValueError):
        render_stack_with_sink(str(base), ConstantHTCSink(1e5), str(tmp_path / 'o.stk'))


def test_render_roundtrips_through_the_real_skylake_template(tmp_path):
    from HotGauge.thermal import get_stack_template
    base = get_stack_template('skylake')
    if not os.path.isfile(base):
        pytest.skip('shipped skylake stack template not present')
    sink = ThermalResistanceSink(0.2, 12.0e-6, ambient_K=300.0)
    out = render_stack_with_sink(base, sink, str(tmp_path / 'skylake_rendered.stk'))
    text = open(out).read()
    assert '{:.6e}'.format(sink.htc_3dice()) in text
    assert '300.000000' in text
