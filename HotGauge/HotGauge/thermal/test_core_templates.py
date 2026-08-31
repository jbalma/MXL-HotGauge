"""Tests for the Golden Cove / Redwood Cove core template. Pure Python, no toolchain.

The template exists to do what ``accelerator_floorplan`` does for GA100 and could not do for a
CPU core until the pack arrived: published areas, an arrangement read off an annotated plate,
``source_image`` per block, and an assertion that the areas sum. These are the checks the pack
README asks a caller to run, kept as tests so they run every time.
"""
import math
import os
import tempfile

import pytest

from HotGauge.thermal import pack_areas
from HotGauge.thermal import core_templates as CT

pytestmark = pytest.mark.skipif(not pack_areas.pack_available(),
                                reason='the 314 MB floorplan pack is not checked out')


class TestTheTemplateClosesByConstruction:
    def test_golden_cove_blocks_sum_to_the_published_core_total(self):
        t = CT.golden_cove()
        assert t.assert_closes() == pytest.approx(7.123)

    def test_redwood_cove_likewise(self):
        assert CT.redwood_cove().assert_closes() == pytest.approx(5.330)

    def test_closure_is_asserted_at_construction_not_on_request(self):
        """Every rescale and re-weighting goes through the constructor, so a slip cannot escape."""
        t = CT.golden_cove()
        with pytest.raises(ValueError) as e:
            CT.CoreTemplate('bad', 'x', '7nm', 7.123, {'a': 1.0}, {'a': 'img'}, 1.5,
                            'p', 'a')
        assert 'partition the core exactly' in str(e.value)

    def test_both_uncore_modes_close(self):
        for mode in ('block', 'distributed'):
            for fn in (CT.golden_cove, CT.redwood_cove):
                t = fn(uncore_mode=mode)
                assert t.assert_closes() == pytest.approx(t.total_mm2)

    def test_the_six_published_areas_survive_unchanged_in_block_mode(self):
        """'distributed' inflates them by the residual; 'block' must not."""
        t = CT.golden_cove(split_nested=False, uncore_mode='block')
        pub = pack_areas.non_overlapping_blocks('Golden Cove (P-core)')
        for name, b in pub.items():
            assert t.blocks[name] == pytest.approx(b['area_mm2'])


class TestTheNestedSplitUsesThePacksFinestStructure:
    def test_splitting_recovers_the_published_parents_exactly(self):
        t = CT.golden_cove(uncore_mode='block')
        assert t.blocks['fpu_excl_fma'] + t.blocks['fma_eus_port_0_1'] == pytest.approx(0.986)
        assert (t.blocks['ooo_sched_and_retire'] + t.blocks['fpu_register_file']
                + t.blocks['int_register_file']) == pytest.approx(1.322)
        arrays = sum(v for k, v in t.blocks.items() if k.startswith('l2_data_'))
        assert arrays + t.blocks['l2_control'] == pytest.approx(1.646)

    def test_the_labelled_L2_arrays_sum_to_the_published_capacity(self):
        """384 + 256 + 256 + 384 KB = the 1.25 MB the plate prints. The check on the labels."""
        assert sum(CT.L2_DATA_ARRAYS_KB) == 1280

    def test_the_L2_splits_into_array_and_control_rather_than_one_uniform_block(self):
        """SRAM and logic do not leak alike; one block hides the difference the loop resolves."""
        t = CT.golden_cove()
        arrays = sum(v for k, v in t.blocks.items() if k.startswith('l2_data_'))
        assert 0.2 < arrays / 1.646 < 0.8

    def test_every_block_still_carries_a_source_image(self):
        t = CT.golden_cove()
        for name in t.blocks:
            assert t.sources.get(name), name


class TestGeometry:
    def test_the_blocks_tile_the_outline_without_overlapping(self):
        t = CT.golden_cove()
        g = t.geometry()
        w, h = t.outline_mm()
        assert sum(r[2] * r[3] for r in g.values()) == pytest.approx(w * h, rel=1e-9)
        items = list(g.items())
        for i, (na, a) in enumerate(items):
            assert a[0] >= -1e-9 and a[1] >= -1e-9, na
            assert a[0] + a[2] <= w + 1e-9 and a[1] + a[3] <= h + 1e-9, na
            for nb, b in items[i + 1:]:
                overlap = (min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]) > 1e-9 and
                           min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]) > 1e-9)
                assert not overlap, '{} overlaps {}'.format(na, nb)

    def test_each_blocks_rectangle_has_its_published_area(self):
        t = CT.golden_cove()
        for name, (x, y, w, h) in t.geometry().items():
            assert w * h == pytest.approx(t.blocks[name], rel=1e-9), name

    def test_the_outline_has_the_aspect_measured_off_the_plate(self):
        t = CT.golden_cove()
        w, h = t.outline_mm()
        assert w / h == pytest.approx(CT.GOLDEN_COVE_ASPECT)

    def test_the_arrangement_agrees_with_the_plates_own_pixels(self):
        """Two independent readings of one design: a transcribed area table, and a colour
        segmentation of the layout drawing. They are not expected to agree closely -- annotation
        overlays are approximate and a watermark washes out part of the plate -- but a systematic
        disagreement would mean the arrangement encoded here is not the one on the plate."""
        c = CT.arrangement_consistency()
        assert c['worst_abs_error'] < 0.25, c
        assert c['blocks']['frontend_branch_decode_l1i_op']['error'] == pytest.approx(0.0,
                                                                                      abs=0.05)


class TestTheRescaleHasAMeasuredErrorBar:
    """Golden Cove -> Redwood Cove is the pack README's own recipe with a published answer."""

    def test_the_pair_really_is_a_three_quarter_rescale(self):
        r = CT.rescale_error_vs_published()
        assert r['scale'] == pytest.approx(0.748, abs=0.005)

    def test_a_uniform_rescale_is_good_to_about_twenty_percent_per_block(self):
        r = CT.rescale_error_vs_published()
        assert 0.10 < r['max_abs_error'] < 0.30
        assert r['mean_abs_error'] < 0.20

    def test_and_the_L2_is_where_it_fails_because_the_L2_is_what_changed(self):
        """Redwood carries 2 MB against Golden Cove's 1.25 MB, so a uniform rescale must miss."""
        r = CT.rescale_error_vs_published()
        worst = max(r['blocks'], key=lambda k: abs(r['blocks'][k]['error']))
        assert worst == 'l2_cache'
        assert r['blocks']['l2_cache']['error'] < 0    # predicted too small

    def test_rescaling_preserves_the_mix_exactly(self):
        t = CT.golden_cove()
        s = t.rescale_to(3.0)
        for name in t.blocks:
            assert s.blocks[name] / s.total_mm2 == pytest.approx(t.blocks[name] / t.total_mm2)


class TestSRAMLinearityIsCheckedNotAssumed:
    def test_published_L2_area_is_linear_in_capacity(self):
        """The assumption behind pricing the 384 KB arrays off the published 256 KB block."""
        checks = CT.sram_linearity_check()
        assert checks, 'no cache-area table found in the pack'
        for chip, d in checks.items():
            for kb, err in d['linearity_error_vs_smallest']:
                assert abs(err) < 0.05, (chip, kb, err)


class TestWritingAFloorplan:
    def test_it_writes_and_the_areas_survive_the_grid(self):
        from HotGauge.thermal.accelerator_floorplan import block_areas_mm2
        t = CT.golden_cove()
        with tempfile.NamedTemporaryFile(suffix='.flp', delete=False) as f:
            path = f.name
        try:
            _, classes = t.write_flp(path, cell_um=10.0)
            got = block_areas_mm2(path)
            assert set(got) == set(t.blocks)
            assert sum(got.values()) == pytest.approx(t.total_mm2, rel=1e-3)
            assert set(classes.values()) >= {'fma', 'l2_array', 'l2_ctrl', 'frontend'}
        finally:
            os.unlink(path)

    def test_a_grid_too_coarse_to_resolve_the_core_is_refused_not_rounded(self):
        """The published decomposition contains structure the catalogue's own 50 um grid cannot
        resolve -- the uncore strip is 77 um and the integer register file 329 x 310 um. Silently
        accepting the distortion would corrupt the density accounting every result reads."""
        t = CT.golden_cove()
        with tempfile.NamedTemporaryFile(suffix='.flp', delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError) as e:
                t.write_flp(path, cell_um=50.0)
            assert 'distorts the density accounting' in str(e.value)
        finally:
            os.unlink(path)


class TestProvenanceIsAttachedAndHonest:
    def test_areas_are_published_geometry_is_not_and_power_is_not(self):
        t = CT.golden_cove()
        assert t.calibrated_area is True
        assert t.calibrated_geometry is False
        assert t.calibrated_power is False

    def test_the_uncore_placement_is_recorded_because_it_is_a_choice(self):
        """Golden Cove's residual can be a block; Redwood's 0.002 mm^2 cannot be anything."""
        assert CT.golden_cove().uncore_mode == 'block'
        assert CT.redwood_cove().uncore_mode == 'distributed'

    def test_provenance_and_assumptions_are_stated(self):
        for fn in (CT.golden_cove, CT.redwood_cove):
            t = fn()
            assert len(t.provenance) > 60
            assert len(t.assumptions) > 60
