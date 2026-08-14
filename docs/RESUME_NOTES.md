# Resume notes — MXL-HotGauge

> **SUPERSEDED IN PART, 14 August 2026.** The relaxation correction described below is real but
> did **not** go far enough. The convergence *criterion* it relied on (change between successive
> solves) scales with `relax`, so tightening the damping made the test weaker — and "relax=0.1
> and 0.05 agree to 0.1 K" turns out to be agreement between two truncations of the same
> diverging trajectory, not convergence. **1.15 W/mm² has no steady state**; the 101.1 °C below
> is iteration 2 of a runaway. Read **docs/CONVERGENCE.md** before trusting any number on this
> page, and treat the table under "THE correction" as an illustration of the old failure rather
> than as results.

Last updated at the start of the overnight study. Everything below is on disk; nothing depends
on a live terminal.

## First thing in the morning

```bash
cat results/overnight2/SUMMARY.txt         # main study (44 points)
cat results/followon/SUMMARY.txt           # follow-on: MR ceiling + generational
tail -20 results/overnight2/driver.log     # progress if still going
squeue -u jbalma                           # is allocation 1154 still alive?
```

`results/overnight/` (no "2") is the FIRST attempt and should be **ignored** -- it ran at
relax=0.5 and is invalid. See the relaxation correction below.

If points are marked INCOMPLETE, just re-run — completed points are skipped:

```bash
bash scripts/overnight_study.sh <jobid>
```

If the allocation died, get a new one and pass the new jobid. Results live on NFS under
`results/overnight/`, so nothing is lost when a node goes away.

---

## THE correction: relax=0.5 was corrupting results in both directions

The leakage fixed point ``T -> f(T)`` has loop gain above the stability limit for
under-relaxation of 0.5, so the iteration diverged **numerically** at densities where a
perfectly good physical solution exists -- and, worse, sometimes satisfied the convergence
tolerance at a partially-diverged value.

| density | relax=0.5 | relax=0.1 | relax=0.05 |
|---|---|---|---|
| 1.00 | 89.2 C | 89.2 | 89.2 |
| **1.10** | **RUNAWAY** | **96.3** | **96.3** |
| **1.15** | **RUNAWAY** | **101.1** | **101.0** |
| 1.25 | RUNAWAY | RUNAWAY | RUNAWAY |
| 1.40 | RUNAWAY | RUNAWAY | RUNAWAY |

relax=0.1 and 0.05 agree to 0.1 K, so those are trustworthy. **The true cliff is between 1.15
and 1.25, not 1.11.**

**Retired by this:** the "-140 K / +288% at 1.10 W/mm^2" headline and the "MR rescue at 1.11".
1.10 was reported as *converged at 239.7 C*; the true value is 96.3 C, so the MR delta was
measured against a partially-diverged baseline. Also retired: the Phase-2 conclusion that a
lower MR target does not help -- every one of those points was a false runaway.

Default is now ``--relax 0.1`` in both study scripts, and Phase 2 of the new study runs each
cliff point at BOTH 0.1 and 0.05 so this class of error cannot recur silently: a genuine
runaway diverges at any damping, a numerical one does not.

## The earlier correction: max_iter

**`max_iter = 12` was silently converting thermal runaways into plausible finite temperatures.**

Measured on the 34-core die at 88 CFM with a persistent session (`max_iter=60`):

| P_die | iters | converged | result |
|---|---|---|---|
| 80.0 W | 2 | yes | 74.6 °C |
| 100.0 W | 3 | yes | 88.3 °C |
| 116.4 W | 13 | **no** | **RUNAWAY** |
| 140.0 W | 5 | **no** | **RUNAWAY** |

Convergent cases settle in **2–3** iterations, so 12 never limited them. But the 116.4 W runaway
is not detected until iteration **13** — one past the old limit. The default is now **30** in
both study scripts.

**What this retires:** the "+150% MR throughput" result and its 172.5 °C no-MR baseline. That
configuration has *no steady state*; the baseline was iteration 12 of a diverging sequence and
the delta was measured against an arbitrary stopping point. Do not quote it. The findings
artifact still contains it and needs updating once the overnight numbers land.

This was invisible at 70 min/point and obvious at 2 min/point — the speedup's main value so far
has been error detection, not throughput.

---

## What survives from the first attempt

Only two things, both at relax-independent densities:

* MR is correctly **idle** below its target (0.90 and 1.00 W/mm^2 gave bit-identical MR-on and
  MR-off results) -- the clipping logic does not fire when nothing is above target.
* **Pixel pitch barely matters** at the operating point tested: 100 um / 10 um / 1 um gave
  identical peaks, and even 100 um with ``exclude`` lost only 0.4 K. The peak is set by
  ``core_other_0`` (454 x 1027 um), which any pitch reaches -- the high-*density* blocks
  (``RBB`` at 13.4 um) are not the ones setting peak temperature. If that holds on other
  floorplans it is a large fabrication saving, since ``examples/tile_array_tradeoff.py`` puts a
  100 um array at ~450 pixels against ~32,000 at 10 um. **Worth re-confirming** in the new
  study (Phase 4) at a target where MR is actually working.

Everything else from that run used relax=0.5 and is void.

---

## Performance work — done and validated

`3D-ICE-Emulator` re-factorised an unchanged matrix on every solve. A persistent
`3D-ICE-Server` session factorises once and re-solves against new right-hand sides.

| | |
|---|---|
| factorisation (once) | 87–88 s (34-core, 691k unknowns) |
| each solve after | **0.43–0.57 s** |
| one MR point | ~70 min → **~2 min** |

Validation, all passing:
* per-solve equality vs the one-shot Emulator: max \|dT\| = 0.0005 K
* **whole leakage loop identical iteration-for-iteration** (372.6 → 448.1 K, both paths)
* 192 fast tests + 2 slow tests

Scaling measured as `t ~ N^1.67` (3D sparse LU), so factorisation — not parsing or assembly —
dominates. Projected: 128-core (2.4M unknowns) ≈ 670 s to factor, ~14 min per MR point.

### Three bugs found doing it

1. **`3D-ICE-Server` refused steady analysis** (`3D-ICE-Server.c:97`). The persistence machinery
   already existed; only that guard blocked it.
2. **Upstream: `inspection_point.c:888`** wrote `Temperature_t` (a double) through
   `insert_message_word()`, which copies 4 bytes — so every Tflp temperature on the socket was
   the low half of a mantissa. **3D-ICE's network Tflp output has never worked** in this
   version. Every other branch in that file already declared a `float` local first.
3. **Mine: the power queue phase offset.** 3D-ICE queues powers — the `.flp` pre-loads one entry,
   `insert_power_values` pushes on the back, `update_source_vector` pops the front. Without a
   priming solve, every solve returned the *previous* insert's temperatures. My original
   end-to-end test fed nearly-identical powers each iteration, so a one-step lag was
   indistinguishable from correct: **it could only pass.** Fixed with a priming solve in
   `start()`; pinned by a test that swings power ×1 → ×2 → ×0.5 → ×1.

All C fixes are in `MXL_3DICE_fixes/` (six files) — `3d-ice/` itself is gitignored, so run
`./MXL_3DICE_fixes/apply.sh` after any fresh `get_and_patch_3DICE.sh`.

### Is the session safe to share across a sweep?

Yes, and it is enforced rather than assumed. `matrix_fingerprint()` hashes everything the
system matrix is built from — the `.stk` with quoted paths blanked, plus `.flp` geometry,
**excluding `power values`**. Power and MR-target sweeps reuse the session; changing airflow,
sink, or floorplan rebuilds it. `check_matrix_unchanged()` runs before every solve and **fails
closed**.

---

## GPU / cuDSS — decision: NOT NOW

Recommend **deferring**. The measurement that decides it:

| | 34-core | 128-core |
|---|---|---|
| MR point today (persistent) | ~2 min | ~14 min |
| with cuDSS (~10× on factorisation) | ~0.5 min | ~4 min |

Persistence already delivered ~150×; cuDSS adds ~3.5× on top for **1–3 days of CUDA work**. At
2 min/point the bottleneck has moved from compute to deciding what to run and interpreting it.
The integration itself is genuinely small — two functions (`do_factorization`,
`solve_sparse_linear_system`), four call sites, `SymmetricMode = YES` already set so cuDSS could
use Cholesky — so this stays cheap to pick up later.

**Revisit when** routine 128-core-and-larger studies become the norm; CPU factorisation scales
as N^1.67 and that is where the GPU wins most.

**numba is the wrong tool here** — the factorisation is inside 3D-ICE's C code. If a Python
route is ever wanted, the better path is a small matrix-dump patch plus `scipy.sparse.linalg.splu`
or cuDSS Python bindings, not hand-written kernels.

---

## Open questions the overnight study addresses

1. **Where exactly does MR stop rescuing?** (Phase 1, densities 1.10–1.16)
2. **Does a lower target push that cliff out?** (Phase 2.) Blocks above 92 °C carry only ~10% of
   die power while 65% sits 10–20 K below it — so coverage, not spot size, is the suspected
   limit.
3. **What pixel pitch does a real tile array need?** (Phase 3, 1/10/100 µm × dilute/exclude/ideal.)
   Analytic answer already in `examples/tile_array_tradeoff.py`: the knee is 25→10 µm, and 1 µm
   costs 96× the pixels for 1 percentage point of coverage.
4. **Does the MR benefit hold as core count scales?** (Phase 4, 70- and 128-core plus airflow.)

## Still open beyond tonight

* **Transient / predictive pre-cooling.** `core_other_0` (454 µm, the block that drives every
  runaway) has τ ≈ 2.2 ms against a 0.2 ms trace step — 11× slower, so there is real lag to
  exploit. The trace has **16 timesteps and we use one**. Needs time-varying MR plans and a
  lookahead controller; the persistent session is the prerequisite and is now done.
* **The MR selection policy is temperature-thresholded**, which is right for protecting the
  clock and wrong for arresting a runaway (leakage is an aggregate over the whole die). A
  policy ranking blocks by leakage contribution would select differently.
* **f_max derate slope is uncalibrated** — absolute GFLOP/s inherit that. Ratios are far more
  robust than absolutes.
* **α/β are digitised** except the 100 CFM point, which is pinned exactly against
  `docs/SimScale/data/tT0.dat`.
* Report the two FMU bugs and the `inspection_point.c` bug upstream to Tufts.

## Uncommitted

`git status` will show the session work (`ice_server.py`, its tests, `MXL_3DICE_fixes/`,
`overnight_study.sh`, `summarise_overnight.py`, raised `max_iter`, `--spot-policy`). The last
commit was `40391d9`; remote is `git@github.com:jbalma/MXL-HotGauge.git` over SSH.
