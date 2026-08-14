#!/usr/bin/env bash
#
# Overnight MR study. Detached, restartable, writes everything to NFS.
#
#   scripts/overnight_study.sh <slurm_jobid>
#
# Runs a pool of mr_comparison points concurrently. Every point is independent, each holds its
# own persistent 3D-ICE session (~88 s factorisation on the 34-core die, then ~0.6 s/solve), so
# a point costs ~2 minutes rather than the ~70 it cost before the session work.
#
# Design notes
# ------------
# * Results go to results/overnight/ on NFS, NOT node-local /tmp, so they survive the
#   allocation ending.
# * Each point writes its own .log and .json. A point that dies takes nothing else with it.
# * Already-completed points are SKIPPED on re-run (checks for mr_comparison.json), so this is
#   safe to relaunch after an interruption.
# * MAX_CONC is deliberately below the core count: each point runs a Python driver and a
#   3D-ICE server, and oversubscribing makes every point slower without finishing any sooner.
#
# The four phases answer four separate questions -- see docs/OVERNIGHT_PLAN.md.
set -uo pipefail

JOBID="${1:?usage: overnight_study.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/overnight2"
MAX_CONC="${MAX_CONC:-14}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }

running() { jobs -rp | wc -l; }

throttle() {
    while [ "$(running)" -ge "$MAX_CONC" ]; do sleep 5; done
}

# point <tag> <extra args...>
point() {
    local tag="$1"; shift
    local dir="$OUT/$tag"
    if [ -f "$dir/mr_comparison.json" ]; then
        log "SKIP $tag (already complete)"
        return 0
    fi
    throttle
    log "START $tag"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python examples/mr_comparison.py $* --out-dir $dir \
         > $OUT/$tag.log 2>&1" &
}

log "=== overnight study starting, max concurrency $MAX_CONC ==="

# -------------------------------------------------------------------------------------
# Phase 1 -- the CONVERGENT regime, broadly sampled.
#
# The previous attempt put almost every point past the cliff and returned RUNAWAY for nearly
# all of them, which told us nothing. Worse, that cliff was an artifact: relax=0.5 exceeded the
# stability limit of the leakage fixed point, so points that have a perfectly good solution
# were reported as diverging (1.10 and 1.15 W/mm^2 both converge in 3 iterations at relax=0.1,
# to 96.3 C and 101.1 C). Everything here runs at relax=0.1, verified relax-independent
# against 0.05 to within 0.1 K.
# -------------------------------------------------------------------------------------
for D in 0.60 0.70 0.80 0.90 1.00 1.05 1.10 1.15; do
    point "p1_dens_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute
done

# -------------------------------------------------------------------------------------
# Phase 2 -- the TRUE cliff, between 1.15 (converges) and 1.25 (diverges at every relax).
# Also re-checks each point at relax=0.05: a genuine runaway diverges at any damping, a
# numerical one does not.
# -------------------------------------------------------------------------------------
for D in 1.16 1.18 1.20 1.22 1.24; do
    point "p2_cliff_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute
    point "p2_cliffR05_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute --relax 0.05
done

# -------------------------------------------------------------------------------------
# Phase 3 -- MR target sweep where it can actually act. At 1.15 the peak is ~101 C, only 9 K
# above the default target, so a lower target is what decides whether MR does anything at all.
# This is the coverage question, now asked at a density that converges.
# -------------------------------------------------------------------------------------
for T in 92 85 78 72 65; do
    for D in 1.05 1.15; do
        point "p3_target_T${T}_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C "$T" \
              --spot-min-um 10 --spot-policy dilute
    done
done

# -------------------------------------------------------------------------------------
# Phase 4 -- pixel pitch and policy, at a target low enough that MR is genuinely working.
# -------------------------------------------------------------------------------------
for S in 1 10 100; do
    for POL in dilute exclude; do
        point "p4_spot_s${S}_${POL}" --cores 34 --density 1.15 --cfm 88 --mr-target-C 78 \
              --spot-min-um "$S" --spot-policy "$POL"
    done
done

# -------------------------------------------------------------------------------------
# Phase 5 -- core count and airflow, in the convergent regime.
# -------------------------------------------------------------------------------------
for N in 70 128; do
    for D in 0.80 1.00; do
        point "p5_cores${N}_d${D}" --cores "$N" --density "$D" --cfm 88 --mr-target-C 78 \
              --spot-min-um 10 --spot-policy dilute
    done
done
for CFM in 50 133 200; do
    point "p5_cfm${CFM}" --cores 34 --density 1.15 --cfm "$CFM" --mr-target-C 78 \
          --spot-min-um 10 --spot-policy dilute
done

log "all points queued; waiting"
wait
log "=== overnight study COMPLETE ==="

# Roll everything up so the morning starts with a table, not a directory listing.
srun --jobid="$JOBID" --overlap bash -lc \
    ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
     python scripts/summarise_overnight.py > $OUT/SUMMARY.txt 2>&1" || true
log "summary written to $OUT/SUMMARY.txt"
