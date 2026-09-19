# Phase 0 checklist — live state

Working state for the Phase 0 programme in `docs/EXECUTION_PLAN.md`. **Update this as work lands**;
it is what a new session reads first to find out where things stand. The plan says what to do and
why; this says what is done.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

Last updated: 13 September 2026 — **§P0.31–§P0.34 opened (the generalized f_max, the 8× / 16× cluster transport ladder, the CoMeT IPC(f) reader, D1 under the per-block shape); §P0.29–§P0.30 closed. Earlier: P0.25 closed (the burst ladder); P0.27 X1–X4 done: the rescue ladder is a current ladder and gen 1's next constraint is the PDN; thermal skew grows with the rung; at the book's utilisation the dense cluster is 1.22× denser and holds every rung; and the gen-3 stack as argued is FALSIFIED — with the storage die on the sink side of the compute die the cache prize costs the whole die at every bond, and an isolating bond takes the compute die's sink away.** Earlier — 8 September 2026 — **P0.21: zone materials decided by the user — Cr:LiSAF storage zone, dye hot zone, no Yb:YLF — and the cold plate we test is SINGLE-material by default (`--mr-zone-mode single`); the floorplan-matched dual arrangement is a flag for Phase 2 / die-integrated arrays. Smoke point at 2.00 W/mm²: the default reproduces P0.20 exactly, the dual arrangement is a 1 % effect on the hot-spot objective (0.1 W shortfall, 80 cold tiles). P1 of P0.21 found and fixed a latent P0.20 bug (uncapped first-plan re-cap tripped the stale-plan guard).** Earlier — **P0.20: v98 supersedes v91; the target device is Table 1.1's R640-SMILES row (rung 6 of the photonic ladder), its temperature dependence is the transparency cap (thermal by construction, so the T_min bracket collapses without a measurement), it is invisible on this die (identical plans, 0 tiles capped), the near-term film delivers 17 W of the 198 W a 2.00 W/mm² rescue needs, and rung 4 (broadband Purcell) is the requirements flow-down. Both notes to the author are resolved in v98. Open: v98's zone materials vs the 3 Sep rule.** Earlier — **P0.19: `dt_max` is DERIVED from the extractor's own cooling curve (v91's constitutive parameters, no Yb:YLF) and it never binds on this die — the coldest tile the array is driven to is 263 K against floors of 207–259 K; a fixed-wavelength GaAs pump has a HOT-side limit near 380 K instead; the converged energy cap takes one rung off the array ceiling (2.40–2.60 W/mm²); and the scalar 45 K turns out to shape the plan, so keep it alongside the curve. Two notes for the book (eq. 9.5 is 3.3× its own benchmark; Fig. 9.9's scale is not the ledger's η_ext).** Earlier — **P0.18: the array charged its own footprint, and at 500 µm pitch / 200 µm burial the charge is ZERO — quarter coverage (644 of 1126 blocks under gaps, 75 mm² reserved) holds the same ceiling on the same minimum plan to ~1 %. The array-assisted ceiling under arm D is 2.60–3.00 W/mm², a full W/mm² above the recorded 1.60–1.80, but it is an ENVELOPE result (the array removes more than the die dissipates at 2.60) — quote the rescue range and cost ladder, not the top rung. SPICE now gives V_t(T), SS(T), DIBL, I_on(V,T) and a fitted alpha (1.45) from the same card; the V_t lever re-priced 2× dearer in cooling (50 mV ≈ 45–60 K, not 22 K). `--leakage-curve` default: RECOMMEND `simulated`, not applied. Two of five predictions wrong, both favourable, both from carrying a derived estimate past a measured neighbour.** Earlier — **P0.16: the MR catalogue is OFF the old leakage curve, and it barely noticed. All 18 airflow rescues survive (6/6 on pipeline, `simulated` and `simulated-gidl-off`), the clipping efficacy moves 2-4 % and the budget cliff does not move — against a 14 % move on the density ladder. So `--leakage-curve` is NOT a reason to re-run the MR catalogue; the density and clock families are the ones that moved. Four of five §P0.16 predictions were wrong, both failures from turning a CURVE ratio into a RESULT ratio. Also: `core_other`'s 2.0000x is a literal `2 *` in `scripts/mcpat_to_blk_lvl_power_dict.py` (die total and static fraction safe; `core_other`'s share of on-die LEAKAGE overstated ~1.75x), the 36 net-generating `p_mr_net_W` rows are corrected by algebra with no re-solves, and the full catalogue re-run is priced at 6.3 h wall, not 63 days.** Earlier — **P0.13/P0.14: the leakage curve is SIMULATED, and spending it moved two recorded numbers in OPPOSITE directions — the cold-zone prize is 2.2x BIGGER and the density ceiling is one rung LOWER (P0.12 predicted higher; that claim is withdrawn). Read P0.14 before quoting either.** Earlier — **P0.13: ngspice 47 + OSDI + OpenVAF-compiled BSIM-CMG evaluates the ASAP7 card directly; the tooling task P0.12 called the project's highest-value one is finished and Xyce was not needed. Two results move recorded numbers in opposite directions: the cold floor is **GIDL, not gate leakage**, so the cold-zone prize is **~20x smaller** than P0.12 promised, and the hot tail is gentler still (500 K: 5820x pipeline, 349x analytic, **123x simulated**). `[!]` P0.13 inferred from that tail that P0.11's ceiling is more conservative than recorded; **P0.14 measured it and the opposite is true** — see P0.14. Read both before quoting anything that rests on leakage-vs-temperature. Earlier — **P0.7: the power-recovery reframing. The objective
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

## P0.14 — The simulated curve, consumed: prize 2.2x bigger, ceiling one rung LOWER  `[x]` 31 Aug 2026

`HotGauge/thermal/leakage_feedback.load_leakage_model` + `LEAKAGE_CURVES`,
`device_leakage.SimulatedLeakageCurve.as_leakage_model`, 12 new tests,
`examples/cold_zone_prize.py`, `docs/evidence/cold_zone_prize_simulated.json`,
`--leakage-curve` on `uniform_density_probe.py`,
`scripts/uniform_density_ladder_simulated.sh`, `examples/density_ceiling_curve_compare.py`.
Suite **863 passed, 1 skipped** (was 842 + 1).

§P0.13 built the simulator and produced a curve; nothing consumed it. This wires it in and spends
it on the two questions that were explicitly waiting on it.

### The wiring, and the one rule it keeps

`load_leakage_model('pipeline'|'simulated'|'simulated-gidl-off')` returns the same
`(LeakageModel, T_ref_K)` pair `load_calibrated_leakage_model` always did, so a study swaps curves
with a flag. **`pipeline` is the default everywhere and stays that way** — same discipline as
`--rbb-policy stock`: every recorded result was solved on the pipeline curve and changing the
default would silently move all of them. A test asserts the default rather than trusting it.

Both curves are anchored at the same 330 K, so the swap changes the *shape* of leakage-vs-
temperature and nothing else — no level is smuggled in with it. The simulated curve still
extrapolates above its table (a clamped hot tail freezes the feedback and turns a divergent
configuration into an apparently convergent one), with an Arrhenius tail fitted to simulated
points: **Ea = 0.341 eV against the pipeline's 0.799 eV**, which is the gentler tail in one number.

### `[+]` The cold-zone prize: the 2.3x spread is closed, and the book was right

`cold_zone_prize_bounds.json` called this *"the single number the architecture argument is most
uncertain about"* and named exactly what would settle it: SPICE cards, because *"McPAT rejects
input outside 300-400 K"*. Cooling the cache from 350 K:

| T_cold | pipeline | **simulated** | GIDL-off bracket |
|---|---|---|---|
| 300 K | 1.73x | **6.1x** | 9.0x |
| 280 K | 1.73x | **10.3x** | 25.8x |
| 250 K | 1.73x | **15.0x** | 134.6x |
| 200 K | 1.73x | **16.6x** | 711.5x |

The pipeline curve is stuck at 1.73x at every temperature **because it clamps below 300 K** — it
reports the same leakage at 200 K as at 300 K. That clamp was read as a floor for the whole
cold-zone argument; it is where CACTI's table stops.

**The prize grows 2.23x.** Recorded: 13.5 % of die power (our curve) against 31.7 % (the book's
Section 10.8), a 2.3x spread. Simulated: the book's end of that *spread*. `[!]` Not the book's
absolute number — see §P0.15, which re-derives the conversion ratios and puts the prize at ~6 % of
die power.

### `[!]` Quote the 2.2x, not the percentage — and the percentage is now ~6 %, not 10-30 %

The reduction factors are measured here. The conversion to "% of die power" needs two ratios — the
static fraction and the cache share of leakage — and §P0.14 could not reproduce the recorded pair
(34.64 %, 92.6 %), so it quoted the absolute prize as a **10-30 %** range. **§P0.15 reproduced it
exactly and it is a scope error.** See "§P0.15 — the conversion ratios, re-derived" below. The
absolute prize is **~6 % of die power**; the 30 % end is withdrawn.

`[+]` **The 2.23x improvement is unchanged**, because every conversion multiplies the same
`1 - 1/reduction` by a constant. The claim "our own curve understated the cold-zone prize 2.2x,
because it clamps" is robust and untouched; "the prize is 30 % of die power" is withdrawn.

## `[+]` §P0.15 — the GIDL-off density ladder: the bracket does NOT move the flat-die ceiling

§P0.14 called this *"the highest-value open item"*: the ceiling is decided at 310-330 K, which is
where the two GIDL brackets disagree most, so the bracket that was harmless for the cold-zone knee
should be **load-bearing for the ceiling**. Twenty solves, `scripts/uniform_density_ladder_gidl_off.sh`.

**It is not load-bearing, on the arm that carries the claim.**

| arm | pipeline | simulated (GIDL on) | simulated-gidl-off |
|---|---|---|---|
| shaped | 0.60 → **0.80** | 0.60 *unconverged* → **0.80** | *(none holds)* → **0.60** |
| **uniform** (the flat-die ceiling) | 1.00 → **1.20** | 0.80 → **1.00** | 0.80 → **1.00** |

`[+]` **On the uniform arm the two brackets are identical** — same highest holding rung, same
lowest failing rung. §P0.11's flat-die ceiling and §P0.14's one-rung move are therefore **not
GIDL artefacts**, and the ASAP7 GIDL coefficient uncertainty does not propagate into them. That
removes a caveat that was recorded as blocking.

`[!]` On the shaped arm the bracket does one small thing: 0.60 moves from **unconverged** — neither
a hold nor a failure — to **diverged**. That is a point becoming decidable, not a ceiling moving;
the fine ladder has both simulated brackets diverging at 0.65 as well.

### `[!]` Why the prediction failed: it compared LEVELS where its own finding says compare SLOPES

§P0.14 established the mechanism itself — runaway is a local instability set by
`d(ln P_leak)/dT`, **not** by the leakage level. It then argued the bracket matters because the two
brackets "differ 14-15 % at 450-500 K but far more at 310-330 K". That is true of the *level* and
false of the *gain*. Measured in the band the holding points actually occupy (**316-328 K**):

| quantity | pipeline → simulated | simulated → GIDL-off |
|---|---|---|
| `d(ln P_leak)/dT` ratio | **6.1 - 13.6×** | **1.16 - 1.27×** |

The curve swap carries an order of magnitude of feedback gain; the bracket carries ~20 %. One rung
moved for the first and none for the second, which is exactly proportionate. **§P0.14 applied its
own key insight to the wrong quantity** — it is the correction that matters here, more than the
ladder result.

`[+]` **So the bracket question is CLOSED**, and closed cheaply: §P0.14 listed it as the single
highest-value outstanding item, and it turns out to change nothing that is quoted.

### `[+]` And the fine ladder turns "one rung" into a number — 14 %, on one arm only

The coarse ladder's rungs are 0.20 W/mm² apart, so "the ceiling moves down one rung" resolved the
move only to an interval. Refined to 0.05 W/mm² on all three curves
(`scripts/uniform_density_ladder_fine.sh`, 27 points):

| arm | pipeline | simulated | simulated-gidl-off |
|---|---|---|---|
| **uniform** | 1.05 → **1.10** | 0.90 → **0.95** | 0.85 → **0.95** *(0.90 unconverged)* |
| shaped | 0.60 → **0.65** | 0.55 → **0.65** *(0.60 unconverged)* | 0.55 → **0.60** |

**The flat-die ceiling moves ~14 %** — 1.05-1.10 W/mm² on the pipeline curve against 0.90-0.95
simulated (−14.3 % on the highest holding rung, −13.6 % on the lowest failing one). The coarse
ladder could only say "somewhere between 0.05 and 0.35".

`[!]` **And the move is on the uniform arm alone.** At 0.05 W/mm² the shaped arm's *failing* rung
is **identical at 0.65** on both curves; only its holding rung differs, by one 0.05 step, and the
point between them is unconverged on the simulated curve. §P0.14 recorded "the shaped arm's failing
rung is unchanged" from a coarse ladder where it could equally have been an artefact of 0.20-wide
rungs. It is not — it survives a 4x finer ladder.

`[+]` **The simulated shaped arm now has a demonstrable hold, which it did not before.** Every
rung on the coarse ladder was either diverged or unconverged, so §P0.14 could state no shaped
ceiling at all on that curve. It holds at **0.55 W/mm² (69.0 °C)**, verified.

`[+]` **The GIDL brackets still agree, at 4x the resolution.** Both hold 0.55 on the shaped arm and
both fail by 0.65; both fail at 0.95 on the uniform arm. The only differences are which single
point comes back *unconverged* — 0.60 shaped under GIDL-on, 0.90 uniform under GIDL-off — and an
unconverged point is neither a hold nor a failure. The negative result survives refinement.

`[!]` The **pipeline** shaped arm is also tighter than §P0.11 recorded: it fails at **0.65**, not
0.80. The recorded 0.60-0.80 bracket was correct and merely coarse.

`[!]` **A process note that cost six solves.** The first refinement pass was sited off the coarse
GIDL-off ladder while it was **16 of 20 complete**, and put all six GIDL-off points above a cliff
that turned out to be below them. The four unfinished points were the four *nearest the cliff* —
which is the only region a refinement cares about. Do not site a refinement off an unfinished
ladder. They were cheap (a point far above the cliff diverges quickly; the expensive points are the
ones that converge) and are kept, since "0.85 through 1.50 all diverge" is a real row.

`[!]` **"Diverging points finish in minutes" is only true far from the cliff.** The four slowest
coarse points all *diverged*, and took over two hours each: near the cliff the solver grinds
through every damping level before it can call a divergence genuine. Progress that looks stalled at
a rung adjacent to a cliff is not evidence of a hang.

Evidence `docs/evidence/uniform_density_curve_compare_gidl_off.json`.

## `[!]` §P0.15 — the conversion ratios, re-derived, and the prize moves DOWN

§P0.14 left one cheap open item: re-derive the static fraction and cache share so the cold-zone
prize has an absolute number instead of a 10-30 % range. Done, and it went further than expected —
the recorded pair is not merely unreproduced, it is **reproducible and wrong**.

### The provenance, pinned to the last digit

`cold_zone_prize_bounds.json`'s measured baseline is
`mcpat_runs/7nm/linpack_3.8GHz/block_powers_split_400000000000.json`, summed over the **true leaves
of Core0 alone**, with `Processor/Total L3s` bridged in. All four recorded quantities come back
exactly:

| quantity | recorded | reproduced |
|---|---|---|
| die dynamic | 2.6062 W | **2.6062 W** |
| die static | 1.3812 W | **1.3812 W** |
| cache leakage | 1.2784 W | **1.2784 W** |
| static fraction | 34.64 % | **34.64 %** |
| cache share of leakage | 92.6 % | **92.56 %** |
| "L3 alone is 89 % of it" | 89 % | **88.69 %** |

`[!]` It took a *structural* leaf test to get there. Dropping the four names in `_AGGREGATES` is
not enough: McPAT's **intermediate** parents — `Core0/Load Store Unit`, `Core0/Renaming Unit`,
`Core0/Instruction Fetch Unit` — restate their children exactly as `Processor` does and are on no
aggregate list. They carry 0.8 mW each, and including them gives 1.3837 W against the recorded
1.3812 W. That 2.5 mW is the difference between a near-miss and a settled provenance, and it is
why §P0.14's hand attempts landed close and stopped.

### Two defects, and they compound

- **Scope.** One core's leaves are weighed against the **whole chip's** L3 — the cache share is
  divided by an eighth of the core power it should be. 66.8 % becomes 92.6 %.
- **Slice.** Tick 4e11 is the trace's warm-up: only Core0 has ramped, so die dynamic power is a
  third of steady state. That lifts the static fraction from 15.5 % to 34.6 % — and it hits this
  scope hardest precisely because Core0 is the one core the rule keeps.

### `[!]` §P0.14's hypothesis is WITHDRAWN

§P0.14 guessed the pair had been measured *after* leakage feedback converged at the operating
temperature (where leakage is ~3x its 330 K value), with L3 bridged. It was not, and the recorded
numbers refute it without any re-solve: **dynamic power does not depend on temperature**, and the
recorded 2.6062 W is that slice's `T_ref` dynamic to four decimal places. No feedback and no
temperature is involved. It is scope and slice arithmetic, and the hypothesis cost nothing to
check because it was falsifiable from the recorded numbers alone.

### What replaces it

The denominator for "% of die power" has one defensible definition in this project: the power that
lands on a real floorplan block, which is what `die_power_of_trace` returns and what every recorded
thermal result is a fraction of. Computed that way over the steady slices:

| conversion | static | cache share (L3+L2) | ceiling | prize at 200 K |
|---|---|---|---|---|
| recorded — **withdrawn** | 34.64 % | 92.56 % | 32.1 % | 30.1 % |
| McPAT leaves, all 8 cores, steady — *upper bound* | 14.45 % | 66.77 % | 9.6 % | 9.1 % |
| **pipeline die (`prepare_dice_trace`), steady** | **15.98 %** | **38.24 %** | **6.1 %** | **5.7 %** |

The gap between the last two rows is **`core_other`** — McPAT's un-itemised per-core power on the
tiler's slab, **42 % of the leakage that reaches the die**. It is absent from any leaf sum, which
is what makes the leaf view an upper bound rather than an answer. If the cold die carries L3 only
rather than L3+L2, the prize is **4.5 %**.

### `[!]` So the absolute prize moves DOWN, and it is a smaller win than recorded

**~4-10 % of die power, best estimate ~6 %**, against §P0.14's 10-30 % and the book's 31.7 %. The
inherited pair was never one plausible reading among two — it was arithmetic on the wrong scope and
the wrong slice — and should not be used again.

`[+]` **The 2.23x improvement is untouched**, which is the point of having quoted it rather than a
percentage: every conversion multiplies the same `1 - 1/reduction` by a constant, so the ratio
cancels it exactly. §P0.14's decision to lead with the improvement is what kept the headline claim
safe through this correction.

`[!]` What this *does* change is the size of the win a separate cold cache die is being built to
collect, and that is a first-order input to whether it pays for itself. What it does not change:
the cold zone still has to be a separate die (TEST 1), and the knee is still ~280 K.

Driver: `examples/cold_zone_prize.py` (`recorded_pair_provenance`, `die_ratios`, `trace_ratios`);
evidence `docs/evidence/cold_zone_prize_simulated.json` (`provenance_of_recorded_pair`,
`ratios.rederived_pipeline_die`); 5 new tests in
`HotGauge/HotGauge/power/test_cold_zone_prize.py`.

### `[+]` §P0.15 — `--leakage-curve` reaches the rest of the catalogue

`clock_headroom.py`, `mr_comparison.py` and `mr_clipping_study.py` all called
`load_calibrated_leakage_model` directly, so the pipeline curve was hard-wired into them and only
`uniform_density_probe.py` could be re-run on a measured one. All three now take
`--leakage-curve {pipeline,simulated,simulated-gidl-off}`, **defaulting to `pipeline`**.

The change is **additive by construction**: the non-default curve is a new branch placed *ahead*
of the existing `load_calibrated_leakage_model` call, which stays reachable and unmodified, so at
the default each driver takes the path it always took. Both properties are now tested for all four
drivers (`test_leakage_curve_select.py`), which is stricter than the single-driver check that was
there before. `mr_comparison.py`'s `--no-leakage-extrapolation` is a property of the pipeline
curve's Arrhenius tail and is **ignored** rather than half-applied on the other curves.

### `[!]` The clock-headroom prediction was WRONG, and what the run found instead

**Prediction, made before the run and recorded here rather than removed.** The clock-headroom
search is the one recorded study whose criterion is a **temperature limit** rather than a
divergence test. §P0.14's explanation for why the density ladder moved only one rung — runaway is
a *local* instability, decided by `d(ln P_leak)/dT` at one temperature — predicted this study
should move **more**, because the simulated curve is steeper through the entire operating band
(~9x the feedback gain at 320 K) rather than only at a cliff.

**It moved less.** `scripts/clock_headroom_curves.sh`, control arm, the six R_th points of
`docs/CLOCK_HEADROOM.md` × all three curves, 18 solves:

| R_th K/W | pipeline | simulated | GIDL-off |
|---|---|---|---|
| 1.0 | 2.984, **runaway** | 3.078, spec limit | 3.031, *unverified* |
| 0.5 | 3.734, **runaway** | 3.734, spec limit | 3.734, spec limit |
| 0.3 | 4.109, **runaway** | 4.109, spec limit | 4.109, spec limit |
| 0.1 | 4.484, spec limit | 4.484, spec limit | 4.484, spec limit |
| 0.05 | 4.625, spec limit | 4.625, spec limit | 4.625, spec limit |
| 0.02 | 4.672, spec limit | 4.672, spec limit | 4.672, spec limit |

The sustainable clock is unchanged at **five of six** cooling points, to the bisection's own
0.05 GHz resolution, and moves **+3.1 %** at the sixth. Against a full-rung move on the density
ladder, that is less, not more. **The prediction is withdrawn.**

### `[+]` But the *limiter* changes, and that kills a recorded claim

At **three of six** points the clock is identical and the reason it stops is not: the pipeline
curve ends the search with a **thermal runaway**, both simulated curves end it at the **100 °C spec
limit**. `docs/CLOCK_HEADROOM.md` builds a headline on the pipeline behaviour —

> *"Above 0.1 K/W the part does not reach its 100 °C spec limit at all — it **runs away first**, at
> 85.7 °C with a 1.0 K/W cooler. The leakage instability, not the temperature spec, is what caps
> the clock on a poorly-cooled die."*

On the measured curve the part reaches spec at **every** cooling point tested. `[!]` **That claim
is withdrawn** (struck through in `CLOCK_HEADROOM.md`). The clocks in its table survive; the
mechanism does not. At 1.0 K/W the phantom runaway also costs real headroom — the +3.1 %.

### `[!]` So the hot tail matters to a SEARCH and not to a LADDER — §P0.14 refined, not withdrawn

§P0.14 argued the pipeline curve's 47x-too-steep hot tail "lives where the answer does not",
because a die that survives never gets that hot, and concluded the defect worth fixing is the
curve's **flatness at 310-330 K**. That reasoning is correct for a **fixed-density divergence
test**, whose reported point is one the die survives. It is wrong for a **search**, which
deliberately probes operating points the die does *not* survive and reads its answer off where
they begin — so the tail decides whether the last failing step failed by running away or by
exceeding spec.

`[+]` **The generalisation worth carrying: which part of a leakage curve is load-bearing is a
property of the EXPERIMENT, not of the curve.** A divergence test at fixed power is decided by the
local slope at the operating temperature; a limit search is decided by the tail as well. §P0.14's
"one clamp, two wrong answers" becomes "one curve, and which of its defects bites depends on what
you are asking it".

`[+]` **The GIDL bracket is worth nothing here** — the two brackets agree on the clock at every
point (within the search's own 0.05 GHz) and on the limiter at every point where the limiter is
judgeable. §P0.14 flagged it as load-bearing for the density ceiling because that is decided at
310-330 K; nothing in this study is.

`[!]` One point needs stating rather than rounding off. The GIDL-off run at 1.0 K/W stopped on a
step the damping check **rejected**, so its `limited_by` is `unverified`: the 3.031 GHz clock is a
demonstrated hold, but *why* the search stopped there is not known. The comparison lists it and
excludes it from the limiter tally rather than counting it either way — the same treatment an
unconverged rung gets on the density ladder. Counting it as a disagreement would have
manufactured one (it is the only thing that made the brackets look like they differed); counting
it as agreement would have laundered it. The clock and the limiter are therefore reported as two
separate questions, so neither can absorb the other.

`[!]` The `pipeline` rows are the **control for this campaign, not a reproduction** of the 14 Aug
table in `CLOCK_HEADROOM.md`, which predates the RBB work, the residual/backtracking convergence
fix and `verify=True` — all of which raise the clock (0.1 K/W: 4.203 there, 4.484 here. Treating
it as a reproduction target would have read a real improvement as a regression.) Additivity of the
new flag is checked structurally instead (`test_leakage_curve_select.py`) and by the density
comparison driver's output being byte-identical at its default.

Driver `examples/clock_headroom_curve_compare.py`, evidence
`docs/evidence/clock_headroom_curve_compare.json`, 6 tests in
`HotGauge/HotGauge/thermal/test_clock_headroom_curve_compare.py`.

### `[!]` The density ceiling moves — DOWN, and the predicted direction was wrong

`scripts/uniform_density_ladder_simulated.sh` (20 points, ladder extended to 4.00 W/mm² in case
the ceiling moved past the old top rung), `examples/density_ceiling_curve_compare.py`,
`docs/evidence/uniform_density_curve_compare.json`. Same die, package, RBB policy, arms and
convergence settings — verified field by field against the recorded P0.11 ladder. One input
changed.

§P0.12 predicted the ceiling would move **up**: the pipeline's Arrhenius tail is ~6x too steep at
450 K, a gentler tail runs away later, so P0.11's 1.0-1.2 W/mm² flat-die ceiling is *conservative*.
§P0.13 then measured a **47x** gap at 500 K, which made the prediction look safe.

**Both arms degrade, in two different ways.** 2 of 16 common points flip verdict:

| arm | pipeline | simulated | |
|---|---|---|---|
| shaped | holds 0.60 (73.48 °C), fails **0.80** | 0.60 **UNCONVERGED** (85.54 °C), fails **0.80** | failing rung unchanged; the last hold is no longer demonstrable |
| uniform | holds 1.00 (65.99 °C), fails **1.20** | holds 0.80, fails **1.00** | **one rung DOWN** |

- `uniform` at 1.00 W/mm² held at 65.99 °C on the pipeline curve and **diverges** on the simulated
  one — resolved by the solver's own guard as a *genuine runaway at minimum damping*, not flagged
  as a damping artefact. That is the ceiling moving.
- `shaped` at 0.60 no longer converges at **any** of the three damping levels (residual stalls at
  0.146 K against a 0.100 K tolerance), so it is **not a demonstrated hold** and its peak must not
  be quoted. Its peak is nevertheless stable to 0.01 K across all three levels at **85.54 °C**,
  against 73.48 °C on the pipeline curve — **+12.1 K at the same density**. Flagged, directional,
  and not a number to cite.

`[!]` **The "P0.11's ceiling is conservative" claim is WITHDRAWN. The recorded ceilings are
optimistic instead.**

`[+]` The two points that survive on *both* curves (uniform 0.60 and 0.80) move only −3.16 K and
−0.69 K — **cooler**, not hotter. Combined with shaped 0.60's +12.1 K, that is the signature of a
curve which is *steeper through the operating band*: it sits below the pipeline curve at 317-329 K
and above it by ~346 K, so cool points cool and hot points heat. The crossover is near 345 K.

### `[+]` Why — runaway is decided where the die sits, not at 500 K

Thermal runaway is a **local instability**: what matters is `d(ln P_leak)/dT` at the temperature
the die is actually at, not the leakage at 500 K. By 500 K a block has already run away under
either curve, so the 47x disagreement lives entirely where the answer does not.

| T | pipeline gain /K | simulated gain /K | sim/pipe |
|---|---|---|---|
| 310 K | 0.0013 | 0.0357 | **27.8x** |
| 320 K | 0.0041 | 0.0373 | **9.2x** |
| 330 K | 0.0091 | 0.0378 | **4.1x** |
| 350 K | 0.0613 | 0.0364 | 0.59x |
| 500 K | 0.0411 | 0.0191 | 0.46x |

The surviving points occupy roughly **317-347 K**, and in that band the ordering **reverses**: the
pipeline curve is nearly flat there — the clamp again — while the simulated one runs ~0.036/K
throughout. The two cross over near **345 K**. More gain runs away earlier, and the surviving
points sit below the crossover. That is the whole mechanism.

### `[!]` And it relocates the defect worth fixing

The pipeline curve's most consequential error for the density ceiling is **not** its 47x-too-steep
hot tail — a surviving die never reaches that region. It is that the curve is nearly **flat at
310-330 K**, understating the feedback gain by roughly an order of magnitude exactly where dies
operate. **The same flatness is what made the cold-zone prize look small.** One clamp, two wrong
answers, in opposite directions — and neither was the error P0.12 went looking for.

`[!]` **The GIDL bracket is load-bearing here, unlike for the cold-zone knee.** The two brackets
differ 14-15 % at 450-500 K (well inside a rung) but much more at 310-330 K — the band this
finding says decides the ceiling. Only the full-GIDL bracket was run, so **running the ladder on
`simulated-gidl-off` is the highest-value open item**.

### Honest limits

The ladder resolves a move only to the nearest rung (0.20-0.40 W/mm² near the cliff); the sub-rung
evidence is the peak temperatures. Rows flagged `unconverged` are counted as neither holding nor
failing by the comparison driver — the stock `uniform_density_report.cliff` counts any non-diverged
row as holding, which was right for the recorded ladder where nothing was flagged, but would
promote a damping artefact into a ceiling here. The pipeline ladder is the **recorded** P0.11 one
rather than a re-run, so the two campaigns were produced by the same code at different times.

---

---

## `[x]` §P0.34 — D1 and the accelerator under the PER-BLOCK envelope shape: the D1 premium ratios re-measured like-for-like. PREDICTIONS, before the run  `[~]` 13 Sep 2026

**Why.** The D1 family (§P0.22.3, `results/d1_family_arr/`) was measured with the seed envelope
shape, which §P0.29 showed over-spends a concentrated block 12× and the reference ladder 18–33 %;
a denser cluster is the concentrated case, so its recorded plans are upper bounds by an unknown
and probably larger factor, and the "density premium" (member plan / reference plan at matched
watts) mixes two over-spends. The reference per-block ladder exists at 1.20–4.00 W/mm²
(`results/array_coverage_armD_power/`, 50 µm); D1's 1.10 rung (111.2 W) is added to it. Run:
`SHAPE=power OUT=results/d1_family_power ARRAY_ONLY=1 scripts/d1_family_ladder.sh` (both
members, five rungs, `array_idle` + `array_on`, 50 µm, arm D, the target device, scalar 45 K).

- **P1 — the ×0.5 member's plans fall 20–35 % at 121 / 162 W and 15–25 % at 202 W** (the
  reference fell 33 / 25 / 18 %), **and it holds 243 W** (lost under the seed shape: 114 °C on
  193 W) with s = 0.80–0.90. Falsifier: 243 W not held, or the 202 W plan moving < 10 %.
- **P2 — the ×0.25 member holds 202 W** (no steady state under the seed shape) with s = 0.70–0.85
  **and loses 243 W** (bistable). Falsifier: 202 W not held, or 243 W held.
- **P3 — the density premium at matched watts, both shapes per-block, is 1.1–1.4× at the
  die-wide rungs** (seed: 1.2×) **and falls at 111 W from 2.8× / 6.9× to 1.5–3×**, because the
  per-block shape helps the concentrated cluster more than the reference (§P0.29's 12× lesson).
  Falsifier: a premium above 1.6× at 202 W.
- **P4 — the accelerator needs no re-run:** §P0.24 parts 2–3 (`results/accel_f3_power`,
  `results/accel_f3_power_tol1`) already ran every kernel and uniform row under the power shape;
  the seed-shape rows of part 1 are the recorded failure of that shape, not a result to
  replace. A check, not a run.

### `[x]` §P0.34 RESULT — under the per-block shape the ×0.5 cluster holds every rung to 243 W and the ×0.25 holds 202 W (both lost under the seed shape); the plans fall 9–59 %; the die-wide premium is 1.1–1.2× (×0.5) and 1.3–1.7× (×0.25); the ×0.25 at 243 W is held only under the injected-energy cap (s = 1.02) and is not a rescue

`results/d1_family_power/` (10 points, 50 µm, ~10 min at PAR 4), `examples/d1_family_power_report.py`
→ `docs/evidence/d1_exec_density_family_power.json`; the reference per-block ladder gained its 1.10
rung (`results/array_coverage_armD_power/d1.10`: 0.82 W, the unpowered array holds it, as under the
seed shape). **Both anchors reproduced first** (`results/anchor_2026-09-13/`: seed 138.72881 W /
93.8752 °C, per-block 113.63869 W / 91.5424 °C — five figures on both).

| member | W | seed shape (recorded): plan (ref) premium | per-block shape: plan (ref) premium, s | change |
|---|---|---|---|---|
| ×0.5 | 111.2 | 14.8 W (0.8) 2.76× | **6.1 W** (0.8) 2.04×, s 0.06 | −59 % |
| ×0.5 | 121.3 | 27.5 (17.3) 1.59× | **17.4** (11.6) 1.97×, 0.15 | −37 % |
| ×0.5 | 161.8 | 93.6 (75.3) 1.17× | **73.6** (56.5) 1.20×, 0.47 | −21 % |
| ×0.5 | 202.2 | 178.6 (138.7) 1.21× | **130.4** (113.6) 1.20×, 0.69 | −27 % |
| ×0.5 | 242.6 | lost (114 °C on 193 W) | **188.5 W, HELD** (176.7) 1.08×, **0.84** | gained |
| ×0.25 | 111.2 | 34.7 (0.8) 6.94× | **31.4** (0.8) 4.93×, 0.29 | −9 % |
| ×0.25 | 121.3 | 55.2 (17.3) 2.92× | **41.5** (11.6) 4.04×, 0.36 | −25 % |
| ×0.25 | 161.8 | 126.5 (75.3) 1.65× | **104.3** (56.5) 1.68×, 0.69 | −18 % |
| ×0.25 | 202.2 | no steady state | **166.1 W, HELD** (113.6) 1.51×, **0.89** | gained |
| ×0.25 | 242.6 | no steady state | 225.5 W "held" (176.7) — **s = 1.02, injected cap: envelope only** | not a rescue |

**P1 half** — the ×0.5 member's 243 W rung is held (s 0.84, inside 0.80–0.90) and its 121 / 202 W
plans fall 37 / 27 % (inside / just outside the brackets; 162 W −21 %). **P2 FALSIFIED on its
second half** — the ×0.25 holds 202 W (s 0.89, above the 0.70–0.85 bracket) and the 243 W row
comes back "held" too, but with the array lifting 225.5 W from a die dissipating 221 W: that is
the injected-energy cap, the same envelope-only regime the seed shape produced at 2.60 W/mm² on
the reference (§P0.18.2), so **the ×0.25 ladder ends at 202 W with the top rung envelope-only**,
and the rule stands: a row with s ≥ 1 is not a rescue. **P3 half** — die-wide the ×0.5 premium is
**1.20 / 1.08×** (confirmed) and the ×0.25's **1.68 / 1.51 / 1.32×** (above 1.4, not as
predicted; under the 1.6× falsifier at 202 W by 0.09); at 111 W the premiums are 2.0× / 4.9×
against the predicted 1.5–3× (the ×0.25 stays high because the reference needs no light there
and the denser cluster's 31 W is set by its own cALU). **P4 confirmed (a check):** `results/
accel_f3_power` and `_tol1` carry every kernel and uniform row under the power shape;
nothing accelerator-side is re-run.

`[!]` What changes in the record: register §1.3's D1 row and ladder §2.2 carry both shapes;
the D1 "top rung lost" statement is a seed-shape statement — under the per-block shape the 2×
cluster loses nothing on the reference's ladder and the 4× cluster loses only the conservation
rung; the premiums quoted are per-block ones from here on (1.1–1.2× for ×0.5, 1.3–1.7× for
×0.25 at the die-wide rungs), like-for-like within a shape only. X1's current ladder is
unaffected (currents are the die's). `[!]` The ×0.25 member at 243 W is the first per-block row
in the D1 record with s > 1: quote it as envelope-only and never as a hold.

## `[x]` §P0.33 — a CoMeT IPC(f) reader: the memory wall enters the throughput claims. PREDICTIONS, before the read  `[~]` 13 Sep 2026

**Why.** Every throughput figure here is `f × 32 FLOP/cycle × cores` — a fixed-IPC proxy that
moves only with the clock. CoMeT's 1–20 GHz sweeps
(`/mnt/nfs01/scratch/jbalma/CoMeT/test/thermal_example_test_1to20ghz/run_<f>/sim.out`; the
`benchmarks_sweep/<bench>/run_<f>` trees) carry Instructions / Cycles / IPC / Time per core at each
frequency with the memory system's latency fixed in nanoseconds, so IPC(f) falls with f — the
memory wall — and `PeriodicVdd.log` carries the DVFS voltage CoMeT assigned. Built:
`examples/comet_ipc_reader.py` → `docs/evidence/comet_ipc_vs_f.json`; `clock_f1c_report.py` and
`iso_package_throughput_report.py` take `--ipc-source` and report `f × IPC(f) × cores` beside
the proxy. `[!]` Only the frequency setting differs between CoMeT's configs; it says nothing about
whether the device can switch at 20 GHz — §P0.31 does.

- **P1 — FFT's IPC(f) (2.88 / 2.49 / 1.95 / 1.43 at 1 / 4 / 10 / 20 GHz, one active core of four)
  fits `IPC0 / (1 + f / f_k)` with f_k = 18–22 GHz within 5 %** at every measured point.
  Falsifier: a residual above 10 % anywhere.
- **P2 — at the F1c clocks the throughput gain is 0.80–0.85 of the clock gain**: +14 % clock
  (3.66 → 4.17 GHz) is +11–12 % instructions per second on FFT; +26 % (3.32 → 4.17) is +20–21 %.
  Falsifier: an elasticity below 0.70 or above 0.95.
- **P3 — the multi-core benchmarks are less elastic than the single-core FFT from 8 to 16 GHz**:
  lu.cont-large-4 0.5–0.7, swaptions-small-4 0.85–0.95 (compute-bound). Falsifier: swaptions
  below lu.cont.
- **P4 — CoMeT's V(f) is a two-level DVFS table (0.8 / 1.2 V) and is the same 1.2 V at every
  f ≥ 4 GHz**: it carries no device V/F information. Falsifier: a voltage that rises with f
  above 4 GHz.

### `[x]` §P0.33 RESULT — IPC(f) is read; at the F1c clocks the fixed-IPC proxy overstates the throughput gain by a fifth (elasticity 0.78–0.84); CoMeT's voltage is a table

`examples/comet_ipc_reader.py` → `docs/evidence/comet_ipc_vs_f.json`: 38 benchmark sweeps (the
1–20 GHz FFT-style `test` kernel on one core; SPLASH-2 / PARSEC on 4–16 cores, most at 8 and
16 GHz, `swaptions-small-4` and `lu.cont-large-4` at 1–20). `clock_f1c_report.py` and
`iso_package_throughput_report.py` now take `--ipc-source` / `--ipc-benchmark` (default the FFT
sweep) and carry `GIPS = f × IPC(f) × cores` and `GIPS per package watt` beside the FLOP/s
proxy; `docs/evidence/clock_f1c.json` and `iso_package_throughput.json` regenerated (additive).

| benchmark (active cores) | IPC at 1 / 4 / 8 / 16 / 20 GHz | knee fit `IPC0 / (1 + f/f_k)` | elasticity 8 → 16 GHz |
|---|---|---|---|
| FFT-style test (1 of 4) | 2.88 / 2.49 / 2.09 / 1.58 / 1.43 | IPC0 3.06, **f_k 17.3 GHz**, max residual 1.0 % | 0.60 |
| lu.cont-large-4 (4) | 1.97 / 1.63 / 1.31 / 0.90 / 0.78 | 2.21, f_k 11.1 GHz, 3.0 % | **0.47** |
| swaptions-small-4 (4) | 1.61 / 1.50 / 1.43 / 1.28 / 1.22 | 1.61, f_k 64 GHz, 1.4 % | **0.84** |

**At the recorded F1c operating points (FFT IPC(f)):** the laser arm's +13.9 % clock at
1.00 W/mm² is **+11.4 %** instructions per second (elasticity 0.83); +25.5 % at 1.20 is **+21.1 %**
(0.84); the table's +33.5 % is **+26.1 %** (0.80); the above-table +78 % is +57 % (0.78). IPC at
3.66 / 4.17 GHz is 2.52 / 2.46. **P1 not as predicted** (f_k 17.3 GHz against 18–22; the fit
itself is within 1 %). **P2 confirmed** (0.83 / 0.84 inside 0.80–0.85). **P3 not as predicted but
the ordering holds** (lu.cont 0.47 against 0.5–0.7, swaptions 0.84 against 0.85–0.95; swaptions
above lu.cont as predicted; the single-core FFT sits between them at 0.60). **P4 confirmed** —
CoMeT's `PeriodicVdd` is 1.2 V at every frequency from 1 to 20 GHz (0.8 V only in the
initialisation rows), so it carries no device V/F information; §P0.31 does.

`[!]` What travels: the elasticity at 3.3–4.9 GHz (0.78–0.84 on a memory-touching kernel, ~0.95
on a compute-bound one) is the correction to every "+x % clock" claim in the register; quote
throughput gains as `f × IPC(f)` with the benchmark named, and never the FLOP/s proxy alone.
`[!]` The `x264` rows read IPC 0.00 (the trace ran outside the ROI) and several `-test` inputs
are too short to mean anything (< 10⁴ instructions per core); the reader records them, the
reports use the FFT sweep.

## `[x]` §P0.32 — the 8× / 16× execution-cluster ladder at 20 µm and 5 µm burial: where heat TRANSPORT binds a >100 W/mm² functional unit. PREDICTIONS, before any run  `[~]` 13 Sep 2026

**Why.** MXL-006 claims ">1000 W/mm² functional units"; the register says no simulated die asks
any tile for more than 5–15 W/mm² and the hottest block is a 29 W/mm² cALU. D1 densified the
cluster 2× / 4× (§P0.22.3) at 200 µm burial and the top rungs were lost to the stability boundary,
not to transport. A 230–460 W/mm² unit is a different regime: ΔT ≈ q·d/k through the silicon
between the transistors and the tile (460 W/mm² through 20 µm of Si is 71 K; through 5 µm, 18 K),
so the extractor must sit within microns and the tile must resolve the block. This ladder measures
that. Built: `generate_exec_density_family.py --factors 0.125 0.0625` (→ `d1_exec0.125`,
`d1_exec0.0625`; `docs/evidence/d1_exec_density_family_x8x16.json`);
`scripts/cluster_transport_ladder.sh` → `results/cluster_transport/x<factor>/b<burial>/p<pitch>/W<watts>`:
factors {0.125, 0.0625} × burial {20, 5} µm × pitch {200, 100} µm × the D1 rungs {111, 121, 162,
202, 243 W} (`--density` = W / member mm²), `array_on` under `--mr-envelope-shape power`,
`array_idle` at 111 and 121 W; plus the REFERENCE die at the same burials / pitches / shape at
202 and 243 W (like-for-like), all at **50 µm cells** (the 34-core stacks fit; 100 µm would put
the 8× cALU inside one cell). Arm D, the target device, scalar 45 K, 92 °C.

`[!]` **The grid caveat, stated before the run.** The reference cALU is 142 × 115 µm; the tiler shrinks the cluster units in ONE
dimension, so ×0.125 makes it a **117 × 17 µm sliver** (2000 µm², 0.8 of a 50 µm cell) and ×0.0625 **117 × 9 µm** (1000 µm², 0.4 of a cell). 3D-ICE spreads a block's
power over the cells it touches, so the 16× cluster's local rise is understated by up to ~2.5×
and the 8×'s by ~1.2× — every "holds" on the 16× rows is a LOWER bound on the block's real
peak, and the 1-D estimate above (18 K at 5 µm, 71 K at 20 µm for 460 W/mm²) is the check.

- **P1 — the family:** die area 83.5–84.5 mm² (×0.125) and 82.5–83.5 mm² (×0.0625) (the ×0.25
  member is 86.33; each halving frees half the previous delta); cALU at 8× / 16× the reference's
  W/mm² at matched watts. Falsifier: the tiler failing on the sub-cell units, or an area outside
  those brackets.
- **P2 — transport binds first at the deeper burial and the denser cluster:** at **5 µm / 100 µm
  pitch the 8× cluster holds every D1 rung (111–243 W)** under the per-block shape and **the 16×
  holds to 202 W and loses 243 W**; at **20 µm / 200 µm the 16× loses the 202 W rung** and the
  8× holds 202 W but not 243 W. Falsifier: the 8× losing 202 W at 5 µm, or the 16× holding
  243 W at 20 µm.
- **P3 — the tile demand climbs past 50 W/mm²** on the 16× at 202 W / 100 µm pitch (the
  reference's highest recorded steady demand is 14.8 at 200 µm pitch, §P0.28), still 15× under the
  film's 813 W/mm² at 300 K tiles; **0 tiles capped at 5 µm**; at 20 µm the tile above the cALU
  is driven below 263 K to reach the block through the silicon and **1–10 tiles are capped** by
  the dye curve on the 16×. Falsifier: a demand above 813 W/mm², or more than 20 tiles capped.
- **P4 — the rails, ARGUED from X1 (not re-solved):** at matched watts the array clips every
  member to the same 92 °C, so the cluster's cALU carries **8× / 16× the reference's current
  density** exactly (X1 measured 2.00× / 3.9× for ×0.5 / ×0.25) and its EM acceleration against
  the native die is the J² term 64× / 256× at the same temperature — a re-sizing statement, no
  rail model (register §3).
- **P5 — the reference die does not get cheaper by thinning under the per-block shape either:**
  its 202 W / 243 W plans at 5 µm and 20 µm land within ±10 % of the 200 µm per-block plans
  (113.6 / 176.7 W), the integration ladder's finding (§P0.28) repeated on the cheaper shape.
  Falsifier: a move above 15 % either way.
- **P6 — the premium of the 8× / 16× cluster over the reference at 5 µm / 100 µm and matched
  watts is 1.3–2× at 162–202 W** (D1's 2× / 4× clusters: 1.2× die-wide under the seed shape); the
  film is not what binds, the silicon between tile and block is. Falsifier: a premium above 3×
  at 202 W where the rung holds.

### `[x]` §P0.32 RESULT — the 8× cluster holds to 202 W at every burial and pitch and its 243 W rung is envelope-only or lost to the dye's cold end; the 16× holds 202 W only at 100 µm pitch (either burial) and loses 243 W everywhere; what binds is the TILE'S RESOLUTION and, at the top, the extractor's own temperature dependence — the first rows in this repository where the film's capability binds; and under the per-block shape the reference die DOES get cheaper by thinning (−14 to −31 %), which withdraws §P0.28's headline as a seed-shape result

`results/cluster_transport/` (48 points, 50 µm, ~35 min at PAR 6), `examples/cluster_transport_report.py`
→ `docs/evidence/cluster_transport.json`; members `d1_exec0.125` (83.87 mm², cALU a 117 × 17 µm sliver,
0.8 of a cell) and `d1_exec0.0625` (82.65 mm², cALU 117 × 9 µm, 0.4 of a cell, smearing ≤ 2.5×); the
reference die at the same burial / pitch / shape at 202 and 243 W. Per-block shape throughout;
a row with s > 1 is envelope-only (`ENV`) and is never counted as a hold.

| member | burial / pitch | 111 W | 121 | 162 | 202 | 243 | max tile demand (held rows) / coldest tile |
|---|---|---|---|---|---|---|---|
| 8× | 20 µm / 200 µm | 37.7 W | 57.0 | 113.6 | **166.9 (s 0.90)** | ENV, s 1.00 | 55 W/mm² / 270 K |
| 8× | 20 / 100 | 32.7 | 47.0 | 96.7 | **173.8 (0.94)** | **lost: 12 tiles capped**, 253 K | 161 / 254 K |
| 8× | 5 / 200 | 49.5 | 63.6 | 124.2 | **178.2 (0.97)** | ENV, s 1.02 (100.8 °C) | 56 / 275 K |
| 8× | 5 / 100 | 35.3 | 49.0 | 101.6 | **152.5 (0.82)** | **lost: 4 tiles capped**, 254 K | 158 / 262 K |
| 16× | 20 / 200 | 48.6 | 60.3 | 124.2 (0.83) | **no steady state** | no steady state | 47 / 281 K |
| 16× | 20 / 100 | 38.8 | 48.4 | 103.3 | **163.9 (0.88)** | no steady state | 167 / 260 K |
| 16× | 5 / 200 | 56.2 | 72.0 | 138.6 (0.93) | **no steady state** | no steady state | 50 / 283 K |
| 16× | 5 / 100 | 41.5 | 50.9 | 110.3 | **164.3 (0.88)** | no steady state | 172 / 258 K |
| reference, per-block, same geometry | 20/200 · 20/100 · 5/200 · 5/100 | | | | **90.2 · 78.0 · 97.2 · 80.5** (200 µm burial: 113.6) | 149.3 · 139.0 · 159.6 · 140.8 (176.7) | |

**P1 confirmed** (83.87 / 82.65 mm² inside both brackets; the tiler took the sub-cell units).
**P2 not as predicted, in one place** — the 16× at 5 µm / 100 µm holds 202 W and loses 243
(predicted), the 16× at 20 µm / 200 µm loses 202 W (predicted), the 8× at 20 / 200 holds 202 W and
its 243 W row is envelope-only (predicted: not held); **but the 8× at 5 µm / 100 µm does not hold
every rung**: its 243 W row diverges with **4 tiles capped by the dye's curve at 254 K**, and at
20 µm / 100 µm with 12 capped at 253 K. **P3 not as predicted** — the demand climbs to **158–172
W/mm²** on the held 202 W rows at 100 µm pitch (predicted > 50: yes; 5× under the film's 813 at
300 K but the tiles are NOT at 300 K) and the coldest tile is driven to **253–254 K**, 10 K below
the 263 K the reference ladder ever reached (§P0.19); 0 tiles capped on any held row at either
burial (predicted 1–10 on the 16× at 20 µm — it holds at 100 µm pitch with none, and at 200 µm
it diverges with none: the coarse tile cannot resolve the block at all). **P4 stands as argued**
(8× / 16× the reference's cALU current density at matched watts; the EM J² term 64× / 256×;
no rail model). **P5 FALSIFIED** — the reference die's per-block plans at 20 µm and 5 µm burial
are **14–31 % below the 200 µm-burial per-block plans** (202 W: 90.2 / 78.0 / 97.2 / 80.5 W
against 113.6; 243 W: 149.3 / 139.0 / 159.6 / 140.8 against 176.7); the integration ladder's
"thinning does not make the rescue cheaper" (§P0.28, memo §8.1) was a **seed-shape** result —
the uniform allotment could not spend what the thinner silicon lets the tiles resolve.
**P6 confirmed** — at 5 µm / 100 µm and 202 W the 8× and 16× clusters cost **1.84× / 1.86×** the
reference at the same geometry (normalised), inside 1.3–2×.

`[+]` **What the ladder says.** (i) **Pitch, not burial, is the lever for a dense cluster.** At
200 µm pitch the 16× cluster has no steady state at 202 W at either burial (the tile spends its
light over 4× the block's footprint and cannot reach the target); at 100 µm it holds 202 W at
both. Thinning from 20 to 5 µm moves the 8×'s 202 W plan −12 % at 100 µm pitch and **+7 % at
200 µm** (a thinner die spreads less, so a coarse tile must do more), and the 16×'s 0 % / +12 %.
(ii) **The top rung is lost to two different walls**: at 200 µm pitch to **conservation** (the
8× at 243 W: s = 1.00 / 1.02, envelope-only), at 100 µm pitch to **the extractor's cold end** —
the tile above the cALU is driven to 253–254 K, where the dye's transparency cap has collapsed
(§P0.20: 263 W/mm² at 263 K), the planner asks it for 170–200 W/mm², and it is capped. **This is
the first row on any die in this repository where the film's capability binds** (register §4's
"never exceeds ~5 W/mm²" is a reference-die statement; on a 230–460 W/mm² cluster the demand is
30× that and the tile is 50 K colder). (iii) **The silicon between tile and block does not
bind** at 5–20 µm for a 230 W/mm² unit: the 1-D estimate through 20 µm (35 K) is absorbed at
the tile; for the 460 W/mm² unit the sub-cell grid understates the local rise (≤ 2.5×), so its
holds are lower bounds and its losses are firm. (iv) **The premium is the tile's, not the
silicon's**: 1.8–1.9× at the like-for-like geometry for both clusters, against 1.2× / 1.5× for
D1's 2× / 4× clusters at 200 µm burial (§P0.34).

`[!]` What changes in the record: §P0.28's Level-1 conclusion is re-labelled seed-shape (register
§2); the "≤ 5 W/mm² per tile" standing constraint gains the cluster exception (register §4); the
memo's ">1000 W/mm² functional units" row gets its measured form: a **230 W/mm² cALU is held to
the 2.00-equivalent rung at 5–20 µm burial and 100–200 µm pitch, a 460 W/mm² cALU only at
100 µm pitch; the film's capability binds at 170–200 W/mm² of tile demand at 254 K, not at
813**. Rails: 8× / 16× the reference's cALU current density at matched watts (ARGUED from X1).

## `[x]` §P0.31 — a GENERALIZED f_max(V, T | logic depth, wire, skew) with V_max from an Arrhenius reliability budget at the cooled temperature; the clock search re-run so it NAMES its limiter. PREDICTIONS, before any run  `[~]` 13 Sep 2026

**Why.** The recorded clock search (§P0.26, F1c) ends every laser arm at **4.17 GHz** because
`DeviceVFModel` (a) is re-anchored at every temperature (`k` re-fitted so 0.70 V = 3.8 GHz at
whatever T it was loaded at, so I_on(T) never reaches the clock), (b) caps V at an ASSUMED 10 %
overdrive whether the worst block sits at 100 °C or 40 °C, and (c) makes a gate the whole period
(no wire, no skew, no setup/jitter), so nothing names what a re-pipelined core would buy and
"10 GHz" cannot be tested either way. Built: `HotGauge/power/fmax_model.py`
(`GeneralizedFmaxModel`, 18 tests): the period is `N·[FO4(V,T) + wire(T)] + T_skew(ΔT,T) + T_ovh`,
anchored ONCE at the trace (3.8 GHz / 0.70 V / 330 K, 20-FO4 reference pipeline → FO4_ref 8.2 ps,
where ASAP7 sits), FO4 ∝ V/I_on(V,T) on the card (`device_vt_vf_asap7_v100.json`: the I_on sweep
extended to 1.00 V today, identical to the recorded file on the common grid), wire a stated
30 % of the combinational delay at 0.40 %/K (Cu), skew X2's `D_ins·ΔT·(w_wire α_R + w_cell α_cell)`
with **ΔT read from the solve**, overhead 8 % fixed in ps; **V_max = the largest supply with the
qualification point's lifetime** (0.77 V at 100 °C — today's rule restated) under EM (Black,
n = 2, E_a = 0.9 eV, J ∝ V·f) and TDDB (power law n = 40, E_a = 0.6 eV), both stated and swept;
`budget_ref=native` is X1's other reading (the native die's own lifetime at 0.70 V / 3.8 GHz /
78.6 °C). `clock_headroom.py --vf-source fmax[:N=..,w=..,ref=..]` solves each candidate clock in
the context the previous one left, re-reads (T_peak, ΔT_core) from the field and re-solves while
the implied supply moves > 2 mV; a row's `limited_by` is now one of `over_thermal_limit` /
`thermal_runaway` / `reliability:tddb` / `reliability:em` / `device` (I_on/V saturates before the
budget is spent) / `sweep_end` (data), and `fmax.period_dominated_by` says what the period is made
of. `--mr-extractor` and `--mr-envelope-shape` added to the clock driver (defaults unchanged).

**P0 — the brief's own prediction, recorded as written (13 Sep):** "the cooled die buys 10–15 % of
V_max on the reliability budget and +6 % of gate speed from I_on(T), i.e. +20–30 % of clock on the
same pipeline; 10 GHz needs the pipeline, not the cooler." Scored against P1–P7 below.

Model arithmetic (`examples/fmax_model_report.py` → `docs/evidence/fmax_model.json`, run first):

- **P1 — the V_max ladder under the qualification budget: TDDB binds at every temperature at
  or below 100 °C, and it buys +1–2 % of supply at the array's 92 °C target, +3–6 % at 60 °C,
  +10–16 % at 27 °C** (0.6 eV through 8 / 40 / 73 K is ×1.56 / ×5.9 / ×137 of lifetime, and the
  40th root of that is 1.1 / 4.5 / 13 %). EM alone would allow ≥ 0.88 V at 92 °C (×1.85 of
  lifetime → ×1.36 of J → +24 % of (V − V_t)). So the brief's 10–15 % is a ROOM-TEMPERATURE
  statement; at the target the array holds today it is ~1 %. Falsifier: EM binding anywhere
  below 100 °C, or V_max at 92 °C above 0.80 V.
- **P2 — a die held at 60 °C instead of 92 °C clocks +8–12 % faster on the same 20-FO4
  pipeline** (supply +3–6 % → +5–8 % of gate speed at the card's α ≈ 1.4; I_on(T) +2 % over
  32 K — the brief's +6 % is the 300 → 400 K span; wire −13 % of its term → +4 % of the period;
  skew < 1 %). Falsifier: < 5 % or > 15 %.
- **P3 — the device's f(V) has a MAXIMUM inside the extended sweep:** I_on/V saturates
  (the α fitted over 0.45–1.00 V is 1.34 against 1.45 over 0.45–0.77 V), so f(V) at 330 K peaks
  at 0.85–0.95 V and falls beyond; below some temperature between 27 and 60 °C the reliability
  V_max exceeds the device's peak-clock supply and the ceiling's limiter reads `device`, not
  `reliability`. Falsifier: f(V) monotone to 1.00 V.

The coupled search (`scripts/clock_fmax.sh` → `results/clock_fmax/`, 50 µm, arm D, 88 CFM, the
target device, per-block shape, three arms at 0.78 / 1.00 / 1.20 W/mm² with the 92 °C target;
`array_on` at 75 / 60 °C targets at 1.00 / 1.20; a 10-FO4 pipeline at 1.00; the native budget at
1.00) — every clock UNCALIBRATED as F1c's were (the 3.8 GHz anchor):

- **P4 — at 1.00 W/mm² with the 92 °C target: control 3.55–3.70 GHz, `over_thermal_limit`
  (F1c: 3.66; the hotter die now needs more supply for the same clock, which costs power);
  array_idle 3.80–3.95, thermal; array_on 4.20–4.35 GHz, `reliability:tddb`** (V_max 0.78 V at
  92 °C; period ~60 % gate, ~27 % wire, ~8 % overhead, 3–5 % skew). At 1.20: control 3.2–3.4,
  array_on the same 4.20–4.35 ceiling at a larger plan (the array pins the temperature, so the
  ceiling is a property of the target, not the rung). At 0.78: every arm within 0.1 GHz of the
  ceiling. Falsifiers: array_on limited thermally at 1.00, or above 4.5 GHz.
- **P5 — the target as a co-design knob:** array_on at 75 °C 4.40–4.60 GHz, at 60 °C
  4.55–4.80 GHz, both `reliability:tddb`; the plan grows 1.5–3× per step (F1c's 38 W at 92 °C /
  1.00 → 80–120 W at 60 °C). Falsifier: the 60 °C arm below 4.4 GHz, or `device`-limited.
- **P6 — 10 GHz needs the pipeline:** at every solved operating point the logic depth that
  would clock 10 GHz is **5–8 FO4 per stage** (the fixed 21 ps of overhead plus 5–10 ps of skew
  are 25–30 % of a 100 ps period). With N = 10 (P4-class) at 1.00 W/mm²: control thermally
  limited at 3.9–4.3 GHz (dynamic power ∝ f), array_on `reliability:tddb` at **6.2–6.8 GHz** with
  a 100–150 W plan. Falsifier: N = 10 array_on below 5.5 or above 7.5 GHz.
- **P7 — under the native budget (the native die's own lifetime is the reference) the laser
  arm at the 92 °C target is reliability-limited BELOW the trace clock: 3.3–3.6 GHz** (V_max at
  92 °C ≈ 0.66–0.68 V), X1's "the cooled die ages faster at matched density" restated as a clock;
  only a target below the native worst block (78.6 °C) buys clock under that reading. Falsifier:
  ≥ 3.8 GHz.

### `[x]` §P0.31 RESULT, part 1 (model arithmetic, `docs/evidence/fmax_model.json`) — once wire, skew and overhead are in the period, the 10 % overdrive at the array's 92 °C target buys +1.6 % of clock, not +10 %; the budget buys supply as an Arrhenius ladder (+1 / +3 / +6 / +12 % at 92 / 78.6 / 60 / 27 °C), TDDB binds everywhere below the corner, and 10 GHz needs a 6–7 FO4 pipeline at every temperature

The anchor decomposes to **FO4_ref 8.18 ps** (20 stages → 163.6 ps of gate), wire 70.1 ps
(3.51 ps per stage), skew 8.3 ps (24 K, X2's constants), overhead 21.1 ps at 263.2 ps
(3.80 GHz). The extended sweep's α over 0.45–1.00 V is 1.34 (1.45 over the recorded range).

| worst block at | V_max (qual budget) | binding | device peak-clock V | f_max, same 20-FO4 pipeline | vs the 100 °C corner | period: gate / wire / skew / ovh | N for 10 GHz |
|---|---|---|---|---|---|---|---|
| 100 °C (the corner) | **0.770 V** (by construction) | em + tddb (tie) | 1.00 (sweep end) | **3.783 GHz** | — | 0.58 / 0.31 / 0.03 / 0.08 | 6.0 |
| 92 °C (the array target) | 0.778 (+1.0 %) | tddb (EM alone would allow 0.974) | 0.975 | **3.844** | **+1.6 %** (supply +0.5, temperature +1.1) | 0.58 / 0.31 / 0.03 / 0.08 | 6.1 |
| 78.6 °C (the native cALU) | 0.792 (+2.9 %) | tddb | 0.975 | 3.948 | +4.4 % | | 6.3 |
| 60 °C | 0.814 (+5.8 %) | tddb | 0.975 | **4.102** | **+8.4 %** (supply +2.4, temperature +5.9) | 0.59 / 0.29 / 0.03 / 0.09 | 6.6 |
| 27 °C | 0.863 (+12.0 %) | tddb | 0.950 | 4.393 | +16.1 % (supply +4.2, temperature +11.4) | 0.60 / 0.27 / 0.04 / 0.09 | 7.1 |

Under the **native** reference (the native die's own lifetime at 0.70 V / 3.8 GHz / 78.6 °C is
the budget) the 92 °C target is **EM-bound at 0.547 V → 2.82 GHz** (the 13 K above the native
cALU cost ×3 of EM life, so J must fall 1.7×), 78.6 °C gives back 0.700 V / 3.69 GHz, and only a
die held at ≤ 60 °C clocks above the trace (0.720 V / 3.85 GHz).

**P1 confirmed** (+1.0 / +5.8 / +12.0 % at 92 / 60 / 27 °C inside the brackets; EM binds nowhere
below the corner — at 92 °C EM alone would allow 0.974 V, TDDB 0.778). **P2 not as predicted** —
a die held at 60 °C instead of 92 °C clocks **+6.7 %** faster, under the 8–12 % bracket and above
the 5 % falsifier: the supply term is smaller than predicted (+1.9 % of clock for +4.6 % of V,
because a third of the period does not scale with V) and I_on(T) + wire give +4.7 %. **P3 not as
predicted** — f(V) does peak inside the extended sweep (0.950 V at 300 K, 0.975 V at 330–365 K;
4.45 / 4.26 / 4.06 GHz), but above the 0.85–0.95 V bracket, and the reliability V_max stays
below the device peak at every temperature down to 27 °C (0.863 < 0.950): **the limiter reads
`reliability:tddb` everywhere below the corner, never `device`**, unless the TDDB term is dropped
(EM alone: `device` at 60 °C, 0.975 V, 4.24 GHz).

`[!]` **What this says about the recorded 4.17 GHz.** F1c's ceiling was the gate-only model at
0.77 V re-anchored at 300 K: `I_on/V` rises 9.8 % from 0.70 to 0.77 V and the whole period
followed it. With 31 % of the period in wire (V-independent, +0.4 %/K), 8 % in setup/jitter
and 3 % in skew, the same supply step buys **+5.5 %** at the anchor temperature and the 373 K
corner takes 4 % back (I_on −2.6 %, wire +17 %), so **the same pipeline's ceiling at the 92 °C
target is 3.84 GHz** — 1 % above the trace clock. The recorded F1c clocks (4.17 GHz laser,
+14 / +26 %) are the gate-only ceiling and are re-labelled as such in the register; the
coupled search under this model (part 2) says what the cooler buys under a stated architecture.
**Sensitivity** (f_max at 92 °C): TDDB n 30 / 50 → 3.849 / 3.840; E_a 0.4 / 0.8 eV → 3.838 /
3.849; wire 0.15 / 0.45 → 3.960 / 3.734; overhead 0.04 / 0.12 → 3.846 / 3.842; D_ins 300 ps →
3.844; **logic depth 10 → 6.91 GHz, 8 → 8.22 GHz** (the same device, the same budget). The
reliability constants move the answer by < 0.3 %; the wire fraction by ±3 %; the pipeline by
80–115 %. **P0 (the brief's) scored:** "10–15 % of V_max" is the 27 °C row, not the target's;
"+6 % of gate speed from I_on(T)" is the 300 → 400 K span (0.06 %/K), 2 % over the 32 K the
array can add at 60 °C; "+20–30 % of clock on the same pipeline" is not available at any
temperature above 27 °C (+16 % there); **"10 GHz needs the pipeline, not the cooler" — confirmed
by the arithmetic**: N = 6.0–7.1 FO4 at every temperature, a P4-class pipeline on this device.

### `[x]` §P0.31 RESULT, part 2 (the coupled search, `docs/evidence/clock_fmax.json`) — on a 20-FO4 pipeline the laser arm's ceiling at the 92 °C target is 3.76–3.83 GHz and `reliability:tddb` names it (F1c's gate-only 4.17 was the model); the laser buys +7 % over the control at 1.00 W/mm² and +15 % at 1.20; a 60 °C target buys 4.08 GHz for 104 W; a 10-FO4 pipeline reaches 5.75 GHz and the COOLER binds again (runaway at 283 W, s 0.92); under the native budget every arm is EM-bound below the trace clock

`results/clock_fmax/` (nine runs, 50 µm, arm D, 88 CFM, the target device, per-block shape, ~1.5 h
at PAR 3; 8–9 candidates per arm, 1–3 self-consistency passes each), `examples/clock_fmax_report.py`.
Every clock UNCALIBRATED as F1c's (the 3.8 GHz anchor); IPC(f) from CoMeT's FFT sweep.

| run | arm | f (GHz) | limiter | V / V_max | worst block | ΔT_core | Q (W) | P_die | period gate / wire | GIPS (+ vs control) | F1c gate-only |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.78 W/mm², 92 °C | control | 3.728 | thermal_runaway | 0.720 / 0.789 | 81.6 °C | 25 K | — | 80.1 | 0.60 / 0.29 | 318 | 4.071 |
| | array_idle | 3.834 | reliability:tddb | 0.755 / 0.790 | 80.6 | 27 | — | 89.0 | | 326 (+2.5 %) | 4.173 |
| | array_on | 3.834 | reliability:tddb | 0.768 / 0.788 | 82.6 | 28 | 0 | 92.2 | | 326 (+2.5 %) | 4.173 |
| 1.00, 92 °C | control | **3.516** | over_thermal_limit | 0.672 / 0.780 | 90.1 | 28 | — | 86.4 | 0.61 / 0.28 | 303 | 3.664 |
| | array_idle | 3.693 | thermal_runaway | 0.724 / 0.776 | 93.8 | 33 | — | 104.0 | | 316 (+4.3 %) | 3.902 |
| | array_on | **3.763** | **reliability:tddb** | 0.759 / 0.774 | 95.8 | 32 | 1.8 | 117.3 | 0.58 / 0.30 | **321 (+6.0 %)** | 4.173 |
| 1.20, 92 °C | control | 3.270 | thermal_runaway | 0.626 / 0.779 | 91.4 | 28 | — | 85.3 | 0.64 / 0.26 | 284 | 3.324 |
| | array_idle | 3.446 | over_thermal_limit | 0.667 / 0.778 | 91.9 | 32 | — | 99.9 | | 297 (+4.6 %) | 3.596 |
| | array_on | **3.763** | **reliability:tddb** | 0.772 / 0.776 | 93.6 | 34 | 36.1 | 141.6 | 0.57 / 0.30 | **321 (+13 %)** | 4.173 |
| 1.00, **75 °C** | array_on | 3.940 | reliability:tddb | 0.786 / 0.798 | 73.8 | 28 | 56.7 | 123.3 | | 334 | |
| 1.00, **60 °C** | array_on | **4.081** | reliability:tddb | 0.813 / 0.814 | 60.0 | 26 | **103.8** | 133.6 | 0.59 / 0.29 | 343 | |
| 1.20, 75 °C | array_on | 3.904 | reliability:tddb | 0.781 / 0.795 | 76.1 | 31 | 81.9 | 144.4 | | 331 | |
| 1.20, 60 °C | array_on | 4.045 | reliability:tddb | 0.807 / 0.813 | 61.0 | 30 | 135.2 | 156.1 | | 341 | |
| 1.00, **10-FO4 pipeline** | control | 3.594 | over_thermal_limit | 0.446 / 0.773 | 97.3 | 31 | — | 92.2 | 0.74 / 0.15 | 308 | |
| | array_idle | 3.969 | over_thermal_limit | 0.469 / 0.770 | 99.5 | 35 | — | 110.0 | | 336 (+8.9 %) | |
| | array_on | **5.750** | **thermal_runaway** | 0.657 / 0.779 | 90.6 | **54** | **259.0** | **283.0** | 0.53 / 0.23 (skew 0.11, overhead 0.12) | **448 (+45 %)** | |
| 1.00, **native budget** | control | 3.446 | reliability:em | 0.649 / 0.665 | 81.6 | 25 | — | 78.4 | | 297 | |
| | array_on | 3.587 | reliability:em | 0.676 / 0.700 | 78.7 | 26 | 0 | 86.9 | | 308 (+3.7 %) | |

**P4 not as predicted** — the limiters are as predicted (control thermal, laser
`reliability:tddb`, TDDB binding everywhere below the corner) but the laser arm's ceiling is
**3.76 GHz at both 1.00 and 1.20**, not 4.20–4.35: the prediction ignored part 1's own
arithmetic (3.84 GHz at 92 °C). The gain over the control is **+7.0 % at 1.00 and +15.1 % at
1.20** (F1c: +14 / +26 %), and in instructions per second **+6.0 % / +13 %**. At 0.78 every arm
sits within 3 % of the ceiling (3.73–3.83) and the array has nothing to remove. **P5 FALSIFIED**
— the target knob buys less than predicted: 75 °C gives 3.94 GHz (+4.7 % over the 92 °C arm) for
57 W and **60 °C gives 4.08 GHz (+8.4 %) for 104 W** (predicted 4.55–4.80); the plan grows
1.6–1.8× per step (57 → 104 W; at 1.20: 82 → 135 W); GIPS per package watt falls 2.09 → 1.43.
The measured +8.4 % from 92 to 60 °C is exactly part 1's arithmetic (+6.7 % at fixed gradient,
+8.4 % at the ceiling's own). **P6 not as predicted** — the 10-FO4 pipeline clocks 5.75 GHz
under the laser (predicted 6.2–6.8), but **the limiter is thermal, not reliability**: at
5.75 GHz the die dissipates 283 W (dynamic power ∝ f), the array lifts 259 W (s = 0.92, the
conservation end of the ladder) and the next step runs away; the skew term is 11 % of the period
(a 54 K core gradient at 174 ps) and the overhead 12 %. So with the pipeline the cooler binds
again, two rungs up. The logic depth that would clock 10 GHz at the solved points is 5.4–6.5 on
the 20-FO4 rows and **2.8–4.6 on the 10-FO4 rows** (the fixed terms grew with the gradient) —
10 GHz is not on this die at any pipeline the model can hold. **P7 confirmed** — under the native
budget both arms are EM-bound **below the trace clock** (3.45 / 3.59 GHz; V_max 0.665 / 0.700 V
at 81.6 / 78.7 °C): a die that must age no faster than the native one cannot be clocked above
3.8 GHz at the temperatures these arms reach, and the array's target must go below the native
worst block before it buys anything.

`[+]` **What the coupled search says, against the brief's P0.** "10–15 % of V_max" is a 27 °C
statement (measured V_max +1 % at 92 °C, +5.6 % at 60 °C); "+6 % of gate speed from I_on(T)" is
the 300 → 400 K span; "+20–30 % of clock on the same pipeline" is **+7 / +15 %** at the 92 °C
target and **+16 %** (4.08 vs 3.52) at a 60 °C target that costs 104 W; and "10 GHz needs the
pipeline, not the cooler" is **half right**: it needs a 6–7 FO4 pipeline the model cannot reach,
and with a 10-FO4 pipeline the cooler is the limit again at 5.75 GHz and 283 W. The memo's
">10 GHz" row stays CONTRADICTED; the claim to build is "clock to the reliability-budgeted
ceiling at the array's target, the target being the co-design knob" (memo §6.3). `[!]` The
recorded F1c clocks (4.17 GHz, +14 / +26 %) are re-labelled the gate-only ceiling (register §2);
the per-block shape and the target device were used here, F1c used neither. `[!]` The 1.00 W/mm²
laser row's worst block reads 95.8 °C against a 92 °C target: the planner's 2 K tolerance plus
the self-consistency passes (the last pass re-solves at the implied supply); quote the row's
peak, not the target.

## `[x]` §P0.30 — the COOLING-SYSTEM ledger: the ambient the conventional package needs at each rescue rung, priced against the laser's net draw (the COP comparison MXL-006 §2.2 asked for). PREDICTIONS, before the run  `[~]` 13 Sep 2026

**Why.** The provisional's "> 10× COP" came from `mxl_LCEstimator_v8`, which priced the fans,
pumps and chillers a conventional system needs to hold the junction (sub-zero chiller COP with
antifreeze/cryogenic penalties, pump and fan power ∝ flow³, HVAC COP for refrigerated air).
§P0.7 Tests 6b–6e made the same comparison on the pipeline-curve solves and found the chiller
still wins at the measured 42 K rescue and the laser overtakes past ~100 K of depth. Neither is
on the current (arm D) coupled solve with the calibrated fan. This ladder measures, per rung,
the **ambient the air package needs** (control arm, 88 CFM, ambient swept 293 → 233 K in 10 K
steps) and the **inlet a liquid plate needs** (control arm on a lumped `--r-th` sink at the
accelerator ladder's microchannel plate resistance scaled to this die's area — 0.0153 K/W × 826 mm² / 101 mm² = **0.125 K/W** — with the coolant temperature swept 30 → −40 °C; the plate's own spreading is inside that number), at 1.20 / 1.60 / 2.00 / 2.40
W/mm² on the 100 µm grid; the laser side is the recorded rescue ladder's net electrical draw
(register §1.3: 10.6 / 45.9 / 84.4 / 136 W net at those rungs) plus the same 35 W fan at 293 K.
Pricing (`examples/cooling_system_ledger.py`, ported from LCEstimator and stated): chiller COP =
γ·T_in/(T_amb − T_in), γ = 0.4, clipped to [0.5, 6], with LCEstimator's 3 %/K antifreeze penalty
below 0 °C and its exponential cryogenic decay below −20 °C; refrigerated air supplied 5 K
below the required ambient; T_amb = 295 K year-round. System COP = die power / (fan + pump +
chiller + laser net).

- **P1 — the air package is rescued by ambient alone at 1.20 and 1.60 but not above.** The
  control holds 1.20 at ≤ 273 K ambient and 1.60 at ≤ 243 K (runaway is a loop gain that falls
  with the die's temperature; 0.325 K/W × the die's watts is the offset); **2.00 and 2.40 hold
  at no ambient ≥ 233 K**. Falsifier: 2.00 held at ≥ 253 K.
- **P2 — the liquid plate needs far less depth.** At the microchannel resistance the control
  holds 1.20 at ≥ 283 K inlet, 1.60 at ≥ 263 K, 2.00 at ≥ 243 K, 2.40 not in range. Falsifier:
  2.00 needs < 233 K.
- **P3 — the system-COP ratio is a curve, and > 10× exists only where the conventional side
  goes sub-zero.** At 1.20 the laser's 10.6 W net beats refrigerated air's chiller draw (COP
  ~5 at 273 K supply → 25–40 W): **2–4×** in the laser's favour; at 1.60 the air side needs
  243 K (COP ≤ 1 with the antifreeze penalty → ≥ 150 W) against 46 W: **3–5×**; at 2.00 air has
  no solution in range and the ratio is unbounded; **against the liquid plate the laser loses at
  1.20 (plate inlet 283 K, chiller COP ~6 → ~25 W plus pump, comparable) and wins from 1.60
  up** (2–3× at 1.60, ≥ 5× at 2.00). Falsifier: the laser losing to refrigerated air at 1.60, or
  to the liquid plate at 2.00.

`scripts/cop_ambient_ladder.sh` → `results/cop_ambient/{air,liquid}/d<rung>/T<ambient>`,
control arm only, 100 µm cells, arm D. The fan is held at 88 CFM (35 W) on the air side; a
flow sweep is the next axis, not this one.

### `[x]` §P0.30 RESULT — refrigerated air is beaten at every rung and has no solution above 1.60; a chilled direct-die liquid plate beats the laser until its coolant goes sub-zero (2.40 W/mm² on this die); > 10× exists only against air where air has no solution

`results/cop_ambient/{air,liquid}/` (28 + 32 control points, 100 µm, minutes each: a control that
runs away is decided fast), `examples/cooling_system_ledger.py` → `docs/evidence/cooling_system_ledger.json`.
The laser side is the recorded c1.00 ladder (seed-shape plans; §P0.29 P5 tests whether the
per-block shape lowers them). Pricing as stated in the predictions (LCEstimator's chiller COP
with sub-zero penalties; fan 35 W at 88 CFM held; pump 6.85 W held).

| rung | air: ambient needed → chiller | liquid plate (0.125 K/W): inlet needed → chiller | photonic: net laser + fan | system COP air / liquid / photonic |
|---|---|---|---|---|
| 1.20 | **273 K** → 36 W (COP 4.2), 71 W total | **293 K** (holds at ambient) → 0 W, 7 W total | 10.6 + 35 = 46 W | 1.65 / **17.3** / 2.59 |
| 1.60 | **243 K** → 254 W (COP 0.73), 289 W | **273 K** → 32 W (COP 5.0), 39 W | 45.9 + 35 = 81 W | 0.52 / **3.94** / 1.90 |
| 2.00 | no solution ≥ 233 K | **263 K** → 57 W (COP 3.5), 64 W | 84.4 + 35 = 119 W | — / **3.02** / 1.58 |
| 2.40 | no solution | **243 K** → 226 W (COP 1.03), 233 W | 136.3 + 35 = 171 W | — / 0.97 / **1.29** |

**P1 confirmed exactly** (273 / 243 / none / none). **P2 falsified in the laser's disfavour** —
the plate is stronger than predicted: 293 / 273 / 263 / 243 K (predicted 283 / 263 / 243 /
out of range); a direct-die microchannel plate at 0.125 K/W holds 2.40 W/mm² with −30 °C
coolant. **P3 half** — against refrigerated air the laser wins **1.6× at 1.20, 3.7× at 1.60**
and is the only solution at 2.00 and 2.40 (predicted 2–4× / 3–5× / unbounded: confirmed);
against the liquid plate the laser **loses at 1.20 (6.7×), 1.60 (2.1×) and 2.00 (1.9×)** and
wins only at **2.40 (1.33×)**, where the plate's coolant is at −30 °C and the chiller's COP has
fallen to 1.0 (predicted a win from 1.60: falsified).

`[+]` **What the ledger says, and it reconciles LCEstimator with §P0.7.** (i) The provisional's
"> 10× COP" is the air comparison in the regime where air has no solution — a true statement
about refrigerated air above ~1.6 W/mm² on this package, and not a statement about liquid
cooling. (ii) Against the strongest conventional option, a direct-die microchannel plate with a
chiller, the laser's system COP is lower until the rung at which the plate needs sub-zero
coolant; the crossover on this die is between 2.00 and 2.40 W/mm² (§P0.7 Test 6c put it past
~100 K of chiller depth on the old curve — consistent). (iii) The laser's advantage is
therefore *reach* (it holds rungs no air package reaches and holds 2.40 without a sub-zero
surface anywhere), not efficiency, until the conventional side is deep in its penalties — the
same conclusion as §P0.7, now on arm D with the calibrated fan. `[!]` Not priced, both
favouring the laser: condensation control for sub-dew-point coolant (a 243–263 K inlet on the
liquid side at 2.00–2.40), and the pump's flow³ scaling at deeper rungs (held at the design
flow); and one favouring liquid: the laser's own LPC waste heat lands on the same fan (§3).
The photonic plans are seed-shape upper bounds (§P0.29 P5 pending); if they fall 20–35 % the
liquid crossover moves to ~2.00.


## `[x]` §P0.29 — the dark-silicon 1.20 / 25 % row is an UNFINISHED DESCENT mislabelled "runaway"; re-run with the planner budget it asks for. PREDICTIONS, before the run  `[~]` 13 Sep 2026

**What the record says.** `results/dark_silicon/d1.20/f0.25`: control diverges; the unpowered
array holds a STABLE hot branch at 107.1 °C (no runaway); the laser row is `diverged: False`,
peak 94.4 °C on a 0.7 W plan with the planner's own verdict *"max_iter reached: the descent was
still building the plan, so this cost is a LOWER BOUND"* — the baseline planning path (from a
hot-branch baseline, the register §3 open item) ran out of its six iterations 2.4 K above the
target. `examples/dark_silicon_report.py` scores a row "lit" only if it holds the target, and
the pack figure paints every non-lit, non-unconverged row "runaway" — so an unfinished descent
was drawn as a leakage runaway, which it is not: 0 tiles capped, the film 100× under-used, the
die on its cool branch. The figure's category and the row's own bracket are corrected here.

- **P1 — with twice the planner budget (`--mr-iter 12`) the 1.20 / 25 % laser row holds the
  92 °C target for 2–8 W** (the 50 % row needs 1.6 W, the 100 % row 17 W; a concentrated
  quarter at 1.2 W/mm² per core sits between). Falsifier: still unfinished at 12 iterations, or a
  plan above 15 W.
- **P2 — the `power` envelope shape (§P0.24's fix for a concentrated kernel) finds the plan in
  fewer iterations and lands within 20 % of P1's plan.** Falsifier: the shapes disagree by > 2×.
- **P3 — at 1.50 / 25 % the `power` shape removes the "a lit quarter costs more than a lit
  half" anomaly (48.7 vs 43.0 W): the quarter costs LESS than the half** (fewer hot cores).
  Falsifier: the quarter still costs more under the power shape.

`results/dark_silicon_v2/`, 50 µm, arm D, `--arms array_on`, otherwise the F2 flags.

### `[x]` §P0.29 RESULT, part 1 — not a runaway: the row holds for 0.8 W with twice the budget; and the seed envelope over-spent the 1.50 / 25 % row 12×

| point | shape / budget | verdict | plan | peak |
|---|---|---|---|---|
| 1.20 / 25 % | seed, 6 iterations (recorded) | unfinished, lower bound | 0.7 W | 94.4 °C |
| 1.20 / 25 % | seed, **12 iterations** | **holds** (descent still marked unfinished, inside tolerance) | **0.82 W** | 92.9 °C |
| 1.20 / 25 % | `power` shape, 6 iterations | unfinished | 0.73 W | 94.4 °C |
| 1.50 / 25 % | seed (recorded) | holds | **48.7 W** | 93.9 °C |
| 1.50 / 25 % | **`power` shape** | holds, bisected minimum | **4.07 W** | 92.7 °C |

**P1 confirmed** (holds; 0.8 W, below the 2–8 W bracket — the row was a budget artefact, and
the figure's "runaway" a labelling artefact; both corrected). **P2 not as predicted** — the
`power` shape does not finish the 1.20 descent in six iterations either; the budget, not the
shape, was the limit there. **P3 confirmed and sharper** — the quarter costs **4.1 W under the
power shape against 43.0 W for the half under the seed shape**; the recorded 48.7 W was the seed
envelope over-spending a concentrated quarter by **12×** (§P0.24's lesson on the accelerator,
now on the CPU). 0 tiles capped, max tile flux 5.0 W/mm².

- **P4 (added before the run) — the rest of the F2 ladder at 1.50 is over-spent by the seed
  shape too, less so as the lit fraction grows:** under the `power` shape the 1.50 rows fall to
  **≤ 15 W at 50 %, ≤ 25 W at 75 %, 30–45 W at 100 %** (recorded 43.0 / 54.0 / 64.2 W), and the
  1.20 rows move < 20 % (2 / 13 / 17 W). Falsifier: any 1.50 row within 20 % of its seed plan.
  `results/dark_silicon_v2/power/`, six points.

### `[x]` §P0.29 RESULT, part 2 — the seed envelope over-spent the whole F2 ladder; under the per-block shape lighting all 34 cores at 1.2 W/mm² costs 11.6 W, not 17.3, and 44 W at 1.5, not 64

| d0 | lit | recorded (seed shape) | `power` shape | change |
|---|---|---|---|---|
| 1.20 | 25 % | 0.7 W, unfinished | 0.7 W, unfinished (holds at 0.8 W with 12 iterations) | budget, not shape |
| 1.20 | 50 % | 1.6 W | 1.7 W | 0 |
| 1.20 | 75 % | 12.8 W | **3.2 W** | −75 % |
| 1.20 | 100 % | 17.3 W | **11.6 W** | −33 % |
| 1.50 | 25 % | 48.7 W | **4.1 W** | −92 % |
| 1.50 | 50 % | 43.0 W | **19.6 W** | −54 % |
| 1.50 | 75 % | 53.8 W | **32.9 W** | −39 % |
| 1.50 | 100 % | 64.2 W | **44.1 W** | −31 % |

**P4 half** — every 1.50 row falls (the falsifier, a row within 20 % of its seed plan, is not
met) but by less than predicted at 50 / 75 % (19.6 / 32.9 W against ≤ 15 / ≤ 25), and the 1.20
rows move far MORE than the predicted 20 % (−33 % at 100 %, −75 % at 75 %). The quarter now
costs less than the half at 1.50 (4.1 vs 19.6 W): the anomaly was the shape. `[!]` The seed
shape (45 W per block from the 1.0 K/W placeholder, scaled by conservation) hands every block
the same allotment and starves the blocks that need it; the `power` shape caps each block at
its own dissipation. **The recorded F2 costs are upper bounds and are replaced** (register §1.3,
`docs/evidence/dark_silicon.json` regenerated with the `power` rows superseding).

- **P5 (added before the run) — the rescue ladder's plans are upper bounds by the same
  mechanism, less so where the plan is die-wide:** under the `power` shape the c1.00 minimum
  plans fall **20–35 % at 1.20 and 1.60** (17.3 → 11–14 W; 75.3 → 49–60 W) and **≤ 15 % at 2.00
  and 2.40** (138.7 → 118–135 W; 221.5 → conservation-bound, unchanged). Falsifier: 2.00 moves
  > 25 %, or 1.20 does not move. `results/array_coverage_armD_power/d<rung>`, 50 µm, four points.
  `[!]` If P5 holds, the register's cost ladder becomes "17 → 139 W (seed shape, upper bounds;
  11–14 → 118–135 under the per-block shape)" and the anchor stays the seed-shape point.

  **P5, first two rungs (13 Sep, before the rest landed):** 2.00 → **113.6 W (−18 %)**, 2.40 →
  **176.7 W (−20 %)** — both just outside the ≤ 15 % bracket, inside the 25 % falsifier — and the
  2.40 plan is now **s = 0.80**, not 1.00: the "ends on conservation at 2.40" reading was the seed
  shape's. 1.20 and 1.60 pending.
- **P6 (added before the run) — under the per-block shape the ladder climbs one rung before
  conservation ends it:** 2.60 holds with **s = 0.85–0.95** (plan 205–230 W of a ~239 W die);
  **3.00 does not hold** (it would need s ≥ 1). Falsifier: 3.00 held, or 2.60 lost.
  `results/array_coverage_armD_power/d2.60, d3.00`, 50 µm.

### `[x]` §P0.29 RESULT, part 3 — the rescue ladder's plans were seed-shape upper bounds by 18–33 %, and its END was a planner artefact: under the per-block shape 3.00 W/mm² holds with s = 0.89 where the seed shape had no steady state

`results/array_coverage_armD_power/` (six rungs, 50 µm, ~2 h at PAR 4), beside `results/array_coverage_armD/c1.00`:

| rung | seed shape (recorded) | per-block (`power`) shape | change | s (power) | max tile flux (power) |
|---|---|---|---|---|---|
| 1.20 | 17.3 W | **11.6 W** | −33 % | 0.10 | 5.1 W/mm² |
| 1.60 | 75.3 W | **56.5 W** | −25 % | 0.36 | 8.1 |
| 2.00 | 138.7 W (the anchor) | **113.6 W** | −18 % | 0.59 | 11.0 |
| 2.40 | 221.5 W, **s = 1.00** (conservation) | **176.7 W** | −20 % | **0.79** | 15.7 |
| 2.60 | 251.2 W, envelope only (s = 1.05) | **202.7 W, held** | −19 % | 0.84 | 17.2 |
| 3.00 | **no steady state** | **248.9 W, held** | — | **0.89** | 19.3 |

**P5 half** — the low rungs fall 25–33 % (predicted 20–35 %: confirmed) and the high rungs
18–20 % (predicted ≤ 15 %; under the 25 % falsifier). **P6 FALSIFIED** — 3.00 holds (s = 0.89,
peak 91.7 °C, 0 tiles capped, the hottest tile asked for 19.3 W/mm² against 813). The ladder's
end is **above 3.00** and has to be bracketed again (P7 below). `[!]` What was wrong: the seed
shape (45 W per block from the 1.0 K/W placeholder, scaled by conservation) spends light on
blocks that do not need it, so at 2.40 the conservation cap was reached by the *plan's waste*,
not by the die's heat. The register's "s = 1.00 at 2.40, the ladder ends on conservation" and
"2.60 envelope only" are withdrawn as ladder properties (they remain true of the seed-shape
planner). The X1 current ladder is unaffected (currents are the die's, not the plan's); the
cost ladder, the s ladder and the top rung move. The anchor (seed shape, 138.73 W) is unchanged
because the default shape is unchanged; a second anchor at the power shape (2.00: 113.6 W,
91.5 °C) is recorded here for the same purpose.

- **P7 (added before the run) — the per-block ladder ends between 3.00 and 4.00 on
  conservation:** 3.50 holds with s = 0.93–0.98 (plan ~310–330 W of a ~335 W die); **4.00 does
  not hold** (s ≥ 1; the array cannot lift more than the die makes), with the hottest tile still
  under 30 W/mm². Falsifier: 4.00 held, or 3.50 lost. `results/array_coverage_armD_power/d3.50,
  d4.00`, 50 µm.

  **P7 confirmed** — 3.50 holds with **s = 0.99** (319.2 W of a 321.8 W converged die: conservation),
  peak 90.3 °C, hottest tile 23.1 W/mm² (35× under the film); **4.00 is bistable** — no plan in the
  bracket keeps the die on the cool branch (hot branch 182 °C, `unconverged`). **The per-block
  ladder ends on conservation at 3.50 W/mm²**, two rungs above the seed shape's 2.40. Register
  §1.3 / §2 and the ladder §2.1 carry the bracket.




## `[x]` §P0.28 — the INTEGRATION ladder for the MXL-006 update memo: burial depth and tile pitch from the decoupled cold plate to the thinned, package-integrated array. PREDICTIONS, before any run  `[~]` 12 Sep 2026

**Why.** The patent update (`docs/photonic_cooling/MXL-006-PRO/Update/`) needs the one axis the
recorded ladders never swept together: the *degree of integration* — a decoupled cold plate on a
direct-die part (500 µm pitch, the array 200 µm above the transistors), a package-integrated
array on a thinned die (100 / 50 µm burial), and a die-integrated one (20 µm). `--burial-um`
sets where the pixel plane sits above the active layer (`die_stack.StackSpec.source_depth_um`);
`--pitch-um` the tile size. Everything else is the recorded reference (34-core, arm D, 88 CFM,
target device, scalar 45 K, full coverage, target 92 °C), **100 µm cells with the 100 µm
reference rows of `results/x3_u70/ref/array/` as the recorded 200 µm / 500 µm baseline** (their
plans are 8–50 % below the 50 µm ones; never mix grids). `scripts/integration_ladder.sh` →
`results/integration/b<burial>/p<pitch>/d<density>`: burial {100, 50, 20} × pitch {500, 200} ×
density {1.20, 2.00, 2.40, 2.60, 3.00} for `array_on`, plus pitch 200 at burial 200, plus the
reference at 2.60 and 3.00 on this grid, plus `array_idle` at 1.20 for each burial (the passive
cliff). ~40 points at PAR 6.

- **P1 — the plan falls with burial.** At 2.00 W/mm² the minimum plan falls from **126 W**
  (200 µm, 100 µm grid) to **95–115 W at 20 µm** (10–25 % less): 200 µm of silicon smears the
  removal into a die-wide plan; at 20 µm the tiles resolve the cALUs and remove less. Falsifier:
  < 5 % at 20 µm.
- **P2 — the top rung rises by one, and conservation still ends the ladder.** 2.60 W/mm²
  holds under the injected cap at burial ≤ 50 µm (it is envelope-only at 200 µm); **3.00 holds at
  no burial** — the array cannot lift more than the die makes, and thinning moves the transport,
  not the conservation, limit. Falsifier: 3.00 held at any burial, or 2.60 lost at 20 µm.
- **P3 — pitch is inert at 200 µm burial and matters at 20 µm.** At 200 µm burial the 200 µm
  and 500 µm pitches agree within **2 %** (the recorded plateau, §P0.16); at 20 µm burial the
  200 µm pitch is **10–20 % cheaper** than 500 µm at 2.00 (the silicon no longer does the
  smearing, so the tile does). Falsifier: < 3 % at 20 µm.
- **P4 — the passive cliff does not move with burial.** The unpowered array diverges at 1.20 at
  every burial (a thinner die spreads less, if anything): the rescue is the laser's, not the
  thinned die's. Falsifier: idle holds 1.20 at any burial.
- **P5 — the peak tile flux rises with integration and stays ≥ 80× under the device.** At 2.00
  the hottest tile's demand rises from ~3 W/mm² (200 µm) to **5–10 W/mm² at 20 µm / 200 µm
  pitch**, against 813 W/mm² at 300 K. Falsifier: > 20 W/mm².

### `[x]` §P0.28 RESULT — thinning the die does NOT make the rescue cheaper: the plan is insensitive to burial depth from 200 to 20 µm (±10 %, a shallow optimum near 100 µm) and to pitch (≤ 7 %); the 200 µm of silicon is a spreader the array benefits from; 3.00 W/mm² holds only at intermediate burial

`results/integration/` (38 driven + 3 unpowered points, 100 µm, ~60 min at PAR 6),
`examples/integration_ladder_report.py` → `docs/evidence/integration_ladder.json`, figure
`docs/photonic_cooling/MXL-006-PRO/Update/figures/fig_integration_ladder.png`. Reference at 200 µm
burial / 500 µm pitch = `results/x3_u70/ref/array/` (100 µm grid). `[!]` The three `array_idle`
rows at 100 / 50 / 20 µm were written to the driven rows' directories and skipped by the DONE
marker; re-queued as `d1.20_idle` and landed.

| burial (µm) | pitch (µm) | 1.20 | 2.00 | 2.40 | 2.60 | 3.00 |
|---|---|---|---|---|---|---|
| 200 (the reference) | 500 | 8.7 W | **126.1 W** | 205.4 | 233.3 | no steady state |
| 200 | 200 | 7.1 | 120.9 | 197.2 | 233.0 | no steady state |
| 100 | 500 | 1.5 | **112.6** | 183.4 | 215.2 | **289.0 W (held, injected cap)** |
| 100 | 200 | 1.5 | 114.9 | 182.9 | 214.7 | 271.3 (held) |
| 50 | 500 | 6.2 | 119.2 | 190.9 | 228.0 | not held (95 °C, hot branch) |
| 50 | 200 | 3.0 | 113.6 | 181.0 | 212.8 | 278.2 (held) |
| 20 | 500 | 15.9 | **130.8** | 209.4 | 242.5 | no steady state |
| 20 | 200 | 8.4 | 121.6 | 199.6 | 227.4 | not held (99 °C) |

Max tile flux at 2.00: **5.0–5.1 W/mm² at 500 µm pitch and 8.1–8.3 at 200 µm at EVERY burial**
(set by the tile area and the plan, not by burial); at 3.00 / 200 µm pitch **14.2–14.8 W/mm²** —
the highest steady tile demand in the repository (register §4 amended; 55× under the device).

**Scorecard.** **P1 falsified** — the plan at 2.00 is 126 → 113 → 119 → 131 W from 200 to
20 µm burial at 500 µm pitch (−11 % at 100 µm, **+4 % at 20 µm**), 121 → 115 → 114 → 122 at
200 µm pitch: a shallow optimum near 100 µm, not a monotone fall; the 200 µm of silicon smears
the removal, but it also smears the hot spot, and on this planner (uniform seed envelope) the
two nearly cancel. **P2 falsified in both clauses** — 2.60 holds at *every* burial on this grid
(the 50 µm grid had it envelope-only at 200 µm); **3.00 holds at 100 µm burial (289 W under the
injected cap, s ≈ 0.95) and at 50 µm / 200 µm pitch**, diverges at 200 µm and at 20 µm / 500 µm,
and lands on the hot branch at 50 / 500 and 20 / 200: the top rung is highest at *intermediate*
burial — thin enough for the tiles to reach the hot spots, thick enough to spread them.
**P3 not as predicted** — the pitch is worth 4 % at 200 µm burial (not ≤ 2 %) and **7 % at 20 µm**
(not 10–20 %); the direction holds (pitch matters more where the silicon spreads less) and at
3.00 the 200 µm pitch is what turns a divergence into a hot-branch hold at 20 µm. **P4 confirmed** — the
unpowered array diverges at 1.20 at every burial (200 / 100 / 50 / 20 µm): the rescue is the
laser's, not the thinned die's. **P5 confirmed on the number,
wrong on the mechanism** — 8.1–8.3 W/mm² at 200 µm pitch (predicted 5–10) but flat in burial.

`[+]` **What this says for the memo and the ladder.** The rescue cost and the top rung are
nearly independent of how close the tiles sit to the transistors — a decoupled cold plate on a
200 µm die is within 10 % of an array integrated 20 µm above the active layer, and thinning the
die *loses* the 3.00 rung at 500 µm pitch. Integration's value is therefore not in the thermal
cost on this floorplan; it is in what it enables structurally (the two-sided stack, the density
co-design) and in resolving sharper hot spots with finer pitch at shallow burial, where the
planner's envelope shape (uniform seed; the `power` shape of §P0.24 was not tried here) may hide
a gain — that is the open item. MEASURED at 100 µm cells; the 3.00 rows are under the injected
energy cap and would want the converged cap before being quoted as operating points.

## `[x]` §P0.27 — X1/X2/X3/X4: the ladder past its thermal end — PDN headroom, EM acceleration and thermal clock skew from the RECORDED fields; the dense cluster at the book's utilisation. PREDICTIONS, before any run  `[x]` 11 Sep 2026

`docs/PHYSICAL_DESIGN_CONSTRAINTS.md` §1–§2; the brief is `NEXT_SESSION_PROMPT.md` (10 Sep). No
new coupled solve. The recorded solve trees hold every iteration's POWER map (`iter_NNN/IC.flp`,
`MR.flp`) and no TEMPERATURE field — the session path renders the stack and spawns no emulator
(`ice_server.py`), so the loop's converged field survives only as the row's summary (`peak_C`,
`die_span_K`). **Step 0 re-solves each recorded final power map once, linearly, through the
session on the node** (`examples/field_resolve.py`, queued as `x1_fields.par4.tsv`; 35 fields:
the rescue ladder's `array_on` 1.00–2.40 and `array_idle` 1.00–1.10, the native 0.78 control and
idle, the D1 family's seven holding array rungs, the twelve F1c rows) and writes the per-block
field under `results/fields/`. `[!]` The pass that is re-solved is selected by the row's own
`heat_removed_W`: the last `itNN` of an `array_on` tree is the bisection's largest **failing**
plan, not the minimum (checked on d2.00 before writing this: it10's `MR.flp` sums to −137.91 W
against the recorded 138.73 W minimum).

**Assumptions, stated once.** `V_dd` = **0.70 V** on every injected-power rung (the trace's
supply; the density ladders scale watts at fixed clock and voltage); on the F1c rows the row's
own voltage from its V/F source (SPICE: 0.77 V at the 4.17 GHz ceiling; the table: 1.32 V at
4.86 GHz). Per-block current density `J = P_block / (V_dd · A_block)` [A/mm²]. The reference map
is the **native die** — the driver's control arm at 0.78 W/mm², 3.8 GHz, 0.70 V
(`results/dark_silicon/d0.78/f1.00/34c_control`: 76.8 W converged, 78.6 °C, holds) — the rails a
conventional floorplan of this die is sized for. Black's law `MTTF ∝ J⁻ⁿ exp(E_a / kT)` with
**n = 2, E_a = 0.9 eV** (Cu; textbook values, stated, not fitted); the acceleration of a design
against the reference at the same block is `(J / J_ref)ⁿ · exp(E_a / k · (1/T_ref − 1/T))`.
Thermal skew: one H-tree per domain (core: one core's 33 blocks by the `_N` suffix; die: all
1126), insertion delay **D_ins = 150 ps core-level, 500 ps die-level** (stated), half wire /
half cell, `α_R` = 0.40 %/K (Cu), `α_cell` from the card's `I_on(400 K) / I_on(300 K)` = 0.942
(delay ∝ V / I_on → 0.062 %/K); `T_skew,th = D_ins · ΔT_domain · (0.5 α_R + 0.5 α_cell)` with
`ΔT_domain` the hottest-minus-coldest block in the domain; the frequency cost is
`T_skew,th / T_period` at the row's clock (book pp. 55–56: `f_max = 1 / (T_comb + T_setup +
T_skew + T_jitter)`, the skew term alone).

- **P0 — the re-solve reproduces the recorded field.** Every re-solved peak matches the row's
  `peak_C` within **1 K** (the loop's verification tolerance) and the peak block is the row's.
  Falsifier: any point off by > 1 K — then these are not "the recorded fields" and the section
  stops there.
- **P1 — the rescue ladder is a current ladder.** At fixed clock and `V_dd` the injected-power
  rungs scale every rail alike: die-average `J / J_ref` ≈ **1.3 / 1.5 / 2.0 / 2.5 / 2.9** at
  1.00 / 1.20 / 1.60 / 2.00 / 2.40 (converged watts over the native 76.8 W), and the peak block's
  ratio is within **10 %** of the die-average (uniform scaling; only the leakage share breaks it).
  Falsifier: a peak-block ratio more than 1.3× the die-average on the reference die. What this
  names: **above ~1.3 W/mm² the laser holds a die whose rails carry 1.7–3× the current they were
  sized for** — the PDN is the gen-1 constraint the thermal solve cannot see.
- **P2 — the dense cluster doubles the peak rail current at matched watts.** On the ×0.5 member
  the cALU's `J / J_ref` is **2.0–2.3×** the reference's at the same die watts (2× by
  construction; the rest is the hotter cALU's leakage); ×0.25: 4.0–4.6×; the die-average is
  unchanged (±5 %). Falsifier: < 1.8× or > 2.6× on ×0.5. This is the number that rewrites gen 1's
  "what binds next": not conservation — **the cluster's rails**, unless they are re-sized 2× / 4×.
- **P3 — the clock rungs raise current less than the cubic law suggests, because the voltage
  does the work.** F1c laser rows relative to native (`I = P / V`): **1.5–1.8× die-average at
  4.17 GHz / 0.77 V** (127 W at 1.00, 151 W at 1.20), **1.5–1.7× at 4.86 GHz / 1.32 V on the
  table** (230 W); the above-table row (189 W at a clamped 0.77 V) 2.1–2.3× — ARGUED only, the
  voltage is clamped. Falsifier: the table rung above 2× or the SPICE 1.20 rung below 1.5×.
- **P4 — the reliability dividend is 1.6–2.5× at the peak block, not 5–10×, unless the control
  has no steady state.** Black's temperature term between the array's 92 °C landing and a
  control at its 100 °C limit is exp(0.9 eV / k · (1/365 − 1/373)) = **1.85×**; against the
  unpowered array's 103.7 °C at 1.10, **2.4×**; against the native control (78.6 °C) the GaAs
  layer alone (7 K cooler) is 1.7×. The `J` term works against it on the F1c rows (the laser rung
  carries more current) and is neutral on the ladder at matched power. The brief's 5–10× needs
  25–30 K at the peak block, which only a control with **no steady state** provides — there the
  acceleration is infinite and the ratio is not a number. Falsifier: < 1.5× at matched power.
- **P5 — thermal skew is a core-level few percent and a die-level tens of percent.** On the
  laser field at 1.20–2.00: core-domain `ΔT` **20–40 K** (cALU at 92 °C, the L2/L3 slice 30–40 K
  cooler) → `T_skew,th` 7–14 ps at D_ins 150 ps → **2.5–5 %** of the 263 ps period at 3.8 GHz;
  die-domain `ΔT` 50–75 K (`die_span_K` on the rows) → 15–25 % — the number that says why a die
  this size runs per-core clock domains; reported, not claimed.
- **P6 — the array's flattening buys 1–3 % of clock at the same density** (the brief's
  prediction). In F1c at 1.00 and 1.20 the control at its thermal limit (cALU 98.5 °C, the rest
  cooler) has a LARGER core-domain `ΔT` than the laser row (cALU clipped to 92 °C on a die that
  dissipates 30–60 % more): the core-level skew cost is **1–3 % of the period lower** on the
  laser field. Falsifier: < 0.5 % (uniformity is not a clock lever on this die), or the laser
  field the less uniform one.
- **P7 — density costs skew as well as watts.** The ×0.5 member's core-domain `ΔT` at matched
  watts is **1.2–1.5×** the reference's (a 2× denser, hotter cluster beside unchanged caches);
  ×0.25: 1.4–2×. Falsifier: ≤ 1.1× (the plan's clipping flattens the cluster).
- **P8 — the gradient grows along the ladder even as the plan pins the peak.** Core-domain `ΔT`
  on `array_on` at 2.00 is ≥ **1.5×** its value at 1.20 (the peak is held at 92 °C; the caches,
  never cooled, warm with the die average). Falsifier: flat within 20 %.

Nothing here is a thermal measurement of a new configuration: the fields are MEASURED
(re-solved from the recorded maps), `J` is arithmetic on them, and every acceleration, lifetime
and skew figure is ARGUED on the stated constants. The register row will say so in that order.
`[!]` Not a run of anything on the login node: the 35 re-solves go through the campaign server.

### `[x]` §P0.27 RESULT (X1/X2) — the rescue ladder is a CURRENT ladder: every rung above ~1.3 W/mm² runs the rails at 1.7–3× the native current, the cooled die's worst block ages 12–50× faster than the native's under Black's law, and thermal skew is a cost of the rescue, not a lever

`results/fields/` (34 fields, 6 min at PAR 4 on the node), `examples/field_resolve.py`,
`examples/pdn_em_skew_report.py` → `docs/evidence/pdn_em_skew.json`. Every acceleration and skew
figure below is ARGUED on the constants stated above (V_dd 0.70 V; n = 2, E_a = 0.9 eV; D_ins
150 / 500 ps, α_R 0.40 %/K, α_cell 0.062 %/K); the fields and the current densities are MEASURED.

**P0 — confirmed to the third decimal.** All 34 re-solved peaks match the recorded `peak_C` to
**±0.000 K** at the recorded peak block: the last `iter_NNN` of the selected pass IS the loop's
final accepted solve. The maps below are the recorded fields.

**X1 — the PDN-headroom map.** Die current relative to the native die (76.8 W at 0.70 V =
110 A), and the peak block's current density against the same block on the native map:

| field | V | P (W) | I / I_native | J at the peak block / native | worst EM block: AF vs native (J ratio, °C) |
|---|---|---|---|---|---|
| native control 0.78 | 0.70 | 76.8 | 1.00 | 1.00 (cALU_16) | 1.0 (BTB_0) |
| rescue 1.00 (idle) / 1.10 / 1.20 | 0.70 | 99–118 | **1.29 / 1.45 / 1.54** | 1.33 / 1.49 / 1.54 | 6.6 / 16.5 / 12.0 |
| rescue 1.60 / 2.00 / 2.40 (laser) | 0.70 | 154–221 | **2.00 / 2.45 / 2.88** | 2.05 / 2.56 / 3.08 | **21 / 40 / 50** (cALU_32 at 90–92 °C; J² alone 4.2 / 6.6 / 9.5) |
| D1 ×0.5 at 121 / 162 / 202 W | 0.70 | 118–185 | 1.53 / 1.98 / 2.41 (= the reference's) | **3.05 / 4.07 / 5.08 — exactly 2.0× the reference's at matched watts** | 43 / 96 / 143 |
| D1 ×0.25 at 121 / 162 W | 0.70 | 115–150 | 1.50 / 1.95 | **6.04 / 8.06 — 3.9×** | 196 / 423 (iALU_32) |
| F1c SPICE, 1.00: control 3.66 GHz / laser 4.17 GHz | 0.68 / 0.77 | 93 / 127 | 1.25 / **1.50** | 1.31 / 1.55 | control **26.8 (IF_0 at 91.5 °C)** / laser **8.4 (cALU_32 at 85 °C)** |
| F1c SPICE, 1.20: control 3.32 / laser 4.17 | 0.63 / 0.77 | 90 / 151 | 1.30 / **1.78** | 1.38 / 1.86 | 40.2 (IF_0) / 15.0 (cALU_32) |
| F1c table, 1.00: control 3.64 / laser 4.86 GHz | 0.90 / 1.32 | 90 / 230 | 0.92 / **1.60** | 0.95 / 1.73 | 8.8 (IF_0) / **19.6** (cALU_32) |

**P1 confirmed** — die current 1.29 / 1.54 / 2.00 / 2.45 / 2.88 at 1.00–2.40 (predicted 1.3 / 1.5
/ 2.0 / 2.5 / 2.9); the peak block's ratio is within **3–7 %** of the die-average on the reference
die. **The rescue ladder is a current ladder**: at fixed clock and supply the laser holds a die
whose rails carry **1.5–3× the current a conventional floorplan of this die is sized for**
(1.54× at 1.20, 2.45× at 2.00, 2.88× at 2.40). **P2 confirmed, and sharper than predicted** —
the ×0.5 cluster's cALU carries **2.00×** the reference's current density at matched watts and
the ×0.25 cluster's 3.9×, i.e. exactly the area ratio: the "hotter cALU's leakage" the
prediction added is absent because the array clips both clusters to the same 92 °C landing. The
die's total current is unchanged (1.53 vs 1.54; 1.98 vs 2.00). **P3 confirmed** — the F1c laser
rows draw 1.50× (1.00) and 1.78× (1.20) the native current at 4.17 GHz / 0.77 V, and **1.60× at
4.86 GHz on the table**, where the 1.32 V supply buys the clock with less current than the
SPICE curve's 0.77 V; the cubic reading (2.3×) is withdrawn as the current figure — the voltage
does the work, and the table's control at 3.64 GHz / 0.90 V draws *less* current than the
native die (0.92×).

**P4 confirmed at matched power; the F1c rows say more.** Black's temperature term between the
laser's landing and the comparator at the comparator's peak block: **2.38× at 1.10 W/mm²** (laser
vs unpowered array at the same injected power; T term 2.15×, the J term 1.1× because the cooled
cALU leaks less), **1.85× from the GaAs layer alone** at native power (78.6 → 71.5 °C). At each
design's OWN worst block (the design-level statement): the laser's worst block outlives the
unpowered array's **3.4×** at 1.10. On the F1c rows, where the laser's headroom is spent on
clock, **the cooled design's worst block outlives the control's by 3.2× at 1.00 (8.4 vs 26.8
against native) and 2.7× at 1.20 while clocking 14 % and 26 % faster** — the control at its
thermal limit is leakage-bloated in its fetch units (IF_0 at 91.5 °C, J 2.4× native), the cooled
die's worst block sits at 85–88 °C; **on the shipped table the sign reverses**: at 4.86 GHz /
1.32 V / 230 W the laser's worst block ages **2.2× faster** than the control's (19.6 vs 8.8). The
brief's 5–10× exists only against a control with no steady state.

`[!]` **The ladder's non-thermal end, named.** Against the native die the cooled die's worst
block ages **12× faster at 1.20, 21× at 1.60, 40× at 2.00, 50× at 2.40** (cALU_32: J ratio 2.2–3.1
squared = 4.8–9.5, times a temperature term of 2.5–6 because the 92 °C target is 15–30 K above
where the native die runs its cALUs). Two levers are visible in that product and neither is
thermal: the rails (J ∝ 1/width — holding the native EM budget at 2.00 W/mm² needs ~2.5× the
stripe metal, the book's own remedy), and the target (92 °C is a spec choice; an EM-budgeted
target would be lower and cost cooling watts). On the dense cluster the cALU's J is 2× / 4× on
top of that (AF 143× at 202 W on ×0.5, 423× on ×0.25 at 162 W). **What binds gen 1 above
~1.3 W/mm² is the PDN — unless the rails are re-sized** — MEASURED as a current density on the
recorded fields, ARGUED as a limit until a rail model exists. `ARCHITECTURE_EVOLUTION.md` §5 and
the ladder's gen-1 row are rewritten accordingly.

**X2 — the thermal-skew metric.** Core-domain gradient (hottest − coldest of a core's 32 blocks,
L3 excluded; worst core) and its cost at D_ins 150 ps; die-domain in brackets at 500 ps:

| field | clock | ΔT_core (K) | skew cost, core (% of period) | ΔT_die (K) | die-level cost |
|---|---|---|---|---|---|
| native control 0.78 | 3.80 | 24.1 | **3.2 %** | 37.8 | 16.6 % |
| rescue 1.10: unpowered / laser (same injected power) | 3.80 | 36.9 / **31.2** | 4.85 / **4.11 %** (−0.74) | 60.6 / 50.5 | 26.6 / 22.2 % |
| rescue laser 1.20 / 1.60 / 2.00 / 2.40 | 3.80 | 31.6 / 40.3 / 49.9 / 60.2 | **4.2 / 5.3 / 6.6 / 7.9 %** | 52.8 / 62.6 / 74.0 / 92.8 | 23 / 28 / 33 / 41 % |
| D1 ×0.5 at 121 / 162 / 202 W | 3.80 | 39.7 / 49.5 / 59.5 (**1.26 / 1.23 / 1.19×** the reference's) | 5.2 / 6.5 / 7.8 % | 55 / 66 / 88 | 24 / 29 / 38 % |
| D1 ×0.25 at 121 / 162 W | 3.80 | 52.1 / 65.9 (**1.65 / 1.64×**) | 6.9 / 8.7 % | 62 / 79 | 27 / 35 % |
| F1c SPICE 1.00: control / laser | 3.66 / 4.17 | 31.5 / 34.2 | 4.0 / **4.9 %** (+0.95) | 54 / 56 | 23 / 27 % |
| F1c SPICE 1.20: control / laser | 3.32 / 4.17 | 31.0 / 40.2 | 3.6 / **5.8 %** (+2.2) | 55 / 63 | 21 / 30 % |
| F1c table 1.00: control / laser | 3.64 / 4.86 | 30.0 / 64.2 | 3.8 / **10.8 %** (+7.0) | 51 / 96 | 21 / 54 % |

**P5 in mechanism, 1.3× above the bracket** — core-level 4.2–6.6 % at 1.20–2.00 (predicted
2.5–5 %), die-level 23–33 % (predicted 15–25 %): the core gradient is 32–50 K, not 20–40, because
the L2/L3 slices never warm with the clipped cALU. **P6 FALSIFIED** — uniformity is not a clock
lever on this die. At the same injected power the laser flattens the worst core by 5.7 K, worth
**0.74 %** of the period (predicted 1–3 %; the falsifier was < 0.5 %, so "small, not nothing"); at
the same DENSITY, where the laser's headroom has become clock and watts, **the laser field is the
less uniform one**: +0.95 points of period at 1.00, +2.2 at 1.20, **+7.0 on the table** — a
tax on the +14 / +26 / +34 % the clock search reported (net ≈ +13 / +23 / +26 % if the skew term
is charged to the period at D_ins 150 ps). **P7 confirmed in substance, one rung under the
bracket** — the ×0.5 cluster's core gradient is 1.19–1.26× the reference's (predicted 1.2–1.5;
1.19 at 202 W), the ×0.25's 1.64×: density costs skew as well as cooling watts. **P8
confirmed** — 49.9 / 31.6 = 1.58× from 1.20 to 2.00.

`[+]` What X2 says, honestly: the array pins the peak and lets the rest of the die ride the
average, so **thermal skew grows with every rung the laser buys** (3.2 % of the period on the
native die → 7.9 % at 2.40, core-level at a stated 150 ps insertion delay; the die-level number,
17 → 41 %, is why a die this size runs per-core clock domains and is reported, not claimed). It
is the second non-thermal cost of the ladder after the rails, and the first clock-tree statement
the project can make. The lever the book names — de-skew, per-core domains, HVT/LVT on clock
paths — is a CTS design lever, not a cooling one. `[!]` Coefficients are stated assumptions;
D_ins scales every skew figure linearly, so quote the gradient (K) beside every percentage.

### §P0.27.3 — X3: the dense cluster at the book's utilisation and halos. PREDICTIONS, before the build and the run

`PHYSICAL_DESIGN_CONSTRAINTS.md` §3. Every floorplan in this repository is a **100 %-utilisation
abstraction**: the tiler packs McPAT's areas edge to edge with no routing, no scan/CTS/ECO
overhead, no macro halos or channels. The book's rule (p. 34): die area = ((G + T + E)/D + IO +
M) / U with **U = 70 %** and **T = 15 %**. Built as two generator options
(`examples/generate_exec_density_family.py`): `--utilisation U --overhead T` scales every
standard-cell (non-macro) unit's area by **(1 + T)/U = 1.643** at the defaults — the leftover
`core_other` slab included, it is un-itemised control logic — with McPAT's power unchanged;
`--cache-halo-um h` grows each SRAM macro (L2, L3, iCache, DCache) by a keep-out ring of **h =
20 µm** (halo plus channel, stated; the book gives the rule `pins × pitch / layers`, not a
number) **modelled as macro area at constant macro power** — the ring is not separately
unpowered, and the caches sit at ≤ 0.3 W/mm², so the difference is under 1 K and is stated
rather than modelled. Two members: `d1_exec0.5_u70` (the ×0.5 cluster at the book's overheads)
and `d1_exec1_u70` (the reference's units at the same overheads — the utilisation control, so
that utilisation and density are separated). The rungs are the D1 rungs at **matched watts**
(111 / 121 / 162 / 202 / 243 W, `--density` = W / member mm²), arm D, 88 CFM, target device,
scalar 45 K; the shaped control probes at 45.5–101 W. `[!]` **100 µm cells, with the reference
die re-run on the same grid as the control** (corrected before the build: the reference two-die
stack at 50 µm is exactly the 366,048-unknown measured limit — 248 × 164 cells × 9 layers — and a
1.5× larger die at 50 µm would be ~540k, between it and the 629k that fails every time; D4 met
the same wall). Quote the `u70` rows only beside the 100 µm reference rows, never the 50 µm ones.

- **P9 — the die grows 1.4–1.55×.** `d1_exec1_u70`: **140–157 mm²** (logic ~57 mm² × 1.643,
  caches +3–5 %, IMC/SoC/IO with the die by the tiler's convention); `d1_exec0.5_u70`:
  **132–150 mm²**; the ×0.5 cluster's W/mm² is **1.22×** the reference cluster's (0.5 × 1.643 =
  0.82 of its McPAT area), not 2× — the D1 "2× denser" is 1.2× denser in silicon. Falsifier:
  outside 1.3–1.65× on either member.
- **P10 — the rescue survives every rung, and regains the one the ×0.5 member lost.** At matched
  watts the `u70` members are 1.4–1.55× the reference's area and spread better into the fixed
  1825 mm² base, so `d1_exec0.5_u70` holds **all five rungs to 243 W** (the ×0.5 member lost 243 W
  to the stability boundary at 2.66 W/mm²-equivalent; here 243 W is 1.6–1.8 W/mm²). 0 tiles
  capped. Falsifier: any rung lost.
- **P11 — the cost premium is against the utilisation control, not the reference.** Relative to
  the reference's plan at matched watts, `d1_exec0.5_u70`'s minimum plan (normalised to 92 °C at
  0.3247 K/W) is **0.5–0.9×** — a larger, less dense die needs less light, so the brief's "premium
  falls toward 1.1–1.3×" cannot be against the reference; **against `d1_exec1_u70`** at the same
  watts it is **1.1–1.3×** at 162–243 W and 1.5–3× at 111–121 W (the hot-spot premium of
  §P0.22.3, shrunk by the flatter cluster). Falsifier: > 1.0× against the reference at ≥ 162 W, or
  > 1.5× against the control at ≥ 162 W.
- **P12 — the passive ceiling rises in watts by the area.** The shaped control (probe) of
  `d1_exec1_u70` holds **85–100 W** and fails one rung above (reference: holds 60.7, fails 65.7),
  and `d1_exec0.5_u70` holds 75–90 W (the reference ×0.5 member: 50.5 / 60.7). Falsifier: a
  ceiling below the reference's 60.7 W on either member.
- **P13 — the peak block is a cALU on every member at every rung.**

### `[x]` §P0.27.3 RESULT (X3) — at the book's utilisation the "2× denser" cluster is 1.22× denser in silicon, the rescue holds every rung, and the cost premium against a same-utilisation reference is 1.2–1.4× at the die-wide rungs

`results/x3_u70/` (36 jobs, 100 µm, 60 min at PAR 5), `examples/x3_utilisation_report.py` →
`docs/evidence/x3_utilisation.json`; members in `docs/evidence/d1_exec_density_family_u70.json`.
Build notes: logic × (1 + 0.15)/0.70 = 1.643 with McPAT's power unchanged; a 20 µm ring on each
SRAM macro sized on the PLACED macro (the tiler scales L2 by 2.9× and the L3 slice by 0.5× after
reading the JSON — the first build sized the ring on the JSON area and overstated L2's halo);
`[!]` a parent whose children fill it to float residue (the Instruction Scheduler, 0.42 µm² of
0.30 mm²) crossed the tiler's 0.5 µm² keep-the-parent threshold once scaled and produced a
34-block `iSched` family carrying the scheduler's whole McPAT power on 0.2 µm² — sub-100 µm²
leftovers are now zeroed; the default (no-overhead) path regenerates the recorded ×0.5 member
byte-identically. The reference was re-run on the same 100 µm grid: its control cliff is the
50 µm one (holds 60.7 W, fails 70.8) and its plans are **8–50 % below** the 50 µm plans (8.7 vs
17.3 W at 121 W; 68 vs 75 at 162; 126 vs 139 at 202; 205 vs 222 at 243) — a coarser grid smooths
the cALU's peak, so **no X3 number may be read beside a 50 µm row.**

| member (100 µm) | die | shaped control: holds / fails | 111 W | 121 W | 162 W | 202 W | 243 W |
|---|---|---|---|---|---|---|---|
| `ref` (recorded reference) | 101.1 mm² | 60.7 / 70.8 W | 0.6 W (idle 102.5 °C) | 8.7 W (idle diverges) | 68.0 W | 126.1 W | 205.4 W |
| `d1_exec1_u70` (utilisation alone) | 137.7 mm² (1.36×) | **70.8 / 80.9 W** | nothing above target (84.8 °C) | 0.2 W (idle 94.6 °C) | 34.4 W | 92.5 W | 156.6 W |
| `d1_exec0.5_u70` (utilisation + ×0.5 cluster, 1.22× denser in silicon) | 121.5 mm² (1.20×) | **60.7 / 70.8 W** (= the reference's rung) | 0.07 W (idle 92.8 °C, lands 92.0) | 0.9 W (idle **107.2 °C**) | 50.5 W | 108.8 W | 182.7 W |
| plan ratio, normalised to 92 °C at 0.3247 K/W: `u70×0.5 / ref` | | | — | 0.39 | **0.75** | **0.85** | **0.90** |
| `u70×0.5 / u70×1` (density alone, at the book's overheads) | | | — | 9.8 (5.1 vs 0.5 W) | **1.44** | **1.22** | **1.16** |
| `u70×1 / ref` (utilisation alone) | | | — | 0.04 | 0.52 | 0.70 | 0.78 |

Every array rung on every member: **0 tiles capped**, peak block a cALU (on two `u70×1` rungs the
zero-power `RBB` stub inside the cluster, a sub-cell sliver that reads the cluster's temperature —
the utilisation transform leaves McPAT's "Area Overhead" key alone, which is a floorplan artefact
and not a hot block).

**Scorecard.** **P9 falsified low** — the dies grow **1.36× / 1.20×** (predicted 1.4–1.55 /
1.3–1.65): the IMC / SoC / IO tiles and the cache macros (+11–17 %) grow less than the logic's
1.643, and the ×0.5 member's cluster is **1.22× denser in silicon** (that part as predicted).
**P10 confirmed** — `d1_exec0.5_u70` holds all five rungs to 243 W with 0 tiles capped (the 50 µm
×0.5 member lost 243 W; on this grid the 100 µm reference holds 243 too, so the grid control
cannot separate "utilisation regained the rung" from "the coarser grid holds it" — say both).
**P11 half** — against the recorded reference the dense-at-70 % die is **cheaper** to hold
(0.75 / 0.85 / 0.90× at 162–243 W: predicted 0.5–0.9, confirmed — it is a larger, lower-density
die); against the utilisation control the premium is **1.44 / 1.22 / 1.16×** (predicted 1.1–1.3;
1.44 at 162 W is above the bracket, under the 1.5 falsifier), converging toward 1.16× by 243 W;
at 121 W it is 9.8× — the hot-spot rung, where the control needs 0.5 W and the 1.22× denser
cluster's unpowered array sits at 107 °C against 95 °C. **P12 not as predicted** — the passive
ceiling rose **one rung on `u70×1`** (60.7 → 70.8 W, +17 % against 1.36× of area) and **not at all
on `u70×0.5`** (the reference's rung exactly; 61.8 °C vs 71.2 at 60.7 W, then the same 70.8 W
failure): the shaped cliff is the cALU's local runaway and scales with the cluster's density
(0.61× → one rung up; 1.22× → the rung given back), not with the die area — the concentration
result of §P0.17 from a third floorplan. **P13 confirmed in substance** (cALU, or the RBB stub
inside the cluster).

`[+]` What X3 says for gen 1. Realistic floorplanning shrinks the D1 penalty and the D1 gain
alike: at the book's overheads the "2× denser cluster" is **1.22× denser**, it still holds every
rung the reference holds, and its cooling premium over a same-utilisation reference is
**1.2–1.4× at the die-wide rungs** (a hot-spot premium of ~10× at the rung where the control
needs no light). X1's rail statement scales with it — the cluster's current density is 1.22× the
reference's, not 2× — so the PDN constraint on gen 1 is a fifth tighter than the reference's,
not twice as tight. Utilisation alone makes the reference die a lower-density die: one rung of
passive ceiling and 0.5–0.8× the plan. `[!]` 100 µm cells, matched-grid reference; the 0.3247 K/W
normalisation was measured on the 101 mm² die and the larger members spread better into the
fixed base, so the normalised ratios carry ~5 % of that (the raw Q ratios agree within 5 % at
≥ 162 W); the halo is macro area at constant macro power.

### `[x]` §P0.27.4 — X4: the gen-3 stack with the 3D chapter's geometry. PREDICTIONS, before the build and the run (11 Sep; built and run the same day — RESULT above)

`PHYSICAL_DESIGN_CONSTRAINTS.md` §4. What exists: `thermal/stack_models.py` puts a thinned memory
die (50 µm default) **above** the logic die with a bond layer (5 µm, microbump/underfill
conductivity as the pessimistic default) and 3D-ICE's one-footprint rule; `die_stack.StackSpec`
puts the pixel layer over ONE processor die; `--mr-objective cache-leakage` and
`MRParams(zone_targets)` hold a named zone at 280 K; `make_extractor('cr-lisaf')`. What is
missing, and is the day's work: (a) a **storage-die floorplan** that carries the reference's L2/L3
blocks at their own positions and powers (the trace's cache dynamic + the ledger's leakage at the
solved field) and a compute-die floorplan with those blocks unpowered (the footprint stays the
reference's, so the storage die is 30 % dark silicon plus TSV keep-outs as unpowered blocks); (b)
a **three-layer spec** — pixel layer / storage die / bond / compute die — in `die_stack.py`, with
the Cr:LiSAF tiles addressing the storage die (cold side) and, as the two-array variant, the dye
array on the compute die's other face (which needs the sink on that side too); (c) the coupled
solve at `--cell-um 100` (the stacked grid at 50 µm is 1.1 M unknowns and fails). ~A day.

- **P14 — the storage die reaches its knee on its own.** With the compute die at the hot-spot
  target and the bond layer at the microbump default, the storage die's cache zone lands at
  **280–290 K for 5–15 W of Cr:LiSAF lift** (its own cold leakage is 1.35 W over 30 mm² plus what
  crosses the bond), against the 99 W that the monolithic die needed (§P0.22.2). Falsifier:
  > 40 W, or the zone above 300 K at any plan the tiles can deliver.
- **P15 — the interface is what decides it.** Swapping the bond to hybrid-bond conductivity
  (near silicon) raises the storage-die cost by ≥ 3× and pushes the zone above 295 K: the
  book's thermal vias would do the same. Falsifier: the cost moves < 1.5×.
- **P16 — the cache-leakage prize is collected**: die leakage down 2.7–3.6× on the cache zone
  (the monolithic figures), ~14 % of die power at the corrected accounting (register §1.2), at
  an electrical cost below the prize for the first time. Falsifier: the laser's electrical draw
  exceeds the leakage saved.
- **P17 — the compute die is unchanged**: its peak, plan and `s` reproduce the reference rung at
  the same density within 5 % (the caches were never where the plan acted).

- **P18 (added before the run, same day) — the single-array stack cannot isolate the storage
  die without losing the compute die.** With the array above the storage die, the compute die's
  ONLY path to the sink is through the bond and the storage die. At the hybrid (120 W/mK) and
  microbump (50) bonds the storage die sits within **2 K of the compute die** (the bond is
  ~0.001 K/W) and the whole stack behaves as the monolithic die of §P0.22.2 — the 280 K knee is
  conservation-bound again; at the underfill (5) and isolating (0.5) bonds the storage die cools
  toward its knee **and the compute die diverges at 1.00 W/mm²** (its sink is gone). Falsifier:
  a bond at which the storage zone lands ≤ 290 K AND the compute die holds 92 °C with a plan
  below the die's own power. The two-array variant (the dye array on the compute die's other
  face) is the design consequence, and it needs the sink on that face too — next session.

Built and run 11 Sep (second half of the day) after X3 landed: `die_stack.StackSpec(storage_um,
bond_um, bond_k_si)` (spec keys `storage`, `bond`, `bondk`), `ICESim.fill_storage_flp_template`,
`ICEThermalSolver(storage_flp_template=)`, `examples/split_storage_die.py` → `examples/floorplans/
outputs/gen3_stack/`, `mr_comparison.py --gen3-split`. Anchor re-run queued beside it (the stack
and solver changed; the storage die is off by default and the default path must reproduce
138.73 W / 93.875 °C). Grid 100 µm (four powered layers at 50 µm would be ~490k unknowns).

### `[x]` §P0.27.4 RESULT (X4) — the two-die stack with the storage die between the compute die and the sink collects NOTHING the monolithic die did not: at every bond from hybrid to near-insulating the 280 K objective costs the whole die, and where the bond finally isolates, the compute die loses its sink. Gen 3 as argued is falsified; the storage die must be off the heat path

`results/gen3_stack/` (17 points, 100 µm, ~2 h at PAR 4), `examples/gen3_stack_report.py` →
`docs/evidence/gen3_stack.json`; the split floorplans in `examples/floorplans/outputs/gen3_stack/`
(68 L2/L3 blocks, 30.08 mm², 29.8 % of the die, moved to a 50 µm storage die at their reference
positions; the compute die keeps them as dark silicon). Anchor after the stack/solver edits:
**138.72881 W / 93.8752 °C at cALU_16 — identical**; the suite 1079 passed + the new storage
tests. The stack (top-down): sink, the array, the storage die, a 5 µm bond of stated `k`, the
compute die — the book's face-to-back arrangement with the array on the storage (cold) side.

| bond k (W/mK) | d (W/mm²) | unpowered array: compute peak / cache zone | dye, caches at 280 K: plan, share, zone mean / max, cache leakage | Cr:LiSAF on the cache tiles: delivered, capped, zone |
|---|---|---|---|---|
| **120** (hybrid) | 1.00 | 85.8 °C / 328 K | **99.3 W, s = 1.08, 289 / 313 K**, 4.70 → **1.30 W** (3.6×), net 66 W; not held (conservation) | 73.7 W, **58 tiles capped**, 300 / 324 K, 1.77 W |
| 50 (microbump) | 1.00 | 86.1 °C / 328 K | 99.3 W, 1.08, 289 / 314 K, 1.30 W | 73.7 W, 58 capped, 300 K |
| 5 (underfill) | 1.00 | 88.3 °C / 328 K | 99.3 W, 1.08, 289 / 315 K, 1.29 W | 73.7 W, 58 capped, 300 K |
| **0.5** (isolating) | 1.00 | **DIVERGED** — the compute die's only sink is a 0.1 K/W bond and a dark die | 30.1 W (a lower bound: envelope descent hit `max_iter`), 86.8 °C, **319 / 350 K** — not held | 82.8 W, **80 capped**, 304 / 334 K — not held |
| 120 / 50 / 5 | 0.60 | 56.8–57.7 °C / 313 K | 59.9 W, 1.08, 290 / 305 K, 1.67 → 0.82 W | 46.0 W, 57 capped, 296 K |
| 0.5 | 0.60 | 64.0 °C / 315 K | 59.9 W, 1.07, 292 / 311 K | 46.0 W, 58 capped, 299 K |
| 50, hot-spot objective (P17) | 2.00 | idle diverges | **plan 121.8 W, 93.76 °C, held** — the 100 µm reference at 202 W: 126.1 W, 93.82 °C (**−3.4 %**) | — |

Monolithic reference (§P0.22.2, 50 µm, 1.00): dye 99.4 W → 289.5 K, 1.35 W; Cr:LiSAF 73.5 W,
56 capped. **The stack reproduces the monolithic die to three figures.**

**Scorecard.** **P14 falsified** — the storage die does not reach its knee for 5–15 W; it costs
the whole die (99.3 W at s = 1.08) and lands at 289 K, exactly as on the monolithic die.
**P15 falsified** — the bond's conductivity moves the cost by **< 0.1 %** across 120 → 5 W/mK
(a 5 µm bond is 0.001–0.01 K/W against a die that dissipates 99 W); only at 0.5 W/mK (0.1 K/W)
does anything move, and what moves is the unpowered array's cliff, not the storage cost.
**P16 falsified** — the cache prize is collected (4.70 → 1.30 W, 3.6×, the monolithic ratio) at
a laser draw of 66 W net against 3.4 W of leakage saved: the laser draws 20× what it saves.
**P17 confirmed** — under the hot-spot objective the compute die is the reference's within
3.4 % of plan and 0.06 K of peak: the split changed nothing the planner acts on. **P18 confirmed,
with its mechanism sharpened** — at the conducting bonds the stack IS the monolithic die (the
zone is within 2 K of the monolithic landing); at the isolating bond the unpowered array
diverges at 1.00 (the compute die's sink is gone) and neither objective holds (the dye's
descent runs out at 30 W with the caches at 319 K; Cr:LiSAF caps 80 tiles). No bond satisfies
the falsifier (zone ≤ 290 K AND the compute die held below its own power).

`[!]` **What this says, and it is a rung of the ladder falsified by measurement.** The gen-3
argument (`EVOLUTION_LADDER.md` §4.2, 9 Sep) was that the separate die makes the storage-zone
material viable because its tiles then lift only the storage die's own 1.35 W. That is true
only if the compute die's heat does not pass through the storage die — and in the face-to-back
stack with the array on the sink side, **all of it does**: the storage die is the compute die's
heat path, so the array above it must lift the whole die's heat to hold it cold (s = 1.08,
conservation), and making the bond insulating merely takes the compute die's sink away. The
1.24 K / 40 W result (§P0.7 TEST 1) has reproduced itself one layer up, as `EVOLUTION_LADDER.md`
§4.2 warned it might. **The design consequence:** the storage die must be **off the compute
die's heat path** — beside it on an interposer (2.5D) with its own tiles, or on the compute
die's far face with the compute die's sink and dye array on the other side (the two-array
variant, which needs a sink on both faces) — so that the only heat crossing into the storage
zone is what the interface conducts *laterally*. That is ARGUED; its measurement is the next
build (a sink and array on the compute die's underside is a new stack, not a flag). `[!]` 100 µm
cells; the 0.5 W/mK rows carry a hot-branch baseline (register §3's open planner item) and
their costs are lower bounds; the bond is 5 µm — a thicker isolating interposer would isolate
more and cook the compute die sooner, which is the same conclusion.

### `[x]` §P0.24 RESULT, part 1 (the recorded planner) — the control has no steady state at 700 W on the simulated curve, the GaAs layer alone holds it, and the rescue path's envelope SHAPE cannot address a concentrated accelerator kernel

`results/accel_f3/` (27 invocations, 49 min), `examples/accel_f3_report.py` →
`docs/evidence/accel_f3.json`.

| point | control | `array_idle` | `array_on` (seed envelope) |
|---|---|---|---|
| uniform 700 W | **runaway** (residual creeps at 10 K under backtracking) | **holds 76.5 °C** (`MEMCTRL_B0`) | holds, nothing to do |
| uniform 1000 W | runaway | runaway | holds 93.7 °C on **464 W** (`s` = 0.45) — **unconverged** (verification 362/367/367 K) |
| uniform 1400–2600 W | runaway | runaway | "envelope insufficient" with the plan = the whole die's power |
| occ8 / occ32 at 700 and 1400 W | runaway | runaway | "envelope insufficient" — plan = the whole die's power |

**Scorecard, part 1.** **P1 FALSIFIED the other way** — the control holds *nothing*: on the
simulated leakage curve the GA100 with the assumed 25 % leakage fraction runs away at 700 W on
the very plate that held it at 64 °C on the pipeline curve (`microchannel_coldplate.json`,
26 Aug). The die sits at ~337 K there, *below* the 345 K crossover where the simulated curve
carries ~9× the pipeline's feedback gain (§P0.14) — the same mechanism that moved the CPU's
flat ceiling down, now taking an accelerator's whole operating point. `[!]` This rests on an
ASSUMED leakage fraction and class split (`calibrated: false` on every row); the register must
carry it as "the accelerator's control ceiling depends on the leakage curve by more than a
rung", not as a GA100 number. **P2 confirmed** — the unpowered GaAs layer holds 700 W where the
grease stack does not (the passive term, one rung). **P3 open/unfavourable** — the laser's top
rung is 1000 W and that row is unconverged. **P4 open** — max tile flux 1.5 W/mm² at 1000 W:
the device is 500× under-used even here. **P5 FALSIFIED as run** — no kernel point holds at
"full capability". **P6** cannot be scored (the control holds nothing).

`[!]` **Why the kernel points failed, and why it is the planner, not the physics.** Every
"envelope insufficient" log says the same thing: *"MR plan wanted 16515.0 W from a die
dissipating 369 W (45×) and was scaled"*. 16 515 W is **367 blocks × 45 W**: the envelope path
seeds every block's sensitivity at the 1.0 K/W placeholder, so `dt_max / s` = 45 W per block
regardless of the block's power, and the conservation cap then scales that *uniform* shape by
45× — the eight hot SMs of the occ8 kernel receive ~1 W each while cool blocks are pushed to
the floor. "Full capability" was never the array's full capability; it was a guessed shape
scaled to conservation. That is register §3's "plan shape" item (§P0.19 measured the same shape
costing 30 % on the CPU), and on a 367-block accelerator with a concentrated kernel it costs
the rescue outright. The CPU rescue ladder's rows carried the same seed (the 2.00 W/mm² log
reads "wanted 19 982 W … scaled by 0.0099") and held because a 34-core die under uniform
activity is close enough to uniform; the accelerator is not.

**Built in response (additive, flagged):** `MRParams(envelope_shape='power')` /
`--mr-envelope-shape power` on both drivers: each block is additionally capped at its **own
dissipation**, so the full-capability plan removes every block's own heat, meets conservation
by construction, and starts the descent from the physical "s = 1" state. Default `seed`
(every recorded row reproduces). Three tests.

**Predictions for part 2 (the `power`-shape re-run of the nine `array_on` points), before it
runs:** **P7** — every uniform point up to 2000 W holds at full capability and the descent finds
a minimum plan; the top holding rung is **1400–2000 W** (bistability or conservation above).
**P8** — the concentrated kernels hold: occ8 at 700 W for **20–60 W** on the active SMs' tiles,
occ8 at 1400 W for ≤ 200 W; the peak block is an SM datapath. **P9** — max tile flux reaches
**≥ 20 W/mm²** on the occ8 kernel (0 tiles capped). Falsifiers: any uniform point ≤ 1400 W
still "envelope insufficient" under the power shape (then the accelerator's runaway is not a
shape problem); occ8 at 700 W not held.

### `[~]` §P0.24 RESULT, part 2 (the `power` envelope shape) — every point finds a cool-branch plan; the device is still 150× under-used; the peaks are brackets until the loop is given its budget

`results/accel_f3_power/` (9 `array_on` invocations, 77 min), `examples/accel_f3_report.py --base
results/accel_f3_power` → `docs/evidence/accel_f3_power.json`.

| point | seed shape (part 1) | **power shape**: peak, plan, `s` | max tile flux | verification (3 dampings) |
|---|---|---|---|---|
| uniform 1000 W | 93.7 °C on 464 W (unconv) | **91.3 °C on 110 W**, `s` 0.09 | 1.3 W/mm² | 364.4 / 364.4 / 364.5 K — agree to 0.1 K, none to the 0.1 K residual |
| uniform 1400 W | envelope insufficient | **91.4 °C on 527 W**, `s` 0.33 | 2.1 | agree within ~1 K |
| uniform 2000 W | envelope insufficient | 76.7 °C on 1304 W, `s` 0.65 | 3.9 | — |
| uniform 2600 W (3.15 W/mm²) | envelope insufficient | 70.3 °C on 2294 W | 5.3 | **344 / 359 / 402 K — damping-dependent, not quotable** |
| occ8 700 W | envelope insufficient | **90.7 °C on 32.5 W**, `s` 0.08, `SM0_DP` | 1.4 | 361.7 / 363.8 / 363.8 K |
| occ8 1400 W | envelope insufficient | 78.1 °C on 317 W, `s` 0.43 | 4.6 | — |
| occ32 700 / 1400 W | envelope insufficient | 87.6 °C on 115 W / 88.5 °C on 563 W | 1.6 / 4.4 | — |

**Provisional scorecard.** **P7 better than predicted** — the laser holds the accelerator at
every rung of the ladder to 2600 W (3.15 W/mm²), the top of the ladder, not 1400–2000: not
bracketed above. **P8 half right** — occ8 at 700 W costs 32.5 W (inside 20–60) with the peak on
an SM datapath; occ8 at 1400 W costs 317 W (outside ≤ 200). **P9 FALSIFIED, and it matters for
the thesis** — the most any tile is asked for is **5.3 W/mm²** even at 3.15 W/mm² of die
average and 4.6 W/mm² on the concentrated kernel, against ≥ 813 W/mm² from the dye at 300 K
tiles: **the target device is 150× under-used on the accelerator too**, at 500 µm pitch. The
"ideal design point" of the extractor is not reachable by any die in this repository at this
pitch; what the device's headroom buys is pitch (finer tiles, §P0.16's plateau) and margin,
not rescue.

`[!]` **Every power-shape row is `unconverged`**, and the reason is the loop's budget, not the
physics on most of them: the three damping levels agree to 0.1–2 K (uniform 1000 W: 364.4 /
364.4 / 364.5 K) but none reaches the 0.1 K residual in 60 iterations on a die whose loop gain
is near one (the same signature as the D1 55.6 W rung, §P0.22.3). The 2600 W row is the
exception — genuinely damping-dependent — and stays a bracket. A re-run with the residual
tolerance and iteration budget the accelerator needs (`--tol 0.5 --max-iter 150`) is queued as
part 3; until it lands these rows are **brackets, not numbers**, and the register carries them
as such.

### `[x]` §P0.24 RESULT, part 3 (final) — with the power-shaped envelope and the loop's own budget, the laser holds the GA100 from 700 W to 2600 W on the microchannel plate; the top rung is conservation; the device is 150× under-used

`results/accel_f3_power_tol1/` (8 `array_on` invocations, `--tol 1.0 --max-iter 100`, every
row **converged** — verification passed at three damping levels), `examples/accel_f3_report.py
--base results/accel_f3_power_tol1` → `docs/evidence/accel_f3_power_tol1.json`. Part 2's
numbers move by ≤ 7 % and the residual plateau (0.4–0.7 K on a 365 K field) was the loop's
0.05 K tolerance, not the physics.

| GA100 on the microchannel plate, 100 µm, simulated curve, 25 % leakage assumed | control | GaAs, no light | **laser on** — peak, plan, `s` | max tile flux |
|---|---|---|---|---|
| uniform 700 W (0.85 W/mm²) | runaway | holds 76.5 °C | nothing to do | 0 |
| 1000 W (1.21) | runaway | runaway | **88.3 °C on 102 W** | 1.3 W/mm² |
| 1400 W (1.69) | runaway | runaway | **86.4 °C on 514 W**, `s` 0.32 | 2.1 |
| 2000 W (2.42) | runaway | runaway | 75.6 °C on 1289 W | 3.9 |
| **2600 W (3.15)** | runaway | runaway | **67.0 °C on 2244 W, `s` 0.98 — conservation** | **5.3** |
| occ8 700 W | runaway | runaway | **85.0 °C on 31.6 W** (`SM0_DP`) | 1.4 |
| occ8 1400 W | runaway | runaway | 76.9 °C on 312 W | 4.6 |
| occ32 700 / 1400 W | runaway | runaway | 86.3 °C on 113 W / 77.1 °C on 557 W | 1.6 / 4.4 |

**Final scorecard.** P1 falsified the other way (the control holds nothing on the simulated
curve — an assumed-leakage result); P2 confirmed (the passive layer holds 700 W); **P3
confirmed in substance** — the laser holds ≥ 2000 W and, with `s` = 0.98 at 2600 W, the ladder
ends on conservation at the top rung, as on the CPU; `s`(2000) = 0.65 (predicted ≤ 0.6: the
plate does less of the work than the cubic estimate said); **P4 FALSIFIED** — max tile flux
**5.3 W/mm²** against ≥ 813 available: the device is **150× under-used on the accelerator**, so
"the accelerator is where the device's rungs matter" is withdrawn; **P5 confirmed in the hold,
not the cost** — occ8 at 1400 W costs 312 W (predicted ≤ 120); at 700 W, 32 W; the hot spot is
an SM datapath at 700 W and an HBM PHY / memory-controller block at 1400 W (the perimeter
stops spreading the concentrated kernel's heat). **P6** cannot be scored against a control
that holds nothing; against the passive layer's 700 W the laser's multiplier is **3.7×** in
watts. **P7 better than predicted** (to the ladder's top, 2600 W); **P8** half; **P9
falsified** (5.3 W/mm²).

`[+]` **What the pack may say, and how.** *On a direct-die microchannel plate the photonic
array holds a GA100-class accelerator at every power from 700 W to 2600 W (3.15 W/mm²) where
the conventional stack has no steady state, ending on energy conservation at the top rung; a
concentrated eight-SM kernel at 700 W is held for 32 W of removal.* Beside it, always: the
control's runaway is a **simulated-curve, assumed-leakage** result (`calibrated: false`), the
rows are at 100 µm cells, and the extractor is 150× under-used — the accelerator does not
need the device's ideal design point either; it needs the array's *shape* to follow the power
(§P0.24 part 1's lesson, now the `power` envelope shape). Three rows for the register: the
accelerator rescue range, the envelope-shape rule, and the tile-flux ceiling across all dies.

## `[x]` §P0.26 — F1c: throughput with the CLOCK as the free variable (the missing DVFS in the density ladders). PREDICTIONS, before any run  `[~]` 10 Sep 2026

**Why (user, 10 Sep).** The proposal pack's TFLOP/s was flat against die power: the density
ladders inject watts at a fixed clock (the trace is 3.8 GHz, rescaled), and `gflops` is
`f_effective × 32 × cores` with `f_effective` the nominal clock derated by the hottest block —
a thermal-only proxy that cannot rise with power by construction. Throughput is ops over
walltime, and walltime falls only when the clock rises. The clock search
(`clock_headroom.py` / `clock_search.py`) is the measurement: the clock is bisected to the
thermal limit with dynamic power ∝ V²f through the V/F curve and leakage ∝ V (assumed exponent
1.0). Its recorded run was on the pipeline curve, with the MR arm read at the spec-limited
point, and inside a V/F table that stops at **5.0 GHz / 1.4 V** (`vf_clamped` above).

**The run.** `scripts/clock_f1c.sh` → `results/clock_f1c/`: 34-core, arm D, 88 CFM with the
spreading base (this package, 0.325 K/W), three arms, `--vf-source spice` (§P0.18.3's device
curve, α = 1.45, anchored 3.8 GHz at 0.70 V), thermal limit 100 °C, MR target = limit − 8 K,
scalar 45 K, full coverage, `--recovery-at-junction`; bisection 2.0–5.0 GHz at 0.05 GHz. A
second invocation with `--above-vf-table` to 6.5 GHz, whose clocks are UPPER BOUNDS (the
voltage clamps, the power cost of the clock is understated) and are reported as ARGUED.
Throughput is then `f × 32 × 34` FLOP/s at the measured sustainable clock (ops / walltime at
fixed IPC), per package watt.

- **P1 — the control is runaway-limited near the trace's own clock:** **3.8–4.0 GHz** (the
  recorded 3.83 GHz at 0.3 K/W on the pipeline curve; at the runaway point the die is above the
  345 K crossover, where the simulated curve carries *less* gain, so at or slightly above).
  Falsifier: ≥ 4.2 GHz (the control reaches the spec, and the laser has no runaway to remove).
- **P2 — the unpowered array is spec-limited: 4.1–4.3 GHz**, limiter the 100 °C limit.
- **P3 — the laser runs into the table, not the cooler:** `array_on` reaches **5.0 GHz with
  `vf_clamped`**, the die at 1.4–1.9 W/mm² there (inside the 2.4 rescue), removing 30–110 W.
  That is **+25–32 % clock and FLOP/s over the control**. Falsifier: `array_on` < 4.5 GHz (the
  V²f cost eats the rescue).
- **P4 — above the table (ARGUED):** `array_on` reaches **5.5–6.2 GHz** before conservation or
  bistability at ≥ 2.4 W/mm² ends it — the cubic-law reading of the 3.8× watts (1.56× clock,
  5.9 GHz) as an upper bound with the voltage clamped. Never quoted as a clock.
- **P5 — FLOP/s per package watt falls monotonically with clock on every arm** (V²f), so the
  headline is throughput per *package*, not efficiency — as §P0.23.1 said.

### `[x]` §P0.26 RESULT, part 1 — on the trace's own power the clock is device-limited, not thermally limited, on every arm; the search has to start from the ladder's operating point

`results/clock_f1c/{cfm88,cfm88_above_table}`, `examples/clock_f1c_report.py` →
`docs/evidence/clock_f1c.json`. Three minutes for both runs — the first sign something was off.

| run | control | `array_idle` | `array_on` | die power at the ceiling |
|---|---|---|---|---|
| SPICE V/F, to the device ceiling | **4.173 GHz**, `vf_envelope`, 50.2 °C | 4.173, 46.7 °C | 4.173, 46.7 °C, 0 W removed | 38.6 W (0.38 W/mm²) |
| `--above-vf-table` to 6.5 GHz (voltage clamped: upper bound) | **6.50 GHz**, search ceiling, 67.0 °C | 6.50, 61.5 °C | 6.50, 61.5 °C, 0 W | 59.4 W (0.59 W/mm²) |

**Why.** The clock search scales power from the trace's *own* operating point: the replicated
single-thread LINPACK trace is **31.1 W on the die at 3.8 GHz — 0.31 W/mm²** under the
corrected accounting — so at the device's 10 % overdrive ceiling (4.173 GHz at 0.770 V, the
SPICE curve's `f_max`) the die is at 50 °C, and even at a clamped 6.5 GHz it is at 67 °C.
**No arm ever meets a thermal limit**, the laser removes nothing, and P1/P3/P5 are "not as
predicted" for a reason that has nothing to do with the cooler: the density ladders — every
rescue, dark-silicon and D1 row — sit **2.5–8× above** this trace's native density. The
thermal problem the array solves belongs to workloads that dense (vector-heavy code, the
accelerator), not to this trace at its own power. P2 is "confirmed" only nominally (4.17 is
inside 4.1–4.3 because that is where the device ceiling is). **P4** is wrong in the opposite
sense: 6.5 GHz is the *search* ceiling, and nothing thermal stops the die before it.

`[+]` Two honest statements come out of this anyway. (1) **The device, not the cooler, caps
this die's clock on this trace:** the SPICE curve's 4.17 GHz at 0.77 V (the shipped table's
5.0 GHz is the same statement one table further) — a clock number the pack may quote with its
provenance, and one no cooler moves. (2) **Every clock-vs-cooling claim needs the operating
point stated in W/mm², not in GHz alone**, because the same clock on this die spans 0.3 to
2.6 W/mm² depending on the workload's activity.

**Built in response:** `clock_headroom.py --density` (scale the trace to `density × area` at
the trace's clock, exactly as the density ladders do, then search the clock from there).
**Part 2, predictions before the run** (`results/clock_f1c_density/`, arm D, 88 CFM, three
arms, SPICE V/F to its ceiling, plus one `table` run and one `--above-vf-table` run at 1.00):

- **P6 — at 0.78 W/mm² (the ladders' "native")**, all three arms reach the **device ceiling
  4.17 GHz** (the driver's control holds 0.78 unaided, §P0.23.2): still device-limited.
- **P7 — at 1.00 W/mm²** the control is **runaway-limited below 3.8 GHz** (it has no steady
  state at 1.00 at 3.8 GHz): **3.4–3.7 GHz**; `array_idle` **3.8–4.0** (spec- or runaway-
  limited); `array_on` reaches the **device ceiling 4.17 GHz** with 10–40 W removed — the laser
  turns a clock-down into the device's own maximum: **+13–23 %** over the control.
- **P8 — at 1.20 W/mm²** the control **3.0–3.4 GHz**, idle 3.4–3.7, laser **4.17 GHz** (the
  ceiling) with 40–90 W removed: **+25–40 %**. Falsifier for P7/P8: `array_on` below 4.0 GHz.
- **P9 — with the shipped table (5.0 GHz ceiling) at 1.00**, `array_on` reaches **4.6–5.0 GHz**
  (`vf_clamped` at 5.0) at ~1.4–1.6 W/mm²; **above the table** (ARGUED) the laser holds to
  **5.5–6.0 GHz** where the die crosses ~2.4 W/mm² and conservation ends it.
- **P10 — FLOP/s per package watt falls with clock on every arm** (V²f).

### `[x]` §P0.26 RESULT, part 2 — from the ladders' operating points the laser converts thermal headroom into clock until the DEVICE ends it: +14 % at 1.00 W/mm², +26 % at 1.20 on the SPICE ceiling, +34 % on the shipped table

`results/clock_f1c_density/` (5 runs, 37 min), `examples/clock_f1c_report.py --base
results/clock_f1c_density` → `docs/evidence/clock_f1c_density.json`. Throughput is
`f × 32 × 34` FLOP/s at the sustainable clock (ops over walltime at fixed IPC).

| operating point at 3.8 GHz | control | `array_idle` | `array_on` | laser gain vs control |
|---|---|---|---|---|
| 0.78 W/mm², SPICE V/F | **4.07 GHz** (thermal, 95.6 W) | 4.17 (device ceiling) | 4.17 (device ceiling, 0 W) | +2 % — the ceiling is 2 % away |
| 1.00, SPICE | **3.66** (thermal, 93 W) | 3.90 (thermal) | **4.17 (device ceiling), 38 W removed, 127 W die** | **+14 %** |
| 1.20, SPICE | **3.32** (thermal, 90 W) | 3.60 (thermal) | **4.17 (device ceiling), 78 W removed, 151 W die** | **+26 %** |
| 1.00, shipped table (5.0 GHz ceiling) | 3.64 | 3.92 | **4.86 GHz, thermal-limited at 100 °C**, 235 W removed, 230 W die (2.28 W/mm²) | **+34 %** |
| 1.00, SPICE, `--above-vf-table` to 6.5 (voltage clamped: upper bound) | 3.65 | 3.90 | 6.50 = the search ceiling, 154 W removed, 189 W die | ARGUED only |

GFLOP/s per package watt (die + fan + net laser) **falls with clock on every arm**: 33.9 → 33.4
at 0.78; 31.1 → 29.7 → 24.5 at 1.00; 28.8 → 27.8 → 19.5 at 1.20; 31.6 → 29.5 → 12.9 on the table.

**Scorecard.** **P6 nearly** — idle and laser at the device ceiling, the control 2 % short of
it (4.07, thermal). **P7 confirmed** — control 3.66 (3.4–3.7), idle 3.90 (3.8–4.0), laser at
the ceiling with 38 W (10–40), +14 % (13–23 %). **P8 confirmed** — 3.32 / 3.60 / ceiling with
78 W (40–90), +26 % (25–40 %). **P9 half** — on the table the laser reaches **4.86 GHz**
(4.6–5.0) but **thermally limited at 2.28 W/mm²**, not clamped at 5.0 at 1.4–1.6: the V²f cost
of the last 0.7 GHz is dearer than the cubic estimate; above the table nothing thermal stops
the laser arm before the 6.5 GHz search ceiling (its 189 W is understated by the clamp), so the
"5.5–6.0 with conservation" reading is withdrawn — the honest statement above the table is
"no bound found inside the search". **P10 confirmed.**

`[+]` **The statement the pack may make, MEASURED:** *at 1.0 W/mm² the conventional package
must clock this die down to 3.66 GHz to keep a steady state; with the photonic array it runs
at the device's own ceiling, 4.17 GHz (+14 %), and on the shipped V/F table to 4.86 GHz
(+34 %) — the laser turns thermal headroom into clock until the transistor's V/F, not the
cooler, ends it. Throughput per package watt falls on every arm as the clock rises: the array
buys performance per package, not efficiency.* Every clock carries its operating point in
W/mm² and its V/F source; the SPICE ceiling (4.17 GHz at 0.77 V, 10 % overdrive, uncalibrated)
and the table's 5.0 GHz are both model ceilings, stated as such.

## `[x]` §P0.25 — F4: burst absorption, the modulated array against the package's thermal mass. PREDICTIONS, before any run  `[x]` 10–11 Sep 2026

`docs/FUTURE_EXPERIMENTS.md` experiment 4. **Built first** (all additive, 160 tests in the
touched suites): the array is now wired for `mode='transient'` (`ICEThermalSolver` passes the
tile floorplan and per-slot tile series to `ICETransientSim`, whose renderer already joined
series; scalars broadcast; the extractor cap stays steady-only), `mr_array.tile_power_schedule`
(a block-level plan per slot projected onto the tiles slot by slot), and
`examples/burst_absorption_study.py`. The two tests that guarded the transient refusal were
rewritten *deliberately*: the array is accepted, `mr_temps` and the session cache are still
refused in transient mode, and a tile series of the wrong length is refused.

**The experiment.** 34-core, arm D, 88 CFM, 50 µm, target 92 °C, spec 100 °C. Steady operating
point `d0` ∈ {0.80, 1.00} W/mm²; for **10 ms** every block's DYNAMIC power is multiplied by
**k** ∈ {1.5, 2.0, 3.0} (an activity burst at fixed voltage; the leakage reference is untouched
and the feedback follows the temperature); 5 ms before, 10 ms after; 1 ms slots, 10 sub-steps.
Each arm is **warm-started** from its own converged steady state (`final.tstack`). Arms:
`control` (grease), `array_static` (GaAs array with the steady baseline plan held through the
burst), `array_modulated` (feed-forward: the burst's own added watts removed at their source,
block by block, during the burst slots — what a controller with a power monitor would command,
and physically what a microsecond-response optical array can deliver).

The physics the predictions rest on: the added heat at k = 2 is (k − 1) × 0.68 × 81 W ≈ **55 W**
for 10 ms (0.55 J); the die's silicon holds ~0.04 J/K and the copper base reached by conduction
in 10 ms (~1 mm) another ~0.3 J/K, so the *die-average* rise is small (a few kelvin) — but the
hot block's *local* excess over its neighbourhood (~10–20 K at steady state on the cALU) tracks
its own power on a sub-millisecond time constant, so the **peak** block overshoots by roughly
its local excess × (k − 1).

- **P1 — the control overshoots through the target and, at k = 3, through the spec.** At 0.80
  (steady ~75 °C, cALU): overshoot **+8–20 K at k = 2** (peak ~85–95 °C), **+15–40 K at k = 3**
  (past 100 °C for ≥ 5 of the 10 ms). The peak block is a cALU throughout. Falsifier: overshoot
  < 5 K at k = 3 — the package's mass absorbs the burst and the burst story is moot on this die.
- **P2 — the static array does not help with the burst.** Its overshoot matches the control's
  within ±3 K (nothing is switched; the 30 µm GaAs layer is not a thermal mass); it only carries
  its steady offset (~7 K cooler baseline). Falsifier: the static array's overshoot < half the
  control's.
- **P3 — the modulated array absorbs the burst.** Overshoot **≤ 3 K** at every k (the added heat
  is removed where it lands, through 200 µm of silicon — a lag of ~0.1–1 ms), **0 ms above the
  spec at k = 3**, at a laser draw during the burst of ~4× the burst's added watts (55 W removed
  → ~200 W electrical gross at COP 0.272; 2 J per 10 ms burst at k = 2). Falsifier: overshoot
  ≥ half the control's.
- **P4 — at 1.00, where the control has no steady state,** the array arms start from 89 °C: the
  static array crosses the 100 °C spec within the 10 ms at k = 2; the modulated array stays
  within 3 K of 89 °C at every k.
- **P5 — no transient runaway inside the 25 ms window at any k**: the die-wide runaway time
  constant is the package's (≫ 10 ms), so the burst ends before the loop gain can act. Falsifier:
  a `diverged` transient at k ≤ 3.

`scripts/burst_ladder.sh` → `results/burst/d<d0>/k<k>/`; a one-point smoke (0.80, k = 2, all
three arms) goes first because the warm-start and the transient array path have never run end
to end; the ladder follows only if it lands.

**Smoke point, landed 10 Sep (0.80 W/mm², k = 2, 105 min for three arms):** control steady
80.6 °C → peak **118.1 °C** (+37.5 K; 20 ms above the target, **11 ms above the spec**);
static array 72.8 → 108.8 °C (+36.0 K; 6 ms above spec); **modulated array 72.8 → 87.1 °C
(+14.2 K; 0 ms above target or spec)** removing **70.4 W** during the burst (the burst adds
70 W of dynamic power: 0.68 × 81 W × (k − 1) — the 55 W in the predictions used the wrong
static fraction; the driver's number is the trace's). P1's *direction* holds and its magnitude
was low by 2×: the peak block's local excess doubles on its own time constant and the leakage
feedback rides on top. P2 holds (36 vs 37.5 K). P3's ≤ 3 K is missed (14 K) while the modulated
array still keeps the die under the target: feed-forward removal through 200 µm of silicon
lags the burst by more than the sub-millisecond the prediction assumed. The full ladder
(0.80 / 1.00 × 1.5 / 2 / 3) is queued.

### `[x]` §P0.25 RESULT (all six points landed 10–11 Sep) — the modulated array cuts the burst's overshoot 2.5–3.3×; the package and the static array ride it on thermal mass and cross the spec at k = 2; at 1.00 W/mm² a k = 3 burst RUNS AWAY under the static array inside the window

`results/burst/`, `examples/burst_report.py` → `docs/evidence/burst_absorption.json` (complete).
Each point is ~100 min (three arms, each a warm-started transient with damping verification);
the last three landed at 18:56 on 10 Sep. Window 25 ms (5 pre, 10 burst, 10 post): "20 ms
above spec" means the die never came back under 100 °C inside the window.

| d0 W/mm² | k | added W | control | static array | **modulated array** (feed-forward) |
|---|---|---|---|---|---|
| 0.80 | 1.5 | 35 | 80.6 → 98.5 °C (+17.9 K), 0 ms above spec (7 ms above target) | 72.8 → 90.8 (+18.0 K), 0 ms | **72.8 → 79.9 (+7.1 K)**, 0 ms above target; 1.3 J of laser |
| 0.80 | 2.0 | 70 | 80.6 → **118.1 (+37.5 K), 11 ms above spec** | 72.8 → 108.8 (+36.0 K), 6 ms above spec | **72.8 → 87.1 (+14.2 K)**, 0 ms above target; 70 W removed, 2.6 J |
| 0.80 | 3.0 | 141 | **non-viable** (past 127 °C; +94.6 K in the model), above spec for the whole 20 ms | **non-viable** (past 127 °C; +76.1 K), 15 ms above spec | 72.8 → **101.3 (+28.5 K)**, 6 ms above spec; 141 W removed, 5.2 J |
| 1.00 | 1.5 | 44 | no steady state to burst from | 89.1 → **113.9 (+24.9 K), 14 ms above spec** | **89.1 → 96.6 (+7.5 K)**, 0 ms above spec (10 ms above target) |
| 1.00 | 2.0 | 88 | no steady state | **non-viable** (past 127 °C; +57.8 K), 20 ms above spec | 89.1 → 104.4 (+15.3 K), 10 ms above spec; 88 W, 3.2 J |
| 1.00 | 3.0 | 176 | no steady state | **transient RUNAWAY** — `diverged` inside the 25 ms window | 89.1 → 122.1 (+33.1 K), 10 ms above spec; 176 W, 6.5 J |

**The durable number is a sensitivity, not a temperature.** Overshoot per added watt of burst:
control **0.51 / 0.53 / 0.67 K/W** (k = 1.5 / 2 / 3; super-linear at k = 3 as the leakage
feedback rides on top), static array 0.51 / 0.51 / 0.54, **modulated array 0.20 / 0.20 /
0.20 K/W at 0.80 and 0.17 / 0.17 / 0.19 at 1.00** — linear in the added watts on every arm
that holds, so the modulated array's reduction is **2.5× at k = 1.5, 2.6× at k = 2, 3.3× at
k = 3**. The residual 0.2 K/W is the conduction lag through 200 µm of silicon between the
source plane and the tile plane plus the peak block's own local rise, which no feed-forward
plan at the tile plane removes.

**Final scorecard.** **P1 confirmed in direction, magnitude 2–2.4× low** — +37.5 K at k = 2
(predicted 8–20), +94.6 K at k = 3 (predicted 15–40), above the spec for all of the burst and
all of the recovery window at k = 3 (predicted ≥ 5 ms). The falsifier (< 5 K) is nowhere near.
**P2 confirmed** — the static array's overshoot equals the control's within 1.5 K at k ≤ 2
(the 30 µm GaAs layer is not a thermal mass; it carries its 8 K steady offset and nothing
else); at k = 3 it is 18 K less, which is the offset acting through the leakage feedback, and
still 80 % of the control's. **P3 absorbs, outside the 3 K band** — worst overshoot 28.5 K at
k = 3 (predicted ≤ 3 K); 0 ms above the spec at k ≤ 2, **6 ms at k = 3** (predicted 0); the
laser spends 2.6 J on a k = 2 burst (predicted ~2 J). The falsifier (≥ half the control's
overshoot) is not met at any k. **P4 half** — the static array crosses the spec at every k at
1.00 (14 / 20 / 20 ms: confirmed, and at k = 1.5 already, not k = 2); the modulated array does
NOT stay within 3 K of 89 °C (7.5 / 15.3 / 33.1 K): starting 3 K under the target it has no
margin, so it crosses the target at every k and the spec at k ≥ 2 for the 10 ms of the burst.
**P5 falsified for one arm** — the static array at 1.00 / k = 3 **runs away inside the
window** (`diverged`, 44 feedback iterations): a die that sits at 89 °C on its cool branch is
tipped onto the hot one by 176 W for 10 ms, and the transient runaway time constant is the
peak block's own, not the package's. The control cannot be tested there (no steady state),
and the modulated array runs away nowhere.

`[+]` What this says, now that the ladder is complete. The burst case is the one where the
array's *speed* — not its steady capacity — is the claim: a conventional package and an
unpowered array both ride a 10 ms burst on thermal mass and cross the 100 °C spec at k = 2
(11 and 6 ms) on a die that holds 0.80 W/mm² with 20 K of margin; the modulated array,
commanded from the power monitor (feed-forward, the burst's own added watts removed at their
source), holds the die **under its 92 °C target through a 2× burst and under the spec (by
1 K) through a 3× burst**, at a fifth of the package's overshoot per watt. Where the die has
no margin (1.00 W/mm², 3 K under target) the same array cuts the overshoot by the same factor
but the burst still crosses the target, and the spec at k ≥ 2 — the burst claim is a margin
claim, stated with the operating point. The cost is the laser draw *during* the burst
(70 W removed at k = 2 ≈ 260 W electrical for 10 ms, 2.6 J; 176 W ≈ 650 W for 6.5 J at the
worst point). ARGUED beside it: the array's optical response is microseconds; the model's
1 ms slots and 0.1 ms sub-steps resolve the thermal response, not the optical one; the
extractor's per-tile cap is steady-only, so the modulated arm's tile flux is not capped by
the film — read it against the device: the burst plan projected on the 500 µm tiles asks **5.2 W/mm² of one tile at 0.80 / k = 2, 10.5 at k = 3, 6.5 at 1.00 / k = 2 and 13.1 W/mm² at 1.00 / k = 3** (`MR_r01_c01`, 550 × 500 µm, read from the transient `MR.flp`) — the first demand in the repository above the steady ~5 W/mm² of register §4, for 10 ms, and still 60× under the target device's 813 W/mm² at 300 K. `[!]` Two rows are past 127 °C and are
reported as **non-viable**, never as a temperature; one row is a transient `diverged` and is
a runaway, not a number.

## `[x]` §P0.24 — F3: the accelerator at its real operating point, with the array. PREDICTIONS, before any run  `[~]` 10 Sep 2026

`docs/FUTURE_EXPERIMENTS.md` experiment 3. GA100 (826 mm², 367 blocks, areas measured from die
shots, power split ASSUMED — every row carries `calibrated: false`) on the **direct-die
microchannel cold plate** (`ACCEL_COOLING`: `--microchannel --dt-fluid-K 10 --inlet-C 30`,
0.0153 K/W at 700 W, `microchannel_coldplate.json`), **100 µm cells** as every accelerator row,
three arms by three invocations (`scripts/accel_mr_batch.sh`'s pattern), **target 92 °C** (the
CPU ladders' target; the 26 Aug batch used 98 °C), target device with the scalar 45 K, full
coverage, 500 µm pitch, `--recovery-at-junction`.

**The driver was extended first** (`examples/accelerator_study.py`, additive): `--leakage-curve`
(default `simulated`, as everywhere since 9 Sep; the recorded accelerator rows were on the
pipeline curve), `--mr-extractor` / `--mr-dt-max` (the per-tile cap, `mr_temps=True`),
`--array-coverage`, `--mr-energy-cap`, and — `[!]` — **the conservation cap on the plan**
(`die_power_W=realised_W`), which the recorded accelerator rows never had.

`scripts/accel_f3_ladder.sh` → `results/accel_f3/`: uniform kernel at **700 / 1000 / 1400 / 2000 /
2600 W** (0.85–3.15 W/mm²) × three arms; occupancy kernels **occ8** and **occ32** (contiguous) at
**700 and 1400 W** × three arms. 27 invocations, PAR=4 (a GA100 session peaks at 14 GB).

The measured neighbours: on the microchannel plate the GA100 held 64 °C at 700 W and 51 °C at
400 W uniform (pipeline curve, no leakage runaway); the occ8 kernel at 700 W peaked at 100.6 °C
on `SM1_DP` with a 15-block plateau and MR removing 11 W without holding 98 °C (no conservation
cap, pipeline curve, `results/accel_mr/`). On the CPU die the array's ceiling is conservation
at 2.40 W/mm² on a 0.325 K/W air package; the microchannel plate is ~20× better per unit area
(0.0153 K/W × 826 mm² against 0.325 × 101).

- **P1 — the control (grease + microchannel) runs away between 1000 and 2000 W.** Uniform:
  holds 700 (~65 °C) and 1000 W (80–90 °C); fails at 1400 or 2000 (leakage runaway on the
  simulated curve). Falsifier: holds 2000 W (then the accelerator on this plate has no thermal
  problem for the array to solve at any realistic power).
- **P2 — the unpowered GaAs layer buys one rung** (the 30 µm substitution), as on both CPU dies.
- **P3 — the laser holds ≥ 2000 W (2.4 W/mm²) and, with a sink this good, 2600 W too**, with
  `s` ≤ 0.6 at 2000 W: the plate carries most of the heat and the array clips what the plate
  cannot spread. The sustainable power is **1.5–2× the control's**. Falsifier: the laser fails
  at ≤ 2000 W, or `s` ≥ 0.9 at 2000 (the plate is not doing its share).
- **P4 — per-tile demand finally reaches the device's scale, but does not bind.** Max tile flux
  **50–300 W/mm²** at 2000–2600 W uniform and **≥ 100 W/mm²** on the occ8 kernel — against
  ≥ 813 W/mm² from the dye at 300 K tiles — so **0 tiles capped**, and the rung the accelerator
  needs is rung 5–6 of Table 8.2, not rung 4 as the CPU (§P0.20). Falsifier: max tile flux
  < 50 W/mm² everywhere (the device is still 10× under-used on an accelerator).
- **P5 — the concentrated kernel is where the laser earns its keep.** occ8 at 700 W: the control
  holds a steady state above the target (~100 °C on the SM datapath, as recorded); the laser
  holds 92 °C for **10–25 W** removed from the eight active SMs' tiles. occ8 at 1400 W: the
  control runs away; the laser holds for **≤ 120 W**. The hot spot is an SM datapath block at
  every point. Falsifier: the laser cannot hold occ8 at 1400 W.
- **P6 — the multiplier is smaller on the accelerator than on the CPU** (1.5–2× against 2.2–2.4×)
  because the control's cliff sits further up a much better sink. Falsifier: ≥ 2.4×.

## `[x]` §P0.23 — the second front opens: iso-package compute scaling (F1) and dark-silicon recovery (F2). PREDICTIONS, before any run  `[~]` 10 Sep 2026

`docs/FUTURE_EXPERIMENTS.md` experiments 1 and 2, launched together on the campaign server.
Same discipline: arm D, the 34-core arm-D point as the anchor, predictions here first.

### §P0.23.1 — F1: iso-package compute scaling in throughput terms, and the 70-core die with the array

**(a) The existing rows, restated.** `examples/iso_package_throughput_report.py` reads
`results/array_coverage_armD/c1.00` and reports, per rung and arm, converged die watts, GFLOP/s
(thermal-only, `gflops`), GFLOP/s per package watt (`gflops_per_total_W`: die + fan + net MR)
and the sustainable-watts multiplier. No solve. Prediction: **3.8×** the die watts at the same
package (2.40 vs 0.60–0.65), and GFLOP/s per package watt that *falls* from ~1.20 W/mm² up
(the laser's draw grows faster than throughput) — the honest shape of the energy claim.

**(b) The 70-core die with the array** — `scripts/iso_package_70core_ladder.sh` →
`results/iso_package_70core/`: 70-core, **100 µm cells** (§P0.22.0), arm D, 88 CFM, target
92 °C, target device with the scalar 45 K, full coverage, 500 µm pitch; densities 0.60 / 0.70
(control + idle + on), 0.80 / 1.00 / 1.20 / 1.60 / 2.00 / 2.40 (idle + on). Injected energy cap,
as the reference ladder. The measured neighbours: the 70-core control holds 0.40 shaped / 0.65
flat (§P0.22.1); the 34-core idle holds 1.10 and the laser 2.40 on a 0.325 K/W boundary; the
70-core boundary is 0.234 K/W (1.40× the rise at the same density).

- **P1 — the unpowered array's cliff scales with the boundary.** `array_idle` holds **0.70–0.80**
  and fails by 0.90 (34-core: 1.10 / 1.20, divided by ~1.4). Falsifier: holds ≥ 1.00.
- **P2 — the laser holds the big die to 2.0–2.4 W/mm²-equivalent**, i.e. **390–470 W** on the
  same air-cooled package, with `s` reaching ~1 at the top rung and 0 tiles capped. Falsifier:
  the top holding rung ≤ 1.60 (314 W), or any tile capped.
- **P3 — the array's cost scales with die watts, not core count.** `s` at 2.00 W/mm² within
  **±0.10 of the 34-core's 0.74**, and the net electrical cost per die watt within ±20 % at
  matched density. Falsifier: `s(2.00)` > 0.90 (the bigger die is dearer per watt) or < 0.60.
- **P4 — the peak block is a cALU** on every holding rung, as on the 34-core.

`[!]` **F1(a) read before the launch (`docs/evidence/iso_package_throughput.json`).** The
watts multiplier is as predicted (2.40 against 0.60–0.65: 3.7–4.0×), and GFLOP/s per package
watt falls monotonically from 32.8 at 1.00 to 11.2 at 2.40 — but for a reason the prediction
did not say out loud: at fixed core count the pipeline's thermal-only GFLOP/s is **flat**
(4.38–4.40 TFLOP/s at the 4.03 GHz the 92 °C target allows) across the whole ladder. The rescue
ladder injects more watts into the *same* 34 cores; nothing in the model turns those watts into
throughput. So "3.8× the compute on the same package" is **not** what the rows say — they say
3.8× the die **watts**. The compute multiplier exists only through more cores (F1b, the 70-core
die: 2.06× the cores at the same clock) or a higher clock (capped by the spec and the V/F
table). Quote the watts multiplier; quote a compute multiplier only from F1b.

### §P0.23.2 — F2: dark-silicon recovery

`scripts/dark_silicon_ladder.sh` → `results/dark_silicon/`: 34-core, 50 µm, arm D, 88 CFM,
target 92 °C, target device with the scalar 45 K; `--activity mixed --background 0.25
--activity-scope iso-per-core` (the saturated die is normalised to `--density`, then the quiet
cores drop to 25 %); active fractions **0.25 / 0.50 / 0.75 / 1.00**; per-core power at
**0.78 W/mm²** (the trace's native map), **1.00, 1.20, 1.50**; arms control, `array_idle`,
`array_on`. `[!]` `mixed_utilisation` activates the lowest-index cores first, and the tiler
lays cores out row by row, so the active set is a **contiguous block** — thermally the worst
case (a scheduler would spread them). Stated, and kept: it is the case a cooler must survive.
Die-average density at (d, f) = d × (f + 0.25 (1 − f)).

- **P1 — the traced die cannot be fully lit on this package without the array.** At the native
  0.78 W/mm² the control lights **50 %** (die average 0.49) and fails at 75 % (0.63 — the
  shaped cliff, with the hot cores clustered); at 1.00 it lights 25–50 %; at 1.20 and 1.50, 25 %
  at most. Falsifier: the control holds 100 % at 1.00.
- **P2 — the material substitution alone lights the native die.** `array_idle` (GaAs in place
  of grease, no light) holds **100 % at 0.78 and 1.00**, 75 % at 1.20, 50 % at 1.50 — because
  the unpowered array holds 1.10 W/mm² uniformly lit and the clustered case is somewhat worse.
  `[!]` So at the native power the *laser* is not what recovers dark silicon on this die; the
  passive layer is. Falsifier: idle fails at 100 % / 0.78.
- **P3 — the laser lights 100 % at every per-core power tested**, at a cost that tracks the
  uniform ladder: **≤ 5 W** at 0.78 and 1.00, **15–35 W** at 1.20, **50–80 W** at 1.50.
  Falsifier: `array_on` fails to light 100 % at ≤ 1.50, or costs > 100 W there.
- **P4 — clustering costs the control more than the array.** The control's highest lit fraction
  at a given die average sits **one rung below** the uniform ladder's cliff (0.60–0.65) because
  the hot cores are adjacent; the array's minimum plan at 100 % is within **±25 %** of the
  uniform ladder's plan at the same die average (the array resolves the cluster). Falsifier:
  the array's plan > 1.5× the uniform ladder's at the same die average.

### `[x]` §P0.23 RESULT — both rounds landed in 13 minutes; two predictions falsified, both about the big die

`docs/evidence/iso_package_throughput.json` (`examples/iso_package_throughput_report.py`),
`docs/evidence/dark_silicon.json` (`examples/dark_silicon_report.py`); raw
`results/iso_package_70core/`, `results/dark_silicon/`.

**F1b — the 70-core die with the array (100 µm, arm D, target device):**

| density | control | `array_idle` | `array_on` | Q | s | TFLOP/s | GF/s per package W |
|---|---|---|---|---|---|---|---|
| 0.60 | holds 81.4 °C (116 W) | holds 73.7 | holds, nothing to do | 0 | 0 | 9.2 | 61 |
| 0.70 | **holds 97.0 °C (137 W)** | holds 85.3 | holds | 0 | 0 | 9.1 | 53 |
| 0.80 | — | **holds 100.5 °C** | holds 93.2 | 0.5 (lower bound) | 0 | 9.0 | 47 |
| 1.00 | — | fails | holds 93.3 (197 W) | 16.1 | 0.08 | 9.0 | 37 |
| 1.20 | — | fails | holds 93.9 (234 W) | 78.3 | 0.34 | 9.0 | 28.5 |
| 1.60 | — | fails | **holds 93.7 (301 W)** — cool branch bracketed | **279.2** | **0.93** | 9.0 | 17.8 |
| 2.00, 2.40 | — | fails | **no steady state even at full capability** | — | — | — | — |

**Scorecard.** **P1 not falsified** (idle holds 0.80, the top of the predicted 0.70–0.80, fails
at 1.00; 0.90 not run). **P2 FALSIFIED** — the laser holds the big die to **1.60 W/mm² = 301 W**,
not 2.0–2.4 (390–470 W); 2.00 has no steady state at full capability. **P3 FALSIFIED** — at
1.60 the array already lifts **93 %** of the die's heat where the 34-core's lifted 49 %; the
bigger die is dearer per watt at the same density, not the same. **P4 confirmed** (cALU).

`[+]` What this says. (1) The **multiplier travels, the watts do not**: the laser takes the
70-core from the driver's control cliff (0.70, 137 W) to 1.60 (301 W) — **2.2×**, against the
34-core's 1.00 → 2.40, 2.4× — and s reaches ~1 one rung earlier because the fixed 1825 mm² base
sees 1.94× the watts at 0.72× the resistance (§P0.22.1's 1.40×): the array has to take over
sooner, and above 1.60 the die is bistable even with the array carrying everything. (2) The
compute statement the proposal may make: **9.0 TFLOP/s (2.06× the cores) at 4.03 GHz on the same
88 CFM package**, at 506 W of package power at the top rung against 4.4 TFLOP/s at 392 W for
the 34-core — and the efficient point is the control's 0.60–0.70 (53–61 GFLOP/s per package
watt), because the laser buys *density*, not efficiency (§P0.23.1's F1(a) note). (3) `[!]`
**Two control ceilings exist and they differ by a factor ~1.5–1.75**: the density probe's
shaped arm (leakage a fixed fraction of every block's power: 0.60–0.65 on the 34-core, 0.40–0.50
on the 70-core) and the driver's control arm (McPAT's per-unit leakage split: holds to 0.88–1.00
on the 34-core, 0.70 on the 70-core). Both are in the register; §P0.23.2's P1 was written
against the wrong one. Now a standing constraint (register §4): **say which**.

**F2 — dark-silicon recovery (34-core, 50 µm, arm D, hot cores a contiguous block):**

| per-core W/mm² | control lights | GaAs layer, no light | laser | laser cost at 100 % (net) |
|---|---|---|---|---|
| 0.78 (native) | **100 %** (79 °C) | 100 % (71 °C) | 100 % | 0 W |
| 1.00 | **50 %** (109 °C); 75 % unconverged; 100 % runaway | 100 % (89 °C) | 100 % | 0 W (the passive layer suffices) |
| 1.20 | **none** — even a contiguous quarter runs away (die average 0.53) | 25 % (107 °C); 50 % unconverged; 75 % runaway | **100 %** (93 °C) | **17.3 W (10.6 net)**; 25 %: 0.7 W, 50 %: 1.6, 75 %: 12.8 |
| 1.50 | none | none | **100 %** (92 °C) | **64.2 W (39.3 net)**; 25 %: 48.7, 50 %: 43.0, 75 %: 53.8 |

**Scorecard.** **P1 FALSIFIED** — the control lights the traced die fully at its native power
(the prediction used the probe's ceiling; the driver's control holds to ~1.0) and 50 % at 1.00.
**P2 confirmed and then some** — the unpowered GaAs layer lights 100 % at 0.78 and 1.00, but
only 25 % at 1.20 and nothing at 1.50 (predicted 75 % / 50 %): clustering hurts the passive
layer more than predicted. **P3 confirmed** — the laser lights 100 % at every per-core power,
at 0 / 0 / 17.3 / 64.2 W (predicted ≤ 5 / ≤ 5 / 15–35 / 50–80). **P4 confirmed trivially** — at
100 % the mixed map *is* the uniform map, so the ratio is 1.00 by construction; the informative
rows are the partial ones, where at 1.50 a lit **quarter costs more than a lit half** (48.7 vs
43.0 W): a contiguous block of eight cores at 1.5 W/mm² is a harder hot spot than sixteen,
and the minimum-plan bisection lands accordingly. Quote it as measured, with that reading.

`[+]` The dark-silicon statement the proposal may make: **at 1.2 W/mm² per core no contiguous
quarter of this die can be lit on this package; the unpowered GaAs layer lights a quarter; the
laser lights all 34 cores for 17 W (11 W net). At 1.5 W/mm² only the laser lights any fraction
— all of it, for 64 W (39 W net).** At the native 0.78 W/mm² the die needs no help on this
package (driver's control), so the recovery claim starts at ~1.0 W/mm² per core.

## `[~]` §P0.22 — the architecture-evolution phase opens: D4 falsification ladder, D3 cache-leakage objective, D1 dense-cluster family. PREDICTIONS, before any run  `[~]` 9 Sep 2026

**The user's decisions (9 Sep).** The one-die rule is lifted; the designs are ARGUED and measured
where the day allows; the deliverable is `docs/designs/EVOLUTION_LADDER.md`; D3's cache-leakage
planner objective is built now. Same discipline as before: one variable at a time, the 34-core
arm-D die as the fixed reference, predictions here before the launch, a falsifier per prediction.

**Decision (user, 10 Sep):** the six future experiments proposed at the end of the session are
recorded as a second front in `docs/FUTURE_EXPERIMENTS.md`, ranked; the net-export energy story
is reserved for the post-evolution, ISA-classed core designs (v100 Tier III, past the BEOL
wall). Nothing in §P0.22 licenses a net-export claim.

### §P0.22.0 — one grid decision, made before the launch, and it is not free

The 70-core die (196.0 mm², 18541 × 10582 µm, 2314 blocks) on the control stack at 50 µm cells
is **629 k unknowns** (78.6 k cells × 8 layers), against the toolchain's largest measured
factorisation of **366 k** (`leakage_feedback.LARGEST_MEASURED_UNKNOWNS`; the 34-core control
stack is 324 k). It will not solve at the recorded grid. The D4 ladder therefore runs at
**`--cell-um 100`** (157 k unknowns), and because a coarser grid understates peaks on small
blocks (`METHODS.md` §5), the 34-core reference is **re-run at 100 µm around its own cliffs** so
the two dies are compared on one grid. Nothing at 100 µm is compared with the recorded 50 µm
rows except through that matched control.

### §P0.22.1 — D4: the 70-core die as a falsification test of the 3 Sep predictions

`scripts/uniform_density_ladder_d4.sh` → `results/uniform_density_70core_armD/` (70-core, uniform
0.45–0.95, shaped 0.30–0.70) and `results/uniform_density_34core_c100_armD/` (34-core at 100 µm,
uniform 0.80–1.00, shaped 0.55–0.75). Arm D, 88 CFM, spreading, `uniform_density_probe.py`,
`PAR=8`. 30 points.

The measured neighbours: the 34-core arm-D ladder at 50 µm holds uniform **0.85** (60.5 °C,
`core_other_5`) and fails 0.90; holds shaped **0.60** (76.6 °C, `cALU_16`) and fails 0.65
(`results/uniform_density_armD/`). The 70-core die sees a boundary of **0.234 K/W** against the
34-core's 0.325 (`spreading_boundary_by_die.json`, fixed 1825 mm² base): 1.94× the watts at the
same density on 0.72× the resistance is **1.40× the temperature rise across the base**, with the
in-die conduction path unchanged per unit area.

- **P1 — the grid control.** At 100 µm the 34-core **uniform** cliff is unchanged (holds 0.85,
  fails 0.90): a Gini-0 die has no small hot block for the grid to smear. The **shaped** cliff
  moves **up by 0–1 rung** (holds 0.60 or 0.65) because the 142 × 115 µm cALU is under-resolved at
  100 µm. Falsifier: either arm moves ≥ 2 rungs, in which case the 100 µm ladders cannot be read
  against the recorded ones at all and D4 is reported on its own grid only.
- **P2 — the flat-die ceiling does NOT travel as a density.** 70-core uniform arm holds **0.65–0.75**
  W/mm² and fails by 0.80 — down from the 34-core's 0.85, by roughly the 1.40× boundary factor
  diluted by the unchanged in-die path. Falsifier: holds ≥ 0.85 (the boundary is not what sets the
  flat-die limit) or fails ≤ 0.60 (something scales worse than the base).
- **P3 — the shaped ceiling moves the same way.** 70-core shaped arm holds **0.45–0.55**, fails by
  0.60.
- **P4 — the concentration ratio TRAVELS.** uniform/shaped ceiling ratio on the 70-core inside
  **1.2–1.7** (34-core: 0.85/0.60 = 1.42). Falsifier: outside that band — the 1.4× is a property of
  this die, not of the floorplan family.
- **P5 — the hot-spot identity travels.** The 70-core shaped arm's runaway block is a **cALU** at
  every diverging rung, as on the 34-core. Falsifier: `core_other` or an edge core.
- **P6 — the absolute WATTS rise.** The 70-core's highest holding uniform die power is **130–150 W**
  (0.65–0.75 × 196), above the 34-core's 86 W (0.85 × 101): a fixed base is a better sink for a
  bigger die. This is the form in which "absolute ceilings do not travel" is expected to be true:
  they move, in the direction the package says.

### `[x]` §P0.22.1 RESULT — the flat ceiling moves the way the package says, the concentration ratio and the hot block travel

`results/uniform_density_70core_armD/`, `results/uniform_density_34core_c100_armD/`,
`examples/d4_falsification_report.py` → `docs/evidence/d4_falsification_70core.json`.

| | 34-core, 50 µm (recorded) | 34-core, 100 µm (grid control) | **70-core, 100 µm** |
|---|---|---|---|
| flat (Gini 0) | holds 0.85 (60.5 °C), fails 0.90 | holds 0.85 (60.5 °C), fails 0.90 — **unchanged** | **holds 0.65 (61.1 °C), fails 0.70** |
| shaped (real map) | holds 0.60 (76.6 °C), fails 0.65 | holds 0.60 (71.2 °C), fails 0.65 — **same rung**, peak 5 K lower | holds 0.40 (60.0 °C), **fails 0.50**; **0.45 UNCONVERGED** (375 / 421 K / runaway at three damping levels — the rung next to the cliff; neither a hold nor a failure) |
| runaway block, shaped | cALU_16 | cALU_0 | **cALU_0 at all five failing rungs** |
| highest holding flat die power | 86 W | 86 W | **127 W** |

**Scorecard.** **P1 confirmed** — the grid moves neither cliff by a rung (the shaped peak reads
5 K lower at 100 µm, as a smeared 142 µm block should, and the cliff does not move); the 100 µm
ladders can be read against the recorded ones. **P2 confirmed** — the flat ceiling lands at
**0.65**, the bottom of the predicted 0.65–0.75 band, failing by 0.70: the 34-core's 0.85 does
not travel as a density, and it moves by the 1.40× the base resistance predicted (0.85/1.40 =
0.61 ≈ 0.65 with the unchanged in-die path). **P3 not falsified, not confirmed** — the cliff is
known to one rung: 0.40 holds, 0.50 fails, and 0.45 is undecidable (register §4's rule: an
unconverged solve is neither), so the ceiling is inside the predicted 0.45–0.55 band if that
rung holds and one rung below it if it fails. **P4 confirmed under either resolution** — the
concentration ratio is 1.42 (if 0.45 holds) or 1.59 (if it fails), both inside 1.2–1.7. **P5 confirmed** — cALU at every diverging shaped rung; the hot-spot identity
travels. **P6 rises, just outside the band** — 127 W against the predicted 130–150 W: the
absolute watts rise with die area as the fixed base predicts, by slightly less than the linear
estimate.

`[+]` **What this says.** The 3 September prediction survives on a second floorplan: the
**ratios travel** (1.4× concentration; cALU the hot spot; the flat-die limit set by the
boundary) and the **absolute ceilings do not** — they move down as a density and up as watts,
by the amount a fixed 1825 mm² base spreading a bigger die predicts. That is the falsification
test the ladder needed before any gen-0 statement could be called a property of the floorplan
family rather than of one die. `[!]` 100 µm cells throughout the comparison; the 50 µm rows are
reached only through the matched-grid control, which moved nothing. `[!]` The unconverged rung
is the same lesson as §P0.14's: adjacent to a cliff the answer depends on the damping, and the
verifier refuses it rather than picking a side — quote the bracket, never the rung.

### §P0.22.2 — D3: the cache-leakage planner objective, built and smoke-tested on the monolithic die

**Build** (pure python, head node): `MRParams(zone_targets=[(pattern, T_K), …], objective=…)` with a
per-block target `target_for(block)`; `clipping_plan`, the baseline descent, the envelope descent
and both bisections test the **objective peak** `target_K + max_b (T_b − target_for(b))`, which
under the default objective is bit-identical to the plain peak; `run_mr_clipping` stamps a
per-zone report; a leakage ledger `thermal.leakage_ledger.zone_leakage_W` prices every reported
field (die leakage and cache leakage at the solved temperatures, from the same `leak_ref` and
curve the feedback loop used). `mr_comparison.py --mr-objective {peak,cache-leakage}` (default
`peak`), `--mr-cold-target-K` (default 280), zone pattern shared with `--mr-cold-zone-pattern`.
Every arm's row carries `die_leakage_W` and `cache_leakage_W`. Tests first
(`thermal/test_mr_objective.py`).

**Smoke** (`scripts/d3_objective_smoke.sh` → `results/d3_objective/`): 34-core, arm D, 88 CFM,
target 92 °C, full coverage, `--arms array_idle array_on`, target device `dye`, at **1.00 W/mm²**
(idle holds at 89.1 °C, so the reference row is a converged baseline with **0 W removed**, and the
cache-zone rows are a clean difference against it) and **0.60** (the control holds too). Variants:
cold target **280 K** and **300 K** × {`dt45` scalar kept, `dtnone` curve only, `dual` Cr:LiSAF on
the cache tiles with the curve only}, plus the `peak` objective as the regression row.

- **P1 — regression.** `--mr-objective peak` reproduces the 1.00 reference row to the digit
  (0 W, 89.1 °C, `cALU_0`) and the 0.60 control/idle rows; the default code path is bit-identical.
- **P2 — 280 K is unreachable on a monolithic die, and CONSERVATION is what says so.** The target is
  15 K *below* the 295 K ambient. With the curve alone (`dtnone`) the descent asks for more than the
  die dissipates (the plan reaches the die-power cap, `+die_power_scaled` or `conservation binds`)
  and the cache zone lands **≥ 292 K**, not holding. Reasoning from the measured neighbour: 40 W
  buys 1.24 K of lateral gradient (`POWER_RECOVERY_PLAN.md` TEST 1), so the caches cannot sit 70 K
  below the ALUs; to put 30 % of the die sub-ambient the array has to put all of it sub-ambient,
  which is refrigerating the room. Falsifier: a converged hold with cache-zone mean ≤ 285 K on a
  plan ≤ 0.9 × the converged die power.
- **P3 — with the scalar 45 K kept, the caches are LIFT-bound**, every cache block reports
  `limit = dt_max`, and the zone lands at (its idle temperature − 45 K) ≈ **300–310 K** at 1.00.
- **P4 — 300 K costs the whole die.** Holding the cache zone at 300 K (above ambient, reachable)
  needs a minimum plan of **25–60 W at 1.00 W/mm²** (25–60 % of the ~99 W die), i.e. more than the
  cache's own dissipation (~30 % of die power: 30 % of the area, leakage-heavy), because conduction
  makes the array cool the compute blocks to cool the caches. Falsifier: plan ≤ the cache zone's own
  power — targeting works on a monolithic die and the separate-die argument loses its measured leg.
- **P5 — the ledger.** Cache leakage on the 300 K row is **≥ 3× below** the idle row's (the simulated
  curve carries ~0.036/K below 345 K: 45 K is e^1.6 ≈ 5×, less the part the zone does not reach).
  Falsifier: < 2×.
- **P6 — Cr:LiSAF cannot do it, even at η_EQE = 1.** On the `dual` variant the ~80 cache tiles cap
  at ≈ 0.045 W each (0.18 W/mm² × 0.25 mm² at 290 K, falling on cooling) against a zone asking for
  ≥ 10 W: **shortfall > 90 %**, `extractor_bound`, the cache target not met. The storage-zone film
  the ladder needs is ≥ 10× thicker than Table 1.1's 10 µm at the volumetric ceiling. Falsifier:
  shortfall < 50 %.

### `[x]` §P0.22.2 RESULT — the objective is built; on the monolithic die the cache knee is conservation-bound and 300 K costs 77 % of the die

`results/d3_objective_v2/` (twelve planner iterations, corrected ledger; the six-iteration first
pass in `results/d3_objective/` agrees on every cache figure), `examples/d3_objective_report.py`
→ `docs/evidence/d3_cache_objective.json`; design record `docs/designs/gen3_cache_objective.md`.
Build: `MRParams(zone_targets, objective)`, `objective_peak`, `zone_report`,
`thermal/leakage_ledger.py`, `--mr-objective` / `--mr-cold-target-K` on `mr_comparison.py`,
16 tests in `thermal/test_mr_objective.py` (the ledger pinned to `cold_zone_prize.die_ratios`).

| 1.00 W/mm², arm D | plan | share of die | cache zone mean / max | cache leakage | stop |
|---|---|---|---|---|---|
| hot-spot objective (regression) | **0 W** | 0 | 55 / 79 °C | 4.88 W | reproduces the reference row exactly |
| caches at 300 K | **≥ 71.3 W** | 0.77 | 299.7 / 322.4 K | **1.83 W (2.7× down)** | max_iter (lower bound; +3 % from 6 to 12 iterations) |
| caches at 280 K, curve only or scalar kept | **99.4 W** | 1.00 injected / 1.08 converged | 289.5 / 316.5 K | **1.35 W (3.6× down)** | **conservation** scales the plan every iteration |
| caches at 280 K, Cr:LiSAF on the cache tiles | 73.5 W delivered | 0.79 | 300.6 / 326.1 K | 1.83 W | **56 tiles capped, 18.1 W short** |

At 0.60 W/mm² the same shape: 300 K costs 35.6 W (63 % of the die), 280 K the whole die (59.9 W
on 55 W converged), the dual plate caps 56 tiles and falls 9.7 W short.

**Scorecard: P1 confirmed exactly; P2 confirmed** (the falsifier — a hold with the zone ≤ 285 K
on ≤ 0.9× die power — is not met; the plan is 100 % of the die and the zone sits at 289.5 K);
**P3 not as predicted** — conservation scales the plan before the 45 K lift binds, so the scalar
and the curve-only variants land on the same plan (the caches' idle temperatures are 328 K mean,
352 K max, so a 45 K lift *would* have reached 283 K had the energy been there); **P4 confirmed
in direction, number too low** — 77 %, not 25–60 %, of die power to hold the caches 20 K above
the knee; **P5 below the prediction, above the falsifier** — 2.7×, not 3×; **P6 confirmed in
substance** — the storage tiles cap and the target is not met, but the "> 90 %" was framed on the
cache tiles' own request while the row reports the whole plan's shortfall (18 W of 91 W asked).

`[!]` Two lessons on the way, both about the LEDGER, both caught by the first rows and both now
tests: summing every key of the split file tripled the die total (McPAT's `Processor`,
`Total Cores`, `NUCA` restate their children — 45.7 W read on a 99 W die); a true-leaf rule then
dropped the bare `Core<N>` row, which *is* the `core_other` slab. The rule that survives is the
pipeline's own — a unit counts iff its temperature key is on the solved die — and it reproduces
`die_ratios` to four figures. The cache figure was right under all three rules.

`[+]` **What this says for the ladder.** The cache-leakage prize (2.23×, knee 280 K) cannot be
collected on the compute die at a price a cooler can pay: the array has to cool the ALUs to cool
the caches (the 1.24 K/40 W gradient, now from the planner's side), so the gen-3 rung's binding
constraint is the die boundary itself. And the storage material's failure here is a *load*
failure, not a material one: the same tiles that fall 84 % short lifting the compute die's heat
have a ~3× margin on the cold leakage of a separate storage die (1.35 W over 30 mm² against
0.18 W/mm² per 10 µm at η_EQE = 1). Design ARGUED; constraint MEASURED.

### §P0.22.3 — D1: the dense execution cluster, as a floorplan family (if the day allows)

**Build:** `examples/generate_exec_density_family.py` scales the execution-unit areas of the
14 nm area JSON (Complex ALUs, Integer ALUs, Floating Point Units → the AVX accelerator follows at
the shipped 1.981×) by a factor, subtracts the delta from `Execution Unit/Area` and `Core/Area` so
the leftover `core_other` slab is unchanged, and tiles a 34-core die per factor under
`examples/floorplans/outputs/d1_exec<f>/`. McPAT's per-unit power is unchanged, so the cluster
gets **denser and hotter** by exactly 1/f. Compared at **matched die watts** (the §9 invariant),
not matched density — the die shrinks.

- **P1 — the control ceiling in WATTS falls.** The ×0.5 family's shaped control arm holds ≤ 55 W
  against the 34-core's 61 W (0.60 × 101); the cALU at twice its density runs away first.
  Falsifier: holds ≥ 61 W.
- **P2 — the array rescues the dense cluster at the reference's watts.** `array_on` holds every rung
  the 34-core holds (121–202 W, i.e. the 1.20–2.00 rungs × 101 mm²) with 0 tiles capped; the
  minimum plan at matched watts is within **±20 %** of the reference's (the 200 µm plateau says the
  array resolves the cluster; above 1.20 the plan engages every block and is set by die-average
  heat). Falsifier: a rung lost at ≤ 162 W (the 1.60 rung), or a plan > 1.5× dearer.
- **P3 — the peak block is a cALU** on every family member at every rung.
- **P4 — what binds next is conservation**, as on the reference (the 2.40 rung), not the lift:
  0 tiles capped throughout.

### `[x]` §P0.22.3 RESULT — the array holds the dense cluster, one rung short of the reference and at a hot-spot premium; the passive ceiling falls

`results/d1_family_arr/` (array rungs, matched watts, 50 µm, arm D, target device, scalar 45 K
kept), `results/d1_family/` (control ladders), `examples/d1_family_report.py` →
`docs/evidence/d1_exec_density_family_result.json`; design record
`docs/designs/gen1_dense_cluster.md`. Reference rows: `results/array_coverage_armD/c1.00`.
Plan ratios are normalised to a 92 °C landing at 0.3247 K/W (register §4).

| die watts (reference rung) | reference: idle / laser plan | **×0.5 cluster** (2× denser) | **×0.25 cluster** (4× denser) |
|---|---|---|---|
| 111 W (1.10) | idle holds 103.7 °C / **0.8 W** | idle **diverges** / holds, **14.8 W** (2.8×) | idle diverges / holds, **34.7 W** (6.9×) |
| 121 W (1.20) | idle fails / 17.3 W | holds, 27.5 W (1.6×) | holds, 55.2 W (2.9×) |
| 162 W (1.60) | 75.3 W | holds, 93.6 W (**1.17×**) | holds, 126.5 W (1.65×) |
| 202 W (2.00) | 138.7 W | holds, 178.6 W (**1.21×**) | **no steady state at full capability** |
| 243 W (2.40) | 221.5 W (injected cap) | **not held**: 192.7 W delivered, 114.4 °C — "no plan in the bracket keeps the die on the cool branch" | no steady state |
| peak block | cALU | cALU (16 / 24 / 32) | cALU_8 |
| tiles capped | 0 | 0 at every rung | 0 at every rung |

**Scorecard.** **P1 confirmed** — the ×0.5 member's shaped control holds **50.5 W** (verified)
and fails **60.7 W**, where the reference still holds (60.7 / 65.7); the 55.6 W rung is
`unconverged` (three damping levels agree on 84.8 °C to 0.1 K but none reaches the 0.1 K
residual in budget — the rung next to the cliff, neither a hold nor a failure). The ×0.25
member holds 45.5 W and fails 55.6 W. The dense cluster runs 4–6 K hotter than the reference
at the same watts (54.8 vs 50.6 °C at 45.5 W; 62.4 vs 55.9 °C at 50.5 W) and loses one to two
rungs of passive ceiling — the concentration penalty of §P0.17, re-measured on a denser map.
**P2 falsified in its cost clause and, for ×0.25, in its hold clause**: the ×0.5 member holds
every reference rung to 2.00 with 0 tiles capped but the plan is 1.17–2.8× the reference's, not
within ±20 %; the ×0.25 member loses the 2.00 rung (the falsifier was a rung ≤ 1.60). **P3
confirmed** — cALU everywhere. **P4 confirmed as to the extractor** (0 tiles capped on 10 rungs)
and refined as to the mechanism: what takes the top rung is the **stability boundary** — the
cool branch disappears one rung below the reference (bistability, §P0.18.2), and at 4× it
disappears two rungs below — not conservation and not the lift.

`[+]` **What this says, and it is the first re-measured design change in the repository.**
(1) The rescue *travels* to a denser cluster: the laser holds a 2× denser execution cluster over
the whole range the reference's laser covers up to 2.00 W/mm²-equivalent, and a 4× denser one to
1.60. (2) **Density is not free — concentration re-enters through the cooling COST.** Where the
reference die needs no light (111 W: the unpowered array holds it), the dense clusters need
15–35 W of removal to hold the same watts, because the hotter cALU has to be clipped; the
premium falls to ~1.2× by the rungs where the plan is die-wide anyway. (3) The unpowered array's
own cliff moves *down* with density (idle diverges at 111 W on both members against 121 W on the
reference) while the laser's ceiling moves down one rung: the laser's rescue range is wider on
the dense die, its top lower. (4) The predicted "within ±20 %" rested on the 200 µm plateau
argument — the array resolves the cluster — which is true of the *hold* and false of the *cost*:
resolving a hotter spot costs proportionally more watts through that spot's sensitivity. Two
of four predictions wrong, both in the direction that makes the rung's next constraint an
electrical-budget one at the low rungs and a stability one at the top.

`[!]` D1's predictions are scored only if the family runs; D2 (the 25 mV `V_t` lever end to end)
is not predicted here because it will not be run today — it stays ARGUED on the §P0.18.3
re-pricing.

## `[x]` §P0.21.5 — 9 September corrections: the leakage default flipped, the recovery crossing named, v100 read  `[x]` 9 Sep 2026

- **`--leakage-curve` default → `simulated`** (user's decision on the §P0.18.0 recommendation).
  Four drivers, `test_leakage_curve_select.py` inverted (24 passed), `CLAUDE.md`, register §0/§3.
  No result moved: every §1 number was already on `simulated`. An un-flagged run is now arm D.
- **`recovery_at_temperature.json` contradicted its own rows** (user, 9 Sep). The summary's
  658 / 528 / 408 K are the *self-powering* temperatures (v91 condition 1.15: recovered
  electricity covers the pump); the rows compute net electrical cost per lifted watt *with the
  LPC*, which for the 90 %-laser preset only changes sign between 600 and 700 K. The driver now
  bisects the rows' own expression: **export crossing 614 K** (90 % laser); the other presets never
  export inside 350–800 K. Register §2 carries the withdrawal; the 30 Aug handoff line is struck.
- **v100 (`docs/Photonic_Cooling_Devices___v100.pdf`) supersedes v98.** Checked against the
  code: Tables 8.1, 8.2 (all eight rungs), 1.1's R640 row, §8.1.2's Cr:LiSAF numbers and Table 9.2's
  GaAs anchor are **unchanged to the printed digit**, so the target device (rung 6) and the
  storage-zone material stand as tested. What moved: (a) chapter-8 equation numbers (η_cool 8.6,
  p_max 8.8, d_min 8.9, Strickler–Berg 8.10, ladder score 8.11) — docstrings and `REFERENCES.md`
  updated; (b) **Table 1.1 gains two organic rows** — a 980 nm-pumped NIR tricarbocyanine
  (1.7×10⁵ W/mm³, 8×10³ W/mm² at 50 µm, η_cool 13 % at η_q 18 %, IQE 0.2 → 0.96 by F_P = 100
  through the new eq. 8.4) and a superradiant silica-TDBC J-aggregate (10⁶ W/mm³, 10³ W/mm²
  from 1 µm, annihilation-capped x ≈ 0.02) — both added as presets `nir-cyanine` and
  `j-aggregate` on the same volumetric route, with `iqe_under_purcell` (8.4), an `x_cap` and the
  book's η_abs → 1 for rows outside the R640 tail model; tests reproduce the rows to 15–25 %;
  (c) **§1.18 (thermally-limited architecture design points)** and **§10.9 (thermal heterogeneity
  as a design knob)** are new and are exactly the frame the evolution ladder needs — eq. (1.32)
  is the architectural budget inequality, (1.33) the hybrid cap ∝ 1/(1−s), the cubic-regime
  2^(1/3) clock per doubling, the three constraints that bound the three-zone template (BEOL
  400 K wall, extractor material wall, thermal-gradient / packaging wall). `[!]` v100 Table 10.8
  still names Yb:YLF for the storage zone; the 8 Sep decision (Cr:LiSAF) stands and is recorded
  as a deliberate departure. The R101 EQE point at 3×10⁻³ M is re-derived in v100 (60 %, replacing
  45 %); nothing in the code used the 45 %.

## `[~]` §P0.21 — zone materials decided: Cr:LiSAF storage zone, dye hot zone, and the dual-material array is a FLAG, not the default  `[~]` 8 Sep 2026

**The decision (user, 8 Sep).** The "storage zone material" concept stands, but the material is
**Cr³⁺:LiSAF**, not Yb:YLF; the "hot zone material" is the dye extractor. And the photonic cold
plate we test is **single-material by default**: a cold-zone / hot-zone tile arrangement has to
be laid out against the chip's floorplan, i.e. designed with the vendor for every architecture,
which defeats the architecture-agnostic premise of the product. The dual arrangement is kept as
a flag so its impact can be measured once the floorplan is itself a swept variable (Phase 2) or
the array is integrated at die manufacture, where the dependence is less of a product problem.

**What this closes.** The §3 register row "which extractor covers which zone — v98 versus the
3 Sep correction" is resolved by decision, not by evidence: v98 Table 10.8's Yb:YLF cold zone is
declined, its dye-is-a-hot-die-platform reading is accepted, and Cr:LiSAF takes the cold zone
on v98's own numbers (§8.1.2, Table 1.1, Table 8.4). The 3 Sep rule's "both thin films cover
the cold zone" is withdrawn as a *zone assignment* — the dye's transparency cap collapses on
cooling (§P0.20), so it is not the cold-zone cooler at any rung — but it stays true as a
*capability* statement at 250–320 K.

### §P0.21.0 — the build

- `thermal.extractor.CrLiSAFExtractor` (`make_extractor('cr-lisaf')`): the same volumetric route
  as the dye (v98 8.7 / 8.9), `x_max` from the McCumber crossing at 815 nm (3.2×10⁻³ at 290 K
  against the book's rounded 4×10⁻³), pump absorption on the measured disorder tail (σ = 0.26,
  anchored σ_a = 4×10⁻²³ cm² at 900 nm / 290 K), quantum defect 5.9 % (900 on 850 nm), N = 10²¹
  cm⁻³, τ = 67 µs. Reproduces Table 1.1's 20–80 W/mm³ at F_P 30–100 (17.6 / 59 W/mm³ at 290 K)
  and Table 8.4's breakeven (negative at η_EQE = 0.90, positive at 0.97). **Every areal figure is
  a ceiling at η_EQE = 1.** Its capability collapses on cooling like every anti-Stokes emitter
  (0.18 W/mm² at 290 K, 0.013 at 200 K, per 10 µm): it is a leakage-suppression tile, not a
  hot-spot razor.
- `thermal.extractor.DualZoneExtractor(cold, hot, cold_tiles)`: one array, two curves, dispatched
  per tile inside `extractor_tile_caps` (the planner's per-tile cap). Without a tile it reports
  the hot curve. `mr_array.tiles_over_blocks(tiles, blocks, pattern)`: a tile is cold when more
  than half the block area under it matches the pattern — **this function is the floorplan
  dependence the default avoids, made explicit.**
- `examples/mr_comparison.py --mr-zone-mode {single,dual}` (**default `single`**),
  `--mr-cold-zone-pattern` (default `^(L2|L3)`), `--mr-cold-extractor` (default `cr-lisaf`).
  Rows stamp `mr_zone_mode` and `n_cold_zone_tiles`.
- `ZONE_EXTRACTORS`: cold_cache → `('cr_lisaf',)` at 150–320 K, hot_compute →
  `('sin_encapsulated_dye',)` at 320–450 K; `PLATFORMS_V91['cr_lisaf']` added; Yb:YLF still
  banned from every zone (`test_platform_materials.py`, rewritten to the decision).

### §P0.21.1 — smoke point, predictions written before the run

Arm D, 34 cores, 88 CFM, target 92 °C, full coverage, 2.00 W/mm², target device (rung 6),
scalar 45 K kept. Reference: `results/extractor_v98/dye_dt45/d2.00` (plan 138.73 W, peak
93.875 °C, 0 tiles capped, 384 tiles).

- **P1 (regression of the default):** `--mr-zone-mode single` reproduces the reference row to
  the last digit (138.73 W, 93.875 °C, `mr_zone_mode = single`, `n_cold_zone_tiles = 0`).
- **P2 (cold-zone size):** with pattern `^(L2|L3)` on the 34-core skylake floorplan (34 L3
  slices + 34 L2s), **100–170 of 384 tiles** are majority-cache.
- **P3 (the dual arrangement loses the hold):** every engaged cold tile caps at ≈ 0.04 W (0.15
  W/mm² × 0.25 mm² at 290 K tiles), the shortfall against the 138.7 W plan is **10–40 W** (the
  cache tiles' share of the sensitivity-weighted envelope), and the re-applied first plan under
  the cap does **not** hold 92 °C: peak lands **2–8 K above** the single-mode 93.9 °C, the row
  reports `extractor_bound` with `n_tiles_capped` equal to the engaged cold-tile count.
- **P4 (why it is a flag):** the impact is entirely a floorplan statement (which tiles sit over
  which blocks); no number in the row transfers to a different architecture.

### `[x]` §P0.21 RESULT — the default reproduces exactly; the dual arrangement is nearly invisible at 2.00 W/mm² on this die

`results/zone_mode_smoke/{single,dual}_d2.00`, `docs/evidence/zone_mode_smoke.json`
(`examples/zone_mode_report.py`).

| point | cold tiles | plan | peak | tiles capped | shortfall |
|---|---|---|---|---|---|
| P0.20 reference (rung 6, pre-fix code) | — | 138.73 W | 93.875 °C | 0 | 0 |
| **`single` (default)** | 0 / 384 | **138.73 W** (Δ 2×10⁻¹³) | **93.875 °C** (Δ 0) | 0 | 0 |
| `dual` (Cr:LiSAF on `^(L2\|L3)` tiles, dye elsewhere) | **80** / 384 | 140.04 W (+1.3 W) | 93.824 °C (−0.05 K) | 23 | **0.10 W** |

**Scorecard: P1 confirmed exactly; P2 wrong (80 cold tiles, under the 100–170 predicted);
P3 wrong** — the dual arrangement holds, the shortfall is 0.1 W, not 10–40 W, and the plan
moves 1 %. P4 stands as a statement, not a measurement. The failure of P3 is instructive: the
sensitivity-weighted envelope at 2.00 W/mm² puts almost nothing over the cache tiles (23 of 80
cold tiles are asked for more than the ~0.04 W a Cr:LiSAF tile can give at 290 K, and the sum
of what they cannot give is 0.1 W), so the storage-zone tiles are not doing the rescue's work
on this die — the compute-zone dye tiles are, and the coldest engaged tile is 290.7 K in both
modes. That is consistent with §P0.15: the array as planned here never drives the caches cold
at all, so a storage-zone material has nothing to do until the planner is *asked* to cool the
caches (the cold-zone prize is a different objective from holding the hot spot).

`[!]` **A latent P0.20 bug found by P1.** The first single-mode run died on `ArrayWiring`'s
stale-plan guard: the §P0.20 first-plan re-cap *applied* the plan to learn its shortfall and
only solved it when the cap bound, so every uncapped run tripped the guard on the next
application. The P0.20 target-device rows (09:50–09:55) pre-date that block (10:01) and had
never been reproduced on the final code; the capped rows (near-term, rung 3) had. Fixed by
previewing the shortfall (`CoolingApplication.preview_shortfall`) and applying only when it
will be solved; regression test
`test_an_uncapped_first_plan_does_not_trip_the_stale_plan_guard` fails on the old code. The
single-mode row above is the reproduction of the P0.20 reference on the fixed code: identical.

`[+]` **What this says.** (1) The user's decision costs nothing on the recorded ladders: the
default is single-material and reproduces every P0.20 number. (2) The dual arrangement, as a
*hot-spot* rescue at 2.00 W/mm², is a 1 % effect on this floorplan — which is exactly the
architecture-agnostic argument from the other side: the layout-specific product buys nothing
here. (3) Its real test is not this objective. The place to measure it is a planner objective
that cools the caches for leakage (the 2.23× prize), on a separate-die cold zone (§P0.7), or in
Phase 2 where the floorplan is the variable. Do not run a dual-mode ladder against the
hot-spot objective; it will keep saying 1 %.

## `[x]` §P0.20 — the target device is v98 Table 1.1, and it closes the `T_min` question without a measurement  `[x]` 8 Sep 2026

### What v98 changed under §P0.19

`docs/Photonic_Cooling_Devices___v98.pdf` supersedes v91 as the authority. Three things bear on
the extractor model directly:

1. **The transparency cap** (eq. 5.7, §8.3.3): `x_max = [1 + exp((E_00 − E_p)/kT)]⁻¹`, the
   largest excited fraction the pump can sustain against its own stimulated emission. The v91
   first cut let every chromophore cycle at the Purcell rate and reproduced v91's eq. 8.4
   (10³–10⁴ W/mm² for a bulk film); **v98 withdraws that figure** — a 10⁻² M × 5 µm film tops
   out at 0.03–0.09 W/mm² at 300 K (Table 8.1), and 10³ is the Tier-I *design point* after the
   photonic ladder (Table 8.2), not a bulk property. The 5 Sep evidence row (819 W/mm², `T_min`
   207 K) rested on the withdrawn figure and is **superseded**.
2. **The tail model is stated** (eq. 9.5): `ε(E,T) = 4290 exp[σ(E − E_600)/kT]`, σ = 1 the
   Boltzmann limit as the design input (σ = 0.26 measured for Cr:LiSAF as the disorder end),
   Kedenburg ethanol background, `λ_00` = 588 nm, τ = 4.3 ns, `λ̄_f` 618/630/590 nm. My
   "thermal fraction of the tail" bracket is the book's σ.
3. **Both notes sent to the author are resolved**: eq. 9.6 now carries 4/27 and states the 3×
   overstatement; the breakeven is `A < A_0`; Fig. 9.9's caption names the plotted quantity as
   the escape efficiency under reabsorption recycling. And §9.3.2 now cites the three-tile
   fixed-pump GaAs finding of §P0.19.

**Rebuilt** `DyeExtractor` on eqs. 8.4–8.9 with the rungs of Table 8.2 as presets
(`DyeExtractor.from_rung`, `--mr-extractor dye` = rung 6 = **Table 1.1's R640-SMILES row, the
target device going forward**; `dye-near` = rung 2, the near-term experimental point). It
reproduces **every printed entry of Tables 8.1 and 8.2**, Table 8.3's η_q, §8.3.5's optima
(651/672/702 nm, +5.3/+8.7/+13 %, required EQE 0.95/0.92/0.885) and Table 1.1 (5.9 × 10³ W/mm²
at 50 µm); the GaAs closed form now matches v98 (9.6) and the Table 1.1 GaAs row (N ≈ 2 × 10¹⁹,
10⁵–10⁶ W/mm³). 36 tests.

### `[+]` Why this closes the `T_min` question

`x_max` is a Boltzmann population ratio between the absorption and emission cross-sections at
the pump (McCumber). It is **thermal by construction and independent of how the tail is
broadened**, so the capability's collapse on cooling does not depend on σ at all:

| target device (rung 6) | 400 K | 365 K | 330 K | 300 K | 263 K | 230 K | 200 K |
|---|---|---|---|---|---|---|---|
| `h` (W/mm²), σ = 1 and σ = 0.26 alike | **5900** | 3343 | 1676 | 813 | **263** | 68 | 11 |

`T_min`, where net cooling vanishes, is 176 K at σ = 1 and below 80 K at σ = 0.26 — but the
capability is under 0.2 % of design at either, so the bracket the device team was asked to
close no longer decides anything the die can see. What remains uncertain (the tail beyond
620 nm, which v98 itself names as the priority experiment) moves the *optimum pump wavelength*
by ~20 nm and the peak efficiency by ±30 %, not the temperature dependence.

`[!]` **The dye is a hot-die platform** (v98 §8.3.3, §8.4, Table 10.8): the design point is at
400 K and the capability falls 7× to 300 K and 22× to 263 K. On this die the array's tiles sit
at 263–330 K, so the target device runs at 5–20× below its design capability there — still
263–1700 W/mm² against a demand that never exceeded 8 W/mm² per tile at full coverage.

### PREDICTIONS, before the run

`scripts/extractor_rescue_points.sh` with `EXTRACTORS="dye dye-near dye-rung3 dye-rung4"`,
`dt45`, densities 2.00 / 2.40 / 2.60 (rung 3/4 at 2.00 only), plus the target device with
`--mr-energy-cap converged` at 2.40 / 2.60. Reference: `results/array_coverage_armD/c1.00`.

- **P1 — the target device never binds on this die.** Rung 6 reproduces §P0.18.2 at every
  rung with 0 tiles capped (h ≥ 263 W/mm² at the coldest tile against ≤ 8 W/mm² asked).
  Falsifier: any tile capped.
- **P2 — the near-term film cannot rescue this die.** Rung 2 gives 0.08–0.53 W/mm² at 263–330 K
  tiles, i.e. ≤ 0.13 W per 0.25 mm² tile, against plans of 139–251 W over 384 tiles with the
  hottest tiles asking 2–8 W/mm². Prediction: **every tile capped, shortfall > 85 %, no hold at
  2.00–2.60** (`envelope insufficient` or holds-but-not-target). Falsifier: a hold at 2.00.
- **P3 — the die needs rung 4.** At 300 K tiles rung 3 gives 0.8 W/mm² (fails the 8 W/mm² demand)
  and rung 4 gives 24 W/mm² (covers it): rung 3 does not hold 2.00, rung 4 does. Falsifier: rung 3
  holding 2.00, or rung 4 failing it.
- **P4 — the converged cap on the target device** repeats §P0.19's P3: 2.40 holds, 2.60 does not.

### `[x]` §P0.20 RESULT — the target device is invisible on this die; the near-term film cannot rescue it; rung 4 is the requirement

`results/extractor_v98/` (10 points), `docs/evidence/extractor_v98.json`, reference
`results/array_coverage_armD/c1.00`.

| extractor (scalar 45 K kept) | 2.00 | 2.40 | 2.60 | tiles capped (reported field) | `h` at coldest engaged tile |
|---|---|---|---|---|---|
| **target device** (rung 6, Table 1.1) | holds, 138.7 W (ref 138.7) | holds, 221.5 (221.5) | holds, 251.2 (251.2) | **0 / 0 / 0** | 632 / 305 / 266 W/mm² |
| near-term film (rung 2) | **runaway** — 197.9 W asked, **17.4 W deliverable**, 322 tiles capped | runaway, 237 asked / 17.4 | runaway, 257 asked / 17.4 | 322 / 329 / 334 | 0.17–0.18 |
| rung 3 (+ blue-edge emission) | runaway — 197.9 asked, **52.1 deliverable**, 317 capped | — | — | 317 | 0.54 |
| rung 4 (+ broadband Purcell 30) | **holds, 138.7 W**, identical to the reference | — | — | 0 | 19 |
| target device, converged energy cap | — | holds, 213.0 W (die 222 W) | **does not hold**: 257 W needed, 239 dissipated | 0 | 382 / 334 |

**Scorecard: P1, P2, P3, P4 all confirmed.** The first pass of this campaign reported the
near-term film *holding* 2.00 W/mm² with no tile capped; that was a wiring flaw (a solve that
diverged *because* the cap starved the tiles cleared the cap, and the next uncapped application
was reported), fixed by persisting the last converged tile field and re-applying the first
envelope plan under the cap before it can stand as a hold. Tested; the flawed rows are
overwritten.

`[+]` **What this says.** (1) With v98's target device the extractor's lift plays no role on
this die at any rung of the ladder the array is asked to hold — the array's ceiling is set by
conservation (2.40–2.60 W/mm²) and the die's bistability, exactly as §P0.19 found with the
v91-based curve, now on the book's own constitutive model with no measurement input. (2) **The
requirements flow-down is rung 4**: a 34-core rescue at 2.00 W/mm² needs ≥ 19 W/mm² per tile at
290 K tiles, which the ladder first provides at rung 4 (broadband Purcell F̄_P = 30 on top of
SMILES 10⁻¹ M, a 400 K-class film and blue-edge emission); rungs 2 and 3 deliver 9 % and 26 % of
the needed watts. That is a statement the device roadmap can use: the photonic-engineering rungs,
not the chemistry rungs, are what turn the dye into a chip cooler at room-temperature tiles.
(3) The dye's capability on *this* die is 7–22× below its 400 K design point because the tiles
run at 263–330 K; v98's own reading — the dye is a hot-die platform — is what the die sees.

`[!]` Open for the user: v98 Table 10.8's zone materials (Yb:YLF cold, dye hot) against the 3 Sep
rule; the code keeps the 3 Sep rule until adjudicated (`RESULTS_REGISTER.md` §3).

---

## `[x]` §P0.19 — `dt_max` derived from the extractor's own cooling curve  `[x]` 5 Sep 2026

### The idea, and what it replaces

`MRParams.dt_max_K` = 45 K was a scalar copied from Draft_5's Yb:YLF bench, capping how far the
planner may pull a *block*. Nothing made the extractor's cooling power depend on how cold the
extractor itself had become, which is the physics that limits the lift; the consequence showed
at the top of the coverage ladder, where the array pulled 12 W more than the die dissipated.

`HotGauge/thermal/extractor.py` derives the cooling flux `h(T_ext)` per platform from the
constitutive parameters (the volumetric route: concentration or carrier density × per-emitter
rate × photon energy, v91 eq. 8.3 made explicit and given its temperature dependence):

- **absorption of the red-tail pump** is an Urbach edge, `σ_a(E_p,T) ∝ exp(−(E_edge − E_p)/E_U(T))`
  (v91 eq. 9.4; the same rule for the dye's vibronic tail);
- **emission** follows from absorption by McCumber (eq. 5.19) on the thermalised core — applied
  to the exponential tail it diverges whenever `E_U > kT`, which is a statement that the far
  tail is not a thermalised manifold, so it is excluded from the emission side;
- **cooling per absorbed photon** is eq. 1.5 with Table 1.1's parasitic split (`η_abs =
  α_dye/(α_dye + α_b)`); the dye at saturation, the semiconductor at the optimum carrier density
  with **photon recycling** (only the escaped fraction of radiative recombination is replenished
  by the pump — without it the Table 9.2 benchmark never cools).

`h(T)` falls as the extractor cools and crosses zero at `T_min`. Wired into the planner as a
**per-tile cap applied at delivery** (`extractor_tile_caps`, `mr_array.deliver_capped`,
`CoolingApplication.tile_caps_fn`, `run_mr_clipping(tile_temps_fn=…)`): the tile is where the
extractor is, a tile asked for more than `h(T_tile) × A_tile` delivers the cap, and the blocks
that asked are scaled back in proportion so the planner reasons about the plan that was applied
(`delivered`). The solver reports the array die's tile temperatures
(`ICEThermalSolver(mr_temps=True)`, split off from the block field), snapshotted per solve so the
stamp describes the *reported* field, not the last probe. `[!]` The cap has to
be solved **self-consistently** with the tile's response: evaluating the curve at the last
solve's tile temperature oscillates whenever the tile cools by more than a degree per watt
(over-pull, freeze-out, plan zero, warm up, over-pull). `extractor_tile_caps` solves `φ = h(T_now +
s_t (φ_last − φ))` per tile with the tile's measured response `s_t`; the toy fixed point (12 W,
364 K) is a test. `dt_max_K=None` is now legal with an extractor; `--mr-energy-cap converged`
makes the conservation cap follow the converged die power. 20 + 9 tests.

`[!]` **The first campaign pass was wrong and is superseded** (`results/extractor_armD_blockcap_superseded/`).
It applied the cap per *block* in `clipping_plan`; since `h × A_block` is under a watt for the
die's smallest blocks against the recorded envelope's 45 W-per-block seed, the cap reshaped the
envelope even with the scalar kept, the descents landed on different cool-branch islands, and the
GaAs first-envelope solves froze tiles to 50 K with no retry. Two more defects came out with it,
both pre-existing: a row's die power and performance were built from the **last solve executed**
rather than the reported field (a bisection ends on a failing probe: `p_chip` 1527 W on a 263 W
die at 91 °C), fixed by matching the reported temperature trace's identity; and the stamp read
the last probe's tiles for the same reason. The `dtnone` variant is dropped from the second pass
(kept behind `DTNONE=1`); its shape lesson stands from the smoke test.

### Anchors — none of them Yb:YLF

| anchor | book | model |
|---|---|---|
| Table 8.1, η_c per pump wavelength (R101/R640, λ̄_f 605 nm) | 2.5 … 22.3 % | reproduced to 0.1 pp at all seven |
| eq. 8.4, dye flux at 10⁻² M × 5 µm, Purcell 10⁹/s, 680 nm | 10³–10⁴ W/mm² | **819 W/mm²** at 300 K |
| Table 9.2 / eq. 9.7, GaAs optimum | 5.7 × 10¹⁷ cm⁻³, 80 W/mm³ | **5.5 × 10¹⁷, 74 W/mm³** |
| eq. 9.6, the A₀ breakeven | passivated cools; 100× worse does not | A = 5×10⁴ cools, 5×10⁶ does not |
| Fig. 9.9 structure | 10⁻⁴ M plane infeasible; 10⁻² M broadly feasible; purity enlarges | reproduced (with `α_b` placeholders set there) |
| McCumber reciprocity, saturation `I_sat = ħω_p/(σ_a τ)`, exergy bound 1.13 | identities | tested |

`[!]` **Two things for the book's author, found by checking.** (1) Eq. 9.5 as printed evaluates
to **263 W/mm³** with Table 9.2's own inputs, 3.3× the table's 80 and 3.6× the numeric optimum
of the same balance: the optimum carries 4/27 where 9.5 has 4/9 (or 9.5 assumes `C′ ≈ 1.8 C`
from free-carrier absorption without saying so). (2) The first-law ledger cannot require an
escape efficiency below `ω_p/ω̄_f` (0.84 at 720/605 nm), so Fig. 9.9's 0.25–0.5 colour scale
must be a different quantity than the caption's `η_ext` — per-cycle escape under reabsorption,
most likely.

### What the curves say before any solve (`docs/evidence/extractor_cooling_curves.json`)

| extractor | `h(300 K)` | `T_min` |
|---|---|---|
| dye, tail purely thermal, "original" host loss | 819 W/mm² | **207 K** (161 K with Kedenburg-class loss) |
| dye, tail static or mixed | 819 | none above 120 K |
| GaAs Table 9.2 bulk, pump fixed at 890 nm | 0.074 W/mm² per µm | **259 K** (Varshni widens the gap; the pump sinks into the tail) |
| GaAs, pump retuned to the gap | 0.074 | none; flux **rises** on cooling (Auger suppressed) |
| GaAs photonically enhanced (η_e 0.99, Purcell 6×, 2 µm — what Table 8.2's 10³ implies) | 2150 W/mm² | 257 K fixed / none retuned |

`[!]` So `T_min` depends first on **how much of the dye's absorption tail is thermal** (one
measured tail at two temperatures pins it), second on the **host background absorption** at the
pump, and for GaAs on whether **the pump follows the extractor**. None of these is `dt_max`; all
are easier to measure. The bracket is carried in the code (`DYE_TAIL_BRACKET`,
`DYE_BACKGROUND_CM`, `retune_pump`) rather than collapsed to a number.

### PREDICTIONS, before the node run

`scripts/extractor_rescue_points.sh` → `results/extractor_armD/`: arm D flags, 34-core, 88 CFM,
target 92 °C, full coverage, `--arms array_on` (control and idle are unchanged and shared from
`results/array_coverage_armD/c1.00`). Densities **1.15, 2.00, 2.40, 2.60** × {`dye`,
`gaas-enhanced`, `gaas-retuned-enhanced`} × {**`dt45`**: scalar cap kept, extractor added as a
further cap; **`dtnone`**: extractor alone}, plus `dye`/`dt45` with `--mr-energy-cap converged`
at **2.40, 2.60, 3.00**. 27 points.

`[!]` **Why two variants — found in the smoke test at 1.30 W/mm² before the campaign.** With the
scalar cap dropped, nothing but `h(T_tile) × area` (820 × 101 mm² ≈ 83 kW) and the energy cap
bounds the envelope plan, so the descent starts from an **area-weighted** shape instead of the
recorded **sensitivity-weighted** one (`45 K / s` per block), and the bisection only scales that
shape. It landed on **41.0 W** against §P0.18.2's **31.1 W** at the same rung — 32 % dearer with
the *same* physics binding nothing. So `dt_max` was doing a second job all along: it shaped the
plan. The `dt45` variant holds that shape fixed so any difference is the extractor's physics;
the `dtnone` variant is the honest "curve only" regime and is reported with this caveat, never
compared with §P0.18.2's Q. (The planner's shape rule is a separate open item: a minimum over
*shape* as well as scale, e.g. sensitivity-weighted seeding of the envelope, is the fix.)

- **P1 — the dye's lift never binds on this die.** With `T_min` ≤ 207 K and the tiles of a
  92 °C-target rescue sitting well above ambient, no dye point up to 2.60 has a block bound by
  the extractor (`n_blocks_bound_by_extractor` = 0), the verdicts and minimum plans match
  §P0.18.2 to 1 %, and the coldest engaged tile at 2.60 is above 250 K. **`dt_max` was never the
  binding physics for the dye platform.** Falsifier: any dye point at ≤ 2.00 bound by the
  extractor.
- **P2 — the fixed-pump GaAs binds only where the array over-pulls.** `gaas-enhanced` (fixed
  890 nm, `T_min` 257 K) binds at 2.60, where §P0.18.2 found the pixel layer sub-ambient, and
  the coldest engaged tile stops at 257 ± 3 K; it does not bind at ≤ 2.00. `gaas-retuned-
  enhanced` binds nowhere. Falsifier: `gaas-enhanced` bound at 2.00.
- **P3 — the converged energy cap takes one rung off the array ceiling.** With the cap following
  the converged die power the 2.60 rescue (251 W removed from a die dissipating 239 W) is no
  longer available: **2.60 fails, 2.40 holds**, and the removed power at 2.40 is ≤ the converged
  die power. Falsifier: 2.60 still holds under the converged cap → the over-pull was not what
  held it.
- **P4 — the emergent lift at the 1.15 airflow anchor** (control and idle both diverge) is
  reported as the coldest engaged tile against the block it cools; predicted coldest tile
  ≥ 300 K for every extractor, i.e. more than 60 K of unused lift at the operating point.
- **P5 — the `dtnone` shape penalty travels.** From the 1.30 smoke test (+32 %), the `dtnone`
  minimum plans land 15–45 % above the `dt45` ones at 2.00–2.60 for every extractor, with the
  same verdicts. Falsifier: a `dtnone` plan *cheaper* than its `dt45` twin at any rung.

Predictions P1, P2 and P4 are scored on the `dt45` variant. P5 is **not run** in the second pass
(the `dtnone` variant was dropped; the +32 % smoke-test figure and the first pass's hot-branch
landing at 2.40 under `dtnone` are its record).

---

### `[x]` §P0.19 RESULT — the extractor's lift never binds on this die; a fixed-wavelength pump has a HOT-side limit

`results/extractor_armD/` (17 points, tile-level cap, converged-field caps only),
`examples/extractor_report.py` → `docs/evidence/extractor_armD.json`. Reference rows from
`results/array_coverage_armD/c1.00`.

| variant (scalar 45 K kept) | 2.00 | 2.40 | 2.60 | tiles capped | coldest engaged tile |
|---|---|---|---|---|---|
| `dye` | holds, 138.5 W (ref 138.7) | holds, 221.5 (221.5) | holds, 251.2 (251.2) | **0 / 0 / 0** | 291 / 267 / **263 K** |
| `gaas-enhanced` (fixed 890 nm, `T_min` 257 K) | holds, 138.7 | holds, 221.5 | holds, 251.2 | 0 / 0 / 0 | 291 / 267 / 263 K, flux there **1299 W/mm²** and falling |
| `gaas-retuned-enhanced` | holds, 138.5 | holds, 221.5 | holds, 251.2 | 0 / 0 / 0 | same tiles; flux **rising** to 5988 W/mm² |

**Every rung reproduces §P0.18.2 to 0.1 % at a common landing peak, with no tile capped.** The
coldest tile the array is ever driven to on this die is **263 K** (at 2.60 W/mm², the top holding
rung), 6 K above the fixed-pump GaAs `T_min` and 56 K above the dye's most pessimistic
(purely thermal tail) `T_min`. So, as measured:

- `[+]` **`dt_max` in its cold-side sense is not the binding physics on this die.** What bounds
  the array-assisted ceiling is energy conservation and the die's bistability (§P0.18.2), not
  the extractor's lift. The device-team ask changes accordingly: not "what is the lift" but the
  three inputs `T_min` depends on, and only to confirm it stays below ~260 K.
- `[!]` **The inference behind P2 was wrong.** §P0.18.2 called the pixel layer "sub-ambient" at
  2.60; the tiles bottom out at 263 K, 32 K below the 295 K ambient — sub-ambient indeed, but
  not below `T_min`. P2 (binding at 2.60) is scored **not as predicted**; the fixed pump gets
  within 6 K of its floor there, so the next rung would have bound it had 3.00 held.
- `[!]` **A fixed-wavelength GaAs pump has a HOT-side limit, and it bit.** As the Varshni gap
  narrows on heating the 890 nm pump crosses it near **380 K** and the extractor heats instead
  of cooling. On the 1.15 W/mm² point, whose baseline holds on the hot branch at 184 °C, the
  fixed-pump extractor capped **3 tiles to zero** while the retuned one capped none. v91's
  per-temperature `ω_p*` (§9.2 Level 1) is therefore *necessary* for a GaAs array over a hot
  die, not an optimisation; the dye at 680 nm has no such ceiling within 500 K. (The first
  pass, before the diverged-field exclusion, read this hot-side limit on runaway fields at every
  rung and called the envelope insufficient — an artefact, recorded above.)
- **P1 confirmed, P4 confirmed** (coldest tile ≥ 328 K at the 1.15 anchor for every extractor).

`[!]` **The 1.15 point is the scalar's, not the extractor's.** Under arm D the idle array holds
the 1.15 die on the *hot branch* (184 °C), so the planner takes the baseline path, and with the
scalar cap kept it stops after lifting exactly 45 K: "envelope insufficient: dt_max binds" at
111 °C, while the extractor above the die had 850 W/mm² available at 333 K. With the curve alone
(`dtnone`) the baseline-path descent then runs out of iterations at 1.7 W (a lower bound, 98 °C)
— the *planner* cannot build a rescue from a hot-branch baseline in six steps. Two planner items
follow, neither physics: the baseline path should hand a hot-branch baseline to the envelope
path, and the plan's shape should be a minimum over shape as well as scale (`RESULTS_REGISTER.md`
§3).

**P3 — the converged energy cap takes one rung off the array ceiling: CONFIRMED.** With the
conservation cap following the *converged* die power (`--mr-energy-cap converged`), **2.40 holds**
at 92.9 °C on **213.0 W** against a cooled die dissipating 222 W, and **2.60 does not hold the
target**: holding it needs 257 W from a die dissipating 239 W, so at the cap the die sits at
106.7 °C ("conservation binds … the array would be refrigerating the heat sink"). 3.00 stays
diverged. `[!]` **The array-assisted ceiling under conservation is therefore 2.40–2.60 W/mm²**,
one rung below §P0.18.2's 2.60–3.00; the register's §1.3 row now carries both. The first two
passes of this campaign let the uncapped first envelope plan stand as the reported hold — the
cap has to re-cap and re-solve that plan before it can count (fixed, tested).

**Scorecard:** P1 confirmed, P2 not as predicted (the tiles stop 6 K above the fixed-pump
floor), P3 confirmed, P4 confirmed, P5 not run. Two of four wrong-or-right calls rested on an
inference about the pixel layer's temperature that the array die's own output has now replaced
with a measurement — which is the point of reporting the tiles.

Suite after the final build: see `NEXT_SESSION.md`.

---

## `[x]` §P0.18 — the array charged its own footprint, the array-arm ceiling under arm D, and SPICE beyond leakage  `[x]` 3 Sep 2026

Three items, in the order the handoff listed them. Item 0 is a decision, not a run; items 1 and 2
are a build followed by a ladder, with the predictions written **before** the launch, as the
standing rule requires.

### §P0.18.0 — `--leakage-curve` default: RECOMMENDATION, not applied — `[x]` **APPLIED 9 Sep 2026 on the user's decision** (four drivers, `test_leakage_curve_select.py` inverted, `CLAUDE.md`, register §0/§3; no result moved)

**Recommend flipping the default to `simulated`**, so the shipped default becomes arm D exactly.
Not applied in this session — the handoff asked for a recommendation with reasoning and said not
to flip it silently — so an un-flagged run today is still `(pipeline, amortized,
hierarchy-consistent)`, which nobody has measured.

Why `simulated` rather than a fifth arm:

- **The only argument for keeping `pipeline` was reproducibility of the recorded catalogue, and
  that argument was already spent on 2–3 September.** Once `--rbb-policy` and
  `--core-other-policy` moved, an un-flagged run stopped reproducing the recorded catalogue
  anyway. Reproduction now goes through the explicit flag set in `RESULTS_REGISTER.md` §0, and
  `test_rbb_default.py` / `test_core_other.py` pin it. Adding `--leakage-curve pipeline` to that
  set costs nothing; keeping it as the default buys nothing.
- **`pipeline` is not a device** (§P0.12: CACTI's eleven numbers, activation energy 0.016–1.081 eV,
  69×, non-monotone). `simulated` is BSIM-CMG on the ASAP7 card, fitted to nothing, checked
  (I_off 0.232 nA/µm, SS 61.7 mV/dec, three model versions agree to 0.4 %). A default should be
  the best available physics, and the other two defaults already moved for exactly that reason.
- **Every §1 quotable number already sits on `simulated`.** The 2.23× cold-zone prize, the 280 K
  knee, the 0.85–0.90 flat-die ceiling, the 1.4× concentration ratio and the 35/35 rescues were
  all measured on it (arm D, the arm-D ladder, `mr_curve_compare`). The default should match the
  evidence base the register quotes from.
- **Arm D is the measured combination** — 159/159, zero anomalies, no `unconverged` rows on its
  ladder. Flipping makes the default a measured point; running `(p,a,hc)` as a fifth arm would
  spend ~3.5 h measuring a combination whose only justification is the order in which the flags
  happened to move, and whose curve is known not to be a device.
- **What a fifth arm would add** is the interaction term between the curve and the accounting,
  which A→B (curve under stock accounting) does not isolate. That is a real, small question; it
  is not a reason to ship the non-device curve as a default. It can be run later as a flagged
  study if anyone needs it.

What the flip touches, so it can be done in one commit: the four `--leakage-curve` defaults
(`mr_comparison.py`, `mr_clipping_study.py`, `clock_headroom.py`, `uniform_density_probe.py`),
`test_every_driver_defaults_to_the_pipeline_curve` in `test_leakage_curve_select.py` (rename and
invert, keeping the additivity test that the pipeline branch is untouched), the `[!]` standing
rule in `CLAUDE.md` ("Default `pipeline` everywhere and it must stay that way"), and §0 of
`RESULTS_REGISTER.md` (add `--leakage-curve pipeline` to the reproduce line; move the §3 row).

### §P0.18.1 — the array's own area: what it physically is, and what it can and cannot move

`[!]` **Read v91 before assuming the array steals silicon.** The tile is coupler / extractor /
back-reflector / sensor; the pump arrives by hollow-core fibre or waveguide to a structured
coupler *at the top of the tile*; the LPC is monolithic-backside on the semiconductor platform
(v91 Figs. 9.1, 9.8, 9.12; §9.5 lists the LPC integration modes as *external recovery /
monolithic backside / LPC-on-back-reflector*). All of it is stacked **above** the exposed
silicon. Tiles, waveguides and LPC cells therefore do not occupy logic area on the die; they
share the **pixel layer's footprint** with each other. What the power map has not charged for
is that the emitting extractor covers only a fraction of that footprint — the recorded catalogue
solved tiles filling it edge to edge (`mr_array.DEFAULT_FILL = 1.0`, never swept, never plumbed
to a driver).

**So the honest correction is an areal coverage on the pixel layer, and this narrows the claim
in `ARCHITECTURE_EVOLUTION.md` §4 and `START_HERE.md`.** The control arm has no array. No
control-arm ceiling — the flat-die 0.85–0.90 W/mm², the shaped 0.60–0.65, the 1.4× between
them — can move with coverage, by construction. What coverage bounds is the **array-assisted**
density and the array's cost, and the only array-assisted ceiling on record (§P0.10: 1.60 holds,
1.80/2.00 fails) was measured on the pipeline curve with stock accounting. That is the number
that was "optimistic by an unquantified amount", and it was optimistic twice over: full coverage
*and* uncorrected inputs.

**Built:** `mr_array.DEFAULT_COVERAGE`, `fill_for_coverage` (coverage is **areal**; `tile_grid`'s
`fill` is linear, so a "50 % array" written straight into it is a 25 % one),
`array_area_ledger` (footprint / extractor / reserved mm², **achieved** coverage after grid
snapping — 0.50 at 500 µm on a 50 µm grid is a 350 µm tile and 0.49), `tile_flux_report`
(per-**tile** flux against `h_max`; the planner caps per block, the device emits per tile),
`ArrayWiring(coverage=)` stamping `array_coverage`, `array_coverage_achieved`,
`array_extractor_mm2`, `array_reserved_mm2` on every row, and `--array-coverage` on the three
catalogue CPU drivers. Default 1.0, so the recorded catalogue is byte-identical un-flagged; a
test pins the default in each driver and that the flag actually reaches the wiring. 17 tests in
`thermal/test_array_area.py`.

`[!]` **A block under a gap is cooled by the nearest tile — found by the first reduced-coverage
points failing.** `project_plan_to_tiles` used to refuse a block that overlaps no tile ("the plan
would silently lose 0.108 W", on `FreeList_0`, 26 × 53 µm, at coverage 0.75); at full coverage
that branch is unreachable, so nine array-only points failed in the first pass before the rule
existed. The rule now (`gap_policy='nearest'`, default): the block's removal goes to the nearest
tile by rectangle distance, split equally between equidistant tiles; the watts are conserved and
3D-ICE decides what the block actually gets through the burial depth. That *is* the physics of a
gapped array — the extractor cannot be over the block — and it is the effect the ladder measures.
`ArrayWiring.gap_blocks` counts such blocks and `array_n_gap_blocks` is stamped on every row.
The rule applies only to blocks *inside* the array's footprint; a block outside it is still the
coordinate-frame error the strict path always refused (the full suite caught the first cut of
the rule swallowing that guard). Six more tests; the failed points were re-run.

Thermal semantics of a gap, stated so nobody has to guess: the pixel die is a 30 µm GaAs slab
with the tiles as its floorplan; a gap is the same slab with no floorplan element, i.e.
unpowered GaAs. Physically the gap holds couplers/waveguides/LPC of other materials, but 30 µm
of anything is small next to 200 µm of silicon, so the conduction difference is not modelled
and is stated here rather than pretended.

### §P0.18.2 — the coverage ladder under arm D. PREDICTIONS, before the run

`scripts/array_coverage_ladder_armD.sh` → `results/array_coverage_armD/`. Arm D flags
(`--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent`),
canonical `$ARM_ARGS` (direct die, 500 µm pitch, 200 µm burial, 50 µm cell, `--spreading`),
34-core, 88 CFM, target 92 °C, spot 10 µm dilute, `--recovery-at-junction`, `h_max` 1000 W/mm².
Densities **1.00–1.80 in 0.10 rungs, plus 2.00**. Coverage **1.00** with all three arms;
**0.75 / 0.50 / 0.25** with `--arms array_on` only (the control and idle arms carry no coverage
— an unpowered gap and an unpowered tile are the same GaAs — so they are shared from the 1.00
run rather than re-solved 30 times).

**The measured neighbours, array_on, 34-core, 88 CFM, target 92 °C, 500 µm:**

| configuration | 1.15 | 1.20 | 1.60 | 1.80 | 2.00 |
|---|---|---|---|---|---|
| `(p,s,s)` recorded, §P0.10 | 93.9 °C, Q 18.3 W | 93.96, Q 26.0 | 92.8, Q 112.5 | 78.1 (overshoot), Q 181 | DIV |
| `(p,a,s)` §P0.10 bracket | — | 87.2, Q 26.8 | 90.8, Q 89.6 | **DIV** | DIV |
| `(s,s,s)` arm B, `mr_curve_compare` | 91.3, Q 26.3 | — | — | — | — |
| `(s,a,hc)` **arm D** | control **diverges at 1.00**; `array_idle` holds 1.00 at 89.1 °C with **0 W removed** (nothing above target); **nothing measured above 1.00** | | | | |

So under arm D the array arm has never been run in the regime where the laser does the work.
That is the first gap this ladder closes, and it is the neighbour the coverage result has to be
read against.

**Prediction 1 — the array-assisted ceiling under arm D, coverage 1.00.** `array_on` **holds at
1.60** and **fails at 1.80 or 2.00**: highest holding rung in **1.50–1.70**, lowest failing rung
≤ 2.00. Reasoning from neighbours, not from a curve ratio: the two flags that separate `(p,a,s)`
from arm D pull opposite ways on this arm. The accounting fix removes the artificial `core_other`
slab hotspot, which §P0.10 named as the runaway block at *every* diverging point on this ladder
under both RBB policies (favourable, and measured at 22 conversions on the catalogue), while the
same fix raises the die-wide static fraction 1.27× (unfavourable, and what took the *uniform*
ceiling down one rung in §P0.17). The simulated curve carries less feedback gain above 345 K,
where every point on this ladder sits (favourable, 57 catalogue conversions). Net: at or slightly
above `(p,a,s)`'s 1.60. **Named falsifier:** highest holding rung **≤ 1.40** → the recorded
1.60–1.80 array ceiling does not survive corrected inputs and is withdrawn.

**Prediction 2 — coverage.** The mechanism is that 200 µm of silicon between the tiles and the
active layer smears a gap of a few hundred µm, and the measured neighbour is the coupled pitch
ladder at 1.15 on the simulated curve: 50/100/200 µm cost 19.476/19.476/19.470 W, **500 µm costs
26.3 W** (+35 %), 1000 µm 26.2 W, 2000 µm 33.1 W. So at 500 µm pitch the tile is already in the
regime where it spends watts on cool silicon; shrinking it for coverage makes it *finer in
extent* (toward the cheaper 200 µm tile) while opening gaps (toward losing the hot block). The
sign at moderate coverage is therefore **not predicted**, only its size:

- coverage **0.75** (450 µm tiles, 50 µm gaps — one cell): indistinguishable from 1.00, |ΔQ| < 5 %
  at every density that holds in both, same rung.
- coverage **0.50** (350 µm tiles, 150 µm gaps): |ΔQ| ≤ 20 %, sign not predicted, **same rung**.
- coverage **0.25** (250 µm tiles, 250 µm gaps): Q **up ≥ 10 %**, and the ceiling **may lose one
  rung**.

**Named falsifier:** coverage 0.50 losing a rung (0.10 W/mm²) against 1.00 → the burial-depth
smearing argument is wrong and the array's area is a first-order thermal term at the shipped
pitch, not a second-order one.

**Prediction 3 — the per-tile flux ledger.** Max tile flux **< 100 W/mm²** at every point and
every coverage ≥ 0.25 (a 250 µm tile is 0.0625 mm²; the largest single-tile share of a ~100 W
plan spread over tens of tiles is a few watts). So `h_max` = 1000 W/mm² never binds through
area, and the area charge, where it shows up at all, is **thermal** (spreading through the
burial depth), not an envelope cap. **Named falsifier:** any engaged tile above **250 W/mm²**,
the Draft_5 demonstrated density — at that coverage the demonstrated envelope would bind and
the ladder would have to be re-read with `--mr-h-max 250`.

`[!]` Standing caveat on reading Q across rows: all rows here share one curve, one policy and one
target, so the cross-curve normalisation trap does not apply, but the minimum-plan descent still
stops wherever it first holds target, so peaks land at 90–94 °C rather than at 92.0. Compare Q at
matched density and report the landing peak beside it.
### `[x]` §P0.18.2 RESULT — coverage costs nothing at this pitch, and the array-assisted ceiling is an envelope, not a package

`results/array_coverage_armD/`, 56 points (the ladder was **extended to 2.20–3.00 after the
first pass**, because `array_on` held at every rung to 2.00 and a ceiling that is not bracketed
is not a ceiling), `examples/array_coverage_report.py` → `docs/evidence/array_coverage_armD.json`.
No `unconverged` rows anywhere.

| arm | holds to | fails at |
|---|---|---|
| control (grease, no array) | — | **1.00** (the arm-D cliff, as before) |
| `array_idle` (GaAs, laser off) | 1.10 | 1.20 |
| `array_on`, coverage **1.00** | **2.60** | **3.00** |
| `array_on`, coverage 0.82 / 0.50 / 0.26 (achieved) | **2.60** | **3.00** |

**Minimum-plan cost at matched density, normalised to a common landing peak at 0.3247 K/W:**
coverage 0.82 within **0.9 %** of full coverage at every rung, 0.50 within **2.9 %** (the 2.9 % is
the 0.8 W plan at 1.10, where 0.02 W is 3 %; ≤ 0.9 % elsewhere), 0.26 within **1.6 %** (≤ 1.3 %
above 1.10). Raw Q differs by up to 6.9 % at 1.70 and 3.6 % at 2.40 and *both are landing-peak
artefacts* — the full-coverage descent stopped 1.9 K and 2.5 K below target there; at a common
peak they are −0.3 % and −0.1 %. Same trap as §P0.16, caught by the same rule.

#### `[+]` The array's own area is free at 500 µm pitch and 200 µm burial

At 0.26 coverage **644 of 1126 blocks sit under a gap** and 74.8 of the 101.1 mm² footprint is
reserved for couplers, waveguides, fibre access and LPC — and the die holds the same ceiling on
the same minimum plan. The 200 µm of silicon between the tiles and the transistors smears a
250 µm gap as completely as it smeared the 50–200 µm pitch ladder (§P0.16: 19.476 / 19.476 /
19.470 W). **So the pixel layer can give three quarters of its footprint to everything that is not
extractor with no thermal penalty on this die at this pitch.** That is a manufacturability
result of the same kind as the 200 µm plateau, and it is the answer to "charge the array its own
area": charged, and at this geometry the charge is zero.

What is *not* free is the per-tile flux: it scales as 1/coverage, **35 W/mm² at 0.26 and 2.60
against 7.9 W/mm² at full coverage** (41 at the diverged 3.00 point). Against `h_max` = 1000 W/mm²
that is 25× under; against Draft_5's demonstrated 250 W/mm² still 7× under. The area charge
shows up as flux, and the flux does not bind.

`[!]` Caveats that travel with it. (1) At ≥ 1.20 W/mm² the rescue plan engages **all 1126
blocks** (envelope-mode descent from a diverging baseline), so the coverage test above 1.10 is a
test of a gapped array's *uniformity*, not of its ability to hit one hot block; the targeted
regime is the single 1.10 rung (18 targets), which agrees. (2) 500 µm pitch only. A 50 µm tile at
quarter coverage is 25 µm, below the 50 µm mesh, so the fine end of the pitch ladder cannot be
run with coverage at this grid. (3) A gap is unpowered GaAs; the couplers and LPC that physically
fill it are other materials, 30 µm thick, not modelled.

#### `[!]` The array-assisted ceiling under corrected inputs is 2.60–3.00 W/mm², and it is an ENVELOPE result

The recorded `(p,s,s)` ceiling was 1.60 holds / 1.80 overshoots / 2.00 fails; `(p,a,s)` 1.60 /
**1.80 fails**. Under arm D the array holds **2.60** and fails at 3.00 — a full watt per mm²
higher. Read it carefully before quoting it:

- **Above ~2.0 W/mm² the array carries essentially all of the heat.** At 2.60 the injected die
  power is 263 W, the converged die dissipates 239 W (cooling lowered its leakage), and the array
  removes **251 W** — more than the die dissipates. The pixel layer is sub-ambient and the cold
  plate is pulling 12 W *out of the room*. Net electrical cost 154 W (effective COP 1.64 with
  recovery). The planner's energy cap is the *injected* power (263 W), so the plan passes it.
- **The failure at 3.00 is the actuator, not the package:** `envelope insufficient: no steady
  state even at full MR capability`. Full capability = `min(h_max·A, dt_max/sensitivity, die
  power)` per block; `dt_max` = 45 K is bounded per *block* (P0.3, still open) and nothing bounds
  the tile.
- So **2.60–3.00 is where the 45 K-per-block, 1000 W/mm² envelope runs out on this die**, not a
  thermal limit of the package, and it is not an operating point anyone would choose (the cooler
  draws 65 % of the die's power). **Quote the rescue *range* — idle fails at 1.20, the laser holds
  from there — and the cost ladder (17 W at 1.20 → 139 W at 2.00 removed; 11 → 84 W net), not the
  top rung.**
- `[!]` **Two things this exposes for the planner.** The energy cap should be the *converged*
  die power, not the injected one (a 12 W over-pull is invisible today), and a per-tile lift cap
  (P0.3) would bind before the per-block one at the top of this ladder. Neither changes any row
  below 2.40. Filed in `RESULTS_REGISTER.md` §3.

#### The predictions, scored

| | predicted | measured | verdict |
|---|---|---|---|
| **P1** array ceiling, coverage 1.00 | highest hold 1.50–1.70, fails ≤ 2.00; falsifier ≤ 1.40 | holds **2.60**, fails 3.00 | **wrong — too low by a full W/mm²** |
| **P2** coverage 0.75 | ‖ΔQ‖ < 5 %, same rung | ≤ 0.9 % at a common peak, same rung | confirmed |
| **P2** coverage 0.50 | ‖ΔQ‖ ≤ 20 %, same rung | ≤ 2.9 %, same rung | confirmed |
| **P2** coverage 0.25 | Q up ≥ 10 %, may lose a rung | ≤ 1.6 %, **same rung** | **wrong — no effect at all** |
| P2 named falsifier | 0.50 loses a rung → smearing wrong | 0 rungs lost | survives |
| **P3** tile flux | < 100 W/mm²; falsifier > 250 | max 41 (35 at the top hold) | confirmed |

Two of five wrong, both in the favourable direction, and **both from the same habit the register
warns about**: P1 carried the `(p,a,s)` rung loss forward as if the accounting fix and the curve
would net to a small move, when the measured neighbour that mattered — arm D's *control* cliff
moving from 1.10 to 1.00 while its `array_idle` moved *up* to 1.10 — already said the array arm
responds to these flags differently from the control. P2's 0.25 estimate assumed a 250 µm gap is
"too coarse" when the measured pitch plateau already extended to 200 µm tiles; the derived
estimate lost to the measured neighbour again.

---

### `[x]` §P0.18.3 — SPICE now gives `V_t(T)`, `SS(T)`, `I_dsat(V,T)` and a device-derived V/F shape

`HotGauge/power/spice_sim.py` (`vt_deck`, `idsat_deck`, `parse_iv`, `constant_current_vt`,
`subthreshold_swing_mV_per_dec`, `dibl_mV_per_V`, `fit_alpha_power`),
`HotGauge/power/device_vf.py` (`DeviceVFModel`, `load_device_vf`),
`examples/device_vt_vf_spice.py` → **`docs/evidence/device_vt_vf_asap7.json`**,
`clock_headroom.py --vf-source spice[:<T_K>]`. 21 tests in `power/test_spice_vt_vf.py`.
Same ngspice 47 + OSDI + OpenVAF BSIM-CMG 110 on the same ASAP7 `nmos_rvt` card; two more decks,
no new device. ~1 s of simulator time for 1134 operating points.

| quantity, 300 K unless stated | value | how |
|---|---|---|
| `V_t,lin` / `V_t,sat` | **0.301 / 0.284 V** | constant-current, 100 nA × W_eff/L_drawn per fin (3.36e-7 A) |
| DIBL | 26 mV/V | from the two thresholds |
| subthreshold swing | **61.0 mV/dec**, rising **0.203 mV/dec per K** (ideality 1.02) | fitted over two decades below the criterion |
| `dV_t/dT`, 250–400 K | **−0.39 mV/K (lin), −0.46 mV/K (sat)** | linear fit |
| `I_on` at 0.70 V | 501 µA/µm; 0.942 of its 300 K value at 400 K | diagonal `V_gs = V_ds` |
| alpha-power exponent | **1.45** (1.35 at 200 K → 1.62 at 500 K), rms 0.04 in ln I | **fitted**, above `V_t,sat` |
| `I_off(T)` vs the leakage evidence file | agree to **0.76 %** | same card, different deck and session |

`[+]` **Two things worth saying plainly.** The textbook `alpha = 1.4` that `irds_vf` assumes is
**right at room temperature** for this card (1.45), and it is not constant: it climbs 0.27 across
200–500 K. And the two SPICE evidence files reproduce each other's `I_off(T)` to under 1 %, which
is the check that both are the same device rather than two plausible curves.

`[!]` **The V/F *shape* differs from the roadmap's by up to 44 % — and it is the threshold, not the
exponent.** Normalised to `f(0.70 V)`, the simulated `I_on(V)/V` and the IRDS 2024 alpha-power
curve differ by 44 % at 0.45 V and converge toward `V_dd`. With the same `alpha` (1.45 vs 1.4) the
whole difference is `V_t`: 0.284 V on the card against the roadmap's 0.156 V. **These are
different devices** (a 2016 predictive 7 nm PDK against a 2024 roadmap "3 nm" row), and the
comparison is of shape, never of level. Anchored on the trace's 3.8 GHz at 0.70 V the device
curve puts the 10 % overdrive ceiling at **4.17 GHz** (IRDS: 4.15). `clock_search` uses ratios
and is insensitive to the anchor; `f_max` inherits it and says so.

### `[!]` §P0.18.3 — the `V_t` lever re-priced on the device: 50 mV costs **45–60 K**, not 22 K

`docs/LADDER_GEN0.md` §2 priced the lever with the roadmap's 82 mV/dec and the **pipeline**
curve's local doubling temperature (10.9 K at 370 K). Both terms are now simulated, and both
moved against the lever:

| T | ΔV_t | clock (device / IRDS) | leakage cost (device SS / IRDS SS) | doubling K, simulated curve | cooling that pays for it |
|---|---|---|---|---|---|
| 300 K | 25 mV | +7.6 % / +6.5 % | 2.57× @ 61.0 / 2.02× @ 82 | 22.1 K | **30.0 K** |
| 300 K | 50 mV | +15.1 % / +13.1 % | 6.59× / 4.07× | 22.1 K | **60.1 K** |
| 350 K | 25 mV | +7.6 % | 2.24× @ 71.2 | 19.2 K | **22.4 K** |
| 350 K | 50 mV | +15.0 % | 5.04× | 19.2 K | **44.8 K** |
| 400 K | 25 mV | +7.5 % | 2.03× @ 81.2 | 23.3 K | **23.9 K** |
| 400 K | 50 mV | +14.9 % | 4.13× | 23.3 K | **47.7 K** |
| 400 K | 75 mV | +22.2 % | 8.38× | 23.3 K | **71.6 K** |

`[!]` **So on the measured physics only the 25 mV step (22–30 K) sits inside the demonstrated
45 K lift; 50 mV sits at its edge (45–48 K at 350–400 K, 60 K at 300 K) and 75 mV is outside it
everywhere.** The recorded "50 mV ≈ 22 K, 75 mV ≈ 33 K, both inside 45 K" is **withdrawn**
(`RESULTS_REGISTER.md` §2). The reason is the same crossover fact as everything else this week:
above 345 K the simulated curve carries *less* gain than the pipeline one, so a kelvin of cooling
buys less leakage there — the doubling temperature is 19–23 K where the pipeline's was ~11 K — and
that is exactly the regime where the lever lives. The clock side of the trade is slightly
*better* on the device (+15 % per 50 mV against the roadmap's +13 %); the cost side is 1.2–1.6×
worse and the payback 2× slower.

`[!]` This is a **re-derivation on measured inputs**, not a thermal measurement. The lever has still
not been run end to end (a low-`V_t` die under the array through the coupled solve), and
`dt_max` is still the device team's number. What changed is that the two inputs it will be run
with are now the card's rather than the roadmap's and CACTI's.

---

### `[x]` §P0.17 RESULT — the density ceiling under arm D, and the two arms move in OPPOSITE directions

22 rungs, 0.05 W/mm² apart, `--leakage-curve simulated --rbb-policy amortized
--core-other-policy hierarchy-consistent`. `results/uniform_density_armD/`.

| arm | pipeline (§P0.15) | simulated (§P0.15) | **arm D** |
|---|---|---|---|
| **uniform** (the flat-die ceiling) | 1.05 → 1.10 | 0.90 → 0.95 | **0.85 → 0.90** |
| **shaped** (the real power map) | 0.60 → 0.65 | 0.55 → 0.65 | **0.60 → 0.65** |

Every rung is decided — **no `unconverged` rows in either arm**, which is unusual for a ladder this
close to a cliff and makes both brackets clean.

#### The prediction: direction RIGHT on both arms, magnitude OVERSTATED on one

- `[+]` **Uniform moved DOWN**, as predicted, and for the predicted reason: the Gini-0 arm has no
  hotspot to redistribute, so the only channel the accounting fix has is the scalar
  `leak_fraction`, which rises **1.27x** (0.3860 → 0.4883) and works strictly against stability.
- `[!]` **But only one rung.** The prediction's band was **0.70-0.85** and the measured highest hold
  is **0.85** — the band's top edge. A 1.27x rise in leakage fraction bought a **5.6 %** ceiling
  move, not the ~20 % the band's midpoint implied. **The magnitude claim is withdrawn; the
  direction stands.** Same failure mode as §P0.16's two wrong predictions, one notch smaller:
  an input ratio was carried too directly into a result ratio.
- `[+]` **Shaped moved UP, and that was the discriminating prediction.** §P0.17 predicted the
  shaped arm would move *less than the uniform arm or even up*, because it carries a real power map
  and therefore does get redistribution benefit to offset the higher fraction. Measured: shaped
  goes **0.55 → 0.60** on the highest holding rung, one rung **up**, while uniform goes one rung
  **down**. `[+]` **The two arms moving in opposite directions under the same flag is the
  mechanism confirming itself** — redistribution helps only where there is concentration to
  redistribute.

#### `[!]` What this means for the ceiling claims

`[+]` **§P0.11's headline survives and is now on corrected inputs.** Concentration is still worth
roughly **1.4x** (0.85-0.90 uniform against 0.60-0.65 shaped), against the ~1.5x recorded — the
same result, slightly smaller, and no longer resting on an accounting defect.

`[!]` **The absolute flat-die ceiling is LOWER than any previously recorded value**: 0.85-0.90
W/mm² against the pipeline curve's 1.05-1.10. Two independent corrections both push it down, and
neither is a modelling preference. **A flat die at ~1 W/mm² is no longer supportable on this
package and this leakage model.**

`[!]` This does **not** contradict §P0.16's 94 → 8 divergence collapse. That was measured on
*heterogeneous catalogue points* at product densities, where the die runs hot and the corrected
accounting removes an artificial hotspot; this is a *uniform* arm at 322-333 K with no hotspot to
remove. Same flag, opposite sign, for the reason §P0.16 named: **which part of an input is
load-bearing is a property of the experiment.**

---

## `[x]` §P0.17 — the density ceiling under arm D. PREDICTION, before the run

§P0.16's four-arm result deliberately did **not** restate the density ceiling: its points are
heterogeneous catalogue operating points, not a ladder, and §P0.11's Gini-0 arm is not among them.
This runs the ladder itself under arm D's configuration
(`--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent`).

### `[+]` First: the probe DOES consume all three flags — checked before spending the run

The `tile_pitch_sweep` lesson (§P0.16: it holds no leakage model, so `--leakage-curve` there was a
no-op) says to verify consumption first. `uniform_density_probe.py` accepts all three flags **and**
derives its die-wide `leak_fraction` from the split file, which is the quantity `core_other` moves:

| policy | `leak_fraction` |
|---|---|
| `stock` | **0.3860** — the value §P0.11 recorded |
| `hierarchy-consistent` | **0.4883** |

**1.27x higher.** So the flag reaches the experiment, and it reaches it through exactly one channel.

### `[!]` The prediction: the ceiling moves DOWN — the OPPOSITE way to the catalogue

§P0.16 measured `core_other` converting **22 catalogue points from diverging to holding**. The naive
extrapolation is that the ceiling rises. **It should fall instead, and the reason is the whole
point of running the ladder rather than inferring from the catalogue.**

`core_other`'s benefit in the catalogue came from **redistributing** power off an artificial
hotspot — the slab was carrying ~32 % of die dynamic on one leftover-area block per core. The
uniform density probe has **no such hotspot to fix**: its uniform arm is Gini 0 by construction, and
neither arm inherits the per-unit map (§P0.11: the probe uses a *flat die-wide* leakage fraction
"rather than the per-unit split"). So the redistribution channel is **closed**, and the only channel
left open is the scalar `leak_fraction` — which goes **up 1.27x**, i.e. strictly against stability.

**Predicted, on the uniform arm:** the recorded pipeline ceiling is 1.05-1.10 W/mm² and the
simulated one 0.90-0.95 (§P0.15's fine ladder). Under arm D I predict **0.70-0.85 W/mm²** — below
the simulated curve's, by roughly the 1.27x leakage increase working through the same feedback.

`[!]` **Named falsifier.** If the arm-D uniform ceiling comes back **at or above 0.90**, this
reasoning is wrong: it would mean the flat-fraction channel is not what sets the uniform arm's
cliff, and the 22 catalogue conversions would need a different explanation than redistribution.

`[+]` **Prediction for the shaped arm, which discriminates the mechanism.** The shaped arm *does*
carry a real power map, so it has hotspots — but they are the *recorded* map's, and `core_other`
sits in it. Predict the shaped arm moves **less** than the uniform arm, or even up, because it gets
some redistribution benefit to offset the higher fraction. If both arms move down by the same
proportion, redistribution contributes nothing here and the effect is purely the scalar.

`[!]` The last four §P0.16 predictions were wrong in ways that shared one cause — turning an input
ratio into a result ratio. This one is deliberately stated as a **direction plus a named falsifier**
rather than a computed magnitude, and the 0.70-0.85 band is a bracket, not an arithmetic claim.

---

### `[+]` §P0.17 — the cold-zone prize re-derived under `hierarchy-consistent`: **5.7 % -> 13.8 %**

`examples/cold_zone_prize.py --core-other-policy hierarchy-consistent`,
`docs/evidence/cold_zone_prize_core_other_consistent.json`. The recorded evidence file is untouched;
this writes beside it. The `stock` run still reproduces §P0.15's pair exactly (15.98 % / 38.24 % /
`core_other` 42.27 %), which is the check that the flag is the only thing that moved.

| ratio (steady slices, power landing on a real floorplan block) | `stock` | `hierarchy-consistent` |
|---|---|---|
| static fraction | 15.98 % | **27.13 %** |
| cache share of leakage (L3+L2) | 38.24 % | **54.14 %** |
| `core_other` share of leakage | 42.27 % | **18.26 %** |
| L3 share of leakage | 28.35 % | 40.14 % |
| **prize at 200 K** | **5.7 %** | **13.8 %** |
| ceiling (all cache leakage removed) | 6.1 % | **14.7 %** |

### `[!]` The prediction said ~10 %. It is 13.8 %, and the miss is instructive

§P0.16 predicted the prize would rise "~1.74x, ~6 % -> ~10 %" by scaling the **static fraction
alone**. The static fraction did move as predicted (1.70x). What the prediction missed is that the
**cache share moves too** — 38.24 % -> 54.14 %, a further 1.42x — and the two multiply:
1.70 x 1.42 = **2.4x**, not 1.74x.

`[+]` The mechanism is the same correction seen from the other side. Undoing the `2 *` takes
leakage **off** the `core_other` slab (42.3 % -> 18.3 %) and puts it back on the real blocks it
belongs to — **including the caches**. So one correction raises *both* terms of the conversion: the
numerator's share and the die's static fraction. Scaling one term and holding the other fixed is
the same class of error as §P0.16's two failed predictions — treating a multi-term conversion as if
one factor carried it.

### `[+]` §P0.15's "leaf view is an upper bound" SURVIVES — but only read within a policy

13.8 % exceeds §P0.15's 9.1 % leaf-view "upper bound", which looks like a contradiction and is not.
The leaf view moves under the policy as well, because its static fraction carries the same doubled
dynamic:

| | leaf-view prize | die-view prize |
|---|---|---|
| `stock` | 9.1 % | 5.7 % |
| `hierarchy-consistent` | **15.7 %** | **13.8 %** |

The ordering holds under both. `[!]` **The two views are only comparable within one policy** — the
9.1 % bound belongs to `stock` and must not be held against a `hierarchy-consistent` number. (The
leaf *cache share* is identical at 66.77 % under both, as it must be: the leaf view has no
`core_other`, and leakage never took the factor, so only the static fraction moves.)

`[+]` **The 2.23x improvement is untouched, for the fourth time.** Every conversion multiplies the
same `1 - 1/reduction` by a constant, so the ratio cancels it. `[+]` And the **280 K knee is
untouched** — it is a property of the leakage curve, not of the power accounting, so the design
target is still barely sub-ambient.

`[!]` **What to quote now.** The prize is **~14 % of die power** under the corrected accounting and
**~6 %** under the recorded one, and which is right depends on a decision that is now made below
(§P0.17 defaults). Neither is the book's 31.7 %. The **2.23x improvement** remains the number that
survives every one of these revisions and is still the one to lead with.

---

### `[x]` §P0.17 — the two defaults are changed, and the third is now the open question

Both flags the §P0.16 re-run was run to decide have been flipped, each in **one** place
(`thermal/rbb.DEFAULT_RBB_POLICY`, `power/core_other.DEFAULT_CORE_OTHER_POLICY`) with the five
drivers pointing at those constants.

| flag | was | **now** | why |
|---|---|---|---|
| `--rbb-policy` | `stock` | **`amortized`** | §P0.10 settled the semantics from `McPAT/core.cc`; §P0.16's B→C isolates it across 145 points and flips **no verdict either way** |
| `--core-other-policy` | `stock` | **`hierarchy-consistent`** | the stock accounting is **provably wrong**, not merely disfavoured — validated leaf-by-leaf against raw McPAT, 864 leaves, 3 nodes, **exactly zero error** |

`[!]` **These are different kinds of decision and the docs should keep them apart.** The RBB flip is
a *semantics* call backed by a null result: the evidence says it is safe, not that it is necessary.
The `core_other` flip is a *defect* fix: the stock die reports 18.43 % static against McPAT's own
Processor-level **29.36 %**, roughly half, which is exactly what a `2 *` on the dynamic column alone
predicts. If either were ever revisited, they would be revisited for different reasons.

`[+]` **The recorded catalogue stays exactly reproducible**, and that is asserted rather than
assumed: `--rbb-policy stock --core-other-policy stock` reproduces it, `apply_core_other_policy(...,
'stock')` is a verified identity, and `add_rbb_argument(ap, default='stock')` still lets a driver
pin the shipped placement un-flagged. Arm A's flag set **is** the recorded configuration.
Tests: `power/test_core_other.py`, `thermal/test_rbb_default.py`.

#### `[!]` The consequence, which is the next decision and is NOT made here

The default is now **`pipeline` + `amortized` + `hierarchy-consistent`** — and that combination is
**not one of the four arms that were measured**. The arms were
A `(p,s,s)`, B `(s,s,s)`, C `(s,a,s)`, D `(s,a,hc)`. Nobody has run `(p,a,hc)`.

That is a real gap: the shipped default should be a configuration somebody has measured end to end.
Two ways to close it, and the choice is the user's:

1. `[+]` **Also default `--leakage-curve` to `simulated`** — the default becomes **arm D exactly**,
   which is measured at 159/159 points with zero anomalies. This is the recommendation. The
   pipeline curve is CACTI's eleven hard-coded numbers (§P0.12: bit-for-bit
   `I_off_n[0][*]`, implied activation energy spanning 69x and non-monotone); the simulated curve is
   ngspice + BSIM-CMG on the ASAP7 card, fitted to nothing (§P0.13). `[!]` But this is the flag with
   the **largest** effect — 57 of 145 control points — and CLAUDE.md carries an emphatic standing
   rule to keep it at `pipeline`, so it should be flipped deliberately and not as a side effect of
   this change.
2. Run the `(p,a,hc)` combination as a fifth arm so the shipped default is measured. ~3.5 h.

`[!]` Until one of those happens, **an un-flagged run is a configuration with no catalogue behind
it.** That is stated here rather than left implicit, because the whole point of the four-arm design
was that every quoted configuration should have been measured.

---

### `[x]` §P0.17 — both §P0.16 defects fixed, each with tests and a re-run

#### 1. `__agg__L3` was placeable and is not a block — **fixed at the source**

`thermal/microrefrigeration.py` now filters bookkeeping keys out of the cooling plan:

```python
SYNTHETIC_TEMP_PREFIX = '__agg__'
def is_synthetic_temp_key(name): ...      # matched on the PREFIX
```

`[+]` **Matched on the prefix rather than importing `BRIDGEABLE_AGGREGATES`**, for two reasons: the
planner then carries no dependency on the feedback layer, and **a future bridged aggregate is
excluded automatically** instead of having to be remembered. A test asserts every current member of
`BRIDGEABLE_AGGREGATES` is caught by the prefix, so the two cannot drift apart.

`[!]` The filter is on the **key**, not on the MR target, because §P0.16 established the trigger is
arm-dependent — the same point raised in arm B and completed in arm D, since the synthetic key's
*temperature* moves with the leakage curve and the `core_other` policy. The earlier fixed
`--mr-target-C <= 45` rule stays withdrawn.

`[!]` **It took TWO sites, and a one-site fix looked like it worked.** `clipping_plan` is not the
only place block temperatures become plannable candidates: `run_mr_clipping`'s
sensitivity-calibration **probe** builds its own plan from `base_hot` and hands it straight to
`apply_plan` -> `project_plan_to_tiles`, never passing through the planner. Filtering only
`clipping_plan` left the probe raising the identical `KeyError` from a different stack, and the
"fixed" re-run failed **10 of 11 points**. An intermediate check that reported "zero errors" had
simply been taken before the runs reached the probe.

`[+]` Both sites are filtered, and the second lesson is pinned rather than remembered: a test
asserts there are **exactly two** temperature-to-candidate sites in the module, so a third cannot
appear silently.

7 tests (`thermal/test_synthetic_temp_keys.py`), including the array-valued case (Tflp temperatures
arrive as per-timestep arrays, so the filter must run *before* the array is read) and a sweep over
MR targets from 30 to 90 C.

`[+]` **VERIFIED on the 11 affected points** (`results/agg_l3_fix/`): **0 failures, 0 `__agg__L3`
errors, 11/11 with output**, where all 11 raised within ~110 s before. The recovered physics is
coherent rather than merely non-crashing — both device sweeps are monotone in the expected
direction (`--mr-dt-max` 5 -> 40 gives peaks 71.1 -> 46.3 C; `--mr-h-max` 5 -> 50 gives 53.9 ->
46.5 C) and the three `A_ceiling_T{30,40,50}` points hold at 37.8 / 46.3 / 54.6 C, tracking their
targets. `[!]` These 11 were **unrunnable in the recorded catalogue** — the recorded rows for them
predate `bridge_aggregates` and come from a different code path — so this restores points nobody
could reproduce.

#### 2. `stacked_memory_study` — the failure is SIZE, and the defect is that it was SILENT

Not a code bug in the driver. Measured discriminator across arm D's eleven stacked-memory points:

| configuration | unknowns | outcome |
|---|---|---|
| 50 µm cells + 4-8 memory dies | **1,098,144** | **failed 4 / 4** |
| 100 µm cells + 4-8 memory dies | 274,536 | succeeded 4 / 4 |
| 50 µm cells + default die count | small | succeeded 3 / 3 |

Largest system **measured** to factorise on this toolchain: **366,048** unknowns
(`session_memory.json`, the 34-core two-die session). The failing stack is 12400 × 8200 µm at 50 µm
over 27 layers — **3.0x that**. So the driver is total unknowns, fed by *both* the cell size and the
die count, and `--cell-um 100` (which quarters the system) already works and is already in the
catalogue.

`[!]` **The real defect is the silence.** 3D-ICE exits during *"Preparing thermal data"* with an
**empty stderr** when SuperLU 4.3 cannot factorise the system, so the only symptoms are an
`ExecutableJobError` and a long wall time — **~75 minutes per point, four times over**, before
anyone looked. `thermal/leakage_feedback.py` now attaches a diagnosis to that exception naming the
measured size, the largest size known to work, the `--cell-um` that fixes it, and the cost of taking
it (a coarser grid smooths lateral gradients, so a 100 µm run must not be compared against a 50 µm
one).

`[+]` **It diagnoses; it does not gate.** An ordinary failure on a normal-sized stack is passed
through untouched, and an unreadable `.stk` never masks the original error — both asserted. Nothing
that currently runs is refused. 5 tests (`thermal/test_stack_size_diagnosis.py`).

`[!]` **Not fixed: why SuperLU gives up at ~1.1 M.** That is a toolchain limit, not something this
session established a remedy for beyond coarsening. The four 50 µm points remain unrun; their
100 µm counterparts are in the catalogue and are the ones to quote.

---

## `[x]` §P0.16 — the MR catalogue on the measured curves  `[x]` 1 Sep 2026

### The PREDICTION, recorded before the run (and largely WRONG — kept in place)

*Written 1 Sep 2026 **before any solve was launched**. §P0.12, §P0.14 (twice) and §P0.15 each made
a prediction here and all four were wrong; writing them down first is the only reason the
corrections were findable. This one is recorded the same way and will be marked right or wrong in
place, not reworked.*

`mr_comparison.py` and `mr_clipping_study.py` gained `--leakage-curve` in §P0.15 but have only ever
been **run** on `pipeline`. The 22 rescues, the clipping study, the granularity result and the
budget cliff are all still on CACTI's eleven hard-coded numbers.

### The quantity that decides it, and where each study sits on it

§P0.15's transferable result: which part of a leakage curve is load-bearing is a property of the
**experiment**, not of the curve, and the deciding quantity is `d(ln P_leak)/dT` **at the
temperature the die actually sits at**. The pipeline and simulated curves **cross over near 345 K**
— simulated is far steeper below it, far gentler above. Measured here on `dP_leak/dT` (level x
log-slope, which is the term that enters the loop gain), pipeline vs simulated:

| T | 320 K | 330 K | 345 K | 367 K | 380 K | 390 K | 400 K | 420 K | 460 K |
|---|---|---|---|---|---|---|---|---|---|
| sim/pipe `dP_leak/dT` | **5.2x more** | 4.1x more | ~1.0 | **0.42** | 0.38 | 0.19 | 0.15 | 0.077 | 0.026 |

The MR families do **not** all sit on one side of this:

| study / arm | sits at | sim vs pipeline |
|---|---|---|
| density ladder (uniform arm) | ~322 K | 7.4x more gain → **ceiling moved DOWN 14 %** (measured, §P0.15) |
| density ladder (**shaped** arm) | ~346 K | ~1.0 → **failing rung identical at 0.65** (measured, §P0.15) |
| MR airflow ladder, **array** arm | 367 K (93.9 °C) | 0.42 — 2.4x **less** |
| MR airflow ladder, **control** arm | **runs away — adjudicated at 400+ K** | 0.15 or less — 7x+ less |
| MR clipping study, baseline | 344.9 K | ~1.0 — on the crossover |
| MR clipping study, **MR** arm | **326.1 K** | ~5x **more** |

`[!]` **The control arm is the piece the 367 K framing misses, and it is the piece that decides
the headline.** A rescue is recorded as *"control has no steady state, array holds target"*. The
control arm has no operating temperature — it diverges — so its verdict is not read off 367 K at
all. It is read off wherever the runaway is adjudicated, and that is **hot**. This is exactly
§P0.15's search-vs-ladder distinction applied one level down: the MR rescue test is a **divergence
test on the array arm and a limit search on the control arm**, in the same run. The tail is
invisible to the first and load-bearing to the second.

### `[+]` The control arm's loop gain is recoverable from the recorded logs, with no re-solve

The runaway message prints the residual on either side of one rejected step at a known damping, and
`anchor_residual` is re-anchored every iteration in that branch (`power/leakage.py` ~633), so the
printed pair is **one iteration apart**. With `T_{n+1} = (1-r)T_n + r f(T_n)` the residual
multiplier is `(1-r) + rG`, so `G = 1 + (ratio - 1)/r` at `r = min_relax = 0.025`:

| CFM | residual, one step | **loop gain G** | cut in `dP_leak/dT` needed to hold |
|---|---|---|---|
| 120 | 46.686 → 49.717 K | **3.60** | 3.60x |
| 88 | 55.072 → 58.894 K | **3.78** | 3.78x |
| 60 | 78.831 → 85.025 K | **4.14** | 4.14x |
| 45 | 146.700 → 186.478 K | **11.85** | 11.85x |
| 30 | 144.149 → 182.738 K | **11.71** | 11.71x |
| 20 | 27.939 → 30.040 K | **4.01** | 4.01x |

Reading the required cut off the table above: **3.6-4.1x is available above ~385 K (112 °C), and
11.9x above ~418 K (145 °C)**. Every one of these trajectories is already 28-186 K of residual
above a die whose array arm holds at 94 °C, so all six are being adjudicated well above 385 K and
the two worst (45/30 CFM, residuals 147-186 K) well above 418 K.

### The prediction

1. `[!]` **The rescues are LOST AS RECORDED — I predict 6 of 6 airflow-ladder control arms acquire
   a steady state on `simulated`, and the same for `simulated-gidl-off`.** Not because
   microrefrigeration got worse: because the pipeline curve's 47x-too-steep hot tail is what was
   killing the control, and it is an artefact. **Predicted count of surviving rescues in the
   airflow family: 0 of 6.** If exactly one survives it will be **20 CFM** (smallest residual, so
   the coolest adjudication, so the smallest available cut); the **most** certain to convert are
   45 and 30 CFM, despite needing 12x, because their trajectories are the hottest.
2. `[+]` **But the physics claim survives, and the recorded criterion is what fails.** I predict
   the converted controls hold at **> 112 °C, most likely 120-160 °C** — past the 100 °C spec, and
   above 127 °C in the range `CLAUDE.md` says to report as non-viable rather than as a number. So
   the die is still unusable and MR still takes it to 93.9 °C. **Prediction: the rescue claim is
   true under a spec-relative criterion ("control cannot hold ≤ 100 °C") and false under the
   divergence-relative one it is currently written in.** The recommendation that follows, if this
   lands: **restate the 22 rescues spec-relative**, which is invariant to the curve swap, rather
   than divergence-relative, which is not.
   `[!]` **Falsifier, named:** if a control converts and holds **below 100 °C**, prediction 2 is
   wrong and the rescue is genuinely gone — that would be a real weakening of the headline and must
   be reported as one, not absorbed.
3. `[+]` **The array arm gets EASIER and CHEAPER, at all six airflows.** At 367 K simulated is
   0.74x the level and 0.57x the slope. Predict: `peak_C` pinned at target (93-94 °C) by
   construction, `chip_W` down **5-12 %**, and `Q_rem_W` / `array_W` down by a similar fraction —
   e.g. 120 CFM `array_W` 5.84 → **~5.0-5.5 W**, 20 CFM 41.3 → **~36-39 W**. `gpw` up a few
   percent. No array arm diverges.
4. `[!]` **The clipping study moves the OPPOSITE way — it gets HARDER to beat and MR gets MORE
   effective.** Its baseline sits at **344.9 K**, on the crossover (predict: baseline peak moves
   < 2 K), and its MR arm at **326.1 K**, where simulated carries **~5x more** `dP_leak/dT`. A
   steeper curve at the cooled temperature means each watt removed sheds *more* leakage on top, so
   predict the **same budget removes more effective heat**: MR-arm peak drops further below
   baseline than the recorded 71.8 → 53.0 °C, and the **budget cliff moves to a LOWER budget**.
   Predict at least one recorded `MR LOSES on GFLOP/s/W` verdict **flips to a win**.
   `[!]` This is the sharp one: **two MR studies on the same die, same package, same flag, moving
   in opposite directions** — a direct instance of §P0.15's transferable result, and the reason the
   catalogue cannot be re-run "in one direction".
5. `[+]` **Granularity (2.77x on a hotspot) and the budget cliff survive within ~20 %** — 2.2-3.3x.
   Both are geometry rather than actuator and both already survived a 4x envelope refresh; a 1.35x
   level change is a smaller perturbation than that. They are ratios between two arms at the same
   temperature, so the curve swap largely cancels.

`[!]` **What would make all of this wrong in one step:** if the control arms' runaways are actually
adjudicated *below* ~385 K rather than above it, the available cut is only 2.4-2.6x against a
required 3.6-11.9x, and **every rescue survives untouched**. That is the single hinge, it is one
number per run (the peak temperature along the control trajectory), and the re-runs report it.

---

### `[!]` §P0.16 RESULT — the airflow rescues all survive, and the prediction above was WRONG

`scripts/mr_curve_compare_joblist.sh`, `examples/mr_curve_compare.py`, evidence
`docs/evidence/mr_catalogue_curve_compare.json`. Twelve new points (6 airflows x 2 measured
curves), three arms each, every argument character-identical to the recorded
`scripts/build_joblist.sh` B family except `--leakage-curve` and `--out-dir`. The recorded tree
under `results/overnight_forward/` was never written to and supplies the pipeline control.

| curve | 120 | 88 | 60 | 45 | 30 | 20 | rescues |
|---|---|---|---|---|---|---|---|
| pipeline (recorded) | YES | YES | YES | YES | YES | YES | **6/6** |
| **simulated** | YES | YES | YES | YES | YES | YES | **6/6** |
| **simulated-gidl-off** | YES | YES | YES | YES | YES | YES | **6/6** |

`[+]` **18 of 18. The control arm has no steady state at any airflow on any curve, and the array
holds target at all of them — including at a fifth of baseline airflow.** `array_idle` diverges
everywhere too, so "the LASER rescues it, the unpowered array does not" is intact. The headline
claim *"across 20 → 120 CFM the unassisted die diverges at every airflow while the array holds at
all"* survives the swap **unchanged**, and it is no longer resting on CACTI's eleven numbers.

`[!]` **§P0.16's prediction 1 — "0 of 6 rescues survive" — is WRONG, and prediction 3 is wrong in
direction too.** Both are withdrawn. The prediction did name its own hinge (*"if the control arms'
runaways are adjudicated below ~385 K, every rescue survives untouched"*), and that is the branch
that fired — but the reasoning that made 385 K the threshold is itself the error, and it is worth
more than the result.

#### `[!]` Why it failed: the loop gain at a runaway is set by the STOPPING RULE, not the curve

The prediction measured `G` from the recorded logs, found 3.6-11.9, and asked what a 2.4x cut in
`dP_leak/dT` would do to it. Measured on the new runs, `G` **barely moved** — but the residual at
which the runaway was called grew a lot:

| | 120 | 88 | 60 | 45 | 30 | 20 |
|---|---|---|---|---|---|---|
| `G` pipeline | 3.60 | 3.78 | 4.14 | 11.85 | 11.71 | 4.01 |
| **`G` simulated** | **3.22** | **3.38** | **3.61** | **3.15** | **3.48** | **4.87** |
| residual at the call, pipeline (K) | 47 | 55 | 79 | 147 | 144 | 28 |
| **residual at the call, simulated (K)** | **65** | **78** | **95** | **89** | **116** | **171** |

`[+]` **The generalisation: `G` at the give-up point is not a property of the configuration — it is
whatever the divergence test's stopping rule selects.** `d(ln P_leak)/dT` rises with temperature on
both curves, and a die with no fixed point simply climbs until the test fires. A gentler curve does
not stop the runaway; it moves the runaway **further out in temperature**, arriving at a similar
gain. So a measured `G` can be compared across *operating points* and must **not** be treated as an
invariant to divide a curve ratio into. The prediction did exactly that.

`[!]` **The evidence that was already on the shelf and would have got it right was §P0.15's fine
ladder.** It measured this arm directly: the **shaped** arm's failing rung is *identical at
0.65 W/mm² on the pipeline and simulated curves*. The airflow ladder's control runs at
**1.15 W/mm²** — 1.77x past that cliff on **both** curves — so it cannot hold on either, and the
rescue cannot be lost. The prediction had that argument, wrote it down as its second handle, and
then let the loop-gain algebra override it. **The measured ladder was the better predictor than an
analytic estimate built on top of it.**

`[+]` **And the crossover framing is vindicated, just not where the prediction applied it.** The
shaped arm sits at ~346 K, right at the 345 K crossover, which is exactly why its cliff does not
move — while the uniform arm at ~322 K moved 14 %. The MR studies inherit the shaped arm's
insensitivity. The prediction was right that the MR families sit on the far side of the crossover
and wrong about what that buys.

#### `[!]` What the array arm costs — and the difference is a LANDING POINT, not physics

Prediction 3 said the array would get cheaper. It got **more expensive at the well-cooled end**
(net W, simulated ÷ pipeline: 1.87x at 120 CFM, 1.45x at 88, 1.25x at 60) and **cheaper at
30 CFM** (0.80x). That looks like a real and confusing effect. It is not:

| CFM | extra heat removed `dQ` (W) | extra temperature drop `dT` (K) | **`dT/dQ`** |
|---|---|---|---|
| 120 | 8.178 | 2.539 | 0.3104 |
| **88** | **8.056** | **2.615** | **0.3245** |
| 60 | 7.162 | 2.437 | 0.3403 |

The measured 34-core spreading boundary **at 88 CFM** is **0.3247 K/W**
(`spreading_boundary_by_die.json`). The 88 CFM row reproduces it to **0.06 %**. `[+]` **So the
entire extra array cost is the cost of landing 2.4-2.6 K cooler, at the package's own thermal
resistance — the leakage curve does not change what MR costs per kelvin.** What it changes is where
the planner's minimum-plan descent stops: on the pipeline curve the plan settles at 93.9 °C, on the
simulated ones at 91.3 °C. 120 and 60 CFM bracket the 88 value because the boundary resistance
genuinely varies with airflow; below 45 CFM the resistance is far enough different that the check no
longer applies and the sign even reverses.

`[!]` **So array costs are NOT comparable across curves as recorded**, because the two arms stop at
different peaks. Any future comparison of MR cost between curves has to be made at a matched peak,
or read as `dT/dQ` rather than as watts.

`[+]` **The die itself barely moved: `p_chip_W` changes by −0.9 to −1.1 % at 45-120 CFM** (116.6 →
115.5 W), because `--density 1.15` pins the die power and the curve only re-weights the leakage
inside it. Prediction 3's "chip_W down 5-12 %" is withdrawn; the true figure is ~1 %.

`[+]` **The GIDL bracket is worth nothing here either**, which now makes three studies in a row
(§P0.15's density ladder, §P0.15's clock search, this). Same 6/6 rescues, same arms diverging, `G`
within 0.3-0.7 of the full-GIDL run at every airflow. Stop carrying the ASAP7 GIDL uncertainty as a
caveat on anything but sub-ambient leakage.

#### `[!]` The clipping study: prediction 4 right in DIRECTION, wrong by two orders in SIZE

Fourteen more points (7 budgets x 2 measured curves), `--powers 25 --r-th 0.3 --mr-target-C 40`,
the E family of `build_joblist.sh` character-identical apart from the flag. This family was
predicted to move **hard and the other way**: its baseline sits at **344.9 K** (on the 345 K
crossover) and its MR arm at **326.1 K**, where the simulated curve carries **~5x** the
`dP_leak/dT` of the pipeline one. A steeper curve at the cooled temperature means each watt removed
sheds more leakage on top, so the same budget should buy more.

**It does — by 2-4 %.**

| K per watt removed | 0.5 W | 1 W | 2 W | 3 W | 5 W | 8 W | 12 W |
|---|---|---|---|---|---|---|---|
| pipeline | 6.070 | 6.048 | 6.007 | 5.596 | 3.759 | 2.438 | 1.704 |
| **simulated** | 6.212 | 6.198 | 6.167 | 5.740 | 3.900 | 2.539 | 1.778 |
| simulated-gidl-off | 6.254 | 6.237 | 6.198 | 5.769 | 3.929 | 2.558 | 1.793 |
| **simulated ÷ pipeline** | **1.023** | 1.025 | 1.027 | 1.026 | 1.038 | 1.041 | **1.043** |

`[+]` **The direction is right and the mechanism is confirmed** — MR is more effective on the
measured curve, more so as the budget grows and the arm sits colder, which is the crossover story
working. `[!]` **The size is not.** A ~5x difference in `dP_leak/dT` produces a **2-4 %** change in
what a watt of clipping buys, because `dT/dQ` at a targeted block is dominated by the local thermal
path and the leakage feedback rides on top as a second-order term. **A curve ratio is not a result
ratio**, and §P0.16 conflated them — the same error, in the other direction, that made prediction 1
wrong.

`[!]` **Two specific sub-predictions are WRONG:**
- *"the budget cliff moves to a LOWER budget"* — **it does not move at all.** The knee sits between
  3 and 5 W on all three curves and `dT` saturates at 20.5 K (pipeline) against 21.3 K (simulated),
  a 4 % difference at 12 W. **The budget cliff is geometry, and it survives the leakage curve
  exactly as it survived the 4x envelope refresh.**
- *"at least one `MR LOSES on GFLOP/s/W` verdict flips to a win"* — **none flips.** MR loses on
  perf/W at all 7 budgets on all 3 curves.

`[+]` **The GIDL bracket again changes nothing** (1.023 vs 1.030 at 0.5 W): four studies in a row.

#### `[!]` The granularity ladder — and the recorded one CANNOT be re-run on a measured curve

The handoff proposed re-running the granularity result (2.77x on a hotspot) with `--leakage-curve`.
**That experiment does not exist.** `examples/tile_pitch_sweep.py`, which produced the recorded
number, holds **no leakage model and never calls the feedback loop** — its own output note says
*"Linear solves, no leakage feedback."* Adding the flag there would be a literal no-op and the
output byte-identical. `[!]` **Before re-running a study on a new input, check the study consumes
that input.**

The coupled form of the same question runs the pitch ladder through `mr_comparison.py`, which does
solve the coupled problem and does take the flag. Held at the airflow ladder's own operating point
(density 1.15, 88 CFM, target 92 °C) so the 500 µm rung reproduces that family exactly. 18 points.

`[+]` **The control arm diverges at every pitch on every curve** — so the rescue survives across
the whole granularity ladder as well as the whole airflow ladder. Combined: **35 of 35 measured
rescue points intact.**

`[+]` **Fine pitch saturates below ~200 µm.** On the simulated curve 50, 100 and 200 µm cost
19.476 / 19.476 / 19.470 W — identical to four figures across an **813x** range in tile count
(40,672 / 10,168 / 2,542 tiles). The recorded *"optics requirement ~50 µm, not 10"* is if anything
conservative: **200 µm buys everything 50 µm buys**, and that is a directly useful relaxation for
the device roadmap.

`[!]` **The coarse-vs-fine penalty appears to move, and it does not — the raw ratio is a landing-
point artefact, and correcting it REVERSES the ordering:**

| curve | raw 2000 µm ÷ 200 µm | **normalised to a common 93.5 °C peak** |
|---|---|---|
| pipeline | 1.30x | **1.29x** |
| simulated | **1.70x** | **1.18x** |
| simulated-gidl-off | 1.71x | 1.18x |

On the simulated curve the 2000 µm rung's descent stops **3.3 K below** the 200 µm rung's (90.20 vs
93.48 °C), and buying those kelvin at the package's own 0.3247 K/W is most of its extra cost. The
pipeline rung barely moves under the same correction (1.30 -> 1.29) precisely because its peaks were
already uniform. `[!]` **So "granularity matters 30 % more on the measured curve" is withdrawn
before it was ever quoted**; the honest statement is that the granularity penalty **does not clearly
move with the leakage curve**, consistent with the airflow and clipping families.

`[+]` This is the third time this session that a minimum-plan comparison across curves has been
confounded by where the descent stopped, and the second time the correction changed the answer's
**sign**. **Any cross-curve MR cost comparison must be normalised to a common peak before it is
read.** That is now a standing rule, not an observation.

### `[+]` §P0.16's real conclusion: the MR catalogue does NOT need a curve-driven re-run

Both MR families are **insensitive** to the leakage curve — 18/18 rescues intact, clipping efficacy
within 4 %, budget cliff unmoved — while the density ladder moved 14 % and the clock search lost a
headline. That is the transferable result sharpened one more turn: **§P0.15 said which part of a
curve is load-bearing depends on the experiment; §P0.16 adds that for a whole family of experiments
the answer can be "no part of it".** The MR studies sit at or above the 345 K crossover, where the
two curves nearly agree, and they are ratios between two arms at the same temperature, so what
disagreement remains largely cancels.

**Practical consequence for §3's decision:** `--leakage-curve` is **not** a reason to re-run the MR
catalogue. It is a reason to re-run the **density and clock** families, which are the ones that
moved. `--rbb-policy` and the `core_other` accounting still argue for one full pass.

#### Prediction scorecard — final

| # | prediction | outcome |
|---|---|---|
| 1 | 0 of 6 rescues survive | **WRONG — 18/18 survive** |
| 2 | converted controls hold > 112 °C | **vacuous — nothing converted** |
| 3 | array cheaper, `chip_W` −5-12 % | **WRONG in direction** — up to 1.87x dearer (a landing-point artefact), `chip_W` −1 % |
| 4 | clipping harder/more effective, cliff moves, a verdict flips | **direction RIGHT, size wrong (2-4 %, not ~5x); cliff does not move; no verdict flips** |
| 5 | granularity + budget cliff survive within ~20 % | **RIGHT — budget cliff unmoved (4 %)**; granularity not re-run this session |

`[!]` **The one methodological lesson worth carrying out of four wrong predictions in a row:** both
of this session's failures came from turning a **curve ratio** into a **result ratio** — dividing a
measured loop gain by 2.4x in prediction 1, multiplying a clipping efficacy by ~5x in prediction 4.
Neither survived contact. Where a directly comparable **measurement** already existed (§P0.15's fine
ladder, which had the shaped arm's cliff identical on both curves), it predicted the outcome
correctly and the analytic estimate built on top of it did not.

### `[+]` §P0.16 — the 36 net-generating rows are corrected, by algebra, with no re-solves

`examples/findings_recovery_correction.py`,
`docs/evidence/findings_recovery_correction.json`, 5 tests in
`HotGauge/HotGauge/thermal/test_findings_recovery_correction.py`.

`FINDINGS.json` carried **36 negative `p_mr_net_W` entries** — a cooler that returns more power
than it draws, the first-law recovery bug in pure form. No solve is needed to fix them:
`recovery_at_junction` is post-hoc accounting, and `net = gross * (1 - ratio)` with `ratio` a
function of the MR params and `T_h` alone, so

    net_new = net_old * (1 - ratio_new) / (1 - ratio_old),
    ratio_new = params.breakeven_ratio_at(peak_C + 273.15)

**All 36 are corrected and all 36 flip sign.** Recorded total **−5.879 W → +32.672 W**. The audited
row `overnight3[11]` goes **−0.596 W → +3.354 W**, matching the +3.35 W the audit predicted, and
its implied `ratio_old` recovers `MRParams.breakeven_ratio` to four significant figures.

`[+]` **`gross`, `cop` and spot dilution all cancel in the ratio form, which is what makes it exact
— and it mattered.** `overnight3[26]` (`p4_spot_s100_dilute`) has `net/q = −0.6210` where every
other row has `−0.1185`, which reads as a *different efficiency preset*. It is not: it is a **5.24x
spot-dilution overhead** — 100 µm spots on the `dilute` policy, billing the laser for the whole
pixel. Identifying a preset per row from `net/q`, the obvious approach, would have mis-assigned
that row; the ratio form never asks. A test pins this.

`[!]` A row with no `peak_C` has no `T_h` and is **refused rather than guessed**. None of the 36
hit that path, but the driver would report it rather than silently correcting.

`[!]` These are corrected values for the *recorded* rows, not a re-run: they inherit whatever
`peak_C` the recorded solve produced, so if the catalogue is re-run under any of the three flags
above, the correction must be recomputed against the new `peak_C`.

### `[+]` §P0.16 — the catalogue re-run is priced: **6.3 h wall**, and three flags now want it

`python scripts/catalogue_rerun.py` re-planned 1 Sep 2026 against the current batch scripts (it
reads the point list out of them, so nothing was re-listed by hand):

```
points           : 252 invocations from 12 batch scripts
arms             : 578 (three per planner point -- control, array_idle, array_on)
distinct matrices: 64 in 41 groups
streams          : 6 concurrent, peak 83.5 GB of a 200 GB budget
solves           : ~161,218
estimated        : 32.0 h total = 3.2 h factorising + 28.8 h solving
                   **6.3 h wall on the longest stream**
```

`[!]` **The "80,330 solves / 63.5 days" figure that gets quoted is the COLD cost and should stop
being quoted.** Warm — reusing each factorisation across every point sharing its system matrix —
the whole catalogue is an **overnight run**. Concurrency is memory-bound, not core-bound: the
widest single session is 28.8 GB, so ~6 streams fill a 200 GB budget on a 96-core node. The count
has roughly doubled from §P0.5b's ~155,000/5.3 h estimate only because every planner point now
emits three arms and the control arm's stack (30 µm of grease) is a *different matrix* from the
array arms' (30 µm of GaAs pixels).

**So the decision is not "is a 14 % move worth 63 days". It is "is it worth one night", and there
are now three separate reasons to spend it, which is the argument for spending it once:**

1. **`--leakage-curve`.** §P0.14/§P0.15 moved the flat-die ceiling ~14 % and withdrew a
   `CLOCK_HEADROOM.md` headline. §P0.16 shows the MR families are *insensitive* — 18/18 rescues —
   so the curve does **not** force a re-run on their account. It is the density and clock families
   that carry the move.
2. **`--rbb-policy stock` vs `amortized`.** Still undecided, still moves every recorded thermal
   number, and §P0.10 settled the semantics in `amortized`'s favour.
3. `[!]` **New this session: the `core_other` accounting** (see below). It leaves the die total and
   the static fraction intact but overstates `core_other`'s share of on-die **leakage** ~1.75x, and
   `core_other_<N>` is the block that runs away at every diverging point on the density ladder.

`[!]` **Do not spend the run on one flag and then need it again for the next.** All three change
the same numbers on the same points, and the plan above costs one night whether it carries one
change or three. **This is a decision for the user, not a run to start unilaterally** — item 3 in
particular is a change to a stock converter that the entire recorded catalogue rests on, and
nothing in it has been modified.

### `[+]` §P0.16 — `core_other` explained: the 2.0000x is a literal `2 *` in our own converter

`core_other_<N>` is stock HotGauge's map of McPAT's **bare `Core<N>` row**
(`HotGauge/configuration/mcpat.py`, `MCPAT_UNIT_NAME_MAP['Core'] = 'core_other'`). It is 32-42 % of
on-die leakage and ~38 % of die power, it is the block that runs away at **every** diverging point
on the density ladder, and nothing had ever checked what it contains. Three things were measured on
1 Sep and flagged as *an observation, not a conclusion*: leaves summing to exactly `2.0000x` the
bare row on dynamic across all 8 cores / 16 slices / 3 nodes, `0.684-0.694x` on leakage, and bare
rows summing **exactly** to `Processor/Total Cores`.

**All three are now explained, from `McPAT/`'s raw print and our own converter rather than the
JSON, and the explanation is one line of source.**

`scripts/mcpat_to_blk_lvl_power_dict.py`, `get_per_core_total_power` — applied to every *itemised*
per-core unit:

```python
total_dynamic_power = 2 * runtime_dynamic          # <- the 2.0000x, literally
total_leakage_power = subthreshold_leakage + gate_leakage    # <- no factor
```

and ~25 lines below, the bare `Core<N>` row is built by a **different code path with no factor**:

```python
runtime_dynamic = mcpat_output_dict['Core'][core_num]['Runtime Dynamic']
thermal_input_dict['Core' + str(core_num)] = [runtime_dynamic, total_leakage_power]
```

That accounts for every part of the observation at once, and for why it hits dynamic *only*:

| observation | cause |
|---|---|
| dynamic leaves = **exactly** 2.0000x the bare row, every node, every slice | a literal `2 *` on the child path and none on the parent path — a constant, so it cannot vary |
| leakage leaves = 0.684/0.688/0.694x, **node-dependent** | no factor on either path, so this is the **genuine** un-itemised leakage remainder |
| bare rows sum exactly to `Processor/Total Cores` | both are 1x and McPAT's own hierarchy closes |

`[+]` **Verified against raw McPAT (`mcpat_output_*.txt`), which is the part that settles it.** In
McPAT's own print the `Core` row's direct children sum to **1.0000x** the bare row for *Runtime
Dynamic* and for *Peak Dynamic*, and every intermediate parent closes on its children to 1.00000.
So **McPAT itemises 100 % of a core's dynamic power — there is no un-itemised dynamic remainder at
all.** Leakage does not close (children are 0.70x the parent), so the un-itemised slab is **real
for leakage and fictitious for dynamic**. Confirmed exact (`min == max == 2.000000` over all 24
leaves) at 10 nm and 14 nm as well as 7 nm.

`[!]` A parser trap worth recording, because it cost the first pass: McPAT prints the per-core
`L2` block as a section header **with no trailing colon**, and prints `L2`'s attributes at the
**same** indent as that header rather than under it. A parser that pops on `indent >= ` re-parents
the whole L2 block onto `Core`, and the bare `Core` row then appears to hold L2's numbers. Pop on
strictly-greater.

#### `[!]` Is the recorded die power consistent? **NO — and a first correction of this section was wrong**

`[!]` **This subsection replaces an earlier version of itself, written the same day, whose numbers
were wrong.** That version reported the static fraction as *safe* (18.43 % -> 18.59 %) and said
`core_other`'s corrected 2.006 W of dynamic was "entirely the modelled IMC/IO/SoC power". Both came
from a scratch McPAT text parser that keyed section headers on `raw.split(':')[0]`. McPAT prints
`Integer ALUs (Count: 6 ):`, `Floating Point Units (FPUs) (Count: 2 ):` and
`Complex ALUs (Mul/Div) (Count: 1 ):` — so that rule yielded `Integer ALUs (Count`, matched no JSON
key, and **silently dropped the three highest-power execution rows of every core into the
remainder**. Sniper's own parser keys on `^( *)([^:(]*)`, stopping at `:` **or** `(`, which is why
the recorded JSON has clean names. `[+]` The production module never had this bug — it works from
the JSON's own key structure and never parses the text — and the corrected figures below are
**its** output, validated leaf-by-leaf against raw McPAT (864 leaves, 3 nodes, **exactly 0**
relative error; corrected `core_other` dynamic 7.4e-06 W).

Measured end to end through `prepare_dice_trace` onto the real 34-core floorplan, 7 nm linpack
tick 2e12:

| variant | die dynamic | die leakage | **static fraction** | `core_other` % of dyn | **`core_other` % of leakage** |
|---|---|---|---|---|---|
| recorded (as built) | 22.71 W | 5.13 W | **18.43 %** | 32.0 % | **35.6 %** |
| undouble dynamic only | 15.45 W | 5.13 W | 24.93 % | 47.0 % | 35.6 % |
| residualise `Core` only | 8.20 W | 3.86 W | 32.03 % | **−88.6 %** | 14.4 % |
| **both — hierarchy-consistent** | **8.20 W** | **3.86 W** | **32.03 %** | **0.0 %** | **14.4 %** |

`[!]` **The static fraction is NOT safe: it moves 18.43 % -> 32.03 %, a factor of 1.74.** The
earlier "0.16 pp, they cancel" claim is **withdrawn** — the apparent cancellation was the missing
ALU/FPU rows inflating the corrected die's dynamic.

`[+]` **And a third, independent check says the corrected value is the right one.** McPAT's own
`Processor` block reports `Runtime Dynamic = 7.3851 W`, `Subthreshold Leakage = 3.05158 W`,
`Gate Leakage = 0.0182661 W` — a **29.36 %** static fraction. The hierarchy-consistent die lands at
32.03 % (the 2.7 pp gap is L3 bridging and which blocks the floorplan carries); the as-built die
lands at **18.43 %, roughly half**, which is exactly what a `2 *` on the dynamic column alone
predicts. The as-built die does not reproduce McPAT's own ratio and the corrected one does.

`[!]` **`core_other` should carry NO dynamic power at all**, only the leakage remainder
(0.0697 W per core at this slice). Its corrected dynamic is 7.4e-06 W across all 144 cores checked.
The earlier "2.006 W of IMC/IO/SoC" is withdrawn — that was the dropped ALUs and FPUs.

`[!]` **`core_other`'s share of on-die leakage is overstated 2.47x**, 35.6 % -> 14.4 % (not the
1.75x first reported).

`[!]` **Neither fix is usable alone.** Undoubling alone gives 24.93 %; residualising alone puts
**negative** power on `core_other` (−88.6 % of die dynamic), because it subtracts doubled children
from an undoubled parent. They are one correction, not two.

#### `[!]` And the `core_other` accounting moves a DENSITY CEILING, on one paired solve

Two `mr_comparison.py` runs at density **0.85 W/mm², 88 CFM**, identical in every argument except
`--core-other-policy` (`results/_co_smoke*`):

| policy | control arm | peak block |
|---|---|---|
| `stock` (recorded) | **RUNAWAY — no steady state** | — |
| `hierarchy-consistent` | **converges, 95.2 °C** | `RBB_0 -> RBB_16` |

Same die, same die power (renormalised by `--density` in both), same package, same curve, same RBB
policy. **The only difference is how McPAT's per-core power is distributed across the floorplan** —
and it decides whether the die has a steady state at all.

`[+]` **The mechanism is exactly what §P0.16 predicted from the accounting.** As built,
`core_other_<N>` carries ~32 % of die dynamic and ~36 % of die leakage concentrated on one
leftover-area slab per core. That is an artificial hotspot, and it is why `core_other_0` is
recorded as *"the block that runs away at every diverging point on the density ladder"* (§P0.10,
§P0.11). Under the corrected accounting `core_other` carries **no dynamic at all** and the peak
block becomes **RBB**, which is a real block with a real floorplan location.

`[!]` **This puts §P0.11's density ceiling in question, and in the optimistic direction** — the
recorded ceiling may be pessimistic because of an accounting artefact rather than physics. It does
**not** overturn it: §P0.11's flat-die (Gini 0) arm has *no* hot block to blame and would be far
less sensitive to how one slab is weighted, and this is **one paired point, not a ladder**. `[!]`
Do not quote a new ceiling from this. The four-arm catalogue re-run (below) carries the measurement
that would settle it, and until it lands the recorded ceilings stand with this caveat attached.

### `[+]` §P0.16 RESULT — the four-arm catalogue re-run: most recorded divergence is an ARTEFACT

`scripts/catalogue_rerun_arms.sh`, `examples/catalogue_arm_compare.py`,
`docs/evidence/catalogue_arm_compare.json`. Four arms, each differing from the previous by
**exactly one flag**, 158-159 reachable points apiece, **all four complete, zero data anomalies**
(every point carries all three MR arms; no holding row has a missing or implausible peak).

#### The control arm — the arm the density ceiling and the rescue claim both rest on

| arm | curve | RBB | `core_other` | holds | **diverged** | unconverged |
|---|---|---|---|---|---|---|
| **A** | pipeline | stock | stock | 50 | **94** | 1 |
| **B** | simulated | stock | stock | 107 | **27** | 11 |
| **C** | simulated | amortized | stock | 107 | **30** | 8 |
| **D** | simulated | amortized | hierarchy-consistent | 134 | **8** | 4 |

Paired, one flag at a time, on the 145 points common to all arms (`unconverged` counted as
neither, so every flip below is decided → decided):

| step | isolates | verdict flips | peak on points holding in BOTH |
|---|---|---|---|
| **A → B** | the leakage curve | **57 diverged → holds** | mean **+0.28 K** |
| **B → C** | the RBB policy | **none** (134/145 unchanged) | mean −0.55 K, largest −5.35 K |
| **C → D** | the `core_other` accounting | **22 diverged → holds** | mean **−5.38 K**, largest −12.73 K |

`[!]` **The recorded catalogue's control arm diverges at 94 of 145 points. Under the best available
physics it diverges at 8.** Two changes account for essentially all of it, and neither is a
cooling improvement — both are corrections to inputs that were wrong:

- **the leakage curve is worth 57 points**, and
- **the `core_other` accounting is worth 22**.

`[+]` **The RBB policy is worth nothing to the verdicts, and that finally settles the open
question.** B → C flips **no** point in either direction; it moves temperatures a little (control
mean −0.55 K, array arm mean −3.02 K). §P0.10 predicted exactly this — *"converging points move a
lot, the ceiling does not move at all"* — and the catalogue-wide re-run confirms it at 145 points
instead of a ladder. **Switching the default to `amortized` is therefore low-risk**: it changes no
verdict anywhere in the catalogue, and §P0.10's source reading (`McPAT/core.cc`) argues for it.

#### `[!]` This looks like it contradicts §P0.14's density ceiling, and it does not

§P0.14/§P0.15 measured the simulated curve moving the flat-die ceiling **DOWN 14 %** — *more*
divergence. Here the same swap converts **57 points from diverging to holding** — far *less*.
Both are right, and the crossover is why. The two curves cross near **345 K**: the simulated curve
carries more feedback gain below it and less above.

- §P0.14's uniform density arm sits at **~322 K**, below the crossover -> more gain -> ceiling down.
- The catalogue's control points at product densities run **hot**, above the crossover -> less gain
  -> they stop running away.

`[+]` So this is a **confirmation** of §P0.14's mechanism at catalogue scale, not a contradiction —
and it sharpens the rule: **the sign of the leakage curve's effect on a point depends on which side
of 345 K that point sits.** Neither "the curve makes things worse" nor "better" is a statement that
survives on its own.

`[+]` Consistent with that, A → B barely moves the temperature of points that hold in **both**
arms (mean +0.28 K): the curve swap matters at the **stability boundary**, not for comfortable
points. `core_other` is the opposite — it moves *every* point (mean −5.38 K, up to −12.73 K),
because it redistributes power rather than changing a feedback slope.

#### The MR arm is far more robust than the control arm

Same chain, `array_on`: **no verdict flips at A → B or B → C**, and only **3** at C → D. The array
holds essentially everywhere under every combination. `[+]` **That is the strongest form yet of
§P0.16's other result** — the MR catalogue is insensitive to all of this, while the *control* arm,
which is what the ceiling claims rest on, is highly sensitive. The rescue claim survives because it
is a difference, and the array side of that difference barely moves.

`[!]` **What this does NOT license.** It does not restate the density ceiling as a number: these
are catalogue points at heterogeneous densities and coolings, not a ladder, and §P0.11's flat
(Gini 0) arm — the one with no hot block to blame — is not among them. The honest claim is
**"most of the recorded catalogue's divergence is an artefact of two corrected inputs"**, and the
ceiling itself wants the density ladder re-run under arm D's configuration. That is the obvious
next measurement and it is cheap.

`[!]` **`unconverged` rows moved too and must not be read as holds** (A 1, B 11, C 8, D 4). They
are excluded from every flip count above.

#### `[!]` A latent MR-planner bug found by the re-run: `__agg__L3` is placeable and is not a block

Ten points of every arm fail with

    KeyError: "plan names block '__agg__L3', which is not in the floorplan"

**Cause.** `bridge_aggregates=True` injects a *synthetic* temperature key for the bridged L3
aggregate (`leakage_feedback.AGG_L3_TEMP_KEY = '__agg__L3'`,
`BRIDGEABLE_AGGREGATES = {'Processor/Total L3s': AGG_L3_TEMP_KEY}`) so L3 leakage can feed back —
the +45 % in CLAUDE.md. The MR planner in `thermal/microrefrigeration.py` then treats **every**
above-target key as a placeable block: it contains no reference to `AGG_L3_TEMP_KEY` or `__agg__`
anywhere, so it never filters the synthetic ones. When the plan is handed back for placement, the
floorplan has no such block and it raises.

**Trigger — the MR target, and the boundary is measured.** The synthetic key only enters the plan
once it is *above target*, so the bug is invisible at ordinary targets and fires at low ones:

| point | `--mr-target-C` | outcome |
|---|---|---|
| 16 `A_ceiling_T50` | 50 | **ok** |
| 17 `A_ceiling_T40` | 40 | **raised** |
| 18 `A_ceiling_T30` | 30 | raised |
| 19-26 `A_dtmax_*`, `A_hmax_*` | 40 | raised |
| 27 `rescue_d0.80` | 98 | ok |

`[!]` **That bracket is WITHDRAWN as a fixed rule.** The table above is arm D. The *same* point 16
(`A_ceiling_T50`, target 50) **raised in arm B**, where it completed in arm D. The bug fires when
the synthetic key's **temperature** exceeds the target, and that temperature depends on the leakage
curve and the `core_other` policy — so the trigger is **physics-dependent and arm-dependent**, and
no fixed `--mr-target-C` threshold expresses it. `[+]` It is also a small independent corroboration
of the `core_other` finding: arm D's corrected accounting leaves the die cool enough that a point
failing elsewhere succeeds there.

`[+]` **Not caused by this session, and not by any of the three flags.** Arm **B** reproduces it
with `--core-other-policy stock`, and the discriminator is the *target*, not a flag. It is a latent
bug that `bridge_aggregates` introduced and that only a low-target point reaches.

`[!]` It affects **most** points in every arm, but *not* identically — see the withdrawal above.
The four-arm comparison is still unharmed:
`catalogue_arm_compare.py` compares only points present in **both** arms of a pair, so these are
skipped rather than counted as a change. The catalogue re-run loses 10 of 180 points per arm.

`[!]` **It also puts a caveat on recorded low-target results.** `results/followon/A_ceiling_T40`
and friends exist in the recorded tree, so they ran successfully *before* `bridge_aggregates` was
added — they are from a different code path than anything solved today, and they cannot currently
be reproduced at all.

**The fix, not applied here:** filter `BRIDGEABLE_AGGREGATES.values()` out of the planner's
candidate blocks (they are a leakage-feedback bookkeeping device, never a coolable surface).
`[!]` Deliberately **not** done mid-run: it changes MR planning behaviour, so applying it now would
leave some points solved with it and some without, inside arms that exist to isolate one flag. It
wants its own change, its own test, and its own re-run of the affected points.

#### `[~]` An operational signal from the running re-run — **PROVISIONAL, partial campaign**

`[!]` **Do not quote this. It is a partial campaign and §P0.15 lost six solves to exactly this
mistake.** It is recorded because it is a *memory* diagnosis that happens to be predictive, and
because it should be checked against the finished arms rather than rediscovered.

Arm D (`hierarchy-consistent`) holds **136 GB** of node-06 against arm A's (`stock`) **85 GB**,
on identical point lists. The cause is convergence rate: a converging point holds its factorised
session for many more solves, so more of them are live at once. Scored so far:

| arm | arms scored | converged | diverged |
|---|---|---|---|
| A (`stock`) | 114 | 89 (**78 %**) | 25 |
| D (`hierarchy-consistent`) | 219 | 217 (**99 %**) | 2 |

Consistent with the paired 0.85 W/mm² solve above (stock runs away, corrected holds at 95.2 °C),
and with the mechanism: the `2 *` concentrates ~32 % of die dynamic on one leftover-area slab per
core, and removing it removes the artificial hotspot. `[!]` **If it survives to completion it means
a large part of the recorded catalogue's divergence is an accounting artefact** — which is a much
bigger claim than "the ceiling moves 14 %", and precisely why it must wait for the full arms.

`[+]` A useful side-effect worth keeping: **arm D is also FASTER** (219 arms scored against 114 in
the same wall time), because a divergence adjacent to a cliff costs hours while a converging point
does not.

#### `[!]` What this does to §P0.15's cold-zone prize

§P0.15's re-derived **static 15.98 %** was computed on the as-built die, so it carries the same
factor. Under the consistent policy it should rise by roughly **1.74x**, and the prize with it —
from ~5.7 % of die power toward **~10 %**, i.e. back to the McPAT-leaf value §P0.15 called an upper
bound. `[!]` **That is a direction and a rough size, not a re-derivation** — it must be recomputed
on the steady slices under the policy, not scaled by hand, and until it is, quote §P0.15's ~6 % with
this caveat attached. **The 2.23x improvement is untouched either way**, which is once again why
that is the number to lead with.

`[!]` **Nothing was changed.** The recorded catalogue rests on the as-built converter, the standing
rule is that stock-file changes stay additive, and the static fraction shows the aggregate is
sound. This is a finding for the **catalogue re-run decision** (§3), not a patch to land mid-flight
— and it is a second reason that re-run wants to be one deliberate pass rather than several.

---

## P0.13 — The curve is simulated now, and the cold end of P0.12 was wrong  `[x]` 31 Aug 2026

`HotGauge/HotGauge/power/spice_sim.py` + `device_leakage.SimulatedLeakageCurve`, 21 new tests,
`examples/device_leakage_spice.py`, `docs/evidence/device_leakage_spice_asap7.json`,
`MXL_SPICE_fixes/`, `scripts/spice_env.sh`. Toolchain in `spice_toolchain/` (gitignored, 6.5 GB).

### The tooling task is finished

§P0.12 ended with "getting a BSIM-CMG-capable simulator is now the highest-value tooling task in
the project". It is built, all three of `docs/BSIMCMG_TOOLCHAIN.md`'s checkpoints pass, and
**Xyce was never needed**:

- **ngspice 47** from source with OSDI (conda-forge's 41 is built `--disable-osdi` and has no CMG);
- **OpenVAF 23.5.0** compiling BSIM-CMG Verilog-A to `.osdi` — after fixing a **segfault-on-every-
  input UB bug in OpenVAF itself**, one character, `MXL_SPICE_fixes/`;
- the vendored ASAP7 card evaluated directly, all ~130 parameters, **no fit to anything**.

The doc's own Checkpoint 1 was testing the wrong spelling (`pre_osdi` is a netlist directive, not
a command); corrections are recorded there rather than silently applied.

### `[+]` It is a device, and that is checked rather than asserted

| check | result |
|---|---|
| I_off at 300 K | **0.232 nA/µm** — an HP 7 nm FinFET |
| subthreshold swing at 300 K | **61.7 mV/dec** against a 59.5 ideal |
| BSIM-CMG 110 vs 111.2.1 vs Xyce tree | agree to **0.37 %** normalised |
| parameters the model rejects | `capmod`, `coremod`, `version` — switches **removed after 107**, not dropped values |
| numerical convergence (10× `nfin`) | **0.036 %** |

### `[!]` The three curves, and they disagree in both directions

Relative to 330 K, `nmos_rvt`, V_gs = 0, V_ds = 0.7 V:

| T | pipeline (CACTI) | analytic (P0.12) | **simulated** | sim, GIDL off |
|---|---|---|---|---|
| 200 K | 0.923 (clamped) | 0.0060 | **0.126** | 0.0032 |
| 250 K | 0.923 (clamped) | 0.0110 | **0.140** | 0.0167 |
| 310 K | 0.923 (clamped) | 0.344 | **0.481** | 0.406 |
| 400 K | 36.1 | 19.4 | **10.9** | 12.3 |
| 450 K | 600 | 95.4 | **41.4** | 47.3 |
| 500 K | 5820 | 349 | **123** | 141 |

### `[!]` Finding 1 — the cold-zone prize is ~20× smaller than P0.12 promised

P0.12 said leakage keeps falling below 310 K until a **gate**-leakage floor takes over at ≈ 244 K.
The floor is real; **the mechanism was wrong and so was its height**. Simulated, the cold floor is
**GIDL — 98 % of the leakage at 200 K** — and it sits about **40× above** the gate floor P0.12
assumed. Decomposed rather than argued: `igcmod = 0` barely moves the curve, `gidlmod = 0` drops
200 K by ~40×.

This was foreseeable from P0.12's own text, which lists GIDL as omitted and says it "would raise
leakage at both ends". What that note got wrong is the reasoning that GIDL "needs a negative gate
bias to matter": the bias that matters is gate-to-**drain**, which in the ordinary off state is
−V_dd. **GIDL is on in every off device on the die**, not in an exotic corner.

At 200 K the pipeline says 0.923, P0.12 said 0.0060, and the simulator says **0.126**. The true
answer is between the two previous ones and much closer to neither.

`[!]` **Carry this as a bracket, not a number.** ASAP7 is a *predictive* PDK; its GIDL
coefficients (`agidl = 1e-12`, `bgidl = 1e7`, `egidl = 0.35`) are a model choice, not a
measurement of a fabricated part. The GIDL-off column is in the table above and in every row of
the evidence file for exactly that reason, and `load_simulated_curve(mechanism=...)` serves both.

### `[+]` Finding 2 — the hot tail is gentler still (but see the `[!]` below)

At 500 K: pipeline **5820×**, P0.12's analytic model **349×**, simulator **123×**. Both
replacements agree the pipeline's Arrhenius tail is far too steep, and the simulator is gentler
than the analytic model by another **2.8×**.

`[!]` **This section originally concluded that §P0.11's flat-die ceiling is therefore
*conservative*, reasoning that a gentler tail runs away later. §P0.14 measured it and the ceiling
moved the other way.** The inference was wrong because runaway is decided by the curve's *slope
near the operating point*, not by its value at 500 K — and there the pipeline curve is the flatter
of the two. The claim is withdrawn; see §P0.14.

### `[+]` What P0.12 got right

Inside **310–400 K** — the only window McPAT will simulate at all — the analytic model and the
simulator agree to better than **2×**, from completely different assumptions (a two-parameter fit
to CACTI's table versus the vendor's full model in a solver). That is a real cross-check and it is
asserted as a test. P0.12's central claims stand: the pipeline curve *is* a pass-through of
CACTI's `I_off_n[0][*]`, its implied activation energy *is* unphysical, and both of its ends move
by a lot. Only the *size and mechanism* of the cold-end correction changed.

### `[!]` What nearly produced a plausible wrong curve, and is now guarded

Not the card — the arithmetic. **One 7 nm fin leaks a few pA, below what ngspice's linear solve
can resolve**: with the default SPARSE solver every current came back an exact multiple of
2⁻⁴³ A. KLU moves the 250 K point 2.3 %; the real fix is to simulate **1000 fins and divide**, DC
current being exactly linear in fin count. At `nfin = 1` the GIDL-off point at 200 K was **70 %
wrong**, and the Xyce-tree cross-check appeared to disagree by **10 %** where it actually agrees to
0.37 %. That 10 % would have been written up as a model difference. `spice_sim.DEFAULT_NFIN` is
1000, the driver asserts convergence against a 10× re-run, and both are tested.

### Honest limits

One device (`nmos_rvt`), one bias corner, one fin's worth of geometry, no self-heating
(`shmod = 0`). A die leaks at a distribution of biases, stack heights and flavours, so **what
transfers downstream is the shape of I_off(T), not the amps**. And ASAP7 remains predictive
silicon, not measured silicon.

### Next

Re-run the density ladder and the cold-zone prize on the simulated curve, **on the same 34-core
die** — the one-die constraint holds. Both directions have moved: the cold zone is worth much less
and the hot ceiling is further away than recorded.

---

## P0.12 — The leakage curve is eleven hard-coded numbers, and they are not a device  `[x]` 31 Aug 2026

`HotGauge/HotGauge/power/spice_cards.py`, `device_leakage.py`, 21 tests,
`examples/device_leakage_calibration.py`, `spice_leakage/` (vendored card + provenance),
`docs/evidence/device_leakage_asap7.json`.

### `[!]` The curve every thermal result rests on is a pass-through

`leakage_calibration.json` came from eleven McPAT runs whose XML differs in **one line** (the
temperature — verified by diff). Normalised, the resulting chip subthreshold power is
**bit-for-bit CACTI's hard-coded `I_off_n[0][*]` array for "16nm DG HP"** — ratio 1.000 at all ten
points, max deviation **3.8e-6**. No device mix, no aggregation, no structure dependence: McPAT is
a pass-through for this quantity.

That array is written at `McPAT/cacti/technology.cc:1610` as literals like `1.52e-7/1.5*1.2*1.07`
— 32 nm numbers times three fudge factors — and the **same table is reused unchanged for 32, 22 and
16 nm**.

### `[!]` And its shape is not a device

Back out the local activation energy, `Ea = −k·d(ln I)/d(1/T)`. One barrier gives one `Ea`,
drifting smoothly. This table gives:

| between | 300–310 | 330–340 | 350–360 | 370–380 | 390–400 |
|---|---|---|---|---|---|
| `Ea` (eV) | **0.016** | 0.119 | 0.740 | 0.561 | **1.081** |

A **69× spread, and not monotone**. 0.016 eV is *below kT at room temperature* (0.026 eV); 1.081 eV
is essentially the silicon bandgap (1.125 eV). Those are different mechanisms. **It is an
interpolation, and this project has been treating it as a measurement.**

### What a real device card says

ASAP7's BSIM-CMG 107 7 nm FinFET card (BSD-3-Clause, vendored with provenance), in the analytic
off-state limit. Two barrier forms — one with its temperature *shape* locked to the card's own
Varshni bandgap, one with a free slope — **agree with each other within 4 % out to 500 K**, so the
answer does not depend on that choice.

| T | pipeline today | card-based | pipeline / card |
|---|---|---|---|
| 200 K | 0.923 (clamped) | 0.0060 | **155×** |
| 250 K | 0.923 (clamped) | 0.0110 | **84×** |
| 310 K | 0.923 (clamped) | 0.344 | 2.7× |
| 400 K | 36.1 | 19.4 | 1.9× |
| 450 K | 600 | 95.4 | **6.3×** |
| 500 K | 5820 | 349 | **17×** |

- **Cold zone: the clamp is not physics.** Leakage keeps falling below 310 K, until the
  temperature-independent **gate-leakage floor takes over at ≈ 244 K**. That is where the
  cold-zone prize actually ends — not at 310 K, which is merely where CACTI's table stops.
- **Hot zone: the Arrhenius tail is too steep**, by 6× at 450 K and 17× at 500 K.

### `[!]` What this does to §P0.11 — **superseded by §P0.14, and it was backwards**

The flat-die ceiling of **1.0–1.2 W/mm² was solved on the pipeline curve**, whose tail is ~6×
steeper at 450 K than the card-based physics. A gentler tail runs away *later*, so **that ceiling
is conservative** and must be quoted "on the current leakage curve" until this is settled.

`[!]` **That inference was tested in §P0.14 and it is wrong.** Runaway is decided by
`d(ln P_leak)/dT` near the *operating* temperature, not by leakage at 450-500 K, and in that band
the pipeline curve is the **flatter** of the two. Measured, the uniform arm's ceiling moves one
rung **down**, so the recorded ceilings are optimistic rather than conservative. The paragraph
above is kept as written because it is what the evidence supported at the time; do not quote it.

### `[!]` Honest limits — this is not a SPICE run

The cards are real; the simulation is not. **No simulator here can evaluate BSIM-CMG**:
conda-forge's `ngspice-41` is built without it *and* without OSDI, there is no `xyce` package, and
OpenVAF ships no binary — compiling the Verilog-A means building a Rust/LLVM toolchain first.
`ptm.asu.edu` no longer resolves at all, which is why ASAP7 (same group, published, BSD) stands in
for PTM. Also: the model is fitted to the very table it criticises, so it inherits that table's
*level* and only its *shape* is independent; its two parameters are **degenerate** over a 90 K
window, so neither may be quoted as a device property; and GIDL is not modelled, which would raise
leakage at both ends.

**Getting a BSIM-CMG-capable simulator is now the highest-value tooling task in the project.**

---

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
