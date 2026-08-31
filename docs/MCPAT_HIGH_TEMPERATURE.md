# Can we model a die above 400 K, and what would fixing McPAT cost?

**30 August 2026.** Written because the corrected loop model
(`docs/evidence/loop_model_reconciliation.json`) puts the entire architecture argument *above* the
temperature McPAT will simulate, so "is that limit real?" stopped being a curiosity.

## The short answer

**Mostly you do not need to fix McPAT, and forking it is the wrong place to spend the effort.**
McPAT is not in the temperature loop. It runs **once**, offline, to produce a power trace with
leakage extracted at a reference temperature — `DEFAULT_TREF_K = 360 K`, comfortably inside the
300–400 K window. From there the feedback loop scales leakage with **this project's own
`LeakageModel`** and calls 3D-ICE, which has no temperature ceiling at all. Verified: nothing in
`converge_power_temperature` invokes McPAT or a subprocess.

So the 400 K bound constrains **the reference extraction point, not the operating temperature**.
What actually binds above 400 K is the validity of *our* leakage model, which is about a hundred
lines of our own code rather than a C++ fork.

## What the limit actually is

One bounds check:

```
McPAT/cacti/io.cc:1547
  if (temp < 300 || temp > 400 || temp%10 != 0)
    cerr << "Temperature must be between 300 and 400 Kelvin and multiple of 10."
```

It is not arbitrary. It guards the extent of a tabulated dataset:

```
McPAT/cacti/technology.cc:194
  double I_off_n[NUMBER_TECH_FLAVORS][101];        // slots for 300..400 K
  ...
  I_off_n[0][0]  = 7e-10;   // 300 K
  I_off_n[0][10] = 8.26e-10;// 310 K
  ...  only indices 0,10,20,...,100 are ever assigned
```

**101 slots, 11 populated.** That is why `temp % 10 != 0` is rejected — the intermediate slots hold
uninitialised memory. Consumption is `I_off_n[tech][g_ip->temp - 300]`, a direct index with no
interpolation. `I_g_on_n` is tabulated the same way, and the pattern repeats per technology node
(77 `I_off_n[0][k]` assignments across the file) and per tech flavour.

The original values came from MASTAR — the source comments say so, and note the Vdd scaling was
never curve-fitted properly either.

## Three tiers of effort, and what each buys

**Tier 1 — remove the `%10` restriction. Hours.** Interpolate between the 11 existing points
instead of indexing directly, and drop that clause from the bounds check. No new physics; it just
stops the reference temperature having to snap to a multiple of 10. Low value but nearly free.

**Tier 2 — extend to ~500 K by fitted extrapolation. Days.** Enlarge the arrays, and generate
`I_off`/`I_g_on` at 410–500 K by fitting the subthreshold form to the existing 11 points:
`I_off ∝ T² exp(−V_th(T)·q/(n k T))` with `dV_th/dT ≈ −0.5 … −1 mV/K`. This is defensible, must be
labelled extrapolation, and is the same physics our `LeakageModel.from_table_extrapolated` already
implements on the Python side — which is an argument for doing it **there instead**, where it is
already exercised and tested.

**Tier 3 — a genuine re-parameterisation above 500 K. Weeks to months, and probably wrong.**
This is where the effort stops being worth it, for a reason that is not about effort:

> **Silicon at 600 K is not a switch.** Intrinsic carrier concentration rises steeply, junction
> leakage overtakes subthreshold conduction, and the on/off ratio collapses. BSIM and MASTAR were
> never fitted in that regime. Extending CACTI's silicon tables to 600 K would produce numbers,
> and they would describe a device that does not work.

And the architecture's hot zone does not propose hot *silicon* — it proposes SiC or GaN. CACTI
cannot represent those at all: different bandgap, mobility, dielectric constant, and a device
structure its models do not parameterise. **That is a materials claim, and no amount of fixing
McPAT will let this toolchain evidence it.**

## What to do instead

1. **Put the work in `HotGauge/power/leakage.py`, not McPAT.** `from_table_extrapolated` already
   exists and already carries an explicit warning that the extrapolated region is uncertain. Extend
   and validate *that*, and the whole pipeline gains high-temperature behaviour without touching
   C++.
2. **Settle it with PTM SPICE cards.** This is the same work item already identified as highest
   value for the *cold* zone, where our curve flattens at 310 K and the architecture assumes it
   keeps falling to 200 K (a ~2.3× uncertainty on 13.5 % vs 31.7 % of die power). **One SPICE
   campaign settles both ends of the three-zone template** — the cold zone's prize and the hot
   zone's leakage — and neither needs McPAT modified.
3. **Note what needs no power model at all.** The exergy side is already unconstrained: `φ = 1 −
   T₀/T_h` needs only a temperature, and 3D-ICE will solve to any temperature asked. Every claim in
   `loop_model_reconciliation.json` — including the whole `η_ASF`-vs-`T_h` design curve — is
   already computable today. What is missing above 400 K is the **power map**: how much heat there
   is to lift, and how leakage redistributes it.
4. **Be explicit about the silicon ceiling in proposal text.** Somewhere around 450–500 K the
   question stops being "can we model this" and becomes "what device is this". Claiming simulated
   support for a 600 K silicon die would not survive review.

## Why this matters more than it looks

The corrected loop model says the extractor efficiency required for self-powering is:

| T_h | 350 K | 400 K | 450 K | 600 K | 1000 K |
|---|---|---|---|---|---|
| required η_ASF | 1.12 | 0.67 | 0.51 | **0.35** | 0.25 |

**`[!]` Corrected 30 Aug** against v91 (1.16)–(1.17): η_LPC is *eliminated* from the feasibility
condition by substituting its exergy ceiling, so folding it into the coupling term double-counts it.
An earlier version of this table was ~1.6× too pessimistic and claimed η_ASF > 1 was needed below
400 K. It is not: 0.67 at 400 K.

The 400 K ceiling still bites, but as a truncation rather than a wall — the requirement roughly
halves again between 400 K and 600 K, and 400–600 K is exactly the hot-compute zone §10.8 proposes.

**And the materials picture has moved.** Yb:YLF at η_ASF ~0.02–0.035 is superseded for compute
tiles; v91 Table 8.2 gives SMILES-R640-in-polymer and GaAs/GaInP at 10³–10⁴ W/mm², with η_ASF
0.124–0.221 tabulated and >0.30 claimed experimentally. At 0.30 the loop closes at **469 K** for a
90 %-wall-plug laser. The binding term is now **η_P and η_cpl**, not the extractor — which is why
the high-temperature power map, not McPAT's bounds check, is what needs the work.
