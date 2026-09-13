# The rescue ladder under the per-block envelope shape: plans 18-33 % below the seed shape's, and 3.00 W/mm^2 holds (s = 0.89) where the seed shape had no steady state -- the "ends on conservation at 2.40" reading was the planner's, not the die's: it ends at 3.50 (§P0.29).

**Figure:** per-block plans 11.6 / 56.5 / 113.6 / 176.7 / 202.7 / 248.9 W at 1.20-3.00 (seed 17.3 / 75.3 / 138.7 / 221.5 / 251.2 / none); s 0.10-0.89; 0 tiles capped; max tile 19.3 W/mm^2  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `results/campaign_queue/ladder_power*.tsv (mr_comparison.py --mr-envelope-shape power); python examples/rescue_ladder_shape_report.py`

## Caveat that travels with this claim

34-core, 50 um, arm D. The seed-shape rows remain that planner's plans and the anchor; under the per-block shape the ladder ends on conservation at 3.50 (s = 0.99; 4.00 bistable). Quote every plan with its shape. X1's current ladder is unaffected.

## Files

- `rescue_ladder_power.json` (from `docs/evidence/rescue_ladder_power.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-array_coverage_armD_power` -> `results/array_coverage_armD_power`
- `raw-array_coverage_armD` -> `results/array_coverage_armD`
