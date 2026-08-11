# Project status & next steps

*Last updated: 2026-08-11. Maintained as the handoff document between Claude sessions and
collaborators. Update it when a milestone lands.*

## Mission

Extend HotGauge to answer: **what do chip architectures gain from integrated photonic
(laser) microrefrigeration?** Four goals (from the original project_goals):

1. **Power/perf/temperature coupling** — model temperature-dependent static power and the
   power↔temperature feedback the stock pipeline lacks. **[Goal 1a DONE — see below]**
2. **ISA support** — understand x86 lock-in; path to RISC-V. *(Parallel track; the 2026
   snipersim fork in-tree already has `riscv/`, `README.riscv`, `riscv.cfg` — lock-in is now
   a configuration problem, not a missing capability.)*
3. **Microrefrigeration coupling** — feed the reduced-order MR model's per-block cooling
   into HotGauge as **negative power sources** per functional unit (decided approach) and
   evaluate performance/power impact + cooling efficiency (laser COP × LPC × pump).
4. **Floorplanning toolset** — architecture sweeps (density, clocks, layout) under
   fine-grain cooling.

Deep analysis of all four: `docs/HotGauge_gap_analysis_and_extension_design.md`.

## Where we are right now (in-flight)

Sniper build just completed on phonon. The **immediate next actions** are the first real
end-to-end pipeline run to produce **real per-unit leakage splits** (replacing the synthetic
leakage used so far):

```bash
# Step 2 — Sniper run on the shipped linpack (from repo root; ~minutes)
./snipersim/run-sniper -n 8 -c $(pwd)/examples/skylake_14nm.cfg -s energystats:200000 \
  --sde-arch=tgl -s stop-by-icount:100000000 \
  -d $(pwd)/mcpat_runs/14nm/linpack_3.8GHz -- $(pwd)/examples/linpack

# Step 3 — McPAT conversion (block_powers_split_*.json emitted automatically)
cd scripts && ./14_perf_sims_to_7_10_14_power_sims.sh $(pwd)/../mcpat_runs 8 8 && cd ..
ls mcpat_runs/7nm/linpack_3.8GHz/ | grep split | head -3

# Step 4 — leakage-feedback smoke test on REAL leakage
OMP_NUM_THREADS=1 python examples/leakage_feedback_smoketest.py \
  --stack skylake_HS483 --plugin-args 6000 --trace-dir mcpat_runs/7nm/linpack_3.8GHz
```

Success criteria: Step 4 prints `using REAL leakage split from N file(s)` and converges.
Known possible snags: linpack may want stdin/problem-size input (feed it or switch
workloads); `run_mcpat.py` expects the McPAT binary at `../McPAT/mcpat` relative to
`scripts/`; the shipped example trace CANNOT be regenerated (its upstream McPAT files never
shipped) — real splits require this pipeline run.

## Goal 1a — done and validated

**The gap:** stock HotGauge computes leakage once (McPAT, at the XML's fixed reference
temperature — 330/360 K per core), sums it with dynamic power, and freezes it. No
temperature feedback, no thermal runaway, cooling's static-power savings invisible. The
authors left the hook as a TODO at `scripts/mcpat_to_blk_lvl_power_dict.py` (~line 241).

**What was built** (all tests: 27 passing):
- `HotGauge/power/leakage.py`: `LeakageModel` (exponential doubling-per-ΔT default;
  `subthreshold` physical form; `from_table` for McPAT-calibrated data),
  `rescale_total_power` / `rescale_trace`, and `converge_power_temperature` — fixed-point
  loop with under-relaxation (`relax`, default 0.5), power-growth guard (10× baseline),
  per-block max-temp guard (1000 K, names the offending block), temp floor (200 K; 3D-ICE
  reports 0 K for blocks outside the die layer), solver-failure→`diverged`, per-iteration
  `history`.
- `HotGauge/thermal/leakage_feedback.py`: `ICEThermalSolver` (one 3D-ICE transient per
  call, fresh `iter_NNN/` dirs, reads per-block Tflp temps in kelvin),
  `mcpat_flp_name_map` (McPAT↔floorplan names; aggregates → `None` → left frozen),
  `load_leakage_ref`/`find_split_files`, `run_leakage_feedback` entry point.

**Validated results on real 3D-ICE (phonon):**
- `skylake.stk`, synthetic 10% leakage: **CONVERGED in 3 iters, −2.66 % total power**
  (816.9 → 795.2 W) — blocks run below T_ref=360 K so temperature-aware leakage is lower
  than the frozen baseline. This is the static-power correction the stock pipeline cannot
  produce.
- Synthetic 20% leakage (both stacks): genuine electro-thermal **runaway at RBB_0**
  (hottest block, 105.5 °C = 18.5 K above T_ref → 2.3× leakage from iter 0; increments grow
  geometrically). Correctly detected and attributed by the guards/inspector. Under-relaxation
  cannot stabilize supercritical gain — reduce the gain (leak fraction, doubling, T_ref) or
  cool better.
- **Methodological finding that shapes Goal 3:** the smoke test's ~2–4 ms transients never
  thermally reach the heatsink (diffusion depth ~0.6 mm < die+TIM+spreader), so convection
  vs. HS483-FMU stacks gave *identical* die temperatures. **Cooling studies require
  steady-state solves (`ICESteadySim`) or long/warmed transients** (repo's production flow
  uses 5-minute warmups at 3 s slots — `HotGauge/thermal/thermal.py`).

## Roadmap (after the real-split run)

1. **Steady-state solver mode** in `ICEThermalSolver` (wrap `ICESteadySim`) — needed for any
   cooling-technology comparison, and much cheaper per feedback iteration.
2. **Leakage calibration**: re-run McPAT at 2–3 XML temperatures → `LeakageModel.from_table`.
3. **Goal 3 — MR bridge**: per-block power density q → MR model (`chip_microrefrigeration_
   stable_v1.ipynb`, reduced-order, per-heat-flux) → required cooling power s, ΔT, COP →
   inject as negative power in the `.flp` (validate 3D-ICE accepts negative sources with a
   1-cell test first) → rerun feedback loop so static-power savings are counted → efficiency
   post-processor (laser COP × LPC × pump vs. compute savings).
4. **Goal 1b — T→performance model** (f_max(T)/guardband; V-F table is in
   `HotGauge/configuration/performance.py`) so cooling converts to performance numbers.
5. **Goal 4 — floorplanning**: overlap-checked placement + legalization on top of the
   existing slicing ops (`examples/floorplans.py` `replace`/`scale_units`); sweep density /
   clocks / cooling-budget allocation.
6. **Goal 2 — RISC-V**: scope against the in-tree snipersim RISC-V support; the McPAT-side
   x86 taxonomy (see gap analysis §2) is the remaining blocker.

## Facts a new session will otherwise rediscover the hard way

- Floorplan is **7-core** (`skylake7nm_7core_3`) but traces are **8-core** → Core-7 units
  have no floorplan block; name-bridge coverage 80 % is *expected*; those units stay frozen.
- McPAT reference temps in the XML template are **per-core (330 K or 360 K)** — pass the
  right `T_ref`; a wrong T_ref flips the sign of the leakage correction.
- Feedback iteration outputs live under `leakage_feedback_smoketest/<stack>/stage2/iter_*/`;
  diagnose with `python examples/inspect_feedback_iters.py <stage2 dir>` (classifies
  gradual-ratchet vs. solver-spike from the increment series).
- The smoke test auto-prefers real `block_powers_split_*.json` in `--trace-dir`; otherwise
  it synthesizes leakage (`--leak-fraction`) and says so.
- `load_block_powers` filters out `block_powers_split_*` companions — keep it that way.
- Pluggable stacks (`skylake_HS483`, `skylake_kryos`) need `--plugin-args` (e.g. `6000` fan
  rpm); plain `skylake` stack needs none and no FMU.
