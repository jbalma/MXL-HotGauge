# Convergence: how a diverging run passed as converged, and what replaced it

**14 August 2026.** This is the reference for the P0.1 work in `docs/GAMEPLAN.md`. It documents
the failure, the evidence, the fix, and what the fix costs.

## The failure

The leakage fixed point is solved by iteration: power → temperature → leakage → power. The old
test for "done" was the change between **successive solves**, `|T_n − T_{n−1}| ≤ tol`.

Under-relaxation moves the driving field by only `relax` times its distance from the solution
each step, so

    |T_n − T_{n−1}|  ≈  relax × |T_solved − T_driving|  =  relax × residual

The test therefore got **weaker in proportion to the damping**. Tightening `relax` from 0.5 to
0.0125 — done four times over this project, each time for safety — made the tolerance 40×
looser. A die creeping up a slow leakage ratchet toward runaway passes it on iteration 2.

Worse, the standard check for this — "run it at two damping levels and see if the answers
agree" — **cannot detect it**, because both runs stop at the same place on the same trajectory:
the threshold and the step size shrink together.

## The evidence

`examples/trajectory_probe.py` prints the raw iteration for one operating point. 34-core 7 nm,
1.15 W/mm², 88 CFM, no MR:

| iter | peak °C (r=0.1) | residual K | Δ vs previous solve | old test |
|---|---|---|---|---|
| 1 | 100.85 | 6.81 | 6.81 | keep going |
| **2** | **101.09** | **6.52** | **0.39** | **"converged" → reported 101.1 °C** |
| 11 | 103.56 | 5.80 | 0.56 | |
| 41 | 121.05 | 10.99 | 2.08 | |
| 46 | 135.72 | 18.81 | 3.75 | |
| 50 | 238.43 | 106.21 | 48.92 | |
| 52 | **1092.55** | 926.81 | 720.75 | runaway |

At `relax = 0.05` the same run stops at iteration 2 reporting **100.97 °C** and diverges to
978 °C by iteration 101. Those two numbers agreeing to 0.12 K is exactly the evidence that
certified them as damping-independent in `docs/RESUME_NOTES.md`.

**1.15 W/mm² has no steady state.** The 101.1 °C in the overnight study is iteration 2 of a
divergence.

Raw data: `results/traj_d115/trajectory.json`, `results/traj_d100/trajectory.json`.

## What replaced it

In `HotGauge/HotGauge/power/leakage.py`:

1. **Residual convergence** (`residual_convergence=True`, default). The test is
   `|T_solved − T_driving| ≤ tol` — the actual distance from the fixed point, independent of the
   damping. Pass `residual_convergence=False` only to reproduce pre-fix numbers.
2. **Backtracking damped Picard** (`adaptive_relax=True`, default). A step that increases the
   residual by more than 5% is rejected and retaken from the same anchor at half the damping,
   down to `min_relax=0.025`. Damping is discovered per point instead of guessed.
3. **Divergence means divergence.** At the damping floor, a residual still growing for
   `stall_patience=3` consecutive iterations is reported as `diverged` with
   `diverged_reason='residual_growing_at_min_relax'`. Hitting `max_iter` without converging is
   now warned about explicitly and is neither converged nor diverged.

In `HotGauge/HotGauge/thermal/leakage_feedback.py`, `run_leakage_feedback(verify=True)` (default):

4. **Every solve is verified** at `relax` and `relax/2`; the peak temperatures must agree within
   `verify_tol_K=1.0` K or the result carries `unconverged=True`. Study drivers print
   `** UNCONVERGED **` and drop those points from summary statistics (they stay in the JSON).
5. **`diverged` means diverged at every damping tried.** If a level diverges and a tighter one
   converges, the converged answer is reported and the divergence is recorded as an artefact.

## Does it work?

Measured on a lumped model driven by the real calibrated 7 nm McPAT leakage curve
(`/tmp` probes, reproduced in `HotGauge/HotGauge/power/test_leakage.py`):

| strategy | apparent cliff (θ, K/W) | peak °C |
|---|---|---|
| fixed relax 1.0, old criterion | 11.21 | 77.4 |
| fixed relax 0.5, old criterion | 11.39 | 78.1 |
| fixed relax 0.1, old criterion | 12.58 | 83.4 |
| fixed relax 0.0125, old criterion | 13.79 | 94.0 |
| **backtracking from 1.0** | **11.228** | 77.4 |
| **backtracking from 0.5** | **11.227** | 77.4 |
| **backtracking from 0.1** | **11.229** | 77.4 |

The old path moves the cliff **23%** and the peak **17 K** depending on a knob. The new path
lands in a **0.01%** band from any starting point.

The damping floor does not move the answer (identical cliff to 4 decimals for `min_relax` from
0.005 to 0.1); it only sets how long a genuine runaway takes to declare — 125 solves at 0.005,
48 at 0.025, 11 at 0.05. Hence the 0.025 default.

## Cost

A verified point is 2–3 coupled solves instead of 1: about **4 minutes instead of 2** on the
34-core die with a persistent 3D-ICE session. Divergent points cost more, because the scheme
walks the damping down before it will call a runaway (~48 solves).

Study defaults are now `--relax 0.5 --max-iter 60`. `relax` is a *starting point*.

## End-to-end check against a known-good point

34-core, 1.00 W/mm², 88 CFM: new path **89.186 °C**, archived old path 89.165 °C, and the two
damping levels agree to **0.0001 K**. Points away from the instability are unaffected — this
correction removes results near the cliff, not everywhere.

The same point under the *raw* probe (fixed `relax=0.1`, `tol=0.05 K`, no backtracking) shows
what the healthy shape looks like, and one thing worth knowing: the peak is flat at 89.17 °C
from iteration 2 — here the old criterion happened to be right — while the residual decays
geometrically but slowly (1.92 → 1.24 K over seven iterations, ~7%/iteration) and does not clear
0.05 K within 60 iterations. **A tight residual tolerance at small fixed damping is slow**, and
that is the second reason the damping is now adaptive rather than pinned low: backtracking from
`relax=0.5` reaches the same fixed point in a handful of solves. Do not respond to a slow point
by lowering `relax` — that is what made this class of error possible in the first place.

## What it retires

* the **+150%** MR throughput figure and its 172.5 °C baseline
* the **−140 K / +288%** headline at 1.10 W/mm² and the "MR rescue at 1.11"
* the **1.30–1.40 W/mm² cliff**: the verified no-MR cliff is between **1.05 and 1.15 W/mm²**
* every `results/overnight2` point at or above the cliff

## What replaces them (34-core, 88 CFM, all damping-verified)

| density W/mm² | no MR | with MR |
|---|---|---|
| 1.00 | 89.19 °C | 89.19 °C (MR idle) |
| 1.05 | 93.08 °C | 92.34 °C |
| 1.10 | **no steady state** | **99.55 °C** |
| 1.15 | **no steady state** | **96.83 °C, 4.013 GHz, not throttling** |
| 1.18–1.45 | no steady state | no steady state |

So the no-MR cliff is between **1.05 and 1.10** W/mm² and MR moves it to between **1.15 and
1.18** — an extension of roughly **8%** in sustainable power density, for a few watts of laser.
That is the honest replacement for the retired "+150%": a modest, verified shift of the
stability boundary, not a throughput multiple.

(The 1.15 MR peak being *lower* than the 1.10 MR peak is not a paradox: MR clips against a fixed
92 °C target, and at the higher density more blocks exceed it, so more of the die gets cooled —
1.98 W removed over 42 blocks at 1.15. It is the coverage, not the density, that sets the peak
once MR is active.)

An independent cross-check falls out of the clock study (`examples/clock_headroom.py`), which
holds density free and searches the clock instead. The 88 CFM baffled-fin sink presents ~0.076
K/W of convective resistance; the clock search finds the same die holding 1.070 W/mm² at
R_th = 0.1 K/W and 1.163 W/mm² at 0.05 K/W. Two studies that share no operating point put the
failure of this die in the same 1.05–1.16 W/mm² band.

### RETRACTED later the same day — see docs/MR_RESCUE_COST.md

The rescue costs first published here were wrong. They were sized by a plan builder that read a
**divergent** baseline field, and two further defects sat behind that one. The corrected
measurement is in `docs/MR_RESCUE_COST.md`; the retracted table is kept below so the error stays
legible.

| | 1.10 W/mm² | 1.15 W/mm² |
|---|---|---|
| heat removed | ~~0.394 W over 30 blocks~~ | ~~1.98 W over 42 blocks~~ |
| net electrical cost | ~~0.685 W~~ | ~~3.43 W~~ |
| claim | ~~290 W of die stabilised per watt removed~~ | |

What is true after the correction: a plan of ~0.34 W does give the 1.10 W/mm² die a steady
state, but that state sits at **133.8 °C** — past McPAT's 127 °C validity ceiling and past
anything shippable. Holding a *usable* 92 °C costs **26.8 W of heat removed and 46.6 W
electrical**, cooling all 1126 blocks. There is no cheap rescue on this die, and the reason is
the same degeneracy that limits the clock: when 15 blocks sit within the device's lift of the
peak, moving the peak means cooling the whole plateau.

The surviving structural results from this page — that 1.10 and 1.15 W/mm² have **no steady
state** without MR, that the verified cliff is 1.05–1.10, and everything in the convergence
sections above — are unaffected. What changed is the price of the intervention, not whether the
die needs one.
