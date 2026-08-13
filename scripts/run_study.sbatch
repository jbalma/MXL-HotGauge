#!/bin/bash
#SBATCH --job-name=mxl-hotgauge
#SBATCH --nodelist=node-06-8xv100
#SBATCH --exclusive
#SBATCH --mem=243000M
#SBATCH --cpus-per-task=96
#SBATCH --output=%x-%j.log
#SBATCH --error=%x-%j.log
#
# Batch driver for long MXL-HotGauge runs.
#
# WHY: interactive `salloc` sessions have repeatedly ended mid-run (jobs 1043, 1084, 1086),
# killing the srun step with exit 143 and losing the results. A batch job is owned by the
# scheduler, not by a terminal, so it survives disconnects.
#
# USAGE:
#   sbatch scripts/run_study.sbatch examples/mr_clipping_study.py --powers 21 23 25 --r-th 0.3
#   sbatch scripts/run_study.sbatch examples/steady_sink_sweep.py --powers 20 25 30
#
# Output lands in mxl-hotgauge-<jobid>.log in the submit directory, written line-buffered so
# a killed run still leaves everything up to the failure point (piping through `tail` does
# NOT do this -- it buffers until exit, which is how one run's results were lost entirely).

set -euo pipefail

REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
cd "$REPO"
source setup_environment.sh

if [ $# -lt 1 ]; then
    echo "usage: sbatch $0 <script.py> [args...]" >&2
    exit 2
fi

echo "=== $(date -Is) job ${SLURM_JOB_ID:-?} on $(hostname) ==="
echo "=== $* ==="

# -u / stdbuf: unbuffered so the log is usable while the job is still running.
stdbuf -oL -eL python -u "$@"
rc=$?

echo "=== $(date -Is) finished rc=$rc ==="
exit $rc
