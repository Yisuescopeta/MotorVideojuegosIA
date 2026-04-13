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

    def get_sprite_metadata(self, locator: Any) -> Dict[str, Any]:
        return self.load_metadata(locator)

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
        payload["path"] = asset_path
        payload = self._synchronize_sprite_metadata(payload)
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

    def generate_sprite_grid_slices(
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
        width, height = self.get_sprite_image_size(asset_path)
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
        return self._save_sprite_pipeline_metadata(
            asset_path,
            import_mode="grid",
            slices=slices,
            grid={
                "cell_width": cell_width,
                "cell_height": cell_height,
                "margin": margin,
                "spacing": spacing,
                "pivot_x": pivot_x,
                "pivot_y": pivot_y,
                "naming_prefix": prefix,
            },
            automatic={},
        )

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
        return self.generate_sprite_grid_slices(
            locator,
            cell_width=cell_width,
            cell_height=cell_height,
            margin=margin,
            spacing=spacing,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )

    def generate_sprite_auto_slices(
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
        return self._save_sprite_pipeline_metadata(
            asset_path,
            import_mode="automatic",
            slices=slices,
            grid={},
            automatic={
                "pivot_x": pivot_x,
                "pivot_y": pivot_y,
                "alpha_threshold": alpha_threshold,
                "naming_prefix": prefix,
            },
        )

    def generate_auto_slices(
        self,
        locator: Any,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
        alpha_threshold: int = 1,
    ) -> Dict[str, Any]:
        return self.generate_sprite_auto_slices(
            locator,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
            alpha_threshold=alpha_threshold,
        )

    def save_sprite_manual_slices(
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
        return self._save_sprite_pipeline_metadata(
            asset_path,
            import_mode="manual",
            slices=normalized,
            grid={},
            automatic={},
        )

    def save_manual_slices(
        self,
        locator: Any,
        slices: List[Dict[str, Any]],
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.save_sprite_manual_slices(
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
    ) -> List[Dict[str, Any]]:
        file_path = self.resolve_asset_path(locator)
        if not file_path.exists():
            return []

        image = rl.load_image(file_path.as_posix())
        if not rl.is_image_valid(image):
            return []

        width = int(image.width)
        height = int(image.height)
        colors = rl.load_image_colors(image)
        prefix = naming_prefix or file_path.stem
        try:
            return self._detect_auto_slices_from_colors(
                width,
                height,
                colors,
                prefix=prefix,
                pivot_x=pivot_x,
                pivot_y=pivot_y,
                alpha_threshold=alpha_threshold,
                color_tolerance=color_tolerance,
            )
        finally:
            rl.unload_image_colors(colors)
            rl.unload_image(image)

    def import_sprite_asset(self, source_path: str, target_folder: str = "", overwrite: bool = False) -> str:
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

    def import_asset(self, source_path: str, target_folder: str = "", overwrite: bool = False) -> str:
        return self.import_sprite_asset(source_path, target_folder=target_folder, overwrite=overwrite)

    def list_sprite_slices(self, locator: Any) -> List[Dict[str, Any]]:
        asset_path = self._resolve_locator_path(locator)
        if not asset_path:
            return []
        return self._database.list_slices(asset_path)

    def list_slices(self, locator: Any) -> List[Dict[str, Any]]:
        return self.list_sprite_slices(locator)

    def get_sprite_slice_rect(self, locator: Any, slice_name: str) -> Optional[Dict[str, Any]]:
        asset_path = self._resolve_locator_path(locator)
        if not asset_path:
            return None
        return self._database.get_slice_rect(asset_path, slice_name)

    def get_slice_rect(self, locator: Any, slice_name: str) -> Optional[Dict[str, Any]]:
        return self.get_sprite_slice_rect(locator, slice_name)

    def get_sprite_image_size(self, locator: Any) -> tuple[int, int]:
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

    def get_image_size(self, locator: Any) -> tuple[int, int]:
        return self.get_sprite_image_size(locator)

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

    def _save_sprite_pipeline_metadata(
        self,
        locator: Any,
        *,
        import_mode: str,
        slices: List[Dict[str, Any]],
        grid: Optional[Dict[str, Any]] = None,
        automatic: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = self.load_metadata(locator)
        metadata["asset_type"] = "sprite_sheet"
        metadata["import_mode"] = import_mode
        metadata["grid"] = dict(grid or {})
        metadata["automatic"] = dict(automatic or {})
        metadata["slices"] = [dict(item) for item in slices]
        return self.save_metadata(locator, metadata)

    def _synchronize_sprite_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        asset_type = str(metadata.get("asset_type", "")).strip()
        asset_kind = str(metadata.get("asset_kind", "")).strip()
        has_sprite_shape = any(key in metadata for key in ("import_mode", "grid", "automatic", "slices"))
        if asset_type != "sprite_sheet" and asset_kind != "texture" and not has_sprite_shape:
            return metadata

        synchronized = dict(metadata)
        grid = dict(synchronized.get("grid", {})) if isinstance(synchronized.get("grid", {}), dict) else {}
        automatic = dict(synchronized.get("automatic", {})) if isinstance(synchronized.get("automatic", {}), dict) else {}
        slices = [dict(item) for item in synchronized.get("slices", [])] if isinstance(synchronized.get("slices", []), list) else []
        import_settings = (
            dict(synchronized.get("import_settings", {}))
            if isinstance(synchronized.get("import_settings", {}), dict)
            else {}
        )
        synchronized["grid"] = grid
        synchronized["automatic"] = automatic
        synchronized["slices"] = slices
        import_settings["asset_type"] = synchronized.get("asset_type", "sprite_sheet")
        import_settings["import_mode"] = synchronized.get("import_mode", "raw")
        import_settings["grid"] = dict(grid)
        import_settings["automatic"] = dict(automatic)
        import_settings["slices"] = [dict(item) for item in slices]
        synchronized["import_settings"] = import_settings
        return synchronized

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
