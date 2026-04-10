import logging
LOGGER = logging.getLogger(__name__)

import numpy as np

from HotGauge.utils import Floorplan
from HotGauge.configuration.power_model import DRAM_IMC_UNITS, DRAM_IO_UNITS, NO_POWER_UNITS, \
                                               DRAM_IMC_POWER, DRAM_IO_POWER, \
                                               get_IO_SoC_powers, IMC_REGEX

def get_IMC_IO_area(floorplan):
    total_IMC_area, total_IO_area = 0.0, 0.0
    for el in floorplan.elements:
        if el.name in DRAM_IMC_UNITS:
            total_IMC_area += el.area
        elif el.name in DRAM_IO_UNITS:
            total_IO_area += el.area
        # Skip no power units
        elif el.name in NO_POWER_UNITS:
            continue
        # Make sure the unit isn't an IMC
        elif IMC_REGEX.match(el.name):
            LOGGER.warn('{} encountered but not included in IMC area'.format(el.name))
    return total_IMC_area, total_IO_area

def add_extra_DICE_units(trace, floorplan, tech_node):
    """ Add units modeled as part of HotGauge

    floorplan [Floorplan or str]: is used to split IMC/IO power by area

    tech_node [int] : used to calulate SoC power
    """
    # Prepare to split IMC IO power (it is just IMC in the trace now)
    try:
        total_IMC_IO_power = trace['IMC']
    except KeyError as e:
        LOGGER.error('{} is missin IMC data'.format(trace.__class__))
        raise

    # Get utility traces that will be used later
    unit_power_trace = np.ones_like(total_IMC_IO_power)
    zero_power_trace = unit_power_trace * 0

    # Make sure we have an actual floorplan
    if isinstance(floorplan, str):
        floorplan = Floorplan.from_file(floorplan)

    # Split the IMC_IO power between IMC and IO
    total_IMC_power = DRAM_IMC_POWER * total_IMC_IO_power
    total_IO_power = DRAM_IO_POWER * total_IMC_IO_power

    # Compute the IMC and IO are to make sure it is split evenly
    total_IMC_area, total_IO_area = get_IMC_IO_area(floorplan)
    # Get the breakdown of SoC unit powers
    IO_SoC_power_splits = get_IO_SoC_powers(tech_node)
    for el in floorplan.elements:
        # Divide the IMC power
        if el.name in DRAM_IMC_UNITS:
            trace[el.name] = total_IMC_power * el.area / total_IMC_area * unit_power_trace
        # Divide the IO power
        elif el.name in DRAM_IO_UNITS:
            trace[el.name] = total_IO_power * el.area / total_IO_area * unit_power_trace
        # Add the units that are missing power models =(
        elif el.name in NO_POWER_UNITS:
             trace[el.name] = zero_power_trace.copy()
        elif el.name in IO_SoC_power_splits:
            trace[el.name] = unit_power_trace * IO_SoC_power_splits[el.name]
    return trace
