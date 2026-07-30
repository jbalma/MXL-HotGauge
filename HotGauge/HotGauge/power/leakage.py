"""Temperature-dependent leakage (static power) modeling and power<->temperature feedback.

Background / why this module exists
-----------------------------------
The stock HotGauge pipeline computes leakage (subthreshold + gate) *once*, inside
McPAT, at a fixed per-core reference temperature (the ``<param name="temperature">``
in the McPAT XML template -- 330 K or 360 K in the shipped templates). That leakage is
then summed with dynamic power and *frozen* for the whole thermal simulation. See the
``TODO`` at ``scripts/mcpat_to_blk_lvl_power_dict.py`` line ~241:

    # TODO: This is where we can also scale leakage (right before we combine them)
    # Look-up unit_name in temperature dictionary to get leakage scale factor (comes from 3D ICE)

Because subthreshold leakage is roughly exponential in temperature, freezing it means the
pipeline (a) cannot represent leakage/temperature positive feedback or thermal runaway and
(b) systematically *undercounts* the benefit of cooling (the static-power savings term is
lost). This module supplies the missing physics and the feedback loop.

What it provides
----------------
* ``LeakageModel`` -- a temperature -> leakage-scaling factor, normalized to the reference
  temperature at which the baseline leakage was extracted. Two closed-form variants
  (exponential "doubles every dT" and a subthreshold-physical form) plus a
  ``from_table`` interpolator so a McPAT-calibrated lookup (re-runs at several
  temperatures) can be dropped in later.
* ``rescale_total_power`` -- given (total, leakage_ref, T, T_ref) return the corrected
  total = dynamic + leakage_ref * scale(T), where dynamic = total - leakage_ref.
* ``rescale_trace`` -- apply the above across a full per-unit, per-timestep power trace
  using a per-unit temperature trace.
* ``converge_power_temperature`` -- fixed-point iteration that alternates
  power -> (thermal solve) -> temperature -> (leakage rescale) -> power until the
  temperature field stops moving. The thermal solve is injected as a callable so this is
  unit-testable without 3D-ICE and pluggable with ``ICETransientSim`` in production.

Scope / simplifications (first cut -- see project gap-analysis doc)
-------------------------------------------------------------------
* Total leakage is treated with a single subthreshold-dominated model. Gate leakage has a
  weaker temperature dependence; splitting the two would need the components kept separate
  (they are available upstream in ``mcpat_to_blk_lvl_power_dict.py`` before they are
  summed). Documented here as a known approximation.
* Voltage dependence of leakage is not modeled here (handled via DVFS/V-F elsewhere).
"""

import math
import logging

import numpy as np

LOGGER = logging.getLogger(__name__)

# McPAT XML reference temperatures (Kelvin) at which the shipped templates extract leakage.
# These MUST match the `<param name="temperature" ...>` used when the trace was generated.
# The shipped HotGauge McPAT templates use 330 K for some cores and 360 K for others; there
# is no single value, so callers should pass the correct T_ref for the trace they loaded.
MCPAT_TEMPLATE_TREF_K = (330.0, 360.0)
DEFAULT_TREF_K = 360.0  # conservative default (higher T_ref -> smaller predicted savings)

# Default leakage-doubling interval in kelvin/degC. Subthreshold leakage in the ~40-100 C
# operating range roughly doubles every 8-12 C; 10 is a standard mid-range choice. This is
# the single most important knob and is meant to be recalibrated against McPAT re-runs.
DEFAULT_DOUBLING_DELTA_K = 10.0

BOLTZMANN_EV_PER_K = 8.617333262e-5  # k in eV/K


def _to_kelvin(t, assume):
    """Coerce a temperature (scalar or array) to Kelvin.

    assume: 'K' or 'C' -- how to interpret values that look ambiguous. We only convert when
    ``assume == 'C'``; values are otherwise taken as already-Kelvin. Heuristic guarding is
    deliberately avoided so behavior is explicit and predictable.
    """
    t = np.asarray(t, dtype=float)
    if assume == 'C':
        return t + 273.15
    if assume == 'K':
        return t
    raise ValueError("assume must be 'K' or 'C', got {!r}".format(assume))


class LeakageModel(object):
    """Maps operating temperature to a multiplicative leakage-scaling factor.

    The factor is normalized so that ``scale(T_ref) == 1.0``: multiplying a baseline leakage
    (extracted by McPAT at ``T_ref``) by ``scale(T)`` gives the leakage at temperature ``T``.

    Construct via one of the classmethods:
        * ``LeakageModel.exponential(doubling_delta_K=10.0)``
        * ``LeakageModel.subthreshold(activation_eV=0.9)``
        * ``LeakageModel.from_table(temps_K, rel_leakage)``
    """

    def __init__(self, factor_fn, description):
        self._factor_fn = factor_fn
        self.description = description

    # ---- constructors -------------------------------------------------------
    @classmethod
    def exponential(cls, doubling_delta_K=DEFAULT_DOUBLING_DELTA_K):
        """Leakage scales as 2**((T - T_ref)/doubling_delta_K).

        Equivalent to P_leak(T) = P_leak(T_ref) * exp(beta*(T - T_ref)) with
        beta = ln(2)/doubling_delta_K. Simple, monotonic, always positive; the default model.
        """
        if doubling_delta_K <= 0:
            raise ValueError('doubling_delta_K must be positive')
        beta = math.log(2.0) / doubling_delta_K

        def factor_fn(T_K, Tref_K):
            # Overflow -> +inf is an acceptable "runaway" signal; the feedback driver guards
            # on non-finite temperatures, so suppress the cosmetic RuntimeWarning here.
            with np.errstate(over='ignore'):
                return np.exp(beta * (T_K - Tref_K))

        return cls(factor_fn, 'exponential(doubling_delta_K={} K)'.format(doubling_delta_K))

    @classmethod
    def subthreshold(cls, activation_eV=0.9):
        """Physical subthreshold form: scale = (T/Tref)^2 * exp(-Ea/k * (1/T - 1/Tref)).

        Captures the T^2 prefactor and Arrhenius-like activation of subthreshold current.
        ``activation_eV`` is an effective activation energy (~0.6-1.0 eV typical); it should
        be fit to McPAT/silicon data. Provided as a more physically-shaped alternative to the
        exponential; still normalized to scale(Tref)=1.
        """
        if activation_eV <= 0:
            raise ValueError('activation_eV must be positive')

        def factor_fn(T_K, Tref_K):
            T_K = np.asarray(T_K, dtype=float)
            ratio2 = (T_K / Tref_K) ** 2
            arr = np.exp(-(activation_eV / BOLTZMANN_EV_PER_K) * (1.0 / T_K - 1.0 / Tref_K))
            return ratio2 * arr

        return cls(factor_fn, 'subthreshold(activation_eV={} eV)'.format(activation_eV))

    @classmethod
    def from_table(cls, temps_K, rel_leakage):
        """Interpolate a measured/McPAT-calibrated relative-leakage curve.

        temps_K: sequence of temperatures (Kelvin).
        rel_leakage: leakage at each temperature in *arbitrary* consistent units; it is
            re-normalized internally to whatever T_ref is requested at call time by
            dividing by the interpolated value at T_ref. Linear interpolation, clamped
            (constant) beyond the table ends with a warning.
        This is the recommended path once McPAT has been re-run at several temperatures.
        """
        temps_K = np.asarray(temps_K, dtype=float)
        rel_leakage = np.asarray(rel_leakage, dtype=float)
        if temps_K.ndim != 1 or temps_K.shape != rel_leakage.shape:
            raise ValueError('temps_K and rel_leakage must be 1-D and the same length')
        order = np.argsort(temps_K)
        temps_K, rel_leakage = temps_K[order], rel_leakage[order]

        def factor_fn(T_K, Tref_K):
            T_K = np.asarray(T_K, dtype=float)
            if np.any(T_K < temps_K[0]) or np.any(T_K > temps_K[-1]):
                LOGGER.warning('Temperature outside leakage table [%g, %g] K; clamping',
                               temps_K[0], temps_K[-1])
            at_T = np.interp(T_K, temps_K, rel_leakage)
            at_ref = np.interp(Tref_K, temps_K, rel_leakage)
            return at_T / at_ref

        return cls(factor_fn, 'from_table({} points, {:.0f}-{:.0f} K)'.format(
            len(temps_K), temps_K[0], temps_K[-1]))

    # ---- evaluation ---------------------------------------------------------
    def scale(self, T, T_ref=DEFAULT_TREF_K, temp_units='K'):
        """Return the leakage-scaling factor at temperature ``T`` relative to ``T_ref``.

        T, T_ref may be scalars or numpy arrays (broadcast). ``temp_units`` in {'K','C'}
        applies to both T and T_ref.
        """
        T_K = _to_kelvin(T, temp_units)
        Tref_K = _to_kelvin(T_ref, temp_units)
        factor = self._factor_fn(T_K, Tref_K)
        return float(factor) if np.isscalar(T) or np.ndim(T) == 0 else factor

    def __repr__(self):
        return 'LeakageModel[{}]'.format(self.description)


def rescale_total_power(total, leakage_ref, T, model, T_ref=DEFAULT_TREF_K, temp_units='K',
                        clip_nonneg=True):
    """Recompute total power at temperature ``T`` by rescaling only the leakage component.

    total       : baseline total power (dynamic + leakage_ref) at ``T_ref`` [W].
    leakage_ref : baseline leakage power at ``T_ref`` [W].
    T           : operating temperature (scalar or array matching ``total``).
    model       : a ``LeakageModel``.
    returns     : corrected total = (total - leakage_ref) + leakage_ref * scale(T).

    ``dynamic = total - leakage_ref`` is assumed temperature-independent. If
    ``clip_nonneg`` (default), the corrected total is floored at 0 to avoid unphysical
    negative power from noisy inputs (does not affect intentional cooling terms, which are
    injected elsewhere as negative sources, not here).
    """
    total = np.asarray(total, dtype=float)
    leakage_ref = np.asarray(leakage_ref, dtype=float)
    dynamic = total - leakage_ref
    factor = model.scale(T, T_ref=T_ref, temp_units=temp_units)
    corrected = dynamic + leakage_ref * factor
    if clip_nonneg:
        corrected = np.maximum(corrected, 0.0)
    return corrected


def rescale_trace(total_trace, leakage_ref, temp_trace, model,
                  T_ref=DEFAULT_TREF_K, temp_units='K', name_map=None, missing='keep',
                  t_floor_K=None):
    """Apply leakage rescaling across a full power trace using a per-unit temperature trace.

    total_trace : PowerTrace-like -> its ``.powers`` maps unit -> [p0, p1, ...] (W).
    leakage_ref : dict unit -> baseline leakage. Either a scalar per unit (constant in time)
                  or a per-timestep sequence matching the trace length.
    temp_trace  : dict unit -> temperature sequence (per timestep). Keys may be floorplan
                  block names; ``name_map(power_unit) -> temp_key`` bridges the naming if the
                  power trace uses McPAT-hierarchy names (see configuration.mcpat.mcpat_to_flp_name).
    model       : a ``LeakageModel``.
    missing     : what to do when a unit has no temperature/leakage entry --
                  'keep' (leave power unchanged, default) or 'error'.
    t_floor_K   : if set, temperatures below this floor are treated as unphysical (e.g. the
                  0 K readings 3D-ICE emits for floorplan elements outside the die layer) and
                  replaced with ``T_ref`` (leakage scale 1.0), so they neither zero-out nor
                  inflate leakage. Interpreted in the same units as ``temp_units``.

    returns a new ``BasicPowerTrace`` with corrected per-unit power. Import of the trace
    class is deferred so this module has no import-time dependency on the trace stack.
    """
    from HotGauge.power.traces import BasicPowerTrace

    powers = total_trace.powers
    new_powers = {}
    for unit, series in powers.items():
        series = np.asarray(series, dtype=float)
        temp_key = name_map(unit) if name_map is not None else unit
        leak = leakage_ref.get(unit) if leakage_ref is not None else None
        temps = temp_trace.get(temp_key) if temp_trace is not None else None
        if leak is None or temps is None:
            if missing == 'error':
                raise KeyError('No leakage/temperature for unit {!r} (temp key {!r})'.format(
                    unit, temp_key))
            new_powers[unit] = series  # unchanged
            continue
        temps = np.asarray(temps, dtype=float)
        if t_floor_K is not None:
            temps = np.where(temps < t_floor_K, float(T_ref), temps)
        if temps.shape != series.shape:
            raise ValueError('Temperature length {} != power length {} for unit {!r}'.format(
                temps.shape, series.shape, unit))
        new_powers[unit] = rescale_total_power(series, leak, temps, model,
                                               T_ref=T_ref, temp_units=temp_units)
    return BasicPowerTrace(new_powers, total_trace.time_step)


def converge_power_temperature(total_trace, leakage_ref, thermal_solve_fn, model,
                               T_ref=DEFAULT_TREF_K, temp_units='K', name_map=None,
                               tol_K=0.1, max_iter=10, relax=1.0, max_power_growth=None,
                               t_floor_K=None, max_temp_K=None):
    """Fixed-point power<->temperature<->leakage iteration.

    total_trace       : baseline PowerTrace (leakage extracted at ``T_ref``).
    leakage_ref       : dict unit -> baseline leakage (see ``rescale_trace``).
    thermal_solve_fn  : callable(PowerTrace) -> temp_trace dict {temp_key: [T0, T1, ...]}.
                        In production this wraps a 3D-ICE run (e.g. ICETransientSim +
                        load_3DICE_block_file). In tests it can be any deterministic map.
    model             : a ``LeakageModel``.
    tol_K             : convergence threshold on the max per-cell temperature change between
                        successive iterations.
    max_iter          : safety cap on iterations.
    relax             : under-relaxation factor in (0, 1] for the temperature field that
                        drives the leakage update: T_drive = (1-relax)*T_prev + relax*T_solved.
                        1.0 is plain Gauss-Seidel (fastest when it converges); <1 damps
                        oscillation/overshoot near the stability boundary. Does not move the
                        fixed point, only the path to it.
    max_power_growth  : if set, stop and flag runaway once the total power of the rescaled
                        trace exceeds this multiple of the baseline total -- caught *before*
                        the next thermal solve, so we never hand a downstream solver (3D-ICE)
                        runaway-inflated power that would make it crash or diverge.
    t_floor_K         : forwarded to ``rescale_trace`` (ignore sub-floor/unphysical temps).
    max_temp_K        : if set, stop and flag runaway as soon as any solved block temperature
                        exceeds this (after t_floor filtering). Attribution is logged -- the
                        offending block is named -- so a localized runaway (one dense block
                        ratcheting) is identified at the first unphysical solve instead of
                        many iterations later when total power overflows.

    returns dict with keys:
        'power_trace'  : latest PowerTrace,
        'temp_trace'   : latest temperature field,
        'iterations'   : number of thermal solves performed,
        'converged'    : bool -- reached tol_K,
        'diverged'     : bool -- runaway/solver-failure detected (mutually exclusive with
                         'converged'),
        'max_delta_K'  : final max temperature change (inf if diverged),
        'history'      : list of per-iteration dicts {iter, max_T_K, max_T_key, total_W,
                         max_delta_K} recording the hottest block and its temperature at each
                         thermal solve -- the primary diagnostic for localized runaway.

    Convergence: with a monotonically-increasing leakage(T) and a passive thermal path this
    is a contraction while d(leakage)/dT * (thermal resistance) < 1. If that product exceeds
    1 the physical device is in thermal runaway and no stable fixed point exists; this is
    surfaced as 'diverged': True (via non-finite temps, the power-growth guard, or a solver
    failure) rather than hidden or raised.
    """
    def _total(trace):
        return sum(float(np.sum(np.asarray(s, float))) for s in trace.powers.values())

    baseline_total = _total(total_trace)
    current = total_trace
    prev_temps = None      # last raw solved field, for the residual convergence check
    driving = None         # under-relaxed field that actually drives the leakage update
    max_delta = float('inf')
    iterations = 0
    converged = False
    diverged = False
    history = []
    for i in range(max_iter):
        # A downstream solver (3D-ICE) can fail outright when handed extreme power; treat any
        # failure as divergence rather than letting it crash the whole run.
        try:
            temps = thermal_solve_fn(current)
        except Exception as e:  # noqa: BLE001 - deliberately broad: any solver failure
            LOGGER.error('leakage feedback iter %d: thermal solve failed (%s) -> treating as '
                         'divergence/runaway; stopping', i, e)
            diverged = True
            break
        iterations += 1

        # Non-finite temperatures also mean the loop diverged.
        if any(not np.all(np.isfinite(np.asarray(v, float))) for v in temps.values()):
            LOGGER.warning('leakage feedback iter %d: non-finite temperature -> thermal '
                           'runaway; stopping', i)
            diverged = True
            max_delta = float('inf')
            break

        # Record the hottest block this iteration (ignoring sub-floor/unphysical readings)
        # -- the primary diagnostic for identifying a localized runaway.
        max_T, max_T_key = -np.inf, None
        for k, v in temps.items():
            v = np.asarray(v, float)
            if t_floor_K is not None:
                v = v[v >= t_floor_K]
            if v.size and float(np.max(v)) > max_T:
                max_T, max_T_key = float(np.max(v)), k
        history.append({'iter': i, 'max_T_K': max_T, 'max_T_key': max_T_key,
                        'total_W': _total(current), 'max_delta_K': max_delta})

        # Per-block temperature sanity guard: a single dense block ratcheting into runaway is
        # caught (and NAMED) at the first unphysical solve, long before total power overflows.
        if max_temp_K is not None and max_T > max_temp_K:
            LOGGER.warning('leakage feedback iter %d: block %r reached %.1f K (> %.0f K '
                           'limit) -> localized runaway; stopping', i, max_T_key, max_T,
                           max_temp_K)
            diverged = True
            max_delta = float('inf')
            prev_temps = temps
            break

        # Residual convergence check on the raw solved field.
        if prev_temps is not None:
            deltas = [np.max(np.abs(np.asarray(v, float) - np.asarray(prev_temps[k], float)))
                      for k, v in temps.items() if k in prev_temps]
            max_delta = max(deltas) if deltas else 0.0
            LOGGER.info('leakage feedback iter %d: max dT = %.4f K', i, max_delta)
            if max_delta <= tol_K:
                converged = True
                prev_temps = temps
                break
        prev_temps = temps

        # Under-relax the field that drives the leakage update.
        if driving is None or relax >= 1.0:
            driving = temps
        else:
            driving = {k: (1.0 - relax) * np.asarray(driving.get(k, v), float)
                            + relax * np.asarray(v, float)
                       for k, v in temps.items()}

        # Always rescale from the BASELINE trace: dynamic = baseline_total - leakage_ref is
        # temperature-independent, so re-deriving it from an already-rescaled trace would make
        # the dynamic component drift each iteration. Only leakage tracks T.
        current = rescale_trace(total_trace, leakage_ref, driving, model, T_ref=T_ref,
                                temp_units=temp_units, name_map=name_map, t_floor_K=t_floor_K)

        # Early runaway guard: stop before the next solve if power has blown up.
        cur_total = _total(current)
        if not np.isfinite(cur_total) or (
                max_power_growth is not None and baseline_total > 0
                and cur_total > max_power_growth * baseline_total):
            LOGGER.warning('leakage feedback iter %d: total power grew to %.4g W (%.1fx '
                           'baseline) -> runaway; stopping', i, cur_total,
                           (cur_total / baseline_total) if baseline_total else float('inf'))
            diverged = True
            max_delta = float('inf')
            break

    return {
        'power_trace': current,
        'temp_trace': prev_temps,
        'iterations': iterations,
        'converged': converged,
        'diverged': diverged,
        'max_delta_K': max_delta,
        'history': history,
    }
