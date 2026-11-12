"""Frozen, resumable studies for local machines and cluster job arrays.

The bundle is an operator artifact. Only a single condition's inputs are staged
into an agent workspace; the study, other trials and reports stay outside it.

Time budgets belong to the study, not the task's contributor. A budget is the
time a run is expected to take; a run that keeps making progress is extended
up to a ceiling, a stalled one is stopped (rules in time_watch). Budgets are
set per task when the study is prepared, so every agent on a task gets the
same budget, extension rule and ceiling:

    time:
      default_s: 3600        # any task not listed below (`timeout_s` is the old name)
      tasks: {T018: 36000}   # explicit per-task budgets win
      reference:             # optional: factor x a reference run's wall time
        results: ./reference-results   # results dir of an earlier study, same machine
        model: claude-opus-5-5         # optional: only this agent's runs
        factor: 3
      min_s: 900             # budgets below this are raised to it
      extend: 0.5            # each extension, as a share of the budget
      ceiling: 4             # hard stop, as a multiple of the budget
      stall_s: 1200          # stop after this long with nothing happening

Each run records its budget, extensions, stop reason and the machine it ran on.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
import json
import math
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
    conditions = spec.get("conditions")
    if conditions is not None and (not conditions or len(set(conditions)) != len(conditions)
            or not set(conditions) <= set(bench.CONDITIONS[:2] + [bench.INITIAL])
            or (bench.INITIAL in conditions and len(conditions) > 1)):
        raise ValueError(f"conditions: distinct values from task, task_instruction; "
                         f"{bench.INITIAL} runs as its own study (it is graded but not uploaded)")
    budgets = _TimeBudgets(spec, manifest_path.parent)
    timeout = budgets.default
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
                if (not conditions or "task_instruction" in conditions) and not (
                        plan.task.get("detailed_instruction") or plan.knowledge):
                    raise ValueError(f"{ref} has no Human knowledge; revise the task first")
                if conditions and bench.INITIAL in conditions:
                    # The original request is visible to the task's author and admins only.
                    initial = (api.get(f"/tasks/{ref}") or {}).get("initial_request") or ""
                    if not initial.strip():
                        raise ValueError(f"{ref} has no original request on record (author/admin login needed)")
                    plan.task["initial_request"] = initial
                package_rel = f"tasks/{len(snapshots)}.zip"
                package_path = destination / package_rel
                package_path.parent.mkdir(exist_ok=True)
                package_path.write_bytes(plan.package)
                knowledge_rel = ""
                if plan.knowledge:
                    knowledge_rel = f"tasks/{len(snapshots)}-knowledge.zip"
                    (destination / knowledge_rel).write_bytes(plan.knowledge)
                snapshots[ref] = {"task": plan.task, "instances": plan.instances,
                    "package": package_rel, "package_digest": bench.sha256_bytes(plan.package),
                    "knowledge": knowledge_rel,
                    "knowledge_digest": bench.sha256_bytes(plan.knowledge) if plan.knowledge else ""}
            # One budget per task, decided before any agent runs: same for every agent.
            budget = budgets.for_task(ref, snapshots[ref]["task"]["task_code"])
            for agent in spec["agents"]:
                nonce = api.benchmark_nonce(skill_name, [snapshots[ref]["task"]["task_code"]])["nonce"]
                jobs.append({"id": f"job-{len(jobs):05d}", **snapshots[ref],
                    "time_budget": budget,
                    "agent": agent, "nonce": nonce, "skill": skill_rel,
                    "skill_name": skill_name, "skill_version": skill_version,
                    "skill_digest": skill_digest})
    if budgets.unused:
        raise ValueError("time.tasks names tasks that are not in this study: "
                         + ", ".join(sorted(budgets.unused)))
    study = {"schema": "buildrix-bundle/1", "protocol": 2, "trials": trials,
             "seed": spec.get("seed", 42), "timeout_s": timeout,
             "execution": execution, "jobs": jobs, "matches": matches,
             "conditions": conditions,
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


class _TimeBudgets:
    """The study's time budgets: per-task override, else reference run, else default."""

    def __init__(self, spec: dict, base: Path):
        time_spec = spec.get("time") or {}
        if "default_s" in time_spec and "timeout_s" in spec and time_spec["default_s"] != spec["timeout_s"]:
            raise ValueError("Set the default budget once: time.default_s (timeout_s is its old name)")
        self.default = time_spec.get("default_s", spec.get("timeout_s", 1800))
        self.overrides = dict(time_spec.get("tasks") or {})
        self.unused = set(self.overrides)
        self.min_s, self.stall_s = time_spec.get("min_s", 900), time_spec.get("stall_s", 1200)
        for value in [self.default, self.min_s, self.stall_s, *self.overrides.values()]:
            _check_seconds(value)
        self.extend, self.ceiling = time_spec.get("extend", 0.5), time_spec.get("ceiling", 4)
        for name, value, low in (("extend", self.extend, 0), ("ceiling", self.ceiling, 1)):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= low:
                raise ValueError(f"time.{name} must be a number above {low}")
        reference = time_spec.get("reference") or {}
        if reference and not reference.get("results"):
            raise ValueError("time.reference needs results: the reference run's results directory")
        self.factor = reference.get("factor", 3)
        if not isinstance(self.factor, (int, float)) or self.factor <= 0:
            raise ValueError("time.reference.factor must be a positive number")
        self.model = reference.get("model", "")
        self.reference = reference_wall_times(base / reference["results"], self.model) if reference else {}

    def for_task(self, ref: str, code: str) -> dict:
        budget = self._budget(ref, code)
        if budget["wall_clock_s"] < self.min_s:
            budget = {**budget, "wall_clock_s": self.min_s, "raised_from_s": budget["wall_clock_s"]}
        seconds = budget["wall_clock_s"]
        return {**budget, "extend_s": math.ceil(self.extend * seconds),
                "ceiling_s": math.ceil(self.ceiling * seconds), "stall_s": self.stall_s}

    def _budget(self, ref: str, code: str) -> dict:
        for key in (code, ref):
            if key in self.overrides:
                self.unused.discard(key)
                return {"wall_clock_s": self.overrides[key], "source": "task_override"}
        if code in self.reference:
            # Rounded up to whole minutes, so the brief states a clean number.
            seconds = 60 * math.ceil(self.factor * self.reference[code] / 60)
            return {"wall_clock_s": seconds, "source": "reference_run", "factor": self.factor,
                    "reference_wall_clock_s": self.reference[code],
                    **({"reference_model": self.model} if self.model else {})}
        return {"wall_clock_s": self.default, "source": "study_default"}


def _check_seconds(value):
    if type(value) is not int or value < 1:
        raise ValueError(f"A time budget must be a whole number of seconds, not {value!r}")


def reference_wall_times(results: Path, model: str = "") -> dict:
    """Longest completed wall time per task code in an earlier study's results.

    Run the reference agent on the study's machine first (with a generous
    budget), then point ``time.reference.results`` at that results directory.
    Runs that failed or were stopped are not a reference.
    """
    groups = sorted(results.glob("job-*/group.json"))
    if not groups:
        raise ValueError(f"No finished groups in reference results {results}")
    times = {}
    for path in groups:
        group = read_json(path)
        if model and group["model"] != model:
            continue
        for record in group["records"]:
            if record.get("status") == "completed" and record.get("wall_clock_s"):
                code = group["task_code"]
                times[code] = max(times.get(code, 0), record["wall_clock_s"])
    return times


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
              agent_factory=CLIAgent, retries=0) -> list[dict]:
    """Run this shard's jobs, skipping finished trials.

    retries: how many times a trial whose worker died mid-run is started again.
    0 keeps it as an "interrupted" record instead.
    """
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
                group = _run_job(bundle, study, job, directory, agent_factory, retries)
                write_json(directory / "group.json", group)
            if api:
                results.append(_sync_group(api, directory))
            else:
                results.append({"job": job["id"], "status": "awaiting_upload"})
            # A run the runner stopped is a measurement (graded on what it left), not an error.
            results[-1]["run_errors"] = sum(r.get("status") not in ("completed", "stopped")
                                            for r in group["records"])
    return results


def model_label(agent: dict) -> str:
    """Reported model name; the reasoning level is part of the compared system."""
    return agent["model"] + (f"@{agent['effort']}" if agent.get("effort") else "")


def _run_job(bundle: Path, study: dict, job: dict, directory: Path, factory, retries=0) -> dict:
    package = _snapshot_path(bundle, job["package"]).read_bytes()
    knowledge = _snapshot_path(bundle, job["knowledge"]).read_bytes() if job.get("knowledge") else b""
    skill = _snapshot_path(bundle, job["skill"]) if job["skill"] else None
    if bench.sha256_bytes(package) != job["package_digest"] or (
            knowledge and bench.sha256_bytes(knowledge) != job["knowledge_digest"]) or (
            skill and bench.digest_path(skill) != job["skill_digest"]):
        raise ValueError("A frozen task, Human knowledge or skill package changed")
    budget = job["time_budget"]
    agent = factory(**job["agent"], **study["execution"], timeout_s=budget["wall_clock_s"],
                    extend_s=budget["extend_s"], ceiling_s=budget["ceiling_s"], stall_s=budget["stall_s"])
    machine = bench.machine_info()
    conditions = study.get("conditions") or bench.conditions_for(skill)
    schedule = [(i, t, c) for i in job["instances"]
                for t in range(1, study["trials"] + 1) for c in conditions]
    random.Random(study["seed"]).shuffle(schedule)
    records = []
    for ordinal, (instance, trial, condition) in enumerate(schedule):
        record_dir = directory / f"record-{ordinal:05d}"
        record_dir.mkdir(exist_ok=True)
        record_path = record_dir / "record.json"
        attempt = 1
        if record_path.exists():
            record = read_json(record_path)
            attempt = record.get("attempt", 1)
            if record.get("status") == "started" and attempt <= retries:
                # The worker died mid-trial (preemption, node failure, time limit).
                # Keep its evidence and start the trial again from a fresh workspace.
                retired = directory / "retired" / f"{record_dir.name}-attempt{attempt}"
                retired.parent.mkdir(exist_ok=True)
                shutil.move(str(record_dir), str(retired))
                record_dir.mkdir()
                attempt += 1
            else:
                if record.get("status") == "started":
                    record.update(status="interrupted", error="Previous worker stopped; trial was not rerun")
                    write_json(record_path, record)
                records.append(record)
                continue
        print(f"{job['id']} [{ordinal+1}/{len(schedule)}] {condition} trial {trial}"
              + (f" (attempt {attempt})" if attempt > 1 else ""), flush=True)
        record = {"condition": condition, "instance_key": instance, "trial": trial,
                  "attempt": attempt,
                  "status": "started", "started_at": time.time(), "score": None,
                  "metric_value": None, "passed": False, "artifacts": [], "usage": {},
                  "error": "", "wall_clock_s": 0, "tokens": 0, "tool_calls": 0,
                  "time_budget_s": budget["wall_clock_s"], "time_budget_source": budget["source"],
                  "machine": machine}
        write_json(record_path, record)
        with tempfile.TemporaryDirectory(prefix="buildrix-trial-") as tmp:
            workspace = Path(tmp)
            try:
                bench._stage(workspace, package, condition, skill,
                             job["task"].get("detailed_instruction", ""), job["skill_name"],
                             knowledge)
                prompt = bench._prompt_for(condition, job["task"], instance,
                    job["task"].get("detailed_instruction", ""), job["skill_name"])
                # The clock starts now; the brief and the runner's watch agree.
                agent.clock_start = time.time()
                prompt += "\n\n" + bench.time_brief(budget["wall_clock_s"], agent.clock_start,
                                                      budget["ceiling_s"])
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
                # Outputs were archived above however the run ended.
                stopped = result.stop_reason not in ("", "exited")
                record.update(status="completed" if result.ok else "stopped" if stopped else "failed",
                    stop_reason=result.stop_reason or "exited", extensions=result.extensions,
                    time_notices=result.time_notices,
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
    machines = []  # usually one; more if a resumed job moved to another node
    for record in records:
        if record.get("machine") and record["machine"] not in machines:
            machines.append(record["machine"])
    config = {"protocol": 2, "trials": study["trials"], "seed": study["seed"],
              "conditions": conditions, "execution": study["execution"],
              "study_digest": study["digest"],
              "budget": {k: budget[k] for k in ("wall_clock_s", "extend_s", "ceiling_s", "stall_s")},
              "time_budget": budget, "machines": machines,
              "snapshot_digest": job["task"].get("snapshot_digest", ""),
              "job_id": job["id"], "hub_url": study["hub_url"]}
    _report(directory, records)
    return {"nonce": job["nonce"], "skill_name": job["skill_name"] or "(none)",
            "skill_version": job["skill_version"], "skill_digest": job["skill_digest"],
            "task_id": job["task"]["id"], "task_code": job["task"]["task_code"],
            "task_version": job["task"].get("version", ""), "task_digest": job["package_digest"],
            "model": model_label(job["agent"]), "harness": job["agent"]["provider"],
            "agent_version": ", ".join(sorted({r.get("agent_version", "") for r in records}))[:64],
            "buildrix_version": bench._buildrix_version(), "evaluator_version": "pending",
            "env_fingerprint": bench.env_fingerprint(model_label(job["agent"]), job["agent"]["provider"],
                {**config["budget"], "execution": study["execution"]}, job["package_digest"]),
            "run_config": config, "records": records, "visibility": study["visibility"]}


def _report(directory: Path, records: list[dict]):
    with (directory / "measurements.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["condition", "instance_key", "trial", "status", "stop_reason", "wall_clock_s",
                  "time_budget_s", "extensions", "error",
                  "input_tokens", "output_tokens", "cached_input_tokens", "cache_creation_tokens",
                  "total_tokens", "cost_usd", "cost_source", "tool_calls",
                  "score", "metric_value", "passed", "criteria"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({**record, **record.get("usage", {}),
                             "extensions": len(record.get("extensions", [])),
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
        if any(r["condition"] == bench.INITIAL for r in group["records"]):
            # The hub stores only its own condition set; keep the graded result here.
            response = {"status": "graded_local", "task_code": group["task_code"]}
            write_json(receipt_path, response)
            return response
        response = api.benchmark_submit(group)
        write_json(receipt_path, response)
        return response
    except ApiError as exc:
        error = {"status": "awaiting_upload", "error": str(exc)}
        write_json(directory / "upload-error.json", error)
        return error


def sync(output: Path, api, workers: int = 8) -> list[dict]:
    """Grade and upload every finished group, several at a time.

    Each group is one independent request chain to the hub, so groups run in
    parallel; the per-group lock keeps a second sync from touching the same one.
    """
    from concurrent.futures import ThreadPoolExecutor
    def one(path):
        with _job_lock(path.parent):
            return _sync_group(api, path.parent)
    paths = sorted(output.glob("job-*/group.json"))
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(one, paths))
    if not results:
        raise ValueError("No completed groups found in this output directory")
    return results
