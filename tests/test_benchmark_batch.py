import base64
import io
import json
from pathlib import Path
import zipfile

import pytest

from buildrix import bench, benchmark_batch as batch
from buildrix.benchmark_agents import CLIAgent, parse_usage


class Hub:
    hub_url = "https://hub.invalid"

    def __init__(self):
        self.registered = 0
        self.uploads = []

    def benchmark_task(self, ref):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("task/prompt.md", "Compute the answer")
            archive.writestr("task/inputs/data.txt", "2")
        data = stream.getvalue()
        return {"task": {"id": "id", "task_code": ref, "version": "1",
                "canonical_prompt": "Compute the answer", "detailed_instruction": "Multiply by two"},
                "package_base64": base64.b64encode(data).decode(),
                "package_sha256": bench.sha256_bytes(data)}

    def benchmark_nonce(self, skill, refs):
        self.registered += 1
        return {"nonce": str(self.registered)}

    def get(self, path):
        return {}

    def benchmark_grade(self, body):
        return {"receipt": "signed", "score": 0.5, "passed": False,
                "metric_name": "test", "evaluator_version": "test/1"}

    def benchmark_submit(self, group):
        self.uploads.append(group)
        return {"group_id": "g1", "status": "community_graded"}


class FakeAgent:
    calls = []

    def __init__(self, **kwargs):
        pass

    def run(self, workspace, prompt):
        assert not (workspace / "previous.txt").exists()
        (workspace / "previous.txt").write_text("private state")
        self.calls.append((str(workspace), prompt))
        (workspace / "outputs" / "answer.txt").write_text("4")
        return bench.AgentResult(True, transcript='{"type":"completed"}', usage={"cost_usd": None})


def prepared(tmp_path, trials=2):
    FakeAgent.calls = []
    manifest = tmp_path / "study.json"
    batch.write_json(manifest, {"schema": "buildrix-study/1", "trials": trials,
        "agents": [{"provider": "codex", "model": "fixed-model"}],
        "pairs": [{"tasks": ["T001"]}], "execution": {"backend": "native"}})
    hub = Hub()
    bundle = tmp_path / "bundle"
    batch.prepare(manifest, bundle, hub)
    return bundle, hub


def test_batch_freezes_registers_isolates_persists_and_resumes(tmp_path):
    bundle, hub = prepared(tmp_path)
    assert hub.registered == 1
    output = tmp_path / "results"
    result = batch.run_batch(bundle, output, api=hub, agent_factory=FakeAgent)
    assert result[0]["group_id"] == "g1"
    assert len(FakeAgent.calls) == 4
    assert len({path for path, _ in FakeAgent.calls}) == 4
    group = hub.uploads[0]
    assert {r["condition"] for r in group["records"]} == {"task", "task_instruction"}
    assert {r["trial"] for r in group["records"]} == {1, 2}
    assert len(list(output.rglob("outputs.zip"))) == 4
    assert len(list(output.rglob("transcript.jsonl"))) == 4
    batch.run_batch(bundle, output, api=hub, agent_factory=FakeAgent)
    assert len(FakeAgent.calls) == 4
    assert len(hub.uploads) == 1


def test_offline_run_then_sync_never_reruns_agents(tmp_path):
    bundle, hub = prepared(tmp_path, trials=1)
    output = tmp_path / "results"
    batch.run_batch(bundle, output, agent_factory=FakeAgent)
    assert not hub.uploads
    batch.sync(output, hub)
    assert len(hub.uploads) == 1 and len(FakeAgent.calls) == 2


def test_modified_snapshot_fails_before_starting_an_agent(tmp_path):
    bundle, hub = prepared(tmp_path)
    (bundle / "tasks/0.zip").write_bytes(b"different")
    with pytest.raises(ValueError, match="changed"):
        batch.run_batch(bundle, tmp_path / "results", agent_factory=FakeAgent)
    assert not FakeAgent.calls


def test_changed_manifest_is_rejected(tmp_path):
    bundle, hub = prepared(tmp_path)
    study = batch.read_json(bundle / "study.json")
    study["trials"] = 9
    batch.write_json(bundle / "study.json", study)
    with pytest.raises(ValueError, match="manifest changed"):
        batch.run_batch(bundle, tmp_path / "results", agent_factory=FakeAgent)


def test_resume_records_interrupted_attempt_instead_of_retrying(tmp_path):
    bundle, hub = prepared(tmp_path, trials=1)

    class Interrupted(FakeAgent):
        def run(self, workspace, prompt):
            raise KeyboardInterrupt()

    output = tmp_path / "results"
    with pytest.raises(KeyboardInterrupt):
        batch.run_batch(bundle, output, agent_factory=Interrupted)
    result = batch.run_batch(bundle, output, agent_factory=FakeAgent)
    records = batch.read_json(output / "job-00000/group.json")["records"]
    assert result[0]["run_errors"] == 1
    assert len(FakeAgent.calls) == 1
    assert sum(r["status"] == "interrupted" for r in records) == 1


def test_shards_partition_jobs(tmp_path):
    bundle, hub = prepared(tmp_path)
    assert batch.run_batch(bundle, tmp_path / "results", shard_index=1, shard_count=2,
                           agent_factory=FakeAgent) == []
    assert not FakeAgent.calls


def test_codex_usage_preserves_unknown_cost_and_counts_tokens_once():
    text = '\n'.join(json.dumps(event) for event in [
        {"type": "item.completed", "item": {"type": "command_execution"}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 20}}])
    result = parse_usage(text, "codex")
    assert result["total_tokens"] == 120
    assert result["cached_input_tokens"] == 60
    assert result["cost_usd"] is None
    assert result["tool_calls"] == 1


def test_claude_usage_uses_final_aggregate_including_cache():
    result = parse_usage(json.dumps({"type": "result", "usage": {
        "input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 50}, "total_cost_usd": 0.012}), "claude")
    assert result["total_tokens"] == 180 and result["cost_usd"] == 0.012
    assert parse_usage("no usage", "claude")["total_tokens"] is None


def test_adapter_clears_inherited_memory_config_and_hub_credentials(tmp_path, monkeypatch):
    import subprocess
    from types import SimpleNamespace
    captured = []
    monkeypatch.setenv("OPENAI_API_KEY", "provider-key")
    monkeypatch.setenv("BUILDRIX_TOKEN", "hub-secret")
    monkeypatch.setenv("CODEX_HOME", "personal-memory")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "other-provider-key")

    class Process:
        returncode = 0
        def __init__(self, command, **kwargs):
            captured.append(kwargs["env"])
            kwargs["stdout"].write(b'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":2}}\n')
        def communicate(self, prompt, timeout):
            pass

    monkeypatch.setattr(subprocess, "Popen", Process)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="codex-test", returncode=0))
    monkeypatch.setattr("shutil.which", lambda _: "codex")
    for _ in range(2):
        assert CLIAgent("codex", "fixed").run(tmp_path, "task").ok
    assert captured[0]["CODEX_HOME"] != captured[1]["CODEX_HOME"]
    assert "BUILDRIX_TOKEN" not in captured[0]
    assert "ANTHROPIC_API_KEY" not in captured[0]
    assert captured[0]["OPENAI_API_KEY"] == "provider-key"


def test_skill_archive_root_is_normalized_and_traversal_rejected(tmp_path):
    archive = tmp_path / "skill.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("root/SKILL.md", "skill")
    ws = tmp_path / "ws"
    ws.mkdir()
    package = base64.b64decode(Hub().benchmark_task("T")["package_base64"])
    bench._stage(ws, package, "task_skill", archive, "", "named")
    assert (ws / "skills/named/SKILL.md").read_text() == "skill"
    with zipfile.ZipFile(archive, "a") as z:
        z.writestr("root/../../outside.txt", "bad")
    with pytest.raises(ValueError, match="Unsafe"):
        bench._stage(ws, package, "task_skill", archive, "", "other")


@pytest.mark.parametrize("backend", ["docker", "apptainer"])
def test_container_mounts_only_current_workspace_and_excludes_hub_credentials(tmp_path, monkeypatch, backend):
    import subprocess
    from types import SimpleNamespace
    captured = []
    monkeypatch.setenv("ANTHROPIC_API_KEY", "provider-key")
    monkeypatch.setenv("BUILDRIX_TOKEN", "hub-secret")

    class Process:
        returncode = 0
        def __init__(self, command, **kwargs):
            captured.append((command, kwargs["env"]))
            kwargs["stdout"].write(b'{"type":"result","usage":{},"is_error":false}\n')
        def communicate(self, prompt, timeout):
            pass

    monkeypatch.setattr(subprocess, "Popen", Process)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    assert CLIAgent("claude", "fixed", backend=backend, image="image").run(tmp_path, "task").ok
    command, env = captured[0]
    assert "hub-secret" not in str(env) and "provider-key" not in str(command)
    assert sum(str(tmp_path) in part for part in command) == 1
    if backend == "apptainer":
        assert "--containall" in command and "--no-home" in command
        assert env["APPTAINERENV_ANTHROPIC_API_KEY"] == "provider-key"
    else:
        assert "--cpus" in command and "--memory" in command


def test_grading_outage_preserves_evidence_for_sync(tmp_path):
    from buildrix.hub_api import ApiError
    bundle, hub = prepared(tmp_path, trials=1)
    original = hub.benchmark_grade
    def unavailable(body):
        raise ApiError("offline")
    hub.benchmark_grade = unavailable
    output = tmp_path / "results"
    result = batch.run_batch(bundle, output, api=hub, agent_factory=FakeAgent)
    assert result[0]["status"] == "awaiting_upload"
    assert not hub.uploads
    hub.benchmark_grade = original
    assert batch.sync(output, hub)[0]["group_id"] == "g1"
    assert len(FakeAgent.calls) == 2
