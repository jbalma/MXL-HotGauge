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
# levels, and is reported only if the peaks agree. See docs/GAMEPLAN.md P0.1.#
# THE ARRAY, 26 Aug 2026
# ----------------------
# mr_comparison now emits three arms per point of its own accord -- control (30 um of thermal
# grease, no cooling), array_idle (30 um of GaAs pixels in its place, at 0 W) and array_on (the
# same array under the planner) -- and reports the passive and the laser term separately. What
# this script has to supply is the GEOMETRY: $ARM_ARGS pins the stack, the burial depth, the grid
# and, above all, the TILE PITCH.
#
# The pitch is the substantive change. Everything in this file was swept at the driver's 500 um
# default, which is a modelling default chosen to keep the element count tractable on an 826 mm^2
# accelerator die. The first-generation device is 4-16 tiles over ~200 mm^2 -- 3.5 to 7 mm -- so
# these points were an order of magnitude finer than anything anyone is building. At 500 um a tile
# sits inside one floorplan block; at 5 mm one tile spans several, which is where the collateral
# trade lives. Results from before this line are a different device and must not be pooled with
# results from after it.

set -uo pipefail

# The cooling array's stack and pitch, in one place -- see scripts/array_config.sh.
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

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
         python examples/mr_comparison.py $ARM_ARGS $* --out-dir $dir \
         > $OUT/$tag.log 2>&1" &
}

log "=== cliff re-verification starting ==="
for D in $DENSITY_SWEEP $DENSITY_CLIFF; do
    point "d${D}" --cores 34 --density "$D" --cfm 88 --mr-target-C 92 \
          --spot-min-um 10 --spot-policy dilute
done
wait
log "=== cliff re-verification COMPLETE ==="
