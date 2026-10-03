"""Interactive contributor workflow; all judgments come from the hub."""
from pathlib import Path

from buildrix.hub_api import ApiError
from buildrix.interactive import ask, ask_block, ask_choice, confirm, para, rule, _submit
from buildrix.contribution_commands import import_skill, read_text


def metadata(meta, kind, current=None):
    current = current or {}
    rule("About the " + kind)
    body = {}
    text_fields = [("title", "Task title")] if kind == "task" else [
        ("name", "Package name"), ("description", "What the skill does and when to use it"),
        ("version", "Version"), ("license", "License")]
    for key, title in text_fields:
        default = current.get(key) or ({"version": "0.1.0", "license": "Apache-2.0"}.get(key, ""))
        body[key] = ask(title, default, required=True)
    for field, source, title in [
        ("domain", "domains", "Domain"),
        ("estimated_effort", "efforts" if kind == "task" else "effort_options", "Human effort"),
        ("complexity", "complexity_options", "Complexity"),
        ("task_familiarity", "task_familiarity", "Familiarity with this work"),
        ("agentic_familiarity", "agentic_familiarity", "Experience with AI agents"),
    ]:
        body[field] = ask_choice(title, [(str(r["id"]), r["label"]) for r in meta[source]],
                                 str(current.get(field) or ""))
    body["complexity"] = int(body["complexity"])
    return body


def pause(kind, draft):
    print(f"\nSaved. Resume here or on the website:\nbuildrix {kind} develop --resume {draft['id']}")
    return draft


def task_files(api, draft, definition):
    dimension = definition["id"]
    kind = definition.get("asset_kind")
    if not kind:
        print("This section does not collect files.")
        return draft
    assets = [a for a in draft.get("assets", []) if a.get("dimension") == dimension]
    for a in assets:
        print(f"  {a['id']}  {a['filename']}")
    action = ask_choice("Files", [("attach", "Attach files"), ("link", "Add shared link if files are above 50 MB"),
                                 ("notes", "Edit file notes"), ("remove", "Remove a file"), ("back", "Back")])
    if action in ("notes", "remove"):
        if not assets:
            return draft
        aid = ask_choice("File", [(a["id"], a["filename"]) for a in assets])
        url = f"/tasks/drafts/{draft['id']}/assets/{aid}"
        if action == "remove":
            return api.delete(url)
        if kind == "environment":
            print("Environment configuration files do not need separate notes.")
            return draft
        return api.patch(url, json_body=file_notes(kind))
    if action == "back":
        return draft
    if action == "link":
        body = {"filename": ask("File or folder name", required=True),
                "source_url": ask("HTTPS share link", required=True),
                "dimension": dimension, "kind": kind, **file_notes(kind)}
        return api.task_draft_link(draft["id"], body)
    paths = ask_block("File paths, one per line", "Paths may contain spaces.").splitlines()
    for raw in paths:
        path = Path(raw.strip().strip('"')).expanduser()
        if not path.is_file():
            print(f"File not found: {path}")
            continue
        print(f"\n{path.name}")
        notes = file_notes(kind)
        try:
            draft = api.task_draft_asset(draft["id"], path, dimension, kind, **notes)
        except ApiError as error:
            print(error)
    return draft


def file_notes(kind):
    if kind == "environment":
        return {"description": "", "usage": ""}
    return {"description": ask_block("What does this file contain?"),
            "usage": ask_block("Which parts should be used, and how?",
                              "Explain it so someone new to the project could work with it, including the units and conventions needed to read it.")}


def _show(value):
    return "" if value is None else str(value)


def scoring_table(record):
    """Build the Evaluation scoring table: 1 Score, then 2 Success.

    The hub's script checks the weights and values when the table is saved.
    """
    current = record.get("rubric") or record.get("rubric_start") or {}
    rule("Evaluation · 1 · Score")
    old_stages = current.get("stages") or [{}]
    count = int(ask("How many stages does the work have", str(len(old_stages)), required=True) or 1)
    stages = []
    for i in range(count):
        old = old_stages[i] if i < len(old_stages) else {}
        stage = {"name": "", "weight": 1, "dimensions": []}
        if count > 1:
            stage["name"] = ask(f"Stage {i + 1} name", old.get("name", ""), required=True)
            stage["weight"] = ask(f"Stage {i + 1} weight", _show(old.get("weight")), required=True)
        old_dims = old.get("dimensions") or [{}]
        for j in range(int(ask("How many dimensions" + (f" in {stage['name']}" if count > 1 else ""),
                               str(len(old_dims)), required=True) or 1)):
            d = old_dims[j] if j < len(old_dims) else {}
            print()
            name = ask("Dimension", d.get("name", ""), required=True)
            better = ask_choice("Scores 100 when the value is", [("lower", "at or below a value (<=)"),
                                                               ("higher", "at or above a value (>=)")],
                                d.get("better") or "lower")
            good, bad = ("<=", ">=") if better == "lower" else (">=", "<=")
            stage["dimensions"].append({
                "name": name, "better": better,
                "metric": ask("How is it calculated", d.get("metric", ""), required=True),
                "best":   ask(f"Scores 100 when {good}", _show(d.get("best")), required=True),
                "worst":  ask(f"Scores 0 when {bad}", _show(d.get("worst")), required=True),
                "weight": ask("Weight", _show(d.get("weight")), required=True),
            })
        stages.append(stage)

    rule("Evaluation · 2 · Success")
    listed = [x.get("name", "") for x in current.get("deliverables") or [] if x.get("name")]
    if listed:
        para("Must be delivered (from your Deliverables section): " + ", ".join(listed))
    extra = ask("Anything else that must be delivered? (comma-separated, Enter for none)")
    names = listed + [x.strip() for x in extra.split(",") if x.strip()]
    para("How good must it be? Give the passing condition for each dimension, and your own result.")
    for stage in stages:
        for d in stage["dimensions"]:
            sign = "<=" if d["better"] == "lower" else ">="
            old = next((o for s in current.get("stages") or [] for o in s.get("dimensions") or []
                        if o.get("name") == d["name"]), {})
            d["pass_line"] = ask(f"{d['name']}: passing condition {sign}", _show(old.get("pass_line")), required=True)
            d["own_value"] = ask(f"{d['name']}: your result", _show(old.get("own_value")), required=True)
    return {"deliverables": [{"name": n, "requirement": ""} for n in names], "stages": stages}


def run_task(api, draft, meta, seed_path=""):
    if not draft.get("initial_request"):
        rule("Task description")
        seed = Path(seed_path) / "prompt.md" if seed_path else None
        text = ""
        if seed and seed.is_file():
            para(read_text(seed))
            if confirm("Use this as your task description", True):
                text = read_text(seed)
        if not text:
            text = ask_block("Describe the real task as clearly and fully as you would when handing it to a teammate.")
        draft = api.task_draft_request(draft["id"], text)
    if draft.get("intake_notes"):
        para(draft["intake_notes"])
    definitions = meta["dimensions"]
    index = next((i for i, d in enumerate(definitions)
                  if draft["dimensions"].get(d["id"], {}).get("state") not in ("clear", "not_applicable")), 0)
    while True:
        definition = definitions[index]
        dim = definition["id"]
        record = draft.get("dimensions", {}).get(dim, {})
        rule(f"Revision · {index + 1}/{len(definitions)} · {definition['title']}")
        print(record.get("state", "").replace("_", " "))
        para(record.get("summary", ""))
        for question in record.get("questions", []):
            if not question.get("answered"):
                para(question.get("text", ""))
        if dim == "evaluation":
            options = [("table", "Fill in the scoring table"),
                       ("table-file", "Load the scoring table from a JSON file")]
        else:
            options = [("answer", "Answer the comments"), ("edit", "Replace this section")]
        options += [("view", "View current text"), ("include", "What to include")]
        if any(p.get("status") == "pending" for p in record.get("proposals", [])):
            options.append(("proposals", "Review suggested changes"))
        if definition.get("asset_kind"):
            options.append(("files", "Files and shared links"))
        options += [("review", "Review this section"), ("next", "Next section"), ("back", "Previous section"),
                    ("about", "Edit About the task"), ("description", "Edit task description"),
                    ("finish", "Final review and submit"), ("pause", "Save and exit")]
        action = ask_choice("Next action", options)
        try:
            if action == "pause":
                return pause("task", draft)
            if action == "view":
                para(record.get("content", ""))
            elif action == "include":
                para(definition.get("help", ""))
            elif action in ("next", "back"):
                index = (index + (1 if action == "next" else -1)) % len(definitions)
            elif action == "proposals":
                for proposal in record.get("proposals", []):
                    if proposal.get("status") != "pending":
                        continue
                    para(proposal.get("text", ""))
                    decision = ask_choice("Use this suggestion", [("accepted", "Accept"), ("rejected", "Reject")])
                    draft = api.task_draft_proposal(draft["id"], dim, proposal["id"], decision)
            elif action == "files":
                draft = task_files(api, draft, definition)
            elif action == "about":
                draft = api.task_draft_patch(draft["id"], metadata(meta, "task", draft["metadata"]))
            elif action == "description":
                text = ask_block("Updated task description")
                draft = api.task_draft_description(draft["id"], text)
            elif action in ("table", "table-file"):
                from buildrix.contribution_commands import read_json
                table = (scoring_table({**record, "rubric_start": draft.get("rubric_start")}) if action == "table"
                         else read_json(ask("JSON file path", required=True).strip('"')))
                draft = api.task_draft_dimension(draft["id"], dim, {"rubric": table, "review": True})
                if draft["dimensions"][dim].get("state") == "clear":
                    index = (index + 1) % len(definitions)
            elif action in ("answer", "edit", "review"):
                if action == "review":
                    body = {"content": record.get("content", ""), "review": True}
                else:
                    text = ask_block("Your answer" if action == "answer" else "Replacement section")
                    if not text.strip():
                        continue
                    body = {"answer" if action == "answer" else "content": text, "review": True}
                draft = api.task_draft_dimension(draft["id"], dim, body)
                updated = draft["dimensions"][dim]
                para(updated.get("content", ""))
                if updated.get("state") in ("clear", "not_applicable"):
                    index = (index + 1) % len(definitions)
            elif action == "finish":
                if not draft.get("complete"):
                    for item in draft.get("missing", []):
                        print(item["title"] + ": " + item["state"].replace("_", " "))
                    continue
                if not draft.get("canonical_prompt"):
                    draft = api.task_draft_finalize(draft["id"])
                rule("Revised task")
                para(draft["canonical_prompt"])
                if confirm("Edit this wording", False):
                    draft = api.task_draft_prompt(draft["id"], ask_block("Revised task"))
                result = _submit(draft, "task", api.task_draft_submit, api.task_draft)
                if result and result.get("task_id"):
                    return result
        except (ApiError, OSError, ValueError) as error:
            print(f"Could not save: {error}")
            # A multi-file upload may have saved some files before the error.
            draft = api.task_draft(draft["id"])


def skill_feedback(draft):
    rule("LLM feedback")
    para(draft.get("intake_notes", ""))
    points = [(key, rec) for key, rec in draft.get("dimensions", {}).items()
              if rec.get("state") not in ("clear", "not_applicable")]
    for key, rec in points:
        print("\n" + rec.get("title", key.replace("_", " ")))
        para(rec.get("summary", ""))
        for q in rec.get("questions", []):
            if not q.get("answered"):
                para(q.get("text", ""))
        if not confirm("Show the next comment", True):
            break
    if not points:
        print("No open section comments.")
    for blocker in draft.get("validation", {}).get("blocking", []):
        para(blocker)


def run_skill(api, draft, meta, seed_path=""):
    if seed_path:
        draft = import_skill(api, seed_path, draft["id"])
    while True:
        rule("Skill details")
        print(draft["metadata"].get("name", ""))
        action = ask_choice("Next action", [
            ("package", "Upload or replace a skill folder / zip"),
            ("instructions", "Write or replace SKILL.md instructions"),
            ("support", "Attach a supporting file"), ("remove", "Remove a supporting file"),
            ("view", "View instructions and files"), ("about", "Edit About the skill"),
            ("review", "Get LLM feedback"), ("feedback", "Read saved feedback"),
            ("finish", "Review and submit"), ("pause", "Save and exit")])
        try:
            if action == "pause":
                return pause("skill", draft)
            if action == "package":
                draft = import_skill(api, ask("Folder or zip path", required=True).strip('"'), draft["id"])
            elif action == "instructions":
                source = ask("SKILL.md path, or Enter to type", "")
                text = read_text(source.strip('"')) if source else ask_block(
                    "Skill instructions", "Explain when to use it, required inputs, the procedure, expected results and checks. Reference supporting files by their relative paths.")
                draft = api.skill_draft_md(draft["id"], text)
            elif action == "support":
                path = Path(ask("File path", required=True).strip('"')).expanduser()
                kind = ask_choice("File role", [(r["id"], r["folder"]) for r in meta["asset_kinds"]])
                draft = api.skill_draft_asset(draft["id"], path, kind)
            elif action == "remove":
                assets = draft.get("assets", [])
                if assets:
                    aid = ask_choice("File", [(r["id"], r["filename"]) for r in assets])
                    draft = api.delete(f"/skills/drafts/{draft['id']}/assets/{aid}")
            elif action == "view":
                para(draft.get("skill_md", ""))
                for file in draft.get("files", []):
                    print(file.get("path", ""))
            elif action == "about":
                draft = api.skill_draft_patch(draft["id"], metadata(meta, "skill", draft["metadata"]))
            elif action == "review":
                draft = api.skill_draft_review_package(draft["id"])
                skill_feedback(draft)
            elif action == "feedback":
                skill_feedback(draft)
            elif action == "finish":
                if not draft.get("intake_model"):
                    draft = api.skill_draft_review_package(draft["id"])
                skill_feedback(draft)
                if draft.get("validation", {}).get("blocking"):
                    continue
                rule("Review and submit")
                para(draft.get("skill_md", ""))
                result = _submit(draft, "skill", api.skill_draft_submit, api.skill_draft)
                if result and result.get("skill_id"):
                    return result
        except (ApiError, OSError, ValueError) as error:
            print(f"Could not save: {error}")
            draft = api.skill_draft(draft["id"])


def run(api, kind, resume="", seed_path=""):
    api.me()
    meta = getattr(api, kind + "_meta")()
    if resume:
        draft = getattr(api, kind + "_draft")(resume)
        if draft.get("status") == "abandoned":
            print("This contribution was withdrawn. Its history is retained; start a new draft to contribute.")
            return draft
        if draft.get("status") == "submitted":
            print("This contribution is submitted. Use revise to open it for changes.")
            return draft
    else:
        draft = getattr(api, kind + "_draft_create")(metadata(meta, kind))
    print(f"\nDraft {draft['id']} · {draft.get(kind + '_code', '')}")
    print(f"Resume at any time: buildrix {kind} develop --resume {draft['id']}")
    if not meta.get("llm_available"):
        print("The hub's LLM reviewer is currently unavailable. Edits can be saved; review needs a configured model.")
    return (run_task if kind == "task" else run_skill)(api, draft, meta, seed_path)

