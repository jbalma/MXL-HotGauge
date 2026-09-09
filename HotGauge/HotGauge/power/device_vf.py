"""A V/F curve whose SHAPE is simulated from the device card, not assumed (§P0.18).

Where the three existing curves fall short, in one line each
-------------------------------------------------------------
* ``configuration.performance.VF_PAIRS`` -- a binning artefact (needs 1.4 V for 5 GHz).
* ``irds_vf.IRDSVFModel`` -- anchored on a roadmap operating point, but its **shape** is the
  alpha-power law with a textbook ``alpha = 1.4`` that the roadmap does not supply.
* ``product_vf`` -- one measured part, four points.

This module takes the shape from the same BSIM-CMG-in-ngspice evaluation of the ASAP7 card that
already supplies the project's leakage curve. A logic gate's delay is ``C V / I_on(V)``, so

    f(V) = k * I_on(V) / V,      k fixed by one anchor  f(V_anchor) = f_anchor

with ``I_on`` read off the diagonal sweep ``V_gs = V_ds = V`` (``spice_sim.idsat_deck``) at the
temperature asked for. Nothing about the exponent is assumed: ``alpha`` is *reported* from a fit
to the same data so it can be compared with the 1.4, and it is not used to compute anything.

`[!]` What the anchor is, and is not
-----------------------------------
The card fixes the shape and nothing else. An absolute clock needs one (voltage, frequency)
pair from somewhere, and the honest one available is the trace's own: LINPACK was run at
**3.8 GHz** and the card's nominal supply is **0.70 V**. So ``f_anchor = 3.8 GHz at 0.70 V`` is a
statement about *where the trace sits on the curve*, not a claim that ASAP7 runs 3.8 GHz.
``clock_search`` only ever uses ratios against ``f_ref`` and is insensitive to it; ``f_max``
and ``v_max`` are absolute and inherit it, and ``calibrated`` is False for that reason.

`[!]` One device is not a die, here as for leakage
--------------------------------------------------
``nmos_rvt`` at one drawn length, no self-heating, no wire load, no p-side. What transfers is
the shape of ``I_on(V)/V`` and the temperature coefficients; the per-um amps do not.

The threshold-voltage lever
---------------------------
Same interface as ``IRDSVFModel``: ``vt_shift_mV`` lowers the threshold, the gain is read off the
curve, and the cost ``10**(dVt / SS)`` uses the subthreshold swing **simulated at the operating
temperature** rather than the roadmap's single room-temperature figure. The shift is applied as a
rigid translation of ``I_on(V)`` in ``V``, which is what a lower-``V_t`` flavour of the same
device does to first order (ASAP7's LVT and SLVT cards differ from RVT in the work function
``phig`` and little else).
"""
import os
import json
import math

import numpy as np

from HotGauge.power.irds_vf import DEFAULT_OVERDRIVE

#: Where ``examples/device_vt_vf_spice.py`` writes the sweep this module reads.
DEVICE_VF_EVIDENCE = os.path.join('docs', 'evidence', 'device_vt_vf_asap7.json')

#: The trace's clock, which is the only honest absolute anchor available -- see the module note.
DEFAULT_F_ANCHOR_GHZ = 3.8


def repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


class DeviceVFModel(object):
    """``f(V) = k * I_on(V) / V`` on a simulated ``I_on(V)``, anchored at one (V, f) pair."""

    calibrated = False

    def __init__(self, V, I_on, vdd, f_anchor_GHz, vt, ss_mV_dec, T_K=300.0,
                 overdrive=DEFAULT_OVERDRIVE, vt_shift_mV=0.0, label='ASAP7 nmos_rvt'):
        V = np.asarray(V, dtype=float)
        I = np.asarray(I_on, dtype=float)
        if len(V) < 3 or len(V) != len(I):
            raise ValueError('need matching V and I_on arrays of at least three points')
        if np.any(np.diff(V) <= 0):
            raise ValueError('V must be strictly increasing')
        if np.any(I <= 0):
            raise ValueError('I_on must be positive everywhere on the sweep')
        if overdrive < 0:
            raise ValueError('overdrive must be >= 0, got {!r}'.format(overdrive))
        self.V = V
        self._lnI = np.log(I)
        self.vdd = float(vdd)
        self.f_anchor = float(f_anchor_GHz)
        self.T_K = float(T_K)
        self.vt_nominal = float(vt)
        self.vt_shift_mV = float(vt_shift_mV)
        self.vt = self.vt_nominal - self.vt_shift_mV / 1000.0
        self.ss_mV_dec = float(ss_mV_dec)
        self.overdrive = float(overdrive)
        self.label = label
        if self.vt <= 0:
            raise ValueError('vt_shift_mV={} drives Vt to {:.4f} V, which is not a device'
                             .format(vt_shift_mV, self.vt))
        # The sweep must reach the shifted top of the operating window: a shifted curve reads
        # I_on at V + dVt, and reading past the data would be an extrapolation dressed as a
        # simulation. Refuse rather than extrapolate.
        self.v_max = self.vdd * (1.0 + self.overdrive)
        if self.v_max + self.vt_shift_mV / 1000.0 > self.V[-1] + 1e-12:
            raise ValueError('the I_on sweep stops at {:.3f} V but the operating window needs '
                             '{:.3f} V (vdd {:.2f} x (1 + {:.2f}) + shift {:.3f}); extend the '
                             'sweep'.format(self.V[-1], self.v_max + self.vt_shift_mV / 1000.0,
                                            self.vdd, self.overdrive,
                                            self.vt_shift_mV / 1000.0))
        self.v_min = max(float(self.V[0]), self.vt * 1.25)
        # k is a property of the TECHNOLOGY: calibrated on the nominal curve and held while Vt
        # moves, for the reason irds_vf gives -- re-fitting it to the shifted curve would define
        # the low-Vt device to be no faster.
        self._k = self.f_anchor * self.vdd / self._ion(self.vdd, shift=False)
        # Reported, not used: the exponent an alpha-power law would need to reproduce this
        # sweep above threshold, so the shape can be compared with irds_vf.DEFAULT_ALPHA.
        from HotGauge.power.spice_sim import fit_alpha_power
        try:
            self.alpha_fit, _, self.alpha_fit_rms = fit_alpha_power(self.V, I, self.vt_nominal)
        except ValueError:
            self.alpha_fit, self.alpha_fit_rms = None, None

    # -- the curve ---------------------------------------------------------------------
    def _ion(self, V, shift=True):
        v = float(V) + (self.vt_shift_mV / 1000.0 if shift else 0.0)
        if v < self.V[0] or v > self.V[-1]:
            raise ValueError('V = {:.3f} is outside the simulated sweep {:.3f}-{:.3f} V'
                             .format(v, self.V[0], self.V[-1]))
        return float(math.exp(np.interp(v, self.V, self._lnI)))

    def frequency(self, V):
        """Clock at supply ``V`` [GHz]; 0 at or below threshold."""
        V = float(V)
        if V <= self.vt or V < self.V[0] - 1e-12:
            return 0.0
        return self._k * self._ion(V) / V

    def voltage(self, f_GHz, clamp=True):
        """Supply needed for ``f_GHz``; ``(voltage, clamped)`` with the same semantics as IRDS."""
        target = float(f_GHz)
        if target <= 0:
            return self.v_min, False
        lo = max(self.V[0], self.vt + 1e-9)
        hi = self.V[-1] - self.vt_shift_mV / 1000.0
        if self.frequency(hi) < target:
            return (self.v_max, True) if clamp else (hi, True)
        for _ in range(200):
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
        return self.frequency(self.v_max)

    def dynamic_power_scale(self, f_GHz, f_ref_GHz):
        v, _ = self.voltage(f_GHz)
        v_ref, _ = self.voltage(f_ref_GHz)
        if v_ref <= 0:
            raise ValueError('reference voltage resolved to <= 0')
        return (v / v_ref) ** 2 * (float(f_GHz) / float(f_ref_GHz))

    # -- the threshold-voltage lever ---------------------------------------------------
    def clock_gain(self, V=None):
        V = self.vdd if V is None else float(V)
        base = self._k * self._ion(V, shift=False) / V
        return self.frequency(V) / base - 1.0

    @property
    def leakage_multiplier(self):
        """``10**(dVt / SS)`` with the swing simulated at ``T_K`` -- see ``IRDSVFModel``."""
        return 10.0 ** (self.vt_shift_mV / self.ss_mV_dec)

    def cooling_K_to_offset(self, local_doubling_K):
        if self.vt_shift_mV <= 0:
            return 0.0
        return math.log2(self.leakage_multiplier) * float(local_doubling_K)

    # -- identification ----------------------------------------------------------------
    #: What clock_search stamps as the voltage source. IRDS models are identified by
    #: (year, anchor); this one by the card and the temperature it was simulated at.
    @property
    def source_tag(self):
        return 'spice:{}:{:.0f}K'.format(self.label.split()[0].lower(), self.T_K)

    year = 'spice'
    anchor = 'card'

    def __repr__(self):
        a = ('alpha_fit {:.2f}'.format(self.alpha_fit) if self.alpha_fit is not None
             else 'alpha_fit n/a')
        return ('<DeviceVFModel {} @ {:.0f} K, Vdd {:.2f} V, Vt {:.3f} V, SS {:.1f} mV/dec, '
                'anchor {:.2f} GHz @ {:.2f} V, {}, f_max {:.3f} GHz @ {:.3f} V UNCALIBRATED>'
                .format(self.label, self.T_K, self.vdd, self.vt, self.ss_mV_dec, self.f_anchor,
                        self.vdd, a, self.f_max, self.v_max))


def load_device_vf(path=None, T_K=300.0, f_anchor_GHz=DEFAULT_F_ANCHOR_GHZ, **kw):
    """A :class:`DeviceVFModel` from the recorded sweep, at the tabulated temperature nearest ``T_K``.

    Reads ``docs/evidence/device_vt_vf_asap7.json`` (``examples/device_vt_vf_spice.py``). The
    threshold and swing come from the same file's linear-regime extraction at that temperature,
    so the lever's cost and the curve's shape are at one operating point rather than two.
    """
    path = path or os.path.join(repo_root(), DEVICE_VF_EVIDENCE)
    with open(path) as f:
        ev = json.load(f)
    rows = ev['idsat']['by_T']
    row = min(rows, key=lambda r: abs(r['T_K'] - T_K))
    vt_row = min(ev['vt'], key=lambda r: abs(r['T_K'] - row['T_K']))
    m = DeviceVFModel(ev['idsat']['V'], row['I_on_A_per_fin'], vdd=ev['criteria']['vdd_V'],
                      f_anchor_GHz=f_anchor_GHz, vt=vt_row['vt_sat_V'],
                      ss_mV_dec=vt_row['ss_lin_mV_dec'], T_K=row['T_K'],
                      label='ASAP7 {}'.format(ev['card']['device']), **kw)
    m.source_meta = {'path': path, 'T_K_requested': float(T_K), 'T_K_used': row['T_K'],
                     'toolchain': ev.get('toolchain')}
    return m
