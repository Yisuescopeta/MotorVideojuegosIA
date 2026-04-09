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
    solid_tile_count = 0
    region_count = 0
    generated_entities = 0
    tilemap_reports: list[dict[str, Any]] = []

    for entity in world.get_entities_with(Transform, Tilemap):
        transform = entity.get_component(Transform)
        tilemap = entity.get_component(Tilemap)
        if transform is None or tilemap is None or not tilemap.enabled:
            continue
        regions = build_tilemap_collision_regions(tilemap, merge_shapes=merge_shapes)
        painted_tiles = sum(len(layer.get("tiles", {})) for layer in tilemap.layers)
        solid_tiles = sum(int(region.get("tile_count", 0)) for region in regions)
        layer_reports = _build_layer_reports(regions)
        tile_count += painted_tiles
        solid_tile_count += solid_tiles
        region_count += len(regions)
        tilemap_reports.append(
            {
                "entity": str(entity.name),
                "tile_count": int(painted_tiles),
                "solid_tile_count": int(solid_tiles),
                "region_count": int(len(regions)),
                "layers": layer_reports,
            }
        )
        for index, region in enumerate(regions):
            collider_entity = world.create_entity(
                f"{RUNTIME_TILE_COLLIDER_PREFIX}{entity.name}_{region.get('layer_name', 'Layer')}_{index}"
            )
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
                metadata={
                    "runtime_generated": "tilemap_collision",
                    "source_tilemap": entity.name,
                    "source_layer": str(region.get("layer_name", "")),
                    "collision_layer": int(region.get("collision_layer", 0)),
                    "tile_count": int(region.get("tile_count", 0)),
                    "cell_x": int(region.get("x", 0)),
                    "cell_y": int(region.get("y", 0)),
                    "width_cells": int(region.get("width_cells", 1)),
                    "height_cells": int(region.get("height_cells", 1)),
                },
            )
            generated_entities += 1

    return {
        "tile_count": tile_count,
        "solid_tile_count": solid_tile_count,
        "region_count": region_count,
        "generated_entities": generated_entities,
        "merge_shapes": bool(merge_shapes),
        "tilemaps": tilemap_reports,
        "duration_ms": (time.perf_counter() - started) * 1000.0,
    }


def build_tilemap_collision_regions(tilemap: Tilemap, *, merge_shapes: bool = True) -> list[dict[str, Any]]:
    regions: list[dict[str, float]] = []
    tile_definitions = _normalize_tile_definitions(tilemap.metadata.get("tile_definitions", {}))
    default_solid_ids = _normalize_tile_id_set(tilemap.metadata.get("solid_tile_ids", []))
    for layer in tilemap.layers:
        if not _layer_collision_enabled(layer):
            continue
        layer_metadata = layer.get("metadata", {})
        layer_definitions = _normalize_tile_definitions(layer_metadata.get("tile_definitions", {}))
        layer_solid_ids = default_solid_ids | _normalize_tile_id_set(layer_metadata.get("solid_tile_ids", []))
        solid_cells: set[tuple[int, int]] = set()
        for key, tile in layer.get("tiles", {}).items():
            resolved_tile = _resolve_tile_collision_payload(
                tile,
                tilemap_definitions=tile_definitions,
                layer_definitions=layer_definitions,
                inherited_solid_ids=layer_solid_ids,
            )
            if not _tile_is_solid(resolved_tile):
                continue
            x_value, y_value = key.split(",", 1)
            solid_cells.add((int(x_value), int(y_value)))
        if not solid_cells:
            continue
        if not merge_shapes:
            rectangles = [
                {"x": x, "y": y, "width_cells": 1, "height_cells": 1}
                for x, y in sorted(solid_cells, key=lambda item: (item[1], item[0]))
            ]
        else:
            rectangles = _merge_cells_to_rectangles(solid_cells)
        for rect in rectangles:
            region = _cell_to_region(
                tilemap,
                rect["x"],
                rect["y"],
                width_cells=rect["width_cells"],
                height_cells=rect["height_cells"],
            )
            region["layer_name"] = str(layer.get("name", "Layer"))
            region["collision_layer"] = max(0, int(layer.get("collision_layer", 0)))
            region["tile_count"] = int(rect["width_cells"] * rect["height_cells"])
            regions.append(region)
    return regions


def _tile_is_solid(tile: dict[str, Any]) -> bool:
    flags = {str(item).strip().lower() for item in tile.get("flags", [])}
    tags = {str(item).strip().lower() for item in tile.get("tags", [])}
    custom = tile.get("custom", {})
    if "solid" in flags or "solid" in tags:
        return True
    if isinstance(custom, dict):
        if bool(custom.get("solid", False)):
            return True
        if bool(custom.get("collision", False)):
            return True
        shape = str(custom.get("collision_shape", "")).strip().lower()
        if shape in {"grid", "box", "solid"}:
            return True
    return False


def _resolve_tile_collision_payload(
    tile: dict[str, Any],
    *,
    tilemap_definitions: dict[str, dict[str, Any]],
    layer_definitions: dict[str, dict[str, Any]],
    inherited_solid_ids: set[str],
) -> dict[str, Any]:
    tile_id = str(tile.get("tile_id", "")).strip()
    merged_flags: list[str] = []
    merged_tags: list[str] = []
    merged_custom: dict[str, Any] = {}
    for definition in (tilemap_definitions.get(tile_id, {}), layer_definitions.get(tile_id, {}), tile):
        merged_flags.extend(str(item) for item in definition.get("flags", []) if str(item).strip())
        merged_tags.extend(str(item) for item in definition.get("tags", []) if str(item).strip())
        custom = definition.get("custom", {})
        if isinstance(custom, dict):
            merged_custom.update(custom)
    if tile_id in inherited_solid_ids:
        merged_flags.append("solid")
    return {
        "tile_id": tile_id,
        "flags": merged_flags,
        "tags": merged_tags,
        "custom": merged_custom,
    }


def _normalize_tile_definitions(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    definitions: dict[str, dict[str, Any]] = {}
    for key, payload in value.items():
        if not isinstance(payload, dict):
            continue
        definitions[str(key).strip()] = {
            "flags": [str(item) for item in payload.get("flags", []) if str(item).strip()],
            "tags": [str(item) for item in payload.get("tags", []) if str(item).strip()],
            "custom": dict(payload.get("custom", {})) if isinstance(payload.get("custom", {}), dict) else {},
        }
    return definitions


def _normalize_tile_id_set(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _layer_collision_enabled(layer: dict[str, Any]) -> bool:
    metadata = layer.get("metadata", {})
    if isinstance(metadata, dict) and metadata.get("collision_enabled") is False:
        return False
    return True


def _build_layer_reports(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_layer: dict[str, dict[str, Any]] = {}
    for region in regions:
        layer_name = str(region.get("layer_name", "Layer"))
        bucket = by_layer.setdefault(
            layer_name,
            {
                "name": layer_name,
                "collision_layer": int(region.get("collision_layer", 0)),
                "region_count": 0,
                "solid_tile_count": 0,
            },
        )
        bucket["region_count"] += 1
        bucket["solid_tile_count"] += int(region.get("tile_count", 0))
    return [by_layer[key] for key in sorted(by_layer)]


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
        "x": float(x),
        "y": float(y),
        "width_cells": float(width_cells),
        "height_cells": float(height_cells),
        "center_x": center_x,
        "center_y": center_y,
        "width": width,
        "height": height,
    }


def _clear_runtime_tile_colliders(world: Any) -> None:
    for entity in list(world.get_all_entities()):
        if str(entity.name).startswith(RUNTIME_TILE_COLLIDER_PREFIX):
            world.remove_entity(entity.id)
