"""engine/components/navigation_region_2d.py — NavigationRegion2D component (Godot NavigationRegion2D)."""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class NavigationRegion2D(Component):
    """Defines a navigable region with cost modifiers for pathfinding.

    Godot mapping: NavigationRegion2D node.
    References a NavigationPolygon resource that defines the walkable area.
    """

    def __init__(
        self,
        navigation_polygon_path: str = "",
        enabled: bool = True,
        enter_cost: float = 0.0,
        travel_cost: float = 0.0,
        navigation_layers: int = 1,
    ) -> None:
        self.navigation_polygon_path: str = str(navigation_polygon_path)
        self.enabled: bool = bool(enabled)
        self.enter_cost: float = float(enter_cost)
        self.travel_cost: float = float(travel_cost)
        self.navigation_layers: int = max(1, int(navigation_layers))

    def to_dict(self) -> dict[str, Any]:
        return {
            "navigation_polygon_path": self.navigation_polygon_path,
            "enabled": self.enabled,
            "enter_cost": self.enter_cost,
            "travel_cost": self.travel_cost,
            "navigation_layers": self.navigation_layers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NavigationRegion2D":
        return cls(
            navigation_polygon_path=data.get("navigation_polygon_path", ""),
            enabled=data.get("enabled", True),
            enter_cost=data.get("enter_cost", 0.0),
            travel_cost=data.get("travel_cost", 0.0),
            navigation_layers=data.get("navigation_layers", 1),
        )
