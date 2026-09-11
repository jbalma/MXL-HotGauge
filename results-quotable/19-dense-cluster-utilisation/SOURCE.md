# At the book's floorplan overheads (U = 70 %, T = 15 %, 20 um cache halos) the "2x denser" cluster is 1.22x denser in silicon, the rescue holds every rung to 243 W, and the cooling premium over a same-utilisation reference is 1.2-1.4x at the die-wide rungs (X3).

**Figure:** members 137.7 mm^2 (1.36x) and 121.5 mm^2 (1.20x); plan vs reference 0.75 / 0.85 / 0.90x at 162 / 202 / 243 W, vs the utilisation control 1.44 / 1.22 / 1.16x (9.8x at 121 W); passive ceiling 60.7 -> 70.8 W with utilisation alone, back to 60.7 W with the x0.5 cluster; 0 tiles capped  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `python examples/generate_exec_density_family.py --factors 1.0 0.5 --utilisation 0.70 --overhead 0.15 --cache-halo-um 20 --tag u70; scripts/x3_utilisation_ladder.sh; python examples/x3_utilisation_report.py`

## Caveat that travels with this claim

100 um cells with the reference re-run on the same grid -- quote only beside those ref rows (the 100 um reference plans are 8-50 % below the 50 um ones; its control cliff is unchanged). Logic x 1.643 with McPAT power unchanged; halos as macro area at constant power; normalisation at 0.3247 K/W measured on the 101 mm^2 die. P9 falsified low (dies grow 1.36x / 1.20x, not 1.4-1.55x); P12 not as predicted.

## Files

- `x3_utilisation.json` (from `docs/evidence/x3_utilisation.json`)
- `d1_exec_density_family_u70.json` (from `docs/evidence/d1_exec_density_family_u70.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-x3_u70` -> `results/x3_u70`
