"""Parameterized top-of-stack cooling models for steady-state HotGauge studies.

Why this exists
---------------
3D-ICE offers two mutually exclusive top-boundary models, and neither alone supports the
studies we need (see docs/PROJECT_STATUS.md):

* ``top pluggable heat sink`` -- a co-simulated Modelica/FMU heatsink (fan curves, liquid
  blocks). Physically detailed, but **transient only**: ``emulate_steady`` refuses it, and
  ms-scale transients never diffuse past the die, so the sink is invisible at those
  timescales. Reaching equilibrium takes ~minutes of simulated time per evaluation.
* ``top heat sink`` -- a single ``heat transfer coefficient`` + ``temperature``. Cheap and
  steady-solvable, but the stock grammar accepts **no spreader/sink geometry** (the
  ``sink height ... / spread height ...`` lines in ``skylake.stk`` are commented out because
  this 3D-ICE version's parser rejects them).

This module makes that second boundary a first-class, parameterized object. That directly
enables **power-regime sweeps**: you can specify "a 0.05 K/W server cooler" and study a 500 W
part without needing an FMU for every cooling class, which no shipped FMU covers (the HS483
model documents itself as valid only below 40 W).

The lumped approximation, stated plainly
----------------------------------------
Collapsing spreader + sink + fan into one coefficient at the die's top face discards lateral
heat spreading in the spreader. It can be calibrated to match a target metric (mean or peak
die temperature) at an operating point, but it will not reproduce the full FMU's spatial
temperature *shape*, and its error grows as the power map changes shape. Quantifying that
error against the FMU is the job of ``examples/calibrate_sink_surrogate.py`` -- treat an
uncalibrated sink as a modeling assumption, not a measurement.

Units
-----
3D-ICE expresses the ambient HTC in **W/(um^2 K)** (see ``get_conductance_top_solid`` in
``3d-ice/sources/thermal_grid.c``: the series form ``2*k*h*L*W / (H*h + 2*k)`` with k in
W/(um K) and lengths in um forces h to W/(um^2 K)). Datasheets quote W/(m^2 K) or K/W, so
everything here converts explicitly -- ``1e-7 W/(um^2 K)`` is ``1e5 W/(m^2 K)``, which over a
~10 mm^2 die is about 1 K/W.
"""

import os
import re

import numpy as np

# 1 m^2 = 1e12 um^2
UM2_PER_M2 = 1.0e12

# Matches e.g. "heat transfer coefficient 1.0e-7 ;" / "temperature 303.15 ;".
# Both are line-anchored so commented-out variants are skipped -- skylake.stk ships a
# commented "// heat transfer coefficient ... for mobile" line right below the active one,
# and an unanchored pattern silently rewrites the comment instead (or matches twice).
# '^\s*' admits only whitespace before the keyword, never '//'.
_HTC_RGX = re.compile(r'^(\s*heat\s+transfer\s+coefficient\s+)([0-9eE.+-]+)(\s*;)', re.MULTILINE)
_TEMP_RGX = re.compile(r'^(\s*temperature\s+)([0-9eE.+-]+)(\s*;)', re.MULTILINE)


def htc_si_to_3dice(h_si):
    """W/(m^2 K) -> W/(um^2 K)."""
    return float(h_si) / UM2_PER_M2


def htc_3dice_to_si(h_dice):
    """W/(um^2 K) -> W/(m^2 K)."""
    return float(h_dice) * UM2_PER_M2


def thermal_resistance_to_htc_si(r_th_K_per_W, area_m2):
    """Convert a datasheet-style thermal resistance [K/W] over ``area_m2`` to W/(m^2 K).

    ``R_th = 1 / (h * A)``, so ``h = 1 / (R_th * A)``. Note the result is *referenced to the
    area you pass*: the same cooler quoted at 0.3 K/W maps to a very different coefficient
    over a 10 mm^2 die than over a 30 mm x 30 mm spreader. Pass the area 3D-ICE actually
    applies the coefficient over -- the chip footprint from the ``dimensions:`` block.
    """
    if r_th_K_per_W <= 0:
        raise ValueError('r_th_K_per_W must be > 0, got {!r}'.format(r_th_K_per_W))
    if area_m2 <= 0:
        raise ValueError('area_m2 must be > 0, got {!r}'.format(area_m2))
    return 1.0 / (float(r_th_K_per_W) * float(area_m2))


class SinkModel(object):
    """A top-of-stack cooling boundary: an HTC, an ambient temperature, and its own power draw.

    ``parasitic_power_W`` is what separates "max performance" from "max performance-per-watt":
    a faster fan lowers die temperature (less leakage, higher f_max) but costs electrical
    power. Subclasses that model a real cooler should report it; it defaults to 0.0 with
    ``parasitic_known = False`` so an efficiency study can tell "no fan" from "fan power
    unknown" instead of silently scoring an unmodelled cooler as free.
    """

    #: whether parasitic_power_W is a real modeled value rather than an unmodelled 0.0
    parasitic_known = False
    #: whether the HTC came from calibration against a reference model/measurement
    calibrated = False

    def __init__(self, ambient_K=303.15, label=None):
        self.ambient_K = float(ambient_K)
        self.label = label or type(self).__name__

    def htc_si(self):
        """Heat transfer coefficient in W/(m^2 K). Subclasses must implement."""
        raise NotImplementedError

    def htc_3dice(self):
        """Heat transfer coefficient in 3D-ICE units, W/(um^2 K)."""
        return htc_si_to_3dice(self.htc_si())

    def parasitic_power_W(self):
        """Electrical power the cooling solution itself consumes (fan/pump/laser)."""
        return 0.0

    def thermal_resistance(self, area_m2):
        """Effective R_th [K/W] this sink presents over ``area_m2``."""
        return 1.0 / (self.htc_si() * float(area_m2))

    def describe(self):
        flags = []
        if not self.calibrated:
            flags.append('UNCALIBRATED')
        if not self.parasitic_known:
            flags.append('parasitic power unmodelled')
        suffix = '  [{}]'.format('; '.join(flags)) if flags else ''
        return '{}: h={:.4g} W/(m^2 K), T_amb={:.2f} K, P_cool={:.3g} W{}'.format(
            self.label, self.htc_si(), self.ambient_K, self.parasitic_power_W(), suffix)


class ConstantHTCSink(SinkModel):
    """A fixed heat transfer coefficient, in W/(m^2 K). The stock ``skylake.stk`` behaviour."""

    def __init__(self, h_si, ambient_K=303.15, label=None, calibrated=False,
                 parasitic_power=None):
        super().__init__(ambient_K=ambient_K, label=label)
        self._h_si = float(h_si)
        self.calibrated = bool(calibrated)
        self._parasitic = parasitic_power
        self.parasitic_known = parasitic_power is not None

    def htc_si(self):
        return self._h_si

    def parasitic_power_W(self):
        return 0.0 if self._parasitic is None else float(self._parasitic)


class ThermalResistanceSink(SinkModel):
    """A cooler specified the way datasheets specify them: thermal resistance in K/W.

    This is the workhorse for **power-regime sweeps** -- pick an R_th representative of the
    cooling class (rough guide: ~0.5-1.0 K/W desktop air, ~0.1-0.3 K/W high-end air/AIO,
    ~0.02-0.05 K/W server liquid loop) and a die area, and study any power level without
    needing an FMU for that class.

    ``area_m2`` must be the chip footprint 3D-ICE applies the coefficient over -- use
    ``chip_area_m2_from_floorplan``.
    """

    def __init__(self, r_th_K_per_W, area_m2, ambient_K=303.15, label=None,
                 parasitic_power=None, calibrated=False):
        super().__init__(ambient_K=ambient_K, label=label)
        self.r_th_K_per_W = float(r_th_K_per_W)
        self.area_m2 = float(area_m2)
        self._h_si = thermal_resistance_to_htc_si(r_th_K_per_W, area_m2)
        self._parasitic = parasitic_power
        self.parasitic_known = parasitic_power is not None
        self.calibrated = bool(calibrated)

    def htc_si(self):
        return self._h_si

    def parasitic_power_W(self):
        return 0.0 if self._parasitic is None else float(self._parasitic)

    def describe(self):
        return '{} (R_th={:.4g} K/W over {:.4g} mm^2)'.format(
            super().describe(), self.r_th_K_per_W, self.area_m2 * 1e6)


#: Fan electrical power per unit airflow [W per CFM], calibrated from
#: docs/MXL-Photonic-Cooling-Power-Analysis.xlsx. Its three cases (with-laser, dT=10 K,
#: dT=50 K) span 3x in airflow yet all give 0.590 W/CFM to four figures, so this is a genuine
#: property of the modelled fan rather than a fitted fudge.
MXL_FAN_W_PER_CFM = 0.5900

#: Heat carried per CFM per kelvin of air temperature rise [W/(CFM*K)] -- rho*c_p for air at
#: ~300 K. The spreadsheet's dT=50 K case reproduces this exactly (0.0351 CFM/W).
AIR_W_PER_CFM_K = 0.569


class FanCoolingModel(object):
    """Airflow and fan power required to carry a heat load at a given air temperature rise.

    Calibrated against the Maxwell Labs fan data. The physics is just an energy balance on the
    air stream::

        CFM    = Q / (AIR_W_PER_CFM_K * dT_air)
        P_fan  = MXL_FAN_W_PER_CFM * CFM

    so **fan power scales as Q / dT_air**. That inverse dependence is the lever in the hybrid
    trade: letting the air run hotter is dramatically cheaper (their own table drops
    100 W-chip fan power from 6.91 W to 2.07 W going from dT 15 K to 50 K), but a hotter air
    stream raises the effective ambient the die sees, which costs temperature margin. MR
    attacks the hotspot instead, leaving the bulk air stream free to run hot and cheap.

    ``effective_ambient_K`` is where that trade shows up: air enters at ``T_inlet`` and leaves
    ``dT_air`` hotter, so the sink sees roughly the mean. Using the mean rather than the inlet
    is the conservative choice and is what makes higher dT_air cost something.
    """

    def __init__(self, w_per_cfm=MXL_FAN_W_PER_CFM, air_w_per_cfm_K=AIR_W_PER_CFM_K,
                 inlet_K=303.15, calibrated=True):
        if w_per_cfm <= 0 or air_w_per_cfm_K <= 0:
            raise ValueError('fan constants must be > 0')
        self.w_per_cfm = float(w_per_cfm)
        self.air_w_per_cfm_K = float(air_w_per_cfm_K)
        self.inlet_K = float(inlet_K)
        self.calibrated = bool(calibrated)

    def cfm_for(self, heat_W, dt_air_K):
        if heat_W < 0:
            raise ValueError('heat_W must be >= 0')
        if dt_air_K <= 0:
            raise ValueError('dt_air_K must be > 0')
        return float(heat_W) / (self.air_w_per_cfm_K * float(dt_air_K))

    def fan_power_for(self, heat_W, dt_air_K):
        """Electrical fan power [W] to carry ``heat_W`` at air rise ``dt_air_K``."""
        return self.w_per_cfm * self.cfm_for(heat_W, dt_air_K)

    def dt_air_for_budget(self, heat_W, fan_budget_W):
        """Air temperature rise implied by spending ``fan_budget_W`` on the fan.

        The inverse of ``fan_power_for`` -- this is what the optimiser calls when it allocates
        part of a cooling budget to the fan. Returns inf for a zero budget (no forced airflow).
        """
        if fan_budget_W <= 0:
            return float('inf')
        cfm = float(fan_budget_W) / self.w_per_cfm
        return float(heat_W) / (self.air_w_per_cfm_K * cfm) if cfm > 0 else float('inf')

    def effective_ambient_K(self, dt_air_K):
        """Ambient the sink effectively sees: inlet plus half the air temperature rise."""
        return self.inlet_K + 0.5 * float(dt_air_K)


#: HS483 calibration measured against the repaired heatsink FMU (2026-08-12): five fan speeds
#: driven to equilibrium at 35 W, R_th taken as (T_die_mean - T_air)/Q over a 28.39 mm^2 die.
#: Fit is to the FORCED-convection branch only (1500-6000 RPM), residuals <= 0.003 K/W.
HS483_FIT = {'R0': 30.08, 'R_inf': 18.34, 'm': 1.6531, 'u_per_rpm': 1.0 / 1500.0}

#: Fan-off is a genuinely different regime and is NOT on that curve -- the Modelica model uses
#: a constant htc = 2.8 W/(m^2 K) for zero air velocity versus a quadratic correlation above
#: 1 m/s. Measured 2.2827 K/W, 2.7x the 1500 RPM value (and still settling, so an
#: under-estimate). Forcing it onto the forced-convection fit biased R0 by -1.19 K/W.
HS483_NATURAL_CONVECTION_R_TH = 2.2827   # K/W over 28.39 mm^2


class PumpedSink(SinkModel):
    """Bulk cooler whose thermal resistance and power draw both depend on a fan/pump setting.

    Functional form taken from the Maxwell Labs MR model
    (``docs/chip_microrefrigeration_stable_v1.ipynb``), so the hybrid optimisation here and the
    reduced-order model there describe the same device::

        R_ext(u) = R_inf + (R0 - R_inf) / (1 + u**m)         [K*mm^2/W]
        p_pump(u) = p_static + p_scale * u**n * ((1+u^2)/(2u))**r   [W/mm^2]

    ``u`` is the normalised fan/pump setting (0 = off, natural convection at ``R0``; large u
    asymptotes to ``R_inf``). Both quantities are **area-normalised** in the notebook's
    convention, so this class divides/multiplies by the die area to get K/W and W --
    the same referencing as ``ThermalResistanceSink``.

    This is what makes "how should a fixed cooling budget be split between fan and MR?" a
    well-posed question: turning the fan up costs ``p_pump`` and buys ``R_ext``, with strongly
    diminishing returns, while MR spends the same watts on the hotspot instead.
    """

    def __init__(self, u, area_m2, R0=60.0, R_inf=15.0, m=1.0,
                 p_static=0.02, p_scale=0.02, n=3.0, r=1.0,
                 ambient_K=303.15, label=None, calibrated=False):
        super().__init__(ambient_K=ambient_K, label=label or 'PumpedSink(u={:.3g})'.format(u))
        if u < 0:
            raise ValueError('u must be >= 0')
        if R_inf <= 0 or R0 < R_inf:
            raise ValueError('need R0 >= R_inf > 0 (K*mm^2/W)')
        self.u = float(u)
        self.area_mm2 = float(area_m2) * 1.0e6
        self.R0, self.R_inf, self.m = float(R0), float(R_inf), float(m)
        self.p_static, self.p_scale, self.n, self.r = (float(p_static), float(p_scale),
                                                       float(n), float(r))
        self.calibrated = bool(calibrated)
        self.parasitic_known = True     # this model *does* describe its own power draw

    def r_area(self):
        """Area-normalised external thermal resistance [K*mm^2/W] at this setting."""
        return self.R_inf + (self.R0 - self.R_inf) / (1.0 + self.u ** self.m)

    def thermal_resistance(self, area_m2=None):
        """R_th [K/W] over the die area."""
        a = self.area_mm2 if area_m2 is None else float(area_m2) * 1.0e6
        return self.r_area() / a

    def htc_si(self):
        return thermal_resistance_to_htc_si(self.thermal_resistance(),
                                            self.area_mm2 / 1.0e6)

    def pump_power_density(self):
        """W/mm^2 drawn at this setting. Zero when the fan is off."""
        if self.u <= 0:
            return 0.0
        shape = self.u ** self.n * ((1.0 + self.u ** 2) / (2.0 * self.u)) ** self.r
        return self.p_static + self.p_scale * shape

    def parasitic_power_W(self):
        return self.pump_power_density() * self.area_mm2

    @classmethod
    def for_power_budget(cls, budget_W, area_m2, u_max=8.0, steps=512, **kw):
        """Largest fan setting whose draw fits ``budget_W`` (None if even u->0 does not).

        Used by the hybrid optimiser to convert "spend X watts on the fan" into a sink.
        """
        if budget_W < 0:
            raise ValueError('budget_W must be >= 0')
        best = None
        for i in range(steps + 1):
            u = u_max * i / steps
            cand = cls(u, area_m2, **kw)
            if cand.parasitic_power_W() <= budget_W:
                best = cand
            else:
                break
        return best

    def describe(self):
        return '{} (u={:.3g}, R_th={:.4g} K/W, P_fan={:.3g} W)'.format(
            super().describe(), self.u, self.thermal_resistance(), self.parasitic_power_W())


# ---------------------------------------------------------------------------
# HS483 air cooler -- the FMU's own physics, made steady-solvable
# ---------------------------------------------------------------------------
class HS483AirSink(SinkModel):
    """Surrogate for the HS483-ND copper heatsink + P14752-ND fan FMU.

    The fin-level convection correlation is taken verbatim from the FMU's Modelica source
    (``3d-ice/heatsink_plugin/heatsinks/HS483/HS483.mo``, ``convectionCorrelation``)::

        htc = 0.8793 * (11.8 + 9.33*v - 1.09*v^2)   W/(m^2 K),  v in [1, 4.1] m/s
        htc = 2.8                                    natural convection (v = 0)

    That coefficient applies to the **fin surface**, not the die. Converting it to the
    die-referenced coefficient 3D-ICE wants requires an area/efficiency factor
    (``area_ratio``) that folds in total fin area, fin efficiency, and base spreading. That
    factor is NOT derivable from the correlation alone -- it must be calibrated against the
    real FMU (``examples/calibrate_sink_surrogate.py``). Until it is, ``calibrated`` stays
    False and ``describe()`` says so.

    Validity limits from the model's own documentation -- **exceeded by real workloads**:
    fan 1500-6000 RPM (or 0), and dissipated power **< 40 W**. Above 40 W the air film
    approaches the fin half-spacing and the fit leaves its validated regime. Our 7nm linpack
    trace is already ~49 W, and server parts are 300-700 W, so this model is a method
    validation vehicle, not a source of customer-facing numbers.
    """

    #: Modelica convectionCorrelation coefficients (HS483.mo)
    C0, C1, C2 = 11.8, 9.33, -1.09
    SCALE = 0.8793
    NATURAL_CONVECTION_HTC = 2.8
    VELOCITY_RANGE = (1.0, 4.1)      # m/s, correlation fitting range
    RPM_RANGE = (1500.0, 6000.0)     # matching fan speed range
    MAX_VALIDATED_POWER_W = 40.0

    def __init__(self, fan_rpm, area_ratio=1.0, ambient_K=303.15, label=None,
                 calibrated=False, fan_power_W=None, strict=True):
        super().__init__(ambient_K=ambient_K, label=label or 'HS483@{:.0f}rpm'.format(fan_rpm))
        self.fan_rpm = float(fan_rpm)
        self.area_ratio = float(area_ratio)
        self.calibrated = bool(calibrated)
        self._fan_power = fan_power_W
        self.parasitic_known = fan_power_W is not None
        self.velocity_m_s = self.rpm_to_velocity(self.fan_rpm, strict=strict)

    @classmethod
    def rpm_to_velocity(cls, fan_rpm, strict=True):
        """Fan RPM -> air velocity [m/s] across the fins.

        The Modelica model derives this from a fan curve and flow-rate coefficient; here it is
        a linear map across the documented endpoints (1500 RPM -> 1.0 m/s, 6000 RPM -> 4.1
        m/s). That is an approximation and a calibration target, not the FMU's exact
        behaviour. 0 RPM means natural convection.
        """
        fan_rpm = float(fan_rpm)
        if fan_rpm == 0.0:
            return 0.0
        rpm_lo, rpm_hi = cls.RPM_RANGE
        v_lo, v_hi = cls.VELOCITY_RANGE
        if strict and not (rpm_lo <= fan_rpm <= rpm_hi):
            raise ValueError(
                'fan_rpm {:.0f} outside the HS483 validated range {:.0f}-{:.0f} RPM (or 0 for '
                'natural convection). Pass strict=False to extrapolate anyway.'.format(
                    fan_rpm, rpm_lo, rpm_hi))
        frac = (fan_rpm - rpm_lo) / (rpm_hi - rpm_lo)
        return v_lo + frac * (v_hi - v_lo)

    @classmethod
    def fin_htc_si(cls, velocity_m_s):
        """The FMU's fin-surface convection coefficient, W/(m^2 K)."""
        v = float(velocity_m_s)
        if v == 0.0:
            return cls.NATURAL_CONVECTION_HTC
        return cls.SCALE * (cls.C0 + cls.C1 * v + cls.C2 * v ** 2)

    def htc_si(self):
        return self.fin_htc_si(self.velocity_m_s) * self.area_ratio

    def parasitic_power_W(self):
        return 0.0 if self._fan_power is None else float(self._fan_power)

    def power_within_validity(self, total_power_W):
        """True if ``total_power_W`` is inside the FMU's validated (<40 W) envelope."""
        return float(total_power_W) <= self.MAX_VALIDATED_POWER_W


# ---------------------------------------------------------------------------
# Rendering a concrete stack file for a given sink
# ---------------------------------------------------------------------------
def chip_area_m2_from_floorplan(flp_template):
    """Chip footprint [m^2] from a floorplan file -- the area the HTC is referenced to."""
    from HotGauge.thermal.ICE import Floorplan
    flp = Floorplan.from_file(flp_template)
    return (flp.width * flp.height) / UM2_PER_M2


def render_stack_with_sink(base_stack_template, sink, out_path):
    """Write a copy of ``base_stack_template`` with the sink's HTC and ambient substituted.

    Kept as file rendering rather than a change to ``ICESim.fill_stk_template`` so nothing in
    stock HotGauge moves: the result is just another stack-template path to hand to
    ``ICEThermalSolver``. The base template must use the conventional ``top heat sink``
    (a pluggable one cannot be steady-solved -- ``assert_steady_supported`` will reject it).

    Returns ``out_path``.
    """
    with open(base_stack_template) as f:
        contents = f.read()

    contents, n_htc = _HTC_RGX.subn(
        lambda m: '{}{:.6e}{}'.format(m.group(1), sink.htc_3dice(), m.group(3)), contents)
    if n_htc != 1:
        raise ValueError(
            'Expected exactly one "heat transfer coefficient" in {}, found {}. A pluggable '
            'stack has none and cannot be used for a steady sink study.'.format(
                base_stack_template, n_htc))

    contents, n_temp = _TEMP_RGX.subn(
        lambda m: '{}{:.6f}{}'.format(m.group(1), sink.ambient_K, m.group(3)), contents, count=1)
    if n_temp != 1:
        raise ValueError('Expected an ambient "temperature" line in {}'.format(
            base_stack_template))

    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        f.write(contents)
    return out_path


def fit_area_ratio(measured_htc_si, fan_rpm, strict=False):
    """Calibrate ``HS483AirSink.area_ratio`` from a measured die-referenced HTC.

    ``measured_htc_si`` comes from a reference run: ``h = Q / (A * (T_die - T_amb))``, i.e.
    ``1 / (R_th * A)``. Dividing by the correlation's fin-surface coefficient gives the
    area/efficiency factor the surrogate needs.
    """
    v = HS483AirSink.rpm_to_velocity(fan_rpm, strict=strict)
    fin_htc = HS483AirSink.fin_htc_si(v)
    if fin_htc <= 0:
        raise ValueError('Non-positive fin HTC for fan_rpm={!r}'.format(fan_rpm))
    return float(measured_htc_si) / fin_htc


# ---------------------------------------------------------------------------
# SimScale baffled-fin heatsink surrogate
# ---------------------------------------------------------------------------
# From the Maxwell Labs SimScale CFD study (docs/SimScale/Write_up/). A baffled fin stack was
# simulated over air speeds of 10-200 CFM, sweeping the power injected into the bulk core area
# (P_core) and into a functional-unit region (P_FU) independently. The resulting peak chip
# temperature fits bi-linearly:
#
#     T_max = T_0 + alpha(v) * P_core + beta(v) * P_FU
#
# This is the server-class replacement for HS483AirSink, whose HTC correlation is only valid
# over 1.0-4.1 m/s on a 60 mm open desktop tower. Three things make it the right model for
# scaling to HPC:
#
#   1. It covers the ducted/baffled server regime at HPC power (the study ran P_core = 290 W,
#      P_FU = 70 W) rather than a desktop tower at 23 W.
#   2. alpha and beta separate *distributed* from *localised* power -- exactly the split
#      between core power and the functional-unit hotspot that microrefrigeration targets.
#   3. It carries a realistic fan power curve, 18-215 W with discrete jumps where the best
#      available fan changes.
#
# CAVEAT: the coefficients below are digitised from Figure 3 of the write-up, and the fan
# segments from Figure 1(a), because docs/SimScale/{Scripts,data,Fan_laws}/ copied over empty.
# They reproduce the published curves but are not the original fitted values. Replace them
# from the source data before quoting numbers externally.
#
# CAVEAT 2: this fit is *linear* in power -- the CFD had no temperature-dependent leakage.
# That is precisely what HotGauge adds, so the two compose: SimScale supplies the boundary
# condition, HotGauge supplies the leakage feedback and the performance model.

#: Sensitivity of peak chip temperature to *distributed* core power [K/W] vs airflow [CFM].
#: alpha_on and alpha_off are superposed in the source figure, so one curve serves both.
SIMSCALE_ALPHA_K_PER_W = (
    (10, 0.800), (20, 0.500), (30, 0.410), (40, 0.360), (50, 0.335), (60, 0.320),
    (70, 0.305), (80, 0.290), (90, 0.280), (100, 0.270), (120, 0.260), (140, 0.250),
    (160, 0.242), (180, 0.235), (200, 0.230),
)

#: Sensitivity of peak chip temperature to *functional-unit* power [K/W] vs airflow [CFM].
#: Always far above alpha: a watt injected in a hotspot costs several times what a watt spread
#: over the core costs, and -- crucially -- airflow barely moves it.
SIMSCALE_BETA_K_PER_W = (
    (10, 1.900), (20, 1.555), (30, 1.445), (40, 1.410), (50, 1.375), (60, 1.355),
    (70, 1.340), (80, 1.325), (90, 1.315), (100, 1.305), (120, 1.290), (140, 1.285),
    (160, 1.280), (180, 1.275), (200, 1.270),
)

#: Piecewise fan power [W] vs airflow [CFM] as ``(cfm_lo, cfm_hi, intercept_W, W_per_CFM)``.
#: Three fan models, each linear over the band where it is the best available choice. The
#: discontinuities at the handovers are physical -- you cannot buy a fan between them -- and
#: they are why the study found best-COP at *nonzero* laser power: cooling the hotspot
#: optically lets the system stay on the cheaper fan instead of jumping to the next one.
SIMSCALE_FAN_SEGMENTS = (
    (0.0, 88.0, 18.0, 0.193),
    (88.0, 133.0, 62.0, 0.286),
    (133.0, 200.0, 100.0, 0.575),
)

#: Reference air temperature used throughout the SimScale study [K] (19.85 C).
SIMSCALE_T0_K = 293.0


def _interp_table(table, x):
    """Linear interpolation over a sorted ``((x, y), ...)`` table, clamped at both ends."""
    xs = [p[0] for p in table]
    ys = [p[1] for p in table]
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            f = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + f * (ys[i] - ys[i - 1])
    return ys[-1]


def simscale_alpha(cfm):
    """Peak-temperature sensitivity to distributed core power [K/W] at ``cfm`` airflow."""
    return _interp_table(SIMSCALE_ALPHA_K_PER_W, float(cfm))


def simscale_beta(cfm):
    """Peak-temperature sensitivity to functional-unit power [K/W] at ``cfm`` airflow."""
    return _interp_table(SIMSCALE_BETA_K_PER_W, float(cfm))


def simscale_fan_power(cfm):
    """Electrical power [W] of the best available fan delivering ``cfm``.

    Above the top of the last segment the fit is extrapolated; the study did not simulate
    beyond 200 CFM, so treat anything past it as an estimate.
    """
    cfm = float(cfm)
    if cfm <= 0:
        return 0.0
    for lo, hi, b, m in SIMSCALE_FAN_SEGMENTS:
        if lo < cfm <= hi:
            return b + m * cfm
    lo, hi, b, m = SIMSCALE_FAN_SEGMENTS[-1]
    return b + m * cfm


#: Laser watts spent per watt extracted at the functional unit, ``P_laser = eta_laser*P_extr``.
#: This is the SimScale write-up's *cost* convention and is the RECIPROCAL of the ASF optical
#: efficiency used elsewhere in HotGauge (``MRParams.eta_asf``): at 20% ASF efficiency,
#: extracting 1 W costs 5 W of laser, so eta_laser = 5.0. Getting this upside down makes laser
#: cooling look 25x cheaper than it is.
#:
#: Four numbers get confused here, so all four are named. The default stays at the ASF-optical
#: reciprocal because that is the assumption the rest of HotGauge is built on.
SIMSCALE_ETA_LASER = 5.0

#: What the write-up itself assumed -- *not* stated in its text. Inferred from the Fig. 4
#: contour plot, whose P_laser axis reaches 175 W at P_FU = 70 W (Eq. 4's ratio
#: ``P_laser/(eta*P_FU)`` hits 1 at full extraction, so eta = 175/70 = 2.5), and cross-checked
#: against its statement that 150 C is unreachable below P_laser ~ 50 W: this model gives
#: ~59 W on that contour, consistent to digitisation accuracy.
SIMSCALE_ETA_LASER_AS_PUBLISHED = 2.5

#: Our gross cost including the laser's own wall-plug efficiency:
#: ``1 / (eta_asf 0.20 * laser_wallplug 0.70)``. Worse than either of the above, because the
#: study charged only the optical conversion and not the laser driver.
SIMSCALE_ETA_LASER_MXL_GROSS = 7.14

#: Our cost net of LPC recovery: ``gross * (1 - breakeven_ratio)`` at breakeven 0.756.
#: The reconciliation worth knowing -- the study has no LPC, so with recovery our net cost is
#: *better* than what it assumed. Its COP conclusions are therefore mildly conservative against
#: our current MR model rather than optimistic, provided the recovery path is real.
SIMSCALE_ETA_LASER_MXL_NET_LPC = 1.74


def simscale_tmax_K(cfm, p_core_W, p_fu_W, p_laser_W=0.0, eta_laser=SIMSCALE_ETA_LASER,
                    t0_K=SIMSCALE_T0_K):
    """Peak chip temperature [K] under combined air and laser cooling.

    Implements Eq. (4) of the write-up. Extracting ``P_extr = P_laser / eta_laser`` at the
    functional units interpolates between the "hotspot on" and "hotspot fully cancelled"
    regimes; ``P_extr = P_FU`` removes the hotspot contribution entirely.

    See ``SIMSCALE_ETA_LASER`` -- ``eta_laser`` is a cost multiplier, not an efficiency.
    """
    p_fu_W = float(p_fu_W)
    a = simscale_alpha(cfm)
    b = simscale_beta(cfm)
    if p_fu_W <= 0:
        return t0_K + a * float(p_core_W)
    # Fraction of the functional-unit hotspot cancelled by extraction, capped at 1.
    frac = float(p_laser_W) / (float(eta_laser) * p_fu_W)
    frac = max(0.0, min(1.0, frac))
    # alpha_on and alpha_off are superposed in the source data, so the P_core bracket in
    # Eq. (4) collapses to alpha; kept explicit for when the real coefficients land.
    return t0_K + a * float(p_core_W) + b * (1.0 - frac) * p_fu_W


#: Wall-plug efficiency (pneumatic out / electrical in) of the fan in each band -- its COP.
#:
#: The write-up's three fans are identified from ``Mathematica_files/Results_3.nb``, which sets
#: ``nfans = 4`` and carries the datasheet voltage sweeps verbatim -- ``QCFM2``/``Ptot2`` are
#: the PFB0412EN-E (22.24-35.93 CFM, 37.82-46.20 W) and ``QCFM``/``Ptot`` the PFB0412EHN-TP06.
#: Times four they reproduce the figure's bands; the PFB0412EN-E check is 89-144 CFM at
#: 151-185 W against figure points at 88-150 CFM and 150-185 W.
#:
#: | band | fan (x4) | CFM x4 | W x4 | eta |
#: |------|----------|--------|------|-----|
#: | low  | PFB0412EHN-TP06 | 0-88   | 21-31  | 0.125 |
#: | mid  | FFB0412EN-00Y2E | 0-133  | 62-100 | 0.197 |
#: | high | PFB0412EN-E     | 89-144 | 151-185| 0.263 |
#:
#: Note the ordering: the *cheap* band is the *least* efficient fan. Cheap here means low
#: absolute power, not efficient use of it -- so the minimum-power operating point sits on the
#: worst-COP fan. An earlier single-value stand-in of 0.263 overstated the fan stage by 2.1x
#: exactly where it matters.
SIMSCALE_FAN_COP_BANDS = (
    (88.0, 0.125),
    (133.0, 0.197),
    (float('inf'), 0.263),
)

#: Efficiency of the best fan in the set, kept for the "what if we always had the good fan"
#: comparison. Not the right default -- see :func:`simscale_fan_cop`.
SIMSCALE_FAN_COP_BEST = 0.263


def simscale_fan_cop(cfm):
    """Wall-plug efficiency of whichever fan bank is carrying ``cfm``."""
    cfm = float(cfm)
    for hi, eta in SIMSCALE_FAN_COP_BANDS:
        if cfm <= hi:
            return eta
    return SIMSCALE_FAN_COP_BANDS[-1][1]


def cooling_cop(cfm, p_laser_W=0.0, fan_cop=None, mr_cop=0.14):
    """Wall-plug COP of the whole cooling system: useful cooling out per watt drawn in.

    Deliberately **not** the write-up's Eq. 1, ``(P_inj + P_cool)/P_cool``, which is >= 1 by
    construction and so cannot express that a cooling stage costs more than it delivers. Here
    every stage is charged on the same basis -- useful output over wall-plug input -- so the
    result is a true efficiency below 1, directly comparable to ``MRParams.cop``::

        COP = (fan_cop * P_fan + mr_cop * P_laser) / (P_fan + P_laser)

    With the laser off this reduces to ``fan_cop``, the fan's aerodynamic wall-plug efficiency:
    a 10% efficient fan is a COP of 0.10. With the laser on it is the power-weighted blend of
    the two stages, so adding MR raises the system COP exactly when MR's COP beats the fan's.

    ``fan_cop`` defaults to :func:`simscale_fan_cop`, which picks the efficiency of whichever
    fan bank is carrying ``cfm`` (0.125 / 0.197 / 0.263 by band). Pass a scalar to override.

    That comparison is the useful one. Below 88 CFM the fan bank is only 12.5% efficient, so
    MR at 0.14 gross already matches it and beats it outright at ~0.57 net of LPC recovery. But
    the deeper reason MR wins is not stage efficiency at all: ``beta`` makes hotspot watts worth
    several times more than distributed watts, so a low-COP watt spent at the hotspot buys more
    temperature than a high-COP watt spent at the fins.
    """
    if fan_cop is None:
        fan_cop = simscale_fan_cop(cfm)
    p_fan = simscale_fan_power(cfm)
    p_laser = float(p_laser_W)
    total = p_fan + p_laser
    if total <= 0:
        return float('nan')
    return (fan_cop * p_fan + mr_cop * p_laser) / total


#: ``alpha(v) = R_cond + amp * v^-n`` fitted to the digitised curve (max residual 0.011 K/W).
#: The split matters: only the second term depends on airflow, so only it is the *convective
#: boundary*. ``alpha`` itself is an END-TO-END resistance -- die peak to air -- that already
#: contains the SimScale die's own conduction and spreading.
SIMSCALE_ALPHA_FIT = {'r_cond': 0.2018, 'amp': 5.2190, 'n': 0.9434}

#: Same decomposition for ``beta``. Note the convective terms of alpha and beta are nearly
#: identical (0.076 vs 0.070 K/W at 88 CFM) -- as they must be, since both see the same fins.
#: The entire alpha/beta gap lives in the conduction floor: 0.2018 vs 1.2442 K/W.
SIMSCALE_BETA_FIT = {'r_cond': 1.2442, 'amp': 6.9315, 'n': 1.0262}


#: The one point where we have SimScale's coefficients EXACTLY rather than digitised.
#: ``docs/SimScale/data/tT0.dat`` is a 46,928-point (P_core, P_FU, T_max) grid spanning
#: 0.1-509 W and 0.1-109 W; a bilinear least-squares fit returns
#: ``T = 19.8500 + 0.270726*P_core + 1.314024*P_FU`` with **zero** residual, so these are the
#: study's own coefficients, and the intercept reproduces its stated T_0 = 19.85 C exactly.
#:
#: Two independent checks come out of it:
#:
#: * the digitised curves are good -- alpha off by -0.27%, beta by -0.69% at 100 CFM;
#: * ``beta - alpha = 1.0433 K/W`` here, against 1.0424 K/W from the fitted conduction floors.
#:   That 0.09% agreement matters more than it looks: the constriction resistance was derived
#:   from the *shape* of two digitised curves, and an exact source point confirms it. The MR
#:   argument does not rest on the digitisation.
#:
#: Inverting the decomposition gives ~98 CFM from alpha and ~88 CFM from beta, so the grid is
#: the 100 CFM case (the residual spread is digitisation error in the fits, not in this data).
#: ``data/tCOP1b.dat`` pins the "off" scenario at the same airflow, also with zero residual:
#: ``T = 19.8500 + 0.271718*P_core + 0.000000*P_FU``. The P_FU coefficient is identically zero,
#: which is what "hotspot fully cancelled" means. Comparing the two grids verifies the
#: write-up's claim that alpha_on and alpha_off are superposed -- 0.270726 vs 0.271718, a 0.37%
#: difference -- which is why Eq. (4)'s P_core bracket collapses to a single alpha.
SIMSCALE_EXACT_ANCHOR = {'cfm': 100.0, 'alpha': 0.270726, 'alpha_off': 0.271718,
                         'beta': 1.314024, 't0_C': 19.85,
                         'source': 'docs/SimScale/data/tT0.dat (on), tCOP1b.dat (off)'}


def simscale_convective_r_th(cfm):
    """The airflow-dependent part of the SimScale sink resistance [K/W].

    This -- not ``alpha`` -- is what belongs in a 3D-ICE ``top heat sink`` boundary. 3D-ICE
    models the die's own conduction and spreading from the floorplan, so handing it ``alpha``
    double-counts that path and produces spurious thermal runaway.
    """
    f = SIMSCALE_ALPHA_FIT
    cfm = float(cfm)
    if cfm <= 0:
        return float('inf')
    return f['amp'] * cfm ** (-f['n'])


def simscale_constriction_r_th():
    """Hotspot constriction resistance [K/W]: ``beta`` conduction floor minus ``alpha``'s.

    1.042 K/W for a 200 um hotspot in 0.5 mm silicon -- the resistance between a
    functional-unit-scale source and the bulk die. It is a *conduction* term and is therefore
    completely unaffected by airflow, which is the mechanistic reason no fan can fix a hotspot
    and why cooling has to be applied at the hotspot itself.
    """
    return SIMSCALE_BETA_FIT['r_cond'] - SIMSCALE_ALPHA_FIT['r_cond']


class BaffledFinSink(SinkModel):
    """Server-class baffled fin stack, from the SimScale CFD study.

    Presents the **convective** resistance only (``simscale_convective_r_th``), because 3D-ICE
    resolves the die's own conduction and spreading from the floorplan. Passing the full
    end-to-end ``alpha`` here would count the die path twice -- which in practice showed up as
    a 100 W die "running away" that the CFD placed at a comfortable 48 C.

    ``alpha`` and ``beta`` remain available as *validation targets*: an end-to-end solve on a
    comparable die should reproduce them, and ``beta - alpha`` predicts the hotspot penalty our
    floorplan model ought to produce independently.
    """

    parasitic_known = True
    calibrated = True

    def __init__(self, cfm, area_m2, ambient_K=SIMSCALE_T0_K, label=None):
        super().__init__(ambient_K=ambient_K, label=label or 'BaffledFinSink')
        self.cfm = float(cfm)
        self.area_m2 = float(area_m2)
        self.r_th_K_per_W = simscale_convective_r_th(self.cfm)
        self.alpha_end_to_end = simscale_alpha(self.cfm)
        self._h_si = thermal_resistance_to_htc_si(self.r_th_K_per_W, self.area_m2)

    def htc_si(self):
        return self._h_si

    def parasitic_power_W(self):
        return simscale_fan_power(self.cfm)

    @property
    def beta_K_per_W(self):
        """Hotspot sensitivity [K/W] -- the quantity microrefrigeration acts on."""
        return simscale_beta(self.cfm)

    @property
    def hotspot_penalty(self):
        """``beta / alpha``: how much worse a watt is at a functional unit than spread out.

        Referenced to the END-TO-END coefficients, not to this sink's convective resistance --
        the penalty is a property of the die, not of the fins.
        """
        return self.beta_K_per_W / self.alpha_end_to_end

    def describe(self):
        return ('{} (SimScale, {:.0f} CFM: R_conv={:.4g} K/W [sink boundary], '
                'alpha={:.4g}, beta={:.4g} K/W end-to-end, beta/alpha={:.2f}, '
                'P_fan={:.1f} W)'.format(
                    super().describe(), self.cfm, self.r_th_K_per_W, self.alpha_end_to_end,
                    self.beta_K_per_W, self.hotspot_penalty, self.parasitic_power_W()))


class SpreadingSink(SinkModel):
    """Wraps a convective sink with the conduction path into an **overhanging** base.

    What this is for
    ----------------
    3D-ICE gives every layer exactly the die footprint. A cold plate modelled as a slab in the
    stack is therefore a column of metal the width of the die, and the package budget comes out
    proportional to 1/area -- measured 0.0402 K/W at 826 mm^2 against 0.3648 at 91 mm^2, which is
    9.08x for 9.08x the area. There is no way to declare the overhang instead: the grammar's
    conventional ``top heat sink`` accepts only a coefficient and a temperature, and the pluggable
    sink that does carry ``spreader length/width/height`` cannot be steady-solved.

    So the base moves out of the stack and into the boundary. The wrapped sink keeps supplying the
    convective and caloric resistance -- which already knows about the overhang, because
    :class:`~HotGauge.thermal.cooling_spec.CoolingSpec` sizes its fins on ``base_area_mm2`` -- and
    this class adds the spreading and conduction from the die footprint into that base. The result
    is presented as one coefficient over the die footprint, which is what 3D-ICE wants.

    **Use it with a stack that has no sink slab** (``StackSpec(sink_in_stack=False)``). Leaving
    the slab in place double-counts the base, and the double count is invisible: it just makes
    every part run hot.

    What it does not do
    -------------------
    The base is lumped, so lateral gradients *inside* the cold plate are not resolved. The die's
    own silicon spreading is still solved by 3D-ICE, so the approximation sits in the package
    rather than in the within-die peak this project reports.
    """

    def __init__(self, sink, die_area_mm2, base_area_mm2=None, base_thickness_mm=2.0,
                 base_k_W_mK=300.0, series_above_base=(), ambient_K=None, label=None):
        from HotGauge.thermal.cooling_spec import base_area_from_footprint

        self.sink = sink
        self.die_area_mm2 = float(die_area_mm2)
        if base_area_mm2 is None:
            # Prefer the wrapped spec's own base if it has one -- it is sized by cooler class and
            # validated against published parts. The fixed footprint is only a fallback.
            spec = getattr(sink, 'spec', None)
            base_area_mm2 = (getattr(spec, 'base_area_mm2', None)
                             or base_area_from_footprint(die_area_mm2))
        self.base_area_mm2 = float(base_area_mm2)
        self.base_thickness_mm = float(base_thickness_mm)
        self.base_k_W_mK = float(base_k_W_mK)
        # Layers sitting on top of the spreading base -- grease, the cold-plate metal on a lidded
        # part. They act over the BASE area, not the die's, which is the point of moving them:
        # 30 um of grease is 0.082 K/W across a 91 mm^2 die and 0.004 across an 1825 mm^2 plate.
        # Supply as (name, thickness_mm, k_W_mK); StackSpec.boundary_series_layers() emits them.
        self.series_above_base = tuple(series_above_base)
        if ambient_K is None:
            ambient_K = getattr(sink, 'ambient_K', 303.15)
        super().__init__(ambient_K=ambient_K,
                         label=label or 'Spreading[{}]'.format(getattr(sink, 'label', sink)))

    @property
    def parasitic_known(self):
        return bool(getattr(self.sink, 'parasitic_known', False))

    @property
    def calibrated(self):
        return bool(getattr(self.sink, 'calibrated', False))

    def _external_r_K_per_W(self):
        """The wrapped sink's own resistance [K/W]: convection and caloric, no conduction.

        **The area this is evaluated over is the whole point of the class**, and getting it
        wrong is silent: it cancels the overhang exactly and leaves the answer tracking 1/area
        as if nothing had been done. Two conventions meet here and they are not the same:

        * A sink that quotes ``r_th_K_per_W`` -- ``ThermalResistanceSink``, ``CoolingSpecSink``
          -- means a WHOLE-COOLER resistance: "a 0.12 K/W tower". That is already an absolute
          K/W and is used as it stands.
        * A plain :class:`SinkModel` is a COEFFICIENT, and a coefficient has no meaning without
          an area. The area a cooler's h acts over is its own wetted base -- the plate it is
          bolted to -- not the die underneath it. Evaluating it over the die footprint says
          "a 1825 mm^2 cold plate that only exchanges heat over the 53 mm^2 directly above the
          die", which is not a cooler; and because ``total_resistance_K_per_W`` then converts
          back with ``h_base = 1/(r_ext * base_area)``, the two area factors cancel and the
          overhang buys exactly nothing. Measured while wiring this into the drivers: 15.2x
          across the die-size range instead of the 2.6x in
          ``docs/evidence/direct_die_overhang.json``, against 15.5x for the slab it replaces.
          The evidence file states the convention outright -- "the die spreads into an 1825 mm^2
          copper base and the cooler acts over THAT area".
        """
        r = getattr(self.sink, 'r_th_K_per_W', None)
        if r is not None:
            return float(r)
        return self.sink.thermal_resistance(self.base_area_mm2 * 1e-6)

    def series_resistance_K_per_W(self):
        """Conduction through the layers above the base, over the base area."""
        area_m2 = self.base_area_mm2 * 1e-6
        return sum((float(t) * 1e-3) / (float(k) * area_m2)
                   for _, t, k in self.series_above_base)

    def total_resistance_K_per_W(self):
        """Die surface to ambient: spreading into the base, then out through it."""
        from HotGauge.thermal.cooling_spec import spreading_resistance_K_per_W

        r_ext = self._external_r_K_per_W() + self.series_resistance_K_per_W()
        if r_ext <= 0:
            raise ValueError('wrapped sink has non-positive resistance ({})'.format(r_ext))
        h_base = 1.0 / (r_ext * self.base_area_mm2 * 1e-6)
        return spreading_resistance_K_per_W(
            self.die_area_mm2, self.base_area_mm2, self.base_thickness_mm,
            self.base_k_W_mK, h_base)

    def htc_si(self):
        return 1.0 / (self.total_resistance_K_per_W() * self.die_area_mm2 * 1e-6)

    def parasitic_power_W(self):
        p = getattr(self.sink, 'parasitic_power_W', 0.0)
        return float(p() if callable(p) else p)

    def describe(self):
        return ('{}: R_total={:.4f} K/W over {:.0f} mm^2 die into a {:.0f} mm^2 base '
                '({:.1f} mm, k={:.0f}); h={:.4g} W/(m^2 K), T_amb={:.2f} K, P_cool={:.3g} W'
                .format(self.label, self.total_resistance_K_per_W(), self.die_area_mm2,
                        self.base_area_mm2, self.base_thickness_mm, self.base_k_W_mK,
                        self.htc_si(), self.ambient_K, self.parasitic_power_W()))


def external_r_for_spreading_total(total_r_K_per_W, die_area_mm2, base_area_mm2,
                                   base_thickness_mm=2.0, base_k_W_mK=300.0,
                                   series_above_base=(), tol=1e-9, max_iter=200):
    """Convective resistance a cooler must supply for :class:`SpreadingSink` to hit a total.

    The inverse of :meth:`SpreadingSink.total_resistance_K_per_W`, and the piece the acceptance
    gate needs. The gate works backwards: it takes a published junction-to-ambient figure,
    subtracts what the stack models, and asks what the external cooling has to deliver. With the
    base in the boundary that remainder is no longer the convective term alone -- it also contains
    the spreading and the layers above the base -- so solving the cooler against it directly would
    demand a cooler better than the target by exactly the spreading resistance.

    Monotone: more convective resistance can only raise the total, so a bisection is safe.
    Returns ``None`` when even a perfect cooler cannot reach the target, which is a real answer --
    it means the spreading alone exceeds the budget.
    """
    total = float(total_r_K_per_W)
    if total <= 0:
        raise ValueError('total resistance must be positive')

    def _total(r_ext):
        return SpreadingSink(
            ThermalResistanceSink(r_ext, die_area_mm2 * 1e-6), die_area_mm2,
            base_area_mm2=base_area_mm2, base_thickness_mm=base_thickness_mm,
            base_k_W_mK=base_k_W_mK, series_above_base=series_above_base
        ).total_resistance_K_per_W()

    lo = 1e-9
    if _total(lo) > total:
        return None                       # spreading alone already exceeds the budget
    hi = total
    while _total(hi) < total:             # widen until it brackets
        hi *= 2.0
        if hi > 1e6:
            return None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if _total(mid) < total:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def spreading_sink_for_stack(stack_name, sink, die_area_mm2, base_area_mm2=None,
                             base_thickness_mm=None, base_k_W_mK=None):
    """Wrap ``sink`` with the overhang the STACK implies, or refuse and say why.

    This is the join between the two halves of P0.4, and it exists so that the join has exactly
    one definition. The physics landed in :func:`spreading_resistance_K_per_W` and
    :class:`SpreadingSink`, and :class:`~HotGauge.thermal.die_stack.StackSpec` learned to hand its
    base out through ``boundary_base()`` / ``boundary_series_layers()`` -- but for a while nothing
    connected them, so every study driver still solved against a 2 mm slab at the die footprint.
    On the baseline stack at a fixed physical cooler that is 9.70 K/W where the overhang is 0.84,
    and it tracks 1/area: 15.5x across the die sizes this project models, against 2.6x.

    **The stack must have had its sink slab removed** (``sink_in_stack=False``, i.e.
    ``--stack spec:...,sink_in_stack=0``). Leaving the slab in place while also adding the base to
    the boundary counts the base twice, and the double count is silent -- it does not error, it
    just makes every part run hot, which is indistinguishable from a cooling result. So it is an
    error here, with the fix named, rather than a warning nobody reads.

    ``base_area_mm2`` defaults to the wrapped spec's own base when it has one (sized by cooler
    class and validated against published parts), and otherwise to the fixed socket footprint from
    :func:`~HotGauge.thermal.cooling_spec.base_area_from_footprint`. It is a fixed AREA and not a
    ratio of the die on purpose: the two SimScale models disagree on ratio precisely because the
    base is near-constant while the die is not, and a ratio would put 1/area straight back in.
    """
    from HotGauge.thermal.die_stack import is_spec_string, parse_spec_string

    if not is_spec_string(stack_name):
        raise ValueError(
            'the spreading boundary needs a generated stack so its base geometry is known, but '
            'got the template name {!r}. Use a spec string with the sink taken out of the stack, '
            'e.g. --stack spec:package=direct_die,mr=GAAS,sink_in_stack=0'.format(stack_name))
    spec = parse_spec_string(stack_name)
    if spec.sink_in_stack:
        raise ValueError(
            'stack {!r} still carries its sink slab, so adding a spreading base to the boundary '
            'would count the base TWICE -- silently, as a part that simply runs hot. Add '
            'sink_in_stack=0 to the spec.'.format(stack_name))
    base = spec.boundary_base()
    if base is None:
        raise ValueError(
            'stack {!r} declares no boundary base to spread into. Set sink_in_stack=0 (direct '
            'die) or package_in_boundary=1 (lidded).'.format(stack_name))
    t_mm, k = base
    return SpreadingSink(sink, die_area_mm2,
                         base_area_mm2=base_area_mm2,
                         base_thickness_mm=(t_mm if base_thickness_mm is None
                                            else base_thickness_mm),
                         base_k_W_mK=(k if base_k_W_mK is None else base_k_W_mK),
                         series_above_base=spec.boundary_series_layers())


# ---------------------------------------------------------------------------------------------
# Direct-die microchannel cold plate
# ---------------------------------------------------------------------------------------------
#: Measured reference point for a silicon direct-die microchannel heat sink.
#:
#: Source: docs/chip_design_lit/design_physics/microchannel-hotspot-limits-1-s2.0-
#: S0017931017340309-am.pdf -- banks of 50 high-aspect-ratio channels, 15-33 um wide and 35-470 um
#: deep, etched into the back of the die, nine sinks over a 5 x 5 mm heated area.
#:
#:   * 1020 W/cm^2 background flux dissipated at a chip temperature < 69 C above fluid inlet,
#:   * at a channel mass flux of 2100 kg/(m^2 s),
#:   * with a pressure drop below 120 kPa.
#:   * Hotspot fluxes to 2700 W/cm^2 raise the hotspot only 16 C above the background.
#:
#: Why this exists: CoolingSpec's water path models a FINNED BASE sized for the die, which is a
#: water block, not a cold plate. On the GA100 it returns ~0.055 K/W and bottoms its flow solver
#: out at a face velocity it then flags as unbuildable. The microchannel reference is ~7x better
#: and is what a direct-die part is actually cooled by.
MICROCHANNEL_REF = {
    'flux_W_per_m2': 1.020e7,        # 1020 W/cm^2
    'dT_chip_K': 69.0,               # above fluid inlet
    'mass_flux_kg_m2s': 2100.0,
    'dp_Pa': 1.20e5,                 # < 120 kPa
    'hotspot_flux_W_per_m2': 2.70e7, # 2700 W/cm^2
    'hotspot_dT_K': 16.0,            # above the background
    'source': ('microchannel-hotspot-limits-1-s2.0-S0017931017340309-am.pdf, '
               'Table 1 / s5.1.1 / abstract'),
}

#: Area-specific convective resistance implied by that point [K m^2 / W].
MICROCHANNEL_R_AREA = MICROCHANNEL_REF['dT_chip_K'] / MICROCHANNEL_REF['flux_W_per_m2']

#: The reference mass flux referred to the DIE FOOTPRINT rather than the channel cross-section,
#: so it can be compared with a configuration whose channel count is not a parameter.
#:
#: The paper's G is per channel: G = mdot / (2 Nsink Nc Ac), with Nsink=9, Nc=50 and, for the
#: 33x470 um sample, Ac = 1.551e-8 m^2. That is 900 channels of total area 1.396e-5 m^2 over a
#: 5 x 5 mm = 2.5e-5 m^2 footprint -- an open fraction of 0.558. So the footprint-referred flux
#: is 2100 * 0.558 = 1172 kg/(m^2 s), and the rig is running a fluid rise of only ~2 K.
MICROCHANNEL_OPEN_FRACTION = (2 * 9 * 50 * (33e-6 * 470e-6)) / (5e-3 * 5e-3)
MICROCHANNEL_REF_FLUX_DIE = (MICROCHANNEL_REF['mass_flux_kg_m2s']
                             * MICROCHANNEL_OPEN_FRACTION)


class MicrochannelSink(SinkModel):
    """Direct-die microchannel cold plate, anchored on a measured reference point.

    The die-to-fluid path is two terms:

    * **convective** -- the paper's area-specific resistance, scaled by die area. It is measured
      AT the reference mass flux; below that flux it is optimistic, and ``flux_ratio`` reports
      how far off the reference the configuration is running so the reader can see it.
    * **caloric** -- the fluid warms as it crosses the die, and the mean driving temperature sits
      half a fluid rise above inlet. Set by the flow, which is set by ``dT_fluid_K``.

    Pump power is ``dp * Q / eta``. Microchannel flow is deeply laminar (Re is a few tens at
    15-33 um), so the pressure drop is taken proportional to flow and anchored on the reference
    -- not a turbulent correlation, which would badly over-predict it.

    **This does not model the manifold, the plenum or the fluid-delivery pressure drop**, only
    the channels. A real assembly adds both, so the pump power here is a floor.
    """

    parasitic_known = True
    calibrated = True          # anchored on a measured point, not an invented one

    def __init__(self, die_area_mm2, heat_W, dT_fluid_K=10.0, inlet_C=30.0,
                 mover_efficiency=None, ambient_K=None, label=None):
        from HotGauge.thermal.cooling_spec import DEFAULT_MOVER_EFFICIENCY
        self.die_area_mm2 = float(die_area_mm2)
        self.heat_W = float(heat_W)
        self.dT_fluid_K = float(dT_fluid_K)
        self.inlet_C = float(inlet_C)
        self.mover_efficiency = float(
            mover_efficiency if mover_efficiency is not None
            else DEFAULT_MOVER_EFFICIENCY['water'])
        if self.dT_fluid_K <= 0:
            raise ValueError('dT_fluid_K must be > 0')
        if self.heat_W <= 0:
            raise ValueError('heat_W must be > 0')
        super().__init__(ambient_K=(ambient_K if ambient_K is not None
                                    else self.inlet_C + 273.15),
                         label=label or 'MicrochannelSink')

    # -- flow ---------------------------------------------------------------------------
    @property
    def flow_m3s(self):
        """Set by the caloric requirement: Q = P / (rho cp dT_fluid)."""
        from HotGauge.thermal.cooling_spec import FLUIDS
        p = FLUIDS['water']
        return self.heat_W / (p['rho'] * p['cp'] * self.dT_fluid_K)

    @property
    def mass_flux_kg_m2s(self):
        """Channel mass flux, for comparison with the reference.

        Referred to the DIE footprint rather than the channel cross-section, because the channel
        count is not a parameter here -- the model is anchored on area-specific performance. It
        is therefore a scaled comparison, not the paper's G, and is used only as a ratio.
        """
        from HotGauge.thermal.cooling_spec import FLUIDS
        p = FLUIDS['water']
        return p['rho'] * self.flow_m3s / (self.die_area_mm2 * 1e-6)

    @property
    def flux_ratio(self):
        """This configuration's mass flux over the reference rig's, both die-referred.

        A practical cold plate runs a 5-15 K fluid rise; the rig runs ~2 K, so this comes out
        well below 1. That does NOT make r_conv optimistic -- see r_conv_K_per_W -- but it does
        mean the pressure drop and pump power are far below the rig's, which is why they are
        scaled by this ratio rather than taken at the reference.
        """
        return self.mass_flux_kg_m2s / MICROCHANNEL_REF_FLUX_DIE

    # -- resistance ---------------------------------------------------------------------
    @property
    def r_conv_K_per_W(self):
        """Area-specific convective resistance, held INDEPENDENT of flow -- deliberately.

        Microchannel flow at 15-33 um is deeply laminar (Re of order tens), and for
        thermally-developed laminar flow the Nusselt number is a constant of the channel
        geometry, so ``h = Nu k / D_h`` does not depend on flow rate at all. Only the caloric
        term does. The paper's "diminishing returns at high mass flux" is the entry-length
        effect on top of that, not a flow dependence of the developed value.

        Cross-check on the anchor: for the 33 x 470 um channel D_h = 61.7 um, and Nu ~ 5.5 for a
        high-aspect-ratio channel heated on three sides gives h ~ 5.5e4 W/(m^2 K) on the wetted
        area. The wetted area is ~16x the footprint, so footprint-referred that is ~5e5, i.e.
        R'' ~ 2e-6 K m^2/W against the measured 6.8e-6 -- same order, with the measurement the
        more conservative. The measured value is what is used.
        """
        return MICROCHANNEL_R_AREA / (self.die_area_mm2 * 1e-6)

    @property
    def r_caloric_K_per_W(self):
        """Half the fluid rise, as a resistance: the mean driving temperature."""
        return 0.5 * self.dT_fluid_K / self.heat_W

    @property
    def r_th_K_per_W(self):
        """Whole-cooler resistance, die surface to fluid inlet."""
        return self.r_conv_K_per_W + self.r_caloric_K_per_W

    def htc_si(self):
        return 1.0 / (self.r_th_K_per_W * self.die_area_mm2 * 1e-6)

    # -- pump ---------------------------------------------------------------------------
    @property
    def pressure_drop_Pa(self):
        """Laminar, anchored on the reference: dp scales with flow."""
        return MICROCHANNEL_REF['dp_Pa'] * max(self.flux_ratio, 0.0)

    def parasitic_power_W(self):
        """Pump wall-plug power: dp * Q / eta. Channels only -- a floor, not the assembly."""
        return self.pressure_drop_Pa * self.flow_m3s / self.mover_efficiency

    def describe(self):
        return ('{}: R_th={:.4f} K/W ({:.4f} conv + {:.4f} caloric) over {:.0f} mm^2, '
                'flow {:.4g} m^3/s, dp {:.1f} kPa, pump {:.2f} W, inlet {:.1f} C, '
                'mass-flux {:.2f}x reference'
                .format(self.label, self.r_th_K_per_W, self.r_conv_K_per_W,
                        self.r_caloric_K_per_W, self.die_area_mm2, self.flow_m3s,
                        self.pressure_drop_Pa / 1e3, self.parasitic_power_W(),
                        self.inlet_C, self.flux_ratio))
