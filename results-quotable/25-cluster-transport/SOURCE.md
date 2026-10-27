# The 8x / 16x execution-cluster ladder at 20 um and 5 um burial: where heat transport binds a >100 W/mm^2 functional unit (section P0.32).

**Figure:** see docs/evidence/cluster_transport.json and PHASE0_CHECKLIST section P0.32 RESULT  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `python examples/generate_exec_density_family.py --factors 0.125 0.0625 --json-out docs/evidence/d1_exec_density_family_x8x16.json; scripts/cluster_transport_ladder.sh > results/campaign_queue/cluster.par6.tsv (node); python examples/cluster_transport_report.py`

## Caveat that travels with this claim

50 um cells: the 8x cALU is one cell and the 16x cALU sub-cell, so the modelled local rise on the 16x rows is understated (up to ~2.5x) and every 16x hold is a lower bound on the block's real peak. Per-block envelope shape; matched die watts; a row with s >= 1 is envelope-only, not a rescue. Rails scale with the density factor (X1).

## Files

- `cluster_transport.json` (from `docs/evidence/cluster_transport.json`)
- `d1_exec_density_family_x8x16.json` (from `docs/evidence/d1_exec_density_family_x8x16.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-cluster_transport` -> `results/cluster_transport`
