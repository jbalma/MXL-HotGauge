# The two-die stack with the storage die between the compute die and the sink collects nothing the monolithic die did not: the 280 K objective costs the whole die (99.3 W, s = 1.08) at every bond conductivity from hybrid to underfill, and an isolating bond takes the compute die's sink away (X4). Gen 3 as argued is falsified in this geometry; the storage die must be off the heat path.

**Figure:** 1.00 W/mm^2, bond 120 / 50 / 5 W/mK: dye 99.3 W, zone 289 K, cache leakage 4.70 -> 1.30 W (3.6x) for 66 W net; Cr:LiSAF 73.7 W, 58 tiles capped; 0.5 W/mK: unpowered array diverges, nothing holds; hot-spot objective at 2.00: 121.8 W vs the 100 um reference 126.1 W (-3.4 %)  
**Register:** `docs/RESULTS_REGISTER.md` §1.2  
**Reproduce:** `python examples/split_storage_die.py; scripts/gen3_stack_ladder.sh; python examples/gen3_stack_report.py`

## Caveat that travels with this claim

100 um cells; 50 um storage die on a 5 um bond, the array above it (the book's face-to-back arrangement, sink side). The 0.5 W/mK rows sit on a hot-branch baseline and are lower bounds. The cache prize itself (2.23x, 280 K knee, 3.6x) stands; what is withdrawn is the geometry argued to collect it cheaply. The surviving variant (storage die off the heat path, two sinks) is ARGUED. Anchor reproduced after the stack/solver edits.

## Files

- `gen3_stack.json` (from `docs/evidence/gen3_stack.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-gen3_stack` -> `results/gen3_stack`
