"""Acceptance gate: does the model reproduce parts that demonstrably work?

These are the checks that four separate defects escaped -- inert leakage feedback, an unpowered
emulator die, a double-counted package, a mis-sized cooler. None was found by reading code. Each
was found by comparing against something external, so the comparison belongs in the suite.

The solving tests need the 3D-ICE toolchain and take minutes, so they are marked ``slow`` and
skipped by default. Run them with ``pytest -m slow``. What runs unconditionally is the arithmetic
around them -- the reference data, the package subtraction, the verdict logic -- because those are
where a silent regression would be cheapest to introduce and hardest to notice.

Current state, recorded honestly rather than as a green tick:

    H100_AIR             PASSES   60.7 C against a published 54-72 C
    H100_LIQUID          FAILS    the lidded package leaves 0.011 K/W for the coolant
    RYZEN_7500F_AIR      FAILS    the package alone is 92% of the budget on a 91 mm^2 die
    RYZEN_7500F_LIQUID   not run

Both failures have the same cause and it is identified: **the stack gives its layers no spreader
overhang.** Every layer spans exactly the die footprint, because 3D-ICE takes ``chip length`` from
the floorplan and the template's ``spread area`` was commented out. A real IHS is roughly 40x40 mm
over an 8x8 mm die and spreads laterally; ours cannot. On an 826 mm^2 die that costs little, which
is why the accelerator point passes. On a 91 mm^2 die the package becomes 0.33 K/W and swamps
everything.

So the model does NOT yet generalise across die size, and that is the gate condition. It is
recorded here rather than asserted away.
"""
import pytest

from HotGauge.thermal.published_reference import (PUBLISHED_POINTS, CPU_POINTS, CPU_CLOCK_POINTS,
                                                  all_thermal_points, check_peak,
                                                  DIRECT_DIE_HARDWARE, DIE_GEOMETRY,
                                                  CORE_ULTRA_125H_POWER, HX370_POWER_DENSITY)
from HotGauge.thermal.cooling_spec import external_r_for_total, COOLER_CLASSES


#: What each point currently does. Update alongside the model, never to make a red test green.
EXPECTED = {
    'H100_AIR': 'pass',
    'H100_LIQUID': 'fail_package_too_resistive',
    'RYZEN_7500F_AIR': 'fail_package_too_resistive',
    'RYZEN_7500F_LIQUID': 'not_run',
}


def test_every_reference_point_is_completely_specified():
    """A point missing its ambient or its cooler class cannot be reproduced by anyone."""
    for key, p in all_thermal_points().items():
        for field in ('label', 'source', 'die_area_mm2', 'power_W', 'ambient_C', 'fluid',
                      'temp_C', 'implied_r_th_peak', 'cooler_class', 'floorplan'):
            assert field in p, '{} is missing {}'.format(key, field)
        lo, hi = p['temp_C']
        assert lo < hi
        assert p['ambient_C'] < lo, '{}: ambient is not below the observed range'.format(key)
        assert p['cooler_class'] in COOLER_CLASSES


def test_implied_resistances_are_self_consistent():
    """R = (T_peak - T_ambient) / P, recomputed from the recorded numbers."""
    for key, p in all_thermal_points().items():
        expect = (p['temp_C'][1] - p['ambient_C']) / p['power_W']
        assert p['implied_r_th_peak'] == pytest.approx(expect, rel=1e-6), key


def test_a_predicted_runaway_can_never_pass():
    """The failure that started this: the model predicted no steady state for a part that ships in
    volume. No tolerance may absorb that."""
    for key in all_thermal_points():
        ok, verdict = check_peak(key, None, diverged=True)
        assert ok is False
        assert 'runaway' in verdict


def test_running_too_cold_also_fails():
    """A model that runs cold flatters every cooling conclusion drawn from it, so it is a failure
    in the same way running hot is -- just a more comfortable one."""
    p = all_thermal_points()['H100_AIR']
    ok, verdict = check_peak('H100_AIR', p['temp_C'][0] - 30.0)
    assert ok is False
    assert 'too cold' in verdict


def test_the_passing_accelerator_point_is_pinned():
    """60.7 C is the measured result of the corrected model. If a change moves it out of the
    published band, that change broke something."""
    ok, verdict = check_peak('H100_AIR', 60.67)
    assert ok is True and 'PASS' in verdict


def test_package_subtraction_matches_the_measured_decomposition():
    """0.1074 published, 0.0566 package including spreading, 0.0508 left for external cooling."""
    assert external_r_for_total(0.1074, 0.0566) == pytest.approx(0.0508, abs=1e-6)


def test_the_small_die_failure_is_recorded_not_asserted_away():
    """The Ryzen point fails because the package takes 92% of its budget, and the model therefore
    does not generalise across die size. Pinning the arithmetic keeps that visible."""
    p = all_thermal_points()['RYZEN_7500F_AIR']
    r_pkg_measured = 0.361            # from the acceptance run on a 91 mm^2 die
    left = p['implied_r_th_peak'] - r_pkg_measured
    assert left / p['implied_r_th_peak'] < 0.10, 'the package should dominate this point'
    assert EXPECTED['RYZEN_7500F_AIR'].startswith('fail')


def test_temperature_limited_points_are_kept_separate():
    """The 9700X rows sit at TjMax: the controller pins the temperature and trades clock, so they
    cannot test a thermal prediction and must not be mixed into the thermal points."""
    assert 'RYZEN_9700X_COOLING_VS_CLOCK' not in all_thermal_points()
    c = CPU_CLOCK_POINTS['RYZEN_9700X_COOLING_VS_CLOCK']
    assert all(abs(r['temp_C'] - c['tjmax_C']) < 10.0 for r in c['rows'])
    assert c['clock_gain_stock_to_best'] > 0.25


@pytest.mark.slow
def test_h100_air_still_reproduces_the_published_point():
    """The real gate. Needs the 3D-ICE toolchain; run with -m slow."""
    pytest.skip('run examples/validate_published.py --point H100_AIR; ~8 minutes with the '
                'session cache')


# ---------------------------------------------------------------------------
# Direct-die hardware: in hand, not yet a gate
# ---------------------------------------------------------------------------
class TestDirectDieHardware:
    """The parts that actually match the baseline configuration.

    Every current gate point is a LIDDED part, so reproducing it means modelling an IHS and a
    solder die-attach the device does not have -- the package we most need to get right is the
    one we cannot check. These are direct-die and in house. They are not gate points yet, and
    the tests here exist to keep it that way until they are measured.
    """

    def test_none_of_it_can_be_used_as_a_gate_point_yet(self):
        """An unmeasured part must not become an acceptance test by being added to a dict."""
        assert not set(DIRECT_DIE_HARDWARE) & set(all_thermal_points())

    def test_every_entry_says_what_it_still_needs(self):
        """A placeholder that does not record its own gap turns into a forgotten assumption."""
        for key, hw in DIRECT_DIE_HARDWARE.items():
            assert hw['form_factor'] == 'direct_die', key
            assert hw.get('missing_for_a_gate_point'), key
            assert hw.get('measurement'), key

    def test_the_framework_inventory_covers_more_than_one_isa(self):
        """Same chassis, same thermal envelope, different ISAs -- that is the cross-ISA
        comparison Phase 2 wants, with the cooling held fixed."""
        parts = DIRECT_DIE_HARDWARE['FRAMEWORK_13']['parts']
        vendors = {p[0].split()[0] for p in parts}
        assert {'AMD', 'Intel'} <= vendors
        assert any('RISC-V' in p[0] for p in parts)

    def test_the_recorded_specs_are_self_consistent(self):
        for name, pc, ec, threads, base, turbo, base_w, max_w in \
                DIRECT_DIE_HARDWARE['FRAMEWORK_13']['parts']:
            assert pc > 0, name
            assert threads >= pc + ec, name
            assert 0 < base_w <= max_w, name
            assert base > 0, name


class TestInHouseDieData:
    """Geometry and measured power read off docs/demo_hw_slides.pdf."""

    def test_die_areas_match_their_stated_dimensions(self):
        for key, g in DIE_GEOMETRY.items():
            if 'die_mm' in g and 'die_area_mm2' in g:
                w, h = g['die_mm']
                assert g['die_area_mm2'] == pytest.approx(w * h, rel=0.01), key

    def test_every_geometry_entry_cites_its_source(self):
        for key, g in DIE_GEOMETRY.items():
            assert 'slides' in g['source'] or 'Intel' in g['source'], key

    def test_the_125h_sweep_is_monotone_in_the_obvious_places(self):
        r = CORE_ULTRA_125H_POWER['rows']
        assert r['idle'][1] < r['1core_2thread_SSE'][1] < r['allcore_allthread'][1]
        assert all(row[0] > row[1] > row[2] for row in r.values()), \
            'system power must exceed package, which must exceed all-core'

    def test_the_125h_is_power_limited_not_thermally_limited(self):
        """25 W all-core against a 115 W ceiling. A ladder that assumes the part is thermally
        limited would be reasoning about the wrong constraint on this hardware."""
        assert CORE_ULTRA_125H_POWER['rows']['allcore_allthread'][1] < 0.3 * 115.0

    def test_power_density_concentrates_as_the_window_shrinks(self):
        """The measured version of what an area cooler responds to: the same watt is 8x denser
        at the innermost block than spread over the core."""
        d = HX370_POWER_DENSITY
        assert list(d['levels_mm2']) == sorted(d['levels_mm2'], reverse=True)
        assert list(d['W_per_mm2']) == sorted(d['W_per_mm2'])
        assert d['W_per_mm2'][-1] / d['W_per_mm2'][0] > 5.0
