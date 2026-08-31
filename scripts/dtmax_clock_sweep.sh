#!/usr/bin/env bash
# Sustainable clock with and without the array, as a function of dt_max.
#
#   scripts/dtmax_clock_sweep.sh <jobid>
#
# Addresses the two outstanding blockers at once, without inventing a number:
#
#  1. dt_max has no v91 source. Rather than guess it, SWEEP it. The deliverable becomes
#     "clock gain vs available temperature lift", which is a parametric result the device team can
#     read their own answer off -- and it is strictly more useful than a point estimate would be.
#
#  2. The catalogue has never entered the frequency-limited regime. clock_headroom.py searches for
#     the SUSTAINABLE CLOCK against a thermal limit -- clock is the output, not an input -- so this
#     is the run that produces "chips that cannot otherwise run" as evidence rather than assertion.
#
# Geometry from array_config.sh as always. h_max comes from the refreshed module default
# (1000 W/mm^2, v91 Table 8.2); recovery is Carnot-bounded at the junction.
set -euo pipefail
JOBID="${1:?usage: dtmax_clock_sweep.sh <jobid>}"
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/dtmax_clock_sweep"
DTMAX="${DTMAX:-10 20 45 80 120 200}"
mkdir -p "$OUT"
for DT in $DTMAX; do
  d="$OUT/dt${DT}"
  if [ -f "$d/DONE" ]; then echo "== dt_max ${DT} K done, skip"; continue; fi
  mkdir -p "$d"
  echo "== sustainable clock search, dt_max ${DT} K =="
  srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none bash -lc \
    ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && \
     OMP_NUM_THREADS=1 python examples/clock_headroom.py --cores 34 --cfm 88 \
       --stack auto --pitch-um ${PITCH_UM} --burial-um ${BURIAL_UM} --cell-um ${CELL_UM} \
       --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} \
       --thermal-limit-C 100 --mr --mr-dt-max $DT --recovery-at-junction \
       --spot-min-um 10 --spot-policy dilute \
       --out-dir $d" < /dev/null && touch "$d/DONE"
done
echo "DTMAX CLOCK SWEEP DONE"
