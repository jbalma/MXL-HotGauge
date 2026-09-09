"""Tests for the post-hoc recovery correction of ``FINDINGS.json`` (§P0.16).

What is worth guarding here is the *reason the correction is legitimate without a re-solve*, not
the arithmetic. Three things carry that:

  * ``recovery_at_junction`` is pure accounting, so ``net_new = net_old * (1 - r_new)/(1 - r_old)``
    is exact rather than an approximation;
  * **``gross``, ``cop`` and spot dilution all cancel** in that ratio -- which is what lets one
    formula cover ``overnight3[26]``, whose 5.24x dilution overhead makes its ``net/q`` look like
    a different efficiency preset;
  * a negative ``p_mr_net_W`` is a *net-generating cooler*, and every one of them must come back
    positive, or the first-law bug is still in the ledger.
"""
import os
import sys

import pytest

from HotGauge.power.device_leakage import repo_root_for_evidence
from HotGauge.thermal.microrefrigeration import MRParams

_REPO = repo_root_for_evidence()
sys.path.insert(0, os.path.join(_REPO, 'examples'))

try:
    from findings_recovery_correction import correct_row, negative_net_rows
except Exception:                                              # pragma: no cover
    correct_row = negative_net_rows = None

_needs_driver = pytest.mark.skipif(correct_row is None, reason='correction driver not importable')


@_needs_driver
def test_recovers_the_audited_row():
    """``overnight3[11]``: -0.596 W must become +3.35 W -- the sign flip the audit predicted."""
    row = {'peak_C': 72.2614685058594, 'p_mr_net_W': -0.595793009012656,
           'heat_removed_W': 5.033251910269931}
    c = correct_row(row, MRParams(313.15))
    assert c['p_mr_net_W_corrected'] == pytest.approx(3.35, abs=0.01)
    assert c['sign_flipped'] is True


@_needs_driver
def test_dilution_and_cop_cancel():
    """Two rows at the same junction temperature differing ONLY by spot dilution must take the
    same correction FACTOR. This is why no preset has to be identified per row -- and identifying
    one from ``net/q`` would have mis-read ``overnight3[26]``'s 5.24x dilution as a preset."""
    p = MRParams(313.15)
    plain = correct_row({'peak_C': 78.06984863281252, 'p_mr_net_W': -0.06089991188959676}, p)
    diluted = correct_row({'peak_C': 78.06984863281252, 'p_mr_net_W': -0.3190493794343414}, p)
    assert plain['correction_factor'] == pytest.approx(diluted['correction_factor'], rel=1e-12)
    # ... and the ratio between the two corrected values is preserved exactly.
    assert (diluted['p_mr_net_W_corrected'] / plain['p_mr_net_W_corrected']
            == pytest.approx(0.3190493794343414 / 0.06089991188959676, rel=1e-12))


@_needs_driver
def test_second_law_ratio_is_below_the_first_law_one():
    """``phi < 1`` at any real junction temperature, so the second-law ratio is strictly smaller
    -- which is the whole reason a net-generating row was possible under the first-law form."""
    p = MRParams(313.15)
    c = correct_row({'peak_C': 90.0, 'p_mr_net_W': -1.0}, p)
    assert 0.0 < c['phi'] < 1.0
    assert c['ratio_second_law'] < c['ratio_first_law']
    assert c['ratio_first_law'] > 1.0          # the first-law form is net-generating: the bug
    assert c['ratio_second_law'] < 1.0         # the second-law form is not


@_needs_driver
def test_a_row_without_peak_C_is_refused_not_guessed():
    assert correct_row({'p_mr_net_W': -1.0}, MRParams(313.15)) is None


@_needs_driver
def test_finds_exactly_the_audited_negative_rows():
    import json
    ev = os.path.join(_REPO, 'docs', 'evidence', 'FINDINGS.json')
    if not os.path.exists(ev):
        pytest.skip('FINDINGS.json not present')
    rows = negative_net_rows(json.load(open(ev)))
    assert len(rows) == 36, 'the audit sized the exposure at 36 negative p_mr_net_W entries'
    p = MRParams(313.15)
    corrected = [correct_row(r, p) for _, r in rows]
    assert all(c is not None and c['sign_flipped'] for c in corrected), \
        'every net-generating row must come back net-consuming'
