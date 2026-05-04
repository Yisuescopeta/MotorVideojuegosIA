"""
engine/systems/animated_sprite_system.py - Sistema de animacion para AnimatedSprite2D.

Avanza frames basado en datos de SpriteFrames y tiempo transcurrido.
Soporta modos: loop, none, pingpong.
Aplica textura del frame actual al componente Sprite de la entidad.
"""

from __future__ import annotations

from typing import Any

from engine.components.animated_sprite_2d import AnimatedSprite2D
from engine.components.sprite import Sprite
from engine.ecs.world import World


class AnimatedSpriteSystem:
    """Actualiza AnimatedSprite2D cada frame, avanza frames y aplica textura."""

    def update(self, world: World, dt: float) -> None:
        for entity in world.get_entities_with(AnimatedSprite2D):
            anim = entity.get_component(AnimatedSprite2D)
            if anim is None or not anim.enabled:
                continue
            if not anim.playing:
                continue

            sprite_frames = anim._sprite_frames
            if sprite_frames is None:
                continue

            animation_name = anim.animation
            frames = sprite_frames.get("animations", {}).get(animation_name, [])
            if not frames:
                continue

            frame_count = len(frames)
            if frame_count == 0:
                continue

            anim._elapsed += dt * anim.speed_scale
            current_frame_data = frames[anim._current_frame]
            frame_duration = float(current_frame_data.get("duration", 0.1))

            if anim._elapsed >= frame_duration:
                anim._elapsed -= frame_duration
                loop_mode = sprite_frames.get("loop_mode", "loop")

                if loop_mode == "none":
                    if anim._current_frame < frame_count - 1:
                        anim._current_frame += 1
                    else:
                        anim.playing = False
                elif loop_mode == "pingpong":
                    direction = getattr(anim, "_pingpong_dir", 1)
                    next_frame = anim._current_frame + direction
                    if next_frame >= frame_count:
                        next_frame = frame_count - 2
                        direction = -1
                    elif next_frame < 0:
                        next_frame = 1
                        direction = 1
                    anim._current_frame = next_frame
                    anim._pingpong_dir = direction
                else:  # loop
                    anim._current_frame = (anim._current_frame + 1) % frame_count

                self._apply_frame(entity, anim, frames)

    def _apply_frame(
        self, entity: Any, anim: AnimatedSprite2D, frames: list[dict[str, Any]]
    ) -> None:
        """Aplica la textura del frame actual al componente Sprite."""
        if anim._current_frame < 0 or anim._current_frame >= len(frames):
            return
        frame_data = frames[anim._current_frame]
        texture_path = frame_data.get("texture", frame_data.get("path", ""))
        if not texture_path:
            return

        sprite = entity.get_component(Sprite)
        if sprite is not None:
            sprite.sync_texture_reference(texture_path)
            sprite.flip_x = anim.flip_h
            sprite.flip_y = anim.flip_v
