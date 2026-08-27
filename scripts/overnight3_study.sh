#!/usr/bin/env bash
#
# Overnight study, third attempt -- everything re-measured with convergence verification.
#
#   scripts/overnight3_study.sh <slurm_jobid>
#   MAX_CONC=8 scripts/overnight3_study.sh <slurm_jobid>     # share the node
#
# Why a third attempt
# -------------------
# `results/overnight/`  (attempt 1) ran at relax=0.5 and is void.
# `results/overnight2/` (attempt 2) fixed the damping but not the CONVERGENCE TEST, which
# measured the change between successive solves and therefore got weaker in proportion to the
# damping. At 1.15 W/mm^2 it declared convergence on iteration 2 at 101.09 C while the residual
# was still 6.5 K, and that trajectory reaches >1000 C by iteration 52. Everything in
# overnight2 at or above ~1.05 W/mm^2 is a truncation, including the 1.30-1.40 W/mm^2 "true
# cliff". See docs/CONVERGENCE.md.
#
# Every point here is solved on the damping-independent fixed-point residual, with backtracking
# damping, and re-solved at half the damping with the peaks required to agree. A point that
# fails prints ** UNCONVERGED ** and is excluded from the summary rather than reported.
#
# What changed in the plan, and why
# ---------------------------------
# The verified cliff on the 34-core die at 88 CFM is between 1.05 and 1.15 W/mm^2, not
# 1.30-1.40, and MR rescues 1.15 but not 1.18. Both interesting regions are therefore MUCH
# narrower and lower than attempt 2 assumed, so the density sweeps are re-centred there instead
# of spending the night confirming runaways at 1.25-1.45 (already done, all divergent).
#
# The open question this is built around: **does a lower MR target push the rescue ceiling out?**
# At a 92 C target MR buys roughly 1.05-1.15 -> 1.15-1.18 in density. Blocks above 92 C carry
# only ~10% of die power while 65% sits 10-20 K below it, so coverage -- not spot size -- is the
# suspected limit. Phase 3 asks it directly at the densities where it now matters.
#
# Points already measured with this exact configuration are SEEDED from results/cliff_verified
# rather than re-run: same code, same arguments, same machine.#
# THE ARRAY, 26 Aug 2026
# ----------------------
# mr_comparison now emits three arms per point of its own accord -- control (30 um of thermal
# grease, no cooling), array_idle (30 um of GaAs pixels in its place, at 0 W) and array_on (the
# same array under the planner) -- and reports the passive and the laser term separately. What
# this script has to supply is the GEOMETRY: $ARM_ARGS pins the stack, the burial depth, the grid
# and, above all, the TILE PITCH.
#
# The pitch is the substantive change. Everything in this file was swept at the driver's 500 um
# default, which is a modelling default chosen to keep the element count tractable on an 826 mm^2
# accelerator die. The first-generation device is 4-16 tiles over ~200 mm^2 -- 3.5 to 7 mm -- so
# these points were an order of magnitude finer than anything anyone is building. At 500 um a tile
# sits inside one floorplan block; at 5 mm one tile spans several, which is where the collateral
# trade lives. Results from before this line are a different device and must not be pooled with
# results from after it.

set -uo pipefail

# The cooling array's stack and pitch, in one place -- see scripts/array_config.sh.
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

JOBID="${1:?usage: overnight3_study.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/overnight3"
SEED="$REPO/results/cliff_verified"
# node-03 has 64 CPUs and a point costs ~2 (one busy 3D-ICE server at ~87% plus a mostly-idle
# Python driver), so ~25 points fit. 8 is a deliberately safe default for sharing the node with
# another sweep; raise it when the node is yours. NB `uptime` on the phonon head node reports
# the HEAD node's load, not the compute node's -- check with
#   srun --jobid=<id> --overlap uptime
MAX_CONC="${MAX_CONC:-8}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
running() { jobs -rp | wc -l; }
throttle() { while [ "$(running)" -ge "$MAX_CONC" ]; do sleep 10; done; }

# seed <tag> <density>  -- reuse an identical, already-verified point
#
# "Identical configuration" was true when the only difference between arms was a number in the
# power trace. It is not true across the cooling-array port: results/cliff_verified predates the
# array, so its points were solved on a different stack, with the cooling subtracted from the
# processor trace, at a tile pitch an order of magnitude finer than the device. Seeding them into
# a post-array run would mix two generations inside one summary table with nothing to tell them
# apart -- the exact failure `placement` was added to stamp against.
#
# So the seed is now CHECKED rather than assumed: the candidate must carry this run's array stack
# in its rows. When it does not, the point is re-run and the reason is logged. This costs
# walltime the first time after a configuration change, which is the correct price.
seed() {
    local tag="$1" d="$2"
    local src="$SEED/d$d/mr_comparison.json"
    if [ -f "$OUT/$tag/mr_comparison.json" ]; then return 0; fi
    [ -f "$src" ] || return 1
    if ! grep -q "\"$ARRAY_STACK\"" "$src"; then
        log "NO SEED $tag: $src predates this configuration (no $ARRAY_STACK in it) -- re-running"
        return 1
    fi
    # Anchored: a bare substring test would let PITCH_UM=500 match "pitch_um": 5000.0.
    if ! grep -qE "\"pitch_um\": ${PITCH_UM}(\.0)?[,[:space:]}]" "$src"; then
        log "NO SEED $tag: $src was solved at a different tile pitch -- re-running"
        return 1
    fi
    mkdir -p "$OUT/$tag"
    cp "$src" "$OUT/$tag/"
    log "SEED $tag from cliff_verified/d$d (configuration verified identical)"
    return 0
}

point() {
    local tag="$1"; shift
    if [ -f "$OUT/$tag/mr_comparison.json" ]; then
        log "SKIP $tag (already complete)"
        return 0
    fi
    throttle
    log "START $tag"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python -u examples/mr_comparison.py $ARM_ARGS $* --out-dir $OUT/$tag \
         > $OUT/$tag.log 2>&1" &
}

log "=== overnight3 starting, max concurrency $MAX_CONC ==="

# ---------------------------------------------------------------------------------------
# Phase 1 -- the convergent regime and the exact cliff position.
# Attempt 2 sampled 0.60-1.15 believing the cliff was at 1.30; it is between 1.05 and 1.15, so
# the resolution goes where the answer is.
# ---------------------------------------------------------------------------------------
for D in $DENSITY_SWEEP; do
    seed "p1_dens_d${D}" "$D" || \
    point "p1_dens_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute
done

# ---------------------------------------------------------------------------------------
# Phase 2 -- where MR stops rescuing. 1.15 rescues (no steady state -> 96.83 C, 4.013 GHz);
# 1.18 does not. This resolves the ceiling to 0.01 W/mm^2.
# ---------------------------------------------------------------------------------------
for D in $DENSITY_CLIFF; do
    seed "p2_ceiling_d${D}" "$D" || \
    point "p2_ceiling_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute
done

# ---------------------------------------------------------------------------------------
# Phase 3 -- THE question: does a lower MR target push that ceiling out?
# A 92 C target only touches blocks above 92 C, which carry ~10% of die power. If coverage is
# the binding constraint, a lower target should rescue densities that 92 C cannot -- and if it
# does not, the limit is the heat budget (h_max / dt_max), which is a different device.
# ---------------------------------------------------------------------------------------
for T in 92 78 65; do
    for D in $DENSITY_WORKING 0.92 0.96; do
        point "p3_target_T${T}_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C "$T" \
              --spot-min-um 10 --spot-policy dilute
    done
done

# ---------------------------------------------------------------------------------------
# Phase 4 -- granularity, in its two distinct senses. They are NOT the same variable and the
# catalogue has historically conflated them.
#
#   --spot-min-um  the legacy BLOCK-LEVEL targeting rule: how narrow a floorplan block the
#                  planner will still aim at. It shapes the plan before any projection happens.
#   --pitch-um     the actual TILE PITCH of the array -- the geometry of the second die. This is
#                  the physical device parameter, and until the array became a real die element
#                  there was no way to sweep it inside a coupled solve at all.
#
# Both are run, and they are labelled apart in the tags so the two families never merge again.
# ---------------------------------------------------------------------------------------
for S in 1 10 100; do
    for POL in dilute exclude; do
        point "p4_spot_s${S}_${POL}" --cores 34 --density $DENSITY_WORKING --cfm 88 --mr-target-C 78 \
              --spot-min-um "$S" --spot-policy "$POL"
    done
done

# The tile-pitch LADDER, coupled. Each rung is its own system matrix -- the tile floorplan is
# part of the geometry the factorisation is built from -- so this is the most expensive family
# per point in the catalogue and it is worth it: the ordering of coarse against fine REVERSES
# with the workload, and that is only visible across the ladder.
#
# ONE workload here, because mr_comparison has no power-shape knob -- its axes are density,
# cores, cooling and target, none of which changes the CONCENTRATION of the map. This arm is
# therefore the CPU plateau case only.
#
# The reversal needs a concentration axis, and the place that has a real one is the accelerator:
# `--kernel occupancy` with `--placement contiguous` against `scattered` is precisely the
# degenerate-plateau against isolated-hotspot contrast. The ladder is run against both in
# scripts/accel_mr_batch.sh; do not read a reversal out of this block alone.
# --pitch-um appears TWICE on these: $ARM_ARGS carries the fixed default and the rung follows
# it. argparse keeps the last, which is the rung -- that is deliberate, not an oversight, and
# scripts/catalogue_rerun.py::matrix_key applies the same last-wins rule so the ladder partitions
# into one matrix group per rung rather than being split by the duplicate.
for P in $PITCH_SWEEP_UM; do
    point "p4_pitch_p${P}" --cores 34 --density $DENSITY_WORKING --cfm 88 --mr-target-C 78 \
          --spot-min-um 10 --spot-policy dilute --pitch-um "$P"
done

# ---------------------------------------------------------------------------------------
# Phase 5 -- does the MR benefit hold as core count scales, and how does airflow move the cliff?
# Densities chosen inside the verified convergent regime so the comparison is between solutions,
# not between two runaways. 128-core is expensive (~670 s factorisation), hence only two points.
# ---------------------------------------------------------------------------------------
for N in 70 128; do
    for D in $DENSITY_SCALING; do
        point "p5_cores${N}_d${D}" --cores "$N" --density "$D" --cfm 88 --mr-target-C 78 \
              --spot-min-um 10 --spot-policy dilute
    done
done
for CFM in 50 133 200; do
    point "p5_cfm${CFM}_d1.10" --cores 34 --density $DENSITY_WORKING_LO --cfm "$CFM" --mr-target-C 78 \
          --spot-min-um 10 --spot-policy dilute
done

log "all points queued; waiting"
wait
log "=== overnight3 COMPLETE ==="

srun --jobid="$JOBID" --overlap bash -lc \
    ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
     python scripts/summarise_overnight3.py > $OUT/SUMMARY.txt 2>&1" || true
log "summary written to $OUT/SUMMARY.txt"
