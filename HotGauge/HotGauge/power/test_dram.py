"""Tests for the DRAM refresh model (HotGauge.power.dram).

These pin the SHAPE of the model -- the feedback, the step at the breakpoint, the separation of
"expensive" from "out of spec". The absolute numbers are conventions, not measurements, and the
tests deliberately do not assert any of them as if they were.
"""
import numpy as np
import pytest

from HotGauge.power.dram import (DRAMPowerModel, stacked_dram_model, dram_block_powers,
                                 dram_limit_report, DEFAULT_REFRESH_BREAK_K,
                                 DEFAULT_DRAM_LIMIT_K)


def test_refresh_is_flat_below_the_breakpoint():
    m = DRAMPowerModel(1.0, 1.0, 1.0)
    assert m.refresh_multiplier(300.0) == pytest.approx(1.0)
    assert m.refresh_multiplier(DEFAULT_REFRESH_BREAK_K) == pytest.approx(1.0)
    assert m.power(300.0) == pytest.approx(3.0)


def test_crossing_the_breakpoint_is_a_step_not_a_slope():
    """JEDEC's extended range doubles the refresh rate AT the breakpoint, so the part sees a
    cliff. That step is why the memory limit behaves like a wall rather than a gentle cost."""
    m = DRAMPowerModel(1.0, 1.0, 1.0)
    just_under = m.power(DEFAULT_REFRESH_BREAK_K - 0.01)
    just_over = m.power(DEFAULT_REFRESH_BREAK_K + 0.01)
    assert just_over > just_under * 1.2


def test_refresh_doubles_per_halving_interval():
    m = DRAMPowerModel(0.0, 0.0, 1.0, halving_K=10.0, extended_range_step=1.0)
    hot = m.refresh_multiplier(DEFAULT_REFRESH_BREAK_K + 10.0)
    assert hot == pytest.approx(2.0)
    assert m.refresh_multiplier(DEFAULT_REFRESH_BREAK_K + 20.0) == pytest.approx(4.0)


def test_power_is_monotone_in_temperature():
    m = stacked_dram_model(100.0)
    T = np.linspace(300.0, 380.0, 40)
    p = [m.power(t) for t in T]
    assert all(b >= a for a, b in zip(p, p[1:]))


def test_model_is_uncalibrated_until_told_otherwise():
    """Nothing here is pinned to a datasheet, and the object must say so."""
    assert stacked_dram_model(100.0).calibrated is False
    assert 'UNCALIBRATED' in repr(stacked_dram_model(100.0))


def test_stacked_model_splits_the_density_as_asked():
    m = stacked_dram_model(100.0, density_W_per_mm2=0.15, refresh_fraction=0.35,
                           activity_fraction=0.30)
    total_at_break = m.background_W + m.activity_W + m.refresh_W
    assert total_at_break == pytest.approx(15.0)
    assert m.refresh_W == pytest.approx(15.0 * 0.35)


def test_block_powers_split_evenly_and_track_temperature():
    m = stacked_dram_model(100.0)
    names = ['MEM_r0c0', 'MEM_r0c1']
    cool = dram_block_powers(names, m, {'MEM_r0c0': 300.0, 'MEM_r0c1': 300.0})
    hot = dram_block_powers(names, m, {'MEM_r0c0': 380.0, 'MEM_r0c1': 300.0})
    assert sum(cool.values()) == pytest.approx(m.power(300.0))
    assert hot['MEM_r0c0'] > cool['MEM_r0c0']      # the hot bank costs more
    assert hot['MEM_r0c1'] == pytest.approx(cool['MEM_r0c1'])


def test_limit_report_separates_expensive_from_out_of_spec():
    """A part at 90 C is expensive; a part at 100 C is broken. Conflating them hides the one
    that matters."""
    temps = {'MEM_r0c0': np.array([DEFAULT_REFRESH_BREAK_K + 5.0]),   # over break, in spec
             'MEM_r0c1': np.array([DEFAULT_DRAM_LIMIT_K + 5.0]),      # out of spec
             'MEM_r1c0': np.array([320.0])}                           # fine
    r = dram_limit_report(temps)
    assert r['n_over_break'] == 2
    assert r['n_over_limit'] == 1
    assert r['over_limit'] == ['MEM_r0c1']
    assert r['peak_block'] == 'MEM_r0c1'


def test_rejects_impossible_fractions_and_negative_power():
    with pytest.raises(ValueError):
        stacked_dram_model(100.0, refresh_fraction=0.8, activity_fraction=0.5)
    with pytest.raises(ValueError):
        DRAMPowerModel(-1.0, 0.0, 0.0)
