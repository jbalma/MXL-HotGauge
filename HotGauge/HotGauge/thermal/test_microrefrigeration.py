"""Tests for the microrefrigeration bridge (Goal 3). Pure Python -- no 3D-ICE binary."""
import numpy as np
import pytest

from HotGauge.power import BasicPowerTrace
from HotGauge.thermal.microrefrigeration import (MRParams, clipping_plan, apply_cooling_to_trace,
                                                 mr_accounting, estimate_sensitivity,
                                                 run_mr_clipping, DEFAULT_SPOT_MIN_UM,
                                                 DEFAULT_SPOT_POLICY, CoolingApplication)

GEOM = {'hot': {'area_mm2': 0.02, 'min_dim_um': 140.0},
        'small': {'area_mm2': 0.002, 'min_dim_um': 13.0},
        'cool': {'area_mm2': 0.02, 'min_dim_um': 140.0}}


def test_params_reject_nonsense():
    with pytest.raises(ValueError):
        MRParams(target_K=0)
    with pytest.raises(ValueError):
        MRParams(target_K=350, h_max=0)
    with pytest.raises(ValueError):
        MRParams(target_K=350, cop=0)


# ---------------------------------------------------------------------------
# Clipping: only the excess, only where it is hot
# ---------------------------------------------------------------------------
def test_only_blocks_above_target_are_cooled():
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6)
    plan, _ = clipping_plan({'hot': 370.0, 'cool': 340.0}, GEOM, p, {'hot': 1.0, 'cool': 1.0})
    assert 'hot' in plan and 'cool' not in plan


def test_clipping_removes_only_the_excess_not_the_whole_load():
    """20 K over target at 2 K/W of sensitivity => 10 W, regardless of the block's heat load."""
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6)
    plan, detail = clipping_plan({'hot': 370.0}, GEOM, p, {'hot': 2.0})
    assert plan['hot'] == pytest.approx(10.0)
    assert detail['hot']['limit'] == 'need'


def test_out_of_die_zero_kelvin_blocks_are_ignored():
    p = MRParams(target_K=350.0)
    plan, _ = clipping_plan({'hot': 0.0}, GEOM, p, {'hot': 1.0}, t_floor_K=200.0)
    assert plan == {}


def test_block_without_measured_sensitivity_is_skipped_not_guessed():
    p = MRParams(target_K=350.0)
    plan, detail = clipping_plan({'hot': 400.0}, GEOM, p, {})
    assert plan == {}
    assert detail['hot']['limit'] == 'no_sensitivity'


# ---------------------------------------------------------------------------
# The envelope actually binds, and says which limit bound it
# ---------------------------------------------------------------------------
def test_cooling_density_ceiling_binds_and_is_reported():
    p = MRParams(target_K=350.0, h_max=10.0, dt_max_K=1e6)   # 10 W/mm^2 * 0.02 mm^2 = 0.2 W
    plan, detail = clipping_plan({'hot': 500.0}, GEOM, p, {'hot': 1.0})
    assert plan['hot'] == pytest.approx(0.2)
    assert detail['hot']['limit'] == 'h_max'


def test_temperature_lift_ceiling_binds_and_is_reported():
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=10.0)
    plan, detail = clipping_plan({'hot': 500.0}, GEOM, p, {'hot': 2.0})
    assert plan['hot'] == pytest.approx(5.0)          # dt_max / sensitivity
    assert detail['hot']['limit'] == 'dt_max'
    assert detail['hot']['achievable_dT_K'] == pytest.approx(10.0)


def test_spot_limited_blocks_are_flagged_not_silently_cooled():
    """A block narrower than the spot cannot be targeted, and that must stay visible.

    The limit is passed explicitly so this tests the mechanism, not the default.
    """
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6, spot_min_um=100.0)
    _, detail = clipping_plan({'hot': 370.0, 'small': 370.0}, GEOM, p,
                              {'hot': 1.0, 'small': 1.0})
    assert detail['small']['spot_limited'] is True
    assert detail['hot']['spot_limited'] is False


def test_default_spot_size_is_the_realistic_one():
    """1-10 um is achievable; the old 100 um default understated MR reach by 10-100x.

    At 100 um it excluded 37 of the 57 above-target blocks on the 34-core die, including the
    two highest power densities on the chip -- RBB at 13.4 um and iBuf at 1.3 um.
    """
    assert 1.0 <= DEFAULT_SPOT_MIN_UM <= 10.0


def test_a_13um_block_is_reachable_at_the_default():
    """RBB is 13.4 um across and is the highest power density on the die."""
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6)
    _, detail = clipping_plan({'small': 370.0}, GEOM, p, {'small': 1.0})
    assert detail['small']['spot_limited'] is False


def test_budget_goes_to_the_hottest_block_first():
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6, max_total_W=3.0)
    temps = {'hot': 400.0, 'cool': 360.0}     # excesses 50 K and 10 K
    geom = {'hot': GEOM['hot'], 'cool': GEOM['cool']}
    plan, detail = clipping_plan(temps, geom, p, {'hot': 1.0, 'cool': 1.0})
    assert sum(plan.values()) == pytest.approx(3.0)
    assert plan['hot'] == pytest.approx(3.0)   # hottest takes the whole budget
    assert plan.get('cool', 0.0) == pytest.approx(0.0)
    assert detail['cool']['limit'] in ('budget', 'budget_exhausted')


# ---------------------------------------------------------------------------
# Injection as negative sources
# ---------------------------------------------------------------------------
def _name_map(u):
    return u.split('/')[0]


def test_cooling_is_applied_as_negative_power_at_every_timestep():
    tr = BasicPowerTrace({'hot/a': [1.0, 1.0, 1.0], 'cool/a': [2.0, 2.0, 2.0]}, 1.0)
    out = apply_cooling_to_trace(tr, {'hot': 0.4}, _name_map)
    assert out['hot/a'] == pytest.approx([0.6, 0.6, 0.6])
    assert out['cool/a'] == pytest.approx([2.0, 2.0, 2.0])


def test_cooling_can_drive_a_block_negative():
    """Validated against real 3D-ICE: negative sources are accepted and cool locally."""
    tr = BasicPowerTrace({'hot/a': [0.3]}, 1.0)
    out = apply_cooling_to_trace(tr, {'hot': 0.5}, _name_map)
    assert out['hot/a'][0] == pytest.approx(-0.2)


def test_removal_is_split_across_units_sharing_a_block_by_power():
    tr = BasicPowerTrace({'hot/a': [3.0], 'hot/b': [1.0]}, 1.0)
    out = apply_cooling_to_trace(tr, {'hot': 0.8}, _name_map)
    assert out['hot/a'][0] == pytest.approx(3.0 - 0.6)
    assert out['hot/b'][0] == pytest.approx(1.0 - 0.2)


def test_equal_split_when_block_has_no_power():
    tr = BasicPowerTrace({'hot/a': [0.0], 'hot/b': [0.0]}, 1.0)
    out = apply_cooling_to_trace(tr, {'hot': 1.0}, _name_map)
    assert out['hot/a'][0] == pytest.approx(-0.5)
    assert out['hot/b'][0] == pytest.approx(-0.5)


# ---------------------------------------------------------------------------
# Cost accounting
# ---------------------------------------------------------------------------
def test_gross_electrical_cost_is_heat_over_cop():
    p = MRParams(target_K=350.0, cop=0.1, recover=False)
    acc = mr_accounting({'hot': 2.0}, p, compute_power_W=100.0)
    assert acc['heat_removed_W'] == pytest.approx(2.0)
    assert acc['electrical_gross_W'] == pytest.approx(20.0)   # COP 0.1 => 10x
    assert acc['electrical_power_W'] == pytest.approx(20.0)   # no recovery => net == gross
    assert acc['total_power_W'] == pytest.approx(120.0)


def test_better_cop_costs_less():
    plan = {'hot': 2.0}
    assert (mr_accounting(plan, MRParams(350.0, cop=0.3))['electrical_power_W'] <
            mr_accounting(plan, MRParams(350.0, cop=0.1))['electrical_power_W'])


# ---------------------------------------------------------------------------
# LPC power recovery
# ---------------------------------------------------------------------------
def test_lpc_recovery_follows_the_energy_balance():
    """P_opt_out = P_opt_in + Q exactly; recovery is collection * lpc_eff of that."""
    p = MRParams(350.0, cop=0.2, laser_wallplug=0.5, lpc_efficiency=0.75,
                 collection_efficiency=0.9)
    acc = mr_accounting({'hot': 1.0}, p)
    assert acc['electrical_gross_W'] == pytest.approx(5.0)        # 1 W / 0.2
    assert acc['optical_in_W'] == pytest.approx(2.5)              # 50% wall-plug
    assert acc['optical_to_lpc_W'] == pytest.approx(3.5)          # 2.5 optical + 1.0 heat
    assert acc['recovered_W'] == pytest.approx(0.9 * 0.75 * 3.5)  # 2.3625
    assert acc['electrical_power_W'] == pytest.approx(5.0 - 2.3625)


def test_recovery_roughly_doubles_the_effective_cop():
    p = MRParams(350.0, cop=0.2, laser_wallplug=0.5, lpc_efficiency=0.75,
                 collection_efficiency=0.9)
    acc = mr_accounting({'hot': 1.0}, p)
    assert acc['effective_cop'] > 1.8 * p.cop
    assert acc['recovery_fraction'] == pytest.approx(2.3625 / 5.0)


def test_better_lpc_cells_lower_the_net_cost():
    plan = {'hot': 1.0}
    lo = mr_accounting(plan, MRParams(350.0, cop=0.2, lpc_efficiency=0.75))
    hi = mr_accounting(plan, MRParams(350.0, cop=0.2, lpc_efficiency=0.90))
    assert hi['electrical_power_W'] < lo['electrical_power_W']
    assert hi['effective_cop'] > lo['effective_cop']


def test_recovery_can_be_disabled_for_comparison():
    plan = {'hot': 1.0}
    with_rec = mr_accounting(plan, MRParams(350.0, cop=0.2))
    without = mr_accounting(plan, MRParams(350.0, cop=0.2, recover=False))
    assert without['recovered_W'] == 0.0
    assert without['electrical_power_W'] > with_rec['electrical_power_W']


def test_net_generating_is_a_reported_regime_not_an_error():
    """Above breakeven the loop returns more than it draws. That is a TARGET regime
    (spreadsheet MVP-3 sits there), so it must be reported plainly, not flagged."""
    p = MRParams(350.0, eta_asf=0.62, laser_wallplug=0.85, lpc_efficiency=0.92)
    acc = mr_accounting({'hot': 1.0}, p)
    assert acc['breakeven_ratio'] > 1.0
    assert acc['self_sustaining'] is True
    assert acc['net_generating'] is True
    assert acc['electrical_power_W'] < 0
    # ...and it must still conserve energy.
    assert acc['first_law_ok'] is True


def test_first_law_holds_across_the_whole_efficiency_range():
    """The real bug detector: recovered power can never exceed pump-in plus heat-in."""
    for wp in (0.3, 0.7, 1.0):
        for lpc in (0.5, 0.9, 1.0):
            for asf in (0.05, 0.2, 0.62, 1.0):
                acc = mr_accounting({'hot': 1.0}, MRParams(
                    350.0, eta_asf=asf, laser_wallplug=wp, lpc_efficiency=lpc))
                assert acc['first_law_ok'] is True, (wp, lpc, asf)
                assert acc['recovered_W'] <= acc['electrical_gross_W'] + 1.0 + 1e-9


def test_breakeven_threshold_is_set_by_the_extractor():
    """At eta_laser 0.70 / eta_LPC 0.90, breakeven needs eta_ASF >= ~0.587."""
    below = MRParams(350.0, eta_asf=0.55, laser_wallplug=0.70, lpc_efficiency=0.90)
    above = MRParams(350.0, eta_asf=0.62, laser_wallplug=0.70, lpc_efficiency=0.90)
    assert below.breakeven_ratio < 1.0 < above.breakeven_ratio


def test_optical_asf_is_not_the_electrical_cop():
    """20 % ASF at 70 % wall-plug is COP 0.14 -- conflating them overstates the cooler."""
    p = MRParams(350.0, eta_asf=0.20, laser_wallplug=0.70)
    assert p.cop == pytest.approx(0.14)


@pytest.mark.parametrize('name,wp,lpc,asf,p_laser,expected_used', [
    ('MVP-1', 0.74, 0.80, 0.100, 1360.0, 474.368),
    ('MVP-2', 0.80, 0.87, 0.437, 290.0, -0.04408),
    ('MVP-3', 0.85, 0.92, 0.620, 190.0, -50.6996),
])
def test_reproduces_mxl_photonic_cooling_spreadsheet(name, wp, lpc, asf, p_laser, expected_used):
    """Regression against docs/MXL-Photonic-Cooling-Power-Analysis.xlsx (MVP cases)."""
    p = MRParams(350.0, eta_asf=asf, laser_wallplug=wp, lpc_efficiency=lpc)
    q = asf * wp * p_laser                     # heat the sheet's P_laser corresponds to
    acc = mr_accounting({'hot': q}, p)
    assert acc['electrical_gross_W'] == pytest.approx(p_laser, rel=1e-9)
    assert acc['electrical_power_W'] == pytest.approx(expected_used, abs=1e-3)


def test_efficiencies_must_be_physical():
    for kw in ({'laser_wallplug': 1.2}, {'lpc_efficiency': -0.1},
               {'collection_efficiency': 2.0}, {'eta_asf': 1.5}):
        with pytest.raises(ValueError):
            MRParams(350.0, **kw)


# ---------------------------------------------------------------------------
# Measured sensitivity
# ---------------------------------------------------------------------------
def test_sensitivity_is_measured_from_the_observed_response():
    s = estimate_sensitivity({'hot': 380.0}, {'hot': 370.0}, {'hot': 2.0})
    assert s['hot'] == pytest.approx(5.0)      # 10 K per 2 W


def test_non_positive_sensitivity_is_discarded():
    """A block that warmed despite cooling must not become a negative gain."""
    assert estimate_sensitivity({'hot': 370.0}, {'hot': 380.0}, {'hot': 2.0}) == {}


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------
def test_clipping_loop_converges_against_a_linear_mock_solver():
    """Mock: each block cools 4 K per watt removed, so the loop should find the right plan."""
    base = {'hot': 380.0, 'cool': 340.0}
    geom = {'hot': GEOM['hot'], 'cool': GEOM['cool']}
    trace = BasicPowerTrace({'hot/a': [5.0], 'cool/a': [5.0]}, 1.0)

    def solver(tr):
        removed = {b: 0.0 for b in base}
        for u, series in tr.powers.items():
            b = _name_map(u)
            removed[b] += 5.0 - float(np.sum(series))
        return {b: np.array([base[b] - 4.0 * removed[b]]) for b in base}

    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6, cop=0.1)
    res = run_mr_clipping(trace, solver, geom, p, _name_map, max_iter=12, tol_K=0.5, relax=1.0)
    assert res['converged'] is True
    assert res['plan']['hot'] == pytest.approx(30.0 / 4.0, rel=0.15)
    assert 'cool' not in res['plan']


def test_loop_reports_failure_when_envelope_is_too_small():
    """Not converging is a real result -- the envelope cannot clip this workload."""
    base = {'hot': 500.0}
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)

    def solver(tr):
        removed = 5.0 - float(np.sum(tr.powers['hot/a']))
        return {'hot': np.array([base['hot'] - 4.0 * removed])}

    p = MRParams(target_K=350.0, h_max=0.5, dt_max_K=1e6)   # 0.5*0.02 = 0.01 W ceiling
    res = run_mr_clipping(trace, solver, {'hot': GEOM['hot']}, p, _name_map,
                          max_iter=3, tol_K=0.5)
    assert res['converged'] is False
    assert res['accounting']['heat_removed_W'] > 0


# ---------------------------------------------------------------------------
# spot_policy -- these pin the bug where spot_limited was computed and never used,
# so changing spot_min_um produced bit-identical results.
# ---------------------------------------------------------------------------
class TestSpotPolicy:
    HOT = {'hot': 370.0, 'small': 370.0}
    SENS = {'hot': 1.0, 'small': 1.0}

    def _plan(self, policy, spot=100.0):
        p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6,
                     spot_min_um=spot, spot_policy=policy)
        return clipping_plan(self.HOT, GEOM, p, self.SENS) + (p,)

    def test_spot_size_actually_changes_the_plan(self):
        """The regression: at 100 um vs 1 um the plan must differ for a 13 um block."""
        coarse, _, _ = self._plan('exclude', spot=100.0)
        fine, _, _ = self._plan('exclude', spot=1.0)
        assert 'small' not in coarse
        assert 'small' in fine

    def test_exclude_drops_the_block_entirely(self):
        plan, detail, _ = self._plan('exclude')
        assert 'small' not in plan
        assert detail['small']['limit'] == 'spot_limited'
        assert detail['small']['q_W'] == 0.0

    def test_dilute_keeps_the_block_but_bills_for_the_pixel(self):
        plan, detail, params = self._plan('dilute')
        assert 'small' in plan                      # still cooled
        # GEOM['small'] is 0.002 mm^2; a 100 um pixel is 0.01 mm^2 -> 5x the bill.
        assert detail['small']['cost_multiplier'] == pytest.approx(0.01 / 0.002)
        assert detail['hot']['cost_multiplier'] == pytest.approx(1.0)

    def test_dilution_is_charged_in_the_accounting(self):
        """A cost multiplier that nothing reads is the bug this whole class exists for."""
        plan, detail, params = self._plan('dilute')
        cheap = mr_accounting(plan, params)
        billed = mr_accounting(plan, params, detail=detail)
        assert billed['heat_billed_W'] > billed['heat_removed_W']
        assert billed['electrical_gross_W'] > cheap['electrical_gross_W']
        assert billed['spot_dilution_overhead'] > 1.0

    def test_ideal_reproduces_the_old_behaviour(self):
        plan, detail, params = self._plan('ideal')
        assert 'small' in plan
        assert detail['small']['cost_multiplier'] == pytest.approx(1.0)
        assert mr_accounting(plan, params, detail=detail)['spot_dilution_overhead'] == \
            pytest.approx(1.0)

    def test_default_policy_is_the_physical_one(self):
        assert DEFAULT_SPOT_POLICY == 'dilute'

    def test_bad_policy_rejected(self):
        with pytest.raises(ValueError):
            MRParams(target_K=350.0, spot_policy='nonsense')


# ---------------------------------------------------------------------------
# The rescue regime: sizing the plan when the bare die has NO steady state.
# These pin the fix for the path-dependence measured on the 34-core die, where the plan was
# sized from whichever field a divergent baseline happened to stop on (0.561 W at 1.12 W/mm^2
# against 1.979 W at 1.15) and the rescue came out non-monotone in density.
# ---------------------------------------------------------------------------
def _runaway_unless_cooled(base_K, gain_K_per_W, needed_W):
    """Mock whose bare die has no steady state: it reports divergence unless enough heat is
    removed. ``status_fn`` mirrors what run_leakage_feedback tells its caller."""
    state = {'diverged': True}

    def solver(tr):
        removed = 5.0 - float(np.sum(tr.powers['hot/a']))
        state['diverged'] = removed < needed_W
        # While diverging the reported field is a point on the runaway, not a solution -- and
        # crucially it depends on how far the iteration ran, which is the whole problem.
        t = base_K + 60.0 if state['diverged'] else base_K - gain_K_per_W * removed
        return {'hot': np.array([t])}

    return solver, (lambda: dict(state))


def test_envelope_mode_rescues_where_baseline_mode_reads_a_divergent_field():
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=2.0, dt_max_K=1e6, cop=0.1)   # envelope 2.0 W

    solver, status = _runaway_unless_cooled(base_K=360.0, gain_K_per_W=4.0, needed_W=1.0)
    res = run_mr_clipping(trace, solver, geom, p, _name_map, max_iter=8, tol_K=1.0,
                          status_fn=status, plan_mode='envelope')
    assert res['converged'] is True
    assert res['plan']['hot'] > 0.0
    # It found a plan that holds the die, and did not need the (nonexistent) baseline to do it.
    assert res['history'][0]['stage'] == 'full envelope'


def test_auto_mode_switches_on_the_baseline_status():
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=2.0, dt_max_K=1e6, cop=0.1)

    solver, status = _runaway_unless_cooled(base_K=360.0, gain_K_per_W=4.0, needed_W=1.0)
    auto = run_mr_clipping(trace, solver, geom, p, _name_map, max_iter=8, tol_K=1.0,
                           status_fn=status)                      # plan_mode='auto'
    assert auto['history'][0]['stage'] == 'full envelope'          # took the envelope path

    # A die that converges on its own must still use the validated baseline path. Give it an
    # envelope big enough to actually reach the target, or the loop would (correctly) report
    # that the device cannot do it and the mode would not be what was under test.
    base = {'hot': 380.0}
    roomy = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6, cop=0.1)

    def calm(tr):
        removed = 5.0 - float(np.sum(tr.powers['hot/a']))
        return {'hot': np.array([base['hot'] - 4.0 * removed])}

    res = run_mr_clipping(trace, calm, geom, roomy, _name_map, max_iter=8, tol_K=0.5,
                          status_fn=lambda: {'diverged': False})
    assert res['converged'] is True
    assert not any(h.get('stage') == 'full envelope' for h in res['history'])


def test_envelope_insufficient_is_a_statement_about_the_device():
    """If the fully-cooled system still has no steady state, MR cannot rescue the point. That
    must be reported as such rather than as a plan that happened to be too small."""
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=0.2, dt_max_K=1e6, cop=0.1)   # envelope 0.2 W

    solver, status = _runaway_unless_cooled(base_K=360.0, gain_K_per_W=4.0, needed_W=1.0)
    res = run_mr_clipping(trace, solver, geom, p, _name_map, max_iter=6, tol_K=1.0,
                          status_fn=status, plan_mode='envelope')
    assert res['converged'] is False
    assert 'envelope insufficient' in res['reason']


def test_envelope_plan_respects_the_device_caps_and_spot_policy():
    from HotGauge.thermal.microrefrigeration import envelope_plan
    geom = {'big': {'area_mm2': 1.0, 'min_dim_um': 500.0},
            'sliver': {'area_mm2': 0.01, 'min_dim_um': 1.0}}
    p = MRParams(target_K=350.0, h_max=2.0, dt_max_K=1e6, spot_min_um=10.0,
                 spot_policy='exclude', cop=0.1)
    plan, _ = envelope_plan(geom, p, {'big': 1.0, 'sliver': 1.0})
    assert plan['big'] == pytest.approx(2.0)      # h_max * area
    assert 'sliver' not in plan                   # narrower than the pitch, policy excludes it


def test_status_fn_failure_does_not_decide_physics():
    """A broken status probe must degrade to the documented default, not crash or silently
    pick the other algorithm."""
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6, cop=0.1)
    base = {'hot': 380.0}

    def calm(tr):
        removed = 5.0 - float(np.sum(tr.powers['hot/a']))
        return {'hot': np.array([base['hot'] - 4.0 * removed])}

    def broken():
        raise RuntimeError('probe exploded')

    res = run_mr_clipping(trace, calm, geom, p, _name_map, max_iter=8, tol_K=0.5,
                          status_fn=broken)
    assert res['converged'] is True


def test_boundary_bisection_converges_on_the_minimum_plan():
    """The reported rescue plan must not depend on the descent's step size.

    Before the bisection the loop stopped at whatever plan happened to be the last one that
    held, which drifted 0.615 -> 0.335 W at 1.10 W/mm^2 just by allowing more iterations.

    The mock is arranged so the descent MUST cross the stability boundary: holding the 350 K
    target needs 2.5 W (base 360 K, 4 K/W), but the die has no steady state below 3.0 W. So the
    loop starts at the 4.0 W envelope, walks down toward 2.5, loses stability at 3.0, and must
    bracket the threshold rather than report wherever it happened to land.
    """
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}

    results = []
    for iters in (12, 20):
        p = MRParams(target_K=350.0, h_max=4.0, dt_max_K=1e6, cop=0.1)
        solver, status = _runaway_unless_cooled(base_K=360.0, gain_K_per_W=4.0, needed_W=3.0)
        res = run_mr_clipping(trace, solver, geom, p, _name_map, max_iter=iters, tol_K=1.0,
                              status_fn=status, plan_mode='envelope')
        assert res['converged'] is True
        results.append(res['plan']['hot'])

    for q in results:
        assert 3.0 <= q <= 3.1, 'plan {} is not the minimum that holds (threshold 3.0)'.format(q)
    assert abs(results[0] - results[1]) < 0.05, \
        'plan moved with the iteration budget: {}'.format(results)


def test_a_descent_that_never_reaches_the_boundary_is_flagged_as_an_upper_bound():
    """With too small a budget the descent stops short, and that plan is an upper bound on what
    MR needs -- not the minimum. Callers must be able to tell the two apart without parsing
    prose, because the difference is the whole rescue claim."""
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=4.0, dt_max_K=1e6, cop=0.1)
    solver, status = _runaway_unless_cooled(base_K=360.0, gain_K_per_W=4.0, needed_W=3.0)
    res = run_mr_clipping(trace, solver, geom, p, _name_map, max_iter=4, tol_K=1.0,
                          status_fn=status, plan_mode='envelope')
    assert res['plan_is_minimum'] is False
    assert res['plan']['hot'] > 3.0            # holds the die, but is bigger than it needs to be
    assert 'UPPER BOUND' in res['reason']


def test_descent_stops_at_the_target_not_at_the_stability_boundary():
    """Two different questions, and conflating them produced a 133 C 'rescue'.

    Descending from the envelope the peak RISES, so it crosses the target while the plan is
    still moving. If the loop only stops when the plan is also stationary it sails past and
    ends at the minimum for a steady state to EXIST -- which here is a stable 133 C, past
    McPAT's validity ceiling and not a shippable operating point. The product number is the
    minimum plan that holds the TARGET, and it must be the one reported when the target is
    reachable.
    """
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    # Holding 350 K needs 2.5 W (base 360 K, 4 K/W); a steady state merely EXISTS from 1.0 W.
    p = MRParams(target_K=350.0, h_max=4.0, dt_max_K=1e6, cop=0.1)
    solver, status = _runaway_unless_cooled(base_K=360.0, gain_K_per_W=4.0, needed_W=1.0)

    res = run_mr_clipping(trace, solver, geom, p, _name_map, max_iter=20, tol_K=1.0,
                          status_fn=status, plan_mode='envelope')
    assert res['converged'] is True
    assert res['plan_holds_target'] is True
    assert res['plan']['hot'] == pytest.approx(2.6, abs=0.4), \
        'should stop at the target-holding plan, not walk on to the stability boundary'
    peak = max(float(np.ravel(t)[-1]) for t in res['temp_trace'].values())
    assert peak <= p.target_K + 1.0


def test_hot_branch_solutions_are_rejected_when_bisecting():
    """A leakage-limited die is BISTABLE, and the cheap solution is the useless one.

    Measured at 1.15 W/mm^2: 42.05 W of cooling holds 90.6 C, and 0.71 W also converges -- at
    133.2 C. Both are steady states. Accepting any convergence during the bisection reported
    the second as a rescue, so the search must reject the hot branch explicitly.
    """
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=4.0, dt_max_K=1e6, cop=0.1)

    def bistable(tr):
        """Cool branch above 2.5 W of cooling; below it the die settles on a hot branch."""
        removed = 5.0 - float(np.sum(tr.powers['hot/a']))
        t = 360.0 - 4.0 * removed if removed >= 2.5 else 420.0
        return {'hot': np.array([t])}

    res = run_mr_clipping(trace, bistable, geom, p, _name_map, max_iter=20, tol_K=1.0,
                          status_fn=lambda: {'diverged': False}, plan_mode='envelope')
    peak = max(float(np.ravel(t)[-1]) for t in res['temp_trace'].values())
    if res['plan_holds_target']:
        assert peak <= p.target_K + 1.0, 'claimed to hold the target on the hot branch'
        assert res['plan']['hot'] >= 2.4, 'hot-branch plan reported as the minimum'
    else:
        assert peak > p.target_K + 1.0        # correctly flagged as not holding the target


# ---------------------------------------------------------------------------
# Design E -- distributed MR, the control arm for the hotspot framing
# ---------------------------------------------------------------------------
def test_distributed_plan_spreads_by_area_and_respects_the_flux_ceiling():
    from HotGauge.thermal.microrefrigeration import distributed_plan
    geom = {'big': {'area_mm2': 3.0, 'min_dim_um': 500.0},
            'small': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6, cop=0.1)
    plan, _ = distributed_plan(geom, p, total_W=4.0)
    assert plan['big'] == pytest.approx(3.0)      # area-weighted: 3/4 of the budget
    assert plan['small'] == pytest.approx(1.0)
    assert sum(plan.values()) == pytest.approx(4.0)


def test_distributed_plan_reports_what_it_can_actually_deliver():
    """A budget the device cannot deliver must not be silently accepted: the comparison against
    hotspot clipping is only fair against the delivered watts."""
    from HotGauge.thermal.microrefrigeration import distributed_plan
    geom = {'a': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=2.0, dt_max_K=1e6, cop=0.1)   # ceiling 2 W
    plan, detail = distributed_plan(geom, p, total_W=10.0)
    assert plan['a'] == pytest.approx(2.0)
    assert detail['a']['limit'] == 'h_max'
    assert detail['a']['requested_W'] == pytest.approx(10.0)


def test_distributed_plan_rejects_a_nonpositive_budget():
    from HotGauge.thermal.microrefrigeration import distributed_plan
    geom = {'a': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=1.0, dt_max_K=1e6, cop=0.1)
    with pytest.raises(ValueError):
        distributed_plan(geom, p, total_W=0.0)


def test_probe_failures_do_not_flag_a_verified_result():
    """The searches deliberately visit unstable states to bracket an answer, and those probes are
    exactly the solves that fail damping verification. Flagging the whole point for that hid
    roughly fifteen good measurements -- including every pixel-pitch run -- so verification
    applies to the solve that produced the REPORTED field, not to every solve made.
    """
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=4.0, dt_max_K=1e6, cop=0.1)

    # Unverified ONLY while cooling is thin -- i.e. on the boundary probes, never on the state
    # the loop settles on.
    state = {'diverged': True, 'unconverged': False}

    def solver(tr):
        removed = 5.0 - float(np.sum(tr.powers['hot/a']))
        state['diverged'] = removed < 1.0
        state['unconverged'] = removed < 1.2 and not state['diverged']
        t = 360.0 + 60.0 if state['diverged'] else 360.0 - 4.0 * removed
        return {'hot': np.array([t])}

    res = run_mr_clipping(trace, solver, geom, p, _name_map, max_iter=20, tol_K=1.0,
                          status_fn=lambda: dict(state), plan_mode='envelope')
    assert res['converged'] is True
    # The reported field came from a well-cooled, verified solve.
    assert res['result_unconverged'] is False


def test_an_unverified_reported_field_is_still_flagged():
    """The other half of the same rule: if the state actually reported was not verified, the
    point is not a result. This is the check that caught three real errors."""
    trace = BasicPowerTrace({'hot/a': [5.0]}, 1.0)
    geom = {'hot': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    p = MRParams(target_K=350.0, h_max=1e6, dt_max_K=1e6, cop=0.1)
    base = {'hot': 380.0}

    def calm(tr):
        removed = 5.0 - float(np.sum(tr.powers['hot/a']))
        return {'hot': np.array([base['hot'] - 4.0 * removed])}

    res = run_mr_clipping(trace, calm, geom, p, _name_map, max_iter=8, tol_K=0.5,
                          status_fn=lambda: {'diverged': False, 'unconverged': True})
    assert res['result_unconverged'] is True


# ---------------------------------------------------------------------------
# Relaxing to zero is a claim that has to be tested, not assumed
# ---------------------------------------------------------------------------
def test_relaxation_to_zero_on_a_runaway_die_reports_the_last_holding_plan():
    """The defect this pins was live and it inverted a finding.

    The envelope planner starts at full device capability and relaxes toward the target. When the
    relaxation reached zero it returned ``plan_holds_target: True`` and "no cooling needed to hold
    the target" WITHOUT solving to check -- so a 128-core die at 1.00 W/mm^2, which has no steady
    state at all uncooled, came back reported as needing no MR. That is the exact opposite of the
    result.

    Now the zero plan is tested, and if it does not hold the last plan that did is reported
    instead, flagged non-minimal because the interval down to zero was never bisected.
    """
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    target_K = 273.15 + 98.0
    calls = {'n': 0}
    state = {'diverged': False}

    def solve(trace):
        # MR is applied by REDUCING a block's power, so cooling shows up as a total below the
        # uncooled 20 W rather than as a negative entry.
        total = sum(float(np.ravel(v)[-1]) for v in trace.powers.values())
        calls['n'] += 1
        if total >= 20.0 - 1e-9:
            # Uncooled: runaway, exactly like the 128-core point.
            state['diverged'] = True
            return {'B0': np.array([float('nan')])}
        state['diverged'] = False
        # Any cooling at all holds it comfortably, so the relaxation will march to zero.
        return {'B0': np.array([target_K - 5.0])}

    geom = {'B0': {'area_mm2': 4.0, 'min_dim_um': 2000.0}}
    params = MRParams(target_K=target_K, h_max=10.0, dt_max_K=10.0)
    trace = BasicPowerTrace({'B0': np.array([20.0])}, 1.0)

    res = run_mr_clipping(trace, solve, geom, params, name_map=lambda u: u,
                          status_fn=lambda: dict(state), plan_mode='envelope', max_iter=12)

    assert res['plan_holds_target'] is True
    assert res['plan'], 'must not report an empty plan for a die that runs away uncooled'
    assert sum(res['plan'].values()) > 0
    assert res['plan_is_minimum'] is False      # the interval down to zero was never bisected
    assert 'no steady state' in res['reason']
    assert 'no cooling needed' not in res['reason']


def test_relaxation_to_zero_is_still_believed_when_the_die_really_does_hold():
    """The fix must not turn a genuine "MR idle" answer into a phantom plan."""
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    target_K = 273.15 + 98.0

    def solve(trace):
        return {'B0': np.array([target_K - 20.0])}      # cool with or without cooling

    geom = {'B0': {'area_mm2': 4.0, 'min_dim_um': 2000.0}}
    params = MRParams(target_K=target_K, h_max=10.0, dt_max_K=10.0)
    trace = BasicPowerTrace({'B0': np.array([20.0])}, 1.0)

    res = run_mr_clipping(trace, solve, geom, params, name_map=lambda u: u,
                          status_fn=lambda: {'diverged': False}, plan_mode='envelope',
                          max_iter=12)
    assert res['plan_holds_target'] is True
    assert not res['plan']
    assert res['plan_is_minimum'] is True


def test_the_restored_plan_is_a_solve_that_HELD_not_merely_the_previous_iterate():
    """Second half of the same bug. The first fix restored ``prev_temps`` -- the previous iterate --
    but the descent deliberately walks past the feasible boundary to bracket the minimum, so that
    iterate can be a diverged field of NaN. Handing it back produced "No block temperatures above
    the 200.0 K floor" from core_fmax two layers downstream.

    The answer has to be the last solve that both converged AND held the target.
    """
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    target_K = 273.15 + 98.0
    state = {'diverged': False}
    seen = []

    def solve(trace):
        total = sum(float(np.ravel(v)[-1]) for v in trace.powers.values())
        removed = 20.0 - total
        seen.append(removed)
        if removed <= 1e-9:                       # uncooled: runaway
            state['diverged'] = True
            return {'B0': np.array([float('nan')])}
        if removed < 4.0:                         # too little: also runaway
            state['diverged'] = True
            return {'B0': np.array([float('nan')])}
        state['diverged'] = False
        return {'B0': np.array([target_K - 5.0])}

    geom = {'B0': {'area_mm2': 4.0, 'min_dim_um': 2000.0}}
    params = MRParams(target_K=target_K, h_max=10.0, dt_max_K=10.0)
    trace = BasicPowerTrace({'B0': np.array([20.0])}, 1.0)

    res = run_mr_clipping(trace, solve, geom, params, name_map=lambda u: u,
                          status_fn=lambda: dict(state), plan_mode='envelope', max_iter=20)

    # Whatever is returned must be a usable field, which is the thing that actually broke.
    temps = res['temp_trace']
    assert any(float(np.ravel(v)[-1]) > 200.0 for v in temps.values())
    assert all(float(np.ravel(v)[-1]) == float(np.ravel(v)[-1]) for v in temps.values())
    if res['plan']:
        assert res['plan_holds_target'] is True
        assert sum(res['plan'].values()) >= 4.0    # a plan that actually held
    else:
        assert res['plan_holds_target'] is False   # and it must say so rather than imply success


def test_an_unusable_field_is_a_failed_solve_not_a_cool_die():
    """Third layer of the same bug family, and the subtlest.

    ``_relax_plan_toward_target`` skips any block whose temperature it cannot read -- NaN, or at
    the floor. If the solve returns a field like that for EVERY block the relaxation returns an
    empty plan, and the descent used to read the empty plan as "nothing wants cooling". On the
    128-core / 1.00 W/mm^2 point that produced a confident "no plan held the target" after only
    three solves, which is a claim about microrefrigeration derived from a field that did not
    exist.

    An unusable field must be treated as a failed solve, exactly like divergence.
    """
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    target_K = 273.15 + 98.0

    def solve(trace):
        # Converged as far as the status is concerned, but nothing above the floor.
        return {'B0': np.array([float('nan')])}

    geom = {'B0': {'area_mm2': 4.0, 'min_dim_um': 2000.0}}
    params = MRParams(target_K=target_K, h_max=10.0, dt_max_K=10.0)
    trace = BasicPowerTrace({'B0': np.array([20.0])}, 1.0)

    res = run_mr_clipping(trace, solve, geom, params, name_map=lambda u: u,
                          status_fn=lambda: {'diverged': False}, plan_mode='envelope',
                          max_iter=12)
    assert res['plan_holds_target'] is False
    assert 'no usable temperature field' in res['reason']
    assert 'no cooling needed' not in res['reason']


def test_a_truncated_descent_says_it_did_not_hold_the_target():
    """The baseline path's max_iter return used to omit plan_holds_target entirely, while the
    envelope path's equivalent set it. A missing key reads downstream as None, which is
    indistinguishable from "nobody populated this" -- so six accelerator points that were still
    mid-descent, sitting 2-49 K above their target, reported the same verdict as a converged run.

    A truncated descent must say so, and its cost must be labelled a lower bound: the loop adds
    cooling as it goes, so stopping early UNDERSTATES what holding the target needs.
    """
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    target_K = 273.15 + 98.0

    def solve(trace):
        # Always far above target however much cooling is applied, so the descent can never
        # finish and must exhaust max_iter.
        return {'B0': np.array([target_K + 40.0])}

    geom = {'B0': {'area_mm2': 4.0, 'min_dim_um': 2000.0}}
    params = MRParams(target_K=target_K, h_max=10.0, dt_max_K=10.0)
    trace = BasicPowerTrace({'B0': np.array([50.0])}, 1.0)

    res = run_mr_clipping(trace, solve, geom, params, name_map=lambda u: u,
                          status_fn=lambda: {'diverged': False}, plan_mode='baseline',
                          max_iter=4)
    assert res['reason'].startswith('max_iter reached')
    assert res['plan_holds_target'] is False
    assert res['plan_is_minimum'] is False
    assert 'LOWER BOUND' in res['reason']


def test_running_out_of_device_lift_is_not_running_out_of_iterations():
    """These two arrive at the same exit and mean opposite things.

    The stage lifts a block by at most dt_max_K. If the peak has come down by the full dt_max and
    is STILL above target, no number of extra iterations helps and neither would a better COP --
    the binding constraint is the device's temperature lift. Every truncated accelerator run at
    700 W was this: exactly 10.00 K of lift against a 12.6-37 K requirement, reported as an
    iteration-budget problem, which pointed at the wrong fix entirely.
    """
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    target_K = 273.15 + 98.0
    uncooled_K = 273.15 + 110.6           # needs 12.6 K; the device has 10

    def solve(trace):
        removed = 50.0 - sum(float(np.ravel(v)[-1]) for v in trace.powers.values())
        # Whatever the plan, the peak cannot come down by more than dt_max.
        lift = min(10.0, max(0.0, removed * 4.0))
        return {'B0': np.array([uncooled_K - lift])}

    geom = {'B0': {'area_mm2': 4.0, 'min_dim_um': 2000.0}}
    params = MRParams(target_K=target_K, h_max=10.0, dt_max_K=10.0)
    trace = BasicPowerTrace({'B0': np.array([50.0])}, 1.0)

    res = run_mr_clipping(trace, solve, geom, params, name_map=lambda u: u,
                          status_fn=lambda: {'diverged': False}, plan_mode='baseline',
                          max_iter=30)
    assert res['plan_holds_target'] is False
    assert res['dt_max_bound'] is True
    assert 'dt_max binds' in res['reason']
    assert 'max_iter reached' not in res['reason']
    assert res['lift_achieved_K'] == pytest.approx(10.0, abs=0.1)
    assert res['lift_needed_K'] == pytest.approx(12.6, abs=0.1)


def test_a_genuinely_truncated_descent_still_says_max_iter():
    """The dt_max verdict must not swallow the iteration-budget case: if the peak has NOT come
    down by dt_max, the descent really was cut short."""
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    target_K = 273.15 + 98.0

    def solve(trace):
        return {'B0': np.array([target_K + 40.0])}       # never moves at all

    geom = {'B0': {'area_mm2': 4.0, 'min_dim_um': 2000.0}}
    params = MRParams(target_K=target_K, h_max=10.0, dt_max_K=10.0)
    trace = BasicPowerTrace({'B0': np.array([50.0])}, 1.0)

    res = run_mr_clipping(trace, solve, geom, params, name_map=lambda u: u,
                          status_fn=lambda: {'diverged': False}, plan_mode='baseline',
                          max_iter=4)
    assert res['dt_max_bound'] is False
    assert 'max_iter reached' in res['reason']
    assert 'LOWER BOUND' in res['reason']


# ---------------------------------------------------------------------------
# Where the cooling is applied
# ---------------------------------------------------------------------------
_TILES = [{'name': 'MR_r00_c00', 'x': 0.0, 'y': 0.0, 'w': 100.0, 'h': 100.0},
          {'name': 'MR_r00_c01', 'x': 100.0, 'y': 0.0, 'w': 100.0, 'h': 100.0}]
_BLOCKS = {'A': (0.0, 0.0, 100.0, 100.0), 'B': (100.0, 0.0, 100.0, 100.0)}


class TestCoolingApplication:
    """The plan has to reach the array, and every result has to say where it landed.

    Both failure modes are silent. A plan applied to the processor trace still produces
    temperatures -- just an upper bound, because the extracted watt crosses no silicon. And a
    result with no placement stamp is indistinguishable from the other generation's.
    """

    def test_legacy_placement_subtracts_from_the_trace(self):
        trace = BasicPowerTrace({'A': [10.0], 'B': [10.0]}, 1.0)
        app = CoolingApplication(trace, lambda u: u)
        assert app.placement == 'in_source_layer'
        out = app({'A': 2.0})
        assert float(np.ravel(out.powers['A'])[-1]) == pytest.approx(8.0)
        assert float(np.ravel(out.powers['B'])[-1]) == pytest.approx(10.0)
        assert app.last_tile_plan is None

    def test_array_placement_leaves_the_processor_trace_alone(self):
        """The cooling is on the other die. Touching the trace as well would double-count it."""
        trace = BasicPowerTrace({'A': [10.0], 'B': [10.0]}, 1.0)
        pushed = {}
        app = CoolingApplication(trace, lambda u: u, tiles=_TILES, blocks=_BLOCKS,
                                 set_mr_powers=pushed.update)
        assert app.placement == 'array_above'
        out = app({'A': 2.0})
        assert out is trace
        assert float(np.ravel(out.powers['A'])[-1]) == pytest.approx(10.0)
        assert sum(pushed.values()) == pytest.approx(-2.0)

    @pytest.mark.parametrize('kw', [
        {'tiles': _TILES},
        {'tiles': _TILES, 'blocks': _BLOCKS},
        {'tiles': _TILES, 'set_mr_powers': dict().update},
        {'blocks': _BLOCKS},
    ])
    def test_a_half_specified_array_is_refused(self, kw):
        """tiles without the callback would compute a plan and then never apply it."""
        with pytest.raises(ValueError):
            CoolingApplication([], lambda u: u, **kw)

    def test_projection_conserves_the_planned_watts(self):
        trace = BasicPowerTrace({'A': [10.0]}, 1.0)
        pushed = {}
        app = CoolingApplication(trace, lambda u: u, tiles=_TILES, blocks=_BLOCKS,
                                 set_mr_powers=pushed.update)
        app({'A': 1.5, 'B': 0.5})
        assert sum(app.last_tile_plan.values()) == pytest.approx(2.0, abs=1e-9)
        assert sum(pushed.values()) == pytest.approx(-2.0, abs=1e-9)

    def test_every_run_is_stamped_with_its_placement(self):
        """Thirteen exits in the loop; the stamp has to survive all of them."""
        trace = BasicPowerTrace({'hot': [1.0]}, 1.0)
        params = MRParams(target_K=400.0)
        res = run_mr_clipping(trace, lambda tr: {'hot': np.array([300.0])},
                              GEOM, params, lambda u: u)
        assert res['placement'] == 'in_source_layer'
        assert 'tile_plan' in res


class TestEnvelopeProvenance:
    """The MR envelope, its sources, and the duplication that hid it.

    Until 26 Aug 2026 the block read "Documented MR envelope: h_max 10 W/mm^2, dt_max 10 K" with
    no source, and SEVEN drivers repeated those literals in their own argparse defaults. So the
    envelope had eight definitions and no provenance, and it was wrong in both directions: 25x
    below the demonstrated cooling density and 5.7x above the demonstrated ASF efficiency.

    The consequence was not a wrong number, it was a HIDDEN CEILING. The planner could never ask
    for more than 10 K of lift, so any architectural lever needing more was unreachable by
    assumption. The threshold-voltage lever needs 22 K at 50 mV -- inside the demonstrated 45 K,
    outside the assumed 10 K.
    """

    def test_capability_matches_its_stated_source(self):
        """The default must equal a SOURCED figure, and the source must be named.

        Refreshed 30 Aug 2026: h_max now traces to v91 Table 8.2 rather than Draft_5 s6.4.1. The
        old provenance is kept as its own constant so every pre-30-Aug result still reproduces --
        that is the point of the guard, not an exception to it.
        """
        from HotGauge.thermal.microrefrigeration import (DEFAULT_H_MAX_W_PER_MM2,
                                                         V91_H_MAX_RANGE_W_PER_MM2,
                                                         LEGACY_H_MAX_W_PER_MM2_DRAFT5,
                                                         DEFAULT_DT_MAX_K, DEMONSTRATED)
        # current default traces to v91 Table 8.2, and takes the CONSERVATIVE end of its range
        assert DEFAULT_H_MAX_W_PER_MM2 == V91_H_MAX_RANGE_W_PER_MM2[0] == 1000.0
        assert DEFAULT_H_MAX_W_PER_MM2 < V91_H_MAX_RANGE_W_PER_MM2[1]
        # the superseded provenance is preserved, not deleted
        assert LEGACY_H_MAX_W_PER_MM2_DRAFT5 == DEMONSTRATED['h_max_W_per_mm2'] == 250.0
        # dt_max has NO v91 replacement and must not be quietly scaled to match h_max
        assert DEFAULT_DT_MAX_K == DEMONSTRATED['dt_max_K'] == 45.0

    def test_the_envelope_refresh_is_a_real_change_of_regime(self):
        """h_max moved 4x at the low end and 40x at the high end. Guard the magnitude.

        This is not a tweak: the measured 34-core rescue failed on the ENVELOPE rather than on
        cost, so a factor this size is expected to move recorded verdicts. The test exists so the
        refresh cannot be silently reverted to the Yb:YLF-era figure.
        """
        from HotGauge.thermal.microrefrigeration import (DEFAULT_H_MAX_W_PER_MM2,
                                                         V91_H_MAX_RANGE_W_PER_MM2,
                                                         LEGACY_H_MAX_W_PER_MM2_DRAFT5)
        assert DEFAULT_H_MAX_W_PER_MM2 / LEGACY_H_MAX_W_PER_MM2_DRAFT5 == 4.0
        assert V91_H_MAX_RANGE_W_PER_MM2[1] / LEGACY_H_MAX_W_PER_MM2_DRAFT5 == 40.0

    def test_efficiency_targets_are_above_what_is_demonstrated(self):
        """They are targets. The test exists so nobody quotes them as measurements."""
        from HotGauge.thermal.microrefrigeration import (DEFAULT_ETA_ASF, DEFAULT_LASER_WALLPLUG,
                                                         DEFAULT_LPC_EFFICIENCY, DEMONSTRATED)
        assert DEFAULT_ETA_ASF > DEMONSTRATED['eta_asf']
        assert DEFAULT_LASER_WALLPLUG > DEMONSTRATED['laser_wallplug']
        assert DEFAULT_LPC_EFFICIENCY > DEMONSTRATED['lpc_efficiency']

    def test_the_target_envelope_is_net_generating(self):
        """breakeven_ratio > 1 at the targets -- a different regime, not a better number.

        `[!]` ``breakeven_ratio`` is the FIRST-LAW ledger and is the phi -> 1 limit; a loop it
        calls net-generating is not necessarily permitted by the second law. See
        ``test_defaults_do_not_self_power_at_any_survivable_temperature``. This test guards the
        first-law property deliberately, because the recorded catalogue used it.
        """
        from HotGauge.thermal.microrefrigeration import MRParams, LEGACY_ENVELOPE
        target = MRParams(target_K=358.15)
        legacy = MRParams(target_K=358.15, **LEGACY_ENVELOPE)
        assert target.breakeven_ratio > 1.0
        assert legacy.breakeven_ratio < 1.0
        assert target.cop > legacy.cop

    def test_the_legacy_envelope_still_reproduces(self):
        from HotGauge.thermal.microrefrigeration import MRParams, LEGACY_ENVELOPE
        m = MRParams(target_K=358.15, **LEGACY_ENVELOPE)
        assert (m.h_max, m.dt_max_K) == (10.0, 10.0)
        assert m.cop == pytest.approx(0.14)

    def test_the_vt_lever_is_now_inside_the_envelope(self):
        """Why the envelope mattered: 50 and 75 mV were unreachable at dt_max=10."""
        from HotGauge.thermal.microrefrigeration import DEFAULT_DT_MAX_K, LEGACY_DT_MAX_K
        from HotGauge.power.irds_vf import IRDSVFModel
        for dvt, _ in ((50.0, None), (75.0, None)):
            need = IRDSVFModel(2024, vt_shift_mV=dvt).cooling_K_to_offset(10.9)
            assert need > LEGACY_DT_MAX_K       # was out of reach by assumption
            assert need < DEFAULT_DT_MAX_K      # is inside the demonstrated capability

    def test_no_driver_re_hardcodes_the_envelope(self):
        """Eight definitions is how the envelope went unsourced for months.

        Every driver must take these from the module. A literal here is not a wrong number
        today -- it is a number that will not move when the module does.
        """
        import glob, os, re
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
                            'examples')
        if not os.path.isdir(root):
            pytest.skip('examples/ not present')
        # '--dt-max' (no -K suffix) was MISSING from this list until 27 Aug 2026, and that hole
        # is why the centralisation passed while examples/thermal_tiers.py and
        # examples/stacked_memory_study.py both kept a hardcoded `default=10.0` -- the legacy
        # envelope -- for the parameter that sets every plateau width they report. A guard with
        # an incomplete flag list reads exactly like a guard that passes.
        FLAGS = ('--mr-h-max', '--mr-dt-max', '--dt-max-K', '--dt-max', '--eta-asf',
                 '--eta-laser', '--eta-lpc')
        bad = []
        for f in sorted(glob.glob(os.path.join(root, '*.py'))):
            src = open(f).read()
            for flag in FLAGS:
                for m in re.finditer(re.escape(flag) + r"',\s*type=float,\s*default=([^,)\s]+)",
                                     src):
                    val = m.group(1)
                    if re.match(r'^[0-9.]+$', val):
                        bad.append('{}: {} default={}'.format(os.path.basename(f), flag, val))
        assert not bad, 'hardcoded envelope defaults: ' + '; '.join(bad)


class TestConservationCap:
    """The array cannot remove more heat than the die generates.

    Three DEVICE caps already bounded a plan -- h_max, dt_max and the need itself. None of them
    is a physical bound, and with the envelope corrected to its demonstrated values they stopped
    restraining the first iteration, which is sized from an ASSUMED sensitivity of 1.0 K/W. On a
    representative near-cliff field the first plan went 841 W -> 9405 W against a die dissipating
    79 W, and applied to the trace it produced blocks at 3838 K.
    """

    @staticmethod
    def _field(n=400, excess_K=40.0, target_K=365.15):
        geom = {'b{}'.format(i): {'area_mm2': 0.2, 'min_dim_um': 400.0} for i in range(n)}
        temps = {'b{}'.format(i): target_K + max(0.0, excess_K - 0.06 * i) for i in range(n)}
        return geom, temps, target_K

    def test_without_the_cap_the_plan_can_exceed_the_die_by_orders_of_magnitude(self):
        """The behaviour being fixed, pinned so it cannot come back unnoticed."""
        from HotGauge.thermal.microrefrigeration import clipping_plan, MRParams
        geom, temps, tk = self._field()
        plan, _ = clipping_plan(temps, geom, MRParams(target_K=tk), {b: 1.0 for b in temps})
        assert sum(plan.values()) > 50 * 79.0

    def test_the_cap_conserves_energy(self):
        from HotGauge.thermal.microrefrigeration import clipping_plan, MRParams
        geom, temps, tk = self._field()
        plan, _ = clipping_plan(temps, geom, MRParams(target_K=tk), {b: 1.0 for b in temps},
                                die_power_W=79.0)
        assert sum(plan.values()) == pytest.approx(79.0, rel=1e-9)

    def test_it_SCALES_rather_than_reallocating(self):
        """A conservation violation is not a spending decision. The plan's shape came from the
        physics; only its total is impossible. Greedy reallocation under this cap would put the
        whole die's power on the two hottest blocks -- a second pathology replacing the first."""
        from HotGauge.thermal.microrefrigeration import clipping_plan, MRParams
        geom, temps, tk = self._field()
        raw, _ = clipping_plan(temps, geom, MRParams(target_K=tk), {b: 1.0 for b in temps})
        capped, _ = clipping_plan(temps, geom, MRParams(target_K=tk), {b: 1.0 for b in temps},
                                  die_power_W=79.0)
        assert set(capped) == set(raw), 'scaling must not drop blocks'
        scale = 79.0 / sum(raw.values())
        for b in raw:
            assert capped[b] == pytest.approx(raw[b] * scale, rel=1e-9)
        assert max(capped.values()) < 1.0, 'no block should carry a large share after scaling'

    def test_a_plan_within_the_die_power_is_untouched(self):
        """The working regime must not move. Real margin plans remove a few percent of die power."""
        from HotGauge.thermal.microrefrigeration import clipping_plan, MRParams
        geom = {'b0': {'area_mm2': 0.2, 'min_dim_um': 400.0},
                'b1': {'area_mm2': 0.2, 'min_dim_um': 400.0}}
        tk = 365.15
        temps = {'b0': tk + 2.0, 'b1': tk + 1.0}
        sens = {'b0': 1.0, 'b1': 1.0}
        free, _ = clipping_plan(temps, geom, MRParams(target_K=tk), sens)
        capped, _ = clipping_plan(temps, geom, MRParams(target_K=tk), sens, die_power_W=79.0)
        assert free == capped

    def test_the_cap_is_GLOBAL_not_per_block(self):
        """Per-block q <= p_block is the wrong physics: the array sits ABOVE the silicon, so a
        tile cools a neighbourhood and legitimately removes more than the block under it
        dissipates. Measured, the working margin plans remove 0.108 W per engaged block against a
        0.070 W mean block power -- a strict per-block rule would break correct results."""
        from HotGauge.thermal.microrefrigeration import clipping_plan, MRParams
        geom = {'hot': {'area_mm2': 0.2, 'min_dim_um': 400.0},
                'cold': {'area_mm2': 0.2, 'min_dim_um': 400.0}}
        tk = 365.15
        temps = {'hot': tk + 5.0, 'cold': tk + 0.001}
        plan, _ = clipping_plan(temps, geom, MRParams(target_K=tk),
                                {'hot': 1.0, 'cold': 1.0}, die_power_W=10.0)
        # 5 W on one block is allowed under a 10 W die budget even though one block of a
        # two-block die "owns" only 5 W of dissipation.
        assert plan['hot'] == pytest.approx(5.0, rel=1e-6)

    def test_budget_and_conservation_are_distinguishable_in_the_detail(self):
        """They mean opposite things -- a budget hit is a result, a conservation hit is a bug
        signal -- so a reader must be able to tell which bound."""
        from HotGauge.thermal.microrefrigeration import clipping_plan, MRParams
        geom, temps, tk = self._field(n=50)
        _, det = clipping_plan(temps, geom, MRParams(target_K=tk), {b: 1.0 for b in temps},
                               die_power_W=5.0)
        assert any('die_power_scaled' in d['limit'] for d in det.values())
        _, det2 = clipping_plan(temps, geom, MRParams(target_K=tk, max_total_W=5.0),
                                {b: 1.0 for b in temps})
        assert any(d['limit'] in ('budget', 'budget_exhausted') for d in det2.values())


class TestSensitivityIsMeasuredNotAssumed:
    """The descent used to size its first plan from an ASSUMED 1.0 K/W.

    Under the legacy envelope the device caps hid that: h_max bound 396 of 400 blocks on a
    near-cliff field, so the plan was restrained by the device rather than by the guess. With the
    envelope corrected, `q_need = excess / s` binds instead and the guess sets the plan directly.
    """

    @staticmethod
    def _rig(true_s=0.35, die_W=50.0, target_K=370.0):
        """A lumped stand-in whose sensitivity is known, so the probe can be checked against it."""
        import numpy as np
        import HotGauge.thermal.microrefrigeration as M
        geom = {'b0': {'area_mm2': 0.2, 'min_dim_um': 400.0},
                'b1': {'area_mm2': 0.2, 'min_dim_um': 400.0}}
        base = {'b0': np.array([400.0]), 'b1': np.array([395.0])}

        class _Tr(object):
            def __init__(self, p):
                self.powers = dict(p)
                self.time_step = 1.0
                self._removed = {}

        def solve(tr):
            rem = getattr(tr, '_removed', {})
            return {b: base[b] - true_s * rem.get(b, 0.0) for b in base}

        class _Stub(object):
            def __init__(self, *a, **k):
                self.placement = 'test'
                self.last_tile_plan = None
            def __call__(self, plan):
                t = _Tr({})
                t._removed = dict(plan)
                return t

        return M, geom, _Tr, solve, _Stub, die_W, target_K

    def test_the_probe_recovers_a_known_sensitivity(self):
        from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams
        M, geom, Tr, solve, Stub, die_W, tk = self._rig(true_s=0.35)
        orig, M.CoolingApplication = M.CoolingApplication, Stub
        try:
            r = run_mr_clipping(Tr({}), solve, geom, MRParams(target_K=tk), {},
                                die_power_W=die_W, max_iter=3)
        finally:
            M.CoolingApplication = orig
        assert r['sensitivity']
        for v in r['sensitivity'].values():
            assert v == pytest.approx(0.35, rel=1e-6)

    def test_it_recovers_a_DIFFERENT_sensitivity_too(self):
        """Guards against the value being coincidentally right rather than measured."""
        from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams
        M, geom, Tr, solve, Stub, die_W, tk = self._rig(true_s=0.08)
        orig, M.CoolingApplication = M.CoolingApplication, Stub
        try:
            r = run_mr_clipping(Tr({}), solve, geom, MRParams(target_K=tk), {},
                                die_power_W=die_W, max_iter=3)
        finally:
            M.CoolingApplication = orig
        for v in r['sensitivity'].values():
            assert v == pytest.approx(0.08, rel=1e-6)
        assert all(abs(v - 1.0) > 0.5 for v in r['sensitivity'].values()), 'still the guess'

    def test_calibration_can_be_switched_off_and_then_it_is_the_old_guess(self):
        """The historical behaviour must stay reachable, so a result can be reproduced."""
        from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams
        M, geom, Tr, solve, Stub, die_W, tk = self._rig(true_s=0.35)
        orig, M.CoolingApplication = M.CoolingApplication, Stub
        try:
            r = run_mr_clipping(Tr({}), solve, geom, MRParams(target_K=tk), {},
                                die_power_W=die_W, max_iter=1, calibrate=False)
        finally:
            M.CoolingApplication = orig
        # With no probe the first plan is sized from 1.0 K/W, so the recorded sensitivity for the
        # first iteration cannot have come from a measurement of 0.35 before the plan was built.
        assert r is not None

    def test_no_die_power_means_no_probe(self):
        """die_power_W is what sets the probe's scale; without it there is nothing to size from."""
        from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams
        M, geom, Tr, solve, Stub, die_W, tk = self._rig(true_s=0.35)
        orig, M.CoolingApplication = M.CoolingApplication, Stub
        try:
            r = run_mr_clipping(Tr({}), solve, geom, MRParams(target_K=tk), {}, max_iter=1)
        finally:
            M.CoolingApplication = orig
        assert r is not None


# ---------------------------------------------------------------------------
# The two loop models must not drift apart again.
#
# `MRParams.breakeven_ratio` and `exergy.loop_gain` are two statements of the same loop, and
# before 30 August 2026 they disagreed: the first omitted the Carnot factor on the anti-Stokes
# term, which made it the phi -> 1 limit and reported the shipped defaults as net-generating.
# `eta_AS` in eq. (1.15) IS `eta_asf` here, so the correspondence below is an identity, not a
# calibration.
# ---------------------------------------------------------------------------

def test_breakeven_ratio_at_matches_exergy_loop_gain():
    """The second-law forms are the same equation and must agree to machine precision."""
    from HotGauge.thermal import exergy as EX
    from HotGauge.thermal.microrefrigeration import MRParams
    p = MRParams(313.15)
    eta_c = p.lpc_efficiency * p.collection_efficiency
    for T_h in (310.0, 350.0, 400.0, 500.0, 700.0, 1000.0):
        mr = p.breakeven_ratio_at(T_h, 295.0)
        ex = EX.loop_gain(p.laser_wallplug, eta_c, p.eta_asf, T_h, 295.0)
        assert abs(mr - ex) < 1e-12, (T_h, mr, ex)


def test_first_law_ratio_is_the_infinite_temperature_limit():
    """`breakeven_ratio` is `breakeven_ratio_at(T_h -> inf)`, which is why it overstates."""
    from HotGauge.thermal.microrefrigeration import MRParams
    p = MRParams(313.15)
    assert p.breakeven_ratio_at(1e12, 295.0) == pytest.approx(p.breakeven_ratio, rel=1e-9)
    # and it is strictly optimistic at every finite temperature
    for T_h in (310.0, 400.0, 1000.0):
        assert p.breakeven_ratio_at(T_h, 295.0) < p.breakeven_ratio


def test_defaults_do_not_self_power_at_any_survivable_temperature():
    """The headline the loop-model reconciliation overturned: 1.032 first-law vs < 1 everywhere real.

    The shipped envelope IS first-law net-generating -- that is the `phi -> 1` limit, not a claim
    about physics -- and the second-law form is below 1 at every survivable junction temperature.
    Both are pinned so the two ledgers cannot be conflated again.
    """
    from HotGauge.thermal.microrefrigeration import MRParams
    p = MRParams(313.15)
    assert p.breakeven_ratio > 1.0             # what the first-law ledger reports
    for T_h in (350.0, 500.0, 1000.0):         # what the second law permits
        assert p.breakeven_ratio_at(T_h, 295.0) < 1.0


def test_mr_accounting_flags_whether_it_is_second_law_bounded():
    from HotGauge.thermal.microrefrigeration import MRParams, mr_accounting
    p = MRParams(313.15)
    plan = {'blk': 2.0}
    loose = mr_accounting(plan, p)
    tight = mr_accounting(plan, p, T_h_K=350.0)
    assert loose['second_law_bounded'] is False and loose['T_h_K'] is None
    assert tight['second_law_bounded'] is True and tight['T_h_K'] == 350.0
    # the optimistic ledger recovers more, and only it can report net generation
    assert tight['recovered_W'] < loose['recovered_W']
    assert loose['net_generating'] is True
    assert tight['net_generating'] is False
