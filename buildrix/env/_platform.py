"""Platform detection helpers."""

import platform
import struct

SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_MAC = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"

ARCH = platform.machine().lower()
IS_ARM = ARCH in ("arm64", "aarch64")
IS_64BIT = struct.calcsize("P") * 8 == 64

if IS_WINDOWS:
    PLATFORM_KEY = "windows"
elif IS_MAC:
    PLATFORM_KEY = "mac_arm" if IS_ARM else "mac"
else:
    PLATFORM_KEY = "linux_arm" if IS_ARM else "linux"

PATH_SEP = ";" if IS_WINDOWS else ":"
EXE_SUFFIX = ".exe" if IS_WINDOWS else ""
