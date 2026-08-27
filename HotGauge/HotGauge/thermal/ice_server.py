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


#: ``die INSTANCE TYPE floorplan "path";`` inside the ``stack:`` section.
_STACK_DIE_RGX = re.compile(r'^\s*die\s+(\w+)\s+(\w+)\s+floorplan\s+"([^"]+)"', re.M)


def stack_floorplans(stack_file):
    """Every powered die in a .stk as ``(instance, flp_path)``, **in power-vector order**.

    Order is the whole point of this function, and it is *not* the order the file lists.

    A ``.stk`` declares its stack top-down -- ``SINK``, then ``MR_ARRAY``, then
    ``PROCESSOR_DIE``. 3D-ICE stores layers bottom-up: ``power_grid_fill`` walks the stack
    element list backwards and indexes each element by its physical ``Offset``
    (``3d-ice/sources/power_grid.c:180``), and ``insert_power_values`` then iterates
    ``layer = 0 .. NLayers`` ascending (``power_grid.c:653``), consuming one floorplan's worth
    of powers at each source layer it meets.

    So the flat power vector runs **bottom of the stack upward**: the processor die's blocks
    first, then the array's tiles. Reversing the declaration order is therefore correct and
    the file order would be exactly wrong -- it would put cooling powers on processor blocks
    and return a plausible, wrong field.

    Verified end to end against the one-shot Emulator by
    ``test_ice_server.py::test_two_die_server_matches_oneshot_emulator_by_name``, which uses an
    asymmetric power pattern so a transposed order cannot pass.
    """
    with open(stack_file) as f:
        text = f.read()
    m = re.search(r'\bstack\s*:(.*?)(?:solver\s*:|output\s*:|\Z)', text, re.S)
    if not m:
        raise ICEServerError('no stack section in {}'.format(stack_file))
    base = os.path.dirname(os.path.abspath(stack_file))
    out = []
    for inst, _typ, path in _STACK_DIE_RGX.findall(m.group(1)):
        if not os.path.isabs(path):
            path = os.path.join(base, path)
        out.append((inst, path))
    if not out:
        raise ICEServerError('no floorplan reference in {}'.format(stack_file))
    out.reverse()                      # declaration order is top-down; the wire is bottom-up
    return out


#: ``Tflp (INSTANCE, "file", QUANTITY, INSTANT) ;`` in the ``output:`` section.
_TFLP_RGX = re.compile(
    r'\bTflp\s*\(\s*(\w+)\s*,\s*"[^"]*"\s*,\s*(\w+)\s*,\s*(\w+)\s*\)', re.I)

_QTY_WORDS = {'average': QTY_AVERAGE, 'maximum': QTY_MAXIMUM,
              'minimum': QTY_MINIMUM, 'gradient': QTY_GRADIENT}
_INSTANT_WORDS = {'final': INSTANT_FINAL, 'slot': INSTANT_SLOT, 'step': INSTANT_STEP}


def tflp_output_dies(stack_file, quantity=QTY_AVERAGE, instant=INSTANT_FINAL):
    """Die instances whose Tflp values come back for a given filter, in reply order.

    Temperatures and powers do **not** travel the same way, and conflating them is the whole
    hazard this function exists to remove. Powers are one flat vector over every source layer,
    bottom-up (:func:`stack_floorplans`). Temperatures come back per *inspection point*: the
    server returns one block of values for each ``Tflp`` instruction matching the requested
    instant/type/quantity, in the order the ``output:`` section declares them
    (``3D-ICE-Server.c``, ``TDICE_SEND_OUTPUT``).

    With one die and one output instruction the two orders coincide, which is why zipping power
    names against temperatures worked until now. With a processor die and a photonic array they
    need not, and a stack that reported the array first would have mapped tile temperatures onto
    processor blocks without any error.
    """
    with open(stack_file) as f:
        text = f.read()
    m = re.search(r'\boutput\s*:(.*)\Z', text, re.S)
    if not m:
        raise ICEServerError('no output section in {}'.format(stack_file))
    body = re.sub(r'//[^\n]*', '', m.group(1))
    out = []
    for inst, qty, when in _TFLP_RGX.findall(body):
        if (_QTY_WORDS.get(qty.lower()) == quantity
                and _INSTANT_WORDS.get(when.lower()) == instant):
            out.append(inst)
    return out


def stack_floorplan_path(stack_file):
    """The .flp a .stk points at (``die NAME IC floorplan "path";``).

    The **first in file order**, i.e. the topmost powered die. Retained for single-die callers
    and for tests that predate multi-die support; anything that has to line up with a power
    vector wants :func:`stack_floorplans` instead.
    """
    flps = stack_floorplans(stack_file)
    return flps[-1][1] if len(flps) > 1 else flps[0][1]


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
        self._temp_names = {}
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

    @staticmethod
    def other_servers_running(exclude_pid=None):
        """Other 3D-ICE-Server processes on this machine, as ``[(pid, elapsed, cmdline)]``.

        A server takes roughly fifteen cores while it factorises. If the Python process that
        launched one is SIGKILLed -- ``pkill``, an OOM kill, a scheduler timeout -- ``atexit``
        never runs and the server survives indefinitely, quietly starving every factorisation
        that follows. The startup timeout then reports itself as a problem-size limit, which is
        the wrong diagnosis and cost an hour to unpick.

        Best-effort: no ``ps``, no diagnosis, and the timeout message just omits this line.
        """
        import subprocess as _sp
        try:
            out = _sp.run(['ps', '-eo', 'pid,etime,args'], capture_output=True, text=True,
                          timeout=10).stdout
        except Exception:      # noqa: BLE001 - a diagnostic must never be the thing that fails
            return []
        rows = []
        for line in out.splitlines()[1:]:
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            # Match the EXECUTABLE, not the line. A shell command that merely mentions
            # 3D-ICE-Server -- this project's own diagnostics do -- is not a running server, and
            # a detector that reports one would send the reader hunting a process that is a grep.
            if os.path.basename(parts[2].split()[0]) != '3D-ICE-Server':
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            if exclude_pid is not None and pid == exclude_pid:
                continue
            rows.append((pid, parts[1], parts[2]))
        return rows

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
            mine = self._proc.pid if self._proc is not None else None
            others = self.other_servers_running(exclude_pid=mine)
            self.close()
            msg = ('server did not become ready within {:.0f} s'
                   .format(self.startup_timeout_s)
                   + '. Startup is the FACTORISATION and it scales as N^1.67, so this is '
                     'usually a problem-size limit rather than a hang: raise '
                     'MXL_ICE_STARTUP_TIMEOUT_S, or coarsen the grid.')
            if others:
                # Check this BEFORE blaming the problem size. A single orphan takes ~15 cores
                # and will time out every factorisation that follows it, forever.
                msg += ('\n\nBUT FIRST: {} other 3D-ICE-Server process(es) are running on this '
                        'machine and each takes roughly fifteen cores. If nothing is '
                        'deliberately using them they are orphans from a killed run, and they '
                        'are the reason this timed out:\n'.format(len(others)))
                for pid, elapsed, cmd in others[:5]:
                    msg += '  pid {:<8} up {:<12} {}\n'.format(pid, elapsed, cmd[:90])
                msg += 'Kill them and retry before touching the grid or the timeout.'
            raise ICEServerError(msg)

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
        """Element names in **power-vector order**, across every powered die in the stack.

        One die is the common case and then this is just that floorplan's names. With a photonic
        array the stack has two, and the vector runs bottom-up -- processor blocks first, then
        tiles. :func:`stack_floorplans` owns that ordering and explains why.

        Two things are checked rather than assumed, because both fail silently:

        * the total must equal what the server reports, or powers land on the wrong elements;
        * names must be unique **across** dies, since :meth:`solve_named` keys by name. A tile
          called ``L3_4`` would collide with the processor block of that name and one of them
          would quietly get the other's power.
        """
        if self._names is None:
            names, per_die = [], []
            for inst, flp in stack_floorplans(self.stack_file):
                got = flp_element_names(flp)
                per_die.append((inst, len(got)))
                names.extend(got)
            if len(set(names)) != len(names):
                seen, dupes = set(), []
                for n in names:
                    if n in seen and n not in dupes:
                        dupes.append(n)
                    seen.add(n)
                raise ICEServerError(
                    'element names collide across dies ({}): e.g. {}. solve_named keys by name, '
                    'so one die would silently take the other\'s power.'
                    .format(', '.join('{}={}'.format(i, n) for i, n in per_die),
                            sorted(dupes)[:5]))
            if self.n_elements is not None and len(names) != self.n_elements:
                raise ICEServerError(
                    'floorplans have {} named elements ({}) but the server reports {}. Powers '
                    'would land on the wrong blocks.'
                    .format(len(names), ', '.join('{}={}'.format(i, n) for i, n in per_die),
                            self.n_elements))
            self._names = names
        return self._names

    def temperature_names(self, quantity=QTY_AVERAGE, instant=INSTANT_FINAL):
        """Element names lining up with :meth:`temperatures`, in reply order.

        Not the same list as :meth:`element_names` in general -- see :func:`tflp_output_dies`.
        Falls back to the power order when the stack has a single powered die, which keeps
        single-die stacks working even if their output section is written unusually.
        """
        key = (quantity, instant)
        cached = self._temp_names.get(key)
        if cached is not None:
            return cached
        by_inst = dict(stack_floorplans(self.stack_file))
        reported = tflp_output_dies(self.stack_file, quantity=quantity, instant=instant)
        if not reported:
            if len(by_inst) > 1:
                raise ICEServerError(
                    'no Tflp output instruction in {} matches quantity={} instant={}, but the '
                    'stack has {} powered dies -- which die the reply describes cannot be '
                    'inferred.'.format(self.stack_file, quantity, instant, len(by_inst)))
            names = list(self.element_names())
        else:
            names = []
            for inst in reported:
                flp = by_inst.get(inst)
                if flp is None:
                    raise ICEServerError(
                        'output section names die {!r}, which is not a powered die in {}. '
                        'Known: {}'.format(inst, self.stack_file, sorted(by_inst)))
                names.extend(flp_element_names(flp))
        self._temp_names[key] = names
        return names

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
        return dict(zip(self.temperature_names(**{k: kw[k] for k in ('quantity', 'instant')
                                                  if k in kw}), temps))

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
    # Every powered die, not just the first. With a photonic array the tile floorplan is as much
    # a part of the system matrix as the processor's -- changing the pitch changes the geometry
    # and must rebuild the session, while changing tile powers must not.
    for inst, flp in stack_floorplans(stack_file):
        h.update(inst.encode('utf-8'))
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
