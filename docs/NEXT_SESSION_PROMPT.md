# Kick-off prompt for the next session

**Rewritten 27 October 2026 (evening), after §P0.44–§P0.45.** Copy the block below verbatim; the
one-paragraph form at the end is the same thing compressed.

---

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`.

**Read `docs/START_HERE.md` first** (trip list 24–27 are the recent ones; **26 and 27 are 27 Oct**), then, in this order:

| file | read it before you |
|---|---|
| `docs/NEXT_SESSION.md` (27 Oct handoff at the top; 19–20 Sep below it) | pick anything up — it lists two decisions waiting on the user |
| `docs/RESULTS_REGISTER.md` | quote any number — §0; §1.2 (the memory-die row); §1.3 (the cache-latency row); §3 (**the two-die planner item, with the specifics §P0.45 added**; the cold-zone item; the DRAM-die item closed); §4 (three new constraints: a memory die's heat path is the cost; the isolation's role reverses; cache hit latency is not a lever) |
| `docs/PHASE0_CHECKLIST.md` §P0.44 and §P0.45 (predictions, the three amendments, RESULTs) | rely on any 27 Oct number — 17 predictions scored, 4 confirmed |
| `docs/designs/EVOLUTION_LADDER.md` §4.3 (the 27 Oct block), §7, §8 | write about architecture |
| `docs/photonic_cooling/MXL-006-PRO/Update/` — the memo (§6.6b lead note, **§6.6c**, §8.2), `make_patent_figures.py`, `figures/pat_fig10.png` (new) and `pat_fig6.png` (fixed; both VIEWED 27 Oct) | touch the patent story or the drawings; rebuild with `build_memo.sh` (pandoc, the one head-node exception) |
| `docs/METHODS.md` §2.2 (**`--gres=gpu:0` and explicit `-c`/`--mem` on every `srun` — job 2748 holds the user's ollama step**), §4.2c (the memory die and its five traps), §6 | touch the node — **nothing runs on the head node**; restart the server with `nohup srun --jobid=2748 --overlap -n1 -c 80 --mem=160G --gres=gpu:0 --cpu-bind=none scripts/campaign_server.sh >> results/campaign_queue/server.log 2>&1 &` (check `squeue -u jbalma`); docker works inside the step now |
| `CLAUDE.md` | everything else |

**The state (27 Oct, evening).** Suite 1132 passed, 1 skipped. Anchors (2.00 W/mm²): seed 138.72881 W /
93.8752 °C; per-block 113.63869 W / 91.5424 °C (reproduced after the memory-die edits). `results-quotable/`
has 36 items. What is MEASURED now: the DRAM die's three placements (§P0.44 — the banks sit at the die's
area-average temperature; the cost is the heat path; 2.5D free, far face −6 / +6 / +16 W by its own sink,
8-high memory-on-logic +40 W or no hold), the hot-end cache die's lack of an unaided steady state, the
HP ledger at 1.00 W/mm² (red by 4–6 W), and that cache hit latency is not a throughput lever on CoMeT's
kernels (§P0.45). What is PLANNER-LIMITED: the cold-cache ledger at 2.00 W/mm² and on the hot-end trace,
and the storage array's true need under the far-face DRAM die — all for one reason.

## The plan — in this order

1. **The two-die planner** (register §3 names the specifics; `thermal/microrefrigeration.py`,
   `_run_mr_clipping_envelope`): an envelope scalar PER DIE (the tile wiring already knows which die a
   block is on — `TwoSinkWiring.storage_blocks`), the storage die's scalar seeded from its HOT-state need
   (its leakage at the diverged field's temperature plus the far-face and isolation inflows), and per-zone
   caps of own dissipation PLUS inflow (the per-block shape's cap cannot remove inflow; the seed shape is
   uniform per block and over-drives). Default paths byte-identical; both anchors after the edit; §P0.37's
   1.00 W/mm² rows and §P0.44's far-face rows as the regression (the latter should lose their 1.9–5.9 W
   storage share). Predictions first.
2. **Then the §P0.45 ladder again** (`scripts/cold_zone_ledger_ladder.sh`, both shapes; the seed rows at
   2.00 and every hot-end row) — the question "does a cold zone pay on a leaky cache" is unread, not red.
3. **§P0.44 follow-ups:** an 8-high stack resolved die by die (`StackSpec` with n die elements and n − 1
   bonds); the 2.5D form on a real interposer (one slab now); CoMeT's bank temperatures (lower
   `sampling_interval`) for the 2.5D / 3D rows.
4. The LSTP-cache catalogue as default (the user's call, §P0.42); dynamic rails and a metal-stack estimate
   for 402; the cropped die on a 25 µm grid; the f_max model's architecture inputs; D2; Phase 2; net export
   stays reserved.

**Decisions waiting on the user:** flip `DEFAULT_COLD_ZONE_PATTERN` to `'^(L2|L3)(_[0-9]+)?$'`? Make the
LSTP-cache trace the default? Build the two-die planner next (recommended)?

**Rules, unchanged:** predictions in `PHASE0_CHECKLIST.md` before any run, amendments recorded AS
amendments (§P0.44 had two, §P0.45 one); an `unconverged` row is neither a hold nor a failure; a row with
s > 1 is envelope-only; a row planned from a diverged baseline is planner-limited; quote every plan with
its envelope shape, every clock with its V/F source, limiter AND rail assumption, every throughput with
IPC(f) and its memory arrangement, every dense-cluster row with its unit shape, every cache-objective row
with its zone pattern and cell class, every memory-die row with placement / k_eff (via count) / far-face R /
dies / W per die / shape, never a memory power (the DRAM model is uncalibrated); the anchor (both shapes)
after any planner or stack edit; nothing on the head node (`--gres=gpu:0` on every step); write queue
files elsewhere and `mv` them in; kill a campaign's `xargs` before its workers; never `git add .`; list the
files. Every drawing caption says MEASURED or ARGUED, and LOOK at a regenerated drawing before it goes out.

---

## Short intro prompt (the same session, in one paragraph)

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`. Read `docs/START_HERE.md` (items
24–27), then `docs/NEXT_SESSION_PROMPT.md` (27 Oct) in full — it is the brief. Context: `docs/NEXT_SESSION.md`
(27 Oct handoff; three decisions waiting), `docs/RESULTS_REGISTER.md` (§1.2 memory-die row; §1.3
cache-latency row; §3 the two-die planner item; §4), `docs/PHASE0_CHECKLIST.md` §P0.44–§P0.45, ladder §4.3,
the memo (§6.6b lead note, §6.6c, §8.2, FIG. 10), `docs/METHODS.md` §2.2 / §4.2c, `CLAUDE.md`. The plan:
(1) the two-die planner — an envelope scalar per die, the storage die's seeded from its hot-state need,
per-zone caps of own dissipation plus inflow; anchors and §P0.37 / §P0.44 regressions; (2) the §P0.45
ladder again; (3) the 8-high stack die by die, the 2.5D interposer, CoMeT bank temperatures; (4) the LSTP
catalogue default, rails, the 25 µm die, f_max inputs, D2, Phase 2. Predictions before any run; nothing on
the head node (`srun … --gres=gpu:0 -c … --mem=…` on job 2748; the campaign server through
`results/campaign_queue/`; `mv` queue files in); never `git add .`.
