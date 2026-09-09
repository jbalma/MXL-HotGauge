# WITHDRAWN — "The flat-die ceiling is 1.0-1.2 W/mm^2." Also: "the simulated curve makes the ceiling higher because its hot tail is gentler."

**Say instead:** 0.85-0.90 W/mm^2, measured under corrected accounting (see quotable/03)  
**Register:** `docs/RESULTS_REGISTER.md` §2

## Why it failed

Two independent corrections both push the ceiling down: the leakage curve and the per-core accounting. The DIRECTIONAL claim was also wrong -- the two curves cross at ~345 K, so the sign of the effect depends on which side a point sits.

## What survives in these files

The ladders themselves are valid measurements OF THEIR OWN CONFIGURATION and are the control the corrected ladder is read against.

## Files

- `uniform_density_probe.json` (from `docs/evidence/uniform_density_probe.json`)
- `uniform_density_curve_compare.json` (from `docs/evidence/uniform_density_curve_compare.json`)
- `uniform_density_curve_compare_fine.json` (from `docs/evidence/uniform_density_curve_compare_fine.json`)
- `uniform_density_curve_compare_gidl_off.json` (from `docs/evidence/uniform_density_curve_compare_gidl_off.json`)
- `uniform_density_curve_compare_gidl_off_fine.json` (from `docs/evidence/uniform_density_curve_compare_gidl_off_fine.json`)
