"""`[+]` §P0.15 -- the measured GIDL-bracket ladder result, pinned.

§P0.14 recorded "run the density ladder on the simulated-gidl-off bracket" as the single
highest-value open item, on the prediction that it would move the flat-die ceiling. It did not.
The uniform arm -- the arm that carries the §P0.11 physics claim -- has the same highest holding
rung and the same lowest failing rung under both brackets.

A negative result is easy to lose: nothing downstream changed, so nothing downstream would notice
if it were quietly re-opened or if a later ladder re-run moved it. These tests hold the two
evidence files against each other so the agreement is asserted rather than remembered.

The *mechanism* -- why the bracket carries ~1.2x the feedback gain where the curve swap carries
6-14x -- is tested in ``test_leakage_curve_select.py`` and needs no campaign results.
"""
import os
import json

import pytest

from HotGauge.power.device_leakage import repo_root_for_evidence

_REPO = repo_root_for_evidence()
_EV = os.path.join(_REPO, 'docs', 'evidence')
_SIM = os.path.join(_EV, 'uniform_density_curve_compare.json')
_OFF = os.path.join(_EV, 'uniform_density_curve_compare_gidl_off.json')

_needs_both = pytest.mark.skipif(
    not (os.path.exists(_SIM) and os.path.exists(_OFF)),
    reason='both ladder comparisons must be generated')


def _cliffs(path, curve):
    return json.load(open(path))['cliffs'], curve


@_needs_both
def test_the_two_brackets_give_the_same_flat_die_ceiling():
    """`[!]` The headline negative result. If this fails, the bracket question is re-opened."""
    sim = json.load(open(_SIM))['cliffs']['uniform']['simulated']
    off = json.load(open(_OFF))['cliffs']['uniform']['simulated-gidl-off']
    assert sim['highest_holding'] == off['highest_holding']
    assert sim['lowest_failing'] == off['lowest_failing']
    # And it is the moved ceiling, not the recorded one -- both brackets fail a rung below
    # the pipeline curve's 1.20.
    assert off['lowest_failing'] == 1.0


@_needs_both
def test_the_shaped_arm_only_gains_a_decision_it_does_not_move():
    """The one place the bracket does something, stated so it is not oversold.

    Under GIDL-on the shaped arm's 0.60 rung is UNCONVERGED -- neither a hold nor a failure, and
    per the standing rule it must not be quoted as either. Under GIDL-off it diverges. That is a
    point becoming decidable, and it is not a ceiling moving: neither bracket has a demonstrable
    hold anywhere on this arm.
    """
    sim = json.load(open(_SIM))['cliffs']['shaped']['simulated']
    off = json.load(open(_OFF))['cliffs']['shaped']['simulated-gidl-off']
    assert sim['highest_holding'] is None and off['highest_holding'] is None
    assert 0.6 in sim['unconverged_densities']
    assert 0.6 not in off['unconverged_densities']
    assert off['lowest_failing'] == 0.6


@_needs_both
def test_the_gidl_off_file_is_labelled_with_its_own_curve():
    """`[!]` Two ladders under one key in two files is how they get compared to each other wrongly.

    Before ``--curve``, this driver hard-coded the second ladder as ``simulated`` -- in the output
    keys *and* in the leakage model the gain table is computed from -- so a GIDL-off run would
    have written GIDL-off cliffs beside full-GIDL gains, under the name of the other bracket.
    """
    off = json.load(open(_OFF))
    assert 'simulated-gidl-off' in off['cliffs']['uniform']
    assert 'simulated' not in off['cliffs']['uniform']
    assert 'simulated-gidl-off' in off['ladders']
    assert 'gidl_off' in off['ladders']['simulated-gidl-off']
    # The gain table must come from the same curve as the ladder.
    assert any(k.startswith('simulated-gidl-off') for k in off['feedback_gain'][0])
