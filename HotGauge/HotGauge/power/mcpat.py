import numpy as np

from HotGauge.configuration import mcpat_to_flp_name, NO_POWER_UNITS, DRAM_IMC_UNITS, \
                                   DRAM_IMC_POWER, DRAM_IO_UNITS, DRAM_IO_POWER, IMC_REGEX,\
                                   get_IO_SoC_powers
from HotGauge.configuration.mcpat import NoSuchMCPATUnitError, core_swap_rename_fn

################################################################################
############################## Trace Manipulation ##############################
################################################################################
# Each of these assumes traces based on block_powers.json format as an input

def swap_cores(trace, core_sources):
    """ Swaps unit traces per core based on specified core_sources

    core_sources: {mapped_core_i: mcpat_core_i}, otherwise don't swap (i:i is implied)

    returns BasicPowerTrace with specified core swaps
    """
    core_swap_fn = lambda unit: core_swap_rename_fn(unit, core_sources)
    return trace.rename_units(core_swap_fn)


################################################################################
########################## Conversion to 3D-ICE Inputs ###########################
################################################################################

def mcpat_block_powers_to_DICE(trace, num_cores):
    include_core_idx = True if num_cores > 1 else False
    trace = rename_mcpat_units_to_ICE_units(trace, include_core_idx)
    trace = split_L3_power(trace, num_cores)
    return trace

def rename_mcpat_units_to_ICE_units(trace, include_core_idx):
    def unit_rename_fn(unit, include_core_idx=include_core_idx):
        try:
            flp_label = mcpat_to_flp_name(unit, include_core_idx=include_core_idx)
            return flp_label
        except NoSuchMCPATUnitError:
            return unit
    return trace.rename_units(unit_rename_fn)

def split_L3_power(trace, num_cores):
    # Split the L3 power evenly among all cores
    is_multicore = True if num_cores > 1 else False
    L3_power_trace = np.array(trace['Processor/Total L3s']) / num_cores
    if is_multicore:
        for core_idx in range(num_cores):
            trace['L3_{}'.format(core_idx)] = L3_power_trace
    else:
        trace['L3'] = L3_power_trace
    return trace
