#!/usr/bin/env bash
# Run a command inside the SLURM allocation instead of on the head node.
#
# Everything in this project is a 3D-ICE factorisation, SuperLU is threaded, and one solve will
# happily take fifteen cores. Run on the login node it competes with every other user and with
# itself -- which is what produced a run of 1800 s startup timeouts that looked like a
# problem-size limit and was not.
#
#   scripts/on_node.sh <jobid> <command...>
#
# --overlap is required: an interactive allocation already holds its task, and without it the
# step queues behind itself forever.
set -euo pipefail
JOBID="${1:?usage: on_node.sh <jobid> <command...>}"; shift
exec srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none "$@"
