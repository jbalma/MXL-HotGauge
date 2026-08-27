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
#
# THREE ARMS, 26 Aug 2026
# -----------------------
# Every point is now run three times, because the cooling array is a real die element and the
# two-arm form of this study cannot say what it appears to say:
#
#   control      30 um of thermal grease above the die, no cooling.
#   array_idle   the same stack with 30 um of GaAs pixels in the grease's place, at 0 W.
#   array_on     the same array under the planner.
#
# The GaAs slab conducts roughly 14x better than the grease it replaces, so `control -> array_on`
# is a packaging change AND a laser, added together. On the first three-arm CPU runs the unpowered
# array alone rescued a die that had no steady state under grease, and the laser then added 4.9 K
# on top -- reported as one number, all of it would have been booked to the light. That matters
# most HERE, because this script exists to answer "what does the rescue cost": the cost of the
# laser is charged against `array_idle`, not against `control`.
#
# accelerator_study.py takes one stack per invocation, so three arms is three invocations -- see
# run3 below. The die-power / kernel / placement axes are unchanged.
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

# Solver settings, shared by all three arms -- the arms must differ ONLY by the 30 um layer and
# by whether the laser is on, so anything affecting convergence has to be common.
SOLVE="--max-iter 60"
# What the laser arm adds on top.
LASER="--mr --mr-target-C 98 --mr-iter 60"

# run3 <tag> <point args...>  -- one operating point, three arms.
#
# Each arm is a separate accelerator_study invocation with its own out-dir, so a failed arm does
# not take the other two with it and the summariser can tell them apart by directory name. The
# point arguments are byte-identical across the three; only the stack and the laser differ.
run3() {
    local tag="$1"; shift
    run "${tag}_control"    $ACCEL_CONTROL_ARGS $SOLVE "$@"
    run "${tag}_array_idle" $ACCEL_ARRAY_ARGS   $SOLVE "$@"
    run "${tag}_array_on"   $ACCEL_ARRAY_ARGS   $SOLVE $LASER "$@"
}

log "=== accelerator MR batch starting ==="
log "    control : $ACCEL_CONTROL_STACK"
log "    array   : $ACCEL_ARRAY_STACK  at ${PITCH_UM} um pitch"

# The point that reopened the case: hot AND concentrated.
run3 "mr_occ8_700W"  --die-power-W $ACCEL_W_HI $ACCEL_COOLING --kernel occupancy --n-active 8 --placement contiguous
# Controls at matched power: same die, same watts, kernel is the ONLY difference.
run3 "mr_uniform_700W" --die-power-W $ACCEL_W_HI $ACCEL_COOLING
run3 "mr_occ64_400W" --die-power-W $ACCEL_W_LO $ACCEL_COOLING --kernel occupancy --n-active 64 --placement contiguous
run3 "mr_uniform_400W" --die-power-W $ACCEL_W_LO $ACCEL_COOLING
# Placement, at the point that matters -- scattered should cost MORE, since it spreads the
# plateau back out across the die.
run3 "mr_occ8_700W_scat" --die-power-W $ACCEL_W_HI $ACCEL_COOLING --kernel occupancy --n-active 8 --placement scattered
# Occupancy sweep at 700 W: where does the rescue stop being cheap?
for N in 16 32 64; do
    run3 "mr_occ${N}_700W" --die-power-W $ACCEL_W_HI $ACCEL_COOLING --kernel occupancy --n-active $N --placement contiguous
done

# ---------------------------------------------------------------------------------------
# THE TILE-PITCH LADDER, against the two power shapes -- and this is where the reversal lives.
#
# Granularity is a swept variable, and its headline result is that the ordering of coarse
# against fine REVERSES with the workload. Showing that needs a concentration axis, and the
# accelerator is the only driver in this directory that has a real one:
#
#   contiguous  the 8 active SMs pile their heat together -> a DEGENERATE PLATEAU. A coarse tile
#               clips several members at once, which per-block cooling cannot do at any price,
#               so coarse should do well here.
#   scattered   each active SM is surrounded by idle silicon -> ISOLATED HOTSPOTS. A coarse tile
#               spends most of its watts on silicon that was already cool, so fine should win.
#
# If the ordering does NOT reverse between these two columns, the reversal result does not
# generalise off the CPU die and should be restated as a CPU-specific finding.
#
# Only the laser arm is swept: control and array_idle carry no plan, so pitch cannot move them,
# and running them per rung would buy six identical numbers at full factorisation cost. The
# per-shape control and idle arms are already above, at the same operating point.
#
# NB the ladder starts at 100 um here, not 50. The GA100 runs on a 100 um thermal grid and
# tile_grid refuses a pitch finer than the mesh -- the solve cannot resolve tiles it cannot mesh.
for P in $PITCH_SWEEP_UM; do
    if [ "$P" -lt "$ACCEL_CELL_UM" ]; then
        log "SKIP pitch ${P} um on the accelerator: finer than its ${ACCEL_CELL_UM} um grid"
        continue
    fi
    for PLACE in contiguous scattered; do
        run "mr_ladder_p${P}_${PLACE}_array_on" \
            --stack "$ACCEL_ARRAY_STACK" --pitch-um "$P" --cell-um "$ACCEL_CELL_UM" $SPREAD_ARGS \
            $SOLVE $LASER --die-power-W $ACCEL_W_HI $ACCEL_COOLING \
            --kernel occupancy --n-active 8 --placement "$PLACE"
    done
done

log "all points queued; waiting"
wait
log "=== accelerator MR batch COMPLETE ==="
