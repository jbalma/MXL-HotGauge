# Near memory and the cooler are complements: a clock gain keeps 0.78 / 0.47 of itself (4 / 16 GHz) on interposer-class memory and 0.51 / 0.21 on off-package DDR; stacking under the cores adds 1-6 % (section P0.43, the matched CoMeT sweep).

**Figure:** FFT vs 2.5D at 2 / 4 / 8 / 16 GHz: DDR -19 / -31 / -43 / -54 %, 3Dmem -1 to -4 %, 3D +1 / +2 / +2 / -1 %; lu.cont: DDR -9 / -19 / -33 / -47 %, 3D +2 to +6 %; floor b = 0.20-0.24 (FFT) / 0.31-0.34 (lu.cont) of the measured DRAM latency in every arrangement  
**Register:** `docs/RESULTS_REGISTER.md` §1.3, §3, §4  
**Reproduce:** `ssh node-06: bash CoMeT/test/mem_arrangement_sweep/run_all_on_node.sh; python examples/comet_mem_arrangement_report.py`

## Caveat that travels with this claim

One workload class (SPLASH-2 small, 4 cores); CoMeT constant-latency DRAM model with a queue, 7.6 GB/s per controller in all four arrangements (no HBM bandwidth model); the 2.5D / 3D rows hold no thermal samples. Name the memory arrangement with every throughput figure.

## Files

- `comet_mem_arrangement.json` (from `docs/evidence/comet_mem_arrangement.json`)
- `comet_ipc_vs_f.json` (from `docs/evidence/comet_ipc_vs_f.json`)
