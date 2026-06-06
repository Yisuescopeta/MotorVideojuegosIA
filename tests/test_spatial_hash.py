import unittest

from engine.physics.spatial_hash import SpatialHash2D


class SpatialHash2DTests(unittest.TestCase):
    def test_insert_and_query_returns_local_entities_across_cells(self) -> None:
        grid = SpatialHash2D(cell_size=10.0)

        grid.insert(1, (0.0, 0.0, 5.0, 5.0))
        grid.insert(2, (8.0, 0.0, 12.0, 5.0))
        grid.insert(3, (30.0, 0.0, 35.0, 5.0))

        self.assertEqual(grid.query((0.0, 0.0, 10.0, 10.0)), {1, 2})
        self.assertEqual(grid.query((10.0, 0.0, 20.0, 10.0)), {2})
        self.assertEqual(grid.query((20.0, 0.0, 30.0, 10.0)), set())

    def test_query_into_reuses_and_clears_output_set(self) -> None:
        grid = SpatialHash2D(cell_size=10.0)
        output = {99}

        grid.insert(1, (0.0, 0.0, 5.0, 5.0))
        grid.insert(2, (10.0, 0.0, 20.0, 10.0))

        result = grid.query_into((0.0, 0.0, 10.0, 10.0), output)

        self.assertIs(result, output)
        self.assertEqual(output, {1})
        self.assertEqual(result, grid.query((0.0, 0.0, 10.0, 10.0)))

        grid.query_into((100.0, 0.0, 110.0, 10.0), output)

        self.assertEqual(output, set())

    def test_clear_removes_all_inserted_entities(self) -> None:
        grid = SpatialHash2D(cell_size=10.0)
        grid.insert(1, (0.0, 0.0, 5.0, 5.0))
        grid.insert(2, (10.0, 0.0, 15.0, 5.0))

        grid.clear()

        self.assertEqual(grid.query((0.0, 0.0, 20.0, 10.0)), set())

    def test_cell_boundaries_and_zero_sized_aabbs_match_existing_contract(self) -> None:
        grid = SpatialHash2D(cell_size=10.0)

        grid.insert(1, (0.0, 0.0, 10.0, 10.0))
        grid.insert(2, (10.0, 0.0, 10.0, 10.0))

        self.assertEqual(grid.query((0.0, 0.0, 10.0, 10.0)), {1})
        self.assertEqual(grid.query((10.0, 0.0, 10.0, 10.0)), {2})

    def test_adaptive_cell_size_uses_typical_collider_extent(self) -> None:
        aabbs = [
            (0.0, 0.0, 16.0, 16.0),
            (24.0, 0.0, 40.0, 16.0),
            (48.0, 0.0, 64.0, 16.0),
            (0.0, 0.0, 2048.0, 2048.0),
        ]

        self.assertEqual(SpatialHash2D.choose_cell_size(aabbs), 32.0)

    def test_oversized_entries_remain_query_candidates_without_cell_explosion(self) -> None:
        grid = SpatialHash2D(cell_size=10.0, max_cells_per_entry=4)
        grid.insert(1, (-1000.0, -1000.0, 1000.0, 1000.0))
        grid.insert(2, (0.0, 0.0, 5.0, 5.0))

        self.assertEqual(grid.oversized_entry_count, 1)
        self.assertLessEqual(grid.reference_count, 1)
        self.assertEqual(grid.query((0.0, 0.0, 5.0, 5.0)), {1, 2})
        self.assertEqual(grid.query((5000.0, 5000.0, 5010.0, 5010.0)), {1})

    def test_different_cell_sizes_return_equivalent_exact_candidates(self) -> None:
        entries = {
            1: (-20.0, -10.0, -5.0, 5.0),
            2: (0.0, 0.0, 16.0, 16.0),
            3: (100.0, 100.0, 132.0, 132.0),
        }
        query = (-8.0, -8.0, 20.0, 20.0)
        results = []
        for cell_size in (8.0, 32.0, 128.0):
            grid = SpatialHash2D(cell_size=cell_size)
            for entity_id, bounds in entries.items():
                grid.insert(entity_id, bounds)
            broadphase = grid.query(query)
            exact = {
                entity_id
                for entity_id in broadphase
                if self._overlaps(query, entries[entity_id])
            }
            results.append(exact)

        self.assertEqual(results, [{1, 2}, {1, 2}, {1, 2}])

    @staticmethod
    def _overlaps(
        first: tuple[float, float, float, float],
        second: tuple[float, float, float, float],
    ) -> bool:
        return (
            first[0] < second[2]
            and first[2] > second[0]
            and first[1] < second[3]
            and first[3] > second[1]
        )


if __name__ == "__main__":
    unittest.main()
