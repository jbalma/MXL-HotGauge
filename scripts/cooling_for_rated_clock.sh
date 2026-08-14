#!/usr/bin/env bash
#
# P1.3 -- what cooling does a 7nm part at its rated clock actually need?
#
#   scripts/cooling_for_rated_clock.sh <slurm_jobid>
#
# The open result this answers: a 7nm 16/34-core part at its rated 5.0 GHz sits far above the
# density its cooling can hold on air, and runs away at 88, 133 and 200 CFM. Airflow is the
# wrong axis for that question -- the constriction resistance (beta-alpha = 1.042 K/W) is
# conduction, and no fan touches it. So sweep the COOLING SOLUTION as a resistance, from
# desktop air down to liquid class (0.02-0.05 K/W), and read off the clock each one sustains.
#
# Clock is searched, not assumed (examples/clock_headroom.py): every point reports the highest
# clock whose coupled solve holds the thermal limit, with damping verification on. One srun per
# resistance so they run concurrently; each holds its own persistent 3D-ICE session.
set -uo pipefail

JOBID="${1:?usage: cooling_for_rated_clock.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/cooling_for_clock"
CORES="${CORES:-34}"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }

point() {
    local rth="$1"; shift
    local tag="rth${rth}"
    local dir="$OUT/$tag"
    if [ -f "$dir/clock_headroom.json" ]; then
        log "SKIP $tag (already complete)"
        return 0
    fi
    log "START $tag"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python -u examples/clock_headroom.py --cores $CORES --node-model 7nm \
           --r-th $rth --f-lo 2.0 --f-hi 5.0 --f-tol 0.05 --mr $* \
           --out-dir $dir > $OUT/$tag.log 2>&1" &
}

log "=== cooling-for-rated-clock sweep starting (${CORES}-core 7nm) ==="
for R in 1.0 0.5 0.3 0.1 0.05 0.02; do
    point "$R"
done
wait
log "=== sweep COMPLETE ==="
