#!/usr/bin/env bash
# §P0.31 part 2 -- the clock search on the GENERALIZED f_max model: three arms, arm D, the
# reliability-budgeted V_max at the cooled temperature, the per-block envelope shape, the target
# device's cap. Every row names its limiter (thermal / reliability:<mech> / device / sweep_end)
# and its period's composition (gate / wire / skew / overhead).
#   scripts/clock_fmax.sh > results/campaign_queue/clock_fmax.par3.tsv
# Predictions: docs/PHASE0_CHECKLIST.md §P0.31, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/clock_fmax}"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
# --f-hi 5.0 (8.0 for the 10-FO4 pipeline): above the device's peak clock, so the search's top is never the answer
POINT="--cores 34 --cfm 88 --thermal-limit-C 100 --mr --mr-dt-max 45 --array-coverage 1.00 --recovery-at-junction --mr-extractor dye --mr-envelope-shape power --f-lo 2.0 --f-tol 0.05"
emit() { printf '%s\t%s\n' "$1" "$2"; }
# (a) the reference ladder's operating points, three arms, the 92 C target (spec - 8 K)
for D in 0.78 1.00 1.20; do
  emit "$OUT/qual_d$D" "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --arms control array_idle array_on --mr-target-margin-K 8 --vf-source fmax --f-hi 5.0 --density $D --out-dir $OUT/qual_d$D"
done
# (b) the target as a co-design knob: the array holds the die cooler and the budget buys supply
for D in 1.00 1.20; do
  for T in 75 60; do
    emit "$OUT/qual_d${D}_T$T" "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --arms array_on --mr-target-C $T --vf-source fmax --f-hi 5.0 --density $D --out-dir $OUT/qual_d${D}_T$T"
  done
done
# (c) what the pipeline buys: a Pentium-4-class 10-FO4 stage on the same device, three arms
emit "$OUT/qual_d1.00_N10" "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --arms control array_idle array_on --mr-target-margin-K 8 --vf-source fmax:N=10 --f-hi 8.0 --density 1.00 --out-dir $OUT/qual_d1.00_N10"
# (d) the other reading of the budget: the native die's own lifetime is the reference (X1)
emit "$OUT/native_d1.00" "python examples/clock_headroom.py $ARM_ARGS $POINT $FLAGS --arms control array_on --mr-target-margin-K 8 --vf-source fmax:ref=native --f-hi 5.0 --density 1.00 --out-dir $OUT/native_d1.00"
