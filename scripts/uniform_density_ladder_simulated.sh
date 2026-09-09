#!/usr/bin/env bash
# The §P0.11 density ladder, re-run on the SIMULATED leakage curve (§P0.13).
#
#   scripts/uniform_density_ladder_simulated.sh > /tmp/uds.tsv
#   srun --jobid=<id> --overlap -n1 scripts/campaign_inner.sh < /tmp/uds.tsv
#   python examples/uniform_density_report.py \
#       --base results/uniform_density_simulated \
#       --json-out docs/evidence/uniform_density_probe_simulated.json
#
# WHY re-run it. P0.11 found the flat-die ceiling at 1.0-1.2 W/mm^2 and P0.12 flagged that it was
# solved on a leakage curve whose hot tail is ~6x too steep. P0.13 measured the tail: at 500 K the
# pipeline says 5820x the 330 K leakage and the simulator says 123x. **A gentler tail runs away
# LATER**, so the ceiling should move UP. How far is the question this campaign answers, and it is
# the difference between "1.0 W/mm^2 is physics" and "1.0 W/mm^2 was an artefact of CACTI".
#
# `[!]` ONE ARM PAIR, ONE CURVE. Only `--leakage-curve simulated` is run, not the GIDL-off
# bracket. GIDL dominates the COLD end (98% of leakage at 200 K) and is nearly absent at the hot
# end where a ceiling lives: the two brackets differ by 14-15% at 450-500 K, against a ladder
# whose verdict is a bracket 0.20 W/mm^2 wide. Running it would double the cost to resolve a
# difference the experiment cannot see. If the ceiling lands on a rung boundary, revisit that.
#
# Everything else is IDENTICAL to scripts/uniform_density_ladder.sh -- same die, same package,
# same RBB policy, same densities, same arms. One input changed, which is the whole point.
set -euo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/uniform_density_simulated"
emit() { printf '%s\t%s\n' "$1" "$2"; }

# The ladder is extended past the original 2.80 top rung: if the ceiling moves up as predicted,
# the old ladder would report "never failed" and the run would be inconclusive.
for ARM in shaped uniform; do
  for D in 0.60 0.80 1.00 1.20 1.60 2.00 2.40 2.80 3.20 4.00; do
    emit "$OUT/$ARM/d${D}" "python examples/uniform_density_probe.py --arms $ARM \
--densities $D --leakage-curve simulated --out-dir $OUT/$ARM/d${D} \
--json-out $OUT/$ARM/d${D}/probe.json"
  done
done
