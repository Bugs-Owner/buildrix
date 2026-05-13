"""
Managed toolchain — download, extract, and resolve pinned tool versions.

Everything lives under ~/.buildrix/toolchain/<tool>/<version>/.
No system-level installs, no admin privileges, no version conflicts.

Skills declare their full tool specs (URLs, binary paths) in config.yaml.
The toolchain just downloads, extracts, and resolves paths — no hardcoded
URLs or versions.
"""

import os
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import yaml

from buildrix.env._platform import (
    PLATFORM_KEY, IS_WINDOWS, PATH_SEP,
)


# ── Paths ──────────────────────────────────────────────────────────────
BUILDRIX_HOME = Path.home() / ".buildrix"
TOOLCHAIN_DIR = BUILDRIX_HOME / "toolchain"
DATA_DIR = BUILDRIX_HOME / "data"
WEATHER_DIR = DATA_DIR / "resstock" / "weather" / "tmy3"
DOWNLOAD_CACHE = BUILDRIX_HOME / "cache" / "downloads"


# ── Result container ───────────────────────────────────────────────────
@dataclass
class ToolchainInfo:
    """Snapshot of resolved tool paths."""
    energyplus_bin: Optional[str] = None
    energyplus_dir: Optional[str] = None
    openstudio_bin: Optional[str] = None
    openstudio_dir: Optional[str] = None
    resstock_dir: Optional[str] = None
    idd_path: Optional[str] = None
    weather_dir: str = str(WEATHER_DIR)
    versions: dict = field(default_factory=dict)


# ── Main class ─────────────────────────────────────────────────────────
class Toolchain:
    """
    Managed toolchain for Buildrix skills.

    Skills provide full tool specs in their config.yaml:

        environment:
          toolchain:
            energyplus:
              version: "24.1.0"
              urls:
                linux: "https://github.com/..."
                windows: "https://github.com/..."
              bin:
                linux: "energyplus"
                windows: "energyplus.exe"

    Usage:
        tc = Toolchain.from_skill_config("config.yaml")
        ep = tc.bin("energyplus")
    """

    def __init__(self, toolchain_dir: Optional[Path] = None):
        self.root = Path(toolchain_dir) if toolchain_dir else TOOLCHAIN_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        DOWNLOAD_CACHE.mkdir(parents=True, exist_ok=True)
        self._installed: dict[str, str] = {}       # tool -> version
        self._specs: dict[str, dict] = {}           # tool -> full spec
        self._scan_installed()

    # ── Public API ─────────────────────────────────────────────────

    @classmethod
    def from_skill_config(cls, config_path: str) -> "Toolchain":
        """
        Create a Toolchain from a skill's config.yaml.
        Reads full tool specs and ensures everything is installed.
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Skill config not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        tc = cls()
        toolchain_section = config.get("environment", {}).get("toolchain", {})

        for tool_name, spec in toolchain_section.items():
            if isinstance(spec, dict):
                # Full spec with URLs — the correct way
                tc.ensure(tool_name, spec=spec)
            elif isinstance(spec, str):
                # Bare version string (legacy/simple skills)
                tc.ensure(tool_name, version=spec)

        return tc

    def ensure(self, tool: str, version: str = "",
               spec: Optional[dict] = None) -> Path:
        """
        Ensure a tool is installed.

        Parameters
        ----------
        tool : str
            Tool name (e.g., "energyplus").
        version : str
            Version string (used when spec not provided).
        spec : dict, optional
            Full tool spec from config.yaml with version, urls, bin, etc.
        """
        if spec:
            version = str(spec.get("version", version))
            self._specs[tool] = spec

        if not version:
            # Check if already installed (from a previous ensure call)
            version = self._installed.get(tool, "")
        if not version:
            raise ValueError(
                f"No version or spec for '{tool}'. "
                f"Declare it in the skill's config.yaml."
            )

        install_dir = self.root / tool / version

        if self._is_installed(tool, version):
            self._installed[tool] = version
            return install_dir

        resolved_spec = spec or self._specs.get(tool, {})
        if not resolved_spec:
            raise ValueError(
                f"No spec for '{tool}' v{version}. "
                f"The skill's config.yaml must include urls and bin paths "
                f"under environment.toolchain.{tool}."
            )

        if resolved_spec.get("type") == "git":
            self._install_git(tool, version, resolved_spec, install_dir)
        else:
            self._install_archive(tool, version, resolved_spec, install_dir)

        self._installed[tool] = version
        print(f"  [toolchain] {tool} {version} ready at {install_dir}")
        return install_dir

    def bin(self, tool: str, version: str = "") -> str:
        """Return full path to a tool's binary."""
        version = version or self._installed.get(tool, "")
        if not version:
            raise RuntimeError(f"Tool '{tool}' not installed.")

        install_dir = self.root / tool / version
        spec = self._specs.get(tool, {})
        bin_map = spec.get("bin", {})
        bin_rel = bin_map.get(PLATFORM_KEY)

        if not bin_rel:
            # Auto-detect: search for tool name as executable
            exe = f"{tool}.exe" if IS_WINDOWS else tool
            candidates = list(install_dir.rglob(exe))
            if candidates:
                c = candidates[0]
                if not IS_WINDOWS:
                    c.chmod(c.stat().st_mode | 0o755)
                return str(c)
            raise FileNotFoundError(
                f"No binary mapping for {tool} on {PLATFORM_KEY}. "
                f"Add 'bin.{PLATFORM_KEY}' to config.yaml."
            )

        candidates = [
            install_dir / bin_rel,
            *install_dir.glob(f"*/{bin_rel}"),
            *install_dir.glob(f"**/{Path(bin_rel).name}"),
        ]
        for c in candidates:
            if c.exists():
                if not IS_WINDOWS:
                    c.chmod(c.stat().st_mode | 0o755)
                return str(c)

        raise FileNotFoundError(
            f"Binary '{bin_rel}' not found in {install_dir}. "
            f"Contents: {[p.name for p in install_dir.iterdir()]}"
        )

    def idd(self, version: str = "") -> str:
        """Return path to Energy+.idd."""
        version = version or self._installed.get("energyplus", "")
        if not version:
            raise RuntimeError("EnergyPlus not installed.")

        install_dir = self.root / "energyplus" / version
        spec = self._specs.get("energyplus", {})
        idd_name = spec.get("idd", "Energy+.idd")

        for candidate in install_dir.rglob(idd_name):
            return str(candidate)

        raise FileNotFoundError(f"Energy+.idd not found in {install_dir}")

    def resstock_dir(self, version: str = "") -> Path:
        """Return path to ResStock repo."""
        version = version or self._installed.get("resstock", "")
        if not version:
            raise RuntimeError("ResStock not installed.")
        return self.root / "resstock" / version

    def env(self) -> dict:
        """Return os.environ copy with toolchain bin dirs on PATH."""
        env = os.environ.copy()
        extra_dirs = []
        for tool in ("energyplus", "openstudio"):
            if tool in self._installed:
                try:
                    extra_dirs.append(str(Path(self.bin(tool)).parent))
                except (FileNotFoundError, RuntimeError):
                    pass
        if extra_dirs:
            existing = env.get("PATH", "")
            env["PATH"] = PATH_SEP.join(extra_dirs + [existing])
        return env

    def info(self) -> ToolchainInfo:
        """Return a snapshot of all resolved paths."""
        result = ToolchainInfo(versions=dict(self._installed))
        result.weather_dir = str(WEATHER_DIR)
        for tool in ("energyplus", "openstudio"):
            if tool in self._installed:
                try:
                    bp = self.bin(tool)
                    setattr(result, f"{tool}_bin", bp)
                    setattr(result, f"{tool}_dir", str(Path(bp).parent))
                except (FileNotFoundError, RuntimeError):
                    pass
        if "energyplus" in self._installed:
            try:
                result.idd_path = self.idd()
            except FileNotFoundError:
                pass
        if "resstock" in self._installed:
            result.resstock_dir = str(self.resstock_dir())
        return result

    @staticmethod
    def docker_available() -> bool:
        try:
            r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def ensure_weather_dir() -> Path:
        WEATHER_DIR.mkdir(parents=True, exist_ok=True)
        return WEATHER_DIR

    # ── Internal ───────────────────────────────────────────────────

    def _scan_installed(self):
        if not self.root.exists():
            return
        for tool_dir in self.root.iterdir():
            if not tool_dir.is_dir() or tool_dir.name.startswith("."):
                continue
            for ver_dir in tool_dir.iterdir():
                if ver_dir.is_dir() and not ver_dir.name.startswith("."):
                    self._installed[tool_dir.name] = ver_dir.name

    def _is_installed(self, tool: str, version: str) -> bool:
        install_dir = self.root / tool / version
        if not install_dir.exists():
            return False
        try:
            next(install_dir.iterdir())
            return True
        except StopIteration:
            return False

    def _install_archive(self, tool, version, spec, install_dir):
        urls = spec.get("urls", {})
        url = urls.get(PLATFORM_KEY)
        if not url:
            raise RuntimeError(
                f"No download URL for {tool} {version} on {PLATFORM_KEY}.\n"
                f"Available platforms: {list(urls)}\n"
                f"Add '{PLATFORM_KEY}' to environment.toolchain.{tool}.urls "
                f"in the skill's config.yaml."
            )
        print(f"  [toolchain] Downloading {tool} {version} for {PLATFORM_KEY}...")
        archive_path = self._download(url)
        print(f"  [toolchain] Extracting to {install_dir}...")
        install_dir.mkdir(parents=True, exist_ok=True)
        self._extract(archive_path, install_dir)

    def _install_git(self, tool, version, spec, install_dir):
        repo_url = spec.get("repo")
        tag = spec.get("tag", version)
        if not repo_url:
            raise ValueError(f"Git tool '{tool}' needs 'repo' in config.yaml.")
        print(f"  [toolchain] Cloning {tool} {tag}...")
        install_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", tag,
             repo_url, str(install_dir)],
            check=True, capture_output=True, text=True, timeout=300,
        )

    def _download(self, url: str) -> Path:
        filename = url.rsplit("/", 1)[-1]
        cache_path = DOWNLOAD_CACHE / filename
        if cache_path.exists() and cache_path.stat().st_size > 0:
            print(f"  [toolchain] Using cached {filename}")
            return cache_path
        for cmd in [
            ["wget", "-q", "--show-progress", "-O", str(cache_path), url],
            ["curl", "-fSL", "-o", str(cache_path), url],
        ]:
            try:
                subprocess.run(cmd, check=True, timeout=600)
                if cache_path.exists() and cache_path.stat().st_size > 0:
                    return cache_path
            except (FileNotFoundError, subprocess.CalledProcessError,
                    subprocess.TimeoutExpired):
                continue
        try:
            import requests
            resp = requests.get(url, stream=True, timeout=600)
            resp.raise_for_status()
            with open(cache_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return cache_path
        except Exception as e:
            cache_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Failed to download {url}: {e}\n"
                f"Manual download: place file at {cache_path}"
            ) from e

    @staticmethod
    def _extract(archive_path: Path, dest: Path):
        name = archive_path.name.lower()
        if name.endswith(".tar.gz") or name.endswith(".tgz"):
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(dest, filter="data")
        elif name.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(dest)
        elif name.endswith(".sh") or name.endswith(".run"):
            subprocess.run(
                ["bash", str(archive_path),
                 f"--prefix={dest}", "--skip-license"],
                check=True, capture_output=True, timeout=120,
            )
        else:
            raise RuntimeError(f"Unknown archive format: {archive_path.name}")

        # Flatten single wrapper directory
        contents = list(dest.iterdir())
        if (len(contents) == 1 and contents[0].is_dir()
                and contents[0].name != ".git"):
            wrapper = contents[0]
            tmp = dest.parent / f".{dest.name}_unwrap"
            wrapper.rename(tmp)
            for item in tmp.iterdir():
                item.rename(dest / item.name)
            tmp.rmdir()
