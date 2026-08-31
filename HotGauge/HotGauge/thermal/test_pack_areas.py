"""Tests for the floorplan-pack reader. Pure Python, no toolchain.

Most of this file is the **three integration traps**. Each one returns a plausible wrong answer
rather than an error, so each gets a test that fails if the guard is removed:

1. summing a chip's rows across hierarchy levels (+9.55% on Golden Cove),
2. filtering ``manifest.csv`` on a folder name instead of a category value (zero rows),
3. reading the V/F anchor voltage from ``vd_v``-shaped guesses instead of ``voltage_v``.
"""
import pytest

from HotGauge.thermal import pack_areas

pytestmark = pytest.mark.skipif(not pack_areas.pack_available(),
                                reason='the 314 MB floorplan pack is not checked out')

GOLDEN = 'Golden Cove (P-core)'
REDWOOD = 'Redwood Cove (P-core)'


class TestTrap1HierarchyLevelsAreMixed:
    """block_areas.csv mixes parents and children, and a naive sum is wrong by ~10%."""

    def test_the_naive_sum_really_is_wrong_and_by_how_much(self):
        """Recorded as a test so the trap is measured, not just described."""
        c = pack_areas.area_closure(GOLDEN)
        assert c['naive_sum_error_frac'] == pytest.approx(0.0955, abs=0.001)
        assert c['n_nested_excluded'] == 4

    def test_the_non_overlapping_set_is_the_six_the_README_names(self):
        blocks = pack_areas.non_overlapping_blocks(GOLDEN)
        assert set(blocks) == {'frontend_branch_decode_l1i_op', 'ooo_sched_and_retire',
                               'load_store_with_l1d', 'fpu_incl_fma_eus', 'integer_execution',
                               'l2_cache'}

    def test_golden_cove_closes_to_the_published_total(self):
        c = pack_areas.assert_area_closure(GOLDEN)
        assert c['published_total_mm2'] == pytest.approx(7.123)
        assert c['sum_of_blocks_mm2'] == pytest.approx(7.027, abs=1e-3)
        assert abs(c['closure_err_frac']) == pytest.approx(0.0135, abs=0.001)

    def test_redwood_cove_closes_far_tighter(self):
        """0.04% -- the pack README quotes it and it is the confidence signal for the pair."""
        c = pack_areas.assert_area_closure(REDWOOD)
        assert abs(c['closure_err_frac']) < 0.001

    def test_a_chip_that_did_not_close_would_raise(self):
        with pytest.raises(ValueError) as e:
            pack_areas.assert_area_closure(GOLDEN, tol=0.001)
        assert 'transcription error' in str(e.value)

    def test_the_register_files_are_recorded_as_children_of_the_OoO_block(self):
        """Their NAMES say FPU and integer; the plate draws them on the OoO field."""
        nested = pack_areas.nested_children(GOLDEN)
        assert nested['fpu_register_file']['parent'] == 'ooo_sched_and_retire'
        assert nested['int_register_file']['parent'] == 'ooo_sched_and_retire'
        assert nested['fma_eus_port_0_1']['parent'] == 'fpu_incl_fma_eus'
        assert nested['l2_sram_block_256kb']['parent'] == 'l2_cache'

    def test_every_block_carries_the_plate_it_came_from(self):
        for name, b in pack_areas.non_overlapping_blocks(GOLDEN).items():
            assert b['source_image'], name


class TestTrap2ManifestCategoriesAreNotFolderNames:
    def test_the_folder_name_is_refused_with_the_right_value_in_the_message(self):
        with pytest.raises(ValueError) as e:
            pack_areas.manifest_rows(category='floorplans')
        assert 'die_floorplan_annotated' in str(e.value)

    def test_the_real_category_returns_the_annotated_layouts(self):
        rows = pack_areas.annotated_floorplans()
        assert len(rows) == 121

    def test_the_ISA_coverage_is_what_the_pack_claims(self):
        assert len(pack_areas.annotated_floorplans(isa='ARM')) == 11
        assert len(pack_areas.annotated_floorplans(isa='RISC-V')) == 3

    def test_block_diagrams_are_not_placement_bearing(self):
        """Their geometry means nothing and nothing may infer placement from them."""
        assert 'block_diagram' not in pack_areas.PLACEMENT_BEARING_CATEGORIES
        assert 'die_floorplan_annotated' in pack_areas.PLACEMENT_BEARING_CATEGORIES


class TestTrap3TheVoltageColumn:
    def test_two_anchors_carry_a_real_voltage(self):
        rows = pack_areas.vf_anchors_with_voltage()
        assert len(rows) == 2
        assert all(r['voltage_v'] == pytest.approx(0.75) for r in rows)
        assert all(r['freq_ghz'] == pytest.approx(2.8) for r in rows)

    def test_zero_would_raise_rather_than_report_none_found(self):
        with pytest.raises(ValueError) as e:
            pack_areas.vf_anchors_with_voltage(rows=[{'chip': 'x', 'voltage_v': None}])
        assert 'voltage_v' in str(e.value)


class TestThePowerPriors:
    """Six Arm rows carry area and power together; nothing else in the pack does at core level."""

    def test_the_measured_densities_are_the_ones_the_pack_publishes(self):
        by_chip = {}
        for d in pack_areas.power_density_priors():
            by_chip.setdefault(d['chip'], []).append(d['w_per_mm2'])
        assert min(by_chip['Neoverse V1']) == pytest.approx(0.476, abs=0.002)
        assert min(by_chip['Neoverse V2']) == pytest.approx(0.560, abs=0.002)
        assert min(by_chip['Neoverse N1']) == pytest.approx(0.870, abs=0.002)
        assert max(by_chip['Neoverse N1']) == pytest.approx(1.286, abs=0.002)
        assert by_chip['Dojo D1'][0] == pytest.approx(0.620, abs=0.002)

    def test_the_wide_vector_V_class_runs_cooler_per_mm2_than_the_compact_N_class(self):
        """The shape of the answer, and the axis the thermal work turns on.

        A wide machine spends area to go fast at a low clock; a compact one spends clock. It is an
        ACTIVITY difference and no amount of area re-weighting can see it, which is why the ISA
        floorplans redistributing a Skylake trace at a common density could not answer this.
        """
        by_chip = {}
        for d in pack_areas.power_density_priors():
            by_chip.setdefault(d['chip'], []).append(d['w_per_mm2'])
        assert max(by_chip['Neoverse V1']) < min(by_chip['Neoverse N1'])
        assert max(by_chip['Neoverse V2']) < min(by_chip['Neoverse N2'])

    def test_every_prior_lands_in_the_range_the_pack_calls_sane_for_a_logic_die(self):
        for d in pack_areas.power_density_priors():
            assert 0.3 <= d['w_per_mm2'] <= 2.0, d


class TestRefusalsRatherThanGuesses:
    def test_an_unknown_chip_raises(self):
        with pytest.raises(KeyError):
            pack_areas.chip_rows('No Such Part')

    def test_duplicate_block_names_are_refused_rather_than_summed(self):
        """Sapphire Rapids really does carry two rows called ``tile_total``.

        Both are filtered out here because ``tile_total`` is a whole, not a part -- but the guard
        exists for the case where a re-transcription duplicates a PART, where summing both would
        double count silently. Exercised on a synthetic row set so it is tested rather than
        assumed to be unreachable.
        """
        dupes = [{'vendor': 'V', 'chip': 'C', 'node': 'N', 'block': 'l2_cache',
                  'area_mm2': 1.0, 'power_w': None, 'note': '', 'source_image': 'x'},
                 {'vendor': 'V', 'chip': 'C', 'node': 'N', 'block': 'l2_cache',
                  'area_mm2': 2.0, 'power_w': None, 'note': '', 'source_image': 'x'}]
        with pytest.raises(ValueError) as e:
            pack_areas.non_overlapping_blocks('C', rows=dupes)
        assert 'two rows named' in str(e.value)

    def test_the_pack_itself_has_a_duplicated_row_and_it_is_a_whole_not_a_part(self):
        rows = pack_areas.load_block_areas()
        spr = [r for r in rows if r['chip'] == 'Sapphire Rapids XCC']
        assert [r['block'] for r in spr].count('tile_total') == 2
        assert 'tile_total' in pack_areas.TOTAL_BLOCKS
