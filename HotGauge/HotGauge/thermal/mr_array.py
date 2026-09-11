"""The photonic cooling array as a real object in the stack: tiles, and what they can reach.

Why this exists
---------------
Microrefrigeration used to be applied as negative power on *processor* floorplan blocks. Those
powers land in the die's own ``source`` layer, so the cooling sat in the same 20 um of silicon as
the transistors. Two things follow from that, and both flatter the technology:

* **The extracted watt never crosses any silicon.** Heat was removed at the point it was made,
  with zero transport distance. Under that arrangement the burial depth of the active layer
  cannot change the answer *by construction* -- sweeping it moves silicon that no heat flows
  through on its way to the cooler.
* **The array had no geometry.** A plan could cool a 142 x 13 um block and nothing else, which is
  a pixel pitch of 13 um in one dimension. Real tiles are hundreds of microns across and cool
  whatever sits under them, hot or not.

This module puts the array where it is: its own 3D-ICE die element bonded to the exposed silicon,
carrying negative power on a floorplan of pixel tiles (see
:class:`~HotGauge.thermal.die_stack.StackSpec` with ``mr_powered=True``). Heat now has to travel
up through ``source_depth_um`` of silicon and across the bond before anything removes it, which
is the physics the whole direct-die question turns on.

What a tile can reach
---------------------
Lateral spreading in the silicon is what decides whether a tile above a hotspot actually cools
that hotspot or the neighbourhood around it, and 3D-ICE answers that -- it is a 3-D solve, not a
stack of independent 1-D paths. Nothing here models spreading; this module only says where the
tiles are and how a plan expressed over processor blocks is projected onto them.

Projection is by **area overlap**, which is the only defensible mapping between two grids that do
not line up: a block covered half by one tile and half by another has its removal split in that
ratio. A block smaller than one tile puts all of its removal on the tile above it, and that tile
then cools everything else under it as well.

Collateral cooling is not a penalty
-----------------------------------
It is tempting to read the extra area a tile touches as pure waste. It is not, and which way it
cuts depends on the die:

* **Where the peak is degenerate it helps, and may be the main mechanism.** The CPU results are
  dominated by the plateau: cooling the single hottest block buys 1.25 K because the second
  hottest immediately becomes the peak. A tile that spans several plateau members clips them
  together, which is exactly what the block-level formulation could not do at any price. And an
  over-cooled neighbour is not wasted either -- it becomes a lateral sink, and the heat flow into
  it scales with the temperature difference the cooling created.
* **Where the hotspot is isolated it costs.** Watts spent on silicon that was already cool buy no
  peak reduction, so the efficiency -- kelvin of peak per watt removed, and ultimately COP --
  gets worse.

So collateral trades **effectiveness** against **efficiency**, and which dominates is a property
of the power map rather than of the device. ``coverage_report`` reports the ratio without calling
it good or bad; a pitch sweep is what decides it. See ``examples/tile_pitch_sweep.py``.
"""

import numpy as np
import os
import math
import logging

LOGGER = logging.getLogger(__name__)

#: Default centre-to-centre tile pitch [um]. Large enough that the element count stays sane on an
#: 826 mm^2 die (a 500 um pitch there is 65 x 51 = 3315 tiles), small enough to resolve a CPU
#: core. Both ends of that trade are real, so it is a parameter everywhere it is used.
DEFAULT_PITCH_UM = 500.0

#: Fraction of each pitch cell the emitting tile actually covers. Below 1.0 the array has gaps --
#: routing, wire bond, optical access -- and the uncovered silicon is cooled only by whatever
#: spreads sideways to a neighbour.
DEFAULT_FILL = 1.0

#: Fraction of the pixel layer's FOOTPRINT that is emitting extractor -- the array charged its own
#: area (§P0.18). `[!]` AREAL, unlike ``fill`` above, which is the linear edge fraction
#: ``tile_grid`` shrinks each tile by, so a ``fill`` of 0.5 covers a QUARTER of the footprint.
#: Every user-facing knob is stated as coverage and converted with :func:`fill_for_coverage`.
#:
#: What the uncovered footprint is. In the v91 device the tile is coupler / extractor /
#: back-reflector / sensor, the pump arrives by hollow-core fibre or waveguide to a structured
#: coupler at the top of the tile, and the LPC is monolithic-backside on the semiconductor
#: platform (v91 Fig. 9.1, 9.8, 9.12). None of that sits in the silicon: it is stacked ABOVE it,
#: sharing the pixel layer's footprint with the emitting tiles. So the area the array has to be
#: charged is not logic area on the die -- it is the fraction of the cooled surface that is
#: routing, couplers, fibre access and LPC rather than extractor. That fraction is this number.
#:
#: `[!]` Consequence worth stating before anyone re-runs a control ladder on it: the CONTROL arm has
#: no array, so no control-arm ceiling (the flat-die 0.85-0.90 W/mm^2, the shaped 0.60-0.65) can
#: move with coverage. What coverage bounds is the ARRAY-assisted density and the array's cost.
#:
#: 1.0 reproduces every recorded result: the whole catalogue was solved with tiles filling the
#: footprint edge to edge. The uncovered silicon under a gap is cooled only by what spreads
#: sideways through the burial depth to a neighbouring tile, which is exactly the effect the
#: coverage ladder exists to measure rather than assume.
DEFAULT_COVERAGE = 1.0


def fill_for_coverage(coverage):
    """Linear tile edge fraction that gives an AREAL coverage of ``coverage``: ``sqrt``.

    ``tile_grid`` shrinks width and height by ``fill`` each, so covered area goes as ``fill**2``.
    Stating the knob as coverage and converting here is what stops a "50 % array" quietly meaning
    a 25 % one.
    """
    coverage = float(coverage)
    if not 0.0 < coverage <= 1.0:
        raise ValueError('array coverage must be in (0, 1], got {!r}'.format(coverage))
    return math.sqrt(coverage)


def array_area_ledger(tiles, chip_w_um, chip_h_um):
    """What the array occupies, in mm^2, against the footprint it sits on.

    ``coverage_achieved`` is the number to report: snapping to the thermal grid means the tiles
    cover what the grid allows, not exactly what was asked for (a 0.50 request at 500 um pitch on
    a 50 um grid gives 350 um tiles and 0.49). ``reserved_mm2`` is the footprint charged to
    everything that is not extractor -- couplers, waveguides, fibre access, LPC.
    """
    footprint = float(chip_w_um) * float(chip_h_um) / 1.0e6
    extractor = sum(t['w'] * t['h'] for t in tiles) / 1.0e6
    if footprint <= 0.0:
        raise ValueError('array footprint has no area')
    return {'n_tiles': len(tiles),
            'footprint_mm2': footprint,
            'extractor_mm2': extractor,
            'reserved_mm2': footprint - extractor,
            'coverage_achieved': extractor / footprint,
            'tile_mm2_max': (max(t['w'] * t['h'] for t in tiles) / 1.0e6) if tiles else 0.0}


def tile_flux_report(tile_plan_W, tiles, h_max_W_per_mm2):
    """Cooling flux per tile against the device's own ceiling -- the per-TILE envelope check.

    The planner caps removal per *block* (``h_max * block_area``, see ``clipping_plan``); the
    device delivers it per *tile*, which after projection can carry several blocks' removal on
    a footprint that coverage has shrunk. This reports the worst tile so that a plan whose
    per-block caps are all satisfied cannot hide a tile asked for more than the extractor can
    emit. ``tile_plan_W`` is POSITIVE removal per tile name (the planner's convention, not the
    stack's); zeros and absent tiles are idle.
    """
    h_max = float(h_max_W_per_mm2)
    rows = []
    for t in tiles:
        q = float(tile_plan_W.get(t['name'], 0.0))
        if q <= 0.0:
            continue
        area = t['w'] * t['h'] / 1.0e6
        rows.append((q / area if area > 0 else float('inf'), q, t['name'], area))
    if not rows:
        return {'n_engaged': 0, 'max_flux_W_per_mm2': 0.0, 'max_flux_tile': None,
                'mean_flux_W_per_mm2': 0.0, 'h_max_W_per_mm2': h_max,
                'n_tiles_over_h_max': 0, 'over_h_max': False, 'W_total': 0.0}
    rows.sort(reverse=True)
    total_q = sum(r[1] for r in rows)
    total_a = sum(r[3] for r in rows)
    return {'n_engaged': len(rows),
            'max_flux_W_per_mm2': rows[0][0], 'max_flux_tile': rows[0][2],
            'mean_flux_W_per_mm2': total_q / total_a if total_a > 0 else 0.0,
            'h_max_W_per_mm2': h_max,
            'n_tiles_over_h_max': sum(1 for r in rows if r[0] > h_max),
            'over_h_max': bool(rows[0][0] > h_max),
            'W_total': total_q}

#: Below this many tiles over the whole die, the array has no spatial structure worth the name
#: and ``ArrayWiring`` says so. Four is where a plan can first distinguish one quadrant from
#: another; at two, "which tile" is not a question it can answer, and at one the array is a
#: uniform slab with a single global knob.
MIN_MEANINGFUL_TILES = 4


def device_pitch_range_um(die_area_mm2=None, n_tiles=None):
    """What the first-generation device's TILE COUNT works out to as a pitch, on a given die.

    **This is an annotation on the pitch ladder, not an operating point**, and the distinction is
    the whole point of the function. What the demo system fixes is a *count* -- 4 to 16 tiles
    (``published_reference.DEMO_SYSTEM['n_tiles']``) over a ~200 mm^2 mobile die
    (``DIE_GEOMETRY['AMD_RYZEN_AI_5_340']``). A count is not a pitch, and converting one into an
    absolute pitch and then applying that pitch to a different die is how the catalogue briefly
    ended up configured at a single global 5 mm: **one** tile on the 7-core die and **two** on the
    34-core, which is the die under most of the sweep. Passing ``die_area_mm2`` is therefore the
    normal use; the demo die is only the default because that is where the count came from.

    Where it lands, and why it is worth reporting:

        die          area mm^2   4-16 tiles
        7-core              53   1.8-3.7 mm
        34-core            101   2.5-5.0 mm
        70-core            196   3.5-7.0 mm
        128-core           348   4.7-9.3 mm
        GA100              826   7.2-14.4 mm

    On the 34-core die that is 2.5-5.0 mm -- **coarser than the 2000 um top of the studied
    ladder**. So the first-generation device sits just beyond the coarse end of the range this
    project has measured, which is a genuinely useful thing to tell a device roadmap. It is not a
    reason to run the catalogue there: granularity is a swept variable (see
    ``examples/tile_pitch_sweep.py`` and ``scripts/array_config.sh``), and the ordering of coarse
    against fine reverses with the workload, so a point estimate reports a curve as a number.

    Returns ``(pitch_fine_um, pitch_coarse_um)`` -- most tiles first.
    """
    from HotGauge.thermal.published_reference import DEMO_SYSTEM, DIE_GEOMETRY
    if die_area_mm2 is None:
        die_area_mm2 = DIE_GEOMETRY['AMD_RYZEN_AI_5_340']['die_area_mm2']
    lo_tiles, hi_tiles = n_tiles or DEMO_SYSTEM['n_tiles']
    # n square tiles tiling an area A have pitch sqrt(A / n).
    fine = 1000.0 * math.sqrt(float(die_area_mm2) / float(max(lo_tiles, hi_tiles)))
    coarse = 1000.0 * math.sqrt(float(die_area_mm2) / float(min(lo_tiles, hi_tiles)))
    return (fine, coarse)


def _snap(v_um, cell_um):
    """Snap a coordinate to the thermal grid, the way 3D-ICE will anyway.

    Tiles that are adjacent in floating point come back overlapping after the solver quantises
    them. Snapping the *boundaries* here means the floorplan the solver reads is the floorplan
    that was designed.
    """
    return round(float(v_um) / float(cell_um)) * float(cell_um)


def tile_grid(chip_w_um, chip_h_um, pitch_um=DEFAULT_PITCH_UM, cell_um=50.0,
              fill=DEFAULT_FILL, name_prefix='MR'):
    """A regular array of pixel tiles covering the chip footprint.

    Boundaries are snapped to the thermal grid, and the last row and column are stretched to the
    chip edge rather than left short -- 3D-ICE requires the floorplan to lie inside the chip, and
    a sliver of uncovered die at one edge is an artifact of arithmetic rather than a design.
    """
    pitch_um, cell_um = float(pitch_um), float(cell_um)
    if pitch_um < cell_um:
        raise ValueError('tile pitch {:.1f} um is finer than the thermal grid {:.1f} um; the '
                         'solve cannot resolve tiles it cannot mesh'.format(pitch_um, cell_um))
    if not 0.0 < fill <= 1.0:
        raise ValueError('fill must be in (0, 1], got {!r}'.format(fill))

    n_cols = max(1, int(math.floor(float(chip_w_um) / pitch_um)))
    n_rows = max(1, int(math.floor(float(chip_h_um) / pitch_um)))

    xs = [_snap(c * chip_w_um / n_cols, cell_um) for c in range(n_cols)] + [float(chip_w_um)]
    ys = [_snap(r * chip_h_um / n_rows, cell_um) for r in range(n_rows)] + [float(chip_h_um)]

    tiles = []
    for r in range(n_rows):
        for c in range(n_cols):
            x0, x1 = xs[c], xs[c + 1]
            y0, y1 = ys[r], ys[r + 1]
            w, h = x1 - x0, y1 - y0
            if fill < 1.0:
                # Shrink about the centre, then re-snap, so a gapped array still meshes.
                cx, cy = x0 + w / 2.0, y0 + h / 2.0
                w, h = _snap(w * fill, cell_um), _snap(h * fill, cell_um)
                w, h = max(w, cell_um), max(h, cell_um)
                x0, y0 = _snap(cx - w / 2.0, cell_um), _snap(cy - h / 2.0, cell_um)
            if w <= 0 or h <= 0:
                continue
            tiles.append({'name': '{}_r{:02d}_c{:02d}'.format(name_prefix, r, c),
                          'x': x0, 'y': y0, 'w': w, 'h': h, 'row': r, 'col': c})
    if not tiles:
        raise ValueError('no tiles fit on a {:.0f} x {:.0f} um chip at {:.0f} um pitch'
                         .format(chip_w_um, chip_h_um, pitch_um))
    return tiles


def write_mr_floorplan(out_path, tiles):
    """Write the tile floorplan with power placeholders the pipeline fills in.

    ``{powers[NAME]}`` rather than literal numbers, for the same reason the processor floorplan
    uses them: a template with literal zeros passes through ``str.format`` untouched and the
    solve silently runs on an unpowered element.
    """
    lines = []
    for t in tiles:
        lines.append('{} :\n\tposition {:.3f}, {:.3f} ;\n\tdimension {:.3f}, {:.3f} ;\n'
                     '\tpower values {{powers[{}]}};'
                     .format(t['name'], t['x'], t['y'], t['w'], t['h'], t['name']))
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    LOGGER.info('wrote MR tile floorplan: %d tiles, %.0f x %.0f um extent -> %s', len(tiles),
                max(t['x'] + t['w'] for t in tiles), max(t['y'] + t['h'] for t in tiles),
                out_path)
    return out_path


def _overlap(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1):
    return (max(0.0, min(ax1, bx1) - max(ax0, bx0)) *
            max(0.0, min(ay1, by1) - max(ay0, by0)))


def _rect_distance2(cx, cy, t):
    """Squared distance from a point to a tile's rectangle; 0 inside it."""
    dx = max(t['x'] - cx, 0.0, cx - (t['x'] + t['w']))
    dy = max(t['y'] - cy, 0.0, cy - (t['y'] + t['h']))
    return dx * dx + dy * dy


def nearest_tiles(block, tiles, tol_um2=1e-6):
    """The tile(s) nearest a block's centre, by rectangle distance; several if equidistant."""
    bx, by, bw, bh = block
    cx, cy = bx + bw / 2.0, by + bh / 2.0
    d = [(_rect_distance2(cx, cy, t), t['name']) for t in tiles]
    best = min(x[0] for x in d)
    return [n for dist, n in d if dist <= best + tol_um2]


def _max_gap(intervals):
    """Largest gap between consecutive (start, end) intervals along one axis; 0 if they abut."""
    iv = sorted(set(intervals))
    gap = 0.0
    for (a0, a1), (b0, _) in zip(iv, iv[1:]):
        if b0 > a1:
            gap = max(gap, b0 - a1)
    return gap


def _inside_footprint(block, tiles):
    """Is the block's centre inside the array's footprint?

    The footprint is the tile grid's extent widened by the inter-tile gap on each side: a gapped
    grid stops half a gap short of the chip edge, so an edge block is inside the footprint even
    though it is outside every tile. At full coverage the gap is zero and this is exactly the
    grid's extent, i.e. the chip -- the recorded behaviour.
    """
    bx, by, bw, bh = block
    cx, cy = bx + bw / 2.0, by + bh / 2.0
    gx = _max_gap([(t['x'], t['x'] + t['w']) for t in tiles])
    gy = _max_gap([(t['y'], t['y'] + t['h']) for t in tiles])
    x0 = min(t['x'] for t in tiles) - gx
    y0 = min(t['y'] for t in tiles) - gy
    x1 = max(t['x'] + t['w'] for t in tiles) + gx
    y1 = max(t['y'] + t['h'] for t in tiles) + gy
    return x0 <= cx <= x1 and y0 <= cy <= y1


def block_tile_temps(tile_temps_K, blocks, tiles):
    """The temperature of the extractor ABOVE each block: area-weighted over the tiles the block
    overlaps, or the nearest tile's for a block under a gap (§P0.19).

    This is what a temperature-dependent cooling cap has to be evaluated at -- the extractor
    sits at the tile's temperature, not the block's. ``tile_temps_K`` maps tile name -> K (the
    array die's solved field); tiles absent from it are skipped, and a block with no readable
    tile is omitted so the caller falls back to its temperature-independent cap.
    """
    out = {}
    for name, (bx, by, bw, bh) in blocks.items():
        hits = []
        for t in tiles:
            if t['name'] not in tile_temps_K:
                continue
            a = _overlap(bx, by, bx + bw, by + bh,
                         t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h'])
            if a > 0:
                hits.append((a, float(tile_temps_K[t['name']])))
        tot = sum(a for a, _ in hits)
        if tot > 0:
            out[name] = sum(a * T for a, T in hits) / tot
            continue
        near = [n for n in nearest_tiles((bx, by, bw, bh), tiles) if n in tile_temps_K]
        if near:
            out[name] = sum(float(tile_temps_K[n]) for n in near) / len(near)
    return out


def tiles_over_blocks(tiles, blocks, pattern, majority=0.5):
    """Tiles whose covered area is mostly under blocks whose name matches ``pattern`` (a regex).

    The dual-zone arrangement's cold tiles (§P0.21): a tile is 'cold' when more than ``majority``
    of the block area beneath it belongs to matching blocks (the caches, by default). Returns the
    tile names. This is exactly the floorplan-dependence the single-material default avoids.
    """
    import re
    rx = re.compile(pattern)
    out = set()
    for t in tiles:
        tot, match = 0.0, 0.0
        for name, (bx, by, bw, bh) in blocks.items():
            a = _overlap(bx, by, bx + bw, by + bh, t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h'])
            if a <= 0:
                continue
            tot += a
            if rx.search(name):
                match += a
        if tot > 0 and match / tot > majority:
            out.add(t['name'])
    return out


def gap_blocks(blocks, tiles):
    """Blocks that overlap no tile at all -- the ones a gapped array cools only sideways."""
    out = []
    for name, (bx, by, bw, bh) in blocks.items():
        if not any(_overlap(bx, by, bx + bw, by + bh,
                            t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h']) > 0
                   for t in tiles):
            out.append(name)
    return sorted(out)


def project_plan_shares(plan_W, blocks, tiles, strict=True, gap_policy='nearest'):
    """``{block: {tile: watts}}`` -- the same projection as :func:`project_plan_to_tiles`, kept per
    block so a per-tile cap can be mapped back onto the blocks that asked (§P0.19)."""
    if gap_policy not in ('nearest', 'error'):
        raise ValueError("gap_policy must be 'nearest' or 'error', got {!r}".format(gap_policy))
    shares = {}
    for name, watts in plan_W.items():
        if watts is None or watts <= 0:
            continue
        if name not in blocks:
            if strict:
                raise KeyError('plan names block {!r}, which is not in the floorplan'.format(name))
            continue
        bx, by, bw, bh = blocks[name]
        hits = []
        for t in tiles:
            a = _overlap(bx, by, bx + bw, by + bh,
                         t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h'])
            if a > 0:
                hits.append((t['name'], a))
        total = sum(a for _, a in hits)
        if total <= 0:
            if gap_policy == 'nearest' and tiles and _inside_footprint(blocks[name], tiles):
                near = nearest_tiles(blocks[name], tiles)
                shares[name] = {tn: watts / len(near) for tn in near}
                continue
            if strict:
                raise ValueError(
                    'block {!r} at ({:.0f}, {:.0f}) {:.0f}x{:.0f} um overlaps no cooling tile; '
                    'the plan would silently lose {:.3f} W'.format(name, bx, by, bw, bh, watts))
            continue
        shares[name] = {tn: watts * a / total for tn, a in hits}
    return shares


def deliver_capped(plan_W, blocks, tiles, tile_caps_W, strict=True, gap_policy='nearest'):
    """Project a plan onto the tiles and clip each tile at ``tile_caps_W`` (§P0.19).

    Returns ``(tile_plan, delivered_block_plan, shortfall_W, n_capped)``. A tile asked for more
    than the extractor above it can remove at its own temperature delivers the cap, and the
    blocks that asked get their requests scaled back in the same proportion -- so the plan the
    planner reasons about (sensitivities, accounting, the reported cost) is the plan that was
    actually applied, not the one that was asked for.
    """
    shares = project_plan_shares(plan_W, blocks, tiles, strict=strict, gap_policy=gap_policy)
    requested = {t['name']: 0.0 for t in tiles}
    for bl in shares.values():
        for tn, w in bl.items():
            requested[tn] += w
    factor, delivered, n_capped, shortfall = {}, {}, 0, 0.0
    for tn, q in requested.items():
        cap = tile_caps_W.get(tn) if tile_caps_W else None
        if cap is not None and q > cap:
            cap = max(float(cap), 0.0)
            factor[tn] = cap / q if q > 0 else 0.0
            delivered[tn] = cap
            n_capped += 1
            shortfall += q - cap
        else:
            factor[tn] = 1.0
            delivered[tn] = q
    block_plan = {}
    for name, bl in shares.items():
        got = sum(w * factor[tn] for tn, w in bl.items())
        if got > 0.0:
            block_plan[name] = got
    return delivered, block_plan, shortfall, n_capped


def project_plan_to_tiles(plan_W, blocks, tiles, strict=True, gap_policy='nearest'):
    """Spread a plan expressed over processor blocks onto the tiles above them.

    ``plan_W`` maps floorplan block name -> watts to remove (positive means removal).
    ``blocks`` maps block name -> ``(x, y, w, h)`` in um, in the same coordinate frame as the
    tiles. Returns tile name -> watts removed, all non-negative.

    Each block's removal is split between the tiles it overlaps in proportion to overlap area.
    That is the only defensible mapping between two grids that do not line up, and it makes the
    geometric cost visible: a 142 x 13 um block cannot be cooled in isolation, because the tile
    above it is hundreds of microns across and cools everything else under it as well.

    **A block under a gap** (§P0.18 -- possible only when the array's coverage is below 1, since
    a full-coverage grid tiles the whole footprint) is handled by ``gap_policy``:

    * ``'nearest'`` (default): its removal goes to the nearest tile by rectangle distance,
      split equally between equidistant ones. That is the physics rather than a convenience --
      the extractor cannot be over the block, so the heat has to cross to the nearest one
      sideways through the burial depth, and 3D-ICE resolves what the block actually gets.
      The plan's watts are conserved; whether they *help* is the solve's answer, which is
      exactly what a coverage ladder measures. Unreachable at full coverage, so every recorded
      result is unchanged.
    * ``'error'``: refuse, as the ``strict`` path did before gaps existed.

    With ``strict``, a plan naming a block that is not in the floorplan is an error rather than
    a silent loss of cooling -- a plan that quietly evaporates would look like an expensive
    device that does not work, which is the wrong conclusion to draw from a coordinate-frame
    mistake.
    """
    if gap_policy not in ('nearest', 'error'):
        raise ValueError("gap_policy must be 'nearest' or 'error', got {!r}".format(gap_policy))
    out = {t['name']: 0.0 for t in tiles}
    for name, watts in plan_W.items():
        if watts is None or watts <= 0:
            continue
        if name not in blocks:
            if strict:
                raise KeyError('plan names block {!r}, which is not in the floorplan'.format(name))
            continue
        bx, by, bw, bh = blocks[name]
        hits = []
        for t in tiles:
            a = _overlap(bx, by, bx + bw, by + bh,
                         t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h'])
            if a > 0:
                hits.append((t['name'], a))
        total = sum(a for _, a in hits)
        if total <= 0:
            # Only a block INSIDE the array's footprint is a gap block. One outside it is the
            # coordinate-frame mistake the strict path has always refused, and routing it to
            # the nearest tile would hide exactly that.
            if gap_policy == 'nearest' and tiles and _inside_footprint(blocks[name], tiles):
                near = nearest_tiles(blocks[name], tiles)
                for tname in near:
                    out[tname] += watts / len(near)
                continue
            if strict:
                raise ValueError(
                    'block {!r} at ({:.0f}, {:.0f}) {:.0f}x{:.0f} um overlaps no cooling tile; '
                    'the plan would silently lose {:.3f} W'.format(name, bx, by, bw, bh, watts))
            continue
        for tname, a in hits:
            out[tname] += watts * a / total
    return out


def ideal_targeting_tiles(blocks, cell_um=50.0, name_prefix='MRB'):
    """One cooling tile per floorplan block: the pitch -> 0 limit, in one ordinary solve.

    A tile finer than every feature on the die can target any block exactly, so the infinitely
    fine array is just "cool precisely the blocks the plan names" -- with the cooling still in
    the pixel layer, above the silicon, where the hardware puts it. That is this.

    It exists because the fine end of a pitch sweep is not reachable by simulation. 3D-ICE must
    mesh at least as finely as the tiles, and on an 8.8 x 6.1 mm die a 1 um grid is 483 million
    unknowns -- about 122 days of factorisation at the measured N^1.67 scaling, and terabytes of
    LU factors. A 10 um grid is 4.8 million unknowns and roughly 1.3 hours per factorisation,
    which affords a few one-off solves but no leakage-feedback loop.

    Rather than extrapolate the trend, this computes its endpoint exactly. Note the endpoint is
    an upper bound on what targeting can buy, not a buildable device: it is finer than the
    thermal grid the rest of the model runs on, so it separates "does finer targeting help" from
    "can the mesh see it".
    """
    cell_um = float(cell_um)
    tiles = []
    for i, (name, (x, y, w, h)) in enumerate(sorted(blocks.items())):
        x0, y0 = _snap(x, cell_um), _snap(y, cell_um)
        x1, y1 = _snap(x + w, cell_um), _snap(y + h, cell_um)
        # A block thinner than a cell snaps to zero width. Give it one cell rather than dropping
        # it: the solver cannot resolve it either way, and a silently missing tile would lose
        # that block's cooling with no error.
        if x1 <= x0:
            x1 = x0 + cell_um
        if y1 <= y0:
            y1 = y0 + cell_um
        tiles.append({'name': '{}_{:04d}'.format(name_prefix, i), 'block': name,
                      'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0, 'row': 0, 'col': i})

    # Everything is cell-aligned, so overlap is exact: rasterise and look for a cell claimed
    # twice. 3D-ICE rejects overlapping floorplan elements, and the failure mode is worth naming
    # rather than passing through -- a die whose blocks are finer than the mesh cannot be
    # targeted per block AT THIS RESOLUTION, which is a statement about the model, not the array.
    claimed, clashes = {}, []
    for t in tiles:
        for cx in range(int(t['x'] / cell_um), int((t['x'] + t['w']) / cell_um)):
            for cy in range(int(t['y'] / cell_um), int((t['y'] + t['h']) / cell_um)):
                prev = claimed.get((cx, cy))
                if prev is not None:
                    clashes.append((prev, t['block']))
                else:
                    claimed[(cx, cy)] = t['block']
    if clashes:
        seen, examples = set(), []
        for a, b in clashes:
            if (a, b) not in seen:
                seen.add((a, b))
                examples.append('{} / {}'.format(a, b))
        raise ValueError(
            'per-block targeting is not representable on a {:.0f} um grid for this floorplan: '
            '{} block pairs collide once snapped to the mesh, e.g. {}. Blocks thinner than one '
            'thermal cell cannot be given their own cooling tile because the solver cannot '
            'resolve them either -- so the pitch -> 0 limit is undefined here rather than merely '
            'expensive. Use a coarser floorplan, or a finer grid if the factorisation affords '
            'one.'.format(cell_um, len(seen), ', '.join(examples[:3])))
    return tiles


def tile_powers_for_stack(tile_plan_W, tiles):
    """Tile powers as 3D-ICE sees them: **negative**, one entry per tile, zeros included.

    Every tile must appear. A floorplan element with no power entry is not zero-powered, it is a
    template placeholder that never got substituted.
    """
    return {t['name']: -float(tile_plan_W.get(t['name'], 0.0)) for t in tiles}


def tile_power_schedule(plans_by_slot, tiles, blocks, gap_policy='nearest'):
    """Per-slot tile powers for a TRANSIENT solve (§P0.25, F4): ``{tile: array(n_slots)}``,
    negative, every tile present in every slot.

    ``plans_by_slot`` is a list of block-level plans (``{block: W}``, or ``{}`` for an idle
    slot), one per slot of the power trace. Each plan is projected onto the tiles exactly as a
    steady plan is (:func:`project_plan_to_tiles`), so a modulated array is the steady planner's
    plan switched on and off slot by slot -- the laser is optical and follows in microseconds,
    which is the capability this schedule exists to measure.
    """
    n = len(plans_by_slot)
    out = {t['name']: np.zeros(n) for t in tiles}
    for i, plan in enumerate(plans_by_slot):
        if not plan:
            continue
        tp = project_plan_to_tiles(plan, blocks, tiles, gap_policy=gap_policy)
        for name, q in tp.items():
            out[name][i] = -float(q)
    return out


def blocks_from_floorplan(flp):
    """``{name: (x, y, w, h)}`` in um from a :class:`HotGauge.utils.floorplan.Floorplan`."""
    return {e.name: (e.minx, e.miny, e.width, e.height) for e in flp.elements}


def coverage_report(plan_W, tile_plan_W, blocks, tiles, share_floor=0.01):
    """What the projection cost, in numbers rather than in prose.

    The interesting figure is ``collateral_area_ratio``: the die area sitting under an engaged
    tile, divided by the area of the blocks the plan actually asked to cool. It is 1.0 only when
    the plan aligns with the tile grid.

    It is reported, not judged. On a degenerate peak the extra area is the mechanism that makes a
    tile array beat block-level clipping; on an isolated hotspot it is watts spent on silicon
    that did not need them. Effectiveness and efficiency move in opposite directions and the
    power map decides which wins.
    """
    total_W = sum(v for v in tile_plan_W.values() if v > 0)
    engaged = [t for t in tiles if tile_plan_W.get(t['name'], 0.0) > 1e-12]
    asked_area = sum(blocks[n][2] * blocks[n][3] for n, w in plan_W.items()
                     if w and w > 0 and n in blocks)

    # Which tiles count as cooling. Any-overlap overstates it badly: snapping puts slivers of
    # neighbouring tiles inside a block's footprint, and a tile carrying 0.1% of the watts was
    # counted at its full area -- which inflated the per-block case to 12.6x when the watts were
    # almost entirely on one tile. Tiles carrying at least ``share_floor`` of the removal are the
    # ones doing the work; the total area of THOSE is the silicon actually being cooled.
    material = [t for t in engaged if tile_plan_W[t['name']] >= share_floor * total_W]
    eff_area = sum(t['w'] * t['h'] for t in material)
    engaged_area = sum(t['w'] * t['h'] for t in engaged)
    n_material = len(material)
    return {'n_tiles': len(tiles), 'n_engaged': len(engaged), 'n_material': n_material,
            'engaged_area_um2': engaged_area, 'effective_area_um2': eff_area,
            'requested_area_um2': asked_area,
            'collateral_area_ratio': (eff_area / asked_area) if asked_area > 0 else float('nan'),
            'collateral_any_overlap': ((engaged_area / asked_area) if asked_area > 0
                                       else float('nan')),
            'W_requested': sum(w for w in plan_W.values() if w and w > 0),
            'W_projected': sum(tile_plan_W.values())}


class ArrayWiring(object):
    """Everything a driver needs to put a cooling plan on the array, in one object.

    Six drivers call ``run_mr_clipping`` and every one of them needs the same four things: a tile
    grid over the floorplan, a tile floorplan on disk for the stack to reference, a place to hold
    the current plan between solves, and the two sets of keyword arguments that connect them. Done
    by hand per driver it is about twenty-five lines each, and the two bugs found wiring the first
    one -- an array rendered unpowered, and a sign converted twice -- are exactly the kind that
    would then be re-introduced independently in the other five.

    Usage::

        wiring = ArrayWiring(flp_path, run_dir, pitch_um=2000.0) if arm != 'control' else None
        solver = ICEThermalSolver(stack, flp, node, **(wiring.solver_kwargs() if wiring else {}))
        res = run_mr_clipping(trace, solve, geom, params, name_map,
                              **(wiring.planner_kwargs() if wiring else {}))

    ``solver_kwargs`` must be re-read for **every** solver built, because the planner revises the
    plan between solves and the solver renders whatever is current at construction.
    """

    def __init__(self, flp_path, out_dir, pitch_um=DEFAULT_PITCH_UM, cell_um=50.0,
                 flp_format='3D-ICE', name='MR.flp', coverage=DEFAULT_COVERAGE):
        import math
        import os
        from HotGauge.utils.floorplan import Floorplan

        self.cell_um = float(cell_um)
        self.pitch_um = float(pitch_um)
        # The array charged its own footprint (§P0.18). AREAL; converted to the linear fill the
        # grid builder takes. 1.0 is every recorded result.
        self.coverage = float(coverage)
        fill = fill_for_coverage(self.coverage)
        self.blocks = blocks_from_floorplan(Floorplan.from_file(flp_path, frmt=flp_format))
        if not self.blocks:
            raise ValueError('no floorplan blocks parsed from {}'.format(flp_path))
        chip_w = int(math.ceil(max(b[0] + b[2] for b in self.blocks.values())
                               / self.cell_um) * self.cell_um)
        chip_h = int(math.ceil(max(b[1] + b[3] for b in self.blocks.values())
                               / self.cell_um) * self.cell_um)
        self.chip_um = (chip_w, chip_h)
        self.tiles = tile_grid(chip_w, chip_h, pitch_um=self.pitch_um, cell_um=self.cell_um,
                               fill=fill)
        self.ledger = array_area_ledger(self.tiles, chip_w, chip_h)
        # Blocks with no tile above them at all; their removal is routed to the nearest
        # tile (project_plan_to_tiles, gap_policy='nearest'). Empty at full coverage.
        self.gap_blocks = gap_blocks(self.blocks, self.tiles)
        # A handful of tiles over a whole die is a uniform slab with one or two global knobs, and
        # it is easy to arrive at by accident -- converting the device's TILE COUNT into an
        # absolute pitch and applying it to a smaller die does exactly that. Everything still
        # runs: the projection conserves, the plan applies, the accounting balances. But
        # "extraction is a spatially-matched response" is vacuous below a few tiles, and a sweep
        # of spot policy or targeting against 2 tiles measures nothing.
        #
        # The threshold is 4 rather than 1 because 1 was not enough: at 5 mm the 34-core die --
        # the die under 38 of the 44 --cores invocations in scripts/ -- gives TWO tiles, and that
        # ran silently. Four is where a tile can begin to distinguish one quadrant of a die from
        # another; below it, "which tile" is not a question the plan can answer.
        if len(self.tiles) < MIN_MEANINGFUL_TILES:
            LOGGER.warning(
                'the %0.0f um pitch gives %d tile(s) over a %0.1f x %0.1f mm die: the array has '
                'essentially NO spatial targeting at this granularity. Results are valid but any '
                'conclusion about targeting, pitch or spot policy is vacuous -- see '
                'mr_array.device_pitch_range_um, and prefer the pitch LADDER over a single '
                'coarse point.',
                self.pitch_um, len(self.tiles), chip_w / 1000.0, chip_h / 1000.0)
        self.degenerate = len(self.tiles) < MIN_MEANINGFUL_TILES

        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        # ICESim fills the template per run, so it has to live on disk as a PATH. Passing the
        # contents instead fails far downstream with "File name too long".
        #
        # ABSOLUTE, and not as a tidiness measure: ExecutableJob fills the template inside a
        # multiprocessing worker whose cwd is the HotGauge package directory, not the caller's.
        # A relative path handed in by a driver invoked as `--out-dir results/x` therefore
        # resolves to HotGauge/HotGauge/script_runner/results/x/MR.flp and the run dies with a
        # FileNotFoundError naming a directory nobody asked for. Every existing driver happened
        # to pass an absolute path, which is why this survived.
        self.mr_flp_template = os.path.join(out_dir, name)
        write_mr_floorplan(self.mr_flp_template, self.tiles)
        self._powers = tile_powers_for_stack({t['name']: 0.0 for t in self.tiles}, self.tiles)
        # Plan generation, and the generation the last solver was built from. See
        # _assert_last_plan_was_solved.
        self._plan_gen = 0
        self._read_gen = 0

    @property
    def powers(self):
        """Current tile powers in **stack convention**: negative watts remove heat."""
        return dict(self._powers)

    def set_mr_powers(self, tile_stack_powers):
        """Callback for :class:`~HotGauge.thermal.microrefrigeration.CoolingApplication`.

        What arrives is already in stack convention -- the applier runs the plan through
        :func:`tile_powers_for_stack` before calling this. Converting again flips removal into
        heating, which is a wrong answer rather than an error, so it is stated here rather than
        left to each caller to remember.
        """
        self._assert_last_plan_was_solved()
        self._powers = dict(tile_stack_powers)
        self._plan_gen += 1

    def _assert_last_plan_was_solved(self):
        """Refuse to overwrite a plan that no solver ever read.

        The failure this catches has no other symptom. ``solver_kwargs()`` snapshots the tile
        powers and ``ICEThermalSolver`` renders them into the array's floorplan **at
        construction**, so a driver that builds one solver and hands it to ``run_mr_clipping``
        re-solves, every iteration, the plan the wiring held before the planner ever ran -- all
        zeros. The loop then completes, the projection conserves its watts, the accounting
        reports the full budget removed, and the temperature field is the uncooled one. There is
        no error, no warning and no wrong number anywhere except the answer.

        It is a two-line mistake to make (the class docstring's own usage example is the correct
        form, and it is easy to hoist the solver out of the closure "for efficiency"), and it
        cost this project a probe run before it was noticed. So it is enforced rather than
        documented: if a plan is replaced without any solver having read the previous one, the
        run stops here instead of producing a plausible field.

        The FIRST plan is exempt -- drivers legitimately zero the tiles before the baseline
        solve -- and repeated reads are fine, because the leakage loop builds one solver per
        iteration against an unchanged plan.
        """
        if self._plan_gen and self._read_gen != self._plan_gen:
            raise RuntimeError(
                'the cooling plan is being replaced but no solver ever read the previous one '
                '(plan generation {}, last read {}). The solver renders the tile powers at '
                'CONSTRUCTION, so a solver built once and reused solves a stale -- usually '
                'all-zero -- array, removes nothing, and reports success. Build a fresh '
                'ICEThermalSolver inside the solve callback, re-reading solver_kwargs() each '
                'time; see ArrayWiring\'s usage example.'
                .format(self._plan_gen, self._read_gen))

    def solver_kwargs(self):
        """For ``ICEThermalSolver``. Re-read for every solver: the plan moves between solves."""
        self._read_gen = self._plan_gen
        return {'mr_flp_template': self.mr_flp_template, 'mr_powers': self.powers}

    def planner_kwargs(self):
        """For ``run_mr_clipping``. Constant for the life of the run."""
        return {'tiles': self.tiles, 'tile_blocks': self.blocks,
                'set_mr_powers': self.set_mr_powers}

    def flux_report(self, h_max_W_per_mm2):
        """Per-tile flux of the CURRENT plan against ``h_max`` -- see :func:`tile_flux_report`.

        Reads the plan the wiring holds, which after ``run_mr_clipping`` returns is the plan
        the reported field was solved on. Stack convention is negative, so it is flipped here.
        """
        return tile_flux_report({k: -v for k, v in self._powers.items()}, self.tiles,
                                h_max_W_per_mm2)

    def area_fields(self):
        """The ledger as row fields, so every driver stamps the same names."""
        L = self.ledger
        return {'array_coverage': self.coverage,
                'array_coverage_achieved': L['coverage_achieved'],
                'array_extractor_mm2': L['extractor_mm2'],
                'array_reserved_mm2': L['reserved_mm2'],
                'array_footprint_mm2': L['footprint_mm2'],
                'array_n_gap_blocks': len(self.gap_blocks),
                'array_n_blocks': len(self.blocks)}

    def __repr__(self):
        return ('<ArrayWiring {} tiles at {:.0f} um over {:.0f}x{:.0f} um, coverage {:.2f}>'
                .format(len(self.tiles), self.pitch_um, self.chip_um[0], self.chip_um[1],
                        self.ledger['coverage_achieved']))


def stack_carries_an_array(stack_file):
    """Does this ``.stk`` declare a cooling array as a second powered die?

    The array is only real if the stack has a die element for it. A driver that wires up tiles
    against a stack without one produces a plan that is computed, projected, and then lands
    nowhere -- which reads as an expensive cooler that does not work.
    """
    from HotGauge.thermal.ice_server import stack_floorplans
    try:
        return len(stack_floorplans(stack_file)) > 1
    except Exception:                     # noqa: BLE001 - an unreadable stack is not an array
        return False


def wiring_for_stack(stack_file, flp_path, out_dir, want_array=True, **kw):
    """``ArrayWiring`` when the stack can carry one, ``None`` when it cannot.

    Derives the placement from the **stack** rather than from a flag, because the two can
    disagree and the disagreement is silent in both directions: tiles wired against a
    single-die stack compute a plan that lands nowhere, and an array stack left unwired
    carries an inert slab that only adds resistance.

    ``want_array=False`` selects the legacy in-source-layer placement deliberately. Asking for
    the array on a stack that has no die element for it is an error, not a fallback -- falling
    back would silently downgrade the physics to an upper bound.
    """
    has = stack_carries_an_array(stack_file)
    if not want_array:
        return None
    if not has:
        raise ValueError(
            'stack {} has no cooling-array die, so a tile plan would land nowhere. Use a stack '
            'with one (e.g. --stack spec:package=direct_die,mr=GAAS) or pass --no-array to '
            'select the legacy in-source-layer placement deliberately -- it is an upper bound, '
            'not the device.'.format(stack_file))
    return ArrayWiring(flp_path, out_dir, **kw)
