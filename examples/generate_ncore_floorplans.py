#!/usr/bin/env python
"""Generate a standard set of N-core floorplans that the trace pipeline can use directly.

Why this exists
---------------
The shipped floorplan is **7-core** while our Sniper/McPAT traces are **8-core**, so every
`FPUs_7`, `cALU_7`, `L3_7` ... has no block to land on and is silently discarded --
2.064 W, **10.4 % of real leaf power** (see `die_power_of_trace`). That single mismatch caps
every thermal and MR result we have.

Nothing about the pipeline is 7-core specific. `mcpat_to_flp_name` extracts the core index
from the McPAT label and appends it, `split_L3_power` and `prepare_dice_trace` both take
`num_cores`, and `make_processor` is a general tiler. The "7" comes from exactly one line::

    def make_7_core_processor(core_flp):
        return make_processor(core_flp, 3, 3, {(1,0):'IMC', (1,2):'SoC'})

i.e. a 3x3 tiling with two slots handed to IMC and SoC. **So the trace approach needs no
change for arbitrary core count** -- only the floorplan does.

Grid selection
--------------
A processor needs `n_cores + 2` slots (the extra two are IMC and SoC, which
`add_extra_DICE_units` puts power on). We pick the *squarest exact* factorisation of that
count, so the die does not come out absurdly elongated, and place IMC/SoC mid-edge on opposite
sides -- the same arrangement the shipped 7-core uses.

Exact factorisation matters: every grid slot must be either a core or a named substitute, and
the substitute names (`IMC`, `SoC`) are not repeatable -- duplicates would collide in the
floorplan and in the power model. When `n_cores + 2` is prime (n = 5, 9, 11 ...) there is no
sensible grid, and this raises with the nearest workable core counts rather than silently
emitting a 1xN sliver.

Usage
-----
    python examples/generate_ncore_floorplans.py --cores 8
    python examples/generate_ncore_floorplans.py --cores 4 6 8 16 --detail 3
"""
import os
import sys
import math
import argparse
import itertools

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))
sys.path.insert(0, _HERE)   # floorplans.py / config.py live here

from HotGauge.configuration import mcpat_to_flp_name, NODE_LENGTH_FACTORS
from HotGauge.configuration.mcpat import MCPAT_UNIT_NAME_MAP, NoSuchMCPATUnitError
from HotGauge.utils import Floorplan

_FLP_UNIT_NAMES = set(MCPAT_UNIT_NAME_MAP.values())


def to_flp_name(name):
    """Convert a base-floorplan element name to its floorplan unit name.

    The base floorplan carries bare McPAT hierarchy paths (``L2``,
    ``Execution Unit/Integer ALUs``), but ``mcpat_to_flp_name`` requires a ``CoreN/`` prefix --
    which is why the shipped ``generate_floorplans`` raises on the current HotGauge and its
    outputs had to be pre-generated with an older version. Prefix, and accept names that are
    already floorplan units; anything else is a genuine error rather than something to pass
    through silently.
    """
    if name in _FLP_UNIT_NAMES:
        return name
    try:
        return mcpat_to_flp_name('Core0/' + name)
    except (NoSuchMCPATUnitError, KeyError):
        raise ValueError('Cannot map floorplan element {!r} to a McPAT unit name'.format(name))

import floorplans as fp   # the shipped generator: area stats, level splitting, tiling

# floorplans.py only binds its module-level LOGGER inside main() (`from config import LOGGER`),
# so calling its functions directly raises NameError from the warn() paths. Inject one rather
# than editing their file.
if getattr(fp, 'LOGGER', None) is None:
    import logging
    fp.LOGGER = logging.getLogger('ncore_floorplans')


#: Largest length:width ratio a generated die may have. An exact factorisation is not enough:
#: 32 cores needs 34 slots, and 34 = 2 x 17 factors only as a 2x17 strip. That is not a die
#: shape, and the thermal answer it gives is dominated by the aspect ratio rather than by the
#: architecture -- edge cores on a 2xN strip have a cooling advantage no real layout would give
#: them. Reject it and point at a nearby core count that tiles squarely.
MAX_ASPECT_RATIO = 2.5


def _well_shaped(n_cores, max_aspect=MAX_ASPECT_RATIO):
    """Best (w, l) for ``n_cores`` if it tiles within ``max_aspect``, else None."""
    slots = n_cores + 2
    best = None
    for w in range(1, int(math.isqrt(slots)) + 1):
        if slots % w:
            continue
        l = slots // w
        if w < 1 or l / w > max_aspect:
            continue
        if best is None or abs(l - w) < abs(best[1] - best[0]):
            best = (w, l)
    return best


def grid_for(n_cores, max_aspect=MAX_ASPECT_RATIO):
    """(width, length, substitutes) for an ``n_cores`` processor plus IMC and SoC.

    Returns the squarest exact factorisation of ``n_cores + 2``, rejecting any tiling more
    elongated than ``max_aspect``. IMC and SoC go mid-edge on opposite sides, matching the
    shipped 7-core layout.
    """
    best = _well_shaped(n_cores, max_aspect)
    if best is None:
        nearby = [n for n in range(2, 4 * max(n_cores, 8))
                  if _well_shaped(n, max_aspect) is not None]
        nearby.sort(key=lambda n: abs(n - n_cores))
        raise ValueError(
            '{} cores needs {} grid slots, which has no factorisation within an aspect ratio '
            'of {:g}. Every slot must hold a core or a named substitute, and IMC/SoC cannot '
            'be duplicated. Nearby core counts that tile squarely: {}'.format(
                n_cores, n_cores + 2, max_aspect, sorted(nearby[:6])))
    w, l = best
    # make_processor iterates `for y, x in product(range(width), range(length))` and keys
    # substitutes by (x, y). Put IMC on the first row and SoC on the last, mid-span.
    mid = l // 2
    return w, l, {(mid, 0): 'IMC', (mid, w - 1): 'SoC'}


def make_n_core_processor(core_flp, n_cores):
    """Generalisation of ``floorplans.make_7_core_processor`` to any workable core count."""
    w, l, substitutes = grid_for(n_cores)
    return fp.make_processor(core_flp, w, l, substitutes)


def generate(output_dir, fname_frmt, flp, n_cores, padding_width=fp.PADDING_SIZE,
             nodes=('14nm', '10nm', '7nm'), force=False):
    """Mirror of ``floorplans.generate_floorplans`` with the core count parameterised.

    Emits, per tech node, both the plain ``.flp`` and the ``_template.flp`` (with ``{powers[..]}``
    placeholders) that ``ICESim`` fills -- the template is the one the pipeline consumes.
    """
    written = []
    old_frmt = flp.frmt
    flp.frmt = '3D-ICE'
    for node in nodes:
        core_flp = flp * NODE_LENGTH_FACTORS[node]
        for el in core_flp.elements:
            el.name = to_flp_name(el.name)

        processor_flp = make_n_core_processor(core_flp, n_cores)
        if padding_width:
            fp.add_padding(core_flp, padding_width)
            fp.add_IO(processor_flp, padding_width)
        core_flp.reset_to_origin()
        processor_flp.reset_to_origin()

        suffix = '{}core'.format(n_cores)
        # Never silently replace a shipped floorplan. Regenerating the 7-core with the current
        # HotGauge produces 235 blocks where the shipped file has 228, so an accidental
        # overwrite would quietly invalidate every result computed against the original.
        if not force:
            clash = [os.path.join(output_dir, fname_frmt.format(frmt=f, node=node, suffix=suffix))
                     for f in ('3D-ICE', 'hotspot', '3D-ICE_template')]
            existing = [c for c in clash if os.path.exists(c)]
            if existing:
                raise FileExistsError(
                    'refusing to overwrite {} existing file(s), e.g. {} -- pass --force if you '
                    'really mean to replace them'.format(len(existing),
                                                         os.path.basename(existing[0])))
        for frmt in ['3D-ICE', 'hotspot']:
            processor_flp.frmt = frmt
            out = os.path.join(output_dir, fname_frmt.format(frmt=frmt, node=node, suffix=suffix))
            processor_flp.to_file(out)
            written.append(out)
        processor_flp.frmt = '3D-ICE'
        out = os.path.join(output_dir, fname_frmt.format(frmt='3D-ICE_template', node=node,
                                                         suffix=suffix))
        processor_flp.to_file(out, element_powers=True)
        written.append(out)
    flp.frmt = old_frmt
    return written


def validate(template_path, n_cores):
    """Check a generated template actually satisfies the pipeline's requirements.

    Generating a geometrically valid floorplan is not enough: the blocks must carry the McPAT
    names the power model maps onto, for every core index. This catches a silently unusable
    floorplan at generation time rather than after a multi-hour thermal run.
    """
    from HotGauge.thermal.leakage_feedback import mcpat_flp_name_map
    from HotGauge.configuration.mcpat import MCPAT_UNIT_NAME_MAP

    flp = Floorplan.from_file(template_path)
    blocks = {e.name for e in flp.elements}
    unit_names = set(MCPAT_UNIT_NAME_MAP.values())

    missing = []
    for core in range(n_cores):
        for unit in unit_names:
            name = '{}_{}'.format(unit, core)
            # Not every unit exists at every level of detail; only flag units that exist for
            # core 0 but are absent for another core -- that is a real per-core gap.
            if '{}_0'.format(unit) in blocks and name not in blocks:
                missing.append(name)
    area_mm2 = (flp.width * flp.height) / 1.0e6
    per_core = sorted({b.rsplit('_', 1)[0] for b in blocks if b.rsplit('_', 1)[-1].isdigit()})
    max_idx = max((int(b.rsplit('_', 1)[-1]) for b in blocks
                   if b.rsplit('_', 1)[-1].isdigit()), default=-1)
    return {'blocks': len(blocks), 'area_mm2': area_mm2, 'unit_types': len(per_core),
            'max_core_idx': max_idx, 'missing': missing,
            'has_IMC': 'IMC' in blocks, 'has_SoC': 'SoC' in blocks,
            'has_IO': any(b.startswith('IO_') for b in blocks)}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cores', type=int, nargs='+', default=[8],
                    help='core counts to generate')
    ap.add_argument('--detail', type=int, default=3, choices=[0, 1, 2, 3],
                    help='floorplan level of detail; 3 = finest (what the 7-core default uses)')
    ap.add_argument('--nodes', nargs='+', default=['14nm', '10nm', '7nm'])
    ap.add_argument('--output-dir', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--area-json', default=os.path.join(_HERE, 'floorplans',
                                                        'adjusted_14nm-area.json'))
    ap.add_argument('--force', action='store_true',
                    help='overwrite existing floorplans (refused by default -- regenerating '
                         'the shipped 7-core yields a DIFFERENT file, 235 blocks vs 228)')
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print('N-core floorplan generation')
    print('  detail level : {}   nodes: {}'.format(args.detail, ', '.join(args.nodes)))
    print('  output       : {}\n'.format(args.output_dir))

    raw_stats = fp.load_14nm_stats(args.area_json)
    split_level_stats = fp.split_levels(raw_stats)

    # Build up to the requested level of detail, exactly as floorplans.main() does.
    base = fp.get_base_floorplan(split_level_stats)
    if args.detail >= 1:
        base = fp.add_pipeline(base, split_level_stats[1])
    if args.detail >= 2:
        base = fp.add_level2(base, split_level_stats[2])
    if args.detail >= 3:
        base = fp.add_level3(base, split_level_stats[3])

    rc = 0
    for n in args.cores:
        try:
            w, l, subs = grid_for(n)
        except ValueError as e:
            print('  [SKIP] {}'.format(e))
            rc = 1
            continue
        print('  {} cores -> {}x{} grid, {} slots, substitutes {}'.format(
            n, w, l, w * l, sorted(subs.values())))
        frmt = 'skylake{{node}}_{{suffix}}_{}_{{frmt}}.flp'.format(args.detail)
        try:
            written = generate(args.output_dir, frmt, base, n, nodes=args.nodes,
                               force=args.force)
        except FileExistsError as e:
            print('     [SKIP] {}'.format(e))
            rc = 1
            continue
        for node in args.nodes:
            tmpl = os.path.join(args.output_dir, frmt.format(
                node=node, suffix='{}core'.format(n), frmt='3D-ICE_template'))
            v = validate(tmpl, n)
            status = 'OK' if (not v['missing'] and v['max_core_idx'] == n - 1) else 'PROBLEM'
            print('     {:<6s} {:>4d} blocks, {:>7.2f} mm^2, {} unit types, cores 0..{}  '
                  'IMC={} SoC={} IO={}  [{}]'.format(
                      node, v['blocks'], v['area_mm2'], v['unit_types'], v['max_core_idx'],
                      v['has_IMC'], v['has_SoC'], v['has_IO'], status))
            if v['missing']:
                print('        MISSING per-core blocks: {}{}'.format(
                    v['missing'][:6], ' ...' if len(v['missing']) > 6 else ''))
                rc = 1
        print('     wrote {} files'.format(len(written)))
    return rc


if __name__ == '__main__':
    sys.exit(main())
