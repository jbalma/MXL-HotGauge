#!/usr/bin/env bash
#
# Follow-on studies. Waits for the main overnight study, then runs two more.
#
#   scripts/followon_study.sh <slurm_jobid>
#
# Study A -- how far can MR be pushed, ignoring the cooling power budget?
# Study B -- can MR make an older process node out-perform a newer one?
#
set -uo pipefail
JOBID="${1:?usage: followon_study.sh <jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/followon"
MAX_CONC="${MAX_CONC:-14}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
running() { jobs -rp | wc -l; }
throttle() { while [ "$(running)" -ge "$MAX_CONC" ]; do sleep 5; done; }

point() {
    local tag="$1"; shift
    local dir="$OUT/$tag"
    [ -f "$dir/mr_comparison.json" ] && { log "SKIP $tag"; return 0; }
    throttle
    log "START $tag"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python examples/mr_comparison.py $* --out-dir $dir > $OUT/$tag.log 2>&1" &
}

# Wait for the main study to release the machine.
log "waiting for overnight2 to finish"
while pgrep -f 'overnight_study.sh' >/dev/null 2>&1; do sleep 60; done
log "=== follow-on starting ==="

# =====================================================================================
# STUDY A -- the MR performance ceiling.
#
# Every result so far clipped to a fixed target with MR's cost counted against a budget. This
# asks the opposite question: with the laser bill ignored, how much performance is available,
# and WHICH constraint stops it?
#
# The answer is not "unlimited". MRParams caps each block at dt_max_K (10 K lift) and h_max
# (10 W/mm^2 flux), so beyond some target the plan stops growing no matter how much laser is
# offered. Driving the target down until performance saturates locates that envelope wall.
#
# The dt_max / h_max sweeps then say what a BETTER MR device would buy -- the device-roadmap
# question, as opposed to the deployment question.
# =====================================================================================
for T in 92 85 78 70 60 50 40 30; do
    point "A_ceiling_T${T}" --cores 34 --density 1.15 --cfm 88 --mr-target-C "$T" \
          --spot-min-um 10 --spot-policy dilute
done
for DT in 5 10 20 40; do
    point "A_dtmax_${DT}" --cores 34 --density 1.15 --cfm 88 --mr-target-C 40 \
          --mr-dt-max "$DT" --spot-min-um 10 --spot-policy dilute
done
for H in 5 10 25 50; do
    point "A_hmax_${H}" --cores 34 --density 1.15 --cfm 88 --mr-target-C 40 \
          --mr-h-max "$H" --spot-min-um 10 --spot-policy dilute
done

# =====================================================================================
# STUDY B -- generational: can MR make an older node beat a newer one?
#
# Same architecture and workload at three process nodes, 16 cores each. Measured natively:
#
#     node    area        power    density
#     14nm    202.4 mm^2  50.5 W   0.249 W/mm^2
#     10nm    106.3 mm^2  42.9 W   0.404 W/mm^2
#      7nm     56.8 mm^2  37.5 W   0.660 W/mm^2
#
# Shrinking cuts power 1.35x but area 3.6x, so power density rises 2.65x from 14nm to 7nm. The
# newer part is thermally harder, which is why MR should help it more -- the interesting
# question is whether MR on the OLD part closes the gap anyway.
#
# Each node is swept up in density (a proxy for pushing voltage/frequency) until it hits its
# thermal wall, with MR off and on. The comparison is achievable throughput at each node's own
# limit.
#
# IMPORTANT CAVEAT, recorded here so nobody reads more into this than it supports: f_nominal is
# the SAME for every node in this sweep, so the comparison isolates the *thermal* difference and
# deliberately ignores the transistor-speed and architectural gains a real newer part brings. It
# answers "how much thermal headroom does MR return at each node", NOT "is a 2021 chip with MR
# faster than a 2027 chip". The latter needs node-dependent f_nominal and IPC, neither of which
# this model has.
# =====================================================================================
for NODE in 14nm 10nm 7nm; do
    for D in 0.25 0.40 0.60 0.80 1.00; do
        point "B_${NODE}_d${D}" --cores 16 --node "$NODE" --density "$D" --cfm 88 \
              --mr-target-C 78 --spot-min-um 10 --spot-policy dilute \
              --trace-dir "$REPO/mcpat_runs/${NODE}/linpack_3.8GHz" \
              --tech-node "$(echo "$NODE" | tr -d 'nm')"
    done
done

log "all follow-on points queued; waiting"
wait
log "=== follow-on COMPLETE ==="
srun --jobid="$JOBID" --overlap bash -lc \
    ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
     python scripts/summarise_followon.py > $OUT/SUMMARY.txt 2>&1" || true
log "summary at $OUT/SUMMARY.txt"
