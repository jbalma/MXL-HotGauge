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
