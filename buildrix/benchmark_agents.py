"""Unattended CLI adapters. Session isolation and OS isolation are distinct.

Native execution resets homes and caches but is not a security boundary.
Docker/Apptainer run each condition with only that condition's workspace mounted.
Authentication uses provider API keys by default. ``auth: subscription`` (native
backend only) instead passes just the subscription login: CLAUDE_CODE_OAUTH_TOKEN
(from ``claude setup-token``) or a copy of ``~/.claude/.credentials.json`` for
Claude, and a copy of ``~/.codex/auth.json`` for Codex. No other personal configuration, skills or memory are inherited.

Time is watched by ``time_watch``: the budget is the expected time, a run that
makes progress is extended up to a ceiling, and a stalled one is stopped. A
stop is graceful (SIGTERM, ``docker stop`` for Docker, then a kill after a
grace period) and whatever the agent wrote to outputs/ is kept and graded.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time
import uuid

from buildrix.bench import AgentResult, _duration
from buildrix import time_watch
import re

RATE_LIMIT = re.compile(r"usage limit|rate limit|rate_limit|too many requests|hit your limit|"
                        r"limit reached|limit will reset|status 429|error 429|\"status\":429")
STOP_GRACE_S = 30    # between the polite stop and the kill


def parse_usage(transcript: str, provider: str) -> dict:
    usage: dict = {"input_tokens": None, "output_tokens": None,
                   "cached_input_tokens": None, "cache_creation_tokens": None,
                   "cost_usd": None, "cost_source": "unavailable", "tool_calls": 0}
    completed = False
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if provider == "codex":
            if kind == "turn.completed" and isinstance(event.get("usage"), dict):
                for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
                    value = event["usage"].get(key)
                    if isinstance(value, int) and value >= 0:
                        usage[key] = (usage[key] or 0) + value
                completed = True
            if kind == "item.completed" and (event.get("item") or {}).get("type") in (
                    "command_execution", "mcp_tool_call", "web_search", "file_change"):
                usage["tool_calls"] += 1
        else:
            if kind == "assistant":
                usage["tool_calls"] += sum(x.get("type") == "tool_use" for x in
                    (event.get("message") or {}).get("content", []) if isinstance(x, dict))
            if kind == "result":
                reported = event.get("usage") or {}
                for dest, src in (("input_tokens", "input_tokens"),
                                  ("output_tokens", "output_tokens"),
                                  ("cached_input_tokens", "cache_read_input_tokens"),
                                  ("cache_creation_tokens", "cache_creation_input_tokens")):
                    value = reported.get(src)
                    if isinstance(value, int) and value >= 0:
                        usage[dest] = value
                cost = event.get("total_cost_usd")
                if isinstance(cost, (float, int)) and cost >= 0:
                    usage.update(cost_usd=cost, cost_source="provider_reported")
                usage["model_usage"] = event.get("modelUsage") or {}
                usage["agent_error"] = bool(event.get("is_error"))
                completed = True
    # Anthropic input_tokens excludes cache reads/writes; Codex includes reads.
    inp, out = usage["input_tokens"], usage["output_tokens"]
    usage["total_tokens"] = None if inp is None or out is None else inp + out + (
        (usage["cached_input_tokens"] or 0) + (usage["cache_creation_tokens"] or 0)
        if provider == "claude" else 0)
    usage["completed_event"] = completed
    return usage


class CLIAgent:
    def __init__(self, provider: str, model: str, *, timeout_s: int = 1800,
                 backend: str = "native", image: str = "", cpus: int = 2,
                 memory_mb: int = 4096, effort: str = "", auth: str = "api_key",
                 extend_s: float = 0, ceiling_s: float = 0, stall_s: float = 1200):
        if provider not in ("codex", "claude") or not model or model == "unspecified":
            raise ValueError("Choose codex or claude and an explicit model ID.")
        if backend not in ("native", "docker", "apptainer"):
            raise ValueError("Unknown execution backend")
        if backend != "native" and not image:
            raise ValueError("Container execution requires an image.")
        if timeout_s < 1 or cpus < 1 or memory_mb < 128:
            raise ValueError("Execution limits must be positive.")
        self.provider, self.model = provider, model
        self.timeout_s, self.backend, self.image = timeout_s, backend, image
        self.cpus, self.memory_mb = cpus, memory_mb
        efforts = ("minimal", "low", "medium", "high", "xhigh") if provider == "codex" else (
            "low", "medium", "high", "xhigh", "max")
        if effort and effort not in efforts:
            raise ValueError(f"{provider} effort must be one of {', '.join(efforts)}")
        if auth not in ("api_key", "subscription"):
            raise ValueError("auth must be api_key or subscription")
        if auth == "subscription" and backend != "native":
            raise ValueError("Subscription auth is only supported with the native backend")
        self.effort, self.auth = effort, auth
        # timeout_s is the expected time; see time_watch for the other three.
        self.extend_s = extend_s or timeout_s / 2
        self.ceiling_s = max(ceiling_s or 4 * timeout_s, timeout_s)
        self.stall_s = stall_s
        self.evidence_dir: Path | None = None
        # Epoch second the next run's clock starts; the batch runner sets it so
        # the brief and the watch agree. Without it: when the run starts.
        self.clock_start: float | None = None

    def command(self) -> list[str]:
        if self.provider == "codex":
            return ["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
                    "--model", self.model] + (
                    ["-c", f'model_reasoning_effort="{self.effort}"'] if self.effort else []) + ["--sandbox",
                    "workspace-write" if self.backend == "native" else "danger-full-access",
                    "-"]
        args = ["claude", "-p", "--model", self.model, "--output-format", "stream-json",
                "--verbose", "--no-session-persistence", "--setting-sources", "",
                "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
        if self.effort:
            args += ["--effort", self.effort]
        if self.backend == "native":
            args += ["--permission-mode", "acceptEdits", "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep"]
        else:
            args += ["--dangerously-skip-permissions"]
        return args

    def run(self, workspace: Path, prompt: str) -> AgentResult:
        login_file = None  # subscription login copied into the fresh home
        if self.auth == "subscription":
            key = "CLAUDE_CODE_OAUTH_TOKEN"
            if not (self.provider == "claude" and os.environ.get(key)):
                login_file = self._login_file()
                if not login_file.is_file():
                    return AgentResult(False, error=f"No {self.provider} login at {login_file}; "
                                       f"run `{self.provider} login` (or set CLAUDE_CODE_OAUTH_TOKEN).")
        else:
            key = "OPENAI_API_KEY" if self.provider == "codex" else "ANTHROPIC_API_KEY"
            if not os.environ.get(key):
                return AgentResult(False, error=f"Set {key}; personal agent settings are not inherited.")
        workspace = workspace.resolve()
        started = time.monotonic()
        container_name = "buildrix-" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix="buildrix-agent-") as state:
            state_path = Path(state)
            # Only OS launch essentials and this provider credential cross over.
            env = {k: v for k, v in os.environ.items() if k.upper() in {
                "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL"}}
            if self.auth == "api_key" or (self.provider == "claude" and not login_file):
                env[key] = os.environ[key]
            if self.provider == "codex" and self.auth == "api_key":
                env["CODEX_API_KEY"] = env[key]
            runtime_home = str(state_path) if self.backend == "native" else "/tmp/buildrix-home"
            isolated = {"HOME": runtime_home, "USERPROFILE": runtime_home,
                "CODEX_HOME": runtime_home + "/.codex",
                "CLAUDE_CONFIG_DIR": runtime_home + "/.claude",
                "XDG_CONFIG_HOME": runtime_home + "/.config",
                "XDG_CACHE_HOME": runtime_home + "/.cache",
                "APPDATA": runtime_home + "/.config", "LOCALAPPDATA": runtime_home + "/.cache",
                "TMPDIR": runtime_home + "/tmp", "TMP": runtime_home + "/tmp",
                "TEMP": runtime_home + "/tmp", "PYTHONUTF8": "1",
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                "BASH_ENV": (workspace.as_posix() if self.backend == "native" else "/workspace")
                            + "/" + time_watch.BASH_FILE}
            start, self.clock_start = self.clock_start or time.time(), None
            (workspace / time_watch.BASH_FILE).write_text(time_watch.BASH_NOTICE,
                                                          encoding="utf-8", newline="\n")
            command = self.command()
            agent_version = ""
            if self.backend == "native":
                env.update(isolated)
                for value in isolated.values():
                    if value.startswith(runtime_home):
                        Path(value).mkdir(parents=True, exist_ok=True)
                if login_file:
                    shutil.copyfile(login_file, self._login_copy(isolated))
                executable = shutil.which(self.provider)
                if not executable:
                    return AgentResult(False, error=f"{self.provider} is not on PATH")
                command[0] = executable
                try:
                    version = subprocess.run([executable, "--version"], env=env,
                        capture_output=True, text=True, timeout=15)
                    agent_version = version.stdout.strip()[:200]
                except (OSError, subprocess.TimeoutExpired) as exc:
                    return AgentResult(False, error=f"Could not inspect CLI version: {exc}")
            else:
                # The image must have these empty home/tmp directories for its
                # non-root runner user. Nothing from the host home is mounted.
                if self.backend == "docker":
                    command = ["docker", "run", "--rm", "--init", "-i", "--name", container_name,
                        "--cpus", str(self.cpus), "--memory", f"{self.memory_mb}m",
                        "--pids-limit", "256", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges", "--workdir", "/workspace",
                        "--mount", f"type=bind,source={workspace},target=/workspace",
                        "-e", key] + (["-e", "CODEX_API_KEY"] if self.provider == "codex" else [])
                    command += [a for k, v in isolated.items() for a in ("-e", f"{k}={v}")]
                    if hasattr(os, "getuid"):
                        command += ["--user", f"{os.getuid()}:{os.getgid()}"]
                    command += [self.image] + self.command()
                else:
                    inherited = {**isolated, key: env[key]}
                    if self.provider == "codex":
                        inherited["CODEX_API_KEY"] = env[key]
                    env.update({"APPTAINERENV_" + k: v for k, v in inherited.items()})
                    command = ["apptainer", "exec", "--containall", "--cleanenv", "--no-home",
                        "--no-mount", "hostfs,bind-paths,cwd", "--no-eval",
                        "--writable-tmpfs", "--bind", f"{workspace}:/workspace",
                        "--pwd", "/workspace", self.image] + self.command()
                # Apptainer exec does not run an OCI ENTRYPOINT. Create its
                # scratch home explicitly in the container, with fixed code.
                inner = command[-len(self.command()):]
                command = command[:-len(inner)] + ["/bin/sh", "-c",
                    'mkdir -p "$HOME/tmp" "$CODEX_HOME" "$CLAUDE_CONFIG_DIR" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"; '
                    'printf "BUILDRIX_AGENT_VERSION=" >&2; "$1" --version >&2; exec "$@"',
                    "buildrix-agent"] + inner
            # Batch execution streams directly into durable evidence files, so
            # scheduler termination still leaves the events written so far.
            log_path = self.evidence_dir or state_path
            stdout_path, stderr_path = log_path / "transcript.jsonl", log_path / "stderr.txt"
            error = ""
            returncode = None
            reason, log = "", {"extensions": [], "notices": []}
            try:
                with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                    proc = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.PIPE,
                        stdout=stdout, stderr=stderr, start_new_session=os.name != "nt")
                    job = None
                    try:
                        if self.backend == "docker":
                            meter = {"cpu_busy": lambda: time_watch.docker_busy(container_name)}
                        elif os.name == "nt":
                            job = time_watch.WindowsJob(proc.pid)
                            meter = {"cpu_seconds": job.cpu_seconds}
                        else:  # the agent's session id is its pid (start_new_session)
                            meter = {"cpu_seconds": lambda: time_watch.session_cpu_seconds(proc.pid)}
                        activity = time_watch.Activity(workspace, [stdout_path, stderr_path], **meter)
                        reason = time_watch.watch(proc, prompt.encode(), workspace, activity, start,
                            self.timeout_s, self.extend_s, self.ceiling_s, self.stall_s, log)
                        if reason != "exited":
                            error = f"STOPPED ({reason}) after {_duration(time.time() - start)}"
                            self._stop(proc, container_name, STOP_GRACE_S, job)
                            time_watch.write_clock(workspace, f"status: STOPPED\nThe run was stopped ({reason}).\n")
                    except BaseException:
                        self._stop(proc, container_name, job=job)
                        raise
                    finally:
                        if job:
                            job.close()
                    returncode = proc.returncode
            except OSError as exc:
                error = f"Could not start agent: {exc}"
            finally:
                if self.backend == "docker":
                    try:
                        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=30)
                    except (OSError, subprocess.TimeoutExpired):
                        error = error or "Container cleanup failed; check Docker before resuming"
            if login_file:
                self._return_refreshed_login(self._login_copy(isolated), login_file)
            transcript = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
            if self.backend != "native":
                agent_version = next((line.split("=", 1)[1][:200] for line in stderr.splitlines()
                    if line.startswith("BUILDRIX_AGENT_VERSION=")), "")
            usage = parse_usage(transcript, self.provider)
            # Subscription caps are infrastructure failures, not model failures.
            limited = not error and (not usage["completed_event"] or usage.get("agent_error") or returncode)
            # Claude streams routine '"status":"allowed"' rate-limit events; ignore those.
            tail = "\n".join(line for line in transcript[-4000:].splitlines()
                              if '"rate_limit_event"' not in line or '"allowed"' not in line)
            if limited and RATE_LIMIT.search((tail + stderr[-4000:]).lower()):
                error = "RATE_LIMITED: provider usage limit reached; rerun this condition"
            ok = returncode == 0 and not error and not usage.get("agent_error") and usage["completed_event"]
            return AgentResult(ok, transcript=transcript, wall_clock_s=round(time.monotonic()-started, 3),
                tokens=usage["total_tokens"] or 0, tool_calls=usage["tool_calls"], usage=usage,
                error=error or ("" if ok else f"Agent failed or returned no completion event (exit {returncode})"),
                stderr=stderr, agent_version=agent_version, stop_reason=reason,
                extensions=log["extensions"], time_notices=log["notices"])

    def _login_file(self) -> Path:
        if self.provider == "codex":
            return Path(os.environ.get("CODEX_AUTH_FILE") or Path.home() / ".codex" / "auth.json")
        return Path(os.environ.get("CLAUDE_CREDENTIALS_FILE")
                    or Path.home() / ".claude" / ".credentials.json")

    def _login_copy(self, isolated: dict) -> Path:
        if self.provider == "codex":
            return Path(isolated["CODEX_HOME"]) / "auth.json"
        return Path(isolated["CLAUDE_CONFIG_DIR"]) / ".credentials.json"

    @staticmethod
    def _return_refreshed_login(used: Path, source: Path):
        """The CLI may rotate its refresh token mid-run; keep the newest login."""
        try:
            fresh = used.read_bytes()
            if fresh and fresh != source.read_bytes():
                tmp = source.with_name(source.name + ".buildrix-tmp")
                tmp.write_bytes(fresh)
                os.replace(tmp, source)
        except OSError:
            pass

    def _stop(self, proc, container_name: str = "", grace_s: float = 0, job=None):
        """Stop the agent: a polite stop first when grace_s > 0, then the kill.

        The polite stop lets in-flight file writes finish; the agent's chance to
        wrap up was the notice written before every stop. Native Windows has no
        polite stop for a console process tree, so it is killed at once.
        """
        polite = self.backend == "docker" or os.name != "nt"
        if grace_s and polite and proc.poll() is None:
            try:
                if self.backend == "docker":
                    subprocess.run(["docker", "stop", "-t", str(int(grace_s)), container_name],
                                   capture_output=True, timeout=grace_s + 30)
                else:
                    os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=grace_s)
            except (OSError, subprocess.SubprocessError):
                pass
        # Always end with the kill: children that outlived the agent (a training
        # script, say) must not keep writing to outputs/ while it is collected.
        if os.name == "nt":
            # The job object holds the whole tree; taskkill is the fallback.
            if not (job and job.kill()):
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait()
