#!/usr/bin/env bash
# Overnight campaign: the evidence the forward case still asserts rather than measures.
#
#   scripts/overnight_forward_campaign.sh <jobid>
#
# Six families, run in parallel with bounded concurrency. Every job is single-threaded
# (OMP_NUM_THREADS=1) so the 96-core node takes many at once; the cap keeps memory and the NFS
# write rate sane rather than the CPU count.
#
# All resumable: a job with a DONE marker is skipped, so this can be re-run after an interruption
# without losing completed work. Every job logs to its own file beside its output.
#
# Geometry always from array_config.sh. h_max comes from the refreshed module default
# (1000 W/mm^2, v91 Table 8.2); recovery is Carnot-bounded at the junction throughout.
set -uo pipefail
JOBID="${1:?usage: overnight_forward_campaign.sh <jobid>}"
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
ROOT="$REPO/results/overnight_forward"
MAXJOBS="${MAXJOBS:-28}"
mkdir -p "$ROOT"

throttle() { while [ "$(jobs -rp | wc -l)" -ge "$MAXJOBS" ]; do sleep 5; done; }

launch() {   # launch <dir> <command...>
  local d="$ROOT/$1"; shift
  if [ -f "$d/DONE" ]; then echo "skip  $(basename $d)"; return 0; fi
  mkdir -p "$d"
  throttle
  echo "start $(basename $d)"
  (
    srun --jobid="$JOBID" --overlap --exact -n1 -c1 --cpu-bind=none bash -lc \
      ". $REPO/setup_environment.sh >/dev/null 2>&1 && cd $REPO && OMP_NUM_THREADS=1 $*" \
      > "$d/log.txt" 2>&1 && touch "$d/DONE" || echo "FAILED $(basename $d)" >> "$ROOT/failures.txt"
  ) &
}

# ---------------------------------------------------------------------------------------------
# A. DENSITY LADDER -- the headline gap. The catalogue has never run above 1.18 W/mm^2 die-average,
#    so "enables chips that cannot otherwise run" has been asserted, not measured. Real fully-
#    clocked 7nm/5nm parts sit higher. Three arms per point; the control arm running away IS the
#    result at the top of the ladder.
# ---------------------------------------------------------------------------------------------
for D in 1.20 1.40 1.60 1.80 2.00 2.40 2.80 3.20; do
  launch "A_density/d${D}" "python examples/mr_comparison.py $ARM_ARGS \
      --cores 34 --density $D --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute \
      --recovery-at-junction --out-dir $ROOT/A_density/d${D}"
done

# ---------------------------------------------------------------------------------------------
# B. FAN DISPLACEMENT, THROUGH THE SOLVER -- the (1-s)^5 claim in hybrid_displacement.json is a
#    closed-form ledger. This measures the real thing: at each airflow, what does the array buy,
#    and how far down can the fan go before the die stops holding target?
# ---------------------------------------------------------------------------------------------
for C in 20 30 45 60 88 120; do
  launch "B_cfm/cfm${C}" "python examples/mr_comparison.py $ARM_ARGS \
      --cores 34 --density 1.15 --cfm $C --mr-target-C 92 --spot-min-um 10 --spot-policy dilute \
      --recovery-at-junction --out-dir $ROOT/B_cfm/cfm${C}"
done

# ---------------------------------------------------------------------------------------------
# C. TILE-PITCH LADDER AT THE REFRESHED ENVELOPE -- the measured efficacy (0.977-1.854 K/W) was
#    taken at h_max 250. A 4x higher intensity ceiling may change where granularity pays.
# ---------------------------------------------------------------------------------------------
launch "C_pitch/concentrated" "python examples/tile_pitch_sweep.py --concentrate 4.0 --target L3_4 \
    --burial-um 200 --cell-um 50 --out-dir $ROOT/C_pitch/concentrated"
launch "C_pitch/uniform" "python examples/tile_pitch_sweep.py \
    --burial-um 200 --cell-um 50 --out-dir $ROOT/C_pitch/uniform"

# ---------------------------------------------------------------------------------------------
# D. BUDGET LADDER AT THE REFRESHED ENVELOPE -- does the cliff (efficacy flat to the target
#    block's own power, then collapse) survive a 4x higher h_max? The cliff is a floorplan
#    property in the old data; this tests whether the envelope moves it.
# ---------------------------------------------------------------------------------------------
for W in 1 3 8 16 24 32 45; do
  launch "D_budget/w${W}" "python examples/tile_pitch_sweep.py --pitches 50 --no-ideal \
      --concentrate 4.0 --target L3_4 --mr-W $W --burial-um 200 --cell-um 50 \
      --out-dir $ROOT/D_budget/w${W}"
done

# ---------------------------------------------------------------------------------------------
# E. LEAKAGE-COUPLED BUDGET SWEEP -- the run that diverged twice on a badly chosen operating
#    point. The probe found 15-45 W usable on the 8-core stack, so it is run there. Tests whether
#    feedback moves the cliff: cooling cuts leakage (pushes it later) but leakage is steepest at
#    the hottest block (pulls it earlier).
# ---------------------------------------------------------------------------------------------
for W in 0.5 1 2 3 5 8 12; do
  launch "E_leak/w${W}" "python examples/mr_clipping_study.py --powers 25 --r-th 0.3 \
      --mr-target-C 40 --mr-budget-W $W --pitch-um 50 --cell-um 50 \
      --stack spec:package=direct_die,mr=GAAS --recovery-at-junction \
      --out-dir $ROOT/E_leak/w${W}"
done

# ---------------------------------------------------------------------------------------------
# F. COOLER LADDER AT DENSITY -- how far up the density ladder can each conventional cooler go
#    before it needs help, and what does the array change? r_th spans air to microchannel.
# ---------------------------------------------------------------------------------------------
for R in 0.05 0.10 0.30; do
  for D in 1.60 2.40; do
    launch "F_rth/r${R}_d${D}" "python examples/mr_comparison.py $ARM_ARGS \
        --cores 34 --density $D --r-th $R --mr-target-C 92 --spot-min-um 10 \
        --spot-policy dilute --recovery-at-junction --out-dir $ROOT/F_rth/r${R}_d${D}"
  done
done

echo "--- all launched; waiting ---"
wait
echo "OVERNIGHT FORWARD CAMPAIGN DONE"
[ -f "$ROOT/failures.txt" ] && { echo "FAILURES:"; cat "$ROOT/failures.txt"; }
exit 0
