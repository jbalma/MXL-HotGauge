#!/usr/bin/env bash
#
# Truthful status for the study runs, because "no done marker" is NOT "still running".
#
#   scripts/jobstat.sh [results/dir ...]
#
# I have now three times reported a job as running when it had died -- once because a run was
# killed with its shell, once because a hard-coded timeout fired at 30 minutes, and once because
# the process crashed after the solve succeeded. Every time the tell was the same: absence of a
# `done` marker was read as progress. It is not evidence of anything on its own.
#
# A run is:
#   DONE     `done` marker present
#   RUNNING  a live process whose command line names the output directory
#   CRASHED  no marker, no process, and a traceback in the log
#   DEAD     no marker, no process, no traceback (killed, or never started)
set -uo pipefail

DIRS=("$@")
if [ ${#DIRS[@]} -eq 0 ]; then
    DIRS=(results/cop results/accel_mr results/dtmax results/kernel results/accel results/nextsteps)
fi

printf '%-34s %-8s %-9s %s\n' 'run' 'status' 'age' 'last line'
for d in "${DIRS[@]}"; do
    [ -d "$d" ] || continue
    for log in "$d"/*.log; do
        [ -e "$log" ] || continue
        tag="$(basename "$log" .log)"
        [ "$tag" = "driver" ] && continue
        out="$d/$tag"
        if [ -f "$out/done" ]; then
            status=DONE
        elif pgrep -f -- "$out" >/dev/null 2>&1; then
            status=RUNNING
        elif grep -q "Traceback" "$log" 2>/dev/null; then
            status=CRASHED
        else
            status=DEAD
        fi
        age=$(( ($(date +%s) - $(stat -c %Y "$log")) / 60 ))
        last=$(grep -vE 'Progress|^[[:space:]]*$' "$log" 2>/dev/null | tail -1 | cut -c1-58)
        printf '%-34s %-8s %6dm  %s\n' "$d/$tag" "$status" "$age" "$last"
    done
done
