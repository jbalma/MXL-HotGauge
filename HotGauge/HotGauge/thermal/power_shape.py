"""Power-map SHAPE as an independent variable -- the control the density ladder never had.

Why this exists
---------------
Five hypotheses for the high-density ceiling have now been eliminated by measurement: the bulk
floor, the leakage extrapolation, the array envelope, ``core_other``, and the results-broadcast
bus. The last two were eliminated the same way and the pattern is the point --

* shrink ``core_other`` from 15.68 % of die area to 0.94 %, and ``RBB`` runs away instead. The
  ceiling does not move (``docs/evidence/rbb_is_the_gate.json``).
* amortize ``RBB`` into the units it spans, and ``core_other`` runs away instead. The ceiling
  does not move (``docs/evidence/rbb_bracket.json``).

A ceiling that survives the removal of whichever block happens to be hottest is not a property of
that block, and chasing a third one is not an experiment. The question that separates the two
remaining explanations is about the map as a whole:

    **is the ceiling set by CONCENTRATION, or by the die average?**

So hold the total power fixed and vary only how it is spread. ``uniform_density_map`` builds the
limiting case -- every block at the same W/mm^2, no hot block by construction. Run the same ladder
on it and on the real map:

* the flat die also loses its steady state at ~2.0 W/mm^2  -> the ceiling is the package and the
  leakage model. It is physics, the artefact hypothesis is finished, and 2.0 W/mm^2 is a real
  number rather than an accounting bound.
* the flat die holds well past it -> the gate is concentration. That is a measurable property of a
  floorplan, and this project already has metrics for it (``floorplan_metrics``).

`[!]` These functions work on **floorplan-named** power maps -- ``{block: W}`` as the solver sees
them -- not on McPAT-named traces. That is deliberate and it is the only place the question can be
asked honestly: a McPAT trace reaches the die through aggregate splitting (L3) and modelled extras
(IMC/IO/SoC), so flattening it would leave a die that is not flat. Drive the solve with
``ICEThermalSolver(already_dice_named=True)`` and ``run_leakage_feedback(name_map=lambda u: u)``,
as ``examples/uniform_density_probe.py`` does.
"""
import numpy as np


def block_power_map(dice_trace, areas, step=0):
    """``{block: W}`` for the blocks of ``areas``, from a floorplan-named trace.

    Keys of the trace that are not floorplan blocks -- the McPAT aggregates ``Processor``,
    ``NUCA``, ``BUSES`` and friends -- are dropped, and their total is returned alongside so a
    caller can see how much of the trace never reaches the die. They are not solved, so counting
    them in a die average is how a 2.0 W/mm^2 die gets reported as 4.3.
    """
    on, off = {}, 0.0
    for k, v in dice_trace.powers.items() if hasattr(dice_trace, 'powers') else dice_trace.items():
        w = float(np.ravel(v)[step])
        if k in areas:
            on[k] = w
        else:
            off += w
    return on, off


def uniform_density_map(areas, total_W):
    """Every block at the same W/mm^2, summing to ``total_W``.

    The limiting flat case: no block is hot, so any ceiling the solve then finds cannot be
    attributed to a hot block. Blocks of zero area get zero power.
    """
    total_area = float(sum(areas.values()))
    if total_area <= 0.0:
        raise ValueError('floorplan has no area')
    if total_W < 0.0:
        raise ValueError('total_W must be >= 0, got {!r}'.format(total_W))
    q = float(total_W) / total_area
    return {b: q * a for b, a in areas.items()}, q


def scale_map_to_density(powers, areas, density_W_per_mm2):
    """Rescale a block power map so the die average is ``density_W_per_mm2``, shape unchanged.

    The companion to ``uniform_density_map``: same total, same die, but every block keeps its
    share. Running both at one density is the concentration test -- one variable, and it is the
    one nobody has held fixed before.
    """
    total_area = float(sum(areas.values()))
    have = float(sum(powers.values()))
    if have <= 0.0:
        raise ValueError('power map is empty; nothing to rescale')
    want = float(density_W_per_mm2) * total_area
    f = want / have
    return {b: w * f for b, w in powers.items()}, f


def concentration(powers, areas):
    """Summary statistics of a block power map, for reporting alongside a verdict.

    Gini and top-decile share come from ``floorplan_metrics.power_density_concentration`` rather
    than being recomputed here -- it is the project's registered concentration metric, it is the
    one the ISA work regressed against cost, and two implementations of a Lorenz curve is one too
    many. A uniform map must come back with Gini 0 and ``peak_over_mean`` 1; that equality is what
    makes the two arms comparable rather than merely differently named.
    """
    from HotGauge.thermal.floorplan_metrics import power_density_concentration
    items = [(b, powers.get(b, 0.0), areas[b]) for b in areas if areas[b] > 0]
    dens = np.array([w / a for _, w, a in items], dtype=float)
    area = np.array([a for _, _, a in items], dtype=float)
    total_W = float(sum(w for _, w, _ in items))
    mean = total_W / float(area.sum())
    conc = power_density_concentration({b: w for b, w, _ in items},
                                       {b: a for b, _, a in items})
    top = max(items, key=lambda t: (t[1] / t[2]))
    return {'mean_W_per_mm2': mean,
            'peak_W_per_mm2': float(dens.max()),
            'p99_W_per_mm2': float(np.percentile(dens, 99)),
            'p90_W_per_mm2': float(np.percentile(dens, 90)),
            'gini': conc['gini'],
            'top_decile_share': conc['top_decile_share'],
            'peak_over_mean': float(dens.max() / mean) if mean > 0 else None,
            'top_block': top[0],
            'total_W': total_W,
            'die_mm2': float(area.sum())}
