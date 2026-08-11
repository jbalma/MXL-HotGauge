# MXL-HotGauge — working context for Claude sessions

Maxwell Labs fork of the Tufts **HotGauge** framework (Sniper → McPAT → 3D-ICE processor
thermal simulation). Mission: extend it to study **photonic microrefrigeration** (laser
cooling) of chips — coupled power/temperature/performance modeling that the stock pipeline
lacks. Full status, validated results, and next steps: **docs/PROJECT_STATUS.md** (read it
before starting work). Architecture gap analysis: **docs/HotGauge_gap_analysis_and_extension_design.md**.

## Environment (server: phonon, Ubuntu 22.04)
- Repo lives at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`; Python env: conda `mxl_hotgauge` + `env` venv.
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
  (`ICEThermalSolver`, `run_leakage_feedback`, McPAT↔floorplan name bridge).
- `scripts/mcpat_to_blk_lvl_power_dict.py` — now also emits `block_powers_split_*.json`
  (`unit -> [dynamic, leakage]`), default-on; the feedback loop consumes these.
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
