"""engine/components/remote_transform_2d.py — RemoteTransform2D component (Godot parity).
Pushes transform (position, rotation, scale) to a target entity.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class RemoteTransform2D(Component):
    """Pushes transform to another entity (Godot RemoteTransform2D)."""

    def __init__(
        self,
        target_entity: str = "",
        update_position: bool = True,
        update_rotation: bool = True,
        update_scale: bool = True,
        use_global_coordinates: bool = True,
    ) -> None:
        self.enabled: bool = True
        self.target_entity: str = str(target_entity)
        self.update_position: bool = bool(update_position)
        self.update_rotation: bool = bool(update_rotation)
        self.update_scale: bool = bool(update_scale)
        self.use_global_coordinates: bool = bool(use_global_coordinates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "target_entity": self.target_entity,
            "update_position": self.update_position,
            "update_rotation": self.update_rotation,
            "update_scale": self.update_scale,
            "use_global_coordinates": self.use_global_coordinates,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoteTransform2D":
        component = cls(
            target_entity=data.get("target_entity", ""),
            update_position=data.get("update_position", True),
            update_rotation=data.get("update_rotation", True),
            update_scale=data.get("update_scale", True),
            use_global_coordinates=data.get("use_global_coordinates", True),
        )
        component.enabled = data.get("enabled", True)
        return component
