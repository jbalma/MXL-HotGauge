#!/usr/bin/env bash
# §P0.38 -- the DESIGNED finger cluster at 16x / 32x beside the strip and compact members, and the
# bounds on the compact 16x's transport wall. Write elsewhere and mv in (METHODS §2.2):
#
#   scripts/finger_cluster_ladder.sh > results/campaign_queue/running/.fc.tmp \
#     && mv results/campaign_queue/running/.fc.tmp results/campaign_queue/finger_cluster.par10.tsv
#
# Per-block shape, 50 um cells, arm D, target device, matched die WATTS (rung x the reference's
# 101.09708 mm^2); die areas are the members' own (docs/evidence/d1_exec_density_family_*.json),
# written here as constants so this script never shells out. The strip / compact 16x rows at this
# geometry are results/cluster_transport/ and results/compact_cluster/.
# Predictions: docs/PHASE0_CHECKLIST.md §P0.38 P1-P5, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/finger_cluster}"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
BASE="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --array-coverage 1.00 --mr-envelope-shape power --arms array_on"
REF_MM2=101.09708
declare -A MM2=( [0.0625]=82.6464 [0.03125]=82.0331 )
emit() { printf '%s\t%s\n' "$1" "$2"; }
run() { # member-dir-suffix factor burial pitch rung extra-flags out-subdir
  local S="$1" F="$2" B="$3" P="$4" R="$5" X="$6" SUB="$7" W D d
  W=$(awk -v r="$R" -v a="$REF_MM2" 'BEGIN{printf "%.3f", r*a}')
  D=$(awk -v r="$R" -v a="$REF_MM2" -v m="${MM2[$F]}" 'BEGIN{printf "%.4f", r*a/m}')
  d="$OUT/$SUB/b${B}/p${P}/W$W"
  emit "$d" "python examples/mr_comparison.py --stack auto --pitch-um $P --burial-um $B --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} $BASE $FLAGS $X --flp-dir $REPO/examples/floorplans/outputs/d1_exec${F}${S} --density $D --out-dir $d"
}
DYE="--mr-extractor dye --mr-dt-max 45"
for P in 100 200; do
  for R in 1.10 1.20 1.60 2.00 2.40; do
    run _finger  0.0625  20 $P $R "$DYE" finger_x0.0625
    run _finger  0.03125 20 $P $R "$DYE" finger_x0.03125
    run ""       0.03125 20 $P $R "$DYE" strip_x0.03125
    run _compact 0.03125 20 $P $R "$DYE" compact_x0.03125
  done
done
# P5: bounds on the compact 16x's wall -- no scalar lift, the extractor's curve alone
for R in 1.60 2.00; do
  run _compact 0.0625 5  100 $R "--mr-extractor gaas-retuned-enhanced" bounds/compact_x0.0625_gaasr
  run _compact 0.0625 5  100 $R "--mr-extractor dye"          bounds/compact_x0.0625_dye
  run _compact 0.0625 20 50  $R "--mr-extractor gaas-retuned-enhanced" bounds/compact_x0.0625_gaasr
done
