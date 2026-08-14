"""3D stacks: put a memory die in the heat path and give it its own temperature limit.

Why this exists (design D in docs/DESIGN_STUDY_PLAN.md)
------------------------------------------------------
Every result so far is on a single logic die whose constraint is a ~100 C spec limit, and on
that die microrefrigeration is weak as a clock lever because the thermal peak is degenerate --
15 blocks within the device's lift of each other (``examples/thermal_tiers.py``). Stacked memory
changes the problem in two ways that are structural rather than incremental:

1. **A lower, different limit.** DRAM is refresh-limited, not delay-limited. The conventional
   JEDEC breakpoint is 85 C, above which retention halves and the part must refresh twice as
   often -- which costs power, which raises temperature. That is a positive feedback like
   leakage, on a *different* structure, with a limit 15 K below the logic's.
2. **A different degeneracy.** A memory array's hot zone is set by where the logic underneath
   it is hot plus where the banks are active. There is no reason for it to be a plateau of
   identical replicated units the way a homogeneous core array is.

So the question design D asks is not "is MR better here" but "does the binding constraint move
to a structure MR can actually address cheaply".

Geometry
--------
The memory die is placed **above** the logic die, between it and the heat sink. That is the
thermally hostile arrangement -- the memory sits in the logic's heat path -- and it is the one
worth studying: it is what logic-on-bottom 3D stacking does, and if MR helps anywhere it is
where a low-limit structure is being cooked by something else's waste heat. It also puts the
memory where photonic cooling can physically reach it, since the laser needs line of sight from
the top of the stack.

The alternative (memory beside the logic on an interposer, i.e. 2.5D HBM) is thermally much
easier and is not what this models.

What is assumed, and how firmly
-------------------------------
* Layer thicknesses: HBM dies are thinned to ~50 um and bonded with a few um of dielectric.
  Values here are parameters, not measurements.
* The 85 C refresh breakpoint is the JEDEC convention for the extended temperature range;
  ``HotGauge.power.dram`` models it. **It needs a real datasheet before any quoted number.**
* 3D-ICE requires every die in a stack to share one footprint, so the memory floorplan is
  generated to the logic die's bounding box. Real stacked memory need not match the logic die's
  area; that is a simplification of the geometry, not of the physics.
"""

import os
import math
import logging

LOGGER = logging.getLogger(__name__)

#: Thinned memory die thickness [um]. HBM dies are thinned aggressively so a stack fits in the
#: package z-budget; 50 um is the usual figure quoted for 8-high stacks.
DEFAULT_MEM_DIE_UM = 50.0

#: Die-to-die bond thickness [um] for hybrid/direct bonding. Thin, and thermally significant
#: precisely because everything the logic dissipates crosses it.
DEFAULT_BOND_UM = 5.0

#: Bond-layer conductivity [W/(um*K)] in 3D-ICE units. Direct copper-oxide hybrid bonding is
#: close to silicon; older microbump+underfill is far worse. The default is the pessimistic
#: microbump-ish value, because assuming the good one flatters every stacked result.
DEFAULT_BOND_CONDUCTIVITY = 0.5e-4

_MEM_DIE_BLOCK = """
/*********************** Stacked memory die (design D) ***********************/
material BOND_MATERIAL :
   thermal conductivity     {bond_k} ;
   volumetric heat capacity 1.628e-12 ; // ASSUMPTION: taken as the solder TIM value

layer BOND_LAYER :
   height {bond_um} ;
   material BOND_MATERIAL ;

die MEM :
   layer  {mem_upper} SILICON ;
   source {mem_source} SILICON ;
   layer  {mem_lower} SILICON ;
"""


def memory_floorplan(logic_flp, out_path, n_x=4, n_y=4, name_prefix='MEM'):
    """Generate a memory floorplan tiling the logic die's footprint with ``n_x * n_y`` banks.

    3D-ICE requires the dies in a stack to share a footprint, so the memory die is generated to
    the logic die's bounding box rather than to a realistic DRAM die size. Blocks are named
    ``MEM_r{row}c{col}`` so they are trivially separable from logic blocks downstream -- the
    temperature limit, the MR policy and the reporting all need to tell the two apart.

    Returns ``(path, block_names)``.
    """
    from HotGauge.thermal.ICE import Floorplan
    flp = logic_flp if hasattr(logic_flp, 'elements') else Floorplan.from_file(logic_flp)
    width, height = float(flp.maxx), float(flp.maxy)
    # Match the rounding ICESim applies to the chip dimensions, so the banks fill the die
    # exactly rather than leaving a sliver 3D-ICE would treat as unpopulated.
    width = math.ceil(width / 100.0) * 100
    height = math.ceil(height / 100.0) * 100

    bw, bh = width / float(n_x), height / float(n_y)
    lines, names = [], []
    for r in range(n_y):
        for c in range(n_x):
            name = '{}_r{}c{}'.format(name_prefix, r, c)
            names.append(name)
            lines.append('{}\t{:.1f}\t{:.1f}\t{:.1f}\t{:.1f}'.format(
                name, bw, bh, c * bw, r * bh))
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    LOGGER.info('wrote %d-bank memory floorplan (%.0f x %.0f um) to %s',
                len(names), width, height, out_path)
    return out_path, names


def render_stacked_memory_template(base_template, out_path, mem_flp_file,
                                   mem_die_um=DEFAULT_MEM_DIE_UM, bond_um=DEFAULT_BOND_UM,
                                   bond_conductivity=DEFAULT_BOND_CONDUCTIVITY):
    """Insert a memory die above the logic die and return a stack template.

    The memory floorplan path is baked in as an absolute path while the logic placeholders
    (``{flp_file}``, ``{flp_width}`` ...) are left untouched, so the result is still a template
    that ``render_stack_with_sink`` and the stock ``ICESim`` machinery can fill exactly as they
    fill a single-die one. Nothing in stock HotGauge needs to know a second die exists.
    """
    with open(base_template) as f:
        stack = f.read()

    if 'die MEM :' in stack:
        raise ValueError('{} already contains a memory die'.format(base_template))
    if 'die PROCESSOR_DIE' not in stack:
        raise ValueError('{} has no PROCESSOR_DIE line to stack onto'.format(base_template))

    # Split the memory die's silicon around its source layer, which is where 3D-ICE puts the
    # power and reports the temperatures.
    source_um = max(10.0, mem_die_um * 0.2)
    rest = max(mem_die_um - source_um, 2.0)
    block = _MEM_DIE_BLOCK.format(bond_k=bond_conductivity, bond_um=bond_um,
                                  mem_upper=rest * 0.5, mem_source=source_um,
                                  mem_lower=rest * 0.5)
    # Definitions must precede the stack section.
    stack = stack.replace('/*********************** Stack ***********************/',
                          block + '\n/*********************** Stack ***********************/', 1)

    mem_abs = os.path.abspath(mem_flp_file)
    # Memory ABOVE logic: it appears earlier in the stack list, which 3D-ICE reads top-down.
    old = [l for l in stack.split('\n') if l.strip().startswith('die PROCESSOR_DIE')][0]
    new = ('   die MEMORY_DIE MEM floorplan "{}";\n'
           '   layer BOND BOND_LAYER ;\n'.format(mem_abs)) + old
    stack = stack.replace(old, new, 1)

    with open(out_path, 'w') as f:
        f.write(stack)
    LOGGER.info('wrote stacked-memory template to %s (memory %g um above %g um bond)',
                out_path, mem_die_um, bond_um)
    return out_path


def split_layer_temps(temps, mem_prefix='MEM'):
    """Separate a solved field into ``(logic, memory)`` by block name.

    The two layers have different limits -- the logic's spec point and the memory's refresh
    breakpoint -- so anything that reduces a field to "the peak" has to know which peak it
    means. Reporting one number across both layers is how a memory-limited part would get
    called thermally fine.
    """
    logic = {k: v for k, v in temps.items() if not k.startswith(mem_prefix)}
    memory = {k: v for k, v in temps.items() if k.startswith(mem_prefix)}
    return logic, memory
