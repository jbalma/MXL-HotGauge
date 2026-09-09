"""The extractor platform is two thin films, and neither is a rare-earth crystal (§P0.18).

Corrected 3 Sep 2026. The shipping device uses **semiconductor (GaAs) extractor tiles** or
**SiN-encapsulated molecular dyes**, both reaching **> 1000 W/mm^2**, across an eta_ASF range
of **0.10-0.60** with **0.32** as the working point.

Two errors this file exists to keep out:

  * an earlier revision of ``PLATFORMS_V91`` recommended **Yb:YLF for the cold zone**. It is not
    the cold-zone material; it is 2-3 orders of magnitude below both shipping platforms and is
    retained only so the pre-30-Aug catalogue reproduces.
  * a 3 Sep 2026 revision narrowed the eta_ASF range to 0.10-0.30 and moved the default to 0.20.
    **That narrowing is withdrawn.** The range is Draft_5's full "10-60 % across MVP stages" and
    0.32 stands, so every recorded MR cost reproduces un-flagged.
"""
import pytest

from HotGauge.thermal.microrefrigeration import (
    PLATFORMS_V91, ZONE_EXTRACTORS, DEFAULT_ETA_ASF, ETA_ASF_RANGE,
    DEFAULT_H_MAX_W_PER_MM2, MRParams)

SHIPPING = ('gaas_gainp_epitaxy', 'sin_encapsulated_dye')


def test_both_shipping_platforms_are_present_and_named_for_what_they_are():
    for p in SHIPPING:
        assert p in PLATFORMS_V91, '%s must be in the platform table' % p
    assert 'smiles_r640_polymer' not in PLATFORMS_V91, \
        'the dye platform is SiN-encapsulated, not polymer-hosted'


def test_both_shipping_platforms_clear_1000_W_per_mm2():
    for p in SHIPPING:
        lo, _hi = PLATFORMS_V91[p]['cooling_density_W_per_mm2']
        assert lo >= 1000.0, '%s must reach >= 1000 W/mm^2, got %g' % (p, lo)


def test_the_default_cooling_density_is_the_conservative_end_of_that():
    assert DEFAULT_H_MAX_W_PER_MM2 >= 1000.0
    assert DEFAULT_H_MAX_W_PER_MM2 == min(
        PLATFORMS_V91[p]['cooling_density_W_per_mm2'][0] for p in SHIPPING), \
        'the default must be the low end of the published range, not the top'


def test_eta_asf_default_is_the_middle_of_the_mvp_stage_range():
    """`[!]` The range is **0.10-0.60** -- Draft_5 s3.5.4's "10-60 % across MVP stages", a span of
    *stages* rather than one platform's tolerance -- and **0.32** is the middle ground.

    A 3 Sep 2026 revision narrowed this to 0.10-0.30 and moved the default to 0.20. That narrowing
    is withdrawn: it would have re-priced every recorded MR cost by 1.6x for no measured reason.
    """
    lo, hi = ETA_ASF_RANGE
    assert (lo, hi) == (0.10, 0.60)
    assert DEFAULT_ETA_ASF == 0.32
    assert lo < DEFAULT_ETA_ASF < hi
    assert MRParams(313.15).eta_asf == DEFAULT_ETA_ASF, \
        'an un-flagged run must reproduce every recorded MR cost'


def test_no_thermal_zone_recommends_a_rare_earth_crystal():
    """`[!]` The specific error being locked out: Yb:YLF as a zone material, cold or otherwise.
    v98 Table 10.8 assigns Yb:YLF to the cold zone; the 8 Sep decision keeps it out and puts
    Cr:LiSAF (a transition-metal-doped colquiriite, not a rare earth) there instead."""
    allowed = set(SHIPPING) | {'cr_lisaf'}
    for zone, spec in ZONE_EXTRACTORS.items():
        for p in spec['platforms']:
            assert p in allowed, 'zone %r names %r, which is not an allowed zone material' % (zone, p)
        blob = repr(spec).lower()
        for banned in ('ylf', 'zblan', 'sic:er', 'gan:yb', 'fluoride', 'yb:'):
            assert banned not in blob, 'zone %r still names the retired material %r' % (zone, banned)


def test_the_zone_assignment_is_the_8_sep_decision():
    """Cold (storage) zone: Cr:LiSAF. Hot (compute) zone: the dye. The 280 K knee sits in the
    cold band."""
    cold, hot = ZONE_EXTRACTORS['cold_cache'], ZONE_EXTRACTORS['hot_compute']
    assert cold['platforms'] == ('cr_lisaf',)
    assert hot['platforms'] == ('sin_encapsulated_dye',)
    assert cold['T_K'][0] <= 280.0 <= cold['T_K'][1]
    assert 'cr_lisaf' in PLATFORMS_V91 and PLATFORMS_V91['cr_lisaf']['cooling_density_W_per_mm3'] == (20.0, 80.0)


def test_the_default_cold_plate_is_single_material():
    """A floorplan-matched dual-material array is a per-architecture product; it is a flag."""
    from HotGauge.thermal.extractor import DEFAULT_ZONE_MODE, ZONE_MODES, DEFAULT_COLD_EXTRACTOR
    assert DEFAULT_ZONE_MODE == 'single' and ZONE_MODES == ('single', 'dual')
    assert DEFAULT_COLD_EXTRACTOR == 'cr-lisaf'
    import os, re
    src = open(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'examples',
                            'mr_comparison.py')).read()
    m = re.search(r"add_argument\('--mr-zone-mode', default=(\w+)", src)
    assert m and m.group(1) == 'DEFAULT_ZONE_MODE'


def test_yb_ylf_is_retained_only_as_a_reproduction_baseline():
    note = PLATFORMS_V91['yb_ylf_crystal']['note'].lower()
    assert 'historical' in note or 'baseline' in note
    assert 'withdrawn' in note, 'the cold-zone recommendation must be explicitly withdrawn'
    hi = PLATFORMS_V91['yb_ylf_crystal']['cooling_density_W_per_mm2'][1]
    assert hi < 1000.0, 'it is orders of magnitude below the shipping platforms, by construction'
