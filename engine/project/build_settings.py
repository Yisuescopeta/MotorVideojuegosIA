from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class BuildTargetPlatform(str, Enum):
    WINDOWS_DESKTOP = "windows_desktop"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_output_name(value: str) -> str:
    normalized = "".join(
        char
        for char in str(value or "").strip()
        if char.isalnum() or char in (" ", "-", "_", ".")
    )
    collapsed = []
    previous_separator = False
    for char in normalized:
        if char.isalnum() or char == ".":
            collapsed.append(char)
            previous_separator = False
            continue
        if not previous_separator:
            collapsed.append("_")
            previous_separator = True
    return "".join(collapsed).strip("._ ") or "game_build"


@dataclass(frozen=True)
class BuildSettings:
    CURRENT_VERSION = 1

    product_name: str
    company_name: str
    startup_scene: str
    scenes_in_build: tuple[str, ...]
    target_platform: BuildTargetPlatform
    development_build: bool
    include_logs: bool
    include_profiler: bool
    output_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.CURRENT_VERSION,
            "product_name": self.product_name,
            "company_name": self.company_name,
            "startup_scene": self.startup_scene,
            "scenes_in_build": list(self.scenes_in_build),
            "target_platform": self.target_platform.value,
            "development_build": self.development_build,
            "include_logs": self.include_logs,
            "include_profiler": self.include_profiler,
            "output_name": self.output_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildSettings":
        if not isinstance(data, dict):
            raise ValueError("Build settings must be a JSON object")
        try:
            target_platform = BuildTargetPlatform(str(data.get("target_platform", "")).strip())
        except ValueError as exc:
            raise ValueError("Unsupported build target platform") from exc
        scenes = data.get("scenes_in_build", [])
        if not isinstance(scenes, list):
            raise ValueError("Build settings scenes_in_build must be a list")
        return cls(
            product_name=str(data.get("product_name", "")).strip(),
            company_name=str(data.get("company_name", "")).strip(),
            startup_scene=str(data.get("startup_scene", "")).strip(),
            scenes_in_build=tuple(str(item).strip() for item in scenes),
            target_platform=target_platform,
            development_build=bool(data.get("development_build", False)),
            include_logs=bool(data.get("include_logs", False)),
            include_profiler=bool(data.get("include_profiler", False)),
            output_name=str(data.get("output_name", "")).strip(),
        )


@dataclass(frozen=True)
class BuildOutputMetadata:
    output_root: str
    executable_name: str
    executable_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_root": self.output_root,
            "executable_name": self.executable_name,
            "executable_path": self.executable_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildOutputMetadata":
        if not isinstance(data, dict):
            raise ValueError("Build output metadata must be a JSON object")
        return cls(
            output_root=str(data.get("output_root", "")).strip(),
            executable_name=str(data.get("executable_name", "")).strip(),
            executable_path=str(data.get("executable_path", "")).strip(),
        )


@dataclass(frozen=True)
class BuildArtifactReferences:
    content_bundle: str
    asset_build_report: str
    bundle_report: str
    player_build_report: str
    build_log: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_bundle": self.content_bundle,
            "asset_build_report": self.asset_build_report,
            "bundle_report": self.bundle_report,
            "player_build_report": self.player_build_report,
            "build_log": self.build_log,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildArtifactReferences":
        if not isinstance(data, dict):
            raise ValueError("Build artifact references must be a JSON object")
        return cls(
            content_bundle=str(data.get("content_bundle", "")).strip(),
            asset_build_report=str(data.get("asset_build_report", "")).strip(),
            bundle_report=str(data.get("bundle_report", "")).strip(),
            player_build_report=str(data.get("player_build_report", "")).strip(),
            build_log=str(data.get("build_log", "")).strip(),
        )


@dataclass(frozen=True)
class BuildManifest:
    SCHEMA_NAME = "motorvideojuegosia.build_manifest"
    SCHEMA_VERSION = 1
    FILE_NAME = "build_manifest.json"

    schema: str
    schema_version: int
    generated_at_utc: str
    product_name: str
    company_name: str
    target_platform: BuildTargetPlatform
    startup_scene: str
    scenes_in_build: tuple[str, ...]
    development_build: bool
    include_logs: bool
    include_profiler: bool
    output: BuildOutputMetadata
    artifacts: BuildArtifactReferences

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "generated_at_utc": self.generated_at_utc,
            "product_name": self.product_name,
            "company_name": self.company_name,
            "target_platform": self.target_platform.value,
            "startup_scene": self.startup_scene,
            "scenes_in_build": list(self.scenes_in_build),
            "development": {
                "development_build": self.development_build,
                "include_logs": self.include_logs,
                "include_profiler": self.include_profiler,
            },
            "output": self.output.to_dict(),
            "artifacts": self.artifacts.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildManifest":
        if not isinstance(data, dict):
            raise ValueError("Build manifest must be a JSON object")
        schema = str(data.get("schema", "")).strip()
        if schema != cls.SCHEMA_NAME:
            raise ValueError("Unsupported build manifest schema")
        try:
            schema_version = int(data.get("schema_version", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("Build manifest schema_version must be an integer") from exc
        if schema_version != cls.SCHEMA_VERSION:
            raise ValueError("Unsupported build manifest schema_version")
        try:
            target_platform = BuildTargetPlatform(str(data.get("target_platform", "")).strip())
        except ValueError as exc:
            raise ValueError("Unsupported build manifest target platform") from exc
        scenes = data.get("scenes_in_build", [])
        if not isinstance(scenes, list):
            raise ValueError("Build manifest scenes_in_build must be a list")
        development = data.get("development", {})
        if not isinstance(development, dict):
            raise ValueError("Build manifest development section must be an object")
        return cls(
            schema=schema,
            schema_version=schema_version,
            generated_at_utc=str(data.get("generated_at_utc", "")).strip(),
            product_name=str(data.get("product_name", "")).strip(),
            company_name=str(data.get("company_name", "")).strip(),
            target_platform=target_platform,
            startup_scene=str(data.get("startup_scene", "")).strip(),
            scenes_in_build=tuple(str(item).strip() for item in scenes),
            development_build=bool(development.get("development_build", False)),
            include_logs=bool(development.get("include_logs", False)),
            include_profiler=bool(development.get("include_profiler", False)),
            output=BuildOutputMetadata.from_dict(dict(data.get("output", {}))),
            artifacts=BuildArtifactReferences.from_dict(dict(data.get("artifacts", {}))),
        )


def build_output_root_relative(settings: BuildSettings, build_root_relative: str) -> str:
    build_root = Path(build_root_relative)
    return (build_root / settings.target_platform.value / settings.output_name).as_posix()


def build_manifest_path_relative(settings: BuildSettings, build_root_relative: str) -> str:
    return (Path(build_output_root_relative(settings, build_root_relative)) / BuildManifest.FILE_NAME).as_posix()


def build_manifest_from_settings(
    settings: BuildSettings,
    build_root_relative: str,
    *,
    generated_at_utc: str | None = None,
) -> BuildManifest:
    build_root = Path(build_root_relative)
    target_root = Path(build_output_root_relative(settings, build_root_relative))
    executable_name = f"{settings.output_name}.exe"
    executable_path = (target_root / executable_name).as_posix()
    artifacts = BuildArtifactReferences(
        content_bundle=(build_root / "content_bundle.json").as_posix(),
        asset_build_report=(build_root / "asset_build_report.json").as_posix(),
        bundle_report=(build_root / "bundle_report.json").as_posix(),
        player_build_report=(target_root / "player_build_report.json").as_posix(),
        build_log=(target_root / "build.log").as_posix(),
    )
    output = BuildOutputMetadata(
        output_root=target_root.as_posix(),
        executable_name=executable_name,
        executable_path=executable_path,
    )
    return BuildManifest(
        schema=BuildManifest.SCHEMA_NAME,
        schema_version=BuildManifest.SCHEMA_VERSION,
        generated_at_utc=generated_at_utc or utc_now_iso(),
        product_name=settings.product_name,
        company_name=settings.company_name,
        target_platform=settings.target_platform,
        startup_scene=settings.startup_scene,
        scenes_in_build=settings.scenes_in_build,
        development_build=settings.development_build,
        include_logs=settings.include_logs,
        include_profiler=settings.include_profiler,
        output=output,
        artifacts=artifacts,
    )
