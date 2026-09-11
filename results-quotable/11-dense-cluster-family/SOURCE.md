# The rescue travels to a denser execution cluster, and density is paid for in cooling watts: the first re-measured design change (D1).

**Figure:** x0.5: holds to 202 W, plan 1.17-2.8x the reference; x0.25: holds to 162 W, 1.65-6.9x; 0 tiles capped; each loses the top rung to the stability boundary  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `examples/generate_exec_density_family.py; scripts/d1_family_ladder.sh; python examples/d1_family_report.py`

## Caveat that travels with this claim

Matched die WATTS, not density (the members are 0.90x / 0.85x the reference area). Arm D, 50 um, target device, scalar 45 K. Plans normalised to a 92 C landing at 0.3247 K/W. Control-arm cliffs may still be open in the result file (check "control_cliff_W"."bracketed").

## Files

- `d1_exec_density_family_result.json` (from `docs/evidence/d1_exec_density_family_result.json`)
- `d1_exec_density_family.json` (from `docs/evidence/d1_exec_density_family.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-d1_family_arr` -> `results/d1_family_arr`
- `raw-d1_family` -> `results/d1_family`
