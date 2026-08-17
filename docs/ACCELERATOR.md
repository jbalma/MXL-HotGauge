# Microrefrigeration on a real accelerator die

**17 August 2026.** Results from `examples/accelerator_study.py` on the GA100 floorplan in
`HotGauge/HotGauge/thermal/accelerator_floorplan.py`. This is item 5 of the next-steps list: a
real accelerator floorplan to replace the power-redistribution proxy.

## Why the proxy was not enough

Every accelerator claim in this project up to now came from taking the Sniper/McPAT CPU floorplan
and pushing each core's power into its FP units (`clock_search.emphasise_units`). That varies the
**power map** and cannot vary the **geometry** — and the degeneracy results turned out to be about
geometry. The proxy could answer "what if a core's power were concentrated?" and could not answer
"what does an accelerator's die actually look like thermally?".

## The floorplan

Built from the SemiAnalysis / Locuza annotated die shots in `docs/chip_design_lit/die_images/`:

* **GA100 (A100, TSMC 7 nm)** — 826 mm² without scribe lines; 1× TPC (2× SM) = 6.86 mm²;
  512 KB L2 tile = 1.24 mm²; 48 MB L2 = 122.6 mm²; 16× PCIe 4.0 PHY = 5.24 mm². Arrangement:
  8 clusters of 16 SM, 96 L2 tiles in two central spines, 6 HBM2e PHY and 4 groups of
  3× 512-bit memory control alternating along the top and bottom edges, 4 NVLINK PHY down the
  left, PCIe/video/control down the right.
* **GA102** — for the one number GA100's shot does not give: the SRAM fraction *inside* a compute
  tile, **33.36%** (0.294 of 0.881 mm² for an SM with its 128 KB L1). Without it the finest
  structure on the die would be 3.4 mm² and no hotspot smaller than a whole SM could exist by
  construction.

Result: **367 blocks**, 32.39 × 25.50 mm, closing on the measured 826 mm² — 53% SM, 14% L2, 32%
lumped into PHY, controllers, routing and control. Same node class as the CPU die already modelled,
so the comparison is iso-node.

The outline is fixed by the measured area and aspect, the SM tile height by the 16-tall
arrangement, and its width by the SM's own measured area — so the interior width is a *prediction*
of the arrangement rather than a fit, and `ga100_consistency()` reports the closure.

### What is assumed

Areas, counts, arrangement and the SRAM fraction are measured. **The per-class power split is
not**, and cannot be — die-shot analysis gives areas, not dissipation, and there is no public
per-block power breakdown for GA100. `GA100_POWER_SPLIT` states it with reasoning per entry
(SM 0.60, L2 0.08, HBM PHY 0.13, memory control 0.07, NVLINK 0.05, PCIe/uncore 0.07),
`calibrated` is False everywhere, and `power_split_sensitivity()` renormalises one share against
the rest so anything leaning on it gets an error bar.

At 400 W that split gives:

| class | n | W | mm² | W/mm² |
|---|---|---|---|---|
| memory control | 4 | 28.0 | 33.3 | **0.841** |
| HBM PHY | 6 | 52.0 | 70.4 | **0.739** |
| SM datapath | 128 | 204.0 | 287.7 | 0.709 |
| NVLINK | 4 | 20.0 | 33.5 | 0.598 |
| L2 | 96 | 32.0 | 120.4 | 0.266 |
| SM L1/SMEM | 128 | 36.0 | 149.4 | 0.241 |
| PCIe/uncore | 1 | 28.0 | 131.6 | 0.213 |

Note the die average: **0.484 W/mm²**, less than half the 1.05–1.17 W/mm² band where the CPU die's
stability cliff lives. An 826 mm² part spreads heat well. **An accelerator's thermal problem is
total power, not density.**

## The result: the die is almost perfectly degenerate

The prediction was written into the module docstring before the run, because it is falsifiable:
with 128 near-identical tiles the plateau should hold most of the SMs and clipping one should buy
essentially nothing.

400 W, 88 CFM air, dt_max 10 K:

| | 34-core CPU (balanced) | 34-core CPU (concentrated + turbo) | **GA100** |
|---|---|---|---|
| blocks within dt_max of peak | 15 | 2 | **332 of 367** |
| clip-one gain | 1.25 K | 9.86 K | **0.040 K** |
| as % of device capability | 12.5% | 98.6% | **0.4%** |
| blocks to clip for the full dt_max | 15 | 2 | **332** |

**All 128 SM datapaths are inside the plateau, spanning 8.3 K.** The compute array is effectively
one thermal entity. There is no hotspot for a hotspot policy to find: 22× the degeneracy of the
balanced CPU die, and a clip-one gain 31× smaller.

Per class, at the 400 W point (peak 88.06 °C):

| class | n | max °C | min °C | spread K | in plateau |
|---|---|---|---|---|---|
| HBM PHY | 6 | 88.06 | 79.93 | 8.13 | 6 |
| memory control | 4 | 88.02 | 83.92 | 4.10 | 4 |
| SM datapath | 128 | 87.44 | 79.13 | 8.31 | **128** |
| NVLINK | 4 | 86.94 | 86.39 | 0.56 | 4 |
| SM L1/SMEM | 128 | 85.50 | 75.81 | 9.69 | 114 |
| L2 | 96 | 83.73 | 77.44 | 6.29 | 76 |
| PCIe/uncore | 1 | 73.05 | 73.05 | 0.00 | 0 |

### The peak is not compute

It is **HBM_PHY_B0 — a memory PHY on the die perimeter.** The assumed split makes the memory
interface denser than the SM datapath and the solve keeps it there. So the one block worth clipping
is I/O, sitting on the edge of the die where the package spreads heat best.

This one *does* depend on the assumed split, which is why the sensitivity exists: at 0.5× the HBM
share the memory interface falls to 0.369 W/mm² and compute becomes the densest class. The
**332-block plateau does not depend on it** — the SM tiles are uniform under any split, so their
degeneracy is a property of the geometry.

### Robustness

The plateau and clip-one gain are **unchanged** across every assumption varied so far:

| variant | blocks | peak °C | peak class | plateau | clip-one |
|---|---|---|---|---|---|
| 400 W air (baseline) | 367 | 88.06 | HBM PHY | 332 | 0.040 K (0.4%) |
| leakage fraction 0.40 (vs 0.25) | 367 | 88.06 | HBM PHY | 332 | 0.040 K |
| leakage distributed by area | 367 | 88.06 | HBM PHY | 332 | 0.040 K |
| SM not split into datapath + L1 | 239 | 87.79 | memory control | 233 | 0.073 K (0.7%) |

Identical to four significant figures across both leakage assumptions — at 88 °C the leakage
feedback is weak (the solve converges in 2 iterations), so it cannot move the answer.

The unsplit control is the interesting one. Splitting each tile *does* create finer structure — the
plateau fraction falls from 97.5% to 90.5% and the clip-one gain roughly halves — which confirms
the split matters and that the plateau is not merely an artefact of coarse blocks. But both sit
under 1% of device capability, so the conclusion does not move.

## Pushing the density: degeneracy weakens, but nowhere near enough

400 W is only 0.484 W/mm². The CPU die's stability cliff is at 1.05–1.17 W/mm², so the obvious
question is whether an accelerator driven into that band starts to look like a CPU. It does not.

| point | W | W/mm² | cooling | peak °C | plateau | clip-one | % of capability |
|---|---|---|---|---|---|---|---|
| A100 class | 400 | 0.484 | 88 CFM air | 88.06 | 332 | 0.040 K | 0.4% |
| H100 class | 700 | 0.847 | 88 CFM air | 127.85 | 170 | 0.070 K | 0.7% |
| H100 class | 700 | 0.847 | liquid, 0.05 K/W | 108.91 | 178 | 0.173 K | 1.7% |
| matched to CPU | 826 | 1.000 | liquid, 0.05 K/W | 122.21 | 127 | 0.204 K | 2.0% |
| matched to CPU | 950 | 1.150 | liquid, 0.05 K/W | 135.29 | 104 | 0.235 K | **2.3%** |

Every point above is damping-verified (`unconverged: False`).

The trend is real and in MR's favour: 2.4× the density narrows the plateau from 332 blocks to 104
and raises the clip-one gain ~6×. But it rises **from 0.4% to 2.3%** of device capability. At the
density where the CPU die sits on the edge of runaway, the accelerator's best single-block clip is
still worth a quarter of a kelvin, and **five times worse than the *balanced* CPU die's 12.5%** —
which was itself the case where the conclusion was "MR is weak as a clock enabler".

### The structural result: this die does not run away

The more important number in that table is the one that is missing. **Nothing diverged.** At
1.15 W/mm² the 34-core CPU die has *no steady state at all* — that is the entire basis of the
rescue result, 0.81 W removed to stabilise a die that otherwise runs away. The accelerator at the
same density reaches 135 °C and **converges**.

So the accelerator fails a different way. It fails by **exceeding its temperature limit**, not by
losing its steady state. 826 mm² spreads laterally far better than 101 mm², and the leakage
feedback is diluted across eight times the area, so the local positive feedback that drives the CPU
die unstable never closes.

That matters because MR's one demonstrated strength in this whole project is *arresting the leakage
instability* — 290 W of die stabilised per watt removed. On this die there is no instability to
arrest. **The same geometry that makes an accelerator degenerate also makes it stable**, so both of
MR's routes to value close at once, for the same reason.

## What this means for microrefrigeration

**Hotspot MR is structurally the wrong tool for an accelerator**, and the two independent arguments
land on the same side:

1. **No hotspot to clip.** 332 of 367 blocks within dt_max of the peak; clipping one buys 0.4% of
   the device's capability, rising only to 2.3% when driven to 1.15 W/mm². The mechanism needs a
   localised peak and a uniform tile array does not have one.
2. **No instability to rescue.** The die converges at densities where the CPU die does not, so the
   one application where MR was measured to be strongly worth buying does not arise.

On this die MR must be **distributed** or it does nothing at all, which makes the original instinct
about "localized cooling across the die average path" the only version of the idea with a route
here. That is a harder sell: distributed cooling competes directly against the heatsink on cost per
watt, at an electrical COP of 0.14. The CPU-side margin curves (`docs/MR_RESCUE_COST.md`) show what
happens when MR has to cool a whole plateau — 27–34 W removed and 48–60 W electrical, against
0.17–0.81 W when it only clips the top few blocks.

The honest summary is that the accelerator is a *worse* MR target than the CPU on every axis
measured, and for a reason that is intrinsic to what an accelerator is rather than incidental to
this particular part.

## Open, and what would change the picture

* **The power split.** The only way to fix it properly is a measured or vendor-published per-block
  breakdown. Until then the peak's identity is provisional, though the plateau is not.
* **Non-uniform activity.** Power is shared equally within a class deliberately, so that any
  hotspot comes from *geometry* rather than from an imbalance assumed into the input. Real kernels
  do not load 128 SMs identically, and a sufficiently skewed one might create a genuine hotspot.
  That is the most promising remaining avenue for MR on an accelerator and it is not yet measured.
* **Grid.** The 100 µm default is required by the die's size (826 mm² at 50 µm is ~330k cells per
  layer, near the SuperLU wall the deep stacks hit). Coarsening understates peaks on small blocks,
  so a 50 µm run is queued to check the plateau is not an artefact of it.
* **The die shots are of GA100 specifically.** A tiled accelerator with a different L2 topology, or
  a chiplet part like MI300, could break the symmetry differently — the `die_images` directory has
  MI300 and Navi31 shots, and the module's structure is parameterised enough to take another.
