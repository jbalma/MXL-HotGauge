# Kick-off prompt for the next session

**Rewritten 13 September 2026, after the user's four points on the MXL-006 memo were addressed
(§P0.29 the planner-shape correction, §P0.30 the cooling-system ledger) and the plan below was
agreed.** Copy the block below verbatim; the one-paragraph form at the end is the same thing
compressed. The 11 September version is in git history.

---

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`.

**Read `docs/START_HERE.md` first**, then, in this order:

| file | read it before you |
|---|---|
| `docs/NEXT_SESSION.md` (13 Sep handoff at the top) | pick anything up — what ran, what is recorded, what is open |
| `docs/RESULTS_REGISTER.md` | quote any number — §0 (the `--mr-envelope-shape` row: **every plan is quoted with its shape**; the seed-shape plans are upper bounds and the anchor), §1.3 (the per-block rescue ladder ends at **3.50 W/mm²**, s = 0.99; the cooling-system ledger; the corrected F2 costs), §2 (the "s = 1 at 2.40" withdrawal), §3, §4 |
| `docs/PHASE0_CHECKLIST.md` §P0.29–§P0.30 | rely on any 13 Sep number — the unfinished-descent lesson, the 12× over-spend on a concentrated quarter, the ambient / inlet ladders |
| `docs/designs/EVOLUTION_LADDER.md` §2.1 (corrected), §2.3, §2.4, §4.3 | write about architecture |
| `docs/photonic_cooling/MXL-006-PRO/Update/MXL-006_update_memo.md` | touch the patent story — the memo's Section 2.2 review, Section 6 claim framing, Section 8 experiments; the user's four points of 13 Sep are answered in `NEXT_SESSION.md` |
| `docs/METHODS.md` §2.2, §2.6 | touch the node — **nothing runs on the head node** (campaign server, `results/campaign_queue/<name>.par<N>.tsv`; pandoc is head-node only and is the one exception, a text conversion) |
| `CLAUDE.md` | everything else |

**The state (13 Sep).** The proposal pack is `proposal_pack_2026-09-13/` (23 quotable items). The
memo package is `docs/photonic_cooling/MXL-006-PRO/Update/` (`.md` / `.docx` / `.html`, figures,
evidence). The default planner shape is still `seed` so the anchor reproduces (2.00 W/mm²: 138.73 W,
93.875 °C); a second anchor under `--mr-envelope-shape power` is 113.6 W / 91.5 °C at 2.00. The
campaign server is stopped; restart it with `nohup srun --jobid=1507 --overlap -n1 --cpu-bind=none
scripts/campaign_server.sh >> results/campaign_queue/server.log 2>&1 &` (check `squeue -u jbalma`).

## The plan, agreed by the user on 13 Sep — do these in this order

1. **A generalized f_max(V, T | logic depth, wire fraction, skew) in the framework.** Today the
   clock search ends at an ASSUMED 10 % overdrive on a saturating I_on(V)/V that is re-anchored at
   every temperature, so I_on(T) never reaches the clock and "10 GHz" cannot be tested either way.
   Build: gate delay FO4(V, T) ∝ C·V / I_on(V, T) from the SPICE card (`device_vt_vf_asap7.json`
   has I_on(V) at 14 temperatures to 0.85 V; extend the sweep upward if needed —
   `examples/device_vt_vf_spice.py`), logic depth per stage as a stated architecture parameter
   (~20 FO4 modern; 8–10 at Pentium-4-class pipelining), a wire-delay fraction, the measured thermal
   skew of X2 (§P0.27), and **V_max from an Arrhenius reliability budget at the cooled temperature**
   (EM: Black's law n = 2, E_a = 0.9 eV as in X1; TDDB: state E_a and the voltage acceleration)
   instead of a fixed overdrive. Then re-run the clock search (`clock_headroom.py --density`, three
   arms, arm D) so it names its limiter: device, wire, skew, reliability, or thermal. Predictions
   first (a §P0.31): the cooled die buys 10–15 % of V_max on the reliability budget and +6 % of gate
   speed from I_on(T), i.e. +20–30 % of clock on the same pipeline; 10 GHz needs the pipeline, not
   the cooler. Never quote a clock above the model's own ceiling.
2. **The 8× / 16× execution-cluster ladder at 20 µm and 5 µm burial** (the ">1000 W/mm² functional
   units" question: ΔT ≈ q·d/k means the extractor must sit within microns). `generate_exec_density_
   family.py --factors 0.125 0.0625` (cALU at 230–460 W/mm²), `mr_comparison.py --flp-dir … --burial-um
   20 | 5 --pitch-um 200 | 100 --mr-envelope-shape power`, matched die watts as D1, 100 µm cells
   (check the stack's unknown count against the 366k limit; 50 µm if it fits). Find where transport
   binds: the rung at which the cluster's peak cannot be held at any plan. Predictions first: at
   5 µm the 8× cluster holds every D1 rung; at 20 µm the 16× cluster loses the 2.00-equivalent rung
   to the gradient through the silicon; the tile flux climbs past 50 W/mm² and still stays under the
   film. Report the rails (X1's current ladder scales with the density factor).
3. **A CoMeT IPC(f) reader.** `/mnt/nfs01/scratch/jbalma/CoMeT/test/thermal_example_test_1to20ghz/
   run_<f>/sim.out` (and the `benchmarks_sweep` runs) carry Instructions / Cycles / IPC / Time per
   frequency (FFT: IPC 2.88 / 2.49 / 1.95 / 1.43 at 1 / 4 / 10 / 20 GHz) and `InstantVdd.log` carries
   CoMeT's DVFS voltage. Build `examples/comet_ipc_reader.py` → `docs/evidence/comet_ipc_vs_f.json`
   (IPC(f) per benchmark, wall time, their V(f)), and replace the fixed-IPC GFLOP/s proxy in
   `clock_f1c_report.py` / `iso_package_throughput_report.py` with throughput = f × IPC(f) × cores so
   the memory wall enters the throughput claims. Only the frequency setting differs between CoMeT's
   configs — it says nothing about whether the device can switch at 20 GHz; item 1 does.
4. **Re-run the D1 family and the accelerator under the per-block shape.** Their recorded plans
   are seed-shape upper bounds (§P0.29: 18–33 % on the reference ladder, 12× on a concentrated
   quarter). D1: `scripts/d1_family_ladder.sh` with `--mr-envelope-shape power` on the array rungs
   (both members, five rungs) → `results/d1_family_power/`; the reference per-block ladder is already
   in `results/array_coverage_armD_power/`. Accelerator: `results/accel_f3_power_tol1` already used the
   power shape (§P0.24) — confirm, and re-run only its seed-shape rows if any remain. Then the
   register's D1 row and the ladder's §2.2 / §2.4 carry both shapes; the D1 premium ratios are
   like-for-like only within a shape.

**Not this session:** the two-sink gen-3 stack (ladder §4.3; needs `bottom heat sink` in `die_stack`
and a second array wiring — next); a rail model (register §3); D2; net export (reserved).

**Rules, unchanged:** predictions in `PHASE0_CHECKLIST.md` before any run (§P0.29–§P0.30: fourteen
written, eight confirmed, four falsified, two half); an `unconverged` row is neither a hold nor a
failure, and an unfinished planner descent is neither (§P0.29); quote every plan with its envelope
shape; re-run the 34-core arm-D anchor after any planner or stack edit (both shapes); nothing on the
head node; never `git add .`; list the files.

---

## Short intro prompt (the same session, in one paragraph)

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`. Read `docs/START_HERE.md`, then
`docs/NEXT_SESSION_PROMPT.md` (13 Sep) in full — it is the brief. Context: `docs/NEXT_SESSION.md`
(13 Sep handoff), `docs/RESULTS_REGISTER.md` (§0's envelope-shape rule; §1.3's per-block ladder to
3.50 W/mm², the cooling-system ledger, the corrected F2 costs; §2's withdrawals), `docs/PHASE0_CHECKLIST.md`
§P0.29–§P0.30, `docs/designs/EVOLUTION_LADDER.md`, the MXL-006 memo in
`docs/photonic_cooling/MXL-006-PRO/Update/`, `docs/METHODS.md` §2.2/§2.6, `CLAUDE.md`. The agreed
plan, in order: (1) a generalized f_max(V, T | logic depth, wire, skew) with V_max from an Arrhenius
reliability budget, then the clock search re-run so it names its limiter; (2) the 8× / 16× cluster
ladder at 20 µm and 5 µm burial under the per-block shape; (3) a CoMeT IPC(f) reader replacing the
fixed-IPC throughput proxy; (4) the D1 family and the accelerator re-run under the per-block shape.
Predictions before any run; quote every plan with its shape; the anchor after any planner or stack
edit; nothing on the head node (campaign server on job 1507); never `git add .`.
