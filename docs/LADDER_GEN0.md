# Generation 0 of the evolution ladder — what it can claim, and what has to be built first

Working plan for `docs/CODESIGN_PLAN.md` §9. The plan says where the programme is going; this says
what the first rung actually consists of, what is ready, and **two corrections to §9 that change
what the ladder's headline can be**.

Status: 26 August 2026. Gen 0 is blocked on the P0.5 catalogue re-run for its baseline. Everything
below that does not need a thermal solve is buildable now.

---

## 1. The prerequisite §9 names is already answered — and the answer is "do not extend the table"

§9 says:

> `clock_search` bisects against a **V/F table that stops at 5.0 GHz**. […] a study of whether LCMR
> reaches 6 GHz cannot be run on a table that stops at 5. Extending the V/F table […] is a
> prerequisite for gen 0 rather than a step within it.

That rests on a misreading, and `clock_search.py:63-72` already says so. The table does not stop at
5.0 GHz because the data ran out. **It stops because the device does.** Checked, not quoted:

| target | supply the fitted curve demands | dynamic power vs 5.0 GHz |
|---|---|---|
| 5.0 GHz | 1.40 V — the top of the table | 1.00× |
| 5.5 GHz | **1.82 V** | 1.86× |
| 6.0 GHz | **2.74 V** | 4.60× |
| 6.5 GHz | **unreachable at any voltage** | — |

`VF_PAIRS` is a voltage→frequency table topping at 1.40 V → 5.01 GHz. It *was* fitted by one
alpha-power curve to 0.3% RMS at **α = 0.949** — and because α < 1, `f(V) = k(V−V_th)^α / V` has a
maximum at `V_th/(1−α)`, which is where the **6.43 GHz at 9.40 V** ceiling came from. That ceiling
was an artefact of the exponent, not a property of any device.

**Corrected 27 Aug 2026** (`docs/evidence/vf_curve_correction.json`). `VF_ALPHA_POWER_FIT` is now
refitted under α ≥ 1 and the bound **binds** — α lands exactly on 1.0, k = 7.5485, V_th = 0.4643,
RMS 0.74%. The corrected curve is monotonic and needs **1.71 V for 5.5 GHz, 2.26 V for 6.0** and
3.34 V for 6.5, so the conclusion below is unchanged: the 1.4 V device ceiling binds at 5.0 GHz.

The refit turned up something larger than the correction. Forced to α = 1.4, the textbook's own
typical value, the table misfits by **4.93% RMS — seventeen times worse** than the free fit. The
data actively resist the physical range. The shape says why: 1.5 GHz per 200 mV at the bottom of
the table, 0.1 GHz per ~50 mV at the top. A device's delay law does not saturate like that; a
**product bin table** does, because the top of a bin range is reliability-limited guardbanding.
So the honest reading is not "we had the wrong exponent" but **"the alpha-power law is the wrong
model for this table"** — which is the clearest evidence in the repository that `VF_PAIRS` is a
binning artefact rather than a device curve.

> **`[!]` Qualified 30 August 2026 — and the qualification matters.** The floorplan pack supplies
> the first real (V, f) anchor this project has had: Arm Neoverse V1/V2 at **2.8 GHz / 0.75 V**.
> The shipped table lands at **0.747 V** there — **within 0.4 %** — while every IRDS node comes in
> 34–53 % low. The shape argument above is untouched, and the table's *high* end remains suspect.
> But "binning artefact" should not be read as "unusable": at the frequencies server parts
> actually run, `VF_PAIRS` is the most accurate V/F source in the repository.
> `docs/evidence/vf_anchor_check.json`.

Extending the table would therefore mean modelling a supply voltage that destroys the gate oxide.
A `vf_clamped` verdict is **a result — voltage-limited, not thermally limited** — and it is one of
the six binding constraints §9's own table lists.

The roadmap curves are *tighter*, not looser. `IRDSVFModel` at each node's overdrive limit:

| node | vdd | V_t | SS mV/dec | f_max |
|---|---|---|---|---|
| 2024 "3nm" Enhanced | 0.70 | 0.1556 | 82 | 3.34 GHz |
| 2027 "1.4nm" | 0.60 | 0.1635 | 70 | 3.82 GHz |
| 2031 "A7 eq" | 0.60 | 0.1638 | 70 | 4.54 GHz |

**Consequence for the ladder.** On every curve available, "does LCMR buy 6 GHz?" is answered
*no, and not for a thermal reason*. The ladder's headline cannot be clock-at-fixed-V_t. The
checklist item *"Extend the V/F table past 5.0 GHz"* should be closed as **answered, not done**.

---

## 2. What the headline becomes: the threshold-voltage lever

§9 already identifies it and calls it *"the deepest lever, and the one only LCMR unlocks"*. It is
also the one lever that **does not run into the voltage ceiling**, because lowering V_t *shifts the
curve* rather than climbing it.

The trade, and every term of it is already in the repository:

* **the gain** — `f(V) = k(V−V_t)^α / V`, so at fixed supply a lower V_t is more overdrive and
  more clock;
* **the cost** — subthreshold leakage rises as `10^(ΔV_t / SS)`, and `IRDS_NODES` carries
  `ss_mV_dec` per node, so the cost is *the node's own number*, not an assumption;
* **the payback** — leakage is exponential in temperature and this project has a **calibrated**
  curve of exactly that (`leakage_calibration/`), so the kelvin needed to undo the leakage cost is
  a measured quantity.

Computed from those three, at α = 1.3 and the calibrated local doubling at 370 K (10.9 K):

| node | ΔV_t | clock gained | leakage cost | cooling that pays for it |
|---|---|---|---|---|
| 2024 "3nm" | 25 mV | **+6.0 %** | 2.02× | **11.0 K** |
| 2024 "3nm" | 50 mV | +12.1 % | 4.07× | 22.0 K |
| 2024 "3nm" | 75 mV | +18.3 % | 8.22× | 33.0 K |
| 2027 "1.4nm" | 25 mV | **+7.5 %** | 2.28× | **12.9 K** |
| 2027 "1.4nm" | 50 mV | +15.1 % | 5.18× | 25.8 K |
| 2031 "A7 eq" | 50 mV | +15.2 % | 5.18× | 25.8 K |

**For scale: the measured passive term alone — swapping 30 µm of thermal grease for 30 µm of GaAs,
with the laser off — was 14.4 K on the 7-core die**
(`docs/evidence/three_arm_first_runs.json`). So on these numbers *the packaging change by itself is
worth roughly one 25 mV V_t step*, and the laser is what buys the second one.

That is a co-design claim of the right shape: it does not exist without active cooling, it is
stated in the vendor's own units (V_t, SS, GHz), and it is testable with what is built.

**Three caveats, stated before the number is used.**

1. **α = 1.3 is an assumption.** `IRDSVFModel.alpha_sensitivity` exists precisely to price it;
   any sign that changes across α ∈ [1.0, 1.6] is not a finding.
2. **The trade only exists in the hot regime.** The calibrated local doubling is 10.4 K at 360 K
   but **300 K at 320 K** — i.e. essentially no leakage sensitivity down there. A part already
   running cool gains nothing from cooling it further, which is the honest boundary of the claim.
3. ~~**`IRDSVFModel` does not yet take a V_t override.**~~ **WRONG — checked 27 Aug 2026, the
   override already exists.** `IRDSVFModel.__init__` takes `vt_shift_mV`
   ([irds_vf.py:112](../HotGauge/HotGauge/power/irds_vf.py#L112)), and it does the subtle part
   correctly: `_k` is calibrated on the node's **nominal** V_t and then held fixed while V_t
   moves, with a comment in the source explaining that re-fitting `k` to the shifted V_t would
   force the curve back through the same anchor and the lever would buy exactly nothing.
   `leakage_multiplier` (`10**(dVt/SS)`) is there too, and
   `TestThresholdVoltageLever` covers both. **The V_t rung is runnable today**, and — because
   lowering V_t *shifts* the curve rather than climbing it — it does not wait on the V/F curve
   either. This caveat was gen 0's only named code blocker and it does not exist.

---

## 3. What gen 0 consists of

Per §9, gen 0 is *"baseline floorplan, solved WITH and WITHOUT LCMR — the delta is not the result,
the BINDING CONSTRAINT it reveals is"*. Concretely:

1. **Establish the baseline on the corrected boundary.** The P0.5 re-run is that baseline. It must
   land first: `--spreading` moved absolute temperatures a long way (the 34-core boundary went
   0.0764 → 0.3247 K/W), so a gen-0 rung built on pre-correction numbers would be measuring the
   old sink model.
2. **Name the binding constraint from the solve**, using §9's table. The pipeline already emits
   every signal it needs: `core_fmax`'s peak block, `diverged`, `vf_clamped`, the plan hitting
   `max_total_W`, and the proportional-vs-targeted divergence.
3. **Record the three invariants** with each rung — same workload and trace, same die power, same
   MR *electrical* budget. `mr_comparison` and `clock_headroom` already stamp arm, placement,
   pitch, burial and stack spec on every row; the MR electrical budget is in `mr_accounting`.

### Ready now, no solver needed

**Phase 1 floorplan metrics** (§3) are computable from a floorplan plus a power trace. Four of the
five candidates already have code behind them:

| metric | status |
|---|---|
| peak-to-runner-up gap | **re-run and it holds** — 1.18 K (fpu2) to 8.07 K (g4_turbo_idle), a 6.8× spread across shapes, and **independent of `dt_max`** |
| plateau width at `dt_max` | **DEGENERATE at the demonstrated envelope — must be redefined or dropped** |
| tile alignment at a pitch | `mr_array.coverage_report` — relationship to benefit untested |
| power-density concentration (Gini / top-decile) | **not built** — trivial from a trace |
| thermal aspect (hot-block distance to die edge) | **not built** — trivial from a floorplan |

**The first two are not two metrics.** Measured across the `dt_max` ladder on 27 August
(`docs/evidence/tier_screens_dt_ladder.json`, 44 points, eleven workload shapes):

* **Plateau width collapses to the whole die at `dt_max` = 45 K.** Every shape returns 1126 of
  1126 blocks. At `dt_max` = 10 K the same shapes span **4 → 56 blocks**, a 14× spread and a
  genuinely discriminating screen. The reason is arithmetic: the die's own temperature spread is
  **31.9–45.0 K**, i.e. *smaller than the demonstrated lift*, so "blocks within `dt_max` of the
  peak" evaluates to "all of them". The metric was only ever informative because `dt_max` was
  pinned at an unsourced 10 K.
* **Clip-one gain does not depend on `dt_max` at all** — identical to six decimal places across
  the whole ladder. `gain = T[0] − max(T[0] − dt_max, T[1])` reduces to `T[0] − T[1]` whenever the
  runner-up is within `dt_max`, which here it always is. So clip-one gain **is** the
  peak-to-runner-up gap, and gen 0 has one robust metric here rather than two.

This also converges with the die-average strategy result from the other direction: once lift is
large relative to the die's spread, *which blocks are within reach* stops being the question and
*where to spend the watts* becomes it.

The deliverable is a regression of measured MR benefit against these, across the floorplan and
workload variants the re-run is producing. **Any metric that does not predict is dropped.** This is
the step that turns the pipeline into something a third party can use without it.

**RUN 27 August 2026** — `docs/evidence/metric_regression_gen0.json`, 11 workload shapes × 3
demanded margins, 33/33 usable. It could not be run before because the predictors and the response
had never been measured on the same points: the shapes existed only in the control-arm tier
screens, and all 35 catalogue points with a measured MR benefit ran at uniform activity on one die.

*First, the obvious response variable is wrong.* `benefit_K` correlates **0.956** with the demanded
margin, because the planner holds the derived target by construction. Benefit is an input. The
response that means anything is **cost** — the heat that must be removed to buy that margin.

| metric | vs cost at 3 / 5 / 8 K | verdict |
|---|---|---|
| **`relative_plateau_25pct`** | ρ **+0.843 / +0.825 / +0.852**, p ≤ 0.0018 | **KEEP — lead with it** |
| `die_span_K` | ρ −0.655 / −0.682 / −0.736, significant throughout | **PROMOTE** — was stamped for context only |
| `peak_to_runner_up_gap_K` | ρ −0.682 / −0.682 / −0.582, **p = 0.060 at 8 K** | KEEP but **DEMOTE** |

So the metric built to replace the degenerate `dt_max` plateau is the strongest predictor at every
margin, an incidental one matches the named gap metric, and the gap — which only sees the top two
blocks — loses significance exactly where the plan is pushed into the plateau.

**And a split no current metric predicts.** Efficiency retained from 3 K to 8 K of margin divides
the shapes cleanly: six retain **97.7–100 %**, five retain **37.4–53.5 %**, with almost nothing in
between — and it is *not monotone in plateau* (turbo at 15 and turbo_idle at 19 retain ~98 %, while
fpu4 at 12 retains 43 %). `relative_plateau` predicts it only weakly (ρ −0.647) and the gap not at
all (p = 0.23). **A third metric is needed, and this says what it must measure**: not how wide the
plateau is, but how fast cost per kelvin degrades as the plan is pushed into it — a property of the
distribution's shape *below* the peak, which none of the four current metrics looks at.

**What this sweep could not test.** It varied workload, not floorplan — one die throughout — so
`power_density_concentration` and `thermal_aspect` were constant across all 33 points and remain
**untested**. They need floorplan variants: the 7/70/128-core dies, or the ARM and RISC-V
floorplans that do not yet exist.

### Blocked, and on what

| item | blocked on |
|---|---|
| gen-0 baseline | P0.5 catalogue re-run |
| the V_t lever, runnable | a `vt` override on `IRDSVFModel` (small) |
| anything a vendor cannot argue with | acceptance gate at 4/4, currently **2/4**, and §4 route (c) |
| turbo / boost policy rungs | P0.6 transient + a burstier trace |
| any rung resting on power delivery | **out of scope and must be labelled** — nothing in the pipeline sees IR drop, dI/dt or the PDN |

---

## 4. What this cannot license yet

Unchanged from §9, and worth restating because the V_t result above is attractive enough to be
misused: generation *n* is a floorplan we designed to our own rules and scored on our own pipeline.
The acceptance gate is **2 of 4** (`docs/evidence/acceptance_gate_spreading.json`), and one of the
two passes runs 5.8 K cold with its cooler at the solver floor. Until that is 4/4 and at least one
ISA's areas come from something a vendor cannot argue with, the ladder characterises **our model's
response to LCMR**, not silicon.
