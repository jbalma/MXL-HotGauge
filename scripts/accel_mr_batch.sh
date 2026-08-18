#!/usr/bin/env bash
#
# What an MR rescue COSTS on the accelerator, now that a kernel has been found that needs one.
#
#   scripts/accel_mr_batch.sh <slurm_jobid>
#
# The occupancy ladder reopened the case. Clip-one gain was the wrong metric: it stays small
# because the active tiles are mutually degenerate, but the PLATEAU collapses from 332 blocks to 9,
# and clipping a 9-block plateau is cheap. At 8 of 128 SMs active on a 700 W part the die sits at
# 110.6 C -- over its limit -- and ten blocks realise the full 10 K of device capability, against
# 332 blocks for 1.43 K on the uniform die.
#
# So the question is no longer "is there a hotspot" but "what does clipping it cost", which needs
# the actual MR loop rather than the tier proxy. The uniform points at matched power are the
# controls: same die, same watts, only the kernel differs.
set -uo pipefail

JOBID="${1:?usage: accel_mr_batch.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/accel_mr"
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

MR="--mr --mr-target-C 98 --mr-iter 15 --max-iter 60"

log "=== accelerator MR batch starting ==="

# The point that reopened the case: hot AND concentrated.
run "mr_occ8_700W"  --die-power-W 700 --cfm 88 $MR --kernel occupancy --n-active 8 --placement contiguous
# Controls at matched power: same die, same watts, kernel is the ONLY difference.
run "mr_uniform_700W" --die-power-W 700 --cfm 88 $MR
run "mr_occ64_400W" --die-power-W 400 --cfm 88 $MR --kernel occupancy --n-active 64 --placement contiguous
run "mr_uniform_400W" --die-power-W 400 --cfm 88 $MR
# Placement, at the point that matters -- scattered should cost MORE, since it spreads the
# plateau back out across the die.
run "mr_occ8_700W_scat" --die-power-W 700 --cfm 88 $MR --kernel occupancy --n-active 8 --placement scattered
# Occupancy sweep at 700 W: where does the rescue stop being cheap?
for N in 16 32 64; do
    run "mr_occ${N}_700W" --die-power-W 700 --cfm 88 $MR --kernel occupancy --n-active $N --placement contiguous
done

log "all points queued; waiting"
wait
log "=== accelerator MR batch COMPLETE ==="
