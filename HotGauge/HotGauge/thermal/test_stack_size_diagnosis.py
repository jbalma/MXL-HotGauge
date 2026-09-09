"""A too-large 3D-ICE stack must fail with a DIAGNOSIS, not silently (§P0.17).

3D-ICE exits during "Preparing thermal data" with an **empty stderr** when the system is larger
than SuperLU 4.3 will factorise here. The only symptoms are an `ExecutableJobError` and a long wall
time — measured at ~75 minutes per point, four times over, in the catalogue re-run before anyone
looked. This does not gate a run; it puts the number in the message.

Measured discriminator (arm D, `stacked_memory_study.py`):

    50 um + 4-8 memory dies   ~1,098,144 unknowns   failed 4/4
    100 um + 4-8 memory dies    ~274,536 unknowns   succeeded 4/4
    50 um + default dies             small          succeeded 3/3

so the driver is total unknowns, fed by both the cell size and the die count.
"""
import os
import textwrap

import pytest

from HotGauge.thermal.leakage_feedback import (stack_unknowns, _with_stack_size_diagnosis,
                                               LARGEST_MEASURED_UNKNOWNS)

_STK_HEAD = """
dimensions :
   chip length {L}, width {W} ;
   cell length {c}, width {c} ;
"""


def _write(tmp_path, L, W, c, layers=27):
    """Render a minimal .stk. `layers` defaults to 27 -- the real stacked-memory stack, which is
    what makes the 12400x8200 @ 50 um case land on the measured 1,098,144."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / 'IC.stk'
    body = ''.join('   layer l%d :\n' % i for i in range(layers))
    p.write_text(textwrap.dedent(_STK_HEAD).format(L=L, W=W, c=c) + body)
    return str(p)


class _Sim:
    def __init__(self, f):
        self.stack_file = f


def test_unknowns_are_read_off_the_rendered_stack(tmp_path):
    f = _write(tmp_path, 12400, 8200, 50)
    n, (L, W), (cl, _), layers = stack_unknowns(f)
    assert (L, W) == (12400.0, 8200.0) and cl == 50.0 and layers == 27
    assert n == 1098144, 'must reproduce the size measured on the real failing stack'


def test_halving_the_cell_quarters_the_system(tmp_path):
    big = stack_unknowns(_write(tmp_path / 'a', 12400, 8200, 50))
    small = stack_unknowns(_write(tmp_path / 'b', 12400, 8200, 100))
    assert big[0] == 4 * small[0], 'the fix the message recommends must actually be 4x'


@pytest.fixture
def _mk(tmp_path):
    def go(L, W, c, sub, layers=27):
        return _write(tmp_path / sub, L, W, c, layers)
    return go


def test_an_oversized_stack_gets_the_diagnosis(_mk):
    exc = OSError(5, '1/1 instances of ICESteadySim failed.')
    out = _with_stack_size_diagnosis(exc, _Sim(_mk(12400, 8200, 50, 'big')))
    msg = str(out)
    assert '1,098,144' in msg, 'the message must carry the measured size'
    assert format(LARGEST_MEASURED_UNKNOWNS, ',') in msg, 'and what is known to work'
    assert '--cell-um 100' in msg, 'and the actionable fix'
    assert 'smooths lateral gradients' in msg, 'and the cost of taking it'


def test_a_normal_sized_stack_is_passed_through_untouched(_mk):
    exc = OSError(5, 'some unrelated failure')
    out = _with_stack_size_diagnosis(exc, _Sim(_mk(2000, 2000, 50, 'small', layers=3)))
    assert out is exc, 'an ordinary failure must not be dressed up as a size problem'


def test_an_unreadable_stack_never_masks_the_original_error():
    exc = OSError(5, 'original')
    assert _with_stack_size_diagnosis(exc, _Sim('/nonexistent/IC.stk')) is exc
    assert stack_unknowns('/nonexistent/IC.stk') is None
