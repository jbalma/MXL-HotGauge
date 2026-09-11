#!/usr/bin/env bash
# §P0.26 (F1c) -- the clock as the free variable: three arms, arm D, the SPICE V/F curve.
#   scripts/clock_f1c.sh > results/campaign_queue/f1c_clock.par2.tsv
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/clock_f1c"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --arms control array_idle array_on --vf-source spice --thermal-limit-C 100 --mr --mr-target-margin-K 8 --mr-dt-max 45 --array-coverage 1.00 --recovery-at-junction --f-lo 2.0 --f-tol 0.05"
emit() { printf '%s\t%s\n' "$1" "$2"; }
emit "$OUT/cfm88"             "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --f-hi 5.0 --out-dir $OUT/cfm88"
emit "$OUT/cfm88_above_table" "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --f-hi 6.5 --above-vf-table --out-dir $OUT/cfm88_above_table"
