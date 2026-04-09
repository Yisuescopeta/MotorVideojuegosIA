from __future__ import annotations

import copy
from typing import Any

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component


class Tilemap(Component):
    """Tilemap serializable con layers, tileset, metadata por tile y enriquecimiento para authoring."""

    VALID_ORIENTATIONS = {"orthogonal"}
    VALID_TILESET_MODES = {"grid", "atlas_slices"}

    def __init__(
        self,
        cell_width: int = 16,
        cell_height: int = 16,
        orientation: str = "orthogonal",
        tileset_mode: str = "grid",
        tileset: Any = None,
        tileset_path: str = "",
        layers: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        tileset_tile_width: int = 16,
        tileset_tile_height: int = 16,
        tileset_columns: int = 0,
        tileset_spacing: int = 0,
        tileset_margin: int = 0,
        default_layer_name: str = "Layer",
    ) -> None:
        self.enabled: bool = True
        self.cell_width: int = max(1, int(cell_width))
        self.cell_height: int = max(1, int(cell_height))
        normalized_orientation = str(orientation or "orthogonal")
        self.orientation: str = normalized_orientation if normalized_orientation in self.VALID_ORIENTATIONS else "orthogonal"
        normalized_tileset_mode = str(tileset_mode or "grid").strip().lower()
        self.tileset_mode: str = normalized_tileset_mode if normalized_tileset_mode in self.VALID_TILESET_MODES else "grid"
        self.tileset = normalize_asset_reference(tileset if tileset is not None else tileset_path)
        self.tileset_path: str = self.tileset.get("path", "")
        self.layers: list[dict[str, Any]] = self._normalize_layers(layers or [])
        self.metadata: dict[str, Any] = copy.deepcopy(metadata or {})
        self.tileset_tile_width: int = max(1, int(tileset_tile_width))
        self.tileset_tile_height: int = max(1, int(tileset_tile_height))
        self.tileset_columns: int = max(0, int(tileset_columns))
        self.tileset_spacing: int = max(0, int(tileset_spacing))
        self.tileset_margin: int = max(0, int(tileset_margin))
        self.default_layer_name: str = str(default_layer_name or "Layer").strip() or "Layer"

    def get_tileset_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.tileset)

    def sync_tileset_reference(self, reference: Any) -> None:
        self.tileset = normalize_asset_reference(reference)
        self.tileset_path = self.tileset.get("path", "")

    def set_tile(
        self,
        layer_name: str,
        x: int,
        y: int,
        tile_id: str,
        *,
        source: Any = None,
        flags: list[str] | None = None,
        tags: list[str] | None = None,
        custom: dict[str, Any] | None = None,
        animated: bool = False,
        animation_id: str = "",
        terrain_type: str = "",
        slice_name: str = "",
        create_layer: bool = True,
    ) -> None:
        layer = self._ensure_layer(layer_name) if create_layer else self._find_layer(layer_name)
        if layer is None:
            raise ValueError(f"Layer '{layer_name}' does not exist and create_layer=False")
        key = f"{int(x)},{int(y)}"
        tiles = layer.setdefault("tiles", {})
        tiles[key] = {
            "tile_id": str(tile_id),
            "source": normalize_asset_reference(source),
            "flags": [str(item) for item in (flags or []) if str(item).strip()],
            "tags": [str(item) for item in (tags or []) if str(item).strip()],
            "custom": copy.deepcopy(custom or {}),
            "animated": bool(animated),
            "animation_id": str(animation_id or "").strip(),
            "terrain_type": str(terrain_type or "").strip(),
            "slice_name": str(slice_name or "").strip(),
        }

    def set_tile_full(
        self,
        layer_name: str,
        x: int,
        y: int,
        tile_id: str,
        *,
        source: Any = None,
        flags: list[str] | None = None,
        tags: list[str] | None = None,
        custom: dict[str, Any] | None = None,
        animated: bool = False,
        animation_id: str = "",
        terrain_type: str = "",
        slice_name: str = "",
        create_layer: bool = True,
    ) -> None:
        self.set_tile(
            layer_name,
            x,
            y,
            tile_id,
            source=source,
            flags=flags,
            tags=tags,
            custom=custom,
            animated=animated,
            animation_id=animation_id,
            terrain_type=terrain_type,
            slice_name=slice_name,
            create_layer=create_layer,
        )

    def fill_rect(
        self,
        layer_name: str,
        x_start: int,
        y_start: int,
        x_end: int,
        y_end: int,
        tile_id: str,
        *,
        source: Any = None,
        flags: list[str] | None = None,
        tags: list[str] | None = None,
        custom: dict[str, Any] | None = None,
        animated: bool = False,
        animation_id: str = "",
        terrain_type: str = "",
        slice_name: str = "",
        create_layer: bool = True,
    ) -> int:
        layer = self._ensure_layer(layer_name) if create_layer else self._find_layer(layer_name)
        if layer is None:
            raise ValueError(f"Layer '{layer_name}' does not exist and create_layer=False")
        tiles = layer.setdefault("tiles", {})
        count = 0
        x_start_i = int(x_start)
        y_start_i = int(y_start)
        x_end_i = int(x_end)
        y_end_i = int(y_end)
        for y in range(y_start_i, y_end_i + 1):
            for x in range(x_start_i, x_end_i + 1):
                key = f"{x},{y}"
                tiles[key] = {
                    "tile_id": str(tile_id),
                    "source": normalize_asset_reference(source),
                    "flags": [str(item) for item in (flags or []) if str(item).strip()],
                    "tags": [str(item) for item in (tags or []) if str(item).strip()],
                    "custom": copy.deepcopy(custom or {}),
                    "animated": bool(animated),
                    "animation_id": str(animation_id or "").strip(),
                    "terrain_type": str(terrain_type or "").strip(),
                    "slice_name": str(slice_name or "").strip(),
                }
                count += 1
        return count

    def clear_tile(self, layer_name: str, x: int, y: int, create_layer: bool = True) -> None:
        layer = self._ensure_layer(layer_name) if create_layer else self._find_layer(layer_name)
        if layer is None:
            raise ValueError(f"Layer '{layer_name}' does not exist and create_layer=False")
        layer.setdefault("tiles", {}).pop(f"{int(x)},{int(y)}", None)

    def get_tile(self, layer_name: str, x: int, y: int) -> dict[str, Any] | None:
        layer = self._find_layer(layer_name)
        if layer is None:
            return None
        tile = layer.setdefault("tiles", {}).get(f"{int(x)},{int(y)}")
        return copy.deepcopy(tile) if tile is not None else None

    def get_layer(self, layer_name: str) -> dict[str, Any] | None:
        layer = self._find_layer(layer_name)
        return copy.deepcopy(layer) if layer is not None else None

    def add_layer(
        self,
        layer_name: str,
        *,
        visible: bool = True,
        opacity: float = 1.0,
        locked: bool = False,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        collision_layer: int = 0,
        tilemap_source: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_name = str(layer_name or self.default_layer_name).strip()
        if not normalized_name:
            normalized_name = self.default_layer_name
        if self._find_layer(normalized_name) is not None:
            existing = self._find_layer(normalized_name)
            if existing is not None:
                return existing
        layer: dict[str, Any] = {
            "name": normalized_name,
            "visible": bool(visible),
            "opacity": float(max(0.0, min(1.0, opacity))),
            "locked": bool(locked),
            "offset_x": float(offset_x),
            "offset_y": float(offset_y),
            "collision_layer": max(0, int(collision_layer)),
            "tilemap_source": normalize_asset_reference(tilemap_source) if tilemap_source else {},
            "metadata": copy.deepcopy(metadata or {}),
            "tiles": {},
        }
        self.layers.append(layer)
        return layer

    def remove_layer(self, layer_name: str) -> bool:
        normalized_name = str(layer_name or "").strip()
        for i, layer in enumerate(self.layers):
            if layer.get("name") == normalized_name:
                self.layers.pop(i)
                return True
        return False

    def set_layer_properties(
        self,
        layer_name: str,
        *,
        visible: bool | None = None,
        opacity: float | None = None,
        locked: bool | None = None,
        offset_x: float | None = None,
        offset_y: float | None = None,
        collision_layer: int | None = None,
        tilemap_source: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        layer = self._find_layer(layer_name)
        if layer is None:
            return False
        if visible is not None:
            layer["visible"] = bool(visible)
        if opacity is not None:
            layer["opacity"] = float(max(0.0, min(1.0, opacity)))
        if locked is not None:
            layer["locked"] = bool(locked)
        if offset_x is not None:
            layer["offset_x"] = float(offset_x)
        if offset_y is not None:
            layer["offset_y"] = float(offset_y)
        if collision_layer is not None:
            layer["collision_layer"] = max(0, int(collision_layer))
        if tilemap_source is not None:
            layer["tilemap_source"] = normalize_asset_reference(tilemap_source)
        if metadata is not None:
            if isinstance(metadata, dict):
                existing = layer.get("metadata", {})
                if isinstance(existing, dict):
                    existing.update(metadata)
                    layer["metadata"] = existing
                else:
                    layer["metadata"] = copy.deepcopy(metadata)
            else:
                layer["metadata"] = copy.deepcopy(metadata or {})
        return True

    def resize(self, cell_width: int, cell_height: int, *, offset_x: int = 0, offset_y: int = 0) -> bool:
        new_cell_width = max(1, int(cell_width))
        new_cell_height = max(1, int(cell_height))
        self.cell_width = new_cell_width
        self.cell_height = new_cell_height
        self.metadata["grid_offset_x"] = int(offset_x)
        self.metadata["grid_offset_y"] = int(offset_y)
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cell_width": self.cell_width,
            "cell_height": self.cell_height,
            "orientation": self.orientation,
            "tileset_mode": self.tileset_mode,
            "tileset": self.get_tileset_reference(),
            "tileset_path": self.tileset_path,
            "layers": self._serialize_layers(),
            "metadata": copy.deepcopy(self.metadata),
            "tileset_tile_width": self.tileset_tile_width,
            "tileset_tile_height": self.tileset_tile_height,
            "tileset_columns": self.tileset_columns,
            "tileset_spacing": self.tileset_spacing,
            "tileset_margin": self.tileset_margin,
            "default_layer_name": self.default_layer_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tilemap":
        tileset_ref = normalize_asset_reference(data.get("tileset"))
        tileset_path = data.get("tileset_path", "")
        if tileset_path and tileset_ref.get("path") != tileset_path:
            tileset_ref = build_asset_reference(tileset_path, tileset_ref.get("guid", ""))
        component = cls(
            cell_width=data.get("cell_width", 16),
            cell_height=data.get("cell_height", 16),
            orientation=data.get("orientation", "orthogonal"),
            tileset_mode=data.get("tileset_mode", "grid"),
            tileset=tileset_ref,
            tileset_path=tileset_path,
            layers=data.get("layers", []),
            metadata=data.get("metadata"),
            tileset_tile_width=data.get("tileset_tile_width", 16),
            tileset_tile_height=data.get("tileset_tile_height", 16),
            tileset_columns=data.get("tileset_columns", 0),
            tileset_spacing=data.get("tileset_spacing", 0),
            tileset_margin=data.get("tileset_margin", 0),
            default_layer_name=data.get("default_layer_name", "Layer"),
        )
        component.enabled = data.get("enabled", True)
        return component

    def _find_layer(self, layer_name: str) -> dict[str, Any] | None:
        normalized_name = str(layer_name or "").strip()
        for layer in self.layers:
            if layer.get("name") == normalized_name:
                return layer
        return None

    def _ensure_layer(self, layer_name: str) -> dict[str, Any]:
        """Find existing layer or create new one with default properties.

        WARNING: This method performs implicit layer creation (autovivification).
        This can hide bugs when typos in layer names create phantom layers.
        Use create_layer=False in set_tile/fill_rect/clear_tile to disable.
        """
        layer = self._find_layer(layer_name)
        if layer is not None:
            return layer
        layer = {
            "name": str(layer_name or self.default_layer_name).strip() or self.default_layer_name,
            "visible": True,
            "opacity": 1.0,
            "locked": False,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "collision_layer": 0,
            "tilemap_source": {},
            "metadata": {},
            "tiles": {},
        }
        self.layers.append(layer)
        return layer

    def _normalize_layers(self, layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_layers: list[dict[str, Any]] = []
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            layer_name = str(layer.get("name") or f"Layer_{index}")
            tiles_map: dict[str, dict[str, Any]] = {}
            raw_tiles = layer.get("tiles", {})
            if isinstance(raw_tiles, list):
                for tile in raw_tiles:
                    if not isinstance(tile, dict):
                        continue
                    key = f"{int(tile.get('x', 0))},{int(tile.get('y', 0))}"
                    tiles_map[key] = self._normalize_tile(tile)
            elif isinstance(raw_tiles, dict):
                for key, tile in raw_tiles.items():
                    if not isinstance(tile, dict):
                        continue
                    tiles_map[str(key)] = self._normalize_tile(tile)
            normalized_layers.append(
                {
                    "name": layer_name,
                    "visible": bool(layer.get("visible", True)),
                    "opacity": float(layer.get("opacity", 1.0)),
                    "locked": bool(layer.get("locked", False)),
                    "offset_x": float(layer.get("offset_x", 0.0)),
                    "offset_y": float(layer.get("offset_y", 0.0)),
                    "collision_layer": max(0, int(layer.get("collision_layer", 0))),
                    "tilemap_source": normalize_asset_reference(layer.get("tilemap_source")),
                    "metadata": copy.deepcopy(layer.get("metadata", {})) if isinstance(layer.get("metadata", {}), dict) else {},
                    "tiles": tiles_map,
                }
            )
        return normalized_layers

    def _normalize_tile(self, tile: dict[str, Any]) -> dict[str, Any]:
        return {
            "tile_id": str(tile.get("tile_id", "")),
            "source": normalize_asset_reference(tile.get("source")),
            "flags": [str(item) for item in tile.get("flags", []) if str(item).strip()],
            "tags": [str(item) for item in tile.get("tags", []) if str(item).strip()],
            "custom": copy.deepcopy(tile.get("custom", {})) if isinstance(tile.get("custom", {}), dict) else {},
            "animated": bool(tile.get("animated", False)),
            "animation_id": str(tile.get("animation_id", "")).strip(),
            "terrain_type": str(tile.get("terrain_type", "")).strip(),
            "slice_name": str(tile.get("slice_name", "")).strip(),
        }

    def _serialize_layers(self) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for layer in self.layers:
            tiles_payload: list[dict[str, Any]] = []
            for key, tile in sorted(layer.get("tiles", {}).items()):
                x_value, y_value = key.split(",", 1)
                tiles_payload.append(
                    {
                        "x": int(x_value),
                        "y": int(y_value),
                        "tile_id": str(tile.get("tile_id", "")),
                        "source": clone_asset_reference(tile.get("source", {})),
                        "flags": list(tile.get("flags", [])),
                        "tags": list(tile.get("tags", [])),
                        "custom": copy.deepcopy(tile.get("custom", {})),
                        "animated": bool(tile.get("animated", False)),
                        "animation_id": str(tile.get("animation_id", "")).strip(),
                        "terrain_type": str(tile.get("terrain_type", "")).strip(),
                        "slice_name": str(tile.get("slice_name", "")).strip(),
                    }
                )
            serialized.append(
                {
                    "name": str(layer.get("name", "Layer")),
                    "visible": bool(layer.get("visible", True)),
                    "opacity": float(layer.get("opacity", 1.0)),
                    "locked": bool(layer.get("locked", False)),
                    "offset_x": float(layer.get("offset_x", 0.0)),
                    "offset_y": float(layer.get("offset_y", 0.0)),
                    "collision_layer": max(0, int(layer.get("collision_layer", 0))),
                    "tilemap_source": clone_asset_reference(layer.get("tilemap_source", {})),
                    "metadata": copy.deepcopy(layer.get("metadata", {})),
                    "tiles": tiles_payload,
                }
            )
        return serialized
