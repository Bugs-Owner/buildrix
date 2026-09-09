"""Entry point for your-skill-name.

Keep the command-line surface small and obvious: the agent reads SKILL.md and
then runs these commands. Everything the agent needs to pass in should be a
flag, and every path should come from the caller, never be hard-coded.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def prepare(input_path: str, out_path: str) -> Path:
    """Clean or reshape the raw input into the form `run` expects."""
    src, dst = Path(input_path), Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    # TODO: your preparation step
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def run(data_path: str, out_dir: str = "outputs") -> dict:
    """Do the work and write the declared outputs. Return a small summary."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # TODO: your actual computation
    result = {"rows": 0, "note": "replace this with the real result"}

    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(prog="your-skill-name")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", help="Clean the raw input")
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="clean.csv")

    r = sub.add_parser("run", help="Run the main step")
    r.add_argument("--data", required=True)
    r.add_argument("--out", default="outputs")

    args = ap.parse_args()
    if args.cmd == "prepare":
        print(prepare(args.input, args.out))
    else:
        print(json.dumps(run(args.data, args.out), indent=2))


if __name__ == "__main__":
    main()
