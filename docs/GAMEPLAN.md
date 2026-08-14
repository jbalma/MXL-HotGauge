# Gameplan

Written after 99 study points completed. Ordered by what unblocks the most downstream work.

---

## STATUS 14 August 2026 — P0.1, P0.2 and P2.6 are done, and P0.1 changed the answers

**P0.1 (convergence verification) is implemented and it retired more than expected.** Full
account in **docs/CONVERGENCE.md**; the short version:

* The old convergence test measured the change between successive solves, which scales with
  `relax`. Tightening the damping for safety therefore made the tolerance ~1/relax *weaker*.
  Two damping levels agreeing could not detect this, because both stop at the same point on the
  same trajectory.
* Measured directly (`examples/trajectory_probe.py`): at 1.15 W/mm² the old test declares
  convergence at **iteration 2** reporting 101.09 °C, while the residual is still 6.5 K, and the
  trajectory then ratchets to **>1000 °C by iteration 52**. At `relax=0.05` it stops at
  100.97 °C — that 0.12 K agreement is what certified those numbers as trustworthy.
* **1.15 W/mm² has no steady state.** The verified no-MR cliff is between **1.05 and
  1.15 W/mm²**, not 1.30–1.40. That cliff is now retired too — it was the same error one level
  up.
* Convergence now tests the damping-independent **fixed-point residual**, the damping
  **backtracks** (rejected steps retaken at half), and every solve is **re-run at half the
  damping with peak agreement required** (`unconverged=True` otherwise). `diverged` means
  diverged at every damping tried. Cost ≈ 2×.
* Validated end-to-end: 1.00 W/mm² gives 89.186 °C against the archived 89.165 °C, damping
  levels agreeing to 0.0001 K.

**A verified MR rescue replaces the retired one.** 34-core, 1.15 W/mm², 88 CFM: the bare die has
no steady state; with MR it converges at **96.83 °C and holds 4.013 GHz without throttling**, for
1.98 W removed from 42 blocks at 3.43 W net electrical. No percentage is quoted — there is no
baseline value to divide by, which is exactly what the +150% got wrong. The band is narrow: at
1.20 W/mm² and above MR does not rescue it either.

**P0.2 done** — the published artifact (`The Constriction Floor`) now carries the correction,
the retraction list, and the trajectory evidence.

**P2.6 done** — `HotGauge/HotGauge/power/clock_search.py` + `examples/clock_headroom.py` search
the highest clock the die can hold instead of derating from a fixed `f_nominal`.

**P1.3 (no-MR arm) — what cooling does a 7nm part at rated clock need?** 34-core, thermal limit
100 °C, clock searched:

| R_th K/W | f sustainable | peak °C | P_die | W/mm² | limited by |
|---|---|---|---|---|---|
| 0.5 | 3.500 | 96.1 | 67.2 | 0.664 | runaway |
| 0.3 | 3.828 | 97.1 | 83.4 | 0.825 | runaway |
| 0.1 | 4.203 | 96.3 | 108.3 | 1.070 | 100 °C limit |
| 0.05 | 4.297 | 97.4 | 117.6 | 1.163 | 100 °C limit |
| 0.02 | 4.344 | 97.1 | 122.4 | 1.210 | 100 °C limit |

**A 25× better cooler buys +24% clock and never reaches the rated 5.0 GHz**, and the last 2.5×
of cooling buys 1.1%. That is the constriction floor expressed in the unit a customer buys. The
MR arms are still running.

The one new assumption in that model — leakage rising with supply voltage as `V^n` — was checked
rather than asserted: at R_th 0.1 K/W the sustainable clock is **4.203 GHz for n = 0, 1 and 2
alike**. It moves the peak (96.05 / 96.3 / 99.77 °C) and which limit binds, not the answer.

**overnight3 is queued** (`scripts/overnight3_study.sh`, summarised by
`scripts/summarise_overnight3.py`). It re-measures everything with verification and is
re-centred on where the answers turned out to be: the cliff at 1.05–1.15 rather than 1.30–1.40,
and the MR rescue ceiling between 1.15 and 1.18. Its Phase 3 asks the question that is now the
most valuable open one — **does a lower MR target push that ceiling out?** If it does, coverage
is the binding constraint; if it does not, the limit is the heat budget, which is a different
device. Points already measured with identical arguments are seeded from `results/cliff_verified`
rather than re-run.

---

## Where we actually are

**Validated and trustworthy:**

| Finding | Evidence |
|---|---|
| Persistent 3D-ICE session: ~150× faster | loop-identical to the Emulator, 194 tests |
| Constriction resistance β−α = 1.042 K/W dominates the hotspot | pinned to source data, 0.09% |
| Static power: leakage saved ≈ heat removed (~60% payback) | 41-point sweep |
| `dt_max` binds, `h_max` does not (10× flux = +0.3 pp) | device-roadmap sweep |
| Pixel pitch 100 µm ≈ 10 µm ≈ 1 µm | confirmed twice, at two targets |
| Coverage: lower MR target has brutal diminishing returns | 47× laser for +0.6 pp |
| ~~True thermal cliff 1.30–1.40 W/mm²~~ | **RETIRED 14 Aug — see below** |
| Thermal cliff between **1.05 and 1.15 W/mm²** (34-core, 88 CFM) | damping-verified, residual criterion |
| MR rescues 1.15 W/mm² (no steady state → 96.83 °C, 4.013 GHz) | damping-verified, peaks agree 0.012 K |

**Void — do not quote:** every result that used `relax=0.5` or `relax=0.1` above ~1.16 W/mm².
That includes "+150%", "−140 K / +288%", "MR rescue at 1.11", and the 128-core rescue. All were
under-damped numerics, not physics.

**Also void as of 14 August:** the **1.30–1.40 W/mm² cliff** and every `results/overnight2`
point at or above ~1.05 W/mm². Those were run at `relax` 0.025/0.0125 and looked
damping-independent, but the criterion they passed *got weaker as the damping tightened*, so the
agreement was between two truncations of the same diverging trajectory. See
**docs/CONVERGENCE.md**.

---

## The one thing that most threatens everything else

**The leakage fixed point needs damping we cannot predict in advance.** We found the true cliff
only by tightening `relax` four times (0.5 → 0.1 → 0.05 → 0.025 → 0.0125) and watching the
answer move. Every tightening changed conclusions.

Nothing currently *detects* under-damping. A study can silently report a converged-looking
number that is 100 K wrong. Two of the three biggest errors in this project were this.

**Fix this before running anything else.** See P0 below.

---

## P0 — correctness (today, before any new science)

### 1. Automatic convergence verification
Every solve should run at two damping levels and require agreement, or use an adaptive scheme.
Cheap now: a point costs ~2 min, and the check roughly doubles it.

* Add `verify_relax=True` to `run_leakage_feedback`: solve at `relax` and `relax/2`, compare
  peak, and mark the result `unconverged` if they differ by more than `tol`.
* Alternatively **Anderson acceleration** or an adaptive relaxation that shrinks on
  oscillation. This is the better long-term answer and removes the guesswork entirely.
* Make `diverged` mean "diverged at every damping tried", not "diverged at the one I picked".

Without this, every future result carries the same risk. **Highest priority by a wide margin.**

### 2. Retire the void numbers from the findings artifact
The published artifact still contains the +150% result and the old cliff. Correct it or it will
be quoted.

---

## P1 — answer the questions we have already set up

### 3. What cooling does a 7nm part at rated clock actually need?
The headline open result: **7nm 16-core at 5.0 GHz sits at 1.953 W/mm² and runs away at 88, 133
and 200 CFM.** That reframes the whole value proposition -- the issue is not reviving old
silicon, it is that **new silicon cannot reach its rated clock on air**.

Runs needed:
* Sweep the cooling solution, not just airflow: better `R_conv`, liquid-class sink resistances
  (0.02-0.05 K/W), and MR on top. Find what is actually required.
* Then the real question: **at a fixed cooling solution, what clock can each node sustain?**
  That is the competitive comparison, and it needs a clock sweep per node rather than a fixed
  `f_nominal`.

### 4. Iso-cooling generational comparison
Currently each node runs at its own native density. Also run all three at a *fixed* cooling
budget and report sustainable clock and throughput. That is the number a customer cares about.

### 5. Re-run the MR comparison at converged damping
Everything in `results/overnight2` above 1.16 W/mm² needs redoing at `relax<=0.025`. The
robust findings listed above survive; the near-wall behaviour does not.

---

## P2 — code features, in priority order

### 6. Clock/voltage as a free variable
Today `f_nominal` is an input and the model only derates downward. To answer "how far can MR
push a part" we need to *raise* the clock until thermal limits bite. Requires V/F scaling above
nominal and a search loop. **This is what turns MR from "recovers throttling" into "enables
higher clocks", and it is currently the ceiling on the whole performance story** -- Study A's
+3.5% ceiling is an artifact of `f_nominal` being a hard cap, not physics.

### 7. Transient / predictive pre-cooling
`core_other_0` (454 µm) has τ ≈ 2.2 ms against a 0.2 ms trace step -- 11× slower, so there is
real lag to exploit. The trace has **16 timesteps and we use one**. Needs time-varying MR plans
and a lookahead controller. The persistent session (prerequisite) is done.

Payoff: pre-cooling should let a *smaller* MR stage hold the same peak, reducing required
`h_max` and peak laser power -- both direct device-cost reductions.

### 8. MR selection policy by leakage contribution
The current policy clips blocks above a temperature target: right for protecting the clock,
wrong for arresting runaway (leakage is a die-wide aggregate). A policy ranking blocks by
`power x sensitivity x reachable area` would select differently. Cheap to try -- `clipping_plan`
already takes the candidate set.

### 9. Calibrate the f_max derate slope
Absolute GFLOP/s inherit an uncalibrated assumption. Ratios are robust; absolutes are not. Until
this is done, report ratios.

### 10. cuDSS — deferred, revisit at 128-core scale
Persistence gave ~150×; cuDSS adds ~3.5× for 1-3 days of CUDA work. Two functions, four call
sites, `SymmetricMode` already set. Worth it only when routine 128-core+ studies are the norm.

---

## P3 — hygiene

* **Commit.** Large body of uncommitted work: `ice_server.py`, `process_nodes.py`,
  `MXL_3DICE_fixes/` (6 files), study scripts, tests.
* **Report upstream to Tufts:** two FMU `fixed=false` bugs and `inspection_point.c:888`
  (network Tflp output has never worked).
* Replace digitised α/β at airflows other than 100 CFM.
* Widen the leakage name bridge over the uncore (~22% of chip power still unbridged).

---

## Suggested order for today

1. **P0.1 convergence verification** -- everything downstream depends on it
2. **P0.2 correct the artifact** -- stop void numbers propagating
3. **P1.3 cooling sweep for 7nm at rated clock** -- the most interesting open result
4. **P2.6 clock as a free variable** -- unlocks the real performance question
5. Commit

Items 1 and 2 are half a day together. Item 3 is mostly runs, which are cheap now. Item 4 is
the largest single piece of new modelling and the one that most changes what we can claim.
