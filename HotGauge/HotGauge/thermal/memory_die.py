"""§P0.44: a DRAM / HBM die beside, under or on top of the compute die -- the re-aimed gen 3.

Why this exists
---------------
§P0.37 measured the gen-3 geometry with a CACHE die (the L2/L3 blocks, filled from the McPAT
trace by name) held at 280 K. §P0.40 then found the cache-leakage prize is a McPAT input and
§P0.43 that a memory die's motive is PROXIMITY, with 2.5D collecting nearly all of it. So the
memory die to price is a DRAM / HBM die, whose power is not in any trace, whose limit is the
JEDEC 85 degC refresh breakpoint rather than a leakage knee, and whose placement is the design
variable: beside the compute die (2.5D), on top of it (the conventional memory-on-logic stack),
or under it on the far face (the §P0.37 geometry).

What this module provides (and what it deliberately reuses)
-----------------------------------------------------------
* **Bank floorplans.** ``build_memory_split`` writes the three-file set ``mr_comparison.py
  --gen3-split`` already consumes -- ``compute_template.flp`` (the reference die, every block
  powered: the caches STAY on the compute die), ``storage_template.flp`` (the banks over the
  same footprint, ``{powers[NAME]}`` placeholders) -- plus ``union_reference.flp`` (reference +
  banks), the floorplan every ledger, the planner's geometry and the tile wiring must see.
  ``build_memory_beside`` writes ONE wide floorplan for the 2.5D form: the reference blocks, a
  bare-silicon gap, the banks translated right of the compute die. 3D-ICE forces one footprint
  per stack, so the two 2.5D dies share one silicon slab; its lateral conduction is an UPPER
  bound on an interposer's (``slab_coupling_W_per_K`` prices it).
* **The memory's power** goes into the solve THROUGH THE TRACE, by name: ``MemoryDie.inject``
  adds ``MEM_r.c.`` keys to the McPAT-named trace. ``rename_mcpat_units_to_ICE_units`` passes
  an unknown name through unchanged, ``ICESim.fill_storage_flp_template`` fills the storage
  die from the trace by name, and ``die_power_of_trace`` on the union floorplan counts the
  banks -- so the planner's conservation cap, ``p_injected_W`` and the leakage ledger all see
  the same watts without a second power path. (``examples/stacked_memory_study.py`` renders the
  bank floorplans itself for the legacy lidded stack; nothing here touches that path.)
* **The refresh fixed point** (``refresh_fixed_point``) wraps the leakage loop: solve, read the
  banks' temperatures, re-price refresh with ``power/dram.py``'s multiplier, re-solve. Refresh
  runaway is reported as its own divergence (``mem_diverged``), distinct from the compute die's
  leakage runaway -- a memory die with no idle steady state behind a poor far-face sink is a
  finding, not a solver failure (§P0.37 learned that the hard way with the cache die).
* **Two conductivities a memory die brings with it:** the isolation layer crossed by a VIA FIELD
  (``via_field_effective_k``: a parallel copper path; 10,000 x 5 um vias lift an aerogel-class
  0.1 W/mK layer to ~0.85) and an n-high stack lumped into one die element
  (``lumped_stack``: series-equivalent k of n dies and n-1 bonds).

Everything numerical about the DRAM itself is ``power/dram.py``'s and carries its UNCALIBRATED
flag: use these rows to say which placement binds and what the array pays, not how many watts a
part draws.
"""
import os
import re
import math
import json
import logging

import numpy as np

from HotGauge.power.dram import (stacked_dram_model, dram_block_powers, dram_limit_report,
                                 DEFAULT_REFRESH_BREAK_K, DEFAULT_DRAM_LIMIT_K)

LOGGER = logging.getLogger(__name__)

#: Bank block names: ``MEM_r<row>c<col>``. Matches nothing McPAT emits and nothing
#: ``is_no_power_unit`` zeroes (checked by test_memory_die).
MEM_PREFIX = 'MEM'
MEM_PATTERN = r'^MEM_r\d+c\d+$'
MEM_ZONE_PATTERN = '^MEM_'
_MEM_RGX = re.compile(MEM_PATTERN)

#: Copper, for the via field [W/(m K)] -- die_stack.MATERIALS['COPPER'].
K_COPPER = 390.0
#: Silicon [W/(m K)] -- die_stack.MATERIALS['SILICON'].
K_SILICON = 120.0

#: A thinned memory die and its bond (stack_models / die_stack use the same figures).
DEFAULT_MEM_DIE_UM = 50.0
DEFAULT_MEM_BOND_UM = 5.0
DEFAULT_MEM_BOND_K = 5.0        # underfill-dominated microbumps; hybrid bonding ~50-120

#: Per-die power at the breakpoint rate [W]. HBM3E-class stacks are ~25-30 W per 8-12 dies
#: (~2-3 W per die), HBM2E ~8-10 W per 8 (~1 W). ASSUMPTIONS -- dram.py says so too.
DEFAULT_W_PER_DIE = 3.0

#: The planning target sits BELOW the breakpoint on purpose: the breakpoint is a x2 step, and a
#: zone held "at 358 K within 2 K" straddles it. 80 degC + the planner's 2 K is under the step.
DEFAULT_MEM_TARGET_K = 353.15

_BLOCK = re.compile(r'^(\S+)\s*:\s*\n\s*position\s+([\d.]+)\s*,\s*([\d.]+)\s*;\s*\n'
                    r'\s*dimension\s+([\d.]+)\s*,\s*([\d.]+)\s*;\s*\n\s*power values ([^;]*);',
                    re.M)


# ---------------------------------------------------------------------------------------------
# Conductivities
# ---------------------------------------------------------------------------------------------
def via_field_effective_k(k_fill, n_vias, via_d_um, die_area_mm2, k_via=K_COPPER):
    """Conductivity of an isolation layer crossed by ``n_vias`` copper vias of ``via_d_um``.

    Parallel paths through one layer: ``k_eff = k_fill (1 - f) + k_via f`` with ``f`` the vias'
    area fill. Returns ``(k_eff, fill)``. This is the floor a SIGNALLED memory die puts under
    the isolation: the via count is an electrical requirement, not a thermal choice.
    """
    if n_vias < 0 or via_d_um <= 0 or die_area_mm2 <= 0 or k_fill < 0:
        raise ValueError('via field needs n_vias >= 0, via_d_um > 0, die_area_mm2 > 0, k_fill >= 0')
    fill = float(n_vias) * math.pi * (float(via_d_um) * 1e-6 / 2.0) ** 2 / (float(die_area_mm2) * 1e-6)
    if fill >= 1.0:
        raise ValueError('{} vias of {} um fill {:.2f} of a {:.1f} mm^2 die: more copper than die'
                         .format(n_vias, via_d_um, fill, die_area_mm2))
    return float(k_fill) * (1.0 - fill) + float(k_via) * fill, fill


def lumped_stack(n_dies, die_um=DEFAULT_MEM_DIE_UM, k_die=K_SILICON,
                 bond_um=DEFAULT_MEM_BOND_UM, k_bond=DEFAULT_MEM_BOND_K):
    """An n-high stack as ONE die element: ``(thickness_um, k_eff_W_mK)``.

    Series-equivalent: ``t / k_eff = n t_die / k_die + (n - 1) t_bond / k_bond``. 3D-ICE's die
    element has one material, so a stack is lumped; the bonds are what make an 8-high stack a
    thermal wall (HIR 2023 ch. 20) and they are kept, as a conductivity, not dropped.
    """
    n = int(n_dies)
    if n < 1:
        raise ValueError('n_dies must be >= 1')
    t = n * float(die_um) + (n - 1) * float(bond_um)
    r = n * float(die_um) / float(k_die) + (n - 1) * float(bond_um) / float(k_bond)
    return t, t / r


def slab_coupling_W_per_K(slab_um, width_um, gap_um, k=K_SILICON):
    """Lateral conductance of the shared 2.5D slab across ``gap_um`` [W/K] -- the upper bound."""
    return float(k) * (float(slab_um) * 1e-6) * (float(width_um) * 1e-6) / (float(gap_um) * 1e-6)


# ---------------------------------------------------------------------------------------------
# Floorplans
# ---------------------------------------------------------------------------------------------
def reference_blocks(flp_path):
    """``[(name, x, y, w, h, power_text), ...]`` from a 3D-ICE floorplan (template or filled)."""
    text = open(flp_path).read()
    out = [(m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)),
            float(m.group(5)), m.group(6).strip()) for m in _BLOCK.finditer(text)]
    if not out:
        raise ValueError('no blocks parsed from {}'.format(flp_path))
    return out


def footprint_um(blocks, cell_um=100.0):
    """The footprint 3D-ICE will use: the blocks' extent rounded up to the grid (ICESim rounds
    to 100 um; stack_models.memory_floorplan does the same)."""
    w = max(b[1] + b[3] for b in blocks)
    h = max(b[2] + b[4] for b in blocks)
    return (math.ceil(w / cell_um) * cell_um, math.ceil(h / cell_um) * cell_um)


def bank_blocks(width_um, height_um, n_x=4, n_y=4, x0=0.0, y0=0.0, prefix=MEM_PREFIX):
    """``n_x * n_y`` banks tiling ``width_um x height_um`` from ``(x0, y0)``."""
    bw, bh = float(width_um) / n_x, float(height_um) / n_y
    out = []
    for r in range(n_y):
        for c in range(n_x):
            out.append(('{}_r{}c{}'.format(prefix, r, c), x0 + c * bw, y0 + r * bh, bw, bh))
    return out


def _flp_text(blocks):
    """3D-ICE floorplan text with ``{powers[NAME]}`` placeholders (the pipeline's template form).

    A literal ``power values 0.0;`` passes through ``str.format`` untouched and the die solves
    unpowered -- commit b7d762e. Every block here gets a placeholder.
    """
    lines = []
    for b in blocks:
        name, x, y, w, h = b[:5]
        pw = b[5] if len(b) > 5 and b[5] else '{{powers[{}]}}'.format(name)
        lines.append('{} :\n\tposition {:.3f}, {:.3f} ;\n\tdimension {:.3f}, {:.3f} ;\n'
                     '\tpower values {};'.format(name, x, y, w, h, pw))
    return '\n'.join(lines) + '\n'


def build_memory_split(reference_flp, out_dir, n_x=4, n_y=4, cell_um=100.0):
    """The far-face / sink-side floorplan set, in the layout ``--gen3-split`` consumes.

    ``compute_template.flp`` is the reference die as it stands (the caches stay on it);
    ``storage_template.flp`` is the banks over the SAME footprint (3D-ICE's one-footprint rule,
    which here coincides with an HBM die's ~100 mm^2); ``union_reference.flp`` is both, for the
    accounting / wiring / planner geometry. Returns the dict ``split.json`` records.
    """
    os.makedirs(out_dir, exist_ok=True)
    ref = reference_blocks(reference_flp)
    names = {b[0] for b in ref}
    w, h = footprint_um(ref, cell_um)
    banks = bank_blocks(w, h, n_x, n_y)
    clash = [b[0] for b in banks if b[0] in names]
    if clash:
        raise ValueError('bank names collide with reference blocks: {}'.format(clash[:3]))
    cp = os.path.join(out_dir, 'compute_template.flp')
    sp = os.path.join(out_dir, 'storage_template.flp')
    up = os.path.join(out_dir, 'union_reference.flp')
    open(cp, 'w').write(_flp_text(ref))
    open(sp, 'w').write(_flp_text(banks))
    open(up, 'w').write(_flp_text(ref) + _flp_text(banks))
    meta = {'arrangement': 'stacked', 'reference': os.path.abspath(reference_flp),
            'compute_template': cp, 'storage_template': sp, 'union_reference': up,
            'n_compute_blocks': len(ref), 'n_banks': len(banks),
            'bank_names': [b[0] for b in banks],
            'footprint_um': [w, h], 'footprint_mm2': w * h * 1e-6,
            'note': 'the compute die is the whole reference die (caches on it); the memory die '
                    'is the banks over the same footprint; account on union_reference.flp'}
    json.dump(meta, open(os.path.join(out_dir, 'split.json'), 'w'), indent=1)
    return meta


def build_memory_beside(reference_flp, out_dir, gap_um=1000.0, n_x=4, n_y=4, cell_um=100.0,
                        mem_width_um=None):
    """The 2.5D form: ONE floorplan, the banks right of the compute die behind a bare gap.

    The gap is unpowered silicon (no block), so it conducts but dissipates nothing. Returns the
    meta dict; the floorplan is ``beside.flp`` and it is both the solver's and the ledger's.
    """
    os.makedirs(out_dir, exist_ok=True)
    ref = reference_blocks(reference_flp)
    w, h = footprint_um(ref, cell_um)
    gap = math.ceil(float(gap_um) / cell_um) * cell_um
    mw = w if mem_width_um is None else math.ceil(float(mem_width_um) / cell_um) * cell_um
    banks = bank_blocks(mw, h, n_x, n_y, x0=w + gap, y0=0.0)
    bp = os.path.join(out_dir, 'beside.flp')
    open(bp, 'w').write(_flp_text(ref) + _flp_text(banks))
    meta = {'arrangement': 'beside', 'reference': os.path.abspath(reference_flp),
            'floorplan': bp, 'n_compute_blocks': len(ref), 'n_banks': len(banks),
            'bank_names': [b[0] for b in banks], 'gap_um': gap,
            'compute_footprint_um': [w, h], 'memory_footprint_um': [mw, h],
            'footprint_um': [w + gap + mw, h], 'footprint_mm2': (w + gap + mw) * h * 1e-6,
            'note': 'one silicon slab for both dies (3D-ICE one-footprint rule): lateral '
                    'coupling through it is an UPPER bound on an interposer\'s'}
    json.dump(meta, open(os.path.join(out_dir, 'beside.json'), 'w'), indent=1)
    return meta


# ---------------------------------------------------------------------------------------------
# The memory die in the solve
# ---------------------------------------------------------------------------------------------
class MemoryDie(object):
    """The banks, their DRAM model, and the two things the solve needs: powers in, temperatures out.

    ``w_per_die`` is the per-die power at the breakpoint rate; ``n_dies`` lumps the stack's
    power into the one die element (the thermal lumping is ``lumped_stack``'s, stated on the
    stack spec). ``target_K`` is the PLANNING target (below the breakpoint, see
    DEFAULT_MEM_TARGET_K); ``break_K`` / ``limit_K`` are the reported lines.
    """

    def __init__(self, bank_names, area_mm2, n_dies=1, w_per_die=DEFAULT_W_PER_DIE,
                 refresh_fraction=0.35, activity_fraction=0.30,
                 break_K=DEFAULT_REFRESH_BREAK_K, limit_K=DEFAULT_DRAM_LIMIT_K,
                 target_K=DEFAULT_MEM_TARGET_K):
        self.names = list(bank_names)
        if not self.names:
            raise ValueError('a memory die needs at least one bank')
        bad = [n for n in self.names if not _MEM_RGX.match(n)]
        if bad:
            raise ValueError('bank names must match {}: {}'.format(MEM_PATTERN, bad[:3]))
        self.n_dies = int(n_dies)
        self.w_per_die = float(w_per_die)
        self.area_mm2 = float(area_mm2)
        total = self.n_dies * self.w_per_die
        # stacked_dram_model sizes from area x density; state the density the total implies
        self.model = stacked_dram_model(self.area_mm2, density_W_per_mm2=total / self.area_mm2,
                                        refresh_fraction=refresh_fraction,
                                        activity_fraction=activity_fraction,
                                        break_K=break_K)
        self.break_K = float(break_K)
        self.limit_K = float(limit_K)
        self.target_K = float(target_K)
        if self.target_K >= self.break_K:
            LOGGER.warning('memory planning target %.1f K is at or above the %.1f K breakpoint: '
                           'the hold will straddle the refresh step', self.target_K, self.break_K)

    @property
    def floor_W(self):
        """The die's power at the breakpoint rate (m = 1) -- what the trace starts with."""
        return float(self.model.power(self.break_K - 1.0))

    def floor_powers(self):
        return dram_block_powers(self.names, self.model, None, default_T_K=self.break_K - 1.0)

    def powers_at(self, temps):
        """Per-bank powers at the solved bank temperatures (banks absent from ``temps`` are
        priced at the floor)."""
        return dram_block_powers(self.names, self.model, temps, default_T_K=self.break_K - 1.0)

    def bank_temps(self, temps, t_floor_K=200.0):
        """The banks' temperatures out of a solved field (``{block: [K, ...]}``)."""
        out = {}
        for n in self.names:
            if n in temps:
                T = float(np.ravel(temps[n])[-1])
                if T > t_floor_K:
                    out[n] = T
        return out

    def inject(self, trace, powers=None):
        """A copy of ``trace`` carrying the banks' powers by name (the floor if not given)."""
        from HotGauge.power.traces import BasicPowerTrace
        powers = self.floor_powers() if powers is None else powers
        n = len(trace)
        merged = dict(trace.powers)
        for b, p in powers.items():
            merged[b] = np.full(n, float(p))
        return BasicPowerTrace(merged, trace.time_step)

    def report(self, temps, powers=None):
        """What a row carries about the memory die."""
        bt = self.bank_temps(temps)
        rep = dram_limit_report({k: np.array([v]) for k, v in bt.items()},
                                limit_K=self.limit_K, break_K=self.break_K)
        pw = self.powers_at(bt) if powers is None else powers
        mult = [float(self.model.refresh_multiplier(T)) for T in bt.values()]
        return {'mem_n_banks': len(self.names), 'mem_n_banks_read': len(bt),
                'mem_dies': self.n_dies, 'mem_W_per_die': self.w_per_die,
                'mem_floor_W': self.floor_W, 'mem_power_W': float(sum(pw.values())),
                'mem_zone_max_C': (rep['peak_K'] - 273.15) if rep['peak_K'] is not None else None,
                'mem_zone_mean_C': ((float(np.mean(list(bt.values()))) - 273.15) if bt else None),
                'mem_peak_bank': rep.get('peak_block'),
                'mem_refresh_mult_max': (max(mult) if mult else None),
                'mem_n_over_break': rep['n_over_break'], 'mem_n_over_limit': rep['n_over_limit'],
                'mem_break_C': self.break_K - 273.15, 'mem_limit_C': self.limit_K - 273.15,
                'mem_target_K': self.target_K, 'mem_calibrated': False}


def refresh_fixed_point(solve_fn, trace, memdie, max_iter=8, tol_frac=0.005,
                        runaway_factor=4.0, runaway_K=None):
    """Couple the memory's refresh loop to the leakage loop: ``solve_fn(trace) -> result``.

    ``solve_fn`` is the damping-verified leakage solve (it returns the ``run_leakage_feedback``
    dict). Each pass re-prices the banks from the field the previous pass produced. Returns the
    last result with ``mem`` (the report), ``mem_iterations``, ``mem_diverged`` and
    ``mem_history`` added; a refresh runaway (power past ``runaway_factor`` x the floor, or a bank
    past ``runaway_K``) marks the result ``diverged`` with ``diverged_reason = 'memory refresh
    runaway'`` -- the memory's own loop, distinct from the compute die's.
    """
    runaway_K = (memdie.limit_K + 60.0) if runaway_K is None else float(runaway_K)
    floor = memdie.floor_W
    powers = memdie.floor_powers()
    hist, res = [], None
    for it in range(max(1, int(max_iter))):
        res = solve_fn(memdie.inject(trace, powers))
        if res.get('diverged'):
            res['mem'] = memdie.report(res.get('temp_trace') or {}, powers)
            res['mem_iterations'] = it + 1
            res['mem_diverged'] = False
            res['mem_history'] = hist
            return res
        bt = memdie.bank_temps(res['temp_trace'])
        new = memdie.powers_at(bt)
        total = float(sum(new.values()))
        delta = max(abs(new[b] - powers[b]) for b in memdie.names)
        hist.append({'iter': it, 'mem_power_W': total, 'max_bank_delta_W': delta,
                     'mem_peak_C': (max(bt.values()) - 273.15) if bt else None})
        hot = max(bt.values()) if bt else 0.0
        if total > runaway_factor * floor or hot > runaway_K:
            res['diverged'] = True
            res['diverged_reason'] = ('memory refresh runaway: {:.1f} W ({:.1f}x the floor), '
                                      'hottest bank {:.0f} K'.format(total, total / floor, hot))
            res['mem'] = memdie.report(res['temp_trace'], new)
            res['mem_iterations'] = it + 1
            res['mem_diverged'] = True
            res['mem_history'] = hist
            return res
        converged = delta <= tol_frac * max(total, 1e-9)
        powers = new
        if converged:
            break
    res['mem'] = memdie.report(res['temp_trace'], powers)
    res['mem_iterations'] = len(hist)
    res['mem_diverged'] = False
    res['mem_converged'] = bool(hist and hist[-1]['max_bank_delta_W']
                                <= tol_frac * max(hist[-1]['mem_power_W'], 1e-9))
    res['mem_history'] = hist
    res['power_trace'] = memdie.inject(res['power_trace'], powers) if 'power_trace' in res else None
    return res
