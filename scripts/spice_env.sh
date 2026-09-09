#!/usr/bin/env bash
# Environment preamble for the BSIM-CMG simulator build -- see docs/BSIMCMG_TOOLCHAIN.md.
#
# `[!]` SOURCE THIS IN EVERY BUILD SHELL, head node or srun.  On node-06 both $HOME and /tmp are
# NODE-LOCAL (and /tmp is a 2 GB tmpfs), so an unpinned Rust/LLVM build either lands somewhere the
# head node cannot see or fills the tmpfs and dies.  Everything below redirects the four tools that
# default into $HOME or /tmp -- cargo, rustup, conda and the compilers' scratch -- onto the shared
# NFS scratch inside the repo.
#
#   source scripts/spice_env.sh
#
# Verify as you go: `spice_env_check` must keep reporting ~/.cargo and ~/.rustup absent.

export SPICE_ROOT=/mnt/nfs01/scratch/jbalma/MXL-HotGauge/spice_toolchain
mkdir -p "$SPICE_ROOT"/{envs,src,cargo,tmp,install,osdi}

export CARGO_HOME=$SPICE_ROOT/cargo
export RUSTUP_HOME=$SPICE_ROOT/cargo/rustup
export CARGO_TARGET_DIR=$SPICE_ROOT/cargo/target
export TMPDIR=$SPICE_ROOT/tmp
export TMP=$TMPDIR
export TEMP=$TMPDIR
export CONDA_PKGS_DIRS=/mnt/nfs01/scratch/jbalma/anaconda3/pkgs

# conda itself: `conda activate` needs conda.sh sourced, and bare `conda activate` fails under srun.
if [ -z "${CONDA_SHLVL:-}" ]; then
    # shellcheck disable=SC1091
    source /mnt/nfs01/scratch/jbalma/anaconda3/etc/profile.d/conda.sh
fi

spice_env_check() {
    stat -f -c "SPICE_ROOT avail: %a MiB" "$SPICE_ROOT"
    local stray=0
    for d in "$HOME/.cargo" "$HOME/.rustup"; do
        if [ -e "$d" ]; then echo "[!] STRAY: $d exists -- preamble was not sourced somewhere"; stray=1; fi
    done
    [ "$stray" = 0 ] && echo "ok: ~/.cargo and ~/.rustup absent"
    du -sh "$SPICE_ROOT"/* 2>/dev/null
}

# `[!]` conda 4.12's classic solver does not converge on these envs in reasonable time (the
# ngspice set was still solving after 10 minutes).  micromamba is a single static binary, needs no
# installer and no $HOME, and solves the same channels in seconds -- so it is what creates the
# envs.  MAMBA_ROOT_PREFIX is pinned for the same reason CARGO_HOME is: its default is ~/.
export MAMBA_ROOT_PREFIX=$SPICE_ROOT/mamba
export MAMBA_PKGS_DIRS=$SPICE_ROOT/mamba/pkgs
mkdir -p "$MAMBA_ROOT_PREFIX"
alias mm="$SPICE_ROOT/bin/micromamba"
spice_mm() { "$SPICE_ROOT/bin/micromamba" "$@"; }
