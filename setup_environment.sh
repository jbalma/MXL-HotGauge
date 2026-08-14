#!/bin/bash
# MXL-HotGauge environment.  Usage:  source setup_environment.sh
#
# Safe in non-interactive shells (srun/sbatch): `conda activate` only works after conda.sh has
# been sourced, which is the usual reason a script that runs fine on the head node fails on a
# compute node.
#
# Override any of these before sourcing if your layout differs:
#   MXL_ROOT      repo checkout            (default: this script's own directory)
#   MXL_CONDA     conda installation       (default: first one found)
#   MXL_ENV_NAME  conda env name           (default: mxl_hotgauge)
#   MXL_PREFIX    installer scratch prefix (default: $MXL_ROOT/.mxl)

# Resolve the repo from this script's own location so a fresh clone needs no editing.
if [ -z "${MXL_ROOT:-}" ]; then
    MXL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
fi
export MXL_ROOT
MXL_ENV_NAME="${MXL_ENV_NAME:-mxl_hotgauge}"
MXL_PREFIX="${MXL_PREFIX:-$MXL_ROOT/.mxl}"

# --- conda (non-interactive safe) ---
if [ -z "${MXL_CONDA:-}" ]; then
    for _c in /mnt/nfs01/scratch/jbalma/anaconda3 "$HOME/anaconda3" "$HOME/miniconda3" \
              "$HOME/miniforge3"; do
        [ -f "$_c/etc/profile.d/conda.sh" ] && { MXL_CONDA="$_c"; break; }
    done
    unset _c
fi
if [ -n "${MXL_CONDA:-}" ] && [ -f "$MXL_CONDA/etc/profile.d/conda.sh" ]; then
    . "$MXL_CONDA/etc/profile.d/conda.sh"
    conda activate "$MXL_ENV_NAME"
else
    echo "setup_environment.sh: no conda found. Set MXL_CONDA=/path/to/anaconda3" >&2
fi

export SNIPER_ROOT="$MXL_ROOT/snipersim"

# --- runtime libs for 3D-ICE and its heatsink FMU plugin ---
# Compute nodes can lack libraries the head node has (libopenblas0-openmp, libpugixml1v5, ...).
# Appended LAST so system copies always win; the staged copies only fill genuine gaps, and this
# is a harmless no-op once the packages are installed properly.
for _d in "$MXL_PREFIX/lib64" /mnt/nfs01/scratch/jbalma/mxl-nodelibs/lib64; do
    [ -d "$_d" ] && export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$_d"
done
unset _d

# 1 is not a compromise -- it is the fastest setting. MEASURED on node-03 (34-core die, 691k
# unknowns, steady solve):
#
#     threads   1      2      4      8     16
#     seconds  93.1  127.5  128.5  194.0  327.1     <- 3.5x SLOWER at 16
#
# 3D-ICE's steady solve is a sparse direct factorisation through SuperLU 4.3, which is
# *sequential* (no MT sources in its SRC/). The only threaded work is BLAS inside supernodes,
# and those are small enough that thread launch and sync overhead dominates. Raising this is a
# pessimisation, and it also oversubscribes the node against other users.
#
# The parallelism that does pay is ACROSS solves: each one is single-threaded, so run many
# independent sweep points concurrently instead. See docs/PERFORMANCE.md.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

# --- report ---
echo "MXL-HotGauge env: python=$(command -v python) ($(python -V 2>&1))"
echo "  MXL_ROOT=$MXL_ROOT"
echo "  SNIPER_ROOT=$SNIPER_ROOT  OMP_NUM_THREADS=$OMP_NUM_THREADS"
command -v parallel >/dev/null 2>&1 || \
    echo "  WARNING: GNU 'parallel' missing - scripts/run_mcpat.py will fail on this node" >&2
if [ -x "$MXL_ROOT/McPAT/mcpat" ] && \
   ! "$MXL_ROOT/McPAT/mcpat" 2>&1 | grep -q "How to use McPAT"; then
    echo "  WARNING: McPAT will not run here (32-bit runtime missing?). Run ./install.sh" >&2
fi
