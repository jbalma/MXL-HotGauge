"""Goal 3: photonic microrefrigeration (MR) as targeted heat removal in the HotGauge pipeline.

The model
---------
MR is injected as **negative power sources** at floorplan blocks. This is validated behaviour,
not an assumption: removing 0.5 W at ``cALU_0`` in a 35 W steady solve drops that block 10.7 K,
cools its neighbours (``RBB_0`` by 9.5 K), and leaves distant blocks essentially untouched.

**Thermal clipping, not bulk cooling.** MR removes only the heat needed to pull a block down to
a temperature target -- the *excess* -- rather than its whole heat load. That is what makes a
poor cooler COP acceptable: you pay to move a small amount of heat from exactly the place that
limits the clock. Two measured facts make the case:

* McPAT leakage is nearly flat below ~340 K and explodes above ~350 K (see
  ``examples/calibrate_leakage_model.py``), so cooling a cool block buys almost nothing while
  clipping a hot one buys a great deal.
* A core runs at one clock, set by its **hottest** block, so removing one hotspot lifts the
  frequency of the whole core.

Operating envelope (docs/Microrefrigeration_v1.pdf)
--------------------------------------------------
The MR stage is not unlimited. Defaults encode the documented envelope:

* cooling power density ``H`` ~1-10 W/mm^2 -- a block's removal is capped at ``H_max * area``
* temperature lift ``dT`` <~ 10 K
* spatial targeting <~100 um -- blocks narrower than this cannot be addressed individually; a
  spot cools a neighbourhood, which ``spot_limited`` flags rather than silently ignoring
* ``COP`` -- electrical cost is ``Q_removed / COP``. The working assumption is **0.2 (20 %
  efficiency)**, i.e. 5 W electrical per watt of heat removed; the literature range for
  thin-film uTEC practical COP is ~0.1-0.3. MR only wins because ``Q_removed`` is small and
  buys a disproportionate frequency gain; it is trivially a net loss if used as a bulk cooler.

Sensitivity is measured, not assumed
------------------------------------
Converting "this block is 20 K too hot" into "remove q watts" needs dT/dq [K/W] per block.
That is NOT derivable from the block's own thermal resistance -- lateral spreading dominates.
For ``cALU_0`` the naive R_die estimate gives 153 K for 0.5 W; the measured response is 10.7 K,
15x smaller. So ``run_mr_clipping`` measures the sensitivity by secant update across iterations
and never trusts an analytical value.
"""

import logging

import numpy as np

LOGGER = logging.getLogger(__name__)

#: Documented MR envelope
DEFAULT_H_MAX_W_PER_MM2 = 10.0
DEFAULT_DT_MAX_K = 10.0
#: Laser wall-plug efficiency (electrical -> optical pump). Maxwell Labs working assumption.
DEFAULT_LASER_WALLPLUG = 0.70
#: Laser power converter (LPC) cell efficiency, optical -> DC. Working assumption.
DEFAULT_LPC_EFFICIENCY = 0.90
#: Anti-Stokes fluorescence (ASF) / extractor efficiency: heat removed per watt of *optical*
#: pump delivered. Working assumption 0.20. NOTE this is an OPTICAL efficiency -- the
#: electrical COP is eta_asf * eta_laser, so 0.20 ASF at 70 % wall-plug is COP 0.14.
DEFAULT_ETA_ASF = 0.20
#: Optical-path collection loss between the cooling element and the LPC. 1.0 reproduces the
#: MXL-Photonic-Cooling-Power-Analysis.xlsx model exactly (it assumes perfect routing).
DEFAULT_COLLECTION_EFFICIENCY = 1.0

#: Smallest feature the cooling stage can be focused onto [um]. The realistic range is
#: **1-10 um**: ~1 um is roughly the diffraction limit at the pump wavelength, ~10 um a
#: conservative practical delivery limit. The default is the cautious end of that range.
#:
#: This was previously 100 um, which is wrong by 10-100x and materially understated what MR can
#: reach. On the 34-core die that excluded 37 of the 57 above-target blocks -- including the two
#: highest power densities on the chip, ``RBB`` (13.4 um) and ``iBuf`` (1.3 um). At 10 um the
#: reachable set is 44 of 57 hot blocks and 99.4% of die power; at 1 um it is all of it.
#:
#: Consequence worth stating plainly: spot size is **not** the binding constraint on photonic
#: cooling here. The block *selection policy* is -- ``run_mr_clipping`` cools only blocks above
#: ``target_K``, and on that die they carry ~10% of total power while 65% sits in a band 10-20 K
#: below the target, untouched.
DEFAULT_SPOT_MIN_UM = 10.0

#: What to do with a block narrower than ``spot_min_um``:
#:
#: * ``'dilute'``  -- illuminate the whole pixel: the block still gets the cooling it needs, but
#:   you pay for the pixel, so the laser cost rises by ``pixel_area / block_area``. This is what
#:   a real tile array does and is the default.
#: * ``'exclude'`` -- the block cannot be targeted at all. A conservative bound.
#: * ``'ideal'``   -- cool it in full at no penalty. This was the *de facto* behaviour before
#:   the policy existed, because ``spot_limited`` was computed and never acted on -- so every
#:   result predating this assumed perfect targeting at any feature size.
DEFAULT_SPOT_POLICY = 'dilute'
#: Maxwell Labs working assumption (2026-08-11): 20% MR efficiency, i.e. 5 W electrical per
#: watt of heat removed. The literature range for thin-film uTEC practical COP is ~0.1-0.3.
DEFAULT_COP = 0.2


class MRParams(object):
    """Microrefrigeration stage capability and cost.

    target_K       : temperature the clipper pulls hot blocks down to.
    h_max          : max cooling power density [W/mm^2] the stage can deliver.
    dt_max_K       : max temperature lift the stage can sustain.
    cop            : coefficient of performance; electrical cost = Q_removed / cop.
    spot_min_um    : spatial targeting limit; narrower blocks are flagged ``spot_limited``.
    max_total_W    : optional cap on total heat removed (a laser power budget).
    """

    def __init__(self, target_K, h_max=DEFAULT_H_MAX_W_PER_MM2, dt_max_K=DEFAULT_DT_MAX_K,
                 eta_asf=DEFAULT_ETA_ASF, spot_min_um=DEFAULT_SPOT_MIN_UM,
                 spot_policy=DEFAULT_SPOT_POLICY, max_total_W=None,
                 laser_wallplug=DEFAULT_LASER_WALLPLUG, lpc_efficiency=DEFAULT_LPC_EFFICIENCY,
                 collection_efficiency=DEFAULT_COLLECTION_EFFICIENCY, recover=True, cop=None):
        if target_K <= 0:
            raise ValueError('target_K must be > 0')
        if h_max <= 0:
            raise ValueError('h_max must be > 0')
        for name, val in (('laser_wallplug', laser_wallplug),
                          ('lpc_efficiency', lpc_efficiency),
                          ('collection_efficiency', collection_efficiency),
                          ('eta_asf', eta_asf)):
            if not 0.0 <= val <= 1.0:
                raise ValueError('{} must be in [0, 1], got {!r}'.format(name, val))
        self.target_K = float(target_K)
        self.h_max = float(h_max)
        self.dt_max_K = float(dt_max_K)
        self.spot_min_um = float(spot_min_um)
        if spot_policy not in ('ideal', 'exclude', 'dilute'):
            raise ValueError("spot_policy must be 'ideal', 'exclude' or 'dilute', got {!r}"
                             .format(spot_policy))
        self.spot_policy = spot_policy
        self.max_total_W = None if max_total_W is None else float(max_total_W)
        self.laser_wallplug = float(laser_wallplug)
        self.lpc_efficiency = float(lpc_efficiency)
        self.collection_efficiency = float(collection_efficiency)
        self.recover = bool(recover)
        if cop is not None:
            # Back-compat: an explicit electrical COP pins eta_asf = cop / eta_laser.
            if cop <= 0:
                raise ValueError('cop must be > 0')
            if self.laser_wallplug <= 0:
                raise ValueError('cannot derive eta_asf from cop with zero wall-plug')
            self.eta_asf = float(cop) / self.laser_wallplug
        else:
            self.eta_asf = float(eta_asf)

    @property
    def cop(self):
        """Electrical COP = heat removed per watt of electrical draw, BEFORE recovery.

        The spreadsheet parameterises the cooler by its *optical* efficiency ``eta_asf``
        (heat removed per watt of optical pump), so the electrical figure is
        ``eta_asf * eta_laser``: 20 % ASF at 70 % wall-plug is an electrical COP of 0.14,
        not 0.20. Keeping these distinct matters -- conflating them overstates the cooler
        by 1/eta_laser.
        """
        return self.eta_asf * self.laser_wallplug

    @property
    def breakeven_ratio(self):
        """``eta_LPC * (1 + eta_ASF) * eta_laser`` -- recovered power per watt drawn.

        This is the master design number from MXL-Photonic-Cooling-Power-Analysis.xlsx:

        * ``< 1`` -- MR costs net electrical power (the usual regime)
        * ``= 1`` -- self-sustaining: recovery exactly pays for the pump
        * ``> 1`` -- net-generating: the loop returns more electrical power than it draws,
          with the extracted chip heat as the additional energy source

        Collection loss multiplies it. With eta_LPC 0.90 and eta_laser 0.70, breakeven needs
        ``eta_ASF >= 0.587`` -- i.e. **the extractor, not the LPC, is the binding constraint**.
        """
        return (self.lpc_efficiency * self.collection_efficiency
                * (1.0 + self.eta_asf) * self.laser_wallplug)

    def __repr__(self):
        rec = ('eta_LPC={:.2f}, eta_ASF={:.2f}, eta_laser={:.2f} -> breakeven ratio {:.3f}'
               .format(self.lpc_efficiency, self.eta_asf, self.laser_wallplug,
                       self.breakeven_ratio)
               if self.recover else 'no recovery (eta_ASF={:.2f})'.format(self.eta_asf))
        return ('MRParams(target={:.1f} K, H<={:.1f} W/mm^2, dT<={:.1f} K, COP_elec={:.3f}, '
                'spot>={:.0f} um, {}{})'.format(
                    self.target_K, self.h_max, self.dt_max_K, self.cop, self.spot_min_um, rec,
                    '' if self.max_total_W is None else
                    ', budget<={:.2f} W'.format(self.max_total_W)))


def clipping_plan(block_temps_K, block_geom, params, sensitivity_K_per_W, t_floor_K=200.0):
    """Heat to remove per block [W] to clip everything above ``params.target_K``.

    block_temps_K       : {block: T_K}
    block_geom          : {block: {'area_mm2': .., 'min_dim_um': ..}}
    sensitivity_K_per_W : {block: dT/dq} -- how much this block cools per watt removed.
                          Measured, never assumed (see module docstring).

    Each block's removal is the smallest of what the excess needs and what the stage can do:

        q_need = (T - target) / sensitivity        (what would clip it)
        q_H    = h_max * area                      (cooling-density ceiling)
        q_dT   = dt_max / sensitivity              (temperature-lift ceiling)

    Returns ``(plan, detail)`` where plan is ``{block: q_W}`` (positive = heat removed) and
    detail records, per block, which limit bound it -- so a disappointing result can be traced
    to the physical constraint responsible rather than guessed at.
    """
    plan, detail = {}, {}
    for blk, T in block_temps_K.items():
        T = float(np.ravel(T)[-1]) if np.ndim(T) else float(T)
        if T <= t_floor_K or T <= params.target_K:
            continue
        geom = block_geom.get(blk)
        if geom is None:
            continue
        s = float(sensitivity_K_per_W.get(blk, 0.0))
        if s <= 0:
            # Without a positive measured sensitivity we cannot size the removal; skipping is
            # the honest choice (removing a guessed amount would be untraceable).
            detail[blk] = {'limit': 'no_sensitivity', 'q_W': 0.0, 'excess_K': T - params.target_K}
            continue
        excess = T - params.target_K
        q_need = excess / s
        q_H = params.h_max * geom['area_mm2']
        q_dT = params.dt_max_K / s
        q = min(q_need, q_H, q_dT)
        limit = ('need' if q == q_need else ('h_max' if q == q_H else 'dt_max'))
        if q <= 0:
            continue

        # A block narrower than the pixel pitch cannot be illuminated on its own. What happens
        # then is set by spot_policy -- see MRParams. Until this was added the flag below was
        # computed and never read, so every result silently assumed ideal targeting at any
        # feature size (i.e. the 1 um array), and changing spot_min_um did nothing at all.
        spot_limited = geom['min_dim_um'] < params.spot_min_um
        cost_mult = 1.0
        if spot_limited:
            if params.spot_policy == 'exclude':
                detail[blk] = {'limit': 'spot_limited', 'q_W': 0.0, 'excess_K': excess,
                               'q_need_W': q_need, 'q_h_max_W': q_H, 'q_dt_max_W': q_dT,
                               'spot_limited': True, 'achievable_dT_K': 0.0,
                               'cost_multiplier': float('inf')}
                continue
            if params.spot_policy == 'dilute':
                # The pixel is illuminated in full but only the block's area fraction of the
                # cooling lands on the block. Delivered q is unchanged; the laser bill is not.
                pixel_mm2 = (params.spot_min_um ** 2) / 1.0e6
                cost_mult = pixel_mm2 / max(geom['area_mm2'], 1e-12)
                limit = limit + '+spot_dilute'

        plan[blk] = q
        detail[blk] = {'limit': limit, 'q_W': q, 'excess_K': excess,
                       'q_need_W': q_need, 'q_h_max_W': q_H, 'q_dt_max_W': q_dT,
                       'spot_limited': spot_limited, 'cost_multiplier': cost_mult,
                       'achievable_dT_K': q * s}

    # A laser budget is spent on the blocks with the largest excess first: the hottest block
    # sets the clock, so the marginal watt is worth most there.
    if params.max_total_W is not None and plan:
        total = sum(plan.values())
        if total > params.max_total_W:
            order = sorted(plan, key=lambda b: -detail[b]['excess_K'])
            remaining, trimmed = params.max_total_W, {}
            for blk in order:
                if remaining <= 0:
                    detail[blk]['limit'] = 'budget_exhausted'
                    detail[blk]['q_W'] = 0.0
                    continue
                take = min(plan[blk], remaining)
                trimmed[blk] = take
                remaining -= take
                if take < plan[blk]:
                    detail[blk]['limit'] = 'budget'
                    detail[blk]['q_W'] = take
            plan = trimmed
    return plan, detail


def apply_cooling_to_trace(trace, plan, name_map):
    """Return a new trace with MR heat removal applied as negative power at mapped units.

    ``plan`` is keyed by floorplan block; the power trace is keyed by McPAT unit, so
    ``name_map`` bridges them. If several McPAT units map to one block, the removal is split
    between them in proportion to their power -- removing it all from one would distort the
    within-block distribution that 3D-ICE sees.
    """
    from HotGauge.power.traces import BasicPowerTrace

    by_block = {}
    for unit in trace.powers:
        blk = name_map(unit)
        if blk in plan:
            by_block.setdefault(blk, []).append(unit)

    powers = {u: np.array(v, dtype=float).copy() for u, v in trace.powers.items()}
    for blk, units in by_block.items():
        weights = np.array([max(float(np.sum(powers[u])), 0.0) for u in units], dtype=float)
        total = weights.sum()
        share = (weights / total) if total > 0 else np.full(len(units), 1.0 / len(units))
        for u, frac in zip(units, share):
            # plan is a steady removal rate in W, so it applies at every timestep.
            powers[u] = powers[u] - plan[blk] * frac
    return BasicPowerTrace(powers, trace.time_step)


def mr_accounting(plan, params, compute_power_W=None, detail=None):
    """Laser power, LPC recovery, and net cost -- the MXL-Photonic-Cooling-Power-Analysis model.

    Implements the spreadsheet's formulation exactly (validated against its MVP-1/2/3 cases)::

        P_laser    = Q / (eta_ASF * eta_laser)                  electrical draw
        P_removed  = eta_ASF * eta_laser * P_laser              = Q, by construction
        P_recovered= eta_LPC * collection * (1 + eta_ASF) * eta_laser * P_laser
        P_used     = P_laser - P_recovered = (1 - breakeven_ratio) * P_laser

    The ``(1 + eta_ASF)`` term is the physics that makes this interesting: the light reaching
    the LPC is the pump *plus* the heat that was up-converted into it, so the recoverable
    optical power exceeds what the laser emitted.

    **Net-generating operation is a regime, not an error.** When
    ``breakeven_ratio = eta_LPC * collection * (1 + eta_ASF) * eta_laser`` exceeds 1, the loop
    returns more electrical power than it draws and ``P_used`` goes negative -- the extracted
    chip heat is the additional source. The spreadsheet's own MVP-3 sits there
    (eta 0.85/0.92/0.62 -> ratio 1.267, P_used = -50.7 W on 190 W of laser), and it is a
    target regime, so it is reported plainly rather than flagged.

    What *is* checked is the **first law**: energy out must not exceed energy in
    (``P_recovered <= P_laser + Q``). That catches genuine bookkeeping bugs without
    editorialising about which efficiency combinations are achievable -- that judgement belongs
    to the device model, not here.

    With eta_laser 0.70 / eta_LPC 0.90 / eta_ASF 0.20 the ratio is 0.756, so MR still costs
    net power; breakeven at that laser and LPC needs eta_ASF >= 0.587, which makes the
    **extractor the binding constraint**.
    """
    q_total = float(sum(plan.values())) if plan else 0.0
    cop_elec = params.cop

    # Blocks narrower than the pixel are illuminated pixel-wide, so the laser is billed for the
    # whole pixel while only the block's share does useful work. ``detail`` carries that
    # multiplier from clipping_plan; without it we would silently price a diluted spot as if it
    # were perfectly focused -- which is exactly the bug the spot_policy work fixed.
    if detail:
        q_billed = float(sum(q * float(detail.get(b, {}).get('cost_multiplier', 1.0))
                             for b, q in plan.items()))
    else:
        q_billed = q_total
    gross = (q_billed / cop_elec) if cop_elec > 0 else 0.0

    if params.recover:
        ratio = params.breakeven_ratio
        recovered = ratio * gross
        optical_in = params.laser_wallplug * gross
        # Heat carried out is what was actually removed from the die, not what was billed.
        optical_out = optical_in + q_total
    else:
        ratio = 0.0
        recovered = optical_in = optical_out = 0.0
    net = gross - recovered

    # First law: what leaves as recovered electricity cannot exceed pump-in plus heat-in.
    first_law_ok = recovered <= gross + q_total + 1e-9
    if not first_law_ok:
        LOGGER.error(
            'MR accounting violates energy conservation: recovered %.4f W > laser %.4f W + '
            'heat %.4f W. Check eta_LPC/collection/eta_laser/eta_ASF.', recovered, gross, q_total)

    out = {'heat_removed_W': q_total, 'heat_billed_W': q_billed,
           'spot_dilution_overhead': (q_billed / q_total) if q_total > 0 else 1.0,
           'cop': cop_elec, 'eta_asf': params.eta_asf,
           'n_blocks_cooled': len(plan),
           'electrical_gross_W': gross, 'optical_in_W': optical_in,
           'optical_to_lpc_W': optical_out, 'recovered_W': recovered,
           'electrical_power_W': net,
           'breakeven_ratio': ratio,
           'net_generating': bool(q_total > 0 and net < 0),
           'self_sustaining': bool(ratio >= 1.0),
           'recovery_fraction': (recovered / gross) if gross > 0 else 0.0,
           'effective_cop': (q_total / net) if net > 0 else float('inf'),
           'first_law_ok': bool(first_law_ok)}
    if compute_power_W is not None:
        out['compute_power_W'] = float(compute_power_W)
        out['total_power_W'] = float(compute_power_W) + net
        out['mr_overhead_frac'] = net / float(compute_power_W) if compute_power_W else float('nan')
    return out


def estimate_sensitivity(temps_before_K, temps_after_K, plan, floor=1e-6):
    """Secant estimate of dT/dq [K/W] per block from one applied cooling step.

    Positive means the block got cooler when heat was removed, which is the physical sign.
    A non-positive result (block warmed despite cooling, e.g. because leakage feedback moved
    more than the removal did) is dropped rather than fed back as a negative gain, which would
    make the controller push heat the wrong way.
    """
    out = {}
    for blk, q in plan.items():
        if q <= floor:
            continue
        t0 = float(np.ravel(temps_before_K.get(blk, np.nan))[-1])
        t1 = float(np.ravel(temps_after_K.get(blk, np.nan))[-1])
        if not (np.isfinite(t0) and np.isfinite(t1)):
            continue
        s = (t0 - t1) / q
        if s > 0:
            out[blk] = s
    return out


def envelope_plan(block_geom, params, sensitivity_K_per_W, blocks=None, t_floor_K=200.0):
    """The most cooling the device can apply to each block, ignoring how much is needed.

    Obtained by asking ``clipping_plan`` about an unboundedly hot die, so ``q_need`` never binds
    and every block is capped by ``h_max * area`` or ``dt_max / sensitivity`` -- which also
    means the spot pitch and policy are applied by exactly the same code path as a normal plan.

    This is the anchor for the rescue regime: it is the most-cooled state the device can reach,
    so if the coupled system has no steady state even here, MR cannot rescue that operating
    point at all. That is a statement about the device, where the old path gave one about the
    solver.
    """
    names = list(blocks if blocks is not None else block_geom)
    hot = {b: params.target_K + 1.0e6 for b in names}
    return clipping_plan(hot, block_geom, params, sensitivity_K_per_W, t_floor_K=t_floor_K)


def _relax_plan_toward_target(plan, envelope, temps, params, sens, relax, t_floor_K):
    """One Newton step on the plan, from the cooled state: cool more where hot, less where cold.

    Symmetric by construction -- a block below target has its cooling *reduced* -- so an initial
    over-cool is corrected rather than locked in, which is the property the baseline-anchored
    scheme was written to get and only got when the baseline existed.
    """
    new = {}
    for blk, q_env in envelope.items():
        t = temps.get(blk)
        if t is None:
            continue
        t = float(np.ravel(t)[-1])
        if t <= t_floor_K:
            continue
        s = float(sens.get(blk, 0.0))
        if s <= 0:
            new[blk] = plan.get(blk, 0.0)
            continue
        step = (t - params.target_K) / s          # >0 wants more cooling, <0 wants less
        q = plan.get(blk, 0.0) + relax * step
        new[blk] = min(max(q, 0.0), q_env)
    return {b: q for b, q in new.items() if q > 0.0}


def run_mr_clipping(trace, thermal_solve_fn, block_geom, params, name_map,
                    initial_sensitivity=None, max_iter=6, tol_K=1.0, relax=0.7,
                    t_floor_K=200.0, status_fn=None, plan_mode='auto'):
    """Iterate MR cooling against the thermal solver until hot blocks reach the target.

    Structurally the same fixed point as the leakage loop: the plan changes the temperatures,
    which change the plan. Sensitivities start from ``initial_sensitivity`` (or a small
    positive seed) and are refined by secant update each iteration, so the controller learns
    the real dT/dq including lateral spreading instead of assuming it.

    Two ways to size the plan
    -------------------------
    ``plan_mode='baseline'`` (the original) sizes every plan from the UNCOOLED solve. Correct
    and cheap when the bare die has a steady state.

    **It is invalid in the rescue regime, which is the regime MR exists for.** There the
    uncooled solve diverges, so the field it plans from is whichever one the iteration happened
    to be passing through when a runaway guard fired. Measured on the 34-core die at 88 CFM:
    the baseline peak used to size the plan was 138.7 C at 1.12 W/mm^2 and 142.8 C at 1.15,
    giving plans of 0.561 W and 1.979 W -- a 3.5x difference between two points 3% apart in
    density. The small plan failed to arrest the runaway and the large one succeeded, so
    "does MR rescue this die" was decided by where a divergent sequence stopped. The rescue was
    correspondingly non-monotone: 1.10 yes, 1.12 no, 1.15 yes, 1.16 no.

    ``plan_mode='envelope'`` starts from the other side instead. It applies the full device
    envelope and relaxes the cooling *down* toward the target, so it never reads a divergent
    field:

      * if the fully-cooled system still has no steady state, MR cannot rescue this point --
        reported as ``reason='envelope insufficient'``;
      * otherwise the loop reduces cooling where blocks sit below target and adds it back where
        they sit above, converging on the *minimum* plan that holds the target.

    ``plan_mode='auto'`` (default) picks 'baseline' when the uncooled solve converged and
    'envelope' when it did not. That keeps previously-validated convergent-regime results
    unchanged while making the rescue regime mean something.

    ``status_fn`` is an optional zero-argument callable returning the status of the most recent
    solve (``{'diverged': ..., 'unconverged': ...}``) -- ``run_leakage_feedback`` callers can
    supply it directly. Without it 'auto' cannot tell the two cases apart and falls back to
    'baseline', so a caller that needs the rescue regime handled correctly must pass it.

    Returns a dict with the final plan, temperature trace, accounting, per-iteration history
    and a ``converged`` flag. Not converging is a real answer -- it means the envelope cannot
    clip this workload -- so it is reported, not raised.
    """
    if plan_mode not in ('auto', 'baseline', 'envelope'):
        raise ValueError("plan_mode must be 'auto', 'baseline' or 'envelope', got {!r}"
                         .format(plan_mode))
    sens = dict(initial_sensitivity or {})

    def _status():
        try:
            return dict(status_fn() or {}) if status_fn is not None else {}
        except Exception:                      # noqa: BLE001 - a broken probe must not decide physics
            LOGGER.warning('status_fn raised; treating the solve status as unknown')
            return {}

    # The plan is always recomputed against the UNCOOLED baseline using the latest measured
    # sensitivity. Planning against the already-cooled temperatures instead would let a first
    # overshoot stand forever: the loop would see nothing above target, declare success, and
    # report a laser budget several times larger than needed. Overspending must be corrected,
    # not just under-spending.
    base_temps = thermal_solve_fn(trace)
    base_status = _status()
    history = []

    mode = plan_mode
    if mode == 'auto':
        mode = 'envelope' if base_status.get('diverged') else 'baseline'
    if mode == 'envelope':
        return _run_mr_clipping_envelope(
            trace, thermal_solve_fn, block_geom, params, name_map, sens,
            max_iter=max_iter, tol_K=tol_K, relax=relax, t_floor_K=t_floor_K,
            status_fn=_status, base_temps=base_temps, base_status=base_status)

    base_hot = {b: float(np.ravel(t)[-1]) for b, t in base_temps.items()
                if float(np.ravel(t)[-1]) > max(t_floor_K, params.target_K)}

    if not base_hot:
        return {'plan': {}, 'detail': {}, 'temp_trace': base_temps, 'sensitivity': sens,
                'converged': True, 'iterations': 0, 'history': history,
                'accounting': mr_accounting({}, params),
                'reason': 'nothing above target; no cooling needed'}

    for b in base_hot:
        sens.setdefault(b, 1.0)

    plan, detail, temps = {}, {}, base_temps
    for it in range(max_iter):
        new_plan, detail = clipping_plan(base_hot, block_geom, params, sens,
                                         t_floor_K=t_floor_K)
        if not new_plan:
            return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                    'converged': False, 'iterations': it, 'history': history,
                    'accounting': mr_accounting(plan, params, detail=detail),
                    'reason': 'envelope allows no further cooling'}

        blended = ({b: relax * new_plan[b] + (1 - relax) * plan.get(b, 0.0) for b in new_plan}
                   if plan else dict(new_plan))
        cooled_trace = apply_cooling_to_trace(trace, blended, name_map)
        temps = thermal_solve_fn(cooled_trace)

        # Refine dT/dq against the baseline, which is what the plan is sized from.
        sens.update(estimate_sensitivity(base_temps, temps, blended))

        peak = max((float(np.ravel(t)[-1]) for t in temps.values()
                    if float(np.ravel(t)[-1]) > t_floor_K), default=float('nan'))
        delta_plan = max((abs(blended[b] - plan.get(b, 0.0)) for b in blended), default=0.0)
        total = float(sum(blended.values()))
        history.append({'iter': it, 'peak_K': peak, 'heat_removed_W': total,
                        'max_plan_change_W': delta_plan})
        plan = blended

        # Converged when the plan has stopped moving AND the peak is at target (within tol).
        # Requiring both is what distinguishes "clipped efficiently" from "overcooled".
        if delta_plan <= max(1e-3, 0.01 * total) and abs(peak - params.target_K) <= tol_K:
            return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                    'converged': True, 'iterations': it + 1, 'history': history,
                    'temp_trace_diverged': False, 'plan_is_minimum': False,
                    'accounting': mr_accounting(plan, params, detail=detail),
                    'reason': 'descent converged on the target; this plan holds the target but '
                              'the stability boundary was never probed, so it is not known to '
                              'be the smallest plan that keeps a steady state'}

    return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
            'converged': False, 'iterations': max_iter, 'history': history,
            'accounting': mr_accounting(plan, params, detail=detail),
            'reason': 'max_iter reached'}


def _run_mr_clipping_envelope(trace, thermal_solve_fn, block_geom, params, name_map, sens,
                              max_iter=6, tol_K=1.0, relax=0.7, t_floor_K=200.0,
                              status_fn=None, base_temps=None, base_status=None,
                              bisect_iters=8):
    """MR sizing anchored on the device envelope rather than on an uncooled baseline.

    Used when the bare die has no steady state, where the baseline the original scheme plans
    from does not exist. See ``run_mr_clipping`` for why that matters.

    Strategy: start at the most-cooled state the device can produce and walk *down* toward the
    target. The first solve then answers the question that actually matters -- can MR hold this
    die at all? -- and everything after it is a descent from a known-feasible point, so the
    answer never depends on where a divergent sequence stopped.
    """
    status_fn = status_fn or (lambda: {})
    history = []

    # Seed sensitivities for every block we might cool. 1.0 K/W is a placeholder that the
    # secant update replaces after the first cooled solve; it only sets the first step.
    for b in block_geom:
        sens.setdefault(b, 1.0)

    envelope, detail = envelope_plan(block_geom, params, sens, t_floor_K=t_floor_K)
    if not envelope:
        return {'plan': {}, 'detail': detail, 'temp_trace': base_temps, 'sensitivity': sens,
                'converged': False, 'iterations': 0, 'history': history,
                'plan_is_minimum': False, 'plan_holds_target': False,
                'temp_trace_diverged': bool((base_status or {}).get('diverged')),
                'accounting': mr_accounting({}, params, detail=detail),
                'reason': 'device envelope allows no cooling on any block'}

    plan = dict(envelope)
    prev_peak = None
    temps = thermal_solve_fn(apply_cooling_to_trace(trace, plan, name_map))
    st = status_fn()
    peak = max((float(np.ravel(t)[-1]) for t in temps.values()
                if float(np.ravel(t)[-1]) > t_floor_K), default=float('nan'))
    history.append({'iter': 0, 'peak_K': peak, 'heat_removed_W': float(sum(plan.values())),
                    'max_plan_change_W': float('inf'), 'stage': 'full envelope'})

    if st.get('diverged'):
        # The strongest statement this model can make about MR at an operating point: even at
        # full device capability the coupled system has no steady state.
        return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                'converged': False, 'iterations': 1, 'history': history,
                'temp_trace_diverged': True,
                'plan_is_minimum': False, 'plan_holds_target': False,
                'accounting': mr_accounting(plan, params, detail=detail),
                'reason': 'envelope insufficient: no steady state even at full MR capability'}

    if base_temps is not None:
        sens.update(estimate_sensitivity(base_temps, temps, plan))

    # Descend: reduce cooling where blocks sit below target, restore it where they sit above.
    for it in range(1, max_iter):
        prev_temps, prev_plan, prev_peak = temps, plan, peak
        plan = _relax_plan_toward_target(plan, envelope, temps, params, sens, relax, t_floor_K)
        if not plan:
            temps = thermal_solve_fn(trace)
            st = status_fn()
            peak = max((float(np.ravel(t)[-1]) for t in temps.values()
                        if float(np.ravel(t)[-1]) > t_floor_K), default=float('nan'))
            history.append({'iter': it, 'peak_K': peak, 'heat_removed_W': 0.0,
                            'max_plan_change_W': float(sum(prev_plan.values())),
                            'stage': 'relaxed to zero'})
            return {'plan': {}, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                    'converged': not st.get('diverged'), 'iterations': it + 1,
                    'history': history, 'temp_trace_diverged': bool(st.get('diverged')),
                    'plan_is_minimum': True, 'plan_holds_target': True,
                    'accounting': mr_accounting({}, params),
                    'reason': 'no cooling needed to hold the target'}

        temps = thermal_solve_fn(apply_cooling_to_trace(trace, plan, name_map))
        st = status_fn()
        sens.update(estimate_sensitivity(prev_temps, temps,
                                         {b: plan.get(b, 0.0) - prev_plan.get(b, 0.0)
                                          for b in set(plan) | set(prev_plan)}))
        peak = max((float(np.ravel(t)[-1]) for t in temps.values()
                    if float(np.ravel(t)[-1]) > t_floor_K), default=float('nan'))
        total = float(sum(plan.values()))
        delta_plan = max((abs(plan.get(b, 0.0) - prev_plan.get(b, 0.0))
                          for b in set(plan) | set(prev_plan)), default=0.0)
        history.append({'iter': it, 'peak_K': peak, 'heat_removed_W': total,
                        'max_plan_change_W': delta_plan, 'stage': 'descent'})

        if st.get('diverged'):
            # Walked past the feasible boundary. Do NOT stop here: "the last plan that held"
            # depends on the step size that got us here, which is exactly the iteration-count
            # dependence this rewrite exists to remove (the plan drifted 0.615 -> 0.335 W at
            # 1.10 W/mm^2 between 6 and 20 iterations). Bisect the plan scale between the
            # smallest plan known to hold and the largest known to fail, which converges on the
            # true minimum instead of wherever the descent happened to overshoot.
            bad = plan
            plan, temps = prev_plan, prev_temps
            for _ in range(bisect_iters):
                trial = {b: 0.5 * (plan.get(b, 0.0) + bad.get(b, 0.0))
                         for b in set(plan) | set(bad)}
                trial = {b: q for b, q in trial.items() if q > 0.0}
                t_trial = thermal_solve_fn(apply_cooling_to_trace(trace, trial, name_map))
                st_trial = status_fn()
                pk = max((float(np.ravel(t)[-1]) for t in t_trial.values()
                          if float(np.ravel(t)[-1]) > t_floor_K), default=float('nan'))
                history.append({'iter': len(history), 'peak_K': pk,
                                'heat_removed_W': float(sum(trial.values())),
                                'max_plan_change_W': float('nan'),
                                'stage': 'boundary bisection'})
                # A trial "fails" if it diverges OR if it lands on the HOT BRANCH. This
                # system is bistable: a leakage-limited die has a cool solution near the target
                # and a second stable solution far above it, with an unstable region between,
                # so reducing MR does not slide the peak up smoothly -- it snaps. Measured at
                # 1.15 W/mm^2: 42.05 W of cooling holds 90.6 C, while 0.71 W also "converges",
                # at 133.2 C. Accepting any convergence made the cheap hot-branch solution look
                # like the answer, which is how a 133 C die got reported as a rescue.
                if st_trial.get('diverged') or pk > params.target_K + tol_K:
                    bad = trial
                else:
                    plan, temps = trial, t_trial
                lo, hi = float(sum(plan.values())), float(sum(bad.values()))
                if lo <= 0 or (lo - hi) <= 0.01 * lo:
                    break
            final_peak = max((float(np.ravel(t)[-1]) for t in (temps or {}).values()
                              if float(np.ravel(t)[-1]) > t_floor_K), default=float('nan'))
            on_cool_branch = bool(final_peak <= params.target_K + tol_K)
            return {'plan': plan, 'detail': detail, 'temp_trace': temps,
                    'sensitivity': sens, 'converged': True,
                    'iterations': it + 1, 'history': history, 'temp_trace_diverged': False,
                    'accounting': mr_accounting(plan, params, detail=detail),
                    'plan_is_minimum': True, 'plan_holds_target': on_cool_branch,
                    'minimum_plan_W': float(sum(plan.values())),
                    'largest_failing_plan_W': float(sum(bad.values())),
                    'reason': ('minimum plan that keeps the die on the cool branch, bracketed '
                               'by bisection' if on_cool_branch else
                               'no plan in the bracket keeps the die on the cool branch: this '
                               'system is BISTABLE and the hot-branch solution is what is '
                               'reported. Stable, but read the peak before calling it a '
                               'rescue')}

        # Crossing the TARGET on the way down is the product-relevant answer, and it has to be
        # caught here rather than waiting for the plan to go stationary too: descending from the
        # envelope the peak RISES, so it sails past the target while the plan is still moving
        # fast. Without this the loop carries on to the stability boundary and reports a plan
        # whose steady state sits at 133 C -- stable, past McPAT's 127 C validity ceiling, and
        # not an operating point anyone would ship. Bisect to land ON the target instead.
        if peak > params.target_K + tol_K and prev_peak is not None \
                and prev_peak <= params.target_K + tol_K:
            too_little, enough, temps_ok = plan, prev_plan, prev_temps
            for _ in range(bisect_iters):
                trial = {b: 0.5 * (enough.get(b, 0.0) + too_little.get(b, 0.0))
                         for b in set(enough) | set(too_little)}
                trial = {b: q for b, q in trial.items() if q > 0.0}
                t_trial = thermal_solve_fn(apply_cooling_to_trace(trace, trial, name_map))
                st_trial = status_fn()
                pk = max((float(np.ravel(t)[-1]) for t in t_trial.values()
                          if float(np.ravel(t)[-1]) > t_floor_K), default=float('nan'))
                history.append({'iter': len(history), 'peak_K': pk,
                                'heat_removed_W': float(sum(trial.values())),
                                'max_plan_change_W': float('nan'),
                                'stage': 'target bisection'})
                if st_trial.get('diverged') or pk > params.target_K + tol_K:
                    too_little = trial
                else:
                    enough, temps_ok = trial, t_trial
                    if abs(pk - params.target_K) <= tol_K:
                        break
            return {'plan': enough, 'detail': detail, 'temp_trace': temps_ok,
                    'sensitivity': sens, 'converged': True, 'iterations': it + 1,
                    'history': history, 'temp_trace_diverged': False,
                    'plan_is_minimum': True, 'plan_holds_target': True,
                    'minimum_plan_W': float(sum(enough.values())),
                    'accounting': mr_accounting(enough, params, detail=detail),
                    'reason': 'minimum plan that holds the target, bracketed by bisection'}

        if delta_plan <= max(1e-3, 0.01 * total) and abs(peak - params.target_K) <= tol_K:
            return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                    'converged': True, 'iterations': it + 1, 'history': history,
                    'temp_trace_diverged': False,
                    # Landed on the target smoothly. It holds the target; whether it is also the
                    # smallest plan that keeps a steady state is a different question and was
                    # not probed, so that flag stays False.
                    'plan_is_minimum': False, 'plan_holds_target': True,
                    'accounting': mr_accounting(plan, params, detail=detail)}

    return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
            'converged': not st.get('diverged'), 'iterations': max_iter, 'history': history,
            'temp_trace_diverged': bool(st.get('diverged')), 'plan_is_minimum': False,
            'plan_holds_target': bool(peak <= params.target_K + tol_K),
            'accounting': mr_accounting(plan, params, detail=detail),
            'reason': 'max_iter reached during envelope descent: the descent never reached the '
                      'stability boundary, so this plan is an UPPER BOUND on what MR needs, not '
                      'the minimum. Raise max_iter to bracket the boundary.'}


def distributed_plan(block_geom, params, total_W, weight='area', t_floor_K=200.0):
    """Spread a fixed cooling budget over the whole die instead of clipping hotspots.

    Design E in docs/DESIGN_STUDY_PLAN.md: the control arm. Every MR result in this project
    assumes MR is a *hotspot* tool, and that assumption is load-bearing -- it is why a poor
    cooler COP is tolerable, because ``Q_removed`` is small and buys a disproportionate
    frequency gain. If spreading the same watts over the die did as well, the framing would be
    wrong and the comparison should be against a better heat sink rather than against nothing.

    It is included because it is the strongest argument against the hotspot framing, and an
    argument you have not measured is an argument you have not answered. The expectation is that
    it loses badly on wall-plug grounds -- an electrical COP of 0.14 against a cold plate that
    moves heat for the cost of a pump -- but it can only be *reported* as a loss if it is run.

    weight : 'area' spreads the budget by block area (uniform cooling flux, which is what a
             tile array with no targeting would do), 'uniform' splits it evenly per block
             (which over-cools small blocks and is mostly a sanity contrast).

    Blocks are still capped by the device envelope, so a budget larger than the device can
    deliver is silently truncated -- the returned plan's total is the honest deliverable amount
    and callers should compare against that rather than against what they asked for.
    """
    if total_W <= 0:
        raise ValueError('total_W must be > 0, got {!r}'.format(total_W))
    if weight not in ('area', 'uniform'):
        raise ValueError("weight must be 'area' or 'uniform', got {!r}".format(weight))

    names = [b for b, g in block_geom.items() if g and g.get('area_mm2', 0.0) > 0]
    if not names:
        return {}, {}
    if weight == 'area':
        tot_area = sum(block_geom[b]['area_mm2'] for b in names)
        share = {b: block_geom[b]['area_mm2'] / tot_area for b in names}
    else:
        share = {b: 1.0 / len(names) for b in names}

    plan, detail = {}, {}
    for b in names:
        want = total_W * share[b]
        cap = params.h_max * block_geom[b]['area_mm2']      # the device's flux ceiling
        q = min(want, cap)
        if q <= 0:
            continue
        plan[b] = q
        detail[b] = {'limit': 'h_max' if q < want else 'budget', 'q_W': q,
                     'requested_W': want, 'q_h_max_W': cap}
    delivered = float(sum(plan.values()))
    if delivered < 0.999 * total_W:
        LOGGER.warning('distributed plan could only deliver %.3f W of the requested %.3f W: the '
                       'per-block h_max ceiling binds. Compare against the delivered figure.',
                       delivered, total_W)
    return plan, detail
