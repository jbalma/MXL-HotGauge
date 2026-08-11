# HotGauge — Gap Analysis & Extension Design for Photonic-Cooling Studies

**Status:** analysis only (no code changes). Prepared for review before implementation.
**Scope:** the four goals in `project_goals.txt`.
**Evidence:** direct reads of the HotGauge source at `HotGauge_projects/HotGauge`, the microrefrigeration model at `../chip_thermal_model/chip_microrefrigeration_stable_v1.ipynb`, and the patched 3D-ICE/McPAT/Sniper interfaces.

---

## TL;DR

HotGauge is, today, a **one-way, open-loop power→temperature visualizer**, not a coupled electro-thermal simulator:

- **Power is computed once, at a fixed assumed temperature, and frozen.** Static/leakage power does **not** respond to the temperature field that 3D-ICE computes. The authors marked the exact hook as a `TODO`.
- **There is no performance model that responds to temperature.** No thermal throttling, no DVFS feedback, no T→f_max degradation. "Performance" is whatever Sniper produced at a fixed frequency, under a *constant-IPC* assumption.
- The only temperature-driven output is a **reliability/hotspot-severity heuristic**, not a performance or power metric.
- The toolchain is **x86-locked in five layers** (Intel SDE → Sniper x86 core models → `x86=1` McPAT XML → a forked AVX512 unit in McPAT C++ → a Skylake functional-unit taxonomy in the Python glue).
- The **floorplan integration surface is small and clean**, and injecting microrefrigeration as **negative power sources per functional unit** requires *no* solver changes.

The good news: every gap that matters for photonic-cooling studies is **additive**. The power-trace object already supports per-unit mutation, the floorplan→3D-ICE handoff is a single template file, and the vector-unit (AVX/RVV) modeling is already isolated. Nothing requires rewriting the core.

---

## Goal 1 — Power / performance / temperature coupling (the physics gaps)

### The pipeline is strictly one-way

```
Sniper (perf sim, FIXED freq)  →  per-interval activity stats (energystats-temp-<t>.xml)
      ↓
McPAT (power model @ FIXED assumed temperature)  →  dynamic + subthreshold + gate leakage per unit
      ↓
mcpat_to_blk_lvl_power_dict.py  →  block_powers_<t>.json   (dynamic + leakage SUMMED and FROZEN)
      ↓
3D-ICE (transient thermal solve)  →  temperature grid over time
      ↓
analysis.py / metrics.py  →  hotspot "severity" (a reliability proxy, NOT performance)
```

Temperature is **never fed back** to power or performance.

### Gap 1a — Leakage is temperature-independent (the feedback loop is an unimplemented TODO)

Leakage is computed by McPAT at whatever temperature its XML config assumes, then permanently summed with dynamic power. In `scripts/mcpat_to_blk_lvl_power_dict.py:239-243`:

```python
for unit_name in thermal_input_dict:
    # TODO: This is where we can also scale leakage (right before we combine them)
    # Look-up unit_name in temperature dictionary to get leakage scale factor (comes from 3D ICE)
    thermal_input_dict[unit_name] = sum(thermal_input_dict[unit_name])   # dyn + leak, frozen
```

The dynamic and subthreshold/gate-leakage components **are kept separate right up to this line** (they're carried as `[dynamic, leakage]` pairs throughout the file, e.g. lines 82-85, 102-108), then collapsed. So the plumbing to rescale leakage exists; the rescale itself was never written.

**Why it matters for cooling studies:** subthreshold leakage is exponential in temperature (roughly doubles per ~8-10 °C in this regime). Freezing it means:
- The model **cannot represent thermal runaway** or leakage/temperature positive feedback.
- It **understates the benefit of cooling** — you lose the entire static-power-savings term, which is one of the two headline benefits of photonic cooling (the other being higher achievable frequency).

### Gap 1b — No temperature-dependent performance model

`HotGauge/configuration/performance.py` (the *entire* file) is a static 8-point voltage↔frequency interpolation table:

```python
VF_PAIRS = [(0.6, 1.7), (0.8, 3.2), (1.0, 4.1), ... (1.4, 5.0)]
```

Performance (IPC, cycle count) comes out of Sniper at a **fixed** frequency and is never revised. The workload splicer states the assumption explicitly (`thermal/workloads.py:195`): *"The splicing assumes constant IPC at each frequency."* Consequences:

- **No thermal throttling / DTM**, no DVFS controller, no T→f_max degradation, no timing-guardband model.
- To change frequency you must **re-run Sniper** at that frequency; there is no analytical performance response.
- "Performance impact of temperature" — the central question in goals 3 and 4 — is currently **unrepresentable** in the core.

### Gap 1c — The only T-driven output is a reliability heuristic

`HotGauge/thermal/metrics.py:35` `severity_metric(MLTD, T)` is a hand-tuned product of sigmoids: one on absolute temperature (centered 60 °C, breakdown term at 115 °C) and one on **MLTD** (Maximum Local Temperature Difference — a local spatial gradient). It's a hotspot-stress / thermal-reliability / side-channel score. Useful for what it is, but it says nothing about GHz, IPC, or watts.

### What Goal 1 requires (additive)

1. **T-dependent leakage rescale** at the `mcpat_to_blk_lvl_power_dict.py:241` hook — a per-unit `leakage(T) = leakage_ref · f(T)` factor keyed on the 3D-ICE per-block temperature (`Tflp` output already exists, `ICE.py:314`).
2. **An outer power↔temperature iteration** (or timestep-marched feedback) so the leakage rescale and the thermal solve converge, instead of running once.
3. **An explicit T→frequency / T→performance model** (guardband/`f_max(T)` + optional leakage-aware DVFS policy) so cooling can be cashed out as either higher frequency at fixed power or lower power at fixed frequency.

The clean injection point is the `PowerTrace` object (`power/traces.py`), which already supports per-unit mutation via `trace[unit] = new_powers`.

---

## Goal 2 — Instruction-set support (x86 lock-in and the RISC-V path)

x86 assumptions are **layered across all four tools**, not localized:

| Layer | x86 lock-in | File / evidence |
|---|---|---|
| Front-end instrumentation | Intel **SDE** (`--sde-arch`, e.g. `tgl`=Tiger Lake) — strictly x86 | `end_to_end/run_HotGauge.py:369,382`; `config_template.yaml:26` |
| Sniper core models | `core_model = nehalem`, branch predictor `pentium_m`; cost model in **fused µops** | `examples/skylake_14nm.cfg:9,24`; Sniper patch `tools/mcpat.py` @314769 |
| McPAT XML | `x86=1`, `micro_opcode_width=8`; comment "all instructions refer to (fused) micro-ops" | McPAT patch @6414-6415, @6478 |
| McPAT C++ fork | A bespoke **AVX512** functional-unit type; `else if (fu_type == AVX512)` scales FPU power/leakage by hardcoded `512/32`=16× | McPAT patch `logic.cc` @27154-27168; `XML_Parse.{h,cc}` @24057-24076 |
| HotGauge Python glue | Hardwired **Skylake FU taxonomy** + AVX-derived-from-FPU hack | `scripts/mcpat_to_blk_lvl_power_dict.py:32-67`; `configuration/mcpat.py:21-62,132-162`; `power_model.py:13-15` |

**Native RISC-V support in the tools:** McPAT has **no** RISC-V ISA model (Alpha/x86/Niagara only); the `x86` flag toggles CISC/µop overhead vs. a generic RISC-ish path. Sniper *as wired here* is x86-only (SDE + Intel core models), though upstream RISC-V forks of Sniper exist.

**Where RISC-V would have to hook in (in dependency order):**
1. **Front end** — replace Intel SDE / `--sde-arch` with a RISC-V-capable driver; swap `nehalem`/`pentium_m` core+predictor models.
2. **Sniper→McPAT stat mapping** (`tools/mcpat.py`) — µop-based accounting → native RISC-V instruction accounting; AVX512 stanzas → RVV (vector).
3. **McPAT XML** — `x86=1`→`0`, drop µop params; the forked AVX512 additions become an RVV analog or are removed.
4. **FU taxonomy (the biggest change)** — the hardwired unit list, the `MCPAT_UNIT_NAME_MAP`, and the AVX-from-FPU derivation all encode Skylake blocks (complex/simple decoders, microcode, dual iRAT/fpRAT, AVX512). A RISC-V core substitutes a different set (vector register file + lanes, simpler front end, no x86 decoders).
5. **Physical floorplan** — the shipped `.flp`/`.stk` are Skylake die layouts; a RISC-V chip needs its own floorplan whose block names match the new taxonomy (both ends of `power/mcpat.py:34-52` must agree).
6. **DVFS / tech models** — `VF_PAIRS`, `NODE_*_FACTORS`, `CLK_FREQ=5e9` are Skylake-calibrated.

**Convenient fact:** the AVX/vector modeling is already **isolated** in `configuration/mcpat.py:132-162` and is *synthetic* (AVX area/power derived from the FPU, zero-power by default). The "real" AVX512 path in both Sniper and McPAT is present but **commented out / unfed**. So the vector-unit story can be swapped for RVV without touching the core dataflow — the single most encouraging thing about the RISC-V effort.

> **Recommendation:** full RISC-V support is a large, multi-tool effort (weeks, and gated on external tool availability). It is **not** on the critical path for the photonic-cooling physics (goals 1, 3, 4), which are ISA-agnostic once you have *a* block-power trace + floorplan. Suggest treating goal 2 as a **parallel track** and, near-term, defining a clean **ISA-neutral block-power/taxonomy interface** so RISC-V (or any front end) can feed the thermal/cooling machinery without the Skylake hardcodes. This also de-risks goals 3-4.

---

## Goal 3 — Microrefrigeration integration (imposed cooling / temperature)

### Two structural facts

**(a) The MR model is reduced-order (lumped), not spatial.** `chip_microrefrigeration_stable_v1.ipynb` is a 1D/lumped thermal-resistance-network optimizer: `PumpParams` / `ThermalParams` / `BUParams`, spreading resistances (`RHH_up`, `RBB_up`, `spreading_terms`), `s_required(u, q, tp)`, `temperatures(q, u, s, tp)`, `optimize_at_q`, hybrid convection+MR candidates, and COP curves. Its natural output is **per-heat-flux**: given a block's power density `q = P/area`, it returns required laser-cooling power `s`, achievable temperature, and COP. So the correct coupling is **per-functional-unit**, not a monolithic map.

**(b) 3D-ICE offers two viable injection mechanisms** (`thermal/ICE.py`, `HotGauge.3D-ICE.ThermalInit.patch`):

- **Negative power sources — chosen approach (forward direction).** The `.flp` maps each block name to a comma-separated power time-series (template substitution, `ICE.py:235-245`; format `IMC : position…; dimension…; power values {powers[IMC]};`). Inject the MR cooling distribution as **negative entries** per block. No solver modification; directly represents localized heat *extraction*.
  - ⚠️ **One thing to validate empirically first:** that the patched 3D-ICE 3.0 accepts negative cell power without clamping. It solves a linear system so it *should*, but the solver source is fetched by `get_and_patch_3DICE.sh` and not in-repo, so this needs a 1-cell sanity test before we build on it.
- **`TSTACK` imposed-temperature initialization (inverse direction).** The ThermalInit patch adds loading a full 3D grid of temperatures to initialize the stack (`initial temperature "file"`, `ICESimConfig.initial_temp_lines:117-159`). But this is an **initial condition that then relaxes**, not a sustained Dirichlet boundary. Holding a block *at* a target temperature is **not natively supported** — the heat sink is a single uniform convective BC (`heat transfer coefficient 1.0e-7; temperature 303.15`, 50 µm cells, `stack_templates/skylake.stk`). A true fixed-temperature boundary would require a solver/stack change (spatially-varying heatsink layer).

### Recommended Goal-3 architecture (per your selection: per-block negative power)

A **bridge module** that:
1. Reads HotGauge `block_powers_*.json` + floorplan geometry (per-block area).
2. Computes per-block power density `q = P/area` per timestep.
3. Calls the MR functions to get per-block cooling power `s`, achievable ΔT, and COP.
4. Writes an **augmented power trace** with negative "cooling" terms co-located with each cooled block.
5. Re-runs 3D-ICE (or the reduced-order thermal network for fast sweeps).
6. **Closes the loop with the Goal-1a leakage rescale** so the lower temperatures actually cash out as static-power savings — otherwise the study systematically undercounts the benefit.

The **cooling-efficiency accounting** (laser COP × LPC efficiency × pump-laser efficiency, vs. the static-power compute savings and any frequency uplift) then sits on top as a post-processor over `s`, COP, and the recomputed leakage. This is exactly the exergy/COP framing already in the MR model — the bridge makes it *spatial and workload-driven* instead of single-heat-flux.

**Fidelity ladder** (each rung is a superset of the last):
- **Rung 0 (analytical, no 3D-ICE):** block power → q → MR COP/ΔT/`s` per block. Fast sweeps of "which blocks to cool, how hard." Pure Python.
- **Rung 1 (chosen):** negative-power injection into 3D-ICE for a true spatial temperature field with realistic lateral spreading.
- **Rung 2 (future):** sustained imposed-temperature BC via a solver/stack modification, for "hold this region at T" studies.

---

## Goal 4 — Floorplanning toolset

### Integration surface (small and clean)

- **Data model** (`utils/floorplan.py`): `Floorplan` = ordered list of named `FloorplanElement` rectangles. Each element stores `name, width, height, minx, miny` (lower-left origin); `area/maxx/maxy` derived. **No layer/z on elements** — vertical structure lives entirely in the `.stk` stack file.
- **Units switch** via `frmt`: `'3D-ICE'` = micrometers, `'hotspot'` = meters; the setter auto-converts (×1e6 / ×1e-6). Set `frmt='3D-ICE'` before writing for simulation.
- **The handoff is one file:** `Floorplan.to_file(path, element_powers=True)` emits a 3D-ICE `_template.flp` with `{powers[<name>]}` placeholders. That file + a `.stk` + a `PowerTrace` is everything `ICETransientSim` needs. Block names must match the power-trace keys (`mcpat_to_flp_name` convention).
- **Thermal mesh is fixed at 50 µm × 50 µm** (stack templates); die dims auto-derived and rounded up to 100 µm multiples in `fill_stk_template` (`ICE.py:256-257`). A floorplanner does **not** set the grid.

### Existing manipulation (reusable)

- Geometry ops: uniform scale (`flp * s`), translate, concat (`+`), replicate (`create_numbered_instance`), mirror/rotate, and `auto_place_element(name, area, where=below|right|left|above)`.
- **Skylake synthesis pipeline** (`examples/floorplans.py` ≈ `thermal/floorplan.py`): builds a core from per-unit **areas** by **recursive slicing** — `replace(flp, unit, subunit_sizes)` deletes a block and re-tiles its rectangle with area-proportional children; `make_processor` tiles cores into a 3×3 grid; `scale_units(configs)` is the **density/size knob** that generated the `RF_2.0`, `fpIWin_10.0`, … sweep variants.
- **One existing geometry↔power coupling:** `power/hotgauge_models.py:26-68` splits DRAM/IMC and IO power **proportionally to block area**. A natural hook for density-aware cooling studies.

### What's net-new for a real floorplanner

- Placement is **slicing/tiling-based** (every block is a strip carved from its parent). **Free-form placement, overlap/DRC legalization, non-rectangular blocks, and a spatial index are all absent.** These are the main net-new components if you want to explore layouts beyond parametric slices of Skylake.

### The goal-4 research question, framed by goals 1 & 3

Once fine-grain laser cooling is on the table, the architecture knobs that *should* change — and that this toolset should let us sweep — are:

- **Density / block sizing** (`scale_units`): cooling relaxes the thermal-density limit, so hot blocks (ALUs, vector units, register files) can shrink or pack tighter.
- **Clock/voltage per region** (needs the Goal-1b T→f model): cooled regions can run at higher `f_max`/lower guardband; this is where "performance impact of cooling" is actually cashed out.
- **Hotspot placement**: with the MR `q`→ΔT relationship, place high-`q` blocks where cooling is most efficient rather than spreading them to avoid hotspots.
- **Cooling budget allocation**: given a total laser/COP budget, which blocks to cool for max performance-per-cooling-watt — a direct optimization over the goal-3 bridge outputs.

The recommended floorplanning tool is therefore a thin layer on the existing `Floorplan` model that (a) adds overlap-checked free placement + legalization, and (b) exposes the density/clock/cooling knobs above as a sweep API feeding the goal-3 bridge and the goal-1 leakage/performance models.

---

## Proposed sequencing (for discussion — no work started)

The dependency structure points to a clear order:

1. **Goal 1a first (leakage↔T feedback).** Smallest change, unblocks everything: without it, every cooling study undercounts the benefit. ~The `mcpat_to_blk_lvl_power_dict.py:241` hook + a leakage model + an outer iteration.
2. **Goal 3 Rung 0-1 (MR bridge + negative-power injection).** Builds directly on #1. Start with the analytical rung, then the negative-power 3D-ICE injection you selected — after the 1-cell negative-power sanity test.
3. **Goal 1b (T→performance model).** Needed to turn cooling into a *performance* number rather than only a power/temperature number. Can proceed in parallel with #2.
4. **Goal 4 (floorplanning + architecture sweeps).** Consumes #1-#3 to answer "what should the architecture become."
5. **Goal 2 (RISC-V) as a parallel track,** de-risked by defining the ISA-neutral block-power interface early.

**Open items to confirm with you** (captured, not assumed):
- Negative-power acceptance in patched 3D-ICE — needs a quick empirical test.
- Leakage `f(T)` model choice (physical BSIM-style vs. simple exponential fit to McPAT re-runs at several temperatures).
- Whether goal-3 studies should run through full 3D-ICE (slow, spatial) or the MR reduced-order network (fast, lumped) for parameter sweeps — likely both, at different rungs.
- Target architecture(s) for goal 4 sweeps (stay on the Skylake floorplan, or introduce a photonic-cooling-native layout).
