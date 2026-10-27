#!/usr/bin/env bash
# §P0.35 -- the dense cluster's cold-end wall: is the lost 243 W rung the film's, or one material's?
#   scripts/cluster_coldend_ladder.sh > results/campaign_queue/coldend.par6.tsv
# The §P0.32 members and flags; (a) retuned-enhanced GaAs over the whole array, (b) a dual layout
# (dye + retuned-enhanced GaAs over the execution column), (c) plain GaAs as the failing control,
# (d) the dye at 50 um pitch. Predictions: docs/PHASE0_CHECKLIST.md §P0.35.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/cluster_coldend}"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --array-coverage 1.00 --mr-dt-max 45 --mr-envelope-shape power --arms array_on"
REF_MM2=101.09708
EVJ="$REPO/docs/evidence/d1_exec_density_family_x8x16.json"
EXEC_PAT='^(cALU|iALU|FPUs|AVXs|RBB|iWin|fpiWin|ROB|iRF|fpRF)'
emit() { printf '%s\t%s\n' "$1" "$2"; }
run() { # tag factor burial pitch rung extra-flags
  local tag="$1" F="$2" B="$3" P="$4" R="$5"; shift 5
  local MM2 W D d
  MM2=$(python3 -c "import json;print([m for m in json.load(open('$EVJ'))['members'] if abs(m['factor']-$F)<1e-9][0]['die_mm2'])")
  W=$(python3 -c "print('%.3f'%($R*$REF_MM2))"); D=$(python3 -c "print('%.4f'%($R*$REF_MM2/$MM2))")
  d="$OUT/$tag/x${F}/b${B}/p${P}/W$W"
  emit "$d" "python examples/mr_comparison.py --stack auto --pitch-um $P --burial-um $B --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} $POINT $FLAGS --flp-dir $REPO/examples/floorplans/outputs/d1_exec${F} --density $D $* --out-dir $d"
}
for F in 0.125 0.0625; do
  for R in 2.00 2.40; do
    for B in 20 5; do run gaas_re $F $B 100 $R --mr-extractor gaas-retuned-enhanced; done
    run dual $F 20 100 $R --mr-extractor dye --mr-zone-mode dual --mr-cold-extractor gaas-retuned-enhanced --mr-cold-zone-pattern "'$EXEC_PAT'"
    run dye_p50 $F 20 50 $R --mr-extractor dye
  done
done
run gaas_plain 0.0625 20 100 2.00 --mr-extractor gaas-retuned
