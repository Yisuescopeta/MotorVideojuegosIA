"""
engine/components/animatable_body_2d.py - AnimatableBody2D component (Godot parity)

PROPÓSITO:
    Static body that can be moved by an AnimationPlayer. When sync_to_physics
    is True, the collider position is updated from Transform each frame but
    no physics motion (gravity, velocity) is applied.

PROPIEDADES:
    - sync_to_physics: Whether to sync collider position from Transform each frame

SERIALIZACIÓN JSON:
    {
        "sync_to_physics": true
    }
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class AnimatableBody2D(Component):
    """Godot AnimatableBody2D — static body movable by AnimationPlayer."""

    def __init__(self, sync_to_physics: bool = True) -> None:
        self.sync_to_physics: bool = bool(sync_to_physics)

    def to_dict(self) -> dict[str, Any]:
        return {"sync_to_physics": self.sync_to_physics}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimatableBody2D":
        return cls(sync_to_physics=data.get("sync_to_physics", True))
