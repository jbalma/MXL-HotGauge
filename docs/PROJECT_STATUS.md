# Project status & next steps

*Last updated: 2026-08-11. Maintained as the handoff document between Claude sessions and
collaborators. Update it when a milestone lands.*

## Mission

Extend HotGauge to answer: **what do chip architectures gain from integrated photonic
(laser) microrefrigeration?** Four goals (from the original project_goals):

1. **Power/perf/temperature coupling** — model temperature-dependent static power and the
   power↔temperature feedback the stock pipeline lacks. **[Goal 1a DONE — see below]**
2. **ISA support** — understand x86 lock-in; path to RISC-V. *(Parallel track; the 2026
   snipersim fork in-tree already has `riscv/`, `README.riscv`, `riscv.cfg` — lock-in is now
   a configuration problem, not a missing capability.)*
3. **Microrefrigeration coupling** — feed the reduced-order MR model's per-block cooling
   into HotGauge as **negative power sources** per functional unit (decided approach) and
   evaluate performance/power impact + cooling efficiency (laser COP × LPC × pump).
4. **Floorplanning toolset** — architecture sweeps (density, clocks, layout) under
   fine-grain cooling.

Deep analysis of all four: `docs/HotGauge_gap_analysis_and_extension_design.md`.

## Leakage above 400 K + hybrid optimiser — 2026-08-12 (in progress)

### McPAT cannot go above 400 K, so the clamp had to be replaced by extrapolation

The ceiling is a hard input validation, not a solver failure. McPAT says so directly::

    410 Temperature must be between 300 and 400 Kelvin and multiple of 10.

Its device tables are populated only at 10 K steps over 300-400 K, so measuring hotter would
mean inventing device data. **The clamp was the real problem, not the missing measurement**:
holding leakage constant above the table removes the feedback term that produces runaway, so a
thermally divergent configuration silently "converged". Any monotonic continuation fixes that.

`LeakageModel.from_table_extrapolated` interpolates the measured curve and continues above the
top point with a subthreshold Arrhenius tail matched for continuity (fitted Ea = 0.799 eV from
the 380-400 K data; 36.099x at 400 K -> 36.102x just above). `load_calibrated_leakage_model`
uses it by default and warns once when a run enters the extrapolated region.

**The extrapolated region is genuinely uncertain**: an Arrhenius fit and a local-exponential
continuation of the same measured points disagree by **~2.5x at 450 K**. Use it to decide
*whether* a configuration diverges, not by how much. That is still a large improvement over a
clamp that answered "never diverges".

Immediate payoff: the first hybrid-optimiser run at 26 W with the whole budget on the fan
reported `core_other_0 reached 1198 K -> localized runaway`. Under the old clamp that point
would have been reported as converged.

### Hybrid optimiser

`examples/hybrid_cooling_optimizer.py` sweeps the P_fan : P_MR split of a fixed cooling budget
and reports both objectives: **A** maximum GFLOP/s, and **B** maximum GFLOP/s per total watt
(with GFLOP/s per chip-W and per cooling-W broken out). Fan power buys R_th through the
FMU-calibrated `PumpedSink`; MR power buys clipping heat through the spreadsheet-exact
accounting, net of LPC recovery.

**Operating-point calibration matters more than expected.** The optimiser uses the *measured*
HS483 fan, which delivers R_th 0.63-0.86 K/W -- a modest desktop cooler, not the 0.3 K/W
assumed in the cliff study. At 26 W every split diverges: that cooler simply cannot hold this
die. A viability probe at R_th 0.66 K/W puts the limit at **21 W** (92.3 C) with divergence by
26 W:

| P_in | peak C | f GHz | note |
|---|---|---|---|
| 12 W | 63.4 | 4.146 | |
| 15 W | 71.8 | 4.113 | |
| 18 W | 80.8 | 4.077 | |
| 21 W | 92.3 | 4.031 | at the MR target temperature |
| 26 W | — | — | diverges |

So the hybrid sweep runs at **23 W**, where MR engages but the part is still rescuable.

### RESULT: a genuine interior optimum — both corners are bad

23 W die, 8-core floorplan, FMU-calibrated fan, LPC recovery on:

**4 W cooling budget**

| P_fan | P_MR | R_th | peak C | f GHz | GFLOP/s | GFLOP/s/W | |
|---|---|---|---|---|---|---|---|
| 3.98 | 0.00 | 0.629 | 112.3 | 2.980 | 763.0 | 22.77 | throttled |
| 2.99 | 1.00 | 0.642 | 102.4 | 3.803 | 973.5 | 31.55 | throttled |
| **2.00** | **2.00** | **0.665** | **95.2** | **4.019** | **1029.0** | **36.38** | **OPTIMUM, not throttled** |
| 1.00 | 3.00 | 0.733 | 103.3 | 3.726 | 953.8 | 31.06 | throttled |
| 0.00 | 4.00 | 0.860 | 203.4 | 1.076 | 275.4 | 1.60 | collapse |

**2 W cooling budget**

| P_fan | P_MR | peak C | f GHz | GFLOP/s | GFLOP/s/W | |
|---|---|---|---|---|---|---|
| 2.00 | 0.00 | 130.1 | 1.542 | 394.7 | 10.07 | throttled |
| **1.50** | **0.50** | **125.0** | **1.953** | **500.0** | **13.66** | **OPTIMUM** |
| 1.00 | 1.00 | 135.7 | 1.157 | 296.2 | 6.73 | worse than all-fan |
| 0.00 | >=1.5 | — | — | — | — | diverges |

**1 W budget**: every split diverges. Below ~2 W of cooling this die is not viable at 23 W
regardless of how the budget is spent.

Three things worth stating plainly:

1. **Both extremes lose.** All-fan is throttled; all-MR is catastrophic (203 C at 4 W) because
   MR moves heat *within* the die but the heat still has to leave the package. The optimum is
   interior, which is precisely what the diminishing-fan-returns-vs-linear-MR-cost shape
   predicted before any of this was run.
2. **The winning split has WORSE bulk cooling.** At 4 W the optimum runs R_th 0.665 against the
   all-fan point's 0.629 — a strictly weaker heat sink and a strictly faster chip (4.019 vs
   2.980 GHz), because the watts moved to where the clock is actually set.
3. **The optimum shifts with budget**: 75:25 at 2 W, 50:50 at 4 W. Once bulk cooling is
   adequate, marginal watts are worth more on the hotspot. Both objectives (max GFLOP/s and max
   GFLOP/s per total watt) select the same split at both budgets here.

Caveat on the rows above 126.85 C (the McPAT ceiling): those use extrapolated leakage and are
directional. The 4 W optimum at 95.2 C is comfortably inside the measured range; the entire
2 W table is not.

### ⚠ The fan POWER model is still uncalibrated

`R_ext(u)` is measured against the FMU, but `p_static`/`p_scale`/`n`/`r` -- what a watt of fan
actually buys -- remain placeholders. **The optimal split depends directly on that**, so any
split the optimiser reports is provisional until real fan curves (W vs RPM or CFM) replace
them. The qualitative shape (diminishing fan returns against roughly linear MR cost, hence an
interior optimum) does not depend on the constants; the crossover point does. The optimiser
prints this warning on every run.

## 8-core floorplan + re-run cliff study — 2026-08-12

### The floorplan was the only 7-core thing in the pipeline

`mcpat_to_flp_name` extracts the core index from the label, `split_L3_power` and
`prepare_dice_trace` take `num_cores`, and `make_processor` is a general tiler. The "7" came
from one line: `make_processor(core_flp, 3, 3, {(1,0):'IMC', (1,2):'SoC'})` — a 3x3 tiling with
two slots given to IMC/SoC. **No trace-side change was needed for arbitrary core count.**

`examples/generate_ncore_floorplans.py` generalises it: a processor needs `n_cores + 2` slots,
and it picks the squarest exact factorisation. Asked for 7 cores it reproduces the shipped
3x3 layout exactly — a good check that the generalisation is faithful. Generated and validated
at 7nm: 2 (2x2), 4 (2x3), 6 (2x4), 8 (2x5), 10 (3x4), 16 (3x6) cores. Counts where `n+2` is
prime (5, 9, 11) are rejected with the nearest workable alternatives rather than emitting a
1xN sliver.

**The 8-core floorplan recovers 100 % of the discarded power**: simulated power
17.776 -> 19.841 W, dropped leaf power 2.064 -> **0.000 W**. Peak/die-average concentration
rises to **119.5x** (from 97x) because the die is larger while the hot block is not.

Two pre-existing bugs fixed on the way: `floorplans.py` could not be imported *or* run —
`mcpat_to_flp_name` requires a `CoreN/` prefix and two call sites passed bare names, which is
why the outputs had to be pre-generated with an older HotGauge.

**Guard added:** the generator refuses to overwrite existing floorplans without `--force`.
Regenerating the shipped 7-core with current HotGauge yields **235 blocks where the shipped
file has 228** — an accidental overwrite (which happened once, and was restored from git)
would silently invalidate every result computed against the original.

### Cliff study re-run on 8 cores — the finding survives the correction

R_th 0.3 K/W, target 92 C, measured leakage, LPC recovery on:

| P_in | case | peak C | P_tot W | f GHz | GFLOP/s | GFLOP/s/W | |
|---|---|---|---|---|---|---|---|
| 23 W | base | 87.0 | 23.4 | 4.052 | 1037 | 44.36 | not throttling |
| 23 W | MR | 87.0 | 23.4 | 4.052 | 1037 | 44.36 | **inactive** — nothing above target |
| 26 W | base | 108.3 | 30.4 | 3.311 | 848 | 27.84 | THROTTLED |
| 26 W | **MR** | **100.4** | **29.0** | **3.965** | **1015** | **35.05** | **WINS +7.21 (+25.9 %)** |
| 29 W | base | 437.2 | 250.3 | 0.795 | 204 | 0.81 | non-viable (clamped) |
| 29 W | MR | 131.3 | 57.9 | 1.448 | 371 | 6.40 | rescued 437 -> 131 C, still throttled |
| 32 W | base / MR | 479.2 / 469.3 | 276.1 / 299.4 | 0.745 / 0.757 | 191 / 194 | 0.69 / 0.65 | MR **loses** |

**The cliff moved from 21–23 W to 23–26 W** (+13 %), exactly as the recovered power predicts.
Note 26 W on 8-core reaches 108.3 C where 23 W on 7-core reached 108.9 C — the same thermal
state now takes ~13 % more power.

**The headline result is unchanged in mechanism and magnitude**: removing 0.218 W from 13
blocks, costing 0.4 W net after LPC recovery, clears the throttle and lifts throughput ~20 %
while *lowering* total power 30.4 -> 29.0 W. On 7 cores that was +28.8 %; on 8 cores it is
+25.9 %. The 10 % power correction shifted where the cliff sits, not whether clipping pays.

Past the cliff MR degrades gracefully rather than failing sharply. At **29 W** it pulls a
non-viable 437.2 C down to 131.3 C — removing 11.8 W across all 268 blocks for 20.5 W net —
but the part is still throttled at 1.45 GHz, so this is a rescue, not a win worth quoting: the
baseline is past McPAT's validity ceiling and clamped, so the +5.59 GFLOP/s/W is measured
against an unquotable number. At **32 W** it loses outright (-0.04), drawing 30.7 W net for
essentially no frequency gain.

Both are MR used as a *bulk* cooler (268 blocks, 20-31 W net) rather than a clipper (13 blocks,
0.4 W net at 26 W) — a ~75x difference in cost for a fraction of the benefit. That contrast is
the clearest statement of the regime boundary the whole model predicts: value is confined to a
narrow band around the throttle threshold, and outside it the envelope is simply the wrong
tool.

## Heatsink FMU: FIXED (2026-08-12) — four stacked bugs

`examples/fmu_acceptance_test.py` now **PASSES** both criteria on phonon:

```
fan    0 RPM: final 46.26 C | increment ratio 0.4492  decaying -> asymptote
fan 6000 RPM: final 45.89 C | increment ratio 0.3510  decaying -> asymptote
  1. constant power asymptotes : PASS
  2. more fan -> cooler        : PASS   (-0.37 K at 6000 RPM vs fan off)
```

**Rebuilding the FMUs alone did not help.** Four independent defects were stacked, each
masking the next; the diagnosis needed instrumenting the loader to print what it actually read.

**1. `spreaderX0`/`spreaderY0` never reached the loader** (`common/HeatsinkBlocks.mo`).
Declared `parameter ... (fixed = false)` and assigned in an `initial algorithm`. OpenModelica
1.27 does not write such a parameter into the slot `fmi2GetReal` reads, so 3D-ICE got
uninitialized memory — measured **`spreaderX0 = -9.09e+11 um`** instead of 15000. The spreader
grid landed ~10^12 um outside the sink, **all 360,000 grid-overlap cells were empty**, the
plugin returned zero heat flow, and the sink rejected nothing at any fan speed. Fixed with
binding equations (`= ParseX0(args)`) — exactly what `sinkLength` and friends have, which is
why they read correctly all along.

**2. Same bug for `constantFanSpeed`/`constantAirTemperature`** (`heatsinks/HS483/HS483.mo`).
The model printed correct values from its initial algorithm while the equations
`sink.fanSpeed = ...` read stale ones. Fixed the same way.

**3. `initialTemperature` could not be set at all.** Being `fixed = false`, OMC exported it as
`causality="calculatedParameter"` — and **FMI forbids `fmi2SetReal` on those**, so 3D-ICE's
call was silently ignored and the sink ran at the model default 288.15 K (15 °C), pinning the
die *below* ambient. Fixed by giving it a default (making it `causality="parameter"`) and
binding the sink's copy by modifier.

**4. The plugin was always initialised with `StepTime = 0`**
(`bison/stack_description_parser.y`). The grammar is
`SOLVER ':' TRANSIENT STEP ... ';' INITIAL_CONDITIONS { ...StepTime = $5... }`, and
`initialize_pluggable_heatsink` was called from inside `INITIAL_CONDITIONS`, which reduces
**before** the enclosing action assigns `StepTime`. The FMU was stepped with `dt = 0` forever:
measured `[step] t=0 dt=0 meanSinkT=303.15` at every step, sink frozen while 15.7 W flowed in.
Moved the call to the end of the steady/transient solver actions. Needs the parser regenerated
(bison 3.8.2 present) and 3D-ICE rebuilt.

### Where these bugs came from: two were introduced by the shipped patches

Checked against the Tufts README patching steps. **Both relevant patches are applied to our
tree, and neither fixes any of the four bugs — two of them created bugs:**

| bug | origin |
|---|---|
| 3. `initialTemperature` unsettable | **introduced by `RHEL9_patches/3dice_rhel9_delta.patch`** |
| 4. plugin init with `StepTime = 0` | **introduced by `HotGauge.3D-ICE.ThermalInit.patch`** |
| 1. `spreaderX0`/`spreaderY0` | original 2021 upstream, broken by OpenModelica 1.27 |
| 2. `constantFanSpeed`/`constantAirTemperature` | original 2021 upstream, same |

The RHEL9 delta (dated 2025-07-31) rewrote a plain settable parameter into a
`calculatedParameter`:

```diff
-      parameter Modelica.SIunits.Temperature initialTemperature "Initial simulation temperature [K] ...";
+      parameter Modelica.SIunits.Temperature initialTemperature(fixed=false) "Initial simulation temperature [K] ...";
```

FMI forbids `fmi2SetReal` on a calculatedParameter, so from that patch onward 3D-ICE could no
longer set the heatsink's initial temperature at all.

The ThermalInit patch refactored the transient production, replacing the inline initial
temperature with a separate `INITIAL_CONDITIONS` nonterminal and putting the
`initialize_pluggable_heatsink` call inside it:

```diff
         TRANSIENT STEP DVALUE ',' SLOT DVALUE ';'
-        INITIAL_ TEMPERATURE DVALUE ';'            // $12 Initial temperature
+        INITIAL_CONDITIONS
```

`INITIAL_CONDITIONS` reduces **before** the enclosing action assigns `StepTime`, so the plugin
has been initialised with `StepTime = 0` for every transient pluggable-sink run since. The
patch's own comment — *"Cannot be done before as we need the step time"* — states the exact
requirement the refactor violates.

**Practical consequence: re-running the README patch steps on a clean checkout reintroduces
bugs 3 and 4.** Our fixes live on top of the patched tree, so do not re-apply the patches over
them. Worth reporting upstream — bug 4 in particular silently affects every transient
pluggable-heatsink simulation.

### Timestep: the co-simulation needs dt <= 0.01 s

With a working plugin the explicit coupling diverges at dt = 0.05 s (alternating-sign blow-up
to ~1e57). At **dt <= 0.01 s it is stable and step-independent** (0.01 / 0.002 / 0.001 all give
42.96 °C), matching the vendor example's 0.01 s. Cost ~0.24 s wall per step on this grid, so
~8 min per 20 s simulated. The earlier apparent "stability" at 0.05 s was meaningless — the
sink was inert.

**Files changed** (git-ignored `3d-ice/` tree; originals in
`/mnt/nfs01/scratch/jbalma/mxl-backups/`): `common/HeatsinkBlocks.mo`,
`heatsinks/HS483/HS483.mo`, `bison/stack_description_parser.y`,
`loaders/FMI/fmiwrapper.cpp` (kept a one-shot `[diag]` print of the geometry the loader reads).

**Unblocks** fan/liquid studies, `PumpedSink` calibration against a real FMU, and the
P_fan : P_MR split. Caveats unchanged: the FMU is valid only below 40 W and 1500–6000 RPM, and
`skylake_HS483` still cannot be steady-solved, so FMU work means long transients.

## Real-leakage-split pipeline run — DONE (2026-08-11, node-06)

Steps 2–4 are complete; the feedback loop now runs on **real McPAT per-unit leakage**, not
synthetic. Reproduce with:

```bash
source setup_environment.sh          # single entry point, srun-safe
# Step 3 — McPAT conversion (48 runs: 3 tech nodes x 16 steps; ~1 min at -j 32)
cd scripts && ./14_perf_sims_to_7_10_14_power_sims.sh $(pwd)/../mcpat_runs 8 32 && cd ..
# Step 4 — leakage feedback on REAL leakage
python examples/leakage_feedback_smoketest.py --stack skylake_HS483 --plugin-args 6000 \
  --trace-dir mcpat_runs/7nm/linpack_3.8GHz
```

**Result (7nm, skylake_HS483 @ 6000 rpm, real splits from 16 files):**
`CONVERGED in 3 iters`, **787.96 → 751.47 W (−36.49 W, −4.63 %)**, hottest block RBB_0 at
89.5 °C, name-bridge coverage 80 % (expected — see below). Compare the synthetic-10 % run on
the same trace-independent path: −2.66 %. Real leakage roughly doubles the correction.

- **Step 2 did not need re-running**: a usable Sniper run from 2026-07-30 was already in
  `mcpat_runs/14nm/linpack_3.8GHz` — 16 timesteps (0.4–3.4 ms at 200 µs, matching
  `energystats:200000`), all XMLs well-formed. `sim.out` is empty (the run was cut short) but
  the McPAT input XMLs are complete. Backed up to
  `/mnt/nfs01/scratch/jbalma/mxl-backups/sniper_14nm_linpack_20260811/` because
  `run_mcpat.py` **deletes** `energystats-temp-*.{txt,py,cfg}` from the run dir on each
  invocation. Restore from there before re-running if you need the Sniper artifacts.
- **Real leakage fraction at 7nm is ~38.6 %** of total (24.44 W dynamic / 15.36 W leakage per
  step) — far above the synthetic 20 % that caused runaway earlier. It **still converges**
  because this workload peaks at 89.5 °C, below the McPAT T_ref, so leakage *falls* rather
  than compounding. Leak fraction alone does not predict runaway; the T vs. T_ref gap does.
- If re-running Step 2: `examples/linpack` reads a line from **stdin** and exits silently at
  EOF (`echo 200 | ...` works). The shipped example trace still cannot be regenerated.

## Goal 1a — done and validated

**The gap:** stock HotGauge computes leakage once (McPAT, at the XML's fixed reference
temperature — 330/360 K per core), sums it with dynamic power, and freezes it. No
temperature feedback, no thermal runaway, cooling's static-power savings invisible. The
authors left the hook as a TODO at `scripts/mcpat_to_blk_lvl_power_dict.py` (~line 241).

**What was built** (all tests: 27 passing):
- `HotGauge/power/leakage.py`: `LeakageModel` (exponential doubling-per-ΔT default;
  `subthreshold` physical form; `from_table` for McPAT-calibrated data),
  `rescale_total_power` / `rescale_trace`, and `converge_power_temperature` — fixed-point
  loop with under-relaxation (`relax`, default 0.5), power-growth guard (10× baseline),
  per-block max-temp guard (1000 K, names the offending block), temp floor (200 K; 3D-ICE
  reports 0 K for blocks outside the die layer), solver-failure→`diverged`, per-iteration
  `history`.
- `HotGauge/thermal/leakage_feedback.py`: `ICEThermalSolver` (one 3D-ICE transient per
  call, fresh `iter_NNN/` dirs, reads per-block Tflp temps in kelvin),
  `mcpat_flp_name_map` (McPAT↔floorplan names; aggregates → `None` → left frozen),
  `load_leakage_ref`/`find_split_files`, `run_leakage_feedback` entry point.

**Validated results on real 3D-ICE (phonon):**
- `skylake.stk`, synthetic 10% leakage: **CONVERGED in 3 iters, −2.66 % total power**
  (816.9 → 795.2 W) — blocks run below T_ref=360 K so temperature-aware leakage is lower
  than the frozen baseline. This is the static-power correction the stock pipeline cannot
  produce.
- Synthetic 20% leakage (both stacks): genuine electro-thermal **runaway at RBB_0**
  (hottest block, 105.5 °C = 18.5 K above T_ref → 2.3× leakage from iter 0; increments grow
  geometrically). Correctly detected and attributed by the guards/inspector. Under-relaxation
  cannot stabilize supercritical gain — reduce the gain (leak fraction, doubling, T_ref) or
  cool better.
- **Methodological finding that shapes Goal 3:** the smoke test's ~2–4 ms transients never
  thermally reach the heatsink (diffusion depth ~0.6 mm < die+TIM+spreader), so convection
  vs. HS483-FMU stacks gave *identical* die temperatures. **Cooling studies require
  steady-state solves (`ICESteadySim`) or long/warmed transients** (repo's production flow
  uses 5-minute warmups at 3 s slots — `HotGauge/thermal/thermal.py`).

## Steady-state solver mode — DONE (2026-08-11), with a hard constraint discovered

`ICEThermalSolver` now takes `mode='transient'|'steady'` (`--steady` on the smoke test).
Steady mode collapses the trace to one operating point (`collapse_trace_for_steady`,
`mean` or `max`), runs a single `ICESteadySim`, and broadcasts the equilibrium temperature
back across the trace (`broadcast_steady_temps`) so `rescale_trace`'s
length-must-match requirement is satisfied. No warmup is needed — equilibrium ignores the
initial condition — so the whole run is one solve instead of a soak plus N slots.

**Validated (7nm, plain `skylake` stack, real splits):** `CONVERGED in 3 iters`,
787.96 → 765.48 W (**−2.85 %**), peak 110.9 °C at RBB_0, ~60 s wall clock. Unlike every
transient run so far, blocks show a real spatial gradient (110.0 / 95.1 / 82.1 °C) and some
units' power *increases* (Core0 3.956 → 4.069 W) because they now sit **above** T_ref — the
first time the feedback has pushed leakage up rather than down.

### ⚠ 3D-ICE cannot do steady state with a pluggable heatsink

`emulate_steady` (`3d-ice/sources/thermal_data.c`) returns `TDICE_SOLVER_ERROR` immediately
for a pluggable top heatsink (`//TODO: support steady state pluggable sink`) — **and
`3D-ICE-Emulator.c` still writes its FINAL output afterwards, printing nothing to stderr.**
The Tflp file is well-formed and contains the untouched *initial temperature* for every
block. The feedback loop "converges" in 2 iterations on it. This bit us before it was
understood: an HS483 steady run reported a tidy `−4.87 %` with every block at exactly
40.0 °C (= the IC).

`assert_steady_supported()` now refuses this combination up front with a message naming the
cause. Covered by tests against the real shipped templates.

**This directly constrains Goal 3.** Cooling comparisons need steady state, but the FMU
heatsink stacks (`skylake_HS483`, `skylake_kryos`) are transient-only, and ms-scale
transients never diffuse past the die. So either:
- run cooling studies on the **plain `skylake` convection stack in steady mode** (works today,
  and negative-power MR injection is orthogonal to the heatsink model), or
- drive FMU stacks with **long transients to equilibrium** (the repo's production flow already
  does 5-minute warmups at 3 s slots — `HotGauge/thermal/thermal.py`), or
- patch 3D-ICE to implement that TODO.

The first option is the cheap path and is what the MR bridge should target first.

## Sink models + the cooling-dependent runaway boundary — 2026-08-11

`HotGauge/thermal/sink_models.py` makes the steady-solvable top boundary a parameterized
object (`ConstantHTCSink`, `ThermalResistanceSink`, `HS483AirSink`, `render_stack_with_sink`).
`ThermalResistanceSink` is the one that matters for **power-regime sweeps**: specify a cooler
in datasheet units (K/W) and study any power level without needing an FMU per cooling class.
Sinks self-report `UNCALIBRATED` and distinguish "no parasitic power" from "parasitic power
unmodelled", so an efficiency study cannot silently score an unmodelled fan as free.

**Headline result** — `examples/steady_sink_sweep.py`, 7nm 7-core die (28.39 mm²), real
McPAT leakage splits, leakage doubling per 15 K, T_ref 360 K:

| cooling (R_th) | 35 W (1.23 W/mm²) | 75 W (2.64 W/mm²) | 150 W (5.28 W/mm²) |
|---|---|---|---|
| desktop air, 1.0 K/W | 79.9 °C, −4.24 % | **runaway** (core_other_0) | runaway |
| high-end air, 0.3 K/W | 69.3 °C, −5.25 % | 131.8 °C, +3.34 % (did not converge in 15 it) | runaway |
| server liquid, 0.05 K/W | 65.7 °C, −5.50 % | 111.8 °C, −2.26 % | runaway |

At 75 W **the cooling solution alone decides whether the chip is thermally stable** — same
die, same workload, same leakage model. That stability boundary, not the few-percent static
power delta, is the strongest argument for targeted photonic cooling: holding one hot block
(`core_other_0` / `RBB_0`) below threshold converts an unstable configuration into a stable
one. Goal 3 should be evaluated against this boundary.

Caveats before quoting any of it: R_th values are assumptions, not products, and the runaway
threshold is sensitive to the leakage doubling constant and T_ref (sweep them). Diverged rows
print `--` deliberately: the last state before a runaway guard fires is not a solution.

**Correction (2026-08-11):** an earlier revision of this table dismissed 5.28 W/mm² as "far
above real datacenter density (~0.5–1.5 W/mm²)". That was wrong, and wrong in an instructive
way — it compared a die-average against die-average literature values. See the power-density
section below: 5.28 W/mm² is a *die-average* that sits inside the normal server-CPU/GPU local
band, and the peak functional-unit flux on this same floorplan is **512 W/mm²**. The 150 W
column is not "a die that cannot take that power"; it is a die whose hotspots are unmanageable
by bulk cooling — which is the case for microrefrigeration, not against it.

### ⚠ The HS483 heatsink FMU does not reject heat in this build

`examples/calibrate_sink_surrogate.py` was written to calibrate the lumped surrogate against
the real FMU. It could not, and the reason is a defect in the FMU path, established as follows:

- At constant 35 W the die temperature rises **perfectly linearly** (increments constant to
  4 decimal places, 124.1 K per slot, blowing past 1100 °C). A working sink must approach an
  asymptote; a straight line means heat is only filling thermal mass. Implied heat capacity
  (~20 J/K) matches the copper spreader + heatsink, so the assembly heats and rejects nothing.
- **Not a timestep artifact**: the trajectory is *identical* at 0.5, 0.1, 0.02 and 0.01 s
  steps. Expected sink time constant is ~13 s, so 600 s should have equilibrated many times over.
- **Not a configuration error**: the FMU echoes back `air temperature = 303.15`,
  `fanSpeed = 6000`; the plugin loads, runs (3.0 s), links `libpugixml`, and writes no stderr;
  spreader offsets match the geometry comments.
- The **vendor's own shipped example is also wrong**: `example.stk` names the FMU
  `HS483.HS483_P14752_...` while the built directory has no prefix (fails with "missing or
  wrong modelDescription.xml"); with the name fixed it runs but settles *below* ambient and
  does not respond to the fan turning on at t=100 s.

Most likely a bad FMU build (these were regenerated 2026-07-30; OpenModelica/MSL version
sensitivity is already a known trap — see CLAUDE.md). **Until the FMUs are rebuilt and
validated, no FMU-derived number is trustworthy**, which is why the sweep above uses
`ThermalResistanceSink` instead. `HS483AirSink.area_ratio` stays uncalibrated.

The calibration harness now detects this signature directly and says "SINK IS REJECTING NO
HEAT ... running longer will NOT help" rather than the generic not-at-equilibrium warning.

## HEADLINE: MR at the throttle cliff — corrected numbers (2026-08-11)

Corrected power accounting, measured McPAT leakage, L3 bridge on, LPC recovery at the
go-forward assumptions (eta_laser 0.70 / eta_LPC 0.90 / eta_ASF 0.20), R_th 0.3 K/W,
MR target 92 °C. **Power labels are now true die power** (see corrections below):

| P_in | case | peak °C | P_cmp W | P_tot W | f GHz | GFLOP/s | GFLOP/s/W |
|---|---|---|---|---|---|---|---|
| 21 W | base | 89.2 | 21.6 | 21.6 | 4.043 | 1035 | 47.84 |
| 21 W | MR | 89.2 | 21.6 | 21.6 | 4.043 | 1035 | 47.84 *(inactive)* |
| 23 W | base | 108.9 | 28.1 | 28.1 | 3.261 *throttled* | 835 | 29.72 |
| 23 W | **MR** | **100.9** | **25.9** | **26.2** | **3.922** | **1004** | **38.29** |
| 25 W | base | 442.5 | 211.3 | 211.3 | 0.789 | 202 | 0.96 *(non-viable)* |

**The 23 W row.** MR removes **0.185 W** from 13 blocks. Gross draw 1.3 W, 1.0 W recovered by
the LPC, **0.3 W net**. That buys:

- peak 108.9 -> 100.9 °C, clearing enough of the throttle to take **f from 3.261 to 3.922 GHz (+20 %)**
- throughput 835 -> 1004 GFLOP/s
- **compute power *falls* 28.1 -> 25.9 W** — the 2.2 W leakage saving is **7.3x the 0.3 W net
  MR cost**, so total system power drops 28.1 -> 26.2 W *while* performance rises
- efficiency **29.7 -> 38.3 GFLOP/s/W, +29 %**

**The cliff is sharp and MR sits exactly on it.** 21 W: nothing above target, MR correctly does
nothing (and costs nothing). 23 W: throttling, and MR converts it back to near-nominal. 25 W:
442 °C, outside McPAT's validity — beyond rescue by a 10 W/mm² envelope. The useful band is
roughly one throttle-threshold wide, which is precisely the thermal-clipping thesis.

Caveats: the MR loop hit `max_iter` (8) so the plan is not fully converged; the 25 W row is
clamped and not quotable; R_th, the f_max derate slope and eta_ASF remain uncalibrated
assumptions; and Core-7 (~10 % of leaf power) is still dropped.

## Resume here

**Compute keeps dying.** Four interactive allocations (1043, 1084, 1086, 1087) ended mid-run,
each killing an `srun` with exit 143. The 25 W MR row was lost to the latest one. Everything
above survived only because output is now written **unbuffered straight to a log** — piping
through `tail` buffers until exit and loses everything.

Use the batch driver instead; it is owned by the scheduler, not a terminal:

```bash
sbatch scripts/run_study.sbatch examples/mr_clipping_study.py \
    --powers 23 25 --r-th 0.3 --mr-target-C 92 --mr-iter 8 --out-dir $(pwd)/mr_cliff_v3
```

**136 tests passing**; all example scripts import and `--help` cleanly.

## Goal 3 — MR bridge built and wired (2026-08-11)## Goal 3 — MR bridge built and wired (2026-08-11)

`HotGauge/thermal/microrefrigeration.py` + `examples/mr_clipping_study.py`.

**Gating question answered: 3D-ICE accepts negative power sources.** Removing 0.5 W at
`cALU_0` in a 35 W steady solve gives −10.7 K there, cools neighbours (`RBB_0` −9.5 K,
`fpRF_0` −7.9 K) and leaves distant blocks alone (−0.4 K); peak fell 72.2 → 64.1 °C. Note the
leverage: **0.5 W of targeted removal beat what a 20× better bulk cooler achieved.**

Design points worth keeping:
- **Sensitivity is measured, never assumed.** Converting "20 K too hot" into watts needs
  dT/dq per block, and lateral spreading dominates it: the naive `R_die` estimate predicts
  153 K for 0.5 W at `cALU_0`; the measured response is 10.7 K, **15× smaller**. The loop
  secant-updates dT/dq each iteration.
- **The plan is always recomputed against the uncooled baseline.** An earlier version planned
  against already-cooled temperatures, so a first-iteration overshoot stood forever — it
  "converged" having removed 30 W where 7.5 W sufficed, silently 4×-ing the laser budget.
  Convergence now requires the plan to stop moving *and* the peak to sit at target.
- Envelope limits (`h_max`, `dt_max`, spot size, budget) each report **which limit bound**
  each block, so a weak result is traceable to a physical constraint.
- `mr_accounting` charges `Q_removed / COP` (10 W per W at COP 0.1) and deliberately does not
  net it against a benefit — the benefit must be demonstrated on GFLOP/s per *total* watt.

### LPC power recovery — and why net-generating operation is a regime, not an error

Implemented to match `docs/MXL-Photonic-Cooling-Power-Analysis.xlsx` exactly (regression-tested
against its MVP-1/2/3 cases to <1e-3 W):

```
P_laser     = Q / (eta_ASF * eta_laser)
P_removed   = eta_ASF * eta_laser * P_laser              ( = Q )
P_recovered = eta_LPC * collection * (1 + eta_ASF) * eta_laser * P_laser
P_used      = P_laser - P_recovered = (1 - breakeven_ratio) * P_laser

breakeven_ratio = eta_LPC * collection * (1 + eta_ASF) * eta_laser
```

The `(1 + eta_ASF)` term is the crux: the light reaching the LPC is the pump **plus** the heat
up-converted into it, so recoverable optical power exceeds what the laser emitted.

**`breakeven_ratio > 1` is a target regime, not a modelling error.** An earlier revision of
this module flagged `P_used <= 0` as "thermodynamically suspect" and warned on it. That was
wrong: the spreadsheet's own MVP-3 (eta 0.85 / 0.92 / 0.62) sits at ratio 1.267 with
`P_used = -50.7 W` on 190 W of laser — the loop returns more electrical power than it draws,
with extracted chip heat as the additional source. It is now reported plainly via
`net_generating` / `self_sustaining` flags. The only guard retained is the **first law**
(`P_recovered <= P_laser + Q`), which catches real bookkeeping bugs without editorialising
about which efficiency combinations are achievable — that judgement belongs to the device
model, not to this code.

**eta_ASF is OPTICAL, not electrical.** Heat removed per watt of *pump light*, so the
electrical COP is `eta_ASF * eta_laser`. At the go-forward assumptions **20 % ASF with 70 %
wall-plug is COP 0.14**, not 0.20 — conflating them overstates the cooler by `1/eta_laser`.

Go-forward assumptions (eta_laser 0.70, eta_LPC 0.90, eta_ASF 0.20):

| quantity | value |
|---|---|
| electrical COP (pre-recovery) | 0.140 |
| breakeven ratio | 0.756 |
| per 1 W removed | draw 7.14 W, recover 5.40 W, **net 1.74 W** |
| **effective COP (net)** | **0.574** |

Recovery takes the effective COP from 0.14 to 0.57 — a 4.1× improvement, so it dominates the
MR economics rather than adjusting them.

**The extractor is the binding constraint.** At eta_laser 0.70 and eta_LPC 0.90, breakeven
needs **eta_ASF >= 0.587**. The LPC is already close to its practical ceiling (the sheet's own
survey: 68.9 % demonstrated at 858 nm, ~80 % credible for GaAs); the ASF/extractor path from
0.20 to ~0.59 is where the leverage is, matching the sheet's MVP-1 -> MVP-3 progression
(Yb:YLF 0.10 -> Cr:LiSAF 0.33 -> semiconductor 0.62).

### Cross-validation of the power-density argument

The spreadsheet's own region table corroborates the functional-unit scale measured in
`examples/power_density_profile.py`:

| region | area mm² | power W | W/mm² |
|---|---|---|---|
| Full die | 484.0 | 400 | 0.83 |
| All cores | 46.24 | 320 | 6.9 |
| Single FU | **0.04** | **18** | **450** |

450 W/mm² at functional-unit scale against a 0.83 W/mm² die average — a **543× ratio**,
independently reproducing (and exceeding) the 97× measured on our 7nm floorplan, and from a
completely separate source. It also carries fan-power data (CFM and W vs chip power, with and
without laser, at dT=10 K and 50 K) that should replace `PumpedSink`'s placeholder
coefficients.

### The fan side: `PumpedSink`### The fan side: `PumpedSink`

`sink_models.PumpedSink` implements the MR notebook's own functional form so the hybrid
optimisation and the reduced-order model describe the same device:
`R_ext(u) = R_inf + (R0−R_inf)/(1+u^m)`, `p_pump(u) = p_static + p_scale·u^n·((1+u²)/2u)^r`,
both area-normalised. It reports its own power draw (`parasitic_known = True`), unlike a bare
`ThermalResistanceSink`. Tested property: **fan thermal returns diminish while fan power cost
accelerates** — which is precisely why an optimal P_fan : P_MR split exists rather than a
corner solution.

### Three accounting corrections (2026-08-11)

**1. Power labels were 2.36x optimistic.** The sweeps normalised a target die power by the raw
sum of McPAT entries. That sum is not die power, and neither is the raw `prepare_dice_trace`
sum: the renamer leaves the hierarchy aggregates (`Processor` 12.80 W, `Processor/Total Cores`
6.66 W, `NUCA`, `Processor/Total L3s`) in its output dict, and they are dropped **silently**
later because `populate_template` only substitutes placeholders the `.flp` actually contains.
Of 291 entries totalling 41.87 W, only **228 entries / 17.78 W** land on a real block. So a run
labelled "50 W" was really simulating ~21 W. `die_power_of_trace()` now counts only what lands
on a block, and `scale_trace_to_die_power()` normalises against that.

**2. Core-7 is silently discarded — 10.4 % of real power.** Separating genuine losses from the
harmless aggregate drops shows **2.064 W** of floorplan-shaped entries (`core_other_7` 0.735,
`FPUs_7` 0.509, `cALU_7` 0.345, `iALU_7` 0.184, `L3_7` 0.157 ...) with no matching block: the
shipped floorplan is **7-core** while the trace is **8-core**. `die_power_of_trace` now warns
whenever >1 % of leaf power has nowhere to go. Fixing this needs an 8-core floorplan (Goal 4),
not a code change.

**3. L3 leakage now participates in the feedback (+45 %).** `Processor/Total L3s` carries
**1.225 W of leakage** — 45 % more than the 2.709 W of everything else in the loop combined —
and its power *is* placed on the die (`split_L3_power` spreads it over `L3_0..L3_6`), so its
temperature is perfectly well defined. It was nonetheless frozen at T_ref because the name
bridge maps it to `None`. `augment_temps_with_aggregates()` + `aggregate_aware_name_map()` add
a synthetic `__agg__L3` temperature (mean of the L3 blocks) so the aggregate can be rescaled;
enable with `run_leakage_feedback(..., bridge_aggregates=True)`, which both sweep scripts now
do. **`NUCA` is deliberately NOT bridged** — it restates `Processor/Total L3s` (identical
dynamic and leakage in the split files), so bridging both would count the L3 twice.

Temperature-responsive leakage therefore goes from 2.709 W to ~3.95 W. Against 17.78 W of
simulated die power that is **~22 %**, up from ~15 %. Still not the whole chip — the remaining
frozen power is uncore with no floorplan representation — but the feedback now covers the
largest single addressable piece.

### Next: the two optimisation scenarios### Next: the two optimisation scenarios

Both are now expressible, and both need `P_MR` to be the **net** (post-LPC) figure:

1. **Max performance at fixed cooling budget** — maximise GFLOP/s subject to
   `P_fan(u) + P_MR_net ≤ budget`, sweeping the split. Tests whether static-power savings are
   better spent on fan or on hotspot clipping.
2. **Max compute efficiency** — `GFLOP/s / (P_chip + P_cool)`, with the two sub-objectives
   separated: `GFLOP/s / P_chip` (how far pre-cooling can drive static power toward zero) and
   `GFLOP/s / P_cool` (the P_fan : P_MR ratio at fixed performance, and where recovered LPC
   power is best spent).

### Results (CORRECTED accounting, 2026-08-11 late) — supersedes the table below

Re-run after three accounting fixes (die-power scaling, output-power double-count, L3 bridge).
Power labels here are **corrected**: old "55 W" == 23 W here. R_th 0.3 K/W, target 92 °C,
eta 0.70/0.90/0.20, LPC recovery on.

| P_in | case | peak °C | P_cmp W | P_tot W | f GHz | GFLOP/s | GFLOP/s/W | |
|---|---|---|---|---|---|---|---|---|
| 21 W | base | 89.2 | 21.6 | 21.6 | 4.043 | 1035 | 47.84 | not throttling |
| 21 W | MR | 89.2 | 21.6 | 21.6 | 4.043 | 1035 | 47.84 | **inactive** — nothing above target |
| 23 W | base | 108.9 | 28.1 | 28.1 | 3.261 | 835 | 29.72 | THROTTLED |
| 23 W | **MR** | **100.9** | 25.9 | **26.2** | **3.922** | **1004** | **38.29** | **WINS +8.56 (+28.8 %)** |
| 25 W | base | 442.5 | 211.3 | 211.3 | 0.789 | 202 | 0.96 | non-viable (clamped) |

**The 23 W row:** removing **0.185 W** from 13 blocks — **0.30 W net** after 1.0 W of LPC
recovery from 1.3 W gross — lifts the clock 3.261 -> 3.922 GHz (**+20 % throughput**) while
total power *falls* 28.1 -> 26.2 W. Efficiency improves **+28.8 %**. The leakage saving from
clipping (2.2 W) is over 7x the net MR cost, so MR pays for itself on static power alone
before any performance credit — the same ratio the pre-correction run showed, which is
reassuring: the fixes changed the magnitudes, not the mechanism.

Still to finish: the 25 W MR row (allocation died mid-run). The 23 W MR row also hit
`max_iter` and remains marginally throttled at 100.9 °C, so more iterations should improve it
further -- treat +28.8 % as a **lower bound**.

### Results: MR pays exactly where the theory says it should

Three operating regimes, all with LPC recovery and measured McPAT leakage
(R_th 0.3 K/W, target 92 °C, eta 0.70/0.90/0.20):

| P_in | case | peak °C | P_total W | f GHz | GFLOP/s | GFLOP/s/W | verdict |
|---|---|---|---|---|---|---|---|
| 50 W | base | 95.0 | 51.3 | 4.020 | 1029 | 20.04 | |
| 50 W | MR | 89.9 | 54.6 | 4.040 | 1034 | 18.96 | **loses** −1.09 |
| 55 W | base | 124.4 | 61.5 | 2.000 *throttled* | 512 | 8.32 | |
| 55 W | **MR** | **95.3** | **54.2** | **4.019** | **1029** | **18.99** | **WINS +10.67** |
| 65 W | base | 406.9 | 220.3 | 0.832 | 213 | 0.97 | *clamped* |
| 65 W | MR | 396.7 | 333.4 | 0.844 | 216 | 0.65 | loses −0.32 |

**The 55 W row is the result the whole toolchain was built to produce.** Removing **0.632 W**
from 25 blocks — **1.1 W net** after 3.4 W of LPC recovery from 4.5 W gross — pulls the peak
from 124.4 °C to 95.3 °C, clears the throttle point, and **doubles throughput** (512 →
1029 GFLOP/s). Total system power *falls* 61.5 → 54.2 W at the same time, because clipping the
hotspot cut die-wide leakage by 8.4 W: **the static-power saving alone repays the MR system
7.6x over**, before any performance credit.

The two losing rows are equally informative and were predicted:

- **50 W — nothing to buy back.** The chip is not thermally limited (95 °C, under the trip), so
  MR spends 4 W to gain 0.02 GHz. MR is worthless when the part is not throttling.
- **65 W — MR used as a bulk cooler.** Every block is over target so the clipper spreads across
  228 blocks; the configuration is also past McPAT's validity ceiling (clamped). The
  H <= 10 W/mm^2 envelope cannot absorb a ~150 W excess, and should not be asked to.

So the value is concentrated in a **narrow band around the throttle threshold** — which is
exactly the thermal-clipping thesis, now measured end to end rather than assumed.

**Caveats on these specific numbers.** (a) The MR loop hit `max_iter` in every row, so the
plans are not fully converged. (b) These runs predate the die-power correction, so the labels
use the old 2.36x-inflated convention — "55 W" is really ~23 W simulated; a rerun at corrected
labels (21/23/25 W) with the L3 bridge enabled is in flight. (c) The 65 W rows sit in the
clamped region and are not quotable. (d) R_th, the f_max derate slope and eta_ASF all remain
uncalibrated assumptions.

## Goal 1b + leakage calibration## Goal 1b + leakage calibration — DONE (2026-08-11)

### The T_ref bug: every earlier leakage result was 4× optimistic

`snipersim/tools/mcpat.py:859` hardcodes `<param name="temperature" value="330"/>` into every
generated McPAT XML, so **T_ref = 330 K** for our traces. `leakage.py` defaulted to
`DEFAULT_TREF_K = 360.0`, described as "conservative (higher T_ref → smaller predicted
savings)". It is conservative for the *savings* number and **anti-conservative for stability**:
using 360 K instead of 330 K divides modelled leakage by `2^(30/15) = 4` at *every*
temperature, so it under-predicts leakage and therefore under-predicts thermal runaway. At
110 °C the true multiplier is 11.7×, not 2.9×.

`mcpat_tref_from_trace_dir()` now reads the anchor out of the trace's own XML. **Never pass a
literal T_ref again** — the shipped example trace has no XML, so there the fallback must be
stated explicitly rather than assumed.

### McPAT's measured leakage curve is NOT a single exponential

`examples/calibrate_leakage_model.py` re-runs McPAT across temperature (anchor 330 K = 1.0):

| T [K] | 310 | 330 | 350 | 360 | 370 | 380 | 390 | 400 |
|---|---|---|---|---|---|---|---|---|
| measured | 0.92 | 1.00 | 1.60 | 3.15 | 6.04 | 9.59 | 16.16 | **36.10** |
| `exp(ΔT₂ₓ=15)` | 0.40 | 1.00 | 2.52 | 4.00 | 6.35 | 10.08 | 16.00 | 25.40 |

The **local** doubling constant runs from ~180 K between 310–330 K down to **~8.6 K** between
390–400 K — a 20× swing. A log-linear fit returns ΔT₂ₓ = 16.4 K with a max residual of 13.7 in
relative units, i.e. the exponential shorthand is indefensible here. Use
`LeakageModel.from_table` via `load_calibrated_leakage_model()`.

**The physics that matters commercially:** leakage is nearly flat below ~340 K (67 °C) and
explodes above ~350 K (77 °C). Uniformly cooling an already-cool chip buys almost no static
power. Clipping a hotspot that sits above ~77 °C buys a great deal. This is the *measured*
quantitative case for targeted cooling over bulk cooling — previously an assumption.

Also: gate leakage is temperature-independent in McPAT (constant 0.0183 W); all of the
temperature dependence is subthreshold.

### ⚠ McPAT validity ceiling: 410 K (137 °C)

At 410 K McPAT prints its banner and stops — no results, no error, exit code 0. The
calibration detects this and reports the ceiling instead of crashing. **Any simulated operating
point above ~127 °C is outside the power model entirely** and must be reported as "thermally
non-viable", never as a quantified result. `LeakageModel.from_table` now warns **once**,
loudly, when it clamps — clamping freezes leakage growth, which suppresses runaway and can make
a divergent configuration look convergent (this happened before the warning was added).

### Goal 1b: temperature → performance

`HotGauge/power/performance_model.py` — `FMaxModel` (linear guardband derate or measured
`from_table`), `core_fmax` (**the hottest block sets the core clock**, not the mean — that
asymmetry is why targeted cooling beats bulk cooling), `throttled_fmax` (hard cliff above the
trip point), `voltage_for_frequency`/`dynamic_power_scale` (V²f, so recovered clock is not
free), and `performance_summary` (perf and perf/W). All constants are declared assumptions;
every result carries `calibrated=False` so a downstream efficiency claim cannot silently
inherit a guessed slope.

### Headline: the viability cliff, and how little bulk cooling buys

`steady_sink_sweep.py` with the measured leakage curve, correct T_ref, and the performance model:

| cooling (R_th) | 35 W | 50 W | 65 W |
|---|---|---|---|
| desktop air, 1.0 K/W | 85.1 °C, 4.06 GHz | non-viable | non-viable |
| high-end air, 0.3 K/W | 72.4 °C, 4.11 GHz | 95.0 °C, 4.02 GHz | non-viable |
| server liquid, 0.05 K/W | 68.3 °C, 4.13 GHz | 86.0 °C, 4.06 GHz | non-viable |

Two things to take from it:

1. **It is a cliff, not a slope.** High-end air goes from 95 °C / 4.02 GHz at 50 W to
   thermally non-viable at 65 W. That is the electrothermal runaway knee, now driven by
   measured leakage rather than a guessed exponential.
2. **A 20× better bulk cooler buys ~35% more power.** Going from 1.0 to 0.05 K/W moves the
   cliff from roughly 40 W to roughly 55 W. Bulk R_th barely touches the local spreading
   resistance that actually sets hotspot temperature — consistent with the 512 W/mm² peak at
   `RBB_0`. This is the quantitative case that bulk cooling is the wrong lever, and it comes
   out of our own pipeline rather than a slide.

## Power density: always state the coarse-graining — 2026-08-11

**Rule for this project: "power density" is meaningless without a length scale.** The spatial
ladder (`docs/Microrefrigeration_v1.pdf`) spans five orders of magnitude:

```
rack 0.01  ->  server 0.1  ->  processor 1.0  ->  core 10  ->  hot spot 100    [W/mm^2]
```

Literature and datasheets almost always quote the **die average** (a 300–800 mm² part at
300–700 W reads as ~1 W/mm²), which makes a chip look benign while the local flux that sets
the thermal limit is 1–2 orders of magnitude higher. The MR paper's *local* flux table:
server CPU **1–8**, GPU/AI accelerator **1–10**, chiplet/2.5D HPC **2–15**, RF/GaN/SiC
**20–300+** W/mm². "Conventional cooling fails above 1 W/mm²."

`examples/power_density_profile.py` measures this on our own floorplan (7nm 7-core,
28.39 mm², real McPAT trace scaled to 150 W):

| coarse-graining | W/mm² |
|---|---|
| die average (what gets quoted) | 5.28 |
| block median | 0.76 |
| block p90 / p99 | 17.0 / 82.8 |
| **block peak (`RBB_0`)** | **512.6** |

**Peak is 97× the die average**, and lands on the "hot spot" rung. `RBB_0` carries 0.98 W in
0.0019 mm² (13.4 µm minimum dimension). Note this is the *same block* that runs away in the
leakage-feedback sweeps — the electrothermal instability is located exactly where the local
flux is highest, which is a good consistency check on the whole pipeline.

Consequences already visible for Goal 3 (at 150 W):
- **34 of 217** units exceed the MR cooling-density ceiling (H ~1–10 W/mm²). MR clips the
  temperature *excess* rather than the full heat load, so this bounds how much excess it can
  absorb — it does not make MR useless there.
- **147 of 217** units are narrower than MR's ~100 µm spatial targeting limit, so most units
  cannot be addressed individually; a spot cools a *neighbourhood*. Floorplanning (Goal 4)
  therefore interacts directly with MR effectiveness.

## The MR model (`docs/chip_microrefrigeration_stable_v1.ipynb`) — how it couples to HotGauge

Reduced-order and **area-normalized**: thermal resistances are R-area products in K·mm²/W, so
`R_th_local = R_area / A_block` — the same area-referencing convention as
`sink_models.ThermalResistanceSink`. The two compose directly.

It already models the hybrid: `R_ext(u) = R_inf + (R0 - R_inf)/(1 + u^m)` is bulk cooling as a
function of pump/fan setting `u`, with `p_pump(u)` its power cost, plus `COP_micro` for the MR
stage. `BUParams` carries the V/f/power/leakage model (`Q_dyn0`, `Q_leak0`, `alpha_leak0`,
`Vth`, ...) — i.e. the performance side of Goal 1b.

**The bridge to build:** the notebook's defaults assume `alpha_tot = 0.05` (hotspot power
fraction) and `beta = 0.01` (hotspot area fraction), i.e. a hotspot only ~5× die average.
Our measured floorplan is ~97×. So HotGauge should *supply* measured (`alpha_tot`, `beta`,
`beta_spot`, and the q distribution) per architecture and workload instead of the defaults —
that is exactly the HotGauge→MR coupling, and it makes the MR projections architecture- and
workload-specific rather than generic.

## Timescales — both regimes matter, for different questions

- **Advanced hotspots are fast**: HotGauge's case study sees the first hotspot at **0.2 ms**,
  with units above 120 °C while neighbours 200 µm away are 30 K cooler. MR targets ≲100 µm and
  ≲ ms — the *same* regime.
- **Bulk sinks are slow** (~10 s time constants). This is why ms transients show no heatsink
  sensitivity — and why that earlier finding does **not** mean "cooling studies need steady
  state, full stop". It means: steady state for bulk-cooling/system-COP comparisons, ms
  transients for hotspot dynamics and MR clipping. The bulk sink is quasi-static boundary
  condition on MR timescales, which is a simplification in our favour.

## Roadmap (after the real-split run)

0. **Rebuild + validate the heatsink FMUs** (blocks all fan/liquid/hybrid work). Acceptance
   test: constant power must produce an asymptote, and raising fan RPM must lower temperature.
1. ~~**Steady-state solver mode**~~ — done, see above.
2. **Leakage calibration**: re-run McPAT at 2–3 XML temperatures → `LeakageModel.from_table`.
3. **Goal 3 — MR bridge**: per-block power density q → MR model (`chip_microrefrigeration_
   stable_v1.ipynb`, reduced-order, per-heat-flux) → required cooling power s, ΔT, COP →
   inject as negative power in the `.flp` (validate 3D-ICE accepts negative sources with a
   1-cell test first) → rerun feedback loop so static-power savings are counted → efficiency
   post-processor (laser COP × LPC × pump vs. compute savings).
4. **Goal 1b — T→performance model** (f_max(T)/guardband; V-F table is in
   `HotGauge/configuration/performance.py`) so cooling converts to performance numbers.
5. **Goal 4 — floorplanning**: overlap-checked placement + legalization on top of the
   existing slicing ops (`examples/floorplans.py` `replace`/`scale_units`); sweep density /
   clocks / cooling-budget allocation.
6. **Goal 2 — RISC-V**: scope against the in-tree snipersim RISC-V support; the McPAT-side
   x86 taxonomy (see gap analysis §2) is the remaining blocker.

## Facts a new session will otherwise rediscover the hard way

- Floorplan is **7-core** (`skylake7nm_7core_3`) but traces are **8-core** → Core-7 units
  have no floorplan block; name-bridge coverage 80 % is *expected*; those units stay frozen.
- McPAT reference temps in the XML template are **per-core (330 K or 360 K)** — pass the
  right `T_ref`; a wrong T_ref flips the sign of the leakage correction.
- Feedback iteration outputs live under `leakage_feedback_smoketest/<stack>/stage2/iter_*/`;
  diagnose with `python examples/inspect_feedback_iters.py <stage2 dir>` (classifies
  gradual-ratchet vs. solver-spike from the increment series).
- The smoke test auto-prefers real `block_powers_split_*.json` in `--trace-dir`; otherwise
  it synthesizes leakage (`--leak-fraction`) and says so.
- `load_block_powers` filters out `block_powers_split_*` companions — keep it that way.
- Pluggable stacks (`skylake_HS483`, `skylake_kryos`) need `--plugin-args` (e.g. `6000` fan
  rpm); plain `skylake` stack needs none and no FMU.
