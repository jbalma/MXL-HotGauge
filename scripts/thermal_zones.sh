#!/usr/bin/env bash
#
# Tests 1 and 2 of the power-recovery programme, fanned out across the allocation.
#
#   scripts/thermal_zones.sh <slurm_jobid> [extractor|zones|both]
#
# Test 2 (extractor, the prerequisite): the Carnot factor phi = 1 - T0/Th is set by the
# temperature of the reservoir the heat is lifted FROM -- the anti-Stokes extractor, not the
# silicon junction. They differ by the conduction drop up through the die, which grows with
# burial depth and with power density. Every exergy number in the framing is wrong by that drop
# if it is read off the junction. Swept over burial x pitch x density.
#
# Test 1 (zones, the blocking one): drive an escalating removal budget over the COLD zone (L2/L3,
# measured 80.3% and 97.7% static) with the hot zone uncooled, and record the ACHIEVED gradient at
# each step. The saturation curve is the deliverable -- thermal_zones.py predicts analytically
# that a monolithic die needs 3000-6300x less boundary conductance than silicon provides, so the
# gradient should stop responding early. This is the same question by 3D-ICE instead of algebra.
#
# One srun per (depth, pitch) so the ladders run concurrently; each invocation does its own sweep.
set -uo pipefail
JOBID="${1:?usage: thermal_zones.sh <slurm_jobid> [extractor|zones|both]}"
MODE="${2:-both}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
DEPTHS="${DEPTHS:-50 200}"
PITCHES="${PITCHES:-100 500 2000}"
DENSITIES="${DENSITIES:-0.6 2.0 10.0 50.0}"
BUDGETS="${BUDGETS:-0 2 5 10 20 40}"
log(){ printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

run_mode () {
    local mode="$1" out="$REPO/results/zone_$1"
    mkdir -p "$out"
    for d in $DEPTHS; do for p in $PITCHES; do
        local tag="d${d}_p${p}"
        [ -f "$out/$tag/results.json" ] && { log "SKIP $mode $tag"; continue; }
        log "START $mode $tag"
        local extra=""
        [ "$mode" = extractor ] && extra="--densities $DENSITIES" || extra="--budgets-W $BUDGETS"
        srun --jobid="$JOBID" --overlap bash -lc \
            ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
             OMP_NUM_THREADS=1 python -u examples/thermal_zone_probe.py --mode $mode \
               --depths $d --pitches $p $extra --out-dir $out/$tag \
             > $out/$tag.log 2>&1" &
    done; done
}
case "$MODE" in
    extractor) run_mode extractor ;;
    zones)     run_mode zones ;;
    both)      run_mode extractor; run_mode zones ;;
esac
wait
log "=== thermal_zones ($MODE) COMPLETE ==="
