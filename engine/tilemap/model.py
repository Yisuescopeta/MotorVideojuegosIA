from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference


def _clamp_opacity(value: Any) -> float:
    return float(max(0.0, min(1.0, float(value))))


def _clone_metadata(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def _normalize_string_items(values: Any) -> list[str]:
    return [text for text in (str(item).strip() for item in (values or [])) if text]


@dataclass(frozen=True, order=True)
class TileCoord:
    x: int
    y: int

    @classmethod
    def from_values(cls, x: Any, y: Any) -> "TileCoord":
        return cls(int(x), int(y))

    @classmethod
    def from_key(cls, key: Any) -> "TileCoord":
        x_value, y_value = str(key).split(",", 1)
        return cls(int(x_value), int(y_value))

    def to_key(self) -> str:
        return f"{self.x},{self.y}"


@dataclass
class TileData:
    tile_id: str = ""
    source: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)
    animated: bool = False
    animation_id: str = ""
    terrain_type: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TileData":
        return cls(
            tile_id=str(payload.get("tile_id", "")),
            source=normalize_asset_reference(payload.get("source")),
            flags=_normalize_string_items(payload.get("flags", [])),
            tags=_normalize_string_items(payload.get("tags", [])),
            custom=_clone_metadata(payload.get("custom", {})),
            animated=bool(payload.get("animated", False)),
            animation_id=str(payload.get("animation_id", "")).strip(),
            terrain_type=str(payload.get("terrain_type", "")).strip(),
        )

    def to_runtime_dict(self) -> dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "source": clone_asset_reference(self.source),
            "flags": list(self.flags),
            "tags": list(self.tags),
            "custom": copy.deepcopy(self.custom),
            "animated": bool(self.animated),
            "animation_id": self.animation_id,
            "terrain_type": self.terrain_type,
        }

    def to_serialized_payload(self, coord: TileCoord) -> dict[str, Any]:
        payload = self.to_runtime_dict()
        payload["x"] = coord.x
        payload["y"] = coord.y
        return payload


@dataclass
class TileLayerData:
    name: str
    visible: bool = True
    opacity: float = 1.0
    locked: bool = False
    offset_x: float = 0.0
    offset_y: float = 0.0
    collision_layer: int = 0
    tilemap_source: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    tiles: dict[TileCoord, TileData] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any], *, index: int = 0) -> "TileLayerData":
        tiles: dict[TileCoord, TileData] = {}
        raw_tiles = payload.get("tiles", {})
        if isinstance(raw_tiles, list):
            for raw_tile in raw_tiles:
                if not isinstance(raw_tile, dict):
                    continue
                coord = TileCoord.from_values(raw_tile.get("x", 0), raw_tile.get("y", 0))
                tiles[coord] = TileData.from_payload(raw_tile)
        elif isinstance(raw_tiles, dict):
            for key, raw_tile in raw_tiles.items():
                if not isinstance(raw_tile, dict):
                    continue
                try:
                    coord = TileCoord.from_key(key)
                except (TypeError, ValueError):
                    continue
                tiles[coord] = TileData.from_payload(raw_tile)
        return cls(
            name=str(payload.get("name") or f"Layer_{index}"),
            visible=bool(payload.get("visible", True)),
            opacity=_clamp_opacity(payload.get("opacity", 1.0)),
            locked=bool(payload.get("locked", False)),
            offset_x=float(payload.get("offset_x", 0.0)),
            offset_y=float(payload.get("offset_y", 0.0)),
            collision_layer=max(0, int(payload.get("collision_layer", 0))),
            tilemap_source=normalize_asset_reference(payload.get("tilemap_source")),
            metadata=_clone_metadata(payload.get("metadata", {})),
            tiles=tiles,
        )

    def get_tile(self, coord: TileCoord) -> TileData | None:
        return self.tiles.get(coord)

    def set_tile(self, coord: TileCoord, tile: TileData) -> None:
        self.tiles[coord] = tile

    def clear_tile(self, coord: TileCoord) -> None:
        self.tiles.pop(coord, None)

    def merge_metadata(self, metadata: Any) -> None:
        if isinstance(metadata, dict):
            self.metadata.update(copy.deepcopy(metadata))
        else:
            self.metadata = _clone_metadata(metadata or {})

    def to_runtime_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "visible": bool(self.visible),
            "opacity": float(self.opacity),
            "locked": bool(self.locked),
            "offset_x": float(self.offset_x),
            "offset_y": float(self.offset_y),
            "collision_layer": max(0, int(self.collision_layer)),
            "tilemap_source": clone_asset_reference(self.tilemap_source),
            "metadata": copy.deepcopy(self.metadata),
            "tiles": {coord.to_key(): tile.to_runtime_dict() for coord, tile in self.tiles.items()},
        }

    def to_serialized_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "visible": bool(self.visible),
            "opacity": float(self.opacity),
            "locked": bool(self.locked),
            "offset_x": float(self.offset_x),
            "offset_y": float(self.offset_y),
            "collision_layer": max(0, int(self.collision_layer)),
            "tilemap_source": clone_asset_reference(self.tilemap_source),
            "metadata": copy.deepcopy(self.metadata),
            "tiles": [self.tiles[coord].to_serialized_payload(coord) for coord in sorted(self.tiles)],
        }


@dataclass
class TilemapData:
    cell_width: int = 16
    cell_height: int = 16
    orientation: str = "orthogonal"
    tileset: dict[str, str] = field(default_factory=dict)
    tileset_path: str = ""
    layers: list[TileLayerData] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tileset_tile_width: int = 16
    tileset_tile_height: int = 16
    tileset_columns: int = 0
    tileset_spacing: int = 0
    tileset_margin: int = 0
    default_layer_name: str = "Layer"

    VALID_ORIENTATIONS = {"orthogonal"}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TilemapData":
        tileset_ref = normalize_asset_reference(payload.get("tileset"))
        tileset_path = str(payload.get("tileset_path", "") or "")
        if tileset_path and tileset_ref.get("path") != tileset_path:
            tileset_ref = build_asset_reference(tileset_path, tileset_ref.get("guid", ""))
        raw_layers = payload.get("layers", [])
        layers = [
            TileLayerData.from_payload(layer, index=index)
            for index, layer in enumerate(raw_layers)
            if isinstance(layer, dict)
        ]
        orientation = str(payload.get("orientation", "orthogonal") or "orthogonal")
        normalized_orientation = orientation if orientation in cls.VALID_ORIENTATIONS else "orthogonal"
        return cls(
            cell_width=max(1, int(payload.get("cell_width", 16))),
            cell_height=max(1, int(payload.get("cell_height", 16))),
            orientation=normalized_orientation,
            tileset=tileset_ref,
            tileset_path=tileset_ref.get("path", ""),
            layers=layers,
            metadata=_clone_metadata(payload.get("metadata", {})),
            tileset_tile_width=max(1, int(payload.get("tileset_tile_width", 16))),
            tileset_tile_height=max(1, int(payload.get("tileset_tile_height", 16))),
            tileset_columns=max(0, int(payload.get("tileset_columns", 0))),
            tileset_spacing=max(0, int(payload.get("tileset_spacing", 0))),
            tileset_margin=max(0, int(payload.get("tileset_margin", 0))),
            default_layer_name=str(payload.get("default_layer_name", "Layer") or "Layer").strip() or "Layer",
        )

    def get_tileset_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.tileset)

    def sync_tileset_reference(self, reference: Any) -> None:
        self.tileset = normalize_asset_reference(reference)
        self.tileset_path = self.tileset.get("path", "")

    def find_layer(self, layer_name: str) -> TileLayerData | None:
        normalized_name = str(layer_name or "").strip()
        for layer in self.layers:
            if layer.name == normalized_name:
                return layer
        return None

    def ensure_layer(self, layer_name: str) -> TileLayerData:
        layer = self.find_layer(layer_name)
        if layer is not None:
            return layer
        normalized_name = str(layer_name or self.default_layer_name).strip() or self.default_layer_name
        layer = TileLayerData(name=normalized_name)
        self.layers.append(layer)
        return layer

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
    ) -> TileLayerData:
        normalized_name = str(layer_name or self.default_layer_name).strip() or self.default_layer_name
        existing = self.find_layer(normalized_name)
        if existing is not None:
            return existing
        layer = TileLayerData(
            name=normalized_name,
            visible=bool(visible),
            opacity=_clamp_opacity(opacity),
            locked=bool(locked),
            offset_x=float(offset_x),
            offset_y=float(offset_y),
            collision_layer=max(0, int(collision_layer)),
            tilemap_source=normalize_asset_reference(tilemap_source) if tilemap_source else {},
            metadata=_clone_metadata(metadata or {}),
        )
        self.layers.append(layer)
        return layer

    def remove_layer(self, layer_name: str) -> bool:
        normalized_name = str(layer_name or "").strip()
        for index, layer in enumerate(self.layers):
            if layer.name == normalized_name:
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
        layer = self.find_layer(layer_name)
        if layer is None:
            return False
        if visible is not None:
            layer.visible = bool(visible)
        if opacity is not None:
            layer.opacity = _clamp_opacity(opacity)
        if locked is not None:
            layer.locked = bool(locked)
        if offset_x is not None:
            layer.offset_x = float(offset_x)
        if offset_y is not None:
            layer.offset_y = float(offset_y)
        if collision_layer is not None:
            layer.collision_layer = max(0, int(collision_layer))
        if tilemap_source is not None:
            layer.tilemap_source = normalize_asset_reference(tilemap_source)
        if metadata is not None:
            layer.merge_metadata(metadata)
        return True

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
        layer = self.ensure_layer(layer_name) if create_layer else self.find_layer(layer_name)
        if layer is None:
            raise ValueError(f"Layer '{layer_name}' does not exist and create_layer=False")
        layer.set_tile(
            TileCoord.from_values(x, y),
            TileData(
                tile_id=str(tile_id),
                source=normalize_asset_reference(source),
                flags=_normalize_string_items(flags or []),
                tags=_normalize_string_items(tags or []),
                custom=_clone_metadata(custom or {}),
                animated=bool(animated),
                animation_id=str(animation_id or "").strip(),
                terrain_type=str(terrain_type or "").strip(),
            ),
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
        count = 0
        for y_value in range(int(y_start), int(y_end) + 1):
            for x_value in range(int(x_start), int(x_end) + 1):
                self.set_tile(
                    layer_name,
                    x_value,
                    y_value,
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
                count += 1
        return count

    def clear_tile(self, layer_name: str, x: int, y: int, *, create_layer: bool = True) -> None:
        layer = self.ensure_layer(layer_name) if create_layer else self.find_layer(layer_name)
        if layer is None:
            raise ValueError(f"Layer '{layer_name}' does not exist and create_layer=False")
        layer.clear_tile(TileCoord.from_values(x, y))

    def get_tile_payload(self, layer_name: str, x: int, y: int) -> dict[str, Any] | None:
        layer = self.find_layer(layer_name)
        if layer is None:
            return None
        tile = layer.get_tile(TileCoord.from_values(x, y))
        return tile.to_runtime_dict() if tile is not None else None

    def get_layer_payload(self, layer_name: str) -> dict[str, Any] | None:
        layer = self.find_layer(layer_name)
        return layer.to_runtime_dict() if layer is not None else None

    def resize(self, cell_width: int, cell_height: int, *, offset_x: int = 0, offset_y: int = 0) -> bool:
        self.cell_width = max(1, int(cell_width))
        self.cell_height = max(1, int(cell_height))
        self.metadata["grid_offset_x"] = int(offset_x)
        self.metadata["grid_offset_y"] = int(offset_y)
        return True

    def to_runtime_layers(self) -> list[dict[str, Any]]:
        return [layer.to_runtime_dict() for layer in self.layers]

    def to_component_payload(self, *, enabled: bool = True) -> dict[str, Any]:
        return {
            "enabled": bool(enabled),
            "cell_width": self.cell_width,
            "cell_height": self.cell_height,
            "orientation": self.orientation,
            "tileset": self.get_tileset_reference(),
            "tileset_path": self.tileset_path,
            "layers": [layer.to_serialized_payload() for layer in self.layers],
            "metadata": copy.deepcopy(self.metadata),
            "tileset_tile_width": self.tileset_tile_width,
            "tileset_tile_height": self.tileset_tile_height,
            "tileset_columns": self.tileset_columns,
            "tileset_spacing": self.tileset_spacing,
            "tileset_margin": self.tileset_margin,
            "default_layer_name": self.default_layer_name,
        }
