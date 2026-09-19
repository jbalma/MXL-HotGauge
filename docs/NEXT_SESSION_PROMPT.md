# Kick-off prompt for the next session

**Rewritten 13 September 2026 (evening), after §P0.31–§P0.34 landed.** Copy the block below
verbatim; the one-paragraph form at the end is the same thing compressed. The 13 Sep morning
version is in git history.

---

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`.

**Read `docs/START_HERE.md` first** (trip list items 15–17 are new), then, in this order:

| file | read it before you |
|---|---|
| `docs/NEXT_SESSION.md` (13 Sep evening handoff at the top) | pick anything up — what ran, what is recorded, what is open, what was not rebuilt |
| `docs/RESULTS_REGISTER.md` | quote any number — §0 (`--vf-source`: every clock carries its source; every plan its shape), §1.3 (the generalized-f_max, cluster-transport and D1-per-block rows; the F1c row re-labelled gate-only with IPC(f)), §1.6 (the extended sweep, the reliability ladder), §2 (three new withdrawals: the 4.17 GHz "device ceiling", D1's "lost top rungs", §P0.28's "thinning does not help"), §3, §4 (IPC(f), limiter, the cluster exception to the 5 W/mm² rule) |
| `docs/PHASE0_CHECKLIST.md` §P0.31–§P0.34 | rely on any 13 Sep number — the predictions and their scorecards, which were mostly wrong in instructive ways |
| `docs/designs/EVOLUTION_LADDER.md` §2.2 (two corrections), §2.4 (the 8× / 16× clusters), §4.3 | write about architecture |
| `docs/photonic_cooling/MXL-006-PRO/Update/MXL-006_update_memo.md` | touch the patent story — the ">1000 W/mm²", ">10 GHz", §6.3, §8 and §8.1 rows changed on 13 Sep; rebuild the `.docx` / `.html` with `build_memo.sh` (pandoc, the one head-node exception) if `NEXT_SESSION.md` says it was not done |
| `docs/METHODS.md` §2.2, §2.6, §3 (the f_max model, the `fmax` search, IPC(f)) | touch the node — **nothing runs on the head node**; campaigns, tests, reports and pack builds go through `scripts/campaign_server.sh` on job 1507 via `results/campaign_queue/<name>.par<N>.tsv`; restart with `nohup srun --jobid=1507 --overlap -n1 --cpu-bind=none scripts/campaign_server.sh >> results/campaign_queue/server.log 2>&1 &` |
| `CLAUDE.md` | everything else |

**The state (13 Sep evening).** Suite 1098 passed, 1 skipped (node). Both anchors reproduce
(seed 138.73 W / 93.875 °C; per-block 113.6 W / 91.5 °C at 2.00 W/mm²). The default planner
shape is still `seed`. The recorded F1c clocks (4.17 GHz) are the gate-only ceiling; under the
generalized model the laser arm's ceiling at the 92 °C target is 3.76–3.83 GHz, `reliability:tddb`.

## The plan for the next session — in this order

1. **The surviving gen-3 geometry** (ladder §4.3): a two-sink `StackSpec` (compute die's sink and
   dye array on one face, the storage die with Cr:LiSAF tiles on the other; 3D-ICE's `bottom heat
   sink`) or a 2.5D side-by-side floorplan with an isolating channel. Predictions first; the anchor
   (both shapes) after any stack edit; 100 µm cells; the cache-leakage objective at 280 K.
2. **The dense cluster's cold-end wall** (§P0.32): the 16× cluster at 100 µm pitch loses its top
   rung because the tile above the cALU is driven to 253 K where the dye's capability collapses.
   Re-run the 8× / 16× top rungs at 100 µm pitch with `--mr-extractor gaas-retuned` and with a
   dual-zone arrangement (`--mr-zone-mode dual` with a cold-capable material over the cluster —
   a per-architecture layout, measured, never the default), and at 50 µm pitch with the dye.
   Predictions first; quote s and the capped-tile count on every row.
3. **A rail model** (register §3): `V_eff = V_dd − IR` with `IR ∝ local P/A` into the generalized
   clock search, so "binds: PDN" becomes a supply term; the 8× / 16× clusters (8–16× the reference's
   cALU current density) are where it matters first.
4. **The fmax model's architecture inputs** (register §3): a synthesised-core timing report for the
   wire share and the FO4 depth; until then every clock from `--vf-source fmax` is quoted with the
   sensitivity (wire ±3 %, pipeline ×2) and its limiter.
5. D2 (the `V_t` lever end to end); Phase 2 (second workload class); net export stays reserved.

**Not this session:** the ISA comparison; the proposal-pack rebuild unless a number is quoted
from it.

**Rules, unchanged:** predictions in `PHASE0_CHECKLIST.md` before any run; an `unconverged` row is
neither a hold nor a failure, an unfinished planner descent is neither, and **a row with s > 1 is
envelope-only, never a hold**; quote every plan with its envelope shape, every clock with its V/F
source and the limiter its row names, every throughput with IPC(f) and the benchmark; re-run the
34-core arm-D anchor (both shapes) after any planner or stack edit; nothing on the head node;
never `git add .`; list the files.

---

## Short intro prompt (the same session, in one paragraph)

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`. Read `docs/START_HERE.md`
(items 15–17 new), then `docs/NEXT_SESSION_PROMPT.md` (13 Sep evening) in full — it is the brief.
Context: `docs/NEXT_SESSION.md` (13 Sep evening handoff), `docs/RESULTS_REGISTER.md` (§0's
source-and-shape rules; the three new §1.3 rows; the three new §2 withdrawals), `docs/PHASE0_CHECKLIST.md`
§P0.31–§P0.34, `docs/designs/EVOLUTION_LADDER.md`, the MXL-006 memo, `docs/METHODS.md` §2.2 / §2.6 /
§3, `CLAUDE.md`. The plan, in order: (1) the two-sink gen-3 stack; (2) the dense cluster's cold-end
wall (GaAs / dual-zone / 50 µm pitch on the 8× / 16× top rungs); (3) a rail model into the
generalized clock search; (4) the f_max model's architecture inputs; (5) D2, Phase 2. Predictions
before any run; s > 1 is envelope-only; quote every plan with its shape, every clock with its
source and limiter, every throughput with IPC(f); the anchor (both shapes) after any planner or
stack edit; nothing on the head node (campaign server on job 1507); never `git add .`.
