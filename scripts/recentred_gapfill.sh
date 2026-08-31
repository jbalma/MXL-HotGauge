#!/usr/bin/env bash
#
# The three families the P0.5 catalogue re-run did not cover, re-centred on the corrected
# boundary and given a batch script so they stop being ad-hoc.
#
#   scripts/recentred_gapfill.sh <slurm_jobid>
#
# Why this exists
# ---------------
# Re-harvesting FINDINGS.json across both re-run roots (27 Aug 2026) shrank three families,
# because points present in the OLD results/ tree are in NO batch script and were therefore
# never in the re-run plan. They were ad-hoc invocations from earlier sessions, so their numbers
# exist only at the SUPERSEDED --spreading boundary and cannot be restated without new solves.
# See docs/evidence/findings_harvest_correction.json.
#
# Being ad-hoc is exactly why they were missed. That is the first thing this file fixes.
#
#   1. TIER SCREENS -- twelve standalone screens (tiers_uniform, tiers_turbo, tiers_fpu*,
#      tiers_g4_*, ...). docs/LADDER_GEN0.md section 3 lists "peak-to-runner-up gap" and
#      "plateau width at dt_max" as produced by these, so TWO of generation 0's five phase-1
#      floorplan metrics currently rest on the superseded boundary.
#
#   2. MARGIN AND RESCUE COST -- inert on the corrected boundary. The sweep asked for absolute
#      targets of 93-99 C while --spreading dropped the die to 73-81 C, so 68 of 85 catalogue
#      points returned "nothing above target", removed zero watts and engaged zero blocks. The
#      handbook's "Cost is dominated by how much margin you demand" has been WITHDRAWN for want
#      of any backing. See docs/evidence/catalogue_naming_and_margin_defects.json.
#
#   3. LEAKAGE-VOLTAGE SENSITIVITY -- leakv_e0 / leakv_e2, the arms that price the
#      `leak_v_exponent` assumption behind leakage scaling as V**exponent. Unmeasured on the
#      corrected boundary, and every clock_search result depends on it.
#
# TWO CORRECTIONS THAT HAD TO LAND FIRST, and both are the point
# --------------------------------------------------------------
# * **Targets are DERIVED, not stated.** Every margin point uses --mr-target-offset-K, so the
#   target is `this point's measured control-arm peak minus the offset`. An absolute target is
#   what let the old study slide out from under itself when the boundary moved, and it would do
#   it again the next time. A derived target cannot.
#
# * **dt_max is swept, not assumed.** examples/thermal_tiers.py hardcoded `--dt-max 10.0` -- the
#   unsourced LEGACY envelope -- until 27 Aug 2026, against a demonstrated 45 K. dt_max sets the
#   plateau width this driver reports, so a plateau measured at one dt_max is not comparable
#   with one measured at another. The 10 K rung is kept deliberately, so the historical screens
#   remain comparable; the rest measure what the hidden ceiling was hiding.
#
# Densities and stacks come from array_config.sh, and out-dirs are named FROM THE VARIABLES, not
# written by hand -- which is how sixteen tags in the last catalogue came to encode densities
# they never ran at.

set -uo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

JOBID="${1:?usage: recentred_gapfill.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT_ROOT:-$REPO/results/recentred_gapfill}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }

# Point-level restart, same contract as the catalogue: a point whose driver output is already on
# disk is skipped, so a re-launch after a fix costs only the points that failed.
run_point() {
    local tag="$1" driver="$2" out_json="$3"; shift 3
    local dir="$OUT/$tag"
    if [ -f "$dir/$out_json" ]; then log "SKIP $tag (already complete)"; return 0; fi
    log "START $tag"
    # %q, not $*. The command crosses TWO boundaries that re-split on whitespace -- this
    # function's argument list and the `bash -lc` string srun runs -- so an argument containing
    # a space (--emphasise 'Floating Point Units') arrives as three arguments and argparse
    # rejects it. scripts/design_study_batch.sh:72 records the same trap in the same words.
    local qargs
    printf -v qargs '%q ' "$@"
    mkdir -p "$dir"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         OMP_NUM_THREADS=1 python -u $driver $qargs --out-dir $dir \
         > $OUT/$tag.log 2>&1" &
}

# The node saturates at ~10 concurrent srun steps; anything past that queues behind itself.
throttle() { while [ "$(jobs -rp | wc -l)" -ge "${MAXJOBS:-8}" ]; do wait -n; done; }

log "=== re-centred gap-fill starting: tiers + margin + leakv ==="
log "    density(tiers)=$DENSITY_STACKED  working=$DENSITY_WORKING/$DENSITY_WORKING_LO  pitch=$PITCH_UM"

# ---------------------------------------------------------------------------------------------
# 1. TIER SCREENS. The twelve historical shapes, at the re-centred density, across the dt_max
#    ladder. dt_max is a pure post-processing parameter here -- it does not change the solve --
#    but it is recorded per point, so the sweep is cheap and the sensitivity becomes measurable
#    instead of assumed.
# ---------------------------------------------------------------------------------------------
DT_LADDER="${DT_LADDER:-10 20 30 45}"

# One shape across the dt_max ladder. Shape arguments arrive as "$@" and stay quoted all the
# way to python -- see run_point.
FPU='Floating Point Units'
tier_shape() {
    local shape="$1"; shift
    local DT
    for DT in $DT_LADDER; do
        throttle
        run_point "tiers_${shape}_dt${DT}" examples/thermal_tiers.py tiers.json \
            --cores 34 --density "$DENSITY_STACKED" --cfm 88 --dt-max "$DT" \
            $CONTROL_STACK_ONLY "$@"
    done
}

tier_shape uniform        --activity uniform
tier_shape turbo          --activity turbo
tier_shape turbo_idle     --activity turbo --background 0.0
tier_shape mixed25        --activity mixed --active-fraction 0.25
tier_shape mixed50        --activity mixed --active-fraction 0.50
tier_shape fpu2           --activity uniform --emphasise "$FPU" --emphasis-factor 2.0
tier_shape fpu3           --activity uniform --emphasise "$FPU" --emphasis-factor 3.0
tier_shape fpu4           --activity uniform --emphasise "$FPU" --emphasis-factor 4.0
tier_shape g4_turbo       --activity turbo --emphasise "$FPU" --emphasis-factor 4.0
tier_shape g4_turbo_idle  --activity turbo --background 0.0 --emphasise "$FPU" --emphasis-factor 4.0
tier_shape g4_mixed25     --activity mixed --active-fraction 0.25 --emphasise "$FPU" --emphasis-factor 4.0

# ---------------------------------------------------------------------------------------------
# 2. MARGIN AND RESCUE COST, on DERIVED targets. The offsets are kelvin BELOW each point's own
#    measured unaided peak, so every point has something to plan against by construction. That
#    is the whole correction: the question "what does margin cost" is only meaningful relative
#    to where the die actually sits.
# ---------------------------------------------------------------------------------------------
MARGIN_OFFSETS="${MARGIN_OFFSETS:-1 2 3 5 8 12}"

for D in $DENSITY_WORKING_LO $DENSITY_WORKING; do
    for OFF in $MARGIN_OFFSETS; do
        throttle
        run_point "margin_d${D}_off${OFF}" examples/mr_comparison.py mr_comparison.json \
            $ARM_ARGS --cores 34 --density "$D" --cfm 88 \
            --mr-target-offset-K "$OFF" --spot-min-um 10 --spot-policy dilute
    done
done

# The liquid arm: the uncomfortable curve, and the one whose MECHANISM survived the withdrawal.
# Better conventional cooling made MR irrelevant on air; this asks whether a derived target
# changes that verdict or merely relocates it.
for OFF in $MARGIN_OFFSETS; do
    throttle
    run_point "margin_liquid_off${OFF}" examples/mr_comparison.py mr_comparison.json \
        $ARM_ARGS --cores 34 --density "$DENSITY_WORKING_LO" --r-th 0.05 \
        --mr-target-offset-K "$OFF" --spot-min-um 10 --spot-policy dilute
done

# ---------------------------------------------------------------------------------------------
# 3. LEAKAGE-VOLTAGE EXPONENT. 1.0 is the documented default and an ASSUMPTION, not a
#    measurement; 0 and 2 bracket it. Any clock conclusion whose SIGN changes across this range
#    is not a finding.
# ---------------------------------------------------------------------------------------------
# NB: clock_headroom has NO --density. It SEARCHES for the sustainable clock, so die power is
# an output of the search rather than a setting -- passing --density is an error, not a no-op.
# Argument set matches scripts/cooling_for_rated_clock.sh so the arms are comparable.
for E in 0.0 1.0 2.0; do
    throttle
    run_point "leakv_e${E}" examples/clock_headroom.py clock_headroom.json \
        $ARM_ARGS --cores 34 --node-model 7nm --cfm 88 \
        --f-lo 2.0 --f-hi 5.0 --f-tol 0.05 --mr \
        --leak-v-exponent "$E" --vf-source table
done

wait
log "=== re-centred gap-fill COMPLETE ==="
log "harvest with: python scripts/collect_findings.py --results $OUT ..."
