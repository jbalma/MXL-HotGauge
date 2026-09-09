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

~~Note the `limited by` column. Above 0.1 K/W the part does not reach its 100 °C spec limit at
all — it **runs away first**, at 85.7 °C with a 1.0 K/W cooler. The leakage instability, not the
temperature spec, is what caps the clock on a poorly-cooled die.~~

`[!]` **WITHDRAWN, 31 August 2026 (§P0.15).** The `limited by` column above is a property of the
**leakage curve**, not of the part. Re-run on the simulated BSIM-CMG curve (§P0.13) at all six of
these cooling points, the die reaches its 100 °C spec at **every** one — the runaway is gone, and
with it the claim that leakage instability rather than the temperature spec caps a poorly-cooled
die. Both GIDL brackets agree.

`[+]` **The clocks in the table survive; the mechanism does not.** The sustainable clock is
unchanged to the search's own 0.05 GHz resolution at five of six cooling points, and moves +3.1 %
at the sixth (1.0 K/W, where the pipeline curve's phantom runaway costs real headroom). So "a 50×
better cooler buys +55 % clock and never reaches 5.0 GHz" stands. "It runs away before it reaches
spec" does not.

The cause is the pipeline curve's hot tail, which §P0.13 measured at **47× too steep at 500 K**.
`[!]` And this is the opposite corner from where §P0.14 put it: §P0.14 argued the tail
disagreement "lives where the answer does not", because a die that survives never gets that hot.
True for a fixed-density **divergence test**, whose reported point is one the die survives — false
for a **search**, which probes points the die does not survive and reads its answer off where they
begin. Which part of a leakage curve is load-bearing is a property of the experiment, not of the
curve.

`[!]` The absolute clocks in this 14 August table also predate the RBB work, the residual/
backtracking convergence fix and `verify=True`, all of which raise them (0.1 K/W: 4.203 here
against 4.484 today). Compare within a campaign, not against this table.

Evidence: `docs/evidence/clock_headroom_curve_compare.json`,
`examples/clock_headroom_curve_compare.py`, `scripts/clock_headroom_curves.sh`.

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

**What that invalidates.** *(Superseded — see the next section. The second and third bullets
below are wrong: the pipeline uses only voltage RATIOS, in which a common factor cancels, so the
absolute error does not reach the power numbers. Only the ceiling bullet survives. Left in place
because the reasoning that produced it is the kind worth being able to re-read.)*

* the "voltage-limited at 5.0 GHz" ceiling in design A is a property of **this table**, not of
  7 nm silicon — IRDS reaches 5.19 GHz at 0.6 V; ✅ this one holds
* ~~every absolute power number at high clock is overstated, and the overstatement grows with
  clock, so the *shape* of the clock/power trade is wrong too, not just its scale;~~ ❌
* ~~MR's measured clock benefit is therefore **understated**: the model charges too much voltage
  for the extra clock MR enables.~~ ❌

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

### What it fixes, which is less than I claimed a few hours ago

**The power numbers do not move.** I wrote above that this corrects a 1.8–3.3× dynamic-power
overstatement. That is the ratio of *absolute* V², and **this pipeline never uses an absolute
voltage.** `scale_trace_for_clock` scales a McPAT trace by the *ratio*
`(V(f)/V(f_ref))² · (f/f_ref)` against the trace's own 3.8 GHz clock, and leakage by
`(V/V_ref)^n`. A common factor on the whole curve cancels in both. `voltage_for_frequency` is
reachable from nowhere else in the model — grep confirms `clock_search` is its only consumer.

Measured over the range, with 3.8 GHz as the reference the pipeline actually uses:

| clock | shipped multiplier | IRDS multiplier | difference |
|---|---|---|---|
| 3.00 GHz | 0.542 | 0.464 | −14% |
| 3.40 GHz | 0.732 | 0.688 | −6% |
| 4.00 GHz | 1.155 | 1.198 | **+4%** |
| 4.10 GHz | 1.239 | 1.309 | **+6%** |
| 4.15 GHz (node f_max) | 1.302 | 1.369 | +5% |
| 4.36 GHz | 1.590 | 1.438 | *clamped — not a cost, a part that does not run* |

Inside the node's valid range the two curves agree to within 6%, and **IRDS is the slightly more
expensive one** near the top. So every power figure in this study stands, and the direction of my
earlier caveat was wrong: MR's clock benefit was not being understated by the V/F table.

### What it does fix: the ceiling, which is where the error actually bit

The shipped table's top is 5.0 GHz at 1.4 V. No part runs at twice its nominal Vdd — reliability
caps overdrive near 10% — so **4.15 GHz at 0.77 V** is the 2024 node's ceiling, and every
`limited_by: vf_envelope` verdict in this study was measured against a ceiling ~20% too high.
That is a real correction and it is the only one.

### What is still open, and it is the bigger uncertainty

**IRDS's loaded-path frequency is not a product clock.** `f_wireloaded` is a
standard-logic-path metric for the technology; `f_unloaded` on the same node is 7.23 GHz, a
ring-oscillator-style figure. Real products reach 5 GHz through deep pipelining and custom
circuits, so an achievable product clock sits between the two and the roadmap does not say where.
The honest replacement for "voltage-limited at 5.0 GHz" is therefore not "4.15 GHz" — it is that
**this model cannot state a product clock ceiling**, and the anchor choice (`wireloaded` / `cpu` /
`unloaded`) moves it by nearly 2×. `alpha` adds a further 7% (ceiling 3.96–4.25 GHz across
1.0–1.6), checkable via `alpha_sensitivity()`.

### Consequence for the MR results

None. Every MR finding is a comparison at fixed clock through one curve, where the curve cancels
entirely, and the degeneracy, plateau, margin-curve and cliff results use density rather than
clock. The one thing to stop quoting is an absolute clock *ceiling* from either curve.
