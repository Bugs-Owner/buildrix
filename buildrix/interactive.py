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
from pathlib import Path
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
    return "\n".join(lines).strip()


def confirm(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = ask(f"{prompt} ({suffix})", "")
    if not raw:
        return default
    return raw.lower().startswith("y")


# ═══════════════════════════════════════════════════════════════════════════
#  Rendering the shared ledger
# ═══════════════════════════════════════════════════════════════════════════

def show_states(draft: dict, dimensions: list[dict]) -> None:
    """The distance-to-done view, identical in content to the website's cards."""
    states = draft.get("dimension_states") or {}
    rule("where the definition stands")
    for d in dimensions:
        state = states.get(d["id"], "not_provided")
        mark, colour = STATE_MARK.get(state, ("?   ", C.dim))
        summary = ((draft.get("dimensions") or {}).get(d["id"]) or {}).get("summary", "")
        line = f"  {colour(mark)} {d['title']:<34} {C.dim(summary[:34])}"
        print(line.rstrip())
    notes = draft.get("intake_notes")
    if notes:
        print()
        para(C.dim(notes))


def show_assessment(draft: dict) -> None:
    """The Skill reusability verdict, when the workflow produced one."""
    r = ((draft.get("assessment") or {}).get("reusability") or {})
    if not r:
        return
    verdict = r.get("verdict", "")
    colour = {"reusable": C.green, "task_specific": C.amber,
              "hardcoded_answer": C.red}.get(verdict, C.dim)
    rule("reusability")
    print(f"  {colour(verdict.replace('_', ' '))}")
    if r.get("rationale"):
        para(C.dim(r["rationale"]))
    for f in r.get("findings") or []:
        print(f"    {C.amber('·')} {f.get('item', '')[:60]}")
        if f.get("fix"):
            para(C.dim(f["fix"]), indent="      ")


def answer_open_questions(draft: dict, by_id: dict) -> list[dict]:
    """Ask whatever the hub asked. Blank skips a question for this round."""
    questions = draft.get("open_questions") or []
    if not questions:
        return []
    rule(f"{len(questions)} question{'s' if len(questions) != 1 else ''} to answer")
    print(C.dim("  Leave one blank to skip it for now.\n"))
    answers = []
    for q in questions:
        title = by_id.get(q.get("dimension"), {}).get("title", q.get("dimension"))
        print(f"  {C.cyan(title)}")
        para(q.get("text", ""), indent="  ")
        if q.get("why"):
            para(C.dim(q["why"]), indent="  ")
        text = ask_block("your answer") if _is_long(q) else ask("answer", "")
        if text.strip():
            answers.append({"dimension": q["dimension"], "question_id": q["id"],
                            "question": q.get("text", ""), "answer": text.strip()})
        print()
    return answers


def _is_long(question: dict) -> bool:
    """Procedure-shaped questions get the block editor; one-liners do not."""
    dim = question.get("dimension", "")
    return dim in ("detailed_instruction", "workflow", "decision_guidance",
                   "failure_recovery", "evaluation", "objective", "purpose")


def decide_proposals(draft: dict, api_call: Callable, draft_id: str) -> bool:
    """Accept or reject anything the assistant suggested. Returns True if any."""
    pending = []
    for dim_id, rec in (draft.get("dimensions") or {}).items():
        for p in rec.get("proposals") or []:
            if p.get("status") == "pending":
                pending.append((dim_id, p))
    if not pending:
        return False
    rule("suggestions from the assistant")
    print(C.dim("  These are not in your draft yet. Engineering decisions are "
                "yours to confirm.\n"))
    for dim_id, p in pending:
        para(p.get("text", ""), indent="  ")
        if p.get("rationale"):
            para(C.dim(p["rationale"]), indent="    ")
        decision = "accepted" if confirm("  accept this", True) else "rejected"
        api_call(draft_id, dim_id, p["id"], decision)
        print()
    return True


def edit_sections(draft: dict, dimensions: list[dict],
                  setter: Callable, draft_id: str) -> None:
    """Let the contributor correct any extracted section directly."""
    dims = draft.get("dimensions") or {}
    titles = [(d["id"], d["title"]) for d in dimensions]
    while True:
        choice = ask("\n  edit a section? (number, or Enter to continue)", "")
        if not choice.strip():
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(titles)):
            for i, (_, t) in enumerate(titles, 1):
                print(f"    {C.dim(str(i) + '.')} {t}")
            continue
        dim_id, title = titles[int(choice) - 1]
        current = (dims.get(dim_id) or {}).get("content", "")
        if current:
            rule(title)
            para(current)
        new = ask_block(f"new text for {title}",
                        "Replaces what is there. End with a '.' on its own line.")
        if new.strip():
            draft.update(setter(draft_id, dim_id, {"content": new.strip()}))
            dims = draft.get("dimensions") or {}
            print(C.green(f"  {title} updated."))


def section_menu(dimensions: list[dict]) -> None:
    for i, d in enumerate(dimensions, 1):
        print(f"    {C.dim(str(i) + '.')} {d['title']}")


# ═══════════════════════════════════════════════════════════════════════════
#  The two loops
# ═══════════════════════════════════════════════════════════════════════════

def run_task_init(api: BuildrixAPI, *, resume: str = "",
                  max_rounds: int = 12) -> Optional[dict]:
    """`buildrix task init` — the website's Task workflow, in the terminal."""
    meta = api.task_meta()
    dimensions = meta["dimensions"]
    by_id = {d["id"]: d for d in dimensions}

    if resume:
        draft = api.task_draft(resume)
        print(C.green(f"\n  Resuming {draft['task_code']} — "
                      f"{draft['metadata'].get('title') or 'untitled'}"))
    else:
        rule("about the task")
        print(C.dim("  Six short answers. The Task ID is generated for you.\n"))
        body = {
            "title":  ask("title", required=True),
            "domain": ask_choice("domain",
                                 [(d["id"], d["label"]) for d in meta["domains"]]),
            "difficulty": ask_choice(
                "difficulty",
                [(d, d.title()) for d in meta["difficulties"]], "medium"),
            "estimated_effort": ask_choice(
                "how long would this take you?",
                [(e["id"], e["label"]) for e in meta["efforts"]]),
            "task_familiarity": ask_choice(
                "how well do you know this kind of work?",
                [(f["id"], f["label"]) for f in meta["task_familiarity"]]),
            "agentic_familiarity": ask_choice(
                "how often do you work with AI agents?",
                [(f["id"], f["label"]) for f in meta["agentic_familiarity"]]),
        }
        draft = api.task_draft_create(body)
        print(C.green(f"\n  Created {draft['task_code']}."))

    if not meta.get("llm_available"):
        para(C.amber(
            "The hub has no language model configured, so the definition below "
            "is read by its keyword analyser. Expect to correct more of it."))

    # -- card 2 ------------------------------------------------------------
    if not draft.get("initial_request"):
        rule("initial agent request")
        text = ask_block(
            "How would you ask an AI agent to work on this task?",
            "Describe the request as you would normally send it to an AI agent. "
            "Include as much information as you think is needed. This is kept "
            "exactly as you write it and is never rewritten.")
        if len(text) < 20:
            print(C.red("  Too short to work with. Nothing was submitted."))
            return None
        print(C.dim("\n  Reading it…"))
        draft = api.task_draft_request(draft["id"], text)

    # -- clarification -----------------------------------------------------
    draft = _clarify(
        draft, dimensions, by_id, max_rounds,
        answers_fn=api.task_draft_answers,
        proposal_fn=api.task_draft_proposal,
        setter_fn=api.task_draft_dimension,
        upload_hint="buildrix task submit --attach")

    # -- files -------------------------------------------------------------
    _attach_task_files(api, draft, dimensions)

    # -- finalize ----------------------------------------------------------
    draft = api.task_draft(draft["id"])
    if not draft["complete"]:
        _explain_incomplete(draft, "task", draft["id"])
        return draft

    print(C.dim("\n  Building the canonical prompt…"))
    draft = api.task_draft_finalize(draft["id"])
    rule("canonical task prompt")
    para(draft["canonical_prompt"])
    print()
    para(C.dim("This, and only this, is what an agent receives at run time. Your "
               "Detailed Instruction is stored with the Task but deliberately kept "
               "out of it, so the benchmark can run the Task with and without it."))
    if confirm("\n  edit the prompt", False):
        new = ask_block("canonical prompt")
        if new.strip():
            draft = api.task_draft_prompt(draft["id"], new.strip())

    return _submit(draft, "task", api.task_draft_submit, api.task_draft)


def run_skill_init(api: BuildrixAPI, *, resume: str = "",
                   max_rounds: int = 12) -> Optional[dict]:
    """`buildrix skill init` — the website's Skill workflow, in the terminal."""
    meta = api.skill_meta()
    dimensions = meta["dimensions"]
    by_id = {d["id"]: d for d in dimensions}

    if resume:
        draft = api.skill_draft(resume)
        print(C.green(f"\n  Resuming {draft['skill_code']} — "
                      f"{draft['metadata'].get('name') or 'unnamed'}"))
    else:
        rule("about the skill")
        print(C.dim("  A Skill is a capability an agent loads and reuses.\n"))
        body = {
            "name": ask("package name (kebab-case)", required=True).lower(),
            "title": ask("human-readable title", ""),
            "description": ask(
                "one sentence: what it does and when to use it", required=True),
            "domain": ask_choice("domain",
                                 [(d["id"], d["label"]) for d in meta["domains"]]),
            "version": ask("version", "0.1.0"),
            "license": ask_choice("licence",
                                  [(l, l) for l in meta["licenses"]], "Apache-2.0"),
            "determinism": ask_choice(
                "determinism",
                [(d, d.title()) for d in meta["determinism"]], "deterministic"),
        }
        draft = api.skill_draft_create(body)
        print(C.green(f"\n  Created {draft['skill_code']}."))

    if not meta.get("llm_available"):
        para(C.amber(
            "The hub has no language model configured, so the sections below are "
            "read by its keyword analyser, and the reusability check is a text "
            "scan rather than a real reading."))

    if not draft.get("initial_description"):
        rule("your method")
        text = ask_block(
            "Describe the method you want to package as a Skill.",
            "What it does, when you reach for it, how it goes, what you check, "
            "and what usually goes wrong. Write it the way you would explain it "
            "to a new colleague.")
        if len(text) < 20:
            print(C.red("  Too short to work with. Nothing was submitted."))
            return None
        print(C.dim("\n  Reading it…"))
        draft = api.skill_draft_describe(draft["id"], text)

    draft = _clarify(
        draft, dimensions, by_id, max_rounds,
        answers_fn=api.skill_draft_answers,
        proposal_fn=api.skill_draft_proposal,
        setter_fn=api.skill_draft_dimension,
        show_reusability=True)

    _attach_skill_files(api, draft)

    draft = api.skill_draft(draft["id"])
    if not draft["complete"]:
        _explain_incomplete(draft, "skill", draft["id"])
        return draft

    print(C.dim("\n  Building SKILL.md…"))
    draft = api.skill_draft_finalize(draft["id"])
    rule("SKILL.md")
    para(draft["skill_md"][:2400])
    if len(draft["skill_md"]) > 2400:
        print(C.dim("  … truncated for display."))
    if confirm("\n  edit SKILL.md", False):
        new = ask_block("SKILL.md body")
        if new.strip():
            draft = api.skill_draft_md(draft["id"], new.strip())

    show_assessment(draft)
    return _submit(draft, "skill", api.skill_draft_submit, api.skill_draft)


# ═══════════════════════════════════════════════════════════════════════════
#  Shared internals
# ═══════════════════════════════════════════════════════════════════════════

def _clarify(draft, dimensions, by_id, max_rounds, *, answers_fn, proposal_fn,
             setter_fn, show_reusability: bool = False, upload_hint: str = ""):
    """Round after round until nothing is open, or the contributor stops.

    Adaptive by construction: the hub decides what is still unclear, so a
    detailed description finishes in one round and a vague one takes several.
    """
    for _ in range(max_rounds):
        show_states(draft, dimensions)
        if show_reusability:
            show_assessment(draft)

        if decide_proposals(draft, proposal_fn, draft["id"]):
            draft = _refresh(draft, setter_fn)

        if draft.get("complete"):
            print(C.green("\n  Every section is resolved."))
            break

        answers = answer_open_questions(draft, by_id)
        if not answers:
            print(C.dim("\n  Nothing answered this round."))
            print(C.dim("  Options: (e)dit a section directly, (s)kip and finish "
                        "later, or Enter to be asked again."))
            choice = ask("what next", "").lower()
            if choice.startswith("e"):
                section_menu(dimensions)
                edit_sections(draft, dimensions, setter_fn, draft["id"])
                draft = _reload(draft, setter_fn)
                continue
            if choice.startswith("s"):
                return draft
            continue

        print(C.dim("\n  Re-reading the whole definition…"))
        draft = answers_fn(draft["id"], answers)
    return draft


def _refresh(draft, setter_fn):
    """Proposal decisions return the updated draft; keep the newest one."""
    return draft


def _reload(draft, setter_fn):
    return draft


def _attach_task_files(api: BuildrixAPI, draft: dict, dimensions: list[dict]) -> None:
    if not confirm("\n  attach any files (inputs, ground truth, reference)", False):
        return
    kinds = [("input", "Input file the agent receives", "inputs_resources"),
             ("ground_truth", "Ground truth the result is scored against", "evaluation"),
             ("human_reference", "Your own reference output", "evaluation")]
    while True:
        raw = ask("  path (Enter to stop)", "")
        if not raw.strip():
            return
        path = Path(raw).expanduser()
        if not path.is_file():
            print(C.red(f"    {path} is not a file."))
            continue
        kind = ask_choice("what is it", [(k, label) for k, label, _ in kinds])
        dim = next(d for k, _, d in kinds if k == kind)
        try:
            api.task_draft_asset(draft["id"], path, dim, kind,
                                 ask("  one-line description", ""))
            print(C.green(f"    attached {path.name}"))
        except ApiError as e:
            print(C.red(f"    {e}"))


def _attach_skill_files(api: BuildrixAPI, draft: dict) -> None:
    if not confirm("\n  bundle any files (scripts, references, examples)", False):
        return
    kinds = [("script", "scripts/ — code the agent runs"),
             ("reference", "references/ — docs loaded on demand"),
             ("example", "examples/ — worked examples"),
             ("asset", "assets/ — templates, lookup tables"),
             ("test", "tests/ — runnable checks")]
    while True:
        raw = ask("  path (Enter to stop)", "")
        if not raw.strip():
            return
        path = Path(raw).expanduser()
        if not path.is_file():
            print(C.red(f"    {path} is not a file."))
            continue
        kind = ask_choice("which folder", kinds)
        try:
            api.skill_draft_asset(draft["id"], path, kind,
                                  ask("  one-line description", ""))
            print(C.green(f"    bundled {path.name}"))
        except ApiError as e:
            print(C.red(f"    {e}"))


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
