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
                                          render_stack_with_sink, fit_area_ratio, SpreadingSink,
                                          external_r_for_spreading_total)


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


# ---------------------------------------------------------------------------
# The overhanging base
# ---------------------------------------------------------------------------
class TestSpreadingSink:
    """The cold plate as a boundary term rather than a die-width column of metal."""

    def _sink(self, r_th, die_mm2):
        return ThermalResistanceSink(r_th, die_mm2 * 1e-6)

    def test_it_wraps_and_reports_the_underlying_convection(self):
        sp = SpreadingSink(self._sink(0.05, 300.0), 300.0, base_area_mm2=1825.0)
        assert sp.total_resistance_K_per_W() > 0.05, 'spreading can only add resistance'
        assert sp.htc_si() == pytest.approx(
            1.0 / (sp.total_resistance_K_per_W() * 300.0 * 1e-6))

    def test_a_small_die_is_penalised_but_not_by_the_area_ratio(self):
        small = SpreadingSink(self._sink(0.05, 91.0), 91.0, base_area_mm2=1825.0)
        large = SpreadingSink(self._sink(0.05, 826.0), 826.0, base_area_mm2=1825.0)
        r_small = small.total_resistance_K_per_W()
        r_large = large.total_resistance_K_per_W()
        assert r_small > r_large
        assert r_small / r_large < 0.6 * (826.0 / 91.0)

    def test_series_layers_act_over_the_base_not_the_die(self):
        """30 um of grease is 0.082 K/W across a 91 mm^2 die and 0.004 across an 1825 mm^2 plate.
        Moving it out of the stack is only correct if it is then charged over the base."""
        grease = [('GREASE', 0.030, 4.0)]
        sp = SpreadingSink(self._sink(0.05, 91.0), 91.0, base_area_mm2=1825.0,
                           series_above_base=grease)
        expect = 0.030e-3 / (4.0 * 1825.0e-6)
        assert sp.series_resistance_K_per_W() == pytest.approx(expect, rel=1e-9)
        die_referenced = 0.030e-3 / (4.0 * 91.0e-6)
        assert sp.series_resistance_K_per_W() < 0.1 * die_referenced

    def test_series_layers_increase_the_total(self):
        bare = SpreadingSink(self._sink(0.05, 91.0), 91.0, base_area_mm2=1825.0)
        with_series = SpreadingSink(self._sink(0.05, 91.0), 91.0, base_area_mm2=1825.0,
                                    series_above_base=[('SINK', 2.0, 300.0)])
        assert with_series.total_resistance_K_per_W() > bare.total_resistance_K_per_W()

    def test_it_takes_the_base_from_a_cooling_spec_when_there_is_one(self):
        """A spec's base is sized by cooler class and validated against published parts; the
        fixed footprint is only the fallback."""
        class _Spec(object):
            base_area_mm2 = 4321.0

        class _Sink(object):
            spec = _Spec()
            ambient_K = 300.0
            label = 'x'
            r_th_K_per_W = 0.05

        assert SpreadingSink(_Sink(), 91.0).base_area_mm2 == pytest.approx(4321.0)

    def test_the_package_no_longer_exceeds_the_published_budget(self):
        """The Ryzen failure, stated as arithmetic.

        As a die-width column the lidded package came to 0.4675 K/W against a published
        junction-to-ambient of 0.3962 -- the package alone exceeded the whole budget, which is
        impossible and is why the gate could not pass. With the lid carrying its real overhang it
        is 0.31, leaving a plausible share for the cooler.
        """
        from HotGauge.thermal.die_stack import StackSpec
        from HotGauge.thermal.cooling_spec import COOLER_CLASSES
        import math as _math

        die, published = 71.0, 0.3962
        base = (_math.sqrt(die) * COOLER_CLASSES['desktop_tower']) ** 2
        old = StackSpec(package='lidded').resistance_budget(die)['total_K_per_W']
        new_spec = StackSpec(package='lidded', package_in_boundary=True)
        t, k = new_spec.boundary_base()
        sp = SpreadingSink(ThermalResistanceSink(1e-6, die * 1e-6), die, base_area_mm2=base,
                           base_thickness_mm=t, base_k_W_mK=k,
                           series_above_base=new_spec.boundary_series_layers())
        new = new_spec.resistance_budget(die)['total_K_per_W'] + sp.total_resistance_K_per_W()

        assert old > published, 'the old package really did exceed the whole published budget'
        assert new < published, 'the new one must leave something for the cooler'
        assert (published - new) / published > 0.1, 'and a plausible share, not a sliver'


class TestExternalRForSpreadingTotal:
    """Inverting the boundary: what a cooler must supply for the total to come out right.

    The gate works backwards from a published junction-to-ambient figure, so it needs this. With
    the base in the boundary the remainder after the stack is no longer the convective term alone
    -- it also holds the spreading and the layers above the base -- and solving the cooler
    directly against it would demand a cooler better than the target by exactly the spreading.
    """

    GEOM = dict(die_area_mm2=71.0, base_area_mm2=1825.0, base_thickness_mm=3.0,
                base_k_W_mK=390.0)

    def test_it_round_trips(self):
        target = 0.2366
        r = external_r_for_spreading_total(target, **self.GEOM)
        assert r is not None
        back = SpreadingSink(ThermalResistanceSink(r, self.GEOM['die_area_mm2'] * 1e-6),
                             self.GEOM['die_area_mm2'],
                             base_area_mm2=self.GEOM['base_area_mm2'],
                             base_thickness_mm=self.GEOM['base_thickness_mm'],
                             base_k_W_mK=self.GEOM['base_k_W_mK']).total_resistance_K_per_W()
        assert back == pytest.approx(target, rel=1e-6)

    def test_a_target_below_the_spreading_floor_is_infeasible_not_negative(self):
        """Returning a negative resistance would silently flatter the cooler. None is the answer."""
        assert external_r_for_spreading_total(1e-4, **self.GEOM) is None

    def test_the_answer_is_below_the_target(self):
        """Spreading is part of the budget, so the cooler must be better than the total."""
        target = 0.2366
        r = external_r_for_spreading_total(target, **self.GEOM)
        assert 0.0 < r < target

    def test_series_layers_tighten_the_requirement(self):
        target = 0.2366
        bare = external_r_for_spreading_total(target, **self.GEOM)
        with_series = external_r_for_spreading_total(
            target, series_above_base=[('SINK', 2.0, 300.0)], **self.GEOM)
        assert with_series < bare


class TestSpreadingSinkForStack:
    """The join between the overhang physics and the stack that implies it.

    Both halves of P0.4 existed and were tested for a day before anything connected them, so
    every study driver went on solving against a 2 mm slab at the die footprint. These pin the
    connection and, more importantly, the two ways of getting it wrong -- both of which are
    silent: a double-counted base just makes every part run hot, and a template name has no base
    geometry to read at all.
    """

    ARRAY = 'spec:package=direct_die,mr=GAAS,src=200,cell=50,sink_in_stack=0'
    SLAB = 'spec:package=direct_die,mr=GAAS,src=200,cell=50'

    def _sink(self, r=0.12):
        from HotGauge.thermal.sink_models import ThermalResistanceSink
        return ThermalResistanceSink(r, 53.0e-6)

    def test_it_builds_from_a_stack_with_the_slab_removed(self):
        from HotGauge.thermal.sink_models import spreading_sink_for_stack, SpreadingSink
        s = spreading_sink_for_stack(self.ARRAY, self._sink(), 53.0)
        assert isinstance(s, SpreadingSink)
        assert s.total_resistance_K_per_W() > 0

    def test_a_stack_that_still_has_its_slab_is_refused(self):
        """Double-counting the base does not error downstream -- it just runs hot."""
        from HotGauge.thermal.sink_models import spreading_sink_for_stack
        with pytest.raises(ValueError, match='TWICE'):
            spreading_sink_for_stack(self.SLAB, self._sink(), 53.0)

    def test_a_template_name_is_refused_with_the_fix_named(self):
        from HotGauge.thermal.sink_models import spreading_sink_for_stack
        with pytest.raises(ValueError, match='sink_in_stack=0'):
            spreading_sink_for_stack('skylake', self._sink(), 53.0)

    def test_the_base_geometry_comes_from_the_spec(self):
        from HotGauge.thermal.die_stack import parse_spec_string
        from HotGauge.thermal.sink_models import spreading_sink_for_stack
        spec = parse_spec_string(self.ARRAY)
        t_mm, k = spec.boundary_base()
        s = spreading_sink_for_stack(self.ARRAY, self._sink(), 53.0)
        assert s.base_thickness_mm == pytest.approx(t_mm)
        assert s.base_k_W_mK == pytest.approx(k)

    def test_it_breaks_the_one_over_area_scaling(self):
        """The whole reason the overhang exists. A slab in the stack gives 1/area exactly."""
        from HotGauge.thermal.sink_models import spreading_sink_for_stack, ThermalResistanceSink
        rs = []
        for area in (53.0, 826.0):
            sink = ThermalResistanceSink(0.12, area * 1e-6)
            rs.append(spreading_sink_for_stack(self.ARRAY, sink, area).total_resistance_K_per_W())
        area_ratio = 826.0 / 53.0                       # 15.6x
        assert rs[0] / rs[1] < 0.35 * area_ratio        # nothing like 1/area

    def test_the_base_is_a_fixed_area_not_a_ratio_of_the_die(self):
        """A ratio would reintroduce 1/area, which is the failure being fixed."""
        from HotGauge.thermal.sink_models import spreading_sink_for_stack
        small = spreading_sink_for_stack(self.ARRAY, self._sink(), 53.0)
        big = spreading_sink_for_stack(self.ARRAY, self._sink(), 200.0)
        assert small.base_area_mm2 == pytest.approx(big.base_area_mm2)

    def test_a_die_larger_than_the_plate_still_gets_a_sane_base(self):
        """Clamped to at least the die: a base smaller than its own source is impossible."""
        from HotGauge.thermal.sink_models import spreading_sink_for_stack
        s = spreading_sink_for_stack(self.ARRAY, self._sink(), 4000.0)
        assert s.base_area_mm2 >= 4000.0

    def test_the_lidded_gate_path_uses_the_lid_as_the_base(self):
        """Gate-only: on a lidded part the dominant spreader is the IHS, not the cold plate."""
        from HotGauge.thermal.sink_models import spreading_sink_for_stack
        from HotGauge.thermal.die_stack import parse_spec_string
        name = 'spec:package=lidded,sink_in_stack=0,package_in_boundary=1'
        spec = parse_spec_string(name)
        t_mm, k = spec.boundary_base()
        s = spreading_sink_for_stack(name, self._sink(), 91.0)
        assert s.base_thickness_mm == pytest.approx(t_mm)
        # ...and the grease and cold plate move above the base, acting over ITS area.
        assert [n for n, _, _ in s.series_above_base] == ['GREASE', 'SINK']


class TestSpreadingReproducesTheOverhangEvidence:
    """The wired path must reproduce docs/evidence/direct_die_overhang.json to the digit.

    This is the strongest test available for the P0.4 integration, because the evidence was
    computed before the driver wiring existed and by a different route: if the join changes the
    physics, these move.

    It also pins the area convention, which is the one thing here that fails SILENTLY.
    ``SpreadingSink`` wraps a cooler expressed as a coefficient, and a coefficient is meaningless
    without an area. The cooler's h acts over its own wetted base -- the plate it is bolted to --
    not over the die beneath it. Evaluating it over the die footprint instead cancels against the
    ``h_base = 1/(r_ext * base_area)`` conversion inside ``total_resistance_K_per_W`` and the
    overhang buys exactly nothing: measured 15.2x across the die-size range against the slab's
    15.5x, i.e. indistinguishable from not having done the work. Nothing errors.
    """

    EVIDENCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                            'docs', 'evidence', 'direct_die_overhang.json')

    def _budget(self, die_area_mm2, mr):
        from HotGauge.thermal.sink_models import spreading_sink_for_stack, ConstantHTCSink
        from HotGauge.thermal.die_stack import stack_for_spreading, parse_spec_string
        name = stack_for_spreading('spec:package=direct_die,mr={},src=200,cell=50'.format(mr))
        stack_r = parse_spec_string(name).resistance_budget(die_area_mm2)['total_K_per_W']
        boundary = spreading_sink_for_stack(
            name, ConstantHTCSink(2000.0, ambient_K=303.15), die_area_mm2
        ).total_resistance_K_per_W()
        return stack_r + boundary

    def _rows(self):
        import json
        if not os.path.isfile(self.EVIDENCE):
            pytest.skip('docs/evidence/direct_die_overhang.json not present')
        return json.load(open(self.EVIDENCE))['rows']

    def test_every_overhang_budget_matches(self):
        for r in self._rows():
            got_grease = self._budget(r['die_mm2'], 'none')
            got_array = self._budget(r['die_mm2'], 'GAAS')
            assert got_grease == pytest.approx(r['grease_overhang_r'], abs=5e-5), r['floorplan']
            assert got_array == pytest.approx(r['array_overhang_r'], abs=5e-5), r['floorplan']

    def test_the_arm_delta_is_unchanged_by_the_sink_model(self):
        """The cooling claim must not rest on the sink model -- see the evidence's own note.

        Tolerance is 1.5e-4 rather than the 5e-5 used for the budgets because these two are a
        DIFFERENCE of two 4-decimal stored values, and the evidence's own delta_slab (0.0688) and
        delta_overhang (0.0687) already disagree by 1e-4 for that reason on the 34-core row. The
        physical claim is that the two are the same number; the file cannot express it more
        precisely than it stored it.
        """
        for r in self._rows():
            delta = self._budget(r['die_mm2'], 'none') - self._budget(r['die_mm2'], 'GAAS')
            assert delta == pytest.approx(r['delta_overhang'], abs=1.5e-4), r['floorplan']
            assert delta == pytest.approx(r['delta_slab'], abs=1.5e-4), r['floorplan']
            # ...and the point of the note: the sink model does not move the arm delta at all.
            assert r['delta_slab'] == pytest.approx(r['delta_overhang'], abs=1.5e-4)

    def test_the_die_size_dependence_is_broken(self):
        """15.5x the die area must not give 15.5x less resistance. That is the whole point."""
        rows = {r['floorplan']: r for r in self._rows()}
        small, big = rows['skylake_7core'], rows['ga100']
        area_ratio = big['die_mm2'] / small['die_mm2']
        slab = small['grease_slab_r'] / big['grease_slab_r']
        over = (self._budget(small['die_mm2'], 'none') / self._budget(big['die_mm2'], 'none'))
        assert slab == pytest.approx(area_ratio, rel=0.02)      # the artefact: exactly 1/area
        assert over < 0.25 * area_ratio                          # the fix

    def test_the_coefficient_is_applied_over_the_base_not_the_die(self):
        """Pinned directly, because the wrong area is invisible in every other symptom."""
        from HotGauge.thermal.sink_models import spreading_sink_for_stack, ConstantHTCSink
        from HotGauge.thermal.die_stack import stack_for_spreading
        name = stack_for_spreading('spec:package=direct_die,mr=GAAS,src=200,cell=50')
        s = spreading_sink_for_stack(name, ConstantHTCSink(2000.0, ambient_K=303.15), 53.2)
        assert s._external_r_K_per_W() == pytest.approx(1.0 / (2000.0 * s.base_area_mm2 * 1e-6))

    def test_a_whole_cooler_resistance_is_used_as_it_stands(self):
        """The other convention: 'a 0.12 K/W tower' is already absolute, not per unit area."""
        from HotGauge.thermal.sink_models import (spreading_sink_for_stack,
                                                  ThermalResistanceSink)
        from HotGauge.thermal.die_stack import stack_for_spreading
        name = stack_for_spreading('spec:package=direct_die,mr=GAAS,src=200,cell=50')
        s = spreading_sink_for_stack(name, ThermalResistanceSink(0.12, 53.2e-6), 53.2)
        assert s._external_r_K_per_W() == pytest.approx(0.12)
