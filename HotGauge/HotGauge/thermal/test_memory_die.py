"""§P0.44: the memory die -- floorplans, conductivities, the refresh fixed point, and the
two guarantees the driver relies on (bank names survive the McPAT translation and are not
zeroed; the union floorplan counts their watts)."""
import os
import re
import math

import numpy as np
import pytest

from HotGauge.thermal import memory_die as md
from HotGauge.thermal.memory_die import (via_field_effective_k, lumped_stack, bank_blocks,
                                         build_memory_split, build_memory_beside, MemoryDie,
                                         refresh_fixed_point, MEM_PATTERN, footprint_um)

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
REF = os.path.join(_REPO, 'examples', 'floorplans', 'outputs', 'skylake7nm_34core_3_3D-ICE_template.flp')
needs_ref = pytest.mark.skipif(not os.path.isfile(REF), reason='reference floorplan not on disk')


def _mini_ref(tmp_path):
    p = tmp_path / 'ref.flp'
    p.write_text('A_0 :\n\tposition 0, 0 ;\n\tdimension 1000, 1000 ;\n\tpower values {powers[A_0]};\n'
                 'L2_0 :\n\tposition 1000, 0 ;\n\tdimension 950, 1000 ;\n\tpower values {powers[L2_0]};\n')
    return str(p)


# --- conductivities ---------------------------------------------------------------------------
def test_via_field_is_a_parallel_copper_path():
    k, f = via_field_effective_k(0.1, 10000, 5.0, 101.68)
    assert 0.8 < k < 0.9 and 1.8e-3 < f < 2.0e-3
    k0, f0 = via_field_effective_k(0.1, 0, 5.0, 101.68)
    assert k0 == 0.1 and f0 == 0.0


def test_via_field_refuses_more_copper_than_die():
    with pytest.raises(ValueError):
        via_field_effective_k(0.1, 10 ** 9, 50.0, 1.0)


def test_lumped_stack_is_series_equivalent_and_one_die_is_silicon():
    t1, k1 = lumped_stack(1)
    assert t1 == 50.0 and k1 == pytest.approx(120.0)
    t8, k8 = lumped_stack(8, bond_um=5.0, k_bond=5.0)
    assert t8 == 435.0
    # 8 x 50/120 + 7 x 5/5 = 3.33 + 7.0 -> 435 / 10.33
    assert k8 == pytest.approx(435.0 / (8 * 50 / 120.0 + 7 * 5 / 5.0), rel=1e-9)
    assert lumped_stack(8, k_bond=50.0)[1] > k8          # better bonds, more conductive stack


# --- floorplans -------------------------------------------------------------------------------
def test_bank_names_match_the_pattern_and_nothing_mcpat_or_no_power_knows():
    from HotGauge.configuration.power_model import is_no_power_unit
    from HotGauge.power.mcpat import rename_mcpat_units_to_ICE_units
    from HotGauge.power.traces import BasicPowerTrace
    banks = bank_blocks(1000, 1000, 2, 2)
    names = [b[0] for b in banks]
    assert all(re.match(MEM_PATTERN, n) for n in names)
    assert not any(is_no_power_unit(n) for n in names)
    tr = BasicPowerTrace({n: np.array([1.0]) for n in names}, 1.0)
    out = rename_mcpat_units_to_ICE_units(tr, True)
    assert set(out.powers) == set(names)                 # pass through unchanged


def test_banks_tile_the_footprint_exactly():
    banks = bank_blocks(12400, 8200, 4, 4)
    assert len(banks) == 16
    assert max(b[1] + b[3] for b in banks) == pytest.approx(12400)
    assert max(b[2] + b[4] for b in banks) == pytest.approx(8200)
    assert sum(b[3] * b[4] for b in banks) == pytest.approx(12400 * 8200)


def test_split_writes_the_gen3_layout_with_placeholders(tmp_path):
    meta = build_memory_split(_mini_ref(tmp_path), str(tmp_path / 'split'), n_x=2, n_y=1)
    comp = open(meta['compute_template']).read()
    stor = open(meta['storage_template']).read()
    uni = open(meta['union_reference']).read()
    assert '{powers[A_0]}' in comp and '{powers[L2_0]}' in comp      # caches STAY on the compute die
    assert '{powers[MEM_r0c0]}' in stor and '{powers[MEM_r0c1]}' in stor
    assert 'power values 0' not in stor
    assert 'A_0 :' in uni and 'MEM_r0c1 :' in uni
    assert meta['footprint_um'] == [2000.0, 1000.0] and meta['n_banks'] == 2


def test_beside_puts_the_banks_right_of_the_die_behind_a_bare_gap(tmp_path):
    meta = build_memory_beside(_mini_ref(tmp_path), str(tmp_path / 'b'), gap_um=500, n_x=1, n_y=1)
    from HotGauge.thermal.ICE import Floorplan
    flp = Floorplan.from_file(meta['floorplan'])
    by = {e.name: e for e in flp.elements}
    assert by['MEM_r0c0'].minx == pytest.approx(2000 + 500)
    assert meta['footprint_um'] == [4500.0, 1000.0]
    assert meta['gap_um'] == 500


# --- the memory die in the solve --------------------------------------------------------------
def _die(n_dies=8, w=3.0):
    return MemoryDie(['MEM_r0c0', 'MEM_r0c1'], area_mm2=100.0, n_dies=n_dies, w_per_die=w)


def test_floor_power_is_dies_times_watts_and_split_evenly():
    d = _die()
    assert d.floor_W == pytest.approx(24.0)
    fp = d.floor_powers()
    assert fp['MEM_r0c0'] == pytest.approx(12.0) and fp['MEM_r0c1'] == pytest.approx(12.0)


def test_inject_adds_the_banks_by_name_and_changes_nothing_else():
    from HotGauge.power.traces import BasicPowerTrace
    d = _die()
    tr = BasicPowerTrace({'Core0/ALU': np.array([1.0, 2.0])}, 1.0)
    out = d.inject(tr)
    assert list(out.powers['Core0/ALU']) == [1.0, 2.0]
    assert out.powers['MEM_r0c0'].shape == (2,) and out.powers['MEM_r0c0'][0] == pytest.approx(12.0)
    assert 'MEM_r0c0' not in tr.powers                    # a copy, not an edit


def test_bank_names_are_refused_if_they_do_not_match():
    with pytest.raises(ValueError):
        MemoryDie(['MEMORY0'], area_mm2=100.0)


def test_report_separates_breakpoint_from_limit_and_reads_the_multiplier():
    d = _die()
    temps = {'MEM_r0c0': np.array([340.0]), 'MEM_r0c1': np.array([370.0]), 'cALU_0': np.array([365.0])}
    r = d.report(temps)
    assert r['mem_n_banks_read'] == 2 and r['mem_n_over_break'] == 1 and r['mem_n_over_limit'] == 1
    assert r['mem_zone_max_C'] == pytest.approx(370.0 - 273.15)
    assert r['mem_refresh_mult_max'] > 2.0 and r['mem_calibrated'] is False
    assert r['mem_power_W'] > r['mem_floor_W']


def test_refresh_fixed_point_converges_in_one_pass_below_the_breakpoint():
    from HotGauge.power.traces import BasicPowerTrace
    d = _die()
    base = BasicPowerTrace({'X': np.array([1.0])}, 1.0)
    calls = []

    def solve(tr):
        calls.append(tr)
        return {'diverged': False, 'temp_trace': {'MEM_r0c0': np.array([330.0]), 'MEM_r0c1': np.array([335.0])},
                'power_trace': tr}
    res = refresh_fixed_point(solve, base, d)
    assert len(calls) == 1 and res['mem_converged'] and not res['mem_diverged']
    assert res['mem']['mem_refresh_mult_max'] == 1.0
    assert res['power_trace'].powers['MEM_r0c0'][0] == pytest.approx(12.0)


def test_refresh_runaway_is_its_own_divergence():
    from HotGauge.power.traces import BasicPowerTrace
    d = _die()
    base = BasicPowerTrace({'X': np.array([1.0])}, 1.0)
    R = 3.0     # K/W: 24 W -> 365 K, above the step -> runs away (the §P0.44 arithmetic)

    def solve(tr):
        P = sum(float(np.ravel(tr.powers[n])[0]) for n in d.names)
        T = 293.0 + R * P
        return {'diverged': False, 'temp_trace': {n: np.array([T]) for n in d.names}, 'power_trace': tr}
    res = refresh_fixed_point(solve, base, d, max_iter=20)
    assert res['diverged'] and res['mem_diverged'] and 'refresh runaway' in res['diverged_reason']
    # the same die with a 1 K/W path holds at the floor
    R = 1.0
    res2 = refresh_fixed_point(solve, base, d, max_iter=20)
    assert not res2['diverged'] and res2['mem']['mem_refresh_mult_max'] == 1.0


def test_a_compute_runaway_is_reported_as_the_compute_dies_not_the_memorys():
    from HotGauge.power.traces import BasicPowerTrace
    d = _die()
    base = BasicPowerTrace({'X': np.array([1.0])}, 1.0)
    res = refresh_fixed_point(lambda tr: {'diverged': True, 'temp_trace': {}, 'diverged_reason': 'leakage'}, base, d)
    assert res['diverged'] and not res['mem_diverged'] and res['diverged_reason'] == 'leakage'


# --- the stack --------------------------------------------------------------------------------
def test_stack_spec_states_the_storage_conductivity_only_when_asked():
    from HotGauge.thermal.die_stack import StackSpec, render_stack_text, spec_identity, parse_spec_string
    a = StackSpec(package='direct_die', mr_layer=True, mr_powered=True, storage_um=50.0)
    b = StackSpec(package='direct_die', mr_layer=True, mr_powered=True, storage_um=435.0, storage_k_si=42.1)
    ta, tb = render_stack_text(a), render_stack_text(b)
    assert 'STORAGE_SI' not in ta and 'material STORAGE_SI' in tb
    assert 'thermal conductivity     4.21e-05' in tb
    assert spec_identity(a) == spec_identity(StackSpec(package='direct_die', mr_layer=True, mr_powered=True, storage_um=50.0))
    assert 'storage_k_si' not in spec_identity(a) and 'storage_k_si=42.1' in spec_identity(b)
    c = parse_spec_string('spec:package=direct_die,mr=GAAS,twosink=1,storage=435,storagek=42.1')
    assert c.storage_k_si == 42.1 and 'STORAGE_SI' in render_stack_text(c)
    with pytest.raises(ValueError):
        StackSpec(package='direct_die', mr_layer=True, mr_powered=True, storage_um=50.0, storage_k_si=0.0)


@needs_ref
def test_union_floorplan_counts_the_banks_watts(tmp_path):
    from HotGauge.thermal.leakage_feedback import die_power_of_trace
    from HotGauge.thermal.ICE import Floorplan
    meta = build_memory_split(REF, str(tmp_path / 'split'))
    assert meta['n_banks'] == 16 and meta['n_compute_blocks'] == 1126
    assert meta['footprint_um'] == [12400.0, 8200.0]
    d = MemoryDie(meta['bank_names'], meta['footprint_mm2'], n_dies=8, w_per_die=3.0)
    from HotGauge.power.traces import BasicPowerTrace
    # a trace with ONLY the banks (plus the two keys the McPAT translation insists on)
    tr = d.inject(BasicPowerTrace({'IMC': np.array([0.0]), 'Processor/Total L3s': np.array([0.0])}, 1.0))
    p_union = die_power_of_trace(tr, meta['union_reference'], 7, num_cores=34)
    p_comp = die_power_of_trace(tr, meta['compute_template'], 7, num_cores=34)
    # the extra-units model adds the IO / SoC blocks' constant power on both; the banks' 24 W is the difference
    assert p_union - p_comp == pytest.approx(24.0, abs=1e-6) and p_comp < 2.0
    assert len(Floorplan.from_file(meta['union_reference']).elements) == 1126 + 16
