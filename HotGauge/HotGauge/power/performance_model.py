"""Goal 1b: turn temperature into performance -- f_max(T), guardband, and throttling.

The missing link
----------------
The pipeline can now say what a block's temperature and power are under a given cooling
solution. It could not say what that *costs in performance*, which is the number any cooling
decision is actually judged on. This module closes that gap:

    temperature  ->  f_max(T)  ->  achievable frequency  ->  throughput & perf-per-watt

Three effects, kept separate because they have different physics and different fixes:

1. **Guardband (temperature-dependent timing margin).** Transistor delay rises with
   temperature, so a frequency that is safe cool becomes unsafe hot. Modelled as a linear
   derating of f_max about a reference temperature (``FMaxModel.linear_derate``). This is the
   effect that fine-grained cooling directly buys back.
2. **Voltage-frequency coupling.** Reaching a higher frequency needs a higher voltage, and
   dynamic power goes as ~V^2*f -- so recovering frequency is not free. The V/F relationship
   comes from the shipped ``configuration.performance.VF_PAIRS`` table.
3. **Thermal throttling.** Above a trip temperature the part must reduce frequency to stay in
   spec. This is a hard, discontinuous performance cliff, and it is where hotspot clipping
   pays off most: the *hottest single block* sets the whole core's clock.

Sign conventions and honesty
----------------------------
``f_max`` is normalized: ``f_max(T_ref_perf) = f_nominal``. All model constants here are
**assumptions with documented provenance, not silicon measurements** -- ``derate_per_K``
especially. Every result object carries ``calibrated=False`` so a downstream efficiency claim
cannot silently inherit a guessed slope. Calibrate against real V/F/T characterization before
any customer-facing number.

Why the *hottest* block governs
-------------------------------
A core runs at one clock. HotGauge's whole premise is that hotspots are localized -- units
exceed 120 C while neighbours 200 um away sit 30 K cooler. So core frequency is set by its
worst block, not its average, and ``core_fmax`` reduces with ``max`` rather than ``mean``.
That asymmetry is exactly why *targeted* cooling can beat *bulk* cooling: removing one hotspot
lifts the clock for the entire core.
"""

import numpy as np

#: Reference temperature for the f_max derating [K]. 100 C is a common spec/characterization
#: point for client parts; it is a modeling choice, not a measurement.
DEFAULT_TREF_PERF_K = 373.15

#: Fractional f_max loss per Kelvin above the reference. ~0.1 %/K is the order of magnitude
#: reported for temperature-induced delay degradation in modern nodes; treat as an assumption.
DEFAULT_DERATE_PER_K = 0.001

#: Default thermal trip point [K] (100 C) above which throttling engages.
DEFAULT_THROTTLE_K = 373.15


class FMaxModel(object):
    """Maps temperature to achievable frequency, normalized to ``f_max(T_ref) = 1``.

    Construct via a classmethod so the provenance of each variant stays explicit.
    """

    def __init__(self, factor_fn, description, calibrated=False):
        self._factor_fn = factor_fn
        self.description = description
        self.calibrated = calibrated

    def __repr__(self):
        return '<FMaxModel {}{}>'.format(self.description,
                                         '' if self.calibrated else ' UNCALIBRATED')

    @classmethod
    def linear_derate(cls, derate_per_K=DEFAULT_DERATE_PER_K, T_ref_K=DEFAULT_TREF_PERF_K,
                      floor=0.1, calibrated=False):
        """``f_max(T)/f_ref = 1 - derate_per_K * (T - T_ref)``, clamped at ``floor``.

        Linear is the right first model: over the 40-130 C range of interest the delay-vs-T
        relationship is close enough to linear that curvature is far smaller than the
        uncertainty in the slope itself.
        """
        if derate_per_K < 0:
            raise ValueError('derate_per_K must be >= 0 (delay grows with temperature)')
        if not 0 < floor <= 1:
            raise ValueError('floor must be in (0, 1]')

        def factor_fn(T_K):
            f = 1.0 - derate_per_K * (np.asarray(T_K, dtype=float) - T_ref_K)
            return np.maximum(f, floor)

        return cls(factor_fn, 'linear_derate({:.4g}/K about {:.1f} K)'.format(
            derate_per_K, T_ref_K), calibrated=calibrated)

    @classmethod
    def from_table(cls, temps_K, rel_fmax, calibrated=True):
        """Interpolate measured f_max vs temperature; clamped beyond the table ends."""
        temps_K = np.asarray(temps_K, dtype=float)
        rel_fmax = np.asarray(rel_fmax, dtype=float)
        if temps_K.ndim != 1 or temps_K.shape != rel_fmax.shape:
            raise ValueError('temps_K and rel_fmax must be 1-D and the same length')
        order = np.argsort(temps_K)
        temps_K, rel_fmax = temps_K[order], rel_fmax[order]

        def factor_fn(T_K):
            return np.interp(np.asarray(T_K, dtype=float), temps_K, rel_fmax)

        return cls(factor_fn, 'from_table({} pts, {:.0f}-{:.0f} K)'.format(
            len(temps_K), temps_K[0], temps_K[-1]), calibrated=calibrated)

    def relative_fmax(self, T_K):
        """f_max at ``T_K`` as a fraction of f_max at the reference temperature."""
        return self._factor_fn(T_K)


def core_fmax(block_temps_K, model, f_nominal_GHz=1.0, t_floor_K=200.0):
    """Frequency a core can sustain, set by its **hottest** block.

    ``block_temps_K`` is any iterable of that core's block temperatures. Values below
    ``t_floor_K`` are dropped: 3D-ICE reports 0 K for floorplan elements outside the die
    layer, and letting those through would invent an arbitrarily cold -- and therefore fast --
    core.
    """
    temps = np.asarray(list(block_temps_K), dtype=float).ravel()
    temps = temps[temps > t_floor_K]
    if temps.size == 0:
        raise ValueError('No block temperatures above the {} K floor'.format(t_floor_K))
    return float(f_nominal_GHz) * float(model.relative_fmax(temps.max())), float(temps.max())


def throttled_fmax(T_hot_K, model, f_nominal_GHz=1.0, throttle_K=DEFAULT_THROTTLE_K,
                   throttle_slope_per_K=0.02, floor_frac=0.3):
    """f_max including a hard throttle above ``throttle_K``.

    Below the trip point only the guardband derating applies. Above it, an additional
    ``throttle_slope_per_K`` fractional cut per Kelvin of exceedance models the control loop
    pulling frequency back to hold temperature -- far steeper than the guardband slope, which
    is what makes the trip point a performance cliff rather than a gentle slope.

    Returns ``(f_GHz, throttling_active)``.
    """
    T_hot_K = float(T_hot_K)
    base = float(f_nominal_GHz) * float(model.relative_fmax(T_hot_K))
    if T_hot_K <= throttle_K:
        return base, False
    cut = 1.0 - throttle_slope_per_K * (T_hot_K - throttle_K)
    return base * max(cut, floor_frac), True


def voltage_for_frequency(f_GHz):
    """Voltage needed for ``f_GHz`` from the shipped V/F table, clamped to its range.

    ``configuration.performance.get_VF_pair`` raises outside the tabulated range, which is
    unhelpful mid-sweep, so this clamps to the table endpoints and reports the clamp.

    Returns ``(voltage_V, clamped)``.
    """
    from HotGauge.configuration.performance import VF_PAIRS
    volts = [v for v, _ in VF_PAIRS]
    freqs = [f for _, f in VF_PAIRS]
    lo, hi = min(freqs), max(freqs)
    f = float(f_GHz)
    if f < lo:
        return float(min(volts)), True
    if f > hi:
        return float(max(volts)), True
    return float(np.interp(f, freqs, volts)), False


def dynamic_power_scale(f_GHz, f_ref_GHz):
    """Dynamic-power multiplier when moving from ``f_ref_GHz`` to ``f_GHz``.

    ``P_dyn ~ C V^2 f``, so the scale is ``(V/V_ref)^2 * (f/f_ref)`` -- the cubic-ish cost
    that makes "just clock it higher once it is cool" a real trade rather than free
    performance.
    """
    if f_ref_GHz <= 0:
        raise ValueError('f_ref_GHz must be > 0')
    v, _ = voltage_for_frequency(f_GHz)
    v_ref, _ = voltage_for_frequency(f_ref_GHz)
    if v_ref <= 0:
        raise ValueError('Reference voltage resolved to <= 0')
    return (v / v_ref) ** 2 * (float(f_GHz) / float(f_ref_GHz))


def performance_summary(block_temps_K, model, f_nominal_GHz=4.0, compute_power_W=None,
                        cooling_power_W=0.0, throttle_K=DEFAULT_THROTTLE_K, t_floor_K=200.0):
    """Bundle the temperature -> performance -> efficiency chain for one configuration.

    ``cooling_power_W`` is the cooling solution's own draw (fan/pump/laser). Leave it at 0.0
    only when it is genuinely zero -- passing 0.0 for an unmodelled cooler silently scores it
    as free, which is the single easiest way to produce a flattering and wrong
    perf-per-watt number.

    Returns a dict; ``calibrated`` propagates from the f_max model so downstream consumers can
    see whether the performance side rests on measurements or assumptions.
    """
    f_guard, t_hot = core_fmax(block_temps_K, model, f_nominal_GHz, t_floor_K=t_floor_K)
    f_eff, throttling = throttled_fmax(t_hot, model, f_nominal_GHz, throttle_K=throttle_K)
    out = {'T_hot_K': t_hot, 'T_hot_C': t_hot - 273.15,
           'f_guardband_GHz': f_guard, 'f_effective_GHz': f_eff,
           'throttling': throttling,
           'rel_perf': f_eff / float(f_nominal_GHz),
           'calibrated': bool(model.calibrated)}
    if compute_power_W is not None:
        total = float(compute_power_W) + float(cooling_power_W)
        out['compute_power_W'] = float(compute_power_W)
        out['cooling_power_W'] = float(cooling_power_W)
        out['total_power_W'] = total
        out['perf_per_W'] = (f_eff / total) if total > 0 else float('nan')
    return out


# ---------------------------------------------------------------------------
# The V/F envelope: why the table ends where it does
# ---------------------------------------------------------------------------
#: Maximum operating voltage in the shipped V/F table (``configuration.performance.VF_PAIRS``).
#: Past it a part does not run slower, it fails -- so a clock search that stops here is reporting
#: a limit rather than running out of data.
#:
#: **But the table is not a 7 nm-class curve.** IRDS 2024 More Moore (MM01 - LOGIC) puts a
#: high-performance logic node at Vdd **0.6-0.7 V** reaching 3.85-5.19 GHz wireloaded, while
#: this table needs 1.19 V for 4.6 GHz and 1.4 V for 5.0 GHz -- about twice the supply voltage
#: for the same clock, and 6.5x the dynamic power at 5.19 GHz. Absolute power and any
#: clock CEILING taken from it are wrong for a modern node; comparisons of two configurations
#: through the same table are not. See docs/CLOCK_HEADROOM.md.
VF_MAX_VOLTAGE = 1.4

#: Alpha-power-law fit to the shipped table, ``f = k (V - Vth)^alpha / V``, which is the
#: standard velocity-saturated delay model -- Chandrakasan, Bowhill & Fox, *Design of
#: High-Performance Microprocessor Circuits*, eq. (4.2):
#:
#:     tau_d = beta * C_L * V_DD / (V_DD - V_TH)^alpha
#:
#: Fitted to all eight shipped pairs with **max error 0.57%, RMS 0.30%**, so the table really is
#: one alpha-power curve rather than a set of unrelated operating points. The book quotes alpha
#: ~1.4 as typical; the fit gives 0.949, i.e. more strongly velocity-saturated, which is the
#: direction modern short-channel devices move in.
VF_ALPHA_POWER_FIT = {'k': 7.5810, 'Vth': 0.4795, 'alpha': 0.9490,
                      'rms_error_frac': 0.0030, 'max_error_frac': 0.0057,
                      'source': 'fit to configuration.performance.VF_PAIRS; model from '
                                'Chandrakasan/Bowhill/Fox eq. 4.2'}


def frequency_for_voltage(V, fit=None):
    """Clock the alpha-power fit predicts at supply voltage ``V`` [GHz]."""
    f = fit or VF_ALPHA_POWER_FIT
    v = float(V)
    return f['k'] * max(v - f['Vth'], 0.0) ** f['alpha'] / v if v > 0 else 0.0


def voltage_for_frequency_extrapolated(f_GHz, fit=None):
    """Voltage the alpha-power fit says ``f_GHz`` needs, **including above the table**.

    Provided for one purpose: to show how fast the cost of clock rises past the table's top, so
    that "the search stopped at 5.0 GHz" can be reported as a device limit rather than as an
    artefact of our lookup. On the shipped curve

        5.00 GHz -> 1.40 V     5.50 GHz -> 1.82 V     6.00 GHz -> 2.74 V

    and a 7 nm part does not operate at 1.8 V, let alone 2.7 V -- that is oxide-breakdown
    territory, not a slower chip. **Do not use this to extend a clock search.** The table ends
    where the device does; a search that runs past it is not measuring silicon.
    """
    from scipy.optimize import brentq
    fit = fit or VF_ALPHA_POWER_FIT
    target = float(f_GHz)
    hi = 1.0
    while frequency_for_voltage(hi, fit) < target:
        hi *= 1.5
        if hi > 100.0:
            raise ValueError('{} GHz is unreachable under the alpha-power fit'.format(f_GHz))
    return float(brentq(lambda v: frequency_for_voltage(v, fit) - target,
                        fit['Vth'] + 1e-6, hi))
