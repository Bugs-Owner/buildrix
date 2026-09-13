"""Commands for the shared web/terminal contribution API.

The server owns metadata choices, questions, validation, history and review.
JSON commands are usable from an agent without pretending to be a terminal.
"""
from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path

from buildrix.hub_api import ApiError, BuildrixAPI


def add_commands(skill, task):
    for kind, commands in (("skill", skill), ("task", task)):
        q = commands.add_parser("develop", help="Develop a contribution or resume its saved draft")
        q.add_argument("--resume", default="")
        q.set_defaults(workflow_command=True)
        q = commands.add_parser("revise", help="Reopen your submitted contribution for a new review")
        q.add_argument("ref", help="Published ID or catalog code")
        q.add_argument("--json", action="store_true", help="Return the editable draft without opening the wizard")
        q.set_defaults(workflow_command=True)
        q = commands.add_parser("drafts", help="List your drafts and submitted contributions")
        q.set_defaults(workflow_command=True)
        q = commands.add_parser("history", help="Read your private, original input log")
        q.add_argument("draft_id")
        q.set_defaults(workflow_command=True)
        q = commands.add_parser("withdraw", help="Withdraw an unfinished contribution")
        q.add_argument("draft_id")
        q.set_defaults(workflow_command=True)
        q = commands.add_parser("draft", help="Work with the same saved draft as the web (JSON responses)")
        actions = q.add_subparsers(dest="action", required=True)
        for action in ("meta", "create", "get", "patch", "describe", "answer", "edit",
                       "upload", "link", "asset-notes", "remove-file", "review",
                       "finalize", "prompt", "instructions", "requirements",
                       "package", "download", "proposal", "submit", "log", "withdraw",
                       "start-session", "log-local", "sync-local", "capture-initial"):
            if kind == "task" and action in {"instructions", "requirements", "package", "download"}:
                continue
            if kind == "skill" and action in {"answer", "edit", "link", "asset-notes", "finalize", "prompt", "proposal", "capture-initial"}:
                continue
            a = actions.add_parser(action)
            a.set_defaults(workflow_command=True)
            a.add_argument("--context", default="", help="JSON file with private client-reported source metadata")
            a.add_argument("--journal", required=action in {"start-session", "log-local", "sync-local", "capture-initial"},
                           default="", help="Local contribution journal; sync automatically before draft actions")
            if action not in ("meta", "create"):
                a.add_argument("draft_id")
            if action in ("create", "patch", "link", "asset-notes", "requirements"):
                a.add_argument("--data", required=True, help="UTF-8 JSON file containing the request fields")
            if action in ("describe", "answer", "edit", "prompt", "instructions", "log-local", "capture-initial"):
                a.add_argument("--text-file", required=True, help="UTF-8 text, sent without rewriting")
            if action in ("answer", "edit"):
                a.add_argument("--dimension", required=True)
            if action == "proposal":
                a.add_argument("--dimension", required=True)
                a.add_argument("--proposal-id", required=True)
                a.add_argument("--decision", required=True, choices=["accepted", "rejected"])
                a.add_argument("--text-file", default="", help="Optional replacement wording")
            if action == "review":
                a.add_argument("--dimension", default="", help="Task section to review, or all sections")
            if action == "upload":
                a.add_argument("--file", required=True)
                a.add_argument("--data", required=True, help="JSON file with dimension, kind, description and usage")
            if action in ("asset-notes", "remove-file"):
                a.add_argument("--asset", required=True)
            if action == "package":
                a.add_argument("--file", required=True, help="Skill folder or archive")
            if action == "download":
                a.add_argument("--out", required=True, help="New destination zip file")
            if action == "submit":
                a.add_argument("--consent", action="store_true", required=True,
                               help="Agree to retain the definition history and aggregate research use")
            if action == "capture-initial":
                a.add_argument("--assistance", required=True, choices=["unassisted", "assisted", "unknown"])
            if action == "log-local":
                a.add_argument("--role", required=True, choices=["human", "assistant"])
                a.add_argument("--purpose", required=True, choices=["initial_prompt", "initial_response",
                    "clarification_question", "clarification_answer", "revision_proposed",
                    "revision_accepted", "artifact_edited", "hub_feedback", "message"])
                a.add_argument("--reply-to", default="")
                a.add_argument("--dimension", default="")


def read_json(path):
    with Path(path).open(encoding="utf-8-sig") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError("The JSON file must contain an object.")
    return value


def read_text(path):
    # Preserve whitespace and newlines in the user's source.
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return f.read()


def import_skill(api, path, draft_id):
    path = Path(path).expanduser()
    if not path.is_dir():
        return api.skill_import(path, draft_id=draft_id)
    if not (path / "SKILL.md").is_file():
        raise ValueError("The skill folder must contain SKILL.md.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(path.rglob("*")):
            if file.is_file() and not file.is_symlink() and not set(file.relative_to(path).parts) & {".git", "__pycache__", ".venv"}:
                archive.write(file, file.relative_to(path).as_posix())
    with tempfile.TemporaryDirectory(prefix="buildrix-skill-") as temp:
        archive = Path(temp) / "skill.zip"
        archive.write_bytes(buf.getvalue())
        return api.skill_import(archive, draft_id=draft_id)


def draft_action(api, kind, args):
    action = args.action
    from buildrix import local_interactions as local
    journal = getattr(args, "journal", "")
    context = getattr(args, "context", "")
    if context:
        if journal and action != "start-session":
            raise ValueError("The journal supplies its immutable context; omit --context")
        api.client_context = read_json(context)
    if action == "start-session":
        if not context:
            raise ValueError("start-session requires --context with harness and skill provenance")
        return local.start(journal, api, kind, args.draft_id, api.client_context)
    if action in {"log-local", "capture-initial"}:
        if action == "log-local" and kind == "task" and args.purpose == "initial_response":
            raise ValueError("Use capture-initial to preserve the task's initial response before assistance")
        return local.record(journal, api, kind, args.draft_id, text=read_text(args.text_file),
            role="human" if action == "capture-initial" else args.role,
            purpose="initial_response" if action == "capture-initial" else args.purpose,
            reply_to=getattr(args, "reply_to", ""), dimension=getattr(args, "dimension", ""),
            assistance=getattr(args, "assistance", None))
    if journal:
        if action in {"meta", "create"}:
            raise ValueError("Create the draft before starting its journal; use --context here")
        receipt = local.sync(journal, api, kind, args.draft_id)
        if action == "sync-local":
            return receipt
    base = f"/{kind}s/drafts"
    if action == "meta":
        return api.get(f"/{kind}s/meta")
    if action == "create":
        return api.post(base, json_body=read_json(args.data))
    url = base + "/" + args.draft_id
    if action == "get":
        return api.get(url)
    if action == "patch":
        return api.patch(url, json_body=read_json(args.data))
    if action == "describe":
        text = read_text(args.text_file)
        if kind == "task":
            draft = api.get(url)
            if draft.get("initial_request"):
                return api.task_draft_description(args.draft_id, text)
            return api.task_draft_request(args.draft_id, text)
        return api.skill_draft_md(args.draft_id, text)
    if action in ("answer", "edit"):
        text = read_text(args.text_file)
        if kind == "task":
            return api.task_draft_dimension(args.draft_id, args.dimension,
                                           {"answer" if action == "answer" else "content": text, "review": True})
        raise ValueError("Revise the skill instructions or package, then run draft review.")
    if action == "upload":
        data = read_json(args.data)
        if kind == "task":
            return api.task_draft_asset(args.draft_id, Path(args.file),
                                       data["dimension"], data["kind"], data.get("description", ""), data.get("usage", ""))
        return api.skill_draft_asset(args.draft_id, Path(args.file), data["kind"], data.get("description", ""))
    if action in ("link", "asset-notes"):
        if kind != "task":
            raise ValueError("Shared links and file notes apply to task files. Bundle skill resources in its package.")
        suffix = "/asset-links" if action == "link" else "/assets/" + args.asset
        return (api.post if action == "link" else api.patch)(url + suffix, json_body=read_json(args.data))
    if action == "remove-file":
        return api.delete(url + "/assets/" + args.asset)
    if action == "review":
        if kind == "skill":
            return api.skill_draft_review_package(args.draft_id)
        if args.dimension:
            draft = api.get(url)
            record = draft.get("dimensions", {}).get(args.dimension)
            if record is None:
                raise ValueError("Unknown task dimension. See draft meta.")
            return api.task_draft_dimension(args.draft_id, args.dimension,
                                           {"content": record.get("content", ""), "review": True})
        return api.post(url + "/answers", json_body={"answers": [], "reanalyse": True}, timeout=300)
    if action == "proposal":
        return api.task_draft_proposal(args.draft_id, args.dimension, args.proposal_id,
                                      args.decision, read_text(args.text_file) if args.text_file else "")
    if action == "finalize":
        if kind != "task":
            raise ValueError("Skill instructions are authored in files. Use draft review, then draft submit.")
        return api.task_draft_finalize(args.draft_id)
    if action == "prompt" and kind == "task":
        return api.task_draft_prompt(args.draft_id, read_text(args.text_file))
    if action == "instructions" and kind == "skill":
        return api.skill_draft_md(args.draft_id, read_text(args.text_file))
    if action == "requirements" and kind == "skill":
        return api.skill_draft_requirements(args.draft_id, read_json(args.data))
    if action == "package" and kind == "skill":
        return import_skill(api, args.file, args.draft_id)
    if action == "download" and kind == "skill":
        data = api.skill_draft_package(args.draft_id)
        with Path(args.out).open("xb") as file:
            file.write(data)
        return {"path": str(Path(args.out).resolve())}
    if action == "submit":
        return getattr(api, kind + "_draft_submit")(args.draft_id, consent=args.consent)
    if action == "log":
        return api.get(url + "/log")
    if action == "withdraw":
        return api.delete(url)
    raise ValueError(f"{action} is not available for {kind} drafts.")


def command(args):
    api = BuildrixAPI()
    try:
        kind = args.noun
        if args.verb == "develop":
            from buildrix.contribution_wizard import run
            run(api, kind, resume=args.resume)
            return 0
        if args.verb == "revise":
            draft = api.revise(kind, args.ref)
            if not args.json:
                from buildrix.contribution_wizard import run
                run(api, kind, resume=draft["id"])
                return 0
            result = draft
        elif args.verb == "drafts":
            result = getattr(api, kind + "_drafts")()
        elif args.verb == "history":
            result = getattr(api, kind + "_draft_log")(args.draft_id)
        elif args.verb == "withdraw":
            result = getattr(api, kind + "_draft_abandon")(args.draft_id)
        else:
            result = draft_action(api, kind, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ApiError, ValueError, OSError, KeyError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1

