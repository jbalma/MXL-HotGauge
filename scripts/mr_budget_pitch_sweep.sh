#!/usr/bin/env bash
# Does the budget cliff move with tile pitch?
#
#   scripts/mr_budget_pitch_sweep.sh <jobid>
#
# Test 6e found efficacy flat to 16 W at 50 um pitch and then a cliff, caused by the aimed block
# ceasing to be the die peak. A coarse tile spans the target AND its neighbours, so it cools the
# runner-up as well -- which should push the cliff later or remove it, at the cost of starting
# lower. If so, fine and coarse pitch are not better and worse but a genuine trade, and the
# crossing point is a design number rather than a preference.
#
# Everything except pitch and budget is held: skylake 7-core template, --concentrate 4.0 on L3_4,
# 200 um burial, 50 um cell. The target block dissipates 16.0 W.
set -euo pipefail
JOBID="${1:?usage: mr_budget_pitch_sweep.sh <jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
PITCHES="${PITCHES:-200 500 2000}"
BUDGETS="${BUDGETS:-1 2 3 5 8 12 16 24 32 45}"
for P in $PITCHES; do
  for W in $BUDGETS; do
    OUT="$REPO/results/mr_budget/p${P}/w${W}"
    if [ -f "$OUT/tile_pitch.json" ]; then echo "== p${P} ${W}W done, skip"; continue; fi
    echo "== pitch ${P} um, ${W} W =="
    srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none \
      bash -lc "export PATH=/mnt/nfs01/scratch/jbalma/anaconda3/bin:\$PATH; \
                cd $REPO && OMP_NUM_THREADS=1 python examples/tile_pitch_sweep.py \
                  --pitches $P --no-ideal --concentrate 4.0 --target L3_4 \
                  --mr-W $W --burial-um 200 --cell-um 50 \
                  --out-dir $OUT" < /dev/null
  done
done
echo "ALL PITCH x BUDGET DONE"
