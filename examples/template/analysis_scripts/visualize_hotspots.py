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

CWD = Path.cwd()

# ~/HotGauge/examples/{your test directory}
BASE = CWD.parent
BASE2 = BASE.parent

#HOTGAUGE_ROOT = BASE2.parent
HOTGAUGE_ROOT = "/data/jake_m/HotGauge"

#sys.path.insert(0, str(Path(HOTGAUGE_ROOT) / "HotGauge"))
PLT_CMD = [sys.executable, "-m", "HotGauge.visualization.ICE_plt", "hotspot_locations"]
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

    path_to_metadata = BASE / "Metadata" / metadata_file_name

    #load json info
    with path_to_metadata.open() as f:
        meta = json.load(f)

    #extract data needed to find 3d-ice output
    interval_ns = str(meta["interval_ns"])
    workload    = str(meta["workload"])
    freq        = str(meta["frequency"])
    tech_node   = str(meta["tech_node"])

    #construct sim_dir

    sim_dir = BASE / "outputs" / "sims" / interval_ns / workload / tech_node / freq / core_name / "idle_00"

    print(f"Using SIM_DIR: {sim_dir}")
    print("Starting analysis...")

    os.chdir(sim_dir)

    PLT_DIR = Path("plots")
    PLT_DIR.mkdir(parents=True, exist_ok=True)

    vid_cmd1 = (
        PLT_CMD
        + [
            "die_grid.temps",
            "IC.flp",
            "--severity_threshold", "0.75",
            "--mltd_radius", "1.0",
            "-o", str(PLT_DIR / "ttrace_{step:04}.png"),
            "-l", "die_grid.temps.2dmaxima",
        ]
    )

    print("\nMaking PNGs for video using this command:")
    print("  " + " ".join(vid_cmd1))
    subprocess.run(vid_cmd1, check=True, env=hg_env)

    print("Analysis complete!")
    return 0


if __name__ == "__main__":
    main()
