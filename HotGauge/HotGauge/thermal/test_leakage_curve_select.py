"""Tests for selecting which leakage-vs-temperature curve a study solves on (§P0.13).

The point of these is not that the arithmetic works -- it is that the *swap* is controlled. A
leakage curve is the single most load-bearing input in this project, so the ways it could go
wrong quietly all get a test:

* the default must stay ``pipeline``, or every recorded result silently moves;
* both curves must be anchored at the same T_ref, or the swap smuggles in a level change and the
  comparison stops being about shape;
* the simulated curve must NOT clamp where the pipeline one does -- that clamp is the cold-zone
  result;
* and above its table it must still extrapolate, because a clamped hot tail suppresses runaway
  and turns a divergent configuration into an apparently convergent one.
"""
import os

import numpy as np
import pytest

from HotGauge.thermal.leakage_feedback import (LEAKAGE_CURVES, load_leakage_model,
                                               load_simulated_leakage_model)
from HotGauge.power.device_leakage import (SIMULATED_EVIDENCE, repo_root_for_evidence)

_REPO = repo_root_for_evidence()
_CAL = os.path.join(_REPO, 'leakage_calibration', 'leakage_calibration.json')
_EV = os.path.join(_REPO, SIMULATED_EVIDENCE)

_needs_evidence = pytest.mark.skipif(not os.path.exists(_EV),
                                     reason='simulated leakage evidence not generated')
_needs_cal = pytest.mark.skipif(not os.path.exists(_CAL), reason='leakage calibration absent')


def test_the_curve_names_are_the_documented_three():
    assert LEAKAGE_CURVES == ('pipeline', 'simulated', 'simulated-gidl-off')


def test_unknown_curve_is_an_error_not_a_fallback():
    with pytest.raises(ValueError, match='unknown leakage curve'):
        load_leakage_model('made-up')


def test_pipeline_requires_its_calibration_file():
    with pytest.raises(ValueError, match='calibration'):
        load_leakage_model('pipeline')


@_needs_evidence
def test_simulated_and_gidl_off_share_the_pipeline_anchor():
    """Both must normalise at 330 K, or the swap changes the level and not just the shape."""
    _, t_full = load_simulated_leakage_model(mechanism='full')
    _, t_off = load_simulated_leakage_model(mechanism='gidl_off')
    assert t_full == t_off == 330.0


@_needs_evidence
@_needs_cal
def test_every_curve_is_unity_at_its_own_anchor():
    for which in LEAKAGE_CURVES:
        m, t_ref = load_leakage_model(which, calibration=_CAL)
        assert float(m.scale(t_ref, t_ref)) == pytest.approx(1.0, rel=1e-9), which


@_needs_evidence
@_needs_cal
def test_the_pipeline_clamps_below_300K_and_the_simulated_one_does_not():
    """This IS the cold-zone result, expressed as a test.

    The pipeline's table starts at 300 K, so it reports identical leakage at 300 K and 200 K --
    a clamp that was read as physics for the whole cold-zone argument. The simulated table
    reaches 200 K, so it keeps falling.
    """
    pipe, t_p = load_leakage_model('pipeline', calibration=_CAL)
    sim, t_s = load_leakage_model('simulated', calibration=_CAL)
    assert float(pipe.scale(200.0, t_p)) == pytest.approx(float(pipe.scale(300.0, t_p)))
    assert float(sim.scale(200.0, t_s)) < 0.5 * float(sim.scale(300.0, t_s))


@_needs_evidence
@_needs_cal
def test_the_simulated_hot_tail_is_gentler_than_the_pipelines():
    """§P0.13's second finding, and the direction matters for P0.11's ceiling."""
    pipe, t_p = load_leakage_model('pipeline', calibration=_CAL)
    sim, t_s = load_leakage_model('simulated', calibration=_CAL)
    assert float(sim.scale(500.0, t_s)) < float(pipe.scale(500.0, t_p))
    # ...and gentler by a lot, not by rounding.
    assert float(pipe.scale(500.0, t_p)) / float(sim.scale(500.0, t_s)) > 10.0


@_needs_evidence
def test_the_simulated_curve_still_extrapolates_above_its_table():
    """A clamped hot tail freezes the feedback and makes a divergent config look convergent."""
    m, t_ref = load_simulated_leakage_model()
    assert float(m.scale(600.0, t_ref)) > float(m.scale(500.0, t_ref)) * 1.5
    assert m.measured_max_K == 500.0
    assert 0.0 < m.activation_eV < 2.0


@_needs_evidence
def test_extrapolation_can_be_turned_off_and_then_it_clamps():
    m, t_ref = load_simulated_leakage_model(extrapolate=False)
    assert float(m.scale(600.0, t_ref)) == pytest.approx(float(m.scale(500.0, t_ref)))


@_needs_evidence
def test_gidl_off_is_the_colder_bracket_and_they_converge_when_hot():
    full, t = load_simulated_leakage_model(mechanism='full')
    off, _ = load_simulated_leakage_model(mechanism='gidl_off')
    assert float(off.scale(200.0, t)) < float(full.scale(200.0, t)) / 10.0
    assert float(off.scale(400.0, t)) == pytest.approx(float(full.scale(400.0, t)), rel=0.25)


@_needs_evidence
def test_the_model_carries_its_provenance():
    """A study stamps ``leakage_model`` into its evidence file; it must say which curve it was."""
    m, _ = load_simulated_leakage_model()
    assert 'simulated' in m.description and 'BSIM-CMG' in m.description
    assert getattr(m, 'simulated', False) is True
    assert m.source_meta['sanity']['PASSES']


# ---------------------------------------------------------------------------
# The study driver's default
# ---------------------------------------------------------------------------
#: Every study driver that selects a leakage curve. §P0.15 added the last three; the flag is the
#: only way to re-run them on a non-pipeline curve, and the default is the only thing standing
#: between the recorded catalogue and a silent re-basing of all of it.
CURVE_SELECTING_DRIVERS = ('uniform_density_probe.py', 'clock_headroom.py',
                           'mr_comparison.py', 'mr_clipping_study.py')

#: The subset §P0.15 RETROFITTED. `uniform_density_probe.py` was written against
#: ``load_leakage_model`` from the start and never had a hard-wired pipeline call, so the
#: additivity check below has nothing to assert about it -- it is excluded rather than skipped,
#: because a test that always skips is noise against the suite's "N passed, 1 skipped" gate.
RETROFITTED_DRIVERS = tuple(d for d in CURVE_SELECTING_DRIVERS if d != 'uniform_density_probe.py')


@pytest.mark.parametrize('driver', CURVE_SELECTING_DRIVERS)
def test_every_driver_defaults_to_the_pipeline_curve(driver):
    """`[!]` If this fails, every recorded result from that driver has silently moved.

    Same guard as ``--rbb-policy`` has. The simulated curve is a deliberate flagged re-run, never
    a new default, until a catalogue re-run says otherwise.
    """
    import re
    path = os.path.join(_REPO, 'examples', driver)
    if not os.path.isfile(path):
        pytest.skip('{} not present'.format(driver))
    src = open(path).read()
    m = re.search(r"add_argument\('--leakage-curve',[^)]*?default='([\w-]+)'", src, re.S)
    assert m is not None, 'the --leakage-curve flag is gone from {}'.format(driver)
    assert m.group(1) == 'pipeline'


@pytest.mark.parametrize('driver', RETROFITTED_DRIVERS)
def test_the_pipeline_branch_is_untouched_by_the_flag(driver):
    """The flag must be additive: at the default, the driver takes the path it always took.

    Checked structurally rather than by running a solve -- every one of these drivers needs
    3D-ICE. The non-pipeline branch has to be a new ``if`` *ahead* of the existing
    ``load_calibrated_leakage_model`` call, leaving that call reachable and unmodified, which is
    the repo's rule for changes to a recorded code path.
    """
    path = os.path.join(_REPO, 'examples', driver)
    if not os.path.isfile(path):
        pytest.skip('{} not present'.format(driver))
    src = open(path).read()
    assert "load_calibrated_leakage_model(" in src, \
        'the pipeline path was replaced rather than branched around'
    assert "if args.leakage_curve != 'pipeline':" in src
    assert src.index("if args.leakage_curve != 'pipeline':") \
        < src.index("elif os.path.isfile(args.leakage_cal):") \
        < src.rindex("load_calibrated_leakage_model(")


def test_the_ladder_comparison_names_its_second_curve():
    """`[!]` Two ladders must not land under the same key in two evidence files.

    §P0.14 compared `pipeline` against `simulated`; §P0.15 compares it against
    `simulated-gidl-off`. Before `--curve` existed, the second ladder was hard-coded as
    ``'simulated'`` everywhere in the output *and* selected the leakage model the gain table is
    computed from -- so a gidl-off run would have written a file labelled `simulated`, containing
    gidl-off cliffs next to full-GIDL gains. The default must stay `simulated` so the recorded
    evidence file is unchanged.
    """
    import re
    path = os.path.join(_REPO, 'examples', 'density_ceiling_curve_compare.py')
    if not os.path.isfile(path):
        pytest.skip('comparison driver not present')
    src = open(path).read()
    m = re.search(r"add_argument\('--curve',\s*default='([\w-]+)'", src)
    assert m is not None, 'the --curve flag is gone'
    assert m.group(1) == 'simulated'
    # It must reach the leakage model too, not just the labels -- that was the real trap.
    assert 'load_leakage_model(CURVE)' in src
    assert "load_leakage_model('simulated')" not in src


# ---------------------------------------------------------------------------
# `[!]` §P0.15 -- why the GIDL bracket does NOT move the density ceiling
# ---------------------------------------------------------------------------
#: The band the surviving (holding) points of the uniform density arm actually occupy, from the
#: measured ladders: peaks of 42.9-54.7 C. Runaway is decided here and nowhere else.
OPERATING_BAND_K = (316.0, 328.0)


def _log_slope(model, T, t_ref, h=1.0):
    """d(ln P_leak)/dT -- the feedback gain, which is what sets local stability."""
    return (np.log(float(model.scale(T + h, t_ref)))
            - np.log(float(model.scale(T - h, t_ref)))) / (2.0 * h)


@_needs_evidence
@_needs_cal
def test_the_gidl_bracket_is_a_small_gain_difference_where_it_counts():
    """`[!]` The measurement that explains a failed prediction, kept as a test.

    §P0.14 predicted the GIDL bracket would move the flat-die ceiling, because the ceiling is
    decided at 310-330 K and the brackets differ most there. They differ most there **in leakage
    level**. Runaway is set by the **slope** -- §P0.14's own finding -- and the slopes differ by
    far less. Measured in the band the holding points occupy, swapping the curve changes the gain
    by roughly an order of magnitude and swapping the bracket changes it by about a fifth.

    The ladder then moved one rung for the first and none for the second. If this ratio ever
    stops holding, the conclusion "the bracket does not reach the density ceiling" has to be
    re-run, so it is asserted rather than remembered.
    """
    pipe, t_p = load_leakage_model('pipeline', calibration=_CAL)
    sim, t_s = load_leakage_model('simulated')
    off, t_o = load_leakage_model('simulated-gidl-off')
    for T in np.arange(OPERATING_BAND_K[0], OPERATING_BAND_K[1] + 1e-9, 6.0):
        g_pipe, g_sim, g_off = (_log_slope(pipe, T, t_p), _log_slope(sim, T, t_s),
                                _log_slope(off, T, t_o))
        curve_swap = g_sim / g_pipe          # pipeline -> simulated
        bracket = g_off / g_sim              # simulated -> GIDL-off
        assert curve_swap > 5.0, 'the curve swap should carry ~6-14x the gain at %.0f K' % T
        assert bracket < 1.4, 'the bracket should carry ~1.2x the gain at %.0f K' % T
        # The point of the whole thing: one of these is an order of magnitude bigger.
        assert curve_swap > 4.0 * bracket


@_needs_evidence
def test_the_two_brackets_converge_in_gain_as_they_get_hot():
    """They are indistinguishable in the hot tail, which is why §P0.14 read the level instead.

    At 450-500 K the brackets differ ~14-15 % in LEVEL and essentially 0 % in gain. Looking at
    the level at 450-500 K, seeing a small number, and inferring the difference must be large at
    310-330 K is the exact step that failed -- the level does diverge cold, the gain does not.
    """
    sim, t_s = load_leakage_model('simulated')
    off, t_o = load_leakage_model('simulated-gidl-off')
    hot = _log_slope(off, 500.0, t_o) / _log_slope(sim, 500.0, t_s)
    cold = _log_slope(off, 316.0, t_o) / _log_slope(sim, 316.0, t_s)
    assert hot == pytest.approx(1.0, abs=0.02)
    assert cold > hot, 'the bracket must still matter more cold than hot, just not by much'
    assert cold < 1.4
