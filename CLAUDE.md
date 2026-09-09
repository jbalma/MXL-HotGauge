# MXL-HotGauge — working context for Claude sessions

## `[!]` START HERE — the four organizing documents (3 Sep 2026)

This project has withdrawn a substantial fraction of its own results. **Read `docs/START_HERE.md`
first**; it routes to four files that supersede any older summary:

| file | for |
|---|---|
| **`docs/RESULTS_REGISTER.md`** | every number as **quotable / withdrawn / open**. Read before quoting anything. |
| **`docs/METHODS.md`** | how to drive the codebase; the trap list; what SPICE does and does not give you |
| **`docs/REFERENCES.md`** | the device physics (v91), the exergy/LPC bound the code implements, the architecture literature |
| **`docs/ARCHITECTURE_EVOLUTION.md`** | hot functional units, cold caches, and the honest gap list to a licensable core |

`[+]` **`results-quotable/` and `results-historical/`** at the repo root materialise register §1 and
§2 as directories — copied evidence plus a per-item `SOURCE.md` / `WHY_RETIRED.md`, with the big
solve trees symlinked. Build/verify: `python scripts/build_results_registers.py [--verify]`.
`[!]` Several historical items are **mixed** (a table whose clocks survive but whose mechanism does
not; a harvest file where one field carries a defect) — that is why they are filed as historical
rather than quotable.

`[!]` **The extractor platform is a thin film of GaAs OR SiN-encapsulated molecular dye**,
> 1000 W/mm², eta_ASF **0.10-0.60** (Draft_5 s3.5.4, across MVP stages; 0.32 is the working
point). **Yb:YLF is NOT the cold-zone material** and is not a zone
material at all — it is retained only so the pre-30-Aug catalogue reproduces. An earlier revision
of `microrefrigeration.py` and of the handbook said otherwise; both are corrected and tests refuse
any rare-earth name in `ZONE_EXTRACTORS`.

`[!]` **Two defaults moved 2-3 Sep**: `--rbb-policy` -> `amortized`, `--core-other-policy` ->
`hierarchy-consistent`. **`--mr-eta-asf` is unchanged at 0.32.** Reproduce the recorded catalogue
with `--rbb-policy stock --core-other-policy stock --mr-h-max 250`.

`[+]` **`eta_asf` moves every MR COST in proportion and no THERMAL result at all** (the planner
sizes removal from the thermal problem), so sweeping it across 0.10-0.60 bounds the cost claims
without touching a single rescue verdict or ceiling.

`[!]` **`MRParams.breakeven_ratio_at()` is v91 eq. (1.13)** — the refined exergy bound. The `1` is
the pump-derived part (work-like, fully recoverable); the `eta_ASF * phi` is the heat-derived part,
Carnot-discounted. We apply the many-mode Carnot limit while the device engineers fluorescence
*away* from it, so **every recovered-power figure is a lower bound**.

Maxwell Labs fork of the Tufts **HotGauge** framework (Sniper → McPAT → 3D-ICE processor
thermal simulation). Mission: extend it to study **photonic microrefrigeration** (laser
cooling) of chips — coupled power/temperature/performance modeling that the stock pipeline
lacks. Full status, validated results, and next steps: **docs/PROJECT_STATUS.md** (read it
before starting work). Architecture gap analysis: **docs/HotGauge_gap_analysis_and_extension_design.md**.

## Environment (server: phonon, Ubuntu 22.04)
- Repo lives at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`. Python env: conda `mxl_hotgauge` from
  `/mnt/nfs01/scratch/jbalma/anaconda3` — now **self-contained**; the old layered `env/` venv is
  no longer used (still on disk, unused). `source setup_environment.sh` is the single entry point
  and is **non-interactive safe** (it sources `conda.sh`; bare `conda activate` fails under srun).
- HotGauge is editable-installed with `--config-settings editable_mode=compat`. This matters:
  PEP 660's default finder loses to the repo-root `HotGauge/` namespace dir, so `import HotGauge`
  from the repo root resolves to nothing (`__file__ is None`). Reinstall with compat if it breaks.

### Running on Slurm compute nodes (node-0X)
Compute nodes are bare — they lack packages the phonon head node has. To run there:
```bash
sudo dpkg --add-architecture i386 && sudo apt-get update && sudo apt-get install -y \
  libc6-i386 lib32gcc-s1 libstdc++6:i386 libopenblas0-openmp parallel csh libpugixml1v5
```
(`libpugixml1v5` is needed only by the heatsink **FMU plugin** stacks — `skylake_HS483` etc.
load `3d-ice/heatsink_plugin/loaders/FMI/fmi_loader.so`, which links `libpugixml.so.1`. The
plain `skylake` stack works without it, so this failure only appears on plugin stacks, as
`ERROR: could not load heatsink plugin ...` in `<rundir>/logs/3D-ICE-Emulator.stderr`.)
- `McPAT/mcpat` is a **32-bit** binary → needs `libc6-i386` et al, else exec fails with the
  misleading "No such file or directory". `3d-ice` needs `libopenblas0-openmp`;
  `scripts/run_mcpat.py` shells out to GNU `parallel`.
- Fallback without root: `/mnt/nfs01/scratch/jbalma/mxl-nodelibs/{lib32,lib64}` holds those libs
  copied from phonon. `setup_environment.sh` auto-adds `lib64` to `LD_LIBRARY_PATH` when the
  system openblas is absent (covers 3D-ICE). McPAT still needs the real package, or invoke it via
  `.../lib32/ld-linux.so.2 --library-path .../lib32 ./McPAT/mcpat`.
- Sniper's `ldd` reporting `libxed.so`/`libtorch_cpu.so` "not found" is **expected on both nodes** —
  `run-sniper` sets `LD_LIBRARY_PATH` from in-tree libs at runtime. Not a gap.
- Toolchain is **built and working** in-tree (all git-ignored): `snipersim/` (SDE frontend,
  RISC-V-era fork), `McPAT/`, `3d-ice/` (emulator + heatsink-plugin FMUs, OpenBLAS-openmp).
- Build quirks already solved (do not re-fight): SuperLU 4.3 from MIT MacPorts mirror; `csh`
  required; 3d-ice links `/usr/lib/x86_64-linux-gnu/openblas-openmp/libopenblas.so.0` with
  matching rpath; OpenModelica needs MSL 3.2.3 (`installPackage(Modelica, "3.2.3+maint.om", exactMatch=true)`).
- Set `OMP_NUM_THREADS=1` for single 3D-ICE runs (openmp BLAS grabs all cores otherwise).

## What we've added (keep these conventions)
- `HotGauge/HotGauge/power/leakage.py` — temperature-dependent leakage models +
  `converge_power_temperature` fixed-point loop (relaxation, runaway guards, history).
- **Convergence is verified automatically — do not switch it off for anything quotable.**
  `converge_power_temperature` now (a) tests the **fixed-point residual** `|T_solved - T_driving|`
  rather than the change between successive solves (the old measure scales with `relax`, so
  tightening the damping for safety made the tolerance ~1/relax *weaker* — that is how a
  partially-converged field passed as an answer), and (b) **backtracks**: a step that grows the
  residual is rejected and retaken at half the damping, down to `min_relax=0.025`. `relax` is
  therefore a starting point, not a choice to get right. `run_leakage_feedback(verify=True)`
  (default) re-solves at half the damping and requires the peaks to agree within
  `verify_tol_K=1.0`, else the result carries `unconverged=True` and must not be quoted;
  `diverged` now means "diverged at every damping tried". Measured on a lumped model driven by
  the real 7nm leakage curve: the apparent cliff moved 23% across fixed `relax` 1.0→0.0125 and
  lands in a 0.01% band with backtracking. Study drivers default to `--relax 0.5 --max-iter 60`
  and print `** UNCONVERGED **` per row.
- `HotGauge/HotGauge/power/clock_search.py` — **clock as a free variable** (`f_nominal` used to
  be a hard cap and the model only derated downward, which is what made Study A's "+3.5%
  ceiling" an artefact of the input). Bisects the highest clock whose coupled solve holds the
  thermal limit; dynamic power scales as `V^2 f` through the shipped V/F table and leakage as
  `V**leak_v_exponent` (an assumption, default 1.0, not silently omitted). The V/F table stops at
  **5.0 GHz** — past it voltage clamps and the power cost is understated, so searches cap there
  and set `vf_clamped`. Driver: `examples/clock_headroom.py` (cooling sweep × MR on/off →
  sustainable clock). Because the criterion is a temperature limit, the answer does **not**
  inherit the uncalibrated `derate_per_K`.
- `examples/trajectory_probe.py` — prints the per-iteration residual/peak trajectory for one
  operating point, and where the *old* criterion would have stopped. This is the tool for
  telling "converging" from "being truncated".
- `HotGauge/HotGauge/thermal/leakage_feedback.py` — wires the loop to real 3D-ICE
  (`ICEThermalSolver`, `run_leakage_feedback`, McPAT↔floorplan name bridge). Supports
  `mode='transient'` (default) and `mode='steady'` (`--steady`); steady is the mode for
  cooling comparisons. **`assert_steady_supported` must not be removed**: 3D-ICE returns the
  unsolved initial temperature, silently and with no stderr, for steady + pluggable-heatsink
  stacks — see docs/PROJECT_STATUS.md.
- `scripts/mcpat_to_blk_lvl_power_dict.py` — now also emits `block_powers_split_*.json`
  (`unit -> [dynamic, leakage]`), default-on; the feedback loop consumes these.
- `HotGauge/HotGauge/power/performance_model.py` — Goal 1b, T→f_max→perf/W. The **hottest
  block sets the core clock** (`core_fmax` reduces with max, not mean).
- **T_ref must be read, never guessed**: `mcpat_tref_from_trace_dir()`. Our pipeline hardcodes
  330 K (`snipersim/tools/mcpat.py:859`); the old 360 K default made leakage 4× optimistic.
- **Leakage is not a single exponential** — use `load_calibrated_leakage_model()` with output
  from `examples/calibrate_leakage_model.py`. Local doubling varies ~180 K → ~8.6 K over
  310–400 K. McPAT returns nothing above ~410 K; above ~127 °C, report "non-viable", not a number.
- `HotGauge/HotGauge/thermal/sink_models.py` — parameterized steady-solvable cooling
  boundaries (`ThermalResistanceSink` in K/W is the power-regime workhorse;
  `render_stack_with_sink` writes a concrete `.stk`, leaving stock `ICE.py` untouched).
- `examples/steady_sink_sweep.py` — cooling-class × power-regime sweeps (the architecture
  study driver). `examples/calibrate_sink_surrogate.py` — FMU-anchored calibration; currently
  blocked, see PROJECT_STATUS.
- **The heatsink FMUs are broken in this build** (they load and run but reject ~no heat; the
  vendor's own example fails too). Don't trust FMU-derived numbers until rebuilt/validated.
- `HotGauge/HotGauge/thermal/microrefrigeration.py` — Goal 3. MR as **negative power sources**
  (validated: 3D-ICE accepts them and cools locally). Power model matches
  `docs/MXL-Photonic-Cooling-Power-Analysis.xlsx` exactly (MVP-1/2/3 regression-tested).
  **`eta_asf` is OPTICAL** — electrical COP is `eta_asf * eta_laser` (0.32 @ 0.85 wp = 0.272).
  `breakeven_ratio = eta_LPC * collection * (1+eta_ASF) * eta_laser`; **>1 is a target regime
  (net-generating), not an error** — only the first law is guarded.
- **Power scaling**: `die_power_of_trace()` counts only what lands on a floorplan block.
  Summing the DICE trace overstates it 2.36x (the hierarchy aggregates are still in the dict
  and get silently dropped by `populate_template`). Always scale with
  `scale_trace_to_die_power()`.
- **Core-7 is dropped** (~10 % of leaf power): floorplan is 7-core, trace is 8-core. Warned
  about at runtime; needs an 8-core floorplan to fix.
- **L3 leakage** now feeds back via `bridge_aggregates=True` (+45 %). Do NOT also bridge
  `NUCA` — it restates `Processor/Total L3s`.
- **Published block areas, and the three ways to read them wrongly.**
  `HotGauge/HotGauge/thermal/pack_areas.py` reads
  `docs/chip_design_lit/MXL-HotGauge-Floorplan-Pack/`. Each trap returns a plausible wrong
  answer, so each has a guard: `block_areas.csv` **mixes hierarchy levels** (a naive sum of
  Golden Cove's rows is +9.55 %; use `non_overlapping_blocks()`), `manifest.csv:category` is
  `die_floorplan_annotated` **not** the folder name, and the V/F voltage column is `voltage_v`.
  **The pack's images are SemiAnalysis subscriber content and third-party die shots — numbers
  derived from them may be published, the plates may not.**
- `HotGauge/HotGauge/thermal/core_templates.py` — Golden Cove / Redwood Cove as a **placed**
  floorplan built from published areas, arrangement read off the annotated plate, `source_image`
  per block, closure asserted in the constructor. The `accelerator_floorplan.py` pattern applied
  to a CPU core. `rescale_error_vs_published()` is the measured error bar on "scale a template by
  area ratio": **22 % worst block, 14 % mean**.
- **Replacing McPAT's areas breaks McPAT's powers, and the pack cannot supply new ones.** Areas
  and powers are outputs of one model; the pack publishes areas and **no per-block power for any
  part**. McPAT's un-itemised core power lands on the tiler's `core_other` slab (38 % of die
  power), and a published mix shrinks that slab 32×. Use
  `mr_comparison.py --power-follows-area <reference flp dir>` on any floorplan whose areas did
  not come from McPAT — it holds each block's **W/mm²** so only the arrangement changes. Without
  it the slab reaches 28 W/mm² and the die has no steady state.
- **`AVX_512_AREA_VS_FPU` is baked into `DERIVED_UNITS` at import**, so an area JSON cannot reach
  it — which is why every ISA variant silently carried the x86 value until 28 Aug 2026. Pass
  `generate_ncore_floorplans.py --vector-multiple`. The shipped constant (1.981) is 4.8× the
  value the Golden Cove plate gives (0.413) and is **deliberately left alone**: the back
  catalogue rests on it, and the corrected core is the `x86_golden_cove` variant instead.
- **The objective now has a second axis: exergy.** `HotGauge/HotGauge/thermal/exergy.py` —
  `phi = 1 - T0/Th`, the LPC ceiling (1.13), the self-powering condition (1.15). Heat lifted from a
  HOTTER source is worth more, so "cool everything" is not automatically right. **The temperature
  that belongs in phi is the EXTRACTOR's, not the junction's** — measured, the junction overstates
  phi by at most 8.2%, peaking near 2 W/mm^2, so junction temperatures are usable but the choice
  must be recorded (`exergy_map(..., temperature_is=...)`). See `docs/POWER_RECOVERY_PLAN.md`.
- **Do not propose a monolithic hot/cold zoned die — it was measured and it does not work.**
  40 W of removal on a 60.7 W die buys **1.24 K** of gradient against the 150 K the architecture
  asks for. Two independent methods (closed-form `thermal_zones.py` and a 3D-ICE solve) agree to
  1.71x. Two separate failure modes: coarse tile pitch cannot *address* the zones (2000 um is 170x
  worse than 100 um) and lateral conduction shorts them anyway. The cold zone has to be a separate
  **die**.
- **McPAT rejects temperatures outside 300-400 K** — *"Temperature must be between 300 and 400
  Kelvin and multiple of 10"*. The architecture template spans 150-600 K, so **both** of its
  interesting zones are outside the model. Our leakage curve stops at 310 K and clamps below;
  anything quoted for a colder zone is the clamp, not physics.
- `examples/leakage_feedback_smoketest.py` — staged end-to-end validation harness.
- `examples/inspect_feedback_iters.py` — post-mortem per-iteration diagnostics.
- Tests colocated with modules: `python -m pytest HotGauge/HotGauge/power/test_leakage.py
  HotGauge/HotGauge/thermal/test_leakage_feedback.py -q` (all pure-Python, no toolchain needed).

## Rules of engagement
- Changes to stock HotGauge files must stay **additive** (existing outputs byte-identical);
  new capability goes in new modules.
- The user reviews, commits, and pushes — don't push; list files to stage (never `git add .`;
  `snipersim/`, `McPAT/`, `mcpat_runs/` are untracked build/output trees).
- Never run `git clean -fdx` (would delete the built toolchain).
- Surface uncertainty and physically-suspect results explicitly; runaway/non-convergence is a
  meaningful signal, not an error to hide.
- **One architecture, one die** (decided 31 Aug 2026). The 34-core 7nm skylake floorplan is the
  only die in play until the physics is verified end to end. ISA variants, the accelerator die,
  n-core sweeps and the pack floorplans are parked for the next phase — each one adds a confound
  to questions that have already been confounded repeatedly. Vary the physics, not the die.
- **The leakage curve is CACTI's hard-coded 11-point `I_off_n` table**, not a measurement — see
  §P0.12 and `docs/evidence/device_leakage_asap7.json`. Its implied activation energy spans 69x and
  is non-monotone. Any claim resting on leakage-vs-temperature carries that caveat, and anything
  outside 310-400 K is extrapolation on top of an interpolation.
- **There is a SIMULATED replacement now — use it for anything quotable** (§P0.13).
  `device_leakage.load_simulated_curve()` reads `docs/evidence/device_leakage_spice_asap7.json`,
  produced by running the ASAP7 BSIM-CMG card in ngspice 47 + OSDI with OpenVAF-compiled
  Verilog-A (`HotGauge/power/spice_sim.py`, toolchain in `docs/BSIMCMG_TOOLCHAIN.md`). It is
  fitted to nothing. Two things it moved, in **opposite** directions:
  - **The cold floor is GIDL, not gate leakage** — 98 % of leakage at 200 K, ~40x above the gate
    floor §P0.12 assumed, so the **cold-zone prize is ~20x smaller** than that section promised.
    ASAP7 is predictive, so quote the cold end as a bracket: `mechanism='full'` vs `'gidl_off'`.
  - **The hot tail is gentler still** (500 K: 5820x pipeline, 349x analytic, 123x simulated), so
    P0.11's flat-die ceiling is *more* conservative than recorded, not less.
  - The analytic model in `device_leakage.py` is kept as an independent cross-check and agrees
    within 2x over 310-400 K. Don't delete it; don't quote it.
- **Studies select a curve with `--leakage-curve {pipeline,simulated,simulated-gidl-off}`**
  (`thermal.leakage_feedback.load_leakage_model`). ~~Default `pipeline` everywhere and it must stay
  that way~~ **`[+]` Default flipped to `simulated` on 9 Sep 2026 (user's decision, §P0.18.0):
  an un-flagged run is now arm D exactly.** Reproducing the recorded catalogue needs
  `--leakage-curve pipeline` explicitly. Both curves anchor at 330 K, so the swap changes the
  *shape* and nothing else.
- **`[!]` The cold-zone prize is 2.2x bigger than the pipeline curve said** (§P0.14,
  `docs/evidence/cold_zone_prize_simulated.json`) — because that curve **clamps below 300 K** and
  reports a 1.73x reduction where the physics gives 16.6x. Quote the **2.2x improvement**; it is
  invariant to the die-power conversion and that is why it is the safe number. The prize saturates:
  it is within 5 % of maximum by **280 K**, so the design target is barely sub-ambient, not cryogenic.
- **`[!]` The absolute prize is ~6 % of die power, NOT 10-30 %** (§P0.15). §P0.14's conversion
  ratios were inherited from `cold_zone_prize_bounds.json` (34.64 % static, 92.6 % cache share) and
  unreproducible; they are now reproduced **exactly** and they are a **scope error** — one core's
  leaves weighed against the whole chip's L3, on the trace's warm-up slice. §P0.14's guess that they
  were measured post-feedback at the operating temperature is **withdrawn**: dynamic power is
  temperature-independent and the recorded 2.6062 W is that slice's `T_ref` dynamic exactly.
  Re-derived on the pipeline's own denominator (power landing on a floorplan block, steady slices):
  **static 15.98 %, cache share 38.24 %**, prize **5.7 %** at 200 K, 4.5 % if the cold die carries
  L3 only. The McPAT-leaf view (9.1 %) is an **upper bound** — it omits `core_other`, which is 42 %
  of on-die leakage. Use `cold_zone_prize.die_ratios()`; never the 34.64/92.6 pair again.
- **`[!]` Which part of a leakage curve is load-bearing depends on the EXPERIMENT, not the curve**
  (§P0.15, `docs/evidence/clock_headroom_curve_compare.json`). A fixed-density **divergence test**
  (the density ladder) is decided by the local slope `d(ln P_leak)/dT` at the temperature the die
  sits at — its reported point is one the die *survives*, so the hot tail never enters. A
  **temperature-limited search** (`clock_headroom.py`) probes operating points the die does *not*
  survive and reads its answer off where they begin, so the tail decides them too. Consequences:
  the clock search barely moved when the curve was swapped (5 of 6 cooling points unchanged) but
  its **limiter** changed at 3 of 6 — pipeline ends the search in runaway, both simulated curves
  end it at the 100 °C spec. `CLOCK_HEADROOM.md`'s "it runs away before it reaches spec" is
  **withdrawn**; its clocks stand. §P0.14's prediction that this study would move *more* than the
  ladder is withdrawn — it moved less.
- **`[!]` P0.12's "P0.11's ceiling is conservative" is WITHDRAWN, and the ceiling moves DOWN**
  (§P0.14, `docs/evidence/uniform_density_curve_compare.json`). P0.12 predicted the ceiling would
  move *up* because the pipeline's hot tail is too steep. Measured on the simulated curve, the
  **uniform arm fails at 1.00 W/mm² where it held before** — one rung lower, not higher.
  - **Runaway is a *local* instability**, set by `d(ln P_leak)/dT` at the temperature the die is
    actually at (~317-347 K), not by leakage at 500 K — by then it has run away under either
    curve, so the 47x tail disagreement lives where the answer does not.
  - In that band the ordering **reverses**: the pipeline curve is nearly flat (0.0013/K at 310 K,
    0.0091/K at 330 K — the clamp again) while the simulated one runs ~0.036/K throughout, so the
    simulated curve carries **~9x more feedback gain at 320 K** and they cross over near 345 K.
    More gain runs away earlier.
  - `[!]` **So the recorded ceilings are optimistic, not conservative.** The defect that matters
    is the curve's flatness at 310-330 K, *not* its hot tail — and that same flatness is what made
    the cold-zone prize look small. One clamp, two wrong answers, opposite directions.
  - `[+]` **The GIDL bracket does NOT move the flat-die ceiling** (§P0.15,
    `docs/evidence/uniform_density_curve_compare_gidl_off.json`). §P0.14 called this the highest-value
    open item and predicted the opposite. Measured: the uniform arm holds 0.80 and fails 1.00 under
    **both** brackets — identical. Only the shaped arm's 0.60 point changes, from *unconverged* to
    *diverged*, which is a point becoming decidable rather than a ceiling moving. `[!]` The
    prediction failed because it compared **levels** where §P0.14's own mechanism says compare
    **slopes**: in the 316-328 K band the holding points occupy, the pipeline→simulated gain ratio
    is 6-14x while the bracket spread is only **1.16-1.27x**. Quote sub-ambient leakage across both
    brackets as before; do **not** carry the bracket as a caveat on the density ceiling.
  - `[+]` **Sub-rung, the flat-die ceiling moves ~14 %**: uniform arm 1.05-1.10 W/mm² (pipeline)
    against 0.90-0.95 (simulated), from a 0.05 W/mm² ladder on all three curves
    (`scripts/uniform_density_ladder_fine.sh`, 27 points). `[!]` **The move is on the uniform arm
    alone** — the shaped arm's *failing* rung is identical at 0.65 on both curves, so §P0.14's "the
    shaped arm is unchanged" survives a 4x finer ladder rather than being a coarse-rung artefact.
    The pipeline shaped arm fails at **0.65**, not the 0.80 §P0.11 recorded, and the simulated
    shaped arm gains a demonstrable hold at **0.55 W/mm² (69.0 °C)** where it previously had none.
  - `[!]` **"Diverging points finish in minutes" holds only far from the cliff.** Adjacent to one, a
    divergence takes hours — the solver must exhaust every damping level before calling it genuine.
    Slow progress at a rung next to a cliff is not a hang.
  - `[!]` **`spice_sim.DEFAULT_NFIN` is 1000 and that is a numerical setting, not a device.** One
    fin leaks below the linear solver's resolution — at `nfin=1` a cold-end point was 70 % wrong
    and a version cross-check appeared to disagree by 10 % where it agrees to 0.4 %. The driver
    asserts convergence against a 10x re-run; keep it that way.
- **The build trees under `spice_toolchain/` are gitignored and node-local hazards.** Always
  `source scripts/spice_env.sh` first — on node-06 `$HOME` is node-local and `/tmp` is a 2 GB
  tmpfs, so an unpinned cargo/conda build lands where the head node cannot see it. Edits to those
  trees go in `MXL_SPICE_fixes/` or they are lost (OpenVAF needs a patch there to run at all).
- **`--rbb-policy` defaults to `stock`** and must keep doing so until a catalogue re-run says
  otherwise: the amortized policy moves every recorded thermal number. See
  `HotGauge/HotGauge/thermal/rbb.py` and §P0.10.
- **`[+]` The 22 MR rescues SURVIVE the measured leakage curves** (§P0.16,
  `docs/evidence/mr_catalogue_curve_compare.json`). The airflow ladder re-run on `simulated` and
  `simulated-gidl-off`, **both arms at every point**: control diverges and the array holds at all
  six airflows on all three curves — **18/18**. `array_idle` diverges everywhere too. The headline
  *"across 20-120 CFM the unassisted die diverges at every airflow while the array holds at all"*
  is no longer resting on CACTI's eleven numbers. §P0.16 predicted the opposite (0/6) and is
  withdrawn.
- **`[!]` A loop gain measured at a runaway is NOT an invariant of the configuration** — it is set
  by the divergence test's stopping rule. `G = 1 + (residual_2/residual_1 - 1)/r` is recoverable
  from any recorded runaway log line with no re-solve, and it is a valid comparison *across
  operating points*; but a gentler leakage curve does not lower it — the die simply climbs further
  (residual 47 K -> 65 K at 120 CFM) and arrives at a similar `G`. Do not divide a curve ratio into
  a measured `G` to predict whether a configuration will hold. §P0.16's prediction failed on
  exactly this step, and §P0.15's measured fine ladder was the better predictor.
- **`[!]` MR array COSTS are not comparable across leakage curves as recorded** — the two arms'
  minimum-plan descents stop at different peaks (93.9 °C pipeline vs 91.3 °C simulated), and at
  88 CFM the whole extra cost is `dT/dQ = 0.3245 K/W` against the package's own measured
  **0.3247 K/W**. Compare at a matched peak, or compare `dT/dQ`, never watts. `--density` pins the
  die power, so `p_chip_W` moves only ~1 % across curves.
- **`[!]` `core_other` carries a converter inconsistency, and it HALVES the apparent static
  fraction** (§P0.16). `scripts/mcpat_to_blk_lvl_power_dict.py:get_per_core_total_power` sets
  `total_dynamic_power = 2 * runtime_dynamic` for every itemised per-core unit, while the bare
  `Core<N>` row (which is what `core_other` maps to) is built ~25 lines below **with no factor**.
  That is the exact `2.0000x` at 7/10/14 nm; leakage takes no factor on either path, which is why
  its ratio is a genuine node-dependent remainder. In raw McPAT the `Core` row's children sum to
  **1.0000x** it for dynamic, so **there is no un-itemised core dynamic — `core_other` should carry
  leakage only**. Measured on the 34-core die: **static fraction 18.43 % as built vs 32.03 %
  hierarchy-consistent (1.74x)**, and `core_other`'s share of on-die leakage **35.6 % -> 14.4 %
  (2.47x)**. `[+]` McPAT's own `Processor` block gives **29.36 %** static, so the corrected die
  reproduces McPAT and the as-built die does not. `[!]` Neither half of the fix works alone —
  residualising without undoubling puts *negative* power on `core_other`.
  `[!]` **Implication: §P0.15's static 15.98 % and its ~6 % cold-zone prize were computed on the
  as-built die and should rise ~1.74x** (prize toward ~10 %). Must be re-derived under the policy,
  not scaled by hand. The **2.23x improvement is untouched**.
  Implemented additively as `HotGauge/HotGauge/power/core_other.py` with
  `--core-other-policy {stock,hierarchy-consistent}`, **default `stock`**.
- **Parsing raw McPAT — two traps, both of which produced plausible wrong answers here.**
  (a) The per-core `L2` block is a section header with **no trailing colon** whose attributes print
  at its *own* indent; popping on `indent >=` re-parents it onto `Core` and the bare `Core` row then
  appears to hold L2's numbers — pop on strictly-greater. (b) McPAT decorates headers:
  `Integer ALUs (Count: 6 ):`, `Floating Point Units (FPUs) (Count: 2 ):`. Splitting the name on
  `:` yields `Integer ALUs (Count`, matches no JSON key, and **silently drops the three
  highest-power execution rows of every core**. Sniper's own parser keys on `^( *)([^:(]*)` —
  stop at `:` **or** `(`. This one cost a wrong write-up: it made the `core_other` static-fraction
  move look like 0.16 pp when it is 13.6 pp. **Prefer the JSON's own key structure to a text
  parser wherever the question allows it.**
- **`[!]` Cross-curve MR cost comparisons MUST be normalised to a common peak.** The minimum-plan
  descent stops wherever it first holds the target, so two curves land at different peaks and their
  watts are not comparable. Normalise with the package's own measured resistance (0.3247 K/W at
  88 CFM on the 34-core die) or compare `dT/dQ`. This bit three times in §P0.16 and **reversed the
  sign twice** — the granularity penalty reads 1.30x vs 1.70x raw and 1.29x vs 1.18x normalised.
- **`[!]` Check a study consumes an input before re-running it on a new one.**
  `examples/tile_pitch_sweep.py` — the source of the recorded 2.77x granularity result — does
  **linear solves and holds no leakage model at all**, so `--leakage-curve` there is a no-op. The
  coupled granularity question goes through `mr_comparison.py --pitch-um`.
- **`[+]` Fine cooling pitch saturates below ~200 um** (§P0.16, coupled ladder): 50/100/200 um cost
  19.476/19.476/19.470 W across an 813x range in tile count. The recorded "~50 um optics
  requirement" is conservative — 200 um buys what 50 um buys.
- **`[!]` node-06 has 251 GB of RAM; the HEAD NODE has 503 GB.** Size concurrency against the
  compute node, not against `free` run on phonon. `catalogue_rerun.py`'s "peak 83.5 GB of a 200 GB
  budget" is **per arm**, and its 200 GB default already exceeds this node. Run catalogue arms
  **one at a time** (`scripts/rerun_chain_sequential.sh`): four reached 240 GB of 251 in 17 min,
  and two then reached 231 GB.
- **`[!]` A solve campaign's memory scales with its CONVERGENCE RATE, not its point count.** A
  converging point holds its factorised 3D-ICE session for many more solves; a diverging one exits
  fast. Measured on identical point lists: 78 % converged -> 85 GB, 99 % converged -> **136 GB**.
  So the arm whose physics works best is the one that OOMs, and a memory budget calibrated on a
  divergence-heavy run will be too small for a convergence-heavy one.
- **`[!]` `scripts/srun_shim/` — run many streams inside ONE slurm step.** This allocation admits
  ~8 concurrent steps; a generated launcher that issues one `srun` per stream will queue the
  surplus while the node idles. Put the shim first on `PATH` and its `srun` calls become local
  forks. Same reason `scripts/campaign_inner.sh` exists.
- **`[!]` Feed `campaign_inner.sh` its joblist as a FILE on the node**
  (`srun ... bash -c 'cat FILE | PAR=N campaign_inner.sh'`). Piping the list into `srun`'s stdin
  **silently truncates it** — measured: 3 of 12 jobs ran and the campaign reported success.
- **`[!]` MOST OF THE RECORDED CATALOGUE'S DIVERGENCE IS AN ARTEFACT** (§P0.16, four-arm re-run,
  `docs/evidence/catalogue_arm_compare.json`). Control arm, 145 common points, one flag at a time:
  **pipeline+stock+stock diverges at 94; simulated+amortized+hierarchy-consistent diverges at 8.**
  The leakage curve is worth **57** of those points and the `core_other` accounting **22**; the RBB
  policy is worth **none**. Neither is a cooling improvement — both are corrections to wrong inputs.
  `[!]` This does **not** restate the density ceiling as a number: these are heterogeneous catalogue
  points, not a ladder, and §P0.11's Gini-0 arm is not among them. Re-run the density ladder under
  arm D's configuration before quoting any new ceiling.
- **`[+]` The RBB question is SETTLED: `amortized` changes no verdict anywhere.** B->C flips zero
  points in either direction across 145 points; it moves temperatures a little (control −0.55 K
  mean, array arm −3.02 K). §P0.10's source reading argues for `amortized` and the catalogue-wide
  re-run says it is low-risk. The default has not been changed — that is the user's call.
- **`[!]` The leakage curve's effect CHANGES SIGN across the ~345 K crossover.** §P0.14 measured the
  simulated curve moving the flat-die ceiling DOWN 14 % (its uniform arm sits at ~322 K, below the
  crossover, where the simulated curve carries MORE gain); the catalogue's control points run hot,
  above it, where it carries LESS, and 57 of them stop diverging. Both are right. **Neither "the
  curve makes things worse" nor "better" survives without saying which side of 345 K the point is
  on.** Consistent with this, the swap barely moves points that hold under both curves (mean
  +0.28 K) — it acts at the stability boundary. `core_other` is the opposite: it moves every point
  (mean −5.38 K) because it redistributes power rather than changing a feedback slope.
- **`[+]` The MR (`array_on`) arm is insensitive to all three flags** — no verdict flips at A->B or
  B->C, 3 at C->D. The rescue claim survives because it is a *difference*, and the array side of it
  barely moves while the control side moves a lot.
- **`[+]` The catalogue re-run is an OVERNIGHT run, not 63 days**- **`[+]` The catalogue re-run is an OVERNIGHT run, not 63 days** (§P0.16). `scripts/catalogue_rerun.py`
  re-planned 1 Sep: 252 points / 578 arms / ~161,218 solves / **6.3 h wall** on 6 memory-bound
  streams. The quoted "80,330 solves, 63.5 days" is the **cold** cost. Three flags now want that
  one run: `--leakage-curve`, `--rbb-policy`, and the `core_other` accounting.
- **`[!]` §P0.18 (3 Sep, second session) — read `docs/START_HERE.md` first; the four routing docs
  supersede everything above.** Four things landed:
  - **`--leakage-curve`: `simulated` is the default since 9 Sep** (recommended 3 Sep, applied on
    the user's decision). The reproducibility argument for `pipeline` was spent when the other
    two defaults moved; every §1 register number already sits on `simulated`; arm D is the
    measured combination. `test_leakage_curve_select.py` pins the new default.
  - **The array charged its own footprint** (`--array-coverage`, AREAL, default 1.0 on
    `mr_comparison.py` / `mr_clipping_study.py` / `clock_headroom.py`; `mr_array.DEFAULT_COVERAGE`;
    a block under a gap is routed to its nearest tile). `[!]` In the v91 device the tiles,
    waveguides and monolithic-backside LPC sit ABOVE the silicon: coverage cannot move a
    control-arm ceiling and `uniform_density_probe.py` does not consume it. **Measured: the charge
    is zero at 500 µm pitch / 200 µm burial** — quarter coverage (644/1126 blocks under gaps)
    holds the same ceiling on the same minimum plan to ~1 %. Per-tile flux rises 1/coverage and
    does not bind. `docs/evidence/array_coverage_armD.json`.
  - **The array-assisted ceiling under arm D is 2.60–3.00 W/mm²** (recorded: 1.60–1.80 on the
    pipeline curve). `[!]` **ENVELOPE, not package:** at 2.60 the array removes 251 W from a die
    dissipating 239 W; the 3.00 failure is `envelope insufficient`. Quote the rescue RANGE
    (`array_idle` fails 1.20, laser holds from there) and the cost ladder, not the top rung.
  - **SPICE beyond leakage:** `spice_sim.vt_deck` / `idsat_deck`, `power/device_vf.DeviceVFModel`,
    `examples/device_vt_vf_spice.py` → `docs/evidence/device_vt_vf_asap7.json`,
    `clock_headroom.py --vf-source spice[:T_K]`. `V_t,sat` 0.284 V, SS 61.0 mV/dec (+0.20/K),
    dVt/dT −0.46 mV/K, alpha **fitted** 1.45, I_off agrees with the leakage file to 0.76 %.
    `[!]` **The `V_t` lever re-priced 2× dearer in cooling: 50 mV ≈ 45–60 K, not 22 K** (the
    simulated curve doubles every 19–23 K above 345 K; the card's swing is 61–81 mV/dec). Only
    the 25 mV step (22–30 K) sits inside the demonstrated 45 K. `LADDER_GEN0` §2's table is
    superseded. Still a re-derivation, not a thermal measurement.
- **`[!]` Node-side files live on NFS.** The agent scratchpad under `/tmp` is head-node-local and
  invisible to `on_node.sh`; put node-side scripts under `spice_toolchain/tmp/`. A `.py` edited on
  the head node can be served stale to the node for ~1 min, so a node `pytest` failing on a bug
  you just fixed is the signature — re-run.
- **`[+]` §P0.19 (5 Sep) — `dt_max` is derived now, and it does not bind on this die.**
  `thermal/extractor.py` gives each platform a cooling flux versus its OWN temperature from v91's
  constitutive parameters (Urbach edge for the red-tail pump, McCumber emission on the
  thermalised core, first-law ledger with Table 1.1's parasitics, photon recycling for GaAs),
  anchored on Table 8.1, eq. 8.4 and Table 9.2 — **none of it Yb:YLF**. `--mr-extractor
  {dye,gaas,gaas-enhanced,gaas-retuned,…}` on `mr_comparison.py` applies it as a **per-tile cap at
  delivery**, self-consistent with the tile's measured response; the solver reports tile
  temperatures (`ICEThermalSolver(mr_temps=True)`). Measured on the rescue rungs: every rung
  reproduces §P0.18.2 with **zero tiles capped**; the coldest tile the array is ever driven to is
  **263 K** at 2.60 W/mm², above every platform's floor (207–259 K). What bounds the array is
  conservation and bistability, not the lift. `[!]` A **fixed-wavelength GaAs pump has a
  hot-side limit near 380 K** (the Varshni-narrowed gap crosses the pump): v91's per-temperature
  pump is necessary over a hot die. `[!]` **Keep `--mr-dt-max 45` alongside the curve**: the
  scalar also *shapes* the plan (uniform per block at the seed sensitivity); the curve alone
  gives an area-weighted envelope that lands ~30 % dearer and, at 2.40, on the hot branch.
  `[!]` Never make caps from a diverged field (the first pass did, and read "envelope
  insufficient" everywhere). Two things for the book's author: eq. 9.5 as printed is 3.3× its
  own Table 9.2 benchmark, and Fig. 9.9's 0.25–0.5 scale cannot be the ledger's `η_ext`.
- **`[+]` §P0.20 (8 Sep) — the target device is v98 Table 1.1, and `T_min` is closed without a
  measurement.** `docs/Photonic_Cooling_Devices___v98.pdf` supersedes v91 (`REFERENCES.md` §1).
  `--mr-extractor dye` is now rung 6 of v98's photonic ladder (Table 8.2) = Table 1.1's
  R640-SMILES row: 5.9 × 10³ W/mm² at 400 K, 813 at 300 K, 263 at 263 K. The temperature
  dependence is the **transparency cap** `x_max = [1 + e^{(E_00−E_p)/kT}]⁻¹` (eq. 5.7), a
  Boltzmann ratio thermal by construction, so it does not depend on the tail steepness σ; σ and
  the host loss move only the pump optimum and `T_min` (176 K), which sits where the capability
  is already negligible. `[!]` **v91 eq. 8.4's 10³–10⁴ W/mm² for a bulk film is withdrawn by
  v98** (a 10⁻² M × 5 µm film tops out at 0.03–0.09 W/mm² at 300 K); the 5 Sep "819 W/mm², `T_min`
  207 K" row rested on it and is superseded (`RESULTS_REGISTER.md` §2). The dye is a **hot-die**
  platform: 7× below design at 300 K tiles. The v98-vs-3 Sep zone conflict is decided — §P0.21.
- **`[+]` §P0.21 (8 Sep) — zone materials decided by the user: the storage (cold) zone material is
  Cr:LiSAF, the hot zone is the dye, Yb:YLF stays out of every zone.** `make_extractor('cr-lisaf')`
  is v98 §8.1.2 / Table 1.1 on the volumetric route (20–80 W/mm³ at F_P 30–100, quantum defect
  5.9 %, needs η_EQE > 0.94 — **every figure is a ceiling at η_EQE = 1**; at the demonstrated 0.90
  it heats). `[!]` **The DEFAULT cold plate is SINGLE-material** (`--mr-zone-mode single`): a
  cold-zone / hot-zone tile arrangement must be laid out against the floorplan, i.e. designed
  with the vendor per architecture, which defeats the architecture-agnostic premise.
  `--mr-zone-mode dual` (`DualZoneExtractor`, `tiles_over_blocks`) exists to *measure* that impact
  once the floorplan is a swept variable (Phase 2) or the array is integrated at die manufacture.
  Never make it the default; never quote a dual-mode number as transferable to another die.
  Smoke point (2.00 W/mm²): the default reproduces P0.20 exactly; `dual` is a **1 % effect** on
  the hot-spot objective (0.1 W shortfall, 80 cold tiles) because the planner never drives the
  caches cold there — measure it against a cache-leakage objective or in Phase 2, not on this
  ladder. `[!]` P1 found a latent P0.20 bug: the uncapped first-plan re-cap tripped the
  stale-plan guard (`preview_shortfall` fixes it; the P0.20 target-device rows now reproduce).
- **`[+]` §P0.21.5 (9 Sep) — three corrections.** (1) `--leakage-curve` **defaults to `simulated`**
  now (user's decision); an un-flagged run is arm D; `--leakage-curve pipeline` reproduces the
  recorded catalogue. (2) **`docs/Photonic_Cooling_Devices___v100.pdf` supersedes v98**: same
  numbers for the target device (rung 6), Cr:LiSAF and GaAs; chapter-8 equations renumbered
  (η_cool 8.6, p_max 8.8, d_min 8.9); Table 1.1 gains `nir-cyanine` and `j-aggregate` presets
  (ceilings, cascade stages, not the target device); **§1.18 and §10.9 are the book's own frame
  for the evolution ladder** (budget inequality 1.32, hybrid cap 1.33, three-zone template and
  its three walls). (3) `recovery_at_temperature.json`'s "crossing at 408 K" was the
  *self-powering* temperature; the **export crossing is 614 K** (90 % laser preset), from the
  rows' own expression. Quote the export crossing.
