"""Tests for the photonic cooling array as a real object in the stack.

The point of these is not that the arithmetic works. It is that the array now has **geometry**,
and geometry costs something: a plan that used to cool a 142 x 13 um block in isolation now
engages a tile hundreds of microns across and cools everything else beneath it too. Several tests
below exist specifically to pin that cost down so it cannot quietly disappear again.
"""

import os
import tempfile
import unittest
import pytest

from HotGauge.thermal.mr_array import (tile_grid, write_mr_floorplan, project_plan_to_tiles,
                                       tile_powers_for_stack, coverage_report,
                                       DEFAULT_PITCH_UM)


def _blocks(**kw):
    return kw


class TestTileGrid(unittest.TestCase):

    def test_tiles_cover_the_chip_without_gaps_or_overlap(self):
        w, h = 8800.0, 6100.0
        tiles = tile_grid(w, h, pitch_um=500.0, cell_um=100.0)
        area = sum(t['w'] * t['h'] for t in tiles)
        self.assertAlmostEqual(area, w * h, delta=1.0)

    def test_boundaries_are_snapped_to_the_thermal_grid(self):
        """Adjacent-in-float tiles come back overlapping once 3D-ICE quantises them."""
        tiles = tile_grid(8800.0, 6100.0, pitch_um=500.0, cell_um=100.0)
        for t in tiles:
            for v in (t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h']):
                self.assertAlmostEqual(v / 100.0, round(v / 100.0), places=9,
                                       msg='{} is off the 100 um grid at {}'.format(t['name'], v))

    def test_tiles_reach_the_chip_edge(self):
        """3D-ICE rejects a floorplan outside the chip; a short last column is an arithmetic
        artifact, not a design, so the last row and column stretch."""
        w, h = 8750.0, 6050.0
        tiles = tile_grid(w, h, pitch_um=500.0, cell_um=50.0)
        self.assertAlmostEqual(max(t['x'] + t['w'] for t in tiles), w, places=6)
        self.assertAlmostEqual(max(t['y'] + t['h'] for t in tiles), h, places=6)

    def test_pitch_finer_than_the_grid_is_refused(self):
        """A tile the solver cannot mesh is not a tile."""
        with self.assertRaises(ValueError):
            tile_grid(8800.0, 6100.0, pitch_um=25.0, cell_um=100.0)

    def test_fill_below_one_leaves_gaps(self):
        full = tile_grid(4000.0, 4000.0, pitch_um=500.0, cell_um=50.0, fill=1.0)
        gapped = tile_grid(4000.0, 4000.0, pitch_um=500.0, cell_um=50.0, fill=0.6)
        self.assertEqual(len(full), len(gapped))
        self.assertLess(sum(t['w'] * t['h'] for t in gapped),
                        sum(t['w'] * t['h'] for t in full))

    def test_names_are_unique(self):
        tiles = tile_grid(8800.0, 6100.0, pitch_um=500.0, cell_um=100.0)
        self.assertEqual(len(set(t['name'] for t in tiles)), len(tiles))


class TestProjection(unittest.TestCase):

    def setUp(self):
        self.tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)  # 2 x 2
        self.assertEqual(len(self.tiles), 4)

    def test_all_of_the_plan_arrives(self):
        blocks = _blocks(A=(100.0, 100.0, 200.0, 200.0))
        tp = project_plan_to_tiles({'A': 7.5}, blocks, self.tiles)
        self.assertAlmostEqual(sum(tp.values()), 7.5, places=9)

    def test_a_block_inside_one_tile_lands_entirely_on_it(self):
        blocks = _blocks(A=(100.0, 100.0, 200.0, 200.0))
        tp = project_plan_to_tiles({'A': 4.0}, blocks, self.tiles)
        hit = [k for k, v in tp.items() if v > 0]
        self.assertEqual(len(hit), 1)
        self.assertAlmostEqual(tp[hit[0]], 4.0, places=9)

    def test_a_block_straddling_two_tiles_splits_by_area(self):
        # 400 um wide centred on the x boundary at 1000: half in each column, one row.
        blocks = _blocks(A=(800.0, 100.0, 400.0, 200.0))
        tp = project_plan_to_tiles({'A': 4.0}, blocks, self.tiles)
        hit = sorted(v for v in tp.values() if v > 0)
        self.assertEqual(len(hit), 2)
        self.assertAlmostEqual(hit[0], 2.0, places=6)
        self.assertAlmostEqual(hit[1], 2.0, places=6)

    def test_an_uneven_straddle_splits_in_the_right_ratio(self):
        # 3/4 of the block left of the boundary, 1/4 right of it.
        blocks = _blocks(A=(700.0, 100.0, 400.0, 200.0))
        tp = project_plan_to_tiles({'A': 8.0}, blocks, self.tiles)
        hit = sorted((v for v in tp.values() if v > 0), reverse=True)
        self.assertAlmostEqual(hit[0], 6.0, places=6)
        self.assertAlmostEqual(hit[1], 2.0, places=6)

    def test_zero_and_negative_entries_are_ignored(self):
        blocks = _blocks(A=(100.0, 100.0, 200.0, 200.0), B=(100.0, 100.0, 200.0, 200.0))
        tp = project_plan_to_tiles({'A': 0.0, 'B': -3.0}, blocks, self.tiles)
        self.assertAlmostEqual(sum(tp.values()), 0.0, places=12)

    def test_a_block_outside_every_tile_is_an_error(self):
        """Silently losing the cooling would read as an expensive device that does not work."""
        blocks = _blocks(A=(50000.0, 50000.0, 100.0, 100.0))
        with self.assertRaises(ValueError):
            project_plan_to_tiles({'A': 1.0}, blocks, self.tiles)

    def test_a_plan_naming_an_unknown_block_is_an_error(self):
        with self.assertRaises(KeyError):
            project_plan_to_tiles({'ghost': 1.0}, _blocks(A=(0.0, 0.0, 10.0, 10.0)), self.tiles)

    def test_every_tile_appears_in_the_stack_powers(self):
        """A floorplan element with no power entry is an unsubstituted placeholder, not a zero."""
        tp = tile_powers_for_stack({}, self.tiles)
        self.assertEqual(set(tp), set(t['name'] for t in self.tiles))

    def test_stack_powers_are_negative(self):
        blocks = _blocks(A=(100.0, 100.0, 200.0, 200.0))
        tp = tile_powers_for_stack(project_plan_to_tiles({'A': 4.0}, blocks, self.tiles),
                                   self.tiles)
        self.assertAlmostEqual(min(tp.values()), -4.0, places=9)
        self.assertLessEqual(max(tp.values()), 0.0)


class TestCollateralCost(unittest.TestCase):
    """The geometric penalty the old block-level formulation could not express."""

    def test_cooling_a_thin_block_engages_far_more_area_than_requested(self):
        tiles = tile_grid(8800.0, 6100.0, pitch_um=500.0, cell_um=100.0)
        # RBB on the 34-core die: 142 x 13 um, the block the cliff results name as hottest.
        blocks = _blocks(RBB=(2000.0, 2000.0, 142.0, 13.0))
        tp = project_plan_to_tiles({'RBB': 1.0}, blocks, tiles)
        cov = coverage_report({'RBB': 1.0}, tp, blocks, tiles)
        # One or two tiles, depending on whether the block happens to straddle a boundary --
        # which is itself the point: at this size, where the block sits is luck.
        self.assertIn(cov['n_engaged'], (1, 2))
        self.assertGreater(cov['collateral_area_ratio'], 100.0,
                           'a 142 x 13 um block under a 500 um tile should engage two orders of '
                           'magnitude more die area than it asked for')

    def test_a_plan_aligned_with_the_grid_has_no_collateral(self):
        tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)
        blocks = _blocks(A=(0.0, 0.0, 1000.0, 1000.0))
        tp = project_plan_to_tiles({'A': 1.0}, blocks, tiles)
        cov = coverage_report({'A': 1.0}, tp, blocks, tiles)
        self.assertAlmostEqual(cov['collateral_area_ratio'], 1.0, places=6)

    def test_finer_pitch_lowers_the_collateral(self):
        blocks = _blocks(A=(2000.0, 2000.0, 200.0, 200.0))
        ratios = []
        for pitch in (1000.0, 500.0, 200.0):
            tiles = tile_grid(8800.0, 6100.0, pitch_um=pitch, cell_um=100.0)
            tp = project_plan_to_tiles({'A': 1.0}, blocks, tiles)
            ratios.append(coverage_report({'A': 1.0}, tp, blocks, tiles)['collateral_area_ratio'])
        self.assertTrue(all(a >= b for a, b in zip(ratios, ratios[1:])),
                        'collateral should fall as the pitch gets finer, got {}'.format(ratios))

    def test_projection_conserves_watts(self):
        tiles = tile_grid(8800.0, 6100.0, pitch_um=500.0, cell_um=100.0)
        blocks = _blocks(A=(1234.0, 2345.0, 900.0, 700.0), B=(4000.0, 1000.0, 300.0, 40.0))
        plan = {'A': 3.0, 'B': 1.25}
        tp = project_plan_to_tiles(plan, blocks, tiles)
        cov = coverage_report(plan, tp, blocks, tiles)
        self.assertAlmostEqual(cov['W_requested'], cov['W_projected'], places=9)


class TestCollateralMetric(unittest.TestCase):
    """The collateral figure has been wrong twice; both mistakes are pinned here.

    First it counted a tile's FULL area whenever it carried any power at all, so snapped slivers
    of neighbouring tiles were reported as cooling at full strength -- the per-block case came
    back as 12.6x when the watts were almost entirely on one tile. The fix for that computed a
    power-weighted MEAN tile area, which is a different quantity again and reported 0.0x at fine
    pitch. It now sums the area of tiles carrying at least ``share_floor`` of the removal.
    """

    def test_a_sliver_of_overlap_does_not_count_as_cooling(self):
        tiles = tile_grid(4000.0, 4000.0, pitch_um=1000.0, cell_um=100.0)
        # Overhangs the tile boundary at 1000 by 1 um: 99.9% of the block is in the first tile.
        blocks = _blocks(A=(1.0, 1.0, 1000.0, 900.0))
        tp = project_plan_to_tiles({'A': 4.0}, blocks, tiles)
        cov = coverage_report({'A': 4.0}, tp, blocks, tiles)
        self.assertGreater(cov['n_engaged'], cov['n_material'],
                           'the sliver should be engaged but not material')
        self.assertLess(cov['collateral_area_ratio'], cov['collateral_any_overlap'])

    def test_collateral_falls_monotonically_as_the_pitch_narrows(self):
        """The headline of the pitch sweep. If this is not monotone the metric is broken."""
        blocks = _blocks(A=(2000.0, 2000.0, 2913.0, 241.0))
        ratios = []
        for pitch in (2000.0, 1000.0, 500.0, 200.0, 100.0):
            tiles = tile_grid(8800.0, 6100.0, pitch_um=pitch, cell_um=50.0)
            tp = project_plan_to_tiles({'A': 3.0}, blocks, tiles)
            ratios.append(coverage_report({'A': 3.0}, tp, blocks, tiles)['collateral_area_ratio'])
        self.assertTrue(all(a >= b for a, b in zip(ratios, ratios[1:])),
                        'collateral must fall as the pitch narrows, got {}'.format(ratios))

    def test_share_floor_is_adjustable(self):
        tiles = tile_grid(4000.0, 4000.0, pitch_um=1000.0, cell_um=100.0)
        blocks = _blocks(A=(1.0, 1.0, 1000.0, 900.0))
        tp = project_plan_to_tiles({'A': 4.0}, blocks, tiles)
        strict = coverage_report({'A': 4.0}, tp, blocks, tiles, share_floor=0.5)
        loose = coverage_report({'A': 4.0}, tp, blocks, tiles, share_floor=0.0)
        self.assertLessEqual(strict['n_material'], loose['n_material'])


class TestFloorplanFile(unittest.TestCase):

    def test_written_floorplan_uses_placeholders_not_literal_zeros(self):
        """A literal 0.0 passes through str.format untouched and the solve runs unpowered."""
        tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)
        with tempfile.TemporaryDirectory() as d:
            path = write_mr_floorplan(os.path.join(d, 'MR.flp'), tiles)
            text = open(path).read()
        self.assertIn('{powers[', text)
        self.assertNotIn('power values 0.0', text)
        for t in tiles:
            self.assertIn('{}powers[{}]{}'.format('{', t['name'], ']}'.replace(']}', '}')), text)

    def test_written_floorplan_accepts_negative_powers(self):
        tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)
        with tempfile.TemporaryDirectory() as d:
            path = write_mr_floorplan(os.path.join(d, 'MR.flp'), tiles)
            powers = {t['name']: '{:.6f}'.format(-1.5) for t in tiles}
            filled = open(path).read().format(powers=powers)
        self.assertIn('-1.500000', filled)
        self.assertNotIn('{powers[', filled)


if __name__ == '__main__':
    unittest.main()


# ---------------------------------------------------------------------------
# The physical requirement: extraction tracks the dissipation beneath it
# ---------------------------------------------------------------------------
class TestExtractionTracksPowerDensity:
    """A tile's negative power must follow the power density of the silicon under it.

    This is the device's premise, not a modelling convenience: the pixel layer senses the local
    temperature under each tile (via the fluorescence spectrum), a controller reads that signal,
    and the laser response is steered and scaled to match. So the projection from a block-level
    plan onto tiles has to preserve *where* the heat is, not merely how much of it there is.

    The failure this guards against is the one the placement fix already had to correct once:
    cooling that is accounted for globally but lands in the wrong place still produces plausible
    temperatures, and reads as a working device.
    """

    def _die(self):
        """Four 1000x1000 um blocks in a row, power density 1:2:4:8."""
        blocks = {'B{}'.format(i): (i * 1000.0, 0.0, 1000.0, 1000.0) for i in range(4)}
        powers = {'B{}'.format(i): float(2 ** i) for i in range(4)}
        return blocks, powers

    def test_proportional_extraction_reproduces_the_power_density_map(self):
        """Removal per unit area under each block must track dissipation per unit area."""
        blocks, powers = self._die()
        tiles = tile_grid(4000.0, 1000.0, pitch_um=1000.0, cell_um=50.0)
        total_W = sum(powers.values())
        budget = 3.0
        plan = {b: budget * p / total_W for b, p in powers.items()}

        tile_plan = project_plan_to_tiles(plan, blocks, tiles)
        assert sum(tile_plan.values()) == pytest.approx(budget, abs=1e-9)

        # One tile per block here, so the comparison is direct.
        by_name = {t['name']: t for t in tiles}
        removal_density, power_density = [], []
        for b, (bx, by, bw, bh) in sorted(blocks.items()):
            over = [t for t in tiles
                    if t['x'] < bx + bw and t['x'] + t['w'] > bx
                    and t['y'] < by + bh and t['y'] + t['h'] > by]
            assert over, b
            w_removed = sum(tile_plan[t['name']] for t in over)
            area = sum(by_name[t['name']]['w'] * by_name[t['name']]['h'] for t in over)
            removal_density.append(w_removed / area)
            power_density.append(powers[b] / (bw * bh))

        ratios = [r / p for r, p in zip(removal_density, power_density)]
        assert max(ratios) / min(ratios) == pytest.approx(1.0, rel=1e-6), (
            'removal density does not track power density: {}'.format(ratios))

    def test_a_hot_block_draws_more_than_a_cold_one_at_the_same_size(self):
        blocks, powers = self._die()
        tiles = tile_grid(4000.0, 1000.0, pitch_um=1000.0, cell_um=50.0)
        plan = {b: p for b, p in powers.items()}
        tile_plan = project_plan_to_tiles(plan, blocks, tiles)
        got = sorted(v for v in tile_plan.values() if v > 0)
        assert got == pytest.approx([1.0, 2.0, 4.0, 8.0]), got

    def test_a_coarse_tile_spreads_removal_over_everything_beneath_it(self):
        """Honest about the geometric cost: one tile over two blocks cannot cool just one.

        The watts are conserved and land under the requested block, but they are shared with its
        neighbour. That is a property of the pitch, and it is what the tile-pitch study measures
        -- it must not be papered over by the projection.
        """
        blocks, _ = self._die()
        coarse = tile_grid(4000.0, 1000.0, pitch_um=2000.0, cell_um=50.0)
        tile_plan = project_plan_to_tiles({'B0': 4.0}, blocks, coarse)
        assert sum(tile_plan.values()) == pytest.approx(4.0)
        engaged = [t for t in coarse if tile_plan[t['name']] > 0]
        assert len(engaged) == 1
        assert engaged[0]['w'] > 1000.0, 'the engaged tile is wider than the block it cools'

    def test_extraction_stays_on_the_die_footprint(self):
        """The array is matched to the die, never to the cold plate above it.

        Every 3D-ICE layer spans the floorplan footprint, so an overhanging heat-sink base must
        not drag the tile array out with it -- the pixels are bonded to the silicon.
        """
        blocks, _ = self._die()
        tiles = tile_grid(4000.0, 1000.0, pitch_um=1000.0, cell_um=50.0)
        assert sum(t['w'] * t['h'] for t in tiles) == pytest.approx(4000.0 * 1000.0)
        assert max(t['x'] + t['w'] for t in tiles) == pytest.approx(4000.0)
        assert max(t['y'] + t['h'] for t in tiles) == pytest.approx(1000.0)


def _tmp():
    return tempfile.mkdtemp()


class TestArrayWiring:
    """The shared wiring six drivers use. Its job is to make the two bugs found wiring the first
    driver impossible to re-introduce in the other five."""

    FLP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                       'examples', 'floorplans', 'outputs',
                       'skylake10nm_7core_0_3D-ICE_template.flp')

    def _wiring(self, tmp_path, **kw):
        from HotGauge.thermal.mr_array import ArrayWiring
        return ArrayWiring(self.FLP, str(tmp_path), **kw)

    def test_it_writes_a_tile_floorplan_to_disk_as_a_path(self):
        """ICESim fills the template per run and takes a PATH. Handing it the contents fails far
        downstream with 'File name too long'."""
        w = self._wiring(_tmp(), pitch_um=2000.0)
        assert os.path.isfile(w.mr_flp_template)
        assert w.solver_kwargs()['mr_flp_template'] == w.mr_flp_template

    def test_powers_start_at_zero_and_stay_in_stack_convention(self):
        w = self._wiring(_tmp(), pitch_um=2000.0)
        assert sum(w.powers.values()) == pytest.approx(0.0)
        w.set_mr_powers({t['name']: -0.25 for t in w.tiles})
        assert sum(w.powers.values()) == pytest.approx(-0.25 * len(w.tiles))

    def test_set_mr_powers_does_not_convert_the_sign_again(self):
        """CoolingApplication has already run the plan through tile_powers_for_stack. Converting
        a second time flips removal into heating -- a wrong answer, not an error."""
        w = self._wiring(_tmp(), pitch_um=2000.0)
        w.set_mr_powers({t['name']: -1.0 for t in w.tiles})
        assert all(v <= 0 for v in w.powers.values())

    def test_solver_kwargs_reflect_the_current_plan(self):
        """Re-read for every solver: the planner revises between solves."""
        w = self._wiring(_tmp(), pitch_um=2000.0)
        before = w.solver_kwargs()['mr_powers']
        w.set_mr_powers({t['name']: -2.0 for t in w.tiles})
        after = w.solver_kwargs()['mr_powers']
        assert sum(before.values()) == pytest.approx(0.0)
        assert sum(after.values()) == pytest.approx(-2.0 * len(w.tiles))

    def test_planner_kwargs_are_what_run_mr_clipping_expects(self):
        w = self._wiring(_tmp(), pitch_um=2000.0)
        kw = w.planner_kwargs()
        assert set(kw) == {'tiles', 'tile_blocks', 'set_mr_powers'}
        assert kw['tiles'] is w.tiles and kw['tile_blocks'] is w.blocks
        assert callable(kw['set_mr_powers'])

    def test_the_tiles_cover_the_die_and_nothing_more(self):
        w = self._wiring(_tmp(), pitch_um=2000.0)
        cw, ch = w.chip_um
        assert sum(t['w'] * t['h'] for t in w.tiles) == pytest.approx(cw * ch)

    def test_a_coarser_pitch_gives_fewer_tiles(self):
        """The first-generation device is 4-16 tiles, so the coarse end is the one that matters."""
        fine = self._wiring(_tmp(), pitch_um=1000.0)
        coarse = self._wiring(_tmp(), pitch_um=4000.0)
        assert len(coarse.tiles) < len(fine.tiles)


class TestWiringFollowsTheStack:
    """Placement is derived from the stack, not from a flag that can disagree with it.

    Both directions of disagreement are silent: tiles wired against a single-die stack compute a
    plan that lands nowhere, and an array stack left unwired carries an inert slab that only adds
    resistance. Deriving it removes the choice.
    """

    STK = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stack_templates')
    FLP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                       'examples', 'floorplans', 'outputs',
                       'skylake10nm_7core_0_3D-ICE_template.flp')

    def test_it_recognises_a_stack_with_and_without_an_array(self):
        from HotGauge.thermal.mr_array import stack_carries_an_array
        assert not stack_carries_an_array(os.path.join(self.STK, 'skylake.stk'))
        assert stack_carries_an_array(os.path.join(self.STK, 'direct_die_mr_powered.stk'))

    def test_an_unreadable_stack_is_not_an_array(self):
        from HotGauge.thermal.mr_array import stack_carries_an_array
        assert not stack_carries_an_array(os.path.join(self.STK, 'does_not_exist.stk'))

    def test_asking_for_an_array_the_stack_cannot_carry_is_an_error(self):
        """Falling back would silently downgrade the physics to an upper bound."""
        from HotGauge.thermal.mr_array import wiring_for_stack
        with pytest.raises(ValueError, match='land nowhere'):
            wiring_for_stack(os.path.join(self.STK, 'skylake.stk'), self.FLP, _tmp())

    def test_the_legacy_placement_is_selected_deliberately(self):
        from HotGauge.thermal.mr_array import wiring_for_stack
        assert wiring_for_stack(os.path.join(self.STK, 'skylake.stk'), self.FLP, _tmp(),
                                want_array=False) is None

    def test_an_array_stack_gets_wiring(self):
        from HotGauge.thermal.mr_array import wiring_for_stack
        w = wiring_for_stack(os.path.join(self.STK, 'direct_die_mr_powered.stk'), self.FLP,
                             _tmp(), pitch_um=2000.0)
        assert w is not None and len(w.tiles) > 0


class TestDevicePitchIsAnAnnotation:
    """The device is a tile COUNT. Turning it into one absolute pitch is the bug these pin.

    The catalogue was briefly configured at a single global 5 mm, derived by converting the demo
    system's 4-16 tiles over ~200 mm^2 into a pitch and applying that pitch to every die. On the
    28-53 mm^2 7-core dies that is ONE tile and on the 34-core -- the die under most of the sweep
    -- it is TWO. Nothing errors; the projection conserves, the accounting balances, and the
    result is a sweep of spot policy against two tiles.
    """

    def test_it_converts_a_count_on_whatever_die_it_is_given(self):
        from HotGauge.thermal.mr_array import device_pitch_range_um
        # (area mm^2, expected fine um, expected coarse um) -- 16 and 4 tiles.
        for area, fine, coarse in ((53.0, 1820, 3640), (101.0, 2512, 5025),
                                   (196.0, 3500, 7000), (826.0, 7185, 14370)):
            got = device_pitch_range_um(area)
            assert got[0] == pytest.approx(fine, rel=1e-3)
            assert got[1] == pytest.approx(coarse, rel=1e-3)

    def test_it_is_derived_from_the_recorded_geometry_not_hardcoded(self):
        import math
        from HotGauge.thermal.mr_array import device_pitch_range_um
        from HotGauge.thermal.published_reference import DEMO_SYSTEM, DIE_GEOMETRY
        area = DIE_GEOMETRY['AMD_RYZEN_AI_5_340']['die_area_mm2']
        lo, hi = DEMO_SYSTEM['n_tiles']
        fine, coarse = device_pitch_range_um()
        assert fine == pytest.approx(1000.0 * math.sqrt(area / hi))
        assert coarse == pytest.approx(1000.0 * math.sqrt(area / lo))

    def test_one_absolute_pitch_across_dies_is_not_a_constant_tile_count(self):
        """The arithmetic of the mistake, stated so it cannot be made twice.

        A tile count fixes pitch = sqrt(area/n), so pitch scales as sqrt(area). Carry the demo
        die's pitch across to a die a quarter the size and the tile count falls by four.
        """
        from HotGauge.thermal.mr_array import device_pitch_range_um
        DEMO_AREA, SMALL_AREA = 200.0, 53.0
        for i, want_on_demo in enumerate((16.0, 4.0)):      # fine end, coarse end
            pitch_mm = device_pitch_range_um(DEMO_AREA)[i] / 1000.0
            on_demo = DEMO_AREA / pitch_mm ** 2
            on_small = SMALL_AREA / pitch_mm ** 2
            assert on_demo == pytest.approx(want_on_demo, rel=1e-6)
            # ...and the same pitch on the smaller die gives area-proportionally fewer.
            assert on_small == pytest.approx(want_on_demo * SMALL_AREA / DEMO_AREA, rel=1e-6)
        # At the coarse end that is barely one tile on the 7-core die.
        assert SMALL_AREA / (device_pitch_range_um(DEMO_AREA)[1] / 1000.0) ** 2 < 2.0

    def test_the_device_is_coarser_than_the_ladder_on_the_workhorse_die(self):
        """The thing worth reporting to a device roadmap, pinned as a fact rather than a note."""
        from HotGauge.thermal.mr_array import device_pitch_range_um
        fine, coarse = device_pitch_range_um(101.0)         # the 34-core die
        assert fine > 2000.0, (fine, 'device should sit beyond the ladder top')
        assert (fine, coarse) == pytest.approx((2512.0, 5025.0), rel=1e-3)


class TestShellConfigLadder:
    """scripts/array_config.sh carries the ladder as literals; this stops them going stale."""

    CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                       'scripts', 'array_config.sh')
    LADDER = [50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0]

    def _cfg(self):
        if not os.path.isfile(self.CFG):
            pytest.skip('scripts/array_config.sh not present')
        return open(self.CFG).read()

    def _var(self, name):
        import re
        m = re.search(r'^{}="\$\{{{}:-([^}}]*)\}}"'.format(name, name), self._cfg(), re.M)
        assert m, '{} not defined in array_config.sh'.format(name)
        return m.group(1)

    def test_the_ladder_is_the_swept_variable(self):
        assert [float(x) for x in self._var('PITCH_SWEEP_UM').split()] == self.LADDER

    def test_the_fixed_pitch_is_the_back_catalogue_value(self):
        """500 um, so arm deltas stay comparable to prior work.

        Absolute temperatures already are not comparable -- --spreading corrected the boundary --
        so moving the pitch too would leave nothing that could be compared with anything.
        """
        from HotGauge.thermal.mr_array import DEFAULT_PITCH_UM
        assert float(self._var('PITCH_UM')) == 500.0 == DEFAULT_PITCH_UM

    def test_the_fixed_pitch_is_on_the_ladder(self):
        assert float(self._var('PITCH_UM')) in self.LADDER

    def test_the_device_is_recorded_as_a_count_not_a_pitch(self):
        """If this ever becomes a pitch again, the collapse has happened again."""
        cfg = self._cfg()
        assert 'DEVICE_TILES=' in cfg
        assert self._var('DEVICE_TILES') == '4-16'

    def test_the_stacks_are_still_the_settled_baseline(self):
        import re
        cfg = self._cfg()
        arr = re.search(r'^ARRAY_STACK="\$\{ARRAY_STACK:-(.+?)\}"', cfg, re.M).group(1)
        ctl = re.search(r'^CONTROL_STACK="\$\{CONTROL_STACK:-(.+?)\}"', cfg, re.M).group(1)
        for spec in (arr, ctl):
            assert spec.startswith('spec:package=direct_die,')
        assert arr.replace('mr=${MR_MATERIAL}', 'MR') == ctl.replace('mr=none', 'MR')
        assert 'src=${BURIAL_UM}' in arr and 'src=${BURIAL_UM}' in ctl


class TestWiringPathsAreAbsolute:
    """A relative --out-dir must not send the MR floorplan somewhere nobody asked for.

    ExecutableJob fills the floorplan template inside a multiprocessing worker whose cwd is the
    HotGauge package directory, so a relative path resolves against THAT. Every driver in the
    repo happened to pass an absolute out-dir, so this only surfaced when a new one did not --
    and it surfaced as a FileNotFoundError naming HotGauge/HotGauge/script_runner/..., which
    reads as a broken install rather than a bad argument.
    """

    def test_the_floorplan_path_is_absolute(self):
        import tempfile
        from HotGauge.thermal.mr_array import ArrayWiring
        flp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                           'examples', 'floorplans', 'outputs',
                           'skylake10nm_7core_0_3D-ICE_template.flp')
        d = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(d)
            w = ArrayWiring(flp, 'relative_out', pitch_um=2000.0)
            assert os.path.isabs(w.mr_flp_template)
            assert os.path.isfile(w.mr_flp_template)
            # ...and it is where the caller meant, not merely somewhere absolute.
            assert os.path.realpath(w.mr_flp_template).startswith(os.path.realpath(d))
        finally:
            os.chdir(cwd)


class TestStalePlanGuard:
    """A plan that no solver ever read must stop the run, not produce a field.

    This is the highest-value guard in the module because the failure has no other symptom: the
    projection conserves its watts, the accounting reports the full budget removed, and the
    temperatures are the UNCOOLED ones. It was found by a probe that reported 3.000 W removed
    and +0.0000 K of cooling.
    """

    def _wiring(self):
        import tempfile
        from HotGauge.thermal.mr_array import ArrayWiring
        flp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                           'examples', 'floorplans', 'outputs',
                           'skylake10nm_7core_0_3D-ICE_template.flp')
        return ArrayWiring(flp, tempfile.mkdtemp(), pitch_um=2000.0)

    def _plan(self, w, watts):
        from HotGauge.thermal.mr_array import tile_powers_for_stack
        return tile_powers_for_stack({w.tiles[0]['name']: watts}, w.tiles)

    def test_replacing_an_unread_plan_is_refused(self):
        w = self._wiring()
        w.set_mr_powers(self._plan(w, 1.0))      # first plan: exempt, nothing before it
        w.solver_kwargs()                        # a solver read it
        w.set_mr_powers(self._plan(w, 2.0))      # second plan...
        with pytest.raises(RuntimeError, match='no solver ever read'):
            w.set_mr_powers(self._plan(w, 3.0))  # ...replaced without ever being solved

    def test_the_correct_loop_is_not_flagged(self):
        """Build a fresh solver per solve -- the documented usage -- and nothing fires."""
        w = self._wiring()
        for watts in (1.0, 2.0, 3.0, 4.0):
            w.set_mr_powers(self._plan(w, watts))
            w.solver_kwargs()                    # stands in for constructing the solver
        assert True

    def test_repeated_reads_of_one_plan_are_fine(self):
        """The leakage loop builds one solver per iteration against an unchanged plan."""
        w = self._wiring()
        w.set_mr_powers(self._plan(w, 1.0))
        for _ in range(5):
            w.solver_kwargs()
        w.set_mr_powers(self._plan(w, 2.0))

    def test_the_first_plan_is_exempt(self):
        """Drivers legitimately zero the tiles before the baseline solve."""
        w = self._wiring()
        w.set_mr_powers({t['name']: 0.0 for t in w.tiles})

    def test_the_error_names_the_fix(self):
        w = self._wiring()
        w.set_mr_powers(self._plan(w, 1.0))
        w.solver_kwargs()
        w.set_mr_powers(self._plan(w, 2.0))
        with pytest.raises(RuntimeError) as e:
            w.set_mr_powers(self._plan(w, 3.0))
        msg = str(e.value)
        assert 'CONSTRUCTION' in msg and 'solver_kwargs()' in msg


class TestDegenerateGrid:
    """One tile over the whole die is a uniform slab, and it must not arrive silently.

    It is easy to reach by accident: device_pitch_um() is 5 mm, derived from a ~200 mm^2 mobile
    die, and the catalogue's 7-core skylake die is 28 mm^2. Everything downstream still works --
    the projection conserves, the accounting balances -- so nothing else would notice.
    """

    def _wiring(self, pitch_um):
        import tempfile
        from HotGauge.thermal.mr_array import ArrayWiring
        flp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                           'examples', 'floorplans', 'outputs',
                           'skylake10nm_7core_0_3D-ICE_template.flp')
        return ArrayWiring(flp, tempfile.mkdtemp(), pitch_um=pitch_um)

    def test_a_single_tile_is_flagged(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger='HotGauge.thermal.mr_array'):
            w = self._wiring(20000.0)
        assert len(w.tiles) == 1
        assert w.degenerate
        assert 'NO spatial targeting' in caplog.text

    def test_a_real_grid_is_not_flagged(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger='HotGauge.thermal.mr_array'):
            w = self._wiring(500.0)
        assert len(w.tiles) > 1
        assert not w.degenerate
        assert 'NO spatial targeting' not in caplog.text

    def test_the_two_tile_case_that_used_to_run_silently_is_flagged(self):
        """Why the threshold moved from 1 to 4.

        At a single global 5 mm the 34-core die -- the die under 38 of the 44 --cores invocations
        in scripts/ -- gets TWO tiles. Under a <=1 threshold that ran with no warning at all, and
        a spot-policy sweep against two tiles measures nothing.
        """
        import logging, math, tempfile
        from HotGauge.thermal.mr_array import ArrayWiring, tile_grid
        flp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                           'examples', 'floorplans', 'outputs',
                           'skylake7nm_34core_3_3D-ICE_template.flp')
        if not os.path.isfile(flp):
            pytest.skip('34-core floorplan not present')
        w = ArrayWiring(flp, tempfile.mkdtemp(), pitch_um=5000.0)
        assert len(w.tiles) == 2, len(w.tiles)
        assert w.degenerate

    def test_the_ladder_top_is_not_degenerate_on_the_workhorse_die(self):
        """The ladder must not itself be in the vacuous regime, or it measures nothing either."""
        import tempfile
        from HotGauge.thermal.mr_array import ArrayWiring
        flp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                           'examples', 'floorplans', 'outputs',
                           'skylake7nm_34core_3_3D-ICE_template.flp')
        if not os.path.isfile(flp):
            pytest.skip('34-core floorplan not present')
        w = ArrayWiring(flp, tempfile.mkdtemp(), pitch_um=2000.0)
        assert len(w.tiles) >= 4 and not w.degenerate


def test_tile_power_schedule_switches_the_plan_on_and_off_per_slot():
    """§P0.25 (F4): a modulated array is the steady projection applied slot by slot, negative,
    every tile present in every slot, idle slots at zero."""
    import numpy as np
    from HotGauge.thermal.mr_array import tile_grid, tile_power_schedule, project_plan_to_tiles
    tiles = tile_grid(1000, 1000, pitch_um=500, cell_um=50)
    blocks = {'A': (0.0, 0.0, 400.0, 400.0), 'B': (600.0, 600.0, 300.0, 300.0)}
    plan = {'A': 2.0, 'B': 1.0}
    sched = tile_power_schedule([{}, plan, plan, {}], tiles, blocks)
    assert set(sched) == {t['name'] for t in tiles}
    for v in sched.values():
        assert v.shape == (4,) and v[0] == 0.0 and v[3] == 0.0 and (v <= 0).all()
    steady = project_plan_to_tiles(plan, blocks, tiles)
    tot = -sum(v[1] for v in sched.values())
    assert abs(tot - sum(steady.values())) < 1e-9 and abs(tot - 3.0) < 1e-9
