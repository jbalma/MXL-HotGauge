# Cooling the cache reduces its leakage far more than the original curve implied; the target is barely sub-ambient; the cold zone must be a separate die.

**Figure:** 2.23x improvement; 280 K knee; 1.24 K of gradient for 40 W removed  
**Register:** `docs/RESULTS_REGISTER.md` §1.2  
**Reproduce:** `python examples/cold_zone_prize.py [--core-other-policy hierarchy-consistent]`

## Caveat that travels with this claim

QUOTE THE 2.23x IMPROVEMENT, NOT A PERCENTAGE. The percentage has moved four times (30 % -> 13.5 % -> ~6 % -> ~14 %) and is accounting-dependent; the ratio has not moved once, because the conversion cancels in it.

## Files

- `cold_zone_prize_simulated.json` (from `docs/evidence/cold_zone_prize_simulated.json`)
- `cold_zone_prize_core_other_consistent.json` (from `docs/evidence/cold_zone_prize_core_other_consistent.json`)
- `thermal_zone_separability.json` (from `docs/evidence/thermal_zone_separability.json`)
- `exergy_map.json` (from `docs/evidence/exergy_map.json`)
