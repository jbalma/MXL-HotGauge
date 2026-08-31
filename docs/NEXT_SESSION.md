# Next session — handoff, 31 August 2026

Read this first, then `docs/PHASE0_CHECKLIST.md` (live state; **§P0.11 and §P0.10 are last
session**, §P0.9 the night before), `docs/DARPA_CLAIM_REGISTER.html`, and `CLAUDE.md`.

Baseline: `python -m pytest HotGauge/HotGauge -q` → **800 passed, 1 skipped**, ~6 min on the head
node. Keep it there. Slurm: `squeue -u jbalma` for the jobid, then `scripts/on_node.sh <jobid>
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

## The one thing to do first

**One architecture, one die, until the physics is verified end to end.** The ISA variants, the
accelerator die and the n-core sweeps all stay parked. The die is the 34-core 7nm skylake
floorplan and nothing else moves.

On that die, the open physics items in order:

1. **PTM SPICE cards.** Now the single largest uncertainty and it bounds both terms above: the
   leakage curve clamps at 310 K and is extrapolated above 400 K, and the flat-die cliff at
   1.0–1.2 W/mm² is a direct function of that curve. Everything else waits behind it.
2. **Re-run the recovery-affected evidence** — no re-solves needed, see below.
3. **Then** the RBB default decision and one deliberate catalogue re-run.

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
- **Recovery crosses to export at 408 K** with the v91 target extractor and a 90 % laser.
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
