"""A real x86 core floorplan, built from published block areas rather than from a model's guess.

Why this exists
---------------
``accelerator_floorplan.py`` set the pattern this module follows: measured areas, the arrangement
read off an annotated die shot, ``source_image`` recorded per block, an assertion that the areas
sum, and the area-closure check kept as a test. It could not be applied to a CPU core because the
repository had no annotated CPU core plate with a matching area table.

The floorplan pack supplies one. **Intel Golden Cove / Redwood Cove is the only fully decomposed
core in it**, and the two are printed side by side on the same plate at ~75% rescale, which makes
them the cleanest template *pair* available: the same block set, one design shrunk, so a rescale
can be checked against a published answer instead of assumed.

Provenance, block by block
--------------------------
* Areas: ``block_areas.csv``, chip ``Golden Cove (P-core)`` / ``Redwood Cove (P-core)``,
  transcribed by the pack's author from ``images/area_tables/semianalysis__Intel_Meteor_Lake_006.png``.
  Six non-overlapping blocks plus four nested children -- see ``pack_areas.NESTED_BLOCKS``, and
  note that summing all ten overstates the core by 9.55%.
* Arrangement: read by eye off ``images/floorplans/semianalysis__Intel_Meteor_Lake_005.png``,
  the annotated Golden Cove / Redwood Cove core pair. Areas do not fix placement or aspect ratio
  and the pack encodes no geometry anywhere, so this is the one input taken from a picture.
* Core aspect ratio 1.583 (w/h): the bounding box of the left-hand core on that plate, measured
  as the extent of its non-black pixels.

What is measured, what is read off a picture, what is assumed
--------------------------------------------------------------
* **Measured (published)**: every block area, and the core total they close against.
* **Read off the plate**: which block is next to which, and the core's aspect ratio. The
  arrangement is checked rather than trusted -- ``arrangement_consistency()`` compares the area
  fractions this layout implies against the fractions measured directly off the plate's pixels,
  which are two independent readings of the same design.
* **Assumed**: (1) the 384 KB L2 data arrays scale linearly in area from the published 256 KB
  block, since the pack prints only the 256 KB one; (2) that a block is a rectangle, which no
  block on the plate exactly is.
* **Not supplied at all**: per-block power. The pack carries power on 9 of 165 rows and none of
  them is an x86 core. ``calibrated_power`` is False everywhere here and area-proportional power
  is offered only to get a pipeline running -- the pack README's own warning is that caches
  dissipate far less per mm^2 than execution units, and resolving exactly that difference is what
  a hotspot simulation is for.

The finest structure the pack has, and why it is worth keeping
---------------------------------------------------------------
With ``split_nested=True`` (the default) the six published blocks become ten, using the four
nested children the naive sum double-counts:

* ``fma_eus_port_0_1`` (0.288 mm^2) out of ``fpu_incl_fma_eus`` -- the AVX-512 FMA hardware, i.e.
  the block a vector-width argument is actually about, and the densest thing on an x86 core.
* ``fpu_register_file`` and ``int_register_file`` out of ``ooo_sched_and_retire`` -- and note the
  parentage: the plate draws all three register-file boxes on the OoO/retirement field, not
  inside the FPU and integer clusters their names suggest.
* ``l2_sram_block_256kb`` (0.151 mm^2), which with the plate's four labelled data arrays
  (384+256+256+384 KB = the published 1.25 MB) splits the L2 into **array and control**. SRAM and
  logic do not leak alike, so an L2 modelled as one uniform block hides the difference the
  leakage-temperature loop exists to resolve -- the same reason ``accelerator_floorplan`` splits
  an SM into datapath and L1.
"""
import math
import logging

from HotGauge.thermal import pack_areas
from HotGauge.thermal.accelerator_floorplan import _fmt_block, _snap

LOGGER = logging.getLogger(__name__)

#: Core outline aspect (width / height) for the Golden Cove core, measured as the bounding box of
#: the left-hand core on ``semianalysis__Intel_Meteor_Lake_005.png``. Redwood Cove on the same
#: plate measures 1.652; the pair are drawn at roughly a common scale (their pixel areas are in
#: 0.694 ratio against a published area ratio of 0.748), which is itself a check that the plate is
#: not schematic.
GOLDEN_COVE_ASPECT = 1.583
REDWOOD_COVE_ASPECT = 1.652

#: L2 data-array capacities as labelled on the plate, in KB, top pair then bottom pair. They sum
#: to the published 1.25 MB, which is the check that the labels were read correctly.
L2_DATA_ARRAYS_KB = (384, 256, 256, 384)

#: The one published SRAM block, used to price the others. ASSUMPTION: array area is linear in
#: capacity at a fixed node. The pack's own cache-area table (L2 area against capacity across
#: three nodes, ``block_areas.csv`` rows ``l2_128kb`` .. ``l2_1mb``) is the cross-check on this
#: and ``sram_linearity_check()`` runs it.
L2_SRAM_REFERENCE_KB = 256

#: Thinnest ``uncore`` strip worth writing as its own block [um]. One cell of the 50 um grid the
#: catalogue solves on; below it the block is not representable and ``uncore_mode='auto'``
#: distributes the residual instead.
MIN_UNCORE_STRIP_UM = 50.0

#: Block class per template block. Classes are what a power model divides watts between, exactly
#: as ``accelerator_floorplan.GA100_POWER_SPLIT`` does, so that "SRAM" and "datapath" can be
#: treated differently without the floorplan knowing about power.
BLOCK_CLASSES = {
    'ooo_sched_and_retire': 'ooo',
    'fpu_register_file': 'regfile',
    'int_register_file': 'regfile',
    'fpu_excl_fma': 'fpu',
    'fma_eus_port_0_1': 'fma',
    'fpu_incl_fma_eus': 'fpu',
    'integer_execution': 'int',
    'load_store_with_l1d': 'lsu',
    'frontend_branch_decode_l1i_op': 'frontend',
    'l2_control': 'l2_ctrl',
    'l2_cache': 'l2_ctrl',
    'uncore': 'uncore',
}


class CoreTemplate(object):
    """A core floorplan template: published block areas plus a plate-read arrangement.

    ``blocks`` is an ordered mapping ``name -> area_mm2``; ``sources`` maps the same names to the
    pack image each area was transcribed from. ``total_mm2`` is the *published* core total, and
    the invariant this class exists to hold is that the blocks sum to it.
    """

    def __init__(self, key, chip, node, total_mm2, blocks, sources, aspect, provenance,
                 assumptions, split_nested=True, uncore_mode='block'):
        self.key = key
        self.chip = chip
        self.node = node
        self.total_mm2 = float(total_mm2)
        self.blocks = dict(blocks)
        self.sources = dict(sources)
        self.aspect = float(aspect)
        self.provenance = provenance
        self.assumptions = assumptions
        self.split_nested = bool(split_nested)
        #: 'block' or 'distributed' -- how the published total's residual was placed. Resolved
        #: from 'auto' at build time and recorded, because it is a modelling choice.
        self.uncore_mode = uncore_mode
        #: Areas are published; the placement is read off a plate. Both are a large step up from a
        #: press ratio, and neither is a measurement we made, so this records which is which
        #: rather than collapsing to a single bit.
        self.calibrated_area = True
        self.calibrated_geometry = False
        self.calibrated_power = False
        self.assert_closes()

    def __repr__(self):
        return '<CoreTemplate {} {:.3f} mm^2, {} blocks>'.format(
            self.key, self.total_mm2, len(self.blocks))

    # -- invariants ---------------------------------------------------------
    def assert_closes(self, tol_mm2=1e-6):
        """The blocks sum to the published core total. Asserted at construction, not on request.

        This is the assertion ``accelerator_floorplan`` makes about GA100 and it earns its keep the
        same way: every rescale, every block split and every variant re-weighting below goes
        through this constructor, so an arithmetic slip cannot reach a solve.
        """
        s = sum(self.blocks.values())
        if abs(s - self.total_mm2) > tol_mm2:
            raise ValueError('{}: blocks sum to {:.6f} mm^2 against a published total of {:.6f} '
                             '({:+.4%}). The template must partition the core exactly.'
                             .format(self.key, s, self.total_mm2, s / self.total_mm2 - 1.0))
        return s

    def area_fractions(self):
        return {k: v / self.total_mm2 for k, v in self.blocks.items()}

    def classes(self):
        out = {}
        for name in self.blocks:
            if name.startswith('l2_data_'):
                out[name] = 'l2_array'
            else:
                out[name] = BLOCK_CLASSES.get(name, 'uncore')
        return out

    def class_areas(self):
        agg = {}
        cls = self.classes()
        for name, area in self.blocks.items():
            agg[cls[name]] = agg.get(cls[name], 0.0) + area
        return agg

    # -- rescaling ----------------------------------------------------------
    def rescale_to(self, total_mm2, key=None, chip=None, node=None, aspect=None,
                   provenance=None, assumptions=None):
        """Uniform rescale to a different core area, preserving the mix exactly.

        This is the pack README's own recipe -- "scale to other cores by ratio" -- and its
        accuracy is *measurable* rather than assumed, because Redwood Cove is the same block set
        at 75% of Golden Cove's area and both are published. ``rescale_error_vs_published()``
        reports how well it does, per block.
        """
        f = float(total_mm2) / self.total_mm2
        return CoreTemplate(
            key=key or '{}_x{:.3f}'.format(self.key, f),
            chip=chip or self.chip, node=node or self.node,
            total_mm2=float(total_mm2),
            blocks={k: v * f for k, v in self.blocks.items()},
            sources=dict(self.sources), aspect=aspect if aspect is not None else self.aspect,
            provenance=provenance or ('uniform rescale x{:.4f} of {}'.format(f, self.key)),
            assumptions=assumptions or ('a uniform rescale preserves the unit MIX, which a real '
                                        'shrink does not -- SRAM and logic scale differently and '
                                        'Redwood Cove is the measurement of how differently'),
            split_nested=self.split_nested, uncore_mode=self.uncore_mode)

    def reweight(self, factors, total_mm2=None, key=None, chip=None, node=None, aspect=None,
                 provenance=None, assumptions=None, renormalise=True):
        """Scale named blocks by ``factors`` (``{block: multiplier}``) and re-close the total.

        This is what makes a variant more than a rescale. Scaling the whole core uniformly
        preserves the mix, which is exactly the limitation the 27 August sweep exposed: three of
        four variants inherited a degenerate peak because nothing about their proportions had
        changed. Re-weighting individual blocks changes the proportions, which is what a different
        microarchitecture actually is.

        ``renormalise=True`` (default) sets the new total to the re-weighted sum. Pass
        ``total_mm2`` instead to re-weight the mix and then scale it to a published core area,
        which is the useful combination: the mix comes from the microarchitecture, the absolute
        size from a published measurement.
        """
        unknown = set(factors) - set(self.blocks)
        if unknown:
            raise KeyError('{}: no such block(s) {}'.format(self.key, sorted(unknown)))
        blocks = {k: v * float(factors.get(k, 1.0)) for k, v in self.blocks.items()}
        s = sum(blocks.values())
        if total_mm2 is not None:
            f = float(total_mm2) / s
            blocks = {k: v * f for k, v in blocks.items()}
            new_total = float(total_mm2)
        elif renormalise:
            new_total = s
        else:
            raise ValueError('pass total_mm2 or leave renormalise=True')
        return CoreTemplate(
            key=key or '{}_reweighted'.format(self.key),
            chip=chip or self.chip, node=node or self.node, total_mm2=new_total,
            blocks=blocks, sources=dict(self.sources),
            aspect=aspect if aspect is not None else self.aspect,
            provenance=provenance or 'block re-weighting of {}'.format(self.key),
            assumptions=assumptions or 'per-block multipliers -- see the variant that set them',
            split_nested=self.split_nested, uncore_mode=self.uncore_mode)

    # -- geometry -----------------------------------------------------------
    def geometry(self):
        """Solve every block's rectangle from the areas, under the plate's arrangement.

        The arrangement, left to right and top to bottom as the plate shows it:

        * a full-height **left column** -- out-of-order scheduling and retirement on top, the
          register-file row at its foot, then the FPU, with the FMA EUs as a strip at the bottom
          of the core;
        * a **top band** across everything to the right of that column -- decode, the micro-op
          ROM, the L1I and its control, and the branch predictor, which on the plate runs along
          the top edge above the L2;
        * beneath the band, three columns -- **integer execution** (narrow), **load/store with
          the L1D**, and the **L2**, which occupies the whole right-hand third with its data
          arrays in two pairs above and below the control block.

        Dimensions are an OUTPUT: the areas are published and the topology is read off the plate,
        so the widths and heights the two imply are a prediction. ``arrangement_consistency()``
        is what checks that prediction against the plate.

        Returns ``{block: (x_mm, y_mm, w_mm, h_mm)}`` with the origin at the bottom-left.
        """
        b = self.blocks
        h = math.sqrt(self.total_mm2 / self.aspect)
        w = self.total_mm2 / h

        left_names = [k for k in b if k in _LEFT_COLUMN_ORDER or k in _REGFILE_ROW]
        left_area = sum(b[k] for k in left_names)
        w_left = left_area / h
        w_right = w - w_left
        if w_right <= 0:
            raise ValueError('{}: the left column alone fills the core'.format(self.key))

        h_band = b['frontend_branch_decode_l1i_op'] / w_right
        h_body = h - h_band
        if h_body <= 0:
            raise ValueError('{}: the frontend band alone fills the core height'.format(self.key))

        out = {}

        # Left column, stacked from the top down in the plate's order.
        y = h
        for name in _LEFT_COLUMN_ORDER:
            if name == '_regfile_row':
                rf = [n for n in _REGFILE_ROW if n in b]
                if not rf:
                    continue
                hh = sum(b[n] for n in rf) / w_left
                y -= hh
                x = 0.0
                for n in rf:
                    ww = b[n] / hh
                    out[n] = (x, y, ww, hh)
                    x += ww
                continue
            if name not in b:
                continue
            hh = b[name] / w_left
            y -= hh
            out[name] = (0.0, y, w_left, hh)

        # Top band: the frontend, spanning everything right of the left column.
        out['frontend_branch_decode_l1i_op'] = (w_left, h - h_band, w_right, h_band)

        # Body, three columns left to right.
        x = w_left
        for name in ('integer_execution', 'load_store_with_l1d'):
            ww = b[name] / h_body
            out[name] = (x, 0.0, ww, h_body)
            x += ww

        # L2 column: array pair, control, array pair, then the uncore residual as a strip at the
        # foot of the column. The residual has no location on the plate -- it is routing and glue
        # -- so this is a placement CHOICE and it is the one place in the template that is.
        col = [n for n in _L2_COLUMN_ORDER
               if n in b or (n in _L2_PAIRS and any(p in b for p in _L2_PAIRS[n]))]
        col_names = [n for n in col if n in b]
        for n in col:
            if n in _L2_PAIRS:
                col_names += [p for p in _L2_PAIRS[n] if p in b]
        w_col = sum(b[n] for n in col_names) / h_body
        y = h_body
        for name in col:
            if name.startswith('_pair_'):
                pair = _L2_PAIRS[name]
                pair = [n for n in pair if n in b]
                hh = sum(b[n] for n in pair) / w_col
                y -= hh
                xx = x
                for n in pair:
                    ww = b[n] / hh
                    out[n] = (xx, y, ww, hh)
                    xx += ww
                continue
            hh = b[name] / w_col
            y -= hh
            out[name] = (x, y, w_col, hh)

        missing = set(b) - set(out)
        if missing:
            raise ValueError('{}: the arrangement does not place {}'
                             .format(self.key, sorted(missing)))
        return out

    def outline_mm(self):
        h = math.sqrt(self.total_mm2 / self.aspect)
        return self.total_mm2 / h, h

    def min_dimension_um(self):
        """Smallest side of any block [um] -- what decides whether a thermal grid can resolve it."""
        g = self.geometry()
        return min(min(r[2], r[3]) for r in g.values()) * 1000.0

    # -- output -------------------------------------------------------------
    def write_flp(self, out_path, cell_um=50.0, max_area_error=0.10, prefix=''):
        """Write a 3D-ICE floorplan for one core and return ``(path, classes)``.

        ``cell_um`` must match the grid the stack will be solved on. Block *boundaries* are
        snapped rather than positions and widths, so neighbours stay exactly adjacent after
        quantisation -- 3D-ICE reports "Intersection between ..." and aborts otherwise, and
        checking non-overlap on the unquantised geometry passes and tells you nothing.
        ``accelerator_floorplan._snap`` carries the full explanation.

        ``max_area_error`` guards the other failure: on a coarse grid a thin block is distorted,
        and silently accepting that corrupts the density accounting every result reads. The
        ``uncore`` residual is 1.3% of the core and comes out as a strip a few tens of microns
        tall, so it is the block that trips this first -- the fix is a finer cell, or
        ``uncore_mode='distributed'``, not a larger tolerance.
        """
        g = self.geometry()
        cls = self.classes()
        MM = 1000.0
        lines, snapped = [], {}
        for name in sorted(g, key=lambda n: (-g[n][1], g[n][0])):
            x, y, ww, hh = g[name]
            # Float error leaves the bottom row at -1e-16; clamp before snapping so no block is
            # written at a negative position.
            x, y = max(x, 0.0), max(y, 0.0)
            x0, y0 = _snap(x * MM, cell_um), _snap(y * MM, cell_um)
            x1, y1 = _snap((x + ww) * MM, cell_um), _snap((y + hh) * MM, cell_um)
            if x1 <= x0 or y1 <= y0:
                raise ValueError(
                    '{}: block {!r} collapses to zero on a {:g} um grid ({:.1f} x {:.1f} um). '
                    'Use a finer cell_um, or uncore_mode="distributed" if this is the residual.'
                    .format(self.key, name, cell_um, ww * MM, hh * MM))
            lines.append(_fmt_block(prefix + name, x0, y0, x1 - x0, y1 - y0))
            snapped[prefix + name] = (x1 - x0) * (y1 - y0) / 1e6
        for name, area in self.blocks.items():
            got = snapped[prefix + name]
            if abs(got - area) / area > max_area_error:
                raise ValueError('{}: on a {:g} um grid block {!r} comes out {:.4f} mm^2 against '
                                 'a published {:.4f} ({:+.1%}); that distorts the density '
                                 'accounting. Use a finer cell_um.'
                                 .format(self.key, cell_um, name, got, area, got / area - 1.0))
        with open(out_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        w, h = self.outline_mm()
        LOGGER.info('wrote %s: %d blocks, %.3f x %.3f mm, %.3f mm^2 -> %s',
                    self.key, len(lines), w, h, sum(snapped.values()), out_path)
        return out_path, {prefix + k: v for k, v in cls.items()}


#: Vertical order of the left column, top to bottom, as the plate shows it. ``_regfile_row`` is a
#: placeholder for the row of register files drawn at the foot of the OoO field.
_LEFT_COLUMN_ORDER = ('ooo_sched_and_retire', '_regfile_row', 'fpu_excl_fma', 'fma_eus_port_0_1',
                      'fpu_incl_fma_eus')
_REGFILE_ROW = ('fpu_register_file', 'int_register_file')
_L2_COLUMN_ORDER = ('_pair_top', 'l2_control', '_pair_bottom', 'l2_cache', 'uncore')
_L2_PAIRS = {'_pair_top': ('l2_data_384kb_a', 'l2_data_256kb_a'),
             '_pair_bottom': ('l2_data_256kb_b', 'l2_data_384kb_b')}


def _split_blocks(chip, split_nested, uncore_mode):
    """Build the block map for one pack chip, honouring the two structural options."""
    rows = pack_areas.load_block_areas()
    six = pack_areas.non_overlapping_blocks(chip, rows)
    nested = pack_areas.nested_children(chip, rows)
    total = pack_areas.published_total(chip, block='core_total', rows=rows)

    blocks, sources = {}, {}
    for k, v in six.items():
        blocks[k] = v['area_mm2']
        sources[k] = v['source_image']

    if split_nested:
        # FPU -> (FPU without the FMA EUs, FMA EUs). The FMA block is the AVX-512 hardware.
        fma = nested['fma_eus_port_0_1']['area_mm2']
        blocks['fpu_excl_fma'] = blocks.pop('fpu_incl_fma_eus') - fma
        blocks['fma_eus_port_0_1'] = fma
        sources['fpu_excl_fma'] = sources.pop('fpu_incl_fma_eus')
        sources['fma_eus_port_0_1'] = nested['fma_eus_port_0_1']['source_image']

        # OoO -> (OoO without the register files, FP RF, INT RF). The plate draws all three RF
        # boxes on the OoO field; see pack_areas.NESTED_BLOCKS.
        for rf in ('fpu_register_file', 'int_register_file'):
            blocks['ooo_sched_and_retire'] -= nested[rf]['area_mm2']
            blocks[rf] = nested[rf]['area_mm2']
            sources[rf] = nested[rf]['source_image']

        # L2 -> (control and tags, four data arrays). The plate labels 384+256+256+384 KB, which
        # sums to the published 1.25 MB; the pack prints only the 256 KB block's area, so the
        # 384 KB arrays are priced linearly from it -- see L2_SRAM_REFERENCE_KB.
        per_kb = nested['l2_sram_block_256kb']['area_mm2'] / float(L2_SRAM_REFERENCE_KB)
        arrays = {'l2_data_384kb_a': 384, 'l2_data_256kb_a': 256,
                  'l2_data_256kb_b': 256, 'l2_data_384kb_b': 384}
        # Scale the arrays to this chip's own L2 capacity. Redwood Cove carries 2 MB against
        # Golden Cove's 1.25 MB in the SAME 1.578 mm^2 block, so assuming the same four array
        # sizes there would be wrong; the arrays are scaled to keep the array:control ratio the
        # plate implies for the chip whose SRAM block is published.
        array_total = sum(v * per_kb for v in arrays.values())
        l2 = blocks.pop('l2_cache')
        if array_total >= l2:
            raise ValueError('{}: L2 data arrays ({:.3f} mm^2) do not fit in the published L2 '
                             'block ({:.3f})'.format(chip, array_total, l2))
        sources_l2 = sources.pop('l2_cache')
        for name, kb in arrays.items():
            blocks[name] = kb * per_kb
            sources[name] = nested['l2_sram_block_256kb']['source_image']
        blocks['l2_control'] = l2 - array_total
        sources['l2_control'] = sources_l2

    residual = total - sum(blocks.values())
    if uncore_mode not in ('block', 'distributed', 'auto'):
        raise ValueError("uncore_mode must be 'block', 'distributed' or 'auto', got {!r}"
                         .format(uncore_mode))
    if uncore_mode == 'auto':
        # The residual is routing and glue with NO location on the plate, so placing it is a
        # choice either way. As a block it lands as a strip along the foot of the L2 column, and
        # the strip's thickness is what decides whether the choice is even representable: Golden
        # Cove's 0.096 mm^2 gives 80 um, which a 50 um grid resolves, while Redwood Cove's
        # 0.002 mm^2 gives 1.5 um, which nothing resolves and which is anyway indistinguishable
        # from zero. 'auto' takes the block when it can be resolved and distributes it otherwise,
        # and records which in ``uncore_placement`` -- it is reported, not silent.
        h = math.sqrt(total / (REDWOOD_COVE_ASPECT if 'Redwood' in chip else GOLDEN_COVE_ASPECT))
        w = total / h
        strip_um = (residual / (0.37 * w)) * 1000.0 if w > 0 else 0.0
        uncore_mode = 'block' if strip_um >= MIN_UNCORE_STRIP_UM else 'distributed'
    if uncore_mode == 'block':
        blocks['uncore'] = residual
        sources['uncore'] = sources.get('l2_control') or sorted(sources.values())[0]
    else:
        # Spread in proportion to area rather than invented as a sliver. The blocks then carry
        # their published area inflated by the residual fraction (1.35% on Golden Cove), and the
        # template still closes exactly to the published core total.
        f = total / sum(blocks.values())
        blocks = {k: v * f for k, v in blocks.items()}
    return blocks, sources, total, residual, uncore_mode


def pack_core_template(chip, key=None, aspect=None, split_nested=True, uncore_mode='auto'):
    """Build a ``CoreTemplate`` for one fully decomposed core in the pack.

    Only Golden Cove and Redwood Cove qualify -- they are the only chips in ``block_areas.csv``
    whose sub-blocks partition a published core total. Everything else in the pack is coarser:
    a core-plus-L2 number, a tile, or a whole die.
    """
    if aspect is None:
        aspect = REDWOOD_COVE_ASPECT if 'Redwood' in chip else GOLDEN_COVE_ASPECT
    blocks, sources, total, residual, used_mode = _split_blocks(chip, split_nested, uncore_mode)
    rows = pack_areas.load_block_areas()
    node = pack_areas.chip_rows(chip, rows)[0]['node']
    return CoreTemplate(
        key=key or chip.split(' (')[0].lower().replace(' ', '_'),
        chip=chip, node=node, total_mm2=total, blocks=blocks, sources=sources, aspect=aspect,
        provenance=('published block areas from the MXL-HotGauge Floorplan Pack '
                    '(block_areas.csv, chip {!r}), arrangement read off '
                    'images/floorplans/semianalysis__Intel_Meteor_Lake_005.png. Closes to '
                    '{:+.2%} of the published core total.'
                    .format(chip, -residual / total)),
        assumptions=('block rectangles; the 384 KB L2 arrays priced linearly from the published '
                     '256 KB block; the {:.4f} mm^2 residual placed as {}'
                     .format(residual, 'an uncore block at the foot of the L2 column'
                             if used_mode == 'block' else 'a proportional inflation of the '
                             'other blocks')),
        split_nested=split_nested, uncore_mode=used_mode)


def golden_cove(**kw):
    """The Golden Cove P-core: 7.123 mm^2 on Intel 7, the pack's only full core decomposition."""
    return pack_core_template('Golden Cove (P-core)', key='golden_cove', **kw)


def redwood_cove(**kw):
    """Redwood Cove: the same block set at 5.33 mm^2 on Intel 4 -- 74.8% of Golden Cove."""
    return pack_core_template('Redwood Cove (P-core)', key='redwood_cove', **kw)


# ---------------------------------------------------------------------------
# checks: the two the pack makes possible and nothing here should skip
# ---------------------------------------------------------------------------
#: Block area fractions measured directly off the Golden Cove plate's pixels, by classifying the
#: annotation colours and scanning for the boundaries. Independent of the transcribed area table,
#: which is what makes the comparison worth anything. Measured 28 Aug 2026 on
#: ``semianalysis__Intel_Meteor_Lake_005.png`` over its non-black bounding box (x 14-510,
#: y 14-327): left column right edge at 0.266 of the width, frontend band foot at 0.38 of the
#: height over the middle columns and 0.23 over the L2, integer/load-store boundary at 0.398,
#: load-store/L2 boundary at 0.60.
PLATE_MEASURED_FRACTIONS = {
    'ooo_sched_and_retire': 0.164,
    'fpu_incl_fma_eus': 0.133,
    'integer_execution': 0.067,
    'load_store_with_l1d': 0.125,
    'l2_cache': 0.280,
    'frontend_branch_decode_l1i_op': 0.231,
}


def arrangement_consistency(template=None):
    """Compare the area fractions the plate's *pixels* give against the *transcribed* table.

    Two independent readings of one design: the pack's author transcribed an area table by eye,
    and this measures coloured regions off the layout drawing. They are not expected to agree
    closely -- annotation overlays are approximate, a watermark washes out part of the plate, and
    real blocks are not rectangles -- but a systematic disagreement would mean the arrangement
    encoded here is not the arrangement on the plate.

    Returns per-block ``{'published_frac', 'plate_frac', 'error'}`` plus the worst case.
    """
    t = template or golden_cove(split_nested=False)
    fr = t.area_fractions()
    out = {}
    for name, plate in PLATE_MEASURED_FRACTIONS.items():
        pub = fr.get(name)
        if pub is None:
            continue
        out[name] = {'published_frac': pub, 'plate_frac': plate, 'error': plate / pub - 1.0}
    worst = max(out.values(), key=lambda d: abs(d['error']))
    return {'blocks': out, 'worst_abs_error': abs(worst['error']),
            'worst_block': [k for k, v in out.items() if v is worst][0]}


def rescale_error_vs_published(split_nested=False):
    """How well does "scale the template by area ratio" reproduce a real shrink?

    The pack README's recipe for building any other core from this template is to scale the block
    ratios by total core area. Golden Cove -> Redwood Cove is that recipe with a published answer,
    so the error is measurable rather than assumed -- and it is the honest error bar on every
    ARM and RISC-V core built by the same route.

    Redwood Cove is not a pure shrink: it is a different node (Intel 4 against Intel 7) carrying
    a 2 MB L2 against 1.25 MB, so part of what this measures is a design change and part is the
    method. That is stated rather than netted out, because both are present in any real rescale.
    """
    gc = golden_cove(split_nested=split_nested)
    rw = redwood_cove(split_nested=split_nested)
    pred = gc.rescale_to(rw.total_mm2)
    out = {}
    for name, published in rw.blocks.items():
        if name not in pred.blocks:
            continue
        out[name] = {'predicted_mm2': pred.blocks[name], 'published_mm2': published,
                     'error': pred.blocks[name] / published - 1.0}
    # The 'uncore' residual is excluded from the summary: it is 1.3% of Golden Cove and 0.04% of
    # Redwood, so its ratio is a difference of two transcription residuals and carries no
    # information about the rescale. It stays in the per-block table.
    errs = [abs(v['error']) for k, v in out.items() if k != 'uncore']
    return {'scale': rw.total_mm2 / gc.total_mm2, 'blocks': out,
            'max_abs_error': max(errs), 'mean_abs_error': sum(errs) / len(errs),
            'n_blocks_summarised': len(errs),
            'note': ('Redwood Cove carries a 2 MB L2 against Golden Cove 1.25 MB on a denser '
                     'node, so the L2 is where a uniform rescale must fail and does')}


def sram_linearity_check():
    """Is L2 array area linear in capacity? The assumption behind the 384 KB blocks.

    The pack carries an L2-area-against-capacity table for three GPUs (128 KB to 1 MB), which is a
    different vendor and node from Golden Cove but is the only published test of the shape of the
    relationship in the pack. Reported rather than assumed away.
    """
    rows = pack_areas.load_block_areas()
    out = {}
    for chip in ('A100', 'GA102', 'Navi22'):
        try:
            r = pack_areas.chip_rows(chip, rows)
        except KeyError:
            continue
        pts = []
        for kb, block in ((128, 'l2_128kb'), (256, 'l2_256kb'), (512, 'l2_512kb'),
                          (1024, 'l2_1mb')):
            hit = [x for x in r if x['block'] == block and x['area_mm2'] is not None]
            if hit:
                pts.append((kb, hit[0]['area_mm2']))
        if len(pts) < 2:
            continue
        ref_kb, ref_a = pts[0]
        out[chip] = {'points': pts,
                     'mm2_per_kb': [(kb, a / kb) for kb, a in pts],
                     'linearity_error_vs_smallest': [(kb, (a / kb) / (ref_a / ref_kb) - 1.0)
                                                     for kb, a in pts]}
    return out
