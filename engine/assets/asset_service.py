"""
engine/assets/asset_service.py - Authoring de assets, metadata y catalogo.
"""

from __future__ import annotations

import json
import shutil
import struct
from collections import Counter, deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyray as rl

from engine.assets.asset_database import AssetDatabase
from engine.assets.asset_reference import build_asset_reference, normalize_asset_reference
from engine.assets.asset_resolver import AssetResolver
from engine.project.project_service import ProjectService
from engine.rendering.materials import Material2D


class AssetService:
    """Gestiona metadata sidecar, slices, catalogo y referencias canonicas."""

    VALID_SLICE_GROUP_MODES = {"row", "name_prefix", "visual_order"}
    VALID_ANIMATION_ORDER_MODES = {"selection", "visual"}

    def __init__(self, project_service: ProjectService) -> None:
        self._history: Any = None
        self._project_service = project_service
        self._database = AssetDatabase(project_service)
        self._resolver = AssetResolver(project_service, self._database)

    def set_project_service(self, project_service: ProjectService) -> None:
        self._project_service = project_service
        self._database = AssetDatabase(project_service)
        self._resolver = AssetResolver(project_service, self._database)

    def set_history_manager(self, history: Any) -> None:
        self._history = history

    def get_asset_database(self) -> AssetDatabase:
        return self._database

    def get_asset_resolver(self) -> AssetResolver:
        return self._resolver

    def refresh_catalog(self) -> Dict[str, Any]:
        return self._database.refresh_catalog()

    def find_assets(
        self,
        search: str = "",
        *,
        asset_kind: str = "",
        importer: str = "",
        extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return self._database.find_assets(
            search=search,
            asset_kind=asset_kind,
            importer=importer,
            extensions=extensions,
        )

    def list_assets(
        self,
        search: str = "",
        extensions: Optional[List[str]] = None,
        asset_kind: str = "",
        importer: str = "",
    ) -> List[Dict[str, Any]]:
        return self.find_assets(search=search, asset_kind=asset_kind, importer=importer, extensions=extensions)

    def get_asset_entry(self, locator: Any) -> Optional[Dict[str, Any]]:
        return self._database.get_asset_entry(locator)

    def get_asset_reference(self, locator: Any) -> Dict[str, str]:
        return self._resolver.canonical_reference(locator)

    def resolve_reference(self, locator: Any) -> Dict[str, str]:
        return self.get_asset_reference(locator)

    def resolve_asset_path(self, locator: Any) -> Path:
        resolved = self._resolver.resolve_path(locator)
        if resolved:
            return Path(resolved)
        path = self._resolve_locator_path(locator)
        return self._project_service.resolve_path(path)

    def get_metadata_path(self, locator: Any) -> Path:
        asset_path = self._resolve_locator_path(locator)
        if not asset_path:
            return Path("")
        return self._database.get_metadata_path(asset_path)

    def load_metadata(self, locator: Any) -> Dict[str, Any]:
        asset_path = self._resolve_locator_path(locator)
        if not asset_path:
            return self._default_metadata("")
        return self._database.load_metadata(asset_path)

    def save_metadata(self, locator: Any, metadata: Dict[str, Any], record_history: bool = True) -> Dict[str, Any]:
        asset_path = self._resolve_locator_path(locator)
        before = self.load_metadata(asset_path)
        payload = dict(before)
        payload.update(metadata)
        payload["source_path"] = asset_path
        saved = self._database.save_metadata(asset_path, payload)
        if record_history and self._history is not None and asset_path:
            after = json.loads(json.dumps(saved))
            self._history.push(
                label=f"Asset metadata: {saved['source_path']}",
                undo=lambda: self.save_metadata(asset_path, before, record_history=False),
                redo=lambda: self.save_metadata(asset_path, after, record_history=False),
            )
        return saved

    def reimport_asset(self, locator: Any) -> Optional[Dict[str, Any]]:
        return self._database.reimport_asset(locator)

    def build_asset_artifacts(self) -> Dict[str, Any]:
        return self._database.build_asset_artifacts()

    def create_bundle(self) -> Dict[str, Any]:
        return self._database.create_bundle()

    def load_material_definition(self, locator: Any) -> Material2D:
        material_path = self._resolve_locator_path(locator)
        if not material_path:
            return Material2D()
        file_path = self.resolve_asset_path(material_path)
        if not file_path.exists():
            return Material2D()
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return Material2D()
        return Material2D.from_dict(payload)

    def save_material_definition(self, locator: Any, material: Material2D) -> Dict[str, Any]:
        material_path = self._resolve_locator_path(locator)
        if not material_path:
            raise ValueError("Material path is required")
        file_path = self.resolve_asset_path(material_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(material.to_dict(), indent=2), encoding="utf-8")
        metadata = self.load_metadata(material_path)
        metadata["asset_kind"] = "material"
        metadata["importer"] = "material"
        self.save_metadata(material_path, metadata, record_history=False)
        return {
            "path": material_path,
            "material": material.to_dict(),
        }

    def move_asset(self, locator: Any, destination_path: str) -> Optional[Dict[str, Any]]:
        return self._database.move_asset(locator, destination_path)

    def rename_asset(self, locator: Any, new_name: str) -> Optional[Dict[str, Any]]:
        return self._database.rename_asset(locator, new_name)

    def generate_grid_slices(
        self,
        locator: Any,
        cell_width: int,
        cell_height: int,
        margin: int = 0,
        spacing: int = 0,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        asset_path = self._resolve_locator_path(locator)
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
        metadata["asset_type"] = "sprite_sheet"
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

    def generate_auto_slices(
        self,
        locator: Any,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
        alpha_threshold: int = 1,
    ) -> Dict[str, Any]:
        asset_path = self._resolve_locator_path(locator)
        prefix = naming_prefix or Path(asset_path).stem
        slices = self.preview_auto_slices(
            asset_path,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=prefix,
            alpha_threshold=alpha_threshold,
        )

        metadata = self.load_metadata(asset_path)
        metadata["asset_type"] = "sprite_sheet"
        metadata["import_mode"] = "automatic"
        metadata["grid"] = {}
        metadata["automatic"] = {
            "pivot_x": pivot_x,
            "pivot_y": pivot_y,
            "alpha_threshold": alpha_threshold,
            "naming_prefix": prefix,
        }
        metadata["slices"] = slices
        return self.save_metadata(asset_path, metadata)

    def apply_auto_slices(
        self,
        locator: Any,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
        alpha_threshold: int = 1,
    ) -> Dict[str, Any]:
        return self.generate_auto_slices(
            locator,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
            alpha_threshold=alpha_threshold,
        )

    def save_manual_slices(
        self,
        locator: Any,
        slices: List[Dict[str, Any]],
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        asset_path = self._resolve_locator_path(locator)
        prefix = naming_prefix or Path(asset_path).stem
        normalized: List[Dict[str, Any]] = []
        for index, item in enumerate(slices):
            width = max(1, int(item.get("width", 0)))
            height = max(1, int(item.get("height", 0)))
            normalized.append(
                {
                    "name": str(item.get("name") or f"{prefix}_{index}"),
                    "x": max(0, int(item.get("x", 0))),
                    "y": max(0, int(item.get("y", 0))),
                    "width": width,
                    "height": height,
                    "pivot_x": float(item.get("pivot_x", pivot_x)),
                    "pivot_y": float(item.get("pivot_y", pivot_y)),
                }
            )
        metadata = self.load_metadata(asset_path)
        metadata["asset_type"] = "sprite_sheet"
        metadata["import_mode"] = "manual"
        metadata["grid"] = {}
        metadata["automatic"] = {}
        metadata["slices"] = normalized
        return self.save_metadata(asset_path, metadata)

    def apply_manual_slices(
        self,
        locator: Any,
        slices: List[Dict[str, Any]],
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.save_manual_slices(
            locator,
            slices=slices,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )

    def preview_auto_slices(
        self,
        locator: Any,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
        alpha_threshold: int = 1,
        color_tolerance: int = 12,
        structured: bool = False,
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        payload = self._preview_auto_slices_payload(
            locator,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
            alpha_threshold=alpha_threshold,
            color_tolerance=color_tolerance,
        )
        if structured:
            return payload
        return list(payload["slices"])

    def group_slices(
        self,
        locator: Any,
        *,
        group_mode: str = "visual_order",
        slice_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        asset_path = self._resolve_locator_path(locator)
        normalized_mode = str(group_mode or "visual_order").strip().lower()
        if normalized_mode not in self.VALID_SLICE_GROUP_MODES:
            raise ValueError(f"Unsupported slice group mode: {group_mode}")

        available = self._normalize_slice_collection(self.list_slices(asset_path))
        selected, missing = self._filter_selected_slices(available, slice_names)
        ordered = sorted(selected, key=self._slice_visual_key)
        groups: list[dict[str, Any]] = []

        if normalized_mode == "visual_order":
            if ordered:
                groups.append(self._build_slice_group("visual_order", "visual_order", ordered))
        elif normalized_mode == "row":
            rows: dict[int, list[dict[str, Any]]] = {}
            for slice_info in ordered:
                rows.setdefault(int(slice_info["y"]), []).append(slice_info)
            for index, row_y in enumerate(sorted(rows)):
                groups.append(self._build_slice_group(f"row_{index}", f"row:{row_y}", rows[row_y]))
        else:
            grouped_by_prefix: dict[str, list[dict[str, Any]]] = {}
            first_order: dict[str, tuple[int, int, str]] = {}
            for slice_info in ordered:
                prefix = self._slice_name_prefix(str(slice_info["name"]))
                grouped_by_prefix.setdefault(prefix, []).append(slice_info)
                first_order.setdefault(prefix, self._slice_visual_key(slice_info))
            for prefix in sorted(grouped_by_prefix, key=lambda item: (first_order[item], item)):
                groups.append(self._build_slice_group(prefix, prefix, grouped_by_prefix[prefix]))

        return {
            "asset_path": asset_path,
            "asset_reference": self.get_asset_reference(asset_path),
            "group_mode": normalized_mode,
            "selected_count": len(selected),
            "missing_slice_names": missing,
            "groups": groups,
        }

    def build_animation_from_slices(
        self,
        locator: Any,
        slice_names: List[str],
        *,
        state_name: str = "",
        fps: float = 8.0,
        loop: bool = True,
        on_complete: Optional[str] = None,
        order_mode: str = "selection",
    ) -> Dict[str, Any]:
        asset_path = self._resolve_locator_path(locator)
        normalized_order_mode = str(order_mode or "selection").strip().lower()
        if normalized_order_mode not in self.VALID_ANIMATION_ORDER_MODES:
            raise ValueError(f"Unsupported animation order mode: {order_mode}")

        available = self._normalize_slice_collection(self.list_slices(asset_path))
        ordered_slices = self._resolve_animation_slices(available, slice_names, order_mode=normalized_order_mode)
        if not ordered_slices:
            raise ValueError("At least one slice is required to build an animation")

        safe_fps = max(0.001, float(fps))
        frame_duration = 1.0 / safe_fps
        ordered_slice_names = [str(item["name"]) for item in ordered_slices]
        frame_widths = [int(item["width"]) for item in ordered_slices]
        frame_heights = [int(item["height"]) for item in ordered_slices]
        preview_frames = []
        for index, slice_info in enumerate(ordered_slices):
            preview_frames.append(
                {
                    "index": index,
                    "slice_name": str(slice_info["name"]),
                    "x": int(slice_info["x"]),
                    "y": int(slice_info["y"]),
                    "width": int(slice_info["width"]),
                    "height": int(slice_info["height"]),
                    "pivot_x": float(slice_info["pivot_x"]),
                    "pivot_y": float(slice_info["pivot_y"]),
                    "duration_seconds": round(frame_duration, 6),
                }
            )

        return {
            "asset_path": asset_path,
            "asset_reference": self.get_asset_reference(asset_path),
            "state_name": str(state_name or ""),
            "order_mode": normalized_order_mode,
            "slice_count": len(ordered_slices),
            "animation": {
                "frames": list(range(len(ordered_slices))),
                "slice_names": ordered_slice_names,
                "fps": float(fps),
                "loop": bool(loop),
                "on_complete": on_complete,
            },
            "preview": {
                "asset_path": asset_path,
                "state_name": str(state_name or ""),
                "frame_count": len(ordered_slices),
                "fps": float(fps),
                "loop": bool(loop),
                "duration_seconds": round(len(ordered_slices) / safe_fps, 6),
                "frame_size_summary": {
                    "min_width": min(frame_widths),
                    "max_width": max(frame_widths),
                    "min_height": min(frame_heights),
                    "max_height": max(frame_heights),
                    "variable_size": (min(frame_widths) != max(frame_widths)) or (min(frame_heights) != max(frame_heights)),
                },
                "frames": preview_frames,
            },
        }

    def _preview_auto_slices_payload(
        self,
        locator: Any,
        *,
        pivot_x: float,
        pivot_y: float,
        naming_prefix: Optional[str],
        alpha_threshold: int,
        color_tolerance: int,
    ) -> Dict[str, Any]:
        file_path = self.resolve_asset_path(locator)
        asset_path = self._resolve_locator_path(locator)
        prefix = naming_prefix or file_path.stem
        width, height = self.get_image_size(asset_path)
        payload = {
            "asset_path": asset_path,
            "asset_reference": self.get_asset_reference(asset_path),
            "image": {"width": int(width), "height": int(height)},
            "settings": {
                "pivot_x": float(pivot_x),
                "pivot_y": float(pivot_y),
                "naming_prefix": prefix,
                "alpha_threshold": int(alpha_threshold),
                "color_tolerance": int(color_tolerance),
            },
            "slice_count": 0,
            "slices": [],
        }
        if not file_path.exists():
            return payload

        image = rl.load_image(file_path.as_posix())
        if not rl.is_image_valid(image):
            return payload

        width = int(image.width)
        height = int(image.height)
        colors = rl.load_image_colors(image)
        payload["image"] = {"width": width, "height": height}
        try:
            slices = self._detect_auto_slices_from_colors(
                width,
                height,
                colors,
                prefix=prefix,
                pivot_x=pivot_x,
                pivot_y=pivot_y,
                alpha_threshold=alpha_threshold,
                color_tolerance=color_tolerance,
            )
            payload["slices"] = self._normalize_slice_collection(slices)
            payload["slice_count"] = len(payload["slices"])
            return payload
        finally:
            rl.unload_image_colors(colors)
            rl.unload_image(image)

    def import_asset(self, source_path: str, target_folder: str = "", overwrite: bool = False) -> str:
        if not source_path:
            raise ValueError("Source path is required")
        source = Path(source_path).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Asset not found: {source_path}")

        assets_root = self._project_service.get_project_path("assets")
        destination_dir = assets_root / target_folder if target_folder else assets_root
        destination_dir.mkdir(parents=True, exist_ok=True)

        destination = destination_dir / source.name
        if not overwrite:
            suffix = 1
            while destination.exists():
                destination = destination_dir / f"{source.stem}_{suffix}{source.suffix}"
                suffix += 1

        shutil.copy2(source, destination)
        imported_path = self._project_service.to_relative_path(destination)
        self.reimport_asset(imported_path)
        return imported_path

    def list_slices(self, locator: Any) -> List[Dict[str, Any]]:
        asset_path = self._resolve_locator_path(locator)
        if not asset_path:
            return []
        return self._database.list_slices(asset_path)

    def get_slice_rect(self, locator: Any, slice_name: str) -> Optional[Dict[str, Any]]:
        asset_path = self._resolve_locator_path(locator)
        if not asset_path:
            return None
        return self._database.get_slice_rect(asset_path, slice_name)

    def get_image_size(self, locator: Any) -> tuple[int, int]:
        file_path = self.resolve_asset_path(locator)
        if not file_path.exists():
            return (0, 0)
        if file_path.suffix.lower() == ".png":
            with file_path.open("rb") as handle:
                signature = handle.read(24)
            if signature[:8] != b"\x89PNG\r\n\x1a\n":
                return (0, 0)
            width, height = struct.unpack(">II", signature[16:24])
            return (int(width), int(height))
        image = rl.load_image(file_path.as_posix())
        if not rl.is_image_valid(image):
            return (0, 0)
        try:
            return (int(image.width), int(image.height))
        finally:
            rl.unload_image(image)

    def _resolve_locator_path(self, locator: Any) -> str:
        if isinstance(locator, str):
            return locator.strip().replace("\\", "/")
        ref = normalize_asset_reference(locator)
        if ref.get("path"):
            return ref["path"]
        entry = self._database.get_asset_entry(ref)
        if entry is not None:
            return str(entry.get("path", ""))
        return ""

    def _default_metadata(self, asset_path: str) -> Dict[str, Any]:
        if asset_path:
            return self._database.load_metadata(asset_path)
        return {
            "guid": "",
            "source_path": "",
            "path": "",
            "asset_kind": "unknown",
            "importer": "unknown",
            "labels": [],
            "dependencies": [],
            "import_settings": {},
            "asset_type": "unknown",
            "import_mode": "raw",
            "grid": {},
            "automatic": {},
            "slices": [],
        }

    def _normalize_slice_collection(self, slices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(slices):
            normalized.append(
                {
                    "name": str(item.get("name") or f"slice_{index}"),
                    "x": int(item.get("x", 0)),
                    "y": int(item.get("y", 0)),
                    "width": max(1, int(item.get("width", 1))),
                    "height": max(1, int(item.get("height", 1))),
                    "pivot_x": float(item.get("pivot_x", 0.5)),
                    "pivot_y": float(item.get("pivot_y", 0.5)),
                }
            )
        return normalized

    def _filter_selected_slices(
        self,
        available: List[Dict[str, Any]],
        selected_names: Optional[List[str]],
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        if not selected_names:
            return (list(available), [])
        by_name = {str(item["name"]): item for item in available}
        selected: list[dict[str, Any]] = []
        missing: list[str] = []
        seen: set[str] = set()
        for name in selected_names:
            normalized_name = str(name or "").strip()
            if not normalized_name or normalized_name in seen:
                continue
            seen.add(normalized_name)
            slice_info = by_name.get(normalized_name)
            if slice_info is None:
                missing.append(normalized_name)
                continue
            selected.append(slice_info)
        return (selected, missing)

    def _resolve_animation_slices(
        self,
        available: List[Dict[str, Any]],
        slice_names: List[str],
        *,
        order_mode: str,
    ) -> List[Dict[str, Any]]:
        by_name = {str(item["name"]): item for item in available}
        ordered: list[dict[str, Any]] = []
        missing: list[str] = []
        for name in slice_names:
            normalized_name = str(name or "").strip()
            if not normalized_name:
                continue
            slice_info = by_name.get(normalized_name)
            if slice_info is None:
                missing.append(normalized_name)
                continue
            ordered.append(slice_info)
        if missing:
            raise ValueError(f"Unknown slice names: {', '.join(missing)}")
        if order_mode == "visual":
            ordered.sort(key=self._slice_visual_key)
        return ordered

    def _build_slice_group(self, group_key: str, label: str, slices: List[Dict[str, Any]]) -> Dict[str, Any]:
        ordered = sorted(slices, key=self._slice_visual_key)
        return {
            "group_key": str(group_key),
            "label": str(label),
            "frame_count": len(ordered),
            "slice_names": [str(item["name"]) for item in ordered],
            "slices": [dict(item) for item in ordered],
        }

    def _slice_visual_key(self, slice_info: Dict[str, Any]) -> tuple[int, int, str]:
        return (
            int(slice_info.get("y", 0)),
            int(slice_info.get("x", 0)),
            str(slice_info.get("name", "")),
        )

    def _slice_name_prefix(self, slice_name: str) -> str:
        normalized = str(slice_name or "").strip()
        if not normalized:
            return "unnamed"
        if "_" in normalized:
            prefix, suffix = normalized.rsplit("_", 1)
            if prefix and suffix.isdigit():
                return prefix
        end = len(normalized)
        while end > 0 and normalized[end - 1].isdigit():
            end -= 1
        trimmed = normalized[:end].rstrip("_- ")
        return trimmed or normalized

    def _detect_auto_slices_from_colors(
        self,
        width: int,
        height: int,
        colors: Any,
        *,
        prefix: str,
        pivot_x: float,
        pivot_y: float,
        alpha_threshold: int,
        color_tolerance: int,
    ) -> List[Dict[str, Any]]:
        background_mask = self._build_background_mask(width, height, colors, alpha_threshold, color_tolerance)
        visited = [False] * (width * height)
        slices: List[Dict[str, Any]] = []
        neighbors = (
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (1, -1), (-1, 1), (1, 1),
        )

        for py in range(height):
            for px in range(width):
                idx = py * width + px
                if visited[idx] or background_mask[idx]:
                    continue
                queue = deque([(px, py)])
                visited[idx] = True
                min_x = max_x = px
                min_y = max_y = py

                while queue:
                    cx, cy = queue.popleft()
                    min_x = min(min_x, cx)
                    max_x = max(max_x, cx)
                    min_y = min(min_y, cy)
                    max_y = max(max_y, cy)
                    for dx, dy in neighbors:
                        nx, ny = cx + dx, cy + dy
                        if nx < 0 or ny < 0 or nx >= width or ny >= height:
                            continue
                        nidx = ny * width + nx
                        if visited[nidx] or background_mask[nidx]:
                            continue
                        visited[nidx] = True
                        queue.append((nx, ny))

                slices.append(
                    {
                        "name": f"{prefix}_{len(slices)}",
                        "x": min_x,
                        "y": min_y,
                        "width": max_x - min_x + 1,
                        "height": max_y - min_y + 1,
                        "pivot_x": pivot_x,
                        "pivot_y": pivot_y,
                    }
                )

        slices.sort(key=lambda item: (item["y"], item["x"]))
        for order, slice_info in enumerate(slices):
            slice_info["name"] = f"{prefix}_{order}"
        return slices

    def _build_background_mask(
        self,
        width: int,
        height: int,
        colors: Any,
        alpha_threshold: int,
        color_tolerance: int,
    ) -> List[bool]:
        total = width * height
        mask = [False] * total

        def color_at(px: int, py: int) -> Any:
            return colors[py * width + px]

        has_transparency = any(colors[index].a < alpha_threshold for index in range(total))
        if has_transparency:
            for index in range(total):
                mask[index] = colors[index].a < alpha_threshold
            return mask

        border_colors = []
        for px in range(width):
            border_colors.append((color_at(px, 0).r, color_at(px, 0).g, color_at(px, 0).b))
            border_colors.append((color_at(px, height - 1).r, color_at(px, height - 1).g, color_at(px, height - 1).b))
        for py in range(height):
            border_colors.append((color_at(0, py).r, color_at(0, py).g, color_at(0, py).b))
            border_colors.append((color_at(width - 1, py).r, color_at(width - 1, py).g, color_at(width - 1, py).b))

        background_color = Counter(border_colors).most_common(1)[0][0] if border_colors else (255, 255, 255)

        def is_background_color(px: int, py: int) -> bool:
            color = color_at(px, py)
            return (
                abs(int(color.r) - background_color[0]) <= color_tolerance
                and abs(int(color.g) - background_color[1]) <= color_tolerance
                and abs(int(color.b) - background_color[2]) <= color_tolerance
            )

        queue = deque()
        for px in range(width):
            if is_background_color(px, 0):
                idx = px
                if not mask[idx]:
                    mask[idx] = True
                    queue.append((px, 0))
            if is_background_color(px, height - 1):
                idx = (height - 1) * width + px
                if not mask[idx]:
                    mask[idx] = True
                    queue.append((px, height - 1))
        for py in range(height):
            if is_background_color(0, py):
                idx = py * width
                if not mask[idx]:
                    mask[idx] = True
                    queue.append((0, py))
            if is_background_color(width - 1, py):
                idx = py * width + (width - 1)
                if not mask[idx]:
                    mask[idx] = True
                    queue.append((width - 1, py))

        while queue:
            cx, cy = queue.popleft()
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                idx = ny * width + nx
                if mask[idx] or not is_background_color(nx, ny):
                    continue
                mask[idx] = True
                queue.append((nx, ny))

        return mask
