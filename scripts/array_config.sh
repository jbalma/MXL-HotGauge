# Shared cooling-array configuration for every batch script in this directory.
# Sourced, not executed:   . "$(dirname "$0")/array_config.sh"
#
# Why this file exists
# --------------------
# Eleven batch scripts drive seven planner drivers. Before the array was a real die element the
# scripts needed no stack at all -- they inherited `--stack skylake`, the historical lidded
# template -- and the cooling was subtracted from the processor trace, so the stack barely
# mattered. It matters now: the arms differ by exactly the 30 um layer between the silicon and
# the cold plate, and that layer is part of the STACK. A script that forgets it either gets a
# refusal naming the fix (an array asked for on a stack that cannot carry one) or, worse, quietly
# measures the wrong package.
#
# Repeating the spec strings once per script is how the two bugs found wiring the first driver
# would have been re-introduced five more times, which is why ArrayWiring was factored out in
# HotGauge; the same argument applies here.
#
# THE BASELINE CONFIGURATION, and it is narrow on purpose
# -------------------------------------------------------
# Direct die, copper heatsink on top. The ONLY difference between arms is the 30 um layer:
# thermal grease in the control, GaAs pixels otherwise. No lid, no solder, no copper IHS -- those
# are the struck-out layers in the handbook's stack figure, and anything reintroducing them is
# either the acceptance gate or a mistake. The active layer sits 200 um below the cooled surface
# in every arm. See docs/PHASE0_CHECKLIST.md, "Settled decisions".
#
# Override any of these from the environment:
#     BURIAL_UM=120 scripts/overnight3_study.sh 1389

MR_MATERIAL="${MR_MATERIAL:-GAAS}"
#: Active-layer depth below the cooled surface [um]. IDENTICAL in every arm -- it is a property
#: of the die, not of the cooling, and letting it differ between arms would put the burial-depth
#: effect into the MR delta.
BURIAL_UM="${BURIAL_UM:-200}"
#: 3D-ICE grid cell [um]. The tile grid snaps to it, so tiles adjacent in floating point do not
#: come back overlapping after the solver quantises them.
CELL_UM="${CELL_UM:-50}"

#: The photonic arm: 30 um of GaAs pixels as a second POWERED die above the silicon.
ARRAY_STACK="${ARRAY_STACK:-spec:package=direct_die,mr=${MR_MATERIAL},src=${BURIAL_UM},cell=${CELL_UM}}"
#: The control arm: the same stack with 30 um of thermal grease in the array's place. Everything
#: else -- die thickness, burial depth, cold plate, ambient -- is identical.
CONTROL_STACK="${CONTROL_STACK:-spec:package=direct_die,mr=none,src=${BURIAL_UM},cell=${CELL_UM}}"

#: THE TILE-PITCH LADDER -- the swept variable, and the reason not to collapse it.
#:
#: Cooling granularity is one of the things this project exists to MEASURE, not to fix. The
#: pitch sweep already found two results that a single pitch destroys:
#:
#:  * **the ordering REVERSES with the workload.** A coarse array wins on a degenerate peak,
#:    because one tile clips several plateau members together and per-block cooling cannot do
#:    that at any price; a fine array wins on an isolated hotspot, because a coarse tile spends
#:    its watts on silicon that was already cool. Which dominates is a property of the power map.
#:  * **a coarse array is low-variance and a fine one is not** -- the fine end swings 3.6x across
#:    workloads on identical hardware. That is a manufacturing and a control-loop argument, and
#:    it only exists as a comparison across the ladder.
#:
#: Fixing the pitch at one value throws both away and reports a point estimate of a curve.
PITCH_SWEEP_UM="${PITCH_SWEEP_UM:-50 100 200 500 1000 2000}"

#: Pitch for studies that hold granularity FIXED while sweeping something else (density, target,
#: cooling class, core count). 500 um, which is what the back catalogue used -- so the arm deltas
#: stay comparable to prior work.
#:
#: Absolute temperatures already are not comparable, because --spreading corrected the boundary
#: (see below and docs/evidence/spreading_boundary_by_die.json). Moving the pitch as well would
#: break the deltas too and leave nothing that could be compared with anything.
PITCH_UM="${PITCH_UM:-500}"

#: The first-generation device is 4-16 tiles on a ~200 mm^2 die. That is an ANNOTATION on the
#: ladder, not an operating point, and the distinction matters: it is a tile COUNT, and turning
#: a count into an absolute pitch and applying it to a different die is how 5 mm ended up here,
#: which is ONE tile on the 7-core die and TWO on the 34-core -- and 38 of the 44 --cores
#: invocations in this directory are 34-core.
#:
#: Where the device lands on each die (mr_array.device_pitch_range_um):
#:
#:     die          area mm^2   4-16 tiles
#:     7-core              53   1.8-3.7 mm
#:     34-core            101   2.5-5.0 mm
#:     70-core            196   3.5-7.0 mm
#:     128-core           348   4.7-9.3 mm
#:     GA100              826   7.2-14.4 mm
#:
#: On the 34-core die -- the catalogue's workhorse -- 4-16 tiles is 2.5-5.0 mm, i.e. COARSER than
#: the ladder's 2000 um top. So the first-generation device sits just beyond the coarse end of
#: the studied range. That is a useful thing to tell a device roadmap, and it is not a reason to
#: run the catalogue there.
DEVICE_TILES="${DEVICE_TILES:-4-16}"

# ---------------------------------------------------------------------------------------------
# POWER-DENSITY GRIDS -- re-centred on the MEASURED cliff, 26 Aug 2026
# ---------------------------------------------------------------------------------------------
# The old grids were chosen for the old boundary. --spreading moved the 34-core boundary from
# 0.0764 to 0.3247 K/W and the cliff with it, from 1.05-1.15 down to **0.80-1.00 W/mm^2**
# (measured: docs/evidence/cliff_after_spreading.json). Re-running the old grids unchanged puts
# almost every point past the cliff and returns RUNAWAY for nearly all of them -- which is the
# failure overnight_study.sh's own header records from a previous attempt, in those words.
#
# A sweep is only informative where the die has a steady state to lose, so these straddle the
# measured cliff instead of sitting beyond it.

#: The main 34-core density sweep [W/mm^2]. Spans the convergent regime and walks up to the
#: cliff, with the resolution concentrated where the answer changes.
DENSITY_SWEEP="${DENSITY_SWEEP:-0.30 0.45 0.60 0.70 0.80 0.85 0.90}"

#: Brackets the cliff itself, to resolve where MR stops rescuing.
DENSITY_CLIFF="${DENSITY_CLIFF:-0.88 0.92 0.96 1.00}"

#: The single "MR is genuinely working" operating point: hot enough that the planner has
#: something to do, cool enough that the die still has a steady state to protect. Was 1.15.
DENSITY_WORKING="${DENSITY_WORKING:-0.85}"

#: A second working point one step below, for anything that wants two. Was 1.10.
DENSITY_WORKING_LO="${DENSITY_WORKING_LO:-0.80}"

#: For the 70- and 128-core dies, which are larger and reach the same die power at lower
#: density. Was 0.80/1.00.
DENSITY_SCALING="${DENSITY_SCALING:-0.50 0.70}"

#: Stacked-memory and tier-screen working point. Was 1.00; those runs are on the same die and
#: the same cooling, so they move with it.
DENSITY_STACKED="${DENSITY_STACKED:-0.60}"

#: GA100 accelerator cooling: a direct-die MICROCHANNEL cold plate.
#:
#: This is the fix for the accelerator's universal runaway, and the cause was the cold-plate
#: MODEL, not the die. CoolingSpec's water path builds a finned base sized for the die -- a water
#: block -- and returns 0.055 K/W, on which the GA100 has no steady state above ~250 W. A real
#: direct-die microchannel plate, anchored on a measured reference (1020 W/cm^2 at <69 C and
#: <120 kPa; sink_models.MICROCHANNEL_REF), gives 0.0153 K/W at 700 W. Measured through the full
#: coupled solve: 400 W -> 51.4 C, 700 W -> 64.0 C, both converged.
#:
#: So the real operating points are back: the accelerator runs at the powers an H100 runs at.
ACCEL_COOLING="${ACCEL_COOLING:---microchannel --dt-fluid-K 10 --inlet-C 30 --ambient-K 303.15}"

#: GA100 die power [W]. The catalogue's real operating points, restored.
ACCEL_POWER_W="${ACCEL_POWER_W:-200 400 550 700}"
ACCEL_W_LO="${ACCEL_W_LO:-400}"   # the study's standard point
ACCEL_W_HI="${ACCEL_W_HI:-700}"   # H100 class

#: The cold-plate base: in the BOUNDARY with its real overhang, not a slab in the stack.
#:
#: 3D-ICE gives every layer exactly the die footprint, so a 2 mm plate declared as a stack layer
#: is a column of metal the width of the die and the whole package budget comes out proportional
#: to 1/area -- 15.5x across the die sizes this project models, against 2.6x with the overhang
#: (docs/evidence/direct_die_overhang.json). Every driver that takes --stack now takes
#: --spreading, which amends the spec with sink_in_stack=0 and wraps the sink in a SpreadingSink.
#:
#: ON BY DEFAULT, because it is the physics. Set SPREADING= (empty) to reproduce the pre-P0.4
#: sink model, which is the only reason to.
#:
#: **This moves absolute temperatures, a lot, and small dies most.** At 88 CFM the boundary the
#: die sees goes from a flat 0.0764 K/W on every die to 0.553 (7-core), 0.325 (34-core), 0.108
#: (GA100) -- see docs/evidence/spreading_boundary_by_die.json. Measured end to end, the 7-core
#: control arm at 1.0 W/mm^2 moved 74.4 -> 95.7 C. That is the correction working: BaffledFinSink
#: presents the SimScale CONVECTIVE resistance only, because 3D-ICE resolves spreading in the
#: die -- but the die is 240 um of silicon and cannot spread a 28 mm^2 source out to a cold
#: plate. That path lived in the base, which the slab model rendered as a die-width column, so it
#: was simply absent. Results from before this line are not comparable on absolute temperature,
#: only on the arm deltas.
SPREADING="${SPREADING-yes}"
SPREAD_ARGS=""
if [ -n "$SPREADING" ]; then SPREAD_ARGS="--spreading"; fi

# ---------------------------------------------------------------------------------------------
# Ready-made argument groups. Which one a driver takes depends on whether it builds its own
# per-arm stacks or is handed one.
# ---------------------------------------------------------------------------------------------

#: For drivers that emit all three arms THEMSELVES and build a stack per arm:
#: examples/mr_comparison.py, examples/clock_headroom.py. They take --stack auto.
ARM_ARGS="--stack auto --pitch-um ${PITCH_UM} --burial-um ${BURIAL_UM} --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS}"

#: For drivers handed ONE stack, which is therefore ONE arm per invocation:
#: accelerator_study, mr_clipping_study, cop_breakeven, hybrid_cooling_optimizer, mr_plan_probe.
#: A three-arm comparison from these is three invocations -- see the run3 helper in
#: accel_mr_batch.sh.
ARRAY_ARGS="--stack ${ARRAY_STACK} --pitch-um ${PITCH_UM} --cell-um ${CELL_UM} ${SPREAD_ARGS}"
CONTROL_ARGS="--stack ${CONTROL_STACK} --cell-um ${CELL_UM} ${SPREAD_ARGS}"

#: For a driver that takes --stack but has no --cell-um (examples/thermal_tiers.py). The grid
#: still comes from the spec's cell= term; there is simply no second place to state it.
CONTROL_STACK_ONLY="--stack ${CONTROL_STACK} ${SPREAD_ARGS}"

#: The accelerator runs on a COARSER grid and must not be given the 50 um one. The GA100
#: floorplan is 826 mm^2 -- eight times the CPU die -- which at 50 um cells is ~330k cells per
#: layer before the array adds a second one, and that is where SuperLU 4.3 gave up on the deep
#: stacks. accelerator_study.py defaults --cell-um to 100 for exactly this reason, and
#: coarsen_stack_grid rewrites the rendered .stk to match; the spec is built at 100 too so the
#: stack is self-consistent BEFORE that rewrite and the generated filename says what it is.
#:
#: The cost is real and belongs next to the number: a coarser grid smooths lateral gradients, so
#: peaks on small blocks are understated and a 100 um run's peak must not be compared against a
#: 50 um run's. Degeneracy questions -- plateau width, what clipping the top block buys -- are
#: far less sensitive.
ACCEL_CELL_UM="${ACCEL_CELL_UM:-100}"
ACCEL_ARRAY_STACK="${ACCEL_ARRAY_STACK:-spec:package=direct_die,mr=${MR_MATERIAL},src=${BURIAL_UM},cell=${ACCEL_CELL_UM}}"
ACCEL_CONTROL_STACK="${ACCEL_CONTROL_STACK:-spec:package=direct_die,mr=none,src=${BURIAL_UM},cell=${ACCEL_CELL_UM}}"
ACCEL_ARRAY_ARGS="--stack ${ACCEL_ARRAY_STACK} --pitch-um ${PITCH_UM} --cell-um ${ACCEL_CELL_UM} ${SPREAD_ARGS}"
ACCEL_CONTROL_ARGS="--stack ${ACCEL_CONTROL_STACK} --cell-um ${ACCEL_CELL_UM} ${SPREAD_ARGS}"

#: The historical lidded template. Still needed by examples/stacked_memory_study.py, whose
#: splicer (stack_models.render_stacked_memory_template) keys on a literal
#: '/****** Heat Sink ******/' comment banner that only the hand-written skylake.stk carries; a
#: generated direct-die stack raises "no Heat Sink section to insert the bond material into".
#: Porting the memory stack to the array is its own job -- it needs a THREE-die stack (logic +
#: memory + array) and the splicer rewritten against StackSpec. Passed explicitly wherever it is
#: used so a reader can tell "deliberate" from "forgotten", which is the distinction every other
#: guard in this project exists to preserve.
LEGACY_STACK="${LEGACY_STACK:-skylake}"
