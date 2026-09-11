#!/usr/bin/env bash
# §P0.27.3 -- X3: the dense cluster at the book's utilisation and halos, at MATCHED DIE WATTS.
#
#   scripts/x3_utilisation_ladder.sh > results/campaign_queue/x3_u70.par5.tsv
#
# Three floorplans on ONE grid (100 um cells -- the u70 members are ~1.5x the reference's area and
# the reference's two-die stack at 50 um is already the 366k-unknown measured limit):
#   ref            the recorded 34-core reference, re-run at 100 um (the grid control)
#   d1_exec1_u70   the reference's units at U = 0.70, T = 0.15, 20 um cache halos (utilisation alone)
#   d1_exec0.5_u70 the x0.5 cluster at the same overheads (utilisation + density)
# Rungs: the D1 rungs in WATTS (1.10/1.20/1.60/2.00/2.40 x 101.1 W) for the array arms; the shaped
# control probe at 0.45-1.00 x 101.1 W. --density is W over the member's own area.
# Predictions: docs/PHASE0_CHECKLIST.md §P0.27.3, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/x3_u70"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent --cell-um 100"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_idle array_on --array-coverage 1.00 --mr-extractor dye --mr-dt-max 45"
REF_MM2=101.09708
EV="$REPO/docs/evidence/d1_exec_density_family_u70.json"
emit() { printf '%s\t%s\n' "$1" "$2"; }
member_mm2() { python3 -c "import json;print([m for m in json.load(open('$EV'))['members'] if abs(m['factor']-$1)<1e-9][0]['die_mm2'])"; }
for M in ref d1_exec1_u70 d1_exec0.5_u70; do
  case $M in
    ref) DIR="$REPO/examples/floorplans/outputs"; MM2=$REF_MM2 ;;
    d1_exec1_u70) DIR="$REPO/examples/floorplans/outputs/d1_exec1_u70"; MM2=$(member_mm2 1.0) ;;
    d1_exec0.5_u70) DIR="$REPO/examples/floorplans/outputs/d1_exec0.5_u70"; MM2=$(member_mm2 0.5) ;;
  esac
  TMPL="$DIR/skylake7nm_34core_3_3D-ICE_template.flp"
  for R in 0.45 0.50 0.60 0.70 0.80 0.90 1.00; do
    W=$(python3 -c "print('%.3f'%($R*$REF_MM2))"); D=$(python3 -c "print('%.4f'%($R*$REF_MM2/$MM2))")
    d="$OUT/$M/control/W${W}"
    emit "$d" "python examples/uniform_density_probe.py --flp $TMPL --cores 34 --arms shaped --densities $D $FLAGS --out-dir $d --json-out $d/probe.json"
  done
  for R in 1.10 1.20 1.60 2.00 2.40; do
    W=$(python3 -c "print('%.3f'%($R*$REF_MM2))"); D=$(python3 -c "print('%.4f'%($R*$REF_MM2/$MM2))")
    d="$OUT/$M/array/W${W}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --flp-dir $DIR --density $D --out-dir $d"
  done
done
