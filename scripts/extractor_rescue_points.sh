#!/usr/bin/env bash
# §P0.19 -- the extractor's own cooling curve as the lift limit, on the rescue points.
#
#   scripts/extractor_rescue_points.sh > results/extractor_armD/joblist.tsv
#   srun --jobid=<id> --overlap -n1 bash -c 'cat results/extractor_armD/joblist.tsv | PAR=6 scripts/campaign_inner.sh'
#
# Arm D, 34-core, 88 CFM, target 92 C, full coverage, array_on only (control and idle are
# unchanged by the extractor and shared from results/array_coverage_armD/c1.00).
#
# `[!]` TWO VARIANTS PER EXTRACTOR, and they answer different questions:
#   dt45  -- the scalar 45 K cap KEPT and the extractor curve added as a further cap. The envelope
#            keeps the recorded (sensitivity-weighted) shape, so the minimum plan is comparable
#            with P0.18.2 and any difference is the extractor's physics. This is the clean test.
#   dtnone -- the scalar cap dropped; the extractor curve alone bounds the envelope. The envelope
#            is then area-weighted and the descent lands on a differently-shaped, dearer plan
#            (+32 % at 1.30 in the smoke test). Reported, and NOT compared with P0.18.2's Q.
# Plus the converged energy cap (dye, dt45) at the rungs where P0.18.2 found the over-pull.
# `[!]` The first pass (results/extractor_armD_blockcap_superseded/) applied the cap per BLOCK,
# which reshaped the envelope for small blocks; the cap now applies per TILE at delivery and the
# block plan keeps its recorded shape. DTNONE=1 re-enables the curve-only variant.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/extractor_armD"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --arms array_on --array-coverage 1.00"
DENSITIES="${DENSITIES:-1.15 2.00 2.40 2.60}"
EXTRACTORS="${EXTRACTORS:-dye gaas-enhanced gaas-retuned-enhanced}"
emit() { printf '%s\t%s\n' "$1" "$2"; }
for X in $EXTRACTORS; do
  for D in $DENSITIES; do
    d="$OUT/${X}_dt45/d${D}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --mr-extractor $X --mr-dt-max 45 --out-dir $d"
    if [ "${DTNONE:-0}" = 1 ]; then
      d="$OUT/${X}_dtnone/d${D}"
      emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --mr-extractor $X --out-dir $d"
    fi
  done
done
for D in 2.40 2.60 3.00; do
  d="$OUT/dye_dt45_converged/d${D}"
  emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --mr-extractor dye --mr-dt-max 45 --mr-energy-cap converged --out-dir $d"
done
