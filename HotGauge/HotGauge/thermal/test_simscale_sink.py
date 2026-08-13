"""Regression tests for the SimScale baffled-fin surrogate and the N-core scaling fixes.

Every test here corresponds to a bug that produced a wrong *result* rather than a crash, which
is why they are worth pinning:

* handing 3D-ICE the end-to-end ``alpha`` as a sink boundary double-counts the die and
  manufactures thermal runaway;
* ``eta_laser`` inverted makes laser cooling look 25x cheaper than it is;
* ``NO_POWER_UNITS`` hardcoded to 8 cores caps the whole pipeline at 8 cores;
* ``grid_for`` accepting any exact factorisation yields 2x17 "dies";
* a solver/setup failure recorded as thermal runaway is a config bug reported as physics.
"""
import numpy as np
import pytest

from HotGauge.thermal.sink_models import (
    simscale_alpha, simscale_beta, simscale_convective_r_th, simscale_constriction_r_th,
    simscale_fan_power, simscale_tmax_K, simscale_fan_cop, cooling_cop, BaffledFinSink,
    SIMSCALE_ALPHA_FIT, SIMSCALE_BETA_FIT, SIMSCALE_ETA_LASER, SIMSCALE_T0_K,
    SIMSCALE_EXACT_ANCHOR,
    SIMSCALE_FAN_COP_BANDS)


class TestDecomposition:
    def test_convective_is_strictly_below_end_to_end(self):
        """The sink boundary must be the convective term only, not alpha.

        Passing alpha (which contains the SimScale die's own conduction) to a solver that
        models the die itself double-counts that path.
        """
        for cfm in (10, 30, 88, 200):
            assert simscale_convective_r_th(cfm) < simscale_alpha(cfm)

    def test_convection_is_a_minority_of_the_path_at_server_airflow(self):
        """Below ~50 CFM convection really does dominate; by 88 CFM it does not, which is why
        more air stops helping. Pinning both regimes so the crossover cannot drift."""
        assert simscale_convective_r_th(10) > 0.6 * simscale_alpha(10)
        for cfm in (88, 133, 200):
            assert simscale_convective_r_th(cfm) < 0.3 * simscale_alpha(cfm)

    def test_alpha_and_beta_share_a_convective_term(self):
        """Both paths end at the same fins, so their airflow-dependent parts must agree.

        This is the physical check that validates the whole decomposition.
        """
        for cfm in (10, 50, 88, 200):
            a_conv = SIMSCALE_ALPHA_FIT['amp'] * cfm ** (-SIMSCALE_ALPHA_FIT['n'])
            b_conv = SIMSCALE_BETA_FIT['amp'] * cfm ** (-SIMSCALE_BETA_FIT['n'])
            assert a_conv == pytest.approx(b_conv, abs=0.07)

    def test_constriction_is_airflow_independent(self):
        """beta - alpha is a conduction term: no fan can touch it. This is the MR argument."""
        r = simscale_constriction_r_th()
        assert r == pytest.approx(1.0424, abs=1e-3)
        # It is a constant by construction; assert the fits actually make it dominant.
        assert r > 4 * SIMSCALE_ALPHA_FIT['r_cond']

    def test_fit_reproduces_the_tabulated_curves(self):
        for cfm in (10, 20, 50, 100, 200):
            fit = SIMSCALE_ALPHA_FIT['r_cond'] + simscale_convective_r_th(cfm)
            assert fit == pytest.approx(simscale_alpha(cfm), abs=0.015)

    def test_digitised_curves_match_the_exact_source_anchor(self):
        """docs/SimScale/data/tT0.dat gives alpha/beta exactly at ~100 CFM."""
        cfm = SIMSCALE_EXACT_ANCHOR['cfm']
        assert simscale_alpha(cfm) == pytest.approx(SIMSCALE_EXACT_ANCHOR['alpha'], rel=0.01)
        assert simscale_beta(cfm) == pytest.approx(SIMSCALE_EXACT_ANCHOR['beta'], rel=0.01)

    def test_alpha_on_and_off_are_superposed(self):
        """Verified against two independent exact grids (tT0.dat vs tCOP1b.dat).

        This is what lets Eq. (4)'s P_core bracket collapse to a single alpha.
        """
        on, off = SIMSCALE_EXACT_ANCHOR['alpha'], SIMSCALE_EXACT_ANCHOR['alpha_off']
        assert on == pytest.approx(off, rel=0.005)

    def test_constriction_survives_the_digitisation(self):
        """The MR argument rests on beta - alpha, so pin it against the exact source pair.

        1.0424 K/W from fitting digitised curve *shapes* vs 1.0433 K/W from exact data.
        """
        exact = SIMSCALE_EXACT_ANCHOR['beta'] - SIMSCALE_EXACT_ANCHOR['alpha']
        assert simscale_constriction_r_th() == pytest.approx(exact, rel=0.005)


class TestFanCurve:
    def test_power_jumps_at_band_edges(self):
        """The discontinuities are physical -- no fan exists between bands -- and they are
        what create the COP optimum. A smooth curve would hide it."""
        assert simscale_fan_power(89) > 2 * simscale_fan_power(88)
        assert simscale_fan_power(134) > 1.7 * simscale_fan_power(133)

    def test_zero_flow_is_zero_power(self):
        assert simscale_fan_power(0) == 0.0


class TestLaserConvention:
    def test_eta_laser_is_a_cost_multiplier(self):
        """P_laser = eta_laser * P_extr, so 20% ASF means 5.0 -- NOT 0.20."""
        assert SIMSCALE_ETA_LASER == pytest.approx(5.0)

    def test_full_cancellation_costs_eta_times_hotspot_power(self):
        p_fu = 70.0
        full = SIMSCALE_ETA_LASER * p_fu
        t_none = simscale_tmax_K(88, 290.0, p_fu, 0.0)
        t_full = simscale_tmax_K(88, 290.0, p_fu, full)
        # Full extraction removes exactly the beta*P_FU term.
        assert t_none - t_full == pytest.approx(simscale_beta(88) * p_fu, rel=1e-6)

    def test_laser_beyond_full_cancellation_does_not_overshoot(self):
        p_fu = 70.0
        full = SIMSCALE_ETA_LASER * p_fu
        assert simscale_tmax_K(88, 290.0, p_fu, 10 * full) == pytest.approx(
            simscale_tmax_K(88, 290.0, p_fu, full))

    def test_inverting_eta_would_change_the_answer(self):
        """Guards the specific mistake: 0.20 instead of 5.0 understates laser cost 25x."""
        p_fu = 70.0
        cheap = simscale_tmax_K(88, 290.0, p_fu, 20.0, eta_laser=0.20)
        real = simscale_tmax_K(88, 290.0, p_fu, 20.0, eta_laser=5.0)
        assert real > cheap + 50.0


class TestCOP:
    def test_fan_only_cop_is_the_band_efficiency(self):
        """With the laser off the system COP is just the fan's wall-plug efficiency."""
        for cfm in (50, 100, 200):
            assert cooling_cop(cfm) == pytest.approx(simscale_fan_cop(cfm))

    def test_cheap_band_is_the_least_efficient_fan(self):
        """The counter-intuitive part: minimum absolute power sits on the worst-COP fan, so
        'cheap' must not be read as 'efficient'."""
        assert simscale_fan_cop(50) < simscale_fan_cop(200)
        assert simscale_fan_cop(50) == pytest.approx(SIMSCALE_FAN_COP_BANDS[0][1])

    def test_adding_mr_helps_exactly_when_it_beats_the_fan(self):
        """MR at 0.14 beats the 0.125 low band and loses to the 0.263 high band."""
        low = simscale_fan_cop(50)
        assert cooling_cop(50, p_laser_W=50.0, mr_cop=0.14) > low
        high = simscale_fan_cop(200)
        assert cooling_cop(200, p_laser_W=50.0, mr_cop=0.14) < high

    def test_cop_is_a_true_efficiency_below_one(self):
        assert 0.0 < cooling_cop(88, p_laser_W=20.0) < 1.0


class TestBaffledFinSink:
    def test_uses_convective_resistance_not_alpha(self):
        s = BaffledFinSink(88, 400e-6)
        assert s.r_th_K_per_W == pytest.approx(simscale_convective_r_th(88))
        assert s.alpha_end_to_end == pytest.approx(simscale_alpha(88))
        assert s.r_th_K_per_W < s.alpha_end_to_end

    def test_htc_matches_the_requested_resistance(self):
        area = 347.55e-6
        s = BaffledFinSink(88, area)
        assert 1.0 / (s.htc_si() * area) == pytest.approx(s.r_th_K_per_W, rel=1e-9)

    def test_reports_its_fan_power(self):
        s = BaffledFinSink(200, 400e-6)
        assert s.parasitic_known
        assert s.parasitic_power_W() == pytest.approx(simscale_fan_power(200))

    def test_hotspot_penalty_is_referenced_end_to_end(self):
        """The penalty is a property of the die, not of the fins."""
        s = BaffledFinSink(88, 400e-6)
        assert s.hotspot_penalty == pytest.approx(simscale_beta(88) / simscale_alpha(88))
        assert s.hotspot_penalty > 4.0

    def test_faster_air_never_raises_temperature(self):
        prev = None
        for cfm in (10, 30, 88, 133, 200):
            r = BaffledFinSink(cfm, 400e-6).r_th_K_per_W
            if prev is not None:
                assert r < prev
            prev = r


class TestTraceReplication:
    def _trace(self):
        from HotGauge.power import BasicPowerTrace
        return BasicPowerTrace({'Core0/FPUs': np.array([1.0]),
                                'Core1/FPUs': np.array([2.0]),
                                'Core0': np.array([1.0]),
                                'BUSES': np.array([9.0])}, 1.0)

    def test_tiles_round_robin_and_conserves_per_core_power(self):
        from HotGauge.thermal.leakage_feedback import replicate_trace_cores
        out = replicate_trace_cores(self._trace(), 6).powers
        assert out['Core4/FPUs'] == pytest.approx(1.0)   # 4 % 2 == 0
        assert out['Core5/FPUs'] == pytest.approx(2.0)   # 5 % 2 == 1
        assert len([k for k in out if k.endswith('/FPUs')]) == 6

    def test_non_core_keys_pass_through_once(self):
        from HotGauge.thermal.leakage_feedback import replicate_trace_cores
        out = replicate_trace_cores(self._trace(), 6).powers
        assert out['BUSES'] == pytest.approx(9.0)
        assert sum(1 for k in out if k == 'BUSES') == 1

    def test_refuses_to_drop_cores(self):
        from HotGauge.thermal.leakage_feedback import replicate_trace_cores
        with pytest.raises(ValueError):
            replicate_trace_cores(self._trace(), 1)

    def test_bare_core_roots_stay_aggregates_at_any_index(self):
        """Otherwise Core8.. get counted as leaf power in the drop accounting."""
        from HotGauge.thermal.leakage_feedback import _is_mcpat_aggregate
        assert _is_mcpat_aggregate('Core0')
        assert _is_mcpat_aggregate('Core127')
        assert not _is_mcpat_aggregate('iALU_0')


class TestNoPowerUnits:
    def test_avx_is_power_free_for_any_core_index(self):
        """Hardcoding range(8) capped the pipeline at 8 cores with KeyError: 'AVXs_10'."""
        from HotGauge.configuration.power_model import is_no_power_unit
        for i in (0, 7, 10, 33, 127):
            assert is_no_power_unit('AVXs_{}'.format(i))

    def test_real_blocks_are_not_power_free(self):
        from HotGauge.configuration.power_model import is_no_power_unit
        assert not is_no_power_unit('FPUs_10')
        assert not is_no_power_unit('AVXs')
