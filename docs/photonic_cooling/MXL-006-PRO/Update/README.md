# MXL-006 update package (12 September 2026)

For patent counsel: the review of the as-filed provisional against the device book (v100, Part VI)
and the MXL-HotGauge simulation record, with the recommended claim framing.

| item | what |
|---|---|
| `MXL-006_update_memo.md` / `.docx` / `.html` | the memo (executive summary; element-by-element review of the filing; Part VI reconciliation; the measured record; the withdrawn list; recommended claim framing; the evolution figures; experiments run for this memo; evidence pointers) |
| `figures/fig_integration_levels.png` | cross-sections of the die at four degrees of integration (conventional → decoupled cold plate → package-integrated thinned die with the redesigned cluster and rails → two-sided stack), each panel tagged MEASURED / ARGUED with its evidence |
| `figures/fig_core_evolution.png` | one core's floorplan per ladder generation (gen 0 → gen 3), one architectural change per measured constraint |
| `figures/fig_scales.png` | the scale ladder (rack → decoupled → package → die → stack) and what is measured at each |
| `figures/fig_integration_ladder.png` | the burial-depth × tile-pitch experiment run for this memo (§P0.28) |
| `figures/fig_evidence_matrix.png` | every claim-relevant statement with its status and evidence file |
| `figures/ev_*.png` | the evidence figures from the quotable proposal pack (rescue ladder and s, current ladder / EM / skew, dense cluster, cache objective, burst, clock, dark silicon, density ceilings, cold-zone prize, accelerator) |
| `results/*.json` | the evidence files behind every number (copied from `docs/evidence/`); `results/RESULTS_REGISTER.md` is the register that classifies them as quotable / withdrawn / open; `EVOLUTION_LADDER.md` and `PHYSICAL_DESIGN_CONSTRAINTS.md` for context |
| `make_evolution_figures.py`, `make_evidence_matrix.py` | regenerate the schematics and the matrix |

Sources reviewed: `../Final/2025-10-13 MXL-006-PRO Application as Filed.PDF` (with the specification text in `../Misc/`), `Photonic_Cooling_Devices___v100.pdf` (Part VI, book pp. 161–180; §1.18; §2.8), and the MXL-HotGauge repository at `/mnt/nfs01/scratch/jbalma/MXL-HotGauge` (`docs/RESULTS_REGISTER.md`, `docs/PHASE0_CHECKLIST.md` §P0.22–§P0.28, `docs/designs/`).

Nothing here is a legal opinion.
