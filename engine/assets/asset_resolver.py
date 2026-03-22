"""
engine/assets/asset_resolver.py - Resolucion centralizada de referencias de assets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from engine.assets.asset_database import AssetDatabase
from engine.assets.asset_reference import build_asset_reference, normalize_asset_path, normalize_asset_reference


class AssetResolver:
    """Convierte referencias AI-friendly en rutas y referencias canonicas."""

    def __init__(self, project_service: Any, asset_database: Optional[AssetDatabase] = None) -> None:
        self._project_service = project_service
        self._asset_database = asset_database or AssetDatabase(project_service)

    @property
    def database(self) -> AssetDatabase:
        return self._asset_database

    def canonical_reference(self, locator: Any) -> Dict[str, str]:
        return self._asset_database.build_reference(locator)

    def resolve_entry(self, locator: Any) -> Optional[Dict[str, Any]]:
        return self._asset_database.get_asset_entry(locator)

    def resolve_path(self, locator: Any) -> str:
        entry = self.resolve_entry(locator)
        if entry is not None:
            return self._project_service.resolve_path(entry["path"]).as_posix()
        ref = normalize_asset_reference(locator)
        if ref.get("path"):
            return self._project_service.resolve_path(ref["path"]).as_posix()
        return ""

    def resolve_module_name(self, locator: Any) -> str:
        entry = self.resolve_entry(locator)
        if entry is not None and entry.get("path"):
            return self._path_to_module_name(entry["path"])

        ref = normalize_asset_reference(locator)
        if ref.get("path"):
            return self._path_to_module_name(ref["path"])

        if isinstance(locator, str):
            value = normalize_asset_path(locator)
            if value.endswith(".py"):
                return self._path_to_module_name(value)
            return value.strip("/").replace("/", ".")
        return ""

    def build_reference(self, path: str = "", guid: str = "") -> Dict[str, str]:
        return build_asset_reference(path, guid)

    def _path_to_module_name(self, asset_path: str) -> str:
        path = normalize_asset_path(asset_path)
        if path.endswith(".py"):
            rel = Path(path).as_posix()
            if rel.startswith("scripts/"):
                rel = rel[len("scripts/"):]
            return rel[:-3].replace("/", ".")
        return path.strip("/").replace("/", ".")
