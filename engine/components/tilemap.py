from __future__ import annotations

import copy
import math
from typing import Any

from engine.assets.asset_reference import clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component
from engine.tilemap.model import TileData, TileLayerData, TilemapData


class Tilemap(Component):
    """Tilemap serializable con base incremental para evolucion futura."""

    VALID_ORIENTATIONS = {"orthogonal"}
    DEFAULT_CHUNK_SIZE = 16

    def __init__(
        self,
        cell_width: int = 16,
        cell_height: int = 16,
        orientation: str = "orthogonal",
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
        create_layer: bool = True,
    ) -> None:
        layer = self._ensure_layer(layer_name) if create_layer else self._find_layer(layer_name)
        if layer is None:
            raise ValueError(f"Layer '{layer_name}' does not exist and create_layer=False")
        coord = (int(x), int(y))
        layer.setdefault("tiles", {})[coord] = self._build_tile_payload(
            tile_id,
            source=source,
            flags=flags,
            tags=tags,
            custom=custom,
            animated=animated,
            animation_id=animation_id,
            terrain_type=terrain_type,
        )
        self._set_chunk_tile(layer, coord)

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
        create_layer: bool = True,
    ) -> int:
        layer = self._ensure_layer(layer_name) if create_layer else self._find_layer(layer_name)
        if layer is None:
            raise ValueError(f"Layer '{layer_name}' does not exist and create_layer=False")
        tiles = layer.setdefault("tiles", {})
        tile_payload = self._build_tile_payload(
            tile_id,
            source=source,
            flags=flags,
            tags=tags,
            custom=custom,
            animated=animated,
            animation_id=animation_id,
            terrain_type=terrain_type,
        )
        count = 0
        for y_value in range(int(y_start), int(y_end) + 1):
            for x_value in range(int(x_start), int(x_end) + 1):
                coord = (int(x_value), int(y_value))
                tiles[coord] = copy.deepcopy(tile_payload)
                self._set_chunk_tile(layer, coord)
                count += 1
        return count

    def clear_tile(self, layer_name: str, x: int, y: int, create_layer: bool = True) -> None:
        layer = self._ensure_layer(layer_name) if create_layer else self._find_layer(layer_name)
        if layer is None:
            raise ValueError(f"Layer '{layer_name}' does not exist and create_layer=False")
        coord = (int(x), int(y))
        layer.setdefault("tiles", {}).pop(coord, None)
        self._clear_chunk_tile(layer, coord)

    def get_tile(self, layer_name: str, x: int, y: int) -> dict[str, Any] | None:
        layer = self._find_layer(layer_name)
        if layer is None:
            return None
        tile = layer.setdefault("tiles", {}).get((int(x), int(y)))
        return copy.deepcopy(tile) if tile is not None else None

    def get_layer(self, layer_name: str) -> dict[str, Any] | None:
        layer = self._find_layer(layer_name)
        return self._copy_layer_without_runtime(layer) if layer is not None else None

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
        normalized_name = str(layer_name or self.default_layer_name).strip() or self.default_layer_name
        existing = self._find_layer(normalized_name)
        if existing is not None:
            return existing
        layer = TileLayerData(
            name=normalized_name,
            visible=bool(visible),
            opacity=float(max(0.0, min(1.0, opacity))),
            locked=bool(locked),
            offset_x=float(offset_x),
            offset_y=float(offset_y),
            collision_layer=max(0, int(collision_layer)),
            tilemap_source=normalize_asset_reference(tilemap_source) if tilemap_source else {},
            metadata=copy.deepcopy(metadata or {}),
        )
        payload = layer.to_runtime_dict()
        payload = self._normalize_layer_payload(payload)
        self.layers.append(payload)
        return payload

    def remove_layer(self, layer_name: str) -> bool:
        normalized_name = str(layer_name or "").strip()
        for index, layer in enumerate(self.layers):
            if layer.get("name") == normalized_name:
                self.layers.pop(index)
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
                    existing.update(copy.deepcopy(metadata))
                    layer["metadata"] = existing
                else:
                    layer["metadata"] = copy.deepcopy(metadata)
            else:
                layer["metadata"] = copy.deepcopy(metadata or {})
        self._mark_layer_chunks_dirty(layer)
        return True

    def resize(self, cell_width: int, cell_height: int, *, offset_x: int = 0, offset_y: int = 0) -> bool:
        self.cell_width = max(1, int(cell_width))
        self.cell_height = max(1, int(cell_height))
        self.metadata["grid_offset_x"] = int(offset_x)
        self.metadata["grid_offset_y"] = int(offset_y)
        self._mark_all_chunks_dirty()
        return True

    def to_dict(self) -> dict[str, Any]:
        return self._build_model_from_surface().to_component_payload(enabled=self.enabled)

    def iter_runtime_chunks(self, layer: dict[str, Any]) -> list[dict[str, Any]]:
        chunks = layer.get("_runtime_chunks", {})
        if not isinstance(chunks, dict):
            chunks = self._rebuild_layer_chunks(layer)
        return [
            chunk
            for _coord, chunk in sorted(chunks.items(), key=lambda item: (int(item[0][1]), int(item[0][0])))
            if isinstance(chunk, dict) and chunk.get("tiles")
        ]

    def iter_visible_runtime_chunks(
        self,
        layer: dict[str, Any],
        transform: Any,
        camera_bounds: tuple[float, float, float, float] | None,
    ) -> list[dict[str, Any]]:
        chunks = self.iter_runtime_chunks(layer)
        if camera_bounds is None:
            return chunks
        return [
            chunk
            for chunk in chunks
            if self._chunk_intersects_camera(layer, transform, chunk, camera_bounds)
        ]

    def get_runtime_chunk(self, layer_name: str, chunk_x: int, chunk_y: int) -> dict[str, Any] | None:
        layer = self._find_layer(layer_name)
        if layer is None:
            return None
        chunks = layer.get("_runtime_chunks", {})
        chunk = chunks.get((int(chunk_x), int(chunk_y))) if isinstance(chunks, dict) else None
        return chunk

    def mark_runtime_chunk_clean(self, layer: dict[str, Any], chunk_x: int, chunk_y: int, version: int | None = None) -> None:
        chunks = layer.get("_runtime_chunks", {})
        if not isinstance(chunks, dict):
            return
        chunk = chunks.get((int(chunk_x), int(chunk_y)))
        if not isinstance(chunk, dict):
            return
        if version is None or int(chunk.get("version", 0)) == int(version):
            chunk["dirty"] = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tilemap":
        model = TilemapData.from_payload(data)
        component = cls(
            cell_width=model.cell_width,
            cell_height=model.cell_height,
            orientation=model.orientation,
            tileset=model.get_tileset_reference(),
            tileset_path=model.tileset_path,
            layers=model.to_runtime_layers(),
            metadata=model.metadata,
            tileset_tile_width=model.tileset_tile_width,
            tileset_tile_height=model.tileset_tile_height,
            tileset_columns=model.tileset_columns,
            tileset_spacing=model.tileset_spacing,
            tileset_margin=model.tileset_margin,
            default_layer_name=model.default_layer_name,
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
        """Find existing layer or create new one with default properties."""
        layer = self._find_layer(layer_name)
        if layer is not None:
            return layer
        layer_payload = TileLayerData(name=str(layer_name or self.default_layer_name).strip() or self.default_layer_name)
        layer = self._normalize_layer_payload(layer_payload.to_runtime_dict())
        self.layers.append(layer)
        return layer

    def _build_model_from_surface(self) -> TilemapData:
        return TilemapData.from_payload(
            {
                "cell_width": self.cell_width,
                "cell_height": self.cell_height,
                "orientation": self.orientation,
                "tileset": self.tileset,
                "tileset_path": self.tileset_path,
                "layers": self._serialized_layers_payload(),
                "metadata": self.metadata,
                "tileset_tile_width": self.tileset_tile_width,
                "tileset_tile_height": self.tileset_tile_height,
                "tileset_columns": self.tileset_columns,
                "tileset_spacing": self.tileset_spacing,
                "tileset_margin": self.tileset_margin,
                "default_layer_name": self.default_layer_name,
            }
        )

    def _normalize_layers(self, layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_layers: list[dict[str, Any]] = []
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            normalized_layers.append(self._normalize_layer_payload(TileLayerData.from_payload(layer, index=index).to_runtime_dict()))
        return normalized_layers

    def _normalize_layer_payload(self, layer: dict[str, Any]) -> dict[str, Any]:
        payload = dict(layer)
        payload["tiles"] = self._normalize_tile_mapping(payload.get("tiles", {}))
        self._rebuild_layer_chunks(payload)
        return payload

    def _normalize_tile_mapping(self, raw_tiles: Any) -> dict[tuple[int, int], dict[str, Any]]:
        tiles: dict[tuple[int, int], dict[str, Any]] = {}
        if isinstance(raw_tiles, dict):
            for key, tile in raw_tiles.items():
                if not isinstance(tile, dict):
                    continue
                coord = self._coerce_tile_coord(key)
                if coord is not None:
                    tiles[coord] = copy.deepcopy(tile)
            return tiles
        if isinstance(raw_tiles, list):
            for tile in raw_tiles:
                if not isinstance(tile, dict):
                    continue
                try:
                    coord = (int(tile.get("x", 0)), int(tile.get("y", 0)))
                except (TypeError, ValueError):
                    continue
                payload = dict(tile)
                payload.pop("x", None)
                payload.pop("y", None)
                tiles[coord] = copy.deepcopy(payload)
        return tiles

    def _coerce_tile_coord(self, key: Any) -> tuple[int, int] | None:
        if isinstance(key, tuple) and len(key) == 2:
            try:
                return (int(key[0]), int(key[1]))
            except (TypeError, ValueError):
                return None
        try:
            x_value, y_value = str(key).split(",", 1)
            return (int(x_value), int(y_value))
        except (TypeError, ValueError):
            return None

    def _chunk_coord_for_tile(self, coord: tuple[int, int]) -> tuple[int, int]:
        return (int(coord[0]) // self.DEFAULT_CHUNK_SIZE, int(coord[1]) // self.DEFAULT_CHUNK_SIZE)

    def _chunk_intersects_camera(
        self,
        layer: dict[str, Any],
        transform: Any,
        chunk: dict[str, Any],
        camera_bounds: tuple[float, float, float, float],
    ) -> bool:
        chunk_bounds = self._chunk_world_bounds(layer, transform, chunk)
        return self._aabb_intersects(chunk_bounds, camera_bounds)

    def _chunk_world_bounds(self, layer: dict[str, Any], transform: Any, chunk: dict[str, Any]) -> tuple[float, float, float, float]:
        chunk_x, chunk_y = chunk.get("coord", (0, 0))
        layer_offset_x = float(layer.get("offset_x", 0.0))
        layer_offset_y = float(layer.get("offset_y", 0.0))
        left = (int(chunk_x) * self.DEFAULT_CHUNK_SIZE * float(self.cell_width)) + layer_offset_x
        top = (int(chunk_y) * self.DEFAULT_CHUNK_SIZE * float(self.cell_height)) + layer_offset_y
        right = left + (self.DEFAULT_CHUNK_SIZE * float(self.cell_width))
        bottom = top + (self.DEFAULT_CHUNK_SIZE * float(self.cell_height))
        scale_x = float(getattr(transform, "scale_x", 1.0))
        scale_y = float(getattr(transform, "scale_y", 1.0))
        world_x = float(getattr(transform, "x", 0.0))
        world_y = float(getattr(transform, "y", 0.0))
        scaled_left = left * scale_x
        scaled_right = right * scale_x
        scaled_top = top * scale_y
        scaled_bottom = bottom * scale_y
        world_left = world_x + min(scaled_left, scaled_right)
        world_right = world_x + max(scaled_left, scaled_right)
        world_top = world_y + min(scaled_top, scaled_bottom)
        world_bottom = world_y + max(scaled_top, scaled_bottom)
        return self._expand_bounds_for_rotation(world_left, world_top, world_right, world_bottom, float(getattr(transform, "rotation", 0.0)))

    def _expand_bounds_for_rotation(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        rotation: float,
    ) -> tuple[float, float, float, float]:
        if math.isclose(float(rotation) % 360.0, 0.0, abs_tol=1e-6):
            return (float(left), float(top), float(right), float(bottom))
        center_x = (left + right) * 0.5
        center_y = (top + bottom) * 0.5
        half_extent = math.hypot(right - left, bottom - top) * 0.5
        return (
            center_x - half_extent,
            center_y - half_extent,
            center_x + half_extent,
            center_y + half_extent,
        )

    def _aabb_intersects(
        self,
        bounds: tuple[float, float, float, float],
        query_bounds: tuple[float, float, float, float],
    ) -> bool:
        left, top, right, bottom = bounds
        query_left, query_top, query_right, query_bottom = query_bounds
        return left < query_right and right > query_left and top < query_bottom and bottom > query_top

    def _rebuild_layer_chunks(self, layer: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
        chunks: dict[tuple[int, int], dict[str, Any]] = {}
        for coord, tile in layer.get("tiles", {}).items():
            normalized_coord = self._coerce_tile_coord(coord)
            if normalized_coord is None:
                continue
            chunk_coord = self._chunk_coord_for_tile(normalized_coord)
            chunk = chunks.setdefault(chunk_coord, {"coord": chunk_coord, "tiles": {}, "version": 0, "dirty": True})
            chunk["tiles"][normalized_coord] = tile
        layer["_runtime_chunks"] = chunks
        return chunks

    def _set_chunk_tile(self, layer: dict[str, Any], coord: tuple[int, int]) -> None:
        chunks = layer.setdefault("_runtime_chunks", {})
        chunk_coord = self._chunk_coord_for_tile(coord)
        chunk = chunks.setdefault(chunk_coord, {"coord": chunk_coord, "tiles": {}, "version": 0, "dirty": False})
        chunk["tiles"][coord] = layer.setdefault("tiles", {})[coord]
        self._mark_chunk_dirty(chunk)

    def _clear_chunk_tile(self, layer: dict[str, Any], coord: tuple[int, int]) -> None:
        chunks = layer.setdefault("_runtime_chunks", {})
        chunk_coord = self._chunk_coord_for_tile(coord)
        chunk = chunks.setdefault(chunk_coord, {"coord": chunk_coord, "tiles": {}, "version": 0, "dirty": False})
        chunk.setdefault("tiles", {}).pop(coord, None)
        self._mark_chunk_dirty(chunk)

    def _mark_chunk_dirty(self, chunk: dict[str, Any]) -> None:
        chunk["version"] = int(chunk.get("version", 0)) + 1
        chunk["dirty"] = True

    def _mark_layer_chunks_dirty(self, layer: dict[str, Any]) -> None:
        chunks = layer.get("_runtime_chunks", {})
        if not isinstance(chunks, dict):
            chunks = self._rebuild_layer_chunks(layer)
        for chunk in chunks.values():
            if isinstance(chunk, dict):
                self._mark_chunk_dirty(chunk)

    def _mark_all_chunks_dirty(self) -> None:
        for layer in self.layers:
            self._mark_layer_chunks_dirty(layer)

    def _serialized_layers_payload(self) -> list[dict[str, Any]]:
        layers: list[dict[str, Any]] = []
        for layer in self.layers:
            payload = self._copy_layer_without_runtime(layer)
            tiles = []
            raw_tiles = self._normalize_tile_mapping(payload.get("tiles", {}))
            for coord in sorted(raw_tiles, key=lambda item: (item[1], item[0])):
                tile_payload = copy.deepcopy(raw_tiles[coord])
                tile_payload["x"] = int(coord[0])
                tile_payload["y"] = int(coord[1])
                tiles.append(tile_payload)
            payload["tiles"] = tiles
            layers.append(payload)
        return layers

    def _copy_layer_without_runtime(self, layer: dict[str, Any]) -> dict[str, Any]:
        return {key: copy.deepcopy(value) for key, value in layer.items() if not str(key).startswith("_runtime_")}

    def _build_tile_payload(
        self,
        tile_id: str,
        *,
        source: Any = None,
        flags: list[str] | None = None,
        tags: list[str] | None = None,
        custom: dict[str, Any] | None = None,
        animated: bool = False,
        animation_id: str = "",
        terrain_type: str = "",
    ) -> dict[str, Any]:
        return TileData(
            tile_id=str(tile_id),
            source=normalize_asset_reference(source),
            flags=[str(item) for item in (flags or []) if str(item).strip()],
            tags=[str(item) for item in (tags or []) if str(item).strip()],
            custom=copy.deepcopy(custom or {}) if isinstance(custom or {}, dict) else {},
            animated=bool(animated),
            animation_id=str(animation_id or "").strip(),
            terrain_type=str(terrain_type or "").strip(),
        ).to_runtime_dict()
