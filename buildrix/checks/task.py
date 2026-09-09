"""The mechanical gates for a `task/2.0` package.

G1 schema | G2 anchors | G3 the gold scores 1.0 | G4 an empty folder scores 0.0 |
G5 every wrong-but-plausible case fails | G6 grading is repeatable |
G7 weights and the judged cap | G8 the expert's own run fits the budget.

G3 to G6 run only when the contributor's grader and reference are present, which
is the normal case on their own machine. The hub repeats all of them.
"""

from __future__ import annotations

import importlib.util
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

import yaml

from buildrix import domains, spec
from buildrix.report import Report


def check_task(path: str | Path, *, run_grader: bool = True) -> Report:
    """Run every task/2.0 gate against a directory. Never raises."""
    d = Path(path).expanduser().resolve()
    rep = Report(title=f"task check | {d.name}")

    if not d.is_dir():
        rep.blocker("structure", f"{d} is not a directory.")
        return rep

    ty = d / "TASK.yaml"
    if not ty.exists():
        rep.blocker("structure", "No TASK.yaml at the top of the folder.",
                    "Run `buildrix task new <name>` and fill it in.")
        return rep

    try:
        doc = yaml.safe_load(ty.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        rep.blocker("structure", f"TASK.yaml is not valid YAML: {e}")
        return rep
    if not isinstance(doc, dict):
        rep.blocker("structure", "TASK.yaml must be a mapping at the top level.")
        return rep

    # -- G1 schema -----------------------------------------------------------
    problems: list[str] = []
    if str(doc.get("schema") or "") != spec.TASK_SCHEMA:
        problems.append(f'`schema` should be "{spec.TASK_SCHEMA}"')

    ident = doc.get("identity") or {}
    if not ident.get("id"):
        problems.append("`identity.id` is missing")
    elif not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(ident["id"])):
        problems.append("`identity.id` must be lower case words joined by hyphens")
    if not ident.get("title"):
        problems.append("`identity.title` is missing")

    tax = doc.get("taxonomy") or {}
    dom = str(tax.get("domain") or "")
    if not dom:
        problems.append("`taxonomy.domain` is missing")
    elif not domains.is_valid(dom, kind="task"):
        problems.append(f"`taxonomy.domain` '{dom}' is not one of the eight "
                        "(a task cannot use 'general')")
    if "tier" in tax or "difficulty" in tax:
        problems.append("`tier`/`difficulty` are not fields any more - difficulty is "
                        "the measured baseline pass rate, written by the server")
    if not tax.get("human_minutes"):
        problems.append("`taxonomy.human_minutes` is missing (how long it took you)")

    if problems:
        rep.blocker("schema", "; ".join(problems[:4]) + ".",
                    "See spec/03-TASK_FORMAT.md for the full schema.")
    else:
        rep.ok("schema", domains.short(dom))

    # -- prompt --------------------------------------------------------------
    prompt_file = str((doc.get("task") or {}).get("prompt_file") or "prompt.md")
    pf = d / prompt_file
    prompt = ""
    if not pf.exists():
        rep.blocker("prompt", f"{prompt_file} is missing.",
                    "This file is the only thing the agent reads. Write it as you would "
                    "brief a new engineer.")
    else:
        raw = pf.read_text(encoding="utf-8", errors="replace")
        prompt = _strip_comments(raw)
        if raw.strip() != prompt:
            rep.concern("prompt", "There is still an HTML comment in the prompt.",
                        "The prompt reaches the agent word for word, template notes "
                        "included. Delete the <!-- ... --> block.")
        words = len(prompt.split())
        if words < 25:
            rep.blocker("prompt", f"Only {words} words. Too thin to be reproducible.",
                        "Name the inputs, the deliverables and the period.")
        else:
            rep.ok("prompt", f"{words} words")

    # -- deliverables --------------------------------------------------------
    delivs = doc.get("deliverables") or []
    if not delivs:
        rep.blocker("deliverables", "None declared.",
                    "Name each file, its format, and for tables its columns and units.")
    else:
        thin = [x.get("path", "?") for x in delivs
                if isinstance(x, dict) and x.get("format") in (None, "")]
        missing_paths = [i for i, x in enumerate(delivs)
                         if not isinstance(x, dict) or not x.get("path")]
        if missing_paths:
            rep.blocker("deliverables", "Every deliverable needs a `path`.")
        elif thin:
            rep.concern("deliverables",
                        "No `format` on " + ", ".join(thin[:3]) + ".",
                        "Add format: csv | markdown | json | idf | ifc | png ...")
        else:
            tabular = [x for x in delivs if x.get("format") == "csv"]
            no_schema = [x["path"] for x in tabular if not x.get("schema")]
            if no_schema:
                rep.concern("deliverables",
                            "CSV deliverables with no column schema: "
                            + ", ".join(no_schema[:3]) + ".",
                            "Declare columns with units and ranges, so grading is about "
                            "the engineering and not the header spelling.")
            else:
                rep.ok("deliverables", f"{len(delivs)} file(s)")

    # -- environment and budget (G8) -----------------------------------------
    env = doc.get("environment") or {}
    budget = doc.get("budget") or {}
    if not env.get("python"):
        rep.concern("environment", "`environment.python` is not pinned.",
                    'Add python: ">=3.11,<3.14" so both arms install the same thing.')
    elif (env.get("network") or {}).get("policy") not in ("allowlist", "offline"):
        rep.concern("environment", "`environment.network.policy` must be allowlist or offline.")
    else:
        rep.ok("environment", str(env.get("python")))

    need = ["wall_clock_s", "max_tokens", "max_tool_calls"]
    absent = [k for k in need if not budget.get(k)]
    if absent:
        rep.blocker("budget", "Missing " + ", ".join(absent) + ".",
                    "Both arms of a paired run get exactly this budget, so it has to be "
                    "stated. 900 s / 250000 tokens / 120 calls is a normal starting point.")
    else:
        rep.ok("budget", f"{budget['wall_clock_s']}s | {int(budget['max_tokens']):,} tok")

    # -- ground rules --------------------------------------------------------
    freedom = doc.get("freedom") or {}
    if not freedom.get("free") and not freedom.get("fixed"):
        rep.concern("ground rules", "Neither free nor fixed choices are declared.",
                    "Anything that changes the answer has to be pinned, or explicitly "
                    "left free. Silence is what makes a task unfair.")
    else:
        rep.ok("ground rules",
               f"{len(freedom.get('free') or [])} free | {len(freedom.get('fixed') or [])} fixed")

    # -- G7 weights and judged cap -------------------------------------------
    rubric = doc.get("rubric") or {}
    criteria = rubric.get("criteria") or []
    threshold = float(rubric.get("pass_threshold") or spec.DEFAULT_PASS_THRESHOLD)
    cap = float(rubric.get("llm_judge_weight_cap") or spec.DEFAULT_JUDGE_CAP)

    if not criteria:
        rep.blocker("rubric", "No criteria.",
                    "Every deliverable needs at least one check.")
    else:
        total = sum(float(c.get("weight") or 0) for c in criteria)
        judged = sum(float(c.get("weight") or 0) for c in criteria
                     if c.get("check") in spec.JUDGED_KINDS)
        bad_kind = [str(c.get("check")) for c in criteria
                    if c.get("check") not in spec.CHECK_KINDS]
        issues = []
        if abs(total - 1.0) > 1e-3:
            issues.append(f"weights sum to {total:.3f}, not 1.0")
        if judged > cap + 1e-9:
            issues.append(f"judged weight is {judged:.2f}, over the cap of {cap:.2f}")
        if bad_kind:
            issues.append("unknown check kinds: " + ", ".join(sorted(set(bad_kind))[:3]))
        if issues:
            rep.blocker("rubric", "; ".join(issues) + ".",
                        "Check kinds: " + " | ".join(spec.CHECK_KINDS))
        else:
            rep.ok("rubric", f"{len(criteria)} checks | {judged:.2f} judged")

    # -- G2 anchors ----------------------------------------------------------
    if criteria and prompt:
        norm_prompt = _norm(prompt)
        unanchored = []
        for c in criteria:
            anchor = str(c.get("prompt_anchor") or "")
            if not anchor:
                unanchored.append((c.get("id", "?"), "no anchor"))
            elif _norm(anchor) not in norm_prompt:
                unanchored.append((c.get("id", "?"), "not in the prompt"))
        if unanchored:
            rep.blocker("anchors",
                        "; ".join(f"{cid}: {why}" for cid, why in unanchored[:4]) + ".",
                        "Every check carries a phrase copied from the prompt. If you want "
                        "to grade it, you have to have asked for it.")
        else:
            rep.ok("anchors", f"{len(criteria)}/{len(criteria)} found")

        unchecked = _unchecked_instructions(prompt, criteria)
        if unchecked:
            rep.concern("prompt coverage",
                        f"{len(unchecked)} instruction(s) in the prompt that no check "
                        f"covers, starting: '{unchecked[0][:70]}'",
                        "Either add a check, or cut the sentence. An unchecked "
                        "instruction is either unfair or noise.")
        else:
            rep.ok("prompt coverage")

    # -- G3-G6 the grader ----------------------------------------------------
    grader = d / "grader" / "grade.py"
    reference = d / "grader" / "reference"
    mutations = doc.get("mutation_tests") or []

    if not grader.exists():
        rep.blocker("grader", "grader/grade.py is missing.",
                    "It needs one function: grade(bundle_dir, reference_dir) -> dict "
                    "with an `overall` in [0, 1].")
    elif not reference.is_dir() or not any(reference.iterdir()):
        rep.blocker("reference", "grader/reference/ is empty.",
                    "Put your own answer here. It stays on the server and is only "
                    "loaded after the agent stops.")
    elif not run_grader:
        rep.ok("grader", "found, not run")
    else:
        fn = _load_grader(grader)
        if fn is None:
            rep.blocker("grader", "grader/grade.py has no callable `grade`.",
                        "def grade(bundle_dir, reference_dir) -> dict")
        else:
            _grader_gates(rep, fn, reference, threshold, mutations, d)

    if len(mutations) < spec.MIN_MUTATIONS:
        rep.concern("wrong-but-plausible",
                    f"{len(mutations)} of {spec.MIN_MUTATIONS} declared.",
                    "Name three ways a wrong answer could still look right. We run them "
                    "against your grader; if one passes, the grader is too loose.")

    # -- provenance ----------------------------------------------------------
    prov = doc.get("provenance") or {}
    if not prov.get("origin"):
        rep.concern("provenance", "`provenance.origin` is empty.",
                    "Say where the work came from. Real jobs make the best tasks.")
    else:
        rep.ok("provenance")

    rep.missing = _ledger(doc, d, prompt, mutations)
    return rep


# -- grader gates ------------------------------------------------------------

def _grader_gates(rep: Report, fn: Callable, reference: Path, threshold: float,
                  mutations: list, task_dir: Path) -> None:
    gold = _score(fn, reference, reference)
    if gold is None:
        rep.blocker("grader", "The grader raised an error on your own answer.",
                    "Run it directly and fix the traceback first.")
        return

    if abs(gold - 1.0) > 1e-6:
        rep.blocker("gold (G3)", f"Your own answer scores {gold:.2f}, not 1.00.",
                    "Either the grader is wrong, or the reference does not satisfy the "
                    "prompt. Both are worth knowing now.")
    else:
        rep.ok("gold (G3)", "1.00")

    with tempfile.TemporaryDirectory() as tmp:
        empty = _score(fn, Path(tmp), reference)
    if empty is None:
        rep.concern("floor (G4)", "The grader raised an error on an empty folder.",
                    "It should return 0.0, not crash, when a deliverable is absent.")
    elif empty > 1e-6:
        rep.blocker("floor (G4)", f"An empty folder scores {empty:.2f}, not 0.00.",
                    "Some check passes without any work. Usually a file_exists check "
                    "pointing at the wrong path.")
    else:
        rep.ok("floor (G4)", "0.00")

    if mutations:
        leaks = []
        for mut in mutations:
            nm = mut.get("name") if isinstance(mut, dict) else str(mut)
            mdir = task_dir / "grader" / "mutations" / str(nm)
            if not mdir.is_dir():
                continue
            sc = _score(fn, mdir, reference)
            if sc is not None and sc >= threshold:
                leaks.append((nm, sc))
        if leaks:
            rep.blocker("discrimination (G5)",
                        "; ".join(f"'{n}' scores {s:.2f}, at or above the {threshold:.2f} "
                                  f"pass mark" for n, s in leaks[:3]) + ".",
                        "The grader cannot tell this wrong answer from a right one. "
                        "Tighten the check that should have caught it.")
        else:
            found = sum(1 for m in mutations
                        if (task_dir / "grader" / "mutations"
                            / str(m.get("name") if isinstance(m, dict) else m)).is_dir())
            if found:
                rep.ok("discrimination (G5)", f"{found} case(s) fail as intended")
            else:
                rep.concern("discrimination (G5)",
                            "Cases are declared but grader/mutations/<name>/ is empty.",
                            "Put a degraded copy of your answer in each folder so the "
                            "check can actually run.")

    second = _score(fn, reference, reference)
    if second is None or abs(second - gold) > 1e-9:
        rep.blocker("repeatable (G6)", "Grading the same folder twice gave two scores.",
                    "Remove the randomness, or seed it, so a result can be re-derived.")
    else:
        rep.ok("repeatable (G6)")


def _load_grader(path: Path) -> Callable | None:
    try:
        sp = importlib.util.spec_from_file_location("buildrix_task_grader", path)
        if sp is None or sp.loader is None:
            return None
        mod = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(mod)
    except Exception:
        return None
    fn = getattr(mod, "grade", None)
    return fn if callable(fn) else None


def _score(fn: Callable, bundle: Path, reference: Path) -> float | None:
    """Call a grader and pull the overall out of whatever shape it returns."""
    try:
        res: Any = fn(str(bundle), str(reference))
    except Exception:
        return None
    if isinstance(res, (int, float)):
        return float(res)
    if isinstance(res, dict):
        for k in ("overall", "score", "total"):
            if k in res:
                try:
                    return float(res[k])
                except (TypeError, ValueError):
                    return None
    return getattr(res, "overall", None)


# -- prompt coverage ---------------------------------------------------------

_IMPERATIVE = re.compile(
    r"\b(write|save|produce|report|compute|calculate|generate|create|output|"
    r"plot|export|list|rank|identify|find|return|include|summari[sz]e)\b", re.I)


def _unchecked_instructions(prompt: str, criteria: list) -> list[str]:
    """Sentences telling the agent to do something that no anchor covers."""
    anchors = [_norm(str(c.get("prompt_anchor") or "")) for c in criteria]
    anchors = [a for a in anchors if a]
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n{2,}", prompt):
        s = " ".join(sentence.split())
        if len(s) < 15 or not _IMPERATIVE.search(s):
            continue
        ns = _norm(s)
        if not any(a in ns or ns in a for a in anchors):
            out.append(s)
    return out


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


# -- completeness ledger -----------------------------------------------------

def _ledger(doc: dict, d: Path, prompt: str, mutations: list) -> list[tuple[str, str]]:
    ref = d / "grader" / "reference"
    have_ref = ref.is_dir() and any(ref.iterdir())
    delivs = doc.get("deliverables") or []
    schemas = [x for x in delivs if isinstance(x, dict) and x.get("schema")]
    return [
        ("prompt", "complete" if len(prompt.split()) >= 25 else "too thin"),
        ("deliverables", "complete" if delivs else "not stated"),
        ("column schemas", f"{len(schemas)} of {len(delivs)}" if delivs else "not stated"),
        ("reference answer", "attached" if have_ref else "not attached"),
        ("wrong-but-plausible", f"{len(mutations)} of {spec.MIN_MUTATIONS}"),
        ("environment", "complete" if (doc.get("environment") or {}).get("python") else "not pinned"),
        ("budget", "complete" if (doc.get("budget") or {}).get("wall_clock_s") else "not set"),
    ]
