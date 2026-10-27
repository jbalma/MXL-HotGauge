#!/usr/bin/env bash
# §P0.39 -- the RAIL model (V_eff = V_dd - IR) in the generalized clock search: the reference die
# and the 8x / 16x strip clusters at the reference's 101.1 W, laser arm, rails sized for the
# native die to a 5 % static IR budget and widened `resize` x. Write elsewhere and mv in:
#   scripts/clock_rail.sh > results/campaign_queue/running/.cr.tmp \
#     && mv results/campaign_queue/running/.cr.tmp results/campaign_queue/clock_rail.par5.tsv
# Predictions: docs/PHASE0_CHECKLIST.md §P0.39 P1-P5, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/clock_rail}"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --thermal-limit-C 100 --mr --mr-dt-max 45 --array-coverage 1.00 --recovery-at-junction --mr-extractor dye --mr-envelope-shape power --f-lo 2.0 --f-hi 5.0 --f-tol 0.05 --arms array_on --mr-target-margin-K 8"
emit() { printf '%s\t%s\n' "$1" "$2"; }
src() { if [ "$1" = off ]; then echo "fmax"; else echo "fmax:rail=0.05,resize=$1"; fi; }
# §P0.41: MEMBERS=finger runs the DESIGNED finger clusters instead (16x / 32x, rails off / native / xJ)
if [ "${MEMBERS:-}" = finger ]; then
  CL="--stack auto --pitch-um 100 --burial-um 20 --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS}"
  for K in off 1 16; do
    d="$OUT/finger_x0.0625/resize$K"
    emit "$d" "python examples/clock_headroom.py $CL $POINT $FLAGS --flp-dir $REPO/examples/floorplans/outputs/d1_exec0.0625_finger --vf-source $(src $K) --density 1.2233 --out-dir $d"
  done
  for K in off 1 32; do
    d="$OUT/finger_x0.03125/resize$K"
    emit "$d" "python examples/clock_headroom.py $CL $POINT $FLAGS --flp-dir $REPO/examples/floorplans/outputs/d1_exec0.03125_finger --vf-source $(src $K) --density 1.2324 --out-dir $d"
  done
  exit 0
fi
# the reference die at 1.00 W/mm^2, the recorded geometry (rail-off twin: results/clock_fmax/qual_d1.00)
for K in 1 2; do
  d="$OUT/ref_d1.00/resize$K"
  emit "$d" "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --vf-source $(src $K) --density 1.00 --out-dir $d"
done
# the strip clusters at the reference's watts (101.097 W over the member's own area), 20 um / 100 um
CL="--stack auto --pitch-um 100 --burial-um 20 --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS}"
for K in off 1 4 8; do
  d="$OUT/x0.125/resize$K"
  emit "$d" "python examples/clock_headroom.py $CL $POINT $FLAGS --flp-dir $REPO/examples/floorplans/outputs/d1_exec0.125 --vf-source $(src $K) --density 1.2054 --out-dir $d"
done
for K in off 1 8 16; do
  d="$OUT/x0.0625/resize$K"
  emit "$d" "python examples/clock_headroom.py $CL $POINT $FLAGS --flp-dir $REPO/examples/floorplans/outputs/d1_exec0.0625 --vf-source $(src $K) --density 1.2233 --out-dir $d"
done
