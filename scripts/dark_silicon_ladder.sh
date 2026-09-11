#!/usr/bin/env bash
# §P0.23.2 (F2) -- dark-silicon recovery: the active-core fraction the die can light at a given
# per-core power, control vs unpowered array vs laser. 34-core, 50 um, arm D, target device.
#   scripts/dark_silicon_ladder.sh > results/campaign_queue/f2_dark.par6.tsv
# The active cores are the LOWEST-INDEX ones (a contiguous block on the tiler's layout): the
# thermally worst case, deliberately.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/dark_silicon"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --array-coverage 1.00 --mr-extractor dye --mr-dt-max 45 --activity mixed --background 0.25 --activity-scope iso-per-core"
emit() { printf '%s\t%s\n' "$1" "$2"; }
for D in 0.78 1.00 1.20 1.50; do
  for F in 0.25 0.50 0.75 1.00; do
    d="$OUT/d${D}/f${F}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --active-fraction $F --out-dir $d"
  done
done
