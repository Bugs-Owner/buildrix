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

    # ── Auth ──────────────────────────────────────────────────────────────

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

    # ── Skills ────────────────────────────────────────────────────────────

    def list_skills(self, domain: str = "", search: str = "",
                    sort_by: str = "") -> list[dict]:
        """List skills from the hub."""
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

        Re-reads SKILL.md frontmatter, re-zips, and PUTs to the hub API.
        Only works if the current user is the original author.
        """
        skill_dir = Path(skill_dir)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"No SKILL.md found in {skill_dir}")

        meta = _parse_frontmatter(skill_md.read_text())
        zip_buffer = _zip_skill_dir(skill_dir)

        resp = requests.put(
            self._url(f"/skills/{skill_id}"),
            headers=self._headers,
            data={
                "description": meta.get("description", ""),
                "domain": meta.get("metadata", {}).get("domain", ""),
                "version": meta.get("metadata", {}).get("version", ""),
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

    # ── Test Cases ────────────────────────────────────────────────────────

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

    # ── Challenges ────────────────────────────────────────────────────────

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

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        resp = requests.get(self._url("/stats"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict:
        resp = requests.get(self._url("/health"), timeout=5)
        resp.raise_for_status()
        return resp.json()


# ── Helpers ───────────────────────────────────────────────────────────────

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
