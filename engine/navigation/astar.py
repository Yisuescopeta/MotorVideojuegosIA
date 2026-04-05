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
    def grid(self, value: NavigationGrid) -> None:
        self._grid = value

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
        if self._grid is None:
            return []

        if not self._grid.in_bounds_vec(start) or not self._grid.in_bounds_vec(goal):
            return []

        if not self._grid.is_walkable_vec(start) or not self._grid.is_walkable_vec(goal):
            return []

        if start == goal:
            return [start]

        counter = 0
        open_set: list[tuple[int, int, Vec2]] = []
        came_from: dict[Vec2, Vec2 | None] = {start: None}
        g_score: dict[Vec2, int] = {start: 0}
        f_score: dict[Vec2, int] = {start: self._heuristic(start, goal)}

        heapq.heappush(open_set, (f_score[start], counter, start))
        counter += 1

        iterations = 0
        while open_set:
            if max_iterations > 0 and iterations >= max_iterations:
                return []

            iterations += 1
            _, _, current = heapq.heappop(open_set)

            if current == goal:
                return self._reconstruct_path(came_from, current)

            for neighbor, is_diagonal in self._get_neighbors(current, diagonal):
                if is_diagonal and not self._is_diagonal_move_allowed(current, neighbor):
                    continue

                move_cost = self._move_cost(neighbor, is_diagonal)
                tentative_g = g_score[current] + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self._heuristic(neighbor, goal)
                    f_score[neighbor] = f
                    heapq.heappush(open_set, (f, counter, neighbor))
                    counter += 1

        return []

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
        path = self.find_path(start, goal, diagonal, max_iterations)
        if not path:
            return [], -1
        cost = self._calculate_path_cost(path, diagonal)
        return path, cost

    def _get_neighbors(
        self, pos: Vec2, diagonal: bool
    ) -> list[tuple[Vec2, bool]]:
        assert self._grid is not None
        if diagonal:
            return list(self._grid.neighbors_8(pos))
        return list(self._grid.neighbors_4(pos))

    def _is_diagonal_move_allowed(self, from_pos: Vec2, to_pos: Vec2) -> bool:
        """Check if diagonal move is allowed (no corner cutting)."""
        assert self._grid is not None
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

    def _heuristic(self, pos: Vec2, goal: Vec2) -> int:
        dx = abs(pos.x - goal.x)
        dy = abs(pos.y - goal.y)
        return CARDINAL_COST * (dx + dy) + (DIAGONAL_COST - 2 * CARDINAL_COST) * min(dx, dy)

    def _move_cost(self, pos: Vec2, diagonal: bool) -> int:
        assert self._grid is not None
        cell = self._grid.get_cell_vec(pos)
        base = DIAGONAL_COST if diagonal else CARDINAL_COST
        return (base * cell.cost_multiplier) // 100

    def _calculate_path_cost(self, path: list[Vec2], diagonal: bool) -> int:
        if len(path) < 2:
            return 0
        total = 0
        for i in range(1, len(path)):
            prev = path[i - 1]
            curr = path[i]
            is_diagonal = curr.x != prev.x and curr.y != prev.y
            total += self._move_cost(curr, is_diagonal)
        return total

    def _reconstruct_path(
        self, came_from: dict[Vec2, Vec2 | None], current: Vec2
    ) -> list[Vec2]:
        path = [current]
        while came_from[current] is not None:
            prev = came_from[current]
            assert prev is not None
            current = prev
            path.append(current)
        path.reverse()
        return path

    def is_path_valid(self, path: list[Vec2]) -> bool:
        """Check if a path is valid (all cells walkable)."""
        assert self._grid is not None
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
