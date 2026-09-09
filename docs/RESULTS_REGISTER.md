# Results register — what may be quoted, and what may not

**Single source of truth for every number this project has produced.** Last updated 5 September 2026 (§P0.19).

`[!]` **Read this before quoting any figure, in a proposal, a paper, a slide, or a session summary.**
The project has produced results for six weeks and has withdrawn a substantial fraction of them.
The withdrawn ones are the ones most likely to resurface, because they live on in older drafts,
earlier artifacts, and the reasoning of anyone who read the repository a fortnight ago.

**How to use this file**

- A claim in **§1 (quotable)** may be used as written, *with its caveat*. The caveat column is not
  editorial trimming — every one of them has bitten at least once.
- A claim in **§2 (withdrawn)** must not be used. Each row names what to say instead.
- A claim in **§3 (open)** has not been measured. Do not derive it, do not estimate it, and do not
  let it into a document — ask, or measure it.
- If a figure you want is in none of the three sections, **it has probably not been measured on this
  die under the current accounting.** Treat that as a "no" until checked.

`[+]` **The evidence for §1 and §2 is materialised as two directories at the repository root**, so a
proposal writer never has to pick the good files out of the working set:

| directory | holds | per-item note |
|---|---|---|
| **`results-quotable/`** | evidence behind the §1 claims below | `SOURCE.md` — claim, figure, reproduce command, caveat |
| **`results-historical/`** | evidence behind the §2 withdrawn claims | `WHY_RETIRED.md` — what to say instead, why it failed, **what still survives inside** |

Evidence JSONs are copied (small, so a directory is a self-contained snapshot); the multi-gigabyte
solve trees are symlinked. Rebuild or drift-check with
`python scripts/build_results_registers.py [--verify]`.
`[!]` They are **curated, not exhaustive** — `docs/evidence/` remains the full ~110-file working
set, and a file's absence from either directory means nobody has classified it, not that it is
wrong.

---

## 0. The configuration every current number is computed under

Changed 2–3 September 2026. An un-flagged run today is **not** the configuration the pre-September
catalogue was computed under.

| flag | value | meaning |
|---|---|---|
| `--leakage-curve` | `pipeline` | CACTI's 11 hard-coded numbers. `[!]` **Still the default. §P0.18.0 recommends `simulated` with reasoning; the flip is the user's call — see §3.** |
| `--array-coverage` | `1.0` | fraction of the pixel layer's footprint that is emitting extractor (areal). New 3 Sep (§P0.18.1); 1.0 is every recorded result |
| `--mr-zone-mode` | `single` | one extractor material over the whole array (architecture-agnostic). `dual` = the flagged cold-zone / hot-zone arrangement laid out against this floorplan (`--mr-cold-extractor cr-lisaf` on tiles majority-under `--mr-cold-zone-pattern '^(L2\|L3)'`), a per-architecture product kept for measurement, never the default. New 8 Sep (§P0.21) |
| `--rbb-policy` | `amortized` | the results-broadcast bus folded onto the execution units it spans |
| `--core-other-policy` | `hierarchy-consistent` | the McPAT per-core `2 *` undone |
| `--mr-eta-asf` | `0.32` | unchanged; the usable range is **0.10–0.60** (Draft_5 §3.5.4, "10–60 % across MVP stages") and 0.32 is the middle ground |
| `--mr-h-max` | `1000` W/mm² | low end of the published platform range |

**To reproduce the recorded catalogue exactly:**
`--leakage-curve pipeline --rbb-policy stock --core-other-policy stock --mr-h-max 250`
(`--mr-eta-asf` needs no flag — 0.32 is still the default.)

`[!]` **The shipped default is not one of the four measured arms.** Arms A–D were
`(pipeline, stock, stock)`, `(simulated, stock, stock)`, `(simulated, amortized, stock)`,
`(simulated, amortized, hierarchy-consistent)`. The default is now
`(pipeline, amortized, hierarchy-consistent)`, which nobody has run end to end. See §3.

---

## 1. Quotable

### 1.1 The core result — microrefrigeration rescues a die that has no steady state

| claim | figure | evidence | caveat that travels with it |
|---|---|---|---|
| The laser rescues a die with no steady state; an unpowered array of the same material does not | **35 / 35** points | `docs/evidence/mr_catalogue_curve_compare.json`, `examples/mr_curve_compare.py` | It is a **difference between arms**. Never quote the array arm alone. Holds across 20–120 CFM and the whole pitch ladder, on all three leakage curves. |
| The rescue is not an artefact of the leakage model | 6/6 airflow points on **all three** curves | same | The `array_idle` arm diverges everywhere too, which is what makes it a statement about the *laser* rather than about adding a second die. |

### 1.2 Cooling the cache

| claim | figure | evidence | caveat |
|---|---|---|---|
| Cooling the cache reduces its leakage far more than the project's original curve implied | **2.23×** | `docs/evidence/cold_zone_prize_simulated.json` | `[!]` **Quote the improvement, not a percentage.** This ratio has survived four revisions of the absolute number because the conversion cancels in it. |
| The cold-zone target is barely sub-ambient, not cryogenic | **280 K** | same | Within 5 % of maximum by 280 K; the 80 K below it buys under 5 % more. Both GIDL brackets agree on the knee. **This is a design constraint, and a favourable one.** |
| The cold zone must be a **separate die** | 1.24 K of gradient for 40 W removed | `docs/POWER_RECOVERY_PLAN.md`, TEST 1 | Two independent methods agree to 1.7×. Lateral conduction shorts the zones on a monolithic die. |
| Cooling the cache is worth this share of die power | **~14 %** | `docs/evidence/cold_zone_prize_core_other_consistent.json` | `[!]` **Accounting-dependent**: ~14 % corrected, ~6 % under the recorded accounting. Neither is the literature's 31.7 %. **Prefer the 2.23×.** |

### 1.3 Density, concentration and the floorplan

| claim | figure | evidence | caveat |
|---|---|---|---|
| Concentrating power costs sustainable density; spreading it buys density back | **1.4×** | `results/uniform_density_armD/` | Flat (Gini 0) arm holds 0.85–0.90 W/mm²; the real power map holds 0.60–0.65. The **ratio** is the durable result. |
| A perfectly flat die still has a hard density ceiling — physics, not a hot block | **0.85–0.90 W/mm²** | `results/uniform_density_armD/uniform/` | `[!]` **Lower than any previously recorded value** (was 1.05–1.10). Two independent corrections both push it down. **A flat die at ~1 W/mm² is no longer supportable** on this package and leakage model. |
| Optics requirement is set by the floorplan and is looser than assumed | **200 µm** | `docs/evidence/mr_catalogue_curve_compare.json` | 50/100/200 µm cost 19.476/19.476/19.470 W — identical to four figures across an **813× range in tile count**. Coarser than 200 µm does degrade. |
| Granularity converts structure into cooling, and the ordering **reverses** with the workload | **2.77×** concentrated vs uniform | `docs/evidence/tile_pitch_*.json` | Still true and still the workload-dependence point. `[!]` It is **not** the pitch story any more — 200 µm above is. |
| The array's own footprint is free at the shipped pitch: a quarter-coverage array holds the same ceiling on the same minimum plan | **0.26 coverage, 644/1126 blocks under gaps, 74.8 of 101 mm² reserved: same rung, Q within 1.6 %** at a common peak | `docs/evidence/array_coverage_armD.json` (§P0.18.2) | 500 µm pitch, 200 µm burial, arm D. The 200 µm of silicon smears a 250 µm gap as it smeared the 50–200 µm pitch ladder. `[!]` Cannot move a **control-arm** ceiling (no array there). Per-tile flux rises 1/coverage — 35 W/mm² at 0.26 — and does not bind against `h_max`. Above 1.10 the plan is die-wide, so this is a uniformity result; the one targeted rung (1.10) agrees. |
| The array holds a steady state far past the passive cliff under corrected inputs | **`array_idle` fails at 1.20; `array_on` holds to 2.60, fails at 3.00** with the injected-power cap; **holds to 2.40, not 2.60, under conservation** (§P0.19, `--mr-energy-cap converged`: 213 W removed from a die dissipating 222 W) | `docs/evidence/array_coverage_armD.json`, `extractor_armD.json` | `[!]` **An envelope result, not a package ceiling.** At 2.60 holding the target needs 257 W from a die dissipating 239 W — the array would be refrigerating the heat sink — so the honest top rung is **2.40**. **Quote the rescue range and the cost ladder** — 17 W removed at 1.20 → 139 W at 2.00, 11 → 84 W net — not the top rung as an operating point. Supersedes the recorded 1.60–1.80 (pipeline curve, stock accounting). |

### 1.4 What the corrections revealed

| claim | figure | evidence | caveat |
|---|---|---|---|
| Most of the recorded catalogue's thermal divergence was an artefact of two wrong inputs | **94 → 8** of 145 | `docs/evidence/catalogue_arm_compare.json` | Control arm. Leakage curve 57 points, accounting 22, bus policy **none**. `[!]` **Not** a restated density ceiling — see §1.3 for that. |
| The bus placement policy changes no verdict anywhere | **0 flips** / 145 points | same | Moves temperatures a little (control −0.55 K, array −3.02 K). A **null result**, which is why the default could move safely. |
| The pipeline leakage curve is not a device | 0.016–1.081 eV, **69×**, non-monotone | `docs/evidence/device_leakage_asap7.json` | It is a bit-for-bit pass-through of CACTI's `I_off_n[0][*]` for "16nm DG HP" — 32 nm numbers × three fudge factors. |
| The McPAT converter double-counts per-core dynamic power | exactly **2.0000×** | `docs/evidence/catalogue_arm_compare.json`, §P0.16 | A literal `2 * runtime_dynamic` in `scripts/mcpat_to_blk_lvl_power_dict.py`. The corrected die reproduces McPAT's own 29.36 % static fraction; the as-built die reports 18.43 %. |

### 1.5 The device platform

| claim | figure | source | caveat |
|---|---|---|---|
| The extractor is a thin film — GaAs tiles **or** SiN-encapsulated molecular dye | **> 1000 W/mm²**, η_ASF **0.10–0.60** | v91 Table 8.2; `microrefrigeration.PLATFORMS_V91` | `[!]` **Neither is a rare-earth crystal.** See §2 — Yb:YLF is withdrawn as a zone material. |
| **Zone materials (decided 8 Sep, §P0.21): storage zone Cr:LiSAF, hot zone the dye** | Cr:LiSAF **20–80 W/mm³** at F_P 30–100 (0.2–0.8 W/mm² per 10 µm), quantum defect 5.9 %, needs η_EQE > 0.94 | v98 §8.1.2 / Tables 1.1, 8.4; `make_extractor('cr-lisaf')` | `[!]` **Ceilings at η_EQE = 1** — at the demonstrated 0.90 the crystal heats. **The default cold plate is single-material**; the dual arrangement is a flag. |
| The dual (cold-zone / hot-zone) arrangement on the hot-spot objective | **1 % effect** at 2.00 W/mm²: plan +1.3 W, 0.10 W shortfall, 80 cold tiles of 384, 23 capped; the default reproduces P0.20 to 10⁻¹³ W | `docs/evidence/zone_mode_smoke.json` | `[!]` **A floorplan statement, this die only.** The planner never drives the caches cold on this objective (coldest tile 290.7 K), so a storage-zone material has nothing to do until the objective is cache leakage or the floorplan is the variable (Phase 2). |
| Supply now meets hot-spot demand | 10³–10⁴ W/mm² both platforms | v91 Table 8.2 / Figure 1.6 | The pre-30-Aug catalogue used 250 W/mm², which understated it 4–40×. |
| Our recovery model is **conservative by construction** | Carnot factor on the anti-Stokes term | v91 Result 7.1 | The device engineers fluorescence toward low entropy, where the bound relaxes toward 1. We apply the many-mode Carnot limit, so our recovered power is a **lower bound**. See `docs/REFERENCES.md` §2. |
| **The target device is v98 Table 1.1's R640-SMILES row** (rung 6 of the Table 8.2 ladder), and its lift is a curve the book's own constitutive model fixes | **5900 W/mm² at 400 K, 813 at 300 K, 263 at 263 K, 11 at 200 K**; `T_min` 176 K (σ = 1) | `docs/evidence/extractor_cooling_curves.json` (§P0.20) | Reproduces v98 Tables 8.1 and 8.2 to the printed digit, Table 8.3, §8.3.5's optima, Table 1.1. The temperature dependence is the transparency cap `x_max`, thermal by construction, so it does not depend on the tail steepness σ. `[!]` A **hot-die** platform: 7× below design at 300 K tiles, 22× at 263 K. Host loss matters more than σ at the design point (an 'original'-class host puts `T_min` at 246 K). |
| GaAs at v98 Table 1.1 (η_e 0.9, Purcell 10) | N_opt **2 × 10¹⁹ cm⁻³**, 3.7 × 10⁶ W/mm³ (book 10⁵–10⁶); fixed 890 nm pump `T_min` 259 K, hot limit ~365–380 K; retuned: none | same | v98 (9.6) now matches the balance optimum (80.4 vs 73.9 W/mm³ at Table 9.2). |
| **The extractor's lift never binds on this die.** With the curve as a per-tile cap, every rescue rung reproduces §P0.18.2 with no tile capped | coldest engaged tile **263 K** at 2.60 W/mm² (291 K at 2.00); 0 tiles capped for dye, fixed-pump GaAs and retuned GaAs | `docs/evidence/extractor_armD.json` (§P0.19) | 6 K above the fixed-pump GaAs `T_min`, 56 K above the dye's most pessimistic one. What bounds the array-assisted ceiling is conservation and bistability, not the lift. Scalar 45 K kept alongside (it shapes the plan). |
| **The target device is invisible on this die, and the requirements flow-down is rung 4** | rung 6: plans identical to §P0.18.2 at 2.00–2.60, **0 tiles capped**, 266–632 W/mm² in hand; **rung 2 (near-term film) delivers 17 W of the 198 W** a 2.00 W/mm² rescue needs and runs away; rung 3 delivers 52 W and fails; **rung 4 holds identically** | `docs/evidence/extractor_v98.json` (§P0.20) | 34-core, 88 CFM, target 92 °C, tiles at 263–330 K. The photonic-engineering rungs (broadband Purcell), not the chemistry rungs, are what make the dye a chip cooler at room-temperature tiles; at 400 K tiles the requirement would be a rung lower. |
| A fixed-wavelength GaAs pump has a **hot-side** limit | ~**380 K**, where the Varshni-narrowed gap crosses an 890 nm pump; 3 tiles capped to zero on the 1.15 W/mm² hot-branch baseline, none with a retuned pump | same | v98 §9.3.2 now states it (pump above the gap at T ≳ 365 K; "a single fixed-wavelength pump is a design error over a non-isothermal die") and cites this result. |

### 1.6 The transistor — ASAP7, simulated (§P0.13, §P0.18.3)

All from ngspice 47 + OSDI + OpenVAF BSIM-CMG 110 on the vendored ASAP7 `nmos_rvt` card, fitted to
nothing. `[!]` **One device, one drawn length, no self-heating, no p-FET.** Shapes and temperature
coefficients transfer; per-fin amps and absolute thresholds do not.

| claim | figure | evidence | caveat |
|---|---|---|---|
| The threshold falls with temperature at a physical FinFET rate | **−0.39 mV/K (lin), −0.46 mV/K (sat)**, 250–400 K | `docs/evidence/device_vt_vf_asap7.json` | Constant-current criterion (100 nA × W/L). Compare *slopes* across sources, never levels: the card's 0.284 V and the roadmap's 0.156 V are different devices. |
| The subthreshold swing is near-ideal and rises with temperature | **61.0 mV/dec** at 300 K, **+0.20 mV/dec per K** (ideality 1.02) | same | This, not the roadmap's 82, is the `V_t` lever's cost term — and it is why the lever re-priced (§2). |
| The alpha-power exponent is a fit, and the textbook value survives at room temperature | **1.45** at 300 K (1.35 → 1.62 over 200–500 K) | same | rms 0.04 in ln I. The roadmap model's assumed 1.4 is right *at 300 K*; it is not a constant. |
| The two SPICE evidence files are the same device | `I_off(T)` agrees to **0.76 %** | same | Different decks and sessions on one card. |
| The V/F shape differs from the roadmap's through the threshold, not the exponent | **44 %** at 0.45 V, **< 4 %** above 0.65 V | same, `vf_300K` | With the trace's 3.8 GHz at 0.70 V as anchor, the 10 % overdrive ceiling is 4.17 GHz (IRDS: 4.15). The anchor is a stated choice. |

---

## 2. Withdrawn — do not use

These are ordered by how likely they are to resurface.

| withdrawn claim | say instead | why it failed |
|---|---|---|
| **"The cold-zone prize is 30 % of die power."** | ~6 % or ~14 % (§1.2), or better, the 2.23× | Rested on a static fraction and cache share computed on **one core's leaves against the whole chip's L3**, on the trace's **warm-up slice**. Reproduced exactly and shown to be a scope-and-slice error. |
| **"Yb:YLF is the cold-zone material."** | **Cr:LiSAF** (decided 8 Sep, §P0.21) | Yb:YLF is 2–3 orders below both shipping platforms and a decade below Cr:LiSAF. It is retained **only** so the pre-30-Aug catalogue reproduces. It is not a zone material at all. |
| **"Both thin films cover the cold zone"** (3 Sep rule, as a *zone assignment*) | Cr:LiSAF is the storage-zone material; the dye is the hot-zone material (§P0.21) | True as a *capability* statement at 250–320 K, wrong as an assignment: the dye's transparency cap collapses on cooling (263 W/mm² at 263 K, 11 at 200 K, §P0.20), so it is a hot-die platform. Withdrawn 8 Sep on the user's decision. |
| **"η_ASF ≈ 0.02 is the demonstrated state of the art."** | 0.10–0.60 across MVP stages; 0.32 the working point | That figure is Yb:YLF. The phrase "0.02 demonstrated" must not appear in proposal text. |
| **"The part never reaches its 100 °C spec limit — it runs away first."** | It reaches spec at **every** cooling point tested | An artefact of the recorded curve's hot tail, ~47× too steep at 500 K. The **clocks** in that table survive; the mechanism does not. |
| **"Real functional blocks run at 1–3 W/mm²."** | p90 = 13.2 W/mm²; cALU reaches 29.2 W/mm² | Contradicted by the literature (>8) and by our own floorplan. |
| **"A monolithic die can be zoned hot and cold."** | 1.24 K of gradient for 40 W — the cold zone needs a separate die | Two independent methods agree to 1.7×. Lateral conduction shorts the zones. |
| **"Fan power scales as R⁻⁵; worth 22–35 % of system power."** | linear in heat carried; at today's extractor the optimum is baseline airflow | Used the textbook affinity law, not the calibrated fan. |
| **"The flat-die ceiling is 1.0–1.2 W/mm²."** | 0.85–0.90 W/mm² | Two independent corrections (leakage curve, per-core accounting) both push it down. |
| **"The simulated curve makes the ceiling *higher* (gentler hot tail)."** | it depends which side of **345 K** the point sits | The curves cross at ~345 K. Cool points destabilise, hot points stabilise. **Neither direction is true on its own.** |
| **"`core_other` is McPAT's un-itemised per-core power."** | true for **leakage only**; there is no un-itemised dynamic | McPAT itemises 100 % of a core's dynamic power. The slab is real for leakage (~30 % of a core's) and fictitious for dynamic. |
| **"The static fraction is safe under the accounting fix (18.43 → 18.59 %)."** | 18.43 % → **32.03 %**, a factor 1.74 | The first correction was computed with a text parser that split names at `:`, silently dropping `Integer ALUs (Count: 6 )` and the other execution rows. |
| **"The `__agg__L3` bug fires at MR target ≤ 45 °C."** | the trigger is **arm-dependent**, not a target threshold | The same point raised in arm B and completed in arm D. The bug fires on the synthetic key's *temperature*, which moves with the leakage curve and the accounting. |
| **"Cost is dominated by how much margin you demand."** | superseded — see `PHASE0_CHECKLIST.md` §P0.7 | |
| **"Recovery alone never beats liquid at any T_h."** | superseded | |
| **"The granularity penalty is 30 % larger on the measured curve (1.30× → 1.70×)."** | it does not clearly move — 1.29× vs 1.18× normalised | The raw ratio is a landing-point artefact; correcting to a common peak **reverses the ordering**. |
| **"A 50 mV `V_t` reduction costs ~22 K of cooling, 75 mV ~33 K — both inside the demonstrated 45 K."** (`LADDER_GEN0` §2) | 25 mV ≈ **22–30 K**, 50 mV ≈ **45–60 K**, 75 mV ≈ **67–90 K** (§P0.18.3); only the 25 mV step is inside 45 K | Priced on the pipeline curve's doubling temperature (10.9 K) and the roadmap's 82 mV/dec. The simulated curve doubles every 19–23 K above 345 K and the card's swing is 61–81 mV/dec over 300–400 K; both terms moved against the lever. Still a re-derivation, not a thermal measurement. |
| **"The dye extractor delivers 819 W/mm² at 300 K with `T_min` 207 K."** (5 Sep evidence, §P0.19) | the v98 target device: 813 W/mm² at 300 K *after* the photonic ladder, 0.03–0.09 for the bulk film; `T_min` 176 K | Rested on v91 eq. 8.4 (every chromophore cycling at the Purcell rate), which v98 withdraws: stimulated emission caps the excited fraction at `x_max` ~ 10⁻³–10⁻⁴. The coincidence of the two 300 K numbers is the design point's Purcell factor (100) offsetting `x_max`, not a confirmation. |
| **"The array's area is un-modelled, so every density ceiling is optimistic."** (`ARCHITECTURE_EVOLUTION` §4, `START_HERE`) | the control-arm ceilings (§1.3) **cannot** move with it; what it bounds is the array-assisted ceiling and cost — see §P0.18 | In the v91 device the tiles, couplers, waveguides and monolithic-backside LPC are stacked *above* the silicon and share the pixel layer's footprint; they take no logic area. The honest correction is an areal coverage on the pixel layer, and the control arm has no pixel layer. |

---

## 3. Open — not measured, do not derive

| question | why it matters | what it needs |
|---|---|---|
| **Should `--leakage-curve` default to `simulated`?** | The shipped default is currently a combination nobody measured. It is the largest single mover (57 of 145 points). | **Recommendation made, not applied (§P0.18.0): flip to `simulated`**, making the default arm D exactly (measured 159/159). The reproducibility argument for `pipeline` was spent when the other two defaults moved; every §1 number already sits on `simulated`; `pipeline` is not a device. The flip touches four driver defaults, one test, the `CLAUDE.md` rule and §0 above. **The user's call.** |
| **Maximum temperature lift of the stage (`dt_max`)** | Was load-bearing: the measured 34-core rescue failed on it, and the 50 mV `V_t` step sits at 45–60 K. | `[+]` **Reframed and measured (§P0.19).** With the extractor's own curve as the per-tile cap, no tile on this die is ever driven within 6 K of any platform's `T_min` (coldest 263 K at 2.60 W/mm²) — the lift does not bind. The remaining ask is to *confirm the bracket*: the dye tail at the pump at two temperatures, the host loss on a SMILES film, and pump retuning for GaAs. `[!]` The scalar 45 K still binds the **1.15 W/mm² baseline-path** point (hot-branch baseline, 45 K lifted, 111 °C) while 850 W/mm² was available — a planner-mode limitation, §3 below. |
| **η_ASF(T) curve inside each thermal window** | Zone-by-zone extractor selection needs it. | v91 gives the principle and the endpoints, not the curve. |
| Behaviour above 400 K | Neither shipping platform is tabulated there; McPAT refuses input there. | Does not bind today — report >127 °C as non-viable rather than as a number. |
| **The `V_t` lever, measured end to end** | Its two inputs are now the card's (§1.6) and they re-priced it 2× dearer in cooling (§2). Whether a low-`V_t` die under the array actually holds is a coupled solve nobody has run. | `clock_headroom.py --vf-source spice` exists; a run needs a leakage reference scaled by the simulated `10^(ΔV_t/SS(T))` — and `dt_max`. |
| **LPC dissipation on the tile stack** | The monolithic-backside LPC converts at η_LPC; the rest of `optical_to_lpc_W` is heat *on the cold-plate side of the tiles* (v91 Table 2.3's "no bulk-loop waste" holds only for external recovery). At the 88 CFM rescue that is ~6 W into a 0.32 K/W package, ~2 K on the whole die. | Not modelled. A second heat source on the pixel die, or a sink-load term. Small, and stated rather than pretended. |
| Whether a tile-scale array sustains 1000 W/mm² over a 500 µm tile | The bench figure is a **local** density over 0.01 mm². | Pump delivery and parasitic load. Shows up as the plan hitting `h_max`, which `run_mr_clipping` already reports. `[+]` The per-tile ledger (§P0.18.2) says the demand on this die never exceeds **41 W/mm²** even at quarter coverage, 25× under `h_max`. |
| ~~**Two planner limits exposed at the top of the coverage ladder**~~ **closed (§P0.19)** | The injected-power energy cap let the array remove 12 W more than the cooled die dissipated at 2.60; nothing bounded a tile. | Both built and measured: `--mr-energy-cap converged` takes the 2.60 rung away (§1.3), and the per-tile extractor cap (`extractor_tile_caps`) binds nowhere on this die. |
| **The planner's plan *shape*** | The scalar `dt_max` shaped the envelope (`45 K / s` per block at the seed sensitivity, i.e. uniform per block); with the extractor curve alone the envelope is area-weighted and the minimum plan lands ~30 % dearer with nothing physical binding (§P0.19 smoke test), and at 2.40 W/mm² the curve-only descent lands on the hot branch. | A minimum over shape as well as scale — e.g. sensitivity-weighted seeding of the envelope — so the reported cost stops depending on which cap happened to shape it. |
| ~~**Which extractor covers which zone — v98 versus the 3 September correction**~~ **decided 8 Sep (§P0.21)** | v98 Table 10.8 put Yb:YLF in the cold zone and the dye at the hot end; the 3 Sep rule said both thin films cover the cold zone. | **User's decision:** the storage (cold) zone material is **Cr:LiSAF** (`make_extractor('cr-lisaf')`, v98 §8.1.2 / Table 1.1), the hot zone is the dye, Yb:YLF stays out of every zone. And the **default cold plate is single-material**: a floorplan-matched dual-material array is a per-architecture product, which defeats the architecture-agnostic premise; `--mr-zone-mode dual` exists to *measure* it once the floorplan is a swept variable (Phase 2) or the array is integrated at die manufacture. |
| **Cr:LiSAF at its demonstrated η_EQE** | v98 Table 8.4: the platform needs η_EQE > 0.94 and the best crystals demonstrate 0.85–0.95, so at 0.90 the curve is *negative* (heating). Every Cr:LiSAF figure in §1 is a ceiling at η_EQE = 1. | A measured η_EQE on a Purcell-enhanced Cr:LiSAF film; until then the storage-zone tile's capability is an upper bound, not a number. |
| **A hot-branch baseline defeats the baseline planning path** | At 1.15 W/mm² under arm D the idle array holds the die on the hot branch (184 °C); the baseline path then lifts 45 K and stops, or with the curve alone runs out of iterations at 1.7 W. The recorded catalogue never met this because idle diverged there under its physics. | Hand a baseline that holds *above target by more than the scalar lift* to the envelope path. |

---

## 4. Standing constraints that bound everything above

- **One die.** 34-core 7 nm skylake only. ISA variants, the accelerator die and n-core sweeps are
  parked; nothing here generalises across floorplans without re-measurement.
- **Above ~127 °C report "non-viable", not a number.** McPAT refuses input outside 300–400 K and
  the leakage curve is extrapolated past its table.
- **Sub-ambient figures are a bracket, not a point.** ASAP7 is a *predictive* PDK and its GIDL
  coefficients are a model choice. Quote across both brackets.
- **An `unconverged` solve is neither a hold nor a failure.** It must never become a ceiling or a
  rescue. 4–20 rows per catalogue arm are in this state.
- **The floorplan-pack images are third-party subscriber content.** Numbers derived from them may
  be published; the plates may not.
- **MR *costs* are not comparable across leakage curves** unless normalised to a common peak — the
  minimum-plan descent stops wherever it first holds target. This has reversed a sign twice.
