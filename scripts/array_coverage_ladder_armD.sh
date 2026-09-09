#!/usr/bin/env bash
# §P0.18 -- the array charged its own footprint: the coverage ladder under ARM D's configuration.
#
#   scripts/array_coverage_ladder_armD.sh > results/array_coverage_armD/joblist.tsv
#   srun --jobid=<id> --overlap -n1 bash -c 'cat results/array_coverage_armD/joblist.tsv | PAR=6 scripts/campaign_inner.sh'
#
# `[!]` Feed the joblist as a FILE read on the node; piping it into srun's stdin truncates it
# silently (measured: 3 of 12 jobs ran and the campaign reported success).
#
# WHAT THIS MEASURES, and what it cannot
# --------------------------------------
# Two gaps, one ladder. (1) The only array-assisted density ceiling on record (§P0.10: 1.60 holds,
# 1.80/2.00 fails) was measured on the pipeline curve with stock accounting; arm D has never run
# the array arm above 1.00 W/mm^2, where the control first diverges. (2) Every recorded array
# result solved tiles filling the cooled surface edge to edge; the device's couplers, waveguides,
# fibre access and monolithic-backside LPC share that footprint with the extractor (v91 Figs.
# 9.1/9.8/9.12), so the emitting fraction is < 1 and has never been swept.
#
# `[!]` Coverage cannot move a CONTROL-arm ceiling -- the control has no array. The flat-die and
# shaped ceilings in RESULTS_REGISTER §1.3 are untouched by construction; do not re-run
# uniform_density_probe.py on this flag, it does not consume it.
#
# Coverage 1.00 runs all three arms. Coverage < 1 runs array_on ONLY: an unpowered gap and an
# unpowered tile are the same 30 um of GaAs, so control and array_idle are identical at every
# coverage and are shared from the 1.00 run rather than re-solved thirty times.
#
# Predictions are in docs/PHASE0_CHECKLIST.md §P0.18.2, written before this was launched.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/array_coverage_armD"
FLAGS="--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent"
POINT="--cores 34 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction"
# `[!]` Extended 3 Sep after the first pass: at full coverage array_on held at EVERY rung to 2.00,
# so the ladder did not bracket the array-assisted ceiling. 2.20-3.00 added to bracket it.
DENSITIES="${DENSITIES:-1.00 1.10 1.20 1.30 1.40 1.50 1.60 1.70 1.80 2.00 2.20 2.40 2.60 3.00}"
COVERAGES="${COVERAGES:-0.75 0.50 0.25}"
emit() { printf '%s\t%s\n' "$1" "$2"; }

# Full coverage, three arms: the array-assisted ceiling under corrected inputs, and the shared
# control / array_idle rows for every other coverage.
for D in $DENSITIES; do
  d="$OUT/c1.00/d${D}"
  emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --array-coverage 1.00 --out-dir $d"
done

# Reduced coverage, array_on only.
for C in $COVERAGES; do
  for D in $DENSITIES; do
    d="$OUT/c${C}/d${D}"
    emit "$d" "python examples/mr_comparison.py $ARM_ARGS $POINT $FLAGS --density $D --array-coverage $C --arms array_on --out-dir $d"
  done
done
