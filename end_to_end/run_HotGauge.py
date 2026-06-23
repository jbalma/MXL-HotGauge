#!/usr/bin/env python3
"""
run_HotGauge.py

End-to-end runner for HotGauge:
  Sniper -> McPAT -> trace generation -> 3D-ICE sim 

Designed to be run from:
  HOTGAUGE_ROOT/end_to_end

Usage:
  python run_HotGauge.py --config end_to_end.yaml

"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

try:
    import yaml  # type: ignore
except ImportError:
    print("ERROR: Missing dependency 'pyyaml'. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# -------------------------
# Logging helpers
# -------------------------

def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def stage(title: str) -> None:
    bar = "=" * 80
    print("\n" + bar, flush=True)
    print(f"[{_ts()}] STAGE: {title}", flush=True)
    print(bar, flush=True)


def run_cmd(cmd: List[str], cwd: Path | None = None, env: Dict[str, str] | None = None) -> None:
    cwd_str = str(cwd) if cwd else os.getcwd()
    log(f"Running command (cwd={cwd_str}):")
    log("  " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=True)
    log("Command completed successfully.")


# -------------------------
# Config loading + interpolation
# -------------------------

_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def deep_get(d: Dict[str, Any], dotted: str) -> Any:
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(f"Unknown interpolation key: {dotted} (missing '{part}')")
        cur = cur[part]
    return cur


def interpolate_str(s: str, cfg: Dict[str, Any], max_passes: int = 10) -> str:
    out = s
    for _ in range(max_passes):
        m = _VAR_RE.search(out)
        if not m:
            return out

        def repl(match: re.Match) -> str:
            key = match.group(1).strip()
            val = deep_get(cfg, key)
            if isinstance(val, (dict, list)):
                raise ValueError(f"Interpolation key '{key}' resolved to non-scalar type.")
            return str(val)

        out = _VAR_RE.sub(repl, out)

    raise ValueError(f"Interpolation did not converge for string: {s}")


def interpolate_all(obj: Any, cfg: Dict[str, Any]) -> Any:
    if isinstance(obj, str):
        return interpolate_str(obj, cfg)
    if isinstance(obj, list):
        return [interpolate_all(x, cfg) for x in obj]
    if isinstance(obj, dict):
        return {k: interpolate_all(v, cfg) for k, v in obj.items()}
    return obj


def load_config(path: Path) -> Dict[str, Any]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("Config root must be a mapping/dict.")

    # Inject runtime variables usable by interpolation, e.g. ${cwd}
    raw["cwd"] = str(Path.cwd().resolve())

    cfg: Any = raw
    for _ in range(5):
        cfg = interpolate_all(cfg, cfg)

    if not isinstance(cfg, dict):
        raise ValueError("Interpolated config root must be a dict.")

    # ------------------------------------------------------------------
    # Derive fields from user_edit section so the rest of the script can
    # keep using the old internal config structure.
    # ------------------------------------------------------------------
    user_edit = cfg.get("user_edit", {})
    if not isinstance(user_edit, dict):
                raise ValueError("user_edit must be a mapping/dict.")
    
    core_mapping = user_edit.get("core_mapping")

    if core_mapping is not None:
        if not isinstance(core_mapping, dict):
            raise ValueError("user_edit.core_mapping must be a mapping/dict.")

        mode = core_mapping.get("mode")
        mapping = core_mapping.get("map")

        if mode is None:
            raise ValueError("user_edit.core_mapping.mode must be set.")
        if mapping is None:
            raise ValueError("user_edit.core_mapping.map must be set.")
        if not isinstance(mapping, dict):
            raise ValueError("user_edit.core_mapping.map must be a mapping/dict.")

        cfg.setdefault("ice", {})
        cfg["ice"].setdefault("core_mapping", {})
        cfg["ice"]["core_mapping"]["mode"] = str(mode)
        cfg["ice"]["core_mapping"]["map"] = mapping
    
    # Build sniper.executables from executable_root + executable_names + shared args
    exe_root = user_edit.get("executable_root")
    exe_names = user_edit.get("executable_names", [])
    exe_args = user_edit.get("executable_args", [])
    
    if exe_root is not None:
        if not isinstance(exe_names, list) or len(exe_names) == 0:
            raise ValueError("user_edit.executable_names must be a non-empty list.")
        if exe_args is None:
            exe_args = []
        if not isinstance(exe_args, list):
            raise ValueError("user_edit.executable_args must be a list.")

        cfg.setdefault("sniper", {})
        cfg["sniper"]["executables"] = [
            {
                "name": str(name),
                "path": str(Path(str(exe_root)).expanduser() / str(name)),
                "args": [str(a) for a in exe_args],
            }
            for name in exe_names
        ]

    # Translate workload_mode: single|multiple -> ice.workloads.mode: single|manifest
    workload_mode = str(user_edit.get("workload_mode", "")).strip().lower()
    if workload_mode:
        cfg.setdefault("ice", {})
        cfg["ice"].setdefault("workloads", {})
        if workload_mode == "single":
            cfg["ice"]["workloads"]["mode"] = "single"
        elif workload_mode == "multiple":
            cfg["ice"]["workloads"]["mode"] = "manifest"
        else:
            raise ValueError("user_edit.workload_mode must be 'single' or 'multiple'.")

    return cfg

# -------------------------
# Validation
# -------------------------

def require(cfg: Dict[str, Any], dotted: str) -> Any:
    try:
        return deep_get(cfg, dotted)
    except KeyError as e:
        raise ValueError(f"Missing required config field: {dotted}") from e


def validate_config(cfg: Dict[str, Any]) -> None:
    require(cfg, "config_version")

    # Paths
    for k in ["hotgauge_root", "snipersim_root", "scripts_dir", "examples_dir", "template_dir"]:
        require(cfg, f"paths.{k}")

    # Experiment
    exp_name = require(cfg, "experiment.name")
    if not exp_name or not str(exp_name).strip():
        raise ValueError("experiment.name must be set (non-empty).")

    # Sniper
    for k in [
        "sniper_cfg",
        "num_cores",
        "sde_arch",
        "energystats_interval",
        "roi_enable",
        "instruction_count",
        "output_root",
        "tech_node_label",
        "frequency_label",
        "executables",
    ]:
        require(cfg, f"sniper.{k}")

    exes = require(cfg, "sniper.executables")
    if not isinstance(exes, list) or len(exes) == 0:
        raise ValueError("sniper.executables must be a non-empty list.")
    for i, exe in enumerate(exes):
        if not isinstance(exe, dict):
            raise ValueError(f"sniper.executables[{i}] must be a mapping.")
        for k in ["name", "path"]:
            if k not in exe or not exe[k]:
                raise ValueError(f"sniper.executables[{i}].{k} is required.")
        if "args" in exe and exe["args"] is not None and not isinstance(exe["args"], list):
            raise ValueError(f"sniper.executables[{i}].args must be a list (or omitted).")

    # McPAT
    require(cfg, "mcpat.script")
    require(cfg, "mcpat.max_jobs")

    # Trace generation
    require(cfg, "trace_gen.make_pow_trace_script")
    require(cfg, "trace_gen.traces_subdir")
    require(cfg, "trace_gen.metadata_subdir")
    require(cfg, "trace_gen.workload_manifest.output_filename")

    # ICE
    require(cfg, "ice.sim_from_warmup_script")
    require(cfg, "ice.warmup.tstack_path")
    require(cfg, "ice.flp.template_name")
    require(cfg, "ice.core_mapping.map")
    require(cfg, "ice.workloads.mode")

    mode = str(deep_get(cfg, "ice.workloads.mode")).strip().lower()
    if mode not in ("single", "manifest"):
        raise ValueError("ice.workloads.mode must be 'single' or 'manifest'.")

    # In single mode, enforce one executable (per your intended semantics)
    if mode == "single" and len(exes) != 1:
        raise ValueError(
            "ice.workloads.mode is 'single' but sniper.executables has != 1 entry. "
            "Either set mode=manifest or provide exactly one executable."
        )


# -------------------------
# Core mapping conversion (YAML dict -> legacy CLI syntax)
# -------------------------

def core_mapping_dict_to_cli(mapping: Dict[str, Any]) -> str:
    """
    Convert target->source mapping dict from YAML into the CLI syntax expected by sim_from_warmup:
      - identity: "0,2,6"
      - single-source fanout: "0->2,6"

    If mapping cannot be represented (multiple sources), raise a ValueError.

    Examples:
      {"0":0} -> "0"
      {2:0, 6:0} -> "0->2,6"
      {0:0, 2:2, 6:6} -> "0,2,6"
    """
    items = [(int(t), int(s)) for t, s in mapping.items()]
    if not items:
        raise ValueError("ice.core_mapping.map cannot be empty.")

    # Sort by target for deterministic output naming / CLI
    items.sort(key=lambda x: x[0])
    targets = [t for t, _ in items]
    sources = [s for _, s in items]

    # Identity mapping
    if all(t == s for t, s in items):
        return ",".join(str(t) for t in targets)

    # Single-source fanout
    unique_sources = sorted(set(sources))
    if len(unique_sources) == 1:
        src = unique_sources[0]
        return f"{src}->" + ",".join(str(t) for t in targets)

    raise ValueError(
        "ice.core_mapping.map cannot be represented with the legacy --core-mapping syntax "
        "('0,2,6' or '0->2,6') because it uses multiple source cores.\n"
        f"Provided mapping: {dict(items)}\n"
        "Either change the mapping to identity or single-source fanout, or extend sim_from_warmup "
        "to accept a general mapping syntax."
    )


# -------------------------
# Core pipeline
# -------------------------

def ensure_experiment_dir(template_dir: Path, experiment_dir: Path, recreate: bool) -> None:
    if experiment_dir.exists():
        if not recreate:
            log(f"Experiment directory already exists: {experiment_dir}")
            log("recreate_if_exists=false, so I will reuse it (no template copy).")
            return
        stage("Recreate experiment directory")
        log(f"Deleting existing experiment directory: {experiment_dir}")
        shutil.rmtree(experiment_dir)

    stage("Create experiment directory from template")
    log(f"Copying template:\n  from {template_dir}\n  to   {experiment_dir}")
    shutil.copytree(template_dir, experiment_dir)
    log("Template copy completed.")


def build_sniper_output_dir(
    cfg: Dict[str, Any],
    exe_name: str,
    override_tech: Optional[str] = None,
) -> Path:
    out_root = Path(cfg["sniper"]["output_root"])
    tech = override_tech or str(cfg["sniper"]["tech_node_label"])
    freq = str(cfg["sniper"]["frequency_label"])
    return out_root / exe_name / tech / freq


def run_sniper_for_executable(cfg: Dict[str, Any], exe: Dict[str, Any], snipersim_root: Path) -> Path:
    exe_name = str(exe["name"])
    exe_path = Path(str(exe["path"])).expanduser().resolve()
    exe_args = [str(a) for a in (exe.get("args") or [])]

    sniper_cfg = Path(str(cfg["sniper"]["sniper_cfg"])).expanduser().resolve()
    ncores = str(cfg["sniper"]["num_cores"])
    sde_arch = str(cfg["sniper"]["sde_arch"])
    energystats_interval = str(cfg["sniper"]["energystats_interval"])
    icount = str(cfg["sniper"]["instruction_count"])

    roi_enable = str(cfg["sniper"]["roi_enable"])

    out_dir = build_sniper_output_dir(cfg, exe_name)
    out_dir.parent.mkdir(parents=True, exist_ok=True)

    if roi_enable == "True":
        cmd = [
            str(snipersim_root / "run-sniper"),
            "-c", str(sniper_cfg),
            "-n", ncores,
            "-d", str(out_dir),
            "-s", f"energystats:{energystats_interval}",
            "-s", f"stop-by-icount:{icount}",
            f"--sde-arch={sde_arch}",
            "--roi",
            "--",
            str(exe_path),
            *exe_args,
        ]
    
    else:
        cmd = [
           str(snipersim_root / "run-sniper"),
            "-c", str(sniper_cfg),
            "-n", ncores,
            "-d", str(out_dir),
            "-s", f"energystats:{energystats_interval}",
            "-s", f"stop-by-icount:{icount}",
            f"--sde-arch={sde_arch}",
            "--",
            str(exe_path),
            *exe_args,
        ]

    stage(f"Sniper: run {exe_name}")
    run_cmd(cmd, cwd=snipersim_root)
    log(f"Sniper stage complete for {exe_name}. Output dir: {out_dir}")

    return out_dir

def run_mcpat(cfg: Dict[str, Any], sniper_out_dir: Path, num_cores: int, scripts_dir: Path) -> None:
    mcpat_script = Path(str(cfg["mcpat"]["script"])).expanduser().resolve()
    max_jobs = int(cfg["mcpat"]["max_jobs"])

    if max_jobs < 1:
        raise ValueError("mcpat_max_jobs must be >= 1.")

    sniper_exe_root = sniper_out_dir.parent.parent

    stage("McPAT: perf -> power sims conversion")
    run_cmd(
        [
            str(mcpat_script),
            str(sniper_exe_root),
            str(num_cores),
            str(max_jobs),
        ],
        cwd=scripts_dir,
    )
    log("McPAT conversion complete.")


def run_make_pow_trace(
    cfg: Dict[str, Any],
    experiment_dir: Path,
    sniper_out_dir: Path,
    exe_name: str,
) -> Tuple[Path, Path]:
    make_pow = Path(str(cfg["trace_gen"]["make_pow_trace_script"])).expanduser().resolve()

    traces_dir = experiment_dir / str(cfg["trace_gen"]["traces_subdir"])
    meta_dir = experiment_dir / str(cfg["trace_gen"]["metadata_subdir"])
    traces_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    prefix = exe_name  # enforced by config: prefix_from_executable_name=true

    icount = str(cfg["sniper"]["instruction_count"])

    # NOTE: Your YAML uses energystats_interval; make_pow_trace expects interval-ns.
    # If these differ in your environment, add a separate config field.
    interval_ns = str(cfg["sniper"]["energystats_interval"])

    suite = str(cfg["experiment"]["name"])

    stage(f"Trace generation: make_pow_trace for {exe_name}")
    cmd = [
        sys.executable, str(make_pow),
        "--sniper-output-dir", str(sniper_out_dir),
        "--prefix-for-files", prefix,
        "--instruction-count", icount,
        "--interval-ns", interval_ns,
        "--suite", suite,
    ]
    run_cmd(cmd, cwd=experiment_dir)

    trace_path = traces_dir / f"{prefix}_pow_trace.json"
    meta_path = meta_dir / f"{prefix}_metadata.json"

    if not trace_path.exists():
        raise FileNotFoundError(f"Expected trace not found after make_pow_trace: {trace_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Expected metadata not found after make_pow_trace: {meta_path}")

    log(f"Trace generation complete for {exe_name}.")
    log(f"  trace: {trace_path}")
    log(f"  meta:  {meta_path}")
    return trace_path, meta_path


def run_make_workloads_json(cfg: Dict[str, Any], experiment_dir: Path) -> Path:
    mj = Path(str(cfg["trace_gen"]["workload_manifest"]["make_workload_json_script"])).expanduser().resolve()
    out_name = str(cfg["trace_gen"]["workload_manifest"]["output_filename"])
    out_path = experiment_dir / out_name

    stage("Manifest generation: workloads.json")
    run_cmd([sys.executable, str(mj)], cwd=experiment_dir)

    if not out_path.exists():
        raise FileNotFoundError(f"Expected workload manifest not found: {out_path}")
    log(f"Workload manifest generated: {out_path}")
    return out_path


def run_ice(cfg: Dict[str, Any], experiment_dir: Path, single_prefix: str | None) -> None:
    sim_script = Path(str(cfg["ice"]["sim_from_warmup_script"])).expanduser().resolve()
    tstack = Path(str(cfg["ice"]["warmup"]["tstack_path"])).expanduser().resolve()
    flp_template = str(cfg["ice"]["flp"]["template_name"])

    workloads_mode = str(cfg["ice"]["workloads"]["mode"]).strip().lower()

    stage("3D-ICE: sim_from_warmup")

    cmd = [
        sys.executable, str(sim_script),
        "--tstack-path", str(tstack),
        "--flp-template", flp_template,
    ]

    if workloads_mode == "manifest":
        mp = Path(str(cfg["ice"]["workloads"]["manifest_path"])).expanduser().resolve()
        cmd += ["--workload-manifest", str(mp)]
    else:
        if single_prefix is None:
            raise RuntimeError("Internal error: single_prefix is required for single workload mode.")
        trace_file = experiment_dir / str(cfg["trace_gen"]["traces_subdir"]) / f"{single_prefix}_pow_trace.json"
        meta_file = experiment_dir / str(cfg["trace_gen"]["metadata_subdir"]) / f"{single_prefix}_metadata.json"
        cmd += ["--trace-file", str(trace_file), "--metadata-file", str(meta_file)]

    core_map: Dict[str, Any] = cfg["ice"]["core_mapping"]["map"]
    core_map_str = core_mapping_dict_to_cli(core_map)
    cmd += ["--core-mapping", core_map_str]
    log(f"Using --core-mapping {core_map_str}")

    run_cmd(cmd, cwd=experiment_dir)
    log("3D-ICE stage complete.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to YAML config (e.g., end_to_end.yaml)")
    args = ap.parse_args()

    cfg_path = Path(args.config).expanduser().resolve()

    stage("Load configuration")
    log(f"Reading config: {cfg_path}")
    cfg = load_config(cfg_path)
    validate_config(cfg)
    log("Config loaded and validated.")

    hotgauge_root = Path(str(cfg["paths"]["hotgauge_root"])).expanduser().resolve()
    snipersim_root = Path(str(cfg["paths"]["snipersim_root"])).expanduser().resolve()
    scripts_dir = Path(str(cfg["paths"]["scripts_dir"])).expanduser().resolve()
    examples_dir = Path(str(cfg["paths"]["examples_dir"])).expanduser().resolve()
    template_dir = Path(str(cfg["paths"]["template_dir"])).expanduser().resolve()

    exp_name = str(cfg["experiment"]["name"])
    recreate = bool(cfg["experiment"].get("recreate_if_exists", False))
    experiment_dir = examples_dir / exp_name

    log(f"HOTGAUGE_ROOT   = {hotgauge_root}")
    log(f"SNIPERSIM_ROOT  = {snipersim_root}")
    log(f"SCRIPTS_DIR     = {scripts_dir}")
    log(f"EXAMPLES_DIR    = {examples_dir}")
    log(f"TEMPLATE_DIR    = {template_dir}")
    log(f"EXPERIMENT_DIR  = {experiment_dir}")

    ensure_experiment_dir(template_dir, experiment_dir, recreate=recreate)

    executables: List[Dict[str, Any]] = cfg["sniper"]["executables"]
    num_cores = int(cfg["sniper"]["num_cores"])

    produced_pairs: List[Tuple[str, Path, Path, Path]] = []

    for exe in executables:
        exe_name = str(exe["name"])

        sniper_out_dir = run_sniper_for_executable(cfg, exe, snipersim_root=snipersim_root)
        other_sniper_out_dir = build_sniper_output_dir(cfg, exe_name, override_tech="7nm")
        run_mcpat(cfg, sniper_out_dir=sniper_out_dir, num_cores=num_cores, scripts_dir=scripts_dir)
        trace_path, meta_path = run_make_pow_trace(
            cfg,
            experiment_dir=experiment_dir,
            sniper_out_dir=other_sniper_out_dir,
            exe_name=exe_name,
        )

        produced_pairs.append((exe_name, sniper_out_dir, trace_path, meta_path))
        log(f"Completed per-executable pipeline for {exe_name}.")

    workloads_mode = str(cfg["ice"]["workloads"]["mode"]).strip().lower()
    if workloads_mode == "manifest":
        enabled = bool(cfg["trace_gen"]["workload_manifest"].get("enabled_if_multiple_executables", True))
        if enabled and len(executables) > 1:
            manifest = run_make_workloads_json(cfg, experiment_dir=experiment_dir)
            log(f"Using manifest for ICE: {manifest}")
        elif len(executables) == 1:
            manifest_path = Path(str(cfg["ice"]["workloads"]["manifest_path"])).expanduser().resolve()
            if not manifest_path.exists():
                raise FileNotFoundError(
                    f"ice.workloads.mode=manifest but manifest does not exist: {manifest_path}\n"
                    f"Either set mode=single or generate workloads.json."
                )
        else:
            raise RuntimeError(
                "ice.workloads.mode=manifest but workload manifest generation is disabled and >1 executables present."
            )

    single_prefix = None
    if workloads_mode == "single":
        single_prefix = str(executables[0]["name"])

    run_ice(cfg, experiment_dir=experiment_dir, single_prefix=single_prefix)

    stage("DONE")
    log("End-to-end HotGauge run completed successfully.")
    log(f"Experiment outputs live under: {experiment_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Command failed with exit code {e.returncode}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        raise
