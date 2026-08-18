# Solver capacity: what is ready now, what unlocks what, and when the GPU port pays

**18 August 2026.** Written to replace an argument conducted in anecdotes. Every number here is
measured on node-03 or derived from `scripts/solver_cost_model.py`, which fits the measurements
and reports its own residual.

## The cost of a study, and the one variable that matters

```
T  =  M x F(N)  +  S x s(N)
```

* `M` — **distinct system matrices**. Not the number of runs.
* `F` — factorisation time, superlinear in the unknowns `N`.
* `S` — total solves. Nearly free once factorised.

A faster solver scales `F` only, so its value is proportional to `M`. And `M` is not what anyone
assumes it is, because the matrix is built from the stack and the floorplan **geometry**
(`ice_server.matrix_fingerprint`):

| changing this… | new matrix? |
|---|---|
| die power, density, kernel/activity, MR target, `dt_max`, COP, leakage fraction, spot policy | **no — free** |
| airflow (CFM), `R_th`, floorplan, grid, core count, die count, ambient | **yes — full refactorisation** |

**Workload sweeps are free. Cooling and geometry sweeps are not.** That single distinction is the
whole answer to "when does a faster solver help".

## Measurements

| case | unknowns | factorisation |
|---|---|---|
| 34-core CPU die, 50 µm | 691 k | 87.5 s |
| GA100, 100 µm | 1.41 M | 431.3 s |
| GA100, 50 µm | 5.64 M | 2849.2 s |

Per-solve after factorisation: 0.43 s at 691 k. A whole additional accelerator study point,
including its leakage fixed point, costs **4.7 s** once the matrix is up.

A single power law fits with a 23% residual (`F ≈ 3.69e-8 · N^1.618`); the local exponent is 2.24
over the first interval and 1.36 over the second, which is normal as sparse LU moves between cache
and memory regimes. The fit was still good enough to predict the 50 µm run at **2916 s against
2849 s measured — 2.3% error over an 8× extrapolation**, which is why the model is trusted enough
to make a decision with.

Composition of a large run: **98.9%** of the 50 µm run and **97.1%** of the 100 µm run is the
single factorisation. There is no Amdahl problem — the target is clean.

## What was actually costing us: process isolation, not the solver

`ICESessionCache` reuses a factorisation while the matrix is unchanged, but it cannot cross a
process boundary, and every batch script ran one process per point. Auditing the accelerator work:

> **42 runs. 4 distinct matrices. 38 redundant factorisations — 4.6 hours.**

`scripts/sweep_runner.py` runs the points of a sweep in one process instead. Measured on three
points sharing a matrix: **339 s, then 4.7 s, then 4.7 s.** Applied to the batches already run:

| batch | points / matrices | before | after |
|---|---|---|---|
| kernel sweep | 16 / 1 | 1.9 h | 8 min (**14×**) |
| accelerator MR | 8 / 1 | 1.0 h | 8 min (7×) |
| `dt_max` sweep | 9 / 1 | 1.1 h | 8 min (8×) |
| whole campaign | 42 / 4 | 5.0 h | 32 min (**10×**) |

One caveat, so this is not oversold: the sweep runner is **serial**. A matrix-*diverse* sweep run
4-wide across processes still finishes sooner than one process doing them in sequence. The right
pattern is to **group points by matrix, run each group in one process, run the groups in
parallel** — which is also exactly the structure a GPU port would want.

The cache singleton had to live in `ice_server`, not in the study script: `runpy.run_path`
re-executes the script and resets its globals, so the first attempt still factorised once per
point while looking like it was sharing. Three tests pin that.

## Readiness: when are we able to test many distinct configurations?

**Matrix-identical sweeps: ready now.** Die power, kernel, occupancy, `dt_max`, MR target and the
whole efficiency chain sweep at 4.7 s per point. A 50-point workload study is ~10 minutes. This is
what today's work unlocked, and it is most of what the accelerator questions need.

**Matrix-diverse sweeps: ready, and priced.** Each point costs a full factorisation — 431 s at
GA100/100 µm. The first real one is the COP break-even study (`examples/cop_breakeven.py`), which
bisects on airflow and therefore needs a *new matrix per trial*: about 8 per operating point.

| study | matrices | CPU | GPU (×3.5) |
|---|---|---|---|
| COP break-even, 1 operating point | 8 | 1.0 h | 0.3 h |
| COP break-even, 5 operating points | 40 | 4.8 h | 1.4 h |
| …at 50 µm instead | 40 | 31.7 h | 9.0 h |

**The one gap:** `cop_breakeven.py` currently builds the Skylake CPU floorplan only. Running it on
GA100 needs the accelerator floorplan wired into it — a small change, and the prerequisite for any
matrix-diverse accelerator study.

## When the GPU port pays

At the gameplan's estimated 3.5× on factorisation, and 12 engineering-hours for the port:

> **Break-even at ~140 distinct matrices at GA100/100 µm scale** (each avoided factorisation saves
> 308 s). That is roughly **3–4 full COP break-even studies** on the accelerator.

So the trigger is specific and checkable:

* **GO** when the plan contains **four or more matrix-diverse studies** on a die of GA100 scale —
  cooling ladders, geometry sweeps, or COP break-evens — *or* one such study at 50 µm, where a
  single campaign is 32 h on CPU and 9 h on GPU.
* **NO-GO** while the work is workload sweeps, which the session cache has just made free, or
  single-configuration deep dives.

Two things must be true before spending the days, and today only one is:

1. **The work must be matrix-diverse.** Grouping by matrix first is not optional — it is a 10×
   that costs nothing, and applying a 3.5× on top of unfixed process isolation would be paying for
   hardware to hide a scheduling bug.
2. **The GPUs must exist.** The node is named `node-03-6xv100`, but `nvidia-smi` in this allocation
   reports *No devices were found*. Estimated fill-in is ~2 GB at 1.41 M unknowns and ~12 GB at
   5.64 M, so a 32 GB V100 is comfortable and a 16 GB one is marginal at 50 µm.

## The other wall, which the GPU does not fix

Deep memory stacks fail with SuperLU 4.3's `Can't expand MemType 0: jcol 1710392` at ~1.7 M
unknowns. The node has 629 GB and the estimated fill is ~2 GB, so this is **not** running out of
memory — it is an expansion heuristic in a solver from 2011. That is a robustness wall, not a speed
wall, and a modern CPU solver (MUMPS, PARDISO, SuperLU_DIST) fixes it for far less effort than a
CUDA port. **If deep stacks become central, do that first and independently of the GPU decision.**

## Recommendation

| action | trigger | effort | payoff |
|---|---|---|---|
| Group sweep points by matrix, one process per group | **now — done** | done | 10× measured |
| Wire the GA100 floorplan into `cop_breakeven.py` | next matrix-diverse study | hours | unblocks item 4 on the accelerator |
| Replace SuperLU 4.3 (CPU) | deep stacks become central | ~1 day | removes the 1.7 M-unknown ceiling |
| cuDSS GPU port | ≥4 matrix-diverse GA100-scale studies planned, **and** GPUs exposed | 1–3 days | 3.5× on 98% of large-run walltime |

The honest summary of today: the two walls I was ready to cite as evidence for the GPU port were a
session cache in the wrong scope and a hard-coded timeout, and the third — 4.6 hours of redundant
factorisation — was process isolation. All three were free to fix and together they are worth more
than the port. The port is still the right answer eventually, and the condition for it is now a
number rather than a feeling.
