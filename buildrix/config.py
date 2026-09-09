"""Local configuration management for Buildrix CLI."""

import json
from pathlib import Path
from typing import Optional

# Default paths
BUILDRIX_HOME = Path.home() / ".buildrix"
CONFIG_FILE   = BUILDRIX_HOME / "config.json"
SKILLS_DIR    = BUILDRIX_HOME / "skills"
DEFAULT_HUB_URL = "http://localhost:8000"

# Claude Code integration
CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"

# --- Canonical domain list ---------------------------------------------------
# The list itself lives in buildrix/domains.py, and the hub serves the same one
# at GET /api/domains. Re-exported here for the older call sites.
from buildrix.domains import SKILL_DOMAINS as VALID_DOMAINS  # noqa: E402,F401
from buildrix.domains import TASK_DOMAINS  # noqa: E402,F401


def ensure_dirs():
    BUILDRIX_HOME.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_dirs()
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {"hub_url": DEFAULT_HUB_URL, "token": "", "user": None}


def save_config(cfg: dict):
    ensure_dirs()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_token() -> str:
    return load_config().get("token", "")


def get_hub_url() -> str:
    return load_config().get("hub_url", DEFAULT_HUB_URL)


def get_user() -> Optional[dict]:
    return load_config().get("user")


def set_auth(token: str, user: dict, hub_url: str = ""):
    cfg = load_config()
    cfg["token"] = token
    cfg["user"]  = user
    if hub_url:
        cfg["hub_url"] = hub_url
    save_config(cfg)


def clear_auth():
    cfg = load_config()
    cfg["token"] = ""
    cfg["user"]  = None
    save_config(cfg)


def set_hub_url(url: str):
    cfg = load_config()
    cfg["hub_url"] = url.rstrip("/")
    save_config(cfg)
