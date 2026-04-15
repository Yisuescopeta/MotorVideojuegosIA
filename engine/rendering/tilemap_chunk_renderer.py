"""Tilemap chunk render target materialization and drawing."""

from __future__ import annotations

import math
from typing import Any, Callable

import pyray as rl
from engine.assets.asset_reference import normalize_asset_reference
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.rendering.render_targets import RenderTargetPool


class TilemapChunkRenderer:
    """Renders tilemap chunks through cached render targets with safe fallback."""

    def __init__(self, render_targets: RenderTargetPool, load_texture: Callable[[Any, str], Any]) -> None:
        self._render_targets = render_targets
        self._load_texture = load_texture

    def invalidate_cached_targets(self, chunk_cache: dict[tuple[int, str, int, int], dict[str, Any]]) -> None:
        self._render_targets.unload_all()
        for cached in chunk_cache.values():
            cached["render_target_dirty"] = True

    def unload_target(self, target_name: str) -> None:
        self._render_targets.unload(str(target_name or ""))

    def prepare_targets(self, graph: dict[str, Any], chunk_cache: dict[tuple[int, str, int, int], dict[str, Any]]) -> None:
        for pass_data in graph.get("passes", []):
            for command in pass_data.get("commands", []):
                if command.get("kind") == "tilemap_chunk":
                    self.prepare_target(command, chunk_cache)

    def prepare_target(self, command: dict[str, Any], chunk_cache: dict[tuple[int, str, int, int], dict[str, Any]]) -> None:
        target_name = str(command.get("render_target_name", ""))
        if not target_name or self.tile_draw_call_count(command) <= 0:
            return

        chunk_data = command.get("chunk_data", {})
        bounds = dict(chunk_data.get("bounds", {}))
        width = int(math.ceil(float(bounds.get("width", 0.0))))
        height = int(math.ceil(float(bounds.get("height", 0.0))))
        if width <= 0 or height <= 0:
            return

        existing = self._render_targets.get(target_name)
        dirty = bool(command.get("render_target_dirty", True))
        if (
            existing is not None
            and existing.render_texture is not None
            and existing.width == width
            and existing.height == height
            and not dirty
        ):
            return

        handle = self._render_targets.begin(target_name, width, height, rl.Color(0, 0, 0, 0))
        try:
            if handle.render_texture is None:
                return
            for tile in chunk_data.get("tiles", []):
                self._draw_tile_into_target(tile, bounds)
        finally:
            self._render_targets.end()

        cache_key = command.get("cache_key")
        if isinstance(cache_key, tuple):
            cached = chunk_cache.get(cache_key)
            if cached is not None:
                cached["render_target_dirty"] = False
        command["render_target_dirty"] = False

    def command_draw_call_count(self, command: dict[str, Any]) -> int:
        return 1 if self.tile_draw_call_count(command) > 0 else 0

    def tile_draw_call_count(self, command: dict[str, Any]) -> int:
        if command.get("kind") != "tilemap_chunk":
            return 0
        entity = command.get("entity")
        transform = entity.get_component(Transform) if isinstance(entity, Entity) else None
        if transform is not None and not self._has_valid_scale(transform):
            return 0
        return sum(1 for tile in command.get("chunk_data", {}).get("tiles", []) if bool(tile.get("resolved", False)))

    def draw_chunk(self, command: dict[str, Any]) -> None:
        entity = command["entity"]
        transform = entity.get_component(Transform)
        if transform is None or not self._has_valid_scale(transform):
            return
        if self._draw_chunk_target(command, transform):
            return
        self._draw_chunk_fallback(command, transform)

    def _draw_tile_into_target(self, tile: dict[str, Any], bounds: dict[str, Any]) -> None:
        if not bool(tile.get("resolved", False)):
            return
        texture = self._load_tile_texture(tile)
        if texture.id == 0:
            return
        source_rect = self._source_rect_from_tile(tile)
        dest_data = dict(tile.get("dest", {}))
        dest_rect = rl.Rectangle(
            float(dest_data.get("x", 0.0)) - float(bounds.get("x", 0.0)),
            float(dest_data.get("y", 0.0)) - float(bounds.get("y", 0.0)),
            float(dest_data.get("width", 0.0)),
            float(dest_data.get("height", 0.0)),
        )
        rl.draw_texture_pro(texture, source_rect, dest_rect, rl.Vector2(0, 0), 0.0, self._color_from_payload(tile.get("tint", [])))

    def _draw_chunk_target(self, command: dict[str, Any], transform: Transform) -> bool:
        target_name = str(command.get("render_target_name", ""))
        if not target_name:
            return False
        handle = self._render_targets.get(target_name)
        if handle is None or handle.render_texture is None:
            return False

        chunk_data = command.get("chunk_data", {})
        bounds = dict(chunk_data.get("bounds", {}))
        local_x = float(bounds.get("x", 0.0))
        local_y = float(bounds.get("y", 0.0))
        local_width = float(bounds.get("width", 0.0))
        local_height = float(bounds.get("height", 0.0))
        if local_width <= 0.0 or local_height <= 0.0:
            return False

        scale_x = float(transform.scale_x)
        scale_y = float(transform.scale_y)
        source_rect = rl.Rectangle(0.0, 0.0, float(handle.render_texture.texture.width), -float(handle.render_texture.texture.height))
        if scale_x < 0.0:
            local_x += local_width
            source_rect.x += source_rect.width
            source_rect.width *= -1.0
        if scale_y < 0.0:
            local_y += local_height
            source_rect.y += source_rect.height
            source_rect.height *= -1.0

        world_x, world_y = self._local_to_world_point(transform, local_x, local_y)
        dest_rect = rl.Rectangle(
            world_x,
            world_y,
            local_width * abs(scale_x),
            local_height * abs(scale_y),
        )
        rl.draw_texture_pro(handle.render_texture.texture, source_rect, dest_rect, rl.Vector2(0, 0), float(transform.rotation), rl.WHITE)
        return True

    def _draw_chunk_fallback(self, command: dict[str, Any], transform: Transform) -> None:
        scale_x = float(transform.scale_x)
        scale_y = float(transform.scale_y)
        chunk_data = command.get("chunk_data", {})
        for tile in chunk_data.get("tiles", []):
            if not bool(tile.get("resolved", False)):
                continue
            texture = self._load_tile_texture(tile)
            if texture.id == 0:
                continue
            source_rect = self._source_rect_from_tile(tile)
            dest_data = dict(tile.get("dest", {}))
            local_x = float(dest_data.get("x", 0.0))
            local_y = float(dest_data.get("y", 0.0))
            local_width = float(dest_data.get("width", 0.0))
            local_height = float(dest_data.get("height", 0.0))
            if scale_x < 0.0:
                local_x += local_width
                source_rect.x += source_rect.width
                source_rect.width *= -1.0
            if scale_y < 0.0:
                local_y += local_height
                source_rect.y += source_rect.height
                source_rect.height *= -1.0
            world_x, world_y = self._local_to_world_point(transform, local_x, local_y)
            dest_rect = rl.Rectangle(
                world_x,
                world_y,
                local_width * abs(scale_x),
                local_height * abs(scale_y),
            )
            rl.draw_texture_pro(texture, source_rect, dest_rect, rl.Vector2(0, 0), float(transform.rotation), self._color_from_payload(tile.get("tint", [])))

    def _load_tile_texture(self, tile: dict[str, Any]) -> Any:
        texture_ref = normalize_asset_reference(tile.get("texture"))
        texture_path = str(tile.get("texture_path", ""))
        return self._load_texture(texture_ref, texture_path)

    @staticmethod
    def _source_rect_from_tile(tile: dict[str, Any]) -> Any:
        source_rect_data = dict(tile.get("source_rect", {}))
        return rl.Rectangle(
            float(source_rect_data.get("x", 0.0)),
            float(source_rect_data.get("y", 0.0)),
            float(source_rect_data.get("width", 0.0)),
            float(source_rect_data.get("height", 0.0)),
        )

    @staticmethod
    def _color_from_payload(color: Any) -> rl.Color:
        values = list(color) if isinstance(color, (list, tuple)) else [255, 255, 255, 255]
        while len(values) < 4:
            values.append(255)
        return rl.Color(int(values[0]), int(values[1]), int(values[2]), int(values[3]))

    @staticmethod
    def _has_valid_scale(transform: Transform) -> bool:
        scale_x = float(transform.scale_x)
        scale_y = float(transform.scale_y)
        return math.isfinite(scale_x) and math.isfinite(scale_y) and scale_x != 0.0 and scale_y != 0.0

    @staticmethod
    def _local_to_world_point(transform: Transform, local_x: float, local_y: float) -> tuple[float, float]:
        scaled_x = float(local_x) * float(transform.scale_x)
        scaled_y = float(local_y) * float(transform.scale_y)
        radians = math.radians(float(transform.rotation))
        cos_r = math.cos(radians)
        sin_r = math.sin(radians)
        world_x = float(transform.x) + (scaled_x * cos_r) - (scaled_y * sin_r)
        world_y = float(transform.y) + (scaled_x * sin_r) + (scaled_y * cos_r)
        return (world_x, world_y)
