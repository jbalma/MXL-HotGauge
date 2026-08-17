# Clock as a free variable: what cooling actually buys

**14 August 2026.** Results from `examples/clock_headroom.py` (P2.6 in `docs/GAMEPLAN.md`).
Every point is a damping-verified coupled solve; see `docs/CONVERGENCE.md`.

## Why this measurement exists

`f_nominal` used to be an input and the model only derated *downward* from it. That makes the
best possible score "stops the throttling", so a study of microrefrigeration on a part that was
not throttling returns ~0 by construction, and Study A's "+3.5% ceiling" was an artefact of the
cap rather than a property of the device.

Here the clock is the output: raise it until the coupled solve can no longer hold the thermal
limit, and report the highest clock it can. Because the criterion is a temperature limit rather
than a frequency derating, **the answer does not inherit the uncalibrated `derate_per_K`
slope** that the GFLOP/s figures elsewhere rest on.

Setup unless stated: 34-core 7 nm die, 101.2 mm², 78.8 W on the die at the trace's 3.8 GHz
(0.779 W/mm²), thermal limit 100 °C, rated clock 5.0 GHz.

## What cooling buys (no MR)

| R_th K/W | f sustainable | peak °C | P_die W | W/mm² | limited by |
|---|---|---|---|---|---|
| 1.0 | 2.797 | 85.7 | 41.0 | 0.406 | **runaway** |
| 0.5 | 3.500 | 96.1 | 67.2 | 0.664 | **runaway** |
| 0.3 | 3.828 | 97.1 | 83.4 | 0.825 | **runaway** |
| 0.1 | 4.203 | 96.3 | 108.3 | 1.070 | 100 °C limit |
| 0.05 | 4.297 | 97.4 | 117.6 | 1.163 | 100 °C limit |
| 0.02 | 4.344 | 97.1 | 122.4 | 1.210 | 100 °C limit |

**A 50× better cooler (1.0 → 0.02 K/W) buys +55% clock, and never reaches the rated 5.0 GHz.**
Within the practical range it is far worse than that: 0.5 → 0.02 K/W is 25× the cooler for +24%
clock, and the last 2.5× (0.05 → 0.02) buys **1.1%**. That is the constriction floor
(β−α = 1.042 K/W, conduction, airflow-independent) expressed in the unit a customer buys.

Note the `limited by` column. Above 0.1 K/W the part does not reach its 100 °C spec limit at
all — it **runs away first**, at 85.7 °C with a 1.0 K/W cooler. The leakage instability, not the
temperature spec, is what caps the clock on a poorly-cooled die.

## What MR adds on top

At R_th 0.1 K/W (108 W die), sweeping the MR clip target:

| MR target | f sustainable | gain | heat removed | MR net electrical | cost per % of clock |
|---|---|---|---|---|---|
| none | 4.203 | — | — | — | — |
| 92 °C | 4.250 | +1.1% | 0.611 W | 1.07 W | ~1 W |
| 78 °C | 4.250 | +1.1% | 4.614 W | 8.02 W | ~7 W |
| 65 °C | 4.297 | +2.2% | 24.85 W | 43.14 W | ~19 W |

**As a clock enabler, MR is weak and gets rapidly worse as coverage widens.** Dropping the
target from 92 to 78 °C costs 7.5× the power for *no* additional clock. Dropping to 65 °C
doubles the gain to 2.2% but costs 43 W — 40% of the die's own power — to get it. Cost per
percent of clock rises about 20× across that sweep.

(The 92 and 78 °C rows land on the same clock because the search resolution is 0.05 GHz ≈ 1.4%;
separating them needs a finer `--f-tol`. The *cost* difference between them, 1.07 W against
8.02 W, is fully resolved and is the point.)

At the widest coverage the die's own power actually falls, 108.3 → 101.7 W, because 24.8 W of
hotspot heat removed also suppresses a lot of leakage. It still is not worth 43 W of laser.

## The result this reframes

Put beside the density study (`docs/CONVERGENCE.md`), the two measurements say the same thing
from opposite directions:

* **MR as a clock enabler: weak.** +1.1% for ~1 W, +2.2% for 43 W.
* **MR as a stability rescue: strong.** At 1.10 W/mm², **0.394 W removed from 30 blocks
  stabilises a 113.5 W die that has no steady state at all** — 290 W of die per watt removed.

That is exactly what the constriction picture predicts, and it is worth stating plainly because
it is not the hoped-for answer. The clock ceiling is set by the die-average thermal path, which
hotspot clipping barely touches. The runaway is *local*, driven by one block, and clipping that
block is correspondingly cheap. **MR's value is arresting the leakage instability, not raising
the clock.**

The practical consequence: MR is worth buying for a part that is thermally non-viable or right
at its stability boundary, and not worth buying for a part that merely wants to clock higher.
That is a narrower claim than "enables higher clocks" and a much more defensible one.

## Policy caveat, and where it points next

The MR target is an absolute temperature, and with the clock free that policy is self-defeating
at the low end: the search cools the die until it holds its limit, so at R_th 1.0 K/W the part
settles at 2.797 GHz with a peak of 85.7 °C — below the 92 °C target — and MR clips nothing.

Anchoring the target to the *thermal limit* does not fix it (`--mr-target-margin-K` exists but
does not help here): that point is limited by runaway at 85.7 °C, 14 K below the spec limit, so
no limit-anchored target ever engages. A policy that works at every cooling class has to be
anchored to the operating point (peak minus a margin) or to leakage contribution — the
leakage-ranked policy in `docs/GAMEPLAN.md`, which this makes a stronger case for.

## CORRECTION (later the same day): the V/F table does not match the roadmap for this node

I earlier concluded that the shipped V/F table "ends where the device does", on the strength of
an alpha-power fit showing 5.5 GHz would need 1.82 V. The fit is good (0.30% RMS) and that
conclusion is right *about the table*. Checked against **IRDS 2024 More Moore, MM01 - LOGIC**,
the table itself is the problem:

| clock GHz | our table needs | IRDS Vdd | ratio |
|---|---|---|---|
| 3.85 | 0.936 V | 0.70 V | 1.34× |
| 4.22 | 1.044 V | 0.65 V | 1.61× |
| 4.36 | 1.092 V | 0.60 V | 1.82× |
| 5.19 | 1.528 V | 0.60 V | 2.55× |

IRDS puts a high-performance logic node at **0.6–0.7 V** reaching 3.85–5.19 GHz (wireloaded HP;
its CPU-frequency row is 3.1–4.2 GHz). The shipped table needs **1.19 V for 4.6 GHz and 1.4 V
for 5.0 GHz** — roughly twice the supply voltage for the same clock. It is not a 7 nm-class
curve.

**What that invalidates.** Dynamic power goes as V²f, so at 5.19 GHz our model charges about
**6.5×** the dynamic power the roadmap implies. Consequences, in order of how much they matter:

* the "voltage-limited at 5.0 GHz" ceiling in design A is a property of **this table**, not of
  7 nm silicon — IRDS reaches 5.19 GHz at 0.6 V;
* every absolute power number at high clock is overstated, and the overstatement grows with
  clock, so the *shape* of the clock/power trade is wrong too, not just its scale;
* MR's measured clock benefit is therefore **understated**: the model charges too much voltage
  for the extra clock MR enables.

**What it does not invalidate.** Everything that compares two configurations at the same clock
through the same table — the degeneracy results, the plateau widths, the design comparisons,
the cliff and rescue work, which use density rather than clock. The table is a consistent error
where it is used as a common yardstick and a real one where it sets an absolute ceiling.

**The fix** is to rebuild the V/F relation from the IRDS table for the node being modelled,
which is now the highest-value item in the performance model — above extending the existing
curve, which is what I was about to do and which would have extrapolated a curve that starts
from the wrong place.

## Assumptions, and how much they matter

* **V/F table stops at 5.0 GHz / 1.4 V.** Above it voltage clamps and the power cost of clock is
  understated, so searches cap there and set `vf_clamped`. No result here hit the cap.
* **Leakage rises with supply voltage as `V^n`** (`--leak-v-exponent`, default 1.0) — a
  necessary assumption, since McPAT was extracted at one voltage. **Checked**: at R_th 0.1 K/W
  the sustainable clock is **4.203 GHz for n = 0, 1 and 2 alike**. It moves the peak
  (96.05 / 96.3 / 99.77 °C) and which limit binds, not the answer.
* **Thermal limit 100 °C** is a spec choice, not a measurement. On the poorly-cooled points it
  is not the binding constraint anyway.
* **`--r-th` points do not model pump or chiller power**, so their cooling power counts MR only.
  Airflow points (`--cfm`) do model fan power.

---

## The IRDS replacement, and what it does and does not fix (17 August)

`HotGauge/HotGauge/power/irds_vf.py` anchors the same alpha-power delay law on each IRDS 2024
node's own **(Vdd, Vt, frequency)** triple, so the curve passes through the roadmap's operating
point and uses the roadmap's threshold voltage instead of one fitted to the wrong table. Every
value in `IRDS_NODES` was extracted programmatically from `2024IRDS_MM_Tables.xlsx`, sheet
`MM01 - LOGIC`.

For the 2024 `"3nm" Enhanced` node: Vdd 0.70 V, Vt 0.156 V, 3.855 GHz wireloaded, and with 10%
overdrive a ceiling of **4.15 GHz at 0.77 V**.

| clock | shipped table | IRDS model | dynamic-power overstatement |
|---|---|---|---|
| 3.85 GHz | 0.944 V | 0.699 V | 1.8× |
| 4.36 GHz | 1.099 V | 0.770 V (clamped) | 2.0× |
| 5.19 GHz | 1.400 V | 0.770 V (clamped) | 3.3× |

### What this fixes

Absolute dynamic power at a given clock, which the shipped table overstated by 1.8–3.3× over the
range we ran, growing with clock. Every "W at this clock" figure inherits that.

### What it does not settle, and this matters

**IRDS's loaded-path frequency is not a product clock.** Its `f_wireloaded` is a
standard-logic-path metric for the technology; its `f_unloaded` (7.23 GHz on the same node) is a
ring-oscillator-style ceiling. Real products reach 5 GHz and beyond through deep pipelining and
custom circuits, so the achievable product clock sits *between* those two figures and the
roadmap does not say where.

Our clock searches ran to 4.7–5.0 GHz, which is above this node's `f_wireloaded` ceiling of
4.15 GHz and far below its unloaded 7.23 GHz. So:

* the searches were **not** exploring an impossible frequency range — a real product does clock
  there — but the *voltage* the old table charged for it was roughly twice what it should be;
* the "voltage-limited at 5.0 GHz" ceiling was an artefact of the table's top, and the honest
  replacement is not "4.15 GHz" either. It is that **this model cannot state a product clock
  ceiling** without a product V/F curve, and the anchor choice (`wireloaded` / `cpu` /
  `unloaded`) moves it by nearly 2×.

`alpha` is not in the roadmap either — one operating point cannot determine a slope. Across
alpha 1.0–1.6 the 2024 ceiling moves 3.96–4.25 GHz, about 7%, and `alpha_sensitivity()` exists so
any result leaning on it can be checked. The anchor choice is the larger uncertainty by far.

### Consequence for the MR results

The comparative results are unaffected: MR-on against MR-off at the same clock through the same
curve cancels the voltage level entirely, and that is what the degeneracy, plateau, margin-curve
and cliff findings rest on. What changes is that **absolute power at high clock comes down**, so
MR's measured clock benefit was understated — and the clock *ceiling* should not be quoted from
either curve until a product V/F relation is available.
