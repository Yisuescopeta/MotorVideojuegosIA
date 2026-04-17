from __future__ import annotations

import copy
from typing import Any

from engine.assets.asset_reference import normalize_asset_reference
from engine.ecs.component import Component
from engine.tilemap.model import TilemapData


class Tilemap(Component):
    """Tilemap serializable con dominio interno estable para futuras extensiones."""

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
        self.cell_width: int = int(cell_width)
        self.cell_height: int = int(cell_height)
        self.orientation: str = str(orientation or "orthogonal")
        self.tileset = normalize_asset_reference(tileset if tileset is not None else tileset_path)
        self.tileset_path: str = str(tileset_path or self.tileset.get("path", ""))
        self.layers: list[dict[str, Any]] = copy.deepcopy(layers or [])
        self.metadata: dict[str, Any] = copy.deepcopy(metadata or {})
        self.tileset_tile_width: int = int(tileset_tile_width)
        self.tileset_tile_height: int = int(tileset_tile_height)
        self.tileset_columns: int = int(tileset_columns)
        self.tileset_spacing: int = int(tileset_spacing)
        self.tileset_margin: int = int(tileset_margin)
        self.default_layer_name: str = str(default_layer_name or "Layer")
        self._model = TilemapData.from_payload(self._surface_payload())
        self._apply_model()

    def get_tileset_reference(self) -> dict[str, str]:
        self._sync_model_from_surface()
        return self._model.get_tileset_reference()

    def sync_tileset_reference(self, reference: Any) -> None:
        self._sync_model_from_surface()
        self._model.sync_tileset_reference(reference)
        self._apply_model()

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
        self._sync_model_from_surface()
        self._model.set_tile(
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
        self._apply_model()

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
        self._sync_model_from_surface()
        count = self._model.fill_rect(
            layer_name,
            x_start,
            y_start,
            x_end,
            y_end,
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
        self._apply_model()
        return count

    def clear_tile(self, layer_name: str, x: int, y: int, create_layer: bool = True) -> None:
        self._sync_model_from_surface()
        self._model.clear_tile(layer_name, x, y, create_layer=create_layer)
        self._apply_model()

    def get_tile(self, layer_name: str, x: int, y: int) -> dict[str, Any] | None:
        self._sync_model_from_surface()
        tile = self._model.get_tile_payload(layer_name, x, y)
        return copy.deepcopy(tile) if tile is not None else None

    def get_layer(self, layer_name: str) -> dict[str, Any] | None:
        self._sync_model_from_surface()
        layer = self._model.get_layer_payload(layer_name)
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
        self._sync_model_from_surface()
        layer = self._model.add_layer(
            layer_name,
            visible=visible,
            opacity=opacity,
            locked=locked,
            offset_x=offset_x,
            offset_y=offset_y,
            collision_layer=collision_layer,
            tilemap_source=tilemap_source,
            metadata=metadata,
        )
        self._apply_model()
        return copy.deepcopy(layer.to_runtime_dict())

    def remove_layer(self, layer_name: str) -> bool:
        self._sync_model_from_surface()
        removed = self._model.remove_layer(layer_name)
        self._apply_model()
        return removed

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
        self._sync_model_from_surface()
        updated = self._model.set_layer_properties(
            layer_name,
            visible=visible,
            opacity=opacity,
            locked=locked,
            offset_x=offset_x,
            offset_y=offset_y,
            collision_layer=collision_layer,
            tilemap_source=tilemap_source,
            metadata=metadata,
        )
        self._apply_model()
        return updated

    def resize(self, cell_width: int, cell_height: int, *, offset_x: int = 0, offset_y: int = 0) -> bool:
        self._sync_model_from_surface()
        resized = self._model.resize(cell_width, cell_height, offset_x=offset_x, offset_y=offset_y)
        self._apply_model()
        return resized

    def to_dict(self) -> dict[str, Any]:
        self._sync_model_from_surface()
        return self._model.to_component_payload(enabled=self.enabled)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tilemap":
        component = cls(
            cell_width=data.get("cell_width", 16),
            cell_height=data.get("cell_height", 16),
            orientation=data.get("orientation", "orthogonal"),
            tileset=data.get("tileset"),
            tileset_path=data.get("tileset_path", ""),
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
        return self.get_layer(layer_name)

    def _ensure_layer(self, layer_name: str) -> dict[str, Any]:
        """Find existing layer or create new one with default properties.

        WARNING: This method performs implicit layer creation (autovivification).
        This can hide bugs when typos in layer names create phantom layers.
        Use create_layer=False in set_tile/fill_rect/clear_tile to disable.
        """
        self._sync_model_from_surface()
        layer = self._model.ensure_layer(layer_name)
        self._apply_model()
        return copy.deepcopy(layer.to_runtime_dict())

    def _surface_payload(self) -> dict[str, Any]:
        return {
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

    def _sync_model_from_surface(self) -> None:
        self._model = TilemapData.from_payload(self._surface_payload())

    def _apply_model(self) -> None:
        self.cell_width = self._model.cell_width
        self.cell_height = self._model.cell_height
        self.orientation = self._model.orientation
        self.tileset = self._model.get_tileset_reference()
        self.tileset_path = self._model.tileset_path
        self.layers = self._model.to_runtime_layers()
        self.metadata = copy.deepcopy(self._model.metadata)
        self.tileset_tile_width = self._model.tileset_tile_width
        self.tileset_tile_height = self._model.tileset_tile_height
        self.tileset_columns = self._model.tileset_columns
        self.tileset_spacing = self._model.tileset_spacing
        self.tileset_margin = self._model.tileset_margin
        self.default_layer_name = self._model.default_layer_name
