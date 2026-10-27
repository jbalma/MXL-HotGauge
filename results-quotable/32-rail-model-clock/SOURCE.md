# With a static rail model (V_eff = V_dd - IR, rails sized for the native die to a 5 % budget) a dense cluster on native rails loses a fifth of its clock, and re-sizing the rails ~J x restores it (section P0.39).

**Figure:** laser arm, 92 C target, 101 W, per-block shape, fmax source, 20 FO4: 8x strip cluster 3.728 GHz rail-off -> 3.019 on native rails (-19.0 % clock, -16.6 % f x IPC(f); 213 mV at 6.1x J_native; rail:ir+reliability:tddb; die 62 W, array plan 0 W) -> 3.662 at 4x -> 3.775 at 8x; 16x: 3.693 -> 2.566 (-30.5 %, -26.8 %; 294 mV; 46 W, plan 0 W) -> 3.624 at 8x -> 3.699 at 16x; reference die at 1.00 W/mm^2: J 1.4x native, 49 mV, +0.3 % (inside the 0.05 GHz tolerance); designed fingers (P0.41): 3.728 GHz rail-off at 16x and 32x, 3.737 GHz widened by the density ratio (J 20x / 40x native), 2.04 GHz (16x) and no clock above 2 GHz (32x) on native rails -- the 16x native-rail clock is path-dependent, quote 2.0-2.6 GHz  
**Register:** `docs/RESULTS_REGISTER.md` §1.3, §3, §4  
**Reproduce:** `scripts/clock_rail.sh; python examples/clock_rail_report.py`

## Caveat that travels with this claim

Static IR only (no L di/dt, no decap, no rail self-heating); the 5 % native budget and J_native are STATED; TDDB / EM see the pin voltage. Clocks UNCALIBRATED (3.8 GHz anchor), bisection tolerance 0.05 GHz; quote with V/F source, limiter and IPC(f). Whether 8-16x the rail cross-section exists over a 0.035 mm^2 unit is a BEOL question the model does not hold.

## Files

- `clock_rail.json` (from `docs/evidence/clock_rail.json`)
- `clock_fmax.json` (from `docs/evidence/clock_fmax.json`)
- `pdn_em_skew.json` (from `docs/evidence/pdn_em_skew.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-clock_rail` -> `results/clock_rail`
