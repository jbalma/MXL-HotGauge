# Fan selection for scaling MXL-HotGauge to HPC hardware

Source data: `docs/Data_sheets/` (Delta PDFs, digitised EFP172 curves, `PQ_123.png`) and
`fan_efficiency_curve_RM.xlsx`. Encoded in `HotGauge/thermal/fan_specs.py`, whose efficiency
calculation reproduces the spreadsheet's `Sheet5` values exactly (0.2628 / 0.1247).

## The candidates

Operating points are the *loaded* points from the spreadsheet or the digitised curves, not the
free-air ratings a datasheet leads with.

| Fan | Size | RPM | CFM (op) | mmH2O (op) | P_elec | eta | Free-air CFM | Max mmH2O |
|---|---|---|---|---|---|---|---|---|
| **PFB0412EN-E** | 40 mm | 32,500 | 22.2 | 96.6 | **37.8 W** | **0.263** | 38 | **188.7** |
| FFB0412EN-00Y2E | 40 mm | 23,000 | 16.0* | 48.0* | 18.0* | 0.198* | — | — |
| PFB0412EHN-TP06 | 40 mm | 16,000 | 11.7 | 15.1 | 6.6 W | 0.125 | — | — |
| **EFP172** | 172 mm | 2,500 | 150 | 6.7 | 21.0 W | 0.223 | **315** | 17.8 |
| San Ace 80 (9P) | 80 mm | ~3,000 | 20* | 2.0* | 2.5 W* | 0.074* | 35 | 3.7 |
| P14752 (HS483's own) | 40 mm | 6,000 | — | — | ~2 W | — | — | — |

`*` estimated — the FFB0412EN and PFB0412EHN-TP06 spec tables are scanned images, and the San
Ace figures are read off a P-Q plot. Measure before relying on them.

## Recommendation

**PFB0412EN-E for the die-level heatsink; EFP172 for the chassis stage.** They are not
alternatives — a real HPC node runs both, in series, and they solve different problems.

Scaling die power and core count is a **static-pressure** problem, not a flow problem. More
power in the same socket means a taller, denser fin stack, which means higher flow impedance,
and only a high-pressure fan can push air through it. That is the whole reason 40 mm screamers
exist. The numbers make the split obvious: the PFB0412EN-E develops **10.6x the static
pressure** of the EFP172 at **0.12x the flow**. The EFP172 is the bulk air mover that gets
315 CFM through the chassis; the PFB0412EN-E is what forces a fraction of it through the fins.

The PFB0412EN-E is also the best-characterised part in the set — a real loaded operating point
from the spreadsheet rather than a curve reading — and the most efficient at 0.263.

The San Ace 80 (3.7 mmH2O peak) and PFB0412EHN-TP06 (15.1 mmH2O) are case and workstation
parts. Neither has the pressure for a server heatsink.

## Two findings that change the model

### 1. A server fan costs 15-20x what our current model assumes

The HS483's own P14752 is a ~2 W desktop fan. A PFB0412EN-E is **31.2 W nominal, 42 W max**,
and a 1U bank of six is **227 W**. The hybrid optimiser sweeps were run over 1-4 W cooling
budgets — a regime a real server fan cannot even enter, since its minimum draw is ~28 W.

This is strongly in MR's favour and is now backed by datasheet numbers rather than assumption.
In the 23 W eight-core study the MR stage cost **0.4 W net** to remove 0.218 W at the hotspot
and bought +25.9% performance. Against a 37.8 W fan, MR is not a marginal adjustment to the
cooling budget; it is two orders of magnitude cheaper per watt of hotspot heat moved. The
reason is structural: the fan cools the whole die to get at one hot block, while MR is applied
where the heat is.

### 2. We cannot bolt a server fan onto HS483 — the correlation forbids it

The HS483 Modelica model asserts its HTC correlation is valid only for fin velocities of
**1.0 to 4.1 m/s** (`HS483.mo:81`), and its fan model `Q = (RPM/9.55) x 5.98e-5 x 0.9`,
`v = Q/8.31e-3` maps that to 1474-6045 RPM — exactly the range our calibration measured:

| P14752 RPM | v (m/s) | R_th (K/W) |
|---|---|---|
| 1,500 | 1.02 | 0.8525 |
| 3,000 | 2.03 | 0.7472 |
| 4,500 | 3.05 | 0.7012 |
| 6,000 | 4.07 | 0.6853 |

Two things follow. First, **the curve has already saturated**: 4x the flow buys only 20% less
resistance, and the last 1500 RPM buys 2%. Second, a six-fan PFB0412EN-E bank would drive
7.58 m/s through that flow area — **outside the validated correlation**, where the model would
assert rather than extrapolate.

So the fan recommendation cannot be applied in isolation. HS483 is a 60 mm open desktop tower;
a 40 mm high-pressure fan is the wrong fan for it, and would in fact underperform its own
P14752. Adopting a server fan requires a **matched server heatsink model** — short, dense,
ducted, with an HTC correlation fitted over a higher velocity range.

## Refinement from the SimScale study

`docs/SimScale/Write_up/` supplies the server heatsink model this section called for, and it
changes the framing of the fan question. That study did not pick one fan: it used **three**, in
bands, because no single part covers 10–200 CFM through a baffled fin stack, and took the
lower envelope of their power–flow curves. The envelope is discontinuous — each fan runs out of
flow and the next one up costs far more even at the same operating point (35 W → 87 W at
90 CFM, 100 W → 175 W at 135 CFM). Those jumps, not the fan efficiencies, are what set the
study's optimum.

So "which fan" is really "which band", and the PFB0412EN-E recommendation stands for the
die-level, high-impedance end of that ladder. See [SIMSCALE_INTEGRATION.md](SIMSCALE_INTEGRATION.md).

## Next step

Re-run the hybrid optimiser against the SimScale α/β surrogate rather than HS483, with
realistic fan costs. Until then the optimiser's absolute P_fan : P_MR split (2:2 at a 4 W
budget) reflects a desktop fan's economics. The qualitative result — an interior optimum, with
MR rescuing a thermally-throttled die that fan speed alone cannot — holds, and a realistic fan
cost moves that optimum further toward MR, not away from it.

`fan_specs.py` provides `at_rpm` / `rpm_for_power` (affinity laws: Q ~ N, dP ~ N^2, P ~ N^3)
and `fan_bank(spec, n)` for parallel banks. Affinity scaling is valid *within* a design only:
the two PFB parts differ by 2.03x in speed but 6.4x in static pressure because they are
different blade designs, not one fan at two speeds.
