#!/usr/bin/env python3
import click
import os
import subprocess
import json
import glob
from collections import defaultdict
from tqdm import tqdm
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = SCRIPT_DIR.parent
EXAMPLES_DIR = EXPERIMENT_DIR.parent
HOTGAUGE_ROOT = EXAMPLES_DIR.parent 

#sys.path.insert(0, str(Path(HOTGAUGE_ROOT) / "HotGauge"))
PLT_CMD = [sys.executable, "-m", "HotGauge.thermal.analysis", "local_max_stats"]
hg_env = os.environ.copy()
hg_pkg_root = str(Path(HOTGAUGE_ROOT) / "HotGauge")
hg_env["PYTHONPATH"] = (
    hg_pkg_root + (":" + hg_env["PYTHONPATH"] if "PYTHONPATH" in hg_env else "")
)


@click.command()
@click.option("--metadata-file-name", required=True, type=str,
        help="For example: metadata.json")
@click.option("--core-name", required=True, type=str,
        help="For example: core_0")

def main(metadata_file_name, core_name):

    path_to_metadata = EXPERIMENT_DIR / "Metadata" / metadata_file_name
    
    if not path_to_metadata.exists():
        raise click.ClickException(
            "Metadata file does not exist.\n"
            f"Requested metadata file: {metadata_file_name}\n"
            f"Looked for: {path_to_metadata}\n"
            f"Metadata directory: {EXPERIMENT_DIR / 'Metadata'}"
        )

    if not path_to_metadata.is_file():
        raise click.ClickException(
            "Metadata path exists but is not a file.\n"
            f"Path: {path_to_metadata}"
        )

    #load json info
    with path_to_metadata.open() as f:
        meta = json.load(f)
    
    #extract data needed to find 3d-ice output
    interval_ns = str(meta["interval_ns"])
    workload    = str(meta["workload"])
    freq        = str(meta["frequency"])
    tech_node   = str(meta["tech_node"])

    #construct sim_dir

    sim_dir = EXPERIMENT_DIR / "outputs" / "sims" / interval_ns / workload / tech_node / freq / core_name / "idle_00"

    print(f"Using SIM_DIR: {sim_dir}")
    print("Starting analysis...")

    os.chdir(sim_dir)

    cmd_2d = (
       
        PLT_CMD
        
        + [
            "die_grid.temps",
            "20",
            "-o", "die_grid.temps.2dmaxima",
            "-o", "die_grid.temps.2dmaxima.pkl",
            "-o", "die_grid.temps.2dmaxima.csv",
        ]
    )

    cmd_1d = (
        PLT_CMD
       
        + [
            "die_grid.temps",
            "20",
            "-o", "die_grid.temps.1dmaxima",
            "--in_either_dimension",
        ]
    )
    
    print("\nRunning 2D maxima command:")
    print("  " + " ".join(cmd_2d))
    subprocess.run(cmd_2d, check=True, env=hg_env)

    print("\nRunning 1D maxima command:")
    print("  " + " ".join(cmd_1d))
    subprocess.run(cmd_1d, check=True, env=hg_env)

    print("Analysis complete!")
    return 0


if __name__ == "__main__":
    main()


    
