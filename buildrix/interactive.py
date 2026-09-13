"""
The conversational definition loop, in a terminal.
==================================================

``buildrix task init`` and ``buildrix skill init`` do not have their own idea of
what a Task or a Skill is. They open a draft on the hub and drive the *same*
endpoints the website drives — the same clarification questions, the same
four-state ledger, the same reusability check, the same final package. What
differs is only the surface: a browser renders cards, this renders prompts.

That is what makes the promise real. A Task defined in a terminal and a Task
defined in a browser are the same row, with the same interaction history behind
it, because there is only one implementation and it lives on the server.

Nothing here decides anything about the content. Every judgement — whether a
dimension is clear, what to ask next, what the canonical prompt says — comes
back from the hub.
"""

from __future__ import annotations

import os
import sys
import textwrap
from typing import Callable, Optional

from buildrix.hub_api import ApiError, BuildrixAPI

WIDTH = 76


# ═══════════════════════════════════════════════════════════════════════════
#  Terminal helpers
# ═══════════════════════════════════════════════════════════════════════════

def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


class _C:
    def __init__(self, on: bool):
        self.on = on

    def _w(self, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if self.on else s

    def dim(self, s):    return self._w("2", s)
    def bold(self, s):   return self._w("1", s)
    def cyan(self, s):   return self._w("36", s)
    def green(self, s):  return self._w("32", s)
    def amber(self, s):  return self._w("33", s)
    def red(self, s):    return self._w("31", s)


C = _C(supports_color())

STATE_MARK = {
    "clear":               ("ok  ", C.green),
    "needs_clarification": ("ask ", C.amber),
    "not_provided":        ("--  ", C.red),
    "not_applicable":      ("n/a ", C.dim),
}


def rule(title: str = "") -> None:
    if title:
        print("\n" + C.cyan(f"── {title} ").ljust(WIDTH + 12, "─"))
    else:
        print(C.dim("─" * WIDTH))


def para(text: str, indent: str = "  ") -> None:
    for block in (text or "").split("\n"):
        if not block.strip():
            print()
            continue
        for line in textwrap.wrap(block, WIDTH, initial_indent=indent,
                                  subsequent_indent=indent):
            print(line)


def ask(prompt: str, default: str = "", required: bool = False) -> str:
    """One line of input. Enter keeps the default."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            value = input(f"  {C.bold(prompt)}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(130)
        value = value or default
        if value or not required:
            return value
        print(C.dim("    Required."))


def ask_choice(prompt: str, options: list[tuple[str, str]],
               default: str = "") -> str:
    """Pick one of a closed set. Accepts the number or the id."""
    print(f"\n  {C.bold(prompt)}")
    for i, (key, label) in enumerate(options, 1):
        mark = " *" if key == default else ""
        print(f"    {C.dim(str(i) + '.')} {label}{C.dim(mark)}")
    while True:
        raw = ask("choose", default or "", required=True)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        for key, _ in options:
            if raw.lower() == key.lower():
                return key
        print(C.dim("    Pick a number from the list, or type the id."))


def ask_block(prompt: str, hint: str = "") -> str:
    """Multi-line input, ended with a lone '.' or EOF.

    An editor would be nicer, but a lone dot works over ssh, inside a container
    and in an agent's shell — which is where a lot of this will be typed.
    """
    print(f"\n  {C.bold(prompt)}")
    if hint:
        para(C.dim(hint), indent="  ")
    print(C.dim("  Write as much as you want. End with a single '.' on its own line."))
    lines: list[str] = []
    while True:
        try:
            line = input("  | ")
        except EOFError:
            break
        except KeyboardInterrupt:
            print()
            raise SystemExit(130)
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines)


def confirm(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = ask(f"{prompt} ({suffix})", "")
    if not raw:
        return default
    return raw.lower().startswith("y")


def run_task_init(api: BuildrixAPI, *, resume: str = "", max_rounds=None):
    from buildrix.contribution_wizard import run
    return run(api, "task", resume=resume)


def run_skill_init(api: BuildrixAPI, *, resume: str = "", max_rounds=None):
    from buildrix.contribution_wizard import run
    return run(api, "skill", resume=resume)


def _explain_incomplete(draft: dict, noun: str, draft_id: str) -> None:
    rule("not finished yet")
    for m in draft.get("missing") or []:
        print(f"  {C.amber('·')} {m['title']} — {m['state'].replace('_', ' ')}")
        for q in m.get("questions") or []:
            para(C.dim(q), indent="      ")
    print()
    para(f"Your draft is saved. Pick it up with "
         f"{C.cyan(f'buildrix {noun} init --resume {draft_id}')}, or in the "
         f"browser — it is the same draft either way.")


def _submit(draft: dict, noun: str, submit_fn: Callable,
            reload_fn: Callable) -> Optional[dict]:
    draft = reload_fn(draft["id"])
    validation = draft.get("validation") or {}
    for w in validation.get("warnings") or []:
        print(C.amber("\n  worth a look: ") + w)
    if validation.get("blocking"):
        rule("cannot submit yet")
        for b in validation["blocking"]:
            print(f"  {C.red('·')} {b}")
        _explain_incomplete(draft, noun, draft["id"])
        return draft

    print()
    para(C.dim(
        f"Submitting keeps this {noun} and its full definition history, which may "
        f"be used in aggregate for research on how people specify engineering "
        f"work for AI agents."))
    if not confirm(f"\n  submit this {noun}", True):
        print(C.dim(f"  Left as a draft. Resume with "
                    f"`buildrix {noun} init --resume {draft['id']}`."))
        return draft

    print(C.dim("\n  Submitting…"))
    try:
        result = submit_fn(draft["id"])
    except ApiError as e:
        print(C.red(f"  {e}"))
        return draft

    code = result.get("task_code") or result.get("skill_code") or ""
    print(C.green(f"\n  {code} submitted."))
    verdict = result.get("llm_review_status", "")
    if verdict and verdict != "none":
        colour = {"accepted": C.green, "minor_revision": C.amber,
                  "major_revision": C.red, "rejected": C.red}.get(verdict, C.dim)
        print(f"  admissibility review: {colour(verdict.replace('_', ' '))}")
        if result.get("llm_review_comments"):
            para(C.dim(result["llm_review_comments"][:600]))
    for w in result.get("warnings") or []:
        print(C.amber("  worth a look: ") + w)
    return result
