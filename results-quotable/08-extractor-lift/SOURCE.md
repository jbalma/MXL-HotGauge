# The extractor's lift is a curve fixed by v98's own constitutive model (the transparency cap), not a scalar and not a measurement; the target device is v98 Table 1.1's R640-SMILES row; on this die it never binds, and a fixed-wavelength GaAs pump has a hot-side limit.

**Figure:** target device 5900 W/mm^2 at 400 K, 813 at 300 K, 263 at 263 K, T_min 176 K (sigma-independent collapse); GaAs fixed pump T_min 259 K, hot limit ~365-380 K; coldest engaged tile on the die 263 K at 2.60 W/mm^2 with 0 tiles capped  
**Register:** `docs/RESULTS_REGISTER.md` §1.5  
**Reproduce:** `python examples/extractor_curves.py; scripts/extractor_rescue_points.sh | scripts/campaign_inner.sh; python examples/extractor_report.py`

## Caveat that travels with this claim

v98 supersedes v91: the bulk-film 10^3-10^4 W/mm^2 of v91 eq. 8.4 is withdrawn and 10^3 is the Tier-I design point after the photonic ladder. The dye is a hot-die platform (7x below design at 300 K tiles). Reproduces v98 Tables 8.1, 8.2, 8.3, 1.1 and Table 9.2; none of it rests on Yb:YLF. Keep --mr-dt-max 45 alongside the curve: the scalar also shapes the plan.

## Files

- `extractor_cooling_curves.json` (from `docs/evidence/extractor_cooling_curves.json`)
- `extractor_armD.json` (from `docs/evidence/extractor_armD.json`)
- `extractor_v98.json` (from `docs/evidence/extractor_v98.json`)

## Raw solve trees

Symlinked, not copied — they are gigabytes. Relative links, so this directory stays movable within the repo.

- `raw-extractor_armD` -> `results/extractor_armD`
- `raw-extractor_v98` -> `results/extractor_v98`
