#!/usr/bin/env bash
#
# What temperature LIFT would microrefrigeration need on an accelerator?
#
#   scripts/dtmax_batch.sh <slurm_jobid>
#
# Every truncated MR run at 700 W turned out to be dt_max-bound, not iteration-bound: the stage
# lifted the peak exactly 10.00 K -- all it has -- and the target needed 12.6 to 37 K. So on a
# high-power accelerator MR is limited by its DEPTH of cooling, not by the breadth of the plateau
# (which a concentrated kernel collapses to 9 blocks) and not by its COP.
#
# That makes the actionable question the same shape as the COP one: not "is 10 K enough" but "what
# dt_max would it take". This sweeps it. The prediction is sharp and worth stating first: if
# dt_max is genuinely the binding constraint, the achieved peak should track
# (uncooled peak - dt_max) exactly, and the target should become reachable the moment dt_max
# exceeds the required lift -- 12.6 K for the 8-of-128 kernel at 700 W.
#
# If instead the peak stops responding once dt_max is large, something else binds and the dt_max
# story is wrong.
set -uo pipefail

JOBID="${1:?usage: dtmax_batch.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/dtmax"
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

BASE="--mr --mr-target-C 98 --mr-iter 60 --max-iter 60 --cfm 88"

log "=== dt_max sweep starting ==="

# The concentrated kernel that needs 12.6 K. 10 is the shipped device; 13 should just clear it.
for DT in 10 13 15 20 30; do
    run "occ8_700W_dt${DT}" --die-power-W 700 $BASE --dt-max-K $DT \
        --kernel occupancy --n-active 8 --placement contiguous
done
# The uniform 700 W control needs 29.8 K -- far outside any plausible device.
for DT in 10 20 30 40; do
    run "uniform_700W_dt${DT}" --die-power-W 700 $BASE --dt-max-K $DT
done

log "all points queued; waiting"
wait
log "=== dt_max sweep COMPLETE ==="
