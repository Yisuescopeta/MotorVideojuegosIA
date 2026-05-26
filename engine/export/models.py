"""Core data models for export pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExportPlatform(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"
    IOS = "ios"


class ExportMode(str, Enum):
    DEBUG = "debug"
    RELEASE = "release"


class BundleMode(str, Enum):
    PACKED = "packed"
    DIRECTORY = "directory"


class ExportValidationError:
    def __init__(self, code: str, path: str = "", hint: str = ""):
        self.code = code
        self.path = path
        self.hint = hint

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "hint": self.hint,
        }

    def __repr__(self) -> str:
        return f"ExportValidationError(code={self.code!r}, path={self.path!r})"


@dataclass
class ExportValidationResult:
    valid: bool = True
    errors: list[ExportValidationError] = field(default_factory=list)


@dataclass
class ExportPreset:
    name: str = ""
    platform: str = ""
    architecture: str = "x86_64"
    mode: str = "release"
    output_path: str = ""
    entry_scene: str = ""
    display_name: str = ""
    application_id: str = ""
    version_name: str = "0.1.0"
    version_code: int = 1
    bundle_mode: str = "packed"
    include_debug_tools: bool = False
    window: dict[str, Any] = field(default_factory=dict)
    min_sdk: int = 23
    target_sdk: int = 35
    orientation: str = "landscape"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExportPreset":
        window = dict(data.get("window", {}) or {})
        extra = {k: v for k, v in data.items() if k not in _KNOWN_PRESET_KEYS}
        return cls(
            name=str(data.get("name", "")),
            platform=str(data.get("platform", "")),
            architecture=str(data.get("architecture", "x86_64")),
            mode=str(data.get("mode", "release")),
            output_path=str(data.get("output_path", "")),
            entry_scene=str(data.get("entry_scene", "")),
            display_name=str(data.get("display_name", "")),
            application_id=str(data.get("application_id", "")),
            version_name=str(data.get("version_name", "0.1.0")),
            version_code=int(data.get("version_code", 1)),
            bundle_mode=str(data.get("bundle_mode", "packed")),
            include_debug_tools=bool(data.get("include_debug_tools", False)),
            window=window,
            min_sdk=int(data.get("min_sdk", 23)),
            target_sdk=int(data.get("target_sdk", 35)),
            orientation=str(data.get("orientation", "landscape")),
            extra=extra,
        )

    _SENSITIVE_EXTRA_KEYS = frozenset({
        "keystore_path", "keystore_password", "key_alias", "key_password",
    })

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "platform": self.platform,
            "architecture": self.architecture,
            "mode": self.mode,
            "output_path": self.output_path,
            "entry_scene": self.entry_scene,
            "display_name": self.display_name,
            "application_id": self.application_id,
            "version_name": self.version_name,
            "version_code": self.version_code,
            "bundle_mode": self.bundle_mode,
            "include_debug_tools": self.include_debug_tools,
        }
        if self.window:
            result["window"] = self.window
        if self.platform == "android":
            result["min_sdk"] = self.min_sdk
            result["target_sdk"] = self.target_sdk
            result["orientation"] = self.orientation
        if include_secrets:
            result.update(self.extra)
        else:
            result.update({
                k: v for k, v in self.extra.items()
                if k not in self._SENSITIVE_EXTRA_KEYS
            })
        return result


_KNOWN_PRESET_KEYS = frozenset({
    "name", "platform", "architecture", "mode", "output_path",
    "entry_scene", "display_name", "application_id", "version_name",
    "version_code", "bundle_mode", "include_debug_tools", "window",
    "min_sdk", "target_sdk", "orientation",
})


@dataclass
class PresetsDocument:
    schema_version: int = 1
    presets: list[ExportPreset] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PresetsDocument":
        presets = [ExportPreset.from_dict(p) for p in data.get("presets", [])]
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            presets=presets,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "presets": [p.to_dict() for p in self.presets],
        }


@dataclass
class BuildGraphResult:
    entry_scene: str = ""
    reachable_assets: list[str] = field(default_factory=list)
    reachable_scenes: list[str] = field(default_factory=list)
    reachable_scripts: list[str] = field(default_factory=list)
    missing_assets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dependency_map: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ContentManifestEntry:
    guid: str = ""
    path: str = ""
    kind: str = ""
    sha256: str = ""
    size_bytes: int = 0
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "guid": self.guid,
            "path": self.path,
            "kind": self.kind,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "dependencies": self.dependencies,
        }


@dataclass
class ContentManifest:
    schema_version: int = 1
    entry_scene: str = ""
    generated_at_utc: str = ""
    engine_version: str = ""
    project: dict[str, str] = field(default_factory=dict)
    assets: list[ContentManifestEntry] = field(default_factory=list)
    scenes: list[ContentManifestEntry] = field(default_factory=list)
    scripts: list[ContentManifestEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "entry_scene": self.entry_scene,
            "generated_at_utc": self.generated_at_utc,
            "engine_version": self.engine_version,
            "project": self.project,
            "assets": [a.to_dict() for a in self.assets],
            "scenes": [s.to_dict() for s in self.scenes],
            "scripts": [s.to_dict() for s in self.scripts],
        }
