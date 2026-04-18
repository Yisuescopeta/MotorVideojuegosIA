"""
engine/navigation/grid.py - Navigation grid data structure

Tilemap-agnostic 2D grid for pathfinding.
Each cell stores: walkability flag and movement cost multiplier.
Coordinate system: x=right, y=down (screen space).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterator

from engine.navigation.types import NeighborMode


@dataclass(frozen=True, slots=True)
class Vec2:
    """2D integer coordinate, immutable."""

    x: int
    y: int

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def __mul__(self, scalar: int) -> Vec2:
        return Vec2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: int) -> Vec2:
        return self.__mul__(scalar)

    def manhattan_distance(self, other: Vec2) -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def chebyshev_distance(self, other: Vec2) -> int:
        return max(abs(self.x - other.x), abs(self.y - other.y))

    def euclidean_distance_squared(self, other: Vec2) -> int:
        dx = self.x - other.x
        dy = self.y - other.y
        return dx * dx + dy * dy

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vec2):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __repr__(self) -> str:
        return f"Vec2({self.x}, {self.y})"


# 4-directional neighbors (cardinal)
CARDINAL_DIRS: list[Vec2] = [
    Vec2(0, -1),  # up
    Vec2(1, 0),   # right
    Vec2(0, 1),   # down
    Vec2(-1, 0),  # left
]

# 8-directional neighbors (cardinal + diagonal)
ALL_DIRS: list[Vec2] = [
    Vec2(-1, -1),  # up-left
    Vec2(0, -1),   # up
    Vec2(1, -1),   # up-right
    Vec2(1, 0),    # right
    Vec2(1, 1),    # down-right
    Vec2(0, 1),    # down
    Vec2(-1, 1),   # down-left
    Vec2(-1, 0),   # left
]

DIAGONAL_COST = 141  # approx(1.41 * 100)
CARDINAL_COST = 100


@dataclass
class Cell:
    """Single cell in a navigation grid."""

    walkable: bool = True
    cost_multiplier: int = 100  # 100 = normal terrain

    def move_cost(self, diagonal: bool = False) -> int:
        """Return cost to leave this cell (multiplier applied to base cost)."""
        if not self.walkable:
            return 0
        base = DIAGONAL_COST if diagonal else CARDINAL_COST
        return (base * self.cost_multiplier) // 100

    def to_dict(self) -> dict[str, Any]:
        return {"walkable": self.walkable, "cost_multiplier": self.cost_multiplier}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Cell:
        return cls(
            walkable=data.get("walkable", True),
            cost_multiplier=data.get("cost_multiplier", 100),
        )


@dataclass
class NavigationGrid:
    """
    2D grid for navigation/pathfinding.

    Grid is tile-based: each cell represents a world tile at
    (col * cell_size, row * cell_size) in world coordinates.

    Cells use screen coordinates: x=right, y=down.
    """

    width: int
    height: int
    cell_size: int = 1
    cells: list[list[Cell]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.cells:
            self.cells = [
                [Cell() for _ in range(self.width)] for _ in range(self.height)
            ]

    def in_bounds(self, col: int, row: int) -> bool:
        return 0 <= col < self.width and 0 <= row < self.height

    def in_bounds_vec(self, pos: Vec2) -> bool:
        return self.in_bounds(pos.x, pos.y)

    def get_cell(self, col: int, row: int) -> Cell:
        if not self.in_bounds(col, row):
            raise IndexError(f"Position ({col}, {row}) out of bounds ({self.width}x{self.height})")
        return self.cells[row][col]

    def get_cell_vec(self, pos: Vec2) -> Cell:
        return self.get_cell(pos.x, pos.y)

    def is_walkable(self, col: int, row: int) -> bool:
        if not self.in_bounds(col, row):
            return False
        return self.cells[row][col].walkable

    def is_walkable_vec(self, pos: Vec2) -> bool:
        if not self.in_bounds_vec(pos):
            return False
        return self.cells[pos.y][pos.x].walkable

    def set_walkable(self, col: int, row: int, walkable: bool) -> None:
        if not self.in_bounds(col, row):
            raise IndexError(f"Position ({col}, {row}) out of bounds")
        self.cells[row][col].walkable = walkable

    def set_cost(self, col: int, row: int, cost: int) -> None:
        if not self.in_bounds(col, row):
            raise IndexError(f"Position ({col}, {row}) out of bounds")
        self.cells[row][col].cost_multiplier = cost

    def world_to_grid(self, wx: float, wy: float) -> Vec2:
        return Vec2(int(wx // self.cell_size), int(wy // self.cell_size))

    def grid_to_world_center(self, col: int, row: int) -> tuple[float, float]:
        return (
            float(col * self.cell_size + self.cell_size // 2),
            float(row * self.cell_size + self.cell_size // 2),
        )

    def neighbors(
        self,
        pos: Vec2,
        neighbor_mode: NeighborMode,
    ) -> Iterator[tuple[Vec2, bool]]:
        """Yield walkable neighbors according to the selected expansion policy."""
        directions = ALL_DIRS if neighbor_mode.allows_diagonal else CARDINAL_DIRS
        for direction in directions:
            neighbor = pos + direction
            if not self.in_bounds_vec(neighbor):
                continue
            if not self.is_walkable_vec(neighbor):
                continue
            yield neighbor, direction.x != 0 and direction.y != 0

    def neighbors_4(self, pos: Vec2) -> Iterator[tuple[Vec2, bool]]:
        """Compatibility wrapper for cardinal-only neighbor expansion."""
        yield from self.neighbors(pos, NeighborMode.CARDINAL_4)

    def neighbors_8(self, pos: Vec2) -> Iterator[tuple[Vec2, bool]]:
        """Compatibility wrapper for 8-way neighbor expansion."""
        yield from self.neighbors(pos, NeighborMode.EIGHT_WAY)

    def move_cost(self, pos: Vec2, diagonal: bool = False) -> int:
        """Return the movement cost of entering a walkable cell."""
        return self.get_cell_vec(pos).move_cost(diagonal=diagonal)

    def move_cost_between(self, from_pos: Vec2, to_pos: Vec2) -> int:
        """Return movement cost between adjacent cells."""
        diagonal = from_pos.x != to_pos.x and from_pos.y != to_pos.y
        return self.move_cost(to_pos, diagonal=diagonal)

    def iter_cells(self) -> Iterator[tuple[int, int, Cell]]:
        for row in range(self.height):
            for col in range(self.width):
                yield col, row, self.cells[row][col]

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "cell_size": self.cell_size,
            "cells": [[c.to_dict() for c in row] for row in self.cells],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NavigationGrid:
        cells_data = data.get("cells", [])
        height = data.get("height", len(cells_data))
        width = data.get("width", len(cells_data[0]) if cells_data else 0)
        cell_size = data.get("cell_size", 1)
        cells = [[Cell.from_dict(cells_data[row][col]) for col in range(width)] for row in range(height)]
        return cls(width=width, height=height, cell_size=cell_size, cells=cells)

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_json(cls, path: str) -> NavigationGrid:
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_walkable_matrix(
        cls,
        walkable: list[list[bool]],
        cell_size: int = 1,
        default_cost: int = 100,
    ) -> NavigationGrid:
        height = len(walkable)
        width = len(walkable[0]) if height > 0 else 0
        cells = [
            [
                Cell(walkable=walkable[row][col], cost_multiplier=default_cost)
                for col in range(width)
            ]
            for row in range(height)
        ]
        return cls(width=width, height=height, cell_size=cell_size, cells=cells)

    def clone(self) -> NavigationGrid:
        cells = [[Cell.from_dict(c.to_dict()) for c in row] for row in self.cells]
        return NavigationGrid(
            width=self.width,
            height=self.height,
            cell_size=self.cell_size,
            cells=cells,
        )
