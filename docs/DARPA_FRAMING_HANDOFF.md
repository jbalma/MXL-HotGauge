# Handoff to the DARPA proposal work — what the simulation results will and will not support

**30 August 2026.** Written for whoever is drafting proposal text, so that claims made there are
ones this repository can defend under questioning. Everything below is measured in
`docs/evidence/` unless labelled otherwise. Where a number rests on an assumption, the assumption
is named.

**Read this first, because it changes the pitch.** Over the last two days the central cooling
comparison was found to have been scored in the wrong regime, rebuilt four times, and the claim
that survives is **narrower and more specific** than the one the earlier material supports. Text
written against the older framing will not survive a technically competent reviewer.

---

## 1. The one-sentence claim

> Photonic microrefrigeration is not a cheaper way to move heat. It is **the only cooling
> mechanism that can be aimed at a hotspot**, which makes it worth having exactly where a die is
> hotspot-limited, and worth more the deeper the thermal rescue — because it is the only mechanism
> whose cost per watt does not diverge with rescue depth.

Everything defensible follows from that sentence. Everything that got us into trouble came from
trying to claim more.

## 2. What NOT to claim, and why each fails

| Do not claim | Why it fails |
|---|---|
| "Photonic cooling beats liquid on efficiency" | It does not, at any temperature swept, **in the regime we have modelled** (T_h ≲ 400 K, where φ is small). Net COP ~3 against a cold plate's ~20. The rescue and high-T_h regimes are the case to make instead. |
| "Exergy recovery makes the loop competitive" | Recovery improves the ledger by ~2×; it does not carry it. Against a cold plate the array is **12.9× short** per watt removed. |
| **"The loop self-powers at our design point"** | **`[!]` Withdrawn 30 Aug.** Our own accounting reported this, from a ledger missing the Carnot factor on the anti-Stokes term. Corrected, the loop gain is 0.821 at 350 K and **0.958 even at 1000 K** — it never reaches 1.0 at any temperature silicon survives. |
| "The loop is self-powering, therefore it wins" | Self-powering (loop gain 1.05 at 450 K) says the loop pays for *itself*. It still costs **+26.4 W** more system power than a pump. These are different claims and conflating them is the single easiest way to lose credibility. |
| "Finer tile pitch is better" | Only on a concentrated hotspot. On a uniform die the pitch ladder is **flat to slightly inverted** — granularity buys nothing. |
| "A three-zone die (hot logic / cold cache) delivers the architecture" | **Not buildable as a monolithic die.** 40 W of removal buys **1.24 K** against the 150 K the architecture asks. Two independent failure modes, confirmed analytically to 1.71×. |
| Any absolute peak temperature from the older catalogue | The floorplans carried a 22 % unallocated slab acting as a heat spreader. Rebuilt on published block areas the same dies run **7–24 K hotter**. Absolute temperatures are optimistic by tens of kelvin. |

## 3. What IS defensible, with the numbers

**The rescue regime is the only one where the comparison matters.** Below a cooler's thermal limit
the cheapest pump wins by construction (cold plate: system COP **20**). Above it, the three
mechanisms diverge by their exponents:

```
more airflow      P_fan ∝ R^-5              900 W die needs a 35,840 W fan
sub-ambient       COP = η₂·T_in/(T_a−T_in)  system COP 20 → 0.15 over 4× overload
laser at T_j      cost per watt FLAT, recovery rises with T_h → floors near 1.8
```

The physical argument is about **where each machine is forced to operate**: the chiller at the
coldest point in the system, where its COP is worst and still falling as the rescue deepens; the
array at the hottest point, where the Carnot factor is largest. They move in opposite directions
against the same variable. That is why a crossover exists and why it is not delicate.

**The crossover is scale-free.** Required inlet temperature depends only on the overload *ratio*,
so the array overtakes at **2.64× / 2.88× / 2.85×** the unaided limit for fan, cold plate and
microchannel alike. The baseline sets the absolute watts, not the crossing point.

**Aimed at a hotspot, the array leads; aimed at a flat die it does not.** Measured, in kelvin of
peak reduction per electrical watt: aimed **0.750** (**1.102** net of leakage) against a chiller's
**1.032** at 42 K and falling — so charged gross the array **loses** there, overtaking only past
**112.5 K** of depth, or **24.5 K** once leakage is credited. On a uniform shape
the array manages 0.563 and needs 159.5 K — the ordering reverses.

**`[+]` The leakage credit, which no prior ledger counted.** Holding a 34-core die at 90.6 °C
instead of 133.8 °C drops what the chip itself draws from **124.9 W to 91.7 W — 26.6 %**. That
takes the array from **2.473 W/W gross to 1.683 W/W net**, about 1.5×, and it is largest exactly
where the rescue is most needed.

**`[+]` Efficacy is flat, then cliffs, and the cliff is predictable.** Holding everything but
budget fixed: **1.854 K/W flat from 1 W to 16 W**, then marginal efficacy collapses to 0.133 by
32 W. 16 W is exactly the target block's own power. Up to it the target *is* the die peak; past it
another block is, and further watts aimed at the original target buy almost nothing.

**Pitch and plan size are close to separable design variables.** Coarse tiles delay the cliff
substantially (50/200 µm after 16 W, 500 µm after 24 W, 2000 µm not at all by 45 W) but the delay
is bought with plateau height and never pays: fine pitch wins at **every** budget measured. So
tile geometry cannot buy past a bad power map in either direction.

## 4. The design rule worth proposing

> Size the array plan to **level the target block with the runner-up**, then **re-aim** rather than
> spend more.

The sizing quantity is `peak_to_runner_up_gap_K` — a floorplan metric measured here, found weaker
than `relative_plateau` at predicting cost, and nearly set aside. It is weak at predicting cost and
it is exactly the right quantity for sizing a plan. This is a concrete, testable contribution and
it is cheap to defend.

## 4b. `[+]` What the v91 materials chapter changes — read this before writing anything

**Yb:YLF is not the platform and "0.02 demonstrated" must not appear in proposal text.** At
1–10 W/mm² it is two to three orders of magnitude below the current platforms, and it is now
correctly scoped as the **cold-zone** material only.

v91 Table 8.2 gives two platforms at **10³–10⁴ W/mm²**:

- **Direct-bandgap GaAs/GaInP epitaxy** — η_EQE ≤ 0.99 (low-temperature), monolithic with a
  co-designed multi-junction LPC. Cost is MBE/MOCVD lattice-matched growth and a substrate
  form-factor constraint.
- **SMILES-R640-in-polymer thin films** — the same cooling density at **room temperature**,
  solution-processed, on **any planar substrate**, with η_EQE 99 % at Nt ≳ 10⁻² M. SMILES =
  Small-Molecule Ionic Isolation Lattices; cyanostar macrocycles sterically prevent the aggregation
  and reabsorption that cap the solvent-phase system at ~10⁻³ M. *(Not the chemical-notation
  format — unrelated abbreviation.)*

Anti-Stokes ladder (Table 8.1, R101/R640, λ̄_f = 605 nm): η_ASF **0.124 at a 680 nm pump**, rising
to **0.221 at 740 nm**. Deeper red-tail pumping widens the shift; the constraint is that σ_a falls
in the tail, which is exactly what the SMILES concentration lift resolves.

**`[!]` Attribution discipline.** Table 8.1 supports 0.12–0.22. **η_ASF > 0.30 is our current
experimental claim and sits beyond the tabulated range** — write it as our result, not as the
book's, and be ready to show the measurement. It matters because 0.30 is the threshold that closes
the loop in the 400–600 K hot-compute zone.

## 4c. The architecture argument, in the book's own terms (v91 §1.18)

The budget inequality is (1.31): `α·N_tr·C_eff·V_dd²·f + P_static(V_dd, T_j) ≤ ΔT_lim·A_die / R_die`.
Microrefrigeration at flux fraction *s* moves it to (1.32): `P_max(s) = ΔT_lim·A_die / [(1−s)·R_die]`.

- **s = 0.5 doubles the architectural power cap; s = 0.9 grows it tenfold.**
- In the **cubic** regime (V_dd tracking f), doubling the cap buys 2^(1/3) ≈ **1.26× frequency**;
  tenfold buys **2.15×**. That is "top boost clock set by transistor physics rather than by the
  package".
- The **V_th trap** (1.28): `I_leak ∝ (W/L)(k_BT_j/q)²·exp(−V_th/(n·k_BT_j/q))`. A 10 K rise roughly
  doubles leakage; 60 mV of V_th buys a decade. **Pushing T_j down does the inverse on both counts
  at once** — it suppresses P_static exponentially *and* relaxes the V_th lower bound, letting the
  architect use lower-V_th cells, which raises f per (1.27) without paying the cubic V_dd penalty.
- **This is the two-sided design point**: run logic hot to raise φ and the recoverable exergy, while
  running the static-power-dominated regions (cache, V_th-limited cells) cold to extend the V/F
  envelope. Our measurement that **89 % of static power sits in L3 alone** says the cold zone is
  not a partition anyone has to impose — it is already where the leakage lives.

**`[!]` Every recovery number above is the second-law value.** Figures recorded before 30 August
2026 used a first-law ledger that was **1.419× too favourable to the array**; Test 7 corrected it
and Tests 6c–6e were re-run. If you find an older array cost quoted anywhere, it is optimistic.

## 5. Honest gaps — name these before a reviewer does

0. **`[!]` Required η_ASF against die temperature — corrected 30 Aug, twice.** Self-powering
   needs, at η_P = 0.85 and η_cpl = 1:

   | T_h | 350 K | 400 K | 450 K | 600 K | 700 K | 1000 K |
   |---|---|---|---|---|---|---|
   | required η_ASF | 1.12 | 0.67 | 0.51 | **0.35** | **0.31** | 0.25 |

   Read the other way — **how hot must logic run for a given extractor to close the loop**:

   | η_ASF | η_P = 0.85 | η_P = 0.90 | η_P = 0.95 |
   |---|---|---|---|
   | 0.12 (SMILES @ 680 nm) | never | 3983 K | 525 K |
   | 0.22 (SMILES @ 740 nm) | 1491 K | 596 K | 388 K |
   | **0.30** | 716 K | **469 K** | 358 K |
   | 0.35 | 595 K | 432 K | 347 K |

   Validated against the book's own worked Examples 1–3 (§1.12) to three figures.
   (`loop_model_reconciliation.json`.)

1. **`[!]` η_P — the laser wall-plug — is now the binding term, not the extractor.** The
   requirement is `[1/(η_P·η_cpl) − 1]/φ`, and that numerator is very steep near unity. At
   η_ASF = 0.30, moving η_P from 0.85 → 0.90 drops the self-powering temperature from **716 K to
   469 K**; at 0.95 it reaches 358 K. §1.12 Example 3 makes the same point about η_cpl: a single
   20 % front-end loss roughly **doubles** the extractor target. **With the v91 materials the
   extractor is no longer the hard part — the laser and the optical path are.** That is a
   different programme from the one this project had been costing, and proposal text should be
   built around it.

2. **η_ASF(T_h) is answered structurally, not numerically (v91 §8.4).** A heterogeneous die does
   **not** use one extractor material across its area. Yb:YLF/Yb:silica for cold storage tiles
   (150–300 K), Yb:ZBLAN or fluoride glass for warm interconnect (300–400 K), Ho³⁺/Tm³⁺ fluorides
   or Cr³⁺ colquiriites for hot compute (400–600 K), SiC:Er or GaN:Yb above 600 K — the same
   wide-bandgap families as the compute devices there. **Per-tile temperature targeting requires
   per-tile extractor selection.** What is still unmodelled is the numerical η_ASF(T) curve within
   each window.
3. **The power model cannot see either zone the architecture wants.** McPAT refuses temperatures
   outside **300–400 K**; the three-zone template spans 150–600 K. The hot end needs SiC/GaN and is
   a materials claim this toolchain cannot evidence.
4. **The cold-zone prize is uncertain by ~2.3×.** Our calibrated leakage curve flattens at 310 K
   and clamps below; the architecture assumes it keeps falling to 200 K. That is 13.5 % of die
   power against 31.7 %. **PTM SPICE cards would settle it in an evening** and it is the highest-
   value open item.
5. **The hottest block on every die here is an accounting entry.** All dies peak on the
   results-broadcast bus, which the power model reports as area overhead and the tiler places at
   105 W/mm² against 1–3 for real silicon. It distorts peaks by a few kelvin — except on the
   largest core, where it carries 9× the power and the die has no steady state.
6. **The cold zone must be a separate die.** A monolithic three-zone die fails two independent
   ways: coarse pitch cannot address the zones (2000 µm is 170× worse than 100 µm) and lateral
   conduction shorts them anyway (~70× at best pitch). This *relocates* the architecture into a
   packaging and disaggregation programme rather than refuting it — and on a separate cache die the
   gradient problem disappears, because you cool the whole thing.
7. **Single-target plans, one shape, one burial.** The cliff result is a single aim point; the real
   rescue spread across 1126 targets. Linear solves without leakage feedback except where stated.

## 6. What is still running

A leakage-coupled repeat of the budget sweep (`scripts/mr_budget_leakage_sweep.sh`), to see whether
feedback moves the cliff. The first attempt diverged at every rung — 65 W / 0.3 K/W has no steady
state on that stack — and a probe found 15–35 W usable; the operating point is being reselected. Two effects run opposite: cooling cuts leakage so a watt removed takes
more than a watt out of the die (pushes the cliff later), but leakage is steepest at the hottest
block so the target sheds power faster than its neighbours (brings migration sooner). Not yet
resolved — **do not write proposal text that depends on which way it goes.**

## 7. Where to look

| Claim | Evidence |
|---|---|
| rescue regime, three mechanisms | `thermal_limit_rescue.json`, `rescue_measured_anchor.json` |
| aimed vs bulk, granularity | `aimed_vs_bulk_rescue.json` |
| budget cliff and its cause | `mr_budget_saturation.json` |
| pitch × budget grid | `mr_budget_pitch_grid.json` |
| per-baseline hybrid ledger | `hybrid_cooling_ledger.json` |
| withdrawn single-baseline comparison | `liquid_vs_photonic.json` (kept, labelled) |
| three-zone verdict | `thermal_zone_tests.json`, `thermal_zone_separability.json` |
| exergy machinery and φ table | `exergy_map.json`, `exergy_vs_cop.json` |

Live state: `docs/PHASE0_CHECKLIST.md` (tests 6–6g). Programme: `docs/POWER_RECOVERY_PLAN.md`.
Narrative: `docs/HANDBOOK.html`, 30 August status section.
