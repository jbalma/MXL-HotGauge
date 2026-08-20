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
#: die -- that overhang is what spreads the heat into the fins. 3x linear (9x area) is typical for
#: a high-performance air cooler and is the single most consequential geometry default here.
DEFAULT_BASE_SPREAD = 3.0


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
                 k_base=K_COPPER, k_die=K_SILICON):
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
    def mover_power_W(self):
        """Fan or pump. ``P = dp * Vdot / eta`` -- and since ``dp ~ v^2`` at fixed geometry, this
        is the cubic-in-flow law both the air and liquid literature report."""
        return self.pressure_drop_Pa * self.flow_m3s / self.mover_efficiency

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
