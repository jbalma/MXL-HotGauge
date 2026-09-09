"""Tests for the MR catalogue's leakage-curve comparison (§P0.16).

What is guarded here is not arithmetic. It is three things a later reader must not lose:

  * **the 22 rescues survive the curve swap** -- 6/6 airflows on all three curves. A re-run that
    reports fewer must be a real change, not a silently loosened rescue definition;
  * **a rescue needs BOTH arms.** The claim is a difference ("control has no steady state, array
    holds target"), so a comparison that only reads the array arm cannot see a lost rescue;
  * **the prediction that failed, and why.** §P0.16 predicted 0/6 and got 6/6, because it treated
    the loop gain ``G`` at a runaway as an invariant of the configuration. It is not: it is set by
    the stopping rule, and a gentler curve moves the runaway further out in temperature at a
    similar gain. That correction is the transferable part.
"""
import os
import sys

import pytest

from HotGauge.power.device_leakage import repo_root_for_evidence

_REPO = repo_root_for_evidence()
sys.path.insert(0, os.path.join(_REPO, 'examples'))

try:
    from mr_curve_compare import loop_gain, is_rescue, CFMS, TREES
except Exception:                                              # pragma: no cover
    loop_gain = is_rescue = None

_EV = os.path.join(_REPO, 'docs', 'evidence', 'mr_catalogue_curve_compare.json')
_needs_driver = pytest.mark.skipif(loop_gain is None, reason='comparison driver not importable')
_needs_evidence = pytest.mark.skipif(not os.path.exists(_EV), reason='comparison not generated')


@_needs_driver
def test_loop_gain_inverts_the_damped_map():
    """``G = 1 + (ratio - 1)/r`` inverts ``residual multiplier = (1-r) + rG`` exactly."""
    import tempfile
    r, G = 0.025, 3.6
    r1 = 40.0
    r2 = r1 * ((1 - r) + r * G)
    with tempfile.NamedTemporaryFile('w', suffix='.log', delete=False) as f:
        f.write('leakage feedback iter 9: residual still growing (%.4f -> %.4f K) at the minimum '
                'damping %g for 3 iterations -> genuine runaway; stopping\n' % (r1, r2, r))
        path = f.name
    try:
        assert loop_gain(path)['loop_gain_G'] == pytest.approx(G, rel=1e-9)
    finally:
        os.unlink(path)


@_needs_driver
def test_unconverged_is_neither_a_rescue_nor_a_failure():
    """An ``unconverged`` arm must never become a rescue -- the density ladder's rule."""
    ok = {'control': {'diverged': True, 'unconverged': False},
          'array_on': {'diverged': False, 'unconverged': False}}
    assert is_rescue(ok) is True
    for arm in ('control', 'array_on'):
        bad = {k: dict(v) for k, v in ok.items()}
        bad[arm]['unconverged'] = True
        assert is_rescue(bad) is None, 'an unconverged %s must not resolve the rescue' % arm


@_needs_driver
def test_a_holding_control_is_not_a_rescue():
    """The failure mode §P0.16 was run to detect: if the CONTROL holds, the rescue is gone even
    though every MR number in it is unchanged."""
    assert is_rescue({'control': {'diverged': False, 'unconverged': False},
                      'array_on': {'diverged': False, 'unconverged': False}}) is False


@_needs_evidence
@_needs_driver
def test_all_airflow_rescues_survive_both_measured_curves():
    import json
    doc = json.load(open(_EV))
    for curve in ('pipeline', 'simulated', 'simulated-gidl-off'):
        pts = doc['points'][curve]
        assert len(pts) == len(CFMS), '%s is incomplete -- do not read a partial ladder' % curve
        assert doc['rescues_surviving'][curve] == 6, (
            '%s should show 6/6 rescues (§P0.16); got %s'
            % (curve, doc['rescues_surviving'][curve]))
        for cfm, pt in pts.items():
            assert pt['array_idle']['diverged'], (
                'the UNPOWERED array must not rescue at %s CFM -- that is the control that makes '
                'the claim about the laser rather than about the extra die' % cfm)


@_needs_evidence
def test_the_die_power_barely_moves_so_chip_W_is_not_the_story():
    """§P0.16 predicted `chip_W` would fall 5-12 %. It falls ~1 %: `--density` pins the die power
    and the curve only re-weights leakage inside it. Guards the withdrawn number."""
    import json
    doc = json.load(open(_EV))['points']
    for cfm in ('120', '88', '60', '45'):
        p = doc['pipeline'][cfm]['array_on']['p_chip_W']
        s = doc['simulated'][cfm]['array_on']['p_chip_W']
        assert abs(s / p - 1.0) < 0.02, 'chip_W moved more than 2 % at %s CFM' % cfm


@_needs_evidence
def test_the_budget_cliff_does_not_move_with_the_leakage_curve():
    """§P0.16 predicted the clipping study would move HARD (its MR arm sits at ~326 K, where the
    simulated curve carries ~5x the ``dP_leak/dT``). It moves **2-4 %**, and the budget cliff does
    not move at all. Guards both the negative result and the size of the effect, because the
    prediction failed by turning a curve ratio into a result ratio."""
    import json
    clip = json.load(open(_EV)).get('clipping') or {}
    if not clip.get('simulated'):
        pytest.skip('clipping comparison not generated')
    for w in ('0.5', '1', '2', '3', '5', '8', '12'):
        p, s = clip['pipeline'][w], clip['simulated'][w]
        kpw_p = p['dT_K'] / p['heat_removed_W']
        kpw_s = s['dT_K'] / s['heat_removed_W']
        assert 1.0 < kpw_s / kpw_p < 1.10, (
            'at %s W the simulated curve should buy 2-4 %% more K/W, got %.3fx'
            % (w, kpw_s / kpw_p))
        assert p['mr_wins_on_perf_per_W'] is False and s['mr_wins_on_perf_per_W'] is False, \
            'no perf/W verdict flips on the measured curve (§P0.16 predicted one would)'
    # the knee stays between 3 and 5 W on both curves: efficacy drops by a third across it
    for curve in ('pipeline', 'simulated'):
        d = clip[curve]
        kpw = {w: d[w]['dT_K'] / d[w]['heat_removed_W'] for w in ('3', '5')}
        assert kpw['5'] / kpw['3'] < 0.75, '%s: the budget knee should sit between 3 and 5 W' % curve
