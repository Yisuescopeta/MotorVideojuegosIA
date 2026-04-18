"""
tests/test_navigation.py - Unit tests for the navigation/pathfinding module

Tests cover:
- Vec2 arithmetic and comparison
- NavigationGrid construction, bounds, and queries
- AStarPathfinder on various grid configurations
- NavigationService high-level queries
- Serialization (to_dict/from_dict)
- Deterministic, tilemap-agnostic behavior
"""

import tempfile
import unittest
from pathlib import Path

from engine.navigation import (
    AStarPathfinder,
    NeighborMode,
    NavigationGrid,
    NavigationQuery,
    NavigationService,
    PathRequest,
    PathResult,
    Vec2,
)


class TestPathContracts(unittest.TestCase):
    def test_neighbor_mode_from_diagonal(self) -> None:
        self.assertEqual(NeighborMode.from_diagonal(True), NeighborMode.EIGHT_WAY)
        self.assertEqual(NeighborMode.from_diagonal(False), NeighborMode.CARDINAL_4)

    def test_path_request_roundtrip(self) -> None:
        request = PathRequest(
            start=Vec2(1, 2),
            goal=Vec2(3, 4),
            neighbor_mode=NeighborMode.CARDINAL_4,
            max_iterations=15,
        )
        restored = PathRequest.from_dict(request.to_dict())
        self.assertEqual(restored.start, Vec2(1, 2))
        self.assertEqual(restored.goal, Vec2(3, 4))
        self.assertEqual(restored.neighbor_mode, NeighborMode.CARDINAL_4)
        self.assertEqual(restored.max_iterations, 15)

    def test_path_result_roundtrip(self) -> None:
        result = PathResult.success_result([Vec2(0, 0), Vec2(1, 0)], 100)
        restored = PathResult.from_dict(result.to_dict())
        self.assertTrue(restored.success)
        self.assertEqual(restored.path, [Vec2(0, 0), Vec2(1, 0)])
        self.assertEqual(restored.cost, 100)


class TestVec2(unittest.TestCase):
    def test_add(self) -> None:
        self.assertEqual(Vec2(1, 2) + Vec2(3, 4), Vec2(4, 6))

    def test_sub(self) -> None:
        self.assertEqual(Vec2(5, 7) - Vec2(2, 3), Vec2(3, 4))

    def test_neg(self) -> None:
        self.assertEqual(-Vec2(3, 4), Vec2(-3, -4))

    def test_mul_scalar(self) -> None:
        self.assertEqual(Vec2(2, 3) * 3, Vec2(6, 9))

    def test_rmul_scalar(self) -> None:
        self.assertEqual(3 * Vec2(2, 3), Vec2(6, 9))

    def test_manhattan(self) -> None:
        self.assertEqual(Vec2(1, 2).manhattan_distance(Vec2(4, 6)), 7)

    def test_chebyshev(self) -> None:
        self.assertEqual(Vec2(1, 2).chebyshev_distance(Vec2(4, 6)), 4)

    def test_equality(self) -> None:
        self.assertEqual(Vec2(1, 2), Vec2(1, 2))
        self.assertNotEqual(Vec2(1, 2), Vec2(1, 3))

    def test_hash(self) -> None:
        s = {Vec2(1, 2), Vec2(1, 2), Vec2(3, 4)}
        self.assertEqual(len(s), 2)

    def test_repr(self) -> None:
        self.assertEqual(repr(Vec2(1, 2)), "Vec2(1, 2)")


class TestNavigationGrid(unittest.TestCase):
    def test_construct_default(self) -> None:
        g = NavigationGrid(width=5, height=4)
        self.assertEqual(g.width, 5)
        self.assertEqual(g.height, 4)
        self.assertEqual(g.cell_size, 1)
        for row in range(g.height):
            for col in range(g.width):
                self.assertTrue(g.is_walkable(col, row))

    def test_construct_from_matrix(self) -> None:
        walkable = [
            [True, True, False],
            [True, False, True],
            [True, True, True],
        ]
        g = NavigationGrid.from_walkable_matrix(walkable, cell_size=2)
        self.assertEqual(g.width, 3)
        self.assertEqual(g.height, 3)
        self.assertEqual(g.cell_size, 2)
        self.assertTrue(g.is_walkable(0, 0))
        self.assertFalse(g.is_walkable(2, 0))
        self.assertFalse(g.is_walkable(1, 1))

    def test_in_bounds(self) -> None:
        g = NavigationGrid(width=3, height=3)
        self.assertTrue(g.in_bounds(0, 0))
        self.assertTrue(g.in_bounds(2, 2))
        self.assertFalse(g.in_bounds(3, 0))
        self.assertFalse(g.in_bounds(-1, 0))
        self.assertFalse(g.in_bounds(0, 3))

    def test_set_walkable(self) -> None:
        g = NavigationGrid(width=3, height=3)
        g.set_walkable(1, 1, False)
        self.assertFalse(g.is_walkable(1, 1))
        g.set_walkable(1, 1, True)
        self.assertTrue(g.is_walkable(1, 1))

    def test_world_to_grid(self) -> None:
        g = NavigationGrid(width=10, height=10, cell_size=32)
        self.assertEqual(g.world_to_grid(0, 0), Vec2(0, 0))
        self.assertEqual(g.world_to_grid(63, 31), Vec2(1, 0))
        self.assertEqual(g.world_to_grid(64, 64), Vec2(2, 2))

    def test_grid_to_world_center(self) -> None:
        g = NavigationGrid(width=10, height=10, cell_size=32)
        cx, cy = g.grid_to_world_center(1, 2)
        self.assertEqual(cx, 48.0)
        self.assertEqual(cy, 80.0)

    def test_neighbors_4(self) -> None:
        g = NavigationGrid.from_walkable_matrix([
            [True, True, True],
            [True, True, True],
            [True, True, True],
        ])
        nbrs = list(g.neighbors_4(Vec2(1, 1)))
        self.assertEqual(len(nbrs), 4)
        positions = [pos for pos, _ in nbrs]
        self.assertIn(Vec2(0, 1), positions)
        self.assertIn(Vec2(2, 1), positions)
        self.assertIn(Vec2(1, 0), positions)
        self.assertIn(Vec2(1, 2), positions)

    def test_neighbors_4_edge(self) -> None:
        g = NavigationGrid.from_walkable_matrix([
            [True, True, True],
            [True, True, True],
            [True, True, True],
        ])
        nbrs = list(g.neighbors_4(Vec2(0, 0)))
        self.assertEqual(len(nbrs), 2)
        positions = [pos for pos, _ in nbrs]
        self.assertIn(Vec2(1, 0), positions)
        self.assertIn(Vec2(0, 1), positions)

    def test_neighbors_8(self) -> None:
        g = NavigationGrid.from_walkable_matrix([
            [True, True, True],
            [True, True, True],
            [True, True, True],
        ])
        nbrs = list(g.neighbors_8(Vec2(1, 1)))
        self.assertEqual(len(nbrs), 8)

    def test_neighbors_8_blocked_diagonal(self) -> None:
        walkable = [
            [False, False, False],
            [False, True, False],
            [False, False, False],
        ]
        g = NavigationGrid.from_walkable_matrix(walkable)
        center = Vec2(1, 1)
        self.assertTrue(g.is_walkable_vec(center))
        nbrs = list(g.neighbors_8(center))
        self.assertEqual(len(nbrs), 0)

    def test_serialization_roundtrip(self) -> None:
        g = NavigationGrid.from_walkable_matrix([
            [True, True, False],
            [True, False, True],
            [False, True, True],
        ])
        g.cells[0][0].cost_multiplier = 150
        g.cells[1][2].cost_multiplier = 200

        data = g.to_dict()
        restored = NavigationGrid.from_dict(data)

        self.assertEqual(restored.width, g.width)
        self.assertEqual(restored.height, g.height)
        self.assertEqual(restored.cell_size, g.cell_size)
        self.assertEqual(restored.cells[0][0].cost_multiplier, 150)
        self.assertEqual(restored.cells[1][2].cost_multiplier, 200)
        self.assertEqual(restored.is_walkable(2, 0), False)
        self.assertEqual(restored.is_walkable(1, 1), False)

    def test_clone(self) -> None:
        g = NavigationGrid.from_walkable_matrix([
            [True, True],
            [True, True],
        ])
        g.cells[0][0].cost_multiplier = 150
        h = g.clone()
        self.assertEqual(h.width, g.width)
        self.assertEqual(h.cells[0][0].cost_multiplier, 150)
        h.cells[0][0].cost_multiplier = 200
        self.assertEqual(g.cells[0][0].cost_multiplier, 150)

    def test_json_roundtrip(self) -> None:
        g = NavigationGrid.from_walkable_matrix([
            [True, False],
            [False, True],
        ])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            tmp = f.name
        try:
            g.to_json(tmp)
            h = NavigationGrid.from_json(tmp)
            self.assertEqual(h.width, 2)
            self.assertEqual(h.height, 2)
            self.assertTrue(h.is_walkable(0, 0))
            self.assertFalse(h.is_walkable(1, 0))
        finally:
            Path(tmp).unlink()


class TestAStarPathfinder(unittest.TestCase):
    def _make_open_grid(self, w: int = 5, h: int = 5) -> NavigationGrid:
        return NavigationGrid.from_walkable_matrix(
            [[True] * w for _ in range(h)]
        )

    def test_no_path_on_blocked_start(self) -> None:
        walkable = [
            [False, True],
            [True, True],
        ]
        g = NavigationGrid.from_walkable_matrix(walkable)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 0), Vec2(1, 0))
        self.assertEqual(path, [])

    def test_no_path_on_blocked_goal(self) -> None:
        walkable = [
            [True, False],
            [True, True],
        ]
        g = NavigationGrid.from_walkable_matrix(walkable)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 0), Vec2(1, 0))
        self.assertEqual(path, [])

    def test_direct_path(self) -> None:
        g = self._make_open_grid(3, 3)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 0), Vec2(2, 2), diagonal=False)
        self.assertEqual(path[0], Vec2(0, 0))
        self.assertEqual(path[-1], Vec2(2, 2))
        self.assertTrue(pf.is_path_valid(path))

    def test_diagonal_path(self) -> None:
        g = self._make_open_grid(3, 3)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 0), Vec2(2, 2), diagonal=True)
        self.assertEqual(len(path), 3)
        self.assertEqual(path[0], Vec2(0, 0))
        self.assertEqual(path[-1], Vec2(2, 2))
        self.assertTrue(pf.is_path_valid(path))

    def test_path_not_found_blocked(self) -> None:
        walkable = [
            [True, False],
            [False, True],
        ]
        g = NavigationGrid.from_walkable_matrix(walkable)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 0), Vec2(1, 1))
        self.assertEqual(path, [])

    def test_path_respects_diagonal_corner_cutting(self) -> None:
        walkable = [
            [True, True, True],
            [False, True, True],
            [True, True, True],
        ]
        g = NavigationGrid.from_walkable_matrix(walkable)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 0), Vec2(2, 0), diagonal=True)
        self.assertGreaterEqual(len(path), 3)
        self.assertTrue(pf.is_path_valid(path))
        path2 = pf.find_path(Vec2(0, 0), Vec2(2, 0), diagonal=False)
        self.assertGreaterEqual(len(path2), 3)

    def test_manhattan_path(self) -> None:
        g = self._make_open_grid(4, 4)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 0), Vec2(3, 3), diagonal=False)
        self.assertGreater(len(path), 0)
        self.assertEqual(path[0], Vec2(0, 0))
        self.assertEqual(path[-1], Vec2(3, 3))
        self.assertEqual(pf._calculate_path_cost(path, False), 600)

    def test_line_of_sight_open(self) -> None:
        g = self._make_open_grid(5, 5)
        pf = AStarPathfinder(g)
        self.assertTrue(pf.get_line_of_sight(Vec2(0, 0), Vec2(4, 4)))
        self.assertTrue(pf.get_line_of_sight(Vec2(0, 0), Vec2(4, 0)))

    def test_line_of_sight_blocked(self) -> None:
        walkable = [
            [True, True, True],
            [False, True, True],
            [True, True, True],
        ]
        g = NavigationGrid.from_walkable_matrix(walkable)
        pf = AStarPathfinder(g)
        self.assertFalse(pf.get_line_of_sight(Vec2(0, 1), Vec2(2, 1)))

    def test_max_iterations(self) -> None:
        g = self._make_open_grid(50, 50)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 0), Vec2(49, 49), max_iterations=10)
        self.assertEqual(path, [])

    def test_start_equals_goal(self) -> None:
        g = self._make_open_grid(3, 3)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(1, 1), Vec2(1, 1))
        self.assertEqual(path, [Vec2(1, 1)])

    def test_request_path_canonical_api(self) -> None:
        g = self._make_open_grid(4, 4)
        pf = AStarPathfinder(g)
        result = pf.request_path(
            PathRequest(
                start=Vec2(0, 0),
                goal=Vec2(3, 3),
                neighbor_mode=NeighborMode.CARDINAL_4,
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(result.path[0], Vec2(0, 0))
        self.assertEqual(result.path[-1], Vec2(3, 3))
        self.assertEqual(result.cost, 600)

    def test_grid_none_returns_empty(self) -> None:
        pf = AStarPathfinder(None)
        self.assertEqual(pf.find_path(Vec2(0, 0), Vec2(1, 1)), [])

    def test_out_of_bounds_returns_empty(self) -> None:
        g = self._make_open_grid(3, 3)
        pf = AStarPathfinder(g)
        self.assertEqual(pf.find_path(Vec2(-1, 0), Vec2(1, 1)), [])
        self.assertEqual(pf.find_path(Vec2(0, 0), Vec2(10, 10)), [])

    def test_different_start_goal_same_row(self) -> None:
        g = self._make_open_grid(5, 3)
        pf = AStarPathfinder(g)
        path = pf.find_path(Vec2(0, 1), Vec2(4, 1), diagonal=False)
        self.assertEqual(path, [Vec2(0, 1), Vec2(1, 1), Vec2(2, 1), Vec2(3, 1), Vec2(4, 1)])


class TestNavigationService(unittest.TestCase):
    def _make_grid(self) -> NavigationGrid:
        return NavigationGrid.from_walkable_matrix([
            [True, True, True, True, True],
            [True, True, True, False, True],
            [True, True, True, True, True],
            [True, True, True, True, True],
            [True, True, True, True, True],
        ])

    def test_query_path_success(self) -> None:
        grid = self._make_grid()
        svc = NavigationService(grid)
        result = svc.query_path(0, 0, 4, 4)
        self.assertTrue(result.success)
        self.assertGreater(len(result.path), 0)
        self.assertEqual(result.path[0], Vec2(0, 0))
        self.assertEqual(result.path[-1], Vec2(4, 4))
        self.assertGreater(result.cost, 0)

    def test_query_path_no_grid(self) -> None:
        svc = NavigationService(None)
        result = svc.query_path(0, 0, 1, 1)
        self.assertFalse(result.success)
        self.assertIn("No navigation grid", result.message)

    def test_request_path_canonical_api(self) -> None:
        grid = self._make_grid()
        svc = NavigationService(grid)
        result = svc.request_path(
            PathRequest(
                start=Vec2(0, 0),
                goal=Vec2(4, 4),
                neighbor_mode=NeighborMode.EIGHT_WAY,
            )
        )
        self.assertTrue(result.success)
        self.assertIsInstance(result, PathResult)

    def test_navigation_query_is_path_result_alias(self) -> None:
        self.assertIs(NavigationQuery, PathResult)

    def test_query_path_out_of_bounds(self) -> None:
        grid = self._make_grid()
        svc = NavigationService(grid)
        result = svc.query_path(10, 0, 4, 4)
        self.assertFalse(result.success)

    def test_query_path_blocked(self) -> None:
        grid = self._make_grid()
        svc = NavigationService(grid)
        result = svc.query_path(0, 0, 3, 1)
        self.assertFalse(result.success)
        self.assertTrue("not walkable" in result.message or "No path found" in result.message)

    def test_query_world_path(self) -> None:
        grid = NavigationGrid(width=10, height=10, cell_size=32)
        for col in range(10):
            for row in range(10):
                grid.set_walkable(col, row, True)
        svc = NavigationService(grid)
        result = svc.query_world_path(16, 16, 64, 64)
        self.assertTrue(result.success)

    def test_has_line_of_sight(self) -> None:
        grid = self._make_grid()
        svc = NavigationService(grid)
        self.assertTrue(svc.has_line_of_sight(0, 0, 4, 4))
        self.assertFalse(svc.has_line_of_sight(0, 0, 3, 1))

    def test_is_walkable(self) -> None:
        grid = self._make_grid()
        svc = NavigationService(grid)
        self.assertTrue(svc.is_walkable(0, 0))
        self.assertFalse(svc.is_walkable(3, 1))

    def test_get_reachable_positions(self) -> None:
        grid = NavigationGrid.from_walkable_matrix([
            [True, True, True],
            [True, True, True],
            [True, True, True],
        ])
        svc = NavigationService(grid)
        reachable = svc.get_reachable_positions(1, 1, max_cost=200, diagonal=False)
        self.assertIn(Vec2(1, 1), reachable)
        self.assertIn(Vec2(0, 1), reachable)
        self.assertIn(Vec2(2, 1), reachable)
        self.assertIn(Vec2(1, 0), reachable)
        self.assertIn(Vec2(1, 2), reachable)

    def test_build_navmesh_from_grid(self) -> None:
        grid = NavigationGrid.from_walkable_matrix([
            [True, True],
            [True, True],
        ])
        svc = NavigationService(grid)
        mesh = svc.build_navmesh_from_grid()
        self.assertEqual(len(mesh["nodes"]), 4)
        self.assertGreater(len(mesh["edges"]), 0)

    def test_query_to_dict(self) -> None:
        grid = self._make_grid()
        svc = NavigationService(grid)
        result = svc.query_path(0, 0, 2, 0)
        d = result.to_dict()
        self.assertIn("success", d)
        self.assertIn("path", d)
        self.assertIn("cost", d)

    def test_set_grid(self) -> None:
        svc = NavigationService()
        grid = self._make_grid()
        svc.set_grid(grid)
        result = svc.query_path(0, 0, 4, 4)
        self.assertTrue(result.success)

    def test_get_reachable_positions_diagonal(self) -> None:
        grid = NavigationGrid.from_walkable_matrix([
            [True, True, True],
            [True, True, True],
            [True, True, True],
        ])
        svc = NavigationService(grid)
        reachable = svc.get_reachable_positions(1, 1, max_cost=300, diagonal=True)
        self.assertIn(Vec2(1, 1), reachable)
        self.assertIn(Vec2(0, 0), reachable)
        self.assertIn(Vec2(2, 2), reachable)

    def test_get_reachable_positions_cost_limit(self) -> None:
        grid = NavigationGrid.from_walkable_matrix([
            [True, True, True],
            [True, True, True],
            [True, True, True],
        ])
        svc = NavigationService(grid)
        reachable = svc.get_reachable_positions(0, 0, max_cost=100, diagonal=False)
        self.assertIn(Vec2(0, 0), reachable)
        self.assertIn(Vec2(1, 0), reachable)
        self.assertNotIn(Vec2(2, 0), reachable)

    def test_build_navmesh_uses_real_costs(self) -> None:
        grid = NavigationGrid.from_walkable_matrix([
            [True, True],
            [True, True],
        ])
        grid.cells[0][1].cost_multiplier = 200
        grid.cells[1][0].cost_multiplier = 50
        svc = NavigationService(grid)
        mesh = svc.build_navmesh_from_grid()
        edges = mesh["edges"]
        cost_200 = None
        cost_50 = None
        for e in edges:
            from_pos = mesh["nodes"][e["from"]]
            to_pos = mesh["nodes"][e["to"]]
            if from_pos["x"] == 0 and from_pos["y"] == 0 and to_pos["x"] == 1 and to_pos["y"] == 0:
                cost_200 = e["cost"]
            if from_pos["x"] == 0 and from_pos["y"] == 0 and to_pos["x"] == 0 and to_pos["y"] == 1:
                cost_50 = e["cost"]
        self.assertEqual(cost_200, 200)
        self.assertEqual(cost_50, 50)


class TestNavigationGridCostModifiers(unittest.TestCase):
    def test_cost_modifier_affects_path(self) -> None:
        walkable = [
            [True, True],
            [True, True],
        ]
        g = NavigationGrid.from_walkable_matrix(walkable)
        g.cells[0][0].cost_multiplier = 100
        g.cells[0][1].cost_multiplier = 100
        g.cells[1][0].cost_multiplier = 100
        g.cells[1][1].cost_multiplier = 100

        g.cells[0][1].cost_multiplier = 1
        pf = AStarPathfinder(g)
        path, cost = pf.find_path_with_cost(Vec2(0, 0), Vec2(1, 1), diagonal=False)
        self.assertTrue(path)
        self.assertGreater(cost, 0)

    def test_cost_modifier_low_vs_high(self) -> None:
        walkable = [
            [True, True, True],
            [True, True, True],
            [True, True, True],
        ]
        g_low = NavigationGrid.from_walkable_matrix(walkable)
        g_low.cells[0][1].cost_multiplier = 1
        g_low.cells[1][1].cost_multiplier = 1
        pf_low = AStarPathfinder(g_low)
        path_low, cost_low = pf_low.find_path_with_cost(Vec2(0, 0), Vec2(2, 0), diagonal=False)

        g_high = NavigationGrid.from_walkable_matrix(walkable)
        g_high.cells[0][1].cost_multiplier = 300
        g_high.cells[1][1].cost_multiplier = 300
        pf_high = AStarPathfinder(g_high)
        path_high, cost_high = pf_high.find_path_with_cost(Vec2(0, 0), Vec2(2, 0), diagonal=False)

        self.assertTrue(path_low)
        self.assertTrue(path_high)
        self.assertLess(cost_low, cost_high)


if __name__ == "__main__":
    unittest.main()
