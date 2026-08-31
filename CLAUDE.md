# MXL-HotGauge — working context for Claude sessions

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
  **`eta_asf` is OPTICAL** — electrical COP is `eta_asf * eta_laser` (0.20 @ 0.70 wp = 0.14).
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
- **`--rbb-policy` defaults to `stock`** and must keep doing so until a catalogue re-run says
  otherwise: the amortized policy moves every recorded thermal number. See
  `HotGauge/HotGauge/thermal/rbb.py` and §P0.10.
