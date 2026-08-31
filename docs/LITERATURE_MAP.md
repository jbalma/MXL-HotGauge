# The reference library, and what each source is actually good for

`docs/chip_design_lit/` holds 33 PDFs and 59 die images. Nobody has written down which of them
answers which question, so each session has rediscovered the same few. This is that index, with
the specific findings pulled out — read the finding here first, then open the PDF only if you need
more than the finding.

Written 27 August 2026 while priming the V/F and floorplan work. Every number below was read out
of the source, not remembered.

---

## 1. The device physics the ladder rests on

### Gonzalez, Gordon & Horowitz, *Supply and Threshold Voltage Scaling for Low Power CMOS*, JSSC 32(8), 1997
`design_physics/CMOS_Supply-And-Threshold-Voltage-Scaling-For-Low-Power-CMOS-Solid-State-Circuits-IEE.pdf`

**The canonical source for the V_t lever in `docs/LADDER_GEN0.md`.** It supplies both halves of
the trade the ladder turns on, in closed form:

* **Leakage** — `I_leak = W_eff · I_0 · 10^(−V_t / S)`, S the subthreshold slope. This is exactly
  the `10^(ΔV_t / SS)` relation `IRDSVFModel.leakage_multiplier` implements, so that lever is
  grounded rather than invented.
* **Delay** — `t_d ∝ C·V_dd / (V_dd − V_t)^α`, with **α between 1 (complete velocity saturation)
  and 2 (none)**, and *"for a 0.25 µm technology α is likely 1.3–1.5"*.

**Use it to settle a live discrepancy.** `irds_vf.DEFAULT_ALPHA = 1.4` sits correctly in that band.
But the shipped `performance_model.VF_ALPHA_POWER_FIT` has **α = 0.949 — below the physical floor
of 1.0** — and that is *why* the shipped curve turns over: `f(V) = k(V−V_th)^α / V` only has a
maximum when α < 1, which is what puts a spurious 6.43 GHz ceiling at 9.40 V. An α < 1 fit is not
a slightly-off fit, it is outside the model's own physical range.

Two more things worth having:

* **Logic depth ≈ 30 equivalent inverters** for a modern microprocessor — the bridge from gate
  delay to clock.
* *"Changes in supply voltage, temperature, and threshold voltage affect all gates in the same
  way, so delay of any gate remains roughly proportional to the delay of an inverter"* (Fig. 1,
  curves at −25/25/125 °C). **This is the justification for treating temperature as a uniform
  derate on the critical path** — which is the *form* `FMaxModel.linear_derate` assumes. The form
  is defensible; the project's slope is still uncalibrated.
* The optimum sits at **V_dd < 0.5 V**, but **uncertainty in V_t/V_dd destroys the advantage**
  *"unless active feedback is used to control the uncertainty"*. Temperature is one such source
  of V_t spread, which is a real and unexploited connection to a cooler that holds T_j tightly.

### *Leakage Current: Moore's Law Meets Static Power*, IEEE Computer, Dec 2003
`design_physics/2003.12.Leakage-Current-Moores-Law-Meetings-Static-Power_Computer.pdf`

**Two findings, and the second changes how the ladder's V_t rung should be framed.**

1. **Thermal runaway, named as a mechanism**: *"If I_sub grows enough to build up heat, V_θ will
   also start to rise, further increasing I_sub and possibly causing thermal runaway."* Every
   `diverged` row in the catalogue is this loop. Cite it — the project currently describes the
   behaviour without a reference for the mechanism.
2. **Multi-V_t is already standard practice, not a proposal**: *"Today's processes typically offer
   two threshold voltages. Designers assign a low threshold voltage to a few performance-critical
   transistors and a high threshold voltage to the majority."* Future processes are expected to
   offer three or more. The paper works a cache example: high-V_t address decoders and bus
   drivers, extra-high-V_t bit cells, low-V_t only where speed is critical.

**Why (2) matters.** `LADDER_GEN0.md` currently frames the lever as *lowering V_t globally*. That
is not what anyone would build. The realistic — and far stronger — framing is:

> Multi-V_t assignment is already a **spatial** decision about which blocks get leaky-fast devices.
> LCMR is a **spatial** cooling capability. So the co-design claim is not "lower V_t" but
> **"cool the tiles over the low-V_t blocks, and you can afford low-V_t in more places than a
> conventionally-cooled part can"** — which is simultaneously a floorplan result (§5) and a
> device result (§9), through one mechanism.

That reframing should be made before the V_t rung is run, because it changes what is swept: not a
global ΔV_t, but the *fraction and placement* of low-V_t area under the array.

### Chandrakasan, Bowhill & Fox — *Design of High-Performance Microprocessor Circuits*
`design_of_highperf_microproc_circuits.pdf`

The textbook both papers above cite for the leakage equations (the 2003 article's Eq. 4 is from
here). Go here for the forms with their assumptions stated, if a referee asks where
`10^(−V_t/S)` comes from.

---

## 2. Real product data — the empirical anchor for item 3

### Sun, Agostini, Dong & Kaeli, *Summarizing CPU and GPU Design Trends with Product Data*, arXiv:1911.11313
`design_physics/Unknown_Summarizing-CPU-and-GPU-Design-Trends-with_2.pdf`

**4031 publicly-available products** (2102 CPU + 1929 GPU), from 2000 onwards, each with process
size, die size, transistor count, **base frequency** and **TDP**.

**What it gives**: what clocks real parts actually ship at, per node and per TDP. That bounds the
ladder's claims empirically — if the model says 5 GHz is reachable at a node where no product
exceeds 4, that is a result about the model.

**What it does NOT give**: voltage. It has base frequency only, so it is not a V/F curve. Building
one needs a voltage source — vendor VID/SMU tables, or the roadmap curves below. **Do not present
this dataset as a V/F curve**; it is an f-vs-node-and-TDP dataset.

### IRDS 2023/2024
`roadmaps/IRDS/` — `2023IRDS_AB.pdf`, `2023IRDS_BC.pdf`, `2023IRDS_FAC.pdf`, `2024IRDS_MM.pdf`,
`2024IRDS_SA.pdf`

Already partly ingested: `HotGauge/HotGauge/power/irds_vf.py::IRDS_NODES` carries vdd, V_t, v_dsat,
subthreshold swing, three frequency anchors and dynamic power per GHz for 2024–2037. **Those are
projections, not measurements** — `IRDSVFModel.calibrated` is False on purpose.

Their ceilings are *tighter* than the shipped table's: f_max at the overdrive limit is 3.34 GHz
(2024) to 4.54 GHz (2031). So on the roadmap curves, too, "does LCMR reach 6 GHz" is answered no
for a non-thermal reason.

### NVIDIA H100 Hopper whitepaper · Dally keynote
`design_physics/nvidia-h100-tensor-core-hopper-whitepaper.pdf`,
`design_physics/Keynote Presentation_William Dally [NVIDIA].pdf`

The accelerator reference point. The H100 numbers behind `published_reference.PUBLISHED_POINTS`
come from here and from arXiv:2507.16781.

---

## 3. Floorplans and architecture — item 5

### *Hot Chips 34 — Intel's Meteor Lake Chiplets, Compared to AMD's*
`design_physics/Hot Chips 34 – Intel's Meteor Lake Chiplets, Compared to AMD's.pdf`

Meteor Lake is **four tiles** — CPU tile, GPU tile, SoC tile, IO extender — on a passive base die
that carries interconnect and power delivery. Useful for item 5 in a specific way: a *tiled* part
has natural cooling boundaries that a monolithic one does not, and the array's tile grid and the
package's tile boundaries are two different griddings of the same die. Whether they should be
aligned is a co-design question nobody has asked here.

### `die_images/` — 59 annotated die shots
Includes AD102/ADA102 (NVIDIA), Intel and AMD parts, and Bohr/Mistry scaling slides. **This is the
raw material for building a floorplan a vendor will not argue with**, and
`HotGauge/HotGauge/thermal/accelerator_floorplan.py` is the worked pattern for doing it with
provenance: measure off the shot, record the source, assert the areas sum.

`published_reference.DIE_GEOMETRY` already does this for three in-house parts, including a
block-level sketch for the Ryzen AI 5 340 (16.0 × 12.5 mm, 200 mm²).

### HotGauge, IISWC 2021
`design_physics/HotGauge_IISWC_2021.pdf` — the upstream framework's own paper. Read before
changing anything in `HotGauge/HotGauge/` that is not ours.

### `moderngpuarchitecturesecondedition.pdf`, `practical_guide_VLSI_SoC.pdf`, `vlsieducation.pdf`
Background texts. The VLSI SoC guide is the one to reach for on floorplanning conventions.

---

## 4. Thermal and packaging

### Microchannel cooling — **already used, and it resolved the accelerator**
`design_physics/microchannel-hotspot-limits-1-s2.0-S0017931017340309-am.pdf`

The measured anchor behind `sink_models.MICROCHANNEL_REF`: **1020 W/cm² background flux at <69 °C
above inlet and <120 kPa**, at a channel mass flux of 2100 kg/(m²·s); hotspot fluxes to
**2700 W/cm²** raise the hotspot only **16 °C**. Channels 15–33 µm wide, 35–470 µm deep, banks of
50, nine sinks over a 5 × 5 mm heated area.

`design_physics/microchannel_COP100k_1-s2.0-S0196890426003912-main.pdf` — the COP side, not yet
read in detail. Worth doing when pump/facility power moves from a floor to a real number.

### HIR 2023
`roadmaps/HIR/ch20_thermalfinal.pdf` (thermal), `ch16_devices.pdf`, `ch02_hpc.pdf`,
`ch09_photonics.pdf`

Already cited in the stacked-memory work for *"large stack thermal resistance"* (ch.20 §2.10).
ch09 is the photonics roadmap and is the natural external cross-check on the LCMR device claims.

### Others in `design_physics/`
* `Gallina_ImplicationsOfPowerDensity_presentation (1).pdf` — power-density trends.
* `Boreas-hotspot-mitigation-using-ml-hw-telemtry.pdf` — ML-driven hotspot mitigation from
  telemetry; the closest published analogue to the sensed closed-loop controller the array assumes.
* `everest_cpu_*.pdf`, `everest_gpu_*.pdf` — not yet read.
* `micromachines-11-00359-v2.pdf`, `ballistic_transport_PhysRevB.44.6329.pdf`,
  `Unknown_Heating-Effects-in-Nanoscale-Devices-33.pdf` — nanoscale transport and heating; relevant
  if the 20 µm burial-depth limit is ever pushed further.

---

## 5. In-house sources that are not in this directory

* `docs/photonic_cooling/Draft_5__Photonic_cooling_of_chips_v12___Provisional_Version.pdf` — the
  device paper. §6.4.1 is the bench data behind `microrefrigeration.DEMONSTRATED`
  (250 W/mm², 45 °C, 3.5 % ASF); §3.5.4 gives η_ASF 10–60 % across MVP stages, η_pump 70–75 %
  demonstrated, η_LPC up to 87 % demonstrated.
* `docs/photonic_cooling/mxl_LCEstimator_v8/` — the rack-scale model. `main_analysis.py` carries
  the CDU spec (1368 kW cooling / 13.7 kW electrical / 0.02 m³/s / 2 pumps at nominal, pump
  efficiency 0.3, cold-plate Δp 2 bar), which is the cross-check for per-device pump power:
  ~7 W/device for the whole loop against the ~0.06 W the microchannel channels alone need.
* `docs/demo_hw_slides.pdf` — die geometry and the measured 125H power sweep, already ingested
  into `published_reference`.
* `docs/SimScale/` — the CFD study behind `BaffledFinSink` and `DEFAULT_BASE_SPREAD`.
