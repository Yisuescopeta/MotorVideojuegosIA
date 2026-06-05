"""Read-only Android SDK, Java, and Gradle environment probes."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


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
    build_tools_available = _has_installed_build_tools(
        build_tools_path if sdk_available else None
    )
    java_path = shutil.which("java") or shutil.which("java.exe") or ""
    gradle = resolve_gradle(project_dir)

    return {
        "android_sdk_available": sdk_available,
        "android_home": str(sdk_path) if sdk_path is not None else "",
        "android_platform_available": bool(
            sdk_available and platform_path and platform_path.is_dir()
        ),
        "android_platform_path": str(platform_path) if platform_path is not None else "",
        "android_build_tools_available": build_tools_available,
        "java_available": bool(java_path),
        "java_path": java_path,
        "gradle_available": gradle["available"],
        "gradle_path": gradle["path"],
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


def _has_installed_build_tools(build_tools_path: Path | None) -> bool:
    if build_tools_path is None or not build_tools_path.is_dir():
        return False
    try:
        return any(path.is_dir() for path in build_tools_path.iterdir())
    except OSError:
        return False


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
            return {
                "available": True,
                "path": str(wrapper),
                "command": [str(wrapper)],
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
        return {
            "available": True,
            "path": gradle_path,
            "command": [gradle_path],
            "wrapper_available": complete_wrapper is not None,
            "wrapper_executable": False,
            "wrapper_path": str(complete_wrapper) if complete_wrapper else "",
            "resolution": "path_executable",
        }

    return {
        "available": False,
        "path": "",
        "command": [],
        "wrapper_available": complete_wrapper is not None,
        "wrapper_executable": False,
        "wrapper_path": str(complete_wrapper) if complete_wrapper else "",
        "resolution": "wrapper_not_executable" if complete_wrapper else "missing",
    }


def android_template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "platforms" / "android" / "template"


def is_complete_gradle_wrapper(wrapper: Path) -> bool:
    wrapper_dir = wrapper.parent
    return (
        wrapper.exists()
        and (wrapper_dir / "gradle" / "wrapper" / "gradle-wrapper.properties").exists()
        and (wrapper_dir / "gradle" / "wrapper" / "gradle-wrapper.jar").exists()
    )
