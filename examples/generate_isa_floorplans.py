#!/usr/bin/env python
"""Generate ARM-, RISC-V- and x86-class floorplans from the floorplan pack's published areas.

    python examples/generate_isa_floorplans.py --cores 34 --nodes 7nm

Uses the SHIPPED tiler (examples/generate_ncore_floorplans.py via --area-json). The tiler is not
ISA-specific and should not learn to be; this writes a re-weighted area JSON per variant and hands
it over, plus the one thing an area JSON cannot carry -- the vector multiple, which lives in
configuration.mcpat.DERIVED_UNITS and is now passed through --vector-multiple.

**That flag is the fix for a silent defect.** Until 28 Aug 2026 every variant declared a vector
multiple, this driver printed it, and nothing installed it: all six generated floorplans came out
with AVXs/FPUs = 1.981, the x86 value. See HotGauge/thermal/isa_floorplans.py for that, for the
pack-derived correction to the multiple itself (4.8x), and for the provenance of every number.

Every run prints the TARGET group mix beside the REALISED one, because the re-weighting inverts
somebody else's forward model in closed form and an inversion that is quietly wrong looks exactly
like one that is right.
"""
import os
import sys
import json
import argparse
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.isa_floorplans import (ISA_VARIANTS, write_variant_area_json,
                                             baseline_group_fractions)

_GROUPS = ('frontend', 'ooo', 'lsu', 'fpu', 'int', 'l2', 'residual')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--variants', nargs='+',
                    default=[k for k in ISA_VARIANTS if k != 'x86_skylake'],
                    choices=sorted(ISA_VARIANTS))
    ap.add_argument('--cores', type=int, nargs='+', default=[34])
    ap.add_argument('--nodes', nargs='+', default=['7nm'])
    ap.add_argument('--detail', type=int, default=3, choices=[0, 1, 2, 3])
    # The SHIPPED TILER's own default, and therefore the file every catalogue floorplan was
    # built from. This driver used to default to 14nm_unit_areas.json instead, which differs by
    # x1.40 on every unit except the ALUs (x0.565) -- so the ISA variants carried a different
    # unit mix from the baseline they were compared against, for no ISA-related reason.
    ap.add_argument('--base-json', default=os.path.join(_HERE, 'floorplans',
                                                        'adjusted_14nm-area.json'))
    ap.add_argument('--out-dir', default=os.path.join(_HERE, 'floorplans', 'isa_outputs'))
    ap.add_argument('--json-dir', default=os.path.join(_HERE, 'floorplans', 'isa_variants'))
    ap.add_argument('--tol', type=float, default=0.02,
                    help='largest acceptable relative error between the target group mix and '
                         'the one the tiler actually realises')
    args = ap.parse_args()

    os.makedirs(args.json_dir, exist_ok=True)
    os.makedirs(args.out_dir, exist_ok=True)
    written, bad = [], []

    base_mix = baseline_group_fractions(args.base_json)
    print('shipped baseline mix (what every catalogue result was measured on):')
    print('  ' + '  '.join('{} {:.3f}'.format(g, base_mix[g]) for g in _GROUPS))
    print('  core+L2 at 7nm: {:.3f} mm^2'.format(base_mix['_core_mm2_at_7nm']))

    for key in args.variants:
        v = ISA_VARIANTS[key]
        jpath = os.path.join(args.json_dir, '{}_unit_areas.json'.format(key))
        meta = write_variant_area_json(v, args.base_json, jpath)
        print('\n=== {} ==='.format(v.label))
        print('  area       : {}  (x{:.3f} of the baseline core) [{}]'.format(
            '{:.3f} mm^2'.format(v.core_area_mm2) if v.core_area_mm2 else 'derived',
            v.core_area_scale, v.area_provenance))
        print('  vector     : {} = {} bit -> {:.4f}x the base FPU'.format(
            v.vector_isa, v.vector_bits, v.vector_multiple))
        print('  caches     : {}   sram x{:.3f}'.format(v.cache_kb(), v.sram_scale))
        print('  power      : {}'.format('{:.3f} W/mm^2 published'.format(v.w_per_mm2)
                                         if v.w_per_mm2 else 'no published density'))
        print('  provenance : {}'.format(v.provenance))
        print('  assumptions: {}'.format(v.assumptions))
        print('  calibrated : False -- no area here was measured off silicon by us')
        if v.published_mix:
            tgt, got = meta['target_group_fractions'], meta['realised']
            print('  mix target : ' + '  '.join('{} {:.3f}'.format(g, tgt[g]) for g in _GROUPS))
            print('  mix realised: ' + '  '.join('{} {:.3f}'.format(g, got[g]) for g in _GROUPS))
            print('  worst group error: {:+.3%}   core+L2 {:.3f} mm^2 at 7nm'.format(
                meta['worst_group_error'], got['_core_mm2_at_7nm']))
            if meta['worst_group_error'] > args.tol:
                bad.append((key, meta['worst_group_error']))
                print('  ** MIX MISS ** above --tol {:.1%}'.format(args.tol))

        # Each variant gets its OWN directory and keeps the tiler's natural
        # skylake<node>_<n>core_<detail>_*.flp names. Every driver in the project resolves a
        # floorplan by that stem, so `--flp-dir <variant dir>` makes the variants usable
        # everywhere with NO driver change.
        vdir = os.path.join(args.out_dir, key)
        os.makedirs(vdir, exist_ok=True)
        cmd = [sys.executable, os.path.join(_HERE, 'generate_ncore_floorplans.py'),
               '--cores'] + [str(c) for c in args.cores] + \
              ['--nodes'] + list(args.nodes) + \
              ['--detail', str(args.detail), '--area-json', jpath,
               '--output-dir', vdir, '--force',
               '--vector-multiple', repr(v.vector_multiple)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print('  FAILED:\n{}'.format((r.stdout + r.stderr)[-1500:]))
            bad.append((key, 'tiler failed'))
            continue
        made = sorted(f for f in os.listdir(vdir) if f.endswith('.flp'))
        print('  wrote: {} -> {}'.format(len(made), os.path.relpath(vdir, _REPO)))
        written.append({'variant': key, 'area_json': jpath, 'dir': vdir, 'floorplans': made,
                        'meta': {k: x for k, x in meta.items() if k != 'realised'},
                        'realised_mix': meta.get('realised')})

    print('\n{} variant(s) generated.'.format(len(written)))
    if bad:
        print('PROBLEMS: {}'.format(bad))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
