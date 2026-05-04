"""tests/test_navigation_agent.py — Tests for NavigationAgent2D component and NavigationAgentSystem."""

from __future__ import annotations

import math
import unittest

from engine.components.navigation_agent_2d import NavigationAgent2D
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.navigation.grid import NavigationGrid, Vec2
from engine.navigation.service import NavigationService
from engine.navigation.types import PathResult
from engine.systems.navigation_agent_system import NavigationAgentSystem


class NavigationAgent2DComponentTests(unittest.TestCase):
    def test_create_default(self):
        agent = NavigationAgent2D()
        self.assertTrue(agent.enabled)
        self.assertEqual(agent.speed, 100.0)
        self.assertEqual(agent.path_desired_distance, 20.0)
        self.assertEqual(agent.target_reached_distance, 10.0)

    def test_set_target(self):
        agent = NavigationAgent2D()
        agent.set_target(300, 400)
        self.assertEqual(agent.target_x, 300.0)
        self.assertEqual(agent.target_y, 400.0)

    def test_path_empty_initially(self):
        agent = NavigationAgent2D()
        self.assertEqual(agent.path, [])
        self.assertTrue(agent.is_navigation_finished)
        self.assertFalse(agent.is_target_reached)

    def test_get_next_waypoint_empty(self):
        agent = NavigationAgent2D()
        self.assertIsNone(agent.get_next_waypoint())

    def test_get_next_waypoint_with_path(self):
        agent = NavigationAgent2D()
        agent.path = [[0, 0], [10, 0], [10, 10]]
        wp = agent.get_next_waypoint()
        self.assertEqual(wp, (0, 0))

        agent.current_path_index = 2
        wp = agent.get_next_waypoint()
        self.assertEqual(wp, (10, 10))

    def test_get_next_waypoint_oob(self):
        agent = NavigationAgent2D()
        agent.path = [[0, 0]]
        agent.current_path_index = 1
        self.assertIsNone(agent.get_next_waypoint())

    def test_distance_to_target(self):
        agent = NavigationAgent2D()
        agent.set_target(3, 4)
        dist = agent.distance_to_target(0, 0)
        self.assertAlmostEqual(dist, 5.0)

    def test_serialization_roundtrip(self):
        agent = NavigationAgent2D()
        agent.set_target(100, 200)
        agent.speed = 150.0
        agent.path = [[0, 0], [50, 50], [100, 100]]
        agent.current_path_index = 1
        agent.is_navigation_finished = False
        agent.is_target_reached = False
        agent.velocity_x = 10.0
        agent.velocity_y = -5.0

        data = agent.to_dict()
        restored = NavigationAgent2D.from_dict(data)

        self.assertEqual(restored.target_x, agent.target_x)
        self.assertEqual(restored.target_y, agent.target_y)
        self.assertEqual(restored.speed, agent.speed)
        self.assertEqual(restored.path, agent.path)
        self.assertEqual(restored.current_path_index, agent.current_path_index)
        self.assertEqual(restored.is_navigation_finished, agent.is_navigation_finished)
        self.assertEqual(restored.is_target_reached, agent.is_target_reached)
        self.assertEqual(restored.velocity_x, agent.velocity_x)
        self.assertEqual(restored.velocity_y, agent.velocity_y)

    def test_from_dict_defaults(self):
        restored = NavigationAgent2D.from_dict({})
        self.assertTrue(restored.enabled)
        self.assertEqual(restored.speed, 100.0)


class NavigationAgentSystemTests(unittest.TestCase):
    def _make_grid(self, width: int = 10, height: int = 10) -> NavigationGrid:
        grid = NavigationGrid(width=width, height=height, cell_size=32)
        for row in range(height):
            for col in range(width):
                grid.set_walkable(col, row, True)
        return grid

    def _make_nav_service(self, grid: NavigationGrid) -> NavigationService:
        return NavigationService(grid=grid)

    def test_no_nav_service_no_error(self):
        system = NavigationAgentSystem(nav_service=None)
        world = World()
        entity = world.create_entity("test")
        entity.add_component(Transform(x=0, y=0))
        entity.add_component(NavigationAgent2D())
        system.update(world, 0.016)

    def test_no_grid_no_error(self):
        service = NavigationService(grid=None)
        system = NavigationAgentSystem(nav_service=service)
        world = World()
        entity = world.create_entity("test")
        entity.add_component(Transform(x=0, y=0))
        entity.add_component(NavigationAgent2D())
        system.update(world, 0.016)

    def test_movement_toward_target(self):
        grid = self._make_grid(10, 10)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()
        entity = world.create_entity("agent")
        entity.add_component(Transform(x=32, y=32))
        agent = NavigationAgent2D(speed=100.0)
        agent.set_target(160, 32)
        entity.add_component(agent)

        system.update(world, 0.5)

        agent = entity.get_component(NavigationAgent2D)
        t = entity.get_component(Transform)
        self.assertGreater(len(agent.path), 0, f"Should have path, got {agent.path}")
        self.assertTrue(t.x > 32 or agent.is_target_reached)
        self.assertFalse(agent.is_navigation_finished)

    def test_target_reached(self):
        grid = self._make_grid(10, 10)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()
        entity = world.create_entity("agent")
        entity.add_component(Transform(x=32, y=32))
        agent = NavigationAgent2D(
            speed=100.0,
            target_reached_distance=5.0,
            path_desired_distance=1.0,
        )
        agent.set_target(32, 32)
        entity.add_component(agent)

        system.update(world, 0.016)

        agent = entity.get_component(NavigationAgent2D)
        self.assertTrue(agent.is_target_reached)

    def test_disabled_agent_no_movement(self):
        grid = self._make_grid(10, 10)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()
        entity = world.create_entity("agent")
        entity.add_component(Transform(x=32, y=32))
        agent = NavigationAgent2D(enabled=False, speed=100.0)
        agent.set_target(160, 32)
        entity.add_component(agent)

        system.update(world, 0.5)

        t = entity.get_component(Transform)
        self.assertEqual(t.x, 32)
        self.assertEqual(t.y, 32)

    def test_velocity_updated(self):
        grid = self._make_grid(10, 10)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()
        entity = world.create_entity("agent")
        entity.add_component(Transform(x=32, y=32))
        agent = NavigationAgent2D(speed=100.0)
        agent.set_target(160, 32)
        entity.add_component(agent)

        system.update(world, 0.5)

        agent = entity.get_component(NavigationAgent2D)
        vel_mag = math.sqrt(agent.velocity_x ** 2 + agent.velocity_y ** 2)
        self.assertAlmostEqual(vel_mag, agent.speed, delta=1.0)
        self.assertGreater(abs(agent.velocity_x), 0)

    def test_target_change_recalculates(self):
        grid = self._make_grid(10, 10)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()
        entity = world.create_entity("agent")
        entity.add_component(Transform(x=32, y=32))
        agent = NavigationAgent2D(speed=100.0)
        agent.set_target(160, 32)
        entity.add_component(agent)

        system.update(world, 0.5)
        first_path = list(agent.path)

        agent.set_target(32, 160)
        system.update(world, 0.5)
        second_path = list(agent.path)

        self.assertNotEqual(first_path, second_path)

    def test_no_path_found_marks_finished(self):
        grid = self._make_grid(3, 3)
        # Block all paths by making a wall
        for row in range(3):
            grid.set_walkable(1, row, False)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()
        entity = world.create_entity("agent")
        entity.add_component(Transform(x=0, y=16))
        agent = NavigationAgent2D(speed=100.0)
        agent.set_target(64, 16)  # Target on other side of wall
        entity.add_component(agent)

        system.update(world, 0.5)

        agent = entity.get_component(NavigationAgent2D)
        self.assertTrue(agent.is_navigation_finished)
        self.assertEqual(agent.path, [])

    def test_nav_service_setter(self):
        system = NavigationAgentSystem(nav_service=None)
        grid = self._make_grid(5, 5)
        service = self._make_nav_service(grid)
        system.set_nav_service(service)
        self.assertIs(system._nav_service, service)

    def test_system_ignores_entities_without_transform(self):
        grid = self._make_grid(5, 5)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()
        entity = world.create_entity("agent_no_transform")
        agent = NavigationAgent2D(speed=100.0)
        agent.set_target(64, 0)
        entity.add_component(agent)

        system.update(world, 0.5)

        # No error, and no path calculated (no transform, so _recalculate_path is skipped for that entity)
        # The system should handle this gracefully and continue
        agent_after = entity.get_component(NavigationAgent2D)
        self.assertIsNotNone(agent_after)


if __name__ == "__main__":
    unittest.main()
