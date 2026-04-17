from __future__ import annotations

import importlib

_EXPORTS = {
    "RUNTIME_TILE_COLLIDER_PREFIX": ("engine.tilemap.collision_builder", "RUNTIME_TILE_COLLIDER_PREFIX"),
    "bake_tilemap_colliders": ("engine.tilemap.collision_builder", "bake_tilemap_colliders"),
    "build_tilemap_collision_regions": ("engine.tilemap.collision_builder", "build_tilemap_collision_regions"),
    "TileCoord": ("engine.tilemap.model", "TileCoord"),
    "TileData": ("engine.tilemap.model", "TileData"),
    "TileLayerData": ("engine.tilemap.model", "TileLayerData"),
    "TilemapData": ("engine.tilemap.model", "TilemapData"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value
