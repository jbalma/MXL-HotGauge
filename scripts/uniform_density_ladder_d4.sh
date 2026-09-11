#!/usr/bin/env bash
# §P0.22.1 -- D4: the 70-core die as a falsification test of the 3 Sep predictions
# ("ratios travel, absolute ceilings do not"), plus the 34-core re-run on the SAME grid.
#
#   scripts/uniform_density_ladder_d4.sh > results/d4_joblist.tsv
#   srun --jobid=<id> --overlap -n1 bash -c 'cat results/d4_joblist.tsv | PAR=8 scripts/campaign_inner.sh'
#
# `[!]` 100 um cells, NOT the recorded 50 um. The 70-core control stack at 50 um is 629 k unknowns
# (78.6 k cells x 8 layers) against the toolchain's largest measured factorisation of 366 k
# (leakage_feedback.LARGEST_MEASURED_UNKNOWNS); it does not solve. A coarser grid understates
# peaks on small blocks (METHODS.md s5), so the 34-core reference is re-run at 100 um around its
# own cliffs (uniform 0.85/0.90, shaped 0.60/0.65 at 50 um) and the two dies are compared on
# ONE grid. The recorded 50 um rows are reached only through that matched control.
#
# Arm D (the shipped default since 9 Sep): --leakage-curve simulated --rbb-policy amortized
# --core-other-policy hierarchy-consistent. Stated explicitly anyway, so the joblist says what
# it ran. Predictions: docs/PHASE0_CHECKLIST.md s.P0.22.1, written before this was launched.
set -euo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent --cell-um 100"
FLP70="$REPO/examples/floorplans/outputs/skylake7nm_70core_3_3D-ICE_template.flp"
FLP34="$REPO/examples/floorplans/outputs/skylake7nm_34core_3_3D-ICE_template.flp"
emit() { printf '%s\t%s\n' "$1" "$2"; }

rung() {   # <out-root> <flp> <cores> <arm> <densities...>
  local OUT="$1" FLP="$2" CORES="$3" ARM="$4"; shift 4
  for D in "$@"; do
    emit "$OUT/$ARM/d${D}" "python examples/uniform_density_probe.py --flp $FLP --cores $CORES \
--arms $ARM --densities $D $FLAGS --out-dir $OUT/$ARM/d${D} --json-out $OUT/$ARM/d${D}/probe.json"
  done
}

# The 34-core grid control first: cheap (10 k cells), and it decides whether the rest is readable.
OUT34="$REPO/results/uniform_density_34core_c100_armD"
rung "$OUT34" "$FLP34" 34 uniform 0.80 0.85 0.90 0.95 1.00
rung "$OUT34" "$FLP34" 34 shaped  0.55 0.60 0.65 0.70 0.75

# The 70-core die. Wider than the prediction band on both sides, so a ceiling that moved the
# other way is still bracketed.
OUT70="$REPO/results/uniform_density_70core_armD"
rung "$OUT70" "$FLP70" 70 uniform 0.45 0.50 0.55 0.60 0.65 0.70 0.75 0.80 0.85 0.90 0.95
rung "$OUT70" "$FLP70" 70 shaped  0.30 0.35 0.40 0.45 0.50 0.55 0.60 0.65 0.70
