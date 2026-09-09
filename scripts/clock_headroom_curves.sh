#!/usr/bin/env bash
# The §P2.6 clock-headroom search, re-run across all three leakage curves (§P0.15).
#
#   scripts/clock_headroom_curves.sh > /tmp/chc.tsv
#   srun --jobid=<id> --overlap -n1 scripts/campaign_inner.sh < /tmp/chc.tsv
#
# WHY. §P0.14 found the density ladder moved by exactly one rung on one arm when the leakage
# curve was swapped, and explained why the move was small: the ladder is a **divergence test**,
# and divergence is decided by d(ln P_leak)/dT at one temperature. This study is the one recorded
# result whose criterion is a **temperature limit** instead -- it asks for the highest clock whose
# coupled solve still holds 100 C -- so a curve that is steeper through the *whole* operating band
# eats headroom continuously rather than only at a cliff. Prediction on record: this should move
# MORE than the ladder did. If it does not, say so and withdraw the prediction.
#
# `[!]` CONTROL ARM ONLY, and that is deliberate. The MR arms add a planner whose target is itself
# a temperature, so an arm difference would mix "the curve changed the clock" with "the curve
# changed what the planner had to do". One thing varies here: the leakage curve.
#
# The R_th ladder is the one in docs/CLOCK_HEADROOM.md, so the `pipeline` rows are directly
# comparable to the recorded table -- which also makes them a check that --leakage-curve is
# additive at its default.
set -euo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/clock_headroom_curves"
emit() { printf '%s\t%s\n' "$1" "$2"; }

for CURVE in pipeline simulated simulated-gidl-off; do
  for RTH in 1.0 0.5 0.3 0.1 0.05 0.02; do
    D="$OUT/$CURVE/rth${RTH}"
    emit "$D" "python examples/clock_headroom.py --arms control --r-th $RTH \
--leakage-curve $CURVE --out-dir $D"
  done
done
