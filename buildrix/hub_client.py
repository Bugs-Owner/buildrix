"""HTTP client for the Buildrix Hub API."""

import io
import json
import zipfile
from pathlib import Path
from typing import Optional

import requests

from buildrix.config import get_token, get_hub_url


class HubClient:
    """Client for the Buildrix Hub REST API."""

    def __init__(self, hub_url: str = "", token: str = ""):
        self.hub_url = (hub_url or get_hub_url()).rstrip("/")
        self.token = token or get_token()

    @property
    def _headers(self) -> dict:
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _url(self, path: str) -> str:
        return f"{self.hub_url}/api{path}"

    # -- Auth --------------------------------------------------------------

    def login(self, email: str, password: str) -> dict:
        """Login and return token + user info."""
        resp = requests.post(
            self._url("/auth/login"),
            json={"email": email, "password": password},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        return data

    def register(self, email: str, password: str, display_name: str,
                 affiliation: str = "", role: str = "contributor") -> dict:
        """Register a new account."""
        resp = requests.post(
            self._url("/auth/register"),
            json={
                "email": email,
                "password": password,
                "display_name": display_name,
                "affiliation": affiliation,
                "role": role,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        return data

    def me(self) -> dict:
        """Get current user profile."""
        resp = requests.get(
            self._url("/auth/me"),
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    # -- Skills ------------------------------------------------------------

    def list_skills(self, domain: str = "", search: str = "",
                    sort_by: str = "") -> list[dict]:
        """List skills from the hub.

        `sort_by` accepts the hub's sort keys: newest, oldest, most_liked,
        most_downloaded, most_saved. When empty, the hub defaults to newest.
        """
        params = {}
        if domain:
            params["domain"] = domain
        if search:
            params["search"] = search
        if sort_by:
            params["sort_by"] = sort_by
        resp = requests.get(
            self._url("/skills/"),
            params=params,
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_skill(self, skill_id: str) -> dict:
        """Get skill details."""
        resp = requests.get(
            self._url(f"/skills/{skill_id}"),
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def get_skill_by_name(self, name: str) -> Optional[dict]:
        """Look up a skill by name. Returns None if not found."""
        resp = requests.get(
            self._url(f"/skills/by-name/{name}"),
            headers=self._headers,
            timeout=10,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def push_skill(self, skill_dir: Path) -> dict:
        """
        Package a skill directory and upload to the hub.

        Reads SKILL.md frontmatter for metadata, zips the directory,
        and POSTs to the hub API.
        """
        skill_dir = Path(skill_dir)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"No SKILL.md found in {skill_dir}")

        # Parse frontmatter
        meta = _parse_frontmatter(skill_md.read_text())

        # Create zip archive in memory
        zip_buffer = _zip_skill_dir(skill_dir)

        # Upload
        resp = requests.post(
            self._url("/skills/"),
            headers=self._headers,
            data={
                "name": meta.get("name", skill_dir.name),
                "description": meta.get("description", ""),
                "domain": meta.get("metadata", {}).get("domain", "general"),
                "version": meta.get("metadata", {}).get("version", "0.1.0"),
                "tags": ",".join(meta.get("metadata", {}).get("tags", [])),
            },
            files={"file": (f"{skill_dir.name}.zip", zip_buffer, "application/zip")},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def update_skill(self, skill_id: str, skill_dir: Path) -> dict:
        """
        Update an existing skill on the hub.

        Re-reads SKILL.md frontmatter, re-zips, and POSTs to the hub API.
        The hub's POST /skills/ handles upsert: same name + same author = update.
        """
        skill_dir = Path(skill_dir)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"No SKILL.md found in {skill_dir}")

        meta = _parse_frontmatter(skill_md.read_text())
        zip_buffer = _zip_skill_dir(skill_dir)

        resp = requests.post(
            self._url("/skills/"),
            headers=self._headers,
            data={
                "name": meta.get("name", skill_dir.name),
                "description": meta.get("description", ""),
                "domain": meta.get("metadata", {}).get("domain", "general"),
                "version": meta.get("metadata", {}).get("version", "0.1.0"),
                "tags": ",".join(meta.get("metadata", {}).get("tags", [])),
            },
            files={"file": (f"{skill_dir.name}.zip", zip_buffer, "application/zip")},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def delete_skill(self, skill_id: str) -> dict:
        """
        Delete a skill from the hub.

        Only works if the current user is the original author or an admin.
        Removes the skill, its archive, and all related social records.
        """
        resp = requests.delete(
            self._url(f"/skills/{skill_id}"),
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def download_skill(self, skill_id: str, dest: Path) -> Path:
        """Download a skill archive from the hub and extract it."""
        resp = requests.get(
            self._url(f"/skills/{skill_id}/download"),
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()

        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)

        # Try to extract as zip
        try:
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
            zf.extractall(dest)
            return dest
        except zipfile.BadZipFile:
            # Save as raw file
            archive_path = dest / "skill_archive.zip"
            archive_path.write_bytes(resp.content)
            return archive_path

    def download_skill_archive(self, skill_id: str, dest_path: Path) -> Path:
        """
        Download the raw skill archive (zipped) to a file path WITHOUT
        unpacking. Used by `buildrix pull` when the user wants the archive
        only - no extraction, no install side-effects.
        """
        resp = requests.get(
            self._url(f"/skills/{skill_id}/download"),
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(resp.content)
        return dest_path

    # -- Test Cases --------------------------------------------------------

    def list_testcases(self, domain: str = "") -> list[dict]:
        params = {}
        if domain:
            params["domain"] = domain
        resp = requests.get(
            self._url("/testcases/"),
            params=params,
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def push_testcase(self, tc_dir: Path) -> dict:
        """Package and upload a test case to the hub."""
        tc_dir = Path(tc_dir)
        tc_yaml = tc_dir / "TESTCASE.yaml"
        if not tc_yaml.exists():
            raise FileNotFoundError(f"No TESTCASE.yaml found in {tc_dir}")

        import yaml
        meta = yaml.safe_load(tc_yaml.read_text())

        # Zip inputs
        input_zip = _zip_subdir(tc_dir / "inputs")
        # Zip expected outputs as reference
        ref_zip = _zip_subdir(tc_dir / "expected_outputs")

        resp = requests.post(
            self._url("/testcases/"),
            headers=self._headers,
            data={
                "name": meta.get("name", tc_dir.name),
                "description": meta.get("description", ""),
                "instructions": meta.get("task", {}).get("prompt", ""),
                "domain": meta.get("domain", "general"),
                "difficulty": meta.get("difficulty", "medium"),
                "tags": ",".join(meta.get("tags", [])),
                "methodology_notes": json.dumps(meta.get("environment", {})),
            },
            files={
                "input_files": ("inputs.zip", input_zip, "application/zip"),
                "reference_output": ("expected.zip", ref_zip, "application/zip"),
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # -- Tasks -------------------------------------------------------------
    #
    # The hub is moving from /testcases to /tasks with the task/2.0 schema.
    # Until that lands everywhere, each call tries the new path and falls back.

    def submit_task(self, task_dir: Path) -> dict:
        """Upload a task/2.0 folder and return the hub's review.

        The public half (TASK.yaml, prompt.md, inputs/, env/, collect.py) and the
        private half (grader/) are uploaded separately, so the server can serve
        one and withhold the other.
        """
        import yaml

        task_dir = Path(task_dir)
        ty = task_dir / "TASK.yaml"
        if not ty.exists():
            raise FileNotFoundError(f"No TASK.yaml in {task_dir}")

        doc = yaml.safe_load(ty.read_text(encoding="utf-8")) or {}
        ident = doc.get("identity") or {}
        tax = doc.get("taxonomy") or {}
        prompt_file = str((doc.get("task") or {}).get("prompt_file") or "prompt.md")
        prompt_path = task_dir / prompt_file
        prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        public = _zip_paths(task_dir, [
            "TASK.yaml", prompt_file, "collect.py", "provenance.md", "inputs", "env",
        ])
        private = _zip_paths(task_dir, ["grader"])

        data = {
            "schema": str(doc.get("schema") or "task/2.0"),
            "slug": str(ident.get("id") or task_dir.name),
            "name": str(ident.get("title") or task_dir.name),
            "version": str(ident.get("version") or "1.0.0"),
            "license_str": str(ident.get("license") or "CC-BY-4.0"),
            "domain": str(tax.get("domain") or ""),
            "tags": ",".join(str(t) for t in (tax.get("tags") or [])),
            "human_minutes": str(tax.get("human_minutes") or 0),
            "instructions": prompt,
            "task_yaml_text": ty.read_text(encoding="utf-8"),
        }
        files = {
            "public_bundle": ("public.zip", public, "application/zip"),
            "grader_bundle": ("grader.zip", private, "application/zip"),
        }
        row = self._post_first(["/tasks/", "/testcases/"], data=data, files=files)
        return review_from_row(row)

    def task_review(self, ident: str) -> dict:
        """Fetch the current review for a task, by slug or id."""
        row = self._get_first([
            f"/tasks/by-slug/{ident}", f"/tasks/{ident}",
            f"/testcases/by-slug/{ident}", f"/testcases/{ident}",
        ])
        return review_from_row(row)

    def list_tasks(self, domain: str = "", search: str = "",
                   sort_by: str = "") -> list[dict]:
        params = {k: v for k, v in
                  (("domain", domain), ("search", search), ("sort_by", sort_by)) if v}
        rows = self._get_first(["/tasks/", "/testcases/"], params=params)
        return rows if isinstance(rows, list) else rows.get("items", [])

    # -- Reviews -----------------------------------------------------------

    def submit_skill(self, skill_dir: Path) -> dict:
        """Upload a skill and return the hub's review of it.

        Same endpoint as ``push_skill``; this wrapper exists because the CLI
        cares about the review, not the row.
        """
        return review_from_row(self.push_skill(skill_dir))

    def skill_review(self, name: str) -> dict:
        """Fetch the current review for a skill, by name."""
        row = self._get_first([f"/skills/by-name/{name}", f"/skills/{name}"])
        return review_from_row(row)

    # -- Domains -----------------------------------------------------------

    def domains(self, kind: str = "skill") -> list[str]:
        """The hub's domain list, falling back to the packaged one offline."""
        try:
            data = self._get_first(["/domains", "/domains/"], params={"kind": kind})
            if isinstance(data, list):
                return [d if isinstance(d, str) else d.get("id", "") for d in data]
            if isinstance(data, dict) and data.get("domains"):
                return [d if isinstance(d, str) else d.get("id", "") for d in data["domains"]]
        except Exception:
            pass
        from buildrix import domains as _d
        return _d.TASK_DOMAINS if kind == "task" else _d.SKILL_DOMAINS

    # -- Request helpers ---------------------------------------------------

    def _get_first(self, paths: list[str], params: dict | None = None):
        """GET the first path that is not a 404. Raises the last error."""
        last: Exception | None = None
        for path in paths:
            try:
                resp = requests.get(self._url(path), params=params or {},
                                    headers=self._headers, timeout=20)
                if resp.status_code == 404:
                    last = requests.HTTPError(f"404 {path}")
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                last = e
        raise last or requests.HTTPError("no endpoint responded")

    def _post_first(self, paths: list[str], data: dict, files: dict):
        """POST to the first path that is not a 404. Raises the last error."""
        last: Exception | None = None
        for path in paths:
            for buf in files.values():
                try:
                    buf.seek(0)
                except Exception:
                    pass
            try:
                resp = requests.post(self._url(path), headers=self._headers,
                                     data=data, files=files, timeout=120)
                if resp.status_code == 404:
                    last = requests.HTTPError(f"404 {path}")
                    continue
                if resp.status_code >= 400:
                    raise requests.HTTPError(
                        f"{resp.status_code} {path}: {resp.text[:300]}")
                return resp.json()
            except requests.RequestException as e:
                last = e
        raise last or requests.HTTPError("no endpoint responded")

    # -- Challenges --------------------------------------------------------

    def list_challenges(self, domain: str = "") -> list[dict]:
        params = {}
        if domain:
            params["domain"] = domain
        resp = requests.get(
            self._url("/challenges/"),
            params=params,
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # -- Stats -------------------------------------------------------------

    def stats(self) -> dict:
        resp = requests.get(self._url("/stats"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict:
        resp = requests.get(self._url("/health"), timeout=5)
        resp.raise_for_status()
        return resp.json()


# -- Helpers ---------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a SKILL.md file."""
    import yaml

    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def _zip_skill_dir(skill_dir: Path) -> io.BytesIO:
    """Zip a skill directory into a BytesIO buffer, excluding __pycache__."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file() and "__pycache__" not in str(file_path):
                arcname = file_path.relative_to(skill_dir)
                zf.write(file_path, arcname)
    buf.seek(0)
    return buf


def _zip_subdir(directory: Path) -> io.BytesIO:
    """Zip a subdirectory into a BytesIO buffer."""
    buf = io.BytesIO()
    directory = Path(directory)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if directory.exists():
            for f in directory.rglob("*"):
                if f.is_file() and f.name != ".gitkeep":
                    zf.write(f, f.relative_to(directory))
        else:
            # Write an empty placeholder
            zf.writestr("_empty", "")
    buf.seek(0)
    return buf


def review_from_row(row: dict) -> dict:
    """Normalise a hub row into the report shape the CLI renders.

    Accepts the new ``review`` payload and the older ``llm_review_*`` columns,
    so the CLI keeps working across the server rewrite.
    """
    if not isinstance(row, dict):
        return {"verdict": "", "findings": []}
    if isinstance(row.get("review"), dict):
        out = dict(row["review"])
    else:
        out = {
            "verdict": row.get("llm_review_status") or row.get("status") or "",
            "round": row.get("review_round") or 0,
            "llm_review_checklist": row.get("llm_review_checklist") or {},
            "rewrite": row.get("suggested_rewrite") or "",
            "missing": row.get("missing") or [],
        }
    out.setdefault("title", row.get("name") or row.get("slug") or "")
    for key in ("id", "slug", "name", "status"):
        if key in row:
            out.setdefault(key, row[key])
    if not out.get("findings") and row.get("llm_review_comments"):
        out["findings"] = [{
            "area": "reviewer",
            "level": "concern",
            "message": str(row["llm_review_comments"])[:2000],
        }]
    return out


def _zip_paths(root: Path, members: list[str]) -> io.BytesIO:
    """Zip a chosen set of files and folders, relative to ``root``."""
    buf = io.BytesIO()
    root = Path(root)
    wrote = False
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for member in members:
            src = root / member
            if src.is_file():
                zf.write(src, src.relative_to(root))
                wrote = True
            elif src.is_dir():
                for f in src.rglob("*"):
                    if (f.is_file() and "__pycache__" not in f.parts
                            and f.name != ".gitkeep"):
                        zf.write(f, f.relative_to(root))
                        wrote = True
        if not wrote:
            zf.writestr("_empty", "")
    buf.seek(0)
    return buf
