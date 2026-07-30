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
def prepare_dice_trace(trace, floorplan, tech_node, num_cores=8, core_sources=None):
    """McPAT-named block-power trace -> 3D-ICE-ready (floorplan-named) trace.

    Mirrors ``examples/ICE_simulation_from_MCPAT.prepare_trace`` but with ``num_cores``
    parameterized (the shipped helper hardcodes 8). Renames McPAT units to floorplan names,
    splits L3 across cores, and adds the HotGauge-modeled IMC/IO/SoC units (whose power is
    split by floorplan block area).
    """
    from HotGauge.power.mcpat import swap_cores, mcpat_block_powers_to_DICE
    from HotGauge.power.hotgauge_models import add_extra_DICE_units
    if core_sources:
        trace = swap_cores(trace, core_sources)
    trace = mcpat_block_powers_to_DICE(trace, num_cores)
    trace = add_extra_DICE_units(trace, floorplan, tech_node)
    return trace


# ---------------------------------------------------------------------------
# The 3D-ICE thermal solve, packaged as a converge_power_temperature callable
# ---------------------------------------------------------------------------
class ICEThermalSolver(object):
    """Callable ``power_trace -> {flp_block: [T_K, ...]}`` backed by a 3D-ICE transient run.

    Each call runs one full 3D-ICE transient simulation of the supplied power trace in a
    fresh per-iteration run directory and returns the per-block average temperatures (Kelvin)
    from the ``Tflp`` (``die_elements.temps``) output.

    Parameters
    ----------
    stack_template, flp_template : paths passed to ``ICETransientSim``.
    tech_node    : int nm (7/10/14), used by the IMC/IO/SoC power model.
    run_base_dir : directory under which ``iter_000/``, ``iter_001/`` ... are created.
    initial_temp : ICESimConfig ``initial_temp`` -- a scalar K, or ``(tstack_file, sink_K)``
                   to resume from a warmup. The warmup is the caller's responsibility and is
                   held fixed across feedback iterations (a documented approximation: the
                   soak state's own weak leakage/T dependence is not re-converged).
    plugin_args  : heat-sink plugin args (e.g. fan rpm), or None.
    num_cores, core_sources : forwarded to ``prepare_dice_trace``.
    single_thread : run one sim directly vs. via GNU parallel.
    """

    def __init__(self, stack_template, flp_template, tech_node, run_base_dir,
                 initial_temp=DEFAULT_TREF_K, plugin_args=None, num_cores=8,
                 core_sources=None, single_thread=True, steps_per_slot=None):
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
        self._iter = 0

    def __call__(self, power_trace):
        dice_trace = prepare_dice_trace(power_trace, self.flp_template, self.tech_node,
                                        num_cores=self.num_cores, core_sources=self.core_sources)
        run_dir = os.path.join(self.run_base_dir, 'iter_{:03d}'.format(self._iter))
        self._iter += 1
        return self._run_and_read_temps(dice_trace, run_dir)

    def _run_and_read_temps(self, dice_trace, run_dir):
        """Run 3D-ICE and read Tflp. Isolated so tests can override without the binary."""
        # Imported here so the module imports cleanly on machines without the toolchain.
        from HotGauge.thermal import ICETransientSim, ICESimConfig
        from HotGauge.thermal.ICE import load_3DICE_block_file, parse_file_name_from_output_line

        outputs = [ICETransientSim.OUTPUT_TSTACK_FINAL, ICETransientSim.DIE_TFLP_OUTPUT]
        config = ICESimConfig(initial_temp=self.initial_temp, plugin_args=self.plugin_args,
                              output_list=outputs)
        sim = ICETransientSim(self.stack_template, self.flp_template, dice_trace, config,
                              run_dir, steps_per_slot=self.steps_per_slot)
        if self.single_thread:
            ICETransientSim.run([sim])
        else:
            ICETransientSim.run_with_parallels([sim])

        tflp_name = parse_file_name_from_output_line(ICETransientSim.DIE_TFLP_OUTPUT)
        tflp_file = os.path.join(sim.run_path, tflp_name)
        # Kelvin (convert_K_to_C=False) so it matches the leakage model's default temp_units.
        return load_3DICE_block_file(tflp_file, convert_K_to_C=False)


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------
def run_leakage_feedback(baseline_trace, leakage_ref, thermal_solve_fn, model=None,
                         T_ref=DEFAULT_TREF_K, num_cores=8, tol_K=0.1, max_iter=10,
                         relax=0.5, max_power_growth=10.0, t_floor_K=200.0,
                         max_temp_K=1000.0):
    """Run the fixed-point leakage feedback given a baseline trace and a thermal solver.

    baseline_trace   : McPAT-named PowerTrace (leakage extracted at ``T_ref``).
    leakage_ref      : ``{mcpat_unit: leakage}`` (scalar or per-timestep series), typically
                       from ``load_leakage_ref(find_split_files(trace_dir))``.
    thermal_solve_fn : callable(PowerTrace) -> {flp_block: [T_K, ...]}. Use ``ICEThermalSolver``
                       in production, or any callable (e.g. a mock) in tests.
    model            : a ``LeakageModel``; defaults to the exponential (doubles per 10 C).
    num_cores        : controls whether floorplan names carry a core index in the name bridge.
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

    Returns the dict from ``converge_power_temperature`` ('power_trace', 'temp_trace',
    'iterations', 'converged', 'diverged', 'max_delta_K', 'history').
    """
    if model is None:
        model = LeakageModel.exponential()
    name_map = mcpat_flp_name_map(include_core_idx=(num_cores > 1))
    return converge_power_temperature(baseline_trace, leakage_ref, thermal_solve_fn, model,
                                      T_ref=T_ref, temp_units='K', name_map=name_map,
                                      tol_K=tol_K, max_iter=max_iter, relax=relax,
                                      max_power_growth=max_power_growth, t_floor_K=t_floor_K,
                                      max_temp_K=max_temp_K)
