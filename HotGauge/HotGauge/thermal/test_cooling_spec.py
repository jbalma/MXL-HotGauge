"""Tests for the geometry-derived cooling specification.

The defect this module exists to fix was invisible for weeks: a sink model that returned the same
thermal resistance for a 101 mm^2 die and an 826 mm^2 one. Nothing raised, nothing looked wrong,
and every accelerator temperature was quietly computed against a heatsink eight times too small.
So the first thing these tests assert is that resistance actually responds to area.
"""
import math
import pytest

from HotGauge.thermal.cooling_spec import (CoolingSpec, FLUIDS, VELOCITY_SANITY,
                                           velocity_is_plausible, solve_flow_for_r_th,
                                           solve_flow_for_peak)


# ---------------------------------------------------------------------------
# The defect this replaces
# ---------------------------------------------------------------------------
def test_thermal_resistance_falls_with_die_area():
    """The whole point. BaffledFinSink gave 0.0764 K/W at both 101 and 826 mm^2."""
    small = CoolingSpec('air', 101.2, flow_m3s=0.02, inlet_C=35.0)
    big = CoolingSpec('air', 826.0, flow_m3s=0.02, inlet_C=35.0)
    assert big.r_th_K_per_W < small.r_th_K_per_W
    assert big.r_th_K_per_W < 0.6 * small.r_th_K_per_W       # materially, not marginally


def test_the_sink_is_built_for_the_die():
    """Geometry scales with the die rather than being a fixed 50 mm block."""
    small = CoolingSpec('air', 101.2, flow_m3s=0.02, inlet_C=35.0)
    big = CoolingSpec('air', 826.0, flow_m3s=0.02, inlet_C=35.0)
    assert big.base_side_mm > small.base_side_mm
    assert big.wetted_area_mm2 > small.wetted_area_mm2
    assert big.n_fins > small.n_fins


def test_the_fin_array_fits_the_base_it_sits_on():
    """The source model set fin spacing and thickness both to L/N, so N*(s+t) = 2L -- the fins
    occupied twice their own base. Solving the COUNT from the base width instead keeps the
    geometry closed."""
    for area in (50.0, 101.2, 826.0):
        s = CoolingSpec('air', area, flow_m3s=0.02, inlet_C=35.0)
        occupied = s.n_fins * (s.fin_thickness_mm + s.fin_gap_mm)
        assert occupied <= s.base_side_mm + 1e-9


# ---------------------------------------------------------------------------
# Flow physics
# ---------------------------------------------------------------------------
def test_low_flow_is_penalised_by_the_coolant_heating_up():
    """Without the caloric term a laminar channel has a flow-INDEPENDENT h (Nu fixed at 3.66), so
    the model says halving the flow costs nothing and an inverse solve drives flow to zero. It did
    exactly that before this term existed."""
    hi = CoolingSpec('air', 826.0, flow_m3s=0.05, inlet_C=35.0)
    lo = CoolingSpec('air', 826.0, flow_m3s=0.005, inlet_C=35.0)
    assert lo.r_caloric_K_per_W > hi.r_caloric_K_per_W
    assert lo.r_th_K_per_W > hi.r_th_K_per_W


def test_caloric_resistance_is_the_textbook_expression():
    s = CoolingSpec('water', 826.0, flow_m3s=1e-4, inlet_C=25.0)
    p = FLUIDS['water']
    assert s.r_caloric_K_per_W == pytest.approx(1.0 / (p['rho'] * p['cp'] * 1e-4))


def test_mover_power_scaling_differs_by_flow_regime():
    """The "pump power goes as flow cubed" rule is the TURBULENT result, and quoting it in the
    laminar regime overstates the cost of flow.

    Laminar: f = 64/Re goes as 1/v, so dp ~ v and P = dp*Vdot ~ v^2 -- doubling flow quadruples
    the power, exactly.
    Turbulent: f ~ Re^-0.25, so dp ~ v^1.75 and P ~ v^2.75, approaching the cubic law.
    """
    lam_a = CoolingSpec('air', 826.0, flow_m3s=0.02, inlet_C=35.0)
    lam_b = CoolingSpec('air', 826.0, flow_m3s=0.04, inlet_C=35.0)
    assert lam_a.reynolds < 2300 and lam_b.reynolds < 2300
    assert lam_b.mover_power_W / lam_a.mover_power_W == pytest.approx(4.0, rel=1e-6)

    turb_a = CoolingSpec('air', 826.0, flow_m3s=0.4, inlet_C=35.0)
    turb_b = CoolingSpec('air', 826.0, flow_m3s=0.8, inlet_C=35.0)
    assert turb_a.reynolds > 2300
    ratio = turb_b.mover_power_W / turb_a.mover_power_W
    assert 6.0 < ratio < 8.0        # 2^2.75 = 6.73, between quadratic and cubic


def test_turbulent_transition_raises_the_heat_transfer_coefficient():
    lam = CoolingSpec('air', 826.0, flow_m3s=0.002, inlet_C=35.0)
    turb = CoolingSpec('air', 826.0, flow_m3s=0.2, inlet_C=35.0)
    assert lam.reynolds < 2300 < turb.reynolds
    assert lam.nusselt == pytest.approx(3.66)
    assert turb.h_conv > lam.h_conv


# ---------------------------------------------------------------------------
# Wall-plug power -- the half that did not exist before
# ---------------------------------------------------------------------------
def test_an_inlet_at_or_above_ambient_is_free_cooling():
    s = CoolingSpec('water', 826.0, flow_m3s=1e-4, inlet_C=35.0, ambient_C=35.0)
    assert s.chiller_cop == float('inf')
    assert s.chiller_power_W(700.0) == 0.0
    assert s.wall_plug_W(700.0) == pytest.approx(s.mover_power_W)


def test_chilling_below_ambient_costs_more_the_colder_it_gets():
    warm = CoolingSpec('water', 826.0, flow_m3s=1e-4, inlet_C=30.0, ambient_C=35.0)
    cold = CoolingSpec('water', 826.0, flow_m3s=1e-4, inlet_C=10.0, ambient_C=35.0)
    assert cold.chiller_cop < warm.chiller_cop
    assert cold.chiller_power_W(700.0) > warm.chiller_power_W(700.0)


def test_chiller_cop_follows_the_carnot_fraction():
    s = CoolingSpec('water', 826.0, flow_m3s=1e-4, inlet_C=15.0, ambient_C=35.0,
                    chiller_gamma=0.4)
    expected = 0.4 * (15.0 + 273.15) / (35.0 - 15.0)
    assert s.chiller_cop == pytest.approx(expected)


def test_the_chiller_also_has_to_reject_the_movers_own_heat():
    """High flow is doubly expensive: cubic to move, then rejected again. Omitting this flatters
    every high-flow configuration."""
    s = CoolingSpec('water', 826.0, flow_m3s=5e-4, inlet_C=15.0, ambient_C=35.0)
    naive = s.chiller_power_W(700.0)
    actual = s.wall_plug_W(700.0) - s.mover_power_W
    assert actual > naive


def test_liquid_now_has_a_power_cost_at_all():
    """The gap that made a liquid comparison arm impossible: --r-th supplied a resistance with no
    power whatsoever, so liquid always won by construction."""
    s = CoolingSpec('water', 826.0, flow_m3s=5e-4, inlet_C=20.0, ambient_C=35.0)
    assert s.mover_power_W > 0
    assert s.wall_plug_W(700.0) > s.mover_power_W
    assert 0 < s.system_cop(700.0) < 1000


# ---------------------------------------------------------------------------
# Inversion -- the direction studies actually need
# ---------------------------------------------------------------------------
def test_solving_for_a_target_returns_a_spec_that_meets_it():
    s = solve_flow_for_r_th('air', 826.0, target_r_th=0.10, inlet_C=35.0, ambient_C=35.0)
    assert s is not None
    assert s.r_th_K_per_W <= 0.10 + 1e-6


def test_an_unreachable_target_returns_None_rather_than_a_fake_answer():
    """The constriction floor produces exactly this, and it has to be reportable."""
    assert solve_flow_for_r_th('air', 101.2, target_r_th=1e-4) is None


def test_solving_for_a_peak_temperature():
    s = solve_flow_for_peak('air', 826.0, heat_W=700.0, target_peak_C=90.0, inlet_C=35.0,
                            ambient_C=35.0)
    assert s is not None
    assert s.inlet_C + 700.0 * s.r_th_K_per_W <= 90.0 + 1e-6


def test_a_target_below_the_inlet_is_rejected():
    with pytest.raises(ValueError):
        solve_flow_for_peak('air', 826.0, heat_W=700.0, target_peak_C=30.0, inlet_C=35.0)


# ---------------------------------------------------------------------------
# Honesty
# ---------------------------------------------------------------------------
def test_implausible_velocities_are_reported_not_clipped():
    """88 CFM through a sink sized for a 101 mm^2 die needs ~66 m/s. Clipping it into range is how
    a nonsense configuration becomes a plausible-looking temperature."""
    s = CoolingSpec('air', 101.2, flow_m3s=0.0415, inlet_C=35.0)
    ok, msg = velocity_is_plausible(s)
    assert ok is False
    assert 'not a buildable configuration' in msg
    assert s.velocity_m_s > VELOCITY_SANITY['air'][1]


def test_nothing_here_claims_to_be_calibrated():
    s = CoolingSpec('air', 826.0, flow_m3s=0.02, inlet_C=35.0)
    assert s.calibrated is False
    assert 'UNCALIBRATED' in repr(s)


def test_bad_inputs_are_rejected():
    with pytest.raises(ValueError):
        CoolingSpec('helium', 826.0, flow_m3s=0.02, inlet_C=35.0)
    with pytest.raises(ValueError):
        CoolingSpec('air', 0.0, flow_m3s=0.02, inlet_C=35.0)
    with pytest.raises(ValueError):
        CoolingSpec('air', 826.0, flow_m3s=0.0, inlet_C=35.0)


def test_report_carries_both_halves_of_the_trade():
    s = CoolingSpec('air', 826.0, flow_m3s=0.043, inlet_C=35.0, ambient_C=35.0)
    r = s.report(700.0)
    for k in ('r_th_K_per_W', 'r_caloric_K_per_W', 'htc_si', 'mover_power_W',
              'chiller_power_W', 'wall_plug_W', 'system_cop', 'peak_estimate_C'):
        assert k in r
    assert r['calibrated'] is False
    assert r['peak_estimate_C'] == pytest.approx(35.0 + 700.0 * s.r_th_K_per_W)
