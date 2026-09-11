"""Wire the temperature-dependent leakage feedback (HotGauge.power.leakage) to real 3D-ICE.

This is the production glue that closes the power<->temperature loop the stock pipeline
leaves open (see the gap-analysis doc and HotGauge.power.leakage):

    baseline block powers (McPAT names, leakage frozen at T_ref)
        |
        v   converge_power_temperature
    +-----------------------------------------------------------+
    |  power trace (McPAT names)                                |
    |     -> prepare_dice_trace: rename McPAT->floorplan,       |
    |        split L3, add IMC/IO/SoC                           |
    |     -> ICETransientSim (3D-ICE)                           |
    |     -> read die_elements.temps (Tflp): per-block T [K]    |
    |        keyed by FLOORPLAN name                            |
    |  rescale leakage per unit using T (bridged McPAT<->flp    |
    |     via mcpat_to_flp_name), holding dynamic fixed         |
    +-----------------------------------------------------------+
        |
        v  iterate until max per-block dT < tol (or runaway flagged)

Execution note
--------------
Running 3D-ICE requires the patched emulator binary + GNU ``parallel`` and therefore only
works on the Linux server where the toolchain is built (not on a Windows dev box). Everything
in this module *except* ``ICEThermalSolver._run_and_read_temps`` is pure Python and unit-tested
without the binary; ``run_leakage_feedback`` accepts any ``thermal_solve_fn`` callable, so the
loop can be exercised with a mock solver (see thermal/test_leakage_feedback.py).
"""

import os
import re
import glob
import json
import logging

import numpy as np

from HotGauge.configuration.mcpat import mcpat_to_flp_name, NoSuchMCPATUnitError
from HotGauge.power.leakage import LeakageModel, converge_power_temperature, DEFAULT_TREF_K

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name bridging: McPAT unit name  <->  floorplan block name (temperature keys)
# ---------------------------------------------------------------------------
def mcpat_flp_name_map(include_core_idx=True):
    """Return a callable mapping a McPAT unit name to its floorplan/Tflp block name.

    3D-ICE reports per-block temperatures keyed by floorplan names (e.g. ``iALU_0``), while
    the power/leakage traces use McPAT hierarchy names (e.g. ``Core0/Execution Unit/Integer
    ALUs``). This wraps ``mcpat_to_flp_name`` and returns ``None`` for units that have no
    floorplan block (aggregates like ``Processor/Total L3s``, ``BUSES``, ``NUCA``, ``IMC``,
    or bare ``Core0``) so the caller's missing-unit policy leaves their leakage unscaled
    rather than erroring.
    """
    def name_map(unit):
        try:
            return mcpat_to_flp_name(unit, include_core_idx=include_core_idx)
        except (NoSuchMCPATUnitError, KeyError):
            return None
    return name_map


# ---------------------------------------------------------------------------
# Bridging aggregates whose POWER is split across floorplan blocks
# ---------------------------------------------------------------------------
#: Synthetic Tflp key standing for "the L3 as a whole".
AGG_L3_TEMP_KEY = '__agg__L3'

#: McPAT aggregates whose power IS placed on the die (so they have a defined temperature) but
#: which have no single floorplan block. ``split_L3_power`` spreads ``Processor/Total L3s``
#: evenly over ``L3_0..L3_{n-1}``, so its leakage can legitimately be fed back against the mean
#: of those blocks. Everything else (``Processor``, ``Processor/Total Cores``) is a pure
#: restatement of its children and must NOT be bridged -- that would double-count.
#:
#: ``NUCA`` is the same quantity as ``Processor/Total L3s`` under another name (identical
#: dynamic and leakage in the split files); bridging both would count the L3 twice, so only
#: the canonical name is listed.
BRIDGEABLE_AGGREGATES = {'Processor/Total L3s': AGG_L3_TEMP_KEY}


def augment_temps_with_aggregates(temps, num_cores=8):
    """Add synthetic temperature entries for bridgeable aggregates.

    Without this, ``Processor/Total L3s`` leakage (1.23 W on the 7nm linpack trace -- 45 % more
    than everything else in the loop combined) stays frozen at T_ref even though its power is
    on the die and its temperature is known. Returns a new dict; the input is not mutated.
    """
    out = dict(temps)
    l3 = [np.asarray(temps[k], dtype=float).ravel()
          for k in ('L3_{}'.format(i) for i in range(num_cores)) if k in temps]
    if l3:
        n = min(len(a) for a in l3)
        out[AGG_L3_TEMP_KEY] = np.mean(np.vstack([a[:n] for a in l3]), axis=0)
    return out


def aggregate_aware_name_map(include_core_idx=True, num_cores=8):
    """Name map that also resolves the bridgeable aggregates to their synthetic temp keys."""
    base = mcpat_flp_name_map(include_core_idx=include_core_idx)

    def name_map(unit):
        if unit in BRIDGEABLE_AGGREGATES:
            return BRIDGEABLE_AGGREGATES[unit]
        return base(unit)
    return name_map


# ---------------------------------------------------------------------------
# Loading the baseline leakage split emitted by mcpat_to_blk_lvl_power_dict.py
# ---------------------------------------------------------------------------
def load_leakage_ref(split_files):
    """Load baseline per-unit leakage from ``block_powers_split_*.json`` files.

    Each split file maps ``unit -> [dynamic, leakage]`` for one timestep (watts, at the
    McPAT reference temperature). ``split_files`` is an ordered list of those files (one per
    timestep, matching the power trace order).

    Returns ``{unit: [leak_t0, leak_t1, ...]}`` -- the per-timestep leakage series suitable
    as ``leakage_ref`` for ``HotGauge.power.leakage.rescale_trace`` /
    ``converge_power_temperature``. Units are assumed consistent across files; a unit absent
    from some timestep is filled with 0.0 for those steps (with a warning).
    """
    series = {}
    n = len(split_files)
    for t, fp in enumerate(split_files):
        with open(fp) as f:
            split = json.load(f)
        for unit, pair in split.items():
            # pair is [dynamic, leakage]; be tolerant of a bare scalar just in case
            leak = float(pair[1]) if isinstance(pair, (list, tuple)) else float(pair)
            if unit not in series:
                series[unit] = [0.0] * n
            series[unit][t] = leak
    # Warn about units that never appeared in some files (stayed at the 0.0 fill)
    return {u: np.asarray(v, dtype=float) for u, v in series.items()}


#: McPAT hierarchy roots that restate their children. They are correctly discarded before
#: 3D-ICE; separating them from genuine losses is what makes the drop accounting meaningful.
#: Bare ``Core<N>`` roots are matched by pattern rather than listed, so the accounting stays
#: correct for any core count (``replicate_trace_cores`` can produce ``Core69``).
_MCPAT_AGGREGATE_NAMES = frozenset(('Processor', 'NUCA', 'BUSES', 'IMC'))
_BARE_CORE_RGX = re.compile(r'^Core\d+$')


def _is_mcpat_aggregate(name):
    """True for McPAT names that restate children rather than naming a leaf block."""
    return name in _MCPAT_AGGREGATE_NAMES or bool(_BARE_CORE_RGX.match(name))


#: Non-block columns that ``load_3DICE_block_file`` returns alongside the real floorplan
#: blocks. ``Time`` is the simulation timestamp, not a temperature.
NON_BLOCK_TFLP_KEYS = frozenset(('Time',))


#: Largest system MEASURED to factorise on this toolchain: the 34-core two-die session
#: (``docs/evidence/session_memory.json``, 366,048 unknowns). Configurations at 275k also solve.
#: The stacked-memory stack at 50 um x 27 layers is **1,098,144** and fails every time.
LARGEST_MEASURED_UNKNOWNS = 366048


def stack_unknowns(stack_file):
    """``(unknowns, chip_um, cell_um, n_layers)`` read off a rendered ``.stk``, or ``None``.

    Cheap and best-effort: this exists to put a NUMBER in a failure message, never to gate a run.
    """
    import re as _re
    try:
        txt = open(stack_file, errors='replace').read()
    except Exception:
        return None
    dim = _re.search(r'chip\s+length\s+([\d.]+)\s*,\s*width\s+([\d.]+)', txt)
    cel = _re.search(r'cell\s+length\s+([\d.]+)\s*,\s*width\s+([\d.]+)', txt)
    if not dim or not cel:
        return None
    L, W = float(dim.group(1)), float(dim.group(2))
    cl, cw = float(cel.group(1)), float(cel.group(2))
    if cl <= 0 or cw <= 0:
        return None
    layers = len(_re.findall(r'^\s+(?:layer|die|source|solid)\b', txt, _re.M)) or 1
    return int((L / cl) * (W / cw) * layers), (L, W), (cl, cw), layers


def _with_stack_size_diagnosis(exc, sim):
    """Return ``exc`` with a size diagnosis appended when the stack is oversized.

    The failure mode this names is silent by construction -- 3D-ICE writes nothing to stderr --
    so without this the only evidence is a wall-clock cost and an errno.
    """
    info = stack_unknowns(getattr(sim, 'stack_file', None) or '')
    if not info:
        return exc
    n, (L, W), (cl, cw), layers = info
    if n <= LARGEST_MEASURED_UNKNOWNS:
        return exc
    msg = (
        '{}\n\n'
        '  `[!]` This stack is {:,} unknowns ({:.0f}x{:.0f} um at {:.0f} um cells, {} layers).\n'
        '  The largest system MEASURED to factorise on this toolchain is {:,} '
        '(docs/evidence/session_memory.json).\n'
        '  3D-ICE exits during "Preparing thermal data" with an EMPTY stderr when the system is '
        'too large,\n'
        '  so a silent failure after a long wall time is the expected symptom rather than a hang '
        '(P0.17:\n'
        '  measured ~75 min per point). Halving the grid quarters the system: --cell-um {:.0f} '
        'gives {:,}.\n'
        '  `[!]` A coarser grid smooths lateral gradients, so peaks on small blocks are '
        'understated and a\n'
        '  {:.0f} um run must not be compared against a {:.0f} um one.'
    ).format(exc, n, L, W, cl, layers, LARGEST_MEASURED_UNKNOWNS,
             cl * 2, int(n / 4), cl * 2, cl)
    return type(exc)(getattr(exc, 'errno', 5), msg) if hasattr(exc, 'errno') else RuntimeError(msg)


def die_block_temps(tflp_path_or_dict, t_floor_K=200.0):
    """Per-block die temperatures from a Tflp result, with non-block columns removed.

    ``load_3DICE_block_file`` keys its result by the Tflp header, whose first column is
    ``Time(s)`` -- so the returned dict contains a ``Time`` entry holding the simulation
    timestamp. That is not a temperature, and it is a silent trap: for short runs the value
    sits below ``t_floor_K`` and is filtered out by accident, but once simulated time exceeds
    200 s it starts masquerading as the hottest block on the die. A 400 s run reported a peak
    of 400 K (126.85 C) that was simply the clock.

    Accepts either a path or an already-loaded dict. Returns ``{block: array}`` for real
    blocks only.
    """
    if isinstance(tflp_path_or_dict, dict):
        raw = tflp_path_or_dict
    else:
        from HotGauge.thermal.ICE import load_3DICE_block_file
        raw = load_3DICE_block_file(tflp_path_or_dict, convert_K_to_C=False)
    return {k: v for k, v in raw.items() if k not in NON_BLOCK_TFLP_KEYS}


def die_power_of_trace(trace, floorplan, tech_node, num_cores=8, core_sources=None,
                       detail=False, already_dice_named=False):
    """Power [W] that 3D-ICE actually simulates -- i.e. that lands on a real floorplan block.

    Neither the raw McPAT sum nor the raw ``prepare_dice_trace`` sum is correct:

    * The **McPAT sum** includes hierarchy aggregates (``Processor``, ``Processor/Total
      Cores``, ``NUCA``, ``Processor/Total L3s``) that restate their children.
    * ``prepare_dice_trace`` renames leaves and adds IMC/IO/SoC, but it **leaves the
      aggregates in the dict**. They are dropped later, silently, because
      ``populate_template`` only substitutes placeholders the ``.flp`` actually contains.
      It also emits per-core entries for cores the floorplan does not have.

    On the 7nm linpack trace: 291 entries totalling 41.87 W, of which only **228 entries /
    17.78 W** land on a block. Summing everything overstates the simulated power by 2.36x, so
    a run labelled "50 W" was really simulating ~21 W.

    With ``detail=True`` returns ``(power_W, info)`` where ``info`` separates the harmless
    aggregate drops from the **real** loss: floorplan-shaped entries (``FPUs_7``, ``L3_7``,
    ...) for cores the floorplan lacks. The shipped floorplan is 7-core while the trace is
    8-core, so all of Core-7 -- about 2.0 W of genuine leaf power -- is discarded.
    """
    from HotGauge.thermal.ICE import Floorplan
    dice = prepare_dice_trace(trace, floorplan, tech_node, num_cores=num_cores,
                              already_dice_named=already_dice_named,
                              core_sources=core_sources)
    flp = floorplan if hasattr(floorplan, 'elements') else Floorplan.from_file(floorplan)
    blocks = {e.name for e in flp.elements}

    simulated, dropped_agg, dropped_leaf = 0.0, {}, {}
    for name, series in dice.powers.items():
        p = float(np.sum(np.asarray(series, dtype=float)))
        if name in blocks:
            simulated += p
        elif '/' in name or _is_mcpat_aggregate(name):
            dropped_agg[name] = p          # hierarchy aggregate: correctly discarded
        else:
            dropped_leaf[name] = p         # floorplan-shaped but no such block: REAL loss

    lost = float(sum(dropped_leaf.values()))
    if lost > 0.01 * max(simulated, 1e-12):
        # Real leaf power with nowhere to go -- almost always a core-count mismatch between
        # the floorplan and the trace. Silent here would mean quietly simulating a smaller
        # chip than the workload describes.
        LOGGER.warning(
            'Dropping %.3f W (%.1f%% of real leaf power) with no matching floorplan block: %s. '
            'Floorplan has %d blocks; check the core count matches the trace.',
            lost, 100.0 * lost / max(simulated + lost, 1e-12),
            ', '.join(sorted(dropped_leaf, key=lambda k: -dropped_leaf[k])[:5]), len(blocks))

    if not detail:
        return simulated
    return simulated, {'simulated_W': simulated,
                       'dropped_aggregate_W': float(sum(dropped_agg.values())),
                       'dropped_leaf_W': float(sum(dropped_leaf.values())),
                       'dropped_aggregates': dropped_agg,
                       'dropped_leaves': dropped_leaf}


_CORE_KEY_RGX = re.compile(r'^Core(\d+)(/.*)?$')


def replicate_trace_cores(trace, n_dst, n_src=None):
    """Tile an ``n_src``-core McPAT trace up to ``n_dst`` cores, round-robin.

    Our Sniper/McPAT traces are 8-core, but studying HPC power regimes needs a die large
    enough that hundreds of watts is a physically sensible *die-average* density -- which
    means far more cores than the trace has. Copying ``Core{i % n_src}`` onto ``Core{i}``
    models a homogeneous many-core running the same kernel on every core, which is exactly
    the workload an HPC throughput study assumes.

    Non-core keys (``BUSES``, ``Processor``, aggregates) are passed through untouched; they
    are not per-core and ``die_power_of_trace`` already ignores the ones that are not real
    floorplan blocks.

    This replicates *activity*, not a new simulation: it assumes every core runs the same
    workload phase simultaneously, which is the worst case for peak temperature and the
    right assumption for a dense LINPACK-style sweep. It would be wrong for a study of
    heterogeneous or phase-shifted workloads.
    """
    powers = dict(trace.powers) if hasattr(trace, 'powers') else dict(trace)
    if n_src is None:
        idx = {int(m.group(1)) for m in
               (_CORE_KEY_RGX.match(k) for k in powers) if m}
        if not idx:
            raise ValueError('trace has no Core<N> keys to replicate')
        n_src = max(idx) + 1
    if n_dst < n_src:
        raise ValueError('n_dst ({}) < n_src ({}): replication cannot drop cores'
                         .format(n_dst, n_src))
    if n_dst == n_src:
        return (type(trace)(powers, trace.time_step)
                if hasattr(trace, 'time_step') else powers)

    out = dict(powers)
    for key, val in powers.items():
        m = _CORE_KEY_RGX.match(key)
        if not m:
            continue
        src_i = int(m.group(1))
        rest = m.group(2) or ''
        for dst_i in range(n_src, n_dst):
            if dst_i % n_src != src_i:
                continue
            out['Core{}{}'.format(dst_i, rest)] = np.copy(val)
    if hasattr(trace, 'time_step'):
        return type(trace)(out, trace.time_step)
    return out


def scale_trace_to_die_power(trace, floorplan, tech_node, target_W, num_cores=8,
                             core_sources=None):
    """Rescale a McPAT-named trace so the **die** dissipates ``target_W``.

    Scaling is linear, so one evaluation of the true die power solves for the factor exactly.
    Returns ``(scaled_trace, scale, original_die_W)``.
    """
    from HotGauge.power.traces import BasicPowerTrace
    current = die_power_of_trace(trace, floorplan, tech_node, num_cores, core_sources)
    if current <= 0:
        raise ValueError('Trace puts no positive power on the die')
    scale = float(target_W) / current
    scaled = BasicPowerTrace({u: np.asarray(v, dtype=float) * scale
                              for u, v in trace.powers.items()}, trace.time_step)
    return scaled, scale, current


def mcpat_tref_from_trace_dir(trace_dir):
    """Read the true leakage anchor temperature [K] out of the trace's McPAT XML.

    ``T_ref`` is the temperature at which McPAT extracted the baseline leakage, and it anchors
    the entire leakage-vs-temperature correction. It must never be guessed: our Sniper->McPAT
    pipeline writes a fixed value (``snipersim/tools/mcpat.py``:
    ``<param name="temperature" value="330"/>``), while ``leakage.py``'s historical default was
    360 K. With a ~10-15 K doubling constant a 30 K anchor error is a ~4x leakage error at
    every temperature, biased *optimistic* -- it under-predicts leakage and therefore
    under-predicts thermal runaway.

    Returns None if no XML is present (e.g. the shipped example trace), so callers can fall
    back explicitly rather than silently.
    """
    xmls = sorted(glob.glob(os.path.join(trace_dir, '*.xml')))
    if not xmls:
        return None
    rgx = re.compile(r'<param\s+name="temperature"\s+value="([0-9.]+)"')
    with open(xmls[0]) as f:
        m = rgx.search(f.read())
    return float(m.group(1)) if m else None


def load_calibrated_leakage_model(json_path, extrapolate=True):
    """Build a ``LeakageModel`` from ``examples/calibrate_leakage_model.py`` output.

    Returns ``(model, t_ref_K)``. Uses ``LeakageModel.from_table`` rather than collapsing the
    curve to one doubling constant, because McPAT's measured response is **not** a single
    exponential: on the 7nm trace the local doubling constant runs from ~127 K between
    320-330 K down to ~10 K between 350-360 K. Fitting one exponential through that is wrong
    at both ends -- it overstates the benefit of cooling an already-cool block and understates
    the leakage of a hot one.
    """
    with open(json_path) as f:
        cal = json.load(f)
    temps = [r['T_K'] for r in cal['rows']]
    rel = cal['rel_leakage']
    if len(temps) != len(rel):
        raise ValueError('Malformed calibration file {}: rows/rel_leakage length mismatch'
                         .format(json_path))
    if extrapolate:
        # Clamping above the measured range freezes the feedback term and makes a divergent
        # configuration look convergent -- see LeakageModel.from_table_extrapolated.
        model = LeakageModel.from_table_extrapolated(temps, rel)
    else:
        model = LeakageModel.from_table(temps, rel)
    return model, float(cal['t_ref_xml_K'])


def load_simulated_leakage_model(path=None, mechanism='full', extrapolate=True):
    """``(LeakageModel, T_ref_K)`` from the SPICE run -- the simulated alternative to
    :func:`load_calibrated_leakage_model`.

    Same signature shape and same return contract, so a study can swap one for the other with a
    flag. What changes underneath is everything that matters:

    ================  ==================================  ==================================
    ..                ``load_calibrated_leakage_model``    ``load_simulated_leakage_model``
    ================  ==================================  ==================================
    source            eleven McPAT runs                    ngspice + BSIM-CMG on the ASAP7 card
    what it really is CACTI's hard-coded ``I_off_n[0][*]`` the vendor's model, fitted to nothing
    range             300-400 K                            **200-500 K**
    below range       clamps at 300 K                       clamps at 200 K
    ================  ==================================  ==================================

    `[!]` **The anchor is the same 330 K either way**, which is what makes the swap a controlled
    one: both tables are renormalised at call time to the pipeline's own ``T_ref``
    (``mcpat_tref``), so only the *shape* of the curve changes and no level is smuggled in with
    it. See §P0.13.

    ``mechanism`` selects the bracket: ``'full'`` is the card as ASAP7 wrote it, ``'gidl_off'``
    the same card with GIDL disabled. They differ ~40x at 200 K and agree above 300 K, and ASAP7
    is a *predictive* PDK, so **any sub-ambient number should be quoted across both**.
    """
    from HotGauge.power.device_leakage import load_simulated_curve
    curve = load_simulated_curve(path=path, mechanism=mechanism)
    model = curve.as_leakage_model(extrapolate=extrapolate)
    return model, float(curve.meta['anchor_K'])


#: The leakage curves a study driver may select, and what each one is.
LEAKAGE_CURVES = ('pipeline', 'simulated', 'simulated-gidl-off')


def load_leakage_model(which='pipeline', calibration=None, simulated=None, extrapolate=True):
    """One entry point for all of :data:`LEAKAGE_CURVES`, returning ``(model, T_ref_K)``.

    `[!]` ``'pipeline'`` is the **default everywhere and must stay that way** until a deliberate
    catalogue re-run says otherwise -- exactly the discipline ``--rbb-policy`` follows. Every
    recorded result in this project was produced on the pipeline curve; changing the default
    would silently move all of them.
    """
    if which == 'pipeline':
        if calibration is None:
            raise ValueError("the 'pipeline' curve needs a calibration file path")
        return load_calibrated_leakage_model(calibration, extrapolate=extrapolate)
    if which == 'simulated':
        return load_simulated_leakage_model(simulated, 'full', extrapolate)
    if which == 'simulated-gidl-off':
        return load_simulated_leakage_model(simulated, 'gidl_off', extrapolate)
    raise ValueError('unknown leakage curve {!r}; expected one of {}'
                     .format(which, LEAKAGE_CURVES))


def find_split_files(trace_dir):
    """Return ``block_powers_split_*.json`` in ``trace_dir`` sorted by timestep tick."""
    import re
    rgx = re.compile(r'block_powers_split_(\d+)\.json')
    files = glob.glob(os.path.join(trace_dir, 'block_powers_split_*.json'))
    def tick(fp):
        m = rgx.search(os.path.basename(fp))
        return int(m.group(1)) if m else -1
    return sorted(files, key=tick)


# ---------------------------------------------------------------------------
# Convert a McPAT-named power trace into the 3D-ICE (floorplan-named) trace
# ---------------------------------------------------------------------------
def prepare_dice_trace(trace, floorplan, tech_node, num_cores=8, core_sources=None,
                       already_dice_named=False):
    """McPAT-named block-power trace -> 3D-ICE-ready (floorplan-named) trace.

    Mirrors ``examples/ICE_simulation_from_MCPAT.prepare_trace`` but with ``num_cores``
    parameterized (the shipped helper hardcodes 8). Renames McPAT units to floorplan names,
    splits L3 across cores, and adds the HotGauge-modeled IMC/IO/SoC units (whose power is
    split by floorplan block area).

    ``already_dice_named=True`` skips the whole translation: the trace's keys are taken to be
    floorplan element names as they stand. That is what a floorplan McPAT knows nothing about
    needs -- the GA100 accelerator die in ``thermal.accelerator_floorplan`` has no cores, no L3
    to split across them and no IMC/IO model, so every step of the McPAT path either fails or
    invents power that is not in the budget. Nothing on the McPAT path changes.
    """
    if already_dice_named:
        return trace
    from HotGauge.power.mcpat import swap_cores, mcpat_block_powers_to_DICE
    from HotGauge.power.hotgauge_models import add_extra_DICE_units
    if core_sources:
        trace = swap_cores(trace, core_sources)
    trace = mcpat_block_powers_to_DICE(trace, num_cores)
    trace = add_extra_DICE_units(trace, floorplan, tech_node)
    return trace


# ---------------------------------------------------------------------------
# Steady-state helpers (pure Python -- unit-tested without the 3D-ICE binary)
# ---------------------------------------------------------------------------
STEADY_REDUCERS = {'mean': np.mean, 'max': np.max}


def collapse_trace_for_steady(trace, reduce='mean'):
    """Reduce an N-timestep power trace to the single representative step a steady solve needs.

    A 3D-ICE steady solve has no notion of time: it wants one power value per block. ``reduce``
    picks the operating point --

    * ``'mean'`` (default): time-averaged power. The right choice for "what temperature does
      this cooling solution hold the chip at over this workload".
    * ``'max'``: per-block peak power. A worst-case bound, NOT a physical instant -- different
      blocks peak at different times, so the result is hotter than any real moment.

    Returns a new ``BasicPowerTrace`` of length 1 with the same ``time_step``.
    """
    from HotGauge.power.traces import BasicPowerTrace
    try:
        reduce_fn = STEADY_REDUCERS[reduce]
    except KeyError:
        raise ValueError('reduce must be one of {}, got {!r}'.format(
            sorted(STEADY_REDUCERS), reduce))
    powers = {unit: np.asarray([float(reduce_fn(np.asarray(series, dtype=float)))])
              for unit, series in trace.powers.items()}
    return BasicPowerTrace(powers, trace.time_step)


class SteadyStateUnsupportedError(RuntimeError):
    """Raised when a steady solve is requested on a stack 3D-ICE cannot solve in steady state."""


def assert_steady_supported(stack_template):
    """Reject steady-state solves on pluggable-heatsink stacks -- they fail SILENTLY.

    3D-ICE's ``emulate_steady`` (sources/thermal_data.c) bails out immediately for a pluggable
    top heatsink::

        if (tdata->ThermalGrid.TopHeatSink->SinkModel == TDICE_HEATSINK_TOP_PLUGGABLE)
            return TDICE_SOLVER_ERROR ; //TODO: support steady state pluggable sink

    but ``3D-ICE-Emulator.c`` writes its FINAL output *after* the loop regardless of how the
    loop ended, and prints nothing to stderr. The result is a perfectly well-formed Tflp file
    containing the untouched **initial temperature** for every block -- which a feedback loop
    will happily "converge" on in 2 iterations. Fail loudly instead.

    Affects the FMU stacks (``skylake_HS483``, ``skylake_kryos``); the plain ``skylake``
    convection stack is fine.
    """
    from HotGauge.thermal.ICE import parse_pluggable_heatsink_from_stack_file
    plugin = parse_pluggable_heatsink_from_stack_file(stack_template)
    if plugin:
        raise SteadyStateUnsupportedError(
            "Stack {!r} uses pluggable heatsink {!r}, which 3D-ICE cannot solve in steady "
            "state: emulate_steady() returns TDICE_SOLVER_ERROR and the emulator then writes "
            "the UNSOLVED initial temperature to the Tflp output without any error. Use "
            "mode='transient' for this stack, or a non-pluggable stack (e.g. 'skylake') for "
            "steady-state runs.".format(stack_template, plugin))


def broadcast_steady_temps(steady_temps, n_steps):
    """Expand a steady solve's one-temperature-per-block result into per-timestep series.

    ``converge_power_temperature``/``rescale_trace`` require the temperature series to match
    the power series length exactly (they raise otherwise). A steady solve yields a single
    equilibrium temperature per block, which applies to every timestep of the original trace,
    so it is repeated ``n_steps`` times.
    """
    out = {}
    for block, value in steady_temps.items():
        arr = np.asarray(value, dtype=float).ravel()
        if arr.size == 0:
            raise ValueError('Steady solve returned no temperature for block {!r}'.format(block))
        out[block] = np.full(n_steps, float(arr[0]))
    return out


# ---------------------------------------------------------------------------
# The 3D-ICE thermal solve, packaged as a converge_power_temperature callable
# ---------------------------------------------------------------------------
class ICEThermalSolver(object):
    """Callable ``power_trace -> {flp_block: [T_K, ...]}`` backed by a 3D-ICE transient run.

    Each call runs one 3D-ICE simulation of the supplied power trace in a fresh per-iteration
    run directory and returns the per-block average temperatures (Kelvin) from the ``Tflp``
    (``die_elements.temps``) output.

    Two solver modes
    ----------------
    ``mode='transient'`` (default) replays the whole trace through ``ICETransientSim``,
    preserving the original behaviour exactly.

    ``mode='steady'`` collapses the trace to one operating point (see
    ``collapse_trace_for_steady``) and runs a single ``ICESteadySim``. This is the mode to use
    for **cooling-technology comparisons**: short transients (a few ms) never diffuse past the
    die -- the thermal penetration depth is far shorter than die+TIM+spreader -- so convection
    and heatsink-FMU stacks return identical die temperatures and the cooling solution is
    invisible. A steady solve reaches the true equilibrium where the heatsink actually matters.
    It is also much cheaper per feedback iteration (one solve instead of N slots) and needs no
    warmup, since equilibrium is independent of the initial condition.

    Parameters
    ----------
    stack_template, flp_template : paths passed to the sim class.
    tech_node    : int nm (7/10/14), used by the IMC/IO/SoC power model.
    run_base_dir : directory under which ``iter_000/``, ``iter_001/`` ... are created.
    initial_temp : ICESimConfig ``initial_temp`` -- a scalar K, or ``(tstack_file, sink_K)``
                   to resume from a warmup. The warmup is the caller's responsibility and is
                   held fixed across feedback iterations (a documented approximation: the
                   soak state's own weak leakage/T dependence is not re-converged).
                   Physically irrelevant in ``'steady'`` mode.
    plugin_args  : heat-sink plugin args (e.g. fan rpm), or None.
    num_cores, core_sources : forwarded to ``prepare_dice_trace``.
    single_thread : run one sim directly vs. via GNU parallel.
    mode          : ``'transient'`` or ``'steady'``.
    steady_reduce : ``'mean'`` or ``'max'``; how ``'steady'`` mode picks the operating point.
    """

    SIM_MODES = ('transient', 'steady')

    def __init__(self, stack_template, flp_template, tech_node, run_base_dir,
                 initial_temp=DEFAULT_TREF_K, plugin_args=None, num_cores=8,
                 core_sources=None, single_thread=True, steps_per_slot=None,
                 mode='transient', steady_reduce='mean', session_cache=None,
                 extra_die_outputs=None, already_dice_named=False, mr_temps=False,
                 mr_flp_template=None, mr_powers=None):
        if mode not in self.SIM_MODES:
            raise ValueError('mode must be one of {}, got {!r}'.format(self.SIM_MODES, mode))
        if steady_reduce not in STEADY_REDUCERS:
            raise ValueError('steady_reduce must be one of {}, got {!r}'.format(
                sorted(STEADY_REDUCERS), steady_reduce))
        self.stack_template = stack_template
        self.flp_template = flp_template
        self.tech_node = tech_node
        self.run_base_dir = run_base_dir
        self.initial_temp = initial_temp
        self.plugin_args = plugin_args
        self.num_cores = num_cores
        self.core_sources = core_sources
        self.single_thread = single_thread
        self.steps_per_slot = steps_per_slot
        self.mode = mode
        self.steady_reduce = steady_reduce
        # Optional ICESessionCache. When set (steady mode only), solves go through a persistent
        # 3D-ICE server that factorises once -- ~0.4 s per solve instead of ~85 s. The cache
        # guarantees correctness by hashing the system matrix inputs, so it is safe to share one
        # across a whole sweep; it rebuilds automatically when the sink or floorplan changes.
        if session_cache is not None and mode != 'steady':
            raise ValueError('session_cache requires mode="steady"; the transient path does '
                             'its own multi-step solve')
        self.session_cache = session_cache
        # Extra ``Tflp(...)`` instructions for dies beyond the processor die. A 3D stack reports
        # nothing for a die with no output instruction, so a stacked run without these would
        # silently return only the logic layer -- and a memory layer that is never read cannot
        # be shown to be the binding constraint.
        self.extra_die_outputs = list(extra_die_outputs or [])
        # §P0.19: report the photonic array's own tile temperatures. They come back in the same
        # named field as the blocks and are SPLIT OFF into ``last_mr_temps`` -- a tile is not a
        # block, and a sub-ambient tile in the block field would corrupt every peak, plateau
        # and floorplan metric downstream. Needs the stack to carry a powered array.
        self.mr_temps = bool(mr_temps)
        self.last_mr_temps = None
        # Set when the incoming trace is already keyed by floorplan element name, which is the
        # case for a floorplan built outside the McPAT pipeline. See prepare_dice_trace.
        self.already_dice_named = bool(already_dice_named)

        # The photonic cooling array, when the stack has one. It is a SECOND powered die element
        # above the silicon, so its heat removal is not part of the processor trace at all: the
        # trace carries what the chip dissipates and mr_powers carries what the array takes away,
        # and 3D-ICE conducts between them through the burial depth.
        #
        # This is what makes the burial depth mean anything. Subtracting the removal from the
        # processor trace instead -- which is what every study did until now -- puts the cooling
        # in the die's own source layer alongside the transistors, so the extracted watt crosses
        # no silicon and thinning the die changes nothing. See HotGauge.thermal.mr_array.
        if (mr_flp_template is None) != (mr_powers is None):
            raise ValueError('mr_flp_template and mr_powers must be given together')
        # §P0.25 (F4): the array is wired for BOTH modes. In 'transient' the tile powers may be
        # per-slot series (``mr_array.tile_power_schedule``), rendered by the same
        # ``fill_mr_flp_template`` the steady path uses -- ICESim already joins a series. A
        # scalar per tile is broadcast by 3D-ICE's own floorplan semantics. The extractor cap
        # (``mr_temps``) stays steady-only: a per-slot tile temperature field is a different
        # output and nothing consumes it yet.
        if mr_flp_template is not None and mode != 'steady' and mr_temps:
            raise ValueError('mr_temps=True (the extractor cap) is wired for mode="steady" only')
        # The session cache DOES carry a cooling array as of 25 Aug 2026. The socket protocol
        # sends one flat power vector, "one value per floorplan element, in order", and with two
        # dies that order is the reverse of the stack's declaration order: 3D-ICE stores layers
        # bottom-up, so the processor die's blocks come first and the array's tiles follow.
        # ice_server.stack_floorplans owns that, and it is verified end to end against the
        # one-shot Emulator by test_two_die_server_matches_oneshot_emulator_by_name using an
        # asymmetric power pattern -- measured agreement 5.1e-4 K across a 121 K field.
        self.mr_flp_template = mr_flp_template
        self.mr_powers = dict(mr_powers) if mr_powers else None
        self._iter = 0

    def set_mr_powers(self, mr_powers):
        """Replace the array's tile powers between solves.

        The MR planner revises its plan every feedback iteration, and the tiles are a fixed grid,
        so the floorplan is written afresh each solve while the geometry stays put. Refuses to
        introduce an array the stack has no die element for -- that would render a stack with an
        unfilled ``{mr_flp_file}`` and fail far downstream.
        """
        if self.mr_flp_template is None:
            raise ValueError('this solver has no cooling array; construct it with '
                             'mr_flp_template= to give the stack one')
        self.mr_powers = dict(mr_powers)
        return self

    def session_powers(self, steady_trace, session):
        """The flat power dict for one persistent-session solve: processor blocks **and** tiles.

        Separated out because leaving the tiles off does not fail. ``solve_named`` zero-fills any
        floorplan element it is not given, so a stack would carry a cooling array that removes
        nothing and the run would read as the cooler being ineffective -- a wrong answer with no
        error attached, which is the failure mode this project keeps meeting.
        """
        powers = {b: float(np.ravel(v)[-1]) for b, v in steady_trace.powers.items()}
        if not self.mr_powers:
            return powers
        known = set(session.element_names())
        missing = [t for t in self.mr_powers if t not in known]
        if missing:
            raise RuntimeError(
                '{} tile powers name elements the stack does not have, e.g. {}. The array would '
                'silently remove nothing.'.format(len(missing), sorted(missing)[:5]))
        overlap = set(powers) & set(self.mr_powers)
        if overlap:
            raise RuntimeError(
                'tile names collide with processor block names: {}. One would overwrite the '
                'other in the power vector.'.format(sorted(overlap)[:5]))
        powers.update({t: float(np.ravel(v)[-1]) for t, v in self.mr_powers.items()})
        return powers

    def __call__(self, power_trace):
        dice_trace = prepare_dice_trace(power_trace, self.flp_template, self.tech_node,
                                        num_cores=self.num_cores, core_sources=self.core_sources,
                                        already_dice_named=self.already_dice_named)
        run_dir = os.path.join(self.run_base_dir, 'iter_{:03d}'.format(self._iter))
        self._iter += 1
        if self.mode == 'steady':
            return self._run_steady_and_read_temps(dice_trace, run_dir, len(dice_trace))
        return self._run_and_read_temps(dice_trace, run_dir)

    def _run_and_read_temps(self, dice_trace, run_dir):
        """Run 3D-ICE and read Tflp. Isolated so tests can override without the binary."""
        # Imported here so the module imports cleanly on machines without the toolchain.
        from HotGauge.thermal import ICETransientSim, ICESimConfig
        from HotGauge.thermal.ICE import load_3DICE_block_file, parse_file_name_from_output_line

        outputs = ([ICETransientSim.OUTPUT_TSTACK_FINAL, ICETransientSim.DIE_TFLP_OUTPUT]
                   + self.extra_die_outputs)
        config = ICESimConfig(initial_temp=self.initial_temp, plugin_args=self.plugin_args,
                              output_list=outputs)
        mr_kwargs = {}
        if self.mr_flp_template is not None:
            # §P0.25: the array die in a transient. Series per tile must match the trace length
            # (one value per slot); scalars are broadcast to it here so the floorplan carries
            # one value per slot for every element, as 3D-ICE expects.
            n = len(dice_trace)
            mr_kwargs = {'mr_flp_template': self.mr_flp_template,
                         'mr_powers': {t: (np.full(n, float(np.ravel(v)[0]))
                                           if np.size(v) == 1 else np.asarray(v, dtype=float))
                                       for t, v in self.mr_powers.items()}}
            bad = [t for t, v in mr_kwargs['mr_powers'].items() if v.shape != (n,)]
            if bad:
                raise ValueError('tile power series must have one value per slot ({}); {} '
                                 'tiles do not, e.g. {}'.format(n, len(bad), bad[:3]))
        sim = ICETransientSim(self.stack_template, self.flp_template, dice_trace, config,
                              run_dir, steps_per_slot=self.steps_per_slot, **mr_kwargs)
        if self.single_thread:
            ICETransientSim.run([sim])
        else:
            ICETransientSim.run_with_parallels([sim])

        tflp_name = parse_file_name_from_output_line(ICETransientSim.DIE_TFLP_OUTPUT)
        tflp_file = os.path.join(sim.run_path, tflp_name)
        # Kelvin (convert_K_to_C=False) so it matches the leakage model's default temp_units.
        return die_block_temps(load_3DICE_block_file(tflp_file, convert_K_to_C=False))

    def _run_steady_and_read_temps(self, dice_trace, run_dir, n_steps):
        """One 3D-ICE steady solve at the collapsed operating point; T broadcast to n_steps.

        Isolated (like ``_run_and_read_temps``) so tests can override it without the binary.
        """
        from HotGauge.thermal import ICESteadySim, ICESimConfig
        from HotGauge.thermal.ICE import load_3DICE_block_file, parse_file_name_from_output_line

        # Must come before the (expensive) run: a pluggable-heatsink steady solve produces a
        # plausible-looking file full of the initial temperature instead of failing.
        assert_steady_supported(self.stack_template)

        steady_trace = collapse_trace_for_steady(dice_trace, reduce=self.steady_reduce)
        # Note ICESteadySim.DIE_TFLP_OUTPUT differs from the transient one: it reports at
        # 'final' rather than per 'slot', so the Tflp file holds exactly one row per block.
        outputs = ([ICESteadySim.OUTPUT_TSTACK_FINAL, ICESteadySim.DIE_TFLP_OUTPUT]
                   + self.extra_die_outputs)
        if self.mr_temps:
            if not self.mr_powers:
                raise ValueError('mr_temps=True asks for the array die\'s temperatures but this '
                                 'solver carries no array (mr_flp_template/mr_powers)')
            if MR_DIE_TFLP_OUTPUT not in outputs:
                outputs = outputs + [MR_DIE_TFLP_OUTPUT]
        config = ICESimConfig(initial_temp=self.initial_temp, plugin_args=self.plugin_args,
                              output_list=outputs)
        sim = ICESteadySim(self.stack_template, self.flp_template, steady_trace, config, run_dir,
                           mr_flp_template=self.mr_flp_template,
                           mr_powers=self.mr_powers)

        if self.session_cache is not None:
            # Persistent path: render IC.stk/IC.flp but do not spawn the Emulator. The session
            # holds the factorisation, so this solve costs ~0.4 s instead of ~85 s. The cache
            # keys on a hash of everything the system matrix is built from, so it silently
            # reuses across a power sweep and rebuilds when the sink or floorplan changes --
            # see ICESessionCache.
            sim.prep_for_run()
            session = self.session_cache.session(sim.stack_file)
            powers = self.session_powers(steady_trace, session)
            named = session.solve_named(powers)
            named = self._split_mr_temps(named)
            steady = {b: np.array([t]) for b, t in named.items()}
            return broadcast_steady_temps(steady, n_steps)

        try:
            if self.single_thread:
                ICESteadySim.run([sim])
            else:
                ICESteadySim.run_with_parallels([sim])
        except Exception as exc:
            # `[!]` 3D-ICE dies during "Preparing thermal data" with an EMPTY stderr when the
            # system is larger than SuperLU 4.3 will factorise here, so the only symptom is an
            # ExecutableJobError after a long wall time -- measured at ~75 minutes per point,
            # four times over, in the §P0.17 catalogue re-run. Attach the size so the next
            # reader gets the diagnosis instead of the symptom.
            raise _with_stack_size_diagnosis(exc, sim)

        # One Tflp file per die, merged by block name. Reading the names from the files
        # themselves means nothing here assumes an ordering across dies -- which is exactly the
        # assumption a stacked run must not make silently.
        steady = {}
        for line in ([ICESteadySim.DIE_TFLP_OUTPUT] + self.extra_die_outputs
                     + ([MR_DIE_TFLP_OUTPUT] if self.mr_temps else [])):
            tflp_file = os.path.join(sim.run_path, parse_file_name_from_output_line(line))
            if not os.path.isfile(tflp_file):
                raise RuntimeError(
                    'no Tflp output at {} for instruction {!r}. A die without an output '
                    'instruction reports nothing.'.format(tflp_file, line))
            steady.update(die_block_temps(load_3DICE_block_file(tflp_file,
                                                                convert_K_to_C=False)))
        steady = self._split_mr_temps(steady)
        return broadcast_steady_temps(steady, n_steps)

    def _split_mr_temps(self, named):
        """Take the tile temperatures out of a solved field into ``last_mr_temps``."""
        if not self.mr_temps or not self.mr_powers:
            return named
        tiles = set(self.mr_powers)
        mr = {k: float(np.ravel(v)[-1]) for k, v in named.items() if k in tiles}
        if not mr:
            raise RuntimeError('mr_temps=True but the solved field carries no tile temperatures; '
                               'the stack\'s output section does not report the array die')
        self.last_mr_temps = mr
        return {k: v for k, v in named.items() if k not in tiles}


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------
#: The array die's average-temperature output instruction (die instance MR_ARRAY, see die_stack).
MR_DIE_TFLP_OUTPUT = 'Tflp (MR_ARRAY, "mr_elements.temps", average, final ) ;'


def peak_temp_K(temps, t_floor_K=200.0):
    """Hottest real block temperature in a solved field, or None if there is none.

    Sub-floor readings are excluded: 3D-ICE emits 0 K for floorplan elements outside the die
    layer, and ``Time`` is not a temperature (see ``die_block_temps``).
    """
    if not temps:
        return None
    peak = -np.inf
    for v in temps.values():
        v = np.asarray(v, dtype=float)
        if t_floor_K is not None:
            v = v[v >= t_floor_K]
        if v.size:
            peak = max(peak, float(np.max(v)))
    return None if peak == -np.inf else peak


def run_leakage_feedback(baseline_trace, leakage_ref, thermal_solve_fn, model=None,
                         T_ref=DEFAULT_TREF_K, num_cores=8, tol_K=0.1, max_iter=10,
                         relax=0.5, max_power_growth=10.0, t_floor_K=200.0,
                         max_temp_K=1000.0, bridge_aggregates=False,
                         verify=True, verify_tol_K=1.0, verify_factor=0.5,
                         verify_max_levels=2, min_relax=0.025, adaptive_relax=True,
                         residual_convergence=True, name_map=None):
    """Run the fixed-point leakage feedback given a baseline trace and a thermal solver.

    baseline_trace   : McPAT-named PowerTrace (leakage extracted at ``T_ref``).
    leakage_ref      : ``{mcpat_unit: leakage}`` (scalar or per-timestep series), typically
                       from ``load_leakage_ref(find_split_files(trace_dir))``.
    thermal_solve_fn : callable(PowerTrace) -> {flp_block: [T_K, ...]}. Use ``ICEThermalSolver``
                       in production, or any callable (e.g. a mock) in tests.
    model            : a ``LeakageModel``; defaults to the exponential (doubles per 10 C).
    num_cores        : controls whether floorplan names carry a core index in the name bridge.
    name_map         : optional callable mapping a trace unit name to a floorplan block name.
                       Pass ``lambda u: u`` when the trace is already keyed by floorplan block
                       names -- otherwise the McPAT map is used and returns None for every
                       unrecognised name, which silently disables the feedback rather than
                       raising.
    relax            : under-relaxation factor (default 0.5) -- damps overshoot so a real
                       3D-ICE-in-the-loop solve is less likely to spike into runaway.
    max_power_growth : stop and flag runaway if total power exceeds this multiple of baseline
                       (default 10x) -- caught before the next 3D-ICE solve, so a runaway
                       workload/stack can't feed the emulator power that makes it crash.
    t_floor_K        : ignore per-block temperatures below this (default 200 K) -- 3D-ICE emits
                       0 K for floorplan elements outside the die layer; those must not scale.
    max_temp_K       : flag runaway as soon as any block's solved temperature exceeds this
                       (default 1000 K) -- names the offending block, catching a localized
                       single-block runaway at the first unphysical solve.

    Damping verification (``verify``, default **on**)
    ------------------------------------------------
    The leakage fixed point needs damping that cannot be predicted in advance, and getting it
    wrong is silent in both directions: an under-damped run can diverge where a perfectly good
    steady state exists, and it can also satisfy the tolerance at a partially-converged field.
    The true cliff on the 34-core die was only found by tightening ``relax`` by hand four times
    (0.5 -> 0.1 -> 0.05 -> 0.025 -> 0.0125) and watching the answer move ~100 K. Two of the
    three largest errors in this project were exactly that, so it is now checked automatically
    instead of being left to the caller's judgement.

    The run is repeated at ``relax * verify_factor`` and the two **peak temperatures** must
    agree within ``verify_tol_K``. If they do not, damping is tightened again, up to
    ``verify_max_levels`` extra levels. The result reported is always the finest damping level
    that participated in an agreeing pair.

    This also makes ``diverged`` mean *diverged at every damping tried* rather than "diverged
    at the one damping I happened to pick": if a level diverges and a tighter one converges,
    the converged answer wins and the divergence is recorded as a numerical artefact.

    Cost is ~2x a single run (a converged point is 2-3 solves at ~0.6 s each with a persistent
    session), which is cheap next to re-doing a study.

    Returns the dict from ``converge_power_temperature`` ('power_trace', 'temp_trace',
    'iterations', 'converged', 'diverged', 'max_delta_K', 'residual_K', 'history') plus, when
    ``verify`` is on:
        'verified'      : bool -- two damping levels agreed on the peak (or all levels agreed
                          it diverges),
        'unconverged'   : bool -- the opposite; the number is NOT safe to quote,
        'peak_spread_K' : peak-temperature disagreement between the two finest levels,
        'verification'  : list of per-level dicts {relax, peak_K, converged, diverged,
                          iterations, residual_K}.
    """
    if model is None:
        model = LeakageModel.exponential()
    # A caller whose trace is ALREADY keyed by floorplan block name must be able to say so.
    #
    # This function used to build its own McPAT->floorplan map unconditionally, and that map
    # returns None for any name it does not recognise -- so for a floorplan McPAT knows nothing
    # about, NO block ever matched and the leakage update was silently applied to nothing. Every
    # accelerator run made before this fix was a constant-power solve wearing the name of a
    # coupled one: residual 0.0000 K at the first iteration, and results bit-identical across a
    # 60% change in leakage fraction and across two different leakage MODELS. That last symptom
    # is what finally gave it away, and it should have been obviously wrong the first time.
    #
    # An explicit name_map (identity, for such callers) overrides the McPAT machinery entirely.
    if name_map is not None:
        supplied_name_map = name_map
        if bridge_aggregates:
            _inner_solve = thermal_solve_fn

            def thermal_solve_fn(trace, _f=_inner_solve):
                return augment_temps_with_aggregates(_f(trace), num_cores=num_cores)
        name_map = supplied_name_map
    elif bridge_aggregates:
        # Let aggregates whose power IS on the die (L3) participate in the feedback instead of
        # sitting frozen at T_ref. Wrapping the solver keeps this orthogonal to the solver
        # itself, so steady/transient/mock all get it identically.
        name_map = aggregate_aware_name_map(include_core_idx=(num_cores > 1),
                                            num_cores=num_cores)
        _inner_solve2 = thermal_solve_fn

        def thermal_solve_fn(trace, _f=_inner_solve2):
            return augment_temps_with_aggregates(_f(trace), num_cores=num_cores)
    else:
        name_map = mcpat_flp_name_map(include_core_idx=(num_cores > 1))

    def _solve_at(relax_level):
        # Tighter damping needs proportionally more iterations to reach the same residual, so
        # the budget scales with it (capped). Without this, a verification level would report
        # "hit max_iter" and the point would be flagged unconverged purely for lack of budget.
        level_iter = int(min(max_iter * (relax / relax_level), 4 * max_iter))
        return converge_power_temperature(
            baseline_trace, leakage_ref, thermal_solve_fn, model,
            T_ref=T_ref, temp_units='K', name_map=name_map,
            tol_K=tol_K, max_iter=max(max_iter, level_iter), relax=relax_level,
            max_power_growth=max_power_growth, t_floor_K=t_floor_K,
            max_temp_K=max_temp_K, residual_convergence=residual_convergence,
            adaptive_relax=adaptive_relax, min_relax=min(min_relax, relax_level))

    result = _solve_at(relax)
    if not verify:
        return result

    def _level(res, relax_level):
        return {'relax': relax_level,
                'peak_K': peak_temp_K(res.get('temp_trace') or {}, t_floor_K),
                'converged': bool(res.get('converged')),
                'diverged': bool(res.get('diverged')),
                'diverged_reason': res.get('diverged_reason'),
                'iterations': res.get('iterations'),
                'residual_K': res.get('residual_K'),
                'relax_final': res.get('relax_final')}

    levels = [_level(result, relax)]
    prev_res, prev_relax = result, relax
    verified, spread = False, None
    for _ in range(max(1, verify_max_levels)):
        this_relax = prev_relax * verify_factor
        res = _solve_at(this_relax)
        levels.append(_level(res, this_relax))
        a, b = levels[-2], levels[-1]

        if a['diverged'] and b['diverged']:
            # Divergent at both damping levels: as close to "no steady state exists" as this
            # method can get. Report the coarser (cheaper) run, which is equivalent.
            verified, spread, result = True, None, prev_res
            break
        if a['diverged'] != b['diverged']:
            # One of them is a numerical artefact. Keep tightening; the finer level is the
            # candidate answer, and it must still agree with a finer one before we trust it.
            LOGGER.warning('convergence verification: relax=%g %s but relax=%g %s -- damping '
                           'artefact, tightening further', a['relax'],
                           'diverged' if a['diverged'] else 'converged', b['relax'],
                           'diverged' if b['diverged'] else 'converged')
            prev_res, prev_relax, result = res, this_relax, res
            continue
        if a['peak_K'] is not None and b['peak_K'] is not None:
            spread = abs(a['peak_K'] - b['peak_K'])
            if spread <= verify_tol_K and a['converged'] and b['converged']:
                verified, result = True, res     # the finer level is the reported answer
                break
            LOGGER.warning('convergence verification: peak differs by %.2f K between relax=%g '
                           '(%.2f K) and relax=%g (%.2f K) -- tightening damping further',
                           spread, a['relax'], a['peak_K'], b['relax'], b['peak_K'])
        prev_res, prev_relax, result = res, this_relax, res

    if not verified:
        LOGGER.error('convergence verification FAILED after %d damping levels (%s). The peak '
                     'temperature still depends on the damping, so this point is NOT a '
                     'converged answer -- do not quote it.', len(levels),
                     ', '.join('relax={g[relax]:g}:{peak}'.format(
                         g=lv, peak=('{:.1f} K'.format(lv['peak_K']) if lv['peak_K'] is not None
                                     else 'diverged')) for lv in levels))
    # Note ``result`` is always the finest damping level that is still a candidate, so a
    # divergence that a tighter damping resolved has already been replaced by the converged
    # answer -- ``diverged`` here means "diverged at every damping tried", as intended.
    result = dict(result)
    result.update({'verified': verified, 'unconverged': not verified,
                   'peak_spread_K': spread, 'verification': levels})
    return result


def rebalance_trace_by_block_area(trace, floorplan, reference_floorplan, name_map=None):
    """Rescale each unit's power so every block keeps its power DENSITY from ``reference_floorplan``.

    Why this is needed, and it is not a convenience
    -----------------------------------------------
    A McPAT trace and a McPAT floorplan are internally consistent: the area a unit gets and the
    power it dissipates come from the same model. Replace the AREAS with published ones -- which
    is exactly what the floorplan-pack rebuild does -- and that consistency breaks, because the
    pack publishes no per-block power for any part and so cannot supply matching powers.

    Left alone the failure is spectacular rather than subtle. McPAT's core carries a large
    un-itemised area *and* a large un-itemised power, which the shipped tiler renders as one
    ``core_other`` slab: 15.85 mm^2 dissipating 22.2 W on the 34-core baseline, 1.4 W/mm^2. The
    published Golden Cove decomposition closes to 1.35%, so the rebuilt floorplan shrinks that
    slab 32x while the trace still hands it 38% of the die's power -- **28 W/mm^2**, and six of
    seven rebuilt floorplans had no steady state at a die average of 0.60 W/mm^2.

    So a rule is needed, and there are only two honest ones:

    * **hold each block's POWER** -- the same work in less area. Physically meaningful, but it
      requires McPAT's power for a block to be right when McPAT's area for that block is wrong by
      up to 30x, which is not a thing one input can be without the other.
    * **hold each block's power DENSITY**, which is this function. The die then dissipates the
      same watts per mm^2 of each kind of structure and only the *arrangement* changes -- which
      is what a floorplan sweep claims to vary and, before this, did not.

    Neither is free of assumption and this one says so: it means these floorplans compare
    **geometry at constant activity density**, not activity. An ISA comparison that needs
    per-block activity needs per-block power the pack does not have.

    ``reference_floorplan`` must carry the same block names as ``floorplan`` (both come from the
    shipped tiler, so they do). Blocks absent from the reference are left alone and counted in
    the returned metadata rather than silently dropped.

    Returns ``(rebalanced_trace, meta)``.
    """
    from HotGauge.power.traces import BasicPowerTrace
    from HotGauge.thermal.ICE import Floorplan
    name_map = name_map or mcpat_flp_name_map(include_core_idx=True)

    def _areas(path):
        fp = Floorplan.from_file(path) if isinstance(path, str) else path
        return {e.name: (e.width * e.height) / 1.0e6 for e in fp.elements}

    new = _areas(floorplan)
    ref = _areas(reference_floorplan)

    factors, unmatched, by_unit = {}, [], {}
    powers = {}
    for unit, series in trace.powers.items():
        block = name_map(unit)
        if block is None or block not in new or block not in ref or ref[block] <= 0:
            if block is not None and (block not in ref or block not in new):
                unmatched.append(block)
            powers[unit] = np.asarray(series, dtype=float)
            continue
        f = new[block] / ref[block]
        factors[block] = f
        by_unit[unit] = f
        powers[unit] = np.asarray(series, dtype=float) * f

    meta = {'n_blocks_rescaled': len(factors),
            'n_units_rescaled': len(by_unit),
            'n_units_left_alone': len(trace.powers) - len(by_unit),
            'factors_by_unit': by_unit,
            'blocks_not_in_both': sorted(set(unmatched)),
            'min_factor': min(factors.values()) if factors else None,
            'max_factor': max(factors.values()) if factors else None,
            'rule': 'each block keeps the W/mm^2 it has on the reference floorplan',
            'reference': reference_floorplan if isinstance(reference_floorplan, str) else '<obj>'}
    return BasicPowerTrace(powers, trace.time_step), meta
