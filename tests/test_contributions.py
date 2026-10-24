import argparse
import io
import json
import zipfile

import pytest

from buildrix import contribution_commands as cc, contribution_wizard as wizard
from buildrix.hub_api import BuildrixAPI


class RecordingAPI(BuildrixAPI):
    def __init__(self):
        self.calls = []
        self.response = {"id": "draft-1"}

    def _request(self, method, path, **kwargs):
        if isinstance(kwargs.get("files"), dict):
            name, handle = kwargs["files"]["file"]
            kwargs["uploaded"] = (name, handle.read())
        elif kwargs.get("files"):
            kwargs["uploaded"] = [(field, name, handle.read()) for field, (name, handle) in kwargs["files"]]
        self.calls.append((method, path, kwargs))
        return self.response


def args(action, **kwargs):
    return argparse.Namespace(action=action, draft_id="draft-1", **kwargs)


def test_task_reply_is_verbatim_and_requests_shared_review(tmp_path):
    file = tmp_path / "reply.txt"
    source = "  Seed 7.\r\nDo not retrain after testing.  \r\n"
    file.write_bytes(source.encode("utf-8"))
    api = RecordingAPI()
    cc.draft_action(api, "task", args("answer", text_file=file, dimension="reproducibility"))
    method, path, data = api.calls[-1]
    assert (method, path) == ("PUT", "/tasks/drafts/draft-1/dimensions/reproducibility")
    assert data["json_body"] == {"answer": source, "review": True}
    assert data["timeout"] >= 180


def test_description_revision_uses_existing_request_endpoint(tmp_path):
    file = tmp_path / "request.txt"
    file.write_text("Updated task description", encoding="utf-8")
    api = RecordingAPI()
    api.response = {"initial_request": "Original"}
    cc.draft_action(api, "task", args("describe", text_file=file))
    assert api.calls[-1][:2] == ("PUT", "/tasks/drafts/draft-1/request")


def test_file_notes_and_large_file_links_reach_shared_api(tmp_path):
    file = tmp_path / "file with spaces.csv"
    file.write_bytes(b"timestamp,kw\n1,2\n")
    notes = tmp_path / "notes.json"
    payload = {"dimension": "inputs_resources", "kind": "input",
               "description": "Meter readings", "usage": "timestamp is an hour; kw is power."}
    notes.write_text(json.dumps(payload), encoding="utf-8")
    api = RecordingAPI()
    cc.draft_action(api, "task", args("upload", file=file, data=notes))
    assert api.calls[-1][2]["data"] == payload
    assert api.calls[-1][2]["uploaded"] == (file.name, file.read_bytes())
    payload.update(filename="data", source_url="https://drive.google.com/file/example")
    notes.write_text(json.dumps(payload), encoding="utf-8")
    cc.draft_action(api, "task", args("link", data=notes))
    assert api.calls[-1][:2] == ("POST", "/tasks/drafts/draft-1/asset-links")
    assert api.calls[-1][2]["json_body"] == payload


def test_package_replacement_keeps_draft_and_relative_paths(tmp_path):
    folder = tmp_path / "my skill"
    (folder / "scripts" / "helpers").mkdir(parents=True)
    (folder / "SKILL.md").write_text("## Method\nUse scripts/helpers/run.py", encoding="utf-8")
    (folder / "scripts" / "helpers" / "run.py").write_text("print('hi')", encoding="utf-8")
    api = RecordingAPI()
    cc.import_skill(api, folder, "existing-draft")
    method, path, request = api.calls[-1]
    assert (method, path) == ("POST", "/skills/import")
    assert request["params"] == {"draft_id": "existing-draft"}
    with zipfile.ZipFile(io.BytesIO(request["uploaded"][1])) as z:
        assert set(z.namelist()) == {"SKILL.md", "scripts/helpers/run.py"}
    assert not list(tmp_path.glob("*.zip"))


def test_metadata_collects_same_fields_for_both_surfaces(monkeypatch):
    meta = {key: [{"id": value, "label": value}] for key, value in {
        "domains": "forecasting-analytics", "efforts": "1_day", "effort_options": "1_day",
        "complexity_options": "3", "task_familiarity": "expert", "agentic_familiarity": "regular",
        "ai_assistance": "claude_code"}.items()}
    monkeypatch.setattr(wizard, "ask", lambda prompt, default="", **kw: default or "a name")
    monkeypatch.setattr(wizard, "ask_choice", lambda prompt, options, default="": options[0][0])
    for kind in ("skill", "task"):
        result = wizard.metadata(meta, kind)
        assert result["complexity"] == 3
        assert result["estimated_effort"] == "1_day"
        assert result["task_familiarity"] == "expert"
        assert result["agentic_familiarity"] == "regular"


def test_revise_is_same_endpoint_and_submit_cannot_skip_review():
    api = RecordingAPI()
    api.revise("skill", "SANA-0001")
    assert api.calls[-1][:2] == ("POST", "/skills/SANA-0001/revise")
    cc.draft_action(api, "skill", args("submit", consent=True))
    assert api.calls[-1][2]["json_body"] == {"auto_review": True, "consent": True}


def test_json_parser_requires_explicit_consent():
    parser = argparse.ArgumentParser()
    nouns = parser.add_subparsers(dest="noun")
    skill = nouns.add_parser("skill").add_subparsers(dest="verb")
    task = nouns.add_parser("task").add_subparsers(dest="verb")
    cc.add_commands(skill, task)
    with pytest.raises(SystemExit):
        parser.parse_args(["task", "draft", "submit", "draft-1"])
    parsed = parser.parse_args(["task", "draft", "submit", "draft-1", "--consent"])
    assert parsed.consent is True


def test_environment_files_skip_notes(monkeypatch):
    monkeypatch.setattr(wizard, "ask_block", lambda *a, **k: pytest.fail("Environment config should not ask for notes"))
    assert wizard.file_notes("environment") == {"description": "", "usage": ""}


def test_review_advances_only_after_hub_resolves_section(monkeypatch):
    api = RecordingAPI()
    initial = {"id": "draft-1", "initial_request": "A completed task", "dimensions": {
        "objective": {"state": "needs_clarification", "content": "Old description"},
        "inputs_resources": {"state": "not_provided"}}}
    api.response = {"id": "draft-1", "dimensions": {
        "objective": {"state": "clear", "content": "Revised objective"},
        "inputs_resources": {"state": "not_provided"}}}
    definitions = [{"id": "objective", "title": "Objective"}, {"id": "inputs_resources", "title": "Inputs"}]
    choices = iter(["answer", "pause"])
    headings = []
    monkeypatch.setattr(wizard, "ask_choice", lambda *a, **kw: next(choices))
    monkeypatch.setattr(wizard, "ask_block", lambda *a, **kw: "Only my new answer")
    monkeypatch.setattr(wizard, "rule", headings.append)
    result = wizard.run_task(api, initial, {"dimensions": definitions})
    assert result["id"] == "draft-1"
    assert "Objective" in headings[0] and "Inputs" in headings[1]
    assert api.calls[0][2]["json_body"]["answer"] == "Only my new answer"



def test_scoring_table_goes_to_evaluation_for_review(tmp_path):
    table = {"deliverables": [{"name": "forecast.csv", "requirement": "kw column"}],
             "stages": [{"name": "", "weight": 1, "dimensions": [{"name": "Accuracy"}]}]}
    data = tmp_path / "table.json"
    data.write_text(json.dumps(table), encoding="utf-8")
    api = RecordingAPI()
    cc.draft_action(api, "task", args("rubric", data=data))
    method, path, sent = api.calls[-1]
    assert (method, path) == ("PUT", "/tasks/drafts/draft-1/dimensions/evaluation")
    assert sent["json_body"] == {"rubric": table, "review": True}


def test_wizard_builds_a_scoring_table(monkeypatch):
    answers = iter(["1", "1", "Accuracy", "CVRMSE", "0.28", "0.88", "1",
                    "For each test day, a CSV of hourly predictions; summary.md", "0.5", "0.43",
                    "No missing hours; Never negative"])
    prompts = []
    def ask(prompt, *a, **k):
        prompts.append(prompt)
        return next(answers)
    monkeypatch.setattr(wizard, "ask", ask)
    monkeypatch.setattr(wizard, "ask_choice", lambda *a, **k: "lower")
    hint = {"deliverables": [{"name": "predictions.csv"}],
            "stages": [{"dimensions": [{"name": "Accuracy", "metric": "MAE of indoor temperature"}]}]}
    table = wizard.scoring_table({"rubric_hint": hint})
    # The reviewer's draft is shown as an example, never kept as an answer.
    assert any("e.g. MAE of indoor temperature" in p for p in prompts)
    assert [d["name"] for d in table["deliverables"]] == ["For each test day, a CSV of hourly predictions", "summary.md"]
    assert table["conditions"] == ["No missing hours", "Never negative"]
    dim = table["stages"][0]["dimensions"][0]
    assert (dim["better"], dim["best"], dim["worst"], dim["pass_line"], dim["own_value"]) == \
        ("lower", "0.28", "0.88", "0.5", "0.43")
    assert "_old" not in dim


def test_run_measurements_keep_only_what_was_measured():
    from buildrix import bench
    assert bench.run_measurements({"wall_clock_s": 12.5, "tokens": 0, "tool_calls": 3, "x": 1}) == \
        {"wall_clock_s": 12.5, "tool_calls": 3}


def test_an_output_note_asks_only_for_its_contents(monkeypatch):
    asked = []
    monkeypatch.setattr(wizard, "ask_block", lambda prompt, *a, **k: asked.append(prompt) or "Hourly predictions")
    assert wizard.file_notes("human_reference") == {"description": "Hourly predictions", "usage": ""}
    assert asked == ["What does this file contain?"]


def test_a_reply_to_the_review_sends_text_and_files(tmp_path):
    reply = tmp_path / "reply.txt"
    reply.write_text("The daily values are averaged.", encoding="utf-8")
    extra = tmp_path / "day8.csv"
    extra.write_bytes(b"timestamp,kw\n1,2\n")
    api = RecordingAPI()
    cc.draft_action(api, "task", args("reply", text_file=reply, file=[str(extra)]))
    method, path, sent = api.calls[-1]
    assert (method, path) == ("POST", "/tasks/drafts/draft-1/review-reply")
    assert sent["data"] == {"text": "The daily values are averaged."}
    assert sent["uploaded"] == [("files", "day8.csv", b"timestamp,kw\n1,2\n")]


def test_metadata_asks_related_stakeholders_with_other(monkeypatch):
    meta = {key: [{"id": value, "label": value}] for key, value in {
        "domains": "forecasting-analytics", "efforts": "1_day", "complexity_options": "3",
        "task_familiarity": "expert", "agentic_familiarity": "regular"}.items()}
    meta["stakeholders"] = [{"id": "engineer", "label": "Engineer"}, {"id": "other", "label": "Other"}]
    prompts = []
    monkeypatch.setattr(wizard, "ask", lambda prompt, default="", **kw: prompts.append(prompt) or "Energy auditors")
    monkeypatch.setattr(wizard, "ask_choice", lambda prompt, options, default="": options[0][0])
    monkeypatch.setattr(wizard, "ask_many", lambda prompt, options, default=None, **kw: ["engineer", "other"])
    result = wizard.metadata(meta, "task")
    assert result["stakeholders"] == ["engineer", "other"]
    assert result["stakeholders_other"] == "Energy auditors"
    monkeypatch.setattr(wizard, "ask_many", lambda *a, **kw: ["engineer"])
    assert wizard.metadata(meta, "task")["stakeholders_other"] == ""
    # Skills never ask about stakeholders.
    assert "stakeholders" not in wizard.metadata({**meta, "effort_options": meta["efforts"]}, "skill")


def test_ask_many_accepts_numbers_and_ids(monkeypatch):
    from buildrix import interactive
    answers = iter(["9", "1, other"])
    monkeypatch.setattr(interactive, "ask", lambda *a, **k: next(answers))
    picked = interactive.ask_many("Who", [("engineer", "Engineer"), ("other", "Other")], required=True)
    assert picked == ["engineer", "other"]


KNOWLEDGE_DEF = {"id": "detailed_instruction", "title": "Human knowledge", "reviewed": False,
                 "accepts_files": True, "asset_kind": "knowledge"}


def test_revision_skips_human_knowledge_section(monkeypatch):
    api = RecordingAPI()
    draft = {"id": "draft-1", "initial_request": "A completed task", "dimensions": {
        "objective": {"state": "clear"}, "detailed_instruction": {"state": "not_provided"},
        "inputs_resources": {"state": "not_provided"}}}
    api.response = draft
    meta = {"dimensions": [{"id": "objective", "title": "Objective"}, KNOWLEDGE_DEF,
                           {"id": "inputs_resources", "title": "Inputs"}]}
    choices = iter(["next", "next", "pause"])
    headings = []
    offered = []
    def choose(prompt, options, *a, **k):
        offered.append([key for key, _ in options])
        return next(choices)
    monkeypatch.setattr(wizard, "ask_choice", choose)
    monkeypatch.setattr(wizard, "rule", headings.append)
    wizard.run_task(api, draft, meta)
    assert headings == ["Revision · 2/2 · Inputs", "Revision · 1/2 · Objective", "Revision · 2/2 · Inputs"]
    assert "knowledge" in offered[0]
    assert not api.calls


def test_human_knowledge_step_follows_revisions_and_is_not_reviewed(monkeypatch):
    api = RecordingAPI()
    draft = {"id": "draft-1", "initial_request": "A completed task", "complete": True,
             "dimensions": {"objective": {"state": "clear"}, "detailed_instruction": {"state": "not_provided"}}}
    saved = {**draft, "dimensions": {**draft["dimensions"],
                                     "detailed_instruction": {"content": "Check the economizer first."}}}
    api.response = saved
    meta = {"dimensions": [{"id": "objective", "title": "Objective"}, KNOWLEDGE_DEF]}
    choices = iter(["write", "done", "pause"])
    headings = []
    monkeypatch.setattr(wizard, "ask_choice", lambda *a, **k: next(choices))
    monkeypatch.setattr(wizard, "ask_block", lambda *a, **k: "Check the economizer first.")
    monkeypatch.setattr(wizard, "rule", headings.append)
    wizard.run_task(api, draft, meta)
    assert headings[0] == "Human knowledge"
    method, path, sent = api.calls[0]
    assert (method, path) == ("PUT", "/tasks/drafts/draft-1/dimensions/detailed_instruction")
    assert sent["json_body"] == {"content": "Check the economizer first.", "review": False}


def test_human_knowledge_counts_files():
    draft = {"dimensions": {}, "assets": [{"dimension": "detailed_instruction", "kind": "knowledge"}]}
    assert wizard.has_knowledge(draft)
    assert not wizard.has_knowledge({"dimensions": {"detailed_instruction": {"content": "  "}}})


def test_knowledge_file_asks_only_for_a_description(monkeypatch):
    asked = []
    monkeypatch.setattr(wizard, "ask_block", lambda prompt, *a, **k: asked.append(prompt) or "My checklist")
    assert wizard.file_notes("knowledge") == {"description": "My checklist", "usage": ""}
    assert len(asked) == 1


def test_knowledge_command_saves_without_review(tmp_path):
    file = tmp_path / "knowledge.txt"
    file.write_bytes(b"Plot supply air first.\n")
    api = RecordingAPI()
    cc.draft_action(api, "task", args("knowledge", text_file=file))
    method, path, sent = api.calls[-1]
    assert (method, path) == ("PUT", "/tasks/drafts/draft-1/dimensions/detailed_instruction")
    assert sent["json_body"] == {"content": "Plot supply air first.\n", "review": False}
    cc.draft_action(api, "task", args("edit", text_file=file, dimension="detailed_instruction"))
    assert api.calls[-1][2]["json_body"]["review"] is False
    with pytest.raises(ValueError):
        cc.draft_action(api, "task", args("answer", text_file=file, dimension="detailed_instruction"))


def test_knowledge_parser_is_task_only():
    parser = argparse.ArgumentParser()
    nouns = parser.add_subparsers(dest="noun")
    skill = nouns.add_parser("skill").add_subparsers(dest="verb")
    task = nouns.add_parser("task").add_subparsers(dest="verb")
    cc.add_commands(skill, task)
    parsed = parser.parse_args(["task", "draft", "knowledge", "draft-1", "--text-file", "k.txt"])
    assert parsed.action == "knowledge"
    with pytest.raises(SystemExit):
        parser.parse_args(["skill", "draft", "knowledge", "draft-1", "--text-file", "k.txt"])


def test_registration_asks_the_short_profile():
    from buildrix import cli

    class Client:
        def profile_options(self):
            return {"occupation": [{"id": "engineer", "label": "Engineer"}, {"id": "other", "label": "Other"}],
                    "career_stage": [{"id": "senior", "label": "Senior"}],
                    "age_range": [{"id": "25_34", "label": "25 to 34"}],
                    "agent_use": [{"id": "daily", "label": "Daily"}]}

    answers = iter(["2", "Energy auditor", "senior", "", "1"])
    profile = cli.ask_profile(Client(), read=lambda prompt: next(answers))
    assert profile == {"occupation": "other", "occupation_other": "Energy auditor",
                       "career_stage": "senior", "agent_use": "daily"}

    class OldHub:
        def profile_options(self):
            return {}
    assert cli.ask_profile(OldHub(), read=lambda prompt: pytest.fail("should not ask")) == {}


def test_register_sends_profile_fields():
    api = RecordingAPI()
    api.register("a@b.c", "pw", "A", profile={"occupation": "engineer", "agent_use": "daily"})
    method, path, sent = api.calls[-1]
    assert (method, path) == ("POST", "/auth/register")
    assert sent["json_body"]["occupation"] == "engineer"
    assert sent["json_body"]["agent_use"] == "daily"
