# Dark-silicon recovery: at 1.2 W/mm^2 per core no contiguous quarter of the die lights on this package, the unpowered GaAs layer lights a quarter, the laser lights all 34 cores for 17 W; at 1.5 only the laser lights any fraction (64 W).

**Figure:** 17.3 W (10.6 net) at 1.2; 64.2 W (39.3 net) at 1.5; native 0.78 lights unaided; 1.0: control 50 %, passive layer 100 %  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/dark_silicon_ladder.sh; python examples/dark_silicon_report.py`

## Caveat that travels with this claim

Hot cores are a contiguous block (worst case). The recovery claim starts at ~1.0 W/mm^2 per core: the driver's control lights the native die unaided (§P0.23.2 P1 falsified -- it was written against the probe's ceiling). At 1.5 a lit quarter costs more than a lit half (48.7 vs 43.0 W): measured.

## Files

- `dark_silicon.json` (from `docs/evidence/dark_silicon.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-dark_silicon` -> `results/dark_silicon`
