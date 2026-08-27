#!/usr/bin/env bash
#
# Accelerator floorplan confirmation set.
#
#   scripts/accel_batch.sh <slurm_jobid>
#
# The 400 W / 88 CFM point already showed a 332-block plateau and a 0.040 K clip-one gain. These
# ask whether that survives the things it could plausibly be an artefact of:
#
#   * the intra-tile split -- without it the finest structure is 3.4 mm^2, so a plateau is
#     guaranteed by construction. With it there IS finer structure and the plateau still holds,
#     which is the version worth quoting. no_split is the control that shows the split matters.
#   * the leakage basis -- by power concentrates leakage in the datapath, by area moves it to the
#     SRAM. These bracket it.
#   * total power -- 400 W is 0.48 W/mm^2, HALF the CPU density where the cliff lives. An
#     accelerator's problem is total power, not density, so these push to 700 W (H100 class) and
#     to matched CPU density, where the die may have no steady state at all.
#   * cooling class -- liquid, since a 700 W part would not be on air.
#   * the assumed power split -- the sensitivity is analytic, but hbm_phy at 0.5x moves the peak
#     off the PHY and onto compute, and whether the plateau changes when the peak MOVES is a
#     thermal question, not an arithmetic one.
#
# Stack, 26 Aug 2026: every point here runs on the CONTROL arm -- direct die, 30 um of thermal
# grease, no cooling array. These questions are about the die's own power map (does the intra-tile
# split matter, does the leakage basis move the peak, does the plateau survive at 700 W), not
# about the cooling layer, so one arm is the right shape. It is the control rather than the
# historical `skylake` lidded template because the lid is not in the baseline configuration and a
# peak measured through 3 mm of copper IHS is not comparable with anything else in this batch.
# The MR arms for the same die live in accel_mr_batch.sh, which emits all three itself.
set -uo pipefail

# The cooling array's stack and pitch, in one place -- see scripts/array_config.sh.
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

# ACCELERATOR POWER, re-centred 26 Aug 2026. The GA100 direct-die has no steady state
# above ~250 W on a water cold plate at 30 C inlet -- measured, see
# docs/evidence/accelerator_water_envelope.json. The 400 W and 700 W points this file
# used are from the air-cooled, constant-power era and are now entirely past the cliff;
# 200 W keeps the "comfortably convergent" role and 280 W the "just past comfortable,
# MR has something to do" one. See also accelerator_runaway_cause.json: the old
# convergent numbers were constant-power solves and their temperatures are withdrawn.

JOBID="${1:?usage: accel_batch.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/accel"
MAX_CONC="${MAX_CONC:-4}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
throttle() { while [ "$(jobs -rp | wc -l)" -ge "$MAX_CONC" ]; do sleep 10; done; }

run() {
    local tag="$1"; shift
    if [ -f "$OUT/$tag/done" ]; then log "SKIP $tag"; return 0; fi
    throttle
    log "START $tag"
    mkdir -p "$OUT/$tag"
    local qargs
    printf -v qargs '%q ' "$@"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python -u examples/accelerator_study.py $qargs --out-dir $OUT/$tag > $OUT/$tag.log 2>&1 && \
         touch $OUT/$tag/done" &
}

# The control arm, on every point. --cell-um comes from here too, so the stack's grid and the
# floorplan's agree before coarsen_stack_grid rewrites it.
BASE="$ACCEL_CONTROL_ARGS $ACCEL_COOLING"

log "=== accelerator batch starting, max concurrency $MAX_CONC ==="
log "    stack: $ACCEL_CONTROL_STACK  (control arm -- grease, no array)"

# Baseline restated in the batch so the whole set lives in one place.
run a400_air        $BASE --die-power-W $ACCEL_W_LO $ACCEL_COOLING  --max-iter 60 --split-sensitivity hbm_phy
# Does the intra-tile split matter, or was the plateau guaranteed by block size?
run a400_air_nosplit $BASE --die-power-W $ACCEL_W_LO $ACCEL_COOLING --max-iter 60 --no-split-sm
# Leakage basis bracket.
run a400_air_leakarea $BASE --die-power-W $ACCEL_W_LO $ACCEL_COOLING --max-iter 60 --leak-by-area
run a400_air_leak40  $BASE --die-power-W $ACCEL_W_LO $ACCEL_COOLING --max-iter 60 --leak-fraction 0.40
# Total power: H100 class, and then matched to the CPU die's density where the cliff lives.
run a700_air        $BASE --die-power-W $ACCEL_W_HI $ACCEL_COOLING  --max-iter 80
run a700_liquid     $BASE --die-power-W $ACCEL_W_HI $ACCEL_COOLING --max-iter 80
run d060           $BASE --density 0.60 --max-iter 80
run d085           $BASE --density 0.85 --max-iter 80
# Finer grid: the 100 um default understates peaks on small blocks, so check the plateau is not
# an artefact of coarsening. May exceed SuperLU capacity -- if it dies, that is the answer.
# $CONTROL_ARGS rather than $BASE: this point is ABOUT the grid, so it takes the 50 um stack
# outright instead of a 100 um one that coarsen_stack_grid then rewrites -- otherwise the
# generated .stk is named cell100 while the run is at 50, and the session cache keys on the
# matrix, not the filename, so nothing would catch it.
run a400_air_c50    $CONTROL_ARGS --die-power-W $ACCEL_W_LO $ACCEL_COOLING  --max-iter 60

log "all points queued; waiting"
wait
log "=== accelerator batch COMPLETE ==="
