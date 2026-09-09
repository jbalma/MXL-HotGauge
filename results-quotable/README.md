# results-quotable

**Evidence behind claims that may be cited.** Every directory maps to a claim in
`docs/RESULTS_REGISTER.md` §1 and carries a `SOURCE.md` with the claim, the figure, the command
that reproduces it, and **the caveat that must travel with it**.

`[!]` **Read the caveat.** It is not editorial trimming — each one has bitten at least once.

`[!]` **Curated, not exhaustive.** Only files a register claim names are here. `docs/evidence/`
remains the full working set of ~110 files, promoted and retired mixed together. A file's absence
from this directory means nobody has classified it, **not** that it is wrong.

| directory | claim | headline figure |
|---|---|---|
| `01-rescue-microrefrigeration/` | The laser rescues a die that has no steady state; an unpowered array of the same material does not. | **35 / 35 rescue points, on all three leakage curves** |
| `02-cold-zone/` | Cooling the cache reduces its leakage far more than the original curve implied; the target is barely sub-ambient; the cold zone must be a separate die. | **2.23x improvement; 280 K knee; 1.24 K of gradient for 40 W removed** |
| `03-density-and-concentration/` | Concentrating power costs sustainable density and spreading it buys density back; a perfectly flat die still has a hard ceiling; the optics requirement is set by the floorplan and is loose. | **1.4x concentration ratio; 0.85-0.90 W/mm^2 flat ceiling; 200 um pitch plateau** |
| `04-accounting-corrections/` | Most of the recorded catalogue's thermal divergence was an artefact of two wrong inputs, not physics. The pipeline leakage curve is not a device. | **94 -> 8 diverging of 145 control points; leakage curve 57, accounting 22, bus 0** |
| `05-recovery-and-thermodynamics/` | The second-law recovery ledger is v91 eq. (1.13); the 36 net-generating rows are corrected by algebra with no re-solves. | **36 rows corrected, all flip sign; -5.879 W -> +32.672 W** |
| `06-transistor-simulated/` | The ASAP7 transistor is simulated, not interpolated: leakage, threshold, swing, drive current and the V/F shape all come from BSIM-CMG in ngspice on the card. | **dVt/dT -0.39/-0.46 mV/K; SS 61.0 mV/dec +0.20/K; alpha 1.45 fitted; the two evidence files agree on I_off(T) to 0.76 %** |
| `07-array-coverage/` | The array charged its own footprint costs nothing at the shipped pitch: a quarter-coverage array holds the same ceiling on the same minimum plan. Under corrected inputs the laser holds from 1.20 to 2.60 W/mm^2. | **coverage 0.26 (644/1126 blocks under gaps, 74.8 mm^2 reserved): same rung, Q within 1.6 % at a common peak; array_idle fails 1.20, array_on holds 2.60** |
| `08-extractor-lift/` | The extractor's lift is a curve fixed by v98's own constitutive model (the transparency cap), not a scalar and not a measurement; the target device is v98 Table 1.1's R640-SMILES row; on this die it never binds, and a fixed-wavelength GaAs pump has a hot-side limit. | **target device 5900 W/mm^2 at 400 K, 813 at 300 K, 263 at 263 K, T_min 176 K (sigma-independent collapse); GaAs fixed pump T_min 259 K, hot limit ~365-380 K; coldest engaged tile on the die 263 K at 2.60 W/mm^2 with 0 tiles capped** |
| `09-zone-mode/` | The photonic cold plate we test is single-material by default (architecture-agnostic); the storage-zone material is Cr:LiSAF and the hot-zone material the dye (user decision, 8 Sep); the floorplan-matched dual arrangement is a flag and, on the hot-spot objective, a 1 % effect on this die. | **single mode reproduces P0.20 to 2e-13 W (138.73 W, 93.875 C); dual mode at 2.00 W/mm^2: 80 cold tiles of 384, 23 capped, 0.10 W shortfall, plan +1.3 W, peak -0.05 K; Cr:LiSAF 17.6-59 W/mm^3 at F_P 30-100 (ceiling at eta_EQE = 1)** |

## Before citing anything from here

1. Check `docs/RESULTS_REGISTER.md` §0 — the configuration these were computed under. Two solver
   defaults changed on 2–3 September 2026.
2. Read the `SOURCE.md` caveat.
3. Prefer a **ratio** to an absolute number where the register offers one. The 2.23× cold-zone
   improvement has survived four revisions of the percentage beside it.

Rebuild or check with `python scripts/build_results_registers.py [--verify]`.
