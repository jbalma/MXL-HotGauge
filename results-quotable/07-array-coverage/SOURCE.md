# The array charged its own footprint costs nothing at the shipped pitch: a quarter-coverage array holds the same ceiling on the same minimum plan. Under corrected inputs the laser holds from 1.20 to 2.60 W/mm^2.

**Figure:** coverage 0.26 (644/1126 blocks under gaps, 74.8 mm^2 reserved): same rung, Q within 1.6 % at a common peak; array_idle fails 1.20, array_on holds 2.60  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/array_coverage_ladder_armD.sh | scripts/campaign_inner.sh; python examples/array_coverage_report.py`

## Caveat that travels with this claim

Coverage cannot move a CONTROL-arm ceiling -- the control has no array. The 2.60 is an ENVELOPE result: the array removes more heat than the converged die dissipates and the 3.00 failure is "envelope insufficient". Quote the rescue range and the cost ladder, never the top rung as an operating point. 500 um pitch, 200 um burial, 34-core, 88 CFM, target 92 C, arm D.

## Files

- `array_coverage_armD.json` (from `docs/evidence/array_coverage_armD.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-array_coverage_armD` -> `results/array_coverage_armD`
