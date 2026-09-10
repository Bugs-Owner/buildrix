"""
The paired benchmark runner.
============================

Heavy work runs here, on the contributor's machine; grading and record-keeping
happen on the hub. That split is what lets the benchmark carry EnergyPlus-years
of compute on a small server without ever letting the reference answers leave it.

Four conditions per Task instance
---------------------------------
    task                     Agent + Task
    task_instruction         Agent + Task + Detailed Instruction
    task_skill               Agent + Task + Skill
    task_instruction_skill   Agent + Task + Detailed Instruction + Skill

Everything else is held identical and *asserted* identical: same agent and
model, same Task and instance, same environment, same inputs, same
reproducibility settings, same budget. The only declared difference between two
conditions is which of the Skill and the Detailed Instruction was staged.

Isolation
---------
Each condition gets its own freshly created workspace directory, populated from
the Task package and torn down afterwards. Nothing is shared: not files, not
caches, not the agent's context, and not skill-written state such as a NOTES.md,
which would otherwise carry learning from one condition into the next. The
runner hashes each workspace after the run and refuses to submit a group whose
conditions all produced the same digest, because that would mean they were not
isolated at all.

Automatic submission
--------------------
There is no `benchmark submit`. When the local run finishes, the group uploads.
A contributor who could choose which runs to send would send the flattering
ones, and a leaderboard built from self-selected results measures nothing. The
honest path is the only path.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from buildrix.hub_api import ApiError, BuildrixAPI
from buildrix.interactive import C, para, rule

CONDITIONS = [
    "task", "task_instruction", "task_skill", "task_instruction_skill",
]

CONDITION_LABELS = {
    "task":                   "Agent",
    "task_instruction":       "+ Detailed Instruction",
    "task_skill":             "+ Skill",
    "task_instruction_skill": "+ Instruction + Skill",
}

RUNNER_VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════
#  Progress
# ═══════════════════════════════════════════════════════════════════════════

class Progress:
    """A live bar the contributor can read at a glance.

    Shows the four things someone actually wants to know: how far through, how
    many runs are done, which Task and instance is running, and which condition.
    """

    def __init__(self, total: int, enabled: bool = True):
        self.total = max(1, total)
        self.done = 0
        self.enabled = enabled and sys.stdout.isatty()
        self.task = ""
        self.instance = ""
        self.condition = ""
        self._lines = 0
        self._last_logged: tuple | None = None

    def update(self, *, task: str = "", instance: str = "", condition: str = "",
               done: int | None = None) -> None:
        if task:      self.task = task
        if instance is not None and instance != "":
            self.instance = instance
        if condition: self.condition = condition
        if done is not None:
            self.done = done
        self.render()

    def tick(self) -> None:
        self.done += 1
        self.render()

    def render(self) -> None:
        pct = min(100, round(100 * self.done / self.total))
        filled = round(20 * self.done / self.total)
        bar = "█" * filled + "░" * (20 - filled)
        where = self.instance or "default"
        current = f"{where} — {CONDITION_LABELS.get(self.condition, self.condition)}"
        block = [
            f"Benchmarking {C.cyan(self.task)}",
            f"{bar} {pct}%",
            "",
            f"{self.done} / {self.total} runs completed",
            f"Current: {current}",
        ]
        if not self.enabled:
            # No cursor control: log one line per actual change, not per field.
            key = (self.done, self.task, self.instance, self.condition)
            if key == self._last_logged:
                return
            self._last_logged = key
            print(f"  [{self.done}/{self.total}] {self.task} · {current}")
            return
        if self._lines:
            sys.stdout.write(f"\033[{self._lines}A")
        for line in block:
            sys.stdout.write("\033[2K  " + line + "\n")
        sys.stdout.flush()
        self._lines = len(block)

    def finish(self) -> None:
        if self.enabled and self._lines:
            sys.stdout.write("\n")
            sys.stdout.flush()
        self._lines = 0


# ═══════════════════════════════════════════════════════════════════════════
#  Fingerprints and digests
# ═══════════════════════════════════════════════════════════════════════════

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_dir(path: Path) -> str:
    """A stable digest over a directory's contents.

    Used to prove two conditions did not share a workspace. Paths are relative
    and sorted so the digest depends on content, not on walk order.
    """
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_dir() or _skip(p):
            continue
        h.update(p.relative_to(path).as_posix().encode())
        try:
            h.update(p.read_bytes())
        except OSError:
            h.update(b"<unreadable>")
    return h.hexdigest()


def _skip(p: Path) -> bool:
    parts = set(p.parts)
    return bool(parts & {"__pycache__", ".git", ".pytest_cache", ".venv"})


def digest_path(path: Path) -> str:
    """Digest a Skill folder or archive — the identity of what was benchmarked."""
    if path.is_dir():
        return digest_dir(path)
    return sha256_bytes(path.read_bytes())


def env_fingerprint(model: str, harness: str, budget: dict,
                    task_digest: str) -> str:
    """Everything that must be identical across the four conditions.

    Deliberately excludes the Skill and the Detailed Instruction — those are
    the declared differences. If anything else varies, the fingerprints differ
    and the hub rejects the group.
    """
    blob = json.dumps({
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "model": model,
        "harness": harness,
        "budget": budget,
        "task_digest": task_digest,
        "runner": RUNNER_VERSION,
    }, sort_keys=True)
    return sha256_bytes(blob.encode())


# ═══════════════════════════════════════════════════════════════════════════
#  Agent adapters
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AgentResult:
    ok: bool
    transcript: str = ""
    wall_clock_s: float = 0.0
    tokens: int = 0
    tool_calls: int = 0
    error: str = ""


class CommandAgent:
    """Runs an agent as a subprocess inside the workspace.

    The command is a template the contributor supplies, so Buildrix does not
    have to know about every harness:

        buildrix benchmark run --skill ./s --task T018 \\
            --agent 'claude -p "$BUILDRIX_PROMPT"' --model claude-opus-5

    The prompt reaches the command as ``$BUILDRIX_PROMPT`` and as the file
    ``PROMPT.md`` in the workspace, so both styles of harness work. The command
    runs with the workspace as its working directory and inherits nothing from
    the previous condition.
    """

    def __init__(self, command: str, timeout_s: int = 1800):
        self.command = command
        self.timeout_s = timeout_s

    def run(self, workspace: Path, prompt: str) -> AgentResult:
        (workspace / "PROMPT.md").write_text(prompt, encoding="utf-8")
        env = os.environ.copy()
        env["BUILDRIX_PROMPT"] = prompt
        env["BUILDRIX_WORKSPACE"] = str(workspace)
        started = time.time()
        try:
            proc = subprocess.run(
                self.command, shell=True, cwd=workspace, env=env,
                capture_output=True, text=True, timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            return AgentResult(False, wall_clock_s=time.time() - started,
                               error=f"The agent exceeded {self.timeout_s}s.")
        except OSError as e:
            return AgentResult(False, error=f"Could not start the agent: {e}")
        transcript = (proc.stdout or "") + (proc.stderr or "")
        return AgentResult(
            ok=proc.returncode == 0, transcript=transcript,
            wall_clock_s=round(time.time() - started, 2),
            error="" if proc.returncode == 0
                  else f"The agent exited {proc.returncode}.")


class DryRunAgent:
    """Stands in for an agent so the pipeline can be exercised without one.

    It produces no deliverables, so every condition scores zero. That is the
    point: it proves the isolation, the evaluation and the upload work, and it
    never pretends to be a measurement — a dry-run group is marked private.
    """

    def run(self, workspace: Path, prompt: str) -> AgentResult:
        (workspace / "PROMPT.md").write_text(prompt, encoding="utf-8")
        (workspace / "outputs").mkdir(exist_ok=True)
        (workspace / "outputs" / "dry-run.txt").write_text(
            "No agent was configured; this run produced no work.\n",
            encoding="utf-8")
        return AgentResult(True, transcript="(dry run)", wall_clock_s=0.0)


# ═══════════════════════════════════════════════════════════════════════════
#  Evaluation
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Evaluation:
    score: float
    metric_value: Optional[float]
    passed: bool
    criteria: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    metric_name: str = "deliverables_present"


def evaluate_workspace(workspace: Path, task: dict) -> Evaluation:
    """Contract check over a workspace. The offline fallback for grading.

    Grading proper happens on the hub, against the hidden reference. This only
    checks what the public package can settle — that each declared deliverable
    exists, is non-empty, and carries the columns the Task asked for — and it
    cannot tell a correct answer from a well-formatted wrong one. It stands in
    when the hub is unreachable, and the record says so.
    """
    return evaluate_workspace_artifacts(task, _artifact_list(workspace))


def evaluate_workspace_artifacts(task: dict, artifacts: list[dict]) -> Evaluation:
    """The same contract check, over already-collected artifacts."""
    deliverables = task.get("deliverables") or []
    named = [d for d in deliverables if (d.get("path") or "").strip()]
    by_path = {a.get("path", ""): a for a in artifacts}
    by_name = {a.get("path", "").split("/")[-1]: a for a in artifacts}
    criteria: dict = {}
    evidence: dict = {}

    if not named:
        produced = [a for a in artifacts
                    if a.get("path", "").split("/")[-1] != "PROMPT.md"]
        score = 1.0 if produced else 0.0
        return Evaluation(
            score=score, metric_value=float(len(produced)), passed=bool(produced),
            criteria={"produced_any_output": score},
            evidence={"files": [a["path"] for a in produced[:10]]},
            metric_name="outputs_produced")

    for d in named:
        rel = d["path"].strip().lstrip("/")
        hit = by_path.get(rel) or by_name.get(rel.split("/")[-1])
        if not hit:
            criteria[rel] = 0.0
            evidence[rel] = "not produced"
            continue
        size = int(hit.get("bytes") or 0)
        if size == 0:
            criteria[rel] = 0.0
            evidence[rel] = "produced but empty"
            continue
        wanted = _columns_from(d.get("description", ""))
        if wanted and rel.lower().endswith(".csv"):
            head = (hit.get("head") or "").splitlines()
            header = {_normal(c) for c in (head[0].replace(";", ",").split(",")
                                           if head else [])}
            matched = [c for c in wanted if _normal(c) in header]
            criteria[rel] = round(0.5 + 0.5 * len(matched) / len(wanted), 3)
            evidence[rel] = (f"{size} bytes; columns matched "
                             f"{len(matched)}/{len(wanted)}")
        else:
            criteria[rel] = 1.0
            evidence[rel] = f"{size} bytes"

    score = round(sum(criteria.values()) / len(criteria), 4) if criteria else 0.0
    return Evaluation(
        score=score, metric_value=score, passed=score >= 0.75,
        criteria=criteria, evidence=evidence,
        metric_name="deliverable_contract")


_COLUMN_HINT = ("columns:", "columns", "with columns")


def _columns_from(description: str) -> list[str]:
    text = (description or "").lower()
    for hint in _COLUMN_HINT:
        if hint in text:
            tail = text.split(hint, 1)[1]
            parts = [p.strip(" .()[]") for p in tail.replace(";", ",").split(",")]
            return [p.split(" ")[0] for p in parts if p and len(p) < 40][:12]
    return []


def _normal(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _read_header(path: Path) -> set[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            line = fh.readline()
    except OSError:
        return set()
    return {_normal(c) for c in line.replace(";", ",").split(",")}


# ═══════════════════════════════════════════════════════════════════════════
#  The run
# ═══════════════════════════════════════════════════════════════════════════

def _grade(api: BuildrixAPI, task: dict, artifacts: list[dict],
           instance: str) -> Evaluation:
    """Ask the hub to grade one condition's artifacts.

    Grading is the hub's job because the reference answer only exists there.
    When the hub cannot be reached the local contract check stands in, and the
    record says which grader produced the score — a run graded two different
    ways should never look like one graded consistently.
    """
    try:
        out = api.benchmark_grade({
            "task_id":      task.get("id", ""),
            "task_code":    task.get("task_code", ""),
            "instance_key": instance,
            "artifacts":    artifacts,
        })
    except ApiError as e:
        local = evaluate_workspace_artifacts(task, artifacts)
        local.evidence = {**local.evidence,
                          "_grader": f"local fallback; the hub could not grade "
                                     f"this run ({e})"}
        return local

    return Evaluation(
        score=float(out.get("score") or 0.0),
        metric_value=out.get("metric_value"),
        passed=bool(out.get("passed")),
        criteria=out.get("criteria") or {},
        evidence={**(out.get("evidence") or {}),
                  "_grader": out.get("grader", ""),
                  "_notes": out.get("notes", "")},
        metric_name=out.get("metric_name", "buildrix_rubric"),
    )


@dataclass
class RunPlan:
    task: dict
    package: bytes
    instances: list[str]


def prepare_task(api: BuildrixAPI, ref: str) -> RunPlan:
    task = api.task_show(ref)
    package = api.task_package(ref)
    instances = [i.get("key") or i.get("label") or ""
                 for i in (task.get("instances") or [])] or [""]
    return RunPlan(task=task, package=package, instances=instances)


def _stage(workspace: Path, package: bytes, condition: str,
           skill_path: Optional[Path], detailed_instruction: str) -> None:
    """Build one condition's workspace from scratch.

    The Task's public half always goes in. The Skill goes in only for the
    conditions that declare it, and the Detailed Instruction likewise — those
    two are the entire difference between the four runs.
    """
    with zipfile.ZipFile(io.BytesIO(package)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = Path(info.filename).parts[1:]     # drop the slug folder
            if not parts or ".." in parts:
                continue
            dest = workspace.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(info))

    (workspace / "outputs").mkdir(exist_ok=True)

    if "skill" in condition and skill_path:
        target = workspace / "skills" / skill_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if skill_path.is_dir():
            shutil.copytree(skill_path, target,
                            ignore=shutil.ignore_patterns(
                                "__pycache__", ".git", "*.pyc"))
        else:
            with zipfile.ZipFile(skill_path) as z:
                z.extractall(target)

    if "instruction" in condition and detailed_instruction:
        (workspace / "DETAILED_INSTRUCTION.md").write_text(
            detailed_instruction, encoding="utf-8")


def _prompt_for(condition: str, task: dict, instance: str,
                detailed_instruction: str, skill_name: str) -> str:
    """The natural-language input for one condition.

    The canonical prompt is identical in all four. What changes is the pointer
    to the extra material staged on disk — never the Task itself, or the
    conditions would not be comparable.
    """
    parts = [task.get("canonical_prompt") or ""]
    if instance:
        parts.append(f"Run this task for instance: {instance}.")
    parts.append("Your working directory is the task workspace. Write every "
                 "deliverable under outputs/.")
    if "instruction" in condition and detailed_instruction:
        parts.append("A detailed procedure written by an experienced engineer is "
                     "in DETAILED_INSTRUCTION.md. Read it before you start.")
    if "skill" in condition and skill_name:
        parts.append(f"A reusable Skill is available at skills/{skill_name}/. "
                     f"Read its SKILL.md and follow it where it applies.")
    return "\n\n".join(p for p in parts if p.strip())


def run_benchmark(
    api: BuildrixAPI,
    *,
    skill_path: Optional[Path],
    skill_name: str,
    skill_version: str,
    task_refs: list[str],
    agent,
    model: str,
    harness: str = "",
    budget: Optional[dict] = None,
    visibility: str = "public",
    on_result: Optional[Callable[[dict], None]] = None,
) -> list[dict]:
    """Run every condition for every Task, then upload each group.

    Returns the hub's response for each Task. A Task whose upload is rejected
    still returns — the contributor needs to see why, and no result is silently
    dropped.
    """
    budget = budget or {"wall_clock_s": 1800}
    skill_digest = digest_path(skill_path) if skill_path else ""

    plans = []
    for ref in task_refs:
        try:
            plans.append(prepare_task(api, ref))
        except ApiError as e:
            print(C.red(f"  {ref}: {e}"))
    if not plans:
        return []

    total = sum(len(p.instances) * len(CONDITIONS) for p in plans)
    progress = Progress(total)
    submitted: list[dict] = []
    done = 0

    for plan in plans:
        task = plan.task
        code = task.get("task_code") or task.get("id")
        task_digest = sha256_bytes(plan.package)
        fingerprint = env_fingerprint(model, harness, budget, task_digest)
        detailed = task.get("detailed_instruction") or ""

        records: list[dict] = []
        for instance in plan.instances:
            for condition in CONDITIONS:
                progress.update(task=code, instance=instance,
                                condition=condition, done=done)
                # A fresh directory per condition. Nothing survives the loop:
                # no files, no caches, no skill-written state.
                workspace = Path(tempfile.mkdtemp(prefix="buildrix-run-"))
                try:
                    _stage(workspace, plan.package, condition,
                           skill_path, detailed)
                    prompt = _prompt_for(condition, task, instance,
                                         detailed, skill_name)
                    result = agent.run(workspace, prompt)
                    artifacts = _artifact_list(workspace)
                    ev = _grade(api, task, artifacts, instance)
                    records.append({
                        "condition": condition,
                        "instance_key": instance,
                        "trial": 1,
                        "score": ev.score,
                        "metric_value": ev.metric_value,
                        "passed": ev.passed,
                        "criteria": ev.criteria,
                        "evidence": ev.evidence,
                        "workspace_digest": digest_dir(workspace),
                        "transcript_digest": sha256_bytes(
                            result.transcript.encode("utf-8", "replace")),
                        "artifacts": [
                            {k: v for k, v in a.items() if k != "head"}
                            for a in artifacts],
                        "wall_clock_s": result.wall_clock_s,
                        "tokens": result.tokens,
                        "tool_calls": result.tool_calls,
                        "error": result.error,
                        "_metric_name": ev.metric_name,
                    })
                finally:
                    shutil.rmtree(workspace, ignore_errors=True)
                done += 1
                progress.update(done=done)

        # The evaluator says which metric it produced. Guessing here would
        # mislabel a fallback score as a deliverable-contract score.
        metric_name = records[0].pop("_metric_name", "score") if records else "score"
        for r in records:
            r.pop("_metric_name", None)
        group = {
            "skill_name": skill_name or "(none)",
            "skill_version": skill_version,
            "skill_digest": skill_digest or "none",
            "task_id": task.get("id", ""),
            "task_code": task.get("task_code", ""),
            "task_version": task.get("version", "1.0.0"),
            "task_digest": task_digest,
            "model": model,
            "harness": harness,
            "evaluator_version": RUNNER_VERSION,
            "buildrix_version": _buildrix_version(),
            "env_fingerprint": fingerprint,
            "environment": {
                "os": platform.system(), "release": platform.release(),
                "python": platform.python_version(),
            },
            "run_config": {"budget": budget, "conditions": CONDITIONS,
                           "instances": plan.instances},
            "metric_name": metric_name,
            "visibility": visibility,
            "records": records,
        }
        try:
            nonce = api.benchmark_nonce(skill_name or "", [code]).get("nonce", "")
            group["nonce"] = nonce
        except ApiError:
            group["nonce"] = ""

        try:
            response = api.benchmark_submit(group)
            submitted.append(response)
            if on_result:
                on_result(response)
        except ApiError as e:
            progress.finish()
            print(C.red(f"\n  {code}: the hub rejected this run — {e}"))
            submitted.append({"task_code": code, "error": str(e)})

    progress.finish()
    return submitted


#: How much of each text file travels to the hub for grading. Enough for a CSV
#: header, a summary or a short memo; nowhere near enough for a simulation
#: directory to cross the wire.
ARTIFACT_HEAD_BYTES = 8000

_READABLE = {".csv", ".md", ".txt", ".json", ".yaml", ".yml", ".tsv", ".log", ".py"}


def _artifact_list(workspace: Path) -> list[dict]:
    """What the agent produced, with a readable slice of each text file.

    The slice is what lets the hub grade content rather than only presence. The
    sha256 is over the whole file, so what was graded is still pinned to what
    was produced.
    """
    out = []
    outputs = workspace / "outputs"
    if not outputs.is_dir():
        return out
    for p in sorted(outputs.rglob("*")):
        if not p.is_file() or _skip(p):
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        head = ""
        if p.suffix.lower() in _READABLE:
            head = data[:ARTIFACT_HEAD_BYTES].decode("utf-8", errors="replace")
        out.append({"path": p.relative_to(workspace).as_posix(),
                    "bytes": len(data), "sha256": sha256_bytes(data)[:16],
                    "head": head})
    return out[:40]


def _buildrix_version() -> str:
    try:
        from buildrix import __version__
        return str(__version__)
    except Exception:
        return "0.0.0"


# ═══════════════════════════════════════════════════════════════════════════
#  Reporting
# ═══════════════════════════════════════════════════════════════════════════

def print_result(response: dict) -> None:
    """The table that lands at the end of a run."""
    if response.get("error"):
        return
    rule(f"benchmark complete · {response.get('task_code', '')}")
    metric = response.get("metric_name", "score")
    print(C.dim(f"  metric: {metric}\n"))
    for cond in response.get("conditions") or []:
        score = cond.get("score")
        shown = "—" if score is None else f"{round(score * 100)}"
        print(f"  {cond['label']:<28} {C.bold(shown.rjust(3))}")
    print()
    for label, key in (("Instruction Lift", "instruction_lift"),
                       ("Skill Lift",       "skill_lift"),
                       ("Combined Lift",    "combined_lift")):
        v = response.get(key)
        if v is None:
            continue
        pts = round(v * 100)
        colour = C.green if pts > 0 else (C.red if pts < 0 else C.dim)
        print(f"  {label:<28} {colour(('+' if pts > 0 else '') + str(pts))}")
    print()
    para(C.dim("Scores are the Task's own evaluator, normalised so the lift "
               "between conditions is comparable across Tasks. The run has been "
               "recorded on the hub."))
