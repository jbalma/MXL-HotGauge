#!/usr/bin/env bash
# §P0.37 -- the TWO-SINK gen-3 stack at 100 um cells: the storage die on the compute die's FAR
# face, behind an isolation layer, with its own array.
#
#   scripts/two_sink_ladder.sh > results/campaign_queue/running/.two_sink.tmp \
#     && mv results/campaign_queue/running/.two_sink.tmp results/campaign_queue/two_sink.par6.tsv
#
# Stack (top-down): sink / dye array / compute die (caches dark) / ISOLATION (100 um, k swept) /
# 50 um storage die (the reference's 68 L2/L3 blocks) / the storage die's own array / far face
# a sink of stated K/W (adiabatic has no idle steady state -- see below). Storage-array material: Cr:LiSAF (--mr-zone-mode dual; the
# cold tiles ARE the storage array) or the dye (single). Objective: caches at 280 K, everything
# else at the 92 C hot-spot target -- so the 2.00 W/mm^2 rows are the combined design point.
# Predictions: docs/PHASE0_CHECKLIST.md §P0.37 P1-P7, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
# `[!]` v2 (19 Sep): the first pass (results/two_sink/) used the default cold-zone pattern
# '^(L2|L3)', which ALSO matches the 34 L2Pred_* blocks (the L2 local branch predictor, on the
# compute die): every row spent a constant 13.8 W of the COMPUTE array chasing them to 280 K and
# reported them in the zone's mean / max. The pattern below names the cache blocks only; twelve
# planner iterations because the first pass ended "still building the plan".
# `[!]` v3: v2's pattern '^(L2|L3)_[0-9]' fixed the planner's zone but starved the LEDGER -- the
# bridged L3 aggregate's temperature key is plain 'L3', so cache_leakage_W read 1.0 W idle where
# the die has ~4. '^(L2|L3)(_[0-9]+)?$' names the 68 cache blocks AND the aggregate, not L2Pred.
OUT="${OUT:-$REPO/results/two_sink_v3}"
SPLIT="$REPO/examples/floorplans/outputs/gen3_stack"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent --cell-um 100"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_idle array_on --array-coverage 1.00 --mr-extractor dye --gen3-split $SPLIT --storage-um 50 --two-sink --iso-um 100"
CACHE="--mr-objective cache-leakage --mr-cold-target-K 280 --mr-cold-zone-pattern '^(L2|L3)(_[0-9]+)?\$' --mr-iter 12"
emit() { printf '%s\t%s\n' "$1" "$2"; }
mat_flag() { if [ "$1" = crlisaf ]; then echo "--mr-zone-mode dual"; else echo ""; fi; }

# `[!]` The far face carries a sink in EVERY ladder row (BS K/W over the die footprint, default 3 --
# a passive plate): the smoke point (isok0.1/dye_T280/d1.00, far face adiabatic) showed the idle
# storage die has NO steady state behind the isolation -- L2 runs away -- so the unpowered baseline
# diverges and nothing can be planned from it. That row is kept as evidence.
BS="${BS:-3}"
# P1-P3: the isolation sweep at 1.00 W/mm^2
for K in 0.025 0.1 0.5 5; do
  for M in crlisaf dye; do
    d="$OUT/isok${K}_bsink${BS}/${M}_T280/d1.00"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --iso-k $K --bottom-sink-r-th $BS --density 1.00 $CACHE $(mat_flag $M) --out-dir $d"
  done
done
# P4: a better far-face sink (1 K/W; fan class 0.3 K/W) at k = 0.1 -- a liability at 280 K?
for B in 1 0.3; do
  for M in crlisaf dye; do
    d="$OUT/isok0.1_bsink${B}/${M}_T280/d1.00"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --iso-k 0.1 --bottom-sink-r-th $B --density 1.00 $CACHE $(mat_flag $M) --out-dir $d"
  done
done
# P9 (added after v2): a WORSE far-face sink at the best isolation -- does Cr:LiSAF get its job?
for B in 10 30; do
  for M in crlisaf dye; do
    d="$OUT/isok0.025_bsink${B}/${M}_T280/d1.00"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --iso-k 0.025 --bottom-sink-r-th $B --density 1.00 $CACHE $(mat_flag $M) --out-dir $d"
  done
done
# P6: the combined design point at 2.00 W/mm^2 (compute die at 92 C AND caches at 280 K)
for K in 0.025 0.1 0.5; do
  for M in crlisaf dye; do
    d="$OUT/isok${K}_bsink${BS}/${M}_T280/d2.00"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --iso-k $K --bottom-sink-r-th $BS --density 2.00 $CACHE $(mat_flag $M) --out-dir $d"
  done
done
# P5: the compute die alone under the hot-spot objective at 2.00 (X4's P17 row is the twin)
d="$OUT/isok0.1_bsink${BS}/peak/d2.00"
emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --iso-k 0.1 --bottom-sink-r-th $BS --density 2.00 --mr-dt-max 45 --mr-objective peak --mr-iter 12 --out-dir $d"
# The same correction on the two recorded twins (D3 monolithic and X4 sink-side stack, 100 um
# cells, 1.00 W/mm^2): did the L2Pred blocks inflate "the prize costs the whole die"?
TW="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_idle array_on --array-coverage 1.00 --mr-extractor dye"
for M in crlisaf dye; do
  d="$OUT/twin_monolithic/${M}_T280/d1.00"
  emit "$d" "python examples/mr_comparison.py $ARM_ARGS $TW $FLAGS --density 1.00 $CACHE $(mat_flag $M) --out-dir $d"
  d="$OUT/twin_x4_bondk50/${M}_T280/d1.00"
  emit "$d" "python examples/mr_comparison.py $ARM_ARGS $TW $FLAGS --gen3-split $SPLIT --storage-um 50 --bond-um 5 --bond-k 50 --density 1.00 $CACHE $(mat_flag $M) --out-dir $d"
done
