# The laser rescues a die that has no steady state; an unpowered array of the same material does not.

**Figure:** 35 / 35 rescue points, on all three leakage curves  
**Register:** `docs/RESULTS_REGISTER.md` §1.1  
**Reproduce:** `python examples/mr_curve_compare.py`

## Caveat that travels with this claim

It is a DIFFERENCE between arms. Never quote the array arm alone. The `array_idle` arm diverges everywhere too, which is what makes this a statement about the laser rather than about adding a second die.

## Files

- `mr_catalogue_curve_compare.json` (from `docs/evidence/mr_catalogue_curve_compare.json`)
- `airflow_ladder_solved.json` (from `docs/evidence/airflow_ladder_solved.json`)
- `mr_rescue_cost_34core.json` (from `docs/evidence/mr_rescue_cost_34core.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-mr_curve_compare` -> `results/mr_curve_compare`
