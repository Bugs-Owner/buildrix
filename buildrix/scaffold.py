"""Scaffold new skills and tasks from the bundled templates."""

from __future__ import annotations

import shutil
from pathlib import Path

from buildrix.config import get_user

_PACKAGE_DIR = Path(__file__).parent.parent
_TEMPLATES_DIR = _PACKAGE_DIR / "templates"
_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".txt", ".py", ".json"}


def scaffold_skill(name: str, target_dir: str = ".") -> Path:
    """Create a skill/2.0 folder.

        skill-name/
        |-- SKILL.md            frontmatter + the seven required sections
        |-- requirements.txt    pinned dependencies
        |-- scripts/main.py     your code
        |-- tests/test_main.py  runnable checks
        |-- references/         long-form docs, loaded on demand
        |-- assets/             templates, lookup tables, small data
        +-- NOTES.md            what went wrong and what fixed it
    """
    dest = _copy_template("skill", name, target_dir)

    user = get_user() or {}
    author = user.get("display_name") or user.get("name") or ""
    affiliation = user.get("affiliation") or ""

    _replace(dest, {
        "your-skill-name": name,
        "Your Skill Name": _title(name),
        '"[Your Name]"': f'"{author}"' if author else '"[Your Name]"',
        'affiliation: ""': f'affiliation: "{affiliation}"' if affiliation else 'affiliation: ""',
    })

    print(f"\n  created  {dest}\n")
    _tree([
        ("SKILL.md", "what it does, when to use it, how it runs"),
        ("requirements.txt", "pinned dependencies"),
        ("scripts/main.py", "your code"),
        ("tests/test_main.py", "at least one end-to-end test"),
        ("references/", "long-form docs, loaded on demand"),
        ("assets/", "templates and small data"),
        ("NOTES.md", "error log"),
    ])
    print("  next\n"
          "    1. write the description in SKILL.md - an agent decides from that alone\n"
          "    2. put your code in scripts/ and a test in tests/\n"
          f"    3. buildrix skill check {dest}\n"
          f"    4. buildrix skill submit {dest}\n")
    return dest


def scaffold_task(name: str, target_dir: str = ".") -> Path:
    """Create a task/2.0 folder.

        task-name/
        |-- TASK.yaml           the contract
        |-- prompt.md           the only text the agent reads
        |-- inputs/             what the agent starts with
        |-- env/requirements.txt
        |-- collect.py          workspace -> submission bundle
        |-- provenance.md       whose work this was
        +-- grader/             PRIVATE - never leaves the server
            |-- grade.py
            |-- reference/      your own answer
            +-- mutations/      wrong-but-plausible answers
    """
    dest = _copy_template("task", name, target_dir)

    user = get_user() or {}
    author = user.get("display_name") or user.get("name") or ""
    affiliation = user.get("affiliation") or ""

    _replace(dest, {
        "your-task-name": name,
        '"[Your Name]"': f'"{author}"' if author else '"[Your Name]"',
        'affiliation: ""': f'affiliation: "{affiliation}"' if affiliation else 'affiliation: ""',
    })

    print(f"\n  created  {dest}\n")
    _tree([
        ("TASK.yaml", "the contract: deliverables, rules, checks"),
        ("prompt.md", "the only text the agent reads"),
        ("inputs/", "what the agent starts with"),
        ("env/requirements.txt", "pinned"),
        ("collect.py", "reduces a finished workspace to a small bundle"),
        ("grader/grade.py", "private; scores a bundle against the reference"),
        ("grader/reference/", "private; your own answer"),
        ("grader/mutations/", "private; three wrong-but-plausible answers"),
        ("provenance.md", "whose work this was"),
    ])
    print("  next\n"
          "    1. write prompt.md as you would brief a new engineer\n"
          "    2. put your own answer in grader/reference/\n"
          "    3. add three degraded copies under grader/mutations/\n"
          f"    4. buildrix task check {dest}\n"
          f"    5. buildrix task submit {dest}\n")
    return dest


# Kept so older docs and scripts keep working.
scaffold_testcase = scaffold_task


# -- helpers -----------------------------------------------------------------

def _copy_template(kind: str, name: str, target_dir: str) -> Path:
    dest = Path(target_dir) / name
    if dest.exists():
        raise FileExistsError(f"{dest} already exists")

    template = _TEMPLATES_DIR / kind
    if not template.exists():
        raise FileNotFoundError(
            f"Template not found at {template}. Reinstall buildrix, or run from a clone."
        )
    shutil.copytree(template, dest)
    for keep in dest.rglob(".gitkeep"):
        keep.unlink()
    return dest


def _replace(root: Path, mapping: dict[str, str]) -> None:
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        new = text
        for old, repl in mapping.items():
            new = new.replace(old, repl)
        if new != text:
            f.write_text(new, encoding="utf-8")


def _tree(rows: list[tuple[str, str]]) -> None:
    width = max(len(r[0]) for r in rows) + 2
    for i, (path, note) in enumerate(rows):
        stem = "+--" if i == len(rows) - 1 else "|--"
        print(f"  {stem} {path:<{width}} {note}")
    print()


def _title(name: str) -> str:
    return " ".join(w.capitalize() for w in name.replace("-", " ").replace("_", " ").split())
