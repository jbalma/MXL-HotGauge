#!/usr/bin/env bash
# Does the budget cliff survive leakage feedback?
#
#   scripts/mr_budget_leakage_sweep.sh <jobid>
#
# Test 6e measured the cliff on LINEAR solves with no leakage feedback -- the same basis as the
# tile-pitch study it extends. Feedback should move it, and it is not obvious which way:
#
#   * cooling cuts leakage, so each watt removed takes more heat out of the die than it lifts,
#     which should raise efficacy and push the cliff later;
#   * but leakage is steepest at the hottest block, so the aimed target sheds power faster than
#     its neighbours as it cools -- which brings the runner-up level SOONER and should pull the
#     cliff earlier.
#
# The two run opposite. This measures which wins, on a coupled solve with the calibrated model.
#
# The plan is driven to a deliberately unreachable target so the BUDGET binds at every rung
# rather than the target; the aggregator reads the heat actually removed, not the cap.
set -euo pipefail
JOBID="${1:?usage: mr_budget_leakage_sweep.sh <jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
BUDGETS="${BUDGETS:-0.5 1 2 3 5 8 12 18 25}"
POWER="${POWER:-65}"
for W in $BUDGETS; do
  OUT="$REPO/results/mr_budget_leak/w${W}"
  if [ -f "$OUT/mr_study.json" ]; then echo "== ${W} W done, skip"; continue; fi
  mkdir -p "$OUT"
  echo "== budget ${W} W (leakage feedback ON) =="
  srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none \
    bash -lc "export PATH=/mnt/nfs01/scratch/jbalma/anaconda3/bin:\$PATH; \
              cd $REPO && OMP_NUM_THREADS=1 python examples/mr_clipping_study.py \
                --powers $POWER --r-th 0.3 --mr-target-C 40 --mr-budget-W $W \
                --pitch-um 50 --cell-um 50 --stack spec:package=direct_die,mr=GAAS \
                --out-dir $OUT" < /dev/null
done
echo "ALL LEAKAGE BUDGETS DONE"
