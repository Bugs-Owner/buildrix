"""Durable, explicitly scoped local contribution journal with idempotent hub sync."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from buildrix.hub_api import ApiError


@contextmanager
def journal_lock(path):
    """Only one writer/sender may use a journal at once, including on Windows."""
    lock = Path(str(path) + ".lock")
    with lock.open("a+b") as f:
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            f.seek(0)
            if os.name == "nt":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def append(path, record, mode="a"):
    with Path(path).open(mode, encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read(path, api, kind, draft_id):
    with Path(path).open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    if not records or records[0].get("record") != "session" or records[0].get("schema_version") != 1:
        raise ValueError("Not a Buildrix local journal")
    header = records[0]
    if (header["kind"], header["draft_id"], header["hub_url"]) != (kind, draft_id, api.hub_url.rstrip("/")):
        raise ValueError("Journal belongs to a different hub or draft")
    api.client_context = header["context"]
    return header, records


def _sync(path, api, kind, draft_id):
    header, records = read(path, api, kind, draft_id)
    acknowledged = {eid for r in records if r["record"] == "ack" for eid in r["event_ids"]}
    pending = [r for r in records if r["record"] == "event" and r["event"]["event_id"] not in acknowledged]
    url = f"/{kind}s/drafts/{draft_id}"
    # Initial capture is retried with the same exact source before coaching or review.
    for r in pending:
        if "initial_assistance" in r:
            api.post(url + "/initial-input", json_body={"text": r["event"]["text"],
                                                       "assistance": r["initial_assistance"]})
    batch = []
    size = 0
    batches = []
    for r in pending:
        event = r["event"]
        length = len(event["text"].encode("utf-8"))
        if batch and (len(batch) >= 100 or size + length > 500000):
            batches.append(batch)
            batch, size = [], 0
        batch.append(event)
        size += length
    if batch or not batches:
        batches.append(batch)
    for batch in batches:
        result = api.post(url + "/local-interactions", json_body={
            "session_id": header["session_id"], "context": header["context"], "events": batch})
        ids = [event["event_id"] for event in batch]
        if set(result.get("acknowledged", [])) != set(ids):
            raise ApiError("The hub did not acknowledge the entire journal batch; local records remain queued")
        if ids:
            append(path, {"record": "ack", "event_ids": ids})
    return {"status": "synced", "session_id": header["session_id"], "synced_events": len(pending), "pending": 0}


def sync(path, api, kind, draft_id):
    with journal_lock(path):
        return _sync(path, api, kind, draft_id)


def start(path, api, kind, draft_id, context):
    if context.get("interface") != "agent":
        raise ValueError("A local agent journal requires interface=agent")
    sid = uuid.uuid4().hex
    context = {**context, "session_id": sid}
    with journal_lock(path):
        append(path, {"record": "session", "schema_version": 1, "kind": kind,
                      "draft_id": draft_id, "hub_url": api.hub_url.rstrip("/"),
                      "session_id": sid, "context": context}, mode="x")
        try:
            return _sync(path, api, kind, draft_id)
        except ApiError as error:
            return {"status": "queued", "session_id": sid, "error": str(error), "journal": str(path)}


def record(path, api, kind, draft_id, *, text, role, purpose, reply_to="", dimension="", assistance=None):
    if not text.strip() or len(text) > 100000:
        raise ValueError("A local message must contain 1–100000 characters")
    human = {"initial_response", "clarification_answer", "revision_accepted"}
    agent = {"initial_prompt", "clarification_question", "revision_proposed", "hub_feedback"}
    if role not in {"human", "assistant"} or (purpose in human and role != "human") or (purpose in agent and role != "assistant"):
        raise ValueError("Event purpose does not match its speaker")
    with journal_lock(path):
        header, records = read(path, api, kind, draft_id)
        events = [r["event"] for r in records if r["record"] == "event"]
        if purpose == "clarification_answer" and not any(
            e["event_id"] == reply_to and e["purpose"] == "clarification_question" for e in events
        ):
            raise ValueError("reply_to must identify an earlier local clarification question")
        existing = next((e for e in events if e["purpose"] == "initial_response"), None) if assistance else None
        if existing and existing["text"] != text:
            raise ValueError("The initial response is already recorded; log later replies as clarifications")
        if existing:
            event = existing
        else:
            event = {"event_id": uuid.uuid4().hex, "sequence": len(events) + 1,
                     "role": role, "purpose": purpose, "text": text,
                     "occurred_at": datetime.now(timezone.utc).isoformat(),
                     "reply_to": reply_to, "dimension": dimension}
            entry = {"record": "event", "event": event}
            if assistance:
                entry["initial_assistance"] = assistance
            append(path, entry)
        try:
            return {**_sync(path, api, kind, draft_id), "event_id": event["event_id"]}
        except ApiError as error:
            return {"status": "queued", "event_id": event["event_id"], "error": str(error), "journal": str(path)}
