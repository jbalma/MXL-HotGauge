"""Tests for the phase-1 floorplan metrics. Pure Python, no toolchain."""
import numpy as np
import pytest

from HotGauge.thermal.floorplan_metrics import (relative_plateau, peak_to_runner_up_gap,
                                                hot_region_depth,
                                                power_density_concentration, thermal_aspect,
                                                hot_block_thermal_aspect)


class TestRelativePlateauFixesTheDegeneracy:
    """The whole point: a floorplan metric must not depend on a device parameter that can move.

    'Plateau at dt_max' collapsed to the whole die when dt_max went from an unsourced 10 K to the
    demonstrated 45 K, because the die's own span is no larger than 45 K.
    """

    @staticmethod
    def _die(span_K, n=200, plateau_n=5, plateau_K=1.0):
        """A die with `plateau_n` blocks bunched near the peak and the rest spread over `span_K`."""
        top = [100.0 - i * (plateau_K / max(plateau_n - 1, 1)) for i in range(plateau_n)]
        rest = list(np.linspace(100.0 - span_K * 0.35, 100.0 - span_K, n - plateau_n))
        return {'b{}'.format(i): t for i, t in enumerate(top + rest)}

    def test_it_does_not_saturate_when_the_lift_exceeds_the_die_span(self):
        """The failure mode being fixed: an absolute width larger than the span counts everything."""
        temps = self._die(span_K=40.0)
        n_total = len(temps)
        absolute = sum(1 for t in temps.values() if t > max(temps.values()) - 45.0)
        assert absolute == n_total                      # the OLD metric: no information
        rel = relative_plateau(temps)
        assert rel['n_blocks'] < n_total                # the new one still discriminates

    def test_it_is_invariant_to_a_uniform_rescale_of_the_distribution(self):
        """Self-normalising: doubling every temperature difference must not change the count."""
        base = self._die(span_K=30.0)
        peak = max(base.values())
        stretched = {k: peak - 2.0 * (peak - v) for k, v in base.items()}
        assert (relative_plateau(base)['n_blocks']
                == relative_plateau(stretched)['n_blocks'])

    def test_a_concentrated_die_has_a_narrower_plateau_than_a_flat_one(self):
        flat = {'b{}'.format(i): 100.0 - i * 0.01 for i in range(200)}     # everything bunched
        peaked = self._die(span_K=40.0, plateau_n=2)
        assert relative_plateau(peaked)['n_blocks'] < relative_plateau(flat)['n_blocks']

    def test_it_reports_the_width_it_actually_used(self):
        """So a reader can see what was asked, rather than trusting the fraction."""
        temps = self._die(span_K=40.0)
        r = relative_plateau(temps, fraction=0.25)
        assert r['span_K'] == pytest.approx(40.0, abs=0.5)
        assert r['width_K'] == pytest.approx(0.25 * r['span_K'])
        assert r['share'] == pytest.approx(r['n_blocks'] / r['n_total'])

    def test_the_fraction_is_validated(self):
        temps = self._die(span_K=10.0)
        for bad in (0.0, -0.1, 1.5):
            with pytest.raises(ValueError):
                relative_plateau(temps, fraction=bad)


class TestPeakToRunnerUpGap:
    def test_it_is_the_top_two_difference(self):
        assert peak_to_runner_up_gap({'a': 90.0, 'b': 82.5, 'c': 10.0}) == pytest.approx(7.5)

    def test_one_block_has_no_runner_up(self):
        with pytest.raises(ValueError):
            peak_to_runner_up_gap({'a': 90.0})


class TestPowerDensityConcentration:
    def test_uniform_density_is_zero_gini(self):
        p = {'a': 2.0, 'b': 4.0, 'c': 6.0}
        a = {'a': 1.0, 'b': 2.0, 'c': 3.0}          # identical density everywhere
        r = power_density_concentration(p, a)
        assert r['gini'] == pytest.approx(0.0, abs=1e-9)

    def test_concentrated_density_scores_higher_than_even(self):
        areas = {'b{}'.format(i): 1.0 for i in range(10)}
        even = {k: 1.0 for k in areas}
        spiky = {k: (10.0 if k == 'b0' else 0.1) for k in areas}
        assert (power_density_concentration(spiky, areas)['gini']
                > power_density_concentration(even, areas)['gini'])

    def test_area_weighting_stops_small_blocks_outvoting_large_ones(self):
        """One large block carrying all the power must read as concentrated, not as even."""
        areas = {'big': 100.0, **{'s{}'.format(i): 0.01 for i in range(50)}}
        powers = {'big': 0.0, **{'s{}'.format(i): 1.0 for i in range(50)}}
        r = power_density_concentration(powers, areas)
        assert r['gini'] > 0.5      # 50 tiny hot blocks on a mostly-cold die IS concentrated

    def test_it_refuses_nonsense_geometry(self):
        with pytest.raises(ValueError):
            power_density_concentration({'a': 1.0}, {'a': 0.0})
        with pytest.raises(ValueError):
            power_density_concentration({'a': 1.0}, {'b': 1.0})


class _El(object):
    def __init__(self, name, minx, miny, w, h):
        self.name, self.minx, self.miny = name, minx, miny
        self.maxx, self.maxy = minx + w, miny + h


class _FP(object):
    def __init__(self, els, w, h):
        self._e = {e.name: e for e in els}
        self.minx, self.miny, self.maxx, self.maxy = 0.0, 0.0, w, h
    def __getitem__(self, k):
        return self._e[k]


class TestThermalAspect:
    def _fp(self):
        return _FP([_El('edge', 0.0, 0.0, 100.0, 100.0),
                    _El('centre', 4950.0, 3950.0, 100.0, 100.0)], 10000.0, 8000.0)

    def test_an_edge_block_scores_near_zero_and_a_central_one_near_one(self):
        fp = self._fp()
        assert thermal_aspect(fp, 'edge')['normalised'] < 0.05
        assert thermal_aspect(fp, 'centre')['normalised'] > 0.95

    def test_it_normalises_by_the_SHORTER_side(self):
        """On a long thin die, 'as central as this die allows' is set by the short dimension."""
        fp = self._fp()
        r = thermal_aspect(fp, 'centre')
        assert r['distance_um'] == pytest.approx(4000.0, abs=1.0)   # 8000 / 2
        assert r['normalised'] == pytest.approx(1.0, abs=0.01)

    def test_hot_block_variant_picks_the_hottest(self):
        fp = self._fp()
        r = hot_block_thermal_aspect(fp, {'edge': 60.0, 'centre': 90.0})
        assert r['block'] == 'centre' and r['peak_C'] == pytest.approx(90.0)


class TestHotRegionDepth:
    """The third metric: it predicts the saturation split the other two cannot see.

    Measured on the eleven workload shapes at fraction 0.05 -- degrades group 10.1-14.0 K,
    holds group 19.5-33.0 K, a clean 5.5 K gap with no overlap. relative_plateau overlaps by
    30 blocks in the WRONG direction; peak_to_runner_up_gap overlaps by 1.8 K.
    """

    @staticmethod
    def _die(depth_K, n=200, hot_frac=0.05, tail_K=40.0):
        """A die whose top `hot_frac` of blocks falls by `depth_K`, then a common tail."""
        n_hot = int(round(hot_frac * n))
        hot = [100.0 - depth_K * i / max(n_hot - 1, 1) for i in range(n_hot)]
        rest = list(np.linspace(100.0 - depth_K, 100.0 - tail_K, n - n_hot))
        return {'b{}'.format(i): t for i, t in enumerate(hot + rest)}

    def test_a_steep_hot_region_scores_higher_than_a_shallow_one(self):
        steep = self._die(depth_K=25.0)
        shallow = self._die(depth_K=5.0)
        assert (hot_region_depth(steep)['depth_K']
                > hot_region_depth(shallow)['depth_K'])

    def test_it_reports_which_block_it_measured_to(self):
        r = hot_region_depth(self._die(10.0, n=1000), fraction=0.05)
        assert r['n_blocks'] == 50 and r['n_total'] == 1000
        assert r['fraction'] == pytest.approx(0.05)

    def test_the_fraction_transfers_across_block_counts(self):
        """A block COUNT would not transfer between floorplans; a fraction does."""
        small = hot_region_depth(self._die(20.0, n=200))
        large = hot_region_depth(self._die(20.0, n=2000))
        assert small['depth_K'] == pytest.approx(large['depth_K'], rel=0.05)

    def test_it_is_robust_to_the_choice_of_fraction(self):
        """The measured split survives 0.02 to 0.20, so the 0.05 default is not delicate."""
        steep, shallow = self._die(25.0), self._die(5.0)
        for frac in (0.02, 0.05, 0.10, 0.20):
            assert (hot_region_depth(steep, frac)['depth_K']
                    > hot_region_depth(shallow, frac)['depth_K']), frac

    def test_it_sees_what_the_gap_cannot(self):
        """Two dies with the SAME peak-to-runner-up gap and different hot-region depth.

        This is the case that motivated the metric: the gap looks only at the top two blocks.
        """
        shallow = {'b0': 100.0, 'b1': 99.0}
        shallow.update({'b{}'.format(i): 98.5 for i in range(2, 100)})
        steep = {'b0': 100.0, 'b1': 99.0}
        steep.update({'b{}'.format(i): 99.0 - 0.5 * i for i in range(2, 100)})
        assert (peak_to_runner_up_gap(shallow)
                == pytest.approx(peak_to_runner_up_gap(steep)))
        # Identical gap, 2.3x the depth: 100->96.5 over the top 5% against 100->98.5.
        assert (hot_region_depth(steep)['depth_K']
                > 2 * hot_region_depth(shallow)['depth_K'])

    def test_the_fraction_is_validated(self):
        t = self._die(10.0)
        for bad in (0.0, -0.1, 1.5):
            with pytest.raises(ValueError):
                hot_region_depth(t, fraction=bad)

    def test_one_block_has_no_depth(self):
        with pytest.raises(ValueError):
            hot_region_depth({'a': 90.0})


def test_hot_region_depth_is_documented_as_failing_the_transfer_test():
    """It predicts saturation within a floorplan and REVERSES SIGN across floorplans
    (+0.800 on 11 workloads, -0.886 on 6 floorplans). LADDER_GEN0 section 3's rule -- any metric
    that does not predict is dropped -- applies. It is kept as a within-floorplan diagnostic only,
    and the docstring has to keep saying so, because the function still looks usable.
    """
    import inspect
    from HotGauge.thermal import floorplan_metrics
    doc = inspect.getdoc(floorplan_metrics.hot_region_depth) or ''
    assert 'FAILS THE TRANSFER TEST' in doc
    assert 'must not be used to compare designs' in doc
