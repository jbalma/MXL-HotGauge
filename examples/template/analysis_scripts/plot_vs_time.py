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
PLT_CMD = [sys.executable, "-m", "HotGauge.visualization.ICE_plt", "grid_transient"]
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
    
    if not sim_dir.exists():
    raise click.ClickException(
        "Simulation directory does not exist.\n"
        f"Looked for: {sim_dir}\n"
        "This usually means the thermal simulation has not been run yet, "
        "or one of interval_ns, workload, tech_node, frequency, or core_name "
        "does not match the output directory structure."
    )

    if not sim_dir.is_dir():
    raise click.ClickException(
        "Simulation path exists but is not a directory.\n"
        f"Path: {sim_dir}"
    )

    os.chdir(sim_dir)

    PLT_DIR = Path("plots")
    PLT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Using SIM_DIR: {sim_dir}")
    print("Building Plots...")

    
    temp_cmd1 = (
        PLT_CMD
        + [
            "die_grid.temps",
            "--plot_type", "stats",
            "--data_type", "temperature",
            "--min_val", "25",
            "--max_val", "135",
            "-t", "110",
            "--output", str(PLT_DIR / "temperature_stats.png"),
        ]
    )

    temp_cmd2 = (
        PLT_CMD
        + [
            "die_grid.temps",
            "--plot_type", "dist",
            "--data_type", "temperature",
            "--min_val", "25",
            "--max_val", "135",
            "-t", "110",
            "--output", str(PLT_DIR / "temperature_dist.png"),
        ]
    )

    pow_cmd1 = (
        PLT_CMD
        + [
            "die_grid.pows",
            "--plot_type", "stats",
            "--data_type", "power",
            "--output", str(PLT_DIR / "power_stats.png"),
        ]
    )

    pow_cmd2 = (
        PLT_CMD
        + [
            "die_grid.pows",
            "--plot_type", "dist",
            "--data_type", "power",
            "--output", str(PLT_DIR / "power_dist.png"),
        ]
    )


    print("\nCreating Temp Plots:")
    print("  " + " ".join(temp_cmd1))
    print("  " + " ".join(temp_cmd2))
    subprocess.run(temp_cmd1, check=True, env=hg_env)
    subprocess.run(temp_cmd2, check=True, env=hg_env)

    print("\nCreating Power Plots:")
    print("  " + " ".join(pow_cmd1))
    print("  " + " ".join(pow_cmd2))
    subprocess.run(pow_cmd1, check=True, env=hg_env)
    subprocess.run(pow_cmd2, check=True, env=hg_env)

    print("Analysis complete!")
    return 0


if __name__ == "__main__":
    main()


