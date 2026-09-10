"""
The v2 command set: task · skill · benchmark.
=============================================

Two vocabularies, one mental model:

    Discover:  search → show → pull
    Develop:   init → validate → submit

Every command here talks to the hub's shared API. ``init`` opens a draft and
drives the same endpoints the website drives; ``validate`` asks the hub to run
the canonical rules, falling back to the local checks only when the hub is not
reachable; ``benchmark run`` executes locally and uploads automatically.

Batch is the default, not a separate mode: anything that takes one name takes
several, and paths accept globs, so ``buildrix skill pull a b c`` and
``buildrix skill validate ./skills/*`` work without a second vocabulary.
"""

from __future__ import annotations

import glob
import io
import json
import sys
import zipfile
from pathlib import Path

from buildrix.hub_api import ApiError, BuildrixAPI
from buildrix.interactive import C, ask, confirm, para, rule


# ═══════════════════════════════════════════════════════════════════════════
#  Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

def _api() -> BuildrixAPI:
    return BuildrixAPI()


def _fail(message: str) -> int:
    print(C.red(f"  {message}"))
    return 1


def _need_login() -> int:
    print()
    print(C.red("  Not signed in."))
    para(C.dim("Run `buildrix auth login`. The CLI and the website share one "
               "account — a draft started in either shows up in the other."))
    print()
    return 1


def _expand(paths: list[str]) -> list[Path]:
    """Globs and directories, so batch works without a batch command."""
    out: list[Path] = []
    for raw in paths:
        hits = glob.glob(raw)
        if hits:
            out.extend(Path(h) for h in sorted(hits))
        else:
            out.append(Path(raw))
    return out


def _write_bytes(dest: Path, data: bytes, extract: bool) -> Path:
    """Save an archive, or unpack it.

    Buildrix packages already contain their own top-level folder, so extracting
    goes to the parent directory — unpacking into a folder named after the zip
    would nest the package inside a copy of its own name.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not extract:
        dest.write_bytes(data)
        return dest
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        roots = {Path(n).parts[0] for n in z.namelist() if n.strip()}
        target = dest.parent if len(roots) == 1 else dest.with_suffix("")
        target.mkdir(parents=True, exist_ok=True)
        z.extractall(target)
        return target / roots.pop() if len(roots) == 1 else target


def _band_colour(band: str):
    return {"strong": C.green, "possible": C.amber}.get(band, C.dim)


# ═══════════════════════════════════════════════════════════════════════════
#  task
# ═══════════════════════════════════════════════════════════════════════════

def task_search(args) -> int:
    api = _api()
    try:
        rows = api.task_search(query=getattr(args, "query", "") or "",
                               domain=args.domain, difficulty=args.difficulty,
                               limit=args.limit)
    except ApiError as e:
        return _fail(str(e))
    if not rows:
        print("\n  No tasks matched.\n")
        return 0
    print()
    for r in rows:
        code = r.get("task_code") or r.get("id", "")
        print(f"  {C.cyan(code):<22} {r.get('name', '')}")
        print(f"  {'':<14} {C.dim(r.get('domain', ''))} · "
              f"{C.dim(r.get('difficulty', ''))} · "
              f"{C.dim(r.get('strength', ''))}")
        desc = (r.get("description") or "").replace("\n", " ")
        if desc:
            para(C.dim(desc[:150]), indent="                 ")
        print()
    print(f"  {len(rows)} task(s). "
          f"{C.dim('buildrix task show <code>')}\n")
    return 0


def task_show(args) -> int:
    api = _api()
    code = 0
    for ref in args.refs:
        try:
            t = api.task_show(ref)
        except ApiError as e:
            code = _fail(f"{ref}: {e}")
            continue
        rule(t.get("task_code") or ref)
        print(f"  {C.bold(t.get('name', ''))}")
        print(f"  {C.dim(t.get('domain', ''))} · {C.dim(t.get('difficulty', ''))}"
              f" · {C.dim(t.get('strength', ''))}"
              f" · by {C.dim(t.get('author_name', 'unknown'))}")
        if t.get("estimated_effort"):
            print(f"  {C.dim('expert effort: ' + t['estimated_effort'].replace('_', ' '))}")

        print()
        para(C.bold("Prompt the agent receives"))
        para(t.get("canonical_prompt") or "(none)", indent="    ")

        dims = (t.get("structured_task") or {}).get("dimensions") or {}
        if dims:
            print()
            para(C.bold("Definition"))
            for key, rec in dims.items():
                title = rec.get("title", key)
                if rec.get("withheld"):
                    print(f"    {C.dim(title + ': held on the hub')}")
                    continue
                body = (rec.get("content") or "").replace("\n", " ")
                if body:
                    print(f"    {C.cyan(title)}")
                    para(C.dim(body[:220]), indent="      ")
        if t.get("withheld_reason"):
            print()
            para(C.dim(t["withheld_reason"]), indent="    ")
        if t.get("instances"):
            print()
            para(C.bold(f"Instances ({len(t['instances'])})"))
            for i in t["instances"]:
                print(f"    · {i.get('label') or i.get('key')}")
        print()
    return code


def task_pull(args) -> int:
    api = _api()
    dest_dir = Path(args.dir)
    code = 0
    for ref in args.refs:
        try:
            data = api.task_package(ref)
        except ApiError as e:
            code = _fail(f"{ref}: {e}")
            continue
        out = _write_bytes(dest_dir / f"{ref}.zip", data, args.extract)
        print(f"  {C.green('pulled')} {ref} → {out}")
    print()
    return code


def task_init(args) -> int:
    from buildrix.config import get_token
    from buildrix.interactive import run_task_init
    if not get_token():
        return _need_login()
    try:
        run_task_init(_api(), resume=getattr(args, "resume", "") or "")
    except ApiError as e:
        return _fail(str(e))
    return 0


def task_validate(args) -> int:
    """Validate a local task folder.

    The hub owns the canonical rules; this runs the packaged checks, which are
    the same gates the hub applies, so the answer is available offline too.
    """
    from buildrix.checks import check_task
    from buildrix.report import render, supports_color
    worst = 0
    for path in _expand(args.paths):
        rep = check_task(str(path), run_grader=not args.no_grader)
        print(render(rep, color=supports_color()))
        worst = max(worst, rep.exit_code)
    if worst == 0:
        print(f"  {C.green('ready')}  buildrix task submit\n")
    return worst


def task_submit(args) -> int:
    """Submit a local task folder through the shared workflow.

    A folder submitted here goes through the same definition as `task init`:
    the hub reads it, states each dimension, and asks about whatever is
    missing. There is no path that skips the workflow.
    """
    from buildrix.config import get_token
    if not get_token():
        return _need_login()
    print()
    para("Task submission runs through the guided definition, so a Task built "
         "in a terminal and one built in a browser are the same Task.")
    para(C.dim("Starting the workflow. Your folder's prompt.md, if there is one, "
               "is offered as the initial agent request."))
    seed = ""
    for path in _expand(args.paths):
        candidate = path / "prompt.md"
        if candidate.is_file():
            seed = candidate.read_text(encoding="utf-8", errors="replace").strip()
            print(C.dim(f"\n  Read {candidate}."))
            break
    from buildrix.interactive import run_task_init
    try:
        run_task_init(_api(), resume=getattr(args, "resume", "") or "")
    except ApiError as e:
        return _fail(str(e))
    return 0


def task_archive(args) -> int:
    """Archive your own draft or task. The history is kept — that is the point."""
    api = _api()
    code = 0
    for ref in args.refs:
        try:
            api.task_draft_abandon(ref)
            print(f"  {C.green('archived')} {ref}")
        except ApiError as e:
            code = _fail(f"{ref}: {e}")
    print()
    return code


# ═══════════════════════════════════════════════════════════════════════════
#  skill
# ═══════════════════════════════════════════════════════════════════════════

def skill_search(args) -> int:
    api = _api()
    try:
        rows = api.skill_search(query=getattr(args, "query", "") or "",
                                domain=args.domain, limit=args.limit)
    except ApiError as e:
        return _fail(str(e))
    if not rows:
        print("\n  No skills matched.\n")
        return 0
    print()
    for s in rows:
        print(f"  {C.cyan(s.get('name', '')):<34} {C.dim(s.get('domain', ''))}")
        para(C.dim((s.get("description") or "")[:150]), indent="    ")
        print(f"    {C.dim('v' + str(s.get('version', '')))} · "
              f"{C.dim(str(s.get('download_count', 0)) + ' downloads')} · "
              f"{C.dim(s.get('status', ''))}")
        print()
    print(f"  {len(rows)} skill(s). {C.dim('buildrix skill show <name>')}\n")
    return 0


def skill_show(args) -> int:
    api = _api()
    code = 0
    for ref in args.refs:
        try:
            s = api.skill_show(ref)
        except ApiError as e:
            code = _fail(f"{ref}: {e}")
            continue
        rule(s.get("name", ref))
        para(s.get("description", ""))
        print(f"\n  {C.dim(s.get('domain', ''))} · v{s.get('version', '')} · "
              f"{C.dim(s.get('status', ''))} · by {C.dim(s.get('author_name', ''))}")
        md = s.get("skill_md_content") or ""
        if md:
            print()
            para(C.dim(md[:1200]), indent="    ")
        try:
            summary = api.benchmark_skill_summary(s.get("name", ref)).get("summary")
            if summary and summary.get("groups"):
                print()
                para(C.bold("Benchmarked"))
                for cid, row in (summary.get("conditions") or {}).items():
                    score = row.get("mean_score")
                    shown = "—" if score is None else str(round(score * 100))
                    print(f"    {row.get('label', cid):<28} {shown}")
        except ApiError:
            pass
        print()
    return code


def skill_pull(args) -> int:
    api = _api()
    dest_dir = Path(args.dir)
    code = 0
    for ref in args.refs:
        try:
            s = api.skill_show(ref)
            data = api.skill_download(s["id"])
        except ApiError as e:
            code = _fail(f"{ref}: {e}")
            continue
        out = _write_bytes(dest_dir / f"{s['name']}.zip", data, args.extract)
        print(f"  {C.green('pulled')} {s['name']} → {out}")
    print()
    return code


def skill_init(args) -> int:
    from buildrix.config import get_token
    from buildrix.interactive import run_skill_init
    if not get_token():
        return _need_login()
    try:
        run_skill_init(_api(), resume=getattr(args, "resume", "") or "")
    except ApiError as e:
        return _fail(str(e))
    return 0


def _zip_folder(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_dir() or set(p.parts) & {"__pycache__", ".git"}:
                continue
            z.write(p, f"{folder.name}/{p.relative_to(folder).as_posix()}")
    return buf.getvalue()


def skill_validate(args) -> int:
    """Validate skill packages against the canonical rules.

    The hub is authoritative — it runs the same rules on submission, so asking
    it here means the answer cannot disagree with the answer you get later. If
    the hub is unreachable, the packaged local checks run instead and say so.
    """
    api = _api()
    worst = 0
    for path in _expand(args.paths):
        if not path.exists():
            worst = max(worst, _fail(f"{path} does not exist."))
            continue
        rule(path.name)
        try:
            if path.is_dir():
                blob = _zip_folder(path)
                tmp = Path(path.parent / f".{path.name}.buildrix.zip")
                tmp.write_bytes(blob)
                try:
                    report = api.skill_validate(tmp)
                finally:
                    tmp.unlink(missing_ok=True)
            else:
                report = api.skill_validate(path)
        except ApiError as e:
            print(C.amber(f"  The hub could not be reached ({e})."))
            print(C.dim("  Running the packaged checks instead — the hub is the "
                        "authority, so re-run this when you are online.\n"))
            worst = max(worst, _local_skill_check(path, args))
            continue

        for b in report.get("blockers") or []:
            print(f"  {C.red('blocker')}  {b}")
        for c in report.get("concerns") or []:
            print(f"  {C.amber('concern')}  {c}")
        info = report.get("info") or {}
        if info.get("context_cost_tokens"):
            print(f"  {C.dim('context cost')} ~{info['context_cost_tokens']} tokens")
        if report.get("ok"):
            print(f"  {C.green('ok')}       every mechanical rule passes")
        else:
            worst = 1
        print()
    return worst


def _local_skill_check(path: Path, args) -> int:
    from buildrix.checks import check_skill
    from buildrix.report import render, supports_color
    rep = check_skill(str(path), run_tests=not getattr(args, "no_tests", False))
    print(render(rep, color=supports_color()))
    return rep.exit_code


def skill_submit(args) -> int:
    """Submit skill packages through the shared authoring workflow.

    An existing folder is imported into a draft rather than uploaded blind: the
    sections it already has come back resolved, whatever is missing gets asked
    about, and the reusability check still runs. That is what keeps a package
    from GitHub identical in standard to one authored in a browser.
    """
    from buildrix.config import get_token
    if not get_token():
        return _need_login()
    api = _api()
    code = 0
    for path in _expand(args.paths):
        if not path.exists():
            code = _fail(f"{path} does not exist.")
            continue
        rule(path.name)
        try:
            if path.is_dir():
                blob = _zip_folder(path)
                tmp = Path(path.parent / f".{path.name}.buildrix.zip")
                tmp.write_bytes(blob)
                try:
                    draft = api.skill_import(tmp)
                finally:
                    tmp.unlink(missing_ok=True)
            else:
                draft = api.skill_import(path)
        except ApiError as e:
            code = _fail(str(e))
            continue

        report = draft.get("import_report") or {}
        for b in report.get("blockers") or []:
            print(f"  {C.red('blocker')}  {b}")
        for c in report.get("concerns") or []:
            print(f"  {C.amber('concern')}  {c}")
        print(f"\n  Imported as draft {C.cyan(draft['skill_code'])}.")

        if draft.get("complete") and not (draft.get("validation") or {}).get("blocking"):
            if confirm("  submit it now", True):
                try:
                    result = api.skill_draft_submit(draft["id"])
                    print(C.green(f"\n  {result.get('skill_code')} submitted "
                                  f"as {result.get('name')}."))
                    _print_review(result)
                except ApiError as e:
                    code = _fail(str(e))
                continue

        print()
        para("The package needs a few things filled in before it can be "
             "submitted. Continuing in the guided workflow.")
        from buildrix.interactive import run_skill_init
        try:
            run_skill_init(api, resume=draft["id"])
        except ApiError as e:
            code = _fail(str(e))
    return code


def _print_review(result: dict) -> None:
    verdict = result.get("llm_review_status", "")
    if not verdict or verdict == "none":
        return
    colour = {"accepted": C.green, "minor_revision": C.amber,
              "major_revision": C.red, "rejected": C.red}.get(verdict, C.dim)
    print(f"  admissibility review: {colour(verdict.replace('_', ' '))}")
    if result.get("llm_review_comments"):
        para(C.dim(result["llm_review_comments"][:600]))


def skill_archive(args) -> int:
    api = _api()
    code = 0
    for ref in args.refs:
        try:
            api.skill_draft_abandon(ref)
            print(f"  {C.green('archived')} {ref}")
        except ApiError as e:
            code = _fail(f"{ref}: {e}")
    print()
    return code


# ═══════════════════════════════════════════════════════════════════════════
#  benchmark
# ═══════════════════════════════════════════════════════════════════════════

def _skill_payload_from_path(path: Path) -> dict:
    """Read enough of a local Skill for the matcher to judge it.

    Matching has to work before a Skill is published — otherwise `benchmark
    match` would only help people who had already committed to a Skill, which
    is backwards.
    """
    from buildrix.checks.skill import _FRONTMATTER  # same parsing as the checks
    import re
    import yaml

    md = path / "SKILL.md" if path.is_dir() else None
    if md is None or not md.is_file():
        return {}
    text = md.read_text(encoding="utf-8", errors="replace")
    m = _FRONTMATTER.match(text)
    fm, body = ({}, text)
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body = m.group(2)

    sections: dict[str, str] = {}
    heads = list(re.finditer(r"^##\s+(.+?)\s*$", body, re.M))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        sections[h.group(1).strip()] = body[h.end():end].strip()

    meta = fm.get("metadata") or {}
    sk = path / "skill.yaml"
    if sk.is_file():
        try:
            meta = {**meta, **(yaml.safe_load(sk.read_text(encoding="utf-8")) or {})}
        except yaml.YAMLError:
            pass
    return {
        "name": fm.get("name") or path.name,
        "description": fm.get("description", ""),
        "domain": meta.get("domain", ""),
        "purpose": sections.get("Purpose", "") or sections.get("Overview", ""),
        "when_to_use": sections.get("When to Use", "") or sections.get("When to use", ""),
        "workflow": sections.get("Workflow", ""),
        "requirements": meta.get("requires", {}) or {},
        "version": str(meta.get("version", "")),
    }


def benchmark_match(args) -> int:
    api = _api()
    body: dict = {"limit": args.limit, "task_domain": args.domain}
    skill_path = None
    if args.skill:
        p = Path(args.skill)
        if p.exists():
            skill_path = p
            payload = _skill_payload_from_path(p)
            if not payload:
                return _fail(f"{p} has no SKILL.md — is it a Skill folder?")
            body.update(payload)
        else:
            body["skill_name"] = args.skill

    try:
        result = api.benchmark_match(body)
    except ApiError as e:
        return _fail(str(e))

    matches = result.get("matches") or []
    rule(f"tasks for {result.get('skill', {}).get('name', args.skill)}")
    if result.get("analyser") == "lexical-fallback":
        para(C.amber(
            "The hub has no model configured, so these were ranked by word "
            "overlap rather than by reading. Treat the order as a hint."))
        print()
    if not matches:
        para("No published Tasks to match against yet.")
        print()
        return 0

    for m in matches:
        colour = _band_colour(m["band"])
        code = m.get("task_code") or m.get("task_id")
        print(f"  {C.cyan(code):<22} {m.get('name', '')[:40]:<42} "
              f"{colour(m['band'].title() + ' match')}")
        if m.get("reason"):
            para(C.dim(m["reason"]), indent="      ")
        for c in m.get("concerns") or []:
            para(C.amber("· " + c), indent="      ")
    print()
    strong = [m for m in matches if m["band"] in ("strong", "possible")]
    if strong:
        codes = " ".join(m.get("task_code") or m["task_id"] for m in strong[:3])
        para(C.dim(f"buildrix benchmark run --skill {args.skill} --task {codes}"))
    print()
    return 0


def benchmark_run(args) -> int:
    from buildrix.bench import (
        CommandAgent, DryRunAgent, print_result, run_benchmark,
    )
    from buildrix.config import get_token
    if not get_token():
        return _need_login()

    skill_path = Path(args.skill) if args.skill else None
    if skill_path and not skill_path.exists():
        return _fail(f"{skill_path} does not exist.")
    payload = _skill_payload_from_path(skill_path) if skill_path else {}
    skill_name = payload.get("name") or (skill_path.name if skill_path else "")

    if not args.task:
        return _fail("Give at least one --task. "
                     "`buildrix benchmark match --skill <path>` suggests some.")

    if args.agent:
        agent = CommandAgent(args.agent, timeout_s=args.timeout)
    else:
        print()
        para(C.amber("No --agent command was given, so this is a dry run."))
        para(C.dim("It exercises the isolation, the evaluator and the upload, but "
                   "produces no work, so every condition scores zero. The run is "
                   "recorded privately so it cannot be mistaken for a measurement."))
        agent = DryRunAgent()

    api = _api()
    print()
    para(C.dim("Four conditions per Task instance, each in its own clean "
               "workspace: Task · +Detailed Instruction · +Skill · +both. "
               "Results upload automatically when the run finishes."))
    print()

    try:
        responses = run_benchmark(
            api,
            skill_path=skill_path, skill_name=skill_name,
            skill_version=payload.get("version", ""),
            task_refs=args.task, agent=agent,
            model=args.model, harness=args.harness,
            budget={"wall_clock_s": args.timeout},
            visibility="private" if not args.agent else args.visibility,
        )
    except ApiError as e:
        return _fail(str(e))

    for r in responses:
        print_result(r)
    failed = [r for r in responses if r.get("error")]
    return 1 if failed else 0


def benchmark_pull(args) -> int:
    api = _api()
    try:
        if args.skill and not args.task:
            data = api.benchmark_skill_summary(args.skill)
            _print_skill_summary(args.skill, data)
        else:
            data = api.benchmark_results(skill=args.skill or "",
                                         task=args.task or "",
                                         model=args.model or "",
                                         limit=args.limit)
            _print_results(data)
    except ApiError as e:
        return _fail(str(e))
    if args.json:
        print(json.dumps(data, indent=2))
    return 0


def _print_skill_summary(name: str, data: dict) -> None:
    rule(f"benchmark · {name}")
    summary = data.get("summary") or {}
    if not summary.get("groups"):
        para("No benchmark runs recorded for this Skill yet.")
        print()
        return
    print(C.dim(f"  {summary['groups']} run group(s)\n"))
    for cid, row in (summary.get("conditions") or {}).items():
        score = row.get("mean_score")
        shown = "—" if score is None else str(round(score * 100))
        print(f"  {row.get('label', cid):<28} {C.bold(shown.rjust(3))}")
    print()
    for label, key in (("Instruction Lift", "instruction_lift"),
                       ("Skill Lift", "skill_lift"),
                       ("Combined Lift", "combined_lift")):
        v = summary.get(key)
        if v is None:
            continue
        pts = round(v * 100)
        colour = C.green if pts > 0 else (C.red if pts < 0 else C.dim)
        print(f"  {label:<28} {colour(('+' if pts > 0 else '') + str(pts))}")
    by_task = data.get("by_task") or []
    if by_task:
        print()
        para(C.bold("By task"))
        for row in by_task:
            lift = row.get("skill_lift")
            shown = "—" if lift is None else f"{round(lift * 100):+d}"
            print(f"    {C.cyan(row['task']):<22} skill lift {shown}"
                  f"   {C.dim(str(row['groups']) + ' run(s)')}")
    print()


def _print_results(data: dict) -> None:
    groups = data.get("groups") or []
    rule("benchmark results")
    if not groups:
        para("Nothing recorded yet.")
        print()
        return
    for g in groups:
        print(f"  {C.cyan(g['task']['code'] or g['task']['id']):<20} "
              f"{g['skill']['name']:<26} {C.dim(g.get('model', ''))}")
        cells = []
        for cond in g.get("conditions") or []:
            score = cond.get("score")
            cells.append(f"{cond['label']} "
                         + ("—" if score is None else str(round(score * 100))))
        para(C.dim(" · ".join(cells)), indent="    ")
    summary = data.get("summary") or {}
    if summary.get("skill_lift") is not None:
        print()
        print(f"  {C.bold('mean skill lift')} "
              f"{round(summary['skill_lift'] * 100):+d} "
              f"{C.dim('across ' + str(summary.get('groups', 0)) + ' group(s)')}")
    print()


# ═══════════════════════════════════════════════════════════════════════════
#  Dispatch tables
# ═══════════════════════════════════════════════════════════════════════════

TASK_V2 = {
    "search": task_search, "show": task_show, "pull": task_pull,
    "init": task_init, "validate": task_validate, "submit": task_submit,
    "archive": task_archive,
}

SKILL_V2 = {
    "search": skill_search, "show": skill_show, "pull": skill_pull,
    "init": skill_init, "validate": skill_validate, "submit": skill_submit,
    "archive": skill_archive,
}

BENCHMARK_V2 = {
    "match": benchmark_match, "run": benchmark_run, "pull": benchmark_pull,
}
