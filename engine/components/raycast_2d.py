"""
engine/components/raycast_2d.py - Componente RayCast2D adaptado de Godot.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class RayCast2D(Component):
    """Godot RayCast2D as component. Updates via system each frame."""

    def __init__(self) -> None:
        self.enabled: bool = True
        self.cast_to_x: float = 0.0
        self.cast_to_y: float = 50.0
        self.collision_mask: int = 1
        self.collide_with_areas: bool = False
        self.collide_with_bodies: bool = True
        self.exclude_parent: bool = True
        # Results (runtime)
        self.is_colliding: bool = False
        self.collision_point_x: float = 0.0
        self.collision_point_y: float = 0.0
        self.collision_normal_x: float = 0.0
        self.collision_normal_y: float = 0.0
        self.collider_entity: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cast_to_x": self.cast_to_x,
            "cast_to_y": self.cast_to_y,
            "collision_mask": self.collision_mask,
            "collide_with_areas": self.collide_with_areas,
            "collide_with_bodies": self.collide_with_bodies,
            "exclude_parent": self.exclude_parent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RayCast2D":
        component = cls()
        component.enabled = bool(data.get("enabled", True))
        component.cast_to_x = float(data.get("cast_to_x", 0.0))
        component.cast_to_y = float(data.get("cast_to_y", 50.0))
        component.collision_mask = int(data.get("collision_mask", 1))
        component.collide_with_areas = bool(data.get("collide_with_areas", False))
        component.collide_with_bodies = bool(data.get("collide_with_bodies", True))
        component.exclude_parent = bool(data.get("exclude_parent", True))
        return component
