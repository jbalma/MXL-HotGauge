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
                                        DEFAULT_DIE_UM, DEFAULT_SOURCE_DEPTH_UM,
                                        DEFAULT_DIRECT_DIE_UM, DEFAULT_DIRECT_SOURCE_DEPTH_UM)
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


class TestTheDeviceAsItIsBuilt(unittest.TestCase):
    """The stack the part actually is: a cold plate on top of a direct-die chip.

    These are not modelling preferences. The array mounts above the die, the convection control
    keeps the same sink, and the active layer sits at the same depth in both arms. A change that
    breaks one of these makes every photonic-versus-convection number a comparison of two
    different machines, which is the failure this class exists to prevent.
    """

    def test_direct_die_buries_the_active_layer_200_um_down_by_default(self):
        spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True)
        self.assertAlmostEqual(spec.source_depth_um, 200.0)
        self.assertAlmostEqual(spec.source_depth_um, DEFAULT_DIRECT_SOURCE_DEPTH_UM)
        self.assertAlmostEqual(spec.die_um, DEFAULT_DIRECT_DIE_UM)
        above = 0.0
        for layer in spec.die_layers():
            if layer['kind'] == 'source':
                break
            above += layer['height_um']
        self.assertAlmostEqual(above, 200.0, places=6)

    def test_lidded_default_is_untouched_by_the_direct_die_default(self):
        """The historical die must not move; skylake.stk equivalence depends on it."""
        spec = StackSpec(package='lidded')
        self.assertAlmostEqual(spec.die_um, DEFAULT_DIE_UM)
        self.assertAlmostEqual(spec.source_depth_um, DEFAULT_SOURCE_DEPTH_UM)

    def test_photonic_and_convection_differ_in_exactly_one_layer(self):
        """Same sink, same die, same burial depth -- only the 30 um above the silicon changes.

        The comparison is only about the cooler if nothing else moves with it.
        """
        mr = StackSpec(package='direct_die', mr_layer=True, mr_powered=True)
        air = StackSpec(package='direct_die', mr_layer=False)

        self.assertEqual([(l['kind'], l['height_um'], l['material']) for l in mr.die_layers()],
                         [(l['kind'], l['height_um'], l['material']) for l in air.die_layers()])
        self.assertAlmostEqual(mr.source_depth_um, air.source_depth_um)

        mr_pkg, air_pkg = mr.package_layers(), air.package_layers()
        self.assertEqual(len(mr_pkg), len(air_pkg))
        self.assertEqual(mr_pkg[0], air_pkg[0], 'the sink must be identical in both arms')

        differing = [(a, b) for a, b in zip(mr_pkg, air_pkg) if a != b]
        self.assertEqual(len(differing), 1, 'exactly one layer may differ')
        (mr_inst, _, mr_h, mr_mat), (air_inst, _, air_h, air_mat) = differing[0]
        self.assertEqual((mr_inst, air_inst), ('MR_PIXELS', 'TIM'))
        self.assertAlmostEqual(mr_h, air_h, msg='the array must be as thick as the grease it '
                                                'replaces, or the comparison moves the sink')
        self.assertEqual((mr_mat, air_mat), ('GAAS', 'THERMAL_GREASE'))

    def test_the_array_sits_directly_between_the_silicon_and_the_sink(self):
        """Nothing may come between the pixels and the die: that interface IS the device."""
        pkg = StackSpec(package='direct_die', mr_layer=True, mr_powered=True).package_layers()
        self.assertEqual([i for i, _, _, _ in pkg], ['SINK', 'MR_PIXELS'])

    def test_every_die_layer_keeps_a_separator_at_an_awkward_depth(self):
        """A height that renders to six characters must not run into the material name.

        '86.745316SILICON' is a .stk 3D-ICE cannot parse, and our own reader skipped the line
        rather than complaining -- so the failure showed up as a resistance budget quietly
        missing 200 um of silicon. Round burial depths hide it; 137 um does not.
        """
        import re
        for depth in (137.0, 200.0, 0.6745, 63.0):
            spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                             source_depth_um=depth, die_um=depth + 40.0)
            text = render_stack_text(spec)
            # Only the die bodies declare layers by thickness; the stack section names
            # instances instead, and would fail this pattern for an unrelated reason.
            bodies = re.findall(r'^die\s+\w+\s*:\n((?:[ \t]+\S.*\n)+)', text, re.M)
            self.assertTrue(bodies, 'no die body rendered at depth {}'.format(depth))
            for body in bodies:
                for line in body.strip().split('\n'):
                    stripped = line.strip()
                    if not re.match(r'^(layer|source)\s+[0-9.]+\s+\w+\s*;', stripped):
                        self.fail('unparseable die layer at depth {}: {!r}'
                                  .format(depth, stripped))

    def test_the_budget_off_disk_sees_every_layer_at_any_depth(self):
        """The spec's own budget and the one parsed back must agree wherever the source sits."""
        for depth in (360.0, 200.0, 137.0):
            spec = StackSpec(package='direct_die', mr_layer=True,
                             source_depth_um=depth, die_um=depth + 40.0)
            with tempfile.TemporaryDirectory() as d:
                path = write_stack(spec, os.path.join(d, 's.stk'))
                parsed = resistance_budget(path, 300.0)['total_K_per_W']
            self.assertAlmostEqual(spec.resistance_budget(300.0)['total_K_per_W'], parsed,
                                   places=9, msg='depth {}'.format(depth))

    def test_the_sink_slab_can_move_into_the_boundary(self):
        """A cold plate modelled as a die-width column is the 1/area artifact. It must be
        removable so SpreadingSink can carry it with a real overhang instead."""
        keep = StackSpec(package='direct_die', mr_layer=True, mr_powered=True)
        drop = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                         sink_in_stack=False)
        self.assertEqual([i for i, _, _, _ in keep.package_layers()], ['SINK', 'MR_PIXELS'])
        self.assertEqual([i for i, _, _, _ in drop.package_layers()], ['MR_PIXELS'])
        text = render_stack_text(drop)
        self.assertNotIn('SINK_LAYER', text)
        self.assertIn('top heat sink', text, 'the convective boundary must remain')
        self.assertLess(drop.resistance_budget(91.0)['total_K_per_W'],
                        keep.resistance_budget(91.0)['total_K_per_W'])

    def test_dropping_the_slab_is_visible_in_the_stack_name(self):
        """Two stacks that differ only in where the base lives must not share a name -- the
        session cache and every results directory key off it."""
        keep = StackSpec(package='direct_die', mr_layer=True, mr_powered=True)
        drop = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                         sink_in_stack=False)
        self.assertNotEqual(keep.name, drop.name)
        self.assertTrue(drop.name.endswith('_extsink'))

    def test_the_array_still_sits_on_the_silicon_without_the_slab(self):
        """Removing the base must not move the pixels: they are bonded to the die."""
        drop = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                         sink_in_stack=False)
        self.assertEqual([i for i, _, _, _ in drop.package_layers()], ['MR_PIXELS'])
        self.assertAlmostEqual(drop.path_to_coolant_um()['total_um'],
                               drop.source_depth_um + drop.mr_um)

    def test_burial_depth_stays_a_free_parameter(self):
        """Die thinning is an experiment we have to be able to run, not a fixed assumption."""
        for depth in (360.0, 200.0, 100.0, 20.0):
            spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True,
                             source_depth_um=depth, die_um=depth + 40.0)
            self.assertAlmostEqual(spec.source_depth_um, depth)
            self.assertAlmostEqual(spec.path_to_coolant_um()['total_um'], depth + spec.mr_um)


if __name__ == '__main__':
    unittest.main()


class TestGeneratedStackFilenamesAreUnique:
    """Two specs that render different stacks must not share a path in _generated/.

    The readable prefix covers package, die, burial, active thickness, pixel material and grid --
    and nothing else. The boundary flags were invisible to it, so a four-layer package, a
    three-layer one and a one-layer one all wrote to the same file.

    Within one process that is only wasteful. Across the catalogue re-run's concurrent streams it
    is a correctness hazard, and the session cache cannot catch it because it fingerprints the
    file's CONTENTS -- it would faithfully factorise whatever it was handed.
    """

    COLLIDED = ('spec:package=lidded',
                'spec:package=lidded,sink_in_stack=0',
                'spec:package=lidded,sink_in_stack=0,package_in_boundary=1')

    def test_the_three_that_used_to_collide_no_longer_do(self):
        from HotGauge.thermal.die_stack import parse_spec_string, spec_string_filename
        names = [spec_string_filename(parse_spec_string(n)) for n in self.COLLIDED]
        assert len(set(names)) == 3, names

    def test_they_really_do_render_different_stacks(self):
        """Otherwise the test above is pinning a distinction without a difference."""
        from HotGauge.thermal.die_stack import parse_spec_string
        counts = [len(parse_spec_string(n).package_layers()) for n in self.COLLIDED]
        assert counts == [4, 3, 1], counts

    def test_the_spreading_amendment_changes_the_filename(self):
        """--spreading turns spec:X into spec:X,sink_in_stack=0 -- the reachable collision."""
        from HotGauge.thermal.die_stack import (parse_spec_string, spec_string_filename,
                                                stack_for_spreading)
        base = 'spec:package=direct_die,mr=GAAS,src=200,cell=50'
        a = spec_string_filename(parse_spec_string(base))
        b = spec_string_filename(parse_spec_string(stack_for_spreading(base)))
        assert a != b

    def test_the_name_is_stable_and_order_independent(self):
        """A sweep revisiting a geometry must reuse the file, not write a second one."""
        from HotGauge.thermal.die_stack import parse_spec_string, spec_string_filename
        a = spec_string_filename(parse_spec_string(
            'spec:package=direct_die,mr=GAAS,src=200,cell=50'))
        b = spec_string_filename(parse_spec_string(
            'spec:src=200,cell=50,mr=GAAS,package=direct_die'))
        assert a == b

    def test_every_identity_field_actually_moves_the_name(self):
        """A StackSpec field left out of the identity reintroduces the collision silently."""
        from HotGauge.thermal.die_stack import (StackSpec, spec_string_filename,
                                                _SPEC_IDENTITY_FIELDS)
        # direct_die + mr_layer is the only combination the constructor accepts with a pixel
        # layer; the perturbations below are applied to a COPY after construction, so they
        # deliberately bypass that validation -- this is a test about names, not about physics.
        base = StackSpec(package='direct_die', mr_layer=True)
        base_name = spec_string_filename(base)
        VARY = {'package': 'lidded', 'die_um': 401.0, 'source_depth_um': 361.0,
                'source_um': 21.0, 'cell_um': 100.0, 'n_above': 6, 'grading_ratio': 1.7,
                'mr_layer': False, 'mr_powered': True, 'mr_material': 'SI3N4', 'mr_um': 31.0,
                'grease_um': 31.0, 'sink_um': 2001.0, 'spreader_um': 3001.0,
                'solder_um': 201.0, 'sink_in_stack': False, 'package_in_boundary': True,
                'ambient_K': 304.0, 'htc_3dice': 2.5e-7,
                # X4: the storage die and its bond (None = no storage die on the base spec)
                'storage_um': 50.0, 'storage_source_um': 11.0, 'bond_um': 6.0, 'bond_k_si': 51.0}
        for f in _SPEC_IDENTITY_FIELDS:
            assert f in VARY, 'no perturbation defined for identity field {}'.format(f)
            import copy
            other = copy.copy(base)
            setattr(other, f, VARY[f])
            assert spec_string_filename(other) != base_name, f

    def test_a_rendered_spec_lands_at_its_own_filename(self):
        import tempfile, os as _os
        from HotGauge.thermal.die_stack import render_spec_string, parse_spec_string, \
            spec_string_filename
        d = tempfile.mkdtemp()
        for n in self.COLLIDED:
            path = render_spec_string(n, d)
            assert _os.path.basename(path) == spec_string_filename(parse_spec_string(n))
        # ...and all three survive on disk together, which is the actual fix.
        assert len([f for f in _os.listdir(d) if f.endswith('.stk')]) == 3


def test_write_stack_is_atomic_under_concurrency(tmp_path):
    """The generated filename is DETERMINISTIC, so concurrent points share it.

    A plain open(path,'w') truncates before writing, so a reader arriving mid-write gets a
    partial stack. This bit a real sweep: 8 concurrent tier points on one spec produced
    'Expected exactly one "heat transfer coefficient" ... found 0'. That guard caught it by
    luck -- a partial file that still parsed would have been a silently wrong geometry shared by
    the whole sweep.

    Readers must only ever observe a COMPLETE file.
    """
    import threading
    from HotGauge.thermal.die_stack import StackSpec, write_stack, render_stack_text

    spec = StackSpec(package='direct_die')
    out = str(tmp_path / 'shared.stk')
    expected = render_stack_text(spec)
    write_stack(spec, out)                       # seed it so readers always find something

    bad, stop = [], threading.Event()

    def writer():
        while not stop.is_set():
            write_stack(spec, out)

    def reader():
        while not stop.is_set():
            try:
                with open(out) as f:
                    txt = f.read()
            except FileNotFoundError:
                bad.append('reader saw NO FILE -- the rename was not atomic')
                continue
            if txt != expected:
                bad.append('reader saw a partial file: {} of {} bytes'
                           .format(len(txt), len(expected)))

    threads = [threading.Thread(target=writer), threading.Thread(target=reader),
               threading.Thread(target=reader)]
    for t in threads:
        t.start()
    stop.wait(1.5)
    stop.set()
    for t in threads:
        t.join(timeout=10)

    assert not bad, bad[:3]
    # and no temp files left behind
    assert not [p for p in tmp_path.iterdir() if p.name.startswith('.tmp_stack_')]


class TestStorageDie(unittest.TestCase):
    """X4 (§P0.27.4): the gen-3 storage die above the processor die on a stated bond."""

    SPEC = 'spec:package=direct_die,mr=GAAS,src=200,cell=100,sink_in_stack=0,storage=50,bond=5,bondk=50'

    def test_storage_die_is_a_third_die_element_between_the_array_and_the_silicon(self):
        text = render_stack_text(parse_spec_string(self.SPEC))
        stack = text[text.index('stack:'):text.index('// ---------------------------- Analysis')]
        lines = [l.strip() for l in stack.splitlines() if l.strip().startswith(('die', 'layer'))]
        self.assertIn('die MR_ARRAY MR_DIE floorplan "{mr_flp_file}";', lines)
        self.assertIn('die STORAGE_DIE STORAGE floorplan "{storage_flp_file}";', lines)
        self.assertIn('layer BOND BOND_LAYER ;', lines)
        i = [n for n, l in enumerate(lines) if l.startswith('die')]
        self.assertEqual([lines[n].split()[1] for n in i], ['MR_ARRAY', 'STORAGE_DIE', 'PROCESSOR_DIE'])
        self.assertLess(lines.index('die STORAGE_DIE STORAGE floorplan "{storage_flp_file}";'),
                        lines.index('layer BOND BOND_LAYER ;'))

    def test_bond_conductivity_is_the_stated_one(self):
        text = render_stack_text(parse_spec_string(self.SPEC.replace('bondk=50', 'bondk=5')))
        block = text[text.index('material BOND :'):]
        self.assertIn('thermal conductivity     5e-06', block)      # 5 W/(m K) in W/(um K)

    def test_default_stack_carries_no_storage_placeholder(self):
        text = render_stack_text(parse_spec_string('spec:package=direct_die,mr=GAAS,src=200,cell=50'))
        self.assertNotIn('{storage_flp_file}', text)
        self.assertNotIn('STORAGE', text)

    def test_storage_die_changes_the_identity_and_the_budget(self):
        a = parse_spec_string(self.SPEC)
        b = parse_spec_string(self.SPEC.replace('bondk=50', 'bondk=5'))
        c = parse_spec_string(self.SPEC.replace(',storage=50,bond=5,bondk=50', ''))
        self.assertNotEqual(spec_string_filename(a), spec_string_filename(b))
        self.assertNotEqual(spec_string_filename(a), spec_string_filename(c))
        names = [r['name'] for r in a.resistance_budget(101.1)['rows']]
        self.assertIn('STORAGE', names)
        self.assertIn('BOND', names)
        self.assertGreater(a.resistance_budget(101.1)['total_K_per_W'], c.resistance_budget(101.1)['total_K_per_W'])
        self.assertGreater(b.resistance_budget(101.1)['total_K_per_W'], a.resistance_budget(101.1)['total_K_per_W'])

    def test_storage_die_is_refused_on_a_lidded_package(self):
        with self.assertRaises(ValueError):
            parse_spec_string('spec:package=lidded,storage=50')
