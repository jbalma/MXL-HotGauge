"""Can a floorplan actually hold two temperatures at once? The zone-separability metric.

Why this exists
---------------
Every floorplan metric this project has built answers the same shape of question: *given that we
are trying to pull the peak down, how hard is this die to cool?* ``relative_plateau`` was the last
of them standing and it failed its transfer test on 28 August.

The photonic-cooling architecture argument (``docs/Photonic_Cooling_Devices___v9.pdf`` Sections 1.14
and 10.8) asks a different question, and it inverts the objective. Chip power splits into a dynamic
term that wants to run **hot** -- the exergy an LPC can recover from chip heat is bounded by the
Carnot factor ``phi = 1 - T0/Th``, which nearly triples between 350 K and 500 K -- and a static term
that wants to run **cold**, because subthreshold leakage carries ``exp(-Vth/(n kB Tj/q))``. Those
two live in different places on the die, so the proposal is a die held at several temperatures at
once: hot compute islands beside cold SRAM.

Only spatially-selective cooling can even attempt that. But *attempting* it is a floorplan
question, and it is the one this module measures: **the two zones have to be thermally separable,
and silicon is an extremely good lateral conductor.**

What is measured, and why it is a watt rather than a score
----------------------------------------------------------
A geometric "separability score" would be easy and useless. What decides whether a zone can exist
is a power balance, so this returns one:

* **the prize** -- how much leakage the cold zone stops drawing when it is cooled, from this
  project's own calibrated curve (``leakage_calibration/``);
* **the price** -- how much heat leaks laterally *back* across the zone boundary through the
  silicon, which the cold zone's cooler must then also remove.

Their ratio is ``isolation_ratio``. Below 1 the gradient costs more than it saves and collapses;
the zone is not buildable on that floorplan at that temperature split.

The lateral term, and why die thickness cancels
------------------------------------------------
Across a zone boundary of length ``P`` in a slab of thickness ``t``, conducting a temperature step
``dT``, the parasitic flow is ``Q = k * (P*t) * dT / L``, where ``L`` is the distance over which the
step heals. In a monolithic die ``L`` is not a free parameter: a step in boundary condition on a
slab heals over a distance of order the slab thickness, so ``L ~ t`` and

    Q  ~  k * P * dT                                        (thickness-independent)

**Thinning the die does not help.** It shrinks the conducting cross-section and shortens the
healing length in equal measure. That is the central result here, and it is why the answer does not
depend on the one geometric parameter a reader would most want to argue about. Breaking the path --
an isolation trench, or physically separate dies -- is a different intervention, and
``trench_transition_um`` prices it.

Provenance
----------
* **Measured (ours)**: the per-block dynamic/static split, from McPAT on the project trace
  (``block_powers_split_*.json``); the leakage-versus-temperature curve
  (``leakage_calibration/``); the block geometry, from the floorplans in use.
* **Reference**: silicon thermal conductivity against temperature, ``SILICON_K_W_MK``, standard
  literature (Glassbrenner & Slack 1964 and successors). Not measured here.
* **The honest limit, and it bounds the headline claim**: McPAT refuses temperatures outside
  300-400 K -- *"Temperature must be between 300 and 400 Kelvin and multiple of 10"* -- so the
  calibrated curve stops at 310 K and **clamps** below it. The cold zone Section 10.8 asks for is
  150-250 K, entirely outside it. ``leakage_saving_W`` therefore refuses to extrapolate silently:
  it reports the saving it can defend and flags how much of the requested span it could not see.
"""
import math

#: Silicon thermal conductivity against temperature [W/m.K]. **Reference values**, not measured
#: here. The shape is the point: conductivity RISES steeply as silicon is cooled, because umklapp
#: phonon scattering freezes out. A cold zone is therefore harder to isolate than a hot one -- the
#: colder it gets, the better its surroundings conduct heat into it.
SILICON_K_W_MK = {
    100: 884.0, 150: 410.0, 200: 266.0, 250: 191.0, 300: 148.0,
    350: 124.0, 400: 105.0, 450: 92.0, 500: 80.0, 600: 65.0,
}

#: Fraction of a block's power that must be static before it is a cold-zone candidate.
#: 0.5 is a deliberate midpoint: on the project trace the split is bimodal, not graded -- L2 is
#: 80.3% static and L3 is 97.7%, while the FPU is 0.3% and the ALUs 2-5% -- so any threshold
#: between about 0.3 and 0.9 selects the same blocks.
COLD_ZONE_STATIC_FRACTION = 0.5

#: Lowest temperature the project's calibrated leakage curve was measured at. Below this the model
#: clamps, so a "saving" computed there is an artefact of the clamp rather than physics.
CALIBRATION_FLOOR_K = 310.0


def silicon_k(T_K):
    """Silicon thermal conductivity [W/m.K] at ``T_K``, linearly interpolated in the table."""
    ts = sorted(SILICON_K_W_MK)
    if T_K <= ts[0]:
        return SILICON_K_W_MK[ts[0]]
    if T_K >= ts[-1]:
        return SILICON_K_W_MK[ts[-1]]
    for a, b in zip(ts, ts[1:]):
        if a <= T_K <= b:
            f = (T_K - a) / float(b - a)
            return SILICON_K_W_MK[a] + f * (SILICON_K_W_MK[b] - SILICON_K_W_MK[a])
    raise AssertionError('unreachable')


def mean_silicon_k(t_cold_K, t_hot_K, n=32):
    """Conductivity averaged across the gradient the boundary actually spans.

    Averaging matters and is not fussiness: k varies 2.6x between 200 K and 400 K, so evaluating it
    at either endpoint biases the parasitic term by most of a factor of two.
    """
    lo, hi = sorted((float(t_cold_K), float(t_hot_K)))
    if hi - lo < 1e-9:
        return silicon_k(lo)
    return sum(silicon_k(lo + (hi - lo) * (i + 0.5) / n) for i in range(n)) / n


def shared_edge_mm(a, b, tol_um=1.0):
    """Length of boundary two axis-aligned blocks share [mm]. ``(x, y, w, h)`` in mm.

    A tolerance is required rather than optional: floorplan coordinates are snapped to the solver
    grid, so blocks that abut exactly in the design abut to within a rounding step on disk.
    """
    tol = tol_um / 1000.0
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if abs((ax + aw) - bx) <= tol or abs((bx + bw) - ax) <= tol:
        return max(0.0, min(ay + ah, by + bh) - max(ay, by))
    if abs((ay + ah) - by) <= tol or abs((by + bh) - ay) <= tol:
        return max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    return 0.0


def zone_boundary_mm(geometry, zone_of, tol_um=1.0):
    """Total boundary length between differently-zoned blocks [mm].

    ``geometry`` is ``{block: (x, y, w, h)}`` in mm; ``zone_of`` maps a block to a zone label.
    Blocks whose zone is ``None`` are ignored -- they belong to no zone and their edges are not a
    zone boundary.
    """
    names = sorted(geometry)
    total = 0.0
    per_pair = {}
    for i, n in enumerate(names):
        zn = zone_of(n)
        if zn is None:
            continue
        for m in names[i + 1:]:
            zm = zone_of(m)
            if zm is None or zm == zn:
                continue
            L = shared_edge_mm(geometry[n], geometry[m], tol_um)
            if L > 0:
                total += L
                key = tuple(sorted((zn, zm)))
                per_pair[key] = per_pair.get(key, 0.0) + L
    return total, per_pair


def boundary_conductance_W_per_K(boundary_mm, t_cold_K, t_hot_K, thickness_um=200.0,
                                 trench_width_um=None, bridge_thickness_um=None):
    """Thermal conductance across a zone boundary [W/K]. The quantity the floorplan actually sets.

    **Monolithic** (no trench): a step in boundary condition on a slab heals over a distance of
    order the slab thickness, so ``G = k * (P*t) / t = k * P`` -- **independent of die thickness**.
    Thinning shrinks the conducting cross-section and the healing length in equal measure, so it
    does not help. This is the single most useful fact in the module.

    **Trenched**: a trench does not lengthen the healing path, it *cuts the cross-section*. Heat
    must cross through whatever silicon bridge remains beneath the trench, over the trench's width:
    ``G = k * P * t_bridge / w_trench``. Both a deeper trench (smaller ``bridge_thickness_um``) and
    a wider one reduce it. Passing one of the two without the other is refused rather than guessed.
    """
    k = mean_silicon_k(t_cold_K, t_hot_K)
    P = float(boundary_mm) * 1e-3
    if (trench_width_um is None) != (bridge_thickness_um is None):
        raise ValueError('a trench needs both trench_width_um and bridge_thickness_um -- its '
                         'width sets the path length and the surviving bridge sets the '
                         'cross-section, and neither alone determines the conductance')
    if trench_width_um is None:
        return k * P                                    # monolithic; thickness cancels
    return k * P * (float(bridge_thickness_um) * 1e-6) / (float(trench_width_um) * 1e-6)


def parasitic_boundary_W(boundary_mm, t_cold_K, t_hot_K, thickness_um=200.0,
                         trench_width_um=None, bridge_thickness_um=None):
    """Heat conducted laterally back across a zone boundary [W]."""
    dT = abs(float(t_hot_K) - float(t_cold_K))
    return boundary_conductance_W_per_K(boundary_mm, t_cold_K, t_hot_K, thickness_um,
                                        trench_width_um, bridge_thickness_um) * dT


def leakage_saving_W(zone_leakage_W, t_from_K, t_to_K, model, t_ref_K):
    """Leakage the cold zone stops drawing, and how much of the span the model could not see.

    ``zone_leakage_W`` is the zone's leakage at ``t_from_K``. Returns a dict rather than a number
    because the number alone would be misleading: the calibrated curve stops at
    ``CALIBRATION_FLOOR_K`` and clamps below, so a request to 200 K silently returns the 310 K
    value. ``unseen_K`` is how much of the requested cooling the model has no evidence for, and
    ``defensible`` is False whenever that is non-zero.
    """
    t_from, t_to = float(t_from_K), float(t_to_K)
    t_eval = max(t_to, CALIBRATION_FLOOR_K)
    rel_from, rel_to = model.scale(t_from), model.scale(t_eval)
    saved = zone_leakage_W * (1.0 - rel_to / rel_from) if rel_from > 0 else 0.0
    unseen = max(0.0, CALIBRATION_FLOOR_K - t_to)
    return {'saving_W': saved,
            'ratio': (rel_from / rel_to) if rel_to > 0 else float('inf'),
            'evaluated_to_K': t_eval, 'requested_to_K': t_to, 'unseen_K': unseen,
            'defensible': unseen == 0.0,
            'note': ('the calibrated curve stops at {:.0f} K and clamps below it, so {:.0f} K of '
                     'the requested cooling is unevidenced -- see Section 10.8 vs '
                     'leakage_calibration/'.format(CALIBRATION_FLOOR_K, unseen)
                     if unseen else 'entirely inside the measured range')}


def zone_separability(geometry, zone_of, zone_leakage_W, t_cold_K, t_hot_K, model, t_ref_K,
                      thickness_um=200.0, trench_width_um=None, bridge_thickness_um=None,
                      cold_zone='cold'):
    """Is a two-temperature split worth building on this floorplan? Returns the power balance.

    ``isolation_ratio`` is the leakage saved divided by the heat conducted back in. Below 1 the
    cold zone's cooler spends more removing parasitic in-flow than the cooling saves, and the
    intended gradient cannot be held.
    """
    boundary_mm, per_pair = zone_boundary_mm(geometry, zone_of)
    areas = {}
    for n, (x, y, w, h) in geometry.items():
        z = zone_of(n)
        if z is not None:
            areas[z] = areas.get(z, 0.0) + w * h
    total_area = sum(g[2] * g[3] for g in geometry.values())
    G = boundary_conductance_W_per_K(boundary_mm, t_cold_K, t_hot_K, thickness_um,
                                     trench_width_um, bridge_thickness_um)
    dT = abs(float(t_hot_K) - float(t_cold_K))
    parasitic = G * dT
    saving = leakage_saving_W(zone_leakage_W, t_hot_K, t_cold_K, model, t_ref_K)
    ratio = (saving['saving_W'] / parasitic) if parasitic > 0 else float('inf')
    # The spec form: what the boundary conductance would have to be for the zone to break even.
    # This is the number to hand a packaging engineer, because it does not depend on how the
    # isolation is built -- only on how much heat it is allowed to pass.
    g_max = saving['saving_W'] / dT if dT > 0 else float('inf')
    return {
        'zone_area_mm2': areas,
        'cold_zone_share': areas.get(cold_zone, 0.0) / total_area if total_area else 0.0,
        'die_area_mm2': total_area,
        'boundary_mm': boundary_mm, 'boundary_by_pair_mm': per_pair,
        'boundary_per_mm2': boundary_mm / total_area if total_area else 0.0,
        't_cold_K': float(t_cold_K), 't_hot_K': float(t_hot_K),
        'mean_k_W_mK': mean_silicon_k(t_cold_K, t_hot_K),
        'thickness_um': thickness_um, 'trench_width_um': trench_width_um,
        'bridge_thickness_um': bridge_thickness_um,
        'boundary_conductance_W_per_K': G,
        'max_conductance_W_per_K': g_max,
        'conductance_excess': (G / g_max) if g_max > 0 else float('inf'),
        'parasitic_W': parasitic,
        'leakage_saving': saving,
        'isolation_ratio': ratio,
        'buildable': ratio >= 1.0,
    }


#: Illustrative 2.5D package numbers, for the comparison the monolithic result forces. **Not a
#: package model** -- stated inputs, one arithmetic step, so the reader can substitute their own.
#: Organic substrate in-plane conductivity is from the pack's own materials note (~15-30 W/m.K
#: from the copper planes; 20 taken here), and the effective thickness is the build-up layers that
#: actually carry lateral heat.
PACKAGE_SUBSTRATE_K_W_MK = 20.0
PACKAGE_LATERAL_THICKNESS_UM = 200.0


def package_boundary_conductance_W_per_K(edge_mm, gap_mm,
                                         k_W_mK=PACKAGE_SUBSTRATE_K_W_MK,
                                         thickness_um=PACKAGE_LATERAL_THICKNESS_UM):
    """Lateral conductance between two side-by-side dies through the substrate [W/K].

    The comparison that matters once the monolithic answer comes back three orders of magnitude
    short: putting the cold zone on its own die replaces a silicon path with a substrate path, and
    the substrate is both far less conductive and far longer.
    """
    return float(k_W_mK) * (float(edge_mm) * 1e-3) * (float(thickness_um) * 1e-6) \
        / (float(gap_mm) * 1e-3)
