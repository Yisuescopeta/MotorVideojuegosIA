"""
engine/navigation/__init__.py - Navigation/Pathfinding module

PUBLIC API:
    - NavigationGrid       : Grid data structure for navigation
    - AStarPathfinder      : A* pathfinding on NavigationGrid
    - NavigationService    : High-level query facade
    - NavigationQuery      : Path query result
    - Vec2                 : 2D integer coordinate

STATUS: experimental/tooling (per docs/module_taxonomy.md)
"""

from __future__ import annotations

from engine.navigation.astar import AStarPathfinder
from engine.navigation.grid import NavigationGrid, Vec2
from engine.navigation.service import NavigationQuery, NavigationService

__all__ = [
    "AStarPathfinder",
    "NavigationGrid",
    "NavigationQuery",
    "NavigationService",
    "Vec2",
]
