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
        tileset_res = tilemap.get_tileset_resource() if hasattr(tilemap, 'get_tileset_resource') else None
        regions = build_tilemap_collision_regions(tilemap, merge_shapes=merge_shapes, tileset_resource=tileset_res)
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


def build_tilemap_collision_regions(
    tilemap: Tilemap,
    *,
    merge_shapes: bool = True,
    tileset_resource: Any = None,
) -> list[dict[str, float]]:
    solid_cells: set[tuple[int, int]] = set()
    per_tile_shapes: dict[tuple[int, int], list[dict[str, float]]] = {}
    for layer in tilemap.layers:
        for key, tile in layer.get("tiles", {}).items():
            if isinstance(key, tuple) and len(key) == 2:
                coord = (int(key[0]), int(key[1]))
            else:
                x_value, y_value = str(key).split(",", 1)
                coord = (int(x_value), int(y_value))
            # Check per-tile physics shapes from TileSet resource
            custom_shapes = _resolve_per_tile_physics(tilemap, tile, coord, tileset_resource)
            if custom_shapes:
                per_tile_shapes[coord] = custom_shapes
            elif _tile_is_solid(tile):
                solid_cells.add(coord)
    regions: list[dict[str, float]] = []
    # Add per-tile custom shapes (these use local coords within tile cell)
    for coord, shapes in per_tile_shapes.items():
        for shape in shapes:
            shape_center_x = float(coord[0] * tilemap.cell_width) + shape.get("center_x", 0)
            shape_center_y = float(coord[1] * tilemap.cell_height) + shape.get("center_y", 0)
            regions.append({
                "center_x": shape_center_x,
                "center_y": shape_center_y,
                "width": shape.get("width", float(tilemap.cell_width)),
                "height": shape.get("height", float(tilemap.cell_height)),
            })
    # Add merged solid cells (grid-aligned only)
    if solid_cells:
        if not merge_shapes:
            regions.extend(
                _cell_to_region(tilemap, x, y, width_cells=1, height_cells=1)
                for x, y in sorted(solid_cells, key=lambda item: (item[1], item[0]))
            )
        else:
            rectangles = _merge_cells_to_rectangles(solid_cells)
            regions.extend(
                _cell_to_region(tilemap, rect["x"], rect["y"], width_cells=rect["width_cells"], height_cells=rect["height_cells"])
                for rect in rectangles
            )
    return regions


def _resolve_per_tile_physics(
    tilemap: Tilemap,
    tile: dict[str, Any],
    coord: tuple[int, int],
    tileset_resource: Any,
) -> list[dict[str, float]]:
    """Resolve per-tile physics shapes from TileSet resource metadata.

    Returns list of {center_x, center_y, width, height} in local tile coords.
    Empty list means no custom physics — use default grid collision.
    """
    if tileset_resource is None:
        return []
    tile_id = str(tile.get("tile_id", ""))
    if not tile_id:
        return []
    # Determine source_id from tile_id (format: source_col_row)
    parts = tile_id.rsplit("_", 2)
    if len(parts) < 3:
        parts = tile_id.split("_", 1)
        if len(parts) < 2:
            return []
        source_id = parts[0]
    else:
        source_id = parts[0]
    meta = tileset_resource.get_tile_metadata(source_id, tile_id)
    if meta is None or not meta.physics_layers:
        return []
    shapes: list[dict[str, float]] = []
    for phys_shape in meta.physics_layers:
        if phys_shape.shape_type == "box":
            if phys_shape.points and len(phys_shape.points) >= 2:
                p1 = phys_shape.points[0]
                p2 = phys_shape.points[1]
                x1, y1 = float(p1[0]), float(p1[1])
                x2, y2 = float(p2[0]), float(p2[1])
                width = abs(x2 - x1)
                height = abs(y2 - y1)
                center_x = (x1 + x2) / 2.0
                center_y = (y1 + y2) / 2.0
            else:
                center_x = float(tilemap.cell_width) / 2.0
                center_y = float(tilemap.cell_height) / 2.0
                width = float(tilemap.cell_width)
                height = float(tilemap.cell_height)
            shapes.append({
                "center_x": center_x,
                "center_y": center_y,
                "width": width,
                "height": height,
            })
        elif phys_shape.shape_type == "circle":
            center_x = float(tilemap.cell_width) / 2.0
            center_y = float(tilemap.cell_height) / 2.0
            radius = float(tilemap.cell_width) / 2.0
            if phys_shape.points:
                center_x = float(phys_shape.points[0][0]) if phys_shape.points else center_x
                center_y = float(phys_shape.points[0][1]) if phys_shape.points else center_y
                radius = float(phys_shape.points[1][0]) if len(phys_shape.points) > 1 and phys_shape.points[1] else radius
            shapes.append({
                "center_x": center_x,
                "center_y": center_y,
                "width": radius * 2.0,
                "height": radius * 2.0,
            })
    return shapes


def build_tile_collision_shapes(
    tilemap: Tilemap,
    tile: dict[str, Any],
    coord: tuple[int, int],
    tileset_resource: Any = None,
) -> list[dict[str, float]]:
    """Build collision shapes from tile metadata.

    Returns list of AABB rects in world coords.
    """
    cell_w = float(tilemap.cell_width)
    cell_h = float(tilemap.cell_height)
    custom_shapes = _resolve_per_tile_physics(tilemap, tile, coord, tileset_resource)
    if custom_shapes:
        result = []
        base_x = float(coord[0]) * cell_w
        base_y = float(coord[1]) * cell_h
        for shape in custom_shapes:
            result.append({
                "center_x": base_x + shape["center_x"],
                "center_y": base_y + shape["center_y"],
                "width": shape["width"],
                "height": shape["height"],
            })
        return result
    if _tile_is_solid(tile):
        return [_cell_to_region(tilemap, coord[0], coord[1], width_cells=1, height_cells=1)]
    return []


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
