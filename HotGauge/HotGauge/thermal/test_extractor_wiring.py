"""The extractor curve wired into the planner: the lift emerges instead of being a parameter (§P0.19).

Synthetic solver throughout (no 3D-ICE). The solver models what matters: block temperatures
fall with the cooling applied, and the tiles above them fall further, so the extractor's
temperature-dependent cap can bind.
"""
import os
import tempfile

import numpy as np
import pytest

from HotGauge.thermal.microrefrigeration import (MRParams, clipping_plan, envelope_plan,
                                                 extractor_caps, run_mr_clipping)
from HotGauge.thermal.mr_array import (tile_grid, block_tile_temps, blocks_from_floorplan,
                                       deliver_capped, project_plan_shares, tiles_over_blocks)
from HotGauge.thermal.microrefrigeration import extractor_tile_caps
from HotGauge.thermal.extractor import DualZoneExtractor
from HotGauge.thermal.leakage_feedback import ICEThermalSolver, MR_DIE_TFLP_OUTPUT
from HotGauge.power import BasicPowerTrace


class _Curve(object):
    """A toy extractor: flux falls linearly with tile temperature, zero at T_min."""
    label = 'toy'
    platform = 'toy'

    def __init__(self, h0=10.0, T_min=260.0, T_ref=300.0):
        self.h0, self.T_min, self.T_ref = h0, T_min, T_ref

    def cooling_density_W_per_mm2(self, T_K):
        return self.h0 * (T_K - self.T_min) / (self.T_ref - self.T_min)

    def t_min_K(self):
        return self.T_min

    def eta_asf(self, T_K):
        return 0.1


# ---------------------------------------------------------------------------
# parameters and caps
# ---------------------------------------------------------------------------
def test_dt_max_none_needs_an_extractor_and_reads_as_no_scalar_cap():
    with pytest.raises(ValueError):
        MRParams(target_K=365.0, dt_max_K=None)
    p = MRParams(target_K=365.0, dt_max_K=None, extractor=_Curve())
    assert p.dt_max_K == float('inf')
    assert 'dT<=inf' in repr(p) and 'extractor=toy' in repr(p)
    # the scalar survives when given explicitly alongside the extractor
    assert MRParams(target_K=365.0, dt_max_K=45.0, extractor=_Curve()).dt_max_K == 45.0


def test_clipping_plan_uses_the_per_block_cap_and_skips_an_exhausted_block():
    p = MRParams(target_K=365.0, h_max=1000.0, dt_max_K=None, extractor=_Curve())
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 500.0}, 'B': {'area_mm2': 1.0, 'min_dim_um': 500.0}}
    temps = {'A': 400.0, 'B': 400.0}
    sens = {'A': 1.0, 'B': 1.0}
    plan, detail = clipping_plan(temps, geom, p, sens, h_max_by_block={'A': 5.0, 'B': 0.0})
    assert plan['A'] == pytest.approx(5.0) and detail['A']['limit'] == 'extractor'
    assert 'B' not in plan and detail['B']['limit'] == 'extractor_exhausted'
    # without the cap the same block is bound by need (35 W) under a generous h_max
    plan2, d2 = clipping_plan(temps, geom, p, sens)
    assert plan2['A'] == pytest.approx(35.0) and d2['A']['limit'] == 'need'


def test_extractor_caps_evaluate_the_curve_at_the_tile_above_each_block():
    tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)      # 2 x 2
    blocks = {'A': (100.0, 100.0, 200.0, 200.0), 'B': (1200.0, 1200.0, 200.0, 200.0)}
    p = MRParams(target_K=365.0, dt_max_K=None, extractor=_Curve(h0=10.0, T_min=260.0))
    tt = {'MR_r00_c00': 300.0, 'MR_r01_c01': 260.0, 'MR_r00_c01': 280.0, 'MR_r01_c00': 280.0}
    caps = extractor_caps(p, tt, tiles, blocks)
    assert caps['A'] == pytest.approx(10.0)
    assert caps['B'] == pytest.approx(0.0)
    assert extractor_caps(MRParams(target_K=365.0), tt, tiles, blocks) is None
    assert extractor_caps(p, {}, tiles, blocks) is None


def test_block_tile_temps_area_weights_and_routes_gap_blocks():
    tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0, fill=0.5)  # gapped
    tt = {t['name']: 300.0 + 10.0 * i for i, t in enumerate(tiles)}
    blocks = {'under': (300.0, 300.0, 100.0, 100.0), 'gap': (0.0, 0.0, 50.0, 50.0),
              'straddle': (700.0, 300.0, 600.0, 100.0)}
    bt = block_tile_temps(tt, blocks, tiles)
    assert bt['under'] == pytest.approx(tt['MR_r00_c00'])
    assert bt['gap'] == pytest.approx(tt['MR_r00_c00'])          # nearest tile
    assert min(tt['MR_r00_c00'], tt['MR_r00_c01']) <= bt['straddle'] <= max(tt['MR_r00_c00'], tt['MR_r00_c01'])


# ---------------------------------------------------------------------------
# the loop: the lift emerges
# ---------------------------------------------------------------------------
def _run(extractor, T0=420.0, s_block=1.0, s_tile=3.0, target=365.0, **kw):
    """One block under one tile. Block T = T0 - s_block q; tile T = T0 - 20 - s_tile q."""
    state = {'q': 0.0, 'tiles': {'MR_r00_c00': T0 - 20.0}}
    tiles = tile_grid(1000.0, 1000.0, pitch_um=1000.0, cell_um=100.0)
    blocks = {'A': (0.0, 0.0, 1000.0, 1000.0)}
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 1000.0}}
    trace = BasicPowerTrace({'A': np.array([50.0])}, 1.0)

    def set_powers(tp):
        state['q'] = -sum(tp.values())

    def solve(tr):
        q = state['q']
        state['tiles'] = {'MR_r00_c00': T0 - 20.0 - s_tile * q}
        return {'A': np.array([T0 - s_block * q])}

    p = MRParams(target_K=target, h_max=1000.0, dt_max_K=None, extractor=extractor, **kw)
    res = run_mr_clipping(trace, solve, geom, p, lambda u: u, tiles=tiles, tile_blocks=blocks,
                          set_mr_powers=set_powers, status_fn=lambda: {'diverged': False},
                          tile_temps_fn=lambda: dict(state['tiles']), die_power_W=200.0,
                          calibrate=False, initial_sensitivity={'A': s_block}, max_iter=12)
    return res, state


def test_a_generous_extractor_lets_the_planner_hit_the_target():
    res, state = _run(_Curve(h0=1000.0, T_min=100.0))
    assert res['plan']['A'] == pytest.approx(55.0, rel=0.05)         # 420 -> 365 at 1 K/W
    assert res['extractor']['n_tiles_capped'] == 0 and res['extractor']['shortfall_W'] == 0.0
    assert res['extractor']['min_engaged_tile_K'] == pytest.approx(state['tiles']['MR_r00_c00'])
    assert res['extractor']['dt_max_scalar_K'] is None


def test_the_extractor_curve_caps_the_lift_where_the_tile_freezes_out():
    """Tile starts at 400 K and falls 3 K per W; a curve that dies at 340 K can therefore never
    deliver more than the flux at the tile temperature the cooling itself produces. The planner
    must land on the self-consistent point, never below T_min, and say so."""
    curve = _Curve(h0=30.0, T_min=340.0, T_ref=400.0)
    res, state = _run(curve)
    q = res['plan'].get('A', 0.0)
    tile = state['tiles']['MR_r00_c00']
    assert q > 0.0
    assert tile >= curve.T_min - 1.0, 'the array was driven below the temperature it can cool at'
    # self-consistent: the plan sits on the curve at the tile temperature it produced. The
    # exact fixed point of this toy is q = 12 W (tile 364 K).
    assert q == pytest.approx(12.0, rel=0.1)
    assert q <= curve.cooling_density_W_per_mm2(tile) + 1.0
    assert res['extractor']['n_tiles_capped'] == 1 and res['extractor']['shortfall_W'] > 0.0
    assert res['extractor']['reported_field_has_tiles']
    # and the target was NOT reached: that is the emergent lift limit, reported not hidden
    assert res['temp_trace']['A'][-1] > 365.0 + 1.0
    assert res['plan_holds_target'] is False


def test_converged_die_power_cap_tracks_the_solve():
    """With die_power_fn the energy cap follows the converged die power: a die that dissipates
    less once cooled cannot have more than that removed (the 12 W over-pull of P0.18.2)."""
    calls = {'n': 0}

    def die_power():
        calls['n'] += 1
        return 20.0                                          # converged die power

    tiles = tile_grid(1000.0, 1000.0, pitch_um=1000.0, cell_um=100.0)
    blocks = {'A': (0.0, 0.0, 1000.0, 1000.0)}
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 1000.0}}
    trace = BasicPowerTrace({'A': np.array([50.0])}, 1.0)
    state = {'q': 0.0}

    def solve(tr):
        return {'A': np.array([420.0 - 1.0 * state['q']])}

    p = MRParams(target_K=365.0, h_max=1000.0)
    res = run_mr_clipping(trace, solve, geom, p, lambda u: u, tiles=tiles, tile_blocks=blocks,
                          set_mr_powers=lambda tp: state.__setitem__('q', -sum(tp.values())),
                          status_fn=lambda: {'diverged': False}, die_power_W=50.0,
                          die_power_fn=die_power, calibrate=False,
                          initial_sensitivity={'A': 1.0}, max_iter=6)
    assert calls['n'] > 0
    assert sum(res['plan'].values()) <= 20.0 + 1e-6


# ---------------------------------------------------------------------------
# the solver reports tile temperatures, split from the blocks
# ---------------------------------------------------------------------------
def test_solver_refuses_mr_temps_without_an_array_and_splits_tiles_when_it_has_one(tmp_path):
    flp = tmp_path / 'die.flp'
    flp.write_text('A :\n\tposition 0.0, 0.0 ;\n\tdimension 1000.0, 1000.0 ;\n'
                   '\tpower values {powers[A]};\n')
    s = ICEThermalSolver('spec:package=direct_die,mr=GAAS', str(flp), 7, str(tmp_path),
                         mr_temps=True)
    assert s.mr_temps and s.last_mr_temps is None
    # no array -> nothing to split, field untouched
    assert s._split_mr_temps({'A': 300.0}) == {'A': 300.0}
    s.mr_powers = {'MR_r00_c00': -1.0}
    out = s._split_mr_temps({'A': np.array([330.0]), 'MR_r00_c00': np.array([290.0])})
    assert out == {'A': pytest.approx(330.0)} or list(out) == ['A']
    assert s.last_mr_temps == {'MR_r00_c00': pytest.approx(290.0)}
    with pytest.raises(RuntimeError, match='no tile temperatures'):
        s._split_mr_temps({'A': np.array([330.0])})
    assert 'MR_ARRAY' in MR_DIE_TFLP_OUTPUT


def test_deliver_capped_scales_blocks_back_in_proportion_and_reports_the_shortfall():
    tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)          # 2 x 2
    blocks = {'A': (100.0, 100.0, 200.0, 200.0),                                # under r00_c00
              'S': (700.0, 300.0, 600.0, 100.0)}                                # straddles c00/c01
    plan = {'A': 4.0, 'S': 2.0}
    shares = project_plan_shares(plan, blocks, tiles)
    assert shares['A'] == {'MR_r00_c00': pytest.approx(4.0)}
    assert sum(shares['S'].values()) == pytest.approx(2.0)
    caps = {'MR_r00_c00': 2.5}                                                  # r00_c00 asked 5.0
    tile_plan, delivered, short, n = deliver_capped(plan, blocks, tiles, caps)
    assert tile_plan['MR_r00_c00'] == pytest.approx(2.5) and n == 1
    assert short == pytest.approx(2.5)
    assert delivered['A'] == pytest.approx(2.0)                                 # scaled by 0.5
    assert delivered['S'] == pytest.approx(1.0 * 0.5 + 1.0)                     # half capped, half not
    assert sum(tile_plan.values()) == pytest.approx(sum(delivered.values()))


def test_caps_are_not_made_from_a_diverged_field():
    """A runaway field's tile temperatures are not a state the array is in; the application
    after a diverged solve must be uncapped (the recorded envelope path's first plan)."""
    calls = {'n': 0}
    state = {'q': 0.0, 'tiles': {'MR_r00_c00': 900.0}, 'div': True}
    tiles = tile_grid(1000.0, 1000.0, pitch_um=1000.0, cell_um=100.0)
    blocks = {'A': (0.0, 0.0, 1000.0, 1000.0)}
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 1000.0}}
    trace = BasicPowerTrace({'A': np.array([50.0])}, 1.0)

    def set_powers(tp):
        state['q'] = -sum(tp.values())
        calls['n'] += 1

    def solve(tr):
        q = state['q']
        # uncooled: runaway (900 K tiles). Any cooling >= 5 W: converged, cool tiles (floored
        # at 250 K so the toy stays physical under a large first plan).
        state['div'] = q < 5.0
        state['tiles'] = {'MR_r00_c00': 900.0 if state['div'] else max(380.0 - 3.0 * q, 250.0)}
        return {'A': np.array([1200.0 if state['div'] else 420.0 - q])}

    # a curve that is DEAD at 900 K (hot-side limit) but fine at 250-400 K
    class HotLimited(_Curve):
        def cooling_density_W_per_mm2(self, T_K):
            return 0.0 if T_K > 500.0 else 30.0
    p = MRParams(target_K=365.0, h_max=1000.0, dt_max_K=None, extractor=HotLimited())
    res = run_mr_clipping(trace, solve, geom, p, lambda u: u, tiles=tiles, tile_blocks=blocks,
                          set_mr_powers=set_powers, status_fn=lambda: {'diverged': state['div']},
                          tile_temps_fn=lambda: dict(state['tiles']), die_power_W=60.0,
                          calibrate=False, initial_sensitivity={'A': 1.0}, max_iter=8,
                          plan_mode='envelope')
    # the first plan (60 W, uncapped) converged; it was then re-applied under the cap made from
    # THAT converged field (30 W), never from the 900 K runaway field
    assert not res.get('temp_trace_diverged'), res.get('reason')
    assert 0.0 < sum(res['plan'].values()) <= 30.0 + 1e-6
    assert res['extractor']['reported_field_has_tiles']


def test_converged_energy_cap_binds_in_the_envelope_path():
    state = {'q': 0.0}
    tiles = tile_grid(1000.0, 1000.0, pitch_um=1000.0, cell_um=100.0)
    blocks = {'A': (0.0, 0.0, 1000.0, 1000.0)}
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 1000.0}}
    trace = BasicPowerTrace({'A': np.array([50.0])}, 1.0)

    def solve(tr):
        q = state['q']
        return {'A': np.array([1200.0 if q < 5.0 else 420.0 - q])}

    p = MRParams(target_K=365.0, h_max=1000.0)
    res = run_mr_clipping(trace, solve, geom, p, lambda u: u, tiles=tiles, tile_blocks=blocks,
                          set_mr_powers=lambda tp: state.__setitem__('q', -sum(tp.values())),
                          status_fn=lambda: {'diverged': state['q'] < 5.0},
                          die_power_W=200.0, die_power_fn=lambda: 30.0, calibrate=False,
                          initial_sensitivity={'A': 1.0}, max_iter=8, plan_mode='envelope')
    assert sum(res['plan'].values()) <= 30.0 + 1e-6


def test_converged_cap_refuses_a_hold_that_over_pulls_the_die():
    """The first envelope plan is sized on the injected power; if holding the target needs more
    than the cooled die dissipates, the answer is 'conservation binds', not a hold."""
    state = {'q': 0.0}
    tiles = tile_grid(1000.0, 1000.0, pitch_um=1000.0, cell_um=100.0)
    blocks = {'A': (0.0, 0.0, 1000.0, 1000.0)}
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 1000.0}}
    trace = BasicPowerTrace({'A': np.array([50.0])}, 1.0)

    def solve(tr):
        q = state['q']
        return {'A': np.array([1200.0 if q < 5.0 else 430.0 - q])}   # needs 65 W for 365 K

    p = MRParams(target_K=365.0, h_max=1000.0)
    res = run_mr_clipping(trace, solve, geom, p, lambda u: u, tiles=tiles, tile_blocks=blocks,
                          set_mr_powers=lambda tp: state.__setitem__('q', -sum(tp.values())),
                          status_fn=lambda: {'diverged': state['q'] < 5.0},
                          # like the driver: no converged power while the last solve diverged
                          die_power_W=200.0, die_power_fn=lambda: None if state['q'] < 5.0 else 40.0,
                          calibrate=False,
                          initial_sensitivity={'A': 1.0}, max_iter=8, plan_mode='envelope')
    assert res.get('conservation_bound') is True
    assert res['plan_holds_target'] is False
    assert sum(res['plan'].values()) <= 40.0 + 1e-6
    assert 'conservation binds' in res['reason']


def test_converged_cap_that_still_holds_continues_the_descent():
    """The re-capped first plan holds the target: the descent must carry on from it (this path
    crashed on an ordering bug in the first run of the P0.19 campaign)."""
    state = {'q': 0.0}
    tiles = tile_grid(1000.0, 1000.0, pitch_um=1000.0, cell_um=100.0)
    blocks = {'A': (0.0, 0.0, 1000.0, 1000.0)}
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 1000.0}}
    trace = BasicPowerTrace({'A': np.array([50.0])}, 1.0)

    def solve(tr):
        q = state['q']
        return {'A': np.array([1200.0 if q < 5.0 else 400.0 - q])}   # 40 W -> 360 K holds

    p = MRParams(target_K=365.0, h_max=1000.0)
    res = run_mr_clipping(trace, solve, geom, p, lambda u: u, tiles=tiles, tile_blocks=blocks,
                          set_mr_powers=lambda tp: state.__setitem__('q', -sum(tp.values())),
                          status_fn=lambda: {'diverged': state['q'] < 5.0},
                          die_power_W=200.0, die_power_fn=lambda: None if state['q'] < 5.0 else 40.0,
                          calibrate=False, initial_sensitivity={'A': 1.0}, max_iter=8,
                          plan_mode='envelope')
    assert not res.get('conservation_bound')
    assert res['plan_holds_target'] is True
    assert sum(res['plan'].values()) <= 40.0 + 1e-6


def test_a_film_that_cannot_deliver_the_plan_is_reported_as_extractor_bound():
    """After the first (uncapped) envelope solve converges, the plan must be re-applied under the
    extractor cap; a film with a few percent of the needed flux cannot hold and must say so
    (the v98 first pass reported a 0.04 W-per-tile film as holding 2.00 W/mm^2)."""
    state = {'q': 0.0, 'tiles': {'MR_r00_c00': 900.0}, 'div': True}
    tiles = tile_grid(1000.0, 1000.0, pitch_um=1000.0, cell_um=100.0)
    blocks = {'A': (0.0, 0.0, 1000.0, 1000.0)}
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 1000.0}}
    trace = BasicPowerTrace({'A': np.array([50.0])}, 1.0)

    def set_powers(tp):
        state['q'] = -sum(tp.values())

    def solve(tr):
        q = state['q']
        state['div'] = q < 5.0                      # needs >= 5 W for a steady state at all
        state['tiles'] = {'MR_r00_c00': 900.0 if state['div'] else 380.0 - 3.0 * q}
        return {'A': np.array([1200.0 if state['div'] else 420.0 - q])}

    weak = _Curve(h0=2.0, T_min=100.0, T_ref=300.0)       # ~2 W/mm^2 -> 2 W per 1 mm^2 tile
    p = MRParams(target_K=365.0, h_max=1000.0, dt_max_K=None, extractor=weak)
    res = run_mr_clipping(trace, solve, geom, p, lambda u: u, tiles=tiles, tile_blocks=blocks,
                          set_mr_powers=set_powers, status_fn=lambda: {'diverged': state['div']},
                          tile_temps_fn=lambda: dict(state['tiles']), die_power_W=200.0,
                          calibrate=False, initial_sensitivity={'A': 1.0}, max_iter=8,
                          plan_mode='envelope')
    assert res.get('extractor_bound') is True
    assert res['plan_holds_target'] is False
    assert res['extractor_shortfall_W'] > 40.0
    assert sum(res['plan'].values()) <= 3.0


def test_tiles_over_cache_blocks_define_the_cold_zone():
    tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)     # 2 x 2
    blocks = {'L3_0': (0.0, 0.0, 1000.0, 1000.0),                          # fills r00_c00
              'L2_1': (1000.0, 0.0, 600.0, 1000.0),                        # 60 % of r00_c01
              'cALU_0': (1600.0, 0.0, 400.0, 1000.0),
              'FPU_0': (0.0, 1000.0, 2000.0, 1000.0)}                      # the bottom row
    cold = tiles_over_blocks(tiles, blocks, r'^(L2|L3)')
    assert cold == {'MR_r00_c00', 'MR_r00_c01'}
    assert tiles_over_blocks(tiles, blocks, r'^(L2|L3)', majority=0.7) == {'MR_r00_c00'}


def test_zoned_caps_give_cold_tiles_the_cold_curve():
    tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)
    dz = DualZoneExtractor(_Curve(h0=2.0, T_min=100.0), _Curve(h0=50.0, T_min=100.0),
                           cold_tiles={'MR_r00_c00'})
    p = MRParams(target_K=365.0, dt_max_K=None, extractor=dz)
    tt = {t['name']: 300.0 for t in tiles}
    caps = extractor_tile_caps(p, tt, tiles)
    assert caps['MR_r00_c00'] == pytest.approx(2.0)          # 2 W/mm^2 x 1 mm^2
    assert caps['MR_r01_c01'] == pytest.approx(50.0)


def test_an_uncapped_first_plan_does_not_trip_the_stale_plan_guard():
    """`[!]` Regression for the P0.21 smoke point: with a film that never binds (the target
    device on this die), the first-plan re-cap used to APPLY the plan to learn the shortfall,
    never solve it, and the next application tripped ArrayWiring's stale-plan guard. The
    set_mr_powers here enforces the same guard the real wiring does."""
    state = {'q': 0.0, 'tiles': {'MR_r00_c00': 900.0}, 'div': True, 'gen': 0, 'read': 0}
    tiles = tile_grid(1000.0, 1000.0, pitch_um=1000.0, cell_um=100.0)
    blocks = {'A': (0.0, 0.0, 1000.0, 1000.0)}
    geom = {'A': {'area_mm2': 1.0, 'min_dim_um': 1000.0}}
    trace = BasicPowerTrace({'A': np.array([50.0])}, 1.0)

    def set_powers(tp):
        if state['gen'] and state['read'] != state['gen']:
            raise RuntimeError('plan replaced before any solver read it')
        state['q'] = -sum(tp.values())
        state['gen'] += 1

    def solve(tr):
        state['read'] = state['gen']
        q = state['q']
        state['div'] = q < 5.0
        # tiles cool with the plan but stay physical (the 200 W seed plan must not send them
        # below the curve's range -- that is the extractor-bound test's job, not this one's)
        state['tiles'] = {'MR_r00_c00': 900.0 if state['div'] else max(380.0 - 3.0 * q, 250.0)}
        return {'A': np.array([1200.0 if state['div'] else 420.0 - q])}

    strong = _Curve(h0=800.0, T_min=100.0, T_ref=300.0)   # >= 600 W per tile: never binds
    p = MRParams(target_K=365.0, h_max=1000.0, dt_max_K=None, extractor=strong)
    res = run_mr_clipping(trace, solve, geom, p, lambda u: u, tiles=tiles, tile_blocks=blocks,
                          set_mr_powers=set_powers, status_fn=lambda: {'diverged': state['div']},
                          tile_temps_fn=lambda: dict(state['tiles']), die_power_W=200.0,
                          calibrate=False, initial_sensitivity={'A': 1.0}, max_iter=8,
                          plan_mode='envelope')
    assert not res.get('extractor_bound')
    assert res['plan_holds_target'] is True
    assert res['extractor']['n_tiles_capped'] == 0
