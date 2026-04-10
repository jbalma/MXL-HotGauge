#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict


THIS_FILE = Path(__file__).resolve()
BASE_DIR = THIS_FILE.parent

TRACES_DIR = BASE_DIR / "Traces"
METADATA_DIR = BASE_DIR / "Metadata"
OUT_FILE = BASE_DIR / "workloads.json"

TRACE_RE = re.compile(r"^(?P<prefix>.+)_pow_trace\.json$")
META_RE = re.compile(r"^(?P<prefix>.+)_metadata\.json$")


def index_by_prefix(files, pattern) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for p in files:
        m = pattern.match(p.name)
        if not m:
            continue
        prefix = m.group("prefix")
        if prefix in out:
            raise RuntimeError(
                f"Duplicate prefix '{prefix}' found:\n  {out[prefix]}\n  {p}"
            )
        out[prefix] = p
    return out


def main() -> int:

    if not TRACES_DIR.is_dir():
        print(f"ERROR: Missing Traces directory: {TRACES_DIR}", file=sys.stderr)
        return 2

    if not METADATA_DIR.is_dir():
        print(f"ERROR: Missing Metadata directory: {METADATA_DIR}", file=sys.stderr)
        return 2

    trace_files = sorted(TRACES_DIR.glob("*.json"))
    meta_files = sorted(METADATA_DIR.glob("*.json"))

    traces_by_prefix = index_by_prefix(trace_files, TRACE_RE)
    metas_by_prefix = index_by_prefix(meta_files, META_RE)

    common = sorted(set(traces_by_prefix) & set(metas_by_prefix))

    if not common:
        print("ERROR: No matching trace/metadata pairs found.", file=sys.stderr)
        return 1

    workloads = []
    for prefix in common:
        workloads.append(
            {
                "trace": str(traces_by_prefix[prefix].resolve()),
                "meta":  str(metas_by_prefix[prefix].resolve()),
            }
        )

    OUT_FILE.write_text(json.dumps(workloads, indent=2) + "\n")

    print(f"Wrote {len(workloads)} workload entries to: {OUT_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
