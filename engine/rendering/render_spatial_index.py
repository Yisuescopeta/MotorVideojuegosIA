from __future__ import annotations

import math
from collections.abc import Iterable

from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.physics.spatial_hash import SpatialHash2D

AABB = tuple[float, float, float, float]


class RenderSpatialIndex:
    """Indice espacial simple para entidades renderizables 2D."""

    PLACEHOLDER_SIZE: float = 32.0

    def __init__(self, cell_size: float = 256.0) -> None:
        self._grid = SpatialHash2D(cell_size=cell_size)
        self._bounds_by_entity_id: dict[int, AABB] = {}

    def clear(self) -> None:
        self._grid.clear()
        self._bounds_by_entity_id.clear()

    def rebuild(self, entities: Iterable[Entity]) -> None:
        self.clear()
        for entity in entities:
            bounds = self.bounds_for_entity(entity)
            if bounds is None:
                continue
            self._bounds_by_entity_id[int(entity.id)] = bounds
            self._grid.insert(int(entity.id), bounds)

    def query(self, camera_bounds: AABB) -> set[int]:
        candidates = self._grid.query(camera_bounds)
        return {
            entity_id
            for entity_id in candidates
            if self._intersects(self._bounds_by_entity_id.get(entity_id), camera_bounds)
        }

    @classmethod
    def bounds_for_entity(cls, entity: Entity) -> AABB | None:
        if not bool(getattr(entity, "active", True)):
            return None
        transform = entity.get_component(Transform)
        if transform is None or not bool(getattr(transform, "enabled", True)):
            return None

        sprite = entity.get_component(Sprite)
        if sprite is not None and bool(getattr(sprite, "enabled", True)):
            return cls._sprite_bounds(transform, sprite)

        tilemap = entity.get_component(Tilemap)
        if tilemap is not None and bool(getattr(tilemap, "enabled", True)):
            return cls._tilemap_bounds(transform, tilemap)

        render_order = entity.get_component(RenderOrder2D)
        if render_order is not None and bool(getattr(render_order, "enabled", True)):
            return cls._placeholder_bounds(transform)

        return None

    @classmethod
    def _sprite_bounds(cls, transform: Transform, sprite: Sprite) -> AABB:
        width = float(sprite.width if sprite.width > 0 else cls.PLACEHOLDER_SIZE)
        height = float(sprite.height if sprite.height > 0 else cls.PLACEHOLDER_SIZE)
        scaled_width = abs(width * float(transform.scale_x))
        scaled_height = abs(height * float(transform.scale_y))
        left = float(transform.x) - (scaled_width * float(sprite.origin_x))
        top = float(transform.y) - (scaled_height * float(sprite.origin_y))
        return cls._expand_for_rotation(left, top, left + scaled_width, top + scaled_height, transform.rotation)

    @classmethod
    def _placeholder_bounds(cls, transform: Transform) -> AABB:
        width = abs(cls.PLACEHOLDER_SIZE * float(transform.scale_x))
        height = abs(cls.PLACEHOLDER_SIZE * float(transform.scale_y))
        left = float(transform.x) - (width * 0.5)
        top = float(transform.y) - (height * 0.5)
        return cls._expand_for_rotation(left, top, left + width, top + height, transform.rotation)

    @classmethod
    def _tilemap_bounds(cls, transform: Transform, tilemap: Tilemap) -> AABB:
        local_bounds = cls._tilemap_local_bounds(tilemap)
        if local_bounds is None:
            return cls._placeholder_bounds(transform)
        left, top, right, bottom = local_bounds
        scaled_left = left * float(transform.scale_x)
        scaled_right = right * float(transform.scale_x)
        scaled_top = top * float(transform.scale_y)
        scaled_bottom = bottom * float(transform.scale_y)
        world_left = float(transform.x) + min(scaled_left, scaled_right)
        world_right = float(transform.x) + max(scaled_left, scaled_right)
        world_top = float(transform.y) + min(scaled_top, scaled_bottom)
        world_bottom = float(transform.y) + max(scaled_top, scaled_bottom)
        return cls._expand_for_rotation(world_left, world_top, world_right, world_bottom, transform.rotation)

    @classmethod
    def _tilemap_local_bounds(cls, tilemap: Tilemap) -> AABB | None:
        min_x: int | None = None
        min_y: int | None = None
        max_x: int | None = None
        max_y: int | None = None
        min_offset_x = 0.0
        min_offset_y = 0.0
        max_offset_x = 0.0
        max_offset_y = 0.0

        for layer in tilemap.layers:
            if not bool(layer.get("visible", True)):
                continue
            layer_offset_x = float(layer.get("offset_x", 0.0))
            layer_offset_y = float(layer.get("offset_y", 0.0))
            for tile_x, tile_y in cls._iter_tile_positions(layer.get("tiles", {})):
                if min_x is None or tile_x < min_x:
                    min_x = tile_x
                    min_offset_x = layer_offset_x
                if min_y is None or tile_y < min_y:
                    min_y = tile_y
                    min_offset_y = layer_offset_y
                if max_x is None or tile_x > max_x:
                    max_x = tile_x
                    max_offset_x = layer_offset_x
                if max_y is None or tile_y > max_y:
                    max_y = tile_y
                    max_offset_y = layer_offset_y

        if min_x is None or min_y is None or max_x is None or max_y is None:
            return None
        cell_width = float(tilemap.cell_width)
        cell_height = float(tilemap.cell_height)
        return (
            float(min_x) * cell_width + min_offset_x,
            float(min_y) * cell_height + min_offset_y,
            float(max_x + 1) * cell_width + max_offset_x,
            float(max_y + 1) * cell_height + max_offset_y,
        )

    @staticmethod
    def _iter_tile_positions(tiles: object) -> Iterable[tuple[int, int]]:
        if isinstance(tiles, dict):
            for key in tiles.keys():
                try:
                    if isinstance(key, tuple) and len(key) == 2:
                        yield (int(key[0]), int(key[1]))
                    else:
                        x_value, y_value = str(key).split(",", 1)
                        yield (int(x_value), int(y_value))
                except (TypeError, ValueError):
                    continue
            return
        if isinstance(tiles, list):
            for tile in tiles:
                if not isinstance(tile, dict):
                    continue
                try:
                    yield (int(tile.get("x", 0)), int(tile.get("y", 0)))
                except (TypeError, ValueError):
                    continue

    @staticmethod
    def _expand_for_rotation(left: float, top: float, right: float, bottom: float, rotation: float) -> AABB:
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

    @staticmethod
    def _intersects(bounds: AABB | None, query_bounds: AABB) -> bool:
        if bounds is None:
            return False
        left, top, right, bottom = bounds
        query_left, query_top, query_right, query_bottom = query_bounds
        return left < query_right and right > query_left and top < query_bottom and bottom > query_top
