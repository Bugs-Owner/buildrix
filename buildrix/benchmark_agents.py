"""Unattended CLI adapters. Session isolation and OS isolation are distinct.

Native execution resets homes and caches but is not a security boundary.
Docker/Apptainer run each condition with only that condition's workspace mounted.
Authentication uses provider API keys, never the user's agent configuration.
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

from buildrix.bench import AgentResult


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
                 memory_mb: int = 4096):
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
        self.evidence_dir: Path | None = None

    def command(self) -> list[str]:
        if self.provider == "codex":
            return ["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
                    "--model", self.model, "--sandbox",
                    "workspace-write" if self.backend == "native" else "danger-full-access",
                    "-"]
        args = ["claude", "-p", "--model", self.model, "--output-format", "stream-json",
                "--verbose", "--no-session-persistence", "--setting-sources", "",
                "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
        if self.backend == "native":
            args += ["--permission-mode", "acceptEdits", "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep"]
        else:
            args += ["--dangerously-skip-permissions"]
        return args

    def run(self, workspace: Path, prompt: str) -> AgentResult:
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
            env[key] = os.environ[key]
            if self.provider == "codex":
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
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
            command = self.command()
            agent_version = ""
            if self.backend == "native":
                env.update(isolated)
                for value in isolated.values():
                    if value.startswith(runtime_home):
                        Path(value).mkdir(parents=True, exist_ok=True)
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
            try:
                with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                    proc = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.PIPE,
                        stdout=stdout, stderr=stderr, start_new_session=os.name != "nt")
                    try:
                        proc.communicate(prompt.encode(), timeout=self.timeout_s)
                    except subprocess.TimeoutExpired:
                        error = f"Agent exceeded {self.timeout_s}s"
                        self._stop(proc)
                    except BaseException:
                        self._stop(proc)
                        raise
                    returncode = proc.returncode
            except OSError as exc:
                error = f"Could not start agent: {exc}"
            finally:
                if self.backend == "docker":
                    try:
                        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=30)
                    except (OSError, subprocess.TimeoutExpired):
                        error = error or "Container cleanup failed; check Docker before resuming"
            transcript = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
            if self.backend != "native":
                agent_version = next((line.split("=", 1)[1][:200] for line in stderr.splitlines()
                    if line.startswith("BUILDRIX_AGENT_VERSION=")), "")
            usage = parse_usage(transcript, self.provider)
            ok = returncode == 0 and not error and not usage.get("agent_error") and usage["completed_event"]
            return AgentResult(ok, transcript=transcript, wall_clock_s=round(time.monotonic()-started, 3),
                tokens=usage["total_tokens"] or 0, tool_calls=usage["tool_calls"], usage=usage,
                error=error or ("" if ok else f"Agent failed or returned no completion event (exit {returncode})"),
                stderr=stderr, agent_version=agent_version)

    @staticmethod
    def _stop(proc):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait()
