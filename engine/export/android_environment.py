"""Read-only Android SDK, Java, and Gradle environment probes."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

MIN_JAVA_MAJOR = 17
MIN_GRADLE_VERSION = (8, 7)
MIN_BUILD_TOOLS_VERSION = (34, 0, 0)


def probe_android_environment(
    project_dir: str | os.PathLike[str] | None = None,
    compile_sdk: int = 35,
) -> dict[str, Any]:
    sdk_path = _resolve_android_sdk_path()
    sdk_available = bool(sdk_path and sdk_path.is_dir())
    platform_path = (
        sdk_path / "platforms" / f"android-{compile_sdk}"
        if sdk_path is not None
        else None
    )
    build_tools_path = sdk_path / "build-tools" if sdk_path is not None else None
    build_tools_versions = _installed_build_tools_versions(
        build_tools_path if sdk_available else None
    )
    build_tools_version = (
        ".".join(str(part) for part in build_tools_versions[-1])
        if build_tools_versions
        else ""
    )
    java_path = shutil.which("java") or shutil.which("java.exe") or ""
    java_version, java_major = _probe_java_version(java_path)
    gradle = resolve_gradle(project_dir)

    return {
        "android_sdk_available": sdk_available,
        "android_home": str(sdk_path) if sdk_path is not None else "",
        "android_platform_available": bool(
            sdk_available and platform_path and platform_path.is_dir()
        ),
        "android_platform_path": str(platform_path) if platform_path is not None else "",
        "android_build_tools_available": bool(build_tools_versions),
        "android_build_tools_version": build_tools_version,
        "android_build_tools_compatible": bool(
            build_tools_versions
            and build_tools_versions[-1] >= MIN_BUILD_TOOLS_VERSION
        ),
        "java_available": bool(java_path),
        "java_path": java_path,
        "java_version": java_version,
        "java_major": java_major,
        "java_compatible": bool(java_major and java_major >= MIN_JAVA_MAJOR),
        "gradle_available": gradle["available"],
        "gradle_path": gradle["path"],
        "gradle_version": gradle["version"],
        "gradle_compatible": gradle["compatible"],
        "gradle_wrapper_available": gradle["wrapper_available"],
        "gradle_wrapper_executable": gradle["wrapper_executable"],
        "gradle_wrapper_path": gradle["wrapper_path"],
        "gradle_resolution": gradle["resolution"],
    }


def _resolve_android_sdk_path() -> Path | None:
    configured = [
        value
        for value in (
            os.environ.get("ANDROID_HOME"),
            os.environ.get("ANDROID_SDK_ROOT"),
        )
        if value
    ]
    candidates = [Path(value).expanduser() for value in configured]
    fallback = candidates[0] if candidates else None
    return next((path for path in candidates if path.is_dir()), fallback)


def _installed_build_tools_versions(
    build_tools_path: Path | None,
) -> list[tuple[int, ...]]:
    if build_tools_path is None or not build_tools_path.is_dir():
        return []
    try:
        versions = [
            parsed
            for path in build_tools_path.iterdir()
            if path.is_dir()
            for parsed in [_parse_version(path.name)]
            if parsed
        ]
        return sorted(versions)
    except OSError:
        return []


def _parse_version(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)*)", value)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _probe_java_version(java_path: str) -> tuple[str, int]:
    if not java_path:
        return "", 0
    try:
        result = subprocess.run(
            [java_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "", 0
    output = "\n".join(part for part in (result.stderr, result.stdout) if part)
    match = re.search(r'version\s+"([^"]+)"', output)
    if not match:
        return "", 0
    version = match.group(1)
    parts = _parse_version(version)
    if not parts:
        return version, 0
    major = parts[1] if parts[0] == 1 and len(parts) > 1 else parts[0]
    return version, major


def resolve_gradle(
    project_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    wrapper_name = "gradlew.bat" if os.name == "nt" else "gradlew"
    candidates: list[Path] = []
    if project_dir is not None:
        candidates.append(Path(project_dir) / wrapper_name)
    candidates.append(Path.cwd() / wrapper_name)
    candidates.append(android_template_dir() / wrapper_name)

    complete_wrapper: Path | None = None
    for wrapper in candidates:
        if not is_complete_gradle_wrapper(wrapper):
            continue
        complete_wrapper = wrapper
        executable = os.name == "nt" or os.access(wrapper, os.X_OK)
        if executable:
            version = _wrapper_gradle_version(wrapper)
            return {
                "available": True,
                "path": str(wrapper),
                "command": [str(wrapper)],
                "version": version,
                "compatible": _version_at_least(version, MIN_GRADLE_VERSION),
                "wrapper_available": True,
                "wrapper_executable": True,
                "wrapper_path": str(wrapper),
                "resolution": (
                    "android_template_wrapper"
                    if wrapper.parent == android_template_dir()
                    else "project_wrapper"
                ),
            }
        break

    gradle_path = shutil.which("gradle") or shutil.which("gradle.bat")
    if gradle_path:
        version = _probe_gradle_version(gradle_path)
        return {
            "available": True,
            "path": gradle_path,
            "command": [gradle_path],
            "version": version,
            "compatible": _version_at_least(version, MIN_GRADLE_VERSION),
            "wrapper_available": complete_wrapper is not None,
            "wrapper_executable": False,
            "wrapper_path": str(complete_wrapper) if complete_wrapper else "",
            "resolution": "path_executable",
        }

    return {
        "available": False,
        "path": "",
        "command": [],
        "version": "",
        "compatible": False,
        "wrapper_available": complete_wrapper is not None,
        "wrapper_executable": False,
        "wrapper_path": str(complete_wrapper) if complete_wrapper else "",
        "resolution": "wrapper_not_executable" if complete_wrapper else "missing",
    }


def _wrapper_gradle_version(wrapper: Path) -> str:
    properties = wrapper.parent / "gradle" / "wrapper" / "gradle-wrapper.properties"
    try:
        content = properties.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r"gradle-([0-9][0-9.]*)-(?:bin|all)\.zip", content)
    return match.group(1) if match else ""


def _probe_gradle_version(gradle_path: str) -> str:
    try:
        result = subprocess.run(
            [gradle_path, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    match = re.search(r"^Gradle\s+([0-9][0-9.]*)", output, re.MULTILINE)
    return match.group(1) if match else ""


def _version_at_least(value: str, minimum: tuple[int, ...]) -> bool:
    parsed = _parse_version(value)
    if not parsed:
        return False
    padded = parsed + (0,) * max(0, len(minimum) - len(parsed))
    return padded[:len(minimum)] >= minimum


def android_template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "platforms" / "android" / "template"


def is_complete_gradle_wrapper(wrapper: Path) -> bool:
    wrapper_dir = wrapper.parent
    return (
        wrapper.exists()
        and (wrapper_dir / "gradle" / "wrapper" / "gradle-wrapper.properties").exists()
        and (wrapper_dir / "gradle" / "wrapper" / "gradle-wrapper.jar").exists()
    )
