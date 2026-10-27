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
                 'lights all 34 cores for 12 W; at 1.5 only the laser lights any fraction (44 W).',
        'figure': '11.6 W at 1.2 (seed shape 17.3); 44.1 W at 1.5 (seed 64.2); a lit quarter at 1.5 4.1 W; '
                  'native 0.78 lights unaided; 1.0: control 50 %, passive layer 100 %',
        'register': '§1.3',
        'files': ['dark_silicon.json'],
        'raw': ['results/dark_silicon'],
        'driver': 'scripts/dark_silicon_ladder.sh; python examples/dark_silicon_report.py',
        'caveat': 'Costs are the per-block (power) envelope-shape plans (§P0.29); the seed-shape plans '
                  '(17.3 / 64.2 / 48.7 W) held but over-spent and are withdrawn as costs. The 1.2 / 25 % row '
                  'holds for 0.8 W at 12 planner iterations (its recorded "runaway" was an unfinished descent). '
                  'Hot cores are a contiguous block (worst case). The recovery claim starts at '
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
    {
        'slug': '21-integration-ladder',
        'claim': 'The rescue is insensitive to the degree of integration: the plan and the top rung '
                 'barely move as the tile plane is brought from 200 um to 20 um above the transistors, '
                 'and thinning to 20 um makes the die less forgiving (§P0.28, for the MXL-006 memo).',
        'figure': '2.00 W/mm^2, 500 um pitch: 126 / 113 / 119 / 131 W at 200 / 100 / 50 / 20 um burial; '
                  '200 um pitch 121 / 115 / 114 / 122 W; 2.60 holds at every burial; 3.00 only at '
                  'intermediate burial (289 W at 100 um); tile flux 5.0 / 8.2 W/mm^2 at 2.00, 14.8 at 3.00',
        'register': '§1.3',
        'files': ['integration_ladder.json'],
        'raw': ['results/integration', 'results/x3_u70'],
        'driver': 'scripts/integration_ladder.sh; python examples/integration_ladder_report.py',
        'caveat': '100 um cells beside the 100 um reference; the 3.00 rows are under the injected energy '
                  'cap; uniform seed envelope shape (the power shape may favour finer pitch at shallow '
                  'burial -- open). A decoupled cold plate on a 200 um die is within 10 % of a '
                  'die-integrated array on this floorplan.',
    },
    {
        'slug': '22-cooling-system-ledger',
        'claim': 'The cooling-system ledger: refrigerated air is beaten at every rung (1.6x at 1.20, '
                 '3.7x at 1.60) and has no solution above 1.60 W/mm^2; a chilled direct-die liquid '
                 'plate beats the laser until its coolant goes sub-zero (the crossover is between 2.00 '
                 'and 2.40 on this die). "> 10x COP" is the air statement where air has no solution.',
        'figure': 'air needs 273 / 243 / none / none K ambient; liquid plate 293 / 273 / 263 / 243 K inlet; '
                  'system COP air 1.65 / 0.52 / - / -, liquid 17.3 / 3.94 / 3.02 / 0.97, photonic '
                  '2.59 / 1.90 / 1.58 / 1.29 at 1.20 / 1.60 / 2.00 / 2.40 W/mm^2',
        'register': '§1.3',
        'files': ['cooling_system_ledger.json'],
        'raw': ['results/cop_ambient', 'results/array_coverage_armD'],
        'driver': 'scripts (queue): results/campaign_queue/cop_ambient.par8.tsv, cop_liquid2.par8.tsv; '
                  'python examples/cooling_system_ledger.py',
        'caveat': 'Temperatures MEASURED (control arm, 100 um, arm D, calibrated 35 W fan); pricing ARGUED '
                  'and stated (LCEstimator chiller COP gamma 0.4 with sub-zero penalties, pump 6.85 W held). '
                  'The laser side is the recorded seed-shape plan (an upper bound, §P0.29). Condensation '
                  'control and pump flow^3 scaling are not priced.',
    },
    {
        'slug': '23-rescue-ladder-per-block-shape',
        'claim': 'The rescue ladder under the per-block envelope shape: plans 18-33 % below the seed '
                 'shape\'s, and 3.00 W/mm^2 holds (s = 0.89) where the seed shape had no steady state -- '
                 'the "ends on conservation at 2.40" reading was the planner\'s, not the die\'s: it ends at 3.50 (§P0.29).',
        'figure': 'per-block plans 11.6 / 56.5 / 113.6 / 176.7 / 202.7 / 248.9 W at 1.20-3.00 (seed 17.3 / '
                  '75.3 / 138.7 / 221.5 / 251.2 / none); s 0.10-0.89; 0 tiles capped; max tile 19.3 W/mm^2',
        'register': '§1.3',
        'files': ['rescue_ladder_power.json'],
        'raw': ['results/array_coverage_armD_power', 'results/array_coverage_armD'],
        'driver': 'results/campaign_queue/ladder_power*.tsv (mr_comparison.py --mr-envelope-shape power); '
                  'python examples/rescue_ladder_shape_report.py',
        'caveat': '34-core, 50 um, arm D. The seed-shape rows remain that planner\'s plans and the anchor; '
                  'under the per-block shape the ladder ends on conservation at 3.50 (s = 0.99; 4.00 bistable). Quote every plan '
                  'with its shape. X1\'s current ladder is unaffected.',
    },
    {
        'slug': '24-generalized-fmax',
        'claim': 'A generalized f_max(V, T | logic depth, wire fraction, skew) with V_max from an '
                 'Arrhenius reliability budget at the cooled temperature: once wire, skew and '
                 'setup/jitter are in the period, the 10 % overdrive at the array\'s 92 C target buys '
                 '+1.6 % of clock (not +10 %); the budget buys supply as an Arrhenius ladder and TDDB '
                 'binds everywhere below the corner; 10 GHz needs a 6-7 FO4 pipeline on this device '
                 '(section P0.31 part 1, model arithmetic; part 2 is the coupled search).',
        'figure': 'anchor 3.8 GHz / 0.70 V / 330 K -> FO4_ref 8.18 ps, wire 70 ps, skew 8.3 ps, overhead '
                  '21 ps; V_max 0.778 / 0.792 / 0.814 / 0.863 V at 92 / 78.6 / 60 / 27 C; f_max 3.84 / '
                  '3.95 / 4.10 / 4.39 GHz (+1.6 / +4.4 / +8.4 / +16.1 % over the 100 C corner); device '
                  'peak clock at 0.95-0.975 V; N for 10 GHz 6.0-7.1; native budget: 92 C is EM-bound at '
                  '0.547 V / 2.82 GHz',
        'register': '§1.6',
        'files': ['fmax_model.json', 'device_vt_vf_asap7_v100.json', 'clock_fmax.json'],
        'raw': ['results/clock_fmax'],
        'driver': 'python examples/fmax_model_report.py; scripts/clock_fmax.sh > results/campaign_queue/'
                  'clock_fmax.par3.tsv (node); python examples/clock_fmax_report.py',
        'caveat': 'ARGUED on stated constants: qualification 0.77 V at 100 C, EM Black n=2 / 0.9 eV with '
                  'J ~ V f, TDDB power law n=40 / 0.6 eV (n 30-50 and Ea 0.4-0.8 move f_max < 0.3 %); '
                  'wire 30 % (+-3 %), overhead 8 %, D_ins 150 ps; FO4_ref inherits the 3.8 GHz anchor '
                  '(uncalibrated). The recorded 4.17 GHz (15-clock-as-free-variable) is the gate-only '
                  'ceiling. Quote every clock with its V/F source and the limiter the row names.',
    },
    {
        'slug': '25-cluster-transport',
        'claim': 'The 8x / 16x execution-cluster ladder at 20 um and 5 um burial: where heat transport '
                 'binds a >100 W/mm^2 functional unit (section P0.32).',
        'figure': 'see docs/evidence/cluster_transport.json and PHASE0_CHECKLIST section P0.32 RESULT',
        'register': '§1.3',
        'files': ['cluster_transport.json', 'd1_exec_density_family_x8x16.json'],
        'raw': ['results/cluster_transport'],
        'driver': 'python examples/generate_exec_density_family.py --factors 0.125 0.0625 --json-out '
                  'docs/evidence/d1_exec_density_family_x8x16.json; scripts/cluster_transport_ladder.sh > '
                  'results/campaign_queue/cluster.par6.tsv (node); python examples/cluster_transport_report.py',
        'caveat': '50 um cells: the 8x cALU is one cell and the 16x cALU sub-cell, so the modelled local '
                  'rise on the 16x rows is understated (up to ~2.5x) and every 16x hold is a lower bound '
                  'on the block\'s real peak. Per-block envelope shape; matched die watts; a row with '
                  's >= 1 is envelope-only, not a rescue. Rails scale with the density factor (X1).',
    },
    {
        'slug': '26-dense-cluster-per-block',
        'claim': 'D1 under the per-block envelope shape: the 2x cluster holds every reference rung to '
                 '243 W and the 4x cluster holds 202 W (both lost under the seed shape -- the lost rungs '
                 'were the planner\'s); the die-wide premium is 1.1-1.2x (x0.5) and 1.3-1.7x (x0.25) '
                 '(section P0.34).',
        'figure': 'x0.5: 6.1 / 17.4 / 73.6 / 130.4 / 188.5 W at 111 / 121 / 162 / 202 / 243 W (s 0.84 at '
                  '243), premium 2.0 / 2.0 / 1.20 / 1.20 / 1.08x; x0.25: 31.4 / 41.5 / 104.3 / 166.1 W to '
                  '202 W (s 0.89), premium 4.9 / 4.0 / 1.68 / 1.51x; x0.25 at 243 W envelope-only (s 1.02); '
                  'plans 9-59 % below the seed rows; both anchors reproduced (138.72881 / 113.63869 W)',
        'register': '§1.3',
        'files': ['d1_exec_density_family_power.json'],
        'raw': ['results/d1_family_power', 'results/anchor_2026-09-13'],
        'driver': 'SHAPE=power OUT=results/d1_family_power ARRAY_ONLY=1 scripts/d1_family_ladder.sh > '
                  'results/campaign_queue/d1_power.par4.tsv (node); python examples/d1_family_power_report.py',
        'caveat': 'Matched die WATTS, arm D, 50 um, target device, scalar 45 K, per-block shape; premiums '
                  'like-for-like within a shape only (the seed-shape record is 11-dense-cluster-family). '
                  'Never quote the x0.25 243 W row as a hold.',
    },
    {
        'slug': '27-ipc-of-f',
        'claim': 'IPC(f) from CoMeT\'s 1-20 GHz sweeps: the memory wall enters the throughput claims. At '
                 'the recorded F1c clocks the fixed-IPC proxy overstates the throughput gain by a fifth '
                 '(elasticity 0.78-0.84); CoMeT\'s DVFS voltage is a table, not a device (section P0.33).',
        'figure': 'FFT IPC 2.88 / 2.49 / 2.09 / 1.58 / 1.43 at 1 / 4 / 8 / 16 / 20 GHz, knee fit IPC0 3.06 '
                  'f_k 17.3 GHz (1 % residual); +13.9 % clock -> +11.4 % instructions/s, +25.5 -> +21.1, '
                  '+33.5 -> +26.1; 8 -> 16 GHz elasticity lu.cont 0.47, swaptions 0.84, FFT 0.60; '
                  'PeriodicVdd 1.2 V at every f',
        'register': '§1.3, §4',
        'files': ['comet_ipc_vs_f.json', 'clock_f1c.json', 'iso_package_throughput.json'],
        'raw': [],
        'driver': 'python examples/comet_ipc_reader.py; python examples/clock_f1c_report.py --base '
                  'results/clock_f1c_density; python examples/iso_package_throughput_report.py',
        'caveat': 'Measured in CoMeT (Sniper) on a different core and memory system: the SHAPE of IPC(f) '
                  'transfers, not the level. Only the frequency setting differs between CoMeT\'s configs; '
                  'nothing there says whether the device switches at 20 GHz (21-generalized-fmax does). '
                  'x264 rows read IPC 0 (outside the ROI); -test inputs are too short to quote.',
    },
    {
        'slug': '28-cluster-cold-end',
        'claim': 'The 8x cluster\'s lost top rung was the DYE\'S temperature dependence, not the film concept: '
                 'with a hot-zone material whose capability rises on cooling it holds 243 W; a dual-material '
                 'layout over the execution column suffices; plain GaAs fails; finer pitch makes the dye worse '
                 '(section P0.35).',
        'figure': 'retuned-enhanced GaAs: 8x holds 243 W at s 0.88 (20 um) / 0.91 (5 um), tile 235-242 K at '
                  '215 W/mm^2, 0 capped; 202 W plan 173.8 -> 142.9 W; dual = whole array on the 8x; 16x at '
                  '243 W no steady state with 0 capped; plain GaAs 5954 tiles capped; dye at 50 um pitch: all '
                  'four rows lost, 59-87 capped; eta_ASF at the coldest tile 0.010-0.016 (dye ~0.10)',
        'register': '§1.3, §2',
        'files': ['cluster_coldend.json'],
        'raw': ['results/cluster_coldend'],
        'driver': 'scripts/cluster_coldend_ladder.sh (write elsewhere, mv into results/campaign_queue/); '
                  'python examples/cluster_coldend_report.py',
        'caveat': 'The retuned-enhanced GaAs is v100 Table 1.1\'s CEILING design point: an upper bound on what a '
                  'cold-tolerant hot-zone material buys, at 6-10x the pump power per watt lifted at the coldest '
                  'tile. A dual-material array is a per-architecture layout: measured, never the default. 50 um '
                  'cells, per-block shape, matched die watts.',
    },
    {
        'slug': '29-compact-cluster-shape',
        'claim': 'The shape of a densified execution cluster is a design variable: compact helps to ~8x and '
                 'breaks at 16x -- past ~8x the units want perimeter (fingers), not compaction (section P0.36).',
        'figure': '8x compact 0.94 / 0.85 of the strip plan at 162 / 202 W and gains 243 W at 200 um pitch '
                  '(s 0.98); 4x compact gains 243 W at the D1 geometry (s 0.93), 3-8 % cheaper; 2x compact '
                  '+3-4 %; 16x compact holds only 111 / 121 W (1.5-1.6x the strip plan), no steady state at '
                  '162 / 202 W with 0 capped, unchanged without the 45 K lift and under either material',
        'register': '§1.3, §4',
        'files': ['compact_cluster.json', 'd1_exec_density_family_compact.json'],
        'raw': ['results/compact_cluster', 'results/compact_cluster_nolift'],
        'driver': 'python examples/generate_exec_density_family.py --factors 0.5 0.25 0.125 0.0625 '
                  '--compact-cluster --json-out docs/evidence/d1_exec_density_family_compact.json; '
                  'scripts/compact_cluster_ladder.sh; python examples/compact_cluster_report.py',
        'caveat': 'Same areas, powers, block names and die area as the strip members; only the shape differs. '
                  '50 um cells: the 16x units are sub-cell in both shapes (holds are lower bounds, losses firm). '
                  'Quote a dense-cluster row with its unit shape.',
    },
    {
        'slug': '30-two-sink-gen3-stack',
        'claim': 'Off the compute die\'s heat path the cache prize costs a ninth of the sink-side stack\'s, and '
                 'the storage die reaches its 280 K knee (section P0.37, the two-sink gen-3 stack, thermal side).',
        'figure': '1.00 W/mm^2, caches at 280 K on the dye storage array, 100 um isolation, 3 K/W far-face sink: '
                  '10.9 / 13.7 / 26.2 / 75.1 W at k = 0.025 / 0.1 / 0.5 / 5 W/mK, all on the storage array '
                  '(s 0.11-0.81), compute array 0 W, zone 280 K mean / 282 K max, cache leakage 3.5-4.0x down '
                  '(sink-side stack and monolithic die: 99.4 W, s 1.08, 286-287 K); no unpowered steady state with '
                  'the far face adiabatic or at 10-30 K/W; 13.7 / 20.1 / 39.8 W at 3 / 1 / 0.3 K/W; Cr:LiSAF capped '
                  'at every isolation (1.7 W short at k = 0.025, zone 290 K, 2.9x); laser 7.0 W net for 2.78 W saved',
        'register': '§1.2, §2, §3, §4',
        'files': ['two_sink.json', 'gen3_stack.json'],
        'raw': ['results/two_sink_v3', 'results/two_sink_v2', 'results/two_sink', 'results/anchor_2026-09-19'],
        'driver': 'scripts/two_sink_ladder.sh; python examples/two_sink_report.py',
        'caveat': 'Thermal side only: the isolation carries no via copper; the interface\'s construction is ARGUED. '
                  '100 um cells, seed shape, curve only, 12 planner iterations; held = converged descent with the '
                  'worst cache block inside the 2 K tolerance. Cr:LiSAF is a ceiling at eta_EQE = 1. The 2.00 W/mm^2 '
                  'rows are planner-limited (one envelope scalar over two dies). Pass the cache-only zone pattern. '
                  'THE LEAKAGE SAVED IS AN UPPER BOUND: the McPAT input gives the caches HP devices (item 33).',
    },
    {
        'slug': '33-cache-leakage-is-a-device-input',
        'claim': 'The caches\' share of on-die leakage (54 %) and the cold-cache prize in watts are a McPAT input: '
                 'the L2 / L3 bitcells are modelled as HP logic devices (section P0.40).',
        'figure': 'steady slice, 8 cores, 330 K: caches 1.652 W = 53.8 % of processor leakage with HP cells (as '
                  'recorded; static fraction 29.4 %) against 0.0054 W = 0.4 % with LSTP cells (306x; static 16.1 %); '
                  'LOP at this fork\'s 7 nm table is not credible (23x MORE leakage). CoMeT record: 2.5D x 111, '
                  '3Dmem x 40, 3D x 8, DDR x 0; the IPC(f) sweep is 2.5D; FFT t = 0.328/f + 0.0191 ns per instruction',
        'register': '§1.2 (head note), §2, §3, §4',
        'files': ['mcpat_cache_device.json', 'mcpat_cache_surface.json', 'comet_ipc_vs_f.json'],
        'raw': ['results/mcpat_cache_device'],
        'driver': 'bash spice_toolchain/tmp/mcpat_cache_device_ab.sh; python examples/mcpat_cache_device_report.py',
        'caveat': 'McPAT-native scope (not the floorplan ledger). A production cache array sits between the HP and LSTP '
                  'columns, far nearer LSTP. Ratios (2.23x, the 280 K knee) and every thermal-geometry result stand. '
                  'This is NOT a finding that a cold memory zone has no benefit (two points, one die): the McPAT surface '
                  '(section P0.42) puts the pay-off at ~2.5-3x the recorded leakage density -- fast cells beside a hot die. '
                  'The near-memory gains (3D +3 / +9 %, DDR -14 / -29 % at 4 / 16 GHz) are ARGUED from one recorded '
                  'sweep; the matched CoMeT sweep is written and not run.',
    },
    {
        'slug': '31-designed-finger-cluster',
        'claim': 'A DESIGNED finger layout -- every execution unit a full-width strip interdigitated with scheduler / '
                 'register-file logic at the tile pitch -- holds every rung to 243 W at 16x and at 32x (section P0.38).',
        'figure': '20 um burial, 100 um pitch, plan W (s) at 162 / 202 / 243 W: 16x finger 76.8 / 132.1 (0.70) / '
                  '170.5 (0.76); 16x strip 103.3 / 163.9 (0.88) / none; 16x compact none; 32x finger 87.7 / 145.0 / '
                  '190.0 (0.85); 32x strip 108.6 / none / none; 32x compact holds 111 W only; 0 tiles capped; the '
                  'compact 16x: nothing at 5 um burial (lift removed, either film); 162 W held at 50 um pitch under the '
                  'cold-tolerant film (117.0 W, s 0.78), 202 W lost',
        'register': '§1.3, §2, §3, §4',
        'files': ['finger_cluster.json', 'd1_exec_density_family_finger.json', 'd1_exec_density_family_x32.json',
                  'd1_exec_density_family_compact_x32.json', 'compact_cluster.json', 'cluster_transport.json'],
        'raw': ['results/finger_cluster'],
        'driver': 'python examples/generate_exec_density_family.py --factors 0.0625 0.03125 --finger-cluster '
                  '--json-out docs/evidence/d1_exec_density_family_finger.json; scripts/finger_cluster_ladder.sh; '
                  'python examples/finger_cluster_report.py',
        'caveat': 'Same areas, powers, names and die area in every shape of one factor. 50 um cells: a strip is one '
                  'cell tall in the tiler\'s and the designed layout alike (like for like); finger-vs-compact keeps '
                  'the sub-cell caveat. The cropped die on a 25 um grid is not built. Quote rows with the unit shape.',
    },
    {
        'slug': '32-rail-model-clock',
        'claim': 'With a static rail model (V_eff = V_dd - IR, rails sized for the native die to a 5 % budget) a dense '
                 'cluster on native rails loses a fifth of its clock, and re-sizing the rails ~J x restores it '
                 '(section P0.39).',
        'figure': 'laser arm, 92 C target, 101 W, per-block shape, fmax source, 20 FO4: 8x strip cluster 3.728 GHz '
                  'rail-off -> 3.019 on native rails (-19.0 % clock, -16.6 % f x IPC(f); 213 mV at 6.1x J_native; '
                  'rail:ir+reliability:tddb; die 62 W, array plan 0 W) -> 3.662 at 4x -> 3.775 at 8x; 16x: 3.693 -> '
                  '2.566 (-30.5 %, -26.8 %; 294 mV; 46 W, plan 0 W) -> 3.624 at 8x -> 3.699 at 16x; reference die at '
                  '1.00 W/mm^2: J 1.4x native, 49 mV, +0.3 % (inside the 0.05 GHz tolerance); designed fingers (P0.41): '
                  '3.728 GHz rail-off at 16x and 32x, 3.737 GHz widened by the density ratio (J 20x / 40x native), '
                  '2.04 GHz (16x) and no clock above 2 GHz (32x) on native rails -- the 16x native-rail clock is '
                  'path-dependent, quote 2.0-2.6 GHz',
        'register': '§1.3, §3, §4',
        'files': ['clock_rail.json', 'clock_fmax.json', 'pdn_em_skew.json'],
        'raw': ['results/clock_rail'],
        'driver': 'scripts/clock_rail.sh; python examples/clock_rail_report.py',
        'caveat': 'Static IR only (no L di/dt, no decap, no rail self-heating); the 5 % native budget and J_native are '
                  'STATED; TDDB / EM see the pin voltage. Clocks UNCALIBRATED (3.8 GHz anchor), bisection tolerance '
                  '0.05 GHz; quote with V/F source, limiter and IPC(f). Whether 8-16x the rail cross-section exists '
                  'over a 0.035 mm^2 unit is a BEOL question the model does not hold.',
    },
    {
        'slug': '34-memory-arrangement-sweep',
        'claim': 'Near memory and the cooler are complements: a clock gain keeps 0.78 / 0.47 of itself (4 / 16 GHz) on '
                 'interposer-class memory and 0.51 / 0.21 on off-package DDR; stacking under the cores adds 1-6 % '
                 '(section P0.43, the matched CoMeT sweep).',
        'figure': 'FFT vs 2.5D at 2 / 4 / 8 / 16 GHz: DDR -19 / -31 / -43 / -54 %, 3Dmem -1 to -4 %, 3D +1 / +2 / +2 / -1 %; '
                  'lu.cont: DDR -9 / -19 / -33 / -47 %, 3D +2 to +6 %; floor b = 0.20-0.24 (FFT) / 0.31-0.34 (lu.cont) of '
                  'the measured DRAM latency in every arrangement',
        'register': '§1.3, §3, §4',
        'files': ['comet_mem_arrangement.json', 'comet_ipc_vs_f.json'],
        'raw': [],
        'driver': 'ssh node-06: bash CoMeT/test/mem_arrangement_sweep/run_all_on_node.sh; '
                  'python examples/comet_mem_arrangement_report.py',
        'caveat': 'One workload class (SPLASH-2 small, 4 cores); CoMeT constant-latency DRAM model with a queue, '
                  '7.6 GB/s per controller in all four arrangements (no HBM bandwidth model); the 2.5D / 3D rows hold '
                  'no thermal samples. Name the memory arrangement with every throughput figure.',
    },
    {
        'slug': '35-memory-die-placement',
        'claim': 'A DRAM / HBM die beside, under or on top of the 2.00 W/mm^2 compute die sits at the '
                 'die\'s area-average temperature (27-70 C), never near the 85 C breakpoint; what the '
                 'array pays is the HEAT PATH the memory adds or removes -- 2.5D nothing, the far face '
                 '-6 to +16 W by its own sink, memory-on-logic 0 W for one hybrid-bonded die and +40 W '
                 'or no hold for an 8-high stack (section P0.44, the re-aimed gen 3).',
        'figure': 'reference 126.1 W; beside 123 W (-2.5 %), banks 27-30 C at 0.5-2 mm; far face through a '
                  '10,000-via field (k_eff 0.85): 120.0 / 132.4 / 141.6 W at 1 / 3 / 10 K/W, banks 47 / 59 / '
                  '67 C; aerogel 0.1 at 10 K/W: refresh runaway; memory-on-logic one die 126.1 / 133.6 W '
                  '(50 / 5 W/mK), 8-high 166.5 W (hybrid) / no hold (microbumps), 35 W at 1.00 W/mm^2',
        'register': '§1.2, §3, §4',
        'files': ['memory_die.json'],
        'raw': ['results/memory_die', 'results/memory_die_twins', 'results/anchor_2026-10-27'],
        'driver': 'scripts/memory_die_ladder.sh; python examples/memory_die_report.py',
        'caveat': '100 um cells, dye, --mr-dt-max 45 beside the curve (curve-only the envelope is '
                  'area-weighted and the banks starve the compute die), seed shape (per-block twins: '
                  'reference 99.2 W, far face 111.9 W). 8 x 3 W lumped into one 435 um die element; '
                  'power/dram.py is UNCALIBRATED (JEDEC conventions) -- quote placements and heat '
                  'paths, never memory watts. The storage array\'s 1.9-5.9 W on far-face rows is the '
                  'one-scalar envelope\'s share (banks 10-37 K under target), not a need. beside: one '
                  'slab (coupling an upper bound), shared-base warming ~1.8 K omitted. Quote placement, '
                  'k_eff with the via count, far-face R, dies, W per die, envelope shape.',
    },
    {
        'slug': '36-cache-latency-not-a-lever',
        'claim': 'Cache hit latency is not a throughput lever on CoMeT\'s SPLASH-2 kernels: L2 + L3 '
                 'access times at 50 / 75 / 150 % of the recorded move instructions per second by '
                 'under 0.5 % at 4 and 16 GHz (section P0.45). A cold / low-V_t cache\'s benefit, where '
                 'it exists, is a leakage benefit, not a throughput one, on this workload class.',
        'figure': 'FFT 4 GHz +0.1 / -0.4 / -0.2 %, 16 GHz -0.3 / +0.2 / +0.3 %; lu.cont +0.4 / +0.3 / -0.3 % '
                  'and +0.3 / +0.4 / +0.1 %; fitted a and b within 2 %; elasticity 0.77-0.78 / 0.45-0.47 '
                  'at every scaling',
        'register': '§1.3, §4',
        'files': ['comet_cache_latency.json'],
        'raw': ['/mnt/nfs01/scratch/jbalma/CoMeT/test/mem_arrangement_sweep/cachelat'],
        'driver': 'CoMeT/test/mem_arrangement_sweep/runit_cachelat.sh (docker, node-06, through the '
                  'campaign server); python examples/comet_cache_latency_report.py',
        'caveat': 'One workload class (SPLASH-2 small, 4 cores), 2.5D memory, CoMeT\'s constant-latency '
                  'DRAM; the kernels are DRAM-latency- and clock-bound. A cache-hit-bound kernel, larger '
                  'inputs or more cores are unmeasured. Says nothing about the LEAKAGE side of a cold '
                  'cache (section P0.45 stack rows are planner-limited above 1.00 W/mm^2).',
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
