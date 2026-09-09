# Vendored device model card — provenance

## What is here

`models/asap7_7nm_TT.pm` — the **ASAP7** 7 nm FinFET predictive PDK model card, typical-typical
corner, BSIM-CMG version 107, eight device flavours (`{n,p}mos_{lvt,rvt,slvt,sram}`).

| | |
|---|---|
| Source | `The-OpenROAD-Project/asap7_pdk_r1p7`, `models/hspice/7nm_TT_160803.pm` |
| Retrieved | 31 August 2026 |
| Licence | **BSD 3-Clause**, Copyright 2020 Lawrence T. Clark, Vinay Vashishtha, or Arizona State University — retained verbatim in the file header |
| Reference | L. T. Clark, V. Vashishtha et al., "ASAP7: A 7-nm finFET predictive process design kit", *Microelectronics Journal* 53 (2016) 105–115 |

The BSD licence permits redistribution with the copyright notice, which the vendored file carries,
so unlike the floorplan pack this file **is** tracked in the repository.

## The one local edit

```
-.model nmos_rvt nmos level = 72
+.model nmos_rvt nmos level = 17
```

`level = 72` is HSPICE's number for BSIM-CMG; `level = 17` is ngspice's. Applied to all eight
`.model` lines and nothing else — verify with a diff against the upstream file. No parameter value
was changed.

## `[!]` Why ASAP7 and not PTM

The work item said "PTM SPICE cards". **`ptm.asu.edu` no longer resolves**, so PTM cannot be
retrieved. ASAP7 is the same Arizona State group's successor 7 nm work: published, peer-reviewed,
openly licensed, and a closer match to the modelled node than any surviving PTM bulk card (PTM's
bulk series stops at 45 nm; below that it is PTM-MG, which is BSIM-CMG like this one).

## `[!]` The card IS simulated now — this section is kept as history

**Superseded 31 August 2026.** What used to be here said no simulator on this machine could
evaluate BSIM-CMG: conda-forge's `ngspice-41` is built without it *and* without OSDI, there is no
`xyce` package, and OpenVAF ships no binaries. All three were true, and none of them is a
permanent obstacle:

`docs/BSIMCMG_TOOLCHAIN.md` builds ngspice 47 from source **with** OSDI and compiles the BSIM-CMG
Verilog-A with OpenVAF (which needed a one-character bug fix of its own,
`MXL_SPICE_fixes/`). `HotGauge/power/spice_sim.py` runs **this file** in it, and
`examples/device_leakage_spice.py` produces `docs/evidence/device_leakage_spice_asap7.json`.
See §P0.13.

`HotGauge/power/device_leakage.py`'s analytic off-state model is still there, but as an
independent cross-check rather than the answer — and the simulation showed its cold end was wrong,
because it omits GIDL and GIDL turns out to dominate below ~250 K.

### `[!]` What the simulator does with the one local edit

The `level = 17` renumbering above is **inert under OSDI**: an OSDI model is selected by its
Verilog-A module name, not a level number, so the generated deck writes
`.model nmos_rvt bsimcmg ...` and drops `level` entirely. The vendored file is still never
rewritten in place — `spice_sim.render_model_card()` builds a fresh deck from the parsed
dictionary, so this file's provenance stays exactly as retrieved.

### `[!]` Three parameters the compiled model does not accept

ngspice reports `capmod`, `coremod` and `version` as unrecognized. These are **switches BSIM-CMG
removed after version 107**, which this card declares — they are not values being silently
dropped. The evidence that nothing important went with them is that BSIM-CMG 110.0.0, 111.2.1 and
the Xyce-flavoured tree, which reject slightly different sets, agree on the normalised curve to
**0.37 %**.
