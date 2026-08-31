#!/usr/bin/env bash
# The RBB bracket: the SAME density ladder run under both placement policies.
#
#   scripts/rbb_bracket.sh > /tmp/rbb_bracket.tsv
#   srun --jobid=<id> --overlap -n1 scripts/campaign_inner.sh < /tmp/rbb_bracket.tsv
#
# Why a bracket and not a switch. Amortizing the results-broadcast bus changes every recorded
# thermal result in the project, so the size of the change has to be on the record BEFORE the
# catalogue is re-run -- otherwise "the numbers moved" and "the numbers are different because
# the study changed" are indistinguishable afterwards. Same points, same everything else, one
# flag apart.
#
# Two questions, and the ladder answers both at once:
#   1. how far do CONVERGING results move (1.20-1.80, where the array already holds)
#   2. does the CEILING move (2.00+, where every run diverged on RBB_0 at thousands of kelvin)
#
# `[!]` A prediction worth writing down before the runs land, because it is falsifiable and it
# is NOT what the evidence files assume: amortizing RBB may not raise the ceiling at all. With
# the bus removed as a powered block, the hottest block by DENSITY on this trace becomes iBuf_0
# at ~510 W/mm^2 against RBB_0's ~1444. iBuf did not run away before, and the plausible reason
# is geometry rather than density -- it is 1.3 um across against RBB's 13.4, so it spreads
# laterally an order of magnitude better. If that reading is right the ceiling rises; if the
# gate is density alone, iBuf simply takes over and the ceiling does not move. Either outcome
# is worth more than the assumption.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/rbb_bracket"
emit() { printf '%s\t%s\n' "$1" "$2"; }

for POL in stock amortized; do
  for D in 1.20 1.60 1.80 2.00 2.40; do
    emit "$OUT/$POL/d${D}" "python examples/mr_comparison.py $ARM_ARGS --cores 34 --density $D \
--cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction \
--rbb-policy $POL --out-dir $OUT/$POL/d${D}"
  done
done
