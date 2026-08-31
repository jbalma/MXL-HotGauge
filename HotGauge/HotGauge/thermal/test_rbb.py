"""Tests for the RBB placement policy (HotGauge.thermal.rbb).

No 3D-ICE and no floorplan file for the arithmetic: ``block_areas_mm2`` takes a dict so the
redistribution can be checked exactly. The last group does load the shipped 34-core floorplan,
because the recipient set is a claim about *that* floorplan and a synthetic one cannot test it.
"""
import os

import numpy as np
import pytest

from HotGauge.power import BasicPowerTrace
from HotGauge.thermal.rbb import (amortize_rbb, rbb_recipients, split_block_name,
                                  block_areas_mm2, EXEC_UNIT_STEMS, RBB_POLICIES)

_FLP = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'examples', 'floorplans',
                    'outputs', 'skylake7nm_34core_3_3D-ICE.flp')

# One core: a 1 mm^2 iALU, a 3 mm^2 FPU, and a bus with all the power on a sliver.
AREAS = {'RBB_0': 0.002, 'iALU_0': 1.0, 'FPUs_0': 3.0, 'DCache_0': 5.0}
UNITS = {'Core0/Execution Unit/Results Broadcast Bus': 'RBB_0',
         'Core0/Execution Unit/Integer ALUs': 'iALU_0',
         'Core0/Execution Unit/Floating Point Units': 'FPUs_0',
         'Core0/Load Store Unit/Data Cache': 'DCache_0'}
NAME_MAP = lambda u: UNITS.get(u)


def _trace(rbb=4.0, ialu=1.0, fpu=1.0, dcache=2.0, n=1):
    return BasicPowerTrace({
        'Core0/Execution Unit/Results Broadcast Bus': np.full(n, rbb),
        'Core0/Execution Unit/Integer ALUs': np.full(n, ialu),
        'Core0/Execution Unit/Floating Point Units': np.full(n, fpu),
        'Core0/Load Store Unit/Data Cache': np.full(n, dcache),
    }, 1.0e-3)


# ---------------------------------------------------------------------------
# Name splitting and recipient selection
# ---------------------------------------------------------------------------
def test_split_block_name():
    assert split_block_name('iALU_7') == ('iALU', 7)
    assert split_block_name('L2Pred_33') == ('L2Pred', 33)
    assert split_block_name('IMC') == ('IMC', None)
    assert split_block_name('AVX_FPU') == ('AVX_FPU', None)


def test_recipients_are_exec_unit_blocks_of_the_same_core():
    r = rbb_recipients({'iALU_0': 1.0, 'FPUs_0': 3.0, 'iALU_1': 1.0, 'DCache_0': 5.0})
    assert set(r) == {0, 1}
    assert set(r[0]) == {'iALU_0', 'FPUs_0'}       # DCache is not an execution unit
    assert set(r[1]) == {'iALU_1'}


def test_lsq_span_adds_the_queues():
    areas = {'iALU_0': 1.0, 'LoadQ_0': 0.5, 'StoreQ_0': 0.5}
    assert set(rbb_recipients(areas, span='exec')[0]) == {'iALU_0'}
    assert set(rbb_recipients(areas, span='exec+lsq')[0]) == {'iALU_0', 'LoadQ_0', 'StoreQ_0'}


def test_unknown_span_rejected():
    with pytest.raises(ValueError):
        rbb_recipients({'iALU_0': 1.0}, span='everything')


def test_parent_beside_child_is_refused():
    """``regs`` and ``iRF`` in one floorplan would count that area twice in the weights."""
    with pytest.raises(ValueError, match='twice'):
        rbb_recipients({'regs_0': 4.0, 'iRF_0': 2.0, 'fpRF_0': 2.0})


# ---------------------------------------------------------------------------
# The redistribution itself
# ---------------------------------------------------------------------------
def test_stock_is_a_no_op_and_returns_the_same_objects():
    tr, leak = _trace(), {'Core0/Execution Unit/Results Broadcast Bus': 0.5}
    out, out_leak, meta = amortize_rbb(tr, AREAS, policy='stock', leakage_ref=leak)
    assert out is tr and out_leak is leak
    assert meta['policy'] == 'stock' and meta['moved_W'] == 0.0


def test_bad_policy_rejected():
    with pytest.raises(ValueError):
        amortize_rbb(_trace(), AREAS, policy='cap')


def test_power_moves_in_proportion_to_area():
    out, _, meta = amortize_rbb(_trace(rbb=4.0, ialu=1.0, fpu=1.0), AREAS,
                                policy='amortized', name_map=NAME_MAP)
    p = out.powers
    # recipients are 1 and 3 mm^2, so the 4 W bus lands as 1 W and 3 W
    assert p['Core0/Execution Unit/Results Broadcast Bus'] == pytest.approx([0.0])
    assert p['Core0/Execution Unit/Integer ALUs'] == pytest.approx([2.0])
    assert p['Core0/Execution Unit/Floating Point Units'] == pytest.approx([4.0])
    assert p['Core0/Load Store Unit/Data Cache'] == pytest.approx([2.0])   # not a recipient
    assert meta['moved_W'] == pytest.approx(4.0)


def test_total_power_is_conserved_per_timestep():
    tr = BasicPowerTrace({
        'Core0/Execution Unit/Results Broadcast Bus': np.array([1.0, 2.0, 3.0]),
        'Core0/Execution Unit/Integer ALUs': np.array([1.0, 1.0, 1.0]),
        'Core0/Execution Unit/Floating Point Units': np.array([2.0, 2.0, 2.0]),
        'Core0/Load Store Unit/Data Cache': np.array([1.0, 1.0, 1.0]),
    }, 1.0e-3)
    out, _, _ = amortize_rbb(tr, AREAS, policy='amortized', name_map=NAME_MAP)
    before = np.sum([np.asarray(v) for v in tr.powers.values()], axis=0)
    after = np.sum([np.asarray(v) for v in out.powers.values()], axis=0)
    assert after == pytest.approx(before)


def test_time_varying_bus_is_distributed_step_by_step():
    tr = BasicPowerTrace({
        'Core0/Execution Unit/Results Broadcast Bus': np.array([4.0, 8.0]),
        'Core0/Execution Unit/Integer ALUs': np.array([0.0, 0.0]),
        'Core0/Execution Unit/Floating Point Units': np.array([0.0, 0.0]),
        'Core0/Load Store Unit/Data Cache': np.array([0.0, 0.0]),
    }, 1.0e-3)
    out, _, _ = amortize_rbb(tr, AREAS, policy='amortized', name_map=NAME_MAP)
    assert out.powers['Core0/Execution Unit/Integer ALUs'] == pytest.approx([1.0, 2.0])
    assert out.powers['Core0/Execution Unit/Floating Point Units'] == pytest.approx([3.0, 6.0])


def test_amortization_is_idempotent():
    once, _, _ = amortize_rbb(_trace(), AREAS, policy='amortized', name_map=NAME_MAP)
    twice, _, meta2 = amortize_rbb(once, AREAS, policy='amortized', name_map=NAME_MAP)
    for u, v in once.powers.items():
        assert twice.powers[u] == pytest.approx(v)
    assert meta2['moved_W'] == pytest.approx(0.0)


def test_leakage_reference_moves_with_the_power():
    """`[!]` The whole point: rescale_trace rebuilds power as series - leak + leak*scale(T).

    Zeroing the bus's series while leaving its baseline leakage behind re-injects the bus --
    with a NEGATIVE power below T_ref -- so the reference has to move too.
    """
    leak = {'Core0/Execution Unit/Results Broadcast Bus': 2.0,
            'Core0/Execution Unit/Integer ALUs': 0.1,
            'Core0/Execution Unit/Floating Point Units': 0.1}
    _, out_leak, meta = amortize_rbb(_trace(), AREAS, policy='amortized',
                                     leakage_ref=leak, name_map=NAME_MAP)
    assert out_leak['Core0/Execution Unit/Results Broadcast Bus'] == pytest.approx(0.0)
    assert out_leak['Core0/Execution Unit/Integer ALUs'] == pytest.approx(0.1 + 0.5)
    assert out_leak['Core0/Execution Unit/Floating Point Units'] == pytest.approx(0.1 + 1.5)
    assert meta['moved_leakage_W'] == pytest.approx(2.0)
    assert leak['Core0/Execution Unit/Results Broadcast Bus'] == 2.0   # input not mutated


def test_power_is_never_silently_dropped():
    """A core with a bus and no execution units is an error, not a skip."""
    areas = {'RBB_0': 0.002, 'DCache_0': 5.0}
    tr = BasicPowerTrace({'Core0/Execution Unit/Results Broadcast Bus': np.array([4.0]),
                          'Core0/Load Store Unit/Data Cache': np.array([2.0])}, 1.0e-3)
    with pytest.raises(ValueError, match='must not be dropped'):
        amortize_rbb(tr, areas, policy='amortized', name_map=NAME_MAP)


def test_a_trace_with_no_bus_is_an_error_not_a_no_op():
    """Silently doing nothing is how a policy flag becomes a lie in a results table."""
    tr = BasicPowerTrace({'Core0/Execution Unit/Integer ALUs': np.array([1.0])}, 1.0e-3)
    with pytest.raises(ValueError, match='silent no-op'):
        amortize_rbb(tr, AREAS, policy='amortized', name_map=NAME_MAP)


def test_each_core_keeps_its_own_bus_power():
    areas = {'RBB_0': 0.002, 'iALU_0': 1.0, 'RBB_1': 0.002, 'iALU_1': 1.0}
    nm = {'Core0/Execution Unit/Results Broadcast Bus': 'RBB_0',
          'Core0/Execution Unit/Integer ALUs': 'iALU_0',
          'Core1/Execution Unit/Results Broadcast Bus': 'RBB_1',
          'Core1/Execution Unit/Integer ALUs': 'iALU_1'}
    tr = BasicPowerTrace({k: np.array([4.0 if 'Broadcast' in k else 0.0]) for k in nm}, 1.0e-3)
    tr.powers['Core1/Execution Unit/Results Broadcast Bus'] = np.array([8.0])
    out, _, _ = amortize_rbb(tr, areas, policy='amortized', name_map=nm.get)
    assert out.powers['Core0/Execution Unit/Integer ALUs'] == pytest.approx([4.0])
    assert out.powers['Core1/Execution Unit/Integer ALUs'] == pytest.approx([8.0])


# ---------------------------------------------------------------------------
# Against the shipped 34-core floorplan -- the recipient set is a claim about THIS die
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.path.exists(_FLP), reason='shipped floorplan not present')
def test_shipped_floorplan_recipient_set():
    areas = block_areas_mm2(_FLP)
    r = rbb_recipients(areas)
    assert len(r) == 34, 'one recipient group per core'
    stems = {split_block_name(b)[0] for blocks in r.values() for b in blocks}
    # the tiler places the CHILDREN of regs and iSched, never the parents; AVXs is dropped
    # because this pipeline forces it to zero power (see rbb_recipients).
    assert stems == {'cALU', 'iALU', 'FPUs', 'iRF', 'fpRF', 'iWin', 'fpiWin', 'ROB'}
    assert 'AVXs_0' in areas and 'AVXs_0' not in r[0]
    n = sum(len(b) for b in r.values())
    assert n == 34 * 8 == 272, (
        'docs/evidence/rbb_amortization.json used 204 because it named regs and iSched, which '
        'this floorplan subdivides -- so it silently excluded the scheduler blocks')


@pytest.mark.skipif(not os.path.exists(_FLP), reason='shipped floorplan not present')
def test_shipped_floorplan_amortized_density_is_far_below_the_placed_one():
    """Not a claim that 53 W/mm^2 is unphysical -- p99 on this die is 64. Just the size."""
    areas = block_areas_mm2(_FLP)
    units = {'Core{}/Execution Unit/Results Broadcast Bus'.format(i): 'RBB_{}'.format(i)
             for i in range(34)}
    stem_to_unit = {'cALU': 'Complex ALUs', 'iALU': 'Integer ALUs',
                    'FPUs': 'Floating Point Units',
                    'iRF': 'Register Files/Integer RF', 'fpRF': 'Register Files/Floating Point RF',
                    'iWin': 'Instruction Scheduler/Instruction Window',
                    'fpiWin': 'Instruction Scheduler/FP Instruction Window',
                    'ROB': 'Instruction Scheduler/ROB'}
    for i in range(34):
        for stem, tail in stem_to_unit.items():
            units['Core{}/Execution Unit/{}'.format(i, tail)] = '{}_{}'.format(stem, i)
    tr = BasicPowerTrace({u: np.array([0.1 if 'Broadcast' in u else 1.0]) for u in units}, 1e-3)
    _, _, meta = amortize_rbb(tr, areas, policy='amortized', name_map=units.get)
    assert meta['n_donor_units'] == 34
    assert meta['n_recipient_blocks'] == 272
    assert meta['density_as_placed_W_per_mm2'] > 40.0
    assert meta['density_amortized_W_per_mm2'] < 0.5
