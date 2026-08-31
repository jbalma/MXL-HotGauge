"""Tests for the zone-separability metric. Pure Python, no toolchain.

The metric exists because the photonic-cooling architecture argument (book Sections 1.14, 10.8)
asks for a die held at two temperatures at once, and that is a floorplan property nothing here
measured before. The tests below pin the three things it would be easy to get quietly wrong: the
geometry of a shared edge, the thickness cancellation, and the refusal to extrapolate leakage
below the calibrated range.
"""
import math
import pytest

from HotGauge.thermal import thermal_zones as TZ


class TestSharedEdge:
    def test_two_abutting_blocks_share_their_overlap(self):
        a = (0.0, 0.0, 1.0, 2.0)
        b = (1.0, 0.5, 1.0, 1.0)          # touches a's right edge, overlapping 1.0 mm of it
        assert TZ.shared_edge_mm(a, b) == pytest.approx(1.0)
        assert TZ.shared_edge_mm(b, a) == pytest.approx(1.0)

    def test_blocks_that_only_touch_at_a_corner_share_nothing(self):
        assert TZ.shared_edge_mm((0, 0, 1, 1), (1, 1, 1, 1)) == pytest.approx(0.0)

    def test_separated_blocks_share_nothing(self):
        assert TZ.shared_edge_mm((0, 0, 1, 1), (2, 0, 1, 1)) == pytest.approx(0.0)

    def test_grid_snapping_does_not_break_adjacency(self):
        """Floorplan coordinates are snapped to the solver grid, so blocks that abut in the
        design abut to within a rounding step on disk. Without a tolerance every boundary in a
        real floorplan would measure zero."""
        a = (0.0, 0.0, 1.0, 1.0)
        b = (1.0004, 0.0, 1.0, 1.0)       # 0.4 um gap from snapping
        assert TZ.shared_edge_mm(a, b, tol_um=1.0) == pytest.approx(1.0)
        assert TZ.shared_edge_mm(a, b, tol_um=0.1) == pytest.approx(0.0)


class TestBoundaryLength:
    def _strip(self):
        # three 1x1 blocks in a row: cold | hot | hot
        return ({'c': (0, 0, 1, 1), 'h1': (1, 0, 1, 1), 'h2': (2, 0, 1, 1)},
                lambda n: 'cold' if n == 'c' else 'hot')

    def test_only_cross_zone_edges_count(self):
        geo, zf = self._strip()
        total, pairs = TZ.zone_boundary_mm(geo, zf)
        assert total == pytest.approx(1.0)                 # c|h1 only, not h1|h2
        assert pairs[('cold', 'hot')] == pytest.approx(1.0)

    def test_unzoned_blocks_are_not_a_boundary(self):
        geo, _ = self._strip()
        total, _ = TZ.zone_boundary_mm(geo, lambda n: 'cold' if n == 'c' else None)
        assert total == pytest.approx(0.0)


class TestTheThicknessCancellation:
    """The central physical result: thinning the die does not help isolate a zone."""

    def test_monolithic_conductance_is_independent_of_die_thickness(self):
        g = [TZ.boundary_conductance_W_per_K(5.0, 200, 350, thickness_um=t)
             for t in (25, 50, 200, 775)]
        assert all(x == pytest.approx(g[0]) for x in g)

    def test_and_it_equals_k_times_boundary_length(self):
        k = TZ.mean_silicon_k(200, 350)
        assert TZ.boundary_conductance_W_per_K(5.0, 200, 350) == pytest.approx(k * 5.0e-3)

    def test_a_trench_cuts_the_cross_section_and_that_does_help(self):
        mono = TZ.boundary_conductance_W_per_K(5.0, 200, 350)
        trenched = TZ.boundary_conductance_W_per_K(5.0, 200, 350,
                                                   trench_width_um=10, bridge_thickness_um=1)
        assert trenched == pytest.approx(mono * 0.1)

    def test_half_a_trench_is_refused_rather_than_guessed(self):
        with pytest.raises(ValueError) as e:
            TZ.boundary_conductance_W_per_K(5.0, 200, 350, trench_width_um=10)
        assert 'both' in str(e.value)


class TestSiliconConductivityRisesAsItCools:
    """Non-obvious and it makes the cold zone harder, so it must not be modelled as a constant."""

    def test_colder_silicon_conducts_better(self):
        assert TZ.silicon_k(200) > TZ.silicon_k(300) > TZ.silicon_k(400)

    def test_by_roughly_a_factor_of_two_between_200_and_350(self):
        assert TZ.silicon_k(200) / TZ.silicon_k(350) == pytest.approx(2.1, abs=0.3)

    def test_the_mean_across_a_gradient_is_between_its_endpoints(self):
        m = TZ.mean_silicon_k(200, 400)
        assert TZ.silicon_k(400) < m < TZ.silicon_k(200)


class TestLeakageSavingRefusesToExtrapolate:
    """McPAT rejects temperatures outside 300-400 K, so the calibrated curve stops at 310 K and
    CLAMPS below it. A saving computed at 200 K is the clamp, not physics, and must say so."""

    class _Model:
        # local-exponential stand-in that clamps below the calibration floor, as the real one does
        def scale(self, T):
            return 2.0 ** ((max(T, TZ.CALIBRATION_FLOOR_K) - 330.0) / 10.0)

    def test_a_saving_inside_the_measured_range_is_defensible(self):
        r = TZ.leakage_saving_W(1.0, 350, 320, self._Model(), 330)
        assert r['defensible'] is True
        assert r['unseen_K'] == 0.0
        assert r['saving_W'] > 0

    def test_a_saving_below_the_floor_is_flagged_with_how_much_is_unevidenced(self):
        r = TZ.leakage_saving_W(1.0, 350, 200, self._Model(), 330)
        assert r['defensible'] is False
        assert r['unseen_K'] == pytest.approx(110.0)
        assert r['evaluated_to_K'] == pytest.approx(TZ.CALIBRATION_FLOOR_K)
        assert 'unevidenced' in r['note']

    def test_and_the_clamp_means_cooling_further_buys_nothing_in_the_model(self):
        a = TZ.leakage_saving_W(1.0, 350, 310, self._Model(), 330)['saving_W']
        b = TZ.leakage_saving_W(1.0, 350, 150, self._Model(), 330)['saving_W']
        assert a == pytest.approx(b)


class TestTheVerdict:
    def test_a_long_boundary_makes_a_zone_unbuildable(self):
        geo = {'c': (0, 0, 1, 10), 'h': (1, 0, 1, 10)}      # 10 mm of shared edge
        r = TZ.zone_separability(geo, lambda n: 'cold' if n == 'c' else 'hot',
                                 0.05, 200, 350, TestLeakageSavingRefusesToExtrapolate._Model(),
                                 330)
        assert r['isolation_ratio'] < 1.0
        assert r['buildable'] is False
        assert r['conductance_excess'] > 100

    def test_the_spec_form_is_the_saving_divided_by_the_gradient(self):
        geo = {'c': (0, 0, 1, 1), 'h': (1, 0, 1, 1)}
        m = TestLeakageSavingRefusesToExtrapolate._Model()
        r = TZ.zone_separability(geo, lambda n: 'cold' if n == 'c' else 'hot',
                                 0.05, 250, 350, m, 330)
        assert r['max_conductance_W_per_K'] == pytest.approx(
            r['leakage_saving']['saving_W'] / 100.0)

    def test_putting_the_cold_zone_on_its_own_die_is_far_better_but_not_by_enough(self):
        """The comparison the monolithic answer forces: silicon path vs substrate path.

        On the stated inputs a 1 mm package gap beats monolithic silicon by ~44x. That is a large
        improvement and it is still short of the ~3000-6300x the measured floorplans ask for, so
        disaggregation is necessary and not sufficient -- the package needs a deliberate thermal
        break on top of it. Pinned here because it is the load-bearing arithmetic behind that
        conclusion."""
        mono = TZ.boundary_conductance_W_per_K(10.0, 200, 350)
        pkg = TZ.package_boundary_conductance_W_per_K(edge_mm=10.0, gap_mm=1.0)
        assert mono / pkg == pytest.approx(44.5, rel=0.05)
        assert mono / pkg < 3000.0
