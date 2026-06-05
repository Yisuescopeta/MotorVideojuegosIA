"""Export doctor: check toolchain and environment."""

from __future__ import annotations

import os
import sys
from typing import Any

from engine.export.android_environment import probe_android_environment, resolve_gradle
from engine.export.preset_loader import PresetLoadError, load_presets
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

    compile_sdks = _android_compile_sdks(project_root)
    android_required = bool(compile_sdks)
    probe_sdks = compile_sdks or [35]
    android_checks = [
        {
            "compile_sdk": compile_sdk,
            **probe_android_environment(project_root, compile_sdk),
        }
        for compile_sdk in probe_sdks
    ]
    primary_android = android_checks[0]
    checks.update(primary_android)
    checks["android_sdk"] = primary_android["android_sdk_available"]
    checks["android_platforms"] = android_checks if android_required else []

    if android_required and not primary_android["android_sdk_available"]:
        issues.append(
            "TOOLCHAIN_UNAVAILABLE: ANDROID_HOME or ANDROID_SDK_ROOT must point "
            "to an installed Android SDK."
        )
    if android_required and not primary_android["java_available"]:
        issues.append(
            "TOOLCHAIN_UNAVAILABLE: Java not found. Android exports require JDK 17+."
        )
    elif android_required and not primary_android["java_compatible"]:
        issues.append(
            "ANDROID_JDK_INCOMPATIBLE: Android Gradle Plugin 8.6.1 requires "
            "JDK 17 or later. Detected "
            f"{primary_android['java_version'] or 'unknown'}."
        )
    if android_required and not primary_android["android_build_tools_available"]:
        issues.append(
            "ANDROID_BUILD_TOOLS_MISSING: Install Android SDK Build-Tools"
        )
    elif android_required and not primary_android["android_build_tools_compatible"]:
        issues.append(
            "ANDROID_BUILD_TOOLS_INCOMPATIBLE: Android builds require SDK "
            "Build-Tools 34.0.0 or later. Detected "
            f"{primary_android['android_build_tools_version'] or 'unknown'}."
        )
    for android_check in android_checks if android_required else []:
        if not android_check["android_platform_available"]:
            issues.append(
                "ANDROID_PLATFORM_MISSING: Install Android SDK Platform "
                f"{android_check['compile_sdk']}"
            )

    if (
        android_required
        and primary_android["android_sdk_available"]
        and primary_android["java_available"]
        and not primary_android["gradle_available"]
    ):
        if (
            primary_android["gradle_wrapper_available"]
            and not primary_android["gradle_wrapper_executable"]
        ):
            issues.append(
                "GRADLE_WRAPPER_NOT_EXECUTABLE: Run chmod +x gradlew"
            )
        issues.append(
            "TOOLCHAIN_UNAVAILABLE: Gradle not found and no complete Gradle wrapper "
            "was found in the project or Android template. Install Gradle, add "
            "gradlew/gradlew.bat with gradle-wrapper.jar, or restore "
            "platforms/android/template/gradle/wrapper/gradle-wrapper.jar."
        )
    elif android_required and not primary_android["gradle_compatible"]:
        issues.append(
            "ANDROID_GRADLE_INCOMPATIBLE: Android Gradle Plugin 8.6.1 requires "
            "Gradle 8.7 or later. Detected "
            f"{primary_android['gradle_version'] or 'unknown'}."
        )

    healthy = len(issues) == 0

    return {
        "healthy": healthy,
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }


def _android_compile_sdks(
    project_root: str | os.PathLike[str] | None,
) -> list[int]:
    if project_root is None:
        return [35]
    try:
        doc = load_presets(project_root)
    except PresetLoadError:
        return [35]
    compile_sdks = sorted({
        preset.compile_sdk
        for preset in doc.presets
        if preset.platform == "android"
    })
    return compile_sdks


def _resolve_gradle(project_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    return resolve_gradle(project_root)
