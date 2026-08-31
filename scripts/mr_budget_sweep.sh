#!/usr/bin/env bash
# Budget sweep on ONE shape: does aimed efficacy hold as the array is asked for more?
#
#   scripts/mr_budget_sweep.sh <jobid>
#
# Test 6d compared a 3 W measurement against a 42 W one taken on a DIFFERENT die and inferred a
# 1.81x fade. That confounds budget with die. This holds the die, the shape, the pitch and the
# burial fixed and moves only the budget, which is the measurement that settles it.
#
# Fixed: skylake 7-core template, --concentrate 4.0 on L3_4 (the isolated-hotspot case), 200 um
# burial, 50 um cell, 50 um pitch -- the fine end, where the aimed advantage is claimed.
# The target block itself dissipates 16.0 W, so the ladder runs from 0.06x to 2.81x its own power.
set -euo pipefail
JOBID="${1:?usage: mr_budget_sweep.sh <jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
BUDGETS="1 2 3 5 8 12 16 24 32 45"
for W in $BUDGETS; do
  OUT="$REPO/results/mr_budget/w${W}"
  if [ -f "$OUT/tile_pitch.json" ]; then echo "== ${W} W already done, skipping"; continue; fi
  echo "== ${W} W =="
  srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none \
    bash -lc "export PATH=/mnt/nfs01/scratch/jbalma/anaconda3/bin:\$PATH; \
              cd $REPO && OMP_NUM_THREADS=1 python examples/tile_pitch_sweep.py \
                --pitches 50 --no-ideal --concentrate 4.0 --target L3_4 \
                --mr-W $W --burial-um 200 --cell-um 50 \
                --out-dir $OUT" < /dev/null
done
echo "ALL BUDGETS DONE"
