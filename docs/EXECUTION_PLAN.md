# Phase 0 execution plan

Companion to `docs/CODESIGN_PLAN.md`. That document says *what* has to be true before the
co-design programme means anything; this one says what to run, in what order, on what hardware,
and how we will know each item is done.

Written 25 August 2026. Everything in §1 was measured today on node-06-8xv100 under slurm job
1320 and is recorded in `docs/evidence/solve_cost_two_die.json`. §6 is **settled** — the device's
geometry was decided the same day and is now pinned in code and tests. Everything in §3 onward is
a plan. The same discipline as the rest of the project applies: `measured` means there is a JSON.

---

## 1. Measurement basis

The whole schedule turns on one number — what a solve costs — so it was measured rather than
carried over. All four are the real two-die stack: silicon plus a *powered* photonic array above
it, 500 µm tiles, 50 µm cells, steady, `OMP_NUM_THREADS=1`.

| floorplan | blocks | tiles | unknowns | cold solve | warm solve | ratio |
|---|---|---|---|---|---|---|
| skylake10nm 7-core | 25 | 204 | 192 k | 22.7 s | 0.165 s | 138× |
| skylake7nm 34-core | 1126 | 384 | 366 k | 68.3 s | 0.370 s | 185× |
| skylake7nm 70-core | 2314 | 777 | 708 k | 274.3 s | 0.919 s | 298× |
| skylake7nm 128-core | 4228 | 1378 | 1254 k | 711.8 s | ~2 s *(projected)* | — |

"Cold" is `3D-ICE-Emulator` end to end: parse, assemble, factorise, solve. "Warm" is the
emulator's own post-factorisation solve timer, which is what a persistent `3D-ICE-Server`
session pays per solve. The gap between the two columns *is* the session cache.

The local exponent on cold cost is 1.69, 2.14, 1.67 across the three intervals — it steepens as
the problem leaves cache and then relaxes, which is why `scripts/solver_cost_model.py` fits
log-log across all points and reports a 23% residual instead of claiming one power law.

**The catalogue is 80,330 solves.** Counted from `iter_*` directories under every result directory
`docs/evidence/FINDINGS.json` cites — not estimated. The 157 findings rows resolve to 144 distinct
run directories, because one run yields both an MR-on and an MR-off row; the counts below are
deduplicated and partition the total. By family:

| family | solves | | family | solves |
|---|---|---|---|---|
| clock | 24,591 | | accelerator | 1,328 |
| overnight3 | 17,587 | | core_scaling | 651 |
| margin_curve | 15,093 | | tiers | 383 |
| pitch | 11,161 | | ceiling | 322 |
| cliff | 6,412 | | stacked | 195 |
| rescue_target98 | 2,607 | | **total** | **80,330** |

---

## 2. The arithmetic that sets the ordering

Every one of those 80,330 solves was computed with the cooling in the die's own source layer
instead of in the array above it. They have to be re-run. At 34-core cost:

| | cost |
|---|---|
| re-run cold, one stream | 80,330 × 68.3 s = **63.5 days** |
| re-run warm, one stream | ~40 factorisations (46 min) + 80,330 × 0.37 s = **9.0 hours** |

`[!]` **Superseded 1 Sep 2026 — re-planned against the CURRENT batch scripts (§P0.16).** The
figures above predate the three-arm drivers. `python scripts/catalogue_rerun.py` now reports
**252 points / 578 arms / 64 distinct matrices / ~161,218 solves**, 32.0 h of total compute
(3.2 h factorising + 28.8 h solving) and **6.3 h wall** across 6 concurrent streams. The count
roughly doubled because every planner point emits three arms and the control arm's stack (30 µm
grease) is a *different matrix* from the array arms' (30 µm GaAs). Concurrency is **memory-bound,
not core-bound**: the widest session is 28.8 GB, so ~6 streams fill a 200 GB budget on a 96-core
node. **Quote the 6.3 h wall figure, not 63.5 days — the latter is the cold cost and is what makes
this look like a decision when it is one night.**

The ~40 distinct matrices is the one estimate in that table; everything else is measured. The
matrix is set by stack and floorplan *geometry* — not by power, MR target or kernel — so it is
bounded by the floorplan × sink × pitch × burial-depth combinations the catalogue actually visits.

That is a **169× difference on the critical path** and it is the entire argument for doing the
two-die session cache first. `CODESIGN_PLAN.md` §2 estimates the penalty at 40× and calls it
"hours versus days"; measured, it is 169× end to end — 185× per solve at 34-core, less the
factorisations a warm run still has to pay — and it is *hours versus months*. Nothing else in
Phase 0 changes the schedule by more than a few percent.

node-06 has 96 CPUs and 243 GB. The re-run parallelises by *matrix*, not by point — each stream
holds its own factorisation, so streams must be partitioned so that points sharing a matrix share
a session. Concurrency will be memory-bound rather than core-bound on the large dies, and the
per-session factorisation footprint has not been measured; that measurement is part of P0.1.

**`clock` is 31% of the catalogue on its own**, because `clock_search` bisects and every
candidate clock is a fully leakage-converged solve. Warm-starting each bisection from the
previous sweep point's answer should cut that family severalfold, and it is cheap to do. Worth
taking before the re-run rather than after.

---

## 3. Work items

### P0.1 — Carry two dies through the session cache

**State:** open. Blocks everything else by 169×.

`ICEThermalSolver` refuses `session_cache` together with an MR array at construction
(`HotGauge/HotGauge/thermal/leakage_feedback.py:579`) because the socket takes one flat power
vector across both dies and that element order was never verified. The refusal is correct — a
wrong order would put cooling powers on processor blocks and return a plausible, wrong field.

The root cause is narrower than the refusal suggests: `stack_floorplan_path`
(`ice_server.py:114`) regexes only the **first** `floorplan "…"` in the `.stk`, so
`element_names` (`ice_server.py:463`) only ever sees one die.

**Work.**
1. `stack_floorplans(stack_file)` returning `(die_instance, flp_path)` in stack declaration order.
2. `element_names()` concatenates them **in the order 3D-ICE actually uses on the wire**. Do not
   assume: the `.stk` lists dies top-down (`SINK`, `MR_ARRAY`, `PROCESSOR_DIE`) and 3D-ICE stores
   layers bottom-up internally, so the wire order is plausibly the reverse of the file order.
   Determine it empirically and record which it is.
3. Guard against name collision between tile names and processor block names. `solve_named` keys
   by name; a collision misroutes power silently.
4. `matrix_fingerprint` hashes both floorplans' geometry.
5. Measure the resident set of one factorised session at 34-core and 128-core, so the re-run's
   concurrency can be set from a number instead of a guess.

**Acceptance.**
- A new `test_two_die_server_matches_oneshot_emulator_by_name` agrees to < 1e-3 K with the
  one-shot Emulator, **using a deliberately asymmetric power pattern** — a distinctive spike on
  one MR tile and a different one on one processor block. A near-uniform pattern cannot detect a
  transposed order, and that is exactly how the original power-queue phase bug survived its first
  test (`docs/RESUME_NOTES.md`). The test must be built so a wrong order fails it.
- The 439 existing tests still pass.
- `matrix_fingerprint` changes when either floorplan's geometry changes and does not change when
  powers change.

**Cost.** Half a day to a day. Iteration is on the 7-core stack: 23 s cold, 0.17 s warm.

---

### P0.2 — The planner emits tile powers

**State:** open.

`run_mr_clipping` (`microrefrigeration.py:445`) still builds `{block: −watts}` and applies it via
`apply_cooling_to_trace` (`:272`) — cooling in the die's own source layer, where the extracted
watt crosses no silicon. Only three drivers use the array path today
(`die_average_cooling.py`, `tile_pitch_sweep.py`, `mr_placement_probe.py`), all of them linear
solves on a synthetic uniform power map with no leakage feedback. **Nothing driven by a real
Sniper→McPAT trace has ever run through the array.**

**Work.**
1. Route the plan through `project_plan_to_tiles` (`mr_array.py:153`) into
   `ICEThermalSolver.set_mr_powers`.
2. `run_mr_clipping(..., tiles=None)` keeps the legacy path so retired results stay reproducible.
   Every output JSON records `placement: 'in_source_layer' | 'array_above'`. Without that stamp
   the catalogue becomes ambiguous again the moment the two coexist.
3. **Every run emits three arms, not two.** Under the legacy path `nomr` meant "same stack, no
   cooling", which was clean because there was no array in the stack at all. Once the array is a
   real die layer that is no longer true: a two-arm comparison against a grease stack silently
   credits the laser with the GaAs-versus-grease conductivity gain, and a two-arm comparison
   against the unpowered array silently discards it. The decomposition is exact with three:

   | arm | stack | MR power | isolates |
   |---|---|---|---|
   | `control` | 30 µm `THERMAL_GREASE` (`TIM`) | — | the incumbent part |
   | `array_idle` | 30 µm GaAs pixels | 0 W | the **passive** term — what the array is worth before any light |
   | `array_on` | 30 µm GaAs pixels | budget | the **active** term, measured against `array_idle` |

   `array_idle` and `array_on` share a system matrix, so with P0.1 the third arm costs one warm
   solve — effectively free. Every output JSON records which arm it is; `mr: true/false` is no
   longer sufficient to identify a row. See §6a for why matching the two materials is the wrong
   way to remove the confound.
4. ~~`estimate_sensitivity` must perturb a **tile**.~~ **Superseded 25 Aug 2026.** It should stay
   per-block. The planner's decision variable is watts requested *at a block*; projection onto
   tiles happens downstream, so `dT_block/dW_requested` already includes the projection, the
   burial depth and the tile geometry. A per-tile sensitivity would describe a quantity the
   planner cannot act on.
5. Promote `uniform` and `proportional` to first-class strategies beside `hotspot`
   (`distributed_plan` at `:898` is most of the way there) and add the budget-based selector the
   die-average run measured: targeted below ~7 W, proportional above, on the 7-core die at 100 W.

**Acceptance.**
- With `tiles=None`, one re-run catalogue point reproduces its old numbers bit-identically.
- With tiles, a plan removing *W* watts has tile powers summing to −*W* within 1e-3 — the
  assertion `die_average_cooling.py` already makes on every case.
- **Burial depth stops being inert through the planner.** Driving `mr_placement_probe`'s
  configuration through `run_mr_clipping` reproduces the 67% swing in
  `docs/evidence/mr_placement_burial_depth.json`. This is the real test: it is the property the
  old path was structurally incapable of showing.

---

### P0.3 — Per-tile `dt_max` and `h_max`

**State:** open, decided (per-tile), falls out of P0.2.

`MRParams.dt_max_K` and `h_max_W_per_mm2` bound per *block* today. Moving them to the tile is a
small code change and a real change in what we are asking the device team for — see §6.

**Acceptance.** `envelope_plan` and `clipping_plan` clamp on tile area and tile ΔT; a test that a
fine and a coarse array covering the same die get the same total envelope but different
per-element caps.

---

### P0.4 — Spreader overhang, and the acceptance gate

**State:** open, diagnosed precisely, blocked on a decision. **These are one item, not two.**

`CODESIGN_PLAN.md` §2 lists "spreader overhang" and "acceptance gate to 4/4" as separate rows.
They have the same cause. The gate stands at 1 of 4 and
`HotGauge/HotGauge/thermal/test_published_acceptance.py` records why: every stack layer spans
exactly the die footprint, so there is no lateral relief, and total resistance scales exactly as
1/area (9.08× for 9.08× area — measured, commit c041f0c). On the 826 mm² accelerator that costs
little and the point passes; on a 91 mm² Ryzen die the package alone is 92% of the budget and
the point fails. That *is* "the model does not generalise across die size".

The fix is known and written down (commit 55c4c48). 3D-ICE does have a real spreader, but only on
the pluggable sink model, and upstream refuses steady + pluggable with a bare `//TODO`. Two of the
three obstacles are already fixed in `MXL_3DICE_fixes/files/sources/thermal_data.c`, whose note at
lines 469-497 is the authoritative account. The third: spreader cells have no conductance
to ambient — the plugin contributes heat as a source, never as a matrix coefficient — so in
steady the spreader block is pure Neumann and the matrix is singular. The remedy is to linearise
the plugin *into the matrix*: probe it at two uniform temperatures to recover `g` and `T_ambient`
from `Q = g(T − T_ambient)`, add `g` to the spreader diagonal and `g·T_ambient` to the source.
For a linear plugin that is exact, needs no iteration, and **preserves the factorisation, so the
session cache from P0.1 still works.** It touches `system_matrix.c`.

**Why this must land before the catalogue re-run, not after.** The direct-die stack the catalogue
uses puts a 2 mm `HEATSINK_METAL` slab straight on the array with no overhang — a spreader in
everything but name, denied its lateral relief. If the overhang becomes available generally, every
absolute temperature in the catalogue moves and the re-run has to happen twice. This reorders
§8 of `CODESIGN_PLAN.md`.

There is a legitimate alternative answer: *direct-die photonic cooling has no IHS, so no overhang
is the physically correct model, and only the lidded gate points need the pluggable path.* That
may well be right. It has to be **decided and recorded**, not left implicit, because the catalogue
inherits it either way.

**Acceptance.** `RYZEN_7500F_AIR` and `H100_LIQUID` land inside their published ranges with no
per-point tuning, `H100_AIR` stays inside its range, and `RYZEN_7500F_LIQUID` runs. `EXPECTED` in
the gate test is updated alongside the model — never to make a red test green.

---

### P0.5 — Catalogue re-run

**State:** blocked on P0.1–P0.4.

Runs after, and only after, the four above. 80,330 solves, ~9 h single-stream warm, less with
matrix-partitioned concurrency. Three things to fix in the re-run rather than repeat:

- **20 points currently fail verification** (`FINDINGS.json.summary.failed_verification`) — the
  `spot_*` pitch family, the `margin_T9x` family, `cores128_d1.00`. These do not just get re-run
  at the same settings; they get re-run with the damping the backtracking loop selects and their
  trajectories kept.
- Warm-start the `clock` bisection (§2). 31% of the catalogue.
- Every row stamps `placement`, so this generation of results is distinguishable from the last one
  by inspection rather than by date.

**Acceptance.** `scripts/collect_findings.py` regenerates `FINDINGS.json` with zero rows lacking a
`placement` stamp, and `n_failed_verification` is either zero or each survivor has a recorded
reason.

---

### P0.5b — Rebuild the handbook against the new configuration

**State:** blocked on P0.5. This is the first test set's actual goal, and it is a re-adjudication,
not a re-render.

`docs/HANDBOOK.html` is the project's living reference and every quantitative section in it
predates both the placement fix and the settled geometry in §6. Its figures come from
`examples/handbook_figures.py`, which reads `docs/evidence/`, so the plots follow the re-run
mechanically. The claims do not, and they are the work.

The handbook already carries per-claim status tags — `verified`, `superseded`, `withdrawn`,
`stands; temperatures withdrawn` — and that machinery is what makes this tractable. Every claim
gets re-adjudicated against the re-run and lands in one of four states, with the reason recorded:

* **stands** — reproduces under the array-above geometry, tag retained.
* **strengthened** — the new configuration makes it larger or better founded. The passive term in
  §6a is a candidate: the handbook has no claim at all for "the array is worth 21 K before it is
  switched on", because the old model could not express it.
* **superseded** — the mechanism was right and the conclusion too narrow. This is what happened to
  "MR is weak as a clock enabler", and the same treatment applies wherever the old single-strategy
  planner was the real limit rather than the physics.
* **withdrawn** — does not survive. Struck with the reason stated, never deleted.

Two sections need more than re-adjudication:

* **"Where microrefrigeration pays, and where it does not"** is the handbook's core, and it was
  written when hotspot clipping was the only expressible strategy and cooling sat in the source
  layer. With three arms and four strategies it is a different analysis, not an updated table.
* **"The package was wrong, and so was the place the cooling was applied"** documents the journey
  to the current stack. It now has an ending — §6 — and should say so rather than reading as an
  open investigation.

**Acceptance.** No quantitative claim in the handbook lacks a status tag; every figure regenerates
from `docs/evidence/` with no hand-edited numbers; every retained number carries the `placement`
stamp from P0.5; and the claims that changed are listed explicitly in one place, so a reader who
knew the old handbook can see what moved and why. **Then**, and only then, the CODESIGN_PLAN
claims and next steps get the same treatment — §9's ladder is only worth building on a handbook
whose baseline is honest.

---

### P0.6 — Transient with a modulated array

**State:** open, and correctly last. `ICEThermalSolver` refuses an MR array in transient mode
(`leakage_feedback.py:570`) because it would need a per-slot tile trace, which nothing produces.
Phase 4 also needs a burstier workload trace than we have, and that trace is a prerequisite
rather than a detail. Not scheduled here.

---

## 4. Phase 2 revised: ARM *and* RISC-V

`CODESIGN_PLAN.md` §4 is written for RISC-V alone. Carrying both changes the shape of the phase,
and the in-tree toolchain turns out to be further along than §4 assumes.

**Our Sniper already has ARM and RISC-V decoders.** `snipersim/decoder_lib/` ships
`arm_decoder.cc` and `riscv_decoder.cc` beside `x86_decoder.cc`; they are gated off at build time
by `BUILD_ARM` and `BUILD_RISCV`, which default to 0 only because their dependencies are absent
(`snipersim/Makefile.config:31-41`). `libdecoder.a` currently contains `x86_decoder.o` alone.
`make capstone` downloads and builds the ARM dependency automatically; RISC-V wants `rv8` at
`$(SIM_ROOT)/../rv8`, for which there is no download rule, so that one is a manual build. Both
decoders are *additive to an x86 build* — the Makefile's own banner reads "Building for x86 …
and RISCV … and arm64".

So the §4 assumption that a second ISA means adopting gem5 and writing an activity→power
converter is not right for this tree. The decoders are a build exercise.

**The real blocker is the frontend, not the model.** Sniper's SDE/Pin frontend is x86-only.
Non-x86 instruction streams come from one of the other two in-tree frontends:
`frontend/dr-frontend/` (DynamoRIO — auto-downloaded and built by `make dynamorio`) or
`frontend/qsim-frontend/` (QSim, QEMU-based). DynamoRIO instruments **native** execution, and
phonon is x86_64 throughout — `sinfo` shows skylake and V100/P40 nodes and nothing else — so
DynamoRIO cannot produce ARM or RISC-V traces here without a machine to run them on. QSim
emulates, which is why it is the interesting one, and it is already wired to a `FrontendISA`
parameter. **Scoping the QSim frontend is the first Phase 2(b) task**, and it should happen before
any commitment to gem5.

**McPAT is less ISA-specific than §4 implies.** McPAT's area and power model is structural — issue
width, register file entries, cache geometry, ALU counts — and the ISA barely enters it. The
exception is precisely decode and the µop cache, which McPAT models thinly or not at all. That is
convenient for getting a RISC-V or ARM core into the existing pipeline and inconvenient for the
one hypothesis §4 wants to test; see below.

Where the two ISAs genuinely differ is in the **highest-fidelity area evidence**, and there they
are complementary rather than redundant:

| | x86 *(have)* | ARM | RISC-V |
|---|---|---|---|
| decoder in our Sniper | built | present, needs `make capstone` | present, needs a manual rv8 build |
| trace frontend on an x86 host | SDE, working | QSim (in tree, unscoped) | QSim (in tree, unscoped) |
| power model | McPAT, calibrated here | McPAT, structural — fine given µarch parameters | same |
| highest-fidelity area | annotated die shots | annotated die shots — **the only route**; no open high-performance Arm RTL exists | open RTL: XiangShan, SonicBOOM, CVA6 → synthesis |
| `CODESIGN_PLAN.md` route (c) available | n/a | **no** | **yes** |

That last row is the argument for doing both rather than a cost of it. **ARM** asks whether the
design rules survive on a floorplan we did not derive ourselves. **RISC-V** is the only one of the
three where we can produce areas a vendor cannot argue with. Neither substitutes for the other,
and the licensable claim in `CODESIGN_PLAN.md` §7 needs the second kind.

Route (a) — re-weighting `examples/floorplans/14nm_unit_areas.json` and reusing the
`make_processor` tiler, which `examples/generate_ncore_floorplans.py` establishes is neither
core-count nor ISA specific — is cheap for both and unblocks Phase 1 across three ISAs without
touching Sniper at all. `HotGauge/HotGauge/thermal/accelerator_floorplan.py` is the pattern to
copy: measured areas, provenance in the module docstring, an explicit assumed/measured split, and
a coverage check that refuses a floorplan whose blocks do not account for the die.

### A correction to the §4 hypothesis, before it is tested

§4 hypothesises that RISC-V cores are more thermally concentrated than x86 "because less of the
die is spent on decode". **The area model this project actually uses does not support the premise.**
In `14nm_unit_areas.json`, against a 5.183 mm² core:

| unit | mm² | share |
|---|---|---|
| Execution Unit | 1.076 | 20.8% |
| Load Store Unit | 0.745 | 14.4% |
| — of which D-cache | 0.655 | 12.6% |
| Instruction Fetch Unit | 0.629 | 12.1% |
| — of which I-cache | 0.375 | 7.2% |
| L2 | 0.524 | 10.1% |
| Floating Point Units | 0.451 | 8.7% |
| **Instruction Decoder** | **0.173** | **3.3%** |
| Renaming Unit | 0.036 | 0.7% |

Decode is 3.3% of core area and McPAT models no µop cache at all. A route-(a) study built on this
JSON cannot express a decode-driven difference larger than a few percent of core area — well
inside the noise of everything else in the pipeline — so it would return "no difference" for a
reason that has nothing to do with the ISAs.

Two honest options: restate the hypothesis around units the model does represent — vector/SIMD
width and the execute cluster (AVX-512 is already a `DERIVED_UNIT`), the LSU, the private cache
split — or obtain an area source that represents the front end properly, which pushes ARM toward
die shots and RISC-V toward synthesis immediately rather than later. The vector-width framing is
the stronger one anyway: the FPU/AVX block is 8.7% of core area *and* it is where the power
density actually is, which is what the array responds to. Recommend restating before running.

---

## 5. Ordering, revised

1. **P0.1** two-die session cache — 169×, and everything downstream is priced by it
2. **P0.4** spreader decision and the gate — must precede the re-run or the re-run happens twice
3. **P0.2 / P0.3** planner tile powers, per-tile device limits
4. **P0.5** catalogue re-run — ~9 h warm, one overnight
5. **P0.5b** rebuild the handbook and re-adjudicate every claim against it — the first test set's goal
6. **Phase 1** metrics regression on the existing x86 floorplans
7. **Phase 3 clustering experiment** — cheapest, most likely to overturn a convention
8. **Phase 2(a)** ARM and RISC-V floorplans, hypothesis restated per §4
9. Phase 4 and Phase 2(c) as `CODESIGN_PLAN.md` has them

All of it is a route to `CODESIGN_PLAN.md` §9 — the generational ladder of floorplans, each
defined by the bottleneck the previous one exposed, run identically across the three ISAs. That
section also names the one prerequisite that blocks the ladder's first rung and is nobody's
current job: **the V/F table stops at 5.0 GHz**, and a study of whether LCMR buys 6 GHz cannot be
run on it.

Two items run **off the critical path** and can start at any time, because neither touches the
solver or the catalogue:

- **Phase 2(a) floorplans.** Route (a) is a JSON re-weighting plus the existing tiler. It needs no
  Sniper build, no 3D-ICE run, and no node-06 time.
- **Scoping the QSim frontend** (§4). This decides whether Phase 2(b) is a build exercise inside
  the pipeline we already trust or a gem5 adoption, and the answer changes the cost of the whole
  phase by a large factor. Worth knowing early even though it is needed late.

The change against `CODESIGN_PLAN.md` §8 is that the acceptance gate moves from last to second.
It is not a presentation concern; it is an input to every number the re-run produces.

---

## 6. The device, as settled

**Answered 25 August 2026, and now pinned in code and tests rather than assumed.**

The extraction is **never co-located with the transistors**. It is always at the interface between
the top of the die and the sink above it, because that is how the part attaches to a real chip: a
cold plate mounted on top of a direct-die package. Integrating the array into the die itself may
get investigated later; it is not what is being built.

What that fixes:

| | setting |
|---|---|
| array position | second die element directly above the silicon, in the place the thermal grease occupied |
| array thickness | 30 µm, the same as the grease it replaces |
| everything above it | identical in both arms — same SINK, fan and cold plate |
| convection control | the same stack with 30 µm of `THERMAL_GREASE` (`TIM`) instead of the array |
| active-layer depth | **200 µm** below the cooled surface by default, and a free parameter so die thinning can be swept |
| active-layer depth when comparing | the same in both arms, always |

`HotGauge/HotGauge/thermal/die_stack.py` carries this as its per-package defaults —
`DEFAULT_DIRECT_SOURCE_DEPTH_UM = 200.0`, `DEFAULT_DIRECT_DIE_UM = 240.0` — with the historical
400/360 lidded pair untouched so `skylake.stk` still reproduces. Five tests in
`test_die_stack.py::TestTheDeviceAsItIsBuilt` assert the invariants directly, including that the
two arms differ in **exactly one layer** and that burial depth stays sweepable.

The co-located arrangement survives only as an explicit upper bound
(`examples/mr_placement_probe.py`, `where='source'`). Its numbers are not device numbers and must
not be quoted as such.

### What this changes elsewhere

`CODESIGN_PLAN.md` §1 says burial depth "is a spec a vendor must agree to, and it is the first item
on any term sheet". That stands, and is now stronger: with the array above the silicon, the 360 →
20 µm sweep moved what a fixed 3 W buys by 67%, and there is no co-located escape from it.

`CODESIGN_PLAN.md` §0's collection-efficiency constraint is unaffected and remains the open
packaging question — it moves effective COP from 3.55 to 1.24 and is a property of optical path
geometry, so it is still a floorplan constraint that needs a number, or at least a floor.

The one device datum still outstanding: **what does `dt_max` bound — a tile or a block?** P0.3
moves it to the tile because that is what the array physically is. If the device datum is per-tile
ΔT against local ambient and `h_max` is per tile area, the change is exact.

## 6a. Pixel-layer conductivity: a design variable, not a confound

**Measured 25 August 2026** — `docs/evidence/pixel_conductivity.json`. Two runs of
`examples/die_average_cooling.py` differing only in `mr_material`: `GAAS` at 55 W/(m K), the device
as built, and `THERMAL_GREASE` at 4, a counterfactual array with the incumbent TIM's conductivity.
Same stack, same 200 µm burial, same tiles, same plans, same hottest block. Linear solves on a
uniform synthetic 100 W map, so conductivity and geometry only.

The question was whether matching the two would cleanly separate the laser-cooling gain from the
interface-conductivity gain. It does not, because the two are coupled — and the coupling runs the
opposite way to intuition.

**A low-conductivity pixel layer extracts more peak reduction per watt removed**, consistently:

| strategy | Δpeak, GaAs | Δpeak, k-matched | active-term ratio |
|---|---|---|---|
| proportional, 30 W | −12.35 K | −15.36 K | 1.24× |
| uniform, 30 W | −9.52 K | −11.48 K | 1.21× |
| hotspot, 30 W | −7.04 K | −9.73 K | 1.38× |
| top5, 10 W | −4.19 K | −6.73 K | 1.61× |

The mechanism: a high-k pixel layer is nearly isothermal and well coupled to the sink, so a
negative source placed in it is partly satisfied by drawing heat *from the sink* rather than from
the die. A low-k layer localises the extraction over the silicon. The two linear strategies show a
perfectly constant ratio (1.21 and 1.24 across a 10× budget range), which is what a pure coupling
effect should do.

**But the device still wins decisively, and by more than it gives up.** At 30 W proportional:

| | peak | vs convection control |
|---|---|---|
| convection control (grease, no cooling) | 101.73 °C | — |
| GaAs array, unpowered | 80.36 °C | **−21.38 K** *(passive)* |
| GaAs array, 30 W | 68.01 °C | **−33.72 K** *(−12.35 K active)* |
| k-matched array, 30 W | 86.37 °C | −15.36 K |

The real device is **18.4 K better in absolute terms** and delivers 2.2× the total benefit, because
the 21.4 K passive term dwarfs the 24% it concedes on the active term.

**So matching the materials would make the laser-cooling number look 24% better while making the
part 18 K worse.** That is the wrong trade to optimise, and it is the reason not to adopt it as the
default. The confound is better removed by the three-arm decomposition in P0.2, which measures the
laser term against the *unpowered array* and never models a device nobody is building.

What the experiment did establish is more useful than a control: **pixel-layer conductivity is a
co-design variable with a genuine optimum.** It trades the passive path against active coupling in
opposite directions, and neither end is best. `MR_PIXEL_MATERIALS` already offers GaAs (55),
Si₃N₄ (30) and grease (4), so the sweep is a one-flag experiment — and it belongs in Phase 1's
design rules, since the answer will depend on burial depth, tile pitch and how targeted the plan
is. It is also a question for the device team, since the host material is theirs to choose.

---

### Burial depth moves the two arms in opposite directions

Solving both arms at zero MR power at two burial depths — same 7-core die, 100 W, uniform
synthetic map, linear:

| burial | array arm (GaAs) | convection control (grease) |
|---|---|---|
| 200 µm | 80.36 °C | 101.73 °C |
| 137 µm | 79.07 °C | 101.84 °C |

Thinning gains the array arm 1.3 K and *costs* the control 0.1 K. That is consistent with the
grease dominating the control's series path, so that thinning it only removes lateral spreading
and buys nothing back — whereas for the array the silicon is a real part of the path.

If it holds under a real power map it is a design rule with commercial weight: **die thinning is
worth paying for only if the cooler is good enough to see it.** A vendor thinning a die for a
conventional TIM is spending money for nothing. Uniform synthetic map, no leakage feedback, two
points — an observation to redo properly once P0.2 lands, not a result.

---

## 7. What could invalidate this schedule

- **Element order on the wire turns out not to be a fixed concatenation.** If 3D-ICE interleaves
  or orders by something other than declaration, P0.1 grows from a day to a socket-protocol
  change. The asymmetric-power test tells us on day one, which is why it is the first thing built.
- **The spreader linearisation is not exact for the plugin we need.** It is exact for a linear
  plugin; a temperature-dependent coolant boundary is not linear, and then it needs the fixed
  point that commit 55c4c48 already built, which costs the factorisation reuse the session cache
  depends on. That would make P0.4 and P0.1 pull against each other.
- **Re-run concurrency is memory-bound lower than expected.** 243 GB across streams that each hold
  a factorisation; unmeasured until P0.1. Would stretch the re-run from one night to several.
- **QSim cannot deliver ARM or RISC-V traces on an x86 host.** Then Phase 2(b) falls back to gem5
  plus a converter — roughly what `CODESIGN_PLAN.md` §4 already budgets, so this is a risk to the
  saving rather than to the plan. Scoping it early is what keeps it that way.
- **The re-run moves a headline result.** It should be assumed it will — the placement change is
  not a refinement, it puts the extracted watt on the far side of the silicon. Anything quoted
  externally between now and P0.5 should carry the `in_source_layer` caveat explicitly.
