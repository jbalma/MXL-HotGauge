#!/usr/bin/env bash
#
# Fill the known gaps: the honest test of design D, the points that failed verification, and
# the one curve the project keeps quoting single points from.
#
#   scripts/gapfill_batch.sh <slurm_jobid>
#
# Every block says what gap it fills and what would count as an answer.
set -uo pipefail

# The cooling array's stack and pitch, in one place -- see scripts/array_config.sh.
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

# The array configuration is injected BY DRIVER rather than written at each call site.
#
# Before the array existed, no point in this file named a stack: they all inherited
# `--stack skylake`, the historical lidded template, and the cooling was subtracted from the
# processor trace so the package barely showed. Both of those are now wrong, and a per-call-site
# fix is a list of places to forget. A driver that is not listed here is REFUSED rather than run
# on whatever default it ships -- an unstamped result is worse than a missing one, because it
# looks like a result.
stack_args_for() {
    case "$1" in
        # Builds its own stack per arm and emits all three.
        examples/mr_comparison.py|examples/clock_headroom.py)  echo "$ARM_ARGS" ;;
        # One stack per invocation; these points are baselines, so the control arm.
        examples/thermal_tiers.py)                             echo "$CONTROL_STACK_ONLY" ;;
        examples/accelerator_study.py)                         echo "$ACCEL_CONTROL_ARGS" ;;
        # The memory stack cannot take a generated template yet -- see LEGACY_STACK.
        examples/stacked_memory_study.py)                      echo "--stack $LEGACY_STACK" ;;
        *)                                                     echo "__UNCONFIGURED__" ;;
    esac
}

JOBID="${1:?usage: gapfill_batch.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/gapfill"
MAX_CONC="${MAX_CONC:-8}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
running() { jobs -rp | wc -l; }
throttle() { while [ "$(running)" -ge "$MAX_CONC" ]; do sleep 10; done; }

# Arguments re-quoted with printf %q: $* silently re-splits anything containing a space and
# killed five runs of the previous batch that way.
run() {
    local tag="$1"; local script="$2"; shift 2
    if [ -f "$OUT/$tag/done" ]; then log "SKIP $tag"; return 0; fi
    throttle
    log "START $tag"
    local sargs; sargs="$(stack_args_for "$script")"
    if [ "$sargs" = "__UNCONFIGURED__" ]; then
        log "REFUSED $tag: no array configuration for $script -- add one to stack_args_for()"
        return 1
    fi
    mkdir -p "$OUT/$tag"
    local qargs
    printf -v qargs '%q ' "$@"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python -u $script $sargs $qargs --out-dir $OUT/$tag > $OUT/$tag.log 2>&1 && \
         touch $OUT/$tag/done" &
}

log "=== gap-fill batch starting, max concurrency $MAX_CONC ==="

# ---------------------------------------------------------------------------------------
# GAP 1: design D was tested in the friendliest possible geometry.
#
# One thin die bonded to the logic left the memory 28 K COOLER than the logic, with a complete
# 16-of-16 plateau, so the constraint never moved. HIR 2023 ch.20 s.2.10 blames "large stack
# thermal resistance" -- an 8-high stack, seven more dies and seven more bonds between the hot
# die and the sink. Depth is swept (1 is already measured) so the trend is visible rather than
# a single contrasting point.
#
# An answer looks like: the memory peak overtaking the logic's margin, and/or the memory
# plateau narrowing because the hot die sees the logic's hotspot rather than the die average.
# ---------------------------------------------------------------------------------------
for N in 4 8; do
    run "D_dies${N}_air" examples/stacked_memory_study.py \
        --cores 34 --density $DENSITY_STACKED --cfm 88 --mem-dies $N --mem-iter 5
done
run "D_dies8_concentrated" examples/stacked_memory_study.py \
    --cores 34 --density $DENSITY_STACKED --cfm 88 --mem-dies 8 --mem-iter 5 \
    --emphasise 'Floating Point Units' --emphasis-factor 4
# Does better bulk cooling rescue a deep stack, or is the stack resistance the wall?
run "D_dies8_liquid" examples/stacked_memory_study.py \
    --cores 34 --density $DENSITY_STACKED --r-th 0.05 --mem-dies 8 --mem-iter 5

# ---------------------------------------------------------------------------------------
# GAP 2: the rescue cost is a CURVE in the margin demanded and we have sampled two points of
# it -- 46.6 W at a 92 C target and 0.29 W at 98 C, a 160x swing over 6 K. That curve is now
# the most decision-relevant object in the study, and its shape (knee? smooth?) is unknown.
# ---------------------------------------------------------------------------------------
for T in 93 94 95 96 97 99; do
    run "margin_T${T}_d1.10" examples/mr_comparison.py \
        --cores 34 --density $DENSITY_WORKING_LO --cfm 88 --mr-target-C $T \
        --spot-min-um 10 --spot-policy dilute --mr-iter 25
done

# ---------------------------------------------------------------------------------------
# GAP 3: five of six pixel-pitch points failed damping verification in overnight3, so the
# "pitch barely matters" claim -- a large fabrication-cost argument -- is currently unsupported.
# They failed in the marginal regime BEFORE the envelope anchor, the boundary bisection, the
# bistability fix and the target-policy correction existed. Re-run with all four, and at a
# target near the limit so the MR loop is not asked to hold 8 K of margin it was never asked for.
# ---------------------------------------------------------------------------------------
for S in 1 10 100; do
    for POL in dilute exclude; do
        run "spot_s${S}_${POL}" examples/mr_comparison.py \
            --cores 34 --density $DENSITY_WORKING --cfm 88 --mr-target-C 98 \
            --spot-min-um "$S" --spot-policy "$POL" --mr-iter 25
    done
done

# ---------------------------------------------------------------------------------------
# GAP 4: the remaining unverified points from overnight3, re-run with the same four fixes.
# p2_ceiling_d1.17 was the MR ceiling boundary; p3_target_T78_d1.12 reported a converged
# 120.3 C that the verification caught.
# ---------------------------------------------------------------------------------------
run "ceiling_d1.17" examples/mr_comparison.py \
    --cores 34 --density 0.95 --cfm 88 --mr-target-C 98 \
    --spot-min-um 10 --spot-policy dilute --mr-iter 25
run "target78_d1.12" examples/mr_comparison.py \
    --cores 34 --density $DENSITY_WORKING --cfm 88 --mr-target-C 78 \
    --spot-min-um 10 --spot-policy dilute --mr-iter 25

# ---------------------------------------------------------------------------------------
# GAP 5: core-count scaling. The 128-core points are the only ones that never produced a
# verified answer, and "does the MR benefit hold as core count scales" is a headline question.
# Expensive (2.4M unknowns, ~670 s to factorise) so only the two that matter.
# ---------------------------------------------------------------------------------------
for D in $DENSITY_SCALING; do
    run "cores128_d${D}" examples/mr_comparison.py \
        --cores 128 --density "$D" --cfm 88 --mr-target-C 98 \
        --spot-min-um 10 --spot-policy dilute --mr-iter 20
done

log "all points queued; waiting"
wait
log "=== gap-fill batch COMPLETE ==="
