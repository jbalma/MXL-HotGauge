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
                                           solve_flow_for_peak, spreading_resistance_K_per_W,
                                           base_area_from_footprint, SIMSCALE_BASE_GEOMETRY,
                                           DEFAULT_BASE_FOOTPRINT_MM2,
                                           staged_spreading_resistance_K_per_W)


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
    lam_a = CoolingSpec('air', 826.0, flow_m3s=0.005, inlet_C=35.0)
    lam_b = CoolingSpec('air', 826.0, flow_m3s=0.010, inlet_C=35.0)
    assert lam_a.reynolds < 2300 and lam_b.reynolds < 2300
    assert (lam_b.analytic_mover_power_W / lam_a.analytic_mover_power_W
            == pytest.approx(4.0, rel=1e-6))

    turb_a = CoolingSpec('air', 826.0, flow_m3s=0.4, inlet_C=35.0)
    turb_b = CoolingSpec('air', 826.0, flow_m3s=0.8, inlet_C=35.0)
    assert turb_a.reynolds > 2300
    ratio = turb_b.analytic_mover_power_W / turb_a.analytic_mover_power_W
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


# ---------------------------------------------------------------------------
# Validation against the measured data, inside its range
# ---------------------------------------------------------------------------
def test_convective_resistance_matches_the_measured_curve():
    """An analytic correlation is only worth extrapolating from if it reproduces measurement where
    measurement exists. base_spread was CALIBRATED against exactly this, so the agreement is a fit
    rather than a prediction -- but the fit is one number across four flow rates, and the residual
    shape is what tells you whether the physics is right."""
    from HotGauge.thermal.cooling_spec import air_spec
    from HotGauge.thermal.sink_models import simscale_convective_r_th
    CFM = 1.0 / 2118.88
    for cfm in (60, 88, 150, 200):
        s = air_spec(484.0, cfm * CFM, 35.0)          # the CFD's own 22x22 mm die
        target = simscale_convective_r_th(cfm)
        assert s.r_conv_K_per_W == pytest.approx(target, rel=0.12), cfm


def test_the_analytic_mover_term_misses_the_fixed_overhead():
    """Where the analytic term fails, and where it does not.

    It models fin friction only, so it misses the mover's fixed overhead -- the measured fan curve
    has an ~18 W intercept at zero flow. At low flow that dominates and the analytic is useless;
    once friction takes over it lands within a few percent. I first reported a uniform 2-6x
    under-prediction, which was an artefact of an over-large default sink, not a property of the
    correlation.
    """
    from HotGauge.thermal.cooling_spec import air_spec
    CFM = 1.0 / 2118.88
    low = air_spec(484.0, 20 * CFM, 35.0)
    assert low.analytic_mover_power_W < 0.1 * low.mover_power_W       # overhead dominates

    high = air_spec(484.0, 88 * CFM, 35.0)
    ratio = high.analytic_mover_power_W / high.mover_power_W
    assert 0.8 < ratio < 1.2                                          # friction dominates
    assert 'fixed overhead' in type(high).analytic_mover_power_W.__doc__


def test_air_spec_defaults_to_the_measured_fan_curve():
    from HotGauge.thermal.cooling_spec import air_spec, measured_air_mover_power
    from HotGauge.thermal.sink_models import simscale_fan_power
    CFM = 1.0 / 2118.88
    s = air_spec(484.0, 88 * CFM, 35.0)
    assert s.mover_power_W == pytest.approx(simscale_fan_power(88))
    assert s.report(100.0)['mover_power_source'] == 'measured curve'


def test_the_measured_fan_curve_is_discontinuous_and_that_is_physical():
    """Three fans, handovers at 88 and 133 CFM. No continuous analytic form reproduces it, and the
    steps are why the source study found best system COP at NONZERO laser power -- cooling the
    hotspot lets the system stay on the cheaper fan."""
    from HotGauge.thermal.cooling_spec import measured_air_mover_power
    CFM = 1.0 / 2118.88
    below, above = measured_air_mover_power(87.9 * CFM), measured_air_mover_power(88.1 * CFM)
    assert above > below * 1.5


# ---------------------------------------------------------------------------
# The sink adapter
# ---------------------------------------------------------------------------
def test_sink_presents_convective_and_caloric_but_not_conduction():
    """3D-ICE models the die and base itself. Including R_cond here would double-count them."""
    from HotGauge.thermal.cooling_spec import air_spec, CoolingSpecSink
    CFM = 1.0 / 2118.88
    s = air_spec(826.0, 88 * CFM, 35.0)
    sink = CoolingSpecSink(s, heat_W=700.0)
    assert sink.r_th_K_per_W == pytest.approx(s.r_conv_K_per_W + s.r_caloric_K_per_W)
    assert sink.r_th_K_per_W < s.r_th_K_per_W


def test_sink_charges_for_the_chiller_not_just_the_mover():
    """The gap that let liquid cooling win by construction: --r-th supplied a resistance for free."""
    from HotGauge.thermal.cooling_spec import CoolingSpec, CoolingSpecSink
    s = CoolingSpec('water', 826.0, flow_m3s=5e-4, inlet_C=15.0, ambient_C=35.0)
    sink = CoolingSpecSink(s, heat_W=700.0)
    assert sink.parasitic_known is True
    assert sink.parasitic_power_W > s.mover_power_W


def test_sink_htc_scales_with_die_area():
    from HotGauge.thermal.cooling_spec import air_spec, CoolingSpecSink
    CFM = 1.0 / 2118.88
    small = CoolingSpecSink(air_spec(101.2, 88 * CFM, 35.0), 111.0)
    big = CoolingSpecSink(air_spec(826.0, 88 * CFM, 35.0), 700.0)
    assert small.htc_si() != pytest.approx(big.htc_si(), rel=0.05)


# ---------------------------------------------------------------------------
# Cooler class, and the package the stack adds
# ---------------------------------------------------------------------------
def test_base_spread_is_a_cooler_property_not_a_universal_constant():
    """1.85 was calibrated on the SimScale CFD's own small sink and then applied everywhere. Real
    coolers differ by nearly an order of magnitude in how far they overhang the die, and using the
    CFD value for a desktop tower demanded 343 m/s of air -- caught by the velocity check, not by
    the resistance, which matched to 1.4%."""
    from HotGauge.thermal.cooling_spec import COOLER_CLASSES
    assert COOLER_CLASSES['cfd_reference'] < COOLER_CLASSES['datacenter_module']
    assert COOLER_CLASSES['datacenter_module'] < COOLER_CLASSES['desktop_tower']
    assert COOLER_CLASSES['desktop_tower'] / COOLER_CLASSES['cfd_reference'] > 5


def test_a_bigger_cooler_reaches_the_same_resistance_at_a_buildable_velocity():
    """The point of the class: it is not that a small sink cannot reach the target, but that it
    can only do so at a face velocity nobody builds."""
    from HotGauge.thermal.cooling_spec import (solve_flow_for_r_th, air_spec,
                                               velocity_is_plausible, COOLER_CLASSES)
    target = 0.0508
    small = solve_flow_for_r_th('air', 826.0, target, inlet_C=21.5, ambient_C=21.5,
                                base_spread=COOLER_CLASSES['cfd_reference'])
    big = solve_flow_for_r_th('air', 826.0, target, inlet_C=21.5, ambient_C=21.5,
                              base_spread=COOLER_CLASSES['datacenter_module'])
    assert small is not None and big is not None
    assert velocity_is_plausible(small)[0] is False
    assert velocity_is_plausible(big)[0] is True


def test_a_published_total_must_have_the_package_subtracted():
    """Published resistances are junction-to-ambient and already contain the package. Handing one
    straight to a sink overshoots, because 3D-ICE adds the package again -- on the GA100 die that
    is more than half the budget."""
    from HotGauge.thermal.cooling_spec import external_r_for_total
    assert external_r_for_total(0.1074, 0.0566) == pytest.approx(0.0508, abs=1e-6)


def test_a_package_larger_than_the_target_is_reported_as_unreachable():
    from HotGauge.thermal.cooling_spec import external_r_for_total
    with pytest.raises(ValueError) as e:
        external_r_for_total(0.05, 0.09)
    assert 'no external cooling reaches' in str(e.value)


def test_the_sink_records_the_package_it_was_built_against():
    from HotGauge.thermal.cooling_spec import air_spec, CoolingSpecSink
    s = air_spec(826.0, 0.03, 21.5)
    sink = CoolingSpecSink(s, 470.0, r_package_K_per_W=0.0406)
    assert sink.r_package_K_per_W == pytest.approx(0.0406)
    # the sink still presents only its OWN resistance -- 3D-ICE models the package itself
    assert sink.r_th_K_per_W == pytest.approx(s.r_conv_K_per_W + s.r_caloric_K_per_W)


# ---------------------------------------------------------------------------
# Spreading resistance
# ---------------------------------------------------------------------------
class TestSpreadingResistance:
    """The package term that has to stop scaling as 1/area.

    Every layer in a 3D-ICE stack spans exactly the die footprint, so a sink modelled as a slab
    gives a package budget proportional to 1/area -- measured 0.0402 K/W at 826 mm^2 and 0.3648
    at 91 mm^2, which is 9.08x for 9.08x the area. That is why the acceptance gate reproduces an
    accelerator and fails a CPU.
    """

    K_CU = 300.0
    H = 2000.0

    def test_a_base_the_size_of_the_die_is_exactly_the_one_dimensional_answer(self):
        """With no overhang there is nothing to spread into, so the correlation must collapse.

        This is the calibration-free check on the whole formula: no fitted constant can hide
        here, because the 1-D answer is arithmetic.
        """
        area, t = 300.0, 2.0
        got = spreading_resistance_K_per_W(area, area, t, self.K_CU, self.H)
        exact = t * 1e-3 / (self.K_CU * area * 1e-6) + 1.0 / (self.H * area * 1e-6)
        assert got == pytest.approx(exact, rel=1e-9)

    def test_the_half_space_limit_is_right_and_conservative(self):
        """The check that caught a dropped 1/sqrt(pi) on the spreading term.

        A vanishing source on a thick, weakly-cooled base is the classical constriction problem.
        The Lee correlation tends to a dimensionless psi of 1/sqrt(pi) = 0.5642 there; the exact
        isoflux half-space value is 8/(3 pi^1.5) = 0.4789, so the correlation runs ~18%
        conservative in its worst corner. Both bounds are asserted, because the *direction* of
        the error matters: this term must never come out optimistically small.

        The ``base == die`` test above cannot see this error at all -- the spreading term
        vanishes when eps = 1 -- which is exactly why a second limit is needed.
        """
        k, die, base, t, h = 300.0, 1.0, 1.0e6, 200.0, 1.0
        a = math.sqrt(die / math.pi) / 1000.0
        r_1d = 1.0 / (h * base * 1e-6)
        psi = math.sqrt(math.pi) * k * a * (
            spreading_resistance_K_per_W(die, base, t, k, h) - r_1d)
        exact_isoflux = 8.0 / (3.0 * math.pi ** 1.5)
        assert psi == pytest.approx(1.0 / math.sqrt(math.pi), rel=0.01), psi
        assert psi > exact_isoflux, 'the correlation must not be optimistic against the exact value'
        assert psi < 1.25 * exact_isoflux

    def test_it_breaks_the_one_over_area_scaling(self):
        """The whole point. 9.08x the die area must not give 1/9.08 the resistance."""
        small = spreading_resistance_K_per_W(91.0, 1825.0, 2.0, self.K_CU, self.H)
        large = spreading_resistance_K_per_W(826.0, 1825.0, 2.0, self.K_CU, self.H)
        area_ratio = 826.0 / 91.0
        assert small > large, 'a smaller die still runs hotter, just not proportionally'
        assert small / large < 0.5 * area_ratio, (
            'resistance ratio {:.2f} is still tracking the area ratio {:.2f}'
            .format(small / large, area_ratio))

    def test_a_fixed_footprint_does_not_scale_with_the_die(self):
        """A cold plate is sized by the socket. Scaling it with the die reintroduces 1/area."""
        assert base_area_from_footprint(91.0) == pytest.approx(DEFAULT_BASE_FOOTPRINT_MM2)
        assert base_area_from_footprint(826.0) == pytest.approx(DEFAULT_BASE_FOOTPRINT_MM2)

    def test_a_die_bigger_than_the_plate_still_gets_a_legal_base(self):
        assert base_area_from_footprint(5000.0) == pytest.approx(5000.0)

    def test_a_base_smaller_than_its_die_is_refused(self):
        with pytest.raises(ValueError):
            spreading_resistance_K_per_W(826.0, 100.0, 2.0, self.K_CU, self.H)

    def test_a_thicker_base_always_helps(self):
        r = [spreading_resistance_K_per_W(300.0, 1825.0, t, self.K_CU, self.H)
             for t in (0.5, 1.0, 2.0, 4.0, 8.0)]
        assert r == sorted(r, reverse=True), r

    def test_base_area_has_an_interior_optimum_and_that_is_not_a_bug(self):
        """Widening the plate at fixed thickness eventually costs more than it buys.

        A wide thin plate spreads badly: tau = t/b falls as the base grows, so past some size the
        spreading term rises faster than the convective term falls. This is the reason you cannot
        rescue a small die by bolting on a bigger cold plate without also making it thicker, and
        it is pinned so nobody later 'fixes' the non-monotonicity.
        """
        areas = (300.0, 600.0, 1200.0, 2400.0, 4800.0, 9600.0)
        r = [spreading_resistance_K_per_W(300.0, b, 2.0, self.K_CU, self.H) for b in areas]
        assert min(r) < r[0] and min(r) < r[-1], r
        assert r != sorted(r, reverse=True), 'expected a minimum, not monotone decay'

    def test_the_simscale_geometry_is_recorded_with_its_ratios(self):
        """Provenance: these are the bases the CFD actually meshed, not a chosen ratio."""
        for key, g in SIMSCALE_BASE_GEOMETRY.items():
            base = g['base_mm'][0] * g['base_mm'][1]
            ratio = math.sqrt(base) / g['die_side_mm']
            assert 2.0 < ratio < 4.0, '{}: implied base_spread {:.2f}'.format(key, ratio)


class TestStagedSpreading:
    """A real package spreads twice: die -> lid -> cold plate.

    Charging the second spreader as a slab over the lid's area throws away its overhang, which is
    the larger of the two opportunities.
    """

    LID = {'area_mm2': 1825.0, 'thickness_mm': 3.0, 'k_W_mK': 390.0}
    PLATE = {'area_mm2': 13916.0, 'thickness_mm': 2.0, 'k_W_mK': 300.0}

    def test_a_single_stage_is_exactly_the_single_stage_function(self):
        """The general form has to contain the special case, or one of them is wrong."""
        staged = staged_spreading_resistance_K_per_W(71.0, [self.LID], 0.05)
        direct = spreading_resistance_K_per_W(
            71.0, self.LID['area_mm2'], self.LID['thickness_mm'], self.LID['k_W_mK'],
            1.0 / (0.05 * self.LID['area_mm2'] * 1e-6))
        assert staged == pytest.approx(direct, rel=1e-12)

    def test_stages_must_grow_outward(self):
        """A spreader smaller than what feeds it is a mis-ordered list, not a design."""
        with pytest.raises(ValueError):
            staged_spreading_resistance_K_per_W(71.0, [self.PLATE, self.LID], 0.05)

    def test_a_second_stage_adds_resistance_at_fixed_external_cooling(self):
        """Counter-intuitive but right: another interface to cross costs something.

        The second stage pays for itself through the much larger area the *convection* then acts
        over -- which is a property of the cooler, not of this function. Compared at the same
        r_external, more stages can only add.
        """
        one = staged_spreading_resistance_K_per_W(71.0, [self.LID], 0.12)
        two = staged_spreading_resistance_K_per_W(71.0, [self.LID, self.PLATE], 0.12)
        assert two > one

    def test_a_thicker_or_more_conductive_plate_always_helps(self):
        base = staged_spreading_resistance_K_per_W(71.0, [self.LID, self.PLATE], 0.12)
        thick = dict(self.PLATE, thickness_mm=6.0)
        conductive = dict(self.PLATE, k_W_mK=2000.0)
        assert staged_spreading_resistance_K_per_W(71.0, [self.LID, thick], 0.12) < base
        assert staged_spreading_resistance_K_per_W(71.0, [self.LID, conductive], 0.12) < base

    def test_contact_resistance_is_charged_over_its_own_stage(self):
        """Grease between lid and plate acts over the LID, which is what makes moving it correct."""
        clean = staged_spreading_resistance_K_per_W(71.0, [self.LID], 0.12)
        greasy = dict(self.LID, contact_r_K_per_W=0.030e-3 / (4.0 * 1825.0e-6))
        assert staged_spreading_resistance_K_per_W(71.0, [greasy], 0.12) > clean

    def test_better_external_cooling_always_lowers_the_total(self):
        r = [staged_spreading_resistance_K_per_W(71.0, [self.LID, self.PLATE], x)
             for x in (0.30, 0.20, 0.12, 0.05)]
        assert r == sorted(r, reverse=True), r
