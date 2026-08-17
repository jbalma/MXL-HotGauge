"""Tests for the 3D stack builder (HotGauge.thermal.stack_models).

No 3D-ICE needed: these check that the emitted .stk is structurally what 3D-ICE requires and
that the memory die lands in the heat path, which is the modelling decision that matters.
"""
import os

import pytest

from HotGauge.thermal.stack_models import (memory_floorplan, render_stacked_memory_template,
                                           split_layer_temps)
from HotGauge.thermal import get_stack_template


def _write_logic_flp(tmp_path):
    p = tmp_path / 'logic.flp'
    p.write_text('\n'.join(['blkA\t1000.0\t500.0\t0.0\t0.0',
                            'blkB\t1000.0\t500.0\t1000.0\t0.0',
                            'blkC\t2000.0\t500.0\t0.0\t500.0']) + '\n')
    return str(p)


def test_memory_floorplan_tiles_the_logic_footprint(tmp_path):
    logic = _write_logic_flp(tmp_path)
    out, names = memory_floorplan(logic, str(tmp_path / 'mem.flp'), n_x=4, n_y=2)
    assert len(names) == 8
    text = open(out).read()
    # 3D-ICE floorplan syntax, not the HotSpot tab-separated form -- both are called .flp and
    # only one of them parses, which cost a run to discover.
    assert 'position' in text and 'dimension' in text and 'power values' in text
    import re
    pos = [(float(a), float(b)) for a, b in re.findall(r'position ([\d.]+), ([\d.]+)', text)]
    dim = [(float(a), float(b)) for a, b in re.findall(r'dimension ([\d.]+), ([\d.]+)', text)]
    # Banks must cover the die exactly: 3D-ICE stacks share one footprint.
    assert max(x + w for (x, _), (w, _) in zip(pos, dim)) == pytest.approx(2000.0)
    assert max(y + h for (_, y), (_, h) in zip(pos, dim)) == pytest.approx(1000.0)


def test_memory_blocks_are_named_so_the_layers_can_be_told_apart(tmp_path):
    _, names = memory_floorplan(_write_logic_flp(tmp_path), str(tmp_path / 'm.flp'), 2, 2)
    assert all(n.startswith('MEM_') for n in names)
    logic, memory = split_layer_temps({'iALU_0': [350.0], 'MEM_r0c0': [360.0]})
    assert list(logic) == ['iALU_0'] and list(memory) == ['MEM_r0c0']


def test_stacked_template_puts_memory_between_the_sink_and_the_logic(tmp_path):
    """The memory must sit in the logic's heat path -- that is the case worth studying, and
    getting the order wrong would quietly model the easy arrangement instead."""
    out = render_stacked_memory_template(get_stack_template('skylake'),
                                         str(tmp_path / 'stacked.stk'),
                                         str(tmp_path / 'mem.flp'))
    text = open(out).read()
    stack_section = text[text.index('/*********************** Stack ***'):]
    mem_at = stack_section.index('die MEMORY_DIE0')
    logic_at = stack_section.index('die PROCESSOR_DIE')
    sink_at = stack_section.index('layer SINK')
    assert sink_at < mem_at < logic_at, 'memory must be above the logic die'
    assert 'die MEM :' in text and 'layer BOND0 BOND_LAYER' in text


def test_stacked_template_leaves_the_logic_placeholders_for_the_stock_machinery(tmp_path):
    """Everything downstream fills {flp_file} and friends; if the builder consumed them the
    stock ICESim path would break."""
    out = render_stacked_memory_template(get_stack_template('skylake'),
                                         str(tmp_path / 's.stk'), str(tmp_path / 'mem.flp'))
    text = open(out).read()
    for placeholder in ('{flp_file}', '{flp_width}', '{flp_height}', '{solver_config}',
                        '{output_list}'):
        assert placeholder in text
    # ...while the memory floorplan is already concrete.
    assert os.path.abspath(str(tmp_path / 'mem.flp')) in text


def test_refuses_to_stack_twice(tmp_path):
    first = render_stacked_memory_template(get_stack_template('skylake'),
                                           str(tmp_path / 'a.stk'), str(tmp_path / 'm.flp'))
    with pytest.raises(ValueError):
        render_stacked_memory_template(first, str(tmp_path / 'b.stk'), str(tmp_path / 'm.flp'))


def test_multi_die_stack_gives_every_die_distinct_block_names(tmp_path):
    """Shared names would make six dies of an eight-high stack vanish into the seventh when the
    Tflp files are merged, with no error anywhere."""
    from HotGauge.thermal.stack_models import (memory_stack_floorplans,
                                               memory_output_instructions)
    logic = _write_logic_flp(tmp_path)
    paths, by_die, every = memory_stack_floorplans(logic, str(tmp_path), n_dies=4, n_x=2, n_y=2)
    assert len(paths) == 4 and len(every) == 16
    assert len(set(every)) == 16, 'block names collide across dies'
    assert by_die[0][0].startswith('MEM0_') and by_die[3][0].startswith('MEM3_')
    # ...and one output instruction per die, or the extra dies report nothing at all.
    outs = memory_output_instructions(4)
    assert len(outs) == 4 and 'MEMORY_DIE3' in outs[3]
    assert len(set(outs)) == 4


def test_multi_die_stack_places_every_die_above_the_logic(tmp_path):
    from HotGauge.thermal.stack_models import memory_stack_floorplans
    logic = _write_logic_flp(tmp_path)
    paths, _, _ = memory_stack_floorplans(logic, str(tmp_path), n_dies=4, n_x=2, n_y=2)
    out = render_stacked_memory_template(get_stack_template('skylake'),
                                         str(tmp_path / 'stack4.stk'), paths, n_dies=4)
    section = open(out).read()
    section = section[section.index('/*********************** Stack ***'):]
    logic_at = section.index('die PROCESSOR_DIE')
    for i in range(4):
        assert section.index('die MEMORY_DIE{}'.format(i)) < logic_at
    assert section.count('layer BOND') == 4


def test_floorplan_count_must_match_die_count(tmp_path):
    from HotGauge.thermal.stack_models import memory_stack_floorplans
    paths, _, _ = memory_stack_floorplans(_write_logic_flp(tmp_path), str(tmp_path),
                                          n_dies=2, n_x=2, n_y=2)
    with pytest.raises(ValueError):
        render_stacked_memory_template(get_stack_template('skylake'),
                                       str(tmp_path / 'x.stk'), paths, n_dies=4)


def test_cell_coarsening_rewrites_the_grid_and_is_labelled(tmp_path):
    """Deep stacks need a coarser grid than the template's 50 um -- SuperLU cannot factorise a
    9-die stack at 50 um. The override must be visible in the .stk, because a coarsened run's
    peak temperature is not comparable with a fine one's."""
    from HotGauge.thermal.stack_models import memory_stack_floorplans
    paths, _, _ = memory_stack_floorplans(_write_logic_flp(tmp_path), str(tmp_path),
                                          n_dies=2, n_x=2, n_y=2)
    out = render_stacked_memory_template(get_stack_template('skylake'),
                                         str(tmp_path / 'coarse.stk'), paths,
                                         n_dies=2, cell_um=100.0)
    text = open(out).read()
    assert 'cell length 100, width 100;' in text
    assert 'COARSENED' in text
    assert 'cell length 50' not in text


def test_coarsening_a_template_without_a_cell_line_is_an_error(tmp_path):
    bad = tmp_path / 'nocell.stk'
    bad.write_text('die PROCESSOR_DIE IC floorplan "{flp_file}";\n'
                   '/*********************** Heat Sink ***********************/\n'
                   '/*********************** Dies ***********************/\n'
                   '/*********************** Stack ***********************/\n')
    with pytest.raises(ValueError):
        render_stacked_memory_template(str(bad), str(tmp_path / 'x.stk'),
                                       [str(tmp_path / 'm.flp')], n_dies=1, cell_um=100.0)
