#!/usr/bin/env python
"""Build ``results-quotable/`` and ``results-historical/`` from the results register.

    python scripts/build_results_registers.py            # build both
    python scripts/build_results_registers.py --verify   # check nothing has drifted

Why these directories exist
---------------------------
``docs/evidence/`` is the **working** evidence set: 110 files, promoted and retired mixed together,
ordered by nothing. That is right for a session that is producing results and wrong for anybody
assembling a proposal, because the withdrawn files sit beside the good ones and look identical.

So this script materialises the two categories ``docs/RESULTS_REGISTER.md`` defines:

* ``results-quotable/`` -- evidence behind a claim in register §1. Safe to cite.
* ``results-historical/`` -- evidence behind a claim in register §2. **Kept deliberately**, because
  a withdrawn number that leaves no trace comes back; every item says what replaced it.

`[!]` **Curated, not exhaustive.** Only files a register claim actually names are placed. The other
~90 evidence files stay in ``docs/evidence/`` as unclassified working material -- silently sorting
files nobody has verified would defeat the point of the exercise.

Copies, not moves
-----------------
Evidence JSONs are **copied** (2.3 MB total), so a register directory is a self-contained snapshot
that can be handed to someone. The raw solve trees are **symlinked** -- they are 125 GB and copying
them would be absurd. Checksums go in ``MANIFEST.json`` so ``--verify`` can tell you when a copy has
drifted from the evidence file it was taken from, which is the failure mode a snapshot invites.
"""
import os
import sys
import json
import shutil
import hashlib
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_EV = os.path.join(_REPO, 'docs', 'evidence')

# --------------------------------------------------------------------------------------------
# The curation. Every entry names the register claim it supports, so a reader can get from a file
# back to the sentence it is evidence for.
# --------------------------------------------------------------------------------------------
QUOTABLE = [
    {
        'slug': '01-rescue-microrefrigeration',
        'claim': 'The laser rescues a die that has no steady state; an unpowered array of the '
                 'same material does not.',
        'figure': '35 / 35 rescue points, on all three leakage curves',
        'register': '§1.1',
        'files': ['mr_catalogue_curve_compare.json', 'airflow_ladder_solved.json',
                  'mr_rescue_cost_34core.json'],
        'raw': ['results/mr_curve_compare'],
        'driver': 'python examples/mr_curve_compare.py',
        'caveat': 'It is a DIFFERENCE between arms. Never quote the array arm alone. The '
                  '`array_idle` arm diverges everywhere too, which is what makes this a statement '
                  'about the laser rather than about adding a second die.',
    },
    {
        'slug': '02-cold-zone',
        'claim': 'Cooling the cache reduces its leakage far more than the original curve implied; '
                 'the target is barely sub-ambient; the cold zone must be a separate die.',
        'figure': '2.23x improvement; 280 K knee; 1.24 K of gradient for 40 W removed',
        'register': '§1.2',
        'files': ['cold_zone_prize_simulated.json', 'cold_zone_prize_core_other_consistent.json',
                  'thermal_zone_separability.json', 'exergy_map.json'],
        'raw': [],
        'driver': 'python examples/cold_zone_prize.py [--core-other-policy hierarchy-consistent]',
        'caveat': 'QUOTE THE 2.23x IMPROVEMENT, NOT A PERCENTAGE. The percentage has moved four '
                  'times (30 % -> 13.5 % -> ~6 % -> ~14 %) and is accounting-dependent; the ratio '
                  'has not moved once, because the conversion cancels in it.',
    },
    {
        'slug': '03-density-and-concentration',
        'claim': 'Concentrating power costs sustainable density and spreading it buys density '
                 'back; a perfectly flat die still has a hard ceiling; the optics requirement is '
                 'set by the floorplan and is loose.',
        'figure': '1.4x concentration ratio; 0.85-0.90 W/mm^2 flat ceiling; 200 um pitch plateau',
        'register': '§1.3',
        'files': ['tile_pitch_concentrated.json', 'tile_pitch_uniform.json',
                  'mr_catalogue_curve_compare.json'],
        'raw': ['results/uniform_density_armD'],
        'driver': 'scripts/uniform_density_ladder_armD.sh | scripts/campaign_inner.sh',
        'caveat': 'The RATIO is the durable result; the absolute ceilings are properties of this '
                  'die and this package. The flat ceiling is LOWER than any previously recorded '
                  'value -- a flat die at ~1 W/mm^2 is no longer supportable.',
    },
    {
        'slug': '04-accounting-corrections',
        'claim': 'Most of the recorded catalogue\'s thermal divergence was an artefact of two '
                 'wrong inputs, not physics. The pipeline leakage curve is not a device.',
        'figure': '94 -> 8 diverging of 145 control points; leakage curve 57, accounting 22, bus 0',
        'register': '§1.4',
        'files': ['catalogue_arm_compare.json', 'device_leakage_asap7.json',
                  'device_leakage_spice_asap7.json'],
        'raw': ['results/rerun_arm_A', 'results/rerun_arm_B', 'results/rerun_arm_C',
                'results/rerun_arm_D'],
        'driver': 'python examples/catalogue_arm_compare.py',
        'caveat': 'This is NOT a restated density ceiling -- these are heterogeneous catalogue '
                  'points at product densities, not a ladder. For the ceiling see 03.',
    },
    {
        'slug': '05-recovery-and-thermodynamics',
        'claim': 'The second-law recovery ledger is v91 eq. (1.13); the 36 net-generating rows are '
                 'corrected by algebra with no re-solves.',
        'figure': '36 rows corrected, all flip sign; -5.879 W -> +32.672 W',
        'register': '§1.5, and docs/REFERENCES.md §2',
        'files': ['findings_recovery_correction.json', 'recovery_at_temperature.json'],
        'raw': [],
        'driver': 'python examples/findings_recovery_correction.py',
        'caveat': 'We apply the many-mode Carnot factor to the anti-Stokes term while the device '
                  'engineers fluorescence AWAY from that limit, so every recovered-power figure is '
                  'a LOWER BOUND. That is a design lever, not an error.',
    },
    {
        'slug': '06-transistor-simulated',
        'claim': 'The ASAP7 transistor is simulated, not interpolated: leakage, threshold, swing, '
                 'drive current and the V/F shape all come from BSIM-CMG in ngspice on the card.',
        'figure': 'dVt/dT -0.39/-0.46 mV/K; SS 61.0 mV/dec +0.20/K; alpha 1.45 fitted; the two '
                  'evidence files agree on I_off(T) to 0.76 %',
        'register': '§1.6',
        'files': ['device_leakage_spice_asap7.json', 'device_vt_vf_asap7.json'],
        'raw': [],
        'driver': 'python examples/device_leakage_spice.py; python examples/device_vt_vf_spice.py',
        'caveat': 'One device, one drawn length, no self-heating, no p-FET. The threshold is a '
                  'constant-current CRITERION (100 nA x W/L): compare slopes and shapes across '
                  'sources, never levels. The V/F anchor (3.8 GHz at 0.70 V) is the trace\'s '
                  'clock, a stated choice. The V_t lever re-priced on these inputs is in §2 -- '
                  'it is a re-derivation, not a thermal measurement.',
    },
    {
        'slug': '07-array-coverage',
        'claim': 'The array charged its own footprint costs nothing at the shipped pitch: a '
                 'quarter-coverage array holds the same ceiling on the same minimum plan. Under '
                 'corrected inputs the laser holds from 1.20 to 2.60 W/mm^2.',
        'figure': 'coverage 0.26 (644/1126 blocks under gaps, 74.8 mm^2 reserved): same rung, Q '
                  'within 1.6 % at a common peak; array_idle fails 1.20, array_on holds 2.60',
        'register': '§1.3',
        'files': ['array_coverage_armD.json'],
        'raw': ['results/array_coverage_armD'],
        'driver': 'scripts/array_coverage_ladder_armD.sh | scripts/campaign_inner.sh; '
                  'python examples/array_coverage_report.py',
        'caveat': 'Coverage cannot move a CONTROL-arm ceiling -- the control has no array. The '
                  '2.60 is an ENVELOPE result: the array removes more heat than the converged '
                  'die dissipates and the 3.00 failure is "envelope insufficient". Quote the '
                  'rescue range and the cost ladder, never the top rung as an operating point. '
                  '500 um pitch, 200 um burial, 34-core, 88 CFM, target 92 C, arm D.',
    },
    {
        'slug': '08-extractor-lift',
        'claim': 'The extractor\'s lift is a curve fixed by v98\'s own constitutive model (the '
                 'transparency cap), not a scalar and not a measurement; the target device is v98 '
                 'Table 1.1\'s R640-SMILES row; on this die it never binds, and a '
                 'fixed-wavelength GaAs pump has a hot-side limit.',
        'figure': 'target device 5900 W/mm^2 at 400 K, 813 at 300 K, 263 at 263 K, T_min 176 K '
                  '(sigma-independent collapse); GaAs fixed pump T_min 259 K, hot limit ~365-380 K; '
                  'coldest engaged tile on the die 263 K at 2.60 W/mm^2 with 0 tiles capped',
        'register': '§1.5',
        'files': ['extractor_cooling_curves.json', 'extractor_armD.json', 'extractor_v98.json'],
        'raw': ['results/extractor_armD', 'results/extractor_v98'],
        'driver': 'python examples/extractor_curves.py; scripts/extractor_rescue_points.sh | '
                  'scripts/campaign_inner.sh; python examples/extractor_report.py',
        'caveat': 'v98 supersedes v91: the bulk-film 10^3-10^4 W/mm^2 of v91 eq. 8.4 is withdrawn '
                  'and 10^3 is the Tier-I design point after the photonic ladder. The dye is a '
                  'hot-die platform (7x below design at 300 K tiles). Reproduces v98 Tables 8.1, '
                  '8.2, 8.3, 1.1 and Table 9.2; none of it rests on Yb:YLF. Keep --mr-dt-max 45 '
                  'alongside the curve: the scalar also shapes the plan.',
    },
    {
        'slug': '09-zone-mode',
        'claim': 'The photonic cold plate we test is single-material by default (architecture-'
                 'agnostic); the storage-zone material is Cr:LiSAF and the hot-zone material the '
                 'dye (user decision, 8 Sep); the floorplan-matched dual arrangement is a flag '
                 'and, on the hot-spot objective, a 1 % effect on this die.',
        'figure': 'single mode reproduces P0.20 to 2e-13 W (138.73 W, 93.875 C); dual mode at '
                  '2.00 W/mm^2: 80 cold tiles of 384, 23 capped, 0.10 W shortfall, plan +1.3 W, '
                  'peak -0.05 K; Cr:LiSAF 17.6-59 W/mm^3 at F_P 30-100 (ceiling at eta_EQE = 1)',
        'register': '§1.5',
        'files': ['zone_mode_smoke.json'],
        'raw': ['results/zone_mode_smoke'],
        'driver': 'python examples/mr_comparison.py ... --mr-extractor dye --mr-dt-max 45 '
                  '--mr-zone-mode {single,dual}; python examples/zone_mode_report.py',
        'caveat': 'A floorplan statement for this die and this cold-zone pattern only; never '
                  'transferable. The planner never drives the caches cold on the hot-spot '
                  'objective (coldest tile 290.7 K), so the storage-zone material has nothing to '
                  'do until the objective is cache leakage or the floorplan is the variable. '
                  'Cr:LiSAF fails breakeven at its demonstrated eta_EQE (0.85-0.95; needs > 0.94).',
    },
    {
        'slug': '10-cache-leakage-objective',
        'claim': 'The cache-leakage prize cannot be collected on the compute die at a price a '
                 'cooler can pay: holding the caches at their knee is conservation-bound and '
                 '20 K above it costs 77 % of die power (lower bound).',
        'figure': '280 K: the whole die (99 W plan on a 99 W die, zone at 289.5 K); 300 K: '
                  '>= 71 W = 77 %; cache leakage 2.7x / 3.6x down; Cr:LiSAF tiles 56 capped, 18 W short',
        'register': '§1.2',
        'files': ['d3_cache_objective.json'],
        'raw': ['results/d3_objective_v2', 'results/d3_objective'],
        'driver': 'scripts/d3_objective_smoke.sh; python examples/d3_objective_report.py',
        'caveat': 'Monolithic 34-core die, arm D, target device, planner objective cache-leakage '
                  '(§P0.22.2). Costs are LOWER bounds (baseline planning path; +3 % from 6 to 12 '
                  'iterations). The measured leg of the separate-die argument, not a two-die '
                  'measurement. Cr:LiSAF figures are ceilings at eta_EQE = 1. results/d3_objective/ '
                  'is the first pass: cache figures valid, die_leakage_W totals NOT (ledger rule).',
    },
    {
        'slug': '11-dense-cluster-family',
        'claim': 'The rescue travels to a denser execution cluster, and density is paid for in '
                 'cooling watts: the first re-measured design change (D1).',
        'figure': 'x0.5: holds to 202 W, plan 1.17-2.8x the reference; x0.25: holds to 162 W, '
                  '1.65-6.9x; 0 tiles capped; each loses the top rung to the stability boundary',
        'register': '§1.3',
        'files': ['d1_exec_density_family_result.json', 'd1_exec_density_family.json'],
        'raw': ['results/d1_family_arr', 'results/d1_family'],
        'driver': 'examples/generate_exec_density_family.py; scripts/d1_family_ladder.sh; '
                  'python examples/d1_family_report.py',
        'caveat': 'Matched die WATTS, not density (the members are 0.90x / 0.85x the reference '
                  'area). Arm D, 50 um, target device, scalar 45 K. Plans normalised to a 92 C '
                  'landing at 0.3247 K/W. Control-arm cliffs may still be open in the result file '
                  '(check "control_cliff_W"."bracketed").',
    },
    {
        'slug': '12-falsification-70core',
        'claim': 'The gen-0 ratios travel to a second floorplan and the absolute ceilings do '
                 'not: the 70-core die as a falsification test (D4).',
        'figure': 'flat ceiling 0.65/0.70 (34-core 0.85/0.90, down by the 1.40x the base '
                  'predicts); 127 W vs 86 W; cALU the runaway block at every failing shaped rung',
        'register': '§1.3',
        'files': ['d4_falsification_70core.json'],
        'raw': ['results/uniform_density_70core_armD', 'results/uniform_density_34core_c100_armD'],
        'driver': 'scripts/uniform_density_ladder_d4.sh; python examples/d4_falsification_report.py',
        'caveat': '100 um cells (the 70-core stack is 629 k unknowns at 50 um); read only beside '
                  'the 34-core matched-grid control, which moved neither cliff. Check "complete" '
                  'in the file: the shaped 0.45 rung may still be open.',
    },
    {
        'slug': '13-iso-package-70core',
        'claim': 'The laser\'s multiplier travels to the 70-core die and the watts do not: 2.2x the '
                 'driver\'s control (0.70 -> 1.60 W/mm^2, 301 W), s = 0.93 at the top rung, '
                 '9.0 TFLOP/s on the same air-cooled package (F1).',
        'figure': 'control 0.70 (137 W); unpowered array 0.80; laser 1.60 = 301 W; 2.00 no steady state '
                  'at full capability; 2.06x the cores at 4.03 GHz',
        'register': '§1.3',
        'files': ['iso_package_throughput.json'],
        'raw': ['results/iso_package_70core', 'results/array_coverage_armD'],
        'driver': 'scripts/iso_package_70core_ladder.sh; python examples/iso_package_throughput_report.py',
        'caveat': '100 um cells. GFLOP/s is the thermal-only proxy, flat at fixed core count: quote '
                  'the watts multiplier and the core-count multiplier, never "N x the compute" from '
                  'one die. Predicted 390-470 W, measured 301 (§P0.23.1 P2 falsified).',
    },
    {
        'slug': '14-dark-silicon',
        'claim': 'Dark-silicon recovery: at 1.2 W/mm^2 per core no contiguous quarter of the die '
                 'lights on this package, the unpowered GaAs layer lights a quarter, the laser '
                 'lights all 34 cores for 17 W; at 1.5 only the laser lights any fraction (64 W).',
        'figure': '17.3 W (10.6 net) at 1.2; 64.2 W (39.3 net) at 1.5; native 0.78 lights unaided; '
                  '1.0: control 50 %, passive layer 100 %',
        'register': '§1.3',
        'files': ['dark_silicon.json'],
        'raw': ['results/dark_silicon'],
        'driver': 'scripts/dark_silicon_ladder.sh; python examples/dark_silicon_report.py',
        'caveat': 'Hot cores are a contiguous block (worst case). The recovery claim starts at '
                  '~1.0 W/mm^2 per core: the driver\'s control lights the native die unaided '
                  '(§P0.23.2 P1 falsified -- it was written against the probe\'s ceiling). At 1.5 a lit '
                  'quarter costs more than a lit half (48.7 vs 43.0 W): measured.',
    },
    {
        'slug': '15-clock-as-free-variable',
        'claim': 'The laser converts thermal headroom into clock until the device\'s V/F ends it: '
                 '+14 % at 1.00 W/mm^2 and +26 % at 1.20 on the SPICE ceiling, +34 % on the shipped '
                 'table (F1c).',
        'figure': '1.00 W/mm^2: control 3.66 GHz, unpowered array 3.90, laser 4.17 (device ceiling, '
                  '38 W); table: 4.86 GHz thermal-limited at 2.28 W/mm^2 (235 W removed)',
        'register': '§1.3',
        'files': ['clock_f1c_density.json', 'clock_f1c.json'],
        'raw': ['results/clock_f1c_density', 'results/clock_f1c'],
        'driver': 'scripts/clock_f1c_density.sh; python examples/clock_f1c_report.py --base results/clock_f1c_density',
        'caveat': 'Operating point in W/mm^2 at the trace clock (--density); the trace\'s own 0.31 W/mm^2 '
                  'never meets a thermal limit (clock_f1c.json). Dynamic ~ V^2 f, leakage ~ V (assumed). '
                  'The SPICE 4.17 GHz and the table\'s 5.0 GHz are MODEL ceilings; above the table the '
                  'voltage clamps and no clock may be quoted. GFLOP/s per package watt falls with clock '
                  'on every arm.',
    },
    {
        'slug': '16-accelerator-microchannel',
        'claim': 'The array holds a GA100-class accelerator from 700 W to 2600 W on a direct-die '
                 'microchannel plate where the conventional stack has no steady state; the top rung '
                 'ends on conservation; a concentrated eight-SM kernel at 700 W is held for 32 W (F3).',
        'figure': '102 / 514 / 1289 / 2244 W removed at 1000 / 1400 / 2000 / 2600 W; s = 0.98 at 2600; '
                  'occ8 700 W: 32 W; max tile flux 5.3 W/mm^2',
        'register': '§1.3',
        'files': ['accel_f3_power_tol1.json', 'accel_f3_power.json', 'accel_f3.json'],
        'raw': ['results/accel_f3_power_tol1', 'results/accel_f3_power', 'results/accel_f3'],
        'driver': 'SHAPE=power ARRAY_ON_ONLY=1 TOL=1.0 MAXITER=100 scripts/accel_f3_ladder.sh; '
                  'python examples/accel_f3_report.py --base results/accel_f3_power_tol1',
        'caveat': 'The control runaway at 700 W is a simulated-curve, ASSUMED 25 %-leakage result on '
                  'an uncalibrated power split (calibrated: false); 100 um cells; needs the power '
                  'envelope shape (accel_f3.json shows the seed shape failing every kernel point) and '
                  'tol 1.0 (accel_f3_power.json rows are the same answers flagged unconverged on a '
                  '0.05 K residual). The device is 150x under-used: max tile flux 5.3 W/mm^2.',
    },
    {
        'slug': '17-burst-absorption',
        'claim': 'Burst absorption (F4): a 10 ms activity burst that the package rides on thermal '
                 'mass is removed at its source by the MODULATED array -- 2.5-3.3x less overshoot '
                 'per added watt; at 0.80 W/mm^2 a 2x burst sends the package 11 ms above the spec '
                 'and the modulated array holds the die under its target.',
        'figure': '0.80 W/mm^2, k=2: control 118 C (11 ms > spec), static array 109 C (6 ms), '
                  'modulated 87 C (0 ms > target, 70 W removed, 2.6 J); k=3: control and static '
                  'array non-viable (> 127 C), modulated 101 C (6 ms > spec); per added watt '
                  '0.51-0.67 K/W control, 0.51-0.54 static, 0.17-0.20 modulated; 1.00, k=3: the '
                  'static array runs away inside the 25 ms window',
        'register': '§1.3',
        'files': ['burst_absorption.json'],
        'raw': ['results/burst'],
        'driver': 'scripts/burst_ladder.sh; python examples/burst_report.py',
        'caveat': 'Transient 3D-ICE (1 ms slots, 10 sub-steps), each arm warm-started from its own '
                  'steady state; whole-die burst on DYNAMIC power at fixed voltage; feed-forward '
                  'modulation (the burst\'s own added watts removed at their source -- what a power '
                  'monitor commands; the array\'s microsecond optical response is ARGUED, the model '
                  'resolves the thermal one). A MARGIN claim: quote with the operating point and '
                  'its steady margin (0.80: 20 K under target; 1.00: 3 K, where the modulated array '
                  'still crosses the target at every k and the spec at k >= 2). Rows past 127 C '
                  'are non-viable, not temperatures; the 1.00/k3 static row is a transient runaway, '
                  'not a number. The extractor\'s per-tile cap is steady-only: the burst plan asks up to '
                  '13 W/mm^2 of one tile for 10 ms (1.00 / 3x; 5.2 at 0.80 / 2x), the first demand above '
                  'the steady ~5 W/mm^2 rule and 60x under the device at 300 K.',
    },
    {
        'slug': '18-pdn-em-skew',
        'claim': 'The rescue ladder is a current ladder and the ladder\'s non-thermal end is the PDN: '
                 'every rung above ~1.3 W/mm^2 runs the rails at 1.5-3x the native current, the dense '
                 'cluster doubles the peak rail current on top, and thermal clock skew grows with every '
                 'rung (a cost of the rescue, not a lever) -- X1/X2 on the recorded fields.',
        'figure': 'die current vs native 1.29 / 1.54 / 2.00 / 2.45 / 2.88x at 1.00-2.40 W/mm^2; x0.5 '
                  'cluster cALU 2.00x, x0.25 3.9x at matched watts; F1c laser 1.50x / 1.78x (SPICE) and '
                  '1.60x (table); Black n=2, Ea=0.9 eV: worst block 12x / 21x / 40x / 50x vs native at '
                  '1.20-2.40; cooling dividend 2.4x at matched power (1.10); core-domain dT 24 K native -> '
                  '32-60 K, 3.2 % -> 4.2-7.9 % of the period at D_ins 150 ps; uniformity buys 0.74 % at '
                  'matched power and the laser field is less uniform at matched density (+1 to +7 points)',
        'register': '§1.3',
        'files': ['pdn_em_skew.json'],
        'raw': ['results/fields'],
        'driver': 'python scripts/x1_fields_queue.py > results/campaign_queue/x1_fields.par4.tsv (node); '
                  'python examples/pdn_em_skew_report.py',
        'caveat': 'Fields and current densities MEASURED (the recorded final power maps re-solved once '
                  'through the session; peaks reproduced to +-0.000 K); every acceleration, lifetime, '
                  'skew percentage and the PDN LIMIT are ARGUED on stated constants (V_dd 0.70 V, n=2, '
                  'Ea=0.9 eV, D_ins 150/500 ps, alpha_R 0.40 %/K, alpha_cell 0.062 %/K). No rail model: '
                  '"binds: PDN" means the rails must be re-sized ~J x, not that the die fails. Quote the '
                  'gradient in K beside any skew percentage and n, Ea beside any lifetime.',
    },
    {
        'slug': '19-dense-cluster-utilisation',
        'claim': 'At the book\'s floorplan overheads (U = 70 %, T = 15 %, 20 um cache halos) the '
                 '"2x denser" cluster is 1.22x denser in silicon, the rescue holds every rung to 243 W, '
                 'and the cooling premium over a same-utilisation reference is 1.2-1.4x at the die-wide '
                 'rungs (X3).',
        'figure': 'members 137.7 mm^2 (1.36x) and 121.5 mm^2 (1.20x); plan vs reference 0.75 / 0.85 / '
                  '0.90x at 162 / 202 / 243 W, vs the utilisation control 1.44 / 1.22 / 1.16x (9.8x at '
                  '121 W); passive ceiling 60.7 -> 70.8 W with utilisation alone, back to 60.7 W with '
                  'the x0.5 cluster; 0 tiles capped',
        'register': '§1.3',
        'files': ['x3_utilisation.json', 'd1_exec_density_family_u70.json'],
        'raw': ['results/x3_u70'],
        'driver': 'python examples/generate_exec_density_family.py --factors 1.0 0.5 --utilisation 0.70 '
                  '--overhead 0.15 --cache-halo-um 20 --tag u70; scripts/x3_utilisation_ladder.sh; '
                  'python examples/x3_utilisation_report.py',
        'caveat': '100 um cells with the reference re-run on the same grid -- quote only beside those '
                  'ref rows (the 100 um reference plans are 8-50 % below the 50 um ones; its control '
                  'cliff is unchanged). Logic x 1.643 with McPAT power unchanged; halos as macro area '
                  'at constant power; normalisation at 0.3247 K/W measured on the 101 mm^2 die. P9 '
                  'falsified low (dies grow 1.36x / 1.20x, not 1.4-1.55x); P12 not as predicted.',
    },
    {
        'slug': '20-gen3-stack',
        'claim': 'The two-die stack with the storage die between the compute die and the sink '
                 'collects nothing the monolithic die did not: the 280 K objective costs the whole '
                 'die (99.3 W, s = 1.08) at every bond conductivity from hybrid to underfill, and an '
                 'isolating bond takes the compute die\'s sink away (X4). Gen 3 as argued is falsified '
                 'in this geometry; the storage die must be off the heat path.',
        'figure': '1.00 W/mm^2, bond 120 / 50 / 5 W/mK: dye 99.3 W, zone 289 K, cache leakage 4.70 -> '
                  '1.30 W (3.6x) for 66 W net; Cr:LiSAF 73.7 W, 58 tiles capped; 0.5 W/mK: unpowered '
                  'array diverges, nothing holds; hot-spot objective at 2.00: 121.8 W vs the 100 um '
                  'reference 126.1 W (-3.4 %)',
        'register': '§1.2',
        'files': ['gen3_stack.json'],
        'raw': ['results/gen3_stack'],
        'driver': 'python examples/split_storage_die.py; scripts/gen3_stack_ladder.sh; '
                  'python examples/gen3_stack_report.py',
        'caveat': '100 um cells; 50 um storage die on a 5 um bond, the array above it (the book\'s '
                  'face-to-back arrangement, sink side). The 0.5 W/mK rows sit on a hot-branch baseline '
                  'and are lower bounds. The cache prize itself (2.23x, 280 K knee, 3.6x) stands; what '
                  'is withdrawn is the geometry argued to collect it cheaply. The surviving variant '
                  '(storage die off the heat path, two sinks) is ARGUED. Anchor reproduced after the '
                  'stack/solver edits.',
    },
]

HISTORICAL = [
    {
        'slug': '01-cold-zone-prize-30-percent',
        'withdrawn': '"The cold-zone prize is 30 % of die power."',
        'replaced_by': '~6 % (recorded accounting) or ~14 % (corrected); better, the 2.23x ratio',
        'register': '§2',
        'files': ['cold_zone_prize_bounds.json'],
        'raw': [],
        'why': 'Rested on a static fraction and cache share computed on ONE core\'s leaves against '
               'the WHOLE chip\'s L3, on the trace\'s warm-up slice. Both defects were reproduced '
               'exactly (34.64 %, 92.6 %) and shown to be scope-and-slice arithmetic, not a '
               'plausible alternative reading. See PHASE0_CHECKLIST §P0.15.',
        'survives': 'Nothing quantitative. The file is the PROVENANCE record for how the wrong '
                    'pair was produced, which is why it is kept.',
    },
    {
        'slug': '02-clock-runaway-mechanism',
        'withdrawn': '"Above 0.1 K/W the part does not reach its 100 C spec limit -- it runs away '
                     'first."',
        'replaced_by': 'the part reaches spec at EVERY cooling point tested',
        'register': '§2',
        'files': ['clock_headroom_34core_7nm.json', 'clock_headroom_curve_compare.json'],
        'raw': [],
        'why': 'An artefact of the pipeline curve\'s hot tail, which is ~47x too steep at 500 K. '
               'On the measured curve the search ends at the spec limit, not in a runaway.',
        'survives': '`[!]` THE SUSTAINABLE CLOCKS IN THE TABLE SURVIVE -- only the MECHANISM is '
                    'withdrawn. This item is mixed, which is exactly why it is filed here: a '
                    'proposal writer reaching into it should read this note first.',
    },
    {
        'slug': '03-fan-affinity-law',
        'withdrawn': '"Fan power scales as R^-5; localized cooling is worth 22-35 % of system '
                     'power through fan displacement."',
        'replaced_by': 'fan power is LINEAR in heat carried; at today\'s extractor the optimum is '
                       'baseline airflow',
        'register': '§2',
        'files': ['fan_displacement_solved.json', 'hybrid_displacement.json'],
        'raw': [],
        'why': 'Used the textbook affinity law rather than the calibrated fan model. The '
               'displacement mechanism is real; its magnitude was not.',
        'survives': 'The measured airflow ladder rows inside `fan_displacement_solved.json` are '
                    'solver output and remain valid; the (1-s)^5 framing around them does not.',
    },
    {
        'slug': '04-density-ceiling-pre-correction',
        'withdrawn': '"The flat-die ceiling is 1.0-1.2 W/mm^2." Also: "the simulated curve makes '
                     'the ceiling higher because its hot tail is gentler."',
        'replaced_by': '0.85-0.90 W/mm^2, measured under corrected accounting (see quotable/03)',
        'register': '§2',
        'files': ['uniform_density_probe.json', 'uniform_density_curve_compare.json',
                  'uniform_density_curve_compare_fine.json',
                  'uniform_density_curve_compare_gidl_off.json',
                  'uniform_density_curve_compare_gidl_off_fine.json'],
        'raw': [],
        'why': 'Two independent corrections both push the ceiling down: the leakage curve and the '
               'per-core accounting. The DIRECTIONAL claim was also wrong -- the two curves cross '
               'at ~345 K, so the sign of the effect depends on which side a point sits.',
        'survives': 'The ladders themselves are valid measurements OF THEIR OWN CONFIGURATION and '
                    'are the control the corrected ladder is read against.',
    },
    {
        'slug': '05-first-law-recovery',
        'withdrawn': 'Every `p_mr_net_W` computed with the first-law recovery term -- 36 rows '
                     'report a NET-GENERATING cooler.',
        'replaced_by': 'the second-law form, `breakeven_ratio_at(T_h)`; corrected values in '
                       'quotable/05',
        'register': '§2',
        'files': ['FINDINGS.json', 'first_law_recovery_audit.json',
                  'loop_model_reconciliation.json', 'findings_harvest_correction.json'],
        'raw': [],
        'why': '`breakeven_ratio` omits the Carnot factor on the anti-Stokes term -- it is the '
               'phi -> 1 limit. At the shipped envelope it reports 1.032, i.e. free energy.',
        'survives': '`[!]` MIXED, and heavily used. `FINDINGS.json` is the harvested record of the '
                    'whole catalogue and most of its fields are fine; only `p_mr_net_W` carries '
                    'the defect. `first_law_recovery_audit.json` SIZES the exposure and is itself '
                    'a quotable piece of method. Read before reaching in.',
    },
    {
        'slug': '06-legacy-envelope-and-materials',
        'withdrawn': '"Yb:YLF is the cold-zone material." "eta_ASF ~ 0.02 is the demonstrated '
                     'state of the art." The pre-30-Aug device envelope (h_max 250 W/mm^2).',
        'replaced_by': 'thin-film GaAs tiles or SiN-encapsulated molecular dye; > 1000 W/mm^2; '
                       'eta_ASF 0.10-0.60 with 0.32 the working point',
        'register': '§2, and CLAUDE.md',
        'files': ['legacy_reproduction.json', 'rescue_measured_anchor.json',
                  'envelope_refresh_robustness.json', 'rescue_envelope_refresh.json'],
        'raw': [],
        'why': 'Yb:YLF is 2-3 orders of magnitude below both shipping platforms and is not a zone '
               'material at all. The 250 W/mm^2 envelope understated the platforms by 4-40x.',
        'survives': '`legacy_reproduction.json` is the BIT-IDENTICAL reproduction check for the '
                    'pre-array catalogue and must not be deleted -- it is how a legacy result is '
                    'verified. Yb:YLF numbers are retained in code solely so that check passes.',
    },
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def place(root, item, kind):
    """Copy an item's evidence, link its raw trees, write its provenance note."""
    d = os.path.join(root, item['slug'])
    os.makedirs(d, exist_ok=True)
    placed, missing = [], []
    for fn in item['files']:
        src = os.path.join(_EV, fn)
        if not os.path.exists(src):
            missing.append(fn)
            continue
        shutil.copy2(src, os.path.join(d, fn))
        placed.append({'file': fn, 'from': os.path.relpath(src, _REPO), 'sha256': sha256(src)})
    for tree in item.get('raw', []):
        src = os.path.join(_REPO, tree)
        link = os.path.join(d, 'raw-' + os.path.basename(tree))
        if os.path.islink(link):
            os.unlink(link)
        if os.path.isdir(src):
            os.symlink(os.path.relpath(src, d), link)   # relative: the tree stays movable
    _write_note(d, item, kind, placed, missing)
    return {'slug': item['slug'], 'files': placed, 'missing': missing,
            'raw': item.get('raw', [])}


def _write_note(d, item, kind, placed, missing):
    L = []
    if kind == 'quotable':
        L += ['# %s' % item['claim'], '',
              '**Figure:** %s  ' % item['figure'],
              '**Register:** `docs/RESULTS_REGISTER.md` %s  ' % item['register'],
              '**Reproduce:** `%s`' % item['driver'], '',
              '## Caveat that travels with this claim', '', item['caveat'], '']
    else:
        L += ['# WITHDRAWN — %s' % item['withdrawn'], '',
              '**Say instead:** %s  ' % item['replaced_by'],
              '**Register:** `docs/RESULTS_REGISTER.md` %s' % item['register'], '',
              '## Why it failed', '', item['why'], '',
              '## What survives in these files', '', item['survives'], '']
    if placed:
        L += ['## Files', ''] + ['- `%s` (from `%s`)' % (p['file'], p['from']) for p in placed] + ['']
    if item.get('raw'):
        L += ['## Raw solve trees', '',
              'Symlinked, not copied — they are gigabytes. Relative links, so this directory '
              'stays movable within the repo.', ''] + \
             ['- `raw-%s` -> `%s`' % (os.path.basename(t), t) for t in item['raw']] + ['']
    if missing:
        L += ['## `[!]` Not found at build time', ''] + ['- `%s`' % m for m in missing] + ['']
    name = 'SOURCE.md' if kind == 'quotable' else 'WHY_RETIRED.md'
    with open(os.path.join(d, name), 'w') as f:
        f.write('\n'.join(L))


QUOTABLE_README = """# results-quotable

**Evidence behind claims that may be cited.** Every directory maps to a claim in
`docs/RESULTS_REGISTER.md` §1 and carries a `SOURCE.md` with the claim, the figure, the command
that reproduces it, and **the caveat that must travel with it**.

`[!]` **Read the caveat.** It is not editorial trimming — each one has bitten at least once.

`[!]` **Curated, not exhaustive.** Only files a register claim names are here. `docs/evidence/`
remains the full working set of ~110 files, promoted and retired mixed together. A file's absence
from this directory means nobody has classified it, **not** that it is wrong.

| directory | claim | headline figure |
|---|---|---|
{rows}

## Before citing anything from here

1. Check `docs/RESULTS_REGISTER.md` §0 — the configuration these were computed under. Two solver
   defaults changed on 2–3 September 2026.
2. Read the `SOURCE.md` caveat.
3. Prefer a **ratio** to an absolute number where the register offers one. The 2.23× cold-zone
   improvement has survived four revisions of the percentage beside it.

Rebuild or check with `python scripts/build_results_registers.py [--verify]`.
"""

HISTORICAL_README = """# results-historical

**Evidence behind claims that have been withdrawn.** Kept deliberately.

A withdrawn number that leaves no trace comes back — from an older draft, an earlier slide, or the
memory of anyone who read the repository a fortnight ago. Several of these were *already* corrected
once and resurfaced. So each directory carries a `WHY_RETIRED.md` naming the claim, **what to say
instead**, why it failed, and — importantly — **what still survives inside the files**.

`[!]` **Several items are MIXED**, not wholly wrong: a table whose numbers survive but whose
mechanism does not, a harvest file where one field carries a defect and the rest are fine. Those are
filed here rather than in `results-quotable/` so that a proposal writer browsing for citations never
picks one up by accident. Read `WHY_RETIRED.md` before reaching in.

| directory | withdrawn claim | say instead |
|---|---|---|
{rows}

Nothing here should appear in a proposal, a slide, or a paper without first reading
`docs/RESULTS_REGISTER.md` §2.

Rebuild or check with `python scripts/build_results_registers.py [--verify]`.
"""


def build():
    out = {}
    for kind, items, readme in (
            ('quotable', QUOTABLE, QUOTABLE_README),
            ('historical', HISTORICAL, HISTORICAL_README)):
        root = os.path.join(_REPO, 'results-%s' % kind)
        os.makedirs(root, exist_ok=True)
        placed = [place(root, it, kind) for it in items]
        if kind == 'quotable':
            rows = '\n'.join('| `%s/` | %s | **%s** |' % (i['slug'], i['claim'], i['figure'])
                             for i in items)
        else:
            rows = '\n'.join('| `%s/` | %s | %s |' % (i['slug'], i['withdrawn'], i['replaced_by'])
                             for i in items)
        with open(os.path.join(root, 'README.md'), 'w') as f:
            f.write(readme.format(rows=rows))
        with open(os.path.join(root, 'MANIFEST.json'), 'w') as f:
            json.dump({'kind': kind, 'built_from': 'docs/RESULTS_REGISTER.md',
                       'note': 'sha256 is of the SOURCE file in docs/evidence at build time; '
                               '--verify re-checks the copy against it',
                       'items': placed}, f, indent=1)
        out[kind] = placed
        n = sum(len(p['files']) for p in placed)
        miss = sum(len(p['missing']) for p in placed)
        print('results-%-11s %d items, %d files%s'
              % (kind, len(placed), n, ', %d MISSING' % miss if miss else ''))
    return out


def verify():
    bad = 0
    for kind in ('quotable', 'historical'):
        root = os.path.join(_REPO, 'results-%s' % kind)
        man = os.path.join(root, 'MANIFEST.json')
        if not os.path.exists(man):
            print('results-%s: not built' % kind)
            bad += 1
            continue
        for item in json.load(open(man))['items']:
            for rec in item['files']:
                copy = os.path.join(root, item['slug'], rec['file'])
                src = os.path.join(_REPO, rec['from'])
                if not os.path.exists(copy):
                    print('MISSING COPY  %s/%s' % (item['slug'], rec['file'])); bad += 1
                elif sha256(copy) != rec['sha256']:
                    print('COPY EDITED   %s/%s' % (item['slug'], rec['file'])); bad += 1
                elif os.path.exists(src) and sha256(src) != rec['sha256']:
                    print('SOURCE MOVED ON  %s/%s -- docs/evidence has changed since the snapshot; '
                          'rebuild' % (item['slug'], rec['file'])); bad += 1
    print('verify: %s' % ('OK' if not bad else '%d problem(s)' % bad))
    return bad


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--verify', action='store_true', help='check for drift instead of building')
    a = ap.parse_args()
    sys.exit(verify() and 1 or 0) if a.verify else build()
