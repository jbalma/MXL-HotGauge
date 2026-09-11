"""The cache-leakage planner objective (§P0.22, D3): per-zone targets, the objective peak, and
the leakage ledger. Synthetic solvers throughout -- no 3D-ICE."""
import numpy as np
import pytest

from HotGauge.power import BasicPowerTrace, LeakageModel
from HotGauge.thermal.microrefrigeration import (MRParams, clipping_plan, objective_peak,
                                                 zone_report, run_mr_clipping,
                                                 _relax_plan_toward_target)
from HotGauge.thermal.leakage_ledger import unit_leakage_W, zone_leakage_W, leakage_ledger

GEOM = {'cALU_0': {'area_mm2': 0.02, 'min_dim_um': 140.0},
        'L2_0': {'area_mm2': 0.5, 'min_dim_um': 700.0},
        'L3_0': {'area_mm2': 0.4, 'min_dim_um': 600.0}}
CACHE = [('^(L2|L3)', 280.0)]


# ---------------------------------------------------------------------------
# parameters
# ---------------------------------------------------------------------------
def test_default_params_have_no_zones_and_read_as_the_peak_objective():
    p = MRParams(target_K=365.0)
    assert not p.has_zones and p.objective == 'peak'
    assert p.target_for('L2_0') == 365.0 and p.target_for('cALU_0') == 365.0
    assert 'zones=' not in repr(p)


def test_zone_targets_resolve_by_regex_search_first_match_wins():
    p = MRParams(target_K=365.0, zone_targets=[('^L2', 300.0), ('^(L2|L3)', 280.0)],
                 objective='cache-leakage')
    assert p.has_zones and p.objective == 'cache-leakage'
    assert p.target_for('L2_7') == 300.0          # first pattern
    assert p.target_for('L3_12') == 280.0
    assert p.target_for('cALU_3') == 365.0
    assert 'zones=[' in repr(p) and '280 K' in repr(p)
    assert MRParams(target_K=365.0, zone_targets=CACHE).objective == 'zoned'


def test_a_nonpositive_zone_target_is_rejected():
    with pytest.raises(ValueError):
        MRParams(target_K=365.0, zone_targets=[('^L2', 0.0)])


# ---------------------------------------------------------------------------
# the objective peak
# ---------------------------------------------------------------------------
def test_objective_peak_is_the_plain_peak_without_zones_including_synthetic_keys():
    rng = np.random.RandomState(3)
    for _ in range(20):
        temps = {'cALU_0': rng.uniform(300, 420), 'L2_0': rng.uniform(300, 420),
                 '__agg__L3': rng.uniform(300, 420), 'IO_N': np.array([0.0, 0.0])}
        p = MRParams(target_K=365.0)
        plain = max(float(np.ravel(t)[-1]) for t in temps.values()
                    if float(np.ravel(t)[-1]) > 200.0)
        assert objective_peak(temps, p, 200.0) == plain      # bit-identical, not approx


def test_objective_peak_reads_the_worst_excess_over_each_blocks_own_target():
    p = MRParams(target_K=365.0, zone_targets=CACHE)
    # cALU 5 K over its target; L2 40 K over ITS target -> the L2 decides
    temps = {'cALU_0': 370.0, 'L2_0': 320.0, '__agg__L3': 500.0, 'IO_N': 0.0}
    assert objective_peak(temps, p) == pytest.approx(365.0 + 40.0)
    # every block at or below its own target reads as "at target"
    assert objective_peak({'cALU_0': 360.0, 'L2_0': 275.0}, p) <= 365.0
    assert np.isnan(objective_peak({'IO_N': 0.0}, p))


def test_zone_report_summarises_each_zone_against_its_own_target():
    p = MRParams(target_K=365.0, zone_targets=CACHE)
    temps = {'cALU_0': 370.0, 'L2_0': 320.0, 'L3_0': 270.0, '__agg__L3': 999.0}
    z = zone_report(temps, p)
    c = z['^(L2|L3)']
    assert c['n_blocks'] == 2 and c['target_K'] == 280.0
    assert c['max_K'] == 320.0 and c['mean_K'] == pytest.approx(295.0)
    assert c['n_above_target'] == 1 and c['worst_excess_K'] == pytest.approx(40.0)
    assert z['rest']['n_blocks'] == 1 and z['rest']['max_K'] == 370.0


# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------
def test_clipping_plan_cools_a_cache_block_against_the_zone_target_only():
    hot = {'cALU_0': 340.0, 'L2_0': 340.0}
    sens = {'cALU_0': 1.0, 'L2_0': 1.0}
    p_peak = MRParams(target_K=365.0, h_max=1e6, dt_max_K=1e6)
    plan, _ = clipping_plan(hot, GEOM, p_peak, sens)
    assert plan == {}                                   # nothing above the hot-spot target
    p_zone = MRParams(target_K=365.0, h_max=1e6, dt_max_K=1e6, zone_targets=CACHE)
    plan, detail = clipping_plan(hot, GEOM, p_zone, sens)
    assert 'cALU_0' not in plan
    assert plan['L2_0'] == pytest.approx(60.0) and detail['L2_0']['excess_K'] == pytest.approx(60.0)
    assert detail['L2_0']['limit'] == 'need'


def test_the_scalar_lift_binds_on_the_cache_block_and_says_so():
    p = MRParams(target_K=365.0, h_max=1e6, dt_max_K=45.0, zone_targets=CACHE)
    plan, detail = clipping_plan({'L2_0': 340.0}, GEOM, p, {'L2_0': 1.0})
    assert plan['L2_0'] == pytest.approx(45.0) and detail['L2_0']['limit'] == 'dt_max'


def test_relax_step_pushes_each_block_toward_its_own_target():
    p = MRParams(target_K=365.0, zone_targets=CACHE)
    env = {'cALU_0': 100.0, 'L2_0': 100.0}
    temps = {'cALU_0': np.array([365.0]), 'L2_0': np.array([300.0])}
    new = _relax_plan_toward_target({'cALU_0': 5.0, 'L2_0': 5.0}, env, temps, p,
                                    {'cALU_0': 1.0, 'L2_0': 1.0}, relax=1.0, t_floor_K=200.0)
    assert new['cALU_0'] == pytest.approx(5.0)          # at its target: unchanged
    assert new['L2_0'] == pytest.approx(25.0)           # 20 K above 280 K: +20 W


# ---------------------------------------------------------------------------
# the loop: two independent blocks, linear responses
# ---------------------------------------------------------------------------
def _run(params, T0=None, s=None, max_iter=12, tol_K=1.0):
    T0 = T0 or {'cALU_0': 380.0, 'L2_0': 340.0}
    s = s or {'cALU_0': 1.0, 'L2_0': 1.0}
    trace = BasicPowerTrace({b: np.array([10.0]) for b in T0}, 1.0)
    state = {'plan': {}}
    calls = {'n': 0}

    def solve(tr):
        calls['n'] += 1
        # legacy in-source placement: the cooling is subtracted from the trace
        return {b: np.array([T0[b] - s[b] * (10.0 - float(tr.powers[b][0]))]) for b in T0}

    res = run_mr_clipping(trace, solve, GEOM, params, lambda u: u,
                          status_fn=lambda: {'diverged': False}, die_power_W=500.0,
                          calibrate=False, initial_sensitivity=dict(s), max_iter=max_iter,
                          tol_K=tol_K)
    return res, calls['n']


def test_the_default_objective_ignores_a_cache_block_below_the_hot_spot_target():
    res, _ = _run(MRParams(target_K=365.0, h_max=1e6, dt_max_K=1e6))
    assert res['objective'] == 'peak' and 'zones' not in res
    assert 'L2_0' not in res['plan'] and res['plan']['cALU_0'] == pytest.approx(15.0, abs=1.5)


def test_the_cache_objective_drives_the_cache_to_its_zone_target_and_reports_the_zone():
    res, _ = _run(MRParams(target_K=365.0, h_max=1e6, dt_max_K=1e6, zone_targets=CACHE,
                           objective='cache-leakage'))
    assert res['objective'] == 'cache-leakage'
    assert res['plan']['L2_0'] == pytest.approx(60.0, abs=1.5)
    assert res['plan']['cALU_0'] == pytest.approx(15.0, abs=1.5)
    z = res['zones']['^(L2|L3)']
    assert z['target_K'] == 280.0 and z['max_K'] == pytest.approx(280.0, abs=1.5)
    assert res['zones']['rest']['max_K'] == pytest.approx(365.0, abs=1.5)


def test_with_the_scalar_lift_kept_the_cache_zone_is_lift_bound_and_the_plan_does_not_hold():
    res, _ = _run(MRParams(target_K=365.0, h_max=1e6, dt_max_K=45.0, zone_targets=CACHE))
    assert res['plan']['L2_0'] == pytest.approx(45.0, abs=1e-6)
    assert res['detail']['L2_0']['limit'] == 'dt_max'
    assert res['plan_holds_target'] is False and res['dt_max_bound'] is True
    assert res['zones']['^(L2|L3)']['max_K'] == pytest.approx(295.0, abs=0.5)


# ---------------------------------------------------------------------------
# the ledger
# ---------------------------------------------------------------------------
def test_unit_leakage_is_priced_on_the_loops_own_curve_and_name_map():
    model = LeakageModel.exponential(10.0)      # doubles every 10 K
    ref = {'Core0/L2': 1.0, 'Core0/cALU': 2.0, 'Processor/Total L3s': 4.0, 'IO': 1.0}
    nm = {'Core0/L2': 'L2_0', 'Core0/cALU': 'cALU_0', 'Processor/Total L3s': '__agg__L3',
          'IO': 'IO_N'}.get
    temps = {'L2_0': np.array([340.0, 350.0]), 'cALU_0': 330.0, '__agg__L3': 320.0,
             'IO_N': 0.0}
    per = unit_leakage_W(temps, ref, model, 330.0, nm)
    assert per['Core0/L2'][0] == pytest.approx(4.0)        # +20 K, last sample
    assert per['Core0/cALU'][0] == pytest.approx(2.0)
    assert per['Processor/Total L3s'][0] == pytest.approx(2.0)   # -10 K via the aggregate key
    assert per['IO'][0] == pytest.approx(1.0) and per['IO'][2] is None   # at the floor: T_ref
    assert zone_leakage_W(temps, ref, model, 330.0, nm, pattern='^(L2|L3)') == pytest.approx(6.0)
    assert zone_leakage_W(temps, ref, model, 330.0, nm) == pytest.approx(9.0)
    led = leakage_ledger(temps, ref, model, 330.0, nm, zones={'cache': '^(L2|L3)'})
    assert led['die_leakage_W'] == pytest.approx(9.0)
    assert led['reference_leakage_W'] == pytest.approx(8.0)
    assert led['zones']['cache'] == pytest.approx(6.0)
    assert led['n_units'] == 4 and led['n_units_at_floor'] == 1 and led['n_units_off_die'] == 0


def test_a_unit_with_no_block_behind_it_is_not_counted_but_is_reported():
    model = LeakageModel.exponential(10.0)
    led = leakage_ledger({'A': 330.0}, {'a': 3.0, 'b': 5.0}, model, 330.0,
                         {'a': 'A', 'b': None}.get, zones={})
    assert led['die_leakage_W'] == pytest.approx(3.0)
    assert led['n_units'] == 1 and led['n_units_off_die'] == 1
    assert led['off_die_reference_W'] == pytest.approx(5.0)


def test_restating_rows_drop_out_and_the_bare_core_row_counts_as_the_slab():
    """The first D3 rows read 45.7 W of die leakage on a 99 W die: every key in the split file
    was summed and Processor / Total Cores / NUCA restate their children. A true-leaf rule then
    dropped the bare Core<N> row, which is the core_other slab. The pipeline's rule -- a unit
    counts iff its temperature key is on the solved die -- gets both right."""
    model = LeakageModel.exponential(10.0)
    ref = {'Processor': 100.0, 'Processor/Total Cores': 60.0, 'Processor/Total L3s': 40.0,
           'NUCA': 40.0, 'Core0': 30.0, 'Core0/L2': 10.0, 'Core0/Load Store Unit': 20.0,
           'Core0/Load Store Unit/Data Cache': 20.0}
    nm = {'Core0': 'core_other_0', 'Core0/L2': 'L2_0',
          'Core0/Load Store Unit/Data Cache': 'DCache_0',
          'Processor/Total L3s': '__agg__L3'}.get          # everything else -> None
    temps = {'core_other_0': 330.0, 'L2_0': 330.0, 'DCache_0': 330.0, '__agg__L3': 330.0}
    led = leakage_ledger(temps, ref, model, 330.0, nm, zones={'cache': '^(L2|L3)'})
    assert led['die_leakage_W'] == pytest.approx(100.0)      # 30 + 10 + 20 + 40
    assert led['zones']['cache'] == pytest.approx(50.0)
    assert led['n_units'] == 4 and led['n_units_off_die'] == 4
    assert led['off_die_reference_W'] == pytest.approx(220.0)


def test_the_ledger_reproduces_the_registers_die_ratios_on_the_34_core_die():
    """The rule is pinned to examples/cold_zone_prize.die_ratios: same static watts and cache
    share on the hierarchy-consistent 8-core trace against the 34-core floorplan, at T_ref."""
    import os, glob, json, sys
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    flp = os.path.join(repo, 'examples', 'floorplans', 'outputs',
                       'skylake7nm_34core_3_3D-ICE_template.flp')
    trace = os.path.join(repo, 'mcpat_runs', '7nm', 'linpack_3.8GHz')
    if not (os.path.isfile(flp) and os.path.isdir(trace)):
        pytest.skip('needs the 34-core floorplan and the linpack trace')
    sys.path.insert(0, os.path.join(repo, 'examples'))
    from cold_zone_prize import die_ratios, STEADY_FROM_TICK
    from HotGauge.power.core_other import resolve_trace_dir
    from HotGauge.thermal.leakage_feedback import aggregate_aware_name_map
    from HotGauge.thermal.ICE import Floorplan
    d = resolve_trace_dir(trace, 'hierarchy-consistent')
    files = [f for f in sorted(glob.glob(os.path.join(d, 'block_powers_split_*.json')))
             if int(f.rsplit('_', 1)[1].split('.')[0]) >= STEADY_FROM_TICK]
    ref = {k: v[1] for k, v in json.load(open(files[-1])).items()}
    temps = {e.name: 330.0 for e in Floorplan.from_file(flp).elements}
    temps['__agg__L3'] = 330.0
    model = LeakageModel.exponential(10.0)
    led = leakage_ledger(temps, ref, model, 330.0, aggregate_aware_name_map(True, 34),
                         zones={'cache': '^(L2|L3)'})
    r = die_ratios(d, flp=flp)
    # die_ratios averages the steady slices; the last slice alone agrees to a percent
    assert led['die_leakage_W'] == pytest.approx(r['static_W'], rel=0.02)
    assert led['zones']['cache'] / led['die_leakage_W'] == pytest.approx(
        r['cache_share_of_leakage'], abs=0.01)


# ---------------------------------------------------------------------------
# the envelope shape (§P0.24)
# ---------------------------------------------------------------------------
def test_default_envelope_shape_is_seed_and_unchanged():
    p = MRParams(target_K=365.0)
    assert p.envelope_shape == 'seed'
    from HotGauge.thermal.microrefrigeration import envelope_plan
    plan, detail = envelope_plan(GEOM, MRParams(target_K=365.0, h_max=1e6, dt_max_K=45.0),
                                 {b: 1.0 for b in GEOM})
    assert all(abs(q - 45.0) < 1e-9 for q in plan.values())        # the uniform seed shape
    with pytest.raises(ValueError):
        MRParams(target_K=365.0, envelope_shape='area')


def test_power_shape_caps_each_block_at_its_own_dissipation_and_meets_conservation():
    from HotGauge.thermal.microrefrigeration import envelope_plan
    p = MRParams(target_K=365.0, h_max=1e6, dt_max_K=45.0, envelope_shape='power')
    own = {'cALU_0': 12.0, 'L2_0': 3.0, 'L3_0': 0.0}
    plan, detail = envelope_plan(GEOM, p, {b: 1.0 for b in GEOM}, die_power_W=15.0,
                                 q_cap_by_block=own)
    assert plan == {'cALU_0': 12.0, 'L2_0': 3.0}                   # L3_0 has nothing to remove
    assert detail['cALU_0']['limit'] == 'own_power'
    assert 'die_power_scaled' not in detail['cALU_0']['limit']    # conservation met by construction


def test_run_mr_clipping_power_shape_starts_from_the_blocks_own_heat():
    """A diverging baseline (the rescue regime): the seed shape starts from 45 W per block
    scaled by conservation; the power shape starts from each block's own dissipation."""
    T0 = {'cALU_0': 380.0, 'L2_0': 340.0}
    trace = BasicPowerTrace({b: np.array([10.0 if b == 'cALU_0' else 2.0]) for b in T0}, 1.0)
    seen = []
    calls = {'n': 0}

    def solve(tr):
        calls['n'] += 1
        removed = {b: 10.0 - float(tr.powers[b][0]) if b == 'cALU_0' else 2.0 - float(tr.powers[b][0]) for b in T0}
        seen.append(dict(removed))
        if calls['n'] == 1:                    # the uncooled baseline diverges
            return {b: np.array([np.nan]) for b in T0}
        return {b: np.array([T0[b] - 1.0 * removed[b]]) for b in T0}

    st = {'n': 0}

    def status():
        st['n'] += 1
        return {'diverged': st['n'] == 1}

    p = MRParams(target_K=365.0, h_max=1e6, dt_max_K=45.0, envelope_shape='power')
    res = run_mr_clipping(trace, solve, GEOM, p, lambda u: u, status_fn=status, die_power_W=12.0,
                          calibrate=False, initial_sensitivity={b: 1.0 for b in T0}, max_iter=3, tol_K=1.0)
    assert res['envelope_shape'] == 'power'
    first = seen[1]                            # the full-envelope application
    assert abs(first['cALU_0'] - 10.0) < 1e-9 and abs(first['L2_0'] - 2.0) < 1e-9
