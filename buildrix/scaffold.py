"""Scaffold new skills and test cases from templates."""

import shutil
from pathlib import Path

from buildrix.config import get_user

# Templates are bundled with the package
_PACKAGE_DIR = Path(__file__).parent.parent
_TEMPLATES_DIR = _PACKAGE_DIR / "templates"

# Text file extensions to search-and-replace in
_TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".txt", ".py", ".json", ""}


def scaffold_skill(name: str, target_dir: str = ".") -> Path:
    """
    Create a new skill directory from the standardized template.

    Generates the full Buildrix skill structure:
        skill-name/
        ├── SKILL.md           # Agent instructions (fill in)
        ├── config.yaml        # Structured metadata (fill in)
        ├── NOTES.md           # Error notebook (agent-managed)
        ├── CHANGELOG.md       # Version history
        ├── LICENSE             # Apache 2.0
        ├── requirements.txt   # Skill-specific dependencies
        ├── scripts/
        │   └── main.py        # Entry point (fill in)
        ├── tests/
        │   └── test_main.py   # Unit tests
        ├── references/
        │   └── README.md
        └── assets/
            └── README.md
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

    # Get author info from login (if available)
    user = get_user()
    author_name = user.get("name", "") if user else ""
    author_email = user.get("email", "") if user else ""

    # Replace placeholders across all text files
    title = _to_title(name)
    replacements = {
        "your-skill-name": name,
        "Your Skill Name": title,
        "[Author Name]": author_name or "[Author Name]",
    }

    # Also fill in config.yaml author fields
    config_replacements = {
        '  name: ""               # Your display name': f'  name: "{author_name}"',
        '  email: ""              # Contact email': f'  email: "{author_email}"',
    }

    for file_path in dest.rglob("*"):
        if file_path.is_file() and file_path.suffix in _TEXT_EXTENSIONS:
            try:
                content = file_path.read_text()
                for old, new in replacements.items():
                    content = content.replace(old, new)
                if file_path.name == "config.yaml":
                    for old, new in config_replacements.items():
                        content = content.replace(old, new)
                file_path.write_text(content)
            except (UnicodeDecodeError, PermissionError):
                continue

    print(f"✅ Created skill: {dest}")
    print()
    print(f"  {dest}/")
    print(f"  ├── SKILL.md           ← describe what the skill does")
    print(f"  ├── config.yaml        ← fill in metadata")
    print(f"  ├── scripts/main.py    ← put your code here")
    print(f"  ├── tests/test_main.py ← add tests")
    print(f"  ├── requirements.txt   ← skill dependencies")
    print(f"  ├── references/        ← papers, docs")
    print(f"  ├── assets/            ← templates, data")
    print(f"  ├── NOTES.md           ← agent error log (auto)")
    print(f"  ├── CHANGELOG.md       ← version history")
    print(f"  └── LICENSE")
    print()
    print("  Next steps:")
    print(f"  1. Edit SKILL.md and config.yaml")
    print(f"  2. Put your code in scripts/main.py")
    print(f"  3. Test: buildrix dev {dest}")
    print(f"  4. Push: buildrix push {dest}")
    print()

    return dest


def scaffold_testcase(name: str, target_dir: str = ".") -> Path:
    """Create a new test case directory from the template."""
    dest = Path(target_dir) / name
    if dest.exists():
        raise FileExistsError(f"Directory already exists: {dest}")

    template = _TEMPLATES_DIR / "testcase"
    if not template.exists():
        raise FileNotFoundError(f"Test case template not found at {template}.")

    shutil.copytree(template, dest, ignore=shutil.ignore_patterns(".gitkeep"))

    # Replace placeholder
    tc_yaml = dest / "TESTCASE.yaml"
    content = tc_yaml.read_text()
    content = content.replace("your-testcase-name", name)
    tc_yaml.write_text(content)

    print(f"✅ Created test case: {dest}")
    print()
    print(f"  {dest}/")
    print(f"  ├── TESTCASE.yaml      ← define the task and expected outputs")
    print(f"  ├── inputs/            ← input data files")
    print(f"  └── expected_outputs/  ← gold-standard reference outputs")
    print()
    print("  Next steps:")
    print(f"  1. Edit TESTCASE.yaml")
    print(f"  2. Add data to inputs/ and expected_outputs/")
    print(f"  3. Push: buildrix push {dest}")
    print()

    return dest


def _to_title(name: str) -> str:
    """Convert 'heat-wave-identification' to 'Heat Wave Identification'."""
    return " ".join(w.capitalize() for w in name.replace("-", " ").replace("_", " ").split())
