"""tests/test_navigation_avoidance.py — Tests for avoidance, TileSet nav generation, regions, and obstacles."""

import unittest

from engine.components.navigation_agent_2d import NavigationAgent2D
from engine.components.navigation_obstacle_2d import NavigationObstacle2D
from engine.components.navigation_region_2d import NavigationRegion2D
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.navigation.grid import NavigationGrid
from engine.navigation.service import NavigationService
from engine.resources.navigation_polygon import NavigationPolygon
from engine.resources.tileset_resource import (
    TileMetaData,
    TileNavigationPolygon,
    TileSetAtlasSource,
    TileSetResource,
)
from engine.systems.navigation_agent_system import NavigationAgentSystem
from engine.tilemap.model import TileCoord, TileData, TilemapData


class NavigationAvoidanceTests(unittest.TestCase):
    def _make_grid(self, width: int = 10, height: int = 10) -> NavigationGrid:
        grid = NavigationGrid(width=width, height=height, cell_size=32)
        for row in range(height):
            for col in range(width):
                grid.set_walkable(col, row, True)
        return grid

    def test_avoidance_pushes_agents_apart(self):
        """Two agents with avoidance radii should influence each other's velocity."""
        world = World()
        grid = self._make_grid(10, 10)
        service = NavigationService(grid)
        system = NavigationAgentSystem(nav_service=service)

        agent1 = world.create_entity("agent1")
        agent1.add_component(Transform(x=100.0, y=100.0))
        agent1.add_component(NavigationAgent2D(
            target_x=500.0, target_y=100.0,
            speed=50.0, avoidance_radius=30.0,
        ))

        agent2 = world.create_entity("agent2")
        agent2.add_component(Transform(x=110.0, y=100.0))
        agent2.add_component(NavigationAgent2D(
            target_x=0.0, target_y=100.0,
            speed=50.0, avoidance_radius=30.0,
        ))

        system.update(world, 0.016)

        a1 = agent1.get_component(NavigationAgent2D)
        a2 = agent2.get_component(NavigationAgent2D)
        self.assertIsNotNone(a1)
        self.assertIsNotNone(a2)

    def test_avoidance_radius_respected(self):
        """Agent with zero avoidance_radius should not block others."""
        world = World()
        grid = self._make_grid(10, 10)
        service = NavigationService(grid)
        system = NavigationAgentSystem(nav_service=service)

        agent1 = world.create_entity("agent1")
        agent1.add_component(Transform(x=100.0, y=100.0))
        agent1.add_component(NavigationAgent2D(
            target_x=500.0, target_y=100.0,
            speed=50.0, avoidance_radius=0.0,
        ))

        agent2 = world.create_entity("agent2")
        agent2.add_component(Transform(x=110.0, y=100.0))
        agent2.add_component(NavigationAgent2D(
            target_x=0.0, target_y=100.0,
            speed=50.0, avoidance_radius=30.0,
        ))

        system.update(world, 0.016)

        a2 = agent2.get_component(NavigationAgent2D)
        self.assertIsNotNone(a2)
        self.assertTrue(a2.velocity_x != 0.0 or a2.velocity_y != 0.0,
                        "Agent2 should still move along path")

    def test_tileset_to_navigation_grid(self):
        """build_grid_from_tileset creates walkable grid from TileSet nav data."""
        tileset = TileSetResource(resource_id="test_ts")
        source = TileSetAtlasSource(source_id="src1", tile_width=32, tile_height=32,
                                     texture_region_w=96, texture_region_h=32, columns=3)
        source.set_tile_metadata("src1_0_0", TileMetaData(
            tile_id="src1_0_0",
            navigation_polygon=TileNavigationPolygon(points=[[0, 0], [32, 0], [32, 32], [0, 32]]),
        ))
        source.set_tile_metadata("src1_1_0", TileMetaData(tile_id="src1_1_0"))
        tileset.sources.append(source)

        tilemap = TilemapData(cell_width=32, cell_height=32)
        layer = tilemap.add_layer("base")
        layer.set_tile(TileCoord(x=0, y=0), TileData(
            tile_id="src1_0_0", source={"source_id": "src1"}, navigation_layer=1,
        ))
        layer.set_tile(TileCoord(x=1, y=0), TileData(
            tile_id="src1_1_0", source={"source_id": "src1"}, navigation_layer=0,
        ))

        service = NavigationService()
        grid = service.build_grid_from_tileset(tilemap, tileset, default_walkable=False)

        self.assertTrue(grid.is_walkable(0, 0), "Tile with nav polygon should be walkable")
        self.assertFalse(grid.is_walkable(1, 0), "Tile without nav polygon should be blocked")

    def test_navigation_region_cost(self):
        """NavigationRegion2D round-trips enter_cost and travel_cost."""
        region = NavigationRegion2D(
            navigation_polygon_path="res://nav.navpoly",
            enter_cost=5.0, travel_cost=2.0, navigation_layers=3,
        )
        data = region.to_dict()
        restored = NavigationRegion2D.from_dict(data)
        self.assertEqual(restored.enter_cost, 5.0)
        self.assertEqual(restored.travel_cost, 2.0)
        self.assertEqual(restored.navigation_layers, 3)

    def test_dynamic_obstacle_serialization(self):
        """NavigationObstacle2D round-trips through to_dict/from_dict."""
        obstacle = NavigationObstacle2D(radius=48.0, estimated=True)
        data = obstacle.to_dict()
        restored = NavigationObstacle2D.from_dict(data)
        self.assertEqual(restored.radius, 48.0)
        self.assertTrue(restored.estimated)
        self.assertTrue(restored.affect_navigation)
        self.assertTrue(restored.affect_avoidance)

    def test_navigation_polygon_serialization(self):
        """NavigationPolygon round-trips through to_dict/from_dict."""
        poly = NavigationPolygon(
            resource_id="nav_1",
            vertices=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
            polygons=[[0, 1, 2], [0, 2, 3]],
        )
        data = poly.to_dict()
        restored = NavigationPolygon.from_dict(data)
        self.assertEqual(restored.resource_id, "nav_1")
        self.assertEqual(len(restored.vertices), 4)
        self.assertEqual(len(restored.polygons), 2)

    def test_navigation_polygon_from_rect(self):
        """NavigationPolygon.from_rect creates a rectangular polygon."""
        poly = NavigationPolygon.from_rect(10, 20, 100, 200, "rect_nav")
        self.assertEqual(poly.resource_id, "rect_nav")
        self.assertEqual(len(poly.vertices), 4)
        self.assertEqual(len(poly.polygons), 2)

    def test_tileset_grid_respects_default_walkable(self):
        """Empty tilemap uses default_walkable for all cells."""
        tileset = TileSetResource(resource_id="empty_ts")
        tilemap = TilemapData(cell_width=16, cell_height=16)
        tilemap.add_layer("base")

        service = NavigationService()
        grid = service.build_grid_from_tileset(tilemap, tileset, default_walkable=True)
        self.assertTrue(grid.is_walkable(0, 0))

        grid2 = service.build_grid_from_tileset(tilemap, tileset, default_walkable=False)
        self.assertFalse(grid2.is_walkable(0, 0))

    def test_navigation_obstacle_avoidance(self):
        """Obstacle with affect_avoidance=True should not crash avoidance system."""
        world = World()
        grid = self._make_grid(10, 10)
        service = NavigationService(grid)
        system = NavigationAgentSystem(nav_service=service)

        obstacle = world.create_entity("obstacle")
        obstacle.add_component(Transform(x=100.0, y=100.0))
        obstacle.add_component(NavigationObstacle2D(radius=40.0, affect_avoidance=True))

        agent = world.create_entity("agent")
        agent.add_component(Transform(x=100.0, y=65.0))
        agent.add_component(NavigationAgent2D(
            target_x=500.0, target_y=65.0,
            speed=50.0, avoidance_radius=30.0,
        ))

        system.update(world, 0.016)
        a = agent.get_component(NavigationAgent2D)
        self.assertIsNotNone(a)

    def test_navigation_obstacle_disabled_avoidance(self):
        """Obstacle with affect_avoidance=False should not affect agent."""
        world = World()
        grid = self._make_grid(10, 10)
        service = NavigationService(grid)
        system = NavigationAgentSystem(nav_service=service)

        obstacle = world.create_entity("obstacle")
        obstacle.add_component(Transform(x=100.0, y=100.0))
        obstacle.add_component(NavigationObstacle2D(radius=40.0, affect_avoidance=False))

        agent = world.create_entity("agent")
        agent.add_component(Transform(x=100.0, y=65.0))
        agent.add_component(NavigationAgent2D(
            target_x=500.0, target_y=65.0,
            speed=50.0, avoidance_radius=30.0,
        ))

        system.update(world, 0.016)
        a = agent.get_component(NavigationAgent2D)
        self.assertIsNotNone(a)

    def test_obstacle_velocity_setter(self):
        """Obstacle velocity can be set via set_velocity."""
        obstacle = NavigationObstacle2D()
        obstacle.set_velocity(10.0, -5.0)
        self.assertEqual(obstacle._velocity_x, 10.0)
        self.assertEqual(obstacle._velocity_y, -5.0)

    def test_navigation_region_defaults(self):
        """NavigationRegion2D has sensible defaults."""
        region = NavigationRegion2D()
        self.assertTrue(region.enabled)
        self.assertEqual(region.enter_cost, 0.0)
        self.assertEqual(region.travel_cost, 0.0)
        self.assertEqual(region.navigation_layers, 1)


if __name__ == "__main__":
    unittest.main()
