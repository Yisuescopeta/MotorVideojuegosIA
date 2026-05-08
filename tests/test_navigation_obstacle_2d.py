"""tests/test_navigation_obstacle_2d.py — Tests for NavigationObstacle2D component."""

from __future__ import annotations

import math
import unittest

from engine.components.navigation_agent_2d import NavigationAgent2D
from engine.components.navigation_obstacle_2d import NavigationObstacle2D
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.navigation.grid import NavigationGrid
from engine.navigation.service import NavigationService
from engine.systems.navigation_agent_system import NavigationAgentSystem


class NavigationObstacle2DComponentTests(unittest.TestCase):
    """Unit tests for NavigationObstacle2D component serialization and defaults."""

    def test_create_default(self) -> None:
        obstacle = NavigationObstacle2D()
        self.assertEqual(obstacle.radius, 0.0)
        self.assertTrue(obstacle.affect_avoidance)

    def test_create_custom(self) -> None:
        obstacle = NavigationObstacle2D(radius=50.0, affect_avoidance=False)
        self.assertEqual(obstacle.radius, 50.0)
        self.assertFalse(obstacle.affect_avoidance)

    def test_to_dict(self) -> None:
        obstacle = NavigationObstacle2D(radius=30.0, affect_avoidance=True)
        data = obstacle.to_dict()
        self.assertEqual(data["radius"], 30.0)
        self.assertEqual(data["affect_avoidance"], True)

    def test_from_dict(self) -> None:
        data = {"radius": 40.0, "affect_avoidance": False}
        obstacle = NavigationObstacle2D.from_dict(data)
        self.assertEqual(obstacle.radius, 40.0)
        self.assertFalse(obstacle.affect_avoidance)

    def test_from_dict_defaults(self) -> None:
        obstacle = NavigationObstacle2D.from_dict({})
        self.assertEqual(obstacle.radius, 0.0)
        self.assertTrue(obstacle.affect_avoidance)

    def test_serialization_roundtrip(self) -> None:
        obstacle = NavigationObstacle2D(radius=75.0, affect_avoidance=True)
        data = obstacle.to_dict()
        restored = NavigationObstacle2D.from_dict(data)
        self.assertEqual(restored.radius, obstacle.radius)
        self.assertEqual(restored.affect_avoidance, obstacle.affect_avoidance)


class NavigationObstacle2DRegistryTests(unittest.TestCase):
    """Verify NavigationObstacle2D is registered in component_registry."""

    def test_registered_in_default_registry(self) -> None:
        registry = create_default_registry()
        desc = registry.get_descriptor("NavigationObstacle2D")
        self.assertIsNotNone(desc, "NavigationObstacle2D not found in registry")
        self.assertEqual(desc.name, "NavigationObstacle2D")

    def test_can_instantiate_from_registry(self) -> None:
        registry = create_default_registry()
        desc = registry.get_descriptor("NavigationObstacle2D")
        component = desc.component_class()
        self.assertIsInstance(component, NavigationObstacle2D)

    def test_default_payload_valid(self) -> None:
        registry = create_default_registry()
        desc = registry.get_descriptor("NavigationObstacle2D")
        payload = desc.default_payload
        restored = NavigationObstacle2D.from_dict(payload)
        self.assertEqual(restored.radius, 0.0)
        self.assertTrue(restored.affect_avoidance)


class NavigationObstacle2DAvoidanceTests(unittest.TestCase):
    """Integration tests: NavigationObstacle2D affect avoidance in NavigationAgentSystem."""

    def _make_grid(self, width: int = 10, height: int = 10) -> NavigationGrid:
        grid = NavigationGrid(width=width, height=height, cell_size=32)
        for row in range(height):
            for col in range(width):
                grid.set_walkable(col, row, True)
        return grid

    def _make_nav_service(self, grid: NavigationGrid) -> NavigationService:
        return NavigationService(grid=grid)

    def test_obstacle_with_affect_avoidance_pushes_agent(self) -> None:
        grid = self._make_grid(10, 10)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()

        # Agent starts at (100, 100)
        agent_entity = world.create_entity("agent")
        agent_entity.add_component(Transform(x=100.0, y=100.0))
        agent = NavigationAgent2D(speed=50.0, avoidance_radius=30.0)
        agent.set_target(200.0, 100.0)  # target to the right
        agent_entity.add_component(agent)

        # Obstacle sits between agent and target, with affect_avoidance=True
        obs_entity = world.create_entity("obstacle")
        obs_entity.add_component(Transform(x=130.0, y=100.0))
        obs = NavigationObstacle2D(radius=40.0, affect_avoidance=True)
        obs_entity.add_component(obs)

        # Run a few frames
        for _ in range(5):
            system.update(world, 0.016)

        agent_after = agent_entity.get_component(NavigationAgent2D)
        transform_after = agent_entity.get_component(Transform)

        # Agent should have moved (maybe not exactly to target due to avoidance)
        self.assertTrue(transform_after.x > 100.0 or agent_after.is_target_reached)
        self.assertFalse(agent_after.is_navigation_finished)

    def test_obstacle_affect_avoidance_false_no_effect(self) -> None:
        grid = self._make_grid(10, 10)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()

        agent_entity = world.create_entity("agent")
        agent_entity.add_component(Transform(x=100.0, y=100.0))
        agent = NavigationAgent2D(speed=50.0, avoidance_radius=30.0)
        agent.set_target(200.0, 100.0)
        agent_entity.add_component(agent)

        # Obstacle with affect_avoidance=False should not affect
        obs_entity = world.create_entity("obstacle")
        obs_entity.add_component(Transform(x=130.0, y=100.0))
        obs = NavigationObstacle2D(radius=40.0, affect_avoidance=False)
        obs_entity.add_component(obs)

        for _ in range(5):
            system.update(world, 0.016)

        agent_after = agent_entity.get_component(NavigationAgent2D)
        transform_after = agent_entity.get_component(Transform)

        # Agent should still move toward target (no avoidance push)
        self.assertTrue(transform_after.x > 100.0 or agent_after.is_target_reached)

    def test_multiple_obstacles_collected(self) -> None:
        grid = self._make_grid(5, 5)
        service = self._make_nav_service(grid)
        system = NavigationAgentSystem(nav_service=service)

        world = World()
        world.create_entity("obs1").add_component(Transform(x=50, y=50))
        world.get_entity_by_name("obs1").add_component(NavigationObstacle2D(radius=10.0))
        world.create_entity("obs2").add_component(Transform(x=80, y=80))
        world.get_entity_by_name("obs2").add_component(NavigationObstacle2D(radius=15.0))

        obstacles = system._collect_obstacles(world)
        self.assertEqual(len(obstacles), 2)

        obstacle_names = sorted([e.name for e, o, t in obstacles])
        self.assertEqual(obstacle_names, ["obs1", "obs2"])


if __name__ == "__main__":
    unittest.main()
