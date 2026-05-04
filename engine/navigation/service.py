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

    def build_grid_from_tileset(
        self,
        tilemap,
        tileset_resource,
        default_walkable: bool = True,
    ) -> NavigationGrid:
        """Generate navigation grid from TileSet navigation layer data.

        Walks through all layers of the tilemap, checks each tile's metadata
        in the tileset_resource for navigation data, and marks walkable cells.

        Args:
            tilemap: TilemapData instance with layers and tiles.
            tileset_resource: TileSetResource with per-tile navigation metadata.
            default_walkable: Whether cells not covered by the tilemap are walkable.

        Returns:
            NavigationGrid with walkable flags set from tileset navigation data.
        """
        from engine.tilemap.model import TileData

        cell_w = tilemap.cell_width if hasattr(tilemap, "cell_width") else 16
        cell_h = tilemap.cell_height if hasattr(tilemap, "cell_height") else 16

        # Determine grid bounds from tilemap layers
        max_x, max_y = 0, 0
        min_x, min_y = 0, 0
        found_any = False

        layers = tilemap.layers if hasattr(tilemap, "layers") else []
        for layer in layers:
            layer_tiles = layer.tiles if hasattr(layer, "tiles") else {}
            for coord in layer_tiles:
                x, y = (coord.x, coord.y) if hasattr(coord, "x") else (0, 0)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                found_any = True

        if not found_any:
            grid = NavigationGrid(1, 1, cell_w)
            grid.set_walkable(0, 0, default_walkable)
            self.set_grid(grid)
            return grid

        grid_w = max_x - min_x + 1
        grid_h = max_y - min_y + 1
        grid = NavigationGrid(grid_w, grid_h, cell_w)

        # Initialize cells to default
        for row in range(grid_h):
            for col in range(grid_w):
                grid.set_walkable(col, row, default_walkable)

        # Mark cells based on tileset navigation data
        for layer in layers:
            layer_tiles = layer.tiles if hasattr(layer, "tiles") else {}
            for coord, tile in layer_tiles.items():
                gx = (coord.x if hasattr(coord, "x") else 0) - min_x
                gy = (coord.y if hasattr(coord, "y") else 0) - min_y
                if not grid.in_bounds(gx, gy):
                    continue

                # Check per-tile metadata for navigation polygon
                source_id = ""
                tile_id = ""
                if isinstance(tile, TileData):
                    source = getattr(tile, "source", {})
                    source_id = str(source.get("source_id", "")) if isinstance(source, dict) else ""
                    tile_id = str(getattr(tile, "tile_id", ""))
                elif isinstance(tile, dict):
                    source = tile.get("source", {})
                    source_id = str(source.get("source_id", "")) if isinstance(source, dict) else ""
                    tile_id = str(tile.get("tile_id", ""))

                metadata = tileset_resource.get_tile_metadata(source_id, tile_id)
                if metadata is not None and metadata.navigation_polygon is not None:
                    grid.set_walkable(gx, gy, True)
                    # Apply cost from navigation_layer if any
                    nav_layer = getattr(tile, "navigation_layer", 0) if isinstance(tile, TileData) else tile.get("navigation_layer", 0)
                    if nav_layer > 0:
                        grid.set_cost(gx, gy, 100 + nav_layer * 5)
                else:
                    # Tiles without navigation polygon are non-walkable (walls/obstacles)
                    nav_layer = getattr(tile, "navigation_layer", 0) if isinstance(tile, TileData) else tile.get("navigation_layer", 0)
                    if nav_layer > 0:
                        grid.set_walkable(gx, gy, False)

        self.set_grid(grid)
        return grid

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
