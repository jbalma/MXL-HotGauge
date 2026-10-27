# A DRAM / HBM die beside, under or on top of the 2.00 W/mm^2 compute die sits at the die's area-average temperature (27-70 C), never near the 85 C breakpoint; what the array pays is the HEAT PATH the memory adds or removes -- 2.5D nothing, the far face -6 to +16 W by its own sink, memory-on-logic 0 W for one hybrid-bonded die and +40 W or no hold for an 8-high stack (section P0.44, the re-aimed gen 3).

**Figure:** reference 126.1 W; beside 123 W (-2.5 %), banks 27-30 C at 0.5-2 mm; far face through a 10,000-via field (k_eff 0.85): 120.0 / 132.4 / 141.6 W at 1 / 3 / 10 K/W, banks 47 / 59 / 67 C; aerogel 0.1 at 10 K/W: refresh runaway; memory-on-logic one die 126.1 / 133.6 W (50 / 5 W/mK), 8-high 166.5 W (hybrid) / no hold (microbumps), 35 W at 1.00 W/mm^2  
**Register:** `docs/RESULTS_REGISTER.md` §1.2, §3, §4  
**Reproduce:** `scripts/memory_die_ladder.sh; python examples/memory_die_report.py`

## Caveat that travels with this claim

100 um cells, dye, --mr-dt-max 45 beside the curve (curve-only the envelope is area-weighted and the banks starve the compute die), seed shape (per-block twins: reference 99.2 W, far face 111.9 W). 8 x 3 W lumped into one 435 um die element; power/dram.py is UNCALIBRATED (JEDEC conventions) -- quote placements and heat paths, never memory watts. The storage array's 1.9-5.9 W on far-face rows is the one-scalar envelope's share (banks 10-37 K under target), not a need. beside: one slab (coupling an upper bound), shared-base warming ~1.8 K omitted. Quote placement, k_eff with the via count, far-face R, dies, W per die, envelope shape.

## Files

- `memory_die.json` (from `docs/evidence/memory_die.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-memory_die` -> `results/memory_die`
- `raw-memory_die_twins` -> `results/memory_die_twins`
- `raw-anchor_2026-10-27` -> `results/anchor_2026-10-27`
