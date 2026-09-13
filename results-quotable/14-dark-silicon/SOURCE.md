# Dark-silicon recovery: at 1.2 W/mm^2 per core no contiguous quarter of the die lights on this package, the unpowered GaAs layer lights a quarter, the laser lights all 34 cores for 12 W; at 1.5 only the laser lights any fraction (44 W).

**Figure:** 11.6 W at 1.2 (seed shape 17.3); 44.1 W at 1.5 (seed 64.2); a lit quarter at 1.5 4.1 W; native 0.78 lights unaided; 1.0: control 50 %, passive layer 100 %  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/dark_silicon_ladder.sh; python examples/dark_silicon_report.py`

## Caveat that travels with this claim

Costs are the per-block (power) envelope-shape plans (§P0.29); the seed-shape plans (17.3 / 64.2 / 48.7 W) held but over-spent and are withdrawn as costs. The 1.2 / 25 % row holds for 0.8 W at 12 planner iterations (its recorded "runaway" was an unfinished descent). Hot cores are a contiguous block (worst case). The recovery claim starts at ~1.0 W/mm^2 per core: the driver's control lights the native die unaided (§P0.23.2 P1 falsified -- it was written against the probe's ceiling). At 1.5 a lit quarter costs more than a lit half (48.7 vs 43.0 W): measured.

## Files

- `dark_silicon.json` (from `docs/evidence/dark_silicon.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-dark_silicon` -> `results/dark_silicon`
