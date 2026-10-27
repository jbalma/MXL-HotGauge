"""A generalized f_max(V, T | logic depth, wire fraction, skew) with V_max from a reliability
budget at the cooled temperature (§P0.31, 13 Sep 2026).

What this replaces, and why
---------------------------
``device_vf.DeviceVFModel`` gives the clock search a V/F *shape* -- ``f(V) = k I_on(V)/V`` on the
ASAP7 card -- but three things about it stop the cooler from ever reaching the clock:

1. **It is re-anchored at every temperature.** ``k`` is fitted so that ``f(0.70 V) = 3.8 GHz`` at
   whatever temperature the model was loaded at, so a colder die has the same clock at the same
   voltage by construction and ``I_on(T)`` never enters.
2. **Its ceiling is an ASSUMED 10 % overdrive** (``irds_vf.DEFAULT_OVERDRIVE``): 0.77 V whether the
   worst block sits at 100 C or at 40 C. That is what makes "4.17 GHz" the end of every laser arm
   (``limited_by: vf_envelope``) and why "10 GHz" cannot be tested either way.
3. **A gate is the whole period.** No wire, no skew, no setup/jitter -- so the period scales with
   the device alone and nothing names what a re-pipelined core would buy.

Here the period is built from its parts and anchored ONCE, at the trace's operating point:

    T_period(V, T, dT) = N_logic * [ FO4(V, T) + wire(T) ] + T_skew(dT, T) + T_ovh

* ``FO4(V, T) = FO4_ref * [V / I_on(V, T)] / [V_dd / I_on(V_dd, T_anchor)]`` -- the gate delay
  ``C V / I_on`` on the card's simulated ``I_on(V, T)`` (``docs/evidence/device_vt_vf_asap7*.json``,
  14 temperatures, V to 0.85 V or, in the extended file, 1.00 V). ``FO4_ref`` is the per-stage
  gate delay the anchor implies for the REFERENCE logic depth (20 FO4 at 3.8 GHz / 0.70 V /
  330 K gives 8.2 ps, which is where the ASAP7 FO4 sits -- a sanity check, not an input).
* ``wire(T) = wire_ref * (1 + alpha_R (T - T_anchor))`` -- the RC part of a stage, a stated
  FRACTION of the combinational delay at the anchor, temperature-dependent through the copper
  resistivity (0.40 %/K) and independent of V (repeaters' drive is folded into the gate term).
* ``T_skew(dT, T) = D_ins * dT * (w_wire alpha_R + w_cell alpha_cell(T))`` -- X2's thermal skew
  (§P0.27), one H-tree per core domain, with the core-domain gradient ``dT`` READ FROM THE SOLVE
  the clock is being evaluated on; ``alpha_cell`` is the card's own ``-d ln I_on / dT``.
* ``T_ovh`` -- setup plus jitter, a stated fraction of the anchor period, fixed in picoseconds
  (it does not shrink with the pipeline, which is what makes very short pipelines pay for it).

and ``V_max`` is the largest supply at which the die's worst block has the SAME lifetime as the
qualification point, mechanism by mechanism (Arrhenius in T, a stated acceleration in V):

* electromigration, Black's law ``MTTF ~ J^-n exp(E_a / kT)`` with ``n = 2``, ``E_a = 0.9 eV``
  as in X1 (§P0.27) and ``J ~ V f`` (the current a rail or signal wire carries at clock ``f``);
* dielectric breakdown (TDDB), the power-law voltage model ``MTTF ~ V^-n exp(E_a / kT)`` with
  ``n = 40`` and ``E_a = 0.6 eV`` (thin-oxide values; both STATED and swept in the evidence).

The **qualification point** is today's rule restated: ``V_dd (1 + 0.10)`` at the thermal limit
(100 C). So at 100 C this model gives back the 10 % overdrive exactly, and below it the budget
buys voltage -- that is the claim the brief asked to test. ``budget_ref='native'`` is the other
reading (X1's): the native die at 0.70 V, 3.8 GHz and its own worst-block temperature is the
budget, in which case a cooled die held at 92 C is OVER budget and must be held cooler than the
native die before it may clock faster.

`[!]` What is still assumed, stated once: one device (``nmos_rvt``), no p-side, no self-heating;
the wire fraction, the logic depth, the overhead fraction and the insertion delay are ARCHITECTURE
parameters, not measurements; the reliability constants are textbook and are swept; and
``FO4_ref`` inherits the trace's 3.8 GHz anchor, so absolute clocks are UNCALIBRATED exactly as
``DeviceVFModel``'s were. What the model makes testable is the *composition* of the ceiling: which
term binds, and what changes it.
"""
import os
import re
import json
import math

import numpy as np

from HotGauge.power.irds_vf import DEFAULT_OVERDRIVE

#: The recorded sweep (to 0.85 V) and its extension (to 1.00 V, §P0.31); the loader prefers the
#: extension when it exists because a reliability-budgeted V_max at a cool target exceeds 0.85 V.
DEVICE_VF_EVIDENCE = os.path.join('docs', 'evidence', 'device_vt_vf_asap7.json')
DEVICE_VF_EVIDENCE_EXTENDED = os.path.join('docs', 'evidence', 'device_vt_vf_asap7_v100.json')

K_EV_PER_K = 8.617333e-5

_CORE_RGX = re.compile(r'^(.*)_(\d+)$')

#: Every stated parameter, in one place, so the evidence file can carry them verbatim.
DEFAULTS = {
    # the anchor: where the trace sits (3.8 GHz at the card's 0.70 V, McPAT's 330 K T_ref)
    'f_anchor_GHz': 3.8, 'T_anchor_K': 330.0,
    # the reference architecture that the anchor is a statement about
    'logic_depth_ref': 20.0,
    # the architecture under study (defaults to the reference; 8-10 is Pentium-4-class)
    'logic_depth': 20.0,
    'wire_fraction': 0.30,          # of the combinational delay at the anchor
    'overhead_fraction': 0.08,      # setup + jitter, of the anchor period, fixed in ps
    # X2's skew model (§P0.27): one H-tree per core domain
    'D_ins_ps': 150.0, 'alpha_R_per_K': 0.0040, 'w_wire': 0.5, 'w_cell': 0.5,
    'dT_anchor_K': 24.0,            # the native die's worst core-domain gradient (X2)
    # the reliability budget
    'budget_ref': 'qual',           # 'qual' | 'native'
    'overdrive_qual': DEFAULT_OVERDRIVE, 'T_qual_K': 373.15,
    'T_native_K': 351.73, 'V_native_V': 0.70, 'f_native_GHz': 3.8,   # native_d0.78_control, cALU_16
    'em_n': 2.0, 'em_Ea_eV': 0.9,
    'tddb_n': 40.0, 'tddb_Ea_eV': 0.6,
    'mechanisms': ('em', 'tddb'),
    # §P0.39: the RAIL model, V_eff = V_dd - IR. OFF by default (0 = no rail, every recorded
    # number unchanged). ``rail_droop_native`` is the fraction of V_dd the NATIVE die's worst
    # execution block drops across its rails at its own current density ``J_native`` (X1,
    # §P0.27: 44.4 A/mm^2, FPUs, native_d0.78_control) -- i.e. the rails are SIZED for the native
    # die to a stated IR budget (5 % is the textbook static budget). ``rail_resize`` widens them:
    # the specific resistance is droop * V_dd / J_native / resize [ohm mm^2].
    'rail_droop_native': 0.0, 'J_native_A_per_mm2': 44.45, 'rail_resize': 1.0,
}

#: The execution-cluster families whose current density the rail model reads (X1's set).
EXEC_FAMILIES = ('cALU', 'iALU', 'FPUs', 'AVXs')


def worst_current_density(power_W_by_block, area_mm2_by_block, V, families=EXEC_FAMILIES):
    """``(J_max [A/mm^2], block)`` over the blocks of ``families``: ``P / (V A)`` per block.

    X1's arithmetic (§P0.27) on a converged power map. ``families=None`` takes every block.
    """
    best, who = 0.0, None
    for name, P in power_W_by_block.items():
        m = _CORE_RGX.match(name)
        fam = m.group(1) if m else name
        if families is not None and fam not in families:
            continue
        a = float(area_mm2_by_block.get(name, 0.0) or 0.0)
        if a <= 0.0:
            continue
        j = float(np.ravel(P)[-1]) / (float(V) * a)
        if j > best:
            best, who = j, name
    return best, who

def repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def core_gradient_K(temps, exclude=('L3',)):
    """Worst and mean core-domain temperature gradient [K] of a solved field ``{block: K}``.

    A block ``<family>_<core>`` belongs to core domain ``<core>``; L3 slices are excluded as in
    X2 (§P0.27). Returns ``(worst_K, mean_K, worst_core)``; ``(0, 0, None)`` if no core parses.
    """
    cores = {}
    for name, t in temps.items():
        m = _CORE_RGX.match(name)
        if not m or m.group(1) in exclude or m.group(1) == 'IO':
            continue
        cores.setdefault(int(m.group(2)), []).append(float(np.ravel(t)[-1]))
    if not cores:
        return 0.0, 0.0, None
    spans = {c: max(v) - min(v) for c, v in cores.items()}
    worst = max(spans, key=spans.get)
    return float(spans[worst]), float(np.mean(list(spans.values()))), worst


class GeneralizedFmaxModel(object):
    """``f_max(V, T | logic depth, wire fraction, skew)`` with ``V_max`` from a reliability budget.

    The model carries an operating **context** ``(T_K, dT_K)`` -- the worst block's temperature
    and the worst core-domain gradient of the solve it is being evaluated against -- because the
    clock search's ``vf_model.voltage(f)`` interface has no temperature argument. The driver sets
    it from each solve (``set_context``) and re-solves when the voltage it implies moves.
    """

    calibrated = False
    year = 'fmax'
    anchor = 'card'

    def __init__(self, V, I_on_by_T, vdd, vt_by_T=None, ss_by_T=None, label='ASAP7 nmos_rvt',
                 **params):
        p = dict(DEFAULTS)
        unknown = set(params) - set(p)
        if unknown:
            raise ValueError('unknown fmax parameters: {}'.format(sorted(unknown)))
        p.update(params)
        self.p = p
        V = np.asarray(V, dtype=float)
        if len(V) < 3 or np.any(np.diff(V) <= 0):
            raise ValueError('V must be a strictly increasing sweep of at least three points')
        Ts = sorted(float(t) for t in I_on_by_T)
        if len(Ts) < 2:
            raise ValueError('need I_on at two or more temperatures')
        lnI = []
        for t in Ts:
            row = np.asarray(I_on_by_T[t], dtype=float)
            if row.shape != V.shape or np.any(row <= 0):
                raise ValueError('I_on row at {} K must match V and be positive'.format(t))
            lnI.append(np.log(row))
        self.V = V
        self.T_rows = np.asarray(Ts)
        self._lnI = np.asarray(lnI)          # [T, V]
        self.vdd = float(vdd)
        self.vt_by_T = {float(k): float(v) for k, v in (vt_by_T or {}).items()}
        self.ss_by_T = {float(k): float(v) for k, v in (ss_by_T or {}).items()}
        self.label = label
        self.T_anchor = float(p['T_anchor_K'])
        self.f_anchor = float(p['f_anchor_GHz'])
        if not (self.T_rows[0] <= self.T_anchor <= self.T_rows[-1]):
            raise ValueError('T_anchor {} K is outside the simulated temperatures'.format(self.T_anchor))
        if not (V[0] <= self.vdd <= V[-1]):
            raise ValueError('vdd {} V is outside the I_on sweep'.format(self.vdd))
        for k in ('logic_depth', 'logic_depth_ref', 'D_ins_ps'):
            if p[k] <= 0:
                raise ValueError('{} must be > 0'.format(k))
        if not 0.0 <= p['wire_fraction'] < 1.0:
            raise ValueError('wire_fraction must be in [0, 1)')
        if not 0.0 <= p['overhead_fraction'] < 1.0:
            raise ValueError('overhead_fraction must be in [0, 1)')
        if p['budget_ref'] not in ('qual', 'native'):
            raise ValueError("budget_ref must be 'qual' or 'native'")
        if not 0.0 <= p['rail_droop_native'] < 0.5:
            raise ValueError('rail_droop_native must be in [0, 0.5)')
        if p['rail_resize'] <= 0 or p['J_native_A_per_mm2'] <= 0:
            raise ValueError('rail_resize and J_native_A_per_mm2 must be > 0')
        # §P0.39: the rail's specific resistance [ohm mm^2] and the context current density.
        # The anchor (3.8 GHz at 0.70 V) is a statement about the native die ON its native
        # rails, so the gate term is normalised at the anchor's EFFECTIVE supply.
        self.rail_ohm_mm2 = (p['rail_droop_native'] * float(vdd) / p['J_native_A_per_mm2']
                             / p['rail_resize'])
        self.J_A_per_mm2 = float(p['J_native_A_per_mm2'])
        self._anchor_drop_V = p['rail_droop_native'] * float(vdd)
        # -- the anchor decomposition, in picoseconds ----------------------------------------
        P0 = 1000.0 / self.f_anchor
        self.T_ovh_ps = p['overhead_fraction'] * P0
        self.T_skew0_ps = self.skew_ps(p['dT_anchor_K'], self.T_anchor)
        T_comb0 = P0 - self.T_ovh_ps - self.T_skew0_ps
        if T_comb0 <= 0:
            raise ValueError('overhead + skew exceed the anchor period; the parameters are not a '
                             'clocked design')
        self.T_gate0_ps = (1.0 - p['wire_fraction']) * T_comb0
        self.T_wire0_ps = p['wire_fraction'] * T_comb0
        # per-stage delays of the REFERENCE architecture at the anchor
        self.FO4_ref_ps = self.T_gate0_ps / p['logic_depth_ref']
        self.wire_ref_ps = self.T_wire0_ps / p['logic_depth_ref']
        v_eff0 = self.vdd - self._anchor_drop_V
        self._gate_norm = v_eff0 / self._ion(v_eff0, self.T_anchor)
        self.v_sweep_end = float(V[-1])
        # operating context: start at the anchor
        self.T_K = self.T_anchor
        self.dT_K = float(p['dT_anchor_K'])
        # the qualification / native reference for the budget
        self._budget = self._budget_reference()

    # -- the card ---------------------------------------------------------------------------
    def _ion(self, V, T):
        V = float(V)
        T = float(T)
        if V < self.V[0] - 1e-12 or V > self.V[-1] + 1e-12:
            raise ValueError('V = {:.3f} is outside the simulated sweep {:.3f}-{:.3f} V'
                             .format(V, self.V[0], self.V[-1]))
        T = min(max(T, self.T_rows[0]), self.T_rows[-1])      # clamp: the card stops at 200 / 500 K
        col = np.array([np.interp(V, self.V, row) for row in self._lnI])
        return float(math.exp(np.interp(T, self.T_rows, col)))

    def ion(self, V, T=None):
        """Simulated ``I_on(V, T)`` [A per fin] with the temperature clamped to the card's range."""
        return self._ion(V, self.T_K if T is None else T)

    def vt(self, T=None):
        T = self.T_K if T is None else float(T)
        if not self.vt_by_T:
            return None
        Ts = sorted(self.vt_by_T)
        return float(np.interp(T, Ts, [self.vt_by_T[t] for t in Ts]))

    def alpha_cell(self, T=None):
        """``-d ln I_on(V_dd, T) / dT`` [1/K] from the card, at ``T`` (X2 used 0.942 over 100 K)."""
        T = self.T_K if T is None else float(T)
        h = 5.0
        lo, hi = max(T - h, self.T_rows[0]), min(T + h, self.T_rows[-1])
        if hi <= lo:
            return 0.0
        return -(math.log(self._ion(self.vdd, hi)) - math.log(self._ion(self.vdd, lo))) / (hi - lo)

    # -- the period -------------------------------------------------------------------------
    def skew_coef(self, T=None):
        p = self.p
        return p['w_wire'] * p['alpha_R_per_K'] + p['w_cell'] * self.alpha_cell(T)

    def skew_ps(self, dT_K, T=None):
        return self.p['D_ins_ps'] * float(dT_K) * self.skew_coef(T)

    @property
    def has_rail(self):
        return self.rail_ohm_mm2 > 0.0

    def ir_drop_V(self, J_A_per_mm2=None):
        """§P0.39: the static IR drop [V] at the worst execution block's current density.

        With the rails widened ``rail_resize`` x the anchor's own drop shrinks too, which is the
        re-sizing dividend on the NATIVE die; it is included (the anchor's FO4 was normalised on
        the un-resized rails).
        """
        J = self.J_A_per_mm2 if J_A_per_mm2 is None else float(J_A_per_mm2)
        return self.rail_ohm_mm2 * J

    def v_eff(self, V, J_A_per_mm2=None):
        return float(V) - self.ir_drop_V(J_A_per_mm2)

    def gate_ps(self, V, T=None):
        """Per-stage gate delay at ``(V, T)``: ``FO4_ref * [V/I_on(V,T)] / [V_dd/I_on(V_dd,T_anchor)]``,
        with ``V`` the EFFECTIVE supply ``V - IR`` when a rail model is on (§P0.39)."""
        T = self.T_K if T is None else float(T)
        v = self.v_eff(V) if self.has_rail else float(V)
        if self.has_rail and v < self.V[0] - 1e-12:
            # the rails eat the supply (found on the 16x cluster on native rails: V_eff 0.08 V):
            # no gate switches, the period is unbounded -- a verdict, not an error
            return float('inf')
        return self.FO4_ref_ps * (v / self._ion(v, T)) / self._gate_norm

    def wire_ps(self, T=None):
        T = self.T_K if T is None else float(T)
        return self.wire_ref_ps * (1.0 + self.p['alpha_R_per_K'] * (T - self.T_anchor))

    def period_terms(self, V, T=None, dT=None, logic_depth=None):
        """The period's four terms [ps] at ``(V, T, dT)`` and the clock they give."""
        T = self.T_K if T is None else float(T)
        dT = self.dT_K if dT is None else float(dT)
        N = self.p['logic_depth'] if logic_depth is None else float(logic_depth)
        gate = N * self.gate_ps(V, T)
        wire = N * self.wire_ps(T)
        skew = self.skew_ps(dT, T)
        ovh = self.T_ovh_ps
        total = gate + wire + skew + ovh
        if not math.isfinite(total):
            return {'ir_drop_V': self.ir_drop_V(), 'V_eff_V': self.v_eff(V), 'gate_ps': None, 'wire_ps': wire,
                    'skew_ps': skew, 'overhead_ps': ovh, 'period_ps': None, 'f_GHz': 0.0, 'V_V': float(V),
                    'T_K': T, 'dT_K': dT, 'logic_depth': N, 'dominant': 'rail',
                    'gate_frac': None, 'wire_frac': None, 'skew_frac': None, 'overhead_frac': None}
        terms = {'ir_drop_V': self.ir_drop_V() if self.has_rail else 0.0,
                 'V_eff_V': self.v_eff(V) if self.has_rail else float(V),
                 'gate_ps': gate, 'wire_ps': wire, 'skew_ps': skew, 'overhead_ps': ovh,
                 'period_ps': total, 'f_GHz': 1000.0 / total, 'V_V': float(V), 'T_K': T,
                 'dT_K': dT, 'logic_depth': N}
        for k in ('gate', 'wire', 'skew', 'overhead'):
            terms[k + '_frac'] = terms[k + '_ps'] / total
        terms['dominant'] = max(('gate', 'wire', 'skew', 'overhead'), key=lambda k: terms[k + '_ps'])
        return terms

    def frequency(self, V, T=None, dT=None):
        """Clock [GHz] at supply ``V`` in the given (or current) context; 0 at or below threshold."""
        V = float(V)
        vt = self.vt(T)
        if vt is not None and V <= vt:
            return 0.0
        if V < self.V[0] - 1e-12:
            return 0.0
        if self.has_rail:
            v = self.v_eff(V)
            if v < self.V[0] - 1e-12 or (vt is not None and v <= vt):
                return 0.0           # the rails eat the supply: no clock at this V and J
        return self.period_terms(V, T, dT)['f_GHz']

    def device_peak(self, T=None, dT=None):
        """The supply at which the clock stops rising with V, and the clock there.

        ``I_on / V`` saturates on the card (velocity saturation: the fitted alpha falls from 1.45
        over 0.45-0.77 V to 1.34 over 0.45-1.00 V), so ``f(V)`` has a MAXIMUM inside the sweep at
        every temperature once the sweep reaches ~1 V. Above it more voltage buys no clock --
        that is a DEVICE limit, distinct from the reliability budget and from the sweep's end.
        Returns ``(V_peak, f_peak, at_sweep_end)``.
        """
        grid = np.linspace(self.V[0], self.v_sweep_end, 281)
        fs = np.array([self.frequency(v, T, dT) for v in grid])
        i = int(np.argmax(fs))
        return float(grid[i]), float(fs[i]), bool(i >= len(grid) - 1)

    def voltage(self, f_GHz, clamp=True, T=None, dT=None):
        """Supply needed for ``f_GHz`` in the context; ``(voltage, clamped)``.

        ``clamped`` is True when the clock is above the device's peak clock in this context:
        the answer is then the peak's supply. Whether that peak is the card's saturation (a
        device limit) or the sweep's last point (a data limit) is ``device_peak()``'s third value.
        """
        target = float(f_GHz)
        lo = self.V[0]
        if target <= 0:
            return lo, False
        v_pk, f_pk, _ = self.device_peak(T, dT)
        if target >= f_pk:
            return v_pk, True
        hi = v_pk
        if self.frequency(lo, T, dT) >= target:
            return lo, False
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if self.frequency(mid, T, dT) < target:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi), False

    def reference_voltage(self, f_ref_GHz):
        """The supply the TRACE was computed at, for the dynamic-power ratio ``(V/V_ref)^2``.

        The trace's dynamic power is a statement about the anchor (0.70 V, 3.8 GHz, 330 K), so
        the reference voltage is evaluated in the ANCHOR context, not the current one -- at a
        hotter die ``voltage(3.8 GHz)`` would exceed 0.70 V and the power ratio would be
        understated. ``clock_search.clock_power_factors`` prefers this method when it exists.
        """
        return self.voltage(f_ref_GHz, T=self.T_anchor, dT=self.p['dT_anchor_K'])

    # -- the reliability budget -------------------------------------------------------------
    def _budget_reference(self):
        p = self.p
        if p['budget_ref'] == 'qual':
            V_q = self.vdd * (1.0 + p['overdrive_qual'])
            T_q = float(p['T_qual_K'])
            f_q = self.frequency(min(V_q, self.v_sweep_end), T_q, p['dT_anchor_K'])
        else:
            V_q, T_q, f_q = float(p['V_native_V']), float(p['T_native_K']), float(p['f_native_GHz'])
        return {'ref': p['budget_ref'], 'V_q_V': V_q, 'T_q_K': T_q, 'f_q_GHz': f_q}

    def _arrhenius(self, Ea_eV, T_K):
        b = self._budget
        return math.exp(Ea_eV / K_EV_PER_K * (1.0 / b['T_q_K'] - 1.0 / float(T_K)))

    def acceleration(self, V, T=None, dT=None):
        """Per-mechanism acceleration factors against the budget's reference point (1 = on budget)."""
        T = self.T_K if T is None else float(T)
        p, b = self.p, self._budget
        f = self.frequency(V, T, dT)
        out = {}
        if 'em' in p['mechanisms']:
            j_ratio = (float(V) * f) / (b['V_q_V'] * b['f_q_GHz'])
            out['em'] = (j_ratio ** p['em_n']) * self._arrhenius(p['em_Ea_eV'], T)
        if 'tddb' in p['mechanisms']:
            out['tddb'] = ((float(V) / b['V_q_V']) ** p['tddb_n']) * self._arrhenius(p['tddb_Ea_eV'], T)
        return out

    def v_max_reliability(self, T=None, dT=None):
        """Largest supply on budget at the worst block's ``T``: per mechanism, and the binding one.

        Each mechanism's acceleration rises monotonically with V, so its own V_max is a bisection
        (TDDB is closed-form: ``V_q exp(-(E_a/k)(1/T_q - 1/T) / n)``). ``sweep_limited`` marks a
        mechanism whose budget is not exhausted at the sweep's last voltage -- its V_max is then
        the sweep end and the true value is above it.
        """
        T = self.T_K if T is None else float(T)
        p, b = self.p, self._budget
        per = {}
        for mech in p['mechanisms']:
            lo, hi = self.V[0], self.v_sweep_end
            acc_hi = self.acceleration(hi, T, dT)[mech]
            if acc_hi <= 1.0:
                per[mech] = {'v_max_V': hi, 'sweep_limited': True}
                continue
            if self.acceleration(lo, T, dT)[mech] >= 1.0:
                per[mech] = {'v_max_V': lo, 'sweep_limited': False}
                continue
            for _ in range(100):
                mid = 0.5 * (lo + hi)
                if self.acceleration(mid, T, dT)[mech] < 1.0:
                    lo = mid
                else:
                    hi = mid
            per[mech] = {'v_max_V': 0.5 * (lo + hi), 'sweep_limited': False}
        if 'tddb' in per and not per['tddb']['sweep_limited']:
            per['tddb']['closed_form_V'] = b['V_q_V'] * math.exp(
                -(p['tddb_Ea_eV'] / K_EV_PER_K) * (1.0 / b['T_q_K'] - 1.0 / T) / p['tddb_n'])
        tight = min(per, key=lambda m: per[m]['v_max_V'])
        # At the qualification corner every mechanism gives back V_q by construction -- a tie,
        # reported as such ('em+tddb') rather than resolved by dictionary order.
        ties = sorted(m for m in per if per[m]['v_max_V'] <= per[tight]['v_max_V'] + 1e-6)
        binding = '+'.join(ties) if len(ties) > 1 else tight
        return {'v_max_V': per[tight]['v_max_V'], 'binding': binding,
                'sweep_limited': per[tight]['sweep_limited'], 'per_mechanism': per,
                'T_K': T, 'reference': dict(b),
                'v_max_over_vdd': per[tight]['v_max_V'] / self.vdd}

    def f_max_at(self, T, dT=None):
        """The ceiling at ``(T, dT)``: the clock at the smaller of the reliability-budgeted V_max
        and the device's peak-clock supply, and which of the two set it.

        ``limiter`` is one of ``reliability:em`` / ``reliability:tddb`` (the budget binds first),
        ``device`` (``I_on/V`` saturates before the budget is spent) or ``sweep_end`` (neither
        binds inside the simulated sweep -- extend it). The period's ``dominant_term`` says what
        the period is made of at the ceiling, which is a different question.
        """
        rel = self.v_max_reliability(T, dT)
        v_pk, f_pk, at_end = self.device_peak(T, dT)
        if v_pk < rel['v_max_V'] - 1e-9:
            v_ceiling, limiter = v_pk, ('sweep_end' if at_end else 'device')
        else:
            v_ceiling = rel['v_max_V']
            limiter = ('sweep_end' if rel['sweep_limited'] else 'reliability:' + rel['binding'])
        terms = self.period_terms(v_ceiling, T, dT)
        return {'f_max_GHz': terms['f_GHz'], 'v_max_V': v_ceiling, 'limiter': limiter,
                'v_max_reliability_V': rel['v_max_V'], 'binding': rel['binding'],
                'sweep_limited': rel['sweep_limited'], 'v_device_peak_V': v_pk,
                'f_device_peak_GHz': f_pk, 'period': terms, 'dominant_term': terms['dominant']}

    @property
    def v_max(self):
        return self.v_max_reliability()['v_max_V']

    @property
    def f_max(self):
        return self.f_max_at(self.T_K, self.dT_K)['f_max_GHz']

    def logic_depth_for(self, f_target_GHz, V, T=None, dT=None):
        """Logic depth (FO4 per stage) at which ``(V, T, dT)`` would clock ``f_target``; None if
        the fixed terms alone exceed the period (no pipeline reaches it)."""
        T = self.T_K if T is None else float(T)
        dT = self.dT_K if dT is None else float(dT)
        fixed = self.T_ovh_ps + self.skew_ps(dT, T)
        avail = 1000.0 / float(f_target_GHz) - fixed
        if avail <= 0:
            return None
        return avail / (self.gate_ps(V, T) + self.wire_ps(T))

    # -- the clock_search interface ---------------------------------------------------------
    def set_context(self, T_K, dT_K=None, J_A_per_mm2=None):
        self.T_K = float(T_K)
        if dT_K is not None:
            self.dT_K = float(dT_K)
        if J_A_per_mm2 is not None:
            self.J_A_per_mm2 = float(J_A_per_mm2)

    def dynamic_power_scale(self, f_GHz, f_ref_GHz):
        v, _ = self.voltage(f_GHz)
        v_ref, _ = self.reference_voltage(f_ref_GHz)
        return (v / v_ref) ** 2 * (float(f_GHz) / float(f_ref_GHz))

    @property
    def source_tag(self):
        p = self.p
        tag = 'fmax:{}:N{:g}:w{:.2f}:{}'.format(self.label.split()[0].lower(), p['logic_depth'],
                                                 p['wire_fraction'], p['budget_ref'])
        if self.has_rail:
            tag += ':rail{:g}x{:g}'.format(p['rail_droop_native'], p['rail_resize'])
        return tag

    def describe(self):
        """Every parameter and derived anchor quantity, for the evidence file."""
        return {'label': self.label, 'vdd_V': self.vdd, 'V_sweep_V': [float(self.V[0]), float(self.V[-1])],
                'T_rows_K': [float(t) for t in self.T_rows], 'params': dict(self.p),
                'anchor': {'f_GHz': self.f_anchor, 'T_K': self.T_anchor, 'period_ps': 1000.0 / self.f_anchor,
                           'gate_ps': self.T_gate0_ps, 'wire_ps': self.T_wire0_ps,
                           'skew_ps': self.T_skew0_ps, 'overhead_ps': self.T_ovh_ps,
                           'FO4_ref_ps': self.FO4_ref_ps, 'wire_per_stage_ref_ps': self.wire_ref_ps,
                           'alpha_cell_per_K': self.alpha_cell(self.T_anchor)},
                'budget_reference': dict(self._budget), 'source_tag': self.source_tag,
                'rail': {'on': self.has_rail, 'specific_resistance_ohm_mm2': self.rail_ohm_mm2,
                         'anchor_drop_V': self._anchor_drop_V,
                         'note': 'V_eff = V - rho_rail * J(worst execution block); static IR only, '
                                 'no L di/dt, no on-die decap; TDDB and EM still see the pin V'}}

    def __repr__(self):
        return ('<GeneralizedFmaxModel {} N={:g} (ref {:g}) wire {:.2f} ovh {:.2f} D_ins {:.0f} ps; '
                'anchor {:.2f} GHz @ {:.2f} V / {:.0f} K (FO4 {:.2f} ps); budget {} (EM n={:g} '
                'Ea={:g}; TDDB n={:g} Ea={:g}); context {:.1f} K / dT {:.1f} K -> V_max {:.3f} V, '
                'f_max {:.3f} GHz UNCALIBRATED>'
                .format(self.label, self.p['logic_depth'], self.p['logic_depth_ref'],
                        self.p['wire_fraction'], self.p['overhead_fraction'], self.p['D_ins_ps'],
                        self.f_anchor, self.vdd, self.T_anchor, self.FO4_ref_ps, self.p['budget_ref'],
                        self.p['em_n'], self.p['em_Ea_eV'], self.p['tddb_n'], self.p['tddb_Ea_eV'],
                        self.T_K, self.dT_K, self.v_max, self.f_max))


def evidence_path(prefer_extended=True):
    root = repo_root()
    ext = os.path.join(root, DEVICE_VF_EVIDENCE_EXTENDED)
    if prefer_extended and os.path.isfile(ext):
        return ext
    return os.path.join(root, DEVICE_VF_EVIDENCE)


def load_fmax_model(path=None, prefer_extended=True, **params):
    """A :class:`GeneralizedFmaxModel` from the recorded sweep (the 1.00 V extension if present)."""
    path = path or evidence_path(prefer_extended)
    with open(path) as f:
        ev = json.load(f)
    by_T = {float(r['T_K']): r['I_on_A_per_fin'] for r in ev['idsat']['by_T']}
    vt = {float(r['T_K']): r['vt_sat_V'] for r in ev['vt']}
    ss = {float(r['T_K']): r['ss_lin_mV_dec'] for r in ev['vt']}
    m = GeneralizedFmaxModel(ev['idsat']['V'], by_T, vdd=ev['criteria']['vdd_V'], vt_by_T=vt,
                             ss_by_T=ss, label='ASAP7 {}'.format(ev['card']['device']), **params)
    m.source_meta = {'path': os.path.relpath(path, repo_root()), 'toolchain': ev.get('toolchain'),
                     'v_sweep_end_V': float(ev['idsat']['V'][-1])}
    return m


def parse_fmax_spec(spec):
    """``'fmax[:key=value[,key=value...]]'`` -> parameter dict for :func:`load_fmax_model`.

    Keys are the :data:`DEFAULTS` names (``logic_depth``, ``wire_fraction``, ``budget_ref``,
    ``tddb_n`` ...) with the short forms ``N`` (logic_depth), ``w`` (wire_fraction) and ``ref``
    (budget_ref). ``mechanisms`` takes ``em+tddb`` / ``em`` / ``tddb``.
    """
    spec = (spec or '').strip()
    if not spec.startswith('fmax'):
        raise ValueError('not an fmax spec: {!r}'.format(spec))
    rest = spec[len('fmax'):].lstrip(':')
    short = {'N': 'logic_depth', 'w': 'wire_fraction', 'ref': 'budget_ref',
             'rail': 'rail_droop_native', 'resize': 'rail_resize'}
    out = {}
    for frag in [x for x in rest.split(',') if x]:
        if '=' not in frag:
            raise ValueError('fmax spec fragment {!r} is not key=value'.format(frag))
        k, v = frag.split('=', 1)
        k = short.get(k, k)
        if k not in DEFAULTS:
            raise ValueError('unknown fmax parameter {!r}; known: {}'.format(k, sorted(DEFAULTS)))
        if k == 'budget_ref':
            out[k] = v
        elif k == 'mechanisms':
            out[k] = tuple(v.split('+'))
        else:
            out[k] = float(v)
    return out
