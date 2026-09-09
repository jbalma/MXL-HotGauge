# Concentrating power costs sustainable density and spreading it buys density back; a perfectly flat die still has a hard ceiling; the optics requirement is set by the floorplan and is loose.

**Figure:** 1.4x concentration ratio; 0.85-0.90 W/mm^2 flat ceiling; 200 um pitch plateau  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/uniform_density_ladder_armD.sh | scripts/campaign_inner.sh`

## Caveat that travels with this claim

The RATIO is the durable result; the absolute ceilings are properties of this die and this package. The flat ceiling is LOWER than any previously recorded value -- a flat die at ~1 W/mm^2 is no longer supportable.

## Files

- `tile_pitch_concentrated.json` (from `docs/evidence/tile_pitch_concentrated.json`)
- `tile_pitch_uniform.json` (from `docs/evidence/tile_pitch_uniform.json`)
- `mr_catalogue_curve_compare.json` (from `docs/evidence/mr_catalogue_curve_compare.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-uniform_density_armD` -> `results/uniform_density_armD`
