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
