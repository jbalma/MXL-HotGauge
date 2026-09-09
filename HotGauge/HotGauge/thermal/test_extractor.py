"""Validation anchors for the extractor cooling-flux model (§P0.19).

None of these rests on Yb:YLF. The anchors are: the identities the model must satisfy (McCumber
reciprocity, saturation, the first-law ledger, the exergy bound), v91's own tabulated design
points (Table 8.1, eq. 8.4, Table 9.2 with eqs. 9.5-9.7), the GaAs breakeven, and the
qualitative structure of the book's feasibility maps (Figs. 9.9-9.10).
"""
import math

import numpy as np
import pytest

from HotGauge.thermal.extractor import (DyeExtractor, SemiconductorExtractor,
                                        UrbachMcCumberLineshape, urbach_energy_phonon,
                                        urbach_energy_static_plus_thermal, gaas_bandgap_eV,
                                        ev_from_nm, nm_from_ev, make_extractor, exergy_bound_ok,
                                        K_B_EV, DYE_LADDER, DYE_SIGMA_BOOK, CrLiSAFExtractor,
                                        DualZoneExtractor, CRLISAF, iqe_under_purcell,
                                        TABLE_1_1_ORGANIC)


# ---------------------------------------------------------------------------
# identities
# ---------------------------------------------------------------------------
def test_mccumber_puts_absorption_blue_of_emission():
    """v91 §5.8: the offset is built in, not added by hand."""
    line = UrbachMcCumberLineshape(1e-16, 2.15, 0.06, 2.10, lambda T: 0.05)
    E = np.linspace(1.7, 2.5, 2000)
    sa, se = line.sigma_a(E, 300.0), line.sigma_e(E, 300.0)
    mean_a = float(np.sum(sa * E) / np.sum(sa))
    mean_e = float(np.sum(se * E) / np.sum(se))
    assert mean_a > mean_e
    # exactly the McCumber ratio wherever both are defined
    k = (E >= line.E_edge)
    ratio = se[k] / sa[k]
    assert np.allclose(ratio, np.exp((line.E_mc - E[k]) / (K_B_EV * 300.0)))


def test_urbach_tail_is_exponential_below_the_edge_and_freezes_out_on_cooling():
    line = UrbachMcCumberLineshape(1e-16, 2.15, 0.06, 2.10,
                                   lambda T: urbach_energy_static_plus_thermal(T, 0.0, 0.05))
    E1, E2 = 1.85, 1.80
    r300 = float(line.sigma_a(E1, 300.0) / line.sigma_a(E2, 300.0))
    assert r300 == pytest.approx(math.exp(0.05 / 0.05), rel=1e-9)
    assert line.sigma_a(1.82, 200.0) < line.sigma_a(1.82, 300.0), 'hot-band absorption dies on cooling'


def test_urbach_phonon_rule_reproduces_its_300K_value_and_flattens_at_low_T():
    assert urbach_energy_phonon(300.0, 0.0067) == pytest.approx(0.0067, rel=1e-9)
    assert urbach_energy_phonon(200.0, 0.0067) < 0.0067
    assert urbach_energy_phonon(20.0, 0.0067) > 0.0


def test_static_plus_thermal_bracket_ends():
    assert urbach_energy_static_plus_thermal(300.0, 0.0, 0.05) == pytest.approx(0.05)
    assert urbach_energy_static_plus_thermal(150.0, 0.0, 0.05) == pytest.approx(0.025)
    assert urbach_energy_static_plus_thermal(150.0, 0.05, 0.05) == pytest.approx(0.05)
    with pytest.raises(ValueError):
        urbach_energy_static_plus_thermal(300.0, 0.06, 0.05)


def test_saturation_intensity_is_photon_energy_over_sigma_tau():
    d = DyeExtractor.from_rung(0)
    I = d.saturation_intensity_W_per_mm2(300.0)
    sigma_a = d.alpha_r(300.0) / d.N_t
    expect = (d.E_p * 1.602176634e-19) / (sigma_a * 1e-4 * d.tau) / 1e6
    assert I == pytest.approx(expect)
    assert d.saturation_intensity_W_per_mm2(250.0) > I, 'a frozen tail needs more pump to saturate'


def test_exergy_bound_1_13():
    # heat-derived part Carnot-bounded, pump-derived part at full exergy
    assert exergy_bound_ok(P_abs_W=10.0, Q_c_W=1.0, P_f_W=10.0 + 1.0 * (1 - 295.0 / 365.0), T_h_K=365.0)
    assert not exergy_bound_ok(P_abs_W=10.0, Q_c_W=1.0, P_f_W=11.0, T_h_K=365.0)


# ---------------------------------------------------------------------------
# the dye on v98's volumetric route: Tables 8.1, 8.2, 8.3, 1.1 and §8.3.5
# ---------------------------------------------------------------------------
V98_TABLE_8_1 = [
    # C [M], T [K], lambda_p, lambda_f, eps, alpha_r, eta_cool %, x_max, p_max [W/mm^3], P/A 5um
    (1e-2, 300.0, 640.0, 618.0, 29.0, 0.67, 3.2, 1.3e-3, 18.0, 0.09),
    (1e-2, 300.0, 651.0, 618.0, 8.2, 0.19, 4.0, 3.7e-4, 6.3, 0.03),
    (1e-2, 400.0, 651.0, 618.0, 39.0, 0.90, 5.1, 2.7e-3, 58.0, 0.29),
    (1e-2, 400.0, 680.0, 618.0, 3.7, 0.085, 7.0, 2.5e-4, 7.3, 0.04),
    (1e-1, 300.0, 651.0, 630.0, 8.2, 1.9, 3.2, 3.7e-4, 51.0, 0.26),
    (1e-1, 400.0, 651.0, 630.0, 39.0, 9.0, 3.3, 2.7e-3, 380.0, 1.9),
    (1e-1, 400.0, 680.0, 630.0, 3.7, 0.85, 7.6, 2.5e-4, 79.0, 0.40),
]


@pytest.mark.parametrize('row', V98_TABLE_8_1)
def test_dye_reproduces_v98_table_8_1(row):
    C, T, lp, lf, eps, ar, ec, xm, pm, pa = row
    d = DyeExtractor(N_t_M=C, lambda_p_nm=lp, lambda_f_nm=lf, purcell=1.0, film_um=5.0)
    assert d.epsilon(T) == pytest.approx(eps, rel=0.06)
    assert d.alpha_r(T) == pytest.approx(ar, rel=0.06)
    assert 100.0 * d.eta_cool(T) == pytest.approx(ec, abs=0.15)
    assert d.x_max(T) == pytest.approx(xm, rel=0.06)
    assert d.cooling_per_volume_W_per_mm3(T) == pytest.approx(pm, rel=0.08)
    assert d.cooling_density_W_per_mm2(T) == pytest.approx(pa, rel=0.12)


V98_TABLE_8_2 = {  # rung: eta_cool %, x_max, p_max, P/A, pump flux
    0: (3.9, 3.7e-4, 6.3, 0.03, 0.8), 1: (3.2, 3.7e-4, 51.0, 0.26, 8.0),
    2: (3.3, 2.7e-3, 380.0, 1.9, 57.0), 3: (10.3, 2.7e-3, 1.2e3, 5.9, 57.0),
    4: (10.3, 2.7e-3, 3.5e4, 180.0, 1.7e3), 5: (10.3, 2.7e-3, 3.5e4, 7e2, 6.9e3),
    6: (10.3, 2.7e-3, 1.2e5, 5.9e3, 5.7e4), 7: (18.5, 1.5e-3, 1.1e5, 5.4e3, 2.9e4),
}


@pytest.mark.parametrize('rung', sorted(V98_TABLE_8_2))
def test_dye_reproduces_the_photonic_ladder_table_8_2(rung):
    """Every rung is a preset; the Tier-I design point (rung 6) is Table 1.1's R640-SMILES row."""
    ec, xm, pm, pa, flux = V98_TABLE_8_2[rung]
    d = DyeExtractor.from_rung(rung)
    T = d.T_design
    assert 100.0 * d.eta_cool(T) == pytest.approx(ec, abs=0.4)
    assert d.x_max(T) == pytest.approx(xm, rel=0.08)
    assert d.cooling_per_volume_W_per_mm3(T) == pytest.approx(pm, rel=0.12)
    assert d.cooling_density_W_per_mm2(T) == pytest.approx(pa, rel=0.12)
    assert d.pump_flux_W_per_mm2(T) == pytest.approx(flux, rel=0.15)


def test_table_1_1_target_device_is_rung_6():
    d = make_extractor('dye')
    assert d.rung == 6 and d.T_design == 400.0
    assert d.cooling_density_W_per_mm2(400.0) == pytest.approx(6e3, rel=0.05)
    assert 100.0 * d.eta_q() == pytest.approx(10.3, abs=0.2)


def test_dye_quantum_defect_reproduces_table_8_3():
    for lp, expect in ((640.0, 3.6), (651.0, 5.3), (660.0, 6.8), (680.0, 10.0), (700.0, 13.3),
                       (720.0, 16.5)):
        assert 100.0 * DyeExtractor(lambda_p_nm=lp, lambda_f_nm=618.0).eta_q() == pytest.approx(expect, abs=0.06)


def test_transparency_cap_is_the_boltzmann_ratio_of_5_7():
    d = DyeExtractor(lambda_p_nm=651.0)
    dE = ev_from_nm(588.0) - ev_from_nm(651.0)
    assert d.x_max(300.0) == pytest.approx(1.0 / (1.0 + math.exp(dE / (K_B_EV * 300.0))))
    # and it is INDEPENDENT of the tail steepness: sigma changes eta_abs, never x_max
    assert DyeExtractor(sigma=0.26).x_max(300.0) == d.x_max(300.0)


def test_section_8_3_5_optimum_pump_and_required_eqe():
    """10^-2 M, 300 K, lambda_f 610: peak eta_cool ~ +5.3 % at 651 nm, EQE >= 0.95 there;
    10^-1 M: +8.7 % at 672 nm, EQE >= 0.92; 10^-1 M at 400 K: +13 % at 702 nm, EQE 0.885."""
    def peak(C, T):
        lams = np.arange(612.0, 720.0, 1.0)
        vals = [DyeExtractor(N_t_M=C, lambda_p_nm=l, lambda_f_nm=610.0).eta_cool(T) for l in lams]
        k = int(np.argmax(vals))
        return float(lams[k]), 100.0 * vals[k]
    lp, ec = peak(1e-2, 300.0)
    assert lp == pytest.approx(651.0, abs=8.0) and ec == pytest.approx(5.3, abs=1.0)
    assert DyeExtractor(N_t_M=1e-2, lambda_p_nm=651.0, lambda_f_nm=610.0).required_eta_EQE(300.0) == pytest.approx(0.95, abs=0.01)
    lp, ec = peak(1e-1, 300.0)
    assert lp == pytest.approx(672.0, abs=8.0) and ec == pytest.approx(8.7, abs=1.2)
    lp, ec = peak(1e-1, 400.0)
    assert lp == pytest.approx(702.0, abs=10.0) and ec == pytest.approx(13.0, abs=1.5)
    assert DyeExtractor(N_t_M=1e-1, lambda_p_nm=702.0, lambda_f_nm=610.0).required_eta_EQE(400.0) == pytest.approx(0.885, abs=0.015)


def test_dye_cools_only_when_pumped_red_of_the_mean_fluorescence():
    assert DyeExtractor(lambda_p_nm=612.0, lambda_f_nm=618.0).cooling_density_W_per_mm2(300.0) < 0.0
    assert DyeExtractor(lambda_p_nm=651.0, lambda_f_nm=618.0).cooling_density_W_per_mm2(300.0) > 0.0


def test_dye_capability_collapses_on_cooling_through_x_max_regardless_of_sigma():
    """The temperature dependence that matters is carried by the transparency cap, which is
    thermal by construction: a 400 K tile gives 5-10x the 300 K ceiling (v98 §8.3.3), and by
    200 K the capability is below 1 % of the design value whatever the tail steepness."""
    for sigma in (1.0, 0.26):
        d = DyeExtractor.from_rung(6, sigma=sigma)
        assert 5.0 < d.cooling_density_W_per_mm2(400.0) / d.cooling_density_W_per_mm2(300.0) < 10.0
        assert d.cooling_density_W_per_mm2(200.0) < 0.01 * d.cooling_density_W_per_mm2(400.0)
    # T_min (where net cooling vanishes) does move with sigma and the host loss ...
    t_book = DyeExtractor.from_rung(6).t_min_K()
    t_dis = DyeExtractor.from_rung(6, sigma=0.26).t_min_K()
    assert t_book is not None and 150.0 < t_book < 200.0
    assert t_dis is None or t_dis < t_book
    # ... but it sits where the capability is already negligible
    assert DyeExtractor.from_rung(6).cooling_density_W_per_mm2(t_book + 20.0) < 0.02 * 6e3


def test_dye_ladder_presets_exist_and_the_near_term_film_is_two_watts_per_mm2():
    near = make_extractor('dye-near')
    assert near.rung == 2 and near.cooling_density_W_per_mm2(400.0) == pytest.approx(1.9, rel=0.12)
    assert make_extractor('dye-bulk').rung == 0 and make_extractor('dye-600K').rung == 7
    assert make_extractor('dye-tier1').describe()['h_at_design_W_per_mm2'] == pytest.approx(5.9e3, rel=0.12)


# ---------------------------------------------------------------------------
# GaAs at v91's Table 9.2 benchmark
# ---------------------------------------------------------------------------
def test_gaas_urbach_energy_is_derived_from_the_tables_two_alphas():
    g = SemiconductorExtractor()
    assert g.E_U_300 == pytest.approx((gaas_bandgap_eV(300.0) - ev_from_nm(890.0)) / math.log(1e4 / 100.0))
    assert 0.005 < g.E_U_300 < 0.010
    assert g.alpha_pump(300.0) == pytest.approx(100.0, rel=1e-6)


def test_gaas_optimum_reproduces_table_9_2():
    """N_opt 5.7e17 cm^-3 and ~80 W/mm^3 from A, B, C, alpha, lambda_p, lambda_f, eta_e = 0.25."""
    g = SemiconductorExtractor()
    N, p = g.optimum(300.0)
    assert N == pytest.approx(5.7e17, rel=0.15)
    assert p == pytest.approx(80.0, rel=0.20)
    book = g.book_closed_form(300.0)
    assert book['N_opt_cm3'] == pytest.approx(5.7e17, rel=0.05), 'eq. (9.7) with the table inputs'
    assert book['cooling_possible']


def test_gaas_v98_closed_form_9_6_matches_the_balance_optimum():
    """v98 corrected (9.6) to 4/27 (the §P0.19 check found the 3x); the closed form and the
    numeric optimum of the same balance now agree."""
    g = SemiconductorExtractor()
    _, p = g.optimum(300.0)
    assert g.book_closed_form(300.0)['p_opt_W_per_mm3'] == pytest.approx(p, rel=0.10)


def test_gaas_breakeven_a0_rule_and_the_unpassivated_negative_control():
    """v98 (9.7): cooling requires A < A0. Passivated GaAs (A = 5e4) cools; unpassivated
    (100x worse, Table 9.3's passivation gain) does not, at any carrier density."""
    good = SemiconductorExtractor(A_per_s=5e4)
    bad = SemiconductorExtractor(A_per_s=5e6)
    assert good.A < good.book_closed_form(300.0)['A0_per_s']
    assert bad.A > bad.book_closed_form(300.0)['A0_per_s']
    assert good.cooling_density_W_per_mm2(300.0) > 0.0
    assert bad.cooling_density_W_per_mm2(300.0) < 0.0
    assert bad.optimum(300.0)[1] < 0.0


def test_gaas_fixed_pump_freezes_out_but_a_retuned_pump_does_not():
    """Varshni widens the gap on cooling, so a fixed 890 nm pump sinks into the Urbach tail and
    the flux dies near 260 K; retuning the pump to the current gap keeps cooling and the flux
    RISES on cooling as Auger recombination is suppressed."""
    fixed = SemiconductorExtractor(retune_pump=False)
    retuned = SemiconductorExtractor(retune_pump=True)
    tmin = fixed.t_min_K()
    assert tmin is not None and 240.0 < tmin < 280.0
    assert retuned.t_min_K() is None
    assert retuned.cooling_density_W_per_mm2(200.0) > retuned.cooling_density_W_per_mm2(300.0)
    assert fixed.alpha_pump(200.0) < 1e-2 * fixed.alpha_pump(300.0)


def test_gaas_table_1_1_row_is_the_enhanced_preset():
    """v98 Table 1.1: eta_e = 0.9, F_P(B) = 10, N ~ 2e19 cm^-3 -> 10^5-10^6 W/mm^3 (Auger-limited).
    The cubic gain puts the balance's optimum at the top of that range."""
    bulk = SemiconductorExtractor().cooling_density_W_per_mm2(300.0)
    assert 0.05 < bulk < 0.12
    g = make_extractor('gaas-enhanced')
    N, p = g.optimum(300.0)
    assert N == pytest.approx(2e19, rel=0.5)
    assert 1e5 < p < 5e6


def test_gaas_bandgap_varshni_anchor():
    assert gaas_bandgap_eV(300.0) == pytest.approx(1.4225, abs=2e-3)
    assert gaas_bandgap_eV(0.0) == pytest.approx(1.519)


# ---------------------------------------------------------------------------
# registry and description
# ---------------------------------------------------------------------------
def test_registry_and_describe_carry_the_bracket_inputs():
    d = make_extractor('dye')
    g = make_extractor('gaas-retuned')
    assert d.describe()['sigma'] == DYE_SIGMA_BOOK and 'alpha_b_cm' in d.describe()
    assert g.describe()['retune_pump'] is True
    assert set(DYE_LADDER) == set(range(8))
    with pytest.raises(ValueError):
        make_extractor('ybylf')


# ---------------------------------------------------------------------------
# Cr:LiSAF, the storage-zone material (v98 §8.1.2, Table 1.1) -- decided 8 Sep
# ---------------------------------------------------------------------------
def test_crlisaf_reproduces_v98_table_1_1_and_8_1_2():
    c = CrLiSAFExtractor(purcell=30.0, film_um=10.0)
    # §8.1.2 quotes ~4e-3 with the crossing 'near 815 nm'; 815 nm gives 3.2e-3, 818 nm gives
    # 4.0e-3 -- the book rounds the crossing, so the anchor is held to the rounding.
    assert c.x_max(290.0) == pytest.approx(4e-3, rel=0.25)
    assert 100.0 * c.eta_q() == pytest.approx(5.9, abs=0.2)                  # 900 on 850 nm
    assert c.sigma_a_pump(290.0) == pytest.approx(4e-23, rel=1e-6)          # the anchor
    lo, hi = CrLiSAFExtractor(purcell=30.0).cooling_per_volume_W_per_mm3(300.0), \
        CrLiSAFExtractor(purcell=100.0).cooling_per_volume_W_per_mm3(300.0)
    assert 15.0 < lo < 35.0 and 55.0 < hi < 110.0                          # 20-80 W/mm^3
    assert 0.15 < c.cooling_density_W_per_mm2(300.0) < 0.35                 # 0.2 W/mm^2 per 10 um


def test_crlisaf_fails_breakeven_at_its_demonstrated_iqe():
    """v98 Table 8.4: needs eta_EQE > 0.94; best crystals 0.85-0.95."""
    assert CrLiSAFExtractor(eta_EQE=0.90).cooling_density_W_per_mm2(300.0) < 0.0
    assert CrLiSAFExtractor(eta_EQE=0.97).cooling_density_W_per_mm2(300.0) > 0.0


def test_crlisaf_capability_also_collapses_on_cooling():
    """Same transparency cap as every anti-Stokes emitter: a storage tile at 200 K has ~6 % of
    the 300 K ceiling -- which is what a leakage-suppression tile needs, not a hot-spot razor."""
    c = CrLiSAFExtractor()
    r = c.cooling_density_W_per_mm2(200.0) / c.cooling_density_W_per_mm2(300.0)
    assert 0.02 < r < 0.15


def test_dual_zone_dispatches_by_tile_and_defaults_to_the_hot_curve():
    cold = CrLiSAFExtractor()
    hot = make_extractor('dye')
    dz = DualZoneExtractor(cold, hot, cold_tiles={'MR_r00_c00'})
    assert dz.zoned is True
    assert dz.cooling_density_W_per_mm2(300.0, tile='MR_r00_c00') == cold.cooling_density_W_per_mm2(300.0)
    assert dz.cooling_density_W_per_mm2(300.0, tile='MR_r00_c01') == hot.cooling_density_W_per_mm2(300.0)
    assert dz.cooling_density_W_per_mm2(300.0) == hot.cooling_density_W_per_mm2(300.0)
    assert set(dz.t_min_K()) == {'cold', 'hot'} and dz.describe()['n_cold_tiles'] == 1


# ---------------------------------------------------------------------------
# v100 (9 Sep 2026): the two organic rows added to Table 1.1, and eq. (8.4)
# ---------------------------------------------------------------------------
def test_v100_eq_8_4_iqe_under_purcell():
    """0.2 -> 0.71, 0.88, 0.96 at F_P = 10, 30, 100 (v100 §8.3.1)."""
    assert iqe_under_purcell(10, 0.2) == pytest.approx(0.71, abs=0.01)
    assert iqe_under_purcell(30, 0.2) == pytest.approx(0.88, abs=0.01)
    assert iqe_under_purcell(100, 0.2) == pytest.approx(0.96, abs=0.01)
    assert iqe_under_purcell(100, 1.0) == 1.0


def test_v100_table_1_1_nir_tricarbocyanine_row():
    """10^-1 M, 400 K, 980 nm pump 200 meV below the zero line, IQE0 0.2, F_P 100, 50 um:
    x_max 3e-3, eta_q 18 %, eta_cool 13 %, 1.7e5 W/mm^3, 8e3 W/mm^2."""
    c = make_extractor('nir-cyanine')
    assert c.x_max(400.0) == pytest.approx(3e-3, rel=0.05)
    assert 100 * c.eta_q() == pytest.approx(18.0, abs=0.5)
    assert c.eta_EQE == pytest.approx(0.96, abs=0.01)                   # eq. 8.4 applied
    assert 100 * c.eta_cool(400.0) == pytest.approx(13.0, abs=0.5)
    assert c.cooling_per_volume_W_per_mm3(400.0) == pytest.approx(1.7e5, rel=0.15)
    assert c.cooling_density_W_per_mm2(400.0) == pytest.approx(8e3, rel=0.15)
    # the cycling rate is (F_P iqe0 + 1 - iqe0)/tau, not F_P/tau: a 4.8x difference
    assert c.gamma_tot() == pytest.approx(20.8 / 0.6e-9, rel=1e-6)


def test_v100_table_1_1_j_aggregate_row():
    """10^20 cm^-3, tau 234 ps, F_P 10, 400 K, pump 60 meV into the hot band of a 590 nm J-band:
    McCumber x_max 0.15, annihilation-capped 0.02, ~1e6 W/mm^3, ~1e3 W/mm^2 from 1 um, eta_q 3 %."""
    j = make_extractor('j-aggregate')
    assert 1.0 / (1.0 + math.exp((j.E_00 - j.E_p) / (K_B_EV * 400.0))) == pytest.approx(0.15, abs=0.01)
    assert j.x_max(400.0) == pytest.approx(0.02)                        # the cap binds
    assert 100 * j.eta_q() == pytest.approx(3.0, abs=0.2)
    assert j.cooling_per_volume_W_per_mm3(400.0) == pytest.approx(1e6, rel=0.25)
    assert j.cooling_density_W_per_mm2(400.0) == pytest.approx(1e3, rel=0.25)
    assert j.film_um == 1.0


def test_v100_leaves_the_target_device_where_v98_put_it():
    """v100 changed equation numbers, not the rung-6 numbers: the target device is unchanged."""
    d = make_extractor('dye')
    assert d.cooling_density_W_per_mm2(400.0) == pytest.approx(5.9e3, rel=0.05)
    assert d.cooling_density_W_per_mm2(300.0) == pytest.approx(813.0, rel=0.02)
    assert set(TABLE_1_1_ORGANIC) == {'nir-cyanine', 'j-aggregate'}
