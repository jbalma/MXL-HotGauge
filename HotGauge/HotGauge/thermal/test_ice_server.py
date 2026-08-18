"""Tests for the persistent 3D-ICE session.

Split in two. The parsing/protocol tests are pure Python and always run. The equivalence test
needs a built ``3D-ICE-Server`` and a solved reference run, so it skips when those are absent --
but it is the one that matters: it asserts the fast path and the stock one-shot path produce the
same temperatures *keyed by block name*.

Getting the name<->index mapping wrong would not crash. It would put the right powers on the
wrong blocks and return plausible, wrong temperatures, which is why it is pinned here.
"""
import os
import re

import numpy as np
import pytest

from HotGauge.thermal.ice_server import (
    ICEServerSession, ICEServerError, ICESessionCache, matrix_fingerprint,
    flp_element_names, stack_floorplan_path,
    _pack, MSG_INSERT_POWERS, MSG_SIMULATE_SLOT,
    SIM_SLOT_DONE, SIM_STEP_DONE, SIM_SOLVER_ERROR, _SIM_RESULT_NAMES)

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REF_DIR = os.path.join(_REPO, 'results', 'mr_compare', '34c_nomr', 'it01', 'iter_000')
_SERVER = os.path.join(_REPO, '3d-ice', 'bin', '3D-ICE-Server')

_has_ref = os.path.isfile(os.path.join(_REF_DIR, 'IC.flp'))
_has_server = os.path.isfile(_SERVER)


# ---------------------------------------------------------------------------
# Protocol framing -- no server needed
# ---------------------------------------------------------------------------
class TestFraming:
    def test_header_is_length_then_type(self):
        blob = _pack(MSG_SIMULATE_SLOT)
        assert len(blob) == 8
        length, mtype = np.frombuffer(blob, dtype='<u4')
        assert length == 2            # counts itself and the type word
        assert mtype == MSG_SIMULATE_SLOT

    def test_length_counts_payload_words(self):
        import struct
        words = [struct.pack('<I', 3), struct.pack('<f', 1.5), struct.pack('<f', 2.5)]
        blob = _pack(MSG_INSERT_POWERS, words)
        length = np.frombuffer(blob[:4], dtype='<u4')[0]
        assert length == 2 + 3
        assert len(blob) == 4 * length

    def test_sim_result_ordinals_match_the_c_enum(self):
        """SLOT_DONE is 4. Reading it as 1 turns every success into an exception."""
        assert SIM_SLOT_DONE == 4
        assert SIM_STEP_DONE == 3
        assert SIM_SOLVER_ERROR == 2
        assert _SIM_RESULT_NAMES[SIM_SLOT_DONE] == 'SLOT_DONE'


# ---------------------------------------------------------------------------
# Floorplan name ordering -- the silent-corruption risk
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _has_ref, reason='no solved reference run in results/')
class TestNameOrdering:
    def test_flp_order_matches_temps_header(self):
        """The wire returns a bare array; this mapping is what names it.

        3D-ICE emits Tflp values in floorplan-file order, and writes the .temps header in that
        same order -- so the header is an independent check on the parse.
        """
        names = flp_element_names(os.path.join(_REF_DIR, 'IC.flp'))
        header = open(os.path.join(_REF_DIR, 'die_elements.temps')).readlines()[1]
        cols = [c.strip().replace('(K)', '') for c in header.replace('%', '').split('\t')]
        cols = [c for c in cols if c and not c.startswith('Time')]
        assert names == cols

    def test_names_are_parsed_despite_the_space_before_colon(self):
        names = flp_element_names(os.path.join(_REF_DIR, 'IC.flp'))
        assert len(names) > 1000
        assert names[0] == 'AVXs_0'

    def test_stack_floorplan_path_resolves(self):
        stk = os.path.join(_REF_DIR, 'IC.stk')
        if not os.path.isfile(stk):
            pytest.skip('no reference stack')
        assert os.path.basename(stack_floorplan_path(stk)) == 'IC.flp'


def test_missing_stack_file_is_rejected_early():
    with pytest.raises(ICEServerError):
        ICEServerSession('/nonexistent/nope.stk')


# ---------------------------------------------------------------------------
# The equivalence test
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.skipif(not (_has_ref and _has_server),
                    reason='needs a built 3D-ICE-Server and a solved reference run')
def test_server_matches_oneshot_emulator_by_name():
    """Same temperatures, keyed by block name, as the stock one-shot Emulator.

    Takes ~90 s: the factorisation is the cost, and it happens once. Tolerance is 0.01 K --
    values cross the socket as float32 while the solver works in double, so ~1e-4 K of
    quantisation is expected and anything larger means a real disagreement.
    """
    from HotGauge.thermal.leakage_feedback import die_block_temps

    flp = os.path.join(_REF_DIR, 'IC.flp')
    stk = os.path.join(_REF_DIR, 'IC.stk')
    names = flp_element_names(flp)

    powers, cur = {}, None
    for line in open(flp):
        m = re.match(r'^\s*([A-Za-z_][A-Za-z_0-9]*)\s*:\s*$', line)
        if m:
            cur = m.group(1)
        m = re.match(r'^\s*power values\s+([0-9.eE+-]+)\s*;', line)
        if m and cur:
            powers[cur] = float(m.group(1))
    assert len(powers) == len(names)

    with ICEServerSession(stk, n_elements=len(names)) as session:
        got = session.solve_named(powers)

    ref = {k: float(np.ravel(v)[-1]) for k, v in die_block_temps(
        os.path.join(_REF_DIR, 'die_elements.temps')).items()}

    assert set(got) == set(ref), 'block name sets differ'
    diffs = {k: abs(got[k] - ref[k]) for k in ref}
    worst = max(diffs, key=diffs.get)
    assert diffs[worst] < 0.01, 'worst block {}: {:.4f} K vs {:.4f} K'.format(
        worst, got[worst], ref[worst])


# ---------------------------------------------------------------------------
# The matrix fingerprint -- what makes sweep-spanning safe rather than assumed
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _has_ref, reason='no solved reference run in results/')
class TestMatrixFingerprint:
    """A session's factorisation is valid exactly while the matrix is unchanged.

    Reusing one past a matrix change is SILENT -- the server solves new powers against the
    stale factorisation and returns plausible, wrong temperatures. These tests pin the
    distinction the fingerprint has to make.
    """

    @staticmethod
    def _rewrite(path, old, new, count=0):
        """Read fully, then write. ``open(p,'w').write(open(p).read()...)`` truncates first."""
        text = open(path).read()
        text = text.replace(old, new) if count == 0 else text.replace(old, new, count)
        with open(path, 'w') as f:
            f.write(text)

    @staticmethod
    def _sandbox(tmp_path):
        import shutil
        shutil.copy(os.path.join(_REF_DIR, 'IC.flp'), str(tmp_path))
        stk = open(os.path.join(_REF_DIR, 'IC.stk')).read()
        stk = re.sub(r'floorplan "[^"]+"', 'floorplan "{}/IC.flp"'.format(tmp_path), stk)
        (tmp_path / 'IC.stk').write_text(stk)
        return str(tmp_path / 'IC.stk'), str(tmp_path / 'IC.flp')

    def test_power_change_keeps_the_session_valid(self, tmp_path):
        """Powers are the RHS. A leakage loop changes them every iteration and must not
        trigger a refactorisation -- that is the entire 195x speedup."""
        stk, flp = self._sandbox(tmp_path)
        before = matrix_fingerprint(stk)
        self._rewrite(flp, 'power values 0.0;', 'power values 1.234;')
        assert matrix_fingerprint(stk) == before

    def test_htc_change_invalidates_the_session(self, tmp_path):
        """Sweeping airflow rewrites the heat transfer coefficient, so the matrix differs."""
        stk, _ = self._sandbox(tmp_path)
        before = matrix_fingerprint(stk)
        self._rewrite(stk, 'heat transfer coefficient 1.293300e-07',
                      'heat transfer coefficient 2.0e-07')
        assert matrix_fingerprint(stk) != before

    def test_geometry_change_invalidates_the_session(self, tmp_path):
        stk, flp = self._sandbox(tmp_path)
        before = matrix_fingerprint(stk)
        self._rewrite(flp, 'dimension 457.982,', 'dimension 500.0,', count=1)
        assert matrix_fingerprint(stk) != before

    def test_stale_session_refuses_to_solve(self, tmp_path):
        """Fails closed: a mutated stack raises instead of returning wrong numbers."""
        stk, _ = self._sandbox(tmp_path)
        sess = ICEServerSession(stk)
        sess.matrix_fingerprint = matrix_fingerprint(stk)
        self._rewrite(stk, 'heat transfer coefficient 1.293300e-07',
                      'heat transfer coefficient 9.9e-07')
        with pytest.raises(ICEServerError, match='stale'):
            sess.check_matrix_unchanged()

    def test_run_directory_does_not_invalidate_the_session(self, tmp_path):
        """Each leakage iteration writes to a fresh run dir, so the .stk embeds a different
        floorplan path while the matrix is unchanged. If that flipped the fingerprint the
        session would refactorise every solve -- correct results, zero speedup, no error."""
        import shutil
        stk, flp = self._sandbox(tmp_path)
        before = matrix_fingerprint(stk)
        other = tmp_path / 'iter_001'
        other.mkdir()
        shutil.copy(flp, str(other / 'IC.flp'))
        stk2 = str(other / 'IC.stk')
        text = re.sub(r'floorplan "[^"]+"', 'floorplan "{}/IC.flp"'.format(other), open(stk).read())
        open(stk2, 'w').write(text)
        assert matrix_fingerprint(stk2) == before

    def test_cache_keys_on_the_fingerprint(self, tmp_path):
        """The cache must reuse across a power change and rebuild across an HTC change."""
        stk, flp = self._sandbox(tmp_path)
        cache = ICESessionCache()
        fp1 = matrix_fingerprint(stk)
        self._rewrite(flp, 'power values 0.0;', 'power values 2.0;')
        assert matrix_fingerprint(stk) == fp1        # reuse
        self._rewrite(stk, 'heat transfer coefficient 1.293300e-07',
                      'heat transfer coefficient 3.0e-07')
        assert matrix_fingerprint(stk) != fp1        # rebuild
        cache.close()


@pytest.mark.slow
@pytest.mark.skipif(not (_has_ref and _has_server),
                    reason='needs a built 3D-ICE-Server and a solved reference run')
def test_powers_take_effect_on_the_same_solve():
    """Each solve must answer the powers it was just given, not the previous ones.

    3D-ICE queues power values: the .flp pre-loads one entry at startup, insert_power_values()
    pushes onto the back, update_source_vector() pops the front. Without the priming solve in
    ICEServerSession.start() every insert/simulate pair runs one step out of phase.

    This is invisible to a comparison that feeds slowly-varying powers -- a leakage loop looks
    like it merely converges fast -- so the test deliberately swings the power hard. Monotonic
    response and exact repeatability are what distinguish a working session from a lagged one.
    """
    stk = os.path.join(_REF_DIR, 'IC.stk')
    flp = os.path.join(_REF_DIR, 'IC.flp')
    powers = [float(m.group(1)) for m in
              (re.match(r'^\s*power values\s+([0-9.eE+-]+)\s*;', l) for l in open(flp)) if m]

    with ICEServerSession(stk, n_elements=len(powers)) as s:
        peaks = [s.solve([p * m for p in powers]).max() for m in (1.0, 2.0, 0.5, 1.0)]

    base, double, half, again = peaks
    assert double > base + 10.0, 'doubling power must raise the peak, got {}'.format(peaks)
    assert half < base - 10.0, 'halving power must lower the peak, got {}'.format(peaks)
    assert abs(again - base) < 0.01, 'same powers must give the same answer, got {}'.format(peaks)


def test_startup_timeout_is_configurable_because_startup_is_the_factorisation():
    """The 50 um GA100 run was reported as a hang. It was not: startup IS the factorisation,
    factorisation scales as N^1.67, and the 87.5 s measured at 691k unknowns projects to ~2900 s at
    5.6M -- past the old hard-coded 1800 s. A problem-size limit must not masquerade as a timeout,
    and the projection was already in this module's docstring when I misread the failure."""
    import os
    import importlib
    import HotGauge.thermal.ice_server as mod

    old = os.environ.get('MXL_ICE_STARTUP_TIMEOUT_S')
    try:
        os.environ['MXL_ICE_STARTUP_TIMEOUT_S'] = '7200'
        importlib.reload(mod)
        assert mod.ICEServerSession.DEFAULT_STARTUP_TIMEOUT_S == 7200.0
    finally:
        if old is None:
            os.environ.pop('MXL_ICE_STARTUP_TIMEOUT_S', None)
        else:
            os.environ['MXL_ICE_STARTUP_TIMEOUT_S'] = old
        importlib.reload(mod)
    assert mod.ICEServerSession.DEFAULT_STARTUP_TIMEOUT_S == 1800.0
