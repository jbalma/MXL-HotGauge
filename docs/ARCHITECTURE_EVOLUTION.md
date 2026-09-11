# How architectures should evolve for a photonic cold plate

**Written 3 September 2026.** What six weeks of measurement says about the *shape* a core should
take when it is cooled by a targeted photonic array rather than by a uniform cold plate — and what
still has to be measured before any of it is licensable.

`[!]` Read `docs/RESULTS_REGISTER.md` first. Everything below marked **measured** has a JSON behind
it; everything marked **argued** is reasoning from measured things, and everything marked **open**
is neither.

---

## 1. The one-sentence version

**A photonic cold plate does not make a die uniformly cooler — it makes cooling *selective*, and
selectivity is only worth paying for if the architecture gives it something to select.** The design
consequence is a die that is deliberately *more* thermally heterogeneous than a conventional one:
hot, dense functional units that would be untenable under uniform cooling, next to cold caches that
are cold because leakage — not heat — is what caches cost.

---

## 2. What is measured, and what it implies

### 2.1 Concentration costs density — and that is the lever, not the problem

**Measured.** Flat (Gini 0) power map holds **0.85–0.90 W/mm²**; the real, concentrated map holds
**0.60–0.65**. Ratio **1.4×** (`results/uniform_density_armD/`).

Read conventionally, that says *spread your power out*. Under a photonic array it says the
opposite, and this is the central inversion:

- Under **uniform** cooling, concentration is a pure liability — you pay the ceiling penalty and
  get nothing.
- Under **targeted** cooling, concentration is what makes the array *efficient*. A cooler that can
  put 1000 W/mm² onto a 142 × 115 µm block is wasted on a die whose power is smeared evenly.

`[!]` So the 1.4× is not an argument against concentration. It is the **size of the deficit the
array has to close**, and the measured rescues say it closes it: at 1.15 W/mm² — well past the
0.60–0.65 shaped ceiling — the unassisted die has no steady state at any airflow and the array
holds target at all of them (**35/35 points**). **Measured under corrected inputs (§P0.18.2):**
the unpowered array fails at 1.20 W/mm² and the laser holds from there to **2.60**, removing 17 W
at 1.20 and 139 W at 2.00. `[!]` The 2.60 is an *envelope* number — the array is carrying all of
the heat there — so the architectural statement is the *range*, not the top rung.

### 2.2 The heat is already concentrated, and we know where

**Measured** (`docs/evidence/mr_catalogue_curve_compare.json`, and the per-block power map):

| block | footprint | power density |
|---|---|---|
| **cALU** | 142 × 115 µm | **29.2 W/mm²** |
| iALU | 142 × 229 µm | 8.2 |
| FPUs | 458 × 345 µm | 4.4 |
| core_other (leftover slab) | 454 × 1027 µm | 0.4 |

`[+]` Independently corroborated: the upstream HotGauge hot-spot study puts its hot spots on the
same cALU/ALU cluster, aggregating over single-threaded benchmarks. Two different methods, same
answer.

**Implication (argued).** The cooling target is a *small, identifiable, architecturally meaningful*
region — the integer/complex ALU cluster — not a diffuse warm area. That is the best possible news
for a targeted cooler and it is why the optics requirement is loose (§2.3).

### 2.3 The optics requirement is set by the floorplan, and it is loose

**Measured.** Tile pitches of 50, 100 and 200 µm cost **19.476 / 19.476 / 19.470 W** — identical to
four significant figures across an **813× range in tile count**.

**Implication.** The array does not need to resolve individual devices. It needs to resolve
*functional units*, and those are 100–500 µm. **200 µm pitch buys everything 50 µm buys.** That is
a manufacturability result as much as a physics one: it relaxes alignment, pump routing and tile
count by orders of magnitude.

`[+]` **And the array need not cover the die (§P0.18.2).** A quarter-coverage array — 250 µm
tiles on the 500 µm pitch, three quarters of the footprint free for couplers, waveguides and the
LPC — holds the same ceiling on the same minimum plan to ~1 %, with 644 of 1126 blocks under a
gap. The 200 µm burial smears the gaps as it smears the pitch. So the optics requirement is
loose in *two* dimensions: pitch and fill. What rises is the per-tile flux (35 W/mm² at 0.26),
still 25× under the platform's 1000.

`[!]` Coarser than ~200 µm *does* degrade — a coarse tile spends its watts on silicon that was
already cool. And the ordering **reverses with the workload**: a coarse array wins on a degenerate
plateau because one tile clips several members together; a fine array wins on an isolated hot spot.
Which dominates is a property of the power map, i.e. of the architecture.

### 2.4 Cold caches: the prize is leakage, not heat

**Measured.** Cooling the cache from 350 K reduces its leakage by **2.23×** more than the project's
original curve implied; the knee is at **280 K** and the prize is within 5 % of maximum there.

**Implication (argued).** Caches are the natural cold zone for a reason that is not thermal comfort:
a cache is mostly *static* power, and static power is exponential in temperature while dynamic power
is not. So the return on cooling a cache is qualitatively different from the return on cooling an
ALU:

| | why you cool it | what you get |
|---|---|---|
| **ALU / FPU cluster** | it is *hot* — power density 29 W/mm² | headroom: the die keeps a steady state at a density that would otherwise run away |
| **L2 / L3 cache** | it is *leaky* — large area, mostly static | energy: leakage falls 2.23× more steeply than the old curve said |

`[!]` **The cold zone must be a separate die.** Measured: 40 W of removal on a 60.7 W die buys
**1.24 K** of lateral gradient, confirmed by two independent methods to within 1.7×. A monolithic
die cannot hold a hot region and a cold region apart — conduction shorts them. This is the single
most consequential architectural constraint the project has produced.

### 2.5 The target temperature is barely sub-ambient

**Measured.** 280 K knee; both GIDL brackets agree. **Implication:** the cold die does not need a
cryogenic plant. It needs ~20 K of sub-ambient lift over a cache-sized area — a far easier machine,
and the difference between a laboratory result and a licensable product.

---

## 3. The design template this points at

**Argued from the measurements above.** Not yet measured as a whole design.

```
   +-----------------------------------------------------------+
   |  COLD DIE  --  L3 / L2 arrays, ~280 K                      |   leakage-dominated
   |              cooled for ENERGY, not headroom               |   large area, low density
   +------------------------ separate die ---------------------+
   |  HOT DIE   --  cores: ALU/FPU clusters run DENSE and HOT   |   dynamic-dominated
   |              array targets the 142 x 115 um cALU class     |   small area, 29 W/mm2
   |              200 um tile pitch is sufficient               |
   +-----------------------------------------------------------+
```

Three design moves follow, in decreasing order of evidential support:

1. **Separate the cache die.** Measured constraint (§2.4). Not optional.
2. **Let the execution cluster get denser and hotter than a conventional floorplan would allow**,
   and put the array's granularity there. Supported by 35/35 rescues at 1.15 W/mm² and by the
   200 µm plateau.
3. **Spend the thermal headroom on the threshold-voltage lever, not only on clock.** `[!]`
   **Re-priced 3 September on the simulated device (§P0.18.3):** a 25 mV `V_t` reduction costs
   **22–30 K** of lift, 50 mV **45–60 K**, 75 mV **67–90 K**. `LADDER_GEN0`'s "50 mV ≈ 22 K, 75 mV
   ≈ 33 K, both inside 45 K" is **withdrawn** — it used the pipeline curve's doubling temperature
   and the roadmap's swing; the measured curve doubles every 19–23 K above 345 K and the card's
   swing is 61–81 mV/dec over 300–400 K. So only the **25 mV step** sits inside the demonstrated
   45 K, and the clock it buys is +7.6 %. `[!]` Still **open** — a re-derivation on measured
   inputs, not a measurement: the lever has not been run end to end. `[+]` `dt_max` is no
   longer the blocking input: §P0.19 derives the lift from the extractor's own cooling curve
   and finds it never binds on this die (coldest tile 263 K against floors of 207–259 K).

---

## 4. What this does **not** yet say, and must before anything is licensable

`[!]` This is the honest gap list. A licensable core design needs all four closed.

| gap | why it blocks licensing | what would close it |
|---|---|---|
| **One die, one workload.** Every number is 34-core 7 nm skylake on single-threaded LINPACK, replicated. | A vendor licenses a design against *their* workloads. Nothing here has been shown to survive a floorplan change. | Re-measure on ≥2 more floorplans and ≥2 more workload classes. The ISA variants are parked, not disproved. |
| **No ISA comparison has been run under the current accounting.** | The programme's premise is that different ISAs evolve differently under selective cooling. That is currently a hypothesis. | `docs/CODESIGN_PLAN.md` describes the method; it is a plan, not results. |
| ~~**`dt_max` is unknown.**~~ **Closed 8 Sep (§P0.20).** | The lift is the extractor's own cooling curve at the tile's temperature, fixed by v98's transparency cap without a measurement; the target device (v98 Table 1.1) does not bind on this die. What the die *does* constrain is the device: a 2.00 W/mm² rescue needs **rung 4 of the photonic ladder** (broadband Purcell); the near-term film delivers 9 % of the watts. | The book's own priority experiment (ε beyond 620 nm) moves the pump optimum, not the lift. Open: v98's zone materials against the 3 Sep rule. |
| ~~**The array's own area and routing are not in the floorplan.**~~ **Closed 3 Sep (§P0.18).** | In the v91 device the tiles, waveguides and monolithic-backside LPC sit *above* the silicon and share the pixel layer's footprint; they take no logic area. Charged as an areal coverage, the charge is **zero** at 500 µm pitch and 200 µm burial down to 0.26. | What remains open is the fine-pitch end (a 50 µm tile at quarter coverage is below the mesh) and the LPC's own dissipation on the tile stack (`RESULTS_REGISTER.md` §3). |

---

## 5. The evolution loop, and where it stands

The intended programme is: **measure → find the binding constraint → change the architecture →
re-measure**, across ISAs, until the design stops improving.

| stage | status |
|---|---|
| Thermal/power model trustworthy enough to compare designs | **done** — but only after correcting a leakage curve that was not a device and a converter that double-counted per-core dynamic power |
| The cooler's envelope pinned to measured device physics | **done** — `h_max` from v91; the lift derived from the extractor's own curve (§P0.19), with a three-input bracket for the device team to confirm |
| One architecture measured end to end under that model | **done** — 34-core 7 nm skylake |
| A second architecture measured the same way | **started 9 Sep (D4)** — the 70-core die's gen-0 ladder, as a falsification test; `docs/evidence/d4_falsification_70core.json` when it lands |
| An ISA-level comparison | **not started** (`CODESIGN_PLAN.md` is a plan) |
| The objective a storage zone needs (cool the caches for leakage, not the hot spot) | **built and measured 9 Sep (§P0.22.2)** — on the monolithic die the cache knee is conservation-bound and 300 K costs 77 % of the die; the gen-3 constraint is measured, its design argued |
| A design changed *because* of a measurement, then re-measured | **done 9 Sep (D1, §P0.22.3)** — the execution cluster made 2× / 4× denser *because* the rescue ladder said the array closes the concentration penalty, re-measured at matched watts: the laser holds the 2× cluster to the 2.00-equivalent rung and the 4× cluster to 1.60, 0 tiles capped, at 1.2–6.9× the reference's cooling; each loses the top rung. One die, one workload, one change: the loop has taken its first step, not run its course |
| The ladder's binding constraint named where it stops being thermal | **done 11 Sep (X1/X2, §P0.27)** — the recorded fields re-solved and read as current density: above ~1.3 W/mm² the rails carry 1.5–3× the native current (the dense cluster's cALU 2× / 4× that), and thermal skew grows with every rung; gen 1's next constraint is the PDN, MEASURED as `J`, ARGUED as a limit (no rail model) — the first non-thermal end on the ladder, for the reference floorplan's rails |

`[!]` **Be precise about this in external material.** The project has built and validated the
measurement apparatus and produced one architecture's worth of results with it. It has taken **one
step** of the evolution loop (D1, 9 Sep: one change, one die, one workload, re-measured on the
array rungs) — say that, and no more; the argued ladder is `docs/designs/EVOLUTION_LADDER.md`. That is the next phase, not a completed one, and claiming otherwise is
the fastest way to lose a technical reviewer.


## 8 September 2026 — zone materials decided; the cold plate stays single-material (§P0.21)

The user's decision: the storage (cold) zone material is **Cr:LiSAF**, the hot zone the dye,
Yb:YLF out of every zone. And the photonic cold plate we test is **one material over the whole
die by default**: a cold-zone / hot-zone tile arrangement has to be laid out against the
floorplan, i.e. designed with the chip vendor per architecture, which defeats the
architecture-agnostic premise. `--mr-zone-mode dual` exists to *measure* that arrangement when
the floorplan is itself the variable (Phase 2) or the array is integrated at die manufacture.
First measurement, hot-spot objective at 2.00 W/mm² on the 34-core die: a 1 % effect — the
planner never drives the caches cold there, so the storage-zone tiles have nothing to do. The
storage-zone material's real test is a cache-leakage objective on a separate-die cold zone.
