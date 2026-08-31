#!/usr/bin/env bash
#
# The ISA comparison at constant DIE POWER -- the experiment the registered prediction should
# have specified.
#
#   scripts/isa_constant_power.sh <slurm_jobid>
#
# Why this exists
# ---------------
# scripts/isa_benefit.sh held constant DENSITY, so a smaller die simply dissipated less power
# (unaided peaks 63.1 -> 42.9 C) and came out cooler and flatter. That falsified the registered
# prediction, but it falsified it against a confound built into the experiment rather than
# against the physics the prediction was about: "a compact core at CONSTANT DIE POWER has less
# SRAM per watt to buffer the heat".
#
# Holding total watts fixed instead makes the compaction real, and it penalises the compact dies
# TWICE -- higher power density AND a worse spreading boundary, because the boundary the die sees
# scales with its area (docs/evidence/spreading_boundary_by_die.json: 0.553 K/W on the 7-core die
# against 0.108 on the GA100). Both are consequences of being small, and both belong in the answer.
#
# Two power levels, chosen from the measured cliff rather than picked:
#   25 W -- every die lands well under the 0.80-0.85 W/mm^2 grease cliff (0.247 .. 0.648)
#   40 W -- the compact dies reach 0.827 and 1.037, i.e. AT and PAST it (0.396 .. 1.037)
# If the compact dies lose their steady state at 40 W while x86 holds, that is not a failed run;
# it is the constant-power result, and it is the one that matters for a real design.

set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

JOBID="${1:?usage: isa_constant_power.sh <slurm_jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT_ROOT:-$REPO/results/isa_constant_power}"
mkdir -p "$OUT"
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
throttle() { while [ "$(jobs -rp | wc -l)" -ge "${MAXJOBS:-8}" ]; do wait -n; done; }

OFFSETS="${OFFSETS:-3 5 8}"
WATTS="${WATTS:-25 40}"

# variant | die area mm^2 | floorplan dir. Areas are measured off the generated floorplans.
variants() {
    cat <<'V'
x86_skylake|101.1|examples/floorplans/outputs
arm_v1|70.2|examples/floorplans/isa_outputs/arm_v1
arm_n2|48.4|examples/floorplans/isa_outputs/arm_n2
riscv_p670|38.6|examples/floorplans/isa_outputs/riscv_p670
V
}

log "=== ISA constant-POWER sweep: 4 floorplans x ${WATTS// /,} W x ${OFFSETS// /,} K margin ==="
while IFS='|' read -r key area dir; do
    [ -z "$key" ] && continue
    for W in $WATTS; do
        # density = total watts / die area, so every floorplan dissipates the SAME power
        DENS=$(awk -v w="$W" -v a="$area" 'BEGIN{printf "%.4f", w/a}')
        for off in $OFFSETS; do
            tag="${key}_${W}W_off${off}"
            [ -f "$OUT/$tag/mr_comparison.json" ] && { log "SKIP $tag"; continue; }
            throttle
            log "START $tag  (density $DENS W/mm^2)"
            mkdir -p "$OUT/$tag"
            srun --jobid="$JOBID" --overlap bash -lc \
                ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
                 OMP_NUM_THREADS=1 python -u examples/mr_comparison.py $ARM_ARGS \
                   --flp-dir $REPO/$dir --cores 34 --density $DENS --cfm 88 \
                   --mr-target-offset-K $off --spot-min-um 10 --spot-policy dilute \
                   --activity uniform --out-dir $OUT/$tag \
                 > $OUT/$tag.log 2>&1" &
        done
    done
done < <(variants)
wait
log "=== ISA constant-power sweep COMPLETE ==="
