# References — what the physics rests on, and where each number comes from

**Written 3 September 2026.** Companion to `docs/METHODS.md` (how to produce a number) and
`docs/RESULTS_REGISTER.md` (what may be quoted).

Every reference below is **in this repository**. Nothing here requires a library search.

---

## 1. The device physics — `docs/Photonic_Cooling_Devices___v100.pdf`

**`[!]` v100 (9 September 2026) supersedes v98, which superseded v91.** When a device number in
this project disagrees with v100, v100 wins and the code comment should say so. Checked 9 Sep
(§P0.21.5): v100 keeps every number the code reproduces from v98 — Tables 8.1, 8.2 (all eight
rungs), 1.1's R640 and Cr:LiSAF rows, §8.1.2, Table 9.2 — and **renumbers chapter 8**: η_cool is
(8.6), the unsaturated slope (8.7), p_max (8.8), the transparency floor d_min (8.9), Strickler–Berg
(8.10), the ladder score Γ_tot (8.11); the new (8.4) is IQE under Purcell. v100 adds two organic
rows to Table 1.1 (NIR tricarbocyanine, J-aggregate — presets `nir-cyanine`, `j-aggregate`), §1.18
(thermally-limited architecture design points) and §10.9 (thermal heterogeneity as a design knob).

| you need (v100) | go to |
|---|---|
| **The target device** — in-principle ceilings per family; the R640-SMILES row is the design point; the two new organic rows are cascade stages | **Table 1.1**, eq. (1.1) |
| **The architectural budget inequality** and what microrefrigeration does to it: (1.32), the hybrid cap ∝ 1/(1−s) (1.33), cubic vs linear frequency scaling, the V_t/leakage trap (1.29), dark silicon | **§1.18** |
| The transparency cap `x_max` | **eq. (5.7)**, §8.3.3 eqs. (8.6)–(8.8) |
| The volumetric route, concentration → W/mm³ → W/mm² | §8.3.3, eq. (8.8) and the `Pcool/A = ∫p dz` line after it; d_min (8.9) |
| IQE under a Purcell factor (low-IQE emitters) | **eq. (8.4)**, §8.3.1 |
| Strickler–Berg: the radiative rate is fixed by the absorption band | eq. (8.10) |
| The dye's operating points and the **photonic ladder** to the design point | **Tables 8.1, 8.2**, §8.3.4 (rungs 0–7, scored by (8.11)) |
| Quantum defect per pump wavelength | Table 8.3 |
| The dye tail model (σ, the 600 nm anchor, λ_00) | **eq. (9.5)**, §9.3.2, Fig. 9.3 |
| Cr:LiSAF (the storage-zone material, 8 Sep decision) | **§8.1.2**, Table 8.4 |
| Why the pump wavelength is a per-temperature variable (GaAs hot-side limit, dye red-shift) | §9.3.2, last subsection |
| Platform comparison at common thickness; the `[T_min, T_max]` axis; selection rules | Table 8.4, §8.4 |
| **Thermal heterogeneity as a design knob**: compute hot / storage cold, the three-zone template and its three walls (BEOL 400 K, extractor material, thermal gradient / packaging) | **§10.9**, Table 10.8 (`[!]` names Yb:YLF for the cold zone; the repository's decision is Cr:LiSAF) |
| **The array geometry** — the tile as coupler / extractor / back-reflector / sensor stacked *above* the silicon, fed by hollow-core fibre or waveguide; LPC external, monolithic-backside or on the back-reflector; the module adds < 500 µm of stack height | **Figs 1.11, 1.13, 1.14, 4.1, 9.1, 9.12, 9.16**; §9.2 Level 2.B (integration modes). `[+]` Cited from v100 since 9 Sep (§P0.22); v91 Figs 9.1/9.8/9.12 said the same |
| What v100 does **not** carry: the demonstrated **45 K lift** and the 250 W/mm² bench figure | **Not in v100** (checked 9 Sep: no bench lift anywhere in the text). They remain Draft_5 §6.4.1 (Yb:YLF bench) — see §1.1 — and the scalar 45 K is kept beside the extractor curve because it shapes the plan (§P0.19) |

v91's map, still valid where v98 did not move it:

| you need | go to |
|---|---|
| Which extractor platform, and its numbers | **Table 8.2** (platforms), **Table 8.1** (anti-Stokes ladder), §8.2.1, §8.3.2–8.3.3 |
| Why the loop can be self-powering at all | §1.8–1.10 (where the second law enters), §1.11–1.15 |
| The exergy bound the code implements | **§1.11, eq. (1.13)** — see §2 below |
| LPC limits, and why they are not Carnot | **§7.2.2, Result 7.1**; §7.3 (bandwidth, étendue, coherence) |
| Multi-junction LPCs | §7.4 — and note §7.4.3, splitting in frequency alone buys nothing on radiation entropy |
| Engineering the fluorescence before the LPC | §7.5 |
| Coupled electro-optic extractor model | Ch. 5, esp. (5.16) cooling power, (5.19) McCumber |
| Where hot-spot **demand** actually is | **Figure 1.6** — 10³–10⁴ W/mm² at the ~10 µm scale |

`[!]` **The binding constraint is cooling power *density*, not cooling capacity.** v91's framing:
rack-level total power is within reach of conventional coolants; the ~10 µm hot spot is not. This
is the argument the project exists to test, and it is why `h_max` matters more than total watts.

### 1.1 Related device documents

- `docs/chip_design_lit/SoC-Physical-Design.pdf` — Chakravarthi & Koteshwar, *SoC Physical
  Design: A Comprehensive Guide* (Springer 2022). **Added 10 Sep 2026** for the core-evolution
  phase: the constraints the pipeline does not model — IR drop / PDN (pp. 36–37, 43–46, 88–90),
  electromigration (90–91), clock skew and CTS (52–63), floorplan overheads and macro halos
  (34–36, 44–46), 3D-IC geometry (122–128). What it changes and what it does not:
  `docs/PHYSICAL_DESIGN_CONSTRAINTS.md`. Book page = PDF page − 21.
- `docs/photonic_cooling/Draft_5__Photonic_cooling_of_chips_v12___Provisional_Version.pdf` —
  the **demonstrated** bench figures (§6.4.1: 250 W/mm² from 100 × 100 µm; 45 K lift; η_ASF 0.035;
  §3.5.4 laser and LPC efficiencies). `[!]` Superseded by v91/v98/v100 for platform capability
  and (since 9 Sep) for the array geometry, but it is still the **only** source for what has
  actually been *built* — v100 carries no bench lift, so the 45 K stays cited here.
- `docs/Microrefrigeration_v1.pdf`, `docs/photonic_cooling/Photonic_Cooling_Devices___v9.pdf` —
  earlier revisions. Prefer v91.

---

## 2. The thermodynamics the code implements

`[!]` **This section is load-bearing. `MRParams.breakeven_ratio_at()` is v91 eq. (1.13).**

### 2.1 The refined exergy bound

Energy conservation around the extractor gives `P_f = P_abs + Q_c`, and **the two halves have
different exergy character**:

- the **pump-derived** part `P_abs` is *work-like* — the pump beam was coherent — so its exergy
  equals its energy;
- the **heat-derived** part `Q_c` was lifted from the chip at `T_h`, so it is **Carnot-bounded**:
  `≤ Q_c (1 − T₀/T_h)`.

Hence v91 (1.13):

```
B_f  ≤  P_abs + Q_c (1 − T₀/T_h)  =  η_cpl · P_L · [ 1 + η_ASF · (1 − T₀/T_h) ]
```

and that is exactly what the code computes, times the LPC and laser efficiencies:

```python
phi = 1.0 - T_0 / T_h                                    # the Carnot factor
return (lpc_efficiency * collection_efficiency
        * (1.0 + eta_asf * phi) * laser_wallplug)        # breakeven_ratio_at()
```

The `1` is the pump-derived part at full exergy; the `η_ASF · φ` is the heat-derived part,
Carnot-discounted. `[!]` **`breakeven_ratio` (no `_at`) is the `φ → 1` limit** — the first-law
ledger — and a loop it calls net-generating is not necessarily permitted by the second law.
That distinction produced 36 rows reporting a cooler that generates free energy.

### 2.2 Why the LPC is not Carnot-limited on the pump

**Result 7.1**: `P_el ≤ Ḣ − T₀Ṡ`, so `η_LPC^max = 1 − T₀Ṡ/Ḣ`.

> The Carnot bound is not about bandwidth. It is about whether the radiation carries entropy.

- **Narrowband coherent laser** — `Ṡ ≈ 0`, so `η → 1`. Not a Carnot violation: it converts
  *work-like* radiation into work. Demonstrated: **74.7 %** at 808 nm (cryogenic), **68.9 %** at
  850 nm (photon-recycling).
- **Broadband / thermal** — `Ṡ` grows with the mode count; `η` falls toward the Carnot factor.
- **Single-mode but incoherent (engineered fluorescence)** — the case this device is in. Purcell
  engineering reduces `Ṡ` and raises the exergy fraction **toward unity**.

The discriminator is **entropy per unit energy** — phase-space density / étendue / brightness —
not bandwidth.

`[+]` **Consequence for our numbers, and it is favourable.** We apply the many-mode Carnot factor
to the anti-Stokes term. The device deliberately engineers fluorescence *away* from that limit.
**So every recovered-power figure this project reports is a lower bound**, and the gap is a design
lever rather than an error. Say this when a reviewer asks why recovery looks modest.

`[!]` What we do **not** model: the `Ṡ` reduction from mode engineering, multi-junction entropy
splitting (§7.4), or the Shockley–Queisser thermalisation gain. All are upside.

### 2.3 The extractor's cooling curve — `thermal/extractor.py` (§P0.19)

Where `h(T_ext)` comes from, equation by equation:

- **Cooling per absorbed photon** — eq. (1.5)/(4.15), `P_cool = P_f − P_abs − P_parasitic`, with
  the parasitic split of Table 1.1: `η_abs = α_dye/(α_dye + α_b)` at the pump.
- **The red-tail pump absorption** — the Urbach edge, eq. (9.4), `α(E) = α_0 exp((E − E_g)/E_U)`,
  used for the semiconductor as written and for the dye's vibronic tail; `E_U(T)` by the
  phonon-assisted Urbach rule (GaAs, 6.7 meV at 300 K from Table 9.2's two alphas) or a
  static-plus-thermal quadrature for the dye (the bracket).
- **Emission from absorption** — McCumber, eq. (5.19), on the thermalised core only; on an
  exponential tail with `E_U > kT` it diverges, which says the far tail is not a thermalised
  manifold. The dye's mean fluorescence is anchored on Table 8.1's 605 nm and the relation
  supplies only its drift.
- **Dye design point** — §8.3.2–8.3.3 (10⁻² M, 1–10 µm, Purcell 10⁹ s⁻¹, IQE 0.99, λ_p ≥ 680 nm);
  Table 8.1 (η_c); eq. (8.4) (10³–10⁴ W/mm²).
- **Semiconductor** — eq. (8.1) balance with **photon recycling** (§5.7: only the escaped
  fraction of radiative recombination is replenished by the pump), Table 9.2 inputs, the
  A₀ breakeven (9.6) and N_opt (9.7); Varshni for `E_g(T)`; `C(T) ∝ exp(−2.4(300/T − 1))` as
  §9.3.3 quotes; `B ∝ T^{-3/2}`.

`[+]` Both notes the §P0.19 check sent to the author are resolved in v98: eq. (9.6) carries 4/27
and says so; the breakeven is `A < A_0`; Fig. 9.9's caption names the plotted quantity as the
escape efficiency under reabsorption recycling. §9.3.2 also cites the three-tile fixed-pump GaAs
result.

### 2.4 The dye on v98's route (§P0.20)

`p_max = n_t · x_max(T) · (F_P/τ) · ħω_p · η_cool(T)` with `x_max = [1 + e^{(E_00−E_p)/kT}]⁻¹`
(eq. 5.7), `η_cool = η_abs η_EQE λ_p/λ̄_f − 1` (8.5), `η_abs = α_r/(α_r + α_b)`, `α_r = ln10·C·ε`,
`ε(E,T) = 4290 exp[σ(E − E_600)/kT]` (9.5); `P_cool/A = p_max d` (8.9). `x_max` is a Boltzmann
population ratio (McCumber) and carries the temperature dependence regardless of σ. The v91 eq.
8.4 figure (10³–10⁴ W/mm² for a bulk film) is withdrawn by v98 and must not be quoted; 10³ is the
Tier-I design point after the ladder.

---

## 3. Chip architecture and floorplanning — `docs/chip_design_lit/`

Use these to keep floorplan and circuit assumptions honest. The project's own floorplans are
generated, and a generated floorplan is only as good as the design rules behind it.

| topic | file |
|---|---|
| **Physical structure of CMOS ICs** — layers, cells, what a block *is* | `642182427-SP16-VLSI-Lec05-...-Physical-Structure-of-CMOS-ICs.pptx` |
| **High-performance microprocessor circuits** — the delay law, sizing, why `α`-power holds | `design_of_highperf_microproc_circuits.pdf` |
| Practical VLSI / SoC flow | `practical_guide_VLSI_SoC.pdf`, `vlsieducation.pdf` |
| **Modern GPU architecture** — for the accelerator die, currently parked | `moderngpuarchitecturesecondedition.pdf` |
| **Leakage and the end of Dennard scaling** | `design_physics/2003.12.Leakage-Current-Moores-Law-Meetings-Static-Power_Computer.pdf` |
| **Supply/threshold voltage scaling** — the `V_t` lever's own literature | `design_physics/CMOS_Supply-And-Threshold-Voltage-Scaling-For-Low-Power-CMOS-...pdf` |
| Power density implications | `design_physics/Gallina_ImplicationsOfPowerDensity_presentation (1).pdf` |
| Microchannel cooling limits — the competing technology | `design_physics/microchannel-hotspot-limits-*.pdf`, `microchannel_COP100k_*.pdf` |
| Hot-spot mitigation via telemetry | `design_physics/Boreas-hotspot-mitigation-using-ml-hw-telemtry.pdf` |
| Real die floorplans | `die_images/`, `MXL-HotGauge-Floorplan-Pack/` |
| **IRDS 2024 roadmap tables** — the V/F curve's actual source | `roadmaps/IRDS/2024IRDS_MM_Tables.xlsx`, sheet `MM01 - LOGIC` |

`[!]` **The floorplan pack and die images are third-party subscriber content.** Numbers derived
from them may be published; **the plates may not.**

---

## 4. The thermal/power tooling this project extends

- `docs/HotGauge-A-Methodology-for-Characterizing-Advanced_2.pdf` and
  `design_physics/HotGauge_IISWC_2021.pdf` — the upstream tool. `[+]` Its published hot-spot
  locations (cALU / ALU cluster, aggregated over single-threaded benchmarks) **agree with our
  independently computed power map**, which is a check on floorplan and power together.
- **The transistor, simulated:** `docs/evidence/device_leakage_spice_asap7.json` (leakage, §P0.13)
  and `docs/evidence/device_vt_vf_asap7.json` (threshold, swing, DIBL, drive current, V/F shape,
  §P0.18.3) — both ngspice 47 + OSDI + OpenVAF BSIM-CMG 110 on the vendored ASAP7 card
  (`spice_leakage/models/asap7_7nm_TT.pm`, BSD-3, `spice_leakage/PROVENANCE.md`). They agree on
  `I_off(T)` to 0.76 %. `[!]` The threshold is a constant-current *criterion* (100 nA × W/L);
  compare coefficients and shapes with other sources, never levels.
- McPAT / CACTI live in `McPAT/`. `[!]` `cacti/technology.cc:1610` is where the pipeline leakage
  curve actually comes from — `I_off_n[0][*]` for "16nm DG HP", 32 nm numbers times three fudge
  factors. See `docs/evidence/device_leakage_asap7.json`.
- 3D-ICE in `3d-ice/`. SuperLU 4.3 gives up somewhere above ~366 k unknowns, silently.

---

## 5. Which source wins when they disagree

1. **A measurement in this repository** (`docs/evidence/*.json`, `results/`) beats any document.
2. **v98** beats v91, which beats Draft_5, for *platform capability*; Draft_5 remains the source
   for what is *demonstrated*.
3. **IRDS 2024** beats the shipped `VF_PAIRS` table for V/F ceilings; the **simulated card**
   beats both for V/F *shape* and for `V_t(T)` / `SS(T)`, but supplies no absolute clock — its
   anchor is the trace's 3.8 GHz at 0.70 V and is a stated choice.
4. **McPAT's own printed totals** beat our derived aggregates — that is how the `2 *` converter bug
   was caught (the corrected die reproduces McPAT's 29.36 % static fraction; the as-built die
   reported 18.43 %).
5. When a *document* and a *measurement* disagree and the measurement is on the parked
   architecture, neither wins — say so and open it in `RESULTS_REGISTER.md` §3.
