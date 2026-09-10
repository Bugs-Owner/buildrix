"""The benchmark runner's local half: staging, isolation, evaluation, progress.

Nothing here touches the network. What is tested is the part that decides
whether a run is *comparable* — that each condition gets its own workspace, that
only the declared difference is staged, and that the fingerprint covers what has
to be held constant.
"""

import io
import json
import zipfile
from pathlib import Path

import pytest

from buildrix import bench


# ── a Task package to stage from ────────────────────────────────────────────

def _package(slug="bxt-1", deliverable="outputs/faults.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{slug}/prompt.md", "Find the faults.")
        z.writestr(f"{slug}/TASK.yaml", "schema: task/2.0\n")
        z.writestr(f"{slug}/inputs/trends.csv", "ts,value\n1,2\n")
    return buf.getvalue()


TASK = {
    "id": "t1", "task_code": "BXT-000001", "version": "1.0.0",
    "canonical_prompt": "Find every fault in AHU-3 and rank them.",
    "detailed_instruction": "SECRET: plot supply air against setpoint first.",
    "deliverables": [
        {"path": "outputs/faults.csv",
         "description": "columns: fault_id, start, end, severity"},
        {"path": "outputs/memo.md", "description": "ranked list"},
    ],
}


@pytest.fixture
def skill_dir(tmp_path):
    d = tmp_path / "ahu-fdd-helper"
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: ahu-fdd-helper\ndescription: Finds AHU faults from trend "
        "data. Use when asked to diagnose air-handler faults.\n---\n\n"
        "## Purpose\n\nFinds faults.\n\n## When to Use\n\nWhen asked.\n\n"
        "## Workflow\n\n1. Run `scripts/fdd.py`.\n", encoding="utf-8")
    (d / "scripts" / "fdd.py").write_text("def go():\n    return 1\n",
                                          encoding="utf-8")
    return d


# ═══════════════════════════════════════════════════════════════════════════
#  Staging and isolation
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("condition,wants_skill,wants_instruction", [
    ("task",                   False, False),
    ("task_instruction",       False, True),
    ("task_skill",             True,  False),
    ("task_instruction_skill", True,  True),
])
def test_only_the_declared_difference_is_staged(
        tmp_path, skill_dir, condition, wants_skill, wants_instruction):
    ws = tmp_path / condition
    ws.mkdir()
    bench._stage(ws, _package(), condition, skill_dir, TASK["detailed_instruction"])

    # The Task's public half is in every condition.
    assert (ws / "prompt.md").is_file()
    assert (ws / "inputs" / "trends.csv").is_file()
    assert (ws / "outputs").is_dir()
    # And only the declared extras vary.
    assert (ws / "skills" / "ahu-fdd-helper" / "SKILL.md").is_file() is wants_skill
    assert (ws / "DETAILED_INSTRUCTION.md").is_file() is wants_instruction


def test_staging_strips_the_package_root_and_refuses_traversal(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("slug/prompt.md", "ok")
        z.writestr("slug/../../escape.txt", "no")
    ws = tmp_path / "ws"
    ws.mkdir()
    bench._stage(ws, buf.getvalue(), "task", None, "")
    assert (ws / "prompt.md").is_file()
    assert not (tmp_path / "escape.txt").exists()


def test_each_condition_produces_a_different_workspace_digest(tmp_path, skill_dir):
    """The hub rejects a group whose conditions all hash the same — that would
    mean they shared a directory instead of being isolated."""
    digests = set()
    for condition in bench.CONDITIONS:
        ws = tmp_path / condition
        ws.mkdir()
        bench._stage(ws, _package(), condition, skill_dir,
                     TASK["detailed_instruction"])
        digests.add(bench.digest_dir(ws))
    assert len(digests) == len(bench.CONDITIONS)


def test_digest_is_content_addressed_not_path_addressed(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        (d / "sub").mkdir(parents=True)
        (d / "sub" / "x.txt").write_text("same", encoding="utf-8")
    assert bench.digest_dir(a) == bench.digest_dir(b)
    (b / "sub" / "x.txt").write_text("different", encoding="utf-8")
    assert bench.digest_dir(a) != bench.digest_dir(b)


# ═══════════════════════════════════════════════════════════════════════════
#  The prompt per condition
# ═══════════════════════════════════════════════════════════════════════════

def test_the_task_prompt_is_identical_in_every_condition():
    prompts = {c: bench._prompt_for(c, TASK, "", TASK["detailed_instruction"],
                                    "ahu-fdd-helper")
               for c in bench.CONDITIONS}
    for text in prompts.values():
        assert TASK["canonical_prompt"] in text


def test_the_control_prompt_never_mentions_the_extras():
    text = bench._prompt_for("task", TASK, "", TASK["detailed_instruction"],
                             "ahu-fdd-helper")
    assert "DETAILED_INSTRUCTION" not in text
    assert "skills/" not in text
    assert "SECRET" not in text


def test_the_skill_and_instruction_are_pointed_at_not_pasted_in():
    text = bench._prompt_for("task_instruction_skill", TASK, "",
                             TASK["detailed_instruction"], "ahu-fdd-helper")
    assert "DETAILED_INSTRUCTION.md" in text
    assert "skills/ahu-fdd-helper/" in text
    # The procedure is staged on disk, not inlined into the prompt.
    assert "SECRET" not in text


def test_an_instance_is_named_in_the_prompt():
    text = bench._prompt_for("task", TASK, "library", "", "")
    assert "library" in text


# ═══════════════════════════════════════════════════════════════════════════
#  The fingerprint
# ═══════════════════════════════════════════════════════════════════════════

def test_the_fingerprint_changes_with_anything_that_must_be_constant():
    base = bench.env_fingerprint("m", "h", {"wall_clock_s": 900}, "td")
    assert base != bench.env_fingerprint("other", "h", {"wall_clock_s": 900}, "td")
    assert base != bench.env_fingerprint("m", "other", {"wall_clock_s": 900}, "td")
    assert base != bench.env_fingerprint("m", "h", {"wall_clock_s": 60}, "td")
    assert base != bench.env_fingerprint("m", "h", {"wall_clock_s": 900}, "other")
    assert base == bench.env_fingerprint("m", "h", {"wall_clock_s": 900}, "td")


# ═══════════════════════════════════════════════════════════════════════════
#  Evaluation
# ═══════════════════════════════════════════════════════════════════════════

def _workspace(tmp_path, files: dict) -> Path:
    ws = tmp_path / "ws"
    (ws / "outputs").mkdir(parents=True)
    for name, body in files.items():
        p = ws / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return ws


def test_an_empty_workspace_scores_zero(tmp_path):
    ev = bench.evaluate_workspace(_workspace(tmp_path, {}), TASK)
    assert ev.score == 0.0 and ev.passed is False
    assert ev.metric_name == "deliverable_contract"


def test_every_deliverable_present_scores_full(tmp_path):
    ws = _workspace(tmp_path, {
        "outputs/faults.csv": "fault_id,start,end,severity\nF1,a,b,1\n",
        "outputs/memo.md": "# ranked\n"})
    ev = bench.evaluate_workspace(ws, TASK)
    assert ev.score == 1.0 and ev.passed is True


def test_a_missing_column_costs_half_of_that_deliverable(tmp_path):
    ws = _workspace(tmp_path, {
        "outputs/faults.csv": "fault_id,start\nF1,a\n",
        "outputs/memo.md": "# ranked\n"})
    ev = bench.evaluate_workspace(ws, TASK)
    assert 0.0 < ev.criteria["outputs/faults.csv"] < 1.0
    assert "columns matched" in ev.evidence["outputs/faults.csv"]


def test_an_empty_file_does_not_count_as_produced(tmp_path):
    ws = _workspace(tmp_path, {"outputs/faults.csv": "", "outputs/memo.md": "x"})
    ev = bench.evaluate_workspace(ws, TASK)
    assert ev.criteria["outputs/faults.csv"] == 0.0
    assert ev.evidence["outputs/faults.csv"] == "produced but empty"


def test_a_task_with_no_named_deliverables_falls_back_and_says_so(tmp_path):
    task = {**TASK, "deliverables": [{"path": "", "description": "a CSV of faults"}]}
    ws = _workspace(tmp_path, {"outputs/anything.csv": "a,b\n1,2\n"})
    ev = bench.evaluate_workspace(ws, task)
    assert ev.metric_name == "outputs_produced"
    assert ev.score == 1.0


def test_column_hints_are_read_out_of_the_description():
    assert bench._columns_from("columns: fault_id, start (ISO), severity (1-5)") == [
        "fault_id", "start", "severity"]
    assert bench._columns_from("just some prose") == []


# ═══════════════════════════════════════════════════════════════════════════
#  Agents
# ═══════════════════════════════════════════════════════════════════════════

def test_the_dry_run_agent_produces_no_work(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    result = bench.DryRunAgent().run(ws, "do the thing")
    assert result.ok
    assert (ws / "PROMPT.md").read_text(encoding="utf-8") == "do the thing"
    # It scores zero against a real contract, which is the point of a dry run.
    assert bench.evaluate_workspace(ws, TASK).score == 0.0


def test_the_command_agent_runs_in_the_workspace_and_gets_the_prompt(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    script = tmp_path / "agent.py"
    script.write_text(
        "import os, pathlib\n"
        "pathlib.Path('outputs').mkdir(exist_ok=True)\n"
        "pathlib.Path('outputs/echo.txt').write_text(os.environ['BUILDRIX_PROMPT'])\n",
        encoding="utf-8")
    import sys
    agent = bench.CommandAgent(f'"{sys.executable}" "{script}"', timeout_s=60)
    result = agent.run(ws, "the prompt")
    assert result.ok, result.error
    assert (ws / "outputs" / "echo.txt").read_text(encoding="utf-8") == "the prompt"


def test_a_failing_agent_is_reported_not_raised(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    result = bench.CommandAgent("exit 3", timeout_s=30).run(ws, "x")
    assert result.ok is False and "exited 3" in result.error


# ═══════════════════════════════════════════════════════════════════════════
#  Progress
# ═══════════════════════════════════════════════════════════════════════════

def test_progress_logs_one_line_per_change_when_not_a_tty(capsys):
    p = bench.Progress(4, enabled=False)
    p.update(task="BXT-1", condition="task", done=0)
    p.update(task="BXT-1", condition="task", done=0)      # nothing changed
    p.update(condition="task_skill", done=1)
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 2
    assert "[0/4]" in out[0] and "Agent" in out[0]
    assert "[1/4]" in out[1] and "+ Skill" in out[1]
