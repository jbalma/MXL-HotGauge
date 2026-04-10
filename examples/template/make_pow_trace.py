#!/usr/bin/env python3
import click
import json
import os
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

#path to hotspot-mitigation repo
sys.path.insert(
    0,
    str(HOTGAUGE_PARENT / "hotspot-mitigation" / "experiments")
)

# Insert HotGauge/HotGauge
sys.path.insert(
    0,
    str(HOTGAUGE_REPO_DIR / "HotGauge")
)

from HotGauge.configuration import load_block_powers
from HotGauge.power.traces import JSONFilesPowerTrace, JSONFilePowerTrace

BASE = os.getcwd()
CWD = os.getcwd()

def fill_metadata_JSON(sniper_output_dir, instruction_count, interval_ns, suite, prepped_meta_path):
    
    #split sniper output filename into parts
    sniper_output_dir = os.path.expanduser(sniper_output_dir)
    norm_path = os.path.normpath(sniper_output_dir)
    parts = norm_path.split(os.sep)

    try:
        frequency = parts[-1]          # e.g. "3.0GHz"
        tech_node = parts[-2]          # e.g. "7nm"
        workload = parts[-3]           # e.g. "libquantum"
    except IndexError:
        raise ValueError(
            f"Unexpected sniper_output_dir layout: {sniper_output_dir}"
        )

    metadata = {
        "region": "start",                         # always "start"
        "instruction_count": int(instruction_count),
        "interval_ns": int(interval_ns),
        "suite": suite,                            # e.g. "spec-2006"
        "workload": workload,                      # from {your test name}
        "tech_node": tech_node,                    # e.g. "7nm"
        "frequency": frequency                     # e.g. "3.0GHz"
    }

    os.makedirs(os.path.dirname(prepped_meta_path), exist_ok=True)
    with open(prepped_meta_path, "w") as f:
        json.dump(metadata, f, indent=2)



@click.command()
@click.option("--sniper-output-dir", required=True, type=click.Path(file_okay=False, exists=True),
        help="Sniper/McPAT output directory. Must be in form:  ~/HotGauge/snipersim/output/{your test name}/{}nm/{frequency}")
@click.option("--prefix-for-files", required=True, type=str, help="this will go in the brackets: {}_metadata.json, {}_pow_trace.json")
@click.option("--instruction-count", required=True, type=int,
        help="The instruction count you used for your sniper simulation")
@click.option("--interval-ns", required=True, type=int,
        help="The number you wrote for energystats: in your sniper simulation")
@click.option("--suite", required=False, default="my_suite", type=str,
        help="For example: spec-2006")

def main(sniper_output_dir, prefix_for_files, instruction_count, interval_ns, suite):

    
    #create trace directory if it doesn't already exist
    trace_dir = os.path.join(BASE, 'Traces')
    os.makedirs(trace_dir, exist_ok=True)
   
    POW_TRACE_NAME = prefix_for_files + "_pow_trace.json"
    META_TRACE_NAME = prefix_for_files + "_metadata.json"

    #create filepath to the power trace file
    prepped_trace_path = os.path.join(BASE, 'Traces', POW_TRACE_NAME)
    
    #create filepath to metadata file
    prepped_meta_path = os.path.join(BASE, 'Metadata', META_TRACE_NAME)

    #create metadata file
    fill_metadata_JSON(
        sniper_output_dir=sniper_output_dir,
        instruction_count=instruction_count,
        interval_ns=interval_ns,
        suite=suite,
        prepped_meta_path=prepped_meta_path,
    )

    #create power trace file
    block_powers = load_block_powers(sniper_output_dir)
    wl_trace = JSONFilesPowerTrace(block_powers, float(interval_ns))

    powers = {unit: list(series) for unit, series in wl_trace.powers.items()}

    with open(prepped_trace_path, "w") as f:
        json.dump(powers, f, indent=2)


if __name__ == "__main__":
    main()




