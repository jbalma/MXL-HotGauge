#!/usr/bin/env bash
# §P0.16 -- the ONE deliberate catalogue re-run, as a chain of four arms.
#
#   scripts/catalogue_rerun_arms.sh plan            # write all four plans + launchers
#   scripts/catalogue_rerun_arms.sh launch <jobid> A D      # run these arms concurrently
#
# WHY FOUR ARMS RATHER THAN ONE
# -----------------------------
# Three separate changes want this run (§P0.16): the leakage curve, the RBB policy, and the
# core_other accounting. Flipping all three at once produces a catalogue nobody can attribute --
# which is the confounding this project has already hit five times ("vary one thing"). Each arm
# below differs from the previous one by EXACTLY ONE flag, so every difference has a cause:
#
#   A  pipeline  + stock     + stock                  <- same-code control
#   B  simulated + stock     + stock                  <- A->B = the leakage curve
#   C  simulated + amortized + stock                  <- B->C = the RBB policy
#   D  simulated + amortized + hierarchy-consistent   <- C->D = the core_other accounting
#
# `[!]` Arm A is NOT redundant with the recorded catalogue. §P0.15 established that the recorded
# rows predate the RBB work, the residual/backtracking convergence fix and `verify=True`, so
# treating them as a reproduction target "would have read a real improvement as a regression".
# A is the same-code control that makes B, C and D interpretable, and it doubles as a check that
# the re-run machinery reproduces the catalogue at all.
#
# WHY THE ACCELERATOR SCRIPTS ARE EXCLUDED
# ----------------------------------------
# `accel_mr_batch.sh`, `kernel_batch.sh`, `dtmax_batch.sh` and `accel_batch.sh` are 72 points on
# the GA100 die, driven by `accelerator_study.py`, which accepts NONE of the three flags -- it has
# no McPAT cores, so `core_other` does not exist there, and it never took `--leakage-curve` or
# `--rbb-policy`. Re-running them reproduces the recorded output byte for byte at the cost of the
# CRITICAL PATH: they were streams 2 and 3 at 6.30 h. Dropping them takes each arm from 6.3 h to
# 3.8 h wall. It is also what the standing "one architecture, one die" rule already says.
set -euo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
cd "$REPO"

# The CPU-die batch scripts -- everything that can actually respond to a flag.
CPU_SCRIPTS="cooling_for_rated_clock.sh overnight3_study.sh nextsteps_batch.sh gapfill_batch.sh
             cliff_reverify.sh overnight_study.sh followon_study.sh design_study_batch.sh"

arm_args() {
  case "$1" in
    A) echo "--leakage-curve pipeline  --rbb-policy stock     --core-other-policy stock" ;;
    B) echo "--leakage-curve simulated --rbb-policy stock     --core-other-policy stock" ;;
    C) echo "--leakage-curve simulated --rbb-policy amortized --core-other-policy stock" ;;
    D) echo "--leakage-curve simulated --rbb-policy amortized --core-other-policy hierarchy-consistent" ;;
    *) echo "unknown arm $1" >&2; exit 1 ;;
  esac
}
arm_dir() { echo "$REPO/results/rerun_arm_$1"; }

case "${1:?usage: catalogue_rerun_arms.sh plan | launch <jobid> <arm>...}" in
plan)
  # Materialise the corrected trace ONCE, so ~24 concurrent workers share it rather than each
  # racing to build it (the materialiser is idempotent, but a half-written file read by a
  # concurrent worker is not something to rely on).
  python - <<'PY'
import sys; sys.path.insert(0, '/mnt/nfs01/scratch/jbalma/MXL-HotGauge/HotGauge')
from HotGauge.power.core_other import resolve_trace_dir, POLICY_CONSISTENT
print('corrected trace:', resolve_trace_dir(
    '/mnt/nfs01/scratch/jbalma/MXL-HotGauge/mcpat_runs/7nm/linpack_3.8GHz', POLICY_CONSISTENT))
PY
  for A in A B C D; do
    echo "=== planning arm $A: $(arm_args $A)"
    python scripts/catalogue_rerun.py --out "$(arm_dir $A)" --scripts $CPU_SCRIPTS \
      --extra-args "$(arm_args $A)" --launch | tail -14
    # `[!]` catalogue_rerun.py always writes its launcher to the FIXED path scripts/run_rerun.sh,
    # so planning four arms in a row leaves only the last one's launcher behind. The content is
    # arm-specific (it hardcodes OUT=<arm dir>), so copy it into the arm directory immediately.
    cp scripts/run_rerun.sh "$(arm_dir $A)/run_rerun.sh"
    chmod +x "$(arm_dir $A)/run_rerun.sh"
    grep -m1 '^OUT=' "$(arm_dir $A)/run_rerun.sh"
  done
  ;;
launch)
  shift; JOBID="${1:?need a slurm jobid}"; shift
  # `[!]` Each arm runs inside ONE real slurm step, with scripts/srun_shim first on PATH so the
  # generated launcher's per-stream `srun` calls become local forks. Without the shim, four arms
  # would ask for 24 concurrent steps against an allocation that admits about eight, and the
  # surplus would queue while most of the node idled. MAX_CONC still bounds the forks per arm.
  MAX_CONC="${MAX_CONC:-6}"
  for A in "$@"; do
    D="$(arm_dir $A)"
    [ -x "$D/run_rerun.sh" ] || { echo "arm $A not planned -- run 'plan' first" >&2; exit 1; }
    echo "launching arm $A -> $D  (MAX_CONC=$MAX_CONC, one slurm step)"
    nohup srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none \
      env PATH="$REPO/scripts/srun_shim:$PATH" MAX_CONC="$MAX_CONC" \
      "$D/run_rerun.sh" "$JOBID" > "$D/launch.log" 2>&1 &
    sleep 3
  done
  echo "all arms launched; $(squeue -s -u "$USER" 2>/dev/null | tail -n +2 | wc -l) slurm step(s) active"
  ;;
*) echo "usage: catalogue_rerun_arms.sh plan | launch <jobid> <arm>..." >&2; exit 1 ;;
esac
