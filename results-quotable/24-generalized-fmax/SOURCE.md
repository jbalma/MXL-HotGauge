# A generalized f_max(V, T | logic depth, wire fraction, skew) with V_max from an Arrhenius reliability budget at the cooled temperature: once wire, skew and setup/jitter are in the period, the 10 % overdrive at the array's 92 C target buys +1.6 % of clock (not +10 %); the budget buys supply as an Arrhenius ladder and TDDB binds everywhere below the corner; 10 GHz needs a 6-7 FO4 pipeline on this device (section P0.31 part 1, model arithmetic; part 2 is the coupled search).

**Figure:** anchor 3.8 GHz / 0.70 V / 330 K -> FO4_ref 8.18 ps, wire 70 ps, skew 8.3 ps, overhead 21 ps; V_max 0.778 / 0.792 / 0.814 / 0.863 V at 92 / 78.6 / 60 / 27 C; f_max 3.84 / 3.95 / 4.10 / 4.39 GHz (+1.6 / +4.4 / +8.4 / +16.1 % over the 100 C corner); device peak clock at 0.95-0.975 V; N for 10 GHz 6.0-7.1; native budget: 92 C is EM-bound at 0.547 V / 2.82 GHz  
**Register:** `docs/RESULTS_REGISTER.md` §1.6  
**Reproduce:** `python examples/fmax_model_report.py; scripts/clock_fmax.sh > results/campaign_queue/clock_fmax.par3.tsv (node); python examples/clock_fmax_report.py`

## Caveat that travels with this claim

ARGUED on stated constants: qualification 0.77 V at 100 C, EM Black n=2 / 0.9 eV with J ~ V f, TDDB power law n=40 / 0.6 eV (n 30-50 and Ea 0.4-0.8 move f_max < 0.3 %); wire 30 % (+-3 %), overhead 8 %, D_ins 150 ps; FO4_ref inherits the 3.8 GHz anchor (uncalibrated). The recorded 4.17 GHz (15-clock-as-free-variable) is the gate-only ceiling. Quote every clock with its V/F source and the limiter the row names.

## Files

- `fmax_model.json` (from `docs/evidence/fmax_model.json`)
- `device_vt_vf_asap7_v100.json` (from `docs/evidence/device_vt_vf_asap7_v100.json`)
- `clock_fmax.json` (from `docs/evidence/clock_fmax.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-clock_fmax` -> `results/clock_fmax`
