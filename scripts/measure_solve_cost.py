"""Time one steady 3D-ICE solve on a two-die stack (silicon + powered photonic array).

Measurement harness, not a study. It exists because the whole Phase 0 schedule is priced off one
number -- what a solve costs cold versus warm -- and that number decides whether the catalogue
re-run is an overnight job or a two-month one. Recomputing it beats trusting a carried-over
estimate: the figure in docs/CODESIGN_PLAN.md was 40x and the measured answer is 169x end to end.

"cold" is this script's wall time: parse, assemble, factorise, solve. "solve-only" is 3D-ICE's own
post-factorisation timer, which is what a persistent 3D-ICE-Server session pays per solve once the
matrix is factorised. The ratio between them is what a working two-die session cache is worth.

Results land in docs/evidence/solve_cost_two_die.json.

Usage
-----
    scripts/on_node.sh <jobid> python scripts/measure_solve_cost.py \\
        --flp examples/floorplans/outputs/skylake7nm_34core_3_3D-ICE_template.flp \\
        --out results/solve_cost/34core --pitch-um 500

Run it under OMP_NUM_THREADS=1: SuperLU is threaded and will otherwise take the whole node,
which makes the timing a measurement of contention rather than of the solve.
"""
import os, re, sys, time, math, subprocess, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'HotGauge'))
from HotGauge.thermal.die_stack import StackSpec, render_stack_text
from HotGauge.thermal.ICE import ICE_DIR
from HotGauge.thermal.mr_array import (tile_grid, write_mr_floorplan, tile_powers_for_stack,
                                       blocks_from_floorplan)
from HotGauge.utils.floorplan import Floorplan

ap = argparse.ArgumentParser()
ap.add_argument('--flp', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--pitch-um', type=float, default=500.0)
ap.add_argument('--cell-um', type=float, default=50.0)
ap.add_argument('--die-W', type=float, default=100.0)
ap.add_argument('--no-mr', action='store_true',
                help='the convection control: 30 um of thermal grease where the array would be')
ap.add_argument('--burial-um', type=float, default=None,
                help='active-layer depth below the cooled surface; default is the direct-die 200 um')
a = ap.parse_args()

os.makedirs(a.out, exist_ok=True)
tmpl = open(a.flp).read()
blocks = blocks_from_floorplan(Floorplan.from_file(a.flp, frmt='3D-ICE'))
cw = int(math.ceil(max(b[0]+b[2] for b in blocks.values())/a.cell_um)*a.cell_um)
ch = int(math.ceil(max(b[1]+b[3] for b in blocks.values())/a.cell_um)*a.cell_um)
dp = {n: a.die_W/len(blocks) for n in blocks}
open(os.path.join(a.out, 'IC.flp'), 'w').write(
    tmpl.format(powers={k: '{:.6f}'.format(v) for k, v in dp.items()}))

tiles = tile_grid(cw, ch, pitch_um=a.pitch_um, cell_um=a.cell_um)
if not a.no_mr:
    write_mr_floorplan(os.path.join(a.out, 'MR.flp'), tiles)
    mt = open(os.path.join(a.out, 'MR.flp')).read()
    tp = tile_powers_for_stack({t['name']: 0.0 for t in tiles}, tiles)
    open(os.path.join(a.out, 'MR.flp'), 'w').write(
        mt.format(powers={k: '{:.6f}'.format(v) for k, v in tp.items()}))

_geom = {} if a.burial_um is None else {'source_depth_um': a.burial_um,
                                        'die_um': a.burial_um + 20.0 + 20.0}
spec = StackSpec(package='direct_die', mr_layer=not a.no_mr, mr_powered=not a.no_mr,
                 source_um=20.0, mr_material='GAAS', mr_um=30.0, cell_um=a.cell_um, **_geom)
open(os.path.join(a.out, 'IC.stk'), 'w').write(render_stack_text(spec).format(
    flp_width='{:.0f}'.format(cw), flp_height='{:.0f}'.format(ch),
    flp_file='IC.flp', mr_flp_file='MR.flp',
    solver_config='   steady ;\n   initial temperature 300.0 ;',
    output_list='   Tflp (PROCESSOR_DIE, "die.temps", maximum, final ) ;'))

t0 = time.time()
r = subprocess.run([os.path.join(ICE_DIR, 'bin', '3D-ICE-Emulator'), 'IC.stk'],
                   cwd=a.out, capture_output=True, text=True)
dt = time.time() - t0
print('{:<40} burial={:<7.1f} {:<7} tiles={:<6} {:>8.1f} s  rc={}'.format(
    os.path.basename(a.flp), spec.source_depth_um, 'TIM' if a.no_mr else 'MR',
    len(tiles) if not a.no_mr else 0, dt, r.returncode))
m = re.search(r'emulation took ([0-9.]+) sec', r.stdout + r.stderr)
print('   solve-only: {} s'.format(m.group(1) if m else '?'))
if r.returncode != 0:
    print((r.stdout + r.stderr)[-500:])
