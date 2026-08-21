"""Tests for reading a 3D-ICE stack back as a resistance budget."""
import pytest

from HotGauge.thermal import get_stack_template
from HotGauge.thermal.stack_report import parse_stack, resistance_budget, format_budget


def test_conductivities_are_read_in_3dice_units_not_si():
    """The first trap, and a consequential one. 3D-ICE quotes conductivity in W/(um K), so
    silicon's 1.20e-4 is 120 W/(m K). Read as SI it looks like 1.2e-4 and every material becomes an
    insulator -- which is exactly the misreading that made me suspect the material constants when
    they were correct all along."""
    p = parse_stack(get_stack_template('skylake'))
    assert p['materials']['SILICON']['k_si'] == pytest.approx(120.0)
    assert p['materials']['COPPER']['k_si'] == pytest.approx(390.0)
    assert p['materials']['THERMAL_GREASE']['k_si'] == pytest.approx(4.0)
    assert p['materials']['SOLDER_TIM']['k_si'] == pytest.approx(25.0)


def test_commented_out_spreader_geometry_is_reported_not_parsed():
    """The template's spread height/area sits inside a /* REMOVED BECAUSE THEY LIE */ block. A
    parser that ignored comments would report a spreader the solver never sees."""
    p = parse_stack(get_stack_template('skylake'))
    assert p['spreader_geometry_commented_out'] is True


def test_the_budget_reproduces_the_measured_package_resistance():
    """Cross-check against 3D-ICE itself. The solve measured 0.0406 K/W of package on an 826 mm^2
    die and 0.361 on 91 mm^2; the budget computed from the file alone must agree, or one of the two
    is wrong."""
    stk = get_stack_template('skylake')
    big = resistance_budget(stk, 826.0)
    small = resistance_budget(stk, 91.0)
    assert big['total_K_per_W'] == pytest.approx(0.0406, rel=0.05)
    assert small['total_K_per_W'] == pytest.approx(0.361, rel=0.05)


def test_resistance_scales_exactly_inversely_with_area():
    """The signature of NO lateral spreading: every layer spans the die footprint, so halving the
    die doubles every resistance. A stack with a real spreader would not do this."""
    stk = get_stack_template('skylake')
    a = resistance_budget(stk, 826.0)['total_K_per_W']
    b = resistance_budget(stk, 91.0)['total_K_per_W']
    assert b / a == pytest.approx(826.0 / 91.0, rel=1e-6)


def test_the_package_layers_dominate_and_the_die_does_not():
    """Where the resistance actually lives: four package layers at ~90%, the silicon at ~10%.
    Worth pinning, because it says optimising the die stack would achieve nothing."""
    rows = resistance_budget(get_stack_template('skylake'), 826.0)['rows']
    pkg = sum(r['share'] for r in rows if not r['name'].startswith('die'))
    assert pkg > 0.85
    for r in rows:
        if not r['name'].startswith('die'):
            assert 0.15 < r['share'] < 0.30      # no single package layer dominates


def test_format_names_the_missing_overhang():
    text = format_budget(resistance_budget(get_stack_template('skylake'), 91.0))
    assert 'COMMENTED OUT' in text
    assert 'spreads heat' in text
