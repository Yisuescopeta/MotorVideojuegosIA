"""
engine/components/animated_sprite_2d.py - Componente AnimatedSprite2D adaptado de Godot.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class AnimatedSprite2D(Component):
    """Godot AnimatedSprite2D equivalent. Uses sprite frames for animation."""

    def __init__(self) -> None:
        self.enabled: bool = True
        self.sprite_frames_path: str = ""
        self.animation: str = "default"
        self.frame: int = 0
        self.playing: bool = False
        self.speed_scale: float = 1.0
        self.centered: bool = True
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.flip_h: bool = False
        self.flip_v: bool = False
        # Runtime
        self._elapsed: float = 0.0
        self._current_frame: int = 0
        self._sprite_frames: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sprite_frames_path": self.sprite_frames_path,
            "animation": self.animation,
            "frame": self.frame,
            "playing": self.playing,
            "speed_scale": self.speed_scale,
            "centered": self.centered,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "flip_h": self.flip_h,
            "flip_v": self.flip_v,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimatedSprite2D":
        component = cls()
        component.enabled = bool(data.get("enabled", True))
        component.sprite_frames_path = str(data.get("sprite_frames_path", ""))
        component.animation = str(data.get("animation", "default"))
        component.frame = int(data.get("frame", 0))
        component.playing = bool(data.get("playing", False))
        component.speed_scale = float(data.get("speed_scale", 1.0))
        component.centered = bool(data.get("centered", True))
        component.offset_x = float(data.get("offset_x", 0.0))
        component.offset_y = float(data.get("offset_y", 0.0))
        component.flip_h = bool(data.get("flip_h", False))
        component.flip_v = bool(data.get("flip_v", False))
        return component
