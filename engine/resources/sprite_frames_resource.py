"""engine/resources/sprite_frames_resource.py — SpriteFrames resource adaptado de Godot SpriteFrames.

SpriteFramesResource es un conjunto de animaciones de frames reutilizable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpriteFramesResource:
    """Conjunto de animaciones de frames reutilizable (adaptado Godot SpriteFrames)."""

    resource_id: str = ""
    resource_name: str = "New SpriteFrames"
    texture_path: str = ""
    animations: dict[str, dict[str, Any]] = field(default_factory=dict)
    fps: float = 8.0

    def add_animation(self, name: str, frames: list[int], fps: float = 8.0) -> None:
        self.animations[name] = {"frames": list(frames), "fps": float(fps)}

    def get_animation(self, name: str) -> dict[str, Any] | None:
        return self.animations.get(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "texture_path": self.texture_path,
            "animations": {
                str(name): {"frames": list(data["frames"]), "fps": data["fps"]}
                for name, data in self.animations.items()
            },
            "fps": self.fps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpriteFramesResource":
        if not isinstance(data, dict):
            return cls()
        resource = cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "New SpriteFrames")),
            texture_path=str(data.get("texture_path", "")),
            fps=float(data.get("fps", 8.0)),
        )
        raw_animations = data.get("animations", {}) or {}
        if isinstance(raw_animations, dict):
            for name, anim_data in raw_animations.items():
                if isinstance(anim_data, dict):
                    resource.animations[str(name)] = {
                        "frames": list(anim_data.get("frames", [])),
                        "fps": float(anim_data.get("fps", 8.0)),
                    }
        return resource
