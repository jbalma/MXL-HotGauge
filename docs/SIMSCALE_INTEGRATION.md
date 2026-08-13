# Using the SimScale baffled-fin study as MXL-HotGauge's server-class sink

**Yes — this solves the gating problem**, and the `Scripts/` geometry turned out to matter more
than the write-up itself: it makes the coefficients mechanistically interpretable rather than
just empirical.

`docs/FAN_SELECTION.md` concluded we could *recommend* a server fan but not *use* one, because
our only calibrated heatsink is HS483 — a 60 mm open desktop tower valid only over 1.0–4.1 m/s
([HS483.mo:81](../3d-ice/heatsink_plugin/heatsinks/HS483/HS483.mo#L81)). The SimScale study is a
baffled fin stack characterised over 10–200 CFM at 290 W + 70 W: server geometry, HPC power.

Implemented in [sink_models.py](../HotGauge/HotGauge/thermal/sink_models.py) as `BaffledFinSink`
and the `simscale_*` functions; driven by [simscale_hpc_study.py](../examples/simscale_hpc_study.py).

## The geometry (`Scripts/Chip_core_fin_groups.py`)

| | |
|---|---|
| die | 20 × 20 mm = **400 mm²**, 0.5 mm thick |
| cores | 4×4 = 16 cores of 2 × 2 mm (64 mm², 16% of die) |
| hotspots | one **200 µm × 200 µm** per core; 0.64 mm² total, **0.16% of die** |
| heatsink | base 40 × 60 × 2 mm; 4 fins of 8.57 × 40 × 100 mm |
| wetted fin area | 38,000 mm² = 0.038 m² — **95× the die footprint** |

Power densities at the study point (290 W core + 70 W functional-unit):

| coarse-graining | density |
|---|---|
| die average | 0.900 W/mm² |
| core area | 4.53 W/mm² |
| **hotspot** | **109.4 W/mm²** (4.375 W per 200 µm spot) |

This is a direct confirmation of the coarse-graining point: the same chip is 0.9, 4.5, or
109 W/mm² depending only on the scale you average over. The SimScale model resolves
functional-unit-scale hotspots, so its `beta` is a genuine hotspot coefficient.

## The decomposition — the important result

Fitting `alpha(v) = R_cond + amp · v^-n` to both coefficients (max residual 0.011 K/W):

| | conduction floor | convective @ 10 CFM | @ 88 CFM | @ 200 CFM |
|---|---|---|---|---|
| **alpha** (distributed) | 0.2018 K/W | 0.595 | 0.076 | 0.035 |
| **beta** (hotspot) | 1.2442 K/W | 0.653 | 0.070 | 0.030 |

Two things fall out.

**The convective terms are essentially identical** (0.076 vs 0.070 K/W at 88 CFM) — as they
must be, since both paths end at the same fins. So the entire `alpha`/`beta` gap lives in the
conduction floor.

**`beta − alpha` = 1.042 K/W is a pure constriction resistance** — the spreading resistance
between a 200 µm source and the bulk of 0.5 mm silicon. It is a conduction term, so it is
*completely unaffected by airflow*. This is the mechanistic reason no fan can fix a hotspot,
and it is a much stronger statement than the empirical "beta saturates" observation: it is not
that air cooling is *inefficient* at the hotspot, it is that the hotspot's dominant resistance
is not in the air path at all.

At the study's design point this dominates the thermal budget:

| | 88 CFM (35 W fan) | 200 CFM (215 W fan) |
|---|---|---|
| total rise above ambient | 174.0 K | 155.6 K |
| — constriction (airflow-immune) | **73.0 K (42%)** | **73.0 K (47%)** |
| — convective (what the fan buys) | 27.5 K (16%) | 12.7 K (8%) |

Going from a 35 W fan to a 215 W one — **6× the fan power** — removes 15 K of the 174 K rise.
The 73 K sitting behind the constriction does not move at all, and grows as a *share* of the
problem the harder you blow. The only place that heat can be removed is at the hotspot itself,
upstream of the constriction, which is exactly what photonic MR does.

It also shows air cooling is nearly *done* by 88 CFM: convection is 0.076 K/W against a
0.202 K/W conduction floor for distributed power, and 1.244 K/W for hotspot power. With 95× the
die area in wetted fin surface, convection was never the bottleneck.

## Correction: alpha is end-to-end, and must not be used as the sink boundary

`alpha` is a **die-peak-to-air** resistance that already contains the SimScale die's own
conduction and spreading. My first implementation handed it to 3D-ICE as the `top heat sink`
resistance, which double-counts the die path — 3D-ICE derives that itself from the floorplan.
The symptom was unmistakable: a 100 W die "ran away" where the CFD fit put it at a comfortable
48 °C.

`BaffledFinSink` now presents `simscale_convective_r_th(cfm)` — the airflow-dependent term
only. `alpha` and `beta` are kept as **validation targets**: an end-to-end solve on a
comparable die should reproduce them, and `beta − alpha` predicts a hotspot penalty our
floorplan model should produce independently. That cross-check is worth more than using them
as inputs would have been.

## Validated against the source data

`docs/SimScale/data/tT0.dat` is a 46,928-point `(P_core, P_FU, T_max)` grid spanning 0.1–509 W
and 0.1–109 W. A bilinear least-squares fit returns

    T = 19.8500 + 0.270726 · P_core + 1.314024 · P_FU

with **zero residual** — so these are the study's own coefficients, not a re-fit, and the
intercept reproduces its stated `T_0 = 19.85 °C` exactly. Inverting the decomposition gives
~98 CFM from α and ~88 CFM from β, so this is the 100 CFM case.

Three things check out:

| | digitised | exact | error |
|---|---|---|---|
| α @ 100 CFM | 0.2700 | 0.270726 | −0.27% |
| β @ 100 CFM | 1.3050 | 1.314024 | −0.69% |
| **β − α** | **1.0424** | **1.0433** | **−0.09%** |

The third row is the one that matters. The constriction resistance — the whole basis of the MR
argument — was derived from the *shape* of two curves read off a figure, and an exact source
point confirms it to 0.09%. **That argument does not rest on the digitisation.**

`data/tCOP1b.dat` pins the "off" scenario at the same airflow, also with zero residual:
`T = 19.8500 + 0.271718·P_core + 0.000000·P_FU`. The P_FU coefficient is *identically* zero,
which is what "hotspot fully cancelled" means, and comparing the two grids verifies the
write-up's claim that α_on and α_off are superposed — 0.270726 vs 0.271718, a 0.37% difference.
That is what lets Eq. (4)'s `P_core` bracket collapse to a single α.

The remaining α/β values are still digitised; only this airflow is pinned exactly.

## First coupled results — and what the gap is *not*

Running the corrected sink through the leakage loop on the 34-core (101 mm²) die:

| P_die | CFM | T_lin (CFD) | T_fb (coupled) | gap | our on-die R | SimScale on-die R | ΔP_leak |
|---|---|---|---|---|---|---|---|
| 100 W | 88 | 48.1 °C | 88.3 °C | +40.3 K | 0.606 K/W | 0.206 K/W | **0.33 W** |
| 100 W | 200 | 42.9 °C | 84.2 °C | +41.3 K | 0.608 K/W | 0.195 K/W | **−0.02 W** |
| 200 W | 88/200 | 76.2 / 65.9 °C | — | — | — | — | RUNAWAY |
| 290 W | 88/200 | 101.6 / 86.6 °C | — | — | — | — | RUNAWAY |

**The +40 K gap at 100 W is not leakage.** Leakage grew by 0.33 W and −0.02 W — essentially
nothing. It is die geometry: our floorplan's on-die resistance is ~0.607 K/W against SimScale's
~0.20 K/W, about **3× worse**, on a die 4× smaller running LINPACK concentrated in the FPU/AVX
blocks rather than SimScale's uniform cores plus discrete 200 µm hotspots. Reporting that gap as
a leakage effect would have been wrong, and the study script now breaks the two out separately
so they cannot be confused.

A useful consistency check falls out: our on-die resistance is 0.606 vs 0.608 K/W across a 2.3×
change in airflow — airflow-independent to 0.3%, exactly as a conduction term must be. That the
split behaves this way is evidence the convective/conduction decomposition above is right.

Leakage does take over, but only at the cliff: at 200 W the loop grows power 10.8× and at 290 W
a single block (`core_other_0`) hits 7548 K on the first iteration. Those are genuine
leakage-driven runaways, and the CFD's linear fit places every one of them at a comfortable
66–102 °C. That is the structural blind spot — the linear model cannot represent a state that
does not exist.

The 200 W+ runaways are not yet a fair test, though: 200 W on 101 mm² is 2 W/mm² die-average
against SimScale's 0.9. A like-for-like comparison needs a ~400 mm² die, and our largest is
196 mm² (70-core).

## Fan bands

Three fans, each linear over the band where it is cheapest, with jumps at ~88 CFM (35 → 87 W)
and ~133 CFM (100 → 177 W). Identified from `Mathematica_files/Results_3.nb` as ×4 banks of the
PFB0412EHN-TP06, FFB0412EN-00Y2E, and PFB0412EN-E — the same parts analysed in
[FAN_SELECTION.md](FAN_SELECTION.md), so the two studies join up. The notebook's zero-flow
intercepts (20.72 W, 99.52 W) match the digitised 18 W and 100 W.

Note the ordering: **the cheap band is the least efficient fan** (η = 0.125), and the efficient
one (0.263) only appears in the most expensive band. "Cheap" means low absolute power, not
efficient use of it.

## Pipeline changes this forced

Scaling to a die where hundreds of watts is a sane die-average density exposed three limits:

1. **`NO_POWER_UNITS` was hardcoded to 8 cores** (`AVXs_0..7`), so a 34-core floorplan died with
   `KeyError: 'AVXs_10'`. Now matched by pattern. This corrects what I said earlier about the
   trace generalising to arbitrary core count — the *trace* does, but the power model did not.
2. **`grid_for` accepted any exact factorisation**, so 32 cores tiled as a 2×17 strip. Added an
   aspect-ratio guard; 34 cores tiles as a clean 6×6, 70 as 8×9.
3. **Solver failures were reported as thermal runaway.** A missing floorplan file was recorded
   as `DIVERGED` — a configuration bug presented as a physical result. Setup-type exceptions
   now propagate instead.

`replicate_trace_cores` tiles the 8-core McPAT trace onto an N-core floorplan (homogeneous
workload, every core in the same phase — the right assumption for a throughput sweep, wrong for
heterogeneous or phase-shifted work).

## Caveats

* alpha/beta are **digitised** from the write-up figures everywhere except the 100 CFM case,
  which is now pinned exactly against `data/tT0.dat` (see above). The other airflows still
  carry ~0.3–0.7% digitisation error; if a similar grid exists for them, use it.
* `eta_laser` is a **cost multiplier**, not an efficiency: `P_laser = eta_laser · P_extr`, so
  20% ASF means `eta_laser = 5.0` — the reciprocal of `MRParams.eta_asf`. Inverting it makes
  laser cooling look 25× too cheap and moves the COP optimum from 88 CFM to 30 CFM.
* The SimScale fit is **linear in power** — the CFD had no temperature-dependent leakage. That
  is what HotGauge adds, and it is why the two compose rather than duplicate.
* Our largest floorplan is 196 mm² (70-core) against SimScale's 400 mm², so density comparisons
  are not yet like-for-like.
