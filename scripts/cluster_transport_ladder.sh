#!/usr/bin/env bash
# §P0.32 -- the 8x / 16x execution-cluster ladder at 20 um and 5 um burial: where heat TRANSPORT
# binds a >100 W/mm^2 functional unit. Members from generate_exec_density_family.py --factors
# 0.125 0.0625; matched die WATTS as D1 (the reference ladder's rungs x 101.097 mm^2); the
# per-block envelope shape; 50 um cells (the 8x cALU is one cell, the 16x sub-cell -- see the
# grid caveat in the predictions). The reference die at the same burials / pitches / shape is
# emitted too, so the premium is like-for-like.
#   scripts/cluster_transport_ladder.sh > results/campaign_queue/cluster.par6.tsv
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/cluster_transport}"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --array-coverage 1.00 --mr-extractor dye --mr-dt-max 45 --mr-envelope-shape power"
REF_MM2=101.09708
REF_DIR="$REPO/examples/floorplans/outputs"
EVJ="$REPO/docs/evidence/d1_exec_density_family_x8x16.json"
emit() { printf '%s\t%s\n' "$1" "$2"; }
run() { # dir flpdir mm2 burial pitch rung arms
  local d="$1" flpdir="$2" mm2="$3" B="$4" P="$5" R="$6" arms="$7"
  local W D
  W=$(python3 -c "print('%.3f'%($R*$REF_MM2))"); D=$(python3 -c "print('%.4f'%($R*$REF_MM2/$mm2))")
  emit "$d/W$W" "python examples/mr_comparison.py --stack auto --pitch-um $P --burial-um $B --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} $POINT $FLAGS --flp-dir $flpdir --density $D --arms $arms --out-dir $d/W$W"
}
for F in 0.125 0.0625; do
  DIR="$REF_DIR/d1_exec${F}"
  MM2=$(python3 -c "import json;print([m for m in json.load(open('$EVJ'))['members'] if abs(m['factor']-$F)<1e-9][0]['die_mm2'])")
  for B in 20 5; do
    for P in 200 100; do
      d="$OUT/x${F}/b${B}/p${P}"
      for R in 1.10 1.20; do run "$d" "$DIR" "$MM2" $B $P $R "array_idle array_on"; done
      for R in 1.60 2.00 2.40; do run "$d" "$DIR" "$MM2" $B $P $R "array_on"; done
    done
  done
done
# the reference die, like-for-like (per-block shape, same burial / pitch / grid), 202 and 243 W
for B in 20 5; do
  for P in 200 100; do
    d="$OUT/ref/b${B}/p${P}"
    for R in 2.00 2.40; do run "$d" "$REF_DIR" "$REF_MM2" $B $P $R "array_on"; done
  done
done
