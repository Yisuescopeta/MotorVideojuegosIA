"""
engine/components/collision_shape_set_2d.py — Multiple collision shapes per entity

PROPÓSITO:
    Define CollisionShape2DDef (data-only, not a Component) and CollisionShapeSet2D
    (a Component) to allow multiple collision shapes on a single entity. Each shape
    can have its own type, offset, trigger flag, friction, restitution, etc.

PROPIEDADES:
    CollisionShape2DDef:
        - shape_type: "box", "circle", "capsule", "polygon"
        - offset_x / offset_y: local offset from entity transform
        - disabled: whether this shape is ignored
        - is_trigger: trigger-only (no physics blocking)
        - one_way_collision / one_way_collision_direction_y
        - friction / restitution: physical material properties
        - width, height, radius, points, capsule_height: shape geometry

    CollisionShapeSet2D:
        - shapes: list[CollisionShape2DDef]
        - get_composite_bounds(x, y): AABB enclosing all enabled non-trigger shapes
        - get_enabled_non_trigger_shapes(): filtered list

SERIALIZACIÓN JSON:
    {
        "shapes": [
            {
                "shape_type": "box",
                "offset_x": 0.0,
                "offset_y": 0.0,
                "disabled": false,
                "is_trigger": false,
                "one_way_collision": false,
                "one_way_collision_direction_y": -1.0,
                "friction": 0.2,
                "restitution": 0.0,
                "width": 32.0,
                "height": 32.0,
                "radius": 16.0,
                "points": [],
                "capsule_height": 0.0
            }
        ]
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.ecs.component import Component

AABB = tuple[float, float, float, float]


@dataclass
class CollisionShape2DDef:
    """Definition of a single collision shape. NOT a Component — pure data."""

    shape_type: str = "box"
    offset_x: float = 0.0
    offset_y: float = 0.0
    disabled: bool = False
    is_trigger: bool = False
    one_way_collision: bool = False
    one_way_collision_direction_y: float = -1.0
    friction: float = 0.2
    restitution: float = 0.0
    width: float = 32.0
    height: float = 32.0
    radius: float = 16.0
    points: list[list[float]] = field(default_factory=list)
    capsule_height: float = 0.0

    def get_bounds(self, cx: float, cy: float) -> AABB:
        """Compute world-space AABB for this shape at (cx, cy)."""
        x = cx + self.offset_x
        y = cy + self.offset_y
        st = str(self.shape_type or "box")
        if st == "capsule":
            half_h = self.radius + self.capsule_height / 2
            return (x - self.radius, y - half_h, x + self.radius, y + half_h)
        if st == "circle":
            return (x - self.radius, y - self.radius, x + self.radius, y + self.radius)
        if st == "polygon" and self.points:
            min_x = min(p[0] for p in self.points)
            min_y = min(p[1] for p in self.points)
            max_x = max(p[0] for p in self.points)
            max_y = max(p[1] for p in self.points)
            return (x + min_x, y + min_y, x + max_x, y + max_y)
        half_w = self.width / 2
        half_h = self.height / 2
        return (x - half_w, y - half_h, x + half_w, y + half_h)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape_type": self.shape_type,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "disabled": self.disabled,
            "is_trigger": self.is_trigger,
            "one_way_collision": self.one_way_collision,
            "one_way_collision_direction_y": self.one_way_collision_direction_y,
            "friction": self.friction,
            "restitution": self.restitution,
            "width": self.width,
            "height": self.height,
            "radius": self.radius,
            "points": [list(p) for p in self.points],
            "capsule_height": self.capsule_height,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollisionShape2DDef:
        return cls(
            shape_type=data.get("shape_type", "box"),
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            disabled=data.get("disabled", False),
            is_trigger=data.get("is_trigger", False),
            one_way_collision=data.get("one_way_collision", False),
            one_way_collision_direction_y=data.get("one_way_collision_direction_y", -1.0),
            friction=data.get("friction", 0.2),
            restitution=data.get("restitution", 0.0),
            width=data.get("width", 32.0),
            height=data.get("height", 32.0),
            radius=data.get("radius", 16.0),
            points=data.get("points", []),
            capsule_height=data.get("capsule_height", 0.0),
        )


class CollisionShapeSet2D(Component):
    """Multiple collision shapes for a single entity (Component)."""

    def __init__(self, shapes: list[CollisionShape2DDef] | None = None) -> None:
        self.shapes: list[CollisionShape2DDef] = list(shapes) if shapes else [
            CollisionShape2DDef(),
        ]

    def get_composite_bounds(self, x: float, y: float) -> AABB:
        """AABB enclosing all enabled non-trigger shapes."""
        enabled = self.get_enabled_non_trigger_shapes()
        if not enabled:
            return (x, y, x, y)
        first = enabled[0].get_bounds(x, y)
        left, top, right, bottom = first
        for shape in enabled[1:]:
            sb = shape.get_bounds(x, y)
            left = min(left, sb[0])
            top = min(top, sb[1])
            right = max(right, sb[2])
            bottom = max(bottom, sb[3])
        return (left, top, right, bottom)

    def get_enabled_non_trigger_shapes(self) -> list[CollisionShape2DDef]:
        return [s for s in self.shapes if not s.disabled and not s.is_trigger]

    def to_dict(self) -> dict[str, Any]:
        return {"shapes": [s.to_dict() for s in self.shapes]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollisionShapeSet2D:
        raw_shapes = data.get("shapes", [])
        shapes = [CollisionShape2DDef.from_dict(s) for s in raw_shapes]
        return cls(shapes=shapes if shapes else None)
