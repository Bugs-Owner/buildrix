"""The eight mechanical rules for a `skill/2.0` package.

Nothing here needs the network or a language model. The reviewer that reads the
prose runs on the hub; these are the checks that either hold or do not.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

from buildrix import domains, spec
from buildrix.report import Report

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)
_H2 = re.compile(r"^##\s+(.+?)\s*$", re.M)
_ABS_PATH = re.compile(r"(?:[A-Za-z]:[\\/]{1,2}[\w.\\/ -]{3,})|(?:/(?:Users|home|mnt/c)/[\w./-]{3,})")
_SECRET = re.compile(
    r"(sk-[A-Za-z0-9]{16,})"
    r"|(gh[pousr]_[A-Za-z0-9]{16,})"
    r"|(AKIA[0-9A-Z]{16})"
    r"|((?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"])",
    re.I,
)
_URL_HOST = re.compile(r"https?://([A-Za-z0-9.\-]+)")
_TEXT_SUFFIXES = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".cfg", ".toml", ".sh"}
_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".idea"}


def estimate_tokens(text: str) -> int:
    """Rough token count. Four characters per token is close enough to budget."""
    return max(1, round(len(text) / 4))


def check_skill(path: str | Path, *, run_tests: bool = True,
                check_determinism: bool = False) -> Report:
    """Run every skill/2.0 rule against a directory. Never raises."""
    d = Path(path).expanduser().resolve()
    rep = Report(title=f"skill check | {d.name}")

    # -- 1. structure --------------------------------------------------------
    md = d / "SKILL.md"
    if not d.is_dir():
        rep.blocker("structure", f"{d} is not a directory.")
        return rep
    if not md.exists():
        rep.blocker("structure", "No SKILL.md at the top of the folder.",
                    "Run `buildrix skill new <name>` and move your code into it.")
        return rep

    text = md.read_text(encoding="utf-8", errors="replace")
    m = _FRONTMATTER.match(text)
    if not m:
        rep.blocker("structure", "SKILL.md has no YAML frontmatter.",
                    "Start the file with a --- fenced block holding name and description.")
        return rep

    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        rep.blocker("structure", f"The frontmatter is not valid YAML: {e}")
        return rep
    body = m.group(2)

    stray = [p.name for p in d.iterdir()
             if p.name not in {
                 "SKILL.md", "NOTES.md", "README.md", "LICENSE", "CHANGELOG.md",
                 "requirements.txt", "scripts", "references", "assets", "tests",
             } and not p.name.startswith(".")]
    if stray:
        rep.concern("structure",
                    f"Unexpected entries at the top level: {', '.join(sorted(stray)[:6])}.",
                    "Keep the root to SKILL.md, requirements.txt, scripts/, references/, "
                    "assets/, tests/ and NOTES.md.")
    else:
        rep.ok("structure")

    # -- 2. frontmatter ------------------------------------------------------
    meta = fm.get("metadata") or {}
    name = str(fm.get("name") or "")
    problems: list[str] = []
    if not name:
        problems.append("`name` is missing")
    elif name != d.name:
        problems.append(f"`name` is '{name}' but the folder is '{d.name}'")
    elif not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        problems.append("`name` must be lower case words joined by hyphens")

    if not isinstance(meta, dict):
        problems.append("`metadata` must be a mapping")
        meta = {}
    else:
        schema = str(meta.get("buildrix_schema") or "")
        if schema != spec.SKILL_SCHEMA:
            problems.append(f"`metadata.buildrix_schema` should be \"{spec.SKILL_SCHEMA}\"")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(meta.get("version") or "")):
            problems.append("`metadata.version` must be semver, e.g. 0.1.0")
        dom = str(meta.get("domain") or "")
        if not dom:
            problems.append("`metadata.domain` is missing")
        elif not domains.is_valid(dom, kind="skill"):
            problems.append(f"`metadata.domain` '{dom}' is not one of the eight (or general)")
        det = str(meta.get("determinism") or "")
        if det and det not in spec.DETERMINISM_VALUES:
            problems.append("`metadata.determinism` must be "
                            + " | ".join(spec.DETERMINISM_VALUES))

    for k in ("name", "description"):
        if not fm.get(k):
            problems.append(f"`{k}` is required by the open Agent Skills standard")

    top_level_extras = set(fm) - {
        "name", "description", "license", "allowed-tools", "metadata", "version",
    }
    if top_level_extras:
        problems.append("Buildrix fields belong under `metadata:`, not at the top level: "
                        + ", ".join(sorted(top_level_extras)))

    if problems:
        rep.blocker("frontmatter", "; ".join(problems[:4]) + ".",
                    "See spec/02-SKILL_FORMAT.md for the full frontmatter.")
    else:
        rep.ok("frontmatter", domains.short(str(meta.get("domain", ""))))

    # -- 3. description ------------------------------------------------------
    desc = " ".join(str(fm.get("description") or "").split())
    if len(desc) < spec.DESCRIPTION_MIN:
        rep.blocker("description",
                    f"Only {len(desc)} characters. An agent decides from this alone.",
                    "Say what it does, then when to use it, in two or three sentences.")
    elif len(desc) > spec.DESCRIPTION_MAX:
        rep.blocker("description",
                    f"{len(desc)} characters, over the {spec.DESCRIPTION_MAX} limit.",
                    "Move the detail into the Overview section.")
    elif not any(p in desc.lower() for p in spec.TRIGGER_PHRASES):
        rep.concern("description", "It says what the skill does but not when to use it.",
                    'Add a trigger sentence: "Use when a task involves ...".')
    else:
        rep.ok("description", f"{len(desc)} chars")

    # -- 4. sections ---------------------------------------------------------
    found = [h.strip() for h in _H2.findall(body)]
    lower = [h.lower() for h in found]
    missing = [s for s in spec.SKILL_SECTIONS
               if not any(s.lower() in h for h in lower)]
    if missing:
        level = rep.blocker if len(missing) > 2 else rep.concern
        level("sections", "Missing required headings: " + ", ".join(missing) + ".",
              "Required, in order: " + " | ".join(spec.SKILL_SECTIONS))
    else:
        rep.ok("sections", f"{len(found)} headings")

    # -- 5. context budget ---------------------------------------------------
    tokens = estimate_tokens(text)
    if tokens > spec.SKILL_BODY_TOKEN_LIMIT:
        rep.blocker("context budget",
                    f"SKILL.md is about {tokens:,} tokens, over "
                    f"{spec.SKILL_BODY_TOKEN_LIMIT:,}.",
                    "Move the long parts into references/ and link them, so they load "
                    "only when needed.")
    else:
        rep.ok("context budget", f"~{tokens:,} tokens")

    # -- 6. paths, secrets, undeclared hosts ---------------------------------
    declared = {str(h).lower() for h in (meta.get("network") or [])}
    bad_paths: list[str] = []
    secrets: list[str] = []
    hosts: set[str] = set()
    for f in _text_files(d):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = f.relative_to(d).as_posix()
        if _ABS_PATH.search(content):
            bad_paths.append(rel)
        if _SECRET.search(content):
            secrets.append(rel)
        hosts.update(h.lower() for h in _URL_HOST.findall(content))

    if secrets:
        rep.blocker("paths & secrets",
                    "Something that looks like a credential appears in "
                    + ", ".join(sorted(secrets)[:3]) + ".",
                    "Read secrets from the environment. The registry is public.")
    elif bad_paths:
        rep.concern("paths & secrets",
                    "Absolute paths in " + ", ".join(sorted(bad_paths)[:3])
                    + " will not resolve on another machine.",
                    "Use {skill_dir} or a path relative to the skill folder.")
    else:
        rep.ok("paths & secrets")

    undeclared = sorted(h for h in hosts
                        if h not in declared
                        and not h.startswith(("localhost", "127.0.0.1", "example."))
                        and h not in {"github.com", "www.github.com", "doi.org",
                                      "creativecommons.org", "agentskills.io",
                                      "www.apache.org", "opensource.org"})
    if "network" not in meta:
        rep.concern("network", "`metadata.network` is not declared.",
                    "List every host the skill contacts, or [] if it runs offline. "
                    "Undeclared hosts are blocked when the benchmark runs.")
    elif undeclared:
        rep.concern("network",
                    "These hosts appear in the code but are not declared: "
                    + ", ".join(undeclared[:4]) + ".",
                    "Add them to `metadata.network`, or drop the call.")
    else:
        rep.ok("network", ", ".join(sorted(declared)) if declared else "offline")

    # -- 7. size -------------------------------------------------------------
    total = sum(f.stat().st_size for f in _all_files(d))
    if total > spec.SKILL_MAX_BYTES:
        rep.blocker("size", f"{total / 1e6:.1f} MB, over the 25 MB limit.",
                    "Bulk data belongs behind a declared host, or in a task's inputs.")
    else:
        rep.ok("size", f"{total / 1e6:.2f} MB")

    # -- 8. tests ------------------------------------------------------------
    tests = d / "tests"
    test_files = sorted(tests.glob("test_*.py")) if tests.is_dir() else []
    if not test_files:
        rep.blocker("tests", "No tests/test_*.py. A skill nobody can run is not a skill.",
                    "Add one test that exercises the main entry point end to end.")
    elif not run_tests:
        rep.ok("tests", f"{len(test_files)} file(s), not run")
    else:
        first = _run_tests(d)
        if first is None:
            rep.concern("tests", "pytest is not installed here, so the tests did not run.",
                        "pip install pytest, then run `buildrix skill check` again.")
        elif first[0] != 0:
            rep.blocker("tests", "The tests fail.", first[1].strip()[-400:])
        elif check_determinism and str(meta.get("determinism")) == "deterministic":
            second = _run_tests(d)
            if second and second[0] == 0 and _normalise(first[1]) != _normalise(second[1]):
                rep.blocker("determinism",
                            "Two runs of the tests produced different output, but the "
                            "skill declares itself deterministic.",
                            "Either seed the randomness, or set "
                            "`metadata.determinism: seeded` (or stochastic).")
            else:
                rep.ok("determinism", "two runs identical")
            rep.ok("tests", f"{len(test_files)} file(s) pass")
        else:
            rep.ok("tests", f"{len(test_files)} file(s) pass")

    return rep


# -- helpers -----------------------------------------------------------------

def _all_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and not any(part in _SKIP_DIRS for part in p.parts):
            yield p


def _text_files(root: Path):
    for p in _all_files(root):
        if p.suffix.lower() in _TEXT_SUFFIXES and p.stat().st_size < 2_000_000:
            yield p


def _run_tests(d: Path) -> tuple[int, str] | None:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests"],
            cwd=d, capture_output=True, text=True, timeout=600,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    out = (proc.stdout or "") + (proc.stderr or "")
    if "No module named pytest" in out:
        return None
    return proc.returncode, out


def _normalise(out: str) -> str:
    """Drop timings and paths so a determinism diff is about the results."""
    out = re.sub(r"\d+\.\d+s", "", out)
    out = re.sub(r"in \d+\.\d+", "in", out)
    out = re.sub(r"0x[0-9a-f]+", "", out)
    return "\n".join(line.rstrip() for line in out.splitlines() if line.strip())
