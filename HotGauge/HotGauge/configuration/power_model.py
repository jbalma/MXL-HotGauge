import os
import re
import glob
from collections import namedtuple

################################# Power Model Configuration ####################################
# Units with no power consumption
NO_POWER_UNITS = {'N', 'E', 'W', 'S','N_0','E_0','W_0','S_0'}

# HACK: Units that have missing power info @ most verbose MCPAT level
MISSING_POWER_INFO = {'Execution Unit', 'Memory Management Unit'}

# HACK: current sims don't have AVX power data
# NOTE: This was removed when running linpack sims with AVX power data
#
# This was hardcoded to range(8), which silently caps the pipeline at 8 cores: on a 34-core
# floorplan the solve dies with ``KeyError: 'AVXs_10'`` because AVXs_8.. were never marked
# power-free. Matched by pattern instead so any core count works. Keep the explicit 0-7 entries
# so anything doing a literal ``in NO_POWER_UNITS`` membership test still behaves as before.
NO_POWER_UNITS.update(['AVXs_{}'.format(n) for n in range(8)])

#: Floorplan block names that carry no power, for any core index.
NO_POWER_UNIT_PATTERNS = (re.compile(r'^AVXs_\d+$'),)


def is_no_power_unit(name):
    """True if ``name`` is a floorplan block that should be assigned zero power.

    Prefer this over ``name in NO_POWER_UNITS`` -- the set cannot express "for every core".
    """
    if name in NO_POWER_UNITS:
        return True
    return any(rgx.match(name) for rgx in NO_POWER_UNIT_PATTERNS)

################################ DRAM Power model

# Regex for IMC components (optional index after underscore)
IMC_REGEX = re.compile(r'^IMC(_(\d)+)?')

# Split DRAM power between some of the IO and IMC units
DRAM_IO_UNITS = {'IO_S'}
DRAM_IO_POWER = 0.8

DRAM_IMC_UNITS = {'IMC'}
DRAM_IMC_POWER = 0.2

################################ Static power for remaining IO/SoC units

# Power of 14nm is the baseline (500mw each)
IO_SoC_POWER_14nm = {'IO_N':0.5, 'SoC':0.5}
# Each tech node advancement scales power by this factor
IO_SoC_TECH_NODE_FACTOR = 0.9
# List of tech nodes and the number of steps of that node from baseline (14nm)
TECH_NODES = [('14nm', 0), ('10nm', 1), ('7nm',2)]
# Construct the factors for each tech node
IO_SoC_TECH_NODE_FACTORS = {node : IO_SoC_TECH_NODE_FACTOR**tech_node_steps
                            for node, tech_node_steps in TECH_NODES}

# Wrap lookup in a function for ease of use and adaptability
def get_IO_SoC_powers(node):
    """Returns a dictionary of IO and SOC powers for a given tech node"""
    if isinstance(node, int):
        node = '{}nm'.format(node)
    tech_node_factor = IO_SoC_TECH_NODE_FACTORS[node]
    # Scale the basline (14nm) powers based on this factor
    return {k:v*tech_node_factor for k,v in IO_SoC_POWER_14nm.items()}


BLOCK_POWERS_REGEX = re.compile(r'block_powers_(\d+)\.json')
def load_block_powers(simulation_dir):
    def get_tick(fp):
        f = os.path.basename(fp)
        return int(BLOCK_POWERS_REGEX.match(f).group(1))
    files = glob.glob(os.path.join(simulation_dir, 'block_powers_*.json'))
    # The glob also catches companion files like block_powers_split_<tick>.json (the
    # dynamic/leakage split emitted for temperature-dependent leakage feedback); only
    # numeric-tick block_powers_<tick>.json files are trace steps, so filter to those.
    files = [f for f in files if BLOCK_POWERS_REGEX.match(os.path.basename(f))]
    return sorted(files, key=get_tick)
