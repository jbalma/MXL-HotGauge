#!/usr/bin/env bash
# ONE slurm step that runs MANY campaigns concurrently, and keeps picking up new ones.
#
#   nohup srun --jobid=<id> --overlap -n1 --cpu-bind=none scripts/campaign_server.sh \
#        > results/campaign_queue/server.log 2>&1 &
#   scripts/some_ladder.sh > results/campaign_queue/<name>.par<N>.tsv      # to queue one
#   touch results/campaign_queue/STOP                                       # to wind down
#
# Why (9 Sep 2026). A step on this allocation takes the WHOLE job by default -- `scontrol show
# step` reads CPUs=96, mem=237000M, because the job was allocated with CPUs/Task=96 -- so a
# second `srun --overlap` sits on "Requested nodes are busy" until the first step ends. Three
# campaigns wanted the node at once (D4's ladder, D3's smoke, D1's family) and only one could
# start. This step is the one step: it watches the queue directory, and every
# `<name>.par<N>.tsv` it finds is handed to campaign_inner.sh with PAR=N in the background.
# The node is shared by the sum of the PARs, so size them against 96 cores and 237 GB.
#
# Queue file contract: the campaign_inner.sh TSV (<out-dir>\t<command> per line). Files are
# moved to running/ when picked up and to done/ when finished; the log sits beside them.
set -uo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
QUEUE="$REPO/results/campaign_queue"
mkdir -p "$QUEUE/running" "$QUEUE/done"
cd "$REPO" || exit 1
export OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
echo "campaign server up on $(hostname) $(date)"
while [ ! -f "$QUEUE/STOP" ]; do
  for f in "$QUEUE"/*.tsv; do
    [ -e "$f" ] || continue
    b="$(basename "$f" .tsv)"
    par="$(echo "$b" | sed -n 's/.*\.par\([0-9][0-9]*\)$/\1/p')"; par="${par:-4}"
    mv "$f" "$QUEUE/running/$b.tsv"
    echo "$(date '+%H:%M:%S') start $b PAR=$par"
    (
      PAR="$par" "$REPO/scripts/campaign_inner.sh" < "$QUEUE/running/$b.tsv" \
          > "$QUEUE/running/$b.log" 2>&1
      mv "$QUEUE/running/$b.tsv" "$QUEUE/running/$b.log" "$QUEUE/done/" 2>/dev/null
      echo "$(date '+%H:%M:%S') done  $b"
    ) &
  done
  sleep 20
done
echo "STOP seen $(date); waiting for running campaigns"
wait
rm -f "$QUEUE/STOP"
echo "campaign server down $(date)"
