# WITHDRAWN — "Above 0.1 K/W the part does not reach its 100 C spec limit -- it runs away first."

**Say instead:** the part reaches spec at EVERY cooling point tested  
**Register:** `docs/RESULTS_REGISTER.md` §2

## Why it failed

An artefact of the pipeline curve's hot tail, which is ~47x too steep at 500 K. On the measured curve the search ends at the spec limit, not in a runaway.

## What survives in these files

`[!]` THE SUSTAINABLE CLOCKS IN THE TABLE SURVIVE -- only the MECHANISM is withdrawn. This item is mixed, which is exactly why it is filed here: a proposal writer reaching into it should read this note first.

## Files

- `clock_headroom_34core_7nm.json` (from `docs/evidence/clock_headroom_34core_7nm.json`)
- `clock_headroom_curve_compare.json` (from `docs/evidence/clock_headroom_curve_compare.json`)
