# The array holds a GA100-class accelerator from 700 W to 2600 W on a direct-die microchannel plate where the conventional stack has no steady state; the top rung ends on conservation; a concentrated eight-SM kernel at 700 W is held for 32 W (F3).

**Figure:** 102 / 514 / 1289 / 2244 W removed at 1000 / 1400 / 2000 / 2600 W; s = 0.98 at 2600; occ8 700 W: 32 W; max tile flux 5.3 W/mm^2  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `SHAPE=power ARRAY_ON_ONLY=1 TOL=1.0 MAXITER=100 scripts/accel_f3_ladder.sh; python examples/accel_f3_report.py --base results/accel_f3_power_tol1`

## Caveat that travels with this claim

The control runaway at 700 W is a simulated-curve, ASSUMED 25 %-leakage result on an uncalibrated power split (calibrated: false); 100 um cells; needs the power envelope shape (accel_f3.json shows the seed shape failing every kernel point) and tol 1.0 (accel_f3_power.json rows are the same answers flagged unconverged on a 0.05 K residual). The device is 150x under-used: max tile flux 5.3 W/mm^2.

## Files

- `accel_f3_power_tol1.json` (from `docs/evidence/accel_f3_power_tol1.json`)
- `accel_f3_power.json` (from `docs/evidence/accel_f3_power.json`)
- `accel_f3.json` (from `docs/evidence/accel_f3.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-accel_f3_power_tol1` -> `results/accel_f3_power_tol1`
- `raw-accel_f3_power` -> `results/accel_f3_power`
- `raw-accel_f3` -> `results/accel_f3`
