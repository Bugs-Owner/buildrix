"""Skill manager — install, list, uninstall, and link skills to agent tools."""

import shutil
from pathlib import Path

from buildrix.config import SKILLS_DIR, CLAUDE_SKILLS_DIR
from buildrix.hub_client import HubClient


def installed_skills() -> list[dict]:
    """List locally installed skills with metadata."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            # Check one level deeper (in case archive extracted with wrapper dir)
            for sub in skill_dir.iterdir():
                if sub.is_dir() and (sub / "SKILL.md").exists():
                    skill_md = sub / "SKILL.md"
                    skill_dir = sub
                    break

        info = {"name": skill_dir.name, "path": str(skill_dir)}
        if skill_md.exists():
            from buildrix.hub_client import _parse_frontmatter
            meta = _parse_frontmatter(skill_md.read_text())
            info["description"] = meta.get("description", "")
            info["version"] = meta.get("metadata", {}).get("version", "")
            info["domain"] = meta.get("metadata", {}).get("domain", "")
        skills.append(info)

    return skills


def install_skill(name_or_id: str, hub_url: str = "") -> Path:
    """
    Download a skill from the hub and install locally.

    1. Search hub for the skill by name
    2. Download the archive
    3. Extract to ~/.buildrix/skills/<name>/
    4. Symlink to ~/.claude/skills/<name>/ for Claude Code discovery
    """
    client = HubClient(hub_url=hub_url)

    # Search by name
    skills = client.list_skills(search=name_or_id)
    if not skills:
        raise ValueError(f"Skill '{name_or_id}' not found on the hub.")

    skill = skills[0]  # Best match
    skill_id = skill["id"]
    skill_name = skill["name"]

    dest = SKILLS_DIR / skill_name
    if dest.exists():
        shutil.rmtree(dest)

    print(f"  Downloading '{skill_name}'...")
    client.download_skill(skill_id, dest)
    print(f"  Installed to {dest}")

    # Symlink to Claude Code skills directory
    _link_to_claude(skill_name, dest)

    return dest


def install_local(skill_dir: Path) -> Path:
    """
    Install a skill from a local directory (copy + link).
    Useful for developing: test your skill with Claude Code.
    """
    skill_dir = Path(skill_dir).resolve()
    if not (skill_dir / "SKILL.md").exists():
        raise FileNotFoundError(f"No SKILL.md in {skill_dir}")

    name = skill_dir.name
    dest = SKILLS_DIR / name

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_dir, dest)
    print(f"  Installed '{name}' from local directory")

    _link_to_claude(name, dest)
    return dest


def uninstall_skill(name: str):
    """Remove a locally installed skill."""
    dest = SKILLS_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
        print(f"  Removed {dest}")

    # Remove Claude Code link (symlink on Linux/Mac, directory copy on Windows)
    link = CLAUDE_SKILLS_DIR / name
    if link.is_symlink():
        link.unlink()
        print(f"  Removed Claude Code link")
    elif link.exists():
        shutil.rmtree(link)
        print(f"  Removed Claude Code copy")


def _link_to_claude(name: str, source: Path):
    """Create symlink in Claude Code's skills directory."""
    CLAUDE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    link = CLAUDE_SKILLS_DIR / name

    # Clean up existing — symlink or directory copy
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        shutil.rmtree(link)

    try:
        link.symlink_to(source)
        print(f"  Linked to Claude Code: {link}")
    except OSError:
        # Symlinks may fail on Windows without admin, fall back to copy
        shutil.copytree(source, link)
        print(f"  Copied to Claude Code: {link} (symlink not supported)")