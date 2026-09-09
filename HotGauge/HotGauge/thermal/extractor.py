"""The extractor's cooling flux as a function of its OWN temperature -- where ``dt_max`` comes from.

Why this exists (§P0.19)
------------------------
Until now the cooler's temperature lift was a scalar, ``MRParams.dt_max_K`` = 45 K, copied from
Draft_5's Yb:YLF bench and capping how far the planner may pull a *block*. Nothing in the model
made the extractor's cooling power depend on how cold the extractor itself had become, which is
the physics that actually limits the lift -- and the coverage ladder (§P0.18.2) showed the
consequence: at 2.60 W/mm² the array pulled 12 W more than the die dissipated, refrigerating the
heat sink, because nothing stopped it.

This module derives the cooling flux from the extractor's constitutive parameters, per platform
(v91 Chapter 8), as a function of extractor temperature ``T_ext``. It is the volumetric route the
book's eq. (8.3) takes in areal form -- concentration (or carrier density) x per-emitter rate x
photon energy -- made explicit and given its temperature dependence:

* **absorption of the red-tail pump** follows an Urbach edge, ``sigma_a(E_p, T) = sigma_peak
  exp(-(E_edge - E_p) / E_U(T))`` (v91 eq. 9.4 for semiconductors; the same rule for the dye's
  vibronic tail), and the pump *by construction* sits in that tail;
* **emission** follows from absorption by the McCumber / Kennard-Stepanov relation, v91 eq.
  (5.19), which is what makes the mean fluorescence energy and its temperature drift a derived
  quantity rather than a table entry;
* **cooling per absorbed photon** is v91 eq. (1.5)/(4.15): escaped fluorescence energy minus
  absorbed pump energy, with the parasitic channels -- background absorption of the host,
  non-radiative decay, imperfect escape -- charged explicitly (the ``eta_abs = alpha_dye /
  (alpha_dye + alpha_b)`` split of v91 Table 1.1).

The result is ``cooling_density_W_per_mm2(T_ext)``: the most heat the film can extract per unit
footprint at that temperature (saturation-limited for the dye, Auger-limited at the optimum
carrier density for the semiconductor). It **falls as the extractor cools**, because the pump
absorption in the tail freezes out and the anti-Stokes shift shrinks, and crosses zero at
``T_min``. Fed to the planner as a per-tile cap evaluated at the tile's solved temperature, the
sustainable lift is then an *output* of the coupled solve, not an input.

`[!]` What is anchored and what is a placeholder
------------------------------------------------
Anchored on v91: the dye design point (§8.3.2-8.3.3: 10^-2 M, 1-10 um film, Purcell rate 1e9/s,
IQE 0.99, lambda_p >= 680 nm, mean fluorescence 605 nm; Table 8.1's per-photon efficiency; the
10^3-10^4 W/mm^2 of (8.4)) and the GaAs 300 K benchmark (Table 9.2 and eqs. 9.5-9.7: A, B, C,
alpha at the edge and at 890 nm, lambda_p 890, lambda_f 860, N_opt 5.7e17, 80 W/mm^3).

Placeholders, flagged as device-team inputs because ``T_min`` depends on them most:

* the dye's **absorption-tail slope and how much of it is thermal**. A vibronic tail has a static
  (inhomogeneous) part and a thermal part, ``E_U(T)^2 = E_inh^2 + (c k T)^2``; a purely thermal
  tail freezes out by ~210 K at 680 nm, a purely static one never does. One measured absorption
  tail at two temperatures pins it. v98 supersedes this bracket: the transparency cap carries the temperature dependence and the tail enters as ``sigma`` (dye section).
* the host's **background absorption** ``alpha_b`` at the pump wavelength. v91 brackets it with an
  "Original" and a Kedenburg-et-al. baseline without printing the numbers; the two presets here
  are order-of-magnitude placeholders to be replaced from [53].
* the GaAs **Urbach energy's temperature law**: the 300 K value is derived from Table 9.2's two
  alphas (6.7 meV); its temperature dependence uses the standard phonon-assisted Urbach rule with
  a 36 meV phonon.

Nothing here is Yb:YLF. The validation anchors are the book's own tabulated numbers, the McCumber
and saturation identities, and the GaAs breakeven -- see ``test_extractor.py``.
"""
import math

import numpy as np

#: Physical constants (SI).
K_B_EV = 8.617333262e-5          # eV/K
H_EV_S = 4.135667696e-15         # eV s
C_M_S = 299792458.0
Q_E = 1.602176634e-19            # J/eV
N_A = 6.02214076e23


def ev_from_nm(lam_nm):
    return H_EV_S * C_M_S / (float(lam_nm) * 1e-9)


def nm_from_ev(E_eV):
    return H_EV_S * C_M_S / float(E_eV) * 1e9


def molar_to_per_cm3(M):
    """Molar concentration -> number density [cm^-3]."""
    return float(M) * N_A / 1000.0


# ---------------------------------------------------------------------------------------------
# The lineshape: an Urbach absorption edge, and its McCumber emission partner
# ---------------------------------------------------------------------------------------------

def urbach_energy_phonon(T_K, E_U_300_eV, phonon_eV=0.036):
    """Phonon-assisted Urbach rule, ``E_U = k T / sigma(T)``,
    ``sigma(T) = sigma_0 (2kT/hw) tanh(hw/2kT)``, with ``sigma_0`` fixed by the 300 K value.

    The standard form for a crystalline semiconductor edge (v91 eq. 9.4 gives the 300 K edge;
    this is how it moves). Tends to a constant at low T (zero-point) and to ``kT/sigma_0`` at
    high T.
    """
    def _s(T):
        x = phonon_eV / (2.0 * K_B_EV * T)
        return (1.0 / x) * math.tanh(x)
    sigma0 = (K_B_EV * 300.0 / float(E_U_300_eV)) / _s(300.0)
    return K_B_EV * float(T_K) / (sigma0 * _s(float(T_K)))


def urbach_energy_static_plus_thermal(T_K, E_inh_eV, E_U_300_eV):
    """Vibronic (dye) tail: a static inhomogeneous width in quadrature with a thermal part,
    ``E_U(T)^2 = E_inh^2 + (c kT)^2``, ``c`` fixed so the tail is ``E_U_300`` at 300 K.

    ``E_inh = 0`` is the purely thermal (hot-band) limit that freezes out on cooling;
    ``E_inh = E_U_300`` is a purely static tail that does not. Which one a real dye is closer to
    is a measurement (the tail at two temperatures), and it is the input ``T_min`` depends on
    most. Kept as a helper; the v98 dye model uses ``sigma`` (eq. 9.5) instead.
    """
    E_inh = float(E_inh_eV)
    E300 = float(E_U_300_eV)
    if E_inh > E300:
        raise ValueError('E_inh {:.4f} eV exceeds the 300 K tail width {:.4f} eV'.format(E_inh, E300))
    th300 = math.sqrt(max(E300 ** 2 - E_inh ** 2, 0.0))
    c = th300 / (K_B_EV * 300.0)
    return math.sqrt(E_inh ** 2 + (c * K_B_EV * float(T_K)) ** 2)


class UrbachMcCumberLineshape(object):
    """Absorption cross-section with a Gaussian core and an exponential (Urbach) red tail, and
    the emission cross-section that the McCumber relation (v91 eq. 5.19) implies from it.

    ``sigma_a(E) = sigma_peak * exp(-(E_peak - E)^2 / 2 w^2)``   for E >= E_edge (the core)
    ``sigma_a(E) = sigma_a(E_edge) * exp(-(E_edge - E) / E_U(T))`` for E < E_edge (the tail)

    ``sigma_e(E, T) = sigma_a(E, T) * exp((E_mc - E) / kT)``  -- absorption blue of the zero-phonon
    line, emission red of it, automatically. The mean fluorescence energy is the first moment of
    the emission *photon flux* spectrum, ``sigma_e(E) E^2`` in the free-space density of states.
    """

    def __init__(self, sigma_peak_cm2, E_peak_eV, width_eV, E_mc_eV, E_U_of_T, edge_offset_eV=None):
        self.sigma_peak = float(sigma_peak_cm2)
        self.E_peak = float(E_peak_eV)
        self.width = float(width_eV)
        self.E_mc = float(E_mc_eV)
        self._E_U = E_U_of_T
        # The tail takes over where the Gaussian core's slope equals the tail's: one
        # width below the peak by default.
        self.E_edge = self.E_peak - (float(edge_offset_eV) if edge_offset_eV is not None
                                     else self.width)

    def E_U(self, T_K):
        return float(self._E_U(T_K))

    def sigma_a(self, E_eV, T_K):
        E = np.asarray(E_eV, dtype=float)
        core = self.sigma_peak * np.exp(-0.5 * ((self.E_peak - E) / self.width) ** 2)
        s_edge = self.sigma_peak * math.exp(-0.5 * ((self.E_peak - self.E_edge) / self.width) ** 2)
        tail = s_edge * np.exp(-(self.E_edge - E) / self.E_U(T_K))
        return np.where(E >= self.E_edge, core, tail)

    def sigma_e(self, E_eV, T_K):
        """McCumber emission, on the THERMALISED core only.

        The relation (5.19) holds between thermalised manifolds. Applied to the Urbach tail it
        diverges on the red side whenever ``E_U > kT`` (the tail falls slower than the Boltzmann
        factor rises), which is a statement that the far tail is not a thermalised manifold --
        it is vibronic and inhomogeneous structure. So emission is taken from the core and cut
        at the edge; the tail enters the *absorption* side, where it belongs.
        """
        E = np.asarray(E_eV, dtype=float)
        core = self.sigma_peak * np.exp(-0.5 * ((self.E_peak - E) / self.width) ** 2)
        return np.where(E >= self.E_edge, core, 0.0) * np.exp((self.E_mc - E) / (K_B_EV * float(T_K)))

    def mean_emission_eV(self, T_K, n=4000):
        """Mean photon energy of the emitted spectrum at ``T``: the ``omega_f`` of (1.6)."""
        E = np.linspace(self.E_edge, self.E_peak + 0.6, n)
        w = self.sigma_e(E, T_K) * E ** 2
        return float(np.sum(w * E) / np.sum(w))


# ---------------------------------------------------------------------------------------------
# The molecular-dispersion platform (R101 / R640-SMILES in a thin film), v100 §8.3.3-8.3.4
# (`[!]` v100 (9 Sep 2026) supersedes v98: same physics and the same Table 8.1 / 8.2 / 1.1 numbers
# for R640 and Cr:LiSAF; equations renumbered (eta_cool 8.6, p_max 8.8, d_min 8.9, Strickler-Berg
# 8.10, ladder score 8.11); Table 1.1 gains the NIR-cyanine and J-aggregate rows below; §1.18 and
# §10.9 add the architecture design points the evolution ladder rests on.)
# ---------------------------------------------------------------------------------------------
#
# `[!]` REBUILT 8 September 2026 on v98's volumetric route (eqs. 8.4-8.7, 8.9; Table 1.1). The
# v91-based first cut let every chromophore cycle at the Purcell rate and reproduced v91's eq.
# 8.4 (10^3-10^4 W/mm^2 for a bulk film) -- a figure v98 itself withdraws: "not reachable in a
# bulk medium at any intensity, because stimulated emission at w_p shuts the pump off long
# before the fluorescence lifetime is the limit". The cap is the TRANSPARENCY limit (5.7),
#
#     x_max = [1 + exp((E_00 - E_p) / kT)]^-1 ,
#
# the largest excited fraction the pump can sustain against its own stimulated emission, set by
# how many kT the pump sits below the zero line. It is a Boltzmann population ratio between the
# absorption and emission cross-sections at w_p (McCumber), so it is thermal BY CONSTRUCTION
# and independent of how the absorption tail is broadened. That is what closes the T_min
# question without a measurement: the capability's collapse on cooling is carried by x_max, and
# the tail steepness sigma and the host loss move only the point where net cooling vanishes,
# which sits where the capability is already negligible.

#: Boltzmann/Urbach tail steepness of the dye absorption beyond the 600 nm anchor (v98 eq. 9.5,
#: E_U = kT/sigma). 1.0 is the pure Boltzmann limit of a thermalised vibronic manifold, the book's
#: design input; 0.26 is the measured Cr:LiSAF disorder tail (§8.1.2), the shallow end of the
#: bracket. v98 names the measurement of epsilon beyond 620 nm on high-purity R640 as the priority
#: experiment; until then sigma is the sensitivity axis.
DYE_SIGMA_BOOK = 1.0
DYE_SIGMA_DISORDER = 0.26

#: Host background absorption at the pump [cm^-1]. The Kedenburg-ethanol value implied by v98
#: Table 8.1's own rows (eta_cool at 640/651/680 nm against alpha_r) is 0.0024 +- 0.0002 cm^-1 and
#: flat over 640-680 nm; 'original' keeps v91 Fig. 9.9's higher historical baseline as the
#: pessimistic end.
DYE_BACKGROUND_CM = {'kedenburg': 0.0024, 'original': 0.05}

#: R101/R640 spectroscopy v98 anchors on (§8.3.3, §9.3.2): the molar extinction at the 600 nm
#: anchor, the zero line, the lifetime, and the mean fluorescence per concentration and per
#: photonic setting (the blue-edge value is rung 3 of the ladder, Purcell-selected emission).
DYE_EPS_ANCHOR = 4290.0          # L mol^-1 cm^-1 at 600 nm
DYE_LAMBDA_ANCHOR_NM = 600.0
DYE_LAMBDA_00_NM = 588.0
DYE_TAU_S = 4.3e-9
DYE_LAMBDA_F_NM = {'1e-2': 618.0, '1e-1': 630.0, 'blue-edge': 590.0}

#: v98 Table 8.2, the photonic ladder: cumulative rungs from the bulk film to the Tier-I design
#: point (which is also the R640-SMILES row of Table 1.1). Every rung is a DyeExtractor preset.
DYE_LADDER = {
    0: dict(N_t_M=1e-2, T_design_K=300.0, lambda_p_nm=651.0, lambda_f_nm=618.0, purcell=1.0, film_um=5.0),
    1: dict(N_t_M=1e-1, T_design_K=300.0, lambda_p_nm=651.0, lambda_f_nm=630.0, purcell=1.0, film_um=5.0),
    2: dict(N_t_M=1e-1, T_design_K=400.0, lambda_p_nm=651.0, lambda_f_nm=630.0, purcell=1.0, film_um=5.0),
    3: dict(N_t_M=1e-1, T_design_K=400.0, lambda_p_nm=651.0, lambda_f_nm=590.0, purcell=1.0, film_um=5.0),
    4: dict(N_t_M=1e-1, T_design_K=400.0, lambda_p_nm=651.0, lambda_f_nm=590.0, purcell=30.0, film_um=5.0),
    5: dict(N_t_M=1e-1, T_design_K=400.0, lambda_p_nm=651.0, lambda_f_nm=590.0, purcell=30.0, film_um=20.0),
    6: dict(N_t_M=1e-1, T_design_K=400.0, lambda_p_nm=651.0, lambda_f_nm=590.0, purcell=100.0, film_um=50.0),
    7: dict(N_t_M=1e-1, T_design_K=600.0, lambda_p_nm=700.0, lambda_f_nm=590.0, purcell=100.0, film_um=50.0),
}


def iqe_under_purcell(F_P, iqe0):
    """v100 eq. (8.4): the Purcell factor acts on the radiative rate alone, so
    IQE(F_P) = F_P iqe0 / (F_P iqe0 + 1 - iqe0). 0.2 -> 0.71, 0.88, 0.96 at F_P = 10, 30, 100."""
    F_P, iqe0 = float(F_P), float(iqe0)
    return F_P * iqe0 / (F_P * iqe0 + 1.0 - iqe0)


#: v100 Table 1.1's two organic rows beyond R640 (9 Sep 2026). Both are evaluated with the book's
#: eta_abs -> 1 and eta_EQE = 1 (before the IQE(F_P) rule for the cyanine), so like every Table 1.1
#: figure they are ceilings. Neither is the target device; they are the cascade's other stages.
#:   nir-cyanine  -- 980 nm-pumped tricarbocyanine, 10^-1 M isolated, 400 K, pump 200 meV below the
#:                   zero line (x_max 3e-3), IQE0 = 0.2 lifted to 0.96 by F_P = 100, tau 0.6 ns,
#:                   50 um: 1.7e5 W/mm^3, 8e3 W/mm^2, eta_cool 13 % at eta_q 18 % -- the R640 density
#:                   at a third of the circulated pump, with fluorescence on a GaAs LPC.
#:   j-aggregate  -- silica-TDBC superradiant J-aggregate, 10^20 cm^-3, tau 234 ps, F_P = 10 on top
#:                   of the superradiant rate, 400 K, pump 60 meV into the hot band of the 590 nm
#:                   J-band (McCumber x_max 0.15, annihilation-capped x ~ 0.02), 1 um: ~1e6 W/mm^3,
#:                   ~1e3 W/mm^2 at eta_q 3 % -- the dense, bluest, terminal stage of a cascade.
TABLE_1_1_ORGANIC = {
    'nir-cyanine': dict(N_t_M=1e-1, T_design_K=400.0, lambda_p_nm=980.0, lambda_f_nm=833.0,
                        lambda_00_nm=nm_from_ev(ev_from_nm(980.0) + 0.200), purcell=100.0,
                        film_um=50.0, tau_s=0.6e-9, iqe0=0.2, eta_abs_fixed=1.0,
                        family='NIR tricarbocyanine', platform='molecular_nir_cyanine'),
    'j-aggregate': dict(N_t_M=1e20 / 6.02214076e20, T_design_K=400.0,
                        lambda_p_nm=nm_from_ev(ev_from_nm(590.0) - 0.060),
                        lambda_f_nm=nm_from_ev(ev_from_nm(590.0) - 0.060) / 1.03,
                        lambda_00_nm=590.0, purcell=10.0, film_um=1.0, tau_s=234e-12, x_cap=0.02,
                        eta_abs_fixed=1.0, family='silica-TDBC J-aggregate',
                        platform='organic_solid_j_aggregate'),
}


class DyeExtractor(object):
    """R101/R640-class dye on the book's volumetric route (v100 §8.3.3: eqs. 8.6-8.8, ladder scored
    by 8.11; v98 numbered these 8.5, 8.7, 8.9 -- the physics did not move between v98 and v100).

    Per unit volume, at the transparency ceiling (pump far above saturation)::

        p_max(T) = n_t * x_max(T) * Gamma_tot * hbar w_p * eta_cool(T)      (v100 8.8)
        x_max(T) = [1 + exp((E_00 - E_p) / kT)]^-1                          (5.7)
        eta_cool  = eta_abs * eta_EQE * lambda_p / lambda_f - 1               (v100 8.6)
        eta_abs   = alpha_r / (alpha_r + alpha_b),  alpha_r = ln10 * C * eps(lambda_p, T)
        eps(E, T) = eps(E_0) exp[sigma (E - E_0) / kT]                        (9.5)
        Gamma_tot = F_P / tau, or (F_P iqe0 + 1 - iqe0) / tau for a low-IQE emitter (v100 8.4)

    and ``Pcool/A = p_max d`` (v100 §8.3.3). ``T`` is the extractor's own temperature. ``T_design_K`` is
    only a label for the rung the preset came from; the curve is evaluated wherever the tile is.
    Reproduces v98 Table 8.1 to the printed digit and Table 8.2's rungs (tests).
    """

    platform = 'sin_encapsulated_dye'

    def __init__(self, N_t_M=1e-1, lambda_p_nm=651.0, lambda_f_nm=590.0, purcell=100.0,
                 film_um=50.0, T_design_K=400.0, eta_EQE=1.0, sigma=DYE_SIGMA_BOOK,
                 background='kedenburg', alpha_b_cm=None, tau_s=DYE_TAU_S,
                 eps_anchor=DYE_EPS_ANCHOR, lambda_anchor_nm=DYE_LAMBDA_ANCHOR_NM,
                 lambda_00_nm=DYE_LAMBDA_00_NM, rung=None, label=None,
                 iqe0=None, x_cap=None, eta_abs_fixed=None, platform=None, family='R640-SMILES'):
        # v100 additions (9 Sep 2026), for the two organic rows v100 adds to Table 1.1:
        #   iqe0          bare internal quantum yield of a low-IQE emitter. The Purcell factor acts
        #                 on the RADIATIVE rate only (v100 eq. 8.4): IQE(F_P) = F_P iqe0 /
        #                 (F_P iqe0 + 1 - iqe0), and the cycling rate is (F_P iqe0 + 1 - iqe0)/tau,
        #                 not F_P/tau. With iqe0 set, eta_EQE defaults to IQE(F_P).
        #   x_cap         an excited-fraction cap below the McCumber one -- exciton-exciton
        #                 annihilation in a J-aggregate (v100 §8.3.6, x ~ 0.02).
        #   eta_abs_fixed the book's eta_abs -> 1 assumption for rows whose tail is not the R640
        #                 tail this class anchors on (low-alpha_b host, fully absorbed pump).
        self.iqe0 = None if iqe0 is None else float(iqe0)
        self.x_cap = None if x_cap is None else float(x_cap)
        self.eta_abs_fixed = None if eta_abs_fixed is None else float(eta_abs_fixed)
        if platform is not None:
            self.platform = platform
        self.family = family
        self.N_t_M = float(N_t_M)
        self.N_t = molar_to_per_cm3(N_t_M)                    # cm^-3
        self.lambda_p = float(lambda_p_nm)
        self.E_p = ev_from_nm(lambda_p_nm)
        self.lambda_f = float(lambda_f_nm)
        self.E_f = ev_from_nm(lambda_f_nm)
        self.purcell = float(purcell)
        self.film_um = float(film_um)
        self.T_design = float(T_design_K)
        self.eta_EQE = (float(eta_EQE) if self.iqe0 is None
                        else iqe_under_purcell(float(purcell), self.iqe0) * float(eta_EQE))
        self.sigma = float(sigma)
        self.background = background
        self.alpha_b = float(alpha_b_cm if alpha_b_cm is not None else DYE_BACKGROUND_CM[background])
        self.tau = float(tau_s)
        self.eps_anchor = float(eps_anchor)
        self.E_anchor = ev_from_nm(lambda_anchor_nm)
        self.E_00 = ev_from_nm(lambda_00_nm)
        self.rung = rung
        self.label = label or ('{} {:.0e} M, {:.0f} nm pump, lambda_f {:.0f} nm, F_P {:.0f}, '
                               '{:.0f} um{}'.format(self.family, self.N_t_M, self.lambda_p, self.lambda_f,
                                                    self.purcell, self.film_um,
                                                    '' if rung is None else ' (rung {})'.format(rung)))

    @classmethod
    def from_rung(cls, rung, **kw):
        """A Table 8.2 rung as a preset (0 = bulk film, 2 = the near-term experimental point,
        6 = the Tier-I design point = Table 1.1's R640-SMILES row, 7 = the 600 K tile)."""
        args = dict(DYE_LADDER[int(rung)])
        args.update(kw)
        return cls(rung=int(rung), **args)

    # -- spectroscopy ------------------------------------------------------------------------
    def epsilon(self, T_K, lambda_nm=None):
        """Molar extinction at the pump (or ``lambda_nm``) from the anchored Boltzmann tail (9.5)."""
        E = self.E_p if lambda_nm is None else ev_from_nm(lambda_nm)
        if E >= self.E_anchor:
            raise ValueError('the tail model applies red of the {:.0f} nm anchor only'
                             .format(nm_from_ev(self.E_anchor)))
        return self.eps_anchor * math.exp(self.sigma * (E - self.E_anchor) / (K_B_EV * float(T_K)))

    def alpha_r(self, T_K):
        """Dye absorption coefficient at the pump [cm^-1]: ln10 * C * eps."""
        return math.log(10.0) * self.N_t_M * self.epsilon(T_K)

    def eta_abs(self, T_K):
        if self.eta_abs_fixed is not None:
            return self.eta_abs_fixed
        a = self.alpha_r(T_K)
        return a / (a + self.alpha_b)

    def eta_q(self):
        """Quantum-defect ceiling: lambda_p / lambda_f - 1 (v100 Table 8.3)."""
        return self.lambda_p / self.lambda_f - 1.0

    def eta_cool(self, T_K):
        """Realised per-absorbed-photon efficiency (v100 eq. 8.6; v98 8.5) at temperature ``T``."""
        return self.eta_abs(T_K) * self.eta_EQE * (1.0 + self.eta_q()) - 1.0

    def x_max(self, T_K):
        """Transparency ceiling on the excited fraction (5.7), or the annihilation cap if lower."""
        x = 1.0 / (1.0 + math.exp((self.E_00 - self.E_p) / (K_B_EV * float(T_K))))
        return x if self.x_cap is None else min(x, self.x_cap)

    def gamma_tot(self):
        """Cycling rate [s^-1]: F_P / tau, or (F_P iqe0 + 1 - iqe0) / tau for a low-IQE emitter
        (v100 eq. 8.4 -- the Purcell factor acts on the radiative rate only)."""
        if self.iqe0 is None:
            return self.purcell / self.tau
        return (self.purcell * self.iqe0 + 1.0 - self.iqe0) / self.tau

    def saturation_intensity_W_per_mm2(self, T_K):
        """I_sat = hbar w_p / (sigma_a tau) with sigma_a = alpha_r / n_t, per (8.4)."""
        sigma_a_cm2 = self.alpha_r(T_K) / self.N_t
        return (self.E_p * Q_E) / (sigma_a_cm2 * 1e-4 * self.tau / self.purcell) / 1e6

    # -- the ledger ---------------------------------------------------------------------------
    def cooling_per_volume_W_per_mm3(self, T_K):
        """p_max (v100 eq. 8.8; v98 8.7) at extractor temperature ``T`` [W/mm^3]; negative = heating."""
        if not (float(T_K) > 50.0):
            return 0.0
        n_m3 = self.N_t * 1e6
        return (n_m3 * self.x_max(T_K) * self.gamma_tot() * self.E_p * Q_E
                * self.eta_cool(T_K)) * 1e-9                           # W/m^3 -> W/mm^3

    def cooling_density_W_per_mm2(self, T_K):
        """Areal cooling flux ``Pcool/A = p_max d`` (v100 §8.3.3, after eq. 8.8; v98 8.9)."""
        if not (float(T_K) > 50.0):
            return 0.0
        return self.cooling_per_volume_W_per_mm3(T_K) * (self.film_um * 1e-3)

    def pump_flux_W_per_mm2(self, T_K):
        """The pump flux the network must deliver at the ceiling: Pcool/(A eta_cool) (Table 8.2)."""
        h = self.cooling_density_W_per_mm2(T_K)
        e = self.eta_cool(T_K)
        return h / e if (h > 0 and e > 0) else float('inf')

    def eta_asf(self, T_K):
        """Net cooling per unit pump power absorbed: eta_cool, when positive."""
        return max(self.eta_cool(T_K), 0.0)

    def required_eta_EQE(self, T_K):
        """The EQE at which net cooling just appears: 1 / (eta_abs (1 + eta_q))."""
        return 1.0 / (self.eta_abs(T_K) * (1.0 + self.eta_q()))

    def t_min_K(self, lo=80.0, hi=700.0):
        """Where net cooling vanishes (eta_cool -> 0). `[!]` The capability is already tiny there:
        quote ``h(T)`` at the tile temperatures in question, not this alone."""
        return _zero_crossing(self.cooling_density_W_per_mm2, lo, hi)

    def describe(self):
        return {'platform': self.platform, 'label': self.label, 'rung': self.rung,
                'N_t_M': self.N_t_M, 'lambda_p_nm': self.lambda_p, 'lambda_f_nm': self.lambda_f,
                'purcell': self.purcell, 'film_um': self.film_um, 'T_design_K': self.T_design,
                'eta_EQE': self.eta_EQE, 'sigma': self.sigma, 'background': self.background,
                'alpha_b_cm': self.alpha_b, 'tau_s': self.tau, 'iqe0': self.iqe0,
                'x_cap': self.x_cap, 'eta_abs_fixed': self.eta_abs_fixed,
                'gamma_tot_per_s': self.gamma_tot(),
                'p_at_design_W_per_mm3': self.cooling_per_volume_W_per_mm3(self.T_design),
                'eta_q': self.eta_q(),
                'x_max_at_design': self.x_max(self.T_design),
                'h_at_design_W_per_mm2': self.cooling_density_W_per_mm2(self.T_design),
                'h_300K_W_per_mm2': self.cooling_density_W_per_mm2(300.0),
                'h_263K_W_per_mm2': self.cooling_density_W_per_mm2(263.0),
                'T_min_K': self.t_min_K()}


# ---------------------------------------------------------------------------------------------
# The direct-bandgap-semiconductor platform (GaAs / GaInP DH), v91 §8.2.1, §9.3.2-9.3.3
# ---------------------------------------------------------------------------------------------

#: GaAs Varshni parameters: E_g(T) = E_g0 - a T^2 / (T + b).
GAAS_VARSHNI = {'E_g0_eV': 1.519, 'a_eV_per_K': 5.405e-4, 'b_K': 204.0}


def gaas_bandgap_eV(T_K, p=GAAS_VARSHNI):
    T = float(T_K)
    return p['E_g0_eV'] - p['a_eV_per_K'] * T * T / (T + p['b_K'])


class SemiconductorExtractor(object):
    """GaAs-class extractor at v91's Table 9.2 benchmark, with the A, B, C balance of eq. (8.1).

    Per unit volume, at carrier density ``N``. Recombination is ``A N + B N^2 + C N^3``, but only
    the ESCAPED fraction ``eta_e`` of the radiative part leaves the film; the rest is reabsorbed
    and regenerates carriers (photon recycling, v91 §5.7), so the pump has to replenish
    ``G_pump = A N + eta_e B N^2 + C N^3`` and no more. The ledger is then::

        p_cool(N, T) = eta_e B N^2 hbar w_f(T) - hbar w_p G_pump (1 + (alpha_b + sigma_fca N) / alpha(w_p, T))

    i.e. escaped radiative energy minus the pump energy that produced the carriers it came from,
    with the host's background and free-carrier absorption charged in proportion to how weakly
    the Urbach tail absorbs the pump. This is the balance behind the book's (9.5)-(9.7): with
    Table 9.2's inputs it puts the optimum at 5.8e17 cm^-3 and ~75 W/mm^3 against the table's
    5.7e17 and 80. Maximised over ``N`` (Auger caps it) and multiplied by the
    film thickness it gives the areal cooling flux. Temperature enters through the Varshni gap
    (the fixed-wavelength pump sinks deeper into the tail as the gap widens on cooling), the
    Urbach energy, ``B ~ T^-3/2`` and the Auger law v91 quotes, ``C(T) ~ exp(-2.4(300/T - 1))``.

    ``retune_pump=True`` keeps the pump at a fixed depth below the *current* gap instead of at a
    fixed wavelength -- the book's per-temperature ``w_p*`` (§9.2 Level 1). The two are the
    hardware question "does the laser follow the extractor down?", and both are reported.
    """

    platform = 'gaas_gainp_epitaxy'

    def __init__(self, A_per_s=5e4, B_cm3_s=4e-10, C_cm6_s=4e-30, alpha_edge_cm=1e4,
                 alpha_pump_300_cm=100.0, lambda_p_nm=890.0, lambda_f_300_nm=860.0,
                 eta_e=0.25, film_um=1.0, alpha_b_cm=0.1, sigma_fca_cm2=0.0, phonon_eV=0.036,
                 purcell=1.0, retune_pump=False, label=None):
        self.A = float(A_per_s)
        # Photonic enhancement of the radiative rate (v91 §9.3.3: 'the cubic gain in eta_e B from
        # photonic enhancement'). 1.0 is the bulk benchmark of Table 9.2; the platform's
        # 10^3-10^4 W/mm^2 (Table 8.2) needs eta_e B raised ~20x over it at 1 um.
        self.purcell = float(purcell)
        self.B300 = float(B_cm3_s) * self.purcell
        self.C300 = float(C_cm6_s)
        self.alpha_edge = float(alpha_edge_cm)
        self.lambda_p = float(lambda_p_nm)
        self.E_p300 = ev_from_nm(lambda_p_nm)
        self.eta_e = float(eta_e)
        self.film_um = float(film_um)
        self.alpha_b = float(alpha_b_cm)
        self.sigma_fca = float(sigma_fca_cm2)
        self.phonon = float(phonon_eV)
        self.retune = bool(retune_pump)
        Eg300 = gaas_bandgap_eV(300.0)
        # Urbach energy at 300 K from the table's two alphas: the edge value and the 890 nm value.
        self.E_U_300 = (Eg300 - self.E_p300) / math.log(self.alpha_edge / float(alpha_pump_300_cm))
        self.tail_depth_300 = Eg300 - self.E_p300
        # Mean fluorescence anchored on the table's VRS-derived 860 nm at 300 K: E_f = E_g + delta,
        # with delta scaled with kT (the VRS spectrum's mean sits ~kT above the gap).
        self.delta_300 = ev_from_nm(lambda_f_300_nm) - Eg300
        self.label = label or 'GaAs/GaInP DH, pump {:.0f} nm{}'.format(
            self.lambda_p, ' (retuned)' if self.retune else '')

    # -- temperature laws -----------------------------------------------------------------
    def E_g(self, T_K):
        return gaas_bandgap_eV(T_K)

    def E_U(self, T_K):
        return urbach_energy_phonon(T_K, self.E_U_300, self.phonon)

    def E_pump(self, T_K):
        return (self.E_g(T_K) - self.tail_depth_300) if self.retune else self.E_p300

    def B(self, T_K):
        return self.B300 * (300.0 / float(T_K)) ** 1.5

    def C(self, T_K):
        return self.C300 * math.exp(-2.4 * (300.0 / float(T_K) - 1.0))

    def mean_fluorescence_eV(self, T_K):
        return self.E_g(T_K) + self.delta_300 * float(T_K) / 300.0

    def alpha_pump(self, T_K):
        """Urbach-tail absorption of the pump [cm^-1], v91 eq. (9.4)."""
        return self.alpha_edge * math.exp((self.E_pump(T_K) - self.E_g(T_K)) / self.E_U(T_K))

    def eta_c(self, T_K):
        return self.mean_fluorescence_eV(T_K) / self.E_pump(T_K) - 1.0

    # -- the ledger, per unit volume ---------------------------------------------------------
    def pump_generation(self, N_cm3, T_K):
        """Carrier generation the PUMP must supply at density ``N`` [cm^-3 s^-1]: recombination
        less the recycled (non-escaped) radiative part."""
        N = float(N_cm3)
        return self.A * N + self.eta_e * self.B(T_K) * N * N + self.C(T_K) * N ** 3

    def parasitic_ratio(self, N_cm3, T_K):
        """Background-plus-free-carrier absorption over the tail absorption of the pump."""
        return (self.alpha_b + self.sigma_fca * float(N_cm3)) / self.alpha_pump(T_K)

    def cooling_per_volume_W_per_mm3(self, N_cm3, T_K):
        N = float(N_cm3)
        esc = self.eta_e * self.B(T_K) * N * N * self.mean_fluorescence_eV(T_K) * Q_E
        absorbed = (self.E_pump(T_K) * Q_E * self.pump_generation(N, T_K)
                    * (1.0 + self.parasitic_ratio(N, T_K)))
        return (esc - absorbed) * 1e-3                                        # W/cm^3 -> W/mm^3

    def optimum(self, T_K, n=400):
        """(N_opt [cm^-3], p_cool^opt [W/mm^3]) by scanning log N; the book's (9.7) is the check."""
        Ns = np.logspace(15, 19.5, n)
        p = np.array([self.cooling_per_volume_W_per_mm3(N, T_K) for N in Ns])
        k = int(np.argmax(p))
        return float(Ns[k]), float(p[k])

    def book_closed_form(self, T_K=300.0):
        """v98 eqs. (9.6)-(9.7) with the same inputs, for the self-consistency test:
        ``p_opt = (4/27) eta_q~^3 (eta_e B)^3 / C'^2 * hbar w_p`` (A -> 0), ``A_0 = eta_q~^2 (eta_e B)^2
        / (4 C')``, cooling requires ``A < A_0``; ``eta_q~ = eta_q - alpha_b/alpha``. (v91's draft
        carried 4/9 and A < 4/3 A_0; v98 corrects both, as the §P0.19 check found.)"""
        eta_q = self.eta_c(T_K)
        eta_qt = eta_q - self.alpha_b / self.alpha_pump(T_K)
        B, C = self.eta_e * self.B(T_K), self.C(T_K)
        A0 = eta_qt ** 2 * B ** 2 / (4.0 * C)
        cools = self.A < A0
        N_opt = (eta_qt * B / (3.0 * C)) * (1.0 + math.sqrt(max(1.0 - 3.0 * self.A / (4.0 * A0), 0.0)))
        p_opt = (4.0 / 27.0) * eta_qt ** 3 * B ** 3 / C ** 2 * self.E_pump(T_K) * Q_E * 1e-3
        return {'A0_per_s': A0, 'cooling_possible': bool(cools), 'N_opt_cm3': N_opt,
                'p_opt_W_per_mm3': p_opt, 'eta_q_tilde': eta_qt}

    def cooling_density_W_per_mm2(self, T_K):
        """Areal cooling flux at the optimum carrier density, through the film thickness.

        Negative when no carrier density cools: the film heats at any pump level. Below 50 K
        the temperature laws are meaningless and the flux is reported as zero.
        """
        if not (float(T_K) > 50.0):
            return 0.0
        _, p = self.optimum(T_K)
        return p * (self.film_um * 1e-3)

    def eta_asf(self, T_K):
        if not (float(T_K) > 50.0):
            return 0.0
        N, p = self.optimum(T_K)
        absorbed = (self.E_pump(T_K) * Q_E * self.pump_generation(N, T_K)
                    * (1.0 + self.parasitic_ratio(N, T_K))) * 1e-3
        return p / absorbed if absorbed > 0 else 0.0

    def t_min_K(self, lo=80.0, hi=500.0):
        return _zero_crossing(self.cooling_density_W_per_mm2, lo, hi)

    def describe(self):
        return {'platform': self.platform, 'label': self.label, 'A_per_s': self.A,
                'B_cm3_s': self.B300, 'C_cm6_s': self.C300, 'alpha_edge_cm': self.alpha_edge,
                'E_U_300_eV': self.E_U_300, 'lambda_p_nm': self.lambda_p,
                'retune_pump': self.retune, 'eta_e': self.eta_e, 'purcell': self.purcell,
                'film_um': self.film_um,
                'alpha_b_cm': self.alpha_b, 'sigma_fca_cm2': self.sigma_fca,
                'h_300K_W_per_mm2': self.cooling_density_W_per_mm2(300.0),
                'T_min_K': self.t_min_K()}


# ---------------------------------------------------------------------------------------------
# The storage-zone material: Cr3+:LiSAF (v98 §8.1.2, Table 1.1, Table 8.4) -- decided 8 Sep 2026
# ---------------------------------------------------------------------------------------------
# The user's decision: the cold (storage / control) zone material is Cr:LiSAF, the hot zone the
# dye; Yb:YLF is not a zone material. And the DEFAULT cold plate is single-material -- a
# floorplan-matched dual-material tile arrangement is a per-architecture product, which defeats
# the architecture-agnostic premise; it is a flagged experiment for when the floorplan is itself
# a variable (Phase 2) or the array is integrated at die manufacture.

#: Cr3+:LiSAF numbers from v98 §8.1.2 (Silva et al. tail, 7.4 % Cr sweet spot) and Table 1.1.
CRLISAF = {'n_t_cm3': 1e21, 'tau_s': 67e-6, 'lambda_p_nm': 900.0, 'lambda_f_nm': 850.0,
           'lambda_mc_nm': 815.0, 'sigma_a_pump_cm2_290K': 4e-23, 'urbach_sigma': 0.26,
           'purcell_range': (30.0, 100.0), 'eta_EQE_demonstrated': (0.85, 0.95)}


class CrLiSAFExtractor(object):
    """Cr3+:LiSAF on the same volumetric route as the dye (v98 eqs. 8.7 / 8.9), for the storage zone.

    ``x_max = [1 + exp((E_mc - E_p)/kT)]^-1`` with the McCumber crossing at 815 nm (the measured
    emission implies it there, not at the peaks; §8.1.2), which gives the book's 4e-3 at 290 K
    for a 900 nm pump. The pump absorption follows the measured disorder tail, Urbach steepness
    sigma = 0.26, anchored at sigma_a(900 nm, 290 K) = 4e-23 cm^2 about the crossing. Quantum
    defect 900 on 850 nm = 5.9 %; with eta_EQE = 1 the ceiling is 20-80 W/mm^3 at F_P = 30-100
    (Table 1.1), i.e. 0.2-0.8 W/mm^2 per 10 um. `[!]` v98 Table 8.4: the platform "fails the
    breakeven test at its demonstrated IQE" (needs eta_EQE > 0.94; best crystals 0.85-0.95), so
    every areal figure scales with the realised eta_cool and is a ceiling at eta_EQE = 1.
    """

    platform = 'cr_lisaf'

    def __init__(self, purcell=30.0, film_um=10.0, eta_EQE=1.0, lambda_p_nm=None,
                 alpha_b_cm=1e-4, sigma=None, label=None):
        # alpha_b: high-purity crystal background; the resonant alpha_r is only 0.04 cm^-1 at
        # 290 K (4e-23 cm^2 x 1e21 cm^-3), so the background must sit two decades under it for
        # eta_abs to reach the ~0.995 that v98 Table 8.4's 'eta_EQE > 0.94' breakeven implies.
        c = CRLISAF
        self.n_t = float(c['n_t_cm3'])
        self.tau = float(c['tau_s'])
        self.purcell = float(purcell)
        self.film_um = float(film_um)
        self.eta_EQE = float(eta_EQE)
        self.lambda_p = float(lambda_p_nm if lambda_p_nm is not None else c['lambda_p_nm'])
        self.E_p = ev_from_nm(self.lambda_p)
        self.lambda_f = float(c['lambda_f_nm'])
        self.E_mc = ev_from_nm(c['lambda_mc_nm'])
        self.sigma = float(sigma if sigma is not None else c['urbach_sigma'])
        self.alpha_b = float(alpha_b_cm)
        # Urbach tail about the crossing, anchored on the 900 nm / 290 K measurement.
        E900 = ev_from_nm(c['lambda_p_nm'])
        self._sigma_a_focus = c['sigma_a_pump_cm2_290K'] / math.exp(
            self.sigma * (E900 - self.E_mc) / (K_B_EV * 290.0))
        self.label = label or 'Cr:LiSAF {:.0f} nm pump, F_P {:.0f}, {:.0f} um'.format(
            self.lambda_p, self.purcell, self.film_um)

    def sigma_a_pump(self, T_K):
        return self._sigma_a_focus * math.exp(self.sigma * (self.E_p - self.E_mc) / (K_B_EV * float(T_K)))

    def alpha_r(self, T_K):
        return self.sigma_a_pump(T_K) * self.n_t

    def eta_abs(self, T_K):
        a = self.alpha_r(T_K)
        return a / (a + self.alpha_b)

    def eta_q(self):
        return self.lambda_p / self.lambda_f - 1.0

    def eta_cool(self, T_K):
        return self.eta_abs(T_K) * self.eta_EQE * (1.0 + self.eta_q()) - 1.0

    def x_max(self, T_K):
        return 1.0 / (1.0 + math.exp((self.E_mc - self.E_p) / (K_B_EV * float(T_K))))

    def cooling_per_volume_W_per_mm3(self, T_K):
        if not (float(T_K) > 50.0):
            return 0.0
        return (self.n_t * 1e6 * self.x_max(T_K) * (self.purcell / self.tau) * self.E_p * Q_E
                * self.eta_cool(T_K)) * 1e-9

    def cooling_density_W_per_mm2(self, T_K):
        if not (float(T_K) > 50.0):
            return 0.0
        return self.cooling_per_volume_W_per_mm3(T_K) * (self.film_um * 1e-3)

    def eta_asf(self, T_K):
        return max(self.eta_cool(T_K), 0.0)

    def t_min_K(self, lo=80.0, hi=700.0):
        return _zero_crossing(self.cooling_density_W_per_mm2, lo, hi)

    def describe(self):
        return {'platform': self.platform, 'label': self.label, 'purcell': self.purcell,
                'film_um': self.film_um, 'eta_EQE': self.eta_EQE, 'lambda_p_nm': self.lambda_p,
                'lambda_f_nm': self.lambda_f, 'sigma': self.sigma, 'alpha_b_cm': self.alpha_b,
                'eta_q': self.eta_q(), 'x_max_290K': self.x_max(290.0),
                'p_290K_W_per_mm3': self.cooling_per_volume_W_per_mm3(290.0),
                'h_290K_W_per_mm2': self.cooling_density_W_per_mm2(290.0),
                'h_200K_W_per_mm2': self.cooling_density_W_per_mm2(200.0),
                'T_min_K': self.t_min_K()}


# ---------------------------------------------------------------------------------------------
# Dual-material tile arrangement -- a FLAG, off by default (decided 8 Sep 2026)
# ---------------------------------------------------------------------------------------------

#: The default cold plate is ONE material over the whole die. A cold-zone / hot-zone arrangement
#: must be laid out against the floorplan, i.e. designed per architecture with the chip vendor,
#: which defeats the architecture-agnostic premise of the product. It exists here so its impact
#: can be measured once the floorplan is a swept variable (Phase 2) or the array is integrated
#: at die manufacture; it is never the default.
ZONE_MODES = ('single', 'dual')
DEFAULT_ZONE_MODE = 'single'
DEFAULT_COLD_ZONE_PATTERN = r'^(L2|L3)'
DEFAULT_COLD_EXTRACTOR = 'cr-lisaf'


class DualZoneExtractor(object):
    """Two curves on one array: ``cold`` over the tiles named in ``cold_tiles``, ``hot`` elsewhere.

    ``cooling_density_W_per_mm2(T, tile=None)`` dispatches by tile; without a tile it reports the
    hot-zone curve (the material over the compute region, which is what a single number about
    the array should mean). The planner's per-tile cap (``extractor_tile_caps``) passes the tile.
    """

    platform = 'dual_zone'
    zoned = True

    def __init__(self, cold, hot, cold_tiles):
        self.cold, self.hot = cold, hot
        self.cold_tiles = set(cold_tiles)
        self.label = 'dual-zone: {} on {} cold tiles / {} elsewhere'.format(
            getattr(cold, 'label', 'cold'), len(self.cold_tiles), getattr(hot, 'label', 'hot'))

    def _for(self, tile):
        return self.cold if (tile is not None and tile in self.cold_tiles) else self.hot

    def cooling_density_W_per_mm2(self, T_K, tile=None):
        return self._for(tile).cooling_density_W_per_mm2(T_K)

    def eta_asf(self, T_K, tile=None):
        return self._for(tile).eta_asf(T_K)

    def t_min_K(self):
        return {'cold': self.cold.t_min_K(), 'hot': self.hot.t_min_K()}

    def describe(self):
        return {'platform': self.platform, 'label': self.label, 'n_cold_tiles': len(self.cold_tiles),
                'cold': self.cold.describe(), 'hot': self.hot.describe()}


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------

def _zero_crossing(f, lo, hi, n=85):
    """Highest temperature in [lo, hi] at which ``f`` crosses from <= 0 to > 0, by scan +
    bisection; ``None`` if ``f`` is positive throughout (never freezes out in range) and ``hi`` if
    it is never positive."""
    Ts = np.linspace(lo, hi, n)
    vals = [f(T) for T in Ts]
    if all(v > 0 for v in vals):
        return None
    if all(v <= 0 for v in vals):
        return float(hi)
    # last index where the value is <= 0 with a positive neighbour above it
    k = max(i for i in range(n - 1) if vals[i] <= 0 < vals[i + 1])
    a, b = float(Ts[k]), float(Ts[k + 1])
    for _ in range(50):
        m = 0.5 * (a + b)
        if f(m) > 0:
            b = m
        else:
            a = m
    return 0.5 * (a + b)


#: The photonic-enhancement design point that lifts the Table 9.2 bulk benchmark (0.07 W/mm^2 per
#: micron) to the platform's 10^5-10^6 W/mm^3 of v98 Table 1.1: escape 0.9, a 10x Purcell gain on
#: the radiative rate (the table's F_P(B) = 10), a 2 um film. Stated, not measured.
GAAS_ENHANCED = {'eta_e': 0.9, 'purcell': 10.0, 'film_um': 2.0}

EXTRACTORS = {
    # `dye` is the TARGET DEVICE going forward (8 Sep): v98 Table 1.1's R640-SMILES row, i.e.
    # rung 6 of the Table 8.2 ladder -- the Tier-I design point at 400 K.
    'dye': lambda **kw: DyeExtractor.from_rung(6, **kw),
    'dye-tier1': lambda **kw: DyeExtractor.from_rung(6, **kw),
    'dye-near': lambda **kw: DyeExtractor.from_rung(2, **kw),        # near-term experimental point
    'dye-bulk': lambda **kw: DyeExtractor.from_rung(0, **kw),
    'dye-600K': lambda **kw: DyeExtractor.from_rung(7, **kw),
    'dye-rung3': lambda **kw: DyeExtractor.from_rung(3, **kw),
    'dye-rung4': lambda **kw: DyeExtractor.from_rung(4, **kw),
    'nir-cyanine': lambda **kw: DyeExtractor(**dict(TABLE_1_1_ORGANIC['nir-cyanine'], **kw)),
    'j-aggregate': lambda **kw: DyeExtractor(**dict(TABLE_1_1_ORGANIC['j-aggregate'], **kw)),
    'cr-lisaf': lambda **kw: CrLiSAFExtractor(**kw),
    'gaas': lambda **kw: SemiconductorExtractor(**kw),
    'gaas-retuned': lambda **kw: SemiconductorExtractor(retune_pump=True, **kw),
    'gaas-enhanced': lambda **kw: SemiconductorExtractor(**dict(GAAS_ENHANCED, **kw)),
    'gaas-retuned-enhanced': lambda **kw: SemiconductorExtractor(retune_pump=True,
                                                                **dict(GAAS_ENHANCED, **kw)),
}


def make_extractor(name, **kw):
    if name not in EXTRACTORS:
        raise ValueError('unknown extractor {!r}; have {}'.format(name, sorted(EXTRACTORS)))
    return EXTRACTORS[name](**kw)


def exergy_bound_ok(P_abs_W, Q_c_W, P_f_W, T_h_K, T_0_K=295.0):
    """v91 eq. (1.13): escaped fluorescence exergy <= P_abs + Q_c (1 - T0/T_h)."""
    return P_f_W <= P_abs_W + Q_c_W * (1.0 - float(T_0_K) / float(T_h_K)) + 1e-9
