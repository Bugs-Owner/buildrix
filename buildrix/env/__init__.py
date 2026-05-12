"""
buildrix.env — Managed toolchain for Buildrix skills.

Downloads and manages exact pinned versions of tools (EnergyPlus,
OpenStudio, ResStock, etc.) into ~/.buildrix/toolchain/.

Skills declare what they need in config.yaml:

    environment:
      toolchain:
        energyplus: "24.1.0"
        openstudio: "3.9.0"

And `buildrix install` provisions everything automatically.
"""

from buildrix.env.toolchain import Toolchain
from buildrix.env.ide_guard import setup_ide_guard

__all__ = ["Toolchain", "setup_ide_guard"]
