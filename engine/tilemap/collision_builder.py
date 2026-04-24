from __future__ import annotations

import time
from typing import Any

from engine.components.collider import Collider
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform


RUNTIME_TILE_COLLIDER_PREFIX = "__tilecollider__"


def bake_tilemap_colliders(world: Any, *, merge_shapes: bool = True) -> dict[str, Any]:
    _clear_runtime_tile_colliders(world)
    started = time.perf_counter()
    tile_count = 0
    region_count = 0
    generated_entities = 0

    for entity in world.get_entities_with(Transform, Tilemap):
        transform = entity.get_component(Transform)
        tilemap = entity.get_component(Tilemap)
        if transform is None or tilemap is None or not tilemap.enabled:
            continue
        regions = build_tilemap_collision_regions(tilemap, merge_shapes=merge_shapes)
        tile_count += sum(len(layer.get("tiles", {})) for layer in tilemap.layers)
        region_count += len(regions)
        for index, region in enumerate(regions):
            collider_entity = world.create_entity(f"{RUNTIME_TILE_COLLIDER_PREFIX}{entity.name}_{index}")
            collider_entity.tag = "TilemapCollision"
            collider_entity.layer = entity.layer
            collider_entity.add_component(
                Transform(
                    x=float(transform.x) + float(region["center_x"]),
                    y=float(transform.y) + float(region["center_y"]),
                    rotation=0.0,
                    scale_x=1.0,
                    scale_y=1.0,
                )
            )
            collider_entity.add_component(
                Collider(
                    width=float(region["width"]),
                    height=float(region["height"]),
                    offset_x=0.0,
                    offset_y=0.0,
                    is_trigger=False,
                ),
                metadata={"runtime_generated": "tilemap_collision", "source_tilemap": entity.name},
            )
            generated_entities += 1

    return {
        "tile_count": tile_count,
        "region_count": region_count,
        "generated_entities": generated_entities,
        "merge_shapes": bool(merge_shapes),
        "duration_ms": (time.perf_counter() - started) * 1000.0,
    }


def build_tilemap_collision_regions(tilemap: Tilemap, *, merge_shapes: bool = True) -> list[dict[str, float]]:
    solid_cells: set[tuple[int, int]] = set()
    for layer in tilemap.layers:
        for key, tile in layer.get("tiles", {}).items():
            if not _tile_is_solid(tile):
                continue
            if isinstance(key, tuple) and len(key) == 2:
                solid_cells.add((int(key[0]), int(key[1])))
            else:
                x_value, y_value = str(key).split(",", 1)
                solid_cells.add((int(x_value), int(y_value)))
    if not solid_cells:
        return []
    if not merge_shapes:
        return [
            _cell_to_region(tilemap, x, y, width_cells=1, height_cells=1)
            for x, y in sorted(solid_cells, key=lambda item: (item[1], item[0]))
        ]
    rectangles = _merge_cells_to_rectangles(solid_cells)
    return [
        _cell_to_region(tilemap, rect["x"], rect["y"], width_cells=rect["width_cells"], height_cells=rect["height_cells"])
        for rect in rectangles
    ]


def _tile_is_solid(tile: dict[str, Any]) -> bool:
    flags = {str(item).strip().lower() for item in tile.get("flags", [])}
    tags = {str(item).strip().lower() for item in tile.get("tags", [])}
    custom = tile.get("custom", {})
    if "solid" in flags or "solid" in tags:
        return True
    if isinstance(custom, dict):
        if bool(custom.get("collision", False)):
            return True
        shape = str(custom.get("collision_shape", "")).strip().lower()
        if shape in {"grid", "box", "solid"}:
            return True
    return False


def _merge_cells_to_rectangles(solid_cells: set[tuple[int, int]]) -> list[dict[str, int]]:
    remaining = set(solid_cells)
    rectangles: list[dict[str, int]] = []
    while remaining:
        start_x, start_y = min(remaining, key=lambda item: (item[1], item[0]))
        width_cells = 1
        while (start_x + width_cells, start_y) in remaining:
            width_cells += 1
        height_cells = 1
        growing = True
        while growing:
            next_row = start_y + height_cells
            growing = all((start_x + offset, next_row) in remaining for offset in range(width_cells))
            if growing:
                height_cells += 1
        for offset_y in range(height_cells):
            for offset_x in range(width_cells):
                remaining.discard((start_x + offset_x, start_y + offset_y))
        rectangles.append(
            {
                "x": start_x,
                "y": start_y,
                "width_cells": width_cells,
                "height_cells": height_cells,
            }
        )
    return rectangles


def _cell_to_region(tilemap: Tilemap, x: int, y: int, *, width_cells: int, height_cells: int) -> dict[str, float]:
    width = float(width_cells * tilemap.cell_width)
    height = float(height_cells * tilemap.cell_height)
    center_x = float(x * tilemap.cell_width) + width / 2.0
    center_y = float(y * tilemap.cell_height) + height / 2.0
    return {
        "center_x": center_x,
        "center_y": center_y,
        "width": width,
        "height": height,
    }


def _clear_runtime_tile_colliders(world: Any) -> None:
    for entity in list(world.get_all_entities()):
        if str(entity.name).startswith(RUNTIME_TILE_COLLIDER_PREFIX):
            world.remove_entity(entity.id)
