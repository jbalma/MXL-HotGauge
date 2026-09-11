# Future experiments — the second front beside the evolution ladder

**Recorded 10 September 2026 on the user's decision (9–10 Sep).** These are the experiments
that would show the largest, defensible impact of photonic cooling at the cold plate's ideal
design points on chip performance and energy utilisation. They run *alongside* the
architecture-evolution front (`docs/designs/EVOLUTION_LADDER.md`, `CODESIGN_PLAN.md` §9), not
instead of it. Every entry has a metric, a prediction with an effect size, a falsifier, what it
needs built, and a cost — because §P0.22 showed again that a prediction written first is the
only reason a wrong one is findable.

`[!]` **The decision that shapes the list.** The dramatic *energy* story — net electrical export
from the recovery loop — exists only in v100's Tier III regime (η_ASF ≥ 0.6, a hot source far
above 400 K: the export crossing is **614 K** for the 90 % laser preset, register §2), which no
rung of this ladder can reach without new metallization (v100 §10.9's BEOL wall). **It is
reserved for after the architectural evolution**, at the stage where ISA-classed, photonically
cooled core designs are optimised for maximum performance *and* energy recovery (Phase 4 of
`START_HERE.md`; `CODESIGN_PLAN.md` §9's "the levers, in the order they are expected to bind").
Until then the defensible energy statement is **performance per package watt at fixed cooling
infrastructure**, which experiments 1–3 below measure directly; "joules per operation" is not
a headline the apparatus can support at today's COP (electrical 0.272, effective 1.64 with
recovery at the top rung).

**One framing fact.** On the CPU die the target device is ~100× under-used: the most any tile is
asked for is 41 W/mm² (§P0.18.2) against 813 W/mm² at 300 K and 5,900 at the dye's 400 K design
point; the array's ceiling is conservation and bistability, never the extractor (§P0.19–20).
"Ideal design point" drama therefore comes from putting the device where the demand is
(accelerator hot spots, denser clusters, bursts) or from spending the freed headroom on
something other than temperature — not from a better film on this die.

---

## The ranked list (drama × defensibility ÷ cost)

| # | experiment | metric | prediction (effect size) | falsifier | needs | cost | status |
|---|---|---|---|---|---|---|---|
| **1** | **Iso-package compute scaling, in throughput** — the rescue ladder restated as sustainable GFLOP/s and GFLOP/s per *package* watt, then repeated on the 70-core die with the array | sustainable die watts and GFLOP/s at a fixed 88 CFM package, control vs array; the `s` ladder on the second die | the same package holds **3.8×** the die power (measured on the 34-core, register §1.3); a 196 mm² die holds **~450 W** on air with the array; the array's cost scales with die watts, not core count | 70-core array ceiling below 2.0 W/mm²-equivalent | `examples/iso_package_throughput_report.py` (done 10 Sep: the 3.8× is a **watts** multiplier — GFLOP/s is flat at fixed core count, so the compute multiplier comes only from F1b's cores); `scripts/iso_package_70core_ladder.sh` → `results/iso_package_70core/` | half a day | **done 10 Sep** (§P0.23 RESULT): laser holds the 70-core to **1.60 = 301 W** (predicted 390–470: falsified), 2.2× the driver's control; `s` = 0.93 at 1.60; **9.0 TFLOP/s** at the same package |
| **1c** | **Throughput with the clock as the free variable** (user, 10 Sep: the density ladders inject watts at a fixed clock, so their GFLOP/s is flat by construction) | sustainable clock per arm with dynamic ∝ V²f on the SPICE V/F; FLOP/s = f × IPC × cores per package watt | control runaway-limited 3.8–4.0 GHz; unpowered array spec-limited 4.1–4.3; laser to the 5.0 GHz table end (`vf_clamped`), +25–32 %; above the table 5.5–6.2 GHz ARGUED only | laser < 4.5 GHz | `scripts/clock_f1c.sh` (clock_headroom.py, three arms, `--vf-source spice`) | ~1–2 h | **done 10 Sep** (§P0.26): at 1.00 W/mm² control 3.66 GHz → laser 4.17 (the device ceiling, **+14 %**); at 1.20 **+26 %**; on the shipped table **4.86 GHz (+34 %)** thermal-limited at 2.28 W/mm²; efficiency per package watt falls on every arm |
| **2** | **Dark-silicon recovery** — active-core fraction at the thermal limit, at the die's native per-core power, control vs array (v100 §1.18: targeting makes dark silicon unnecessary) | the fraction of cores that can be active without losing the steady state; laser cost at 100 % | the traced die has no steady state fully lit (0.78 W/mm² is above the 0.60–0.65 cliff): **~25 % dark** without the array, **100 % active with headroom** with it, at ~the 1.20 rung's 17 W | the control holds fully lit; or the array needs > 50 W to light the last quarter | `scripts/dark_silicon_ladder.sh` → `results/dark_silicon/`; read back with `examples/dark_silicon_report.py` | one campaign | **done 10 Sep** (§P0.23 RESULT): at 1.2 W/mm² per core the control lights nothing, the GaAs layer a quarter, the laser all 34 cores for 17 W; at 1.5 only the laser (64 W). The native die lights unaided (P1 falsified — the driver's control, not the probe's) |
| **3** | **The accelerator at its real operating point** — GA100 (826 mm²) on the direct-die microchannel plate at 400–700 W, control vs array: the s-ladder and the rescue range where v100 Fig 1.6's hot spots live | sustainable power on the microchannel plate; per-tile demand against the device's rungs (Table 8.2) | the array raises the sustainable power of a microchannel-cooled accelerator **1.5–2×** before conservation binds; per-tile demand reaches **hundreds of W/mm²**, so the device's rungs finally matter | per-tile demand stays under 50 W/mm² (the device is still 10× under-used) | `accelerator_study.py` (parked since the one-die rule; the rule is lifted), 100 µm cells, the two-die stack's size checked against the 366 k limit; `ACCEL_COOLING` in `array_config.sh` | about a day | **part 1 done 10 Sep** (§P0.24 RESULT): on the simulated curve the control runs away at 700 W where the pipeline curve held 64 °C; the GaAs layer alone holds 700 W; the recorded planner's uniform envelope shape cannot address a concentrated kernel — `--mr-envelope-shape power` built; part 2 (power shape): every point finds a cool-branch plan to 2600 W, occ8 at 700 W for 32 W, max tile flux 5.3 W/mm² (**the device is 150× under-used on the accelerator too**) — part 3 (tol 1.0, 100 iterations) **done**: every row converged; the laser holds 700–2600 W, `s` = 0.98 at the top (conservation); occ8 at 700 W for 32 W; "the accelerator is where the device's rungs matter" withdrawn (5.3 W/mm² max) |
| **4** | **Burst absorption (temporal targeting)** — a transient solve with a 2× power step for 1–10 ms, control vs a modulated array: the "burst factor" before throttling (v100 §2.7, §10.12's boost-clock cliff) | how much boost, for how long, the die sustains before the 100 °C spec; the array's response time vs the package's thermal mass | the array holds a **2× burst the package throttles within ~5 ms**; the differentiator no conventional cooler has | the package absorbs the burst on its own thermal mass for the whole window | **built 10 Sep** (§P0.25): the array in `mode='transient'`, `mr_array.tile_power_schedule`, `examples/burst_absorption_study.py` (warm-started, feed-forward or planner modulation); `scripts/burst_ladder.sh`; read back with `examples/burst_report.py` | built in a morning; the six-point ladder ran 10 Sep (~100 min per point) | **done 11 Sep** (§P0.25 RESULT): at 0.80 W/mm² a 2× burst sends the package to 118 °C (11 ms above spec) and the static array to 109 °C; the **modulated array holds 87 °C, 0 ms above target, for 70 W (2.6 J)**; overshoot per added watt 0.51–0.67 K/W package vs **0.17–0.20 modulated (2.5–3.3× less)**; at 3× the package and static array are non-viable (> 127 °C), the modulated array 101 °C; at 1.00 (3 K of margin) the static array runs away inside the window at 3× and the modulated array crosses the spec at k ≥ 2 — a margin claim, quoted with its operating point |
| **5** | **The two-die cold-cache stack** — close gen 3 of the ladder: the storage die (L2/L3) held near 280 K on Cr:LiSAF, the compute die on the dye | die power saved at fixed throughput; the storage die's cooling margin; the interface's thermal isolation | **~14 % of die power** (register §1.2, corrected accounting) at a ~3× margin on the storage die's own cold leakage (1.35 W over 30 mm² against 0.18 W/mm² per 10 µm at η_EQE = 1) | the interface conducts enough that the cache never reaches 300 K (the 1.24 K/40 W result one layer up) | `stacked_memory_study.py` ported to the array stack at `--cell-um 100` (a size limit at 50 µm) | about a day | **done 11 Sep (§P0.27.4): the prediction is FALSIFIED** — with the storage die between the compute die and the sink the 280 K objective costs the whole die (99.3 W) at every bond from hybrid to underfill, and an isolating bond removes the compute die's sink; the cache prize stands (3.6× leakage), the geometry to collect it cheaply is off the heat path (2.5D or two sinks) — the next build |
| **6** | **The V_t lever end to end (D2)** — low-V_th on the cooled execution cluster at 25 mV, through the coupled solve | clock gained per kelvin of cooling; the MR budget it costs | **+7.6 % clock** on the cluster for 22–30 K of lift (§P0.18.3); the budget binds before the lift | the low-V_th die does not hold under the array at the 25 mV step | `clock_headroom.py --vf-source spice` with the leakage reference scaled by `10^(ΔV_th/SS(T))` on the assigned blocks (the missing piece) | half a day | planned — the only lever that is *device* headroom rather than thermal headroom; modest |

**Energy utilisation, as the list treats it.** Experiments 1–3 measure performance per package
watt at fixed cooling infrastructure — the honest energy claim today. The iso-throughput total
energy comparison (die + laser − recovery + fan against a bigger conventional package or liquid;
Tests 6b/6c in §P0.7 are the precedent) can be run at any time and is expected to show the
array winning on *density*, not on joules; it is worth one run so the statement is measured
rather than asserted. **Net export** waits for the Tier III stage (above).

---

## The physical-design front (added 10 Sep from *SoC Physical Design*, Chakravarthi & Koteshwar 2022)

`docs/PHYSICAL_DESIGN_CONSTRAINTS.md` maps the book onto this project and adds four experiments
that take the ladder past its thermal end: **X1** PDN-headroom and EM-acceleration maps from the
recorded fields (the non-thermal binding constraint, named), **X2** thermal clock skew as a
frequency cost (uniformity as a clock lever), **X3** the dense cluster at the book's utilisation
and halos, **X4** the gen-3 stack with the 3D chapter's geometry. They were the 11 Sep session's brief. **Status (11 Sep, §P0.27): X1 and X2 done** — the
rescue ladder is a current ladder (die current 1.29–2.88× native from 1.00 to 2.40 W/mm²; the
dense cluster's cALU 2× / 4× that), the ladder's non-thermal end is the PDN, and thermal skew
grows with every rung (uniformity is not a clock lever: P6 falsified); **X3 done** (§P0.27.3: at the
book's 70 % utilisation the dense cluster is 1.22× denser in silicon, holds every rung, premium
1.2–1.4× over a same-utilisation reference); **X4 done** (§P0.27.4: gen 3 as argued falsified — the
storage die on the sink side costs the whole die at every bond; off the heat path is the surviving design).

## What is reserved for after the architectural evolution

The ISA-classed, photonically cooled core designs (`CODESIGN_PLAN.md` §4–§7, `START_HERE.md`
Phase 4) are where **maximum performance and energy recovery** are optimised together:

- a compute zone whose metallization allows continuous operation above 400 K (v100 §10.9
  wall 1 — W/Mo/Ta BEOL, SiC/GaN devices), which is what moves the recovery loop toward its
  export crossing;
- the Tier III extractor cascade (η_ASF 0.3–0.6 by cascading, v100 Table 1.1's molecular rows;
  the `nir-cyanine` / `j-aggregate` presets are the cascade stages) on that hot zone;
- the storage zone on Cr:LiSAF at the 280 K knee (experiment 5's result carried over);
- the recovery ledger read at the *extractor's* temperature (`exergy_map(temperature_is=…)`,
  `recovery_at_temperature.py`'s export crossing by bisection), never the junction's.

Nothing in the current ladder licenses a net-export claim; the ladder's last rung ends at the
BEOL wall, and this document says why.

---

## How these are run

Predictions in `PHASE0_CHECKLIST.md` before any launch; one variable at a time; the 34-core
arm-D point at 2.00 W/mm² (plan 138.73 W, peak 93.875 °C) as the regression anchor; campaigns
through `scripts/campaign_server.sh`; every result lands in `RESULTS_REGISTER.md` as quotable /
withdrawn / open with its caveat, and in `results-quotable/` through
`scripts/build_results_registers.py`.
