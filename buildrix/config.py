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

# ─── Canonical domain list ──────────────────────────────────────────────────
# MUST match the DOMAINS array in static/index.html on the hub frontend.
# When you change this list, change both — they're the canonical taxonomy
# documented in the Buildrix paper (Section 3, "Skill Categories").
VALID_DOMAINS = [
    "general",                # 1. cross-cutting helpers
    "weather-climate",        # 2. TMY, EPW, climate analysis
    "energy-modeling",        # 3. EnergyPlus, OpenStudio, eQUEST
    "hvac-mechanical",        # 4. sizing, sequences, equipment
    "controls-optimization",  # 5. MPC, RL, supervisory control
    "thermal-comfort-ieq",    # 6. PMV/PPD, adaptive, IAQ, ventilation
    "lighting-daylighting",   # 7. Radiance, daylight autonomy
    "envelope",               # 8. U-values, thermal bridges, WWR
    "semantic-modeling",      # 9. Brick, Haystack, RealEstateCore
    "bim-geometry",           # 10. IFC, Revit, geometry extraction
    "sensor-operations",      # 11. BAS data, FDD, KPI dashboards
    "grid-demand-response",   # 12. tariffs, DR, flexibility
    "embodied-carbon-lca",    # 13. EPDs, material LCA
    "code-compliance",        # 14. ASHRAE 90.1, 55, 62.1, IECC
    "structural",             # 15. loads, sizing, drawings
    "cost-construction",      # 16. estimating, scheduling, takeoff
]


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
