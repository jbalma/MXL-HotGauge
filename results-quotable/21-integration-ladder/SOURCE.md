# The rescue is insensitive to the degree of integration: the plan and the top rung barely move as the tile plane is brought from 200 um to 20 um above the transistors, and thinning to 20 um makes the die less forgiving (§P0.28, for the MXL-006 memo).

**Figure:** 2.00 W/mm^2, 500 um pitch: 126 / 113 / 119 / 131 W at 200 / 100 / 50 / 20 um burial; 200 um pitch 121 / 115 / 114 / 122 W; 2.60 holds at every burial; 3.00 only at intermediate burial (289 W at 100 um); tile flux 5.0 / 8.2 W/mm^2 at 2.00, 14.8 at 3.00  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/integration_ladder.sh; python examples/integration_ladder_report.py`

## Caveat that travels with this claim

100 um cells beside the 100 um reference; the 3.00 rows are under the injected energy cap; uniform seed envelope shape (the power shape may favour finer pitch at shallow burial -- open). A decoupled cold plate on a 200 um die is within 10 % of a die-integrated array on this floorplan.

## Files

- `integration_ladder.json` (from `docs/evidence/integration_ladder.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-integration` -> `results/integration`
- `raw-x3_u70` -> `results/x3_u70`
