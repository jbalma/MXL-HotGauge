"""Reader for the MXL-HotGauge Floorplan Pack -- published block areas, with the traps handled.

Why this exists
---------------
``docs/chip_design_lit/MXL-HotGauge-Floorplan-Pack/`` (assembled 28 Aug 2026) is the input this
project was blocked on: 165 rows of **published** block-level areas in mm^2, each citing the
plate it was transcribed from. Until it arrived, every ARM and RISC-V floorplan here was an area
*re-weighting* of the Skylake-class McPAT unit mix with ``calibrated = False``, because there were
zero ARM or RISC-V die shots in the repository. There are now 11 ARM and 3 RISC-V annotated
floorplans and a fully decomposed x86 core.

This module is the loader. It exists as a module rather than a few lines of ``csv.DictReader`` in
each caller **because the file has three ways to be read wrongly that all fail silently**, and a
silent wrong answer that is off by 9.55% is worse than an exception.

The three traps, each with a guard and a test
---------------------------------------------
1. **``block_areas.csv`` mixes hierarchy levels.** Golden Cove has ten area rows and four of them
   are nested *inside* the other six. Summing all ten overstates the core by **+9.55%**; the
   correct non-overlapping six close to **-1.35%** against the published ``core_total``. The pack
   README lists the right six but never says the others are nested, so anyone filtering by
   ``chip`` and summing gets the wrong number with no warning. ``non_overlapping_blocks()`` is the
   only sanctioned way to get a chip's block set, and ``NESTED_BLOCKS`` records the parentage.

2. **``manifest.csv:category`` values are not the folder names.** Annotated floorplans live in
   ``images/floorplans/`` but their category is ``die_floorplan_annotated``. Filtering on the
   folder name returns **zero rows**, not an error. ``CATEGORIES`` names them and
   ``manifest_rows(category=...)`` rejects a category that is not one of them.

3. **The V/F anchor voltage column is ``voltage_v``, not ``vdd_v``.** Guessing gives "0 rows with
   a real voltage", which is wrong -- there are two, both Arm Neoverse at 0.75 V.
   ``vf_anchors_with_voltage()`` returns them and asserts the count is not zero.

What the pack does and does not give
------------------------------------
* **Gives**: areas, and for nine rows a matching power. Every row cites ``source_image``.
* **Does not give geometry.** No x, y, w, h anywhere in the pack -- areas alone do not fix
  placement or aspect ratio. That has to be read off the annotated plates by eye, which is what
  ``core_templates.py`` does for the Golden Cove / Redwood Cove pair.
* Power on only 9 of 165 rows, and the pack's own README says the numbers are hand-transcribed
  from images and not cross-checked against a second source. ``provenance`` for a chip's areas is
  therefore "published, transcribed by hand", which is a long way better than a press ratio and a
  long way short of a measurement we made.

The licensing constraint, because it binds on what can be published
-------------------------------------------------------------------
104 of the pack's images are SemiAnalysis paid-subscriber content, many watermarked, and much of
the rest is third-party (TechInsights explicitly not redistributable). **The plates are internal
reference only and must not be embedded in the published handbook artifact.** Figures our own code
draws from pack *numbers* are fine -- the pack README makes the same point, that the published
numbers are the durable asset. Nothing in this module reads or emits an image; it reads CSVs.
"""
import os
import csv


PACK_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
    'docs', 'chip_design_lit', 'MXL-HotGauge-Floorplan-Pack'))

#: Trap 2. ``manifest.csv:category`` values, which are NOT the ``images/`` folder names. The
#: mapping is recorded so a caller who has a folder name can convert rather than guess.
CATEGORIES = {
    'die_floorplan_annotated': 'images/floorplans',
    'block_diagram': 'images/block_diagrams',
    'die_photo_plain': 'images/die_photos',
    'area_data_table': 'images/area_tables',
    'stack_source': 'images/stack_sources',
    'process_micrograph': 'images/micrographs',
}

#: ``floorplans/`` versus ``block_diagrams/`` is a real distinction and the pack README says so:
#: a floorplan is a placed layout, where position and adjacency mean something; a block diagram is
#: a logical dataflow drawing, where they mean nothing. Never infer placement from the latter.
PLACEMENT_BEARING_CATEGORIES = ('die_floorplan_annotated', 'die_photo_plain')

#: Trap 1. Block -> the block it is drawn INSIDE, per chip family. Summing a chip's rows without
#: removing these double-counts.
#:
#: Two of the four are named in the pack README (``fma_eus_port_0_1`` in ``fpu_incl_fma_eus``,
#: ``l2_sram_block_256kb`` in ``l2_cache``). The other two are not, and their *names* point at the
#: wrong parent: ``fpu_register_file`` and ``int_register_file`` are drawn on the plate inside the
#: **out-of-order scheduling and retirement** block, not inside the FPU and the integer cluster.
#: Read directly off ``images/floorplans/semianalysis__Intel_Meteor_Lake_005.png``: the two
#: "FP Regs." boxes and the "INT Reg." box are blue-outlined rectangles sitting on the cyan
#: OoO/retirement field, with the olive FPU and the crimson INT Exec blocks BELOW them.
#: It does not change the non-overlapping set, and it does change where that area sits on the die,
#: which is the part a thermal model cares about.
NESTED_BLOCKS = {
    'fma_eus_port_0_1': 'fpu_incl_fma_eus',
    'l2_sram_block_256kb': 'l2_cache',
    'fpu_register_file': 'ooo_sched_and_retire',
    'int_register_file': 'ooo_sched_and_retire',
}

#: Rows that state a whole rather than a part. Excluded from any sum of parts, and used as the
#: closure target when one is present.
TOTAL_BLOCKS = (
    'core_total', 'die_total', 'die_no_scribe', 'die_with_scribe', 'chip_area_no_scribe',
    'platform_total', 'tile_total', 'gpu_complex_total', 'package_power',
    'system_level_cache_total', 'top_dies_edge_to_edge',
)


def _pack_path(*parts):
    return os.path.join(PACK_DIR, *parts)


def pack_available():
    """Whether the pack is present. It is 314 MB of mostly images and may not be checked out."""
    return os.path.isfile(_pack_path('block_areas.csv'))


def _require_pack():
    if not pack_available():
        raise IOError('the floorplan pack is not at {}. It is 314 MB and lives under '
                      'docs/chip_design_lit/; without it nothing in this module can run.'
                      .format(PACK_DIR))


def _float_or_none(s):
    s = (s or '').strip()
    return float(s) if s else None


def load_block_areas():
    """Every row of ``block_areas.csv``, areas and powers parsed, ``None`` where blank.

    Returns a list of dicts. No filtering and no summing -- both of those are where the mistakes
    live, so they are separate functions with guards on them.
    """
    _require_pack()
    rows = []
    with open(_pack_path('block_areas.csv')) as f:
        for r in csv.DictReader(f):
            r = dict(r)
            r['area_mm2'] = _float_or_none(r.get('area_mm2'))
            r['power_w'] = _float_or_none(r.get('power_w'))
            rows.append(r)
    return rows


def chips():
    """``(vendor, chip, node)`` for every chip in the pack, in file order."""
    seen, out = set(), []
    for r in load_block_areas():
        key = (r['vendor'], r['chip'], r['node'])
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def chip_rows(chip, rows=None):
    """Every row for one ``chip``, unfiltered. Raises if the name matches nothing."""
    rows = load_block_areas() if rows is None else rows
    out = [r for r in rows if r['chip'] == chip]
    if not out:
        raise KeyError('no rows for chip {!r}; see pack_areas.chips()'.format(chip))
    return out


def non_overlapping_blocks(chip, rows=None):
    """Trap 1's guard: the block rows for ``chip`` that do **not** overlap each other.

    Drops the ``TOTAL_BLOCKS`` wholes and the ``NESTED_BLOCKS`` children, and drops rows with no
    area. What is left is the set that may legitimately be summed, and for Golden Cove it is the
    six the pack README nominates.

    Returns ``{block: {'area_mm2', 'note', 'source_image'}}``.
    """
    out = {}
    for r in chip_rows(chip, rows):
        if r['area_mm2'] is None:
            continue
        if r['block'] in TOTAL_BLOCKS or r['block'] in NESTED_BLOCKS:
            continue
        if r['block'] in out:
            # Two rows with the same block name for one chip (SPR has a duplicated 'tile_total').
            # Summing them would double count; refusing is the only safe default.
            raise ValueError('chip {!r} has two rows named {!r}; this loader will not guess which '
                             'to use'.format(chip, r['block']))
        out[r['block']] = {'area_mm2': r['area_mm2'], 'note': r['note'],
                           'source_image': r['source_image'], 'node': r['node'],
                           'vendor': r['vendor']}
    return out


def nested_children(chip, rows=None):
    """The rows that were excluded as nested, with the parent each sits inside.

    Kept as API rather than dropped on the floor, because the children are the finest structure
    the pack has for a core -- the FMA EUs and the register files are exactly the blocks a
    hotspot study wants -- and because reporting what was excluded is what makes the closure
    number checkable.
    """
    out = {}
    for r in chip_rows(chip, rows):
        if r['block'] in NESTED_BLOCKS and r['area_mm2'] is not None:
            out[r['block']] = {'area_mm2': r['area_mm2'], 'parent': NESTED_BLOCKS[r['block']],
                               'source_image': r['source_image']}
    return out


def published_total(chip, block=None, rows=None):
    """The published whole for ``chip`` -- ``core_total``, ``die_total``, whichever it carries."""
    candidates = [r for r in chip_rows(chip, rows)
                  if r['area_mm2'] is not None
                  and (r['block'] == block if block else r['block'] in TOTAL_BLOCKS)]
    if not candidates:
        raise KeyError('chip {!r} publishes no total area row'.format(chip))
    if len(candidates) > 1:
        raise ValueError('chip {!r} publishes {} total rows ({}); name one with block='
                         .format(chip, len(candidates), ', '.join(c['block'] for c in candidates)))
    return candidates[0]['area_mm2']


def area_closure(chip, block=None, rows=None):
    """Do the non-overlapping sub-blocks reconcile to the published total?

    The pack README calls this "a meaningful confidence signal", and it is: the sub-block areas
    and the published total were transcribed independently from the same plate, so agreement is
    evidence that neither was mis-read. It also states the threshold -- a residual much above a
    few percent means a transcription error, not a real uncore.

    Returned alongside is ``naive_sum_error`` -- what summing *every* row would have given -- so
    the trap is visible in the output rather than only in a docstring.
    """
    rows = load_block_areas() if rows is None else rows
    blocks = non_overlapping_blocks(chip, rows)
    nested = nested_children(chip, rows)
    total = published_total(chip, block=block, rows=rows)
    s = sum(b['area_mm2'] for b in blocks.values())
    naive = s + sum(n['area_mm2'] for n in nested.values())
    return {'chip': chip, 'published_total_mm2': total, 'sum_of_blocks_mm2': s,
            'n_blocks': len(blocks), 'residual_mm2': total - s,
            'residual_frac': (total - s) / total,
            'closure_err_frac': s / total - 1.0,
            'n_nested_excluded': len(nested),
            'naive_sum_mm2': naive, 'naive_sum_error_frac': naive / total - 1.0}


def assert_area_closure(chip, tol=0.03, block=None, rows=None):
    """Raise unless ``chip`` closes within ``tol``. The check the pack README asks callers to run.

    ``tol`` defaults to 3%: the pack says "a residual much above a few percent means a
    transcription error", and the two decomposed cores land at 1.35% and 0.04%.
    """
    c = area_closure(chip, block=block, rows=rows)
    if abs(c['closure_err_frac']) > tol:
        raise ValueError('{} does not close: {} blocks sum to {:.3f} mm^2 against a published '
                         '{:.3f} ({:+.2%}, tolerance {:.0%}). Per the pack README that is a '
                         'transcription error, not a real uncore.'
                         .format(chip, c['n_blocks'], c['sum_of_blocks_mm2'],
                                 c['published_total_mm2'], c['closure_err_frac'], tol))
    return c


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
def load_manifest():
    """Every row of ``manifest.csv`` (310 images), areas parsed."""
    _require_pack()
    rows = []
    with open(_pack_path('manifest.csv')) as f:
        for r in csv.DictReader(f):
            r = dict(r)
            r['die_area_mm2'] = _float_or_none(r.get('die_area_mm2'))
            rows.append(r)
    return rows


def manifest_rows(category=None, isa=None, verified=None, rows=None):
    """Filter the manifest. Trap 2's guard: an unknown ``category`` raises rather than returning [].

    ``category`` must be one of ``CATEGORIES``; passing a folder name like ``'floorplans'`` is the
    documented mistake and it is refused with the right value in the message.
    """
    rows = load_manifest() if rows is None else rows
    if category is not None and category not in CATEGORIES:
        folder_match = [k for k, v in CATEGORIES.items() if v.endswith('/' + str(category))]
        hint = (' -- did you mean {!r}? That is the FOLDER name; manifest.csv:category uses the '
                'other one.'.format(folder_match[0]) if folder_match else '')
        raise ValueError('unknown manifest category {!r}. Valid: {}{}'
                         .format(category, ', '.join(sorted(CATEGORIES)), hint))
    out = rows
    if category is not None:
        out = [r for r in out if r['category'] == category]
    if isa is not None:
        out = [r for r in out if r['isa'] == isa]
    if verified is not None:
        out = [r for r in out if r['verified'] == verified]
    return out


def annotated_floorplans(isa=None):
    """Annotated, placed layouts -- the images placement may legitimately be read from.

    Deliberately excludes ``block_diagram``: those give hierarchy and connectivity and their
    geometry means nothing, and feeding one to anything that infers placement produces a
    confident, wrong floorplan.
    """
    return manifest_rows(category='die_floorplan_annotated', isa=isa)


# ---------------------------------------------------------------------------
# power: the nine rows that carry it, and the priors they support
# ---------------------------------------------------------------------------
def rows_with_power(rows=None):
    """The 9 of 165 rows carrying a published power alongside an area or a scope."""
    rows = load_block_areas() if rows is None else rows
    return [r for r in rows if r['power_w'] is not None]


def power_density_priors(rows=None):
    """Measured W/mm^2 for every row publishing area **and** power on the same row.

    This is the pack's answer to the gap flagged all through the 27-28 August work: every ISA
    result so far redistributed the *Skylake* power trace by area, so an "ISA comparison" was a
    geometry comparison wearing an architecture's name. These are a real per-part prior.

    Note the shape of the answer, because it is the axis the thermal work turns on: the
    **wide-vector V-class runs at roughly half the power density of the compact N-class**
    (V1 0.476 and V2 0.560 against N1 0.870-1.286 and N2 0.909-1.538 W/mm^2). A wide machine
    spends area to go fast at low clock; a compact one spends clock. That is an activity
    difference, and it is invisible to any amount of area re-weighting.

    Returns a list of dicts sorted by W/mm^2, each carrying its own ``source_image``.
    """
    out = []
    for r in rows_with_power(rows):
        if r['area_mm2'] is None or r['area_mm2'] <= 0:
            continue
        out.append({'vendor': r['vendor'], 'chip': r['chip'], 'node': r['node'],
                    'block': r['block'], 'area_mm2': r['area_mm2'], 'power_w': r['power_w'],
                    'w_per_mm2': r['power_w'] / r['area_mm2'],
                    'note': r['note'], 'source_image': r['source_image']})
    return sorted(out, key=lambda d: d['w_per_mm2'])


# ---------------------------------------------------------------------------
# V/F anchors
# ---------------------------------------------------------------------------
def load_vf_anchors():
    """``vf_anchors.csv`` -- 12 operating points read off the dataset."""
    _require_pack()
    rows = []
    with open(_pack_path('vf_anchors.csv')) as f:
        for r in csv.DictReader(f):
            r = dict(r)
            for k in ('voltage_v', 'freq_ghz', 'power_w'):
                r[k] = _float_or_none(r.get(k))
            rows.append(r)
    return rows


def vf_anchors_with_voltage(rows=None):
    """Trap 3's guard: the anchors that carry a real voltage. There are two; zero means a bug.

    Both are Arm Neoverse from Arm's own PPA slide -- V1 at 2.8 GHz / 0.75 V on TSMC N7 and V2 at
    2.8 GHz / 0.75 V on TSMC N5. Every other anchor is frequency-only or power-only, and
    everything in ``vf_node_params.csv`` is a foundry-nominal reference value rather than a
    measurement of these parts.
    """
    rows = load_vf_anchors() if rows is None else rows
    out = [r for r in rows if r.get('voltage_v')]
    if not out:
        raise ValueError('no vf anchors carry a voltage. The column is voltage_v; if this fired '
                         'after an edit, something is reading the wrong column name -- the pack '
                         'has two anchors at 0.75 V.')
    return out
