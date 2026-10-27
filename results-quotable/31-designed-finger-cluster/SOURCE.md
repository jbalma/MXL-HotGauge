# A DESIGNED finger layout -- every execution unit a full-width strip interdigitated with scheduler / register-file logic at the tile pitch -- holds every rung to 243 W at 16x and at 32x (section P0.38).

**Figure:** 20 um burial, 100 um pitch, plan W (s) at 162 / 202 / 243 W: 16x finger 76.8 / 132.1 (0.70) / 170.5 (0.76); 16x strip 103.3 / 163.9 (0.88) / none; 16x compact none; 32x finger 87.7 / 145.0 / 190.0 (0.85); 32x strip 108.6 / none / none; 32x compact holds 111 W only; 0 tiles capped; the compact 16x: nothing at 5 um burial (lift removed, either film); 162 W held at 50 um pitch under the cold-tolerant film (117.0 W, s 0.78), 202 W lost  
**Register:** `docs/RESULTS_REGISTER.md` §1.3, §2, §3, §4  
**Reproduce:** `python examples/generate_exec_density_family.py --factors 0.0625 0.03125 --finger-cluster --json-out docs/evidence/d1_exec_density_family_finger.json; scripts/finger_cluster_ladder.sh; python examples/finger_cluster_report.py`

## Caveat that travels with this claim

Same areas, powers, names and die area in every shape of one factor. 50 um cells: a strip is one cell tall in the tiler's and the designed layout alike (like for like); finger-vs-compact keeps the sub-cell caveat. The cropped die on a 25 um grid is not built. Quote rows with the unit shape.

## Files

- `finger_cluster.json` (from `docs/evidence/finger_cluster.json`)
- `d1_exec_density_family_finger.json` (from `docs/evidence/d1_exec_density_family_finger.json`)
- `d1_exec_density_family_x32.json` (from `docs/evidence/d1_exec_density_family_x32.json`)
- `d1_exec_density_family_compact_x32.json` (from `docs/evidence/d1_exec_density_family_compact_x32.json`)
- `compact_cluster.json` (from `docs/evidence/compact_cluster.json`)
- `cluster_transport.json` (from `docs/evidence/cluster_transport.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-finger_cluster` -> `results/finger_cluster`
