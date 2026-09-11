#!/usr/bin/env bash
# §P0.22.2 -- D3: the cache-leakage planner objective, smoke-tested on the MONOLITHIC 34-core die.
#
#   scripts/d3_objective_smoke.sh > results/d3_objective/joblist.tsv
#   srun --jobid=<id> --overlap -n1 bash -c 'cat results/d3_objective/joblist.tsv | PAR=4 scripts/campaign_inner.sh'
#
# Arm D, 34-core, 88 CFM, hot-spot target 92 C, full coverage, target device (rung 6 dye), arms
# array_idle + array_on (the control is unchanged by the objective and diverges at 1.00 anyway).
# The idle row is the reference every objective row is a difference against: at 1.00 W/mm^2 it
# holds at 89.1 C with 0 W removed, so nothing is above the hot-spot target and every watt the
# cache objective spends is spent on the caches' account.
#
# Variants per density and cold target:
#   peak    -- the recorded objective; regression row (P1: reproduces the c1.00 ladder to the digit)
#   dt45    -- cache objective, scalar 45 K lift kept (P3: lift-bound)
#   dtnone  -- cache objective, the extractor curve alone (P2 at 280 K: conservation-bound;
#              P4/P5 at 300 K: the cost of the monolithic route and the leakage it buys)
#   dual    -- cache objective, curve only, Cr:LiSAF on the cache tiles (P6: extractor-bound)
# Predictions: docs/PHASE0_CHECKLIST.md s.P0.22.2, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/d3_objective"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_idle array_on --array-coverage 1.00 --mr-extractor dye"
DENSITIES="${DENSITIES:-1.00 0.60}"
TARGETS="${TARGETS:-280 300}"
emit() { printf '%s\t%s\n' "$1" "$2"; }
for D in $DENSITIES; do
  d="$OUT/peak/d${D}"
  emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --mr-dt-max 45 --mr-objective peak --out-dir $d"
  for T in $TARGETS; do
    d="$OUT/dt45_T${T}/d${D}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --mr-dt-max 45 --mr-objective cache-leakage --mr-cold-target-K $T --out-dir $d"
    d="$OUT/dtnone_T${T}/d${D}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --mr-objective cache-leakage --mr-cold-target-K $T --out-dir $d"
    d="$OUT/dual_T${T}/d${D}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --mr-objective cache-leakage --mr-cold-target-K $T --mr-zone-mode dual --out-dir $d"
  done
done
