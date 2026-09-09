# WITHDRAWN — "The cold-zone prize is 30 % of die power."

**Say instead:** ~6 % (recorded accounting) or ~14 % (corrected); better, the 2.23x ratio  
**Register:** `docs/RESULTS_REGISTER.md` §2

## Why it failed

Rested on a static fraction and cache share computed on ONE core's leaves against the WHOLE chip's L3, on the trace's warm-up slice. Both defects were reproduced exactly (34.64 %, 92.6 %) and shown to be scope-and-slice arithmetic, not a plausible alternative reading. See PHASE0_CHECKLIST §P0.15.

## What survives in these files

Nothing quantitative. The file is the PROVENANCE record for how the wrong pair was produced, which is why it is kept.

## Files

- `cold_zone_prize_bounds.json` (from `docs/evidence/cold_zone_prize_bounds.json`)
