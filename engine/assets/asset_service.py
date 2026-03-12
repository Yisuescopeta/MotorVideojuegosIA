"""
engine/assets/asset_service.py - Metadata serializable y slicing de assets.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.project.project_service import ProjectService


class AssetService:
    """Gestiona metadata sidecar, slices y busqueda de assets del proyecto."""

    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service
        self._history: Any = None

    def set_project_service(self, project_service: ProjectService) -> None:
        self._project_service = project_service

    def set_history_manager(self, history: Any) -> None:
        self._history = history

    def list_assets(self, search: str = "", extensions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return self._project_service.list_assets(search=search, extensions=extensions)

    def resolve_asset_path(self, asset_path: str) -> Path:
        return self._project_service.resolve_path(asset_path)

    def get_metadata_path(self, asset_path: str) -> Path:
        return Path(str(self.resolve_asset_path(asset_path)) + ".meta.json")

    def load_metadata(self, asset_path: str) -> Dict[str, Any]:
        metadata_path = self.get_metadata_path(asset_path)
        if not metadata_path.exists():
            return self._default_metadata(asset_path)
        try:
            with metadata_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return self._default_metadata(asset_path)
        data.setdefault("asset_type", "sprite_sheet")
        data.setdefault("source_path", self._project_service.to_relative_path(asset_path))
        data.setdefault("import_mode", "grid")
        data.setdefault("grid", {})
        data.setdefault("slices", [])
        return data

    def save_metadata(self, asset_path: str, metadata: Dict[str, Any], record_history: bool = True) -> Dict[str, Any]:
        before = self.load_metadata(asset_path)
        payload = self._default_metadata(asset_path)
        payload.update(metadata)
        payload["source_path"] = self._project_service.to_relative_path(asset_path)
        metadata_path = self.get_metadata_path(asset_path)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)
        if record_history and self._history is not None:
            after = json.loads(json.dumps(payload))
            self._history.push(
                label=f"Asset metadata: {payload['source_path']}",
                undo=lambda: self.save_metadata(asset_path, before, record_history=False),
                redo=lambda: self.save_metadata(asset_path, after, record_history=False),
            )
        return payload

    def generate_grid_slices(
        self,
        asset_path: str,
        cell_width: int,
        cell_height: int,
        margin: int = 0,
        spacing: int = 0,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        width, height = self.get_image_size(asset_path)
        if width <= 0 or height <= 0 or cell_width <= 0 or cell_height <= 0:
            raise ValueError("Invalid image or cell size for grid slicing")
        slices: List[Dict[str, Any]] = []
        prefix = naming_prefix or Path(asset_path).stem
        index = 0
        y = margin
        while y + cell_height <= height - margin:
            x = margin
            while x + cell_width <= width - margin:
                slices.append(
                    {
                        "name": f"{prefix}_{index}",
                        "x": x,
                        "y": y,
                        "width": cell_width,
                        "height": cell_height,
                        "pivot_x": pivot_x,
                        "pivot_y": pivot_y,
                    }
                )
                index += 1
                x += cell_width + spacing
            y += cell_height + spacing
        metadata = self.load_metadata(asset_path)
        metadata["import_mode"] = "grid"
        metadata["grid"] = {
            "cell_width": cell_width,
            "cell_height": cell_height,
            "margin": margin,
            "spacing": spacing,
            "pivot_x": pivot_x,
            "pivot_y": pivot_y,
            "naming_prefix": prefix,
        }
        metadata["slices"] = slices
        return self.save_metadata(asset_path, metadata)

    def list_slices(self, asset_path: str) -> List[Dict[str, Any]]:
        return list(self.load_metadata(asset_path).get("slices", []))

    def get_slice_rect(self, asset_path: str, slice_name: str) -> Optional[Dict[str, Any]]:
        for slice_info in self.list_slices(asset_path):
            if slice_info.get("name") == slice_name:
                return slice_info
        return None

    def get_image_size(self, asset_path: str) -> tuple[int, int]:
        file_path = self.resolve_asset_path(asset_path)
        if not file_path.exists():
            return (0, 0)
        if file_path.suffix.lower() == ".png":
            with file_path.open("rb") as handle:
                signature = handle.read(24)
            if signature[:8] != b"\x89PNG\r\n\x1a\n":
                return (0, 0)
            width, height = struct.unpack(">II", signature[16:24])
            return (int(width), int(height))
        return (0, 0)

    def _default_metadata(self, asset_path: str) -> Dict[str, Any]:
        return {
            "asset_type": "sprite_sheet",
            "source_path": self._project_service.to_relative_path(asset_path),
            "import_mode": "grid",
            "grid": {},
            "slices": [],
        }
