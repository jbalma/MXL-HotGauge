#!/usr/bin/env bash
#
# Item 1: can a realistic kernel produce a genuine accelerator hotspot?
#
#   scripts/kernel_batch.sh <slurm_jobid>
#
# The uniform study gave every block in a class the same power ON PURPOSE, so that any hotspot came
# from geometry rather than from an imbalance assumed into the input. That is the right control and
# it is also the LEAST favourable input for microrefrigeration. This is the other end: the three
# kernel shapes most likely to break the 332-block plateau, given the best shot available.
#
# Pre-registered prediction, so it cannot be reinterpreted afterwards:
#
#   * occupancy/contiguous at low n_active SHOULD produce a hotspot. It is the accelerator's
#     analogue of single-core turbo, which on the CPU die took the plateau from 15 blocks to 2 and
#     the clip-one gain from 1.25 K to 9.86 K. If anything reopens the case, this is it.
#   * occupancy/scattered should NOT, because each active tile is surrounded by idle silicon.
#     The contiguous-minus-scattered difference isolates placement from occupancy.
#   * memory_bound is the dark horse: the interface classes are already the hottest and sit on the
#     perimeter, so this concentrates power into the top of the distribution.
#   * tensor is pure intra-tile redistribution at constant die power -- the cleanest test of
#     whether the split tiles resolve anything a uniform tile would hide.
#
# The catch that has to be reported either way: idling SMs LOWERS die power, moving the part away
# from the runaway regime where MR's rescue value lives. A kernel that creates a hotspot and
# removes the instability has given MR a target and taken away its reason.
set -uo pipefail

JOBID="${1:?usage: kernel_batch.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/kernel"
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

BASE="--die-power-W 400 --cfm 88 --max-iter 60"

log "=== kernel batch starting, max concurrency $MAX_CONC ==="

# --- the occupancy ladder, contiguous: the best shot MR gets ---------------------------
for N in 64 32 16 8 4 2 1; do
    run "occ_c${N}" $BASE --kernel occupancy --n-active $N --placement contiguous
done

# --- placement isolated at the two most concentrated points ----------------------------
for N in 8 2; do
    run "occ_s${N}" $BASE --kernel occupancy --n-active $N --placement scattered
done
run "occ_cluster32" $BASE --kernel occupancy --n-active 32 --placement cluster

# --- the other two kernel shapes -------------------------------------------------------
run "memory_bound" $BASE --kernel memory_bound
run "tensor"       $BASE --kernel tensor

# --- the load-bearing assumption, swept at the most concentrated point -----------------
# DEFAULT_BOOST_POWER_RATIO is 1.9 and it caps how concentrated the die may become, so the
# occupancy conclusion has to survive 1.3 and 2.5 to mean anything.
run "occ_c8_boost1.3" $BASE --kernel occupancy --n-active 8 --placement contiguous --boost-power-ratio 1.3
run "occ_c8_boost2.5" $BASE --kernel occupancy --n-active 8 --placement contiguous --boost-power-ratio 2.5
# Idle power is the other assumption: 0 would make any partial-occupancy die look maximally
# concentrated, so the zero case bounds how much of the result is that choice.
run "occ_c8_idle0"    $BASE --kernel occupancy --n-active 8 --placement contiguous --idle-fraction 0.0

# --- combined worst case: concentrated kernel on a high-power part ---------------------
run "occ_c8_700W" --die-power-W 700 --cfm 88 --max-iter 80 --kernel occupancy --n-active 8 --placement contiguous

log "all points queued; waiting"
wait
log "=== kernel batch COMPLETE ==="
