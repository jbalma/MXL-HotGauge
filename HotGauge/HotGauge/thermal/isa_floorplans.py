"""ARM- and RISC-V-class core floorplans, rebuilt on published block areas.

Why this exists
---------------
The project's stated goal is core designs across **multiple ISAs**, and for most of its history
every floorplan in it was one microarchitecture: the Sniper/McPAT Skylake-class core.

The first cut of this module (27 August 2026) closed that gap with *press ratios* -- "V1 is ~70%
larger than N1", "P670 reaches A78 performance in half the area" -- because the repository held
zero ARM or RISC-V die shots and no published block areas at all. It said so, and it set
``calibrated = False`` on everything.

**This is the rebuild on the floorplan pack** (28 August 2026), which supplies 165 rows of
published block areas including the only fully decomposed core available anywhere in it, and 11
ARM plus 3 RISC-V annotated floorplans. Three things changed, and each is a correction rather
than an addition.

1. The vector multiple was never applied
----------------------------------------
``ISAVariant.vector_multiple`` was declared per variant, returned in the re-weighting metadata,
and printed by the generator -- and **nothing ever installed it**. ``AVX_512_AREA_VS_FPU`` is a
module constant baked into ``configuration.mcpat.DERIVED_UNITS`` at import, and the generator
handed the tiler only a re-weighted area JSON, which cannot reach it. Measured on the six
floorplans that were on disk: ``AVXs/FPUs = 1.981`` in **every one of them**, x86 and ARM and
RISC-V alike.

So the axis this module's own docstring called "the largest single lever in the unit mix" was
never varied. That matters for how the 27 August result is read: the registered prediction's
second clause failed with the gap "ordered by nothing", and
``docs/evidence/isa_benefit_prediction_test.json`` attributes that to uniform scaling preserving
the unit mix. True, but not the cause -- the cause is that every variant carried the x86 AVX-512
accelerator at full size. ``examples/generate_ncore_floorplans.py --vector-multiple`` now installs
it, and ``test_isa_floorplans.py`` asserts the generated floorplans differ.

2. The vector multiple itself was 4.8x too large, and the pack says so
-----------------------------------------------------------------------
``configuration.mcpat`` carries an explicit ``# HACK: Fudge the AVX ratio to match die photos``
targeting ``DESIRED_RATIO = 0.1`` of total die, which it hits: the AVX blocks are 10.5% of the
shipped 34-core die. The pack's Golden Cove plate disagrees. Its FMA EUs on ports 0 and 1 are
**0.288 mm^2 of a 7.123 mm^2 core -- 4.04%**, and the whole FP cluster including them is
0.986 mm^2, 13.8%. Against the rest of the FP cluster the FMA hardware is
``0.288 / (0.986 - 0.288) = 0.413x``, where the shipped constant is **1.981x**.

``GOLDEN_COVE_VECTOR_MULTIPLE`` is that 0.413, and every variant's vector multiple is now
0.413 scaled linearly by total vector width against AVX-512's 1024 bit. That is an assumption --
area linear in width at a fixed pipeline count -- but it is arithmetic on published widths rather
than the judgement calls the first cut used.

**The shipped baseline is deliberately NOT changed.** Every catalogue result in this repository
rests on the 1.981 floorplan, and silently recalibrating it would invalidate the back catalogue
for the sake of one number. The corrected core enters as a *variant*, ``x86_golden_cove``, so the
size of the correction is measurable rather than asserted.

3. The variants were built from a different base file than the baseline
------------------------------------------------------------------------
``examples/floorplans/`` holds two area JSONs. The shipped tiler defaults to
``adjusted_14nm-area.json``; ``generate_isa_floorplans.py`` defaulted to ``14nm_unit_areas.json``.
They are not the same file -- the adjusted one multiplies every unit by 1.40 except the ALUs,
which it multiplies by 0.565, while leaving ``Core/Area`` alone. So every ISA variant carried a
different unit mix from the baseline it was being compared against, for a reason that had nothing
to do with any ISA: the baseline's unallocated residual is 22.1% of its core and the variants'
was 34.7%. Both drivers now default to ``adjusted_14nm-area.json``, and a test asserts the
baseline regenerates **byte-identically** through the new ``--vector-multiple`` path.

4. The unit MIX disagrees with the one published measurement, badly
--------------------------------------------------------------------
Grouping the McPAT units into Golden Cove's six published blocks and comparing shares of the
per-core area (both excluding L3), against the file the catalogue actually rests on:

===========  ==========  =============  ======
group        our McPAT   Golden Cove    ratio
===========  ==========  =============  ======
frontend     10.40%       23.02%         0.45
ooo           5.13%       18.56%         0.28
load/store   12.64%       14.47%         0.87
FP + vector  22.23%       13.84%         1.61
integer       2.31%        5.64%         0.41
L2           25.21%       23.11%         1.09
**residual** **22.08%**   **1.35%**      **16.4**
===========  ==========  =============  ======

The residual is the headline. McPAT reports a ``Core/Area`` its own itemised children fall well
short of, and the shipped tiler renders that shortfall as **one featureless ``core_other`` slab
per core** -- 15.85 mm^2 of a 101 mm^2 die, the second largest block on it. A real core,
transcribed independently from the same plate as its own total, closes to 1.35%. Every floorplan
metric this project has validated was measured on a die a fifth of whose area is a single uniform
block, and that is worth knowing whether or not it changes the answer. ``x86_golden_cove`` is the
same core with the published mix and it is in the sweep to find out.

A note on the decode argument, which this cuts both ways on
------------------------------------------------------------
``DECODE_FRACTION_OF_CORE`` -- 3.34% -- is the number this module has used since it was written to
retire "x86 decode is complex" as an architecture argument. It is a **McPAT output**, and the one
published decomposition does not corroborate it: Golden Cove's frontend block (branch prediction,
decode, the micro-op ROM, the L1I and its control) is **23.0% of the core** against McPAT's 10.4%,
and the L1I inside it prices at roughly 2.3% of that block. The pack cannot isolate the decoder --
the plate labels one block for the whole frontend -- so it does not restore the decode argument.
What it does is remove the *model's* authority for dismissing it, and the honest statement is now
"the frontend is a fifth to a quarter of a real x86 core and the pack does not separate the
decoder from the rest of it".

Absolute size, iso-node
------------------------
Our modelled core is **2.116 mm^2** of core + 512 KB L2 at 7 nm. The pack publishes AMD Zen 2 at
**3.54 mm^2** for core + 512 KB L2 on TSMC N7 -- same node class, same L2 capacity, **1.67x**.
Golden Cove is 7.123 mm^2 with a 1.25 MB L2 on Intel 7. So the baseline core is around 60% of a
real one at iso-node, which is why every ARM ratio in the first cut came out below 1.0 and why
``arm_v1`` is now **above** it.

What each variant is now, and what it still is not
----------------------------------------------------
* **Absolute core area**: published, from ``block_areas.csv``, for every variant that has one --
  Neoverse V1 2.52 mm^2, Neoverse N1 1.15-1.4 mm^2, Zen 2 3.54 mm^2, Golden Cove 7.123 mm^2, all
  iso-node at 7 nm. ``arm_a64fx`` and ``riscv_xiangshan`` have no published area anywhere in the
  pack and keep the derived route.
* **Mix**: Golden Cove's published six-group decomposition, adjusted for the variant's own cache
  capacities and vector width. **No ARM or RISC-V core decomposition is published in the pack** --
  the three RISC-V layouts are unit-coloured renderings with no printed areas, and the Arm rows
  are core-plus-L2 totals. So the mix is an x86 core's, moved on the two axes that are published
  per variant. That is stated rather than hidden, and it is still a long way better than McPAT's
  mix, which disagrees with the one published measurement by up to 4.5x per group.
* **Power**: the pack gives per-core W/mm^2 for six Arm rows and a die-level anchor for Tesla D1.
  ``w_per_mm2`` carries them. It does **not** give a per-block power split for any part, so the
  intra-core power shape is still the Skylake trace redistributed by area. An ISA comparison run
  at each part's own published density is an activity comparison at the die level and a geometry
  comparison within the core, and it must not be quoted as more than that.
* ``calibrated`` remains **False** on every variant, and the word keeps its old meaning: nothing
  here was measured off silicon by us. ``area_provenance`` is the field that says what each area
  actually is.

The licensing constraint
------------------------
The pack's plates are SemiAnalysis subscriber content and third-party die shots. Numbers derived
from them are fine to publish; the images are internal reference only and must not be embedded in
the handbook artifact. See ``pack_areas``.
"""
import os
import sys
import copy
import json
import logging
import tempfile

from HotGauge.thermal import pack_areas

LOGGER = logging.getLogger(__name__)

#: Instruction decoder as a fraction of core area in the shipped model. Recorded because it is
#: the number that kills the naive ISA argument, and it should be quoted whenever someone
#: proposes one.
DECODE_FRACTION_OF_CORE = 0.173040 / 5.18282        # 3.34%

#: The AVX-512 accelerator's area as a multiple of the base FPU **in the shipped model**
#: (``configuration.mcpat.AVX_512_AREA_VS_FPU``, after its own documented fudge factor). Kept
#: under its original name because the shipped baseline still uses it and the back catalogue
#: rests on it.
X86_VECTOR_MULTIPLE = 1.9810072416144315

#: The same quantity measured off the pack's Golden Cove decomposition: FMA EUs on ports 0 and 1
#: (0.288 mm^2) against the rest of the FP cluster (0.986 - 0.288 = 0.698 mm^2). **4.8x smaller
#: than the shipped constant.** This is what the variants below use.
GOLDEN_COVE_VECTOR_MULTIPLE = 0.288 / (0.986 - 0.288)     # 0.4126

#: Total vector datapath width of the x86 baseline, in bits: AVX-512 with two 512-bit FMA units
#: on ports 0 and 1, which is what the Golden Cove plate labels. Variants scale
#: ``GOLDEN_COVE_VECTOR_MULTIPLE`` linearly against this.
X86_VECTOR_BITS = 2 * 512

#: Parent/child slack below this fraction of the parent is float noise in the shipped area data
#: and is clamped to zero before the tiler sees it. Above it, the slack is modelled area the
#: tiler legitimately places as its own block. See ``_repair_parent_coverage``.
TINY_SLACK_FRACTION = 1e-4

#: 7 nm area factor from ``configuration.mcpat.NODE_AREA_FACTORS``. The unit areas are 14 nm and
#: the published comparisons are 7 nm, so one of the two has to move and this is what moves it.
NODE_AREA_FACTOR_7NM = 0.25

#: The baseline model core: core + 512 KB L2 at 7 nm, excluding its L3 share, from
#: ``examples/floorplans/adjusted_14nm-area.json`` -- **the file the shipped tiler defaults to and
#: therefore the one every catalogue floorplan was built from**, not the ``14nm_unit_areas.json``
#: the ISA generator used to default to. Through the shipped ``load_14nm_stats``. Written
#: down rather than computed at import so this module does not need ``examples/`` on the path to
#: be imported; ``test_isa_floorplans.py`` asserts it still matches what the tiler produces.
BASELINE_CORE_MM2_7NM = 2.116150

#: Die-level power density anchor for x86, from the pack: Tesla D1, 400 W over 645 mm^2 on TSMC
#: N7, the only clean whole-die area-and-power pair in the file. It is not an x86 part -- nothing
#: in the pack gives an x86 core its own power -- so it stands in as a same-node logic-die
#: density, and it lands within 4% of the 0.60 W/mm^2 the catalogue has been sweeping at anyway.
DIE_LEVEL_W_PER_MM2_N7 = 0.620

#: The core count the shipped tiler passes to ``load_14nm_stats``, which sets the per-core L3
#: share. ``examples/generate_ncore_floorplans.py`` calls it with the default **8** whatever
#: ``--cores`` says, so a 34-core die carries L3 sized for an 8-core one -- 4.25x the model's own
#: ``Total L3s``. That is a pre-existing property of the shipped baseline and every catalogue
#: result rests on it, so it is recorded here and deliberately NOT changed: what matters for this
#: module is that the re-weighting inverts the same forward model the tiler will run, and it does
#: that by using the same number.
TILER_NUM_CORES = 8

_PACK_BLOCK_TO_GROUP = {
    'frontend_branch_decode_l1i_op': 'frontend',
    'ooo_sched_and_retire': 'ooo',
    'load_store_with_l1d': 'lsu',
    'fpu_incl_fma_eus': 'fpu',
    'integer_execution': 'int',
    'l2_cache': 'l2',
}

#: McPAT subtree roots that make up each published group. This mapping is the point of contact
#: between a model's unit tree and a plate's labelled blocks, so it is written once here rather
#: than re-derived per caller.
#:
#: Note where the register files go: **into ``ooo``**, not into ``fpu`` and ``int``. The plate
#: draws all three register-file boxes on the out-of-order scheduling and retirement field, with
#: the FPU and integer clusters below them -- see ``pack_areas.NESTED_BLOCKS``, which records the
#: same reading. Their names in ``block_areas.csv`` point at the other parent and are misleading.
GOLDEN_COVE_GROUPS = {
    'frontend': ('Instruction Fetch Unit',),
    'ooo': ('Execution Unit/Instruction Scheduler', 'Renaming Unit',
            'Execution Unit/Results Broadcast Bus', 'Execution Unit/Register Files'),
    'lsu': ('Load Store Unit', 'Memory Management Unit'),
    'fpu': ('Execution Unit/Floating Point Units',),
    'int': ('Execution Unit/Complex ALUs', 'Execution Unit/Integer ALUs'),
    'l2': ('L2',),
}

#: L2 data-array density from the pack's own Golden Cove row: ``l2_sram_block_256kb`` is
#: 0.151 mm^2 for 256 KB. Published, on the same plate and the same node as everything else here.
L2_ARRAY_MM2_PER_KB = 0.151 / 256.0                # 5.898e-4

#: How much less dense an L1 array is than an L2 array, per bit. **ASSUMED**: an L1 is
#: multi-ported, latency-critical and built from faster, larger cells, and 1.5-3x is the range
#: usually quoted. ``l1_sensitivity()`` prices a disagreement over 1x to 4x.
#:
#: Corroborated from the other side by the pack's own Arm rows: Neoverse N1 is 1.15 mm^2 with a
#: 512 KB L2 and 1.4 mm^2 with 1 MB, so its **marginal** L2 costs 0.25 mm^2 per 512 KB =
#: 4.88e-4 mm^2/KB at 7 nm -- within 20% of the Golden Cove array density used here, on a
#: different vendor and node. Two independent published numbers agreeing to that tolerance is
#: what makes this an anchor rather than a guess.
L1_DENSITY_PENALTY = 2.0
L1_MM2_PER_KB = L2_ARRAY_MM2_PER_KB * L1_DENSITY_PENALTY

#: Largest share of its group an L1 cache may take before the construction is refused. A cache
#: bigger than this means the group fraction and the cache capacity are describing different
#: machines, and continuing would produce a floorplan whose frontend is mostly SRAM.
MAX_L1_SHARE_OF_GROUP = 0.45

#: Golden Cove's own residual -- routing and glue the plate does not itemise -- as a fraction of
#: the core. Held constant across variants rather than let float, because it is a property of how
#: completely a core was transcribed, not of the microarchitecture.
PUBLISHED_RESIDUAL_FRACTION = (7.123 - 7.027) / 7.123      # 1.35%

#: SRAM-bearing units, kept for callers of the legacy re-weighting path. They are scaled together
#: because they are one design decision (cache capacity per core), not three.
SRAM_UNITS = ('Instruction Fetch Unit/Instruction Cache/Area',
              'Load Store Unit/Data Cache/Area',
              'L2/Area')

#: Per-core cache capacities [KB].
#:
#: ``baseline`` is this project's own McPAT configuration (``leakage_calibration/mcpat_T330.xml``:
#: icache 32768, dcache 32768, L2 524288), so it is not an estimate. ``golden_cove`` is read
#: **off the plate itself** -- the annotated core labels "32KB L1I$", "48KB L1D$" and
#: "1.25MB L2$/MLC", and the four data arrays it labels (384+256+256+384 KB) sum to that 1.25 MB,
#: which is the check that the labels were read right. The rest are published microarchitecture.
CACHE_KB = {
    'baseline':          {'L1I': 32,  'L1D': 32,  'L2': 512},
    'golden_cove':       {'L1I': 32,  'L1D': 48,  'L2': 1280},
    'zen2':              {'L1I': 32,  'L1D': 32,  'L2': 512},
    'arm_n1':            {'L1I': 64,  'L1D': 64,  'L2': 512},   # the 1.15 mm^2 row is 512K L2
    'arm_v1':            {'L1I': 64,  'L1D': 64,  'L2': 1024},  # row is core_plus_1mb_l2
    'arm_a64fx':         {'L1I': 64,  'L1D': 64,  'L2': 683},   # 8 MB L2 per 12-core CMG
    'riscv_xiangshan':   {'L1I': 64,  'L1D': 64,  'L2': 1024},  # "up to 1MB, unified"
}


def published_mix(chip='Golden Cove (P-core)'):
    """The published six-group mix for ``chip``, as fractions of its published core total.

    Uses ``pack_areas.non_overlapping_blocks``, so the nested children that make a naive sum
    overstate the core by 9.55% are excluded by construction, and the leftover appears as
    ``'residual'`` -- 1.35% on Golden Cove, against McPAT's 34.67%.
    """
    blocks = pack_areas.non_overlapping_blocks(chip)
    total = pack_areas.published_total(chip, block='core_total')
    out = {_PACK_BLOCK_TO_GROUP[k]: v['area_mm2'] / total for k, v in blocks.items()}
    out['residual'] = 1.0 - sum(out.values())
    return out


def sram_scale_from_capacity(key):
    """Total per-core SRAM capacity relative to the baseline. Measured input, not an estimate."""
    b = CACHE_KB['baseline']
    v = CACHE_KB[key]
    return float(sum(v.values())) / float(sum(b.values()))


def vector_multiple_from_width(bits):
    """Vector hardware as a multiple of the base FP unit, from total vector datapath width.

    Anchored on the pack's own measurement of an AVX-512 core -- ``GOLDEN_COVE_VECTOR_MULTIPLE``
    at ``X86_VECTOR_BITS`` -- and linear in width from there.

    **The linearity is the assumption**, and it is the mild half of the pair: doubling the
    datapath width of a fixed number of FMA pipes roughly doubles the multiplier arrays, which
    dominate the block. What it ignores is that a wider machine also needs more register-file
    ports and more forwarding, so the true relationship is slightly superlinear and this slightly
    understates wide vector hardware. That direction is the conservative one for the claim these
    floorplans exist to test.
    """
    return GOLDEN_COVE_VECTOR_MULTIPLE * float(bits) / X86_VECTOR_BITS


class ISAVariant(object):
    """A core design expressed as a mix, a size, a vector width and a power density.

    ``core_area_mm2``   published core + private L2 area [mm^2] at ``node``, or ``None`` when
                        nothing publishes one. This is the pack's contribution and it replaces
                        the chained press ratios the first cut used.
    ``core_area_scale`` the same thing relative to the baseline model core -- derived when
                        ``core_area_mm2`` is given, and assumed only when it is not.
    ``vector_bits``     total vector datapath width, from published microarchitecture.
    ``vector_multiple`` vector hardware as a multiple of the base FP unit, derived from
                        ``vector_bits``.
    ``cache_key``       key into ``CACHE_KB`` for this variant's per-core cache capacities.
    ``published_mix``   True if the block mix comes from Golden Cove's published decomposition
                        rather than being inherited from McPAT.
    ``w_per_mm2``       published power density for the part, or ``None``.
    ``area_provenance`` what the area actually is: ``'published'``, ``'model'`` or
                        ``'derived_from_microarchitecture'``.
    """

    def __init__(self, key, label, vector_isa, vector_bits, cache_key, provenance, assumptions,
                 core_area_mm2=None, core_area_scale=None, node='7nm', w_per_mm2=None,
                 w_per_mm2_range=None, source_image=None, published_mix=True,
                 area_provenance='derived_from_microarchitecture', vector_multiple=None):
        self.key = key
        self.label = label
        self.vector_isa = vector_isa
        self.vector_bits = int(vector_bits)
        self.cache_key = cache_key
        self.node = node
        self.core_area_mm2 = None if core_area_mm2 is None else float(core_area_mm2)
        self._core_area_scale = core_area_scale
        self.vector_multiple = (vector_multiple_from_width(vector_bits)
                                if vector_multiple is None else float(vector_multiple))
        self.sram_scale = sram_scale_from_capacity(cache_key)
        self.w_per_mm2 = None if w_per_mm2 is None else float(w_per_mm2)
        self.w_per_mm2_range = w_per_mm2_range
        self.source_image = source_image
        self.published_mix = bool(published_mix)
        self.area_provenance = area_provenance
        self.provenance = provenance
        self.assumptions = assumptions
        #: Unchanged meaning: nothing here was measured off silicon by us. What the area IS lives
        #: in ``area_provenance``, because "published vendor number" and "chained press ratio"
        #: are not the same claim and one bit cannot hold both.
        self.calibrated = False

    @property
    def core_area_scale(self):
        """Core + L2 area relative to the baseline model core (1.882 mm^2 at 7 nm)."""
        if self._core_area_scale is not None:
            return float(self._core_area_scale)
        if self.core_area_mm2 is not None:
            return self.core_area_mm2 / BASELINE_CORE_MM2_7NM
        # No published area: the size is whatever the cache and vector changes make it, measured
        # against the same changes applied to the baseline's own capacities.
        return self._derived_area_scale()

    def _derived_area_scale(self):
        base = published_mix()
        mine = self.group_fractions(normalise=False)
        theirs = _baseline_adjusted_mix()
        return sum(mine.values()) / sum(theirs.values())

    def cache_kb(self):
        return dict(CACHE_KB[self.cache_key])

    def group_fractions(self, base_chip='Golden Cove (P-core)', normalise=True):
        """This variant's six-group mix, as fractions summing to 1.

        Built from Golden Cove's published decomposition and moved on exactly the two axes that
        are published per variant:

        * **cache capacity** -- the L2 fraction scales with L2 capacity, and the L1I and L1D
          scale within their own groups rather than dragging the group with them. L2 area is
          linear in capacity to a good approximation, and the pack's own cache-area table
          (128 KB to 1 MB across three GPUs) measures it flat to within a percent, so this is
          checked rather than assumed -- ``core_templates.sram_linearity_check()``.
        * **vector width** -- the FMA share of the FP cluster scales linearly with total vector
          datapath width, anchored on the plate's own AVX-512 measurement.

        Everything else keeps Golden Cove's proportions, because **no ARM or RISC-V core
        decomposition is published anywhere in the pack**. That is the honest limit of this
        construction and it is the largest remaining assumption in the module.
        """
        total = pack_areas.published_total(base_chip, block='core_total')
        mix = published_mix(base_chip)
        gc_cache = CACHE_KB['golden_cove']
        my_cache = self.cache_kb()

        # Work in mm^2 on the Golden Cove core's own scale, then normalise. Absolute areas are
        # what the cache adjustments are naturally expressed in, and normalising last keeps the
        # published proportions exact for a variant that changes nothing.
        area = {g: f * total for g, f in mix.items() if g != 'residual'}

        # L2 is linear in capacity. Checked, not assumed: the pack's cache-area table runs
        # 128 KB to 1 MB across three GPUs at a flat mm^2/KB.
        area['l2'] *= my_cache['L2'] / float(gc_cache['L2'])

        # L1 caches move INSIDE their groups -- a 64 KB L1I is a bigger cache in the same
        # frontend, not a bigger frontend -- and they are priced from the plate's own L2 array
        # density with an L1 penalty, not from a McPAT proportion. Using McPAT's I$-share of its
        # own instruction fetch unit (60%) would put a 32 KB L1I at 0.98 mm^2 of Golden Cove's
        # 1.64 mm^2 frontend, which the same plate's L2 density says is 23x too large.
        area['frontend'] += (my_cache['L1I'] - gc_cache['L1I']) * L1_MM2_PER_KB
        area['lsu'] += (my_cache['L1D'] - gc_cache['L1D']) * L1_MM2_PER_KB

        # Vector: the FP cluster is non-vector FP hardware plus the FMA EUs, and only the latter
        # scales with datapath width.
        fma_share = GOLDEN_COVE_VECTOR_MULTIPLE / (1.0 + GOLDEN_COVE_VECTOR_MULTIPLE)
        width = self.vector_multiple / GOLDEN_COVE_VECTOR_MULTIPLE
        area['fpu'] = mix['fpu'] * total * ((1.0 - fma_share) + fma_share * width)

        # The residual stays at the published fraction: it measures how completely the core was
        # transcribed, not anything about the microarchitecture.
        r = PUBLISHED_RESIDUAL_FRACTION
        area['residual'] = sum(area.values()) * r / (1.0 - r)

        if not normalise:
            return area
        s = sum(area.values())
        return {k: v / s for k, v in area.items()}

    def __repr__(self):
        a = ('{:.3f} mm^2'.format(self.core_area_mm2) if self.core_area_mm2 is not None
             else 'derived')
        return '<ISAVariant {} {} (x{:.2f}) vector {}b>'.format(
            self.key, a, self.core_area_scale, self.vector_bits)


def _baseline_adjusted_mix():
    """Golden Cove's mix with the BASELINE's cache capacities and vector width applied.

    The reference a derived core area is measured against, so that "derived" means "the size this
    mix implies relative to the baseline's own mix" rather than an arbitrary normalisation.
    """
    ref = ISAVariant('_ref', 'reference', vector_isa='AVX-512', vector_bits=X86_VECTOR_BITS,
                     cache_key='baseline', provenance='internal', assumptions='internal')
    return ref.group_fractions(normalise=False)


ISA_VARIANTS = {v.key: v for v in [
    ISAVariant(
        'x86_skylake', 'Skylake-class x86 (the shipped baseline)',
        vector_isa='AVX-512', vector_bits=X86_VECTOR_BITS, cache_key='baseline',
        core_area_scale=1.0, node='7nm', published_mix=False, area_provenance='model',
        vector_multiple=X86_VECTOR_MULTIPLE, w_per_mm2=DIE_LEVEL_W_PER_MM2_N7,
        provenance=('McPAT on the project trace; this is the shipped floorplan, unmodified, and '
                    'it stays unmodified. Every catalogue result rests on it, so it is the '
                    'control against which the pack-calibrated variants are read -- not a '
                    'candidate for correction.'),
        assumptions=('None beyond those already in the McPAT model, which is the point of '
                     'keeping it. Its mix and its absolute size are both now known to disagree '
                     'with the one published x86 core decomposition -- see the module docstring '
                     'and x86_golden_cove.')),

    ISAVariant(
        'x86_golden_cove', 'Intel Golden Cove P-core (published decomposition)',
        vector_isa='AVX-512', vector_bits=X86_VECTOR_BITS, cache_key='golden_cove',
        core_area_mm2=7.123, node='Intel 7', area_provenance='published',
        w_per_mm2=DIE_LEVEL_W_PER_MM2_N7,
        source_image='images/area_tables/semianalysis__Intel_Meteor_Lake_006.png',
        provenance=("The pack's only fully decomposed core: 7.123 mm^2 broken into frontend "
                    '1.640, OoO schedule/retire 1.322, load-store with L1D 1.031, FPU including '
                    'the FMA EUs 0.986, integer execution 0.402 and L2 1.646 mm^2, closing to '
                    '1.35% of the published total. Cache capacities read off the annotated core '
                    'plate itself (32 KB L1I, 48 KB L1D, 1.25 MB L2). This is the floorplan the '
                    'whole rebuild is calibrated against.'),
        assumptions=('The mix is published and the size is published; what is assumed is that '
                     'our McPAT trace, which is a Skylake-class workload, is a fair power input '
                     'for a Golden Cove core. It is the same x86 lineage two generations on, '
                     'which is the closest available and not the same thing.')),

    ISAVariant(
        'x86_zen2', 'AMD Zen 2 core (iso-node x86 size check)',
        vector_isa='AVX2', vector_bits=2 * 256, cache_key='zen2',
        core_area_mm2=3.54, node='TSMC N7', area_provenance='published',
        w_per_mm2=DIE_LEVEL_W_PER_MM2_N7,
        source_image='block_areas.csv: AMD / Zen 2 / core_incl_l2',
        provenance=('AMD Zen 2, 3.54 mm^2 for core including its 512 KB L2 on TSMC N7. It '
                    'matters because it is the ONLY published x86 core area in the pack at the '
                    'same node AND the same L2 capacity as our own McPAT configuration, which '
                    'makes it a direct check on the baseline: 3.54 against a modelled 2.116, so '
                    'the model core is 1.67x too small at iso-node.'),
        assumptions=('AVX2 at 2x256b sets the vector width; Zen 2 splits 256-bit ops across two '
                     '128-bit halves internally, so treating it as 512 bit of datapath is an '
                     'upper bound on its vector area. No Zen 2 block decomposition is published, '
                     "so the mix is Golden Cove's.")),

    ISAVariant(
        'arm_n1', 'Arm Neoverse N1 (compact server core)',
        vector_isa='NEON 2x128b', vector_bits=2 * 128, cache_key='arm_n1',
        core_area_mm2=1.15, node='7nm', area_provenance='published',
        w_per_mm2=0.870, w_per_mm2_range=(0.870, 1.286),
        source_image=('images/floorplans/'
                      'isa_cores__ARM_ARM_s_Neoverse_N2_Cortex_A710_for_Server_509.jpeg'),
        provenance=("Arm's own slide: Neoverse N1 at 7 nm is 1.15-1.4 mm^2 for core plus L2 "
                    '(512K/1M) at 1.0-1.8 W. The 1.15 mm^2 / 1.0 W end is taken because it is '
                    'the one whose L2 capacity (512 KB) matches the cache row used here; the '
                    'range is carried in w_per_mm2_range rather than averaged away.'),
        assumptions=('Which end of the published range to take is a choice, and it is the '
                     'consequential one: 1.15 mm^2 at 1.0 W is 0.870 W/mm^2 against 1.4 mm^2 at '
                     '1.8 W = 1.286, a 48% spread. No N1 block decomposition is published, so '
                     "the mix is Golden Cove's with N1's cache capacities and vector width.")),

    ISAVariant(
        'arm_v1', 'Arm Neoverse V1 (wide vector server core)',
        vector_isa='SVE 2x256b', vector_bits=2 * 256, cache_key='arm_v1',
        core_area_mm2=2.52, node='7nm', area_provenance='published',
        w_per_mm2=0.476,
        source_image=('images/floorplans/'
                      'isa_cores__ARM_Hot_Chips_2023_Arm_s_Neoverse_V2_468.jpeg'),
        provenance=("Arm's PPA slide: V1 is 2.52 mm^2 for core plus 1 MB L2 at 1.2 W, 2.8 GHz, "
                    '0.75 V, typical 7 nm implementation. **This corrects the first cut.** That '
                    'used a press claim of "V1 is ~70% larger than N1" chained onto an assumed '
                    'N2 ratio, giving 0.71x the baseline. The pack\'s own rows give V1 against '
                    'N1 as 2.52/1.4 = 1.80x to 2.52/1.15 = 2.19x -- not 1.70 -- and against our '
                    'baseline core V1 is 1.19x, i.e. LARGER, where the first cut had it 29% '
                    'smaller.'),
        assumptions=('The 2.52 mm^2 includes 1 MB of L2 against the baseline\'s 512 KB, and the '
                     'mix accounts for that. What is assumed is that Arm\'s "typical '
                     'implementation" is comparable to a McPAT area estimate at all -- a '
                     'hardened commercial layout against a model, which is exactly the '
                     'comparison the 1.9x Zen 2 discrepancy is warning about.')),

    ISAVariant(
        'arm_a64fx', 'Fujitsu A64FX (HPC, 512-bit SVE)',
        vector_isa='SVE 512b x2', vector_bits=2 * 512, cache_key='arm_a64fx',
        node='7nm', area_provenance='derived_from_microarchitecture',
        provenance=('Fujitsu A64FX, the machine the HPC question is actually about: 7 nm, 48 '
                    'compute + 4 assistant cores in 4 CMGs of 12, 8.786 G transistors, '
                    'Armv8.2-A with 512-bit SVE, 64 KB L1I and 64 KB L1D per core, 8 MB L2 per '
                    'CMG (683 KB per core), HBM2 at 1 TB/s. **The pack publishes no A64FX area '
                    'and no A64FX floorplan** -- it is absent from all 310 images -- so this '
                    'variant keeps the derived route and its absolute size is an OUTPUT of the '
                    'cache and vector changes, not a measurement.'),
        assumptions=('Core area is derived, not published: it is whatever the Golden Cove mix '
                     "becomes once A64FX's cache capacities and 1024-bit vector width are "
                     'applied. Every other variant in this set except riscv_xiangshan has a '
                     'published area, which is the reason to read this one\'s absolute size '
                     'with more suspicion than its shape.')),

    ISAVariant(
        'riscv_xiangshan', 'XiangShan Kunminghu RISC-V (server OoO)',
        vector_isa='RVV 1.0 VLEN 128b x2', vector_bits=2 * 128, cache_key='riscv_xiangshan',
        node='7nm', area_provenance='derived_from_microarchitecture',
        provenance=('XiangShan Kunminghu (v3) from ICT/CAS: out-of-order superscalar RV64, '
                    'RVA-23, server/data-centre targeted, taped out, fully open. 64 KB L1I, up '
                    'to 64 KB L1D, up to 1 MB unified L2, RVV 1.0 with VLEN 128 bit x 2. Chosen '
                    'over the OpenHW CORE-V and riscv/learn populations because those are '
                    'in-order embedded and application-class parts -- CVA6 is their ceiling and '
                    'is roughly Cortex-A55 tier, three classes below the target.'),
        assumptions=('Like A64FX, the area is derived. The pack DOES carry three real RISC-V '
                     'layouts -- XuanTie C910, SiFive P870 and Ventana Veyron V1 -- but only '
                     'Veyron prints an area and it is a 16-core cluster on N5, not a core on '
                     '7 nm, so none of them can size this variant. Open-RTL synthesised area is '
                     'typically 2-3x worse density than a hardened design, which is why the MIX '
                     'is used and any absolute from that route would not be.')),
]}

#: Variants retired by the rebuild, kept so results already on disk can still be interpreted.
#: Their floorplans are in ``examples/floorplans/isa_outputs/`` and their numbers are in
#: ``docs/evidence/isa_benefit_prediction_test.json``.
#:
#: ``arm_n2`` (x0.42) and ``riscv_p670`` (x0.30) were chained press ratios -- P670's compounded
#: two of them -- and the old ``arm_v1``'s 0.71 came from the "~70% larger than N1" claim the
#: pack's own rows put at 80-119%. All three are superseded by published areas above, and none of
#: them ever varied its vector width, because the multiple was never installed.
RETIRED_VARIANTS = {
    'arm_n2': {'core_area_scale': 0.42, 'vector_multiple': 0.50,
               'why': 'press ratio; superseded by arm_n1, whose area is published'},
    'arm_v1_press': {'core_area_scale': 0.71, 'vector_multiple': 1.60,
                     'why': '0.42 x 1.70 chained press ratios; the pack gives 2.52 mm^2 directly'},
    'riscv_p670': {'core_area_scale': 0.30, 'vector_multiple': 0.80,
                   'why': 'two chained press ratios; no published P670 area exists anywhere'},
}


def _ancestors(unit_path):
    """Ancestor Area keys of a slash-delimited unit path, innermost first, ending at 'Area'.

    'Load Store Unit/Data Cache/Area' -> ['Load Store Unit/Area', 'Area']
    'L2/Area'                         -> ['Area']
    """
    parts = unit_path.split('/')
    assert parts[-1] == 'Area', unit_path
    stem = parts[:-1]
    out = []
    for i in range(len(stem) - 1, 0, -1):
        out.append('/'.join(stem[:i]) + '/Area')
    out.append('Area')                      # the core itself
    return out


def _root_area(core, root):
    """A subtree root's area, tolerating the one key the raw JSON spells differently.

    ``Execution Unit/Results Broadcast Bus`` is published as ``Area Overhead`` and renamed to
    ``Area`` by ``load_14nm_stats``. Resolving it in the scaler but not in the *denominator* the
    scale factor is computed from made every group factor 1.78% too large -- the bus's share of
    the out-of-order group -- and the excess came straight out of the residual. One helper, used
    by both, is why that cannot recur.
    """
    for key in (root + '/Area', root + '/Area Overhead'):
        if key in core:
            return core[key]
    return 0.0


def _scale_subtree(core, root, factor):
    """Scale ``root`` and everything under it by ``factor``, propagating the delta to ancestors.

    Scaling a leaf without propagating to its ancestors overflows the shipped tiler's assertion
    that children fit inside their parent (``examples/floorplans.py::replace``). That defect could
    not appear while variants only ever shrank things, and it surfaced the first time one scaled
    SRAM **up**. The tiler caught it; this is where it stays fixed.
    """
    root_key = root + '/Area'
    if root_key not in core:
        root_key = root + '/Area Overhead'
        if root_key not in core:
            return 0.0
    delta = core[root_key] * (factor - 1.0)
    prefix = root + '/'
    for k in list(core):
        if k == root_key or k.startswith(prefix):
            core[k] *= factor
    for parent in _ancestors(root + '/Area'):
        if parent in core:
            core[parent] += delta
    return delta


def _repair_parent_coverage(core):
    """Make every internal node at least as large as the sum of its own children.

    The shipped tiler asserts ``total_size <= unit.area + 1e-1`` when it subdivides a block, and
    the shipped data violates it by **exactly 0.1 um^2** on the branch predictor: its five
    children sum to 12461.5 against a parent of 12461.4. That sits precisely on the tolerance, so
    the baseline builds and **any upscaling breaks it** -- a variant with a 3.8x larger frontend
    turns the 0.1 into 0.38 and ``add_level3`` raises.

    The repair is bottom-up and additive: a parent short of its children is raised to *exactly*
    cover them, and the increase propagates to its own ancestors. On the shipped numbers it moves
    0.4 um^2 of a 2.5 mm^2 core -- 1.6e-7 -- so it cannot affect a result; what it does is stop a
    floating point artefact in somebody else's input from deciding which variants can be built.

    Exactly, with no safety margin, because the tiler has a second assertion pulling the other
    way: a parent with MORE than 0.5 um^2 of slack takes a different branch in ``replace`` and
    then demands the slack be under 1e-8. The register files sit at equality in the shipped data,
    so a 1e-6 mm^2 margin here becomes 1.0 um^2 there and trips it. There is no room between the
    two assertions for a margin, and none is needed.

    The same 0.5 um^2 threshold is why a *tiny positive* slack is clamped to zero as well, and
    that half of the repair is the one that mattered. McPAT's instruction scheduler carries
    0.42 um^2 more area than its three children -- below the threshold, so the shipped baseline
    emits no block for it. Scale the scheduler up to the published mix and that rounding artefact
    scales too: at 0.99 um^2 it crosses the threshold, the tiler emits a **sliver block** for it,
    and the sliver comes out 509 um wide and a few nanometres tall. 3D-ICE returned non-finite
    temperatures for those floorplans and every driver read that as thermal runaway -- a
    62 mm^2 die "diverging" at 12.5 W, which is not a temperature at all.

    ``TINY_SLACK_FRACTION`` is the cutoff: slack below it is float noise in somebody else's
    numbers and is removed; slack above it is modelled area the tiler is entitled to place. The
    instruction fetch unit's genuine 0.7% internal residual is far above it and survives.
    """
    kids = {}
    for k in core:
        if not k.endswith('/Area'):
            continue
        stem = k[:-len('/Area')]
        if '/' not in stem:
            parent = 'Area'
        else:
            parent = stem.rsplit('/', 1)[0] + '/Area'
        kids.setdefault(parent, []).append(k)
    # Deepest first, so a raise propagates correctly upward.
    for parent in sorted(kids, key=lambda p: -p.count('/')):
        if parent not in core:
            continue
        total = sum(core[c] for c in kids[parent])
        slack = core[parent] - total
        if slack < 0:
            bump = -slack
        elif 0 < slack < TINY_SLACK_FRACTION * core[parent]:
            bump = -slack                      # clamp the rounding artefact away
        else:
            continue
        core[parent] += bump
        for anc in (_ancestors(parent) if parent != 'Area' else []):
            if anc in core:
                core[anc] += bump


def _forward_constants():
    """The three constants the shipped forward model applies, read from the shipped code."""
    _ex = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'examples')
    _ex = os.path.normpath(_ex)
    if _ex not in sys.path:
        sys.path.insert(0, _ex)
    import floorplans as fp
    if getattr(fp, 'LOGGER', None) is None:
        fp.LOGGER = LOGGER
    return fp.L2_AREA_MULTIPLIER, fp.L3_CORRECTION_FACTOR, fp


def reweight_area_stats(base_stats, variant, num_cores=TILER_NUM_CORES):
    """Re-weight a raw ``14nm_unit_areas.json`` dict for ``variant``. Returns ``(stats, meta)``.

    Operates on the RAW json -- before ``floorplans.load_14nm_stats`` folds in L3, rescales L2 and
    adds the derived vector units -- so the shipped generator consumes the result with
    ``--area-json`` and no code change. That is deliberate: the tiler is not ISA-specific and
    should not learn to be.

    Two paths, and which one runs is a property of the variant:

    * ``published_mix=False`` (only ``x86_skylake``) keeps McPAT's mix and applies nothing. The
      shipped baseline must come out byte-identical, and a test asserts it does.
    * ``published_mix=True`` sets each group's share to ``variant.group_fractions()`` and the
      core's absolute area from ``variant.core_area_scale``, which is derived from a published
      core area wherever one exists.

    The arithmetic is closed-form rather than fitted. ``load_14nm_stats`` is linear in the raw
    areas -- it multiplies L2 by a constant, adds an L3 share, and adds a vector block
    proportional to the FPU -- so the raw values that produce a wanted post-load mix can be
    written down. It is still an inversion of somebody else's function, so
    ``write_variant_area_json`` runs the real forward model on the result and reports the realised
    mix beside the target rather than trusting the algebra.
    """
    if isinstance(variant, str):
        variant = ISA_VARIANTS[variant]
    out = copy.deepcopy(base_stats)
    core = out['Core']

    meta = {'variant': variant.key, 'vector_multiple': variant.vector_multiple,
            'vector_bits': variant.vector_bits, 'sram_scale': variant.sram_scale,
            'core_area_scale': variant.core_area_scale,
            'core_area_mm2': variant.core_area_mm2,
            'area_provenance': variant.area_provenance,
            'published_mix': variant.published_mix,
            'w_per_mm2': variant.w_per_mm2,
            'calibrated': False}

    if not variant.published_mix:
        meta['note'] = 'shipped baseline, unmodified'
        return out, meta

    m_l2, l3_factor, _ = _forward_constants()
    avx = variant.vector_multiple          # what the generator installs for this variant

    # Target post-load core area (excluding the L3 share), in the 14 nm units the raw JSON uses.
    target = BASELINE_CORE_MM2_7NM * variant.core_area_scale / NODE_AREA_FACTOR_7NM
    frac = variant.group_fractions()

    # Invert the forward map group by group. A group's post-load area equals its raw area except
    # for L2 (x m_l2) and the FP cluster (x (1 + avx)), so the raw target is the post-load target
    # divided by that factor.
    post_of_raw = {'l2': m_l2, 'fpu': 1.0 + avx}
    for group, roots in GOLDEN_COVE_GROUPS.items():
        want_raw = frac[group] * target / post_of_raw.get(group, 1.0)
        have_raw = sum(_root_area(core, r) for r in roots)
        if have_raw <= 0:
            raise ValueError('group {!r} has no area in the base stats'.format(group))
        for r in roots:
            _scale_subtree(core, r, want_raw / have_raw)

    # --- pin the L1 caches by capacity, INSIDE their groups --------------------------------
    # The published mix fixes each group's total; McPAT's internal split then decides how much of
    # a group is its L1 array, and the pack shows that split to be badly wrong. McPAT puts the
    # instruction cache at 60% of its own instruction fetch unit; carried onto Golden Cove's
    # published 1.640 mm^2 frontend that makes a 32 KB L1I about 0.98 mm^2, where the same
    # plate's L2 array density prices it at 0.038 -- a factor of 26. Left alone it turned the
    # iCache into the third largest block on the die (11% of it, against 4.4% in the baseline).
    #
    # So the cache leaf is scaled to its capacity-derived area as a share of the final group,
    # and the group scale above then carries everything to the published total. Solving for the
    # leaf factor that lands the leaf at share ``st`` after the group is renormalised:
    #     k = st * (G - C) / (C * (1 - st))
    for group, leaf, cap in (('frontend', 'Instruction Fetch Unit/Instruction Cache',
                              variant.cache_kb()['L1I']),
                             ('lsu', 'Load Store Unit/Data Cache',
                              variant.cache_kb()['L1D'])):
        roots = GOLDEN_COVE_GROUPS[group]
        G = sum(_root_area(core, r) for r in roots)
        C = _root_area(core, leaf)
        if not C or not G:
            continue
        want_mm2_7nm = cap * L1_MM2_PER_KB
        group_mm2_7nm = frac[group] * BASELINE_CORE_MM2_7NM * variant.core_area_scale
        st = want_mm2_7nm / group_mm2_7nm
        if st >= MAX_L1_SHARE_OF_GROUP:
            raise ValueError(
                '{}: a {} KB L1 prices at {:.4f} mm^2, which is {:.0%} of the {:.4f} mm^2 the '
                'published mix gives its {} group. Above {:.0%} the group fraction and the cache '
                'capacity are describing different machines -- check the core area, the capacity '
                'and L1_DENSITY_PENALTY before going further.'
                .format(variant.key, cap, want_mm2_7nm, st, group_mm2_7nm, group,
                        MAX_L1_SHARE_OF_GROUP))
        _scale_subtree(core, leaf, st * (G - C) / (C * (1.0 - st)))
        # Re-scale the group back onto its target, now that the leaf has moved.
        have = sum(_root_area(core, r) for r in roots)
        want = frac[group] * target / post_of_raw.get(group, 1.0)
        for r in roots:
            _scale_subtree(core, r, want / have)
        meta.setdefault('l1_pin', {})[group] = {
            'capacity_kb': cap, 'area_mm2_at_7nm': want_mm2_7nm,
            'share_of_group': st, 'mcpat_share_would_have_been': C / G}

    # Repair the shipped data's one float artefact before the tiler meets it -- see
    # _repair_parent_coverage. Must run before 'Area' is set, since it can raise ancestors.
    _repair_parent_coverage(core)

    # Finally set the core's own Area so the residual -- what the tiler renders as the
    # `core_other` slab -- lands at the published 1.35% rather than McPAT's 34.67%. This is the
    # single largest change the pack makes to the floorplan and it is one line.
    core['Area'] = (target
                    - frac['l2'] * target * (1.0 - 1.0 / m_l2)
                    - frac['fpu'] * target)
    out['Processor']['Total Cores/Area'] = core['Area'] * num_cores

    meta['target_group_fractions'] = frac
    meta['target_core_area_14nm_units'] = target
    meta['residual_fraction'] = frac['residual']
    meta['note'] = ('mix from the published Golden Cove decomposition, moved by this variant\'s '
                    'cache capacities and vector width; absolute size from {}'
                    .format(variant.area_provenance))
    return out, meta


def realised_group_fractions(stats, num_cores=TILER_NUM_CORES, avx=None):
    """The six-group mix a raw area JSON actually produces, after the shipped forward model.

    Runs ``floorplans.load_14nm_stats`` for real, with ``avx`` temporarily installed in
    ``DERIVED_UNITS`` exactly as the generator installs it, so what is measured here is what the
    tiler will see.
    """
    _, _, fp = _forward_constants()
    old = None
    if avx is not None:
        from HotGauge.configuration import mcpat as _mc
        old = _mc.DERIVED_UNITS['AVX_FPU/AVX512 Accelerator']
        _mc.DERIVED_UNITS['AVX_FPU/AVX512 Accelerator'] = [
            _mc.SourceComponent(old[0].base, avx)]
    path = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(stats, f)
            path = f.name
        s = fp.load_14nm_stats(path, num_cores=num_cores)
    finally:
        if old is not None:
            from HotGauge.configuration import mcpat as _mc
            _mc.DERIVED_UNITS['AVX_FPU/AVX512 Accelerator'] = old
        if path:
            os.unlink(path)

    core = s['Area'] - s['L3/Area']
    roots = {'frontend': ['Instruction Fetch Unit/Area'],
             'ooo': ['Execution Unit/Instruction Scheduler/Area', 'Renaming Unit/Area',
                     'Execution Unit/Results Broadcast Bus/Area',
                     'Execution Unit/Register Files/Area'],
             'lsu': ['Load Store Unit/Area', 'Memory Management Unit/Area'],
             'fpu': ['AVX_FPU/Area'],
             'int': ['Execution Unit/Complex ALUs/Area', 'Execution Unit/Integer ALUs/Area'],
             'l2': ['L2/Area']}
    out, acc = {}, 0.0
    for g, keys in roots.items():
        a = sum(s[k] for k in keys if k in s)
        acc += a
        out[g] = a / core
    out['residual'] = (core - acc) / core
    out['_core_mm2_at_7nm'] = core * NODE_AREA_FACTOR_7NM / 1e6
    return out


def baseline_group_fractions(base_json_path, num_cores=TILER_NUM_CORES):
    """The shipped baseline's own mix, for the comparison the module docstring tabulates."""
    with open(base_json_path) as f:
        return realised_group_fractions(json.load(f), num_cores=num_cores)


def write_variant_area_json(variant, base_json_path, out_path,
                            num_cores=TILER_NUM_CORES):
    """Write the re-weighted area JSON for ``variant`` and return its metadata.

    The metadata carries ``realised`` -- the mix the tiler will actually produce -- beside the
    target, so the generator prints both and a silent miss is impossible.
    """
    if isinstance(variant, str):
        variant = ISA_VARIANTS[variant]
    with open(base_json_path) as f:
        base = json.load(f)
    stats, meta = reweight_area_stats(base, variant, num_cores=num_cores)
    with open(out_path, 'w') as f:
        json.dump(stats, f, indent=1)
    meta['path'] = out_path
    meta['realised'] = realised_group_fractions(stats, num_cores=num_cores,
                                                avx=variant.vector_multiple)
    if variant.published_mix:
        tgt = meta['target_group_fractions']
        # The residual is 1.35% of the core, so a relative error on it is a fraction of a
        # fraction; it is reported on its own rather than allowed to dominate a max().
        meta['worst_group_error'] = max(abs(meta['realised'][g] / tgt[g] - 1.0)
                                        for g in tgt if g != 'residual')
        meta['residual_error'] = meta['realised']['residual'] / tgt['residual'] - 1.0
    return meta


def variant_summary():
    """One row per variant, for a report or a table."""
    rows = []
    for k, v in ISA_VARIANTS.items():
        rows.append({'key': k, 'label': v.label, 'vector_isa': v.vector_isa,
                     'vector_bits': v.vector_bits,
                     'core_area_mm2': v.core_area_mm2,
                     'core_area_scale': v.core_area_scale,
                     'vector_multiple': v.vector_multiple,
                     'sram_scale': v.sram_scale, 'node': v.node,
                     'w_per_mm2': v.w_per_mm2,
                     'area_provenance': v.area_provenance,
                     'published_mix': v.published_mix,
                     'calibrated': v.calibrated})
    return sorted(rows, key=lambda r: -r['core_area_scale'])


def density_for(key, end='min'):
    """Published W/mm^2 for a variant, for a sweep running each part at its own density.

    ``end`` selects which end of a published range to take (``'min'``, ``'max'``, ``'mid'``). The
    N-class rows span 48%, so the choice is reported, never averaged away silently.
    """
    v = ISA_VARIANTS[key]
    if v.w_per_mm2 is None:
        return None
    if v.w_per_mm2_range is None:
        return v.w_per_mm2
    lo, hi = v.w_per_mm2_range
    return {'min': lo, 'max': hi, 'mid': 0.5 * (lo + hi)}[end]


def l1_sensitivity(key, penalties=(1.0, 2.0, 3.0, 4.0)):
    """How much ``L1_DENSITY_PENALTY`` moves a variant's mix. The one unanchored assumption.

    Returns the frontend and load/store group fractions at each penalty, so a reader can see
    directly whether the number they disagree with matters for the variant they care about.
    """
    global L1_MM2_PER_KB
    v = ISA_VARIANTS[key]
    saved, out = L1_MM2_PER_KB, {}
    try:
        for p in penalties:
            L1_MM2_PER_KB = L2_ARRAY_MM2_PER_KB * p
            f = v.group_fractions()
            out[p] = {'frontend': f['frontend'], 'lsu': f['lsu']}
    finally:
        L1_MM2_PER_KB = saved
    lo = min(out[p]['frontend'] for p in penalties)
    hi = max(out[p]['frontend'] for p in penalties)
    out['frontend_spread'] = hi / lo - 1.0
    out['note'] = ('the group FRACTIONS barely move, because the penalty only shifts the small '
                   'capacity delta against Golden Cove; where it bites is the share of the '
                   'group the L1 leaf takes, which reweight_area_stats reports as l1_pin')
    return out
