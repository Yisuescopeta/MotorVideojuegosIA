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

    def query_ray_candidates(
        self, ox: float, oy: float, dx: float, dy: float, max_distance: float
    ) -> set[int]:
        """Return candidate entity IDs along a ray segment using DDA grid traversal.

        Args:
            ox, oy: Ray origin in world coordinates.
            dx, dy: Normalized ray direction.
            max_distance: Maximum ray distance.

        Returns:
            Set of entity IDs in cells intersected by the ray.
        """
        entity_ids: set[int] = set()
        end_x = ox + dx * max_distance
        end_y = oy + dy * max_distance

        # Build swept AABB of the ray segment
        left = min(ox, end_x)
        top = min(oy, end_y)
        right = max(ox, end_x)
        bottom = max(oy, end_y)

        # Query cells covering the swept AABB (conservative, avoids complex DDA)
        for cell in self._iter_cells((left, top, right, bottom)):
            cell_ids = self._cells.get(cell)
            if cell_ids is not None:
                entity_ids.update(cell_ids)
        return entity_ids

    def _max_cell(self, minimum: float, maximum: float) -> int:
        if maximum <= minimum:
            return math.floor(minimum / self.cell_size)
        return math.floor((maximum - 1e-9) / self.cell_size)
