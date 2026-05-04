"""engine/resources/navigation_polygon.py — NavigationPolygon resource (Godot NavigationPolygon).

Defines a polygon that marks navigable area for pathfinding and avoidance.
Referenced by NavigationRegion2D components and TileSet navigation layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Tuple


@dataclass
class NavigationPolygon:
    """Polygon defining navigable area.

    Uses triangulated polygons (Godot-style navigation mesh).
    Vertices in world/pixel coordinates. Polygons are index triples.
    """

    resource_id: str = ""
    resource_name: str = "New NavigationPolygon"
    vertices: List[Tuple[float, float]] = field(default_factory=list)
    polygons: List[List[int]] = field(default_factory=list)
    agent_radius: float = 10.0
    border_size: float = 0.0

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def polygon_count(self) -> int:
        return len(self.polygons)

    def add_vertex(self, x: float, y: float) -> int:
        idx = len(self.vertices)
        self.vertices.append((float(x), float(y)))
        return idx

    def add_polygon(self, indices: List[int]) -> None:
        self.polygons.append(list(int(i) for i in indices))

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "vertices": [list(v) for v in self.vertices],
            "polygons": [list(p) for p in self.polygons],
            "agent_radius": self.agent_radius,
            "border_size": self.border_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NavigationPolygon":
        return cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "New NavigationPolygon")),
            vertices=[tuple(float(c) for c in v) for v in data.get("vertices", [])],
            polygons=[list(int(i) for i in p) for p in data.get("polygons", [])],
            agent_radius=float(data.get("agent_radius", 10.0)),
            border_size=float(data.get("border_size", 0.0)),
        )

    @classmethod
    def from_rect(
        cls,
        x: float,
        y: float,
        width: float,
        height: float,
        resource_id: str = "",
    ) -> "NavigationPolygon":
        """Create a rectangular navigation polygon (common case)."""
        return cls(
            resource_id=resource_id,
            vertices=[
                (x, y),
                (x + width, y),
                (x + width, y + height),
                (x, y + height),
            ],
            polygons=[
                [0, 1, 2],
                [0, 2, 3],
            ],
        )

    def __repr__(self) -> str:
        return (
            f"NavigationPolygon(id={self.resource_id!r}, "
            f"resource_name={self.resource_name!r}, "
            f"vertices={len(self.vertices)}, polygons={len(self.polygons)})"
        )
