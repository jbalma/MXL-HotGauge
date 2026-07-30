"""Tests for temperature-dependent leakage feedback (HotGauge.power.leakage).

Runs on any platform (no Sniper/McPAT/3D-ICE needed): the thermal solve is mocked with a
deterministic lumped model. Run with `pytest`, or directly: `python -m HotGauge.power.test_leakage`.
"""
import os
import glob
import json

import numpy as np
import pytest

from HotGauge.power import (LeakageModel, rescale_total_power, rescale_trace,
                            converge_power_temperature, BasicPowerTrace)

TREF = 360.0


# ----------------------------------------------------------------------------
# LeakageModel physics
# ----------------------------------------------------------------------------
def test_scale_is_unity_at_reference():
    for model in (LeakageModel.exponential(10.0),
                  LeakageModel.subthreshold(0.9),
                  LeakageModel.from_table([300, 360, 400], [1.0, 4.0, 9.0])):
        assert model.scale(TREF, T_ref=TREF) == pytest.approx(1.0)


def test_exponential_doubles_every_delta():
    model = LeakageModel.exponential(doubling_delta_K=10.0)
    assert model.scale(TREF + 10, T_ref=TREF) == pytest.approx(2.0)
    assert model.scale(TREF + 20, T_ref=TREF) == pytest.approx(4.0)
    assert model.scale(TREF - 10, T_ref=TREF) == pytest.approx(0.5)


def test_scale_monotonic_increasing():
    for model in (LeakageModel.exponential(10.0), LeakageModel.subthreshold(0.9)):
        temps = np.linspace(300, 400, 50)
        factors = model.scale(temps, T_ref=TREF)
        assert np.all(np.diff(factors) > 0)


def test_celsius_units():
    model = LeakageModel.exponential(10.0)
    # 87 C == 360.15 K ~= TREF; scale ~ 1
    assert model.scale(86.85, T_ref=86.85, temp_units='C') == pytest.approx(1.0)
    assert model.scale(96.85, T_ref=86.85, temp_units='C') == pytest.approx(2.0, rel=1e-3)


def test_table_interpolation_and_clamp():
    model = LeakageModel.from_table([300, 350, 400], [1.0, 2.0, 4.0])
    assert model.scale(325, T_ref=300) == pytest.approx(1.5)   # linear midpoint
    # clamp beyond table (constant extension)
    assert model.scale(500, T_ref=300) == pytest.approx(4.0)


# ----------------------------------------------------------------------------
# rescale_total_power arithmetic
# ----------------------------------------------------------------------------
def test_rescale_preserves_dynamic_and_scales_leakage():
    model = LeakageModel.exponential(10.0)
    total, leak = 1.0, 0.4          # dynamic = 0.6
    # at T = Tref, unchanged
    assert rescale_total_power(total, leak, TREF, model, T_ref=TREF) == pytest.approx(1.0)
    # at T = Tref + 10, leakage doubles: 0.6 + 0.8 = 1.4
    assert rescale_total_power(total, leak, TREF + 10, model, T_ref=TREF) == pytest.approx(1.4)
    # cooling to Tref - 10 halves leakage: 0.6 + 0.2 = 0.8  (this is the savings goal-1 misses)
    assert rescale_total_power(total, leak, TREF - 10, model, T_ref=TREF) == pytest.approx(0.8)


def test_rescale_array_and_nonneg_clip():
    model = LeakageModel.exponential(10.0)
    total = np.array([1.0, 1.0, 1.0])
    leak = np.array([0.4, 0.4, 0.4])
    T = np.array([TREF, TREF + 10, TREF - 10])
    out = rescale_total_power(total, leak, T, model, T_ref=TREF)
    np.testing.assert_allclose(out, [1.0, 1.4, 0.8])


# ----------------------------------------------------------------------------
# rescale_trace with name mapping and missing-unit handling
# ----------------------------------------------------------------------------
def test_rescale_trace_with_name_map():
    model = LeakageModel.exponential(10.0)
    total = BasicPowerTrace({'iALU': [1.0, 1.0], 'FPU': [2.0, 2.0]}, time_step=1.0)
    leak = {'iALU': 0.4, 'FPU': 1.0}
    # temperatures keyed by FLOORPLAN name; power keyed by unit name -> map bridges them
    temps = {'iALU_flp': [TREF, TREF + 10], 'FPU_flp': [TREF, TREF - 10]}
    name_map = {'iALU': 'iALU_flp', 'FPU': 'FPU_flp'}.get
    out = rescale_trace(total, leak, temps, model, T_ref=TREF, name_map=name_map)
    np.testing.assert_allclose(out['iALU'], [1.0, 1.4])   # heated -> more leakage
    np.testing.assert_allclose(out['FPU'], [2.0, 1.5])    # cooled -> 1.0 dyn + 0.5 leak


def test_rescale_trace_missing_keeps_unchanged():
    model = LeakageModel.exponential(10.0)
    total = BasicPowerTrace({'known': [1.0], 'unknown': [3.0]}, time_step=1.0)
    leak = {'known': 0.4}                    # 'unknown' absent
    temps = {'known': [TREF + 10]}
    out = rescale_trace(total, leak, temps, model, T_ref=TREF, missing='keep')
    np.testing.assert_allclose(out['known'], [1.4])
    np.testing.assert_allclose(out['unknown'], [3.0])   # untouched
    with pytest.raises(KeyError):
        rescale_trace(total, leak, temps, model, T_ref=TREF, missing='error')


# ----------------------------------------------------------------------------
# Fixed-point power<->temperature feedback
# ----------------------------------------------------------------------------
def _lumped_thermal_solver(theta_K_per_W, t_ambient_K=TREF):
    """Return a thermal_solve_fn: per-unit T = ambient + theta * P (steady lumped model)."""
    def solve(trace):
        return {u: [t_ambient_K + theta_K_per_W * p for p in series]
                for u, series in trace.powers.items()}
    return solve


def test_feedback_converges_and_captures_leakage_increase():
    model = LeakageModel.exponential(10.0)
    total = BasicPowerTrace({'hot': [1.0]}, time_step=1.0)
    leak = {'hot': 0.4}
    # Mild thermal coupling -> contraction -> converges above the isothermal baseline.
    solver = _lumped_thermal_solver(theta_K_per_W=2.0, t_ambient_K=TREF)
    res = converge_power_temperature(total, leak, solver, model, T_ref=TREF,
                                     tol_K=1e-4, max_iter=50)
    assert res['converged']
    final_T = res['temp_trace']['hot'][0]
    final_P = res['power_trace']['hot'][0]
    # Self-consistent: T = ambient + theta*P and P = dyn + leak*scale(T)
    assert final_T == pytest.approx(TREF + 2.0 * final_P, abs=1e-3)
    # Feedback raised power above the frozen-leakage baseline (1.0 W) -- the effect goal-1 misses.
    assert final_P > 1.0


def test_feedback_flags_thermal_runaway_as_nonconvergence():
    model = LeakageModel.exponential(10.0)
    total = BasicPowerTrace({'hot': [1.0]}, time_step=1.0)
    leak = {'hot': 0.4}
    # Strong coupling: d(leak)/dT * theta > 1 -> divergent physical system -> must NOT report
    # false convergence within the iteration cap.
    solver = _lumped_thermal_solver(theta_K_per_W=60.0, t_ambient_K=TREF)
    res = converge_power_temperature(total, leak, solver, model, T_ref=TREF,
                                     tol_K=1e-3, max_iter=8)
    assert not res['converged']


def test_cooling_reduces_total_power():
    """Imposing a lower ambient (proxy for microrefrigeration) must lower converged power."""
    model = LeakageModel.exponential(10.0)
    total = BasicPowerTrace({'hot': [1.0]}, time_step=1.0)
    leak = {'hot': 0.4}
    hot = converge_power_temperature(total, leak, _lumped_thermal_solver(2.0, TREF),
                                     model, T_ref=TREF, tol_K=1e-5, max_iter=50)
    cooled = converge_power_temperature(total, leak, _lumped_thermal_solver(2.0, TREF - 30),
                                        model, T_ref=TREF, tol_K=1e-5, max_iter=50)
    assert cooled['power_trace']['hot'][0] < hot['power_trace']['hot'][0]


# ----------------------------------------------------------------------------
# Plumbing check against a real shipped 280-unit block_powers trace
# ----------------------------------------------------------------------------
_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'examples',
                           'ICE_simulation_from_MCPAT', 'traces', 'example_workload', '7nm')


@pytest.mark.skipif(not glob.glob(os.path.join(_SAMPLE_DIR, 'block_powers_*.json')),
                    reason='shipped sample trace not present')
def test_real_trace_plumbing_uniform_field():
    model = LeakageModel.exponential(10.0)
    fp = sorted(glob.glob(os.path.join(_SAMPLE_DIR, 'block_powers_*.json')))[0]
    with open(fp) as f:
        block = json.load(f)
    # Real trace has dynamic+leakage already summed; synthesize a plausible split (30% leak)
    # and a uniform field just to exercise the per-unit machinery at real scale (280 units).
    total = BasicPowerTrace({u: [float(v)] for u, v in block.items()}, time_step=1.0)
    leak = {u: 0.3 * float(v) for u, v in block.items()}
    temps = {u: [TREF + 15.0] for u in block}          # uniform +15 K everywhere
    out = rescale_trace(total, leak, temps, model, T_ref=TREF)
    assert set(out.powers) == set(block)               # all 280 units preserved
    # +15 K -> leakage *2^1.5; every (originally non-negative) unit's power should rise.
    base = sum(max(float(v), 0.0) for v in block.values())
    new = sum(max(float(out[u][0]), 0.0) for u in block)
    assert new > base


if __name__ == '__main__':
    import sys
    sys.exit(pytest.main([__file__, '-v']))
