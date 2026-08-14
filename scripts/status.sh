#!/usr/bin/env bash
#
# What is running, what has finished, what is left.
#
#   scripts/status.sh              summary
#   scripts/status.sh -v           also list every point and its result
#   scripts/status.sh -w           watch (refresh every 30 s)
#
# Safe to run any time from anywhere; it only reads. Needs no arguments -- the Slurm job is
# discovered automatically.
set -uo pipefail
REPO=/mnt/nfs01/scratch/jbalma/MXL-HotGauge
cd "$REPO" || exit 1

VERBOSE=0; WATCH=0
for a in "$@"; do
    case "$a" in
        -v|--verbose) VERBOSE=1 ;;
        -w|--watch)   WATCH=1 ;;
        -h|--help)    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    esac
done

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
dim()  { printf '\033[2m%s\033[0m\n' "$*"; }

show() {
    bold "=== allocation ==="
    local jobline
    jobline=$(squeue -u "$USER" -h -o "%i %T %M %L %R" 2>/dev/null | head -1)
    if [ -z "$jobline" ]; then
        printf '  no Slurm allocation -- results below are whatever finished before it ended\n'
        JOBID=""
    else
        printf '  job %s\n' "$jobline"
        JOBID=$(echo "$jobline" | awk '{print $1}')
    fi

    bold ""
    bold "=== running now ==="
    if [ -n "$JOBID" ]; then
        # --overlap so this does not queue behind the study's own steps.
        timeout 60 srun --jobid="$JOBID" --overlap bash -lc \
            'ps -eo etime,cmd --sort=start_time | grep -E "[m]r_comparison|[s]imscale_hpc" |
             sed "s|--out-dir.*||; s|python examples/||" | head -20' 2>/dev/null |
            grep -v '^srun:' | sed 's/^/  /'
        local n
        n=$(timeout 60 srun --jobid="$JOBID" --overlap bash -lc \
            'ps -eo cmd | grep -c "[m]r_comparison.py"' 2>/dev/null | grep -v '^srun:' | tr -d ' ')
        [ "${n:-0}" = "0" ] && printf '  (idle -- nothing running)\n'
        printf '  --> %s point(s) running\n' "${n:-0}"
    else
        printf '  (no allocation)\n'
    fi

    bold ""
    bold "=== studies ==="
    printf '  %-14s %8s %8s   %s\n' STUDY DONE RUNNING DIRECTORY
    for d in results/overnight2 results/followon results/gen results/conv results/relax025; do
        [ -d "$d" ] || continue
        local done_n dirs_n
        done_n=$(find "$d" -name mr_comparison.json 2>/dev/null | wc -l)
        dirs_n=$(find "$d" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        printf '  %-14s %8s %8s   %s\n' "$(basename "$d")" "$done_n" \
               "$((dirs_n - done_n))" "$d"
    done

    bold ""
    bold "=== driver logs (last line) ==="
    for f in results/overnight2/driver.log results/followon/driver.log; do
        [ -f "$f" ] && printf '  %-22s %s\n' "$(basename "$(dirname "$f")")" "$(tail -1 "$f")"
    done

    if [ "$VERBOSE" -eq 1 ]; then
        bold ""
        bold "=== every completed point ==="
        for d in results/overnight2 results/followon results/gen results/conv results/relax025; do
            [ -d "$d" ] || continue
            find "$d" -name mr_comparison.json 2>/dev/null | sort | while read -r j; do
                python3 - "$j" <<'PY' 2>/dev/null
import json, sys, os
j = sys.argv[1]
try:
    d = json.load(open(j))
except Exception:
    print('  %-40s (unreadable)' % os.path.basename(os.path.dirname(j))); raise SystemExit
p = {('mr' if r.get('mr') else 'nomr'): r for r in d.get('rows', [])}
a, b = p.get('nomr'), p.get('mr')
tag = os.path.relpath(os.path.dirname(j), 'results')
if not a or not b:
    print('  %-44s partial' % tag)
elif a.get('diverged') and b.get('diverged'):
    print('  %-44s RUNAWAY both' % tag)
elif a.get('diverged'):
    print('  %-44s RUNAWAY -> %.1f C  (MR rescue)' % (tag, b['peak_C']))
else:
    dT = b['peak_C'] - a['peak_C']
    dP = 100.0 * (b['gflops'] / a['gflops'] - 1.0) if a.get('gflops') else 0.0
    print('  %-44s %6.1f -> %6.1f C (%+5.1f K) %+6.1f%%' % (tag, a['peak_C'], b['peak_C'], dT, dP))
PY
            done
        done
    fi

    bold ""
    dim "  summaries:  cat results/overnight2/SUMMARY.txt"
    dim "              cat results/followon/SUMMARY.txt"
    dim "  full detail: scripts/status.sh -v"
    dim "  handoff:     docs/RESUME_NOTES.md"
}

if [ "$WATCH" -eq 1 ]; then
    while true; do clear; show; sleep 30; done
else
    show
fi
