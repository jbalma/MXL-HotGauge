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

#: 3D-ICE's grammar is section-ordered: materials, then layers, then dies, then the stack. A
#: declaration in the wrong section is a parse error ("unexpected keyword material, expecting
#: keyword die or keyword stack"), so the three pieces are inserted separately rather than as
#: one block next to the stack.
_MEM_MATERIAL = """
material BOND_MATERIAL :
   thermal conductivity     {bond_k} ;
   volumetric heat capacity 1.628e-12 ; // ASSUMPTION: taken as the solder TIM value

"""

_MEM_LAYER = """
layer BOND_LAYER :
   height {bond_um} ;
   material BOND_MATERIAL ;

"""

_MEM_DIE = """
/*********************** Stacked memory die (design D) ***********************/
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
            # 3D-ICE's own floorplan syntax, NOT the HotSpot tab-separated form: the two are
            # both called .flp and only one of them parses here.
            lines.append('{} :\n\tposition {:.3f}, {:.3f} ;\n\tdimension {:.3f}, {:.3f} ;\n'
                         '\tpower values 0.0;'.format(name, c * bw, r * bh, bw, bh))
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    LOGGER.info('wrote %d-bank memory floorplan (%.0f x %.0f um) to %s',
                len(names), width, height, out_path)
    return out_path, names


def render_stacked_memory_template(base_template, out_path, mem_flp_file,
                                   mem_die_um=DEFAULT_MEM_DIE_UM, bond_um=DEFAULT_BOND_UM,
                                   bond_conductivity=DEFAULT_BOND_CONDUCTIVITY,
                                   n_dies=1, cell_um=None):
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

    # Each declaration goes in its own section: 3D-ICE parses materials, then layers, then
    # dies, then the stack, and rejects anything out of order.
    def _insert_before(text, marker, block, what):
        if marker not in text:
            raise ValueError('{} has no {!r} section to insert the {} into'
                             .format(base_template, marker, what))
        return text.replace(marker, block + marker, 1)

    stack = _insert_before(stack, '/*********************** Heat Sink ***********************/',
                           _MEM_MATERIAL.format(bond_k=bond_conductivity), 'bond material')
    stack = _insert_before(stack, '/*********************** Dies ***********************/',
                           _MEM_LAYER.format(bond_um=bond_um), 'bond layer')
    stack = _insert_before(stack, '/*********************** Stack ***********************/',
                           _MEM_DIE.format(mem_upper=rest * 0.5, mem_source=source_um,
                                           mem_lower=rest * 0.5), 'memory die')

    # Memory ABOVE logic: it appears earlier in the stack list, which 3D-ICE reads top-down.
    #
    # n_dies > 1 is the case the HIR thermal chapter says actually matters: "HBMs are generally
    # challenging to cool due to the LARGE STACK THERMAL RESISTANCE and thermal coupling from
    # high power logic chips close by, which might have higher operating temperature limits
    # than that of HBMs" (HIR 2023 ch.20 s.2.10). A single thin bonded die is the most
    # favourable memory geometry there is; an 8-high stack puts seven more dies and seven more
    # bond layers between the hot one and the sink, and each bond is a thermal wall.
    if n_dies < 1:
        raise ValueError('n_dies must be >= 1, got {!r}'.format(n_dies))
    # One floorplan per die, because every die needs DISTINCT block names. Sharing one
    # floorplan would put MEM_r0c0 on every layer, and merging the Tflp files by name would
    # then silently keep whichever was read last -- seven dies' temperatures discarded without
    # a word.
    flps = [mem_flp_file] if isinstance(mem_flp_file, str) else list(mem_flp_file)
    if len(flps) != n_dies:
        raise ValueError('need one floorplan per die: {} dies, {} floorplans'
                         .format(n_dies, len(flps)))
    old = [l for l in stack.split('\n') if l.strip().startswith('die PROCESSOR_DIE')][0]
    dies = []
    for i, flp in enumerate(flps):
        # Numbered from the sink downward, so MEMORY_DIE0 is the coolest and the highest index
        # sits directly on the logic -- which is the one that gets cooked.
        dies.append('   die MEMORY_DIE{} MEM floorplan "{}";\n'
                    '   layer BOND{} BOND_LAYER ;\n'.format(i, os.path.abspath(flp), i))
    stack = stack.replace(old, ''.join(dies) + old, 1)

    if cell_um is not None:
        # Grid coarsening, needed for deep stacks and not free.
        #
        # A 9-die stack at the template's 50 um cells is ~1.7M unknowns and SuperLU 4.3 cannot
        # factorise it: "Can't expand MemType 0: jcol 1710392 / SuperLu factorization error".
        # Unknowns scale as 1/cell^2, so 100 um cells cut the problem 4x and it fits. This is a
        # capacity limit of the solver, not of the model -- it is the case the deferred cuDSS
        # work in docs/GAMEPLAN.md exists for.
        #
        # What it costs: a coarser grid smooths lateral gradients, so ABSOLUTE peak temperatures
        # on small blocks are understated. The questions a deep-stack screen asks -- which layer
        # binds, and how wide the memory plateau is -- are far less sensitive to that than a peak
        # temperature is, but a coarsened run must not be compared against a 50 um run's peak.
        n = 0
        out_lines = []
        for line in stack.split('\n'):
            if line.strip().startswith('cell length'):
                indent = line[:len(line) - len(line.lstrip())]
                out_lines.append('{}cell length {:g}, width {:g}; // COARSENED for a deep stack'
                                 .format(indent, cell_um, cell_um))
                n += 1
            else:
                out_lines.append(line)
        if not n:
            raise ValueError('{} has no "cell length" line to coarsen'.format(base_template))
        stack = '\n'.join(out_lines)

    with open(out_path, 'w') as f:
        f.write(stack)
    LOGGER.info('wrote stacked-memory template to %s (%d memory die(s) of %g um above %g um '
                'bond%s)', out_path, n_dies, mem_die_um, bond_um,
                '' if cell_um is None else ', {:g} um cells'.format(cell_um))
    return out_path


def memory_stack_floorplans(logic_flp, out_dir, n_dies=1, n_x=4, n_y=4):
    """One prefixed floorplan per memory die: ``(paths, names_by_die, all_names)``.

    Distinct names per die are not cosmetic. 3D-ICE reports temperatures per die, and the
    reader merges them by name -- shared names would mean six of an eight-high stack vanish
    into the seventh without any error.
    """
    paths, by_die, every = [], [], []
    for i in range(n_dies):
        p = os.path.join(out_dir, 'memory{}.flp'.format(i))
        path, names = memory_floorplan(logic_flp, p, n_x=n_x, n_y=n_y,
                                       name_prefix='MEM{}'.format(i))
        paths.append(path)
        by_die.append(names)
        every.extend(names)
    return paths, by_die, every


def memory_output_instructions(n_dies=1):
    """Tflp instruction per memory die: a die with no output instruction reports nothing.

    Returned in stack order (die 0 nearest the sink), and each writes its own file so the
    reader never has to assume an ordering across dies.
    """
    return ['Tflp (MEMORY_DIE{0}, "memory{0}_elements.temps", average, final ) ;'.format(i)
            for i in range(n_dies)]


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
