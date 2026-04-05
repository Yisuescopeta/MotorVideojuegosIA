# Navigation / Pathfinding Module

## Status

**experimental/tooling** — This module is not part of the core motor contract.
It is a standalone pathfinding infrastructure that can grow to integrate
with Tilemap and physics in future phases.

## Overview

The navigation module provides:

- **NavigationGrid**: A 2D tile-based grid for navigation data
- **AStarPathfinder**: A* pathfinding algorithm on NavigationGrid
- **NavigationService**: High-level query facade
- **Vec2**: Immutable 2D integer coordinate

## Quick Start

```python
from engine.navigation import NavigationGrid, NavigationService, Vec2

# Create a 5x5 open grid
grid = NavigationGrid.from_walkable_matrix([
    [True, True, True, True, True],
    [True, True, True, True, True],
    [True, True, True, True, True],
    [True, True, True, True, True],
    [True, True, True, True, True],
])

# Query a path
svc = NavigationService(grid)
result = svc.query_path(0, 0, 4, 4)
print(result.success, result.path, result.cost)
```

## Architecture

### Vec2

Immutable 2D integer coordinate with vector math operations:
`+`, `-`, `*`, `manhattan_distance`, `chebyshev_distance`.

### NavigationGrid

Tile-based 2D grid:
- `width`, `height`, `cell_size` (world units per tile)
- Per-cell: `walkable` (bool) + `cost_multiplier` (int, default=100)
- `world_to_grid(x, y)` → Vec2
- `grid_to_world_center(col, row)` → (float, float)
- `neighbors_4(pos)` / `neighbors_8(pos)` for graph traversal

### AStarPathfinder

A* algorithm on NavigationGrid:
- 4-directional or 8-directional movement
- Per-cell cost multipliers (terrain cost)
- Diagonal corner-cutting prevention (8-directional)
- Line-of-sight check (Bresenham-based)
- Max iterations cap for budgeted queries

### NavigationService

Facade providing:
- `query_path(x1, y1, x2, y2, diagonal=True)` → NavigationQuery
- `query_world_path(wx1, wy1, wx2, wy2)` → NavigationQuery (world coords)
- `has_line_of_sight(x1, y1, x2, y2)` → bool
- `get_reachable_positions(x, y, max_cost)` → list[Vec2]
- `build_navmesh_from_grid()` → mesh-like dict for AI/external consumers

## Serialization

NavigationGrid is serializable to/from dict and JSON:

```python
data = grid.to_dict()
restored = NavigationGrid.from_dict(data)
grid.to_json("path/to/navgrid.json")
restored = NavigationGrid.from_json("path/to/navgrid.json")
```

## Phase 2 Integration Points

When integrating with **Tilemap**:

1. `NavigationGrid.from_tilemap(tilemap_component)` — generate navigation
   grid from tile properties (e.g., tile `navigation` tag)
2. Hook into `TilemapComponent.on_tile_changed` to invalidate/rebuild grid
3. Register `NavigationService` in `Game` or `HeadlessGame` for runtime queries

When integrating with **Physics**:

1. Use `ColliderComponent` bounds to mark cells as blocked
2. `NavigationSystem` could receive collision events and update walkability
3. Alternatively, keep navigation walkability independent (navmesh vs physics body)

When integrating with **RuntimeController**:

1. `NavigationService` is a query-only facade — it doesn't tick
2. `AISystem` or `ScriptBehaviourComponent` can call `NavigationService.query_path()`
   every frame or on demand
3. `NavigationQuery.path` returns `list[Vec2]` in grid coordinates; caller
   converts to world waypoints

## What This Module Is NOT

- Not coupled to physics or Tilemap in this phase
- Not a runtime system that ticks each frame
- Not a NavMesh in the traditional 3D sense (uses tile grid instead)

## Module Location

`engine/navigation/`
- `__init__.py` — public exports
- `grid.py` — Vec2 + NavigationGrid
- `astar.py` — AStarPathfinder
- `service.py` — NavigationService facade
