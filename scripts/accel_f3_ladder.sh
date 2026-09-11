#!/usr/bin/env bash
# §P0.24 (F3) -- the GA100 accelerator on the direct-die microchannel plate, with the array.
#   scripts/accel_f3_ladder.sh > results/campaign_queue/f3_accel.par4.tsv
#   SHAPE=power ARRAY_ON_ONLY=1 OUT=$REPO/results/accel_f3_power scripts/accel_f3_ladder.sh > results/campaign_queue/f3b.par4.tsv   # §P0.24 part 2
#   SHAPE=power ARRAY_ON_ONLY=1 TOL=1.0 MAXITER=100 OUT=$REPO/results/accel_f3_power_tol1 scripts/accel_f3_ladder.sh > results/campaign_queue/f3c.par4.tsv   # §P0.24 part 3
# Three arms by three invocations (accelerator_study.py takes one stack); 100 um cells; the
# simulated leakage curve; target device with the scalar 45 K; conservation cap on the plan.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/accel_f3}"
COMMON="--leakage-curve simulated --max-iter ${MAXITER:-60} --tol ${TOL:-0.05} --recovery-at-junction $ACCEL_COOLING"
LASER="--mr --mr-target-C 92 --mr-iter 60 --mr-extractor dye --mr-dt-max 45 --array-coverage 1.00 --mr-envelope-shape ${SHAPE:-seed}"
emit() { printf '%s\t%s\n' "$1" "$2"; }
run3() {   # <tag> <point args...>
  local tag="$1"; shift
  if [ -z "${ARRAY_ON_ONLY:-}" ]; then
  emit "$OUT/${tag}_control"    "python examples/accelerator_study.py $ACCEL_CONTROL_ARGS $COMMON $* --out-dir $OUT/${tag}_control"
  emit "$OUT/${tag}_array_idle" "python examples/accelerator_study.py $ACCEL_ARRAY_ARGS $COMMON $* --out-dir $OUT/${tag}_array_idle"
  fi
  emit "$OUT/${tag}_array_on"   "python examples/accelerator_study.py $ACCEL_ARRAY_ARGS $COMMON $LASER $* --out-dir $OUT/${tag}_array_on"
}
for W in 700 1000 1400 2000 2600; do
  run3 "uniform_${W}W" --die-power-W $W
done
for W in 700 1400; do
  run3 "occ8_${W}W"  --die-power-W $W --kernel occupancy --n-active 8  --placement contiguous
  run3 "occ32_${W}W" --die-power-W $W --kernel occupancy --n-active 32 --placement contiguous
done
