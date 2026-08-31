"""A **measured product** V/F curve, and the one thing every other curve here is missing.

Why this module exists
----------------------
The project has had three V/F sources and none of them is a product curve:

* ``configuration.performance.VF_PAIRS`` -- the shipped table. Needs **1.4 V for 5.0 GHz**, about
  twice a modern node's supply, and its alpha-power fit only reaches 0.3% RMS by driving alpha
  below 1, which is outside the delay model's physical range (see
  ``performance_model.VF_ALPHA_POWER_FIT``). That is not a slightly-wrong curve; it is evidence
  the table is a **binning artefact** rather than a device curve.
* ``irds_vf.IRDS_NODES`` -- roadmap **projections**, deliberately ``calibrated = False``, whose
  ceilings (3.34 GHz at 2024, 4.54 at 2031) sit *below* what parts already ship at.
* ``published_reference`` -- real products, but **base frequency and TDP only**. No voltage, so
  it bounds clock and cannot produce a V/F curve.

What was missing in all three is voltage per frequency bin from real firmware. This module
supplies it for one part, from measurements of AMD's own SMU curve.

**And it carries something no other curve in this repository has: temperature.**

That is the part that matters for LCMR. The voltage a part needs at a given frequency *rises
with temperature*, and the sensitivity **grows steeply with frequency** -- on the measurements
below it roughly doubles between 4.77 and 5.17 GHz. So cooling does not only buy thermal
headroom, it buys **voltage** headroom, and dynamic power goes as V^2. Every clock result in
this project so far has been computed on a temperature-INDEPENDENT V/F curve, which means this
lever has been absent by construction, exactly as ``dt_max`` = 10 K was.

Provenance, and its limits
--------------------------
Measurements of a **Ryzen 9 9950X** (Zen 5, TSMC N4P) through AMD's Curve Optimizer and Curve
Shaper interfaces, which expose the SMU's own V/F curve:

* https://skatterbencher.com/2024/08/07/granite-ridge-overclocking-curve-shaper/
* https://skatterbencher.com/amd-curve-optimizer/

**This is enthusiast-press measurement of ONE part, not a datasheet**, and product V/F curves are
per-part: each die is calibrated at test and its curve fused, which is why no vendor publishes a
frequency->voltage table (Intel's published VID tables are an 8-bit code->volts *encoding*, not a
frequency mapping). ``calibrated`` is therefore False here too -- but for a different reason than
``IRDSVFModel``: that model is a projection nobody has measured, this one is a measurement of a
sample size of one. Treat it as an existence proof of curve SHAPE, and do not quote an absolute
clock ceiling from it without saying whose part it was.

The SMU's own structure is worth recording because it says what a real curve is: Curve Shaper
exposes **15 tuning points -- 5 frequency regions x 3 temperature points (-5, 50, 90 C)**. A
product V/F curve is a surface over (f, T), not a line.
"""
import bisect

#: Frequency [GHz] -> supply voltage [V] on the measured curve, at the LOW-temperature anchor
#: (reported as "below 40 C"). Two of these are temperature-resolved measurements; the top point
#: is the all-core maximum at the part's 1.35 V ceiling.
ZEN5_9950X_VF = [
    (4.766, 1.060),   # Curve Shaper, <40 C
    (5.000, 1.080),   # Curve Optimizer, default curve at 5 GHz (temperature unstated)
    (5.165, 1.110),   # Curve Shaper, <40 C
    (5.630, 1.350),   # all-core maximum at the 1.35 V limit
]

#: Frequency [GHz] -> dV/dT [mV/K], from the two temperature-resolved Curve Shaper points.
#: 4766 MHz: 1.060 V below 40 C -> 1.080 V above 90 C, i.e. 20 mV over ~50 K.
#: 5165 MHz: 1.110 V below 40 C -> 1.158 V above 90 C, i.e. 48 mV over ~50 K.
#: The sensitivity more than doubles across 0.4 GHz, which is the whole point.
ZEN5_9950X_DVDT_mV_per_K = [
    (4.766, 20.0 / 50.0),
    (5.165, 48.0 / 50.0),
]

#: Temperature the ``ZEN5_9950X_VF`` voltages are quoted at [C].
ZEN5_REF_T_C = 40.0

#: The part's own supply ceiling [V] -- the limit the all-core maximum runs into.
ZEN5_VMAX = 1.35


def _interp(table, x):
    """Piecewise-linear interpolation on a sorted [(x, y)] table. No extrapolation."""
    xs = [p[0] for p in table]
    if x < xs[0] or x > xs[-1]:
        raise ValueError('{:.4f} is outside the measured range {:.3f}-{:.3f}; this curve is four '
                         'measured points on one part, and extrapolating it would invent data'
                         .format(x, xs[0], xs[-1]))
    i = bisect.bisect_left(xs, x)
    if xs[i] == x:
        return table[i][1]
    (x0, y0), (x1, y1) = table[i - 1], table[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


class ProductVFModel(object):
    """The measured Zen 5 curve, as a function of frequency **and temperature**.

    ``calibrated`` is False: one part, press measurement. See the module docstring.
    """

    def __init__(self, vf=None, dvdt=None, ref_T_C=ZEN5_REF_T_C, v_max=ZEN5_VMAX,
                 label='Ryzen 9 9950X (Zen 5, N4P)'):
        self.vf = sorted(vf or ZEN5_9950X_VF)
        self.dvdt = sorted(dvdt or ZEN5_9950X_DVDT_mV_per_K)
        self.ref_T_C = float(ref_T_C)
        self.v_max = float(v_max)
        self.label = label
        self.calibrated = False
        self.f_min = self.vf[0][0]
        self.f_max_measured = self.vf[-1][0]

    # -- the curve -----------------------------------------------------------------------
    def dV_dT_mV_per_K(self, f_GHz):
        """Voltage-temperature sensitivity at this frequency [mV/K].

        Held flat outside the two measured frequencies rather than extrapolated: the trend is
        steeply increasing, so extending it would overstate the LCMR benefit, and this error
        runs the safe way.
        """
        lo, hi = self.dvdt[0], self.dvdt[-1]
        if f_GHz <= lo[0]:
            return lo[1]
        if f_GHz >= hi[0]:
            return hi[1]
        return _interp(self.dvdt, f_GHz)

    def voltage_for_frequency(self, f_GHz, T_C=None):
        """Supply this part needs for ``f_GHz`` at junction temperature ``T_C`` [V]."""
        v = _interp(self.vf, float(f_GHz))
        if T_C is None:
            return v
        dT = float(T_C) - self.ref_T_C
        return v + self.dV_dT_mV_per_K(f_GHz) * dT / 1000.0

    def voltage_saved_by_cooling(self, f_GHz, T_hot_C, T_cold_C):
        """Volts not needed at ``f_GHz`` because the part runs at ``T_cold_C`` not ``T_hot_C``.

        This is the LCMR lever the temperature-independent curves cannot express.
        """
        return (self.voltage_for_frequency(f_GHz, T_hot_C)
                - self.voltage_for_frequency(f_GHz, T_cold_C))

    def dynamic_power_ratio_from_cooling(self, f_GHz, T_hot_C, T_cold_C):
        """Dynamic power at ``T_cold_C`` relative to ``T_hot_C``, same frequency.

        Dynamic power goes as V^2 f, and f is held fixed here, so this is purely the V^2 term.
        Below 1 means cooling saved power at constant clock.
        """
        v_hot = self.voltage_for_frequency(f_GHz, T_hot_C)
        v_cold = self.voltage_for_frequency(f_GHz, T_cold_C)
        return (v_cold / v_hot) ** 2

    def frequency_at_voltage_limit(self, T_C=None, v_limit=None):
        """Highest measured frequency whose required voltage stays within the limit [GHz].

        Bisects the measured range only -- it will not report a frequency the part was never
        measured at.
        """
        v_limit = self.v_max if v_limit is None else float(v_limit)
        lo, hi = self.f_min, self.f_max_measured
        if self.voltage_for_frequency(lo, T_C) > v_limit:
            return None
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if self.voltage_for_frequency(mid, T_C) <= v_limit:
                lo = mid
            else:
                hi = mid
        return lo

    def clock_gained_by_cooling(self, T_hot_C, T_cold_C, v_limit=None):
        """Extra clock available at a fixed voltage ceiling purely from running cooler [GHz]."""
        hot = self.frequency_at_voltage_limit(T_hot_C, v_limit)
        cold = self.frequency_at_voltage_limit(T_cold_C, v_limit)
        if hot is None or cold is None:
            return None
        return cold - hot
