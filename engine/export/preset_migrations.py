"""Versioned migrations for export presets."""

from __future__ import annotations

from typing import Any

LATEST_SCHEMA_VERSION = 1


def migrate_presets(data: dict[str, Any]) -> dict[str, Any]:
    version = int(data.get("schema_version", 0))
    if version < 1:
        data = _migrate_v0_to_v1(data)
    return data


def _migrate_v0_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    data["schema_version"] = 1
    presets = data.get("presets", [])
    for preset in presets:
        if not isinstance(preset, dict):
            continue
        if "bundle_mode" not in preset:
            preset["bundle_mode"] = "packed"
        if "include_debug_tools" not in preset:
            preset["include_debug_tools"] = False
        if "version_name" not in preset:
            preset["version_name"] = "0.1.0"
        if "version_code" not in preset:
            preset["version_code"] = 1
    return data
