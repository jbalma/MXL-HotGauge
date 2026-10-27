# IPC(f) from CoMeT's 1-20 GHz sweeps: the memory wall enters the throughput claims. At the recorded F1c clocks the fixed-IPC proxy overstates the throughput gain by a fifth (elasticity 0.78-0.84); CoMeT's DVFS voltage is a table, not a device (section P0.33).

**Figure:** FFT IPC 2.88 / 2.49 / 2.09 / 1.58 / 1.43 at 1 / 4 / 8 / 16 / 20 GHz, knee fit IPC0 3.06 f_k 17.3 GHz (1 % residual); +13.9 % clock -> +11.4 % instructions/s, +25.5 -> +21.1, +33.5 -> +26.1; 8 -> 16 GHz elasticity lu.cont 0.47, swaptions 0.84, FFT 0.60; PeriodicVdd 1.2 V at every f  
**Register:** `docs/RESULTS_REGISTER.md` §1.3, §4  
**Reproduce:** `python examples/comet_ipc_reader.py; python examples/clock_f1c_report.py --base results/clock_f1c_density; python examples/iso_package_throughput_report.py`

## Caveat that travels with this claim

Measured in CoMeT (Sniper) on a different core and memory system: the SHAPE of IPC(f) transfers, not the level. Only the frequency setting differs between CoMeT's configs; nothing there says whether the device switches at 20 GHz (21-generalized-fmax does). x264 rows read IPC 0 (outside the ROI); -test inputs are too short to quote.

## Files

- `comet_ipc_vs_f.json` (from `docs/evidence/comet_ipc_vs_f.json`)
- `clock_f1c.json` (from `docs/evidence/clock_f1c.json`)
- `iso_package_throughput.json` (from `docs/evidence/iso_package_throughput.json`)
