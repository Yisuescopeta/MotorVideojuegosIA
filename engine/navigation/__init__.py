"""
engine/navigation/__init__.py - Navigation/Pathfinding module

PUBLIC API:
    - NavigationGrid       : Grid data structure for navigation
    - NeighborMode         : Canonical neighbor expansion policy
    - PathRequest          : Canonical pathfinding request
    - PathResult           : Canonical pathfinding result
    - AStarPathfinder      : A* pathfinding on NavigationGrid
    - NavigationService    : High-level query facade
    - NavigationQuery      : Compatibility alias for PathResult
    - Vec2                 : 2D integer coordinate

STATUS: experimental/tooling (per docs/module_taxonomy.md)
"""

from __future__ import annotations

from engine.navigation.astar import AStarPathfinder
from engine.navigation.grid import NavigationGrid, Vec2
from engine.navigation.service import NavigationQuery, NavigationService
from engine.navigation.types import NeighborMode, PathRequest, PathResult

__all__ = [
    "AStarPathfinder",
    "NeighborMode",
    "NavigationGrid",
    "NavigationQuery",
    "NavigationService",
    "PathRequest",
    "PathResult",
    "Vec2",
]
