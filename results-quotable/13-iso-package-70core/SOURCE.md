# The laser's multiplier travels to the 70-core die and the watts do not: 2.2x the driver's control (0.70 -> 1.60 W/mm^2, 301 W), s = 0.93 at the top rung, 9.0 TFLOP/s on the same air-cooled package (F1).

**Figure:** control 0.70 (137 W); unpowered array 0.80; laser 1.60 = 301 W; 2.00 no steady state at full capability; 2.06x the cores at 4.03 GHz  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/iso_package_70core_ladder.sh; python examples/iso_package_throughput_report.py`

## Caveat that travels with this claim

100 um cells. GFLOP/s is the thermal-only proxy, flat at fixed core count: quote the watts multiplier and the core-count multiplier, never "N x the compute" from one die. Predicted 390-470 W, measured 301 (§P0.23.1 P2 falsified).

## Files

- `iso_package_throughput.json` (from `docs/evidence/iso_package_throughput.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-iso_package_70core` -> `results/iso_package_70core`
- `raw-array_coverage_armD` -> `results/array_coverage_armD`
