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
