"""A real accelerator floorplan, measured from die shots rather than invented.

Why this exists
---------------
Every design-study result so far used a *proxy* for an accelerator: take the Sniper/McPAT CPU
floorplan and redistribute each core's power into its FP units (``clock_search.emphasise_units``).
That answers "what if a core's power were concentrated?" but it cannot answer anything about
accelerator **geometry**, and geometry is exactly what the degeneracy results turned out to hinge
on. A 34-core CPU die has 15 blocks within 10 K of its peak; an accelerator has a hundred-plus
nearly identical compute tiles, and that is a different thermal problem, not a scaled one.

So this builds the floorplan from published die analysis of **Nvidia GA100 (A100, TSMC 7 nm)**,
the same node class as the CPU die already modelled, which makes the comparison iso-node.

Provenance
----------
Areas are from the SemiAnalysis / Locuza annotated die shots in
``docs/chip_design_lit/die_images/``:

* ``GA100-...jpg`` -- GA100 itself: die 826 mm^2 without scribe lines, 1x TPC (2x SM)
  6.86-6.95 mm^2, 512KB L2 tile 1.24-1.40 mm^2, 12MB L2 30.64-31.03 mm^2, 48MB L2
  122.56-124.12 mm^2, 16x PCIe 4.0 PHY 5.24-5.31 mm^2, and the arrangement: 8 clusters of
  16 SM, 96 L2 tiles in two central spines, 6 HBM2e PHY plus 4 groups of 3x 512-bit memory
  control around the top and bottom edges, 4 NVLINK PHY on the left edge, PCIe/video/control
  on the right.
* ``ga102-unit-sizes...jpg`` -- GA102, used for **one** number GA100's shot does not give: the
  SRAM fraction *inside* a compute tile, 33.36% of an SM with its 128KB L1. That matters because
  SRAM and datapath do not dissipate alike, so an SM modelled as one uniform block hides the very
  concentration the MR policy is supposed to exploit.

Where two figures are quoted for one block (Locuza gives with- and without-scribe measurements)
the **smaller** is used, so the die comes out slightly dense rather than slightly optimistic.

What is measured and what is assumed
------------------------------------
Measured: every area, every block count, the arrangement, the SRAM fraction.

Assumed, and this is the part to argue with: **how power divides between block classes**.
Die-shot analysis gives areas, not dissipation, and no public per-block power breakdown for
GA100 exists. ``GA100_POWER_SPLIT`` states the split explicitly with reasoning, and
``calibrated`` is False on everything this module produces. Any result that turns on the exact
split has to be checked against ``power_split_sensitivity()`` before it is quoted.

The prediction this floorplan exists to test
--------------------------------------------
It is worth writing down in advance, because it is falsifiable: with 128 near-identical compute
tiles, thermal degeneracy should be close to *maximal* -- the plateau within dt_max should contain
most of the SMs, and the gain from clipping one should be near zero. If that holds, hotspot MR is
structurally the wrong tool for an accelerator, and the only MR policy with any hope on such a die
is the distributed/die-average one. If it does *not* hold -- if the L2 cross and the perimeter
PHY break the symmetry enough to produce a genuine hotspot -- then accelerators are a better MR
target than CPUs, not a worse one.
"""

import math
import logging

LOGGER = logging.getLogger(__name__)

#: GA100 block areas [mm^2], measured. See the module docstring for provenance.
GA100_AREAS = {
    'die_mm2': 826.0,           # without scribe lines
    'sm_mm2': 6.86 / 2.0,       # 1x TPC = 2x SM, smaller of the two quoted TPC figures
    'l2_tile_mm2': 1.24,        # 512KB L2 tile, smaller of tile A / tile B
    'pcie_phy_mm2': 5.24,       # 16x PCIe 4.0 PHY
    # Ratio of die width to height, read off the annotated shot (the die spans roughly 1400 x
    # 1100 px of it). Together with the area this fixes the outline; it is the one geometric
    # input taken by eye rather than from a quoted number.
    'die_aspect': 1.27,
}

#: GA100 block counts and arrangement, from the annotated die shot.
GA100_COUNTS = {
    'n_sm': 128,                # 8 clusters of 16 (108 enabled on the shipped part)
    'n_sm_clusters': 4,         # each 2 SM wide x 16 SM tall, i.e. 32 SM -- the image's pairing
    'n_l2_tiles': 96,           # 48 MB / 0.5 MB
    'n_l2_spines': 2,           # two central columns, 48 tiles each
    'n_hbm_phy': 6,             # 3 along the top edge, 3 along the bottom
    'n_mem_ctrl': 4,            # groups of 3x 512-bit, 2 top and 2 bottom
    'n_nvlink_phy': 4,          # left edge
}

#: Fraction of a compute tile that is SRAM rather than datapath, from the GA102 shot (purple box,
#: SM with 128KB L1: 0.294 of 0.881 mm^2). Applied to GA100's larger SM as the best available
#: estimate -- GA100 carries 192KiB of L1/SMEM, so if anything this UNDERSTATES its SRAM share,
#: which makes the datapath block modelled here slightly larger and cooler than reality.
SM_SRAM_FRACTION = 0.3336

#: How die power divides between block classes. **ASSUMED, not measured** -- see the module note.
#:
#: Reasoning, so it can be disagreed with specifically:
#: * ``sm`` 0.60 -- on a compute-bound kernel the SMs are the machine; tensor-core datapath is
#:   where an accelerator's power goes, and 60% is the middle of the range usually quoted for
#:   GPU compute-vs-uncore.
#: * ``l2`` 0.08 -- 48 MB of SRAM is large in area but SRAM burns far less per mm^2 than
#:   datapath; most of an L2's power is dynamic access energy, not the array.
#: * ``hbm_phy`` + ``mem_ctrl`` 0.22 together -- HBM interfaces are notoriously expensive, and a
#:   6-stack part at 2.4-3.2 Gbps/pin spends a large fraction of package power moving bits. This
#:   is the least certain entry and the one most worth a sensitivity check.
#: * ``nvlink`` 0.05 -- 12 NVLinks at 50 GB/s bidirectional are real power, but the PHY strips
#:   are narrow.
#: * ``pcie_misc`` 0.07 -- this block is a catch-all: PCIe, video decode, control, AND the
#:   crossbar / GigaThread / inter-cluster routing this floorplan does not resolve separately. It
#:   is large in area and low in density, which is the right shape for routing and control.
GA100_POWER_SPLIT = {
    'sm': 0.60, 'l2': 0.08, 'hbm_phy': 0.13, 'mem_ctrl': 0.07,
    'nvlink': 0.05, 'pcie_misc': 0.07,
}

#: Within an SM, the split between datapath and its L1/SMEM array. Area is measured
#: (``SM_SRAM_FRACTION``); the *power* ratio is assumed. 0.85 to the datapath encodes that the
#: datapath is both the larger fraction and by far the hotter per mm^2 -- a tensor core at full
#: rate against an SRAM array that is read a few times per instruction.
SM_DATAPATH_POWER_FRACTION = 0.85


def _fmt_block(name, x_um, y_um, w_um, h_um):
    """One 3D-ICE floorplan element. Not the HotSpot tab-separated form -- both are called .flp
    and only one of them parses here."""
    return ('{} :\n\tposition {:.3f}, {:.3f} ;\n\tdimension {:.3f}, {:.3f} ;\n'
            '\tpower values 0.0;'.format(name, x_um, y_um, w_um, h_um))


def ga100_geometry(areas=None, counts=None, sm_rows=16, l2_cols=4, mem_band_mm=1.6,
                   nvlink_band_mm=1.5):
    """Solve the GA100 floorplan's dimensions from the measured areas.

    Both the die **area** (826 mm^2) and its **aspect** (from the shot, wider than tall) are
    measured, so they fix the outline. The 16-SM direction is the short axis, which sets the SM
    tile height, and the SM's own measured area then sets its width. The interior width that
    results is *not* fitted to anything -- it is the arrangement's prediction, and comparing it
    with the die width the outline allows is the check that the arrangement is right.
    ``ga100_consistency()`` reports that residual.

    ``sm_rows``/``l2_cols`` come from the die shot (SM clusters are 2 wide x 16 tall; an L2 spine
    is 4 tiles wide). ``mem_band_mm`` and ``nvlink_band_mm`` are the two dimensions the shot does
    not quantify.

    Returns a dict of dimensions in mm.
    """
    A = dict(GA100_AREAS if areas is None else areas)
    N = dict(GA100_COUNTS if counts is None else counts)

    sm_per_cluster = N['n_sm'] // N['n_sm_clusters']
    sm_cols = sm_per_cluster // sm_rows
    if sm_cols * sm_rows != sm_per_cluster:
        raise ValueError('{} SM per cluster does not divide into {} rows'
                         .format(sm_per_cluster, sm_rows))
    tiles_per_spine = N['n_l2_tiles'] // N['n_l2_spines']
    l2_rows = tiles_per_spine // l2_cols
    if l2_rows * l2_cols != tiles_per_spine:
        raise ValueError('{} L2 tiles per spine does not divide into {} columns'
                         .format(tiles_per_spine, l2_cols))

    # Outline from the measured area and aspect.
    h_die = math.sqrt(A['die_mm2'] / A['die_aspect'])
    w_die = A['die_mm2'] / h_die
    h_int = h_die - 2 * mem_band_mm
    if h_int <= 0:
        raise ValueError('memory bands ({:.2f} mm each) do not fit in a {:.2f} mm die height'
                         .format(mem_band_mm, h_die))

    # 16 SM tall spans the interior height; the SM's measured area then gives its width.
    h_sm = h_int / sm_rows
    w_sm = A['sm_mm2'] / h_sm
    h_l2 = h_int / l2_rows
    w_l2 = A['l2_tile_mm2'] / h_l2

    w_cluster = sm_cols * w_sm
    w_spine = l2_cols * w_l2
    w_int = N['n_sm_clusters'] * w_cluster + N['n_l2_spines'] * w_spine

    # Whatever the outline has left over after the interior and the NVLINK edge is the right-hand
    # strip. On the real die that strip is labelled "PCIe Control, NV Video Decoder,
    # Miscellaneous", and here it necessarily also absorbs the uncore this floorplan does not
    # model as separate blocks -- the crossbar, GigaThread engine and inter-cluster routing that
    # the shot shows woven between the SM clusters. It is therefore a LOW-density catch-all, not
    # a claim that PCIe occupies 100+ mm^2.
    w_pcie = w_die - w_int - nvlink_band_mm
    if w_pcie <= 0:
        raise ValueError('no room left for the PCIe/uncore band: interior {:.2f} mm + NVLINK '
                         '{:.2f} mm exceeds the {:.2f} mm die width implied by {:.0f} mm^2 at '
                         'aspect {:.2f}'.format(w_int, nvlink_band_mm, w_die, A['die_mm2'],
                                                A['die_aspect']))

    return {'w_sm': w_sm, 'h_sm': h_sm, 'sm_cols': sm_cols, 'sm_rows': sm_rows,
            'w_l2': w_l2, 'h_l2': h_l2, 'l2_cols': l2_cols, 'l2_rows': l2_rows,
            'w_cluster': w_cluster, 'w_spine': w_spine,
            'w_int': w_int, 'h_int': h_int,
            'w_die': w_die, 'h_die': h_die,
            'mem_band': mem_band_mm, 'w_nvlink': nvlink_band_mm, 'w_pcie': w_pcie,
            'sm_per_cluster': sm_per_cluster, 'tiles_per_spine': tiles_per_spine}


def ga100_consistency(geom=None, counts=None, areas=None):
    """What fraction of the die the measured blocks account for, and what is lumped.

    The arrangement is only credible if the measured SM and L2 areas, laid out as the shot shows
    them, leave a plausible remainder for everything else. This reports that remainder rather than
    hiding it in a band width.
    """
    A = dict(GA100_AREAS if areas is None else areas)
    N = dict(GA100_COUNTS if counts is None else counts)
    g = ga100_geometry(areas=areas, counts=counts) if geom is None else geom
    sm = N['n_sm'] * A['sm_mm2']
    l2 = N['n_l2_tiles'] * A['l2_tile_mm2']
    bands = 2 * g['w_die'] * g['mem_band']
    nvlink = g['w_nvlink'] * g['h_int']
    pcie = g['w_pcie'] * g['h_int']
    total = g['w_die'] * g['h_die']
    return {'die_mm2': total, 'measured_die_mm2': A['die_mm2'],
            'sm_mm2': sm, 'l2_mm2': l2, 'mem_bands_mm2': bands,
            'nvlink_mm2': nvlink, 'pcie_uncore_mm2': pcie,
            'sm_frac': sm / total, 'l2_frac': l2 / total,
            'lumped_frac': (bands + nvlink + pcie) / total,
            'closure_err_mm2': (sm + l2 + bands + nvlink + pcie) - total}


def ga100_floorplan(out_path, split_sm=True, geom=None, counts=None):
    """Write a 3D-ICE floorplan for GA100 and return ``(path, block_classes)``.

    ``split_sm`` splits every compute tile into ``SM<i>_DP`` (datapath) and ``SM<i>_L1`` (the
    L1/SMEM array) using the measured GA102 SRAM fraction. It is the default because a uniform
    SM hides the intra-tile concentration that a hotspot MR policy would have to exploit -- with
    it off, the finest structure on the die is 3.4 mm^2 and no hotspot smaller than that can
    exist by construction.

    ``block_classes`` maps each block name to one of the ``GA100_POWER_SPLIT`` keys (plus
    ``'sm_dp'``/``'sm_l1'`` when split), which is what ``ga100_block_powers`` consumes.

    Interior arrangement, left to right, from the die shot:
    ``[SM cluster] [L2 spine] [SM cluster] [SM cluster] [L2 spine] [SM cluster]``
    with the memory PHY and controllers in full-width bands top and bottom, NVLINK down the left
    edge and PCIe/video/control down the right.
    """
    g = ga100_geometry(counts=counts) if geom is None else geom
    N = dict(GA100_COUNTS if counts is None else counts)
    MM = 1000.0                     # 3D-ICE floorplans are in um

    lines, classes = [], {}

    def add(name, x, y, w, h, cls):
        lines.append(_fmt_block(name, x * MM, y * MM, w * MM, h * MM))
        classes[name] = cls

    y0 = g['mem_band']              # interior sits above the bottom memory band
    x = g['w_nvlink']

    # Interior: clusters and spines interleaved as the shot shows them.
    order = ['sm', 'l2', 'sm', 'sm', 'l2', 'sm']
    sm_i, l2_i = 0, 0
    for kind in order:
        if kind == 'sm':
            for c in range(g['sm_cols']):
                for r in range(g['sm_rows']):
                    bx = x + c * g['w_sm']
                    by = y0 + r * g['h_sm']
                    if split_sm:
                        # The array sits alongside the datapath within the tile, so the split is
                        # spatial: a hotspot in the datapath is a real 2/3-of-a-tile hotspot.
                        w_dp = g['w_sm'] * (1.0 - SM_SRAM_FRACTION)
                        add('SM{}_DP'.format(sm_i), bx, by, w_dp, g['h_sm'], 'sm_dp')
                        add('SM{}_L1'.format(sm_i), bx + w_dp, by,
                            g['w_sm'] - w_dp, g['h_sm'], 'sm_l1')
                    else:
                        add('SM{}'.format(sm_i), bx, by, g['w_sm'], g['h_sm'], 'sm')
                    sm_i += 1
            x += g['w_cluster']
        else:
            for c in range(g['l2_cols']):
                for r in range(g['l2_rows']):
                    add('L2_{}'.format(l2_i), x + c * g['w_l2'], y0 + r * g['h_l2'],
                        g['w_l2'], g['h_l2'], 'l2')
                    l2_i += 1
            x += g['w_spine']

    if sm_i != N['n_sm'] or l2_i != N['n_l2_tiles']:
        raise ValueError('placed {} SM and {} L2 tiles, expected {} and {}'
                         .format(sm_i, l2_i, N['n_sm'], N['n_l2_tiles']))

    # Memory bands, full die width, top and bottom. HBM PHY and controller groups alternate
    # along each edge exactly as the shot shows: PHY, MC, PHY, MC, PHY.
    per_edge_phy = N['n_hbm_phy'] // 2
    per_edge_mc = N['n_mem_ctrl'] // 2
    band_seq = []
    for i in range(per_edge_phy):
        band_seq.append('hbm_phy')
        if i < per_edge_mc:
            band_seq.append('mem_ctrl')
    # Width is shared in proportion to how the shot reads: a PHY strip is wider than an MC group.
    weights = [1.4 if k == 'hbm_phy' else 1.0 for k in band_seq]
    total_w = sum(weights)
    for edge, y_edge in (('B', 0.0), ('T', g['h_die'] - g['mem_band'])):
        bx = 0.0
        n_phy = n_mc = 0
        for kind, wt in zip(band_seq, weights):
            bw = g['w_die'] * wt / total_w
            if kind == 'hbm_phy':
                add('HBM_PHY_{}{}'.format(edge, n_phy), bx, y_edge, bw, g['mem_band'], 'hbm_phy')
                n_phy += 1
            else:
                add('MEMCTRL_{}{}'.format(edge, n_mc), bx, y_edge, bw, g['mem_band'], 'mem_ctrl')
                n_mc += 1
            bx += bw

    # Left edge: NVLINK PHY, stacked. Right edge: PCIe / video / control, one strip.
    h_nv = g['h_int'] / N['n_nvlink_phy']
    for i in range(N['n_nvlink_phy']):
        add('NVLINK_{}'.format(i), 0.0, y0 + i * h_nv, g['w_nvlink'], h_nv, 'nvlink')
    add('PCIE_MISC', g['w_nvlink'] + g['w_int'], y0, g['w_pcie'], g['h_int'], 'pcie_misc')

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    LOGGER.info('wrote GA100 floorplan: %d blocks, %.2f x %.2f mm (%.1f mm^2) to %s',
                len(classes), g['w_die'], g['h_die'], g['w_die'] * g['h_die'], out_path)
    return out_path, classes


def ga100_block_powers(total_W, classes, split=None,
                       datapath_fraction=SM_DATAPATH_POWER_FRACTION):
    """Divide ``total_W`` across the floorplan's blocks by class.

    Within a class, power is shared **equally** between blocks. That is deliberate and it is the
    conservative choice for the question being asked: a uniform tile array is the most degenerate
    possible arrangement, so any hotspot this floorplan does produce comes from *geometry* -- edge
    versus interior, proximity to the L2 spines and the PHY bands -- rather than from an activity
    imbalance assumed into existence. Non-uniform activity is a separate axis, and one already
    covered by the per-core machinery in ``clock_search``.

    ``calibrated`` is False: the class split is an assumption (``GA100_POWER_SPLIT``).

    Returns ``(powers, meta)``.
    """
    split = dict(GA100_POWER_SPLIT if split is None else split)
    total_W = float(total_W)
    if abs(sum(split.values()) - 1.0) > 1e-6:
        raise ValueError('power split must sum to 1.0, got {:.6f}'.format(sum(split.values())))

    # An SM's share divides between its datapath and its array when the tile was split.
    by_class = {}
    for cls in set(classes.values()):
        if cls == 'sm_dp':
            by_class[cls] = split['sm'] * datapath_fraction
        elif cls == 'sm_l1':
            by_class[cls] = split['sm'] * (1.0 - datapath_fraction)
        else:
            if cls not in split:
                raise ValueError('no power share for block class {!r}'.format(cls))
            by_class[cls] = split[cls]

    counts = {}
    for cls in classes.values():
        counts[cls] = counts.get(cls, 0) + 1

    powers = {}
    for name, cls in classes.items():
        powers[name] = total_W * by_class[cls] / counts[cls]

    meta = {'total_W': total_W, 'split': split, 'datapath_fraction': datapath_fraction,
            'counts': counts, 'calibrated': False,
            'per_class_W': {c: total_W * by_class[c] for c in by_class},
            'note': 'areas measured from die shots; the class power split is ASSUMED -- see '
                    'GA100_POWER_SPLIT and power_split_sensitivity()'}
    return powers, meta


def block_areas_mm2(flp_path):
    """Area of each block in a written floorplan [mm^2], for checking against the measurement."""
    out = {}
    name = None
    with open(flp_path) as f:
        for line in f:
            s = line.strip()
            if s.endswith(':'):
                name = s[:-1].strip()
            elif s.startswith('dimension') and name:
                w, h = [float(v) for v in s[len('dimension'):].strip(' ;').split(',')]
                out[name] = w * h / 1e6
    return out


def power_density_by_class(classes, powers, areas):
    """W/mm^2 per block class -- the number that decides where the die actually gets hot.

    Reported because the interesting comparison is not which class has the most power but which
    has the highest density: 48 MB of L2 is a lot of area and not much heat, and a PHY strip is
    the reverse.
    """
    agg = {}
    for name, cls in classes.items():
        a = agg.setdefault(cls, {'W': 0.0, 'mm2': 0.0, 'n': 0})
        a['W'] += powers.get(name, 0.0)
        a['mm2'] += areas.get(name, 0.0)
        a['n'] += 1
    for cls, a in agg.items():
        a['W_per_mm2'] = a['W'] / a['mm2'] if a['mm2'] > 0 else float('nan')
    return agg


def power_split_sensitivity(total_W, classes, areas, vary='hbm_phy', factors=(0.5, 1.0, 1.5)):
    """How much the per-class power density moves when one assumed share is scaled.

    ``GA100_POWER_SPLIT`` is the module's weakest input, so it gets an error bar rather than
    trust. The varied class is scaled and the remainder renormalised, which is the honest way to
    do it -- the shares have to keep summing to 1.
    """
    out = {}
    for fac in factors:
        split = dict(GA100_POWER_SPLIT)
        if vary not in split:
            raise ValueError('unknown class {!r}'.format(vary))
        split[vary] = GA100_POWER_SPLIT[vary] * fac
        rest = 1.0 - split[vary]
        others = sum(v for k, v in GA100_POWER_SPLIT.items() if k != vary)
        for k in split:
            if k != vary:
                split[k] = GA100_POWER_SPLIT[k] * rest / others
        powers, _ = ga100_block_powers(total_W, classes, split=split)
        out[fac] = power_density_by_class(classes, powers, areas)
    return out
