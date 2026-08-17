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
set -uo pipefail

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

log "=== accelerator batch starting, max concurrency $MAX_CONC ==="

# Baseline restated in the batch so the whole set lives in one place.
run a400_air        --die-power-W 400 --cfm 88  --max-iter 60 --split-sensitivity hbm_phy
# Does the intra-tile split matter, or was the plateau guaranteed by block size?
run a400_air_nosplit --die-power-W 400 --cfm 88 --max-iter 60 --no-split-sm
# Leakage basis bracket.
run a400_air_leakarea --die-power-W 400 --cfm 88 --max-iter 60 --leak-by-area
run a400_air_leak40  --die-power-W 400 --cfm 88 --max-iter 60 --leak-fraction 0.40
# Total power: H100 class, and then matched to the CPU die's density where the cliff lives.
run a700_air        --die-power-W 700 --cfm 88  --max-iter 80
run a700_liquid     --die-power-W 700 --r-th 0.05 --max-iter 80
run d100_liquid     --density 1.00 --r-th 0.05  --max-iter 80
run d115_liquid     --density 1.15 --r-th 0.05  --max-iter 80
# Finer grid: the 100 um default understates peaks on small blocks, so check the plateau is not
# an artefact of coarsening. May exceed SuperLU capacity -- if it dies, that is the answer.
run a400_air_c50    --die-power-W 400 --cfm 88  --max-iter 60 --cell-um 50

log "all points queued; waiting"
wait
log "=== accelerator batch COMPLETE ==="
