# The power-recovery reframing — what changes, and what it costs to find out

Programme document, written 29 August 2026 against `docs/Photonic_Cooling_Devices___v9.pdf`
§§1.4, 1.10–1.17 and 10.8. It supersedes nothing; it states an **objective change** that touches
most of what the project measures, and separates the parts that are now measured from the parts
that are still argument.

Companion documents: `docs/PHASE0_CHECKLIST.md` (live state), `docs/LADDER_GEN0.md` (the
generation-0 rung), `docs/EXECUTION_PLAN.md` (the plan this sits inside).

---

## 1. The objective has changed, and it is not a refinement

Every result in this repository scores cooling by **temperature**: peak pulled down, margin held,
watts spent. That is the right score for *holding a thermal limit*, which is what the whole
catalogue measures.

The book adds a second axis that runs the other way. Heat lifted from a chip at `T_h` carries
exergy `φ = 1 − T₀/T_h`, so **the hotter the source, the more of that heat is convertible back to
work**:

| `T_h` | 350 K | 400 K | 500 K | 600 K | 700 K |
|---|---|---|---|---|---|
| `φ` | 0.157 | 0.262 | 0.410 | 0.508 | 0.579 |

*(reproduced exactly by `HotGauge/thermal/exergy.py`)*

Two consequences the project has never had to face:

1. **"Cool everything" stops being obviously right.** Dynamic-power-dominated logic is worth
   running *hot*, because its waste heat is worth more. Static-power-dominated SRAM is worth
   running *cold*, because leakage carries `exp(−V_th/(n k_B T_j/q))`. Those two live in different
   places on the die, and only spatially-selective cooling can serve both.
2. **The loop can close.** The sharp self-powering condition `η_L η_c [1 + η_AS φ] ≥ 1` (1.15)
   is nearly unreachable at 350 K and comfortable at 600 K: the required `η_AS` falls from
   **1.77** (impossible) to **0.55** (plausible). `T_h` is therefore a *design knob*, not an
   inherited property.

## 2. `[!]` The single largest trap: which temperature goes into φ

`φ` is set by the temperature of the reservoir the heat is lifted **from** — the anti-Stokes
extractor in the cold plate, **not** the silicon junction. They differ by the conduction drop up
through the die, which grows with burial depth and with power density.

**Measured** (`examples/thermal_zone_probe.py --mode extractor`, Test 2 below): the drop is
0.91 K at 0.60 W/mm² and 3.03 K at 2.0 W/mm² at 200 µm burial — roughly linear in density, so it
reaches tens of kelvin at the densities §10.8 contemplates for hot compute islands.

**Reading φ off the junction always overstates recoverable work.** `exergy.exergy_map` records
which reservoir was used so a result cannot silently answer the wrong question.

## 3. What this changes in the pipeline, part by part

| component | today | under the reframing |
|---|---|---|
| planner objective | minimise watts to hold a margin | zone-additive net balance, eq. (10.29) |
| extraction policy | removal ∝ **power density** | allocation by marginal benefit; projection unchanged |
| floorplan metrics | plateau width, span, gap | zone **separability**; per-tile exergy |
| per-tile target | one global `target_K` | per-zone `T_h`, some deliberately *raised* |
| scoring | K per W | K per W **and** W of exergy per W removed |

Two of these are built and measured (`thermal_zones.py`, `leakage_targeting.py`, `exergy.py`);
the planner objective is not.

## 4. `[!]` The domain limits that bound every claim here

These are not caveats, they are the boundary of what this toolchain can evidence, and they should
be stated before any of it is pitched.

- **McPAT rejects temperatures outside 300–400 K** — *"Temperature must be between 300 and 400
  Kelvin and multiple of 10"*. §10.8's template spans **150–600 K**. Only the middle zone is inside
  the model.
- **Cold end**: our calibrated curve stops at 310 K and *clamps* below. §10.8 claims 100–200×
  leakage reduction for 350→200 K; our local doubling constant is already **274 K at 310 K**,
  which would give ~2×. **That is a ~50× disagreement on the cold-zone prize** and it is the
  highest-value open question in the argument. **PTM SPICE cards (ptm.asu.edu, free, 7 nm) would
  settle it.**
- **Hot end**: extrapolating our curve to 600 K gives ~10⁵× leakage. Silicon is not viable there,
  which is why §10.8 specifies SiC/GaN and refractory metallisation — so the hot-zone claim is a
  **materials** claim and nothing in this repository can evidence it. The exergy half needs no
  model (`φ = 1 − T₀/T_h` is exact); every chip-side consequence is unmodelled.
- **`η_AS(T_h)` is not modelled at all.** Chapter 1c notes it rises with `T_h` to the extractor
  material's quenching temperature and turns over above it, putting a material-dependent optimum
  on `T_h`. Every "hotter is better" statement here carries that unmodelled ceiling.

## 5. The test programme

Ranked as agreed. Status as of this document; results land in `docs/evidence/`.

| # | test | outcome | evidence |
|---|---|---|---|
| 2 | extractor temperature vs burial × pitch × density | **prerequisite discharged** — reading φ off the junction is good to 8.2 %, peaking near 2 W/mm² | `thermal_zone_tests.json` |
| 1 | heterogeneous zones: achieved vs demanded gradient | **`[!]` not buildable** — 40 W buys 1.24 K against 150 K; two failure modes; confirmed analytically to 1.71× | `thermal_zone_tests.json` |
| 3 | per-tile exergy map | done — collapsing to one temperature costs only 0.3–0.6 % | `exergy_map.json` |
| 4 | exergy-optimal vs COP-optimal extraction | a **narrow but real** frontier — same direction, different winners | `exergy_vs_cop.json` |
| 5 | constant-power ISA redo | done — **all 42 converge**, correcting a recorded result; compact die hottest *and* cheapest | `isa_constant_power_pack.json` |
| 6 | bounded liquid comparison | **`[~]` superseded** — one baseline, and no junction limit at a fixed 250 W | `liquid_vs_photonic.json` |
| 6b | every cooler alone vs. that cooler **+ laser** | fixes the baseline gap — fan hybrid wins on per-watt cost, but in 3 rows of 72 and at `η_AS = 1.0` | `hybrid_cooling_ledger.json` |
| 6c | pricing the **rescue** of an inoperable die | the comparison that means something — chiller COP collapses with depth, laser cost stays flat; crossover **scale-free** at 2.6–2.9× the unaided limit | `thermal_limit_rescue.json`, `rescue_measured_anchor.json` |
| 6d | the **aimed** rescue, hotspot only | granularity is worth **2.77×** on a hotspot and **nothing** on a flat die; crossover falls to 33 K | `aimed_vs_bulk_rescue.json` |
| 6e | budget sweep, one shape, 1→45 W | efficacy **flat to 16 W** then cliffs — the fade is a discrete event when the target stops being the peak, not decay. Rule: **size the plan by `peak_to_runner_up_gap_K`, then re-aim** | `mr_budget_saturation.json` |

**All six are complete**, and test 6 was then re-run twice more (6b, 6c, 6d) after review found it
had been scored against a single baseline and on an operating point at 108 °C that no fan can run.
The two tests that matter most still came back negative, which is what they were run for.

**`[!]` The claim to carry forward is narrower than the one this plan started with.** The array is
not cheaper cooling — on every bulk comparison it loses to a pump. It is *the only mechanism that
can be aimed*, worth having where the die is hotspot-limited and worth more the deeper the rescue,
because its cost per watt is the only one that does not diverge with depth. Recovery improves that
ledger by about 2×; it does not carry it. **Settled since**: the budget sweep (6e) shows efficacy is flat
to the target block's own power and then cliffs when the peak migrates — so the aimed advantage
survives at scale provided the planner **re-aims** instead of over-driving one block. **Open**:
whether the cliff moves with pitch, and the same sweep with leakage feedback in the loop.

**Deliberately not run**: transients and the sustainable-clock re-run. Both are worth more as
*stated gaps* than as rushed numbers — but state them **accurately**:

- **Transients are not blocked on trace length.** `tau` is ~2.2 ms and the 3.2 ms trace covers
  ~1.5 of it. The blocker is that the trace's burstiness sits in LoadQ/TLB/ICache/IMC while the
  *hot* units are flat (median unit swing 0.0 %), so there is nothing for pre-cooling to
  anticipate. It needs a workload with phase behaviour in the **compute** units — a data problem,
  not a modelling or trace-duration one.
- **The sustainable-clock re-run is blocked on a product V/F curve**, and the pack supplies the
  first real anchors this project has had (§7 below).

## 5a. `[!]` What the six tests changed about the argument

Three things a reader of §10.8 would not expect, all measured:

1. **The monolithic three-zone die is not buildable** — and it fails two independent ways, so
   fixing either alone does not help. This relocates §10.8 to a packaging and disaggregation
   programme; it does not refute it, and on a separate cache die the gradient problem disappears
   entirely because you cool the whole die.
2. **Self-powering is not the same as beating liquid.** The loop self-powers above 450 K and still
   costs more net system power than a cold plate, because liquid's COP is ~20 and photonic's ~3.
   Recovery improves the ledger; it does not carry it. **The case has to rest on what liquid
   cannot do at all.**
3. **Good cooling is self-defeating for recovery** — φ is set by T_h, so every kelvin the cold
   plate wins is exergy it destroys. That tension is real, it is quantified, and it is the
   sharpest statement of why the architecture has to change rather than just the cooler.

## 6. What would change the plan

- If Test 1's achieved gradient saturates far below the demanded one — which
  `thermal_zones.py` predicts analytically at 3000–6300× — then §10.8's template is a
  **packaging and disaggregation** programme before it is an architecture one, and the ISA work
  should target chiplet-level partitioning rather than intra-die zones.
- If the PTM leakage extension shows the floor sits near 150 K as the book assumes rather than
  near 330 K as our curve suggests, the cold-zone prize grows ~50× and the leakage-targeted
  allocation policy stops being a tie-breaker and becomes the primary objective.
- If `η_AS(T_h)` turns over below 500 K, the hot-zone argument caps out well short of the
  600 K design point and the whole template compresses toward the middle.
