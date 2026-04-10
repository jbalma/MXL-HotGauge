#!/usr/bin/env python3
import click
import os
import json
import glob
from collections import defaultdict
from tqdm import tqdm
import sys
from pathlib import Path

# Directory of THIS script
THIS_FILE = Path(__file__).resolve()

# .../HotGauge/examples/template
TEMPLATE_DIR = THIS_FILE.parent

# .../HotGauge/examples
EXAMPLES_DIR = TEMPLATE_DIR.parent

# .../HotGauge
HOTGAUGE_REPO_DIR = EXAMPLES_DIR.parent

# .../{hotgauge parent}
HOTGAUGE_PARENT = HOTGAUGE_REPO_DIR.parent

# Insert HotGauge/HotGauge
sys.path.insert(
    0,
    str(HOTGAUGE_REPO_DIR / "HotGauge")
)

#from HotGauge.power.traces import JSONFilesPowerTrace, JSONFilePowerTrace
from HotGauge.power.traces import JSONFilesPowerTrace, JSONFilePowerTrace
from HotGauge.thermal.ICE import get_stack_template, ICETransientSim, ICESimConfig
from HotGauge.thermal.ICE import parse_file_name_from_output_line

from HotGauge.thermal.workloads import cached_traces_for_workload_set, block_powers_trace_to_DICE
from HotGauge.thermal.thermal import make_transient_warmups, run_thermal_sims_with_node_dict
from HotGauge.thermal.floorplan import get_flp_info

BASE = os.getcwd()
FLP_BASE_DIR = os.path.join(BASE, "floorplans", "outputs")
OUTPUT_DIR = os.path.join(BASE, "outputs")

HEATSINK_MODEL = 'HS483'
HEATSINK_ARGS = '6000'

def parse_core_mapping(value: str) -> dict[int, int]:
    #Accepts either:
     # '0->2,6'  => {2:0, 6:0}
     # '0,2,6'   => {0:0, 2:2, 6:6}
    s = value.strip()

    def parse_int_list(part: str) -> list[int]:
        items = [p.strip() for p in part.split(",") if p.strip()]
        if not items:
            raise click.BadParameter(f"Invalid '{value}': empty core list.")
        try:
            out = [int(x) for x in items]
        except ValueError:
            raise click.BadParameter(
                f"Invalid '{value}': core lists must be comma-separated integers."
            )
        for c in out:
            if c < 0:
                raise click.BadParameter(f"Invalid '{value}': cores must be >= 0.")
        return out

    if "->" in s:
        left, right = s.split("->", 1)
        left = left.strip()
        right = right.strip()

        # source
        try:
            source = int(left)
        except ValueError:
            raise click.BadParameter(
                f"Invalid '{value}': left side of '->' must be an int source core (e.g. 0->2,6)."
            )
        if source < 0:
            raise click.BadParameter(f"Invalid '{value}': source core must be >= 0.")

        targets = parse_int_list(right)

        # Map each target to the single source
        return {t: source for t in dict.fromkeys(targets)}  # dedupe, preserve order

    # Identity mapping: treat list as active targets, sourced from themselves
    cores = parse_int_list(s)
    cores = list(dict.fromkeys(cores))  # dedupe
    return {c: c for c in cores}


def load_workloads(trace_file, metadata_file, workload_manifest):
    
    #Returns a list of dicts: [{"trace": "/abs/path/to/trace", "meta": "/abs/path/to/meta"}, ...]
    #Enforces either (trace_file & metadata_file) OR workload_manifest.
    
    single_mode = (trace_file is not None) or (metadata_file is not None)
    manifest_mode = workload_manifest is not None

    if manifest_mode and single_mode:
        raise click.UsageError(
            "Use either --workload-manifest OR (--trace-file AND --metadata-file), not both."
        )

    if manifest_mode:
        manifest_path = Path(workload_manifest).expanduser().resolve()
        base_dir = manifest_path.parent
        try:
            data = json.loads(manifest_path.read_text())
        except Exception as e:
            raise click.ClickException(f"Failed to read manifest JSON: {manifest_path}\n{e}")

        if not isinstance(data, list) or not data:
            raise click.UsageError("--workload-manifest must be a JSON list of objects.")

        workloads = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise click.UsageError(f"Manifest entry {i} is not an object.")

            if "trace" not in item or "meta" not in item:
                raise click.UsageError(f"Manifest entry {i} must include keys 'trace' and 'meta'.")

            trace = str(Path(item["trace"]).expanduser()).resolve()
            meta = str(Path(item["meta"]).expanduser()).resolve()
            workloads.append({"trace": trace, "meta": meta})

        return workloads

    # single pair mode
    if (trace_file is None) != (metadata_file is None):
        raise click.UsageError("If using single-file mode, you must provide BOTH --trace-file and --metadata-file.")

    if trace_file is None and metadata_file is None:
        raise click.UsageError("Provide either --workload-manifest OR (--trace-file AND --metadata-file).")

    return [{"trace": trace_file, "meta": metadata_file}]


@click.command()
@click.option("--tstack-path", required=True, type=click.Path(file_okay=True),
              help="Path to tstack file")
@click.option("--flp-template", required=True, type=str,
        help="For example: skylake7nm_7core_3_3D-ICE_template.flp")
@click.option("--trace-file", type=click.Path(exists=True, dir_okay=False),
              help="Path to one trace file (single-workload mode).")
@click.option("--metadata-file", type=click.Path(exists=True, dir_okay=False),
              help="Path to one metadata JSON file (single-workload mode).")
@click.option("--workload-manifest", type=click.Path(exists=True, dir_okay=False),
              help="Path to a JSON manifest listing multiple workloads.")
@click.option(
    "--core-mapping",
    required=False,
    type=str,
    default=None,
    show_default=False,
    help=(
        "Either identity active cores '0,2,6' (maps each to itself) "
        "or a single-source mapping '0->2,6' (maps source core 0 to targets 2 and 6)."
    ),
)

def main(tstack_path, flp_template, trace_file, metadata_file, workload_manifest, core_mapping):
    
    workloads = load_workloads(trace_file, metadata_file, workload_manifest)
   
    raw_workload_traces = {}
    for w in workloads:
        trace_path = w["trace"]
        meta_path  = w["meta"]

        with open(meta_path, "r") as f:
            wl_meta = json.load(f)

        raw_workload_traces[trace_path] = wl_meta

    flp_templates = glob.glob(os.path.join(FLP_BASE_DIR, flp_template))
    warmup_labels = ["idle_00"]

    #this is also a dictionary
    #key is (flp_template_path, warmup_label)
    #value is the filepath to the .tstack warmup
    tdata_info = {
        (flp_templates[0], warmup_labels[0]): tstack_path
    }

    stack_template = get_stack_template('skylake_{}'.format(HEATSINK_MODEL))
    
    #this will be the collection of simulations to be run
    thermal_sims = defaultdict(list)

    core_sources = parse_core_mapping(core_mapping) if core_mapping else {0: 0}
    
    target_cores = tuple(sorted(core_sources.keys()))
    cores_list_str = "_".join(map(str, target_cores))
    cores_str = f"core_{cores_list_str}" if len(target_cores) == 1 else f"cores_{cores_list_str}"

    
    
    #this outer loop cycles through each power_trace and metadata combo
    for wl_trace_file, wl_meta in tqdm(raw_workload_traces.items()):
        #reads json
        wl_trace = JSONFilePowerTrace(wl_trace_file, wl_meta['interval_ns'] * 1e-9)
        
        #this middle loop iterates through flp_templates and warmup data
        for (flp_template, warmup_label), initial_temp in tdata_info.items():
            
            flp_info = get_flp_info(flp_template)
                
            #we are making sure flp template matches sim metadata
            if wl_meta['tech_node'] != flp_info['node_nm']:
                continue

            output_list = [ICETransientSim.DIE_TMAP_OUTPUT, ICETransientSim.DIE_TFLP_OUTPUT]
            sim_config = ICESimConfig(initial_temp=initial_temp, plugin_args=HEATSINK_ARGS,
                                  output_list=output_list)
            
            sim_info = wl_meta.copy()
            sim_info.update({'cores_str' : cores_str, 'warmup' : warmup_label})
            sim_dir = os.path.join(OUTPUT_DIR, 'sims', *sim_info_to_sim_dir(sim_info))

            sim_trace = block_powers_trace_to_DICE(wl_trace, flp_template, wl_meta['tech_node'],
                                          core_sources=core_sources)
            sim = ICETransientSim(stack_template, flp_template, sim_trace, sim_config, sim_dir)
            thermal_sims[wl_meta['tech_node']].append(sim)

            
        run_thermal_sims_with_node_dict(thermal_sims)

        print("Simulation Finished!")


def tech_node(node_str):
    return int(node_str.strip('nm'))

def frequncy(freq_str):
    return float(freq_str.strip('GHz'))

#def core_nums(core_str):
#    return core_str.strip('core_').strip('cores_').split('_')

SIM_DIR_STRUCTURE = [('interval_ns', float), ('workload', str), ('tech_node', tech_node),
                     ('frequency', frequncy), ('cores_str', str), ('warmup', str)]

############### Generate the file naming scheme ######################
def sim_info_to_sim_dir(sim_info):
    return [str(sim_info[key]) for key,_ in SIM_DIR_STRUCTURE]

def sim_dir_to_sim_info(sim_dir):
    num_meta = len(SIM_DIR_STRUCTURE)
    fields = sim_dir.split('/')[-num_meta:]
    sim_info = {name: fn(field) for (name, fn), field in zip(SIM_DIR_STRUCTURE, fields)}
    sim_info['tech_node_nm'] = '{}nm'.format(sim_info['tech_node'])
    sim_info['frequency_GHz'] = '{}GHz'.format(sim_info['frequency'])
    sim_info['cores'] = sim_info['cores_str'].strip('core_').strip('cores_')
    return sim_info


if __name__ == '__main__':
    main()



