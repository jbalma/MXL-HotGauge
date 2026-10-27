# D1 under the per-block envelope shape: the 2x cluster holds every reference rung to 243 W and the 4x cluster holds 202 W (both lost under the seed shape -- the lost rungs were the planner's); the die-wide premium is 1.1-1.2x (x0.5) and 1.3-1.7x (x0.25) (section P0.34).

**Figure:** x0.5: 6.1 / 17.4 / 73.6 / 130.4 / 188.5 W at 111 / 121 / 162 / 202 / 243 W (s 0.84 at 243), premium 2.0 / 2.0 / 1.20 / 1.20 / 1.08x; x0.25: 31.4 / 41.5 / 104.3 / 166.1 W to 202 W (s 0.89), premium 4.9 / 4.0 / 1.68 / 1.51x; x0.25 at 243 W envelope-only (s 1.02); plans 9-59 % below the seed rows; both anchors reproduced (138.72881 / 113.63869 W)  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `SHAPE=power OUT=results/d1_family_power ARRAY_ONLY=1 scripts/d1_family_ladder.sh > results/campaign_queue/d1_power.par4.tsv (node); python examples/d1_family_power_report.py`

## Caveat that travels with this claim

Matched die WATTS, arm D, 50 um, target device, scalar 45 K, per-block shape; premiums like-for-like within a shape only (the seed-shape record is 11-dense-cluster-family). Never quote the x0.25 243 W row as a hold.

## Files

- `d1_exec_density_family_power.json` (from `docs/evidence/d1_exec_density_family_power.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-d1_family_power` -> `results/d1_family_power`
- `raw-anchor_2026-09-13` -> `results/anchor_2026-09-13`
