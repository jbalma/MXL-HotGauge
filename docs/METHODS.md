# Methods — how to drive this codebase and get a correct answer

**Written 3 September 2026 for a fresh session.** Companion to `docs/RESULTS_REGISTER.md` (what may
be quoted) and `docs/REFERENCES.md` (what the physics rests on).

This file is about **producing** a number. The register is about **quoting** one.

---

## 1. The pipeline, end to end

```
Sniper trace  ->  McPAT  ->  block_powers_split_*.json  ->  prepare_dice_trace  ->  3D-ICE
                                      |                                              |
                                      |                                    per-block temperatures
                                      |                                              |
                                      +------------ leakage feedback loop <-----------+
                                                    (converges P and T together)
```

Two things about this loop that are not obvious and both have cost time:

1. **It is a fixed-point solve, not a forward pass.** Power sets temperature, temperature sets
   leakage, leakage sets power. `converge_power_temperature` damps and re-anchors; a run either
   converges, **diverges** (no steady state), or comes back `unconverged` — which is *neither*.
2. **The trace is not the die.** The trace is 8 cores; the catalogue die is 34.
   `replicate_trace_cores` tiles core activity round-robin, and
   `scale_trace_to_die_power` renormalises to the requested density. **Absolute watts in the trace
   never survive to a result** — only the distribution does.

### 1.1 The workload trace, and its two constraints

`mcpat_runs/7nm/linpack_3.8GHz/` — LINPACK at 3.8 GHz, 16 slices, 400 → 3400 µs, 200 µs apart.

- **It is single-threaded.** Exactly one core is active in every slice. The 34-core die models a
  homogeneous many-core running the same kernel — *not* a measured 34-thread workload. Say so when
  it matters.
- **The first five slices are warm-up.** 760 k instructions/slice while caches fill, stepping to
  ~2.1 M at 1600 µs. Core-0 power is **2.74 W warm vs 7.61 W steady**.
  `STEADY_FROM_TICK = 1_600_000_000_000` is drawn exactly where that step completes.
  `[!]` Using an earlier slice is what inflated a recorded static fraction from 15.5 % to 34.6 %.

---

## 2. Running things

### 2.1 Never on the login node

Every solve is a 3D-ICE factorisation and SuperLU is threaded; on the login node it competes with
itself and with other users.

```bash
squeue -u jbalma                          # get the jobid
scripts/on_node.sh <jobid> <command>      # one command inside the allocation
```
Always `OMP_NUM_THREADS=1`.

### 2.2 Campaigns: one slurm step, N local workers

This allocation admits about **eight** concurrent slurm steps. One `srun` per point queues 88 of 96
cores into idleness. Use the campaign runner, which forks workers inside a single step:

```bash
scripts/build_joblist.sh > /tmp/jobs.tsv
srun --jobid=<id> --overlap -n1 bash -c 'cat /tmp/jobs.tsv | PAR=14 scripts/campaign_inner.sh'
```

`[!]` **Feed the joblist as a file read on the node.** Piping it into `srun`'s stdin silently
truncates — measured: 3 of 12 jobs ran and the campaign reported success.

`[!]` For a generated launcher that issues its own `srun` per stream (`catalogue_rerun.py`), put
`scripts/srun_shim/` first on `PATH` so those become local forks inside one step.

### 2.3 Memory is the limit, not cores

**node-06 has 251 GB. The head node has 503 GB.** Size against the compute node.

`[!]` A campaign's memory scales with its **convergence rate**, not its point count — a converging
point holds its factorised session for many more solves; a diverging one exits fast. Measured on
identical point lists: 78 % converged → 85 GB, 99 % converged → **136 GB**. *The arm whose physics
works best is the one that OOMs.* Run catalogue arms one at a time
(`scripts/rerun_chain_sequential.sh`).

### 2.4 Node-side files live on NFS, not in the head node's scratch

`[!]` node-06's `/tmp` and `$HOME` are **node-local** (`docs/BSIMCMG_TOOLCHAIN.md`); the head
node's `/tmp` is likewise invisible from the node. A script written into an agent scratchpad
under `/tmp` and handed to `on_node.sh` fails with "No such file". Put node-side scripts under the
repo — `spice_toolchain/tmp/` is gitignored and shared. And a `.py` edited on the head node can be
served to the node with **stale attributes for up to a minute**, so `pytest` there may run the
*previous* compiled version of a just-edited test: a failure that reproduces a bug you have
already fixed is the signature; re-run.

### 2.5 Reading progress honestly

Counting output files reads **high** (argv and plan files); counting `mr_comparison.json` reads
**low** (several drivers are not that); counting stream `.done` markers also reads low (a stream can
finish all its points and leave no marker). Use `scripts/rerun_progress.sh`, which counts against
each run's own `plan.json`.

---

## 3. The device layer: what SPICE gives you, and what it does not

**Updated 3 September (§P0.18.3).** The toolchain now produces **three** views of the same
ASAP7 `nmos_rvt` card — leakage, threshold and drive current — all from ngspice 47 + OSDI +
OpenVAF-compiled BSIM-CMG 110, fitted to nothing. What still comes from elsewhere is stated.

| quantity | where it actually comes from | status |
|---|---|---|
| **Leakage vs temperature** | `spice_sim.ioff_deck`; `examples/device_leakage_spice.py` → `docs/evidence/device_leakage_spice_asap7.json` | **SPICE, §P0.13** |
| **`V_t(T)`, `SS(T)`, DIBL** | `spice_sim.vt_deck` (gate sweep at `V_ds` = 0.05 V and `V_dd`), constant-current criterion 100 nA × W_eff/L_drawn; `examples/device_vt_vf_spice.py` → `docs/evidence/device_vt_vf_asap7.json` | **SPICE, §P0.18.3** — `V_t,sat` 0.284 V, SS 61.0 mV/dec at 300 K, −0.46 mV/K, +0.20 mV/dec/K |
| **`I_on(V, T)` and the V/F *shape*** | `spice_sim.idsat_deck` (diagonal `V_gs = V_ds`); `power/device_vf.DeviceVFModel` gives `f(V) = k·I_on(V)/V`; `clock_headroom.py --vf-source spice[:<T_K>]` | **SPICE, §P0.18.3** — alpha **fitted** at 1.45 (300 K), not assumed |
| **V/F curve, default in the clock search** | `power/irds_vf.py`, IRDS 2024 `MM01 - LOGIC` (`--vf-source table` is still the shipped `VF_PAIRS`; `irds:<year>` the roadmap) | roadmap; **still the default**, so recorded clock results reproduce |
| **The absolute clock anchor of the device curve** | the trace's 3.8 GHz at the card's 0.70 V | a *choice*, stated on the model (`calibrated = False`); `clock_search` uses ratios and is insensitive to it |
| **The analytic `V_t` in `device_leakage.py`** | still a parameter of the analytic cross-check model | kept as a cross-check; **do not quote** |

`[!]` **Three conventions travel with the numbers.** (1) A threshold is a *criterion*; compare
temperature coefficients and shapes across sources, never levels (the roadmap's 0.156 V and the
card's 0.284 V are different devices, and that one difference is 44 % of V/F shape at 0.45 V).
(2) The swing is fitted over two decades below the criterion — clear of GIDL below, clear of the
threshold above — and a one-decade window with a 50 mV gate step returns nothing. (3) The
`V_t` lever's cost now uses the card's swing **at the operating temperature** (61 → 81 mV/dec over
300–400 K), which is why it re-priced 1.2–1.6× dearer than `LADDER_GEN0` (§P0.18.3).

`[!]` **What is still not a measurement:** the lever itself. The device numbers exist; a low-`V_t`
die has not been run under the array through the coupled solve, and `dt_max` is still the
device team's number.

### 3.1 Choosing a leakage curve

```
--leakage-curve pipeline            # CACTI's 11 hard-coded numbers -- the recorded catalogue
--leakage-curve simulated           # BSIM-CMG on the ASAP7 card (P0.13)
--leakage-curve simulated-gidl-off  # the other GIDL bracket
```

`[!]` **The two curves cross at ~345 K.** Below it the simulated curve carries up to **14.6×** more
feedback gain; above it as little as **0.15×**. So *which* part of a curve is load-bearing is a
property of the **experiment**, not of the curve:

- a divergence test at fixed power is decided by the local slope at the operating temperature;
- a **limit search** is decided by the tail as well, because it deliberately probes points the die
  does not survive.

`[!]` **The GIDL bracket has changed nothing in four consecutive studies.** Stop carrying it as a
caveat on anything but sub-ambient leakage.

### 3.2 Reading a divergence

`G = 1 + (residual₂/residual₁ − 1) / r` recovers the loop gain from any recorded runaway log line
with no re-solve. It is valid **across operating points**.

`[!]` **It is not an invariant of the configuration.** A gentler curve does not lower it — the die
climbs further and arrives at a similar `G`. Never divide a curve ratio into a measured `G` to
predict whether something holds. That mistake produced two wrong predictions in one session.

---

## 4. The microrefrigeration model

### 4.1 The envelope, and which numbers are which kind

| parameter | default | kind |
|---|---|---|
| `h_max` | 1000 W/mm² | **demonstrated** platform low end (range 10³–10⁴) |
| `dt_max` | 45 K | **demonstrated** (Draft_5) as a scalar; `[+]` **derivable since §P0.19**: `--mr-extractor {dye,gaas,…}` bounds each tile by the extractor's own cooling flux at the tile's solved temperature (`thermal.extractor`), so the lift is an output. Keep `--mr-dt-max 45` alongside it to hold the recorded plan shape (§P0.19); drop it only when the curve is meant to bound the envelope alone. |
| `eta_asf` | **0.32** | range **0.10–0.60** (Draft_5 §3.5.4, across MVP stages); **target**, middle ground |
| `laser_wallplug` | 0.85 | **target** (70–75 % demonstrated) |
| `lpc_efficiency` | 0.92 | **target** (68.9–74.7 % demonstrated, v91 §7.2.2) |

`DEMONSTRATED` in `microrefrigeration.py` holds the bench figures next to the targets so the gap is
inspectable rather than remembered.

### 4.1a The extractor's cooling curve (§P0.19)

`thermal.extractor.DyeExtractor` (R640-SMILES on **v98's** volumetric route, eqs. 5.7 and 8.4–8.9;
the rungs of Table 8.2 as presets via `from_rung`) and `SemiconductorExtractor` (GaAs at Table
9.2 with photon recycling; `gaas-enhanced` = Table 1.1's row) give `cooling_density_W_per_mm2(T_ext)`:
the most heat the film removes per unit footprint at its own temperature. **`--mr-extractor dye`
is the target device**: rung 6 of the ladder = Table 1.1's R640-SMILES row, the Tier-I design
point at 400 K (5.9 × 10³ W/mm²; 813 at 300 K; 263 at 263 K). `dye-near` is rung 2, the
near-term experimental point (1.9 W/mm² at 400 K). `examples/extractor_curves.py` writes the
curves, anchors and the rung this die needs to `docs/evidence/extractor_cooling_curves.json`.

`[+]` The temperature dependence is carried by the transparency cap `x_max`, a Boltzmann ratio
that is thermal by construction, so it does not depend on the tail steepness σ; σ (`DYE_SIGMA_BOOK`
= 1, `DYE_SIGMA_DISORDER` = 0.26) and the host loss (`DYE_BACKGROUND_CM`) move only the optimum
pump wavelength and the point where net cooling vanishes, which sits where the capability is
already negligible. That is what closed the `dt_max` ask without a measurement (§P0.20).

`[!]` The cap is solved **self-consistently** with the tile's response (`extractor_caps`): the
curve evaluated at the last solve's tile temperature oscillates whenever a tile cools by more
than a degree per watt. And the scalar `dt_max` was also *shaping* the plan: without it the
envelope is area-weighted and the descent lands ~30 % dearer with nothing physical binding.
Run `--mr-dt-max 45` with the extractor for anything compared against the recorded ladders.

**Zone materials and `--mr-zone-mode` (§P0.21, decided 8 Sep).** The storage (cold) zone material
is Cr³⁺:LiSAF (`make_extractor('cr-lisaf')`, v98 §8.1.2 / Table 1.1 on the same volumetric route;
every figure a ceiling at η_EQE = 1 — at the demonstrated 0.90 it heats), the hot zone is the
dye; Yb:YLF is not a zone material. **The default cold plate is single-material**
(`--mr-zone-mode single`): a cold-zone / hot-zone tile arrangement is laid out against the
floorplan (`mr_array.tiles_over_blocks`: a tile is cold when more than half the block area
under it matches `--mr-cold-zone-pattern`, default `^(L2|L3)`), i.e. a per-architecture
product that defeats the architecture-agnostic premise. `--mr-zone-mode dual` wraps the two
curves in `DualZoneExtractor` and `extractor_tile_caps` dispatches per tile. Use it to
*measure* the arrangement's impact when the floorplan is a swept variable (Phase 2) or the
array is integrated at die manufacture; never quote a dual-mode number as transferable.
`[!]` The first-plan re-cap must **preview** the shortfall (`CoolingApplication.preview_shortfall`)
rather than apply the plan: applying advances the wiring's plan generation, and an uncapped
plan that is never solved trips `ArrayWiring`'s stale-plan guard on the next application
(found by the §P0.21 regression point; the P0.20 target-device rows pre-date the block).

### 4.2 Two ledgers, and only one is physical

- `breakeven_ratio` — **first law**, the `phi → 1` limit. A loop it calls net-generating is not
  necessarily permitted by the second law.
- `breakeven_ratio_at(T_h)` — **second law**, weighting the anti-Stokes term by the Carnot factor
  `phi = 1 − T₀/T_h`. **Use this one.**

`[!]` At the shipped envelope the first-law ledger reports **1.032** — free energy — which is what
produced 36 negative `p_mr_net_W` rows. That is the `phi → 1` limit, not a claim about physics: the
second-law form is below 1 at every survivable junction temperature. `[!]` **A 3 Sep revision moved
the default to 0.20 and reported that this made the pathology unreachable. That change is
withdrawn** — the range is 0.10–0.60 and 0.32 stands — so the first-law ledger reports net
generation at the default and the two ledgers must still not be conflated.
`examples/findings_recovery_correction.py` re-prices the 36 recorded rows.

### 4.3 Comparing MR costs

`[!]` **Never compare MR cost in watts across leakage curves or accounting policies.** The
minimum-plan descent stops wherever it first holds target, so two runs land at different peaks.
Normalise to a common peak at the package resistance (0.3247 K/W at 88 CFM on the 34-core die), or
compare `dT/dQ`. This has **reversed a sign twice**.

`[+]` Sweeping `eta_asf` across 0.10–0.60 moves **every MR cost in proportion and no thermal
result at all** — not a peak, not a rescue verdict, not a density ceiling — because the planner
sizes its removal from the thermal problem. That makes it a cheap sensitivity axis: one sweep
bounds the cost claims without re-running a single solve's thermal outcome.

---

## 5. Gotchas that have each cost a session

| trap | what happens | the rule |
|---|---|---|
| Siting a refinement off an **unfinished** ladder | The points still running are the ones nearest the cliff — the only region a refinement cares about | Finish the ladder first. Cost: six solves. |
| Treating a slow point as a hang | A divergence adjacent to a cliff must exhaust every damping level; `sweep_runner` shells out so the parent shows ~0 % CPU | Check for a live `3D-ICE-Emulator` child, not parent CPU |
| Re-running a study on a new input without checking it **consumes** that input | `tile_pitch_sweep.py` holds no leakage model — `--leakage-curve` there is a no-op | Grep the driver first |
| Quoting a partial campaign | Shared points are non-random — whichever finished first | `catalogue_arm_compare.py` refuses to summarise mismatched arms |
| `pkill -f <pattern>` | Matches the agent's own command line and kills the calling shell (exit 144) | Kill by explicit PID |
| A 3D-ICE stack over ~366 k unknowns | Exits during "Preparing thermal data" with an **empty stderr**, after ~75 min | The exception now carries a size diagnosis; halve the grid with `--cell-um` |
| Parsing McPAT text output | `L2` is a colon-less header whose attributes sit at its own indent; `Integer ALUs (Count: 6 ):` breaks a `:`-split | Prefer the JSON's key structure to a text parser |
| Assuming a fix worked because one site stopped failing | `clipping_plan` is not the only place block temps become plannable — the sensitivity probe is another | Count the sites; a test pins the count at two |
| Re-running a control ladder on an array knob | `uniform_density_probe.py` has no array; `--array-coverage` cannot reach it and the flat-die ceiling cannot move | Coverage bounds the **array-assisted** ceiling; run `mr_comparison.py` arms |
| Writing `fill` where you mean coverage | `tile_grid`'s `fill` is a linear edge fraction: 0.5 covers a quarter | State coverage (areal) and let `fill_for_coverage` convert |
| A test on the node failing on a bug already fixed | NFS attribute cache served the old `.py`; the node ran the stale `.pyc` | Wait a minute and re-run; see §2.4 |
| Comparing a `dtnone` extractor run's Q with a recorded ladder | The scalar `dt_max` shaped the plan (sensitivity-weighted); without it the envelope is area-weighted and ~30 % dearer | Keep `--mr-dt-max 45` when comparing; `dtnone` is the curve-only regime, reported on its own |

---

## 6. Before you finish a session

1. `python -m pytest HotGauge/HotGauge -q` — **1050 passed, 1 skipped** as of 8 Sep (§P0.21, on node-06 in 4 min 39 s; 1042 after §P0.20, 1025 after §P0.19, 992 after §P0.18, 947 before). Do not run it
   with ~20 campaign workers active (it starves on NFS: 8 s of CPU in 17 min). At ~10 it is fine.
2. Update `docs/RESULTS_REGISTER.md` if a number moved — **including moving a claim to §2**.
3. Record any prediction you made, right or wrong, in `docs/PHASE0_CHECKLIST.md`. Four of five
   predictions in the last two sessions were wrong; writing them down first is the only reason the
   corrections were findable.
4. `git status --porcelain` — list files for the user to stage. **Never `git add .`**;
   `results/`, `snipersim/`, `McPAT/`, `spice_toolchain/` are gitignored build trees.
