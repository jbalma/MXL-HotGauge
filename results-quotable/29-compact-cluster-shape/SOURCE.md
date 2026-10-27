# The shape of a densified execution cluster is a design variable: compact helps to ~8x and breaks at 16x -- past ~8x the units want perimeter (fingers), not compaction (section P0.36).

**Figure:** 8x compact 0.94 / 0.85 of the strip plan at 162 / 202 W and gains 243 W at 200 um pitch (s 0.98); 4x compact gains 243 W at the D1 geometry (s 0.93), 3-8 % cheaper; 2x compact +3-4 %; 16x compact holds only 111 / 121 W (1.5-1.6x the strip plan), no steady state at 162 / 202 W with 0 capped, unchanged without the 45 K lift and under either material  
**Register:** `docs/RESULTS_REGISTER.md` §1.3, §4  
**Reproduce:** `python examples/generate_exec_density_family.py --factors 0.5 0.25 0.125 0.0625 --compact-cluster --json-out docs/evidence/d1_exec_density_family_compact.json; scripts/compact_cluster_ladder.sh; python examples/compact_cluster_report.py`

## Caveat that travels with this claim

Same areas, powers, block names and die area as the strip members; only the shape differs. 50 um cells: the 16x units are sub-cell in both shapes (holds are lower bounds, losses firm). Quote a dense-cluster row with its unit shape.

## Files

- `compact_cluster.json` (from `docs/evidence/compact_cluster.json`)
- `d1_exec_density_family_compact.json` (from `docs/evidence/d1_exec_density_family_compact.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-compact_cluster` -> `results/compact_cluster`
- `raw-compact_cluster_nolift` -> `results/compact_cluster_nolift`
