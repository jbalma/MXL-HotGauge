"""Results-broadcast-bus placement policy -- the one accounting entry that gated high density.

What McPAT actually publishes
-----------------------------
``Execution Unit/Results Broadcast Bus`` is reported as an **Area Overhead**, not an ``Area``.
The project's own ``isa_floorplans._root_area`` exists because of that spelling. Two facts from
McPAT's source settle what the spelling means, and they are the reason this module exists:

* **The bus is wire, and the wire spans the cluster.** ``EXECU::EXECU`` (``McPAT/core.cc``
  ~1150-1259) builds ``bypass`` out of ``interconnect`` objects whose *length* argument is
  ``rfu->int_regfile_height + exeu->FU_height + lsq_height`` -- plus ``scheu->Iw_height`` for the
  tag bus. ``RegFU``'s own comment (``core.cc`` ~989) states it: *"the bypass buses need to
  travel across all the register files."* The area is real silicon -- wire tracks -- but it is
  distributed over the execution cluster by construction.
* **It is already inside its parent.** ``core.cc:1265`` -- ``area.set_area(area.get_area() +
  bypass.area.get_area())`` -- folds the bus area into the Execution Unit's own area. "Area
  Overhead" means *itemised, and already counted in the parent*. It does not mean "a block".

What the shipped tiler does with it
-----------------------------------
``examples/floorplans.py`` (**stock** HotGauge, present in the initial commit) renames the key::

    # Make RBB Area instead of Area Overhead
    stats['Core'][unit_name] = stats['Core'][unit_name + ' Overhead']

and the tiler then renders the bus as a discrete rectangle -- 142 x 13 um, 0.0019 mm^2, 0.064 %
of the die on the 34-core floorplan -- and hands it the bus's full power. That is upstream's
deliberate choice, not a defect introduced here, and Fig. 5 of the paper shows RBB as a block.
This module therefore **defaults to leaving it alone** (``policy='stock'``) and makes the
alternative explicit and opt-in.

Why the alternative is needed
-----------------------------
Leakage feedback is exponential in temperature, so the hottest block decides whether the coupled
solve has a fixed point at all. RBB is the hottest block on every die this project has simulated:
past 400 K -- the top of the calibrated leakage table -- the Arrhenius tail multiplies its leakage
by hundreds and it reaches thousands of kelvin on iteration one (36 466 K measured). Every
question asked above ~1.8 W/mm^2 then returns "diverged" whatever else was varied, which is why
sweeping ``dt_max`` over 6.7x and ``h_max`` over 120x changed nothing. See
``docs/evidence/rbb_is_the_gate.json``.

`[!]` The density argument is NOT the reason, and must not be repeated
----------------------------------------------------------------------
Three places in this repo's history justified the change by claiming real blocks sit at
1-3 W/mm^2, so RBB's 53 W/mm^2 must be unphysical. **That claim is false.** The HotGauge paper
(SII-A) reports >8 W/mm^2 within a core, literature hotspot definitions are 6.8-10, and our own
measured distribution on these dies has block p90 = 13.2 and p99 = 64.4 W/mm^2, with ``iBuf`` at
141. RBB's density sits *inside* that distribution. The case for amortizing rests entirely on the
area semantics above -- on what McPAT's geometry says the bus is -- and not on its density.

What ``policy='amortized'`` does
--------------------------------
Moves the bus's power onto the execution-unit blocks it spans, in proportion to their area, and
leaves the RBB rectangle in the floorplan carrying zero power. That is deliberate: the rectangle
stands for wire tracks that are real silicon but physically elsewhere, so deleting it would
shrink the die, while re-tiling to grow its neighbours would change every block's coordinates and
make the two policies incomparable. Power moves; geometry does not. The transform is
power-conserving to floating-point tolerance and idempotent.

The recipient set is McPAT's own ``Execution Unit`` membership as the shipped tiler places it.
`[!]` It is NOT the set used by ``docs/evidence/rbb_amortization.json``: that file named
``regs`` and ``iSched``, which the tiler never places (it subdivides them), and so silently
excluded the scheduler blocks the tag bus explicitly spans -- 204 recipient blocks where there
should have been 306. ``span='exec+lsq'`` adds the load-store queues, which McPAT's *wire length*
includes even though its *area accounting* does not; it is offered to size that ambiguity, not
because it is better.

Applying it
-----------
Once, on the baseline McPAT-named trace, before the feedback loop -- so the planner, the
accounting and the solver all see the same trace. **Both** the trace and ``leakage_ref`` must be
passed: ``rescale_trace`` rebuilds each unit's power as ``series - leak + leak*scale(T)``, so
zeroing a donor's series while leaving its baseline leakage behind would re-inject the bus, with
a negative power below ``T_ref``.
"""
import re

import numpy as np

RBB_POLICIES = ('stock', 'amortized')

#: Floorplan-name stem of the bus itself.
RBB_STEM = 'RBB'

#: The blocks McPAT's ``Execution Unit`` decomposes into, as the shipped tiler names them.
#: Parents (``regs``, ``iSched``) and their children (``iRF``/``fpRF``, ``iWin``/``fpiWin``/
#: ``ROB``) are both listed because which of the two a given floorplan places depends on how far
#: the tiler subdivided; they are never both present, and the code asserts that.
EXEC_UNIT_STEMS = ('cALU', 'iALU', 'FPUs', 'AVXs', 'AVX_FPU',
                   'regs', 'iRF', 'fpRF',
                   'iSched', 'iWin', 'fpiWin', 'ROB')

#: Added by ``span='exec+lsq'``. McPAT's bypass *wire length* includes ``lsq_height``, so the
#: copper does run over these; its *area* is booked to EXECU, which does not contain them.
LSQ_STEMS = ('LoadQ', 'StoreQ')

SPANS = {'exec': EXEC_UNIT_STEMS,
         'exec+lsq': EXEC_UNIT_STEMS + LSQ_STEMS}

_CORE_IDX_RE = re.compile(r'^(?P<stem>.+?)_(?P<idx>\d+)$')


def split_block_name(block):
    """``'iALU_7'`` -> ``('iALU', 7)``; ``'IMC'`` -> ``('IMC', None)``."""
    m = _CORE_IDX_RE.match(block)
    if m is None:
        return block, None
    return m.group('stem'), int(m.group('idx'))


def block_areas_mm2(floorplan):
    """``{block_name: area_mm^2}`` from a 3D-ICE floorplan path, ``Floorplan``, or dict.

    A dict is passed straight through so the redistribution can be unit-tested without a
    floorplan file, which is most of why this is a separate function.
    """
    if isinstance(floorplan, dict):
        return dict(floorplan)
    if isinstance(floorplan, str):
        from HotGauge.thermal.ICE import Floorplan
        floorplan = Floorplan.from_file(floorplan)
    return {e.name: (e.width * e.height) / 1.0e6 for e in floorplan.elements}


def _as_array(v):
    return np.atleast_1d(np.asarray(v, dtype=float))


def rbb_recipients(areas, span='exec', skip_no_power=True):
    """``{core_idx: {block: area_mm^2}}`` -- who receives the bus power on each core.

    Raises if a floorplan places both a parent and its children (e.g. ``regs`` beside ``iRF``),
    which would double-count that area in the weights.

    `[!]` ``skip_no_power`` drops blocks the power model forces to zero -- ``AVXs_*`` on every
    trace without AVX power data. This is not a nicety: those blocks are zeroed downstream, so
    power routed to them would be **silently destroyed** between here and the solver. It is an
    execution unit by area and would otherwise be a recipient, so the exclusion is deliberate
    and belongs on the record rather than falling out of which units a trace happens to carry.
    """
    from HotGauge.configuration.power_model import is_no_power_unit
    try:
        stems = SPANS[span]
    except KeyError:
        raise ValueError('span must be one of {}, got {!r}'.format(sorted(SPANS), span))
    out = {}
    for block, area in areas.items():
        stem, idx = split_block_name(block)
        if stem in stems and not (skip_no_power and is_no_power_unit(block)):
            out.setdefault(idx, {})[block] = area
    for idx, blocks in out.items():
        stems_here = {split_block_name(b)[0] for b in blocks}
        for parent, children in (('regs', {'iRF', 'fpRF'}),
                                 ('iSched', {'iWin', 'fpiWin', 'ROB'})):
            if parent in stems_here and (children & stems_here):
                raise ValueError(
                    'floorplan places {!r} alongside its children {} on core {}: the recipient '
                    'weights would count that area twice'
                    .format(parent, sorted(children & stems_here), idx))
    return out


def amortize_rbb(trace, floorplan, policy='stock', leakage_ref=None, name_map=None,
                 span='exec', rbb_stem=RBB_STEM):
    """Apply the RBB placement policy to a McPAT-named trace (and its leakage reference).

    Returns ``(trace, leakage_ref, meta)``. ``policy='stock'`` returns the inputs unchanged --
    the same objects -- so a driver can call this unconditionally and pay nothing.

    ``name_map`` maps a trace unit name to a floorplan block name; defaults to
    ``leakage_feedback.mcpat_flp_name_map(include_core_idx=True)``. Units it maps to ``None``,
    and units whose block is absent from the floorplan, are left alone and counted in ``meta``.
    """
    if policy not in RBB_POLICIES:
        raise ValueError('policy must be one of {}, got {!r}'.format(RBB_POLICIES, policy))
    if policy == 'stock':
        return trace, leakage_ref, {'policy': 'stock', 'moved_W': 0.0, 'n_donor_units': 0,
                                    'rule': 'RBB placed as a block, as shipped'}

    from HotGauge.power.traces import BasicPowerTrace
    if name_map is None:
        from HotGauge.thermal.leakage_feedback import mcpat_flp_name_map
        name_map = mcpat_flp_name_map(include_core_idx=True)

    areas = block_areas_mm2(floorplan)
    recipients_by_core = rbb_recipients(areas, span=span)

    # unit -> block, for every unit the trace carries that lands on a placed block
    blocks = {}
    for unit in trace.powers:
        b = name_map(unit)
        if b is not None and b in areas:
            blocks[unit] = b

    donors = {u: b for u, b in blocks.items() if split_block_name(b)[0] == rbb_stem}
    if not donors:
        raise ValueError(
            'no {} unit in the trace maps onto a block of the floorplan -- the amortized policy '
            'would be a silent no-op. Check the name map and the floorplan.'.format(rbb_stem))

    # Recipient units, grouped by the core their bus belongs to. Two units mapping to one block
    # would make the weights sum past 1, so that is refused rather than silently normalised.
    recip_units = {}
    for unit, b in blocks.items():
        stem, idx = split_block_name(b)
        if idx in recipients_by_core and b in recipients_by_core[idx]:
            if b in recip_units.setdefault(idx, {}):
                raise ValueError('two trace units map to block {!r}: {!r} and {!r}'
                                 .format(b, recip_units[idx][b], unit))
            recip_units[idx][b] = unit

    powers = {u: _as_array(v).copy() for u, v in trace.powers.items()}
    leaks = None
    if leakage_ref is not None:
        leaks = {u: (_as_array(v).copy() if np.ndim(v) else float(v))
                 for u, v in leakage_ref.items()}

    moved_W = 0.0
    moved_leak_W = 0.0
    per_core = {}
    for unit, b in sorted(donors.items()):
        idx = split_block_name(b)[1]
        targets = recip_units.get(idx) or {}
        if not targets:
            raise ValueError(
                'block {!r} has no execution-unit blocks on core {} to amortize onto. Its power '
                'must not be dropped, so this is an error rather than a skip.'.format(b, idx))
        total_area = sum(areas[t] for t in targets)
        if total_area <= 0.0:
            raise ValueError('recipient blocks for {!r} have zero total area'.format(b))

        donor_p = powers[unit]
        moved_W += float(np.mean(donor_p))
        for tb, tu in targets.items():
            w = areas[tb] / total_area
            powers[tu] = powers[tu] + donor_p * w
        powers[unit] = np.zeros_like(donor_p)

        if leaks is not None and unit in leaks:
            donor_l = leaks[unit]
            moved_leak_W += float(np.mean(_as_array(donor_l)))
            for tb, tu in targets.items():
                w = areas[tb] / total_area
                if tu in leaks:
                    leaks[tu] = leaks[tu] + donor_l * w
                else:
                    leaks[tu] = donor_l * w
            leaks[unit] = np.zeros_like(_as_array(donor_l)) if np.ndim(donor_l) else 0.0

        per_core[b] = {'core': idx, 'n_recipients': len(targets),
                       'recipient_area_mm2': total_area,
                       'rbb_area_mm2': areas[b],
                       'power_W': float(np.mean(donor_p))}

    # Conservation, per timestep, on the quantity that reaches the solver.
    before = np.sum([_as_array(v) for v in trace.powers.values()], axis=0)
    after = np.sum(list(powers.values()), axis=0)
    if not np.allclose(before, after, rtol=1e-9, atol=1e-9):
        raise AssertionError('amortization lost power: {} W in, {} W out'
                             .format(before.sum(), after.sum()))

    n_recip = sum(v['n_recipients'] for v in per_core.values())
    rbb_area = sum(v['rbb_area_mm2'] for v in per_core.values())
    recip_area = sum(v['recipient_area_mm2'] for v in per_core.values())
    meta = {
        'policy': 'amortized',
        'span': span,
        'rule': ('RBB power redistributed over the execution-unit blocks of its own core, in '
                 'proportion to block area; the RBB rectangle stays in the floorplan at zero '
                 'power'),
        'n_donor_units': len(donors),
        'n_recipient_blocks': n_recip,
        'moved_W': moved_W,
        'moved_leakage_W': moved_leak_W if leaks is not None else None,
        'rbb_area_mm2': rbb_area,
        'recipient_area_mm2': recip_area,
        'density_as_placed_W_per_mm2': (moved_W / rbb_area) if rbb_area > 0 else None,
        'density_amortized_W_per_mm2': (moved_W / recip_area) if recip_area > 0 else None,
        'n_units_left_alone': len(trace.powers) - len(donors) - n_recip,
        'per_block': per_core,
        'WHY': ('McPAT publishes the bus as an Area Overhead already folded into the EXECU area '
                '(core.cc:1265) and builds it from interconnect wires whose length spans the '
                'register file, the functional units and the LSQ (core.cc ~1150-1259). The '
                'compact rectangle the tiler gives it is a fictitious footprint. This is an '
                'area-semantics argument, NOT a density one -- see the module docstring.'),
    }
    out_trace = BasicPowerTrace(powers, trace.time_step)
    return out_trace, (leaks if leaks is not None else None), meta


#: The shipped default. `[!]` Changed 'stock' -> 'amortized' on 2 Sep 2026 (§P0.17), on the
#: evidence the standing rule asked for: "``stock`` ships as the default until a catalogue re-run
#: says otherwise". The re-run said otherwise. §P0.16's arm B -> arm C isolates this flag across
#: 145 catalogue points and flips **no verdict in either direction**; it moves temperatures a
#: little (control −0.55 K mean, array arm −3.02 K). §P0.10 had already settled the semantics from
#: McPAT's own source (``core.cc`` folds the bus's ``Area Overhead`` into the Execution Unit).
#: `[!]` The recorded catalogue is still reproducible EXACTLY -- pass ``--rbb-policy stock``.
DEFAULT_RBB_POLICY = 'amortized'


def add_rbb_argument(ap, default=None):
    """Add ``--rbb-policy`` to a driver's parser.

    Kept here so every driver spells the flag, the choices and the help text identically -- a
    results table that mixes ``--rbb`` and ``--rbb-policy`` across drivers is a table nobody can
    re-run. Default is :data:`DEFAULT_RBB_POLICY`; pass ``default='stock'`` to pin the shipped
    placement for a driver that must reproduce a recorded row un-flagged.
    """
    if default is None:
        default = DEFAULT_RBB_POLICY
    ap.add_argument('--rbb-policy', choices=RBB_POLICIES, default=default,
                    help='how to treat the results-broadcast bus. "stock" (default) places it '
                         'as a block, as shipped HotGauge does. "amortized" moves its power onto '
                         'the execution-unit blocks it spans, which is what McPAT\'s "Area '
                         'Overhead" means. "stock" places it as a block, as shipped HotGauge '
                         'does, and reproduces the recorded catalogue -- see '
                         'HotGauge.thermal.rbb.')
    ap.add_argument('--rbb-span', choices=sorted(SPANS), default='exec',
                    help='with --rbb-policy amortized, which blocks receive the power '
                         '(default: exec -- the Execution Unit, which is where McPAT books the '
                         'bus area)')
