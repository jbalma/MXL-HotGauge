# What does an MR rescue actually cost?

**14 August 2026.** This supersedes the rescue figures in `docs/CONVERGENCE.md`, which were
wrong three separate ways in one day. Each version produced a plausible watt figure behind a
converged-looking solve, which is why they need writing down: the failures were never in the
physics, always in what the loop was asked to find.

## The three defects, in the order they were found

**1. The plan was sized from a field that does not exist.** `run_mr_clipping` sized every plan
from an uncooled baseline solve. In the rescue regime the bare die has no steady state, so that
"baseline" is whichever field the iteration was passing through when a runaway guard fired.
Measured (`examples/mr_plan_probe.py`, 34-core, 88 CFM): baseline peaks of 138.7 °C at
1.12 W/mm² and 142.8 °C at 1.15, giving plans of 0.561 W and 1.979 W — **3.5× apart for two
points 3% apart in density**. The smaller plan failed to arrest the runaway and the larger
succeeded, so "does MR rescue this die" was decided by numerics. The symptom was a rescue that
was non-monotone in density: 1.10 yes, 1.12 no, 1.15 yes, 1.16 no.

*Fix:* anchor on the device envelope and descend toward the target, never reading a divergent
field (`plan_mode='envelope'`, default `'auto'`).

**2. The descent stopped wherever its step size left it.** The reported plan still moved with the
iteration budget — 0.615 W at `mr-iter 6` against 0.335 W at 20, same operating point — because
near the stability boundary the loop gain is high and a Newton step on the plan overshoots.

*Fix:* bisect the plan scale between the smallest plan known to hold and the largest known to
fail. On a mock with a true threshold of 3.0 W it returns 3.0126, identically for budgets of 12
and 20. Results carry `plan_is_minimum`; a descent that never reached the boundary reports an
**upper bound** and says so.

**3. It was converging on the wrong objective.** With the bisection working, the bracketed
minimum at 1.15 W/mm² was 0.708 W (bracket 0.704–0.708) — and the peak at that plan was
**133.78 °C**. Descending from the envelope the peak *rises*, so it crosses the 92 °C target
while the plan is still moving, and a convergence test that also demanded a stationary plan
sailed past it to the stability boundary.

*Fix:* detect the target crossing and bisect onto it. Every result now carries
`plan_holds_target` as well, because these are two different questions:

* the minimum plan for a steady state to **exist**
* the minimum plan that holds a **usable temperature**

## THIRD REVISION: the cost is a curve in how much margin you demand

The numbers below (26.8 W removed, 46.6 W electrical) were measured with the MR target at
**92 °C on a die whose limit is 100 °C**. That is not "the cost of a rescue", it is the cost of
a rescue *plus 8 K of margin*, and the margin is almost all of it. Re-measured with the target
2 K under the limit, and with the bistability fix in place:

| density | MR target | peak °C | heat removed | MR electrical | blocks | holds target |
|---|---|---|---|---|---|---|
| 1.10 | 92 °C | 90.96 | 26.8 W | 46.6 W | 1126 | yes |
| 1.10 | **98 °C** | 99.94 | **0.169 W** | **0.29 W** | **4** | yes |
| 1.15 | 92 °C | 90.60 | 42.1 W | 73.0 W | 1126 | yes |
| 1.15 | **98 °C** | 99.87 | **0.814 W** | **1.42 W** | **13** | yes |

**160× for 6 K of margin.** Holding 92 °C means cooling every block in the 92–100 K band, which
on this die is the whole chip; holding 98 °C means cooling the four blocks that exceed it. Both
numbers are right and they answer different questions, which is why quoting either alone is
misleading.

> ### The 98 °C rows WERE provisional — re-runs have now confirmed them
>
> I first wrote this section calling them "damping-verified". They were not, and the check that
> caught it was `scripts/collect_findings.py`, which harvests the verification status alongside
> every value rather than trusting a summary:
>
> | point | final-solve spread | **worst-solve spread** | solves failing |
> |---|---|---|---|
> | 1.10 @ 98 °C | 0.0112 K | **7.32 K** | 1 of 15 |
> | 1.15 @ 98 °C | 0.0006 K | **19.85 K** | 1 of 13 |
>
> The *final* state of each was well converged, which is what I read and reported. But the MR
> loop makes 13–15 solves and one of them was not, so the plan was sized partly from a trajectory
> containing an unverified field. By this project's own rule that is not a result.
>
> That was the fourth revision of this number and the first where the defect was **mine reading
> the data carelessly** rather than a solver bug — I checked `holds_target` and `peak_C` and did
> not check `unconverged`.
>
> **Resolved (17 August).** Two things happened. The verification rule was tightened to
> distinguish the solve that produced the *reported field* from any solve in the loop (commit
> `049a364`), because the searches deliberately visit unstable states to bracket an answer and
> conflating the two condemns good results for probes behaving as designed. And the points were
> re-run with a larger budget. Both now come back **`unconverged: False`** under the reported-field
> rule, and the earlier 1.10 @ 98 °C figure also survived a *stricter* any-solve re-run at
> 0.169 W removed / 0.29 W electrical / 4 blocks / peak 99.95 °C. The numbers in the table stand
> as measured.

So the claim, no longer provisional: **0.29 W of net electrical power gives a 113 W die with no
steady state a stable operating point just under its 100 °C spec.** What was wrong before was
never the direction — it was three solver defects, then a policy choice that quietly bought 8 K
nobody asked for, then a reporting slip.

The engineering consequence is worth stating separately: **MR's cost is extremely sensitive to
the operating margin demanded of it.** A part specified to run at its limit is cheap to rescue;
one specified to run 8 K cooler is not. That is a system-design lever, not a device parameter,
and it is bigger than any device parameter measured in this project.

## FOURTH REVISION: the knee is real, and it moves with the operating point

The 160× above is two points on a curve. Three curves have now been measured, chosen so that the
knee has somewhere to move to if it is a property of the die rather than of a temperature.

**Curve 1 — 1.10 W/mm², 88 CFM air** (uncooled peak: runaway)

| MR target | peak °C | removed | electrical | blocks |
|---|---|---|---|---|
| 93 °C | 93.0 | 34.40 W | 59.7 W | 1126 |
| 95 °C | 96.94 | 0.249 W | 0.434 W | 5 |
| 97 °C | — | 0.43 W | 0.75 W | — |
| 98 °C | 99.95 | 0.169 W | 0.294 W | 4 |
| 99 °C | 100.99 | 0.145 W | 0.252 W | 4 |

**Curve 2 — 1.15 W/mm², 88 CFM air** (harder point, same cooling)

| MR target | peak °C | removed | electrical | blocks |
|---|---|---|---|---|
| 93 °C | 94.39 | 28.31 W | 49.11 W | 1126 |
| 94 °C | 94.40 | 28.05 W | 48.66 W | 1126 |
| 96 °C | 94.44 | 27.53 W | 47.76 W | 1126 |
| 98 °C | 99.87 | 0.814 W | 1.42 W | 13 |

**Curve 3 — 1.10 W/mm², liquid-class sink (R_th 0.05 K/W)** (uncooled peak **93.59 °C** — it
holds on its own)

| MR target | peak °C | removed | electrical | blocks |
|---|---|---|---|---|
| 93 °C | 93.00 | 0.023 W | 0.040 W | 2 |
| 94 / 96 / 98 °C | 93.59 | **0** | **0** | **0** |

### What the three say together

**The knee moved, and it moved the way the plateau predicts.** On curve 1 it sits near 94 °C; on
curve 2, at 0.05 W/mm² more, it sits between 96 and 98 °C. In both cases the jump is the same
mechanism: `blocks` goes from 4–13 to **1126** in one step. Below the knee the demanded target
dips into the thermal plateau, and cooling *anything* means cooling *everything*.

So the knee is **not an absolute temperature** and must not be quoted as one. It tracks the top
of the block-temperature distribution, which moves with density. That is the same degeneracy
result arriving from a third direction, and it is the sharpest form of it: the cost of MR is set
by how many blocks sit between the operating point and the target, and nothing else.

**Curve 3 is the one worth arguing about.** At the same 1.10 W/mm², a liquid-class sink puts the
uncooled peak at 93.59 °C — under the 100 °C limit, no runaway, no rescue required. Targets of
94, 96 and 98 °C engage **zero blocks**. Better cooling did not make MR more valuable; it made MR
**irrelevant**, because the failure MR was rescuing no longer happens.

That is a genuinely uncomfortable result for the technology and it should be stated plainly:
across these three curves, MR pays only in a **narrow band** — a die hot enough to be unstable on
the cooling it actually has, and specified to run close enough to its limit that the target stays
out of the plateau. Move either way and it goes to zero: cool the die better and there is nothing
to rescue; demand more margin and the price rises 30–160×.

The cliff work bounds the other edge of that band. At 1.17 W/mm² the rescue costs **14.98 W
removed / 25.99 W electrical over 92 blocks** — 18× the 1.15 figure. So the band in density is
roughly 1.05 (below which nothing is needed on air) to somewhere under 1.17 (above which the
price has left the "essentially free" regime).

## The earlier measurement (target 92 °C)

34-core 7 nm, 88 CFM, MR target 92 °C, spot ≥ 10 µm, damping-verified, plan bracketed by
bisection:

| density W/mm² | bare die | heat removed | MR electrical | blocks cooled | peak °C | holds target |
|---|---|---|---|---|---|---|
| 1.10 | no steady state | **26.8 W** | **46.6 W** | 1126 | 90.96 | yes |
| 1.15 | no steady state | 42.1 W | 73.0 W | 1126 | 90.60 | yes |
| 1.18 | no steady state | 44.9 W | 77.8 W | 1126 | 92.65 | yes |
| 1.10 (stability only) | no steady state | 0.34 W | 0.59 W | 7 | **133.8** | **no** |

**1126 blocks is the entire die.** Holding a usable temperature costs a quarter of the die's own
power in heat removed, at 46.6 W of wall power to remove it — microrefrigeration used as a bulk
cooler, which this model has always said is a net loss (electrical COP 0.14).

The last row is the trap. A 0.34 W plan really does give the die a steady state; that state is
133.8 °C. **"A steady state exists" and "the part works" are different claims**, and the cheap
number belongs only to the first.

## Why it is so expensive, and what could change it

The top of this die's temperature distribution is a **plateau, not a spike**
(`examples/thermal_tiers.py`): 15 blocks within the device's 10 K lift of the peak, and they are
the same functional units repeated across cores. Clipping the hottest buys the 1.25 K gap to its
twin. Moving the peak means cooling the plateau, and on a homogeneous many-core the plateau is
the chip — which is exactly the 1126 blocks above.

So the cost is a property of **this design and workload**, not of MR:

* single-core turbo halves the plateau (15 → 7) but exposes a second, *intra-core* degeneracy —
  the hot functional units within one core also sit within a few K;
* the open candidate is a core with one dominant hot structure (a matrix engine rather than a
  balanced scalar core), which is what current AI silicon looks like.

See `docs/DESIGN_STUDY_PLAN.md`.

## One caveat on the number itself

26.8 W is the minimum along the path the descent takes, which scales an envelope-shaped plan
down. It is **not** proven to be the cheapest possible plan: a smarter block-selection policy —
ranking by leakage contribution rather than by temperature threshold — might hold the same
target for less. That is now the most valuable open question in the MR model, and it is item 8
in `docs/GAMEPLAN.md`.

---

## AXIS CORRECTION (19 August): these are rescue costs, not hold-a-temperature costs

Every number in this document answers **"what is the cheapest plan that gives this die a steady
state?"** — not "what does it cost to hold this temperature?". The two differ by up to **450×** at
the same density and the same nominal target, and the `--mr-target-C` label made them look like
one quantity.

The discrepancy surfaced when `examples/cop_breakeven.py` priced 1.10 W/mm² at a 98 °C target and
got 131 W, against the 0.29 W in the table above. Neither is wrong; the solver said so in its own
`reason` strings, which I had not been reading:

| | reason returned | achieved peak | blocks | electrical |
|---|---|---|---|---|
| this document | *minimum plan that keeps the die on the **cool branch*** | 99.95 °C | 4 | **0.29 W** |
| `cop_breakeven` | *minimum plan that **holds the target*** | 98.59 °C | 1126 | **131.3 W** |

Both are minimal for their own question and both converged. The rescue lands wherever the cool
branch happens to sit — here 99.95 °C, just under the 100 °C limit — and costs almost nothing,
because arresting a runaway needs only the few blocks that drive it. Pinning the peak to 98.0 °C
instead means cooling everything between 98 and 100 °C, which on this die is the whole plateau.

**A `tol_K` of 2.0 K is what let one pass as the other.** A plan that lands at 99.95 against a
98 °C target reports `holds_target: True` because it is within tolerance — and the cost difference
across that 2 K band is 450×. That is the knee of the margin curve, seen at far finer resolution
than the curve itself resolves.

### What changes and what does not

**Unchanged:** every measured value, the knee at ~94 °C on curve 1 and ~97 °C on curve 2, the
observation that the knee tracks the top of the block distribution rather than an absolute
temperature, the three-curve comparison, and the conclusion that MR's cost is dominated by how many
blocks sit between the operating point and the target. The physics and the mechanism stand.

**Changed:** the axis label and the headline. This is a **rescue-cost curve**. Read
"MR target 98 °C" as *"consider blocks above 98 °C as candidates"*, not as *"hold the die at
98 °C"*. The achieved peak is in the tables and is the number to quote alongside the watts.

The rescue result itself is unaffected and remains the strongest MR finding on the CPU die:
**0.29 W of net electrical power gives a 113 W die with no steady state a stable operating point
just under its 100 °C spec.** What that sentence does *not* claim, and never did, is that 0.29 W
holds any particular temperature below it.
