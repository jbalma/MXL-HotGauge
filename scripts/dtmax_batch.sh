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
#
# THREE ARMS, 26 Aug 2026. The array is a real die element now, so the dt_max prediction has to be
# stated against the right baseline. The prediction is that the achieved peak tracks
# (uncooled peak - dt_max) -- and "uncooled" is `array_idle`, the same GaAs stack with the laser
# off, NOT `control`. Testing it against the grease control would fold the ~14x conductivity step
# from grease to GaAs into the dt_max budget, and the sweep would appear to over-deliver at every
# dt_max: exactly the kind of agreement that is worse than a disagreement, because it looks like
# confirmation.
#
# control and array_idle do not depend on dt_max, so they run ONCE per configuration rather than
# once per dt_max value -- the array is at 0 W in both, and dt_max is a cap on a plan that does
# not exist.
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

# Common to every arm: the operating point and the solver settings. The arms must differ ONLY by
# the 30 um layer and by whether the laser is on.
BASE="--max-iter 60 $ACCEL_COOLING --die-power-W $ACCEL_W_HI"
# What the laser arm adds on top.
LASER="--mr --mr-target-C 98 --mr-iter 60"
OCC8="--kernel occupancy --n-active 8 --placement contiguous"

log "=== dt_max sweep starting ==="
log "    control : $ACCEL_CONTROL_STACK"
log "    array   : $ACCEL_ARRAY_STACK  at ${PITCH_UM} um pitch"

# The two laser-free arms, once per configuration. array_idle is what the dt_max prediction is
# measured against; control says how much of the gap the GaAs slab had already closed before any
# light was applied.
run "occ8_700W_control"       $ACCEL_CONTROL_ARGS $BASE $OCC8
run "occ8_700W_array_idle"    $ACCEL_ARRAY_ARGS   $BASE $OCC8
run "uniform_700W_control"    $ACCEL_CONTROL_ARGS $BASE
run "uniform_700W_array_idle" $ACCEL_ARRAY_ARGS   $BASE

# The concentrated kernel that needs 12.6 K. 10 is the shipped device; 13 should just clear it.
for DT in 10 13 15 20 30; do
    run "occ8_700W_dt${DT}" $ACCEL_ARRAY_ARGS $BASE $LASER --dt-max-K $DT $OCC8
done
# The uniform 700 W control needs 29.8 K -- far outside any plausible device.
for DT in 10 20 30 40; do
    run "uniform_700W_dt${DT}" $ACCEL_ARRAY_ARGS $BASE $LASER --dt-max-K $DT
done

log "all points queued; waiting"
wait
log "=== dt_max sweep COMPLETE ==="
