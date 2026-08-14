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
    rows = [l.split('\t') for l in open(out).read().strip().split('\n')]
    # Banks must cover the die exactly: 3D-ICE stacks share one footprint.
    right = max(float(r[1]) + float(r[3]) for r in rows)
    top = max(float(r[2]) + float(r[4]) for r in rows)
    assert right == pytest.approx(2000.0)
    assert top == pytest.approx(1000.0)


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
    mem_at = stack_section.index('die MEMORY_DIE')
    logic_at = stack_section.index('die PROCESSOR_DIE')
    sink_at = stack_section.index('layer SINK')
    assert sink_at < mem_at < logic_at, 'memory must be above the logic die'
    assert 'die MEM :' in text and 'layer BOND BOND_LAYER' in text


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
