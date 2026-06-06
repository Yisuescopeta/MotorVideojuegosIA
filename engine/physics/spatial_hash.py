from __future__ import annotations

import math
from collections.abc import Iterator
from statistics import median

AABB = tuple[float, float, float, float]


class SpatialHash2D:
    def __init__(self, cell_size: float = 128.0, *, max_cells_per_entry: int = 256) -> None:
        self.cell_size = max(float(cell_size), 1.0)
        self.max_cells_per_entry = max(1, int(max_cells_per_entry))
        self._cells: dict[tuple[int, int], set[int]] = {}
        self._oversized_entities: set[int] = set()

    def clear(self) -> None:
        self._cells.clear()
        self._oversized_entities.clear()

    def reset(self, *, cell_size: float | None = None) -> None:
        if cell_size is not None:
            self.cell_size = max(float(cell_size), 1.0)
        self.clear()

    def insert(self, entity_id: int, aabb: AABB) -> None:
        min_cell_x, min_cell_y, max_cell_x, max_cell_y = self._cell_bounds(aabb)
        cell_count = (max_cell_x - min_cell_x + 1) * (max_cell_y - min_cell_y + 1)
        normalized_id = int(entity_id)
        if cell_count > self.max_cells_per_entry:
            self._oversized_entities.add(normalized_id)
            return
        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                self._cells.setdefault((cell_x, cell_y), set()).add(normalized_id)

    def query(self, aabb: AABB) -> set[int]:
        entity_ids: set[int] = set()
        return self.query_into(aabb, entity_ids)

    def query_into(self, aabb: AABB, output_set: set[int]) -> set[int]:
        output_set.clear()
        output_set.update(self._oversized_entities)
        for cell in self._iter_cells(aabb):
            entity_ids = self._cells.get(cell)
            if entity_ids is not None:
                output_set.update(entity_ids)
        return output_set

    def _iter_cells(self, aabb: AABB) -> Iterator[tuple[int, int]]:
        min_cell_x, min_cell_y, max_cell_x, max_cell_y = self._cell_bounds(aabb)
        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                yield (cell_x, cell_y)

    def _cell_bounds(self, aabb: AABB) -> tuple[int, int, int, int]:
        left, top, right, bottom = [float(value) for value in aabb]
        return (
            math.floor(left / self.cell_size),
            math.floor(top / self.cell_size),
            self._max_cell(left, right),
            self._max_cell(top, bottom),
        )

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
        entity_ids.update(self._oversized_entities)
        return entity_ids

    def _max_cell(self, minimum: float, maximum: float) -> int:
        if maximum <= minimum:
            return math.floor(minimum / self.cell_size)
        return math.floor((maximum - 1e-9) / self.cell_size)

    @property
    def cell_count(self) -> int:
        return len(self._cells)

    @property
    def reference_count(self) -> int:
        return sum(len(entity_ids) for entity_ids in self._cells.values())

    @property
    def oversized_entry_count(self) -> int:
        return len(self._oversized_entities)

    @staticmethod
    def choose_cell_size(
        aabbs: list[AABB],
        *,
        fallback: float = 128.0,
        minimum: float = 32.0,
        maximum: float = 256.0,
    ) -> float:
        longest_sides = [
            max(abs(float(right) - float(left)), abs(float(bottom) - float(top)))
            for left, top, right, bottom in aabbs
            if max(abs(float(right) - float(left)), abs(float(bottom) - float(top))) > 0.0
        ]
        if not longest_sides:
            return max(min(float(fallback), float(maximum)), float(minimum))
        target = max(float(minimum), min(float(maximum), float(median(longest_sides)) * 2.0))
        return max(float(minimum), min(float(maximum), float(2 ** math.ceil(math.log2(target)))))
