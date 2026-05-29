"""Export doctor: check toolchain and environment."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from engine.export.toolchain import resolve_pyinstaller

_KEY_TOOLCHAINS = frozenset({"pyinstaller", "pip"})


def run_export_doctor(project_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    issues: list[str] = []
    warnings: list[str] = []

    checks["python_version"] = sys.version
    checks["python_executable"] = sys.executable

    pyinstaller = resolve_pyinstaller()
    checks["pyinstaller_available"] = pyinstaller["pyinstaller_available"]
    checks["pyinstaller_path"] = pyinstaller["pyinstaller_path"]
    checks["pyinstaller_module_available"] = pyinstaller["pyinstaller_module_available"]
    checks["pyinstaller_resolution"] = pyinstaller["pyinstaller_resolution"]
    if not pyinstaller["pyinstaller_available"]:
        issues.append(
            "TOOLCHAIN_UNAVAILABLE: PyInstaller not found. Desktop builds will fail. "
            f"Install with: {sys.executable} -m pip install pyinstaller"
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

    gradle = _resolve_gradle(project_root)
    checks["gradle_available"] = gradle["available"]
    checks["gradle_path"] = gradle["path"]
    checks["gradle_wrapper_available"] = gradle["wrapper_available"]
    checks["gradle_resolution"] = gradle["resolution"]
    checks["gradle_wrapper_path"] = gradle["wrapper_path"]
    if android_home and java_path and not gradle["available"]:
        issues.append(
            "TOOLCHAIN_UNAVAILABLE: Gradle not found and no complete Gradle wrapper "
            "was found in the project or Android template. Install Gradle, add "
            "gradlew/gradlew.bat with gradle-wrapper.jar, or restore "
            "platforms/android/template/gradle/wrapper/gradle-wrapper.jar."
        )

    healthy = len(issues) == 0

    return {
        "healthy": healthy,
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }


def _resolve_gradle(project_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    gradle_path = shutil.which("gradle") or shutil.which("gradle.bat")
    if gradle_path:
        return {
            "available": True,
            "path": gradle_path,
            "wrapper_available": False,
            "wrapper_path": "",
            "resolution": "path_executable",
        }

    wrapper_name = "gradlew.bat" if os.name == "nt" else "gradlew"
    candidates: list[Path] = []
    if project_root is not None:
        candidates.append(Path(project_root) / wrapper_name)
    candidates.append(Path.cwd() / wrapper_name)
    candidates.append(_android_template_dir() / wrapper_name)

    for wrapper in candidates:
        if _is_complete_gradle_wrapper(wrapper):
            return {
                "available": True,
                "path": str(wrapper),
                "wrapper_available": True,
                "wrapper_path": str(wrapper),
                "resolution": (
                    "android_template_wrapper"
                    if wrapper.parent == _android_template_dir()
                    else "project_wrapper"
                ),
            }

    return {
        "available": False,
        "path": "",
        "wrapper_available": False,
        "wrapper_path": "",
        "resolution": "missing",
    }


def _android_template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "platforms" / "android" / "template"


def _is_complete_gradle_wrapper(wrapper: Path) -> bool:
    wrapper_dir = wrapper.parent
    return (
        wrapper.exists()
        and (wrapper_dir / "gradle" / "wrapper" / "gradle-wrapper.properties").exists()
        and (wrapper_dir / "gradle" / "wrapper" / "gradle-wrapper.jar").exists()
    )
