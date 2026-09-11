# Start here

**For a fresh session, human or agent. Written 3 September 2026; updated the same day after §P0.18.**

This project has produced six weeks of results and withdrawn a substantial fraction of them. The
withdrawn ones are the ones most likely to resurface. **Read in this order and you will not quote
one.**

---

## 1. Read these four, in this order

| # | file | what it is for | read it before you… |
|---|---|---|---|
| 1 | **`RESULTS_REGISTER.md`** | every number, sorted into **quotable / withdrawn / open** | …quote any figure, anywhere |
| 2 | **`METHODS.md`** | how to drive the codebase and get a correct answer | …run anything |
| 3 | **`REFERENCES.md`** | what the physics rests on; which source wins | …argue about a device number |
| 4 | **`ARCHITECTURE_EVOLUTION.md`** | what the results say about core design | …write about architecture |

Then `PHASE0_CHECKLIST.md` for the full history (long — it is the lab notebook, not a summary),
and `NEXT_SESSION.md` for what the previous session was doing.

`[+]` **Assembling a proposal or a talk?** The evidence is pre-sorted at the repository root:
**`results-quotable/`** (cite these; each carries its caveat) and **`results-historical/`**
(withdrawn, kept so they cannot quietly resurface; several are *mixed*, so read `WHY_RETIRED.md`
before reaching in).

`[!]` **`CLAUDE.md` is loaded automatically and is the short form of all of this.** If it and a doc
here disagree, the doc is newer — fix `CLAUDE.md`.

---

## 2. The five things most likely to trip you

1. **Two defaults changed on 2–3 September** (`--rbb-policy` → `amortized`, `--core-other-policy`
   → `hierarchy-consistent`). `--mr-eta-asf` is **unchanged at 0.32**. An un-flagged run today is not
   the recorded catalogue. Reproduce it with the flag set in `RESULTS_REGISTER.md` §0.
2. **Yb:YLF is not the cold-zone material** and is not a zone material at all. The platform is a
   thin film of **GaAs** or **SiN-encapsulated molecular dye**, >1000 W/mm², η_ASF 0.10–0.60.
3. **The leakage curves cross at ~345 K.** "The measured curve is more pessimistic" is false; so is
   the opposite. The sign depends on which side a point sits.
4. **An `unconverged` solve is neither a hold nor a failure.** Never let one become a ceiling or a
   rescue.
5. **Quote the 2.23× cold-zone improvement, not a percentage.** The percentage has moved four times;
   the ratio has not moved once.
6. **The array's area cannot move a control-arm ceiling.** In the v91 device the tiles,
   waveguides and LPC sit *above* the silicon; `--array-coverage` reaches only the array arms,
   and measured, the charge is zero at the shipped pitch (§P0.18.2). The 2.60 W/mm² array
   ceiling is an **envelope** number — quote the rescue range, not the top rung.
7. **The `V_t` lever costs 45–60 K per 50 mV on the simulated device, not 22 K.** Only the
   25 mV step sits inside the demonstrated 45 K. `LADDER_GEN0` §2's table is superseded.
8. **`dt_max` is a curve now, not a number, and it does not bind on this die** (§P0.19). Keep
   the scalar 45 K alongside the curve — it shapes the plan.
9. **v100 is the device authority (9 Sep; v98 numbers unchanged, equations renumbered, §1.18 and
   §10.9 added), and the target device is its Table 1.1 R640 row** (§P0.20, §P0.21.5). v91's
   10³–10⁴ W/mm² for a *bulk* dye film is withdrawn by v98; the dye is a hot-die platform and
   the extractor's temperature dependence is the transparency cap, not the tail.
10. **Zone materials are decided (§P0.21): Cr:LiSAF storage zone, dye hot zone, no Yb:YLF.** And
    the default cold plate is **single-material** — the dual cold/hot arrangement is a flag
    (`--mr-zone-mode dual`) for measuring a per-architecture layout, never the product default.
    On the hot-spot objective at 2.00 W/mm² it is a 1 % effect (the planner never cools the
    caches there); the default reproduces P0.20 exactly.
11. **The architecture-evolution phase is open (9 Sep, §P0.22).** The ladder is
    `docs/designs/EVOLUTION_LADDER.md`; the cache-leakage objective exists (`--mr-objective`);
    on the monolithic die the cache knee is conservation-bound. **Campaigns go through one
    slurm step** (`scripts/campaign_server.sh`); `on_node.sh` hangs while it runs.
12. **Every rung above ~1.3 W/mm² is a current statement (11 Sep, §P0.27).** At fixed clock and
    0.70 V the laser holds a die whose rails carry 1.5–3× the native current; the dense cluster's
    cALU 2× / 4× that. "Binds: PDN" is a re-sizing statement (no rail model), EM lifetimes carry
    `n` and `E_a`, skew percentages carry `D_ins` and the gradient in kelvin. The recorded solve
    trees hold power maps, not fields — `examples/field_resolve.py` (`METHODS.md` §2.6).
13. **Nothing runs on the head node** (user, 11 Sep): solves, the suite and the pack builds all go
    through the campaign server on job 1507.
14. **Gen 3 as argued is falsified (11 Sep, §P0.27.4).** A storage die between the compute die and
    the sink costs the whole die to hold cold at every bond conductivity; the cache prize
    (2.23×, 280 K knee) stands, the geometry that collects it must keep the storage die off the
    compute die's heat path. Never quote the 9 Sep two-die design as viable.

---

## 3. Where the work stands

**Built and trustworthy:** the thermal/power model, the SPICE leakage curve, the four-arm catalogue,
the MR planner, the evidence set.

**Measured:** one architecture (34-core 7 nm skylake) on one workload (single-threaded LINPACK,
replicated), end to end.

**First step taken (9 Sep):** one architecture change made *because* of a measurement and
re-measured — the dense execution cluster (D1); the argued ladder is written. See
`ARCHITECTURE_EVOLUTION.md` §5 for exactly which rows changed.

---

## 4. The phased plan

### Phase 0 — trust the model (essentially complete)

| item | state |
|---|---|
| Leakage curve is a real device, not CACTI's 11 numbers | **done** (§P0.13) |
| Per-core power accounting reproduces McPAT's own totals | **done** (§P0.16–17) |
| Bus placement matches McPAT semantics | **done**, default changed |
| Catalogue re-measured under corrected inputs | **done** — four arms, 158–159 points each |
| Density ceiling re-measured | **done** — 0.85–0.90 W/mm² flat, 0.60–0.65 shaped |
| **`dt_max` from the device team** | `[+]` **Closed 8 Sep (§P0.20)** — v98's transparency cap fixes the extractor's temperature dependence without a measurement; the target device (Table 1.1) does not bind on this die. Remaining device ask (v98's own): ε beyond 620 nm on high-purity R640, which moves the pump optimum, not the lift |
| Array charged its own area | **done** (§P0.18.2) — the charge is zero at 500 µm / 200 µm |
| SPICE `V_t(T)`, `SS(T)`, `I_on(V,T)`, V/F shape | **done** (§P0.18.3) |
| `--leakage-curve` default decision | `[!]` **OPEN — recommendation made (§P0.18.0: flip to `simulated`), not applied; the user's call** |

### Phase 1 — close the apparatus gaps (next)

1. **Decide the leakage-curve default** — recommendation on record (§P0.18.0: `simulated`);
   apply it or overrule it. Until then an un-flagged run has no catalogue behind it.
2. ~~Get `dt_max`~~ **closed (§P0.19–20)**: derived from v98's transparency cap; not binding here.
   What remains is the book's own priority experiment (ε beyond 620 nm) and the zone-material
   adjudication (v98 Table 10.8 vs the 3 Sep rule).
3. ~~Charge the array its own die area~~ **done** — the charge is zero at 500 µm pitch and
   200 µm burial (§P0.18.2). Open remainder: the LPC's own dissipation on the tile stack and
   the two planner limits the ladder's top exposed (`RESULTS_REGISTER.md` §3).
4. ~~Extend SPICE to `V_t(T)` and a device-derived V/F curve~~ **done** (§P0.18.3). Open
   remainder: run the lever end to end (`clock_headroom.py --vf-source spice`, leakage
   reference scaled by the simulated `10^(ΔV_t/SS(T))`).

### Phase 2 — a second architecture

Re-measure the whole register on a second floorplan and a second workload class. **The purpose is
falsification**: find which of the §1 claims are properties of *this* die. Expect the ratios
(1.4× concentration, 2.23× cold-zone, the 200 µm plateau) to travel and the absolute ceilings not
to.

### Phase 3 — the evolution loop

Change one architectural thing *because* a measurement said to, then re-measure. The first
candidates, in order of evidential support:

1. split the cache onto a separate die (measured constraint — conduction shorts the zones);
2. densify the execution cluster and target the array at it;
3. spend headroom on `V_t` rather than clock (blocked on `dt_max`).

### The second front — future experiments (10 Sep)

`docs/FUTURE_EXPERIMENTS.md`: six ranked experiments (iso-package throughput scaling,
dark-silicon recovery, the accelerator at its real operating point, burst absorption, the
two-die cold-cache stack, the `V_t` lever end to end) beside the ladder. `[!]` **The net-export
energy story is reserved for after the architectural evolution** (v100 Tier III needs a hot
zone past the BEOL wall): the defensible energy claim now is performance per package watt.

### Phase 4 — across ISAs, toward a licensable core

`docs/CODESIGN_PLAN.md` describes the method. `[!]` It is a **plan, not results.** Nothing in the
repository has yet compared two ISAs under the current accounting.

---

## 5. Working rules that have each cost a session

- **Write predictions down before the run.** Four of five in the last two sessions were wrong;
  writing them first is the only reason the corrections were findable.
- **Never site a refinement off an unfinished ladder** — the points still running are the ones
  nearest the cliff.
- **Check a study *consumes* an input before re-running it on a new one.**
- **Prefer the measured neighbour to the derived estimate.** Both failed predictions came from
  turning an *input* ratio into a *result* ratio.
- **Never `git add .`** — list files and let the user stage them.
- **Suite must end at 947 passed, 1 skipped or better.** Do not run it with ~20 campaign workers
  active.
