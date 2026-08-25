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

    def test_transient_mode_refuses_an_array(self):
        """It would need a per-slot tile trace, and nothing produces one."""
        from HotGauge.thermal import ICEThermalSolver
        with self.assertRaises(ValueError):
            ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='transient',
                             mr_flp_template='MR.flp', mr_powers={'MR_r00_c00': -1.0})

    def test_set_mr_powers_refuses_a_solver_with_no_array(self):
        """Adding one late would render a stack with an unfilled placeholder."""
        with self.assertRaises(ValueError):
            self._solver().set_mr_powers({'MR_r00_c00': -1.0})

    def test_set_mr_powers_replaces_the_plan_between_solves(self):
        s = self._solver(mr_flp_template='MR.flp', mr_powers={'MR_r00_c00': -1.0})
        s.set_mr_powers({'MR_r00_c00': -2.0, 'MR_r00_c01': -0.5})
        self.assertEqual(s.mr_powers, {'MR_r00_c00': -2.0, 'MR_r00_c01': -0.5})

    def test_session_cache_refuses_an_array_until_ordering_is_verified(self):
        """The socket takes one flat vector across both dies; a wrong order is silent."""
        from HotGauge.thermal import ICEThermalSolver
        from HotGauge.thermal.ice_server import ICESessionCache
        with self.assertRaises(NotImplementedError):
            ICEThermalSolver('s.stk', 'f.flp', 7, run_base_dir='.', mode='steady',
                             session_cache=ICESessionCache(),
                             mr_flp_template='MR.flp', mr_powers={'MR_r00_c00': -1.0})


if __name__ == '__main__':
    unittest.main()
