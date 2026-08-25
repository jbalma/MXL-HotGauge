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


def project_plan_to_tiles(plan_W, blocks, tiles, strict=True):
    """Spread a plan expressed over processor blocks onto the tiles above them.

    ``plan_W`` maps floorplan block name -> watts to remove (positive means removal).
    ``blocks`` maps block name -> ``(x, y, w, h)`` in um, in the same coordinate frame as the
    tiles. Returns tile name -> watts removed, all non-negative.

    Each block's removal is split between the tiles it overlaps in proportion to overlap area.
    That is the only defensible mapping between two grids that do not line up, and it makes the
    geometric cost visible: a 142 x 13 um block cannot be cooled in isolation, because the tile
    above it is hundreds of microns across and cools everything else under it as well.

    With ``strict``, a block that overlaps no tile is an error rather than a silent loss of
    cooling -- a plan that quietly evaporates would look like an expensive device that does not
    work, which is the wrong conclusion to draw from a coordinate-frame mistake.
    """
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
