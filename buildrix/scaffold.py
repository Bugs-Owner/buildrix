"""Scaffold new skills and test cases from templates."""

import shutil
from pathlib import Path

# Templates are bundled with the package
_PACKAGE_DIR = Path(__file__).parent.parent
_TEMPLATES_DIR = _PACKAGE_DIR / "templates"


def scaffold_skill(name: str, target_dir: str = ".") -> Path:
    """
    Create a new skill directory from the template.

    Parameters
    ----------
    name : str
        Skill name (e.g., "heat-wave-identification")
    target_dir : str
        Parent directory where the skill folder will be created

    Returns
    -------
    Path to the created skill directory
    """
    dest = Path(target_dir) / name
    if dest.exists():
        raise FileExistsError(f"Directory already exists: {dest}")

    template = _TEMPLATES_DIR / "skill"
    if not template.exists():
        raise FileNotFoundError(
            f"Skill template not found at {template}. "
            "Make sure you're running from a buildrix repo clone."
        )

    shutil.copytree(template, dest, ignore=shutil.ignore_patterns(".gitkeep"))

    # Replace placeholder values in SKILL.md
    skill_md = dest / "SKILL.md"
    content = skill_md.read_text()
    content = content.replace("your-skill-name", name)
    content = content.replace("Your Skill Name", _to_title(name))
    skill_md.write_text(content)

    print(f"✅ Created skill scaffold: {dest}")
    print()
    print("  Next steps:")
    print(f"  1. Edit {dest}/SKILL.md — fill in description, instructions, examples")
    print(f"  2. Add your scripts to {dest}/scripts/")
    print(f"  3. Test locally: buildrix dev {name}")
    print(f"  4. Push to hub: buildrix push {dest}")
    print()

    return dest


def scaffold_testcase(name: str, target_dir: str = ".") -> Path:
    """
    Create a new test case directory from the template.
    """
    dest = Path(target_dir) / name
    if dest.exists():
        raise FileExistsError(f"Directory already exists: {dest}")

    template = _TEMPLATES_DIR / "testcase"
    if not template.exists():
        raise FileNotFoundError(f"Test case template not found at {template}.")

    shutil.copytree(template, dest, ignore=shutil.ignore_patterns(".gitkeep"))

    # Replace placeholder in TESTCASE.yaml
    tc_yaml = dest / "TESTCASE.yaml"
    content = tc_yaml.read_text()
    content = content.replace("your-testcase-name", name)
    tc_yaml.write_text(content)

    print(f"✅ Created test case scaffold: {dest}")
    print()
    print("  Next steps:")
    print(f"  1. Edit {dest}/TESTCASE.yaml — define the task, inputs, expected outputs")
    print(f"  2. Add input data to {dest}/inputs/")
    print(f"  3. Add reference outputs to {dest}/expected_outputs/")
    print(f"  4. Push to hub: buildrix push {dest}")
    print()

    return dest


def _to_title(name: str) -> str:
    """Convert 'heat-wave-identification' to 'Heat Wave Identification'."""
    return " ".join(w.capitalize() for w in name.replace("-", " ").replace("_", " ").split())
