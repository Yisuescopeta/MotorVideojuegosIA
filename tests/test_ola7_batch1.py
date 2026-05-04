"""
tests/test_ola7_batch1.py - Tests for CanvasLayer, Polygon2D UV, Navigation debug drawing.
"""

import unittest
from unittest.mock import MagicMock, patch

from engine.components.canvas_layer import CanvasLayer
from engine.components.polygon2d import Polygon2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.transform import Transform
from engine.components.navigation_agent_2d import NavigationAgent2D
from engine.components.navigation_obstacle_2d import NavigationObstacle2D
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.render_system import RenderSystem
from engine.systems.navigation_agent_system import NavigationAgentSystem


# ============================================================
# CanvasLayer tests
# ============================================================

class CanvasLayerTests(unittest.TestCase):
    def test_defaults(self) -> None:
        cl = CanvasLayer()
        self.assertEqual(cl.layer, 1)
        self.assertEqual(cl.offset_x, 0.0)
        self.assertEqual(cl.offset_y, 0.0)
        self.assertEqual(cl.rotation, 0.0)
        self.assertEqual(cl.scale_x, 1.0)
        self.assertEqual(cl.scale_y, 1.0)
        self.assertTrue(cl.visible)
        self.assertFalse(cl.follow_viewport)
        self.assertEqual(cl.follow_viewport_scale, 1.0)
        self.assertEqual(cl.custom_viewport_path, "")

    def test_custom_values(self) -> None:
        cl = CanvasLayer(
            layer=5,
            offset_x=10.0,
            offset_y=20.0,
            rotation=45.0,
            scale_x=2.0,
            scale_y=0.5,
            visible=False,
            follow_viewport=True,
            follow_viewport_scale=2.0,
            custom_viewport_path="/path/to/viewport",
        )
        self.assertEqual(cl.layer, 5)
        self.assertEqual(cl.offset_x, 10.0)
        self.assertEqual(cl.offset_y, 20.0)
        self.assertEqual(cl.rotation, 45.0)
        self.assertEqual(cl.scale_x, 2.0)
        self.assertEqual(cl.scale_y, 0.5)
        self.assertFalse(cl.visible)
        self.assertTrue(cl.follow_viewport)
        self.assertEqual(cl.follow_viewport_scale, 2.0)
        self.assertEqual(cl.custom_viewport_path, "/path/to/viewport")

    def test_serialization_round_trip(self) -> None:
        cl = CanvasLayer(
            layer=3,
            offset_x=5.0,
            offset_y=-10.0,
            rotation=90.0,
            scale_x=0.8,
            scale_y=1.2,
            visible=False,
            follow_viewport=True,
            follow_viewport_scale=1.5,
            custom_viewport_path="sub_viewport",
        )
        data = cl.to_dict()
        restored = CanvasLayer.from_dict(data)
        self.assertEqual(restored.layer, 3)
        self.assertEqual(restored.offset_x, 5.0)
        self.assertEqual(restored.offset_y, -10.0)
        self.assertEqual(restored.rotation, 90.0)
        self.assertEqual(restored.scale_x, 0.8)
        self.assertEqual(restored.scale_y, 1.2)
        self.assertFalse(restored.visible)
        self.assertTrue(restored.follow_viewport)
        self.assertEqual(restored.follow_viewport_scale, 1.5)
        self.assertEqual(restored.custom_viewport_path, "sub_viewport")

    def test_visible_toggle(self) -> None:
        cl = CanvasLayer()
        self.assertTrue(cl.visible)
        cl.visible = False
        self.assertFalse(cl.visible)
        cl.visible = True
        self.assertTrue(cl.visible)

    def test_layer_must_be_int(self) -> None:
        cl = CanvasLayer(layer=3.7)
        self.assertIsInstance(cl.layer, int)
        self.assertEqual(cl.layer, 3)


# ============================================================
# Polygon2D UV tests
# ============================================================

class Polygon2DUVTests(unittest.TestCase):
    def test_defaults_uvs_empty(self) -> None:
        poly = Polygon2D(points=[[0, 0], [10, 0], [10, 10], [0, 10]])
        self.assertEqual(poly.uvs, [])
        self.assertEqual(poly.internal_vertices, 0)

    def test_uvs_provided(self) -> None:
        uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        poly = Polygon2D(
            points=[[0, 0], [10, 0], [10, 10], [0, 10]],
            uvs=uvs,
            internal_vertices=2,
        )
        self.assertEqual(len(poly.uvs), 4)
        self.assertEqual(poly.uvs[0], (0.0, 0.0))
        self.assertEqual(poly.uvs[1], (1.0, 0.0))
        self.assertEqual(poly.uvs[2], (1.0, 1.0))
        self.assertEqual(poly.uvs[3], (0.0, 1.0))
        self.assertEqual(poly.internal_vertices, 2)

    def test_uvs_serialization(self) -> None:
        uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
        poly = Polygon2D(
            points=[[0, 0], [10, 0], [10, 10]],
            uvs=uvs,
            internal_vertices=1,
        )
        data = poly.to_dict()
        self.assertIn("uvs", data)
        self.assertEqual(len(data["uvs"]), 3)
        self.assertEqual(data["uvs"][0], [0.0, 0.0])
        self.assertEqual(data["internal_vertices"], 1)

    def test_uvs_deserialization(self) -> None:
        data = {
            "points": [[0, 0], [10, 0], [10, 10]],
            "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
            "internal_vertices": 0,
        }
        poly = Polygon2D.from_dict(data)
        self.assertEqual(len(poly.uvs), 3)
        self.assertEqual(poly.uvs[0], (0.0, 0.0))
        self.assertEqual(poly.uvs[1], (1.0, 0.0))
        self.assertEqual(poly.uvs[2], (0.5, 1.0))

    def test_uvs_partial_mismatch(self) -> None:
        """UVs fewer than points: should store what's provided."""
        poly = Polygon2D(
            points=[[0, 0], [10, 0], [10, 10], [0, 10]],
            uvs=[(0.0, 0.0), (1.0, 1.0)],  # Only 2 UVs for 4 points
        )
        self.assertEqual(len(poly.uvs), 2)
        self.assertEqual(len(poly.points), 4)


# ============================================================
# RenderOrder2D canvas_layer_entity tests
# ============================================================

class RenderOrder2DCanvasLayerTests(unittest.TestCase):
    def test_default_canvas_layer_entity_empty(self) -> None:
        ro = RenderOrder2D()
        self.assertEqual(ro.canvas_layer_entity, "")

    def test_canvas_layer_entity_set(self) -> None:
        ro = RenderOrder2D(canvas_layer_entity="HUDLayer")
        self.assertEqual(ro.canvas_layer_entity, "HUDLayer")

    def test_canvas_layer_entity_serialization(self) -> None:
        ro = RenderOrder2D(
            sorting_layer="UI",
            order_in_layer=5,
            render_pass="Overlay",
            canvas_layer_entity="HUDRoot",
        )
        data = ro.to_dict()
        self.assertEqual(data["canvas_layer_entity"], "HUDRoot")
        restored = RenderOrder2D.from_dict(data)
        self.assertEqual(restored.canvas_layer_entity, "HUDRoot")
        self.assertEqual(restored.sorting_layer, "UI")
        self.assertEqual(restored.order_in_layer, 5)
        self.assertEqual(restored.render_pass, "Overlay")


# ============================================================
# CanvasLayer in RenderSystem tests
# ============================================================

class CanvasLayerRenderSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()

    def test_build_canvas_layer_map(self) -> None:
        rs = RenderSystem()
        # Create CanvasLayer entity
        cl_entity = Entity("HUDLayer")
        cl_entity.add_component(Transform(x=0, y=0))
        cl_entity.add_component(CanvasLayer(layer=2, offset_x=10, scale_x=2.0, visible=True))
        self.world.add_entity(cl_entity)

        # Create another CanvasLayer entity (invisible)
        hidden_entity = Entity("HiddenLayer")
        hidden_entity.add_component(Transform(x=0, y=0))
        hidden_entity.add_component(CanvasLayer(layer=3, visible=False))
        self.world.add_entity(hidden_entity)

        layer_map = rs._build_canvas_layer_map(self.world)
        self.assertIn("HUDLayer", layer_map)
        self.assertNotIn("HiddenLayer", layer_map)
        self.assertEqual(layer_map["HUDLayer"]["layer"], 2)
        self.assertEqual(layer_map["HUDLayer"]["offset_x"], 10.0)
        self.assertEqual(layer_map["HUDLayer"]["scale_x"], 2.0)

    def test_canvas_layer_entity_in_render_command(self) -> None:
        """Verify that RenderOrder2D.canvas_layer_entity flows into RenderCommand."""
        world = World()
        entity = Entity("TestSprite")
        entity.add_component(Transform(x=100, y=200))
        entity.add_component(RenderOrder2D(canvas_layer_entity="HUDLayer"))
        world.add_entity(entity)

        rs = RenderSystem()
        graph = rs._build_render_graph(world, viewport_size=(800, 600))
        world_pass = next((p for p in graph["passes"] if p["name"] == "World"), None)
        self.assertIsNotNone(world_pass)
        commands = world_pass["commands"]
        entity_cmds = [c for c in commands if c["kind"] == "entity"]
        self.assertTrue(len(entity_cmds) > 0)
        self.assertEqual(str(entity_cmds[0].get("canvas_layer_entity", "")), "HUDLayer")


# ============================================================
# Navigation debug drawing tests
# ============================================================

class NavigationDebugPrimitivesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()

    def _create_mock_grid(self):
        from engine.navigation.grid import NavigationGrid
        grid = NavigationGrid(width=10, height=8, cell_size=32)
        return grid

    def test_empty_world_produces_empty_primitives(self) -> None:
        nav_system = NavigationAgentSystem()
        primitives = nav_system.get_debug_primitives(self.world)
        self.assertEqual(primitives, [])

    def test_agent_with_path_produces_path_primitive(self) -> None:
        agent_entity = Entity("NavAgent")
        agent_entity.add_component(Transform(x=50, y=60))
        agent = NavigationAgent2D()
        agent.enabled = True
        agent.path = [[100.0, 200.0], [150.0, 250.0], [300.0, 400.0]]
        agent.avoidance_radius = 0.0
        agent_entity.add_component(agent)
        self.world.add_entity(agent_entity)

        nav_system = NavigationAgentSystem()
        primitives = nav_system.get_debug_primitives(self.world)
        path_primitives = [p for p in primitives if p["kind"] == "navigation_path"]
        self.assertEqual(len(path_primitives), 1)
        path = path_primitives[0]
        self.assertEqual(path["color"], [50, 255, 50, 150])
        self.assertIn([50.0, 60.0], path["points"])
        self.assertIn([300.0, 400.0], path["points"])

    def test_agent_with_avoidance_radius(self) -> None:
        agent_entity = Entity("NavAgent2")
        agent_entity.add_component(Transform(x=30, y=40))
        agent = NavigationAgent2D()
        agent.enabled = True
        agent.path = []
        agent.avoidance_radius = 25.0
        agent_entity.add_component(agent)
        self.world.add_entity(agent_entity)

        nav_system = NavigationAgentSystem()
        primitives = nav_system.get_debug_primitives(self.world)
        radius_primitives = [p for p in primitives if p["kind"] == "navigation_radius" and p["entity_name"] == "NavAgent2"]
        self.assertEqual(len(radius_primitives), 1)
        self.assertEqual(radius_primitives[0]["radius"], 25.0)
        self.assertEqual(radius_primitives[0]["color"], [255, 255, 50, 150])

    def test_disabled_agent_not_drawn(self) -> None:
        agent_entity = Entity("DisabledAgent")
        agent_entity.add_component(Transform(x=10, y=10))
        agent = NavigationAgent2D()
        agent.enabled = False
        agent.path = [[100.0, 200.0]]
        agent.avoidance_radius = 10.0
        agent_entity.add_component(agent)
        self.world.add_entity(agent_entity)

        nav_system = NavigationAgentSystem()
        primitives = nav_system.get_debug_primitives(self.world)
        self.assertEqual(len(primitives), 0)

    def test_obstacle_radius_primitive(self) -> None:
        obs_entity = Entity("Obstacle1")
        obs_entity.add_component(Transform(x=200, y=300))
        obstacle = NavigationObstacle2D()
        obstacle.radius = 15.0
        obstacle.affect_avoidance = True
        obs_entity.add_component(obstacle)
        self.world.add_entity(obs_entity)

        nav_system = NavigationAgentSystem()
        primitives = nav_system.get_debug_primitives(self.world)
        obs_primitives = [p for p in primitives if p["entity_name"] == "Obstacle1"]
        self.assertEqual(len(obs_primitives), 1)
        self.assertEqual(obs_primitives[0]["radius"], 15.0)
        self.assertEqual(obs_primitives[0]["color"], [255, 50, 50, 150])

    def test_obstacle_zero_radius_not_drawn(self) -> None:
        obs_entity = Entity("SmallObstacle")
        obs_entity.add_component(Transform(x=100, y=100))
        obstacle = NavigationObstacle2D()
        obstacle.radius = 0.0
        obs_entity.add_component(obstacle)
        self.world.add_entity(obs_entity)

        nav_system = NavigationAgentSystem()
        primitives = nav_system.get_debug_primitives(self.world)
        obs_primitives = [p for p in primitives if p["entity_name"] == "SmallObstacle"]
        self.assertEqual(len(obs_primitives), 0)

    def test_navigation_polygon_with_grid(self) -> None:
        """When nav_service has a grid, a navigation_polygon primitive is produced."""
        grid = self._create_mock_grid()
        from engine.navigation.service import NavigationService
        nav_service = NavigationService(grid=grid)
        nav_system = NavigationAgentSystem(nav_service=nav_service)

        primitives = nav_system.get_debug_primitives(self.world)
        poly_primitives = [p for p in primitives if p["kind"] == "navigation_polygon"]
        self.assertEqual(len(poly_primitives), 1)
        poly = poly_primitives[0]
        self.assertEqual(poly["color"], [50, 100, 255, 150])
        self.assertEqual(poly["entity_name"], "__nav_grid__")
        # Grid is 10x8 with cell_size=32
        self.assertEqual(poly["points"][0], [0.0, 0.0])
        self.assertEqual(poly["points"][2], [320.0, 256.0])

    def test_navigation_polygon_without_grid(self) -> None:
        """Without grid, no navigation_polygon primitive."""
        nav_system = NavigationAgentSystem()
        # No nav_service → no grid → no polygon
        primitives = nav_system.get_debug_primitives(self.world)
        poly_primitives = [p for p in primitives if p["kind"] == "navigation_polygon"]
        self.assertEqual(len(poly_primitives), 0)


# ============================================================
# Debug primitive normalization tests
# ============================================================

class DebugPrimitiveNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rs = RenderSystem()

    def test_normalize_navigation_polygon(self) -> None:
        prim = {
            "kind": "navigation_polygon",
            "color": [50, 100, 255, 150],
            "points": [[0, 0], [100, 0], [100, 50]],
        }
        normalized = self.rs._normalize_debug_primitive(prim)
        self.assertEqual(normalized["kind"], "navigation_polygon")
        self.assertEqual(normalized["points"], [[0.0, 0.0], [100.0, 0.0], [100.0, 50.0]])

    def test_normalize_navigation_path(self) -> None:
        prim = {
            "kind": "navigation_path",
            "color": [50, 255, 50, 150],
            "points": [[0, 0], [50, 50]],
        }
        normalized = self.rs._normalize_debug_primitive(prim)
        self.assertEqual(normalized["kind"], "navigation_path")
        self.assertEqual(normalized["points"], [[0.0, 0.0], [50.0, 50.0]])

    def test_normalize_navigation_radius(self) -> None:
        prim = {
            "kind": "navigation_radius",
            "color": [255, 255, 50, 150],
            "x": 100,
            "y": 200,
            "radius": 25.0,
        }
        normalized = self.rs._normalize_debug_primitive(prim)
        self.assertEqual(normalized["kind"], "navigation_radius")
        self.assertEqual(normalized["x"], 100.0)
        self.assertEqual(normalized["y"], 200.0)
        self.assertEqual(normalized["radius"], 25.0)


# ============================================================
# RenderSystem debug options with navigation
# ============================================================

class RenderSystemDebugNavigationTests(unittest.TestCase):
    def test_draw_navigation_flag_default_off(self) -> None:
        rs = RenderSystem()
        self.assertFalse(rs.debug_draw_navigation)

    def test_set_debug_options_draw_navigation(self) -> None:
        rs = RenderSystem()
        rs.set_debug_options(draw_navigation=True)
        self.assertTrue(rs.debug_draw_navigation)

    def test_get_debug_state_includes_navigation(self) -> None:
        rs = RenderSystem()
        rs.set_debug_options(draw_navigation=True)
        state = rs.get_debug_state()
        self.assertTrue(state["draw_navigation"])


if __name__ == "__main__":
    unittest.main()
