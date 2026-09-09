#!/usr/bin/env bash
# §P0.16 -- the MR catalogue re-run on the measured leakage curves.
#
#   scripts/mr_curve_compare_joblist.sh [family] > /tmp/joblist.tsv
#   srun --jobid=<id> --overlap -n1 scripts/campaign_inner.sh < /tmp/joblist.tsv
#
# families: airflow (default) | clipping | all
#
# WHY THIS FILE EXISTS, and what it must not do
# ---------------------------------------------
# `mr_comparison.py` and `mr_clipping_study.py` gained `--leakage-curve` in §P0.15 but have only
# ever been RUN on `pipeline`. The 22 rescues, the clipping study, the granularity result and the
# budget cliff therefore all still rest on CACTI's eleven hard-coded numbers (§P0.12).
#
# Every command below is the RECORDED invocation from scripts/build_joblist.sh, character for
# character, plus `--leakage-curve` and a different `--out-dir`. That is the whole point: one
# input changes. The recorded trees under results/overnight_forward/ are NEVER written to -- these
# land in results/mr_curve_compare/, so the pipeline rows stay available as the control.
#
# `[!]` BOTH ARMS, ALWAYS. The rescue claim is a DIFFERENCE between the control and array arms
# ("control has no steady state, array holds target"). Re-running only the array arm cannot tell
# you whether a rescue survived, so mr_comparison.py is left to emit all three arms as it does by
# default -- do not add --arms here.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/array_config.sh"
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
OUT="$REPO/results/mr_curve_compare"
FAMILY="${1:-airflow}"
emit() { printf '%s\t%s\n' "$1" "$2"; }

# Curve tags: directory suffix -> --leakage-curve value.
curve_dir() { case "$1" in simulated) echo simulated;; simulated-gidl-off) echo gidl_off;; esac; }

if [ "$FAMILY" = airflow ] || [ "$FAMILY" = all ]; then
  # B. the airflow ladder -- docs/evidence/airflow_ladder_solved.json. The claim most exposed by
  #    the §P0.16 prediction (control_diverged at ALL SIX airflows) and the smallest family.
  for CURVE in simulated simulated-gidl-off; do
    D="$(curve_dir $CURVE)"
    for C in 120 88 60 45 30 20; do
      emit "$OUT/B_cfm_${D}/cfm${C}" "python examples/mr_comparison.py $ARM_ARGS --cores 34 --density 1.15 --cfm $C --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --leakage-curve $CURVE --out-dir $OUT/B_cfm_${D}/cfm${C}"
    done
  done
fi

if [ "$FAMILY" = pitch ] || [ "$FAMILY" = all ]; then
  # C'. the GRANULARITY ladder -- COUPLED, which is the whole point.
  #
  # `[!]` The recorded granularity result (2.77x on a hotspot) comes from
  # `examples/tile_pitch_sweep.py`, which does **linear solves with no leakage feedback at all** --
  # it holds no leakage model and never calls the loop. So `--leakage-curve` cannot be tested
  # there: the flag would be a literal no-op and the output byte-identical. Re-running it proves
  # nothing.
  #
  # The coupled form of the same question runs the pitch ladder through `mr_comparison.py`, which
  # DOES solve the coupled power/temperature problem and DOES take the flag. At a fixed target the
  # array's cost vs pitch IS the granularity curve: a coarse tile cools collateral silicon and
  # spends watts doing it. Held at the airflow ladder's own operating point (density 1.15,
  # 88 CFM, target 92 C) so pitch 500 reproduces that family's row exactly and the ladder is
  # anchored to something already measured.
  #
  # The `pipeline` arm is run too: there is no recorded row to use as a control, because the
  # recorded granularity number came from a different driver doing a different kind of solve.
  for CURVE in pipeline simulated simulated-gidl-off; do
    case "$CURVE" in pipeline) D=pipeline;; simulated) D=simulated;; *) D=gidl_off;; esac
    for P in $PITCH_SWEEP_UM; do
      emit "$OUT/C_pitch_${D}/p${P}" "python examples/mr_comparison.py --stack auto --pitch-um $P --burial-um ${BURIAL_UM} --cell-um ${CELL_UM} --mr-material ${MR_MATERIAL} ${SPREAD_ARGS} --cores 34 --density 1.15 --cfm 88 --mr-target-C 92 --spot-min-um 10 --spot-policy dilute --recovery-at-junction --leakage-curve $CURVE --out-dir $OUT/C_pitch_${D}/p${P}"
    done
  done
fi

if [ "$FAMILY" = clipping ] || [ "$FAMILY" = all ]; then
  # E. the leakage-coupled budget sweep -- the clipping study, at the operating point that
  #    CONVERGES (25 W), which is the one that carries the budget cliff. Its baseline sits at
  #    344.9 K and its MR arm at 326.1 K -- the COLD side of the 345 K crossover, i.e. the
  #    opposite side from the airflow ladder's array arm. See §P0.16's prediction 4.
  for CURVE in simulated simulated-gidl-off; do
    D="$(curve_dir $CURVE)"
    for W in 0.5 1 2 3 5 8 12; do
      emit "$OUT/E_leak_${D}/w${W}" "python examples/mr_clipping_study.py --powers 25 --r-th 0.3 --mr-target-C 40 --mr-budget-W $W --pitch-um 50 --cell-um 50 --stack spec:package=direct_die,mr=GAAS --recovery-at-junction --leakage-curve $CURVE --out-dir $OUT/E_leak_${D}/w${W}"
    done
  done
fi
