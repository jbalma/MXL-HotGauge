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


def check_peak(point_key, peak_C, diverged=False):
    """Does a predicted peak reproduce this published point? Returns ``(ok, verdict)``."""
    p = PUBLISHED_POINTS[point_key]
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
