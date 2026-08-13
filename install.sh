#!/usr/bin/env bash
#
# MXL-HotGauge installer -- no root required.
#
#   ./install.sh                 full install into a new conda env
#   ./install.sh --skip-sniper   everything except the Sniper build (the slow part)
#   ./install.sh --check         verify an existing install, build nothing
#
# The upstream Tufts README assumes RHEL 9 and `dnf install` as root. Phonon is Ubuntu 22.04
# and you will not have root on the compute nodes, so this script takes a different route:
# every build dependency comes from conda-forge, and the one thing conda cannot provide --
# the 32-bit glibc runtime McPAT needs -- is unpacked from .deb files into a local prefix and
# reached through an explicit loader invocation. Nothing is written outside the repo, the
# conda env, and $MXL_PREFIX.
#
# What gets built, in order, because each step depends on the one before:
#   1. conda env            (compilers, libs, Python)
#   2. 32-bit runtime       (McPAT is a 32-bit binary; see mcpat.mk:25)
#   3. Sniper               performance model
#   4. McPAT                power model
#   5. SuperLU + 3D-ICE     thermal model, including the heatsink plugin
#   6. HotGauge python pkg  editable install
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${MXL_ENV_NAME:-mxl_hotgauge}"
PREFIX="${MXL_PREFIX:-$REPO/.mxl}"
LIB32="$PREFIX/lib32"
JOBS="${MXL_JOBS:-$(nproc 2>/dev/null || echo 4)}"

SKIP_SNIPER=0
CHECK_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --skip-sniper) SKIP_SNIPER=1 ;;
        --check)       CHECK_ONLY=1 ;;
        -h|--help)     sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }
warn() { printf '\033[33m    WARNING: %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31m    ERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 0. Locate conda
# ---------------------------------------------------------------------------
say "Locating conda"
CONDA_ROOT="${MXL_CONDA:-}"
if [ -z "$CONDA_ROOT" ]; then
    for c in /mnt/nfs01/scratch/jbalma/anaconda3 "$HOME/anaconda3" "$HOME/miniconda3" \
             "$HOME/miniforge3"; do
        [ -f "$c/etc/profile.d/conda.sh" ] && { CONDA_ROOT="$c"; break; }
    done
fi
[ -n "$CONDA_ROOT" ] || die "no conda found. Set MXL_CONDA=/path/to/anaconda3 and re-run."
note "conda root: $CONDA_ROOT"

# Sourcing conda.sh is what makes `conda activate` work in a non-interactive shell --
# without it this script cannot be used under srun/sbatch.
# shellcheck disable=SC1091
. "$CONDA_ROOT/etc/profile.d/conda.sh"

# ---------------------------------------------------------------------------
# 1. Conda environment
# ---------------------------------------------------------------------------
# Pick the fastest available solver. Phonon ships conda 4.12 with the classic solver, which
# takes >25 minutes on this spec -- long enough that it looks hung. In order of preference:
# mamba, conda's libmamba solver, then classic with a warning so nobody kills it at minute 10.
pick_solver() {
    if command -v mamba >/dev/null 2>&1; then
        CONDA_CMD="mamba"; SOLVER_ARGS=(); note "using mamba"
        return
    fi
    if command -v micromamba >/dev/null 2>&1; then
        CONDA_CMD="micromamba"; SOLVER_ARGS=(); note "using micromamba"
        return
    fi
    CONDA_CMD="conda"
    if python -c "import libmambapy" >/dev/null 2>&1; then
        SOLVER_ARGS=(--solver=libmamba); note "using conda with the libmamba solver"
    else
        SOLVER_ARGS=()
        warn "conda $(conda --version 2>/dev/null | awk '{print $2}') with the classic solver."
        warn "The solve alone can take 25+ minutes. It is not hung -- let it run."
        warn "To make this fast once, and for every future env:"
        warn "    conda install -n base -c conda-forge conda-libmamba-solver"
        warn "    conda config --set solver libmamba"
    fi
}

if [ "$CHECK_ONLY" -eq 0 ]; then
    say "Creating conda environment '$ENV_NAME'"
    pick_solver
    if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
        note "already exists -- updating from environment.yml"
        "$CONDA_CMD" env update -n "$ENV_NAME" -f "$REPO/environment.yml" --prune \
            "${SOLVER_ARGS[@]}"
    else
        note "solving and downloading (grab a coffee)"
        "$CONDA_CMD" env create -n "$ENV_NAME" -f "$REPO/environment.yml" "${SOLVER_ARGS[@]}"
    fi
fi
conda activate "$ENV_NAME"
note "python: $(command -v python) ($(python -V 2>&1))"

# ---------------------------------------------------------------------------
# 2. 32-bit runtime for McPAT
# ---------------------------------------------------------------------------
# McPAT/mcpat.mk hardcodes `CXX = g++ -m32`, so the binary is 32-bit and needs
# /lib/ld-linux.so.2 plus 32-bit libc/libstdc++/libgcc. On Ubuntu that is the libc6-i386 and
# lib32stdc++6 packages, which need root -- so instead we unpack the .debs into $LIB32 and run
# the binary through the loader explicitly:
#
#     $LIB32/ld-linux.so.2 --library-path $LIB32 McPAT/mcpat.bin
#
# Step 5 installs a wrapper at McPAT/mcpat that does this, so callers (scripts/run_mcpat.py
# invokes "../McPAT/mcpat" by relative path) need no changes.
#
# Building McPAT 64-bit instead would avoid all of this, but McPAT is old code with known
# 64-bit correctness problems, and Tufts ship it as 32-bit. Changing the word size silently
# would risk wrong power numbers, which is worse than an awkward install.
stage_lib32() {
    mkdir -p "$LIB32"
    if [ -e "$LIB32/ld-linux.so.2" ]; then
        note "32-bit runtime already staged in $LIB32"
        return 0
    fi
    if [ -e /lib/ld-linux.so.2 ]; then
        note "system already has a 32-bit loader; staging a copy anyway for compute nodes"
    fi
    command -v apt-get >/dev/null 2>&1 || {
        warn "apt-get not available -- cannot stage 32-bit libs automatically."
        warn "Copy ld-linux.so.2, libc.so.6, libm.so.6, libstdc++.so.6, libgcc_s.so.1"
        warn "(all i386) into $LIB32 by hand, or ask an admin for libc6-i386 + lib32stdc++6."
        return 1
    }

    local tmp
    tmp="$(mktemp -d)"
    note "downloading i386 runtime packages (no root needed)"
    (
        cd "$tmp"
        # `apt-get download` writes .debs to the cwd and needs no privileges. If the i386
        # architecture is not enabled on this host these will 404 -- that is the usual
        # failure, and it needs a one-time `dpkg --add-architecture i386` from an admin.
        apt-get download libc6:i386 libgcc-s1:i386 libstdc++6:i386 2>/dev/null \
            || apt-get download libc6-i386 lib32gcc-s1 lib32stdc++6 2>/dev/null \
            || return 1
        for d in ./*.deb; do dpkg -x "$d" "$tmp/root"; done
    ) || { rm -rf "$tmp"; warn "could not fetch i386 packages"; return 1; }

    find "$tmp/root" \( -name 'ld-linux.so.2' -o -name 'libc.so.6' -o -name 'libm.so.6' \
        -o -name 'libstdc++.so.6*' -o -name 'libgcc_s.so.1' \) -exec cp -aL {} "$LIB32/" \; \
        2>/dev/null || true
    rm -rf "$tmp"
    [ -e "$LIB32/ld-linux.so.2" ] || { warn "staging incomplete -- no loader in $LIB32"; return 1; }
    note "staged: $(ls "$LIB32" | tr '\n' ' ')"
}

if [ "$CHECK_ONLY" -eq 0 ]; then
    say "Staging 32-bit runtime for McPAT"
    stage_lib32 || warn "McPAT will not run until this is resolved"
fi

# ---------------------------------------------------------------------------
# 3. Sniper
# ---------------------------------------------------------------------------
export SNIPER_ROOT="$REPO/snipersim"
if [ "$CHECK_ONLY" -eq 0 ] && [ "$SKIP_SNIPER" -eq 0 ]; then
    say "Building Sniper (this is the slow step -- 10-30 min)"
    if [ -x "$SNIPER_ROOT/run-sniper" ] && [ -n "$(find "$SNIPER_ROOT" -name '*.so' -print -quit 2>/dev/null)" ]; then
        note "already built -- skipping (rm -rf snipersim/build to force)"
    else
        [ -d "$SNIPER_ROOT" ] || die "snipersim/ missing. It is vendored in this repo; re-clone."
        make -C "$SNIPER_ROOT" -j"$JOBS"
    fi
elif [ "$SKIP_SNIPER" -eq 1 ]; then
    note "Sniper build skipped (--skip-sniper)"
fi

# ---------------------------------------------------------------------------
# 4. McPAT
# ---------------------------------------------------------------------------
if [ "$CHECK_ONLY" -eq 0 ]; then
    say "Building McPAT"
    if [ -f "$REPO/McPAT/mcpat.bin" ] || file "$REPO/McPAT/mcpat" 2>/dev/null | grep -q ELF; then
        note "already built -- skipping"
    else
        # A `make clean` here leaves McPAT unbuildable; the upstream README says to delete the
        # directory and start over instead. Do not add a clean step.
        make -C "$REPO/McPAT" -j"$JOBS"
        chmod u+x "$REPO/McPAT/mcpat"
    fi
fi

# ---------------------------------------------------------------------------
# 5. McPAT loader wrapper
# ---------------------------------------------------------------------------
install_mcpat_wrapper() {
    local m="$REPO/McPAT/mcpat"
    [ -e "$m" ] || { warn "no McPAT binary to wrap"; return 1; }
    # Idempotent: if mcpat is already our wrapper, leave it alone.
    if head -c 2 "$m" 2>/dev/null | grep -q '#!'; then
        note "wrapper already installed"
        return 0
    fi
    file "$m" | grep -q "ELF 32-bit" || { note "mcpat is not 32-bit; no wrapper needed"; return 0; }
    mv "$m" "$REPO/McPAT/mcpat.bin"
    cat > "$m" <<WRAP
#!/bin/sh
# Generated by install.sh. McPAT is built 32-bit (mcpat.mk:25); on hosts without the i386
# runtime installed system-wide we reach it through the staged loader instead. Falls back to
# running the binary directly wherever the system loader exists.
LIB32="$LIB32"
if [ -x "\$LIB32/ld-linux.so.2" ] && [ ! -e /lib/ld-linux.so.2 ]; then
    exec "\$LIB32/ld-linux.so.2" --library-path "\$LIB32" "$REPO/McPAT/mcpat.bin" "\$@"
fi
exec "$REPO/McPAT/mcpat.bin" "\$@"
WRAP
    chmod +x "$m"
    note "installed wrapper: McPAT/mcpat -> mcpat.bin via staged loader"
}
[ "$CHECK_ONLY" -eq 0 ] && { say "Installing McPAT loader wrapper"; install_mcpat_wrapper || true; }

# ---------------------------------------------------------------------------
# 6. SuperLU and 3D-ICE
# ---------------------------------------------------------------------------
if [ "$CHECK_ONLY" -eq 0 ]; then
    say "Building SuperLU and 3D-ICE"
    if [ -f "$REPO/3d-ice/bin/3D-ICE-Emulator" ]; then
        note "3D-ICE already built -- skipping"
    else
        if [ ! -d "$REPO/3d-ice" ]; then
            note "fetching 3D-ICE"
            (cd "$REPO" && ./get_and_patch_3DICE.sh)
        fi
        # Upstream's patches reintroduce two of the four FMU bugs this fork fixes, so the MXL
        # sources go on top of whatever get_and_patch_3DICE.sh just produced. Must happen
        # BEFORE the build. See MXL_3DICE_fixes/README.md.
        note "applying MXL 3D-ICE source fixes"
        "$REPO/MXL_3DICE_fixes/apply.sh"
        [ -d "$REPO/3d-ice/SuperLU_4.3" ] || (cd "$REPO/3d-ice" && ./install-superlu.sh)
        # SuperLU's self-tests segfault at the end of its build. That is expected and does not
        # mean the library is bad.
        note "building heatsink plugin (20-60 min)"
        make -C "$REPO/3d-ice/heatsink_plugin" -j"$JOBS"
        make -C "$REPO/3d-ice" -j"$JOBS"
    fi
fi

# ---------------------------------------------------------------------------
# 7. HotGauge python package
# ---------------------------------------------------------------------------
if [ "$CHECK_ONLY" -eq 0 ]; then
    say "Installing the HotGauge package (editable)"
    # editable_mode=compat matters: the modern PEP 660 editable install leaves __file__ as None
    # for some modules, and HotGauge resolves data files relative to __file__. Without this the
    # package imports but cannot find its own templates.
    pip install -e "$REPO/HotGauge" --config-settings editable_mode=compat
fi

# ---------------------------------------------------------------------------
# 8. Verify
# ---------------------------------------------------------------------------
say "Verifying"
fail=0
check() {  # check <label> <command...>
    local label="$1"; shift
    if "$@" >/dev/null 2>&1; then printf '    [ ok ] %s\n' "$label"
    else printf '\033[31m    [fail] %s\033[0m\n' "$label"; fail=$((fail + 1)); fi
}
check "python imports HotGauge"      python -c "import HotGauge, HotGauge.thermal.sink_models"
check "GNU parallel on PATH"         command -v parallel
check "3D-ICE emulator built"        test -x "$REPO/3d-ice/bin/3D-ICE-Emulator"
check "heatsink FMI loader built"    test -f "$REPO/3d-ice/heatsink_plugin/loaders/FMI/fmi_loader.so"
check "McPAT runs"                   sh -c "'$REPO/McPAT/mcpat' 2>&1 | grep -q 'How to use McPAT'"
if [ "$SKIP_SNIPER" -eq 0 ]; then
    check "Sniper present"           test -x "$SNIPER_ROOT/run-sniper"
fi
check "unit tests pass"              python -m pytest "$REPO/HotGauge/HotGauge" -q

say "Result"
if [ "$fail" -eq 0 ]; then
    cat <<DONE
    Install looks good.

    Every session:   source setup_environment.sh
    Quick smoke:     python examples/plot_floorplans.py --cores 34 --out-dir plots
    Read next:       README.md, docs/SIMSCALE_INTEGRATION.md

    Note: setup_environment.sh has absolute paths for the original developer's checkout.
    Set MXL_ROOT / MXL_CONDA in your shell, or edit it, if yours differs.
DONE
else
    echo "    $fail check(s) failed -- see above." >&2
    exit 1
fi
