"""Tests for the ARM/RISC-V/x86 floorplan variants rebuilt on the floorplan pack.

Pure Python, no toolchain. Several tests here replace assertions that encoded the FIRST cut's
numbers, and the replacements say why:

* ``arm_v1 / arm_n2 == 1.70`` -- the press claim. The pack's own rows put V1 against N1 at
  1.80-2.19x, so the assertion now checks that published range instead.
* ``0 < core_area_scale <= 1.0`` -- the first cut expressed every non-x86 core as a fraction of
  the baseline. With published areas, V1 comes out LARGER than the model core, and the baseline
  is itself 1.67x smaller than a real iso-node x86 core.
* ``no variant reports an absolute mm^2`` -- written when no absolute area was known. Four of
  them are now published numbers, and hiding them would be the dishonest choice.
"""
import json
import os

import pytest

from HotGauge.thermal import pack_areas
from HotGauge.thermal.isa_floorplans import (
    ISA_VARIANTS, RETIRED_VARIANTS, reweight_area_stats, variant_summary, realised_group_fractions,
    baseline_group_fractions, published_mix, vector_multiple_from_width, l1_sensitivity,
    density_for, DECODE_FRACTION_OF_CORE, X86_VECTOR_MULTIPLE, GOLDEN_COVE_VECTOR_MULTIPLE,
    X86_VECTOR_BITS, BASELINE_CORE_MM2_7NM, SRAM_UNITS, GOLDEN_COVE_GROUPS,
    MAX_L1_SHARE_OF_GROUP)

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_BASE_JSON = os.path.join(_REPO, 'examples', 'floorplans', 'adjusted_14nm-area.json')

needs_pack = pytest.mark.skipif(not pack_areas.pack_available(),
                                reason='the 314 MB floorplan pack is not checked out')
needs_examples = pytest.mark.skipif(not os.path.isfile(_BASE_JSON),
                                    reason='examples/floorplans is not present')


def _base():
    with open(_BASE_JSON) as f:
        return json.load(f)


class TestTheISAArgumentIsRestatedNotAssumed:
    def test_decode_is_a_negligible_fraction_of_core_area_IN_THE_MODEL(self):
        assert DECODE_FRACTION_OF_CORE == pytest.approx(0.0334, abs=0.001)

    @needs_pack
    @needs_examples
    def test_but_the_published_frontend_is_a_quarter_of_a_real_core(self):
        """So the model's authority for dismissing the decode argument is gone, even though the
        pack cannot restore the argument -- its plate labels one block for the whole frontend."""
        gc = published_mix()
        model = baseline_group_fractions(_BASE_JSON)
        assert gc['frontend'] > 0.22
        assert model['frontend'] < 0.12
        assert gc['frontend'] / model['frontend'] > 2.0


class TestTheVectorMultipleWasWrongAndUnapplied:
    def test_the_pack_puts_the_vector_block_far_below_the_shipped_constant(self):
        """0.288 mm^2 of FMA EUs against 0.698 of the rest of the FP cluster."""
        assert GOLDEN_COVE_VECTOR_MULTIPLE == pytest.approx(0.4126, abs=0.001)
        assert X86_VECTOR_MULTIPLE / GOLDEN_COVE_VECTOR_MULTIPLE == pytest.approx(4.8, abs=0.1)

    def test_the_multiple_now_scales_with_published_vector_width(self):
        assert vector_multiple_from_width(X86_VECTOR_BITS) == pytest.approx(
            GOLDEN_COVE_VECTOR_MULTIPLE)
        assert vector_multiple_from_width(512) == pytest.approx(
            GOLDEN_COVE_VECTOR_MULTIPLE / 2.0)

    def test_the_variants_no_longer_share_one_vector_multiple(self):
        """The defect this replaces: all six generated floorplans had AVXs/FPUs = 1.981."""
        v = {r['key']: r['vector_multiple'] for r in variant_summary()}
        assert v['arm_n1'] < v['arm_v1'] < v['arm_a64fx']
        assert v['riscv_xiangshan'] == pytest.approx(v['arm_n1'])
        assert len({round(x, 6) for x in v.values()}) >= 3

    def test_ordering_follows_datapath_width_because_that_is_what_sets_it(self):
        rows = {r['key']: r for r in variant_summary()}
        for k, r in rows.items():
            if k == 'x86_skylake':
                continue                     # the shipped baseline keeps the shipped constant
            assert r['vector_multiple'] == pytest.approx(
                vector_multiple_from_width(r['vector_bits'])), k


@needs_pack
class TestTheAreasArePublishedNow:
    def test_the_four_published_cores_carry_their_published_area(self):
        want = {'x86_golden_cove': 7.123, 'x86_zen2': 3.54, 'arm_v1': 2.52, 'arm_n1': 1.15}
        for k, mm2 in want.items():
            assert ISA_VARIANTS[k].core_area_mm2 == pytest.approx(mm2)
            assert ISA_VARIANTS[k].area_provenance == 'published'

    def test_every_published_area_traces_to_a_pack_row(self):
        rows = pack_areas.load_block_areas()
        areas = {r['area_mm2'] for r in rows if r['area_mm2'] is not None}
        for k, v in ISA_VARIANTS.items():
            if v.area_provenance == 'published':
                assert v.core_area_mm2 in areas, k
                assert v.source_image, k

    def test_the_two_without_a_published_area_say_so(self):
        for k in ('arm_a64fx', 'riscv_xiangshan'):
            assert ISA_VARIANTS[k].core_area_mm2 is None
            assert ISA_VARIANTS[k].area_provenance == 'derived_from_microarchitecture'

    def test_the_V1_against_N1_ratio_is_the_packs_not_the_press_claim(self):
        """The first cut chained a "V1 is ~70% larger than N1" press claim. The pack's own rows
        give 2.52 against 1.15-1.4, which is 1.80x to 2.19x."""
        r = ISA_VARIANTS['arm_v1'].core_area_mm2 / ISA_VARIANTS['arm_n1'].core_area_mm2
        assert 1.80 <= r <= 2.20
        assert abs(r - 1.70) > 0.05
        assert RETIRED_VARIANTS['arm_v1_press']['core_area_scale'] == pytest.approx(0.71)

    def test_the_baseline_core_is_smaller_than_a_real_isonode_x86_core(self):
        """Zen 2: same node class, same 512 KB L2, and 1.67x the modelled area."""
        assert (3.54 / BASELINE_CORE_MM2_7NM) == pytest.approx(1.67, abs=0.03)

    def test_a_wide_vector_core_can_now_be_LARGER_than_the_baseline(self):
        """Which the first cut could not express -- every variant there was a fraction of 1.0."""
        assert ISA_VARIANTS['arm_v1'].core_area_scale > 1.0
        assert ISA_VARIANTS['arm_n1'].core_area_scale < 1.0


@needs_pack
class TestTheMixComesFromThePublishedDecomposition:
    def test_the_published_mix_is_the_six_blocks_plus_a_1_35_percent_residual(self):
        m = published_mix()
        assert set(m) == {'frontend', 'ooo', 'lsu', 'fpu', 'int', 'l2', 'residual'}
        assert m['residual'] == pytest.approx(0.0135, abs=0.001)
        assert sum(m.values()) == pytest.approx(1.0)

    @needs_examples
    def test_the_shipped_baseline_carries_a_twenty_percent_featureless_residual(self):
        """The single largest difference between the model and the one published measurement."""
        model = baseline_group_fractions(_BASE_JSON)
        assert model['residual'] > 0.20
        assert model['residual'] / published_mix()['residual'] > 10

    @needs_examples
    def test_the_reweighting_lands_the_mix_it_targets(self):
        """The inversion is closed-form but it inverts somebody else's function, so it is
        checked by running that function."""
        base = _base()
        for k, v in ISA_VARIANTS.items():
            if not v.published_mix:
                continue
            stats, meta = reweight_area_stats(base, v)
            got = realised_group_fractions(stats, avx=v.vector_multiple)
            tgt = meta['target_group_fractions']
            for g in tgt:
                assert got[g] == pytest.approx(tgt[g], rel=1e-4), (k, g)

    @needs_examples
    def test_and_lands_the_absolute_core_area_it_targets(self):
        base = _base()
        for k, v in ISA_VARIANTS.items():
            if not v.published_mix:
                continue
            stats, _ = reweight_area_stats(base, v)
            got = realised_group_fractions(stats, avx=v.vector_multiple)
            want = BASELINE_CORE_MM2_7NM * v.core_area_scale
            assert got['_core_mm2_at_7nm'] == pytest.approx(want, rel=1e-6), k

    @needs_examples
    def test_the_written_down_baseline_core_area_is_what_the_tiler_actually_produces(self):
        """BASELINE_CORE_MM2_7NM is a constant so the module imports without examples/ on the
        path. That makes it a number that can silently go stale, so it is checked here against
        the shipped forward model rather than trusted."""
        m = baseline_group_fractions(_BASE_JSON)
        assert m['_core_mm2_at_7nm'] == pytest.approx(BASELINE_CORE_MM2_7NM, rel=1e-5)

    @needs_examples
    @needs_pack
    def test_the_module_docstrings_mix_table_is_what_the_code_computes(self):
        """The table in the module docstring is the single most quotable thing here. It is
        generated numbers written into prose, which is exactly how prose goes stale."""
        m = baseline_group_fractions(_BASE_JSON)
        gc = published_mix()
        for group, model_pct, gc_pct in (('frontend', 10.40, 23.02), ('ooo', 5.13, 18.56),
                                         ('lsu', 12.64, 14.47), ('fpu', 22.23, 13.84),
                                         ('int', 2.31, 5.64), ('l2', 25.21, 23.11),
                                         ('residual', 22.08, 1.35)):
            assert 100 * m[group] == pytest.approx(model_pct, abs=0.01), group
            assert 100 * gc[group] == pytest.approx(gc_pct, abs=0.01), group

    @needs_examples
    def test_the_baseline_variant_changes_nothing_at_all(self):
        """The back catalogue rests on it; it must come out untouched."""
        base = _base()
        out, meta = reweight_area_stats(base, 'x86_skylake')
        assert out == base
        assert meta['vector_multiple'] == pytest.approx(X86_VECTOR_MULTIPLE)
        assert meta['published_mix'] is False

    @needs_examples
    def test_it_does_not_mutate_the_input(self):
        base = _base()
        before = json.dumps(base, sort_keys=True)
        reweight_area_stats(base, 'arm_n1')
        assert json.dumps(base, sort_keys=True) == before

    @needs_examples
    def test_the_L1_is_pinned_by_capacity_rather_than_by_the_models_group_share(self):
        """McPAT puts the instruction cache at 60% of its own fetch unit; carried onto Golden
        Cove's published 1.64 mm^2 frontend that prices a 32 KB L1I at about 1 mm^2."""
        _, meta = reweight_area_stats(_base(), 'arm_n1')
        pin = meta['l1_pin']['frontend']
        assert pin['share_of_group'] < 0.35
        assert pin['mcpat_share_would_have_been'] > 0.55
        assert pin['area_mm2_at_7nm'] < 0.15

    @needs_examples
    def test_an_L1_that_cannot_fit_its_group_is_refused_not_squeezed(self):
        from HotGauge.thermal import isa_floorplans as I
        v = I.ISAVariant('tiny', 'absurd', vector_isa='x', vector_bits=256,
                         cache_key='riscv_xiangshan', core_area_mm2=0.20, node='7nm',
                         provenance='synthetic', assumptions='synthetic')
        with pytest.raises(ValueError) as e:
            reweight_area_stats(_base(), v)
        assert 'describing different machines' in str(e.value)
        assert str(int(MAX_L1_SHARE_OF_GROUP * 100)) in str(e.value)

    def test_the_L1_density_assumption_is_second_order(self):
        s = l1_sensitivity('arm_n1')
        assert s['frontend_spread'] < 0.05


@needs_pack
class TestThePowerPriorsAreWiredThrough:
    def test_the_arm_rows_carry_their_published_density(self):
        assert density_for('arm_v1') == pytest.approx(0.476, abs=0.002)
        assert density_for('arm_n1') == pytest.approx(0.870, abs=0.002)
        assert density_for('arm_n1', 'max') == pytest.approx(1.286, abs=0.002)

    def test_the_wide_vector_core_runs_at_half_the_density_of_the_compact_one(self):
        """The shape of the pack's answer, and the axis the thermal work turns on."""
        assert density_for('arm_v1') < 0.6 * density_for('arm_n1')

    def test_the_variants_with_no_published_density_return_None_rather_than_a_guess(self):
        assert density_for('arm_a64fx') is None
        assert density_for('riscv_xiangshan') is None


class TestProvenanceIsAttachedAndHonest:
    def test_nothing_claims_to_have_been_measured_off_silicon_by_us(self):
        """`calibrated` keeps its original meaning. What the area IS lives in area_provenance,
        because "published vendor number" and "chained press ratio" are not the same claim."""
        for k, v in ISA_VARIANTS.items():
            assert v.calibrated is False, k

    def test_every_variant_states_its_provenance_and_its_assumptions(self):
        for k, v in ISA_VARIANTS.items():
            assert v.provenance and len(v.provenance) > 60, k
            assert v.assumptions and len(v.assumptions) > 60, k

    def test_the_retired_press_ratio_variants_are_recorded_not_deleted(self):
        """Results built on them are on disk and have to stay interpretable."""
        assert set(RETIRED_VARIANTS) == {'arm_n2', 'arm_v1_press', 'riscv_p670'}
        for k, d in RETIRED_VARIANTS.items():
            assert 'why' in d and len(d['why']) > 20

    def test_the_summary_reports_the_published_area_where_there_is_one(self):
        for r in variant_summary():
            if r['area_provenance'] == 'published':
                assert r['core_area_mm2'] is not None
            else:
                assert r['core_area_mm2'] is None

    def test_the_groups_partition_the_mcpat_unit_tree_without_overlap(self):
        roots = [r for rs in GOLDEN_COVE_GROUPS.values() for r in rs]
        assert len(roots) == len(set(roots))
        for a in roots:
            for b in roots:
                if a is not b:
                    assert not b.startswith(a + '/'), (a, b)

    def test_the_legacy_sram_unit_list_is_still_exported(self):
        assert len(SRAM_UNITS) == 3
