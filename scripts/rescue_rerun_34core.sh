#!/usr/bin/env bash
# Re-run the 34-core rescue at the refreshed envelope AND with second-law recovery.
#
#   scripts/rescue_rerun_34core.sh <jobid>
#
# Reproduces the configuration behind docs/evidence/mr_rescue_cost_34core.json with exactly two
# things changed:
#   h_max 250 -> 1000 W/mm^2 (v91 Table 8.2), picked up from the module default;
#   --recovery-at-junction   (v91 eq. 1.14-1.16, Carnot-bounded LPC recovery).
# dt_max stays at 45 K: v91 supplies no replacement and it is the constraint this case failed on.
#
# `[!]` The geometry comes from array_config.sh via $ARM_ARGS -- stack, pitch, burial, cell size,
# extractor material and --spreading -- exactly as cliff_reverify.sh does it. Do NOT hand-roll
# these. Two earlier attempts at this re-run did, and both produced numbers that were not
# comparable to the recorded evidence: one used the wrong driver entirely (mr_clipping_study, the
# 8-core linpack configuration) at a power point with no steady state, and the next omitted
# --spreading and the burial depth, which left the die 49 K cooler than the recorded control and
# the array with nothing to do.
set -euo pipefail
JOBID="${1:?usage: rescue_rerun_34core.sh <jobid>}"
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/rescue_rerun_34core"
mkdir -p "$OUT"
for D in 1.10 1.15 1.18; do
  d="$OUT/d${D}"
  if [ -f "$d/DONE" ]; then echo "== d${D} done, skip"; continue; fi
  mkdir -p "$d"
  echo "== 34-core d${D}, refreshed envelope + second-law recovery =="
  srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none bash -lc \
    ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
     OMP_NUM_THREADS=1 python examples/mr_comparison.py $ARM_ARGS \
       --cores 34 --density $D --cfm 88 --mr-target-C 92 \
       --spot-min-um 10 --spot-policy dilute --recovery-at-junction \
       --out-dir $d" < /dev/null && touch "$d/DONE"
done
echo "RESCUE RERUN 34CORE DONE"
