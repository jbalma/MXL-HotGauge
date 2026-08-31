"""Tests for power-map shaping (HotGauge.thermal.power_shape).

Pure arithmetic on dicts -- no floorplan file, no solver. The one thing that must hold for the
concentration experiment to mean anything is that the two arms differ ONLY in shape: same total
power, same die, same everything else. Most of these assert exactly that.
"""
import numpy as np
import pytest

from HotGauge.power import BasicPowerTrace
from HotGauge.thermal.power_shape import (uniform_density_map, scale_map_to_density,
                                          block_power_map, concentration)

AREAS = {'a': 1.0, 'b': 3.0, 'c': 6.0}
SHAPED = {'a': 8.0, 'b': 1.0, 'c': 1.0}          # 8 W/mm^2 on 'a', 0.17 on 'c'


def test_uniform_map_is_uniform_and_sums_to_the_total():
    m, q = uniform_density_map(AREAS, 20.0)
    assert q == pytest.approx(2.0)
    assert sum(m.values()) == pytest.approx(20.0)
    for b, a in AREAS.items():
        assert m[b] / a == pytest.approx(q)


def test_uniform_map_has_zero_gini_and_peak_equal_to_mean():
    """The defining property. If this fails the 'no hot block' arm has a hot block."""
    m, _ = uniform_density_map(AREAS, 20.0)
    c = concentration(m, AREAS)
    assert c['gini'] == pytest.approx(0.0, abs=1e-12)
    assert c['peak_over_mean'] == pytest.approx(1.0)
    assert c['peak_W_per_mm2'] == pytest.approx(c['mean_W_per_mm2'])


def test_zero_area_die_is_refused():
    with pytest.raises(ValueError):
        uniform_density_map({'a': 0.0}, 1.0)


def test_negative_total_is_refused():
    with pytest.raises(ValueError):
        uniform_density_map(AREAS, -1.0)


def test_scale_preserves_shape_and_hits_the_density():
    scaled, f = scale_map_to_density(SHAPED, AREAS, 2.0)
    assert sum(scaled.values()) == pytest.approx(2.0 * sum(AREAS.values()))
    # shape is untouched: every block keeps its share
    for b in SHAPED:
        assert scaled[b] / sum(scaled.values()) == pytest.approx(
            SHAPED[b] / sum(SHAPED.values()))
    assert f == pytest.approx(20.0 / 10.0)


def test_the_two_arms_differ_only_in_shape():
    """The experiment's whole validity: same total, same die, different Gini."""
    d = 2.0
    flat, _ = uniform_density_map(AREAS, d * sum(AREAS.values()))
    shaped, _ = scale_map_to_density(SHAPED, AREAS, d)
    assert sum(flat.values()) == pytest.approx(sum(shaped.values()))
    cf, cs = concentration(flat, AREAS), concentration(shaped, AREAS)
    assert cf['mean_W_per_mm2'] == pytest.approx(cs['mean_W_per_mm2'])
    assert cf['gini'] == pytest.approx(0.0, abs=1e-12)
    assert cs['gini'] > 0.3
    assert cs['peak_over_mean'] > 4.0


def test_empty_map_is_refused_rather_than_scaled_to_nothing():
    with pytest.raises(ValueError):
        scale_map_to_density({'a': 0.0, 'b': 0.0}, AREAS, 2.0)


# ---------------------------------------------------------------------------
# block_power_map -- keeping aggregates out of the die average
# ---------------------------------------------------------------------------
def test_block_power_map_separates_aggregates():
    """`[!]` McPAT aggregates are in the trace but never reach the die.

    Counting them in a die average is how a 2.0 W/mm^2 die gets reported as 4.3.
    """
    tr = BasicPowerTrace({'a': np.array([1.0]), 'b': np.array([2.0]),
                          'Processor': np.array([99.0]),
                          'Processor/Total Cores': np.array([50.0])}, 1.0e-3)
    on, off = block_power_map(tr, AREAS)
    assert on == {'a': 1.0, 'b': 2.0}
    assert off == pytest.approx(149.0)


def test_block_power_map_accepts_a_plain_dict():
    on, off = block_power_map({'a': [4.0], 'zzz': [1.0]}, AREAS)
    assert on == {'a': 4.0}
    assert off == pytest.approx(1.0)


def test_block_power_map_reads_the_requested_step():
    tr = BasicPowerTrace({'a': np.array([1.0, 7.0])}, 1.0e-3)
    assert block_power_map(tr, AREAS, step=1)[0] == {'a': 7.0}
