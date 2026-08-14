"""Process-node performance characteristics, for cross-generation comparisons.

Why this module is separate, and what it is honest about
--------------------------------------------------------
Our floorplans exist at 14nm, 10nm and 7nm, and McPAT gives a power trace for each. That
captures the *physical* generational change -- area shrinks, power per operation falls, power
density rises. What it does NOT capture is that a newer part also clocks higher and does more
work per cycle, because every trace is the same Skylake microarchitecture at 3.8 GHz.

So a generational comparison needs two inputs the simulation cannot supply, and they are NOT
equally well founded:

``f_nominal_GHz`` -- **partially simulated.** Raising the clock raises dynamic power through the
    V/F relation, and the thermal model then responds to that: a faster part runs hotter, throttles
    sooner, and may need more cooling. The consequence of the assumption is computed, even though
    the assumption itself is an input.

``ipc_rel`` -- **pure assumption.** IPC is architectural. Our trace is one microarchitecture, so
    nothing in the pipeline can confirm or refute an IPC ratio; it is a post-hoc multiplier on
    throughput and nothing else. It does not change power, temperature or anything the solver
    sees. Treat any result that leans on it as a scenario, not a prediction.

The numbers below are illustrative of the industry trajectory, not measurements, and are meant
to be overridden. State them explicitly whenever a result depends on them.

Why the distinction matters
---------------------------
A conclusion resting on ``f_nominal`` differences has thermal physics behind it. A conclusion
resting on ``ipc_rel`` differences is arithmetic on an assumed ratio. Reporting them as one
number hides which is which, so ``generational_summary`` returns both the thermal-only and the
IPC-scaled comparison.
"""

import numpy as np

#: Frequency the shipped McPAT/Sniper traces were generated at. Running a node at a different
#: nominal clock rescales dynamic power against this reference.
TRACE_REFERENCE_GHZ = 3.8


class ProcessNode(object):
    """One process generation's performance characteristics.

    ``f_nominal_GHz`` feeds the thermal loop (via dynamic power scaling); ``ipc_rel`` is applied
    only to throughput at the very end. ``era`` and ``note`` exist so a result can be traced back
    to what was assumed.
    """

    def __init__(self, name, tech_node, f_nominal_GHz, ipc_rel=1.0, era='', note=''):
        self.name = name
        self.tech_node = int(tech_node)
        self.f_nominal_GHz = float(f_nominal_GHz)
        self.ipc_rel = float(ipc_rel)
        self.era = era
        self.note = note

    def dynamic_power_factor(self, f_ref_GHz=TRACE_REFERENCE_GHZ):
        """Dynamic-power multiplier for running at this node's clock instead of the trace's.

        Uses the shipped V/F table, so this is ``(f/f_ref) * (V(f)/V(f_ref))^2`` -- the standard
        relation, not a guess. This is what makes a higher-clocked node genuinely hotter in the
        coupled solve rather than just nominally faster.
        """
        from HotGauge.power.performance_model import dynamic_power_scale
        return dynamic_power_scale(self.f_nominal_GHz, f_ref_GHz)

    def __repr__(self):
        return ('ProcessNode({} {}nm, f_nom={:.2f} GHz, IPC={:.2f}x, {})'
                .format(self.name, self.tech_node, self.f_nominal_GHz, self.ipc_rel, self.era))


#: Illustrative trajectory for an Intel-like line, normalised to 14nm Skylake = 1.00 IPC.
#: Clocks are turbo-class figures; IPC ratios are the widely-reported generational steps
#: (Skylake -> Sunny Cove ~+18%, -> Golden Cove ~+19% on top). ADJUST THESE -- they are the
#: assumption every generational conclusion rests on.
NODES = {
    '14nm': ProcessNode('Skylake-class', 14, 4.0, 1.00, era='~2015-2020',
                        note='baseline for both clock and IPC'),
    '10nm': ProcessNode('Sunny-Cove-class', 10, 4.3, 1.18, era='~2019-2021',
                        note='early 10nm clocked poorly; IPC gain is the real advance'),
    '7nm': ProcessNode('Golden-Cove-class', 7, 5.0, 1.40, era='~2021-2023',
                       note='clock recovers and IPC compounds'),
}

#: A hypothetical next step, for "what would a 2026/2027 part look like" questions. Entirely
#: speculative -- there is no floorplan or power trace for it, so it can only be used as an
#: analytic target to compare an MR-assisted older node against.
FUTURE_NODE = ProcessNode('next-gen', 3, 5.5, 1.60, era='~2026-2027',
                          note='SPECULATIVE: no floorplan or trace exists for this node')


def throughput_gflops(f_effective_GHz, node, n_cores, flops_per_cycle=32.0):
    """Throughput including the node's IPC multiplier.

    ``f_effective_GHz`` comes from the thermal solve (nominal clock after temperature derating
    and throttling). The IPC factor is applied here and nowhere else, so removing it recovers
    the thermal-only number.
    """
    return float(f_effective_GHz) * float(flops_per_cycle) * int(n_cores) * node.ipc_rel


def generational_summary(results_by_node, n_cores, flops_per_cycle=32.0):
    """Compare nodes both ways: thermal-only, and with the assumed IPC applied.

    ``results_by_node`` maps node key -> dict with ``f_effective_GHz`` (and optionally
    ``label``). Returns one row per node carrying both numbers, because collapsing them into a
    single figure would hide which part of the difference is simulated and which is assumed.
    """
    rows = []
    for key, res in results_by_node.items():
        node = NODES.get(key)
        if node is None:
            raise KeyError('unknown node {!r}; known: {}'.format(key, sorted(NODES)))
        f_eff = float(res['f_effective_GHz'])
        thermal_only = f_eff * flops_per_cycle * n_cores
        rows.append({
            'node': key,
            'name': node.name,
            'era': node.era,
            'f_nominal_GHz': node.f_nominal_GHz,
            'f_effective_GHz': f_eff,
            'ipc_rel': node.ipc_rel,
            'gflops_thermal_only': thermal_only,
            'gflops_with_ipc': thermal_only * node.ipc_rel,
            'label': res.get('label', ''),
        })
    rows.sort(key=lambda r: -r['tech_node'] if 'tech_node' in r else 0)
    return rows


def describe_assumptions():
    """One-line-per-node statement of what is being assumed, for printing above any result."""
    out = ['process-node assumptions (illustrative, override before quoting):',
           '  {:<7s} {:<20s} {:<12s} {:>9s} {:>8s}'.format(
               'node', 'name', 'era', 'f_nom GHz', 'IPC')]
    for key in sorted(NODES, key=lambda k: -NODES[k].tech_node):
        n = NODES[key]
        out.append('  {:<7s} {:<20s} {:<12s} {:>9.2f} {:>8.2f}'.format(
            key, n.name, n.era, n.f_nominal_GHz, n.ipc_rel))
    out.append('  f_nominal feeds the thermal loop (power scales with f and V^2);')
    out.append('  IPC is a post-hoc throughput multiplier ONLY and is not simulated.')
    return '\n'.join(out)
