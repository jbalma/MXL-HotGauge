# The ASAP7 transistor is simulated, not interpolated: leakage, threshold, swing, drive current and the V/F shape all come from BSIM-CMG in ngspice on the card.

**Figure:** dVt/dT -0.39/-0.46 mV/K; SS 61.0 mV/dec +0.20/K; alpha 1.45 fitted; the two evidence files agree on I_off(T) to 0.76 %  
**Register:** `docs/RESULTS_REGISTER.md` §1.6  
**Reproduce:** `python examples/device_leakage_spice.py; python examples/device_vt_vf_spice.py`

## Caveat that travels with this claim

One device, one drawn length, no self-heating, no p-FET. The threshold is a constant-current CRITERION (100 nA x W/L): compare slopes and shapes across sources, never levels. The V/F anchor (3.8 GHz at 0.70 V) is the trace's clock, a stated choice. The V_t lever re-priced on these inputs is in §2 -- it is a re-derivation, not a thermal measurement.

## Files

- `device_leakage_spice_asap7.json` (from `docs/evidence/device_leakage_spice_asap7.json`)
- `device_vt_vf_asap7.json` (from `docs/evidence/device_vt_vf_asap7.json`)
