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
        if kwargs.get("files"):
            name, handle = kwargs["files"]["file"]
            kwargs["uploaded"] = (name, handle.read())
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
        "complexity_options": "3", "task_familiarity": "expert", "agentic_familiarity": "regular"}.items()}
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
    answers = iter(["1", "1", "Accuracy", "CVRMSE", "0.28", "0.88", "1", "report.md", "0.5", "0.43"])
    monkeypatch.setattr(wizard, "ask", lambda *a, **k: next(answers))
    monkeypatch.setattr(wizard, "ask_choice", lambda *a, **k: "lower")
    start = {"deliverables": [{"name": "forecast.csv", "requirement": ""}]}
    table = wizard.scoring_table({"rubric_start": start})
    assert [d["name"] for d in table["deliverables"]] == ["forecast.csv", "report.md"]
    dim = table["stages"][0]["dimensions"][0]
    assert (dim["better"], dim["best"], dim["worst"], dim["pass_line"], dim["own_value"]) == \
        ("lower", "0.28", "0.88", "0.5", "0.43")


def test_run_measurements_keep_only_what_was_measured():
    from buildrix import bench
    assert bench.run_measurements({"wall_clock_s": 12.5, "tokens": 0, "tool_calls": 3, "x": 1}) == \
        {"wall_clock_s": 12.5, "tool_calls": 3}
