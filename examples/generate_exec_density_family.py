#!/usr/bin/env python
"""D1 (§P0.22.3): the 34-core die with a DENSER execution cluster, as a floorplan family.

    python examples/generate_exec_density_family.py --factors 0.5 0.25

What changes and what does not
------------------------------
The execution units -- Complex ALUs, Integer ALUs, Floating Point Units, and through the shipped
1.981x ratio the AVX-512 accelerator -- have their AREAS scaled by ``factor``. Nothing else moves:
the caches, the front end, the load/store path and the leftover ``core_other`` slab keep their
areas, because the delta is subtracted from ``Execution Unit/Area`` and the core total at the
same time (otherwise the tiler would hand the freed area to ``core_other``, which is the
accounting slab and not a design element). McPAT's per-unit POWER is untouched -- the trace is
the same -- so a unit at half the area runs at twice the W/mm^2. That is the design move
``ARCHITECTURE_EVOLUTION.md`` §3 names second: let the cluster the array can resolve get denser
and hotter than a conventional floorplan would allow.

`[!]` The die SHRINKS. Compare family members with the reference at matched die WATTS (the
CODESIGN_PLAN §9 invariant), never at matched W/mm^2: ``--density`` on the drivers is watts
over the family member's own area.

`[!]` IMC, SoC and the IO pads are sized by the tiler from the core footprint, so they shrink
with the die (about 14 % on the x0.5 member) and carry their modelled power a little denser.
That is the tiler's convention, not a design choice, and it is recorded in the evidence file.

X3 (§P0.27.3): the book's floorplan overheads (SoC Physical Design p. 34, U = 70 %, T = 15 %).
``--utilisation U --overhead T`` scales every STANDARD-CELL unit's area by (1 + T)/U -- the
leftover ``core_other`` slab included, it is un-itemised control logic -- with McPAT's power
unchanged; ``--cache-halo-um h`` grows each SRAM macro (L2, L3, iCache, DCache) by a keep-out ring
of ``h`` (physical microns at the 7 nm placement; halo + channel) modelled as macro area at
constant macro power (square-macro assumption; the ring is not separately unpowered). Members
built with these carry ``--tag`` in their directory name (``d1_exec<factor>_<tag>``).

Output: ``examples/floorplans/outputs/d1_exec<factor>/skylake7nm_34core_3_*.flp`` (the naming
``mr_comparison.floorplan_path`` expects, so ``--flp-dir`` selects a member) and the scaled area
JSON beside them, plus a per-unit density table against the reference.
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))
sys.path.insert(0, _HERE)

import floorplans as fp                                   # noqa: E402
from generate_ncore_floorplans import generate, validate  # noqa: E402
from HotGauge.utils import Floorplan                      # noqa: E402

#: The units that get denser. The AVX-512 accelerator is DERIVED from the FPU at import
#: (configuration.mcpat.DERIVED_UNITS), so it follows the FPU without being listed.
EXEC_UNITS = ('Execution Unit/Complex ALUs/Area',
              'Execution Unit/Integer ALUs/Area',
              'Execution Unit/Floating Point Units/Area')


def scaled_area_json(src, factor, dst):
    stats = json.load(open(src))
    core = stats['Core']
    delta, delta_fpu = 0.0, 0.0
    for k in EXEC_UNITS:
        new = core[k] * factor
        delta += core[k] - new
        if k.endswith('Floating Point Units/Area'):
            delta_fpu += core[k] - new
        core[k] = new
    core['Execution Unit/Area'] -= delta
    # `[!]` The FPU delta stays INSIDE the core total on purpose. floorplans.load_14nm_stats
    # relocates the FPU into AVX_FPU and subtracts it from its parents but not from the core
    # total (its own comment calls this an HPCA-era bug and leaves it), so the reference die's
    # leftover ``core_other`` slab already contains the ORIGINAL FPU area. Subtracting the FPU
    # delta here would shrink that slab by exactly the delta (measured: 15.850 -> 13.167 mm^2
    # on the x0.5 member) and turn a design move into an accounting move. The slab must not
    # change; only the named units do.
    core['Area'] -= (delta - delta_fpu)
    # Cosmetic: the processor totals restate the cores; keep them consistent.
    n_cores = round(stats['Processor']['Total Cores/Area'] / (stats['Core']['Area'] + delta))
    stats['Processor']['Total Cores/Area'] -= (delta - delta_fpu) * n_cores
    stats['Processor']['Area'] -= (delta - delta_fpu) * n_cores
    # The loader asserts the JSON holds exactly the four McPAT sections, so the provenance goes
    # in a sidecar rather than in the file it reads.
    with open(dst, 'w') as f:
        json.dump(stats, f, indent=1)
    with open(dst.replace('.json', '.meta.json'), 'w') as f:
        json.dump({'factor': factor, 'scaled': list(EXEC_UNITS), 'delta_mm2_per_core': delta,
                   'source': os.path.relpath(src, _REPO)}, f, indent=1)
    return delta


#: SRAM hard macros: they keep their own area and get a halo; everything else is standard cells.
MACRO_UNITS = ('L2/Area', 'Instruction Fetch Unit/Instruction Cache/Area',
               'Load Store Unit/Data Cache/Area')
#: The tiler rescales two macros AFTER reading the JSON (floorplans.load_14nm_stats: L2 by
#: L2_AREA_MULTIPLIER, the L3 slice by L3_CORRECTION_FACTOR / num_cores). The halo ring must be
#: sized on the PLACED macro, so the factor is computed on JSON area x this multiplier.
PLACED_MULTIPLIER = {'L2/Area': fp.L2_AREA_MULTIPLIER, 'Processor/Total L3s/Area': fp.L3_CORRECTION_FACTOR / 8.0}


def _halo_factor(area_mm2_14nm, halo_um, node='7nm'):
    """Area growth of a square macro by a ring ``halo_um`` wide at the placement node.

    The JSON holds 14 nm areas; the tiler scales LENGTHS by ``NODE_LENGTH_FACTORS[node]`` when it
    renders that node, so a physical halo at 7 nm is ``halo / factor`` in 14 nm microns.
    """
    from HotGauge.configuration import NODE_LENGTH_FACTORS
    h_mm = (halo_um / NODE_LENGTH_FACTORS[node]) / 1000.0
    side = area_mm2_14nm ** 0.5
    return ((side + 2.0 * h_mm) ** 2) / area_mm2_14nm


def apply_floorplan_overheads(stats, utilisation=1.0, overhead=0.0, halo_um=0.0, node='7nm'):
    """The book's overheads on the area JSON: logic x (1 + T)/U, macros + halo. In place; returns a report.

    Hierarchical keys (``X/Y/Area``) are handled bottom-up: a node's LEFTOVER (its area less its
    direct children) is logic and scales; its children scale by their own rule. The core total
    ``Area`` is the root. ``Total L3s/Area`` in the Processor section gets the halo too (the tiler
    makes it a per-core slice).
    """
    core = stats['Core']
    s = (1.0 + overhead) / utilisation
    keys = [k for k in core if k.endswith('/Area')]
    paths = {k: k[:-len('/Area')] for k in keys}
    children = {}
    for k, p in paths.items():
        parent = p.rsplit('/', 1)[0] if '/' in p else None
        children.setdefault(parent, []).append(k)
    old = dict(core)
    new = {}

    def visit(k):
        if k in new:
            return new[k]
        kids = children.get(paths[k], [])
        kid_new = sum(visit(c) for c in kids)
        kid_old = sum(old[c] for c in kids)
        if k in MACRO_UNITS:
            assert not kids, k
            placed = old[k] * PLACED_MULTIPLIER.get(k, 1.0)
            new[k] = old[k] * _halo_factor(placed, halo_um, node) if halo_um > 0 else old[k]
        else:
            leftover = max(old[k] - kid_old, 0.0)
            # `[!]` A parent whose children fill it to float residue (Instruction Scheduler:
            # 0.42 um^2 of 0.30 mm^2) must stay filled: scaled, the residue crosses the tiler's
            # 0.5 um^2 keep-the-parent threshold and a 34-block "iSched" family appears carrying
            # the scheduler's WHOLE McPAT power on 0.2 um^2 -- measured on the first u70 build.
            # Real leftovers (IF, LS, Rename, the core slab) are >= 0.005 mm^2.
            if leftover < 1e-4:
                leftover = 0.0
            new[k] = leftover * s + kid_new
        return new[k]
    for k in keys:
        visit(k)
    top_old = sum(old[c] for c in children.get(None, []))
    top_new = sum(new[c] for c in children.get(None, []))
    core_leftover = max(old['Area'] - top_old, 0.0)
    if core_leftover < 1e-4:
        core_leftover = 0.0
    new_core = core_leftover * s + top_new
    report = {'utilisation': utilisation, 'overhead': overhead, 'halo_um': halo_um, 'logic_scale': s,
              'core_area_mm2_before': old['Area'], 'core_area_mm2_after': new_core,
              'macros': {m: {'before': old[m], 'after': new[m]} for m in MACRO_UNITS if m in old}}
    for k in keys:
        core[k] = new[k]
    core['Area'] = new_core
    proc = stats['Processor']
    n_cores = round(proc['Total Cores/Area'] / old['Area'])
    l3 = proc['Total L3s/Area']
    l3_slice_placed = l3 * PLACED_MULTIPLIER['Processor/Total L3s/Area']   # what the tiler places per core
    l3_new = l3 * _halo_factor(l3_slice_placed, halo_um, node) if halo_um > 0 else l3
    report['macros']['Processor/Total L3s/Area'] = {'before': l3, 'after': l3_new}
    proc['Total L3s/Area'] = l3_new
    proc['Total Cores/Area'] = new_core * n_cores
    proc['Area'] += (new_core - old['Area']) * n_cores + (l3_new - l3)
    return report


def family_member(factor, cores, area_json, out_root, nodes=('7nm',), detail=3, force=False,
                  utilisation=1.0, overhead=0.0, halo_um=0.0, tag=None):
    out_dir = os.path.join(out_root, 'd1_exec{:g}{}'.format(factor, '_' + tag if tag else ''))
    os.makedirs(out_dir, exist_ok=True)
    dst_json = os.path.join(out_dir, 'area-{:g}.json'.format(factor))
    delta = scaled_area_json(area_json, factor, dst_json)
    if utilisation != 1.0 or overhead != 0.0 or halo_um > 0:
        stats = json.load(open(dst_json))
        rep = apply_floorplan_overheads(stats, utilisation, overhead, halo_um, node=nodes[0])
        with open(dst_json, 'w') as f:
            json.dump(stats, f, indent=1)
        meta_p = dst_json.replace('.json', '.meta.json')
        meta = json.load(open(meta_p))
        meta['overheads'] = rep
        with open(meta_p, 'w') as f:
            json.dump(meta, f, indent=1)
    raw = fp.load_14nm_stats(dst_json)
    split = fp.split_levels(raw)
    base = fp.get_base_floorplan(split)
    if detail >= 1:
        base = fp.add_pipeline(base, split[1])
    if detail >= 2:
        base = fp.add_level2(base, split[2])
    if detail >= 3:
        base = fp.add_level3(base, split[3])
    frmt = 'skylake{{node}}_{{suffix}}_{}_{{frmt}}.flp'.format(detail)
    written = generate(out_dir, frmt, base, cores, nodes=nodes, force=force)
    tmpl = os.path.join(out_dir, frmt.format(node=nodes[0], suffix='{}core'.format(cores),
                                             frmt='3D-ICE_template'))
    return out_dir, tmpl, validate(tmpl, cores), delta


def unit_areas(tmpl):
    flp = Floorplan.from_file(tmpl)
    out = {}
    for e in flp.elements:
        fam = e.name.rsplit('_', 1)[0] if e.name.rsplit('_', 1)[-1].isdigit() else e.name
        out.setdefault(fam, []).append(e.width * e.height / 1.0e6)
    return {k: (len(v), sum(v)) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--factors', type=float, nargs='+', default=[0.5, 0.25])
    ap.add_argument('--cores', type=int, default=34)
    ap.add_argument('--area-json', default=os.path.join(_HERE, 'floorplans',
                                                        'adjusted_14nm-area.json'))
    ap.add_argument('--out-root', default=os.path.join(_HERE, 'floorplans', 'outputs'))
    ap.add_argument('--reference', default=os.path.join(
        _HERE, 'floorplans', 'outputs', 'skylake7nm_34core_3_3D-ICE_template.flp'))
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--json-out', default=os.path.join(_REPO, 'docs', 'evidence',
                                                       'd1_exec_density_family.json'))
    ap.add_argument('--utilisation', type=float, default=1.0,
                    help='standard-cell utilisation U (book: 0.70); logic area x (1 + T)/U')
    ap.add_argument('--overhead', type=float, default=0.0,
                    help='scan / CTS / buffer / ECO overhead T on logic (book: 0.15)')
    ap.add_argument('--cache-halo-um', type=float, default=0.0,
                    help='keep-out ring around each SRAM macro, physical um at 7 nm (halo + channel)')
    ap.add_argument('--tag', default=None, help='suffix for the member directory (e.g. u70)')
    args = ap.parse_args()

    ref = unit_areas(args.reference)
    ref_area = sum(a for _n, a in ref.values())
    print('reference {}  {:.2f} mm^2'.format(os.path.basename(args.reference), ref_area))
    members = []
    for f in args.factors:
        out_dir, tmpl, v, delta = family_member(f, args.cores, args.area_json, args.out_root,
                                                force=args.force, utilisation=args.utilisation,
                                                overhead=args.overhead, halo_um=args.cache_halo_um,
                                                tag=args.tag)
        ua = unit_areas(tmpl)
        area = sum(a for _n, a in ua.values())
        status = 'OK' if (not v['missing'] and v['max_core_idx'] == args.cores - 1) else 'PROBLEM'
        print('  factor {:g}: {}  {} blocks  {:.2f} mm^2 ({:.3f}x)  [{}]'.format(
            f, os.path.relpath(out_dir, _REPO), v['blocks'], area, area / ref_area, status))
        rows = {}
        for fam in ('cALU', 'iALU', 'FPUs', 'AVXs', 'L2', 'L3', 'core_other', 'DCache'):
            if fam in ua and fam in ref:
                rows[fam] = {'ref_mm2': ref[fam][1], 'mm2': ua[fam][1],
                             'area_ratio': ua[fam][1] / ref[fam][1],
                             'density_multiplier_at_same_power': ref[fam][1] / ua[fam][1]}
                print('     {:<11s} {:7.3f} -> {:7.3f} mm^2  x{:.3f} area, x{:.2f} W/mm^2 at '
                      'the same power'.format(fam, ref[fam][1], ua[fam][1],
                                              rows[fam]['area_ratio'],
                                              rows[fam]['density_multiplier_at_same_power']))
        members.append({'factor': f, 'dir': os.path.relpath(out_dir, _REPO),
                        'template': os.path.relpath(tmpl, _REPO), 'blocks': v['blocks'],
                        'die_mm2': area, 'die_area_ratio': area / ref_area,
                        'delta_mm2_per_core_14nm': delta, 'units': rows, 'status': status})
    out = {'note': __doc__.strip(), 'reference': os.path.relpath(args.reference, _REPO),
           'reference_mm2': ref_area, 'scaled_units': list(EXEC_UNITS),
           'avx_follows_fpu': True, 'members': members,
           'INVARIANT': 'compare at matched die WATTS; --density = W / die_mm2 per member'}
    with open(args.json_out, 'w') as f:
        json.dump(out, f, indent=1)
    print('written: {}'.format(os.path.relpath(args.json_out, _REPO)))
    return 0 if all(m['status'] == 'OK' for m in members) else 1


if __name__ == '__main__':
    sys.exit(main())
