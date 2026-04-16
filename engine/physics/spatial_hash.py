from __future__ import annotations

import math

AABB = tuple[float, float, float, float]


class SpatialHash2D:
    def __init__(self, cell_size: float = 128.0) -> None:
        self.cell_size = max(float(cell_size), 1.0)
        self._cells: dict[tuple[int, int], set[int]] = {}

    def clear(self) -> None:
        self._cells.clear()

    def insert(self, entity_id: int, aabb: AABB) -> None:
        for cell in self._iter_cells(aabb):
            self._cells.setdefault(cell, set()).add(int(entity_id))

    def query(self, aabb: AABB) -> set[int]:
        entity_ids: set[int] = set()
        for cell in self._iter_cells(aabb):
            entity_ids.update(self._cells.get(cell, set()))
        return entity_ids

    def _iter_cells(self, aabb: AABB) -> list[tuple[int, int]]:
        left, top, right, bottom = [float(value) for value in aabb]
        min_cell_x = math.floor(left / self.cell_size)
        min_cell_y = math.floor(top / self.cell_size)
        max_cell_x = self._max_cell(left, right)
        max_cell_y = self._max_cell(top, bottom)
        return [
            (cell_x, cell_y)
            for cell_x in range(min_cell_x, max_cell_x + 1)
            for cell_y in range(min_cell_y, max_cell_y + 1)
        ]

    def _max_cell(self, minimum: float, maximum: float) -> int:
        if maximum <= minimum:
            return math.floor(minimum / self.cell_size)
        return math.floor((maximum - 1e-9) / self.cell_size)
