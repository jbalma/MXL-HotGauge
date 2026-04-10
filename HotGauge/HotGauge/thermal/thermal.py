import os
import itertools

import numpy as np

from HotGauge.power import JSONFilesPowerTrace
from HotGauge.thermal import ICETransientSim, ICESimConfig
from HotGauge.thermal.ICE import parse_file_name_from_output_line
from HotGauge.script_runner import ExecutableJob

from .floorplan import get_flp_info
from .workloads import block_powers_trace_to_DICE
from .config import LOGGER

EFFECTIVE_AMBIENT = 298.15 + 5

WARMUP_STEP = 0.001 # This time step seems to not result in overflow
WARMUP_NUM_STEPS = 100 # So that we can monitor progress
WARMUP_TOTAL_TIME_S = 5*60 # A few minutes
WARMUP_SLOT = WARMUP_TOTAL_TIME_S / WARMUP_NUM_STEPS
WARMUP_STEPS_PER_SLOT = int(WARMUP_SLOT / WARMUP_STEP)

HOTGAUGE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)

def make_transient_warmups(warmup_dir, flp_templates, stack_template, args):
    idle_ptrace = os.path.join(
      HOTGAUGE_ROOT,
      "HotGauge",
      "examples",
      "{}nm_idle_power_trace.json"
    )
    warmups = [('idle_00', idle_ptrace)]
    print("here1")
    output_list = [ICETransientSim.OUTPUT_TSTACK_FINAL, ICETransientSim.DIE_TFLP_OUTPUT]
    thermal_state_file = parse_file_name_from_output_line(output_list[0])
    print("here2")
    warmup_sims = []
    tdata_files = {}
    print("here3")
    for flp_template, (warmup_label, warmup_ptrace) in itertools.product(flp_templates, warmups):
        flp_info = get_flp_info(flp_template)
        print("here4")
        pdata_file = warmup_ptrace.format(flp_info['node'])
        try:
            pdata_trace = JSONFilesPowerTrace([pdata_file], WARMUP_SLOT)
            warmup_trace = block_powers_trace_to_DICE(pdata_trace ** WARMUP_NUM_STEPS, flp_template, flp_info['node'])
        except FileNotFoundError as e:
            msg = '{} warmup for {}nm does not exist for {} at {}'
            LOGGER.warn(msg.format(warmup_label, flp_info['node'], flp_template, pdata_file))
            continue
        print("here5")
        DELTA_T_STK = {7: 14, 14: 3}
        DELTA_T_SINK = {7: 5, 14: 2}
        initial_temps = (EFFECTIVE_AMBIENT + DELTA_T_STK[flp_info['node']], EFFECTIVE_AMBIENT + DELTA_T_SINK[flp_info['node']])
        print("here6")
        stack_info = os.path.splitext(os.path.basename(stack_template))[0]
        print("here7")
        flp_str = os.path.basename(flp_template)
        print("here8")
        sim_dir = os.path.join(warmup_dir, 'warmups', stack_info, warmup_label, flp_str)
        print("here9")
        sim_config = ICESimConfig(initial_temp=initial_temps, plugin_args=args,
                                  output_list=output_list)
        print("here10")
        sim = ICETransientSim(stack_template, flp_template, warmup_trace, sim_config, sim_dir,
                              steps_per_slot=WARMUP_STEPS_PER_SLOT)

        print("here10")
        #sim.prep_for_run()
        warmup_sims.append(sim)
        print("here11")
        tdata_files[(flp_template, warmup_label)] = os.path.join(sim_dir, thermal_state_file)
        print("here12")
    #assert False, ""
    ICETransientSim.run_with_parallels(warmup_sims)

    def get_hsink_temp(tstack_file):
        t1 = get_avg_final_temp(tstack_file)
        t0 = 300
        return t0 + (t1-t0)*0.5
    tdata_info = {k: (t, get_hsink_temp(t)) for k,t in tdata_files.items()}

    for flp_template in flp_templates:
        tdata_info[(flp_template, 'cold_00')] = (EFFECTIVE_AMBIENT)
    return tdata_info

def get_avg_final_temp(tsck_file):
    print("tsck_file: ", tsck_file)
    with open(tsck_file, 'r') as f:
        last_line = None
        for line in f:
            final_data_line = last_line
            last_line = line
    print("last line is: ", last_line)
    assert last_line == '\n' 
    data = np.array(final_data_line.split(), dtype=float)
    return round(data.mean(), 2)

def run_thermal_sims_with_node_dict(thermal_sims_dict):
    try:
        from psutil import virtual_memory
        mem = virtual_memory()
        TOTAL_RAM = mem.total  # total physical memory available
    except:
        TOTAL_RAM = 256e9 # 256 Gb
        LOGGER.warn('Using hard coded RAM estimate: {}'.format(TOTAL_RAM))

    ICETransientSim.CHECK_CORES_PERCENT = 0.15
    RAM_PER_SIM = {'14nm': 2.6e9, '10nm': 1.5e9, '7nm': 1.0e9}
    for node, node_sims in sorted(thermal_sims_dict.items(), key=lambda s: int(s[0][:-2])):
        num_threads = int(0.75 * TOTAL_RAM / RAM_PER_SIM[node]) # Use 75% of total RAM
        # Base numbe of sims on total ram or percent of CPU threads
        ICETransientSim.parallel_options["-j"] = min(num_threads, ExecutableJob.parallel_options["-j"])
        LOGGER.info('Running thermal sims for {}'.format(node))
        ICETransientSim.run_with_parallels(node_sims)

