#!/usr/bin/env bash
#
# Test 5: the constant-POWER ISA sweep, redone on the pack-rebuilt floorplans.
#
#   scripts/isa_constant_power_pack.sh <slurm_jobid>
#
# Why 34 cores here and iso-area elsewhere
# ----------------------------------------
# scripts/isa_isoarea.sh holds the DIE at ~100 mm^2 and lets core count vary, which is the right
# control for comparing ISAs. This test asks the opposite question -- the one the 27 August
# prediction was actually about: at the SAME total watts, does a more compact die cool better or
# worse? That needs the die areas to differ, so it runs at 34 cores where they span 4.7x
# (62 to 290 mm^2) and holds total power fixed by setting density = W / area per floorplan.
#
# The original run (scripts/isa_constant_power.sh, 27 Aug) found half the sweep had no steady
# state: both compact dies diverged at both power levels, including at densities comfortably
# under the measured grease cliff, because a compact die is penalised twice -- higher density at
# the same watts AND a worse spreading boundary. That was measured on press-ratio floorplans with
# a 22% featureless slab acting as a heat spreader. The rebuilt floorplans have no such slab and
# run 7-24 K hotter at matched area and power (P0.5g), so MORE divergence is expected, not less.
# Divergence is a result and is recorded as such, never averaged in as a large cost.
#
# --power-follows-area is mandatory: these floorplans' areas are published, not McPAT's, and
# without the rule McPAT's un-itemised core power lands on a slab the published mix shrinks 32x.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

JOBID="${1:?usage: isa_constant_power_pack.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT_ROOT:-$REPO/results/isa_constant_power_pack}"
mkdir -p "$OUT"
log(){ printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
throttle(){ while [ "$(jobs -rp | wc -l)" -ge "${MAXJOBS:-6}" ]; do wait -n; done; }

WATTS="${WATTS:-25 40 60}"
OFFSETS="${OFFSETS:-3 8}"

# variant | die area mm^2 at 34 cores | floorplan dir. Areas measured off the generated files.
variants() {
    cat <<'V'
x86_skylake|101.10|examples/floorplans/outputs
x86_golden_cove|290.08|examples/floorplans/isa_outputs/x86_golden_cove
x86_zen2|153.94|examples/floorplans/isa_outputs/x86_zen2
arm_v1|115.91|examples/floorplans/isa_outputs/arm_v1
arm_n1|62.19|examples/floorplans/isa_outputs/arm_n1
arm_a64fx|103.92|examples/floorplans/isa_outputs/arm_a64fx
riscv_xiangshan|106.83|examples/floorplans/isa_outputs/riscv_xiangshan
V
}

log "=== ISA constant-POWER on rebuilt floorplans: 7 dies x ${WATTS// /,} W x ${OFFSETS// /,} K ==="
# `< /dev/null` on the srun below is load-bearing: srun reads stdin, and inside a
# `while read ... done < <(...)` loop it consumes the loop's own input stream. Without it this
# driver silently stops after two variants -- it launched 12 of 42 points and then reported
# COMPLETE, which looks like success. The other sweep scripts iterate with `for` over a variable
# and are not exposed to this.
while IFS='|' read -r key area dir; do
    [ -z "$key" ] && continue
    for W in $WATTS; do
        DENS=$(awk -v w="$W" -v a="$area" 'BEGIN{printf "%.4f", w/a}')
        for off in $OFFSETS; do
            tag="${key}_${W}W_off${off}"
            [ -f "$OUT/$tag/mr_comparison.json" ] && { log "SKIP $tag"; continue; }
            throttle
            log "START $tag  (${area} mm^2 -> ${DENS} W/mm^2)"
            mkdir -p "$OUT/$tag"
            srun --jobid="$JOBID" --overlap bash -lc \
                ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
                 OMP_NUM_THREADS=1 python -u examples/mr_comparison.py $ARM_ARGS \
                   --flp-dir $REPO/$dir --power-follows-area $REPO/examples/floorplans/outputs \
                   --cores 34 --density $DENS --cfm 88 \
                   --mr-target-offset-K $off --spot-min-um 10 --spot-policy dilute \
                   --activity uniform --out-dir $OUT/$tag \
                 > $OUT/$tag.log 2>&1" < /dev/null &
        done
    done
done < <(variants)
wait
log "=== ISA constant-power (pack) COMPLETE ==="
