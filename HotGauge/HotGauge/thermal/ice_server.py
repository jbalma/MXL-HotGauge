"""Persistent 3D-ICE session: factor the system matrix once, solve many times.

Why this exists
---------------
``3D-ICE-Emulator`` is a one-shot process: it parses the stack, assembles the system matrix,
factorises it, solves once, and exits. The leakage fixed point and the MR clipping loop call it
dozens of times per study point with an **identical matrix** -- only the power values (the
right-hand side) change -- so almost all of that work is thrown away and redone.

Measured on the 34-core die (691k unknowns, node-03):

===========================================  ========
one-shot Emulator run (factor + 1 solve)      83.0 s
persistent server startup (factor once)       87.5 s
each subsequent solve in the session           0.43 s
===========================================  ========

So a 51-solve MR point goes from ~70 minutes to under two. Timing across grid refinements gives
``t ~ N^1.67`` -- the signature of 3D sparse LU -- confirming factorisation, not parsing or
assembly, is what dominates.

``3D-ICE-Server`` already held the factorisation across requests but refused any non-transient
analysis. ``MXL_3DICE_fixes/files/bin/3D-ICE-Server.c`` lifts that restriction; this module is
the client side.

Wire protocol
-------------
Every message is a sequence of little-endian 4-byte words::

    word 0 : total length in words, including this one
    word 1 : message type
    word 2+: payload

Payload scalars are 4 bytes whatever they mean -- powers and temperatures travel as C ``float``
even though the solver works in double internally, so expect ~1e-7 relative quantisation on
values that cross the socket.

Usage
-----
    with ICEServerSession(stack_file, n_elements=1126) as s:
        for powers in traces:
            temps = s.solve(powers)          # one factorisation, many solves
"""

import os
import re
import time
import hashlib
import atexit
import socket
import struct
import logging
import subprocess

import numpy as np

LOGGER = logging.getLogger(__name__)

#: Message types -- ordinals from ``3d-ice/include/types.h`` ``enum MessageType_t``.
MSG_EXIT = 0
MSG_RESET_THERMAL_STATE = 1
MSG_SEND_OUTPUT = 2
MSG_PRINT_OUTPUT = 3
MSG_TOTAL_N_FLOORPLAN_ELEMENTS = 4
MSG_INSERT_POWERS = 5
MSG_SIMULATE_SLOT = 6
MSG_SIMULATE_STEP = 7

#: ``enum OutputInstant_t`` / ``OutputType_t`` / ``OutputQuantity_t``.
INSTANT_NONE, INSTANT_FINAL, INSTANT_SLOT, INSTANT_STEP = 0, 1, 2, 3
TYPE_NONE, TYPE_TCELL, TYPE_TFLP, TYPE_TFLPEL, TYPE_TMAP, TYPE_TSTACK = 0, 1, 2, 3, 4, 5
QTY_NONE, QTY_AVERAGE, QTY_MAXIMUM, QTY_MINIMUM, QTY_GRADIENT = 0, 1, 2, 3, 4

#: ``enum SimResult_t`` from ``types.h``. Ordinals matter: SLOT_DONE is 4, not 1, and reading
#: a success as a failure (or worse, a failure as success) is silent either way.
SIM_END_OF_SIMULATION = 0
SIM_WRONG_CONFIG = 1
SIM_SOLVER_ERROR = 2
SIM_STEP_DONE = 3
SIM_SLOT_DONE = 4

_SIM_RESULT_NAMES = {
    SIM_END_OF_SIMULATION: 'END_OF_SIMULATION',
    SIM_WRONG_CONFIG: 'WRONG_CONFIG',
    SIM_SOLVER_ERROR: 'SOLVER_ERROR',
    SIM_STEP_DONE: 'STEP_DONE',
    SIM_SLOT_DONE: 'SLOT_DONE',
}


#: A floorplan element declaration: ``NAME :`` -- note the space before the colon.
_FLP_NAME_RGX = re.compile(r'^\s*([A-Za-z_][A-Za-z_0-9]*)\s*:\s*$')


def flp_element_names(flp_path):
    """Floorplan element names **in file order**, which is the order values cross the wire.

    3D-ICE returns Tflp values as a bare array with no names, so this mapping is the only
    thing standing between correct results and powers landing on the wrong blocks. It is
    verified against the ``.temps`` header (same order) by
    ``test_ice_server.py::test_flp_order_matches_temps_header``.
    """
    names = []
    with open(flp_path) as f:
        for line in f:
            m = _FLP_NAME_RGX.match(line)
            if m:
                names.append(m.group(1))
    if not names:
        raise ICEServerError('no floorplan elements parsed from {}'.format(flp_path))
    return names


def stack_floorplan_path(stack_file):
    """The .flp a .stk points at (``die NAME IC floorplan "path";``)."""
    with open(stack_file) as f:
        m = re.search(r'floorplan\s+"([^"]+)"', f.read())
    if not m:
        raise ICEServerError('no floorplan reference in {}'.format(stack_file))
    path = m.group(1)
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(stack_file)), path)
    return path


class ICEServerError(RuntimeError):
    """The server rejected a request, died, or returned an unusable reply."""


def _pack(mtype, words=()):
    """Frame a message. ``words`` are pre-packed 4-byte strings."""
    body = b''.join(words)
    return struct.pack('<II', 2 + len(words), mtype) + body


def _f32(x):
    return struct.pack('<f', float(x))


def _u32(x):
    return struct.pack('<I', int(x))


class ICEServerSession(object):
    """A live 3D-ICE server holding one factorisation.

    The session owns the subprocess. Always use it as a context manager (or call ``close``)
    so the server does not outlive the study -- an orphaned server keeps a ~GB factorisation
    resident and holds its port.
    """

    #: Default startup budget [s]. Startup IS the factorisation, and factorisation time scales as
    #: ``N^1.67`` (see the module note), so this is a problem-SIZE limit wearing a timeout's
    #: clothes. Measured 87.5 s at 691k unknowns, which projects to ~290 s for the GA100 die on a
    #: 100 um grid and ~2900 s on a 50 um grid. The latter exceeded the old hard-coded 1800 s, and
    #: I reported it as a hang when it was simply a die eight times larger -- the projection had
    #: been sitting in this module's own docstring the whole time. Override per session or with
    #: ``MXL_ICE_STARTUP_TIMEOUT_S``.
    DEFAULT_STARTUP_TIMEOUT_S = float(os.environ.get('MXL_ICE_STARTUP_TIMEOUT_S', 1800.0))

    def __init__(self, stack_file, n_elements=None, port=0, host='127.0.0.1',
                 server_bin=None, startup_timeout_s=None, solve_timeout_s=600.0):
        self.stack_file = os.path.abspath(stack_file)
        if not os.path.isfile(self.stack_file):
            raise ICEServerError('no stack file at {}'.format(self.stack_file))
        self.host = host
        self.port = int(port) or self._free_port()
        self.server_bin = server_bin or self._default_bin()
        self.startup_timeout_s = float(self.DEFAULT_STARTUP_TIMEOUT_S
                                       if startup_timeout_s is None else startup_timeout_s)
        self.solve_timeout_s = float(solve_timeout_s)
        self._proc = None
        self._sock = None
        self._log_path = None
        self.n_elements = n_elements
        self.factorisation_time_s = None
        self.n_solves = 0
        # 3D-ICE writes temperatures with insert_message_word(), which memcpy's exactly
        # sizeof(MessageWord_t) = 4 bytes -- but Temperature_t is a double. So each value
        # arrives as the low half of a double, not a float. _probe_temp_encoding() settles
        # which interpretation this build actually produces rather than assuming.
        self._temp_dtype = '<f4'
        self._names = None
        self.matrix_fingerprint = None
        self._warned_unknown = False

    # -- lifecycle ---------------------------------------------------------------------
    @staticmethod
    def _default_bin():
        here = os.path.dirname(os.path.abspath(__file__))
        repo = os.path.abspath(os.path.join(here, '..', '..', '..'))
        return os.path.join(repo, '3d-ice', 'bin', '3D-ICE-Server')

    @staticmethod
    def _free_port():
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        p = s.getsockname()[1]
        s.close()
        return p

    #: How many times to re-pick a port when the server loses the bind race. Choosing a free
    #: port here and handing it to a child process to bind is inherently racy -- nothing owns
    #: the port in between -- and a sweep running a dozen concurrent points hits it. It shows up
    #: as "ERROR :: server bind: Address already in use" in the server log and kills the study
    #: point, which is an expensive way to lose a run to a one-line race.
    _BIND_RETRIES = 5

    def start(self):
        if self._proc is not None:
            return self
        if not os.path.isfile(self.server_bin):
            raise ICEServerError(
                '3D-ICE-Server not built at {}. Run: make -C 3d-ice'.format(self.server_bin))
        for attempt in range(self._BIND_RETRIES):
            try:
                return self._start_once()
            except ICEServerError as e:
                if 'Address already in use' not in str(e) or attempt == self._BIND_RETRIES - 1:
                    raise
                LOGGER.warning('3D-ICE server lost the bind race on port %d (attempt %d/%d); '
                               'retrying on a fresh port', self.port, attempt + 1,
                               self._BIND_RETRIES)
                self._proc = None
                self.port = self._free_port()

    def _start_once(self):
        self._log_path = self.stack_file + '.server{}.log'.format(self.port)
        log = open(self._log_path, 'wb')
        t0 = time.time()
        # cwd matters: relative paths inside the .stk resolve against it.
        self._proc = subprocess.Popen(
            [self.server_bin, self.stack_file, str(self.port)],
            stdout=log, stderr=subprocess.STDOUT,
            cwd=os.path.dirname(self.stack_file) or '.')
        atexit.register(self.close)

        # The server prints "Waiting for client" only after the factorisation finishes, which
        # on a large die is many minutes. Poll the log rather than the port: connecting early
        # would succeed against the listen backlog and then hang.
        deadline = t0 + self.startup_timeout_s
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise ICEServerError('server exited during startup; see {}\n{}'.format(
                    self._log_path, self._tail_log()))
            try:
                with open(self._log_path, 'rb') as f:
                    if b'Waiting for client' in f.read():
                        break
            except IOError:
                pass
            time.sleep(0.25)
        else:
            self.close()
            raise ICEServerError('server did not become ready within {:.0f} s'
                                 .format(self.startup_timeout_s)
                                 + '. Startup is the FACTORISATION and it scales as '
                                   'N^1.67, so this is usually a problem-size limit rather '
                                   'than a hang: raise MXL_ICE_STARTUP_TIMEOUT_S, or coarsen the grid.')

        self.factorisation_time_s = time.time() - t0
        self.matrix_fingerprint = matrix_fingerprint(self.stack_file)
        LOGGER.info('3D-ICE server ready on port %d after %.1f s (factorisation)',
                    self.port, self.factorisation_time_s)

        self._sock = socket.create_connection((self.host, self.port), timeout=30.0)
        self._sock.settimeout(self.solve_timeout_s)
        if self.n_elements is None:
            self.n_elements = self.total_floorplan_elements()

        # PRIMING SOLVE -- do not remove.
        #
        # 3D-ICE models power as a QUEUE: the .flp's own `power values` are loaded at startup,
        # insert_power_values() pushes onto the back, and update_source_vector() pops the front.
        # Without this, every insert/simulate pair runs one step out of phase and each solve
        # returns the PREVIOUS insert's temperatures -- silently, and plausibly enough that a
        # comparison using slowly-varying powers still looks correct. It shows up only when
        # consecutive power vectors differ sharply (feed x1, x2, x0.5 and the answers arrive
        # shifted by one). Consuming the pre-loaded .flp entry here puts insert and simulate in
        # phase for the rest of the session.
        self.simulate()
        self.n_solves = 0
        return self

    def close(self):
        if self._sock is not None:
            try:
                self._send(_pack(MSG_EXIT))
            except Exception:      # noqa: BLE001 - shutting down; the server may already be gone
                pass
            try:
                self._sock.close()
            except Exception:      # noqa: BLE001
                pass
            self._sock = None
        if self._proc is not None:
            try:
                self._proc.wait(timeout=10)
            except Exception:      # noqa: BLE001
                self._proc.kill()
            self._proc = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()
        return False

    def _tail_log(self, n=2000):
        try:
            with open(self._log_path, 'rb') as f:
                return f.read()[-n:].decode('utf-8', 'replace')
        except Exception:          # noqa: BLE001
            return '(no log)'

    # -- transport ---------------------------------------------------------------------
    def _send(self, blob):
        if self._sock is None:
            raise ICEServerError('session is not open')
        self._sock.sendall(blob)

    def _recv_exactly(self, n):
        buf = b''
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ICEServerError('server closed the connection; {}'.format(self._tail_log()))
            buf += chunk
        return buf

    def _recv(self):
        """Read one framed message; returns (mtype, payload_bytes)."""
        length = struct.unpack('<I', self._recv_exactly(4))[0]
        if length < 2:
            raise ICEServerError('malformed reply: length {}'.format(length))
        rest = self._recv_exactly((length - 1) * 4)
        mtype = struct.unpack('<I', rest[:4])[0]
        return mtype, rest[4:]

    def _request(self, mtype, words=()):
        self._send(_pack(mtype, words))
        rtype, payload = self._recv()
        if rtype != mtype:
            raise ICEServerError('reply type {} does not match request {}'.format(rtype, mtype))
        return payload

    # -- operations --------------------------------------------------------------------
    def total_floorplan_elements(self):
        payload = self._request(MSG_TOTAL_N_FLOORPLAN_ELEMENTS)
        return struct.unpack('<I', payload[:4])[0]

    def insert_powers(self, powers):
        """Set the source vector. ``powers`` is one value per floorplan element, in order."""
        vals = np.asarray(powers, dtype=float).ravel()
        if self.n_elements is not None and len(vals) != self.n_elements:
            raise ICEServerError('expected {} power values, got {}'
                                 .format(self.n_elements, len(vals)))
        words = [_u32(len(vals))] + [_f32(v) for v in vals]
        payload = self._request(MSG_INSERT_POWERS, words)
        err = struct.unpack('<I', payload[:4])[0]
        if err != 0:
            raise ICEServerError('insert_powers rejected (error {})'.format(err))

    def simulate(self):
        """Run one solve against the existing factorisation. Returns the SimResult ordinal."""
        payload = self._request(MSG_SIMULATE_SLOT)
        result = struct.unpack('<I', payload[:4])[0]
        # The patched server normalises steady's END_OF_SIMULATION to SLOT_DONE, so anything
        # else here is a genuine failure rather than "the run finished".
        if result not in (SIM_SLOT_DONE, SIM_STEP_DONE):
            raise ICEServerError('simulate returned {} ({}); {}'.format(
                result, _SIM_RESULT_NAMES.get(result, 'unknown'), self._tail_log()))
        self.n_solves += 1
        return result

    def temperatures(self, instant=INSTANT_FINAL, otype=TYPE_TFLP, quantity=QTY_AVERAGE):
        """Per-floorplan-element temperatures [K] from the last solve."""
        payload = self._request(MSG_SEND_OUTPUT,
                                [_u32(instant), _u32(otype), _u32(quantity)])
        if len(payload) < 8:
            raise ICEServerError('short SEND_OUTPUT reply ({} bytes)'.format(len(payload)))
        # Layout: time(f32), n_points(u32), then per matching inspection point
        # nflp(u32) followed by nflp temperature words.  n_points counts *output
        # instructions* in the .stk that match the filter -- NOT the number of values.
        _sim_time = struct.unpack('<f', payload[0:4])[0]
        n_points = struct.unpack('<I', payload[4:8])[0]
        out, off = [], 8
        for _ in range(n_points):
            if off + 4 > len(payload):
                raise ICEServerError('truncated SEND_OUTPUT reply')
            nflp = struct.unpack('<I', payload[off:off + 4])[0]
            off += 4
            end = off + 4 * nflp
            if end > len(payload):
                raise ICEServerError('SEND_OUTPUT promised {} values, {} bytes left'
                                     .format(nflp, len(payload) - off))
            out.append(np.frombuffer(payload[off:end], dtype=self._temp_dtype).astype(float))
            off = end
        if not out:
            raise ICEServerError(
                'no inspection point matched (instant={}, type={}, quantity={}). The .stk must '
                'declare a matching output instruction, e.g. Tflp (DIE, "f", average, final).'
                .format(instant, otype, quantity))
        return np.concatenate(out) if len(out) > 1 else out[0]

    def reset(self):
        """Reset the thermal state without touching the factorisation."""
        self._request(MSG_RESET_THERMAL_STATE)


    # -- named interface ---------------------------------------------------------------
    def element_names(self):
        """Block names in wire order, parsed from the .flp this session's .stk references."""
        if self._names is None:
            self._names = flp_element_names(stack_floorplan_path(self.stack_file))
            if self.n_elements is not None and len(self._names) != self.n_elements:
                raise ICEServerError(
                    'floorplan has {} named elements but the server reports {}. Powers would '
                    'land on the wrong blocks.'.format(len(self._names), self.n_elements))
        return self._names

    def solve_named(self, power_by_name, strict=False, **kw):
        """``{block: watts}`` in, ``{block: kelvin}`` out.

        Two asymmetric rules, chosen to match what 3D-ICE's file path does:

        * A floorplan block **absent** from ``power_by_name`` gets 0 W explicitly. Skipping it
          would leave the previous solve's power for that block in the persistent source
          vector -- an error that surfaces only as a slightly wrong temperature.
        * A key that is **not** a floorplan block is dropped. A prepared trace legitimately
          still carries McPAT aggregates (``BUSES``, ``NUCA``, ``Processor/Total Cores``) whose
          power is not placed on the die, and ``fill_flp_template`` ignores them too. Pass
          ``strict=True`` to reject them instead, which is useful when the caller believes it
          has already filtered.
        """
        names = self.element_names()
        known = set(names)
        unknown = set(power_by_name) - known
        if unknown:
            if strict:
                raise ICEServerError('{} power keys are not floorplan elements, e.g. {}'
                                     .format(len(unknown), sorted(unknown)[:5]))
            if not self._warned_unknown:
                LOGGER.debug('dropping %d non-floorplan power keys (McPAT aggregates), e.g. %s',
                             len(unknown), sorted(unknown)[:5])
                self._warned_unknown = True
        vec = [float(np.ravel(power_by_name.get(n, 0.0))[-1]) for n in names]
        temps = self.solve(vec, **kw)
        return dict(zip(names, temps))

    def check_matrix_unchanged(self):
        """Raise if the stack has been rewritten since this session factorised it.

        Cheap (one hash of two small text files) next to a 0.43 s solve, and it is the only
        thing standing between a sweep and silently solving against a stale matrix.
        """
        if self.matrix_fingerprint is None:
            return
        now = matrix_fingerprint(self.stack_file)
        if now != self.matrix_fingerprint:
            raise ICEServerError(
                'the stack changed since this session factorised it, so its factorisation is '
                'stale. Solving anyway would return plausible, wrong temperatures. Start a new '
                'session (or use ICESessionCache, which does it for you).')

    def solve(self, powers, **kw):
        """insert_powers -> simulate -> temperatures, the loop this class exists for."""
        self.check_matrix_unchanged()
        self.insert_powers(powers)
        self.simulate()
        return self.temperatures(**kw)

#: Lines in a .flp that carry POWER rather than geometry. Power is the right-hand side and may
#: change freely within a session; everything else feeds the system matrix and may not.
_FLP_POWER_RGX = re.compile(r'^\s*power values\b')


def matrix_fingerprint(stack_file):
    """Hash of everything the system matrix is built from.

    A session's factorisation is valid exactly while this is unchanged. It covers the whole
    ``.stk`` (geometry, materials, heat transfer coefficient, ambient) and the ``.flp``
    **geometry** -- deliberately excluding ``power values``, which are the RHS and are expected
    to change on every solve.

    This matters because reusing a session across a change 3D-ICE cannot see is silent: the
    server happily solves new powers against a stale matrix and returns plausible, wrong
    temperatures. Sweeping die power or MR target is safe; sweeping airflow is not, because
    ``render_stack_with_sink`` writes a new heat transfer coefficient into the ``.stk``.
    """
    h = hashlib.sha256()
    with open(stack_file) as f:
        stk = f.read()
    # Blank out quoted strings before hashing. In a .stk these are only file paths -- the
    # floorplan reference and the output filenames -- and every leakage iteration writes its
    # inputs to a fresh run directory, so the paths differ while the matrix is identical.
    # Hashing them verbatim would rebuild the session on every solve and silently give back
    # the full factorisation cost with no error to show for it. The floorplan's *content* is
    # hashed below, so nothing material is lost.
    h.update(re.sub(r'"[^"]*"', '""', stk).encode('utf-8'))
    flp = stack_floorplan_path(stack_file)
    with open(flp) as f:
        for line in f:
            if not _FLP_POWER_RGX.match(line):
                h.update(line.encode('utf-8'))
    return h.hexdigest()


class ICESessionCache(object):
    """Reuse a session while the matrix is unchanged; build a new one when it is not.

    Makes sweep-spanning safe by construction rather than by convention::

        cache = ICESessionCache()
        for cfm in (50, 88, 200):            # each writes a different HTC -> new session
            for power in (200, 313, 360):    # RHS only -> the session is reused
                stk = render_stack_with_sink(...)
                temps = cache.session(stk).solve_named(powers)
        cache.close()
    """

    def __init__(self, max_sessions=1, **session_kw):
        self.max_sessions = int(max_sessions)
        self.session_kw = session_kw
        self._sessions = {}          # fingerprint -> ICEServerSession
        self.hits = 0
        self.misses = 0

    def session(self, stack_file):
        fp = matrix_fingerprint(stack_file)
        got = self._sessions.get(fp)
        if got is not None:
            self.hits += 1
            return got
        self.misses += 1
        # Evict oldest first; each live session pins a factorisation in memory.
        while len(self._sessions) >= self.max_sessions:
            _, old = self._sessions.popitem()
            old.close()
        sess = ICEServerSession(stack_file, **self.session_kw).start()
        sess.matrix_fingerprint = fp
        self._sessions[fp] = sess
        return sess

    def close(self):
        for sess in list(self._sessions.values()):
            sess.close()
        self._sessions.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


#: Process-wide cache, lazily built by :func:`shared_cache`.
_SHARED_CACHE = None


def shared_cache(**kwargs):
    """One :class:`ICESessionCache` per PROCESS, surviving re-execution of a study script.

    A cache held at module level inside a study script does not survive ``runpy.run_path``, which
    re-executes the file and resets its globals -- so a sweep driver that ran three points in one
    process still factorised three times, which is exactly the cost it was written to avoid. This
    module is imported normally and therefore lives in ``sys.modules`` for the life of the process,
    so a singleton parked here does survive.

    Worth being concrete about the size of the prize, because it is larger than the GPU port's:
    the system matrix depends on the stack and the floorplan GEOMETRY, not on power values, so
    sweeping die power, the kernel, the MR target or dt_max reuses one factorisation for the whole
    sweep. An audit of the accelerator study found 42 runs sharing 4 distinct matrices -- 38
    redundant factorisations at ~430 s each, 4.6 hours, paid purely for process isolation.

    ``kwargs`` are used only when the singleton is first built.
    """
    global _SHARED_CACHE
    if _SHARED_CACHE is None:
        _SHARED_CACHE = ICESessionCache(**kwargs)
    return _SHARED_CACHE


def reset_shared_cache():
    """Drop the process-wide cache, closing its sessions. For tests, and for a driver that wants
    to reclaim the memory a factorisation pins between unrelated sweeps."""
    global _SHARED_CACHE
    if _SHARED_CACHE is not None:
        try:
            _SHARED_CACHE.close()
        except Exception:
            LOGGER.warning('shared cache did not close cleanly', exc_info=True)
        _SHARED_CACHE = None
