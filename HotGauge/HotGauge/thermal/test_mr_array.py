"""Tests for the photonic cooling array as a real object in the stack.

The point of these is not that the arithmetic works. It is that the array now has **geometry**,
and geometry costs something: a plan that used to cool a 142 x 13 um block in isolation now
engages a tile hundreds of microns across and cools everything else beneath it too. Several tests
below exist specifically to pin that cost down so it cannot quietly disappear again.
"""

import os
import tempfile
import unittest

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
