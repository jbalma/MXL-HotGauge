"""Bookkeeping temperature keys must never reach a cooling plan (§P0.17).

`bridge_aggregates=True` injects `__agg__L3` so the L3's leakage can feed back against the mean of
the real `L3_*` blocks. It is a temperature with **no floorplan block behind it**. The MR planner
treated every above-target key as placeable, so a low-enough MR target produced

    KeyError: "plan names block '__agg__L3', which is not in the floorplan"

at placement time, killing ~10 points per arm of the §P0.16 catalogue re-run.

`[!]` The trigger is arm-dependent, which is why the filter is on the KEY and not on the target:
the bug fires when the synthetic key's *temperature* exceeds the target, and that temperature moves
with the leakage curve and the core_other policy. The same point raised in arm B and completed in
arm D. An earlier fixed `--mr-target-C <= 45` rule was tried and withdrawn.
"""
import numpy as np
import pytest

from HotGauge.thermal.microrefrigeration import (clipping_plan, is_synthetic_temp_key,
                                                 SYNTHETIC_TEMP_PREFIX, MRParams)
from HotGauge.thermal.leakage_feedback import AGG_L3_TEMP_KEY, BRIDGEABLE_AGGREGATES


def test_every_bridged_aggregate_is_recognised_as_synthetic():
    """Matched on prefix, so a future bridged aggregate is excluded automatically."""
    assert is_synthetic_temp_key(AGG_L3_TEMP_KEY)
    assert all(is_synthetic_temp_key(v) for v in BRIDGEABLE_AGGREGATES.values())
    assert AGG_L3_TEMP_KEY.startswith(SYNTHETIC_TEMP_PREFIX)


def test_real_floorplan_blocks_are_not_filtered():
    for blk in ('L3_0', 'L2_7', 'core_other_0', 'RBB_16', 'FPUs_3', 'iCache_2'):
        assert not is_synthetic_temp_key(blk), '%s is a real block' % blk


def _geom(names):
    return {n: {'area_mm2': 1.0, 'min_dim_um': 500.0} for n in names}


def test_the_synthetic_key_never_enters_a_plan():
    """The regression itself: hot enough to be planned, and it must still be skipped."""
    temps = {'L3_0': 360.0, 'L3_1': 358.0, AGG_L3_TEMP_KEY: 359.0}
    sens = {n: 1.0 for n in temps}
    plan, detail = clipping_plan(temps, _geom(temps), MRParams(313.15), sens)
    assert AGG_L3_TEMP_KEY not in plan
    assert AGG_L3_TEMP_KEY not in detail
    assert 'L3_0' in plan, 'the real blocks beside it must still be planned'


def test_it_is_skipped_even_at_a_target_low_enough_to_catch_everything():
    """The failing catalogue points used MR targets of 30-50 C, where every key is above target."""
    temps = {'L3_0': 340.0, AGG_L3_TEMP_KEY: 340.0}
    sens = {n: 1.0 for n in temps}
    plan, _ = clipping_plan(temps, _geom(temps), MRParams(303.15), sens)   # 30 C target
    assert AGG_L3_TEMP_KEY not in plan
    assert plan.get('L3_0', 0.0) > 0.0


def test_an_array_valued_temperature_is_still_filtered():
    """Tflp temperatures arrive as per-timestep arrays; the filter runs before the array is read."""
    temps = {'L3_0': np.array([350.0, 361.0]), AGG_L3_TEMP_KEY: np.array([350.0, 361.0])}
    sens = {n: 1.0 for n in temps}
    plan, _ = clipping_plan(temps, _geom(temps), MRParams(313.15), sens)
    assert AGG_L3_TEMP_KEY not in plan and 'L3_0' in plan


def test_the_sensitivity_probe_also_excludes_the_synthetic_key():
    """`[!]` The regression that a one-site fix missed.

    `run_mr_clipping`'s sensitivity-calibration probe builds its own plan from `base_hot` and hands
    it to `apply_plan` -> `project_plan_to_tiles` **without going through `clipping_plan`**. Filtering
    only the planner left the probe raising the identical KeyError from a different stack, and a
    "fixed" re-run failed 10 of 11 points. Both sites are filtered; this pins the second.
    """
    import inspect
    from HotGauge.thermal import microrefrigeration as mr
    src = inspect.getsource(mr)
    # every construction that turns block temperatures into plannable candidates must filter
    sites = [l for l in src.splitlines() if 'base_hot = {' in l or 'for blk, T in block_temps_K' in l]
    assert len(sites) == 2, 'expected exactly two temp->candidate sites, found %d' % len(sites)
    probe_src = src[src.index('base_hot = {'):src.index('base_hot = {') + 400]
    assert 'is_synthetic_temp_key' in probe_src, 'the probe path must filter synthetic keys'


def test_no_plan_built_from_block_temps_can_name_a_synthetic_key():
    """Belt and braces on the planner: whatever the temperatures, the key never appears."""
    for target in (303.15, 313.15, 323.15, 363.15):
        temps = {'L3_0': 370.0, 'core_other_0': 372.0, AGG_L3_TEMP_KEY: 371.0}
        sens = {n: 1.0 for n in temps}
        plan, detail = clipping_plan(temps, _geom(temps), MRParams(target), sens)
        assert AGG_L3_TEMP_KEY not in plan and AGG_L3_TEMP_KEY not in detail, \
            'leaked at target %.2f K' % target
