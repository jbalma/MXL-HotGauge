#!/usr/bin/env bash
# §P0.36 -- the COMPACT execution cluster beside its sliver twin, same geometry, per-block shape.
#   scripts/compact_cluster_ladder.sh > results/campaign_queue/compact.par6.tsv
# 8x / 16x at 20 um burial x {200, 100} um pitch x five rungs, and at 5 um / 100 um x {202, 243 W};
# x0.5 / x0.25 at the D1 geometry (200 um burial, 500 um pitch) x five rungs. Matched die watts.
# Predictions: docs/PHASE0_CHECKLIST.md §P0.36.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/compact_cluster}"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --array-coverage 1.00 --mr-extractor dye --mr-dt-max 45 --mr-envelope-shape power"
REF_MM2=101.09708
EVJ="$REPO/docs/evidence/d1_exec_density_family_compact.json"
emit() { printf '%s\t%s\n' "$1" "$2"; }
run() { # factor burial pitch rung arms
  local F="$1" B="$2" P="$3" R="$4" arms="$5" MM2 W D d
  MM2=$(python3 -c "import json;print([m for m in json.load(open('$EVJ'))['members'] if abs(m['factor']-$F)<1e-9][0]['die_mm2'])")
  W=$(python3 -c "print('%.3f'%($R*$REF_MM2))"); D=$(python3 -c "print('%.4f'%($R*$REF_MM2/$MM2))")
  d="$OUT/x${F}/b${B}/p${P}/W$W"
  emit "$d" "python examples/mr_comparison.py --stack auto --pitch-um $P --burial-um $B --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} $POINT $FLAGS --flp-dir $REPO/examples/floorplans/outputs/d1_exec${F}_compact --density $D --arms $arms --out-dir $d"
}
for F in 0.125 0.0625; do
  for P in 200 100; do
    for R in 1.10 1.20 1.60 2.00 2.40; do run $F 20 $P $R array_on; done
  done
  for R in 2.00 2.40; do run $F 5 100 $R array_on; done
done
for F in 0.5 0.25; do
  for R in 1.10 1.20 1.60 2.00 2.40; do run $F 200 500 $R array_on; done
done
