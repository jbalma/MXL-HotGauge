# The laser converts thermal headroom into clock until the device's V/F ends it: +14 % at 1.00 W/mm^2 and +26 % at 1.20 on the SPICE ceiling, +34 % on the shipped table (F1c).

**Figure:** 1.00 W/mm^2: control 3.66 GHz, unpowered array 3.90, laser 4.17 (device ceiling, 38 W); table: 4.86 GHz thermal-limited at 2.28 W/mm^2 (235 W removed)  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/clock_f1c_density.sh; python examples/clock_f1c_report.py --base results/clock_f1c_density`

## Caveat that travels with this claim

Operating point in W/mm^2 at the trace clock (--density); the trace's own 0.31 W/mm^2 never meets a thermal limit (clock_f1c.json). Dynamic ~ V^2 f, leakage ~ V (assumed). The SPICE 4.17 GHz and the table's 5.0 GHz are MODEL ceilings; above the table the voltage clamps and no clock may be quoted. GFLOP/s per package watt falls with clock on every arm.

## Files

- `clock_f1c_density.json` (from `docs/evidence/clock_f1c_density.json`)
- `clock_f1c.json` (from `docs/evidence/clock_f1c.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-clock_f1c_density` -> `results/clock_f1c_density`
- `raw-clock_f1c` -> `results/clock_f1c`
