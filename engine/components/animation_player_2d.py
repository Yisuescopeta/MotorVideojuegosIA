"""
engine/components/animation_player_2d.py - AnimationPlayer2D component (adaptado de Godot AnimationPlayer).

Reproduce AnimationResources en una entidad aplicando tracks de propiedades,
métodos, audio y sub-animaciones a sus componentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from engine.ecs.component import Component


class AnimationPlayer2D(Component):
    """Reproduce AnimationResources en una entidad (adaptado de Godot AnimationPlayer)."""

    def __init__(
        self,
        autoplay: bool = False,
        playback_speed: float = 1.0,
        animation_resource_path: str = "",
        current_animation: str = "",
        auto_capture: bool = True,
        capture_on_play: bool = False,
    ) -> None:
        self.enabled: bool = True
        self.autoplay: bool = autoplay
        self.playback_speed: float = playback_speed
        self.animation_resource_path: str = animation_resource_path
        self.current_animation: str = current_animation
        self.auto_capture: bool = auto_capture
        self.capture_on_play: bool = capture_on_play

        # Method tracks
        self.method_tracks: List[dict] = []
        # Audio tracks
        self.audio_tracks: List[dict] = []
        # Animation tracks (sub-animation chaining)
        self.animation_tracks: List[dict] = []

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

    def add_method_track(self, data: dict) -> None:
        self.method_tracks.append(data)

    def add_audio_track(self, data: dict) -> None:
        self.audio_tracks.append(data)

    def add_animation_track(self, data: dict) -> None:
        self.animation_tracks.append(data)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "enabled": self.enabled,
            "autoplay": self.autoplay,
            "playback_speed": self.playback_speed,
            "animation_resource_path": self.animation_resource_path,
            "current_animation": self.current_animation,
            "auto_capture": self.auto_capture,
            "capture_on_play": self.capture_on_play,
        }
        if self.method_tracks:
            result["method_tracks"] = [dict(t) for t in self.method_tracks]
        if self.audio_tracks:
            result["audio_tracks"] = [dict(t) for t in self.audio_tracks]
        if self.animation_tracks:
            result["animation_tracks"] = [dict(t) for t in self.animation_tracks]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationPlayer2D":
        component = cls(
            autoplay=bool(data.get("autoplay", False)),
            playback_speed=float(data.get("playback_speed", 1.0)),
            animation_resource_path=str(data.get("animation_resource_path", "")),
            current_animation=str(data.get("current_animation", "")),
            auto_capture=bool(data.get("auto_capture", True)),
            capture_on_play=bool(data.get("capture_on_play", False)),
        )
        component.enabled = bool(data.get("enabled", True))
        component.method_tracks = [dict(t) for t in (data.get("method_tracks") or [])]
        component.audio_tracks = [dict(t) for t in (data.get("audio_tracks") or [])]
        component.animation_tracks = [dict(t) for t in (data.get("animation_tracks") or [])]
        return component
