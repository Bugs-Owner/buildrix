"""
Thin client for the Buildrix hub's v2 API.
==========================================

Every command in the CLI that creates, discovers or benchmarks something goes
through here, and every call maps to an endpoint the website uses too. That is
the whole point: ``buildrix task init`` does not have its own idea of what a
Task is — it drives the same draft API the browser drives, so the Task that
comes out is the same Task either way.

``hub_client.HubClient`` stays for the older skill-archive endpoints. This is
the surface the new command tree uses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import requests

from buildrix.config import get_hub_url, get_token


class ApiError(RuntimeError):
    """An error the hub reported, with its message rather than a status code."""

    def __init__(self, message: str, status: int = 0, path: str = ""):
        super().__init__(message)
        self.status = status
        self.path = path


class BuildrixAPI:
    def __init__(self, hub_url: str = "", token: str = ""):
        self.hub_url = (hub_url or get_hub_url()).rstrip("/")
        self.token = token if token is not None else get_token()
        if token == "":
            self.token = get_token()

    # -- plumbing ----------------------------------------------------------

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _url(self, path: str) -> str:
        return f"{self.hub_url}/api{path}"

    def _request(self, method: str, path: str, *, json_body: Any = None,
                 params: dict | None = None, files: dict | None = None,
                 data: dict | None = None, timeout: int = 120,
                 raw: bool = False):
        try:
            r = requests.request(
                method, self._url(path), headers=self._headers,
                json=json_body, params=params, files=files, data=data,
                timeout=timeout,
            )
        except requests.RequestException as e:
            raise ApiError(
                f"Could not reach the hub at {self.hub_url}: {e}", path=path)

        if r.status_code == 401:
            raise ApiError("Not signed in, or the session expired. "
                           "Run `buildrix auth login`.", 401, path)
        if r.status_code >= 400:
            detail = ""
            try:
                payload = r.json()
                detail = payload.get("detail") or payload.get("message") or ""
                if isinstance(detail, list):          # pydantic validation errors
                    detail = "; ".join(
                        f"{'.'.join(str(x) for x in d.get('loc', [])[1:])}: "
                        f"{d.get('msg', '')}" for d in detail)
            except ValueError:
                detail = r.text[:400]
            raise ApiError(detail or f"{r.status_code} {r.reason}",
                           r.status_code, path)
        if raw:
            return r.content
        if not r.content:
            return {}
        try:
            return r.json()
        except ValueError:
            return {"text": r.text}

    def get(self, path, **kw):    return self._request("GET", path, **kw)
    def post(self, path, **kw):   return self._request("POST", path, **kw)
    def put(self, path, **kw):    return self._request("PUT", path, **kw)
    def patch(self, path, **kw):  return self._request("PATCH", path, **kw)
    def delete(self, path, **kw): return self._request("DELETE", path, **kw)

    # -- health ------------------------------------------------------------

    def health(self) -> dict:
        return self.get("/health", timeout=10)

    def domains(self, kind: str = "skill") -> list[dict]:
        try:
            return self.get("/domains", params={"kind": kind}).get("domains", [])
        except ApiError:
            from buildrix import domains as d
            ids = d.TASK_DOMAINS if kind == "task" else d.SKILL_DOMAINS
            return [{"id": i, "label": d.LABELS[i], "short": d.SHORT[i]} for i in ids]

    # ── Tasks ─────────────────────────────────────────────────────────────

    def task_meta(self) -> dict:
        return self.get("/tasks/meta")

    def task_search(self, query: str = "", domain: str = "",
                    difficulty: str = "", limit: int = 50) -> list[dict]:
        params = {"limit": limit}
        if query:      params["search"] = query
        if domain:     params["domain"] = domain
        if difficulty: params["difficulty"] = difficulty
        return self.get("/tasks/", params=params)

    def task_show(self, ref: str) -> dict:
        return self.get(f"/tasks/{ref}")

    def task_package(self, ref: str) -> bytes:
        return self.get(f"/tasks/{ref}/package", raw=True)

    # draft workflow — the same endpoints the website calls
    def task_draft_create(self, body: dict) -> dict:
        return self.post("/tasks/drafts", json_body=body)

    def task_drafts(self) -> list[dict]:
        return self.get("/tasks/drafts")

    def task_draft(self, draft_id: str) -> dict:
        return self.get(f"/tasks/drafts/{draft_id}")

    def task_draft_patch(self, draft_id: str, body: dict) -> dict:
        return self.patch(f"/tasks/drafts/{draft_id}", json_body=body)

    def task_draft_request(self, draft_id: str, text: str) -> dict:
        return self.post(f"/tasks/drafts/{draft_id}/request",
                         json_body={"text": text}, timeout=180)

    def task_draft_answers(self, draft_id: str, answers: list[dict]) -> dict:
        return self.post(f"/tasks/drafts/{draft_id}/answers",
                         json_body={"answers": answers}, timeout=180)

    def task_draft_dimension(self, draft_id: str, dim: str, body: dict) -> dict:
        return self.put(f"/tasks/drafts/{draft_id}/dimensions/{dim}", json_body=body)

    def task_draft_proposal(self, draft_id: str, dim: str, pid: str,
                            decision: str, text: str = "") -> dict:
        return self.post(
            f"/tasks/drafts/{draft_id}/dimensions/{dim}/proposals/{pid}",
            json_body={"decision": decision, "text": text})

    def task_draft_asset(self, draft_id: str, path: Path, dimension: str,
                         kind: str, description: str = "") -> dict:
        with open(path, "rb") as fh:
            return self.post(
                f"/tasks/drafts/{draft_id}/assets",
                files={"file": (path.name, fh)},
                data={"dimension": dimension, "kind": kind,
                      "description": description})

    def task_draft_instance(self, draft_id: str, body: dict) -> dict:
        return self.post(f"/tasks/drafts/{draft_id}/instances", json_body=body)

    def task_draft_finalize(self, draft_id: str) -> dict:
        return self.post(f"/tasks/drafts/{draft_id}/finalize", timeout=180)

    def task_draft_prompt(self, draft_id: str, prompt: str) -> dict:
        return self.put(f"/tasks/drafts/{draft_id}/canonical-prompt",
                        json_body={"canonical_prompt": prompt})

    def task_draft_submit(self, draft_id: str, consent: bool = True) -> dict:
        return self.post(f"/tasks/drafts/{draft_id}/submit",
                         json_body={"auto_review": True, "consent": consent},
                         timeout=180)

    def task_draft_log(self, draft_id: str) -> dict:
        return self.get(f"/tasks/drafts/{draft_id}/log")

    def task_draft_abandon(self, draft_id: str) -> dict:
        return self.delete(f"/tasks/drafts/{draft_id}")

    # ── Skills ────────────────────────────────────────────────────────────

    def skill_meta(self) -> dict:
        return self.get("/skills/meta")

    def skill_search(self, query: str = "", domain: str = "",
                     limit: int = 50) -> list[dict]:
        params = {"limit": limit}
        if query:  params["search"] = query
        if domain: params["domain"] = domain
        return self.get("/skills/", params=params)

    def skill_show(self, ref: str) -> dict:
        try:
            return self.get(f"/skills/by-name/{ref}")
        except ApiError as e:
            if e.status == 404:
                return self.get(f"/skills/{ref}")
            raise

    def skill_download(self, skill_id: str) -> bytes:
        return self.get(f"/skills/{skill_id}/download", raw=True)

    def skill_validate(self, path: Path) -> dict:
        with open(path, "rb") as fh:
            return self.post("/skills/validate",
                             files={"file": (path.name, fh)}, timeout=120)

    def skill_import(self, path: Path) -> dict:
        with open(path, "rb") as fh:
            return self.post("/skills/import",
                             files={"file": (path.name, fh)}, timeout=180)

    def skill_draft_create(self, body: dict) -> dict:
        return self.post("/skills/drafts", json_body=body)

    def skill_drafts(self) -> list[dict]:
        return self.get("/skills/drafts")

    def skill_draft(self, draft_id: str) -> dict:
        return self.get(f"/skills/drafts/{draft_id}")

    def skill_draft_patch(self, draft_id: str, body: dict) -> dict:
        return self.patch(f"/skills/drafts/{draft_id}", json_body=body)

    def skill_draft_describe(self, draft_id: str, text: str) -> dict:
        return self.post(f"/skills/drafts/{draft_id}/describe",
                         json_body={"text": text}, timeout=180)

    def skill_draft_answers(self, draft_id: str, answers: list[dict]) -> dict:
        return self.post(f"/skills/drafts/{draft_id}/answers",
                         json_body={"answers": answers}, timeout=180)

    def skill_draft_dimension(self, draft_id: str, dim: str, body: dict) -> dict:
        return self.put(f"/skills/drafts/{draft_id}/dimensions/{dim}",
                        json_body=body)

    def skill_draft_proposal(self, draft_id: str, dim: str, pid: str,
                             decision: str, text: str = "") -> dict:
        return self.post(
            f"/skills/drafts/{draft_id}/dimensions/{dim}/proposals/{pid}",
            json_body={"decision": decision, "text": text})

    def skill_draft_requirements(self, draft_id: str, body: dict) -> dict:
        return self.put(f"/skills/drafts/{draft_id}/requirements", json_body=body)

    def skill_draft_asset(self, draft_id: str, path: Path, kind: str,
                          description: str = "") -> dict:
        with open(path, "rb") as fh:
            return self.post(f"/skills/drafts/{draft_id}/assets",
                             files={"file": (path.name, fh)},
                             data={"kind": kind, "description": description})

    def skill_draft_finalize(self, draft_id: str) -> dict:
        return self.post(f"/skills/drafts/{draft_id}/finalize", timeout=180)

    def skill_draft_md(self, draft_id: str, body: str) -> dict:
        return self.put(f"/skills/drafts/{draft_id}/skill-md",
                        json_body={"skill_md": body})

    def skill_draft_package(self, draft_id: str) -> bytes:
        return self.get(f"/skills/drafts/{draft_id}/package", raw=True)

    def skill_draft_submit(self, draft_id: str, consent: bool = True) -> dict:
        return self.post(f"/skills/drafts/{draft_id}/submit",
                         json_body={"auto_review": True, "consent": consent},
                         timeout=180)

    def skill_draft_log(self, draft_id: str) -> dict:
        return self.get(f"/skills/drafts/{draft_id}/log")

    def skill_draft_abandon(self, draft_id: str) -> dict:
        return self.delete(f"/skills/drafts/{draft_id}")

    # ── Benchmark ─────────────────────────────────────────────────────────

    def benchmark_match(self, body: dict) -> dict:
        return self.post("/benchmark/match", json_body=body, timeout=180)

    def benchmark_grade(self, body: dict) -> dict:
        return self.post("/benchmark/grade", json_body=body, timeout=300)

    def benchmark_grader(self) -> dict:
        return self.get("/benchmark/grader")

    def benchmark_conditions(self) -> dict:
        return self.get("/benchmark/conditions")

    def benchmark_nonce(self, skill_ref: str, task_refs: list[str]) -> dict:
        return self.post("/benchmark/nonce",
                         json_body={"skill_ref": skill_ref, "task_refs": task_refs})

    def benchmark_submit(self, group: dict) -> dict:
        return self.post("/benchmark/runs", json_body=group, timeout=180)

    def benchmark_results(self, skill: str = "", task: str = "",
                          model: str = "", limit: int = 50) -> dict:
        params = {"limit": limit}
        if skill: params["skill"] = skill
        if task:  params["task"] = task
        if model: params["model"] = model
        return self.get("/benchmark/results", params=params)

    def benchmark_skill_summary(self, skill_ref: str) -> dict:
        return self.get(f"/benchmark/skills/{skill_ref}/summary")

    # ── Auth ──────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        return self.post("/auth/login",
                         json_body={"email": email, "password": password})

    def register(self, email: str, password: str, display_name: str,
                 affiliation: str = "") -> dict:
        return self.post("/auth/register", json_body={
            "email": email, "password": password,
            "display_name": display_name, "affiliation": affiliation})

    def me(self) -> dict:
        return self.get("/auth/me")
