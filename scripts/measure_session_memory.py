"""Resident memory of one factorised 3D-ICE session, and what it costs to hold N of them.

Measurement harness, not a study. The catalogue re-run parallelises by system matrix, and each
concurrent stream holds its own factorisation -- so concurrency is bounded by memory, not by
cores, on the large dies. That bound was a guess; this measures it.

Usage
-----
    scripts/on_node.sh <jobid> python scripts/measure_session_memory.py \\
        --flp examples/floorplans/outputs/skylake7nm_34core_3_3D-ICE_template.flp \\
        --out results/session_mem/34core
"""
import os
import re
import sys
import math
import time
import json
import argparse
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'HotGauge'))

from HotGauge.thermal.die_stack import StackSpec, render_stack_text
from HotGauge.thermal.mr_array import (tile_grid, write_mr_floorplan, blocks_from_floorplan)
from HotGauge.thermal.ice_server import ICEServerSession
from HotGauge.utils.floorplan import Floorplan


def rss_kb(pid):
    """Peak and current resident set of a pid, from /proc. None if it has gone."""
    try:
        with open('/proc/{}/status'.format(pid)) as f:
            txt = f.read()
    except IOError:
        return None
    def field(name):
        m = re.search(r'^{}:\s+(\d+) kB'.format(name), txt, re.M)
        return int(m.group(1)) if m else None
    return {'rss_kb': field('VmRSS'), 'peak_kb': field('VmHWM')}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--flp', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pitch-um', type=float, default=500.0)
    ap.add_argument('--cell-um', type=float, default=50.0)
    ap.add_argument('--die-W', type=float, default=100.0)
    ap.add_argument('--node-GB', type=float, default=243.0,
                    help='node memory, for the concurrency estimate')
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    tmpl = open(a.flp).read()
    blocks = blocks_from_floorplan(Floorplan.from_file(a.flp, frmt='3D-ICE'))
    cw = int(math.ceil(max(b[0] + b[2] for b in blocks.values()) / a.cell_um) * a.cell_um)
    ch = int(math.ceil(max(b[1] + b[3] for b in blocks.values()) / a.cell_um) * a.cell_um)
    dp = {n: a.die_W / len(blocks) for n in blocks}
    open(os.path.join(a.out, 'IC.flp'), 'w').write(
        tmpl.format(powers={k: '{:.6f}'.format(v) for k, v in dp.items()}))

    tiles = tile_grid(cw, ch, pitch_um=a.pitch_um, cell_um=a.cell_um)
    write_mr_floorplan(os.path.join(a.out, 'MR.flp'), tiles)
    mt = open(os.path.join(a.out, 'MR.flp')).read()
    open(os.path.join(a.out, 'MR.flp'), 'w').write(
        mt.format(powers={t['name']: '0.0' for t in tiles}))

    spec = StackSpec(package='direct_die', mr_layer=True, mr_powered=True, cell_um=a.cell_um)
    stk = os.path.join(a.out, 'IC.stk')
    open(stk, 'w').write(render_stack_text(spec).format(
        flp_width=str(cw), flp_height=str(ch), flp_file='IC.flp', mr_flp_file='MR.flp',
        solver_config='   steady ;\n   initial temperature 300.0 ;',
        output_list='   Tflp (PROCESSOR_DIE, "die.temps", average, final ) ;\n'))

    t0 = time.time()
    with ICEServerSession(stk) as s:
        factor_s = time.time() - t0
        mem = rss_kb(s._proc.pid) if getattr(s, '_proc', None) else None
        names = s.element_names()
        t1 = time.time()
        s.solve_named(dict(dp))
        solve_s = time.time() - t1
        after = rss_kb(s._proc.pid) if getattr(s, '_proc', None) else None

    gb = (after or mem or {}).get('peak_kb')
    gb = gb / 1024.0 / 1024.0 if gb else None
    out = {'floorplan': os.path.basename(a.flp), 'blocks': len(blocks), 'tiles': len(tiles),
           'unknowns': (cw // int(a.cell_um)) * (ch // int(a.cell_um)) * 9,
           'elements': len(names), 'factorise_s': round(factor_s, 2),
           'solve_s': round(solve_s, 3),
           'rss_after_factor_kb': mem, 'rss_after_solve_kb': after,
           'peak_GB': round(gb, 3) if gb else None,
           'concurrent_sessions_in_node_GB': (int(a.node_GB / gb) if gb else None)}
    print(json.dumps(out, indent=1))
    with open(os.path.join(a.out, 'session_memory.json'), 'w') as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
