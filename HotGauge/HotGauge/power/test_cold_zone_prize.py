"""Tests for the cold-zone prize arithmetic (§P0.14).

The interesting property under test is **saturation**, and it is the reason the whole 2.3x
argument in `cold_zone_prize_bounds.json` was less decisive than it looked: the prize is bounded
by the cache's share of die power and approaches it as ``1 - 1/reduction``, so three orders of
magnitude of disagreement about the *reduction factor* can be worth ~1 % of die power. Anything
that quotes a reduction factor as if it were the answer is making that mistake.

The driver lives in ``examples/``, so it is imported by path rather than as a package -- the same
thing ``test_device_leakage`` does for its driver.
"""
import os
import sys
import json

import pytest

from HotGauge.power.device_leakage import repo_root_for_evidence

_REPO = repo_root_for_evidence()
sys.path.insert(0, os.path.join(_REPO, 'examples'))

_EV = os.path.join(_REPO, 'docs', 'evidence', 'cold_zone_prize_simulated.json')
_needs_evidence = pytest.mark.skipif(not os.path.exists(_EV),
                                     reason='cold-zone prize evidence not generated')

try:
    from cold_zone_prize import (prize_pct, trace_ratios, die_ratios,
                                 recorded_pair_provenance, RECORDED_SLICE, STEADY_FROM_TICK)
except ImportError:                                            # pragma: no cover
    prize_pct = trace_ratios = die_ratios = recorded_pair_provenance = None
    RECORDED_SLICE = STEADY_FROM_TICK = None

#: The re-derived conversion pair (§P0.15). Used in the arithmetic tests in place of the recorded
#: 34.64 %/92.6 %, which is reproduced below only to show it is a scope error.
SF, CS = 0.1598, 0.3824

_needs_driver = pytest.mark.skipif(prize_pct is None, reason='cold_zone_prize driver not importable')


@_needs_driver
def test_prize_is_bounded_by_the_cache_share_of_die_power():
    """Infinite reduction takes all of the cache's leakage and not one watt more."""
    ceiling = 100.0 * SF * CS
    assert prize_pct(1e12, SF, CS) == pytest.approx(ceiling, rel=1e-6)
    assert prize_pct(2.0, SF, CS) < ceiling


@_needs_driver
def test_no_reduction_is_no_prize():
    assert prize_pct(1.0, SF, CS) == pytest.approx(0.0)


@_needs_driver
def test_it_saturates_which_is_the_whole_point():
    """10x collects 90 % of the prize; 100x collects 99 %; 200x is indistinguishable from 100x."""
    ceiling = prize_pct(1e12, SF, CS)
    assert prize_pct(10.0, SF, CS) == pytest.approx(0.90 * ceiling, rel=1e-6)
    assert prize_pct(100.0, SF, CS) == pytest.approx(0.99 * ceiling, rel=1e-6)
    # The book's "realistic 100-200x" spans a factor of two and buys half a percent of die power.
    assert abs(prize_pct(200.0, SF, CS) - prize_pct(100.0, SF, CS)) < 0.2


@_needs_driver
def test_the_improvement_ratio_is_independent_of_the_conversion_ratios():
    """`[!]` This is why §P0.14 quotes 2.2x and not a percentage.

    Both conversions multiply the same ``1 - 1/reduction`` by a constant, so the ratio between two
    curves' prizes cancels the constant exactly. The absolute prize inherits two ratios that could
    not be reproduced from any trace in the repo; the improvement does not.
    """
    red_pipe, red_sim = 1.73, 16.58
    for sf, cs in ((0.3464, 0.926), (SF, CS), (0.1445, 0.6677), (0.5, 1.0)):
        assert (prize_pct(red_sim, sf, cs) / prize_pct(red_pipe, sf, cs)
                == pytest.approx(2.2278, rel=1e-3))


@_needs_driver
def test_trace_ratios_excludes_hierarchy_aggregates_but_bridges_L3():
    """Summing McPAT's dict double-counts; dropping L3 loses the block the prize lives in."""
    td = os.path.join(_REPO, 'mcpat_runs', '7nm', 'linpack_3.8GHz')
    if not os.path.isdir(td):
        pytest.skip('McPAT trace not present')
    r = trace_ratios(td)
    assert r is not None
    assert 0.0 < r['static_fraction'] < 1.0
    assert 0.0 < r['cache_share_of_leakage'] <= 1.0
    # L3 is bridged in, so it must be a real share of leakage rather than zero.
    assert r['l3_share_of_leakage'] > 0.1
    assert r['l3_share_of_leakage'] <= r['cache_share_of_leakage']


# ---------------------------------------------------------------------------
# `[!]` §P0.15 -- the recorded conversion pair, its provenance, and its withdrawal
# ---------------------------------------------------------------------------
@_needs_driver
def test_the_recorded_pair_is_reproduced_exactly_and_it_is_a_scope_error():
    """`[!]` Pins the provenance §P0.14 could not find, and pins it as a defect.

    `cold_zone_prize_bounds.json`'s measured baseline is not a mystery and was not measured
    post-feedback: it is the **first** slice of the 7nm linpack trace summed over the true leaves
    of **Core0 alone**, with the whole chip's L3 bridged in. All four recorded quantities come
    back to the last recorded digit, which is what makes this a provenance rather than a guess.

    Two defects, and the test names both so neither can be re-introduced:
      * scope -- one core's leaves against eight cores' worth of L3;
      * slice -- tick 4e11 is warm-up, where only Core0 has ramped.
    """
    td = os.path.join(_REPO, 'mcpat_runs', '7nm', 'linpack_3.8GHz')
    if not os.path.isfile(os.path.join(td, RECORDED_SLICE)):
        pytest.skip('McPAT trace not present')
    p = recorded_pair_provenance(td)
    assert p['dynamic_W'] == pytest.approx(2.6062, abs=5e-5)
    assert p['static_W'] == pytest.approx(1.3812, abs=5e-5)
    assert p['cache_leakage_W'] == pytest.approx(1.2784, abs=5e-5)
    assert 100 * p['static_fraction'] == pytest.approx(34.64, abs=0.005)
    assert 100 * p['cache_share_of_leakage'] == pytest.approx(92.6, abs=0.05)
    # 'L3 alone is 89% of it', per the recorded file's own comment.
    assert 100 * p['l3_share_of_leakage'] == pytest.approx(89.0, abs=0.5)


@_needs_driver
def test_the_intermediate_parents_are_what_make_it_reproduce():
    """Dropping `_AGGREGATES` is not enough -- McPAT's mid-level parents restate children too.

    ``Core0/Load Store Unit``, ``Core0/Renaming Unit`` and ``Core0/Instruction Fetch Unit`` carry
    0.8 mW of leakage each and are on no aggregate list. Including them gives 1.3837 W where the
    recorded value is 1.3812 W -- a near-miss that would have left the provenance unsettled. The
    leaf test has to be structural.
    """
    td = os.path.join(_REPO, 'mcpat_runs', '7nm', 'linpack_3.8GHz')
    path = os.path.join(td, RECORDED_SLICE)
    if not os.path.isfile(path):
        pytest.skip('McPAT trace not present')
    sp = json.load(open(path))
    naive = sum(float(v[1]) for k, v in sp.items() if k.startswith('Core0/'))
    naive += float(sp['Processor/Total L3s'][1])
    assert naive == pytest.approx(1.3837, abs=5e-4)
    assert abs(naive - 1.3812) > 1e-3, 'the parents must actually matter, or this test is vacuous'


@_needs_driver
def test_die_ratios_are_smaller_than_the_leaf_view_because_of_core_other():
    """The conversion to quote, and why it is not the McPAT-leaf one.

    ``core_other`` is McPAT's un-itemised per-core power on the tiler's slab. It is real die
    leakage -- about 42 % of what reaches the die -- and it is absent from any leaf sum, so the
    leaf view makes the cache look like two thirds of leakage instead of two fifths. The die
    view is therefore strictly the smaller prize, and it is the one whose denominator matches
    every other "% of die power" in the project.
    """
    td = os.path.join(_REPO, 'mcpat_runs', '7nm', 'linpack_3.8GHz')
    if not os.path.isdir(td):
        pytest.skip('McPAT trace not present')
    d = die_ratios(td)
    if d is None:
        pytest.skip('floorplan not present')
    leaf = trace_ratios(td)
    assert d['core_other_share_of_leakage'] > 0.3
    assert d['cache_share_of_leakage'] < leaf['cache_share_of_leakage']
    assert d['l3_share_of_leakage'] < d['cache_share_of_leakage']
    # The whole point: the re-derived ceiling is far below the recorded 32.1 %.
    ceiling = 100 * d['static_fraction'] * d['cache_share_of_leakage']
    assert 3.0 < ceiling < 12.0
    assert ceiling < 100 * 0.3464 * 0.926 / 2


@_needs_driver
def test_the_warm_up_slices_are_excluded():
    """The slice half of the defect. Tick 4e11 has only Core0 ramped and inflates static power."""
    td = os.path.join(_REPO, 'mcpat_runs', '7nm', 'linpack_3.8GHz')
    if not os.path.isdir(td):
        pytest.skip('McPAT trace not present')
    r = trace_ratios(td)
    assert 'steady' in r['source']
    # Steady-state static fraction is well under the 20.3 % the warm-up slices give at die scope.
    assert r['static_fraction'] < 0.16


@_needs_evidence
def test_evidence_records_both_conversions_and_the_same_improvement():
    ev = json.load(open(_EV))
    imp = ev['improvement_over_pipeline_x']
    assert imp['recorded_ratios'] == pytest.approx(imp['rederived'], rel=1e-6), \
        'the improvement must be conversion-independent or the headline claim is unsafe'
    assert imp['recorded_ratios'] > 2.0


@_needs_evidence
def test_evidence_carries_the_provenance_and_the_withdrawal():
    """The evidence file must say where the recorded pair came from and that it is withdrawn."""
    ev = json.load(open(_EV))
    p = ev.get('provenance_of_recorded_pair')
    assert p is not None and len(p['defects']) == 2
    assert 'withdrawn_hypothesis' in p
    d = ev['ratios']['rederived_pipeline_die']
    assert d['static_fraction'] * d['cache_share_of_leakage'] < 0.3464 * 0.926 / 2
    assert any('SCOPE_ERROR' in k for k in ev), 'the finding must be stated, not just the numbers'


@_needs_evidence
def test_evidence_reproduces_the_recorded_files_arithmetic():
    """Guards the comparison: if the formula drifted, the 13.5 % reference would move too."""
    ev = json.load(open(_EV))
    assert ev['ratios']['recorded_formula_reproduces'] is True


@_needs_evidence
def test_the_pipeline_curve_is_flat_across_the_whole_cold_sweep():
    """The clamp, stated as a test -- it is why the recorded prize was 13.5 %."""
    ev = json.load(open(_EV))
    red = {r['T_cold_K']: r['pipeline']['leakage_reduction_x'] for r in ev['rows']}
    assert red[300.0] == pytest.approx(red[200.0]), \
        'the pipeline curve reports the same leakage at 200 K as at 300 K'


@_needs_evidence
def test_the_knee_is_inside_the_sweep_and_barely_sub_ambient():
    ev = json.load(open(_EV))
    knee = ev['saturation_knee_K']
    assert knee is not None
    assert 250.0 <= knee <= 300.0, 'a knee at the sweep edge is the edge, not a knee'
    assert ev['saturation_knee_K_gidl_off'] is not None
