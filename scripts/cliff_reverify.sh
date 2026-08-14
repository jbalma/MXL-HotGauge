#!/usr/bin/env bash
#
# Re-measure the 34-core thermal cliff with automatic convergence verification.
#
#   scripts/cliff_reverify.sh <slurm_jobid>
#
# Why this rerun exists
# ---------------------
# The previously reported cliff (1.30-1.40 W/mm^2) was established by tightening `relax` by hand
# and checking that the answer stopped moving. That test used the OLD convergence criterion --
# the change between successive solves -- which is proportional to `relax`. Tightening the
# damping therefore made the tolerance weaker by the same factor, so "the answer stopped moving"
# is not the evidence it appears to be: on a lumped model driven by the real 7nm leakage curve,
# the apparent cliff moved UP by 23% as fixed relax went 1.0 -> 0.0125, precisely because more
# points passed a progressively weaker test.
#
# Every point here is solved on the fixed-point RESIDUAL (damping-independent) at two damping
# levels, and is reported only if the peaks agree. See docs/GAMEPLAN.md P0.1.
set -uo pipefail

JOBID="${1:?usage: cliff_reverify.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/cliff_verified"
mkdir -p "$OUT"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }

point() {
    local tag="$1"; shift
    local dir="$OUT/$tag"
    if [ -f "$dir/mr_comparison.json" ]; then
        log "SKIP $tag (already complete)"
        return 0
    fi
    log "START $tag"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         python examples/mr_comparison.py $* --out-dir $dir \
         > $OUT/$tag.log 2>&1" &
}

log "=== cliff re-verification starting ==="
for D in 1.15 1.20 1.25 1.30 1.35 1.40 1.45; do
    point "d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute
done
wait
log "=== cliff re-verification COMPLETE ==="
