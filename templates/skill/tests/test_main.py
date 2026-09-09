"""Tests for your-skill-name.

`buildrix skill check` runs these, and runs them twice when the skill declares
itself deterministic. Keep them fast and offline: at least one test should
exercise the main entry point end to end on a small fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import main  # noqa: E402


def test_run_writes_its_declared_output(tmp_path):
    data = tmp_path / "clean.csv"
    data.write_text("timestamp,value\n2025-01-01T00:00:00,1.0\n", encoding="utf-8")

    out = tmp_path / "outputs"
    result = main.run(str(data), str(out))

    assert (out / "result.json").exists()
    assert isinstance(result, dict)


def test_run_is_repeatable(tmp_path):
    data = tmp_path / "clean.csv"
    data.write_text("timestamp,value\n2025-01-01T00:00:00,1.0\n", encoding="utf-8")

    first = main.run(str(data), str(tmp_path / "a"))
    second = main.run(str(data), str(tmp_path / "b"))

    assert first == second
