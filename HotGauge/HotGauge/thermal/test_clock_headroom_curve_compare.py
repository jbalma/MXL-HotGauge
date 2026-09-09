"""Tests for the clock-headroom leakage-curve comparison (§P0.15).

The thing worth guarding here is not arithmetic -- it is that a **withdrawn prediction stays
withdrawn**. §P0.14 predicted the temperature-limited clock search would move MORE than the
density ladder did when the leakage curve was swapped. It moved less. A later reader who re-runs
this and sees "nothing moved" should find the prediction and its refutation together, not an
absence.

The second guard is the one that actually cost something to find: the sustainable clock is
identical across curves at almost every cooling point while the **limiter** changes underneath it.
A comparison that only looked at ``f_sustainable_GHz`` would have reported "no effect" and missed
that a headline claim in ``docs/CLOCK_HEADROOM.md`` was an artefact.
"""
import os
import sys
import json

import pytest

from HotGauge.power.device_leakage import repo_root_for_evidence

_REPO = repo_root_for_evidence()
sys.path.insert(0, os.path.join(_REPO, 'examples'))

_EV = os.path.join(_REPO, 'docs', 'evidence', 'clock_headroom_curve_compare.json')
_needs_evidence = pytest.mark.skipif(not os.path.exists(_EV),
                                     reason='clock-headroom curve comparison not generated')

try:
    from clock_headroom_curve_compare import load_runs, RECORDED_2026_08_14
except ImportError:                                            # pragma: no cover
    load_runs = RECORDED_2026_08_14 = None

_needs_driver = pytest.mark.skipif(load_runs is None, reason='comparison driver not importable')


@_needs_evidence
def test_the_prediction_is_recorded_as_withdrawn():
    """`[!]` If this fails, a wrong prediction has been quietly reworded instead of retracted."""
    ev = json.load(open(_EV))
    key = 'FINDING_1_THE_PREDICTION_IS_WITHDRAWN'
    assert key in ev
    assert 'withdrawn' in ev[key].lower()
    # It must say which way it was wrong, not merely that it was.
    assert 'moved LESS' in ev[key]


@_needs_evidence
def test_the_clock_barely_moves_but_the_limiter_does():
    """The finding in one assertion: same answer, different reason.

    A comparison that reported only the clock would have concluded "the leakage curve does not
    matter to this study", which is false in the way that matters.
    """
    ev = json.load(open(_EV))
    assert ev['n_where_clock_moved'] < ev['n_where_limiter_changed']
    assert ev['n_where_limiter_changed'] > 0


@_needs_evidence
def test_every_limiter_change_is_pipeline_runaway_becoming_a_spec_limit():
    """The direction matters: the pipeline curve invents a runaway, it does not hide one."""
    ev = json.load(open(_EV))
    changed = [r for r in ev['rows'] if r.get('limiter_changed')]
    assert changed, 'no limiter changed -- the finding is gone'
    for r in changed:
        assert r['pipeline']['limited_by'] == 'thermal_runaway'
        assert r['simulated']['limited_by'] == 'over_thermal_limit'


@_needs_evidence
def test_the_gidl_brackets_agree_and_the_file_says_so():
    """Unlike the density ceiling, this study does not wait on settling GIDL."""
    ev = json.load(open(_EV))
    assert ev['gidl_brackets_agree_on_clock'] in (True, None)
    assert ev['gidl_brackets_agree_on_limiter_where_judgeable'] in (True, None)


@_needs_evidence
def test_an_unverified_limiter_is_counted_as_neither_agreement_nor_disagreement():
    """`[!]` The standing rule: an unverified point is not a hold and not a failure.

    One GIDL-off point stops on a step the damping check rejected, so its *clock* is a
    demonstrated hold while the *reason* it stopped is unknown. Counting it as a limiter
    disagreement would manufacture one; counting it as agreement would launder it. It is listed
    and excluded, and the two questions -- did the clock agree, did the limiter agree -- are
    answered separately so neither can absorb the other.
    """
    ev = json.load(open(_EV))
    assert 'points_with_an_unverified_limiter' in ev
    for u in ev['points_with_an_unverified_limiter']:
        row = next(r for r in ev['rows'] if r['r_th_K_per_W'] == u['r_th_K_per_W'])
        for c in u['curves']:
            assert row[c]['limited_by'] == 'unverified'
            # The clock itself is still a real measurement -- that is the whole distinction.
            assert row[c]['f_sustainable_GHz'] > 0


@_needs_evidence
def test_the_bracket_clock_comparison_uses_the_search_resolution():
    """Two bisections stopping one step apart have not disagreed about anything measurable."""
    ev = json.load(open(_EV))
    if 'simulated-gidl-off' not in ev['curves']:
        pytest.skip('only one simulated curve present')
    tol = ev['f_tol_GHz']
    both = [r for r in ev['rows'] if r.get('simulated') and r.get('simulated-gidl-off')]
    worst = max(abs(r['simulated']['f_sustainable_GHz']
                    - r['simulated-gidl-off']['f_sustainable_GHz']) for r in both)
    assert ev['gidl_brackets_agree_on_clock'] == (worst <= tol)


@_needs_evidence
def test_a_move_smaller_than_the_search_resolution_is_not_counted_as_a_move():
    """`[!]` The bisection's own tolerance is the noise floor of this measurement."""
    ev = json.load(open(_EV))
    tol = ev['f_tol_GHz']
    for r in ev['rows']:
        if 'clock_moved' in r:
            assert r['clock_moved'] == (abs(r['delta_GHz_simulated_minus_pipeline']) > tol)


@_needs_driver
def test_the_recorded_august_table_is_labelled_reference_only():
    """It predates three fixes that raise the clock; treating it as a target inverts their sign."""
    import clock_headroom_curve_compare as m
    assert 'NOT a reproduction target' in m.__file__ or True   # the note lives in the source
    src = open(os.path.join(_REPO, 'examples', 'clock_headroom_curve_compare.py')).read()
    assert 'NOT a reproduction target' in src
    assert set(RECORDED_2026_08_14) == {1.0, 0.5, 0.3, 0.1, 0.05, 0.02}
