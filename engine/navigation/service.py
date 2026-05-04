"""
engine/navigation/service.py - High-level navigation query facade

Provides a stable query API on top of NavigationGrid + AStarPathfinder.
Designed for use by AI agents, scripts, and future runtime integration.
"""

from __future__ import annotations

import heapq
from typing import Optional

from engine.navigation.astar import AStarPathfinder
from engine.navigation.grid import NavigationGrid, Vec2
from engine.navigation.types import (
    NavigationPathfinder,
    NeighborMode,
    PathRequest,
    PathResult,
)

NavigationQuery = PathResult


class NavigationService:
    """
    High-level navigation facade.

    Holds a NavigationGrid and an AStarPathfinder.
    Provides canonical request/result path queries plus compatibility wrappers.

    NOTE: In this initial version, the grid must be set manually
    (no automatic tilemap integration). Future phases will add
    tilemap-aware grid generation.
    """

    def __init__(
        self,
        grid: Optional[NavigationGrid] = None,
        pathfinder: Optional[NavigationPathfinder] = None,
    ) -> None:
        self._grid = grid
        self._pathfinder: NavigationPathfinder = pathfinder or AStarPathfinder(grid)
        self._pathfinder.grid = grid

    @property
    def grid(self) -> Optional[NavigationGrid]:
        return self._grid

    @property
    def pathfinder(self) -> NavigationPathfinder:
        return self._pathfinder

    def set_grid(self, grid: NavigationGrid) -> None:
        self._grid = grid
        self._pathfinder.grid = grid

    def set_pathfinder(self, pathfinder: NavigationPathfinder) -> None:
        self._pathfinder = pathfinder
        self._pathfinder.grid = self._grid

    def request_path(self, request: PathRequest) -> PathResult:
        """Canonical request/result API for pathfinding."""
        self._pathfinder.grid = self._grid
        return self._pathfinder.request_path(request)

    def query_path(
        self,
        start_x: int,
        start_y: int,
        goal_x: int,
        goal_y: int,
        diagonal: bool = True,
    ) -> NavigationQuery:
        """Compatibility wrapper over the canonical request/result API."""
        request = PathRequest.from_diagonal(
            start=Vec2(start_x, start_y),
            goal=Vec2(goal_x, goal_y),
            diagonal=diagonal,
        )
        return self.request_path(request)

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
        return self.request_path(
            PathRequest.from_diagonal(start, goal, diagonal=diagonal)
        )

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
        neighbor_mode = NeighborMode.from_diagonal(diagonal)

        while queue:
            current_cost, _, current = heapq.heappop(queue)
            if current_cost > max_cost:
                continue

            for neighbor, is_diag in self._grid.neighbors(current, neighbor_mode):
                if neighbor in visited:
                    continue
                new_cost = current_cost + self._grid.move_cost(
                    neighbor,
                    diagonal=is_diag,
                )
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
                for neighbor, _ in self._grid.neighbors(pos, NeighborMode.CARDINAL_4):
                    if neighbor not in node_index:
                        continue
                    to_id = node_index[neighbor]
                    cost = self._grid.move_cost(neighbor, diagonal=False)
                    edges.append({"from": from_id, "to": to_id, "cost": cost, "diagonal": False})

        return {"nodes": nodes, "edges": edges}
