#!/usr/bin/env bash
# The §P0.11 density ladder on the GIDL-OFF bracket of the simulated leakage curve (§P0.14).
#
#   scripts/uniform_density_ladder_gidl_off.sh > /tmp/uds_gidl.tsv
#   srun --jobid=<id> --overlap -n1 scripts/campaign_inner.sh < /tmp/uds_gidl.tsv
#   python examples/density_ceiling_curve_compare.py \
#       --simulated-base results/uniform_density_gidl_off
#
# WHY run the bracket after all. scripts/uniform_density_ladder_simulated.sh declined to, on the
# argument that GIDL is a cold-end mechanism and the two brackets differ by only 14-15% at
# 450-500 K -- i.e. that the ladder's verdict is decided in the hot tail where the bracket is
# nearly closed. §P0.14 measured where the flat-die ceiling is actually decided and it is
# **310-330 K**, not the hot tail: a die at the ceiling is the one that *fails to leave* the cold
# band, so the runaway/no-runaway split is set by the slope right above ambient. That is exactly
# where GIDL is load-bearing and where the two brackets are furthest apart. The earlier argument
# was correct about the physics of GIDL and wrong about which temperatures the experiment probes.
#
# ASAP7 is a *predictive* PDK: its GIDL coefficients are a model choice, not a measurement, so
# neither bracket is "the" answer. The pair of ladders is the result.
#
# Everything else is IDENTICAL to scripts/uniform_density_ladder_simulated.sh -- same die, same
# package, same RBB policy, same densities, same arms, same extended top rung. One input changed.
set -euo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/uniform_density_gidl_off"
emit() { printf '%s\t%s\n' "$1" "$2"; }

for ARM in shaped uniform; do
  for D in 0.60 0.80 1.00 1.20 1.60 2.00 2.40 2.80 3.20 4.00; do
    emit "$OUT/$ARM/d${D}" "python examples/uniform_density_probe.py --arms $ARM \
--densities $D --leakage-curve simulated-gidl-off --out-dir $OUT/$ARM/d${D} \
--json-out $OUT/$ARM/d${D}/probe.json"
  done
done
