"""engine/components/navigation_obstacle_2d.py — NavigationObstacle2D component (Godot NavigationObstacle2D)."""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class NavigationObstacle2D(Component):
    """Static obstacle that blocks navigation agents.

    Godot mapping: NavigationObstacle2D node.
    Provides radius and affect_avoidance for local avoidance in NavigationAgentSystem.
    """

    def __init__(self, radius: float = 0.0, affect_avoidance: bool = True) -> None:
        self.radius: float = float(radius)
        self.affect_avoidance: bool = bool(affect_avoidance)

    def to_dict(self) -> dict[str, Any]:
        return {
            "radius": self.radius,
            "affect_avoidance": self.affect_avoidance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NavigationObstacle2D":
        return cls(
            radius=float(data.get("radius", 0.0)),
            affect_avoidance=bool(data.get("affect_avoidance", True)),
        )
