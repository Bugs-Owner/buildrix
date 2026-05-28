"""
IDE Guard — prevent editors from indexing large data/output directories.

ResStock weather data (~1 GB of TMY3 files) and simulation outputs
(thousands of IDFs and CSVs) will freeze VS Code and PyCharm if indexed.
Call setup_ide_guard() once per project to write exclusion configs.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

# Directories to exclude (relative patterns and absolute paths)
_EXCLUDE_PATTERNS = [
    "outputs",
    "results_baseline",
    "results_upgraded",
    "simulation_results",
    "**/*.epw",
    "**/*.idf",
    "**/*.osm",
    "**/tmy3",
]

_GITIGNORE_LINES = [
    "# Buildrix — large data and simulation outputs",
    "outputs/",
    "results_baseline/",
    "results_upgraded/",
    "simulation_results/",
    "*.epw",
    "*.sql",
    "*.eso",
    "*.mtr",
    "*.rdd",
    "*.shd",
]


def setup_ide_guard(
    project_dir: str = ".",
    data_dir: Optional[str] = None,
) -> list[str]:
    """
    Write exclusion configs for VS Code, PyCharm/IntelliJ, and .gitignore.

    Parameters
    ----------
    project_dir : str
        Root of the user's project.
    data_dir : str, optional
        The shared data directory (~/.buildrix/data by default).

    Returns
    -------
    list[str]
        Paths of files created or updated.
    """
    project = Path(project_dir).resolve()
    data = Path(data_dir) if data_dir else Path.home() / ".buildrix" / "data"

    touched = []

    touched.extend(_setup_vscode(project, data))
    touched.extend(_setup_idea(project, data))
    touched.extend(_setup_gitignore(project))

    if touched:
        print(f"  [ide_guard] Updated {len(touched)} config(s) in {project}")
    return touched


# ── VS Code ────────────────────────────────────────────────────────
def _setup_vscode(project: Path, data: Path) -> list[str]:
    """Add file exclusions to .vscode/settings.json."""
    vscode_dir = project / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    settings_path = vscode_dir / "settings.json"

    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            settings = {}

    excludes = settings.setdefault("files.exclude", {})
    search_excludes = settings.setdefault("search.exclude", {})
    watcher_excludes = settings.setdefault("files.watcherExclude", {})

    changed = False
    for pattern in _EXCLUDE_PATTERNS:
        for target in (excludes, search_excludes, watcher_excludes):
            if pattern not in target:
                target[pattern] = True
                changed = True

    # Exclude the shared data directory
    data_str = str(data)
    for target in (search_excludes, watcher_excludes):
        if data_str not in target:
            target[data_str] = True
            changed = True

    if changed:
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        return [str(settings_path)]
    return []


# ── PyCharm / IntelliJ ────────────────────────────────────────────
def _setup_idea(project: Path, data: Path) -> list[str]:
    """Mark directories as excluded in .idea/ config."""
    idea_dir = project / ".idea"
    if not idea_dir.exists():
        return []  # Only update if PyCharm already initialised the project

    # Find the .iml file (project module)
    iml_files = list(idea_dir.glob("*.iml"))
    if not iml_files:
        return []

    touched = []
    for iml_path in iml_files:
        try:
            tree = ET.parse(iml_path)
            root = tree.getroot()
        except ET.ParseError:
            continue

        content = root.find(".//content[@url='file://$MODULE_DIR$']")
        if content is None:
            continue

        existing = {
            ef.get("url", "") for ef in content.findall("excludeFolder")
        }

        changed = False
        for pattern in ["outputs", "results_baseline", "results_upgraded",
                        "simulation_results"]:
            url = f"file://$MODULE_DIR$/{pattern}"
            if url not in existing:
                ET.SubElement(content, "excludeFolder", url=url)
                changed = True

        if changed:
            tree.write(str(iml_path), xml_declaration=True, encoding="utf-8")
            touched.append(str(iml_path))

    return touched


# ── .gitignore ─────────────────────────────────────────────────────
def _setup_gitignore(project: Path) -> list[str]:
    """Append exclusion lines to .gitignore if not already present."""
    gi_path = project / ".gitignore"
    existing = ""
    if gi_path.exists():
        existing = gi_path.read_text()

    new_lines = [
        line for line in _GITIGNORE_LINES
        if line not in existing
    ]

    if not new_lines:
        return []

    with open(gi_path, "a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n".join(new_lines) + "\n")

    return [str(gi_path)]
