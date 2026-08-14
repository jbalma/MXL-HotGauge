#!/usr/bin/env bash
#
# Overnight study, third attempt -- everything re-measured with convergence verification.
#
#   scripts/overnight3_study.sh <slurm_jobid>
#   MAX_CONC=8 scripts/overnight3_study.sh <slurm_jobid>     # share the node
#
# Why a third attempt
# -------------------
# `results/overnight/`  (attempt 1) ran at relax=0.5 and is void.
# `results/overnight2/` (attempt 2) fixed the damping but not the CONVERGENCE TEST, which
# measured the change between successive solves and therefore got weaker in proportion to the
# damping. At 1.15 W/mm^2 it declared convergence on iteration 2 at 101.09 C while the residual
# was still 6.5 K, and that trajectory reaches >1000 C by iteration 52. Everything in
# overnight2 at or above ~1.05 W/mm^2 is a truncation, including the 1.30-1.40 W/mm^2 "true
# cliff". See docs/CONVERGENCE.md.
#
# Every point here is solved on the damping-independent fixed-point residual, with backtracking
# damping, and re-solved at half the damping with the peaks required to agree. A point that
# fails prints ** UNCONVERGED ** and is excluded from the summary rather than reported.
#
# What changed in the plan, and why
# ---------------------------------
# The verified cliff on the 34-core die at 88 CFM is between 1.05 and 1.15 W/mm^2, not
# 1.30-1.40, and MR rescues 1.15 but not 1.18. Both interesting regions are therefore MUCH
# narrower and lower than attempt 2 assumed, so the density sweeps are re-centred there instead
# of spending the night confirming runaways at 1.25-1.45 (already done, all divergent).
#
# The open question this is built around: **does a lower MR target push the rescue ceiling out?**
# At a 92 C target MR buys roughly 1.05-1.15 -> 1.15-1.18 in density. Blocks above 92 C carry
# only ~10% of die power while 65% sits 10-20 K below it, so coverage -- not spot size -- is the
# suspected limit. Phase 3 asks it directly at the densities where it now matters.
#
# Points already measured with this exact configuration are SEEDED from results/cliff_verified
# rather than re-run: same code, same arguments, same machine.
set -uo pipefail

JOBID="${1:?usage: overnight3_study.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/overnight3"
SEED="$REPO/results/cliff_verified"
# node-03 has 64 CPUs and a point costs ~2 (one busy 3D-ICE server at ~87% plus a mostly-idle
# Python driver), so ~25 points fit. 8 is a deliberately safe default for sharing the node with
# another sweep; raise it when the node is yours. NB `uptime` on the phonon head node reports
# the HEAD node's load, not the compute node's -- check with
#   srun --jobid=<id> --overlap uptime
MAX_CONC="${MAX_CONC:-8}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
running() { jobs -rp | wc -l; }
throttle() { while [ "$(running)" -ge "$MAX_CONC" ]; do sleep 10; done; }

# seed <tag> <density>  -- reuse an identical, already-verified point
seed() {
    local tag="$1" d="$2"
    if [ -f "$OUT/$tag/mr_comparison.json" ]; then return 0; fi
    if [ -f "$SEED/d$d/mr_comparison.json" ]; then
        mkdir -p "$OUT/$tag"
        cp "$SEED/d$d/mr_comparison.json" "$OUT/$tag/"
        log "SEED $tag from cliff_verified/d$d (identical configuration)"
        return 0
    fi
    return 1
}

point() {
    local tag="$1"; shift
    if [ -f "$OUT/$tag/mr_comparison.json" ]; then
        log "SKIP $tag (already complete)"
        return 0
    fi
    throttle
    log "START $tag"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python -u examples/mr_comparison.py $* --out-dir $OUT/$tag \
         > $OUT/$tag.log 2>&1" &
}

log "=== overnight3 starting, max concurrency $MAX_CONC ==="

# ---------------------------------------------------------------------------------------
# Phase 1 -- the convergent regime and the exact cliff position.
# Attempt 2 sampled 0.60-1.15 believing the cliff was at 1.30; it is between 1.05 and 1.15, so
# the resolution goes where the answer is.
# ---------------------------------------------------------------------------------------
for D in 0.60 0.70 0.80 0.90 1.00 1.05 1.08 1.10 1.12 1.15; do
    seed "p1_dens_d${D}" "$D" || \
    point "p1_dens_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute
done

# ---------------------------------------------------------------------------------------
# Phase 2 -- where MR stops rescuing. 1.15 rescues (no steady state -> 96.83 C, 4.013 GHz);
# 1.18 does not. This resolves the ceiling to 0.01 W/mm^2.
# ---------------------------------------------------------------------------------------
for D in 1.16 1.17 1.18 1.20; do
    seed "p2_ceiling_d${D}" "$D" || \
    point "p2_ceiling_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute
done

# ---------------------------------------------------------------------------------------
# Phase 3 -- THE question: does a lower MR target push that ceiling out?
# A 92 C target only touches blocks above 92 C, which carry ~10% of die power. If coverage is
# the binding constraint, a lower target should rescue densities that 92 C cannot -- and if it
# does not, the limit is the heat budget (h_max / dt_max), which is a different device.
# ---------------------------------------------------------------------------------------
for T in 92 78 65; do
    for D in 1.12 1.16 1.18; do
        point "p3_target_T${T}_d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C "$T" \
              --spot-min-um 10 --spot-policy dilute
    done
done

# ---------------------------------------------------------------------------------------
# Phase 4 -- pixel pitch and policy, at a density and target where MR is genuinely working.
# Re-confirms the "pitch barely matters" result at a verified operating point; that result is a
# large fabrication saving if it holds (~450 pixels at 100 um vs ~32,000 at 10 um).
# ---------------------------------------------------------------------------------------
for S in 1 10 100; do
    for POL in dilute exclude; do
        point "p4_spot_s${S}_${POL}" --cores 34 --density 1.15 --cfm 88 --mr-target-C 78 \
              --spot-min-um "$S" --spot-policy "$POL"
    done
done

# ---------------------------------------------------------------------------------------
# Phase 5 -- does the MR benefit hold as core count scales, and how does airflow move the cliff?
# Densities chosen inside the verified convergent regime so the comparison is between solutions,
# not between two runaways. 128-core is expensive (~670 s factorisation), hence only two points.
# ---------------------------------------------------------------------------------------
for N in 70 128; do
    for D in 0.80 1.00; do
        point "p5_cores${N}_d${D}" --cores "$N" --density "$D" --cfm 88 --mr-target-C 78 \
              --spot-min-um 10 --spot-policy dilute
    done
done
for CFM in 50 133 200; do
    point "p5_cfm${CFM}_d1.10" --cores 34 --density 1.10 --cfm "$CFM" --mr-target-C 78 \
          --spot-min-um 10 --spot-policy dilute
done

log "all points queued; waiting"
wait
log "=== overnight3 COMPLETE ==="

srun --jobid="$JOBID" --overlap bash -lc \
    ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
     python scripts/summarise_overnight3.py > $OUT/SUMMARY.txt 2>&1" || true
log "summary written to $OUT/SUMMARY.txt"
