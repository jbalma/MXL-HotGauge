"""Tests for the four-arm catalogue comparison (§P0.16).

What is guarded is the *reading discipline*, not the arithmetic:

  * an ``unconverged`` row is **neither** holding nor failing and must never be counted as a flip
    (the density ladder's rule -- letting one become a ceiling or a rescue is how §P0.11's arms
    would have been misread);
  * the arms form a chain where each pair differs by **one** flag, so a difference has one cause;
  * a **partial** campaign must announce itself. §P0.15 lost six solves to a refinement sited off
    a 16-of-20 ladder.
"""
import os
import sys

import pytest

from HotGauge.power.device_leakage import repo_root_for_evidence

_REPO = repo_root_for_evidence()
sys.path.insert(0, os.path.join(_REPO, 'examples'))

try:
    from catalogue_arm_compare import verdict, compare, ARM_FLAGS, ARMS, STEPS
except Exception:                                              # pragma: no cover
    verdict = None

_needs = pytest.mark.skipif(verdict is None, reason='comparison driver not importable')


@_needs
def test_unconverged_is_its_own_verdict():
    assert verdict({'unconverged': True, 'diverged': True}) == 'unconverged'
    assert verdict({'unconverged': True, 'diverged': False}) == 'unconverged'
    assert verdict({'diverged': True}) == 'diverged'
    assert verdict({}) == 'holds'


@_needs
def test_an_unconverged_point_is_never_counted_as_a_flip():
    data = {'A': {'p1': {'control': {'diverged': True}},
                  'p2': {'control': {'unconverged': True}}},
            'B': {'p1': {'control': {'diverged': False, 'peak_C': 90.0}},
                  'p2': {'control': {'diverged': False, 'peak_C': 90.0}}}}
    c = compare('A', 'B', data)
    assert c['n_undecided'] == 1
    assert c['flips'] == {'diverged->holds': 1}, 'only the DECIDED pair may be counted'


@_needs
def test_each_adjacent_pair_differs_by_exactly_one_flag():
    """The whole point of four arms: a difference must have a single cause."""
    for lo, hi, _ in STEPS:
        diff = sum(1 for x, y in zip(ARM_FLAGS[lo], ARM_FLAGS[hi]) if x != y)
        assert diff == 1, '%s->%s differs by %d flags, not 1' % (lo, hi, diff)
    assert ARM_FLAGS['A'] == ('pipeline', 'stock', 'stock'), \
        'arm A must be the all-defaults control'


@_needs
def test_peak_delta_only_uses_points_holding_in_both():
    data = {'A': {'p1': {'control': {'diverged': False, 'peak_C': 80.0}},
                  'p2': {'control': {'diverged': True}}},
            'B': {'p1': {'control': {'diverged': False, 'peak_C': 75.0}},
                  'p2': {'control': {'diverged': False, 'peak_C': 60.0}}}}
    c = compare('A', 'B', data)
    assert c['n_peak_pairs'] == 1, 'a point that diverged in one arm has no comparable peak'
    assert c['mean_dpeak_K'] == pytest.approx(-5.0)


@_needs
def test_a_missing_arm_yields_no_shared_points_rather_than_a_crash():
    assert compare('A', 'B', {'A': {'p1': {'control': {}}}})['n_common'] == 0


@_needs
def test_broken_driver_exclusion_is_driver_level_only():
    """`stacked_memory_study.py` fails outright on this toolchain and accepts none of the re-run
    flags, so it is identical in every arm. That is a property of the DRIVER and is the only
    exclusion statable without looking at a log."""
    from catalogue_arm_compare import is_broken_driver
    assert is_broken_driver({'driver': 'examples/stacked_memory_study.py', 'argv': []})
    assert not is_broken_driver({'driver': 'examples/mr_comparison.py', 'argv': []})


@_needs
def test_failure_is_read_from_the_logs_not_from_a_target_threshold(tmp_path):
    """`[!]` A fixed `--mr-target-C <= 45` rule was tried and was WRONG.

    It came from bracketing the `__agg__L3` planner bug with two real points in arm D --
    `A_ceiling_T50` completing, `A_ceiling_T40` raising. The same point 16 then **raised in arm
    B**. The bug fires when the synthetic key's TEMPERATURE exceeds the target, which depends on
    the leakage curve and the core_other policy, so the trigger is arm-dependent and no target
    threshold can express it. A completeness guard needs the STATE (done / attempted-and-failed /
    not yet run), which the sweep logs record directly.
    """
    import json as _json
    import catalogue_arm_compare as m
    root = tmp_path / 'results' / 'rerun_arm_Z'
    (root / 'logs').mkdir(parents=True)
    (root / 'sf00_mr_comparison.json').write_text(_json.dumps(
        [['--out-dir', '/p0'], ['--out-dir', '/p1'], ['--out-dir', '/p2']]))
    (root / 'logs' / 'sf00_mr_comparison.log').write_text(
        '[sweep] point 0 ok in 10.0 s\n[sweep] point 1 raised in 11.0 s\n')
    old = m.arm_root
    m.arm_root = lambda a: str(root)
    try:
        assert m.raised_out_dirs('Z') == {'/p1'}, 'only the point the log says RAISED'
    finally:
        m.arm_root = old


@_needs
def test_an_out_of_range_point_index_is_ignored(tmp_path):
    """A log line naming a point index the stream does not have must not invent an out-dir."""
    import json as _json
    import catalogue_arm_compare as m
    root = tmp_path / 'rerun_arm_Z'
    (root / 'logs').mkdir(parents=True)
    (root / 'sf00_mr_comparison.json').write_text(_json.dumps([['--out-dir', '/p0']]))
    (root / 'logs' / 'sf00_mr_comparison.log').write_text('[sweep] point 7 raised in 1.0 s\n')
    old = m.arm_root
    m.arm_root = lambda a: str(root)
    try:
        assert m.raised_out_dirs('Z') == set()
    finally:
        m.arm_root = old
