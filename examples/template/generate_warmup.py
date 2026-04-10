#!/usr/bin/env python3
import click
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


# Insert HotGauge/HotGauge
sys.path.insert(
    0,
    str(HOTGAUGE_REPO_DIR / "HotGauge")
)

#from HotGauge.power.traces import JSONFilesPowerTrace, JSONFilePowerTrace
from HotGauge.thermal.ICE import get_stack_template
from HotGauge.thermal.ICE import parse_file_name_from_output_line
from HotGauge.thermal.thermal import make_transient_warmups


HEATSINK_MODEL = 'HS483'
HEATSINK_ARGS = '6000'
CWD = os.getcwd()
FLP_BASE_DIR = os.path.join(CWD, "floorplans", "outputs")

@click.command()
@click.option("--warmup-dir", required=True, type=click.Path(file_okay=False),
              help="Directory to write warmup outputs into (will be created if missing).")
@click.option("--flp-template", required=True, type=str,
              help="The name of the .flp template you wish to use e.g skylake7nm_core_3_3D-ICE_template.flp")

def main(warmup_dir, flp_template):
    
    flp_templates = glob.glob(os.path.join(FLP_BASE_DIR, flp_template))

    stack_template = get_stack_template('skylake_{}'.format(HEATSINK_MODEL))
    
    tdata_info = make_transient_warmups(warmup_dir, flp_templates, stack_template, HEATSINK_ARGS)
    
    print("tdata_info: ", tdata_info)
    print("Warmup map entries:", len(tdata_info))
    for (flp, label), f in tdata_info.items():
        print(" ", label, "->", f, "exists:", os.path.exists(f))

    print("Warmup complete.")
    print("Warmup run directory:", warmup_sim.run_path)


if __name__ == "__main__":
    main()


