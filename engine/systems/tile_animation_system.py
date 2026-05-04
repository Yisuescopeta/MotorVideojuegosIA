"""
engine/systems/tile_animation_system.py - Sistema de animacion de tiles en runtime.

Actualiza tile_id de tiles animados cada frame segun secuencia de frames.
Adaptado del patron AnimatedTile de Godot.
"""

from __future__ import annotations

from typing import Any

from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.world import World


class TileAnimationSystem:
    """Sistema que anima tiles marcados con animated=True cada frame."""

    def update(self, world: World, dt: float) -> None:
        """Recorre tiles animados y avanza su secuencia de frames."""
        for entity in world.get_entities_with(Tilemap, Transform):
            tilemap = entity.get_component(Tilemap)
            if tilemap is None or not tilemap.enabled:
                continue

            for layer in tilemap.layers:
                tiles = layer.get("tiles", {})
                if not tiles:
                    continue

                for _coord_key, tile in list(tiles.items()):
                    if not isinstance(tile, dict):
                        continue
                    if not tile.get("animated"):
                        continue

                    self._advance_tile_animation(tile, dt)

    def _advance_tile_animation(self, tile: dict[str, Any], dt: float) -> None:
        """Avanza animacion de un tile individual."""
        # Frames se almacenan en custom._anim_frames (inline fallback)
        custom: dict[str, Any] = tile.setdefault("custom", {})
        if not isinstance(custom, dict):
            custom = {}
            tile["custom"] = custom

        anim_frames: list[dict[str, Any]] = custom.get("_anim_frames", [])
        if not anim_frames:
            return

        # Timer acumulativo
        timer: float = float(custom.get("_anim_timer", 0.0)) + dt
        frame_index: int = int(custom.get("_anim_frame_index", 0))
        frame_count: int = len(anim_frames)

        # Clamp frame_index por si frames cambiaron mientras tanto
        if frame_index >= frame_count:
            frame_index = 0

        current_frame: dict[str, Any] = anim_frames[frame_index]
        frame_duration: float = float(current_frame.get("duration", 0.1))

        if timer >= frame_duration:
            timer = 0.0
            frame_index = (frame_index + 1) % frame_count

            # Actualizar tile_id al del nuevo frame
            new_tile_id: str = str(anim_frames[frame_index].get("tile_id", tile.get("tile_id", "")))
            if new_tile_id:
                tile["tile_id"] = new_tile_id

        custom["_anim_timer"] = timer
        custom["_anim_frame_index"] = frame_index
