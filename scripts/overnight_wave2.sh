#!/usr/bin/env bash
# Overnight campaign, second wave: sensitivity of the forward case to its own assumptions.
#
#   scripts/overnight_wave2.sh <jobid>
#
# Wave 1 (overnight_forward_campaign.sh) measures the claims. This wave asks how fragile they are
# -- which is what a reviewer asks second. Runs alongside wave 1 at a lower concurrency cap; the
# node has 96 cores and every job is single-threaded, so the two together stay well inside it.
#
# Resumable via DONE markers, per-job logs, geometry from array_config.sh.
#
# `[!]` srun needs --exact -c1 here. Without it every step inherits the
# allocation's full CPU count, slurm admits only ~8 at a time, and a 96-core node
# runs 8 single-threaded solves while 88 cores idle.
set -uo pipefail
JOBID="${1:?usage: overnight_wave2.sh <jobid>}"
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
ROOT="$REPO/results/overnight_wave2"
MAXJOBS="${MAXJOBS:-24}"
mkdir -p "$ROOT"
throttle() { while [ "$(jobs -rp | wc -l)" -ge "$MAXJOBS" ]; do sleep 5; done; }
launch() {
  local d="$ROOT/$1"; shift
  if [ -f "$d/DONE" ]; then echo "skip  $1"; return 0; fi
  mkdir -p "$d"; throttle; echo "start $1"
  ( srun --jobid="$JOBID" --overlap --exact -n1 -c1 --cpu-bind=none bash -lc \
      ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && OMP_NUM_THREADS=1 $*" \
      > "$d/log.txt" 2>&1 && touch "$d/DONE" || echo "FAILED $1" >> "$ROOT/failures.txt" ) &
}

# G. DOES THE STORY HOLD ON BIGGER DIES? The 34-core result is one die. Core count changes both
#    the area the heat spreads over and the number of independent hotspots.
for N in 70 128; do
  for D in 1.60 2.40; do
    launch "G_cores/n${N}_d${D}" "python examples/mr_comparison.py $ARM_ARGS \
        --cores $N --density $D --cfm 88 --mr-target-C 92 --spot-min-um 10 \
        --spot-policy dilute --recovery-at-junction --out-dir $ROOT/G_cores/n${N}_d${D}"
  done
done

# H. SPOT SIZE -- 10 um is a device assumption that the whole spatial-selectivity argument rests
#    on. If the win collapses at 25 um, that is a hard requirement on the optics, and the
#    proposal should say so rather than discover it later.
for S in 1 5 10 25 50 100; do
  launch "H_spot/s${S}" "python examples/mr_comparison.py $ARM_ARGS \
      --cores 34 --density 1.60 --cfm 88 --mr-target-C 92 --spot-min-um $S \
      --spot-policy dilute --recovery-at-junction --out-dir $ROOT/H_spot/s${S}"
done

# I. BURIAL DEPTH at the refreshed envelope. The array sits above the active layer; how much
#    silicon it must reach through sets how much of its capability survives to the junction.
#    `[!]` The ladder stops at 220 um and that is a HARD limit, not a choice: the 'auto' stack's
#    die is 240 um thick and the active layer is 20 um, so a source buried deeper than ~220 um
#    does not fit inside it. A 400 um point was launched on the first pass and failed with exactly
#    that error -- "active layer does not fit". Going deeper needs a thicker die, which is a
#    different experiment and should be run as one.
for B in 50 100 150 200; do
  launch "I_burial/b${B}" "python examples/mr_comparison.py --stack auto --pitch-um ${PITCH_UM} \
      --burial-um $B --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} \
      --cores 34 --density 1.60 --cfm 88 --mr-target-C 92 --spot-min-um 10 \
      --spot-policy dilute --recovery-at-junction --out-dir $ROOT/I_burial/b${B}"
done

# J. dt_max AT DENSITY -- the blocking device question, asked where it actually binds. Wave 1's
#    clock sweep asks it against frequency; this asks it against the density ladder.
for DT in 20 45 80 150; do
  launch "J_dtmax/dt${DT}" "python examples/mr_comparison.py $ARM_ARGS \
      --cores 34 --density 2.00 --cfm 88 --mr-target-C 92 --mr-dt-max $DT \
      --spot-min-um 10 --spot-policy dilute --recovery-at-junction \
      --out-dir $ROOT/J_dtmax/dt${DT}"
done

# K. h_max SENSITIVITY -- the refreshed value takes the LOW end of the published range. This
#    prices the rest of it, so the 10x lever is measured rather than assumed.
for H in 250 1000 3000 10000; do
  launch "K_hmax/h${H}" "python examples/mr_comparison.py $ARM_ARGS \
      --cores 34 --density 2.00 --cfm 88 --mr-target-C 92 --mr-h-max $H \
      --spot-min-um 10 --spot-policy dilute --recovery-at-junction \
      --out-dir $ROOT/K_hmax/h${H}"
done

echo "--- wave 2 launched; waiting ---"
wait
echo "OVERNIGHT WAVE2 DONE"
[ -f "$ROOT/failures.txt" ] && { echo "FAILURES:"; cat "$ROOT/failures.txt"; }
exit 0
