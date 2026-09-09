# The photonic cold plate we test is single-material by default (architecture-agnostic); the storage-zone material is Cr:LiSAF and the hot-zone material the dye (user decision, 8 Sep); the floorplan-matched dual arrangement is a flag and, on the hot-spot objective, a 1 % effect on this die.

**Figure:** single mode reproduces P0.20 to 2e-13 W (138.73 W, 93.875 C); dual mode at 2.00 W/mm^2: 80 cold tiles of 384, 23 capped, 0.10 W shortfall, plan +1.3 W, peak -0.05 K; Cr:LiSAF 17.6-59 W/mm^3 at F_P 30-100 (ceiling at eta_EQE = 1)  
**Register:** `docs/RESULTS_REGISTER.md` §1.5  
**Reproduce:** `python examples/mr_comparison.py ... --mr-extractor dye --mr-dt-max 45 --mr-zone-mode {single,dual}; python examples/zone_mode_report.py`

## Caveat that travels with this claim

A floorplan statement for this die and this cold-zone pattern only; never transferable. The planner never drives the caches cold on the hot-spot objective (coldest tile 290.7 K), so the storage-zone material has nothing to do until the objective is cache leakage or the floorplan is the variable. Cr:LiSAF fails breakeven at its demonstrated eta_EQE (0.85-0.95; needs > 0.94).

## Files

- `zone_mode_smoke.json` (from `docs/evidence/zone_mode_smoke.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-zone_mode_smoke` -> `results/zone_mode_smoke`
