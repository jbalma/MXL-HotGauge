# The gen-0 ratios travel to a second floorplan and the absolute ceilings do not: the 70-core die as a falsification test (D4).

**Figure:** flat ceiling 0.65/0.70 (34-core 0.85/0.90, down by the 1.40x the base predicts); 127 W vs 86 W; cALU the runaway block at every failing shaped rung  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/uniform_density_ladder_d4.sh; python examples/d4_falsification_report.py`

## Caveat that travels with this claim

100 um cells (the 70-core stack is 629 k unknowns at 50 um); read only beside the 34-core matched-grid control, which moved neither cliff. Check "complete" in the file: the shaped 0.45 rung may still be open.

## Files

- `d4_falsification_70core.json` (from `docs/evidence/d4_falsification_70core.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-uniform_density_70core_armD` -> `results/uniform_density_70core_armD`
- `raw-uniform_density_34core_c100_armD` -> `results/uniform_density_34core_c100_armD`
