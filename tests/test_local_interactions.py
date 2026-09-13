import argparse
import json

import pytest

from buildrix import local_interactions as local, contribution_commands as cc
from buildrix.hub_api import ApiError, BuildrixAPI


class Hub:
    hub_url = "https://hub.example"

    def __init__(self):
        self.events = {}
        self.calls = []
        self.offline = False
        self.lose_ack = False

    def post(self, path, *, json_body):
        self.calls.append((path, json_body))
        if self.offline:
            raise ApiError("offline")
        if path.endswith("initial-input"):
            return {"captured": True}
        for e in json_body["events"]:
            if e["event_id"] in self.events:
                assert e == self.events[e["event_id"]]
            self.events[e["event_id"]] = e
        if self.lose_ack:
            self.lose_ack = False
            raise ApiError("connection lost after hub committed")
        return {"acknowledged": [e["event_id"] for e in json_body["events"]]}


def start(tmp_path):
    path = tmp_path / "session.jsonl"
    hub = Hub()
    assert local.start(path, hub, "task", "d1", {
        "interface": "agent", "buildrix_skill_used": True, "skill_version": "1.2.0"
    })["status"] == "synced"
    return path, hub


def test_offline_capture_retains_exact_initial_input_then_syncs_before_review(tmp_path):
    path, hub = start(tmp_path)
    text = "  Original words.\r\nKeep these.  \r\n"
    hub.offline = True
    result = local.record(path, hub, "task", "d1", text=text, role="human",
                          purpose="initial_response", assistance="unassisted")
    assert result["status"] == "queued"
    saved = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert saved[1]["event"]["text"] == text
    hub.offline = False
    assert local.sync(path, hub, "task", "d1")["status"] == "synced"
    assert hub.calls[-2][0].endswith("initial-input")
    assert hub.calls[-2][1] == {"text": text, "assistance": "unassisted"}
    assert len(hub.events) == 1
    # Retrying capture cannot manufacture another original message.
    local.record(path, hub, "task", "d1", text=text, role="human", purpose="initial_response", assistance="unassisted")
    assert len(hub.events) == 1
    with pytest.raises(ValueError, match="already recorded"):
        local.record(path, hub, "task", "d1", text="Rewrite", role="human", purpose="initial_response", assistance="unassisted")


def test_lost_ack_does_not_duplicate_and_replies_are_linked(tmp_path):
    path, hub = start(tmp_path)
    hub.lose_ack = True
    q = local.record(path, hub, "task", "d1", text="Question?", role="assistant", purpose="clarification_question")
    assert q["status"] == "queued" and len(hub.events) == 1
    assert local.sync(path, hub, "task", "d1")["synced_events"] == 1
    local.record(path, hub, "task", "d1", text="Answer.", role="human", purpose="clarification_answer", reply_to=q["event_id"])
    assert len(hub.events) == 2
    assert local.sync(path, hub, "task", "d1")["synced_events"] == 0
    with pytest.raises(ValueError, match="earlier local"):
        local.record(path, hub, "task", "d1", text="Answer.", role="human", purpose="clarification_answer")


def test_journal_binding_and_failed_sync_prevent_dependent_submission(tmp_path):
    path, hub = start(tmp_path)
    count = len(hub.calls)
    with pytest.raises(ValueError, match="different hub or draft"):
        local.sync(path, hub, "task", "other-draft")
    assert len(hub.calls) == count
    hub.offline = True
    args = argparse.Namespace(action="submit", draft_id="d1", journal=str(path), context="", consent=True)
    with pytest.raises(ApiError, match="offline"):
        cc.draft_action(hub, "task", args)
    assert all(not path.endswith("/submit") for path, body in hub.calls)
    with pytest.raises(FileExistsError):
        local.start(path, hub, "task", "d1", {"interface": "agent"})


def test_cli_records_without_permission_flag_and_context_is_transmitted(tmp_path):
    path, hub = start(tmp_path)
    source = tmp_path / "utterance.txt"
    source.write_bytes(b"Original spelling \r\n")
    args = argparse.Namespace(action="capture-initial", draft_id="d1", journal=str(path),
        context="", text_file=str(source), assistance="unassisted")
    assert cc.draft_action(hub, "task", args)["status"] == "synced"
    assert next(iter(hub.events.values()))["text"] == "Original spelling \r\n"
    api = BuildrixAPI(hub_url="https://hub.example", token="test")
    assert json.loads(api._headers["X-Buildrix-Context"])["interface"] == "cli"
    api.client_context = hub.client_context
    assert json.loads(api._headers["X-Buildrix-Context"])["buildrix_skill_used"] is True
