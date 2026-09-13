# The evolution ladder — the 34-core 7 nm die under a photonic cold plate

**Written 9 September 2026 (§P0.22); §2.3 and the gen-1 row rewritten 11 September (§P0.27). Status: gen 0 and gen 1's constraint MEASURED; gen 1's
design MEASURED on the array rungs (D1, the first re-measured design change in the repository); **gen 1's NEXT constraint named from the recorded fields — the PDN, as a current density (MEASURED), as a limit (ARGUED)**; gen 2 ARGUED on measured inputs; gen 3's
monolithic-die constraint MEASURED, its design ARGUED.** Every number is a register row
(`docs/RESULTS_REGISTER.md`) or a §P0 measurement, cited by section; every claim carries a
**MEASURED** or **ARGUED** tag. Predictions for what was run today are in
`docs/PHASE0_CHECKLIST.md` §P0.22, written before the runs; the scorecard is at the end.

`[!]` This document argues how an architecture evolves once laser cooling is deployed on one
specific die. It is not a licensable core and it does not claim that an architecture *has* been
evolved — `docs/ARCHITECTURE_EVOLUTION.md` §5 says exactly which rows changed today.

---

## 0. The frame, and what a rung is

**The book's frame (v100 §1.18).** Every architectural choice trades against one inequality, the
architectural budget

    α N_tr C_eff V_dd² f  +  P_static(V_dd, T_j)   ≤   ΔT_lim · A_die / R_die            (1.32)

and photonic microrefrigeration at fraction `s` of the chip flux moves the right-hand side to

    P_chip^max,hyb(s) = ΔT_lim · A_die / [(1 − s) R_die]                                  (1.33)

— the cap doubles at `s = 0.5`, grows tenfold at `s = 0.9`, and *diverges as s → 1* (v100 §2.5).
In the cubic clock regime a doubled cap buys 2^(1/3) = 1.26× in `f`; a tenfold cap 2.15×. The
static term carries the threshold trap (1.29): `I_leak ∝ exp(−V_th / n ν_T)`, a decade per 60 mV
of `V_th` at room temperature and a doubling per ~10 K of `T_j` — so lowering `T_j` both suppresses
`P_static` and "relaxes the `V_th` lower bound". §10.9 then makes temperature a *per-tile*
design variable: compute (dynamic-dominated) wants to be hot, storage (static-dominated) wants
to be cold, and the template's reach is bounded by three walls — the Cu/low-κ **BEOL above
~400 K**, the **extractor material** per zone, and the **thermal-gradient / packaging** wall.

**What this project measures instead of assuming.** The pipeline solves (1.32) as a coupled
fixed point on a real floorplan (Sniper → McPAT → 3D-ICE with the leakage feedback closed,
`METHODS.md` §1) and names the binding constraint from the solve (`CODESIGN_PLAN.md` §9):
peak block, die-average path, leakage runaway, MR budget, V/F ceiling, or none. Two things it
finds that the inequality does not contain, and both shape the ladder:

- the control die's ceiling is a **leakage runaway** (`diverged` at every damping), which sits
  *below* the `ΔT_lim` wall — the die loses its steady state before it reaches its spec limit
  (register §1.3, §2 "it runs away first" withdrawn only as to the *cooled* clock search);
- the cooled die's ceiling is **energy conservation** — the array cannot remove more heat than
  the die makes — which (1.33) has no term for, and which is where `s → 1` actually ends
  (§P0.19, §P0.20).

**What a rung is** (§9's three invariants): the same trace, the same die power, the same MR
*electrical* budget. A rung names its binding constraint before the next is designed, changes
one architectural thing *because* of it, and re-measures. The ladder ends where the binding
constraint stops being thermal.

**The die.** 34-core 7 nm skylake, 101.1 mm², 1126 blocks, single-threaded LINPACK replicated
round-robin (`METHODS.md` §1.1); 88 CFM baffled fin on a fixed 1825 mm² base (0.325 K/W to this
die); arm D throughout (`--leakage-curve simulated --rbb-policy amortized --core-other-policy
hierarchy-consistent`, the shipped default since 9 Sep). Static fraction **32 %**
(hierarchy-consistent, §P0.16), of which the L2/L3 caches carry **54 %** and the leftover core
slab 18 % (`cold_zone_prize.die_ratios`, pinned by `test_mr_objective.py`). The cache zone is
**30.1 mm², 29.8 %** of the die.

**The device.** The target extractor is v100 Table 1.1's R640-SMILES row (rung 6 of Table 8.2:
5.9 × 10³ W/mm² at 400 K, 813 at 300 K, 263 at 263 K; `--mr-extractor dye`), the storage-zone
material is Cr:LiSAF (v100 §8.1.2; 20–80 W/mm³ at F_P 30–100, **every figure a ceiling at
η_EQE = 1**), the array geometry is v100 Ch. 9's tile — coupler / extractor / back-reflector /
sensor stacked *above* the silicon, fed by hollow-core fibre or waveguide, LPC monolithic on the
backside (Figs 1.11, 1.13, 4.1, 9.1, 9.12, 9.16) — so the tiles take no logic area (§P0.18.1).
`[!]` The **demonstrated 45 K lift** is not in v100; it remains Draft_5 §6.4.1 (Yb:YLF bench),
kept alongside the extractor curve because it also *shapes* the plan (§P0.19). Working point
η_ASF 0.32, laser 0.85, LPC 0.92 (targets; `METHODS.md` §4.1).

---

## 1. Gen 0 — the die as measured: what binds today

**Binding constraint: leakage runaway, entered through the hot block.** MEASURED.

| arm | holds to | fails at | the block that runs away | evidence |
|---|---|---|---|---|
| control, real power map (Gini 0.73) | **0.60 W/mm²** (76.6 °C) | 0.65 | `cALU_16` | `results/uniform_density_armD/shaped` (§P0.17) |
| control, flat map (Gini 0) | **0.85** (60.5 °C) | 0.90 | `core_other_5` | `…/uniform` (§P0.17); register §1.3 |
| unpowered array (GaAs in place of grease) | 1.10 (103.7 °C) | 1.20 | `cALU_0` | `results/array_coverage_armD/c1.00` (§P0.18.2) |

Read in (1.32)'s terms: the term that binds is **P_static(T_j)**, through its slope. The die is
lost not at the `ΔT_lim` wall but where the loop gain of leakage-on-temperature reaches one
(`METHODS.md` §3.2), and on the simulated curve that happens at 317–347 K for the points that
hold (§P0.14). The *shape* term is the other half: concentrating the same watts onto the
execution cluster costs **1.4×** of ceiling (0.85 → 0.60; register §1.3), because the peak block
— `cALU`, 142 × 115 µm at **29.2 W/mm²** against a die average under 1 — is where (1.32) is
tightest locally (v100 §1.18, "hot spots emerge from the local power-equation imbalance").

`[!]` Two consequences that the rest of the ladder rests on, both MEASURED: (i) the die as traced
(real map, 0.78 W/mm² native) has **no steady state on this package** under arm D — it is
above the 0.60–0.65 cliff — so gen 0 is a die that a conventional package cannot hold at its own
power; (ii) the hot-spot identity is stable: `cALU` runs away at every shaped rung, and the
upstream HotGauge study puts its hot spots on the same cluster (`ARCHITECTURE_EVOLUTION.md`
§2.2).

**What is *not* binding at gen 0.** The clock: the temperature-limited search on this package
ends at the **100 °C spec** at 4.20–4.34 GHz for cooling classes ≤ 0.1 K/W, and in runaway at
3.83 GHz at 0.3 K/W (`CLOCK_HEADROOM.md`; the mechanism re-read in §P0.15) — the spec and the
V/F table cap the clock long before cooling does. Power delivery was **out of scope**
(`CODESIGN_PLAN.md` §9) until 11 Sep: nothing here sees IR drop, but the block power map at a fixed
`V_dd` *is* a current-density map, and §2.3 now reads it — every rung that "injects more power"
injects current in the same ratio.

---

## 2. Gen 1 — laser cooling removes the runaway; the architecture spends it on density

### 2.1 What the cooler removes — MEASURED

The powered array holds the die from where the unpowered one fails to **2.40 W/mm² under
conservation** (213 W removed from a cooled die dissipating 222 W) and to 2.60 under the
injected-power cap; 3.00 has no steady state at full capability (`array_coverage_armD.json`,
`extractor_armD.json`, `extractor_v98.json`; register §1.3). **0 tiles capped** by the target
device at every rung; the coldest tile the array is ever driven to is 263 K (§P0.19–20). The
array's footprint is free at 500 µm pitch and 200 µm burial down to quarter coverage (§P0.18.2),
and 200 µm pitch buys what 50 µm buys (§P0.16).

The rescue as a ladder in the book's variable `s` (heat lifted optically / converged die power),
`results/array_coverage_armD/c1.00`:

| density W/mm² | heat removed Q | converged die P | **s** | 1/(1−s) | net MR electrical | cap vs the shaped control (0.625) |
|---|---|---|---|---|---|---|
| 1.20 | 17.3 W | 117.9 W | 0.15 | 1.17 | 10.6 W | 1.9× |
| 1.40 | 47.5 | 135.6 | 0.35 | 1.54 | 29.0 | 2.2× |
| 1.60 | 75.3 | 153.6 | **0.49** | 1.96 | 45.9 | **2.6×** |
| 1.80 | 110.1 | 170.6 | 0.65 | 2.83 | 67.4 | 2.9× |
| 2.00 | 138.7 | 188.5 | 0.74 | 3.79 | 84.4 | 3.2× |
| 2.20 | 178.1 | 204.2 | 0.87 | 7.8 | 108.5 | 3.5× |
| 2.40 | 221.5 | 221.0 | **1.00** | — | 136.3 | **3.8×** (conservation) |
| 2.60 | 251.2 | 239.0 | 1.05 | — | 153.6 | envelope only: the array is refrigerating the sink |

`[!]` **Corrected 13 Sep (§P0.29 part 3): the table above is the seed-shape planner's ladder, and
its end was the planner's, not the die's.** Under the per-block envelope shape (`--mr-envelope-shape
power`, each block capped at its own dissipation) the same rungs cost 18–33 % less — **11.6 / 56.5 /
113.6 / 176.7 / 202.7 / 248.9 W at 1.20 / 1.60 / 2.00 / 2.40 / 2.60 / 3.00**, s = 0.10 / 0.36 / 0.59 /
0.79 / 0.84 / **0.89** — and **3.00 W/mm² holds** where the seed shape had no steady state; **the ladder ends on
conservation at 3.50 (s = 0.99, 319 W of 322 W), and 4.00 is bistable** (the hot branch is the only
solution in the bracket). The seed shape spent light on blocks that did not
need it, so the conservation cap at 2.40 was met by the plan's waste. The s-ladder reading below stands
in form (the cap still beats (1.33) at s = 0.5 and conservation still ends it, two rungs higher, at 3.50);
the numbers to quote are the per-block ones, with their shape. `docs/evidence/rescue_ladder_power.json`.

`[+]` **Read against (1.33).** At `s = 0.5` the book's cap doubles; the measured cap is 2.6× the
shaped control's — *more* than (1.33), because the control's ceiling is a runaway below the
`ΔT_lim` wall and the first thing the laser buys is the instability, not the wall (§P0.14's
"leakage runaway is a local slope"), and because cooling gives leakage back (the converged die
at 1.60 dissipates 153.6 W on 158.5 W injected). And where (1.33) *diverges* — `s → 1` — the
measured ladder **ends**: at 2.40 the array lifts 100 % of the die's heat, 2.60 lifts more than
the die makes, 3.00 does not hold. The hybrid cap's asymptote is not reachable on a die whose
sink is the array itself. Both MEASURED; the reading of (1.33) is ARGUED.

`[!]` What is *not* claimed: any rung above ~1.6 as an operating point. At 2.00 the cooler draws
84 W net against a 188 W die under the seed shape (effective COP with recovery 1.64), less under
the per-block shape; the register's rule is to quote the **rescue range and the cost ladder, with the
planner's shape**, never the top rung.

### 2.2 What the architecture does with the freed constraint — ARGUED, D1 measures it

(1.32) can now grow ~2.5–3.8× on the left at the same package. Three places to spend it:

1. **Clock, `f`.** In the cubic regime a 2.6× cap is 1.37×; but the measured clock study says
   the die reaches its **100 °C spec at 4.2–4.3 GHz** with or without the array, and the array
   adds **+1.1 % for 0.6 W removed, +2.2 % for 24.9 W** (`CLOCK_HEADROOM.md`, MR on top of the
   0.1 K/W point). The clock is capped by the spec and the device's V/F, not by cooling. The
   register's clocks stand; the *lever* is small. MEASURED.
2. **Voltage, `V_dd`.** Same cap, same spec; and the V/F table stops at 5 GHz (`clock_search`
   sets `vf_clamped`) — "not an architecture result" (§9). Not a rung.
3. **Transistor density, `N_tr / A_die`.** The one term the cooler frees *specifically*: the
   array's granularity resolves a 142 × 115 µm unit (200 µm plateau), its coverage is free, and
   the demand it sees never exceeds 41 W/mm² per tile against 813 available at 300 K
   (§P0.18.2). A conventional floorplan spreads the execution cluster out because concentration
   costs 1.4× of ceiling (§1); under the array that penalty is what the laser closes (35/35
   rescues at 1.15, the whole ladder above). So the first thing to change is the thing the
   cooler was built for: **let the execution cluster get denser and hotter than a conventional
   floorplan allows, and keep the caches where they are.** v100 §10.9's "compute wants to be
   hot" and §10.10's "higher-density wire layouts" say the same from the device side.

**The design (D1, `examples/generate_exec_density_family.py`, §P0.22.3).** The 34-core die with
the execution units — cALU, iALU, FPU and, through the shipped 1.981× ratio, the AVX-512
accelerator — at **×0.5 and ×0.25 of their area**, everything else unchanged (the leftover
`core_other` slab is held invariant, the caches untouched; IMC/SoC/IO shrink with the die by the
tiler's convention). McPAT's per-unit power is the same, so the cluster runs at **2× and 4× its
W/mm²**; the die is 91.3 and 86.3 mm² (0.90×, 0.85×). Compared with the reference at **matched
die watts** (§9's invariant), not matched density.

**What the family measured (D1, `gen1_dense_cluster.md`, §P0.22.3 RESULT) — MEASURED.** At
matched die watts the laser holds the **2× denser cluster at every reference rung to 202 W
(2.00-equivalent) and the 4× denser one to 162 W**, with **0 tiles capped** on all ten rungs
and a cALU as the peak block everywhere. Two things the prediction got wrong, both instructive:
(i) **density is paid for in cooling watts** — where the reference needs no light (111 W, the
unpowered array holds it) the dense clusters need 15–35 W to hold the same watts, because the
hotter cALU must be clipped through its own sensitivity; the premium is 2.8×/6.9× at 111 W and
converges to **1.2×** by the die-wide rungs; (ii) **the top rung is lost** — the cool branch
disappears one rung (×0.5: 243 W not held, 114 °C on 193 W) or two rungs (×0.25: 202 W has no
steady state at full capability) below the reference's 2.40. So the rescue *travels* to a denser
cluster, and what binds gen 1 is the **MR electrical budget at the low rungs and the stability
boundary at the top** — neither the lift nor, yet, conservation. The passive ceilings fall with density
too: the ×0.5 control holds 50.5 W and fails 60.7 W where the reference holds (×0.25: 45.5 /
55.6 W) — the concentration penalty re-measured on a denser map (§P0.22.3 P1).

### 2.3 The non-thermal end of gen 1 — the rails, read from the recorded fields (§P0.27, X1/X2)

`SoC Physical Design` (Chakravarthi & Koteshwar 2022, pp. 88–92) names what the thermal solve
cannot: IR drop and electromigration rise with local current density, and "concentrated high
density of cells" is a listed cause. The recorded final power maps of the ladder, the D1 family
and the F1c rungs were re-solved once through the session (34 fields, peaks reproduced to
±0.000 K) and read as current densities `J = P / (V_dd A)` at the trace's 0.70 V against the
**native die** (the driver's control at 0.78 W/mm², 3.8 GHz — the rails a conventional floorplan
of this die is sized for). MEASURED as `J`; ARGUED as a limit (no rail model; Black's law with
`n` = 2, `E_a` = 0.9 eV stated).

| rung (fixed clock, 0.70 V) | die current / native | peak block `J` / native | worst block's EM acceleration vs native (Black, n = 2, 0.9 eV) |
|---|---|---|---|
| 1.00 (unpowered array holds) | 1.29 | 1.33 | 6.6 |
| 1.20 | **1.54** | 1.54 | 12 |
| 1.60 | **2.00** | 2.05 | 21 |
| 2.00 | **2.45** | 2.56 | **40** (cALU_32: J² 6.6 × temperature 6.0) |
| 2.40 (conservation) | **2.88** | 3.08 | 50 |
| D1 ×0.5 at 121 / 162 / 202 W | as the reference | **2.00× the reference's** | 43 / 96 / 143 |
| D1 ×0.25 at 121 / 162 W | as the reference | **3.9×** | 196 / 423 |
| F1c laser, 4.17 GHz / 0.77 V at 1.00 / 1.20 | 1.50 / 1.78 | 1.55 / 1.86 | 8.4 / 15 — **the control's worst block is 3.2× / 2.7× worse** (26.8 / 40.2, IF_0 leakage-bloated at 91.5 °C) |
| F1c laser, 4.86 GHz / 1.32 V on the table | 1.60 | 1.73 | 19.6 — 2.2× worse than the control's (8.8) |

**What this says.** (i) **The rescue ladder is a current ladder**: at fixed clock and supply the
laser holds a die whose rails carry 1.5–3× the current they were sized for — the peak block's
ratio is within 3–7 % of the die-average on the reference die, so this is every rail, not a hot
spot. (ii) **The dense cluster doubles the peak rail current at matched watts, exactly** — 2.00× on
×0.5, 3.9× on ×0.25 — because the array clips both clusters to the same 92 °C landing, so the
current ratio is the area ratio with no leakage premium. (iii) **The reliability dividend of
cooling is a matched-power statement**: 2.4× longer EM life at the peak block at 1.10 W/mm²
(laser vs unpowered array), 1.85× from the GaAs layer alone at native power; against the *native*
die the cooled die's worst block ages 12–50× faster along the ladder, roughly half of it (in
log terms) the current squared and half the 92 °C target sitting 15–30 K above where the native
die runs its cALUs. (iv) Spent on clock inside the device's V/F ceiling (F1c, SPICE), the cooled
design's worst block outlives the control's 2.7–3.2× while clocking 14–26 % faster; spent on the
table's 1.32 V, it ages 2.2× faster.

**Gen 1's next constraint, rewritten.** Not conservation (that is the top rung's, §2.1) and not
the stability boundary alone (§P0.22.3): **above ~1.3 W/mm² what binds is the PDN — unless the
rails are re-sized ~J× (2.5× the stripe metal at 2.00 W/mm², the book's own remedy), and the
target re-chosen on an EM budget rather than the spec.** The dense cluster's rails need 2× / 4×
that again. MEASURED as a current density; ARGUED as a limit until a rail model exists (register
§3). It is the first rung on this ladder whose binding constraint is not thermal, which is where
`CODESIGN_PLAN.md` §9 says a ladder ends — and it ends here for the *reference* floorplan's
rails, not for a floorplan whose PDN is designed for the array.

**The second non-thermal cost — thermal clock skew (X2).** The array pins the peak and lets the
rest of the die ride the average, so the core-domain gradient grows with every rung: **24 K on
the native die → 32 / 40 / 50 / 60 K** at 1.20 / 1.60 / 2.00 / 2.40 (worst core, L3 excluded),
which at a stated 150 ps core insertion delay is **3.2 % → 4.2 / 5.3 / 6.6 / 7.9 %** of the
period (die-level at 500 ps: 17 → 41 %, why a die this size runs per-core clock domains). At the
same injected power the laser flattens the worst core by 5.7 K, worth 0.74 % — uniformity is not
a clock lever on this die (§P0.27 P6 falsified); at the same density the laser field is the *less*
uniform one, a tax of 1–2 points of period on the SPICE F1c rungs and 7 on the table's, against
the +14 / +26 / +34 % of clock. The dense cluster adds 1.2× (×0.5) / 1.6× (×0.25) to the
gradient. Gradients MEASURED; the conversion ARGUED (quote kelvin beside every percentage).

### 2.4 The dense cluster at the book's utilisation (X3, §P0.27.3) — MEASURED at 100 µm

Every floorplan above is a 100 %-utilisation abstraction. Rebuilt at the book's overheads
(U = 70 %, T = 15 %, 20 µm cache halos; logic × 1.643 at McPAT's power, `d1_exec*_u70`) and
measured at matched watts on a 100 µm grid beside the reference re-run on the same grid:

| member | die | shaped control holds / fails | array plan at 162 / 202 / 243 W | vs reference | vs utilisation control |
|---|---|---|---|---|---|
| reference (100 µm) | 101.1 mm² | 60.7 / 70.8 W | 68 / 126 / 205 W | — | — |
| reference at 70 % utilisation | 137.7 mm² (1.36×) | **70.8 / 80.9 W** | 34 / 93 / 157 W | 0.52 / 0.70 / 0.78 | — |
| **×0.5 cluster at 70 %** (1.22× denser in silicon) | 121.5 mm² (1.20×) | 60.7 / 70.8 W | 51 / 109 / 183 W | **0.75 / 0.85 / 0.90** | **1.44 / 1.22 / 1.16** (9.8× at the 121 W hot-spot rung) |

**What it changes.** The D1 "2× denser" is **1.22× denser** in silicon; the rescue holds every
rung (0 tiles capped, 243 W included); the density premium over a same-utilisation reference is
**1.2–1.4× at the die-wide rungs**, ~10× at the rung where the control needs no light; the
passive cliff scales with the cluster's density and not the die area (utilisation alone buys one
rung, the cluster gives it back). X1's rail ratio for the cluster is 1.22×, not 2×, at these
overheads — gen 1's PDN constraint is a fifth tighter than the reference's, not twice. `[!]`
100 µm: the reference's 100 µm plans are 8–50 % below its 50 µm ones; never mix grids.

---

## 3. Gen 2 — spend the headroom on the device, not the clock: the threshold lever

**ARGUED on measured inputs (§P0.18.3); not run end to end (D2).**

Once density is bought, the next term in (1.32) the cooler can reach is `P_static(V_dd, T_j)`
through `V_th` — the trap of (1.29). On the ASAP7 card (BSIM-CMG, fitted to nothing; register
§1.6): swing **61.0 mV/dec at 300 K rising 0.20 mV/dec per K**, `dV_th/dT` −0.46 mV/K, α = 1.45.
The re-priced lever:

| ΔV_th | clock | leakage on the low-`V_th` blocks | cooling that pays for it | inside the demonstrated 45 K? |
|---|---|---|---|---|
| 25 mV | **+7.6 %** | 2.57× (300 K) … 2.03× (400 K) | **22–30 K** | yes |
| 50 mV | +15 % | 6.6× … 4.1× | 45–60 K | at its edge |
| 75 mV | +22 % | 8.4× (400 K) | 67–90 K | no |

`LADDER_GEN0` §2's "50 mV ≈ 22 K" is withdrawn (register §2). The design move is v100 §10.10's
fourth item made spatial: **low-`V_th` cells on the execution cluster the array cools, high-`V_th`
everywhere else** — a floorplan result and a device result through one mechanism. The array's
lift is not what limits it: on this die the tiles run at 263–330 K with the target device
263–1700 W/mm² in hand (§P0.20).

**What binds gen 2 — predicted: the MR electrical budget.** The leakage the low-`V_th` cluster
adds is paid in cooling watts at the electrical COP `η_ASF η_laser` = 0.272 (1.64 effective with
recovery at the top rung). A 25 mV step on a cluster carrying ~10 % of on-die leakage adds
~1.6 × 0.32 × 0.10 ≈ **+5 % of die power** in leakage, i.e. ~18 % of die power in gross laser
draw for +7.6 % of clock on that cluster — the budget binds before the lift does. ARGUED; the
falsifier is D2's coupled solve (`clock_headroom.py --vf-source spice` with the leakage reference
scaled by `10^(ΔV_th / SS(T))` on the assigned blocks — the missing piece, not run today).

---

## 4. Gen 3 — split the cache onto a cold die

### 4.1 The constraint — MEASURED, and re-measured today under the objective it needs

The cache is not hot; it is **leaky**: L2/L3 are 80–98 % static (§P0.7 TEST 1) and carry 54 % of
on-die leakage on 30 % of the area. Cooling it is worth **2.23×** more than the project's original
curve said, the prize is within 5 % of maximum by **280 K** (register §1.2), and the absolute
prize is ~14 % of die power under the corrected accounting (~6 % recorded; quote the ratio).

Three measurements say the cold zone cannot be on the compute die:

1. **40 W of removal buys 1.24 K of lateral gradient** on a 60.7 W die — two methods agree to
   1.7× (§P0.7 TEST 1). Conduction shorts the zones.
2. **The hot-spot planner never cools the caches** (§P0.21): at 2.00 W/mm² the dual-material
   plate is a 1 % effect because the coldest engaged tile is 290.7 K in either mode. A storage
   material has no job under the hot-spot objective.
3. **`[+]` The cache-leakage objective, built today and run on the monolithic die (D3, §P0.22.2,
   first pass at 1.00 W/mm², arm D, target device, `results/d3_objective/`):**

| objective (cache target) | plan | cache zone landed at | cache leakage (idle 4.88 W) | how it stopped |
|---|---|---|---|---|
| hot-spot (regression) | **0 W** | 55 °C mean, 79 °C max | 4.88 W | nothing above 92 °C — reproduces the reference row exactly |
| caches at **300 K**, curve only | **≥ 69 W** (70 % of the 99 W die) | 300 K mean, 324 K max | **1.88 W (2.6× down)** | descent unfinished: a LOWER bound |
| caches at **280 K**, curve only | **99 W = the whole die**; asked 110–121 W, scaled to conserve | 289 K mean, 317 K max | 1.35 W (3.6× down) | **conservation** — 15 K below ambient on 30 % of the die means the whole die sub-ambient |
| caches at 280 K, scalar 45 K kept | 99 W, same landing | 289 K mean | 1.35 W | conservation before the lift (P3 not as predicted) |
| caches at 280 K, **Cr:LiSAF on the cache tiles** | 73 W delivered; **57 tiles capped, 18 W short** | 301 K mean, 327 K max | 1.84 W | the storage material cannot carry the compute die's conducted heat (P6) |

`[!]` First pass, six planner iterations, lower bounds on cost; the twelve-iteration pass with
the corrected die-leakage ledger is running (`results/d3_objective_v2/`) and replaces these
rows in the scorecard when it lands. What is already decided: **holding the caches at their
leakage knee on the compute die costs the whole die's heat**, because the array has to cool the
ALUs to cool the caches — the measured 1.24 K/40 W, now seen from the planner's side.

### 4.2 The design as argued on 9 Sep — FALSIFIED by X4 on 11 Sep (kept as written; read §4.3)

A two-die stack: the **storage die** (L2/L3, 30 mm²-class) held near 280 K on Cr:LiSAF tiles;
the **compute die** at the hot-spot target on the dye, cooled by the gen-1 array. What the
separation buys, from the numbers above: the storage die's own dissipation at ~289 K is the
**1.35 W** of cold leakage plus its small dynamic share — ≈ **0.05 W/mm²** over the cache area —
against Cr:LiSAF's **0.18 W/mm² per 10 µm at 290 K** (η_EQE = 1, §P0.21). The same tiles that
fell 84 % short on the monolithic die (they were being asked to lift the ALUs' heat through the
silicon) have a 3× margin on their own die. **The separation is what makes the storage-zone
material viable, not a better film.** ARGUED from measured leakage; the film's own numbers are
ceilings at η_EQE = 1 — at the demonstrated 0.90 it heats (register §3).

What the gradient becomes: ~80 K between a 280 K storage die and a 365 K compute die across a
die-to-die interface — a fraction of §10.9's 300 K three-zone template, and the mildest form of
its packaging wall: the interface must conduct *selectively* (thermal isolation between dies,
through-stack signalling that does not short them), or the 1.24 K/40 W result is reproduced one
layer up.

**What binds gen 3 — predicted: something a cooler cannot fix.** The stack's interconnect —
bandwidth and latency across the die-to-die interface — and the interface's thermal isolation,
which is a packaging element (v100 §10.9 wall 3, §10.10 item 1). That is the honest end of the
thermal ladder on this die: past it, the limit is wire, not heat. ARGUED; the two-die solve
(`examples/stacked_memory_study.py`, a size limit at 50 µm — `--cell-um 100` works) is the
measurement, and it did not run today.

### 4.3 The two-die stack, measured (X4, §P0.27.4) — the storage die must be OFF the heat path

Built with the book's geometry (pp. 122–128): the reference's 68 L2/L3 blocks on a **50 µm
storage die**, face-to-back **above** the compute die on a **5 µm bond** of stated conductivity,
the array above the storage die (the cold side), 100 µm cells; the compute die keeps the cache
area as dark silicon. Anchor reproduced after the stack and solver edits.

| bond k (W/mK) | 1.00 W/mm², caches at 280 K on the dye | Cr:LiSAF on the cache tiles | compute die, hot-spot objective at 2.00 |
|---|---|---|---|
| 120 / 50 / 5 | **99.3 W, s = 1.08 (conservation), zone 289 K, cache leakage 3.6× down, 66 W net** — identical to the monolithic die's 99.4 W / 289.5 K | 73.7 W, **58 tiles capped** (monolithic: 73.5, 56) | 121.8 W held at 93.8 °C — the 100 µm reference's 126.1 W within 3.4 % |
| 0.5 (isolating) | the unpowered array **diverges** (the compute die's only sink is the 0.1 K/W bond); nothing holds | 80 capped, not held | — |

**What it says.** §4.2's argument held only if the compute die's heat did not cross the storage
die. In this stack **all of it does** — the storage die *is* the compute die's heat path — so the
array above it must lift the whole die to hold the caches cold, and the bond's conductivity
(swept 240×) changes the cost by under 0.1 % until it is low enough to take the compute die's
sink away. The 1.24 K / 40 W result of §P0.7 TEST 1 reproduced itself one layer up, as §4.2
warned. MEASURED. **Gen 3 as argued is falsified in this geometry.** The cache prize itself
(2.23×, the 280 K knee, 3.6× leakage reduction) is untouched.

**The surviving design — ARGUED.** The storage die must be *off* the compute die's heat path:
beside it on an interposer (2.5D) with its own tiles, or on the compute die's far face with the
compute die's sink and dye array on the other side (two sinks). Then the only heat entering the
storage zone is what the interface conducts laterally, and the 1.35 W argument of §4.2 applies.
Its measurement is a two-sink stack, which is a new stack template, not a flag — the next build.
Gen 3's row in the scorecard reads: constraint MEASURED (monolithic and stacked), design as
argued FALSIFIED, surviving variant ARGUED.

---

## 5. What is not a rung, and where the ladder stops

- **The dual-material plate is not a rung.** It is a per-architecture layout laid against one
  floorplan; the product is single-material and architecture-agnostic (`--mr-zone-mode single`,
  user's decision 8 Sep). Its only role is to *measure* what a storage material does — which it
  did today: on the monolithic die, fail (§4.1).
- **The hot end stops at the BEOL wall.** v100 §10.9 wants compute at 500–600 K for the exergy
  (φ = 0.14 at 350 K, 0.40 at 500 K) and says plainly that Cu/low-κ interconnect is not viable in
  continuous operation above ~400 K: a hot compute zone is a metallization story (W/Mo/Ta,
  SiC/GaN devices) before it is a cooling story. No rung here changes the metallization, so **no
  rung goes above 400 K**; McPAT refuses input there anyway, and this project reports > 127 °C
  as non-viable rather than as a number. The dye's 400 K design point is where it is strongest
  — and the die cannot go there. The recovery loop's **export crossing is 614 K** (90 % laser
  preset, register §2): on this die recovery is a cost reduction (effective COP 1.64 at the top
  rung), never a generator.
- **Yb:YLF is in no zone.** Retained only so the pre-30-Aug catalogue reproduces.
- **Turbo / boost policy** and anything resting on **power delivery** are outside the model
  (`CODESIGN_PLAN.md` §9).

---

## 6. Falsification — does any of this travel? (D4, running)

The 3 September prediction was: the ratios travel, the absolute ceilings do not. The 70-core
die (196 mm², same core, 0.234 K/W to the same base) runs the gen-0 ladder at 100 µm cells beside
a 34-core control on the same grid (§P0.22.0–1). Rows as they land, `results/uniform_density_70core_armD/`,
`…_34core_c100_armD/`:

| | 34-core, 50 µm (recorded) | 34-core, 100 µm (grid control) | 70-core, 100 µm |
|---|---|---|---|
| flat ceiling | 0.85 / 0.90 | 0.85 / 0.90 — unchanged | **0.65 / 0.70** (predicted 0.65–0.75) |
| shaped ceiling | 0.60 / 0.65 | 0.60 / 0.65 — same rung | **0.40 holds, 0.50 fails**, 0.45 unconverged (predicted 0.45–0.55: inside if 0.45 holds, one rung below if not) |
| ratio | 1.4× | 1.4× | **1.42–1.59** under either resolution of the undecidable rung (predicted 1.2–1.7) |
| hot block | `cALU` | `cALU` | **`cALU`** at every failing rung |
| highest holding flat watts | 86 W | 86 W | **127 W** (predicted 130–150) |

**MEASURED (§P0.22.1 RESULT).** The ratios travel and the absolute ceilings do not — down as a
density by the 1.40× the fixed base predicts, up as watts. Gen 0's statements are properties of
the floorplan family, not of one die.

---

## 7. Scorecard — the ladder in one table

| rung | binding constraint (from the solve) | evidence | tag | change made because of it | predicted next constraint | falsifier |
|---|---|---|---|---|---|---|
| gen 0 | leakage runaway through `cALU`; 0.60–0.65 shaped, 0.85–0.90 flat; the traced die has no steady state on this package | §P0.17, register §1.3 | **MEASURED** | — | — | — |
| gen 1 | conservation at **3.50 W/mm²** under the per-block planner (s = 0.99; 4.00 bistable; the seed shape's "2.40, s = 1.00" was the planner's limit, §P0.29) | §P0.18.2, §P0.19–20, register §1.3 | **MEASURED** | execution cluster 2×/4× denser at the same power (D1 family) — **re-measured**: holds to 202 W / 162 W, 0 tiles capped, cost 1.2–6.9× the reference's | **the PDN above ~1.3 W/mm², unless the rails are re-sized ~J×** (§2.3, §P0.27: die current 1.5–2.9× native along the ladder, the dense cluster's cALU 2× / 4× that at 100 % utilisation and 1.22× at the book's 70 % — §2.4; worst-block EM 12–50× vs native at n = 2, 0.9 eV) — MEASURED as `J`, ARGUED as a limit; thermal skew grows with the rung (3.2 → 7.9 % of the period) | §P0.22.3 P1–P4: P2 falsified on cost, P4 refined; §P0.27 P1–P4 confirmed, P6 (uniformity as a lever) falsified |
| gen 2 | (predicted) MR electrical budget | §P0.18.3 | **ARGUED** on measured inputs | low-`V_th` on the cooled cluster, 25 mV | budget/COP | D2's coupled solve |
| gen 3 | on the monolithic die: conservation at 280 K, ≥ 70 % of die power at 300 K; **on the two-die stack with the storage die on the sink side: the same, at every bond (X4)** | §P0.22.2, §P0.27.4, §P0.7 TEST 1, register §1.2 | constraint **MEASURED**; the design as argued **FALSIFIED** (§4.3); the surviving variant **ARGUED** | storage die on Cr:LiSAF at ~280 K **off the compute die's heat path** (2.5D, or the far face with two sinks) | interface isolation and two-sided packaging — not thermal | the two-sink stack |
| end | the limit is wire, not heat | v100 §10.9–10.10 | **ARGUED** | — | — | — |

**Predictions scored today** (§P0.22): filled in as the campaigns land — see the RESULT
subsections of §P0.22 and `gen1_dense_cluster.md`, `gen3_cache_objective.md`.

---

## 8. What the patent-facing text may and may not say (from this ladder)

**May say, as measured on this die:** the rescue range (unpowered array fails at 1.20, the laser
holds to 2.40 under the seed-shape planner and to 3.50 under the per-block one, on conservation) and the
cost ladder with its shape (seed 17 → 139 W at 1.20 → 2.00; per-block 12 → 114 W); the array's heat share `s` reaching 1.0 at the top rung; 0 tiles capped by the
target device; the 200 µm plateau and the zero coverage charge; the 2.23× cold-zone ratio and the
280 K knee; the 1.24 K/40 W gradient; the cache-leakage objective's cost on the monolithic die
(the whole die at 280 K; ≥ 70 % of it at 300 K, lower bound) **and on the sink-side two-die stack
(the same, at every bond — X4)** and the 2.6–3.6× cache-leakage reduction it buys; the `V_th` re-pricing (25 mV ≈ 22–30 K, +7.6 %); and whatever D1/D4 rows the
scorecard marks measured.

**May say, MEASURED on the recorded fields (§P0.27):** the die current relative to the native
die at every rung (1.29 → 2.88× from 1.00 to 2.40 W/mm² at 0.70 V), the dense cluster's cALU at 2×
/ 4× the reference's current density at matched watts, the core-domain gradient in kelvin.

**Argued, not measured:** the two-die design in its surviving form (the storage die off the heat path); **never** the 9 Sep form (storage die on the sink side, one array) as a design — it is measured and it fails; the dense-cluster design until D1's
rows say otherwise; the `V_th` lever until D2 runs; the reading of (1.33) against the ladder;
**every EM lifetime or acceleration (state `n` and `E_a`), every skew percentage (state `D_ins`),
and "binds: PDN" itself** — a re-sizing statement, not a failure, until a rail model exists.

**Never:** Yb:YLF as a zone material; a dual-material plate as the product; v91 eq. 8.4's
10³–10⁴ W/mm² for a bulk film; the 22 K `V_th` figure; "the cold-zone prize is 30 % of die
power"; any Cr:LiSAF figure without "ceiling at η_EQE = 1"; any top-rung ceiling as an operating
point; "an architecture has been evolved" beyond what `ARCHITECTURE_EVOLUTION.md` §5 says.
