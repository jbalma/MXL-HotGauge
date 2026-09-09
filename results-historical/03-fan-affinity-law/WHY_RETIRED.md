# WITHDRAWN — "Fan power scales as R^-5; localized cooling is worth 22-35 % of system power through fan displacement."

**Say instead:** fan power is LINEAR in heat carried; at today's extractor the optimum is baseline airflow  
**Register:** `docs/RESULTS_REGISTER.md` §2

## Why it failed

Used the textbook affinity law rather than the calibrated fan model. The displacement mechanism is real; its magnitude was not.

## What survives in these files

The measured airflow ladder rows inside `fan_displacement_solved.json` are solver output and remain valid; the (1-s)^5 framing around them does not.

## Files

- `fan_displacement_solved.json` (from `docs/evidence/fan_displacement_solved.json`)
- `hybrid_displacement.json` (from `docs/evidence/hybrid_displacement.json`)
