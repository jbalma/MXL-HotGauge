# Patches to the BSIM-CMG toolchain

Same convention as `MXL_3DICE_fixes/`: the build trees under `spice_toolchain/` are gitignored
and fetched by script, so any edit made to them has to live here or it is lost the next time the
tree is re-cloned. One patch so far.

Rebuild instructions, and the environment preamble that has to precede them, are in
`docs/BSIMCMG_TOOLCHAIN.md`; `scripts/spice_env.sh` is that preamble.

---

## `OpenVAF.llvm-overview-nul.patch` — OpenVAF segfaults on **every** input without it

**Symptom.** `openvaf --version` works, a syntax error is reported correctly, and then *any*
successful parse ends in `Segmentation fault (core dumped)` with no message — including a
five-line Verilog-A diode. That pattern (front end fine, code generation dead) reads like a broken
LLVM link, and roughly a day can be spent rebuilding LLVM against it.

**Cause.** It is not the link. `openvaf/llvm/src/initialization.rs:105` passes LLVM's
`ParseCommandLineOptions` an `overview` string built as `b"".as_ptr()`. A zero-length byte-string
literal has no allocation, so rustc is free to give it a *dangling* aligned pointer — in this
build, literally `0x1` — and it is **not NUL-terminated either way**. LLVM hands it to `strlen`.

```
Program received signal SIGSEGV
0x00007ffff7b5413c in ?? () from /lib/x86_64-linux-gnu/libc.so.6   <- strlen, AVX-512
=> 0x7ffff7b5413c:  vpcmpeqb (%rdi),%ymm16,%k0
rdi  0x1
#1  LLVMParseCommandLineOptions ()
#2  llvm::initialization::configure_llvm (...) at openvaf/llvm/src/initialization.rs:102
```

`[!]` This is **undefined behaviour in OpenVAF, not a local misconfiguration**. It is latent
everywhere and faults only where the dangling pointer lands in an unmapped page — which is why
upstream's docker image works and this build did not. Do not go looking for a toolchain fix.

**Fix.** One character: pass `b"\0"`, a genuine NUL-terminated empty string.

**Verify.** `openvaf diode.va -o diode.osdi` on any trivial module must exit 0 and write the
`.osdi`. Before the patch it segfaults; there is no partial-success state to confuse the two.
