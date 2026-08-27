# Co-designing cores for photonic cooling

A methodology for iterating core designs — x86 and RISC-V — against an integrated photonic
cooling array, in enough detail to license the result to a chip manufacturer.

Status: **plan**, not results. Everything marked `measured` below has a JSON in `docs/evidence/`;
everything else is a hypothesis this programme is meant to test or a component that has to be
built. The distinction is load-bearing — the whole point of the exercise is to end up with claims
a vendor can check.

---

## 0. The premise, and the one number it is sensitive to

The architecture discussion assumes the cooler reaches **COP ≥ 1**. Checked against
`mr_accounting` rather than asserted:

| configuration | breakeven ratio | net cost to remove 100 W | effective COP |
|---|---|---|---|
| handbook baseline — η_ASF 0.20, laser 0.70, LPC 0.90 | 0.756 | 174.3 W | 0.57 |
| **target — η_ASF 0.33, laser 0.80, LPC 0.87** | 0.926 | **28.2 W** | **3.55** |
| target, 92% collection | 0.852 | 56.2 W | 1.78 |
| target, 85% collection | 0.787 | 80.7 W | 1.24 |

The premise holds across a plausible range. But **collection efficiency alone moves COP from 3.55
to 1.24**, and collection is a property of the optical path geometry — which is package and
floorplan, not device physics. That makes it a co-design variable and it belongs in the design
rules as a first-class constraint. A core design that makes 85% collection unavoidable has
thrown away two thirds of the cooler.

---

## 1. What is already established, and what it constrains

These are the measured results the methodology has to be built on. Each one is a design knob.

**Placement of the extraction decides whether die thinning is worth anything.** `measured` —
`docs/evidence/mr_placement_burial_depth.json`. With cooling co-located with the transistors the
burial depth is inert by construction. With the array above the silicon, thinning from 360 µm to
20 µm improves what a fixed 3 W buys **by 44% through the production path** (67% by the direct
probe — see the qualification immediately below). Burial depth is therefore a spec a vendor must
agree to, and it is the first item on any term sheet.

> **Qualification on the number, 26 August 2026 — read before quoting it externally.** The **67%**
> is real but it is **not a die-wide constant**, and two things move it several-fold:
>
> * **Block maximum against block average.** `mr_placement_probe` writes its own `.stk` with
>   `Tflp(..., maximum, final)`. The production path is `ICE.DIE_TFLP_OUTPUT`, which is
>   **`average`** — so every catalogue row, and every block the planner ranks on, is a block
>   *mean*. On the same block at the same depth the two differ by 2.6 K (81.24 max vs 78.62 avg).
> * **Which block.** On averages the hottest block is `L2_4`, not `L3_4`. The direct probe re-run
>   on `L2_4` gives **+11.0%** against +67.2% on `L3_4` —
>   `docs/evidence/mr_placement_burial_depth_L2.json`.
>
> Driven end to end through `run_mr_clipping` — same 3 W, same block, byte-identical tile plan at
> every depth — the swing is **+44.1% in the array against −7.0% in the source layer**
> (`docs/evidence/burial_depth_through_planner.json`). **What survives all three measurements is
> the claim the term sheet actually needs**: array placement is strongly burial-sensitive and
> co-located placement is not. Quote the magnitude with the block and the reduction stated, or
> quote the separation.

> **Settled, 25 August 2026.** The device is the array **above the silicon**, always — a cold
> plate mounted on a direct-die package, with 30 µm of pixel array where the thermal grease
> would be. Co-location is not what is being built, so there is no escape from the burial-depth
> spec above and the 67% is a real constraint rather than a choice between two models. The
> convection control carries the same sink and the same active-layer depth, differing only in
> that one 30 µm layer. Recorded in `HotGauge/HotGauge/thermal/die_stack.py`, asserted by
> `test_die_stack.py::TestTheDeviceAsItIsBuilt`, and detailed in `docs/EXECUTION_PLAN.md` §6.
> Default active-layer depth is 200 µm; it remains a free parameter so thinning can be swept.

**The optimal tile pitch reverses with the workload.** `measured` —
`docs/evidence/tile_pitch_{uniform,concentrated}.json`. On a degenerate peak a coarse 2000 µm
tile beats a fine 100 µm one by 59%; on an isolated hotspot the fine tile wins by 123%. The
discriminator is the gap between the hottest block and the runner-up — 0.56 K versus 12.25 K in
the two cases measured.

**A coarse array is low-variance; a fine array is a bet.** `measured` — same evidence. The coarse
array delivered 3.03 K and 3.09 K across power maps whose peak differed by 79 K. The fine array
swung 3.6× on identical hardware.

### The central tension

Those last two together are the reason this is a *co-design* problem rather than two independent
ones. **The core design determines which array is right, and the array determines which core
design pays.** A thermally uniform core wants a coarse array; a core with deliberate hot clusters
wants a fine one. Choosing either in isolation gives up most of the benefit.

The licensable artifact is therefore not "a cooling array" or "a core". It is a **matched pair**,
plus the rule that tells a vendor which pair their workload wants.

---

## 2. Phase 0 — close the measurement gaps

None of the design exploration is trustworthy until these are done, because every existing MR
number was computed with the cooling in the wrong layer.

| gap | state | why it blocks the programme |
|---|---|---|
| Planner emits tile powers, not block subtractions | **open** | Every study driver still applies MR the old way |
| Per-tile `dt_max` instead of per-block | **open** | Decided (per-tile); changes what the device spec means |
| Re-run the catalogue: cliff, tiers, rescue cost, clock | **open** | All of it predates the placement fix |
| Session cache carries two dies | **open** | Element ordering unverified; 40× solve-cost penalty without it |
| Transient with a modulated array | **open** | Turbo policy is unreachable without it |
| Spreader overhang in the matrix | **open** | Largest remaining geometric artifact |

The session cache one is worth flagging for cost: a re-run of the catalogue without it pays a
full factorisation per solve. On node-06 that is the difference between hours and days.

---

## 3. Phase 1 — cooling-aware floorplan metrics (x86 baseline)

**Goal:** find the floorplan properties that predict MR benefit, so a vendor can score their own
design without running our pipeline.

Candidate metrics, all computable from a floorplan plus a power trace, no thermal solve needed:

1. **Peak-to-runner-up gap** — already shown to discriminate the two pitch regimes.
2. **Plateau width** at the device's `dt_max` — already produced by the tier screens.
3. **Tile alignment** — what fraction of hot-block area falls inside a single tile at a given
   pitch. `coverage_report` computes this; its relationship to benefit is untested.
4. **Power-density concentration** — Gini or top-decile share of the power map.
5. **Thermal aspect** — how far hot blocks sit from the die edge, where lateral spreading helps.

The deliverable is a regression of measured MR benefit against these metrics across many
floorplan and workload variants. **Any metric that does not predict is dropped**; the ones that
survive become the design rules. This is the step that turns a simulation capability into
something a third party can use.

Existing assets: the 34/70/128-core Skylake-derived floorplans, Sniper→McPAT traces at 7/10/14 nm,
and the activity generators (`uniform`, `turbo`, `mixed`, per-unit `emphasise`).

---

## 4. Phase 2 — a RISC-V baseline

**Why it is not just a re-parameterisation.** The thermally interesting ISA difference is where
the area and power go. An x86 core spends a large, *distributed* fraction of its front end on
decode, µop cache and the associated control. A RISC-V core of comparable performance spends less
there and relatively more in execute and vector.

**Hypothesis, to be tested rather than assumed:** *RISC-V cores are more thermally concentrated
than x86 cores at equal performance, because less of the die is spent on decode.* If true, it
follows from the pitch result that **the two ISAs want different cooling arrays** — RISC-V toward
fine pitch, x86 toward coarse — and that is a licensable finding in its own right.

Three routes, in increasing order of fidelity and cost:

- **(a) Parameterised unit-area model.** Re-weight the existing unit-area JSON toward a RISC-V
  split using published core-area breakdowns. Cheap, gives a floorplan immediately, and is honest
  as long as the provenance is recorded the way the GA100 areas were. Good enough for Phase 1
  metric work; **not** good enough to license.
- **(b) gem5 + power model.** gem5 has mature RISC-V support; the gap is activity→power, since
  McPAT's templates are x86/ARM-shaped. Needs a converter and a calibration point.
- **(c) Public RTL through synthesis.** BOOM or CVA6 gives real areas and real activity factors.
  Highest fidelity, highest cost, and the only route that produces areas a vendor will not argue
  with.

Recommend (a) to unblock Phase 1, with (c) scoped as the path to a licensable claim. Do not
present (a) results as anything else.

---

## 5. Phase 3 — the co-design loop

The loop that actually designs a core:

```
  floorplan parameters
        │
        ├─→ generate floorplan ──→ score on Phase 1 metrics ──→ (cheap screen)
        │
        └─→ solve with array ──→ sustainable clock at fixed power and fixed MR budget
                    │
                    └─→ update parameters
```

**Objective:** maximise sustainable clock — or better, throughput — at a fixed die power *and* a
fixed MR electrical budget. Fixing the MR budget is what stops the optimiser buying performance
with cooling power it has not paid for.

**Search space**, ordered by expected effect from what is already measured:

- die thickness / burial depth *(67% swing measured — start here)*
- hot-unit clustering versus spreading *(inverts current practice; see below)*
- tile pitch, jointly with the above *(regime reversal measured)*
- placement of hot units relative to the tile grid
- die aspect ratio and edge proximity

**The counter-intuitive one worth testing first.** Conventional floorplanning spreads hot units
apart because silicon cannot move heat laterally fast enough. With extraction directly above every
square millimetre, that constraint weakens and the opposite may pay: **cluster the hot logic**,
shorten the wires, cut repeater power, and let the array over the cluster run harder. Dark silicon
exists because you cannot cool everything at once; an area cooler attacks exactly that. This is
the highest-value hypothesis in the programme and it is cheap to test with the tools in Phase 1.

---

## 6. Phase 4 — turbo and dynamic policy

Requires the transient path plus a modulated array, and a burstier workload trace than we have —
that trace is a prerequisite, not a detail.

The interesting policies, none of them currently reachable:

- **Pre-cooling.** Drive the array ahead of a known-hot kernel phase, using the die's thermal mass
  as a buffer. Turns boost from a duty-cycle game into a scheduled one.
- **Co-scheduled cooling.** The OS or runtime already knows which core is about to be loaded.
  Steering the array with that signal is free information the current model throws away.
- **Cooling-aware DVFS.** Today the controller trades clock against temperature. With a second
  actuator it trades clock against temperature *and* cooling power, and the optimum depends on
  the COP — which is where the ≥ 1 premise starts to matter commercially.

---

## 7. Phase 5 — packaging it as licensable IP

What a chip manufacturer needs, and what each item depends on:

| deliverable | depends on |
|---|---|
| **Thermal design rules** — max power density per tile area, burial-depth requirement, tile-alignment guidance, optical-collection geometry constraint | Phases 1–3 |
| **Reference floorplan** — a core designed to the rules, with quantified benefit against a conventional baseline at equal power | Phase 3 |
| **Evaluation kit** — lets a vendor score *their* floorplan on the Phase 1 metrics without our simulator or our data | Phase 1 |
| **Validated claims** — benefit numbers backed by the acceptance gate against real parts | Phase 0 + the existing gate |

The acceptance gate is what makes the claims defensible: a vendor's first question will be
whether the thermal model reproduces parts they know. Today it passes one of four published
points. **That has to be four of four before any of this is presentable**, and it is the reason
Phase 0 is not optional.

---

## 8. Suggested ordering

1. **Phase 0** — planner, per-tile `dt_max`, catalogue re-run, acceptance gate to 4/4.
2. **Phase 1** on the existing x86 floorplans — metrics and the regression.
3. **Phase 3 clustering experiment** — cheap, and the most likely to overturn a design convention.
4. **Phase 2(a)** RISC-V floorplan, test the concentration hypothesis.
5. **Phase 4** once a burstier trace exists.
6. **Phase 2(c)** and **Phase 5** when there is something worth licensing.

Section 9 records where this is meant to end up — the generational ladder of floorplans, each
defined by the bottleneck the previous one exposed — so that the ordering above is read as a route
to something rather than as a list of studies.

The one thing to avoid: presenting Phase 2(a) RISC-V numbers as characterising RISC-V. They
characterise a plausible RISC-V-shaped floorplan, which is a different claim, and this project has
already had to withdraw a catalogue of results once for exactly that class of slippage.

---

## 9. Where this is going — the evolution ladder

Phases 1–4 are instruments. This section is what they are for, and it is the record of the
destination rather than a schedule.

The output of the programme is not "an LCMR-enabled core". It is a **sequence of floorplans, each
one defined by the bottleneck the previous one exposed**, run identically across all three ISAs:

```
  gen 0   baseline floorplan, solved WITH and WITHOUT LCMR
            │   the delta is not the result -- the BINDING CONSTRAINT it reveals is
            ▼
  gen 1   floorplan that spends the removed constraint on the primary bottleneck
            │   which exposes the next one
            ▼
  gen 2   floorplan that addresses what gen 1 exposed
            │
            ▼   ... until the binding constraint is no longer thermal
```

The deliverable is the ladder itself: for each ISA, what bound the design at each rung, what was
changed in response, and what that bought at fixed die power and fixed MR electrical budget.

### What makes this a measurement rather than a story

Each generation must **name its binding constraint before the next is designed**, and the naming
has to come out of the solve rather than out of intuition. The pipeline can already distinguish:

| binding constraint | how it announces itself | the lever it licenses |
|---|---|---|
| peak block temperature | one block sets `core_fmax` | clustering, tile alignment, hot-unit placement |
| die-average path | proportional extraction stays linear while targeted saturates | die thinning, tile pitch, total budget |
| leakage runaway | `diverged` at every damping | lower `T_j` outright — the regime LCMR opens |
| MR electrical budget | the plan hits its own COP-weighted ceiling | collection efficiency, pitch, η_ASF |
| V/F table ceiling | `vf_clamped` | **not an architecture result — see below** |
| none of the above | clock rises with no thermal response | LCMR has stopped being the limit; the ladder ends |

That last row is the honest stopping rule and it belongs up front rather than as a footnote. At
some rung the answer becomes *"you are now limited by something a cooler cannot fix"* — memory
bandwidth, ILP, wire delay. Knowing exactly which rung that is, and for which ISA, is a more
valuable and more defensible claim than pretending the ladder goes on forever.

Three invariants make the rungs comparable. Break any one and "generation 3 is faster" degenerates
into "generation 3 was allowed more":

* same workload and same trace,
* same die power budget,
* same MR **electrical** budget — not the same heat removed, the same watts spent removing it.

### The prerequisite that blocks the first rung

`clock_search` bisects against a **V/F table that stops at 5.0 GHz**. Past it the voltage clamps,
the power cost is understated, and the search sets `vf_clamped`. The entire premise of the ladder
is that LCMR buys sustainable clock — and **a study of whether LCMR reaches 6 GHz cannot be run on
a table that stops at 5.** Extending the V/F table, with its provenance stated the way the unit
areas are, is a prerequisite for gen 0 rather than a step within it.

### The levers, in the order they are expected to bind

**Turbo and boost policy.** Cheapest to change and most likely to be mis-set for a cooled part:
today's policies are tuned for a thermal mass that dissipates slowly and a cooler that cannot be
steered. Needs Phase 4 — transient plus a modulated array — so it is gated on the burstier trace.

**Threshold voltage and the operating regime — the deepest lever, and the one only LCMR unlocks.**
Lowering V_t buys frequency at the cost of leakage, and leakage is what has always made it
unaffordable. But leakage is exponential in temperature and this project already has a *calibrated*
model of that curve: local doubling runs from ~180 K at 310 K to ~8.6 K at 400 K. A cooler that
holds the junction far below the conventional operating point therefore **buys back the leakage
cost of a low-V_t device**. That is a co-design result which does not exist without active cooling,
it is testable with what is already built, and it is the strongest candidate for the programme's
headline claim. It also inverts the usual framing: LCMR's value is not that it removes more heat,
it is that it moves the device to a part of the leakage curve nobody can otherwise afford.

**Vector / SIMD width.** The FPU/AVX block is 8.7% of core area *and* it carries the highest power
density, which is what an area cooler responds to. This is also the honest replacement for the
decode-area hypothesis in §4, which the unit-area model cannot express (decode is 3.3%).

**Specialised high-frequency ALUs and registers.** A small block clocked past what the rest of the
core can sustain, because the array can hold that block alone. This is §5's "cluster the hot logic"
with a concrete mechanism attached, and it is the point where floorplan and µarchitecture stop
being separable.

**Clustering high-density logic.** Already §5, and the cheapest of these to test.

**Power delivery is out of scope for the current model, and that has to be said rather than
assumed away.** Nothing in the pipeline sees IR drop, dI/dt or the PDN, so "inject more power to
reach higher frequency" is a lever we cannot presently evaluate. It is also the lever most likely
to bind in a real part while remaining invisible here, so any rung that depends on it must be
labelled as resting on an unmodelled assumption.

### The figures this is meant to produce

Per ISA, and comparable across them:

1. **The ladder itself** — sustainable clock (or throughput) against generation, at fixed die
   power and fixed MR electrical budget, with the binding constraint annotated at each rung.
2. **Where the constraint moved** — the floorplan at each generation, shaded by whatever was
   binding, so the reader sees the hotspot migrate and then stop being a hotspot.
3. **The three-ISA overlay** — the same ladder for x86, ARM and RISC-V. If the ISAs bind at
   different rungs, or want different arrays, that is the licensable finding §2 predicts.
4. **The stopping rung** — what is left when thermal stops being the limit, which is the
   boundary of the claim.

### What this does not license

Generation *n* is a floorplan we designed to our own rules and scored on our own pipeline. Until
the acceptance gate reaches 4/4 and at least one ISA's areas come from something a vendor cannot
argue with (§4 route (c)), the ladder characterises **our model's response to LCMR**, not silicon.
That is a real and useful thing to know; it is not the same claim, and the project has already had
to withdraw a catalogue once for exactly this class of slippage.
