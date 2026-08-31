#!/usr/bin/env bash
#
# The per-ISA comparison at ISO DIE AREA -- one die per ISA class, all ~100 mm^2.
#
#   scripts/isa_isoarea.sh <slurm_jobid> [iso|published|both]
#
# Why this exists, and why the earlier sweeps cannot answer the question it asks
# ------------------------------------------------------------------------------
# scripts/isa_benefit_pack.sh runs every floorplan at **34 cores**, which is the right control
# for a metric study -- it holds the tiling fixed and lets geometry vary. It is the wrong control
# for an ISA comparison, because the cores differ 6x in area and so the dies differ **4.7x**,
# 62 to 290 mm^2. And the metric work established that what orders the cost of holding a margin
# is the die's ABSOLUTE THERMAL SCALE, not the shape of its temperature distribution
# (docs/evidence/isa_metric_transfer_pack.json). So a per-ISA claim taken from that sweep is
# mostly a claim about die size wearing an architecture's name -- the same error as the 27 Aug
# constant-density sweep, one level up.
#
# Here the DIE is held at ~100 mm^2 and the core count varies, which is what a real product
# comparison is: a 100 mm^2 die is a 100 mm^2 die whether it carries 10 Golden Coves or 54
# Neoverse N1s. Spread falls from 4.67x to 1.15x (94.9 - 108.8 mm^2).
#
#   x86_skylake      34 cores  101.10 mm^2   <- UNCHANGED, the back-catalogue control
#   x86_golden_cove  10        104.20        published mix AND published area
#   x86_zen2         22        107.53        iso-node x86 size check
#   arm_v1           30        108.82        published area + power + V/F on one row
#   arm_n1           54         94.88        the compact N-class contrast
#   arm_a64fx        33        103.33        derived area
#   riscv_xiangshan  33        106.83        derived area -- NO published RISC-V core area exists
#
# Keeping x86_skylake at 34 cores is deliberate: it is the exact point the whole catalogue rests
# on, it lands inside the iso-area band anyway, and it makes every number here comparable with
# every number already on disk.
#
# It should also settle Golden Cove's runaway, which was never about Golden Cove: 34 P-cores at
# 7.123 mm^2 is a 290 mm^2 die at 175 W on an 88 CFM direct-die cooler, which is not a part
# anyone builds.
#
# The two arms are as in isa_benefit_pack.sh -- iso density (0.60 W/mm^2) and each part at its
# own published density. --power-follows-area is mandatory on every pack-rebuilt floorplan; see
# leakage_feedback.rebalance_trace_by_block_area for why.

set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

JOBID="${1:?usage: isa_isoarea.sh <slurm_jobid> [iso|published|both]}"
MODE="${2:-both}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT_ROOT:-$REPO/results/isa_isoarea}"
mkdir -p "$OUT"
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
throttle() { while [ "$(jobs -rp | wc -l)" -ge "${MAXJOBS:-6}" ]; do wait -n; done; }

OFFSETS="${OFFSETS:-3 5 8}"
ISO_DENSITY="${ISO_DENSITY:-0.60}"

# variant -> "core_count floorplan_dir". The core count is the whole point of this script, so it
# lives here beside the directory rather than being passed in.
declare -A CORES=( [x86_skylake]=34 [x86_golden_cove]=10 [x86_zen2]=22
                   [arm_v1]=30 [arm_n1]=54 [arm_a64fx]=33 [riscv_xiangshan]=33 )
VARIANTS="x86_skylake x86_golden_cove x86_zen2 arm_v1 arm_n1 arm_a64fx riscv_xiangshan"
flpdir_for() {
    if [ "$1" = x86_skylake ]; then echo "$REPO/examples/floorplans/outputs"
    else echo "$REPO/examples/floorplans/isa_outputs/$1"; fi
}

declare -A PUB
while IFS='=' read -r k v; do PUB["$k"]="$v"; done < <(
    cd "$REPO" && . "$REPO/setup_environment.sh" >/dev/null 2>&1 && python - <<'PY'
import sys
sys.path.insert(0, 'HotGauge')
from HotGauge.thermal.isa_floorplans import ISA_VARIANTS, density_for
for k in ISA_VARIANTS:
    d = density_for(k)
    print('{}={}'.format(k, d if d is not None else ''))
PY
)
if [ "${#PUB[@]}" -eq 0 ]; then
    echo "FATAL: could not read published densities. Check setup_environment.sh." >&2
    exit 3
fi

run_point() {
    local key="$1" ncore="$2" flpdir="$3" density="$4" off="$5" tag="$6"
    local dir="$OUT/$tag"
    if [ -f "$dir/mr_comparison.json" ]; then log "SKIP $tag"; return; fi
    throttle
    log "START $tag  (${ncore}c, d=$density)"
    mkdir -p "$dir"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         OMP_NUM_THREADS=1 python -u examples/mr_comparison.py $ARM_ARGS \
           --flp-dir $flpdir --power-follows-area $REPO/examples/floorplans/outputs \
           --cores $ncore --density $density --cfm 88 \
           --mr-target-offset-K $off --spot-min-um 10 --spot-policy dilute \
           --activity uniform --out-dir $dir \
         > $OUT/$tag.log 2>&1" &
}

run_arm() {
    local arm="$1" v off d n
    for v in $VARIANTS; do
        n="${CORES[$v]}"
        if [ "$arm" = published ]; then
            d="${PUB[$v]:-}"
            if [ -z "$d" ]; then
                log "NO PUBLISHED DENSITY for $v -- falling back to $ISO_DENSITY (stated, not silent)"
                d="$ISO_DENSITY"
            fi
        else
            d="$ISO_DENSITY"
        fi
        for off in $OFFSETS; do
            run_point "$v" "$n" "$(flpdir_for "$v")" "$d" "$off" "${arm}_${v}_off${off}"
        done
    done
}

log "=== ISA at ISO DIE AREA (~100 mm^2): 7 dies x ${OFFSETS// /,} K, mode=$MODE ==="
case "$MODE" in
    iso)       run_arm iso ;;
    published) run_arm published ;;
    both)      run_arm iso; run_arm published ;;
    *) echo "mode must be iso|published|both" >&2; exit 2 ;;
esac
wait
log "=== ISA iso-area sweep COMPLETE ==="
