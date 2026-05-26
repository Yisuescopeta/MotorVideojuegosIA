"""Helpers to resolve external export toolchains against the active Python."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from typing import Any


def resolve_pyinstaller() -> dict[str, Any]:
    """Resolve PyInstaller preferring the active Python module over PATH.

    Returns a dict suitable for diagnostics and exporters. When the module is
    importable in the current interpreter, callers should execute it via
    ``sys.executable -m PyInstaller`` even if no standalone launcher exists.
    """

    pyinstaller_path = shutil.which("pyinstaller") or shutil.which("pyinstaller.exe")
    module_available = importlib.util.find_spec("PyInstaller") is not None

    if module_available:
        command = [sys.executable, "-m", "PyInstaller"]
        resolution = "python_module"
    elif pyinstaller_path:
        command = [pyinstaller_path]
        resolution = "path_executable"
    else:
        command = []
        resolution = "missing"

    return {
        "pyinstaller_available": bool(module_available or pyinstaller_path),
        "pyinstaller_path": pyinstaller_path or "",
        "pyinstaller_module_available": module_available,
        "pyinstaller_resolution": resolution,
        "pyinstaller_command": command,
        "python_executable": sys.executable,
    }
