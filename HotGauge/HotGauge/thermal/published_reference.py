"""Published operating points, for checking the model against parts that demonstrably work.

Why this exists
---------------
Everything in this project is calibrated piecewise -- leakage from McPAT, the sink from a CFD
study, block areas from die shots -- and none of it had ever been checked end to end against a
real machine. The result was a model that predicted thermal runaway for a 400 W accelerator at
0.48 W/mm^2, which is a configuration that ships in volume and does not run away.

A model that contradicts a part you can buy is falsified, whatever its components say. These are
the operating points it has to reproduce before any of its predictions mean anything.

Provenance
----------
``H100_AIR`` and ``H100_LIQUID`` come from arXiv:2507.16781, a direct air-versus-liquid benchmark
on 8x H100 80GB HBM3 nodes. Both arms ran the same LLM fine-tuning workloads in the same facility
at 21-22 C room ambient, with the liquid loop on a 20 C datacenter chilled-water supply. That
paired design is what makes it useful: the two arms differ in cooling and in nothing else.

What is NOT pinned down by it
-----------------------------
The paper reports *GPU temperature* from telemetry, which on Nvidia parts is a die sensor rather
than a true peak-block junction temperature -- the real hotspot is somewhat hotter than the number
quoted. So these bounds are, if anything, generous to a model that runs hot, and a model that
still exceeds them is failing by more than the margin suggests.

Die area is the H100 SXM's 814 mm^2. Our floorplan is GA100's 826 mm^2 -- a 1.5% difference, and
the same architectural family and node class, so it stands in as a geometric proxy. What we are
testing is not "is this an H100" but "does a die of this size, at this power, under this cooling,
land anywhere near this temperature".
"""

#: Published operating points. ``temp_C`` is the observed range under load.
PUBLISHED_POINTS = {
    'H100_AIR': {
        'label': 'H100 80GB HBM3, air-cooled, LLM fine-tuning',
        'source': 'arXiv:2507.16781',
        'die_area_mm2': 814.0,
        'power_W': 470.0,            # 457-489 W per GPU across five models; midpoint
        'power_range_W': (457.0, 489.0),
        'ambient_C': 21.5,           # 21-22 C room
        'fluid': 'air',
        'temp_C': (54.0, 72.0),
        'implied_r_th_peak': (72.0 - 21.5) / 470.0,     # 0.1074 K/W
        'note': 'traditional air setup, 8 fans per node',
        'floorplan': 'ga100',
        'cooler_class': 'datacenter_module',
    },
    'H100_LIQUID': {
        'label': 'H100 80GB HBM3, direct-to-chip liquid, LLM fine-tuning',
        'source': 'arXiv:2507.16781',
        'die_area_mm2': 814.0,
        'power_W': 453.0,            # 438-468 W per GPU; midpoint
        'power_range_W': (438.0, 468.0),
        'ambient_C': 20.0,           # datacenter chilled water loop
        'fluid': 'water',
        'temp_C': (41.0, 50.0),
        'implied_r_th_peak': (50.0 - 20.0) / 453.0,     # 0.0662 K/W
        'note': 'D2C cooling, 4 fans per node',
        'floorplan': 'ga100',
        'package_note': 'direct-to-chip removes the lid and heat spreader, so the lidded\n            skylake package is wrong here -- it consumes 0.055 of the 0.0662 K/W budget\n            and leaves 0.011 that no water flow delivers',
        'cooler_class': 'datacenter_module',
    },
}

#: CPU operating points, from nhsjs.com/2026 "Analysis of Thermodynamics of Air and Liquid
#: Coolers and Their Impact on Performance of Processors" -- a paired design like the H100 study,
#: with the same CPUs under four coolers in a 24 C +/- 0.5 C controlled ambient.
#:
#: **Only the 7500F points are usable as thermal tests, and the reason matters.** Every 9700X
#: point sits at 95.2-95.4 C against a 95 C TjMax: those parts are THROTTLING, so the temperature
#: is pinned by the controller and the power is whatever happens to fit under it. Asking a model
#: to "predict" a temperature that a control loop is holding constant tests nothing. They are kept
#: because they test something else -- see ``CPU_CLOCK_POINTS``.
#:
#: Die area is the Zen 4 CCD's ~71 mm^2. Our CPU floorplan is 101 mm^2 for 34 cores, so this is a
#: geometric analogue rather than the same part; what is being tested is whether a die of roughly
#: this size at this power under this cooler lands anywhere near this temperature.
CPU_POINTS = {
    'RYZEN_7500F_AIR': {
        'label': 'Ryzen 5 7500F, Thermalright Peerless Assassin 120 SE, Prime95',
        'source': 'nhsjs.com/2026 air-vs-liquid cooler study',
        'die_area_mm2': 71.0,
        'power_W': 132.0, 'power_range_W': (130.3, 133.7),
        'ambient_C': 24.0,
        'fluid': 'air',
        'temp_C': (74.9, 76.3),          # 75.6 +/- 0.7
        'implied_r_th_peak': (76.3 - 24.0) / 132.0,      # 0.396 K/W, from the TOP of
        #                                                 the range, as every other point
        'note': 'dual 120 mm fans, 6x6 mm heat pipes; NOT at TjMax, so a clean thermal point',
        'cooler_class': 'desktop_tower',
        'floorplan': 'skylake10nm_14core_3',
        'floorplan_note': 'nearest available CPU floorplan is 90.6 mm^2 against the CCD\'s '
                          '71 mm^2 -- a 28% area mismatch, so this tests whether the model '
                          'generalises to a die of ROUGHLY this size, not this exact part',
    },
    'RYZEN_7500F_LIQUID': {
        'label': 'Ryzen 5 7500F, Lian Li Galahad II Lite 360 mm AIO, Prime95',
        'source': 'nhsjs.com/2026 air-vs-liquid cooler study',
        'die_area_mm2': 71.0,
        'power_W': 129.0, 'power_range_W': (126.1, 131.9),
        'ambient_C': 24.0,
        'fluid': 'water',
        'temp_C': (69.5, 71.1),          # 70.3 +/- 0.8
        'implied_r_th_peak': (71.1 - 24.0) / 129.0,      # 0.365 K/W, top of the range
        'note': '360 mm radiator, 3x120 mm fans; NOT at TjMax',
        'cooler_class': 'desktop_tower',
        'floorplan': 'skylake10nm_14core_3',
    },
}

#: Points where the part is TEMPERATURE-LIMITED rather than free-running, and what they test.
#:
#: On these the controller pins the junction at TjMax and trades clock for it, so the useful
#: prediction is not "what temperature" but "how much clock does better cooling buy". That is
#: precisely what ``examples/clock_headroom.py`` computes, and this project has never checked it
#: against a real part.
#:
#: The 9700X is the sharp case: identical silicon, identical 95 C limit, and 3808 MHz on the stock
#: cooler against 4966 MHz on a 360 mm AIO -- **+30% clock bought by cooling alone**, at 99 W
#: against 180 W. Our own cooling sweep claims a 50x better cooler buys +55%, which is the same
#: order and has never been validated.
CPU_CLOCK_POINTS = {
    'RYZEN_9700X_COOLING_VS_CLOCK': {
        'label': 'Ryzen 7 9700X, four coolers, Prime95, all at TjMax 95 C',
        'source': 'nhsjs.com/2026 air-vs-liquid cooler study',
        'die_area_mm2': 71.0, 'ambient_C': 24.0, 'tjmax_C': 95.0,
        'rows': [
            {'cooler': 'AMD Wraith Stealth SR1 (stock)', 'fluid': 'air',
             'power_W': 99.0, 'temp_C': 95.2, 'clock_MHz': 3808},
            {'cooler': 'Thermalright Peerless Assassin 120 SE', 'fluid': 'air',
             'power_W': 174.0, 'temp_C': 95.4, 'clock_MHz': 4899},
            {'cooler': 'Cooler Master ML240L V2 (240 mm AIO)', 'fluid': 'water',
             'power_W': 163.0, 'temp_C': 90.2, 'clock_MHz': 4840},
            {'cooler': 'Lian Li Galahad II Lite (360 mm AIO)', 'fluid': 'water',
             'power_W': 180.0, 'temp_C': 86.3, 'clock_MHz': 4966},
        ],
        'clock_gain_stock_to_best': 4966.0 / 3808.0 - 1.0,     # +30.4%
        'note': 'temperature-limited: the controller holds TjMax and trades clock, so these test '
                'the clock-vs-cooling relation rather than the thermal solve',
    },
}


#: How far outside the published range a predicted peak may sit and still pass.
#:
#: Generous on purpose, and asymmetric in what it forgives. The reported telemetry is a die sensor
#: rather than a true peak block, so a model may legitimately run somewhat HOTTER than the quoted
#: maximum; there is no corresponding reason for it to run colder than the quoted minimum. What
#: this must not forgive is the failure actually observed -- a predicted runaway where the real
#: part sits at 72 C, which no tolerance should absorb.
ACCEPT_ABOVE_MAX_K = 15.0
ACCEPT_BELOW_MIN_K = 8.0


# ---------------------------------------------------------------------------
# Direct-die hardware available for in-house validation
# ---------------------------------------------------------------------------
#: Parts that match the **baseline configuration** -- bare die, cold plate or heatsink straight on
#: the silicon, no lid, no die-attach solder, no copper IHS.
#:
#: Why this matters more than the published points above. Every entry in ``PUBLISHED_POINTS`` and
#: ``CPU_POINTS`` is a **lidded** part, so reproducing them requires modelling an IHS and a solder
#: die-attach that the device we are designing for does not have. Validating a direct-die model
#: against lidded hardware means the package we most need to get right is the one we cannot check.
#: These are direct-die and in hand.
#:
#: **Nothing here is a gate point yet, by construction.** Each needs a measured operating point --
#: die area, power, ambient, and a temperature -- before ``check_peak`` can use it, and
#: ``all_thermal_points()`` deliberately does not include them. Specs below are from the Batch 1
#: demo hardware list; anything absent is absent because it has not been measured, and inventing
#: it would defeat the point of a gate.
#:
#: A thermal camera changes what a gate point *is*. A published number validates one scalar -- the
#: peak, or whatever sensor the vendor exposes. An IR map validates the **spatial field**, which is
#: what this project actually predicts: hotspot location, the peak-to-runner-up gap that decides
#: tile pitch, the plateau width that sizes a plan. That is a far stronger test, and it is the one
#: a licensee would ask for.
#:
#: Two practical caveats that shape the measurement, recorded here because they change what the
#: data can support rather than merely how it is taken:
#:
#: * **Imaging the die means the cooler is off**, so the boundary condition under the camera is not
#:   the one in service. That is not fatal and may be preferable: a bare die under natural
#:   convection is a *simpler* boundary to model than a heatsink, and the resulting field is set
#:   almost entirely by the floorplan and the power map -- which is exactly what we want to test.
#:   Model the configuration that was measured, not the one that ships.
#: * **Bare silicon is a poor IR target.** Emissivity is low (~0.6-0.7) and varies with doping,
#:   surface finish and angle, so an uncalibrated map is not a temperature map. A high-emissivity
#:   coating or in-frame reference spots at known temperature are needed before the numbers mean
#:   anything absolute. Relative structure survives uncalibrated; absolute values do not.
DIRECT_DIE_HARDWARE = {
    'FRAMEWORK_13': {
        'label': 'Framework Laptop 13 mainboards, lidless mobile CPUs, in house',
        'form_factor': 'direct_die',
        'measurement': 'thermal camera, not yet taken',
        'parts': [
            # (part, P-cores, E-cores, threads, base GHz, turbo GHz, base W, max W)
            ('AMD Ryzen 5 7640U',      6,  0, 12, 3.5, '4.9',          15.0,  30.0),
            ('AMD Ryzen AI 5 340',     6,  0, 12, 2.0, '4.8',          28.0,  54.0),
            ('Intel Core i7-1185G7',   4,  0,  8, 1.2, '4.8',          12.0,  28.0),
            ('Intel Core i7-8650U',    4,  0,  8, 1.9, '4.2',          15.0,  25.0),
            ('Intel Core i7-1260P',    4,  8, 16, 2.1, 'P:4.7 E:3.4',  28.0,  64.0),
            ('Intel Core Ultra 5 125H', 4, 10, 18, 1.2, 'P:4.5 E:3.6', 28.0, 115.0),
            ('DC-ROMA RISC-V RVA23',   8,  0, 16, 2.5, '2.5 (?)',      13.0,  25.0),
        ],
        'note': ('x86 from two vendors plus a RISC-V part in the same thermal envelope and the '
                 'same chassis -- which makes it a cross-ISA comparison with the cooling held '
                 'fixed, not merely a set of validation points. See docs/CODESIGN_PLAN.md 4. '
                 'No ARM part in house yet; Framework ships them, so it is procurable rather '
                 'than blocked.'),
        'missing_for_a_gate_point': ('a measured operating point per part -- power AND '
                                     'temperature at a known ambient -- plus the cooling '
                                     'configuration it was taken under, and an emissivity '
                                     'calibration for any absolute temperature. Die geometry is '
                                     'now known for three parts; see DIE_GEOMETRY below.'),
    },
    'V100_SXM2': {
        'label': 'Tesla V100 SXM2, bare GV100 die under a cold plate',
        'form_factor': 'direct_die',
        'measurement': 'nvidia-smi telemetry, available on this cluster',
        'note': ('The direct-die HPC part, and the closest available analogue to the accelerator '
                 'floorplan this project already models. node-06 carries eight of them, so an '
                 'operating point is a GPU allocation and a load away rather than a literature '
                 'search -- but the GPUs are not in the current CPU-only allocation '
                 '(TRES=cpu=96), so it needs one requested.'),
        'missing_for_a_gate_point': ('a measured temperature/power/clock sweep under a known '
                                     'ambient, plus the cold-plate configuration'),
    },
}


#: Die geometry read off ``docs/demo_hw_slides.pdf``, which carries annotated die shots for the
#: in-house parts. Dimensions are as marked on the slides.
#:
#: These are what a floorplan gets built from, so the provenance matters as much as the number --
#: the same discipline ``accelerator_floorplan.py`` applies to the GA100 die shot.
DIE_GEOMETRY = {
    'AMD_RYZEN_AI_5_340': {
        'die_mm': (16.0, 12.5), 'die_area_mm2': 200.0,
        'source': 'demo_hw_slides.pdf, annotated die shot',
        'blocks': ('Zen 5 P-cores', 'Zen 5c E-cores', 'Cache + AI Engine',
                   'Graphics & Media', 'I/O & Memory'),
        'note': 'the slide carries a block-level floorplan sketch, not just an outline',
    },
    'INTEL_CORE_ULTRA_5_125H': {
        'package_mm': (42.0, 20.0), 'compute_region_mm': (23.0, 11.0),
        'source': 'demo_hw_slides.pdf, annotated package photo + Intel SKU 236848',
        'hotspots_mm': {'cluster': (8.9, 8.3), 'block': (2.0, 1.0), 'pitch': 4.3},
        'hotspot_W': 8.0, 'package_W': 115.0,
        'note': ('four 8 W blocks inside an 8.9 x 8.3 mm cluster -- a concrete hot-cluster '
                 'geometry to test tile pitch against, rather than a synthetic one'),
    },
    'AMD_RYZEN_9_AI_HX_370': {
        'die_mm': (19.6, 12.3), 'die_area_mm2': 241.1,
        'source': 'demo_hw_slides.pdf',
        'note': 'not in the Batch 1 list; carries the nested power-density decomposition below',
    },
}

#: Measured package power for the Core Ultra 5 125H across instruction mixes and core counts.
#: **Measured, not modelled** -- and the only such sweep this project has for a direct-die part.
#: Its shape is the interesting part: package power barely moves from SSE to AVX-512 on one core
#: (14 -> 16 W) but single-core power is 14.2 W at one thread against 9.2 W at two, and all-core
#: all-thread reaches only 25 W package. A part whose ceiling is 115 W sitting at 25 W all-core is
#: power-management-limited long before it is thermally limited, which is exactly the regime the
#: CODESIGN_PLAN 9 ladder has to reason about.
CORE_ULTRA_125H_POWER = {
    'source': 'demo_hw_slides.pdf, in-house measurement',
    'units': 'W',
    'columns': ('system', 'package', 'all_core', 'single_core'),
    'rows': {
        'idle':                  (20.0,  6.5,  1.1,  0.3),
        '1core_1thread_SSE':     (35.0, 22.0, 15.0, 14.2),
        '1core_2thread_SSE':     (35.0, 14.0, 10.0,  9.2),
        '1core_2thread_AVX':     (35.0, 15.0, 10.0,  9.2),
        '1core_2thread_AVX2':    (35.0, 15.0, 10.0,  9.2),
        '1core_2thread_AVX512':  (37.0, 16.0, 11.0, 10.2),
        '4core_2thread_AVX512':  (42.0, 18.0, 14.0,  3.5),
        'allcore_allthread':     (56.0, 25.0, 16.0,  4.0),
    },
}

#: Nested power density on the Ryzen 9 AI HX 370, from the same 1.75 W at four zoom levels.
#: This is the measured version of the argument CODESIGN_PLAN 4 needs: **concentration, not
#: decode area**, is what an area cooler responds to. The same watt is 1.05 W/mm^2 spread over a
#: core and 8.33 W/mm^2 at the innermost block -- an 8x range inside one core, which is the range
#: a tile array has to resolve and the reason tile pitch has a regime reversal at all.
HX370_POWER_DENSITY = {
    'source': 'demo_hw_slides.pdf',
    'W': 1.75,
    'levels_mm2': (5.87, 1.40, 0.54, 0.21),
    'W_per_mm2': (1.05, 1.25, 3.24, 8.33),
}

#: The demo stack as drawn on the Core Ultra 5 125H slide, top to bottom.
#: Note it is NOT the baseline stack this project models: it has a TEC below the board and treats
#: the PCB as a conduction path. Recorded so a validation run models what was actually built.
DEMO_STACK = {
    'source': 'demo_hw_slides.pdf',
    'layers': (('Cu heatsink', None, None),
               ('Si', 500.0, 130.0),
               ('PCB (BEOL)', 2000.0, 0.6),
               ('TEC', None, None)),
    'note': ('thicknesses in um, conductivity in W/(m K) where the slide states it. The 0.6 W/mK '
             'board is a near-insulator, so essentially all the heat must leave upward -- which '
             'makes the top-side cooling comparison cleaner than a socketed desktop part.'),
}


#: The demo system as built, from ``docs/demo_system_details.pdf``. This is the configuration a
#: validation run has to model -- not the baseline stack, and not the slide's heatsink drawing.
#:
#: Stack, top to bottom in the schematic::
#:
#:     thermal camera (3-6 um window)
#:     PCP tiles                 <- free-space laser, 4-16 of them
#:     chip substrate            <- bulk silicon, the backside the camera sees
#:     active layer of chip
#:     power delivery network
#:     PCB
#:     TEC                       <- the cooling, BELOW the board
#:
#: Two things about it change what we should be simulating.
#:
#: **This configuration has no heatsink on top** -- the board mounts to a TEC underneath so the
#: die can run bare and be imaged under load. That is a *measurement* configuration, not a change
#: to what we model. **The baseline model stays heatsink-on-top** (see the baseline configuration
#: in docs/PHASE0_CHECKLIST.md); this is one of two complementary ways to check it:
#:
#: * **Heatsink and fan, temperatures read in software.** The real heatsink and the real fan we
#:   already model, mounted on a direct-die part, sweeping airflow against temperature, power and
#:   performance. This validates the working model end to end -- sink resistance, fan power, the
#:   power/airflow/performance trade -- and it is the primary validation route.
#: * **No heatsink, thermal camera.** Gives the spatial temperature *distribution* the software
#:   sensors cannot: hotspot location, the peak-to-runner-up gap that decides tile pitch, plateau
#:   width. A bare die under natural convection is also a simpler boundary, so the field is set
#:   mostly by the floorplan and the power map -- which is what makes it a clean test of the
#:   floorplan model specifically.
#:
#: Either way, model the configuration that was measured. Neither replaces the heatsink-on-top
#: stack the design work runs on.
#:
#: **The first-generation array is 4-16 tiles**, not thousands. On a ~200 mm^2 die that is roughly
#: a 3.5-7 mm pitch -- coarser than the coarsest point in the tile-pitch sweep (2000 um). The
#: device-relevant regime is therefore the COARSE end of that study, where a coarse tile was
#: measured to beat a fine one by 59% on a degenerate peak. The 1-10 um pitches this project has
#: swept are a long-run limit, not the part being built.
DEMO_SYSTEM = {
    'source': 'docs/demo_system_details.pdf',
    'camera_window_um': (3.0, 6.0),
    'cooling': ('TEC below the PCB; no heatsink on top, so the die can be imaged under load. '
                'A measurement configuration -- the modelled baseline keeps its heatsink.'),
    'validation_routes': ('heatsink + fan with software temperature readout (primary: validates '
                          'the sink and fan models and the power/airflow/performance trade); '
                          'thermal camera with no heatsink (spatial distribution)'),
    'stack_top_down': ('thermal camera', 'PCP tiles', 'chip substrate', 'active layer',
                       'power delivery network', 'PCB', 'TEC'),
    'n_tiles': (4, 16),
    'control_loop': ('thermal camera -> temperature distribution and targeting -> laser pulse '
                     'and position schedule, with workload functional-unit dynamics as a '
                     'feed-forward input'),
    'chips': ('AMD Ryzen 5-7640U', 'AMD Ryzen AI-5340', 'Intel Core i7-1185G7',
              'Intel Core i7-1260P', 'Intel Core i7-8650U', 'Intel Core Ultra 5 125H',
              'RISC-V StarFive JH7110'),
    'note': ('the RISC-V part is the StarFive JH7110 here, superseding the DC-ROMA RVA23 in the '
             'Batch 1 list. The control loop is the one modelled by run_mr_clipping: sense the '
             'field, revise the plan, re-solve.'),
}


def all_thermal_points():
    """Every point usable as a thermal acceptance test -- accelerator and CPU."""
    out = dict(PUBLISHED_POINTS)
    out.update(CPU_POINTS)
    return out


def check_peak(point_key, peak_C, diverged=False):
    """Does a predicted peak reproduce this published point? Returns ``(ok, verdict)``."""
    p = all_thermal_points()[point_key]
    lo, hi = p['temp_C']
    if diverged:
        return False, ('FAIL: model predicts thermal runaway where {} runs stably at {:.0f}-{:.0f} C. '
                       'A part that ships in volume does not run away.'.format(p['label'], lo, hi))
    if peak_C is None:
        return False, 'FAIL: no peak temperature returned'
    if peak_C > hi + ACCEPT_ABOVE_MAX_K:
        return False, ('FAIL: predicted {:.1f} C against a published {:.0f}-{:.0f} C '
                       '({:+.1f} K above the top of the range, tolerance {:.0f} K)'
                       .format(peak_C, lo, hi, peak_C - hi, ACCEPT_ABOVE_MAX_K))
    if peak_C < lo - ACCEPT_BELOW_MIN_K:
        return False, ('FAIL: predicted {:.1f} C against a published {:.0f}-{:.0f} C '
                       '({:.1f} K below the bottom of the range) -- the model is running too '
                       'cold, which flatters every cooling conclusion drawn from it'
                       .format(peak_C, lo, hi, lo - peak_C))
    return True, ('PASS: predicted {:.1f} C against a published {:.0f}-{:.0f} C'
                  .format(peak_C, lo, hi))
