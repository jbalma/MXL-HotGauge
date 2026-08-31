"""Tests for the measured product V/F curve. Pure Python, no toolchain."""
import pytest

from HotGauge.power.product_vf import (ProductVFModel, ZEN5_9950X_VF, ZEN5_VMAX,
                                       ZEN5_9950X_DVDT_mV_per_K)


class TestMeasuredAnchors:
    """The curve must reproduce what was measured, exactly, at the points that were measured."""

    def test_the_anchors_come_back_unchanged(self):
        m = ProductVFModel()
        for f, v in ZEN5_9950X_VF:
            assert m.voltage_for_frequency(f) == pytest.approx(v, abs=1e-9)

    def test_the_temperature_resolved_points_reproduce(self):
        """4766 MHz: 1.060 -> 1.080 V and 5165 MHz: 1.110 -> 1.158 V, both over 40 -> 90 C."""
        m = ProductVFModel()
        assert m.voltage_for_frequency(4.766, 40.0) == pytest.approx(1.060, abs=1e-6)
        assert m.voltage_for_frequency(4.766, 90.0) == pytest.approx(1.080, abs=1e-6)
        assert m.voltage_for_frequency(5.165, 40.0) == pytest.approx(1.110, abs=1e-6)
        assert m.voltage_for_frequency(5.165, 90.0) == pytest.approx(1.158, abs=1e-6)

    def test_it_refuses_to_extrapolate(self):
        """Four points on one part. Outside them there is no data, and inventing some is the
        failure mode this project keeps finding in its own history."""
        m = ProductVFModel()
        for f in (3.0, 4.0, 6.0, 7.0):
            with pytest.raises(ValueError):
                m.voltage_for_frequency(f)

    def test_it_is_not_calibrated_and_says_so(self):
        """One part, enthusiast-press measurement. The flag exists so nobody quotes it as spec."""
        assert ProductVFModel().calibrated is False


class TestTemperatureIsTheNewLever:
    """Every other V/F curve in this repository is temperature-independent, so this lever has
    been absent by construction -- the same shape of omission as the unsourced dt_max = 10 K."""

    def test_sensitivity_rises_steeply_with_frequency(self):
        """It more than doubles across 0.4 GHz, which is why it cannot be a constant."""
        m = ProductVFModel()
        assert m.dV_dT_mV_per_K(5.165) > 2.0 * m.dV_dT_mV_per_K(4.766)

    def test_sensitivity_is_held_flat_outside_the_measured_range(self):
        """The trend is steeply increasing, so extrapolating would OVERSTATE the LCMR benefit.
        Holding it flat makes the error run the safe way."""
        m = ProductVFModel()
        top = m.dV_dT_mV_per_K(5.165)
        assert m.dV_dT_mV_per_K(5.60) == pytest.approx(top)
        assert m.dV_dT_mV_per_K(4.00) == pytest.approx(m.dV_dT_mV_per_K(4.766))

    def test_cooling_saves_voltage_and_therefore_dynamic_power(self):
        m = ProductVFModel()
        saved = m.voltage_saved_by_cooling(5.165, 90.0, 40.0)
        assert saved == pytest.approx(0.048, abs=1e-6)
        # V^2 at constant f: a 48 mV saving on 1.158 V is ~8%.
        ratio = m.dynamic_power_ratio_from_cooling(5.165, 90.0, 40.0)
        assert 0.90 < ratio < 0.93

    def test_cooling_buys_clock_at_a_fixed_voltage_ceiling(self):
        """The lever stated the other way round: same 1.35 V, colder part, more clock."""
        m = ProductVFModel()
        gain = m.clock_gained_by_cooling(90.0, 40.0)
        assert gain > 0.0
        assert gain == pytest.approx(0.093, abs=0.01)   # ~93 MHz

    def test_no_cooling_no_gain(self):
        m = ProductVFModel()
        assert m.voltage_saved_by_cooling(5.0, 60.0, 60.0) == pytest.approx(0.0)
        assert m.dynamic_power_ratio_from_cooling(5.0, 60.0, 60.0) == pytest.approx(1.0)


class TestAgainstTheShippedTable:
    """Why the shipped table cannot be a modern-node curve, stated as a measurement rather than
    as an argument from IRDS projections."""

    def test_the_shipped_table_demands_far_more_voltage_for_the_same_clock(self):
        from HotGauge.configuration.performance import VF_PAIRS
        m = ProductVFModel()
        shipped_5GHz = dict((f, v) for v, f in VF_PAIRS)[5.0]
        measured_5GHz = m.voltage_for_frequency(5.0, 40.0)
        assert shipped_5GHz == pytest.approx(1.4)
        assert measured_5GHz == pytest.approx(1.08, abs=0.01)
        # ~30% more supply for the same clock, hence ~1.7x the dynamic power.
        assert shipped_5GHz / measured_5GHz > 1.25
        assert (shipped_5GHz / measured_5GHz) ** 2 > 1.6

    def test_a_real_part_exceeds_the_shipped_table_top_at_a_lower_voltage(self):
        """The shipped table calls 1.4 V / 5.0 GHz the device limit. A shipping part does
        5.63 GHz at 1.35 V. The table's ceiling is a property of the table."""
        m = ProductVFModel()
        assert m.f_max_measured > 5.0
        assert m.voltage_for_frequency(m.f_max_measured) <= ZEN5_VMAX < 1.4
