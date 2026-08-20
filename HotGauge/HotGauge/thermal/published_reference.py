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
        'implied_r_th_peak': (75.6 - 24.0) / 132.0,      # 0.391 K/W
        'note': 'dual 120 mm fans, 6x6 mm heat pipes; NOT at TjMax, so a clean thermal point',
        'cooler_class': 'desktop_tower',
    },
    'RYZEN_7500F_LIQUID': {
        'label': 'Ryzen 5 7500F, Lian Li Galahad II Lite 360 mm AIO, Prime95',
        'source': 'nhsjs.com/2026 air-vs-liquid cooler study',
        'die_area_mm2': 71.0,
        'power_W': 129.0, 'power_range_W': (126.1, 131.9),
        'ambient_C': 24.0,
        'fluid': 'water',
        'temp_C': (69.5, 71.1),          # 70.3 +/- 0.8
        'implied_r_th_peak': (70.3 - 24.0) / 129.0,      # 0.359 K/W
        'note': '360 mm radiator, 3x120 mm fans; NOT at TjMax',
        'cooler_class': 'desktop_tower',
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
