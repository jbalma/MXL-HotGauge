"""Tests for the BSIM-CMG deck generator and the simulated leakage curve.

Two kinds here, and the split is deliberate.

The **deck-generation** tests are pure string/arithmetic work and always run. They exist because
every one of them encodes a mistake that produced a *plausible wrong answer* during P0.13 rather
than an error: a four-terminal instance line, a ``level =`` that names a non-existent built-in, an
``osdi`` command that loads the model too late to matter, and a per-fin current divided by a
thousand-fin width.

The **simulator** tests need ``spice_toolchain/`` and skip without it. They are the ones that
would catch the toolchain silently regressing -- an ngspice rebuilt without OSDI, or a recompiled
``.osdi`` that no longer binds the card.
"""
import os

import numpy as np
import pytest

from HotGauge.power import spice_sim
from HotGauge.power.spice_cards import parse_card, card_path
from HotGauge.power.device_leakage import (SimulatedLeakageCurve, load_simulated_curve,
                                           SIMULATED_EVIDENCE, repo_root_for_evidence)

_needs_card = pytest.mark.skipif(not os.path.exists(card_path()),
                                 reason='vendored card not present')
_needs_toolchain = pytest.mark.skipif(not spice_sim.have_toolchain(),
                                      reason='spice_toolchain/ not built '
                                             '(see docs/BSIMCMG_TOOLCHAIN.md)')
_EVIDENCE = os.path.join(repo_root_for_evidence(), SIMULATED_EVIDENCE)
_needs_evidence = pytest.mark.skipif(not os.path.exists(_EVIDENCE),
                                     reason='simulated leakage evidence not generated')


# ---------------------------------------------------------------------------
# Module name resolution -- 110 and 111 disagree, and guessing binds nothing
# ---------------------------------------------------------------------------
def test_module_name_reads_the_active_ifdef_branch(tmp_path):
    p = tmp_path / 'm.va'
    p.write_text('`ifdef __XYCE__\n'
                 '    module bsimcmg_va(d, g, s, e, t);\n'
                 '`else\n'
                 '    module bsimcmg(d, g, s, e, t);\n'
                 '`endif\n')
    assert spice_sim.module_name_of(str(p)) == 'bsimcmg'
    assert spice_sim.module_name_of(str(p), defines=['__XYCE__']) == 'bsimcmg_va'


def test_module_name_handles_ifndef_and_nesting(tmp_path):
    p = tmp_path / 'm.va'
    p.write_text('`ifndef FOO\n`ifdef BAR\nmodule wrong(a);\n`endif\n'
                 'module right(a);\n`endif\n')
    assert spice_sim.module_name_of(str(p)) == 'right'


def test_module_name_raises_when_nothing_is_active(tmp_path):
    p = tmp_path / 'm.va'
    p.write_text('`ifdef NEVER\nmodule hidden(a);\n`endif\n')
    with pytest.raises(ValueError):
        spice_sim.module_name_of(str(p))


# ---------------------------------------------------------------------------
# The generated model card
# ---------------------------------------------------------------------------
def test_render_model_card_drops_level_and_names_the_module():
    dev = {'__type__': 'nmos', '__level__': 17, 'ute': -0.7, 'version': 107.0}
    card = spice_sim.render_model_card(dev, 'nmos_rvt', 'bsimcmg')
    assert card.splitlines()[0] == '.model nmos_rvt bsimcmg'
    assert 'level' not in card, 'OSDI models have no level; a level= names a built-in that is absent'
    assert '+ ute = -0.7' in card


def test_render_model_card_is_deterministic_and_excludable():
    dev = {'__type__': 'nmos', '__level__': 17, 'b': 2.0, 'a': 1.0, 'c': 3.0}
    assert spice_sim.render_model_card(dev, 'm', 'mod') == \
        spice_sim.render_model_card(dev, 'm', 'mod')
    card = spice_sim.render_model_card(dev, 'm', 'mod', exclude=['B'])
    assert '+ b =' not in card and '+ a =' in card


def test_effective_width_is_the_wraparound_perimeter():
    dev = {'hfin': 32e-9, 'tfin': 6.5e-9}
    assert spice_sim.effective_width_um(dev, nfin=1) == pytest.approx(0.0705)
    assert spice_sim.effective_width_um(dev, nfin=10) == pytest.approx(0.705)


# ---------------------------------------------------------------------------
# The deck
# ---------------------------------------------------------------------------
def test_deck_binds_five_terminals_and_loads_the_model_first():
    deck = spice_sim.ioff_deck('.model dut bsimcmg', 'dut', [26.85], '/tmp/x.osdi')
    lines = [l.strip() for l in deck.splitlines()]
    inst = next(l for l in lines if l.startswith('N1 '))
    # d g s e t + model name -> six fields after the instance name
    assert inst.split()[1:7] == ['d', 'g', '0', '0', '0', 'dut'], \
        'BSIM-CMG has five terminals; a four-node line misbinds silently'
    ctrl = lines.index('.control')
    assert lines[ctrl + 1].startswith('pre_osdi '), \
        'the model must load BEFORE the netlist is parsed, which only pre_osdi does'


def test_deck_defaults_to_many_fins_and_the_klu_solver():
    deck = spice_sim.ioff_deck('.model dut bsimcmg', 'dut', [26.85], '/tmp/x.osdi')
    assert 'nfin={:d}'.format(spice_sim.DEFAULT_NFIN) in deck
    assert spice_sim.DEFAULT_NFIN >= 1000, 'one fin leaks below the linear solver resolution'
    assert 'option klu' in deck


def test_deck_emits_one_solve_per_temperature():
    temps = [-73.15, 26.85, 126.85]
    deck = spice_sim.ioff_deck('.model dut bsimcmg', 'dut', temps, '/tmp/x.osdi')
    assert deck.count('\nop\n') == len(temps)
    assert deck.count('option temp =') == len(temps)


def test_deck_never_writes_numpy_repr():
    """``%r`` of a numpy scalar is ``np.float64(...)``, which ngspice cannot parse."""
    deck = spice_sim.ioff_deck('.model dut bsimcmg', 'dut', np.array([26.85, 100.0]),
                               '/tmp/x.osdi')
    assert 'np.float64' not in deck


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def test_parse_ioff_takes_magnitude_and_divides_by_nfin():
    out = 'noise\nIOFF 26.85 -1.63709E-11\nIOFF 100.0 -2.21689E-10\nmore noise\n'
    assert spice_sim.parse_ioff(out) == [(26.85, 1.63709e-11), (100.0, 2.21689e-10)]
    rows = spice_sim.parse_ioff(out, nfin=1000)
    assert rows[0][1] == pytest.approx(1.63709e-14)


def test_unknown_parameters_picks_up_ngspices_wording():
    out = ('Warning: Model issue on line 2 :\n'
           'unrecognized parameter (capmod) - ignored\n'
           'unrecognized parameter (version) - ignored\n'
           'Doing analysis at TEMP = 26.85\n')
    found = spice_sim.unknown_parameters(out)
    assert len(found) == 2 and 'capmod' in found[0]


def test_toolchain_raises_rather_than_falling_back(tmp_path):
    with pytest.raises(RuntimeError) as e:
        spice_sim.toolchain(ngspice=str(tmp_path / 'nope'), osdi=str(tmp_path / 'nope.osdi'))
    assert 'BSIMCMG_TOOLCHAIN' in str(e.value)


# ---------------------------------------------------------------------------
# The simulated curve
# ---------------------------------------------------------------------------
def test_simulated_curve_interpolates_in_log_not_linear():
    c = SimulatedLeakageCurve([300.0, 400.0], [1.0, 100.0])
    assert float(c.total_rel(350.0)) == pytest.approx(10.0), 'geometric, not the linear 50.5'


def test_simulated_curve_clamps_and_says_so():
    c = SimulatedLeakageCurve([300.0, 400.0], [1.0, 100.0])
    assert float(c.total_rel(250.0)) == pytest.approx(1.0)
    assert float(c.total_rel(500.0)) == pytest.approx(100.0)
    assert bool(c.clamped_at(250.0)) and bool(c.clamped_at(500.0))
    assert not bool(c.clamped_at(350.0))


def test_simulated_curve_rejects_non_positive_currents():
    with pytest.raises(ValueError):
        SimulatedLeakageCurve([300.0, 400.0], [0.0, 100.0])


def test_floor_temperature_finds_the_flat_end():
    T = np.linspace(200.0, 400.0, 21)
    rel = np.where(T < 260.0, 1.0, np.exp((T - 260.0) / 20.0))
    c = SimulatedLeakageCurve(T, rel)
    assert 250.0 <= c.floor_temperature_K() <= 280.0


@_needs_evidence
def test_loaded_curve_matches_the_recorded_evidence():
    c = load_simulated_curve()
    assert c.meta['anchor_K'] == 330.0
    assert float(c.total_rel(330.0)) == pytest.approx(1.0, rel=1e-9), 'anchor is a simulated point'
    assert c.T_K[0] <= 200.0 and c.T_K[-1] >= 500.0
    # The three headline numbers, so a re-run that moves them fails here rather than silently.
    assert float(c.total_rel(200.0)) == pytest.approx(0.126, rel=0.05)
    assert float(c.total_rel(500.0)) == pytest.approx(123.0, rel=0.05)
    assert c.meta['sanity']['PASSES']


@_needs_evidence
def test_gidl_off_is_a_bracket_not_a_variant():
    full = load_simulated_curve(mechanism='full')
    off = load_simulated_curve(mechanism='gidl_off')
    # They must diverge at the cold end and converge at the hot end -- that IS the finding.
    assert float(full.total_rel(200.0)) / float(off.total_rel(200.0)) > 10.0
    assert float(full.total_rel(450.0)) / float(off.total_rel(450.0)) == pytest.approx(1.0, rel=0.2)


@_needs_evidence
def test_simulated_and_analytic_agree_inside_mcpats_own_window():
    """310-400 K is the only range McPAT will simulate; two independent models should agree there.

    They are built from different assumptions -- one is a two-parameter fit to CACTI's table, the
    other is the vendor's full model run in a simulator -- so agreement is a real check, and the
    2x bound is the honest one rather than a tight number chosen after the fact.
    """
    import json
    sim = load_simulated_curve()
    analytic = json.load(open(os.path.join(repo_root_for_evidence(), 'docs', 'evidence',
                                           'device_leakage_asap7.json')))
    for row in analytic['comparison']:
        if 310.0 <= row['T_K'] <= 400.0:
            ratio = row['card_rel'] / float(sim.total_rel(row['T_K']))
            assert 0.5 < ratio < 2.0, 'analytic/simulated = {:.2f} at {} K'.format(ratio,
                                                                                  row['T_K'])


@_needs_toolchain
@_needs_card
def test_the_simulator_actually_evaluates_the_card():
    """End-to-end: the card runs, and leakage rises with temperature.

    This is the test that fails if ngspice is rebuilt without OSDI, if the .osdi is recompiled
    from a different Verilog-A, or if the vendored card stops parsing -- all of which would
    otherwise surface as a plausible wrong curve.
    """
    import tempfile
    ng, osdi = spice_sim.toolchain()
    va = os.path.join(repo_root_for_evidence(), 'spice_toolchain', 'src', 'VA-Models', 'code',
                      'bsimcmg', 'vacode110', 'bsimcmg.va')
    if not os.path.exists(va):
        pytest.skip('VA-Models source not present')
    dev = parse_card()['nmos_rvt']
    card = spice_sim.render_model_card(dev, 'dut', spice_sim.module_name_of(va))
    deck = spice_sim.ioff_deck(card, 'dut', [26.85, 126.85], osdi)
    workdir = tempfile.mkdtemp(prefix='ioff_test_')
    out, _ = spice_sim.run_deck(deck, workdir, name='t')
    rows = spice_sim.parse_ioff(out, nfin=spice_sim.DEFAULT_NFIN)
    assert len(rows) == 2, out[-2000:]
    i300, i400 = rows[0][1], rows[1][1]
    assert i400 > i300, 'off-state leakage must rise with temperature'
    per_um = i300 / spice_sim.effective_width_um(dev, nfin=1)
    assert 1e-11 < per_um < 1e-7, 'I_off {:.3g} A/um is not a 7 nm FinFET'.format(per_um)
