"""
engine/components/audio_stream_player_2d.py - AudioStreamPlayer2D component (adaptado de Godot AudioStreamPlayer2D).

Reproduce un AudioStreamResource vinculado a una entidad.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class AudioStreamPlayer2D(Component):
    """Reproduce un AudioStreamResource (adaptado de Godot AudioStreamPlayer2D)."""

    def __init__(
        self,
        enabled: bool = True,
        audio_stream_path: str = "",
        autoplay: bool = False,
        volume_db: float = 0.0,
        pitch_scale: float = 1.0,
        playing: bool = False,
        loop: bool = False,
    ) -> None:
        self.enabled: bool = enabled
        self.audio_stream_path: str = audio_stream_path
        self.autoplay: bool = autoplay
        self.volume_db: float = volume_db
        self.pitch_scale: float = pitch_scale
        self.playing: bool = playing
        self.loop: bool = loop
        self._playback_position: float = 0.0

    def play(self) -> None:
        self.playing = True
        self._playback_position = 0.0

    def stop(self) -> None:
        self.playing = False
        self._playback_position = 0.0

    def pause(self) -> None:
        self.playing = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "audio_stream_path": self.audio_stream_path,
            "autoplay": self.autoplay,
            "volume_db": self.volume_db,
            "pitch_scale": self.pitch_scale,
            "playing": self.playing,
            "loop": self.loop,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioStreamPlayer2D":
        if not isinstance(data, dict):
            return cls()
        component = cls(
            enabled=bool(data.get("enabled", True)),
            audio_stream_path=str(data.get("audio_stream_path", "")),
            autoplay=bool(data.get("autoplay", False)),
            volume_db=float(data.get("volume_db", 0.0)),
            pitch_scale=float(data.get("pitch_scale", 1.0)),
            playing=bool(data.get("playing", False)),
            loop=bool(data.get("loop", False)),
        )
        component._playback_position = float(data.get("_playback_position", 0.0))
        return component
