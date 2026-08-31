#!/usr/bin/env bash
#
# MR benefit across the eleven workload shapes -- the missing join for LADDER_GEN0 section 3.
#
#   scripts/shape_benefit.sh <slurm_jobid>
#
# Why this exists
# ---------------
# Section 3's deliverable is a REGRESSION of measured MR benefit against the phase-1 floorplan
# metrics, across floorplan and workload variants, with any metric that does not predict DROPPED.
# It has never been runnable, and the reason is a gap nobody had looked for:
#
#   * the 11 workload shapes that give the metrics their variety exist only in the CONTROL-ARM
#     tier screens (scripts/recentred_gapfill.sh) -- no MR was ever measured on them;
#   * all 35 catalogue points that DO have a measured MR benefit ran at uniform activity on the
#     same 34-core die, varying only density, target and pitch.
#
# The predictors and the response were never measured on the same points. This closes that.
#
# Design
# ------
# * SAME shapes, SAME density (DENSITY_STACKED) and SAME construction as the tier screens, so a
#   shape screened there and measured here are the same input. examples/mr_comparison.py gained
#   the shaping flags for exactly this reason, copied from thermal_tiers rather than reinvented.
# * DERIVED targets (--mr-target-offset-K), because an absolute target is what made the previous
#   margin study measure nothing when the boundary moved. Three offsets give the regression a
#   benefit RANGE per shape rather than a single point.
# * Metrics are stamped on every row by the driver, so predictors and response land in one file
#   and no join by tag is needed -- tags have lied about their contents before.

set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

JOBID="${1:?usage: shape_benefit.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT_ROOT:-$REPO/results/shape_benefit}"
mkdir -p "$OUT"
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
throttle() { while [ "$(jobs -rp | wc -l)" -ge "${MAXJOBS:-8}" ]; do wait -n; done; }

run_point() {
    local tag="$1"; shift
    local dir="$OUT/$tag"
    if [ -f "$dir/mr_comparison.json" ]; then log "SKIP $tag"; return 0; fi
    log "START $tag"
    local qargs; printf -v qargs '%q ' "$@"      # %q: --emphasise takes a value with spaces
    mkdir -p "$dir"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         OMP_NUM_THREADS=1 python -u examples/mr_comparison.py $qargs --out-dir $dir \
         > $OUT/$tag.log 2>&1" &
}

FPU='Floating Point Units'
OFFSETS="${OFFSETS:-3 5 8}"

shape() {
    local name="$1"; shift
    local off
    for off in $OFFSETS; do
        throttle
        run_point "${name}_off${off}" $ARM_ARGS --cores 34 --density "$DENSITY_STACKED" \
            --cfm 88 --mr-target-offset-K "$off" --spot-min-um 10 --spot-policy dilute "$@"
    done
}

log "=== shape-benefit sweep: 11 shapes x ${OFFSETS// /,} K margin, d=$DENSITY_STACKED ==="
shape uniform         --activity uniform
shape turbo           --activity turbo
shape turbo_idle      --activity turbo --background 0.0
shape mixed25         --activity mixed --active-fraction 0.25
shape mixed50         --activity mixed --active-fraction 0.50
shape fpu2            --activity uniform --emphasise "$FPU" --emphasis-factor 2.0
shape fpu3            --activity uniform --emphasise "$FPU" --emphasis-factor 3.0
shape fpu4            --activity uniform --emphasise "$FPU" --emphasis-factor 4.0
shape g4_turbo        --activity turbo --emphasise "$FPU" --emphasis-factor 4.0
shape g4_turbo_idle   --activity turbo --background 0.0 --emphasise "$FPU" --emphasis-factor 4.0
shape g4_mixed25      --activity mixed --active-fraction 0.25 --emphasise "$FPU" --emphasis-factor 4.0
wait
log "=== shape-benefit sweep COMPLETE ==="
