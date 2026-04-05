"""
engine/navigation/service.py - High-level navigation query facade

Provides a stable query API on top of NavigationGrid + AStarPathfinder.
Designed for use by AI agents, scripts, and future runtime integration.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Optional

from engine.navigation.astar import AStarPathfinder
from engine.navigation.grid import CARDINAL_COST, DIAGONAL_COST, NavigationGrid, Vec2


@dataclass
class NavigationQuery:
    """Result of a navigation query."""

    path: list[Vec2]
    cost: int
    success: bool
    message: str

    @classmethod
    def success_result(cls, path: list[Vec2], cost: int) -> NavigationQuery:
        return cls(path=path, cost=cost, success=True, message="Path found")

    @classmethod
    def failure(cls, message: str) -> NavigationQuery:
        return cls(path=[], cost=-1, success=False, message=message)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "cost": self.cost,
            "path": [{"x": p.x, "y": p.y} for p in self.path],
        }


class NavigationService:
    """
    High-level navigation facade.

    Holds a NavigationGrid and an AStarPathfinder.
    Provides query methods that return NavigationQuery results.

    NOTE: In this initial version, the grid must be set manually
    (no automatic tilemap integration). Future phases will add
    tilemap-aware grid generation.
    """

    def __init__(self, grid: Optional[NavigationGrid] = None) -> None:
        self._grid = grid
        self._pathfinder = AStarPathfinder(grid)

    @property
    def grid(self) -> Optional[NavigationGrid]:
        return self._grid

    def set_grid(self, grid: NavigationGrid) -> None:
        self._grid = grid
        self._pathfinder.grid = grid

    def query_path(
        self,
        start_x: int,
        start_y: int,
        goal_x: int,
        goal_y: int,
        diagonal: bool = True,
    ) -> NavigationQuery:
        """
        Find a path between two grid positions.

        Args:
            start_x, start_y: Start position in grid coordinates
            goal_x, goal_y: Goal position in grid coordinates
            diagonal: Allow diagonal movement

        Returns:
            NavigationQuery with path, cost, and status
        """
        if self._grid is None:
            return NavigationQuery.failure("No navigation grid set")

        start = Vec2(start_x, start_y)
        goal = Vec2(goal_x, goal_y)

        if not self._grid.in_bounds_vec(start):
            return NavigationQuery.failure(f"Start {start} out of bounds")
        if not self._grid.in_bounds_vec(goal):
            return NavigationQuery.failure(f"Goal {goal} out of bounds")
        if not self._grid.is_walkable_vec(start):
            return NavigationQuery.failure(f"Start {start} is not walkable")
        if not self._grid.is_walkable_vec(goal):
            return NavigationQuery.failure(f"Goal {goal} is not walkable")

        path, cost = self._pathfinder.find_path_with_cost(start, goal, diagonal=diagonal)

        if not path:
            return NavigationQuery.failure("No path found")

        return NavigationQuery.success_result(path, cost)

    def query_world_path(
        self,
        wx_start: float,
        wy_start: float,
        wx_goal: float,
        wy_goal: float,
        diagonal: bool = True,
    ) -> NavigationQuery:
        """
        Find a path between two world positions.
        Converts world -> grid, queries, returns grid path.
        """
        if self._grid is None:
            return NavigationQuery.failure("No navigation grid set")

        start = self._grid.world_to_grid(wx_start, wy_start)
        goal = self._grid.world_to_grid(wx_goal, wy_goal)
        return self.query_path(start.x, start.y, goal.x, goal.y, diagonal=diagonal)

    def has_line_of_sight(
        self,
        start_x: int,
        start_y: int,
        goal_x: int,
        goal_y: int,
    ) -> bool:
        """Check if two grid positions have clear line of sight."""
        if self._grid is None:
            return False
        return self._pathfinder.get_line_of_sight(Vec2(start_x, start_y), Vec2(goal_x, goal_y))

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if a grid cell is walkable."""
        if self._grid is None:
            return False
        return self._grid.is_walkable(x, y)

    def get_reachable_positions(
        self,
        start_x: int,
        start_y: int,
        max_cost: int,
        diagonal: bool = True,
    ) -> list[Vec2]:
        """
        Flood-fill to find all positions reachable within max_cost from start.
        Useful for AI awareness / movement range queries.
        """
        if self._grid is None:
            return []

        start = Vec2(start_x, start_y)
        if not self._grid.in_bounds_vec(start) or not self._grid.is_walkable_vec(start):
            return []

        visited: dict[Vec2, int] = {start: 0}
        counter = 0
        queue: list[tuple[int, int, Vec2]] = [(0, counter, start)]
        counter += 1

        while queue:
            current_cost, _, current = heapq.heappop(queue)
            if current_cost > max_cost:
                continue

            neighbors = self._grid.neighbors_8(current) if diagonal else self._grid.neighbors_4(current)
            for neighbor, is_diag in neighbors:
                if neighbor in visited:
                    continue
                cell = self._grid.get_cell_vec(neighbor)
                base = DIAGONAL_COST if is_diag else CARDINAL_COST
                move_cost = (base * cell.cost_multiplier) // 100
                new_cost = current_cost + move_cost
                if new_cost <= max_cost:
                    visited[neighbor] = new_cost
                    heapq.heappush(queue, (new_cost, counter, neighbor))
                    counter += 1

        return list(visited.keys())

    def build_navmesh_from_grid(self) -> dict:
        """
        Export grid as a mesh-like dict for external consumers (AI, visualization).
        Returns {"nodes": [...], "edges": [...]} in grid coordinates.
        """
        if self._grid is None:
            return {"nodes": [], "edges": []}

        nodes: list[dict] = []
        edges: list[dict] = []
        node_index: dict[Vec2, int] = {}

        for col in range(self._grid.width):
            for row in range(self._grid.height):
                pos = Vec2(col, row)
                if self._grid.is_walkable_vec(pos):
                    node_id = len(nodes)
                    nodes.append({"id": node_id, "x": col, "y": row})
                    node_index[pos] = node_id

        for col in range(self._grid.width):
            for row in range(self._grid.height):
                pos = Vec2(col, row)
                if pos not in node_index:
                    continue
                from_id = node_index[pos]
                for neighbor, is_diag in self._grid.neighbors_4(pos):
                    if neighbor not in node_index:
                        continue
                    to_id = node_index[neighbor]
                    neighbor_cell = self._grid.get_cell_vec(neighbor)
                    cost = (CARDINAL_COST * neighbor_cell.cost_multiplier) // 100
                    edges.append({"from": from_id, "to": to_id, "cost": cost, "diagonal": False})

        return {"nodes": nodes, "edges": edges}
