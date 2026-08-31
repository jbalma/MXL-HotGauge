#!/usr/bin/env bash
# The concentration test: the same density ladder on the real power map and on a flat one.
#
#   scripts/uniform_density_ladder.sh > /tmp/ud.tsv
#   srun --jobid=<id> --overlap -n1 scripts/campaign_inner.sh < /tmp/ud.tsv
#   python examples/uniform_density_report.py
#
# One slurm step, one worker per point. Serially this is hours -- a single point is a full
# leakage-feedback convergence with damping verification over 1126 blocks -- and the points are
# independent, so there is no reason to pay for that.
#
# See examples/uniform_density_probe.py for what the two arms are and how to read the result.
set -euo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/uniform_density"
emit() { printf '%s\t%s\n' "$1" "$2"; }

for ARM in shaped uniform; do
  for D in 0.60 0.80 1.00 1.20 1.60 2.00 2.40 2.80; do
    emit "$OUT/$ARM/d${D}" "python examples/uniform_density_probe.py --arms $ARM \
--densities $D --out-dir $OUT/$ARM/d${D} --json-out $OUT/$ARM/d${D}/probe.json"
  done
done
