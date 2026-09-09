"""``core_other`` accounting policy -- the ``2 *`` in the McPAT converter, and how to undo it.

`[!]` **This is additive and OFF by default.** ``POLICY_STOCK`` reproduces every recorded result
byte for byte. Nothing in the shipped converter is modified; this corrects the split dict at load
time, behind a flag, exactly as ``--rbb-policy`` and ``--leakage-curve`` do.

What is wrong, and how it was found (§P0.16)
---------------------------------------------
``scripts/mcpat_to_blk_lvl_power_dict.py:get_per_core_total_power`` builds every *itemised*
per-core unit with::

    total_dynamic_power = 2 * runtime_dynamic            # <- a literal 2x
    total_leakage_power = subthreshold_leakage + gate_leakage      # <- no factor

and ~25 lines below builds the bare ``Core<N>`` row -- which is what
``MCPAT_UNIT_NAME_MAP['Core'] = 'core_other'`` maps onto a floorplan block -- through a **different
code path with no factor at all**. So on the die the core's dynamic power is carried three times:
once by ``core_other_<N>`` and twice by its own leaves.

Checked against raw McPAT (``mcpat_output_*.txt``), which is what settles it: the ``Core`` row's
direct children sum to **1.0000x** it for *Runtime Dynamic* and for *Peak Dynamic*, and every
intermediate parent closes on its children to 1.00000. **McPAT itemises 100 % of a core's dynamic
power -- there is no un-itemised dynamic remainder.** Leakage does not close (children are ~0.70x
the parent), so the un-itemised slab is **real for leakage and fictitious for dynamic**.

What the correction does
------------------------
The recorded split is already a *residualised* tree below ``Core<N>``: each intermediate parent
holds ``parent - sum(children)``, built from doubled values, so it holds ``2 x`` the true residual.
Every row under ``Core<N>`` is therefore exactly ``2 x`` its hierarchy-consistent dynamic, and the
correction needs nothing but the JSON's own key structure:

1. every ``Core<N>/...`` row: **dynamic / 2**, leakage untouched;
2. every bare ``Core<N>`` row: **subtract the (undoubled) sum of its subtree** from both columns.
   For dynamic that lands on exactly 0 -- McPAT itemises all of it. For leakage it lands on the
   genuine remainder (~30 % of the core's leakage).

`[!]` **Both steps must be applied together.** Either one alone moves the die's static fraction by
2-5 pp, which is a *larger* error than leaving the whole thing alone: as built the two errors act
on opposite terms and very nearly cancel (static fraction 18.43 % as built, 18.59 % consistent).
That near-cancellation is why the recorded die powers are sound and only the *distribution* is
wrong -- ``core_other``'s share of on-die leakage is overstated ~1.75x (35.6 % -> 20.3 %).
"""
import re

#: Reproduce the recorded catalogue exactly. The default everywhere.
POLICY_STOCK = 'stock'
#: Undo the ``2 *`` and residualise the bare ``Core<N>`` row, so the split matches McPAT's own
#: hierarchy. Changes the *distribution* of power across blocks, barely the die total.
POLICY_CONSISTENT = 'hierarchy-consistent'

CORE_OTHER_POLICIES = (POLICY_STOCK, POLICY_CONSISTENT)

#: The shipped default. `[!]` Changed 'stock' -> 'hierarchy-consistent' on 2 Sep 2026 (§P0.17).
#: Unlike the leakage curve, this is not a modelling preference between two defensible inputs --
#: the stock accounting is **provably wrong**: it carries a literal ``2 * runtime_dynamic`` on
#: itemised per-core units that the bare ``Core<N>`` row never gets, so the die reports roughly
#: HALF McPAT's own static fraction (18.43 % against McPAT's Processor-level 29.36 %; the
#: corrected die gives 32.03 %). The correction is validated leaf-by-leaf against raw McPAT --
#: 864 leaves, three technology nodes, exactly zero error.
#: `[!]` The recorded catalogue is still reproducible EXACTLY -- pass ``--core-other-policy stock``.
DEFAULT_CORE_OTHER_POLICY = POLICY_CONSISTENT

_BARE_CORE = re.compile(r'^Core(\d+)$')
_CORE_CHILD = re.compile(r'^Core(\d+)/')

#: McPAT prints ``Runtime Dynamic`` for a leaf and the converter doubles it. Named rather than
#: written inline so the one magic number in this module is greppable.
CONVERTER_DYNAMIC_FACTOR = 2.0


def is_core_child(unit):
    """True for an itemised per-core row -- the rows the converter doubled."""
    return bool(_CORE_CHILD.match(unit))


def bare_core_index(unit):
    """``N`` for a bare ``Core<N>`` row (the row ``core_other_<N>`` comes from), else ``None``."""
    m = _BARE_CORE.match(unit)
    return int(m.group(1)) if m else None


def apply_core_other_policy(split, policy=POLICY_STOCK):
    """Return a ``{unit: [dynamic, leakage]}`` split under ``policy``.

    ``split`` is the dict loaded from a ``block_powers_split_*.json``. The input is never mutated.
    Under :data:`POLICY_STOCK` the input is returned unchanged (a copy), which is what keeps every
    recorded result reproducible.
    """
    if policy == POLICY_STOCK:
        return {u: list(v) for u, v in split.items()}
    if policy != POLICY_CONSISTENT:
        raise ValueError('unknown core_other policy {!r}; expected one of {}'
                         .format(policy, CORE_OTHER_POLICIES))

    out = {}
    # 1. undouble every itemised per-core row's DYNAMIC column (leakage took no factor).
    for unit, pair in split.items():
        dyn, leak = float(pair[0]), float(pair[1])
        if is_core_child(unit):
            dyn /= CONVERTER_DYNAMIC_FACTOR
        out[unit] = [dyn, leak]

    # 2. residualise each bare Core<N> against its (now undoubled) subtree.
    subtree = {}
    for unit, pair in out.items():
        m = _CORE_CHILD.match(unit)
        if m:
            acc = subtree.setdefault(int(m.group(1)), [0.0, 0.0])
            acc[0] += pair[0]
            acc[1] += pair[1]
    for unit, pair in out.items():
        n = bare_core_index(unit)
        if n is not None and n in subtree:
            out[unit] = [pair[0] - subtree[n][0], pair[1] - subtree[n][1]]
    return out


def core_other_share(split, floorplan_blocks=None):
    """Diagnostic: ``core_other``'s share of the split's dynamic and leakage, as fractions.

    Uses the bare ``Core<N>`` rows, which are what ``core_other_<N>`` carries. Intended for
    reporting and tests, not for the solve path.
    """
    d_all = l_all = d_core = l_core = 0.0
    for unit, pair in split.items():
        if unit.startswith('Processor') or unit in ('BUSES', 'NUCA', 'IMC'):
            continue
        d_all += float(pair[0]); l_all += float(pair[1])
        if bare_core_index(unit) is not None:
            d_core += float(pair[0]); l_core += float(pair[1])
    return {'dynamic_share': d_core / d_all if d_all else 0.0,
            'leakage_share': l_core / l_all if l_all else 0.0,
            'total_dynamic_W': d_all, 'total_leakage_W': l_all}


def materialise_corrected_trace_dir(trace_dir, dest, policy=POLICY_CONSISTENT):
    """Write a policy-corrected copy of ``trace_dir`` into ``dest`` and return ``dest``.

    Why a whole directory rather than a parameter threaded through the solve path: the split
    feeds **two** consumers -- the leakage reference (``load_leakage_ref``, which reads the
    leakage column) and the power trace itself (``block_powers_*.json``, which the converter
    writes as ``dynamic + leakage``). Correcting only one of them would leave the die carrying
    corrected leakage on uncorrected dynamic, which is worse than either policy. Rewriting both
    files means **no downstream code changes at all** -- a driver just points at a different
    trace dir, and every existing call behaves exactly as it always has.

    ``block_powers_*.json`` is regenerated as ``dynamic + leakage`` from the corrected split,
    which is precisely how the shipped converter builds it
    (``thermal_input_dict[unit] = sum(thermal_input_dict[unit])``).

    The McPAT ``energystats-temp-*.xml`` files are copied through unchanged: they carry the
    leakage anchor temperature that ``mcpat_tref_from_trace_dir`` must still be able to read.
    """
    import os
    import glob
    import json
    import shutil

    if policy == POLICY_STOCK:
        return trace_dir                     # nothing to do; use the original tree

    splits = sorted(glob.glob(os.path.join(trace_dir, 'block_powers_split_*.json')))
    if not splits:
        raise ValueError('no block_powers_split_*.json in {} -- the core_other policy needs the '
                         '[dynamic, leakage] split, not the collapsed totals'.format(trace_dir))
    # Idempotent: a campaign forks ~20 workers against ONE trace dir, and each would otherwise
    # rewrite the same files underneath the others. If the destination already holds a complete
    # set, use it. (Re-writing identical content is harmless, but a half-written file read by a
    # concurrent worker is not.)
    if len(glob.glob(os.path.join(dest, 'block_powers_split_*.json'))) == len(splits):
        return dest
    os.makedirs(dest, exist_ok=True)
    for sp in splits:
        with open(sp) as f:
            fixed = apply_core_other_policy(json.load(f), policy)
        base = os.path.basename(sp)
        with open(os.path.join(dest, base), 'w') as f:
            json.dump(fixed, f)
        totals = {u: (v[0] + v[1]) for u, v in fixed.items()}
        with open(os.path.join(dest, base.replace('block_powers_split_', 'block_powers_')), 'w') as f:
            json.dump(totals, f)
    for xml in glob.glob(os.path.join(trace_dir, 'energystats-temp-*.xml')):
        dst = os.path.join(dest, os.path.basename(xml))
        if not os.path.exists(dst):
            shutil.copy2(xml, dst)
    return dest


def default_corrected_dir(trace_dir, policy):
    """Deterministic sibling directory for a corrected trace tree.

    Deterministic (not a temp dir) so that every worker in a campaign shares one materialisation
    instead of each building its own, and so a re-run reuses it.
    """
    import os
    parent, base = os.path.split(os.path.normpath(trace_dir))
    return os.path.join(parent, '{}__core_other_{}'.format(base, policy.replace('-', '_')))


def resolve_trace_dir(trace_dir, policy):
    """``trace_dir`` under ``policy`` -- the one call a driver needs.

    Returns ``trace_dir`` unchanged under :data:`POLICY_STOCK`, so the default path is untouched.
    """
    if policy == POLICY_STOCK:
        return trace_dir
    return materialise_corrected_trace_dir(trace_dir, default_corrected_dir(trace_dir, policy),
                                           policy)
