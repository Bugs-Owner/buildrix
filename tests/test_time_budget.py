"""Per-task time budgets, extensions for runs that progress, and stop rules.

The agents here are short Python scripts run through the real CLI adapter's
process handling and the real watch, with budgets of a few seconds. No model
is called.
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import zipfile

import pytest

from buildrix import bench, benchmark_batch as batch, time_watch
from buildrix.benchmark_agents import CLIAgent
from test_benchmark_batch import FakeAgent, Hub


START = """
import json, sys, time
from pathlib import Path
sys.stdin.read()
Path("outputs").mkdir(exist_ok=True)
Path("outputs/answer.txt").write_text("draft")
def status():
    try:
        return Path("TIME_REMAINING.txt").read_text().splitlines()[0]
    except (OSError, IndexError):  # being replaced this instant
        return "status: ok"
def done():
    Path("outputs/answer.txt").write_text("final")
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}))
"""
DILIGENT = START + """
while status() == "status: ok":
    time.sleep(0.05)
done()
"""
WORKING = START + """
for i in range(30):  # keeps changing files for ~6 s
    Path(f"outputs/step-{i}.txt").write_text(str(i))
    time.sleep(0.2)
done()
"""
COMPUTING = START + """
end = time.time() + 5  # silent number crunching: no files, no output
while time.time() < end:
    sum(i * i for i in range(10000))
done()
"""
ENDLESS = START + """
i = 0
while True:
    Path("outputs/progress.txt").write_text(str(i)); i += 1
    time.sleep(0.2)
"""
SILENT = START + """
time.sleep(120)
"""
TALKING = START + """
i = 0
while True:  # new output, but no files and no computation
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": str(i)}}), flush=True)
    i += 1
    time.sleep(0.2)
"""
LOOPING = START + """
while True:  # the same failing command again and again
    print(json.dumps({"type": "item.completed", "item": {"type": "command_execution",
          "command": "python fit.py", "exit_code": 1}}), flush=True)
    time.sleep(0.2)
"""


def script_agent(tmp_path, monkeypatch, source, **kwargs):
    """A CLIAgent whose CLI is a Python script; process handling is the real one."""
    script = tmp_path / "agent.py"
    script.write_text(textwrap.dedent(source))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("shutil.which", lambda name: sys.executable)
    monkeypatch.setattr(CLIAgent, "command", lambda self: [sys.executable, str(script)])
    return CLIAgent("codex", "fixed", **kwargs)


def run(tmp_path, monkeypatch, source, **kwargs):
    ws = tmp_path / "ws"
    (ws / "outputs").mkdir(parents=True)
    result = script_agent(tmp_path, monkeypatch, source, **kwargs).run(ws, "task")
    return result, ws, [n["status"] for n in result.time_notices]


def test_agent_reads_the_reminder_and_finishes(tmp_path, monkeypatch):
    result, ws, notices = run(tmp_path, monkeypatch, DILIGENT, timeout_s=4, stall_s=60)
    assert result.ok and result.stop_reason == "exited"
    assert (ws / "outputs/answer.txt").read_text() == "final"
    assert notices == ["EXPECTED TIME NEARLY USED"] and 2.5 <= result.time_notices[0]["at_s"] < 4


def test_run_that_keeps_changing_files_is_extended_past_its_budget(tmp_path, monkeypatch):
    result, ws, notices = run(tmp_path, monkeypatch, WORKING, timeout_s=2, extend_s=1, ceiling_s=20, stall_s=3)
    assert result.ok and result.stop_reason == "exited" and result.wall_clock_s > 4
    assert len(result.extensions) >= 2
    assert all(e["evidence"]["files_changed_s_ago"] <= 1 for e in result.extensions)
    assert "PAST EXPECTED TIME" in notices
    assert (ws / "outputs/answer.txt").read_text() == "final"


@pytest.mark.skipif(sys.platform == "darwin", reason="no CPU meter for native macOS")
def test_silent_computation_counts_as_progress(tmp_path, monkeypatch):
    result, ws, _ = run(tmp_path, monkeypatch, COMPUTING, timeout_s=2, extend_s=1, ceiling_s=20, stall_s=2)
    assert result.ok and result.stop_reason == "exited"
    assert result.extensions and result.extensions[0]["evidence"]["cpu_busy_s_ago"] <= 1


def test_stalled_run_is_stopped_before_its_budget_and_keeps_outputs(tmp_path, monkeypatch):
    result, ws, notices = run(tmp_path, monkeypatch, SILENT, timeout_s=60, stall_s=2)
    assert result.stop_reason == "stalled" and not result.ok
    assert result.error.startswith("STOPPED (stalled)")
    assert result.wall_clock_s < 2 + 15  # far below the 60 s budget (grace included)
    assert notices == ["NO ACTIVITY"]  # announced before the stop
    assert (ws / "outputs/answer.txt").read_text() == "draft"
    assert (ws / "TIME_REMAINING.txt").read_text().startswith("status: STOPPED")


def test_ceiling_is_the_hard_stop_and_is_announced_ahead(tmp_path, monkeypatch):
    result, ws, notices = run(tmp_path, monkeypatch, ENDLESS, timeout_s=2, extend_s=1, ceiling_s=4, stall_s=2)
    assert result.stop_reason == "ceiling"
    final = next(n for n in result.time_notices if n["status"] == "FINAL WARNING")
    assert final["at_s"] <= 4 - 1  # lead here: min(300 s, stall/2, budget/2) = 1 s
    assert (ws / "outputs/progress.txt").exists()


def test_talking_without_files_or_computation_is_not_progress_past_the_budget(tmp_path, monkeypatch):
    result, ws, notices = run(tmp_path, monkeypatch, TALKING, timeout_s=2, extend_s=1, ceiling_s=20, stall_s=10)
    assert result.stop_reason == "no_progress"
    assert "NO PROGRESS" in notices and not result.extensions
    assert result.wall_clock_s < 2 + 1 + 15


def test_repeating_the_same_call_is_a_loop_not_activity(tmp_path, monkeypatch):
    result, ws, notices = run(tmp_path, monkeypatch, LOOPING, timeout_s=60, stall_s=2)
    assert result.stop_reason == "loop"


def test_tool_calls_are_read_from_both_transcript_formats():
    claude = json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}, {"type": "text", "text": "x"}]}})
    codex = json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}})
    other = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ls"}})
    assert len(time_watch.tool_calls("\n".join([claude, codex, other, "not json"]))) == 2


def test_bash_shows_the_notice_before_each_command(tmp_path):
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is not installed")
    ws = tmp_path / "work space"
    ws.mkdir()
    (ws / time_watch.BASH_FILE).write_text(time_watch.BASH_NOTICE, newline="\n")
    env = {"PATH": os.environ["PATH"], "BASH_ENV": (ws / time_watch.BASH_FILE).as_posix()}
    command = lambda: subprocess.run([bash, "-c", "echo done"], env=env, capture_output=True, text=True)
    time_watch.write_clock(ws, "status: ok\nExpected time: 60 minutes.\n")
    quiet = command()
    time_watch.write_clock(ws, "status: PAST EXPECTED TIME\nKeep going only if you are making progress.\n")
    noticed = command()
    assert quiet.stdout.strip() == "done" and "status" not in quiet.stderr
    assert noticed.stdout.strip() == "done" and "PAST EXPECTED TIME" in noticed.stderr


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


def test_old_timeout_s_is_the_default_budget_with_default_rules(tmp_path):
    found = budgets(tmp_path, study(tmp_path, timeout_s=3600))
    assert set(map(json.dumps, found.values())) == {json.dumps({"wall_clock_s": 3600,
        "source": "study_default", "extend_s": 1800, "ceiling_s": 14400, "stall_s": 1200})}


def test_short_budgets_are_raised_to_the_minimum(tmp_path):
    found = budgets(tmp_path, study(tmp_path, timeout_s=300))
    assert found["T001", "a"]["wall_clock_s"] == 900 and found["T001", "a"]["raised_from_s"] == 300


def test_task_override_wins_and_every_agent_gets_the_same_rules(tmp_path):
    found = budgets(tmp_path, study(tmp_path, time={"default_s": 1800, "tasks": {"T002": 36000},
                                                    "extend": 0.25, "ceiling": 2, "stall_s": 600}))
    assert found["T001", "a"] == found["T001", "b"]
    assert found["T002", "a"] == found["T002", "b"] == {"wall_clock_s": 36000, "source": "task_override",
        "extend_s": 9000, "ceiling_s": 72000, "stall_s": 600}


@pytest.mark.parametrize("time_settings, message", [
    ({"timeout_s": 600, "time": {"default_s": 900}}, "once"),
    ({"time": {"tasks": {"T999": 60}}}, "T999"),
    ({"time": {"default_s": 0}}, "whole number"),
    ({"time": {"tasks": {"T001": "1h"}}}, "whole number"),
    ({"time": {"ceiling": 0.5}}, "ceiling"),
    ({"time": {"extend": 0}}, "extend"),
    ({"time": {"reference": {"factor": 2}}}, "needs results")])
def test_unclear_budgets_are_rejected(tmp_path, time_settings, message):
    with pytest.raises(ValueError, match=message):
        batch.prepare(study(tmp_path, **time_settings), tmp_path / "bundle", Hub())


def test_budget_from_a_reference_run(tmp_path):
    reference = tmp_path / "reference"
    for index, (model, code, status, wall) in enumerate([
            ("a", "T001", "completed", 500), ("a", "T001", "completed", 610),
            ("a", "T001", "stopped", 5000), ("b", "T002", "completed", 50)]):
        batch.write_json(reference / f"job-{index:05d}/group.json", {"model": model, "task_code": code,
            "records": [{"status": status, "wall_clock_s": wall}]})
    assert batch.reference_wall_times(reference) == {"T001": 610, "T002": 50}
    found = budgets(tmp_path, study(tmp_path, time={"default_s": 900,
        "reference": {"results": "reference", "model": "a", "factor": 3}}))
    assert found["T001", "b"]["wall_clock_s"] == 1860
    assert found["T001", "b"]["source"] == "reference_run" and found["T001", "b"]["reference_wall_clock_s"] == 610
    assert found["T002", "a"]["source"] == "study_default"  # no run by model a


def test_stopped_run_is_kept_graded_and_recorded(tmp_path, monkeypatch):
    manifest = study(tmp_path, time={"default_s": 600, "min_s": 1, "stall_s": 2})
    batch.write_json(manifest, {**batch.read_json(manifest), "pairs": [{"tasks": ["T001"]}],
                                "agents": [{"provider": "codex", "model": "a"}]})
    hub = Hub()
    batch.prepare(manifest, tmp_path / "bundle", hub)
    script_agent(tmp_path, monkeypatch, SILENT)
    output = tmp_path / "results"
    result = batch.run_batch(tmp_path / "bundle", output, api=hub)
    assert result[0]["group_id"] == "g1" and result[0]["run_errors"] == 0
    group = hub.uploads[0]
    assert group["run_config"]["time_budget"]["stall_s"] == 2
    assert group["run_config"]["machines"][0]["cpu_count"]
    for record in group["records"]:
        assert record["status"] == "stopped" and record["stop_reason"] == "stalled"
        assert record["score"] == 0.5  # graded on what it left
        assert record["time_budget_s"] == 600 and record["time_notices"][0]["status"] == "NO ACTIVITY"
        assert record["extensions"] == [] and record["wall_clock_s"] < 600
        assert "hostname" not in str(record["machine"]).lower()
        assert any(a["path"] == "outputs/answer.txt" for a in record["artifacts"])
    for path in output.rglob("outputs.zip"):
        assert zipfile.ZipFile(path).read("outputs/answer.txt") == b"draft"
    prompt = next(output.rglob("prompt.md")).read_text(encoding="utf-8")
    assert "Expected time: about 10 minutes" in prompt and "hard limit of 40 minutes" in prompt
    assert "stop_reason" in next(output.rglob("measurements.csv")).read_text()
