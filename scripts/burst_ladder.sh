#!/usr/bin/env bash
# §P0.25 (F4) -- burst absorption: control vs static array vs modulated array, transient,
# warm-started. 34-core, arm D, 50 um, feed-forward modulation.
#   scripts/burst_ladder.sh > results/campaign_queue/f4_burst.par3.tsv
#   DENSITIES="0.80" FACTORS="2.0" scripts/burst_ladder.sh > results/campaign_queue/f4_smoke.par1.tsv
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/burst"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spec-C 100 --pre-ms 5 --burst-ms 10 --post-ms 10 --slot-ms 1 --steps-per-slot 10 --modulation feedforward --array-coverage 1.00 --mr-dt-max 45"
DENSITIES="${DENSITIES:-0.80 1.00}"
FACTORS="${FACTORS:-1.5 2.0 3.0}"
emit() { printf '%s\t%s\n' "$1" "$2"; }
for D in $DENSITIES; do
  for K in $FACTORS; do
    d="$OUT/d${D}/k${K}"
    emit "$d" "python examples/burst_absorption_study.py --pitch-um ${PITCH_UM} --burial-um ${BURIAL_UM} --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} $POINT $FLAGS --density $D --burst-factor $K --out-dir $d"
  done
done
