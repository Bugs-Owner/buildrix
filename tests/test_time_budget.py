"""Per-task time budgets, the warnings an agent gets, and what a timeout keeps.

The agents here are short Python scripts run through the real CLI adapter's
process handling, with budgets of a few seconds. No model is called.
"""
import sys
import textwrap
import zipfile

import pytest

from buildrix import bench, benchmark_batch as batch
from buildrix.benchmark_agents import CLIAgent
from test_benchmark_batch import FakeAgent, Hub


# Reads the clock file the way the brief asks; finalizes when warned.
DILIGENT = """
import json, sys, time
from pathlib import Path
sys.stdin.read()
out = Path("outputs"); out.mkdir(exist_ok=True)
(out / "answer.txt").write_text("draft")
def status():
    try:
        return Path("TIME_REMAINING.txt").read_text().splitlines()[0]
    except (OSError, IndexError):  # being replaced this instant
        return "status: ok"
while status() == "status: ok":
    time.sleep(0.05)
(out / "answer.txt").write_text("final")
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}))
"""

# Writes a draft, then ignores every warning.
STUBBORN = """
import sys, time
from pathlib import Path
sys.stdin.read()
Path("outputs").mkdir(exist_ok=True)
Path("outputs/answer.txt").write_text("draft")
time.sleep(120)
"""


def script_agent(tmp_path, monkeypatch, source, **kwargs):
    """A CLIAgent whose CLI is a Python script; process handling is the real one."""
    script = tmp_path / "agent.py"
    script.write_text(textwrap.dedent(source))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("shutil.which", lambda name: sys.executable)
    monkeypatch.setattr(CLIAgent, "command", lambda self: [sys.executable, str(script)])
    return CLIAgent("codex", "fixed", **kwargs)


def workspace(tmp_path):
    ws = tmp_path / "ws"
    (ws / "outputs").mkdir(parents=True)
    return ws


def test_agent_is_warned_through_the_clock_file_and_can_finish(tmp_path, monkeypatch):
    agent = script_agent(tmp_path, monkeypatch, DILIGENT, timeout_s=4)
    ws = workspace(tmp_path)
    result = agent.run(ws, "task")
    assert result.ok and not result.timed_out
    assert (ws / "outputs/answer.txt").read_text() == "final"
    assert result.time_notices and 2.5 <= result.time_notices[0] < 4
    assert result.wall_clock_s < 4


def test_timeout_stops_the_agent_and_keeps_its_outputs(tmp_path, monkeypatch):
    agent = script_agent(tmp_path, monkeypatch, STUBBORN, timeout_s=4)
    ws = workspace(tmp_path)
    result = agent.run(ws, "task")
    assert result.timed_out and not result.ok
    assert result.error.startswith("TIMED_OUT")
    assert len(result.time_notices) == 2  # 75% and 90% were both written
    assert result.wall_clock_s < 4 + 15
    assert (ws / "outputs/answer.txt").read_text() == "draft"
    assert (ws / "TIME_REMAINING.txt").read_text().startswith("status: STOPPED")


def test_bash_shows_the_warning_before_each_command(tmp_path):
    import shutil
    import subprocess
    from buildrix.benchmark_agents import BASH_NOTICE, write_clock
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is not installed")
    ws = tmp_path / "work space"
    ws.mkdir()
    (ws / ".buildrix-time.sh").write_text(BASH_NOTICE, newline="\n")
    env = {"PATH": __import__("os").environ["PATH"], "BASH_ENV": (ws / ".buildrix-time.sh").as_posix()}
    run = lambda: subprocess.run([bash, "-c", "echo done"], env=env, capture_output=True, text=True)
    write_clock(ws, 3600, __import__("time").time() + 3000, "ok")
    quiet = run()
    write_clock(ws, 3600, __import__("time").time() + 300, "FINAL WARNING", "Stop exploring now.")
    warned = run()
    assert quiet.stdout.strip() == "done" and "status" not in quiet.stderr
    assert warned.stdout.strip() == "done" and "FINAL WARNING" in warned.stderr


def study(tmp_path, **time_settings):
    FakeAgent.calls = []
    manifest = tmp_path / "study.json"
    batch.write_json(manifest, {"schema": "buildrix-study/1", "trials": 1,
        "agents": [{"provider": "codex", "model": "a"}, {"provider": "claude", "model": "b"}],
        "pairs": [{"tasks": ["T001", "T002"]}], "execution": {"backend": "native"}, **time_settings})
    return manifest


def budgets(tmp_path, manifest):
    prepared = batch.prepare(manifest, tmp_path / "bundle", Hub())
    return {(job["task"]["task_code"], job["agent"]["model"]): job["time_budget"] for job in prepared["jobs"]}


def test_old_timeout_s_is_the_default_budget_for_every_task_and_agent(tmp_path):
    found = budgets(tmp_path, study(tmp_path, timeout_s=3600))
    assert {b["wall_clock_s"] for b in found.values()} == {3600}
    assert {b["source"] for b in found.values()} == {"study_default"}


def test_task_override_wins_and_every_agent_gets_the_same_budget(tmp_path):
    found = budgets(tmp_path, study(tmp_path, time={"default_s": 1800, "tasks": {"T002": 36000}}))
    assert found["T001", "a"] == found["T001", "b"] == {"wall_clock_s": 1800, "source": "study_default"}
    assert found["T002", "a"] == found["T002", "b"] == {"wall_clock_s": 36000, "source": "task_override"}


@pytest.mark.parametrize("time_settings, message", [
    ({"timeout_s": 600, "time": {"default_s": 900}}, "once"),
    ({"time": {"tasks": {"T999": 60}}}, "T999"),
    ({"time": {"default_s": 0}}, "whole number"),
    ({"time": {"tasks": {"T001": "1h"}}}, "whole number"),
    ({"time": {"reference": {"factor": 2}}}, "needs results")])
def test_unclear_budgets_are_rejected(tmp_path, time_settings, message):
    with pytest.raises(ValueError, match=message):
        batch.prepare(study(tmp_path, **time_settings), tmp_path / "bundle", Hub())


def test_budget_from_a_reference_run(tmp_path):
    reference = tmp_path / "reference"
    for index, (model, code, status, wall) in enumerate([
            ("a", "T001", "completed", 500), ("a", "T001", "completed", 610),
            ("a", "T001", "timed_out", 5000), ("b", "T002", "completed", 50)]):
        batch.write_json(reference / f"job-{index:05d}/group.json", {"model": model, "task_code": code,
            "records": [{"status": status, "wall_clock_s": wall}]})
    assert batch.reference_wall_times(reference) == {"T001": 610, "T002": 50}
    found = budgets(tmp_path, study(tmp_path, time={"default_s": 900,
        "reference": {"results": "reference", "model": "a", "factor": 3}}))
    assert found["T001", "b"] == {"wall_clock_s": 1860, "source": "reference_run", "factor": 3,
                                  "reference_wall_clock_s": 610, "reference_model": "a"}
    assert found["T002", "a"]["source"] == "study_default"  # no run by model a


def test_timed_out_run_is_kept_graded_and_recorded_with_its_budget(tmp_path, monkeypatch):
    manifest = study(tmp_path, time={"default_s": 600, "tasks": {"T001": 2}})
    batch.write_json(manifest, {**batch.read_json(manifest), "pairs": [{"tasks": ["T001"]}],
                                "agents": [{"provider": "codex", "model": "a"}]})
    hub = Hub()
    batch.prepare(manifest, tmp_path / "bundle", hub)
    script_agent(tmp_path, monkeypatch, STUBBORN)
    output = tmp_path / "results"
    result = batch.run_batch(tmp_path / "bundle", output, api=hub)
    assert result[0]["group_id"] == "g1" and result[0]["run_errors"] == 0
    group = hub.uploads[0]
    assert group["run_config"]["time_budget"] == {"wall_clock_s": 2, "source": "task_override"}
    assert group["run_config"]["machines"][0]["cpu_count"]
    for record in group["records"]:
        assert record["status"] == "timed_out" and record["score"] == 0.5  # graded
        assert record["time_budget_s"] == 2 and len(record["time_notices_s"]) == 2
        assert "hostname" not in str(record["machine"]).lower()
        assert any(a["path"] == "outputs/answer.txt" for a in record["artifacts"])
    for path in output.rglob("outputs.zip"):
        assert zipfile.ZipFile(path).read("outputs/answer.txt") == b"draft"
    prompt = next(output.rglob("prompt.md")).read_text(encoding="utf-8")
    assert "Time budget: 2 seconds" in prompt and "TIME_REMAINING.txt" in prompt
    assert "time_budget_s" in next(output.rglob("measurements.csv")).read_text()
