from __future__ import annotations

import copy
from typing import Any

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component


class Tilemap(Component):
    """Tilemap serializable con layers, tileset y metadata por tile."""

    VALID_ORIENTATIONS = {"orthogonal"}

    def __init__(
        self,
        cell_width: int = 16,
        cell_height: int = 16,
        orientation: str = "orthogonal",
        tileset: Any = None,
        tileset_path: str = "",
        layers: list[dict[str, Any]] | None = None,
    ) -> None:
        self.enabled: bool = True
        self.cell_width: int = max(1, int(cell_width))
        self.cell_height: int = max(1, int(cell_height))
        normalized_orientation = str(orientation or "orthogonal")
        self.orientation: str = normalized_orientation if normalized_orientation in self.VALID_ORIENTATIONS else "orthogonal"
        self.tileset = normalize_asset_reference(tileset if tileset is not None else tileset_path)
        self.tileset_path: str = self.tileset.get("path", "")
        self.layers: list[dict[str, Any]] = self._normalize_layers(layers or [])

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
    ) -> None:
        layer = self._ensure_layer(layer_name)
        key = f"{int(x)},{int(y)}"
        tiles = layer.setdefault("tiles", {})
        tiles[key] = {
            "tile_id": str(tile_id),
            "source": normalize_asset_reference(source),
            "flags": [str(item) for item in (flags or []) if str(item).strip()],
            "tags": [str(item) for item in (tags or []) if str(item).strip()],
            "custom": copy.deepcopy(custom or {}),
        }

    def clear_tile(self, layer_name: str, x: int, y: int) -> None:
        layer = self._ensure_layer(layer_name)
        layer.setdefault("tiles", {}).pop(f"{int(x)},{int(y)}", None)

    def get_tile(self, layer_name: str, x: int, y: int) -> dict[str, Any] | None:
        layer = self._find_layer(layer_name)
        if layer is None:
            return None
        tile = layer.setdefault("tiles", {}).get(f"{int(x)},{int(y)}")
        return copy.deepcopy(tile) if tile is not None else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cell_width": self.cell_width,
            "cell_height": self.cell_height,
            "orientation": self.orientation,
            "tileset": self.get_tileset_reference(),
            "tileset_path": self.tileset_path,
            "layers": self._serialize_layers(),
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
            tileset=tileset_ref,
            tileset_path=tileset_path,
            layers=data.get("layers", []),
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
        layer = self._find_layer(layer_name)
        if layer is not None:
            return layer
        layer = {
            "name": str(layer_name or "Layer"),
            "visible": True,
            "opacity": 1.0,
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
                    tiles_map[key] = {
                        "tile_id": str(tile.get("tile_id", "")),
                        "source": normalize_asset_reference(tile.get("source")),
                        "flags": [str(item) for item in tile.get("flags", []) if str(item).strip()],
                        "tags": [str(item) for item in tile.get("tags", []) if str(item).strip()],
                        "custom": copy.deepcopy(tile.get("custom", {})) if isinstance(tile.get("custom", {}), dict) else {},
                    }
            elif isinstance(raw_tiles, dict):
                for key, tile in raw_tiles.items():
                    if not isinstance(tile, dict):
                        continue
                    tiles_map[str(key)] = {
                        "tile_id": str(tile.get("tile_id", "")),
                        "source": normalize_asset_reference(tile.get("source")),
                        "flags": [str(item) for item in tile.get("flags", []) if str(item).strip()],
                        "tags": [str(item) for item in tile.get("tags", []) if str(item).strip()],
                        "custom": copy.deepcopy(tile.get("custom", {})) if isinstance(tile.get("custom", {}), dict) else {},
                    }
            normalized_layers.append(
                {
                    "name": layer_name,
                    "visible": bool(layer.get("visible", True)),
                    "opacity": float(layer.get("opacity", 1.0)),
                    "metadata": copy.deepcopy(layer.get("metadata", {})) if isinstance(layer.get("metadata", {}), dict) else {},
                    "tiles": tiles_map,
                }
            )
        return normalized_layers

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
                    }
                )
            serialized.append(
                {
                    "name": str(layer.get("name", "Layer")),
                    "visible": bool(layer.get("visible", True)),
                    "opacity": float(layer.get("opacity", 1.0)),
                    "metadata": copy.deepcopy(layer.get("metadata", {})),
                    "tiles": tiles_payload,
                }
            )
        return serialized
