"""Recoverable work from chip heat: the Carnot factor, the LPC ceiling, and the per-tile map.

Why this exists
---------------
Every thermal result in this project scores cooling by **temperature** -- peak pulled down, margin
held, watts spent. ``docs/Photonic_Cooling_Devices___v9.pdf`` Chapter 1 adds a second scoring axis
that runs the *other way*: heat lifted from a hot chip carries exergy, and the hotter the chip the
more of it is convertible to work.

    phi(T_h) = 1 - T_0 / T_h                                                          (Carnot factor)

At an ambient of 295 K that is 0.157 at 350 K, 0.26 at 400 K, 0.41 at 500 K. A tile lifted from
350 K to 500 K nearly **triples** the recoverable exergy per dissipated joule. So "cool everything"
stops being obviously right, and the die acquires an optimisation it did not have before.

The four equations this module implements, from Chapter 1
-----------------------------------------------------------
* **(1.12)** the fluorescence exergy: ``B_f <= eta_c P_L [1 + eta_AS phi]``
* **(1.13)** the LPC's thermodynamic ceiling:
  ``eta_P <= eta_P_max = [1 + eta_AS phi] / (1 + eta_AS)``
* **(1.15)** the sharp self-powering condition: ``eta_L eta_c [1 + eta_AS phi] >= 1``
* **(1.16)** rearranged: ``eta_AS >= (1/(eta_L eta_c) - 1) / phi``

(1.15) is the useful one. It is why ``T_h`` is a design knob rather than an inherited property:
raising ``T_h`` widens ``phi`` and the condition that reads as marginal at 350 K reads as
comfortable at 500 K.

`[!]` The temperature that belongs in phi is the EXTRACTOR's, not the junction's
--------------------------------------------------------------------------------
This is the trap, and it is easy to get wrong in a way that flatters every number. The Carnot
factor is set by the temperature of the reservoir the heat is lifted *from* -- which is the
anti-Stokes medium in the cold plate, not the silicon junction. Those are not the same
temperature: the extractor sits above the die across a conduction path, so it runs **cooler** than
the junction by the drop across that path, and the drop grows with burial depth and with power
density. Using the junction temperature overstates ``phi``, and therefore overstates recoverable
work, by exactly that drop.

``examples/extractor_temperature_probe.py`` measures the drop; ``phi_from_field`` takes whichever
temperature you hand it and ``exergy_map`` records which one was used, so a result cannot silently
be computed on the wrong reservoir.

What is measured and what is not
--------------------------------
* **Measured**: the temperature fields, from 3D-ICE solves in this repository.
* **Reference**: ``T_0``. Ambient is a modelling choice; 295 K is the book's, and the project's
  own ``SIMSCALE_T0_K`` may differ -- pass it explicitly rather than inheriting a default.
* **Not modelled here at all**: ``eta_AS``'s own temperature dependence. Chapter 1c notes that the
  anti-Stokes efficiency rises with ``T_h`` up to the extractor material's quenching temperature
  and turns over above it, which puts a material-dependent optimum on ``T_h``. Nothing in this
  repository models that curve, so ``eta_AS`` is taken as a constant here and every "hotter is
  better" statement carries an unmodelled ceiling.
"""
import math

#: Ambient the book uses for its numerical examples [K].
BOOK_T0_K = 295.0


def carnot_factor(T_h_K, T_0_K=BOOK_T0_K):
    """``phi = 1 - T_0/T_h`` -- the fraction of heat lifted at ``T_h`` that can become work.

    Negative below ambient, and deliberately not clamped: a tile cooled below ambient has no
    exergy to give and the sign is the honest signal that it is a consumer rather than a source.
    """
    T_h = float(T_h_K)
    if T_h <= 0:
        raise ValueError('T_h must be positive, got {}'.format(T_h_K))
    return 1.0 - float(T_0_K) / T_h


def lpc_ceiling(eta_AS, T_h_K, T_0_K=BOOK_T0_K):
    """Equation (1.13): the second-law ceiling on the LPC's optical-to-electrical efficiency.

    The pump-derived part of the fluorescence is work-like and fully recoverable in principle; the
    heat-derived part is Carnot-limited. The ceiling is their weighted mean.
    """
    phi = carnot_factor(T_h_K, T_0_K)
    return (1.0 + float(eta_AS) * phi) / (1.0 + float(eta_AS))


def loop_gain(eta_L, eta_c, eta_AS, T_h_K, T_0_K=BOOK_T0_K):
    """Left side of the sharp self-powering condition. ``>= 1`` means the loop self-powers.

    **v91 numbering: this is equation (1.16),** ``eta_P * eta_cpl * [1 + eta_ASF * (1 - T_0/T_h)]``.
    Validated against the book's own worked examples 1-3 of Section 1.12 to three figures.

    `[!]` **``eta_c`` here is the COUPLING efficiency ``eta_cpl``, not the LPC efficiency.** The
    LPC has already been eliminated from this expression by substituting its exergy ceiling
    (1.14); folding ``eta_LPC`` in as well double-counts it and makes the requirement look far
    harder than it is. Passing 0.92 for a 92 %-efficient LPC inflated the required ``eta_ASF`` at
    600 K from 0.347 to 0.548 before this was caught on 30 August 2026.

    To keep a practical LPC irreversibility, use the factorisation (1.15)
    ``eta_LPC = eta_P_int * eta_LPC_max`` and multiply this result by ``eta_P_int`` -- which is a
    fraction OF THE CEILING, not an absolute opt->elec efficiency.

    Arguments keep their historical names for back-compatibility; read ``eta_L`` as ``eta_P``
    (pump laser wall-plug), ``eta_c`` as ``eta_cpl``, ``eta_AS`` as ``eta_ASF``.
    """
    return float(eta_L) * float(eta_c) * (1.0 + float(eta_AS) * carnot_factor(T_h_K, T_0_K))


def self_powering_T_h(eta_ASF, eta_P, eta_cpl=1.0, T_0_K=BOOK_T0_K):
    """Lowest source temperature at which (1.16) closes, for a given extractor and laser.

    The inverse of :func:`eta_AS_required`, and the more useful direction now that extractor
    efficiency is a material choice rather than a hard ceiling: it answers "how hot must the
    logic run for THIS extractor to close the loop". Returns ``None`` if no finite temperature
    suffices (required Carnot factor >= 1).
    """
    if eta_ASF <= 0.0:
        return None
    phi_needed = (1.0 / (float(eta_P) * float(eta_cpl)) - 1.0) / float(eta_ASF)
    if phi_needed >= 1.0:
        return None
    return float(T_0_K) / (1.0 - phi_needed)


def eta_AS_required(eta_L, eta_c, T_h_K, T_0_K=BOOK_T0_K):
    """Equation (1.17) in v91 (was 1.16): the anti-Stokes efficiency self-powering demands at this ``T_h``.

    ``inf`` when the chip is at or below ambient -- there is no Carnot factor to work with, and no
    finite ``eta_AS`` closes the loop.
    """
    phi = carnot_factor(T_h_K, T_0_K)
    if phi <= 0:
        return float('inf')
    return (1.0 / (float(eta_L) * float(eta_c)) - 1.0) / phi


def exergy_map(block_temps_K, block_powers_W, T_0_K=BOOK_T0_K, temperature_is='junction'):
    """Recoverable exergy per block, and the die integral. ``{block: T}``, ``{block: P}``.

    Returns per-block ``phi`` and ``exergy_W = phi * P``, plus the die totals. ``temperature_is``
    is recorded verbatim in the result: ``phi`` computed on junction temperatures overstates the
    recoverable work, because the extractor the heat is actually lifted from is cooler. Nothing
    here corrects for that -- it records which reservoir was used so the reader can tell.
    """
    per = {}
    tot_P = tot_B = 0.0
    for blk, T in block_temps_K.items():
        P = float(block_powers_W.get(blk, 0.0))
        if P <= 0:
            continue
        phi = carnot_factor(T, T_0_K)
        per[blk] = {'T_K': float(T), 'power_W': P, 'phi': phi, 'exergy_W': phi * P}
        tot_P += P
        tot_B += phi * P
    return {
        'per_block': per,
        'die_power_W': tot_P,
        'die_exergy_W': tot_B,
        'die_mean_phi': (tot_B / tot_P) if tot_P > 0 else 0.0,
        'T_0_K': float(T_0_K),
        'temperature_is': temperature_is,
        'note': ('phi computed on {} temperatures. The Carnot factor is set by the reservoir the '
                 'heat is lifted FROM, which is the extractor, not the junction -- junction '
                 'temperatures overstate recoverable work by the conduction drop between them.'
                 .format(temperature_is)),
    }


def power_weighted_temperature(block_temps_K, block_powers_W):
    """The single ``T_h`` a uniform-temperature analysis would use, weighted by dissipation.

    Reported alongside the map because it is what a one-number treatment implicitly assumes, and
    the gap between ``phi(T_weighted)`` and the properly integrated ``die_mean_phi`` is the error
    that collapsing a die to one temperature introduces.
    """
    num = den = 0.0
    for blk, T in block_temps_K.items():
        P = float(block_powers_W.get(blk, 0.0))
        if P <= 0:
            continue
        num += P * float(T)
        den += P
    return (num / den) if den > 0 else float('nan')


def zone_additive_fom(zones, T_0_K=BOOK_T0_K):
    """Equation (10.29): the figure of merit when each zone has its own ``T_h``.

    ``zones`` is a list of dicts with ``perf_gain``, ``p_inj_W``, ``q_c_W``, ``cop``,
    ``d_p_leak_W`` (positive = leakage saved) and ``T_h_K``. The uniform-temperature FOM assumed
    one tile at one temperature; under thermal heterogeneity it becomes zone-additive, with hot
    zones contributing performance at a wide ``phi`` and cold zones shrinking the denominator by
    the leakage they stop drawing.
    """
    num = den = 0.0
    detail = []
    for z in zones:
        phi = carnot_factor(z['T_h_K'], T_0_K)
        cost = (float(z.get('p_inj_W', 0.0))
                + float(z.get('q_c_W', 0.0)) / max(float(z.get('cop', 1.0)), 1e-12)
                - float(z.get('d_p_leak_W', 0.0))
                - float(z.get('d_p_pdn_W', 0.0)))
        num += float(z.get('perf_gain', 0.0))
        den += cost
        detail.append({'zone': z.get('name'), 'phi': phi, 'cost_W': cost,
                       'perf_gain': float(z.get('perf_gain', 0.0))})
    return {'fom': (num / den) if den != 0 else float('inf'),
            'numerator': num, 'denominator': den, 'zones': detail, 'T_0_K': float(T_0_K)}
