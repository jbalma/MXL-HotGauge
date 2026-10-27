# The caches' share of on-die leakage (54 %) and the cold-cache prize in watts are a McPAT input: the L2 / L3 bitcells are modelled as HP logic devices (section P0.40).

**Figure:** steady slice, 8 cores, 330 K: caches 1.652 W = 53.8 % of processor leakage with HP cells (as recorded; static fraction 29.4 %) against 0.0054 W = 0.4 % with LSTP cells (306x; static 16.1 %); LOP at this fork's 7 nm table is not credible (23x MORE leakage). CoMeT record: 2.5D x 111, 3Dmem x 40, 3D x 8, DDR x 0; the IPC(f) sweep is 2.5D; FFT t = 0.328/f + 0.0191 ns per instruction  
**Register:** `docs/RESULTS_REGISTER.md` §1.2 (head note), §2, §3, §4  
**Reproduce:** `bash spice_toolchain/tmp/mcpat_cache_device_ab.sh; python examples/mcpat_cache_device_report.py`

## Caveat that travels with this claim

McPAT-native scope (not the floorplan ledger). A production cache array sits between the HP and LSTP columns, far nearer LSTP. Ratios (2.23x, the 280 K knee) and every thermal-geometry result stand. This is NOT a finding that a cold memory zone has no benefit (two points, one die): the McPAT surface (section P0.42) puts the pay-off at ~2.5-3x the recorded leakage density -- fast cells beside a hot die. The near-memory gains (3D +3 / +9 %, DDR -14 / -29 % at 4 / 16 GHz) are ARGUED from one recorded sweep; the matched CoMeT sweep is written and not run.

## Files

- `mcpat_cache_device.json` (from `docs/evidence/mcpat_cache_device.json`)
- `mcpat_cache_surface.json` (from `docs/evidence/mcpat_cache_surface.json`)
- `comet_ipc_vs_f.json` (from `docs/evidence/comet_ipc_vs_f.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-mcpat_cache_device` -> `results/mcpat_cache_device`
