#!/usr/bin/env bash
# Runs a whole campaign INSIDE one slurm step, forking workers locally.
#
#   srun --jobid=<id> --overlap -n1 scripts/campaign_inner.sh < joblist.tsv
#
# Why not one srun per job. This allocation has NumTasks=1 and OverSubscribe=NO, so slurm admits
# only about EIGHT concurrent steps regardless of --overlap, --exact or -c1. Measured: 76 srun
# clients sat queued behind 8 running steps while 88 of 96 cores idled. A single step that forks N
# workers on the node sidesteps the step limit entirely, which is the standard pattern for many
# small tasks inside one allocation -- and it is the difference between the campaign finishing
# overnight and finishing in three days.
#
# Input: a TSV job list on stdin, one job per line:
#     <output-dir>\t<shell command>
# A job whose output dir already contains DONE is skipped, so this is resumable.
set -uo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
PAR="${PAR:-32}"
cd "$REPO" || exit 1
. "$REPO/setup_environment.sh" >/dev/null 2>&1 || true
export OMP_NUM_THREADS=1
export REPO

run_one() {
  local line="$1"
  local d="${line%%$'\t'*}"
  local cmd="${line#*$'\t'}"
  [ -f "$d/DONE" ] && { echo "skip $d"; return 0; }
  mkdir -p "$d"
  if eval "$cmd" > "$d/log.txt" 2>&1; then
    touch "$d/DONE"; echo "ok   $d"
  else
    echo "FAILED $d" >> "$REPO/results/campaign_failures.txt"; echo "FAIL $d"
  fi
}
export -f run_one

xargs -d '\n' -P "$PAR" -I{} bash -c 'run_one "$@"' _ {}
echo "CAMPAIGN INNER DONE"
