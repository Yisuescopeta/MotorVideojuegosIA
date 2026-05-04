"""engine/resources/animation_resource.py — Animation resource adaptado de Godot Animation.

AnimationResource es un recurso serializable reutilizable con tracks de animación
que interpolan propiedades, invocan métodos o emiten eventos en el tiempo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AnimationTrackType:
    PROPERTY = "property"
    METHOD = "method"
    EVENT = "event"
    AUDIO = "audio"
    ANIMATION = "animation"
    BEZIER = "bezier"
    DISCRETE = "discrete"


@dataclass
class AnimationTrack:
    """Un track de animación con tipo (property, method, event, audio, animation, bezier, discrete)."""

    track_type: str = AnimationTrackType.PROPERTY
    property_path: str = ""
    interpolation: str = "linear"
    loop_wrap: bool = True
    enabled: bool = True
    keyframes: list[dict[str, Any]] = field(default_factory=list)
    method_name: str = ""
    event_name: str = ""
    # Audio track
    audio_stream: str = ""
    volume: float = 1.0
    # Animation track (sub-animation)
    target_animation: str = ""
    target_entity: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "track_type": self.track_type,
            "interpolation": self.interpolation,
            "loop_wrap": self.loop_wrap,
            "enabled": self.enabled,
            "keyframes": [dict(kf) for kf in self.keyframes],
        }
        if self.track_type == AnimationTrackType.PROPERTY:
            d["property_path"] = self.property_path
        elif self.track_type == AnimationTrackType.METHOD:
            d["method_name"] = self.method_name
        elif self.track_type == AnimationTrackType.EVENT:
            d["event_name"] = self.event_name
        elif self.track_type == AnimationTrackType.AUDIO:
            d["audio_stream"] = self.audio_stream
            d["volume"] = self.volume
        elif self.track_type == AnimationTrackType.ANIMATION:
            d["target_animation"] = self.target_animation
            d["target_entity"] = self.target_entity
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationTrack":
        if not isinstance(data, dict):
            return cls()
        track_type = str(data.get("track_type", AnimationTrackType.PROPERTY))
        raw_keyframes = data.get("keyframes", []) or []
        keyframes: list[dict[str, Any]] = []
        if isinstance(raw_keyframes, list):
            for kf in raw_keyframes:
                if isinstance(kf, dict):
                    keyframes.append(dict(kf))
        return cls(
            track_type=track_type,
            property_path=str(data.get("property_path", "")),
            interpolation=str(data.get("interpolation", "linear")),
            loop_wrap=bool(data.get("loop_wrap", True)),
            enabled=bool(data.get("enabled", True)),
            keyframes=keyframes,
            method_name=str(data.get("method_name", "")),
            event_name=str(data.get("event_name", "")),
            audio_stream=str(data.get("audio_stream", "")),
            volume=float(data.get("volume", 1.0)),
            target_animation=str(data.get("target_animation", "")),
            target_entity=str(data.get("target_entity", "")),
        )


@dataclass
class AnimationResource:
    """Recurso de animación reutilizable con tracks de propiedades, métodos, audio y sub-animaciones."""

    resource_id: str = ""
    resource_name: str = "New Animation"
    length: float = 1.0
    loop: bool = True
    loop_mode: str = "none"
    step: float = 0.1
    tracks: list[AnimationTrack] = field(default_factory=list)

    def add_track(self, property_path: str, interpolation: str = "linear") -> AnimationTrack:
        track = AnimationTrack(property_path=property_path, interpolation=interpolation)
        self.tracks.append(track)
        return track

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "length": self.length,
            "loop": self.loop,
            "loop_mode": self.loop_mode,
            "step": self.step,
            "tracks": [track.to_dict() for track in self.tracks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationResource":
        if not isinstance(data, dict):
            return cls()
        resource = cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "New Animation")),
            length=float(data.get("length", 1.0)),
            loop=bool(data.get("loop", True)),
            loop_mode=str(data.get("loop_mode", "none")),
            step=float(data.get("step", 0.1)),
        )
        raw_tracks = data.get("tracks", []) or []
        if isinstance(raw_tracks, list):
            for track_data in raw_tracks:
                if isinstance(track_data, dict):
                    resource.tracks.append(AnimationTrack.from_dict(track_data))
        return resource
