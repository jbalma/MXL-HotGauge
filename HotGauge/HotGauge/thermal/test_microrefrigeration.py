"""Tests for the microrefrigeration bridge (Goal 3). Pure Python -- no 3D-ICE binary."""
import numpy as np
import pytest

from HotGauge.power import BasicPowerTrace
from HotGauge.thermal.microrefrigeration import (MRParams, clipping_plan, apply_cooling_to_trace,
                                                 mr_accounting, estimate_sensitivity,
                                                 run_mr_clipping, DEFAULT_SPOT_MIN_UM,
                                                 DEFAULT_SPOT_POLICY)

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
