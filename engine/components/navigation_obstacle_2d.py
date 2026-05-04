"""engine/components/navigation_obstacle_2d.py — NavigationObstacle2D component (Godot NavigationObstacle2D)."""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class NavigationObstacle2D(Component):
    """Dynamic obstacle that blocks navigation when active.

    Godot mapping: NavigationObstacle2D node.
    Entities with this component are treated as obstacles for pathfinding
    and avoidance calculations.
    """

    def __init__(
        self,
        radius: float = 32.0,
        estimated: bool = False,
        affect_navigation: bool = True,
        affect_avoidance: bool = True,
    ) -> None:
        self.radius: float = float(radius)
        self.estimated: bool = bool(estimated)
        self.affect_navigation: bool = bool(affect_navigation)
        self.affect_avoidance: bool = bool(affect_avoidance)

        # Runtime velocity (set by physics/movement systems)
        self._velocity_x: float = 0.0
        self._velocity_y: float = 0.0

    def set_velocity(self, vx: float, vy: float) -> None:
        self._velocity_x = float(vx)
        self._velocity_y = float(vy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "radius": self.radius,
            "estimated": self.estimated,
            "affect_navigation": self.affect_navigation,
            "affect_avoidance": self.affect_avoidance,
            "_velocity_x": self._velocity_x,
            "_velocity_y": self._velocity_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NavigationObstacle2D":
        return cls(
            radius=data.get("radius", 32.0),
            estimated=data.get("estimated", False),
            affect_navigation=data.get("affect_navigation", True),
            affect_avoidance=data.get("affect_avoidance", True),
        )
