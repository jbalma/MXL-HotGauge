"""Tests for the ``core_other`` accounting policy (§P0.16).

Guarded here:
  * **the default reproduces the recorded catalogue byte for byte** -- the same discipline
    ``--rbb-policy stock`` and ``--leakage-curve pipeline`` follow;
  * **the correction reproduces raw McPAT**, leaf by leaf, which is the only external check there
    is (the JSON cannot validate itself);
  * **the two halves are one correction** -- residualising without undoubling puts *negative* power
    on ``core_other``, which is worse than doing nothing;
  * **`core_other` carries no dynamic** under the policy, because McPAT itemises 100 % of a core's
    dynamic power. That is the claim an earlier write-up got wrong.
"""
import os
import glob
import json

import pytest

from HotGauge.power.core_other import (apply_core_other_policy, materialise_corrected_trace_dir,
                                       core_other_share, is_core_child, bare_core_index,
                                       POLICY_STOCK, POLICY_CONSISTENT, CORE_OTHER_POLICIES)
from HotGauge.power.device_leakage import repo_root_for_evidence

_REPO = repo_root_for_evidence()
_TRACE = os.path.join(_REPO, 'mcpat_runs', '7nm', 'linpack_3.8GHz')
_needs_trace = pytest.mark.skipif(
    not glob.glob(os.path.join(_TRACE, 'block_powers_split_*.json')),
    reason='McPAT trace not present')


def _split():
    fp = sorted(glob.glob(os.path.join(_TRACE, 'block_powers_split_*.json')))[0]
    return json.load(open(fp))


def test_stock_is_the_default_and_is_a_faithful_copy():
    src = {'Core0': [3.0, 0.2], 'Core0/Load Store Unit/Data Cache': [1.0, 0.05],
           'Processor/Total L3s': [0.1, 1.2], 'IMC': [0.5, 0.0]}
    out = apply_core_other_policy(src)                     # no policy argument at all
    assert out == src
    assert out is not src and out['Core0'] is not src['Core0'], 'must not alias the input'


def test_unknown_policy_is_refused():
    with pytest.raises(ValueError):
        apply_core_other_policy({}, 'amortized')
    assert CORE_OTHER_POLICIES == (POLICY_STOCK, POLICY_CONSISTENT)


def test_key_classification():
    assert is_core_child('Core0/Execution Unit/Integer ALUs')
    assert not is_core_child('Core0')
    assert not is_core_child('Processor/Total L3s')
    assert bare_core_index('Core12') == 12
    assert bare_core_index('Core12/L2') is None
    assert bare_core_index('Processor') is None


def test_correction_undoubles_children_and_empties_the_dynamic_remainder():
    src = {'Core0': [10.0, 1.0],
           'Core0/A': [12.0, 0.4],          # doubled: true dynamic 6.0
           'Core0/A/B': [8.0, 0.3],         # doubled: true dynamic 4.0
           'Processor': [99.0, 9.0]}
    out = apply_core_other_policy(src, POLICY_CONSISTENT)
    assert out['Core0/A'] == [6.0, 0.4]
    assert out['Core0/A/B'] == [4.0, 0.3]
    assert out['Core0'] == [0.0, pytest.approx(0.3)]   # 10 - (6+4) dyn; 1.0 - 0.7 leak
    assert out['Processor'] == [99.0, 9.0], 'non-core rows must be untouched'


def test_residualising_without_undoubling_would_go_negative():
    """Why the two halves are ONE correction and must never be shipped separately."""
    src = {'Core0': [10.0, 1.0], 'Core0/A': [12.0, 0.4], 'Core0/A/B': [8.0, 0.3]}
    kids = src['Core0/A'][0] + src['Core0/A/B'][0]
    assert src['Core0'][0] - kids < 0, 'residualise-only puts negative power on core_other'


@_needs_trace
def test_correction_reproduces_raw_mcpat_leaf_by_leaf():
    """The external check: every corrected leaf must equal McPAT's own ``Runtime Dynamic``.

    Uses the recorded ``mcpat_output_*.txt`` alongside the split. Parses names the way Sniper's
    own parser does -- stopping at ``:`` OR ``(`` -- because McPAT writes
    ``Integer ALUs (Count: 6 ):`` and a ``:``-only split silently drops the execution units.
    """
    import re
    txts = sorted(glob.glob(os.path.join(_TRACE, 'mcpat_output_*.txt')))
    if not txts:
        pytest.skip('raw McPAT text output not present')
    txt = txts[0]
    split = json.load(open(txt.replace('mcpat_output_', 'block_powers_split_')
                              .replace('.txt', '.json')))
    fixed = apply_core_other_policy(split, POLICY_CONSISTENT)

    # Only LEAVES may be compared against McPAT's raw Runtime Dynamic. Intermediate parents are
    # residualised (parent - sum(children)) and land near zero by construction -- comparing one
    # against the raw parent value is what a first version of this test got wrong.
    leaf = {k for k in fixed
            if not any(o != k and o.startswith(k + '/') for o in fixed)}

    # walk the text, tracking the (indent -> name) prefix stack, exactly as the converter does
    core_i, prefix, spaces, seen = -1, [], [], 0
    for line in open(txt, errors='replace'):
        raw = line.rstrip()
        if not raw.strip() or raw.lstrip().startswith('*'):
            continue
        m = re.match(r'^( *)([^=:(]+?)\s*=\s*(-?[\d.]+(?:[eE][-+]?\d+)?)', raw)
        if m and prefix:
            if m.group(2).strip() == 'Runtime Dynamic':
                key = 'Core%d' % core_i + ('/' + '/'.join(prefix[1:]) if len(prefix) > 1 else '')
                if core_i >= 0 and key in leaf and '/' in key:
                    assert fixed[key][0] == pytest.approx(float(m.group(3)), abs=1e-9), key
                    seen += 1
            continue
        if '=' in raw:
            continue
        mm = re.match(r'^( *)([^:(]*)', raw)
        name = mm.group(2).strip()
        if not name:
            continue
        j = len(mm.group(1))
        while spaces and j <= spaces[-1]:
            spaces.pop(); prefix.pop()
        spaces.append(j); prefix.append(name)
        if len(prefix) == 1 and name == 'Core':
            core_i += 1
    assert seen > 100, 'expected to check many leaves, saw %d' % seen


@_needs_trace
def test_core_other_carries_no_dynamic_under_the_policy():
    """McPAT itemises 100 % of a core's dynamic power, so the slab is leakage-only.

    An earlier §P0.16 write-up claimed the corrected slab still held ~2 W of modelled IMC/IO/SoC
    dynamic. It does not; that was a text-parser artefact.
    """
    fixed = apply_core_other_policy(_split(), POLICY_CONSISTENT)
    for unit, pair in fixed.items():
        if bare_core_index(unit) is not None:
            assert abs(pair[0]) < 1e-4, '%s should carry no dynamic, got %g' % (unit, pair[0])
            assert pair[1] > 0.0, '%s should carry a POSITIVE leakage remainder' % unit


@_needs_trace
def test_the_policy_raises_the_static_fraction_toward_mcpats_own():
    """The headline: the `2 *` roughly halves the apparent static fraction."""
    split = _split()
    stock = core_other_share(apply_core_other_policy(split, POLICY_STOCK))
    fixed = core_other_share(apply_core_other_policy(split, POLICY_CONSISTENT))
    f_stock = stock['total_leakage_W'] / (stock['total_dynamic_W'] + stock['total_leakage_W'])
    f_fixed = fixed['total_leakage_W'] / (fixed['total_dynamic_W'] + fixed['total_leakage_W'])
    assert f_fixed > f_stock * 1.4, 'the correction should raise the static fraction substantially'
    assert fixed['leakage_share'] < stock['leakage_share'], \
        "core_other's share of leakage must fall"


@_needs_trace
def test_materialise_is_a_no_op_under_stock(tmp_path):
    dest = str(tmp_path / 'x')
    assert materialise_corrected_trace_dir(_TRACE, dest, POLICY_STOCK) == _TRACE
    assert not os.path.exists(dest), 'stock must not write anything'


@_needs_trace
def test_materialise_writes_both_files_and_keeps_the_anchor(tmp_path):
    from HotGauge.thermal.leakage_feedback import mcpat_tref_from_trace_dir
    dest = materialise_corrected_trace_dir(_TRACE, str(tmp_path / 'fixed'), POLICY_CONSISTENT)
    n_split = len(glob.glob(os.path.join(dest, 'block_powers_split_*.json')))
    n_tot = len(glob.glob(os.path.join(dest, 'block_powers_*.json'))) - n_split
    assert n_split == n_tot > 0, 'both the split and the collapsed totals must be written'
    assert mcpat_tref_from_trace_dir(dest) == 330.0, 'the leakage anchor must survive the copy'
    # the totals must be the corrected split's own sum -- that is how the converter builds them
    fp = sorted(glob.glob(os.path.join(dest, 'block_powers_split_*.json')))[0]
    sp = json.load(open(fp))
    tot = json.load(open(fp.replace('block_powers_split_', 'block_powers_')))
    for u, pair in sp.items():
        assert tot[u] == pytest.approx(pair[0] + pair[1], abs=1e-12)


@pytest.mark.parametrize('driver', ['mr_comparison', 'clock_headroom', 'mr_clipping_study',
                                    'uniform_density_probe', 'cold_zone_prize'])
def test_every_driver_defaults_to_the_corrected_policy(driver):
    """`[!]` The default CHANGED on 2 Sep 2026 (§P0.17): stock -> hierarchy-consistent.

    This is not a modelling preference between two defensible inputs. The stock accounting is
    provably wrong -- a literal ``2 * runtime_dynamic`` on itemised per-core units that the bare
    ``Core<N>`` row never gets -- and the die reports roughly HALF McPAT's own static fraction
    because of it. The correction is validated leaf-by-leaf against raw McPAT with zero error.

    Every driver must agree, or a results table mixes two accountings and nobody can tell which
    rows are which.
    """
    import ast
    src = os.path.join(_REPO, 'examples', '%s.py' % driver)
    if not os.path.exists(src):
        pytest.skip('%s not present' % driver)
    found = []
    for node in ast.walk(ast.parse(open(src).read())):
        if not (isinstance(node, ast.Call) and getattr(node.func, 'attr', None) == 'add_argument'):
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == '--core-other-policy'):
            continue
        found.append({k.arg: k.value for k in node.keywords})
    assert len(found) == 1, '%s should declare --core-other-policy exactly once' % driver
    default = found[0].get('default')
    assert default is not None, '%s: --core-other-policy must state a default' % driver
    name = getattr(default, 'id', None) or getattr(default, 'value', None)
    assert name in ('DEFAULT_CORE_OTHER_POLICY', POLICY_CONSISTENT), \
        '%s: expected the corrected default, got %r' % (driver, name)


def test_the_default_constant_is_the_corrected_policy():
    from HotGauge.power.core_other import DEFAULT_CORE_OTHER_POLICY
    assert DEFAULT_CORE_OTHER_POLICY == POLICY_CONSISTENT


@_needs_trace
def test_the_recorded_accounting_is_still_exactly_reachable():
    """`[!]` Changing a default is only safe if the OLD behaviour stays reachable and exact.

    Every recorded result in the catalogue was produced under ``stock``; ``--core-other-policy
    stock`` must still reproduce it byte-for-byte, or the back catalogue becomes unverifiable.
    """
    split = _split()
    assert apply_core_other_policy(split, POLICY_STOCK) == {u: list(v) for u, v in split.items()}
    assert materialise_corrected_trace_dir(_TRACE, '/nonexistent', POLICY_STOCK) == _TRACE, \
        'stock must not materialise anything -- it uses the recorded trace as it stands'


@_needs_trace
def test_the_correction_actually_moves_the_die(tmp_path):
    """Guard against a silently inert flag: the corrected tree must differ from the recorded one."""
    dest = materialise_corrected_trace_dir(_TRACE, str(tmp_path / 'fixed'), POLICY_CONSISTENT)
    a = json.load(open(sorted(glob.glob(os.path.join(_TRACE, 'block_powers_split_*.json')))[0]))
    b = json.load(open(sorted(glob.glob(os.path.join(dest, 'block_powers_split_*.json')))[0]))
    moved = [u for u in a if abs(a[u][0] - b[u][0]) > 1e-9 or abs(a[u][1] - b[u][1]) > 1e-9]
    # 61 of 280 on the 7nm trace: the rows carrying real dynamic, plus every bare Core row.
    # Residualised intermediate parents sit at ~0 and stay there, so they do not count.
    assert len(moved) > 50, 'the policy should move many rows, moved %d' % len(moved)
    bare = [u for u in a if bare_core_index(u) is not None]
    assert bare and set(bare) <= set(moved), 'every bare Core row must move'
