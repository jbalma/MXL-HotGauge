#!/usr/bin/env bash
#
# MR benefit across the FOUR floorplans -- the test of the prediction registered in
# docs/evidence/isa_floorplans.json, and the first sweep that varies GEOMETRY rather than workload.
#
#   scripts/isa_benefit.sh <slurm_jobid>
#
# Why this exists
# ---------------
# The 27 Aug workload regression validated relative_plateau_25pct (rho +0.84 against cost) but
# could not touch power_density_concentration or thermal_aspect, because it varied the workload on
# ONE die and those two are geometric -- they were literally constant across all 33 points.
#
# It also could not tell whether the metrics TRANSFER. A predictor validated on eleven workloads
# over one floorplan may be describing that floorplan.
#
# The registered prediction, which this can falsify:
#   1. a compact core at constant die power has a NARROWER plateau and larger span
#   2. a wide-vector core stands further clear of its runner-up
#   3. therefore both are BETTER MR targets than x86 -- lower cost for the same demanded margin
# If (3) fails while (1) and (2) hold, the metrics do not transfer and the regression that
# validated them was workload-specific. That is the more valuable outcome and it is why this runs.
#
# Held fixed so only GEOMETRY varies: same density, same margins, same pitch, same burial, same
# workload shape (uniform -- the most hostile assumption for MR, and the one the tier screens use
# as their control).

# ---------------------------------------------------------------------------------------------
# [!] SUPERSEDED 28 Aug 2026 -- this script no longer describes the floorplans it would load.
# ---------------------------------------------------------------------------------------------
# It resolves variants by directory under examples/floorplans/isa_outputs/, and those directories
# were REBUILT on the floorplan pack's published block areas. arm_n2 and riscv_p670 no longer
# exist (they were chained press ratios and are retired -- see isa_floorplans.RETIRED_VARIANTS),
# and arm_v1 is now a different floorplan with a published 2.52 mm^2 core rather than a 0.71x
# re-weighting. Worse, the rebuilt floorplans REQUIRE --power-follows-area, which this script
# does not pass: without it McPAT's un-itemised core power lands on a slab the published mix
# shrinks 32x, and the die has no steady state.
#
# So running this would silently mix two generations of floorplan into results/isa_benefit and
# report runaway for physical dies. Use scripts/isa_benefit_pack.sh instead. The results this
# script produced are still on disk and still valid for the floorplans they were run on:
# results/isa_benefit/ and docs/evidence/isa_benefit_prediction_test.json.
# ---------------------------------------------------------------------------------------------
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

if [ "${I_KNOW_THIS_IS_SUPERSEDED:-0}" != "1" ]; then
    echo "REFUSED: scripts/isa_benefit.sh is superseded -- its variant directories were rebuilt" >&2
    echo "         on published block areas and it does not pass --power-follows-area." >&2
    echo "         Use: scripts/isa_benefit_pack.sh <jobid> [iso|published|both]" >&2
    echo "         Override with I_KNOW_THIS_IS_SUPERSEDED=1 only to reproduce an old point." >&2
    exit 2
fi

JOBID="${1:?usage: isa_benefit.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT_ROOT:-$REPO/results/isa_benefit}"
mkdir -p "$OUT"
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
throttle() { while [ "$(jobs -rp | wc -l)" -ge "${MAXJOBS:-8}" ]; do wait -n; done; }

OFFSETS="${OFFSETS:-3 5 8}"

# variant -> floorplan directory. The baseline uses the shipped outputs; each ISA variant has its
# own directory holding the tiler's natural skylake<node>_... names, so --flp-dir is all that
# changes between arms. No driver knows an ISA exists.
run_variant() {
    local key="$1" flpdir="$2" off
    for off in $OFFSETS; do
        local tag="${key}_off${off}"
        local dir="$OUT/$tag"
        if [ -f "$dir/mr_comparison.json" ]; then log "SKIP $tag"; continue; fi
        throttle
        log "START $tag"
        mkdir -p "$dir"
        srun --jobid="$JOBID" --overlap bash -lc \
            ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
             OMP_NUM_THREADS=1 python -u examples/mr_comparison.py $ARM_ARGS \
               --flp-dir $flpdir --cores 34 --density $DENSITY_STACKED --cfm 88 \
               --mr-target-offset-K $off --spot-min-um 10 --spot-policy dilute \
               --activity uniform --out-dir $dir \
             > $OUT/$tag.log 2>&1" &
    done
}

log "=== ISA benefit sweep: 4 floorplans x ${OFFSETS// /,} K margin, d=$DENSITY_STACKED ==="
run_variant x86_skylake "$REPO/examples/floorplans/outputs"
run_variant arm_v1      "$REPO/examples/floorplans/isa_outputs/arm_v1"
run_variant arm_n2      "$REPO/examples/floorplans/isa_outputs/arm_n2"
run_variant riscv_p670  "$REPO/examples/floorplans/isa_outputs/riscv_p670"
wait
log "=== ISA benefit sweep COMPLETE ==="
