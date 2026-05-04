"""
engine/components/collision_polygon_2d.py - CollisionPolygon2D component (Godot parity)

PROPÓSITO:
    Polygon collision shape built from vertex data. Supports solids (filled)
    and segments (edges) build modes.

PROPIEDADES:
    - polygon: List of (x, y) vertex tuples defining the collision shape
    - build_mode: "solids" (filled polygon) or "segments" (edge-only)
    - disabled: Whether this shape is disabled
    - one_way_collision: One-way collision flag

SERIALIZACIÓN JSON:
    {
        "polygon": [],
        "build_mode": "solids",
        "disabled": false,
        "one_way_collision": false
    }
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class CollisionPolygon2D(Component):
    """Godot CollisionPolygon2D — polygon collision shape from vertices."""

    def __init__(
        self,
        polygon: list | None = None,
        build_mode: str = "solids",
        disabled: bool = False,
        one_way_collision: bool = False,
    ) -> None:
        self.polygon: list = list(polygon) if polygon else []
        self.build_mode: str = str(build_mode or "solids")
        self.disabled: bool = bool(disabled)
        self.one_way_collision: bool = bool(one_way_collision)

    def get_bounds(self, x: float, y: float) -> tuple[float, float, float, float]:
        """Calcula los límites AABB del polígono en coordenadas mundo."""
        if not self.polygon:
            return (x, y, x, y)
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        return (
            x + min(xs),
            y + min(ys),
            x + max(xs),
            y + max(ys),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "polygon": list(self.polygon),
            "build_mode": self.build_mode,
            "disabled": self.disabled,
            "one_way_collision": self.one_way_collision,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollisionPolygon2D":
        return cls(
            polygon=data.get("polygon", []),
            build_mode=data.get("build_mode", "solids"),
            disabled=data.get("disabled", False),
            one_way_collision=data.get("one_way_collision", False),
        )
