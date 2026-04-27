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


if __name__ == "__main__":
    unittest.main()
