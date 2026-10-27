# The 8x cluster's lost top rung was the DYE'S temperature dependence, not the film concept: with a hot-zone material whose capability rises on cooling it holds 243 W; a dual-material layout over the execution column suffices; plain GaAs fails; finer pitch makes the dye worse (section P0.35).

**Figure:** retuned-enhanced GaAs: 8x holds 243 W at s 0.88 (20 um) / 0.91 (5 um), tile 235-242 K at 215 W/mm^2, 0 capped; 202 W plan 173.8 -> 142.9 W; dual = whole array on the 8x; 16x at 243 W no steady state with 0 capped; plain GaAs 5954 tiles capped; dye at 50 um pitch: all four rows lost, 59-87 capped; eta_ASF at the coldest tile 0.010-0.016 (dye ~0.10)  
**Register:** `docs/RESULTS_REGISTER.md` §1.3, §2  
**Reproduce:** `scripts/cluster_coldend_ladder.sh (write elsewhere, mv into results/campaign_queue/); python examples/cluster_coldend_report.py`

## Caveat that travels with this claim

The retuned-enhanced GaAs is v100 Table 1.1's CEILING design point: an upper bound on what a cold-tolerant hot-zone material buys, at 6-10x the pump power per watt lifted at the coldest tile. A dual-material array is a per-architecture layout: measured, never the default. 50 um cells, per-block shape, matched die watts.

## Files

- `cluster_coldend.json` (from `docs/evidence/cluster_coldend.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-cluster_coldend` -> `results/cluster_coldend`
