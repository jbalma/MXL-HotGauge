"""Tests for the generated thermal stack.

The load-bearing test is :func:`test_lidded_reproduces_legacy_template`. Every result this project
has published came through the checked-in ``skylake.stk``, so a generator that does not reproduce
it layer-for-layer would silently reinterpret the whole back catalogue rather than extend it.
"""

import os
import tempfile
import unittest

from HotGauge.thermal.die_stack import (StackSpec, MATERIALS, die_layers, graded_above,
                                        render_stack_text, write_stack, compare_packages,
                                        parse_spec_string, spec_string_filename, is_spec_string,
                                        DEFAULT_DIE_UM, DEFAULT_SOURCE_DEPTH_UM)
from HotGauge.thermal.stack_report import parse_stack, resistance_budget

_LEGACY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'stack_templates', 'skylake.stk')


class TestDieLayers(unittest.TestCase):

    def test_layers_sum_to_die_thickness(self):
        for die, depth in ((400.0, 360.0), (775.0, 700.0), (150.0, 100.0), (80.0, 40.0)):
            layers = die_layers(die, depth)
            self.assertAlmostEqual(sum(l['height_um'] for l in layers), die, places=6)

    def test_exactly_one_source_layer(self):
        layers = die_layers(400.0, 360.0)
        self.assertEqual(sum(1 for l in layers if l['kind'] == 'source'), 1)

    def test_source_sits_at_the_requested_depth(self):
        depth = 220.0
        layers = die_layers(400.0, depth)
        above = 0.0
        for l in layers:
            if l['kind'] == 'source':
                break
            above += l['height_um']
        self.assertAlmostEqual(above, depth, places=6)

    def test_source_can_reach_the_exposed_surface(self):
        """Depth zero is the limiting direct-die case and must not be a special case in code."""
        layers = die_layers(400.0, 0.0)
        self.assertEqual(layers[0]['kind'], 'source')

    def test_die_too_thin_for_its_active_layer_is_an_error(self):
        with self.assertRaises(ValueError):
            die_layers(die_um=100.0, source_depth_um=200.0)

    def test_grading_is_monotone_towards_the_source(self):
        hs = graded_above(500.0, n=5, ratio=0.6)
        self.assertTrue(all(a > b for a, b in zip(hs, hs[1:])),
                        'mesh must get finer approaching the active layer, got {}'.format(hs))
        self.assertAlmostEqual(sum(hs), 500.0, places=6)


class TestLegacyEquivalence(unittest.TestCase):

    def test_lidded_reproduces_legacy_template(self):
        """A default lidded build must be the historical stack, layer for layer.

        Not a formatting comparison -- the generated file is deliberately different text. What
        must match is everything the solver reads: the die's sub-layers and which one is the
        source, the package layers and their order, and every material constant.
        """
        legacy = parse_stack(_LEGACY)
        with tempfile.TemporaryDirectory() as d:
            path = write_stack(StackSpec(package='lidded', cell_um=50.0),
                               os.path.join(d, 's.stk'))
            built = parse_stack(path)

        self.assertEqual([(l['kind'], l['height_um'], l['material']) for l in legacy['die_layers']],
                         [(l['kind'], l['height_um'], l['material']) for l in built['die_layers']])
        self.assertEqual([(e['kind'], e['instance']) for e in legacy['stack']],
                         [(e['kind'], e['instance']) for e in built['stack']])
        for name, m in built['materials'].items():
            if name in legacy['materials']:
                self.assertAlmostEqual(m['k_si'], legacy['materials'][name]['k_si'], places=6,
                                       msg='conductivity drifted for {}'.format(name))

    def test_lidded_budget_matches_legacy_budget(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_stack(StackSpec(package='lidded', cell_um=50.0),
                               os.path.join(d, 's.stk'))
            for area in (826.0, 91.0):
                a = resistance_budget(_LEGACY, area)['total_K_per_W']
                b = resistance_budget(path, area)['total_K_per_W']
                self.assertAlmostEqual(a, b, places=9)

    def test_spec_budget_agrees_with_the_parsed_file(self):
        """The spec's own lumped budget and the one read back off disk must not diverge."""
        spec = StackSpec(package='direct_die', mr_layer=True)
        with tempfile.TemporaryDirectory() as d:
            path = write_stack(spec, os.path.join(d, 's.stk'))
            parsed = resistance_budget(path, 300.0)['total_K_per_W']
        self.assertAlmostEqual(spec.resistance_budget(300.0)['total_K_per_W'], parsed, places=9)


class TestDirectDie(unittest.TestCase):

    def test_direct_die_has_no_lid_or_die_attach(self):
        spec = StackSpec(package='direct_die', mr_layer=True)
        mats = [mat for _, _, _, mat in spec.package_layers()]
        self.assertNotIn('COPPER', mats)
        self.assertNotIn('SOLDER_TIM', mats)

    def test_pixel_layer_sits_directly_on_the_silicon(self):
        """Nothing may come between the pixel array and the die -- that is what direct-die means."""
        spec = StackSpec(package='direct_die', mr_layer=True)
        self.assertEqual(spec.package_layers()[-1][0], 'MR_PIXELS')

    def test_pixel_layer_is_refused_on_a_lidded_package(self):
        with self.assertRaises(ValueError):
            StackSpec(package='lidded', mr_layer=True)

    def test_direct_die_cuts_the_stack_resistance(self):
        cmp_ = compare_packages(91.0)
        self.assertGreater(cmp_['reduction'], 0.5,
                           'removing solder and a copper lid should more than halve the budget')

    def test_reduction_is_area_independent(self):
        """Every layer is 1/area, so the package's relative benefit cannot depend on die size."""
        a = compare_packages(826.0)['reduction']
        b = compare_packages(91.0)['reduction']
        self.assertAlmostEqual(a, b, places=9)

    def test_path_to_coolant_shrinks_with_burial_depth(self):
        deep = StackSpec(package='direct_die', mr_layer=True, source_depth_um=360.0)
        thin = StackSpec(package='direct_die', mr_layer=True, die_um=100.0,
                         source_depth_um=60.0)
        self.assertLess(thin.path_to_coolant_um()['total_um'],
                        deep.path_to_coolant_um()['total_um'])

    def test_pixel_material_choice_moves_the_budget(self):
        gaas = StackSpec(package='direct_die', mr_layer=True, mr_material='GAAS')
        grease = StackSpec(package='direct_die', mr_layer=True, mr_material='THERMAL_GREASE')
        self.assertLess(gaas.resistance_budget(91.0)['total_K_per_W'],
                        grease.resistance_budget(91.0)['total_K_per_W'])

    def test_unknown_pixel_material_is_refused(self):
        with self.assertRaises(ValueError):
            StackSpec(package='direct_die', mr_layer=True, mr_material='UNOBTAINIUM')


class TestPoweredArray(unittest.TestCase):
    """The array as a die element -- the only arrangement in which burial depth means anything."""

    def test_powered_array_is_a_die_element_with_its_own_floorplan(self):
        text = render_stack_text(StackSpec(package='direct_die', mr_layer=True, mr_powered=True))
        self.assertIn('die MR_ARRAY MR_DIE floorplan "{mr_flp_file}";', text)
        self.assertIn('die MR_DIE :', text)

    def test_powered_array_is_not_also_emitted_as_a_passive_layer(self):
        """Emitting both would put the pixels in the stack twice and double their resistance."""
        text = render_stack_text(StackSpec(package='direct_die', mr_layer=True, mr_powered=True))
        self.assertNotIn('layer MR_PIXELS MR_LAYER ;', text)
        self.assertNotIn('layer MR_LAYER :', text)

    def test_array_sits_between_the_silicon_and_the_sink(self):
        """Order is the whole point: sink on top, pixels, then the die."""
        text = render_stack_text(StackSpec(package='direct_die', mr_layer=True, mr_powered=True))
        stack = text.split('stack:')[1]
        i_sink = stack.index('layer SINK')
        i_mr = stack.index('die MR_ARRAY')
        i_die = stack.index('die PROCESSOR_DIE')
        self.assertLess(i_sink, i_mr)
        self.assertLess(i_mr, i_die)

    def test_unpowered_array_stays_a_passive_layer(self):
        text = render_stack_text(StackSpec(package='direct_die', mr_layer=True))
        self.assertIn('layer MR_PIXELS MR_LAYER ;', text)
        self.assertNotIn('MR_ARRAY', text)

    def test_powering_an_absent_array_is_refused(self):
        with self.assertRaises(ValueError):
            StackSpec(package='direct_die', mr_layer=False, mr_powered=True)

    def test_burial_depth_is_inert_unless_the_array_is_powered(self):
        """The heart of it. With the removal in the die's own source layer the extracted watt
        crosses no silicon, so sweeping the burial depth cannot change what MR achieves."""
        inert = StackSpec(package='direct_die', mr_layer=True)
        powered = StackSpec(package='direct_die', mr_layer=True, mr_powered=True)
        self.assertEqual(inert.path_to_coolant_um()['to_cooling_um'], 0.0)
        self.assertAlmostEqual(powered.path_to_coolant_um()['to_cooling_um'],
                               powered.source_depth_um)

    def test_powered_stack_declares_the_second_floorplan(self):
        spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True)
        self.assertEqual(spec.mr_flp_placeholder(), '{mr_flp_file}')
        self.assertIsNone(StackSpec(package='direct_die', mr_layer=True).mr_flp_placeholder())

    def test_powering_the_array_does_not_change_the_resistance_budget(self):
        """Same material, same thickness, same place -- only the power differs."""
        a = StackSpec(package='direct_die', mr_layer=True).resistance_budget(91.0)
        b = StackSpec(package='direct_die', mr_layer=True,
                      mr_powered=True).resistance_budget(91.0)
        self.assertAlmostEqual(a['total_K_per_W'], b['total_K_per_W'], places=12)


class TestSpecStrings(unittest.TestCase):
    """Spec strings are how the thirteen ``--stack`` drivers reach generated stacks."""

    def test_round_trips_through_a_spec_string(self):
        spec = parse_spec_string('spec:package=direct_die,mr=GAAS,src=120,die=200,cell=100')
        self.assertEqual(spec.package, 'direct_die')
        self.assertTrue(spec.mr_layer)
        self.assertEqual(spec.mr_material, 'GAAS')
        self.assertAlmostEqual(spec.source_depth_um, 120.0)
        self.assertAlmostEqual(spec.die_um, 200.0)
        self.assertAlmostEqual(spec.cell_um, 100.0)

    def test_mr_none_leaves_the_pixel_layer_off(self):
        self.assertFalse(parse_spec_string('spec:package=direct_die,mr=none').mr_layer)

    def test_unknown_key_is_an_error_not_a_silent_no_op(self):
        """A typo'd sweep parameter that quietly does nothing produces N identical results."""
        with self.assertRaises(ValueError):
            parse_spec_string('spec:srcc=120')

    def test_fragment_without_a_value_is_an_error(self):
        with self.assertRaises(ValueError):
            parse_spec_string('spec:package')

    def test_filename_is_deterministic_across_key_order(self):
        a = parse_spec_string('spec:package=direct_die,mr=GAAS,src=120')
        b = parse_spec_string('spec:src=120,mr=GAAS,package=direct_die')
        self.assertEqual(spec_string_filename(a), spec_string_filename(b))

    def test_geometry_change_changes_the_filename(self):
        """Otherwise a sweep would overwrite one file and the solver cache would reuse a matrix."""
        a = parse_spec_string('spec:package=direct_die,src=120')
        b = parse_spec_string('spec:package=direct_die,src=240')
        self.assertNotEqual(spec_string_filename(a), spec_string_filename(b))

    def test_plain_template_names_are_untouched(self):
        self.assertFalse(is_spec_string('skylake'))
        self.assertFalse(is_spec_string('direct_die_mr'))
        self.assertTrue(is_spec_string('spec:package=direct_die'))


class TestRendering(unittest.TestCase):

    def test_placeholders_the_pipeline_fills_are_preserved(self):
        text = render_stack_text(StackSpec(package='direct_die', mr_layer=True))
        for ph in ('{flp_width}', '{flp_height}', '{flp_file}', '{solver_config}',
                   '{output_list}'):
            self.assertIn(ph, text)

    def test_exactly_one_htc_and_one_ambient(self):
        """render_stack_with_sink() rejects anything else, so assert it here rather than there."""
        text = render_stack_text(StackSpec(package='direct_die', mr_layer=True))
        self.assertEqual(text.count('heat transfer coefficient'), 1)
        self.assertEqual(text.count('temperature '), 1)

    def test_no_block_comments_are_emitted(self):
        """3D-ICE's scanner mis-tokenises block comments; the generator must not write any.

        Its comment rules skip ``"*"[^/]`` -- two characters at a time -- so a run of ``*``
        before the closing ``/`` is consumed in pairs and the comment only terminates when that
        run is ODD. An even run swallows the rest of the file, and the parse error surfaces at
        whatever section keyword comes next, nowhere near the cause. This cost an afternoon.
        """
        text = render_stack_text(StackSpec(package='direct_die', mr_layer=True))
        self.assertNotIn('/*', text)

    def test_lexer_guard_rejects_an_even_trailing_star_run(self):
        from HotGauge.thermal.die_stack import _assert_lexer_safe
        _assert_lexer_safe('/* fine */')                      # 1 star: closes
        _assert_lexer_safe('/*** fine ***/')                  # 3 stars: closes
        with self.assertRaises(ValueError):
            _assert_lexer_safe('/**** broken ****/')          # 4+1 = even run: does not close

    def test_legacy_template_survives_the_same_guard(self):
        """skylake.stk gets away with star banners only because all of them have 23. Prove it."""
        from HotGauge.thermal.die_stack import _assert_lexer_safe
        with open(_LEGACY) as f:
            _assert_lexer_safe(f.read())

    def test_conductivity_is_written_in_ice_units(self):
        """1.20e-4 W/(um K) is 120 W/(m K). Writing the SI number here makes silicon an insulator."""
        text = render_stack_text(StackSpec(package='lidded'))
        self.assertIn('0.00012', text)
        self.assertNotIn('thermal conductivity     120', text)


if __name__ == '__main__':
    unittest.main()
