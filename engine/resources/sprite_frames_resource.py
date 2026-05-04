"""engine/resources/sprite_frames_resource.py — SpriteFrames resource adaptado de Godot SpriteFrames.

SpriteFramesResource es un conjunto de animaciones de frames reutilizable.
SpriteFrame y SpriteAnimation son tipos auxiliares para frames individuales.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SpriteFrame:
    """Un frame individual de animacion sprite."""
    texture_path: str = ""
    duration: float = 0.1

    def to_dict(self) -> dict[str, Any]:
        return {"texture_path": self.texture_path, "duration": self.duration}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpriteFrame":
        return cls(
            texture_path=str(data.get("texture_path", "")),
            duration=float(data.get("duration", 0.1)),
        )


@dataclass
class SpriteAnimation:
    """Una animacion con sus frames, velocidad y modo de loop."""
    name: str = "default"
    frames: List[SpriteFrame] = field(default_factory=list)
    speed: float = 10.0
    loop_mode: str = "loop"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "frames": [f.to_dict() for f in self.frames],
            "speed": self.speed,
            "loop_mode": self.loop_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpriteAnimation":
        raw_frames = data.get("frames", [])
        frames = [SpriteFrame.from_dict(f) for f in raw_frames] if isinstance(raw_frames, list) else []
        return cls(
            name=str(data.get("name", "default")),
            frames=frames,
            speed=float(data.get("speed", 10.0)),
            loop_mode=str(data.get("loop_mode", "loop")),
        )


@dataclass
class SpriteFrames:
    """Standalone sprite frames resource (Godot SpriteFrames)."""
    resource_id: str = ""
    animations: Dict[str, SpriteAnimation] = field(default_factory=dict)

    def add_animation(self, name: str) -> SpriteAnimation:
        anim = SpriteAnimation(name=name)
        self.animations[name] = anim
        return anim

    def remove_animation(self, name: str) -> None:
        self.animations.pop(name, None)

    def add_frame(self, anim_name: str, texture_path: str, duration: float = 0.1) -> None:
        if anim_name not in self.animations:
            self.add_animation(anim_name)
        frame = SpriteFrame(texture_path=texture_path, duration=duration)
        self.animations[anim_name].frames.append(frame)

    def set_animation_speed(self, name: str, speed: float) -> None:
        if name in self.animations:
            self.animations[name].speed = float(speed)

    def set_animation_loop(self, name: str, loop_mode: str) -> None:
        if name in self.animations:
            self.animations[name].loop_mode = str(loop_mode)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "animations": {name: anim.to_dict() for name, anim in self.animations.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpriteFrames":
        instance = cls(resource_id=str(data.get("resource_id", "")))
        raw = data.get("animations", {})
        if isinstance(raw, dict):
            for name, anim_data in raw.items():
                if isinstance(anim_data, dict):
                    instance.animations[name] = SpriteAnimation.from_dict(anim_data)
        return instance


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
