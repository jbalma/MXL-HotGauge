#!/usr/bin/env bash
#
# Confirmation runs for the design study (docs/DESIGN_STUDY_PLAN.md).
#
#   scripts/design_study_batch.sh <slurm_jobid>
#   MAX_CONC=12 scripts/design_study_batch.sh <slurm_jobid>
#
# Everything here was integrated first and is launched together, so the whole study lands as
# one set rather than as a trickle of individually-interpreted points. Each block states the
# prediction it is testing, because a run whose expected outcome was not written down in
# advance is very easy to read as confirmation of whatever it produced.
#
# Predictions on the record:
#
#  D  stacked memory  -- the binding constraint moves to the MEMORY layer (85 C refresh
#     breakpoint, 95 C hard limit, against the logic's 100 C), and the memory hot zone is
#     LESS degenerate than the logic's 15-block plateau. If the memory plateau is also wide,
#     the same problem simply moved up a layer and MR gains nothing from stacking.
#
#  F  dt_max roadmap -- on the BALANCED die, raising dt_max 10 -> 20 -> 30 K does NOT help,
#     because the binding constraint is the number of blocks that must be clipped, not the
#     depth of each clip. On the CONCENTRATED + turbo die it SHOULD help roughly
#     proportionally, because clip-one gain there is already 9.86 K of a 10 K device and is
#     capped by the device rather than by the neighbours. Two opposite predictions from one
#     mechanism, which is the point of running both.
#
#  E  distributed MR -- spending the clipping run's own budget (9.01 W) spread over the die
#     buys much LESS clock than clipping does. If it buys the same, the hotspot framing that
#     every MR result here rests on is wrong.
#
#  Plus: the item-2 re-measurement of the rescue cost under the corrected target policy and
#  the bistability fix, and the 1.10 W/mm^2 point that failed damping verification.
set -uo pipefail

JOBID="${1:?usage: design_study_batch.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/design_batch"
MAX_CONC="${MAX_CONC:-10}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
running() { jobs -rp | wc -l; }
throttle() { while [ "$(running)" -ge "$MAX_CONC" ]; do sleep 10; done; }

# run <tag> <script> <args...>
run() {
    local tag="$1"; local script="$2"; shift 2
    if [ -f "$OUT/$tag/done" ]; then log "SKIP $tag"; return 0; fi
    throttle
    log "START $tag"
    mkdir -p "$OUT/$tag"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python -u $script $* --out-dir $OUT/$tag > $OUT/$tag.log 2>&1 && touch $OUT/$tag/done" &
}

log "=== design study batch starting, max concurrency $MAX_CONC ==="

# ---------------------------------------------------------------------------------------
# D -- stacked memory. Baseline logic mix and the concentrated (design G) mix, since the two
# put the logic hotspot in different places and therefore heat different memory banks.
# ---------------------------------------------------------------------------------------
run "D_stacked_balanced"     examples/stacked_memory_study.py \
    --cores 34 --density 1.00 --cfm 88 --mem-iter 8
run "D_stacked_concentrated" examples/stacked_memory_study.py \
    --cores 34 --density 1.00 --cfm 88 --mem-iter 8 \
    --emphasise 'Floating Point Units' --emphasis-factor 4
# Cooler logic: does the memory limit still bind when the logic is comfortable?
run "D_stacked_liquid"       examples/stacked_memory_study.py \
    --cores 34 --density 1.00 --r-th 0.05 --mem-iter 8

# ---------------------------------------------------------------------------------------
# F -- dt_max roadmap, on both degeneracy regimes. Screens only: the tier metric is what the
# prediction is about, and it costs one solve.
# ---------------------------------------------------------------------------------------
for DT in 10 20 30; do
    run "F_balanced_dt$DT"    examples/thermal_tiers.py \
        --cores 34 --density 1.00 --cfm 88 --dt-max $DT --top 20
    run "F_concentrated_dt$DT" examples/thermal_tiers.py \
        --cores 34 --density 1.00 --cfm 88 --dt-max $DT --top 20 \
        --emphasise 'Floating Point Units' --emphasis-factor 4 \
        --activity turbo --background 0.25
done

# ---------------------------------------------------------------------------------------
# E -- distributed MR at the clipping run's own budget, on the design where clipping won.
# 9.01 W is what turbo_m2_concentrated spent to buy +6.0%.
# ---------------------------------------------------------------------------------------
run "E_distributed" examples/clock_headroom.py \
    --cores 34 --node-model 7nm --cfm 88 --turbo-core 0 --turbo-background 0.25 \
    --emphasise 'Floating Point Units' --emphasis-factor 4 \
    --mr --mr-mode distributed --mr-budget-W 5.198 --mr-target-margin-K 2 \
    --f-lo 3.0 --f-hi 5.0 --f-tol 0.05

# ---------------------------------------------------------------------------------------
# Item 2 -- the rescue cost, re-measured under the corrected target policy AND the
# bistability fix. The published 46.6 W used a 92 C target on a 100 C-limit die, so part of
# that cost was policy; and the hot-branch rejection was not in place when it was measured.
# ---------------------------------------------------------------------------------------
for D in 1.10 1.15; do
    run "rescue_d${D}" examples/mr_comparison.py \
        --cores 34 --density "$D" --cfm 88 --mr-target-C 98 \
        --spot-min-um 10 --spot-policy dilute --mr-iter 25
done

log "all points queued; waiting"
wait
log "=== design study batch COMPLETE ==="
