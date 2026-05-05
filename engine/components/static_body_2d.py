"""
engine/components/static_body_2d.py - StaticBody2D component (Godot parity)

PROPÓSITO:
    Immovable physics body. Entities with this component are treated as
    static by the physics system: no velocity integration, no gravity,
    infinite mass in collisions.

PROPIEDADES:
    - constant_linear_velocity_x/y: Constant linear velocity for moving platforms
    - constant_angular_velocity: Constant angular velocity
    - physics_material_override_path: Path to physics material resource

SERIALIZACIÓN JSON:
    {
        "constant_linear_velocity_x": 0.0,
        "constant_linear_velocity_y": 0.0,
        "constant_angular_velocity": 0.0,
        "physics_material_override_path": ""
    }
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class StaticBody2D(Component):
    """Godot StaticBody2D — immovable physics body."""

    def __init__(
        self,
        constant_linear_velocity_x: float = 0.0,
        constant_linear_velocity_y: float = 0.0,
        constant_angular_velocity: float = 0.0,
        physics_material_override_path: str = "",
    ) -> None:
        self.constant_linear_velocity_x: float = constant_linear_velocity_x
        self.constant_linear_velocity_y: float = constant_linear_velocity_y
        self.constant_angular_velocity: float = constant_angular_velocity
        self.physics_material_override_path: str = str(physics_material_override_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "constant_linear_velocity_x": self.constant_linear_velocity_x,
            "constant_linear_velocity_y": self.constant_linear_velocity_y,
            "constant_angular_velocity": self.constant_angular_velocity,
            "physics_material_override_path": self.physics_material_override_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StaticBody2D":
        return cls(
            constant_linear_velocity_x=data.get("constant_linear_velocity_x", 0.0),
            constant_linear_velocity_y=data.get("constant_linear_velocity_y", 0.0),
            constant_angular_velocity=data.get("constant_angular_velocity", 0.0),
            physics_material_override_path=data.get("physics_material_override_path", ""),
        )
