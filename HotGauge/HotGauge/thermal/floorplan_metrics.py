"""Phase-1 floorplan metrics for the evolution ladder: properties of a DESIGN, not of a device.

Why this module exists, and what changed on 27 August 2026
----------------------------------------------------------
``docs/LADDER_GEN0.md`` section 3 lists five metrics a generation-0 floorplan should be scored on,
so that measured MR benefit can be regressed against them and **any metric that does not predict
is dropped**. Two of the five were listed as "not built"; a third turned out to be broken.

The broken one is instructive. *Plateau width at* ``dt_max`` -- how many blocks sit within the
device's lift of the peak -- was the workhorse screen, and it **degenerates completely at the
demonstrated device envelope**. Measured across eleven workload shapes on the 34-core die
(``docs/evidence/tier_screens_dt_ladder.json``):

    dt_max = 10 K   plateau spans   3 - 56 blocks   (18.7x, discriminating)
    dt_max = 45 K   plateau spans 1125 - 1126       ( 1.0x, no information at all)

The cause is arithmetic, not physics: the die's own temperature span is **31.9-45.0 K**, i.e. no
larger than the demonstrated 45 K lift, so "within ``dt_max`` of the peak" evaluates to "every
block". The metric was only ever informative because ``dt_max`` was pinned at an unsourced 10 K.
**A floorplan metric must not depend on a device parameter that can move under it**, which is the
design rule the rest of this module follows.

:func:`relative_plateau` is the replacement: the plateau measured as a fraction of *the die's own*
temperature span. It is self-normalising, has no device parameter, and preserves what the old
metric measured -- **Spearman 0.934** against ``plateau at dt_max = 10 K`` across the same eleven
shapes, while still discriminating 12.3x. The default fraction of 0.25 is where that agreement
peaks; correlation stays 0.76-0.93 over 0.10-0.50, so the choice is not delicate.
"""
import numpy as np


# ---------------------------------------------------------------------------------------------
# Temperature-distribution metrics
# ---------------------------------------------------------------------------------------------
def _sorted_desc(temps):
    t = np.asarray(list(temps.values()) if isinstance(temps, dict) else temps, dtype=float)
    if t.size == 0:
        raise ValueError('no temperatures given')
    return np.sort(t)[::-1]


def relative_plateau(temps, fraction=0.25):
    """Blocks within ``fraction`` of the die's OWN temperature span of the peak.

    The device-independent replacement for "plateau width at ``dt_max``". Returns a dict with the
    count, the count as a share of all blocks, and the absolute width in kelvin that the fraction
    worked out to -- the last so a reader can see what was actually asked.

    A narrow plateau means one block sets the peak and targeted cooling is the right tool; a wide
    one means moving the peak requires moving most of the die, which is bulk cooling.
    """
    if not 0.0 < fraction <= 1.0:
        raise ValueError('fraction must be in (0, 1], got {!r}'.format(fraction))
    t = _sorted_desc(temps)
    span = float(t[0] - t[-1])
    width = fraction * span
    n = int((t > t[0] - width).sum())
    return {'n_blocks': n, 'share': n / float(t.size), 'width_K': width,
            'span_K': span, 'fraction': float(fraction), 'n_total': int(t.size)}


def hot_region_depth(temps, fraction=0.05):
    """How far the temperature falls from the peak to the coolest of the hottest ``fraction``.

    **FAILS THE TRANSFER TEST -- do not use this as a design metric.** Tested 28 August 2026
    against six floorplans and it does not survive: the correlation with retained efficiency is
    **+0.800 across eleven workloads on one floorplan and -0.886 across six floorplans**. The sign
    REVERSES. Normalising by die span does not rescue it (+0.718 against -0.829).

    So it measures something real but workload-specific, not a property of a design, and
    ``docs/LADDER_GEN0.md`` section 3's own rule -- *any metric that does not predict is dropped*
    -- applies to it. It is kept, documented and tested because a metric that fails cleanly is
    worth more on the record than one quietly deleted, and because it remains a valid
    **within-floorplan workload diagnostic**. It must not be used to compare designs.

    The likely reason for the reversal is worth recording: across floorplans this quantity mostly
    tracks the die's absolute temperature SCALE (span), which is set by area and power rather than
    by the shape of the distribution. Within one floorplan the span is roughly fixed and the
    metric does measure shape. That also suggests saturation behaviour may not be predictable from
    the temperature distribution alone at all -- it appears to need the absolute thermal scale too.

    What follows is the original rationale, kept so the reasoning can be audited.

    Added 27 August 2026 to answer a question the other two metrics cannot.

    The 33-point workload regression turned up a split that nothing then computed could predict:
    efficiency retained as the demanded margin grows from 3 K to 8 K divides eleven workload
    shapes almost binarily -- six retain 98-100 %, five retain 37-54 %, with nothing in between --
    and it is **not ordered by plateau width**. Two of the widest-plateau shapes scale gracefully
    while a narrow one collapses to 43 %.

    What separates them is the *depth of the hot region below the peak*. Measured on the same
    eleven shapes at ``fraction = 0.05``:

        degrades (37-54 % retained)   10.1 - 14.0 K
        holds    (98-100 % retained)  19.5 - 33.0 K

    -- a clean 5.5 K gap with no overlap. Neither existing metric separates them at all:
    ``relative_plateau`` overlaps by 30 blocks *in the wrong direction*, and
    ``peak_to_runner_up_gap`` overlaps by 1.8 K.

    **Why it works.** As the demanded margin grows the plan must reach further down the
    distribution. Where the temperature falls away steeply below the top few per cent there is a
    well-defined hot group, and cooling it stays efficient. Where it falls away shallowly the plan
    runs into an ever-widening set of near-peak blocks and efficiency collapses. The
    peak-to-runner-up gap cannot see this because it looks only at the top two blocks, and the
    plateau cannot because it counts blocks rather than measuring how fast the temperature drops.

    ``fraction`` is expressed as a share of blocks rather than a count, so the metric is at least
    *computable* across floorplans with different block counts -- which is what made the transfer
    test above possible, and it failed on the physics rather than on the units. The default of
    0.05 is not delicate within a floorplan: the split survives cleanly from 0.02 to 0.20.
    """
    if not 0.0 < fraction <= 1.0:
        raise ValueError('fraction must be in (0, 1], got {!r}'.format(fraction))
    t = _sorted_desc(temps)
    if t.size < 2:
        raise ValueError('need at least two blocks to measure a depth')
    n = max(1, int(round(fraction * t.size)))
    idx = min(n, t.size - 1)
    return {'depth_K': float(t[0] - t[idx]), 'n_blocks': int(idx),
            'fraction': float(fraction), 'n_total': int(t.size),
            'span_K': float(t[0] - t[-1])}


def peak_to_runner_up_gap(temps):
    """How far the hottest block stands clear of the next one [K].

    Robust and device-free: it is what "clip-one gain" reduces to whenever the runner-up lies
    within the device's lift, which on every die measured here it does. Measured across the
    eleven tier shapes it spans 1.18-8.07 K, a 6.8x range.
    """
    t = _sorted_desc(temps)
    if t.size < 2:
        raise ValueError('need at least two blocks to have a runner-up')
    return float(t[0] - t[1])


# ---------------------------------------------------------------------------------------------
# Power-density concentration -- LADDER_GEN0 section 3, "not built"
# ---------------------------------------------------------------------------------------------
def power_density_concentration(powers, areas_mm2):
    """How unevenly power density is distributed over the die.

    ``powers`` and ``areas_mm2`` are dicts keyed by block name. Returns the Gini coefficient of
    the area-weighted power-density distribution plus the top-decile share, both dimensionless
    and both computable from a trace and a floorplan alone -- no solve.

    Gini is area-weighted on purpose: an unweighted Gini over blocks would let a thousand tiny
    blocks outvote the few large ones that carry the die's power.
    """
    names = [k for k in powers if k in areas_mm2]
    if not names:
        raise ValueError('no block names common to powers and areas')
    p = np.array([float(powers[k]) for k in names])
    a = np.array([float(areas_mm2[k]) for k in names])
    if np.any(a <= 0):
        raise ValueError('every block needs a positive area')
    d = p / a                                     # W/mm^2 per block
    order = np.argsort(d)
    d, a = d[order], a[order]
    w = a / a.sum()                               # area weights
    cum_w = np.cumsum(w)
    cum_p = np.cumsum(d * w)
    if cum_p[-1] <= 0:
        return {'gini': 0.0, 'top_decile_share': 0.0, 'n_blocks': len(names)}
    cum_p = cum_p / cum_p[-1]
    # Gini = 1 - 2 * area under the Lorenz curve (trapezoid over the area-weighted axis).
    # np.trapz is deprecated in numpy 2; np.trapezoid is its replacement and does not exist in 1.x.
    _trapz = getattr(np, 'trapezoid', None) or np.trapz
    lorenz_area = _trapz(np.concatenate(([0.0], cum_p)), np.concatenate(([0.0], cum_w)))
    gini = float(1.0 - 2.0 * lorenz_area)
    # Share of total power carried by the hottest-density decile OF AREA.
    top = cum_w >= 0.9
    top_share = float(1.0 - cum_p[~top][-1]) if (~top).any() else 1.0
    return {'gini': max(gini, 0.0), 'top_decile_share': top_share, 'n_blocks': len(names)}


# ---------------------------------------------------------------------------------------------
# Thermal aspect -- LADDER_GEN0 section 3, "not built"
# ---------------------------------------------------------------------------------------------
def thermal_aspect(floorplan, block_name):
    """How far a block sits from the nearest die edge, normalised.

    Heat leaving a block spreads laterally before it reaches the cooled surface, so a block in the
    middle of the die is worse off than the same block at its edge. Returns the absolute distance
    in um and that distance divided by half the die's shorter side, so 0 means "on the edge" and
    1 means "as central as this die allows".

    Geometry only -- no solve, no power map.
    """
    el = floorplan[block_name]
    minx, maxx = float(floorplan.minx), float(floorplan.maxx)
    miny, maxy = float(floorplan.miny), float(floorplan.maxy)
    cx = 0.5 * (float(el.minx) + float(el.maxx))
    cy = 0.5 * (float(el.miny) + float(el.maxy))
    d = min(cx - minx, maxx - cx, cy - miny, maxy - cy)
    half_short = 0.5 * min(maxx - minx, maxy - miny)
    return {'distance_um': float(d),
            'normalised': float(d / half_short) if half_short > 0 else 0.0,
            'block': block_name}


def hot_block_thermal_aspect(floorplan, temps):
    """:func:`thermal_aspect` of whichever block is hottest -- the metric LADDER_GEN0 names."""
    hottest = max(temps, key=temps.get)
    out = thermal_aspect(floorplan, hottest)
    out['peak_C'] = float(temps[hottest])
    return out
