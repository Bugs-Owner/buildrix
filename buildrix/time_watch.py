"""Watching a running agent: the expected time, extensions and stop rules.

A task's time budget is the time a run is *expected* to take, not a deadline.
A CLI agent runs as one non-interactive process, so the runner cannot talk to
it; it writes TIME_REMAINING.txt in the workspace instead (the brief tells the
agent to read it), and BASH_ENV makes every bash command print that file once
it holds a notice. Each step (a minute) the runner samples what it can see:

  files   something in the workspace was added, removed or changed
  outputs the same, under outputs/ only (where deliverables are graded)
  output  the transcript or stderr grew, other than one tool call repeated
          LOOP_REPEATS times in a row (a loop is not activity) or harness
          keep-alive events (Claude Code's tool_progress, every 30 s)
  cpu     processes the agent started used at least CPU_BUSY of a core; a
          long training or simulation counts. The CLI's own CPU is left out
          natively (Linux, Windows) but not in containers; unknown on macOS

Stop rules, the same for every agent on a task:

  stalled / loop  no files, output or cpu for stall_s, at any time; any file
                  in the workspace counts, since a script writing scratch
                  files is not stalled
  no_progress     at the expected time, and at the end of each extension, the
                  run is extended by extend_s if something under outputs/
                  changed or cpu was busy in the last extend_s; otherwise it
                  is stopped. Heartbeat or scratch files elsewhere do not
                  extend a run
  ceiling         the hard limit, so a study always finishes

Every stop is announced in TIME_REMAINING.txt first: at least WARN_LEAD_S
before the ceiling, a no-progress stop or a stall stop. GPU use is not read
directly; a process driving a GPU normally keeps a CPU core busy too.

Not implemented, by design: a model judge for the ambiguous case (output but
no outputs/ change or CPU past the expected time) would plug in at the checkpoint in
``watch`` as ``judge(transcript_tail, budget_s, elapsed_s) -> (progressing,
reason)`` and its verdict and reason would go into the extension's evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time

from buildrix.bench import _duration

CLOCK_FILE = "TIME_REMAINING.txt"
BASH_FILE = ".buildrix-time.sh"
CLOCK_EVERY_S = 60     # sampling and refresh step
WARN_LEAD_S = 300      # every stop is announced at least this early
REMIND_AT = 0.75       # share of the expected time when the agent is reminded
CPU_BUSY = 0.1         # cores; below this the agent's processes count as idle
LOOP_REPEATS = 6       # identical tool calls in a row that make a loop
# Sourced by every non-interactive bash (BASH_ENV): show any notice.
BASH_NOTICE = """# Written by the Buildrix runner. Shows TIME_REMAINING.txt when it holds a notice.
f="${BASH_SOURCE%/*}/TIME_REMAINING.txt"
if [ -r "$f" ] && read -r line < "$f" && [ "${line#status: ok}" = "$line" ]; then cat "$f" >&2; fi
"""


def write_clock(workspace: Path, text: str):
    """Replace TIME_REMAINING.txt. A failed refresh is skipped, never fatal."""
    temporary = workspace / f".{CLOCK_FILE}.tmp"
    # On Windows the agent (or a virus scanner) reading the file blocks the
    # replacement for a moment; retry briefly so a notice is not dropped.
    for attempt in range(10):
        try:
            temporary.write_text(text, encoding="utf-8", newline="\n")  # read by bash
            os.replace(temporary, workspace / CLOCK_FILE)
            return
        except OSError:
            time.sleep(0.02 * (attempt + 1))


def is_heartbeat(line: str) -> bool:
    """A harness keep-alive event (Claude Code's ``tool_progress``), not agent output."""
    try:
        event = json.loads(line)
    except ValueError:
        return False
    return isinstance(event, dict) and (event.get("type") == "tool_progress" or event.get("heartbeat") is True)


def tool_calls(transcript_tail: str) -> list[str]:
    """Each tool call in a Claude or Codex JSONL transcript, as comparable text."""
    calls = []
    for line in transcript_tail.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "assistant":  # Claude
            calls += [json.dumps([c.get("name"), c.get("input")], sort_keys=True)
                      for c in (event.get("message") or {}).get("content", [])
                      if isinstance(c, dict) and c.get("type") == "tool_use"]
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and isinstance(item, dict) and item.get("type") in (
                "command_execution", "mcp_tool_call", "file_change"):  # Codex
            calls.append(json.dumps([item.get("type"), item.get("command") or item.get("changes")],
                                    sort_keys=True, default=str))
    return calls


class Activity:
    """Samples what changed since the previous sample (see the module notes)."""

    def __init__(self, workspace: Path, logs: list[Path], cpu_seconds=None, cpu_busy=None):
        self.workspace, self.logs = workspace, logs
        # Either a cumulative CPU-seconds reader or a direct "busy now?" check.
        self.cpu_seconds, self.cpu_busy = cpu_seconds, cpu_busy
        self.files, self.sizes = self._files(), self._sizes()
        self.cpu, self.cpu_at = (cpu_seconds() if cpu_seconds else None), time.monotonic()

    def _files(self):
        """(count, bytes, newest mtime) of the whole workspace and of outputs/."""
        everything, outputs = [0, 0, 0], [0, 0, 0]
        prefix = os.path.join(str(self.workspace), "outputs")
        for root, _, names in os.walk(self.workspace):
            under_outputs = root == prefix or root.startswith(prefix + os.sep)
            for name in names:
                if root == str(self.workspace) and name in (CLOCK_FILE, f".{CLOCK_FILE}.tmp", BASH_FILE):
                    continue
                try:
                    stat = os.stat(os.path.join(root, name))
                except OSError:
                    continue
                for total in [everything] + ([outputs] if under_outputs else []):
                    total[0] += 1
                    total[1] += stat.st_size
                    total[2] = max(total[2], stat.st_mtime_ns)
        return tuple(everything), tuple(outputs)

    def _sizes(self):
        return [path.stat().st_size if path.exists() else 0 for path in self.logs]

    def _new_output(self, sizes) -> bool:
        """Did the agent write anything new, apart from its harness's heartbeats?

        Claude Code writes a ``tool_progress`` heartbeat every 30 s while a tool
        runs; that says the harness is alive, not that the agent did anything.
        """
        for path, old, new in zip(self.logs, self.sizes, sizes):
            if new - old > 1_000_000:
                return True
            if new > old:
                with path.open("rb") as stream:
                    stream.seek(old)
                    text = stream.read(new - old).decode("utf-8", "replace")
                if any(line.strip() and not is_heartbeat(line) for line in text.splitlines()):
                    return True
        return False

    def sample(self, cpu_window_s: float = 1.0) -> dict:
        """What changed since the last sample.

        CPU use is judged over at least ``cpu_window_s`` (never under 1 s):
        Windows counts CPU time in 15.6 ms ticks, so one tick in a short window
        would look like a busy core. A shorter sample reports no new CPU use and
        keeps its baseline for the next one.
        """
        files, sizes, now = self._files(), self._sizes(), time.monotonic()
        seen = {"files": files[0] != self.files[0], "outputs": files[1] != self.files[1],
                "output": self._new_output(sizes),
                "cpu": None, "looping": False}
        if self.cpu_seconds:
            if self.cpu is None:
                self.cpu, self.cpu_at = self.cpu_seconds(), now
            elif now - self.cpu_at >= max(1.0, cpu_window_s):
                cpu = self.cpu_seconds()
                if cpu is not None:
                    seen["cpu"] = (cpu - self.cpu) / (now - self.cpu_at) >= CPU_BUSY
                self.cpu, self.cpu_at = cpu, now
            else:
                seen["cpu"] = False
        elif self.cpu_busy:
            seen["cpu"] = self.cpu_busy()
        if seen["output"] and self.logs and self.logs[0].exists():
            with self.logs[0].open("rb") as stream:
                stream.seek(max(0, sizes[0] - 256_000))
                calls = tool_calls(stream.read().decode("utf-8", "replace"))
            seen["looping"] = len(calls) >= LOOP_REPEATS and len(set(calls[-LOOP_REPEATS:])) == 1
        self.files, self.sizes = files, sizes
        return seen


def session_cpu_seconds(session: int):
    """Linux: CPU seconds of the processes the agent CLI started (its session,
    finished children included), not the CLI's own: an idle CLI has bursts of
    its own. None where /proc is not available."""
    if not Path("/proc/self/stat").exists():
        return None
    ticks = 0
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if int(fields[3]) == session:  # field 6, session id
            # utime stime cutime cstime; the CLI itself (the session leader) only
            # contributes the time of its finished children.
            own = stat.parent.name == str(session)
            ticks += sum(int(x) for x in fields[13 if own else 11:15])
    return ticks / os.sysconf("SC_CLK_TCK")


class WindowsJob:
    """Windows: CPU seconds of all descendants of the agent CLI, via a job object.

    The CLI's own time is subtracted: an idle CLI has bursts of its own (seen
    in a real run: 1.5 s in 11 s), which are not the agent's computation.
    """

    def __init__(self, pid: int):
        import ctypes
        from ctypes import wintypes
        self.ctypes, kernel = ctypes, ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                     wintypes.DWORD, ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel, self.job = kernel, kernel.CreateJobObjectW(None, None)
        # SET_QUOTA | TERMINATE | QUERY_LIMITED_INFORMATION; kept open to read its times.
        self.process = kernel.OpenProcess(0x0100 | 0x0001 | 0x1000, False, pid)
        self.ok = bool(self.job and self.process and kernel.AssignProcessToJobObject(self.job, self.process))

    def cpu_seconds(self):
        ctypes = self.ctypes
        class Accounting(ctypes.Structure):  # JOBOBJECT_BASIC_ACCOUNTING_INFORMATION
            _fields_ = [(n, ctypes.c_longlong) for n in ("user", "kernel", "period_user", "period_kernel")] + [
                (n, ctypes.c_ulong) for n in ("faults", "processes", "active", "terminated")]
        info = Accounting()
        times = [ctypes.c_longlong() for _ in range(4)]  # creation, exit, kernel, user
        if not self.ok or not self.kernel.QueryInformationJobObject(
                self.job, 1, ctypes.byref(info), ctypes.sizeof(info), None) or not                 self.kernel.GetProcessTimes(self.process, *map(ctypes.byref, times)):
            return None
        return (info.user + info.kernel - times[2].value - times[3].value) / 1e7

    def kill(self) -> bool:
        """End every process in the tree at once (no extra process launched)."""
        return bool(self.ok and self.kernel.TerminateJobObject(self.job, 1))

    def close(self):
        for handle in (self.job, self.process):
            if handle:
                self.kernel.CloseHandle(handle)


def docker_busy(container: str):
    """Docker: is the container using at least CPU_BUSY of a core right now?"""
    try:
        out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}", container],
                             capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip().rstrip("%")) >= CPU_BUSY * 100
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def watch(proc, prompt: bytes, workspace: Path, activity: Activity, start: float,
          budget_s: float, extend_s: float, ceiling_s: float, stall_s: float, log: dict) -> str:
    """Feed the prompt, then watch the run until it ends or a stop rule fires.

    Returns "exited" when the agent ended by itself, otherwise the rule that
    stopped it: "stalled", "loop", "no_progress" or "ceiling". ``log`` gets the
    extensions (with their evidence) and each notice written to the agent.
    ``start`` is the epoch second the clock started, as stated in the brief.
    """
    ceiling, checkpoint = start + ceiling_s, start + budget_s
    step = max(0.05, min(CLOCK_EVERY_S, stall_s / 8, budget_s / 8))
    lead = min(WARN_LEAD_S, stall_s / 2, budget_s / 2)
    # Notices go out a little before `lead`, so a late wake-up never shortens it.
    early = lead + min(5.0, step)
    last_active = last_outputs = last_cpu = start
    stop_at, shown, data, looping = None, "ok", prompt, False
    clock = lambda t: time.strftime("%H:%M UTC", time.gmtime(t))
    while True:
        now = time.time()
        idle = now - last_active
        # What the agent is told, the most urgent first.
        if ceiling - now <= early:
            status, advice = "FINAL WARNING", (f"The run is stopped at {clock(ceiling)} (hard limit). "
                "Stop exploring and finalize outputs/ now.")
        elif idle >= stall_s - early:
            status, advice = "NO ACTIVITY", (f"Nothing has happened for {_duration(idle)}. The run is "
                f"stopped at {clock(last_active + stall_s)} unless work continues. Finalize outputs/.")
        elif stop_at:
            status, advice = "NO PROGRESS", (f"Past the expected time and nothing in outputs/ changed "
                f"and no computation ran in the last {_duration(extend_s)}. The run is stopped at {clock(stop_at)} "
                "unless that changes. Make sure every deliverable in outputs/ is written.")
        elif now >= start + budget_s:
            status, advice = "PAST EXPECTED TIME", ("Keep going only if you are making progress; "
                f"make sure every deliverable in outputs/ is written. Hard limit {clock(ceiling)}.")
        elif now >= start + REMIND_AT * budget_s:
            # Guidance, not a stop: a run that is making progress may go on.
            status, advice = "EXPECTED TIME NEARLY USED", ("Make sure every deliverable in outputs/ "
                "is written and current. This is not a stop: you may keep working past the "
                "expected time while you are making progress.")
        else:
            status, advice = "ok", ""
        write_clock(workspace, f"status: {status}\n"
            f"Expected time: {_duration(budget_s)}, until {clock(start + budget_s)}. "
            f"Hard limit: {clock(ceiling)}.\n"
            f"Time used: {_duration(now - start)} (as of {clock(now)}; updated every minute).\n"
            + (advice + "\n" if advice else ""))
        if status != shown:
            log["notices"].append({"at_s": round(now - start, 1), "status": status})
            shown = status
        # Wake for the next sample, or exactly when a notice or rule is due.
        due = [t for t in (ceiling - early, ceiling, checkpoint, stop_at, start + REMIND_AT * budget_s,
                           last_active + stall_s - early, last_active + stall_s) if t and t > now]
        planned = min([now + step] + due)
        try:
            proc.communicate(data, timeout=max(0.05, planned - now))
            return "exited"
        except subprocess.TimeoutExpired:
            data = None  # the prompt went in on the first call
        now, seen = time.time(), activity.sample(cpu_window_s=step / 2)
        if now - planned > max(10, 2 * step):
            # The runner itself was paused (machine asleep, node frozen): time it
            # did not watch is not the agent's idle time.
            last_active = now
        last_outputs = now if seen["outputs"] else last_outputs
        last_cpu = now if seen["cpu"] else last_cpu
        looping = seen["looping"] if seen["output"] else looping
        if seen["files"] or seen["cpu"] or (seen["output"] and not looping):
            last_active = now
        if now >= ceiling:
            return "ceiling"
        if now - last_active >= stall_s:
            return "loop" if looping else "stalled"
        if now >= checkpoint:
            if now - max(last_outputs, last_cpu) <= extend_s:
                checkpoint, stop_at = min(ceiling, now + extend_s), None
                log["extensions"].append({"at_s": round(now - start, 1),
                    "until_s": round(checkpoint - start, 1),
                    "evidence": {"outputs_changed_s_ago": round(now - last_outputs, 1),
                                 "cpu_busy_s_ago": round(now - last_cpu, 1)}})
            elif stop_at is None:
                stop_at = now + lead  # announce first, then stop
            elif now >= stop_at:
                return "no_progress"
