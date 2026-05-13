"""Skill manager — install, list, uninstall, and provision toolchain."""

import shutil
from pathlib import Path

import yaml

from buildrix.config import SKILLS_DIR, CLAUDE_SKILLS_DIR


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
    Download a skill from the hub, install locally, and provision its
    toolchain (EnergyPlus, OpenStudio, etc.) automatically.
    """
    from buildrix.hub_client import HubClient

    client = HubClient(hub_url=hub_url)

    skills = client.list_skills(search=name_or_id)
    if not skills:
        raise ValueError(f"Skill '{name_or_id}' not found on the hub.")

    skill = skills[0]
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

    # Auto-provision toolchain from config.yaml
    provision_toolchain(dest)

    return dest


def install_local(skill_dir: Path) -> Path:
    """
    Install a skill from a local directory (copy + link + provision).
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

    # Auto-provision toolchain from config.yaml
    provision_toolchain(dest)

    return dest


def uninstall_skill(name: str):
    """Remove a locally installed skill."""
    dest = SKILLS_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
        print(f"  Removed {dest}")

    link = CLAUDE_SKILLS_DIR / name
    if link.is_symlink():
        link.unlink()
        print(f"  Removed Claude Code link")
    elif link.exists():
        shutil.rmtree(link)
        print(f"  Removed Claude Code copy")


# ── Toolchain provisioning ─────────────────────────────────────────
def provision_toolchain(skill_dir: Path) -> list[str]:
    """
    Read a skill's config.yaml and download any declared toolchain
    dependencies. Supports both full specs (with URLs) and simple
    version strings.

    Returns list of tools provisioned.
    """
    config_path = skill_dir / "config.yaml"
    if not config_path.exists():
        return []

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    toolchain_section = config.get("environment", {}).get("toolchain", {})
    if not toolchain_section:
        return []

    from buildrix.env.toolchain import Toolchain

    tc = Toolchain()
    provisioned = []

    for tool_name, spec in toolchain_section.items():
        try:
            if isinstance(spec, dict):
                # Full spec with URLs — the correct way
                version = spec.get("version", "unknown")
                print(f"  Provisioning {tool_name} {version}...")
                tc.ensure(tool_name, spec=spec)
                provisioned.append(f"{tool_name}=={version}")
            elif isinstance(spec, str):
                # Bare version string (legacy)
                print(f"  Provisioning {tool_name} {spec}...")
                tc.ensure(tool_name, version=spec)
                provisioned.append(f"{tool_name}=={spec}")
        except Exception as e:
            print(f"  ⚠️  Failed to provision {tool_name}: {e}")

    if provisioned:
        print(f"  ✅ Toolchain ready: {', '.join(provisioned)}")

    return provisioned


# ── Internal ───────────────────────────────────────────────────────
def _link_to_claude(name: str, source: Path):
    """Create symlink in Claude Code's skills directory."""
    CLAUDE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    link = CLAUDE_SKILLS_DIR / name

    if link.is_symlink():
        link.unlink()
    elif link.exists():
        shutil.rmtree(link)

    try:
        link.symlink_to(source)
        print(f"  Linked to Claude Code: {link}")
    except OSError:
        shutil.copytree(source, link)
        print(f"  Copied to Claude Code: {link} (symlink not supported)")
