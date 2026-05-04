"""
engine/components/collision_shape_2d.py - CollisionShape2D component (Godot parity)

PROPÓSITO:
    Dedicated collision shape definition. If both CollisionShape2D and Collider
    exist on the same entity, CollisionShape2D takes precedence for shape
    definition. Supports box, circle, capsule, and polygon shapes.

PROPIEDADES:
    - shape_type: "box", "circle", "capsule", or "polygon"
    - width / height: Rectangle dimensions (for box)
    - radius: Radius (for circle/capsule)
    - points: Polygon vertices
    - disabled: Whether this shape is disabled
    - one_way_collision: One-way collision flag
    - one_way_collision_margin: Margin for one-way collision
    - one_way_collision_direction_y: Direction Y for one-way collision

SERIALIZACIÓN JSON:
    {
        "shape_type": "box",
        "width": 32.0,
        "height": 32.0,
        "radius": 16.0,
        "points": null,
        "disabled": false,
        "one_way_collision": false,
        "one_way_collision_margin": 1.0,
        "one_way_collision_direction_y": -1.0
    }
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class CollisionShape2D(Component):
    """Dedicated collision shape (Godot CollisionShape2D)."""

    def __init__(
        self,
        shape_type: str = "box",
        width: float = 32.0,
        height: float = 32.0,
        radius: float = 16.0,
        points: list | None = None,
        disabled: bool = False,
        one_way_collision: bool = False,
        one_way_collision_margin: float = 1.0,
        one_way_collision_direction_y: float = -1.0,
    ) -> None:
        self.shape_type: str = str(shape_type or "box")
        self.width: float = width
        self.height: float = height
        self.radius: float = radius
        self.points: list = list(points) if points else []
        self.disabled: bool = bool(disabled)
        self.one_way_collision: bool = bool(one_way_collision)
        self.one_way_collision_margin: float = float(one_way_collision_margin)
        self.one_way_collision_direction_y: float = float(one_way_collision_direction_y)

    def get_bounds(self, x: float, y: float) -> tuple[float, float, float, float]:
        """Calcula los límites AABB del shape en coordenadas mundo."""
        if self.shape_type == "circle":
            return (
                x - self.radius,
                y - self.radius,
                x + self.radius,
                y + self.radius,
            )
        if self.shape_type == "polygon" and self.points:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            min_x = min(xs)
            min_y = min(ys)
            max_x = max(xs)
            max_y = max(ys)
            return (
                x + min_x,
                y + min_y,
                x + max_x,
                y + max_y,
            )
        half_w = self.width / 2
        half_h = self.height / 2
        return (
            x - half_w,
            y - half_h,
            x + half_w,
            y + half_h,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape_type": self.shape_type,
            "width": self.width,
            "height": self.height,
            "radius": self.radius,
            "points": list(self.points),
            "disabled": self.disabled,
            "one_way_collision": self.one_way_collision,
            "one_way_collision_margin": self.one_way_collision_margin,
            "one_way_collision_direction_y": self.one_way_collision_direction_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollisionShape2D":
        return cls(
            shape_type=data.get("shape_type", "box"),
            width=data.get("width", 32.0),
            height=data.get("height", 32.0),
            radius=data.get("radius", 16.0),
            points=data.get("points", []),
            disabled=data.get("disabled", False),
            one_way_collision=data.get("one_way_collision", False),
            one_way_collision_margin=data.get("one_way_collision_margin", 1.0),
            one_way_collision_direction_y=data.get("one_way_collision_direction_y", -1.0),
        )
