# Cache hit latency is not a throughput lever on CoMeT's SPLASH-2 kernels: L2 + L3 access times at 50 / 75 / 150 % of the recorded move instructions per second by under 0.5 % at 4 and 16 GHz (section P0.45). A cold / low-V_t cache's benefit, where it exists, is a leakage benefit, not a throughput one, on this workload class.

**Figure:** FFT 4 GHz +0.1 / -0.4 / -0.2 %, 16 GHz -0.3 / +0.2 / +0.3 %; lu.cont +0.4 / +0.3 / -0.3 % and +0.3 / +0.4 / +0.1 %; fitted a and b within 2 %; elasticity 0.77-0.78 / 0.45-0.47 at every scaling  
**Register:** `docs/RESULTS_REGISTER.md` §1.3, §4  
**Reproduce:** `CoMeT/test/mem_arrangement_sweep/runit_cachelat.sh (docker, node-06, through the campaign server); python examples/comet_cache_latency_report.py`

## Caveat that travels with this claim

One workload class (SPLASH-2 small, 4 cores), 2.5D memory, CoMeT's constant-latency DRAM; the kernels are DRAM-latency- and clock-bound. A cache-hit-bound kernel, larger inputs or more cores are unmeasured. Says nothing about the LEAKAGE side of a cold cache (section P0.45 stack rows are planner-limited above 1.00 W/mm^2).

## Files

- `comet_cache_latency.json` (from `docs/evidence/comet_cache_latency.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-cachelat` -> `/mnt/nfs01/scratch/jbalma/CoMeT/test/mem_arrangement_sweep/cachelat`
