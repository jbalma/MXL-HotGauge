# MXL fixes to the vendored 3D-ICE tree

`3d-ice/` is gitignored (457 MB, and it is fetched by `get_and_patch_3DICE.sh`), so the four
source files this fork has hand-edited would otherwise exist on one machine and nowhere else.
They live here instead, mirroring their paths under `3d-ice/`, and `apply.sh` copies them in.

**Run `apply.sh` after any fresh `get_and_patch_3DICE.sh`.** Upstream's patch scripts reintroduce
two of the bugs below — they are not merely missing the fixes, they actively undo them.

| File | What was wrong |
|---|---|
| `heatsink_plugin/common/HeatsinkBlocks.mo` | `spreaderX0`/`spreaderY0` were `fixed=false` with no binding equation, so the FMU read `spreaderX0` as **−9.09e+11 µm**. Every one of the 360,000 grid cells fell outside the die and no heat flowed at all. Also gives `initialTemperature` a settable default — it was exported as `calculatedParameter`, which FMI forbids setting, pinning the sink at 288.15 K. |
| `heatsink_plugin/heatsinks/HS483/HS483.mo` | Same `fixed=false` problem for `constantFanSpeed` and `constantAirTemperature`, so fan speed and ambient were garbage. |
| `bison/stack_description_parser.y` | `initialize_pluggable_heatsink` ran from `INITIAL_CONDITIONS`, before the solver had a step time, so the plugin initialised with `StepTime = 0` and the FMU never advanced. Moved to the end of the steady and transient solver actions. |
| `heatsink_plugin/loaders/FMI/fmiwrapper.cpp` | Adds the one-shot `[diag]` geometry print that made the `spreaderX0` corruption visible. Diagnostic only. |

| `sources/thermal_data.c` | Steady state with a pluggable heat sink. Upstream returns `TDICE_SOLVER_ERROR` with a bare `//TODO`. Two of the three obstacles are fixed here: `fill_system_vector_steady` never wrote the spreader rows, and the plugin's heat flow depends on the temperature it is handed so one linear solve cannot close it (now a fixed point). The third is **not** fixed and is the real blocker — see below. |

## Steady + pluggable heat sink: how far it goes

The pluggable sink is the only route to a real heat **spreader** in 3D-ICE (`spreader length,
width, height`), and a spreader is what lets a small die shed heat sideways instead of paying full
vertical resistance through every package layer. Without one the model reproduces an 826 mm² part
and fails a 91 mm² one.

Steady state still does not work, and the reason is structural rather than an oversight:

**Spreader cells have no conductance to ambient.** The plugin contributes heat as a *source*, never
as a matrix coefficient. In transient, `capacity/StepTime` on the spreader diagonal
(`system_matrix.c`, the `if TRANSIENT` branch) keeps the system non-singular. In steady that term
is zero, so the spreader block couples only to its neighbours and the assembled matrix is singular
— a pure Neumann problem with no Dirichlet reference. SuperLU returns NaN.

The fix is to **linearise the plugin into the matrix** rather than the right-hand side: probe it at
two uniform temperatures to recover `g` and `T_ambient` from `Q = g (T − T_ambient)`, add `g` to
the spreader diagonal and `g · T_ambient` to the source. For a linear plugin — and a
fixed-resistance cooling boundary is linear — that is exact, needs no iteration, and preserves the
factorisation so the persistent session cache still works. It requires touching `system_matrix.c`
and storing the probed coefficients on the sink.

Until then this path detects the singularity and reports it, rather than iterating on NaN or
returning a plausible-looking field.

Two of these five — the `fixed=false` bugs — were introduced by Tufts' own
`3dice_rhel9_delta.patch` and `HotGauge.3D-ICE.ThermalInit.patch`.

## Verifying

After applying and rebuilding, the acceptance test should pass — raising fan speed must lower
temperature, and constant power must asymptote rather than drift:

```bash
python examples/fmu_acceptance_test.py
```

Reference numbers from the repaired FMU: 46.26 °C with the fan off versus 45.89 °C at 6000 RPM,
with temperature increments decaying (ratios 0.449, 0.351). Co-simulation is stable only at
`dt <= 0.01 s`, roughly 0.24 s of wall time per step.

## Regenerating the FMU

Editing either `.mo` file means rebuilding the FMU through OpenModelica (1.27 was used):

```bash
cd 3d-ice/heatsink_plugin/heatsinks/HS483 && omc buildfmi.mos
```

The generated `HS483_P14752_*_Interface3DICE/` trees are build products — do not commit them.
