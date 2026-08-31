# Phase 0 checklist — live state

Working state for the Phase 0 programme in `docs/EXECUTION_PLAN.md`. **Update this as work lands**;
it is what a new session reads first to find out where things stand. The plan says what to do and
why; this says what is done.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

Last updated: 29 August 2026, fifth session — **P0.7: the power-recovery reframing. The objective
now has a second axis (exergy, phi = 1 - T0/Th) and the book's three-zone template was tested:
40 W of removal on a 60.7 W die buys 1.24 K of gradient against the 150 K asked for, confirmed by
two independent methods to within 1.7x. Read docs/POWER_RECOVERY_PLAN.md first. Earlier, P0.5h: the book's three-zone template measured
against our own floorplans and leakage curve. The premise holds (34.6 % static, 89 % of it in L3)
but no floorplan here can hold the gradient — 3 000–6 300× too much boundary conductance — and
McPAT's 300–400 K domain excludes both of the template's zones. Earlier, P0.5g: one die per ISA at matched die area; the
peak block on EVERY die in this project turns out to be a mis-placed accounting figure, and the
absolute temperatures are optimistic by tens of kelvin. P0.5f: the ISA floorplans REBUILT on the
floorplan pack's published block areas, four defects in the first cut found and fixed, and the
one surviving phase-1 metric FAILS the rebuilt sweep (ρ +1.00 → +0.29/−0.06/−0.29). Read P0.5f
before quoting any floorplan-metric result.** Earlier: P0.1 and P0.2 complete; all twelve
`scripts/` batch scripts ported; P0.4 integrated with the gate RUN at 2/4; P0.5 catalogue re-run
FINISHED; P0.5b handbook figures and headline sections rebuilt.

---

## Environment

- Repo `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`, `source setup_environment.sh` first.
- Compute: slurm job **1389** on `node-06-8xv100` (96 CPU, 237 GB, TimeLimit UNLIMITED). Run
  everything through `scripts/on_node.sh 1389 <cmd>` with `OMP_NUM_THREADS=1`. If the allocation
  died, get a new one and use the new jobid (`squeue -u jbalma`).
- Test suite: `python -m pytest HotGauge/HotGauge -q` — **768 passed, 1 skipped** as of this line
  (645 at the start of the pack rebuild; +123 across P0.5f-P0.8). No toolchain needed; ~5.5 min.
- **`/tmp` on node-06 is a 2 GB tmpfs and is 100 % full** — 1.8 GB of it a stale
  `/tmp/catalogue_rerun_gi92jv0o` from the 26 Aug catalogue re-run, holding 3D-ICE working files
  and no result JSONs (those were harvested to `results/`). Anything writing to node-local `/tmp`
  fails with ENOSPC; write run directories under the repo on NFS instead.

## Settled decisions — do not relitigate

- **Extraction is never co-located.** The array is a die element directly above the silicon, in
  the grease's place. Cold plate on a direct-die package. `docs/EXECUTION_PLAN.md` §6.
- **Both arms share the sink**; only the 30 µm layer differs (GaAs pixels vs `THERMAL_GREASE`).
- **Active layer 200 µm below the cooled surface by default**, free parameter for thinning sweeps,
  identical in both arms when comparing.
- **Do not match pixel conductivity to grease to remove the confound** — use three arms. §6a.
- **Three arms everywhere**: `control` (grease, no cooling) → `array_idle` (GaAs, 0 W) →
  `array_on` (GaAs, budget). Laser term is measured against `array_idle`.
- **THE BASELINE CONFIGURATION, and it is narrow on purpose.** Direct die, copper heatsink on
  top, `StackSpec(package='direct_die')`. The **only** difference between arms is the 30 µm
  layer: `TIM` (thermal grease) in the control, `MR_PIXELS` (GaAs) in the photonic arm. **No lid,
  no solder, no copper IHS** — those are the struck-out layers in the handbook's stack figure.
  Anything reintroducing them is either the acceptance gate (see P0.4) or a mistake.
- **Extraction is a sensed, closed-loop, spatially-matched response.** The pixel layer senses the
  local temperature under each tile — physically, via the fluorescence spectrum — a controller
  reads that signal and steers both the *location* and the *intensity* of the laser response, so
  a tile's negative power approximately matches the power density of the silicon beneath it.
  Extraction accounted for globally but landed in the wrong place still produces plausible
  temperatures, so this is asserted, not assumed:
  `test_mr_array.py::TestExtractionTracksPowerDensity`.
- **Second ISA is both ARM and RISC-V**, not one. §4.
- **Tile pitch is a SWEPT VARIABLE, not a setting.** *(Corrected 26 Aug 2026; the 25 Aug entry
  saying "held at the device's 5 mm on every die" was wrong and came from a bad handoff, not from
  a decision anyone made.)* The ladder is **50 / 100 / 200 / 500 / 1000 / 2000 µm**
  (`PITCH_SWEEP_UM`). Granularity is one of the things this project exists to measure, and the
  two results already obtained exist only as comparisons *across* the ladder: the **ordering
  reverses with the workload** (coarse wins on a degenerate peak, fine on an isolated hotspot),
  and **coarse is low-variance while fine swings 3.6× on identical hardware**. Collapsing it to
  one value reports a curve as a point.
- **Studies that hold pitch fixed while sweeping something else use 500 µm** (`PITCH_UM`) — the
  back-catalogue value, so **arm deltas stay comparable to prior work**. Absolute temperatures
  already are not comparable because `--spreading` corrected the boundary; moving the pitch as
  well would leave nothing that could be compared with anything.
- **The device's 4–16 tiles is an ANNOTATION, not an operating point.** It is a tile *count*, and
  converting a count into an absolute pitch and applying it across dies is exactly the error
  above: 5 mm is **1 tile** on the 7-core die and **2** on the 34-core — and **38 of the 44
  `--cores` invocations in `scripts/` are 34-core**. Per die
  (`mr_array.device_pitch_range_um(area)`): 7-core 1.8–3.7 mm · 34-core 2.5–5.0 mm · 70-core
  3.5–7.0 mm · 128-core 4.7–9.3 mm · GA100 7.2–14.4 mm. On the 34-core workhorse that is
  **coarser than the ladder's 2000 µm top**, so the first-generation device sits just beyond the
  coarse end of the studied range. Report that to the device roadmap; do not run the catalogue
  there.
- `ArrayWiring` warns and sets `.degenerate` below **4 tiles** (`MIN_MEANINGFUL_TILES`), raised
  from 1 — the 2-tile 34-core case ran silently under the old threshold.

---

## P0.1 — Two dies through the session cache  `[x]` DONE 25 Aug 2026

*Was blocking everything by 169×.* Plan: `docs/EXECUTION_PLAN.md` §3 / P0.1.

- [x] `stack_floorplans(stack_file)` returns `(die_instance, flp_path)` in **power-vector order**
- [x] **Order established from the 3D-ICE source and then verified empirically**: the wire order is
      the *reverse* of the file's declaration order. `power_grid_fill` walks the stack element list
      backwards indexing by physical `Offset` (`power_grid.c:180`) and `insert_power_values`
      ascends `layer = 0..NLayers` (`power_grid.c:653`), so the vector runs bottom-up —
      **processor blocks first, tiles second**
- [x] `element_names()` concatenates across dies in that order
- [x] `temperature_names()` added — temperatures do **not** share the power order. They come back
      per inspection point, in `output:` section order (`3D-ICE-Server.c`, `TDICE_SEND_OUTPUT`).
      With one die the two coincided, which is why zipping worked until now
- [x] Name-collision guard between tile names and processor block names
- [x] `matrix_fingerprint` hashes every powered die's geometry; tile *power* still does not invalidate
- [x] Test: two-die server vs one-shot Emulator with an asymmetric pattern —
      **max |dT| = 5.1e-4 K across a 121 K field**. `test_two_die_server_matches_oneshot_emulator_by_name`
- [x] Dropped the `NotImplementedError`; replaced its test with one asserting construction succeeds,
      plus one asserting the *transient* refusal was not lifted by accident
- [x] **Found and fixed a silent-inertness bug on the newly-enabled path.** The session branch sent
      only processor powers; `solve_named` zero-fills absent elements, so the array would have been
      present and removed nothing — a wrong answer with no error. Factored out as
      `ICEThermalSolver.session_powers()` with four tests
- [x] **Fixed a pre-existing test-isolation trap**: `test_startup_timeout_...` calls
      `importlib.reload`, which rebinds every class, so `pytest.raises(ICEServerError)` in any
      later test silently stopped matching. `_resync_module_names()` now restores them
- [x] Session memory measured — `docs/evidence/session_memory.json`

**Measured:** 34-core 2.83 GB peak / 67.8 s factorise / 0.385 s solve → ~85 sessions fit, so
**CPU-bound, use the whole node**. 128-core 14.4 GB / 722.6 s / 1.916 s → 16 sessions,
**memory-bound**. Peak RSS is ~1.3× steady RSS; size on peak or the node over-subscribes.

## P0.2 — Planner emits tile powers  `[x]` DONE 26 Aug 2026

- [x] `CoolingApplication` — one strategy object with the two placements, threaded through all
      **five** application sites in the planner (baseline loop + four in the envelope descent)
- [x] `run_mr_clipping(..., tiles=, tile_blocks=, set_mr_powers=)`; omitting all three keeps the
      legacy path. A half-specified array is refused rather than computing a plan and never
      applying it
- [x] Every result stamps `placement` (`in_source_layer` | `array_above`) and `tile_plan`.
      Done in a thin wrapper because the loop has **thirteen** exits and one of them would
      eventually be missed
- [x] Projection conserves watts — checked inside the applier on every call, not just in drivers
- [x] Acceptance: tile powers sum to −W within 1e-3
- [x] **Spatial matching preserved and pinned.** `project_plan_to_tiles` splits each block's
      removal across the tiles above it *in proportion to overlap area*, so removal density tracks
      power density exactly (ratio spread 1.0 to 1e-6 across a 1:2:4:8 density map). The coarse-
      tile penalty is preserved rather than papered over: one tile spanning two blocks cools both,
      which is the geometric cost the tile-pitch study measures
- [x] The array stays matched to the **die** footprint, never the cold plate — asserted
- [x] **`examples/mr_comparison.py` wired.** `--arms control array_idle array_on`, `--stack auto`
      builds a direct-die stack per arm (30 µm grease for the control, 30 µm array otherwise,
      nothing else different), plus `--pitch-um`, `--burial-um`, `--mr-material`, `--cell-um`.
      Every row stamps `arm`, `placement`, `n_tiles`, `pitch_um` and `stack_spec`. Back-compatible
      `nomr`/`mr` aliases kept so the summarisers keep working while both generations are on disk
- [x] **The printed summary reports the two terms separately** — passive (grease→GaAs) and laser
      (idle→on) — and attributes a runaway rescue to whichever arm actually achieved it.
      Collapsing them into one "MR delta" is the confound the arms exist to remove
- [x] **Verified end to end on node-06** — `docs/evidence/three_arm_first_runs.json`
- [x] **All six planner drivers ported**: `mr_comparison`, `mr_clipping_study`,
      `hybrid_cooling_optimizer`, `mr_plan_probe`, `cop_breakeven`, `accelerator_study`.
      Each gains `--pitch-um` and `--no-array`
- [x] **The wiring is factored into `mr_array.ArrayWiring`** rather than repeated six times.
      It owns the tile grid, the tile floorplan on disk, and the plan that moves between solves,
      and exposes `solver_kwargs()` / `planner_kwargs()`. Both bugs found wiring the first driver
      would otherwise have been re-introduced five more times
- [x] **Placement derives from the STACK, not from a flag** — `wiring_for_stack()`. Both
      directions of disagreement are silent: tiles wired against a single-die stack compute a plan
      that lands nowhere, and an array stack left unwired carries an inert slab that only adds
      resistance. Asking for an array the stack cannot carry is now an error with the fix in the
      message, not a silent downgrade to the legacy upper bound
- [x] `spec:` keys `mr_powered`, `sink_in_stack`, `package_in_boundary` reachable from every
      `--stack` driver
- [x] **All twelve batch scripts in `scripts/` ported**, 26 Aug 2026. They never named a stack —
      they inherited `--stack skylake`, the historical *lidded* template — so the fix is not only
      "add an array spec": the whole catalogue was being solved on the wrong package.
      `scripts/array_config.sh` holds the stacks, the pitch and the argument groups in **one
      place** (the ArrayWiring argument, applied to shell), and the mixed-driver scripts inject
      it **by driver** through a `stack_args_for()` case, so an unconfigured driver is REFUSED
      rather than run on whatever default it ships
- [x] **`accel_mr_batch.sh` and `dtmax_batch.sh` restructured to three arms.**
      `accelerator_study` takes one stack per invocation, so three arms is three invocations —
      `run3`. In `dtmax_batch` the control and idle arms run *once per configuration* rather than
      once per dt_max, and the dt_max prediction is now measured against `array_idle`: against
      the grease control it would fold a 14× conductivity step into the dt_max budget and appear
      to over-deliver at every point, which is the kind of agreement that is worse than a
      disagreement
- [x] **`overnight3_study.sh`'s seed path is now checked, not assumed.** It copied
      `results/cliff_verified` points as "same code, same arguments, same machine"; they predate
      the array. A seed must now carry this run's array stack *and* pitch in its JSON or the
      point is re-run and the reason logged
- [x] Dry-run harness: **238 invocations across 12 scripts validated against the real argparse** —
      every one names a stack, every planner run has an array die or `--no-array`, no unknown
      flags, pitch 5000 µm everywhere
- [x] **Acceptance: the legacy path reproduces an old point BIT-IDENTICALLY.**
      `docs/evidence/legacy_reproduction.json`. `margin2_T98_d1.15` re-run as
      `--stack skylake --no-array`: `peak_C` 99.86638793945315 both times, and
      `gflops`, `gflops_per_total_W`, `heat_removed_W`, `p_mr_net_W`, `p_chip_W`, `p_cool_W`,
      `n_targets`, `peak_block` identical to the last digit. The **residual trajectory** matches
      too (iter 49 21.9424→24.6929 K, iter 52 23.7690→26.7467, iter 105 18.5093→20.8400, iter
      124 18.0042→20.2718) — the same path to the runaway, not just the same verdict. The only
      difference is the new row's `placement: in_source_layer` where the old had no stamp
- [x] **Acceptance: burial depth is live through the planner.**
      `docs/evidence/burial_depth_through_planner.json`, new driver
      `examples/burial_depth_planner_probe.py`. Same 3 W, same block, byte-identical tile plan at
      every depth; 360 → 20 µm moves what it buys by **+44.1 % in the array and −7.0 % in the
      source layer**. The separation is the test and it is unambiguous

### The 67 % is not a die-wide constant — read this before quoting it

`CODESIGN_PLAN.md` §1 quotes "thinning 360 → 20 µm improves what a fixed 3 W buys by 67 %" as a
design constant. It is not one. Two things move it several-fold:

* **Block maximum against block average.** `mr_placement_probe` writes its own `.stk` with
  `Tflp(..., maximum, final)`. The production path is `ICE.DIE_TFLP_OUTPUT`, which is
  **`average`** — so every catalogue row, and every number the planner ranks on, is a block
  *mean*. On the same block at the same depth the two differ by 2.6 K (81.24 max vs 78.62 avg).
* **Which block.** On averages the hottest block is `L2_4`, not `L3_4`. The direct probe re-run
  on `L2_4` gives **+11.0 %** against +67.2 % on `L3_4` —
  `docs/evidence/mr_placement_burial_depth_L2.json`.

What survives all three measurements is the claim the acceptance check exists for: **array
placement is strongly burial-sensitive, source placement is not.** Quote the magnitude with the
block and the reduction stated, or quote the separation.

### Found while porting — three real defects, all silent

- [x] **`clock_headroom.py` was never ported and nobody had noticed.** It is a *seventh* planner
      driver (the checklist said six), it calls `run_mr_clipping`, and with no tiles it took the
      legacy in-source-layer path silently. Two batch scripts drive it with `--mr`. Now three-arm
      with `--pitch-um` / `--burial-um` / `--cell-um` / `--mr-material` / `--no-array`, and it
      reports the **passive and laser terms separately** — it produces a *sustainable clock*, so
      "MR buys +0.4 GHz" was the single worst place in the project to be booking a packaging
      change to the laser
- [x] **`clock_headroom`'s `distributed` arm applied cooling to the trace directly**, so under an
      array stack it would have been legacy placement reported as array. Now goes through
      `CoolingApplication`, the same object `run_mr_clipping` uses, so the two cannot drift
- [x] **`mr_comparison.py` built `ArrayWiring` directly instead of `wiring_for_stack`**, so
      `--stack skylake --arms array_on` would have computed a plan and landed it nowhere. Now
      derives placement from the stack like the other six, and gained `--no-array`
- [x] **`ArrayWiring` wrote a RELATIVE floorplan path.** `ExecutableJob` fills the template inside
      a multiprocessing worker whose cwd is the HotGauge package dir, so `--out-dir results/x`
      resolved to `HotGauge/HotGauge/script_runner/results/x/MR.flp`. Every existing driver
      happened to pass an absolute path. Now absolute, with a test
- [x] **`mr_clipping_study`, `hybrid_cooling_optimizer` and `mr_plan_probe` had no `--cell-um`**,
      so their tile grid snapped to 50 µm regardless of the `cell=` in the stack spec — tiles on
      a finer grid than the solver's come back overlapping after quantisation. All three now take
      it and pass it to the wiring

### The stale-plan guard — the highest-value thing to come out of this

The burial-depth probe's first run reported **3.000 W removed and +0.0000 K of cooling**, at every
depth, with no error. Cause: the driver built one `ICEThermalSolver` and handed it to
`run_mr_clipping`. `solver_kwargs()` snapshots the tile powers and the solver renders them into
the array's floorplan **at construction**, so every iteration re-solved the plan the wiring held
*before the planner ran* — all zeros. The projection conserved its watts, the accounting reported
the full budget, and the field was the uncooled one.

`ArrayWiring` now refuses to replace a plan no solver ever read
(`_assert_last_plan_was_solved`, five tests). It is a two-line mistake to make and it has no other
symptom.

### First result out of the three arms, and it matters

7-core skylake, 10 nm, 2000 µm pitch, 200 µm burial, 88 CFM. **Smoke settings** (`--mr-iter 2-3`,
`--max-iter 12-20`) — wiring proof, not production numbers.

| density | control (grease) | array idle (0 W) | array on |
|---|---|---|---|
| 0.6 W/mm² | 59.8 °C | 49.6 °C | 49.6 °C, 0 W removed |
| 1.6 W/mm² | **RUNAWAY** | 106.0 °C | 101.0 °C, 2.76 W removed, +11.8% throughput |

At low density the laser term is **exactly zero** — correctly, since nothing is above target — and
all 10.2 K is passive. At high density **the unpowered array alone rescues a die that has no
steady state under grease**: swapping 30 µm of TIM for 30 µm of GaAs is sufficient on its own,
and the laser then adds 4.9 K and +11.8% throughput on top.

Under the old two-arm scheme both of these would have been reported as MR results, crediting the
light with what the material substitution achieved. The confound fired on the first real run.

### Two bugs the existing guards caught during the wiring

Both would have produced plausible, wrong numbers rather than errors:

* the `spec:` string set `mr_layer` but not `mr_powered`, so the array rendered as an **inert slab
  with no tile floorplan** — caught by `session_powers()`'s "the array would silently remove
  nothing" check, which was added for exactly this. `mr_powered` now defaults to true
* the driver converted plan→stack sign a second time after `CoolingApplication` had already done
  it, **flipping removal into heating** — caught by `fill_mr_flp_template()`'s sign guard

**Note on `estimate_sensitivity`:** the execution plan said to make it perturb a tile. On
inspection that is wrong and it should stay per-block. The planner's decision variable is watts
requested *at a block*; the projection onto tiles happens downstream, so `dT_block/dW_requested`
already includes the projection, the burial depth and the tile geometry. Measuring per tile would
describe a quantity the planner cannot act on. `docs/EXECUTION_PLAN.md` P0.2 item 4 is superseded
by this note.

## P0.3 — Per-tile `dt_max` / `h_max`  `[ ]`  **`[!]` PROMOTED 30 Aug — now the top Phase 0 item**

**`[!]` The shipped envelope is stale by 4–40×, and it is the binding constraint in the rescue
results.** `DEFAULT_H_MAX_W_PER_MM2 = 250.0` comes from Draft_5 §6.4.1 — the Yb:YLF era. v91
Table 8.2 gives **10³–10⁴ W/mm²** for *both* current platforms (SMILES-R640-in-polymer and
GaAs/GaInP). Figure 1.6 puts hot-spot demand at the same 10³–10⁴ W/mm², so **supply now matches
demand where it previously fell 4–40× short** — that is the single largest change v91 makes to
anything this project has measured.

This is not a refinement. Test 6c's own solver diagnostic on the measured rescue reads *"envelope
insufficient: dt_max binds. The stage lifted the peak the full 45.0 K it is capable of and the
target needs 103.2 K. More iterations cannot help and neither can a better COP — this is the
device's temperature lift, not its cost."* The binding constraint there was the **envelope**, and
the envelope is the stale number.

- [ ] **Refresh `DEFAULT_H_MAX_W_PER_MM2` to the v91 platform range**, keeping 250.0 as
      `LEGACY_H_MAX_W_PER_MM2_DRAFT5` so every recorded result still reproduces
- [ ] **`dt_max` needs a v91 or device-team source.** 45.0 K is also Draft_5 §6.4.1 and no v91
      replacement was found on a first pass. Do not invent one — this is an ask, not a lookup.
- [ ] **Re-run the affected sweeps**: the rescue anchor, Tests 6c–6e, the tile-pitch ladder, and
      the clock/turbo studies. Expect the "MR LOSES / chiller wins" verdicts to move, possibly
      to reverse — they were computed against an actuator 4–40× too weak.
- [ ] `ZONE_EXTRACTORS_V91` answers the standing open question **per zone**: cold tiles get
      Yb:YLF/Yb:silica, hot compute Ho³⁺/Tm³⁺ fluorides, >600 K SiC:Er or GaN:Yb — so `h_max` and
      `dt_max` are properties of the *zone's material*, not one global constant.

**`[+]` LANDED 30 Aug — the re-run at the refreshed envelope.** `scripts/rescue_rerun_34core.sh`,
`docs/evidence/rescue_envelope_refresh.json`. 34-core, 88 CFM, target 92 °C, canonical `$ARM_ARGS`
geometry, `--recovery-at-junction`.

| density | recorded Q / elec | re-run Q / elec | Q reduction | matched-eff elec |
|---|---|---|---|---|
| 1.10 | 26.8 W / 46.6 W | 10.4 W / 6.3 W | **2.58×** | 25.6 W (**1.82×** less) |
| 1.15 | 42.1 W / 72.9 W | 18.3 W / 11.1 W | **2.30×** | 45.1 W (**1.62×** less) |
| 1.18 | 44.9 W / 77.8 W | 22.9 W / 14.0 W | **1.96×** | 56.5 W (**1.38×** less) |

- **The array rescues a die with no steady state; the unpowered array does not.** Control and
  `array_idle` run away at all three densities; `array_on` holds 93.9–94.0 °C on a minimum plan
  bracketed by bisection (`mr_plan_is_minimum`, `mr_plan_holds_target` both true, 1126 targets).
- **`net_generating: False`** — the second-law correction is live in the pipeline.
- **`[!]` The raw electrical columns are not like-for-like**: the recorded run used
  `LEGACY_ENVELOPE` (cop 0.14), the re-run the shipped defaults (cop 0.272). The matched-efficiency
  column re-prices the re-run at the recorded preset, isolating the envelope effect from the
  efficiency change and from the second-law correction.
- **`[!]` The chiller comparison must be re-derived.** The control arm no longer reaches a steady
  state, so there is no unaided temperature to measure a required chill depth against. Tests
  6c–6e's chiller numbers are stale in a way the constants refresh alone does not fix.
- **`[!]` Three misconfigured attempts preceded this one** — wrong driver (`mr_clipping_study`, the
  8-core linpack configuration), then a power point with no steady state, then hand-rolled geometry
  omitting `--spreading` and the burial depth, which left the die 49 K cooler than the recorded
  control and the array idle. The fix is structural: source `array_config.sh` for `$ARM_ARGS`
  rather than reconstructing it. That instruction is now in the script header.

*This is the controller's actuator limit: `h_max` is the intensity ceiling per tile and `dt_max`
the ΔT it may pull. Both are per tile because the tile is what the laser addresses.*
`ICEServerSession.temperature_names()` (added in P0.1) can now read MR-die temperatures, which is
the sensing signal the real controller uses — so a per-tile sensed loop is reachable.

- [ ] Clamp on tile area and tile ΔT
- [ ] Test: fine and coarse arrays over the same die get the same total envelope, different caps
- [ ] **Open question for the device team**: does `dt_max` bound a tile or a block?

## P0.4 — Spreader overhang + acceptance gate  `[~]` physics + integration landed, gate 2/4

**Decided 25 Aug 2026: apply the overhang generally**, to every stack rather than only the lidded
gate points. Must still precede P0.5 or the re-run happens twice.

**Route changed, and this is the important part.** The plan assumed 3D-ICE's pluggable spreader.
That route is closed twice over: the grammar's conventional `top heat sink` accepts *only* a heat
transfer coefficient and a temperature (`stack_description_parser.y`, rule `topsink`) so an
overhang cannot be declared on it; and the pluggable sink, which does have `spreader length/width/
height`, cannot be steady-solved *and* depends on the FMU plugins, which are broken in this build
(they load, run, and reject almost no heat). Fixing `system_matrix.c` would still leave the plugin
unreliable.

Taken instead: fold the base into the boundary resistance analytically.

- [x] `spreading_resistance_K_per_W()` — Lee/Song/Moran/Yovanovich constriction correlation,
      source-to-ambient, in `cooling_spec.py`
- [x] **Collapses exactly to the 1-D answer when the base equals the die** (ratio 1.0000) — a
      calibration-free check that no fitted constant can hide behind
- [x] **Breaks the 1/area scaling**: 9.08× the die area now gives 2.35× the resistance, not 9.08×
- [x] SimScale geometry read off `docs/SimScale/Scripts` and recorded with provenance —
      20 mm chip / 40×60 mm base (ratio 2.45) and 10 mm chip / 25×50 mm base (ratio 3.54)
- [x] `base_area_from_footprint()` — a **fixed absolute** cold-plate footprint, not a ratio.
      The two SimScale models disagree on ratio precisely because the base is near-constant while
      the die is not; a fixed ratio would reintroduce 1/area and the gate would still fail
- [x] Interior optimum in base area pinned as intended behaviour, not a bug: a wide thin plate
      spreads badly (τ = t/b falls), so you cannot rescue a small die with a bigger cold plate
      without also making it thicker
- [x] **A dropped `1/sqrt(pi)` on the spreading term, caught and fixed.** The `base == die` test
      cannot see it (that term vanishes at ε=1); the half-space limit can. Now ψ → 0.5635 against
      Lee's 0.5642, and the correlation is ~18% conservative versus the exact isoflux 0.4789 —
      pinned in both directions, because the error must never go optimistic
- [x] `SpreadingSink` in `sink_models.py` — wraps a convective sink with the conduction into an
      overhanging base, presented as one HTC over the die footprint
- [x] `StackSpec(sink_in_stack=False)` — drops the cold-plate slab
- [x] `StackSpec(package_in_boundary=True)` — the wider correction. On a **lidded** part the
      dominant spreader is the IHS, not the sink; a 3 mm copper lid as a die-width column is most
      of why a small part came out too hot. Keeps only genuinely die-sized layers (die attach) and
      exposes `boundary_base()` / `boundary_series_layers()`
- [x] `external_r_for_spreading_total()` — inverts the boundary. The gate works backwards from a
      published figure, and the remainder after the stack now contains spreading and the layers
      above the base, so solving the cooler directly against it would demand a cooler better than
      the target by exactly the spreading resistance
- [x] Feasibility established — `docs/evidence/spreading_budget.json`

**Where it stands.** The Ryzen package was **0.4675 K/W against a published 0.3962** — the package
alone exceeded the entire junction-to-ambient budget, leaving a negative share for the cooler.
That is impossible, not mis-tuned, and it is why two of four points could not be reached at any
flow. It is now `0.1596` of stack plus a `0.2366` boundary budget, and **all four points are
feasible**.

**Sizing the spreading base — a distinction that matters.** Use the **lid footprint** (fixed,
~1825 mm², which is also where the SimScale bases land), *not* the cooler class. Cooler class
sizes the **fins**, which is right for convection and wrong for spreading: a 3 mm copper lid
cannot spread to a tower cooler's 118 mm extent. Using the fin extent demanded a 0.0028 K/W cooler
for Ryzen, which is not a thing that exists.

- [x] **Two-stage spreading built** — `staged_spreading_resistance_K_per_W`, die → lid → cold
      plate, any number of stages, each with its own contact resistance charged over its own area.
      Reduces *exactly* to the single-stage function for one stage, which in turn reduces exactly
      to `t/(kA) + 1/(hA)` when base == die
- [x] **It did not close the gap — it widened it slightly, and that is correct.** At a fixed
      external resistance another interface can only add. A second stage pays for itself through
      the larger area the *convection* then acts over, which is a property of the cooler rather
      than of the spreading model. My earlier hypothesis was wrong and is recorded as such

### Scope correction, 25 Aug 2026 — read this before continuing P0.4

The plan bundles "spreader overhang" with "acceptance gate to 4/4" as one item, so the overhang
work went after the gate — and the gate's reference points (H100, Ryzen) are **lidded** parts.
That pulled the analysis into IHS, die-attach solder and two-stage spreading, none of which exist
in the baseline configuration above. **That work is gate-only and must not leak into the
baseline.**

The part that *is* in scope landed and is what matters:

- [x] **The overhang applied to the direct-die stack** — `StackSpec(sink_in_stack=False)` plus
      `SpreadingSink`. Evidence: `docs/evidence/direct_die_overhang.json`

At a **fixed physical cooler** (h = 2000 W/(m²K), the same in every column) on the baseline stack:

| die | as shipped (slab at die footprint) | with the overhang |
|---|---|---|
| skylake 7-core, 53 mm² | 9.70 K/W | 0.84 K/W |
| skylake 34-core, 101 mm² | 5.10 K/W | 0.65 K/W |
| GA100, 826 mm² | 0.62 K/W | 0.32 K/W |
| **spread across 15.5× die area** | **15.5×** | **2.6×** |

The shipped model tracks 1/area almost exactly, because the 2 mm base is a stack layer at the die
footprint *and* 3D-ICE applies the convective boundary over that same footprint — at h = 2000 the
convection alone is 9.40 K/W of the 9.70. That is the grey sink base in the handbook figure, and
it dominated everything else in the stack.

**The grease-vs-array delta is identical in both models** (0.1307 K/W on the 7-core die either
way), because the 30 µm layer sits at the die footprint regardless. The overhang fixes the
absolute scale and the die-size dependence; it does not move the photonic result. Worth keeping
that separation visible — the cooling claim does not rest on the sink model.

### The gate is being rebuilt on direct-die hardware — decided 25 Aug 2026

The open question ("every reference point is a lidded part") is answered: **direct-die reference
hardware is in house.** `published_reference.DIRECT_DIE_HARDWARE`.

* **Framework Laptop 13 mainboards** — lidless mobile CPUs, thermal-camera accessible.
  AMD Ryzen 5 7640U · Ryzen AI 5 340 · Intel i7-1185G7 · i7-8650U · i7-1260P · Core Ultra 5 125H ·
  **DC-ROMA RISC-V RVA23**. 12–115 W. Two x86 vendors *and* a RISC-V part in the same chassis and
  the same thermal envelope — a cross-ISA comparison with the cooling held fixed, not just a set
  of validation points. No ARM part in house; Framework ships them, so procurable not blocked.
* **V100 SXM2** — bare GV100 under a cold plate, the direct-die HPC analogue of the accelerator
  floorplan already modelled. node-06 carries eight. **Not in the current allocation**
  (`TRES=cpu=96`, no gres), so an operating point needs a GPU request.

**A thermal camera changes what a gate point is.** A published number validates one scalar. An IR
map validates the **spatial field** — hotspot location, the peak-to-runner-up gap that decides
tile pitch, the plateau width that sizes a plan. That is what this project actually predicts, and
it is a far stronger claim for a licensee than "the peak landed in a range".

Two caveats that shape the measurement, recorded because they change what the data can support:

* **Imaging the die means the cooler is off**, so the boundary under the camera is not the one in
  service. Not fatal, possibly preferable — a bare die under natural convection is a *simpler*
  boundary to model, and the field is then set almost entirely by the floorplan and power map,
  which is exactly what we want to test. Model what was measured, not what ships.
* **Bare silicon is a poor IR target** — emissivity ~0.6–0.7, varying with doping, finish and
  angle. Without a high-emissivity coating or in-frame reference spots, relative structure
  survives but absolute values do not.

- [x] Inventory recorded, with what each entry still needs before it can be a gate point
- [x] Guarded: `DIRECT_DIE_HARDWARE` cannot leak into `all_thermal_points()` unmeasured
- [x] **Die geometry captured from `docs/demo_hw_slides.pdf`** → `published_reference.DIE_GEOMETRY`
      · Ryzen AI 5 340 **16.0 × 12.5 mm = 200 mm²**, with a block-level floorplan sketch
      (P-cores / E-cores / Cache+AI / Graphics / IO) — enough to build a floorplan from
      · Core Ultra 5 125H package 42 × 20 mm, compute region 23 × 11 mm, and a **concrete hot
      cluster**: four 8 W blocks of 2 × 1 mm on a 4.3 mm pitch inside an 8.9 × 8.3 mm cluster
      · Ryzen 9 AI HX 370 19.6 × 12.3 mm
- [x] **Measured 125H power sweep captured** → `CORE_ULTRA_125H_POWER`. Eight operating points
      across SSE / AVX / AVX2 / AVX-512 and core counts. **All-core all-thread draws 25 W package
      against a 115 W ceiling** — the part is power-management-limited long before it is thermally
      limited, which the §9 ladder must not assume away
- [x] **Nested power density captured** → `HX370_POWER_DENSITY`. The same 1.75 W is 1.05 W/mm²
      over a core and **8.33 W/mm² at 0.21 mm²** — a 7.9× range *inside one core*. This is the
      measured form of the §4 argument: concentration is what an area cooler responds to, and this
      is the range a tile array has to resolve
- [x] Demo stack recorded (`DEMO_STACK`): Cu heatsink / 500 µm Si / 2 mm PCB at 0.6 W/mK / TEC.
      **Not** the baseline stack — a validation run must model what was built. The near-insulating
      board means essentially all heat leaves upward, which makes the top-side comparison cleaner
      than a socketed desktop part
- [ ] Die area for the remaining Batch 1 parts (7640U, 1185G7, 8650U, 1260P, DC-ROMA)
- [ ] A measured operating point each: power, ambient, temperature, cooling configuration
- [ ] Emissivity calibration protocol settled before any absolute number is used
- [x] V100 idle baseline measured on node-06 under allocation 1382: **41 °C at 42.4 W**,
      300 W limit, SM 135 MHz idle / 1530 max, stable to ±0.5 W over a minute
- [ ] V100 loaded points — **blocked on a load generator**. No CUDA toolkit, torch, cupy or numba
      in the env, so nothing can drive the GPU. Installing one modifies the user's environment,
      so it needs a decision. Two points at different powers give R_th from the *slope*, which
      does not require knowing ambient
- [ ] Retire or keep the lidded points once direct-die ones exist — they validate a package the
      device does not have, so they are a generalisation check at best

### Gate-only, parked: the lidded path

`package_in_boundary`, two-stage spreading and the solder analysis exist and are tested. They
serve **only** the lidded published points and must not leak into the baseline config.

### Gate-only: the gap is in the package inputs, not the spreading model

Evaluated against **typical real coolers** (0.12 K/W tower, 0.05 datacenter module) rather than
inverting for whatever the budget allows, the model overshoots every point — Ryzen air by 0.217,
H100 air by 0.042. Decomposing the 0.3962 K/W Ryzen budget:

| term | K/W | share |
|---|---|---|
| **SOLDER, 200 µm at k=25** | **0.1127** | **28.4%** |
| die → lid spreading (realistic Bi) | 0.1952 | 49% |
| lid → plate spreading | 0.1340 | 34% |
| silicon die | 0.0468 | 12% |
| grease over lid | 0.0041 | 1% |

Solder alone is the largest single package term — larger than either spreading stage — and it is
**28% of the entire published junction-to-ambient budget** for a die-attach layer.

Sensitivity, one unvalidated input at a time (`docs/evidence/staged_spreading.json`):

| change | Δ K/W |
|---|---|
| solder 200 → 80 µm (real Zen4 die attach) | −0.068 |
| solder k 25 → 82 (bulk indium) | −0.078 |
| cold plate 2 → 6 mm copper | −0.081 |
| cold plate k 300 → 2000 (heatpipes) | −0.114 |
| IHS 3 → 4 mm | −0.029 |
| **all four** | **−0.228 → lands at 0.3850 vs published 0.3962** |

- [x] **The four inputs, examined 26 Aug 2026 — and the task turned out to be a different one.**
      `docs/evidence/package_input_provenance.json`. **None of them has a reference to be
      validated against.** They are not measurements of any gate part: they are the upstream
      Tufts `skylake.stk` numbers, inherited layer-for-layer so a default lidded build reproduces
      that file, and `skylake.stk` cites nothing. So a generic ~2015 desktop CPU package is being
      applied to a 2022 Hopper module and a 2023 Zen4 chiplet, and nobody had asked whether it
      fits. Per input:
      · **solder k = 25** — *partially settled from the code alone, and it is an internal
        inconsistency rather than a wrong number.* The material is "indium solder die attach";
        bulk indium is ~82 W/(m·K), 3.3× higher. 25 over 200 µm is a **lumped joint** (metal +
        both interfaces + voids), in which case the 200 µm is a fitted equivalent thickness and
        neither number may be moved alone; 82 is the **bulk**, in which case two interface
        resistances are missing from the model entirely. The stack has no interfacial resistance
        anywhere, which points to the lumped reading — and the sensitivity study moves k to 82 as
        though it were bulk, which is only legitimate under the other one
      · **solder 200 µm** — no source, here or for the proposed 80 µm; and not independent of the
        above
      · **cold plate 2 mm** — generic, and it now matters *more*: with the overhang it enters the
        constriction correlation as τ = t/b, so it is a shape parameter, not a small series term
      · **cold plate k 300 → 2000** — **a category error, do not adopt at any value.** 2000 is an
        *axial* effective conductivity along a heat pipe; the spreading correlation assumes an
        isotropic disc. The Thermalright Peerless Assassin the Ryzen points name really is a
        direct-touch heatpipe cooler, so the geometry question is real — but it needs an
        anisotropic or multi-stage treatment, which `staged_spreading` already supports
- [x] **Nothing was changed for the gate run.** `staged_spreading.json` says moving all four
      favourably is worth −0.228 K/W and lands Ryzen at 0.385 against a published 0.396. That is
      precisely why it was not done
- [x] **The overhang is reachable from the drivers**, 26 Aug 2026. It was not: the physics landed
      in `sink_models.py` / `cooling_spec.py` and `StackSpec` learned to hand its base out, but
      **nothing connected them** — `grep -rn SpreadingSink examples/ scripts/` returned nothing,
      so every study still solved against a 2 mm slab at the die footprint. Now
      `sink_models.spreading_sink_for_stack()` is the single join, `die_stack.stack_for_spreading()`
      amends a spec to `sink_in_stack=0`, and **eight drivers take `--spreading` / `--base-mm2`**:
      `mr_comparison`, `clock_headroom`, `accelerator_study`, `cop_breakeven`, `mr_clipping_study`,
      `hybrid_cooling_optimizer`, `mr_plan_probe`, `thermal_tiers`
- [x] **Both silent failures are refused with the fix named**: a stack that still carries its sink
      slab (which would count the base twice — no error, the part just runs hot) and a plain
      template name (no base geometry to read; guessing would invent a package)
- [x] **Reproduces `direct_die_overhang.json` to the digit** through the wired path —
      all six budgets and all three arm deltas, `test_sink_models.py::
      TestSpreadingReproducesTheOverhangEvidence`. The evidence was computed by a different route
      before the wiring existed, so this is a real cross-check rather than a restatement
- [x] Wire `examples/validate_published.py` — now takes `--spreading`, inverts the boundary with
      `external_r_for_spreading_total`, sizes the cooler over the **base** it is bolted to rather
      than the die, and wraps the **probe** sink identically so the resistance
      `measure_package_resistance` subtracts is the one the stack was rendered with

### A convention bug in `SpreadingSink`, found by wiring it up

The first wired check gave **15.2×** across the die-size range where the evidence says 2.6× — the
slab it replaces gives 15.5×, so the overhang was buying *nothing*. Nothing errored.

`SpreadingSink` wraps a cooler, and two conventions meet there:

* a sink quoting `r_th_K_per_W` (`ThermalResistanceSink`, `CoolingSpecSink`, `BaffledFinSink`)
  means a **whole-cooler** resistance — "a 0.12 K/W tower" — already absolute;
* a plain `SinkModel` is a **coefficient**, and a coefficient means nothing without an area.

`_external_r_K_per_W` evaluated the coefficient case over the **die** footprint. That says "an
1825 mm² cold plate that only exchanges heat over the 53 mm² directly above the die", and because
`total_resistance_K_per_W` converts back with `h_base = 1/(r_ext · base_area)`, the two area
factors cancel exactly. Fixed to use the base area, which is what the evidence file states
outright — "the die spreads into an 1825 mm² copper base and **the cooler acts over THAT area**".
Pinned by `test_the_coefficient_is_applied_over_the_base_not_the_die`.

### What `--spreading` does to the catalogue, before it is run

`docs/evidence/spreading_boundary_by_die.json`. `BaffledFinSink` — the `--cfm` sink almost every
catalogue point uses — presents the SimScale **convective** resistance only, deliberately, because
3D-ICE resolves spreading in the die. But the die is 240 µm of silicon: it cannot spread a 28 mm²
source out to a cold plate. That spreading happens in the **base**, which the slab model rendered
as a die-width column, so the path was simply **absent**. Adding it is not a double count.

At 88 CFM the boundary the die sees goes from a flat 0.0764 K/W on every die to:

| die | mm² | slab K/W | overhang K/W | × |
|---|---|---|---|---|
| skylake 7nm 7-core | 28.4 | 0.0764 | 0.5526 | 7.2 |
| skylake 7nm 34-core | 101.2 | 0.0764 | 0.3247 | 4.3 |
| skylake 7nm 128-core | 347.6 | 0.0764 | 0.1726 | 2.3 |
| GA100 | 826.0 | 0.0764 | 0.1077 | 1.4 |

**Small dies get hotter, substantially.** Measured end to end: the 7-core control arm at
1.0 W/mm² moved **74.4 → 95.7 °C**. Every cliff position, rescue threshold and sustainable clock
in the catalogue moves with it. That is the correction working — a fitted whole-cooler resistance
applied at a 28 mm² die footprint with no constriction was never a physical boundary — but it
means the re-run's numbers are not comparable to the back catalogue's on absolute temperature,
only on the arm deltas.
- [x] **Gate RUN, 26 Aug 2026, at the model's existing inputs — `2 of 4`.**
      `docs/evidence/acceptance_gate_spreading.json`

| point | published | R_pkg | R_ext | predicted | verdict |
|---|---|---|---|---|---|
| `H100_AIR` | 54–72 °C | 0.0542 | 0.0265 | **61.0 °C** | **PASS** |
| `RYZEN_7500F_LIQUID` | 70–71 °C | 0.1224 | 0.0714 | **64.2 °C** | **PASS**, but see below |
| `RYZEN_7500F_AIR` | 75–76 °C | 0.1223 | 0.0998 | runaway | **FAIL** |
| `H100_LIQUID` | 41–50 °C | — | 0.0037 needed | — | **INFEASIBLE** |

- [x] **The blocking failure is gone, and that is the headline.** The Ryzen package was
      **0.4675 K/W against a published 0.3962 total** — the package alone exceeded the entire
      junction-to-ambient budget, leaving a negative share for the cooler. That is impossible,
      not mis-tuned, and it is why two points could not be reached at any flow. With the lid and
      plate in the boundary with their real overhang it is **0.1223**, a 31% share, and both
      Ryzen points now have a feasible external budget
- [ ] `RYZEN_7500F_AIR`: the failure **moved** rather than went away — from an impossible package
      to a **leakage runaway in the coupled solve** (`diverged` means diverged at *every* damping
      the backtracking tried, so it is the model's answer, not an artefact). Two readings, not
      exclusive, and both are substantive:
      · **the modelled cliff is too low** — the catalogue puts the 34-core cliff at
        1.05–1.15 W/mm² and this point is 132 W over 90.6 mm² = **1.46 W/mm²**, so a part that
        ships in volume sits well past it. That would falsify the cliff position, which is a
        headline result elsewhere in this project
      · **the power map is a stand-in** — 132 W spread *by area* over a 14-core skylake floorplan
        is not a Zen4 CCD, and the real part is a ~71 mm² chiplet plus an IOD
      Distinguishing them needs a **Zen4 floorplan**, not a parameter change. Until then this
      point cannot adjudicate either claim
- [ ] `H100_LIQUID`: needs **0.0037 K/W** of external resistance after the stack (0.054) and the
      spreading have taken their share of a 0.0662 K/W budget. No flow in the class reaches it.
      The liquid points are where the package share hurts most, because the budget is small
      enough that the package is nearly all of it
- [ ] **`RYZEN_7500F_LIQUID` is on the optimistic edge and should be labelled so wherever the
      gate result is quoted.** 64.2 °C against a published 70–71 °C is **5.8 K below the range**,
      inside the 8.0 K `ACCEPT_BELOW_MIN_K` tolerance — a **legitimate pass**, and `check_peak` is
      right to accept it. But its flow solver bottomed out at 1e-05 m³/s and 0 W at the wall: the
      *minimum* flow already cleared the requirement. So one of the gate's two passes carries no
      information about whether the cooler model is right at the operating point, only that the
      package no longer eats the budget. Report it as "passes, 5.8 K cold with the cooler at the
      solver floor", not as a clean pass
- [ ] Gate to 4/4 with no per-point tuning. **Not reached, and not to be reached by moving the
      four inputs above** — see the provenance note
- [ ] Update `EXPECTED` in `test_published_acceptance.py` alongside the model, never to green a test

**Known limitation to state wherever this is used:** the base term is lumped, so lateral gradients
*inside* the cold plate are not resolved. The die's own silicon spreading is still solved by
3D-ICE, which is where the within-die peak comes from, so the approximation sits in the package
rather than in the quantity being asked for.

**Tile array stays matched to the die**, not the base: every 3D-ICE layer spans the floorplan
footprint, so `tile_grid` already covers exactly the die. Folding the base into the boundary keeps
it that way — an overhanging base does **not** drag the array out with it. Worth an explicit
assertion when `SpreadingSink` lands.

## P0.5 — Catalogue re-run  `[x]` DONE 27 Aug 2026 (finished; stragglers landed)

### Launched 26 Aug 2026, after four corrections

**1. The MR envelope was unsourced and wrong in both directions.** It read
`h_max 10 W/mm², dt_max 10 K` with no provenance, while Draft_5 §6.4.1 reports **250 W/mm²** from
a 100×100 µm area and a **45 °C** reduction on the bench — 25× and 4.5× higher — and 3.5 % ASF
efficiency against the model's assumed 20 %. So the model was **pessimistic about capability and
optimistic about efficiency at the same time**, and the capability side was a hidden ceiling: the
planner could never ask for more than 10 K, so any architectural lever needing more was
unreachable *by assumption*. The V_t lever needs 22 K at 50 mV — inside the demonstrated 45 K,
outside the assumed 10 K.

Now `h_max 250`, `dt_max 45` (**demonstrated**) and η_ASF 0.32 / η_laser 0.85 / η_LPC 0.92
(**targets**, and labelled so — Draft_5 §3.5.4 puts *demonstrated* at 0.75 and 0.87). At the
targets `breakeven_ratio` is **1.032 > 1**: the loop is net-generating, a different regime rather
than a better number. `DEMONSTRATED` and `LEGACY_ENVELOPE` sit beside the defaults so the gaps
are inspectable.

**The envelope had eight definitions.** Seven drivers repeated the literals in their own argparse
defaults, which is how it stayed unsourced. They now take the module constants, and a test fails
if a literal reappears.

**2. Density grids re-centred on the measured cliff** — 0.80–1.00 W/mm², down from 1.05–1.15
(`cliff_after_spreading.json`). Grids live in `array_config.sh` (`DENSITY_SWEEP`, `DENSITY_CLIFF`,
`DENSITY_WORKING`, …), not as literals in eleven scripts.

**3. The accelerator was never a power-map problem — it was the cold-plate model.**
`CoolingSpec`'s water path builds a *finned base* sized for the die, i.e. a water block: 0.055 K/W,
on which the GA100 has no steady state above ~250 W. A direct-die **microchannel** plate anchored
on a measured reference (1020 W/cm² at <69 °C and <120 kPa, channels 15–33 µm × 35–470 µm) gives
**0.0153 K/W**, and through the full coupled solve the GA100 runs **51.4 °C at 400 W and 64.0 °C
at 700 W**. The catalogue keeps its real operating points. `microchannel_coldplate.json`;
`accelerator_water_envelope.json` is marked superseded.

Pump power is reported and is **channels only, a floor**: 0.06 W at 700 W, on a flow of
1.7e-05 m³/s — close to the LCEstimator CDU per-device nominal of 1.0e-05, which is the
cross-check that matters. Manifold, plenum and facility loop are not modelled.

**4. A launcher bug that discarded every result** — enumerated `--out-dir` pointed into the
deleted enumeration scratch tree on node-local disk. Fixed, and the planner now refuses to emit a
plan whose points would write outside the output tree.

### Early results, 90 CPU points in

| arm | converged | runaway |
|---|---|---|
| control (grease) | 29 | **61** |
| array_idle (GaAs, 0 W) | 79 | 11 |
| array_on (GaAs, planner) | 79 | 11 |

**50 passive-term rescues** — the grease control has no steady state and the *unpowered* array
does, at 0.85–0.92 W/mm². The passive term runs **2.7 K at d=0.30 to 33.4 K at d=0.88**: a modest
conductivity gain becomes tens of kelvin near the cliff, because that is where leakage feedback is
steepest. This is precisely the confound the three arms exist to separate, and it is large.

### Complete, 27 Aug 2026

**176/180 CPU and 70/72 accelerator points.** The four stragglers are 8-high memory stacks and
two hard occupancy cases; they are the slowest points in the catalogue and are still finishing.

- [x] **Acceptance met: 714 rows, ZERO lacking a `placement` stamp**, all three arms balanced
      (231 each), 229/231 recording `spreading: true`
- [x] `collect_findings.py` regenerates `FINDINGS.json` — 159 entries across 11 families, 39
      flagged unquotable. It gained `--results`, taking several roots: it hardcoded `results/`,
      so a harvest would silently have picked up the **old** generation
- [x] `sweep_runner.py` gained point-level restart (skip if the driver's output exists). The
      gap-fill re-ran only the failed points — `sf03_mr_comparison` skipped 28 and redid 5.
      Without it each of the three bug fixes would have cost a full re-solve of ~200 points

### The result the three arms were built to produce

34-core, 88 CFM, 500 µm pitch, 200 µm burial, spreading boundary:

| W/mm² | control (grease) | array_idle (GaAs, 0 W) | passive |
|---|---|---|---|
| 0.30 | 44.2 °C | 41.5 °C | 2.7 K |
| 0.60 | 68.6 °C | 63.1 °C | 5.5 K |
| 0.80 | 84.9 °C | 77.5 °C | 7.4 K |
| **0.85** | **RUNAWAY** | **81.1 °C** | — |
| 0.92 | RUNAWAY | 86.2 °C | — |
| **0.96** | RUNAWAY | **RUNAWAY** | — |

**Two cliffs, cleanly separated: 0.80–0.85 under grease, 0.92–0.96 with the unpowered array.**
A 14% density gain from a materials substitution with the laser off, and **80 rescued operating
points** across the run. The passive term reaches **33.4 K** near the cliff, where leakage
feedback is steepest — it is not a fixed offset. Under the old two-arm scheme every bit of that
would have been reported as a photonic result.

**The laser term**: 45 points had something above target for the planner to act on; there it
removes 0.04–124.7 W for a further **0.3–50.2 K**. The top of that range exists only because
`dt_max` went from the unsourced 10 K to the demonstrated 45 K.

### The pitch ladder, re-measured — the reversal holds

| power map | best | worst | spread on the same 3 W |
|---|---|---|---|
| uniform (degenerate peak) | **2000 µm, coarsest** 2.93 K | 500 µm, 2.00 K | 0.94 K |
| concentrated (isolated hotspot) | **per-block, finest** 5.57 K | **2000 µm** 2.93 K | 2.63 K |

The coarsest array is the best choice on a plateau and the worst on a hotspot, and the
concentrated case swings 2.8× more across the ladder. Both results exist only as comparisons
*across* the ladder — which is why collapsing it to a single pitch was the wrong call.

### The harvest was stale — found and fixed 27 Aug 2026, second session

`docs/NEXT_SESSION.md` records `FINDINGS.json` as *"159 entries, 11 families, 39 flagged
unquotable"*, harvested across both re-run roots. **The file in the working tree was not that
harvest.** All 157 of its entries pointed at the **pre-re-run `results/` generation** — the old
sink boundary, before `--spreading`. Proof, one point:

| | f_sustainable at r_th 0.02 K/W, no MR | limited_by | source |
|---|---|---|---|
| stale file | 4.34 GHz | `over_thermal_limit` | `results/cooling_for_clock/…` |
| re-harvest | 4.25 / 4.48 GHz (two arms) | `thermal_runaway` | `results/rerun_cpu/cooling_for_clock/…` |

The stale file also had **no cliff entry at d = 0.85**, the density the three-arm cliff result
turns on. Fixed by one command — nothing needed re-solving:

```
python scripts/collect_findings.py \
  --results "$PWD/results/rerun_cpu" "$PWD/results/rerun_accel" \
  --out docs/evidence/FINDINGS.json
```

Now **161 entries, 39 unquotable, every source under a re-run root**.
`docs/evidence/findings_harvest_correction.json` carries the proof and the counts.

**And it exposed a coverage gap that matters more than the stale file did.** Three families
*shrank*, because points in the old `results/` tree are **not in the re-run plan at all** and no
batch script in `scripts/` reproduces them — they were ad-hoc runs from earlier sessions:

| family | stale | re-run | what is missing |
|---|---|---|---|
| `tiers` | 18 | **6** | the twelve standalone screens `tiers_{34c,uniform,turbo,turbo_idle,mixed25,mixed50,fpu2,fpu3,fpu4,g4_*}` |
| `clock` | 28 | **21** | `turbo_{,m2_}{balanced,concentrated}`, `clock_target_T{65,78}`, `leakv_e{0,2}` |
| `accelerator` | 18 | **41** | *grew* — the stale harvest never saw `results/rerun_accel` |

- [ ] **The tier screens have no re-run backing, and gen 0 depends on them.**
      `docs/LADDER_GEN0.md` §3 lists *peak-to-runner-up gap* and *plateau width at `dt_max`* as
      "produced by the tier screens" — those screens are these twelve unreproduced points. **Two
      of gen 0's five phase-1 floorplan metrics currently rest on the superseded boundary.**
      They are cheap (`examples/thermal_tiers.py`, no new physics); they need a batch script so
      they stop being ad-hoc, and a re-run
- [ ] **`leakv_e0` / `leakv_e2` are the `leak_v_exponent` sensitivity arms** — the documented
      assumption behind leakage scaling as `V**leak_v_exponent`. That sensitivity is now
      **unmeasured on the corrected boundary**, and `clock_search` results depend on it
- [ ] `dtmax_batch.sh`, `kernel_batch.sh` and `14_perf_sims_to_7_10_14_power_sims.sh` contribute
      no standalone points to the plan. Decide per script: fold in, or mark deliberately excluded

## P0.5b — Rebuild the handbook  `[~]` figures and the headline sections done

- [x] **Every figure regenerated from `docs/evidence/`** — 9 embedded, 5 changed
      (`acceptance_gate`, `results`, `tile_pitch`, `die_average`, `stack_packages`). The gate
      figure's hardcoded `GATE_ROWS` now carries the measured 2/4
- [x] Evidence re-harvested at current settings: `cliff_verified_34core_88cfm.json` rebuilt with
      three arms, `tile_pitch_{uniform,concentrated}.json` on the restored ladder at 200 µm
      burial, `die_average_strategies.json` likewise
- [x] **Status banner rewritten** — the old one said "nothing has been re-run"
- [x] **New section: "What the three arms separated, and what moved"**, with both cliff tables,
      the laser term, the pitch reversal, and an explicit note on what is *not* comparable with
      the older numbers
- [x] **The 67% burial claim is qualified in place** — block maximum on `L3_4` against the
      production path's block average on `L2_4`; +44.1% through the planner, +11.0% on `L2_4`
      by the direct probe. The separation survives all three; the magnitude does not
- [x] Gate section rewritten: 2/4, the package falling 0.4675 → 0.1223 K/W as the real result,
      the liquid Ryzen pass flagged as the weaker one, and the four unvalidated inputs named
- [~] Re-adjudicate the remaining ~90 quantitative claims: stands / strengthened / superseded /
      withdrawn. **Second pass done 27 Aug 2026 (second session)** — 18 claims adjudicated across
      six sections. HTML re-validated well-formed after every edit; no Python touched, so the
      569/1 baseline is unaffected (re-confirmed, 5 min 29 s). What moved:
  - **withdrawn** — *"Cost is dominated by how much margin you demand"*, previously marked
    **verified**. Its 30–160× rescue-cost rise and both knees (~94 °C at 1.10, ~97 °C at 1.15)
    have **no backing on the corrected boundary**; see the new defect entry below. Also the
    450× rescue-vs-hold pair (0.29 W / 131 W), same cause
  - **superseded** — the stability cliff wherever it appeared as 1.05–1.10 W/mm² (now 0.80–0.85
    grease, 0.92–0.96 array); the "typical density 1.00–1.17" row; the cliff figure caption
  - **strengthened** — *proportional extraction ≈ reducing die power*. Re-measured through three
    fresh solves at `--die-W 97/90/70`: predicted 78.85 / 75.32 / 65.25 °C against measured
    79.12 / 76.24 / 68.01. **The residuals reproduce the superseded measurement to two decimal
    places (+0.27 / +0.92 / +2.76 K) across a boundary differing 4.25× in K/W and a burial depth
    that was half** — so the residual is a property of the array layer, not the sink.
    `docs/evidence/proportional_equals_power_reduction.json`
  - **re-measured** — the four-strategy table at 200 µm burial: hotspot 0.665/0.436/0.235, top5
    1.119/0.419/0.218, uniform 0.317 flat, proportional 0.412 flat. Every number moved and **not
    one ordering did**. "1.9× at 30 W" → **1.75×**; "1.50 K per electrical watt" → **1.46**;
    the "roughly 7 W" crossover was an unsupported interpolation and is now bounded at 10–30 W
  - **overtaken** — *"the binding constraint is lift"*: correct diagnosis, but the 10 K wall it
    named was the unsourced envelope. The bench demonstrates 45 K, so the device ask
    ("get dt_max from 10 to 13 K") was already satisfied before it was asked
  - **falsified** — the caveat *"MR against a cold plate cannot be run as the pipeline stands"*.
    `MicrochannelSink` exists, is measured, and lands the GA100 at 64.0 °C at 700 W. That gap is
    now a study to run, not a capability to build
  - **corrected** — footer said **311 tests passing**; it is 569 passed / 1 skipped
- [ ] Still carrying pre-re-run numbers, not yet adjudicated: the accelerator break-even table
      (184 CFM / 575.0 W vs 88 CFM / 413.8 W and the 33.7× margin) and the workload-dependence
      section's absolute temperatures. Both are air-cooled accelerator results, so both are
      downstream of the withdrawal that already covers them — they need re-solving on the
      microchannel plate, not re-wording
- [ ] Rewrite "Where microrefrigeration pays" — a different analysis now, with three arms and
      four strategies
- [ ] Give "The package was wrong" its ending: the package it was wrong about is now measured,
      and the answer is that the packaging term is most of the effect
- [x] List what moved, in one place, for a reader who knew the old handbook — the new section
      and its "what is not comparable" note
- [ ] **Then** re-adjudicate `CODESIGN_PLAN.md` claims and next steps the same way

### Two more defects the catalogue carries — found 27 Aug 2026 while re-adjudicating

`docs/evidence/catalogue_naming_and_margin_defects.json`. Neither needed a re-solve to diagnose;
the second one voids a handbook headline until its study is re-centred and re-run.

- [ ] **Sixteen point tags lie about their density.** The grids were re-centred onto the measured
      cliff and moved into `array_config.sh`, but the tag strings kept their old names.
      `margin_T95_d1.10` ran at **0.80** W/mm², `ceiling_d1.17` at **0.95**, `cores128_d1.00` at
      **0.70** — overstating by up to **43 %**. The `density` field in the JSON is correct
      throughout, so this is a naming defect, not a data one: *trust the field, not the tag*.
      **Fix:** have `sweep_runner` stamp the density into the tag, so it cannot drift again
- [ ] **The margin study is inert on the corrected boundary.** Of 85 catalogue points that build
      an MR plan, **68 removed zero heat and engaged zero blocks** — "nothing above target". Every
      `margin_curve` point and both `rescue_target98` points are among them. The sweep asks for
      93–99 °C; the corrected boundary puts the die at 77.5 °C (d=0.80), 81.1 °C (d=0.85) and
      73.0 °C (liquid), i.e. **12–26 K below its own targets**.
      **This is the same mechanism the handbook's own third margin curve already reported** — on a
      liquid sink the die held 93.6 °C unaided and MR engaged zero blocks, *"better conventional
      cooling did not make MR more valuable, it made it irrelevant"*. The spreading correction did
      to the air case what the liquid sink did to the liquid one. The mechanism generalises; the
      numbers are gone.
      **Fix:** re-centre targets to ~70–85 °C and *derive them from each point's measured unaided
      peak* rather than from absolute literals, so the study cannot slide out from under its own
      targets the next time the boundary moves



### What the first launch found, 26 Aug 2026

Launched, stopped twice, and both stops were worth it.

**1. A launcher bug that silently discarded every result.** The enumerated `--out-dir` is built
from the scratch tree's `$REPO`, so the commands said
`--out-dir /tmp/catalogue_rerun_XXXX/results/...`. `sweep_runner` only assigns an out-dir to
points that lack one, so the run faithfully *recreated the deleted enumeration tree on the compute
node's local disk* and wrote into it — off NFS, so it would not have survived the allocation.
Caught after 108 MB. Fixed by `_reroot_out_dir`, and `catalogue_rerun.py` now **refuses to emit a
plan** whose points would write outside the output tree (verified by sabotaging the re-rooting and
watching the guard fire).

**2. The density grids are now mostly past the cliff.** `--spreading` moved the 34-core boundary
from 0.0764 to 0.3247 K/W, and the cliff with it — measured, not estimated
(`docs/evidence/cliff_after_spreading.json`):

| W/mm² | die W | control | array_idle | passive |
|---|---|---|---|---|
| 0.20 | 20.2 | 36.1 °C | 34.3 °C | 1.8 K |
| 0.40 | 40.5 | 52.3 °C | 48.7 °C | 3.7 K |
| 0.60 | 60.7 | 68.6 °C | 63.1 °C | 5.5 K |
| 0.80 | 81.0 | **84.9 °C** | 77.5 °C | 7.4 K |
| 1.00 | 101.2 | **RUNAWAY** | **RUNAWAY** | — |

**The cliff is now between 0.80 and 1.00 W/mm², against 1.05–1.15 before.** The catalogue sweeps
0.60–1.25 with most points at 1.05–1.25 — almost entirely past it. Re-running unchanged reproduces
the failure `overnight_study.sh`'s own header records: *"almost every point past the cliff and
RUNAWAY for nearly all of them, which told us nothing."*

**3. Every accelerator point runs away, and it is CORRECT** —
`docs/evidence/accelerator_runaway_cause.json`. Not the package and not the spreading: the *old
lidded stack* runs away too. The cause is commit `0f91991` (20 Aug), *"Leakage feedback was inert
on the accelerator: 43 studies were constant-power solves"*. The accelerator rows in
`FINDINGS.json` are dated 17–18 Aug — **they are constant-power solves**, and `ac9229d` the same
day already withdrew their temperatures from the handbook. With working leakage feedback the
GA100 has no steady state at 400 W on 88 CFM air. The accelerator points need a viable envelope
(`--r-th 0.05`, `--cooling-fluid water`, or lower power), not a re-run at 400/700 W on air.

**4. The cold-plate base thickness is now a first-order input, and it has no reference.** It was
gate-only; with the overhang it sets the constriction through τ = t/b:

| base | boundary (34-core, 88 CFM) | vs slab | ΔT at 116 W |
|---|---|---|---|
| 2 mm, k 300 *(the skylake.stk default)* | 0.3247 K/W | 4.2× | 37.7 K |
| 4 mm, k 390 | 0.2083 K/W | 2.7× | 24.2 K |
| 6 mm, k 390 | 0.1920 K/W | 2.5× | 22.3 K |

That 1.7× range is the difference between running away and not, on an input recorded as
**NOT ESTABLISHED** in `package_input_provenance.json`. Reachable as `--stack spec:...,sink=6000`.

- [ ] **Re-centre the sweep grids** — CPU densities onto 0.30–0.90, accelerator onto a viable
      cooling class — then re-plan and relaunch
- [ ] Decide whether the 2 mm base stands, or is replaced with a sourced value



*Was: 80,330 solves, ~9 h warm single-stream. **Re-costed, and it is bigger**: three arms
instead of two is 556 arms rather than 288, so ~155,000 solves and ~29 h of solver work — 5.3 h
wall at the concurrency the memory allows.*

- [x] **`scripts/catalogue_rerun.py`** — enumerates the points, partitions by system matrix,
      emits per-stream points files and a throttled launcher (`scripts/run_rerun.sh`)
- [x] **The batch scripts define the catalogue, not this script.** Points are read out of them by
      running each with a printing stand-in for `srun` (plus no-op `sleep` and false `pgrep`, or
      the throttle loops and `followon_study`'s wait make enumeration take minutes/forever). A
      point added to a batch script is in the re-run automatically
- [x] **The matrix key is conservative on purpose** — computed from arguments, so same key ⇒
      same matrix, different key ⇒ maybe. `ICESessionCache` re-checks the real fingerprint every
      solve, so a wrong key costs factorisations and **can never produce a wrong temperature**
- [x] **Critical-path splitting**, not "split big groups". The first version split almost
      everything down to single points, which is the cold re-run wearing a different hat. Now:
      split the longest group, and only it, while it exceeds an even share *and* its solve time
      is worth ≥ 4 factorisations *and* it has more than one point
- [x] **A stream is a process.** Streams are single-driver because `sweep_runner.py` takes one
      script per points file; an earlier version planned 11 streams and generated a launcher
      wanting 30 processes, so the memory budget it was costed against was fiction
- [x] Concurrency is **memory-bound, not core-bound**: one two-die accelerator session is
      ~28.8 GB, so 6 streams fill a 200 GB budget on a 96-core node. Sized on **peak** RSS
      (~1.3× steady), because sizing on steady over-subscribes during exactly the factorisation
      transient that makes it peak
- [x] **The pitch LADDER is restored as the swept variable** (corrected 26 Aug 2026 — see the
      settled decisions). `PITCH_SWEEP_UM` is **50/100/200/500/1000/2000 µm**; fixed-pitch studies
      use **500 µm**, the back-catalogue value, so arm deltas stay comparable. `tile_pitch_sweep.py`
      defaults to the ladder. `device_pitch_um()` is **deleted** — a single device pitch is the
      collapse being corrected; `device_pitch_range_um(die_area)` remains as a per-die annotation
- [x] **The re-run now actually sweeps it.** Two new families, deliberately labelled apart from
      the legacy `--spot-min-um` rule they are *not* the same as:
      · `overnight3_study.sh` Phase 4 — the six rungs coupled on the 34-core die
      · `accel_mr_batch.sh` — the ladder × `--placement contiguous|scattered`, which is the only
        real **concentration axis** in the directory (degenerate plateau vs isolated hotspot) and
        therefore the only place the **ordering reversal** can be observed. `mr_comparison` has no
        power-shape knob, so the CPU ladder is the plateau case *only* — do not read a reversal
        out of it
      · the accelerator ladder skips the 50 µm rung: the GA100 runs on a 100 µm grid and
        `tile_grid` refuses a pitch finer than the mesh
- [x] **`matrix_key` is last-wins, like argparse.** The ladder points carry `--pitch-um` twice
      (the shared default, then the rung). Keying on both split a 500 µm point that overrode
      itself to 500 from a plain one and paid its factorisation twice — 67 matrices instead of 65
- [ ] Warm-start the `clock` bisection first (31% of the catalogue)
- [ ] Re-run the 20 points that fail verification at the damping backtracking selects; keep trajectories
- [ ] **Run it**: `scripts/run_rerun.sh <jobid>` (restartable; `.done` markers per stream)
- [ ] `collect_findings.py` regenerates `FINDINGS.json`; zero rows lacking a stamp

**Plan as generated, 26 Aug 2026, with the ladder** (`results/rerun_plan/plan.json`):
**254 invocations → 584 arms → 65 matrices in 42 groups → 6 streams / 11 processes,
32.4 h of solver work (3.4 h factorising + 29.0 h solving), 6.3 h wall.**

What the ladder cost, against holding one pitch: +16 invocations, +28 arms, **+10 matrices**
(3.4 h of factorising against 2.4 h) and +1.0 h of wall. Each rung is its own system matrix —
the tile floorplan is part of the geometry the factorisation is built from — so granularity is
the most expensive axis per point in the catalogue. It is also the one whose headline result
(the ordering reverses with the workload) cannot be obtained any other way.

The solves-per-arm figure (279) is *counted* from the old catalogue but is an average over very
unequal families — treat the hours as an estimate, not a schedule.

**Piloted end to end**, 26 Aug 2026: two real plan points through `sweep_runner.py` in one
process, three arms each, 19–21 s per point at smoke settings, every row stamped with `arm`,
`placement`, `n_tiles`, `pitch_um` and `stack_spec`. The mechanism works; what follows is why it
has not been launched.

### `[!]` BLOCKED — and it is P0.4, exactly as the plan predicted

`docs/EXECUTION_PLAN.md` P0.4 says the overhang "must still precede P0.5 or the re-run happens
twice". It does, and it would:

**No driver can build a `SpreadingSink`.** `grep -rn SpreadingSink examples/ scripts/` returns
nothing. The physics landed in `sink_models.py` and `cooling_spec.py` and is tested, and the
`sink_in_stack` spec key is reachable from `--stack`, but nothing wires the two together — so
every point in this plan would still solve against the 2 mm slab at the die footprint. On the
baseline stack at a fixed physical cooler that is **9.70 K/W against 0.84 K/W**, and it tracks
1/area (15.5× across die sizes against 2.6×). Twenty-nine hours of solver time against a sink
model the project has already superseded.

The integration is bounded: a `--spreading` / `--base-mm2` path on the drivers that take
`--stack`, building `SpreadingSink` with `base_area_from_footprint()` and setting
`sink_in_stack=0` in the spec. Nothing else in the re-run is waiting on anything.

**RESOLVED 26 Aug 2026.** The sink is wired, reproduces its own evidence to the digit, and the
gate has been run: **2 of 4**, with the blocking failure (a package exceeding its whole budget)
gone and the two survivors diagnosed as needing a Zen4 floorplan and a tighter liquid budget
respectively — neither of them a property of the sink model. `array_config.sh` now passes
`--spreading` on **227 of the 238** catalogue commands (the 11 without are
`stacked_memory_study`, which cannot take a generated stack). The plan is regenerated against it.
See P0.4 below for the gate table and what it means.

**DECIDED 26 Aug 2026: do the gate as well as the integration, before the catalogue.** Not just
wire the sink — run `validate_published.py` to 4/4 first, so the 29 hours are spent against a sink
model that has been *validated*, not merely *plumbed in*. Slower, and it means nothing gets run
twice. The four unvalidated package inputs (solder thickness, indium conductivity, cold-plate
thickness and conductivity) must be checked against **their own references**, not adopted because
they close the gate — that is tuning against the acceptance test, which is the exact failure the
gate exists to prevent. If it then passes that is a result; if it still fails that is also a
result.

### The pitch collapse, and the arithmetic that makes it visible

**SUPERSEDED 26 Aug 2026.** An earlier version of this section recorded *"hold the pitch at 5 mm
everywhere"* as a decision. It was not one — it came from a bad handoff, and it stacked two
errors, each sufficient on its own:

1. **It collapsed a swept study variable into a point estimate.** Granularity is one of the things
   this project exists to measure. The ordering of coarse against fine *reverses with the
   workload*, and a coarse array is low-variance while a fine one swings 3.6× on identical
   hardware. Neither result exists except as a comparison across the ladder.
2. **It converted a tile COUNT into an absolute PITCH.** The demo device is 4–16 *tiles* on a
   ~200 mm² die. A count fixes `pitch = sqrt(area/n)`, so carrying the demo's pitch to a smaller
   die divides the tile count by the area ratio.

What the second error costs, on the dies the catalogue actually uses — and note that **38 of the
44 `--cores` invocations in `scripts/` are 34-core**:

| die | area mm² | 50 µm | 100 | 200 | 500 | 1000 | 2000 | device 4–16 tiles |
|---|---|---|---|---|---|---|---|---|
| skylake 10nm 7-core | 53 | 21350 | 5307 | 1290 | 204 | 48 | 12 | 1.8–3.7 mm |
| **skylake 7nm 34-core** | **101** | **40672** | **10168** | **2542** | **384** | **96** | **24** | **2.5–5.0 mm** |
| skylake 7nm 70-core | 196 | 78652 | 19610 | 4876 | 777 | 180 | 45 | 3.5–7.0 mm |
| skylake 7nm 128-core | 348 | 139360 | 34840 | 8710 | 1378 | 338 | 78 | 4.7–9.3 mm |
| GA100 | 826 | *(grid)* | 82656 | 20592 | 3249 | 784 | 196 | 7.2–14.4 mm |

Counts are from `tile_grid` on the snapped floorplan extent, so they differ by ~1% from an
`area/pitch²` estimate at the fine end. **The GA100 cannot take the 50 µm rung**: it runs on a
100 µm thermal grid and `tile_grid` refuses a pitch finer than the mesh — the solve cannot
resolve tiles it cannot mesh.

At **5 mm** the 7-core die gets **1 tile** and the 34-core **2**. Everything still runs and the
watts still conserve, but *"extraction is a spatially-matched response"* is vacuous and a
spot-policy sweep against two tiles measures nothing. `ArrayWiring` now warns and sets
`.degenerate` below **4 tiles** — the threshold was 1, under which the 2-tile 34-core case ran
silently.

**Where the device actually sits, which is the thing worth reporting.** On the 34-core die 4–16
tiles is **2.5–5.0 mm — coarser than the ladder's 2000 µm top.** So the first-generation device
lies just beyond the coarse end of the studied range. That belongs in a device-roadmap
conversation; it is not a reason to run the catalogue there.


## P0.5c — The re-centred gap-fill, and the V/F correction  `[x]` DONE 27 Aug 2026 (2nd session)

Two tracks run in parallel: solver work on node-06, model work on the head node.
**Test suite: 569 → 587 passed, 1 skipped. 18 tests added, none removed, no regressions.**

### Track A — the three unbacked families, re-centred and re-run

`scripts/recentred_gapfill.sh` (new — being ad-hoc is *why* these were missed).
**44/44 tier points, 18/18 margin points**, restart-safe at point granularity.

- [x] **Two drivers had missed the envelope centralisation.** `thermal_tiers.py` and
      `stacked_memory_study.py` still hardcoded `--dt-max 10.0` — the legacy envelope, against a
      demonstrated 45 K — and `thermal_tiers.py` defaulted `--density 1.07`, past the current
      cliff. **The guard test existed and had a hole**: its `FLAGS` list carried `--dt-max-K` but
      not plain `--dt-max`, so both drivers slipped through. Flag list widened; a guard with an
      incomplete list reads exactly like a guard that passes
- [x] **`--mr-target-offset-K` on `mr_comparison.py`** — targets derived from each point's own
      measured unaided peak instead of absolute literals. **The reference arm is `array_idle`, not
      `control`**: the control is a different stack, cooler by the passive term (7.4 K at d=0.80),
      so offsetting from it lands above the array's own peak and engages nothing. That error was
      made, then caught by smoke test before the batch ran
- [x] **`collect_findings.py` now refuses to report either defect silently** — it flags tags whose
      encoded density contradicts the `density` field (18 rows) and counts MR plans that engaged
      nothing (68 of 85). Both reproduce the manual analysis exactly
- [x] **A concurrency bug in `write_stack`, found by the batch.** The generated stack filename is
      *deterministic* and therefore shared, and `open(path,'w')` truncates before writing — so a
      concurrent reader gets a partial stack. Eight concurrent tier points produced
      `Expected exactly one "heat transfer coefficient" ... found 0`. That guard caught it by
      luck; a partial file that still parsed would have been a silently wrong geometry shared by
      the whole sweep. Now writes to a temp file and `os.replace`s it (atomic on POSIX), with a
      threaded regression test

**Result 1 — the margin curve is restored, and it overturns a handbook claim.**
`docs/evidence/margin_curve_restored.json`. Cost rises **24.0× / 23.9× / 25.1×** from 1 K to 12 K
of margin at d=0.80 air, d=0.85 air, and liquid. The knee is visible as the plateau being entered:
the plan holds the target with **one** block up to 2 K, then engaged blocks explode
1 → 3 → 6 → 12 → 32 while achieved lags demanded.
**The liquid arm now behaves like air.** The old "better conventional cooling made MR irrelevant"
came from an *absolute* target the die already met — a fact about the requirement, not about MR or
about liquid cooling. Cost-of-margin is a property of the die's temperature distribution.

**Result 2 — the plateau metric is degenerate at the demonstrated envelope.**
`docs/evidence/tier_screens_dt_ladder.json`, 44 points × 11 shapes × dt_max ∈ {10,20,30,45}.
At **45 K every shape returns plateau = the whole die** (1126/1126); at 10 K the same shapes span
**4 → 56 blocks**. The die's own spread is 31.9–45.0 K, i.e. *smaller than the demonstrated lift*,
so "blocks within `dt_max` of the peak" means "all of them". And **clip-one gain does not depend on
`dt_max` at all** — it reduces to the peak-to-runner-up gap. So gen 0 has **one** robust metric
here, not two, and `LADDER_GEN0.md` §3 is corrected.

- [ ] `leakv_e{0,1,2}` still running at the time of writing — `clock_headroom` has no `--density`
      (it *searches* for the clock), which the first launch got wrong. Re-launched with the
      `cooling_for_rated_clock.sh` argument set

### Track B — the V/F curve

- [x] **`VF_ALPHA_POWER_FIT` refitted under α ≥ 1**, and the bound **binds**: α lands exactly on
      1.0, k = 7.5485, V_th = 0.4643, RMS 0.74 %. The old α = 0.949 was below the physical floor
      and put an interior maximum in the curve at `V_th/(1−α)` — the spurious "6.43 GHz at 9.40 V".
      The unconstrained fit is kept as `VF_ALPHA_POWER_FIT_UNCONSTRAINED` so the withdrawn numbers
      stay reproducible rather than merely asserted. **Nothing in the solve path uses either fit**,
      so no historical result moves
- [x] **The refit found something bigger than the correction.** Forced to the textbook's typical
      α = 1.4 the table misfits by **4.93 % RMS, seventeen times worse** than the free fit. The
      data actively resist the physical range, and the shape says why — 1.5 GHz per 200 mV at the
      bottom, 0.1 GHz per ~50 mV at the top. That is a **product bin table** (reliability-limited
      guardbanding), not a device curve. The honest conclusion is not "wrong exponent" but
      **"the alpha-power law is the wrong model for this table"**
- [x] **A measured product V/F curve now exists**: `HotGauge/HotGauge/power/product_vf.py`,
      Ryzen 9 9950X (Zen 5, N4P) via AMD Curve Optimizer / Curve Shaper — the SMU's own curve.
      Refuses to extrapolate outside its four measured points. `calibrated = False`, for a
      *different* reason than `IRDSVFModel`: that is a projection nobody measured, this is a
      measurement with a sample size of one
- [x] **And it carries temperature, which no other V/F source here does.** dV/dT is
      **0.40 mV/K at 4.77 GHz and 0.96 at 5.17** — it more than doubles across 0.4 GHz. Cooling
      90 → 40 °C saves 48 mV at 5.165 GHz (**≈8 % dynamic power at constant clock**) or buys
      **93 MHz at a fixed 1.35 V ceiling**. Every clock result in this project was computed on a
      temperature-*independent* curve, so **this lever has been absent by construction** — the same
      shape of omission as the unsourced `dt_max` = 10 K
- [x] **The shipped table is empirically refuted as a modern-node curve.** It needs 1.4 V for
      5.0 GHz; the measured part needs **1.08 V**, and reaches **5.63 GHz at 1.35 V**. That is
      1.68× the dynamic power for the same clock
- [ ] **Vendor VID tables: a negative result worth recording.** There is no published
      frequency→voltage table because the curve is **per-part** — each die is calibrated at test
      and its curve fused. Intel's published VID tables are an 8-bit code→volts *encoding*, not a
      frequency mapping. This corroborates the binning reading of `VF_PAIRS` and means the
      sourcing job is *measurement*, not document retrieval

**Consequence for the ladder.** "Does LCMR reach 6 GHz?" was answered *no* on the shipped table
(5.0 GHz at 1.4 V) and IRDS (3.34–4.54 GHz) — both now known to sit well below what ships. A
measured part does 5.63 GHz at 1.35 V. This does **not** overturn the answer, because the measured
curve stops at 5.63 GHz and must not be extrapolated — but it removes the basis for the confident
no, and the question should be re-asked against product data.

- [x] **`LADDER_GEN0.md` §2 caveat 3 was wrong and is corrected.** It said `IRDSVFModel` takes no
      V_t override and called that "the one piece of code gen 0 needs". The override has been there
      all along (`vt_shift_mV`), and it does the subtle part right: `k` is calibrated on nominal
      V_t and held fixed, because re-fitting it would make the lever buy exactly nothing.
      **The V_t rung is runnable today, and it does not wait on the V/F curve**

## P0.5d — The clock study's MR arm, and a floorplan metric that survives the device  `[~]` 27 Aug 2026

### `[!]` A defect that zeroed the MR arm of every clock study in the project

Found while harvesting the `leak_v_exponent` runs — the harvest was the point of them, and it
turned up something bigger than the sensitivity it was measuring.

**Symptom.** 9 of 10 `array_on` rows across the whole catalogue report `f_sustainable_GHz`
= **2.0000** — *exactly* `--f-lo`, the bottom of the search bracket — with
`limited_by: 'unverified'`. The one exception uses `--mr-mode distributed`, which bypasses
`run_mr_clipping` entirely.

**Mechanism.** `clock_headroom`'s solve wrapper accumulates `state['unconverged']` over *every*
solve the MR loop makes. The envelope descent deliberately probes past the stability boundary to
bracket its answer, so for an MR point that counter is essentially always non-zero.
`is_sustainable()` treats unconverged as **not** sustainable — correctly, since "we could not
tell" must not become "yes" — so every candidate clock was rejected and the bisection walked all
the way down to the floor.

**Why it survived.** *The identical bug was already found and fixed in `mr_comparison.py`*, whose
source says it "hid roughly fifteen good measurements, including every pixel-pitch point".
`clock_headroom.py` received **half** of that fix: `diverged` was taken from the MR result
(`temp_trace_diverged`) while `unconverged` was still taken from the probe counter. **A
half-applied fix is worse than none, because the file reads as though it had been corrected.**

- [x] Fixed: `unconverged` now comes from `run_mr_clipping`'s `result_unconverged`, exactly as
      `mr_comparison.py` does
- [x] `TestProbeFailuresMustNotSinkTheAnswer` pins the semantics and **spans both drivers**,
      because the defect was an asymmetry *between* them
- [x] Pre-fix numbers recorded in `docs/evidence/clock_search_mr_arm_defect.json` — they are on
      disk across the catalogue and they look like measurements
- [x] Re-ran the three `leakv` arms on the fixed driver — **and the symptom did not move.** The
      probe-counter diagnosis above was **wrong**, and is marked superseded in the evidence file
      rather than quietly edited. `result_unconverged` is `bool(status_fn()['unconverged'])` — the
      status of the *last* solve, not of the probes — so taking the verdict from there changes
      nothing when the last solve is itself unconverged, which here it is. The consistency fix is
      kept and still correct; it was not the cause
- [x] **Diagnosed to a boundary by three probes**, without further guessing:
      *low clock, two arms* → array_on converges cleanly (2.550 GHz at 42.1 °C), so the path is not
      broken; *low clock, three arms* → all three converge, ruling out an arm-ordering or
      session-cache interaction; *the full search* → fails at every candidate, with a block at
      **3838 K on iteration 1**.
      **The pattern: array_on converges whenever the planner has nothing to do, and fails whenever
      the planner engages.** At 2.5 GHz the die is 42 °C against a 92 °C absolute target, so the
      plan is empty. At the clocks the search cares about, the die is at or past its runaway
      boundary and the plan is sized from a baseline that cannot support one
- [x] **Root cause found, and it is neither of the first two guesses.** The descent sized its
      **first** plan from an *assumed* sensitivity of 1.0 K/W (`sens.setdefault(b, 1.0)`). Under
      the **legacy** envelope the device caps hid that — `h_max` bound **396 of 400** blocks on a
      representative near-cliff field, so the plan was restrained by the device rather than by the
      guess. Correcting the envelope to its demonstrated values removed the restraint and
      `q_need = excess / s` began to bind, so the guess set the plan directly:
      **841 W → 9405 W (11.2×) against a die dissipating 79 W.**
      That is what produced blocks at 3838 K. The handbook's own *"cooling plan sized from a
      diverging trajectory"* was the right family of defect; the specific mechanism is that
      **correcting the envelope removed a safety net nobody knew was load-bearing**
- [x] **Fix 2 — a conservation cap** (`clipping_plan(die_power_W=…)`). The three existing caps are
      all *device* limits; this is the one *physical* one. **Two design choices were overturned by
      measurement during implementation, and both are recorded:**
      *per-block → global*, because the array sits above the silicon so a tile cools a
      neighbourhood — the working plans already remove **0.108 W per block against a 0.070 W mean
      block power**, so a strict `q ≤ p_block` would have broken correct results;
      *greedy → proportional scaling*, because a conservation violation is not a spending
      decision — reusing the budget's hottest-first trim put the whole die's 79 W onto 2 blocks.
      Hitting `max_total_W` is a result; hitting `die_power_W` is a **bug signal**, and it warns
      accordingly
- [x] **Fix 1 — measure the sensitivity before sizing from it.** A small *proportional* probe
      (2 % of die power) over the hot blocks, one extra solve, then plan from measured dT/dq.
      Verified against a rig with a known sensitivity: recovers 0.35 and 0.08 K/W exactly.
      `calibrate=False` restores the historical behaviour, so old results stay reproducible
- [x] **Regression checked on the working regime, which is the point.** Margin at 1 K offset:
      **0.144 → 0.143 W**, unchanged. At 12 K: **3.453 W / −7.3 K → 3.771 W / −8.8 K** — *improved*,
      not regressed: a measured sensitivity sizes a better plan, so the same target buys 1.5 K more
      for 9 % more heat. The curve's shape and its ~24× cost rise are unaffected. Zero conservation
      warnings fired on these points
- [!] **It produced a number, and the number was FALSE.** 4.8125 GHz at r_th 0.3, a +39 % laser
      term. The arithmetic gave it away: `array_on` reported **62.6 °C on 183.9 W** while
      `array_idle` diverged at **85.0 °C on 61.7 W** — three times the power at a 22 K *lower*
      peak, with **0.000 W removed**
- [x] **Cause: `CoolingApplication` pushes tile powers into the solver as a side effect and nothing
      rewound them.** `clock_headroom` builds the wiring once per *arm* and reuses it across every
      step of the clock bisection, so a plan from one candidate clock persisted into the next while
      the accounting reported the new, empty one. Cooling applied but not accounted — the exact
      failure the placement-stamping machinery exists to prevent.
      **The leak predates this session**; what the two fixes changed is that the stale plan went
      from *so large everything diverged* to a large **finite** plan, so the leak began producing a
      plausible-looking result instead of an obvious failure. Strictly more dangerous
- [x] Fixed in `run_mr_clipping`, which already exists to do "one thing the loop must not be
      trusted to remember at each of its thirteen exits": the reported plan is re-applied on exit,
      so array state and accounting agree by construction
- [x] **And it is now checked automatically, not just fixed.** New
      `HotGauge/HotGauge/thermal/arm_consistency.py`, wired into **both** drivers so it runs on
      every point. *Zero removal must mean zero cooling* — exact, cannot false-positive, and it is
      the case actually observed. A gain beyond **10 K/W** is warned about rather than raised: the
      best strategy ever measured here is **1.119 K/W**, so that ceiling has ~9× headroom and is
      labelled a smoke alarm, not a physical law. This class of defect is silent in every recorded
      field — it surfaced only because three numbers were looked at together — so "fixed once" is
      not "cannot recur"
- [x] Margin points re-verified after the leak fix: **byte-identical** (0.143 W / −1.0 K and
      3.771 W / −8.8 K), confirming `mr_comparison` was never affected — its final plan *is* the
      reported plan, so the re-apply is a no-op there
- [x] **A fifth defect, caught by the codebase rather than by me.** The exit hook tripped
      `ArrayWiring._assert_last_plan_was_solved`: *"the cooling plan is being replaced but no
      solver ever read the previous one (plan generation 2, last read 1)"*. The guard was right —
      applying a plan nothing will solve is a no-op that only confuses the next caller. **Entry
      zeroing was the correct half; the exit hook was wrong** and is removed. Both regression tests
      still pass, because entry zeroing alone already satisfies them
- [!] **The run completed, the numbers are self-consistent, and the answer is still not a result.**
      control 3.3125 GHz / 84.0 °C / 55.4 W · array_idle 3.4531 / 85.0 / 61.7 ·
      array_on **4.6719 / 86.3 °C / 163.5 W / 152.4 W removed**.
      `array_on` is now *hotter* than `array_idle`, which is what a much higher clock should look
      like, and the arm-consistency check passes. **But it removes 93.2 % of die power — it is
      pinned against the conservation cap.** The cap fired **seven times**, the last recording the
      planner wanting **12 692.7 W from a 160.9 W die — 79×**. So "+35 % from the laser" measures
      what the safety bound allows, not what the device does
- [!] **Option 1 did not fix the sizing.** The plan is still 79× too large *with a measured
      sensitivity*, because near the boundary the baseline the probe measures against is itself
      untrustworthy — a sensitivity measured on it is no better than the guess it replaced
- [ ] **This makes the earlier recommendation to skip option 4 wrong.** Widening the
      envelope-descent trigger — use the envelope path whenever the baseline is *near* the
      boundary, not only when it diverges — was argued against on the grounds that a bounded plan
      makes the baseline/envelope split work again. It does not: the plan is still absurd, merely
      bounded. The envelope path **ascends from zero and never sizes anything from a baseline**,
      which is the property this regime actually needs. It now looks necessary rather than optional
- [ ] **The clock laser term remains unmeasured.** Five defects fixed in this path today and the
      study still cannot produce a trustworthy number. `4.6719 GHz` and anything derived from it
      must not be quoted. The **passive** term is unaffected and stands
- [ ] Once it lands: re-run the `cooling_for_clock` family and re-harvest the `clock` family of
      `FINDINGS.json`, which is still carrying the void `array_on` rows
- [~] `results/clock_refix/` (three cooling resistances) still running; expected to show the same
- [ ] **The whole `clock` family of `FINDINGS.json` needs re-harvesting once those land.** The
      passive term (`array_idle − control`) is unaffected — neither arm runs the planner — so what
      was missing was specifically the **laser** term. The project has never had a measured answer
      to *"what clock does the laser buy?"*: the arm that answers it was returning its own floor

### The `leak_v_exponent` assumption is not load-bearing

Measured at e ∈ {0, 1, 2} — the documented default is 1.0 and it is an assumption, not a
measurement. Sustainable clock is essentially invariant: control **3.875 GHz identically**,
array_idle 4.109 / 4.109 / 4.063 (1.2 % spread), and the passive term is +234 / +234 / +188 MHz —
same sign, same magnitude within 20 %. **An unmeasured assumption that turns out not to matter**,
which is worth as much as one that does. *(These are the pre-fix runs; the array_on arm of them is
void and is being re-run.)*

### A phase-1 floorplan metric that does not depend on the device

New module `HotGauge/HotGauge/thermal/floorplan_metrics.py`, 14 tests.
`docs/evidence/floorplan_metric_replacement.json`.

The design rule, learned the hard way: **a floorplan metric must not depend on a device parameter
that can move under it.** "Plateau width at `dt_max`" was informative only because `dt_max` was
pinned at an unsourced 10 K; at the demonstrated 45 K it reports the whole die for every workload.

- [x] **`relative_plateau`** — blocks within a fraction of *the die's own* temperature span.
      Self-normalising, no device parameter. **Spearman 0.934** against the legacy metric across
      eleven shapes (it preserves the ordering, two adjacent swaps), discriminates **12.3×**
      against the legacy 18.7× at 10 K and **1.0×** at 45 K. Correlation stays 0.76–0.93 over
      fractions 0.10–0.50, so the 0.25 default is not delicate
- [x] **`peak_to_runner_up_gap`** — already robust and device-free; now has a home
- [x] **`power_density_concentration`** — LADDER_GEN0 §3 listed this as *not built*. Area-weighted
      Gini plus top-decile share, from a trace and a floorplan, no solve. Area-weighted on purpose:
      an unweighted Gini lets a thousand tiny blocks outvote the few large ones carrying the power
- [x] **`thermal_aspect` / `hot_block_thermal_aspect`** — also listed *not built*. Hot-block
      distance to the nearest die edge, normalised by half the **shorter** side. Geometry only
- [x] Both new metrics emitted by `examples/thermal_tiers.py` alongside the legacy ones
- [ ] **Still owed**: §3's actual deliverable is a *regression* of measured MR benefit against
      these metrics across floorplan and workload variants, **dropping any metric that does not
      predict**. The metrics now exist and are tested; the regression has not been run

**Four of gen 0's five phase-1 metrics are now built and tested** (the fifth, tile alignment at a
pitch, exists as `mr_array.coverage_report` with its relationship to benefit still untested).

## P0.5e — Floorplans from published microarchitecture, and a metric dropped  `[x]` 28 Aug 2026

### The open RISC-V core lists were checked and do not serve

All three (`openhwgroup/core-v-cores`, `riscv/learn`, the GitHub `riscv-cores` collection) are
overwhelmingly **32-bit in-order embedded and educational** parts. **CVA6 is their ceiling** —
6-stage, dual-issue, in-order RV64, roughly Cortex-A55 tier, three performance classes below an
HPC target. The out-of-order entries (`riscy-OOO`, `lizard`, RSD) are academic.

**Building an HPC floorplan on one would have been worse than a press ratio**, because it would
carry the authority of real synthesisable RTL while representing the wrong class of machine.
*(One correction to the GitHub collection's own summary: it lists Rocket Chip as out-of-order.
Rocket is 5-stage **in-order**; BOOM is the OoO core in that ecosystem.)*

### What replaced them, and why it is a real provenance upgrade

- **`arm_a64fx`** — Fujitsu A64FX, the machine the HPC question is actually about. 7 nm, 48+4
  cores in 4 CMGs of 12, 8.786 G transistors, 512-bit SVE, 64 KB L1I + 64 KB L1D per core,
  8 MB L2 per CMG, HBM2 at 1 TB/s
- **`riscv_xiangshan`** — XiangShan Kunminghu, ICT/CAS: out-of-order superscalar RV64, RVA-23,
  server/data-centre targeted, taped out, fully open. 64 KB L1I, ≤64 KB L1D, ≤1 MB unified L2,
  RVV 1.0 VLEN 128b × 2

**`core_area_scale` is gone as an assumption.** `sram_scale` is now *derived* from real per-core
cache capacity against this project's own McPAT config (32/32/512 KB, `mcpat_T330.xml`) —
A64FX 1.41, XiangShan 2.00 — and `vector_multiple` from real vector width. **Core area is an
output**: 102.1 and 117.3 mm² against the 101.1 mm² baseline. The weakest assumption in the first
cut is removed.

- [x] **A defect the shipped tiler caught.** Scaling an SRAM leaf without propagating to its
      ancestors overflows the tiler's assertion that children fit inside their parent. It could
      not appear until a variant scaled SRAM **up** — the earlier ones only shrank it — so the
      first A64FX build failed loudly. Fixed by propagating the delta up the unit tree

### `[!]` `hot_region_depth` FAILS the transfer test and is dropped — one day after being built

| | 11 workloads, 1 floorplan | 6 floorplans |
|---|---|---|
| `hot_region_depth` vs retained | **+0.800** | **−0.886** |
| normalised by die span | +0.718 | −0.829 |
| `relative_plateau` vs retained | −0.647 | +0.829 |
| **`relative_plateau` vs COST** | **+0.843** | **+1.000** |

**The sign reverses**, and normalising does not rescue it. LADDER_GEN0 §3's own rule — *any metric
that does not predict is dropped* — applies to a metric I built the day before. It is **kept,
documented and tested as failing**, because a metric that fails cleanly is worth more on the record
than one quietly deleted, and it survives as a **within-floorplan workload diagnostic** only.

**And it is not alone**: `relative_plateau` reverses too when regressed against *retained
efficiency*. So saturation behaviour appears **not predictable from the temperature distribution
alone** by any of these metrics — it seems to need the absolute thermal scale as well.

### The scoreboard, and it is short

> **`[!]` SUPERSEDED 28 Aug 2026 — see P0.5f.** The transfer claim below does not survive
> floorplans built from published block areas: ρ falls from +1.00/+1.00/+0.83 to
> **+0.29/−0.06/−0.29**. All six floorplans regressed here were *uniform rescales* of one unit
> mix, so plateau width and die size were never independent variables. The +0.84 result over
> eleven workloads on one floorplan is untouched and still stands; the *transfer* is what fails.

Of five candidate phase-1 metrics, **exactly one predicts across both kinds of variation**:
**plateau width as a fraction of the die's own span, against the cost of holding a margin** —
ρ **+0.84** (11 workloads), **+1.00** (4 floorplans), **+1.00** (6 floorplans). Three independent
datasets, two kinds of variation, consistent throughout. Everything else is dropped or demoted.

- [ ] The six floorplans are still **area re-weightings with `calibrated = False`** — no ARM or
      RISC-V die shot with block annotations was found. Good enough to test metrics against; **not
      good enough to licence a design from**


## P0.5f — The ISA floorplans REBUILT on the floorplan pack  `[x]` 28 Aug 2026

`docs/chip_design_lit/MXL-HotGauge-Floorplan-Pack/` arrived with 165 rows of published block
areas and the only fully decomposed core in it. This is the rebuild. Evidence:
`docs/evidence/isa_floorplans_pack_rebuild.json`.

### The pack was verified before anything was built on it, and the three traps are now guarded

`HotGauge/HotGauge/thermal/pack_areas.py` + 19 tests. Every trap returns a plausible wrong
answer rather than an error, so each has a guard and a test that fails if the guard goes:

- **`block_areas.csv` mixes hierarchy levels.** Golden Cove's ten rows include four nested
  children; summing all ten overstates the core by **+9.55 %**, the correct six close to
  **−1.35 %**, Redwood Cove to **−0.04 %**. `non_overlapping_blocks()` is the only sanctioned
  way to get a chip's block set.
- *A refinement the README does not make*: `fpu_register_file` and `int_register_file` are drawn
  on the plate inside the **out-of-order** block, not inside the FPU and integer clusters their
  names suggest. Doesn't change the six; does change where that area sits.
- **`manifest.csv:category` is `die_floorplan_annotated`, not the folder name.** An unknown
  category now raises with the right value in the message rather than returning zero rows.
- **The V/F voltage column is `voltage_v`.** Two anchors carry one, both Neoverse at 0.75 V.

### `[!]` FOUR defects in the first cut, and the first two invalidate how a recorded result reads

1. **The vector multiple was never applied.** It was declared per variant, returned in metadata,
   printed by the generator — and nothing installed it, because `AVX_512_AREA_VS_FPU` is baked
   into `DERIVED_UNITS` at import and an area JSON cannot reach it. Measured: **`AVXs/FPUs =
   1.981` in all six floorplans on disk**, x86 and ARM and RISC-V alike. The axis the module
   called *"the largest single lever in the unit mix"* was never varied.
   **Read `isa_benefit_prediction_test.json` with this beside it**: PREDICTION_2 failed with the
   gap "ordered by nothing" and that file blames uniform scaling preserving the mix. True, but
   the cause is that every variant carried the x86 AVX-512 accelerator at full size.
   Fixed: `generate_ncore_floorplans.py --vector-multiple`.
2. **The variants were built from a different base area file than the baseline.** The tiler
   defaults to `adjusted_14nm-area.json`; the ISA generator defaulted to `14nm_unit_areas.json`,
   which differs by ×1.40 on every unit except the ALUs (×0.565). So every variant carried a
   different unit mix from the baseline it was compared against, for no ISA-related reason —
   residual 22.1 % of core on the baseline against 34.7 % on the variants. Both now default to
   the tiler's own file.
3. **Re-weighting emitted sliver blocks 3D-ICE could not solve, and they presented as runaway.**
   `floorplans.py::replace` emits a block for a parent's leftover only above 0.5 µm². McPAT's
   instruction scheduler carries 0.42 µm² more than its children — just under it, so the
   baseline emits nothing. Scale the scheduler to the published mix and the rounding artefact
   scales too: at 0.99 µm² it crosses the threshold and the tiler emits a sliver **509 µm wide
   and a few nanometres tall**, negative-area in some variants. 3D-ICE returned non-finite
   temperatures and every driver read that as thermal runaway — **a 62 mm² die "diverging" at
   12.5 W**, which is not a temperature at all. `_repair_parent_coverage` now clamps slack below
   1e-4 of the parent and raises a short parent to exactly cover its children; genuine internal
   residual (the fetch unit's 0.7 %) survives. All six now emit **1126 blocks, the baseline's
   own count**, with no degenerate dimension.
4. **The trace and the areas became two inconsistent models.** McPAT's areas and powers are
   outputs of one model; the pack publishes areas and **no per-block power for any part**. Its
   un-itemised core power lands on the tiler's `core_other` slab — 15.85 mm² at 1.4 W/mm²,
   **38 % of die power** — and the published mix shrinks that slab 32×, putting **28 W/mm²** on
   it. `--power-follows-area` holds every block's *power density* at its reference-floorplan
   value so only the arrangement changes. The rejected alternative (hold each block's power) needs
   McPAT's power for a block to be right while its area is wrong by up to 30×.
   **The cost is stated, not hidden: these floorplans compare geometry at constant activity
   density.** Per-block activity needs per-block power the pack does not have.
   The failed run is **kept** at `results/isa_benefit_pack_powerheld/` — 18 of 18 logs report
   RUNAWAY — because the failure mode is the evidence for the rule, and because defects 3 and 4
   were tangled in it: some of those dies fail for the sliver blocks and some for the power.

### Three corrections to the numbers

- **The vector multiple is 4.8× too large.** `configuration.mcpat` carries an explicit
  `# HACK: Fudge the AVX ratio to match die photos` targeting 10 % of die, and hits it (10.5 %).
  Golden Cove's FMA EUs on ports 0 & 1 are **0.288 mm² of a 7.123 mm² core — 4.04 %**, and
  against the rest of the FP cluster that is **0.413×** where the shipped constant is 1.981×.
  Every variant now uses 0.413 scaled linearly by published vector width.
  **The baseline is deliberately NOT changed** — the whole back catalogue rests on it, and the
  corrected core enters as the `x86_golden_cove` *variant* so the size of the correction is
  measurable. Acceptance: the shipped 34-core baseline regenerates **byte-identically** through
  the new code path, all three formats.
- **V1 against N1 is 1.80–2.19×, not the press claim's 1.70.** The first cut chained that claim
  onto an assumed N2 ratio and got 0.71× the baseline. The pack's own rows (V1 2.52 mm²,
  N1 1.15–1.4) put `arm_v1` at **1.19× the baseline — larger**, where the first cut had it 29 %
  smaller. The direction of the correction is the point.
- **The baseline core is small at iso-node.** Modelled core + 512 KB L2 at 7 nm is 2.116 mm²;
  published AMD Zen 2, same node class and the same 512 KB L2, is **3.54 mm² — 1.67×**.

### The mix, and this is the largest single change

Grouping the McPAT units into Golden Cove's six published blocks, as fractions of per-core area:

| group | our McPAT | Golden Cove | ratio |
|---|---|---|---|
| frontend | 10.40 % | 23.02 % | 0.45 |
| ooo | 5.13 % | 18.56 % | 0.28 |
| load/store | 12.64 % | 14.47 % | 0.87 |
| FP + vector | 22.23 % | 13.84 % | 1.61 |
| integer | 2.31 % | 5.64 % | 0.41 |
| L2 | 25.21 % | 23.11 % | 1.09 |
| **residual** | **22.08 %** | **1.35 %** | **16.4** |

**Every floorplan metric this project has validated was measured on a die a fifth of whose area
is one featureless `core_other` slab.** A real core, transcribed independently from the same
plate as its own total, closes to 1.35 %. `x86_golden_cove` is the same core with the published
mix and it is in the sweep to find out whether that changes the answer.

### `[!]` The decode argument cuts both ways now

`DECODE_FRACTION_OF_CORE = 3.34 %` has been this project's reason for retiring "x86 decode is
complex" as an architecture argument. **It is a McPAT output.** Golden Cove's frontend block —
branch prediction, decode, micro-op ROM, L1I and its control — is **23.0 % of the core** against
McPAT's 10.4 %, and the L1I inside it prices at ~2.3 % of that block from the plate's own L2
array density. The pack **cannot restore** the decode argument: its plate labels one block for
the whole frontend and never separates the decoder. What it removes is the *model's authority
for dismissing it*. Do not quote 3.34 % as a measurement.

### The core template — `accelerator_floorplan.py`'s pattern, applied to a CPU core at last

`HotGauge/HotGauge/thermal/core_templates.py` + 23 tests. Golden Cove / Redwood Cove as a
**placed** floorplan: published areas, arrangement read off
`images/floorplans/semianalysis__Intel_Meteor_Lake_005.png`, `source_image` per block, closure
asserted in the constructor so no rescale or re-weighting can escape it.

- **14 blocks, not 6.** The four nested children the naive sum double-counts are the pack's
  finest structure and all of it is used: the **FMA EUs** split out of the FP cluster (the block
  a vector-width argument is actually about), both register files out of the OoO block, and the
  L2 split into **control and four data arrays** — 384+256+256+384 KB, which sums to the printed
  1.25 MB and is the check that the labels were read right. SRAM and logic do not leak alike.
- **The arrangement is checked, not trusted.** `arrangement_consistency()` compares the area
  fractions this layout implies against fractions measured directly off the plate's *pixels* by
  colour segmentation — two independent readings of one design. Worst block 21 % (the L2),
  frontend agrees to **0.3 %**.
- **The rescale has a measured error bar.** Golden Cove → Redwood Cove is the pack README's own
  "scale by area ratio" recipe *with a published answer*: max **22 %** per block, mean 14 %, and
  the worst block is the L2 — which is what actually changed (2 MB against 1.25 MB). That is the
  honest error bar on every core built by the same route.
- **SRAM linearity is checked rather than assumed** — the pack's own L2-area-vs-capacity table
  (128 KB → 1 MB, three GPUs) is flat to under 1 %, which is what licenses pricing the 384 KB
  arrays off the published 256 KB block.
- **The published decomposition contains structure the catalogue's 50 µm grid cannot resolve**
  (the uncore residual is a 77 µm strip; the integer register file 329 × 310 µm). `write_flp`
  refuses a grid that distorts a block by more than 10 %; 20 µm is the coarsest that works.

### What the variants are now, and what they still are not

Seven floorplans, all 7 nm-class, all built through the shipped tiler:

| key | core+L2 | provenance | vector | W/mm² |
|---|---|---|---|---|
| `x86_skylake` | 2.116 mm² | model — **the unchanged control** | AVX-512 @1.981 | 0.620 |
| `x86_golden_cove` | 7.123 mm² | published | AVX-512 1024 b | 0.620 |
| `x86_zen2` | 3.540 mm² | published | AVX2 512 b | 0.620 |
| `arm_v1` | 2.520 mm² | published | SVE 2×256 b | **0.476** |
| `arm_n1` | 1.150 mm² | published | NEON 2×128 b | **0.870–1.286** |
| `arm_a64fx` | 2.220 mm² | derived | SVE 512 b ×2 | none published |
| `riscv_xiangshan` | 2.298 mm² | derived | RVV 128 b ×2 | none published |

- **Areas** are published for four of seven; `arm_a64fx` and `riscv_xiangshan` have **no
  published area anywhere in the pack** and keep the derived route, which is why their absolute
  size deserves more suspicion than their shape.
- **The mix** is Golden Cove's, moved by each variant's own cache capacities and vector width.
  **No ARM or RISC-V core decomposition is published in the pack** — the three RISC-V layouts
  are unit-coloured renderings with no printed areas and the Arm rows are core-plus-L2 totals.
  So the mix is an x86 core's on two published axes, which is stated rather than hidden and is
  still far better than McPAT's, which misses the one published measurement by up to 3.6× per
  group.
- `calibrated` stays **False** everywhere and keeps its original meaning — nothing was measured
  off silicon by us. `area_provenance` is the field that says what each area actually is.
- **Retired, not deleted**: `arm_n2` (×0.42), `riscv_p670` (×0.30) and the press-ratio `arm_v1`
  (×0.71) are recorded in `RETIRED_VARIANTS` so results on disk stay interpretable.

### The W/mm² priors are wired, and note their shape

Six Arm rows carry area **and** power on the same row. The **wide-vector V-class runs at roughly
half the power density of the compact N-class** — V1 0.476 and V2 0.560 against N1 0.870–1.286
and N2 0.909–1.538. A wide machine spends area to go fast at a low clock; a compact one spends
clock. That is an *activity* difference and no amount of area re-weighting can see it, which is
exactly why every ISA result before this one redistributed the Skylake trace at a common density.
`scripts/isa_benefit_pack.sh` runs a `published` arm at each part's own density beside the `iso`
arm at 0.60 W/mm². **Still a geometry comparison inside the core**: the pack gives no per-block
power for anything.


### `[!]` THE RESULT: `relative_plateau` does NOT transfer to the rebuilt floorplans

`scripts/isa_benefit_pack.sh`, `examples/isa_metric_transfer_report.py`,
`docs/evidence/isa_metric_transfer_pack.json`. Six floorplans × three margins, **everything but
the floorplans held identical** to the 28 Aug sweep — same 0.60 W/mm², same margins, same 500 µm
pitch, same 200 µm burial, same uniform activity. `x86_skylake` is unchanged and reproduces its
old numbers to the digit (peak 63.08 °C, plateau 17, cost 0.4908 W), which is the control that
makes the comparison a comparison.

| dataset | ρ(plateau, cost) at 3 K | 5 K | 8 K |
|---|---|---|---|
| six press-ratio floorplans, 0.60 W/mm² | **+1.000** | **+1.000** | **+0.829** |
| six pack-rebuilt floorplans, 0.60 W/mm² | **+0.290** | **−0.058** | **−0.290** |
| six pack-rebuilt, each at its own published density | **+0.725** | **+0.551** | **+0.319** |

n = 6 floorplans at every margin. **Neither rebuilt arm reproduces ρ ≈ +1.0**, and neither is
significant. The iso arm is the like-for-like re-run — same density, same everything — and there
the metric is indistinguishable from noise. Running each part at its own density leaves it weakly
positive, in the registered direction, at roughly half the strength claimed.

**Why, and it was foreseeable.** Every floorplan in the earlier six was a *uniform rescale* of one
McPAT unit mix, so the only thing varying was compaction — and plateau width and die size are both
monotone in compaction. They were never independent variables. The rebuild moves block mix, block
sizes and vector width independently of die area, and the metric stops predicting.
**The transfer result recorded in `isa_microarchitecture_variants.json` was a property of that
family of re-weightings, not of designs** — which is exactly the outcome the 28 Aug handoff named
as the reason to run this.

**What predicts instead — a PANEL, not a result.** With the registered metric failing, the same
points were regressed against six other quantities. Reported because a negative result demands
knowing what *does* predict, not as candidates that have passed anything:

| quantity | old six, iso | rebuilt six, iso | rebuilt six, published density |
|---|---|---|---|
| `relative_plateau_25pct` *(registered)* | +1.00 / +1.00 / +0.83 | +0.29 / −0.06 / −0.29 | +0.73 / +0.55 / +0.32 |
| `peak_to_runner_up_gap_K` | −0.94 / −0.94 / −0.66 | **−1.00** / −0.77 / −0.60 | −0.83 / −0.77 / −0.54 |
| `die_span_K` | −0.77 / −0.77 / −0.94 | −0.66 / −0.89 / −0.94 | −0.14 / −0.83 / **−0.94** |
| `unaided_peak_C` | −0.77 / −0.77 / −0.94 | −0.66 / −0.89 / −0.94 | −0.26 / −0.77 / −0.89 |
| die **area** | −0.71 / −0.71 / −0.89 | −0.66 / −0.89 / −0.94 | −0.14 / −0.20 / −0.26 |
| die **power** | *(same variable)* | *(same variable)* | −0.31 / −0.66 / −0.60 |

**The bottom two rows are the reason the second arm exists.** At fixed density, die area and die
power are the same number and cannot be told apart. Give each part its own published density and
they separate: **die area stops predicting almost entirely (−0.14 to −0.26) while die power keeps
signal (−0.31 to −0.66)**. So what the iso arm was reading as "bigger dies are cheaper to cool"
is at least partly "hotter dies are more expensive", which is a different claim about a different
quantity.

**None of this is validated.** n = 6, seven quantities were examined, one was registered in
advance, and in the `iso` arm die area and die power are the *same variable* (power = density ×
area) — which is why the `published` arm exists. They are hypotheses to register and test on data
that was not used to pick them.

**What IS established is the negative.** The ρ ≈ +1.0 transfer recorded across six floorplans
does not reproduce on floorplans whose block mix and block sizes move independently of die area,
under either power rule. It sat at +1.00 because the six floorplans it was measured on were
uniform rescales, and it drops to +0.29 or +0.73 depending on a choice — how to power a die whose
areas did not come from McPAT — that the metric should not be sensitive to at all.

`die_span_K` is the one quantity strong in every dataset and every arm (−0.77 to −0.94 at the
larger margins), which is consistent with the `hot_region_depth` failure and its note that
saturation "seems to need the absolute thermal scale as well". Cost looks the same way. **That is
a hypothesis, not a result** — span was one of seven quantities looked at and none but the plateau
was registered.

**And one thing the metric result does not touch**: `x86_skylake` reproducing exactly means the
`--power-follows-area` rule is a no-op on a McPAT-derived floorplan, as it must be.

**`x86_golden_cove` has no steady state at 0.60 W/mm²** and is excluded from all three margins —
291 mm² at 175 W on an 88 CFM direct-die cooler. It is a *genuine* runaway (the backtracking loop
reached its minimum damping with the residual still growing), not the sliver artefact above, and
it is reported as absent rather than folded in as a large cost. A runaway is not an expensive
point; averaging it in as one would invert the ranking.

### The second arm: each part at its OWN published power density

`scripts/isa_benefit_pack.sh 1389 published` — Neoverse V1 at **0.476 W/mm²**, N1 at **0.870**,
the three x86 variants at the Tesla D1 die-level **0.620**, and `arm_a64fx`/`riscv_xiangshan` at
the iso value because the pack publishes no density for either, which the driver *logs* rather
than silently substituting. This is the swap the handoff asked for: the ISA comparison stops
redistributing the Skylake trace at one common density.

It also does something the `iso` arm structurally cannot. At fixed density, die area and die
power are **the same variable** (power = density × area), so the panel above cannot tell a
geometry effect from a thermal-scale one. Running each part at its own density separates them —
and at 3 K they *do* separate: ρ(die area) −0.40 against ρ(die power) −0.80.

**Still a geometry comparison inside the core.** The pack gives per-core W/mm² for six Arm rows
and per-block power for nothing, so the intra-core power shape is still the Skylake trace. An ISA
claim that rests on per-block *activity* is not answerable from this pack, and the module says so.

**And it makes the V-class visible for the first time.** At its own 0.476 W/mm², Neoverse V1 is
the second-largest die in the set (116.4 mm²) at the *lowest* power (55.4 W) and a 64.7 °C peak —
cooler than the compact N1's 76.3 °C on a die 40 % its size. It is also the **most expensive to
cool at 8 K** (2.92 W against N1's 2.04) because its plateau is the widest in the set. A wide,
low-density machine is a cool die and a bad hotspot target, and no amount of area re-weighting at
a common density could have shown that — which is the whole reason the Arm rows were worth
wiring in.

## P0.5g — One die per ISA, compared at matched die area  `[x]` 28 Aug 2026

`scripts/isa_isoarea.sh`, `docs/evidence/isa_isoarea.json`. 42 points, 36 convergent.

### The design, and why 34 cores everywhere was the wrong control

P0.5f's sweep ran every floorplan at **34 cores**, so the dies spanned **62–290 mm² (4.7×)** — and
since the metric work established that absolute thermal scale orders cooling cost, a per-ISA claim
from it is mostly a claim about die size. Holding the **die** at ~100 mm² and letting core count
vary is what a product comparison actually is. Spread falls to **1.15×** (94.9–109.2 mm²), and
`x86_skylake` stays at exactly 34 cores so the back-catalogue control is preserved.

| die | cores | die mm² |
|---|---|---|
| `x86_skylake` *(control, unchanged)* | 34 | 101.2 |
| `x86_golden_cove` | 10 | 104.2 |
| `x86_zen2` | 22 | 108.1 |
| `arm_v1` | 30 | 109.2 |
| `arm_n1` | 54 | 95.2 |
| `arm_a64fx` | 33 | 103.7 |
| `riscv_xiangshan` | 33 | 106.8 |

- **`--power-follows-area` needs a reference floorplan at the SAME core count.** The first launch
  failed 24 of 42 points on that and said so by name; `generate_ncore_floorplans.py --cores 22 30
  33 54` fixed it. The error message naming its own fix is why this cost minutes, not a session.

### `[!]` The absolute temperatures in this project are optimistic, by tens of kelvin

At matched die area **and** matched die power, the published-mix dies run **7–24 K hotter** than
the model-mix control with up to **1.9× the span**:

| die | peak | span | plateau | cost @3 K |
|---|---|---|---|---|
| `x86_skylake` (model mix) | **63.1 °C** | 30.5 K | 17 | 0.491 W |
| `arm_n1` | 69.8 | 39.9 | 68 | 0.732 |
| `arm_a64fx` | 73.1 | 43.1 | 32 | 0.367 |
| `x86_zen2` | 86.9 | 57.3 | 18 | 0.332 |
| `arm_v1` | 87.5 | 58.7 | 37 | 0.575 |
| `x86_golden_cove` | *no steady state* | | | |

**McPAT's 22 % unallocated slab was acting as a heat spreader a real core does not have.** This is
a result about the model, not about any ISA.

### `[!]` The hottest block on EVERY die in this project is an accounting entry

All six dies peak on the **results broadcast bus** — the unmodified baseline included. McPAT
publishes it as `Area Overhead`, and `floorplans.py` converts that overhead figure into a placed
rectangle:

```
# Make RBB Area instead of Area Overhead
stats['Core'][unit_name] = stats['Core'][unit_name + ' Overhead']
```

0.0019 mm² carrying 0.199 W on the baseline = **105 W/mm²**. ~~Real silicon runs 1–3, ten in a bad
hotspot.~~ **The identity of the peak block in every result this project has produced is an
artefact.**

> **`[!]` Corrected 31 Aug 2026 — the density argument struck above is WITHDRAWN.** Real blocks do
> not run 1–3 W/mm². The HotGauge paper (§II-A) reports **>8 W/mm² in a core**, literature hotspot
> definitions are 6.8–10, and our own measured distribution on these dies has block **p90 = 13.2
> and p99 = 64.4 W/mm²**, with `iBuf` at 141 and `cALU` at 65. RBB sits *inside* that
> distribution, so its density was never the evidence. **The evidence is the area semantics, and
> the McPAT source settles it**: `EXECU::EXECU` builds the bus from `interconnect` objects whose
> length is `rfu->int_regfile_height + exeu->FU_height + lsq_height` (+ `scheu->Iw_height` for the
> tag bus) — `RegFU`'s own comment reads *"the bypass buses need to travel across all the register
> files"* — and `core.cc:1265` folds that area into the Execution Unit's own. An `Area Overhead`
> is *itemised, and already inside its parent*; it is not a block. The compact rectangle is a
> fictitious footprint because of where the copper is, not because of how many watts are on it.

**But it is a small artefact, and that was measured rather than assumed.** It stands only
**0.2–3.9 K** above the next block, so deleting it moves each die's peak by at most ~4 K and leaves
the 24 K spread between dies intact. **The exception is the largest core**: the block's area scales
with the core, so on Golden Cove it carries **1.81 W** against the baseline's 0.199 W — and that is
the die with no steady state. **Golden Cove's runaway is the artefact, not an architecture
result.** Fixing this is one block and one line in the shipped tiler, and it is the prerequisite
for any per-ISA thermal ranking.

### The metric recovers at matched area, and not enough to rescue it

ρ(`relative_plateau_25pct`, cost), n = 6 at every margin:

| arm | 3 K | 5 K | 8 K |
|---|---|---|---|
| iso density 0.60 W/mm² | +0.60 | +0.54 | +0.31 |
| each part at its own published density | +0.60 | +0.66 | +0.03 |

Better than the +0.29 / −0.06 / −0.29 it managed with die area free to vary 4.7×, and nothing
significant. Dropping the one legacy model-mix die lifts 3 K to +0.90 — and decays to +0.50 by
8 K, which is what post-hoc exclusion looks like when it is not a real effect.

### `[x]` The one result that came out clean, and it is the Arm priors doing their job

Each part at the power density its vendor publishes, same die area, same cooler:

| die | cores | its density | die power | peak | plateau | cost @3 K |
|---|---|---|---|---|---|---|
| `x86_skylake` *(control)* | 34 | 0.620 | 62.7 W | 64.5 °C | 17 | 0.485 W |
| **`arm_v1`** | 30 | **0.476** | **52.0 W** | **73.5 °C** | 36 | **0.583 W** |
| `arm_a64fx` *(no published density)* | 33 | 0.600 | 62.2 | 73.1 | 32 | 0.367 |
| `riscv_xiangshan` *(no published density)* | 33 | 0.600 | 64.4 | 77.4 | 31 | 0.445 |
| `x86_zen2` | 22 | 0.620 | 67.0 | 89.6 | 18 | 0.319 |
| **`arm_n1`** | 54 | **0.870** | **82.8 W** | **92.3 °C** | 71 | **0.714 W** |

**V1 against N1 is the only comparison here published at both ends.** Same die-area class, same
cooler, each at its vendor's own density: the wide machine dissipates **31 W less**, runs
**19 K cooler** and is **cheaper to cool**. A wide, low-clocked core spends area to avoid density;
a compact one spends density to avoid area and pays thermally at both ends. **An activity
difference, invisible to any common-density sweep** — which is exactly why every earlier ISA result
here missed it.

**Two cautions that stop it being a verdict on ARM.** The core-internal power shape is still the
x86 trace, so this is an activity comparison at the *die* level and a geometry comparison inside
the core. And the N1 row takes the compact end of a published 0.870–1.286 W/mm² range — a 48 %
spread — so the size of the gap is a choice within the evidence even though its direction is not.

### The down-selection, and the three classes are not equally evidenced

| ISA | die | area | power | V/F | block mix |
|---|---|---|---|---|---|
| **ARM** | Neoverse V1, 2.52 mm² + 1 MB L2, 7 nm | published | published | published | inherited |
| **x86** | Golden Cove, 7.123 mm², Intel 7 | published | borrowed (Tesla D1) | none | published |
| **RISC-V** | XiangShan Kunminghu | **derived** | none | none | inherited |

**ARM is the best-evidenced part in the pack** — V1 is the only row anywhere carrying area, power
and voltage together, so it is the only part where area → power → V/F closes without an assumption.
**x86 is the best decomposed.** **RISC-V cannot be modelled to the same standard**: no published
RISC-V *core* area exists anywhere in the pack. Only Ventana Veyron V1 prints a number at all —
62.5 mm² for a *16-core cluster* on N5 — and it is worth carrying as the cross-check beside AMD
Bergamo's 16-core CCD at 69.5 mm² on the same node. **Anyone quoting a RISC-V core area from this
work is quoting an output of our own model.**

## P0.5h — Zone separability, and the extraction policy re-examined  `[x]` 29 Aug 2026

Driven by `docs/Photonic_Cooling_Devices___v9.pdf` §§1.14 and 10.8, which make leakage suppression
and per-tile temperature first-class objectives. Two new modules, 34 tests, two evidence files:
`docs/evidence/thermal_zone_separability.json` and `leakage_targeting_policy.json`.

### The premise checks out, and more sharply than the book states it

Static is **34.6 %** of die power on our trace (§10.2 assumes ~30 %). The sharper point: **89 % of
all leakage is in L3 alone**, L2-within-core is 80.3 % static, the FPU 0.3 %. The cold zone is not
a partition anyone has to impose — it is already where the leakage lives, in one contiguous
structure.

### `[!]` But no floorplan here can hold the gradient — by three orders of magnitude

`thermal_zones.py`. The metric is a **power balance**, not a geometric score: leakage saved versus
heat conducted back across the zone boundary.

| cold zone | boundary | conductance | allowed | short by |
|---|---|---|---|---|
| L2 inside a Golden Cove core | 2.57 mm | 0.457 W/K | 1.5e-4 | **3 039×** |
| L3 across the 34-core die | 122 mm | 21.8 W/K | 3.4e-3 | **6 322×** |

To save 22 mW of L2 leakage you must remove **68 W** of parasitic in-flow.

- **Die thickness cancels.** Q = k(P·t)ΔT/L, and in a monolithic die the healing length is not
  free — a step heals over ~the slab thickness — so **G = k·P, independent of thickness**. Thinning
  shrinks cross-section and healing length equally. The answer does not depend on the parameter a
  reader would most want to argue about.
- **Silicon gets worse as it cools**: k rises 148 → 266 W/m·K from 300 K to 200 K as umklapp
  scattering freezes out. The colder the zone, the better its surroundings conduct into it.
- **The 34-core die is worse than one core** because the tiler interleaves L3 with the cores —
  122 mm of boundary. Cache laid out for latency is cache laid out for maximum zone boundary.
- **Disaggregation is necessary and not sufficient.** A 1 mm package gap beats monolithic silicon
  by ~44×, against 3 000–6 300× required. The cold zone must be a separate die **and** the package
  needs a deliberate thermal break. A packaging programme, not a floorplan optimisation.

### The extraction policy: a secondary term, not an inversion

`leakage_targeting.py`. Allocating by **marginal leakage benefit** `B = s·(dP_leak/dT)` instead of
temperature excess. It wins on its own objective — **1.45× to 10.6×** more leakage removed for the
same watts — but:

- **The lever is small: peak benefit 0.017 W per W removed**, near 360 K. **Leakage payback alone
  never justifies the cooling**; the justification stays on the performance side, which
  `clipping_plan` already optimises.
- **So the settled decision needs a secondary term, not an inversion.** It conflates *projection*
  (a block's removal lands on the tiles above it — geometry, correct, still guarded by
  `TestExtractionTracksPowerDensity`, untouched) with *allocation* (how much each block gets). Only
  allocation is in question.
- **Non-obvious result**: the most valuable block to cool is **not the hottest**. The measured
  curve's doubling constant is 10.7 K at 360 K but 13.3 K at 380 K, so the relative response peaks
  mid-range. Pinned by a test, because the obvious intuition is wrong.
- **`[!]` And it currently chases an artefact**: every scenario sends its watts to `core_other`,
  the 22 % unallocated slab. A leakage-targeted policy is only as good as the per-block leakage
  attribution, and ours puts the most leakage in a block that does not exist. **Same root cause as
  the broadcast-bus defect in P0.5g** — one blocker, not two.

### `[!]` The domain limit that bounds the whole architecture argument

**McPAT rejects temperatures outside 300–400 K outright.** §10.8's template spans 150–600 K; our
power model is valid over 300–400 K. Only the middle zone is inside it.

- **Cold end**: our curve stops at 310 K and *clamps* below. §10.8 claims 100–200× leakage
  reduction for 350→200 K; our local doubling constant is already **274 K at 310 K** — essentially
  flat — which would give ~2×. Whether that early flattening is a real gate/BTBT floor or a McPAT
  artefact **decides the cold-zone prize by ~50×**, and it is the highest-value open question in
  the architecture argument. **PTM SPICE cards (ptm.asu.edu, free, 7 nm) would settle it.**
- **Hot end**: extrapolating to 600 K gives ~1e5× leakage. Silicon is not viable there, which is
  why §10.8 specifies SiC/GaN and refractory metal — so the hot-zone claim is a **materials** claim
  and nothing in this toolchain can evidence it. The exergy half needs no model (φ = 1 − T₀/T_h is
  exact); every chip-side consequence is unmodelled.

## P0.7 — The power-recovery reframing, and the tests it demanded  `[x]` 29-30 Aug 2026

Driven by `docs/Photonic_Cooling_Devices___v9.pdf` §§1.4, 1.10–1.17, 10.8. Programme document:
**`docs/POWER_RECOVERY_PLAN.md`** — read that first, it states the objective change.
Modules: `exergy.py` (22 tests), `thermal_zones.py`, `leakage_targeting.py`.
Drivers: `thermal_zone_probe.py`, `exergy_map.py`, `exergy_vs_cop.py`.

### The objective changed, and it is not a refinement

Heat lifted at `T_h` carries exergy `φ = 1 − T₀/T_h`, so **hotter waste heat is worth more**.
`exergy.py` reproduces the book's table exactly (0.157 / 0.262 / 0.410 / 0.508 / 0.579 at
350/400/500/600/700 K). The self-powering condition (1.15) goes from **impossible to plausible**
across that range: required `η_AS` falls **1.77 → 0.55**. So `T_h` is a design knob, and
"cool everything" stops being obviously right — dynamic-dominated logic wants to run hot,
static-dominated SRAM wants to run cold.

### Test 2 `[x]` — the extractor's temperature, and a counter-intuitive answer

`φ` is set by the reservoir the heat is lifted **from** — the extractor, not the junction. Swept
burial × pitch × density, array present at zero power.

- **The drop is large and pitch-dominated**: up to **99.4 K** at 200 µm burial / 2000 µm pitch /
  50 W/mm². At fixed depth and density, 100 µm pitch gives 10.1 K and 2000 µm gives 99.4 K.
- **But the `φ` error is small, and non-monotonic**: the overstatement from using junction
  temperatures never exceeds **8.2 %** across a 100× density range, and it does *not* fall
  monotonically — 6.1 % at 0.6 W/mm², **peaking at 8.2 % near 2 W/mm²**, then 6.8 % at 10 and
  2.8 % at 50. *(An earlier reading of this table called it "worst at low density"; that was
  wrong.)* The fall at the top is `φ` saturating — 872 K against 972 K moves it only
  0.742 → 0.763, so a 99 K drop costs under 3 %. The rise at the bottom is the opposite limit,
  where `φ` is small enough that 1 K is a few percent of it.
- **Verdict: the prerequisite is discharged.** Reading `φ` off junction temperatures is defensible
  to ~8 %, smaller than most other uncertainties in the framing, so Tests 3 and 4 do not need
  correcting. *(The 10 and 50 W/mm² rows put silicon at 200–970 °C and run without leakage
  feedback — a conduction result, not a claim that such a die works.)*

### Test 1 `[x]` `[!]` — the die cannot hold the gradient, and two methods agree it cannot

Escalating removal over the cold zone (L2/L3, measured 80.3 % and 97.7 % static), hot zone
uncooled. Achieved gradient, 34-core die dissipating 60.7 W:

| removed | 0 W | 2 W | 5 W | 10 W | 20 W | 40 W |
|---|---|---|---|---|---|---|
| gradient | 0.00 K | 0.07 K | 0.18 K | 0.35 K | 0.70 K | **1.24 K** |

Roughly **linear at ~0.031 K per watt**, no saturation — 40 W removed, *two-thirds of the die's
entire power*, buys **1.24 K**. §10.8 asks for 150 K.

**And it confirms the closed-form model from P0.5h.** For this zone definition the boundary is
124.6 mm, so `G = k·P = 16.8 W/K` and 150 K needs **2 516 W** analytically; the solver says
**4 307 W**. **Two independent methods — algebra and 3D-ICE — agree within 1.71× on a quantity
spanning three orders of magnitude**, with the analytic one optimistic as expected since it counts
only the direct boundary path.

**`[!]` The full matrix separates TWO independent failure modes, and both must be fixed:**

| pitch | K per W removed | watts for 150 K |
|---|---|---|
| 100 µm | 0.0348 | 4 307 |
| 500 µm | 0.0309 | 4 856 |
| **2000 µm** | **0.0002** | **810 000** |

1. **The array cannot ADDRESS the zones at coarse pitch.** At 2000 µm the gradient essentially
   vanishes — 0.01 K for 40 W, **170× worse** than at 100 µm — because a tile straddling the zone
   boundary cools both sides equally. Note the device's own first-generation 4–16 tiles is
   **2.5–5.0 mm** on the 34-core die, i.e. coarser than the case that fails completely.
2. **Lateral conduction shorts the zones even at fine pitch** — 0.0348 K/W is still ~70× short.

These are independent: a fine array on a monolithic die still fails on conduction; a disaggregated
die with a coarse array still fails on addressing. That raises the bar rather than offering two
chances to clear it.

**A refinement, not a contradiction**: a 50 µm die beats a 200 µm one (0.0348 vs 0.0215 K/W).
Thickness cancels in the *lateral* boundary conductance (`G = k·P`) but not in the *vertical* path
from array to active layer — a thinner die delivers more of the cooling. Two different mechanisms,
both real, worth ~1.6× here.

**Verdict: the monolithic three-zone template is not buildable.** This does not refute §10.8, it
*relocates* it — the cold zone must be a physically separate die with a deliberate thermal break,
making this a **packaging and disaggregation programme before it is an architecture one**.

### Test 3 `[x]` — the exergy map

`docs/figures/exergy_map.png`, no new solves. Recoverable exergy on the four dies runs
2.65–5.47 W against 42–70 W dissipated (mean `φ` 0.062–0.078). **Collapsing a die to one
power-weighted temperature costs only 0.3–0.6 %** on the die integral — so the per-tile refinement
is a *visualisation* gain, not an accuracy one, at present temperatures.

### Test 4 `[x]` — a narrow frontier, and it is real

Re-scored the four extraction strategies on recovered exergy instead of peak reduction, computed
per block from the 1126-block field rather than from summary means.

- **The direction is shared**: both objectives reward concentrating removal on the hottest blocks.
- **The winners differ**: peak reduction favours `top5` (1.119 K/W vs hotspot 0.665); exergy
  favours `hotspot` (0.1367 vs 0.1313 W/W).
- **The trade is lopsided** — top5 buys ~68 % more peak reduction, hotspot only ~4 % more exergy —
  so the thermal objective should still decide and exergy should break ties.
- **What makes exergy worth carrying**: a watt removed at the peak is worth **76.7 %** more than
  one removed at the die average.

### Test 5 `[x]` — constant power, and it CORRECTS a recorded result

`scripts/isa_constant_power_pack.sh`, 42 points at 34 cores where areas span 4.7× (62–291 mm²),
so holding watts fixed isolates compaction. `docs/evidence/isa_constant_power_pack.json`.

**`[!]` All 42 points converge.** The 27 August run recorded *"24 attempted, 12 converged; both
compact dies diverge at both power levels."* That was substantially an **artefact of the power
model**: the old run kept McPAT's per-block *power* on re-sized blocks, so shrinking a die
concentrated watts into blocks whose sizes had changed but whose power had not. Driven with
`--power-follows-area`, `arm_n1` converges at 0.965 W/mm² and 83.0 °C. *(The physical point that
entry was making — a compact die is penalised twice, by density and by a worse spreading boundary
— survives and is visible below. The divergence does not. The transferable lesson, that any ISA
comparison holding watts fixed must scale the cooler with die area, is untouched.)*

**Compaction, cleanly isolated at 60 W:**

| die | area | density | peak | span | cost @3 K |
|---|---|---|---|---|---|
| `arm_n1` | 62.4 mm² | 0.965 | **83.0 °C** | 48.1 K | **0.483 W** |
| `x86_skylake` | 101.2 | 0.594 | 62.6 | 30.1 | 0.493 |
| `arm_v1` | 116.4 | 0.518 | 68.7 | 39.3 | 0.554 |
| `x86_zen2` | 154.7 | 0.390 | 63.1 | 35.6 | 0.497 |
| `x86_golden_cove` | 291.4 | 0.207 | **55.8 °C** | 31.4 | **0.666 W** |

**The compact die runs hottest and is CHEAPEST to cool — the opposite of the constant-density
result**, where compact dies were the most expensive. The two sweeps bracket the answer and
disagree because they hold different things fixed: at constant density a small die is cool and
flat, so there is no concentrated peak to clip; at constant power it is hot and concentrated, so
there is.

### Test 6 `[~]` — liquid against photonic  →  **superseded twice, see 6b/6c/6d**

`examples/liquid_vs_photonic.py`, `docs/evidence/liquid_vs_photonic.json`. Scored on
`P_die + P_cool − P_recovered` rather than temperature. One result from it survives; the headline
does not.

- **Good cooling is self-defeating for recovery.** `φ` is set by `T_h`, so the better the cold
  plate the colder the die and the less its waste heat is worth. That falls straight out of the
  ledger and it *is* the architecture argument. **This stands.**
- **`[!]` Self-powering is not the same as winning.** The loop self-powers at **450 K** (gain
  1.05) and still costs more net system power than the liquid loop. Self-powering says the loop
  pays for **itself**; it does not say it moves heat more cheaply than a pump. **This stands** as a
  distinction, but the specific margins (+26.4 W, +17.6 W) came from the defective comparison
  below and should not be quoted.
- **`[!]` WITHDRAWN — "recovery alone never beats liquid at any T_h."** Two defects, both found
  30 Aug 2026 on review:
  1. **One baseline.** The sweep loop ran `cold_plate_liquid` only and reported everything against
     it. Air and microchannel were tabulated and never paired with a laser. The cold plate is the
     *least* favourable partner available, on both terms at once.
  2. **No junction limit, at a fixed 250 W.** Nothing in either script checked `T_j`. At
     0.325 K/W the air baseline sits at **381.2 K = 108 °C** — past 100 °C and well past 85 °C. The
     comparison was scored on an operating point the cooler cannot legally run.

### Test 6b `[x]` — every cooler, alone vs. that cooler **plus** a laser

`examples/hybrid_cooling_ledger.py`, `docs/evidence/hybrid_cooling_ledger.json`. Fixes defect 1.

- **The baseline sets both terms of the photonic ledger, in the same direction.** It fixes `T_h`
  — hence `φ`, hence recoverable fraction — *and* the pumping power the laser displaces. Air runs
  at 381.2 K (φ 0.2262) against the plate's 312.5 K (φ 0.0560), **4.04×**, while costing 145 W
  against 12.5 W, **11.6×**.
- Per-watt breakeven, which is the whole decision (`f` cancels under a linear pumping model):
  air **0.580** baseline vs **0.543** laser → hybrid wins; cold plate 0.050 vs 0.645 → loses
  12.9×; microchannel 0.120 vs 0.661 → loses 5.5×.
- **`[!]` But the win is 3 rows of 72**, worth 0.2–1.2 %, all at `η_AS = 1.0` (~50× beyond
  demonstrated), and it flips if the fan-power extrapolation is halved. At `η_AS = 0.02` the fan
  hybrid costs **+2076 W**. And defect 2 still applies: that air point is illegal.

### Test 6c `[x]` — pricing the **rescue** of an otherwise-inoperable die

`examples/thermal_limit_rescue.py`, `docs/evidence/thermal_limit_rescue.json`,
`docs/evidence/rescue_measured_anchor.json`. Fixes defect 2, and is the comparison that means
something: below a cooler's limit the cheapest pump wins by construction (cold plate: system COP
**20**), so only the rescue regime is worth scoring.

- **The three mechanisms diverge by their exponents.** More airflow: `P_fan ∝ R^−5`, so a 900 W
  die needs a **35.8 kW** fan. Sub-ambient chiller: `COP = η₂T_in/(T_a−T_in)`, so system COP falls
  **20 → 0.15** across 4× overload. Laser at `T_j`: cost per watt **flat**, and recovery *rises*
  with `T_h`, so system COP floors near **1.8** instead of collapsing.
- **The contrast is where each machine is forced to work.** The chiller operates at the coldest
  point in the system, where its COP is worst and still falling as the rescue deepens; the laser
  at the hottest, where `φ` is largest. Opposite directions against the same variable — which is
  why a crossover exists and why it is not delicate.
- **The crossover is scale-free.** Required inlet temperature depends only on the overload
  *ratio*, so at `η_AS = 0.2` the laser overtakes at **2.64× / 2.88× / 2.85×** the unaided limit
  for fan, cold plate and microchannel alike. The baseline sets the absolute watts, not the
  crossing point.
- **`[!]` Against the repository's own measured rescue, the chiller still wins today.** The
  34-core die at d1.15 runs at **133.8 °C** unaided and is held at **90.6 °C** by the array — a
  genuinely inoperable chip made operable, through the coupled solve. The same rescue by chiller
  needs only **41.8 K** of depth, where COP is still 2.47: **163.8 W** system against the array's
  **230.7 W**. The laser overtakes past ~**100 K** of depth. **`[!]` Corrected 30 Aug (Test 7)**: the recovery term in the recorded study was first-law and 1.419x too favourable to the array; the figures here are the second-law values. The rescue framing locates where the
  win starts; it does not hand it over.
- **`[+]` NEW — the rescue pays for a quarter of itself in leakage.** Holding d1.15 at 90.6 °C
  instead of 133.8 °C drops what the chip draws from **124.9 W to 91.7 W**, **26.6 %**. That takes
  the array from **2.473 W/W gross to 1.683 W/W net**, about 1.5×, and it is largest exactly where
  the rescue is most needed. This credit was in the evidence and no ledger had counted it.
- **Not priced, both favouring the laser**: a 258 K inlet is far below dew point, so the chiller
  route needs the enclosure sealed against condensation — a build problem, not a power one — and
  the laser creates no sub-ambient surface at all.

### Test 6d `[x]` — the **aimed** rescue, charged only for the hotspot

`examples/aimed_vs_bulk_rescue.py`, `docs/evidence/aimed_vs_bulk_rescue.json`. 6c charged the
array for *bulk* die power and said its crossovers were conservative. This is that case. Metric
is **kelvin of peak reduction per electrical watt**, because that is what a thermal limit spends.

- **`[+]` Granularity converts spatial structure into efficacy, and only that.** Measured, 2000 µm
  → 50 µm pitch: **1.90×** on a concentrated hotspot (0.977 → 1.854 K/W) and **0.69×** on a
  uniform die — that is, nothing. Fine pitch is not a general good. It follows that **array value
  cannot be quoted per-die**: the same hardware is worth **2.77×** more on one shape than another,
  so it is a property of workload and floorplan, not of the part.
- Aimed array **0.750 K/W** electrical (**1.102** net of leakage) against the chiller's **1.032**
  at 42 K and falling. So charged gross the aimed array **loses** at 42 K and overtakes only past
  **112.5 K** of depth; with the leakage credit it overtakes at **24.5 K**. On a uniform shape it
  manages 0.395 K/W and needs **201.5 K** — the ordering reverses. **`[!]` Corrected 30 Aug (Test 7)**: the recovery term in the recorded study was first-law and 1.419x too favourable to the array; the figures here are the second-law values. More airflow is never competitive: 0.054 K/W at 10 K, ~0 past 20 K.
- **`[~]` Efficacy does fade with budget — but not the way this test inferred.** Comparing the
  3 W measurement against the 42 W rescue on a *different* die suggested a smooth **1.81× fade**
  and a gross loss to the chiller. **Test 6e holds the die fixed and shows the magnitude is right
  and the shape is wrong**: efficacy is flat to 16 W, then cliffs when the target stops being the
  peak. The "loses gross at 42 W" reading was the far side of that cliff, not an operating point.
- **The measurement that would settle it**: a budget sweep on **one** shape, 1 W → 45 W. **Run —
  see Test 6e.** It reproduces the fade's magnitude and refutes its shape.

### Test 6e `[x]` — the budget sweep, on one shape

`scripts/mr_budget_sweep.sh`, `examples/mr_budget_saturation.py`,
`docs/evidence/mr_budget_saturation.json`. Ten solves, 1 → 45 W, holding die, shape, target, pitch
(50 µm) and burial (200 µm) fixed. Only the budget moves.

- **`[+]` Efficacy is FLAT at 1.854 K/W from 1 W to 16 W** — not a percent of decay across a 16×
  range — and 16 W is exactly what the target block itself dissipates. Then it falls off a cliff:
  marginal efficacy drops **1.854 → 0.133 K/W** between 24 and 32 W.
- **The cause is in the solve.** Up to 16 W the target *is* the die peak (`target_C == peak_C` to
  the millikelvin); by 24 W it is not — another block has become the hottest thing on the die, so
  every further watt aimed at the original target buys almost nothing.
- **Test 6d's fade was right in magnitude and wrong in shape.** At 45 W this gives 1.030 K/W
  against the 34-core rescue's 1.027 on a *different* die — a striking agreement — but it is not
  gradual saturation of a local region. It is a **discrete event at a predictable budget**.
- **`[+]` The practical rule.** The right array budget is the one that **levels the target with
  the runner-up**, and past that the answer is to **re-aim**, not to spend more. That budget is set
  by `peak_to_runner_up_gap_K` — the floorplan metric this project measured, found weaker than
  `relative_plateau` as a cost predictor, and nearly set aside. It is weak at predicting cost and
  it is exactly the right quantity for **sizing a plan**.
- **Against a chiller at 42 K of depth (1.032 K/W electrical):** the array **never leads gross at
  any budget**, and leads **net of leakage only up to 24 W**. **`[!]` Corrected 30 Aug (Test 7)**: the recovery term in the recorded study was first-law and 1.419x too favourable to the array; the figures here are the second-law values.
- **`[!]` What this does not show.** A single-target plan. The measured 34-core rescue spread
  across **1126** targets, so a real planner re-aims as the peak moves and would not drive one
  block off this cliff. The cliff bounds how far **one aim point** can be pushed, not how far an
  array can be. One pitch, one shape, linear solves without leakage feedback.

**`[!]` What the five tests together license.** The array's case is *not* "cheaper cooling" — on
every bulk comparison run it loses to a pump. It is **"the only mechanism that can be aimed"**,
worth having exactly and only where the die is hotspot-limited, and worth more the deeper the
rescue, because it is the one mechanism whose cost per watt does not diverge with depth. Recovery
improves that ledger by roughly a factor of two; it does not carry it.

### Test 7 `[x]` — reconciling the two loop models  `[!] retroactive`

`examples/reconcile_loop_models.py`, `docs/evidence/loop_model_reconciliation.json`,
`docs/MCPAT_HIGH_TEMPERATURE.md`. Found because the diverged leakage runs printed a *net-generating*
cooling loop at shipped defaults.

- **Two statements of the same loop disagreed.**
  `MRParams.breakeven_ratio = η_laser·η_LPC·coll·(1 + η_ASF)` against
  `exergy.loop_gain = η_L·η_c·(1 + η_AS·φ)`. **`η_AS` and `η_ASF` are the same quantity**, so they
  differ by *exactly* φ multiplying it, and the first is the **φ → 1 limit** of the second, which
  requires `T_h → ∞`. Now verified identical to 1e-12 across 310–1000 K, with four tests locking
  them together.
- **`[!]` It flipped a verdict.** The first-law form returns **1.032 and reports the loop
  net-generating**; the second-law value is **0.821 at 350 K** and **0.958 even at 1000 K** — it
  never reaches 1.0 at any temperature silicon survives. The self-powering result was entirely the
  missing Carnot factor.
- **Why nothing caught it.** The guard is `first_law_ok`, testing `recovered ≤ gross + heat`. That
  is the *first* law and it passes — the energy really is there. It is the *second* law that
  forbids converting it at that efficiency, and nothing was testing it. `mr_accounting` now stamps
  `second_law_bounded`, `T_h_K` and `phi` on every result.
- **`[!] Retroactive scope.** Every `mr_accounting` figure recorded before 30 August 2026 used the
  optimistic term** — including the recovery credits in `mr_rescue_cost_34core.json` and every
  `p_mr_net_W`. Behaviour is unchanged by default so those results still reproduce exactly, but any
  *recovery* number from them is an upper bound. Costs quoted as gross laser draw are unaffected.
  `examples/mr_clipping_study.py --recovery-at-junction` recomputes the ledger at the measured
  junction temperature.
- **`[!]` A SECOND error, found the same day against v91.** Equation (1.16) is
  `η_P·η_cpl·[1 + η_ASF·φ] ≥ 1` — **η_LPC has already been eliminated** by substituting its exergy
  ceiling (1.14). I had been passing `η_LPC × collection` as the coupling term, double-counting the
  LPC and inflating the requirement. Corrected against the book's own worked Examples 1–3 (§1.12),
  which `exergy.eta_AS_required` now reproduces to three figures. Required η_ASF at 600 K falls
  **0.548 → 0.347**; at 400 K **1.062 → 0.672**, so the "impossible below 400 K" claim is
  withdrawn.
- **`[+]` η_P is the binding term now, not the extractor.** The numerator is
  `1/(η_P·η_cpl) − 1`, very steep near unity. At η_ASF = 0.30 the self-powering temperature is
  **716 K at η_P = 0.85, 469 K at 0.90, 358 K at 0.95**. §1.12 Example 3 says the same of η_cpl: a
  20 % front-end loss roughly doubles the extractor target.
- **`[!]` The materials counterweight is withdrawn — Yb:YLF is superseded.** v91 Table 8.2 gives
  SMILES-R640-in-polymer and direct-bandgap GaAs/GaInP at **10³–10⁴ W/mm²**, against Yb:YLF's
  1–10. Table 8.1 gives η_ASF **0.124 at 680 nm → 0.221 at 740 nm** with η_EQE 0.99. Yb:YLF is now
  correctly scoped as the **cold-zone** material only. `PLATFORMS_V91` and `ZONE_EXTRACTORS_V91`
  are in `microrefrigeration.py`. **η_ASF ≥ 0.30 — our experimental claim, beyond Table 8.1's
  range — closes the loop in the 400–600 K hot-compute zone.**
- **`[+]` The recorded gap "η_AS(T_h) is not modelled" is answered structurally** by v91 §8.4: a
  heterogeneous die uses a different extractor per zone (Yb:YLF cold, Yb:ZBLAN warm, Ho³⁺/Tm³⁺
  fluoride hot, SiC:Er / GaN:Yb above 600 K). Per-tile temperature targeting requires per-tile
  extractor selection. The numerical η_ASF(T) curve within each window is still unmodelled.

### `[!]` McPAT above 400 K — assessed, and it is not the blocker

`docs/MCPAT_HIGH_TEMPERATURE.md`. The bound is one check (`McPAT/cacti/io.cc:1547`) guarding a
table: `double I_off_n[NUMBER_TECH_FLAVORS][101]` with **only 11 slots populated** (300, 310 … 400 K),
indexed directly as `I_off_n[tech][temp-300]` — hence the `%10` rule, since the gaps are
uninitialised memory.

**But McPAT is not in the temperature loop.** It runs once, offline, extracting leakage at
`DEFAULT_TREF_K = 360 K` — inside the window — and the feedback loop scales with *our own*
`LeakageModel` before calling 3D-ICE, which has no ceiling. Verified: nothing in
`converge_power_temperature` invokes McPAT. **The 400 K bound constrains the reference extraction
point, not the operating temperature.** What binds above 400 K is our leakage model's validity —
~100 lines of Python, not a C++ fork. Above ~500 K it stops being a tooling question at all:
silicon is no longer a switch there, and the hot zone posits SiC/GaN, which CACTI cannot represent.
**Recommendation: extend `LeakageModel.from_table_extrapolated` and settle it with PTM SPICE cards
— the same campaign already flagged for the cold zone. One effort settles both ends.**

## P0.11 — The ceiling has two terms, and neither is an accounting artefact  `[x]` 31 Aug 2026

`HotGauge/HotGauge/thermal/power_shape.py` + 10 tests, `examples/uniform_density_probe.py`,
`scripts/uniform_density_ladder.sh`, `docs/evidence/uniform_density_probe.json`. 16 solves.

### Why this and not a third block

`core_other` and `RBB` have each been removed once now, and the ceiling did not move either time —
remove one and the other runs away (§P0.9, §P0.10). **A ceiling that survives the removal of
whichever block happens to be hottest is not a property of that block.** So the next test varied
the map, not a block.

Two arms, **identical in every respect except how the same watts are spread** — same total power,
same die, same package, same leakage rule:

- **`shaped`** — the real McPAT map, rescaled to the target die average. Peak **174× the mean**,
  Gini 0.774.
- **`uniform`** — every block at the same W/mm². **Gini 0, peak == mean, asserted at run time.**
  No hot block, by construction.

Control arm only: the question is whether a steady state *exists*, which is a property of the die
and its package. Adding the array would have put the planner's path back into an experiment built
to remove confounds.

### `[+]` The result

| arm | holds to | first fails | hottest block when it fails |
|---|---|---|---|
| shaped | **0.60** W/mm² | **0.80** | `RBB_16` |
| uniform | **1.00** W/mm² | **1.20** | `core_other_5` |

**Both terms are real, and that is the answer:**

1. **Concentration is worth ~1.5×** (0.80 → 1.20 on first failure; 1.67× on highest holding). It
   is a property of how power is *arranged* — measurable with `floorplan_metrics`, and designable.
2. **`[!]` A perfectly flat die still dies at 1.0–1.2 W/mm².** With Gini 0 there is no hot block to
   blame, so that cliff is the **die-average limit of this package and this leakage model**. It is
   physics. The artefact hypothesis is finished after five eliminations.

**Cross-check that it is measuring the right thing:** the shaped arm's 0.60–0.80 bracket lands on
the independently measured **0.80–0.85 W/mm² grease cliff**, and the array arm of the same die
holds to 1.60–1.80 (§P0.10) — so the array roughly doubles the passive shaped cliff. Three numbers
from three different studies that had no reason to agree, and do.

### `[!]` What these numbers are NOT

The absolute cliffs are **not** the catalogue's. This probe is control-only, `--rbb-policy stock`,
and it applies a **flat die-wide leakage fraction (0.386)** rather than the per-unit split — a
uniform map has no per-unit identity to inherit one from. Both arms use the same rule so it cannot
favour either, and the *ratio between the arms* is the result. Any absolute density quoted for the
product case must come from the catalogue drivers, not from here.

---

## P0.10 — RBB lands as a policy, and the ceiling survives it  `[x]` 31 Aug 2026

`HotGauge/HotGauge/thermal/rbb.py` + 17 tests. Suite **790 passed, 1 skipped** (was 773).
`--rbb-policy {stock,amortized}` on `mr_comparison.py`, `mr_clipping_study.py` and
`clock_headroom.py`, stamped on every row; **default `stock`**, so an un-flagged re-run
reproduces the recorded catalogue.

### The area semantics are settled, and not by density

`[!]` The density argument in P0.5f and in both RBB evidence files is **withdrawn** — real blocks
do not run 1–3 W/mm²; our own p90 is 13.2 and p99 is 64.4, and RBB sits inside that. The case is
the McPAT source, and it is unambiguous:

- **`EXECU::EXECU`** (`McPAT/core.cc` ~1150–1259) builds the bus from `interconnect` objects whose
  *length* is `rfu->int_regfile_height + exeu->FU_height + lsq_height`, plus `scheu->Iw_height` for
  the tag bus. `RegFU`'s own comment (~989): *"the bypass buses need to travel across all the
  register files."* The area is real silicon — wire tracks — spread across the cluster.
- **`core.cc:1265`** folds that area into the Execution Unit's own. `Area Overhead` means
  *itemised, and already inside its parent*. It is not a block.

`[!]` But `floorplans.py`'s `# Make RBB Area instead of Area Overhead` is **stock** HotGauge,
present in the initial commit, and Fig. 5 shows RBB as a block. Amortizing is a deliberate
divergence from upstream, not a bug fix — hence a policy with `stock` as the default.

**Recipient set corrected while landing it.** `rbb_amortization.json` named `regs` and `iSched`,
which the tiler *subdivides*, so it silently excluded `iWin`/`fpiWin`/`ROB` — the scheduler blocks
the tag bus explicitly spans — and counted **204** recipients where the die has **272**. `AVXs` is
excluded deliberately: this pipeline forces it to zero power, so anything routed there would be
destroyed downstream.

### `[+]` The change is real and material

Same ladder, one flag apart (`scripts/rbb_bracket.sh`, 10 solves, `docs/evidence/rbb_bracket.json`):

| density | stock | amortized | Δpeak | ΔQ_mr |
|---|---|---|---|---|
| 1.20 | 93.96 °C | **87.24 °C** | −6.7 K | +3.1 % |
| 1.60 | 92.83 °C | **90.79 °C** | −2.0 K | **−20.4 %** |
| 1.80 | 78.07 °C | diverged | — | — |
| 2.00 | diverged | diverged | — | — |
| 2.40 | diverged | diverged | — | — |

**And the `stock` path is bit-for-bit unchanged.** All 15 arm x density points of the stock
bracket reproduce `results/overnight_forward/A_density` to better than 0.01 K, verdicts included.
The policy is genuinely additive: with the default flag, the pipeline is the one that produced the
catalogue.

No recorded result survives the switch unchanged. The 1.80 point is **not** usable in either
direction: stock converges there at 78.07 °C having lifted 181 W, far under its own 92 °C target,
so the planner overshot — the ladder is not monotone under either policy at that point.

### `[!]` And the ceiling did not move — RBB was never the gate on this die

Both policies fail at 2.00 and 2.40, on every arm. **At every diverging point the block the
leakage loop names is `core_other_0`, under both policies, at nearly the same temperature**
(d2.00: 3488 K stock, 3611 K amortized; d2.40: 15 760 and 16 417 K). RBB never appears.

`rbb_is_the_gate.json` measured RBB as the runaway on the **rebuilt ISA floorplans**, where
`core_other` had already been shrunk from 15.68 % of die area to 0.94 %. That says which block is
hottest *once `core_other` is gone* — not which block gates the ladder. On the standard 34-core
die the density ladder actually runs on, `core_other_0` is still the hottest thing on the die.

**This is the informative result.** Each candidate has now been removed once, and the ceiling did
not move either time: shrink `core_other` → RBB runs away, ceiling unchanged; amortize RBB →
`core_other` runs away, ceiling unchanged. A ceiling that survives the removal of whichever block
happens to be hottest is **not a property of that block**. That is the fifth hypothesis eliminated
by measurement, after the bulk floor, the leakage extrapolation, the array envelope and
`core_other` itself.

### Next, and it should not be a third block

Run the ladder on a **uniform power map**, where no block is hot by construction. If a flat die
also has no steady state at 2.00 W/mm², the ceiling is the package and the leakage model — physics
— and the artefact hypothesis is finished. If a flat die holds, the gate is concentration, and
*that* is a measurable property rather than a block to chase.

---

## P0.9 — The forward campaign, and the ceiling it found  `[~]` 30–31 Aug 2026

**102 solves, zero job failures.** `scripts/build_joblist.sh` + `scripts/campaign_inner.sh`,
eleven families. Run to produce evidence for the forward case; produced that, and also found the
boundary of what this toolchain can currently measure.

### What the campaign established

- **`[+]` 22 measured rescues.** Control has no steady state, array holds target. The strongest
  is the airflow family: across **20 → 120 CFM**, a 6× range, the unassisted die diverges at
  *every* airflow while the array holds at all of them. `overnight_campaign.json`,
  `airflow_ladder_solved.json`.
- **`[+]` The optics requirement is ~50 µm, not 10 µm.** Spot swept 1–100 µm: identical thermal
  result at every size, cost flat within 3 % to 50 µm then **+20 % at 100**. The floorplan
  explains it — median block min-dimension is **45.4 µm**. The requirement is set by the die, not
  the device. `spot_size_requirement.json`.
- **`[+]` Pitch ladder and budget cliff are robust to the 4× envelope refresh** — identical to
  three decimals, because both are set by spreading geometry and peak migration rather than by the
  actuator. `envelope_refresh_robustness.json`.
- **`[!]` But the fan-power claim is contingent, not present-tense.** At today's extractor,
  turning the fan down makes net system power *worse*: the array lifts more and costs more per watt
  than the fan saves, so the optimum sits at the baseline airflow. It moves to 60 CFM at the v91
  target with a 90 % laser and 30 CFM with logic run hot, worth 2.0 and 7.7 W.

### `[!]` The ceiling: high density is gated by an accounting artefact

Every high-density run — passing *and* failing — has `core_other_0` reaching thousands of kelvin
(**17 381 K** worst, on iteration 1) and a plan sized from that field at up to **849×** die power.
The code prints "treat the result as suspect".

- **`core_other` is the un-itemised slab**: power the model could not attribute, given an area.
  **15.68 % of die area** on the standard 34-core floorplan, where a real core carries ~1.35 %.
  It is not silicon. `high_density_artifact.json`.
- **It is not the leakage extrapolation.** The Arrhenius tail above 400 K is unbounded (36× at
  400 K, 184 000× at 600 K) and was the obvious suspect. Clamping it changes nothing: **10 of 10
  points give the same verdict both ways.** `leakage_clamp_bracket.json`,
  `leakage_extrapolation_gate.json`.
- **Nor is it the array envelope.** `dt_max` swept 20–300 K (6.7×) and `h_max` 250–30 000 W/mm²
  (120×), on a package where bulk sits at 39 °C. Every point diverges identically.
- The ceiling itself (**holds at 1.60–1.80, fails at 2.00+**) is reproducible across both leakage
  treatments — but it is a property of the artefact and **must not be quoted as where photonic
  cooling gives out**.

### `[!]` Withdrawn tonight

| claim | why |
|---|---|
| fan power falls as R^−5, worth 22–35 % system power | used the textbook affinity law; this project's `FanCoolingModel` is **linear in heat carried**, calibrated at 0.590 W/CFM. Confirmed by the campaign: 45 CFM draws 26.7 W against 88 CFM's 35.0 |
| `dt_max` is / is not the blocker | measured where the target sat below the bulk floor, then where the plan was sized from a 7703 K field. Both confounded |
| the array gives out at 2.0–2.4 W/mm² | same artefact |
| the leakage extrapolation is the runaway mechanism | asserted before the clamp ran; clamping changes nothing |
| McPAT's 400 K ceiling is not a constraint | true of the power map (T_ref = 360 K, run once) but the **leakage table** the loop scales with is built from McPAT over 310–400 K, so it bounds the trustworthy range indirectly |

### Next, in order

1. **Attribute `core_other`'s power.** The project has already done this once —
   `isa_floorplans.py` lands the residual at the published 1.35 %, and those floorplans measure
   0.78–1.11 %. Applying the same treatment to the standard floorplan is the unblock, and a
   controlled test on the ISA variants is running now (`results/core_other_test`).
2. **PTM SPICE cards.** Still the top item for the cold zone (curve clamps at 310 K, prize
   uncertain 2.3×) and for any claim above 400 K. It will *not* unblock high density on its own —
   the clamp test settled that.
3. Re-run the density and `dt_max` questions once (1) lands. Only then is there an answer to
   "where does the array give out".

### `[!]` The domain limits, restated because they bound everything above

**McPAT rejects temperatures outside 300–400 K.** §10.8's template spans 150–600 K; only the
middle zone is inside the model. The cold-zone prize is uncertain by **~50×** (our curve flattens
at 310 K where the book assumes it falls to 200 K) — **PTM SPICE cards would settle it**, and that
is the highest-value open item. The hot zone needs SiC/GaN and is a materials claim this toolchain
cannot evidence. `η_AS(T_h)` is not modelled at all, so every "hotter is better" statement carries
an unmodelled quenching ceiling.

## P0.8 — Beginning the deferred gaps  `[~]` 30 Aug 2026

Both gaps the ranked list deferred were **mis-stated**, and correcting the statement is most of
the work.

### `[!]` Transients are NOT blocked on trace length

Recorded as *"needs a trace longer than 3.2 ms"* in three documents. That is wrong, and
`docs/SUMMARY_2026-08-14.md` §6 already had the right version: **τ ≈ 2.2 ms**, so the 3.2 ms trace
covers ~1.5 τ. The blocker is that **the trace's burstiness sits in LoadQ / TLB / ICache / IMC
while the hot units are flat** — median unit swing 0.0 % — so pre-cooling has nothing to
anticipate. It needs a workload with phase behaviour in the **compute** units. That is a data
problem, not a modelling or trace-duration one, and it changes what to go looking for. Corrected
in `NEXT_SESSION.md` and `POWER_RECOVERY_PLAN.md`.

### `[!]` The V/F gap: the shipped table is better than this project has been saying

`docs/evidence/vf_anchor_check.json`. The pack supplies the **only real (V, f) points this project
has ever had** — Arm's PPA slide, 2.8 GHz at 0.75 V on both N7 and N5. Used as a spot check on all
three V/F sources:

| source | V at 2.8 GHz | error |
|---|---|---|
| **measured (Arm)** | **0.750** | — |
| shipped `VF_PAIRS`, raw interpolation | 0.747 | **−0.4 %** |
| shipped `VF_PAIRS`, α-power fit | 0.738 | −1.6 % |
| IRDS 2024 … 2037 | 0.493 … 0.352 | **−34 % … −53 %** |

**This cuts against the recorded position.** `LADDER_GEN0.md` §1 and `product_vf.py`'s docstring
both call `VF_PAIRS` *"a binning artefact rather than a device curve"*. That critique rests on its
**high end** — 1.4 V for 5.0 GHz, and an α-power fit that only reaches low RMS by driving α below
the physical floor of 1. **Both remain true.** What the anchor shows is that the criticism does not
generalise: at 2.8 GHz, where server parts actually run, the table is essentially exact.

**The distinction is frequency-dependent and has not been drawn before**: clock-search results in
the 2–3.5 GHz range rest on firmer ground than assumed; results near 5 GHz, where `vf_clamped`
verdicts are produced, do not.

**And IRDS is the one that misses** — 34–53 % low, consistently, across every node. Already marked
`calibrated = False`, but the size and consistency of the miss is worth recording: it is not a
conservative substitute for the shipped table at moderate frequencies, it is a different answer.

**What this does not establish**: one frequency, one vendor, two parts sharing an operating point.
Nothing here tests curve *shape*, which is what the α < 1 criticism is actually about. A second
anchor at a different frequency would be worth more than any re-fitting — and the pack lists the
routes (AMD `pp_od_clk_voltage`, ACPI `_PSS`, Intel MSR `0x198`), each a full curve for an
afternoon's work.

## P0.6 — Transient + modulated array  `[ ]`

*Correctly last. Needs a per-slot tile trace and a burstier workload trace.*

---

## Off the critical path — can start any time

- [x] **Phase 2(a) floorplans for ARM and RISC-V — BUILT 27 Aug 2026.**
      `HotGauge/HotGauge/thermal/isa_floorplans.py` + `examples/generate_isa_floorplans.py`,
      11 tests. JSON re-weighting handed to the **shipped tiler unchanged** — the tiler is not
      ISA-specific and should not learn to be.
  - **The ISA argument had to be restated first, and the module states it.** The instruction
    decoder is **3.34 % of core area** in our model, so "x86 decode is complex" cannot carry an
    architecture result. What can: **vector width** — the x86 baseline carries an AVX-512
    accelerator at **1.98× the base FPU area**, so vector hardware is ~3× the scalar FP block —
    and **core size at constant power**
  - Three variants, every ratio sourced: **arm_n2** (×0.42, NEON 2×128b), **arm_v1** (×0.71,
    SVE 2×256b — from Arm's published *"V1 is ~70 % larger than N1 at equal L1/L2"*, and
    0.42 × 1.70 = 0.71), **riscv_p670** (×0.30, RVV — SiFive's A78-class performance in ~half
    the area)
  - **Honest limits, recorded in the module and the evidence:** there are **zero ARM or RISC-V
    die shots** in the library (0 of 59), so unlike `accelerator_floorplan.py` nothing is
    measured off one — every ratio is a published *relative* claim and `calibrated` is False
    throughout. These re-weight **area only**; the power trace is still the Skylake-class one, so
    nothing depending on ARM-specific *activity* is answerable from them
- [x] **And they unblock the two metrics the workload regression could not test.**
      `power_density_concentration` and `thermal_aspect` were **constant** across all 33 points of
      the 27 Aug regression, because that sweep varied workload on one die. Measured across the
      four floorplans at uniform power — isolating geometry, no solve needed — both order
      **monotonically with core compaction**: Gini 0.811 → 0.835 → 0.852 → **0.861** and
      top-decile share 0.789 → **0.817** as the core shrinks. A more compact core concentrates
      power density, which is the direction the registered prediction expects
- [x] **The prediction was tested the same day — and it FAILED, which is the useful outcome.**
      `scripts/isa_benefit.sh`, 12 points (4 floorplans × 3 margins), everything but geometry held
      fixed. `docs/evidence/isa_benefit_prediction_test.json`.
  - **`[!]` Read (2) below with P0.5f beside it.** The vector multiple these floorplans declared
    was **never installed** — `AVXs/FPUs = 1.981` in all six, x86 and ARM alike — so the gap being
    "ordered by nothing" is not a limitation of area re-weighting. The input never varied.
  - **(1) falsified.** Compact dies came out **wider-plateaued and more uniform**, not narrower:
    plateau 17 → 59 → 54 → 71 and span 30.5 → 21.1 → 18.5 → 16.0 K as the core shrinks
  - **(2) not supported.** Gap is 2.00 K on x86 (AVX-512) but 0.54 / 0.07 / 0.00 on the variants —
    ordered by *nothing*, because scaling the whole core uniformly preserves the mix and leaves a
    degenerate peak. That is a limitation of area re-weighting as a method, not a finding about
    ARM or RISC-V, and it must be fixed before any vector-width claim rests on these
  - **(3) falsified.** x86 is the **cheapest** to cool: 3 K of margin costs **0.49 W on x86 against
    1.35 W on the most compact die**, 2.7× the wrong way
  - **The error was mine, and it is instructive.** The reasoning assumed constant die *power*;
    the sweep holds constant *density*, so a smaller die simply dissipates less — unaided peaks
    fall 63.1 → 42.9 °C. A cooler die is a flatter die. The confound was built into the
    experiment by holding the wrong quantity fixed
- [x] **The metric survived, and that is the result.** `relative_plateau_25pct` ordered cost
      **perfectly — ρ = +1.000 at every one of the three margins.** It had predicted cost at
      ρ +0.84 across eleven workloads on one die; it now predicts across four floorplans at one
      workload. **The metric transfers**, which is exactly the question the workload regression
      could not answer. A metric that survives its designer's prediction being wrong is better
      evidence than one that agrees with it
- [x] **Figure**: `docs/figures/isa_floorplans.png` — four floorplans on a common millimetre scale
      with their solved fields beneath, one temperature scale. Published in the handbook artifact
- [x] **DONE — and half the sweep has no steady state.** `scripts/isa_constant_power.sh`,
      24 points attempted, **12 converged**. Both compact dies diverge at **both** power levels,
      including 25 W where their densities are only 0.517 and 0.648 W/mm² — comfortably *under*
      the 0.80–0.85 W/mm² grease cliff measured on the x86 die.
      **They fail below the cliff because the cliff is not a property of density alone.** A compact
      die is penalised twice: 2.1× the density at the same watts, *and* a worse spreading boundary,
      which scales with die area (0.553 K/W at 53 mm² against 0.325 at 101 and 0.108 at 826).
      ~2.1× density into ~1.8× resistance ≈ 3.7× the temperature rise.
      **Read as a packaging result, not a verdict on an ISA**: at a *fixed cooler*, shrinking the
      die is thermally expensive in a way density does not capture, and the dominant term is
      exactly what a real compact part would cool differently. The transferable lesson:
      **any ISA comparison holding watts fixed must scale the cooler with die area, or it is
      measuring the package rather than the architecture.**
      Taken with the constant-density sweep the two bracket the answer and fail the original
      prediction for *different* reasons — cooler-but-costlier in one, no steady state in the
      other. `docs/evidence/isa_constant_power.json`
- [x] **The THIRD metric is built and validated.** `hot_region_depth(temps, fraction=0.05)` — the
      drop from the peak to the coolest of the hottest 5 % of blocks, a *share* not a count so it
      transfers across floorplans. No new solves; the eleven fields were already on disk.
      It separates the saturation split **cleanly — degrades 10.1–14.0 K, holds 19.5–33.0 K, a
      5.5 K gap with no overlap** — where `relative_plateau` overlaps by 30 blocks *in the wrong
      direction* and `peak_to_runner_up_gap` overlaps by 1.8 K and is not significant.
      Mechanism: as the margin grows the plan reaches further down the distribution; a steep fall
      below the top few per cent means a well-defined hot group, a shallow one means an
      ever-widening set of near-peak blocks. Robust from a 2 % to a 20 % share.
      **Status stated precisely: validated on eleven workloads over ONE floorplan.** It has not
      passed the transfer test `relative_plateau` has — the constant-power sweep left only two
      convergent dies, too few to regress. `docs/evidence/hot_region_depth_metric.json`
- [ ] ~~Next, and it is cheap (12 points): repeat at constant die power rather than constant
      density.~~ That isolates the compaction effect the prediction was actually about, and it is
      what the prediction should have specified. Nothing here says ARM or RISC-V cores are poor MR
      targets — what was measured is that smaller dies at constant density run cooler and flatter,
      which is nearly a tautology once stated plainly
- [ ] ~~The prediction is registered and not yet tested~~ (`docs/evidence/isa_floorplans.json`):
      a compact core should have a *narrower* plateau and larger span; a wide-vector core should
      stand further clear of its runner-up; **therefore both should be better MR targets than
      x86**, since the validated regression says cost rises with plateau width (ρ +0.84).
      **If that third part fails while the first two hold, the metrics do not transfer across
      floorplans and the regression that validated them was workload-specific** — which would be
      worth more than a confirmation. Testing it means running `scripts/shape_benefit.sh` against
      the four floorplans
- [ ] **Scope the QSim frontend** — decides whether Phase 2(b) is a build exercise in our own
      Sniper (which already ships ARM and RISC-V decoders, gated off) or a gem5 adoption
- [x] **~~Extend the V/F table past 5.0 GHz~~ — ANSWERED, not done.** 5.0 GHz is a *device* limit
      at 1.4 V, not a truncated lookup: the shipped fit demands 1.82 V for 5.5 GHz and 2.74 V for
      6.0, which is oxide breakdown. `vf_clamped` is therefore a result — voltage-limited, not
      thermally limited. Extending the table would model a supply that destroys the part.
      Corroborated by Gonzalez et al. 1997 (`docs/LITERATURE_MAP.md` §1): the shipped fit's
      **α = 0.949 is below the physical floor of 1.0**, which is why the curve turns over at
      9.40 V and reports a spurious 6.43 GHz ceiling. `irds_vf.DEFAULT_ALPHA = 1.4` is correct.
      **The open item is a defensible product V/F curve, which is a different job** — see
      `docs/NEXT_SESSION.md` "Item 3"
- [ ] **Restate the §4 ISA hypothesis** around vector width / execute cluster before running it —
      decode is 3.3% of core area in the model we use and cannot carry the argument
- [ ] **Reframe the V_t rung as multi-V_t SPATIAL ASSIGNMENT, before running it.**
      `LADDER_GEN0.md` currently frames it as lowering V_t globally, which nobody would build.
      *Leakage Current: Moore's Law Meets Static Power* (2003) records that multi-V_t is already
      standard — low V_t on the few speed-critical transistors, high V_t on the majority — so the
      assignment is already a **spatial** decision. LCMR is a **spatial** cooling capability. The
      claim becomes "cool the tiles over the low-V_t blocks and you can afford low-V_t in more
      places than a conventionally-cooled part can", which is a floorplan result and a device
      result through one mechanism. It changes what is swept: the fraction and placement of
      low-V_t area under the array, not a global ΔV_t
- [ ] **Pixel-material sweep** (GaAs 55 / Si₃N₄ 30 / grease 4) as a design variable — §6a

## Open questions for the device team

- [ ] Does `dt_max` bound a tile or a block? Is `h_max` per tile area?
- [ ] A floor on optical collection efficiency — it alone moves effective COP 3.55 → 1.24
- [ ] Pixel host material: the conductivity optimum is a real trade, not a free choice (§6a)
