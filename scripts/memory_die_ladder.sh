#!/usr/bin/env bash
# §P0.44 -- a DRAM / HBM die beside, under or on top of the 2.00 W/mm^2 compute die, held under
# the JEDEC 85 C refresh breakpoint (planned at 80 C): what each placement costs the array.
#
#   scripts/memory_die_ladder.sh > results/campaign_queue/running/.memdie.tmp \
#     && mv results/campaign_queue/running/.memdie.tmp results/campaign_queue/memdie.par6.tsv
#
# Placements (examples/mr_comparison.py --memory-die):
#   beside     one wide floorplan: compute die | bare gap | memory banks (2.5D, FIG. 6c)
#   sink-side  memory stack between the compute die and the array on a bond (X4 geometry)
#   far-face   memory stack under the compute die behind the isolation (via field folded in),
#              its own array, a far-face sink of stated K/W (§P0.37 geometry, FIG. 6b)
# Memory: power/dram.py (UNCALIBRATED): --mem-W-per-die at the breakpoint rate, --mem-dies lumped
# into one die element (thickness and series-equivalent k stated on the spec). 100 um cells.
# Predictions: docs/PHASE0_CHECKLIST.md §P0.44 P1-P10, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="${OUT:-$REPO/results/memory_die}"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent --cell-um 100"
# `[!]` --mr-dt-max 45 ALONGSIDE the dye curve (as §P0.37's 2.00 W/mm^2 compute regression): the curve-only
# envelope is AREA-weighted, and the 16 banks (half the footprint beside, the whole storage die
# elsewhere) absorbed half of it while the compute die starved -- "envelope insufficient" on the
# three beside rows of the first launch (results/memory_die_v1_curveonly/). The scalar shapes the
# seed envelope per block (45 W each), so the banks take 16 blocks' worth, not half the die's.
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_idle array_on --array-coverage 1.00 --mr-extractor dye --mr-dt-max 45 --mr-iter 12"
MEM="--mem-banks 4 --mem-target-K 353.15 --mem-iter 8"
VIAS="${VIAS:-10000:5}"     # an HBM-class TSV count through the isolation: k 0.1 -> ~0.85 W/mK
emit() { printf '%s\t%s\n' "$1" "$2"; }
# ---- beside (2.5D): the gap --------------------------------------------------------------------
for G in 500 1000 2000; do
  d="$OUT/beside_gap${G}/n8_w3/d2.00"
  emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --memory-die beside --mem-gap-um $G --mem-dies 8 --mem-W-per-die 3 $MEM --density 2.00 --out-dir $d"
done
# ---- sink-side (X4 geometry): dies x bond k ----------------------------------------------------
for N in 1 8; do
  for KB in 5 50; do
    d="$OUT/sinkside_bondk${KB}/n${N}_w3/d2.00"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --memory-die sink-side --bond-um 5 --bond-k $KB --mem-bond-k $KB --mem-dies $N --mem-W-per-die 3 $MEM --density 2.00 --out-dir $d"
  done
done
# ---- far-face (§P0.37 geometry): isolation k_eff x far-face sink -------------------------------
# k 0.1 stated with the via field (-> ~0.85), k 0.1 with NO vias (the §P0.37 row, not buildable
# for a signalled die), k 5 (underfill / microbump class, vias immaterial)
far() { # $1 tag  $2 iso flags  $3 R  $4 n  $5 w  $6 density
  d="$OUT/farface_${1}_bsink${3}/n${4}_w${5}/d${6}"
  emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --memory-die far-face --iso-um 100 $2 --bottom-sink-r-th $3 --mem-dies $4 --mem-W-per-die $5 $MEM --density $6 --out-dir $d"
}
for R in 1 3 10; do
  far vias "--iso-k 0.1 --iso-vias $VIAS" $R 8 3 2.00
  far k0.1 "--iso-k 0.1" $R 8 3 2.00
  far k5   "--iso-k 5"   $R 8 3 2.00
done
far vias "--iso-k 0.1 --iso-vias $VIAS" 3 1 3 2.00
# ---- 1 W per die (HBM2E-class): the far-face and sink-side verdicts ----------------------------
far vias "--iso-k 0.1 --iso-vias $VIAS" 3 8 1 2.00
d="$OUT/sinkside_bondk5/n8_w1/d2.00"
emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --memory-die sink-side --bond-um 5 --bond-k 5 --mem-bond-k 5 --mem-dies 8 --mem-W-per-die 1 $MEM --density 2.00 --out-dir $d"
# ---- 1.00 W/mm^2 ---------------------------------------------------------------------------------
far vias "--iso-k 0.1 --iso-vias $VIAS" 3 8 3 1.00
d="$OUT/sinkside_bondk5/n8_w3/d1.00"
emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --memory-die sink-side --bond-um 5 --bond-k 5 --mem-bond-k 5 --mem-dies 8 --mem-W-per-die 3 $MEM --density 1.00 --out-dir $d"
d="$OUT/beside_gap1000/n8_w3/d1.00"
emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --memory-die beside --mem-gap-um 1000 --mem-dies 8 --mem-W-per-die 3 $MEM --density 1.00 --out-dir $d"
# ---- the compute-die regression at 100 um cells, no memory die (the twin of every row) ---------
d="$OUT/reference_100um/peak/d2.00"
emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density 2.00 --out-dir $d"
