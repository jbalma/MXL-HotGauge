#!/usr/bin/env python
"""X4 (§P0.27.4): split the reference die into the gen-3 stack's two floorplans.

    python examples/split_storage_die.py            # -> examples/floorplans/outputs/gen3_stack/

``storage_template.flp``  the L2/L3 blocks at their reference positions with their
                          ``{powers[NAME]}`` placeholders -- the storage die (X4 puts it above
                          the processor die on a bond; the array cools it first).
``compute_template.flp``  the reference with those blocks renamed ``DARK_<name>`` at a literal
                          0 W -- the vacated cache area stays on the processor die as dark
                          silicon (3D-ICE needs every die on one footprint, and the outer cores'
                          caches define the die's edge), so it conducts and dissipates nothing.

Every other block keeps its name, so the trace, the name map, the leakage feedback, the
planner's zone patterns (``^(L2|L3)``) and the tile wiring all work by name across the two
dies. The union of the two is the reference die, which is what the die-power accounting
(``die_power_of_trace``) must keep using. TSV keep-outs are not modelled: an unpowered block
changes nothing in a solve whose blocks are already placed.
"""
import os
import re
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_BLOCK = re.compile(r'^(\S+)\s*:\s*\n(\s*position[^\n]*\n\s*dimension[^\n]*\n)\s*power values ([^;]*);', re.M)
STORAGE = re.compile(r'^(L2|L3)_\d+$')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reference', default=os.path.join(_HERE, 'floorplans', 'outputs', 'skylake7nm_34core_3_3D-ICE_template.flp'))
    ap.add_argument('--out-dir', default=os.path.join(_HERE, 'floorplans', 'outputs', 'gen3_stack'))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    text = open(args.reference).read()
    comp, stor, n_c, n_s, a_c, a_s = [], [], 0, 0, 0.0, 0.0
    for m in _BLOCK.finditer(text):
        name, geom, pw = m.group(1), m.group(2), m.group(3).strip()
        dims = re.search(r'dimension\s+([\d.]+)\s*,\s*([\d.]+)', geom)
        area = float(dims.group(1)) * float(dims.group(2)) * 1e-6
        if STORAGE.match(name):
            stor.append('{} :\n{}\tpower values {};'.format(name, geom, pw)); n_s += 1; a_s += area
            comp.append('DARK_{} :\n{}\tpower values 0.0;'.format(name, geom))
        else:
            comp.append('{} :\n{}\tpower values {};'.format(name, geom, pw)); n_c += 1; a_c += area
    if not stor:
        raise SystemExit('no L2/L3 blocks found in {}'.format(args.reference))
    cp = os.path.join(args.out_dir, 'compute_template.flp')
    sp = os.path.join(args.out_dir, 'storage_template.flp')
    open(cp, 'w').write('\n'.join(comp) + '\n')
    open(sp, 'w').write('\n'.join(stor) + '\n')
    meta = {'reference': os.path.relpath(args.reference, _REPO), 'compute_template': os.path.relpath(cp, _REPO),
            'storage_template': os.path.relpath(sp, _REPO), 'n_compute_blocks': n_c, 'n_storage_blocks': n_s,
            'n_dark_blocks_on_compute_die': n_s, 'compute_powered_mm2': a_c, 'storage_mm2': a_s,
            'storage_share_of_die': a_s / (a_c + a_s), 'storage_pattern': STORAGE.pattern,
            'note': 'the union is the reference die; account die power on the reference floorplan'}
    json.dump(meta, open(os.path.join(args.out_dir, 'split.json'), 'w'), indent=1)
    print('compute: {} powered blocks + {} dark ({:.2f} mm^2 powered); storage: {} blocks, {:.2f} mm^2 ({:.1%} of the die)'
          .format(n_c, n_s, a_c, n_s, a_s, meta['storage_share_of_die']))
    print('written:', os.path.relpath(args.out_dir, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
