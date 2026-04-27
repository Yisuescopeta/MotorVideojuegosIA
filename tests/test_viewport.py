"""
tests/test_viewport.py - Tests de utilidades de viewport.
"""

import unittest

from engine.components.camera2d import Camera2D
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.utils.viewport import resolve_world_viewport_rect


class ResolveWorldViewportRectTests(unittest.TestCase):
    def test_none_world_returns_none(self) -> None:
        self.assertIsNone(resolve_world_viewport_rect(None))

    def test_no_camera_returns_none(self) -> None:
        world = World()
        world.create_entity()
        self.assertIsNone(resolve_world_viewport_rect(world))

    def test_disabled_camera_skipped(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=True)
        cam.enabled = False
        entity.add_component(cam)
        self.assertIsNone(resolve_world_viewport_rect(world))

    def test_non_primary_camera_skipped(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=False)
        cam.enabled = True
        entity.add_component(cam)
        self.assertIsNone(resolve_world_viewport_rect(world))

    def test_primary_camera_returns_rect(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=100, y=200))
        cam = Camera2D(is_primary=True, zoom=1.0)
        cam.enabled = True
        entity.add_component(cam)
        rect = resolve_world_viewport_rect(world, viewport_size=(800, 600))
        self.assertIsNotNone(rect)
        assert rect is not None
        left, top, right, bottom = rect
        self.assertEqual(left, 100 - 400)
        self.assertEqual(top, 200 - 300)
        self.assertEqual(right, 100 + 400)
        self.assertEqual(bottom, 200 + 300)

    def test_zoom_affects_rect(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=True, zoom=2.0)
        cam.enabled = True
        entity.add_component(cam)
        rect = resolve_world_viewport_rect(world, viewport_size=(800, 600))
        self.assertIsNotNone(rect)
        assert rect is not None
        left, top, right, bottom = rect
        self.assertEqual(left, -200)
        self.assertEqual(top, -150)
        self.assertEqual(right, 200)
        self.assertEqual(bottom, 150)

    def test_zero_zoom_uses_epsilon(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=True, zoom=0.0)
        cam.enabled = True
        entity.add_component(cam)
        rect = resolve_world_viewport_rect(world, viewport_size=(800, 600))
        self.assertIsNotNone(rect)
        assert rect is not None
        left, top, right, bottom = rect
        # With epsilon 1e-4, half sizes become enormous but finite
        self.assertLess(left, -1e6)
        self.assertGreater(right, 1e6)


if __name__ == "__main__":
    unittest.main()
