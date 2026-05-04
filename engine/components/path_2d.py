"""
engine/components/path_2d.py - Path2D visual component.

Defines a Curve2D path for PathFollow2D. Rendered as connected lines
in debug color by the render system.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class Path2D(Component):
    """Godot Path2D — defines a Curve2D path for PathFollow2D."""

    def __init__(
        self,
        curve_points: list[tuple[float, float]] | None = None,
        closed: bool = False,
    ) -> None:
        self.curve_points: list[tuple[float, float]] = [
            (float(p[0]), float(p[1])) for p in (curve_points or [])
            if isinstance(p, (tuple, list)) and len(p) >= 2
        ]
        self.closed: bool = bool(closed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "curve_points": [list(p) for p in self.curve_points],
            "closed": self.closed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Path2D":
        raw_points = data.get("curve_points", [])
        points: list[tuple[float, float]] = []
        if isinstance(raw_points, list):
            points = [
                (float(p[0]), float(p[1]))
                for p in raw_points
                if isinstance(p, (tuple, list)) and len(p) >= 2
            ]
        return cls(
            curve_points=points,
            closed=bool(data.get("closed", False)),
        )
