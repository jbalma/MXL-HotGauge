#!/usr/bin/env bash
#
# Next-steps batch: item 1's re-runs, item 3's deep stacks, item 4's second margin curve.
#
#   scripts/nextsteps_batch.sh <slurm_jobid>
#
# Item 1 (verification scope) is a code change and it only takes effect on NEW runs: the older
# JSONs recorded "some solve failed" and nothing finer, so the points it was hiding have to be
# re-measured to benefit. Those are the pitch family, three margin points, and the two other
# overnight3 stragglers.
#
# Item 3's 8-high stacks failed on solver capacity rather than on physics -- SuperLU 4.3 cannot
# factorise ~1.7M unknowns ("Can't expand MemType 0") -- so they are re-run on a 100 um grid.
# Coarsening smooths lateral gradients, so a coarsened peak is not comparable with a 50 um peak;
# the questions being asked (which layer binds, how wide the memory plateau is) tolerate it.
#
# Item 4 puts a second margin curve at a different density and cooling class, because the knee
# at ~94 C is the largest lever in the study and currently rests on one curve at one point.
set -uo pipefail

JOBID="${1:?usage: nextsteps_batch.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/nextsteps"
MAX_CONC="${MAX_CONC:-8}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
running() { jobs -rp | wc -l; }
throttle() { while [ "$(running)" -ge "$MAX_CONC" ]; do sleep 10; done; }

# `done` is written by the step itself, so a job that dies leaves no marker and is retried.
# Two earlier runs were launched without one and I read their absence as "still running" for two
# days -- every launch goes through this function now.
run() {
    local tag="$1"; local script="$2"; shift 2
    if [ -f "$OUT/$tag/done" ]; then log "SKIP $tag"; return 0; fi
    throttle
    log "START $tag"
    mkdir -p "$OUT/$tag"
    local qargs
    printf -v qargs '%q ' "$@"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python -u $script $qargs --out-dir $OUT/$tag > $OUT/$tag.log 2>&1 && \
         touch $OUT/$tag/done" &
}

log "=== next-steps batch starting, max concurrency $MAX_CONC ==="

# ---------------------------------------------------------------------------------------
# ITEM 1 re-runs: points whose verdict was decided by a probe failure rather than by the
# reported field. The pitch family is the prize -- six runs that agree to within 0.02 W across
# 1/10/100 um and both policies, currently unquotable on a technicality.
# ---------------------------------------------------------------------------------------
for S in 1 10 100; do
    for POL in dilute exclude; do
        run "pitch_s${S}_${POL}" examples/mr_comparison.py \
            --cores 34 --density 1.15 --cfm 88 --mr-target-C 98 \
            --spot-min-um "$S" --spot-policy "$POL" --mr-iter 25 --max-iter 120
    done
done
for T in 95 98 99; do
    run "margin_T${T}_d1.10" examples/mr_comparison.py \
        --cores 34 --density 1.10 --cfm 88 --mr-target-C $T \
        --spot-min-um 10 --spot-policy dilute --mr-iter 25 --max-iter 120
done
run "ceiling_d1.17" examples/mr_comparison.py \
    --cores 34 --density 1.17 --cfm 88 --mr-target-C 98 \
    --spot-min-um 10 --spot-policy dilute --mr-iter 25 --max-iter 120
run "cores128_d1.00" examples/mr_comparison.py \
    --cores 128 --density 1.00 --cfm 88 --mr-target-C 98 \
    --spot-min-um 10 --spot-policy dilute --mr-iter 20 --max-iter 120

# ---------------------------------------------------------------------------------------
# ITEM 3: the 8-high stack, on a grid that fits. 4 dies at 50 um already ran and is the
# comparison point; the 8-die run at 100 um answers whether depth moves the constraint, and a
# 4-die run at 100 um is included so depth can be compared at EQUAL grid rather than across one.
# ---------------------------------------------------------------------------------------
run "D_dies8_air_c100"    examples/stacked_memory_study.py \
    --cores 34 --density 1.00 --cfm 88 --mem-dies 8 --mem-iter 5 --cell-um 100
run "D_dies4_air_c100"    examples/stacked_memory_study.py \
    --cores 34 --density 1.00 --cfm 88 --mem-dies 4 --mem-iter 5 --cell-um 100
run "D_dies8_liquid_c100" examples/stacked_memory_study.py \
    --cores 34 --density 1.00 --r-th 0.05 --mem-dies 8 --mem-iter 5 --cell-um 100
# Worse bond conductivity is the other half of "large stack thermal resistance": microbump rather
# than hybrid bonding, seven layers of it.
run "D_dies8_air_badbond" examples/stacked_memory_study.py \
    --cores 34 --density 1.00 --cfm 88 --mem-dies 8 --mem-iter 5 --cell-um 100 --bond-um 15

# ---------------------------------------------------------------------------------------
# ITEM 4: a second margin curve. 1.15 W/mm^2 on air (a harder point on the same cooling) and
# 1.10 on a liquid-class sink (the same density, much better cooling). If the knee tracks the
# top of the plateau rather than an absolute temperature, it should MOVE with both.
# ---------------------------------------------------------------------------------------
for T in 93 94 96 98; do
    run "margin2_T${T}_d1.15" examples/mr_comparison.py \
        --cores 34 --density 1.15 --cfm 88 --mr-target-C $T \
        --spot-min-um 10 --spot-policy dilute --mr-iter 25 --max-iter 120
    run "margin3_T${T}_liquid" examples/mr_comparison.py \
        --cores 34 --density 1.10 --r-th 0.05 --mr-target-C $T \
        --spot-min-um 10 --spot-policy dilute --mr-iter 25 --max-iter 120
done

log "all points queued; waiting"
wait
log "=== next-steps batch COMPLETE ==="
