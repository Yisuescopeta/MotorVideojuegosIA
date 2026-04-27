"""
engine/assets/asset_reference.py - Helpers para referencias de assets.
"""

from __future__ import annotations

from typing import Any, Dict

AssetReference = Dict[str, str]


def normalize_asset_path(path: Any) -> str:
    if path is None:
        return ""
    return str(path).strip().replace("\\", "/")


def build_asset_reference(path: Any = "", guid: Any = "") -> AssetReference:
    return {
        "guid": str(guid or "").strip(),
        "path": normalize_asset_path(path),
    }


def is_asset_reference(value: Any) -> bool:
    return isinstance(value, dict) and ("path" in value or "guid" in value)


def normalize_asset_reference(value: Any) -> AssetReference:
    if is_asset_reference(value):
        return build_asset_reference(value.get("path", ""), value.get("guid", ""))
    if isinstance(value, str):
        return build_asset_reference(path=value)
    return build_asset_reference()


def clone_asset_reference(value: Any) -> AssetReference:
    ref = normalize_asset_reference(value)
    return build_asset_reference(ref.get("path", ""), ref.get("guid", ""))


def reference_has_identity(value: Any) -> bool:
    ref = normalize_asset_reference(value)
    return bool(ref.get("guid") or ref.get("path"))


def get_asset_reference_path(value: Any) -> str:
    return normalize_asset_reference(value).get("path", "")


def get_asset_reference_guid(value: Any) -> str:
    return normalize_asset_reference(value).get("guid", "")
