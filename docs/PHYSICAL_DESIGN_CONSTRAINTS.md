# Physical-design constraints for the core-evolution phase — what *SoC Physical Design* adds

**Written 10 September 2026** from `docs/chip_design_lit/SoC-Physical-Design.pdf`
(V. S. Chakravarthi, S. R. Koteshwar, *SoC Physical Design: A Comprehensive Guide*, Springer
2022, 173 pp). Book page = PDF page − 21. Read in full: floorplan/placement (pp. 31–48), CTS
(49–63), routing for timing and SI (76–80), design finishing and DFM (81–100: latch-up, antenna,
crosstalk, IR drop, EM, tap/decap/tie cells), 3D-SoC (122–129); the rest by heading.

`[!]` It is a practitioner's overview, mostly qualitative. Its value here is not numbers but
**the constraints our pipeline does not model**, stated by someone who tapes out. Every item
below says what the book gives, what we have, and what to do with it — ranked by how much it
changes the ladder.

---

## 1. The ladder's non-thermal end: IR drop and electromigration (book pp. 88–92, 36–37, 43–46)

**What the book gives.** The PDN is rings → stripes → rails (Figs 4, 8, 9); `V_sc = V_dd − IR`;
static vs dynamic IR drop, droop and ground bounce; **the listed causes include "concentrated
high density of cells in some parts of layout" and "higher signal switching in some parts of the
die"** — the fixes are wider/higher metal, more stripes, decaps ("decap cells are leaky and
increase leakage power"), and *spreading cells out*. EM: ion displacement driven by current
density, **temperature** and stress; fixes are width, upper metals, via stacking.

**What we have.** `CODESIGN_PLAN.md` §9 puts power delivery out of scope; nothing in the model
sees a rail. But the block power map *is* a current-density map at fixed `V_dd`, and every gen-1
move we made (D1: the cluster at 2×/4× its W/mm²; F1c: the laser rung at 4.86 GHz on a 230 W die)
raises local current per rail in proportion.

**What to do.** (a) A **PDN-headroom metric**: per block, `I/A = P_block / (V_dd · A_block)`
relative to the reference die's native map (the rails a conventional floorplan is sized for);
report the peak ratio per design. A design whose peak rail current doubles needs twice the
stripe metal or drops `V_sc`, which raises delay. (b) Couple it to the clock search: `V_eff =
V_dd − IR` with `IR ∝ local P/A`, so the cluster that the array cools *also* starves itself.
(c) **EM acceleration map**: Black's law `MTTF ∝ J⁻ⁿ exp(E_a / kT)`, `n ≈ 2`, `E_a ≈ 0.9 eV` for
Cu (stated as assumptions): per block, the acceleration factor of the design against the
reference at the reference's temperature. This gives the ladder its stopping rule in a form the
solve can name — **"binds: PDN"** — and gives the pack the reliability dividend of cooling (a
30 K cooler interconnect is ~7× EM lifetime at 0.9 eV). ARGUED from textbook physics until a
rail model exists; the metric itself is MEASURED from the fields.

## 2. Temperature-induced clock skew — uniformity as a clock lever (book pp. 52–58, 63)

**What the book gives.** `f_max = 1 / (T_comb + T_setup + T_skew + T_jitter)`; the frequency
cost of skew `(T_skew + T_jitter) / (T_comb + T_setup + T_skew + T_jitter)`; on-chip variation
(OCV) "including surface variations" is what CTS fights; > 1 GHz designs need clock meshes;
the clock network is 30–40 % of dynamic power; HVT/LVT swapping is used on clock paths.

**What we have.** Temperature fields per block; `relative_plateau`, `die_span_K` on every row
(§P0.5d); the D1 family's fields; the SPICE `I_on(V, T)` (0.942 at 400 K vs 300 K, §P0.18.3);
no delay model. A clock tree spanning a die with a 30 K gradient sees Cu resistance differ by
~12 % (α ≈ 0.4 %/K) end to end, and cell delay by a few %; skew from the *gradient* is a
frequency cost the array removes by flattening the die — a lever distinct from clipping the
peak.

**What to do.** A **thermal-skew metric**: with an H-tree span per clock domain (core-level:
one core; die-level: the whole die), `T_skew,thermal ≈ Σ_path d_i · (α_R ΔT_i + α_cell ΔT_i)`
between the hottest and coldest leaves, converted to a frequency cost by the book's formula
with a stated `T_comb` (the 3.8 GHz trace's period less setup). Compute it on the control,
idle and laser fields of the rescue ladder and the D1 family. Prediction: the array's
uniformity buys 1–3 % of clock at the 1.20–2.00 rungs on top of the thermal-limit gain of
§P0.26 — small, but it is the first *clock-tree* statement the project can make. ARGUED
(coefficients), MEASURED (the gradients).

## 3. Floorplan realism — utilisation, halos, channels (book pp. 34–36, 44–46)

**What the book gives.** Die area = ((G + T + E)/D + IO + M) / U with U = 70 %, T = 15 %
(scan, CTS, buffers), E = ECO; 30 % of the core for routing; macros (memories) get **halos**
(keep-outs) and **channels** sized as `pins × pitch / layers`; "memories following similar
guidelines are clustered into the same partition"; "all elements on the same supply in one
module".

**What we have.** The tiler (`examples/floorplans.py`) packs McPAT areas at 100 % utilisation
with no channels and no halos; the D1 family shrinks execution units to ×0.5 / ×0.25 of their
McPAT area with nothing added back.

**What to do.** (a) State it: every floorplan here is a **100 %-utilisation abstraction**; the
book's overheads make a real cluster ~1.4–1.6× larger for the same logic, which lowers its
W/mm² by the same factor — the D1 "2× denser" is nearer 1.3–1.4× denser in silicon. (b) Add
a `--utilisation` and a cache-halo option to the generator so a family member can be built at
the book's overheads, and re-measure the D1 rungs there (prediction: the rescue survives, the
cost premium shrinks toward 1.1–1.3×). (c) The clustering rules (same supply, same guidelines)
are the book's version of our zone template: the storage zone as one partition.

## 4. The gen-3 stack geometry (book pp. 122–128)

**What the book gives.** TSVs 12 µm on a 180 µm pitch through wafers thinned to **50 µm**;
microbumps < 10 µm pitch for face-to-face; face-to-face vs face-to-back; TSV stress and
keep-out zones; "PD flow should be thermal-aware — move hotspots toward the heat sinks and
apart from each other"; **thermal vias** from hot to cold regions; routers should route critical
nets away from hot regions; TSVs are ESD paths.

**What we have.** `stacked_memory_study.py` (a memory die over logic, a size limit at 50 µm
cells), the two-die array stack, the §P0.7 TEST 1 gradient result, D3's cache-leakage
objective.

**What to do.** Build the gen-3 stack with the book's numbers: a 50 µm storage die,
face-to-back over the compute die, a microbump/underfill interface layer with a stated
conductivity, TSV keep-outs as unpowered blocks; the array above the *storage* die (the cold
side) with Cr:LiSAF tiles and the dye array on the compute die's other face is the two-array
variant the ladder argued. Thermal vias are the book's own answer to the 1.24 K/40 W result —
they *raise* coupling, which is the opposite of what the storage zone wants; say so.

## 5. Multi-V_t and clock power (book pp. 60, 63)

HVT/LVT swapping on clock paths and "clock switching is 30–40 % of dynamic power" bear on D2
(§P0.18.3) and on how to read `core_other` (McPAT's clock network sits in the un-itemised
per-core power). A low-V_t cluster under the array is the book's clock-path optimisation made
spatial; its leakage cost is priced in §P0.18.3.

## 6. What does *not* inform the thermal co-design (book pp. 84–88)

Antenna effect (metal-to-gate ratio 100:1–5000:1, fixed by jumpers or diodes), crosstalk
(timing-window analysis, shielding, sizing), latch-up (guard rings, tap cells), well proximity
(±10 % delay) and stress (±30 %) are tapeout rules with no temperature coupling worth modelling
at this project's level. They belong in the "what a real core adds" paragraph of the ladder,
not in an experiment. The one exception is the leakage the book attributes to decaps and to
antenna damage ("increases gate leakage"): both are reasons a real die leaks *more* than
McPAT's split, which is the direction our static fraction is already suspected to err.

---

## The experiments this adds, in order (see `FUTURE_EXPERIMENTS.md` for the standing list)

| # | experiment | needs | cost | what it settles |
|---|---|---|---|---|
| X1 | PDN-headroom and EM-acceleration maps on the rescue ladder, D1 and F1c fields | a post-processing script over saved fields; `V_dd` 0.70 V, `E_a` 0.9 eV, `n` 2 stated | half a day | the ladder's non-thermal end, named from the solve; the reliability dividend | **Done 11 Sep (§P0.27):** the recorded fields had to be re-solved first (`examples/field_resolve.py`, 34 fields); die current 1.29–2.88× native along the ladder, the ×0.5 cluster's cALU 2.00× at matched watts; worst-block EM 12–50× vs native; the cooling dividend 2.4× at matched power; on the F1c SPICE rows the cooled design's worst block outlives the control's 2.7–3.2× at +14–26 % clock, on the table it ages 2.2× faster. `examples/pdn_em_skew_report.py`, register §1.3. |
| X2 | thermal-skew metric and its frequency cost, control vs array | the same script, an H-tree span per domain, α_R 0.4 %/K, cell α from SPICE | half a day | whether uniformity is a clock lever | **Done 11 Sep (§P0.27): it is not.** Core-domain ΔT 24 K native → 32–60 K along the ladder (3.2 → 7.9 % of the period at D_ins 150 ps); the laser flattens the worst core by 5.7 K = 0.74 % at matched power and is the LESS uniform field at matched density (+1 to +7 points). Skew is a cost of the rescue, growing with the rung. |
| X3 | D1 at the book's utilisation and halos | generator flags; one campaign | a day | whether the dense-cluster result survives realistic floorplanning | **Done 11 Sep (§P0.27.3 RESULT):** the rescue holds every rung to 243 W; plan 0.75–0.90× the reference's and 1.16–1.44× the utilisation control's at 162–243 W; the passive cliff scales with the cluster's density, not the die area (P12); P9 falsified low. Build: `--utilisation 0.70 --overhead 0.15 --cache-halo-um 20` built; members 137.7 mm² (×1, 1.36×) and 121.5 mm² (×0.5, 1.20×); the ×0.5 cluster is 1.22× denser in silicon, not 2×; 100 µm cells with a matched-grid reference (`results/x3_u70/`). |
| X4 | the gen-3 stack with the 3D chapter's geometry | `stacked_memory_study.py` extended; `--cell-um 100` | 1–2 days | gen 3 from ARGUED to MEASURED | **Done 11 Sep (§P0.27.4): gen 3 as argued is FALSIFIED** — with the storage die on the sink side of the compute die the 280 K objective costs the whole die at every bond (99.3 W, 120 → 5 W/mK), and an isolating bond (0.5) takes the compute die's sink away; the storage die must be off the heat path (2.5D or two sinks). Built as `StackSpec(storage_um, bond_um, bond_k_si)`, `split_storage_die.py`, `mr_comparison.py --gen3-split`. The book's "thermal vias from hot to cold regions" (p. 126) are the same lesson from the other side. |
