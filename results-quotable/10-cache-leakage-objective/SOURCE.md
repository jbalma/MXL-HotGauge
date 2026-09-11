# The cache-leakage prize cannot be collected on the compute die at a price a cooler can pay: holding the caches at their knee is conservation-bound and 20 K above it costs 77 % of die power (lower bound).

**Figure:** 280 K: the whole die (99 W plan on a 99 W die, zone at 289.5 K); 300 K: >= 71 W = 77 %; cache leakage 2.7x / 3.6x down; Cr:LiSAF tiles 56 capped, 18 W short  
**Register:** `docs/RESULTS_REGISTER.md` §1.2  
**Reproduce:** `scripts/d3_objective_smoke.sh; python examples/d3_objective_report.py`

## Caveat that travels with this claim

Monolithic 34-core die, arm D, target device, planner objective cache-leakage (§P0.22.2). Costs are LOWER bounds (baseline planning path; +3 % from 6 to 12 iterations). The measured leg of the separate-die argument, not a two-die measurement. Cr:LiSAF figures are ceilings at eta_EQE = 1. results/d3_objective/ is the first pass: cache figures valid, die_leakage_W totals NOT (ledger rule).

## Files

- `d3_cache_objective.json` (from `docs/evidence/d3_cache_objective.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-d3_objective_v2` -> `results/d3_objective_v2`
- `raw-d3_objective` -> `results/d3_objective`
