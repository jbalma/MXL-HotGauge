#!/usr/bin/env bash
# The density ladder REFINED around each curve's cliff, on all three curves (§P0.15).
#
#   scripts/uniform_density_ladder_fine.sh > /tmp/udf.tsv
#   srun --jobid=<id> --overlap -n1 scripts/campaign_inner.sh < /tmp/udf.tsv
#
# WHY. The coarse ladder's rungs are 0.20 W/mm^2 apart, so §P0.14's headline -- "the ceiling moves
# DOWN one rung" -- resolves the move only to "somewhere between 0.20 and 0.40 W/mm^2", and the
# only sub-rung evidence is peak temperatures at the holding points. §P0.15's GIDL-off ladder makes
# that worse, not better: it puts the uniform arm's cliff two coarse rungs above the GIDL-on one,
# and a two-rung claim with 0.20 W/mm^2 rungs is a claim about an interval, not a number.
#
# Each curve gets 0.05 W/mm^2 points spanning ITS OWN measured bracket, so every point is inside a
# region where the answer is already known to change. The brackets, from the coarse ladders:
#
#   curve               shaped: holds -> fails      uniform: holds -> fails
#   pipeline            0.60 -> 0.80                1.00 -> 1.20
#   simulated           0.60* -> 0.80               0.80 -> 1.00
#   simulated-gidl-off  (none) -> 0.60              0.80 -> 1.00
#
#   * `[!]` the simulated shaped 0.60 point is flagged UNCONVERGED, which is neither a hold nor a
#     failure. Its bracket is refined anyway: if the fine points below it converge, they give the
#     arm a demonstrable hold it currently does not have; if they do not, that is worth knowing
#     before anyone quotes 0.60 as a hold on this curve.
#
# `[!]` PASS 2 (the second block below) was added after the coarse GIDL-off ladder finished and
# moved two of its own brackets. The first pass placed the GIDL-off points from a PARTIAL coarse
# ladder -- 16 of 20 points, with the four slowest still running -- and put all six of them above
# a cliff that turned out to be below them. They cost little (a point far above the cliff diverges
# quickly; the expensive points are the ones that converge) and they are kept, because "0.85 to
# 1.50 all diverge" is a real if unsurprising row. The lesson is cheaper than the six solves:
# **do not site a refinement off an unfinished ladder** -- the points still running are exactly
# the ones nearest the cliff, which is the only region a refinement cares about.
#
# The script is resumable via campaign_inner's DONE marker, so re-running it adds only the new
# points.
set -euo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
emit() { printf '%s\t%s\n' "$1" "$2"; }

fine() {   # <curve> <outdir-name> <arm> <densities...>
  local CURVE="$1" NAME="$2" ARM="$3"; shift 3
  local OUT="$REPO/results/${NAME}_fine"
  for D in "$@"; do
    emit "$OUT/$ARM/d${D}" "python examples/uniform_density_probe.py --arms $ARM \
--densities $D --leakage-curve $CURVE --out-dir $OUT/$ARM/d${D} \
--json-out $OUT/$ARM/d${D}/probe.json"
  done
}

fine pipeline           uniform_density           shaped  0.65 0.70 0.75
fine pipeline           uniform_density           uniform 1.05 1.10 1.15
fine simulated          uniform_density_simulated shaped  0.65 0.70 0.75
fine simulated          uniform_density_simulated uniform 0.85 0.90 0.95
fine simulated-gidl-off uniform_density_gidl_off  shaped  0.85 0.90 0.95
fine simulated-gidl-off uniform_density_gidl_off  uniform 1.30 1.40 1.50

# --- PASS 2: sited off the FINISHED coarse ladders (see the note above) ---
# GIDL-off shaped fails at the ladder's own bottom rung, so its cliff is below 0.60 and the coarse
# ladder never bracketed it at all. GIDL-off uniform brackets 0.80 -> 1.00, same as GIDL-on.
fine simulated-gidl-off uniform_density_gidl_off  shaped  0.45 0.50 0.55
fine simulated-gidl-off uniform_density_gidl_off  uniform 0.85 0.90 0.95
# The GIDL-on shaped arm has no demonstrable hold anywhere: 0.60 is unconverged and 0.65 diverges.
fine simulated                 uniform_density_simulated shaped  0.45 0.50 0.55
