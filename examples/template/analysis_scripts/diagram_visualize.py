#!/usr/bin/env python3
"""
diagram_visualize.py

End-to-end temperature visualization pipeline for HotGauge grid traces.

What this script does:
  1) Loads die_grid.temps from a simulation directory.
  2) Converts HotGauge-style IC.flp into a grid_thermal_map-friendly tabular floorplan.
  3) Renders one SVG per timestep with grid_thermal_map.py.
  4) Converts SVG frames to PNG.
  5) Builds temps.mp4 with ffmpeg.

This script preserves the original CLI style:
    python diagram_visualize.py --metadata-file-name metadata.json --core-name core_0

It also still supports pass-through arguments to grid_thermal_map.py via repeated --grid-args.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import shlex
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import click
from tqdm import tqdm

# --------------------------------------------------------------------------------------
# Repo / import setup
# --------------------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = SCRIPT_DIR.parent
EXAMPLES_DIR = EXPERIMENT_DIR.parent
HOTGAUGE_ROOT = EXAMPLES_DIR.parent

# Allow THIS Python process to import HotGauge modules.
HG_PKG_PARENT = HOTGAUGE_ROOT / "HotGauge"
sys.path.insert(0, str(HG_PKG_PARENT))

# Import HotGauge loader after sys.path is set.
from HotGauge.thermal.ICE import load_3DICE_grid_file  # type: ignore

# Allow the CHILD Python process (running grid_thermal_map.py) to import
# ThermalSideChannelAnalysisTools.
TSCA_PKG_PARENT = REPO_ROOT / "ThermalSideChannelAnalysisTools"

sub_env = os.environ.copy()
sub_env["PYTHONPATH"] = (
    str(HG_PKG_PARENT)
    + ":"
    + str(TSCA_PKG_PARENT)
    + (":" + sub_env["PYTHONPATH"] if "PYTHONPATH" in sub_env else "")
)

GRID_THERMAL_MAP_PY = (
    REPO_ROOT
    / "ThermalSideChannelAnalysisTools"
    / "ThermalSideChannelAnalysisTools"
    / "grid_thermal_map.py"
)

PYTHON = sys.executable


# --------------------------------------------------------------------------------------
# Small utility helpers
# --------------------------------------------------------------------------------------

def run_cmd(cmd: List[str], cwd: Path, env: Optional[dict] = None) -> None:
    """Run a subprocess command, print it, and fail fast if it errors."""
    print("[cwd]", str(cwd))
    print("[cmd]", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def svg_to_png(svg_path: Path) -> Path:
    """
    Convert one SVG -> PNG using ImageMagick.
    Keeps the same basename and writes next to the SVG.
    """
    png_path = svg_path.with_suffix(".png")
    subprocess.run(["/usr/bin/convert", str(svg_path), str(png_path)], check=True)
    return png_path


def write_gridthermal_input(
    frame_2d,
    out_path: Path,
    *,
    one_indexed: bool = False,
) -> None:
    """
    grid_thermal_map.py expects lines of the form:

        <grid_number> <grid_temperature>

    We generate indices in row-major order.

    one_indexed=False -> 0, 1, 2, ...
    one_indexed=True  -> 1, 2, 3, ...
    """
    nrows, ncols = frame_2d.shape
    base = 1 if one_indexed else 0

    with out_path.open("w") as f:
        idx = base
        for r in range(nrows):
            for c in range(ncols):
                f.write(f"{idx}	{float(frame_2d[r, c])}\n")
                idx += 1


# --------------------------------------------------------------------------------------
# Floorplan conversion
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class FlpBlock:
    """One floorplan block with lower-left position and dimensions."""
    name: str
    x: float
    y: float
    w: float
    h: float


_BLOCK_START_RE = re.compile(r"^\s*([A-Za-z0-9_.+\-]+)\s*:\s*$")
_POS_RE = re.compile(r"^\s*position\s+([0-9.+\-eE]+)\s*,\s*([0-9.+\-eE]+)\s*;\s*$")
_DIM_RE = re.compile(r"^\s*dimension\s+([0-9.+\-eE]+)\s*,\s*([0-9.+\-eE]+)\s*;\s*$")


def parse_hotgauge_flp(text: str) -> List[FlpBlock]:
    """
    Parse the HotGauge floorplan format:

        NAME :
            position x, y ;
            dimension w, h ;
            power values ...

    Only geometry is kept. Power values are ignored.
    """
    blocks: List[FlpBlock] = []
    cur_name: Optional[str] = None
    cur_x: Optional[float] = None
    cur_y: Optional[float] = None
    cur_w: Optional[float] = None
    cur_h: Optional[float] = None

    for line in text.splitlines():
        m = _BLOCK_START_RE.match(line)
        if m:
            # Commit the previous block if complete.
            if (
                cur_name is not None
                and cur_x is not None
                and cur_y is not None
                and cur_w is not None
                and cur_h is not None
            ):
                blocks.append(FlpBlock(cur_name, cur_x, cur_y, cur_w, cur_h))

            # Start a new block.
            cur_name = m.group(1)
            cur_x = cur_y = cur_w = cur_h = None
            continue

        if cur_name is None:
            continue

        m = _POS_RE.match(line)
        if m:
            cur_x = float(m.group(1))
            cur_y = float(m.group(2))
            continue

        m = _DIM_RE.match(line)
        if m:
            cur_w = float(m.group(1))
            cur_h = float(m.group(2))
            continue

    # Commit the final block.
    if (
        cur_name is not None
        and cur_x is not None
        and cur_y is not None
        and cur_w is not None
        and cur_h is not None
    ):
        blocks.append(FlpBlock(cur_name, cur_x, cur_y, cur_w, cur_h))

    if not blocks:
        raise ValueError("No valid floorplan blocks were found in IC.flp")

    return blocks


def write_grid_flp(blocks: List[FlpBlock], out_path: Path) -> None:
    """
    Write a grid_thermal_map-friendly tabular floorplan:

        <name>  <width> <height> <x> <y>
    """
    with out_path.open("w") as f:
        for b in blocks:
            f.write(f"{b.name}	{b.w:.6f}	{b.h:.6f}	{b.x:.6f}	{b.y:.6f}\n")


def convert_hotgauge_flp_to_grid_flp(in_path: Path, out_path: Path) -> None:
    """
    Convert HotGauge IC.flp to a tabular IC.grid.flp.

    This does not overwrite the original floorplan.
    """
    txt = in_path.read_text()
    blocks = parse_hotgauge_flp(txt)
    write_grid_flp(blocks, out_path)


# --------------------------------------------------------------------------------------
# Core pipeline
# --------------------------------------------------------------------------------------

def mk_temp_viz(
    sim_dir: Path,
    *,
    num_threads: int,
    celsius: bool,
    one_indexed: bool,
    rows: Optional[int],
    cols: Optional[int],
    extra_grid_args: List[str],
    auto_convert_flp: bool,
) -> None:
    """
    Temps-only pipeline in one sim_dir:

      1) parse die_grid.temps using load_3DICE_grid_file()
      2) auto-convert IC.flp -> IC.grid.flp (if requested)
      3) per timestep: write grid_thermal_map input -> render SVG
      4) convert SVG -> PNG
      5) ffmpeg to temps.mp4

    IMPORTANT:
      - All outputs are written under sim_dir / "viz"
    """
    if not GRID_THERMAL_MAP_PY.exists():
        raise FileNotFoundError(f"grid_thermal_map.py not found at: {GRID_THERMAL_MAP_PY}")

    die_grid = sim_dir / "die_grid.temps"
    flp_file = sim_dir / "IC.flp"

    if not die_grid.exists():
        raise FileNotFoundError(f"Missing required input: {die_grid}")
    if not flp_file.exists():
        raise FileNotFoundError(f"Missing required input: {flp_file}")

    # Choose which floorplan file to hand to grid_thermal_map.py.
    # By default we use the original IC.flp, but if auto-convert is on we generate
    # IC.grid.flp and use that instead.
    flp_for_render = flp_file
    if auto_convert_flp:
        converted_flp = sim_dir / "IC.grid.flp"
        print(f"Converting {flp_file.name} -> {converted_flp.name} ...")
        convert_hotgauge_flp_to_grid_flp(flp_file, converted_flp)
        flp_for_render = converted_flp

    viz_dir = sim_dir / "viz"
    viz_dir.mkdir(parents=True, exist_ok=True)

    tmp_frames_dir = viz_dir / "tmp_frames"
    tmp_frames_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1) Load the grid trace exactly once
    # ------------------------------------------------------------------
    print("Loading die_grid.temps using HotGauge.thermal.ICE.load_3DICE_grid_file ...")
    ttrace = load_3DICE_grid_file(str(die_grid), convert_K_to_C=celsius)

    # Defensive: if the loader ever returns 2D, promote it to T=1.
    if ttrace.ndim == 2:
        ttrace = ttrace[None, :, :]

    T, H, W = ttrace.shape
    print(f"Parsed grid trace shape: T={T}, rows(H)={H}, cols(W)={W}")

    # Validate user-supplied rows/cols if present.
    if rows is not None and rows != H:
        raise ValueError(f"--rows={rows} does not match parsed grid rows={H}")
    if cols is not None and cols != W:
        raise ValueError(f"--cols={cols} does not match parsed grid cols={W}")

    # Use the parsed grid dimensions so the renderer interprets indices correctly.
    rows = H
    cols = W

    # ------------------------------------------------------------------
    # 2) Render one SVG per timestep
    # ------------------------------------------------------------------
    print("Writing per-timestep frame files + rendering SVGs with grid_thermal_map.py ...")

    def render_step(step: int) -> Path:
        """
        Render one timestep:
          - write tmp frame .t file (index temp)
          - run grid_thermal_map.py -> temps_{step}.svg
        """
        frame_path = tmp_frames_dir / f"frame_{step:05d}.t"
        out_svg = viz_dir / f"temps_{step:05d}.svg"

        # Convert the 2D grid into the "idx temp" text format expected by grid_thermal_map.py.
        write_gridthermal_input(ttrace[step], frame_path, one_indexed=one_indexed)

        # Command line expected by grid_thermal_map.py:
        #   grid_thermal_map.py flp_file input_file output_file --input_type grid ...
        cmd = [
            PYTHON,
            str(GRID_THERMAL_MAP_PY),
            str(flp_for_render),
            str(frame_path),
            str(out_svg),
            "--input_type",
            "grid",
            "--rows",
            str(rows),
            "--cols",
            str(cols),
        ]

        # Append any caller-provided pass-through args (min/max/font/etc).
        cmd += extra_grid_args

        run_cmd(cmd, cwd=sim_dir, env=sub_env)
        return out_svg

    rendered_svgs: List[Path] = []
    with ThreadPoolExecutor(max_workers=num_threads) as ex:
        futures = [ex.submit(render_step, step) for step in range(T)]
        for fut in tqdm(as_completed(futures), total=len(futures), desc="render SVG"):
            rendered_svgs.append(fut.result())

    rendered_svgs = sorted(rendered_svgs)

    # ------------------------------------------------------------------
    # 3) Convert SVG -> PNG
    # ------------------------------------------------------------------
    print("Converting SVG frames to PNG frames ...")
    with ThreadPoolExecutor(max_workers=num_threads) as ex:
        futures = [ex.submit(svg_to_png, svg) for svg in rendered_svgs]
        for _ in tqdm(as_completed(futures), total=len(futures), desc="convert PNG"):
            pass

    # ------------------------------------------------------------------
    # 4) Assemble video with ffmpeg
    # ------------------------------------------------------------------
    ffmpeg_threads = min(num_threads, 16)

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(viz_dir / "temps_%05d.png"),
        "-threads",
        str(ffmpeg_threads),
        str(viz_dir / "temps.mp4"),
    ]

    print("Creating temps.mp4 with ffmpeg ...")
    run_cmd(ffmpeg_cmd, cwd=sim_dir)


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--metadata-file-name", required=True, type=str, help="For example: metadata.json")
@click.option("--core-name", required=True, type=str, help="For example: core_0")
@click.option(
    "--num-threads",
    type=int,
    default=32,
    show_default=True,
    help="Parallelism for rendering/conversion. ffmpeg threads are capped at 16.",
)
@click.option(
    "--celsius/--kelvin",
    default=True,
    show_default=True,
    help=(
        "Whether to convert die_grid.temps from K->C when loading. "
        "Default is --celsius."
    ),
)
@click.option(
    "--one-indexed/--zero-indexed",
    default=False,
    show_default=True,
    help=(
        "Indexing for grid_thermal_map input files. Default is 0-indexed. "
        "Flip to --one-indexed if your heatmap looks scrambled."
    ),
)
@click.option(
    "--grid-args",
    multiple=True,
    help=(
        "Pass-through args to grid_thermal_map.py. "
        "Use multiple times, e.g. --grid-args --min_t --grid-args 300"
    ),
)
@click.option(
    "--auto-convert-flp/--no-auto-convert-flp",
    default=True,
    show_default=True,
    help="Automatically convert HotGauge IC.flp into IC.grid.flp and render with the converted file.",
)
def main(
    metadata_file_name: str,
    core_name: str,
    num_threads: int,
    celsius: bool,
    one_indexed: bool,
    grid_args: List[str],
    auto_convert_flp: bool,
) -> int:
    CWD = Path.cwd()
    BASE = CWD.parent  

    path_to_metadata = BASE / "Metadata" / metadata_file_name
    if not path_to_metadata.exists():
        print(f"ERROR: metadata file not found: {path_to_metadata}", file=sys.stderr)
        return 2

    with path_to_metadata.open() as f:
        meta = json.load(f)

    interval_ns = str(meta["interval_ns"])
    workload = str(meta["workload"])
    freq = str(meta["frequency"])
    tech_node = str(meta["tech_node"])

    sim_dir = BASE / "outputs" / "sims" / interval_ns / workload / tech_node / freq / core_name / "idle_00"

    print(f"Using SIM_DIR: {sim_dir}")
    print("Starting temperature visualization (load_3DICE_grid_file -> grid_thermal_map.py) ...")

    if not sim_dir.exists():
        print(f"ERROR: sim_dir not found: {sim_dir}", file=sys.stderr)
        return 2
    
    extra_grid_args = []
    for arg in grid_args:
        extra_grid_args.extend(shlex.split(arg))

    try:
        mk_temp_viz(
            sim_dir=sim_dir,
            num_threads=num_threads,
            celsius=celsius,
            one_indexed=one_indexed,
            rows=None,
            cols=None,
            extra_grid_args=extra_grid_args,
            auto_convert_flp=auto_convert_flp,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print("Analysis complete!")
    print("Outputs written to: {sim_dir / 'viz'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
