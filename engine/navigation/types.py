"""
engine/navigation/types.py - Canonical navigation/pathfinding contracts

Small, grid-first request/result types intended to stay stable while
algorithms and integrations evolve in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from engine.navigation.grid import NavigationGrid, Vec2


class NeighborMode(str, Enum):
    """Neighbor expansion policy for grid-based pathfinding."""

    CARDINAL_4 = "cardinal_4"
    EIGHT_WAY = "eight_way"

    @property
    def allows_diagonal(self) -> bool:
        return self is NeighborMode.EIGHT_WAY

    @classmethod
    def from_diagonal(cls, diagonal: bool) -> NeighborMode:
        return cls.EIGHT_WAY if diagonal else cls.CARDINAL_4

    @classmethod
    def from_value(cls, value: NeighborMode | str) -> NeighborMode:
        if isinstance(value, cls):
            return value
        return cls(value)


@dataclass(frozen=True, slots=True)
class PathRequest:
    """Canonical pathfinding request."""

    start: Vec2
    goal: Vec2
    neighbor_mode: NeighborMode = NeighborMode.EIGHT_WAY
    max_iterations: int = 0

    @property
    def allows_diagonal(self) -> bool:
        return self.neighbor_mode.allows_diagonal

    @classmethod
    def from_diagonal(
        cls,
        start: Vec2,
        goal: Vec2,
        diagonal: bool = True,
        max_iterations: int = 0,
    ) -> PathRequest:
        return cls(
            start=start,
            goal=goal,
            neighbor_mode=NeighborMode.from_diagonal(diagonal),
            max_iterations=max_iterations,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": {"x": self.start.x, "y": self.start.y},
            "goal": {"x": self.goal.x, "y": self.goal.y},
            "neighbor_mode": self.neighbor_mode.value,
            "max_iterations": self.max_iterations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PathRequest:
        from engine.navigation.grid import Vec2

        start_data = data.get("start", {})
        goal_data = data.get("goal", {})
        return cls(
            start=Vec2(int(start_data.get("x", 0)), int(start_data.get("y", 0))),
            goal=Vec2(int(goal_data.get("x", 0)), int(goal_data.get("y", 0))),
            neighbor_mode=NeighborMode.from_value(
                data.get("neighbor_mode", NeighborMode.EIGHT_WAY.value)
            ),
            max_iterations=int(data.get("max_iterations", 0)),
        )


@dataclass(slots=True)
class PathResult:
    """Canonical pathfinding result."""

    path: list[Vec2] = field(default_factory=list)
    cost: int = -1
    success: bool = False
    message: str = ""

    @classmethod
    def success_result(
        cls,
        path: list[Vec2],
        cost: int,
        message: str = "Path found",
    ) -> PathResult:
        return cls(path=list(path), cost=cost, success=True, message=message)

    @classmethod
    def failure(cls, message: str) -> PathResult:
        return cls(path=[], cost=-1, success=False, message=message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "cost": self.cost,
            "path": [{"x": p.x, "y": p.y} for p in self.path],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PathResult:
        from engine.navigation.grid import Vec2

        path = [
            Vec2(int(point.get("x", 0)), int(point.get("y", 0)))
            for point in data.get("path", [])
        ]
        return cls(
            path=path,
            cost=int(data.get("cost", -1)),
            success=bool(data.get("success", False)),
            message=str(data.get("message", "")),
        )


class NavigationPathfinder(Protocol):
    """Minimal extension point for future navigation algorithms."""

    grid: NavigationGrid | None

    def request_path(self, request: PathRequest) -> PathResult:
        ...

    def get_line_of_sight(self, start: Vec2, goal: Vec2) -> bool:
        ...
