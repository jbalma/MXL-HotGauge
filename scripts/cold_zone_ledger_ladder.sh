#!/usr/bin/env bash
# §P0.45 -- where a cold memory zone pays: §P0.37's two-sink ledger on the HP trace and on the
# HP / short-channel / 4x-L3 trace (linpack_3.8GHz_hpx4nolc), at the 1.00- and 2.00-equivalent
# points (MATCHED ACTIVITY for the hot-end trace: D1 / D2 from the build's printed dynamic power),
# cache-leakage objective at 280 K against the peak objective (the alternative). --mr-dt-max 80 on
# every row (the §P0.44 lesson: curve-only the envelope is area-weighted).
#
#   D1=... D2=... scripts/cold_zone_ledger_ladder.sh > results/campaign_queue/running/.cz.tmp && mv ... czl.par4.tsv
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/cold_zone_ledger}"
SPLIT="$REPO/examples/floorplans/outputs/gen3_stack"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent --cell-um 100"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_idle array_on --array-coverage 1.00 --mr-extractor dye --mr-dt-max 80 --mr-iter 12 --gen3-split $SPLIT --storage-um 50 --two-sink --iso-um 100 --bottom-sink-r-th 3"
CACHE="--mr-objective cache-leakage --mr-cold-target-K 280 --mr-cold-zone-pattern '^(L2|L3)(_[0-9]+)?\$'"
PEAK="--mr-objective peak --mr-cold-zone-pattern '^(L2|L3)(_[0-9]+)?\$'"
HPX="$REPO/mcpat_runs/7nm/linpack_3.8GHz_hpx4nolc"
# `[!]` EXTRA="--mr-envelope-shape power" (OUT=.../cold_zone_ledger_power): the seed envelope is
# UNIFORM per block, so under full capability the storage array's share lands 0.35 W on every cache
# block regardless of size -- the large L3 blocks (which leak the most on the hot-end trace) are
# under-served and run away while the small ones are over-cooled ("envelope insufficient" on the
# first two hpx4nolc rows). The per-block shape caps each block at its OWN dissipation.
EXTRA="${EXTRA:-}"
POINT="$POINT $EXTRA"
D1="${D1:?matched-activity density for the 1.00 point}"; D2="${D2:?matched-activity density for the 2.00 point}"
emit() { printf '%s\t%s\n' "$1" "$2"; }
for K in 0.025 0.1; do
  for OBJ in cache peak; do
    [ $OBJ = cache ] && O="$CACHE" || O="$PEAK"
    for D in 1.00 2.00; do
      d="$OUT/hp_isok${K}/${OBJ}/d${D}"
      emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --iso-k $K --density $D $O --out-dir $d"
    done
    for D in $D1 $D2; do
      d="$OUT/hpx4nolc_isok${K}/${OBJ}/d${D}"
      emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --trace-dir $HPX --iso-k $K --density $D $O --out-dir $d"
    done
  done
done
