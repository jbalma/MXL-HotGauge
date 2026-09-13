# The cooling-system ledger: refrigerated air is beaten at every rung (1.6x at 1.20, 3.7x at 1.60) and has no solution above 1.60 W/mm^2; a chilled direct-die liquid plate beats the laser until its coolant goes sub-zero (the crossover is between 2.00 and 2.40 on this die). "> 10x COP" is the air statement where air has no solution.

**Figure:** air needs 273 / 243 / none / none K ambient; liquid plate 293 / 273 / 263 / 243 K inlet; system COP air 1.65 / 0.52 / - / -, liquid 17.3 / 3.94 / 3.02 / 0.97, photonic 2.59 / 1.90 / 1.58 / 1.29 at 1.20 / 1.60 / 2.00 / 2.40 W/mm^2  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts (queue): results/campaign_queue/cop_ambient.par8.tsv, cop_liquid2.par8.tsv; python examples/cooling_system_ledger.py`

## Caveat that travels with this claim

Temperatures MEASURED (control arm, 100 um, arm D, calibrated 35 W fan); pricing ARGUED and stated (LCEstimator chiller COP gamma 0.4 with sub-zero penalties, pump 6.85 W held). The laser side is the recorded seed-shape plan (an upper bound, §P0.29). Condensation control and pump flow^3 scaling are not priced.

## Files

- `cooling_system_ledger.json` (from `docs/evidence/cooling_system_ledger.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-cop_ambient` -> `results/cop_ambient`
- `raw-array_coverage_armD` -> `results/array_coverage_armD`
