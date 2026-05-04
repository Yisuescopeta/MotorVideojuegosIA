"""engine/resources/animation_resource.py — Animation resource adaptado de Godot Animation.

AnimationResource es un recurso serializable reutilizable con tracks de animación
que interpolan propiedades en el tiempo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnimationTrack:
    """Un track de animación que interpola una propiedad en el tiempo (adaptado Godot)."""

    property_path: str = ""
    interpolation: str = "linear"
    keyframes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_path": self.property_path,
            "interpolation": self.interpolation,
            "keyframes": [dict(kf) for kf in self.keyframes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationTrack":
        if not isinstance(data, dict):
            return cls()
        raw_keyframes = data.get("keyframes", []) or []
        keyframes: list[dict[str, Any]] = []
        if isinstance(raw_keyframes, list):
            for kf in raw_keyframes:
                if isinstance(kf, dict):
                    keyframes.append(dict(kf))
        return cls(
            property_path=str(data.get("property_path", "")),
            interpolation=str(data.get("interpolation", "linear")),
            keyframes=keyframes,
        )


@dataclass
class AnimationResource:
    """Recurso de animación reutilizable con tracks de propiedades."""

    resource_id: str = ""
    resource_name: str = "New Animation"
    length: float = 1.0
    loop: bool = True
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
        )
        raw_tracks = data.get("tracks", []) or []
        if isinstance(raw_tracks, list):
            for track_data in raw_tracks:
                if isinstance(track_data, dict):
                    resource.tracks.append(AnimationTrack.from_dict(track_data))
        return resource
