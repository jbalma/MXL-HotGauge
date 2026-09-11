# Burst absorption (F4): a 10 ms activity burst that the package rides on thermal mass is removed at its source by the MODULATED array -- 2.5-3.3x less overshoot per added watt; at 0.80 W/mm^2 a 2x burst sends the package 11 ms above the spec and the modulated array holds the die under its target.

**Figure:** 0.80 W/mm^2, k=2: control 118 C (11 ms > spec), static array 109 C (6 ms), modulated 87 C (0 ms > target, 70 W removed, 2.6 J); k=3: control and static array non-viable (> 127 C), modulated 101 C (6 ms > spec); per added watt 0.51-0.67 K/W control, 0.51-0.54 static, 0.17-0.20 modulated; 1.00, k=3: the static array runs away inside the 25 ms window  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `scripts/burst_ladder.sh; python examples/burst_report.py`

## Caveat that travels with this claim

Transient 3D-ICE (1 ms slots, 10 sub-steps), each arm warm-started from its own steady state; whole-die burst on DYNAMIC power at fixed voltage; feed-forward modulation (the burst's own added watts removed at their source -- what a power monitor commands; the array's microsecond optical response is ARGUED, the model resolves the thermal one). A MARGIN claim: quote with the operating point and its steady margin (0.80: 20 K under target; 1.00: 3 K, where the modulated array still crosses the target at every k and the spec at k >= 2). Rows past 127 C are non-viable, not temperatures; the 1.00/k3 static row is a transient runaway, not a number. The extractor's per-tile cap is steady-only: the burst plan asks up to 13 W/mm^2 of one tile for 10 ms (1.00 / 3x; 5.2 at 0.80 / 2x), the first demand above the steady ~5 W/mm^2 rule and 60x under the device at 300 K.

## Files

- `burst_absorption.json` (from `docs/evidence/burst_absorption.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-burst` -> `results/burst`
