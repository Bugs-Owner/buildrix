"""The one report format, shared by local checks and server reviews.

`buildrix skill check`, `buildrix skill submit`, `buildrix task check`,
`buildrix task submit` and `buildrix ... status` all print the same thing, so a
contributor learns to read one report. The hub returns the same structure as
JSON, and `from_hub` converts it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PASS = "pass"
CONCERN = "concern"
BLOCKER = "blocker"

_ORDER = {BLOCKER: 0, CONCERN: 1, PASS: 2}

# Verdicts, in the same vocabulary the reviewer uses.
READY = "ready to submit"
MINOR = "minor revision"
MAJOR = "major revision"
ACCEPTED = "accepted"
REJECTED = "rejected"


@dataclass
class Finding:
    """One outcome for one area of the check or review."""

    area: str                 # "structure", "description", "anchors", ...
    level: str                # PASS | CONCERN | BLOCKER
    message: str = ""         # what is wrong, in one sentence
    fix: str = ""             # what to write instead
    detail: str = ""          # short value shown beside a passing line

    @property
    def ok(self) -> bool:
        return self.level == PASS


@dataclass
class Report:
    """A full check or review outcome."""

    title: str = ""
    findings: list[Finding] = field(default_factory=list)
    verdict: str = ""
    round: int = 0
    missing: list[tuple[str, str]] = field(default_factory=list)  # (item, state)
    rewrite: str = ""                                             # suggested prompt/text

    # -- building ------------------------------------------------------------

    def add(self, area: str, level: str, message: str = "", fix: str = "",
            detail: str = "") -> None:
        self.findings.append(Finding(area, level, message, fix, detail))

    def ok(self, area: str, detail: str = "") -> None:
        self.add(area, PASS, detail=detail)

    def concern(self, area: str, message: str, fix: str = "") -> None:
        self.add(area, CONCERN, message, fix)

    def blocker(self, area: str, message: str, fix: str = "") -> None:
        self.add(area, BLOCKER, message, fix)

    # -- reading -------------------------------------------------------------

    @property
    def blockers(self) -> list[Finding]:
        return [f for f in self.findings if f.level == BLOCKER]

    @property
    def concerns(self) -> list[Finding]:
        return [f for f in self.findings if f.level == CONCERN]

    @property
    def passed(self) -> bool:
        return not self.blockers

    def resolve_verdict(self) -> str:
        """Derive a verdict from the findings, never from an average."""
        if self.verdict:
            return self.verdict
        if self.blockers:
            return MAJOR
        if self.concerns:
            return MINOR
        return READY

    @property
    def exit_code(self) -> int:
        return 0 if self.passed else 1

    # -- conversion ----------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "verdict": self.resolve_verdict(),
            "round": self.round,
            "findings": [
                {"area": f.area, "level": f.level, "message": f.message,
                 "fix": f.fix, "detail": f.detail}
                for f in self.findings
            ],
            "missing": [{"item": i, "state": s} for i, s in self.missing],
            "rewrite": self.rewrite,
        }

    @classmethod
    def from_hub(cls, payload: dict, title: str = "") -> "Report":
        """Build a report from the hub's review response.

        Accepts both the new shape (``findings``) and the older checklist shape
        (``llm_review_checklist`` with ``{status, rationale, suggestions}``).
        """
        rep = cls(title=title or payload.get("title", ""))
        rep.verdict = payload.get("verdict") or payload.get("llm_review_status") or ""
        rep.round = int(payload.get("round") or 0)
        rep.rewrite = payload.get("rewrite", "")

        findings = payload.get("findings")
        if findings:
            for f in findings:
                rep.add(f.get("area", "review"), f.get("level", CONCERN),
                        f.get("message", ""), f.get("fix", ""), f.get("detail", ""))
        else:
            checklist = payload.get("llm_review_checklist") or {}
            for area, item in checklist.items():
                if not isinstance(item, dict):
                    continue
                level = item.get("status", CONCERN)
                sugg = item.get("suggestions") or []
                rep.add(area, level if level in _ORDER else CONCERN,
                        item.get("rationale", ""),
                        sugg[0] if sugg else "")

        for m in payload.get("missing", []) or []:
            if isinstance(m, dict):
                rep.missing.append((m.get("item", ""), m.get("state", "")))
        return rep


# -- terminal rendering ------------------------------------------------------

_MARK = {PASS: "pass", CONCERN: "concern", BLOCKER: "blocker"}
_DOTS = 26


def render(rep: Report, *, color: bool = True) -> str:
    """Format a report for the terminal."""
    c = _Colors() if color else _NoColors()
    out: list[str] = []

    if rep.title:
        out.append(f"\n{c.bold}{rep.title}{c.off}")
    out.append("")

    for f in rep.findings:
        dots = "." * max(3, _DOTS - len(f.area))
        tone = c.green if f.level == PASS else (c.amber if f.level == CONCERN else c.mag)
        line = f"  {f.area} {c.dim}{dots}{c.off} {tone}{_MARK[f.level]}{c.off}"
        if f.detail:
            line += f"   {c.dim}{f.detail}{c.off}"
        out.append(line)

    problems = sorted([f for f in rep.findings if f.level != PASS],
                      key=lambda f: _ORDER[f.level])
    if problems:
        out.append("")
        for f in problems:
            tone = c.mag if f.level == BLOCKER else c.amber
            out.append(f"  {tone}{_MARK[f.level]}{c.off}  {c.bold}{f.area}{c.off}")
            for line in _wrap(f.message):
                out.append(f"    {line}")
            if f.fix:
                for i, line in enumerate(_wrap(f.fix)):
                    out.append(f"    {c.dim}{'fix: ' if i == 0 else '     '}{line}{c.off}")

    if rep.missing:
        out.append("")
        out.append(f"  {c.bold}still missing{c.off}")
        width = max(len(m[0]) for m in rep.missing)
        for item, state in rep.missing:
            tone = c.green if state in ("complete", "ok") else c.amber
            out.append(f"    {item:<{width}}   {tone}{state}{c.off}")

    if rep.rewrite:
        out.append("")
        out.append(f"  {c.bold}suggested rewrite{c.off}")
        for line in rep.rewrite.strip().splitlines():
            out.append(f"    {c.dim}{line}{c.off}")

    verdict = rep.resolve_verdict()
    tone = c.green if verdict in (READY, ACCEPTED) else (
        c.mag if verdict in (MAJOR, REJECTED) else c.amber)
    tail = []
    if rep.blockers:
        tail.append(f"{len(rep.blockers)} blocker" + ("s" if len(rep.blockers) != 1 else ""))
    if rep.concerns:
        tail.append(f"{len(rep.concerns)} concern" + ("s" if len(rep.concerns) != 1 else ""))
    suffix = f"  {c.dim}({', '.join(tail)}){c.off}" if tail else ""
    round_txt = f"{c.dim} | round {rep.round}{c.off}" if rep.round else ""

    out.append("")
    out.append(f"  verdict: {tone}{verdict}{c.off}{round_txt}{suffix}")
    out.append("")
    return "\n".join(out)


def _wrap(text: str, width: int = 72) -> list[str]:
    import textwrap
    text = " ".join((text or "").split())
    return textwrap.wrap(text, width) or [""]


class _Colors:
    bold = "\033[1m"
    dim = "\033[2m"
    green = "\033[32m"
    amber = "\033[33m"
    mag = "\033[35m"
    cyan = "\033[36m"
    off = "\033[0m"


class _NoColors:
    bold = dim = green = amber = mag = cyan = off = ""


def supports_color() -> bool:
    import os
    import sys
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())
