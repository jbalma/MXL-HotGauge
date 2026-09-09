"""Evaluate a BSIM-CMG card in a **real simulator**, instead of in an analytic limit.

What this replaces
------------------
:mod:`HotGauge.power.device_leakage` reads the ASAP7 card's temperature parameters and puts them
into the analytic off-state limit -- a barrier-limited exponential with a power-law prefactor. It
is honest about being an approximation, and about being *fitted to the very CACTI table it
criticises*, so it inherits that table's level and only its shape is independent.

This module removes both caveats. It runs the card in ngspice against the compiled BSIM-CMG
Verilog-A, so the answer is the vendor's model evaluating the vendor's parameters: every one of
the card's ~130 parameters is in play, not the eight the analytic form uses, and the level is the
model's own rather than something borrowed from CACTI.

The toolchain this needs, and why it is not in the repo
------------------------------------------------------
``docs/BSIMCMG_TOOLCHAIN.md`` builds it under ``spice_toolchain/`` (gitignored, ~40 GB of build
tree for a few hundred KB of product):

* **ngspice 47 from source** -- the conda-forge package is built ``--disable-osdi`` and has no
  BSIM-CMG, so it cannot evaluate this card at all.
* **OpenVAF** compiling ``bsimcmg.va`` to ``bsimcmg.osdi``, an OSDI shared object ngspice loads at
  run time with its ``osdi`` command.

`[!]` **``osdi`` and ``pre_osdi`` are two different things, and only one of them works here.**
``osdi`` is an interactive/control command (``src/frontend/commands.c:289``) and it runs *after*
the netlist is parsed -- by which time ``.model ... bsimcmg`` has already been rejected as
"Unknown model type" and the instance line has already failed to bind. ``pre_osdi`` is not a
command at all: ``src/frontend/inp.c:786`` strips the ``pre_`` prefix off lines in a ``.control``
section and runs them *before* parsing, which is the only ordering that works. That is why
``pre_osdi`` at the interactive prompt correctly reports "no such command" on a perfectly good
build -- the doc's Checkpoint 1 tests the wrong spelling. Use ``osdi <path>`` at the prompt to
check the build, and ``pre_osdi <path>`` inside the deck to actually load a model.

Both paths are located by :func:`toolchain`, which raises rather than silently falling back to a
simulator that would answer with the wrong model.

`[!]` Three things about the card that produce plausible wrong answers
----------------------------------------------------------------------
1. **There is no ``level`` with OSDI.** The vendored card's ``level = 17`` names a *built-in*
   ngspice model that does not exist. The generated deck writes ``.model <name> <module> ...``
   instead, where ``<module>`` is the Verilog-A module name. The vendored file is never rewritten
   in place -- :func:`render_model_card` builds a fresh deck from the parsed dictionary -- so its
   provenance stays intact.
2. **Five terminals, not four.** ``module bsimcmg(d, g, s, e, t)`` -- drain, gate, source,
   substrate and a **thermal** node. A four-node instance line binds silently wrong.
3. **The module name depends on the version.** 111.2.1 declares ``bsimcmg_va``; 110.0.0 declares
   ``bsimcmg`` unless ``__XYCE__`` is defined, in which case it is ``bsimcmg_va``. Guessing gets a
   "unknown model" error at best. :func:`module_name_of` reads it out of the ``.va`` source under
   the same preprocessor conditions OpenVAF was given.

`[!]` And one about parameters. The card declares ``version = 107``; the compiled model is 110 or
111. A parameter the model does not know is the failure mode that produces a *plausible* wrong
curve, so :func:`unknown_parameters` reports them explicitly and the driver records them in the
evidence file rather than letting them pass.
"""
import os
import re
import math
import subprocess

#: Parameters that describe the *card format*, not the device -- never emitted into a deck.
_RESERVED = ('__type__', '__level__')

#: Parsed-card keys that name the model version. Kept in the deck: the model checks it.
VERSION_KEY = 'version'


def repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def toolchain(ngspice=None, osdi=None):
    """``(ngspice_binary, bsimcmg_osdi)``, or a :class:`RuntimeError` naming what is missing.

    Overridable with ``$NGSPICE_BIN`` / ``$BSIMCMG_OSDI`` so a differently-placed build can be
    used without editing code. **There is deliberately no fallback to a ``ngspice`` on ``PATH``**:
    the conda-forge build is present in this project's own environment, it has neither OSDI nor
    BSIM-CMG, and silently answering with the wrong model is the outcome this whole exercise
    exists to prevent.
    """
    root = os.path.join(repo_root(), 'spice_toolchain')
    ng = ngspice or os.environ.get('NGSPICE_BIN') or os.path.join(root, 'install', 'bin', 'ngspice')
    os_ = osdi or os.environ.get('BSIMCMG_OSDI') or os.path.join(root, 'osdi', 'bsimcmg.osdi')
    missing = [p for p in (ng, os_) if not os.path.exists(p)]
    if missing:
        raise RuntimeError('BSIM-CMG toolchain not built: missing {}. See docs/BSIMCMG_TOOLCHAIN.md'
                           .format(', '.join(missing)))
    return ng, os_


def have_toolchain():
    try:
        toolchain()
        return True
    except RuntimeError:
        return False


_MODULE_RE = re.compile(r'^\s*module\s+(\w+)\s*\(', re.M)
_IFDEF_RE = re.compile(r'^\s*`(ifdef|ifndef|else|endif)\s*(\w*)', re.M)


def module_name_of(va_path, defines=()):
    """The module name a ``.va`` file declares, honouring ``\\`ifdef`` the way OpenVAF will.

    110.0.0 wraps the declaration in ``\\`ifdef __XYCE__ ... \\`else ... \\`endif`` with a
    *different name in each branch*, so reading the first ``module`` line gets the wrong one half
    the time. This walks the conditionals with the same define set the compile used.
    """
    defines = set(defines)
    stack = []            # True while the enclosing branches are all active
    with open(va_path) as f:
        for line in f:
            m = _IFDEF_RE.match(line)
            if m:
                kind, name = m.group(1), m.group(2)
                if kind == 'ifdef':
                    stack.append(name in defines)
                elif kind == 'ifndef':
                    stack.append(name not in defines)
                elif kind == 'else' and stack:
                    stack[-1] = not stack[-1]
                elif kind == 'endif' and stack:
                    stack.pop()
                continue
            if all(stack):
                m = _MODULE_RE.match(line)
                if m:
                    return m.group(1)
    raise ValueError('no active module declaration in {} with defines {}'
                     .format(va_path, sorted(defines)))


def render_model_card(device, model_name, module, exclude=()):
    """``.model`` lines for an OSDI module, from a :func:`~HotGauge.power.spice_cards.parse_card`
    dictionary.

    The card is the vendor's file and stays as retrieved; this is the *generated copy* the doc
    calls for. ``level`` is dropped (OSDI has none) and everything else is passed through in sorted
    order so two runs produce byte-identical decks.
    """
    exclude = {e.lower() for e in exclude}
    params = sorted(k for k in device
                    if k not in _RESERVED and k != 'level' and k not in exclude)
    lines = ['.model {} {}'.format(model_name, module)]
    for k in params:
        lines.append('+ {} = {!r}'.format(k, device[k]))
    return '\n'.join(lines)


def effective_width_um(device, nfin=1):
    """Electrical width of a FinFET in um: ``nfin * (2*hfin + tfin)``.

    A FinFET has no ``W`` to divide by, so "nA/um" needs the gate's wrap-around perimeter -- two
    sidewalls of height ``hfin`` plus the top of thickness ``tfin``, from the card. Getting this
    wrong moves every absolute number without changing the shape, which is why it is computed from
    the card rather than assumed.
    """
    from HotGauge.power.spice_cards import require
    hfin, tfin = require(device, 'hfin', 'tfin')
    return nfin * (2.0 * hfin + tfin) * 1e6


#: Fins per device. **Not cosmetic** -- see :func:`ioff_deck`.
DEFAULT_NFIN = 1000


def ioff_deck(model_card, model_name, temps_C, osdi_path, vdd=0.7, vgs=0.0, nfin=DEFAULT_NFIN,
              l=None, extra_instance='', klu=True):
    """A deck that solves the off state at each temperature and prints the drain current.

    One ``.control`` loop rather than one process per point, so every temperature sees the
    identically-parsed model. Four things in here are not obvious, and the last one changes
    answers:

    * ``pre_osdi`` must come first, and must be inside ``.control`` -- see the module docstring.
    * The instance is ``N1``: ngspice binds OSDI devices by the ``N`` prefix.
    * The thermal terminal is tied to ground. The card sets ``shmod = 0``, so self-heating is off
      and that node carries no equation; left floating it is a singular row in the matrix.
    * `[!]` **``nfin`` defaults to 1000, and one fin gives a wrong cold-end answer.** A single
      7 nm fin leaks a few pA, and the linear solve cannot resolve a branch current below
      ~2e-13 A -- with the default SPARSE solver every value comes back an exact multiple of
      2**-43 A, which looks like a curve and is quantisation. Since DC current is exactly linear
      in ``nfin`` (no self-heating, so nothing couples the fins), simulating a thousand of them
      and dividing lifts the whole curve clear of that floor at no physical cost. Measured, the
      200 K point moves 70 % between ``nfin=1`` and the converged value once GIDL is off. Going
      much further is not free either: at ``nfin=1e7`` the *hot* end starts losing digits.
      ``klu`` also matters, by ~2 % at 250 K, and is on by default.

    Anything quoting these numbers should confirm convergence by re-running at 10x ``nfin`` --
    the driver does, and records it.
    """
    inst = 'N1 d g 0 0 0 {}'.format(model_name)
    if l is not None:
        inst += ' l={!r}'.format(l)
    inst += ' nfin={:d}'.format(int(nfin))
    if extra_instance:
        inst += ' ' + extra_instance
    body = [
        '* off-state leakage vs temperature -- generated, do not edit',
        model_card,
        'Vd d 0 dc {!r}'.format(vdd),
        'Vg g 0 dc {!r}'.format(vgs),
        inst,
        '.control',
        'pre_osdi {}'.format(osdi_path),
    ]
    if klu:
        body.append('option klu')
    for t in temps_C:
        body += ['option temp = {!r}'.format(float(t)),
                 'op',
                 'echo "IOFF {!r} $&i(vd)"'.format(float(t))]
    body += ['quit', '.endc', '.end', '']
    return '\n'.join(body)


_IOFF_RE = re.compile(r'^IOFF\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*$', re.M)
#: ngspice reports a model parameter the OSDI module does not define with this wording.
_UNKNOWN_RE = re.compile(r'unrecognized|unknown parameter|not a (?:valid|known) parameter'
                         r'|no such parameter', re.I)


def run_deck(deck_text, workdir, ngspice=None, osdi=None, name='deck'):
    """Write the deck, ``osdi``-load the compiled model, run in batch, return the raw output.

    Returns ``(stdout_plus_stderr, deck_path)``. Nothing is parsed here -- the caller decides what
    a failure means, and the full log is kept so a wrong answer can be traced to its warnings.
    """
    ng, _ = toolchain(ngspice, osdi)
    if not os.path.isdir(workdir):
        os.makedirs(workdir)
    deck_path = os.path.join(workdir, name + '.sp')
    with open(deck_path, 'w') as f:
        f.write(deck_text)
    # -a: run the .control block without needing a .plot/.print. The model is loaded by the deck's
    # own `pre_osdi` line, not from here -- ordering, see the module docstring.
    proc = subprocess.Popen([ng, '-b', '-a', deck_path], cwd=workdir,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, universal_newlines=True)
    out, _ = proc.communicate()
    return out, deck_path


def parse_ioff(output, nfin=1):
    """``[(T_C, I_drain_A_per_fin), ...]`` from the deck's echoed lines, sign-corrected.

    ``i(vd)`` is the current *into* the source's positive terminal, so an n-FET leaking from drain
    to source reports it negative. The magnitude is what a leakage table wants. Dividing by
    ``nfin`` undoes the numerical scaling described in :func:`ioff_deck` -- pass the same value.
    """
    return [(float(t), abs(float(i)) / nfin) for t, i in _IOFF_RE.findall(output)]


def unknown_parameters(output):
    """Model parameters the simulator complained about -- the silent-wrong-answer failure mode.

    The card is version 107 and the compiled model is 110 or 111, so some of its 130-odd
    parameters may not exist any more. A dropped parameter does not fail the run; it produces a
    different device. Every complaint is surfaced so the driver can record it.
    """
    return [l.strip() for l in output.splitlines() if _UNKNOWN_RE.search(l)]


# ---------------------------------------------------------------------------------------------
# Beyond I_off: the gate sweep that gives V_t(T), and the diagonal that gives I_dsat(V, T)
# ---------------------------------------------------------------------------------------------
# `[!]` Until §P0.18 the toolchain produced ONE curve -- off-state leakage vs temperature -- and
# the project's threshold voltage was an analytic parameter while its V/F curve came from the
# IRDS 2024 roadmap table (docs/METHODS.md §3). The two decks below are the natural additions
# that note asked for. They are the same ngspice + OSDI + BSIM-CMG evaluation of the same
# ASAP7 card, so what they add is not a new device but two more views of the one already
# trusted: how its threshold moves with temperature, and how its drive current moves with
# supply. Everything here is one deck per sweep, for the reason ``ioff_deck`` gives -- every
# point must see the identically-parsed model.


def _deck_prelude(title, model_card, model_name, osdi_path, vdd, nfin, l, extra_instance, klu):
    inst = 'N1 d g 0 0 0 {}'.format(model_name)
    if l is not None:
        inst += ' l={!r}'.format(l)
    inst += ' nfin={:d}'.format(int(nfin))
    if extra_instance:
        inst += ' ' + extra_instance
    body = [title, model_card,
            'Vd d 0 dc {!r}'.format(float(vdd)),
            'Vg g 0 dc 0',
            inst,
            '.control',
            'pre_osdi {}'.format(osdi_path)]
    if klu:
        body.append('option klu')
    return body


def iv_deck(model_card, model_name, temps_C, osdi_path, vgs_V, vds_V, vdd=0.7,
            nfin=DEFAULT_NFIN, l=None, extra_instance='', klu=True, tag='IV'):
    """A deck that solves ``I_d`` on a (temperature x V_ds x V_gs) grid and echoes each point.

    Same conventions as :func:`ioff_deck` -- ``pre_osdi`` first, five terminals, thermal node
    grounded, ``nfin`` as a numerical lift, KLU on. Each echoed line is
    ``<tag> <T_C> <V_ds> <V_gs> <i(vd)>`` so one regular expression reads the whole grid back.
    """
    body = _deck_prelude('* I-V grid -- generated, do not edit', model_card, model_name,
                         osdi_path, vdd, nfin, l, extra_instance, klu)
    for t in temps_C:
        body.append('option temp = {!r}'.format(float(t)))
        for vds in vds_V:
            body.append('alter vd = {!r}'.format(float(vds)))
            for vgs in vgs_V:
                body += ['alter vg = {!r}'.format(float(vgs)), 'op',
                         'echo "{} {!r} {!r} {!r} $&i(vd)"'.format(tag, float(t), float(vds),
                                                                   float(vgs))]
    body += ['quit', '.endc', '.end', '']
    return '\n'.join(body)


#: Linear-regime drain bias for the threshold-voltage extraction [V]. Small enough that the
#: channel is uniform, large enough that the current is well above the solver floor at
#: ``DEFAULT_NFIN``.
DEFAULT_VDS_LIN = 0.05


def vt_deck(model_card, model_name, temps_C, osdi_path, vdd=0.7, vds_lin=DEFAULT_VDS_LIN,
            vgs_step=0.025, **kw):
    """The gate sweep behind ``V_t(T)``: ``V_gs`` from 0 to ``vdd`` at ``V_ds`` linear and at ``vdd``.

    Two drain biases because a threshold is a *criterion*, not a property: the linear one gives
    the channel's own threshold and subthreshold swing, the saturated one gives ``V_t,sat`` and,
    against the linear one, DIBL. Both are extracted downstream by :func:`constant_current_vt`
    and :func:`subthreshold_swing_mV_per_dec` from the same echoed grid, tag ``VT``.
    """
    n = int(round(float(vdd) / float(vgs_step)))
    vgs = [i * float(vgs_step) for i in range(n + 1)]
    return iv_deck(model_card, model_name, temps_C, osdi_path, vgs_V=vgs,
                   vds_V=(float(vds_lin), float(vdd)), vdd=vdd, tag='VT', **kw)


def idsat_deck(model_card, model_name, temps_C, osdi_path, v_V, vdd=0.7, nfin=DEFAULT_NFIN,
               l=None, extra_instance='', klu=True, tag='ION'):
    """The diagonal ``V_gs = V_ds = V`` sweep behind a device-derived V/F curve.

    A logic gate's delay goes as ``C V / I_on(V)``, so ``f(V) ~ I_on(V) / V`` up to a constant
    that the anchor fixes. Sweeping the diagonal at each temperature gives that shape from the
    card rather than from the alpha-power law's assumed exponent -- which is the one number
    ``irds_vf`` says the roadmap does not supply. Echoed as ``<tag> <T_C> <V> <V> <i(vd)>`` so
    :func:`parse_iv` reads it with the same regular expression.
    """
    body = _deck_prelude('* I_on along V_gs = V_ds -- generated, do not edit', model_card,
                         model_name, osdi_path, vdd, nfin, l, extra_instance, klu)
    for t in temps_C:
        body.append('option temp = {!r}'.format(float(t)))
        for v in v_V:
            body += ['alter vd = {!r}'.format(float(v)), 'alter vg = {!r}'.format(float(v)),
                     'op', 'echo "{} {!r} {!r} {!r} $&i(vd)"'.format(tag, float(t), float(v),
                                                                     float(v))]
    body += ['quit', '.endc', '.end', '']
    return '\n'.join(body)


def parse_iv(output, nfin=1, tag='IV'):
    """``[(T_C, V_ds, V_gs, I_A_per_fin), ...]`` from an :func:`iv_deck` / :func:`idsat_deck` log.

    Magnitude, per fin -- see :func:`parse_ioff` for why both.
    """
    rx = re.compile(r'^{}\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*$'
                    .format(re.escape(tag)), re.M)
    return [(float(t), float(vds), float(vgs), abs(float(i)) / nfin)
            for t, vds, vgs, i in rx.findall(output)]


# ---------------------------------------------------------------------------------------------
# Extraction -- pure arithmetic on the echoed grid, so it is testable without a simulator
# ---------------------------------------------------------------------------------------------

#: The constant-current threshold criterion: ``I_th = I_REF * W_eff / L`` per device. 100 nA per
#: square is the conventional figure; it is a CONVENTION, and a threshold is only comparable to
#: another extracted the same way. Stated here once so every number downstream shares it.
DEFAULT_I_REF_A_PER_SQUARE = 100e-9


def threshold_current_A(device, nfin=1, i_ref_A_per_square=DEFAULT_I_REF_A_PER_SQUARE):
    """``I_REF * W_eff / L_drawn`` for a FinFET of ``nfin`` fins, in amps.

    ``W_eff`` is the wrap-around perimeter from :func:`effective_width_um`; ``L`` is the card's
    drawn gate length. Drawn rather than effective because the effective length is a model
    internal (``lint`` enters with a sign that differs between BSIM-CMG versions) and the
    criterion is a convention anyway -- what matters is that the same one is used everywhere.
    """
    if 'l' not in device:
        raise KeyError("card has no 'l' (drawn gate length); cannot form a W/L criterion")
    W_um = effective_width_um(device, nfin=nfin)
    L_um = float(device['l']) * 1e6
    return float(i_ref_A_per_square) * W_um / L_um


def constant_current_vt(vgs_V, i_A, i_th_A):
    """Gate voltage at which the current first crosses ``i_th``, interpolated in ``log I``.

    ``None`` if the sweep never crosses, or already exceeds ``i_th`` at its first point -- both
    mean the criterion does not apply to this sweep, which is a result rather than an error.
    """
    import numpy as np
    v = np.asarray(vgs_V, dtype=float)
    i = np.asarray(i_A, dtype=float)
    if len(v) != len(i) or len(v) < 2:
        raise ValueError('need matching V and I arrays of at least two points')
    if i[0] >= i_th_A:
        return None
    above = np.nonzero(i >= i_th_A)[0]
    if len(above) == 0:
        return None
    k = int(above[0])
    v0, v1, i0, i1 = v[k - 1], v[k], i[k - 1], i[k]
    if i0 <= 0 or i1 <= 0:
        return None
    f = (math.log(i_th_A) - math.log(i0)) / (math.log(i1) - math.log(i0))
    return float(v0 + f * (v1 - v0))


def subthreshold_swing_mV_per_dec(vgs_V, i_A, i_lo_A, i_hi_A):
    """Least-squares ``dV_gs / d(log10 I)`` over the points with ``i_lo <= I <= i_hi`` [mV/dec].

    Bounded by CURRENT rather than by voltage so the window sits in the same physical regime at
    every temperature; a fixed voltage window walks out of the subthreshold region as ``V_t``
    moves. Give it at least two decades -- at 60 mV/dec one decade is 60 mV, which a 25 mV gate
    step samples three times and a 50 mV step once. ``None`` if fewer than two points fall in.
    """
    import numpy as np
    v = np.asarray(vgs_V, dtype=float)
    i = np.asarray(i_A, dtype=float)
    m = (i >= i_lo_A) & (i <= i_hi_A) & (i > 0)
    if int(m.sum()) < 2:
        return None
    x = np.log10(i[m])
    y = v[m]
    slope = np.polyfit(x, y, 1)[0]
    return float(slope * 1000.0)


def dibl_mV_per_V(vt_lin_V, vt_sat_V, vds_lin_V, vds_sat_V):
    """Drain-induced barrier lowering: ``(V_t,lin - V_t,sat) / (V_ds,sat - V_ds,lin)`` [mV/V]."""
    if vt_lin_V is None or vt_sat_V is None:
        return None
    return float((vt_lin_V - vt_sat_V) / (vds_sat_V - vds_lin_V) * 1000.0)


def fit_alpha_power(v_V, i_on_A, vt_V):
    """Fit ``I_on = k (V - V_t)^alpha`` over the points above threshold; returns ``(alpha, k, rms)``.

    ``alpha`` is the velocity-saturation exponent the alpha-power delay law needs and the roadmap
    does not give (``irds_vf.DEFAULT_ALPHA`` is a textbook 1.4). ``rms`` is the residual in
    ``ln I``, so a poor fit is visible rather than absorbed into the exponent.
    """
    import numpy as np
    v = np.asarray(v_V, dtype=float)
    i = np.asarray(i_on_A, dtype=float)
    m = (v > vt_V) & (i > 0)
    if int(m.sum()) < 3:
        raise ValueError('need at least three points above threshold to fit alpha')
    x = np.log(v[m] - vt_V)
    y = np.log(i[m])
    alpha, lnk = np.polyfit(x, y, 1)
    rms = float(np.sqrt(np.mean((y - (alpha * x + lnk)) ** 2)))
    return float(alpha), float(math.exp(lnk)), rms
