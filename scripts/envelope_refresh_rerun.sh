#!/usr/bin/env bash
# Re-run the studies affected by BOTH 30-Aug corrections, in one pass.
#
#   scripts/envelope_refresh_rerun.sh <jobid>
#
# Two independent corrections landed the same day and they touch the same studies, so running
# them separately would re-do the work:
#
#   1. h_max 250 -> 1000 W/mm^2 (v91 Table 8.2; the 250 was the Yb:YLF-era figure). The measured
#      rescue failed on the ENVELOPE rather than on cost, so this is expected to move verdicts.
#   2. --recovery-at-junction: the recorded ledger credited the whole fluorescence stream as
#      convertible work, omitting the Carnot factor.
#
# dt_max stays at 45 K: v91 supplies no replacement and inventing one would manufacture the
# result the rescue case is meant to test.
#
# Each run writes beside the original rather than over it, so the pre-refresh evidence stays
# readable for comparison.
set -euo pipefail
JOBID="${1:?usage: envelope_refresh_rerun.sh <jobid>}"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
run() {  # run <label> <cmd...>
  local label="$1"; shift
  local out="$REPO/results/envelope_refresh/$label"
  if [ -f "$out/DONE" ]; then echo "== $label already done, skip"; return 0; fi
  mkdir -p "$out"
  echo "== $label =="
  srun --jobid="$JOBID" --overlap -n1 --cpu-bind=none \
    bash -lc "export PATH=/mnt/nfs01/scratch/jbalma/anaconda3/bin:\$PATH; cd $REPO && OMP_NUM_THREADS=1 $*" \
    < /dev/null && touch "$out/DONE"
}

# clock headroom -- the study whose MR arm carries p_mr_net_W with first-law recovery
run clock_headroom "python examples/clock_headroom.py \
    --recovery-at-junction \
    --out-dir $REPO/results/envelope_refresh/clock_headroom" || true

# the measured rescue, at the refreshed envelope
run mr_rescue "python examples/mr_clipping_study.py \
    --powers 95 --r-th 0.3 --mr-target-C 92 --pitch-um 50 --cell-um 50 \
    --stack spec:package=direct_die,mr=GAAS --recovery-at-junction \
    --out-dir $REPO/results/envelope_refresh/mr_rescue" || true

echo "ENVELOPE REFRESH RERUN DONE"
