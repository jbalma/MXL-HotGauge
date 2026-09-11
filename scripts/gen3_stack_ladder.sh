#!/usr/bin/env bash
# §P0.27.4 -- X4: the gen-3 two-die stack with the 3D chapter's geometry, at 100 um cells.
#
#   scripts/gen3_stack_ladder.sh > results/campaign_queue/gen3.par4.tsv
#
# Storage die (the reference's L2/L3 blocks, examples/floorplans/outputs/gen3_stack/) 50 um thick,
# face-to-back ABOVE the processor die on a 5 um bond; the array above the storage die. The bond's
# conductivity is the swept variable: hybrid ~120 W/mK, microbump ~50 (default), underfill ~5,
# isolating ~0.5. Objectives as D3 (§P0.22.2): the cache-leakage objective at 280 K on the dye
# (curve only) and with Cr:LiSAF on the cache tiles (--mr-zone-mode dual); the hot-spot objective
# at 2.00 W/mm^2 as the compute-die regression (P17) against results/x3_u70/ref/array/W202.194.
# Predictions: docs/PHASE0_CHECKLIST.md §P0.27.4 P14-P18, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/gen3_stack"
SPLIT="$REPO/examples/floorplans/outputs/gen3_stack"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent --cell-um 100"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_idle array_on --array-coverage 1.00 --mr-extractor dye --gen3-split $SPLIT --storage-um 50 --bond-um 5"
emit() { printf '%s\t%s\n' "$1" "$2"; }
for K in 120 50 5 0.5; do
  for D in 1.00 0.60; do
    d="$OUT/bondk${K}/dye_T280/d${D}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --bond-k $K --density $D --mr-objective cache-leakage --mr-cold-target-K 280 --out-dir $d"
    d="$OUT/bondk${K}/dual_T280/d${D}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --bond-k $K --density $D --mr-objective cache-leakage --mr-cold-target-K 280 --mr-zone-mode dual --out-dir $d"
  done
done
# P17: the compute die under the hot-spot objective at the 2.00 rung (202 W), microbump bond
d="$OUT/bondk50/peak/d2.00"
emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --bond-k 50 --density 2.00 --mr-dt-max 45 --mr-objective peak --out-dir $d"
