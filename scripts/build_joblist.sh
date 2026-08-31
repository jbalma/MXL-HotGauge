#!/usr/bin/env bash
# Emit the full overnight campaign as a TSV job list for campaign_inner.sh.
#
#   scripts/build_joblist.sh > /tmp/joblist.tsv
#
# Same eleven families as the two wave scripts, same geometry from array_config.sh. Splitting the
# job DEFINITIONS from the job RUNNER is what lets the whole campaign run inside one slurm step
# instead of one step per job -- see the header of campaign_inner.sh for why that matters here.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
W1="$REPO/results/overnight_forward"
W2="$REPO/results/overnight_wave2"
emit() { printf '%s\t%s\n' "$1" "$2"; }

# A. density ladder -- the gap: nothing above 1.18 W/mm^2 had ever been run
for D in 1.20 1.40 1.60 1.80 2.00 2.40 2.80 3.20; do
  emit "$W1/A_density/d${D}" "python examples/mr_comparison.py $ARM_ARGS --cores 34 --density $D --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --out-dir $W1/A_density/d${D}"
done
# B. airflow -- the (1-s)^5 fan-displacement claim, through the solver
for C in 20 30 45 60 88 120; do
  emit "$W1/B_cfm/cfm${C}" "python examples/mr_comparison.py $ARM_ARGS --cores 34 --density 1.15 --cfm $C --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --out-dir $W1/B_cfm/cfm${C}"
done
# C. pitch ladder at the refreshed envelope
emit "$W1/C_pitch/concentrated" "python examples/tile_pitch_sweep.py --concentrate 4.0 --target L3_4 --burial-um 200 --cell-um 50 --out-dir $W1/C_pitch/concentrated"
emit "$W1/C_pitch/uniform" "python examples/tile_pitch_sweep.py --burial-um 200 --cell-um 50 --out-dir $W1/C_pitch/uniform"
# D. budget ladder -- does the cliff survive 4x h_max
for W in 1 3 8 16 24 32 45; do
  emit "$W1/D_budget/w${W}" "python examples/tile_pitch_sweep.py --pitches 50 --no-ideal --concentrate 4.0 --target L3_4 --mr-W $W --burial-um 200 --cell-um 50 --out-dir $W1/D_budget/w${W}"
done
# E. leakage-coupled budget sweep, at an operating point that converges
for W in 0.5 1 2 3 5 8 12; do
  emit "$W1/E_leak/w${W}" "python examples/mr_clipping_study.py --powers 25 --r-th 0.3 --mr-target-C 40 --mr-budget-W $W --pitch-um 50 --cell-um 50 --stack spec:package=direct_die,mr=GAAS --recovery-at-junction --out-dir $W1/E_leak/w${W}"
done
# F. resistance ladder at density -- the division-of-labour test
for R in 0.05 0.10 0.30; do
  for D in 1.60 2.40; do
    emit "$W1/F_rth/r${R}_d${D}" "python examples/mr_comparison.py $ARM_ARGS --cores 34 --density $D --r-th $R --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --out-dir $W1/F_rth/r${R}_d${D}"
  done
done
# G. bigger dies
for N in 70 128; do
  for D in 1.60 2.40; do
    emit "$W2/G_cores/n${N}_d${D}" "python examples/mr_comparison.py $ARM_ARGS --cores $N --density $D --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --out-dir $W2/G_cores/n${N}_d${D}"
  done
done
# H. spot size -- the optics requirement the selectivity argument rests on
for S in 1 5 10 25 50 100; do
  emit "$W2/H_spot/s${S}" "python examples/mr_comparison.py $ARM_ARGS --cores 34 --density 1.60 --cfm 88 --mr-target-C 92 --spot-min-um $S --spot-policy dilute --recovery-at-junction --out-dir $W2/H_spot/s${S}"
done
# I. burial depth. Stops at 200 um: the auto stack's die is 240 um and the active layer 20 um, so
#    a source buried deeper does not fit. A 400 um point was tried and failed with exactly that.
for B in 50 100 150 200; do
  emit "$W2/I_burial/b${B}" "python examples/mr_comparison.py --stack auto --pitch-um ${PITCH_UM} --burial-um $B --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} --cores 34 --density 1.60 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --out-dir $W2/I_burial/b${B}"
done
# J. dt_max at density 2.00 -- the blocking device question, asked where it binds
for DT in 20 45 80 150; do
  emit "$W2/J_dtmax/dt${DT}" "python examples/mr_comparison.py $ARM_ARGS --cores 34 --density 2.00 --cfm 88 --mr-target-C 92 --mr-dt-max $DT --spot-min-um 10 --spot-policy dilute --recovery-at-junction --out-dir $W2/J_dtmax/dt${DT}"
done
# K. h_max at density 2.00 -- prices the rest of the published range
for H in 250 1000 3000 10000; do
  emit "$W2/K_hmax/h${H}" "python examples/mr_comparison.py $ARM_ARGS --cores 34 --density 2.00 --cfm 88 --mr-target-C 92 --mr-h-max $H --spot-min-um 10 --spot-policy dilute --recovery-at-junction --out-dir $W2/K_hmax/h${H}"
done
