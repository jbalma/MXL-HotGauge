# Off the compute die's heat path the cache prize costs a ninth of the sink-side stack's, and the storage die reaches its 280 K knee (section P0.37, the two-sink gen-3 stack, thermal side).

**Figure:** 1.00 W/mm^2, caches at 280 K on the dye storage array, 100 um isolation, 3 K/W far-face sink: 10.9 / 13.7 / 26.2 / 75.1 W at k = 0.025 / 0.1 / 0.5 / 5 W/mK, all on the storage array (s 0.11-0.81), compute array 0 W, zone 280 K mean / 282 K max, cache leakage 3.5-4.0x down (sink-side stack and monolithic die: 99.4 W, s 1.08, 286-287 K); no unpowered steady state with the far face adiabatic or at 10-30 K/W; 13.7 / 20.1 / 39.8 W at 3 / 1 / 0.3 K/W; Cr:LiSAF capped at every isolation (1.7 W short at k = 0.025, zone 290 K, 2.9x); laser 7.0 W net for 2.78 W saved  
**Register:** `docs/RESULTS_REGISTER.md` §1.2, §2, §3, §4  
**Reproduce:** `scripts/two_sink_ladder.sh; python examples/two_sink_report.py`

## Caveat that travels with this claim

Thermal side only: the isolation carries no via copper; the interface's construction is ARGUED. 100 um cells, seed shape, curve only, 12 planner iterations; held = converged descent with the worst cache block inside the 2 K tolerance. Cr:LiSAF is a ceiling at eta_EQE = 1. The 2.00 W/mm^2 rows are planner-limited (one envelope scalar over two dies). Pass the cache-only zone pattern. THE LEAKAGE SAVED IS AN UPPER BOUND: the McPAT input gives the caches HP devices (item 33).

## Files

- `two_sink.json` (from `docs/evidence/two_sink.json`)
- `gen3_stack.json` (from `docs/evidence/gen3_stack.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-two_sink_v3` -> `results/two_sink_v3`
- `raw-two_sink_v2` -> `results/two_sink_v2`
- `raw-two_sink` -> `results/two_sink`
- `raw-anchor_2026-09-19` -> `results/anchor_2026-09-19`
