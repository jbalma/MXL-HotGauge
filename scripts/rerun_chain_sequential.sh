#!/usr/bin/env bash
# Run the remaining catalogue arms ONE AT A TIME on job 1389.
#
#   nohup scripts/rerun_chain_sequential.sh 1389 B C A > results/rerun_chain.log 2>&1 &
#
# `[!]` WHY SEQUENTIAL. node-06 has 251 GB, not the head node's 503 GB. Four arms reached 240 GB in
# 17 minutes; two arms (A + D) then reached 231 GB. A single arm's footprint is NOT the planner's
# 83.5 GB estimate for every arm -- it scales with how many points CONVERGE, because a converging
# point holds its factorised session for many more solves than a diverging one, which exits fast.
# Measured: arm A (stock, 78 % converged) 85 GB; arm D (hierarchy-consistent, 99 % converged)
# 136 GB. So the memory-hungriest arm is the one whose physics works best, and "two arms fit" is
# not a safe rule. One at a time is.
#
# Restartable: each arm's launcher skips streams that left a .done marker, so a re-run resumes.
set -uo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
cd "$REPO"
JOBID="${1:?usage: rerun_chain_sequential.sh <jobid> <arm>...}"; shift

# Wait for any arm step already running to finish. Matches the step NAME the arm launcher gives
# its steps ("env"), not a hard-coded step-id list, so it keeps working across relaunches.
#
# `[!]` Do NOT stop this script with `pkill -f rerun_chain_sequential` or a `pgrep -f` loop: the
# pattern matches this agent's own command line and kills the calling shell too (measured: exit
# 144 = SIGTERM). Find the PID with `ps -eo pid,args | grep rerun_chain_sequential | grep -v grep`
# and kill that PID.
while squeue -s -u "$USER" 2>/dev/null | awk 'NR>1 && $2=="env"' | grep -q .; do
  sleep 120
done

for A in "$@"; do
  D="$REPO/results/rerun_arm_$A"
  if [ ! -x "$D/run_rerun.sh" ]; then echo "arm $A not planned; skipping"; continue; fi
  echo "[$(date +%H:%M:%S)] === starting arm $A ==="
  srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none \
    env PATH="$REPO/scripts/srun_shim:$PATH" MAX_CONC="${MAX_CONC:-6}" \
    "$D/run_rerun.sh" "$JOBID" >> "$D/launch.log" 2>&1
  echo "[$(date +%H:%M:%S)] === arm $A finished ($(find "$D" -name '*.json' | grep -vc 'plan.json\|stream_') results) ==="
done
echo "[$(date +%H:%M:%S)] ALL REMAINING ARMS DONE"
