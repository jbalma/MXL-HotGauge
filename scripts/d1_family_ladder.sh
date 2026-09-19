#!/usr/bin/env bash
# §P0.22.3 -- D1: the dense-execution-cluster family, measured at MATCHED DIE WATTS.
#
#   scripts/d1_family_ladder.sh > results/campaign_queue/d1.par4.tsv
#
# Two members (execution-unit area x0.5 and x0.25; examples/generate_exec_density_family.py).
# The die shrinks (91.25 / 86.33 mm^2 against 101.10), so every point is placed at the
# reference ladder's WATTS -- the CODESIGN_PLAN §9 invariant -- and --density is W / member mm^2.
#   control (shaped arm, uniform_density_probe): 0.45-0.70 x 101.1 W = 45.5-70.8 W
#   array (mr_comparison, array_idle + array_on, target device, scalar 45 K kept):
#        the 1.10 / 1.20 / 1.60 / 2.00 / 2.40 rungs x 101.1 W = 111-243 W
# 50 um cells as the recorded reference (the members are SMALLER, so they fit).
# Predictions: docs/PHASE0_CHECKLIST.md s.P0.22.3, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
# §P0.34: SHAPE=power re-runs the array rungs under the per-block envelope shape into OUT
# (results/d1_family_power); ARRAY_ONLY=1 skips the control rows (they carry no planner).
OUT="${OUT:-$REPO/results/d1_family}"
SHAPE="${SHAPE:-seed}"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_idle array_on --array-coverage 1.00 --mr-extractor dye --mr-dt-max 45 --mr-envelope-shape $SHAPE"
REF_MM2=101.09708
emit() { printf '%s\t%s\n' "$1" "$2"; }
for F in 0.5 0.25; do
  DIR="$REPO/examples/floorplans/outputs/d1_exec${F}"
  TMPL="$DIR/skylake7nm_34core_3_3D-ICE_template.flp"
  MM2=$(python3 -c "import json;print([m for m in json.load(open('$REPO/docs/evidence/d1_exec_density_family.json'))['members'] if m['factor']==$F][0]['die_mm2'])")
  [ -n "${ARRAY_ONLY:-}" ] || for R in 0.45 0.50 0.55 0.60 0.65 0.70; do
    W=$(python3 -c "print('%.3f'%($R*$REF_MM2))"); D=$(python3 -c "print('%.4f'%($R*$REF_MM2/$MM2))")
    d="$OUT/exec${F}/control/W${W}"
    emit "$d" "python examples/uniform_density_probe.py --flp $TMPL --cores 34 --arms shaped --densities $D $FLAGS --out-dir $d --json-out $d/probe.json"
  done
  for R in 1.10 1.20 1.60 2.00 2.40; do
    W=$(python3 -c "print('%.3f'%($R*$REF_MM2))"); D=$(python3 -c "print('%.4f'%($R*$REF_MM2/$MM2))")
    d="$OUT/exec${F}/array/W${W}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --flp-dir $DIR --density $D --out-dir $d"
  done
done
