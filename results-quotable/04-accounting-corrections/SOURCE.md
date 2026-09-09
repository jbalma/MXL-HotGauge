# Most of the recorded catalogue's thermal divergence was an artefact of two wrong inputs, not physics. The pipeline leakage curve is not a device.

**Figure:** 94 -> 8 diverging of 145 control points; leakage curve 57, accounting 22, bus 0  
**Register:** `docs/RESULTS_REGISTER.md` §1.4  
**Reproduce:** `python examples/catalogue_arm_compare.py`

## Caveat that travels with this claim

This is NOT a restated density ceiling -- these are heterogeneous catalogue points at product densities, not a ladder. For the ceiling see 03.

## Files

- `catalogue_arm_compare.json` (from `docs/evidence/catalogue_arm_compare.json`)
- `device_leakage_asap7.json` (from `docs/evidence/device_leakage_asap7.json`)
- `device_leakage_spice_asap7.json` (from `docs/evidence/device_leakage_spice_asap7.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-rerun_arm_A` -> `results/rerun_arm_A`
- `raw-rerun_arm_B` -> `results/rerun_arm_B`
- `raw-rerun_arm_C` -> `results/rerun_arm_C`
- `raw-rerun_arm_D` -> `results/rerun_arm_D`
