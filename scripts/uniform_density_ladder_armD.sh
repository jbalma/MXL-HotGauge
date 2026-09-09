#!/usr/bin/env bash
# §P0.17 -- the density ladder under ARM D's configuration.
#
#   scripts/uniform_density_ladder_armD.sh > /tmp/joblist.tsv
#   srun --jobid=<id> --overlap -n1 bash -c 'cat /tmp/joblist.tsv | PAR=14 scripts/campaign_inner.sh'
#
# §P0.16's four-arm re-run deliberately did NOT restate the density ceiling: its points are
# heterogeneous catalogue operating points, not a ladder, and §P0.11's Gini-0 arm is not among them.
# This is the ladder itself, under the best available physics:
#
#     --leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent
#
# `[+]` All three flags are CONSUMED here -- checked before spending the run, per the
# tile_pitch_sweep lesson (it holds no leakage model, so --leakage-curve there is a no-op).
# `uniform_density_probe.py` takes all three, and derives its die-wide leak_fraction from the split:
# 0.3860 under `stock`, 0.4883 under `hierarchy-consistent`, a 1.27x rise.
#
# `[!]` The ladder is deliberately WIDER than the predicted band. §P0.17 predicts the uniform arm
# lands at 0.70-0.85, below the simulated curve's recorded 0.90-0.95 -- but a ladder that only spans
# the prediction cannot falsify it. The uniform arm runs 0.60-1.15 and the shaped arm 0.35-0.80, so
# a ceiling that moved UP is still bracketed.
set -euo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/uniform_density_armD"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
emit() { printf '%s\t%s\n' "$1" "$2"; }

rung() {   # <arm> <densities...>
  local ARM="$1"; shift
  for D in "$@"; do
    emit "$OUT/$ARM/d${D}" "python examples/uniform_density_probe.py --arms $ARM \
--densities $D $FLAGS --out-dir $OUT/$ARM/d${D} --json-out $OUT/$ARM/d${D}/probe.json"
  done
}

rung uniform 0.60 0.65 0.70 0.75 0.80 0.85 0.90 0.95 1.00 1.05 1.10 1.15
rung shaped  0.35 0.40 0.45 0.50 0.55 0.60 0.65 0.70 0.75 0.80
