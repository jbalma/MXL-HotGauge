# WITHDRAWN — Every `p_mr_net_W` computed with the first-law recovery term -- 36 rows report a NET-GENERATING cooler.

**Say instead:** the second-law form, `breakeven_ratio_at(T_h)`; corrected values in quotable/05  
**Register:** `docs/RESULTS_REGISTER.md` §2

## Why it failed

`breakeven_ratio` omits the Carnot factor on the anti-Stokes term -- it is the phi -> 1 limit. At the shipped envelope it reports 1.032, i.e. free energy.

## What survives in these files

`[!]` MIXED, and heavily used. `FINDINGS.json` is the harvested record of the whole catalogue and most of its fields are fine; only `p_mr_net_W` carries the defect. `first_law_recovery_audit.json` SIZES the exposure and is itself a quotable piece of method. Read before reaching in.

## Files

- `FINDINGS.json` (from `docs/evidence/FINDINGS.json`)
- `first_law_recovery_audit.json` (from `docs/evidence/first_law_recovery_audit.json`)
- `loop_model_reconciliation.json` (from `docs/evidence/loop_model_reconciliation.json`)
- `findings_harvest_correction.json` (from `docs/evidence/findings_harvest_correction.json`)
