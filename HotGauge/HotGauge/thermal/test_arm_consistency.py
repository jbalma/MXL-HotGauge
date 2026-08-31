"""Tests for the arm-consistency check. Pure Python."""
import pytest

from HotGauge.thermal.arm_consistency import (check_arm_consistency, ArmConsistencyError,
                                              BEST_MEASURED_K_PER_W)


def test_zero_removal_and_zero_cooling_is_fine():
    r = check_arm_consistency(85.0, 85.0, 0.0)
    assert r['checked'] and r['verdict'].startswith('ok')


def test_the_observed_defect_is_caught():
    """The real numbers: array_idle 85.0 C, array_on 62.6 C, 0.000 W removed."""
    with pytest.raises(ArmConsistencyError) as e:
        check_arm_consistency(85.0, 62.6, 0.0, label='r_th 0.3 array_on')
    msg = str(e.value)
    assert 'ZERO heat removed' in msg and 'must not be quoted' in msg
    assert 'r_th 0.3 array_on' in msg


def test_a_powered_arm_that_is_WARMER_with_no_removal_is_not_an_error():
    """Only unexplained COOLING is the defect; noise in the other direction is not."""
    assert check_arm_consistency(85.0, 85.4, 0.0)['verdict'].startswith('ok')


def test_solver_noise_does_not_trip_it():
    assert check_arm_consistency(85.0, 84.99, 0.0)['verdict'].startswith('ok')


def test_a_realistic_gain_passes():
    """The measured 12 K margin point: 8.8 K for 3.771 W = 2.3 K/W."""
    r = check_arm_consistency(85.0, 76.2, 3.771)
    assert r['verdict'] == 'ok'
    assert r['K_per_W'] == pytest.approx(8.8 / 3.771, rel=1e-6)


def test_an_absurd_gain_per_watt_is_flagged_but_not_fatal(caplog):
    """A smoke alarm, not a physical law -- so it warns and says which it is."""
    r = check_arm_consistency(85.0, 25.0, 0.5)      # 120 K/W
    assert r['verdict'].startswith('suspicious')
    assert r['K_per_W'] > 100


def test_the_ceiling_has_real_headroom_over_anything_measured():
    """Guards against the threshold being tightened into false positives.

    The first version of this ceiling was 10 K/W, derived from uniform-workload data, and it
    fired on the very first concentrated shape measured (g4_turbo at 10.7 K/W) -- a real result.
    It is now derived from the widest measured basis available.
    """
    from HotGauge.thermal.arm_consistency import (DEFAULT_MAX_K_PER_W,
                                                  BEST_MEASURED_CONCENTRATED_K_PER_W)
    assert DEFAULT_MAX_K_PER_W > 2 * BEST_MEASURED_CONCENTRATED_K_PER_W


def test_a_real_concentrated_shape_does_not_trip_the_alarm():
    """g4_turbo at 3 K of margin: 3.00 K for 0.280 W = 10.7 K/W. Measured, and legitimate."""
    r = check_arm_consistency(85.0, 82.0, 0.280)
    assert r['verdict'] == 'ok', 'a measured concentrated-workload result must not be flagged'


def test_a_missing_arm_is_skipped_not_failed():
    assert check_arm_consistency(None, 60.0, 0.0)['checked'] is False
    assert check_arm_consistency(85.0, None, 0.0)['checked'] is False
