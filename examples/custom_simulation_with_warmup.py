#!/usr/bin/env python
""" This takes around 5 minutes on our X-year-old development server """

import os
import math
import random
from itertools import product
import sys
from pathlib import Path
import click

#path to HotGauge
sys.path.insert(0, str(Path("/data/jake_m/HotGauge/HotGauge")))

from HotGauge.thermal.utils import C_to_K
from HotGauge.power import BasicPowerTrace
from HotGauge.thermal import ICETransientSim, get_stack_template, ICESimConfig
from HotGauge.thermal.ICE import parse_file_name_from_output_line
from HotGauge.utils import Floorplan, FloorplanElement

from config import LOGGER, EXP_BASE_DIR, FLP_BASE_DIR, OUTPUT_DIR
FLP_DIR = os.path.join(OUTPUT_DIR, 'floorplans')

def get_1_cm2_flp():
    """ Returns a floorplan with two small elements and one big element """
    small_0 = FloorplanElement('small_0', 5000, 5000, 0, 0)
    IC = Floorplan([small_0], frmt='3D-ICE')
    IC.auto_place_element('small_1', 5000*5000, where='right')
    IC.auto_place_element('big', 5000*5000*2, where='above')
    return IC

def create_flp_template(area_cm2):
    flp = get_1_cm2_flp() * math.sqrt(area_cm2)
    flp_file_name = os.path.join(FLP_DIR, 'flp_{}_template.flp'.format(area_cm2))
    flp.to_file(flp_file_name, element_powers=True)
    return flp_file_name

SEED = 0xBADC0DE # for repeatable power generation
def get_power_trace(average_power_watts, time_slot, length):
    random.seed(int(SEED * average_power_watts))
    powers = {}
    factors = {'big' : 0.5, 'small_0' : 0.25, 'small_1': 0.25}
    for unit in ['big', 'small_0', 'small_1']:
        factor = factors[unit] * average_power_watts
        powers[unit] = [factor*(random.random()+0.5) for _ in range(length)]
    return BasicPowerTrace(powers, time_slot)


@click.command()
@click.option('--time-slot-ms', '-t', type=float, multiple=True, default=(0.2,0.4))
@click.option('--steps-per-slot', '-s', type=int, default=None)
@click.option('--flp-area-cm2', '-f', type=float, multiple=True, default=(0.2,0.5))
@click.option('--length-of-sim', '-l', type=int, default=25)
@click.option('--average-power-watts', '-p', type=int, multiple=True, default=(50,100))
@click.option('-1/-N','--single-threaded/--multi-threaded', default=False)
def run_sims(time_slot_ms, steps_per_slot, flp_area_cm2, length_of_sim, average_power_watts,
             single_threaded):
    time_slots_ms = time_slot_ms
    flp_areas_cm2 = flp_area_cm2
    average_powers_watts = average_power_watts

    HEAT_SINKS = [None, ('HS483', 6000)]

    flps = {}
    for flp_area in flp_areas_cm2:
        flps[flp_area] = create_flp_template(flp_area)

    warmup_sims = []
    warmup_stack_files = {}
    for area, sink in product(flp_areas_cm2, HEAT_SINKS):
        flp_template = flps[area]
        if sink is None:
            model, args = 'convection', None
            stk_template = get_stack_template('skylake')
        else:
            model, args = sink
            stk_template = get_stack_template('skylake_{}'.format(model))
        output_list = [ICETransientSim.OUTPUT_TSTACK_FINAL, ICETransientSim.DIE_TMAP_OUTPUT]
        sim_config = ICESimConfig(plugin_args=args, output_list=output_list)
        slot = 1 # seconds
        length = 2
        power_trace = get_power_trace(25, slot, length)
        # repeat the power trace three times
        repeated_power_trace = power_trace << power_trace << power_trace
        run_path = os.path.join(OUTPUT_DIR, 'warmups', '{}cm2'.format(area), str(model))
        sim = ICETransientSim(stk_template, flp_template, repeated_power_trace, sim_config, run_path)
        warmup_sims.append(sim)
        warmup_stack = os.path.join(sim.run_path, parse_file_name_from_output_line(output_list[0]))
        warmup_stack_files[sink, area] = warmup_stack

    if single_threaded:
        ICETransientSim.run(warmup_sims)
    else:
        ICETransientSim.run_with_parallels(warmup_sims)


    sims = []
    for slot_ms, area, power, sink in product(time_slots_ms, flp_areas_cm2, average_powers_watts, HEAT_SINKS):
        warmup_stack_file = warmup_stack_files[sink, area]
        flp_template = flps[area]
        if sink is None:
            model, args = 'convection', None
            stk_template = get_stack_template('skylake')
        else:
            model, args = sink
            stk_template = get_stack_template('skylake_{}'.format(model))
        output_list = [ICETransientSim.DIE_TMAP_OUTPUT, ICETransientSim.DIE_PMAP_OUTPUT]
        sim_config = ICESimConfig(plugin_args=args, output_list=output_list,
                                  initial_temp=(warmup_stack_file, 315))
        slot = slot_ms / 1000 # seconds
        power_trace = get_power_trace(power, slot, length_of_sim)
        run_path = os.path.join(OUTPUT_DIR, 'sims', '{}_ms'.format(slot_ms), '{}cm2'.format(area),
                                '{}_watts'.format(power), str(model))
        sim = ICETransientSim(stk_template, flp_template, power_trace, sim_config, run_path)
        sims.append(sim)

    if single_threaded:
        ICETransientSim.run(sims)
    else:
        ICETransientSim.run_with_parallels(sims)

    LOGGER.log_end()

if __name__ == '__main__':
    run_sims()
