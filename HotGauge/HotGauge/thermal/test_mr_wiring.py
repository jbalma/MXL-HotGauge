"""The cooling array carried through the solver, not just through a hand-built .stk.

These guard the seams where a mistake would be silent rather than loud: a floorplan that accepts
no power, a sign lost between the plan and the file, a stack that declares a cooling die nobody
filled in. Every one of those returns a plausible temperature field rather than an error, which
is the only reason they are worth testing at this level of detail.

The end-to-end equivalence -- wired solver against a directly-driven 3D-ICE run -- is
``examples/mr_placement_probe.py``; it agrees to 0.0000 K and takes a couple of minutes, so it
lives there rather than here.
"""

import os
import tempfile
import unittest

import numpy as np

from HotGauge.thermal.ICE import ICESteadySim, ICESimConfig
from HotGauge.thermal.die_stack import StackSpec, write_stack
from HotGauge.thermal.mr_array import tile_grid, write_mr_floorplan, tile_powers_for_stack
from HotGauge.power import BasicPowerTrace


def _tiles():
    return tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)


def _sim(d, mr_flp_template=None, mr_powers=None, powered=True):
    spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=powered, cell_um=100.0)
    stack = write_stack(spec, os.path.join(d, 's.stk'))
    flp = os.path.join(d, 'die_template.flp')
    with open(flp, 'w') as f:
        f.write('A :\n\tposition 0.0, 0.0 ;\n\tdimension 2000.0, 2000.0 ;\n'
                '\tpower values {powers[A]};\n')
    trace = BasicPowerTrace({'A': np.array([10.0])}, 1.0)
    return ICESteadySim(stack, flp, trace, ICESimConfig(initial_temp=300.0),
                        os.path.join(d, 'run'),
                        mr_flp_template=mr_flp_template, mr_powers=mr_powers)


class TestConstruction(unittest.TestCase):

    def test_floorplan_and_powers_must_arrive_together(self):
        with tempfile.TemporaryDirectory() as d:
            tiles = _tiles()
            mr = write_mr_floorplan(os.path.join(d, 'MR.flp'), tiles)
            with self.assertRaises(ValueError):
                _sim(d, mr_flp_template=mr)
            with self.assertRaises(ValueError):
                _sim(d, mr_powers=tile_powers_for_stack({}, tiles))

    def test_a_sim_without_an_array_is_unchanged(self):
        """Every existing study takes this path; it must not shift by a byte."""
        with tempfile.TemporaryDirectory() as d:
            sim = _sim(d, powered=False)
            self.assertFalse(sim.has_mr_array)
            self.assertIsNone(sim.mr_flp_template)


class TestPowerLanding(unittest.TestCase):

    def test_a_stack_declaring_a_cooling_die_refuses_to_render_without_one(self):
        """Otherwise the stack keeps a literal {mr_flp_file} and 3D-ICE reports a missing file."""
        with tempfile.TemporaryDirectory() as d:
            sim = _sim(d)
            os.makedirs(sim.run_path, exist_ok=True)
            sim.fill_flp_template()
            with self.assertRaises(ValueError) as cm:
                sim.fill_stk_template()
            self.assertIn('cooling-array die', str(cm.exception))

    def test_tile_powers_must_actually_land(self):
        """A template with literal numbers passes through str.format and cools nothing."""
        with tempfile.TemporaryDirectory() as d:
            tiles = _tiles()
            bad = os.path.join(d, 'MR_literal.flp')
            with open(bad, 'w') as f:
                for t in tiles:
                    f.write('{} :\n\tposition {}, {} ;\n\tdimension {}, {} ;\n'
                            '\tpower values 0.0;\n'
                            .format(t['name'], t['x'], t['y'], t['w'], t['h']))
            powers = tile_powers_for_stack({tiles[0]['name']: 2.0}, tiles)
            sim = _sim(d, mr_flp_template=bad, mr_powers=powers)
            with self.assertRaises(ValueError) as cm:
                sim.fill_mr_flp_template()
            self.assertIn('inert', str(cm.exception))

    def test_positive_array_powers_are_refused(self):
        """The array REMOVES heat. A positive total means the sign was lost on the way in, and
        the solve would come back HOTTER with the cooler switched on."""
        with tempfile.TemporaryDirectory() as d:
            tiles = _tiles()
            mr = write_mr_floorplan(os.path.join(d, 'MR.flp'), tiles)
            positive = {t['name']: 1.0 for t in tiles}
            sim = _sim(d, mr_flp_template=mr, mr_powers=positive)
            with self.assertRaises(ValueError) as cm:
                sim.fill_mr_flp_template()
            self.assertIn('must be negative', str(cm.exception))

    def test_negative_powers_are_written_and_totalled_correctly(self):
        with tempfile.TemporaryDirectory() as d:
            tiles = _tiles()
            mr = write_mr_floorplan(os.path.join(d, 'MR.flp'), tiles)
            powers = tile_powers_for_stack({tiles[0]['name']: 2.0, tiles[3]['name']: 1.5}, tiles)
            sim = _sim(d, mr_flp_template=mr, mr_powers=powers)
            os.makedirs(sim.run_path, exist_ok=True)
            sim.fill_mr_flp_template()
            import re
            text = open(sim.mr_flp_file).read()
            vals = [float(x) for x in re.findall(r'power values ([-0-9.eE+]+)\s*;', text)]
            self.assertEqual(len(vals), len(tiles))
            self.assertAlmostEqual(sum(vals), -3.5, places=6)
            self.assertNotIn('{powers[', text)


class TestSolverPlumbing(unittest.TestCase):

    def _solver(self, **kw):
        from HotGauge.thermal import ICEThermalSolver
        return ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='steady', **kw)

    def test_solver_refuses_half_an_array(self):
        with self.assertRaises(ValueError):
            self._solver(mr_flp_template='MR.flp')

    def test_transient_mode_accepts_an_array_but_not_the_extractor_cap(self):
        """§P0.25 (F4): the array is wired for transients -- ``tile_power_schedule`` produces
        the per-slot tile trace the old refusal said nothing produced. The extractor cap
        (mr_temps) is still steady-only: a per-slot tile temperature field is a different
        output and nothing consumes it yet. Both halves are DELIBERATE; the refusal was lifted
        on purpose, not by accident."""
        from HotGauge.thermal import ICEThermalSolver
        s = ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='transient',
                             mr_flp_template='MR.flp', mr_powers={'MR_r00_c00': -1.0})
        self.assertEqual(s.mode, 'transient')
        with self.assertRaises(ValueError):
            ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='transient',
                             mr_temps=True,
                             mr_flp_template='MR.flp', mr_powers={'MR_r00_c00': -1.0})

    def test_set_mr_powers_refuses_a_solver_with_no_array(self):
        """Adding one late would render a stack with an unfilled placeholder."""
        with self.assertRaises(ValueError):
            self._solver().set_mr_powers({'MR_r00_c00': -1.0})

    def test_set_mr_powers_replaces_the_plan_between_solves(self):
        s = self._solver(mr_flp_template='MR.flp', mr_powers={'MR_r00_c00': -1.0})
        s.set_mr_powers({'MR_r00_c00': -2.0, 'MR_r00_c01': -0.5})
        self.assertEqual(s.mr_powers, {'MR_r00_c00': -2.0, 'MR_r00_c01': -0.5})

    def test_session_cache_now_accepts_an_array(self):
        """Was refused while the two-die element order was unverified. It is verified now.

        The socket takes one flat vector across both dies and a wrong order is silent, so this
        was a NotImplementedError rather than a bug waiting to happen. What lifted it is
        ice_server.stack_floorplans plus an end-to-end check against the one-shot Emulator on an
        asymmetric field -- see test_ice_server.py::TestTwoDieOrdering and
        test_two_die_server_matches_oneshot_emulator_by_name. Construction succeeding is the
        whole assertion; correctness lives in those tests, not this one.
        """
        from HotGauge.thermal import ICEThermalSolver
        from HotGauge.thermal.ice_server import ICESessionCache
        s = ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='steady',
                             session_cache=ICESessionCache(),
                             mr_flp_template='MR.flp', mr_powers={'MR_r00_c00': -1.0})
        self.assertIsNotNone(s.session_cache)
        self.assertEqual(s.mr_powers, {'MR_r00_c00': -1.0})

    def test_tile_powers_reach_the_session_solve(self):
        """The array must not be inert on the fast path.

        solve_named zero-fills any element it is not handed, so omitting the tiles produces a
        stack with a cooling array that removes nothing -- and a run that reads as the cooler
        being ineffective, with no error anywhere.
        """
        class _Session(object):
            def element_names(self):
                return ['CORE_0', 'CORE_1', 'MR_r00_c00', 'MR_r00_c01']

        class _Trace(object):
            powers = {'CORE_0': 3.0, 'CORE_1': 4.0}

        s = self._solver(mr_flp_template='MR.flp',
                         mr_powers={'MR_r00_c00': -1.5, 'MR_r00_c01': -0.5})
        got = s.session_powers(_Trace(), _Session())
        self.assertEqual(got, {'CORE_0': 3.0, 'CORE_1': 4.0,
                               'MR_r00_c00': -1.5, 'MR_r00_c01': -0.5})
        self.assertAlmostEqual(sum(got.values()), 5.0)

    def test_a_tile_the_stack_does_not_have_is_refused(self):
        class _Session(object):
            def element_names(self):
                return ['CORE_0', 'MR_r00_c00']

        class _Trace(object):
            powers = {'CORE_0': 3.0}

        s = self._solver(mr_flp_template='MR.flp', mr_powers={'MR_r09_c09': -1.0})
        with self.assertRaisesRegex(RuntimeError, 'silently remove nothing'):
            s.session_powers(_Trace(), _Session())

    def test_a_tile_named_like_a_processor_block_is_refused(self):
        class _Session(object):
            def element_names(self):
                return ['CORE_0']

        class _Trace(object):
            powers = {'CORE_0': 3.0}

        s = self._solver(mr_flp_template='MR.flp', mr_powers={'CORE_0': -1.0})
        with self.assertRaisesRegex(RuntimeError, 'collide'):
            s.session_powers(_Trace(), _Session())

    def test_no_array_means_the_block_powers_are_unchanged(self):
        class _Session(object):
            def element_names(self):
                raise AssertionError('must not be consulted when there is no array')

        class _Trace(object):
            powers = {'CORE_0': 3.0, 'CORE_1': 4.0}

        s = self._solver()
        self.assertEqual(s.session_powers(_Trace(), _Session()),
                         {'CORE_0': 3.0, 'CORE_1': 4.0})

    def test_a_transient_array_still_refuses_the_session_cache(self):
        """The transient path does its own multi-step solve; the cache is steady-only."""
        from HotGauge.thermal import ICEThermalSolver
        with self.assertRaises(ValueError):
            ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='transient',
                             session_cache=object(),
                             mr_flp_template='MR.flp', mr_powers={'MR_r00_c00': -1.0})

    def test_a_tile_series_must_have_one_value_per_slot(self):
        """The transient branch broadcasts scalars and refuses a series of the wrong length --
        a short series would let 3D-ICE pad the array with zeros and read as a cooler that
        switches itself off."""
        import numpy as np
        from HotGauge.thermal import ICEThermalSolver
        from HotGauge.thermal.leakage_feedback import ICEThermalSolver as _S
        s = ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='transient',
                             mr_flp_template='MR.flp',
                             mr_powers={'MR_r00_c00': -1.0, 'MR_r00_c01': np.array([-1.0, -2.0])})
        captured = {}

        class _Sim(object):
            OUTPUT_TSTACK_FINAL = 'Tstack ("final.tstack", final ) ;'
            DIE_TFLP_OUTPUT = 'Tflp (PROCESSOR_DIE, "die_elements.temps", average, slot) ;'
            def __init__(self, *a, **k):
                captured.update(k); self.run_path = '.'
            @staticmethod
            def run(sims): raise RuntimeError('stop here')
        import HotGauge.thermal as th
        orig = th.ICETransientSim
        th.ICETransientSim = _Sim
        try:
            class _T(object):
                powers = {'B': np.array([1.0, 2.0])}; time_step = 1e-3
                def __len__(self): return 2
            try:
                s._run_and_read_temps(_T(), '.')
            except RuntimeError:
                pass
            np.testing.assert_allclose(captured['mr_powers']['MR_r00_c00'], [-1.0, -1.0])
            np.testing.assert_allclose(captured['mr_powers']['MR_r00_c01'], [-1.0, -2.0])
            s3 = ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='transient',
                                  mr_flp_template='MR.flp',
                                  mr_powers={'MR_r00_c00': np.array([-1.0, -2.0, -3.0])})
            with self.assertRaises(ValueError):
                s3._run_and_read_temps(_T(), '.')
        finally:
            th.ICETransientSim = orig


if __name__ == '__main__':
    unittest.main()


def test_planner_leaves_the_array_matching_the_plan_it_reports():
    """CoolingApplication sets tile powers as a SIDE EFFECT and nothing rewinds them.

    An exit that reports a different plan than the last one applied -- 'nothing above target'
    reports {} -- would leave the array carrying the previous call's cooling, so the caller solves
    a die cooled by a plan its own accounting says does not exist. In clock_headroom the wiring is
    built once per arm and reused across every step of the clock bisection, so this leaked between
    candidate clocks and produced 4.8125 GHz at 62.6 C on 183.9 W with 0.000 W removed, against an
    array_idle arm that diverged at 3.4531 GHz on 61.7 W.
    """
    import numpy as np
    import HotGauge.thermal.microrefrigeration as M
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    applied = []                      # every tile-power push, in order

    geom = {'b0': {'area_mm2': 0.2, 'min_dim_um': 400.0}}
    base = {'b0': np.array([300.0])}  # WELL below target -> 'nothing above target'

    class _Tr(object):
        def __init__(self):
            self.powers, self.time_step = {}, 1.0

    def solve(tr):
        return base

    class _Stub(object):
        def __init__(self, *a, **k):
            self.placement, self.last_tile_plan = 'test', None
        def __call__(self, plan):
            applied.append(dict(plan))
            self.last_tile_plan = dict(plan)
            return _Tr()

    orig, M.CoolingApplication = M.CoolingApplication, _Stub
    try:
        res = run_mr_clipping(_Tr(), solve, geom, MRParams(target_K=400.0), {},
                              die_power_W=50.0, max_iter=2)
    finally:
        M.CoolingApplication = orig

    assert res['plan'] == {}, 'nothing was above target, so the reported plan must be empty'
    assert applied, 'the stub should have seen at least one application'
    assert applied[-1] == {}, (
        'the LAST thing applied to the array must be the plan being reported; it was {!r}'
        .format(applied[-1]))


def test_a_second_planning_call_does_not_inherit_the_first_ones_plan():
    """Zero at entry and re-apply at exit are two halves of ONE invariant.

    The exit hook alone leaves the array holding call N's plan when call N+1 solves its baseline.
    In clock_headroom the wiring is built once per ARM and reused across every step of the clock
    bisection, so that is the path actually taken. Symptom, measured 27 Aug 2026 at r_th 0.3 with
    the exit hook in place but not the entry zeroing: array_on reported 4.7188 GHz at 71.0 C on
    167.6 W with 0.000 W removed, while array_idle -- same stack, lower clock, 61.7 W -- sat at
    85.0 C. A baseline cannot be cooler than the same die at lower power unless something is
    cooling it.
    """
    import numpy as np
    import HotGauge.thermal.microrefrigeration as M
    from HotGauge.thermal.microrefrigeration import run_mr_clipping, MRParams

    geom = {'b0': {'area_mm2': 0.2, 'min_dim_um': 400.0}}
    hot = {'b0': np.array([500.0])}      # above target -> a real plan is built
    cold = {'b0': np.array([300.0])}     # below target -> 'nothing above target'
    state = {'temps': hot, 'applications': []}

    class _Tr(object):
        def __init__(self):
            self.powers, self.time_step = {}, 1.0

    def solve(tr):
        return state['temps']

    class _Stub(object):
        def __init__(self, *a, **k):
            self.placement, self.last_tile_plan, self.current = 'test', None, {}

        def __call__(self, plan):
            state['applications'].append(dict(plan))
            self.current = dict(plan)
            self.last_tile_plan = dict(plan)
            return _Tr()

    stub = _Stub()
    orig, M.CoolingApplication = M.CoolingApplication, lambda *a, **k: stub
    try:
        r1 = run_mr_clipping(_Tr(), solve, geom, MRParams(target_K=400.0), {},
                             die_power_W=50.0, max_iter=2)
        assert r1['plan'], 'call 1 should have planned something'
        assert stub.current, 'and should leave it applied, matching what it reports'

        state['temps'] = cold
        state['applications'] = []
        r2 = run_mr_clipping(_Tr(), solve, geom, MRParams(target_K=400.0), {},
                             die_power_W=50.0, max_iter=2)
    finally:
        M.CoolingApplication = orig

    assert r2['plan'] == {}
    assert state['applications'], 'call 2 should have applied something'
    assert state['applications'][0] == {}, (
        'call 2 must zero the array before solving its baseline rather than inheriting the '
        'previous plan; it applied {!r}'.format(state['applications'][0]))
