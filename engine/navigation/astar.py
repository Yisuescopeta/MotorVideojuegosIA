"""
engine/navigation/astar.py - A* pathfinding implementation

Pure algorithm, no engine dependencies.
Works on NavigationGrid instances.
"""

from __future__ import annotations

import heapq
from typing import Optional

from engine.navigation.grid import (
    CARDINAL_COST,
    DIAGONAL_COST,
    NavigationGrid,
    Vec2,
)
from engine.navigation.types import NeighborMode, PathRequest, PathResult


class AStarPathfinder:
    """
    A* pathfinder operating on a NavigationGrid.

    Supports 4-directional and 8-directional movement.
    Movement costs are per-cell (tile cost multiplier on base movement cost).
    """

    def __init__(self, grid: Optional[NavigationGrid] = None) -> None:
        self._grid = grid

    @property
    def grid(self) -> Optional[NavigationGrid]:
        return self._grid

    @grid.setter
    def grid(self, value: Optional[NavigationGrid]) -> None:
        self._grid = value

    def request_path(self, request: PathRequest) -> PathResult:
        """Resolve a canonical path request into a canonical result."""
        if self._grid is None:
            return PathResult.failure("No navigation grid set")

        start = request.start
        goal = request.goal
        if not self._grid.in_bounds_vec(start):
            return PathResult.failure(f"Start {start} out of bounds")
        if not self._grid.in_bounds_vec(goal):
            return PathResult.failure(f"Goal {goal} out of bounds")
        if not self._grid.is_walkable_vec(start):
            return PathResult.failure(f"Start {start} is not walkable")
        if not self._grid.is_walkable_vec(goal):
            return PathResult.failure(f"Goal {goal} is not walkable")
        if start == goal:
            return PathResult.success_result([start], 0)

        counter = 0
        open_set: list[tuple[int, int, Vec2]] = []
        came_from: dict[Vec2, Vec2 | None] = {start: None}
        g_score: dict[Vec2, int] = {start: 0}
        f_score: dict[Vec2, int] = {
            start: self._heuristic(start, goal, request.neighbor_mode)
        }

        heapq.heappush(open_set, (f_score[start], counter, start))
        counter += 1

        iterations = 0
        while open_set:
            if request.max_iterations > 0 and iterations >= request.max_iterations:
                return PathResult.failure("Path search exceeded iteration budget")

            iterations += 1
            _, _, current = heapq.heappop(open_set)

            if current == goal:
                path = self._reconstruct_path(came_from, current)
                cost = self._calculate_path_cost(path)
                return PathResult.success_result(path, cost)

            for neighbor, is_diagonal in self._get_neighbors(
                current,
                request.neighbor_mode,
            ):
                if is_diagonal and not self._is_diagonal_move_allowed(current, neighbor):
                    continue

                tentative_g = g_score[current] + self._move_cost(neighbor, is_diagonal)

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self._heuristic(
                        neighbor,
                        goal,
                        request.neighbor_mode,
                    )
                    f_score[neighbor] = f
                    heapq.heappush(open_set, (f, counter, neighbor))
                    counter += 1

        return PathResult.failure("No path found")

    def find_path(
        self,
        start: Vec2,
        goal: Vec2,
        diagonal: bool = True,
        max_iterations: int = 0,
    ) -> list[Vec2]:
        """
        Find shortest path from start to goal using A*.

        Args:
            start: Starting grid coordinate
            goal: Target grid coordinate
            diagonal: Allow diagonal movement if True
            max_iterations: Cap iterations (0 = unlimited)

        Returns:
            List of grid positions from start to goal (inclusive),
            or empty list if no path found.
        """
        request = PathRequest.from_diagonal(
            start=start,
            goal=goal,
            diagonal=diagonal,
            max_iterations=max_iterations,
        )
        result = self.request_path(request)
        return result.path if result.success else []

    def find_path_with_cost(
        self,
        start: Vec2,
        goal: Vec2,
        diagonal: bool = True,
        max_iterations: int = 0,
    ) -> tuple[list[Vec2], int]:
        """
        Find path and return cost. Returns ([], -1) on failure.
        """
        request = PathRequest.from_diagonal(
            start=start,
            goal=goal,
            diagonal=diagonal,
            max_iterations=max_iterations,
        )
        result = self.request_path(request)
        if not result.success:
            return [], -1
        return result.path, result.cost

    def _get_neighbors(
        self,
        pos: Vec2,
        neighbor_mode: NeighborMode,
    ) -> list[tuple[Vec2, bool]]:
        if self._grid is None:
            raise RuntimeError("AStarPathfinder._get_neighbors: grid is not set")
        return list(self._grid.neighbors(pos, neighbor_mode))

    def _is_diagonal_move_allowed(self, from_pos: Vec2, to_pos: Vec2) -> bool:
        """Check if diagonal move is allowed (no corner cutting)."""
        if self._grid is None:
            raise RuntimeError("AStarPathfinder._is_diagonal_move_allowed: grid is not set")
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        if dx == 0 or dy == 0:
            return True
        blocking_dx = Vec2(dx, 0)
        blocking_dy = Vec2(0, dy)
        return (
            self._grid.is_walkable_vec(from_pos + blocking_dx)
            and self._grid.is_walkable_vec(from_pos + blocking_dy)
        )

    def _heuristic(
        self,
        pos: Vec2,
        goal: Vec2,
        neighbor_mode: NeighborMode,
    ) -> int:
        dx = abs(pos.x - goal.x)
        dy = abs(pos.y - goal.y)
        if not neighbor_mode.allows_diagonal:
            return CARDINAL_COST * (dx + dy)
        diagonal_steps = min(dx, dy)
        straight_steps = max(dx, dy) - diagonal_steps
        return diagonal_steps * DIAGONAL_COST + straight_steps * CARDINAL_COST

    def _move_cost(self, pos: Vec2, diagonal: bool) -> int:
        if self._grid is None:
            raise RuntimeError("AStarPathfinder._move_cost: grid is not set")
        return self._grid.move_cost(pos, diagonal=diagonal)

    def _calculate_path_cost(
        self,
        path: list[Vec2],
        diagonal: bool | None = None,
    ) -> int:
        if len(path) < 2:
            return 0
        total = 0
        for i in range(1, len(path)):
            prev = path[i - 1]
            curr = path[i]
            total += self._grid.move_cost_between(prev, curr)
        return total

    def _reconstruct_path(
        self, came_from: dict[Vec2, Vec2 | None], current: Vec2
    ) -> list[Vec2]:
        path = [current]
        while came_from[current] is not None:
            prev = came_from[current]
            if prev is None:
                raise RuntimeError("AStarPathfinder._reconstruct_path: unexpected None predecessor")
            current = prev
            path.append(current)
        path.reverse()
        return path

    def is_path_valid(self, path: list[Vec2]) -> bool:
        """Check if a path is valid (all cells walkable)."""
        if self._grid is None:
            raise RuntimeError("AStarPathfinder.is_path_valid: grid is not set")
        if not path:
            return False
        for pos in path:
            if not self._grid.in_bounds_vec(pos) or not self._grid.is_walkable_vec(pos):
                return False
        return True

    def get_line_of_sight(self, start: Vec2, goal: Vec2) -> bool:
        """
        Check if there's a clear line of sight between two positions (no obstacles).
        Uses Bresenham-like check for 8-connectivity.
        """
        if self._grid is None:
            return False
        if not self._grid.in_bounds_vec(start) or not self._grid.in_bounds_vec(goal):
            return False
        if not self._grid.is_walkable_vec(start) or not self._grid.is_walkable_vec(goal):
            return False

        dx = abs(goal.x - start.x)
        dy = abs(goal.y - start.y)
        sx = 1 if start.x < goal.x else -1
        sy = 1 if start.y < goal.y else -1
        err = dx - dy

        x, y = start.x, start.y
        while True:
            if x == goal.x and y == goal.y:
                return True
            if not self._grid.is_walkable(x, y):
                return False

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
