"""
engine/components/animation_player_2d.py - AnimationPlayer2D component (adaptado de Godot AnimationPlayer).

Reproduce AnimationResources en una entidad aplicando tracks de propiedades
a sus componentes.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class AnimationPlayer2D(Component):
    """Reproduce AnimationResources en una entidad (adaptado de Godot AnimationPlayer)."""

    def __init__(
        self,
        autoplay: bool = False,
        playback_speed: float = 1.0,
        animation_resource_path: str = "",
        current_animation: str = "",
    ) -> None:
        self.enabled: bool = True
        self.autoplay: bool = autoplay
        self.playback_speed: float = playback_speed
        self.animation_resource_path: str = animation_resource_path
        self.current_animation: str = current_animation

        # Runtime state (NO serializado)
        self._playback_time: float = 0.0
        self._is_playing: bool = False
        self._resource_cache: Any = None

    def play(self, animation_name: str = "") -> None:
        self.current_animation = animation_name or self.current_animation
        self._playback_time = 0.0
        self._is_playing = True

    def stop(self) -> None:
        self._is_playing = False

    def seek(self, time: float) -> None:
        self._playback_time = max(0.0, time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "autoplay": self.autoplay,
            "playback_speed": self.playback_speed,
            "animation_resource_path": self.animation_resource_path,
            "current_animation": self.current_animation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationPlayer2D":
        component = cls(
            autoplay=bool(data.get("autoplay", False)),
            playback_speed=float(data.get("playback_speed", 1.0)),
            animation_resource_path=str(data.get("animation_resource_path", "")),
            current_animation=str(data.get("current_animation", "")),
        )
        component.enabled = bool(data.get("enabled", True))
        return component
