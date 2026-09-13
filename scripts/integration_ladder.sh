#!/usr/bin/env bash
# §P0.28 -- the integration ladder for the MXL-006 update: burial depth x tile pitch on the
# reference die, 100 um cells (compare with results/x3_u70/ref/array/ at 200 um / 500 um).
#   scripts/integration_ladder.sh > results/campaign_queue/integration.par6.tsv
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/integration"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent --cell-um 100"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --array-coverage 1.00 --mr-extractor dye --mr-dt-max 45"
emit() { printf '%s\t%s\n' "$1" "$2"; }
run() { # burial pitch density arms
  local d="$OUT/b$1/p$2/d$3"
  emit "$d" "python examples/mr_comparison.py --stack auto --pitch-um $2 --burial-um $1 --cell-um 100 --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} $POINT $FLAGS --density $3 --arms $4 --out-dir $d"
}
for B in 100 50 20; do
  for P in 500 200; do
    for D in 1.20 2.00 2.40 2.60 3.00; do run $B $P $D array_on; done
  done
  run $B 500 1.20 array_idle
done
for D in 1.20 2.00 2.40 2.60 3.00; do run 200 200 $D array_on; done
for D in 2.60 3.00; do run 200 500 $D array_on; done
run 200 500 1.20 array_idle
