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

So the honest headline is the one the original intuition reached by the wrong route: **0.29 W of
net electrical power gives a 113 W die with no steady state a stable operating point at
99.9 °C** — inside its 100 °C spec, damping-verified, on the cool branch, with the plan
bracketed as the minimum that holds the target. What was wrong before was never the direction,
it was three solver defects and then a policy choice that quietly bought 8 K nobody asked for.

The engineering consequence is worth stating separately: **MR's cost is extremely sensitive to
the operating margin demanded of it.** A part specified to run at its limit is cheap to rescue;
one specified to run 8 K cooler is not. That is a system-design lever, not a device parameter,
and it is bigger than any device parameter measured in this project.

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
