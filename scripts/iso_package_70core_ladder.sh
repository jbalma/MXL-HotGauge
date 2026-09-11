#!/usr/bin/env bash
# §P0.23.1 (F1b) -- the 70-core die WITH the array: how much compute does the same air-cooled
# package hold when the die is twice the size? 100 um cells (§P0.22.0), arm D, target device.
#   scripts/iso_package_70core_ladder.sh > results/campaign_queue/f1_70core.par4.tsv
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/iso_package_70core"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
ARMS100="--stack auto --pitch-um 500 --burial-um 200 --cell-um 100 --mr-material GAAS --spreading"
POINT="--cores 70 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --array-coverage 1.00 --mr-extractor dye --mr-dt-max 45"
emit() { printf '%s\t%s\n' "$1" "$2"; }
for D in 0.60 0.70; do
  emit "$OUT/d$D" "python examples/mr_comparison.py $ARMS100 $POINT $FLAGS --arms control array_idle array_on --density $D --out-dir $OUT/d$D"
done
for D in 0.80 1.00 1.20 1.60 2.00 2.40; do
  emit "$OUT/d$D" "python examples/mr_comparison.py $ARMS100 $POINT $FLAGS --arms array_idle array_on --density $D --out-dir $OUT/d$D"
done
