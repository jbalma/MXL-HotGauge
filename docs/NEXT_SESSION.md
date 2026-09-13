# 13 September 2026 — the user's four points on the memo (§P0.29, §P0.30)

1. **The dark-silicon "runaway" at 1.20 / 25 % was an unfinished six-iteration planner descent**
   (peak 94.4 °C, 0.7 W, `diverged: False`); it holds for 0.8 W at 12 iterations. The pack figure
   now paints such rows "unfinished", not "runaway". **The seed envelope shape over-spent the
   whole F2 ladder**: under `--mr-envelope-shape power` 17.3 → 11.6 W at 1.2 / 100 %, 64.2 → 44.1 W
   at 1.5 / 100 %, 48.7 → 4.1 W at 1.5 / 25 % (register §1.3 row and §2 withdrawal;
   `dark_silicon_report.py --override results/dark_silicon_v2/power results/dark_silicon_v2/iter12`
   regenerates the evidence). **§P0.29 P5–P7 (done, `results/array_coverage_armD_power/`)**: the rescue ladder's plans fall
   18–33 % under the per-block shape and the ladder ends on conservation at **3.50 W/mm² (s = 0.99),
   not 2.40**; 4.00 is bistable. The register carries both shapes; the anchor stays the seed-shape
   138.73 W (the default shape is unchanged) with a second, per-block anchor at 2.00: 113.6 W / 91.5 °C.
2. **The cooling-system ledger (§P0.30, `examples/cooling_system_ledger.py`)**: refrigerated air needs
   273 / 243 / none / none K ambient at 1.20 / 1.60 / 2.00 / 2.40; the 0.125 K/W liquid plate 293 /
   273 / 263 / 243 K; system COP air 1.65 / 0.52 / – / –, liquid 17.3 / 3.94 / 3.02 / 0.97,
   photonic 2.59 / 1.90 / 1.58 / 1.29. The laser beats air at every rung and is the only solution
   above 1.60; it beats the chilled plate only where the coolant goes sub-zero (2.40 here). The
   provisional's "> 10× COP" is the air statement. Open: pump flow³ scaling, condensation, the
   laser's LPC waste heat on the fan, a fan-speed sweep on the air side.
3. **The plan, agreed by the user on 13 Sep for the next session (see `NEXT_SESSION_PROMPT.md`), in
   order: (1) the generalized f_max; (2) the 8× / 16× cluster ladder at 20 µm and 5 µm burial; (3)
   the CoMeT IPC(f) reader; (4) the D1 family and the accelerator re-run under the per-block shape.
   Earlier note on what each needs:** a generalized f_max(V, T |
   logic depth, wire, skew) with V_max from an Arrhenius reliability budget (the clock search's
   4.17 GHz ceiling is an assumed 10 % overdrive on a saturating I_on(V)/V, re-anchored at every
   temperature so I_on(T) never reaches the clock); the 8× / 16× cluster ladder at 20 µm and 5 µm
   burial (1000 W/mm² functional units need the extractor within microns: ΔT ≈ q·d/k); a reader
   for CoMeT's 1–20 GHz run_N outputs to get IPC(f) per benchmark
   (`/mnt/nfs01/scratch/jbalma/CoMeT/test/thermal_example_test_1to20ghz/`).

---

# 12 September 2026 — the MXL-006 patent update memo (§P0.28)

The user asked for an update memo for patent counsel on MXL-006 (the provisional filed 13 Oct
2025, "Chip Architectures Enabled by Integrated Photonic Cooling"), reviewing the filing against
v100 Part VI and the HotGauge record. Delivered in `docs/photonic_cooling/MXL-006-PRO/Update/`:
`MXL-006_update_memo.md` (+ `.docx` / `.html`), `figures/` (the evolution schematics by degree of
integration and by ladder generation, the scale ladder, the evidence matrix, the evidence figures
from the pack, the integration-ladder figure), `results/` (the evidence JSONs + the register),
`README.md`. The memo's discipline is the register's: every number MEASURED / ARGUED / WITHDRAWN.
Its headline recommendations: build the independent claims on the driven, planner-commanded array
(the rescue as a DIFFERENCE from an undriven layer of the same film), the densified cluster with
re-sized rails, feed-forward burst absorption from the power monitor, clock to the device V/F
ceiling, dark-silicon recovery, and the storage die OFF the heat path; drop the filing's
> 1000 W/mm² / > 10 GHz / > 10¹¹ cm⁻² / 160 °C / > 10× COP / > 30 % recovery / branch-predictor
modulation numbers (not supported or contradicted). **§P0.28, the integration ladder** (burial
200 → 20 µm × pitch 500 / 200 µm, 100 µm grid, `scripts/integration_ladder.sh`,
`examples/integration_ladder_report.py` → `docs/evidence/integration_ladder.json`) was run for
the memo: see §P0.28 RESULT — thinning the die does NOT make the rescue cheaper.

Files to stage from this: `docs/photonic_cooling/MXL-006-PRO/Update/` (memo, figures, scripts,
README; the `results/` copies are duplicates of `docs/evidence/` and may be left out),
`scripts/integration_ladder.sh`, `examples/integration_ladder_report.py`,
`docs/evidence/integration_ladder.json`, `docs/PHASE0_CHECKLIST.md`, `docs/RESULTS_REGISTER.md`,
`scripts/build_results_registers.py`, this file.

---

# Next session — handoff, 11 September 2026 (§P0.25 closed, §P0.27: X1–X4 done; gen 3 as argued falsified)

Read `docs/START_HERE.md`, then `docs/NEXT_SESSION_PROMPT.md` (rewritten 11 Sep), then
`docs/PHASE0_CHECKLIST.md` §P0.27 (X1/X2 RESULT, X3 predictions, X4 scope), `docs/RESULTS_REGISTER.md`
(three new §1.3 rows: burst, X1, X2; two §3 items; one §4 constraint), `docs/designs/EVOLUTION_LADDER.md`
§2.3 (new), `CLAUDE.md`. Slurm: job **1507** on node-06. `[!]` **Nothing runs on the head node**
(user, 11 Sep) — solves, the test suite AND pack/register builds all go through the campaign
server (`results/campaign_queue/<name>.par<N>.tsv`). Baseline: **1080 passed, 1 skipped** (11 Sep, on the node, after the storage-die tests; 1075 before X4).

## What landed 11 Sep

- **§P0.25 closed (F4, burst absorption, six points):** the modulated array cuts the overshoot per
  added watt from 0.51–0.67 K/W (package) to 0.17–0.20 (2.5–3.3×); at 0.80 W/mm² it holds a 2×
  burst under the target and a 3× burst 1 K under the spec; at 1.00 (3 K of margin) it crosses
  the target at every k and the spec at k ≥ 2; the static array RUNS AWAY inside the window at
  1.00 / 3× (P5 falsified for that arm); two rows are non-viable (> 127 °C). `[!]` The burst plan
  asks up to **13 W/mm² of one tile for 10 ms** — the first demand above the steady ~5 W/mm² rule
  (register §4 amended). Register §1.3 row, `results-quotable/17-burst-absorption/`, pack figure.
- **§P0.27 X1/X2 (the recorded fields, no new coupled solve):** the solve trees hold every
  iteration's POWER map and no temperature field, so `examples/field_resolve.py` re-solves the
  recorded final map once through the session (34 fields, `results/fields/`, peaks reproduced to
  ±0.000 K — P0). `[!]` The last `itNN` of an `array_on` tree is the bisection's largest FAILING
  plan; the pass is selected by the row's `heat_removed_W`. `examples/pdn_em_skew_report.py` →
  `docs/evidence/pdn_em_skew.json`: **the rescue ladder is a current ladder** (die current 1.29 /
  1.54 / 2.00 / 2.45 / 2.88× native at 1.00–2.40 W/mm², 0.70 V; peak block within 3–7 % of the
  die-average); **the ×0.5 cluster's cALU carries exactly 2.00× the reference's current density at
  matched watts** (×0.25: 3.9×) because the array clips both to 92 °C; F1c laser rows 1.50× / 1.78×
  (SPICE) and 1.60× (table, the voltage does the work); Black's law (n = 2, 0.9 eV stated): the
  cooled die's worst block ages 12–50× faster than the native die's along the ladder, the
  cooling dividend at matched power is 2.4× (1.10), and on the F1c SPICE rows the cooled design's
  worst block outlives the control's 2.7–3.2× at +14–26 % clock (on the table it ages 2.2× faster).
  **Thermal skew grows with the rung** (core-domain 24 → 32–60 K; 3.2 → 7.9 % of the period at a
  stated 150 ps): uniformity buys 0.74 % at matched power and the laser field is the less uniform
  one at matched density (**P6 falsified**). Gen 1's "what binds next" is rewritten: **the PDN,
  unless the rails are re-sized ~J×** — MEASURED as J, ARGUED as a limit (register §3: no rail
  model). `results-quotable/18-pdn-em-skew/`, pack figure `pdn_em_skew.png`.
- **§P0.27.3 X3 done** (`results/x3_u70/`, 36 jobs at 100 µm, ~1 h):
  `generate_exec_density_family.py --utilisation 0.70 --overhead 0.15 --cache-halo-um 20 --tag u70`
  (logic × 1.643; a 20 µm ring on the PLACED macro; a sub-100 µm² parent leftover is zeroed or a
  spurious 34-block `iSched` family appears carrying the scheduler's power — found and fixed; the
  default path is byte-identical). Members 137.7 mm² (1.36×, the utilisation control) and
  121.5 mm² (1.20×, the cluster 1.22× denser in silicon) — **P9 falsified low**. `[!]` 100 µm cells
  with the reference re-run on the same grid (its plans are 8–50 % below the 50 µm ones; its
  control cliff is unchanged): the ×0.5-at-70 % member holds all five rungs to 243 W, 0 tiles
  capped; plan 0.75 / 0.85 / 0.90× the reference's and **1.44 / 1.22 / 1.16× the utilisation
  control's** at 162 / 202 / 243 W (9.8× at the 121 W hot-spot rung); the passive cliff scales
  with the cluster's density, not the die area (utilisation alone 60.7 → 70.8 W; with the cluster
  back to 60.7). Register §1.3 row, `results-quotable/19-dense-cluster-utilisation/`, ladder §2.4.
- **§P0.27.4 X4 built and measured the same afternoon — gen 3 as argued is FALSIFIED.**
  Built: `die_stack.StackSpec(storage_um, bond_um, bond_k_si)` (spec keys `storage`, `bond`,
  `bondk`; a third powered die `STORAGE_DIE` with `{storage_flp_file}`), `ICESim.fill_storage_flp_template`
  (filled from the same trace by name), `ICEThermalSolver(storage_flp_template=)` (adds the
  storage die's Tflp), `examples/split_storage_die.py` → `examples/floorplans/outputs/gen3_stack/`
  (68 L2/L3 blocks to the storage die; dark on the compute die), `mr_comparison.py --gen3-split
  --storage-um --bond-um --bond-k`, `scripts/gen3_stack_ladder.sh`, `examples/gen3_stack_report.py`,
  five tests in `test_die_stack.py::TestStorageDie`. **Anchor reproduced exactly** after the
  edits (138.72881 W / 93.8752 °C). Measured (`results/gen3_stack/`, 17 points, 100 µm): with the
  storage die between the compute die and the sink, the 280 K objective costs **99.3 W (s = 1.08)
  at every bond from 120 to 5 W/mK** (monolithic: 99.4), zone 289 K, cache leakage 3.6× down for
  66 W net; Cr:LiSAF 73.7 W with 58 tiles capped; at 0.5 W/mK the unpowered array diverges and
  nothing holds; the compute die under the hot-spot objective at 2.00 is the reference's (−3.4 %).
  P14–P16 falsified, P17–P18 confirmed. Register §1.2 row + a §2 withdrawal, ladder §4.3,
  `results-quotable/20-gen3-stack/`. **The surviving design is ARGUED: the storage die off the
  compute die's heat path (2.5D beside it, or the far face with two sinks).**

## Still open, in order

1. **The surviving gen-3 geometry** (§P0.27.4, ladder §4.3): a stack with the storage die OFF the
   compute die's heat path — the compute die's sink and dye array on one face, the storage die
   (Cr:LiSAF tiles) on the other, i.e. a two-sink `StackSpec` (or a 2.5D side-by-side floorplan on
   one die footprint with an isolating channel). Predictions first; the anchor after any stack edit.
2. A rail model (register §3) so "binds: PDN" becomes a `V_eff` in the clock search.
3. D2 (the `V_t` lever end to end); Phase 2 (second workload class).

## Files this session touched — list for staging (never `git add .`)

New: `examples/field_resolve.py`, `examples/pdn_em_skew_report.py`, `examples/x3_utilisation_report.py`, `examples/split_storage_die.py`, `examples/gen3_stack_report.py`, `scripts/gen3_stack_ladder.sh`, `examples/floorplans/outputs/gen3_stack/`, `docs/evidence/gen3_stack.json`, `results-quotable/20-gen3-stack/`,
`scripts/x1_fields_queue.py`, `scripts/x3_utilisation_ladder.sh`, `docs/evidence/pdn_em_skew.json`,
`docs/evidence/d1_exec_density_family_u70.json`, `docs/evidence/x3_utilisation.json`, `examples/floorplans/outputs/d1_exec1_u70/`, `examples/floorplans/outputs/d1_exec0.5_u70/`,
`results-quotable/17-burst-absorption/`, `results-quotable/18-pdn-em-skew/`, `results-quotable/19-dense-cluster-utilisation/` (+ regenerated manifests),
`proposal_pack_2026-09-11/` (+ `.zip`; generated, not for staging).
Modified: `HotGauge/HotGauge/thermal/die_stack.py`, `HotGauge/HotGauge/thermal/ICE.py`, `HotGauge/HotGauge/thermal/leakage_feedback.py`, `HotGauge/HotGauge/thermal/test_die_stack.py`, `examples/mr_comparison.py`, `examples/generate_exec_density_family.py`, `scripts/build_results_registers.py`, `docs/METHODS.md`, `docs/START_HERE.md`, `docs/ARCHITECTURE_EVOLUTION.md`,
`scripts/build_proposal_pack.py`, `docs/evidence/burst_absorption.json`, `docs/PHASE0_CHECKLIST.md`,
`docs/RESULTS_REGISTER.md`, `docs/FUTURE_EXPERIMENTS.md`, `docs/PHYSICAL_DESIGN_CONSTRAINTS.md`,
`docs/designs/EVOLUTION_LADDER.md`, `docs/designs/gen1_dense_cluster.md`, `docs/NEXT_SESSION_PROMPT.md`,
this file. `results/` trees are gitignored.

---

# Next session — handoff, 9 September 2026 (§P0.22, the architecture-evolution phase)

Read `docs/START_HERE.md`, then **`docs/designs/EVOLUTION_LADDER.md`** (the deliverable), then
`docs/PHASE0_CHECKLIST.md` §P0.22 (predictions and RESULT subsections), `docs/RESULTS_REGISTER.md`
(§0 flag table, the new §1.2/§1.3 rows, §3), `CLAUDE.md`. Slurm: job **1507** on node-06.
`[!]` **One step at a time** — a step takes the whole job (CPUs/Task=96); campaigns go through
`scripts/campaign_server.sh` (`results/campaign_queue/<name>.par<N>.tsv`), `on_node.sh` hangs
while it runs, `ssh node-06-8xv100` works for `free`/`ps`. Baseline: **1070 passed, 1 skipped** (head node, 6 min, 9 Sep; 1054 before §P0.22).

## What landed 9 Sep

- **`docs/designs/EVOLUTION_LADDER.md`** — the argued ladder in v100's §1.18/§10.9 frame, every
  claim tagged MEASURED/ARGUED; the `s` ladder read against (1.33); design records
  `gen1_dense_cluster.md`, `gen3_cache_objective.md`; floorplan figures under `docs/designs/figures/`.
- **D3, the cache-leakage planner objective** — built (`--mr-objective cache-leakage`,
  `MRParams(zone_targets)`, `objective_peak`, `thermal/leakage_ledger.py`, 16 tests) and measured
  on the monolithic die: the cache knee (280 K) is **conservation-bound**, 300 K costs **≥ 77 %
  of die power**, cache leakage 2.7×/3.6× down, Cr:LiSAF tiles fail by load (§P0.22.2 RESULT,
  `docs/evidence/d3_cache_objective.json`, `results-quotable/10-cache-leakage-objective/`).
- **D1, the dense-execution-cluster family** — `examples/generate_exec_density_family.py`
  (×0.5, ×0.25 execution-unit area, slab invariant), `scripts/d1_family_ladder.sh`, running at
  matched watts; `examples/d1_family_report.py` scores §P0.22.3.
- **D4, the 70-core falsification ladder** — at 100 µm cells with a matched-grid 34-core
  control (`scripts/uniform_density_ladder_d4.sh`, `examples/d4_falsification_report.py`); the
  grid control confirmed (P1), the 70-core rows landing.
- **Infrastructure:** `scripts/campaign_server.sh`; `METHODS.md` §2.2 rewritten (the one-step
  reality), §4.2a (objective + ledger); `REFERENCES.md` §1 cites v100 Ch. 9 for the array geometry
  and says the 45 K lift is *not* in v100 (Draft_5 stays).

## Still open, in order

`[+]` **10 Sep, done:** F1b (the 70-core with the array) and F2 (dark-silicon recovery) ran
and are recorded — §P0.23 RESULT, register §1.3 (two rows) and §4 (the two control ceilings),
`results-quotable/13-…, 14-…`, `FUTURE_EXPERIMENTS.md`. Two predictions falsified (the big
die's laser ceiling: 301 W, not 390–470; the native die lights unaided — the probe's ceiling is
not the driver's). **F3, the accelerator:** part 1 is recorded (§P0.24 RESULT: the control runs away at 700 W on
the simulated curve; the seed envelope shape fails every kernel point); part 2 (power shape) is recorded (§P0.24 part 2: holds to 2600 W, tile flux ≤ 5.3 W/mm², all
rows unconverged on the 0.05 K residual); part 3 (`--tol 1.0 --max-iter 100`) is **done and recorded** (§P0.24 part 3, register §1.3 and §4,
`results-quotable/16-accelerator-microchannel/`, the pack's accelerator figure). **F1c (clock as the free variable, §P0.26) is done and recorded** (register §1.3,
`results-quotable/15-clock-as-free-variable/`, the pack's clock figure): at 1.00 W/mm² the laser
runs the die at the device ceiling, +14 %; +26 % at 1.20; +34 % on the shipped table. The
proxy caveat is closed: quote clocks with their W/mm² operating point and V/F source. **The full F4 burst ladder is running** (`results/burst/`, `examples/burst_report.py`). **F4 is built** (§P0.25; the array in transient mode, the burst driver) and its smoke point
`results/burst/d0.80/k2.0` is running; if it lands, queue `scripts/burst_ladder.sh` (6 points)
and read back with `examples/burst_report.py`. Next after that: F5 (the two-die stack). The campaign server is
still up; `touch results/campaign_queue/STOP` when nothing is queued.

`[+]` **10 Sep:** the six future experiments are recorded and ranked in
`docs/FUTURE_EXPERIMENTS.md` (iso-package throughput and the 70-core array ladder first, then
dark-silicon recovery); the net-export energy story is reserved for the post-evolution
ISA-classed designs (user's decision). Items 1–5 below stand.

1. **Read D1 and D4 back** if they were still running when this was written:
   `python examples/d1_family_report.py`, `python examples/d4_falsification_report.py`; score
   §P0.22.1/§P0.22.3, update the ladder's §6/§7 scorecard and `ARCHITECTURE_EVOLUTION.md` §5's
   last row (it flips only when D1's rows are in).
2. **D2** — the `V_t` lever end to end at 25 mV (never run).
3. **The two-die solve** for gen 3 (`stacked_memory_study.py --cell-um 100`, ported to the array
   stack) — the measurement that would turn the gen-3 design from ARGUED to MEASURED.
4. **Planner shape/mode** (§P0.19) and the envelope-path minimum for the cache objective (the
   baseline path reports lower bounds).
5. Phase 2 as planned (second workload class).

## Also new on 10 Sep (staging list, in addition to the 9 Sep list below)

`docs/PHYSICAL_DESIGN_CONSTRAINTS.md`, `docs/NEXT_SESSION_PROMPT.md` (rewritten),
`docs/FUTURE_EXPERIMENTS.md`; scripts: `scripts/iso_package_70core_ladder.sh`,
`scripts/dark_silicon_ladder.sh`, `scripts/accel_f3_ladder.sh`, `scripts/burst_ladder.sh`,
`scripts/clock_f1c.sh`, `scripts/clock_f1c_density.sh`; drivers: `examples/burst_absorption_study.py`
(new), `examples/accelerator_study.py`, `examples/clock_headroom.py`, `examples/mr_comparison.py`
(flags); reports: `examples/iso_package_throughput_report.py`, `examples/dark_silicon_report.py`,
`examples/accel_f3_report.py`, `examples/burst_report.py`, `examples/clock_f1c_report.py`;
library: `HotGauge/HotGauge/thermal/microrefrigeration.py` (envelope shape), `leakage_feedback.py`
and `mr_array.py` (transient array), tests in `test_mr_wiring.py`, `test_mr_array.py`,
`test_mr_objective.py`; evidence: `docs/evidence/{iso_package_throughput,dark_silicon,accel_f3,
accel_f3_power,accel_f3_power_tol1,clock_f1c,clock_f1c_density,burst_absorption}.json`;
`results-quotable/13-…16-…`; `scripts/build_proposal_pack.py` and `scripts/build_results_registers.py`.

## Files this session touched — list for staging (never `git add .`)

New: `docs/designs/EVOLUTION_LADDER.md`, `docs/designs/gen1_dense_cluster.md`,
`docs/designs/gen3_cache_objective.md`, `docs/designs/figures/` (3 × `floorplan_34core.png` +
`density_summary.json`), `HotGauge/HotGauge/thermal/leakage_ledger.py`,
`HotGauge/HotGauge/thermal/test_mr_objective.py`, `examples/generate_exec_density_family.py`,
`examples/d3_objective_report.py`, `examples/d4_falsification_report.py`,
`examples/d1_family_report.py`, `scripts/build_proposal_pack.py` (→ `proposal_pack_<date>/` + `.zip`, generated, not for staging), `examples/floorplans/outputs/d1_exec0.5/`,
`examples/floorplans/outputs/d1_exec0.25/`, `scripts/campaign_server.sh`,
`scripts/uniform_density_ladder_d4.sh`, `scripts/d3_objective_smoke.sh`,
`scripts/d1_family_ladder.sh`, `docs/evidence/d3_cache_objective.json`,
`docs/evidence/d1_exec_density_family.json`, `docs/evidence/d4_falsification_70core.json`,
`docs/evidence/d1_exec_density_family_result.json`, `results-quotable/10-cache-leakage-objective/`
(+ regenerated manifests).
Modified: `HotGauge/HotGauge/thermal/microrefrigeration.py`, `examples/mr_comparison.py`,
`scripts/build_results_registers.py`, `CLAUDE.md`, `docs/START_HERE.md`, `docs/PHASE0_CHECKLIST.md`,
`docs/RESULTS_REGISTER.md`, `docs/METHODS.md`, `docs/REFERENCES.md`,
`docs/ARCHITECTURE_EVOLUTION.md`, this file. `results/` trees are gitignored.

---

# (superseded) handoff, 8 September 2026 (§P0.20–§P0.21)

`[!]` **9 Sep: the kick-off prompt for the architecture-evolution phase is `docs/NEXT_SESSION_PROMPT.md`.**
The user lifted the one-die rule and asked for initial core designs within about a day (patent
update). Read that prompt first; this file is the 8 Sep state it builds on.

Read `docs/START_HERE.md`, then `docs/PHASE0_CHECKLIST.md` **§P0.20** (this session), §P0.19,
`docs/RESULTS_REGISTER.md`, `CLAUDE.md`. Slurm: job **1507** on node-06 as of 8 Sep. Baseline:
`python -m pytest HotGauge/HotGauge -q` → **1042 passed, 1 skipped** (4:40 on node-06, measured
after the last code change; 1025 after §P0.19).

## `[!]` v98 is the device authority now, and the target device is its Table 1.1

`docs/Photonic_Cooling_Devices___v98.pdf` supersedes v91 (`REFERENCES.md` §1). `--mr-extractor
dye` is rung 6 of v98's photonic ladder (Table 8.2) = Table 1.1's R640-SMILES row, the Tier-I
design point at 400 K. `DyeExtractor` was rebuilt on eqs. 5.7 and 8.4–8.9 and reproduces every
printed entry of Tables 8.1 and 8.2, Table 8.3, §8.3.5's optima and Table 1.1; the GaAs closed
form now matches v98 (9.6). Both notes sent to the author after §P0.19 are resolved in v98.

- **`T_min` is closed without a measurement.** The temperature dependence is the transparency
  cap `x_max = [1 + e^{(E_00−E_p)/kT}]⁻¹`, a Boltzmann ratio thermal by construction, so it does
  not depend on the tail steepness σ. Target device: 5900 W/mm² at 400 K, 813 at 300 K, 263 at
  263 K, 11 at 200 K; `T_min` 176 K (σ = 1), where the capability is already under 0.2 % of
  design. v98's own priority experiment (ε beyond 620 nm) moves the pump optimum, not the lift.
- **v91 eq. 8.4's 10³–10⁴ W/mm² for a bulk film is withdrawn by v98**; the 5 Sep "819 W/mm²,
  `T_min` 207 K" row rested on it and is in §2 of the register.
- **On this die the target device is invisible** (plans identical to §P0.18.2, 0 tiles capped)
  and **the requirements flow-down is rung 4**: a 2.00 W/mm² rescue needs ≥ 19 W/mm² per tile at
  290 K tiles; the near-term film (rung 2) delivers 17 W of the 198 W and runs away, rung 3
  delivers 52 W, rung 4 holds identically to the reference. The converged energy cap still
  takes the 2.60 rung: the array's ceiling is 2.40–2.60 W/mm².
- **The dye is a hot-die platform** (v98 §8.3.3, Table 10.8): 7–22× below design at the
  263–330 K this die's tiles run at.
- **A wiring flaw was found and fixed on the way**: a solve that diverged *because* the tile cap
  starved the array cleared the cap, so an uncapped application was reported as a hold. The last
  converged tile field now persists, and the first envelope plan is re-applied under the cap
  before it can stand.

## `[+]` Decided 8 Sep (§P0.21): zone materials, and the single-material default

The user's decision: storage (cold) zone material **Cr:LiSAF**, hot zone the **dye**, Yb:YLF out of
every zone; and the cold plate we test is **single-material by default** — a floorplan-matched
dual-material arrangement is a per-architecture product, which defeats the architecture-agnostic
premise. `--mr-zone-mode dual` (default `single`) exists to measure that arrangement once the
floorplan is a swept variable (Phase 2) or the array is integrated at die manufacture. Built,
tested (`cr-lisaf` extractor, `DualZoneExtractor`, `tiles_over_blocks`, the zone table), and
smoke-tested at 2.00 W/mm² — see `PHASE0_CHECKLIST.md` §P0.21 RESULT. On the way the regression
point found a latent P0.20 bug (the uncapped first-plan re-cap tripped the stale-plan guard);
fixed with a regression test.

## Still open, in order

1. The leakage-curve default (§P0.18.0) — still the user's call.
2. **Planner shape and mode** (§P0.19): a minimum over plan shape as well as scale; hand a
   hot-branch baseline to the envelope path.
3. **Run the `V_t` lever end to end** (25 mV first).
4. **Phase 2** (second floorplan, second workload) as planned in the 3 September handoff.

## Files this session touched — list for staging (never `git add .`)

Modified: `HotGauge/HotGauge/thermal/extractor.py` (rebuilt dye on v98),
`HotGauge/HotGauge/thermal/test_extractor.py`, `HotGauge/HotGauge/thermal/test_extractor_wiring.py`,
`HotGauge/HotGauge/thermal/microrefrigeration.py`, `examples/extractor_curves.py`,
`scripts/build_results_registers.py`, `CLAUDE.md`, `docs/START_HERE.md`, `docs/PHASE0_CHECKLIST.md`,
`docs/RESULTS_REGISTER.md`, `docs/METHODS.md`, `docs/REFERENCES.md`, `docs/ARCHITECTURE_EVOLUTION.md`,
this file. New: `docs/evidence/extractor_v98.json`, `docs/Photonic_Cooling_Devices___v98.pdf`
(yours), `results-quotable/08-extractor-lift/` (rebuilt). `results/extractor_v98/` is gitignored.

**§P0.21 (8 Sep, later) — additional files.** Modified: `HotGauge/HotGauge/thermal/extractor.py`
(Cr:LiSAF, `DualZoneExtractor`), `HotGauge/HotGauge/thermal/mr_array.py` (`tiles_over_blocks`),
`HotGauge/HotGauge/thermal/microrefrigeration.py` (zone table, zoned caps, `preview_shortfall`),
`HotGauge/HotGauge/thermal/test_extractor.py`, `HotGauge/HotGauge/thermal/test_extractor_wiring.py`,
`HotGauge/HotGauge/thermal/test_platform_materials.py`, `examples/mr_comparison.py`
(`--mr-zone-mode`), `scripts/build_results_registers.py` (entry 09), `CLAUDE.md`,
`docs/START_HERE.md`, `docs/PHASE0_CHECKLIST.md`, `docs/RESULTS_REGISTER.md`, `docs/METHODS.md`,
`docs/ARCHITECTURE_EVOLUTION.md`, `docs/NEXT_SESSION_PROMPT.md` (9 Sep rewrite), this file.
New: `examples/zone_mode_report.py`, `docs/evidence/zone_mode_smoke.json`,
`results-quotable/09-zone-mode/` (+ regenerated `results-quotable/` and `results-historical/`
manifests). `results/zone_mode_smoke/` is gitignored.

---

# (superseded) handoff, 5 September 2026 (§P0.19)

Read `docs/START_HERE.md`, then `docs/PHASE0_CHECKLIST.md` **§P0.19** (this session) and §P0.18,
`docs/RESULTS_REGISTER.md`, `CLAUDE.md`. Slurm: job **1507** on node-06 as of 5 Sep (`squeue -u
jbalma`), `scripts/on_node.sh <jobid> <cmd>`, `OMP_NUM_THREADS=1`. Baseline: `python -m pytest
HotGauge/HotGauge -q` → **1025 passed, 1 skipped** (4:39 on node-06, measured after the last code
change; was 992 after §P0.18).

## What landed — `dt_max` is derived, and it does not bind

`HotGauge/thermal/extractor.py` (`DyeExtractor`, `SemiconductorExtractor`) gives each platform its
cooling flux versus its **own** temperature from v91's constitutive parameters, anchored on Table
8.1, eq. 8.4 and Table 9.2 — nothing Yb:YLF. `--mr-extractor` on `mr_comparison.py` applies it
as a per-tile cap at delivery (`extractor_tile_caps`, `mr_array.deliver_capped`), self-consistent
with the tile's measured response; `ICEThermalSolver(mr_temps=True)` reports tile temperatures.
`examples/extractor_curves.py` → `docs/evidence/extractor_cooling_curves.json`;
`scripts/extractor_rescue_points.sh` + `examples/extractor_report.py` →
`docs/evidence/extractor_armD.json`.

- **Every rescue rung reproduces §P0.18.2 with zero tiles capped**, for the dye, fixed-pump GaAs
  and retuned GaAs alike. The coldest tile the array is ever driven to on this die is **263 K**
  (2.60 W/mm²), above every floor (dye 207 K at worst, GaAs fixed pump 259 K). The lift is not
  what bounds the array; conservation and bistability are.
- **A fixed-wavelength GaAs pump has a hot-side limit near 380 K**: on the 1.15 W/mm² hot-branch
  baseline it capped 3 tiles to zero; retuned, none. v91's per-temperature pump is necessary.
- **The scalar 45 K does a second job: it shapes the plan.** Keep `--mr-dt-max 45` with the
  curve; the curve alone gives an area-weighted envelope ~30 % dearer that lands on the hot
  branch at 2.40. Planner shape optimisation is an open item (`RESULTS_REGISTER.md` §3).
- **For the book's author**: eq. 9.5 as printed is 3.3× its own Table 9.2 benchmark (4/9 vs the
  balance's 4/27, or an unstated `C′ ≈ 1.8 C`); Fig. 9.9's 0.25–0.5 colour scale cannot be the
  first-law ledger's `η_ext`, which is bounded below by `ω_p/ω̄_f` ≈ 0.84.
- **Three defects fixed on the way**, two pre-existing: a row's die power and performance came
  from the last solve executed rather than the reported field (bisections end on a failing
  probe); caps must never be made from a diverged field; and the converged energy cap has to
  re-cap the first envelope plan before it can stand as a hold. `[!]` Rows in earlier ladders
  may carry the first defect in `p_chip_W`, `p_cool_W`, `f_GHz`, `gflops*` — never in Q, peaks
  or verdicts, which come from the plan and the reported field.
- **The converged energy cap takes one rung off the array ceiling**: 2.40 holds on 213 W from a
  die dissipating 222 W; 2.60 cannot hold the target without removing more than the cooled die
  produces. The honest array-assisted ceiling is **2.40–2.60 W/mm²** (register §1.3).

## Still open, in order

1. **Apply or overrule the leakage-curve recommendation** (§P0.18.0: flip to `simulated`).
2. **Confirm the extractor bracket with the device team**: the dye absorption tail at 680 nm at
   two temperatures (its thermal fraction decides `T_min` between 207 K and "never"), the host
   background absorption on a SMILES film, and whether the GaAs pump tracks temperature.
3. **Planner: shape and mode.** A minimum over plan *shape* as well as scale; hand a hot-branch
   baseline (holds above target by more than the scalar lift) to the envelope path — the 1.15
   W/mm² point under arm D is stuck on both today.
4. **Run the `V_t` lever end to end** (25 mV first; `clock_headroom.py --vf-source spice`).
5. **Phase 2** as planned in the 3 September handoff below.

## Files this session touched — list for staging (never `git add .`)

New: `HotGauge/HotGauge/thermal/extractor.py`, `HotGauge/HotGauge/thermal/test_extractor.py`,
`HotGauge/HotGauge/thermal/test_extractor_wiring.py`, `examples/extractor_curves.py`,
`examples/extractor_report.py`, `scripts/extractor_rescue_points.sh`,
`docs/evidence/extractor_cooling_curves.json`, `docs/evidence/extractor_armD.json`,
`results-quotable/08-extractor-lift/`.
Modified: `HotGauge/HotGauge/thermal/microrefrigeration.py`, `HotGauge/HotGauge/thermal/mr_array.py`,
`HotGauge/HotGauge/thermal/leakage_feedback.py`, `examples/mr_comparison.py`,
`scripts/build_results_registers.py`, `CLAUDE.md`, `docs/START_HERE.md`,
`docs/PHASE0_CHECKLIST.md`, `docs/RESULTS_REGISTER.md`, `docs/METHODS.md`, `docs/REFERENCES.md`,
`docs/ARCHITECTURE_EVOLUTION.md`, this file. `results/extractor_armD*/` are gitignored.

---

# (superseded) handoff, 3 September 2026 (second session, §P0.18)


Read `docs/START_HERE.md` first, then `docs/PHASE0_CHECKLIST.md` **§P0.18** (this session),
`docs/RESULTS_REGISTER.md`, `CLAUDE.md`. Baseline: `python -m pytest HotGauge/HotGauge -q` →
**992 passed, 1 skipped** on node-06, 4:44 (947 + 23 array-area/gap-rule + 21 SPICE V_t/V-F,
measured after the last code change). Slurm: `squeue -u
jbalma` (job **1389** as of 3 Sep), `scripts/on_node.sh <jobid> <cmd>`, `OMP_NUM_THREADS=1`.
`[!]` Node-side scripts must live on NFS — the head node's `/tmp` (and any agent scratchpad
there) is invisible from node-06 (`METHODS.md` §2.4).

## `[!]` The one decision still pending

**`--leakage-curve` default.** §P0.18.0 recommends **flipping to `simulated`** (the shipped default
becomes arm D exactly, the measured combination; every register §1 number already sits on it;
`pipeline` is not a device; the reproducibility argument was spent when the other two defaults
moved). **Not applied** — the handoff asked for a recommendation, not a silent flip. Apply it or
overrule it; what it touches is listed in §P0.18.0. Until then an un-flagged run is
`(pipeline, amortized, hierarchy-consistent)`, which nobody has measured.

## What landed

1. **The array charged its own footprint — and the charge is zero at the shipped geometry.**
   `--array-coverage` (areal; `mr_array.fill_for_coverage`, `array_area_ledger`,
   `tile_flux_report`, gap blocks routed to the nearest tile) on the three catalogue drivers,
   default 1.0. Ladder `scripts/array_coverage_ladder_armD.sh` → `results/array_coverage_armD/`
   (56 points, arm D, 34-core, 88 CFM, target 92 °C, 500 µm pitch) →
   `docs/evidence/array_coverage_armD.json`. **Quarter coverage (644/1126 blocks under gaps,
   74.8 of 101 mm² reserved) holds the same ceiling on the same minimum plan to ~1 %** at a
   common landing peak. The 200 µm burial smears a 250 µm gap as it smeared the pitch ladder.
   `[!]` Coverage cannot move a control-arm ceiling; `START_HERE`'s "every density ceiling is
   optimistic" was narrowed and the narrowing is in `RESULTS_REGISTER.md` §2.
2. **The array-assisted ceiling under arm D is 2.60–3.00 W/mm²** (recorded 1.60–1.80 on the
   pipeline curve). `[!]` **Envelope, not package**: at 2.60 the array removes 251 W from a die
   dissipating 239 W (sub-ambient pixels, 154 W net); the 3.00 failure is "envelope
   insufficient". Quote the rescue range (`array_idle` fails 1.20, the laser holds from there)
   and the cost ladder (17 W at 1.20 → 139 W at 2.00 removed; 11 → 84 W net).
3. **SPICE beyond leakage.** `spice_sim.vt_deck` / `idsat_deck`, `power/device_vf.py`,
   `examples/device_vt_vf_spice.py` → `docs/evidence/device_vt_vf_asap7.json`,
   `clock_headroom.py --vf-source spice[:T_K]`. `V_t,sat` 0.284 V, SS 61.0 mV/dec rising
   0.20/K, dVt/dT −0.46 mV/K, alpha **fitted** 1.45, I_off agrees with the leakage file to
   0.76 %. **The `V_t` lever re-priced:** 25 mV ≈ 22–30 K, **50 mV ≈ 45–60 K**, 75 mV ≈ 67–90 K
   of cooling — `LADDER_GEN0` §2's 22 K is withdrawn. Only the 25 mV step is inside the
   demonstrated 45 K.
4. **Predictions: two of five wrong, both favourable, both from carrying a derived estimate past a
   measured neighbour** (§P0.18.2 scores them). The falsifiers survived.

## Still open, in order

1. **Apply or overrule the leakage-curve recommendation** (above).
2. **`dt_max` from the device team** — now doubly load-bearing: the measured rescue failed on
   it, and the 50 mV `V_t` step lands on it. The precise ask is in `RESULTS_REGISTER.md` §3.
3. **Two planner limits exposed at the top of the coverage ladder** (§3): the energy cap should be
   the *converged* die power (a 12 W over-pull is invisible today), and a per-tile lift cap
   (P0.3) would bind before the per-block one. Neither moves any row below 2.40.
4. **Run the `V_t` lever end to end**: `clock_headroom.py --vf-source spice` with the leakage
   reference scaled by the simulated `10^(ΔV_t/SS(T))`, 25 mV first (the only step inside 45 K).
   Write the prediction down first: expect the lever's clock gain (+7.6 %) to survive and the
   cooling cost to land within 20 % of the 22–30 K re-derivation — and the named falsifier is a
   cost above 45 K, which would put even the 25 mV step outside the envelope.
5. **The LPC's own dissipation on the tile stack** (~6 W at the 88 CFM rescue, ~2 K die-wide) —
   a second heat source on the pixel die or a sink-load term. Small; stated, not modelled.
6. **Then Phase 2 — a second architecture, for falsification.** The apparatus is ready and
   nothing has yet been evolved (`ARCHITECTURE_EVOLUTION.md` §5). Concrete plan:
   - **Floorplan:** the 70-core 7 nm die (`examples/floorplans/outputs/skylake7nm_70core_*`,
     196 mm²) — same core, different die, so the *die*-level claims are tested without an ISA
     confound; the rebuilt ISA floorplans (§P0.5f) stay parked until the 34-core register has
     travelled once.
   - **Workload class:** a second Sniper/McPAT trace that is *not* single-threaded LINPACK —
     memory-bound (STREAM-like, cache-resident traffic) so the cache-vs-execution split of the
     power map moves. `mcpat_runs/7nm/` has the recipe; `STEADY_FROM_TICK` must be re-drawn on
     the new trace's warm-up step (`METHODS.md` §1.1).
   - **Register to re-measure, in this order, each with a written prediction:** the 1.4×
     concentration ratio (expect it to travel), the 200 µm pitch plateau and the coverage null
     (expect both to travel — they are burial-depth results), the 2.23× cold-zone ratio (expect
     it to travel), the 35/35 rescue as a *difference* (expect the range to move with die area),
     the absolute ceilings (expect them **not** to travel: 0.85–0.90 flat, 0.60–0.65 shaped are
     package-and-die numbers).
   - **Cost:** one arm-D density ladder (`scripts/uniform_density_ladder_armD.sh`, ~22 points)
     plus one coverage/rescue ladder (~14 points × 3 arms) per floorplan ≈ 2–3 h wall each at
     `PAR=6`. Memory is not the constraint it was (the coverage ladder peaked at 11 GB for six
     workers).
   - **What would count as the evolution loop's first step**, after Phase 2: split the cache
     onto a separate die (`stacked_memory_study.py` is broken on this toolchain — fix it first,
     `--cell-um 100`), re-run the register, and let the measurement say whether the cold die's
     14 % is real on a two-die stack.

## Files this session touched — list for staging (never `git add .`)

New: `HotGauge/HotGauge/thermal/test_array_area.py`, `HotGauge/HotGauge/power/device_vf.py`,
`HotGauge/HotGauge/power/test_spice_vt_vf.py`, `examples/device_vt_vf_spice.py`,
`examples/array_coverage_report.py`, `scripts/array_coverage_ladder_armD.sh`,
`docs/evidence/device_vt_vf_asap7.json`, `docs/evidence/array_coverage_armD.json`,
`results-quotable/06-transistor-simulated/`, `results-quotable/07-array-coverage/`.
Modified: `HotGauge/HotGauge/thermal/mr_array.py`, `HotGauge/HotGauge/power/spice_sim.py`,
`HotGauge/HotGauge/power/clock_search.py`, `examples/mr_comparison.py`,
`examples/mr_clipping_study.py`, `examples/clock_headroom.py`,
`scripts/build_results_registers.py`, `CLAUDE.md`, `docs/START_HERE.md`,
`docs/PHASE0_CHECKLIST.md`, `docs/RESULTS_REGISTER.md`, `docs/METHODS.md`,
`docs/REFERENCES.md`, `docs/ARCHITECTURE_EVOLUTION.md`, `docs/LADDER_GEN0.md`, this file.
`results/array_coverage_armD/` is gitignored (solve trees; the evidence JSON is the record).

---

# (superseded) handoff, 2 September 2026


Read this first, then `docs/PHASE0_CHECKLIST.md` (**§P0.17 is this session, §P0.16 the one before**),
`CLAUDE.md`.

## `[!]` TWO DEFAULTS CHANGED — read this before re-running anything

| flag | was | **now** |
|---|---|---|
| `--rbb-policy` | `stock` | **`amortized`** |
| `--core-other-policy` | (new in §P0.16) | **`hierarchy-consistent`** |

Both were decided on §P0.16's four-arm evidence: the RBB flip flips **no verdict** across 145
points (a null result, so it is safe rather than necessary), and the `core_other` flip fixes a
**provable defect** — the stock die reports 18.43 % static against McPAT's own 29.36 %.
`[+]` **The recorded catalogue is still exactly reproducible**: pass
`--rbb-policy stock --core-other-policy stock`. Asserted, not assumed
(`power/test_core_other.py`, `thermal/test_rbb_default.py`).

`[!]` **The open consequence, and it is the next decision.** The default is now
`pipeline` + `amortized` + `hierarchy-consistent`, which is **not one of the four measured arms**
(A `(p,s,s)`, B `(s,s,s)`, C `(s,a,s)`, D `(s,a,hc)`). Either also default `--leakage-curve` to
`simulated` — the default becomes **arm D exactly**, measured at 159/159 with zero anomalies, and
this is the recommendation — or run `(p,a,hc)` as a fifth arm (~3.5 h). Until then an un-flagged
run has no catalogue behind it.

## `[+]` The cold-zone prize under the corrected accounting: **5.7 % -> 13.8 %**

`examples/cold_zone_prize.py --core-other-policy hierarchy-consistent`. Static fraction
15.98 % -> **27.13 %**, cache share of leakage 38.24 % -> **54.14 %**. `[!]` The §P0.16 prediction
of "~10 %" was low because it scaled the static fraction **alone**; the cache share rises too
(undoing the `2 *` puts leakage back on real blocks *including the caches*), and the two multiply:
1.70 x 1.42 = 2.4x. `[+]` §P0.15's "leaf view is an upper bound" **survives** — but the two views
are only comparable **within** one policy (9.1 % vs 5.7 % under `stock`; 15.7 % vs 13.8 % under
`hierarchy-consistent`). The **2.23x improvement and the 280 K knee are untouched**.

## `[+]` Both §P0.16 defects fixed, with tests and a verified re-run

- **`__agg__L3` is filtered at the planner**, by prefix (`SYNTHETIC_TEMP_PREFIX = '__agg__'`) so a
  future bridged aggregate is excluded automatically. `[!]` **It took TWO sites** — the
  sensitivity-calibration probe builds its own plan from `base_hot` and bypasses `clipping_plan`
  entirely, so a one-site fix failed **10 of 11** points on re-run. A test asserts there are exactly
  two temperature-to-candidate sites so a third cannot appear silently.
  `[+]` **Verified: 11/11, 0 failures**, sweeps monotone. These 11 points were **unrunnable in the
  recorded catalogue**.
- **`stacked_memory_study` is a SIZE limit, not a code bug.** 1,098,144 unknowns at 50 um x 27
  layers against a measured working ceiling of 366,048; `--cell-um 100` quarters it and already
  works. `[!]` The real defect was the **silence** — 3D-ICE exits with an empty stderr after
  ~75 min — so a size diagnosis is now attached to the exception. It diagnoses, it does not gate.

---

# (superseded) handoff, 1 September 2026

Read this first, then `docs/PHASE0_CHECKLIST.md` (**§P0.16 is this session**), `CLAUDE.md`.
Baseline: `python -m pytest HotGauge/HotGauge -q` -> **919 passed, 1 skipped**, 5.4 min on node-06
(was 888 + 1; §P0.16 added 31: 11 for the curve comparison and recovery correction, 15 for the core_other policy, 5 for the four-arm comparison). Slurm: `squeue -u jbalma` for the jobid, then
`scripts/on_node.sh <jobid> <cmd>` with `OMP_NUM_THREADS=1`. Campaigns go through
`scripts/campaign_inner.sh` — `[!]` **feed it the joblist as a FILE on the node**
(`srun ... bash -c 'cat FILE | PAR=N campaign_inner.sh'`); piping the list into `srun`'s stdin
silently truncates it (measured: 3 of 12 jobs ran and the campaign reported success).

---

## §P0.16 — the MR catalogue came off the old leakage curve, and it barely noticed

`scripts/mr_curve_compare_joblist.sh`, `examples/mr_curve_compare.py`,
`docs/evidence/mr_catalogue_curve_compare.json`. 26 new points, three arms each, every argument
identical to the recorded `build_joblist.sh` families except `--leakage-curve` and `--out-dir`.

**`[+]` All 18 airflow rescues survive** — control diverges and the array holds at 6/6 airflows on
`pipeline`, `simulated` AND `simulated-gidl-off`; `array_idle` diverges everywhere too. The
headline *"across 20-120 CFM the unassisted die diverges at every airflow while the array holds at
all"* is intact and no longer rests on CACTI's eleven numbers.

**`[+]` The clipping study moves 2-4 % and the budget cliff does not move at all.** Knee stays
between 3 and 5 W on all three curves; no perf/W verdict flips.

**`[+]` So `--leakage-curve` is NOT a reason to re-run the MR catalogue.** The density ladder moved
14 % and the clock search lost a headline; the MR families are insensitive because they sit at or
above the **345 K crossover** where the two curves nearly agree, and because they are ratios
between two arms at the same temperature.

**`[!]` Four of five predictions were wrong, and both failures have ONE cause: turning a CURVE
ratio into a RESULT ratio.** Prediction 1 divided a measured loop gain by 2.4x and predicted 0/6
rescues; prediction 4 multiplied a clipping efficacy by ~5x and predicted a big move. Where a
directly comparable **measurement** already existed — §P0.15's fine ladder, which had the *shaped*
arm's cliff identical at 0.65 W/mm² on both curves — it predicted the outcome correctly and the
analytic estimate built on top of it did not. **Prefer the measured neighbour to the derived
estimate.**

**`[!]` A loop gain measured at a runaway is not an invariant.** `G = 1 + (r2/r1 - 1)/r` is
recoverable from any recorded runaway line with no re-solve, but a gentler curve does not lower it
— the die climbs further (residual 47 -> 65 K at 120 CFM) and arrives at a similar `G`. It is set
by the stopping rule. Valid across operating points; never divide a curve ratio into it.

**`[!]` MR array costs are not comparable across curves as recorded** — the descents stop at
different peaks (93.9 vs 91.3 °C), and at 88 CFM the entire extra cost is `dT/dQ = 0.3245 K/W`
against the package's measured **0.3247**. Compare at matched peak, or compare `dT/dQ`.

## §P0.16 — `core_other` is explained, and it is a `2 *` in our own converter

`scripts/mcpat_to_blk_lvl_power_dict.py:get_per_core_total_power` sets
`total_dynamic_power = 2 * runtime_dynamic` for every itemised per-core unit; the bare `Core<N>`
row that `core_other` maps to is built ~25 lines below **with no factor**. Leakage takes no factor
on either path, which is why its ratio (0.68-0.69) is a genuine node-dependent remainder. In raw
McPAT the `Core` row's children sum to **1.0000x** it for dynamic — **there is no un-itemised core
dynamic at all**; the slab is real for leakage only (~30 % of a core's leakage), plus an area-share
of modelled IMC/IO/SoC.

- **`[+]` The die total and the static fraction are SAFE** (18.43 % -> 18.59 %, and
  `scale_trace_to_die_power` renormalises anyway). §P0.15's cold-zone prize does not move.
- **`[!]` `core_other`'s share of on-die LEAKAGE is overstated ~1.75x** (35.6 % -> 20.3 %). That is
  load-bearing: §P0.15 leaned on "42 % of on-die leakage" to bound the prize, and `core_other_<N>`
  is the block that runs away at every diverging point on the density ladder.
- **`[!]` Nothing was changed.** Both fixes must land together (either alone moves the static
  fraction 2-5 pp), and the whole recorded catalogue rests on the as-built converter.

## `[+]` The catalogue re-run is priced: **6.3 h wall**, not 63 days

`scripts/catalogue_rerun.py`, re-planned 1 Sep: 252 points / 578 arms / 64 matrices /
~161,218 solves / 32.0 h compute / **6.3 h wall** on 6 memory-bound streams (28.8 GB widest
session). The quoted "80,330 solves / 63.5 days" is the **cold** cost. **THE DECISION IS THE
USER'S**, and three flags now want the same single pass: `--rbb-policy` (still undecided),
the `core_other` accounting, and — for the **density and clock** families only —
`--leakage-curve`.

## `[+]` The 36 net-generating rows are corrected, no re-solves

`examples/findings_recovery_correction.py`,
`docs/evidence/findings_recovery_correction.json`. All 36 flip sign; total **-5.879 W -> +32.672 W**;
`overnight3[11]` -0.596 -> **+3.354 W** as the audit predicted. `gross`, `cop` and spot dilution all
cancel in the ratio form, which is what let one formula cover `overnight3[26]`'s 5.24x dilution
overhead — a row that *looks* like a different efficiency preset and is not.

## `[+]` The granularity ladder, coupled — and why the recorded one could not be re-run

`[!]` `examples/tile_pitch_sweep.py`, which produced the recorded 2.77x, does **linear solves and
holds no leakage model** ("Linear solves, no leakage feedback" in its own output note). The flag
would have been a no-op there. The coupled form runs the pitch ladder through `mr_comparison.py`
instead (18 points, density 1.15, 88 CFM, target 92 °C).

- **Control diverges at every pitch on every curve** — with the airflow ladder that is **35 of 35
  rescue points intact**.
- **`[+]` Fine pitch saturates below ~200 µm**: 50/100/200 µm cost 19.476/19.476/19.470 W, identical
  to four figures across an **813x** range in tile count. **200 µm buys what 50 µm buys** — the
  recorded "~50 µm optics requirement" is conservative.
- **`[!]` The coarse-vs-fine penalty looks like it moves (1.30x -> 1.70x) and does not.** Normalised
  to a common peak at the package's 0.3247 K/W it is **1.29x vs 1.18x** — the correction *reverses*
  the ordering. **Any cross-curve MR cost comparison must be normalised to a common peak before it
  is read.** That is now a standing rule; it has bitten three times this session and changed the
  sign twice.

## `[!]` RUNNING NOW — the four-arm catalogue re-run

`scripts/catalogue_rerun_arms.sh`, launched on job 1389. Each arm differs from the previous by
**exactly one flag**, so every difference has a cause:

| arm | leakage curve | RBB | core_other | isolates |
|---|---|---|---|---|
| **A** | pipeline | stock | stock | same-code control |
| **B** | simulated | stock | stock | A->B = the leakage curve |
| **C** | simulated | amortized | stock | B->C = the RBB policy |
| **D** | simulated | amortized | hierarchy-consistent | C->D = the core_other accounting |

180 points / 506 arms / ~141k solves each, **3.75 h wall per arm**. Results land in
`results/rerun_arm_{A,B,C,D}/`; the recorded catalogue is untouched (the planner re-roots every
`--out-dir` under the arm directory and guards against writes outside it).

`[!]` **ONE ARM AT A TIME — node-06 has 251 GB, not the head node's 503 GB.** All four were
launched concurrently and hit **240 GB of 251 in 17 minutes** (arms B, C cancelled); the remaining
two then climbed to **231 GB** and arm A was cancelled as well. The planner's "peak 83.5 GB of a
200 GB budget" is **per arm**, and its 200 GB default already exceeds this node.

`[!]` **And an arm's footprint is not fixed — it scales with how many points CONVERGE**, because a
converging point holds its factorised session for many more solves while a diverging one exits
fast. Measured: arm A (`stock`, 78 % converged) **85 GB**; arm D (`hierarchy-consistent`, 99 %
converged) **136 GB**. So *the memory-hungriest arm is the one whose physics works best*, and "two
arms fit" is not a safe rule. `scripts/rerun_chain_sequential.sh` runs them one at a time.

`[+]` **Watch for the tail and overlap the next arm by hand — worth ~1 h each time.** An arm spends
its last stretch on two or three streams grinding through expensive points while ~90 cores and
~180 GB sit idle, and the sequential chain will not start the next arm until the *step* exits. Done
three times here (D->B, B->C, C->A) with no memory trouble, because a starting arm ramps up as the
finishing one winds down. The recipe: stop the chain **by explicit PID** (`ps -eo pid,args | grep
rerun_chain_sequential | grep -v grep`), `scripts/catalogue_rerun_arms.sh launch <jobid> <next>`,
then re-arm the chain for whatever remains. `[!]` Sequential is still the right DEFAULT — two arms
launched together from cold is what hit 240 GB of 251.

`[+]` **Nothing was lost.** The launcher is restartable (a finished stream leaves a `.done` marker
and is skipped) and every cancelled arm keeps its partial results (A 55, B 42, C 41). Arm **D is
running to completion**; `scripts/rerun_chain_sequential.sh 1389 B C A` is armed behind it and runs
the rest one at a time. To drive it by hand:

    nohup scripts/rerun_chain_sequential.sh 1389 B C A > results/rerun_chain.log 2>&1 &

- **The 72 accelerator points are excluded.** `accelerator_study.py` accepts none of the three
  flags (no McPAT cores, so `core_other` does not exist there), so they would reproduce the
  recorded output byte for byte — and they were the critical path. Dropping them took each arm
  from 6.3 h to 3.75 h. It is also what "one architecture, one die" already says.
- `[!]` **`scripts/srun_shim/`** makes each arm run inside ONE slurm step. The generated launcher
  issues one `srun` per stream; four arms x six streams would have asked for 24 concurrent steps
  against an allocation that admits ~8, and the surplus would have queued while the node idled.
- **Restartable**: a finished stream leaves a `.done` marker and is skipped, so re-running an arm's
  `run_rerun.sh` resumes it.
- `[!]` **`stacked_memory_study.py` is BROKEN on this toolchain and its points are excluded.** They
  fail with `ExecutableJobError: [Errno 5] 1/1 instances of ICESteadySim failed` **after burning
  ~75 minutes each** (measured 4684 / 4434 / 4420 s). Left alone they would have spent ~17 h across
  the arms producing nothing. They accept **none** of the three flags — verified against the plan —
  so they are identical in every arm and contribute nothing to a comparison. **The failure is
  pre-existing, not caused by this session**: those points run with default flags, exactly as the
  recorded catalogue ran them. Stopped and marked `.done` in arm D with the reasoning written to
  `results/rerun_arm_D/logs/EXCLUDED_stacked_memory.txt`. `[!]` **This is a real open defect worth
  its own investigation — do not fold it into the catalogue re-run.**
- `[!]` **Two defects the re-run surfaced, neither caused by it — see §P0.16 in the checklist:**
  - **`__agg__L3` is placeable and is not a block.** `bridge_aggregates=True` injects a synthetic
    L3 temperature key; the MR planner never filters it, so any point whose `--mr-target-C` is low
    enough for that key to exceed target dies with
    `KeyError: "plan names block '__agg__L3', which is not in the floorplan"`. `[!]` The trigger is
    **arm-dependent, not a target threshold**: point 16 (`A_ceiling_T50`) raised in arm B and
    completed in arm D, because the bug fires on the synthetic key's *temperature*, which moves
    with the leakage curve and the core_other policy. Costs ~10-11 points per arm. Fix = filter
    `BRIDGEABLE_AGGREGATES.values()` out of the planner's candidates; deliberately not applied
    mid-run.
  - **`stacked_memory_study.py` fails** (`ICESteadySim failed`) after ~75 min per point. Excluded
    from all four arms, documented in each arm's `logs/EXCLUDED_stacked_memory.txt`.

  Both are **pre-existing**: they reproduce with default flags, and arm B hits the `__agg__L3` one
  with `--core-other-policy stock`. Together they mean **each arm tops out at 159 reachable points,
  not 180** — 21 excluded, identically in every arm.

  `[!]` `catalogue_arm_compare.py` therefore reports **`done / reachable`**, not `done / planned`.
  Without that, completeness would read `159/180` forever and the "arms not complete" guard would
  cry wolf on every future run — a warning that is always on is a warning nobody reads. The
  exclusions are **evidence-based, per arm**: the broken driver (arm-independent) plus every point
  the arm's own `[sweep] point N raised` lines say it attempted and failed. `[!]` An earlier fixed
  `--mr-target-C <= 45` rule was **wrong and is withdrawn** — the trigger is arm-dependent. What a
  completeness guard needs is the STATE (done / attempted-and-failed / not yet run), not the cause.
  8 tests.

  `[!]` One asymmetry I introduced knowingly: arm D ran a few `stacked_memory` points successfully
  before they were stopped, while A/B/C had those streams pre-marked and ran none. Those points are
  flag-independent and excluded from the comparison, so it costs nothing — but arm D's tree holds a
  handful of results the others lack, and that is why, not a partial run.
- `[!]` **A stream can log every point `ok` and still leave points with no output.** Arm D's
  `sf01_mr_comparison` logged through its last point index and left **10 `followon/A_*` points**
  with empty out-dirs and no `.done` marker. That is why completeness is measured from the plan's
  `--out-dir` list and not from logs or markers. The chain runs **a final D pass** to recover them;
  the launcher skips the 15 streams that did finish.

**When they land**, run

    python examples/catalogue_arm_compare.py            # add --mr-arm array_on for the MR side

`[!]` **Completeness is measured from each arm's own `plan.json`, and must be.** Counting `*.json`
under an arm root reads HIGH (it also holds one `sf<NN>_<driver>.json` argv file per stream, plus
the plan); counting `mr_comparison.json` reads LOW (several catalogue drivers are not
`mr_comparison`); and counting stream `.done` markers reads low too — **one arm-D stream completed
all 33 of its points and left no marker**. The plan's own `--out-dir` list is the only honest
denominator. The driver prints `done/planned` per arm and refuses to let a partial pair be quoted.

`[!]` `docs/evidence/catalogue_arm_compare.json` **does not exist until you run this on
finished arms** — an interim snapshot was deleted rather than left on disk, because a file marked
`complete: false` is still a file someone will lift numbers out of.

`examples/catalogue_arm_compare.py` reports each adjacent pair separately (A->B the curve, B->C the
RBB policy, C->D the core_other accounting), counts verdict flips, and reports the peak-temperature
move on points that hold in **both** arms. It **refuses to summarise** unless the arms have the same
point count, and an `unconverged` row is counted as neither a hold nor a failure — the density
ladder's rule. 5 tests in `HotGauge/HotGauge/thermal/test_catalogue_arm_compare.py`.

The questions each pair answers: **A vs the recorded catalogue** = code drift since 14 Aug (a
difference here is *drift*, never a defect — §P0.15); **A->B** = does the 14 % density-ceiling move
survive across the catalogue; **B->C** = the RBB default decision; **C->D** = how much of the
recorded catalogue's divergence was the `core_other` artefact.

## Still open, in order

1. **Read the four arms** (above) and settle the RBB default and the `core_other` policy.
2. **Re-derive §P0.15's static fraction and cold-zone prize under `hierarchy-consistent`** — it
   should rise ~1.74x (prize ~6 % -> ~10 %). Must be recomputed, not scaled by hand.
3. **The density ceiling under the corrected accounting.** One paired point already shows a die
   that runs away under `stock` converging at 95.2 °C under `hierarchy-consistent`; arm D carries
   the ladder that would settle it.

---

# (superseded) handoff, 31 August 2026

Read this first, then `docs/PHASE0_CHECKLIST.md` (live state; **§P0.13 and §P0.14 are this
session**, §P0.12/§P0.11/§P0.10 the one before), `docs/DARPA_CLAIM_REGISTER.html`, and `CLAUDE.md`.

Baseline: `python -m pytest HotGauge/HotGauge -q` → **888 passed, 1 skipped**, ~5.5 min on
node-06 (821 + 1 before §P0.13's 21, §P0.14's 21 and §P0.15's 25; the same single skip). Keep it
there. `[!]` Do not run it while ~20 campaign workers are active — it starves on NFS (measured: 8 s
of CPU in 17 min). At ~10 workers it is fine. Slurm: `squeue -u jbalma` for the jobid, then `scripts/on_node.sh <jobid>
<cmd>` with `OMP_NUM_THREADS=1`.

---

## Where the last session left it

**RBB is done, and it was not the gate.** `HotGauge/HotGauge/thermal/rbb.py` +
`--rbb-policy {stock,amortized}` on `mr_comparison.py`, `mr_clipping_study.py` and
`clock_headroom.py`, default `stock`, stamped on every row.
Full write-up in §P0.10; the bracket is `docs/evidence/rbb_bracket.json`.

**The area semantics are settled** — and by the McPAT source, not by density. `EXECU::EXECU`
builds the bus from `interconnect` wires whose length spans the register file, the functional
units and the LSQ (`McPAT/core.cc` ~1150–1259), and `core.cc:1265` folds their area into the
Execution Unit's own. An `Area Overhead` is *itemised, and already inside its parent*. The compact
rectangle is a fictitious footprint because of **where the copper is**, not how many watts sit on
it. The "real blocks are 1–3 W/mm²" claim is withdrawn everywhere it appeared (P0.5f and both RBB
evidence files now carry the correction).

**But amortizing it does not unblock high density.** Same ladder, one flag apart: converging
points move a lot (1.20: 93.96 → 87.24 °C; 1.60: 92.83 → 90.79 °C and −20 % on the cooling bill),
and the ceiling does not move at all — both policies fail at 2.00 and 2.40. `[!]` At **every**
diverging point the block that runs away is `core_other_0`, under both policies, at nearly the
same temperature. RBB never appears. `rbb_is_the_gate.json` had measured RBB as the runaway on the
**rebuilt ISA floorplans**, where `core_other` was already shrunk to 0.94 % — a different die from
the one the density ladder runs on.

## The ceiling question is closed

**It has two terms, and neither is an accounting artefact.** §P0.11,
`docs/evidence/uniform_density_probe.json`, 16 solves. Two arms carrying the *same watts on the
same die with the same package* and differing only in how the power is spread:

| arm | holds to | first fails | hottest block at failure |
|---|---|---|---|
| shaped (real map, peak 174× mean) | **0.60** W/mm² | **0.80** | `RBB_16` |
| uniform (Gini 0, peak == mean) | **1.00** W/mm² | **1.20** | `core_other_5` |

1. **Concentration is worth ~1.5×.** A property of how power is *arranged* — measurable with
   `floorplan_metrics`, and designable.
2. **`[!]` A perfectly flat die still dies at 1.0–1.2 W/mm².** With Gini 0 there is no hot block to
   blame, so that is the **die-average limit of this package and this leakage model**. Physics.
   The artefact hypothesis is finished after five eliminations — stop chasing blocks.

**Three independent numbers agree, which is the reason to believe it:** the shaped arm's 0.60–0.80
bracket lands on the separately measured 0.80–0.85 W/mm² grease cliff, and the array arm of the
same die holds to 1.60–1.80 (§P0.10) — the array roughly doubles the passive shaped cliff.

`[!]` The **absolute** cliffs above are not the catalogue's: the probe is control-only, stock RBB,
and uses a flat die-wide leakage fraction (0.386) rather than the per-unit split. The **ratio
between the arms** is the result. Quote product densities from the catalogue drivers, not here.

## `[!]` The leakage curve is eleven hard-coded numbers

§P0.12, `docs/evidence/device_leakage_asap7.json`. The single most important thing found this
session, and it qualifies every thermal result in the project.

**The curve is a pass-through.** `leakage_calibration.json` came from eleven McPAT runs differing
in one XML line, and normalised it is **bit-for-bit CACTI's hard-coded `I_off_n[0][*]` array for
"16nm DG HP"** — ratio 1.000 at all ten points, max deviation 3.8e-6. That array
(`McPAT/cacti/technology.cc:1610`) is written as `1.52e-7/1.5*1.2*1.07` and friends: 32 nm numbers
times three fudge factors, reused unchanged for 32, 22 and 16 nm.

**And it is not a device.** Its implied local activation energy runs **0.016 → 1.081 eV, a 69×
spread, not monotone**. 0.016 eV is below kT at room temperature; 1.081 eV is the silicon bandgap.
Different mechanisms — so it is an interpolation, and we have been treating it as a measurement.

**Against a real card** (ASAP7 BSIM-CMG 7 nm, BSD-3, vendored under `spice_leakage/`; two barrier
forms agreeing within 4 % out to 500 K):

| T | pipeline today | card-based | ratio |
|---|---|---|---|
| 250 K | 0.923 (clamped) | 0.0110 | **84×** |
| 400 K | 36.1 | 19.4 | 1.9× |
| 500 K | 5820 | 349 | **17×** |

- **The cold-zone clamp is not physics.** Leakage keeps falling below 310 K until the
  temperature-independent gate floor takes over at **≈ 244 K**. That is where the cold-zone prize
  ends — not at 310 K, which is where CACTI's table happens to stop.
- **The hot tail is too steep** — 6× at 450 K, 17× at 500 K.
- **So §P0.11's 1.0–1.2 W/mm² flat-die ceiling is conservative.** A gentler tail runs away later.
  Quote it "on the current leakage curve" until this is settled.

`[!]` **That was not a SPICE run — but the one below it is.** The caveat that used to live here
(no simulator on this machine evaluates BSIM-CMG) held for about a day. See the next section: the
analytic model's hot-end verdict survives, its cold-end verdict does not, and the reason is the
GIDL it says here is unmodelled.

## `[+]` The one thing to do first — DONE. The curve is simulated

§P0.13, `docs/evidence/device_leakage_spice_asap7.json`, `HotGauge/power/spice_sim.py`,
`examples/device_leakage_spice.py`, 21 new tests. **All three checkpoints in
`docs/BSIMCMG_TOOLCHAIN.md` passed and Xyce was never needed.** ngspice 47 built from source with
OSDI loads OpenVAF-compiled BSIM-CMG and evaluates the ASAP7 card directly — all ~130 parameters,
absolute amps, **fitted to nothing**.

It is a device, and that is checked rather than claimed: **I_off(300 K) = 0.232 nA/µm**,
**subthreshold swing 61.7 mV/dec** against a 59.5 ideal, and BSIM-CMG 110 / 111.2.1 / the Xyce
tree agree to **0.37 %**.

| T | pipeline | analytic (P0.12) | **simulated** | sim, GIDL off |
|---|---|---|---|---|
| 200 K | 0.923 (clamped) | 0.0060 | **0.126** | 0.0032 |
| 250 K | 0.923 (clamped) | 0.0110 | **0.140** | 0.0167 |
| 400 K | 36.1 | 19.4 | **10.9** | 12.3 |
| 500 K | 5820 | 349 | **123** | 141 |

**`[!]` The cold-zone prize is ~20× smaller than P0.12 promised.** The floor below ~250 K is real,
but it is **GIDL — 98 % of leakage at 200 K** — not the gate leakage P0.12 assumed, and it sits
~40× higher. P0.12 listed GIDL as omitted and reasoned it "needs a negative gate bias to matter";
the bias that matters is gate-to-**drain**, which in the ordinary off state is −V_dd, so GIDL is on
in every off device on the die. Quote the cold end as a bracket (`mechanism='full'` vs
`'gidl_off'`): ASAP7 is a *predictive* PDK and its GIDL coefficients are a model choice.

**`[+]` The hot tail is gentler still**, so §P0.11's flat-die ceiling is *more* conservative than
recorded, not less.

**`[+]` And P0.12's method holds where it can be checked**: over 310–400 K — the only window McPAT
will simulate — the analytic and simulated curves agree within 2×, from wholly different
assumptions. That is asserted as a test.

**`[!]` The trap, for anyone extending this.** It was not the card, it was arithmetic: one 7 nm fin
leaks a few pA, below what ngspice's linear solve resolves, and every current came back an exact
multiple of 2⁻⁴³ A. `spice_sim.DEFAULT_NFIN = 1000` (DC current is exactly linear in fin count) and
the driver asserts convergence against a 10× re-run. At `nfin = 1` a cold point was **70 % wrong**
and the version cross-check appeared to disagree by **10 %** where it agrees to 0.37 %.

Toolchain notes worth reading before touching it: `docs/BSIMCMG_TOOLCHAIN.md`'s "What actually
happened" section — conda 4.12 cannot solve these envs (micromamba does, in seconds), conda's
clang-15 ships gcc-16 headers it cannot parse (use the system g++), node-06 has no `libz.so`, and
**OpenVAF segfaults on every input** until the one-character patch in `MXL_SPICE_fixes/`.

### `[+]` The re-runs are DONE — §P0.14, and they went two different ways

`load_leakage_model('pipeline'|'simulated'|'simulated-gidl-off')` wires the curve into the thermal
loop; `--leakage-curve` selects it on `uniform_density_probe.py`. **Default `pipeline` everywhere
and it must stay there** — same discipline as `--rbb-policy stock`. Both curves anchor at 330 K,
so the swap changes shape and nothing else.

#### `[+]` The cold-zone prize is 2.2x bigger, and the question is closed

`cold_zone_prize_bounds.json` called this *"the single number the architecture argument is most
uncertain about"* (13.5 % ours vs 31.7 % the book, a 2.3x spread) and named SPICE cards as what
would settle it. Cooling the cache from 350 K to 200 K:

| | pipeline | **simulated** | GIDL-off |
|---|---|---|---|
| leakage reduction | 1.73x | **16.6x** | 711x |

The pipeline is stuck at 1.73x at **every** cold temperature because it clamps below 300 K. The
prize grows **2.23x** — the book's end of the spread.

`[!]` **Quote the 2.23x, not a percentage.** `[+]` **DONE — §P0.15, and the absolute prize moved
down.** The recorded pair (34.64 %, 92.6 %) is now reproduced **exactly** and is a **scope error**:
`block_powers_split_400000000000.json` summed over the true leaves of **Core0 alone** with the whole
chip's L3 bridged in, on the trace's **warm-up** slice. §P0.14's hypothesis that it was measured
post-feedback at the operating temperature is **withdrawn** — dynamic power is temperature-independent
and the recorded 2.6062 W is that slice's `T_ref` dynamic to four decimals. Re-derived on the
pipeline's own denominator: **static 15.98 %, cache share 38.24 %**, prize **5.7 %** of die power at
200 K (4.5 % for an L3-only cold die; 9.1 % on the McPAT-leaf upper bound, which omits `core_other`
— 42 % of on-die leakage). **The absolute prize is ~4-10 %, best estimate ~6 %, and the 30 % end is
withdrawn.** The 2.23x improvement is untouched, which is exactly why §P0.14 led with it.

`[+]` And the prize is within 5 % of maximum by **280 K** — barely sub-ambient, a far easier
machine than the reduction factors suggest, and both GIDL brackets agree on the knee. The book's
"realistic 100-200x" is about 6x too big and it does not matter: the prize saturates, so 16.6x
already collects 94 % of what 200x would. Quote the die power, never the reduction factor.

#### `[!]` The density ceiling moves — DOWN, not up. P0.12's inference is withdrawn

This was predicted to go the other way. §P0.12 argued the pipeline tail is too steep, that a
gentler tail runs away later, and therefore §P0.11's 1.0-1.2 W/mm² flat-die ceiling is
*conservative*. §P0.13 measured a **47x** gap at 500 K, which made the prediction look safe.

Measured: **the uniform arm fails at 1.00 W/mm² where it previously held** (65.99 °C on the
pipeline curve) — one rung **lower**. The shaped arm's failing rung is unchanged at 0.80. **The
"conservative" claim is withdrawn, and the recorded ceilings are optimistic instead.**

The reason is the part worth carrying: runaway is a **local** instability, decided by
`d(ln P_leak)/dT` at the temperature the die is actually at (~317-347 K), not by leakage at
500 K — by then it has already run away under either curve, so the 47x disagreement lives where
the answer does not. In that band the ordering **reverses**: the pipeline curve is nearly flat
(0.0013/K at 310 K, 0.0091/K at 330 K, because that is where CACTI's table is clamped) while the
simulated one runs ~0.036/K throughout. The simulated curve carries **~9x more feedback gain at
320 K**, and the two cross over near 345 K. More gain runs away earlier.

`[!]` **This relocates the defect worth fixing.** The pipeline curve's most consequential error
for the ceiling is *not* its 47x-too-steep hot tail — a surviving die never reaches that region.
It is that the curve is nearly **flat at 310-330 K**, understating feedback gain by roughly an
order of magnitude exactly where dies operate. The same flatness is what made the cold-zone prize
look small. **One clamp, two wrong answers, in opposite directions.**

~~`[!]` And the GIDL bracket is a real open question *here*, unlike for the cold-zone knee: the two
brackets differ 14-15 % at 450-500 K (inside a rung, harmless) but far more at 310-330 K — which
this finding says is the band that decides the ceiling. Only the full-GIDL bracket was run.~~

`[!]` **WITHDRAWN (§P0.15).** The bracket was run and changes nothing on the uniform arm. The
inference above is wrong at one step: the brackets differ more at 310-330 K in leakage **level**,
but runaway is set by the **slope**, and the slopes there differ by only 1.16-1.27x against the
6-14x that the pipeline→simulated swap carries. This section's own mechanism was applied to the
wrong quantity.

### What is still worth doing here, in order

1. ~~**Run the density ladder on the `simulated-gidl-off` bracket**~~ `[+]` **DONE (§P0.15) — and
   the bracket is NOT load-bearing. Question closed.** The uniform arm — the flat-die ceiling —
   holds 0.80 and fails 1.00 under **both** brackets, identically. Only the shaped arm's 0.60 point
   changes, from *unconverged* to *diverged*: a point becoming decidable, not a ceiling moving.
   `[!]` The prediction failed for a reason worth more than the run: it compared leakage **levels**
   between brackets where §P0.14's own mechanism says compare **slopes**. In the 316-328 K band the
   holding points occupy, the pipeline→simulated gain ratio is **6-14x** and the bracket spread is
   **1.16-1.27x**. One rung moved for the first, none for the second — proportionate.
   `[+]` §P0.11's ceiling and §P0.14's one-rung move are therefore not GIDL artefacts, and the
   ASAP7 GIDL uncertainty does not need carrying as a caveat on the density ceiling.
2. ~~**Re-derive the static fraction and cache share**~~ `[+]` **DONE (§P0.15).** The prize is
   ~6 % of die power, not 10-30 %; the recorded pair was a scope + slice error. See above.
3. ~~**the clock-headroom search should move more than the ladder**~~ `[!]` **DONE (§P0.15), and
   the prediction was WRONG — it moved LESS.** Six cooling points × three curves, control arm: the
   sustainable clock is unchanged at **5 of 6** to the search's own 0.05 GHz resolution, +3.1 % at
   the sixth. `[+]` What it found instead is worth more: **the limiter changes at 3 of 6 while the
   clock does not.** The pipeline curve ends the search with a *thermal runaway*; both simulated
   curves end it at the *100 °C spec limit*. That withdraws `docs/CLOCK_HEADROOM.md`'s headline —
   *"the part does not reach its 100 °C spec limit at all, it runs away first"* — as an artefact of
   the pipeline curve's 47x-too-steep hot tail. `[!]` And it **refines §P0.14**: the tail is
   invisible to a fixed-density divergence test (whose reported point is one the die survives) and
   load-bearing to a search (which probes points it does not). **Which part of a leakage curve
   matters is a property of the experiment, not of the curve.** The GIDL bracket is worth nothing
   here — both brackets agree on the clock and on the limiter wherever it is judgeable.
   `docs/evidence/clock_headroom_curve_compare.json`.

4. **Still open: what the moved density ceiling means for the catalogue.** §P0.15's fine ladder
   (0.05 W/mm², 27 points, all three curves) turned "one rung" into a number: the flat-die ceiling
   moves **~14 %** — uniform arm 1.05-1.10 W/mm² pipeline against 0.90-0.95 simulated. `[!]` And
   the move is on that arm **alone**: the shaped arm's failing rung is identical at 0.65 on both
   curves, so §P0.14's "the shaped arm is unchanged" survives a 4x finer ladder. Whether a 14 %
   move on one arm justifies re-running 80,330 solves is still undecided.

## Still open, and unchanged by the above

**The RBB default.** `stock` ships as the default so an un-flagged re-run reproduces the recorded
catalogue. Whether the quoted results should move to `amortized` is a decision that has *not* been
made — the semantics argue for it, but it is a divergence from upstream and it moves every number,
so it wants to ride one deliberate catalogue re-run rather than drift in.

## Then, in order

1. **Re-run the density and `dt_max` questions** once RBB lands. Both are currently unanswerable;
   `dt_max` has been asked four times and confounded four different ways (§P0.9 table).
2. **PTM SPICE cards.** Extend the leakage calibration past 400 K (top measured) and below 310 K
   (where it clamps). Gates the cold-zone prize — uncertain 2.3× — *and* every claim above 400 K.
   It is not what blocks high density; the clamp test settled that (10/10 points identical).
3. **Re-run the recovery-affected evidence — `[!]` it needs NO re-solves.** Verified 31 Aug:
   `recovery_at_junction` is pure post-hoc accounting (`microrefrigeration.py` ~763–785 re-runs
   `mr_accounting` on the finished plan; it touches neither the solve nor the plan). And
   `net = gross * (1 - ratio)` with `ratio` a function of the params and `T_h` alone, so a
   recorded row can be corrected by algebra from its own numbers:
   **`net_new = net_old * (1 - ratio_new) / (1 - ratio_old)`**, with `ratio_new =
   params.breakeven_ratio_at(peak_C + 273.15)`. Checked against `FINDINGS.json` `overnight3[11]`:
   the implied `ratio_old` recovers `MRParams.breakeven_ratio` to 4 significant figures, and the
   row's −0.596 W becomes **+3.35 W** — the sign flip the audit predicted. Worth doing *after* the
   RBB default is settled, since the corrected values key off `peak_C`.
   **Original note follows.** All 8 `run_mr_clipping` call sites now thread
   `--recovery-at-junction`, but the recorded results predate it. `FINDINGS.json` has **36 negative
   `p_mr_net_W` entries** — a net-generating cooler, the bug in pure form. See
   `first_law_recovery_audit.json` for the sized exposure; two files flagged earlier are clean.
4. **The clock result is worth extending.** `clock_headroom.py` searches the *sustainable* clock,
   which sidesteps the RBB gate because it raises power gradually rather than imposing a density.
   It already gives control 3.875 → array_on **4.906 GHz (+26.6 %)** at **2.08 W/mm²**, 92.1 °C.
   Its `p_mr_net` was first-law (−22 W where the second law gives ~+121 W) and needs re-running now
   the flag is wired.

## What is solid (below 400 K)

- **22 measured rescues.** Control has no steady state, array holds target. Strongest: across
  **20 → 120 CFM** the unassisted die diverges at *every* airflow while the array holds at all.
- **Optics requirement ~50 µm, not 10** — 5× looser, and set by the floorplan (median block
  min-dimension 45.4 µm), not the device.
- **Granularity worth 2.77× on a hotspot, nothing on a flat die.** Robust to the 4× envelope
  refresh, as is the budget cliff — both are geometry, not actuator.
- ~~**Recovery crosses to export at 408 K**~~ **corrected 9 Sep: the export crossing is 614 K** with
  the v91 target extractor and a 90 % laser; 408 K is the *self-powering* temperature (condition
  1.15, pump covered), a different quantity the JSON summary had labelled "the crossing" against
  its own rows. `examples/recovery_at_temperature.py` now reports both.
- **Self-powering at 658 K shipped / 452 K at η_P 0.90** — validated against v91 §1.12 Examples 1–3.

## What was withdrawn last night, and why

| claim | why |
|---|---|
| fan power ∝ R⁻⁵, worth 22–35 % system power | used the textbook affinity law; `FanCoolingModel` is calibrated and **linear in heat carried** |
| turning the fan down saves power | at today's extractor it does not — optimum is baseline airflow; moves to 60/30 CFM only as the extractor improves |
| `dt_max` is / is not the blocker | confounded four ways; unanswerable until RBB |
| the array gives out at 2.0–2.4 W/mm² | same |
| the leakage extrapolation is the runaway mechanism | clamping changes nothing, 10/10 identical |
| `core_other` is the gate | fixed it to 0.94 %; ceiling did not move |
| real blocks are 1–3 W/mm² | contradicted by the paper (>8) and by our own p90 of 13.2 |

## Standing constraints

**One architecture, one die.** Decided 31 Aug 2026. The 34-core 7nm skylake floorplan is the only
die in play until the physics is verified end to end. ISA variants, the accelerator die, the
n-core sweeps and the pack floorplans are parked — they are the *next* phase, and every one of
them adds a confound to a question that has already been confounded five times. Vary one thing:
the physics.


Changes to stock HotGauge files stay **additive**. The user reviews, commits and pushes — never
`git add .`; `snipersim/`, `McPAT/`, `mcpat_runs/` are untracked build trees. Never
`git clean -fdx`. Pack images are **not** redistributable and must not be embedded in artifacts.

## Infrastructure notes worth keeping

- This allocation admits only **~8 concurrent slurm steps** (`NumTasks=1`, `OverSubscribe=NO`).
  One `srun` per job leaves 88 of 96 cores idle. Use `scripts/campaign_inner.sh`, which forks N
  workers inside a single step, with `scripts/build_joblist.sh` for the job list.
- `find` here is `bfs` and rejects `-newermt` — a silently failing check, not an idle node.
- `pkill -f <pattern>` matches this agent's own command line. Kill by PID.
