"""
Managed toolchain — download, extract, and resolve pinned tool versions.

Everything lives under ~/.buildrix/toolchain/<tool>/<version>/.
No system-level installs, no admin privileges, no version conflicts.
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


# ── Tool manifest ──────────────────────────────────────────────────────
# Update URLs here when new versions ship.

TOOL_MANIFEST = {
    "energyplus": {
        "24.1.0": {
            "urls": {
                "linux":   "https://github.com/NREL/EnergyPlus/releases/download/v24.1.0/EnergyPlus-24.1.0-9d7789a3f2-Linux-Ubuntu22.04-x86_64.tar.gz",
                "windows": "https://github.com/NREL/EnergyPlus/releases/download/v24.1.0/EnergyPlus-24.1.0-9d7789a3f2-Windows-x86_64.zip",
                "mac":     "https://github.com/NREL/EnergyPlus/releases/download/v24.1.0/EnergyPlus-24.1.0-9d7789a3f2-macOS-x86_64.tar.gz",
                "mac_arm": "https://github.com/NREL/EnergyPlus/releases/download/v24.1.0/EnergyPlus-24.1.0-9d7789a3f2-macOS-arm64.tar.gz",
            },
            "bin": {
                "linux":   "energyplus",
                "windows": "energyplus.exe",
                "mac":     "energyplus",
                "mac_arm": "energyplus",
            },
            "idd": "Energy+.idd",
        },
        "22.1.0": {
            "urls": {
                "linux":   "https://github.com/NREL/EnergyPlus/releases/download/v22.1.0/EnergyPlus-22.1.0-ed759b17ee-Linux-Ubuntu22.04-x86_64.tar.gz",
                "windows": "https://github.com/NREL/EnergyPlus/releases/download/v22.1.0/EnergyPlus-22.1.0-ed759b17ee-Windows-x86_64.zip",
                "mac":     "https://github.com/NREL/EnergyPlus/releases/download/v22.1.0/EnergyPlus-22.1.0-ed759b17ee-macOS-x86_64.tar.gz",
            },
            "bin": {
                "linux":   "energyplus",
                "windows": "energyplus.exe",
                "mac":     "energyplus",
            },
            "idd": "Energy+.idd",
        },
    },
    "openstudio": {
        "3.9.0": {
            "urls": {
                "linux":   "https://github.com/NREL/OpenStudio/releases/download/v3.9.0/OpenStudio-3.9.0+e3cb53c973-Ubuntu-22.04-x86_64.tar.gz",
                "windows": "https://github.com/NREL/OpenStudio/releases/download/v3.9.0/OpenStudio-3.9.0+e3cb53c973-Windows.zip",
                "mac":     "https://github.com/NREL/OpenStudio/releases/download/v3.9.0/OpenStudio-3.9.0+e3cb53c973-Darwin-x86_64.tar.gz",
                "mac_arm": "https://github.com/NREL/OpenStudio/releases/download/v3.9.0/OpenStudio-3.9.0+e3cb53c973-Darwin-arm64.tar.gz",
            },
            "bin": {
                "linux":   "bin/openstudio",
                "windows": "bin/openstudio.exe",
                "mac":     "bin/openstudio",
                "mac_arm": "bin/openstudio",
            },
        },
    },
    "resstock": {
        "v3.3.0": {
            "type": "git",
            "repo": "https://github.com/NREL/resstock.git",
            "tag": "v3.3.0",
        },
    },
}

DEFAULTS = {
    "energyplus": "24.1.0",
    "openstudio": "3.9.0",
    "resstock":   "v3.3.0",
}


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

    Downloads exact pinned versions into ~/.buildrix/toolchain/.

        tc = Toolchain()
        tc.ensure("energyplus", "24.1.0")
        ep = tc.bin("energyplus")
    """

    def __init__(self, toolchain_dir: Optional[Path] = None):
        self.root = Path(toolchain_dir) if toolchain_dir else TOOLCHAIN_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        DOWNLOAD_CACHE.mkdir(parents=True, exist_ok=True)
        self._installed: dict[str, str] = {}
        self._scan_installed()

    # ── Public API ─────────────────────────────────────────────────

    @classmethod
    def from_skill_config(cls, config_path: str) -> "Toolchain":
        """
        Create a Toolchain and ensure all tools declared in a skill's
        config.yaml are installed.

            tc = Toolchain.from_skill_config("path/to/config.yaml")
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Skill config not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        tc = cls()
        toolchain_spec = config.get("environment", {}).get("toolchain", {})
        for tool, version in toolchain_spec.items():
            tc.ensure(tool, str(version))

        return tc

    def ensure(self, tool: str, version: str = "") -> Path:
        """
        Ensure a tool is installed at the specified version.
        Downloads and extracts if not already present.
        Returns the tool's installation directory.
        """
        version = version or DEFAULTS.get(tool, "")
        if not version:
            raise ValueError(f"No version specified for '{tool}' and no default.")

        install_dir = self.root / tool / version

        if self._is_installed(tool, version):
            self._installed[tool] = version
            return install_dir

        manifest = self._get_manifest(tool, version)

        if manifest.get("type") == "git":
            self._install_git(tool, version, manifest, install_dir)
        else:
            self._install_archive(tool, version, manifest, install_dir)

        self._installed[tool] = version
        print(f"  [toolchain] {tool} {version} ready at {install_dir}")
        return install_dir

    def bin(self, tool: str, version: str = "") -> str:
        """Return full path to a tool's binary."""
        version = version or self._installed.get(tool) or DEFAULTS.get(tool, "")
        install_dir = self.ensure(tool, version)

        manifest = self._get_manifest(tool, version)
        bin_rel = manifest.get("bin", {}).get(PLATFORM_KEY)
        if not bin_rel:
            raise RuntimeError(
                f"No binary defined for {tool} {version} on {PLATFORM_KEY}"
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
        """Return path to Energy+.idd from the managed EnergyPlus install."""
        version = version or self._installed.get("energyplus") or DEFAULTS["energyplus"]
        install_dir = self.ensure("energyplus", version)

        manifest = self._get_manifest("energyplus", version)
        idd_name = manifest.get("idd", "Energy+.idd")

        for candidate in install_dir.rglob(idd_name):
            return str(candidate)

        raise FileNotFoundError(f"Energy+.idd not found in {install_dir}")

    def resstock_dir(self, version: str = "") -> Path:
        """Return path to ResStock repo."""
        version = version or self._installed.get("resstock") or DEFAULTS["resstock"]
        return self.ensure("resstock", version)

    def env(self) -> dict:
        """Return os.environ copy with toolchain bin dirs on PATH."""
        env = os.environ.copy()
        extra_dirs = []

        for tool in ("energyplus", "openstudio"):
            version = self._installed.get(tool)
            if version:
                try:
                    bin_path = self.bin(tool, version)
                    extra_dirs.append(str(Path(bin_path).parent))
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
                    bin_path = self.bin(tool)
                    setattr(result, f"{tool}_bin", bin_path)
                    setattr(result, f"{tool}_dir", str(Path(bin_path).parent))
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
        """Check if Docker daemon is running (optional)."""
        try:
            r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def ensure_weather_dir() -> Path:
        """Create shared weather cache directory."""
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

    def _get_manifest(self, tool: str, version: str) -> dict:
        tool_versions = TOOL_MANIFEST.get(tool)
        if not tool_versions:
            raise ValueError(f"Unknown tool '{tool}'. Available: {list(TOOL_MANIFEST)}")
        entry = tool_versions.get(version)
        if not entry:
            raise ValueError(
                f"Unknown version '{version}' for {tool}. "
                f"Available: {list(tool_versions)}"
            )
        return entry

    def _install_archive(self, tool: str, version: str, manifest: dict,
                         install_dir: Path):
        url = manifest["urls"].get(PLATFORM_KEY)
        if not url:
            raise RuntimeError(
                f"No download for {tool} {version} on {PLATFORM_KEY}. "
                f"Available: {list(manifest['urls'])}"
            )

        print(f"  [toolchain] Downloading {tool} {version} for {PLATFORM_KEY}...")
        archive_path = self._download(url)

        print(f"  [toolchain] Extracting to {install_dir}...")
        install_dir.mkdir(parents=True, exist_ok=True)
        self._extract(archive_path, install_dir)

    def _install_git(self, tool: str, version: str, manifest: dict,
                     install_dir: Path):
        repo_url = manifest["repo"]
        tag = manifest["tag"]

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

        elif name.endswith(".sh"):
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
