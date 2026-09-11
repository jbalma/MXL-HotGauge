# Kick-off prompt for the next session

**Rewritten 11 September 2026, after §P0.25 closed and §P0.27 ran (X1/X2 on the recorded fields,
X3 at the book's utilisation; X4 scoped).** Copy the block below verbatim; the one-paragraph form at the
end is the same thing compressed. The 10 September version is in git history.

---

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`.

**Read `docs/START_HERE.md` first**, then, in this order:

| file | read it before you |
|---|---|
| `docs/NEXT_SESSION.md` (11 Sep handoff at the top) | pick anything up — what ran, what is recorded, what is open |
| `docs/RESULTS_REGISTER.md` | quote any number — §0 flag table, §1.3 (now with the burst, X1, X2 and X3 rows), §3 (a rail model and `D_ins` are open), §4 (every rung above ~1.3 W/mm² is a current statement; two control ceilings; ~5 W/mm² steady tile demand, 13 W/mm² transient) |
| `docs/designs/EVOLUTION_LADDER.md` §2.3 (new) + `gen1_dense_cluster.md` | write about architecture — gen 1's next constraint is the PDN, MEASURED as `J`, ARGUED as a limit |
| `docs/PHASE0_CHECKLIST.md` §P0.27 (predictions, the X1/X2 and X3 RESULTs, §P0.27.4 X4 scope) | rely on any 11 Sep number |
| `docs/PHYSICAL_DESIGN_CONSTRAINTS.md` + `docs/chip_design_lit/SoC-Physical-Design.pdf` (book page = PDF page − 21) | design the next rung |
| `docs/FUTURE_EXPERIMENTS.md` | run anything — status current to 11 Sep; net export stays reserved |
| `docs/METHODS.md` §2.2, §2.6 | touch the node — **nothing runs on the head node** (solves, the suite, pack builds: all through `scripts/campaign_server.sh`); recorded solve trees hold power maps, not fields — `examples/field_resolve.py` |
| `CLAUDE.md` | everything else |

**The state (11 Sep).** F4's six burst points are recorded (register §1.3, `results-quotable/17-…`).
X1/X2 are recorded on 34 re-solved recorded fields (`results/fields/`, `docs/evidence/pdn_em_skew.json`,
`results-quotable/18-…`): the rescue ladder is a current ladder (1.29–2.88× the native rail current
from 1.00 to 2.40 W/mm² at 0.70 V), the ×0.5 cluster doubles the peak rail current exactly, the
cooled die's worst block ages 12–50× faster than the native die's (Black, n = 2, 0.9 eV), thermal
skew grows with every rung (uniformity is not a clock lever — P6 falsified). **X3 is recorded** (§P0.27.3, register §1.3, `results-quotable/19-…`): at the book's 70 % utilisation the dense cluster is 1.22× denser in silicon, holds every rung to 243 W, and costs 1.2–1.4× a same-utilisation reference at the die-wide rungs; 100 µm, never beside a 50 µm row. X4 is scoped with predictions
(§P0.27.4) and not built. The proposal pack is `proposal_pack_2026-09-11/`.

## The goal of this session

1. **X4 — the gen-3 stack** (§P0.27.4; the day's work): a storage-die floorplan carrying the
   reference's L2/L3 blocks at their positions and powers, a three-layer spec (pixel / storage
   / bond / compute) in `die_stack.py`, `stacked_memory_study.py` or a new driver at
   `--cell-um 100`, Cr:LiSAF tiles on the storage die under the cache-leakage objective, the bond
   conductivity as the swept variable (P15). Predictions P14–P17 are written; add any before
   changing them. **Re-run the 34-core arm-D anchor (2.00 W/mm²: plan 138.73 W, peak 93.875 °C)
   after any planner edit** — `die_stack.py` and `microrefrigeration.py` both count.
2. **If the day allows: a first rail model** (register §3) — `IR ∝ local P/A` on a stated stripe
   pitch, `V_eff = V_dd − IR` into `clock_search`, so "binds: PDN" becomes a clock cost like the
   skew term. Predictions first.

**Not this session:** D2 stays argued; nothing on net export (reserved); no new floorplan family
beyond X3's; no accelerator re-run.

## What the patent- and proposal-facing text may and may not say

- Measured on the 34-core die: register §1 including the burst, X1 and X2 rows — always with the
  W/mm² operating point, the V/F source, the leakage curve, the grid, and for X1/X2 the stated
  constants (`V_dd`, `n`, `E_a`, `D_ins`) beside every derived figure; the current ratios and the
  gradients in kelvin are the measured part.
- Argued: the two-die design, D2, EM lifetimes and accelerations, every skew percentage, "binds:
  PDN" (a re-sizing statement, not a failure), any cubic-law clock above the V/F table.
- Never: a clock from above the V/F table; "N× the compute" from a fixed-core-count ladder; a
  GA100 power as a fact; the extractor's ideal design point as needed; Yb:YLF in a zone; net
  export from any current rung; a burst temperature above 127 °C (say non-viable); the withdrawn
  list in register §2.

## How to work here

Predictions in `PHASE0_CHECKLIST.md` before any run (§P0.27's sixteen: eleven confirmed, one
falsified, four off in magnitude). Prefer the measured neighbour to the derived estimate. An
`unconverged` row is neither a hold nor a failure. Nothing on the head node. Never `git add .`;
list the files. Re-run the anchor after any planner edit.

---

## Short intro prompt (the same session, in one paragraph)

Continue MXL-HotGauge at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge`. Read `docs/START_HERE.md`,
then `docs/NEXT_SESSION_PROMPT.md` (11 Sep) in full — it is the brief. Context: `docs/NEXT_SESSION.md`
(11 Sep handoff), `docs/RESULTS_REGISTER.md` (§1.3's burst / X1 / X2 rows; §3; §4's current-ladder
rule), `docs/designs/EVOLUTION_LADDER.md` §2.3, `docs/PHASE0_CHECKLIST.md` §P0.27 (X1/X2 and X3 RESULTs, X4 scope), `docs/PHYSICAL_DESIGN_CONSTRAINTS.md`, `docs/METHODS.md` §2.2/§2.6,
`CLAUDE.md`. Goal: build and measure X4, the gen-3 stack with the 3D
chapter's geometry (§P0.27.4, P14–P17), then a first rail model if the day allows. Predictions
before any run; **nothing on the head node** (campaign server); re-run the 34-core arm-D anchor
after any planner edit; never `git add .`; an unconverged row is neither a hold nor a failure.
