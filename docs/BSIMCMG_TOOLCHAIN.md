# Getting a BSIM-CMG simulator working on node-06

**Written 31 August 2026. Executed the same day -- see "What actually happened" at the bottom, which supersedes the predictions in the middle.** The goal is to replace §P0.12's *analytic* off-state curve with a
*simulated* one, so the leakage-vs-temperature curve the whole project rests on stops being an
interpolation of eleven hard-coded CACTI numbers. Everything below was checked on the live system,
not assumed; the checks are recorded so the next session does not repeat them.

## Why this is the top item

`docs/evidence/device_leakage_asap7.json` established two things:

- the pipeline's leakage curve is a **bit-for-bit pass-through** of `I_off_n[0][*]` for "16nm DG
  HP" (`McPAT/cacti/technology.cc:1610`) — 32 nm numbers times three fudge factors;
- its implied activation energy spans **0.016–1.081 eV, 69×, non-monotone**, so it is not a device.

The stand-in is an analytic off-state model parameterised from a real card. It is fitted to the
very table it criticises, so it inherits that table's *level* — only its *shape* is independent.
**A simulator removes that dependency entirely**, and with it the two largest open uncertainties:
the cold-zone prize below 310 K and every claim above 400 K, including §P0.11's flat-die ceiling.

## What is already established

| fact | evidence |
|---|---|
| `ptm.asu.edu` does not resolve | DNS failure; ASAP7 substituted, see `spice_leakage/PROVENANCE.md` |
| conda-forge `ngspice-41` has **no BSIM-CMG** | `devhelp` lists BSIM1/2/3/4, SOI, HiSIM — no CMG |
| ...and **OSDI is compiled out** | `pre_osdi` string is *in* the binary but the command is unavailable → built with `--disable-osdi` |
| ngspice from source gets OSDI **by default** | `configure.ac:145` offers `--disable-osdi`; `:1114` treats unset as enabled. **There is no `--enable-osdi` flag** |
| latest ngspice release | **47** (`sourceforge.net/projects/ngspice/files/ng-spice-rework/`, reachable) |
| OpenVAF ships **no binaries** | latest release `OpenVAF-v23.5.0` has an empty asset list |
| OpenVAF needs **rust ≥ 1.64, LLVM-15 and clang-15**, matching | its README, "Build Instructions" |
| BSIM-CMG Verilog-A source | `dwarning/VA-Models`, `code/bsimcmg/vacode` (**111.2.1**) and `code/bsimcmg/vacode110` (**110.0.0**) |
| module name is `bsimcmg_va`, **five terminals** `(d, g, s, e, t)` | `bsimcmg.va:27` — note the thermal node `t` |
| no `xyce` conda package exists | anaconda.org API: "could not be found" |

### node-06, surveyed under the allocation

```
Ubuntu 22.04.5, gcc/g++ 11.4.0, make 4.3, git 2.34.1
MISSING: cmake autoconf automake libtool bison flex rustc cargo llvm-config (all versions)
MISSING dev libs: libtool-bin libfl-dev libxaw7-dev libreadline-dev libncurses-dev
passwordless sudo: NO
/mnt/nfs01 free: 5.9 T
```

**`[!]` No root, and the node is bare — but every missing tool is on conda-forge**, which is how
the rest of this project already works. Confirmed available: `cmake`, `bison`, `flex`, `autoconf`,
`automake`, `libtool`, `make`, `rust` (1.98), and **`llvmdev` 15.0.0–15.0.6** — the exact major
version OpenVAF wants. Build in a dedicated env; do **not** touch `mxl_hotgauge`.

## Where to build — and the two facts that decide it

### `[!]` Size: this needs tens of GB, not terabytes

The "5.9 T" and "8.0 T" figures are **free space, not a requirement** — `df` output, misread as an
estimate. Calibrated against the build trees already in this repo (`snipersim` 1.6 G, `3d-ice`
457 M, `McPAT` 13 M) and the existing conda envs (`mxl_hotgauge` 565 M):

| component | expected |
|---|---|
| conda env: `llvmdev` 15 + `clangdev` 15 + `rust` + build tools | ~5–8 GB |
| OpenVAF `target/release` (Rust + `llvm-sys`) | ~5–15 GB |
| cargo registry + git cache | ~2 GB |
| ngspice 47 source + build + install | ~0.5 GB |
| `VA-Models` clone | ~0.1 GB |
| **reserve** | **40 GB** |

That is **0.5 % of the 8.0 TB free**. Space is not a constraint here; *landing in the right
filesystem* is.

### `[!]` `$HOME` is node-local. `/mnt/nfs01/scratch` is the shared one

Verified from inside the allocation:

```
/mnt/nfs01/scratch  ->  nfs4, 10.10.10.200:/scratch, rw     8.0 TiB avail   SHARED
/home/jbalma        ->  ext2/ext3 on the node's own nvme    834 G free      NODE-LOCAL
/tmp                ->  tmpfs, 2.0 G                        NODE-LOCAL, tiny
```

A file written by node-06 under `/mnt/nfs01/scratch/...` was read back on the head node, so the
share is genuinely two-way. But **anything a build puts in `$HOME` on node-06 lands on that node's
local disk and the head node never sees it** — and Rust defaults to `~/.cargo` and `~/.rustup`,
conda's fallback `pkgs_dirs`/`envs_dirs` are `~/.conda/*`, and cmake/cargo spill to `/tmp`, which
here is a **2 GB tmpfs** that a Rust/LLVM build will fill and fail on.

So the environment has to be pinned explicitly. This is the whole answer to "will it need moving
afterwards": pinned, no; unpinned, yes — and silently.

Note `df -h /mnt/nfs01` reports the *root* filesystem, because the mount point is
`/mnt/nfs01/scratch`. Use `stat -f` or `df -h /mnt/nfs01/scratch` or the number is wrong.

### The layout

Build **inside the repo**, alongside the toolchains already there — `snipersim/`, `McPAT/` and
`3d-ice/` are all in-tree build trees and all three are **already gitignored**, so this follows the
established pattern rather than inventing one:

```
/mnt/nfs01/scratch/jbalma/MXL-HotGauge/
└── spice_toolchain/          <- add to .gitignore BEFORE building
    ├── envs/                 conda envs, created with `-p` so they land here
    │   ├── ngspice_build/
    │   └── openvaf_build/
    ├── src/                  ngspice-47/, OpenVAF/, VA-Models/
    ├── cargo/                CARGO_HOME + CARGO_TARGET_DIR
    ├── tmp/                  TMPDIR — NOT the node's 2 GB tmpfs
    ├── install/              ngspice --prefix lands here
    └── osdi/                 the compiled bsimcmg.osdi, the actual deliverable
```

`[!]` **Add `spice_toolchain/` to `.gitignore` before the first build**, not after — otherwise a
`git status` mid-build lists tens of thousands of object files, and the one thing worth keeping
(`osdi/bsimcmg.osdi`, a few hundred KB) gets lost among them. Decide separately whether to track
the built `.osdi`; it is a binary artefact, but a small and reproducible one.

### The environment preamble

Every build shell — head node or `srun` — starts with this. Nothing below writes to `$HOME`:

```bash
export SPICE_ROOT=/mnt/nfs01/scratch/jbalma/MXL-HotGauge/spice_toolchain
mkdir -p $SPICE_ROOT/{envs,src,cargo,tmp,install,osdi}
export CARGO_HOME=$SPICE_ROOT/cargo
export RUSTUP_HOME=$SPICE_ROOT/cargo/rustup
export CARGO_TARGET_DIR=$SPICE_ROOT/cargo/target
export TMPDIR=$SPICE_ROOT/tmp
export TMP=$TMPDIR TEMP=$TMPDIR
export CONDA_PKGS_DIRS=/mnt/nfs01/scratch/jbalma/anaconda3/pkgs   # already on NFS; pin it anyway
```

Create envs by **path**, never by name, so they cannot fall back to `~/.conda/envs`:

```bash
conda create -y -p $SPICE_ROOT/envs/ngspice_build -c conda-forge <pkgs>
conda activate $SPICE_ROOT/envs/ngspice_build
```

**Check before starting a long build**, and again after:

```bash
stat -f -c "avail: %a MiB" $SPICE_ROOT          # expect ~8.3e6, want >40000 free
du -sh $HOME/.cargo $HOME/.rustup $HOME/.conda 2>/dev/null   # must stay absent/empty
```

If either `~/.cargo` or `~/.rustup` appears, the preamble was not sourced in that shell — stop and
fix it rather than letting the build finish somewhere it will have to be moved from.

## The plan

Three stages. Each has a checkpoint that must pass before moving on — the point is to find out
early which one fails, because stage 2 is the risky one.

### Stage 1 — ngspice 47 from source, with OSDI  *(low risk)*

Source the preamble above first, then:

```bash
conda create -y -p $SPICE_ROOT/envs/ngspice_build -c conda-forge \
  autoconf automake libtool bison flex make gcc_linux-64 gxx_linux-64 \
  readline ncurses libxaw   # adjust names to what conda-forge actually ships
conda activate $SPICE_ROOT/envs/ngspice_build
cd $SPICE_ROOT/src && curl -sSLO \
  https://sourceforge.net/projects/ngspice/files/ng-spice-rework/47/ngspice-47.tar.gz
tar xf ngspice-47.tar.gz && cd ngspice-47
./configure --prefix=$SPICE_ROOT/install --with-ngshared=no --enable-xspice --disable-debug
make -j16 && make install
```

`--prefix` points at `$SPICE_ROOT/install`, **not** `$CONDA_PREFIX` — the binary then survives the
env being rebuilt, and stays on NFS either way. **Do not pass `--enable-osdi`; it does not exist.** Confirm OSDI
survived configure: the log prints `OSDI features included`.

**Checkpoint 1:** `printf 'osdi /nonexistent.osdi\nquit\n' | ngspice -p` must say the *file*
is missing, not that the *command* is missing. That single line distinguishes a working build from
the conda one.

`[!]` **Corrected while running it: the command is `osdi`, not `pre_osdi`.** `pre_osdi` at the
prompt reports "no such command" on a *perfectly good* build, so the original spelling of this
checkpoint fails the thing it is supposed to pass. The two are not synonyms and both are needed:

| | what it is | when it runs | where it goes |
|---|---|---|---|
| `osdi <path>` | a real command, `src/frontend/commands.c:289` | *after* the netlist is parsed | the prompt, to test the build |
| `pre_osdi <path>` | not a command; `src/frontend/inp.c:786` strips the `pre_` prefix | *before* parsing | inside the deck's `.control`, to actually load a model |

A deck that says `osdi` instead of `pre_osdi` fails with `Unknown model type bsimcmg - ignored`
followed by `Unable to find definition of model` -- the model loads, just too late to bind.

### Stage 2 — OpenVAF  *(the risky stage)*

```bash
conda create -y -p $SPICE_ROOT/envs/openvaf_build -c conda-forge \
  rust llvmdev=15.0.6 clangdev=15.0.6 cmake
conda activate $SPICE_ROOT/envs/openvaf_build
export LLVM_CONFIG=$CONDA_PREFIX/bin/llvm-config
cd $SPICE_ROOT/src && git clone https://github.com/pascalkuthe/OpenVAF && cd OpenVAF
cargo build --release          # lands in $CARGO_TARGET_DIR, i.e. on NFS, not ~/.cargo
```

The README's blessed path is a docker image, which is unavailable here (no root, no docker), so
this is the unblessed path and is where the plan is most likely to break. Expect trouble with
`llvm-sys` finding the conda LLVM, and with clang and LLVM having to be the *same* version.

**Checkpoint 2:** `target/release/openvaf --version` runs, then it compiles the Verilog-A:

```bash
cd $SPICE_ROOT/src && git clone https://github.com/dwarning/VA-Models
$CARGO_TARGET_DIR/release/openvaf \
  $SPICE_ROOT/src/VA-Models/code/bsimcmg/vacode110/bsimcmg.va \
  -o $SPICE_ROOT/osdi/bsimcmg.osdi
```

**If stage 2 cannot be made to work, stop and report rather than grinding.** The fallback is
**Xyce**, which has BSIM-CMG built in and needs no Verilog-A at all — but it is a Trilinos + CMake
source build with no conda package, so it is a bigger job, not a quicker one. Do not start it
without checking in first.

### Stage 3 — run the card

`[!]` Two things change versus the vendored card, and both will produce confusing failures:

1. **The `.model` line.** With OSDI there is no `level=`. The vendored
   `spice_leakage/models/asap7_7nm_TT.pm` has `level = 17` (converted from HSPICE's `72`) for a
   built-in model that does not exist. For OSDI it becomes `.model nmos_rvt bsimcmg_va ...`, the
   module name from the `.va`. **Keep the vendored file as retrieved and do the rewriting in a
   generated copy** so provenance stays intact.
2. **Five terminals, not four.** `module bsimcmg_va(d, g, s, e, t)` — drain, gate, source,
   substrate, and a **thermal node**. A four-node instance line will fail or silently misbind.

`[!]` **Version mismatch to resolve first.** The ASAP7 card declares `version = 107`; VA-Models
ships **110.0.0** and **111.2.1**. Try 110 first (closer), and check explicitly which of the
card's 134 parameters the model rejects or ignores — a silently dropped parameter is the failure
mode that produces a plausible wrong curve. If 107 is needed, it is on the Berkeley BSIM site.

`[!]` **And the module name is not `bsimcmg_va` in every tree.** 111.2.1 declares `bsimcmg_va`,
but 110.0.0 wraps the declaration in `` `ifdef __XYCE__ `` and declares **`bsimcmg`** in the
branch OpenVAF actually compiles. Reading the first `module` line out of the file gets the wrong
name half the time; `spice_sim.module_name_of()` walks the conditionals instead.

**Checkpoint 3 — validation, and this is the point of the whole exercise:**

1. **Sanity**: at T = 300 K, V_gs = 0, V_ds = 0.7 V, `nmos_rvt` off-current should land in the
   nA/µm range for an HP 7 nm FinFET. Orders of magnitude out means the card is not binding.
2. **The real test**: sweep 200–500 K and compare against
   `docs/evidence/device_leakage_asap7.json`'s card-based curve. The analytic model predicts
   0.011 at 250 K and 349 at 500 K, relative to 330 K. **Agreement confirms the analytic
   stand-in; disagreement is the more interesting result and supersedes it.** Either way the
   simulated curve is what gets used afterwards.
3. Then re-run the density ladder and the cold-zone prize on the simulated curve, **on the same
   34-core die** — the one-die constraint still holds.

## Scope discipline

This is a **tooling** task. It ends when a simulated `I_off(T)` table exists and
`HotGauge/power/device_leakage.py` can be re-anchored to it. Re-running studies comes after, and
no new floorplan enters the picture — see the one-die constraint in `CLAUDE.md`.

---

# What actually happened — 31 August 2026

**All three stages passed.** The simulated curve is in
`docs/evidence/device_leakage_spice_asap7.json`, produced by `examples/device_leakage_spice.py`
via `HotGauge/power/spice_sim.py`. Total elapsed: about half a day, most of it on stage 2, exactly
as predicted — though not for the predicted reason.

Everything below is a correction to, or an addition to, the plan above. Read it before repeating
any of this.

## The predictions that were wrong

| the plan said | what happened |
|---|---|
|  **~40 GB** | **6.5 GB.** conda envs 3.6 G (including a 1 G gdb env that was only needed to diagnose the OpenVAF crash), cargo 2.8 G, sources 232 M, ngspice install 8.8 M, and the actual deliverable -- three `.osdi` files -- 2.3 M. The reserve was 6x over. |
| `llvm-sys` will fight the conda LLVM | **There is no `llvm-sys`.** OpenVAF has its own hand-written `openvaf/llvm` crate. It found conda's LLVM 15 on the first try, and every required component (`ipo`, `lto`, `debuginfopdb`, `windowsmanifest`, `libdriver`) is present with static libs. |
| clang and LLVM must be the same version | True, and *insufficient*: **conda's `clangdev=15` ships alongside gcc **16**'s libstdc++ headers, which clang 15 cannot parse.** The C++ shim dies on `stl_iterator.h`. Fix: build the shim with the **system** `g++ 11.4.0` (`CC=/usr/bin/gcc CXX=/usr/bin/g++`) and leave clang out of it entirely. |
| stage 2 is where it breaks | It broke three times, none of them where expected — see below. |

## The four things that actually blocked stage 2

1. **`conda` 4.12's classic solver does not converge** on these environments in usable time (the
   ngspice set was still solving after ten minutes and was killed). **micromamba** — one static
   binary, no installer, no `$HOME` — solves the same channels in **five seconds**. It is now
   fetched by `scripts/spice_env.sh`, which also pins `MAMBA_ROOT_PREFIX` for the same reason
   `CARGO_HOME` is pinned. Also: the conda-forge package is **`xorg-libxaw`**, not `libxaw`; X is
   not needed at all, so ngspice is configured `--without-x`.
2. **The libstdc++ version clash** above.
3. **node-06 has no `libz.so`, `libzstd.so` or `libxml2.so`** — only the runtime `.so.N`. The final
   Rust link needs all three. `micromamba install zlib zstd` into the OpenVAF env and link with
   `RUSTFLAGS="-Clink-arg=-L$E/lib -Clink-arg=-Wl,-rpath,$E/lib"`.
4. `[!]` **OpenVAF then segfaulted on every input, including a five-line diode.** This is a
   genuine **undefined-behaviour bug in OpenVAF**, not a build problem: it passes LLVM an
   `overview` string built from `b""`, which is a dangling, non-NUL-terminated pointer, and LLVM
   calls `strlen` on it. One-character fix, kept in
   `MXL_SPICE_fixes/OpenVAF.llvm-overview-nul.patch` with the backtrace. **Do not rebuild LLVM
   over this symptom** — the front end works, the crash is in `configure_llvm`, and that is the
   whole diagnosis.

## `[!]` Stage 3's real hazard was not the card. It was the linear solver

The card bound on the first try. The three parameters ngspice rejects — `capmod`, `coremod`,
`version` — are switches BSIM-CMG *removed* after 107, not values being silently dropped, and all
three model trees agree to **0.4 %** once normalised, which is the evidence that nothing important
went with them.

What nearly produced a plausible wrong curve was arithmetic:

- **One 7 nm fin leaks a few pA, and ngspice cannot resolve a branch current that small.** With
  the default SPARSE solver every value came back an *exact multiple of 2⁻⁴³ A* — quantisation
  that looks exactly like a curve. Switching to **KLU** moved the 250 K point by 2.3 %; it is still
  a floor, just a different one.
- **The fix is `nfin`.** DC current is exactly linear in the fin count (`shmod = 0`, so nothing
  couples them), so simulate **1000 fins and divide**. At `nfin = 1` the GIDL-off point at 200 K
  was **70 % wrong**; at 1000 it is converged to 0.04 % against a 10× check. Do not go much
  further — at `nfin = 1e7` the *hot* end starts losing digits instead.
- **Convergence is now asserted, not assumed**: the driver re-runs the whole sweep at 10× `nfin`
  and records the deviation. Anything that does not do this should not be quoted.

The version cross-check makes the same point. At `nfin = 1` the Xyce-flavoured tree appeared to
disagree with 110 by **10 %**; converged, it agrees to **0.37 %**. The 10 % was noise, and it would
have been written up as a model difference.

## Checkpoint results

| | result |
|---|---|
| **1** — ngspice 47 has OSDI | **PASS**, with the spelling correction above. `configure` logged `OSDI features included`. |
| **2** — OpenVAF compiles BSIM-CMG | **PASS** after the patch. All three trees build: `vacode110` (3.2 s), `vacode111` (3.5 s), `vacode` (7.0 s). |
| **3a** — sanity | **PASS.** I_off(300 K) = **0.232 nA/µm**; subthreshold swing **61.7 mV/dec** against a 59.5 ideal — the card is binding and the device is a device. |
| **3b** — versus the analytic curve | **The analytic curve is confirmed hot and superseded cold.** See §P0.13. |

`[!]` **The headline result is that the analytic model's cold end was wrong**, and not by a little:
the floor below ~250 K is **GIDL** (98 % of the current at 200 K), not the gate leakage the
analytic model assumed, and it sits ~40× higher. The cold-zone prize is **~20× smaller** than
§P0.12 promised. The hot tail is gentler than either previous curve. Both are recorded in
§P0.13 and in the evidence file.

## Rebuilding from scratch

```bash
source scripts/spice_env.sh          # pins CARGO_HOME, RUSTUP_HOME, TMPDIR, MAMBA_ROOT_PREFIX
spice_env_check                      # ~/.cargo and ~/.rustup must stay absent, throughout

# stage 1
spice_mm create -y -p $SPICE_ROOT/envs/ngspice_build -c conda-forge \
  autoconf automake libtool bison flex make pkg-config readline ncurses
cd $SPICE_ROOT/src && curl -sSLo ngspice-47.tar.gz \
  'https://sourceforge.net/projects/ngspice/files/ng-spice-rework/47/ngspice-47.tar.gz/download'
tar xf ngspice-47.tar.gz && cd ngspice-47
PATH=$SPICE_ROOT/envs/ngspice_build/bin:$PATH \
  ./configure --prefix=$SPICE_ROOT/install --with-ngshared=no --enable-xspice \
              --disable-debug --without-x
make -j16 && make install

# stage 2
spice_mm create -y -p $SPICE_ROOT/envs/openvaf_build -c conda-forge \
  rust llvmdev=15.0.7 clangdev=15.0.7 cmake make zlib zstd
E=$SPICE_ROOT/envs/openvaf_build
cd $SPICE_ROOT/src && git clone https://github.com/pascalkuthe/OpenVAF && cd OpenVAF
git apply $REPO/MXL_SPICE_fixes/OpenVAF.llvm-overview-nul.patch     # REQUIRED, see above
LLVM_CONFIG=$E/bin/llvm-config CC=/usr/bin/gcc CXX=/usr/bin/g++ \
  RUSTFLAGS="-Clink-arg=-L$E/lib -Clink-arg=-Wl,-rpath,$E/lib" \
  cargo build --release --bin openvaf

# the deliverable
cd $SPICE_ROOT/src && git clone https://github.com/dwarning/VA-Models
for v in vacode110 vacode111 vacode; do
  (cd VA-Models/code/bsimcmg/$v && \
   LD_LIBRARY_PATH=$E/lib $CARGO_TARGET_DIR/release/openvaf bsimcmg.va \
     -o $SPICE_ROOT/osdi/bsimcmg_$v.osdi)
done
ln -sf bsimcmg_vacode110.osdi $SPICE_ROOT/osdi/bsimcmg.osdi

# stage 3
python examples/device_leakage_spice.py
```

**Xyce was never needed.** The fallback is not required and should not be started.
