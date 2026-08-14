# Is MR really weak as a clock enabler? A design study plan

**14 August 2026.** Written after the clock-headroom result (`docs/CLOCK_HEADROOM.md`) came back
saying MR buys ~1% clock, and after finding the mechanism behind it. The conclusion in that
document is correct **for the die and workload we tested**, and that qualifier turns out to be
the whole story.

---

## 1. The mechanism: the peak is degenerate

`examples/thermal_tiers.py` measures the shape of the top of the temperature distribution. MR
lowers a block by at most `dt_max` (10 K), so clipping the hottest block only buys headroom
down to whatever becomes the peak next. On the 34-core die at 1.00 W/mm², 88 CFM:

| rank | block | T °C | peak after clipping ranks 1..n |
|---|---|---|---|
| 1 | RBB_16 | 89.19 | 87.94 (gain 1.25 K) |
| 2 | RBB_0 | 87.94 | 85.86 |
| 3 | cALU_16 | 85.86 | 85.49 |
| 5 | RBB_24 | 85.28 | 84.75 |
| 9 | RBB_8 | 83.52 | 82.27 |
| 15 | fpRF_8 | 79.73 | **79.19 (full 10 K)** |

* **15 blocks sit within `dt_max` of the peak.**
* Clipping one block realises **12%** of the device's capability (1.25 K of 10).
* Realising the full 10 K requires clipping **all 15**.

The blocks are `RBB_16, RBB_0, cALU_16, cALU_0, RBB_24, RBB_32, fpRF_16, fpRF_0, …` — the same
few functional units repeated across cores. **The peak is N-fold degenerate**, and the
degeneracy grows with core count.

That is why MR looked weak, and it is a property of the *design and workload*, not of MR:

> Clipping a degenerate peak is bulk cooling in disguise. You must pay for every copy.

Two of our own modelling choices manufacture the worst case:

* `replicate_trace_cores` copies one core's power onto all cores. Documented as the worst case
  for peak temperature — it is also the worst case for MR leverage, and we have never run
  anything else.
* One workload (linpack), homogeneous in time and space, so no core is idle or in a different
  phase.

**Revised hypothesis, and the thing this study exists to test:**

> MR is weak as a clock enabler where the thermal peak is degenerate, and should be strong
> wherever one structure is distinctly hottest. The question is not whether MR works, but which
> designs have a non-degenerate peak.

The screening metric follows directly, and it is cheap — one converged solve, no clock search:

* **plateau width** — blocks within `dt_max` of the peak (15 today; want ≤ 2–3)
* **clip-one gain** — T[1] − T[2] (1.25 K today; want ≥ 5 K)

Rank candidate designs on those before spending a sweep on any of them.

---

## 1b. First results: the prediction was wrong, and there are TWO degeneracies

Screened at 1.00 W/mm² equivalent, 88 CFM, `--activity-scope iso-per-core` (each core keeps its
saturated power; total die power falls as cores go quiet, as a real part does):

| activity | die W | peak °C | plateau width | clip-one gain |
|---|---|---|---|---|
| uniform (today's assumption) | 101.2 | 89.19 | **15** | 1.25 K |
| mixed, 50% of cores active | 65.2 | 78.34 | 12 | 1.15 K |
| mixed, 25% active | 44.2 | 72.79 | 6 | 2.42 K |
| turbo, 1 core, others at 0.25 | 31.3 | 65.31 | **7** | 2.56 K |
| turbo, 1 core, others at 0.05 | 12.7 | 59.83 | 8 | 2.61 K |

**Predicted:** turbo collapses the plateau to 1–3 and clip-one gain approaches the full 10 K.
**Measured:** the plateau halves (15 → 7) and the gain doubles (1.25 → 2.6 K). Real, and far
short of the prediction. The hypothesis as stated is falsified.

The block names say why. Under turbo the top five are `RBB_0, cALU_0, fpRF_0, fpiWin_0, iRF_0` —
**all from the same core**. There are two degeneracies stacked:

1. **Inter-core** — N copies of each unit at nearly the same temperature. Broken by activity
   (turbo, low active fraction). This is the one the plan assumed was the whole problem.
2. **Intra-core** — the hot functional units *within* one core also sit within a few K of each
   other. Nothing in the activity domain touches this, and it is what still limits MR after
   turbo.

That relegates design C (heterogeneous cores): it attacks degeneracy 1, which turbo already
addresses, and leaves 2 untouched. It promotes a candidate the data suggests rather than the
plan:

### G. A core with one dominant hot unit (accelerator-style)
A design where a single structure — a matrix/vector engine, not a balanced scalar core —
carries most of the core's power. That is the only way found so far to break degeneracy 2, and
it is what modern AI-oriented silicon actually looks like.

* **Tests:** whether intra-core dominance is what MR needs, as opposed to any property of the
  workload or the core count.
* **Screen first:** plateau width on such a floorplan. If it is 1–3, MR becomes a clock lever
  and the whole positioning changes.

### Caveat on the screening metric itself
`tier_analysis` assumes clipping one block leaves the others where they are. That is **not**
true here: the measured lateral coupling on this die is strong (removing 0.5 W at `cALU_0`
cooled `RBB_0` by 9.5 K, nearly as much as `cALU_0`'s own 10.7 K). Clipping the top block
therefore also pulls its plateau-mates down, so the metric is **pessimistic** by an unknown
factor. It is a screen, not a measurement — the clock search is the measurement, and the two
agree on "weak" for the uniform die (+1.1%), which is what gives the screen its credibility.
Coupling cuts both ways: it also means the plateau cannot be clipped independently, since
cooling one member cools the neighbours it is competing with.

---

## 2. Blocking correctness work (do first)

**2.1 The MR loop is not verified, and may be path-dependent.** `run_mr_clipping` sizes its
whole plan from an uncooled baseline solve. In the rescue regime that baseline *has no steady
state*, so the plan is sized from wherever a divergent iteration happened to be stopped. The
symptom is already visible: at a fixed 92 °C target the rescue is **non-monotone in density** —
1.10 rescues, 1.12 does not, 1.15 rescues, 1.16 does not. `examples/mr_plan_probe.py` is
measuring this now.

This is the same class of error as `docs/CONVERGENCE.md`, one level up, and **every design
comparison would inherit it**. Fix before the study: size the plan from something that exists
(continuation from a converged lower-power point, carrying the previous plan as the seed), and
verify the MR fixed point the way the leakage loop now is.

**2.2 Phase 4 of overnight3 is mostly unverified** — 5 of 6 pixel-pitch points failed
verification. Whatever it says about pitch cannot be quoted yet, and it is the same MR-loop
instability.

---

## 3. Candidate designs, in priority order

Each entry: what it tests, why it might break the degeneracy, what it costs, and what result
would falsify the revised hypothesis.

### A. Single-core turbo — the non-degenerate case by construction
One core boosted, the rest at base clock or idle. This is the classic single-thread turbo
scenario, and it is the *most favourable* geometry MR can have: one hot core, its neighbours
acting as heat sinks through the constriction path MR sits upstream of.

* **Tests:** whether a non-degenerate peak converts MR into a real clock lever.
* **Expected:** plateau width ~1–2; clip-one gain ≈ full `dt_max`; large single-core clock gain.
* **Cost:** cheap. Needs a per-core clock in `scale_trace_for_clock` (currently one global
  clock) and a clock search over the boosted core only.
* **Falsifies the hypothesis if:** the gain is still ~1%, which would mean the limit is the
  die-average path even for one hot core.
* **Value if true:** MR sells as a *turbo enabler*, a well-understood product axis.

### B. Heterogeneous workload on the existing die — is our assumption the problem?
Same floorplan, but cores at mixed utilisation (e.g. 25/50/100% active) or phase-shifted,
instead of `replicate_trace_cores`' identical copies.

* **Tests:** how much of the degeneracy is real versus an artefact of our trace handling.
* **Expected:** plateau width falls with the number of fully-active cores.
* **Cost:** cheap, and it is the single highest information-per-hour item here. Needs a
  per-core scale factor in the trace replication.
* **Note:** this is a *correction* to the current study as much as a new design — every MR
  result we have assumes the most hostile workload possible.

### C. Heterogeneous cores (big + little)
A few large high-power cores among smaller ones.

* **Tests:** degeneracy broken by design rather than by workload.
* **Cost:** medium — needs a floorplan generator change to tile two core types
  (`examples/generate_ncore_floorplans.py` currently tiles one).

### D. On-die HBM / 3D stack — a different, lower limit
A memory layer over the logic. Two things change qualitatively: DRAM has a hard ~85 °C limit
(refresh doubles above it), well below the logic's 100 °C, so the *system* may be
memory-thermally limited; and 3D stacking puts a low-conductivity layer in the heat path.

* **Tests:** whether MR's value shows up as protecting a **different, lower-limited structure**
  rather than as clock on the logic. If the binding constraint is a DRAM hot zone, clipping it
  is exactly the local intervention MR is good at.
* **Cost:** highest here. Needs a multi-layer `.stk` (3D-ICE supports it natively), a memory
  floorplan and power model, and a DRAM temperature limit as a separate constraint in the
  search. The memory-latency-to-performance link would be a new assumption and must be kept
  separate from the thermal result, exactly as `ipc_rel` is.
* **Worth it because:** it is the case where "MR addresses latency" becomes a thermal claim we
  can actually simulate, rather than an architectural assertion.

### E. Distributed MR on the die-average path — the control arm
Instead of clipping hotspots, spread the same laser power over the whole die.

* **Tests:** the assumption baked into every MR result so far, that MR is a *hotspot* tool.
  If localized cooling of the die-average path is competitive, our framing is too narrow.
* **Expected:** loses on wall-plug grounds (electrical COP 0.14 against a cold plate), *unless*
  the LPC recovery puts it in the net-generating regime that `breakeven_ratio > 1` describes.
* **Cost:** low — MR already accepts an arbitrary plan; this is a different plan builder.
* **Why it must be in the study:** it is the strongest counter-argument to "MR is weak", and it
  should be measured rather than assumed away.

### F. `dt_max` device roadmap — sanity check, not a fix
Sweep `dt_max` 10 → 20 → 30 K on the current die.

* **Prediction from the tier data:** it does *not* rescue clock leverage on a degenerate peak,
  because the binding constraint is the number of blocks that must be clipped, not the depth of
  each clip. A 15-wide plateau still needs 15 clips.
* **Cost:** trivial. Include it precisely because it is the intuitive fix and the tier data says
  it will not work — a cheap, falsifiable prediction of the mechanism.

---

## 4. Method: how each design is judged

1. **Screen** with `examples/thermal_tiers.py` — plateau width and clip-one gain. Cheap, one
   solve. Designs that stay degenerate are not worth sweeping.
2. **Search the clock** with `examples/clock_headroom.py`, MR on and off, at matched cooling.
   The metric is sustainable clock, which does not inherit the uncalibrated `derate_per_K`.
3. **Compare at iso-cooling-power.** MR watts against the equivalent spent on the sink/fan, so
   the comparison is a budget allocation rather than free cooling.
4. **Damping-verified only.** Unverified points are excluded, not tabulated.

Report per design: plateau width, clip-one gain, sustainable clock MR-on vs MR-off, MR watts,
and clock gained per MR watt. That last number is the one that decides the technology.

---

## 5. What would change the headline

The current defensible claim is: *MR arrests the leakage instability cheaply (0.394 W stabilises
a 113.5 W die, pending the 2.1 fix) and buys ~1% clock on a homogeneous many-core.*

It becomes *"MR enables higher clocks"* if design A or B shows a non-degenerate peak converting
into a multi-percent clock gain at a laser cost of a few watts. The tier metric predicts which
before the sweep is run, so this is answerable in a day of runs once 2.1 is fixed — not a
research programme.

If A and B both come back at ~1%, then MR's value is genuinely the stability rescue and the
memory-limit case (D), and the honest positioning is "thermal viability and hotspot protection",
not clock.
