"""Turn a finished workspace into a submission bundle.

This file is public and it runs on the contributor's machine. Its whole job is
to make the upload small: a four-gigabyte EnergyPlus output folder becomes a
couple of megabytes of the files that are actually graded.

Two rules:
  · it must not score anything — that is the grader's job, on the server
  · it must be deterministic, so the same workspace always yields the same bundle

The default below copies the declared deliverables and nothing else. Add
aggregation here if your deliverables are large (hourly to monthly, a hash of a
big model file, the head and tail of a long log).
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Paths, relative to the workspace, that the grader needs.
DELIVERABLES = [
    "outputs/result.csv",
    "outputs/report.md",
]


def collect(workspace_dir: str, bundle_dir: str) -> list[str]:
    """Copy the graded files out of the workspace. Returns what was found."""
    ws, bundle = Path(workspace_dir), Path(bundle_dir)
    bundle.mkdir(parents=True, exist_ok=True)

    taken: list[str] = []
    for rel in DELIVERABLES:
        src = ws / rel
        if not src.exists():
            continue
        dst = bundle / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        taken.append(rel)
    return taken


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(prog="collect")
    ap.add_argument("workspace")
    ap.add_argument("bundle")
    args = ap.parse_args()
    for rel in collect(args.workspace, args.bundle):
        print(rel)
