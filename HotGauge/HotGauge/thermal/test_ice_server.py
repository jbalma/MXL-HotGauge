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
    flp_element_names, stack_floorplan_path, stack_floorplans, tflp_output_dies,
    _pack, MSG_INSERT_POWERS, MSG_SIMULATE_SLOT,
    SIM_SLOT_DONE, SIM_STEP_DONE, SIM_SOLVER_ERROR, _SIM_RESULT_NAMES)

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REF_DIR = os.path.join(_REPO, 'results', 'mr_compare', '34c_nomr', 'it01', 'iter_000')
_SERVER = os.path.join(_REPO, '3d-ice', 'bin', '3D-ICE-Server')

#: Names this file imports from ice_server at module scope. ``importlib.reload`` rebinds every
#: class in a module, so after a reload these names point at objects the module no longer uses --
#: and ``pytest.raises(ICEServerError)`` then silently stops matching the error the code actually
#: raises, because the two classes are different objects with the same name. Any test that reloads
#: must re-sync through :func:`_resync_module_names` or it leaves that trap for everything that
#: runs after it. This is not hypothetical: it is what made TestTwoDieOrdering pass in isolation
#: and fail in file order.
_IMPORTED_FROM_ICE_SERVER = (
    'ICEServerSession', 'ICEServerError', 'ICESessionCache', 'matrix_fingerprint',
    'flp_element_names', 'stack_floorplan_path', 'stack_floorplans', 'tflp_output_dies',
    'MSG_INSERT_POWERS', 'MSG_SIMULATE_SLOT', 'SIM_SLOT_DONE', 'SIM_STEP_DONE',
    'SIM_SOLVER_ERROR', '_SIM_RESULT_NAMES', '_pack')


def _resync_module_names(mod):
    """Point this file's module-scope imports back at the reloaded module's objects."""
    globals().update({n: getattr(mod, n) for n in _IMPORTED_FROM_ICE_SERVER
                      if hasattr(mod, n)})


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


def test_orphan_detector_matches_the_executable_not_the_line():
    """An orphaned server starves every factorisation after it, so the timeout must name it.

    A single 3D-ICE-Server takes roughly fifteen cores. If the Python process that launched one
    is SIGKILLed, atexit never runs and the server survives; the next run then times out and
    blames the problem size, which is the wrong diagnosis. The detector has to match the
    EXECUTABLE, though -- this project's own diagnostics mention the server by name on their
    command lines, and reporting one of those as an orphan sends the reader after a grep.
    """
    rows = ICEServerSession.other_servers_running()
    assert isinstance(rows, list)
    for pid, elapsed, cmd in rows:
        assert isinstance(pid, int)
        assert os.path.basename(cmd.split()[0]) == '3D-ICE-Server', \
            'detector matched a line that merely mentions the server: {!r}'.format(cmd)


def test_orphan_detector_can_exclude_our_own_process():
    import subprocess
    p = subprocess.Popen(['sleep', '30'])
    try:
        assert all(pid != p.pid for pid, _, _ in
                   ICEServerSession.other_servers_running(exclude_pid=p.pid))
    finally:
        p.kill()
        p.wait()


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
        _resync_module_names(mod)
    assert mod.ICEServerSession.DEFAULT_STARTUP_TIMEOUT_S == 1800.0


def test_shared_cache_is_one_object_per_process():
    """A sweep driver runs many study points in one process precisely so they share a
    factorisation. The first attempt kept the cache at module level inside the study script, and
    runpy.run_path re-executes that file per point -- so the globals reset and three points
    factorised three times, silently paying the exact cost the driver existed to avoid. Parking the
    singleton in this module, which lives in sys.modules, is what makes the sharing real."""
    import HotGauge.thermal.ice_server as mod

    mod.reset_shared_cache()
    try:
        a = mod.shared_cache()
        b = mod.shared_cache()
        assert a is b
        assert isinstance(a, mod.ICESessionCache)
    finally:
        mod.reset_shared_cache()


def test_resetting_the_shared_cache_yields_a_fresh_one():
    import HotGauge.thermal.ice_server as mod

    mod.reset_shared_cache()
    try:
        a = mod.shared_cache()
        mod.reset_shared_cache()
        b = mod.shared_cache()
        assert a is not b
    finally:
        mod.reset_shared_cache()


def test_shared_cache_survives_module_re_execution_the_way_a_study_global_does_not():
    """The precise failure mode, pinned. Re-executing a file resets ITS globals; it does not touch
    an already-imported module's."""
    import runpy
    import tempfile
    import os
    import HotGauge.thermal.ice_server as mod

    mod.reset_shared_cache()
    try:
        first = mod.shared_cache()
        script = os.path.join(tempfile.mkdtemp(), 'point.py')
        with open(script, 'w') as f:
            f.write('MY_GLOBAL = None\n'
                    'from HotGauge.thermal.ice_server import shared_cache\n'
                    'CACHE_ID = id(shared_cache())\n')
        seen = [runpy.run_path(script, run_name='__main__')['CACHE_ID'] for _ in range(3)]
        assert seen == [id(first)] * 3
    finally:
        mod.reset_shared_cache()


# ---------------------------------------------------------------------------
# Two dies: the photonic array as a second powered element
# ---------------------------------------------------------------------------
def _build_two_die_stack(d, pitch_um=2000.0, cell_um=50.0, mr_first_in_output=False):
    """A real two-die stack in ``d``. Returns (stk, block_names, tile_names)."""
    import math
    from HotGauge.thermal.die_stack import StackSpec, render_stack_text
    from HotGauge.thermal.mr_array import tile_grid, write_mr_floorplan, blocks_from_floorplan
    from HotGauge.utils.floorplan import Floorplan

    flp = os.path.join(_REPO, 'examples', 'floorplans', 'outputs',
                       'skylake10nm_7core_0_3D-ICE_template.flp')
    tmpl = open(flp).read()
    blocks = blocks_from_floorplan(Floorplan.from_file(flp, frmt='3D-ICE'))
    cw = int(math.ceil(max(b[0] + b[2] for b in blocks.values()) / cell_um) * cell_um)
    ch = int(math.ceil(max(b[1] + b[3] for b in blocks.values()) / cell_um) * cell_um)
    tiles = tile_grid(cw, ch, pitch_um=pitch_um, cell_um=cell_um)

    bnames, tnames = sorted(blocks), [t['name'] for t in tiles]
    write_mr_floorplan(os.path.join(d, 'MR.flp'), tiles)
    mt = open(os.path.join(d, 'MR.flp')).read()
    open(os.path.join(d, 'MR.flp'), 'w').write(
        mt.format(powers={k: '0.0' for k in tnames}))
    open(os.path.join(d, 'IC.flp'), 'w').write(
        tmpl.format(powers={k: '1.0' for k in bnames}))

    ic = '   Tflp (PROCESSOR_DIE, "die.temps", average, final ) ;\n'
    mr = '   Tflp (MR_ARRAY, "mr.temps", average, final ) ;\n'
    spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True, cell_um=cell_um)
    stk = os.path.join(d, 'IC.stk')
    open(stk, 'w').write(render_stack_text(spec).format(
        flp_width=str(cw), flp_height=str(ch), flp_file='IC.flp', mr_flp_file='MR.flp',
        solver_config='   steady ;\n   initial temperature 300.0 ;',
        output_list=(mr + ic) if mr_first_in_output else (ic + mr)))
    return stk, bnames, tnames


class TestTwoDieOrdering:
    """Powers and temperatures travel differently, and both orders have to be right.

    A wrong order does not crash. It puts cooling powers on processor blocks and returns a
    plausible, wrong field -- so every assertion here is about ordering, not about physics.
    """

    def test_power_order_is_bottom_up_not_file_order(self, tmp_path):
        """The .stk lists dies top-down; 3D-ICE consumes powers bottom-up."""
        stk, _, _ = _build_two_die_stack(str(tmp_path))
        got = [inst for inst, _ in stack_floorplans(stk)]
        assert got == ['PROCESSOR_DIE', 'MR_ARRAY'], (
            'power vector runs from the bottom of the stack up: the processor die comes first '
            'even though the file declares the array above it')
        declared = re.findall(r'die\s+(\w+)\s+\w+\s+floorplan', open(stk).read())
        assert got == list(reversed(declared))

    def test_temperature_order_follows_the_output_section(self, tmp_path):
        """Not the power order: whichever Tflp instruction is written first replies first."""
        a, _, _ = _build_two_die_stack(str(tmp_path))
        assert tflp_output_dies(a) == ['PROCESSOR_DIE', 'MR_ARRAY']
        d2 = tmp_path / 'flipped'
        d2.mkdir()
        b, _, _ = _build_two_die_stack(str(d2), mr_first_in_output=True)
        assert tflp_output_dies(b) == ['MR_ARRAY', 'PROCESSOR_DIE'], (
            'reversing the output section must reverse the reply order -- if this tracked the '
            'power order instead, tile temperatures would be reported as processor blocks')

    def test_only_matching_quantity_and_instant_are_reported(self, tmp_path):
        stk, _, _ = _build_two_die_stack(str(tmp_path))
        from HotGauge.thermal.ice_server import QTY_MAXIMUM
        assert tflp_output_dies(stk, quantity=QTY_MAXIMUM) == []

    def test_fingerprint_covers_the_tile_floorplan(self, tmp_path):
        """Changing the array's geometry must rebuild the session; changing its powers must not."""
        d1, d2, d3 = tmp_path / 'a', tmp_path / 'b', tmp_path / 'c'
        for x in (d1, d2, d3):
            x.mkdir()
        a, _, tn = _build_two_die_stack(str(d1), pitch_um=2000.0)
        b, _, _ = _build_two_die_stack(str(d2), pitch_um=1000.0)
        c, _, tnc = _build_two_die_stack(str(d3), pitch_um=2000.0)
        assert matrix_fingerprint(a) != matrix_fingerprint(b), 'pitch changes the matrix'
        assert matrix_fingerprint(a) == matrix_fingerprint(c), 'same geometry, same matrix'
        mr = os.path.join(str(d3), 'MR.flp')
        txt = open(mr).read()
        open(mr, 'w').write(re.sub(r'power values [-0-9.eE+]+', 'power values -3.5', txt))
        assert matrix_fingerprint(a) == matrix_fingerprint(c), (
            'tile POWER is the right-hand side and must not invalidate the factorisation')

    def test_colliding_names_across_dies_are_refused(self, tmp_path):
        """solve_named keys by name, so a shared name would silently misroute power."""
        stk, bnames, _ = _build_two_die_stack(str(tmp_path))
        mr = os.path.join(str(tmp_path), 'MR.flp')
        txt = open(mr).read()
        m = re.search(r'^(\w+)\s*:', txt, re.M)
        assert m, 'no floorplan element parsed from the tile floorplan'
        open(mr, 'w').write(txt.replace(m.group(0), bnames[0] + ' :', 1))
        s = ICEServerSession.__new__(ICEServerSession)
        s.stack_file = stk
        s.n_elements = None
        s._names = None
        with pytest.raises(ICEServerError, match='collide'):
            s.element_names()


@pytest.mark.slow
@pytest.mark.skipif(not _has_server, reason='3D-ICE-Server not built')
def test_two_die_server_matches_oneshot_emulator_by_name(tmp_path):
    """The load-bearing test for the photonic array on the fast path.

    Deliberately **asymmetric**: one processor block at 40 W among neighbours near 0.5 W, and one
    tile pulling -6 W. A near-uniform pattern cannot detect a transposed element order -- that is
    exactly how the original power-queue phase bug survived its first test -- so the pattern is
    chosen to make a wrong order impossible to miss. The resulting field spans >100 K; a
    transposition would show up as errors of that size, not of the 1e-3 K this asserts.
    """
    import subprocess
    from HotGauge.thermal.ICE import ICE_DIR

    d = str(tmp_path)
    stk, bnames, tnames = _build_two_die_stack(d)
    bpow = {n: 0.5 + 0.01 * i for i, n in enumerate(bnames)}
    bpow[bnames[3]] = 40.0
    tpow = {n: 0.0 for n in tnames}
    tpow[tnames[7]] = -6.0

    # Rewrite both floorplans with the asymmetric powers.
    for path, pw in ((os.path.join(d, 'IC.flp'), bpow), (os.path.join(d, 'MR.flp'), tpow)):
        lines, cur = [], None
        for line in open(path):
            m = re.match(r'^(\w+)\s*:', line)
            if m:
                cur = m.group(1)
            if re.match(r'^\s*power values', line) and cur in pw:
                line = '\tpower values {:.6f};\n'.format(pw[cur])
            lines.append(line)
        open(path, 'w').writelines(lines)

    r = subprocess.run([os.path.join(ICE_DIR, 'bin', '3D-ICE-Emulator'), 'IC.stk'],
                       cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout + r.stderr)[-800:]

    def read(fname):
        ls = open(os.path.join(d, fname)).read().split('\n')
        ns = [x.strip()[:-3] for x in ls[1].split('\t')[1:] if x.strip()]
        vs = [float(x) for x in ls[2].split('\t')[1:] if x.strip()]
        return dict(zip(ns, vs))

    ref = {}
    ref.update(read('die.temps'))
    ref.update(read('mr.temps'))
    assert max(ref.values()) - min(ref.values()) > 50.0, (
        'the reference field must be strongly non-uniform or this test cannot detect a '
        'transposed element order')

    with ICEServerSession(stk) as s:
        assert len(s.element_names()) == s.n_elements
        got = s.solve_named({**bpow, **tpow})

    common = sorted(set(ref) & set(got))
    assert len(common) == len(ref), 'server did not report every element the emulator did'
    assert any(k.startswith('MR') for k in common) and any(not k.startswith('MR')
                                                           for k in common)
    worst = max(common, key=lambda k: abs(ref[k] - got[k]))
    assert abs(ref[worst] - got[worst]) < 1e-3, (
        '{}: emulator {:.4f} K vs server {:.4f} K'.format(worst, ref[worst], got[worst]))
