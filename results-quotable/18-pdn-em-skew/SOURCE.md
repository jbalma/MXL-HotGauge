# The rescue ladder is a current ladder and the ladder's non-thermal end is the PDN: every rung above ~1.3 W/mm^2 runs the rails at 1.5-3x the native current, the dense cluster doubles the peak rail current on top, and thermal clock skew grows with every rung (a cost of the rescue, not a lever) -- X1/X2 on the recorded fields.

**Figure:** die current vs native 1.29 / 1.54 / 2.00 / 2.45 / 2.88x at 1.00-2.40 W/mm^2; x0.5 cluster cALU 2.00x, x0.25 3.9x at matched watts; F1c laser 1.50x / 1.78x (SPICE) and 1.60x (table); Black n=2, Ea=0.9 eV: worst block 12x / 21x / 40x / 50x vs native at 1.20-2.40; cooling dividend 2.4x at matched power (1.10); core-domain dT 24 K native -> 32-60 K, 3.2 % -> 4.2-7.9 % of the period at D_ins 150 ps; uniformity buys 0.74 % at matched power and the laser field is less uniform at matched density (+1 to +7 points)  
**Register:** `docs/RESULTS_REGISTER.md` §1.3  
**Reproduce:** `python scripts/x1_fields_queue.py > results/campaign_queue/x1_fields.par4.tsv (node); python examples/pdn_em_skew_report.py`

## Caveat that travels with this claim

Fields and current densities MEASURED (the recorded final power maps re-solved once through the session; peaks reproduced to +-0.000 K); every acceleration, lifetime, skew percentage and the PDN LIMIT are ARGUED on stated constants (V_dd 0.70 V, n=2, Ea=0.9 eV, D_ins 150/500 ps, alpha_R 0.40 %/K, alpha_cell 0.062 %/K). No rail model: "binds: PDN" means the rails must be re-sized ~J x, not that the die fails. Quote the gradient in K beside any skew percentage and n, Ea beside any lifetime.

## Files

- `pdn_em_skew.json` (from `docs/evidence/pdn_em_skew.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-fields` -> `results/fields`
