# The second-law recovery ledger is v91 eq. (1.13); the 36 net-generating rows are corrected by algebra with no re-solves.

**Figure:** 36 rows corrected, all flip sign; -5.879 W -> +32.672 W  
**Register:** `docs/RESULTS_REGISTER.md` §1.5, and docs/REFERENCES.md §2  
**Reproduce:** `python examples/findings_recovery_correction.py`

## Caveat that travels with this claim

We apply the many-mode Carnot factor to the anti-Stokes term while the device engineers fluorescence AWAY from that limit, so every recovered-power figure is a LOWER BOUND. That is a design lever, not an error.

## Files

- `findings_recovery_correction.json` (from `docs/evidence/findings_recovery_correction.json`)
- `recovery_at_temperature.json` (from `docs/evidence/recovery_at_temperature.json`)
