#!/usr/bin/env bash
# §P0.26 part 2 -- the clock search from the ladders' operating points (--density at the trace clock).
#   scripts/clock_f1c_density.sh > results/campaign_queue/f1c_density.par3.tsv
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/clock_f1c_density"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --arms control array_idle array_on --thermal-limit-C 100 --mr --mr-target-margin-K 8 --mr-dt-max 45 --array-coverage 1.00 --recovery-at-junction --f-lo 2.0 --f-tol 0.05"
emit() { printf '%s\t%s\n' "$1" "$2"; }
for D in 0.78 1.00 1.20; do
  emit "$OUT/spice_d$D" "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --vf-source spice --f-hi 5.0 --density $D --out-dir $OUT/spice_d$D"
done
emit "$OUT/table_d1.00"       "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --vf-source table --f-hi 5.0 --density 1.00 --out-dir $OUT/table_d1.00"
emit "$OUT/spice_above_d1.00" "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --vf-source spice --f-hi 6.5 --above-vf-table --density 1.00 --out-dir $OUT/spice_above_d1.00"
