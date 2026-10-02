"""Frozen, resumable studies for local machines and cluster job arrays.

The bundle is an operator artifact. Only a single condition's inputs are staged
into an agent workspace; the study, other trials and reports stay outside it.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
import json
import os
from pathlib import Path
import random
import shutil
import tempfile
import time
import zipfile

import yaml

from buildrix import bench
from buildrix.benchmark_agents import CLIAgent
from buildrix.hub_api import ApiError


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    # Windows scanners can briefly hold a just-written destination open.
    # Keep the previous checkpoint intact and retry the atomic replacement.
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(value) -> str:
    return bench.sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def prepare(manifest_path: Path, destination: Path, api) -> dict:
    spec = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema") != "buildrix-study/1":
        raise ValueError("Expected schema: buildrix-study/1")
    trials = spec.get("trials", 3)
    if type(trials) is not int or not 1 <= trials <= 100:
        raise ValueError("trials must be an integer between 1 and 100")
    if not spec.get("agents") or not spec.get("pairs"):
        raise ValueError("A study needs agents and task/skill pairs")
    execution = spec.get("execution") or {"backend": "native"}
    timeout = spec.get("timeout_s", 1800)
    for agent in spec["agents"]:
        CLIAgent(**agent, **execution, timeout_s=timeout)
    if execution.get("backend") == "docker" and "@sha256:" not in execution.get("image", ""):
        raise ValueError("Pin the Docker image by digest (image@sha256:...) for a repeatable study")
    if execution.get("backend") == "apptainer":
        image = (manifest_path.parent / execution["image"]).resolve()
        if not image.is_file():
            raise ValueError("Apptainer requires a local immutable SIF image")
        execution = {**execution, "image": str(image)}
    destination.mkdir(parents=True, exist_ok=False)
    snapshots, jobs = {}, []
    matches = []
    for pair_index, pair in enumerate(spec["pairs"]):
        skill = (manifest_path.parent / pair["skill"]).resolve() if pair.get("skill") else None
        skill_name, skill_version, skill_rel, skill_digest = "", "", "", "none"
        if skill:
            if destination.resolve().is_relative_to(skill.resolve()):
                raise ValueError("Place the study bundle outside the skill folder being copied")
            from buildrix.commands import _skill_payload_from_path
            payload = _skill_payload_from_path(skill)
            skill_name = payload.get("name") or skill.stem
            skill_version = payload.get("version", "")
            skill_rel = f"skills/{pair_index}" + (".zip" if skill.is_file() else "")
            target = destination / skill_rel
            target.parent.mkdir(exist_ok=True)
            if skill.is_dir():
                if any(p.is_symlink() for p in skill.rglob("*")):
                    raise ValueError("Skill snapshots cannot contain symbolic links")
                shutil.copytree(skill, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            else:
                shutil.copyfile(skill, target)
            skill_digest = bench.digest_path(target)
        refs = pair.get("tasks", [])
        if pair.get("match"):
            if not skill or refs:
                raise ValueError("Automatic matching requires a skill and no explicit tasks")
            match = api.benchmark_match({**payload, "limit": 50})
            matches.append({"pair": pair_index, **match})
            refs = [m.get("task_code") or m["task_id"] for m in match["matches"] if m["band"] == "strong"]
        if not refs:
            raise ValueError("No tasks selected; specify tasks or review the automatic matches")
        if len(refs) != len(set(refs)):
            raise ValueError("A pair lists the same task more than once")
        for ref in refs:
            if ref not in snapshots:
                plan = bench.prepare_task(api, ref)
                if not (plan.task.get("instruction_prompt") or plan.task.get("detailed_instruction")):
                    raise ValueError(f"{ref} has no instruction treatment; revise the task first")
                package_rel = f"tasks/{len(snapshots)}.zip"
                package_path = destination / package_rel
                package_path.parent.mkdir(exist_ok=True)
                package_path.write_bytes(plan.package)
                snapshots[ref] = {"task": plan.task, "instances": plan.instances,
                    "package": package_rel, "package_digest": bench.sha256_bytes(plan.package)}
            for agent in spec["agents"]:
                nonce = api.benchmark_nonce(skill_name, [snapshots[ref]["task"]["task_code"]])["nonce"]
                jobs.append({"id": f"job-{len(jobs):05d}", **snapshots[ref],
                    "agent": agent, "nonce": nonce, "skill": skill_rel,
                    "skill_name": skill_name, "skill_version": skill_version,
                    "skill_digest": skill_digest})
    study = {"schema": "buildrix-bundle/1", "protocol": 2, "trials": trials,
             "seed": spec.get("seed", 42), "timeout_s": timeout,
             "execution": execution, "jobs": jobs, "matches": matches,
             "hub_url": api.hub_url, "runner_version": bench.RUNNER_VERSION}
    study["visibility"] = spec.get("visibility", "public")
    if study["visibility"] not in ("public", "private"):
        raise ValueError("visibility must be public or private")
    if execution.get("backend") == "apptainer":
        import hashlib
        with Path(execution["image"]).open("rb") as source:
            study["image_digest"] = hashlib.file_digest(source, "sha256").hexdigest()
    study["digest"] = _digest(study)
    write_json(destination / "study.json", study)
    return study


@contextmanager
def _job_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a+b") as lock:
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            if not lock.read(1):
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def _load_study(bundle: Path) -> dict:
    study = read_json(bundle / "study.json")
    if study["digest"] != _digest({k: v for k, v in study.items() if k != "digest"}):
        raise ValueError("Study manifest changed after preparation")
    if study["runner_version"] != bench.RUNNER_VERSION:
        raise ValueError("Use the runner version that prepared this study")
    return study


def _snapshot_path(bundle: Path, relative: str) -> Path:
    path = (bundle / relative).resolve()
    if not path.is_relative_to(bundle.resolve()):
        raise ValueError("Snapshot path escapes the bundle")
    return path


def run_batch(bundle: Path, output: Path, *, api=None, shard_index=0, shard_count=1,
              agent_factory=CLIAgent) -> list[dict]:
    if not 0 <= shard_index < shard_count:
        raise ValueError("Require 0 <= shard-index < shard-count")
    study = _load_study(bundle)
    if study.get("image_digest"):
        import hashlib
        with Path(study["execution"]["image"]).open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != study["image_digest"]:
                raise ValueError("Apptainer image changed after preparation")
    results = []
    for index, job in enumerate(study["jobs"]):
        if index % shard_count != shard_index:
            continue
        directory = output / job["id"]
        with _job_lock(directory):
            marker = directory / "study-digest.json"
            if marker.exists() and read_json(marker) != study["digest"]:
                raise ValueError("Output directory belongs to a different study")
            write_json(marker, study["digest"])
            if (directory / "group.json").exists():
                group = read_json(directory / "group.json")
            else:
                group = _run_job(bundle, study, job, directory, agent_factory)
                write_json(directory / "group.json", group)
            if api:
                results.append(_sync_group(api, directory))
            else:
                results.append({"job": job["id"], "status": "awaiting_upload"})
            results[-1]["run_errors"] = sum(r.get("status") != "completed" for r in group["records"])
    return results


def _run_job(bundle: Path, study: dict, job: dict, directory: Path, factory) -> dict:
    package = _snapshot_path(bundle, job["package"]).read_bytes()
    skill = _snapshot_path(bundle, job["skill"]) if job["skill"] else None
    if bench.sha256_bytes(package) != job["package_digest"] or (
            skill and bench.digest_path(skill) != job["skill_digest"]):
        raise ValueError("A frozen task or skill package changed")
    agent = factory(**job["agent"], **study["execution"], timeout_s=study["timeout_s"])
    conditions = bench.conditions_for(skill)
    schedule = [(i, t, c) for i in job["instances"]
                for t in range(1, study["trials"] + 1) for c in conditions]
    random.Random(study["seed"]).shuffle(schedule)
    records = []
    for ordinal, (instance, trial, condition) in enumerate(schedule):
        record_dir = directory / f"record-{ordinal:05d}"
        record_dir.mkdir(exist_ok=True)
        record_path = record_dir / "record.json"
        if record_path.exists():
            record = read_json(record_path)
            if record.get("status") == "started":
                record.update(status="interrupted", error="Previous worker stopped; trial was not rerun")
                write_json(record_path, record)
            records.append(record)
            continue
        print(f"{job['id']} [{ordinal+1}/{len(schedule)}] {condition} trial {trial}", flush=True)
        record = {"condition": condition, "instance_key": instance, "trial": trial,
                  "status": "started", "started_at": time.time(), "score": None,
                  "metric_value": None, "passed": False, "artifacts": [], "usage": {},
                  "error": "", "wall_clock_s": 0, "tokens": 0, "tool_calls": 0}
        write_json(record_path, record)
        with tempfile.TemporaryDirectory(prefix="buildrix-trial-") as tmp:
            workspace = Path(tmp)
            try:
                bench._stage(workspace, package, condition, skill,
                             job["task"].get("detailed_instruction", ""), job["skill_name"])
                prompt = bench._prompt_for(condition, job["task"], instance,
                    job["task"].get("detailed_instruction", ""), job["skill_name"])
                (record_dir / "prompt.md").write_text(prompt, encoding="utf-8")
                agent.evidence_dir = record_dir
                result = agent.run(workspace, prompt)
                (record_dir / "transcript.jsonl").write_text(result.transcript, encoding="utf-8")
                (record_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
                artifacts = bench._artifact_list(workspace)
                with zipfile.ZipFile(record_dir / "outputs.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                    for path in sorted((workspace / "outputs").rglob("*")):
                        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(workspace):
                            archive.write(path, path.relative_to(workspace).as_posix())
                record.update(status="completed" if result.ok else "failed",
                    agent_version=result.agent_version,
                    artifacts=artifacts, usage=result.usage, wall_clock_s=result.wall_clock_s,
                    tokens=result.tokens, tool_calls=result.tool_calls, error=result.error,
                    workspace_digest=bench.digest_dir(workspace),
                    transcript_digest=bench.sha256_bytes(result.transcript.encode()),
                    prompt_digest=bench.sha256_bytes(prompt.encode()))
            except Exception as exc:
                record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        record["finished_at"] = time.time()
        write_json(record_path, record)
        records.append(record)
    budget = {"wall_clock_s": study["timeout_s"]}
    config = {"protocol": 2, "trials": study["trials"], "seed": study["seed"],
              "conditions": conditions, "execution": study["execution"],
              "study_digest": study["digest"], "budget": budget,
              "snapshot_digest": job["task"].get("snapshot_digest", ""),
              "job_id": job["id"], "hub_url": study["hub_url"]}
    _report(directory, records)
    return {"nonce": job["nonce"], "skill_name": job["skill_name"] or "(none)",
            "skill_version": job["skill_version"], "skill_digest": job["skill_digest"],
            "task_id": job["task"]["id"], "task_code": job["task"]["task_code"],
            "task_version": job["task"].get("version", ""), "task_digest": job["package_digest"],
            "model": job["agent"]["model"], "harness": job["agent"]["provider"],
            "agent_version": ", ".join(sorted({r.get("agent_version", "") for r in records}))[:64],
            "buildrix_version": bench._buildrix_version(), "evaluator_version": "pending",
            "env_fingerprint": bench.env_fingerprint(job["agent"]["model"],
                job["agent"]["provider"], {**budget, "execution": study["execution"]}, job["package_digest"]),
            "run_config": config, "records": records, "visibility": study["visibility"]}


def _report(directory: Path, records: list[dict]):
    with (directory / "measurements.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["condition", "instance_key", "trial", "status", "wall_clock_s", "error",
                  "input_tokens", "output_tokens", "cached_input_tokens", "cache_creation_tokens",
                  "total_tokens", "cost_usd", "cost_source", "tool_calls",
                  "score", "metric_value", "passed", "criteria"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({**record, **record.get("usage", {}),
                             "criteria": json.dumps(record.get("criteria", {}), sort_keys=True)})


def _sync_group(api, directory: Path) -> dict:
    receipt_path = directory / "upload.json"
    if receipt_path.exists():
        return read_json(receipt_path)
    group_path = directory / "group.json"
    group = read_json(group_path)
    if api.hub_url.rstrip("/") != group["run_config"]["hub_url"].rstrip("/"):
        raise ValueError("Upload must use the hub that registered this study")
    try:
        existing = api.get(f"/benchmark/receipts/{group['nonce']}")
        if existing.get("group_id"):
            write_json(receipt_path, existing)
            return existing
        for record in group["records"]:
            if record.get("grade_receipt"):
                continue
            graded = api.benchmark_grade({"task_id": group["task_id"],
                "snapshot_digest": group["run_config"].get("snapshot_digest", ""),
                "instance_key": record["instance_key"], "artifacts": record["artifacts"],
                "run": bench.run_measurements(record)})
            if not graded.get("receipt"):
                raise ApiError("Hub did not issue a grading receipt; result retained for retry")
            record.update({k: graded[k] for k in ("score", "metric_value", "passed", "criteria", "evidence") if k in graded})
            if graded.get("rubric"):
                record["evidence"] = {**record.get("evidence", {}), "_rubric": graded["rubric"]}
            record["grade_receipt"] = graded["receipt"]
            group["metric_name"] = graded.get("metric_name", "score")
            group["evaluator_version"] = graded.get("evaluator_version", "hub")
            group["run_config"]["grader"] = graded.get("grader", "hub")
            write_json(group_path, group)
        _report(directory, group["records"])
        response = api.benchmark_submit(group)
        write_json(receipt_path, response)
        return response
    except ApiError as exc:
        error = {"status": "awaiting_upload", "error": str(exc)}
        write_json(directory / "upload-error.json", error)
        return error


def sync(output: Path, api) -> list[dict]:
    results = []
    for path in sorted(output.glob("job-*/group.json")):
        with _job_lock(path.parent):
            results.append(_sync_group(api, path.parent))
    if not results:
        raise ValueError("No completed groups found in this output directory")
    return results
