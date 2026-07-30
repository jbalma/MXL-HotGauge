"""Tests for the 3D-ICE leakage-feedback wiring (HotGauge.thermal.leakage_feedback).

These do NOT run 3D-ICE (that needs the patched emulator + GNU parallel on the Linux
server). They exercise everything around the binary: the McPAT<->floorplan name bridge,
the split-file loading, and the full fixed-point orchestration on a real shipped 280-unit
trace using a mock thermal solver. Run with pytest or `python -m HotGauge.thermal.test_leakage_feedback`.
"""
import os
import glob
import json

import numpy as np
import pytest

from HotGauge.power import BasicPowerTrace
from HotGauge.thermal.leakage_feedback import (mcpat_flp_name_map, load_leakage_ref,
                                               find_split_files, run_leakage_feedback)
from HotGauge.power.leakage import LeakageModel

TREF = 360.0
_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'examples',
                           'ICE_simulation_from_MCPAT', 'traces', 'example_workload', '7nm')


# ---------------------------------------------------------------------------
# Name bridge
# ---------------------------------------------------------------------------
def test_name_map_core_units():
    nm = mcpat_flp_name_map(include_core_idx=True)
    assert nm('Core0/Execution Unit/Integer ALUs') == 'iALU_0'
    assert nm('Core7/L2') == 'L2_7'
    assert nm('Core3/Load Store Unit/Data Cache') == 'DCache_3'
    assert nm('Core0/Instruction Fetch Unit/Branch Predictor/Global Predictor') == 'gPred_0'
    assert nm('Core2/Execution Unit/Instruction Scheduler/ROB') == 'ROB_2'
    assert nm('Core0') == 'core_other_0'          # bare core maps to the aggregate block


def test_name_map_returns_none_for_unmappable_aggregates():
    nm = mcpat_flp_name_map(include_core_idx=True)
    for agg in ('Processor/Total L3s', 'BUSES', 'BUSES/Bus', 'NUCA', 'IMC', 'Processor'):
        assert nm(agg) is None


def test_name_map_without_core_idx():
    nm = mcpat_flp_name_map(include_core_idx=False)
    assert nm('Core0/Execution Unit/Integer ALUs') == 'iALU'


# ---------------------------------------------------------------------------
# Split-file loading
# ---------------------------------------------------------------------------
def test_load_leakage_ref_and_ordering(tmp_path):
    # Write split files out of order to check tick-sorted loading.
    payloads = {
        200: {'Core0/Execution Unit/Integer ALUs': [0.8, 0.2], 'IMC': [1.0, 0.0]},
        100: {'Core0/Execution Unit/Integer ALUs': [0.6, 0.1], 'IMC': [1.0, 0.0]},
    }
    for tick, data in payloads.items():
        with open(tmp_path / 'block_powers_split_{}.json'.format(tick), 'w') as f:
            json.dump(data, f)
    files = find_split_files(str(tmp_path))
    assert [os.path.basename(f) for f in files] == ['block_powers_split_100.json',
                                                     'block_powers_split_200.json']
    leak = load_leakage_ref(files)
    # leakage is the SECOND element; ordering follows ticks 100 then 200
    np.testing.assert_allclose(leak['Core0/Execution Unit/Integer ALUs'], [0.1, 0.2])
    np.testing.assert_allclose(leak['IMC'], [0.0, 0.0])


def test_load_leakage_ref_fills_missing_units(tmp_path):
    with open(tmp_path / 'block_powers_split_1.json', 'w') as f:
        json.dump({'A': [1.0, 0.3]}, f)
    with open(tmp_path / 'block_powers_split_2.json', 'w') as f:
        json.dump({'A': [1.0, 0.3], 'B': [2.0, 0.5]}, f)   # B appears only at t=2
    leak = load_leakage_ref(find_split_files(str(tmp_path)))
    np.testing.assert_allclose(leak['A'], [0.3, 0.3])
    np.testing.assert_allclose(leak['B'], [0.0, 0.5])       # filled 0.0 at t=1


# ---------------------------------------------------------------------------
# Full orchestration with a mock 3D-ICE solver on the real 280-unit trace
# ---------------------------------------------------------------------------
def _mock_solver(theta_K_per_W, ambient_K=TREF, include_core_idx=True):
    """Return a thermal_solve_fn that maps the McPAT-named trace to floorplan-named temps
    via the real name bridge, so it exercises exactly the keys run_leakage_feedback looks up.
    T = ambient + theta * P (steady lumped model), only for mappable units.
    """
    nm = mcpat_flp_name_map(include_core_idx=include_core_idx)

    def solve(trace):
        temps = {}
        for unit, series in trace.powers.items():
            key = nm(unit)
            if key is None:
                continue
            temps[key] = [ambient_K + theta_K_per_W * max(float(p), 0.0) for p in series]
        return temps
    return solve


@pytest.mark.skipif(not glob.glob(os.path.join(_SAMPLE_DIR, 'block_powers_*.json')),
                    reason='shipped sample trace not present')
def test_orchestration_on_real_trace_converges_and_bridges_names():
    fp = sorted(glob.glob(os.path.join(_SAMPLE_DIR, 'block_powers_*.json')))[0]
    with open(fp) as f:
        block = json.load(f)
    baseline = BasicPowerTrace({u: [float(v)] for u, v in block.items()}, time_step=1.0)
    leak = {u: np.array([0.3 * max(float(v), 0.0)]) for u, v in block.items()}

    res = run_leakage_feedback(baseline, leak, _mock_solver(theta_K_per_W=1.0),
                               model=LeakageModel.exponential(10.0), T_ref=TREF,
                               num_cores=8, tol_K=1e-3, max_iter=25)
    assert res['converged']
    # A mappable, high-power unit should have had its leakage scaled (power changed from
    # baseline); an unmappable aggregate (IMC) should be untouched.
    conv = res['power_trace']
    hot_unit = 'Core0/Execution Unit/Integer ALUs'
    assert conv[hot_unit][0] != pytest.approx(block[hot_unit], rel=1e-6)   # feedback applied
    if 'IMC' in block:
        assert conv['IMC'][0] == pytest.approx(block['IMC'])               # left frozen


@pytest.mark.skipif(not glob.glob(os.path.join(_SAMPLE_DIR, 'block_powers_*.json')),
                    reason='shipped sample trace not present')
def test_orchestration_cooling_lowers_power():
    fp = sorted(glob.glob(os.path.join(_SAMPLE_DIR, 'block_powers_*.json')))[0]
    with open(fp) as f:
        block = json.load(f)
    baseline = BasicPowerTrace({u: [float(v)] for u, v in block.items()}, time_step=1.0)
    leak = {u: np.array([0.3 * max(float(v), 0.0)]) for u, v in block.items()}
    model = LeakageModel.exponential(10.0)

    hot = run_leakage_feedback(baseline, leak, _mock_solver(1.0, ambient_K=TREF),
                               model=model, T_ref=TREF, num_cores=8, tol_K=1e-4, max_iter=25)
    cool = run_leakage_feedback(baseline, leak, _mock_solver(1.0, ambient_K=TREF - 25),
                                model=model, T_ref=TREF, num_cores=8, tol_K=1e-4, max_iter=25)
    hot_unit = 'Core0/Execution Unit/Integer ALUs'
    assert cool['power_trace'][hot_unit][0] < hot['power_trace'][hot_unit][0]


if __name__ == '__main__':
    import sys
    sys.exit(pytest.main([__file__, '-v']))
