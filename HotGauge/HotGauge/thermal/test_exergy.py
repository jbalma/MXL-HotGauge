"""Tests for the exergy accounting. Pure Python, no toolchain.

The numbers in Chapter 1 of ``docs/Photonic_Cooling_Devices___v9.pdf`` are the reference: if these
tests stop matching the book, one of the two has moved and it matters which.
"""
import math
import pytest

from HotGauge.thermal import exergy as EX


class TestAgainstTheBooksOwnNumbers:
    """Section 1.14 tabulates phi at T_0 = 295 K. Reproducing it is the acceptance test."""

    @pytest.mark.parametrize('T_h,phi', [(350, 0.157), (400, 0.26), (500, 0.41),
                                         (600, 0.51), (700, 0.58)])
    def test_carnot_factor_matches_the_book(self, T_h, phi):
        assert EX.carnot_factor(T_h) == pytest.approx(phi, abs=0.005)

    def test_lifting_350_to_500_nearly_triples_the_recoverable_exergy(self):
        """The sentence the whole architecture argument rests on."""
        assert EX.carnot_factor(500) / EX.carnot_factor(350) == pytest.approx(2.6, abs=0.15)

    def test_the_self_powering_condition_goes_from_impossible_to_plausible(self):
        """Section 1.16: the required anti-Stokes efficiency collapses as T_h rises."""
        hot = EX.eta_AS_required(0.85, 0.92, 600)
        cold = EX.eta_AS_required(0.85, 0.92, 350)
        assert cold > 1.5          # above 1 is not physically reachable
        assert hot < 0.7
        assert cold / hot > 3


class TestSigns:
    def test_a_chip_at_ambient_has_no_exergy(self):
        assert EX.carnot_factor(295.0, 295.0) == pytest.approx(0.0)

    def test_a_sub_ambient_block_is_negative_and_deliberately_not_clamped(self):
        """A tile cooled below ambient is a consumer, not a source. Clamping to zero would hide
        that, and the sign is the honest signal."""
        assert EX.carnot_factor(250.0, 295.0) < 0

    def test_zero_or_negative_absolute_temperature_is_refused(self):
        with pytest.raises(ValueError):
            EX.carnot_factor(0.0)


class TestTheLPCCeiling:
    def test_the_ceiling_sits_between_the_carnot_factor_and_one(self):
        """Equation (1.13): the pump-derived part is fully recoverable, the heat-derived part is
        Carnot-limited, so the ceiling is their weighted mean."""
        for T in (350, 500, 700):
            phi = EX.carnot_factor(T)
            c = EX.lpc_ceiling(0.5, T)
            assert phi < c < 1.0

    def test_with_no_anti_stokes_cooling_all_the_fluorescence_is_pump_derived(self):
        assert EX.lpc_ceiling(0.0, 350) == pytest.approx(1.0)

    def test_the_ceiling_rises_with_chip_temperature(self):
        assert EX.lpc_ceiling(0.5, 600) > EX.lpc_ceiling(0.5, 350)

    def test_loop_gain_crosses_one_as_the_chip_gets_hotter(self):
        lo = EX.loop_gain(0.9, 0.95, 1.2, 350)
        hi = EX.loop_gain(0.9, 0.95, 1.2, 700)
        assert hi > lo


class TestTheExergyMap:
    def _field(self):
        temps = {'hot': 400.0, 'warm': 350.0, 'cold': 320.0, 'dark': 500.0}
        powers = {'hot': 10.0, 'warm': 10.0, 'cold': 10.0, 'dark': 0.0}
        return temps, powers

    def test_a_block_with_no_power_contributes_nothing_however_hot(self):
        """Exergy is phi * P. A hot block dissipating nothing is worth nothing, which is the
        whole reason this is not a temperature map."""
        t, p = self._field()
        m = EX.exergy_map(t, p)
        assert 'dark' not in m['per_block']

    def test_the_die_integral_is_the_sum_of_the_parts(self):
        t, p = self._field()
        m = EX.exergy_map(t, p)
        assert m['die_exergy_W'] == pytest.approx(
            sum(d['exergy_W'] for d in m['per_block'].values()))
        assert m['die_power_W'] == pytest.approx(30.0)

    def test_hotter_blocks_carry_more_exergy_at_equal_power(self):
        t, p = self._field()
        m = EX.exergy_map(t, p)['per_block']
        assert m['hot']['exergy_W'] > m['warm']['exergy_W'] > m['cold']['exergy_W']

    def test_the_reservoir_used_is_recorded_because_the_wrong_one_flatters_the_answer(self):
        t, p = self._field()
        m = EX.exergy_map(t, p, temperature_is='junction')
        assert m['temperature_is'] == 'junction'
        assert 'overstate' in m['note']

    def test_power_weighted_temperature_ignores_unpowered_blocks(self):
        t, p = self._field()
        tw = EX.power_weighted_temperature(t, p)
        assert tw == pytest.approx((400 + 350 + 320) / 3.0)


class TestZoneAdditiveFOM:
    """Equation (10.29): hot zones contribute performance at a wide phi, cold zones shrink the
    denominator through the leakage they stop drawing."""

    def test_a_cold_zone_saving_leakage_improves_the_figure_of_merit(self):
        base = [{'name': 'compute', 'T_h_K': 500, 'perf_gain': 1.0, 'p_inj_W': 10.0,
                 'q_c_W': 10.0, 'cop': 2.0}]
        with_cold = base + [{'name': 'sram', 'T_h_K': 250, 'perf_gain': 0.0, 'p_inj_W': 0.0,
                             'q_c_W': 2.0, 'cop': 2.0, 'd_p_leak_W': 5.0}]
        assert EX.zone_additive_fom(with_cold)['fom'] > EX.zone_additive_fom(base)['fom']

    def test_each_zone_carries_its_own_carnot_factor(self):
        r = EX.zone_additive_fom([{'name': 'a', 'T_h_K': 500, 'perf_gain': 1.0, 'p_inj_W': 1.0},
                                  {'name': 'b', 'T_h_K': 300, 'perf_gain': 1.0, 'p_inj_W': 1.0}])
        phis = {z['zone']: z['phi'] for z in r['zones']}
        assert phis['a'] > phis['b']

    def test_the_denominator_is_the_sum_of_zone_costs(self):
        r = EX.zone_additive_fom([{'name': 'a', 'T_h_K': 400, 'perf_gain': 2.0, 'p_inj_W': 3.0},
                                  {'name': 'b', 'T_h_K': 400, 'perf_gain': 1.0, 'p_inj_W': 1.0}])
        assert r['numerator'] == pytest.approx(3.0)
        assert r['denominator'] == pytest.approx(4.0)
        assert r['fom'] == pytest.approx(0.75)
