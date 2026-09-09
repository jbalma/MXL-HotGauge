"""Off-state leakage vs temperature, from a published device card instead of an extrapolation.

The problem this replaces
-------------------------
The pipeline's leakage curve is built from McPAT/CACTI over **310-400 K** and nothing else, because
``McPAT/cacti/io.cc:1547`` refuses any other temperature. Outside that window the project has been
guessing in two directions, and both guesses are load-bearing:

* **Below 310 K** the curve *clamps* -- it is flat because there is no data, not because leakage
  stops falling. The cold-zone prize (how much power a sub-ambient die saves) rests on it, and was
  recorded as uncertain by ~2.3x, ~50x at the extreme.
* **Above 400 K** an unbounded Arrhenius tail takes over: 36x at 400 K, 184000x at 600 K. §P0.11
  showed the flat-die ceiling at 1.0-1.2 W/mm^2 is a direct function of this curve, so the tail is
  no longer a footnote -- it sets a headline number.

`[!]` SUPERSEDED as the primary answer -- the card is simulated now
------------------------------------------------------------------
This module was written when **no simulator on this machine could evaluate BSIM-CMG**. That is no
longer true: ``docs/BSIMCMG_TOOLCHAIN.md`` builds ngspice 47 with OSDI and compiles the BSIM-CMG
Verilog-A with OpenVAF, and ``examples/device_leakage_spice.py`` runs the ASAP7 card in it. **For
anything quotable, use :func:`load_simulated_curve`**, at the bottom of this file, which reads
that run's output.

What survives here is the analytic **off-state limit** of the BSIM-CMG temperature model,
parameterised from the same card: at V_gs = 0 the drain current reduces to a barrier-limited
exponential with a power-law prefactor, with every temperature coefficient read from the vendor's
file rather than assumed. It is kept for two reasons, both of them still live:

* it is an **independent check** on the simulation, built from different assumptions, and over
  310-400 K -- the only window McPAT itself will simulate -- the two agree within 2x;
* it models **subthreshold conduction only**, which turns out to be the interesting difference:
  the simulator says the cold end is dominated by GIDL, a mechanism this model omits by
  construction. See the note above :class:`SimulatedLeakageCurve`.

Its two weaknesses are why it is no longer the answer: it models one mechanism, and its two free
parameters are fitted to the very CACTI table it criticises, so it inherits that table's *level*
and only its *shape* is independent.

The model
---------
For a fixed off-state bias the two surviving temperature dependences are the prefactor (thermal
voltage squared, times mobility) and the barrier::

    I(T) / I(T_r) = (T/T_r)**(2 + ute) * exp( (q/k) * [ Phi(T_r)/T_r - Phi(T)/T ] )

``ute`` is the card's mobility temperature exponent (-0.7). ``Phi`` is an effective barrier in
volts, and how it moves with temperature is the whole question -- so it is asked as an experiment
rather than assumed. Two forms, **both with exactly two free parameters**, so the comparison is
fair:

* :class:`VarshniBarrier` -- the barrier follows the **card's own bandgap**. Silicon's gap narrows
  with temperature by Varshni's law, with alpha and beta given in the card as ``tbgasub`` and
  ``tbgbsub``, and the band edge carries roughly half of that into the source barrier. Free:
  ``phi0`` and the subthreshold ideality ``n``. **The shape is the vendor's, not ours.**
* :class:`LinearBarrier` -- the textbook stand-in, ``Phi(T) = phi0 + b*(T - T_r)``, i.e. a constant
  dV_th/dT. Free: ``phi0/n`` and ``b/n``.

If the Varshni form -- whose temperature shape is fixed by the card -- predicts points it was not
fitted to better than the free-slope form, the card is carrying real information and its
extrapolation is worth trusting. If it does not, this is an over-elaborate curve fit and should be
reported as one. :func:`extrapolation_test` is what decides it.

`[!]` The two fitted parameters are DEGENERATE, and only the curve means anything
--------------------------------------------------------------------------------
Over a 90 K fitting window the barrier height and its temperature slope trade off almost exactly:
recovering a synthetic curve returns parameters ~1 % off while reproducing the curve itself to
1e-5. So a fitted ``phi0`` is **not** a measured barrier height and a fitted ``b`` is **not**
dV_th/dT, and neither may be quoted as one. What *is* meaningful is that the two independent
barrier forms -- one with its shape locked to the card's bandgap, one with a free slope -- agree
with each other to within a few percent all the way out to 500 K. That agreement is a stronger
check than parameter recovery would have been, because the forms differ where it matters.

Gate leakage is carried as an additive, temperature-independent floor. That is McPAT's own
treatment (its ``gate_W`` is identical at all eleven temperatures) and it is the term that stops
total leakage collapsing as the die is cooled. The card supports a weak dependence through ``igt``;
it is not modelled, and the floor is small enough (0.65 % of leakage at 310 K) that it only matters
deep in the cold zone -- where it is stated as a bound rather than a prediction.

`[!]` Not modelled: GIDL -- **and the simulation says that is the largest error here.** The card
enables it (``gidlmod = 1``) and gives its temperature coefficient (``tgidl``). This module
originally reasoned that GIDL "needs a negative gate bias to matter"; that is true of the gate-to-
DRAIN bias, which in the ordinary off state is ``-V_dd``, so GIDL is on in every off device rather
than in an exotic corner. Simulated, it is **98 % of the leakage at 200 K** and it sets a floor
about 40x above the gate floor assumed below. Every number from this module is therefore a lower
bound at the cold end, and the gate-floor knee it reports (~244 K) is not the real one.
"""
import numpy as np

#: Boltzmann constant over elementary charge, volts per kelvin.
K_OVER_Q = 8.617333262e-5


def varshni_eg(T_K, eg0, alpha, beta):
    """Silicon bandgap in eV: ``Eg(T) = eg0 - alpha*T**2 / (T + beta)``.

    Parameters come from the model card (``bg0sub``, ``tbgasub``, ``tbgbsub``); ASAP7's give
    1.1245 eV at 300 K, which is silicon.
    """
    T = np.asarray(T_K, dtype=float)
    return eg0 - alpha * T ** 2 / (T + beta)


class _Barrier(object):
    """Common machinery: an effective barrier Phi(T) in volts, and the current ratio it implies."""

    n_params = 2

    def __init__(self, T_ref_K, ute):
        self.T_ref_K = float(T_ref_K)
        self.ute = float(ute)

    def phi_over_n(self, T_K, params):
        raise NotImplementedError

    def ratio(self, T_K, params):
        """``I(T) / I(T_ref)`` for the off state."""
        T = np.asarray(T_K, dtype=float)
        Tr = self.T_ref_K
        prefactor = (T / Tr) ** (2.0 + self.ute)
        a_T = self.phi_over_n(T, params)
        a_r = self.phi_over_n(np.asarray([Tr], dtype=float), params)[0]
        expo = (a_r / Tr - a_T / T) / K_OVER_Q
        return prefactor * np.exp(expo)


class VarshniBarrier(_Barrier):
    """Barrier shape fixed by the card's bandgap; only its height and ideality are free.

    ``Phi(T) = phi0 + 0.5 * (Eg(T) - Eg(T_ref))`` -- the source barrier follows the band edge, and
    the band edge follows Varshni with the card's own alpha and beta. Nothing about the temperature
    *shape* is fitted, which is what makes the extrapolation test meaningful.
    """

    def __init__(self, T_ref_K, ute, eg0, alpha, beta):
        _Barrier.__init__(self, T_ref_K, ute)
        self.eg0, self.alpha, self.beta = float(eg0), float(alpha), float(beta)

    def phi_over_n(self, T_K, params):
        phi0, n = params
        d_eg = varshni_eg(T_K, self.eg0, self.alpha, self.beta) \
            - varshni_eg(self.T_ref_K, self.eg0, self.alpha, self.beta)
        return (phi0 + 0.5 * d_eg) / n

    @staticmethod
    def initial_guess():
        return np.array([0.30, 1.10])

    @staticmethod
    def bounds():
        return [(0.05, 1.50), (1.0, 2.0)]

    labels = ('phi0_V', 'n')


class LinearBarrier(_Barrier):
    """The textbook stand-in: a constant dV_th/dT, both terms free.

    ``Phi(T)/n = a + b*(T - T_ref)``. Reported as an implied ``dV_th/dT = b * n``, which is worth
    checking against the -0.5 to -1.5 mV/K a real device shows: a fit that only works at an
    unphysical slope is a fit, not a model.
    """

    def phi_over_n(self, T_K, params):
        a, b = params
        return a + b * (np.asarray(T_K, dtype=float) - self.T_ref_K)

    @staticmethod
    def initial_guess():
        return np.array([0.28, -3.0e-4])

    @staticmethod
    def bounds():
        return [(0.05, 1.20), (-3.0e-3, 0.0)]

    labels = ('a_V', 'b_V_per_K')


def barriers_from_card(device, T_ref_K):
    """``{'varshni': ..., 'linear': ...}`` built from a parsed model-card device."""
    from HotGauge.power.spice_cards import require
    ute = require(device, 'ute')
    eg0, alpha, beta = require(device, 'bg0sub', 'tbgasub', 'tbgbsub')
    return {'varshni': VarshniBarrier(T_ref_K, ute, eg0, alpha, beta),
            'linear': LinearBarrier(T_ref_K, ute)}


def fit_barrier(model, T_K, I_rel, weights=None):
    """Least squares in **log** current -- the quantity that spans four decades.

    Fitting in linear current would let the two hottest points set the whole curve and report an
    excellent fit while being wrong by 10x at 310 K, which is the end the cold-zone claim needs.
    Returns ``(params, rms_log10_residual)``.
    """
    from scipy.optimize import minimize
    T_K = np.asarray(T_K, dtype=float)
    y = np.log(np.asarray(I_rel, dtype=float))
    w = np.ones_like(y) if weights is None else np.asarray(weights, dtype=float)

    def loss(p):
        r = np.log(np.clip(model.ratio(T_K, p), 1e-300, None)) - y
        return float(np.sum(w * r ** 2))

    res = minimize(loss, model.initial_guess(), method='L-BFGS-B', bounds=model.bounds())
    p = res.x
    resid = (np.log(model.ratio(T_K, p)) - y) / np.log(10.0)
    return p, float(np.sqrt(np.mean(resid ** 2)))


def extrapolation_test(model, T_K, I_rel, n_fit):
    """Fit on the ``n_fit`` coldest points, predict the rest. The test that decides the module.

    An in-sample fit proves nothing about a curve whose entire purpose is to be evaluated outside
    the data. This holds out the hottest points -- the direction the tail is actually used in --
    and reports the error on them in decades.
    """
    T_K = np.asarray(T_K, dtype=float)
    I_rel = np.asarray(I_rel, dtype=float)
    order = np.argsort(T_K)
    T_K, I_rel = T_K[order], I_rel[order]
    if not 2 <= n_fit < len(T_K):
        raise ValueError('n_fit must leave at least one held-out point and exceed the parameter '
                         'count; got {} of {}'.format(n_fit, len(T_K)))
    p, rms_in = fit_barrier(model, T_K[:n_fit], I_rel[:n_fit])
    pred = model.ratio(T_K[n_fit:], p)
    err = np.log10(pred / I_rel[n_fit:])
    return {'params': [float(v) for v in p],
            'n_fit': int(n_fit), 'n_held_out': int(len(T_K) - n_fit),
            'fit_T_K': [float(t) for t in T_K[:n_fit]],
            'held_out_T_K': [float(t) for t in T_K[n_fit:]],
            'rms_log10_in_sample': rms_in,
            'held_out_log10_error': [float(e) for e in err],
            'max_abs_log10_error': float(np.max(np.abs(err))),
            'worst_factor': float(10 ** np.max(np.abs(err)))}


class DeviceLeakageCurve(object):
    """A fitted off-state curve, usable outside the window McPAT will simulate.

    ``total_rel(T)`` returns leakage relative to the anchor, **including** the gate floor, so it
    can be dropped in where the pipeline currently uses the extrapolated table.
    """

    def __init__(self, model, params, gate_fraction_at_ref=0.0):
        self.model = model
        self.params = np.asarray(params, dtype=float)
        self.gate_fraction_at_ref = float(gate_fraction_at_ref)

    def subthreshold_rel(self, T_K):
        return self.model.ratio(T_K, self.params)

    def total_rel(self, T_K):
        """Subthreshold falls with cooling; the gate floor does not. Their sum is what a die sees."""
        g = self.gate_fraction_at_ref
        return (1.0 - g) * self.subthreshold_rel(T_K) + g

    def floor_temperature_K(self, T_lo=150.0, T_hi=320.0, ratio=2.0):
        """Where the constant gate term starts to dominate -- the real end of the cold-zone prize.

        Returns the temperature at which subthreshold leakage has fallen to ``1/ratio`` of the gate
        floor, or None if it never does inside the bracket. Below that point, cooling further buys
        almost nothing, and *that* -- not the 310 K edge of the table -- is where the curve should
        flatten.
        """
        if self.gate_fraction_at_ref <= 0.0:
            return None
        T = np.linspace(T_lo, T_hi, 2000)
        sub = (1.0 - self.gate_fraction_at_ref) * self.subthreshold_rel(T)
        below = sub <= self.gate_fraction_at_ref / ratio
        return float(T[below][-1]) if below.any() else None


# =============================================================================================
# The simulated curve -- and why everything above it is now a cross-check rather than the answer
# =============================================================================================
#
# `[!]` Everything above this line was written under the constraint that **no simulator on this
# machine could evaluate BSIM-CMG**. That constraint is gone: ``docs/BSIMCMG_TOOLCHAIN.md`` builds
# ngspice 47 with OSDI and compiles the BSIM-CMG Verilog-A with OpenVAF, and
# ``examples/device_leakage_spice.py`` runs the ASAP7 card in it. The result is
# ``docs/evidence/device_leakage_spice_asap7.json``.
#
# What that changes, in order of how much it matters:
#
# 1. **The level is no longer borrowed.** The analytic forms above have two free parameters fitted
#    to CACTI's table, so they inherited its level and only their *shape* was independent. The
#    simulated curve is fitted to nothing at all.
# 2. **`[!]` The cold end was wrong, and in the direction that costs the project something.** The
#    analytic model carried gate leakage as the floor and put its knee at ~244 K. The simulator
#    says the floor is real but it is **GIDL** -- 98 % of the current at 200 K -- and it is
#    ~40x higher than the gate floor the analytic model assumed. Turning ``igcmod`` off barely
#    moves the curve; turning ``gidlmod`` off drops 200 K by ~40x. GIDL is precisely what the
#    docstring above says is "not modelled ... would raise leakage at both ends", and at
#    ``V_gs = 0, V_ds = V_dd`` the gate-to-drain bias is ``-V_dd``, so it is on in the *ordinary*
#    off state, not an exotic corner. **The cold-zone prize is roughly 20x smaller than the
#    analytic curve promised** (0.126 vs 0.0060 of the 330 K value at 200 K).
# 3. **The hot tail is gentler still.** At 500 K: pipeline 5820x, analytic 349x, simulated 123x.
#    P0.11's flat-die ceiling was solved on the pipeline curve and a gentler tail runs away later,
#    so that ceiling is conservative by more than P0.12 estimated.
#
# The analytic classes are kept, not deleted: they are the independent check that the simulation
# is not simply wrong, and between 310 and 400 K -- the only window McPAT itself will simulate --
# the two agree to better than 2x. Prefer :func:`load_simulated_curve` for anything quotable.

import json
import os

#: Default location of the simulated table, relative to the repo root.
SIMULATED_EVIDENCE = os.path.join('docs', 'evidence', 'device_leakage_spice_asap7.json')


class SimulatedLeakageCurve(object):
    """``I_off(T)`` read from a simulator run, interpolated in log current.

    Same ``total_rel(T)`` interface as :class:`DeviceLeakageCurve`, so it drops into the same
    call sites -- but there is no model and no fit here, only a table the simulator produced and
    the interpolation between its points.

    `[!]` **Log-linear interpolation, and NO extrapolation.** Leakage moves four decades across
    this range, so interpolating the current linearly would be wrong by tens of percent between
    10 K samples. Outside ``[T_min, T_max]`` the value is *clamped*, and ``clamped_at(T)`` says
    so, because the whole point of P0.12 was that a silent clamp got mistaken for physics. If a
    temperature outside 200-500 K is needed, run the sweep wider rather than trusting an
    extrapolation of an interpolation -- that is the mistake this module exists to undo.

    `[!]` **``mechanism`` is a bracket, not a preference.** ``'full'`` is the card as ASAP7 wrote
    it. ``'gidl_off'`` is the same card with GIDL disabled. ASAP7 is a *predictive* PDK, so its
    GIDL coefficients are a model choice rather than a measurement of a fabricated part, and the
    two curves differ by ~40x at 200 K while agreeing within 15 % above 300 K. Anything that
    depends on the cold end should be quoted across both.
    """

    def __init__(self, T_K, rel, mechanism='full', meta=None):
        order = np.argsort(np.asarray(T_K, dtype=float))
        self.T_K = np.asarray(T_K, dtype=float)[order]
        self.rel = np.asarray(rel, dtype=float)[order]
        if np.any(self.rel <= 0):
            raise ValueError('simulated currents must be positive to interpolate in log')
        self._log_rel = np.log(self.rel)
        self.mechanism = mechanism
        self.meta = meta or {}

    def clamped_at(self, T_K):
        """True wherever the requested temperature is outside the simulated range."""
        T = np.asarray(T_K, dtype=float)
        return (T < self.T_K[0]) | (T > self.T_K[-1])

    def total_rel(self, T_K):
        """Leakage relative to the anchor. Includes every mechanism the card enables.

        Named ``total_rel`` to match :class:`DeviceLeakageCurve`, but note the difference in what
        "total" means: there the gate floor was bolted on as a separate additive term, here the
        simulator has already summed subthreshold, gate and GIDL currents itself.
        """
        T = np.asarray(T_K, dtype=float)
        return np.exp(np.interp(T, self.T_K, self._log_rel))

    def floor_temperature_K(self, ratio=1.1):
        """Where cooling stops paying: the coldest T at which leakage is still ``ratio`` above its
        own minimum.

        The analytic version of this asked where subthreshold falls below the *gate* floor. That
        question has the wrong mechanism in it now, so this one does not name a mechanism at all
        -- it just finds where the simulated curve flattens, whatever is doing the flattening.
        Returns None if the curve never flattens inside the simulated range.
        """
        lo = float(np.min(self.rel))
        flat = self.rel <= ratio * lo
        return float(self.T_K[flat][-1]) if flat.any() else None


def load_simulated_curve(path=None, mechanism='full'):
    """:class:`SimulatedLeakageCurve` from an evidence file written by the SPICE driver.

    Raises rather than falling back to the analytic model: a caller that asked for the simulated
    curve and silently got a fitted one would reintroduce exactly the confusion P0.12 documented.
    """
    if path is None:
        path = os.path.join(repo_root_for_evidence(), SIMULATED_EVIDENCE)
    if not os.path.exists(path):
        raise IOError('no simulated leakage evidence at {}. Run '
                      'examples/device_leakage_spice.py (needs the toolchain in '
                      'docs/BSIMCMG_TOOLCHAIN.md)'.format(path))
    with open(path) as f:
        ev = json.load(f)
    key = {'full': 'rel_to_anchor', 'gidl_off': 'rel_to_anchor_gidl_off'}[mechanism]
    T = [r['T_K'] for r in ev['curve']]
    rel = [r[key] for r in ev['curve']]
    meta = {'anchor_K': ev['anchor_K'], 'card': ev['card'], 'bias': ev['bias'],
            'toolchain': ev['toolchain'], 'sanity': ev['sanity'],
            'numerical_convergence': ev.get('numerical_convergence'),
            'version_spread': ev.get('version_spread')}
    if not ev['sanity'].get('PASSES'):
        raise ValueError('{} records a FAILED sanity check -- the card may not have been binding; '
                         'refusing to use it'.format(path))
    return SimulatedLeakageCurve(T, rel, mechanism=mechanism, meta=meta)


def repo_root_for_evidence():
    """The repository root, from this file's location (same rule as ``spice_cards``)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def _simulated_as_leakage_model(curve, extrapolate=True, fit_from_K=430.0):
    """Turn a :class:`SimulatedLeakageCurve` into a :class:`~HotGauge.power.leakage.LeakageModel`.

    This is the bridge that lets the thermal feedback loop run on simulated device physics
    instead of on CACTI's eleven numbers. It reuses ``LeakageModel.from_table_extrapolated``
    rather than inventing a second extrapolation path, so the hot tail behaves identically to
    the pipeline's and only the *table* changes -- which is the point of the comparison.

    `[!]` **The clamp moves from 310 K down to 200 K, and that is the cold-zone result.** The
    pipeline's table stops at 300 K, so every sub-ambient claim it made was a clamp. This table
    reaches 200 K, so the cold zone is inside the data for the first time.

    `[!]` **Above 500 K it is still an extrapolation**, just a better-anchored one: the Arrhenius
    tail is fitted to simulated points from ``fit_from_K`` up rather than to McPAT's last two.
    ``fit_from_K`` defaults to 430 K -- high enough that the fit sees only the barrier-limited
    region, low enough to have ~8 points. Nothing in the studies should be reaching 500 K anyway;
    if it does, that is a runaway and the tail's job is only to let it diverge rather than to be
    accurate.
    """
    from HotGauge.power.leakage import LeakageModel
    if extrapolate:
        model = LeakageModel.from_table_extrapolated(
            curve.T_K, curve.rel, fit_from_K=fit_from_K,
            source_note=('The simulator can go hotter -- the table stops at {:.0f} K because '
                         'that is where the sweep was run, not because a tool refused. Above it '
                         'the Arrhenius tail is fitted to simulated points, so it is better '
                         'anchored than McPAT\'s but still an extrapolation.'
                         .format(curve.T_K[-1])))
    else:
        model = LeakageModel.from_table(curve.T_K, curve.rel)
    model.description = 'simulated BSIM-CMG {} ({}, {:.0f}-{:.0f} K) + {}'.format(
        curve.meta.get('toolchain', {}).get('model_version', '?'), curve.mechanism,
        curve.T_K[0], curve.T_K[-1],
        'Arrhenius tail' if extrapolate else 'CLAMPED above the table')
    model.simulated = True
    model.mechanism = curve.mechanism
    model.source_meta = curve.meta
    return model


SimulatedLeakageCurve.as_leakage_model = _simulated_as_leakage_model
