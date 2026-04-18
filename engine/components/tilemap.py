from __future__ import annotations

import copy
from typing import Any

from engine.assets.asset_reference import clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component
from engine.tilemap.model import TileData, TileLayerData, TilemapData


class Tilemap(Component):
    """Tilemap serializable con base incremental para evolucion futura."""

    VALID_ORIENTATIONS = {"orthogonal"}

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
        layer.setdefault("tiles", {})[f"{int(x)},{int(y)}"] = self._build_tile_payload(
            tile_id,
            source=source,
            flags=flags,
            tags=tags,
            custom=custom,
            animated=animated,
            animation_id=animation_id,
            terrain_type=terrain_type,
        )

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
                tiles[f"{x_value},{y_value}"] = copy.deepcopy(tile_payload)
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
        return True

    def resize(self, cell_width: int, cell_height: int, *, offset_x: int = 0, offset_y: int = 0) -> bool:
        self.cell_width = max(1, int(cell_width))
        self.cell_height = max(1, int(cell_height))
        self.metadata["grid_offset_x"] = int(offset_x)
        self.metadata["grid_offset_y"] = int(offset_y)
        return True

    def to_dict(self) -> dict[str, Any]:
        return self._build_model_from_surface().to_component_payload(enabled=self.enabled)

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
        layer = layer_payload.to_runtime_dict()
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
                "layers": self.layers,
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
            normalized_layers.append(TileLayerData.from_payload(layer, index=index).to_runtime_dict())
        return normalized_layers

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
