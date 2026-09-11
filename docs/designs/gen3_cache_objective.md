# Gen 3 design record — the cache-leakage objective on the monolithic die (D3)

**9 September 2026 (§P0.22.2).** The rung's constraint, measured with the planner objective it
needs; the rung's design (a separate storage die) is ARGUED in `EVOLUTION_LADDER.md` §4.
Evidence: `docs/evidence/d3_cache_objective.json` (`examples/d3_objective_report.py`); raw
solves `results/d3_objective_v2/` (twelve planner iterations, corrected ledger) and
`results/d3_objective/` (first pass, six iterations — cache figures valid, die totals not).

## The floorplan

The 34-core 7 nm die as measured (`figures/ref/floorplan_34core.png`): 1126 blocks, 101.1 mm².
The cache zone is every block matching `^(L2|L3)` — 34 L2 slices and 34 L3 slices, **30.1 mm²,
29.8 %** of the die, carrying **54 %** of on-die leakage under the corrected accounting.

## What was built

- `MRParams(zone_targets=[(pattern, T_K)], objective=…)`, `target_for(block)`, `objective_peak`,
  `zone_report` (`thermal/microrefrigeration.py`): the planner plans each block against its own
  target; every hold/convergence test reads the *objective peak*, bit-identical to the plain
  peak when no zone is declared (pinned by `thermal/test_mr_objective.py`, 16 tests).
- `thermal/leakage_ledger.py`: die and per-zone leakage at the solved field, on the loop's own
  reference and curve; a unit counts iff it lands on the solved die (reproduces
  `cold_zone_prize.die_ratios` to four figures — test).
- `mr_comparison.py --mr-objective {peak,cache-leakage} --mr-cold-target-K`; every arm's row
  carries `die_leakage_W`, `cache_leakage_W`, `cache_zone_mean_C`, `cache_zone_max_C`.

## Predictions (written before the run — §P0.22.2)

P1 regression exact · P2 280 K conservation-bound, zone ≥ 292 K · P3 with the scalar 45 K the
caches are lift-bound at ~300–310 K · P4 300 K costs 25–60 % of die power, more than the zone's
own ~30 % · P5 cache leakage ≥ 3× down at 300 K (falsifier < 2×) · P6 Cr:LiSAF shortfall > 90 %.

## The rows (34-core, arm D, 88 CFM, target device, `array_idle` + `array_on`)

Twelve planner iterations, `results/d3_objective_v2/`. "share" is heat removed over the
converged die power; the injected die power is 99.4 W at 1.00 and 59.7 W at 0.60.

| density | objective (cache target) | variant | plan | share | cache zone mean / max | cache leakage (idle) | tiles capped, short |
|---|---|---|---|---|---|---|---|
| 1.00 | hot-spot 92 °C (regression) | — | **0 W** | 0 | 55 / 79 °C | 4.88 W | 0 |
| 1.00 | caches **300 K** | scalar 45 K kept | **71.3 W** | 0.77 | 299.7 / 322.4 K | **1.83 W** (4.88) | 0 |
| 1.00 | caches **280 K** | curve only | **99.4 W** | 1.08 | 289.5 / 316.5 K | **1.35 W** | 0 |
| 1.00 | caches 280 K | scalar 45 K kept | 99.4 W | 1.08 | 289.6 / 320.1 K | 1.36 W | 0 |
| 1.00 | caches 280 K | **Cr:LiSAF on the cache tiles** | 73.5 W delivered | 0.79 | 300.6 / 326.1 K | 1.83 W | **56 tiles, 18.1 W short** |
| 0.60 | hot-spot (regression) | — | 0 W | 0 | 40 / 53 °C | 1.71 W | 0 |
| 0.60 | caches 300 K | curve only / scalar | 35.6 W | 0.63 | 299.5 / 311.1 K | 1.10 W (1.71) | 0 |
| 0.60 | caches 280 K | curve only / scalar | 59.9 W | 1.08 | 290.9 / 306.1 K | 0.85 W | 0 |
| 0.60 | caches 280 K | Cr:LiSAF on the cache tiles | 46.1 W delivered | 0.82 | 296.7 / 310.6 K | 1.00 W | 56 tiles, 9.7 W short |
| 0.60 | caches 300 K | Cr:LiSAF on the cache tiles | 29.8 W delivered | 0.53 | 301.9 / 312.9 K | 1.18 W | 36 tiles, 2.7 W short |

Every objective row stopped on `max_iter` (the baseline planning path, from a converged idle
field): the costs are **lower bounds**, and they moved under 4 % between six and twelve
iterations (69.0 → 71.3 W at 300 K), so they are close ones. At 280 K the plan is scaled to the
injected die power on every iteration ("MR plan wanted 110–121 W from a die dissipating 99.4 W …
scaled to conserve energy") and exceeds the *converged* die power (the die cools and leaks
less), which is the §P0.18.2 over-pull seen from the other side.

## The constraint, before and after

- **Before (gen 0 / gen 1, hot-spot objective):** the planner never touches the caches — 0 W
  at 1.00, coldest engaged tile 290.7 K at 2.00 (§P0.21). The storage material has no job.
- **After (cache-leakage objective, monolithic die):** holding the cache zone at its leakage
  knee is **conservation-bound** (the plan is the whole die's heat and the zone still sits
  10 K above 280 K); holding it 20 K warmer costs **≥ 71 W of the 99 W** the die makes, against
  a zone whose own dissipation is under a third of that. The array cools the ALUs to cool the
  caches: the measured 1.24 K per 40 W of lateral gradient (§P0.7 TEST 1), now from the planner's
  side. What the cooling buys is real — cache leakage **2.7× down at 300 K, 3.6× at 280 K** —
  and it cannot be bought on this die at a price a cooler can pay. **The next binding
  constraint is therefore not on this die: it is the die boundary itself.** That is the gen-3
  design move (`EVOLUTION_LADDER.md` §4.2), and it is ARGUED.
- **The storage material:** on the monolithic die the Cr:LiSAF tiles (η_EQE = 1 ceiling) cap
  56 tiles and fall 18 W short of the plan at 1.00 — they are being asked to lift the compute
  blocks' heat through 200 µm of silicon. On its own die the zone's cold leakage is 1.35 W over
  30 mm² ≈ 0.05 W/mm², against 0.18 W/mm² per 10 µm of film at 290 K: a 3× margin. The
  separation is what makes the material viable (ARGUED from the measured cold leakage).

## Scorecard

| | verdict |
|---|---|
| P1 regression | **confirmed** — 0 W, 89.1 °C, identical to the c1.00 reference row |
| P2 280 K conservation-bound | **confirmed** — plan = 100 % of injected / 108 % of converged die power; zone 289.5 K mean; not holding |
| P3 scalar lift binds | **not as predicted** — conservation scales the plan before the 45 K lift binds; the two variants land on the same plan (`dt45` ≡ `dtnone` here) |
| P4 300 K costs the whole die | **confirmed in direction, number too low** — 77 % of die power, not 25–60 % |
| P5 cache leakage ≥ 3× at 300 K | **below the prediction, above the falsifier** — 2.7× (3.6× at 280 K) |
| P6 Cr:LiSAF cannot | **confirmed in substance** — 56 tiles capped, target not met; the "> 90 %" was framed on the cache tiles' request, the row reports the whole plan's shortfall (18 W of 91 W asked) |

Two of six numerically wrong, both in the direction that strengthens the rung: the monolithic
route is dearer than predicted and the 45 K scalar never got a chance to bind.

## The two-die stack, measured (X4, 11 Sep, §P0.27.4)

The storage die was built with the book's geometry (50 µm, face-to-back above the compute die
on a 5 µm bond, the array above it) and measured at 100 µm: the cache-leakage objective costs
**99.3 W (s = 1.08) at every bond conductivity from 120 to 5 W/mK**, the zone lands at 289 K, the
leakage falls 3.6× — the monolithic rows above to three figures — and at 0.5 W/mK the unpowered
array diverges. The compute die under the hot-spot objective is the reference's (−3.4 %). The
design argued in `EVOLUTION_LADDER.md` §4.2 is falsified in this geometry; the surviving variant
puts the storage die off the compute die's heat path (§4.3). `docs/evidence/gen3_stack.json`.

## Honest limits

Lower-bound costs (baseline planning path; the envelope path with a descent-from-full plan would
give the minimum and was not run because the idle die converges at these densities). One die,
one workload. A 280 K target is 15 K below the 295 K ambient: reaching it on the monolithic die
would refrigerate the heat sink, which this model refuses on conservation rather than prices.
Cr:LiSAF figures are ceilings at η_EQE = 1. The two-die solve (`stacked_memory_study.py`) did not
run today; the gen-3 design stays ARGUED.
