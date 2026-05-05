"""
tests/test_line2d.py - Tests unitarios para Line2D component.
"""

from __future__ import annotations

import unittest

from engine.components.line2d import Line2D
from engine.levels.component_registry import create_default_registry


class TestLine2DComponent(unittest.TestCase):

    def test_create_default(self):
        line = Line2D()
        self.assertTrue(line.enabled)
        self.assertEqual(line.points, [])
        self.assertEqual(line.width, 2.0)
        self.assertEqual(line.color, (255, 255, 255, 255))
        self.assertEqual(line.joint_mode, "sharp")
        self.assertFalse(line.closed)
        self.assertEqual(line.cap_mode, "none")
        self.assertEqual(line.point_count, 0)

    def test_create_with_params(self):
        line = Line2D(
            points=[[0, 0], [100, 100]],
            width=5.0,
            color=(255, 0, 0, 128),
            joint_mode="round",
            closed=True,
            cap_mode="round",
        )
        self.assertEqual(line.point_count, 2)
        self.assertEqual(line.width, 5.0)
        self.assertEqual(line.color, (255, 0, 0, 128))
        self.assertEqual(line.joint_mode, "round")
        self.assertTrue(line.closed)
        self.assertEqual(line.cap_mode, "round")

    def test_add_point(self):
        line = Line2D()
        line.add_point(10.0, 20.0)
        self.assertEqual(line.point_count, 1)
        self.assertEqual(line.points[0], [10.0, 20.0])

        line.add_point(30.0, 40.0)
        self.assertEqual(line.point_count, 2)

    def test_remove_point(self):
        line = Line2D(points=[[0, 0], [1, 1], [2, 2]])
        line.remove_point(1)
        self.assertEqual(line.point_count, 2)
        self.assertEqual(line.points, [[0, 0], [2, 2]])

        # out of bounds
        line.remove_point(5)
        self.assertEqual(line.point_count, 2)
        line.remove_point(-1)
        self.assertEqual(line.point_count, 2)

    def test_get_point(self):
        line = Line2D(points=[[10, 20], [30, 40]])
        pt = line.get_point(0)
        self.assertEqual(pt, (10.0, 20.0))
        pt = line.get_point(1)
        self.assertEqual(pt, (30.0, 40.0))
        self.assertIsNone(line.get_point(99))

    def test_set_point(self):
        line = Line2D(points=[[0, 0], [1, 1]])
        line.set_point(0, 99.0, 88.0)
        self.assertEqual(line.points[0], [99.0, 88.0])
        # out of bounds does nothing
        line.set_point(5, 1.0, 1.0)
        self.assertEqual(line.point_count, 2)

    def test_clear_points(self):
        line = Line2D(points=[[0, 0], [1, 1], [2, 2]])
        line.clear_points()
        self.assertEqual(line.point_count, 0)

    def test_point_count_property(self):
        line = Line2D()
        self.assertEqual(line.point_count, 0)
        line.add_point(0, 0)
        self.assertEqual(line.point_count, 1)

    def test_closed_property(self):
        line = Line2D(closed=True)
        self.assertTrue(line.closed)
        line.closed = False
        self.assertFalse(line.closed)

    def test_color_clamp(self):
        line = Line2D(color=(300, -10, 128, 500))
        self.assertEqual(line.color, (255, 0, 128, 255))

    def test_color_tuple_3(self):
        line = Line2D(color=(100, 150, 200))
        self.assertEqual(line.color, (100, 150, 200, 255))

    def test_color_invalid(self):
        line = Line2D()
        line.color = "invalid"  # type: ignore
        self.assertEqual(line.color, (255, 255, 255, 255))

    def test_invalid_joint_mode_defaults_to_sharp(self):
        line = Line2D(joint_mode="invalid")
        self.assertEqual(line.joint_mode, "sharp")

    def test_invalid_cap_mode_defaults_to_none(self):
        line = Line2D(cap_mode="invalid")
        self.assertEqual(line.cap_mode, "none")

    def test_negative_width_clamped(self):
        line = Line2D(width=-5.0)
        self.assertEqual(line.width, 0.0)

    def test_to_dict(self):
        line = Line2D(points=[[1, 2], [3, 4]], width=3.0, color=(255, 0, 0, 255))
        data = line.to_dict()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["points"], [[1, 2], [3, 4]])
        self.assertEqual(data["width"], 3.0)
        self.assertEqual(data["color"], [255, 0, 0, 255])
        self.assertEqual(data["joint_mode"], "sharp")
        self.assertFalse(data["closed"])
        self.assertEqual(data["cap_mode"], "none")

    def test_from_dict(self):
        data = {
            "enabled": True,
            "points": [[0.0, 0.0], [10.0, 10.0]],
            "width": 4.0,
            "color": [0, 255, 0, 128],
            "joint_mode": "round",
            "closed": True,
            "cap_mode": "round",
        }
        line = Line2D.from_dict(data)
        self.assertTrue(line.enabled)
        self.assertEqual(line.points, [[0.0, 0.0], [10.0, 10.0]])
        self.assertEqual(line.width, 4.0)
        self.assertEqual(line.color, (0, 255, 0, 128))
        self.assertEqual(line.joint_mode, "round")
        self.assertTrue(line.closed)
        self.assertEqual(line.cap_mode, "round")

    def test_from_dict_defaults(self):
        line = Line2D.from_dict({})
        self.assertTrue(line.enabled)
        self.assertEqual(line.points, [])
        self.assertEqual(line.width, 2.0)
        self.assertEqual(line.color, (255, 255, 255, 255))

    def test_roundtrip_to_from_dict(self):
        original = Line2D(
            points=[[1.5, 2.5], [3.5, 4.5], [5.5, 6.5]],
            width=3.5,
            color=(128, 64, 32, 255),
            joint_mode="round",
            closed=True,
            cap_mode="round",
        )
        encoded = original.to_dict()
        restored = Line2D.from_dict(encoded)
        self.assertEqual(restored.points, original.points)
        self.assertEqual(restored.width, original.width)
        self.assertEqual(restored.color, original.color)
        self.assertEqual(restored.joint_mode, original.joint_mode)
        self.assertEqual(restored.closed, original.closed)
        self.assertEqual(restored.cap_mode, original.cap_mode)
        self.assertEqual(restored.enabled, original.enabled)

    def test_from_dict_bad_points(self):
        data = {"points": [1, 2, 3]}
        line = Line2D.from_dict(data)
        self.assertEqual(line.points, [])

        data2 = {"points": [[0], [1]]}
        line2 = Line2D.from_dict(data2)
        self.assertEqual(line2.points, [])


class TestLine2DRegistry(unittest.TestCase):

    def test_line2d_registered(self):
        registry = create_default_registry()
        self.assertIn("Line2D", registry.list_registered())

    def test_create_from_registry(self):
        registry = create_default_registry()
        data = {
            "enabled": True,
            "points": [[1, 2], [3, 4]],
            "width": 2.0,
            "color": [255, 255, 255, 255],
        }
        component = registry.create("Line2D", data)
        self.assertIsInstance(component, Line2D)
        self.assertEqual(component.point_count, 2)
        self.assertEqual(component.width, 2.0)

    def test_descriptor(self):
        registry = create_default_registry()
        descriptor = registry.get_descriptor("Line2D")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.origin, "native")
        self.assertEqual(descriptor.badge, "CORE")


class TestLine2DRenderSystem(unittest.TestCase):

    def test_system_import(self):
        from engine.systems.line2d_render_system import Line2DRenderSystem
        system = Line2DRenderSystem()
        self.assertIsNotNone(system)

    def test_system_render_no_entities(self):
        from engine.ecs.world import World
        from engine.systems.line2d_render_system import Line2DRenderSystem

        world = World()
        system = Line2DRenderSystem()
        system.render(world)  # no crash

    def test_system_render_with_line_no_crash(self):
        from engine.components.transform import Transform
        from engine.ecs.entity import Entity
        from engine.ecs.world import World
        from engine.systems.line2d_render_system import Line2DRenderSystem

        world = World()
        entity = Entity(1, "test")
        entity.add_component(Transform(100, 100))
        entity.add_component(Line2D(points=[[0, 0], [50, 50]]))
        entity._owner_world = world
        world._entities_by_name["test"] = entity
        world._entities_by_component.setdefault(Line2D, []).append(entity)
        world._entities_by_component.setdefault(Transform, []).append(entity)

        system = Line2DRenderSystem()
        system.render(world)  # no crash

    def test_draw_thin_line_points(self):
        from engine.systems.line2d_render_system import Line2DRenderSystem

        system = Line2DRenderSystem()
        points = [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0)]
        pairs = system._build_pairs(points, closed=False)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0], ((0.0, 0.0), (10.0, 10.0)))
        self.assertEqual(pairs[1], ((10.0, 10.0), (20.0, 0.0)))

    def test_draw_closed_line_pairs(self):
        from engine.systems.line2d_render_system import Line2DRenderSystem

        system = Line2DRenderSystem()
        points = [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0)]
        pairs = system._build_pairs(points, closed=True)
        self.assertEqual(len(pairs), 3)
        self.assertEqual(pairs[2], ((20.0, 0.0), (0.0, 0.0)))

    def test_transform_points(self):
        from engine.components.transform import Transform
        from engine.systems.line2d_render_system import Line2DRenderSystem

        system = Line2DRenderSystem()
        transform = Transform(100.0, 50.0)
        points = [[10.0, 20.0], [30.0, 40.0]]
        world_pts = system._transform_points(points, transform)
        self.assertEqual(len(world_pts), 2)
        self.assertAlmostEqual(world_pts[0][0], 110.0)  # 100 + 10
        self.assertAlmostEqual(world_pts[0][1], 70.0)    # 50 + 20
        self.assertAlmostEqual(world_pts[1][0], 130.0)   # 100 + 30
        self.assertAlmostEqual(world_pts[1][1], 90.0)    # 50 + 40

    def test_draw_thick_segment_no_crash(self):
        import pyray as rl
        from engine.systems.line2d_render_system import Line2DRenderSystem
        system = Line2DRenderSystem()
        system._draw_thick_segment((0.0, 0.0), (100.0, 100.0), 5.0, rl.Color(255, 0, 0, 255))
        # Zero length segment
        system._draw_thick_segment((0.0, 0.0), (0.0, 0.0), 5.0, rl.Color(255, 0, 0, 255))


if __name__ == "__main__":
    unittest.main()
