from __future__ import annotations

import math
from collections.abc import Iterator

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
        return self.query_into(aabb, entity_ids)

    def query_into(self, aabb: AABB, output_set: set[int]) -> set[int]:
        output_set.clear()
        for cell in self._iter_cells(aabb):
            entity_ids = self._cells.get(cell)
            if entity_ids is not None:
                output_set.update(entity_ids)
        return output_set

    def _iter_cells(self, aabb: AABB) -> Iterator[tuple[int, int]]:
        left, top, right, bottom = [float(value) for value in aabb]
        min_cell_x = math.floor(left / self.cell_size)
        min_cell_y = math.floor(top / self.cell_size)
        max_cell_x = self._max_cell(left, right)
        max_cell_y = self._max_cell(top, bottom)
        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                yield (cell_x, cell_y)

    def _max_cell(self, minimum: float, maximum: float) -> int:
        if maximum <= minimum:
            return math.floor(minimum / self.cell_size)
        return math.floor((maximum - 1e-9) / self.cell_size)
