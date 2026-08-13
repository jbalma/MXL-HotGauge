# MXL-HotGauge

Maxwell Labs fork of [Tufts HotGauge](https://github.com/TuftsCompArchLab/HotGauge), extended to
model **photonic microrefrigeration (MR)** — anti-Stokes fluorescence laser cooling applied at
on-die hotspots — and its effect on processor performance, power and temperature.

Upstream HotGauge chains Sniper → McPAT → 3D-ICE to find hotspots. This fork closes the loop:
temperature feeds back into leakage power, leakage back into temperature, and the converged
temperature sets the achievable clock. That fixed point is what makes it possible to ask whether
spending a watt on a fan or a watt on a laser buys more compute.

> **New here?** [Quick start](#quick-start) → [What this fork adds](#what-this-fork-adds) →
> [docs/SIMSCALE_INTEGRATION.md](docs/SIMSCALE_INTEGRATION.md) for the current physics results.

---

## Quick start

On phonon (Ubuntu 22.04, Slurm, no root on the compute nodes):

```bash
git clone <this repo> MXL-HotGauge && cd MXL-HotGauge
./install.sh                      # ~1-2 h, mostly Sniper and the heatsink plugin
source setup_environment.sh       # every session, including inside srun/sbatch
python -m pytest HotGauge/HotGauge -q
```

`install.sh` needs **no root**. Everything comes from conda-forge into a self-contained
environment; nothing is written outside the repo, the conda env, and `$MXL_PREFIX`
(`./.mxl` by default).

| Command | Use when |
|---|---|
| `./install.sh --skip-sniper` | You only need the thermal/power side; skips the slowest build |
| `./install.sh --check` | Verify an existing install without building anything |
| `MXL_CONDA=/path/to/conda ./install.sh` | Your conda is somewhere unusual |
| `MXL_JOBS=8 ./install.sh` | Limit build parallelism |

> **Do this first if you value your afternoon.** Phonon's conda is 4.12 with the classic
> solver, which takes **25+ minutes just to solve** this environment — long enough that it
> looks hung, and people kill it. One-time fix, worth it for every conda env you ever create:
>
> ```bash
> conda install -n base -c conda-forge conda-libmamba-solver
> conda config --set solver libmamba
> ```
>
> `install.sh` detects mamba/libmamba and uses whichever is fastest, warning you if it is stuck
> with the classic solver.

### Running on a compute node

```bash
salloc -N1 --exclusive --mem=0        # then, from the allocation:
srun --jobid=<id> bash -lc 'source /path/to/MXL-HotGauge/setup_environment.sh && \
    cd /path/to/MXL-HotGauge && python examples/simscale_hpc_study.py'
```

Three things bite people here:

- **`conda activate` fails under `srun`** unless `conda.sh` is sourced first. That is exactly
  what `setup_environment.sh` does — always source it rather than activating conda by hand.
- **`srun` runs one step at a time** per allocation. A second `srun` blocks with *"step creation
  temporarily disabled"* until the first finishes. Pass `--overlap` to run alongside.
- **Write long runs straight to a log file**, not through `tee`/`tail` — a pipe buffers, so if
  the job is killed you lose everything it had produced.

---

## Why the install is unusual

The upstream README assumes RHEL 9 and `dnf install` as root. Phonon is Ubuntu 22.04 and you
will not have root on the compute nodes, so `install.sh` takes a different route. Two details
will otherwise confuse you:

**McPAT is a 32-bit binary.** `McPAT/mcpat.mk:25` hardcodes `CXX = g++ -m32`, so it needs
`/lib/ld-linux.so.2` and 32-bit libc/libstdc++ — normally the `libc6-i386` package, which needs
root. Instead the installer unpacks those `.deb`s into `.mxl/lib32` with `dpkg -x` and installs
a wrapper at `McPAT/mcpat` that invokes the real binary through the staged loader. Callers need
no changes. Rebuilding McPAT as 64-bit would be simpler, but it is old code with known 64-bit
correctness problems and Tufts ship it 32-bit — quietly changing the word size risks wrong power
numbers, which is worse than an awkward install.

**Compute nodes can be missing libraries the head node has.** `setup_environment.sh` appends
`.mxl/lib64` to `LD_LIBRARY_PATH` *last*, so system copies always win and staged copies only
fill genuine gaps.

### The 3D-ICE tree is fetched, not cloned

`3d-ice/`, `McPAT/` and `snipersim/` are **not in git** — together they are over 2 GB, and
`get_and_patch_3DICE.sh` / `get_and_patch_McPAT.sh` fetch them. `install.sh` runs those for you.

That matters because this fork hand-edits four 3D-ICE source files, and upstream's own patches
*reintroduce* two of the bugs they fix. Those four files are versioned in
[`MXL_3DICE_fixes/`](MXL_3DICE_fixes/) and copied into place by `install.sh`. If you ever re-run
`get_and_patch_3DICE.sh` yourself:

```bash
./MXL_3DICE_fixes/apply.sh          # re-apply the fixes
./MXL_3DICE_fixes/apply.sh --check  # or just report what differs
make -C 3d-ice/heatsink_plugin && make -C 3d-ice
python examples/fmu_acceptance_test.py
```

See [3D-ICE heatsink FMU](#3d-ice-heatsink-fmu) for what each fix does.

---

## What this fork adds

### Temperature ↔ power feedback

`HotGauge/thermal/leakage_feedback.py` closes the loop upstream leaves open. Leakage is rescaled
against solved per-block temperatures and iterated to a fixed point, with runaway detection for
when no steady state exists. It also adds a **steady-state** solver mode (upstream is
transient-only), which is what makes parameter sweeps affordable.

Watch for: 3D-ICE silently returns the initial temperature if you ask for a steady solve with a
pluggable (FMU) heat sink. `assert_steady_supported()` catches that rather than letting you
publish a flat line.

### Cooling models — `HotGauge/thermal/sink_models.py`

| Model | What it is |
|---|---|
| `ConstantHTCSink` | Fixed heat transfer coefficient; the stock `skylake.stk` behaviour |
| `ThermalResistanceSink` | Specified in K/W, the way coolers are actually datasheeted |
| `PumpedSink` / `HS483AirSink` | Calibrated against the repaired HS483 FMU |
| `BaffledFinSink` | **Server-class**, from the SimScale CFD study — use this for HPC work |

`fan_specs.py` carries real datasheet fans (Delta PFB0412EN-E and relatives), validated against
`docs/Data_sheets/fan_efficiency_curve_RM.xlsx`.

### Photonic microrefrigeration — `HotGauge/thermal/microrefrigeration.py`

Applies cooling at individual floorplan blocks subject to physical limits: maximum heat flux,
maximum ΔT, and a **minimum optical spot size** (100 µm). That last one is a real constraint —
on our floorplans the two hottest units are 13.4 µm and 1.3 µm wide and cannot be targeted at
all. Accounting covers laser wall-plug efficiency and laser-power-converter recovery, and
matches the Maxwell Labs power-analysis spreadsheet.

### Performance model — `HotGauge/power/performance_model.py`

Temperature → f_max derating and throttling, so results come out as GFLOP/s rather than only °C.
**The derate slope is uncalibrated** and absolute throughput inherits that uncertainty; the
*ratio* between configurations is far more robust than the absolute number.

### Arbitrary core count

`examples/generate_ncore_floorplans.py` builds N-core floorplans (34, 70 and 128-core are
generated and used in the current studies) and `replicate_trace_cores` tiles an 8-core McPAT
trace onto them. Core counts are checked for aspect ratio — 32 cores would otherwise tile as a
2×17 strip whose thermal answer is dominated by its shape.

---

## Key examples

| Script | What it answers |
|---|---|
| `examples/simscale_hpc_study.py` | Where does leakage feedback break the CFD's linear model? |
| `examples/mr_comparison.py` | MR vs no MR across floorplans at matched power density |
| `examples/hybrid_cooling_optimizer.py` | How to split a cooling budget between fan and MR |
| `examples/plot_floorplans.py` | Floorplan block maps and power-density maps |
| `examples/calibrate_leakage_model.py` | Fit the leakage curve from McPAT |
| `examples/fmu_acceptance_test.py` | Does the heatsink FMU behave physically? |

All take `--help`.

---

## Gotchas worth knowing up front

**McPAT's temperature range is hard-limited** to 300–400 K in 10 K steps. Above 400 K the
leakage model extrapolates with an Arrhenius tail — use it to decide *whether* a configuration
diverges, not by how much.

**T_ref matters more than it looks.** The pipeline anchors leakage at 330 K; assuming 360 K
instead makes predicted leakage roughly 4× too optimistic.

**Power density depends entirely on coarse-graining.** The same 128-core die is 0.58 W/mm²
averaged over its area, 53 W/mm² over the hottest 1% of blocks, and 96 W/mm² at the peak. When
Maxwell Labs says "power density" it usually means the functional-unit scale — tens of W/mm². Be
careful with literature numbers that mean the die average.

**`die_power_of_trace` counts only power landing on real floorplan blocks.** McPAT emits
hierarchy aggregates (`Processor`, `Core0`, `Processor/Total L3s`) that restate their children;
summing everything overcounts by ~2.4×.

### 3D-ICE heatsink FMU

The HS483 FMU was broken and is now repaired — the acceptance test passes (raising fan speed
lowers temperature, constant power asymptotes). Four stacked bugs, **two of them introduced by
upstream's own patches**:

1. `spreaderX0` read as −9.09e+11 µm, so all 360,000 grid cells were empty and no heat flowed
2. the same `fixed=false` problem for `constantFanSpeed` / `constantAirTemperature`
3. `initialTemperature` exported as `calculatedParameter`, which FMI forbids setting
4. the plugin initialised with `StepTime = 0`, so the FMU never advanced

Co-simulation is stable only at `dt <= 0.01 s` (~0.24 s wall per step). This is why re-running
the upstream patch scripts is a bad idea.

---

## Repository layout

| Path | Contents |
|---|---|
| `HotGauge/` | The Python package (installed with `pip install -e`) |
| `examples/` | Studies and analysis scripts; the main entry points |
| `scripts/` | Sniper → McPAT glue |
| `end_to_end/` | Full Sniper-through-3D-ICE driver |
| `docs/` | Findings write-ups, fan datasheets, the SimScale CFD study |
| `3d-ice/`, `McPAT/`, `snipersim/` | Vendored simulators, already patched |
| `RHEL9_patches/` | Upstream patches — **see the warning above** |
| `mcpat_runs/` | Pre-generated McPAT traces used by the examples |

### Documentation

- [`docs/SIMSCALE_INTEGRATION.md`](docs/SIMSCALE_INTEGRATION.md) — current physics results: the
  hotspot constriction resistance airflow cannot reach, and cross-validation against the
  SimScale CFD study. **Read this first.**
- [`docs/FAN_SELECTION.md`](docs/FAN_SELECTION.md) — which fan represents a server-class part,
  and why die-level cooling is a static-pressure problem
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — running status
- [`docs/RESUME_NOTES.md`](docs/RESUME_NOTES.md) — in-flight work and open questions
- `HotGauge_use_instructions.pdf` — upstream usage guide, still accurate for the base pipeline

---

## Upstream

Tufts HotGauge: https://github.com/TuftsCompArchLab/HotGauge — see `LICENSE` and
`OLD_README_deprecated.md` for the original RHEL 9 instructions.
