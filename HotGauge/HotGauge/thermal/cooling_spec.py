"""Cooling as a specification: geometry in, thermal resistance AND wall-plug power out.

Why this exists
---------------
The sink models this replaces return a thermal resistance and nothing else, and worse, they return
the **same** resistance whatever the die is: ``BaffledFinSink`` gives 0.0764 K/W for a 101 mm^2 CPU
die and 0.0764 K/W for an 826 mm^2 accelerator. That single missing area term invalidated every
accelerator temperature this project produced -- an 826 mm^2 part was being cooled by a heatsink
sized for a CPU, and duly ran away at less than half the density the CPU survives.

The liquid path was worse: ``--r-th`` supplies a resistance with **no power cost at all**, so a
liquid point could not honestly be used as the comparison arm for anything.

What a specification has to provide
-----------------------------------
Both halves of the trade, from the same geometry, so they cannot drift apart:

1. **Thermal resistance**, derived from the actual heat-transfer surface and the actual channel
   flow -- and therefore scaling with die area and with the sink built for it.
2. **Wall-plug power**, as a function of flow rate and inlet temperature -- mover (fan or pump)
   plus whatever chiller work is needed to hold an inlet below ambient.

With both, a sweep can ask the question that actually matters: *what flow rate and inlet
temperature meet this thermal target, and what does that cost at the wall?* Neither of the models
this replaces can answer it, which is why microrefrigeration has only ever been priced here against
a fan.

Provenance of the physics
-------------------------
The correlations follow the Maxwell Labs photonic-cooling analysis
(``docs/photonic_cooling/``), whose CFD-validated form for the temperature response --
``T_max = T_in + R_core(v) P_core + R_FU(v) P_FU`` -- is the same two-resistance structure this
project measures independently as alpha/beta, including the saturation of both resistances at high
velocity that we call the constriction floor. Two routes to one structure is the reason to trust it.

Specifically:

* convection coefficient from Nusselt/Reynolds on the channel (Dittus-Boelter turbulent, 3.66
  laminar), so ``R_conv = 1 / (h * A_wet)`` scales with the **built** surface area;
* conduction through die and base, ``R_cond = t / (k * A_die)``, scaling with **die** area;
* fan power ``P = dp * Vdot / eta``, which with ``h ~ v^0.8`` gives the familiar ``P ~ v^3``;
* pump power identically, ``P = Vdot * dp / eta``, cubic in flow;
* chiller COP as a Carnot fraction, ``COP = gamma * T_in / (T_amb - T_in)`` with gamma ~ 0.4.

What is NOT claimed
-------------------
These are **engineering correlations, not measurements**. Where this project has measured data --
the HS483 fit, the SimScale alpha/beta digitisation -- that data remains the better source inside
its calibrated range, and ``calibrated`` is False on everything here. The value of the analytic
form is the three things measurement cannot give us: scaling to a die size nothing was measured at,
extrapolation beyond the measured flow range, and a liquid loop at all.

One correction against the source. Its wetted-area expression sets fin spacing and thickness both
to ``L / N_fins``, so ``N * (s + t) = 2L`` -- the fins occupy twice the base they sit on. A real
array satisfies ``N * (s + t) = W``. This module solves the pitch from the base width instead, so
the geometry closes; expect roughly half the wetted area, and correspondingly higher (more
pessimistic) convective resistance, than the source model reports.
"""

import math
import logging

LOGGER = logging.getLogger(__name__)

#: Fluid properties. Air at ~50 C, water at ~30 C -- the ranges these loops actually run in.
FLUIDS = {
    'air':   {'k': 0.0283, 'rho': 1.093, 'mu': 1.96e-5, 'cp': 1005.0, 'Pr': 0.707},
    'water': {'k': 0.615,  'rho': 996.0, 'mu': 7.98e-4, 'cp': 4180.0, 'Pr': 5.42},
}

#: Mover efficiency (fan or pump), wall-plug to fluid work. 0.3-0.6 is the usual band.
DEFAULT_MOVER_EFFICIENCY = {'air': 0.45, 'water': 0.60}

#: Fraction of Carnot COP a real chiller achieves.
DEFAULT_CHILLER_GAMMA = 0.4

#: Thermal conductivities [W/m-K].
K_SILICON = 148.0
K_COPPER = 398.0

#: How much bigger than the die the sink base is, per side. A heatsink base always overhangs the
#: die -- that overhang is what spreads the heat into the fins -- and this is the single most
#: consequential geometry default here.
#:
#: **Calibrated, not guessed.** Solving for the value that reproduces the SimScale convective
#: resistance on that study's own 22x22 mm die gives 1.71-1.94 across the turbulent range
#: (60, 88, 150, 200 CFM), with a single outlier at 110 CFM where the correlation crosses the
#: laminar/turbulent transition. 1.85 is the middle of that band and puts a 41 mm base on a
#: 484 mm^2 die, which is a heatsink somebody would actually build. An earlier invented default of
#: 3.0 made every sink ~60% too large in linear extent.
DEFAULT_BASE_SPREAD = 1.85

#: Base overhang by COOLER CLASS, because 1.85 is not a universal constant -- it is what the
#: SimScale CFD's own small sink happened to be, and real coolers are far larger relative to their
#: die. Validated against published parts, the spread that reproduces them differs by nearly an
#: order of magnitude:
#:
#: * ``cfd_reference`` 1.85 -- the 22x22 mm CFD sink base_spread was calibrated on. Use it only to
#:   reproduce that study.
#: * ``datacenter_module`` 3.0 -- an SXM-class GPU module: ~86 mm of heatsink over a 28.7 mm die
#:   side. This is what reproduces the published H100 air point once the package resistance is
#:   accounted for, at a plausible 14 m/s and ~193 W of fan -- which matches the study's own
#:   air-versus-liquid node difference of ~146 W per GPU.
#: * ``desktop_tower`` 14.0 -- a 120 mm tower cooler over an ~8.4 mm CCD side. At 1.85 the model
#:   demanded 343 m/s to reach the published Ryzen resistance, which the velocity check caught.
#: * ``desktop_stock`` 7.0 -- a 92 mm stock cooler on the same die.
#:
#: Sizing a cooler from die area alone is the mistake this replaces; the cooler class is an input.
COOLER_CLASSES = {
    'cfd_reference': 1.85,
    'datacenter_module': 3.0,
    'desktop_stock': 7.0,
    'desktop_tower': 14.0,
}


class CoolingSpec(object):
    """A cooling configuration, priced.

    Construct from die footprint and the geometry of the sink built for it; query for thermal
    resistance and wall-plug power at any (flow rate, inlet temperature).

    ``calibrated`` is False: these are engineering correlations. Inside the range where this
    project has measured data, prefer the measured sink models.
    """

    def __init__(self, fluid, die_area_mm2, flow_m3s, inlet_C,
                 ambient_C=35.0, base_spread=DEFAULT_BASE_SPREAD,
                 fin_height_mm=None, fin_thickness_mm=0.5, fin_gap_mm=1.5,
                 base_thickness_mm=3.0, die_thickness_mm=0.5,
                 mover_efficiency=None, chiller_gamma=DEFAULT_CHILLER_GAMMA,
                 k_base=K_COPPER, k_die=K_SILICON, mover_power_model=None):
        if fluid not in FLUIDS:
            raise ValueError('fluid must be one of {}, got {!r}'.format(sorted(FLUIDS), fluid))
        if die_area_mm2 <= 0 or flow_m3s <= 0:
            raise ValueError('die_area_mm2 and flow_m3s must be > 0')
        self.fluid = fluid
        self.props = dict(FLUIDS[fluid])
        self.die_area_mm2 = float(die_area_mm2)
        self.die_area_m2 = self.die_area_mm2 / 1e6
        self.flow_m3s = float(flow_m3s)
        self.inlet_C = float(inlet_C)
        self.ambient_C = float(ambient_C)
        self.chiller_gamma = float(chiller_gamma)
        self.mover_efficiency = float(
            mover_efficiency if mover_efficiency is not None
            else DEFAULT_MOVER_EFFICIENCY[fluid])

        # --- geometry, scaled to the die ------------------------------------------------
        # The base is a square overhanging the die by `base_spread` in linear extent. Everything
        # downstream keys off this, which is how the whole spec acquires its area dependence.
        die_side_mm = math.sqrt(self.die_area_mm2)
        self.base_side_mm = die_side_mm * float(base_spread)
        self.base_area_mm2 = self.base_side_mm ** 2
        self.base_thickness_mm = float(base_thickness_mm)
        self.die_thickness_mm = float(die_thickness_mm)

        # Fin height defaults to the base side for air (a tall stack) and a quarter of it for a
        # liquid cold plate, whose channels are shallow by comparison.
        if fin_height_mm is None:
            fin_height_mm = self.base_side_mm * (1.0 if fluid == 'air' else 0.25)
        self.fin_height_mm = float(fin_height_mm)
        self.fin_thickness_mm = float(fin_thickness_mm)
        self.fin_gap_mm = float(fin_gap_mm)

        # Solve the fin COUNT from the base width, so the array actually fits the base it sits on.
        pitch_mm = self.fin_thickness_mm + self.fin_gap_mm
        self.n_fins = max(2, int(self.base_side_mm / pitch_mm))
        self.n_channels = self.n_fins - 1
        if self.n_channels < 1:
            raise ValueError('fin pitch {:.2f} mm does not fit a {:.2f} mm base'
                             .format(pitch_mm, self.base_side_mm))

        # Wetted area: both faces of every fin, plus the exposed base between them.
        fin_faces_mm2 = 2.0 * self.n_fins * self.fin_height_mm * self.base_side_mm
        exposed_base_mm2 = self.n_channels * self.fin_gap_mm * self.base_side_mm
        self.wetted_area_mm2 = fin_faces_mm2 + exposed_base_mm2
        self.wetted_area_m2 = self.wetted_area_mm2 / 1e6

        self.k_base = float(k_base)
        self.k_die = float(k_die)
        # Optional measured mover-power curve, ``f(flow_m3s) -> W``. Strongly preferred for air:
        # see the note on ``mover_power_W``.
        self.mover_power_model = mover_power_model
        self.calibrated = False

    # -- flow ---------------------------------------------------------------------------
    @property
    def channel_area_m2(self):
        """Total open cross-section the fluid passes through."""
        return self.n_channels * (self.fin_gap_mm / 1e3) * (self.fin_height_mm / 1e3)

    @property
    def velocity_m_s(self):
        return self.flow_m3s / self.channel_area_m2

    @property
    def hydraulic_diameter_m(self):
        g, h = self.fin_gap_mm / 1e3, self.fin_height_mm / 1e3
        return 2.0 * g * h / (g + h)

    @property
    def reynolds(self):
        p = self.props
        return p['rho'] * self.velocity_m_s * self.hydraulic_diameter_m / p['mu']

    @property
    def nusselt(self):
        """Dittus-Boelter above the transition, fully-developed laminar below."""
        Re = self.reynolds
        if Re < 2300.0:
            return 3.66
        n = 0.4 if self.fluid == 'water' else (1.0 / 3.0)
        return 0.023 * (Re ** 0.8) * (self.props['Pr'] ** n)

    @property
    def h_conv(self):
        """Convective coefficient [W/m^2-K]. NOT clipped: a nonsense h means nonsense geometry,
        and clamping it into range is how a geometry error becomes a plausible temperature."""
        return self.nusselt * self.props['k'] / self.hydraulic_diameter_m

    # -- resistance ---------------------------------------------------------------------
    @property
    def r_cond_K_per_W(self):
        """Conduction through the die and the sink base. Scales with DIE area."""
        r_die = (self.die_thickness_mm / 1e3) / (self.k_die * self.die_area_m2)
        r_base = (self.base_thickness_mm / 1e3) / (self.k_base * self.die_area_m2)
        return r_die + r_base

    @property
    def r_conv_K_per_W(self):
        """Convection off the wetted surface. Scales with the area actually BUILT."""
        return 1.0 / (self.h_conv * self.wetted_area_m2)

    @property
    def r_caloric_K_per_W(self):
        """The coolant heating up as it passes: ``1 / (rho * cp * Vdot)``.

        Easy to omit and then wrong in a way that hides. Without it, a laminar channel has a
        flow-INDEPENDENT ``h`` (Nu is fixed at 3.66), so the model says halving the flow costs
        nothing and an inverse solve happily drives the flow to zero. In reality the fluid simply
        leaves hotter, and below some flow the loop cannot carry the heat away at all whatever
        the surface does.

        This is the term that makes flow rate matter at the low end, and it is the reason a
        700 W part needs real flow rather than a large surface.
        """
        p = self.props
        return 1.0 / (p['rho'] * p['cp'] * self.flow_m3s)

    @property
    def coolant_rise_K(self):
        """How much hotter the fluid leaves than it arrived, per watt removed."""
        return self.r_caloric_K_per_W

    @property
    def r_th_K_per_W(self):
        # Caloric first: the fluid's own temperature rise is in series with everything the
        # surface does, and it is what sets the floor at low flow.
        return self.r_cond_K_per_W + self.r_conv_K_per_W + self.r_caloric_K_per_W

    def htc_si(self):
        """Heat transfer coefficient over the DIE footprint, which is what 3D-ICE wants: it
        applies a coefficient over the chip area, not over the fin area."""
        return 1.0 / (self.r_th_K_per_W * self.die_area_m2)

    # -- pressure and wall-plug power ---------------------------------------------------
    @property
    def friction_factor(self):
        Re = self.reynolds
        return 64.0 / Re if Re < 2300.0 else 0.316 * Re ** -0.25

    @property
    def pressure_drop_Pa(self):
        """Darcy-Weisbach across the fin stack. Channel length is the base side."""
        L = self.base_side_mm / 1e3
        return (self.friction_factor * (L / self.hydraulic_diameter_m)
                * self.props['rho'] * self.velocity_m_s ** 2 / 2.0)

    @property
    def analytic_mover_power_W(self):
        """Fin-stack friction only: ``P = dp * Vdot / eta``.

        **It omits the mover's fixed overhead**, and that is where it goes wrong. Validated
        against the measured SimScale fan curve on that study's own die and a calibrated sink:

            20 CFM   0.5 W vs  21.9 W   0.02x   <- overhead dominates; analytic is useless here
            60 CFM  11.5 W vs  29.6 W   0.39x
            88 CFM  33.0 W vs  35.0 W   0.94x   <- friction dominates; analytic is close
           133 CFM 102.6 W vs 100.0 W   1.03x
           200 CFM 315.2 W vs 215.0 W   1.47x   <- and eventually over-predicts

        So it is not a uniform under-estimate: the measured curve has an ~18 W intercept at zero
        flow that no friction term can produce, and friction only catches up once the flow is high.
        Use it above roughly 80 CFM-equivalent, or where no measured curve exists at all; below
        that, supply ``mover_power_model``.
        """
        return self.pressure_drop_Pa * self.flow_m3s / self.mover_efficiency

    @property
    def mover_power_W(self):
        """Wall-plug power for the fan or pump.

        Uses ``mover_power_model`` when one is supplied and the analytic term otherwise. For AIR,
        supply the measured curve: the real one is *discontinuous* -- three different fans with
        handovers at 88 and 133 CFM -- and no continuous analytic form can reproduce that. The
        discontinuity is not noise; it is why the SimScale study found best system COP at NONZERO
        laser power, since cooling the hotspot optically lets the system stay on the cheaper fan
        instead of jumping to the next one.
        """
        if self.mover_power_model is not None:
            return float(self.mover_power_model(self.flow_m3s))
        return self.analytic_mover_power_W

    @property
    def chiller_cop(self):
        """Carnot fraction. Infinite when the inlet is at or above ambient -- that is free
        cooling, and it costs nothing beyond the mover."""
        lift = self.ambient_C - self.inlet_C
        if lift <= 0:
            return float('inf')
        T_in_K = self.inlet_C + 273.15
        return self.chiller_gamma * T_in_K / lift

    def chiller_power_W(self, heat_W):
        """Work to reject ``heat_W`` at an inlet below ambient."""
        cop = self.chiller_cop
        if cop == float('inf'):
            return 0.0
        return float(heat_W) / cop

    def wall_plug_W(self, heat_W):
        """Total electrical power this configuration draws to remove ``heat_W``.

        The chiller must reject the chip heat *and* the mover's own dissipation, which is what
        makes high flow doubly expensive: cubic to move, then rejected again.
        """
        mover = self.mover_power_W
        chiller = self.chiller_power_W(float(heat_W) + mover)
        return mover + chiller

    def system_cop(self, heat_W):
        total = self.wall_plug_W(heat_W)
        return float(heat_W) / total if total > 0 else float('inf')

    def report(self, heat_W):
        """Everything a sweep needs from one operating point."""
        return {
            'fluid': self.fluid, 'calibrated': False,
            'die_area_mm2': self.die_area_mm2, 'base_side_mm': self.base_side_mm,
            'wetted_area_mm2': self.wetted_area_mm2, 'n_fins': self.n_fins,
            'flow_m3s': self.flow_m3s, 'velocity_m_s': self.velocity_m_s,
            'reynolds': self.reynolds, 'nusselt': self.nusselt, 'h_conv': self.h_conv,
            'inlet_C': self.inlet_C, 'ambient_C': self.ambient_C,
            'r_cond_K_per_W': self.r_cond_K_per_W, 'r_conv_K_per_W': self.r_conv_K_per_W,
            'r_caloric_K_per_W': self.r_caloric_K_per_W,
            'coolant_rise_K': float(heat_W) * self.r_caloric_K_per_W,
            'r_th_K_per_W': self.r_th_K_per_W, 'htc_si': self.htc_si(),
            'pressure_drop_Pa': self.pressure_drop_Pa,
            'mover_power_W': self.mover_power_W,
            'analytic_mover_power_W': self.analytic_mover_power_W,
            'mover_power_source': ('measured curve' if self.mover_power_model is not None
                                   else 'analytic (fin friction only -- a LOWER BOUND)'),
            'chiller_cop': self.chiller_cop,
            'chiller_power_W': self.chiller_power_W(float(heat_W) + self.mover_power_W),
            'wall_plug_W': self.wall_plug_W(heat_W),
            'system_cop': self.system_cop(heat_W),
            'heat_W': float(heat_W),
            'die_rise_K': float(heat_W) * self.r_th_K_per_W,
            'peak_estimate_C': self.inlet_C + float(heat_W) * self.r_th_K_per_W,
        }

    def __repr__(self):
        return ('CoolingSpec({} over {:.0f} mm^2 die: base {:.1f} mm, {} fins, '
                'R_th {:.4f} K/W, {:.4g} m^3/s, inlet {:.1f} C, mover {:.1f} W UNCALIBRATED)'
                .format(self.fluid, self.die_area_mm2, self.base_side_mm, self.n_fins,
                        self.r_th_K_per_W, self.flow_m3s, self.inlet_C, self.mover_power_W))


#: Plausible face velocities [m/s]. Air above ~25 m/s through a fin stack is not a computer
#: cooler, it is a wind tunnel; water above ~5 m/s erodes channels. Exceeding these does not mean
#: the arithmetic is wrong, it means the CONFIGURATION is not one anybody would build -- so it is
#: reported rather than clipped, and the caller decides.
VELOCITY_SANITY = {'air': (0.5, 25.0), 'water': (0.05, 5.0)}


def velocity_is_plausible(spec):
    """``(ok, message)`` for the face velocity this configuration implies.

    Worth checking before quoting any number from a spec. 88 CFM forced through a heatsink sized
    for a 101 mm^2 die needs 66 m/s, which is why the same flow rate cannot simply be reused
    across die sizes -- the flow has to be solved for, not assumed.
    """
    lo, hi = VELOCITY_SANITY[spec.fluid]
    v = spec.velocity_m_s
    if v < lo:
        return False, ('face velocity {:.2f} m/s is below the plausible {} range ({:.2f}-{:.1f}); '
                       'the flow is too low for this geometry'.format(v, spec.fluid, lo, hi))
    if v > hi:
        return False, ('face velocity {:.1f} m/s exceeds the plausible {} range ({:.2f}-{:.1f}); '
                       'this flow through this geometry is not a buildable configuration'
                       .format(v, spec.fluid, lo, hi))
    return True, 'face velocity {:.2f} m/s'.format(v)


def solve_flow_for_r_th(fluid, die_area_mm2, target_r_th, inlet_C=35.0, ambient_C=35.0,
                        flow_lo=1e-5, flow_hi=1.0, tol=1e-4, max_iter=80, **kw):
    """Least flow rate that reaches ``target_r_th`` for this die and geometry.

    This is the direction a study actually needs: not "what does 88 CFM give me" but "what flow
    meets my thermal target, and what does it cost". Thermal resistance falls monotonically with
    flow, so bisection is exact.

    Returns a ``CoolingSpec``, or None when even ``flow_hi`` cannot reach the target -- which is a
    real answer, and the one the constriction floor produces.
    """
    def spec_at(f):
        return CoolingSpec(fluid, die_area_mm2, flow_m3s=f, inlet_C=inlet_C,
                           ambient_C=ambient_C, **kw)

    if spec_at(flow_hi).r_th_K_per_W > target_r_th:
        return None
    lo, hi = flow_lo, flow_hi
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if spec_at(mid).r_th_K_per_W > target_r_th:
            lo = mid
        else:
            hi = mid
        if (hi - lo) / max(hi, 1e-12) < tol:
            break
    return spec_at(hi)


def solve_flow_for_peak(fluid, die_area_mm2, heat_W, target_peak_C, inlet_C=35.0,
                        ambient_C=35.0, **kw):
    """Least flow that holds ``target_peak_C`` given ``heat_W``, via the resistance it implies.

    Uses the lumped estimate ``T = T_inlet + Q * R_th``; a real answer still needs the coupled
    3D-ICE solve, because this has no notion of a hotspot. It is the right way to CHOOSE the
    operating point to hand to that solve.
    """
    rise = float(target_peak_C) - float(inlet_C)
    if rise <= 0:
        raise ValueError('target_peak_C ({:.1f}) must exceed inlet_C ({:.1f})'
                         .format(target_peak_C, inlet_C))
    return solve_flow_for_r_th(fluid, die_area_mm2, rise / float(heat_W),
                               inlet_C=inlet_C, ambient_C=ambient_C, **kw)


def measured_air_mover_power(flow_m3s):
    """Measured fan power [W] at this airflow, from the SimScale piecewise fan curve.

    Pass as ``mover_power_model`` for any air configuration inside 0-200 CFM. Prefer it to the
    analytic term, which covers fin friction alone and under-predicts by 2-6x over that range.

    The curve is piecewise because it is three physical fans, each linear over the band where it
    is the best available choice, and the steps at the handovers are real -- there is no fan to buy
    between them.
    """
    from HotGauge.thermal.sink_models import simscale_fan_power
    return float(simscale_fan_power(float(flow_m3s) * 2118.88))


def air_spec(die_area_mm2, flow_m3s, inlet_C, ambient_C=35.0, **kw):
    """An air configuration wired to the measured fan curve by default.

    The convenience matters: forgetting ``mover_power_model`` silently under-prices air cooling
    several-fold, which would flatter every comparison against it -- including the one that
    matters, microrefrigeration against the alternative.
    """
    kw.setdefault('mover_power_model', measured_air_mover_power)
    return CoolingSpec('air', die_area_mm2, flow_m3s, inlet_C, ambient_C=ambient_C, **kw)


class CoolingSpecSink(object):
    """Adapter presenting a :class:`CoolingSpec` as a stack sink for 3D-ICE.

    Implements the ``SinkModel`` surface -- ``htc_si``, ``htc_3dice``, ``parasitic_power_W``,
    ``ambient_K`` -- so ``render_stack_with_sink`` and every study accept it unchanged.

    Two things it does that the sinks it replaces do not:

    * its resistance **scales with the die it is cooling**, which is the defect that invalidated
      every accelerator temperature;
    * ``parasitic_power_W`` includes the **chiller**, not just the mover, so an inlet held below
      ambient is charged for. That is what finally makes a liquid loop comparable with an air one
      rather than free.

    3D-ICE applies a coefficient over the chip footprint and computes the conduction itself, so
    ``htc_si`` deliberately presents the **convective and caloric** resistance only. Including
    ``R_cond`` here would double-count the die and base that the stack already models.
    """

    parasitic_known = True
    calibrated = False

    def __init__(self, spec, heat_W, label=None, r_package_K_per_W=0.0):
        self.spec = spec
        self.heat_W = float(heat_W)
        self.ambient_K = spec.inlet_C + 273.15
        # Resistance the STACK adds above the silicon -- solder TIM, spreader, grease, sink layer.
        # It is recorded here only so a caller can see what was assumed; the sink still presents
        # its own resistance, because 3D-ICE adds the package itself. What this exists for is the
        # inverse problem: given a published junction-to-ambient figure, the external cooling has
        # to supply that MINUS this. See ``external_r_for_total`` and measure_package_resistance.
        self.r_package_K_per_W = float(r_package_K_per_W)
        self.label = label or 'CoolingSpec[{}]'.format(spec.fluid)

    @property
    def r_th_K_per_W(self):
        """Resistance 3D-ICE is being asked to represent: everything above the silicon."""
        return self.spec.r_conv_K_per_W + self.spec.r_caloric_K_per_W

    def htc_si(self):
        return 1.0 / (self.r_th_K_per_W * self.spec.die_area_m2)

    def htc_3dice(self):
        from HotGauge.thermal.sink_models import htc_si_to_3dice
        return htc_si_to_3dice(self.htc_si())

    @property
    def parasitic_power_W(self):
        """Mover plus chiller. A sink whose inlet is below ambient is not free."""
        return self.spec.wall_plug_W(self.heat_W)

    def describe(self):
        ok, msg = velocity_is_plausible(self.spec)
        return ('{}: h={:.4g} W/(m^2 K) over {:.0f} mm^2, T_in={:.1f} C, '
                'P_cool={:.1f} W ({:.1f} mover + {:.1f} chiller), {}{}'
                .format(self.label, self.htc_si(), self.spec.die_area_mm2, self.spec.inlet_C,
                        self.parasitic_power_W, self.spec.mover_power_W,
                        self.parasitic_power_W - self.spec.mover_power_W,
                        msg, '' if ok else '  [IMPLAUSIBLE CONFIGURATION]'))

    def __repr__(self):
        return '<{}>'.format(self.describe())


def measure_package_resistance(stack_file, flp_file, tech_node, die_area_mm2, sink_r_th,
                               heat_W, ambient_K, powers, session_cache=None, run_dir=None):
    """Thermal resistance the STACK adds above the silicon, measured by one solve [K/W].

    Why this is needed. ``CoolingSpecSink`` computes the resistance from the die surface out to
    the coolant and hands 3D-ICE the equivalent coefficient. But 3D-ICE then puts the *package*
    in series above the die -- solder TIM, copper heat spreader, grease, sink layer -- and that
    resistance is nowhere in the sink model. So the total the solve produces is larger than the
    sink believes, and a configuration built to hit a published junction-to-ambient resistance
    overshoots it.

    Measured on the GA100 die at 470 W: the sink supplied 0.0942 K/W, the solve returned a
    **mean** of 84.9 C against a 65.8 C lumped prediction, and the difference is the package --
    about 0.041 K/W. A 19 K gap in the MEAN cannot be a hotspot, which is what identified it.

    Published figures like ``H100_AIR``'s 0.107 K/W are junction-to-ambient and already include
    the package. To reproduce one, the external cooling must supply the REMAINDER:
    ``R_external = R_published - R_package``.

    Returns ``(r_package_mean, r_package_peak, detail)``. The peak figure additionally carries
    lateral spreading to the hottest block and is not a pure series term; use the mean when
    subtracting.
    """
    import numpy as np
    from HotGauge.power import BasicPowerTrace
    from HotGauge.thermal import ICEThermalSolver

    solver = ICEThermalSolver(stack_file, flp_file, tech_node,
                              run_base_dir=run_dir, initial_temp=ambient_K, num_cores=1,
                              single_thread=True, mode='steady', session_cache=session_cache,
                              already_dice_named=True)
    temps = solver(BasicPowerTrace({u: np.array([v]) for u, v in powers.items()}, 1.0))
    vals = [float(np.ravel(v)[-1]) for v in temps.values() if float(np.ravel(v)[-1]) > 273.15]
    if not vals:
        raise ValueError('the calibration solve returned no usable temperatures')
    mean_K, peak_K = sum(vals) / len(vals), max(vals)
    total_mean = (mean_K - ambient_K) / float(heat_W)
    total_peak = (peak_K - ambient_K) / float(heat_W)
    detail = {'mean_C': mean_K - 273.15, 'peak_C': peak_K - 273.15,
              'total_r_mean': total_mean, 'total_r_peak': total_peak,
              'sink_r_th': float(sink_r_th), 'die_area_mm2': float(die_area_mm2),
              'heat_W': float(heat_W)}
    return total_mean - float(sink_r_th), total_peak - float(sink_r_th), detail


def external_r_for_total(total_r_K_per_W, r_package_K_per_W):
    """What the external cooling must supply to hit a published junction-to-ambient figure.

    Published resistances are junction-to-ambient: they already contain the package. Handing one
    straight to a sink model overshoots, because 3D-ICE then adds the package again. On the GA100
    die that error is 0.041 K/W of series package -- 0.057 including spreading to the peak --
    against a 0.107 K/W published total, so more than half the budget.

    Raises when the package alone exceeds the target, which is a real answer: no external cooling,
    however good, reaches that junction temperature through that package.
    """
    ext = float(total_r_K_per_W) - float(r_package_K_per_W)
    if ext <= 0:
        raise ValueError(
            'the package alone is {:.4f} K/W against a {:.4f} K/W target -- no external cooling '
            'reaches this junction temperature through this package'
            .format(r_package_K_per_W, total_r_K_per_W))
    return ext


# ---------------------------------------------------------------------------
# Spreading resistance: why a small die is not simply a scaled-down large one
# ---------------------------------------------------------------------------
#: Contact-base overhang implied by the SimScale study's own CAD, as a linear ratio to the die
#: side. Read off ``docs/SimScale/Scripts``, which built the geometry the CFD actually meshed:
#:
#: * ``Chip_core_fin_larger_box.py`` / ``Chip_core_fin_groups.py`` -- 20 mm chip, 40 x 60 mm base
#:   => 2400 mm^2, equivalent side 49.0 mm, ratio **2.45**
#: * ``Chip_fin_box.py`` -- 10 mm chip, 25 x 50 mm base => 1250 mm^2, side 35.4 mm, ratio **3.54**
#:
#: The two disagree because the base is close to a FIXED physical size across both models -- a
#: socket-sized cold plate -- while the die is not. That is how real coolers are built and it is
#: the whole reason a small die does better than 1/area would predict. Quoting a single ratio
#: reintroduces the bug it is meant to fix: if the base scales with the die, every resistance is
#: proportional to 1/area again and the model still cannot tell a 91 mm^2 part from an 826 mm^2
#: one. Prefer :func:`base_area_from_footprint`; the ratios are recorded for provenance.
SIMSCALE_BASE_GEOMETRY = {
    'chip_core_fin_larger_box': {'die_side_mm': 20.0, 'base_mm': (40.0, 60.0),
                                 'fin_base_mm': (60.0, 100.0)},
    'chip_fin_box': {'die_side_mm': 10.0, 'base_mm': (25.0, 50.0),
                     'fin_base_mm': (40.0, 100.0)},
}

#: Contact-base footprint [mm^2] to assume when nothing better is known, taken as the midpoint of
#: the two SimScale bases (2400 and 1250 mm^2). Absolute, not a ratio -- see above.
DEFAULT_BASE_FOOTPRINT_MM2 = 1825.0


def base_area_from_footprint(die_area_mm2, footprint_mm2=DEFAULT_BASE_FOOTPRINT_MM2):
    """Contact-base area for a die, as a fixed footprint clamped to at least the die.

    A cold plate is sized by the socket, not by the die, so this does not scale with
    ``die_area_mm2`` -- that is the point. The clamp only stops a die larger than the plate from
    producing a base smaller than its own source, which would be geometrically impossible rather
    than merely pessimistic.
    """
    return max(float(footprint_mm2), float(die_area_mm2))


def spreading_resistance_K_per_W(die_area_mm2, base_area_mm2, base_thickness_mm,
                                 k_W_mK, h_base_W_m2K):
    """Source-to-ambient resistance of a die-sized source on a larger, cooled base [K/W].

    The Lee/Song/Moran/Yovanovich constriction-resistance correlation for a circular-equivalent
    source coaxial on a disc of finite thickness with a convective back face
    (*Constriction/Spreading Resistance Model for Electronics Packaging*, 1995). It returns the
    **total** resistance from the source into ambient: the spreading term plus the one-dimensional
    conduction and convection over the full base area.

    Why this rather than another stack layer
    ----------------------------------------
    3D-ICE gives every layer exactly the die footprint -- ``chip length``/``width`` come from the
    floorplan and there is no way to declare an overhang on the conventional ``top heat sink``
    (the grammar accepts only a heat transfer coefficient and a temperature; a real spreader
    exists only on the *pluggable* sink, which cannot be steady-solved). So a 2 mm slab of sink
    metal in the stack is a column of metal the width of the die, and the whole package budget
    comes out proportional to 1/area. Measured: 0.0402 K/W on 826 mm^2 and 0.3648 on 91 mm^2 --
    9.08x for 9.08x the area, the exact signature of no lateral relief. That is why the acceptance
    gate reproduces an 826 mm^2 accelerator and fails a 91 mm^2 CPU.

    Folding the base into the boundary resistance instead gets the area dependence right, because
    the spreading term depends on the *ratio* of die to base and not on die area alone. What it
    does not do is resolve lateral gradients inside the base -- this is a lumped term. The die's
    own silicon spreading is still solved by 3D-ICE, which is where the within-die peak comes
    from, so the approximation is in the package rather than in the answer being asked for.

    Accuracy
    --------
    Exact in the ``base == die`` limit, where it collapses to ``t/(kA) + 1/(hA)`` -- arithmetic,
    with no fitted constant able to hide. In the opposite corner (a vanishing source on a thick,
    weakly-cooled base) it tends to a dimensionless ``psi`` of ``1/sqrt(pi) = 0.564`` against the
    exact isoflux half-space value of ``8/(3 pi^1.5) = 0.479``, i.e. it runs ~18% conservative
    there. That corner is the correlation's worst case and is far from any real package, but the
    direction matters: this model errs toward *more* resistance, never less.

    Parameters are in mm, mm^2, W/(m K) and W/(m^2 K); the result is K/W.
    """
    die_area_mm2 = float(die_area_mm2)
    base_area_mm2 = float(base_area_mm2)
    if die_area_mm2 <= 0 or base_area_mm2 <= 0:
        raise ValueError('areas must be positive')
    if base_area_mm2 < die_area_mm2 - 1e-9:
        raise ValueError('base area {:.1f} mm^2 is smaller than the die it carries ({:.1f} mm^2)'
                         .format(base_area_mm2, die_area_mm2))
    if k_W_mK <= 0 or h_base_W_m2K <= 0:
        raise ValueError('conductivity and htc must be positive')

    a = math.sqrt(die_area_mm2 / math.pi) / 1000.0        # equivalent source radius [m]
    b = math.sqrt(base_area_mm2 / math.pi) / 1000.0       # equivalent base radius   [m]
    t = float(base_thickness_mm) / 1000.0
    k = float(k_W_mK)
    h = float(h_base_W_m2K)

    eps = a / b
    tau = t / b
    bi = h * b / k
    lam = math.pi + 1.0 / (math.sqrt(math.pi) * eps)
    # tanh saturates for a thick base; guard the ratio rather than letting it overflow.
    tl = math.tanh(lam * tau)
    phi = (tl + lam / bi) / (1.0 + (lam / bi) * tl)
    # Both terms carry the 1/sqrt(pi). Dropping it from the second one inflates the spreading
    # term by sqrt(pi) = 1.77 and is invisible in the eps -> 1 check, because that term vanishes
    # there. The half-space limit below is what catches it.
    psi = ((eps * tau) + (1.0 - eps) ** 1.5 * phi) / math.sqrt(math.pi)

    r_spread = psi / (math.sqrt(math.pi) * k * a)
    r_1d = 1.0 / (h * base_area_mm2 * 1e-6)
    return r_spread + r_1d


def staged_spreading_resistance_K_per_W(die_area_mm2, stages, r_external_K_per_W):
    """Source-to-ambient resistance through a chain of successively larger spreaders [K/W].

    Why one stage is not enough
    ---------------------------
    A real package spreads twice. The die feeds a lid a few centimetres across; the lid feeds a
    cold plate several times larger again. Charging the second one as a *slab over the lid's
    area* -- which is what a single-stage model does with everything above the base -- throws away
    its overhang entirely, and that is the larger of the two spreading opportunities.

    Measured consequence: single-stage put the Ryzen point's required external cooling at
    0.046 K/W against a typical tower's 0.10-0.15, i.e. still demanding a better cooler than
    exists. The missing stage is the cold plate's own overhang.

    Parameters
    ----------
    die_area_mm2 : the source.
    stages : list, **from the die outward**. Each is a dict with ``area_mm2``, ``thickness_mm``,
        ``k_W_mK`` and optionally ``contact_r_K_per_W`` -- the interface resistance sitting on top
        of that stage (grease, solder), charged over that stage's own area.
    r_external_K_per_W : the convective and caloric resistance out of the last stage.

    Computed from the outside in, because each stage's spreading depends on how easily heat leaves
    its far face, which is everything beyond it.
    """
    areas = [float(die_area_mm2)] + [float(s['area_mm2']) for s in stages]
    for i, a in enumerate(areas[:-1]):
        if areas[i + 1] < a - 1e-9:
            raise ValueError('stage {} ({:.1f} mm^2) is smaller than what feeds it ({:.1f} mm^2); '
                             'stages must be ordered from the die outward'
                             .format(i, areas[i + 1], a))
    r = float(r_external_K_per_W)
    if r <= 0:
        raise ValueError('external resistance must be positive')
    for i in range(len(stages) - 1, -1, -1):
        st = stages[i]
        contact = float(st.get('contact_r_K_per_W', 0.0))
        # spreading_resistance_K_per_W already adds 1/(h*A_base), so feeding it an h that encodes
        # everything downstream makes the return value the running total from this stage outward.
        h = 1.0 / ((r + contact) * float(st['area_mm2']) * 1e-6)
        r = spreading_resistance_K_per_W(areas[i], st['area_mm2'], st['thickness_mm'],
                                         st['k_W_mK'], h)
    return r
