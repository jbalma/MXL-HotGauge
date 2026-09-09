# Kick-off prompt for the next session

**Rewritten 9 September 2026, revised the same day after the user's answers and the v100 drop.**
Copy the block below verbatim (the short intro prompt at the end of this file is the same thing
compressed to one paragraph, for a session that will read the files itself). This version opens the **architecture-evolution phase**: the user lifted the
one-die rule on 9 September and asked for **initial core designs within about a day**, as input
to a patent update. The user's decisions: **the designs are to be ARGUED, measured where the day
allows**; the deliverable is the rational evolution ladder (bottleneck → laser cooling removes it →
the architecture changes → the next bottleneck emerges → repeat); and **D3's cache-leakage planner
objective is worth building now**. The previous version
(3 September, which opened the §P0.18–§P0.21 sessions) is in git history.

---

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`.

**Read `docs/START_HERE.md` first**, then, in this order:

| file | read it before you |
|---|---|
| `docs/RESULTS_REGISTER.md` | quote any number — quotable / withdrawn / open, and the flag table in §0 |
| `docs/ARCHITECTURE_EVOLUTION.md` | design anything — §3 is the design template, §4 the gap list, §5 says **no architecture has been evolved yet** |
| `docs/CODESIGN_PLAN.md` §9 | call anything a "design" — a rung is a floorplan **plus** the binding constraint the solve named **plus** the change made because of it, at three fixed invariants |
| `docs/METHODS.md` | run anything — pipeline, cluster, traps (§5), suite baseline **1050 passed, 1 skipped** (re-run 9 Sep after the flip) |
| `docs/REFERENCES.md` §1 and **`docs/Photonic_Cooling_Devices___v100.pdf`** | argue any device number — v100 is the authority (9 Sep). For the ladder read **§1.18** (the architectural budget inequality 1.32, the hybrid cap 1.33, cubic vs linear scaling, the V_t trap) and **§10.9** (thermal heterogeneity as a design knob; the three-zone template and its three walls) |
| `docs/PHASE0_CHECKLIST.md` §P0.18–§P0.21 | rely on the array footprint, the SPICE device, the extractor curve, or the zone decision |
| `docs/NEXT_SESSION.md` (8 Sep handoff at the top) | pick up open items; the 3 Sep Phase 2 plan below it is still the plan |

`CLAUDE.md` is the short form and loads automatically. The run ledger artifact from the last
session (charts of every campaign, 3–8 Sep) is at
https://claude.ai/code/artifact/9f44928b-5d22-4ae2-909d-b7113bbc083c.

`[+]` **`--leakage-curve` defaults to `simulated` since 9 Sep** (user's decision): an un-flagged
run is arm D. Add `--leakage-curve pipeline` only to reproduce the pre-30-Aug catalogue.

Compute: `squeue -u jbalma` for the jobid (**1507** on node-06 as of 9 Sep; it may have ended).
`scripts/on_node.sh <jobid> <cmd>` with `OMP_NUM_THREADS=1` and `PYTHONDONTWRITEBYTECODE=1`.
Never solve on the login node. Campaigns go through `scripts/campaign_inner.sh` fed a joblist
**file** (`< joblist.tsv`) — see `scripts/extractor_rescue_points.sh` for the shape. Node-side
scripts live under `spice_toolchain/tmp/` (the head-node scratchpad is invisible on the node).
Wait ~1 min after head-node edits before launching (NFS attribute cache). Run the full suite on
the node through a script file; it takes ~5 min there and stalls on the head node.

## Where things stand

The apparatus is built, validated, and one die is measured end to end under arm D
(`--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent`).
Since 3 September: the array is charged its own footprint and the charge is **zero** at 500 µm
pitch / 200 µm burial (§P0.18); SPICE gives V_t(T), SS(T), I_on(V,T) and α = 1.45 from the ASAP7
card, re-pricing the 50 mV V_t step to **45–60 K** (§P0.18.3); `dt_max` is **derived** from the
extractor's own cooling curve on v98's transparency cap and **never binds** on this die
(§P0.19–20); the target device is v98 Table 1.1 (rung 6), and rung 4 is the requirements
flow-down; the zone materials are **decided** — Cr:LiSAF storage zone, dye hot zone, no Yb:YLF —
and the cold plate we test is **single-material by default** (`--mr-zone-mode single`), the dual
arrangement being a flag that measured as a 1 % effect on the hot-spot objective (§P0.21).
On 9 Sep (§P0.21.5): the leakage default was flipped; v100 was checked against the code (target
device, Cr:LiSAF and GaAs unchanged; two new Table 1.1 organic rows added as `nir-cyanine` and
`j-aggregate` presets — ceilings, cascade stages, not the target device); and the recovery
evidence's "crossing at 408 K" was corrected to a **614 K export crossing** (408 K is the
self-powering temperature) — quote the export crossing.

`[!]` **The one-die rule (31 Aug) is lifted as of 9 September.** The user opened the
architecture-evolution phase. Other floorplans are in scope now, with the same discipline: one
variable at a time, predictions written first, the 34-core die as the fixed reference.

`[!]` **`ARCHITECTURE_EVOLUTION.md` §5 is still true until this session changes it:** nothing has
yet been changed *because* of a measurement and re-measured. The first design that closes that
loop is the deliverable.

## The goal of this session

**Produce initial core designs within about one day**, as evidence for a patent update. `[!]`
**The user's decision (9 Sep): the designs are to be ARGUED, measured where possible.** What the
patent update needs is a rational, defensible account of how an architecture evolves once laser
cooling is deployed on a specific die: *what binds the die today → laser cooling removes it →
what changes on the architecture first → what binds the new architecture → laser cooling
addresses that → the architecture changes again → …*, until the binding constraint is no longer
thermal (`CODESIGN_PLAN.md` §9's stopping rule). Each rung's argument must rest on a measurement
already in the register wherever one exists, and must say plainly where it rests on argument
instead. A rung that gets measured during the day is a bonus, not the bar.

A design here is a **gen-0 → gen-1 rung** in `CODESIGN_PLAN.md` §9's sense:

1. the baseline solved with and without the array, the **binding constraint named from the
   solve** (peak block / die-average path / leakage runaway / MR budget / V/F ceiling / none);
2. one architectural change made **because** of that constraint;
3. the re-measurement at the three invariants — same trace, same die power, same MR electrical
   budget — with the *next* binding constraint named.

**The primary deliverable is `docs/designs/EVOLUTION_LADDER.md`**: the ladder for the 34-core
7 nm die, written rung by rung, in the frame v100 §1.18 gives it — every rung is a statement about
which term of the budget inequality (1.32) binds, and what moving the wall by 1/(1−s) (1.33) lets
the architecture spend; §10.9's three walls (BEOL ≳ 400 K, extractor material, thermal gradient /
packaging) are the honest limits on the hot end. Written rung by rung — gen 0 (the die as measured: what binds, from the solve),
gen 1 (what laser cooling removes and what the architecture does with the freed constraint),
gen 2 (what binds the gen-1 design and how cooling plus a second change addresses it), and so
on to the rung where the limit stops being thermal. For every rung: the binding constraint and
the evidence that names it (register row or a §P0 measurement, with its number); the
architectural change and why it is the *first* thing to change rather than another; the
prediction for what binds next and its falsifier; and a MEASURED / ARGUED tag on every claim.
Each rung that gets run also gets a design record `docs/designs/gen<N>_<name>.md` with the
floorplan figure (`examples/plot_floorplans.py`), the predictions written before the run, the
rows, and the constraint before and after. Keep the patent-facing text out of the code; it lives
in those records and in a new §P0.22 of the checklist.

The ladder as the evidence currently supports it — check each step against the register before
writing it, and change it where the register disagrees:

- **gen 0 — what binds today.** Under arm D the uncooled die has no steady state above
  1.00 W/mm² (leakage runaway; control diverges at every rung) and the idle array holds only to
  1.10; below that the peak block (cALU class) sets `core_fmax`. MEASURED (§P0.18.1).
- **gen 1 — cooling removes the runaway; the first change is to the execution cluster.** The
  array holds the die to 2.40 W/mm² (conservation) / 2.60 (envelope) with 0 tiles capped and
  no tile below 263 K, so the freed constraint is *die power density at the hot spot*. The
  first architectural change is therefore to let the execution cluster get denser and hotter
  than a conventional floorplan allows and to aim the array's granularity there (200 µm pitch
  suffices; coverage is free). What binds gen 1: predicted **conservation** — the array cannot
  remove more than the die dissipates — which is a package/LPC number, not a floorplan number.
  MEASURED for the constraint, ARGUED for the design (D1 measures it if it lands).
- **gen 2 — spend the headroom on the device, not the clock.** Once density is bought, the next
  lever is V_t: low-V_t on the cooled cluster, high-V_t elsewhere. The 25 mV step (+7.6 %
  clock, 22–30 K of lift) is inside the demonstrated 45 K; 50 mV (45–60 K) is not. What binds
  gen 2: predicted the **MR electrical budget / COP** (the leakage the low-V_t cluster adds is
  paid in cooling watts at η_ASF ~0.1). ARGUED on measured inputs (D2 measures it if it lands).
- **gen 3 — split the cache onto a cold die.** Leakage is the cache's cost, not heat; the knee is
  280 K and the improvement 2.23×; a monolithic die shorts the zones (1.24 K per 40 W). The
  change is a two-die stack with the storage zone on Cr:LiSAF and the compute die on the dye,
  cooled under a *cache-leakage* objective, not the hot-spot objective (§P0.21 showed the latter
  never cools the caches). What binds gen 3: predicted **something a cooler cannot fix** —
  interconnect / memory bandwidth across the stack — which is the ladder's honest end. ARGUED;
  D3's objective is what makes it measurable.
- **The dual-material plate is not a rung.** It is a per-architecture layout; the product stays
  single-material. Say so in the ladder.
- **The hot end has walls the cooler cannot move** (v100 §10.9): Cu/low-κ BEOL is not viable in
  continuous operation above ~400 K, so a 500–600 K compute zone is a metallization story before
  it is a cooling story; the extractor is zone-specific; a 300 K in-plane gradient over sub-mm is
  a packaging element. The ladder's hot rungs stop at the BEOL wall unless the rung changes the
  metallization, and the ladder must say which.

**Device parameters for the next batch (v100-checked, 9 Sep):** target device `--mr-extractor dye`
= v100 Table 1.1's R640-SMILES row (rung 6: 10⁻¹ M, 651 nm pump, λ̄_f 590 nm, F̄_P 100, 50 µm;
5.9×10³ W/mm² at 400 K, 813 at 300 K); `--mr-dt-max 45` kept alongside; storage-zone material
`cr-lisaf` (F_P 30, 10 µm, η_EQE = 1 ceiling); `--mr-zone-mode single` default; `--array-coverage
1.00`; `--mr-energy-cap converged` for any ceiling claim. The two new organic rows are available as
`nir-cyanine` and `j-aggregate` for a cascade argument, not as the plate under test.

### The candidates, in order of evidential support (`ARCHITECTURE_EVOLUTION.md` §3)

**D1 — Dense, hot execution cluster with the array targeted at it.** The best-supported design
move after the cache split: 35/35 rescues at 1.15 W/mm², the 200 µm pitch plateau, the array
ceiling at 2.40–2.60 W/mm² against a control that fails at 1.00. Build variants of the 34-core
die with the execution units (cALU/FPU class, 142 × 115 µm) denser and the caches unchanged —
`examples/generate_ncore_floorplans.py` (`--vector-multiple`, `--area-json`) and
`examples/floorplans.py` are the tiler; the 10 nm `fpIWin_*` variants in
`examples/floorplans/outputs/` are the precedent for a scaled-unit family. Measure the
density ceiling and the rescue cost ladder at fixed die power against the 34-core reference
(`scripts/uniform_density_ladder_armD.sh`, ~22 points; `scripts/array_coverage_ladder_armD.sh`
for the rescue ladder). Expected to produce numbers **inside the day**.

**D2 — Multi-V_t spatial assignment under the array.** Reframed in the checklist's open items:
low-V_t on the execution cluster the array cools, high-V_t elsewhere — a floorplan result and a
device result through one mechanism. The 25 mV step is the only one inside the demonstrated
45 K lift (22–30 K, +7.6 % clock). `examples/clock_headroom.py --vf-source spice` exists; the
missing piece is the leakage reference scaled by the simulated `10^(ΔV_t/SS(T))` for the
assigned blocks only. This has never been run end to end; running it once at 25 mV on the
34-core die is a result by itself.

**D3 — Separate cache die (cold die ~280 K, cooled for leakage). `[!]` The user decided (9 Sep)
that the cache-leakage planner objective is worth building now.** The measured constraint
(1.24 K of gradient for 40 W; conduction shorts the zones on a monolithic die) and the 2.23×
cold-zone ratio are the strongest evidence in the register. Build: a planner objective in
`thermal/microrefrigeration.py` that minimises **die leakage** (or holds a cache-zone
temperature target, e.g. 280 K, at minimum cooling watts) instead of holding the hot-spot
peak — `examples/cold_zone_prize.py` already has the leakage-versus-temperature ledger the
objective needs, and `--mr-zone-mode dual` with `--mr-cold-extractor cr-lisaf` gives the
storage-zone tiles their own curve. Expose it as `--mr-objective {peak,cache-leakage}` (default
`peak`; write the prediction and the test first). Then the two-die solve:
`examples/stacked_memory_study.py` is a **size** limit (1.1 M unknowns at 50 µm; `--cell-um 100`
works). Build the objective in the morning; if the two-die solve is not running by mid-afternoon,
the gen-3 rung stays *argued* and the objective is still a deliverable.

**D4 — Falsification on the 70-core die**, in parallel, not as a design:
`examples/floorplans/outputs/skylake7nm_70core_3_3D-ICE_template.flp` (196 mm²) exists. Run the
arm-D density ladder on it and score the 3 Sep predictions (ratios travel, absolute ceilings do
not). One ladder ≈ 2–3 h wall at `PAR=6`; it can run while D1's floorplans are being generated.

### A one-day shape

- **First hour, no solver:** draft `docs/designs/EVOLUTION_LADDER.md` from the register (the
  argued ladder is the deliverable; everything after this improves it); write §P0.22 with the
  predictions for D1, D3 and D4 (a number and a falsifier each); launch D4's ladder on the node.
- **Morning:** build D3's cache-leakage objective and its test (head node, pure python); generate
  and plot D1's floorplan family; launch D1's ladder at `PAR=6`.
- **Afternoon:** D3's two-die solve on the node if the objective is in; D2's leakage-reference
  scaling and one run at 25 mV if time allows; read D1/D4 back with
  `examples/uniform_density_report.py` / `examples/array_coverage_report.py`.
- **Last hour:** finish the ladder with MEASURED/ARGUED tags updated for what landed, the design
  records, §P0.22 RESULT with the scorecard, `RESULTS_REGISTER.md` §1/§3 rows,
  `ARCHITECTURE_EVOLUTION.md` §5 (change the "not started" rows only for what was actually
  re-measured), `scripts/build_results_registers.py` entry 10, the staging list.

## What the patent-facing text may and may not say

- **Measured on this die:** the rescue range and cost ladder (17 W at 1.20 → 139 W at 2.00),
  the 2.60 envelope ceiling and 2.40 under conservation, the 2.23× cold-zone ratio, the 280 K
  knee, the 200 µm plateau, the coverage null, the derived-lift result (0 tiles capped), the
  V_t re-pricing, and whatever this session re-measures.
- **Argued, not measured:** the two-die split as a whole design, the dense-cluster design until
  D1 lands, the V_t lever until D2 lands.
- **Never:** Yb:YLF as a zone material; a dual-material plate as the product (it is a flag; the
  default is single-material and architecture-agnostic); v91 eq. 8.4's 10³–10⁴ W/mm² for a bulk
  film; the 22 K V_t figure; "the cold-zone prize is 30 % of die power"; any Cr:LiSAF figure
  without "ceiling at η_EQE = 1" beside it; any top-rung ceiling as an operating point; and
  "an architecture has been evolved" until §5 says so.
- Quote ratios rather than absolute ceilings across dies; normalise MR costs to a common peak
  (0.3247 K/W) before comparing across curves.

## How to work here

- **Write predictions in `PHASE0_CHECKLIST.md` before the run.** Five of sixteen this month
  were wrong; every correction came from having written them first.
- **Prefer the measured neighbour to the derived estimate.** Three of the five misses carried a
  derived estimate past a measured neighbour.
- `unconverged` is neither a hold nor a failure. Never site a refinement off an unfinished
  ladder. Check a study consumes an input before re-running it.
- **Re-run the reference point after any planner edit.** The P0.20 target-device rows were
  produced before the last planner fix and had never run on the final code; the §P0.21
  regression point found the bug. The 34-core arm-D point at 2.00 W/mm² (plan 138.73 W, peak
  93.875 °C) is the regression anchor.
- Keep `--mr-dt-max 45` alongside `--mr-extractor dye`; never make tile caps from a diverged
  field; preview a cap's shortfall rather than applying an unsolved plan
  (`CoolingApplication.preview_shortfall`).
- **Never `git add .`** — list touched files for the user. The 8 Sep files are listed at the end
  of the 8 Sep handoff in `docs/NEXT_SESSION.md` and may still be unstaged.
- Suite baseline must not regress (1050 passed, 1 skipped, on the node).

## Decided by the user on 9 Sep

- The designs are **argued, measured where possible**; the ladder argument is the deliverable.
- D3's cache-leakage planner objective **is** built this session.

## Still open for the user

Nothing blocking. The `--leakage-curve` default is flipped (9 Sep).

---

## Short intro prompt (the same session, in one paragraph)

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`. Read `docs/START_HERE.md`,
then `docs/NEXT_SESSION_PROMPT.md` (9 Sep) in full — it is the brief for this session. Context files:
`docs/RESULTS_REGISTER.md` (quotable / withdrawn / open, flag table in §0), `docs/METHODS.md`
(pipeline, cluster, traps), `docs/PHASE0_CHECKLIST.md` §P0.18–§P0.21.5 (the lab notebook for
the last week), `docs/ARCHITECTURE_EVOLUTION.md` and `docs/CODESIGN_PLAN.md` §9 (what a design
is), `CLAUDE.md` (the rules). Evidence: `docs/evidence/*.json` (every number the register quotes;
`results-quotable/` is the checksummed copy, `scripts/build_results_registers.py --verify`), and
the run-ledger artifact https://claude.ai/code/artifact/9f44928b-5d22-4ae2-909d-b7113bbc083c
(charts of every 3–8 Sep campaign). References: `docs/REFERENCES.md` §1 maps the device physics
to **`docs/Photonic_Cooling_Devices___v100.pdf`**, the authority since 9 Sep — read §1.18 and
§10.9 before writing the ladder, Table 1.1 / Tables 8.1–8.2 / §8.1.2 for the extractor, §8.4 for
platform selection; v91 remains the source for the array geometry and Draft_5 for the demonstrated
45 K lift. Goal: the argued evolution ladder `docs/designs/EVOLUTION_LADDER.md` (bottleneck →
laser cooling removes it → the architecture changes → the next bottleneck), with D3's
cache-leakage planner objective built, and D1/D2/D4 measured where the day allows. Predictions in
`PHASE0_CHECKLIST.md` §P0.22 before any run; never solve on the login node; never `git add .`.
