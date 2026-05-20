"""Export doctor: check toolchain and environment."""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any

_KEY_TOOLCHAINS = frozenset({"pyinstaller", "pip"})


def run_export_doctor() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    issues: list[str] = []
    warnings: list[str] = []

    checks["python_version"] = sys.version
    checks["python_executable"] = sys.executable

    pyinstaller_path = shutil.which("pyinstaller") or shutil.which("pyinstaller.exe")
    checks["pyinstaller_available"] = pyinstaller_path is not None
    checks["pyinstaller_path"] = pyinstaller_path or ""
    if not pyinstaller_path:
        issues.append(
            "TOOLCHAIN_UNAVAILABLE: PyInstaller not found. Desktop builds will fail. "
            "Install with: pip install pyinstaller"
        )

    try:
        import pip  # noqa: F401
        pip_available = True
    except ImportError:
        pip_available = False
        issues.append("TOOLCHAIN_UNAVAILABLE: pip not available.")
    checks["pip_available"] = pip_available

    checks["os_name"] = os.name
    checks["platform"] = sys.platform

    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    checks["android_sdk"] = bool(android_home)
    checks["android_home"] = android_home or ""
    if not android_home:
        warnings.append(
            "ANDROID_HOME not set. Android exports will fail "
            "with TOOLCHAIN_UNAVAILABLE."
        )

    java_path = shutil.which("java") or shutil.which("java.exe")
    checks["java_available"] = bool(java_path)
    checks["java_path"] = java_path or ""
    if not java_path:
        warnings.append("Java not found. Android exports require JDK.")

    gradle_path = shutil.which("gradle") or shutil.which("gradle.bat")
    checks["gradle_available"] = gradle_path is not None
    checks["gradle_path"] = gradle_path or ""

    healthy = len(issues) == 0

    return {
        "healthy": healthy,
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }
