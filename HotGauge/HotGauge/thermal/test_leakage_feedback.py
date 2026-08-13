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
                                               find_split_files, run_leakage_feedback,
                                               collapse_trace_for_steady,
                                               broadcast_steady_temps, ICEThermalSolver,
                                               assert_steady_supported,
                                               SteadyStateUnsupportedError,
                                               mcpat_tref_from_trace_dir,
                                               load_calibrated_leakage_model)
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


# ---------------------------------------------------------------------------
# Steady-state mode
# ---------------------------------------------------------------------------
def test_collapse_trace_mean_averages_over_time():
    trace = BasicPowerTrace({'a': [1.0, 2.0, 3.0], 'b': [10.0, 10.0, 10.0]}, time_step=1.0)
    out = collapse_trace_for_steady(trace, reduce='mean')
    assert len(out) == 1
    assert out.powers['a'][0] == pytest.approx(2.0)
    assert out.powers['b'][0] == pytest.approx(10.0)
    assert out.time_step == trace.time_step


def test_collapse_trace_max_takes_per_block_peak():
    trace = BasicPowerTrace({'a': [1.0, 5.0, 3.0], 'b': [9.0, 2.0, 2.0]}, time_step=1.0)
    out = collapse_trace_for_steady(trace, reduce='max')
    # Peaks are taken per block independently -- deliberately not a single real instant.
    assert out.powers['a'][0] == pytest.approx(5.0)
    assert out.powers['b'][0] == pytest.approx(9.0)


def test_collapse_trace_rejects_unknown_reducer():
    trace = BasicPowerTrace({'a': [1.0, 2.0]}, time_step=1.0)
    with pytest.raises(ValueError):
        collapse_trace_for_steady(trace, reduce='median')


def test_broadcast_steady_temps_matches_trace_length():
    out = broadcast_steady_temps({'iALU_0': np.array([350.0]), 'FPUs_0': 340.0}, 4)
    assert out['iALU_0'].shape == (4,)
    assert np.all(out['iALU_0'] == 350.0)
    # A bare scalar is accepted as well as a 1-element array.
    assert np.all(out['FPUs_0'] == 340.0)


def test_broadcast_steady_temps_rejects_empty_block():
    with pytest.raises(ValueError):
        broadcast_steady_temps({'iALU_0': np.array([])}, 3)


def test_steady_broadcast_length_satisfies_rescale_trace():
    """The whole point of broadcasting: rescale_trace requires temps.shape == power.shape."""
    from HotGauge.power.leakage import rescale_trace
    trace = BasicPowerTrace({'Core0/Execution Unit/Integer ALUs': [1.0, 2.0, 3.0]},
                            time_step=1.0)
    temps = broadcast_steady_temps({'iALU_0': np.array([TREF + 10.0])}, len(trace))
    out = rescale_trace(trace, {'Core0/Execution Unit/Integer ALUs': 0.5}, temps,
                        LeakageModel.exponential(10.0), T_ref=TREF,
                        name_map=mcpat_flp_name_map(include_core_idx=True))
    # 10 K above T_ref with doubling-per-10 K => leakage 0.5 -> 1.0, so each step gains 0.5 W.
    assert out['Core0/Execution Unit/Integer ALUs'] == pytest.approx([1.5, 2.5, 3.5])


def test_solver_rejects_bad_mode_and_reducer():
    with pytest.raises(ValueError):
        ICEThermalSolver('s.stk', 'f.flp', 7, '/tmp/x', mode='transonic')
    with pytest.raises(ValueError):
        ICEThermalSolver('s.stk', 'f.flp', 7, '/tmp/x', steady_reduce='median')


def test_solver_steady_mode_dispatches_and_broadcasts(monkeypatch):
    """mode='steady' must call the steady path and return per-timestep series."""
    calls = {}

    class FakeSteadySolver(ICEThermalSolver):
        def _run_steady_and_read_temps(self, dice_trace, run_dir, n_steps):
            calls['n_steps'] = n_steps
            calls['collapsed'] = collapse_trace_for_steady(dice_trace, self.steady_reduce)
            return broadcast_steady_temps({'iALU_0': np.array([355.0])}, n_steps)

        def _run_and_read_temps(self, dice_trace, run_dir):
            raise AssertionError('transient path must not run in steady mode')

    solver = FakeSteadySolver('s.stk', 'f.flp', 7, '/tmp/x', mode='steady', num_cores=1)
    monkeypatch.setattr('HotGauge.thermal.leakage_feedback.prepare_dice_trace',
                        lambda trace, *a, **k: trace)
    trace = BasicPowerTrace({'iALU_0': [1.0, 2.0, 3.0, 4.0]}, time_step=1.0)
    temps = solver(trace)
    assert calls['n_steps'] == 4
    assert calls['collapsed'].powers['iALU_0'][0] == pytest.approx(2.5)
    assert temps['iALU_0'].shape == (4,)


def test_assert_steady_supported_rejects_pluggable_stack(tmp_path):
    """A pluggable heatsink must be refused: 3D-ICE would silently return the initial temp."""
    stk = tmp_path / 'plug.stk'
    stk.write_text('heat sink :\n'
                   '   plugin "{ICE_DIR}/heatsink_plugin/loaders/FMI/fmi_loader.so", '
                   '"HS483_P14752_ConstantFanSpeed_Interface3DICE 0.015 0.015 303.15 6000" ;\n')
    with pytest.raises(SteadyStateUnsupportedError) as exc:
        assert_steady_supported(str(stk))
    assert 'steady' in str(exc.value).lower()


def test_assert_steady_supported_allows_conventional_stack(tmp_path):
    stk = tmp_path / 'conv.stk'
    stk.write_text('heat sink :\n   heat transfer coefficient 1.0e-7 ;\n')
    assert_steady_supported(str(stk)) is None


@pytest.mark.skipif(not os.path.isdir(_SAMPLE_DIR), reason='shipped stack templates not present')
def test_shipped_fmu_stacks_are_rejected_for_steady():
    """Guard against the real shipped templates, not just a synthetic one."""
    from HotGauge.thermal import get_stack_template
    for name in ('skylake_HS483', 'skylake_kryos'):
        with pytest.raises(SteadyStateUnsupportedError):
            assert_steady_supported(get_stack_template(name))
    # The plain convection stack must remain usable in steady mode.
    assert_steady_supported(get_stack_template('skylake'))


def test_tref_is_read_from_the_trace_xml_not_guessed(tmp_path):
    """A guessed T_ref is a ~4x leakage error per 30 K; it must come from the XML."""
    (tmp_path / 'energystats-temp-100.xml').write_text(
        '<component id="system">\n  <param name="temperature" value="330"/>\n</component>\n')
    assert mcpat_tref_from_trace_dir(str(tmp_path)) == pytest.approx(330.0)


def test_tref_returns_none_when_no_xml_so_caller_must_decide(tmp_path):
    assert mcpat_tref_from_trace_dir(str(tmp_path)) is None


def test_load_calibrated_leakage_model_roundtrip(tmp_path):
    cal = {'t_ref_xml_K': 330.0,
           'rows': [{'T_K': 330.0}, {'T_K': 350.0}, {'T_K': 370.0}],
           'rel_leakage': [1.0, 1.6, 6.0]}
    p = tmp_path / 'cal.json'
    p.write_text(json.dumps(cal))
    model, t_ref = load_calibrated_leakage_model(str(p))
    assert t_ref == pytest.approx(330.0)
    assert model.scale(330.0, T_ref=330.0) == pytest.approx(1.0)
    assert model.scale(370.0, T_ref=330.0) == pytest.approx(6.0)
    # Interpolated, not exponential-fitted.
    assert model.scale(360.0, T_ref=330.0) == pytest.approx((1.6 + 6.0) / 2)


def test_load_calibrated_leakage_model_rejects_mismatched_lengths(tmp_path):
    p = tmp_path / 'bad.json'
    p.write_text(json.dumps({'t_ref_xml_K': 330.0, 'rows': [{'T_K': 330.0}],
                             'rel_leakage': [1.0, 2.0]}))
    with pytest.raises(ValueError):
        load_calibrated_leakage_model(str(p))


def test_measured_curve_is_flat_when_cool_and_steep_when_hot():
    """The central physical finding: McPAT leakage barely moves below ~340 K and explodes
    above ~350 K, so a single doubling constant cannot describe it."""
    from HotGauge.power.leakage import LeakageModel
    temps = [310., 320., 330., 340., 350., 360., 370., 380., 390., 400.]
    rel = [0.923078, 0.946747, 1.0, 1.130173, 1.59761, 3.153769, 6.041236, 9.591414,
           16.159236, 36.09929]
    m = LeakageModel.from_table(temps, rel)
    cool_decade = m.scale(330.0, T_ref=310.0)     # 20 K rise while cool
    hot_decade = m.scale(400.0, T_ref=380.0)      # 20 K rise while hot
    assert cool_decade < 1.15          # ~8% over 20 K
    assert hot_decade > 3.0            # ~3.8x over the same 20 K
    # An exponential with a single constant cannot span both regimes.
    assert hot_decade / cool_decade > 3.0


def test_die_power_counts_only_what_lands_on_a_floorplan_block(tmp_path):
    """Summing the DICE trace overstates simulated power 2.36x on the real trace: the
    hierarchy aggregates are still in the dict and get silently dropped later."""
    from HotGauge.thermal.leakage_feedback import die_power_of_trace
    import HotGauge.thermal.leakage_feedback as lf

    class FakeEl:
        def __init__(self, n): self.name = n
    class FakeFlp:
        elements = [FakeEl('iALU_0'), FakeEl('FPUs_0')]

    trace = BasicPowerTrace({'x': [1.0]}, 1.0)
    # prepare_dice_trace is the stock renamer; stub it to isolate the accounting logic.
    fake = BasicPowerTrace({'iALU_0': [3.0], 'FPUs_0': [2.0],
                            'Processor': [99.0],            # aggregate -> correctly dropped
                            'Processor/Total L3s': [7.0],   # aggregate -> correctly dropped
                            'iALU_7': [1.5]}, 1.0)          # real leaf, no block -> REAL loss
    orig = lf.prepare_dice_trace
    lf.prepare_dice_trace = lambda *a, **k: fake
    try:
        p, info = die_power_of_trace(trace, FakeFlp(), 7, num_cores=8, detail=True)
    finally:
        lf.prepare_dice_trace = orig

    assert p == pytest.approx(5.0)                       # only the two real blocks
    assert info['dropped_aggregate_W'] == pytest.approx(106.0)
    assert info['dropped_leaf_W'] == pytest.approx(1.5)   # the genuine loss, isolated
    assert 'iALU_7' in info['dropped_leaves']


def test_aggregate_bridge_feeds_back_l3_leakage():
    """Processor/Total L3s carries 1.23 W of leakage on the real trace -- 45 % more than
    everything else in the loop. Without bridging it stays frozen at T_ref."""
    from HotGauge.thermal.leakage_feedback import AGG_L3_TEMP_KEY
    trace = BasicPowerTrace({'Processor/Total L3s': [10.0],
                             'Core0/Execution Unit/Integer ALUs': [10.0]}, 1.0)
    leak = {'Processor/Total L3s': 1.0, 'Core0/Execution Unit/Integer ALUs': 1.0}

    def solver(tr):
        # L3 blocks run hot; the aggregate must pick that up via the synthetic key.
        return {'L3_0': [TREF + 30.0], 'L3_1': [TREF + 30.0], 'iALU_0': [TREF + 30.0]}

    model = LeakageModel.exponential(10.0)
    off = run_leakage_feedback(trace, leak, solver, model=model, T_ref=TREF, num_cores=2,
                               tol_K=1e-3, max_iter=1, relax=1.0, bridge_aggregates=False)
    on = run_leakage_feedback(trace, leak, solver, model=model, T_ref=TREF, num_cores=2,
                              tol_K=1e-3, max_iter=1, relax=1.0, bridge_aggregates=True)
    # Unbridged: L3 aggregate power untouched. Bridged: it grows with temperature.
    assert off['power_trace']['Processor/Total L3s'][0] == pytest.approx(10.0)
    assert on['power_trace']['Processor/Total L3s'][0] > 10.0
    # The ordinary mapped unit behaves the same either way.
    assert (off['power_trace']['Core0/Execution Unit/Integer ALUs'][0]
            == pytest.approx(on['power_trace']['Core0/Execution Unit/Integer ALUs'][0]))


def test_nuca_is_not_bridged_so_l3_is_not_double_counted():
    """NUCA restates Processor/Total L3s; bridging both would count the L3 twice."""
    from HotGauge.thermal.leakage_feedback import aggregate_aware_name_map
    nm = aggregate_aware_name_map(num_cores=8)
    assert nm('Processor/Total L3s') is not None
    assert nm('NUCA') is None
    assert nm('Processor') is None
    assert nm('Processor/Total Cores') is None


def test_augment_is_a_noop_without_l3_blocks():
    from HotGauge.thermal.leakage_feedback import augment_temps_with_aggregates
    t = {'iALU_0': [350.0]}
    assert augment_temps_with_aggregates(t, num_cores=8) == t


def test_solver_defaults_to_transient():
    solver = ICEThermalSolver('s.stk', 'f.flp', 7, '/tmp/x')
    assert solver.mode == 'transient'
    assert solver.steady_reduce == 'mean'


if __name__ == '__main__':
    import sys
    sys.exit(pytest.main([__file__, '-v']))
