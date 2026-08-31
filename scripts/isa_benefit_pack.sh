#!/usr/bin/env bash
#
# MR benefit across the REBUILT floorplans -- the re-run of the six-floorplan sweep on the
# MXL-HotGauge Floorplan Pack's published block areas.
#
#   scripts/isa_benefit_pack.sh <slurm_jobid> [iso|published|both]
#
# Why this exists
# ---------------
# scripts/isa_benefit.sh ran the same experiment on floorplans built from press ratios, and its
# one durable result was that `relative_plateau_25pct` ordered the cost of holding a margin at
# rho +1.000 across six of them. That result now has to survive floorplans whose block mix, block
# sizes and vector width all changed:
#
#   * every core area is a PUBLISHED number where one exists (Golden Cove 7.123 mm^2,
#     Zen 2 3.54, Neoverse V1 2.52, N1 1.15), not a chained press ratio;
#   * the unit mix is Golden Cove's published six-block decomposition, so the featureless
#     `core_other` slab falls from 22.1% of the core to 1.35%;
#   * the vector multiple is now actually INSTALLED -- it never was, and all six of the old
#     floorplans carried the x86 AVX-512 accelerator at 1.981x the FPU.
#
# If the metric survives that, it has survived a change of input as large as anything this
# project can throw at it. If it does not, the earlier transfer result was a property of one
# family of re-weightings rather than of designs, which is worth more than a confirmation.
#
# Two arms, and they answer different questions
# ---------------------------------------------
#   iso        every floorplan at 0.60 W/mm^2 -- the SAME conditions as the earlier sweep, so the
#              metric result is comparable point for point. Geometry is the only thing that moves.
#   published  every floorplan at ITS OWN published power density: Neoverse V1 0.476 W/mm^2,
#              N1 0.870, and the Tesla D1 die-level anchor 0.620 for the x86 parts. This is the
#              swap the handoff asks for -- the ISA comparison stops redistributing the Skylake
#              trace at a common density and becomes an activity comparison at the die level.
#              NOTE it is still a GEOMETRY comparison inside the core: the pack publishes no
#              per-block power for any part, so the intra-core shape is still the Skylake trace.
#
# --power-follows-area, and it is not optional here
# ------------------------------------------------
# A McPAT trace and a McPAT floorplan agree by construction. These floorplans' areas are
# published, and the pack publishes no per-block power for anything, so the two inputs no longer
# match and a rule is needed. Holding each block's POWER puts 28 W/mm^2 on the shrunken
# `core_other` slab and six of seven dies then have no steady state; holding each block's power
# DENSITY leaves only the arrangement changing, which is what this sweep claims to vary.
# The cost of that choice is stated rather than hidden: these points compare geometry at
# constant activity density, and the `published` arm moves activity only at the DIE level.
#
# Held fixed so only the intended thing moves: same margins, same 500 um pitch, same burial,
# same uniform activity (the most hostile assumption for MR and the tier screens' own control).

set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"

JOBID="${1:?usage: isa_benefit_pack.sh <slurm_jobid> [iso|published|both]}"
MODE="${2:-both}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT_ROOT:-$REPO/results/isa_benefit_pack}"
mkdir -p "$OUT"
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
throttle() { while [ "$(jobs -rp | wc -l)" -ge "${MAXJOBS:-8}" ]; do wait -n; done; }

OFFSETS="${OFFSETS:-3 5 8}"
ISO_DENSITY="${ISO_DENSITY:-0.60}"

# variant -> floorplan directory. The baseline uses the shipped outputs; each variant has its own
# directory holding the tiler's natural skylake<node>_... names, so --flp-dir is all that changes
# between arms. No driver knows an ISA exists.
FLPDIR_x86_skylake="$REPO/examples/floorplans/outputs"
for v in x86_golden_cove x86_zen2 arm_n1 arm_v1 arm_a64fx riscv_xiangshan; do
    eval "FLPDIR_$v=$REPO/examples/floorplans/isa_outputs/$v"
done
VARIANTS="x86_skylake x86_golden_cove x86_zen2 arm_n1 arm_v1 arm_a64fx riscv_xiangshan"

# Published W/mm^2 per variant, read from the pack through isa_floorplans.density_for(). Derived
# in one place so the script and the module cannot disagree; a variant with no published density
# falls back to the iso value and the fallback is LOGGED, never silent.
declare -A PUB
while IFS='=' read -r k v; do PUB["$k"]="$v"; done < <(
    cd "$REPO" && . "$REPO/setup_environment.sh" >/dev/null 2>&1 && python - <<'PY'
import sys, os
sys.path.insert(0, 'HotGauge')
from HotGauge.thermal.isa_floorplans import ISA_VARIANTS, density_for
for k in ISA_VARIANTS:
    d = density_for(k)
    print('{}={}'.format(k, d if d is not None else ''))
PY
)
# An empty table means the query above failed -- most often because the conda environment was
# not on PATH. Refusing here is the point: with `set -u` an empty table used to abort the driver
# mid-run with 'PUB[...]: unbound variable' AFTER the iso arm had already been launched, which
# reads like the sweep finished rather than like it died.
if [ "${#PUB[@]}" -eq 0 ]; then
    echo "FATAL: could not read published densities from isa_floorplans.density_for()." >&2
    echo "       Check that setup_environment.sh activates the conda env." >&2
    exit 3
fi

run_point() {
    local key="$1" flpdir="$2" density="$3" tag="$4"
    local dir="$OUT/$tag"
    if [ -f "$dir/mr_comparison.json" ]; then log "SKIP $tag"; return; fi
    throttle
    log "START $tag  (d=$density)"
    mkdir -p "$dir"
    srun --jobid="$JOBID" --overlap bash -lc \
        ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
         OMP_NUM_THREADS=1 python -u examples/mr_comparison.py $ARM_ARGS \
           --flp-dir $flpdir --power-follows-area $REPO/examples/floorplans/outputs \
           --cores 34 --density $density --cfm 88 \
           --mr-target-offset-K ${tag##*off} --spot-min-um 10 --spot-policy dilute \
           --activity uniform --out-dir $dir \
         > $OUT/$tag.log 2>&1" &
}

run_arm() {
    local arm="$1" v off d dir
    for v in $VARIANTS; do
        eval "dir=\$FLPDIR_$v"
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
            run_point "$v" "$dir" "$d" "${arm}_${v}_off${off}"
        done
    done
}

log "=== ISA benefit on PACK-REBUILT floorplans: 7 floorplans x ${OFFSETS// /,} K, mode=$MODE ==="
case "$MODE" in
    iso)       run_arm iso ;;
    published) run_arm published ;;
    both)      run_arm iso; run_arm published ;;
    *) echo "mode must be iso|published|both" >&2; exit 2 ;;
esac
wait
log "=== ISA benefit (pack) COMPLETE ==="
