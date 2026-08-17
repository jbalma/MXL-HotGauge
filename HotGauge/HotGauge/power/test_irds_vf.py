"""Tests for the IRDS-anchored V/F model (HotGauge.power.irds_vf).

These pin the anchoring property, the ceiling behaviour and the honesty flags. They deliberately
do NOT assert the roadmap's own numbers as if this project had measured them -- what is checked
is that the curve passes through whatever IRDS says and reports its own assumptions.
"""
import pytest

from HotGauge.power.irds_vf import (IRDSVFModel, IRDS_NODES, ANCHORS, DEFAULT_ALPHA,
                                    compare_with_shipped_table)


def test_curve_passes_through_the_roadmap_operating_point():
    """The whole point of anchoring: f(Vdd) must equal the node's own quoted frequency."""
    for year in (2024, 2027, 2031):
        for anchor in ANCHORS:
            m = IRDSVFModel(year, anchor=anchor)
            assert m.frequency(m.vdd) == pytest.approx(m.f_anchor, rel=1e-9)


def test_voltage_and_frequency_invert_each_other():
    m = IRDSVFModel(2024)
    for f in (2.5, 3.0, 3.5, 3.85):
        v, clamped = m.voltage(f)
        assert not clamped
        assert m.frequency(v) == pytest.approx(f, rel=1e-6)


def test_uses_the_roadmap_threshold_not_a_fitted_one():
    """The shipped table's fit implied Vt ~0.48 V, an artefact of the wrong data. IRDS says
    ~0.16 V, and the curve must use that."""
    m = IRDSVFModel(2024)
    assert m.vt == pytest.approx(IRDS_NODES[2024]['vt'])
    assert m.vt < 0.2


def test_ceiling_is_overdrive_limited_and_reported_as_a_clamp():
    """Past the node's overdrive limit a part fails rather than running slower, so asking for a
    clock beyond it must come back clamped and flagged, never as a quietly higher voltage."""
    m = IRDSVFModel(2024, overdrive=0.10)
    assert m.v_max == pytest.approx(m.vdd * 1.10)
    v, clamped = m.voltage(m.f_max * 1.5)
    assert clamped is True
    assert v == pytest.approx(m.v_max)
    # ...and f_max is the frequency at exactly that voltage
    assert m.frequency(m.v_max) == pytest.approx(m.f_max, rel=1e-9)


def test_more_overdrive_buys_more_clock_but_it_is_a_choice():
    lo = IRDSVFModel(2024, overdrive=0.0)
    hi = IRDSVFModel(2024, overdrive=0.20)
    assert hi.f_max > lo.f_max
    assert lo.f_max == pytest.approx(lo.frequency(lo.vdd), rel=1e-9)


def test_alpha_sensitivity_brackets_the_assumption():
    """alpha is not in the roadmap, so anything leaning on it needs its own error bar."""
    m = IRDSVFModel(2024)
    s = m.alpha_sensitivity(4.0, alphas=(1.0, 1.4, 1.6))
    fmaxes = [d['f_max_GHz'] for d in s.values()]
    assert min(fmaxes) < m.f_max < max(fmaxes) or len(set(fmaxes)) > 1
    # the spread is modest but real -- a result that flips across it is not a finding
    assert (max(fmaxes) - min(fmaxes)) / m.f_max < 0.15


def test_model_is_not_calibrated_and_says_so():
    m = IRDSVFModel(2024)
    assert m.calibrated is False
    assert 'UNCALIBRATED' in repr(m)
    assert 'wireloaded' in repr(m)          # the anchor choice moves every absolute number


def test_dynamic_power_scale_is_flatter_than_the_shipped_table():
    """The specific error this module exists to fix: the shipped table demands far more voltage
    for the same clock, so it overstates the power cost of clock."""
    m = IRDSVFModel(2024)
    rows = {r['f_GHz']: r for r in compare_with_shipped_table(freqs=(3.85, 4.36))}
    for f, r in rows.items():
        assert r['shipped_V'] > r['irds_V'], f
        assert r['dyn_power_ratio'] > 1.5


def test_rejects_unknown_nodes_and_bad_parameters():
    with pytest.raises(ValueError):
        IRDSVFModel(1999)
    with pytest.raises(ValueError):
        IRDSVFModel(2024, anchor='vibes')
    with pytest.raises(ValueError):
        IRDSVFModel(2024, alpha=0.0)
    with pytest.raises(ValueError):
        IRDSVFModel(2024, overdrive=-0.1)


def test_every_node_row_is_self_consistent():
    """Guard against a transcription slip in the extracted table."""
    for year, n in IRDS_NODES.items():
        assert 0.4 < n['vdd'] < 1.0, year
        assert 0.05 < n['vt'] < 0.35, year
        assert n['vt'] < n['vdd'], year
        assert n['f_cpu'] < n['f_wireloaded'] < n['f_unloaded'], year
        assert 0.5 < n['dyn_mW_per_GHz'] < 5.0, year
