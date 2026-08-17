"""Voltage/frequency from the IRDS 2024 roadmap, replacing the shipped V/F table.

Why this exists
---------------
``configuration.performance.VF_PAIRS`` is one alpha-power curve to 0.30% RMS -- it is
internally consistent -- but it is not a curve for any modern node. It asks **1.19 V for
4.6 GHz and 1.4 V for 5.0 GHz**, while IRDS 2024 More Moore (MM01 - LOGIC) puts a
high-performance logic node at **Vdd 0.6-0.7 V** reaching 3.9-5.2 GHz wireloaded. That is about
twice the supply voltage for the same clock, and since dynamic power goes as V^2*f it overstates
the power cost of clock by roughly 6.5x at 5 GHz.

The consequences were not academic. Every clock search that stopped at "5.0 GHz, voltage-limited"
was reporting the top of that table, not a property of silicon; and because the model overcharged
for voltage, the clock gain microrefrigeration was measured to deliver came out understated.

What this module does instead
-----------------------------
For each IRDS node it anchors the standard velocity-saturated delay law -- Chandrakasan, Bowhill
& Fox, *Design of High-Performance Microprocessor Circuits*, eq. (4.2),
``tau_d = beta*C_L*V/(V - Vt)^alpha`` -- on that node's own **(Vdd, Vt, frequency)** triple:

    f(V) = k * (V - Vt)^alpha / V,     k set so that f(Vdd) = f_ref

so the curve passes through the roadmap's operating point by construction and uses the
roadmap's threshold voltage rather than one fitted to the wrong data.

Every number in ``IRDS_NODES`` below was extracted programmatically from
``docs/chip_design_lit/roadmaps/IRDS/2024IRDS_MM_Tables.xlsx``, sheet ``MM01 - LOGIC``, not
transcribed by hand.

The two judgement calls, stated plainly
---------------------------------------
* **alpha** is not in the roadmap. IRDS gives one operating point per node, and one point cannot
  determine a slope. The book quotes ~1.4 as typical; modern short-channel devices sit lower.
  It is a parameter here, ``DEFAULT_ALPHA``, and ``alpha_sensitivity()`` exists so any result
  that leans on it can be checked rather than trusted.
* **Which frequency** to anchor on. ``'wireloaded'`` (default) is the roadmap's loaded-path
  figure and the closest thing it offers to an achievable core clock; ``'cpu'`` is its own CPU
  row, roughly 20% lower; ``'unloaded'`` is a ring-oscillator-style ceiling and is not a product
  clock. The choice is recorded in the model's ``repr`` because it moves every absolute number.

Maximum operating voltage
-------------------------
The other thing the old table got badly wrong was the ceiling. Parts do not run at twice their
nominal Vdd -- reliability limits overdrive to order 10%. ``v_max`` is ``vdd * (1 + overdrive)``
with ``overdrive`` defaulting to 0.10, so on the 2024 node the clock ceiling lands near 4 GHz
rather than the old table's 5 GHz.
"""

import math
import logging

LOGGER = logging.getLogger(__name__)

#: Velocity-saturation exponent in the alpha-power delay law. NOT from IRDS -- see the module
#: note. 1.4 is the textbook's "typical"; the previous fit to the shipped table gave 0.95.
DEFAULT_ALPHA = 1.4

#: Fractional overdrive allowed above nominal Vdd. Reliability, not performance, sets this.
DEFAULT_OVERDRIVE = 0.10

#: IRDS 2024 More Moore, sheet "MM01 - LOGIC", high-performance (HP) device rows.
#: vdd [V], vt [V] (Vt,sat at Ioff=10nA/um), vdsat [V], subthreshold slope [mV/dec],
#: frequencies [GHz], dynamic power at 1 GHz [mW].
IRDS_NODES = {
    2024: {'label': '"3nm" Enhanced', 'vdd': 0.70, 'vt': 0.1555631, 'vdsat': 0.0922,
           'ss_mV_dec': 82, 'f_unloaded': 7.231405, 'f_wireloaded': 3.854563,
           'f_cpu': 3.100000, 'dyn_mW_per_GHz': 2.672713},
    2025: {'label': '"2nm"', 'vdd': 0.65, 'vt': 0.1645370, 'vdsat': 0.1008,
           'ss_mV_dec': 72, 'f_unloaded': 7.891687, 'f_wireloaded': 4.220736,
           'f_cpu': 3.394492, 'dyn_mW_per_GHz': 2.100465},
    2027: {'label': '"1.4nm"', 'vdd': 0.60, 'vt': 0.1635054, 'vdsat': 0.1080,
           'ss_mV_dec': 70, 'f_unloaded': 8.353392, 'f_wireloaded': 4.359346,
           'f_cpu': 3.505967, 'dyn_mW_per_GHz': 1.729211},
    2029: {'label': '"A10 eq"', 'vdd': 0.60, 'vt': 0.1523264, 'vdsat': 0.1080,
           'ss_mV_dec': 70, 'f_unloaded': 6.392204, 'f_wireloaded': 3.661315,
           'f_cpu': 2.944582, 'dyn_mW_per_GHz': 1.610121},
    2031: {'label': '"A7 eq"', 'vdd': 0.60, 'vt': 0.1637964, 'vdsat': 0.1440,
           'ss_mV_dec': 70, 'f_unloaded': 9.461525, 'f_wireloaded': 5.189313,
           'f_cpu': 4.173462, 'dyn_mW_per_GHz': 1.518142},
    2033: {'label': '"A5 eq"', 'vdd': 0.60, 'vt': 0.1636221, 'vdsat': 0.1200,
           'ss_mV_dec': 70, 'f_unloaded': 8.590244, 'f_wireloaded': 4.889564,
           'f_cpu': 3.932391, 'dyn_mW_per_GHz': 1.438783},
    2035: {'label': '"A3.5 eq"', 'vdd': 0.60, 'vt': 0.1578691, 'vdsat': 0.1200,
           'ss_mV_dec': 70, 'f_unloaded': 7.740604, 'f_wireloaded': 5.192435,
           'f_cpu': 4.175973, 'dyn_mW_per_GHz': 1.229334},
    2037: {'label': '"A2.5 eq"', 'vdd': 0.60, 'vt': 0.1507670, 'vdsat': 0.1200,
           'ss_mV_dec': 70, 'f_unloaded': 6.689179, 'f_wireloaded': 4.961969,
           'f_cpu': 3.990622, 'dyn_mW_per_GHz': 1.096813},
}

ANCHORS = ('wireloaded', 'cpu', 'unloaded')


class IRDSVFModel(object):
    """Alpha-power V/F curve anchored on one IRDS node's own operating point.

        f(V) = k * (V - Vt)^alpha / V,   k chosen so f(vdd) == f_anchor

    ``calibrated`` is False: the curve passes through a roadmap projection, which is a published
    target rather than a measurement of silicon, and ``alpha`` is an assumption on top of it.
    """

    def __init__(self, year=2024, anchor='wireloaded', alpha=DEFAULT_ALPHA,
                 overdrive=DEFAULT_OVERDRIVE):
        if year not in IRDS_NODES:
            raise ValueError('no IRDS node for {!r}; have {}'.format(year, sorted(IRDS_NODES)))
        if anchor not in ANCHORS:
            raise ValueError('anchor must be one of {}, got {!r}'.format(ANCHORS, anchor))
        if alpha <= 0:
            raise ValueError('alpha must be > 0, got {!r}'.format(alpha))
        if overdrive < 0:
            raise ValueError('overdrive must be >= 0, got {!r}'.format(overdrive))
        node = IRDS_NODES[year]
        self.year = year
        self.label = node['label']
        self.anchor = anchor
        self.alpha = float(alpha)
        self.vdd = float(node['vdd'])
        self.vt = float(node['vt'])
        self.f_anchor = float(node['f_' + anchor])
        self.dyn_mW_per_GHz = float(node['dyn_mW_per_GHz'])
        self.overdrive = float(overdrive)
        self.v_max = self.vdd * (1.0 + self.overdrive)
        self.v_min = self.vt * 1.25          # below this the delay law is meaningless
        if self.vdd <= self.vt:
            raise ValueError('node {} has vdd <= vt'.format(year))
        self._k = self.f_anchor * self.vdd / (self.vdd - self.vt) ** self.alpha
        self.calibrated = False

    # -- the curve ---------------------------------------------------------------------
    def frequency(self, V):
        """Clock at supply voltage ``V`` [GHz]. Returns 0 at or below threshold."""
        V = float(V)
        if V <= self.vt:
            return 0.0
        return self._k * (V - self.vt) ** self.alpha / V

    def voltage(self, f_GHz, clamp=True):
        """Supply voltage needed for ``f_GHz`` [V].

        ``clamp`` (default) limits the answer to ``v_max`` and reports the clamp, because past
        the node's overdrive limit a part does not run slower -- it fails. Returns
        ``(voltage, clamped)``.
        """
        target = float(f_GHz)
        if target <= 0:
            return self.v_min, False
        lo, hi = self.vt + 1e-9, max(self.v_max * 4.0, self.vdd * 4.0)
        if self.frequency(hi) < target:
            return (self.v_max, True) if clamp else (hi, True)
        for _ in range(200):                      # monotone in V above vt: bisection is exact
            mid = 0.5 * (lo + hi)
            if self.frequency(mid) < target:
                lo = mid
            else:
                hi = mid
        v = 0.5 * (lo + hi)
        if clamp and v > self.v_max:
            return self.v_max, True
        return v, False

    @property
    def f_max(self):
        """Clock at the node's maximum operating voltage [GHz] -- the real ceiling."""
        return self.frequency(self.v_max)

    def dynamic_power_scale(self, f_GHz, f_ref_GHz):
        """``(V/V_ref)^2 * (f/f_ref)`` on this curve -- the cost of moving clock."""
        v, _ = self.voltage(f_GHz)
        v_ref, _ = self.voltage(f_ref_GHz)
        if v_ref <= 0:
            raise ValueError('reference voltage resolved to <= 0')
        return (v / v_ref) ** 2 * (float(f_GHz) / float(f_ref_GHz))

    def alpha_sensitivity(self, f_GHz, alphas=(1.0, 1.3, 1.4, 1.6)):
        """Voltage for ``f_GHz`` across plausible ``alpha`` -- the assumption's own error bar.

        Provided so a result that leans on alpha can be checked instead of trusted. Anything
        whose sign changes across this range is not a finding.
        """
        out = {}
        for a in alphas:
            m = IRDSVFModel(self.year, self.anchor, alpha=a, overdrive=self.overdrive)
            v, clamped = m.voltage(f_GHz)
            out[a] = {'V': v, 'clamped': clamped, 'f_max_GHz': m.f_max}
        return out

    def __repr__(self):
        return ('<IRDSVFModel {} ({}) Vdd {:.2f} V, Vt {:.3f} V, anchor {}={:.3f} GHz, '
                'alpha {:.2f}, f_max {:.3f} GHz @ {:.3f} V UNCALIBRATED>'.format(
                    self.year, self.label, self.vdd, self.vt, self.anchor, self.f_anchor,
                    self.alpha, self.f_max, self.v_max))


def compare_with_shipped_table(freqs=(3.85, 4.22, 4.36, 5.19), year=2024, anchor='wireloaded'):
    """Voltage the shipped table demands versus this model, at the same clocks.

    Kept as a function rather than a comment so the discrepancy that motivated this module can be
    re-derived on demand instead of being taken on faith.
    """
    from HotGauge.power.performance_model import voltage_for_frequency
    m = IRDSVFModel(year, anchor)
    rows = []
    for f in freqs:
        old, old_clamped = voltage_for_frequency(f)
        new, new_clamped = m.voltage(f)
        rows.append({'f_GHz': f, 'shipped_V': old, 'shipped_clamped': old_clamped,
                     'irds_V': new, 'irds_clamped': new_clamped,
                     'dyn_power_ratio': (old / new) ** 2 if new > 0 else float('inf')})
    return rows
