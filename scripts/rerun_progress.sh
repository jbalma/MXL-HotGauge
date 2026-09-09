#!/usr/bin/env bash
# Honest completeness for the catalogue arms: done/reachable, per arm.
#
#   scripts/rerun_progress.sh      -> "A:39/159 B:122/159 C:25/159 D:159/159 (21 excluded)"
#
# `[!]` The obvious ways to count are all wrong. Under an arm root, `*.json` reads HIGH (it also
# holds one `sf<NN>_<driver>.json` argv file per stream plus plan.json); `mr_comparison.json` reads
# LOW (several catalogue drivers are not mr_comparison); and stream `.done` markers read low too --
# one arm-D stream completed all 33 of its points and left no marker. The plan's own `--out-dir`
# list is the denominator, minus the points that cannot complete in ANY arm.
#
# `[!]` The exclusion rule is IMPORTED from examples/catalogue_arm_compare.py rather than restated
# here. Two copies of a threshold is how one of them ends up stale, and this one is a measured
# quantity (the __agg__L3 boundary is bracketed by real points at 40 C and 50 C).
python3 - "$@" <<'PY'
import json, glob, os, sys
REPO = '/mnt/nfs01/scratch/jbalma/MXL-HotGauge'
sys.path.insert(0, os.path.join(REPO, 'examples'))
from catalogue_arm_compare import arm_completeness, ARMS
out, excl = [], 0
for a in ARMS:
    done, reach, _, unreach = arm_completeness(a)
    out.append('%s:%d/%d' % (a, done, reach))
    excl = max(excl, unreach)
print('%s (%d excluded)' % (' '.join(out), excl))
PY
