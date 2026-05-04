"""engine/components/navigation_agent_2d.py — NavigationAgent2D component (Godot NavigationAgent2D)."""

from __future__ import annotations

import math
from typing import Any

from engine.ecs.component import Component


class NavigationAgent2D(Component):
    """Component that navigates an entity toward a target using pathfinding.

    Godot mapping: NavigationAgent2D node.
    Requires Transform component. Pathfinding is delegated to NavigationService.
    """

    def __init__(
        self,
        enabled: bool = True,
        target_x: float = 0.0,
        target_y: float = 0.0,
        speed: float = 100.0,
        path_desired_distance: float = 20.0,
        target_reached_distance: float = 10.0,
        avoidance_radius: float = 0.0,
    ) -> None:
        self.enabled: bool = bool(enabled)
        self.target_x: float = float(target_x)
        self.target_y: float = float(target_y)
        self.speed: float = float(speed)
        self.path_desired_distance: float = float(path_desired_distance)
        self.target_reached_distance: float = float(target_reached_distance)
        self.avoidance_radius: float = float(avoidance_radius)

        # Runtime state (serializable)
        self.path: list[list[float]] = []
        self.current_path_index: int = 0
        self.is_navigation_finished: bool = True
        self.is_target_reached: bool = False
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0
        self._last_target_x: float = 0.0
        self._last_target_y: float = 0.0

    def set_target(self, target_x: float, target_y: float) -> None:
        self.target_x = float(target_x)
        self.target_y = float(target_y)

    def get_next_waypoint(self) -> tuple[float, float] | None:
        if self.current_path_index < len(self.path):
            wp = self.path[self.current_path_index]
            return (float(wp[0]), float(wp[1]))
        return None

    def distance_to_target(self, current_x: float, current_y: float) -> float:
        dx = self.target_x - current_x
        dy = self.target_y - current_y
        return math.sqrt(dx * dx + dy * dy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "speed": self.speed,
            "path_desired_distance": self.path_desired_distance,
            "target_reached_distance": self.target_reached_distance,
            "avoidance_radius": self.avoidance_radius,
            "path": [list(wp) for wp in self.path],
            "current_path_index": self.current_path_index,
            "is_navigation_finished": self.is_navigation_finished,
            "is_target_reached": self.is_target_reached,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
            "_last_target_x": self._last_target_x,
            "_last_target_y": self._last_target_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NavigationAgent2D":
        component = cls(
            enabled=data.get("enabled", True),
            target_x=data.get("target_x", 0.0),
            target_y=data.get("target_y", 0.0),
            speed=data.get("speed", 100.0),
            path_desired_distance=data.get("path_desired_distance", 20.0),
            target_reached_distance=data.get("target_reached_distance", 10.0),
            avoidance_radius=data.get("avoidance_radius", 0.0),
        )
        component.path = [list(wp) for wp in data.get("path", [])]
        component.current_path_index = int(data.get("current_path_index", 0))
        component.is_navigation_finished = bool(data.get("is_navigation_finished", True))
        component.is_target_reached = bool(data.get("is_target_reached", False))
        component.velocity_x = float(data.get("velocity_x", 0.0))
        component.velocity_y = float(data.get("velocity_y", 0.0))
        component._last_target_x = float(data.get("_last_target_x", 0.0))
        component._last_target_y = float(data.get("_last_target_y", 0.0))
        return component
